from __future__ import annotations

import copy
from pathlib import Path

from tools.quality.validation import check_policy_design_case_layer2_readiness as readiness

REPO_ROOT = Path(__file__).resolve().parents[3]
CELLS_CLOSED_THROUGH_S6 = [
    "ACTOR.mandate_legitimacy",
    "ACTOR.state_capacity_feasibility",
    "INTERVENTION.design_candidate",
    "INTERVENTION.design_grammar",
    "INTERVENTION.reversibility_lifecycle_stakes",
    "INTERVENTION.scale_composition",
    "KNOWLEDGE.epistemic_regime",
    "OTHER_AGENTS.strategic_response",
    "SYSTEM.connectivity_modularity",
    "SYSTEM.dynamics_feedback",
    "SYSTEM.measurability",
    "SYSTEM.subject_granularity",
]
CELLS_CLOSED_THROUGH_S7 = sorted([
    *CELLS_CLOSED_THROUGH_S6,
    "CROSS_CUTTING.scientist_orchestration",
])


def _issue_codes(validation: dict[str, object]) -> set[str]:
    return {str(issue["code"]) for issue in validation["issues"]}  # type: ignore[index]


def test_layer2_s0_readiness_manifest_is_valid() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)

    assert validation["status"] == "pass", validation["issues"]
    assert validation["summary"]["open_cell_count_baseline"] == 17  # type: ignore[index]
    assert validation["summary"]["assigned_open_cell_count"] == 17  # type: ignore[index]
    assert validation["summary"]["current_open_cell_count"] == 4  # type: ignore[index]
    assert validation["summary"]["s0_cells_closed"] == []  # type: ignore[index]
    assert validation["summary"]["cells_closed_since_s0"] == CELLS_CLOSED_THROUGH_S7  # type: ignore[index]
    assert validation["summary"]["s6_maturity"] == "fail_closed"  # type: ignore[index]
    assert validation["summary"]["s6_case_count"] == 13  # type: ignore[index]
    assert validation["summary"]["s6_axis_coverage_count"] == 5  # type: ignore[index]
    assert validation["summary"]["s6_fail_closed_coverage"] == 1.0  # type: ignore[index]
    assert validation["summary"]["s6_false_clear_count"] == 0  # type: ignore[index]
    assert validation["summary"]["s6_expected_current_open_cell_count"] == 5  # type: ignore[index]
    assert validation["summary"]["s7_case_count"] == 13  # type: ignore[index]
    assert validation["summary"]["s7_delegation_precision"] == 1.0  # type: ignore[index]
    assert validation["summary"]["s7_delegation_recall"] == 1.0  # type: ignore[index]
    assert validation["summary"]["s7_responsibility_integrity_pass_rate"] == 1.0  # type: ignore[index]
    assert validation["summary"]["s7_oversight_theater_false_clear_count"] == 0  # type: ignore[index]
    assert validation["summary"]["s7_wrong_role_false_clear_count"] == 0  # type: ignore[index]
    assert validation["summary"]["s7_workflow_only_summary_false_clear_count"] == 0  # type: ignore[index]
    assert validation["summary"]["s7_expected_current_open_cell_count"] == 4  # type: ignore[index]


def test_layer2_slice_cell_matrix_preserves_baseline_and_current_open_subset() -> None:
    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)
    cluster_map = payloads["cluster_map"]
    current_open_cells = readiness._open_cell_refs(cluster_map)  # type: ignore[attr-defined]
    assigned = {
        str(entry["cell_ref"]) for entry in payloads["slice_cell_matrix"].get("assignment", [])
    }

    assert len(assigned) == 17
    assert current_open_cells < assigned
    assert assigned - current_open_cells == set(CELLS_CLOSED_THROUGH_S7)


def test_layer2_readiness_rejects_missing_open_cell_assignment() -> None:
    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)
    payloads = copy.deepcopy(payloads)
    payloads["slice_cell_matrix"]["assignment"] = [
        entry
        for entry in payloads["slice_cell_matrix"]["assignment"]
        if entry["cell_ref"] != "KNOWLEDGE.calibration"
    ]

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_slice_cell_matrix_current_open_cell_not_assigned" in _issue_codes(validation)


def test_layer2_readiness_rejects_maturity_as_ratchet_state() -> None:
    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)
    payloads = copy.deepcopy(payloads)
    payloads["slice_cell_matrix"]["assignment"][0]["target_state"] = "fail_closed"

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_slice_cell_matrix_unknown_ratchet_state" in _issue_codes(validation)


def test_layer2_readiness_rejects_unsealed_corpus_partition() -> None:
    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)
    payloads = copy.deepcopy(payloads)
    payloads["corpus_partition"]["sealed_universality_battery"]["path"] = (
        payloads["corpus_partition"]["dev_regression_corpus"]["path"]
    )

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_corpus_partition_not_sealed" in _issue_codes(validation)


def test_layer2_readiness_rejects_missing_required_artifact_trace() -> None:
    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)
    payloads = copy.deepcopy(payloads)
    payloads["artifact_traceability"]["artifact"] = [
        row
        for row in payloads["artifact_traceability"]["artifact"]
        if row["name"] != "CertifiedEnvelopeDelta"
    ]

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert "layer2_artifact_traceability_missing_required_artifact" in _issue_codes(validation)
    assert validation["status"] == "fail"


def test_layer2_readiness_rejects_incomplete_ua_msme_proving_case() -> None:
    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)
    payloads = copy.deepcopy(payloads)
    payloads["first_proving_case"]["constructs"].remove("fiscal_burden_per_beneficiary")

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_first_proving_case_missing_construct" in _issue_codes(validation)


def test_layer2_readiness_artifacts_are_in_policy_design_case_inventory() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)

    assert validation["status"] == "pass", validation["issues"]
    assert validation["summary"]["inventory_artifact_count"] == 15  # type: ignore[index]


def test_layer2_readiness_validates_s6_manifest_metrics_and_coverage() -> None:
    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "pass", validation["issues"]
    summary = validation["summary"]
    assert set(summary["s6_bridge_consumer_coverage"].values()) == {True}  # type: ignore[index]
    assert set(summary["s6_c3_authority_dimension_coverage"].values()) == {True}  # type: ignore[index]

    payloads = copy.deepcopy(payloads)
    payloads["s6_blind_spot_firewalls"]["false_clear_count"] = 1
    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_s6_false_clear_count_nonzero" in _issue_codes(validation)


def test_layer2_readiness_validates_s7_manifest_metrics_and_authority_boundary() -> None:
    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "pass", validation["issues"]
    s7 = payloads["s7_delegation"]
    inventory_artifact = next(
        artifact
        for artifact in payloads["inventory"]["artifacts"]
        if artifact["id"] == "layer2_s7_delegation_manifest"
    )
    assert inventory_artifact["capability_reality_label"] == "implemented"
    assert inventory_artifact["authority_scope"] == s7["authority_scope"]
    assert inventory_artifact["may_not_use_for"] == s7["may_not_use_for"]

    payloads = copy.deepcopy(payloads)
    payloads["s7_delegation"]["workflow_only_summary_false_clear_count"] = 1
    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_s7_workflow_only_summary_false_clear_count_nonzero" in _issue_codes(
        validation
    )
