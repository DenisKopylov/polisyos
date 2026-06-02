from __future__ import annotations

import copy
import json
from pathlib import Path

from tools.quality.validation import check_policy_design_case_cluster_ownership_map as cluster_map
from tools.quality.validation import check_policy_design_case_layer2_readiness as readiness
from tools.quality.validation import run_universal_outcome_corpus as w12d

REPO_ROOT = Path(__file__).resolve().parents[3]
S5_MANIFEST = (
    REPO_ROOT
    / "architecture/policy_design_case/layer2_s5_coupling_composition_manifest.json"
)
S5_MANIFEST_PATH = "architecture/policy_design_case/layer2_s5_coupling_composition_manifest.json"
S5_CASE_SIGNALS = REPO_ROOT / "tests/fixtures/layer2/s5/s5_coupling_case_signals.json"
S5_EXPERT_LABELS = REPO_ROOT / "tests/fixtures/layer2/s5/s5_coupling_expert_labels.json"
CORPUS_CASES = REPO_ROOT / "tests/fixtures/universal-corpus/cases"
S5_CELLS = {
    "SYSTEM.connectivity_modularity",
    "SYSTEM.dynamics_feedback",
    "INTERVENTION.scale_composition",
}
S5_REGIMES = {
    "modular",
    "near_decomposable",
    "hierarchically_coupled",
    "entangled",
}
S5_REQUIRED_ARTIFACTS = {
    "CompositionReceipt",
    "ComputationalTractabilityBudget",
    "CouplingGraph",
    "CouplingRegimeClassification",
    "DecompositionResult",
    "DesignInterfaceContract",
    "RecursiveDesignGraph",
    "SystemDynamicsRequirement",
}
S5_NESTED_RECORDS = {
    "BoundaryCouplingClassification",
    "CompositionLawCheck",
    "ForecastSupportScope",
    "ModuleDiscoveryResult",
}
S5_REQUIRED_DENY = {
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "equilibrium_prediction_authority",
    "whole_design_authority_without_coupling_graph",
    "whole_design_authority_from_syntactic_decomposition",
    "whole_design_authority_from_user_supplied_module_split",
    "false_modular_decomposition",
    "weakened_authority_from_tractability_cutoff",
}


def _s5() -> dict[str, object]:
    return json.loads(S5_MANIFEST.read_text(encoding="utf-8"))


def _issue_codes(validation: dict[str, object]) -> set[str]:
    return {str(issue["code"]) for issue in validation["issues"]}  # type: ignore[index]


def _payloads() -> dict[str, object]:
    return copy.deepcopy(readiness.load_layer2_readiness_payloads(REPO_ROOT))


def _registered_payloads() -> dict[str, object]:
    return _payloads()


def test_layer2_s5_manifest_is_valid_and_readiness_open_count_is_3_when_registered() -> None:
    validation = readiness.validate_layer2_readiness_payloads(_registered_payloads())

    assert validation["status"] == "pass", validation["issues"]
    summary = validation["summary"]  # type: ignore[index]
    assert summary["open_cell_count"] == 3
    assert summary["current_open_cell_count"] == 3
    assert summary["s5_expected_current_open_cell_count"] == 10
    assert summary["s5_coupling_accuracy"] == 1.0
    assert summary["s5_penalized_score"] == 1.0
    assert summary["s5_false_modular_count"] == 0
    assert summary["s5_false_entangled_count"] == 0
    assert set(summary["s5_coupling_regime_counts"]) == S5_REGIMES
    assert set(summary["s5_boundary_regime_counts"]) == S5_REGIMES
    assert "simulation_only_system_effect" in summary["s5_system_effect_support_labels"]


