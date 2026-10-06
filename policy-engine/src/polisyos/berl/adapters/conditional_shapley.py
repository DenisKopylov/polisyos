"""Law-bound conditional Shapley candidate profiles for BERL.

This module implements the mathematical profiles and typed integration boundaries,
but it does not implement a population-law producer or admit source/model verifiers.
Injected resolver and verifier protocols can support diagnostic candidates only; the
persisted consumers keep conditional claims fail-closed until an admitted owner exists.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import combinations
from typing import Protocol

import numpy as np

from polisyos.berl.adapters._coalition import exact_shapley_attributions
from polisyos.berl.adapters.protocol import (
    AdapterUnavailableError,
    AssumptionReport,
    ExplanationContext,
    RawExplanation,
    ScalarModel,
    UncertaintyReport,
)

_GAUSSIAN_SUPPORT_TOLERANCE = 1.0e-10


@dataclass(frozen=True, slots=True)
class ConditionalLawBinding:
    """Source-owner binding required to resolve a conditional joint law."""

    law_ref: str
    content_digest: str
    authority_purpose: str
    model_hash: str
    population_ref: str
    cohort_ref: str
    observation_window_ref: str
    feature_schema_version: str
    model_epoch: str
    feature_order: tuple[str, ...]
    support_ref: str
    provenance_ref: str
    verifier_ref: str


@dataclass(frozen=True, slots=True)
class GaussianJointLaw:
    """A declared multivariate Gaussian joint law in feature-order coordinates."""

    mean: tuple[float, ...]
    covariance: tuple[tuple[float, ...], ...]


@dataclass(frozen=True, slots=True)
class WeightedFiniteSupportLaw:
    """A finite joint support with one admitted nonnegative weight per row."""

    rows: tuple[tuple[float, ...], ...]
    weights: tuple[float, ...]


ConditionalJointLaw = GaussianJointLaw | WeightedFiniteSupportLaw


@dataclass(frozen=True, slots=True)
class ResolvedConditionalLaw:
    """Candidate law content returned by an injected resolver."""

    binding: ConditionalLawBinding
    law: ConditionalJointLaw


class ConditionalLawResolver(Protocol):
    """Describe a candidate law resolver's required source/model binding.

    An implementation must load the referenced artifact, recompute its content digest,
    verify its producer provenance, and check the model/population/cohort/time/order/
    schema/epoch/support bindings. A caller-supplied label or covariance is not enough.
    This package does not admit implementations, so returned records remain candidates.
    """

    def resolve(self, law_ref: str) -> ResolvedConditionalLaw | None: ...


@dataclass(frozen=True, slots=True)
class VerifiedModelIdentity:
    """Candidate model identity response from an injected integration callback."""

    profile_ref: str
    content_digest: str
    verifier_ref: str


class ConditionalModelVerifier(Protocol):
    """Describe how an integration can resolve the model bound by a conditional law.

    The protocol's return value is not accepted as authority by persisted consumers.
    """

    def verify_model(
        self,
        model: ScalarModel,
        *,
        model_hash: str,
        model_epoch: str,
    ) -> VerifiedModelIdentity | None: ...


@dataclass(frozen=True, slots=True)
class VerifiedAffineModelProfile:
    """Candidate affine profile returned by an injected model-profile resolver."""

    profile_ref: str
    content_digest: str
    verifier_ref: str
    model_hash: str
    model_epoch: str
    feature_order: tuple[str, ...]
    intercept: float
    coefficients: tuple[float, ...]


class AffineModelProfileResolver(Protocol):
    """Describe an integration that resolves a model-bound affine candidate profile."""

    def resolve_affine_profile(
        self,
        model: ScalarModel,
        *,
        model_hash: str,
        model_epoch: str,
        feature_order: tuple[str, ...],
    ) -> VerifiedAffineModelProfile | None: ...


@dataclass(frozen=True, slots=True)
class VerifiedOutputBounds:
    """Candidate structural output interval returned by an injected callback."""

    lower: float
    upper: float
    profile_ref: str
    content_digest: str
    verifier_ref: str
    model_hash: str
    model_epoch: str


class BoundedOutputProfileVerifier(Protocol):
    """Describe a global bound resolver; its callback claim is not admitted authority."""

    def verify_output_bounds(
        self,
        model: ScalarModel,
        *,
        model_hash: str,
        model_epoch: str,
        feature_order: tuple[str, ...],
    ) -> VerifiedOutputBounds | None: ...


@dataclass(frozen=True, slots=True)
class ConditionalGaussianMoments:
    """Conditional mean and covariance in the original feature order."""

    mean: tuple[float, ...]
    covariance: tuple[tuple[float, ...], ...]


@dataclass(frozen=True, slots=True)
class HoeffdingCoalitionPlan:
    """Frozen familywise fixed-N plan for bounded conditional expectations."""

    coalition_count: int
    epsilon_per_coalition: float
    familywise_delta: float
    required_draws_per_coalition: int
    draws_per_coalition: int
    draw_cap_per_coalition: int
    random_seed: int
    achieved_shapley_error: float
    precision_met: bool


@dataclass(frozen=True, slots=True)
class ConditionalShapleyResult:
    values: Mapping[str, float]
    intervals: Mapping[str, tuple[float, float]]
    coalition_count: int
    exact: bool


@dataclass(frozen=True, slots=True)
class ConditionalSHAPAdapter:
    """Execute diagnostic conditional Shapley candidates over injected profiles.

    Gaussian laws use an affine-profile candidate for exact coalition expectations or
    a bounded-profile candidate and fixed-N IID draws for nonlinear functions.
    Weighted finite-support laws use exact matching strata and weighted conditional
    means. Candidate callbacks do not establish source authority; persisted consumers
    reject conditional claims until an owner-admitted verification path exists.
    """

    method_id: str = "kernel_shap_conditional"
    max_exact_features: int = 10
    law_resolver: ConditionalLawResolver | None = field(default=None, repr=False, compare=False)
    model_verifier: ConditionalModelVerifier | None = field(default=None, repr=False, compare=False)
    affine_profile_resolver: AffineModelProfileResolver | None = field(
        default=None, repr=False, compare=False
    )
    output_bounds_verifier: BoundedOutputProfileVerifier | None = field(
        default=None, repr=False, compare=False
    )

    @property
    def effective_method_id(self) -> str:
        """Return the implementation identity shared by conditional law profiles."""

        return "conditional_shapley"

    def explain(
        self,
        model: ScalarModel,
        x: Mapping[str, float],
        context: ExplanationContext,
    ) -> RawExplanation:
        """Compute the declared conditional Shapley profile or refuse unsupported input."""

        if context.feature_dependence_policy != "conditional_observational":
            raise ValueError("ConditionalSHAPAdapter requires conditional_observational semantics")
        feature_order = context.feature_names
        if len(feature_order) > self.max_exact_features:
            raise ValueError(
                "exact conditional Shapley is exponential; reduce features or set "
                "max_exact_shap_features"
            )
        if len(set(feature_order)) != len(feature_order):
            raise ValueError("conditional Shapley feature order must be unique")
        if self.law_resolver is None:
            raise AdapterUnavailableError(
                "conditional law producer/resolver is unavailable; no marginal fallback"
            )
        law_ref = _required_context_text(context, "conditional_law_ref")
        resolved = self.law_resolver.resolve(law_ref)
        if resolved is None:
            raise AdapterUnavailableError(
                "conditional law reference did not resolve to an admitted joint law"
            )
        _validate_law_binding(resolved.binding, context)
        model_hash = _required_context_text(context, "model_hash")
        model_epoch = _required_context_text(context, "model_epoch")
        observed = _ordered_observation(x, feature_order)

        if isinstance(resolved.law, WeightedFiniteSupportLaw):
            return self._explain_finite_support(
                model,
                resolved,
                observed=observed,
                feature_order=feature_order,
                model_hash=model_hash,
                model_epoch=model_epoch,
            )

        if self.affine_profile_resolver is not None:
            affine_profile = self.affine_profile_resolver.resolve_affine_profile(
                model,
                model_hash=model_hash,
                model_epoch=model_epoch,
                feature_order=feature_order,
            )
            if affine_profile is not None:
                return self._explain_gaussian_affine(
                    resolved,
                    affine_profile,
                    observed=observed,
                    feature_order=feature_order,
                )

        if self.output_bounds_verifier is not None:
            verified_bounds = self.output_bounds_verifier.verify_output_bounds(
                model,
                model_hash=model_hash,
                model_epoch=model_epoch,
                feature_order=feature_order,
            )
            if verified_bounds is not None:
                return self._explain_gaussian_bounded(
                    model,
                    resolved,
                    verified_bounds,
                    observed=observed,
                    feature_order=feature_order,
                    context=context,
                )
        raise AdapterUnavailableError(
            "conditional Gaussian law resolved but no verified affine or bounded "
            "model profile is available"
        )

    def _explain_finite_support(
        self,
        model: ScalarModel,
        resolved: ResolvedConditionalLaw,
        *,
        observed: Mapping[str, float],
        feature_order: tuple[str, ...],
        model_hash: str,
        model_epoch: str,
    ) -> RawExplanation:
        if self.model_verifier is None:
            raise AdapterUnavailableError(
                "finite-support conditional law resolved but model verifier is unavailable"
            )
        identity = self.model_verifier.verify_model(
            model,
            model_hash=model_hash,
            model_epoch=model_epoch,
        )
        if identity is None or not all(
            (identity.profile_ref, identity.content_digest, identity.verifier_ref)
        ):
            raise AdapterUnavailableError("conditional model identity could not be verified")
        law = resolved.law
        if not isinstance(law, WeightedFiniteSupportLaw):
            raise TypeError("finite-support profile requires WeightedFiniteSupportLaw")
        _validate_finite_support_law(law, feature_order)
        values_cache: dict[frozenset[str], float] = {}

        def value(coalition: frozenset[str]) -> float:
            if coalition not in values_cache:
                values_cache[coalition] = finite_support_conditional_expectation(
                    law,
                    feature_order=feature_order,
                    coalition=coalition,
                    observed=observed,
                    model=model,
                )
            return values_cache[coalition]

        attributions = exact_shapley_attributions(feature_order, value)
        evidence = _conditional_evidence_payload(
            resolved.binding,
            profile_id="finite_support_weighted_exact",
            model_profile_ref=identity.profile_ref,
            model_profile_digest=identity.content_digest,
            model_verifier_ref=identity.verifier_ref,
            feature_order=feature_order,
            precision_status="exact",
            coalition_count=2 ** len(feature_order),
        )
        return RawExplanation(
            method_id=self.method_id,
            attributions=attributions,
            params={
                "conditional_profile": "finite_support_weighted_exact",
                "coalition_count": 2 ** len(feature_order),
                "exact_enumeration": True,
            },
            assumptions={
                "feature_dependence_policy": "conditional_observational",
                "conditional_law_ref": resolved.binding.law_ref,
                "causal_claim_made": False,
            },
            requested_method_id=self.method_id,
            effective_method_id=self.effective_method_id,
            conditional_evidence=evidence,
        )

    def _explain_gaussian_affine(
        self,
        resolved: ResolvedConditionalLaw,
        profile: VerifiedAffineModelProfile,
        *,
        observed: Mapping[str, float],
        feature_order: tuple[str, ...],
    ) -> RawExplanation:
        law = resolved.law
        if not isinstance(law, GaussianJointLaw):
            raise TypeError("Gaussian affine profile requires GaussianJointLaw")
        _validate_affine_profile(
            profile,
            binding=resolved.binding,
            feature_order=feature_order,
        )
        attribution_result = gaussian_linear_conditional_shapley(
            law,
            feature_order=feature_order,
            observed=observed,
            intercept=profile.intercept,
            coefficients=profile.coefficients,
        )
        evidence = _conditional_evidence_payload(
            resolved.binding,
            profile_id="gaussian_linear_exact",
            model_profile_ref=profile.profile_ref,
            model_profile_digest=profile.content_digest,
            model_verifier_ref=profile.verifier_ref,
            feature_order=feature_order,
            precision_status="exact",
            coalition_count=2 ** len(feature_order),
        )
        return RawExplanation(
            method_id=self.method_id,
            attributions=dict(attribution_result.values),
            params={
                "conditional_profile": "gaussian_linear_exact",
                "coalition_count": attribution_result.coalition_count,
                "exact_enumeration": True,
            },
            assumptions={
                "feature_dependence_policy": "conditional_observational",
                "conditional_law_ref": resolved.binding.law_ref,
                "causal_claim_made": False,
            },
            requested_method_id=self.method_id,
            effective_method_id=self.effective_method_id,
            conditional_evidence=evidence,
        )

    def _explain_gaussian_bounded(
        self,
        model: ScalarModel,
        resolved: ResolvedConditionalLaw,
        bounds: VerifiedOutputBounds,
        *,
        observed: Mapping[str, float],
        feature_order: tuple[str, ...],
        context: ExplanationContext,
    ) -> RawExplanation:
        law = resolved.law
        if not isinstance(law, GaussianJointLaw):
            raise TypeError("bounded Gaussian profile requires GaussianJointLaw")
        model_hash = resolved.binding.model_hash
        if bounds.model_hash != model_hash or bounds.model_epoch != resolved.binding.model_epoch:
            raise AdapterUnavailableError("verified output bounds do not match model epoch")
        if not all((bounds.profile_ref, bounds.content_digest, bounds.verifier_ref)):
            raise AdapterUnavailableError("verified output bound is missing source provenance")
        if not math.isfinite(bounds.lower) or not math.isfinite(bounds.upper):
            raise ValueError("verified model output bounds must be finite")
        if bounds.lower > bounds.upper:
            raise ValueError("verified model output bounds are reversed")
        target_error = _required_context_number(context, "conditional_shapley_tolerance")
        familywise_delta = _required_context_number(context, "conditional_familywise_delta")
        draw_cap = _required_context_integer(context, "conditional_draw_cap_per_coalition")
        if context.random_seed is None:
            raise AdapterUnavailableError("conditional bounded profile requires a frozen seed")
        plan = fixed_n_hoeffding_plan(
            feature_count=len(feature_order),
            output_range=(bounds.lower, bounds.upper),
            target_shapley_error=target_error,
            familywise_delta=familywise_delta,
            random_seed=context.random_seed,
            draw_cap_per_coalition=draw_cap,
        )
        interval_result = gaussian_bounded_conditional_shapley(
            model,
            law,
            feature_order=feature_order,
            observed=observed,
            output_range=(bounds.lower, bounds.upper),
            plan=plan,
        )
        # No source-owned model-bound verifier is admitted in this slice. Keep the
        # fixed-N result candidate-only even when its arithmetic target was reached.
        precision_status = "precision_not_met"
        evidence = _conditional_evidence_payload(
            resolved.binding,
            profile_id="gaussian_bounded_hoeffding",
            model_profile_ref=bounds.profile_ref,
            model_profile_digest=bounds.content_digest,
            model_verifier_ref=bounds.verifier_ref,
            feature_order=feature_order,
            precision_status=precision_status,
            draw_count_per_coalition=plan.draws_per_coalition,
            coalition_count=plan.coalition_count,
            epsilon_per_coalition=plan.epsilon_per_coalition,
            familywise_delta=plan.familywise_delta,
            random_seed=plan.random_seed,
            draw_cap_per_coalition=plan.draw_cap_per_coalition,
            achieved_shapley_error=plan.achieved_shapley_error,
        )
        return RawExplanation(
            method_id=self.method_id,
            attributions=dict(interval_result.values),
            params={
                "conditional_profile": "gaussian_bounded_hoeffding",
                "coalition_count": plan.coalition_count,
                "draw_count_per_coalition": plan.draws_per_coalition,
                "required_draws_per_coalition": plan.required_draws_per_coalition,
                "draw_cap_per_coalition": plan.draw_cap_per_coalition,
                "epsilon_per_coalition": plan.epsilon_per_coalition,
                "familywise_delta": plan.familywise_delta,
                "achieved_shapley_error": plan.achieved_shapley_error,
                "random_seed": plan.random_seed,
                "precision_status": precision_status,
            },
            assumptions={
                "feature_dependence_policy": "conditional_observational",
                "conditional_law_ref": resolved.binding.law_ref,
                "causal_claim_made": False,
            },
            estimator_uncertainty={
                "confidence_intervals": {
                    name: [interval[0], interval[1]]
                    for name, interval in interval_result.intervals.items()
                },
                "diagnostic": "candidate_only_unadmitted_output_bound",
            },
            requested_method_id=self.method_id,
            effective_method_id=self.effective_method_id,
            conditional_evidence=evidence,
        )

    def reconstruct_delta(
        self,
        explanation: RawExplanation,
        perturbation: Mapping[str, float],
    ) -> float:
        """Return the additive local reconstruction used by BERL held-out checks."""

        return sum(
            float(value) * float(perturbation.get(feature, 0.0))
            for feature, value in explanation.attributions.items()
        )

    def estimator_uncertainty(self, explanation: RawExplanation) -> UncertaintyReport:
        """Expose simultaneous fixed-N coalition intervals when present."""

        raw_intervals = explanation.estimator_uncertainty.get("confidence_intervals", {})
        intervals: dict[str, tuple[float, float]] = {}
        if isinstance(raw_intervals, Mapping):
            for feature, interval in raw_intervals.items():
                if (
                    isinstance(interval, Sequence)
                    and not isinstance(interval, str | bytes)
                    and len(interval) == 2
                ):
                    intervals[str(feature)] = (float(interval[0]), float(interval[1]))
        return UncertaintyReport(
            confidence_intervals=intervals,
            diagnostic=str(
                explanation.estimator_uncertainty.get("diagnostic", "exact_conditional_profile")
            ),
        )

    def assumptions(self, context: ExplanationContext) -> AssumptionReport:
        """Return the method's conditional prediction-attribution assumptions."""

        return AssumptionReport(
            output_scale=context.output_scale,
            perturbation_distribution=context.perturbation_distribution,
            feature_dependence_policy="conditional_observational",
            causal_claim_made=False,
            notes=("conditional prediction attribution, not a causal intervention",),
        )


