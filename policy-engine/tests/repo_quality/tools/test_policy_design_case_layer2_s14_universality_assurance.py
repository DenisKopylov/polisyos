from __future__ import annotations

# ruff: noqa: S101
import importlib
import json
import tomllib
from pathlib import Path
from typing import Any

import polisyos.runtime.quality as runtime_quality
from tools.quality.validation import check_policy_design_case_layer2_readiness as readiness

REPO_ROOT = Path(__file__).resolve().parents[3]
S14_MANIFEST = (
    REPO_ROOT
    / "architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json"
)
S14_MANIFEST_PATH = (
    "architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json"
)
S14_REQUIRED_ARTIFACTS = {
    "SealedUniversalityBatteryRun",
    "UniversalityAxisScorecard",
    "MechanismGeneralityReport",
    "SkepticDefeaterRecord",
    "UniversalityClaimAssuranceCase",
    "UniversalityClaimGateRecord",
}
S14_REQUIRED_SUPPORTING_RECORDS = {
    "D4CorpusTrackCoverage",
    "ExpertOracleBootstrapRecord",
    "UniversalityBreadthFloorConfig",
    "UniversalityBaselineComparison",
    "GroundedAuthorityCoverageRecord",
    "EvaluationStatusCompositionRecord",
    "EnvelopeRevisionDynamicsRecord",
}
S14_REQUIRED_AUTHORITY_SCOPE = {
    "s14_universality_claim_gate",
    "sealed_battery_integrity",
    "per_axis_universality_scorecard",
    "mechanism_generality_assessment",
    "skeptic_defeater_evaluation",
    "d4_corpus_track_coverage",
    "expert_oracle_bootstrap",
    "universality_breadth_floor",
    "baseline_comparison",
    "grounded_authority_coverage",
    "evaluation_status_composition",
    "envelope_revision_dynamics",
    "declared_operation_envelope",
}
S14_REQUIRED_DENY = {
    "production_rollout_authority",
    "production_recommendation",
    "recommendation_authority",
    "publication_authority",
    "approval_authority",
    "claim_authority",
    "runtime_closeout_authority",
    "scorecard_authority",
    "preference_learning",
    "automated_value_learning",
    "sealed_battery_training",
    "development_fixture_access",
    "aggregate_universal_score",
    "untested_axis_envelope_expansion",
    "gold_label_authority",
    "weak_gold_promotion_floor",
    "shadow_candidate_oracle",
    "baseline_free_universal_claim",
    "grounded_authority_without_a_firewalls",
    "status_composition_override",
}
S14_FALSE_CLEAR_FIELDS = (
    "bare_universal_claim_without_battery",
    "sealed_battery_dev_access",
    "aggregate_universal_number_laundering",
    "untested_axis_combination_in_envelope",
    "bespoke_cost_hidden_as_generality",
    "skeptic_defeater_ignored",
    "faithfulness_claim_without_s9",
    "battery_result_as_production_authority",
    "gold_label_leak_into_dev_signal",
    "freeze_hash_mismatch_accepted",
    "d4_breadth_floor_missing",
    "expert_oracle_bootstrap_missing",
    "weak_gold_floor_laundering",
    "shadow_candidate_oracle_laundering",
    "grounded_authority_refs_missing",
    "status_composition_laundering",
    "envelope_revision_freeze_laundering",
    "baseline_comparison_missing",
)
S14_SKEPTIC_MAPPING = {
    "bespoke_disguise_defeater": "This is bespoke in disguise.",
    "confident_theater_defeater": "It is confident theater.",
    "failure_boundary_defeater": "It does not know where it fails.",
    "single_axis_universality_defeater": "It is universal only on one axis.",
    "frozen_once_defeater": "It works once, then freezes.",
    "first_call_defeater": "Why call it first?",
}
S14_REQUIRED_SUBSTRATE_REUSE_REFS = {
    "src/polisyos/runtime/quality/assurance_case.py#build_universality_assurance_case",
    "src/polisyos/runtime/quality/assurance_case.py#build_assurance_case_for_scorecard",
    "src/polisyos/runtime/quality/capability_ratchet.py#build_capability_reality_report",
    "src/polisyos/runtime/quality/layer2_resource_economics.py#GrowthThermometerRecord",
    "src/polisyos/runtime/quality/layer2_resource_economics.py#EnvelopeGrowthLedger",
    "src/polisyos/runtime/quality/layer2_post_deploy_accountability.py#EnvelopeRevision",
    "src/polisyos/runtime/quality/layer2_post_deploy_accountability.py#CertifiedEnvelopeDelta",
    "src/polisyos/runtime/quality/case_lifecycle.py#status_lattice",
    "src/polisyos/runtime/quality/approval.py#closeout_status_composition",
}


