from __future__ import annotations

# ruff: noqa: S101, S608, TC003
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import polisyos.runtime.quality.capability_index_compiler as compiler
from polisyos.runtime.quality.capability_index import (
    AuthorityEnvelope,
    CapabilityConflictRecord,
    CapabilityScope,
    EvidenceCapability,
    FailureModeNode,
    FreshnessEnvelope,
    QualityScore,
    RightsEnvelope,
)
from polisyos.runtime.quality.capability_index_compiler import (
    CapabilityIndexCompilerConfig,
    build_capability_discovery_snapshot,
    compile_capability_index,
    create_capability_index_fixture_inputs,
    validate_capability_authority,
)


def test_discovery_snapshot_projects_owner_kinds_and_never_world_agents(
    tmp_path: Path,
) -> None:
    input_root = create_capability_index_fixture_inputs(tmp_path / "production_data")
    result = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=input_root,
            output_dir=tmp_path / "out",
            mode="fixture",
            generated_at="2026-05-25T00:00:00Z",
        )
    )

    rows = build_capability_discovery_snapshot(result.capability_index)

    assert {row.resource_kind for row in rows} >= {"method", "dataset", "legal_norm"}
    assert all(row.resource_kind != "agent" for row in rows)
    assert all("agent_registry" not in ref for row in rows for ref in row.provenance_refs)
    legal_rows = tuple(row for row in rows if row.resource_kind == "legal_norm")
    assert legal_rows
    assert all(row.owner_truth.grounding_status == "grounded" for row in legal_rows)
    assert all(row.owner_truth.hallucination_status == "verified_clear" for row in legal_rows)
    assert all(row.owner_truth.jurisdiction == "UA" for row in legal_rows)
    assert all(row.owner_truth.temporal_resolution_status == "resolved" for row in legal_rows)
    assert all(
        row.owner_truth.temporal_snapshot_at == datetime(2026, 5, 25, tzinfo=UTC)
        for row in legal_rows
    )

    method = next(
        capability
        for capability in result.capability_index.capabilities
        if "foundry_method_contract" in capability.modality
    )
    no_source_method = method.model_copy(update={"source_assets": (), "lineage_refs": ()})
    fallback_index = result.capability_index.model_copy(
        update={"capabilities": (no_source_method,)}
    )

    fallback_rows = build_capability_discovery_snapshot(fallback_index)

    assert fallback_rows[0].provenance_refs == (result.capability_index.release_ref,)

    legal = next(
        capability
        for capability in result.capability_index.capabilities
        if "lex_norm" in capability.modality
    )
    opaque_legal = legal.model_copy(update={"metadata": {"input_groups": ("l3_lex_kg",)}})
    opaque_index = result.capability_index.model_copy(update={"capabilities": (opaque_legal,)})

    assert build_capability_discovery_snapshot(opaque_index) == ()

    owner_truth = dict(legal.metadata["legal_norm_owner_truth"])
    corruptions = (
        ("grounding_status", "candidate"),
        ("hallucination_status", "unknown"),
        ("jurisdiction", ""),
        ("effective_from", "not-a-date"),
        ("temporal_state", "unknown"),
        ("temporal_resolution_status", "unresolved"),
    )
    for field, value in corruptions:
        corrupted = legal.model_copy(
            update={
                "metadata": {
                    **legal.metadata,
                    "legal_norm_owner_truth": {**owner_truth, field: value},
                }
            }
        )
        corrupted_index = result.capability_index.model_copy(update={"capabilities": (corrupted,)})
        assert build_capability_discovery_snapshot(corrupted_index) == (), field


