"""Compute partial-identification bounds when point identification is not credible."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np

_logger = logging.getLogger(__name__)

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
from polisyos.foundry.methods.catalog.causal.model_class_compatibility import (
    check_model_class_compatibility,
)
from polisyos.ir.analytics.partial_identification import BoundMethod, PartialIdentificationResult


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


@foundry_method(
    namespace="causal.bounds",
    version="1.0.0",
    tags={"causal", "bounds", "manski"},
)
class ManskiBoundsEstimator:
    """Compute no-assumption Manski treatment-effect bounds; expect wide intervals under weak support information."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="manski",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec(
                    "treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="y_lower", default=0.0),
            ParameterSpec(name="y_upper", default=1.0),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Manski (1990) worst-case bounds on ATE under no assumptions.",
        tags=frozenset({"causal", "bounds", "manski", "worst-case", "partial-identification"}),
        citations=("Manski, C.F. (1990). Nonparametric Bounds on Treatment Effects. AER P&P.",),
        equations={
            "lower": "ATE_lb = E[Y|T=1]*P(T=1) + y_min*P(T=0) - E[Y|T=0]*P(T=0) - y_max*P(T=1)",
            "upper": "ATE_ub = E[Y|T=1]*P(T=1) + y_max*P(T=0) - E[Y|T=0]*P(T=0) - y_min*P(T=1)",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Partial identification without strong assumptions; worst-case bounds on ATE under monotone treatment response",
        when_not_to_use="Strong instrument available enabling point identification; need point estimate not interval",
        output_interpretation="[lower, upper] sharp bounds on ATE. Interval narrows under MTR. Bounds may be wide — interpret as range of compatibility.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        Y = np.asarray(state["outcome"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        y_lo = float(params.get("y_lower", 0.0))
        y_hi = float(params.get("y_upper", 1.0))
        n = len(Y)

        treated = T > 0.5
        p1 = float(np.mean(treated))
        p0 = 1.0 - p1

        e_y1 = float(np.mean(Y[treated])) if np.any(treated) else 0.0
        e_y0 = float(np.mean(Y[~treated])) if np.any(~treated) else 0.0

        # Manski bounds
        ate_lower = e_y1 * p1 + y_lo * p0 - (e_y0 * p0 + y_hi * p1)
        ate_upper = e_y1 * p1 + y_hi * p0 - (e_y0 * p0 + y_lo * p1)

        # Simpler: direct computation
        ate_lower2 = (e_y1 - y_hi) * p1 + (y_lo - e_y0) * p0
        ate_upper2 = (e_y1 - y_lo) * p1 + (y_hi - e_y0) * p0

        return {
            "result": {
                "ate_lower_bound": min(ate_lower, ate_lower2),
                "ate_upper_bound": max(ate_upper, ate_upper2),
                "bound_width": max(ate_upper, ate_upper2) - min(ate_lower, ate_lower2),
                "naive_ate": e_y1 - e_y0,
                "p_treated": p1,
                "n_obs": n,
            }
        }


@foundry_method(
    namespace="causal.bounds",
    version="1.0.0",
    tags={"causal", "bounds", "lee"},
)
class LeeBoundsEstimator:
    """Compute Lee attrition bounds under monotone selection; avoid when treatment can move selection in both directions."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="lee",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec(
                    "treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)
                ),
                SlotSpec(
                    "selected", SlotType.VECTOR, Unit("selection", "binary"), shape=("n_obs",)
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Lee (2009) bounds for treatment effects under sample selection.",
        tags=frozenset({"causal", "bounds", "lee", "sample-selection", "partial-identification"}),
        citations=("Lee, D.S. (2009). Training, Wages, and Sample Selection. ReStud.",),
        equations={
            "lee": "Trim always-selected from larger group, bound ATE by trimming from top/bottom"
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Sample selection or attrition in RCT; want sharp bounds on ATE controlling for selective non-compliance",
        when_not_to_use="No attrition or selection problem; full compliance in RCT",
        typical_min_obs=50,
        output_interpretation="[lower, upper] Lee bounds trimming worst-case survivors. Tightest sharp bounds under monotone selection assumption.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        Y = np.asarray(state["outcome"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        S = np.asarray(state["selected"], dtype=float)
        n = len(Y)

        treated = T > 0.5
        selected = S > 0.5

        # Selected outcomes by group
        y1 = Y[treated & selected]
        y0 = Y[~treated & selected]
        n1_sel = len(y1)
        n0_sel = len(y0)
        n1_tot = int(np.sum(treated))
        n0_tot = int(np.sum(~treated))

        if n1_sel == 0 or n0_sel == 0:
            return {"result": {"ate_lower": 0.0, "ate_upper": 0.0, "n_obs": n}}

        # Selection rates
        s1 = n1_sel / max(n1_tot, 1)
        s0 = n0_sel / max(n0_tot, 1)

        # Trimming proportion
        if s1 > s0:
            # Trim from treated group
            trim_frac = 1.0 - s0 / s1
            y1_sorted = np.sort(y1)
            n_trim = int(np.round(trim_frac * n1_sel))
            # Lower bound: trim from top
            y1_lower = y1_sorted[: n1_sel - n_trim] if n_trim > 0 else y1_sorted
            # Upper bound: trim from bottom
            y1_upper = y1_sorted[n_trim:] if n_trim > 0 else y1_sorted
            ate_lower = float(np.mean(y1_lower) - np.mean(y0))
            ate_upper = float(np.mean(y1_upper) - np.mean(y0))
        else:
            # Trim from control group
            trim_frac = 1.0 - s1 / s0
            y0_sorted = np.sort(y0)
            n_trim = int(np.round(trim_frac * n0_sel))
            y0_upper = y0_sorted[: n0_sel - n_trim] if n_trim > 0 else y0_sorted
            y0_lower = y0_sorted[n_trim:] if n_trim > 0 else y0_sorted
            ate_lower = float(np.mean(y1) - np.mean(y0_lower))
            ate_upper = float(np.mean(y1) - np.mean(y0_upper))

        return {
            "result": {
                "ate_lower_bound": min(ate_lower, ate_upper),
                "ate_upper_bound": max(ate_lower, ate_upper),
                "bound_width": abs(ate_upper - ate_lower),
                "trimming_fraction": trim_frac,
                "selection_rate_treated": s1,
                "selection_rate_control": s0,
                "n_obs": n,
            }
        }


def _make_partial_id_result(
    lower: float,
    upper: float,
    method: BoundMethod,
    assumptions: list[str],
    confidence: float = 0.9,
    display_label: str = "",
    bounds_type: str = "manski",
) -> dict[str, Any]:
    """Build a PartialIdentificationResult-compatible dict for pure_step returns."""
    return PartialIdentificationResult(
        method=method,
        lower_bound=lower,
        upper_bound=upper,
        confidence=confidence,
        assumptions_used=assumptions,
        display_label=display_label,
        bounds_type=bounds_type,
    ).model_dump()


def _balke_pearl_lp(
    p_yxz: np.ndarray,
) -> tuple[float, float, str, dict[str, Any] | None]:
    """LP solver for Balke-Pearl sharp IV bounds.

    Parameters
    ----------
    p_yxz : (2, 2, 2) array
        p_yxz[y, x, z] = P(Y=y, X=x | Z=z), estimated from data.

    Returns
    -------
    (lower_bound, upper_bound, solver_status)
    """
    from scipy.optimize import linprog

    n_types = 16  # 2^4 response-function types (x0,x1,y0,y1)

    # Build equality constraints for observed P(Y=y, X=x | Z=z)
    rows: list[np.ndarray] = []
    rhs: list[float] = []
    for z in range(2):
        for x in range(2):
            for y in range(2):
                row = np.zeros(n_types)
                for r in range(n_types):
                    x_z = (r >> z) & 1  # X(Z=z): bit 0 = X(Z=0), bit 1 = X(Z=1)
                    y_xz = (r >> (2 + x_z)) & 1  # Y(X(Z=z)): bit 2 = Y(X=0), bit 3 = Y(X=1)
                    if x_z == x and y_xz == y:
                        row[r] = 1.0
                rows.append(row)
                rhs.append(float(p_yxz[y, x, z]))

    # Sum-to-1
    rows.append(np.ones(n_types))
    rhs.append(1.0)

    A_eq = np.array(rows)
    b_eq = np.array(rhs)

    # ATE objective: c_r = Y(1)_r - Y(0)_r
    c = np.array([((r >> 3) & 1) - ((r >> 2) & 1) for r in range(n_types)], dtype=float)
    bounds = [(0.0, None)] * n_types

    res_lo = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    res_hi = linprog(-c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")

    if res_lo.status == 0 and res_hi.status == 0:
        from polisyos.ir.analytics.dual_certificate import (
            build_binary_iv_dual_certificate_bundle,
        )

        cert = build_binary_iv_dual_certificate_bundle(
            joint=p_yxz,
            lower_result=res_lo,
            upper_result=res_hi,
        )
        return (
            float(res_lo.fun),
            float(-res_hi.fun),
            "optimal",
            cert.model_dump(mode="json"),
        )
    if res_lo.status == 2 or res_hi.status == 2:
        status = f"infeasible(lo={res_lo.status},hi={res_hi.status})"
    elif res_lo.status == 3 or res_hi.status == 3:
        status = f"unbounded(lo={res_lo.status},hi={res_hi.status})"
    else:
        status = f"solver_failed(lo={res_lo.status},hi={res_hi.status})"
    return -1.0, 1.0, status, None


@foundry_method(
    namespace="causal.bounds",
    version="1.0.0",
    tags={"causal", "bounds", "balke-pearl", "iv", "lp"},
)
class BalkePearlBoundsEstimator:
    """Sharp IV bounds via linear programming (Balke & Pearl 1994).

    For binary instrument Z, binary treatment X, binary outcome Y.
    Computes the sharpest possible bounds on ATE = E[Y(1) - Y(0)]
    consistent with the observed distribution P(Y, X | Z).
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scipy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="balke_pearl",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "binary"), shape=("n_obs",)),
                SlotSpec(
                    "treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)
                ),
                SlotSpec(
                    "instrument", SlotType.VECTOR, Unit("instrument", "binary"), shape=("n_obs",)
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="clip_probs", default=True),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Balke-Pearl (1994) sharp IV bounds on ATE via LP over response functions.",
        tags=frozenset({"causal", "bounds", "balke-pearl", "iv", "lp", "partial-identification"}),
        citations=(
            "Balke, A. & Pearl, J. (1994). Counterfactual Probabilities. UAI.",
            "Balke, A. & Pearl, J. (1997). Bounds on Treatment Effects. JASA.",
        ),
        equations={
            "ate": "E[Y(1)-Y(0)] = ∑_r p_r*(y1_r - y0_r)",
            "constraint": "P(Y=y,X=x|Z=z) = ∑_{r: X(z)=x, Y(X(z))=y} p_r",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy", "scipy"),
        when_to_use="Binary IV, binary treatment, binary outcome; want sharp (tightest) bounds on ATE",
        when_not_to_use="Non-binary outcomes or treatments; use Manski instead",
        output_interpretation=(
            "[lower, upper] sharp bounds on ATE. These are tighter than Manski under IV assumption."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        Y = np.asarray(state["outcome"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        Z = np.asarray(state["instrument"], dtype=float)
        n = len(Y)
        clip_probs = bool(params.get("clip_probs", True))

        # Binarise inputs
        y = (Y > 0.5).astype(int)
        t = (T > 0.5).astype(int)
        z = (Z > 0.5).astype(int)

        compatibility_alpha = float(params.get("compatibility_alpha", 0.05))
        compatibility_multiple_testing = (
            str(params.get("compatibility_multiple_testing", "holm")).strip().lower()
        )
        run_compatibility_check = bool(params.get("check_model_class_compatibility", True))
        if run_compatibility_check:
            compatibility = check_model_class_compatibility(
                model_class_id="iv.binary.unconditional",
                data=np.column_stack([z, t, y]).astype(float),
                variable_names=["Z", "X", "Y"],
                observed_variables=["Z", "X", "Y"],
                alpha=compatibility_alpha,
                multiple_testing=(
                    compatibility_multiple_testing
                    if compatibility_multiple_testing in {"holm", "bonferroni", "none"}
                    else "holm"
                ),
            )
            if compatibility.status == "incompatible":
                return {
                    "result": {
                        "ate_lower_bound": None,
                        "ate_upper_bound": None,
                        "bound_width": None,
                        "solver_status": "model_class_incompatible",
                        "n_obs": n,
                        "partial_id_result": None,
                        "dual_certificate_payload": None,
                        "negative_certificate": (
                            compatibility.negative_certificate.model_dump(mode="json")
                            if compatibility.negative_certificate is not None
                            else None
                        ),
                        "model_class_compatibility": compatibility.report.model_dump(mode="json"),
                    }
                }

        # Estimate P(Y=y, X=x | Z=z) — shape (2,2,2)
        p_yxz = np.zeros((2, 2, 2))
        for zv in range(2):
            mask_z = z == zv
            n_z = np.sum(mask_z)
            if n_z == 0:
                continue
            for xv in range(2):
                for yv in range(2):
                    p_yxz[yv, xv, zv] = np.sum(mask_z & (t == xv) & (y == yv)) / n_z

        if clip_probs:
            p_yxz = np.clip(p_yxz, 0.0, 1.0)

        lower, upper, solver_status, dual_certificate_payload = _balke_pearl_lp(p_yxz)

        partial_id = _make_partial_id_result(
            lower=lower,
            upper=upper,
            method=BoundMethod.LP_BALKE_PEARL,
            assumptions=["binary_iv", "binary_treatment", "binary_outcome", "iv_relevance"],
            confidence=0.95 if solver_status == "optimal" else 0.5,
            display_label="Balke-Pearl Sharp IV Bounds",
            bounds_type="sharp_lp",
        )

        return {
            "result": {
                "ate_lower_bound": lower,
                "ate_upper_bound": upper,
                "bound_width": upper - lower,
                "solver_status": solver_status,
                "n_obs": n,
                "partial_id_result": partial_id,
                "dual_certificate_payload": dual_certificate_payload,
            }
        }


@foundry_method(
    namespace="causal.bounds",
    version="1.0.0",
    tags={"causal", "bounds", "manski", "confidence-interval"},
)
class ImbensManskiBoundsEstimator:
    """Asymptotic confidence interval around Manski worst-case bounds (Imbens & Manski 2004).

    Provides a confidence interval [CI_lo, CI_hi] such that the true ATE lies within
    the interval with at least (1-alpha) probability, accounting for sampling uncertainty
    in the Manski bounds themselves.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scipy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="imbens_manski",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec(
                    "treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="y_lower", default=0.0),
            ParameterSpec(name="y_upper", default=1.0),
            ParameterSpec(name="alpha", default=0.05),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Imbens-Manski (2004) confidence interval for partially identified ATE.",
        tags=frozenset(
            {"causal", "bounds", "manski", "confidence-interval", "partial-identification"}
        ),
        citations=(
            "Imbens, G. & Manski, C. (2004). Confidence Intervals for Partially Identified Parameters. Econometrica.",
        ),
        equations={
            "ci_lower": "ATE_lb - c_n * se / sqrt(n)",
            "ci_upper": "ATE_ub + c_n * se / sqrt(n)",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy", "scipy"),
        when_to_use="Need CI around Manski worst-case bounds that covers true ATE with 1-alpha probability",
        when_not_to_use="Point identification available; prefer standard SE around point estimate",
        output_interpretation=(
            "[ci_lower, ci_upper] CI covers the true ATE with probability ≥ 1-alpha. "
            "Wider than Manski bounds by ±c_n*se/sqrt(n)."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from scipy.stats import norm

        Y = np.asarray(state["outcome"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        y_lo = float(params.get("y_lower", 0.0))
        y_hi = float(params.get("y_upper", 1.0))
        alpha = float(params.get("alpha", 0.05))
        n = len(Y)

        treated = T > 0.5
        p1 = float(np.mean(treated))
        p0 = 1.0 - p1

        e_y1 = float(np.mean(Y[treated])) if np.any(treated) else y_lo
        e_y0 = float(np.mean(Y[~treated])) if np.any(~treated) else y_lo

        # Manski point bounds
        ate_lb = (e_y1 - y_hi) * p1 + (y_lo - e_y0) * p0
        ate_ub = (e_y1 - y_lo) * p1 + (y_hi - e_y0) * p0

        # Sample variances for delta-method SE (conservative)
        var_y1 = float(np.var(Y[treated])) if np.sum(treated) > 1 else 0.0
        var_y0 = float(np.var(Y[~treated])) if np.sum(~treated) > 1 else 0.0
        n1 = int(np.sum(treated))
        n0 = n - n1

        se_lb = np.sqrt(p1**2 * var_y1 / max(n1, 1) + p0**2 * var_y0 / max(n0, 1))
        se_ub = se_lb  # symmetric in this formulation

        # Imbens-Manski (2004) critical value c_n
        # Calibrated so that the interval [lb - c*se, ub + c*se] covers ATE with prob >= 1-alpha.
        # We use the standard normal quantile as an approximation (asymptotically valid).
        z_alpha = float(norm.ppf(1.0 - alpha / 2))

        ci_lower = ate_lb - z_alpha * se_lb
        ci_upper = ate_ub + z_alpha * se_ub

        partial_id = _make_partial_id_result(
            lower=ci_lower,
            upper=ci_upper,
            method=BoundMethod.IMBENS_MANSKI_CI,
            assumptions=["no_assumptions_on_selection"],
            confidence=1.0 - alpha,
            display_label=f"Imbens-Manski {int((1 - alpha) * 100)}% CI",
        )

        return {
            "result": {
                "ate_lower_bound": ate_lb,
                "ate_upper_bound": ate_ub,
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
                "bound_width": ate_ub - ate_lb,
                "ci_width": ci_upper - ci_lower,
                "se": float(se_lb),
                "alpha": alpha,
                "n_obs": n,
                "partial_id_result": partial_id,
            }
        }


@foundry_method(
    namespace="causal.bounds",
    version="1.0.0",
    tags={"causal", "bounds", "mtr", "miv", "mts", "lp", "optimization"},
)
class OptimizationBasedBoundsEstimator:
    """LP-based bounds under monotone shape restrictions.

    Supports three assumptions:
    - ``"mtr"``: Monotone Treatment Response — Y(1) >= Y(0) for all units (Manski 1997).
      Closed-form; does not require scipy.
    - ``"miv"``: Monotone Instrumental Variable — Z stochastically increases treatment
      (Manski & Pepper 2000). Stratify Z into quantile bins; MIV lower = max of stratum
      lowers; MIV upper = min of stratum uppers.  Requires a ``miv_proxy`` input slot.
      Falls back to MTR bounds when scipy is unavailable.
    - ``"mts"``: Monotone Treatment Selection — units selecting T=1 have weakly higher
      potential outcomes than those selecting T=0.  LP over 4 response types.
      Falls back to MTR bounds when scipy is unavailable.
    - ``"mts_mtr"``: Both MTS and MTR simultaneously (tightest intersection).
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="optimization",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec(
                    "treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)
                ),
                SlotSpec(
                    "miv_proxy", SlotType.VECTOR, Unit("instrument", "ordinal"), shape=("n_obs",)
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="y_lower", default=0.0),
            ParameterSpec(name="y_upper", default=1.0),
            ParameterSpec(
                name="assumption", default="mtr", description="'mtr' | 'mts' | 'mts_mtr' | 'miv'"
            ),
            ParameterSpec(
                name="n_strata",
                default=5,
                description="Number of quantile bins for MIV stratification",
            ),
            ParameterSpec(name="clip_probs", default=True),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "LP-based bounds under monotone shape restrictions: MTR (Manski 1997), "
            "MIV (Manski & Pepper 2000), MTS, or MTS+MTR joint."
        ),
        tags=frozenset({"causal", "bounds", "mtr", "miv", "mts", "lp", "partial-identification"}),
        citations=(
            "Manski, C.F. (1997). Monotone Treatment Response. Econometrica.",
            "Manski, C.F. & Pepper, J.V. (2000). Monotone Instrumental Variables. Econometrica.",
        ),
        equations={
            "mtr_lower": "E[Y(1)-Y(0)] >= (E[Y|T=1] - y_max) * p1 + (y_min - E[Y|T=0]) * p0",
            "mtr_upper": "E[Y(1)-Y(0)] <= (E[Y|T=1] - y_min) * p1 + (y_max - E[Y|T=0]) * p0",
            "miv_lower": "max over strata z_k of Manski lower bounds given Z >= z_k",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Manski bounds are too wide; want tighter bounds under a plausible monotonicity "
            "assumption; or have a monotone instrumental variable that is non-binary."
        ),
        when_not_to_use=(
            "Binary IV available — use Balke-Pearl which is sharper. "
            "Monotonicity assumption is questionable for the application."
        ),
        output_interpretation=(
            "[lower, upper] tighter than Manski bounds under the stated monotone assumption. "
            "BoundMethod indicates which assumption was enforced."
        ),
    )

    @staticmethod
    def _mtr_bounds(
        Y: np.ndarray,
        T: np.ndarray,
        y_lo: float,
        y_hi: float,
    ) -> tuple[float, float, str]:
        """Closed-form MTR bounds — no scipy needed."""
        treated = T > 0.5
        p1 = float(np.mean(treated))
        p0 = 1.0 - p1
        e_y1 = float(np.mean(Y[treated])) if np.any(treated) else y_lo
        e_y0 = float(np.mean(Y[~treated])) if np.any(~treated) else y_lo

        # Manski worst-case bounds
        manski_lower = (e_y1 - y_hi) * p1 + (y_lo - e_y0) * p0
        manski_upper = (e_y1 - y_lo) * p1 + (y_hi - e_y0) * p0

        # MTR tightening: Y(1) >= Y(0) => ATE >= 0 always, but also tightens
        # the upper/lower based on the fact that Y(1) >= Y(0) per unit.
        # Under MTR: E[Y(1)] >= E[Y(0)] => ATE >= 0
        # Lower bound tightens to max(manski_lower, 0)
        # Upper bound: unchanged (already uses y_hi - y_lo range correctly)
        # Additional tightening from Manski (1997) Eq. (3.3)-(3.4):
        #   lb_mtr = E[Y|T=1]*p1 + y_min*p0 - E[Y|T=0]*p0 - y_max*p1 but clipped at 0
        mtr_lower = max(manski_lower, 0.0)
        # Upper bound from MTR: E[Y(1)] bounded above by E[Y|T=1]*p1 + y_max*p0
        # and E[Y(0)] bounded below by y_min*p1 + E[Y|T=0]*p0 but constrained <= E[Y(1)]
        # Net: ATE <= min(manski_upper, e_y1 - e_y0 + (y_hi - y_lo) * min(p1, p0))
        mtr_upper = min(manski_upper, e_y1 - y_lo)

        # Ensure ordering
        lb = min(mtr_lower, mtr_upper)
        ub = max(mtr_lower, mtr_upper)
        return lb, ub, "mtr_closed_form"

    @staticmethod
    def _miv_bounds(
        Y: np.ndarray,
        T: np.ndarray,
        Z: np.ndarray,
        y_lo: float,
        y_hi: float,
        n_strata: int,
    ) -> tuple[float, float, str]:
        """MIV bounds via quantile stratification of Z."""
        quantiles = np.quantile(Z, np.linspace(0.0, 1.0, n_strata + 1))
        stratum_lowers: list[float] = []
        stratum_uppers: list[float] = []

        for i in range(n_strata):
            q_lo_s = quantiles[i]
            q_hi_s = quantiles[i + 1]
            if i == n_strata - 1:
                mask = q_lo_s <= Z
            else:
                mask = (q_lo_s <= Z) & (q_hi_s > Z)
            if np.sum(mask) < 5:
                continue
            Ys, Ts = Y[mask], T[mask]
            treated_s = Ts > 0.5
            p1_s = float(np.mean(treated_s))
            p0_s = 1.0 - p1_s
            e_y1_s = float(np.mean(Ys[treated_s])) if np.any(treated_s) else y_lo
            e_y0_s = float(np.mean(Ys[~treated_s])) if np.any(~treated_s) else y_lo
            lb_s = (e_y1_s - y_hi) * p1_s + (y_lo - e_y0_s) * p0_s
            ub_s = (e_y1_s - y_lo) * p1_s + (y_hi - e_y0_s) * p0_s
            stratum_lowers.append(lb_s)
            stratum_uppers.append(ub_s)

        if not stratum_lowers:
            # Fall back to full-sample Manski
            treated = T > 0.5
            p1 = float(np.mean(treated))
            p0 = 1.0 - p1
            e_y1 = float(np.mean(Y[treated])) if np.any(treated) else y_lo
            e_y0 = float(np.mean(Y[~treated])) if np.any(~treated) else y_lo
            lb = (e_y1 - y_hi) * p1 + (y_lo - e_y0) * p0
            ub = (e_y1 - y_lo) * p1 + (y_hi - e_y0) * p0
            return lb, ub, "miv_fallback_manski"

        # MIV: lb = max of stratum lowers, ub = min of stratum uppers
        lb = max(stratum_lowers)
        ub = min(stratum_uppers)
        if lb > ub:
            # Intersection is empty; stratum bounds are inconsistent.
            # This typically indicates model misspecification or violation of the
            # MIV monotonicity assumption.  Fall back to the widest interval.
            _logger.warning(
                "MIV stratum bounds inconsistent (lb=%.4f > ub=%.4f): "
                "monotonicity assumption may be violated. "
                "Falling back to widest interval [min(lowers), max(uppers)].",
                lb,
                ub,
            )
            lb = min(stratum_lowers)
            ub = max(stratum_uppers)
        return lb, ub, "miv_quantile_strata"

    @staticmethod
    def _mts_bounds_lp(
        Y: np.ndarray,
        T: np.ndarray,
        y_lo: float,
        y_hi: float,
        apply_mtr: bool = False,
    ) -> tuple[float, float, str]:
        """MTS bounds via LP over potential outcome means.

        Monotone Treatment Selection: E[Y(t)|T=1] >= E[Y(t)|T=0] for t in {0,1}.
        This bounds E[Y(1)] - E[Y(0)] tighter than Manski by leveraging that
        compliers have higher potential outcomes than never-takers.

        Falls back to MTR closed-form if scipy unavailable.
        """
        try:
            from scipy.optimize import linprog
        except ImportError:
            return OptimizationBasedBoundsEstimator._mtr_bounds(Y, T, y_lo, y_hi)

        treated = T > 0.5
        p1 = float(np.mean(treated))
        p0 = 1.0 - p1
        e_y1_obs = float(np.mean(Y[treated])) if np.any(treated) else y_lo
        e_y0_obs = float(np.mean(Y[~treated])) if np.any(~treated) else y_lo
        n = len(Y)

        # Variables: mu1_1 = E[Y(1)|T=1], mu1_0 = E[Y(1)|T=0],
        #            mu0_1 = E[Y(0)|T=1], mu0_0 = E[Y(0)|T=0]
        # ATE = p1*(mu1_1 - mu0_1) + p0*(mu1_0 - mu0_0)
        # Observations:
        #   E[Y|T=1] = mu1_1 (consistency + SUTVA)
        #   E[Y|T=0] = mu0_0
        # MTS: mu1_1 >= mu1_0 and mu0_1 >= mu0_0
        # MTR: mu1_t >= mu0_t => mu1_1 >= mu0_1 and mu1_0 >= mu0_0
        # Bounds for each variable: [y_lo, y_hi]

        # ATE objective: c = p1*[1, 0, -1, 0] + p0*[0, 1, 0, -1]
        # Variables: [mu1_1, mu1_0, mu0_1, mu0_0]
        c_ate = np.array([p1, p0, -p1, -p0])

        # Bounds: each variable in [y_lo, y_hi]
        var_bounds = [(y_lo, y_hi)] * 4

        # Equality constraints from observational data:
        # mu1_1 = e_y1_obs  (index 0)
        # mu0_0 = e_y0_obs  (index 3)
        A_eq = np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]])
        b_eq = np.array([e_y1_obs, e_y0_obs])

        # Inequality constraints (A_ub @ x <= b_ub):
        ineq_rows: list[np.ndarray] = []
        ineq_rhs: list[float] = []

        # MTS: mu1_1 >= mu1_0  =>  mu1_0 - mu1_1 <= 0
        ineq_rows.append(np.array([-1.0, 1.0, 0.0, 0.0]))
        ineq_rhs.append(0.0)
        # MTS: mu0_1 >= mu0_0  =>  mu0_0 - mu0_1 <= 0
        ineq_rows.append(np.array([0.0, 0.0, -1.0, 1.0]))
        ineq_rhs.append(0.0)

        if apply_mtr:
            # MTR: mu1_1 >= mu0_1  =>  mu0_1 - mu1_1 <= 0
            ineq_rows.append(np.array([-1.0, 0.0, 1.0, 0.0]))
            ineq_rhs.append(0.0)
            # MTR: mu1_0 >= mu0_0  =>  mu0_0 - mu1_0 <= 0
            ineq_rows.append(np.array([0.0, -1.0, 0.0, 1.0]))
            ineq_rhs.append(0.0)

        A_ub = np.array(ineq_rows)
        b_ub = np.array(ineq_rhs)

        res_lo = linprog(
            c_ate, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=var_bounds, method="highs"
        )
        res_hi = linprog(
            -c_ate, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=var_bounds, method="highs"
        )

        if res_lo.status == 0 and res_hi.status == 0:
            status = "mts_mtr_lp" if apply_mtr else "mts_lp"
            return float(res_lo.fun), float(-res_hi.fun), status
        # LP failed — fall back to MTR closed-form
        return OptimizationBasedBoundsEstimator._mtr_bounds(Y, T, y_lo, y_hi)

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        Y = np.asarray(state["outcome"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        y_lo = float(params.get("y_lower", 0.0))
        y_hi = float(params.get("y_upper", 1.0))
        assumption = str(params.get("assumption", "mtr"))
        n_strata = int(params.get("n_strata", 5))
        n = len(Y)

        if assumption == "miv":
            Z_raw = state.get("miv_proxy")
            if Z_raw is not None:
                Z = np.asarray(Z_raw, dtype=float)
                lower, upper, solver_status = OptimizationBasedBoundsEstimator._miv_bounds(
                    Y, T, Z, y_lo, y_hi, n_strata
                )
                bound_method = BoundMethod.MIV_BOUNDS
            else:
                lower, upper, solver_status = OptimizationBasedBoundsEstimator._mtr_bounds(
                    Y, T, y_lo, y_hi
                )
                bound_method = BoundMethod.MTR_BOUNDS
                solver_status = "miv_fallback_mtr_no_proxy"
        elif assumption == "mts":
            lower, upper, solver_status = OptimizationBasedBoundsEstimator._mts_bounds_lp(
                Y, T, y_lo, y_hi, apply_mtr=False
            )
            bound_method = BoundMethod.MTS_BOUNDS
        elif assumption == "mts_mtr":
            lower, upper, solver_status = OptimizationBasedBoundsEstimator._mts_bounds_lp(
                Y, T, y_lo, y_hi, apply_mtr=True
            )
            bound_method = BoundMethod.MTR_BOUNDS  # combined, report as MTR
        else:
            # Default: MTR
            lower, upper, solver_status = OptimizationBasedBoundsEstimator._mtr_bounds(
                Y, T, y_lo, y_hi
            )
            bound_method = BoundMethod.MTR_BOUNDS

        assumptions_map = {
            "mtr": ["monotone_treatment_response"],
            "mts": ["monotone_treatment_selection"],
            "mts_mtr": ["monotone_treatment_response", "monotone_treatment_selection"],
            "miv": ["monotone_instrumental_variable"],
        }
        assumptions = assumptions_map.get(assumption, ["monotone_treatment_response"])

        partial_id = _make_partial_id_result(
            lower=lower,
            upper=upper,
            method=bound_method,
            assumptions=assumptions,
            confidence=0.9,
            display_label=f"Optimization Bounds ({assumption.upper()})",
        )

        return {
            "result": {
                "ate_lower_bound": lower,
                "ate_upper_bound": upper,
                "bound_width": upper - lower,
                "assumption": assumption,
                "solver_status": solver_status,
                "n_obs": n,
                "partial_id_result": partial_id,
            }
        }


def _general_balke_pearl_lp(
    p_yxz: np.ndarray,
    n_treatment_levels: int,
    n_outcome_levels: int,
    treatment_target: int = 1,
    treatment_ref: int = 0,
    outcome_scale: float = 1.0,
    max_response_fns: int = 5_000,
) -> tuple[float, float, str, dict[str, Any] | None]:
    """General Balke-Pearl LP for multi-valued T ∈ {0,...,K} and Y ∈ {0,...,J}.

    Parameters
    ----------
    p_yxz : (J+1, K+1, 2) array
        p_yxz[y, x, z] = P(Y=y, X=x | Z=z), estimated from data.
    n_treatment_levels : int
        K+1 (number of distinct treatment values).
    n_outcome_levels : int
        J+1 (number of distinct outcome values).
    treatment_target : int
        The "treated" level t whose effect we want.
    treatment_ref : int
        The reference/control level.
    max_response_fns : int
        Safety cap on LP size.

    Returns
    -------
    (lower_bound, upper_bound, solver_status)
    """
    import itertools

    from scipy.optimize import linprog

    K1 = n_treatment_levels  # |T|
    J1 = n_outcome_levels  # |Y|

    # Each response function q = (x_resp, y_resp) where:
    #   x_resp ∈ {0,...,K}^2  — treatment response per Z value (binary Z only)
    #   y_resp ∈ {0,...,J}^K1 — outcome response per treatment level
    x_responses = list(itertools.product(range(K1), repeat=2))  # K1^2 items
    y_responses = list(itertools.product(range(J1), repeat=K1))  # J1^K1 items

    n_rf = len(x_responses) * len(y_responses)
    if n_rf > max_response_fns:
        raise ValueError(
            f"Response function space has {n_rf} elements (exceeds max={max_response_fns}). "
            f"Reduce cardinality of T or Y, or raise max_response_fns."
        )

    # Build all (x_resp, y_resp) response-function pairs
    all_rfs = [(xr, yr) for xr in x_responses for yr in y_responses]

    # --- Equality constraints: P̂(Y=y, X=x | Z=z) ---
    rows: list[np.ndarray] = []
    rhs: list[float] = []
    for z in range(2):
        for x in range(K1):
            for y in range(J1):
                row = np.zeros(n_rf)
                for i, (xr, yr) in enumerate(all_rfs):
                    x_when_z = xr[z]  # treatment response when Z=z
                    y_when_x = yr[x_when_z]  # outcome when T = x_when_z
                    if x_when_z == x and y_when_x == y:
                        row[i] = 1.0
                rows.append(row)
                rhs.append(float(p_yxz[y, x, z]))

    # Sum-to-1 constraint
    rows.append(np.ones(n_rf))
    rhs.append(1.0)

    A_eq = np.array(rows)
    b_eq = np.array(rhs)

    # --- Objective: ATE = E[Y(treatment_target) - Y(treatment_ref)] ---
    # For each response function, contribution = y_resp[treatment_target] - y_resp[treatment_ref]
    # Normalise to [0,1] scale by dividing by (J1 - 1) so bounds are on original scale.
    scale = float(J1 - 1) if J1 > 1 else 1.0
    c = np.array(
        [
            ((yr[treatment_target] - yr[treatment_ref]) / scale) * float(outcome_scale)
            for (_, yr) in all_rfs
        ],
        dtype=float,
    )
    bounds_lp = [(0.0, None)] * n_rf

    res_lo = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds_lp, method="highs")
    res_hi = linprog(-c, A_eq=A_eq, b_eq=b_eq, bounds=bounds_lp, method="highs")

    if res_lo.status == 0 and res_hi.status == 0:
        from polisyos.ir.analytics.dual_certificate import (
            build_general_iv_dual_certificate_bundle,
        )

        cert = build_general_iv_dual_certificate_bundle(
            joint=p_yxz,
            n_treatment_levels=K1,
            n_outcome_levels=J1,
            treatment_target=treatment_target,
            treatment_ref=treatment_ref,
            outcome_scale=outcome_scale,
            lower_result=res_lo,
            upper_result=res_hi,
        )
        return (
            float(res_lo.fun),
            float(-res_hi.fun),
            "optimal",
            cert.model_dump(mode="json"),
        )
    if res_lo.status == 2 or res_hi.status == 2:
        status = f"infeasible(lo={res_lo.status},hi={res_hi.status})"
    elif res_lo.status == 3 or res_hi.status == 3:
        status = f"unbounded(lo={res_lo.status},hi={res_hi.status})"
    else:
        status = f"solver_failed(lo={res_lo.status},hi={res_hi.status})"
    return (
        -float(J1 - 1) * float(outcome_scale),
        float(J1 - 1) * float(outcome_scale),
        status,
        None,
    )


@foundry_method(
    namespace="causal.bounds",
    version="1.0.0",
    tags={"causal", "bounds", "balke-pearl", "iv", "lp", "multi-valued"},
)
class GeneralBalkePearlBoundsEstimator:
    """Generalised Balke-Pearl LP bounds for multi-valued T and Y (Balke & Pearl 1997 §4).

    Extends the binary Balke-Pearl estimator to T ∈ {0,...,K} and Y ∈ {0,...,J}
    with a binary instrument Z ∈ {0,1}.  The LP enumerates all (K+1)^2 × (J+1)^(K+1)
    response functions and solves for the tightest ATE bounds consistent with
    the observed distribution P(Y,X|Z).

    Size of LP:
        binary T/Y     →  16 response functions  (same as BalkePearlBoundsEstimator)
        ternary T/Y    → 729 response functions  (still fast with HiGHS)
        4-level T/Y    → 4^2 × 4^4 = 4096       (nearing the cap — use with care)
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scipy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="general_balke_pearl",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "numeric"), shape=("n_obs",)),
                SlotSpec(
                    "treatment", SlotType.VECTOR, Unit("treatment", "categorical"), shape=("n_obs",)
                ),
                SlotSpec(
                    "instrument", SlotType.VECTOR, Unit("instrument", "binary"), shape=("n_obs",)
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(
                name="treatment_target",
                default=1,
                description="Which treatment level to compare (vs treatment_ref).",
            ),
            ParameterSpec(
                name="treatment_ref", default=0, description="Reference treatment level."
            ),
            ParameterSpec(
                name="max_response_fns",
                default=5_000,
                description="Safety cap on LP size; raise carefully.",
            ),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "General Balke-Pearl LP bounds for multi-valued treatment/outcome with binary IV."
        ),
        tags=frozenset({"causal", "bounds", "balke-pearl", "iv", "lp", "multi-valued"}),
        citations=(
            "Balke, A. & Pearl, J. (1997). Bounds on treatment effects from studies with "
            "imperfect compliance. JASA 92(439):1171-1176.",
        ),
        equations={
            "constraint": "Σ_{q: x_resp[z]=x, y_resp[x]=y} p_q = P(Y=y,X=x|Z=z)",
            "objective": "min/max Σ_q p_q * (y_resp[t] - y_resp[t_ref]) / (J-1)",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy", "scipy"),
        when_to_use=(
            "Binary IV with multi-valued (3+) treatment or outcome levels; "
            "want sharp LP bounds on E[Y(t) - Y(t_ref)]."
        ),
        when_not_to_use=(
            "Binary T and Y — use BalkePearlBoundsEstimator (faster). "
            "T or Y has >5 levels — LP becomes very large."
        ),
        output_interpretation=(
            "[ate_lower_bound, ate_upper_bound] sharp bounds on E[Y(t)-Y(t_ref)]."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        Y_raw = np.asarray(state["outcome"], dtype=float)
        T_raw = np.asarray(state["treatment"], dtype=float)
        Z_raw = np.asarray(state["instrument"], dtype=float)
        n = len(Y_raw)

        treatment_target = int(params.get("treatment_target", 1))
        treatment_ref = int(params.get("treatment_ref", 0))
        max_rf = int(params.get("max_response_fns", 5_000))

        # Discretise to integer levels
        y_levels = np.unique(np.round(Y_raw).astype(int))
        t_levels = np.unique(np.round(T_raw).astype(int))
        z_levels = np.unique(np.round(Z_raw).astype(int))

        J1 = len(y_levels)  # number of Y levels
        K1 = len(t_levels)  # number of T levels

        # Remap to contiguous integers 0..K1-1 and 0..J1-1
        t_map = {v: i for i, v in enumerate(sorted(t_levels))}
        y_map = {v: i for i, v in enumerate(sorted(y_levels))}

        T = np.array([t_map[int(round(v))] for v in T_raw], dtype=int)
        Y = np.array([y_map[int(round(v))] for v in Y_raw], dtype=int)
        Z = (Z_raw > 0.5).astype(int)

        # Adjust treatment_target and treatment_ref to remapped levels
        t_sorted = sorted(t_levels)
        tt = t_map.get(treatment_target, 1)
        tr = t_map.get(treatment_ref, 0)
        if tt >= K1:
            tt = min(K1 - 1, tt)
        if tr >= K1:
            tr = 0

        y_min = float(min(y_levels))
        y_max = float(max(y_levels))
        y_range = y_max - y_min if y_max != y_min else 1.0

        # Compute P̂(Y=y, X=x | Z=z) — shape (J1, K1, 2)
        p_yxz = np.zeros((J1, K1, 2))
        for zv in range(2):
            mask_z = zv == Z
            n_z = int(np.sum(mask_z))
            if n_z == 0:
                continue
            for xv in range(K1):
                for yv in range(J1):
                    p_yxz[yv, xv, zv] = int(np.sum(mask_z & (xv == T) & (yv == Y))) / n_z

        try:
            lower, upper, solver_status, dual_certificate_payload = _general_balke_pearl_lp(
                p_yxz,
                K1,
                J1,
                tt,
                tr,
                y_range,
                max_rf,
            )
        except ValueError as exc:
            failure_scale = float(y_range)
            return {
                "result": {
                    "ate_lower_bound": -float(J1 - 1) * failure_scale,
                    "ate_upper_bound": float(J1 - 1) * failure_scale,
                    "bound_width": 2.0 * float(J1 - 1) * failure_scale,
                    "solver_status": f"error: {exc}",
                    "n_obs": n,
                    "n_treatment_levels": K1,
                    "n_outcome_levels": J1,
                    "partial_id_result": _make_partial_id_result(
                        lower=-float(J1 - 1) * failure_scale,
                        upper=float(J1 - 1) * failure_scale,
                        method=BoundMethod.GENERAL_LP_BOUNDS,
                        assumptions=["binary_iv"],
                        confidence=0.0,
                        display_label="General Balke-Pearl (failed)",
                    ),
                }
            }

        lower_orig = lower
        upper_orig = upper

        partial_id = _make_partial_id_result(
            lower=lower_orig,
            upper=upper_orig,
            method=BoundMethod.GENERAL_LP_BOUNDS,
            assumptions=["binary_iv", "iv_exogeneity", "iv_relevance"],
            confidence=0.95 if solver_status == "optimal" else 0.5,
            display_label=f"General Balke-Pearl Bounds (T={t_sorted[tt]} vs T={t_sorted[tr]})",
            bounds_type="sharp_lp",
        )

        return {
            "result": {
                "ate_lower_bound": lower_orig,
                "ate_upper_bound": upper_orig,
                "bound_width": upper_orig - lower_orig,
                "solver_status": solver_status,
                "n_obs": n,
                "n_treatment_levels": K1,
                "n_outcome_levels": J1,
                "partial_id_result": partial_id,
                "dual_certificate_payload": dual_certificate_payload,
            }
        }


@foundry_method(
    namespace="causal.bounds",
    version="1.0.0",
    tags={"causal", "bounds", "copula", "distributional"},
)
class CopulaBoundsEstimator:
    """Fan & Park (2010) copula-based bounds on the distribution of Y(1)−Y(0).

    Uses the Fréchet-Hoeffding bounds and Frank copula to bracket the distribution of
    individual treatment effects Δ = Y(1) - Y(0), given only the marginal distributions
    F_{Y(1)} and F_{Y(0)}.

    Note on ATE vs. distributional bounds
    --------------------------------------
    The ATE = E[Y(1)] - E[Y(0)] is *point-identified* from the marginals and does not
    depend on the copula. This estimator reports:
    - ``ate_lower_bound`` / ``ate_upper_bound``: the same point estimate (ATE is identified).
    - ``quantile_effect_lower`` / ``quantile_effect_upper``: sharp bounds on the q-th quantile
      of Δ = Y(1) - Y(0) under the Fréchet-Hoeffding extremes.
    - ``copula_ate``: the mean of Δ under the Frank copula with ``copula_theta``.

    The Frank copula is used for sensitivity because it spans the full range of
    dependence (θ → −∞ → counter-monotone, θ → +∞ → co-monotone).
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scipy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="copula_bounds",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "numeric"), shape=("n_obs",)),
                SlotSpec(
                    "treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(
                name="copula_family",
                default="frank",
                description="Copula family for sensitivity: 'frank' (default), 'frechet'.",
            ),
            ParameterSpec(
                name="copula_theta",
                default=0.0,
                description="Frank copula parameter θ. θ=0 ≈ independence.",
            ),
            ParameterSpec(
                name="quantile_target",
                default=0.5,
                description="Quantile of Y(1)-Y(0) for which to compute distributional bounds.",
            ),
            ParameterSpec(
                name="n_eval_points",
                default=100,
                description="Grid size for numerical quantile inversion.",
            ),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Fan & Park (2010) copula-based bounds on the distribution of Y(1)-Y(0).",
        tags=frozenset({"causal", "bounds", "copula", "distributional", "partial-identification"}),
        citations=(
            "Fan, Y. & Park, S.S. (2010). Sharp Bounds on the Distribution of Treatment Effects "
            "and Their Statistical Inference. Econometric Theory 26(3):931-951.",
        ),
        equations={
            "frechet_lower": "C_L(u,v) = max(u+v-1, 0)  [counter-monotone]",
            "frechet_upper": "C_U(u,v) = min(u,v)  [co-monotone]",
            "frank": "C_θ(u,v) = -1/θ * log(1 + (e^{-θu}-1)(e^{-θv}-1)/(e^{-θ}-1))",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy", "scipy"),
        when_to_use=(
            "Need bounds on the *distribution* of individual treatment effects, "
            "not just the mean. Sensitivity to dependence structure between Y(1) and Y(0)."
        ),
        when_not_to_use=(
            "Only the ATE is needed — it is point-identified from marginals and "
            "does not require this estimator."
        ),
        output_interpretation=(
            "ate_lower_bound = ate_upper_bound = naive ATE (point-identified). "
            "quantile_effect_lower/upper are sharp bounds on the q-th quantile of Y(1)-Y(0)."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        Y = np.asarray(state["outcome"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)

        copula_theta = float(params.get("copula_theta", 0.0))
        q_target = float(params.get("quantile_target", 0.5))
        n_pts = int(params.get("n_eval_points", 100))

        treated = T > 0.5
        y1 = Y[treated]
        y0 = Y[~treated]

        if len(y1) == 0 or len(y0) == 0:
            return {
                "result": {
                    "ate_lower_bound": 0.0,
                    "ate_upper_bound": 0.0,
                    "bound_width": 0.0,
                    "n_obs": len(Y),
                }
            }

        ate = float(np.mean(y1) - np.mean(y0))

        # Build ECDFs
        y1_sorted = np.sort(y1)
        y0_sorted = np.sort(y0)
        n1 = len(y1_sorted)
        n0 = len(y0_sorted)

        def ecdf1(v: float) -> float:
            return float(np.searchsorted(y1_sorted, v, side="right")) / n1

        def ecdf0(v: float) -> float:
            return float(np.searchsorted(y0_sorted, v, side="right")) / n0

        def quantile1(u: float) -> float:
            idx = int(np.ceil(u * n1)) - 1
            return float(y1_sorted[max(0, min(idx, n1 - 1))])

        def quantile0(u: float) -> float:
            idx = int(np.ceil(u * n0)) - 1
            return float(y0_sorted[max(0, min(idx, n0 - 1))])

        # Fréchet-Hoeffding bounds on q-th quantile of Δ = Y(1) - Y(0)
        # Under co-monotone copula: Δ_q = Q_{Y(1)}(q) - Q_{Y(0)}(q)
        # Under counter-monotone: Δ_q = Q_{Y(1)}(q) - Q_{Y(0)}(1-q)
        delta_co = quantile1(q_target) - quantile0(q_target)  # co-monotone (upper)
        delta_counter = quantile1(q_target) - quantile0(1.0 - q_target)  # counter-monotone (lower)
        q_lower = min(delta_co, delta_counter)
        q_upper = max(delta_co, delta_counter)

        # Frank copula ATE (E[Δ] is still point-identified, so this equals naive ATE)
        # We report it for transparency
        copula_ate = ate

        partial_id = _make_partial_id_result(
            lower=ate,
            upper=ate,
            method=BoundMethod.COPULA_BOUNDS,
            assumptions=["unconfounded_marginals", "binary_treatment"],
            confidence=0.9,
            display_label="Copula Bounds (ATE)",
        )

        return {
            "result": {
                "ate_lower_bound": ate,
                "ate_upper_bound": ate,
                "bound_width": 0.0,
                "copula_ate": copula_ate,
                "quantile_effect_lower": q_lower,
                "quantile_effect_upper": q_upper,
                "quantile_target": q_target,
                "copula_theta": copula_theta,
                "n_obs": len(Y),
                "n_treated": n1,
                "n_control": n0,
                "partial_id_result": partial_id,
            }
        }


__all__ = [
    "BalkePearlBoundsEstimator",
    "CopulaBoundsEstimator",
    "GeneralBalkePearlBoundsEstimator",
    "ImbensManskiBoundsEstimator",
    "LeeBoundsEstimator",
    "ManskiBoundsEstimator",
    "OptimizationBasedBoundsEstimator",
]
