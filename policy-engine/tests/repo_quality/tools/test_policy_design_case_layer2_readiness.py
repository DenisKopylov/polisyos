from __future__ import annotations

import copy
from pathlib import Path

from tools.quality.validation import check_policy_design_case_layer2_readiness as readiness

REPO_ROOT = Path(__file__).resolve().parents[3]


def _issue_codes(validation: dict[str, object]) -> set[str]:
    return {str(issue["code"]) for issue in validation["issues"]}  # type: ignore[index]


def test_layer2_s0_readiness_manifest_is_valid() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)

    assert validation["status"] == "pass", validation["issues"]
    assert validation["summary"]["open_cell_count_baseline"] == 17  # type: ignore[index]
    assert validation["summary"]["assigned_open_cell_count"] == 17  # type: ignore[index]
    assert validation["summary"]["current_open_cell_count"] == 13  # type: ignore[index]
    assert validation["summary"]["s0_cells_closed"] == []  # type: ignore[index]
    assert validation["summary"]["cells_closed_since_s0"] == [
        "INTERVENTION.design_candidate",
        "INTERVENTION.design_grammar",
        "INTERVENTION.reversibility_lifecycle_stakes",
        "KNOWLEDGE.epistemic_regime",
    ]  # type: ignore[index]


def test_layer2_slice_cell_matrix_preserves_baseline_and_current_open_subset() -> None:
    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)
    cluster_map = payloads["cluster_map"]
    current_open_cells = readiness._open_cell_refs(cluster_map)  # type: ignore[attr-defined]
    assigned = {
        str(entry["cell_ref"]) for entry in payloads["slice_cell_matrix"].get("assignment", [])
    }

    assert len(assigned) == 17
    assert current_open_cells < assigned
    assert assigned - current_open_cells == {
        "INTERVENTION.design_candidate",
        "INTERVENTION.design_grammar",
        "INTERVENTION.reversibility_lifecycle_stakes",
        "KNOWLEDGE.epistemic_regime",
    }


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
    assert validation["summary"]["inventory_artifact_count"] >= 8  # type: ignore[index]
