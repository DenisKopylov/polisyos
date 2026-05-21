from __future__ import annotations

from polisyos.foundry.validation.method_quality import (
    build_foundry_method_report,
    build_foundry_method_report_from_execution_outputs,
    normalize_foundry_method_report,
)


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _method(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "method_id": "causal.difference_in_differences",
        "method_family": "causal_effect_estimation",
        "input_refs": {
            "data_snapshot_ref": _sha("1"),
            "input_bindings_ref": _sha("2"),
        },
        "assumptions": ["parallel_trends", "stable_composition"],
        "identification_requirements": {
            "estimand": "ATT",
            "requirements": ["parallel_trends", "overlap"],
        },
        "uncertainty": {"status": "pass", "interval": [0.01, 0.07]},
        "missingness": {"status": "pass", "missing_rate": 0.02},
        "missingness_handling": {
            "strategy": "complete_case_with_ipw_sensitivity",
            "status": "pass",
        },
        "sensitivity": {"status": "pass", "robustness": "moderate"},
        "transportability_limits": {
            "target_population": "wartime_msmes",
            "limits": ["No extrapolation outside observed firm-size support."],
        },
        "method_refs": {
            "method_spec_ref": _sha("b"),
            "execution_plan_ref": _sha("c"),
        },
        "objective_tradeoff_refs": {
            "objective_ref": _sha("d"),
            "tradeoff_ref": _sha("e"),
        },
        "uncertainty_refs": {"uncertainty_envelope_ref": _sha("f")},
        "sensitivity_refs": {"sensitivity_result_ref": _sha("0")},
        "limitation_refs": {"method_limitation_ref": _sha("b")},
        "specification_space": {
            "primary": "two_way_fixed_effects",
            "alternatives": ["event_study", "matched_did"],
        },
        "method_result_refs": {"method_result_ref": _sha("3")},
        "validity_surfaces": {
            "identification": {"status": "present", "ref": _sha("4")},
            "transportability": {"status": "present", "ref": _sha("5")},
            "partial_identification": {"status": "present", "ref": _sha("6")},
            "recoverability": {"status": "present", "ref": _sha("7")},
            "causal_ensemble": {"status": "present", "ref": _sha("8")},
            "falsification": {"status": "present", "ref": _sha("9")},
            "certificate_proof": {"status": "present", "ref": _sha("a")},
        },
        "input_diagnostics": {
            "status": "pass",
            "sample_size": 240,
            "min_required_sample_size": 30,
        },
        "result_summary": {"effect_estimate": 0.04},
    }
    payload.update(overrides)
    return payload


def test_foundry_method_report_passes_for_valid_method_diagnostics() -> None:
    report = build_foundry_method_report(
        selected_methods=[_method()],
        expected_method_expectations=["causal_effect_estimation"],
        canary_kind="production",
    )

    assert report["status"] == "pass"
    assert report["selected_methods"][0]["method_id"] == "causal.difference_in_differences"
    assert report["blocking_issue_count"] == 0


