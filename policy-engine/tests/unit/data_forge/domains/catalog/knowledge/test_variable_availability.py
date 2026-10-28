"""Real Catalog presence counts retain the existing logical-read custody guard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pytest

from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
    CatalogReadSourceError,
    CatalogSelectionError,
)
from polisyos.data_forge.domains.catalog.knowledge.store import DatasetCatalogStore


def _catalog(path: Path, *, populated: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as connection:
        connection.execute("CREATE TABLE ds_metric_bindings(metric_id VARCHAR, source VARCHAR)")
        connection.execute("CREATE TABLE ds_observations(canonical_var VARCHAR)")
        connection.execute("CREATE TABLE ds_datasets(polisyos_metrics VARCHAR[])")
        if populated:
            connection.execute(
                "INSERT INTO ds_metric_bindings VALUES ('government.balance', NULL), "
                "('government.balance', '')"
            )
            connection.execute(
                "INSERT INTO ds_observations VALUES ('government.balance'), "
                "('government.balance'), ('unrelated')"
            )
            connection.execute("INSERT INTO ds_datasets VALUES (['government.balance'])")


def test_availability_reads_all_actual_owner_inputs_without_source_filter(tmp_path: Path) -> None:
    database = tmp_path / "catalog.duckdb"
    _catalog(database, populated=True)
    reader = DatasetCatalogStore(database, database.parent)
    try:
        assert reader.variable_availability_counts("government.balance") == (2, 2, 1)
        assert reader.variable_availability_counts("unrelated") == (0, 1, 0)
        assert reader.variable_availability_counts("absent") == (0, 0, 0)
    finally:
        reader.close()


def test_replacement_during_actual_count_read_refuses_before_result_escapes(tmp_path: Path) -> None:
    database = tmp_path / "catalog.duckdb"
    replacement = tmp_path / "replacement.duckdb"
    _catalog(database, populated=True)
    _catalog(replacement, populated=False)
    reader = DatasetCatalogStore(database, database.parent)
    native_connection = reader._con

    class ReplaceAfterFirstActualQuery:
        changed = False

        def execute(self, query: str, parameters: list[str]) -> Any:
            actual = native_connection.execute(query, parameters)
            if not self.changed:
                replacement.replace(database)
                self.changed = True
            return actual

        def close(self) -> None:
            native_connection.close()

    reader._con = ReplaceAfterFirstActualQuery()  # type: ignore[assignment]
    try:
        with pytest.raises(CatalogSelectionError, match="catalog_read_session_stale"):
            reader.variable_availability_counts("government.balance")
    finally:
        reader.close()


@pytest.mark.parametrize("member", ["baseline", "overlay"])
def test_read_identity_refuses_uncheckpointed_native_wal_without_deleting_it(
    tmp_path: Path, member: str
) -> None:
    database = tmp_path / "catalog.duckdb"
    overlay = tmp_path / "overlay.duckdb"
    _catalog(database, populated=False)
    _catalog(overlay, populated=False)
    target = database if member == "baseline" else overlay
    wal = target.with_name(target.name + ".wal")
    wal.write_bytes(b"uncommitted native state must not be ignored")
    before = wal.read_bytes()
    with pytest.raises(CatalogSelectionError, match="catalog_read_source_checkpoint_required"):
        DatasetCatalogStore.identify_read_sources(database, overlay_path=overlay)
    assert wal.read_bytes() == before


@pytest.mark.parametrize("member", ["baseline", "overlay"])
def test_existing_read_scope_preserves_an_appearing_wal_refusal(
    tmp_path: Path, member: str
) -> None:
    database = tmp_path / "catalog.duckdb"
    overlay = tmp_path / "overlay.duckdb"
    _catalog(database, populated=True)
    # The optional overlay is absent during open; this probes fresh identity
    # refusal, without passing a malformed overlay off as an admitted epoch.
    reader = DatasetCatalogStore(database, database.parent, overlay_path=overlay)
    if member == "overlay":
        _catalog(overlay, populated=False)
    target = database if member == "baseline" else overlay
    wal = target.with_name(target.name + ".wal")
    wal.write_bytes(b"pending native owner state")
    try:
        with pytest.raises(CatalogSelectionError) as failure:
            reader.variable_availability_counts("government.balance")
        assert failure.value.code == "catalog_read_source_checkpoint_required"
        assert wal.read_bytes() == b"pending native owner state"
    finally:
        reader.close()


def test_closed_native_backend_is_a_typed_source_error_not_zero_counts(tmp_path: Path) -> None:
    database = tmp_path / "catalog.duckdb"
    _catalog(database, populated=True)
    reader = DatasetCatalogStore(database, database.parent)
    reader.close()
    with pytest.raises(CatalogSelectionError) as failure:
        reader.variable_availability_counts("government.balance")
    assert failure.value.code == "catalog_read_native_query_unavailable"
    assert isinstance(failure.value.__cause__, duckdb.Error)


def test_initial_identity_io_failure_is_typed_not_a_missing_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "catalog.duckdb"
    _catalog(database, populated=True)
    original_open = Path.open

    def refuse_only_the_owned_native_read(path: Path, *args, **kwargs):
        if path == database:
            raise PermissionError("controlled unavailable read")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", refuse_only_the_owned_native_read)
    with pytest.raises(CatalogSelectionError) as failure:
        DatasetCatalogStore.identify_read_sources(database)
    assert failure.value.code == "catalog_read_source_unavailable"
    assert isinstance(failure.value.__cause__, PermissionError)


@pytest.mark.parametrize("entry", ["identity", "initial_store"])
def test_empty_initial_native_identity_is_typed_error_not_absent_data(
    tmp_path: Path, entry: str
) -> None:
    database = tmp_path / "empty.duckdb"
    database.write_bytes(b"")

    def read_initial_source():
        if entry == "identity":
            return DatasetCatalogStore.identify_read_sources(database)
        return DatasetCatalogStore(database, database.parent)

    with pytest.raises(CatalogSelectionError) as failure:
        read_initial_source()
    assert isinstance(failure.value, CatalogReadSourceError)
    assert failure.value.code == "catalog_read_source_unavailable"
    assert isinstance(failure.value.__cause__, ValueError)
