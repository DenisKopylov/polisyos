from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path

from tools.quality.validation import check_policy_design_case_cluster_ownership_map as cluster_map
from tools.quality.validation import check_policy_design_case_layer2_readiness as readiness

REPO_ROOT = Path(__file__).resolve().parents[3]
S4_MANIFEST = (
    REPO_ROOT
    / "architecture/policy_design_case/layer2_s4_epistemic_regime_manifest.json"
)
S4_MANIFEST_PATH = "architecture/policy_design_case/layer2_s4_epistemic_regime_manifest.json"
S4_CELLS = {
    "KNOWLEDGE.epistemic_regime",
    "INTERVENTION.reversibility_lifecycle_stakes",
}
S4_LABELS = REPO_ROOT / "tests/fixtures/layer2/s4/s4_expert_labels.json"
CORPUS_CASES = REPO_ROOT / "tests/fixtures/universal-corpus/cases"
INVENTORY = REPO_ROOT / "architecture/policy_design_case/inventory.json"


def _s4() -> dict[str, object]:
    return json.loads(S4_MANIFEST.read_text(encoding="utf-8"))


def _issue_codes(validation: dict[str, object]) -> set[str]:
    return {str(issue["code"]) for issue in validation["issues"]}  # type: ignore[index]


def _payloads() -> dict[str, object]:
    return copy.deepcopy(readiness.load_layer2_readiness_payloads(REPO_ROOT))


def _s4_labels() -> dict[str, object]:
    payload = json.loads(S4_LABELS.read_text(encoding="utf-8"))
    return dict(payload["cases"])


def test_layer2_s4_manifest_is_valid_and_live_open_count_is_4() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)

    assert validation["status"] == "pass", validation["issues"]
    assert validation["summary"]["open_cell_count"] == 3  # type: ignore[index]
    assert validation["summary"]["s4_w12_overblocking_hypothesis"] == "confirmed"  # type: ignore[index]
    assert validation["summary"]["s4_regime_accuracy"] == 1.0  # type: ignore[index]
    assert validation["summary"]["s4_expected_current_open_cell_count"] == 13  # type: ignore[index]


def test_layer2_s4_manifest_is_registered_in_inventory() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    artifacts = {artifact["path"]: artifact for artifact in inventory["artifacts"]}
    artifact = artifacts[S4_MANIFEST_PATH]

    assert artifact["id"] == "layer2_s4_epistemic_regime_manifest"
    assert artifact["kind"] == "layer2_s4_epistemic_regime_manifest"
    assert artifact["schema_version"] == (
        "policyos.policy_design_case.layer2_s4_epistemic_regime_manifest.v1"
    )
    assert artifact["capability_reality_label"] == "implemented"
    assert "epistemic_regime_classification" in artifact["authority_scope"]
    assert "risk_regime_authority_without_risk_evidence" in artifact["may_not_use_for"]
    assert artifact["validator"] == (
        "tools/quality/validation/check_policy_design_case_layer2_readiness.py"
    )


def test_layer2_s4_manifest_records_cells_metrics_and_authority_boundary() -> None:
    manifest = _s4()

    assert manifest["schema_version"] == (
        "policyos.policy_design_case.layer2_s4_epistemic_regime_manifest.v1"
    )
    assert set(manifest["cells_closed"]) == S4_CELLS  # type: ignore[arg-type]
    assert manifest["expected_current_open_cell_count"] == 13
    assert manifest["regime_accuracy"] == 1.0
    assert manifest["penalized_score"] == 1.0
    assert manifest["commitment_profile_adequacy"] == 0.9231
    assert manifest["w12_overblocking_hypothesis"] == "confirmed"
    assert set(manifest["required_artifacts"]) == {  # type: ignore[arg-type]
        "CommitmentProfileRecord",
        "EpistemicRegimeClaim",
        "RegimeEvidenceBasis",
    }
    assert {
        "risk_regime_authority_without_risk_evidence",
        "b_side_regime_selection",
        "outcome_claim_from_ignorance",
        "low_stakes_floor_on_catastrophic_irreversible",
    } <= set(manifest["may_not_use_for"])  # type: ignore[arg-type]


def test_layer2_s4_cluster_map_marks_cells_implemented_and_not_open() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)

    assert payload["cell"]["KNOWLEDGE"]["epistemic_regime"]["ratchet_state"] == (
        "implemented"
    )
    assert payload["cell"]["KNOWLEDGE"]["epistemic_regime"]["p01_chain"] == (
        "implemented"
    )
    assert payload["cell"]["INTERVENTION"]["reversibility_lifecycle_stakes"][
        "ratchet_state"
    ] == "implemented"
    assert payload["cell"]["INTERVENTION"]["reversibility_lifecycle_stakes"][
        "p01_chain"
    ] == "implemented"
    open_closures = payload.get("open_cell_closure", {})
    assert "epistemic_regime" not in open_closures.get("KNOWLEDGE", {})
    assert "reversibility_lifecycle_stakes" not in open_closures.get("INTERVENTION", {})


def test_layer2_s4_expert_labels_cover_13_cases_with_regime_and_commitment_gold() -> None:
    labels = _s4_labels()
    cases = {path.stem for path in CORPUS_CASES.glob("*.json")}
    regimes = {"risk", "uncertainty", "ambiguity", "ignorance", "contested_model"}
    commitment_fields = {
        "reversibility",
        "option_value",
        "lifecycle_stage",
        "transition_cost",
        "stakes",
    }

    assert len(cases) == 13
    assert set(labels) == cases
    for entry in labels.values():
        assert entry["expert_regime"] in regimes  # type: ignore[index]
        assert commitment_fields <= set(entry)  # type: ignore[arg-type]
        assert "case_label" not in entry
        assert "expected_outcome" not in entry


def test_layer2_s4_outcome_split_comes_from_corpus_not_the_fixture() -> None:
    counts = Counter(
        json.loads(path.read_text(encoding="utf-8"))["expert_adjudication"][
            "case_label"
        ]
        for path in CORPUS_CASES.glob("*.json")
    )

    assert counts["limitation_required"] == 9
    assert counts["semantic_pass"] == 3
    assert counts["false_pass"] == 1


def test_layer2_s4_readiness_validator_rejects_missing_authority_boundary() -> None:
    payloads = _payloads()
    payloads["s4_epistemic_regime"]["may_not_use_for"] = [  # type: ignore[index]
        "production_claim_authority"
    ]

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_s4_authority_boundary_incomplete" in _issue_codes(validation)