def test_layer2_s5_manifest_records_cells_metrics_artifacts_and_authority_boundary() -> None:
    manifest = _s5()

    assert manifest["schema_version"] == (
        "policyos.policy_design_case.layer2_s5_coupling_composition_manifest.v1"
    )
    assert set(manifest["cells_closed"]) == S5_CELLS  # type: ignore[arg-type]
    assert manifest["expected_current_open_cell_count"] == 10
    assert manifest["floors"] == ["s5_coupling_accuracy"]
    assert manifest["coupling_accuracy"] == 1.0
    assert manifest["penalized_score"] == 1.0
    assert manifest["false_modular_count"] == 0
    assert manifest["false_entangled_count"] == 0
    assert set(manifest["coupling_regime_counts"]) == S5_REGIMES  # type: ignore[arg-type]
    assert set(manifest["boundary_regime_counts"]) == S5_REGIMES  # type: ignore[arg-type]
    assert set(manifest["required_artifacts"]) == S5_REQUIRED_ARTIFACTS  # type: ignore[arg-type]
    assert set(manifest["nested_records"]) >= S5_NESTED_RECORDS  # type: ignore[arg-type]
    assert set(manifest["may_not_use_for"]) >= S5_REQUIRED_DENY  # type: ignore[arg-type]
    assert "tests/fixtures/layer2/s5/boundary_spoof_probe.json" in manifest[
        "negative_controls"
    ]
    assert "P17" in manifest["relevant_patterns"]  # type: ignore[operator]
    assert manifest["authority_boundary"] == (
        "shadow_governed_composition_gate_only_no_production_or_prediction_authority"
    )


def test_layer2_s5_cluster_map_marks_cells_implemented_and_not_open() -> None:
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)

    expected_owners = {
        "SYSTEM.connectivity_modularity": "src/polisyos/runtime/quality",
        "SYSTEM.dynamics_feedback": "src/polisyos/runtime/quality",
        "INTERVENTION.scale_composition": "src/polisyos/pdc",
    }
    for cell_ref, owner_module in expected_owners.items():
        cluster, axis = cell_ref.split(".", 1)
        cell = payload["cell"][cluster][axis]
        assert cell["owner_module"] == owner_module
        assert cell["ratchet_state"] == "implemented"
        assert cell["p01_chain"] == "implemented"
        assert cell["gap"] == "none_for_s5_scope"

    open_closures = payload.get("open_cell_closure", {})
    assert "connectivity_modularity" not in open_closures.get("SYSTEM", {})
    assert "dynamics_feedback" not in open_closures.get("SYSTEM", {})
    assert "scale_composition" not in open_closures.get("INTERVENTION", {})


def test_layer2_s5_labels_cover_13_cases_and_boundary_regimes() -> None:
    labels = json.loads(S5_EXPERT_LABELS.read_text(encoding="utf-8"))
    cases = {path.stem for path in CORPUS_CASES.glob("*.json")}
    label_cases = labels["cases"]
    boundary_regimes = {
        boundary["expert_coupling_regime"]
        for entry in label_cases.values()
        for boundary in entry["boundary_gold"]
    }

    assert len(cases) == 13
    assert set(label_cases) == cases
    assert boundary_regimes == S5_REGIMES


def test_layer2_s5_case_signals_cover_same_cases_and_contain_no_gold_fields() -> None:
    signals = json.loads(S5_CASE_SIGNALS.read_text(encoding="utf-8"))
    labels = json.loads(S5_EXPERT_LABELS.read_text(encoding="utf-8"))
    forbidden = {
        "expert_coupling_regime",
        "expected_composition_disposition",
        "coupling_matches_gold",
        "composition_matches_gold",
        "boundary_gold",
    }

    assert set(signals["cases"]) == set(labels["cases"])
    assert len(signals["cases"]) == 13
    for entry in signals["cases"].values():
        assert forbidden.isdisjoint(entry)
        for boundary in entry["observed_boundaries"]:
            assert forbidden.isdisjoint(boundary)
            assert not any("gold" in key for key in boundary)


def test_layer2_s5_manifest_metrics_match_generated_corpus_summary(tmp_path: Path) -> None:
    report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=REPO_ROOT / "tests/fixtures/universal-corpus",
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="real_producer",
    )
    summary = report["s5_coupling_summary"]
    manifest = _s5()

    for field in (
        "coupling_accuracy",
        "penalized_score",
        "false_modular_count",
        "false_entangled_count",
        "coupling_regime_counts",
        "boundary_regime_counts",
        "system_effect_support_labels",
    ):
        assert manifest[field] == summary[field]


