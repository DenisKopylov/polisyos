"""Focused verified-input tests for the Ukraine D4 Scientist bridge."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from polisyos.data_forge.domains.ukraine.builders.calibration import build_d4_stage
from polisyos.data_forge.domains.ukraine.manifests import (
    ArtifactRecord,
    BuildRunManifest,
    D5ReleaseContentRef,
    D5ReleaseHandoffRequest,
    D5ReleaseProducerFacts,
    ReleaseManifest,
    SourceSnapshotManifest,
    ValidationFinding,
    write_manifest,
)
from polisyos.data_forge.domains.ukraine.models import (
    StageId,
    build_default_pipeline_config,
)
from polisyos.data_forge.read_api.ukraine import UkraineStageArtifactVerificationError
from polisyos.ir.governance.gate import GateDecision, GateVerdict
from polisyos.scientist.governance import blueprint_release
from polisyos.scientist.governance.blueprint_release import (
    _household_distribution_observation_panel,
    _load_d4_governance_request,
    _recompute_identity_resolution_coverage,
    run_verified_ukraine_d4_governance,
    run_verified_ukraine_d5_release,
)
from polisyos.scientist.governance.calibration_leaderboard import (
    CalibrationLeaderboardEntry,
    CalibrationLeaderboardMetrics,
)
from polisyos.scientist.governance.calibration_validation import (
    CalibrationValidationBundle,
    CalibrationValidationRunnerResult,
    load_calibration_validation_bundle,
    persist_calibration_validation_bundle,
)


def _write_completed_stage_manifest(
    config,
    *,
    stage_id: StageId,
    outputs: list[ArtifactRecord],
) -> None:
    write_manifest(
        config.build_root.manifests_dir / f"build_run_{stage_id.value}.json",
        BuildRunManifest(
            run_id=f"{stage_id.value}-fixture",
            stage_id=stage_id,
            status="completed",
            started_at="2026-08-26T10:00:00+00:00",
            finished_at="2026-08-26T10:01:00+00:00",
            outputs=outputs,
        ),
    )


def _verified_bridge_fixture(tmp_path):
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    d0_dir = config.build_root.runtime_dir / "d0_p0"
    d2_dir = config.build_root.calibration_dir / "d2"
    d3_dir = config.build_root.calibration_dir / "d3"
    for directory in (d0_dir, d2_dir, d3_dir):
        directory.mkdir(parents=True, exist_ok=True)

    cohort_path = d0_dir / "identity_resolution_cohort_v1.json"
    cohort_path.write_text(
        json.dumps(
            {
                "schema_version": "policyos.data_forge.ukraine.identity_resolution_cohort.v1",
                "rows": [
                    {"cohort": "spending", "raw_identity": "s1"},
                    {"cohort": "spending", "raw_identity": "s2"},
                    {"cohort": "procurement", "raw_identity": "p1"},
                    {"cohort": "procurement", "raw_identity": "p2"},
                ],
            }
        ),
        encoding="utf-8",
    )
    registry_path = d0_dir / "agent_registry_runtime.parquet"
    pd.DataFrame(
        {
            "agent_id": ["agent::s1", "agent::s2", "agent::p1", "agent::p2"],
            "registration_code": ["s1", "s2", "p1", "p2"],
            "tax_id": [None, None, None, None],
            "edrpou": [None, None, None, None],
        }
    ).to_parquet(registry_path, index=False)
    _write_completed_stage_manifest(
        config,
        stage_id=StageId.D0_P0,
        outputs=[
            ArtifactRecord.from_path(cohort_path),
            ArtifactRecord.from_path(registry_path),
        ],
    )

    periods = ["2023-01-01", "2024-01-01", "2025-01-01"]
    families = [
        "budget_flows",
        "procurement_flows",
        "macro_state",
        "trade_exposure",
        "public_service_domain_flows",
        "labor_market",
        "distress_enforcement",
    ]
    rows = [
        {
            "family": family,
            "period_start": period,
            "observed_value": 10.0 + index,
            "trust_weight": 0.99,
            "coverage_estimate": 0.99,
            "measurement_bias_flag": False,
            "source_id": f"source_{family}",
            "source_version": "v1",
            "identification_mode": "point_identified",
            "source_confidence_tier": "validated",
            "proxy_source_id": None,
            "regime_id": "regime_a",
            "entity_id": f"entity::{family}",
        }
        for family in families
        for index, period in enumerate(periods)
    ]
    observation_path = d2_dir / "observation_panel_monthly.parquet"
    from polisyos.data_forge.read_api.ukraine import (
        UKRAINE_PERIOD_PROJECTION_VERSION,
        project_ukraine_observation_periods,
    )
    from polisyos.ir import TimeFrequency

    d2_panel = pd.DataFrame(rows)
    d2_panel["period_id"] = d2_panel["period_start"].str[:7]
    d2_panel["time_grain"] = TimeFrequency.MONTH.value
    start, end, disposition, reason = project_ukraine_observation_periods(
        d2_panel["period_id"], time_grain=TimeFrequency.MONTH
    )
    d2_panel["period_start"] = start
    d2_panel["period_end"] = end
    d2_panel["period_disposition"] = disposition
    d2_panel["period_reason"] = reason
    d2_panel["period_projection_version"] = UKRAINE_PERIOD_PROJECTION_VERSION
    d2_panel.to_parquet(observation_path, index=False)
    splits_path = d2_dir / "calibration_splits.json"
    splits_path.write_text(
        json.dumps(
            {
                "train_pre_2024": {"start": "2023-01-01", "end": "2023-12-31"},
                "validation_2024": {"start": "2024-01-01", "end": "2024-12-31"},
                "test_2025": {"start": "2025-01-01", "end": "2025-12-31"},
            }
        ),
        encoding="utf-8",
    )
    _write_completed_stage_manifest(
        config,
        stage_id=StageId.D2,
        outputs=[
            ArtifactRecord.from_path(observation_path),
            ArtifactRecord.from_path(splits_path),
        ],
    )

    household_path = d3_dir / "calibrated_household_cells.parquet"
    pd.DataFrame(
        {
            "cell_id": ["cell::1", "cell::1", "cell::1"],
            "region_code": ["01", "01", "01"],
            "period_id": ["2023-01", "2024-01", "2025-01"],
            "household_income_mean": [100.0, 110.0, 120.0],
            "trust_weight": [0.99, 0.99, 0.99],
            "measurement_bias_flag": [False, False, False],
        }
    ).to_parquet(household_path, index=False)
    labor_path = d3_dir / "labor_validation_panel.parquet"
    pd.DataFrame(
        {
            "micro_employment_rate": [0.5, 0.6, 0.7, 0.8],
            "admin_employment_rate_proxy": [0.5, 0.6, 0.7, 0.8],
            "micro_sample_weight": [1.0, 1.0, 1.0, 1.0],
            "macro_labor_signal": [0.5, 0.6, 0.7, 0.8],
        }
    ).to_parquet(labor_path, index=False)
    _write_completed_stage_manifest(
        config,
        stage_id=StageId.D3,
        outputs=[
            ArtifactRecord.from_path(household_path),
            ArtifactRecord.from_path(labor_path),
        ],
    )

    d4_result = build_d4_stage(config)
    d4_manifest_path = config.build_root.manifests_dir / "build_run_d4.json"
    _write_completed_stage_manifest(
        config,
        stage_id=StageId.D4,
        outputs=list(d4_result.outputs.values()),
    )
    return config, d4_manifest_path, observation_path


def _d5_release_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    build_root = tmp_path / "ukraine"
    release_root = build_root / "bundles" / "d5"
    runtime_dir = release_root / "runtime_bundle_v1"
    method_dir = release_root / "method_contract_bundle_v1"
    runtime_dir.mkdir(parents=True)
    method_dir.mkdir(parents=True)
    runtime_agents = runtime_dir / "agent_registry_runtime.parquet"
    pd.DataFrame({"agent_id": ["a1", "a2"], "cell_id": ["c1", "c2"]}).to_parquet(
        runtime_agents, index=False
    )
    cell_registry = runtime_dir / "cell_registry_region_sector.parquet"
    pd.DataFrame(
        {
            "cell_id": ["c1", "c2"],
            "region_code": ["01", "02"],
            "sector_id": ["A", "B"],
        }
    ).to_parquet(cell_registry, index=False)
    method_contract = method_dir / "observation_to_contract_manifest.json"
    method_contract.write_text("{}\n", encoding="utf-8")
    d4_request = build_root / "calibration" / "d4" / "d4_governance_request.json"
    d4_request.parent.mkdir(parents=True)
    d4_request.write_text(
        json.dumps(
            {
                "schema_version": "policyos.data_forge.ukraine.d4_governance_request.v1",
                "authority_purpose": "producer_governance_handoff",
                "may_not_use_for": [
                    "governance_admissibility",
                    "release_acceptance",
                    "legal_intervention_compilation",
                    "method_validity",
                ],
                "required_stage_manifests": {
                    "d0_p0": "build_run_d0_p0.json",
                    "d2": "build_run_d2.json",
                    "d3": "build_run_d3.json",
                },
            }
        ),
        encoding="utf-8",
    )
    compression = release_root / "graph_compression_bundle.json"
    compression.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "method": "test_cell_coarsening",
                "layers": [
                    {
                        "layer_id": "budget",
                        "coarsening_strategy": "cell_aware_sparse_coarsening",
                        "n_original_edges": 2,
                        "n_compressed_edges": 1,
                        "n_supernodes": 2,
                        "degree_preservation_score": 1.0,
                        "edge_weight_reconstruction_error": 0.0,
                        "neighborhood_overlap_stability": 1.0,
                    }
                ],
                "fidelity_metrics": {
                    "degree_preservation_score": 1.0,
                    "edge_weight_reconstruction_error": 0.0,
                    "neighborhood_overlap_stability": 1.0,
                    "downstream_policy_response_stability": {
                        "status": "not_established",
                        "reason": "requires Scientist consumption",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    content_records = {
        "cell_registry": ArtifactRecord.from_path(cell_registry),
        "d4_governance_request": ArtifactRecord.from_path(d4_request),
        "graph_compression_bundle": ArtifactRecord.from_path(compression),
    }
    handoff = D5ReleaseHandoffRequest(
        declared_release_root=str(release_root),
        producer_facts=D5ReleaseProducerFacts(
            primary_region_id="01",
            primary_sector_id="A",
            graph_compression_degree_preservation_score=1.0,
            graph_compression_edge_weight_reconstruction_error=0.0,
        ),
        content_refs={
            name: D5ReleaseContentRef.from_artifact_record(record)
            for name, record in content_records.items()
        },
    )
    handoff_path = release_root / "d5_release_handoff_request.json"
    write_manifest(handoff_path, handoff)
    runtime_files = {
        runtime_agents.name: ArtifactRecord.from_path(runtime_agents),
        cell_registry.name: ArtifactRecord.from_path(cell_registry),
    }
    method_files = {method_contract.name: ArtifactRecord.from_path(method_contract)}
    manifest = ReleaseManifest(
        bundles={
            "runtime_bundle_v1": ArtifactRecord(
                path=str(runtime_dir),
                size_bytes=sum(record.size_bytes for record in runtime_files.values()),
            ),
            "method_contract_bundle_v1": ArtifactRecord(
                path=str(method_dir),
                size_bytes=sum(record.size_bytes for record in method_files.values()),
            ),
        },
        bundle_contents={
            "runtime_bundle_v1": runtime_files,
            "method_contract_bundle_v1": method_files,
        },
        evidence_refs={
            **content_records,
            "d5_release_handoff_request": ArtifactRecord.from_path(handoff_path),
        },
        metrics={
            "compression_degree_preservation_score": 1.0,
            "compression_edge_weight_reconstruction_error": 0.0,
            "compression_neighborhood_overlap_stability": 1.0,
        },
    )
    manifest_path = release_root / "release_manifest_v1.json"
    write_manifest(manifest_path, manifest)
    return build_root, manifest_path, runtime_dir, method_dir


def _install_admissible_d4_result(
    monkeypatch: pytest.MonkeyPatch,
    *,
    build_root: Path,
) -> None:
    d4_request = build_root / "calibration" / "d4" / "d4_governance_request.json"
    d4_manifest = build_root / "manifests" / "build_run_d4.json"
    d4_manifest.parent.mkdir(parents=True, exist_ok=True)
    config = build_default_pipeline_config(root=build_root)
    d0_dir = config.build_root.runtime_dir / "d0_p0"
    d0_dir.mkdir(parents=True, exist_ok=True)
    cohort_path = d0_dir / "identity_resolution_cohort_v1.json"
    cohort_path.write_text(
        json.dumps(
            {
                "schema_version": "policyos.data_forge.ukraine.identity_resolution_cohort.v1",
                "rows": [],
            }
        ),
        encoding="utf-8",
    )
    _write_completed_stage_manifest(
        config,
        stage_id=StageId.D0_P0,
        outputs=[ArtifactRecord.from_path(cohort_path)],
    )
    d2_dir = config.build_root.calibration_dir / "d2"
    d2_dir.mkdir(parents=True, exist_ok=True)
    splits_path = d2_dir / "calibration_splits.json"
    splits_path.write_text(
        json.dumps({"validation": {"start": "2024-01-01", "end": "2024-12-31"}}),
        encoding="utf-8",
    )
    _write_completed_stage_manifest(
        config,
        stage_id=StageId.D2,
        outputs=[ArtifactRecord.from_path(splits_path)],
    )
    write_manifest(
        d4_manifest,
        BuildRunManifest(
            run_id="d4-release-fixture",
            stage_id=StageId.D4,
            status="completed",
            started_at="2026-08-26T10:00:00+00:00",
            finished_at="2026-08-26T10:01:00+00:00",
            outputs=[ArtifactRecord.from_path(d4_request)],
        ),
    )

    def _admissible_d4(*, build_root, d4_manifest_path, cas_root):
        store = blueprint_release.FileSystemCAS(cas_root)
        d0_receipt = blueprint_release.load_verified_stage_artifacts(
            build_root / "manifests" / "build_run_d0_p0.json",
            store=store,
            allowed_root=build_root,
            expected_stage="d0_p0",
            required_outputs=("identity_resolution_cohort_v1.json",),
        )
        d2_receipt = blueprint_release.load_verified_stage_artifacts(
            build_root / "manifests" / "build_run_d2.json",
            store=store,
            allowed_root=build_root,
            expected_stage="d2",
            required_outputs=("calibration_splits.json",),
        )
        receipt = blueprint_release.load_verified_stage_artifacts(
            d4_manifest_path,
            store=store,
            allowed_root=build_root,
            expected_stage="d4",
            required_outputs=("d4_governance_request.json",),
        )
        receipt_refs = {
            "d0_p0": blueprint_release._persist_verified_stage_receipt(store, d0_receipt),
            "d2": blueprint_release._persist_verified_stage_receipt(store, d2_receipt),
            "d4": blueprint_release._persist_verified_stage_receipt(store, receipt),
        }
        candidate_ref = store.put_json(
            {"candidate_id": "d4-release-candidate"},
            blueprint_release.PutOptions(
                kind="scientist.calibration_candidate",
                media_type="application/json",
            ),
        )
        leaderboard = CalibrationLeaderboardEntry(
            entry_id="d4-release-entry",
            run_id="d4-release-run",
            candidate_ref=candidate_ref,
            metrics=CalibrationLeaderboardMetrics(
                governance_verdict="approve",
                adversarial_passed=True,
                eligible_for_promotion=True,
            ),
        )
        bundle = CalibrationValidationBundle(
            run_id="d4-release-run",
            candidate_ref=candidate_ref,
            governance_verdict="approve",
            status="completed",
            leaderboard_entry=leaderboard,
            metadata={
                "producer_receipt_refs": {
                    name: ref.model_dump(mode="json") for name, ref in receipt_refs.items()
                },
                "ukraine_json_snapshot_profile_reads": [
                    {
                        "consumer_contract": consumer_contract,
                        "profile_status": "declared_bytes_conformant",
                    }
                    for consumer_contract in (
                        "scientist.d4.governance_request",
                        "scientist.d4.identity_resolution_cohort",
                        "scientist.d4.calibration_splits",
                    )
                ],
            },
        )
        bundle_ref = persist_calibration_validation_bundle(store, bundle)
        return CalibrationValidationRunnerResult(bundle_ref=bundle_ref, bundle=bundle)

    monkeypatch.setattr(
        blueprint_release,
        "run_verified_ukraine_d4_governance",
        _admissible_d4,
    )


def _forge_d4_receipt_manifest_profile(
    monkeypatch: pytest.MonkeyPatch,
    *,
    field: str,
) -> None:
    """Republish the exact D4 receipt bytes under one counterfeit manifest field."""
    original_persist = blueprint_release._persist_verified_stage_receipt

    def _persist_with_profile_mismatch(store, receipt):
        selected_ref = original_persist(store, receipt)
        if receipt.stage_id != "d4":
            return selected_ref
        manifest = store.get_manifest(selected_ref)
        payload = store.get_bytes(selected_ref)
        schema = manifest.artifact_schema
        assert schema is not None
        mismatches = {
            "kind": {
                "kind": "scientist.other_verified_producer_receipt",
                "media_type": manifest.media_type,
                "schema": schema,
            },
            "media_type": {
                "kind": manifest.kind,
                "media_type": "application/octet-stream",
                "schema": schema,
            },
            "schema_name": {
                "kind": manifest.kind,
                "media_type": manifest.media_type,
                "schema": blueprint_release.SchemaInfo(
                    name="polisyos.data_forge.ukraine.OtherReceipt",
                    version=schema.version,
                ),
            },
            "schema_version": {
                "kind": manifest.kind,
                "media_type": manifest.media_type,
                "schema": blueprint_release.SchemaInfo(
                    name=schema.name,
                    version="v3",
                ),
            },
        }
        options = mismatches[field]
        forged_ref = store.put_bytes(
            payload,
            blueprint_release.PutOptions(
                kind=options["kind"],
                media_type=options["media_type"],
                schema=options["schema"],
                producer=manifest.producer,
                canon=manifest.canon,
            ),
            return_selected_profile=True,
        )
        assert forged_ref.artifact_id == selected_ref.artifact_id
        assert store.get_bytes(forged_ref) == payload
        # The generic model validator accepts the typed payload; only the owner
        # reader should reject these same bytes when their producer ABI differs.
        blueprint_release.validate_core_model_json_artifact(
            blueprint_release.VerifiedUkraineStageArtifacts,
            store,
            forged_ref,
            manifest_profile_sha256=forged_ref.manifest_profile_sha256,
        )
        return forged_ref

    monkeypatch.setattr(
        blueprint_release,
        "_persist_verified_stage_receipt",
        _persist_with_profile_mismatch,
    )


@pytest.mark.parametrize("profile_field", ["kind", "media_type", "schema_name", "schema_version"])
def test_d4_reopen_rejects_same_receipt_bytes_under_foreign_owner_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile_field: str,
) -> None:
    """D4 receipt admission binds the real receipt payload to the writer's ABI."""
    build_root, _, _, _ = _d5_release_fixture(tmp_path)
    _forge_d4_receipt_manifest_profile(monkeypatch, field=profile_field)
    _install_admissible_d4_result(monkeypatch, build_root=build_root)

    context = blueprint_release._run_d4_release_predicate(
        blueprint_release.FileSystemCAS(build_root / "cas"),
        build_root=build_root,
        cas_root=build_root / "cas",
    )

    assert context.status == "not_established"
    assert context.predicate_provenance == "not_established"
    assert context.reason == "d4_governance_not_established"
    assert context.stage_receipt is None


