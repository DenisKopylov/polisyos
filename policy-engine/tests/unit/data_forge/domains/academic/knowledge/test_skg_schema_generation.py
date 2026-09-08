from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
from polisyos.data_forge.domains.academic.batch.graph_builder import run_graph_load
from polisyos.data_forge.domains.academic.knowledge import skg_store


def test_skg_schema_generation_is_reproducible_and_ddl_sensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = skg_store.skg_schema_generation_basis()
    repeated = skg_store.skg_schema_generation_basis()

    monkeypatch.setattr(
        skg_store,
        "SKG_DDL",
        skg_store.SKG_DDL + "\n-- schema-generation mutation\n",
    )
    changed = skg_store.skg_schema_generation_basis()

    assert first == repeated
    assert tuple(member.identifier for member in first.members) == (
        "compatibility_alters",
        "skg_ddl",
    )
    assert first.basis_digest != changed.basis_digest


def test_graph_load_persists_the_schema_generation_it_materialized(
    tmp_path: Path,
) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snapshot")
    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    config.merged_records_path.write_text("", encoding="utf-8")

    run_graph_load(config)

    manifest = json.loads(
        (config.manifests_dir / "graph_load.json").read_text(encoding="utf-8")
    )
    assert manifest["metrics"]["schema_generation"] == (
        skg_store.skg_schema_generation_basis().to_dict()
    )
    assert manifest["metrics"]["materialized_schema_identity"] == (
        skg_store.skg_materialized_schema_identity(config.db_path)
    )


def test_materialized_schema_identity_changes_when_a_table_disappears(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "academic.duckdb"
    with duckdb.connect(str(db_path)) as connection:
        skg_store.ensure_skg_schema(connection)
    current = skg_store.skg_materialized_schema_identity(db_path)

    with duckdb.connect(str(db_path)) as connection:
        connection.execute("DROP TABLE ac_skg_span_grounded_claims")
    changed = skg_store.skg_materialized_schema_identity(db_path)

    assert current != changed


def test_materialized_schema_identity_ignores_row_content_changes(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "academic.duckdb"
    with duckdb.connect(str(db_path)) as connection:
        skg_store.ensure_skg_schema(connection)
    current = skg_store.skg_materialized_schema_identity(db_path)

    with duckdb.connect(str(db_path)) as connection:
        connection.execute(
            """
            INSERT INTO ac_skg_versions(
                version_id,
                created_ts,
                n_articles,
                n_edges,
                n_variables,
                description
            ) VALUES (1, '2026-09-02T00:00:00+00:00', 0, 0, 0, 'content change')
            """
        )
    after_row_change = skg_store.skg_materialized_schema_identity(db_path)

    assert after_row_change == current