@pytest.mark.parametrize(
    (
        "generated_at",
        "effective_from",
        "effective_to",
        "declared_state",
        "expected_projected",
    ),
    [
        ("2026-05-25T12:34:56.123456+03:00", "2099-01-01", None, "effective", False),
        ("2026-05-25T12:34:56.123456+03:00", "2022-02-01", "2026-05-24", "effective", False),
        ("2026-05-25T12:34:56.123456+03:00", "2022-02-01", None, "superseded", False),
        ("2026-05-25T12:34:56.123456+03:00", "2026-05-25", None, "effective", True),
        (
            "2026-05-25T12:34:56.123456+03:00",
            "2022-02-01",
            "2026-05-25",
            "effective",
            True,
        ),
    ],
)
def test_legal_norm_effectiveness_is_recomputed_at_release_snapshot(
    tmp_path: Path,
    generated_at: str,
    effective_from: str,
    effective_to: str | None,
    declared_state: str,
    expected_projected: bool,
) -> None:
    input_root = create_capability_index_fixture_inputs(tmp_path / "production_data")
    lex_path = next(input_root.glob("**/lex_knowledge_graph.duckdb"))
    with duckdb.connect(str(lex_path)) as con:
        con.execute(
            """
            UPDATE lex_normative_facts
            SET effective_from = ?, effective_to = ?, temporal_state = ?
            """,
            [effective_from, effective_to, declared_state],
        )

    result = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=input_root,
            output_dir=tmp_path / "out",
            mode="fixture",
            generated_at=generated_at,
        )
    )

    legal_rows = tuple(
        row
        for row in build_capability_discovery_snapshot(result.capability_index)
        if row.resource_kind == "legal_norm"
    )
    assert bool(legal_rows) is expected_projected
    if legal_rows:
        assert legal_rows[0].owner_truth.temporal_snapshot_at == datetime.fromisoformat(
            generated_at
        )


def test_capability_release_snapshot_requires_timezone_for_temporal_truth(tmp_path: Path) -> None:
    input_root = create_capability_index_fixture_inputs(tmp_path / "production_data")

    with pytest.raises(ValueError, match="release snapshot must be timezone-aware"):
        compile_capability_index(
            CapabilityIndexCompilerConfig(
                production_data_root=input_root,
                output_dir=tmp_path / "out",
                mode="fixture",
                generated_at="2026-05-25T12:34:56.123456",
            )
        )


def test_quarantined_legal_norm_cannot_enter_discovery_owner_snapshot(
    tmp_path: Path,
) -> None:
    input_root = create_capability_index_fixture_inputs(tmp_path / "production_data")
    lex_path = next(input_root.glob("**/lex_knowledge_graph.duckdb"))
    with duckdb.connect(str(lex_path)) as con:
        con.execute("UPDATE lex_normative_facts SET canonical_status = 'quarantined'")

    result = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=input_root,
            output_dir=tmp_path / "out",
            mode="fixture",
            generated_at="2026-05-25T00:00:00Z",
        )
    )

    assert not any(
        row.resource_kind == "legal_norm"
        for row in build_capability_discovery_snapshot(result.capability_index)
    )


def test_fixture_compiler_promotes_l1_l7_assets_into_authority_scoped_index(
    tmp_path: Path,
) -> None:
    input_root = create_capability_index_fixture_inputs(tmp_path / "production_data")
    output_dir = tmp_path / "out"

    result = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=input_root,
            output_dir=output_dir,
            mode="fixture",
            generated_at="2026-05-25T00:00:00Z",
        )
    )

    assert result.primary_duckdb_path.name == "capability_index_v1.duckdb"
    assert result.summary_path.name == "capability_index_v1.summary.json"
    assert result.conflict_report_path.exists()
    assert result.white_space_report_path.exists()
    assert json.loads(result.conflict_report_path.read_text())["conflicts"] == []

    with duckdb.connect(str(result.primary_duckdb_path), read_only=True) as con:
        assert _count(con, "capabilities") > 0
        assert _count(con, "source_assets") > 0
        assert _count(con, "capability_source_assets") > 0
        assert (
            con.execute(
                """
            SELECT count(*)
            FROM source_assets
            WHERE source_layer = 'L1'
              AND table_name = 'ds_distributions'
              AND role = 'distribution_metadata'
            """
            ).fetchone()[0]
            >= 1
        )

        firm_rows = con.execute(
            """
            SELECT capability_id, source_refs_json, method_contract_targets_json
            FROM capabilities
            WHERE construct = 'firm_fundamentals'
              AND compatibility_only = false
            ORDER BY capability_id
            """
        ).fetchall()
        assert firm_rows, "firm_fundamentals must promote into a firm-outcome capability"
        assert any("firm_fundamentals_annual" in row[1] for row in firm_rows)
        assert any("survival_hazard_estimates" in row[1] for row in firm_rows)
        assert any("foundry.ml.survival_data.v1" in row[2] for row in firm_rows)

        assert (
            con.execute(
                """
            SELECT count(*)
            FROM capabilities
            WHERE modality_json LIKE '%lex_norm%'
              AND evidence_mode = 'legal_threshold'
              AND source_refs_json LIKE '%lex_rule_thresholds%'
            """
            ).fetchone()[0]
            >= 1
        )
        assert (
            con.execute(
                """
            SELECT count(*)
            FROM capabilities
            WHERE modality_json LIKE '%scholar_claim%'
              AND source_refs_json LIKE '%ac_skg_edges%'
            """
            ).fetchone()[0]
            >= 1
        )
        assert (
            con.execute(
                """
            SELECT count(*)
            FROM capabilities
            WHERE compatibility_only = true
              AND source_refs_json LIKE '%data_contracts.json%'
            """
            ).fetchone()[0]
            >= 1
        )
        assert (
            con.execute(
                """
            SELECT count(*)
            FROM capabilities
            WHERE compatibility_only = false
              AND modality_json LIKE '%fabric_data%'
            """
            ).fetchone()[0]
            >= 1
        ), "L7 curated contracts cannot be the only data authority"

    summary = json.loads(result.summary_path.read_text())
    assert summary["primary_runtime_output"] == "capability_index_v1.duckdb"
    assert summary["exports_are_summary_only"] is True
    assert summary["performance_budget"]["status"] == "pass"
    assert summary["capability_floors"]["fabric_data"]["observed"] >= 1