def test_d4_reopen_accepts_current_owner_profile_before_candidate_source_refs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A good D4 receipt reaches the unchanged profileless-source limitation."""
    build_root, _, _, _ = _d5_release_fixture(tmp_path)
    _install_admissible_d4_result(monkeypatch, build_root=build_root)

    context = blueprint_release._run_d4_release_predicate(
        blueprint_release.FileSystemCAS(build_root / "cas"),
        build_root=build_root,
        cas_root=build_root / "cas",
    )

    assert context.status == "not_established"
    assert context.reason == "d4_json_snapshot_profile_not_conformant"
    assert context.stage_receipt is not None
    assert context.stage_receipt_ref is not None
    assert context.stage_receipt.schema_version == ("policyos.data_forge.ukraine.verified_stage.v2")


def test_d4_receipt_owner_gate_removal_control_keeps_same_bytes_and_markers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without owner admission, the unchanged wrong-version D4 receipt is accepted."""
    from types import SimpleNamespace

    build_root, _, _, _ = _d5_release_fixture(tmp_path)
    _forge_d4_receipt_manifest_profile(monkeypatch, field="schema_version")
    _install_admissible_d4_result(monkeypatch, build_root=build_root)

    context = blueprint_release._run_d4_release_predicate(
        blueprint_release.FileSystemCAS(build_root / "cas"),
        build_root=build_root,
        cas_root=build_root / "cas",
    )
    assert context.status == "not_established"
    assert context.stage_receipt is None

    def generic_typed_read(model, store, selector, *, expected_owner, **kwargs):
        del expected_owner
        return SimpleNamespace(
            value=blueprint_release.validate_core_model_json_artifact(
                model,
                store,
                selector,
                **kwargs,
            )
        )

    with monkeypatch.context() as removed_owner_gate:
        removed_owner_gate.setattr(
            blueprint_release,
            "validate_owned_core_model_json_artifact",
            generic_typed_read,
        )
        bypassed = blueprint_release._run_d4_release_predicate(
            blueprint_release.FileSystemCAS(build_root / "cas"),
            build_root=build_root,
            cas_root=build_root / "cas",
        )
    assert bypassed.status == "not_established"
    assert bypassed.reason == "d4_json_snapshot_profile_not_conformant"
    assert bypassed.stage_receipt is not None


