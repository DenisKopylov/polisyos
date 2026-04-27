from __future__ import annotations

from polisyos.berl.benchmarks.policy_tabular_suite import eligibility_rows, eligibility_score_model
from polisyos.berl.service import ExplanationOrchestrator, ExplanationRequest


def test_orchestrator_returns_bounded_bundle_for_three_methods() -> None:
    rows = eligibility_rows()
    request = ExplanationRequest(
        prediction_id="prediction-1",
        row_id="row-1",
        x=rows[0],
        feature_names=("income", "assets", "employment_status", "household_size"),
        methods=("kernel_shap", "lime", "ale_local_bin"),
        output_name="eligibility_risk",
        output_scale="logit",
        background_rows=rows,
        n_eval_perturbations=64,
        residual_cap=10.0,
        adapter_params={
            "lime_sample_count": 64,
            "max_exact_shap_features": 6,
            "ale_bin_count": 4,
        },
    )

    bundle = ExplanationOrchestrator().explain(eligibility_score_model, request)

    assert bundle.methods
    assert {method.method_id for method in bundle.methods} == {
        "kernel_shap",
        "lime",
        "ale_local_bin",
    }
    assert all(method.infidelity is not None for method in bundle.methods)
    assert bundle.disagreement is not None
    assert bundle.disagreement.methods_compared == ["kernel_shap", "lime", "ale_local_bin"]


def test_orchestrator_fails_closed_for_missing_adapter() -> None:
    request = ExplanationRequest(
        prediction_id="prediction-1",
        row_id="row-1",
        x={"x1": 1.0},
        feature_names=("x1",),
        methods=("missing_adapter",),
        n_eval_perturbations=8,
    )

    bundle = ExplanationOrchestrator().explain(lambda features: features["x1"], request)

    assert bundle.faithfulness_claim == "unbounded"
    assert bundle.display_policy == "diagnostic_only"
    assert bundle.methods[0].scope == "diagnostic"
