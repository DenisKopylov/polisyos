"""Run validity diagnostics such as placebo and parallel-trends checks."""
from __future__ import annotations

from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog._payloads import extract_model_payload
from polisyos.foundry.methods.catalog.causal.treatment_effects import _logistic_propensity
from polisyos.ir.analytics.estimand import SideConditionKind

from .protocols import PanelObservationalData


def _panel_payload(state: Any) -> dict[str, Any]:
    return extract_model_payload(
        state,
        model_cls=PanelObservationalData,
        nested_keys=("panel_data", "panel_observational_data"),
    )


@foundry_method(
    namespace="causal.diagnostics",
    version="1.0.0",
    tags={"causal", "diagnostics", "parallel-trends"},
)
class ParallelTrendsCheck:
    """Store pre-trend diagnostics for DiD designs under a no-differential-trends assumption."""
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("statsmodels", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="parallel_trends_check",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "outcome",
                    SlotType.MATRIX,
                    Unit("outcome", "value"),
                    shape=("n_units", "n_periods"),
                ),
                SlotSpec(
                    "treatment",
                    SlotType.VECTOR,
                    Unit("binary", "flag"),
                    shape=("n_units",),
                ),
                SlotSpec("time_treatment", SlotType.SCALAR, Unit("time", "index")),
            }
        ),
        output_slots=frozenset({SlotSpec("result", SlotType.SCALAR, Unit("diagnostic", "json"))}),
        parameters=(ParameterSpec(name="alpha", default=0.05),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Pre-treatment slope check for the DiD parallel trends assumption.",
        tags=frozenset({"causal", "diagnostics", "parallel-trends"}),
        when_to_use="Assess covariate balance after matching/weighting; check overlap; validate identification assumptions",
        citations=(
            "Angrist, J. & Pischke, J. (2009). Mostly Harmless Econometrics. Princeton University Press.",
        ),
        output_interpretation="Standardized mean differences < 0.1 = good balance. Propensity overlap plot: check common support.",
    )

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any],
        fallback_state: Any,
    ) -> PanelObservationalData:
        payload = _panel_payload(fallback_state)
        payload.update(bound_inputs)
        return PanelObservationalData.model_validate(payload)

    @staticmethod
    def pure_step(state: PanelObservationalData, params: Mapping[str, Any]) -> dict[str, Any]:
        import statsmodels.api as sm

        data = (
            state
            if isinstance(state, PanelObservationalData)
            else PanelObservationalData.model_validate(state)
        )
        if data.time_treatment < 2:
            raise ValueError("parallel_trends_check requires at least 2 pre-treatment periods")

        treated_mask = np.asarray(data.treatment, dtype=int) == 1
        control_mask = ~treated_mask
        if not treated_mask.any() or not control_mask.any():
            raise ValueError("parallel_trends_check requires treated and control units")

        pre_outcome = np.asarray(data.outcome[:, : data.time_treatment], dtype=float)
        treated_mean = np.mean(pre_outcome[treated_mask], axis=0)
        control_mean = np.mean(pre_outcome[control_mask], axis=0)
        diff = treated_mean - control_mean
        trend = np.arange(diff.shape[0], dtype=float)

        x = sm.add_constant(trend, has_constant="add")
        fit = sm.OLS(diff, x).fit()
        slope = float(fit.params[1])
        p_value = float(fit.pvalues[1])
        alpha = float(params.get("alpha", 0.05))

        return {
            "result": {
                "test_name": "parallel_trends_check",
                "statistic": float(fit.tvalues[1]),
                "p_value": p_value,
                "passed": bool(p_value >= alpha),
                "critical_value": alpha,
                "metadata": {
                    "pre_periods": int(diff.shape[0]),
                    "slope": slope,
                    "intercept": float(fit.params[0]),
                    "treated_mean_pre": treated_mean.tolist(),
                    "control_mean_pre": control_mean.tolist(),
                    "difference_series": diff.tolist(),
                    "r_squared": float(getattr(fit, "rsquared", 0.0)),
                },
            }
        }