def gaussian_conditional_moments(
    law: GaussianJointLaw,
    *,
    feature_order: tuple[str, ...],
    coalition: frozenset[str],
    observed: Mapping[str, float],
    support_tolerance: float = _GAUSSIAN_SUPPORT_TOLERANCE,
) -> ConditionalGaussianMoments:
    """Compute Gaussian conditional moments using a PSD pseudoinverse without jitter.

    Singular observed covariance is handled by a Moore-Penrose pseudoinverse. An
    observation outside its affine support is rejected; no diagonal jitter is added.
    """

    mean, covariance = _validated_gaussian(law, feature_order)
    unknown_features = coalition.difference(feature_order)
    if unknown_features:
        raise ValueError(f"coalition contains unknown features: {sorted(unknown_features)}")
    if not math.isfinite(support_tolerance) or support_tolerance <= 0.0:
        raise ValueError("support tolerance must be finite and positive")
    index = {feature: position for position, feature in enumerate(feature_order)}
    observed_indices = tuple(index[name] for name in feature_order if name in coalition)
    missing_indices = tuple(index[name] for name in feature_order if name not in coalition)
    conditional_mean = mean.copy()
    conditional_covariance = np.zeros_like(covariance)
    if not observed_indices:
        conditional_mean = mean.copy()
        conditional_covariance = covariance.copy()
    else:
        x_s = np.asarray(
            [_finite_observed_value(observed, feature_order[i]) for i in observed_indices]
        )
        mu_s = mean[list(observed_indices)]
        sigma_ss = covariance[np.ix_(observed_indices, observed_indices)]
        eigenvalues = np.linalg.eigvalsh(sigma_ss)
        scale = max(1.0, float(np.max(np.abs(eigenvalues))))
        if float(np.min(eigenvalues)) < -support_tolerance * scale:
            raise ValueError("observed Gaussian covariance is not positive semidefinite")
        inverse = np.linalg.pinv(sigma_ss, hermitian=True)
        delta = x_s - mu_s
        supported_delta = sigma_ss @ inverse @ delta
        if np.linalg.norm(delta - supported_delta) > support_tolerance * (
            1.0 + float(np.linalg.norm(delta))
        ):
            raise ValueError("observed values lie outside the singular Gaussian support")
        conditional_mean[list(observed_indices)] = x_s
        if missing_indices:
            sigma_us = covariance[np.ix_(missing_indices, observed_indices)]
            sigma_uu = covariance[np.ix_(missing_indices, missing_indices)]
            conditional_mean[list(missing_indices)] = mean[list(missing_indices)] + (
                sigma_us @ inverse @ delta
            )
            conditional_uu = sigma_uu - sigma_us @ inverse @ sigma_us.T
            conditional_uu = (conditional_uu + conditional_uu.T) / 2.0
            conditional_eigenvalues = np.linalg.eigvalsh(conditional_uu)
            conditional_scale = max(1.0, float(np.max(np.abs(conditional_eigenvalues))))
            if float(np.min(conditional_eigenvalues)) < -support_tolerance * conditional_scale:
                raise ValueError("computed conditional covariance is not positive semidefinite")
            conditional_covariance[np.ix_(missing_indices, missing_indices)] = conditional_uu
    return ConditionalGaussianMoments(
        mean=tuple(float(value) for value in conditional_mean),
        covariance=tuple(tuple(float(value) for value in row) for row in conditional_covariance),
    )