def _rewrite_release_compression(
    manifest_path: Path,
    *,
    layer_degree: float,
    layer_weight_error: float,
    aggregate_degree: float,
    aggregate_weight_error: float,
) -> None:
    manifest = ReleaseManifest.model_validate_json(manifest_path.read_bytes())
    compression_path = Path(manifest.evidence_refs["graph_compression_bundle"].path)
    compression = json.loads(compression_path.read_bytes())
    compression["layers"][0]["degree_preservation_score"] = layer_degree
    compression["layers"][0]["edge_weight_reconstruction_error"] = layer_weight_error
    compression["fidelity_metrics"]["degree_preservation_score"] = aggregate_degree
    compression["fidelity_metrics"]["edge_weight_reconstruction_error"] = aggregate_weight_error
    compression_path.write_text(json.dumps(compression), encoding="utf-8")
    compression_record = ArtifactRecord.from_path(compression_path)

    handoff_path = Path(manifest.evidence_refs["d5_release_handoff_request"].path)
    handoff = D5ReleaseHandoffRequest.model_validate_json(handoff_path.read_bytes())
    handoff = handoff.model_copy(
        update={
            "producer_facts": handoff.producer_facts.model_copy(
                update={
                    "graph_compression_degree_preservation_score": aggregate_degree,
                    "graph_compression_edge_weight_reconstruction_error": (aggregate_weight_error),
                }
            ),
            "content_refs": {
                **handoff.content_refs,
                "graph_compression_bundle": D5ReleaseContentRef.from_artifact_record(
                    compression_record
                ),
            },
        }
    )
    write_manifest(handoff_path, handoff)
    manifest = manifest.model_copy(
        update={
            "evidence_refs": {
                **manifest.evidence_refs,
                "graph_compression_bundle": compression_record,
                "d5_release_handoff_request": ArtifactRecord.from_path(handoff_path),
            },
            "metrics": {
                **manifest.metrics,
                "compression_degree_preservation_score": aggregate_degree,
                "compression_edge_weight_reconstruction_error": aggregate_weight_error,
            },
        }
    )
    write_manifest(manifest_path, manifest)