def test_ukraine_panel_profiler_excludes_curated_and_simulation_parquets(
    tmp_path: Path,
) -> None:
    input_root = create_capability_index_fixture_inputs(tmp_path / "production_data")
    _write_test_parquet(
        input_root / "canonical/local_data_20260501/policy_engine_data/curated/agents.parquet",
        {"agent_id": [1], "salary": [10.0]},
    )
    _write_test_parquet(
        input_root
        / "ukraine_agent_simulation_baseline_20260410/production_bundle/bundles"
        / "runtime_bundle_v1/agent_registry_runtime.parquet",
        {"agent_id": [1], "state": ["simulated"]},
    )

    result = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=input_root,
            output_dir=tmp_path / "out",
            mode="fixture",
            generated_at="2026-05-25T00:00:00Z",
        )
    )

    with duckdb.connect(str(result.primary_duckdb_path), read_only=True) as con:
        assert (
            con.execute(
                """
            SELECT count(*)
            FROM source_assets
            WHERE source_layer = 'L4'
              AND (
                path LIKE '%policy_engine_data/curated%'
                OR path LIKE '%ukraine_agent_simulation_baseline%'
              )
            """
            ).fetchone()[0]
            == 0
        )


def test_incremental_l7_change_rebuilds_only_l7_assets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = create_capability_index_fixture_inputs(tmp_path / "production_data")
    first = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=input_root,
            output_dir=tmp_path / "first",
            mode="fixture",
            generated_at="2026-05-25T00:00:00Z",
        )
    )
    contracts_path = (
        input_root / "canonical/local_data_20260501/policy_engine_data/curated/data_contracts.json"
    )
    payload = json.loads(contracts_path.read_text())
    payload["contracts"].append(
        {
            "metric_id": "us.macro.unemployment_rate",
            "display_name": "Unemployment rate",
            "jurisdiction": "US",
        }
    )
    contracts_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    def _unexpected_loader(*_args: object, **_kwargs: object) -> tuple[object, ...]:
        raise AssertionError("unchanged heavy loader called during L7-only incremental build")

    monkeypatch.setattr(compiler, "load_dataset_catalog_capabilities", _unexpected_loader)
    monkeypatch.setattr(compiler, "load_scholar_capabilities", _unexpected_loader)
    monkeypatch.setattr(compiler, "load_lex_capabilities", _unexpected_loader)

    second = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=input_root,
            output_dir=tmp_path / "second",
            mode="incremental",
            previous_manifest_path=first.manifest_path,
            generated_at="2026-05-25T00:01:00Z",
        )
    )

    assert second.summary["incremental"]["changed_input_labels"] == ["l7_curated_contracts"]
    assert second.summary["incremental"]["rebuilt_input_labels"] == ["l7_curated_contracts"]
    assert second.summary["incremental"]["reused_previous_index"] is False
    with duckdb.connect(str(second.primary_duckdb_path), read_only=True) as con:
        assert (
            con.execute(
                """
            SELECT count(*)
            FROM capabilities
            WHERE compatibility_only = true
              AND source_refs_json LIKE '%us.macro.unemployment_rate%'
            """
            ).fetchone()[0]
            == 1
        )