def gaussian_linear_conditional_shapley(
    law: GaussianJointLaw,
    *,
    feature_order: tuple[str, ...],
    observed: Mapping[str, float],
    intercept: float,
    coefficients: tuple[float, ...],
) -> ConditionalShapleyResult:
    """Compute exact Gaussian conditional Shapley values for an admitted affine model."""

    if len(coefficients) != len(feature_order):
        raise ValueError("affine coefficient count must match feature order")
    if not math.isfinite(intercept) or any(not math.isfinite(value) for value in coefficients):
        raise ValueError("affine model parameters must be finite")
    values_cache: dict[frozenset[str], float] = {}

    def value(coalition: frozenset[str]) -> float:
        if coalition not in values_cache:
            moments = gaussian_conditional_moments(
                law,
                feature_order=feature_order,
                coalition=coalition,
                observed=observed,
            )
            values_cache[coalition] = intercept + sum(
                coefficient * mean
                for coefficient, mean in zip(coefficients, moments.mean, strict=True)
            )
        return values_cache[coalition]

    attributions = exact_shapley_attributions(feature_order, value)
    return ConditionalShapleyResult(
        values=attributions,
        intervals={},
        coalition_count=2 ** len(feature_order),
        exact=True,
    )


def finite_support_conditional_expectation(
    law: WeightedFiniteSupportLaw,
    *,
    feature_order: tuple[str, ...],
    coalition: frozenset[str],
    observed: Mapping[str, float],
    model: ScalarModel,
) -> float:
    """Compute an exact weighted conditional expectation on a matched finite stratum."""

    _validate_finite_support_law(law, feature_order)
    unknown = coalition.difference(feature_order)
    if unknown:
        raise ValueError(f"coalition contains unknown features: {sorted(unknown)}")
    indices = tuple(i for i, name in enumerate(feature_order) if name in coalition)
    target = tuple(_finite_observed_value(observed, feature_order[i]) for i in indices)
    matched: list[tuple[tuple[float, ...], float]] = []
    for row, weight in zip(law.rows, law.weights, strict=True):
        if all(row[i] == value for i, value in zip(indices, target, strict=True)) and weight > 0.0:
            matched.append((row, weight))
    if not matched:
        raise ValueError("conditional finite-support stratum is empty or has zero weight")
    probabilities = _normalized_finite_support_weights(tuple(weight for _, weight in matched))
    weighted_outputs: list[float] = []
    for (row, _), probability in zip(matched, probabilities, strict=True):
        prediction = float(model(dict(zip(feature_order, row, strict=True))))
        if not math.isfinite(prediction):
            raise ValueError("model output on finite support must be finite")
        weighted_outputs.append(probability * prediction)
    return math.fsum(weighted_outputs)