def test_verified_ukraine_d4_bridge_persists_all_typed_source_json_reads(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise D4 read lineage while the fixture stays non-admissible.

    The fixture has no verifier-grade household coverage, so omit only that
    final-signoff family in this test to reach the bridge. The produced C5b
    artifact must still label profileless reads candidate-only and ineligible.
    """
    config, d4_manifest_path, _ = _verified_bridge_fixture(tmp_path)
    store = blueprint_release.FileSystemCAS(config.build_root.resolved_cas_root)
    monkeypatch.setattr(
        blueprint_release,
        "REQUIRED_SIGNOFF_FAMILIES",
        tuple(
            family
            for family in blueprint_release.REQUIRED_SIGNOFF_FAMILIES
            if family.value != "household_distribution"
        ),
    )
    result = run_verified_ukraine_d4_governance(
        build_root=config.build_root.root,
        d4_manifest_path=d4_manifest_path,
        cas_root=config.build_root.resolved_cas_root,
    )
    fresh = load_calibration_validation_bundle(store, result.bundle_ref)
    manifest = store.get_manifest(result.bundle_ref)
    expected_roles = {
        "scientist.d4.governance_request": "d4_governance_request",
        "scientist.d4.identity_resolution_cohort": "identity_resolution_cohort",
        "scientist.d4.calibration_splits": "selected_split_manifest",
    }

    assert fresh.schema_version == "1.1"
    assert set(fresh.source_json_snapshot_reads) == set(expected_roles)
    assert fresh.readout_summary()["source_json_snapshot_binding_status"] == "available"
    assert fresh.readout_summary()["source_json_snapshot_profile_status"] == "candidate_only"
    assert fresh.readout_summary()["eligible_for_promotion"] is False
    for contract, role in expected_roles.items():
        provenance = fresh.source_json_snapshot_reads[contract]
        assert provenance.profile_status == "profile_absent_raw_snapshot_candidate"
        assert provenance.schema_validation_provenance == "recomputed"
        assert provenance.producer_attestation_status == "not_established"
        edges = [item for item in manifest.inputs if item.role == role]
        assert len(edges) == 1
        assert edges[0].artifact_id == provenance.artifact_ref.artifact_id
        assert edges[0].manifest_profile_sha256 == provenance.selected_manifest_profile_sha256

    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
    from polisyos.ir.analytics.backtest import (
        load_backtest_report,
        persist_backtest_report,
    )

    candidate_ref = fresh.candidate_ref
    assert candidate_ref.manifest_profile_sha256 is not None
    report_ref = fresh.backtest_report_ref
    assert report_ref is not None
    report_manifest = store.get_manifest(
        ArtifactRef.model_validate(report_ref.model_dump(mode="python"))
    )
    report_schema = report_manifest.artifact_schema
    assert report_schema is not None
    report = load_backtest_report(ensure_ir_artifact_store(store), report_ref)

    profileless_candidate_ref = candidate_ref.model_copy(update={"manifest_profile_sha256": None})
    profileless_candidate_edge = InputRef(
        artifact_id=profileless_candidate_ref.artifact_id,
        role="candidate",
        manifest_profile_sha256=None,
    )
    report_inputs = [
        profileless_candidate_edge if edge.role == "candidate" else edge
        for edge in report_manifest.inputs
    ]
    assert len([edge for edge in report_inputs if edge.role == "candidate"]) == 1
    profileless_report_ref = persist_backtest_report(
        ensure_ir_artifact_store(store),
        report,
        inputs=report_inputs,
        schema_name=report_schema.name,
        schema_version=report_schema.version,
    )
    persisted_report_candidate_edges = [
        edge
        for edge in store.get_manifest(profileless_report_ref).inputs
        if edge.role == "candidate"
    ]
    assert len(persisted_report_candidate_edges) == 1
    assert persisted_report_candidate_edges[0].manifest_profile_sha256 is None
    assert fresh.backtest_matrix is not None
    assert fresh.leaderboard_entry is not None
    profileless_bundle = fresh.model_copy(
        update={
            "run_id": "ukraine-d4-profileless-candidate-control",
            "candidate_ref": profileless_candidate_ref,
            "backtest_matrix": fresh.backtest_matrix.model_copy(
                update={"backtest_report_ref": profileless_report_ref}
            ),
            "leaderboard_entry": fresh.leaderboard_entry.model_copy(
                update={"candidate_ref": profileless_candidate_ref}
            ),
        }
    )
    bundle_inputs = [
        profileless_candidate_edge if edge.role == "candidate" else edge
        for edge in manifest.inputs
        if edge.role != "backtest_report"
    ]
    assert len([edge for edge in bundle_inputs if edge.role == "candidate"]) == 1
    profileless_bundle_ref = persist_calibration_validation_bundle(
        store, profileless_bundle, inputs=bundle_inputs
    )
    persisted_bundle_manifest = store.get_manifest(profileless_bundle_ref)
    persisted_candidate_edges = [
        edge for edge in persisted_bundle_manifest.inputs if edge.role == "candidate"
    ]
    persisted_report_candidate_edges = [
        edge
        for edge in store.get_manifest(profileless_report_ref).inputs
        if edge.role == "candidate"
    ]
    assert len(persisted_candidate_edges) == len(persisted_report_candidate_edges) == 1
    assert (
        persisted_candidate_edges[0].manifest_profile_sha256
        == persisted_report_candidate_edges[0].manifest_profile_sha256
        is None
    )

    negative = load_calibration_validation_bundle(store, profileless_bundle_ref)
    negative_summary = negative.readout_summary()
    assert negative_summary["source_json_snapshot_binding_status"] == "not_established"
    assert (
        negative_summary["source_json_snapshot_binding_reason"]
        == "candidate_source_manifest_profile_not_selected:candidate"
    )
    assert negative_summary["backtest_report_status"] == "available"
    assert negative_summary["eligible_for_promotion"] is False


def test_verified_ukraine_d4_bridge_requires_recomputable_d0_coverage_evidence(
    tmp_path,
) -> None:
    """A completed D0 manifest without row evidence cannot make D4 governance run."""

    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    result = build_d4_stage(config)
    d4_manifest_path = config.build_root.manifests_dir / "build_run_d4.json"
    write_manifest(
        d4_manifest_path,
        BuildRunManifest(
            run_id="d4-producer",
            stage_id=StageId.D4,
            status="completed",
            started_at="2026-08-26T10:00:00+00:00",
            finished_at="2026-08-26T10:01:00+00:00",
            outputs=list(result.outputs.values()),
        ),
    )
    write_manifest(
        config.build_root.manifests_dir / "build_run_d0_p0.json",
        BuildRunManifest(
            run_id="d0-without-coverage-cohort",
            stage_id=StageId.D0_P0,
            status="completed",
            started_at="2026-08-26T10:00:00+00:00",
            finished_at="2026-08-26T10:01:00+00:00",
        ),
    )

    with pytest.raises(
        UkraineStageArtifactVerificationError,
        match=(
            "required stage outputs are missing: "
            "agent_registry_runtime.parquet,identity_resolution_cohort_v1.json"
        ),
    ):
        run_verified_ukraine_d4_governance(
            build_root=config.build_root.root,
            d4_manifest_path=d4_manifest_path,
            cas_root=config.build_root.resolved_cas_root,
        )


def test_verified_ukraine_d4_bridge_blocks_household_signoff_after_immutable_admission(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Producer household rows remain bounds-only after immutable admission."""

    config, d4_manifest_path, _ = _verified_bridge_fixture(tmp_path)
    load_verified_stage_artifacts = blueprint_release.load_verified_stage_artifacts

    def _admit_then_mutate_sources(*args, **kwargs):
        receipt = load_verified_stage_artifacts(*args, **kwargs)
        for output in receipt.outputs.values():
            Path(output.source_path).write_bytes(b"mutated after immutable admission")
        return receipt

    monkeypatch.setattr(
        blueprint_release,
        "load_verified_stage_artifacts",
        _admit_then_mutate_sources,
    )

    with pytest.raises(
        ValueError,
        match=r"families_not_exact_signoff_ready:.*household_distribution",
    ):
        run_verified_ukraine_d4_governance(
            build_root=config.build_root.root,
            d4_manifest_path=d4_manifest_path,
            cas_root=config.build_root.resolved_cas_root,
        )


def test_d4_identity_coverage_is_recomputed_from_registry_bytes(tmp_path) -> None:
    """Raw producer identities cannot declare their own resolution predicate."""

    cohort = json.dumps(
        {
            "schema_version": "policyos.data_forge.ukraine.identity_resolution_cohort.v1",
            "rows": [
                {"cohort": "spending", "raw_identity": "s1"},
                {"cohort": "spending", "raw_identity": "s2"},
                {"cohort": "procurement", "raw_identity": "p1"},
                {"cohort": "procurement", "raw_identity": "p2"},
            ],
        }
    ).encode()
    registry_path = tmp_path / "agent_registry_runtime.parquet"
    pd.DataFrame(
        {
            "agent_id": ["agent::s1", "agent::p1"],
            "registration_code": ["s1", "p1"],
            "tax_id": [None, None],
            "edrpou": [None, None],
        }
    ).to_parquet(registry_path, index=False)

    spending, procurement = _recompute_identity_resolution_coverage(
        cohort,
        registry_path.read_bytes(),
    )

    assert spending == pytest.approx(0.5)
    assert procurement == pytest.approx(0.5)


def test_d4_rejects_producer_resolved_flags() -> None:
    """Even all-true producer flags cannot enter the recomputed coverage gate."""

    cohort = json.dumps(
        {
            "schema_version": "policyos.data_forge.ukraine.identity_resolution_cohort.v1",
            "rows": [
                {"cohort": "spending", "raw_identity": "s1", "resolved": True},
                {"cohort": "procurement", "raw_identity": "p1", "resolved": True},
            ],
        }
    ).encode()

    with pytest.raises(UkraineStageArtifactVerificationError, match="resolved"):
        _recompute_identity_resolution_coverage(cohort, b"not-consulted")


def test_d4_waiver_flip_is_rejected_with_constant_receipt_hash(tmp_path) -> None:
    """A stable digest cannot authorize a producer-authored signoff waiver."""

    config, d4_manifest_path, _ = _verified_bridge_fixture(tmp_path)
    store = blueprint_release.FileSystemCAS(config.build_root.resolved_cas_root)
    receipt = blueprint_release.load_verified_stage_artifacts(
        d4_manifest_path,
        store=store,
        allowed_root=config.build_root.root,
        expected_stage="d4",
        required_outputs=("d4_governance_request.json",),
    )
    admitted_output = receipt.outputs["d4_governance_request.json"]
    fixed_receipt_hash = admitted_output.sha256
    admitted_bytes = blueprint_release.load_verified_stage_output_bytes(
        store,
        receipt,
        "d4_governance_request.json",
    )
    _load_d4_governance_request(admitted_bytes)
    request = json.loads(admitted_bytes)
    request["waived_signoff_families"] = ["household_distribution"]

    with pytest.raises(UkraineStageArtifactVerificationError, match="waived_signoff_families"):
        _load_d4_governance_request(json.dumps(request).encode())

    assert receipt.outputs["d4_governance_request.json"].sha256 == fixed_receipt_hash


def test_household_projection_carries_declared_unknown_instead_of_coverage() -> None:
    """Household synthesis cannot manufacture verifier-grade exact coverage."""

    panel = _household_distribution_observation_panel(
        pd.DataFrame(
            {
                "cell_id": ["cell::1"],
                "region_code": ["01"],
                "period_id": ["2025-01"],
                "household_income_mean": [100.0],
                "trust_weight": [1.0],
                "measurement_bias_flag": [False],
            }
        )
    )

    assert panel["coverage_estimate"].tolist() == [0.0]
    assert panel["measurement_bias_flag"].tolist() == [True]
    assert panel["identification_mode"].tolist() == ["bounds_only"]
    assert panel["source_confidence_tier"].tolist() == ["exploratory"]
    assert panel["proxy_source_id"].tolist() == ["calibrated_household_cells.parquet"]
    assert blueprint_release._UKRAINE_D4_COVERAGE_THRESHOLD == 0.95


def test_verified_ukraine_d4_bridge_rejects_content_drift_before_governance(
    tmp_path,
) -> None:
    """A mutated D2 output cannot create a Scientist governance artifact."""

    config, d4_manifest_path, observation_path = _verified_bridge_fixture(tmp_path)
    pd.DataFrame({"tampered": [1]}).to_parquet(observation_path, index=False)

    with pytest.raises(UkraineStageArtifactVerificationError, match="content hash mismatch"):
        run_verified_ukraine_d4_governance(
            build_root=config.build_root.root,
            d4_manifest_path=d4_manifest_path,
            cas_root=config.build_root.resolved_cas_root,
        )


def test_verified_ukraine_d5_release_recomputes_profileless_snapshot_refusals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_root, manifest_path, runtime_dir, method_dir = _d5_release_fixture(tmp_path)
    _install_admissible_d4_result(monkeypatch, build_root=build_root)
    original_loader = blueprint_release.load_verified_release_artifacts

    def _admit_then_mutate(*args, **kwargs):
        receipt = original_loader(*args, **kwargs)
        for artifact in receipt.evidence.values():
            Path(artifact.source_path).write_bytes(b"mutated-after-admission")
        for bundle in receipt.bundle_contents.values():
            for artifact in bundle.values():
                Path(artifact.source_path).write_bytes(b"mutated-after-admission")
        return receipt

    monkeypatch.setattr(blueprint_release, "load_verified_release_artifacts", _admit_then_mutate)
    report = run_verified_ukraine_d5_release(
        build_root=build_root,
        release_manifest_path=manifest_path,
        runtime_bundle_dir=runtime_dir,
        method_contract_bundle_dir=method_dir,
        cas_root=build_root / "cas",
    )

    assert report.passed is False
    assert report.governance_verdict == "reject"
    assert report.release_admissibility_status == "blocked"
    assert report.admission_receipt_ref
    assert report.predicate_receipt_ref
    assert report.foundry_receipt_ref
    assert report.postflight_receipt_ref
    assert report.packet_ref
    store = blueprint_release.FileSystemCAS(build_root / "cas")
    postflight = json.loads(store.get_bytes(report.postflight_receipt_ref))
    assert postflight["status"] == "admissible"
    assert postflight["predicate_provenance"] == "recomputed"
    assert postflight["reasons"] == []
    predicates = json.loads(store.get_bytes(report.predicate_receipt_ref))
    assert predicates["status"] == "blocked"
    assert "release_manifest_profile_unqualified_candidate" in predicates["reasons"]
    assert predicates["manifest_no_errors_provenance"] == "recomputed"
    assert predicates["compression_predicate_provenance"] == "not_established"
    assert predicates["compression_status"] == "not_established"
    assert predicates["d4_predicate_provenance"] == "not_established"
    assert predicates["d4_status"] == "not_established"
    assert predicates["manifest_snapshot_profile_status"] == "profile_absent_raw_snapshot_candidate"
    assert (
        predicates["compression_snapshot_profile_status"] == "profile_absent_raw_snapshot_candidate"
    )
    assert predicates["handoff_snapshot_profile_status"] == "profile_absent_raw_snapshot_candidate"
    assert predicates["json_snapshot_profile_conformance_provenance"] == "not_established"
    assert set(predicates["d4_source_json_snapshot_profile_statuses"]) == {
        "scientist.d4.governance_request",
        "scientist.d4.identity_resolution_cohort",
        "scientist.d4.calibration_splits",
        "scientist.d5.d4_governance_request_evidence",
    }
    assert all(
        status == "profile_absent_raw_snapshot_candidate"
        for status in predicates["d4_source_json_snapshot_profile_statuses"].values()
    )
    packet = json.loads(store.get_bytes(report.packet_ref))
    decision_packet = blueprint_release.ReleaseDecisionPacket.model_validate(packet)
    assert packet["admission_receipt_ref"] == report.admission_receipt_ref
    assert packet["predicate_receipt_ref"] == report.predicate_receipt_ref
    assert packet["foundry_receipt_ref"] == report.foundry_receipt_ref
    assert packet["postflight_receipt_ref"] == report.postflight_receipt_ref
    assert packet["decision"] == "blocked"
    assert decision_packet.authoritative_for == ("release_admissibility",)
    assert decision_packet.may_not_use_for == (
        "publication_authorization",
        "legal_authority",
    )
    with pytest.raises(ValidationError, match="unexpected_authority"):
        blueprint_release.ReleaseDecisionPacket.model_validate(
            {**packet, "unexpected_authority": True}
        )
    with pytest.raises(ValidationError, match="frozen"):
        decision_packet.decision = "blocked"


def test_verified_ukraine_d5_release_postflight_block_prevents_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_root, manifest_path, runtime_dir, method_dir = _d5_release_fixture(tmp_path)
    _install_admissible_d4_result(monkeypatch, build_root=build_root)

    def _blocked_postflight(state, profile=None):
        return (
            {**state, "validation_trace": {"passes": []}, "validation_issues": []},
            GateDecision(
                request_id="blocked-release",
                run_id=state["run_id"],
                verdict=GateVerdict.REJECT,
                approver_id="test",
                reason_codes=["TEST_BLOCK"],
            ),
        )

    monkeypatch.setattr(blueprint_release, "postflight_checks", _blocked_postflight)
    report = run_verified_ukraine_d5_release(
        build_root=build_root,
        release_manifest_path=manifest_path,
        runtime_bundle_dir=runtime_dir,
        method_contract_bundle_dir=method_dir,
        cas_root=build_root / "cas",
    )

    assert report.passed is False
    assert report.governance_verdict == "reject"
    assert report.release_admissibility_status == "blocked"
    assert "scientist_postflight_blocked" in report.notes


def test_verified_ukraine_d5_release_none_without_trace_never_approves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_root, manifest_path, runtime_dir, method_dir = _d5_release_fixture(tmp_path)
    _install_admissible_d4_result(monkeypatch, build_root=build_root)
    monkeypatch.setattr(
        blueprint_release, "postflight_checks", lambda state, profile=None: ({}, None)
    )

    report = run_verified_ukraine_d5_release(
        build_root=build_root,
        release_manifest_path=manifest_path,
        runtime_bundle_dir=runtime_dir,
        method_contract_bundle_dir=method_dir,
        cas_root=build_root / "cas",
    )

    assert report.passed is False
    assert report.governance_verdict == "reject"
    assert report.release_admissibility_status == "blocked"
    assert "scientist_postflight_outcome_not_established" in report.notes


def test_verified_ukraine_d5_release_blocks_manifest_with_error_finding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_root, manifest_path, runtime_dir, method_dir = _d5_release_fixture(tmp_path)
    _install_admissible_d4_result(monkeypatch, build_root=build_root)
    manifest = ReleaseManifest.model_validate_json(manifest_path.read_bytes())
    write_manifest(
        manifest_path,
        manifest.model_copy(
            update={
                "validation": [
                    ValidationFinding(
                        severity="error",
                        code="compression_failed",
                        message="producer detected a compression failure",
                    )
                ]
            }
        ),
    )

    report = run_verified_ukraine_d5_release(
        build_root=build_root,
        release_manifest_path=manifest_path,
        runtime_bundle_dir=runtime_dir,
        method_contract_bundle_dir=method_dir,
        cas_root=build_root / "cas",
    )

    assert report.passed is False
    assert report.governance_verdict == "reject"
    assert report.release_admissibility_status == "blocked"
    assert "release_manifest_profile_unqualified_candidate" in report.notes
    assert "producer_manifest_contains_errors" not in report.notes
    store = blueprint_release.FileSystemCAS(build_root / "cas")
    predicates = json.loads(store.get_bytes(report.predicate_receipt_ref))
    assert predicates["status"] == "blocked"
    assert predicates["manifest_snapshot_profile_status"] == (
        "profile_absent_raw_snapshot_candidate"
    )
    assert predicates["manifest_no_errors"] is False
    assert "release_manifest_profile_unqualified_candidate" in predicates["reasons"]
    assert "producer_manifest_contains_errors" not in predicates["reasons"]


def test_verified_ukraine_d5_release_keeps_compression_unestablished_when_manifest_read_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_root, manifest_path, runtime_dir, method_dir = _d5_release_fixture(tmp_path)
    _install_admissible_d4_result(monkeypatch, build_root=build_root)

    def _unavailable_manifest(*args, **kwargs):
        raise ValueError("injected verified manifest read failure")

    monkeypatch.setattr(
        blueprint_release, "load_verified_release_manifest_json", _unavailable_manifest
    )
    report = run_verified_ukraine_d5_release(
        build_root=build_root,
        release_manifest_path=manifest_path,
        runtime_bundle_dir=runtime_dir,
        method_contract_bundle_dir=method_dir,
        cas_root=build_root / "cas",
    )

    assert report.passed is False
    assert report.release_admissibility_status == "blocked"
    predicates = json.loads(
        blueprint_release.FileSystemCAS(build_root / "cas").get_bytes(report.predicate_receipt_ref)
    )
    assert predicates["manifest_snapshot_profile_status"] == "not_established"
    assert (
        predicates["compression_snapshot_profile_status"] == "profile_absent_raw_snapshot_candidate"
    )
    assert predicates["compression_predicate_provenance"] == "not_established"
    assert predicates["compression_status"] == "not_established"
    assert "compression_predicate_not_established" in predicates["reasons"]


def test_verified_ukraine_d5_release_blocks_compression_aggregate_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_root, manifest_path, runtime_dir, method_dir = _d5_release_fixture(tmp_path)
    _install_admissible_d4_result(monkeypatch, build_root=build_root)
    _rewrite_release_compression(
        manifest_path,
        layer_degree=1.0,
        layer_weight_error=0.0,
        aggregate_degree=0.9,
        aggregate_weight_error=0.0,
    )

    report = run_verified_ukraine_d5_release(
        build_root=build_root,
        release_manifest_path=manifest_path,
        runtime_bundle_dir=runtime_dir,
        method_contract_bundle_dir=method_dir,
        cas_root=build_root / "cas",
    )

    assert report.passed is False
    assert report.release_admissibility_status == "blocked"
    assert "compression_aggregate_mismatch" in report.notes


def test_verified_ukraine_d5_release_blocks_compression_below_threshold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_root, manifest_path, runtime_dir, method_dir = _d5_release_fixture(tmp_path)
    _install_admissible_d4_result(monkeypatch, build_root=build_root)
    _rewrite_release_compression(
        manifest_path,
        layer_degree=0.84,
        layer_weight_error=0.16,
        aggregate_degree=0.84,
        aggregate_weight_error=0.16,
    )

    report = run_verified_ukraine_d5_release(
        build_root=build_root,
        release_manifest_path=manifest_path,
        runtime_bundle_dir=runtime_dir,
        method_contract_bundle_dir=method_dir,
        cas_root=build_root / "cas",
    )

    assert report.passed is False
    assert report.release_admissibility_status == "blocked"
    assert "compression_threshold_failed" in report.notes


def test_verified_ukraine_d5_release_blocks_when_d4_is_not_established(
    tmp_path: Path,
) -> None:
    build_root, manifest_path, runtime_dir, method_dir = _d5_release_fixture(tmp_path)

    report = run_verified_ukraine_d5_release(
        build_root=build_root,
        release_manifest_path=manifest_path,
        runtime_bundle_dir=runtime_dir,
        method_contract_bundle_dir=method_dir,
        cas_root=build_root / "cas",
    )

    assert report.passed is False
    assert report.release_admissibility_status == "blocked"
    assert "d4_governance_not_established" in report.notes
    store = blueprint_release.FileSystemCAS(build_root / "cas")
    predicates = json.loads(store.get_bytes(report.predicate_receipt_ref))
    assert predicates["d4_status"] == "not_established"
    assert predicates["d4_predicate_provenance"] == "not_established"
    assert (
        predicates["d4_source_json_snapshot_profile_statuses"][
            "scientist.d5.d4_governance_request_evidence"
        ]
        == "profile_absent_raw_snapshot_candidate"
    )


def test_release_receipt_cas_check_rehashes_manifest_bytes(tmp_path: Path) -> None:
    build_root, manifest_path, _runtime_dir, _method_dir = _d5_release_fixture(tmp_path)
    store = blueprint_release.FileSystemCAS(build_root / "cas")
    receipt = blueprint_release.load_verified_release_artifacts(
        manifest_path,
        store=store,
        allowed_root=build_root,
        expected_stage="d5",
    )

    class _TamperedManifestCAS:
        def get_bytes(self, artifact_id):
            payload = store.get_bytes(artifact_id)
            if artifact_id == receipt.manifest_ref:
                return bytes([payload[0] ^ 1]) + payload[1:]
            return payload

    with pytest.raises(
        UkraineStageArtifactVerificationError,
        match="manifest is not content-bound",
    ):
        blueprint_release._verify_release_receipt_cas(
            _TamperedManifestCAS(),
            receipt,
            allowed_root=build_root,
            release_manifest_path=manifest_path,
        )


def test_release_receipt_scientist_check_rejects_forged_admitted_path(
    tmp_path: Path,
) -> None:
    build_root, manifest_path, _runtime_dir, _method_dir = _d5_release_fixture(tmp_path)
    store = blueprint_release.FileSystemCAS(build_root / "cas")
    receipt = blueprint_release.load_verified_release_artifacts(
        manifest_path,
        store=store,
        allowed_root=build_root,
        expected_stage="d5",
    )
    forged_evidence = dict(receipt.evidence)
    forged_evidence["cell_registry"] = forged_evidence["cell_registry"].model_copy(
        update={"source_path": str(tmp_path.parent / "forged-cell-registry.parquet")}
    )
    forged_receipt = receipt.model_copy(update={"evidence": forged_evidence})

    with pytest.raises(
        UkraineStageArtifactVerificationError,
        match="evidence path escapes",
    ):
        blueprint_release._verify_release_receipt_cas(
            store,
            forged_receipt,
            allowed_root=build_root,
            release_manifest_path=manifest_path,
        )


def test_calibration_validation_schema_1_0_remains_readable_and_unbound(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts import CanonInfo
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.canon import CanonSpec, to_canonical_bytes

    store = blueprint_release.FileSystemCAS(tmp_path / "cas")
    candidate_ref = store.put_json(
        {"candidate": "legacy-schema-fixture"},
        PutOptions(kind="scientist.calibration_candidate", media_type="application/json"),
    )
    legacy_bundle = CalibrationValidationBundle(
        run_id="legacy-c5b-schema-1-0",
        candidate_ref=candidate_ref,
        governance_verdict="human_gate",
        status="completed",
    )
    legacy_ref = persist_calibration_validation_bundle(store, legacy_bundle)
    payload = json.loads(store.get_bytes(legacy_ref.artifact_id))
    assert payload["schema_version"] == "1.0"
    assert "source_json_snapshot_reads" not in payload
    manifest = store.get_manifest(legacy_ref)
    assert manifest.kind == "scientist.calibration_validation_bundle"
    assert manifest.media_type == "application/json"
    assert manifest.artifact_schema is not None
    assert manifest.artifact_schema.name == (
        "polisyos.scientist.governance.CalibrationValidationBundle"
    )
    assert manifest.artifact_schema.version == "1.0"
    fresh = load_calibration_validation_bundle(store, legacy_ref)
    summary = fresh.readout_summary()
    assert summary["source_json_snapshot_binding_status"] == "not_established"
    assert summary["source_json_snapshot_binding_reason"] == "source_json_snapshot_reads_absent"
    assert summary["eligible_for_promotion"] is False

    bad_manifests = (
        PutOptions(
            kind="scientist.other_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.governance.CalibrationValidationBundle",
                version="1.0",
            ),
        ),
        PutOptions(
            kind="scientist.calibration_validation_bundle",
            media_type="application/octet-stream",
            schema=SchemaInfo(
                name="polisyos.scientist.governance.CalibrationValidationBundle",
                version="1.0",
            ),
        ),
        PutOptions(
            kind="scientist.calibration_validation_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="scientist.wrong_schema", version="1.0"),
        ),
        PutOptions(
            kind="scientist.calibration_validation_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.governance.CalibrationValidationBundle",
                version="1.1",
            ),
        ),
    )
    canon_spec = CanonSpec(forbid_floats=False)
    for index, options in enumerate(bad_manifests):
        mismatched_payload = {**payload, "run_id": f"manifest-mismatch-{index}"}
        mismatched_ref = store.put_bytes(
            to_canonical_bytes(mismatched_payload, canon_spec),
            PutOptions(
                kind=options.kind,
                media_type=options.media_type,
                schema=options.schema,
                canon=CanonInfo.from_spec(canon_spec),
            ),
        )
        with pytest.raises(ValueError, match="manifest schema"):
            load_calibration_validation_bundle(store, mismatched_ref)