def test_simulation_only_cannot_satisfy_production_authority() -> None:
    capability = EvidenceCapability(
        capability_id="capability:test_simulation_only",
        construct="firm_survival",
        modality=("simulation_state",),
        evidence_mode="simulation_only",
        concept_spine_refs=("concept:firm_survival",),
        scope=CapabilityScope(geography="UA", entity_scope="firm"),
        identification_mode="simulation_only",
        trust_tier="simulation_context",
        quality_score=QualityScore(composite=0.95, breakdown={"simulation_fit": 0.95}),
        source_assets=(),
        method_contract_targets=("foundry.ml.survival_data.v1",),
        authority_envelope=AuthorityEnvelope(
            research="advisory_context_only",
            governed_pilot="blocked_simulation_only",
            production="admissible",
            authoritative_for=("production_claim_evidence",),
            may_not_use_for=(),
        ),
        rights_envelope=RightsEnvelope(access_class="internal"),
        freshness_envelope=FreshnessEnvelope(freshness_class="synthetic"),
    )

    with pytest.raises(ValueError, match="simulation_only"):
        validate_capability_authority(capability)


def test_capability_construct_alias_preserves_artifact_schema() -> None:
    capability = EvidenceCapability(
        capability_id="capability:test_alias",
        construct="firm_survival",
        modality=("fabric_data",),
        evidence_mode="observed",
        concept_spine_refs=("concept:firm_survival",),
        scope=CapabilityScope(geography="UA", entity_scope="firm"),
        identification_mode="point_identified",
        trust_tier="authoritative_partial_coverage",
        quality_score=QualityScore(composite=0.8),
        authority_envelope=AuthorityEnvelope(
            research="admissible",
            governed_pilot="admissible",
            production="blocked_rights_boundary",
        ),
        rights_envelope=RightsEnvelope(access_class="government_administrative"),
        freshness_envelope=FreshnessEnvelope(freshness_class="fresh"),
    )
    failure = FailureModeNode(
        failure_id="failure:test_alias",
        construct="credit_program_enrollment",
        geography="UA",
        cause_class="data_source_unavailable",
        severity="blocking_production",
        owner="team-data-acquisition",
        detected_at="2026-05-25",
    )
    conflict = CapabilityConflictRecord(
        conflict_id="conflict:test_alias",
        construct="firm_survival",
        geography="UA",
        conflict_class="empirical",
        conflict_resolution_route="new_evidence",
        capability_refs=("capability:test_alias",),
    )

    assert capability.construct_id == "firm_survival"
    assert failure.construct_id == "credit_program_enrollment"
    assert conflict.construct_id == "firm_survival"
    for payload in (
        capability.model_dump(mode="json"),
        failure.model_dump(mode="json"),
        conflict.model_dump(mode="json"),
    ):
        assert "construct" in payload
        assert "construct_id" not in payload


def test_fixture_build_is_deterministic_except_manifest_generated_at(tmp_path: Path) -> None:
    input_root = create_capability_index_fixture_inputs(tmp_path / "production_data")
    first = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=input_root,
            output_dir=tmp_path / "a",
            mode="fixture",
            generated_at="2026-05-25T00:00:00Z",
        )
    )
    second = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=input_root,
            output_dir=tmp_path / "b",
            mode="fixture",
            generated_at="2026-05-25T00:01:00Z",
        )
    )

    assert first.sha256_path.read_text() == second.sha256_path.read_text()
    assert _manifest_without_generated_at(first.manifest_path) == _manifest_without_generated_at(
        second.manifest_path
    )


def test_same_construct_conflicts_are_materialized(tmp_path: Path) -> None:
    input_root = create_capability_index_fixture_inputs(tmp_path / "production_data")
    result = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=input_root,
            output_dir=tmp_path / "out",
            mode="fixture",
            inject_same_construct_conflict=True,
            generated_at="2026-05-25T00:00:00Z",
        )
    )

    conflict_report = json.loads(result.conflict_report_path.read_text())
    assert conflict_report["conflicts"]
    assert conflict_report["w8e_conflict_records"]
    assert conflict_report["w8e_conflict_records"][0]["schema_version"] == (
        "policyos.runtime.construct_conflict_record.v1"
    )


def _count(con: duckdb.DuckDBPyConnection, table: str) -> int:
    return int(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0])


def _manifest_without_generated_at(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text())
    payload.pop("generated_at", None)
    return payload


def _write_test_parquet(path: Path, payload: dict[str, list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(payload), path)
