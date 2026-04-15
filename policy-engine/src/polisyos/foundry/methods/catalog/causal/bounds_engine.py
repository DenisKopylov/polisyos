"""BoundsEngine — orchestrated partial identification bounds selector.

Selects and runs the most appropriate bounds methods given the estimation
context, then aggregates the results into a BoundsReport.

Decision table:
  has_iv=True, binary instrument, has_multi_valued=False → BalkePearlBoundsEstimator + ImbensM
  has_iv=True, binary instrument, has_multi_valued=True  → GeneralBalkePearlBoundsEstimator
  has_iv=True, non-binary IV      → OptimizationBasedBoundsEstimator(assumption="miv") + Manski
  has_selection=True              → LeeBoundsEstimator + ManskiBoundsEstimator
  has_monotone=True               → OptimizationBasedBoundsEstimator(assumption="mtr") + Manski
  sensitivity_lambda=True         → TanBoundsEstimator sensitivity sweep
 run_all=True                    → all applicable methods
 run_intersection=True           → IntersectionBoundsEstimator on all accumulated results
  use_auto_bounds=True            → auto_bounds() as a first-pass bounds method
 default                         → ManskiBoundsEstimator + ImbensManskiBoundsEstimator

BoundsEngine calls inner estimators' pure_step() directly (same package;
no registry lookup at execution time — fast and testable in isolation).
"""
from __future__ import annotations

import json
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
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    BoundsReport,
    bounds_bundle_from_bounds_report,
    PartialIdentificationResult,
)

from polisyos.foundry.methods.catalog.causal.bounds import (
    BalkePearlBoundsEstimator,
    CopulaBoundsEstimator,
    GeneralBalkePearlBoundsEstimator,
    ImbensManskiBoundsEstimator,
    LeeBoundsEstimator,
    ManskiBoundsEstimator,
    OptimizationBasedBoundsEstimator,
)
from polisyos.foundry.methods.catalog.causal.lp_bounds import auto_bounds
from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import (
    IntersectionBoundsEstimator,
    TanBoundsEstimator,
)


def _extract_partial_id(result_dict: dict[str, Any]) -> PartialIdentificationResult | None:
    """Extract PartialIdentificationResult from a bounds estimator result dict."""
    inner = result_dict.get("result", {})
    pid = inner.get("partial_id_result")
    if pid is None:
        # Build one from ate_lower_bound / ate_upper_bound if present
        lb = inner.get("ate_lower_bound")
        ub = inner.get("ate_upper_bound")
        if lb is not None and ub is not None:
            return None  # will be built by caller with explicit method
        return None
    if isinstance(pid, PartialIdentificationResult):
        return pid
    if isinstance(pid, dict):
        return PartialIdentificationResult.model_validate(pid)
    return None


def _manski_partial_id(result_dict: dict[str, Any]) -> PartialIdentificationResult:
    """Build PartialIdentificationResult from ManskiBoundsEstimator output."""
    inner = result_dict.get("result", {})
    lb = float(inner.get("ate_lower_bound", -1.0))
    ub = float(inner.get("ate_upper_bound", 1.0))
    return PartialIdentificationResult(
        method=BoundMethod.MANSKI,
        lower_bound=lb,
        upper_bound=ub,
        confidence=0.9,
        assumptions_used=["no_assumptions_on_selection"],
        display_label="Manski Worst-Case Bounds",
    )


def _lee_partial_id(result_dict: dict[str, Any]) -> PartialIdentificationResult:
    """Build PartialIdentificationResult from LeeBoundsEstimator output."""
    inner = result_dict.get("result", {})
    lb = float(inner.get("ate_lower_bound", -1.0))
    ub = float(inner.get("ate_upper_bound", 1.0))
    return PartialIdentificationResult(
        method=BoundMethod.IV_BOUNDS,
        lower_bound=lb,
        upper_bound=ub,
        confidence=0.9,
        assumptions_used=["monotone_selection"],
        display_label="Lee Selection Bounds",
    )


