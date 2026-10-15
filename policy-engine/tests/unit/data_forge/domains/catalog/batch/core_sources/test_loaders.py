from __future__ import annotations

import pytest

from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CoreSourcesCompatibilityContext,
    bind_core_sources_compatibility_context,
)
from polisyos.data_forge.domains.catalog.batch.core_sources import loaders, transformers


def test_core_sources_loaders_resolve_repo_data_paths() -> None:
    assert loaders._seed_alignments_path().exists()


def test_loader_resolves_transformer_dependency_without_facade_bootstrap(monkeypatch) -> None:
    monkeypatch.delattr(loaders, "_to_iso3", raising=False)
    monkeypatch.setattr(transformers, "_to_iso3", lambda _country_code: "CANONICAL")

    assert loaders._bulk_country_values("ilo", ("UA",)) == ["CANONICAL"]


def test_core_sources_loaders_keep_facade_compatibility() -> None:
    from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade

    assert facade._seed_alignments_path().exists()


def test_loader_reads_wvs_path_from_request_context(tmp_path) -> None:
    scoped_path = tmp_path / "scoped-missing-wvs.csv"
    context = CoreSourcesCompatibilityContext(
        {(loaders.__name__, "_wvs_bulk_csv_path"): lambda: scoped_path}
    )

    with (
        bind_core_sources_compatibility_context(context),
        pytest.raises(RuntimeError, match=str(scoped_path)),
    ):
        loaders._load_wvs_bulk_duckdb(["A165"])
