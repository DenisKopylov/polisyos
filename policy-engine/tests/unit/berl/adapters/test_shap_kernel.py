from __future__ import annotations

import pytest

from polisyos.berl.adapters.protocol import AdapterUnavailableError, ExplanationContext
from polisyos.berl.adapters.shap_kernel import KernelSHAPAdapter
from tests._helpers.mirror_contracts import assert_source_stem_has_static_contract


def _context(
    *,
    feature_dependence_policy: str = "conditional_observational",
) -> ExplanationContext:
    return ExplanationContext(
        feature_names=("x1", "x2"),
        output_scale="logit",
        perturbation_distribution="conditional_empirical_local",
        feature_dependence_policy=feature_dependence_policy,
    )


def test_kernel_shap_exact_enumeration_matches_linear_model() -> None:
    assert_source_stem_has_static_contract("berl", "shap_kernel")
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


@pytest.mark.parametrize(
    ("method_id", "feature_dependence_policy"),
    [
        ("kernel_shap", "conditional_observational"),
        ("kernel_shap_conditional", "marginal_interventional"),
    ],
)
def test_kernel_shap_direct_call_refuses_unverified_conditional_route(
    method_id: str,
    feature_dependence_policy: str,
) -> None:
    model_calls: list[dict[str, float]] = []

    def model(features: dict[str, float]) -> float:
        model_calls.append(dict(features))
        return features["x1"]

    with pytest.raises(AdapterUnavailableError, match="verified conditional law"):
        KernelSHAPAdapter(method_id=method_id).explain(
            model,
            {"x1": 1.0, "x2": 1.0},
            _context(feature_dependence_policy=feature_dependence_policy),
        )

    assert model_calls == []