def finite_support_conditional_shapley(
    law: WeightedFiniteSupportLaw,
    *,
    feature_order: tuple[str, ...],
    observed: Mapping[str, float],
    model: ScalarModel,
) -> ConditionalShapleyResult:
    """Compute exact Shapley values for a weighted finite-support conditional law."""

    values_cache: dict[frozenset[str], float] = {}

    def value(coalition: frozenset[str]) -> float:
        if coalition not in values_cache:
            values_cache[coalition] = finite_support_conditional_expectation(
                law,
                feature_order=feature_order,
                coalition=coalition,
                observed=observed,
                model=model,
            )
        return values_cache[coalition]

    attributions = exact_shapley_attributions(feature_order, value)
    return ConditionalShapleyResult(
        values=attributions,
        intervals={},
        coalition_count=2 ** len(feature_order),
        exact=True,
    )


def fixed_n_hoeffding_plan(
    *,
    feature_count: int,
    output_range: tuple[float, float],
    target_shapley_error: float,
    familywise_delta: float,
    random_seed: int,
    draw_cap_per_coalition: int,
) -> HoeffdingCoalitionPlan:
    """Freeze the simultaneous fixed-N Hoeffding budget before conditional draws.

    Coalition epsilon is half the requested per-attribution error because exact
    Shapley interval arithmetic can combine one positive and one negative coalition
    error. The familywise union covers all ``2**feature_count`` coalition values.
    """

    lower, upper = output_range
    if feature_count < 1:
        raise ValueError("feature count must be positive")
    if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
        raise ValueError("output bounds must be finite and ordered")
    if not math.isfinite(target_shapley_error) or target_shapley_error <= 0.0:
        raise ValueError("target Shapley error must be finite and positive")
    if not math.isfinite(familywise_delta) or not 0.0 < familywise_delta < 1.0:
        raise ValueError("familywise delta must be in (0, 1)")
    if draw_cap_per_coalition < 1:
        raise ValueError("draw cap per coalition must be positive")
    coalition_count = 2**feature_count
    epsilon = target_shapley_error / 2.0
    output_width = upper - lower
    if not math.isfinite(output_width):
        raise ValueError("output range width must be finite")
    if output_width == 0.0:
        required_draws = 0
        draws = 0
        achieved_error = 0.0
    else:
        required_draws = math.ceil(
            (output_width**2)
            * math.log(2.0 * coalition_count / familywise_delta)
            / (2.0 * epsilon**2)
        )
        draws = min(required_draws, draw_cap_per_coalition)
        achieved_epsilon = output_width * math.sqrt(
            math.log(2.0 * coalition_count / familywise_delta) / (2.0 * draws)
        )
        achieved_error = 2.0 * achieved_epsilon
    return HoeffdingCoalitionPlan(
        coalition_count=coalition_count,
        epsilon_per_coalition=epsilon,
        familywise_delta=familywise_delta,
        required_draws_per_coalition=required_draws,
        draws_per_coalition=draws,
        draw_cap_per_coalition=draw_cap_per_coalition,
        random_seed=random_seed,
        achieved_shapley_error=achieved_error,
        precision_met=required_draws <= draw_cap_per_coalition,
    )


