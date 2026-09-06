from __future__ import annotations

import json
from pathlib import Path

import duckdb

from polisyos.data_forge.domains.academic.knowledge.skg_store import (
    ensure_skg_schema,
    skg_materialized_schema_identity,
    skg_schema_generation_basis,
)
from polisyos.data_forge.domains.academic.shadow import load_academic_shadow_bundle
from polisyos.data_forge.kernel.io.generation_basis import build_generation_basis


def _write_shadow_snapshot(
    root: Path,
    *,
    schema_generation: object = None,
    materialized_schema_identity: str | None = None,
) -> None:
    publish_root = root / "publish"
    publish_root.mkdir(parents=True)
    readiness = {
        "canonical_runtime_ready": True,
        "parameter_utility_ready": True,
        "consumer_ready": True,
    }
    readiness_payload: dict[str, object] = {
        "kind": "academic_pipeline_readiness",
        "readiness": readiness,
    }
    if schema_generation is not None:
        readiness_payload["schema_generation"] = schema_generation
    if materialized_schema_identity is not None:
        readiness_payload["materialized_schema_identity"] = materialized_schema_identity
    (publish_root / "academic_pipeline_readiness.json").write_text(
        json.dumps(readiness_payload),
        encoding="utf-8",
    )
    (publish_root / "manifest.json").write_text(
        json.dumps(
            {
                "pipeline": "academic",
                "artifacts": [],
                "extra": {
                    "readiness_report": "publish/academic_pipeline_readiness.json",
                    "readiness": readiness,
                },
            }
        ),
        encoding="utf-8",
    )


def test_shadow_consumer_accepts_the_current_schema_generation(tmp_path: Path) -> None:
    current = skg_schema_generation_basis()
    db_path = tmp_path / "graph" / "scholar_knowledge.duckdb"
    db_path.parent.mkdir(parents=True)
    with duckdb.connect(str(db_path)) as connection:
        ensure_skg_schema(connection)
    materialized_identity = skg_materialized_schema_identity(db_path)
    _write_shadow_snapshot(
        tmp_path,
        schema_generation=current.to_dict(),
        materialized_schema_identity=materialized_identity,
    )

    bundle = load_academic_shadow_bundle(tmp_path)

    assert bundle.consumer_ready is True
    assert bundle.readiness["schema_generation_current"] is True
    assert bundle.readiness_summary.failed_readiness_checks == ()
    assert bundle.warnings == ()


def test_shadow_consumer_reports_an_unrecorded_schema_generation(tmp_path: Path) -> None:
    current = skg_schema_generation_basis()
    _write_shadow_snapshot(tmp_path)

    bundle = load_academic_shadow_bundle(tmp_path)

    assert bundle.consumer_ready is False
    assert bundle.readiness["schema_generation_current"] is False
    assert bundle.readiness_summary.failed_readiness_checks == (
        "schema_generation_current",
    )
    assert bundle.warnings == (
        "academic SKG schema generation drift: status=missing; "
        f"recorded_generation=unrecorded; current_generation={current.basis_digest}; "
        "recorded_rule_version=unrecorded; "
        f"current_rule_version={current.generator_rule_version}",
    )


def test_shadow_consumer_names_recorded_and_current_schema_generations(
    tmp_path: Path,
) -> None:
    current = skg_schema_generation_basis()
    recorded = build_generation_basis(
        basis_kind="academic_skg_duckdb_schema",
        generator_rule_version="policyos.academic.skg_schema_generation.v0",
        members=(("skg_ddl", b"older DDL"), ("compatibility_alters", b"[]")),
    )
    _write_shadow_snapshot(tmp_path, schema_generation=recorded.to_dict())

    bundle = load_academic_shadow_bundle(tmp_path)

    assert bundle.consumer_ready is False
    assert bundle.readiness["schema_generation_current"] is False
    assert bundle.warnings == (
        "academic SKG schema generation drift: status=incompatible; "
        f"recorded_generation={recorded.basis_digest}; "
        f"current_generation={current.basis_digest}; "
        f"recorded_rule_version={recorded.generator_rule_version}; "
        f"current_rule_version={current.generator_rule_version}",
    )


def test_shadow_consumer_rejects_materialized_schema_drift(tmp_path: Path) -> None:
    current = skg_schema_generation_basis()
    db_path = tmp_path / "graph" / "scholar_knowledge.duckdb"
    db_path.parent.mkdir(parents=True)
    with duckdb.connect(str(db_path)) as connection:
        ensure_skg_schema(connection)
    recorded_schema_identity = skg_materialized_schema_identity(db_path)
    with duckdb.connect(str(db_path)) as connection:
        connection.execute("DROP TABLE ac_skg_span_grounded_claims")
    current_schema_identity = skg_materialized_schema_identity(db_path)
    _write_shadow_snapshot(
        tmp_path,
        schema_generation=current.to_dict(),
        materialized_schema_identity=recorded_schema_identity,
    )

    bundle = load_academic_shadow_bundle(tmp_path)

    assert bundle.consumer_ready is False
    assert bundle.readiness["schema_generation_current"] is False
    assert bundle.warnings == (
        "academic SKG schema generation drift: status=incompatible; "
        f"recorded_generation={current.basis_digest}; "
        f"current_generation={current.basis_digest}; "
        f"recorded_rule_version={current.generator_rule_version}; "
        f"current_rule_version={current.generator_rule_version}; "
        f"recorded_schema_identity={recorded_schema_identity}; "
        f"current_schema_identity={current_schema_identity}",
    )