def _manifest() -> dict[str, Any]:
    assert S14_MANIFEST.exists()
    return json.loads(S14_MANIFEST.read_text(encoding="utf-8"))


def _runner() -> Any:
    return importlib.import_module("tools.quality.validation.run_layer2_s14_universality_battery")


def _runner_payload() -> dict[str, Any]:
    battery_root = (
        REPO_ROOT
        / "tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/"
        "layer2-sealed-universality-battery"
    )
    return dict(
        _runner().run_layer2_s14_universality_battery(
            repo_root=REPO_ROOT,
            battery_root=battery_root,
            allow_sealed_battery=True,
        )
    )


def _payloads() -> dict[str, Any]:
    return readiness.load_layer2_readiness_payloads(REPO_ROOT)


def _inventory_artifact() -> dict[str, Any]:
    artifacts = {
        str(artifact["id"]): artifact
        for artifact in _payloads()["inventory"]["artifacts"]
        if isinstance(artifact, dict)
    }
    return dict(artifacts["layer2_s14_universality_assurance_manifest"])


def _cluster_map() -> dict[str, Any]:
    return tomllib.loads(
        (REPO_ROOT / "architecture/policy_design_case/cluster_ownership_map.toml")
        .read_text(encoding="utf-8")
    )


def test_s14_manifest_exists_and_declares_closure_contract() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    manifest = _manifest()

    assert validation["status"] == "pass", validation["issues"]
    assert manifest["schema_version"] == (
        "policyos.policy_design_case.layer2_s14_universality_assurance_manifest.v1"
    )
    assert manifest["status"] == "active"
    assert manifest["owner"] == "governance-board"
    assert manifest["slice"] == "S14"
    assert manifest["slice_label"] == "evaluation_redesign_universality_assurance_battery"
    assert manifest["depends_on"] == [
        "S0",
        "S1",
        "S2",
        "S3",
        "S4",
        "S5",
        "S6",
        "S7",
        "S8",
        "S9",
        "S10",
        "S11",
        "S12",
        "S13",
    ]
    assert manifest["floor_id"] == "s14_universality"
    assert manifest["floor_metric"] == "per_axis_posture_thresholds_and_breadth_floor"


def test_s14_manifest_registers_six_artifacts_and_firewalls() -> None:
    manifest = _manifest()

    assert set(manifest["required_artifacts"]) == S14_REQUIRED_ARTIFACTS
    assert set(manifest["authority_scope"]) == S14_REQUIRED_AUTHORITY_SCOPE
    assert set(manifest["may_not_use_for"]) >= S14_REQUIRED_DENY
    assert set(manifest["firewalls"]) >= {
        "universality_claim_firewall",
        "held_out_integrity_firewall",
        "sealed_battery_freeze_hash_replay",
        "d4_breadth_floor_firewall",
        "expert_oracle_bootstrap_firewall",
        "grounded_authority_coverage_firewall",
        "evaluation_status_composition_firewall",
        "baseline_comparison_firewall",
        "envelope_revision_dynamics_firewall",
        "s9_faithfulness_required",
        "no_aggregate_universal_number",
        "no_production_authority_from_battery",
        "no_gold_label_or_hidden_fixture_leakage",
    }
    assert tuple(manifest["false_clear_counts"]) == S14_FALSE_CLEAR_FIELDS
    for false_clear_field in S14_FALSE_CLEAR_FIELDS:
        flat_field = f"{false_clear_field}_false_clear_count"
        assert manifest[flat_field] == 0
        assert manifest["false_clear_counts"][false_clear_field] == 0
    for artifact_name in S14_REQUIRED_ARTIFACTS:
        artifact = getattr(runtime_quality, artifact_name)
        assert artifact.model_config.get("extra") == "forbid", artifact_name


