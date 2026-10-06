"""Behavioral oracles for law-bound conditional Shapley profiles."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace

import numpy as np
import pytest

from polisyos.berl.adapters.conditional_shapley import (
    ConditionalLawBinding,
    ConditionalSHAPAdapter,
    GaussianJointLaw,
    ResolvedConditionalLaw,
    VerifiedAffineModelProfile,
    WeightedFiniteSupportLaw,
    finite_support_conditional_expectation,
    finite_support_conditional_shapley,
    fixed_n_hoeffding_plan,
    gaussian_bounded_conditional_shapley,
    gaussian_conditional_moments,
    gaussian_linear_conditional_shapley,
)
from polisyos.berl.adapters.protocol import (
    AdapterUnavailableError,
    ExplanationContext,
    ScalarModel,
)
from polisyos.berl.adapters.shap_kernel import KernelSHAPAdapter
from polisyos.berl.contracts.schema import validate_persisted_explanation_bundle
from polisyos.berl.service import ExplanationOrchestrator, ExplanationRequest
from polisyos.runtime.quality.explanation_reliability import _validate_bundle_record
from polisyos.scientist.validation.phase5_preflight import _run_berl_validation

FEATURES = ("x1", "x2")
CORRELATED_GAUSSIAN = GaussianJointLaw(
    mean=(0.0, 0.0),
    covariance=((1.0, 0.8), (0.8, 1.0)),
)


def test_gaussian_conditional_mean_uses_correlations_without_diagonal_jitter() -> None:
    result = gaussian_conditional_moments(
        CORRELATED_GAUSSIAN,
        feature_order=FEATURES,
        coalition=frozenset({"x1"}),
        observed={"x1": 1.0, "x2": 1.0},
    )

    assert result.mean == pytest.approx((1.0, 0.8))
    assert np.asarray(result.covariance) == pytest.approx(np.asarray([[0.0, 0.0], [0.0, 0.36]]))


def test_correlated_gaussian_oracle_diverges_from_marginal_background_game() -> None:
    conditional = gaussian_linear_conditional_shapley(
        CORRELATED_GAUSSIAN,
        feature_order=FEATURES,
        observed={"x1": 1.0, "x2": 1.0},
        intercept=0.0,
        coefficients=(1.0, 0.0),
    )
    marginal = KernelSHAPAdapter().explain(
        lambda values: values["x1"],
        {"x1": 1.0, "x2": 1.0},
        ExplanationContext(
            feature_names=FEATURES,
            output_scale="score",
            perturbation_distribution="marginal_interventional",
            feature_dependence_policy="marginal_interventional",
            params={"background_rows": [{"x1": 0.0, "x2": 0.0}]},
        ),
    )

    assert conditional.values == pytest.approx({"x1": 0.6, "x2": 0.4})
    assert marginal.attributions == pytest.approx({"x1": 1.0, "x2": 0.0})
    assert conditional.values != pytest.approx(marginal.attributions)


def test_independent_gaussian_control_matches_marginal_attributions() -> None:
    independent = GaussianJointLaw(
        mean=(0.0, 0.0),
        covariance=((1.0, 0.0), (0.0, 1.0)),
    )
    result = gaussian_linear_conditional_shapley(
        independent,
        feature_order=FEATURES,
        observed={"x1": 1.0, "x2": 1.0},
        intercept=0.0,
        coefficients=(1.0, 0.0),
    )

    assert result.values == pytest.approx({"x1": 1.0, "x2": 0.0})


def test_gaussian_profile_rejects_asymmetric_indefinite_and_off_support_inputs() -> None:
    asymmetric = GaussianJointLaw(
        mean=(0.0, 0.0),
        covariance=((1.0, 0.4), (0.3, 1.0)),
    )
    indefinite = GaussianJointLaw(
        mean=(0.0, 0.0),
        covariance=((1.0, 2.0), (2.0, 1.0)),
    )
    singular = GaussianJointLaw(
        mean=(0.0, 0.0),
        covariance=((1.0, 1.0), (1.0, 1.0)),
    )

    with pytest.raises(ValueError, match="symmetric"):
        gaussian_conditional_moments(
            asymmetric,
            feature_order=FEATURES,
            coalition=frozenset({"x1"}),
            observed={"x1": 0.0, "x2": 0.0},
        )
    with pytest.raises(ValueError, match="positive semidefinite"):
        gaussian_conditional_moments(
            indefinite,
            feature_order=FEATURES,
            coalition=frozenset(),
            observed={"x1": 0.0, "x2": 0.0},
        )
    on_support = gaussian_conditional_moments(
        singular,
        feature_order=FEATURES,
        coalition=frozenset({"x1"}),
        observed={"x1": 0.7, "x2": 0.7},
    )
    assert np.asarray(on_support.covariance) == pytest.approx(np.zeros((2, 2)))
    with pytest.raises(ValueError, match="outside the singular Gaussian support"):
        gaussian_conditional_moments(
            singular,
            feature_order=FEATURES,
            coalition=frozenset(FEATURES),
            observed={"x1": 0.7, "x2": -0.7},
        )


def test_weighted_finite_support_uses_exact_matching_strata_and_admitted_weights() -> None:
    law = WeightedFiniteSupportLaw(
        rows=((0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (1.0, 1.0)),
        weights=(1.0, 3.0, 2.0, 4.0),
    )

    def model(values: dict[str, float]) -> float:
        return values["x1"]

    conditional_mean = finite_support_conditional_expectation(
        law,
        feature_order=FEATURES,
        coalition=frozenset({"x2"}),
        observed={"x1": 1.0, "x2": 1.0},
        model=model,
    )
    result = finite_support_conditional_shapley(
        law,
        feature_order=FEATURES,
        observed={"x1": 1.0, "x2": 1.0},
        model=model,
    )

    assert conditional_mean == pytest.approx(4.0 / 7.0)
    assert result.values == pytest.approx({"x1": 0.4142857142857143, "x2": -0.01428571428571429})
    assert result.exact


def test_weighted_finite_support_rejects_empty_exact_stratum() -> None:
    law = WeightedFiniteSupportLaw(rows=((0.0, 0.0),), weights=(1.0,))

    with pytest.raises(ValueError, match="stratum is empty"):
        finite_support_conditional_expectation(
            law,
            feature_order=FEATURES,
            coalition=frozenset({"x1"}),
            observed={"x1": 2.0, "x2": 0.0},
            model=lambda values: values["x1"],
        )


def test_fixed_n_plan_freezes_familywise_union_budget_and_reports_cap_shortfall() -> None:
    exact_budget = fixed_n_hoeffding_plan(
        feature_count=2,
        output_range=(0.0, 1.0),
        target_shapley_error=0.05,
        familywise_delta=0.05,
        random_seed=19,
        draw_cap_per_coalition=10_000,
    )
    capped = fixed_n_hoeffding_plan(
        feature_count=2,
        output_range=(0.0, 1.0),
        target_shapley_error=0.05,
        familywise_delta=0.05,
        random_seed=19,
        draw_cap_per_coalition=exact_budget.required_draws_per_coalition - 1,
    )

    assert exact_budget.coalition_count == 4
    assert exact_budget.epsilon_per_coalition == pytest.approx(0.025)
    assert exact_budget.required_draws_per_coalition == 4061
    assert exact_budget.draws_per_coalition == 4061
    assert exact_budget.precision_met
    assert capped.draws_per_coalition == 4060
    assert not capped.precision_met
    assert capped.achieved_shapley_error > 0.05
    assert capped.random_seed == 19


def test_bounded_nonlinear_conditional_result_carries_interval_and_rejects_fake_bound() -> None:
    plan = fixed_n_hoeffding_plan(
        feature_count=2,
        output_range=(-1.0, 1.0),
        target_shapley_error=1.0,
        familywise_delta=0.5,
        random_seed=7,
        draw_cap_per_coalition=100,
    )
    result = gaussian_bounded_conditional_shapley(
        lambda values: float(np.tanh(values["x1"] + values["x2"])),
        CORRELATED_GAUSSIAN,
        feature_order=FEATURES,
        observed={"x1": 0.0, "x2": 0.0},
        output_range=(-1.0, 1.0),
        plan=plan,
    )

    assert not result.exact
    assert result.coalition_count == 4
    assert set(result.intervals) == set(FEATURES)
    assert all(
        lower <= result.values[name] <= upper for name, (lower, upper) in result.intervals.items()
    )
    with pytest.raises(ValueError, match="escaped its verified structural bounds"):
        gaussian_bounded_conditional_shapley(
            lambda values: 2.0,
            CORRELATED_GAUSSIAN,
            feature_order=FEATURES,
            observed={"x1": 0.0, "x2": 0.0},
            output_range=(-1.0, 1.0),
            plan=plan,
        )


@dataclass(frozen=True)
class _FixtureLawResolver:
    resolved: ResolvedConditionalLaw

    def resolve(self, law_ref: str) -> ResolvedConditionalLaw | None:
        return self.resolved if law_ref == self.resolved.binding.law_ref else None


@dataclass(frozen=True)
class _FixtureAffineProfileResolver:
    profile: VerifiedAffineModelProfile

    def resolve_affine_profile(
        self,
        model: ScalarModel,
        *,
        model_hash: str,
        model_epoch: str,
        feature_order: tuple[str, ...],
    ) -> VerifiedAffineModelProfile | None:
        del model
        if (
            self.profile.model_hash == model_hash
            and self.profile.model_epoch == model_epoch
            and self.profile.feature_order == feature_order
        ):
            return self.profile
        return None


def _binding() -> ConditionalLawBinding:
    return ConditionalLawBinding(
        law_ref="law://fixture/joint-1",
        content_digest="sha256:fixture-law-content",
        authority_purpose="prediction_attribution",
        model_hash="sha256:fixture-model",
        population_ref="population://fixture",
        cohort_ref="cohort://fixture",
        observation_window_ref="time-window://fixture",
        feature_schema_version="features-v1",
        model_epoch="model-epoch-1",
        feature_order=FEATURES,
        support_ref="support://fixture",
        provenance_ref="producer://fixture",
        verifier_ref="verifier://fixture-law",
    )


def _conditional_context() -> ExplanationContext:
    binding = _binding()
    return ExplanationContext(
        feature_names=FEATURES,
        output_scale="score",
        perturbation_distribution="conditional",
        feature_dependence_policy="conditional_observational",
        random_seed=7,
        params={
            "conditional_law_ref": binding.law_ref,
            "model_hash": binding.model_hash,
            "population_ref": binding.population_ref,
            "cohort_ref": binding.cohort_ref,
            "observation_window_ref": binding.observation_window_ref,
            "feature_schema_version": binding.feature_schema_version,
            "model_epoch": binding.model_epoch,
        },
    )


def test_conditional_adapter_requires_independent_law_resolution() -> None:
    adapter = ConditionalSHAPAdapter()

    with pytest.raises(AdapterUnavailableError, match="resolver is unavailable"):
        adapter.explain(
            lambda values: values["x1"],
            {"x1": 1.0, "x2": 1.0},
            _conditional_context(),
        )


def test_resolved_gaussian_profile_produces_bound_conditional_bundle_without_authority_claim() -> (
    None
):
    binding = _binding()
    resolved = ResolvedConditionalLaw(binding=binding, law=CORRELATED_GAUSSIAN)
    profile = VerifiedAffineModelProfile(
        profile_ref="model-profile://fixture/affine",
        content_digest="sha256:fixture-affine-profile",
        verifier_ref="verifier://fixture-model",
        model_hash=binding.model_hash,
        model_epoch=binding.model_epoch,
        feature_order=FEATURES,
        intercept=0.0,
        coefficients=(1.0, 0.0),
    )
    adapter = ConditionalSHAPAdapter(
        law_resolver=_FixtureLawResolver(resolved),
        affine_profile_resolver=_FixtureAffineProfileResolver(profile),
    )

    def model(values: dict[str, float]) -> float:
        return values["x1"]

    raw = adapter.explain(
        model,
        {"x1": 1.0, "x2": 1.0},
        _conditional_context(),
    )

    assert raw.attributions == pytest.approx({"x1": 0.6, "x2": 0.4})
    assert raw.effective_method_id == "conditional_shapley"
    assert raw.conditional_evidence["law_content_digest"] == binding.content_digest
    assert raw.conditional_evidence["feature_order"] == list(FEATURES)
    assert raw.assumptions["causal_claim_made"] is False


def test_service_bundle_round_trips_before_both_consumers_fail_closed(
    tmp_path,
) -> None:
    binding = _binding()
    resolved = ResolvedConditionalLaw(binding=binding, law=CORRELATED_GAUSSIAN)
    profile = VerifiedAffineModelProfile(
        profile_ref="model-profile://fixture/affine",
        content_digest="sha256:fixture-affine-profile",
        verifier_ref="verifier://fixture-model",
        model_hash=binding.model_hash,
        model_epoch=binding.model_epoch,
        feature_order=FEATURES,
        intercept=0.0,
        coefficients=(1.0, 0.0),
    )
    request = ExplanationRequest(
        prediction_id="prediction-conditional-1",
        row_id="row-conditional-1",
        x={"x1": 1.0, "x2": 1.0},
        feature_names=FEATURES,
        methods=("kernel_shap_conditional",),
        feature_dependence_policy="conditional_observational",
        model_hash=binding.model_hash,
        feature_schema_version=binding.feature_schema_version,
        conditional_law_ref=binding.law_ref,
        population_ref=binding.population_ref,
        cohort_ref=binding.cohort_ref,
        observation_window_ref=binding.observation_window_ref,
        model_epoch=binding.model_epoch,
        n_eval_perturbations=1,
        random_seed=7,
        include_redundancy=False,
    )
    bundle = ExplanationOrchestrator(
        conditional_law_resolver=_FixtureLawResolver(resolved),
        affine_model_profile_resolver=_FixtureAffineProfileResolver(profile),
    ).explain(lambda values: values["x1"], request)

    method = bundle.methods[0]
    assert method.attributions[0].value == pytest.approx(0.6)
    assert method.attributions[1].value == pytest.approx(0.4)
    assert method.conditional_evidence is not None
    assert binding.law_ref in bundle.audit.artifact_refs
    assert bundle.display_policy == "diagnostic_only"
    assert "conditional_law_verifier_unavailable" in str(bundle.analyst_warning)

    artifact_path = tmp_path / "conditional-explanation-bundle.json"
    artifact_path.write_text(
        json.dumps(bundle.model_dump(mode="json"), sort_keys=True),
        encoding="utf-8",
    )
    serialized = json.loads(artifact_path.read_text(encoding="utf-8"))
    persisted = validate_persisted_explanation_bundle(serialized)
    runtime_result, runtime_issues = _validate_bundle_record(
        serialized,
        thresholds={},
        evidence_ref="evidence://conditional-fixture",
    )
    phase5_result = _run_berl_validation(serialized)

    assert persisted.methods[0].conditional_evidence is not None
    assert runtime_result["threshold_decision"]["status"] == "fail"
    assert any("conditional_law_verifier_unavailable" in issue.message for issue in runtime_issues)
    assert phase5_result["passed"] is False
    assert "conditional_law_verifier_unavailable" in " ".join(phase5_result["violations"])


def test_law_binding_mismatch_is_rejected_even_with_test_resolver_markers() -> None:
    binding = replace(_binding(), population_ref="population://other")
    resolved = ResolvedConditionalLaw(binding=binding, law=CORRELATED_GAUSSIAN)
    adapter = ConditionalSHAPAdapter(law_resolver=_FixtureLawResolver(resolved))

    with pytest.raises(AdapterUnavailableError, match="population_ref"):
        adapter.explain(
            lambda values: values["x1"],
            {"x1": 1.0, "x2": 1.0},
            _conditional_context(),
        )