def gaussian_bounded_conditional_shapley(
    model: ScalarModel,
    law: GaussianJointLaw,
    *,
    feature_order: tuple[str, ...],
    observed: Mapping[str, float],
    output_range: tuple[float, float],
    plan: HoeffdingCoalitionPlan,
) -> ConditionalShapleyResult:
    """Estimate conditional Gaussian coalition means with frozen simultaneous bounds."""

    lower, upper = output_range
    expected_plan = fixed_n_hoeffding_plan(
        feature_count=len(feature_order),
        output_range=output_range,
        target_shapley_error=2.0 * plan.epsilon_per_coalition,
        familywise_delta=plan.familywise_delta,
        random_seed=plan.random_seed,
        draw_cap_per_coalition=plan.draw_cap_per_coalition,
    )
    if plan != expected_plan:
        raise ValueError("Hoeffding plan does not match its frozen inputs")
    achieved_epsilon = plan.achieved_shapley_error / 2.0
    rng = np.random.default_rng(plan.random_seed)
    coalition_intervals: dict[frozenset[str], tuple[float, float]] = {}
    for size in range(len(feature_order) + 1):
        for subset in combinations(feature_order, size):
            coalition = frozenset(subset)
            if upper == lower:
                mean = lower
            else:
                moments = gaussian_conditional_moments(
                    law,
                    feature_order=feature_order,
                    coalition=coalition,
                    observed=observed,
                )
                draws = _draw_from_conditional_gaussian(
                    moments,
                    count=plan.draws_per_coalition,
                    rng=rng,
                )
                outputs = [
                    float(model(dict(zip(feature_order, row, strict=True)))) for row in draws
                ]
                if any(not math.isfinite(value) for value in outputs):
                    raise ValueError("bounded model returned a non-finite value")
                if any(value < lower or value > upper for value in outputs):
                    raise ValueError("model output escaped its verified structural bounds")
                mean = sum(outputs) / len(outputs)
            coalition_intervals[coalition] = (
                max(lower, mean - achieved_epsilon),
                min(upper, mean + achieved_epsilon),
            )

    values: dict[str, float] = {}
    intervals: dict[str, tuple[float, float]] = {}
    feature_count = len(feature_order)
    factorial_n = math.factorial(feature_count)
    for feature in feature_order:
        others = tuple(name for name in feature_order if name != feature)
        interval_lower = 0.0
        interval_upper = 0.0
        for size in range(feature_count):
            weight = math.factorial(size) * math.factorial(feature_count - size - 1) / factorial_n
            for subset in combinations(others, size):
                coalition = frozenset(subset)
                with_feature = coalition | {feature}
                coalition_lower, coalition_upper = coalition_intervals[coalition]
                feature_lower, feature_upper = coalition_intervals[with_feature]
                interval_lower += weight * (feature_lower - coalition_upper)
                interval_upper += weight * (feature_upper - coalition_lower)
        intervals[feature] = (interval_lower, interval_upper)
        values[feature] = (interval_lower + interval_upper) / 2.0
    return ConditionalShapleyResult(
        values=values,
        intervals=intervals,
        coalition_count=plan.coalition_count,
        exact=False,
    )


