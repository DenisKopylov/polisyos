from __future__ import annotations

import pytest
from polisyos.berl.adapters.ale import ALEAdapter
from polisyos.berl.adapters.gradients import FiniteDifferenceGradientAdapter
from polisyos.berl.adapters.lime import LIMEAdapter
from polisyos.berl.adapters.protocol import ExplanationContext
from polisyos.berl.adapters.shap_kernel import KernelSHAPAdapter


def _context() -> ExplanationContext:
    return ExplanationContext(
        feature_names=("x1", "x2"),
        output_scale="logit",
        perturbation_distribution="conditional_empirical_local",
        feature_dependence_policy="conditional_observational",
    )


def test_finite_difference_gradient_adapter_reconstructs_linear_delta() -> None:
    adapter = FiniteDifferenceGradientAdapter()

    def model(features):
        return 2.0 * features["x1"] - features["x2"]

    explanation = adapter.explain(model, {"x1": 1.0, "x2": 2.0}, _context())
    reconstructed = adapter.reconstruct_delta(explanation, {"x1": 0.5, "x2": 1.0})

    assert explanation.attributions["x1"] == pytest.approx(2.0)
    assert explanation.attributions["x2"] == pytest.approx(-1.0)
    assert reconstructed == pytest.approx(0.0, abs=1.0e-10)


def test_ale_adapter_returns_local_bin_effects() -> None:
    adapter = ALEAdapter()

    explanation = adapter.explain(
        lambda features: 3.0 * features["x1"] + features["x2"],
        {"x1": 1.0, "x2": 2.0},
        ExplanationContext(
            feature_names=("x1", "x2"),
            output_scale="logit",
            perturbation_distribution="conditional_empirical_local",
            feature_dependence_policy="conditional_observational",
            params={
                "background_rows": [
                    {"x1": 0.0, "x2": 1.0},
                    {"x1": 1.0, "x2": 2.0},
                    {"x1": 2.0, "x2": 3.0},
                ],
                "ale_bin_count": 2,
            },
        ),
    )

    assert explanation.attributions["x1"] == pytest.approx(3.0)
    assert explanation.attributions["x2"] == pytest.approx(1.0)

    assumptions = adapter.assumptions(_context())
    assert not assumptions.causal_claim_made
    assert assumptions.output_scale == "logit"


def test_kernel_shap_exact_enumeration_matches_linear_model() -> None:
    adapter = KernelSHAPAdapter()
    context = ExplanationContext(
        feature_names=("x1", "x2"),
        output_scale="logit",
        perturbation_distribution="marginal_interventional",
        feature_dependence_policy="marginal_interventional",
        params={"background_rows": [{"x1": 0.0, "x2": 0.0}]},
    )

    explanation = adapter.explain(
        lambda features: (2.0 * features["x1"]) + (3.0 * features["x2"]),
        {"x1": 1.0, "x2": 2.0},
        context,
    )

    assert explanation.attributions == {"x1": pytest.approx(2.0), "x2": pytest.approx(6.0)}
    assert adapter.reconstruct_delta(explanation, {"x1": 0.5, "x2": 1.0}) == pytest.approx(4.0)


def test_lime_adapter_fits_local_linear_reconstruction() -> None:
    adapter = LIMEAdapter()
    context = ExplanationContext(
        feature_names=("x1", "x2"),
        output_scale="logit",
        perturbation_distribution="conditional_empirical_local",
        feature_dependence_policy="conditional_observational",
        random_seed=42,
        params={"lime_sample_count": 128, "lime_radius": 0.5, "lime_kernel_width": 1.0},
    )

    explanation = adapter.explain(
        lambda features: (2.0 * features["x1"]) - features["x2"],
        {"x1": 1.0, "x2": 2.0},
        context,
    )

    assert explanation.attributions["x1"] == pytest.approx(2.0, abs=1.0e-3)
    assert explanation.attributions["x2"] == pytest.approx(-1.0, abs=1.0e-3)
    assert explanation.estimator_uncertainty["diagnostic"] == "weighted_ridge_local_surrogate"