@foundry_method(
    namespace="causal.bounds",
    version="1.0.0",
    tags={"causal", "bounds", "orchestration", "partial-identification"},
)
class BoundsEngineMethod:
    """Orchestrated bounds engine — selects and runs appropriate partial identification methods.

    Given the estimation context (presence of IV, selection indicator, monotone assumption),
    selects the best combination of bounds methods, runs them, and returns an aggregated
    BoundsReport with the tightest bounds and consensus interval.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="bounds_engine",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)
                ),
                SlotSpec(
                    "treatment", SlotType.VECTOR, Unit("treatment", "binary"), shape=("n_obs",)
                ),
                SlotSpec(
                    "instrument", SlotType.VECTOR, Unit("instrument", "binary"), shape=("n_obs",)
                ),
                SlotSpec(
                    "selected", SlotType.VECTOR, Unit("selection", "binary"), shape=("n_obs",)
                ),
                SlotSpec(
                    "miv_proxy", SlotType.VECTOR, Unit("instrument", "ordinal"), shape=("n_obs",)
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "bounds_report",
                    SlotType.SCALAR,
                    Unit("report", "json"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="y_lower", default=0.0),
            ParameterSpec(name="y_upper", default=1.0),
            ParameterSpec(name="alpha", default=0.05),
            ParameterSpec(
                name="has_iv",
                default=False,
                description="Whether an instrumental variable slot is expected.",
            ),
            ParameterSpec(
                name="has_selection",
                default=False,
                description="Whether a selection indicator slot is expected.",
            ),
            ParameterSpec(
                name="has_monotone",
                default=False,
                description="Whether a monotone treatment response assumption holds.",
            ),
            ParameterSpec(
                name="run_all",
                default=False,
                description="If True, run all applicable methods regardless of context.",
            ),
            ParameterSpec(
                name="informative_threshold",
                default=0.5,
                description=(
                    "Bounds are considered informative when tightest bound_width / "
                    "(y_upper - y_lower) < this threshold."
                ),
            ),
            ParameterSpec(
                name="has_multi_valued",
                default=False,
                description=(
                    "If True and has_iv=True with a binary IV, route to "
                    "GeneralBalkePearlBoundsEstimator instead of binary-only BalkePearlBoundsEstimator."
                ),
            ),
            ParameterSpec(
                name="run_intersection",
                default=False,
                description=(
                    "If True, run IntersectionBoundsEstimator on all accumulated bound results "
                    "after other methods complete."
                ),
            ),
            ParameterSpec(
                name="sensitivity_lambda",
                default=False,
                description="If True, run TanBoundsEstimator sensitivity sweep.",
            ),
            ParameterSpec(
                name="lambda_values",
                default=None,
                description="List of λ values for TanBoundsEstimator. None → default grid.",
            ),
            ParameterSpec(
                name="use_auto_bounds",
                default=True,
                description="If True, run auto_bounds() as a first-pass bounds method.",
            ),
            ParameterSpec(
                name="treatment_target",
                default=1.0,
                description="Target treatment level passed to auto_bounds().",
            ),
            ParameterSpec(
                name="treatment_ref",
                default=0.0,
                description="Reference treatment level passed to auto_bounds().",
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
            "Orchestrated partial identification bounds engine. Selects and runs "
            "Manski / Lee / Balke-Pearl / Imbens-Manski / MTR-MIV-MTS bounds based on "
            "estimation context and aggregates results into a BoundsReport."
        ),
        tags=frozenset(
            {"causal", "bounds", "partial-identification", "orchestration", "manski",
             "balke-pearl", "lee", "mtr", "miv"}
        ),
        citations=(
            "Manski, C.F. (1990). Nonparametric Bounds on Treatment Effects. AER P&P.",
            "Balke, A. & Pearl, J. (1997). Bounds on Treatment Effects. JASA.",
            "Lee, D.S. (2009). Training, Wages, and Sample Selection. ReStud.",
            "Imbens, G. & Manski, C. (2004). CIs for Partially Identified Parameters. Econometrica.",
            "Manski, C.F. & Pepper, J.V. (2000). Monotone Instrumental Variables. Econometrica.",
        ),
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use=(
            "Causal query is partially identified (MANSKI_BOUNDS strategy); "
            "need the tightest available bounds given available data."
        ),
        when_not_to_use=(
            "Point-identified estimand — use ATE/ATT estimators instead."
        ),
        output_interpretation=(
            "bounds_report: BoundsReport with tightest_lower/upper, consensus interval, "
            "is_informative flag, and list of all method results."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            from polisyos.ir.observation.contract_compilers import BoundsEstimationInput

            if isinstance(state, BoundsEstimationInput):
                state = state.model_dump(mode="python")
            else:
                raise TypeError("state must be a mapping or BoundsEstimationInput")
        Y = np.asarray(state["outcome"], dtype=float)
        T = np.asarray(state["treatment"], dtype=float)
        y_lo = float(params.get("y_lower", 0.0))
        y_hi = float(params.get("y_upper", 1.0))
        alpha = float(params.get("alpha", 0.05))
        has_iv = bool(params.get("has_iv", False))
        has_selection = bool(params.get("has_selection", False))
        has_monotone = bool(params.get("has_monotone", False))
        run_all = bool(params.get("run_all", False))
        informative_threshold = float(params.get("informative_threshold", 0.5))
        has_multi_valued = bool(params.get("has_multi_valued", False))
        run_intersection = bool(params.get("run_intersection", False))
        sensitivity_lambda = bool(params.get("sensitivity_lambda", False))
        lambda_values = params.get("lambda_values")
        use_auto_bounds = bool(params.get("use_auto_bounds", True))
        y_range = y_hi - y_lo if y_hi > y_lo else 1.0

        # Detect available optional slots
        Z_raw = state.get("instrument")
        S_raw = state.get("selected")
        M_raw = state.get("miv_proxy")

        has_instrument = Z_raw is not None
        has_selected = S_raw is not None

        base_params = {"y_lower": y_lo, "y_upper": y_hi}
        base_state = {"outcome": Y, "treatment": T}

        partial_id_results: list[PartialIdentificationResult] = []
        warnings: list[str] = []

        # --- Auto bounds (Phase 7 first-pass LP / relaxation) ---
        if use_auto_bounds:
            try:
                auto_pid = auto_bounds(
                    outcome=Y,
                    treatment=T,
                    instrument=(
                        None
                        if (not has_iv or Z_raw is None)
                        else np.asarray(Z_raw, dtype=float)
                    ),
                    target_treatment=float(params.get("treatment_target", 1.0)),
                    reference_treatment=float(params.get("treatment_ref", 0.0)),
                    constraints={"monotone": has_monotone},
                )
                partial_id_results.append(auto_pid)
            except Exception as exc:  # pragma: no cover - defensive fallback
                warnings.append(f"auto_bounds failed: {exc}")

        # --- Manski (always run — worst-case baseline) ---
        manski_out = ManskiBoundsEstimator.pure_step(base_state, base_params)
        partial_id_results.append(_manski_partial_id(manski_out))

        # --- Imbens-Manski CI (default; also run when no IV) ---
        if not has_iv or run_all:
            im_params = {**base_params, "alpha": alpha}
            im_out = ImbensManskiBoundsEstimator.pure_step(base_state, im_params)
            pid = _extract_partial_id(im_out)
            if pid is not None:
                partial_id_results.append(pid)

        # --- IV path ---
        if has_iv and has_instrument:
            Z = np.asarray(Z_raw, dtype=float)
            n_unique_z = len(np.unique(Z[np.isfinite(Z)]))
            is_binary_iv = n_unique_z <= 2

            if is_binary_iv and has_multi_valued:
                # Phase 7: multi-valued T or Y — use GeneralBalkePearlBoundsEstimator
                gbp_state = {**base_state, "instrument": Z}
                gbp_params = {
                    "treatment_target": int(params.get("treatment_target", 1)),
                    "treatment_ref": int(params.get("treatment_ref", 0)),
                    "max_response_fns": int(params.get("max_response_fns", 5_000)),
                }
                gbp_out = GeneralBalkePearlBoundsEstimator.pure_step(gbp_state, gbp_params)
                pid = _extract_partial_id(gbp_out)
                if pid is not None:
                    partial_id_results.append(pid)
            elif is_binary_iv:
                # Balke-Pearl sharp IV bounds (binary IV + treatment + outcome)
                bp_state = {**base_state, "instrument": Z}
                bp_out = BalkePearlBoundsEstimator.pure_step(bp_state, {"clip_probs": True})
                pid = _extract_partial_id(bp_out)
                if pid is not None:
                    partial_id_results.append(pid)
                # Also run Imbens-Manski for CI
                if run_all:
                    im_params = {**base_params, "alpha": alpha}
                    im_out = ImbensManskiBoundsEstimator.pure_step(base_state, im_params)
                    pid = _extract_partial_id(im_out)
                    if pid is not None:
                        partial_id_results.append(pid)
            else:
                # Non-binary IV → MIV bounds
                miv_state = {**base_state, "miv_proxy": Z}
                miv_params = {**base_params, "assumption": "miv", "n_strata": 5}
                miv_out = OptimizationBasedBoundsEstimator.pure_step(miv_state, miv_params)
                pid = _extract_partial_id(miv_out)
                if pid is not None:
                    partial_id_results.append(pid)
        elif has_iv and not has_instrument:
            warnings.append(
                "has_iv=True but 'instrument' slot not found in state; "
                "IV bounds skipped. Pass instrument data to enable Balke-Pearl bounds."
            )

        # --- Selection path (Lee bounds) ---
        if has_selection and has_selected:
            S = np.asarray(S_raw, dtype=float)
            lee_state = {**base_state, "selected": S}
            lee_out = LeeBoundsEstimator.pure_step(lee_state, {})
            partial_id_results.append(_lee_partial_id(lee_out))
        elif has_selection and not has_selected:
            warnings.append(
                "has_selection=True but 'selected' slot not found in state; "
                "Lee bounds skipped."
            )

        # --- Monotone Treatment Response path ---
        if has_monotone or run_all:
            mtr_params = {**base_params, "assumption": "mtr"}
            mtr_out = OptimizationBasedBoundsEstimator.pure_step(base_state, mtr_params)
            pid = _extract_partial_id(mtr_out)
            if pid is not None:
                partial_id_results.append(pid)

        # --- MIV with proxy if available (run_all path) ---
        if run_all and M_raw is not None:
            miv_state = {**base_state, "miv_proxy": np.asarray(M_raw, dtype=float)}
            miv_params = {**base_params, "assumption": "miv", "n_strata": 5}
            miv_out = OptimizationBasedBoundsEstimator.pure_step(miv_state, miv_params)
            pid = _extract_partial_id(miv_out)
            if pid is not None:
                partial_id_results.append(pid)

        # --- Phase 7: Tan sensitivity sweep ---
        if sensitivity_lambda:
            tan_state: dict[str, Any] = {**base_state}
            ps_raw = state.get("propensity_scores")
            if ps_raw is not None:
                tan_state["propensity_scores"] = ps_raw
            tan_params: dict[str, Any] = {}
            if lambda_values is not None:
                tan_params["lambda_values"] = lambda_values
            tan_out = TanBoundsEstimator.pure_step(tan_state, tan_params)
            pid = _extract_partial_id(tan_out)
            if pid is not None:
                partial_id_results.append(pid)

        # --- Phase 7: Intersection bounds (after all other methods) ---
        if run_intersection and len(partial_id_results) >= 2:
            bounds_list = [
                {
                    "ate_lower_bound": r.lower_bound,
                    "ate_upper_bound": r.upper_bound,
                    "se": 0.0,
                }
                for r in partial_id_results
            ]
            ib_out = IntersectionBoundsEstimator.pure_step(
                {"bounds_list": bounds_list},
                {"alpha": alpha, "n_obs": len(Y), "use_clr_bootstrap": False},
            )
            ib_pid = _extract_partial_id(ib_out)
            if ib_pid is not None:
                partial_id_results.append(ib_pid)

        # Check if bounds are vacuous (empty consensus)
        if len(partial_id_results) > 1:
            consensus_lo = max(r.lower_bound for r in partial_id_results)
            consensus_hi = min(r.upper_bound for r in partial_id_results)
            if consensus_lo > consensus_hi:
                warnings.append(
                    "Consensus interval is empty — partial identification is vacuous; "
                    "NegativeCertificate recommended."
                )

        # Check informativeness of tightest bound
        if partial_id_results:
            tightest = min(partial_id_results, key=lambda r: r.bound_width)
            if tightest.bound_width > informative_threshold * y_range:
                warnings.append(
                    f"Tightest bound width ({tightest.bound_width:.3f}) exceeds "
                    f"informative threshold ({informative_threshold:.1%} × y_range={y_range:.3f}). "
                    "Bounds may be too wide to guide policy decisions."
                )

        # Aggregate all assumptions
        all_assumptions: list[str] = []
        seen: set[str] = set()
        for r in partial_id_results:
            for a in r.assumptions_used:
                if a not in seen:
                    all_assumptions.append(a)
                    seen.add(a)

        report = BoundsReport(
            run_id=str(params.get("run_id", "")),
            estimand_type="ate",
            results=partial_id_results,
            assumptions_used=all_assumptions,
            warnings=warnings,
        )
        bundle = bounds_bundle_from_bounds_report(
            report,
            rescue_actions=[
                "Collect stronger design information or additional instruments to tighten bounds."
            ],
            metadata={
                "run_id": report.run_id,
                "legacy_tightest_method": (
                    report.tightest_method.value if report.tightest_method is not None else None
                ),
                "n_methods": len(report.results),
            },
        )

        return {
            "bounds_report": bundle.model_dump(mode="json"),
        }


__all__ = ["BoundsEngineMethod"]
