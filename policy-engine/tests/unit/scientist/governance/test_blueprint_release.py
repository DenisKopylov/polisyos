"""Focused verified-input tests for the Ukraine D4 Scientist bridge."""

from __future__ import annotations

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
    ValidationFinding,
    write_manifest,
)
from polisyos.data_forge.domains.ukraine.models import StageId, build_default_pipeline_config
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
        outputs=[ArtifactRecord.from_path(cohort_path), ArtifactRecord.from_path(registry_path)],
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
    pd.DataFrame(rows).to_parquet(observation_path, index=False)
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
        outputs=[ArtifactRecord.from_path(observation_path), ArtifactRecord.from_path(splits_path)],
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
        outputs=[ArtifactRecord.from_path(household_path), ArtifactRecord.from_path(labor_path)],
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
    pd.DataFrame(
        {"agent_id": ["a1", "a2"], "cell_id": ["c1", "c2"]}
    ).to_parquet(runtime_agents, index=False)
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
    d4_request.write_text('{"candidate": true}\n', encoding="utf-8")
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
                }
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
        receipt = blueprint_release.load_verified_stage_artifacts(
            d4_manifest_path,
            store=store,
            allowed_root=build_root,
            expected_stage="d4",
            required_outputs=("d4_governance_request.json",),
        )
        receipt_ref = blueprint_release._persist_verified_stage_receipt(store, receipt)
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
                "producer_receipt_refs": {"d4": str(receipt_ref.artifact_id)},
            },
        )
        bundle_ref = persist_calibration_validation_bundle(store, bundle)
        return CalibrationValidationRunnerResult(bundle_ref=bundle_ref, bundle=bundle)

    monkeypatch.setattr(
        blueprint_release,
        "run_verified_ukraine_d4_governance",
        _admissible_d4,
    )


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
    compression["fidelity_metrics"][
        "edge_weight_reconstruction_error"
    ] = aggregate_weight_error
    compression_path.write_text(json.dumps(compression), encoding="utf-8")
    compression_record = ArtifactRecord.from_path(compression_path)

    handoff_path = Path(manifest.evidence_refs["d5_release_handoff_request"].path)
    handoff = D5ReleaseHandoffRequest.model_validate_json(handoff_path.read_bytes())
    handoff = handoff.model_copy(
        update={
            "producer_facts": handoff.producer_facts.model_copy(
                update={
                    "graph_compression_degree_preservation_score": aggregate_degree,
                    "graph_compression_edge_weight_reconstruction_error": (
                        aggregate_weight_error
                    ),
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


def test_verified_ukraine_d4_bridge_requires_recomputable_d0_coverage_evidence(tmp_path) -> None:
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


def test_verified_ukraine_d4_bridge_rejects_content_drift_before_governance(tmp_path) -> None:
    """A mutated D2 output cannot create a Scientist governance artifact."""

    config, d4_manifest_path, observation_path = _verified_bridge_fixture(tmp_path)
    pd.DataFrame({"tampered": [1]}).to_parquet(observation_path, index=False)

    with pytest.raises(UkraineStageArtifactVerificationError, match="content hash mismatch"):
        run_verified_ukraine_d4_governance(
            build_root=config.build_root.root,
            d4_manifest_path=d4_manifest_path,
            cas_root=config.build_root.resolved_cas_root,
        )


def test_verified_ukraine_d5_release_consumes_cas_and_emits_scientist_decision(
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

    assert report.passed is True
    assert report.governance_verdict == "approve"
    assert report.release_admissibility_status == "admissible"
    assert report.admission_receipt_ref
    assert report.predicate_receipt_ref
    assert report.foundry_receipt_ref
    assert report.postflight_receipt_ref
    assert report.packet_ref
    store = blueprint_release.FileSystemCAS(build_root / "cas")
    postflight = json.loads(store.get_bytes(report.postflight_receipt_ref))
    assert postflight["status"] == "admissible"
    assert postflight["predicate_provenance"] == "recomputed"
    predicates = json.loads(store.get_bytes(report.predicate_receipt_ref))
    assert predicates["manifest_no_errors_provenance"] == "recomputed"
    assert predicates["compression_predicate_provenance"] == "independently_reconciled"
    assert predicates["d4_predicate_provenance"] == "independently_reconciled"
    assert predicates["d4_status"] == "admissible"
    packet = json.loads(store.get_bytes(report.packet_ref))
    decision_packet = blueprint_release.ReleaseDecisionPacket.model_validate(packet)
    assert packet["admission_receipt_ref"] == report.admission_receipt_ref
    assert packet["predicate_receipt_ref"] == report.predicate_receipt_ref
    assert packet["foundry_receipt_ref"] == report.foundry_receipt_ref
    assert packet["postflight_receipt_ref"] == report.postflight_receipt_ref
    assert packet["decision"] == "admissible"
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
    monkeypatch.setattr(blueprint_release, "postflight_checks", lambda state, profile=None: ({}, None))

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
    assert "producer_manifest_contains_errors" in report.notes


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
            if artifact_id == receipt.manifest_ref.artifact_id:
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