def _draw_from_conditional_gaussian(
    moments: ConditionalGaussianMoments,
    *,
    count: int,
    rng: np.random.Generator,
) -> tuple[tuple[float, ...], ...]:
    if count < 1:
        raise ValueError("a nonconstant bounded profile requires at least one draw")
    mean = np.asarray(moments.mean, dtype=float)
    covariance = np.asarray(moments.covariance, dtype=float)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    scale = max(1.0, float(np.max(np.abs(eigenvalues))))
    if float(np.min(eigenvalues)) < -_GAUSSIAN_SUPPORT_TOLERANCE * scale:
        raise ValueError("conditional covariance is not positive semidefinite")
    # Clip only round-off-sized negative eigenvalues; do not add diagonal jitter.
    factor = eigenvectors @ np.diag(np.sqrt(np.maximum(eigenvalues, 0.0)))
    standard = rng.standard_normal((count, len(mean)))
    samples = mean + standard @ factor.T
    return tuple(tuple(float(value) for value in row) for row in samples)


def _validated_gaussian(
    law: GaussianJointLaw,
    feature_order: tuple[str, ...],
) -> tuple[np.ndarray, np.ndarray]:
    if len(set(feature_order)) != len(feature_order):
        raise ValueError("Gaussian feature order must be unique")
    mean = np.asarray(law.mean, dtype=float)
    covariance = np.asarray(law.covariance, dtype=float)
    expected_shape = (len(feature_order), len(feature_order))
    if mean.shape != (len(feature_order),) or covariance.shape != expected_shape:
        raise ValueError("Gaussian law dimensions do not match feature order")
    if not np.all(np.isfinite(mean)) or not np.all(np.isfinite(covariance)):
        raise ValueError("Gaussian law parameters must be finite")
    scale = max(1.0, float(np.max(np.abs(covariance))))
    if not np.allclose(
        covariance,
        covariance.T,
        rtol=0.0,
        atol=_GAUSSIAN_SUPPORT_TOLERANCE * scale,
    ):
        raise ValueError("Gaussian covariance must be symmetric")
    covariance = (covariance + covariance.T) / 2.0
    eigenvalues = np.linalg.eigvalsh(covariance)
    eigenvalue_scale = max(1.0, float(np.max(np.abs(eigenvalues))))
    if float(np.min(eigenvalues)) < -_GAUSSIAN_SUPPORT_TOLERANCE * eigenvalue_scale:
        raise ValueError("Gaussian covariance must be positive semidefinite")
    return mean, covariance