def test_foundry_method_report_fails_point_estimate_without_uncertainty() -> None:
    method = _method(uncertainty={}, result_summary={"effect_estimate": 0.04})

    report = build_foundry_method_report(
        selected_methods=[method],
        expected_method_expectations=["causal_effect_estimation"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert "point_estimate_without_uncertainty" in issue_codes


def test_foundry_method_report_requires_assumptions_and_sensitivity() -> None:
    method = _method(assumptions=[], sensitivity={})

    report = build_foundry_method_report(
        selected_methods=[method],
        expected_method_expectations=["causal_effect_estimation"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert "method_assumptions_missing" in issue_codes
    assert "method_sensitivity_missing" in issue_codes


def test_foundry_method_report_fails_insufficient_data_without_degrade() -> None:
    method = _method(
        input_diagnostics={
            "status": "pass",
            "sample_size": 8,
            "min_required_sample_size": 30,
        },
        degradation={},
    )

    report = build_foundry_method_report(
        selected_methods=[method],
        expected_method_expectations=["causal_effect_estimation"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert "insufficient_data_without_degrade" in issue_codes


def test_foundry_method_report_fails_unexpected_method_family() -> None:
    method = _method(method_family="forecasting")

    report = build_foundry_method_report(
        selected_methods=[method],
        expected_method_expectations=["causal_effect_estimation"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert "method_family_not_expected" in issue_codes


def test_foundry_method_report_requires_registry_surfaces_and_result_refs() -> None:
    method = _method(
        identification_requirements={},
        transportability_limits={},
        specification_space={},
        method_result_refs={},
        validity_surfaces={},
    )

    report = build_foundry_method_report(
        selected_methods=[method],
        expected_method_expectations=["causal_effect_estimation"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert {
        "method_identification_requirements_missing",
        "method_transportability_limits_missing",
        "method_specification_space_missing",
        "method_result_refs_missing",
        "method_validity_surface_missing",
    } <= issue_codes


def test_normalize_report_refuses_raw_pass_without_uncertainty() -> None:
    normalized = normalize_foundry_method_report(
        {
            "status": "pass",
            "selected_methods": [
                _method(uncertainty={}, result_summary={"effect_estimate": 0.04})
            ],
        },
        expected_method_expectations=["causal_effect_estimation"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in normalized["issues"]}
    assert normalized["status"] == "fail"
    assert "point_estimate_without_uncertainty" in issue_codes


def test_builds_method_report_from_actual_execution_outputs_with_foundry_refs() -> None:
    data_snapshot_ref = "sha256:" + "a" * 64
    input_bindings_ref = "sha256:" + "b" * 64
    method_result_ref = "sha256:" + "c" * 64
    method_evidence_ref = "sha256:" + "d" * 64

    report = build_foundry_method_report_from_execution_outputs(
        method_outputs=[
            {
                "method_result_ref": method_result_ref,
                "method_evidence_ref": method_evidence_ref,
                "method_result": {
                    "report": {
                        "method": "difference_in_differences",
                        "status": "success",
                        "estimand": "ATT",
                        "point_estimate": 0.04,
                        "standard_error": 0.01,
                        "confidence_interval": [0.01, 0.07],
                        "confidence_level": 0.95,
                        "inference_method": "bootstrap",
                        "assumptions": {
                            "parallel_trends": "pass",
                            "stable_composition": "pass",
                        },
                        "sample_size": 240,
                        "n_treated": 120,
                        "n_control": 120,
                        "diagnostics": [
                            {"test_name": "parallel_trends", "passed": True},
                            {
                                "test_name": "missingness_rate",
                                "passed": True,
                                "details": {"missing_rate": 0.02},
                            },
                        ],
                        "metadata": {
                            "sensitivity": {"status": "pass", "robustness": "moderate"},
                            "min_required_sample_size": 30,
                        },
                    }
                },
                    "method_evidence": {
                        "method_fqn": "causal.inference.difference_in_differences@1.0.0",
                        "backend": "numpy",
                        "result_ref": method_result_ref,
                    },
                    "identification_result_ref": _sha("1"),
                    "transportability_result_ref": _sha("2"),
                    "partial_identification_result_ref": _sha("3"),
                    "recoverability_result_ref": _sha("4"),
                    "causal_ensemble_result_ref": _sha("5"),
                    "falsification_result_ref": _sha("6"),
                    "certificate_proof_ref": _sha("7"),
                }
            ],
        foundry_input_refs={
            "data_snapshot_ref": data_snapshot_ref,
            "input_bindings_ref": input_bindings_ref,
        },
        expected_method_expectations=["causal_effect_estimation"],
        canary_kind="production",
    )

    selected = report["selected_methods"][0]
    assert report["status"] == "pass"
    assert report["foundry_input_refs"] == {
        "data_snapshot_ref": data_snapshot_ref,
        "input_bindings_ref": input_bindings_ref,
    }
    assert selected["method_id"] == "causal.inference.difference_in_differences@1.0.0"
    assert selected["method_family"] == "causal_effect_estimation"
    assert selected["input_refs"]["data_snapshot_ref"] == data_snapshot_ref
    assert selected["input_refs"]["input_bindings_ref"] == input_bindings_ref
    assert selected["result_refs"]["method_result_ref"] == method_result_ref
    assert selected["result_refs"]["method_evidence_ref"] == method_evidence_ref
    assert selected["uncertainty"]["interval"] == [0.01, 0.07]
    assert selected["missingness"]["missing_rate"] == 0.02
    assert selected["input_diagnostics"]["sample_size"] == 240
    assert selected["input_diagnostics"]["min_required_sample_size"] == 30
    assert selected["result_summary"]["point_estimate"] == 0.04


def test_execution_report_selects_causal_method_after_execution() -> None:
    data_snapshot_ref = "sha256:" + "a" * 64
    input_bindings_ref = "sha256:" + "b" * 64
    causal_result_ref = "sha256:" + "c" * 64
    simulation_result_ref = "sha256:" + "d" * 64

    report = build_foundry_method_report_from_execution_outputs(
        method_outputs=[
            {
                "method_id": "foundry.execute",
                "method_family": "simulation",
                "simulation_result_ref": simulation_result_ref,
                "method_result": {
                    "status": "pass",
                    "result_summary": {"effect_estimate": 0.04},
                    "assumptions": ["generic_transition_model"],
                    "uncertainty": {"status": "pass", "interval": [0.01, 0.07]},
                    "missingness": {"status": "pass", "missing_rate": 0.02},
                    "sensitivity": {"status": "pass", "robustness": "moderate"},
                    "input_diagnostics": {
                        "sample_size": 240,
                        "min_required_sample_size": 30,
                    },
                },
            },
            {
                "method_result_ref": causal_result_ref,
                "method_result": {
                    "report": {
                        "method": "difference_in_differences",
                        "status": "success",
                        "estimand": "ATT",
                        "point_estimate": 0.04,
                        "confidence_interval": [0.01, 0.07],
                        "assumptions": {
                            "parallel_trends": "pass",
                            "stable_composition": "pass",
                        },
                        "missingness_handling": {
                            "strategy": "complete_case_with_ipw_sensitivity",
                            "status": "pass",
                        },
                        "transportability_limits": {
                            "target_population": "wartime_msmes",
                            "limits": ["no extrapolation outside observed firm-size support"],
                        },
                        "specification_space": {
                            "primary": "two_way_fixed_effects",
                            "alternatives": ["event_study", "matched_did"],
                        },
                        "metadata": {
                            "sensitivity": {"status": "pass", "robustness": "moderate"},
                            "min_required_sample_size": 30,
                        },
                    },
                    "identification_requirements": {
                        "estimand": "ATT",
                        "requirements": ["parallel_trends", "overlap"],
                    },
                    "identification_result_ref": "sha256:" + "1" * 64,
                    "transportability_result_ref": "sha256:" + "2" * 64,
                    "partial_identification_result_ref": "sha256:" + "3" * 64,
                    "recoverability_result_ref": "sha256:" + "4" * 64,
                    "causal_ensemble_result_ref": "sha256:" + "5" * 64,
                    "falsification_result_ref": "sha256:" + "6" * 64,
                    "certificate_proof_ref": "sha256:" + "7" * 64,
                },
                "method_evidence": {
                    "method_fqn": "causal.inference.difference_in_differences@1.0.0",
                    "backend": "numpy",
                },
            },
        ],
        foundry_input_refs={
            "data_snapshot_ref": data_snapshot_ref,
            "input_bindings_ref": input_bindings_ref,
        },
        expected_method_expectations=["causal_effect_estimation"],
        canary_kind="production",
    )

    assert report["status"] == "pass"
    assert report["candidate_method_families"] == [
        "causal_effect_estimation",
        "simulation",
    ]
    assert [method["method_id"] for method in report["selected_methods"]] == [
        "causal.inference.difference_in_differences@1.0.0"
    ]
    assert report["selected_methods"][0]["method_result_refs"] == {
        "method_result_ref": causal_result_ref
    }
    assert report["rejected_methods"] == [
        {
            "method_id": "foundry.execute",
            "method_family": "simulation",
            "reason_code": "generic_simulation_not_valid_for_expected_method",
            "reason": (
                "Generic simulation output is not an analytical causal method for "
                "the expected method family."
            ),
            "result_refs": {"simulation_result_ref": simulation_result_ref},
        }
    ]

    selected = report["selected_methods"][0]
    assert selected["identification_requirements"]["requirements"] == [
        "parallel_trends",
        "overlap",
    ]
    assert selected["missingness_handling"]["strategy"] == (
        "complete_case_with_ipw_sensitivity"
    )
    assert selected["transportability_limits"]["target_population"] == "wartime_msmes"
    assert selected["specification_space"]["alternatives"] == [
        "event_study",
        "matched_did",
    ]
    assert set(selected["validity_surfaces"]) == {
        "identification",
        "transportability",
        "partial_identification",
        "recoverability",
        "causal_ensemble",
        "falsification",
        "certificate_proof",
    }
    assert selected["validity_surfaces"]["identification"]["ref"] == (
        "sha256:" + "1" * 64
    )


def test_generic_simulation_false_pass_blocks_expected_causal_method() -> None:
    report = build_foundry_method_report_from_execution_outputs(
        method_outputs=[
            {
                "method_id": "foundry.execute",
                "method_family": "simulation",
                "simulation_result_ref": "sha256:" + "8" * 64,
                "method_result": {
                    "status": "pass",
                    "result_summary": {"effect_estimate": 0.04},
                    "assumptions": ["generic_transition_model"],
                    "uncertainty": {"status": "pass", "interval": [0.01, 0.07]},
                    "missingness": {"status": "pass", "missing_rate": 0.02},
                    "sensitivity": {"status": "pass", "robustness": "moderate"},
                    "input_diagnostics": {
                        "sample_size": 240,
                        "min_required_sample_size": 30,
                    },
                },
            }
        ],
        expected_method_expectations=["causal_effect_estimation"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert report["selected_methods"] == []
    assert report["candidate_method_families"] == ["simulation"]
    assert report["rejected_methods"][0]["reason_code"] == (
        "generic_simulation_not_valid_for_expected_method"
    )
    assert "generic_simulation_false_pass" in issue_codes


def test_generic_foundry_execute_cannot_satisfy_policy_method_obligations() -> None:
    report = build_foundry_method_report_from_execution_outputs(
        method_outputs=[
            {
                "method_id": "foundry.execute",
                "method_family": "simulation",
                "simulation_result_ref": "sha256:" + "8" * 64,
                "method_result": {
                    "status": "pass",
                    "result_summary": {"effect_estimate": 0.04},
                    "assumptions": ["generic_transition_model"],
                    "uncertainty": {"status": "pass", "interval": [0.01, 0.07]},
                    "missingness": {"status": "pass", "missing_rate": 0.02},
                    "sensitivity": {"status": "pass", "robustness": "moderate"},
                    "input_diagnostics": {
                        "sample_size": 240,
                        "min_required_sample_size": 30,
                    },
                },
            }
        ],
        expected_method_expectations=[
            "distributional_evidence",
            "implementation_feasibility",
        ],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    obligation_statuses = {
        obligation["expectation"]: obligation["status"]
        for obligation in report["method_obligations"]
    }
    assert report["status"] == "fail"
    assert report["selected_methods"] == []
    assert report["rejected_methods"][0]["reason_code"] == (
        "generic_method_not_admissible"
    )
    assert "generic_method_not_admissible" in issue_codes
    assert "method_obligation_missing" in issue_codes
    assert obligation_statuses == {
        "distributional_evidence": "missing",
        "implementation_feasibility": "missing",
    }


def test_selected_generic_foundry_execute_is_demoted_under_serious_obligations() -> None:
    generic = _method(
        method_id="foundry.execute",
        method_family="mechanism_runtime_execution",
        method_expectations=["causal_effect_estimation"],
        method_refs={"runtime_method_ref": _sha("b")},
        objective_tradeoff_refs={"objective_ref": _sha("c")},
        uncertainty_refs={"uncertainty_ref": _sha("d")},
        sensitivity_refs={"sensitivity_ref": _sha("e")},
        limitation_refs={"limitation_ref": _sha("f")},
    )

    report = build_foundry_method_report(
        selected_methods=[generic],
        expected_method_expectations=[
            "causal_effect_estimation",
            "heterogeneity_by_region_or_firm_size",
            "uncertainty_interval",
            "sensitivity_or_transportability_diagnostic",
            "implementation_feasibility",
            "assumptions",
            "missingness_diagnostics",
            "analytical_proof_surfaces",
            "limitations",
            "objective_tradeoff_evidence",
        ],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert report["selected_methods"] == []
    assert report["rejected_methods"][0]["method_id"] == "foundry.execute"
    assert report["rejected_methods"][0]["reason_code"] == "generic_method_not_admissible"
    assert "generic_method_not_admissible" in issue_codes
    assert report["summary"]["method_obligation_statuses"] == {
        "analytical_proof_surfaces": "missing",
        "assumptions": "missing",
        "causal_effect_estimation": "missing",
        "heterogeneity_by_region_or_firm_size": "missing",
        "implementation_feasibility": "missing",
        "limitations": "missing",
        "missingness_diagnostics": "missing",
        "objective_tradeoff_evidence": "missing",
        "sensitivity_or_transportability_diagnostic": "missing",
        "uncertainty_interval": "missing",
    }


def test_explicit_policy_method_obligations_pass_with_refs_and_limitations() -> None:
    method = _method(
        method_id="foundry.method.wartime_msme_distributional_feasibility",
        method_expectations=[
            "causal_effect_estimation",
            "distributional_evidence",
            "implementation_feasibility",
        ],
        method_refs={
            "method_spec_ref": _sha("b"),
            "execution_plan_ref": _sha("c"),
        },
        objective_tradeoff_refs={
            "objective_ref": _sha("d"),
            "tradeoff_ref": _sha("e"),
        },
        distributional_evidence={
            "status": "pass",
            "heterogeneity_ref": _sha("f"),
            "subgroup_effect_ref": _sha("0"),
        },
        implementation_feasibility={
            "status": "pass",
            "delivery_capacity_ref": _sha("a"),
            "agency_readiness_ref": _sha("b"),
        },
        uncertainty_refs={"uncertainty_envelope_ref": _sha("c")},
        sensitivity_refs={"sensitivity_result_ref": _sha("d")},
        limitation_refs={"method_limitation_ref": _sha("e")},
    )

    report = build_foundry_method_report(
        selected_methods=[method],
        expected_method_expectations=[
            "distributional_evidence",
            "implementation_feasibility",
        ],
        canary_kind="production",
    )

    assert report["status"] == "pass"
    assert report["method_obligations"] == [
        {
            "requirement_id": "foundry.method.distributional_evidence",
            "expectation": "distributional_evidence",
            "status": "satisfied",
            "selected_method_refs": [
                "foundry.method.wartime_msme_distributional_feasibility"
            ],
            "missing_facets": [],
        },
        {
            "requirement_id": "foundry.method.implementation_feasibility",
            "expectation": "implementation_feasibility",
            "status": "satisfied",
            "selected_method_refs": [
                "foundry.method.wartime_msme_distributional_feasibility"
            ],
            "missing_facets": [],
        },
    ]
    assert report["summary"]["method_obligation_statuses"] == {
        "distributional_evidence": "satisfied",
        "implementation_feasibility": "satisfied",
    }


def test_expanded_policy_method_obligations_pass_with_named_method_surfaces() -> None:
    method = _method(
        method_id="foundry.method.wartime_msme_causal_heterogeneity",
        method_expectations=[
            "causal_effect_estimation",
            "heterogeneity_by_region_or_firm_size",
            "uncertainty_interval",
            "sensitivity_or_transportability_diagnostic",
            "implementation_feasibility",
            "objective_tradeoff_evidence",
        ],
        method_refs={
            "method_spec_ref": _sha("b"),
            "execution_plan_ref": _sha("c"),
        },
        objective_tradeoff_refs={
            "objective_ref": _sha("d"),
            "tradeoff_ref": _sha("e"),
        },
        heterogeneity_refs={
            "regional_effect_ref": _sha("f"),
            "firm_size_effect_ref": _sha("0"),
        },
        implementation_feasibility_refs={
            "delivery_capacity_ref": _sha("a"),
            "agency_readiness_ref": _sha("b"),
        },
        uncertainty_refs={"uncertainty_envelope_ref": _sha("c")},
        sensitivity_refs={"sensitivity_result_ref": _sha("d")},
        limitation_refs={"method_limitation_ref": _sha("e")},
    )

    report = build_foundry_method_report(
        selected_methods=[method],
        expected_method_expectations=[
            "causal_effect_estimation",
            "heterogeneity_by_region_or_firm_size",
            "uncertainty_interval",
            "sensitivity_or_transportability_diagnostic",
            "implementation_feasibility",
            "assumptions",
            "missingness_diagnostics",
            "analytical_proof_surfaces",
            "limitations",
            "objective_tradeoff_evidence",
        ],
        canary_kind="production",
    )

    assert report["status"] == "pass"
    assert report["summary"]["method_obligation_statuses"] == {
        "analytical_proof_surfaces": "satisfied",
        "assumptions": "satisfied",
        "causal_effect_estimation": "satisfied",
        "heterogeneity_by_region_or_firm_size": "satisfied",
        "implementation_feasibility": "satisfied",
        "limitations": "satisfied",
        "missingness_diagnostics": "satisfied",
        "objective_tradeoff_evidence": "satisfied",
        "sensitivity_or_transportability_diagnostic": "satisfied",
        "uncertainty_interval": "satisfied",
    }


def test_method_report_fails_when_method_refs_do_not_match_foundry_bindings() -> None:
    report = build_foundry_method_report(
        selected_methods=[
            _method(
                input_refs={
                    "data_snapshot_ref": "sha256:" + "1" * 64,
                    "input_bindings_ref": "sha256:" + "2" * 64,
                }
            )
        ],
        foundry_input_refs={
            "data_snapshot_ref": "sha256:" + "a" * 64,
            "input_bindings_ref": "sha256:" + "b" * 64,
        },
        expected_method_expectations=["causal_effect_estimation"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "fail"
    assert "method_input_ref_mismatch" in issue_codes


def test_insufficient_sample_size_with_explicit_degrade_does_not_pass_quality() -> None:
    report = build_foundry_method_report(
        selected_methods=[
            _method(
                input_diagnostics={
                    "status": "pass",
                    "sample_size": 8,
                    "min_required_sample_size": 30,
                },
                degradation={"status": "degraded", "reason": "insufficient_sample_size"},
            )
        ],
        expected_method_expectations=["causal_effect_estimation"],
        canary_kind="production",
    )

    issue_codes = {issue["code"] for issue in report["issues"]}
    assert report["status"] == "warn"
    assert "insufficient_data_degraded" in issue_codes