def _s1_controlled_candidate_fixture(
    tmp_path: Path,
    holdout_truths: list[float],
    *,
    holdout_start: str = "2026-01-01",
    holdout_end: str = "2026-12-31",
    reverse_split_order: bool = False,
):
    from polisyos.data_forge.domains.ukraine.adapters import (
        SourceExecutionContext,
        TabularSourceAdapter,
    )
    from polisyos.data_forge.domains.ukraine.builders.demography import build_d3_stage

    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    raw_root = tmp_path / "manual_drop"
    workbook_dir = raw_root / "mic_doch_i_umovy_2023_2025"
    workbook_dir.mkdir(parents=True)
    values = [100.0] * 4 + [300.0] * 4 + [500.0] * 4 + [700.0] * 4 + [900.0] * 4 + holdout_truths
    periods = [
        (year, quarter) for year in (2021, 2022, 2023, 2024, 2025, 2026) for quarter in range(1, 5)
    ]
    source_rows = [
        {
            "rik_fa_1": year,
            "kvart_kd": quarter,
            "code_fam": index + 1,
            "w_q": 1.0,
            "cod_obl": "05",
            "cashinc": value,
            "totalinc": value,
            "totalexp": value * 0.8,
        }
        for index, ((year, quarter), value) in enumerate(
            zip(periods[: len(values)], values, strict=True)
        )
    ]
    raw_workbook = workbook_dir / "Households_microdani_anonimni_controlled.xlsx"
    pd.DataFrame(source_rows).to_excel(raw_workbook, index=False)
    source = config.sources["household_microdata"].model_copy(update={"local_path": raw_root})
    config.sources["household_microdata"] = source
    adapter = TabularSourceAdapter()
    snapshot = adapter.fetch(source, SourceExecutionContext(config.build_root))
    assert isinstance(snapshot, SourceSnapshotManifest)
    adapter.normalize(source, snapshot, SourceExecutionContext(config.build_root))
    normalized = config.build_root.normalized_dir
    other_sources = (
        (
            "labor_force_microdata",
            pd.DataFrame(
                {
                    "household_id": ["lfs::1"],
                    "cell_id": ["cell::05::labor_market"],
                    "period_id": ["2023-03"],
                    "participation_rate": [0.5],
                    "weight": [1.0],
                    "employment_flag": [0.5],
                    "informal_employment_flag": [0.1],
                    "region_code": ["05"],
                }
            ),
        ),
        (
            "pfu_debt",
            pd.DataFrame({"agent_id": ["a"], "period_id": ["2023-03"], "debt_amount": [1.0]}),
        ),
        (
            "wage_arrears",
            pd.DataFrame({"agent_id": ["a"], "period_id": ["2023-03"], "arrears_amount": [1.0]}),
        ),
        (
            "distress_events",
            pd.DataFrame(
                {
                    "agent_id": ["a"],
                    "period_id": ["2023-03"],
                    "months_to_event": [1],
                    "event_flag": [0],
                }
            ),
        ),
    )
    for source_id, frame in other_sources:
        source_dir = normalized / source_id
        source_dir.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(source_dir / config.sources[source_id].normalized_artifact, index=False)
    d3_result = build_d3_stage(config)
    _write_completed_stage_manifest(
        config, stage_id=StageId.D3, outputs=list(d3_result.outputs.values())
    )
    d2_dir = config.build_root.calibration_dir / "d2"
    d2_dir.mkdir(parents=True, exist_ok=True)
    splits = {
        "fixture_training": {"start": "2021-01-01", "end": "2021-12-31"},
        "train_pre_2024": {"start": "2022-01-01", "end": "2022-12-31"},
        "fixture_validation": {"start": "2023-01-01", "end": "2023-12-31"},
        "validation_2024": {"start": "2024-01-01", "end": "2024-12-31"},
        "test_2025": {"start": "2025-01-01", "end": "2025-12-31"},
        "fixture_holdout": {"start": holdout_start, "end": holdout_end},
    }
    if reverse_split_order:
        splits = dict(reversed(list(splits.items())))
    split_path = d2_dir / "calibration_splits.json"
    split_path.write_text(json.dumps(splits), encoding="utf-8")
    _write_completed_stage_manifest(
        config, stage_id=StageId.D2, outputs=[ArtifactRecord.from_path(split_path)]
    )
    copied_workbook = Path(snapshot.raw_artifacts[0].path) / workbook_dir.name / raw_workbook.name
    return config, copied_workbook


