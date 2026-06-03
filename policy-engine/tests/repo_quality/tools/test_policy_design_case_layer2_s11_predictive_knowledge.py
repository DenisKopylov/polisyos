from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import polisyos.runtime.quality as runtime_quality
from tools.quality.validation import check_policy_design_case_layer2_readiness as readiness

REPO_ROOT = Path(__file__).resolve().parents[3]
S11_MANIFEST = (
    REPO_ROOT
    / "architecture/policy_design_case/layer2_s11_predictive_knowledge_manifest.json"
)
S11_MANIFEST_PATH = "architecture/policy_design_case/layer2_s11_predictive_knowledge_manifest.json"
S11_REQUIRED_ARTIFACTS = {
    "PredictiveAxisCalibrationRecord",
    "PredictiveAxisUpgradeRecord",
    "ProofCarryingAnalyticsRecord",
    "S11PredictiveKnowledgeIntegrityReport",
}
S11_REQUIRED_DENY = {
    "production_authority",
    "production_recommendation",
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "closeout_authority",
    "runtime_closeout_authority",
    "approval_authority",
    "scorecard_authority",
    "calibrated_equilibrium_prediction",
    "rich_simulation_authority",
    "portfolio_optimization_authority",
    "preference_learning_authority",
    "s12_envelope_growth",
    "s13_accountability_closure",
    "s14_universality",
    "mandate_legitimacy_predictive_upgrade",
    "historical_prior_current_evidence",
    "llm_method_authority",
}
EXPECTED_REMAINING_OPEN_CELLS = {"DESIGNER_ITSELF.envelope_growth"}
EXPECTED_MATURITY_TRANSITIONS = {
    "OTHER_AGENTS.strategic_response",
    "ACTOR.state_capacity_feasibility",
    "SYSTEM.measurability",
    "SYSTEM.subject_granularity",
}


def _manifest() -> dict[str, Any]:
    return json.loads(S11_MANIFEST.read_text(encoding="utf-8"))


def _payloads() -> dict[str, Any]:
    return readiness.load_layer2_readiness_payloads(REPO_ROOT)


def _inventory_artifact() -> dict[str, Any]:
    artifacts = {
        str(artifact["id"]): artifact
        for artifact in _payloads()["inventory"]["artifacts"]
        if isinstance(artifact, dict)
    }
    return dict(artifacts["layer2_s11_predictive_knowledge_manifest"])


def _s11_false_clear_fields() -> tuple[str, ...]:
    return tuple(runtime_quality.S11_FALSE_CLEAR_FIELDS)


def test_layer2_s11_manifest_exists_and_open_count_drops_to_1() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    manifest = _manifest()

    assert validation["status"] == "pass", validation["issues"]
    assert manifest["schema_version"] == (
        "policyos.policy_design_case.layer2_s11_predictive_knowledge_manifest.v1"
    )
    assert manifest["status"] == "active"
    assert manifest["owner"] == "team-research"
    assert manifest["slice"] == "S11"
    assert manifest["depends_on"] == ["S6", "S10"]
    assert set(manifest["cells_closed"]) == {
        "KNOWLEDGE.calibration",
        "KNOWLEDGE.ir_proof_carrying_analytics",
    }
    assert manifest["expected_current_open_cell_count"] == 1
    assert set(manifest["remaining_open_cells"]) == EXPECTED_REMAINING_OPEN_CELLS

    summary = validation["summary"]
    assert summary["current_open_cell_count"] == 0
    assert set(summary["remaining_open_cells"]) == set()
    assert summary["s11_case_count"] == 13
    assert summary["s11_expected_current_open_cell_count"] == 1
    assert summary["inventory_artifact_count"] >= 19


def test_layer2_s11_required_artifacts_are_traceable_and_exported() -> None:
    payloads = _payloads()
    manifest = _manifest()
    trace_s11_artifacts = {
        str(row["name"])
        for row in payloads["artifact_traceability"]["artifact"]
        if row.get("slice") == "S11"
    }
    trace_s11_maturity = {
        str(row["name"]): row.get("maturity")
        for row in payloads["artifact_traceability"]["artifact"]
        if row.get("slice") == "S11"
    }

    assert set(manifest["required_artifacts"]) == S11_REQUIRED_ARTIFACTS
    assert trace_s11_artifacts == S11_REQUIRED_ARTIFACTS
    assert trace_s11_maturity == {
        "PredictiveAxisCalibrationRecord": "implemented",
        "PredictiveAxisUpgradeRecord": "implemented",
        "ProofCarryingAnalyticsRecord": "implemented",
        "S11PredictiveKnowledgeIntegrityReport": "implemented",
    }
    for artifact_name in S11_REQUIRED_ARTIFACTS:
        artifact = getattr(runtime_quality, artifact_name)
        assert artifact.model_config.get("extra") == "forbid", artifact_name