@foundry_method(
    namespace="causal.diagnostics",
    version="1.0.0",
    tags={"causal", "diagnostics", "positivity", "overlap", "governance"},
)
class PositivityDiagnostic:
    """Positivity / overlap check for causal identification governance.

    Estimates propensity scores using logistic regression and evaluates whether
    the positivity assumption holds: 0 < P(T=1|X=x) < 1 for all x in the support.

    Reports:
    - passes_positivity: True when all propensity scores are within [min_threshold, 1-min_threshold]
    - ESS (Kish effective sample size) and ESS fraction
    - overlap score (fraction of obs with propensity in [0.1, 0.9])
    - n_trimmed: observations outside [trim_threshold, 1-trim_threshold]
    - actionable recommendations (governance gates)

    This method is a prerequisite for AIPW, TMLE, CrossFitOrchestrator, and
    DensityRatioEstimator — its result should be checked before running estimators.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="positivity_check",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("X", SlotType.MATRIX, Unit("covariate", "value"), shape=("n_obs", "n_features")),
                SlotSpec("treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)),
            }
        ),
        output_slots=frozenset(
            {SlotSpec("result", SlotType.SCALAR, Unit("diagnostic", "json"))}
        ),
        parameters=(
            ParameterSpec(
                name="min_threshold",
                default=0.01,
                description="Lower bound for valid propensity scores (and 1-bound for upper).",
            ),
            ParameterSpec(
                name="overlap_band",
                default=0.1,
                description="Overlap is scored as fraction of obs with propensity in [overlap_band, 1-overlap_band].",
            ),
            ParameterSpec(
                name="propensity_max_iter",
                default=100,
                description="Max IRLS iterations for logistic propensity model.",
            ),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Positivity / overlap diagnostic: estimates propensity scores and evaluates "
            "whether the positivity assumption holds for causal identification."
        ),
        tags=frozenset(
            {"causal", "diagnostics", "positivity", "overlap", "governance", "identification"}
        ),
        citations=(
            "Rosenbaum, P.R. & Rubin, D.B. (1983). The central role of the propensity score. Biometrika.",
            "Cole, S.R. & Hernán, M.A. (2008). Constructing inverse probability weights. AJPH.",
        ),
        equations={
            "ess": "ESS = (Σw)² / Σw²  where w_i = T_i/e_i + (1-T_i)/(1-e_i)",
            "overlap": "overlap_score = mean(min_threshold < e(x) < 1-min_threshold)",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Always run before AIPW, TMLE, CrossFitOrchestrator, or DensityRatioEstimator.",
        when_not_to_use="Not needed for instrumental variables or regression discontinuity designs.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=50,
        output_interpretation=(
            "passes_positivity=True: safe to proceed with IPW-based estimation. "
            "ESS fraction < 0.3: consider trimming or a different estimand. "
            "overlap_score < 0.5: severe positivity violation — estimation unreliable."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        X = np.asarray(state["X"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        n = len(T)

        min_threshold: float = float(params.get("min_threshold", 0.01))
        overlap_band: float = float(params.get("overlap_band", 0.1))
        propensity_max_iter: int = int(params.get("propensity_max_iter", 100))

        if X.ndim == 1:
            X = X[:, None]

        # Fit propensity model
        e = _logistic_propensity(X, T, max_iter=propensity_max_iter)

        # Positivity check
        passes_positivity = bool(
            np.all(e >= min_threshold) and np.all(e <= 1.0 - min_threshold)
        )

        min_e = float(np.min(e))
        max_e = float(np.max(e))

        # Trimmed count (outside [min_threshold, 1-min_threshold])
        n_trimmed = int(np.sum((e < min_threshold) | (e > 1.0 - min_threshold)))

        # Kish ESS using IPW weights
        w1 = np.where(T > 0.5, 1.0 / np.clip(e, min_threshold, 1.0 - min_threshold), 0.0)
        w0 = np.where(T <= 0.5, 1.0 / np.clip(1.0 - e, min_threshold, 1.0 - min_threshold), 0.0)
        w = w1 + w0
        w_sum = float(np.sum(w))
        w_sq_sum = float(np.sum(w ** 2))
        ess = float(w_sum ** 2 / max(w_sq_sum, 1e-12))
        ess_fraction = min(float(ess / n), 1.0)

        # Overlap score: fraction of obs with propensity in [overlap_band, 1-overlap_band]
        overlap_score = float(
            np.mean((e >= overlap_band) & (e <= 1.0 - overlap_band))
        )

        # Build actionable recommendations
        recommendations: list[str] = []
        side_conditions_violated: list[str] = []

        if not passes_positivity:
            recommendations.append(
                f"Positivity violated: {n_trimmed} obs have propensity outside "
                f"[{min_threshold:.3f}, {1 - min_threshold:.3f}]. "
                "Consider trimming, matching, or restricting the covariate space."
            )
            side_conditions_violated.append(SideConditionKind.POSITIVITY.value)

        if ess_fraction < 0.3:
            recommendations.append(
                f"ESS fraction is low ({ess_fraction:.2f}): effective sample size = {ess:.1f} / {n}. "
                "IPW estimators will be highly variable. Use TMLE or cross-fitting."
            )

        if overlap_score < 0.5:
            recommendations.append(
                f"Overlap score = {overlap_score:.2f}: many observations have propensity "
                f"outside [{overlap_band:.2f}, {1 - overlap_band:.2f}]. "
                "Causal identification may be unreliable in these regions."
            )

        if min_e < 0.05:
            recommendations.append(
                f"Minimum propensity score {min_e:.4f} is very small. "
                "Consider restricting analysis to the region of common support."
            )

        if max_e > 0.95:
            recommendations.append(
                f"Maximum propensity score {max_e:.4f} is very large. "
                "Near-deterministic treatment assignment detected."
            )

        return {
            "result": {
                "passes_positivity": passes_positivity,
                "min_propensity_observed": min_e,
                "max_propensity_observed": max_e,
                "effective_sample_size": ess,
                "ess_fraction": ess_fraction,
                "overlap_score": overlap_score,
                "n_obs": n,
                "n_trimmed": n_trimmed,
                "recommendations": recommendations,
                "side_conditions_violated": side_conditions_violated,
                "propensity_percentiles": {
                    "p5": float(np.percentile(e, 5)),
                    "p25": float(np.percentile(e, 25)),
                    "p50": float(np.percentile(e, 50)),
                    "p75": float(np.percentile(e, 75)),
                    "p95": float(np.percentile(e, 95)),
                },
                "n_treated": int(np.sum(T > 0.5)),
                "n_control": int(np.sum(T <= 0.5)),
            }
        }


@foundry_method(
    namespace="causal.diagnostics",
    version="1.0.0",
    tags={"causal", "diagnostics", "support", "transportability", "density-ratio", "cross-section"},
)
class SupportMismatchDiagnostic:
    """Support mismatch diagnostic using density-ratio estimation.

    Computes importance weights w(x) = p_target(x) / p_source(x) and evaluates
    whether the source and target domains share adequate covariate support for
    transportability.

    Reports:
    - passes_support_check: True when ESS fraction >= ess_threshold
    - ESS (Kish effective sample size) and ESS fraction
    - support_mismatch_fraction: fraction of source obs with extreme weights (> 95th pct)
    - actionable recommendations

    Use before CheckTransportability, DensityRatioEstimator, or any cross-domain estimation.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="support_mismatch",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "X_source",
                    SlotType.MATRIX,
                    Unit("covariate", "value"),
                    shape=("n_source", "n_features"),
                ),
                SlotSpec(
                    "X_target",
                    SlotType.MATRIX,
                    Unit("covariate", "value"),
                    shape=("n_target", "n_features"),
                ),
            }
        ),
        output_slots=frozenset(
            {SlotSpec("result", SlotType.SCALAR, Unit("diagnostic", "json"))}
        ),
        parameters=(
            ParameterSpec(
                name="method",
                default="logistic_trick",
                description="Density-ratio estimation method: 'logistic_trick' or 'kliep'.",
            ),
            ParameterSpec(
                name="ess_threshold",
                default=0.1,
                description="Minimum ESS fraction to pass support check.",
            ),
            ParameterSpec(
                name="max_iter",
                default=100,
                description="Max iterations for density-ratio estimator.",
            ),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Support mismatch diagnostic: estimates density ratios between source and target "
            "domains and evaluates whether covariate support is adequate for transportability."
        ),
        tags=frozenset(
            {"causal", "diagnostics", "support", "transportability", "density-ratio", "governance"}
        ),
        citations=(
            "Sugiyama, M. et al. (2012). Density-ratio matching under the Bregman divergence.",
            "Bareinboim, E. & Pearl, J. (2016). Causal inference and the data-fusion problem.",
        ),
        equations={
            "ess": "ESS = (Σw)² / Σw²",
            "weights": "w(x) = p_target(x) / p_source(x)",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Run before CheckTransportability, DensityRatioEstimator, or any estimator "
            "that reweights source-domain data to a target domain."
        ),
        when_not_to_use="Not needed for single-domain estimation without transportability concerns.",
        prerequisites=(),
        diagnostic_checks=(),
        typical_min_obs=50,
        output_interpretation=(
            "passes_support_check=True: ESS fraction >= ess_threshold, reweighting is feasible. "
            "support_mismatch_fraction > 0.2: substantial tail extrapolation, use with caution. "
            "ESS fraction < 0.05: severe mismatch — reweighting will produce unreliable estimates."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.methods.catalog.causal.density_ratio import (
            _kliep,
            _logistic_trick,
        )

        X_source = np.asarray(state["X_source"], dtype=float)
        X_target = np.asarray(state["X_target"], dtype=float)

        if X_source.ndim == 1:
            X_source = X_source[:, None]
        if X_target.ndim == 1:
            X_target = X_target[:, None]

        n_source = X_source.shape[0]
        n_target = X_target.shape[0]

        method: str = str(params.get("method", "logistic_trick"))
        ess_threshold: float = float(params.get("ess_threshold", 0.1))
        max_iter: int = int(params.get("max_iter", 100))

        if method == "kliep":
            weights = _kliep(X_source, X_target, max_iter=max_iter)
        else:
            weights = _logistic_trick(X_source, X_target, max_iter=max_iter)

        weights = np.asarray(weights, dtype=float)
        w_sum = float(np.sum(weights))
        w_sq_sum = float(np.sum(weights ** 2))
        ess = float(w_sum ** 2 / max(w_sq_sum, 1e-12))
        ess_fraction = min(float(ess / n_source), 1.0)

        p95 = float(np.percentile(weights, 95))
        support_mismatch_fraction = float(np.mean(weights > p95))

        passes_support_check = bool(ess_fraction >= ess_threshold)

        recommendations: list[str] = []
        if not passes_support_check:
            recommendations.append(
                f"ESS fraction is low ({ess_fraction:.3f} < {ess_threshold:.3f}). "
                "Source and target distributions are substantially different. "
                "Consider restricting to the region of common support."
            )
        if support_mismatch_fraction > 0.2:
            recommendations.append(
                f"support_mismatch_fraction={support_mismatch_fraction:.2f}: "
                "a large fraction of source observations have extreme density ratios. "
                "Extrapolation risk is high."
            )
        if ess_fraction < 0.05:
            recommendations.append(
                "Severe support mismatch: ESS fraction < 5%. "
                "Reweighting-based estimation will be highly unreliable."
            )

        return {
            "result": {
                "passes_support_check": passes_support_check,
                "ess": ess,
                "ess_fraction": ess_fraction,
                "support_mismatch_fraction": support_mismatch_fraction,
                "n_source": n_source,
                "n_target": n_target,
                "density_ratio_method": method,
                "recommendations": recommendations,
                "weight_percentiles": {
                    "p5": float(np.percentile(weights, 5)),
                    "p25": float(np.percentile(weights, 25)),
                    "p50": float(np.percentile(weights, 50)),
                    "p75": float(np.percentile(weights, 75)),
                    "p95": p95,
                    "p99": float(np.percentile(weights, 99)),
                },
            }
        }


__all__ = ["ParallelTrendsCheck", "PositivityDiagnostic", "SupportMismatchDiagnostic"]
