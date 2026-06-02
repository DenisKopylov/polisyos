from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polisyos.runtime.quality as runtime_quality
from tools.quality.validation import check_policy_design_case_layer2_readiness as readiness

REPO_ROOT = Path(__file__).resolve().parents[3]
S10_MANIFEST = (
    REPO_ROOT
    / "architecture/policy_design_case/layer2_s10_outcome_prediction_manifest.json"
)
S10_MANIFEST_PATH = "architecture/policy_design_case/layer2_s10_outcome_prediction_manifest.json"
S10_REQUIRED_ARTIFACTS = {"ForecastSupport", "ForecastCalibrationRecord"}
S10_FALSE_CLEAR_FIELDS = {
    "equilibrium_contested_single_forecast_false_clear_count": (
        "equilibrium_contested_single_forecast"
    ),
    "simulation_only_evidence_laundering_false_clear_count": (
        "simulation_only_evidence_laundering"
    ),
    "uncalibrated_observable_promotion_false_clear_count": (
        "uncalibrated_observable_promotion"
    ),
    "welfare_without_value_provenance_false_clear_count": (
        "welfare_without_value_provenance"
    ),
    "observed_outcome_without_credible_evaluation_false_clear_count": (
        "observed_outcome_without_credible_evaluation"
    ),
    "scalar_welfare_hides_pareto_tradeoff_false_clear_count": (
        "scalar_welfare_hides_pareto_tradeoff"
    ),
    "weakest_boundary_ignored_false_clear_count": "weakest_boundary_ignored",
}
S10_REQUIRED_DENY = {
    "production_recommendation",
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "closeout_authority",
    "approval_authority",
    "scorecard_authority",
    "preference_learning_authority",
    "s11_calibration",
    "s12_envelope_growth",
    "s13_accountability_closure",
    "s14_universality",
}
EXPECTED_LIVE_OPEN_CELLS = {
    "DESIGNER_ITSELF.envelope_growth",
    "KNOWLEDGE.calibration",
    "KNOWLEDGE.ir_proof_carrying_analytics",
}


def _manifest() -> dict[str, Any]:
    return json.loads(S10_MANIFEST.read_text(encoding="utf-8"))


def _payloads() -> dict[str, Any]:
    return readiness.load_layer2_readiness_payloads(REPO_ROOT)


def _inventory_artifact() -> dict[str, Any]:
    artifacts = {
        str(artifact["id"]): artifact
        for artifact in _payloads()["inventory"]["artifacts"]
        if isinstance(artifact, dict)
    }
    return dict(artifacts["layer2_s10_outcome_prediction_manifest"])


def test_layer2_s10_manifest_exists_and_open_count_stays_3() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    manifest = _manifest()

    assert validation["status"] == "pass", validation["issues"]
    assert manifest["schema_version"] == (
        "policyos.policy_design_case.layer2_s10_outcome_prediction_manifest.v1"
    )
    assert manifest["status"] == "active"
    assert manifest["owner"] == "team-research"
    assert manifest["slice"] == "S10"
    assert manifest["depends_on"] == ["S5", "S6", "S8"]
    assert manifest["cells_closed"] == []
    assert manifest["layer_cells_advanced"] == [
        "outcome_prediction_welfare_comparison"
    ]
    assert manifest["expected_current_open_cell_count"] == 3
    summary = validation["summary"]
    assert summary["current_open_cell_count"] == 3
    assert summary["s10_case_count"] == 13
    assert summary["s10_expected_current_open_cell_count"] == 3
    assert summary["inventory_artifact_count"] == 18


def test_layer2_s10_required_artifacts_are_traceable_and_exported() -> None:
    payloads = _payloads()
    manifest = _manifest()
    trace_s10_artifacts = {
        str(row["name"])
        for row in payloads["artifact_traceability"]["artifact"]
        if row.get("slice") == "S10"
    }

    assert set(manifest["required_artifacts"]) == S10_REQUIRED_ARTIFACTS
    assert trace_s10_artifacts == S10_REQUIRED_ARTIFACTS
    for artifact_name in S10_REQUIRED_ARTIFACTS:
        artifact = getattr(runtime_quality, artifact_name)
        assert artifact.model_config.get("extra") == "forbid", artifact_name


def test_layer2_s10_inventory_registration_exists() -> None:
    manifest = _manifest()
    artifact = _inventory_artifact()

    assert artifact["id"] == "layer2_s10_outcome_prediction_manifest"
    assert artifact["path"] == S10_MANIFEST_PATH
    assert artifact["kind"] == "layer2_s10_outcome_prediction_manifest"
    assert artifact["schema_version"] == manifest["schema_version"]
    assert artifact["owner"] == "team-research"
    assert artifact["status"] == "active"
    assert artifact["capability_reality_label"] == "implemented"
    assert artifact["authority_scope"] == manifest["authority_scope"]
    assert artifact["may_not_use_for"] == manifest["may_not_use_for"]


def test_layer2_s10_floor_and_false_clears_are_governed() -> None:
    payloads = _payloads()
    manifest = _manifest()
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    summary = validation["summary"]
    floor = next(
        row
        for row in payloads["floor_governance"]["floor"]
        if row.get("floor_id") == "s10_calibration"
    )

    assert floor["slice"] == "S10"
    assert floor["metric"] == "observable_subset_calibration"
    assert floor["revision_rule"] == (
        "forecast_support_tier_change_requires_calibration_record"
    )
    assert manifest["case_count"] == 13
    assert manifest["observable_subset_calibration_denominator"] >= 4
    assert manifest["observable_subset_calibration_numerator"] == (
        manifest["observable_subset_calibration_denominator"]
    )
    assert manifest["observable_subset_calibration_status"] == "pass"
    assert manifest["observable_subset_calibration_floor_passed"] is True
    assert manifest["non_observable_downgrade_count"] >= 1
    assert manifest["equilibrium_contested_single_forecast_block_count"] >= 1
    assert manifest["simulation_only_evidence_block_count"] >= 1
    assert manifest["weakest_boundary_inheritance_count"] == 13

    for flat_field, nested_field in S10_FALSE_CLEAR_FIELDS.items():
        assert manifest[flat_field] == 0
        assert summary[f"s10_{flat_field}"] == 0
        assert summary["s10_false_clear_counts"][nested_field] == 0


def test_layer2_s10_does_not_mark_s11_s12_s13_or_s14_implemented() -> None:
    manifest = _manifest()
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    summary = validation["summary"]
    rendered_manifest = json.dumps(manifest, sort_keys=True)

    assert set(manifest["may_not_use_for"]) >= S10_REQUIRED_DENY
    assert set(summary["remaining_open_cells"]) == EXPECTED_LIVE_OPEN_CELLS
    assert summary["current_open_cell_count"] == 3
    for future_term in (
        "s11_calibration",
        "s12_envelope_growth",
        "s13_accountability",
        "s14_universality",
        "production_authority",
        "preference_learning",
        "rich_simulation",
        "portfolio_optimization",
    ):
        assert future_term in rendered_manifest
        assert f'"{future_term}": "implemented"' not in rendered_manifest