@pytest.mark.parametrize(
    ("time_index", "intervention_date"),
    [
        ([], "2020-01-01"),
        (["not-a-date"], "not-a-date"),
        (["2020-01-01", "2021-01-01", "2021-01-01"], "2021-01-01"),
        (["2020-01-01", "2022-01-01", "2021-01-01"], "2021-01-01"),
        (["2020-01-01", "2021-01-01"], "2022-01-01"),
    ],
)
def test_backtest_intervention_step_refuses_ambiguous_time_axes(
    time_index: list[str], intervention_date: str
) -> None:
    """A cutoff needs a complete, parseable, unique, ordered date axis."""

    assert (
        blueprint_release._resolve_backtest_intervention_step(time_index, intervention_date) is None
    )


def test_required_backtest_bundle_masks_from_full_sorted_time_axis(
    tmp_path: Path,
) -> None:
    """The persisted intervention cutoff is the date's index in the full history."""
    from polisyos.ir.observation.contracts import ObservationFamily
    from polisyos.scientist.methods.backtesting.masking import (
        MaskingValidationError,
        OutcomeMasker,
    )
    from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan

    time_index = [f"{year}-01-01" for year in range(2020, 2026)]
    panel = pd.DataFrame(
        {
            "family": [ObservationFamily.MACRO_STATE.value] * len(time_index),
            "period_start": list(reversed(time_index)),
            "observed_value": list(reversed(range(len(time_index)))),
        }
    )
    bundle = blueprint_release.build_required_backtest_bundles(
        panel,
        stage_dir=tmp_path,
        splits={
            "training": {"start": "2020-01-01", "end": "2020-12-31"},
            "validation": {"start": "2022-01-01", "end": "2022-12-31"},
            "holdout": {"start": "2025-01-01", "end": "2025-12-31"},
        },
        selected_training_role="training",
        selected_validation_role="validation",
        selected_holdout_role="holdout",
    )[blueprint_release.BacktestKind.MACRO]

    assert bundle.gap_reason is None
    assert len(bundle.plans) == 1
    plan_payload = bundle.plans[0]
    historical_path = Path(plan_payload["historical_data_path"])
    historical_data = json.loads(historical_path.read_text(encoding="utf-8"))
    assert historical_data["period_start"] == time_index
    assert historical_data["time_index"] == time_index
    assert plan_payload["intervention_date"] == "2025-01-01"
    assert plan_payload["intervention_step"] == time_index.index("2025-01-01")

    plan = HistoricalValidationPlan.model_validate(plan_payload)
    masked = OutcomeMasker().mask(historical_data, plan)
    assert masked["observed_value"] == [0.0, 1.0, 2.0, 3.0, 4.0]
    assert masked["time_index"] == time_index[:5]
    assert masked["_backtest_metadata"]["intervention_step"] == 5
    without_axis = {key: value for key, value in historical_data.items() if key != "time_index"}
    with pytest.raises(MaskingValidationError) as exc_info:
        OutcomeMasker().mask(without_axis, plan)
    assert exc_info.value.code == "intervention_date_unresolved"


@pytest.mark.parametrize(
    "period_start",
    [
        ["2020-01-01", "not-a-date", "2022-01-01", "2025-01-01"],
        [
            "2020-01-01 00:00:00",
            "2021-01-01 00:00:00",
            "2021-01-01 12:00:00",
            "2022-01-01 00:00:00",
            "2025-01-01 00:00:00",
        ],
    ],
)
def test_required_backtest_bundle_gaps_when_time_axis_is_ambiguous(
    tmp_path: Path, period_start: list[str]
) -> None:
    """Missing or duplicate civil dates cannot produce a guessed intervention index."""
    from polisyos.ir.observation.contracts import ObservationFamily

    panel = pd.DataFrame(
        {
            "family": [ObservationFamily.MACRO_STATE.value] * len(period_start),
            "period_start": period_start,
            "observed_value": list(range(len(period_start))),
        }
    )
    bundle = blueprint_release.build_required_backtest_bundles(
        panel,
        stage_dir=tmp_path,
        splits={
            "training": {"start": "2020-01-01", "end": "2020-12-31"},
            "validation": {"start": "2022-01-01", "end": "2022-12-31"},
            "holdout": {"start": "2025-01-01", "end": "2025-12-31"},
        },
        selected_training_role="training",
        selected_validation_role="validation",
        selected_holdout_role="holdout",
    )[blueprint_release.BacktestKind.MACRO]

    assert bundle.plans == []
    assert bundle.gap_reason == "intervention_time_axis_unresolved:macro"