def test_layer2_s5_readiness_validator_rejects_stale_manifest_metrics() -> None:
    payloads = _registered_payloads()
    payloads["s5_coupling_composition"]["coupling_accuracy"] = 0.5  # type: ignore[index]

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_s5_coupling_accuracy_below_floor" in _issue_codes(validation)


def test_layer2_s5_readiness_validator_rejects_missing_nested_records() -> None:
    payloads = _registered_payloads()
    nested = payloads["s5_coupling_composition"]["nested_records"]  # type: ignore[index]
    nested.remove("BoundaryCouplingClassification")

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_s5_nested_records_missing" in _issue_codes(validation)


def test_layer2_s5_readiness_validator_rejects_missing_forecast_support_scope() -> None:
    payloads = _registered_payloads()
    nested = payloads["s5_coupling_composition"]["nested_records"]  # type: ignore[index]
    nested.remove("ForecastSupportScope")

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_s5_nested_records_missing" in _issue_codes(validation)


def test_layer2_s5_readiness_validator_rejects_missing_tractability_budget() -> None:
    payloads = _registered_payloads()
    artifacts = payloads["s5_coupling_composition"]["required_artifacts"]  # type: ignore[index]
    artifacts.remove("ComputationalTractabilityBudget")

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_s5_required_artifacts_missing" in _issue_codes(validation)


def test_layer2_s5_readiness_validator_rejects_missing_boundary_spoof_probe() -> None:
    payloads = _registered_payloads()
    controls = payloads["s5_coupling_composition"]["negative_controls"]  # type: ignore[index]
    controls.remove("tests/fixtures/layer2/s5/boundary_spoof_probe.json")

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_s5_negative_control_missing" in _issue_codes(validation)


def test_layer2_s5_readiness_validator_rejects_missing_p17_authority_boundary() -> None:
    payloads = _registered_payloads()
    payloads["s5_coupling_composition"]["authority_boundary"] = "shadow_gate_only"  # type: ignore[index]

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_s5_authority_boundary_incomplete" in _issue_codes(validation)


def test_layer2_s5_readiness_validator_rejects_s5_cells_still_open() -> None:
    payloads = _registered_payloads()
    system_closures = payloads["cluster_map"]["open_cell_closure"].setdefault(  # type: ignore[index]
        "SYSTEM",
        {},
    )
    system_closures["connectivity_modularity"] = {}

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_s5_cluster_map_not_closed" in _issue_codes(validation)


def test_layer2_s5_manifest_is_registered_in_inventory() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)

    assert validation["status"] == "pass", validation["issues"]
    summary = validation["summary"]  # type: ignore[index]
    assert summary["open_cell_count"] == 3
    assert summary["s5_expected_current_open_cell_count"] == 10

    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)
    artifacts = {artifact["path"]: artifact for artifact in payloads["inventory"]["artifacts"]}
    artifact = artifacts[S5_MANIFEST_PATH]
    assert artifact["id"] == "layer2_s5_coupling_composition_manifest"
    assert artifact["kind"] == "layer2_s5_coupling_composition_manifest"
    assert artifact["schema_version"] == (
        "policyos.policy_design_case.layer2_s5_coupling_composition_manifest.v1"
    )
    assert artifact["capability_reality_label"] == "implemented"
    assert artifact["authority_scope"] == [
        "coupling_regime_classification",
        "composition_gate",
        "system_dynamics_requirement",
        "boundary_coupling_classification",
        "system_effect_support_scope",
        "computational_tractability_budget",
    ]
    assert set(artifact["may_not_use_for"]) >= S5_REQUIRED_DENY
    assert artifact["validator"] == (
        "tools/quality/validation/check_policy_design_case_layer2_readiness.py"
    )
    assert artifact["canonical_route"] == (
        "tools/quality/validation/run_universal_outcome_corpus.py"
    )