def test_s14_manifest_capability_status_is_not_runner_claim_disposition() -> None:
    manifest = _manifest()
    runner_payload = _runner_payload()
    summary = runner_payload["s14_universality_assurance_summary"]
    public_summary = runner_payload["public_summary"]
    gate_record = runner_payload["universality_claim_gate_record"]

    assert manifest["universal_claim_gate_status"] == "pass"
    assert "universal_claim_gate_status" not in summary
    assert "universal_claim_gate_status" not in public_summary
    assert summary["universal_claim_disposition"] == gate_record["disposition"]
    assert public_summary["universal_claim_disposition"] == gate_record["disposition"]
    assert summary["universal_claim_disposition"] in {
        "universal_claim_blocked",
        "universal_claim_limited",
    }
    assert summary["universal_claim_disposition"] != "universal_claim_allowed"


def test_s14_manifest_registers_d4_corpus_oracle_breadth_supporting_records() -> None:
    manifest = _manifest()

    supporting = manifest["supporting_records"]
    assert set(supporting) == S14_REQUIRED_SUPPORTING_RECORDS
    assert manifest["d4_corpus_track_count"] == 19
    assert manifest["expert_oracle_layer_count"] == 4
    assert manifest["breadth_floor_config_status"] == "ratified"
    assert manifest["baseline_comparison_status"] == "pass"
    assert manifest["grounded_authority_coverage_status"] == "pass"
    assert manifest["evaluation_status_composition_status"] == "pass"
    assert manifest["envelope_revision_dynamics_status"] == "pass"


def test_s14_manifest_registers_required_substrate_reuse_refs() -> None:
    manifest = _manifest()

    assert set(manifest["substrate_reuse_refs"]) >= S14_REQUIRED_SUBSTRATE_REUSE_REFS


def test_s14_manifest_maps_skeptic_defeaters_to_architecture_attacks() -> None:
    manifest = _manifest()

    assert manifest["skeptic_defeater_mapping"] == S14_SKEPTIC_MAPPING
    assert set(manifest["skeptic_defeater_mapping"]) == set(S14_SKEPTIC_MAPPING)
    assert "held_out_integrity_firewall" not in manifest["skeptic_defeater_mapping"]


def test_s14_manifest_requires_grounded_authority_and_baseline_comparison() -> None:
    manifest = _manifest()

    assert manifest["grounded_authority_coverage_ref"]
    assert manifest["baseline_comparison_ref"]
    assert set(manifest["required_grounded_authority_ref_types"]) >= {
        "a_firewall_refs",
        "claim_evidence_binding_refs",
        "value_choice_provenance_refs",
        "mandate_legitimacy_refs",
        "capacity_check_refs",
        "regime_refs",
        "coupling_refs",
        "projection_faithfulness_refs",
    }
    assert set(manifest["required_baseline_families"]) == {
        "bespoke_tool",
        "raw_llm",
        "expert_panel",
    }


def test_s14_manifest_advances_evaluation_corpus_without_new_closed_cell() -> None:
    manifest = _manifest()

    assert manifest["cells_closed"] == []
    assert manifest["layer_cells_advanced"] == ["DESIGNER_ITSELF.evaluation_corpus"]
    assert manifest["burn_down_complete"] is True


def test_s14_manifest_keeps_current_open_cell_count_zero() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    manifest = _manifest()

    assert manifest["expected_current_open_cell_count"] == 0
    assert manifest["remaining_open_cells"] == []
    assert validation["summary"]["current_open_cell_count"] == 0
    assert validation["summary"]["remaining_open_cells"] == []
    assert validation["summary"]["s14_expected_current_open_cell_count"] == 0