def _validate_finite_support_law(
    law: WeightedFiniteSupportLaw,
    feature_order: tuple[str, ...],
) -> None:
    if not law.rows or len(law.rows) != len(law.weights):
        raise ValueError("finite support requires one weight per nonempty row set")
    if not feature_order or len(set(feature_order)) != len(feature_order):
        raise ValueError("finite support requires a nonempty unique feature order")
    if any(len(row) != len(feature_order) for row in law.rows):
        raise ValueError("finite-support row dimensions do not match feature order")
    if any(not math.isfinite(value) for row in law.rows for value in row):
        raise ValueError("finite-support values must be finite")
    if any(not math.isfinite(weight) or weight < 0.0 for weight in law.weights):
        raise ValueError("finite-support weights must be finite and nonnegative")
    _normalized_finite_support_weights(law.weights)


def _normalized_finite_support_weights(weights: Sequence[float]) -> tuple[float, ...]:
    """Normalize finite nonnegative weights without overflowing their raw sum."""

    scale = max(weights, default=0.0)
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("finite-support weights must have positive total mass")
    scaled = tuple(weight / scale for weight in weights)
    total = math.fsum(scaled)
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("finite-support weights must have positive finite total mass")
    return tuple(weight / total for weight in scaled)


def _validate_law_binding(
    binding: ConditionalLawBinding,
    context: ExplanationContext,
) -> None:
    expected = {
        "law_ref": "conditional_law_ref",
        "model_hash": "model_hash",
        "population_ref": "population_ref",
        "cohort_ref": "cohort_ref",
        "observation_window_ref": "observation_window_ref",
        "feature_schema_version": "feature_schema_version",
        "model_epoch": "model_epoch",
    }
    for binding_name, context_name in expected.items():
        value = getattr(binding, binding_name)
        expected_value = context.params.get(context_name)
        if not isinstance(value, str) or not value:
            raise AdapterUnavailableError(f"conditional law binding is missing {binding_name}")
        if not isinstance(expected_value, str) or not expected_value:
            raise AdapterUnavailableError(f"request is missing conditional binding {context_name}")
        if value != expected_value:
            raise AdapterUnavailableError(f"conditional law binding mismatch for {binding_name}")
    if binding.authority_purpose != "prediction_attribution":
        raise AdapterUnavailableError(
            "conditional law authority purpose is not prediction attribution"
        )
    if binding.feature_order != context.feature_names:
        raise AdapterUnavailableError("conditional law feature order does not match request")
    if not all(
        (
            binding.content_digest,
            binding.support_ref,
            binding.provenance_ref,
            binding.verifier_ref,
        )
    ):
        raise AdapterUnavailableError(
            "conditional law is missing digest/support/provenance identity"
        )


