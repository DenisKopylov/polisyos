from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import polisyos.runtime.quality as runtime_quality
from tools.quality.validation import check_policy_design_case_layer2_readiness as readiness

REPO_ROOT = Path(__file__).resolve().parents[3]
S13_MANIFEST = (
    REPO_ROOT
    / "architecture/policy_design_case/layer2_s13_post_deploy_accountability_manifest.json"
)
S13_MANIFEST_PATH = (
    "architecture/policy_design_case/layer2_s13_post_deploy_accountability_manifest.json"
)
S13_REQUIRED_ARTIFACTS = {
    "DeploymentDossier",
    "DivergenceRecord",
    "LearningUpdateProposal",
    "EnvelopeRevision",
    "CertifiedEnvelopeDelta",
    "AssuranceCaseDelta",
}
S13_REQUIRED_AUTHORITY_SCOPE = {
    "post_deploy_accountability",
    "deployment_monitorability",
    "divergence_attribution",
    "learning_update_proposal",
    "post_deploy_mape_k_trace",
    "envelope_revision",
    "assurance_case_delta",
    "public_accountability_note",
}
S13_REQUIRED_DENY = {
    "production_rollout_authority",
    "recommendation_authority",
    "publication_authority",
    "approval_authority",
    "scorecard_authority",
    "pre_policy_evidence",
    "current_evidence_slot",
    "preference_learning",
    "automated_value_learning",
    "naive_ml_update",
    "s14_universality",
    "llm_attribution_authority",
    "local_governance_enum_for_reissue",
}
S13_FALSE_CLEAR_FIELDS = (
    "post_policy_data_as_pre_policy_evidence",
    "learned_prior_in_current_evidence_slot",
    "unattributable_updates_model",
    "silent_closed_case_rewrite",
    "learning_without_attribution",
    "envelope_shrink_without_assurance_delta",
    "b_update_before_a_baseline",
    "implementation_failure_as_theory_refutation",
    "outcome_learning_without_counterfactual",
    "s13_as_production_or_recommendation_authority",
)


def _manifest() -> dict[str, Any]:
    assert S13_MANIFEST.exists()
    return json.loads(S13_MANIFEST.read_text(encoding="utf-8"))


def _payloads() -> dict[str, Any]:
    return readiness.load_layer2_readiness_payloads(REPO_ROOT)


def _inventory_artifact() -> dict[str, Any]:
    artifacts = {
        str(artifact["id"]): artifact
        for artifact in _payloads()["inventory"]["artifacts"]
        if isinstance(artifact, dict)
    }
    return dict(artifacts["layer2_s13_post_deploy_accountability_manifest"])


def _cluster_map() -> dict[str, Any]:
    return tomllib.loads(
        (REPO_ROOT / "architecture/policy_design_case/cluster_ownership_map.toml")
        .read_text(encoding="utf-8")
    )


def test_s13_manifest_exists_and_declares_closure_contract() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    manifest = _manifest()

    assert validation["status"] == "pass", validation["issues"]
    assert manifest["schema_version"] == (
        "policyos.policy_design_case.layer2_s13_post_deploy_accountability_manifest.v1"
    )
    assert manifest["status"] == "active"
    assert manifest["owner"] == "governance-board"
    assert manifest["slice"] == "S13"
    assert manifest["slice_label"] == "post_deploy_accountability_learning"
    assert manifest["depends_on"] == ["S7", "S9", "S12"]
    assert manifest["floor_id"] == "s13_accountability"
    assert manifest["floor_metric"] == "a_before_b_ratio_and_attribution_resolution"


def test_s13_manifest_registers_six_artifacts_and_firewalls() -> None:
    manifest = _manifest()

    assert set(manifest["required_artifacts"]) == S13_REQUIRED_ARTIFACTS
    assert set(manifest["authority_scope"]) == S13_REQUIRED_AUTHORITY_SCOPE
    assert set(manifest["may_not_use_for"]) >= S13_REQUIRED_DENY
    assert set(manifest["firewalls"]) >= {
        "anti_learning_authority_boundary",
        "c41_learned_prior_current_evidence_slot",
        "a_before_b_sequence",
        "closed_case_replay_integrity",
        "lucas_post_policy_pre_policy_evidence",
        "s7_governance_decision_bypass",
    }
    assert tuple(manifest["false_clear_counts"]) == S13_FALSE_CLEAR_FIELDS
    for false_clear_field in S13_FALSE_CLEAR_FIELDS:
        flat_field = f"{false_clear_field}_false_clear_count"
        assert manifest[flat_field] == 0
        assert manifest["false_clear_counts"][false_clear_field] == 0
    for artifact_name in S13_REQUIRED_ARTIFACTS:
        artifact = getattr(runtime_quality, artifact_name)
        assert artifact.model_config.get("extra") == "forbid", artifact_name