def test_layer2_s11_inventory_registration_exists() -> None:
    manifest = _manifest()
    artifact = _inventory_artifact()

    assert artifact["id"] == "layer2_s11_predictive_knowledge_manifest"
    assert artifact["path"] == S11_MANIFEST_PATH
    assert artifact["kind"] == "layer2_s11_predictive_knowledge_manifest"
    assert artifact["schema_version"] == manifest["schema_version"]
    assert artifact["owner"] == "team-research"
    assert artifact["status"] == "active"
    assert artifact["capability_reality_label"] == "implemented"
    assert artifact["authority_scope"] == manifest["authority_scope"]
    assert artifact["may_not_use_for"] == manifest["may_not_use_for"]


def test_layer2_s11_floor_and_false_clears_are_governed() -> None:
    payloads = _payloads()
    manifest = _manifest()
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    summary = validation["summary"]
    floor = next(
        row
        for row in payloads["floor_governance"]["floor"]
        if row.get("floor_id") == "s11_axis_calibration"
    )

    assert floor["slice"] == "S11"
    assert floor["metric"] == "per_axis_predictive_calibration"
    assert manifest["case_count"] == 13
    assert manifest["axis_count"] == 52
    assert manifest["per_axis_predictive_calibration_denominator"] == (
        manifest["axis_count"]
    )
    assert manifest["per_axis_predictive_calibration_threshold_ref"]
    assert manifest["per_axis_predictive_calibration_pass_rate"] >= (
        manifest["per_axis_predictive_calibration_threshold"]
    )
    assert manifest["per_axis_predictive_calibration_status"] == "pass"
    assert manifest["per_axis_predictive_calibration_floor_passed"] is True
    assert manifest["predictive_axis_count"] + manifest[
        "reverted_fail_closed_axis_count"
    ] == manifest["axis_count"]
    assert summary["s11_axis_count"] == 52
    assert summary["s11_per_axis_predictive_calibration_denominator"] == (
        summary["s11_axis_count"]
    )
    assert summary["s11_method_infrastructure_consumed_count"] > 0

    for nested_field in _s11_false_clear_fields():
        flat_field = f"{nested_field}_false_clear_count"
        assert manifest[flat_field] == 0
        assert summary[f"s11_{flat_field}"] == 0
        assert summary["s11_false_clear_counts"][nested_field] == 0


def test_layer2_s11_manifest_keeps_s12_s13_s14_and_production_authority_scoped() -> None:
    manifest = _manifest()
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    summary = validation["summary"]
    rendered_manifest = json.dumps(manifest, sort_keys=True)

    assert set(manifest["may_not_use_for"]) >= S11_REQUIRED_DENY
    assert set(summary["remaining_open_cells"]) == set()
    assert "ACTOR.mandate_legitimacy" not in {
        transition["cell_ref"] for transition in manifest["maturity_transitions"]
    }
    for future_term in (
        "s12_envelope_growth",
        "s13_accountability",
        "s14_universality",
        "production_authority",
        "preference_learning",
        "rich_simulation",
        "portfolio_optimization",
        "mandate_legitimacy_predictive_upgrade",
    ):
        assert future_term in rendered_manifest
        assert f'"{future_term}": "implemented"' not in rendered_manifest


def test_layer2_s11_maturity_transitions_match_matrix() -> None:
    manifest = _manifest()
    matrix_payload = tomllib.loads(
        (REPO_ROOT / "architecture/policy_design_case/layer2_slice_cell_matrix.toml")
        .read_text(encoding="utf-8")
    )
    matrix_transitions = {
        row["cell_ref"]
        for row in matrix_payload["maturity_transition"]
        if row.get("slice") == "S11"
    }
    manifest_transitions = {
        row["cell_ref"] for row in manifest["maturity_transitions"]
    }

    assert matrix_transitions == EXPECTED_MATURITY_TRANSITIONS
    assert manifest_transitions == matrix_transitions
    assert all(
        row["from_maturity"] == "fail_closed" and row["to_maturity"] == "predictive"
        for row in manifest["maturity_transitions"]
    )