def _validate_affine_profile(
    profile: VerifiedAffineModelProfile,
    *,
    binding: ConditionalLawBinding,
    feature_order: tuple[str, ...],
) -> None:
    if (
        profile.model_hash != binding.model_hash
        or profile.model_epoch != binding.model_epoch
        or profile.feature_order != feature_order
        or len(profile.coefficients) != len(feature_order)
        or not all((profile.profile_ref, profile.content_digest, profile.verifier_ref))
    ):
        raise AdapterUnavailableError("verified affine model profile does not match law binding")


def _conditional_evidence_payload(
    binding: ConditionalLawBinding,
    *,
    profile_id: str,
    model_profile_ref: str,
    model_profile_digest: str,
    model_verifier_ref: str,
    feature_order: tuple[str, ...],
    precision_status: str,
    draw_count_per_coalition: int | None = None,
    coalition_count: int | None = None,
    epsilon_per_coalition: float | None = None,
    familywise_delta: float | None = None,
    random_seed: int | None = None,
    draw_cap_per_coalition: int | None = None,
    achieved_shapley_error: float | None = None,
) -> dict[str, object]:
    return {
        "profile_id": profile_id,
        "authority_purpose": binding.authority_purpose,
        "law_ref": binding.law_ref,
        "law_content_digest": binding.content_digest,
        "model_hash": binding.model_hash,
        "model_profile_ref": model_profile_ref,
        "model_profile_digest": model_profile_digest,
        "model_verifier_ref": model_verifier_ref,
        "population_ref": binding.population_ref,
        "cohort_ref": binding.cohort_ref,
        "observation_window_ref": binding.observation_window_ref,
        "feature_schema_version": binding.feature_schema_version,
        "model_epoch": binding.model_epoch,
        "feature_order": list(feature_order),
        "support_ref": binding.support_ref,
        "provenance_ref": binding.provenance_ref,
        "verifier_ref": binding.verifier_ref,
        "precision_status": precision_status,
        "draw_count_per_coalition": draw_count_per_coalition,
        "coalition_count": coalition_count,
        "epsilon_per_coalition": epsilon_per_coalition,
        "familywise_delta": familywise_delta,
        "random_seed": random_seed,
        "draw_cap_per_coalition": draw_cap_per_coalition,
        "achieved_shapley_error": achieved_shapley_error,
    }


def _ordered_observation(
    observed: Mapping[str, float],
    feature_order: tuple[str, ...],
) -> dict[str, float]:
    result = {feature: _finite_observed_value(observed, feature) for feature in feature_order}
    if set(observed).difference(feature_order):
        raise ValueError("observed input contains features outside the admitted feature order")
    return result


def _finite_observed_value(observed: Mapping[str, float], feature: str) -> float:
    if feature not in observed:
        raise ValueError(f"observed input is missing feature {feature}")
    value = float(observed[feature])
    if not math.isfinite(value):
        raise ValueError(f"observed value for {feature} must be finite")
    return value


def _required_context_text(context: ExplanationContext, key: str) -> str:
    value = context.params.get(key)
    if not isinstance(value, str) or not value:
        raise AdapterUnavailableError(f"conditional request is missing {key}")
    return value


def _required_context_number(context: ExplanationContext, key: str) -> float:
    value = context.params.get(key)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise AdapterUnavailableError(f"conditional bounded profile requires numeric {key}")
    return float(value)


def _required_context_integer(context: ExplanationContext, key: str) -> int:
    value = context.params.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise AdapterUnavailableError(f"conditional bounded profile requires integer {key}")
    return value
