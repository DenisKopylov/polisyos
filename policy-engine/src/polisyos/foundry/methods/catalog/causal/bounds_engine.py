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

from collections.abc import Mapping
from typing import Any, ClassVar

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
from polisyos.foundry.methods.catalog.causal.bounds import (
    BalkePearlBoundsEstimator,
    GeneralBalkePearlBoundsEstimator,
    ImbensManskiBoundsEstimator,
    LeeBoundsEstimator,
    ManskiBoundsEstimator,
    OptimizationBasedBoundsEstimator,
)
from polisyos.foundry.methods.catalog.causal.lp_bounds import (
    auto_bounds_with_metadata,
    conditional_auto_bounds_with_metadata,
)
from polisyos.foundry.methods.catalog.causal.model_class_compatibility import (
    check_model_class_compatibility,
)
from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import (
    IntersectionBoundsEstimator,
    TanBoundsEstimator,
)
from polisyos.ir.analytics.certified_tightening import build_certified_tightening_claim
from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    BoundsMethodSummary,
    BoundsReport,
    BoundTighteningLogEntry,
    PartialIdentificationResult,
    TighteningStatus,
    bounds_bundle_from_bounds_report,
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


def _annotate_method_summaries(
    summaries: list[BoundsMethodSummary],
    annotations: list[dict[str, Any]],
) -> list[BoundsMethodSummary]:
    if len(summaries) != len(annotations):
        return summaries
    return [
        summary.model_copy(update=annotation)
        for summary, annotation in zip(summaries, annotations, strict=False)
    ]


def _conditioning_candidates(
    state: Mapping[str, Any],
    params: Mapping[str, Any],
    *,
    n_obs: int,
) -> list[tuple[str, np.ndarray]]:
    metadata = state.get("metadata")
    metadata_map = metadata if isinstance(metadata, Mapping) else {}
    raw = (
        params.get("conditioning_variables")
        or params.get("conditioning")
        or state.get("conditioning_variables")
        or state.get("conditioning")
        or metadata_map.get("conditioning_variables")
        or metadata_map.get("conditioning")
    )
    candidates: list[tuple[str, np.ndarray]] = []
    if raw is None:
        return candidates
    if isinstance(raw, Mapping):
        iterable = raw.items()
    else:
        iterable = [("conditioning", raw)]
    for name, values in iterable:
        arr = np.asarray(values, dtype=float).reshape(-1)
        if arr.size == n_obs:
            candidates.append((str(name), arr))
    return candidates


def _as_thresholds(value: Any) -> list[float]:
    if value is None:
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    try:
        return [float(item) for item in value]
    except TypeError:
        return []


def _tightening_assumptions(
    state: Mapping[str, Any],
    params: Mapping[str, Any],
    *,
    has_monotone: bool,
) -> list[str]:
    metadata = state.get("metadata")
    metadata_map = metadata if isinstance(metadata, Mapping) else {}
    raw = (
        params.get("tightening_assumptions")
        or state.get("tightening_assumptions")
        or metadata_map.get("tightening_assumptions")
    )
    if raw is None:
        return []
    if isinstance(raw, str):
        items = [raw]
    else:
        items = [str(item) for item in raw]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        token = str(item).strip().lower()
        if token in {"mtr", "monotone", "monotone_treatment_response"} and not has_monotone:
            canonical = "monotone_treatment_response"
            if canonical not in seen:
                normalized.append(canonical)
                seen.add(canonical)
    return normalized