@pytest.mark.parametrize(
    ("holdout_truths", "expected_status", "expected_mean_residual"),
    [
        ([90.0, 90.0, 90.0], "not_computable", 10.0),
        ([99.5, 98.5, 97.5], "available", 1.5),
    ],
)
def test_s1_b172_b173_test_owned_d4_diagnostic_backtest_cas_fresh_read(
    tmp_path: Path,
    holdout_truths: list[float],
    expected_status: str,
    expected_mean_residual: float,
) -> None:
    from polisyos.ir.analytics.backtest import load_backtest_report
    from polisyos.scientist.governance.calibration_validation import (
        load_calibration_validation_bundle,
    )

    if expected_status == "available":
        pytest.importorskip("scipy.stats")
    config, raw_workbook = _s1_controlled_candidate_fixture(tmp_path, holdout_truths)
    result = blueprint_release.run_verified_ukraine_d4_candidate_diagnostic(
        build_root=config.build_root.root,
        d2_manifest_path=config.build_root.manifests_dir / "build_run_d2.json",
        d3_manifest_path=config.build_root.manifests_dir / "build_run_d3.json",
        cas_root=config.build_root.resolved_cas_root,
        test_owned_unit_label="fixture_unit",
        selected_training_role="fixture_training",
        selected_validation_role="fixture_validation",
        selected_holdout_role="fixture_holdout",
    )
    assert result.bundle.status == result.bundle.purpose == "candidate_diagnostic"
    assert result.bundle.leaderboard_entry is None and result.bundle.stress_scenarios is None
    assert result.bundle.governance_accountability_ref is None
    store = blueprint_release.FileSystemCAS(config.build_root.resolved_cas_root)
    fresh = load_calibration_validation_bundle(store, result.bundle_ref)
    summary = fresh.readout_summary()
    assert fresh.schema_version == "1.1"
    bundle_manifest = store.get_manifest(result.bundle_ref)
    assert bundle_manifest.kind == "scientist.calibration_validation_bundle"
    assert bundle_manifest.media_type == "application/json"
    assert bundle_manifest.artifact_schema is not None
    assert bundle_manifest.artifact_schema.name == (
        "polisyos.scientist.governance.CalibrationValidationBundle"
    )
    assert bundle_manifest.artifact_schema.version == fresh.schema_version
    expected_source_contracts = {
        "scientist.d3.household_candidate_basis",
        "scientist.d4.calibration_splits",
    }
    assert set(fresh.source_json_snapshot_reads) == expected_source_contracts
    expected_source_roles = {
        "scientist.d3.household_candidate_basis": "household_source_basis",
        "scientist.d4.calibration_splits": "selected_split_manifest",
    }
    for contract, role in expected_source_roles.items():
        provenance = fresh.source_json_snapshot_reads[contract]
        edges = [item for item in bundle_manifest.inputs if item.role == role]
        assert len(edges) == 1
        assert edges[0].artifact_id == provenance.artifact_ref.artifact_id
        assert edges[0].manifest_profile_sha256 == provenance.selected_manifest_profile_sha256
    legacy_schema_payload = fresh.model_dump(mode="json")
    legacy_schema_payload["schema_version"] = "1.0"
    with pytest.raises(
        ValidationError,
        match="source JSON snapshot provenance requires bundle schema 1.1",
    ):
        CalibrationValidationBundle.model_validate(legacy_schema_payload)
    assert summary["source_json_snapshot_binding_status"] == "available", summary[
        "source_json_snapshot_binding_reason"
    ]
    assert set(summary["source_json_snapshot_reads"]) == expected_source_contracts
    for source_read in fresh.source_json_snapshot_reads.values():
        assert source_read.profile_status == "profile_absent_raw_snapshot_candidate"
        assert source_read.producer_attestation_status == "not_established"
        assert source_read.currentness_provenance == "not_established"
        assert source_read.authority_provenance == "not_established"
    assert summary["eligible_for_promotion"] is False
    assert summary["backtest_report_ref"] and summary["backtest_metric_diagnostics"]
    if expected_status == "available":
        fresh_diagnostic = next(
            item
            for item in summary["backtest_metric_diagnostics"]
            if item["metric_name"] == "observed_value"
        )
        assert fresh_diagnostic["method_id"] == "scipy.stats.ttest_1samp"
        assert fresh_diagnostic["backend_id"] == "scipy" and fresh_diagnostic["backend_version"]
        assert fresh_diagnostic["p_value"] == pytest.approx(0.121690, abs=1e-6)
    report = load_backtest_report(
        blueprint_release._ensure_ir_artifact_store(store), fresh.backtest_report_ref
    )
    diagnostic = next(
        item for item in report.metric_diagnostics if item.metric_name == "observed_value"
    )
    assert diagnostic.status == expected_status and diagnostic.scope["holdout_windows"]
    assert diagnostic.scope["selected_training_roles"] == ["fixture_training"]
    assert diagnostic.scope["selected_validation_roles"] == ["fixture_validation"]
    assert diagnostic.scope["selected_holdout_roles"] == ["fixture_holdout"]
    assert diagnostic.mean_residual == pytest.approx(expected_mean_residual)
    assert diagnostic.magnitude == pytest.approx(abs(expected_mean_residual))
    assert (
        diagnostic.residual_sign == "positive" and diagnostic.direction_status == "not_established"
    )
    assert result.bundle.selected_training_role == "fixture_training"
    assert result.bundle.selected_validation_role == "fixture_validation"
    assert result.bundle.selected_holdout_role == "fixture_holdout"
    candidate_payload = json.loads(store.get_bytes(result.bundle.candidate_ref.artifact_id))
    from io import BytesIO

    panel_edge = next(
        item
        for item in store.get_manifest(result.bundle_ref.artifact_id).inputs
        if item.role == "household_candidate_panel"
    )
    candidate_panel = pd.read_parquet(BytesIO(store.get_bytes(panel_edge.artifact_id)))
    assert candidate_panel["unit"].isna().all()
    assert candidate_panel["population_coverage"].isna().all()
    assert candidate_panel["custody"].eq("not_established").all()
    assert candidate_panel["currentness"].eq("not_established").all()
    assert candidate_payload["metadata"]["selected_training_role"] == "fixture_training"
    assert candidate_payload["metadata"]["selected_validation_role"] == "fixture_validation"
    assert candidate_payload["metadata"]["selected_holdout_role"] == "fixture_holdout"
    assert report.trust_eligible is False and report.degraded is True
    required_roles = {
        "candidate",
        "household_candidate_panel",
        "household_source_basis",
        "selected_split_manifest",
    }
    assert required_roles <= {
        item.role for item in store.get_manifest(result.bundle_ref.artifact_id).inputs
    }
    assert required_roles <= {
        item.role for item in store.get_manifest(fresh.backtest_report_ref.artifact_id).inputs
    }
    raw_directory = raw_workbook.parent
    before = {
        p.relative_to(raw_directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in raw_directory.rglob("*")
        if p.is_file()
    }
    declared = [
        config.build_root.manifests_dir / "build_run_d2.json",
        config.build_root.manifests_dir / "build_run_d3.json",
        config.build_root.manifests_dir / "household_microdata" / "source_snapshot_manifest.json",
        config.build_root.manifests_dir
        / "household_microdata"
        / config.sources["household_microdata"].manifest_name,
    ]
    declared_bytes = {p: p.read_bytes() for p in declared}
    raw_workbook.write_bytes(raw_workbook.read_bytes() + b"\x00")
    after = {
        p.relative_to(raw_directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in raw_directory.rglob("*")
        if p.is_file()
    }
    rel = raw_workbook.relative_to(raw_directory).as_posix()
    assert before.keys() == after.keys() and before[rel] != after[rel]
    assert {p: p.read_bytes() for p in declared} == declared_bytes
    with pytest.raises(UkraineStageArtifactVerificationError, match="raw directory"):
        blueprint_release.run_verified_ukraine_d4_candidate_diagnostic(
            build_root=config.build_root.root,
            d2_manifest_path=config.build_root.manifests_dir / "build_run_d2.json",
            d3_manifest_path=config.build_root.manifests_dir / "build_run_d3.json",
            cas_root=config.build_root.resolved_cas_root,
            test_owned_unit_label="fixture_unit",
            selected_training_role="fixture_training",
            selected_validation_role="fixture_validation",
            selected_holdout_role="fixture_holdout",
        )


@pytest.mark.parametrize(
    ("stage_id", "output_name"),
    [
        ("d2", "calibration_splits.json"),
        ("d3", "household_candidate_basis.json"),
    ],
)
@pytest.mark.parametrize(
    ("profile_kind", "expected_code"),
    [
        ("declared_nonconformant", "canon_profile_payload_nonconformant"),
        ("declared_unknown", "ukraine_snapshot_unknown_profile_raw_only"),
    ],
)
def test_s1_candidate_diagnostic_refuses_present_nonconformant_or_unknown_json_profiles(
    tmp_path: Path,
    monkeypatch,
    stage_id: str,
    output_name: str,
    profile_kind: str,
    expected_code: str,
) -> None:
    from polisyos.core.artifacts.manifest import CanonInfo as CoreCanonInfo
    from polisyos.data_forge.read_api.ukraine import UkraineJSONSnapshotRefusalError

    config, _ = _s1_controlled_candidate_fixture(tmp_path, [90.0, 90.0, 90.0])
    original_load = blueprint_release.load_verified_stage_artifacts

    def load_with_present_profile(
        manifest_path,
        *,
        store,
        allowed_root,
        expected_stage,
        required_outputs=(),
    ):
        receipt = original_load(
            manifest_path,
            store=store,
            allowed_root=allowed_root,
            expected_stage=expected_stage,
            required_outputs=required_outputs,
        )
        if expected_stage != stage_id:
            return receipt
        output = receipt.outputs[output_name]
        payload = store.get_bytes(output.content_ref)
        canon = (
            CoreCanonInfo()
            if profile_kind == "declared_nonconformant"
            else CoreCanonInfo(name="polisyos.canon.future", version="9.9.9")
        )
        declared_ref = store.put_bytes(
            payload,
            blueprint_release.PutOptions(
                kind=output.content_ref.kind,
                media_type=output.content_ref.media_type,
                canon=canon,
            ),
            return_selected_profile=True,
        )
        outputs = dict(receipt.outputs)
        outputs[output_name] = output.model_copy(update={"content_ref": declared_ref})
        return receipt.model_copy(update={"outputs": outputs})

    monkeypatch.setattr(
        blueprint_release, "load_verified_stage_artifacts", load_with_present_profile
    )
    with pytest.raises(UkraineJSONSnapshotRefusalError) as refusal:
        blueprint_release.run_verified_ukraine_d4_candidate_diagnostic(
            build_root=config.build_root.root,
            d2_manifest_path=config.build_root.manifests_dir / "build_run_d2.json",
            d3_manifest_path=config.build_root.manifests_dir / "build_run_d3.json",
            cas_root=config.build_root.resolved_cas_root,
            test_owned_unit_label="fixture_unit",
            selected_training_role="fixture_training",
            selected_validation_role="fixture_validation",
            selected_holdout_role="fixture_holdout",
        )
    assert refusal.value.code == expected_code


def test_s1_empty_named_holdout_is_typed_gap_without_tail(tmp_path: Path) -> None:
    config, _ = _s1_controlled_candidate_fixture(
        tmp_path,
        [90.0, 90.0, 90.0],
        holdout_start="2027-01-01",
        holdout_end="2027-12-31",
        reverse_split_order=True,
    )
    result = blueprint_release.run_verified_ukraine_d4_candidate_diagnostic(
        build_root=config.build_root.root,
        d2_manifest_path=config.build_root.manifests_dir / "build_run_d2.json",
        d3_manifest_path=config.build_root.manifests_dir / "build_run_d3.json",
        cas_root=config.build_root.resolved_cas_root,
        test_owned_unit_label="fixture_unit",
        selected_training_role="fixture_training",
        selected_validation_role="fixture_validation",
        selected_holdout_role="fixture_holdout",
    )
    household = next(
        item
        for item in result.bundle.backtest_matrix.kind_results
        if item.kind.value == "household"
    )
    assert household.status == "gap"
    assert household.gap_flag == "empty_named_holdout:fixture_holdout"
    assert household.metadata["selected_training_role"] == "fixture_training"
    assert household.metadata["selected_validation_role"] == "fixture_validation"
    assert household.metadata["selected_holdout_role"] == "fixture_holdout"
    assert household.metadata["gap_reason"] == "empty_named_holdout:fixture_holdout"
    assert household.n_plans == 0
    assert result.bundle.backtest_matrix.backtest_report_ref is not None


@pytest.mark.parametrize(
    ("case", "frame_rows", "expected_household_state"),
    [
        ("empty", [], "no_source_rows"),
        (
            "short",
            [
                ("2023-03-31", 10.0),
                ("2025-03-31", 12.0),
            ],
            "insufficient_history",
        ),
        (
            "full",
            [
                ("2023-03-31", 10.0),
                ("2024-03-31", 11.0),
                ("2025-03-31", 12.0),
            ],
            "plans",
        ),
    ],
)
def test_s1_named_split_bundle_denominator_covers_empty_short_and_full(
    tmp_path: Path,
    case: str,
    frame_rows: list[tuple[str, float]],
    expected_household_state: str,
) -> None:
    from polisyos.scientist.governance.backtest_matrix import BacktestKind

    roles = ("fixture_training", "fixture_validation", "fixture_holdout")
    splits = {
        roles[0]: {"start": "2023-01-01", "end": "2023-12-31"},
        roles[1]: {"start": "2024-01-01", "end": "2024-12-31"},
        roles[2]: {"start": "2025-01-01", "end": "2025-12-31"},
    }
    panel = pd.DataFrame(
        [
            {
                "family": "household_distribution",
                "period_start": period,
                "observed_value": value,
            }
            for period, value in frame_rows
        ],
        columns=["family", "period_start", "observed_value"],
    )
    bundles = blueprint_release.build_required_backtest_bundles(
        panel,
        stage_dir=tmp_path / case,
        splits=splits,
        selected_training_role=roles[0],
        selected_validation_role=roles[1],
        selected_holdout_role=roles[2],
    )
    assert set(bundles) == set(BacktestKind)
    for kind, bundle in bundles.items():
        assert (
            bundle.selected_training_role,
            bundle.selected_validation_role,
            bundle.selected_holdout_role,
        ) == roles
        if kind is BacktestKind.HOUSEHOLD and expected_household_state == "plans":
            assert bundle.plans and bundle.gap_reason is None
        elif kind is BacktestKind.HOUSEHOLD:
            assert not bundle.plans and bundle.gap_reason.startswith(expected_household_state)
        else:
            assert not bundle.plans and bundle.gap_reason.startswith("no_source_rows")


def test_household_consumer_checks_projection_against_source_and_labels_legacy() -> None:
    """The real D4 consumer recomputes period facts instead of trusting labels."""
    from polisyos.data_forge.domains.ukraine.builders.demography import (
        _build_calibrated_household_cells,
    )

    raw = pd.DataFrame(
        {
            "cell_id": ["valid", "missing", "invalid"],
            "region_code": ["01", "01", "01"],
            "period_id": ["2024-02", None, "2024-13"],
            "income": [10.0, 20.0, 30.0],
            "weight": [1.0, 1.0, 1.0],
        }
    )
    cells = _build_calibrated_household_cells(raw)
    panel = _household_distribution_observation_panel(cells).set_index("entity_id")
    assert panel.loc["valid", "period_start"] == "2024-02-01"
    assert panel.loc["valid", "period_end"] == "2024-02-29"
    assert panel.loc["missing", "period_reason"] == "period_identifier_missing"
    assert panel.loc["invalid", "period_reason"] == "period_identifier_invalid"
    assert pd.isna(panel.loc["missing", "period_start"])
    assert pd.isna(panel.loc["invalid", "period_start"])
    assert pd.isna(panel.loc["missing", "regime_id"])
    assert pd.isna(panel.loc["invalid", "regime_id"])
    assert panel.loc["valid", "regime_provenance"] == "legacy_unverified"
    assert panel.loc["missing", "regime_provenance"] == "period_unresolved"
    assert set(panel["period_projection_provenance"]) == {"recomputed_from_period_id"}

    forged = cells.copy()
    forged.loc[forged["cell_id"] == "invalid", "period_disposition"] = "missing"
    with pytest.raises(UkraineStageArtifactVerificationError, match="period_projection_mismatch"):
        _household_distribution_observation_panel(forged)
    with pytest.raises(UkraineStageArtifactVerificationError, match="period_projection_incomplete"):
        _household_distribution_observation_panel(cells.drop(columns=["period_reason"]))

    legacy = cells.drop(
        columns=[
            "period_start",
            "period_end",
            "period_disposition",
            "period_reason",
            "period_projection_version",
        ]
    )
    legacy_panel = _household_distribution_observation_panel(legacy).set_index("entity_id")
    assert legacy_panel.loc["invalid", "period_reason"] == "period_identifier_invalid"
    assert legacy_panel.loc["missing", "period_reason"] == "period_identifier_missing"
    assert set(legacy_panel["period_projection_provenance"]) == {"recomputed_from_period_id"}
    assert "period_projection_version" not in legacy.columns
    legacy["period_source_projection_version"] = "ukraine_observation_period_v1"
    adversarial_panel = _household_distribution_observation_panel(legacy)
    rechecked = blueprint_release._reconcile_ukraine_period_projection(adversarial_panel)
    assert "period_source_projection_version" not in adversarial_panel.columns
    assert "period_source_projection_version" not in rechecked.columns
    assert set(rechecked["period_projection_provenance"]) == {"recomputed_from_period_id"}


def test_legacy_d2_period_projection_is_limited_not_assumed_valid() -> None:
    """An old panel without source period IDs cannot gain a new valid status."""
    panel = pd.DataFrame(
        {
            "family": ["macro_state"],
            "period_start": ["2024-02-01"],
            "observed_value": [1.0],
            "coverage_estimate": [1.0],
            "measurement_bias_flag": [False],
            "source_id": ["legacy"],
            "identification_mode": ["point_identified"],
            "source_confidence_tier": ["validated"],
        }
    )
    reconciled = blueprint_release._reconcile_ukraine_period_projection(panel)
    assert reconciled.loc[0, "period_disposition"] == "not_established"
    assert reconciled.loc[0, "period_reason"] == "period_projection_not_established"
    assert reconciled.loc[0, "period_projection_provenance"] == "legacy_unavailable"
    assert reconciled.loc[0, "period_start"] == "2024-02-01"
    registry = blueprint_release.build_family_eligibility_registry(
        reconciled, coverage_threshold=0.95
    )
    entry = registry.families["macro_state"]
    assert entry.exact_signoff_eligible is False
    assert "period_projection_not_established" in entry.reasons


def test_two_d2_reconciliations_do_not_promote_a_forged_source_projection_version() -> None:
    """A column supplied by a legacy source cannot attest an original artifact schema."""
    legacy = pd.DataFrame(
        {
            "period_id": ["2024-02"],
            "time_grain": ["M"],
            "source_version": ["original-source-v0"],
            "period_source_projection_version": ["ukraine_observation_period_v1"],
        }
    )
    first = blueprint_release._reconcile_ukraine_period_projection(legacy)
    second = blueprint_release._reconcile_ukraine_period_projection(first)
    assert "period_source_projection_version" not in first.columns
    assert "period_source_projection_version" not in second.columns
    assert first.loc[0, "period_projection_provenance"] == "recomputed_from_period_id"
    assert second.loc[0, "period_projection_provenance"] == "recomputed_from_period_id"
    assert second.loc[0, "period_end"] == "2024-02-29"
    assert second.loc[0, "source_version"] == "original-source-v0"
    assert "period_disposition" not in legacy.columns