def test_s13_manifest_does_not_claim_new_closed_cell() -> None:
    manifest = _manifest()

    assert manifest["cells_closed"] == []
    assert manifest["layer_cells_advanced"] == ["DESIGNER_ITSELF.envelope_growth"]
    assert manifest["burn_down_complete"] is True


def test_s13_manifest_keeps_current_open_cell_count_zero() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    manifest = _manifest()

    assert manifest["expected_current_open_cell_count"] == 0
    assert manifest["remaining_open_cells"] == []
    assert validation["summary"]["current_open_cell_count"] == 0
    assert validation["summary"]["remaining_open_cells"] == []
    assert validation["summary"]["s13_expected_current_open_cell_count"] == 0


def test_s13_artifact_traceability_is_implemented_once() -> None:
    payloads = _payloads()
    trace_s13_artifacts = [
        row
        for row in payloads["artifact_traceability"]["artifact"]
        if row.get("slice") == "S13"
    ]

    assert {str(row["name"]) for row in trace_s13_artifacts} == S13_REQUIRED_ARTIFACTS
    for artifact_name in S13_REQUIRED_ARTIFACTS:
        matching = [
            row for row in trace_s13_artifacts if row.get("name") == artifact_name
        ]
        assert len(matching) == 1
        assert matching[0]["maturity"] == "implemented"


def test_s13_cluster_map_advances_envelope_growth_without_reopening_cell() -> None:
    cluster_map = _cluster_map()
    cell = cluster_map["cell"]["DESIGNER_ITSELF"]["envelope_growth"]

    assert cell["owner_module"] == (
        "src/polisyos/runtime/quality/design_axes/resource_economics.py"
    )
    assert cell["ratchet_state"] == "implemented"
    assert cell["p01_chain"] == "implemented"
    assert cell["gap"] == "none_for_s12_resource_economics_scope"
    assert "S13" in cell["action"]
    assert "bidirectional" in cell["action"]
    assert "DESIGNER_ITSELF" not in cluster_map.get("open_cell_closure", {})


def test_s13_inventory_adds_one_manifest_and_no_s14_claims() -> None:
    manifest = _manifest()
    artifact = _inventory_artifact()
    payloads = _payloads()

    assert artifact["id"] == "layer2_s13_post_deploy_accountability_manifest"
    assert artifact["path"] == S13_MANIFEST_PATH
    assert artifact["kind"] == "layer2_s13_post_deploy_accountability_manifest"
    assert artifact["schema_version"] == manifest["schema_version"]
    assert artifact["owner"] == "governance-board"
    assert artifact["status"] == "active"
    assert artifact["capability_reality_label"] == "implemented"
    assert artifact["authority_scope"] == manifest["authority_scope"]
    assert artifact["may_not_use_for"] == manifest["may_not_use_for"]
    assert readiness._inventory_layer2_artifact_count(payloads["inventory"]) in {21, 22}
    assert "s14_universality" in artifact["may_not_use_for"]
    assert "s14_universality" not in artifact["authority_scope"]


def test_s13_readiness_validator_accepts_post_deploy_accountability() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    summary = validation["summary"]

    assert validation["status"] == "pass", validation["issues"]
    assert summary["inventory_artifact_count"] in {21, 22}
    assert summary["s13_case_count"] == 13
    assert summary["s13_required_artifact_count"] == 6
    assert summary["s13_monitorability_rate"] == 1.0
    assert summary["s13_a_before_b_ratio"] == 1.0
    assert summary["s13_attribution_resolution_rate"] == 1.0
    assert summary["s13_envelope_shrink_count"] >= 1
    assert summary["s13_envelope_expansion_count"] >= 1
    assert summary["s13_unattributable_accountability_without_training_count"] >= 1
    assert summary["s13_learning_without_attribution_count"] == 0
    assert summary["s13_growth_without_assurance_delta_count"] == 0