def _tightening_log_entry(
    *,
    method: BoundMethod,
    status: str,
    reason: str,
    candidate_name: str,
    lower_bound: float | None = None,
    upper_bound: float | None = None,
    bound_width: float | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> BoundTighteningLogEntry:
    return BoundTighteningLogEntry(
        method=method,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        bound_width=bound_width,
        status=status,
        reason=reason,
        metadata={
            "candidate_name": candidate_name,
            **dict(metadata or {}),
        },
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
                SlotSpec("outcome", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
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
                name="tighten_bounds",
                default=False,
                description=(
                    "If True, run certified finite-class tightening and exclude uncertified "
                    "auto_bounds candidates from the headline bundle."
                ),
            ),
            ParameterSpec(
                name="tightening_assumptions",
                default=None,
                description=(
                    "Optional finite assumption family for certified tightening, "
                    "for example ['mtr']."
                ),
            ),
            ParameterSpec(
                name="instrument_family_thresholds",
                default=None,
                description=(
                    "Finite threshold family for binary IV transformations used only "
                    "by certified tightening."
                ),
            ),
            ParameterSpec(
                name="tightening_candidate_limit",
                default=None,
                description=(
                    "Optional hard cap on generated tightening candidates; when hit, "
                    "certified tightening stops with budget_exceeded."
                ),
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
            {
                "causal",
                "bounds",
                "partial-identification",
                "orchestration",
                "manski",
                "balke-pearl",
                "lee",
                "mtr",
                "miv",
            }
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
        when_not_to_use=("Point-identified estimand — use ATE/ATT estimators instead."),
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
        tighten_bounds = bool(params.get("tighten_bounds", False))
        y_range = y_hi - y_lo if y_hi > y_lo else 1.0

        # Detect available optional slots
        Z_raw = state.get("instrument")
        S_raw = state.get("selected")
        M_raw = state.get("miv_proxy")

        has_instrument = Z_raw is not None
        has_selected = S_raw is not None

        base_params = {"y_lower": y_lo, "y_upper": y_hi}
        base_state = {"outcome": Y, "treatment": T}
        tightening_assumptions = _tightening_assumptions(
            state,
            params,
            has_monotone=has_monotone,
        )
        conditioning_candidates = _conditioning_candidates(state, params, n_obs=len(Y))
        instrument_family_thresholds = _as_thresholds(params.get("instrument_family_thresholds"))
        tightening_candidate_limit_raw = params.get("tightening_candidate_limit")
        tightening_candidate_limit = (
            None
            if tightening_candidate_limit_raw in (None, "")
            else max(int(tightening_candidate_limit_raw), 0)
        )

        partial_id_results: list[PartialIdentificationResult] = []
        certificate_candidates: list[tuple[PartialIdentificationResult, dict[str, Any]]] = []
        tightening_log_entries: list[BoundTighteningLogEntry] = []
        warnings: list[str] = []
        negative_certificate_payload: dict[str, Any] | None = None
        model_class_compatibility_payload: dict[str, Any] | None = None
        auto_pid: PartialIdentificationResult | None = None
        auto_payload: dict[str, Any] = {}
        generated_tightener_count = 0
        generated_tightener_certified_count = 0
        tightening_infeasible_count = 0
        budget_exhausted = False

        def _reserve_tightening_budget(
            *,
            method: BoundMethod,
            candidate_name: str,
            metadata: Mapping[str, Any] | None = None,
        ) -> bool:
            nonlocal generated_tightener_count, budget_exhausted
            if (
                tightening_candidate_limit is not None
                and generated_tightener_count >= tightening_candidate_limit
            ):
                budget_exhausted = True
                tightening_log_entries.append(
                    _tightening_log_entry(
                        method=method,
                        status="skipped",
                        reason="budget_exceeded",
                        candidate_name=candidate_name,
                        metadata=metadata,
                    )
                )
                return False
            generated_tightener_count += 1
            return True

        # --- Auto bounds (Phase 7 first-pass LP / relaxation) ---
        if use_auto_bounds:
            try:
                auto_pid, auto_payload = auto_bounds_with_metadata(
                    outcome=Y,
                    treatment=T,
                    instrument=(
                        None if (not has_iv or Z_raw is None) else np.asarray(Z_raw, dtype=float)
                    ),
                    target_treatment=float(params.get("treatment_target", 1.0)),
                    reference_treatment=float(params.get("treatment_ref", 0.0)),
                    constraints={"monotone": has_monotone},
                )
                candidate_payload = auto_payload.get("dual_certificate_payload")
                auto_has_certificate = isinstance(candidate_payload, dict)
                include_auto_result = not tighten_bounds or auto_has_certificate
                if include_auto_result:
                    partial_id_results.append(auto_pid)
                else:
                    warnings.append("auto_bounds_excluded_from_headline_bundle_without_certificate")
                if isinstance(candidate_payload, dict):
                    certificate_candidates.append((auto_pid, candidate_payload))
            except Exception as exc:  # pragma: no cover - defensive fallback
                warnings.append(f"auto_bounds failed: {exc}")

        if tighten_bounds:
            for assumption_name in tightening_assumptions:
                candidate_name = f"assumption:{assumption_name}"
                if not _reserve_tightening_budget(
                    method=BoundMethod.GENERAL_LP_BOUNDS,
                    candidate_name=candidate_name,
                    metadata={"assumption_name": assumption_name},
                ):
                    continue
                try:
                    assumed_pid, assumed_metadata = auto_bounds_with_metadata(
                        outcome=Y,
                        treatment=T,
                        target_treatment=float(params.get("treatment_target", 1.0)),
                        reference_treatment=float(params.get("treatment_ref", 0.0)),
                        constraints={"monotone": assumption_name == "monotone_treatment_response"},
                    )
                    candidate_payload = assumed_metadata.get("dual_certificate_payload")
                    if isinstance(candidate_payload, dict):
                        assumed_pid = assumed_pid.model_copy(
                            update={
                                "display_label": "Monotone treatment-response LP bounds",
                                "assumptions_used": [
                                    *assumed_pid.assumptions_used,
                                    "assumption_card:monotone_treatment_response",
                                ],
                            }
                        )
                        partial_id_results.append(assumed_pid)
                        certificate_candidates.append((assumed_pid, candidate_payload))
                        generated_tightener_certified_count += 1
                    else:
                        solver_status = str(
                            assumed_metadata.get("solver_status", "missing_solver_status")
                        )
                        is_infeasible = solver_status.startswith("infeasible(")
                        if is_infeasible:
                            tightening_infeasible_count += 1
                        warnings.append(
                            f"assumption_candidate_{'infeasible' if is_infeasible else 'uncertified'}:{assumption_name}"
                        )
                        tightening_log_entries.append(
                            _tightening_log_entry(
                                method=BoundMethod.GENERAL_LP_BOUNDS,
                                status="infeasible" if is_infeasible else "uncertified",
                                reason=(
                                    "candidate_infeasible_under_added_assumption"
                                    if is_infeasible
                                    else "missing_machine_checkable_certificate"
                                ),
                                candidate_name=candidate_name,
                                metadata={
                                    "assumption_name": assumption_name,
                                    "solver_status": solver_status,
                                },
                            )
                        )
                except Exception as exc:
                    warnings.append(
                        f"assumption_candidate_failed:{assumption_name}:{exc.__class__.__name__}"
                    )
                    tightening_log_entries.append(
                        _tightening_log_entry(
                            method=BoundMethod.GENERAL_LP_BOUNDS,
                            status="uncertified",
                            reason=f"candidate_failed:{exc.__class__.__name__}",
                            candidate_name=candidate_name,
                            metadata={"assumption_name": assumption_name},
                        )
                    )

            for conditioning_name, conditioning in conditioning_candidates:
                candidate_name = f"conditioning:{conditioning_name}"
                if not _reserve_tightening_budget(
                    method=BoundMethod.GENERAL_LP_BOUNDS,
                    candidate_name=candidate_name,
                    metadata={"conditioning_name": conditioning_name},
                ):
                    continue
                try:
                    conditioned = conditional_auto_bounds_with_metadata(
                        outcome=Y,
                        treatment=T,
                        conditioning=conditioning,
                        target_treatment=float(params.get("treatment_target", 1.0)),
                        reference_treatment=float(params.get("treatment_ref", 0.0)),
                        constraints={"monotone": has_monotone},
                    )
                    if conditioned is None:
                        warnings.append(f"conditioning_candidate_uncertified:{conditioning_name}")
                        tightening_log_entries.append(
                            _tightening_log_entry(
                                method=BoundMethod.GENERAL_LP_BOUNDS,
                                status="uncertified",
                                reason="conditioning_candidate_not_certifiable",
                                candidate_name=candidate_name,
                                metadata={"conditioning_name": conditioning_name},
                            )
                        )
                        continue
                    conditioned_pid, conditioned_payload = conditioned
                    conditioned_pid = conditioned_pid.model_copy(
                        update={
                            "display_label": (
                                f"Conditioned response-function LP bounds ({conditioning_name})"
                            ),
                            "assumptions_used": [
                                *conditioned_pid.assumptions_used,
                                f"condition_on:{conditioning_name}",
                            ],
                        }
                    )
                    partial_id_results.append(conditioned_pid)
                    candidate_payload = conditioned_payload.get("dual_certificate_payload")
                    if isinstance(candidate_payload, dict):
                        certificate_candidates.append((conditioned_pid, candidate_payload))
                        generated_tightener_certified_count += 1
                    else:
                        warnings.append(f"conditioning_candidate_uncertified:{conditioning_name}")
                        tightening_log_entries.append(
                            _tightening_log_entry(
                                method=BoundMethod.GENERAL_LP_BOUNDS,
                                status="uncertified",
                                reason="missing_machine_checkable_certificate",
                                candidate_name=candidate_name,
                                metadata={"conditioning_name": conditioning_name},
                            )
                        )
                except Exception as exc:
                    warnings.append(
                        f"conditioning_candidate_failed:{conditioning_name}:{exc.__class__.__name__}"
                    )
                    tightening_log_entries.append(
                        _tightening_log_entry(
                            method=BoundMethod.GENERAL_LP_BOUNDS,
                            status="uncertified",
                            reason=f"candidate_failed:{exc.__class__.__name__}",
                            candidate_name=candidate_name,
                            metadata={"conditioning_name": conditioning_name},
                        )
                    )

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
            binary_iv_incompatible = False
            if is_binary_iv and not has_multi_valued:
                try:
                    compatibility = check_model_class_compatibility(
                        model_class_id="iv.binary.unconditional",
                        data=np.column_stack(
                            [
                                (Z > 0.5).astype(float),
                                (T > 0.5).astype(float),
                                (Y > 0.5).astype(float),
                            ]
                        ),
                        variable_names=["Z", "X", "Y"],
                        observed_variables=["Z", "X", "Y"],
                        alpha=alpha,
                        multiple_testing="holm",
                    )
                except ValueError as exc:
                    compatibility = None
                    binary_iv_incompatible = True
                    warnings.append(
                        f"binary_iv_model_class_check_failed:{exc.__class__.__name__}:{exc}"
                    )
                if compatibility is not None:
                    model_class_compatibility_payload = compatibility.report.model_dump(mode="json")
                    if compatibility.status == "incompatible":
                        binary_iv_incompatible = True
                        warnings.append(
                            "binary_iv_model_class_incompatible:blocked_balke_pearl_under_declared_iv_class"
                        )
                        if compatibility.negative_certificate is not None:
                            negative_certificate_payload = (
                                compatibility.negative_certificate.model_dump(mode="json")
                            )
            if tighten_bounds:
                for threshold in instrument_family_thresholds:
                    candidate_name = f"instrument_threshold:{threshold:g}"
                    try:
                        z_binary = (threshold < Z).astype(float)
                        if len(np.unique(z_binary[np.isfinite(z_binary)])) < 2:
                            warnings.append(
                                f"instrument_family_candidate_degenerate:threshold={threshold:g}"
                            )
                            tightening_log_entries.append(
                                _tightening_log_entry(
                                    method=BoundMethod.LP_BALKE_PEARL,
                                    status="skipped",
                                    reason="degenerate_binary_instrument_transform",
                                    candidate_name=candidate_name,
                                    metadata={"threshold": threshold},
                                )
                            )
                            continue
                        if not _reserve_tightening_budget(
                            method=BoundMethod.LP_BALKE_PEARL,
                            candidate_name=candidate_name,
                            metadata={"threshold": threshold},
                        ):
                            continue
                        candidate_pid, candidate_metadata = auto_bounds_with_metadata(
                            outcome=Y,
                            treatment=T,
                            instrument=z_binary,
                            target_treatment=float(params.get("treatment_target", 1.0)),
                            reference_treatment=float(params.get("treatment_ref", 0.0)),
                            constraints={"monotone": has_monotone},
                        )
                        candidate_payload = candidate_metadata.get("dual_certificate_payload")
                        if not isinstance(candidate_payload, dict):
                            solver_status = str(
                                candidate_metadata.get("solver_status", "missing_solver_status")
                            )
                            is_infeasible = solver_status.startswith("infeasible(")
                            if is_infeasible:
                                tightening_infeasible_count += 1
                            warnings.append(
                                f"instrument_family_candidate_"
                                f"{'infeasible' if is_infeasible else 'uncertified'}:"
                                f"threshold={threshold:g}"
                            )
                            tightening_log_entries.append(
                                _tightening_log_entry(
                                    method=BoundMethod.LP_BALKE_PEARL,
                                    status="infeasible" if is_infeasible else "uncertified",
                                    reason=(
                                        "candidate_infeasible_under_instrument_family"
                                        if is_infeasible
                                        else "missing_machine_checkable_certificate"
                                    ),
                                    candidate_name=candidate_name,
                                    metadata={
                                        "threshold": threshold,
                                        "solver_status": solver_status,
                                    },
                                )
                            )
                            continue
                        candidate_pid = candidate_pid.model_copy(
                            update={
                                "display_label": (
                                    "Instrument-family Balke-Pearl bounds "
                                    f"(threshold={threshold:g})"
                                ),
                                "assumptions_used": [
                                    *candidate_pid.assumptions_used,
                                    f"instrument_threshold:{threshold:g}",
                                ],
                            }
                        )
                        partial_id_results.append(candidate_pid)
                        certificate_candidates.append((candidate_pid, candidate_payload))
                        generated_tightener_certified_count += 1
                    except Exception as exc:
                        warnings.append(
                            f"instrument_family_candidate_failed:threshold={threshold:g}:"
                            f"{exc.__class__.__name__}"
                        )
                        tightening_log_entries.append(
                            _tightening_log_entry(
                                method=BoundMethod.LP_BALKE_PEARL,
                                status="uncertified",
                                reason=f"candidate_failed:{exc.__class__.__name__}",
                                candidate_name=candidate_name,
                                metadata={"threshold": threshold},
                            )
                        )

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
                    candidate_payload = gbp_out.get("result", {}).get("dual_certificate_payload")
                    if isinstance(candidate_payload, dict):
                        certificate_candidates.append((pid, candidate_payload))
            elif is_binary_iv and not binary_iv_incompatible:
                # Balke-Pearl sharp IV bounds (binary IV + treatment + outcome)
                bp_state = {**base_state, "instrument": Z}
                bp_out = BalkePearlBoundsEstimator.pure_step(bp_state, {"clip_probs": True})
                pid = _extract_partial_id(bp_out)
                if pid is not None:
                    partial_id_results.append(pid)
                    candidate_payload = bp_out.get("result", {}).get("dual_certificate_payload")
                    if isinstance(candidate_payload, dict):
                        certificate_candidates.append((pid, candidate_payload))
                # Also run Imbens-Manski for CI
                if run_all:
                    im_params = {**base_params, "alpha": alpha}
                    im_out = ImbensManskiBoundsEstimator.pure_step(base_state, im_params)
                    pid = _extract_partial_id(im_out)
                    if pid is not None:
                        partial_id_results.append(pid)
            elif is_binary_iv:
                warnings.append("binary_iv_bounds_skipped_due_to_model_class_incompatibility")
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
                "has_selection=True but 'selected' slot not found in state; Lee bounds skipped."
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
        selected_certificate_payload = None
        if partial_id_results:
            tightest = min(partial_id_results, key=lambda item: item.bound_width)
            for candidate_pid, candidate_payload in certificate_candidates:
                if candidate_pid == tightest:
                    selected_certificate_payload = candidate_payload
                    break
            if tightest.bounds_type == "sharp_lp" and selected_certificate_payload is None:
                bundle_warnings = list(bundle.warnings)
                bundle_warnings.append("tightest_sharp_lp_missing_dual_certificate")
                bundle = bundle.model_copy(update={"warnings": bundle_warnings})

        tightening_claim = None
        if partial_id_results:
            all_tighteners_infeasible = (
                generated_tightener_count > 0
                and generated_tightener_certified_count == 0
                and tightening_infeasible_count == generated_tightener_count
            )
            tightening_claim, annotations, certified_payload = build_certified_tightening_claim(
                partial_id_results,
                certificate_candidates,
                class_spec={
                    "tightening_assumptions": list(tightening_assumptions),
                    "conditioning_candidates": [name for name, _ in conditioning_candidates],
                    "instrument_family_thresholds": list(instrument_family_thresholds),
                    "tightening_candidate_limit": tightening_candidate_limit,
                },
                extra_log_entries=tightening_log_entries,
                budget_exhausted=budget_exhausted,
                all_tighteners_infeasible=all_tighteners_infeasible,
                generated_tightener_count=generated_tightener_count,
                generated_tightener_certified_count=generated_tightener_certified_count,
            )
            bundle_metadata = dict(bundle.metadata)
            bundle_metadata.update(
                {
                    "certified_tightening_class": tightening_claim.class_name,
                    "certified_tightening_proof_note": tightening_claim.proof_note,
                    "certified_tightening_generated_candidate_count": generated_tightener_count,
                    "certified_tightening_generated_certified_count": (
                        generated_tightener_certified_count
                    ),
                }
            )
            bundle_updates: dict[str, Any] = {
                "method_summaries": _annotate_method_summaries(
                    bundle.method_summaries, annotations
                ),
                "metadata": bundle_metadata,
            }
            if tighten_bounds:
                bundle_updates["tightening_status"] = tightening_claim.status
                bundle_updates["tightening_stop_reason"] = tightening_claim.stop_reason
                bundle_updates["best_in_class_claim"] = tightening_claim
                if (
                    tightening_claim.status is TighteningStatus.IMPROVED
                    and tightening_claim.lower_bound is not None
                    and tightening_claim.upper_bound is not None
                ):
                    legacy_lower = bundle.lower_bound
                    legacy_upper = bundle.upper_bound
                    bundle_metadata.update(
                        {
                            "legacy_tightest_lower": legacy_lower,
                            "legacy_tightest_upper": legacy_upper,
                            "selected_method": (
                                tightening_claim.selected_method.value
                                if tightening_claim.selected_method is not None
                                else None
                            ),
                        }
                    )
                    bundle_updates.update(
                        {
                            "lower_bound": tightening_claim.lower_bound,
                            "upper_bound": tightening_claim.upper_bound,
                            "point_identified": (
                                abs(tightening_claim.upper_bound - tightening_claim.lower_bound)
                                <= 1e-12
                            ),
                            "metadata": bundle_metadata,
                        }
                    )
                    if certified_payload is not None:
                        selected_certificate_payload = certified_payload
            bundle = bundle.model_copy(update=bundle_updates)

        response: dict[str, Any] = {
            "bounds_report": bundle.model_dump(mode="json"),
        }
        if selected_certificate_payload is not None:
            response["dual_certificate_payload"] = selected_certificate_payload
        if negative_certificate_payload is not None:
            response["negative_certificate"] = negative_certificate_payload
        if model_class_compatibility_payload is not None:
            response["model_class_compatibility"] = model_class_compatibility_payload
        return response


__all__ = ["BoundsEngineMethod"]