def test_s14_artifact_traceability_is_implemented_once() -> None:
    payloads = _payloads()
    trace_s14_artifacts = [
        row
        for row in payloads["artifact_traceability"]["artifact"]
        if row.get("slice") == "S14"
    ]

    assert {str(row["name"]) for row in trace_s14_artifacts} == S14_REQUIRED_ARTIFACTS
    for artifact_name in S14_REQUIRED_ARTIFACTS:
        matching = [
            row for row in trace_s14_artifacts if row.get("name") == artifact_name
        ]
        assert len(matching) == 1
        assert matching[0]["maturity"] == "implemented"


def test_s14_cluster_map_advances_evaluation_corpus_without_reopening_cell() -> None:
    cluster_map = _cluster_map()
    cell = cluster_map["cell"]["DESIGNER_ITSELF"]["evaluation_corpus"]

    assert cell["owner_module"] == "src/polisyos/corpus"
    assert cell["ratchet_state"] == "implemented"
    assert cell["p01_chain"] == "implemented"
    assert "S14" in cell["action"]
    assert "sealed battery" in cell["action"]
    assert "D4 corpus coverage" in cell["action"]
    assert "expert oracle bootstrap" in cell["action"]
    assert "breadth floor" in cell["action"]
    assert "grounded-authority coverage" in cell["action"]
    assert "baseline comparison" in cell["action"]
    assert "universal-claim gate" in cell["action"]
    assert "DESIGNER_ITSELF" not in cluster_map.get("open_cell_closure", {})


def test_s14_inventory_adds_one_manifest_and_authorizes_only_universal_claim_gate() -> None:
    manifest = _manifest()
    artifact = _inventory_artifact()
    payloads = _payloads()

    assert artifact["id"] == "layer2_s14_universality_assurance_manifest"
    assert artifact["path"] == S14_MANIFEST_PATH
    assert artifact["kind"] == "layer2_s14_universality_assurance_manifest"
    assert artifact["schema_version"] == manifest["schema_version"]
    assert artifact["owner"] == "governance-board"
    assert artifact["status"] == "active"
    assert artifact["capability_reality_label"] == "implemented"
    assert artifact["authority_scope"] == manifest["authority_scope"]
    assert artifact["may_not_use_for"] == manifest["may_not_use_for"]
    assert readiness._inventory_layer2_artifact_count(payloads["inventory"]) == 22
    assert "s14_universality_claim_gate" in artifact["authority_scope"]
    assert "production_recommendation" in artifact["may_not_use_for"]
    assert "recommendation_authority" not in artifact["authority_scope"]


def test_s14_readiness_validator_accepts_universality_assurance() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    summary = validation["summary"]

    assert validation["status"] == "pass", validation["issues"]
    assert summary["inventory_artifact_count"] == 22
    assert summary["s14_required_artifact_count"] == 6
    assert summary["s14_supporting_record_count"] >= 7
    assert summary["s14_d4_corpus_track_count"] == 19
    assert summary["s14_expert_oracle_layer_count"] == 4
    assert summary["s14_axis_scorecard_row_count"] == 27
    assert summary["s14_skeptic_defeater_count"] == 6
    assert summary["s14_universal_claim_gate_status"] == "pass"
    assert all(count == 0 for count in summary["s14_false_clear_counts"].values())


def test_s14_corpus_partition_rotates_freeze_hash_and_keeps_hidden_access_rule() -> None:
    manifest = _manifest()
    partition = json.loads(
        (REPO_ROOT / "architecture/policy_design_case/layer2_corpus_partition.json")
        .read_text(encoding="utf-8")
    )["sealed_universality_battery"]

    assert partition["path"] == (
        "tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/"
        "layer2-sealed-universality-battery"
    )
    assert partition["extensible"] is False
    assert partition["access"] == "ci_gate_only"
    assert partition["owner"] == "governance-board"
    assert partition["freeze_hash"].startswith("sha256:")
    assert partition["freeze_hash"] != (
        "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    assert partition["freeze_hash"] == manifest["sealed_battery_freeze_hash"]
    assert manifest["sealed_battery_integrity_status"] == "pass"
