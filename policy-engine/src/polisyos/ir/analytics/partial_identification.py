"""DOD-135: Partial identification with Manski bounds."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import BoundsBundleRef, BoundsTighteningLogRef, DualCertificateRef


class BoundMethod(str, Enum):
    """Bound method public type."""
    MANSKI = "manski_bounds"
    TRANSPORT_BOUNDS = "transport_bounds"
    DP_ROBUSTNESS = "dp_robustness_bounds"
    IV_BOUNDS = "iv_bounds"
    MONOTONE_TREATMENT = "monotone_treatment"
    LP_BALKE_PEARL = "lp_balke_pearl"
    IMBENS_MANSKI_CI = "imbens_manski_ci"
    MTR_BOUNDS = "mtr_bounds"
    """Monotone Treatment Response LP bounds (Manski 1997)."""
    MIV_BOUNDS = "miv_bounds"
    """Monotone Instrumental Variable bounds (Manski & Pepper 2000)."""
    MTS_BOUNDS = "mts_bounds"
    """Monotone Treatment Selection LP bounds."""
    GENERAL_LP_BOUNDS = "general_lp_bounds"
    """Generalised Balke-Pearl LP for multi-valued T/Y, binary Z (Balke & Pearl 1997 §4)."""
    COPULA_BOUNDS = "copula_bounds"
    """Fan & Park (2010) sharp bounds on the distribution of Y(1)−Y(0)."""
    TAN_BOUNDS = "tan_bounds"
    """Tan (2006, JASA) sensitivity sweep under Marginal Sensitivity Model."""
    INTERSECTION_BOUNDS = "intersection_bounds"
    """Chernozhukov, Lee & Rosen (2013) intersection of multiple identified sets."""
    ROSENBAUM_SHARP = "rosenbaum_sharp"
    """Sharp per-γ p-value bounds for matched pairs (Rosenbaum 2002)."""


class BoundSoundnessLevel(str, Enum):
    """Soundness tier for one bounds result."""

    CERTIFIED = "CERTIFIED"
    ASSUMPTION_ONLY = "ASSUMPTION_ONLY"
    HEURISTIC = "HEURISTIC"


class TighteningStatus(str, Enum):
    """Outcome of certified bound tightening."""

    NOT_RUN = "not_run"
    IMPROVED = "improved"
    EXHAUSTED_NO_IMPROVEMENT = "exhausted_no_improvement"
    INCOMPLETE = "incomplete"
    BLOCKED = "blocked"


class TighteningStopReason(str, Enum):
    """Formal stopping reasons for certified tightening."""

    EXHAUSTED_CLASS_NO_IMPROVEMENT = "exhausted_class_no_improvement"
    CLASS_NOT_CERTIFIABLE_WITH_BACKEND = "class_not_certifiable_with_backend"
    MODEL_INFEASIBLE_UNDER_ALL_TIGHTENERS = "model_infeasible_under_all_tighteners"
    BUDGET_EXCEEDED = "budget_exceeded"
    NOT_RUN = "not_run"


class PartialIdentificationResult(BaseModel):
    """Result of partial identification analysis (e.g., Manski bounds on ATE)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    method: BoundMethod
    lower_bound: float
    upper_bound: float
    bound_width: float = 0.0
    is_informative: bool = True
    confidence: float = Field(ge=0.0, le=1.0)
    assumptions_used: list[str] = Field(default_factory=list)
    assumptions_violated: list[str] = Field(default_factory=list)
    informativeness_threshold: float = 0.5
    bounds_type: Literal["sharp_lp", "relaxed_polynomial", "manski"] = "manski"
    relaxation_gap: float | None = None
    discretization_method: str | None = None
    n_bins_final: int | None = Field(default=None, ge=1)
    discretization_converged: bool | None = None
    n_refinement_steps: int = Field(default=0, ge=0)
    display_label: str = ""
    """Human-readable label for UI display, e.g. 'Manski Worst-Case Bounds'."""
    chart_type: str = "interval"
    """Visualization hint: 'interval' | 'density' | 'scatter'."""
    certificate_ref: DualCertificateRef | BoundsTighteningLogRef | None = None
    certificate_kind: str | None = None
    soundness_level: BoundSoundnessLevel | None = None
    solver_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _compute_derived(self) -> "PartialIdentificationResult":
        width = self.upper_bound - self.lower_bound
        informative = width < self.informativeness_threshold
        object.__setattr__(self, "bound_width", width)
        object.__setattr__(self, "is_informative", informative)
        return self

    def to_ui_dict(self) -> dict:
        """Return a JSON-serializable dict for frontend rendering."""
        return {
            "lower": self.lower_bound,
            "upper": self.upper_bound,
            "width": self.bound_width,
            "method": self.method.value,
            "is_informative": self.is_informative,
            "confidence": self.confidence,
            "bounds_type": self.bounds_type,
            "relaxation_gap": self.relaxation_gap,
            "discretization_method": self.discretization_method,
            "n_bins_final": self.n_bins_final,
            "discretization_converged": self.discretization_converged,
            "n_refinement_steps": self.n_refinement_steps,
            "display_label": self.display_label or self.method.value,
            "chart_type": self.chart_type,
            "certificate_kind": self.certificate_kind,
            "soundness_level": (
                self.soundness_level.value if self.soundness_level is not None else None
            ),
        }


class BoundsReport(BaseModel):
    """Aggregated result from running multiple partial identification methods.

    Computes the tightest method (argmin bound_width) and the consensus interval
    (intersection of all bound intervals).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    run_id: str = ""
    estimand_type: str = "ate"
    results: list[PartialIdentificationResult]
    """One PartialIdentificationResult per bounds method that was run."""
    tightest_method: BoundMethod | None = None
    """Method with the smallest bound_width."""
    tightest_lower: float | None = None
    tightest_upper: float | None = None
    consensus_lower: float | None = None
    """max(all lower_bounds) — tightest lower bound across all methods."""
    consensus_upper: float | None = None
    """min(all upper_bounds) — tightest upper bound across all methods."""
    assumptions_used: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    is_informative: bool = False
    """True when the tightest bound_width < informative_threshold * (y_max - y_min)."""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _compute_derived(self) -> "BoundsReport":
        if not self.results:
            return self
        # Tightest: argmin bound_width
        tightest = min(self.results, key=lambda r: r.bound_width)
        object.__setattr__(self, "tightest_method", tightest.method)
        object.__setattr__(self, "tightest_lower", tightest.lower_bound)
        object.__setattr__(self, "tightest_upper", tightest.upper_bound)
        # Consensus: intersection of all intervals
        object.__setattr__(self, "consensus_lower", max(r.lower_bound for r in self.results))
        object.__setattr__(self, "consensus_upper", min(r.upper_bound for r in self.results))
        # Informative: tightest_lower != tightest_upper (some information gained)
        object.__setattr__(self, "is_informative", tightest.is_informative)
        return self

    def to_ui_dict(self) -> dict:
        """Return a JSON-serializable dict for frontend rendering."""
        return {
            "estimand_type": self.estimand_type,
            "tightest_method": self.tightest_method.value if self.tightest_method else None,
            "tightest_lower": self.tightest_lower,
            "tightest_upper": self.tightest_upper,
            "consensus_lower": self.consensus_lower,
            "consensus_upper": self.consensus_upper,
            "is_informative": self.is_informative,
            "n_methods": len(self.results),
            "warnings": self.warnings,
        }


class SensitivitySweepResult(BaseModel):
    """Bounds expressed as a function of a sensitivity parameter (γ or λ).

    Captures the entire sensitivity sweep so the UI can render a sensitivity
    curve rather than just a single critical value.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    parameter_name: str
    """Name of the sensitivity parameter, e.g. 'gamma' or 'lambda'."""
    parameter_values: tuple[float, ...]
    lower_bounds: tuple[float, ...]
    upper_bounds: tuple[float, ...]
    critical_value: float | None = None
    """Parameter value at which the bounds first exclude the null (0)."""
    method: BoundMethod = BoundMethod.ROSENBAUM_SHARP
    display_label: str = ""

    @model_validator(mode="after")
    def _validate_lengths(self) -> "SensitivitySweepResult":
        n = len(self.parameter_values)
        if len(self.lower_bounds) != n or len(self.upper_bounds) != n:
            raise ValueError(
                "parameter_values, lower_bounds, and upper_bounds must have equal length"
            )
        return self


class BoundsMethodSummary(BaseModel):
    """Canonical summary of one bounds method in a public bounds artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: BoundMethod
    lower_bound: float
    upper_bound: float
    bound_width: float
    certificate_ref: DualCertificateRef | BoundsTighteningLogRef | None = None
    assumptions_used: list[str] = Field(default_factory=list)
    bounds_type: str = "manski"
    display_label: str = ""
    certificate_kind: str | None = None
    soundness_level: BoundSoundnessLevel | None = None
    solver_metadata: dict[str, Any] = Field(default_factory=dict)


class BoundTighteningLogEntry(BaseModel):
    """One candidate evaluation in a certified tightening search."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: BoundMethod
    lower_bound: float | None = None
    upper_bound: float | None = None
    bound_width: float | None = None
    status: Literal[
        "baseline",
        "certified_improvement",
        "certified_no_improvement",
        "infeasible",
        "uncertified",
        "skipped",
    ]
    reason: str = ""
    certificate_kind: str | None = None
    soundness_level: BoundSoundnessLevel | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BestInClassClaim(BaseModel):
    """Certified best-in-class tightening claim over a finite search class."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    class_name: str
    class_spec_hash: str = ""
    status: TighteningStatus = TighteningStatus.NOT_RUN
    stop_reason: TighteningStopReason | None = None
    baseline_method: BoundMethod | None = None
    baseline_lower_bound: float | None = None
    baseline_upper_bound: float | None = None
    selected_method: BoundMethod | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    certified_width_reduction: float | None = None
    proof_ref: BoundsTighteningLogRef | None = None
    proof_note: str = ""
    log: list[BoundTighteningLogEntry] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BoundsTighteningLog(BaseModel):
    """Persisted proof-of-stopping log for a certified tightening search."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    class_name: str
    class_spec_hash: str
    status: TighteningStatus
    stop_reason: TighteningStopReason | None = None
    proof_note: str = ""
    entries: list[BoundTighteningLogEntry] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BoundsBundle(BaseModel):
    """Canonical public bounds contract for non-point-identified queries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    estimand_type: str = "ate"
    point_identified: bool = False
    lower_bound: float | None = None
    upper_bound: float | None = None
    consensus_lower: float | None = None
    consensus_upper: float | None = None
    dual_certificate_ref: DualCertificateRef | None = None
    sharpness_status: Literal["sharp", "inner_approx", "outer_approx", "unknown"] = "unknown"
    tightening_status: TighteningStatus = TighteningStatus.NOT_RUN
    tightening_stop_reason: TighteningStopReason | None = None
    tightening_log_ref: BoundsTighteningLogRef | None = None
    best_in_class_claim: BestInClassClaim | None = None
    method_summaries: list[BoundsMethodSummary] = Field(default_factory=list)
    rescue_actions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def bounds_bundle_from_partial_identification_result(
    result: PartialIdentificationResult,
    *,
    estimand_type: str = "ate",
    dual_certificate_ref: DualCertificateRef | None = None,
    rescue_actions: list[str] | None = None,
    warnings: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> BoundsBundle:
    """Lift one partial-identification result into the canonical public bundle."""
    sharpness_status = _sharpness_from_bounds_type(
        result.bounds_type,
        has_dual_certificate=dual_certificate_ref is not None,
    )
    return BoundsBundle(
        estimand_type=estimand_type,
        point_identified=abs(result.upper_bound - result.lower_bound) <= 1e-12,
        lower_bound=result.lower_bound,
        upper_bound=result.upper_bound,
        consensus_lower=result.lower_bound,
        consensus_upper=result.upper_bound,
        dual_certificate_ref=dual_certificate_ref,
        sharpness_status=sharpness_status,
        method_summaries=[
            BoundsMethodSummary(
                method=result.method,
                lower_bound=result.lower_bound,
                upper_bound=result.upper_bound,
                bound_width=result.bound_width,
                certificate_ref=result.certificate_ref,
                assumptions_used=list(result.assumptions_used),
                bounds_type=result.bounds_type,
                display_label=result.display_label,
                certificate_kind=result.certificate_kind,
                soundness_level=result.soundness_level,
                solver_metadata=dict(result.solver_metadata),
            )
        ],
        rescue_actions=list(rescue_actions or []),
        warnings=list(warnings or []),
        metadata=dict(metadata or {}),
    )


def bounds_bundle_from_bounds_report(
    report: BoundsReport,
    *,
    dual_certificate_ref: DualCertificateRef | None = None,
    rescue_actions: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> BoundsBundle:
    """Lift an aggregated bounds report into the canonical public bundle."""
    method_summaries = [
        BoundsMethodSummary(
            method=result.method,
            lower_bound=result.lower_bound,
            upper_bound=result.upper_bound,
            bound_width=result.bound_width,
            certificate_ref=result.certificate_ref,
            assumptions_used=list(result.assumptions_used),
            bounds_type=result.bounds_type,
            display_label=result.display_label,
            certificate_kind=result.certificate_kind,
            soundness_level=result.soundness_level,
            solver_metadata=dict(result.solver_metadata),
        )
        for result in report.results
    ]
    sharpness_status = "unknown"
    if report.tightest_method is not None:
        tightest = min(report.results, key=lambda item: item.bound_width)
        sharpness_status = _sharpness_from_bounds_type(
            tightest.bounds_type,
            has_dual_certificate=dual_certificate_ref is not None,
        )
    lower_bound = report.tightest_lower
    upper_bound = report.tightest_upper
    return BoundsBundle(
        estimand_type=report.estimand_type,
        point_identified=(
            lower_bound is not None
            and upper_bound is not None
            and abs(upper_bound - lower_bound) <= 1e-12
        ),
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        consensus_lower=report.consensus_lower,
        consensus_upper=report.consensus_upper,
        dual_certificate_ref=dual_certificate_ref,
        sharpness_status=sharpness_status,
        method_summaries=method_summaries,
        rescue_actions=list(rescue_actions or []),
        warnings=list(report.warnings),
        metadata={
            "run_id": report.run_id,
            "tightest_method": report.tightest_method.value if report.tightest_method is not None else None,
            "assumptions_used": list(report.assumptions_used),
            **dict(metadata or {}),
        },
    )


def annotate_bounds_bundle_for_proximal_bridge_failure(
    bundle: BoundsBundle,
    report: "BridgePlausibilityReport",
    *,
    rescue_actions: list[str] | None = None,
    warnings: list[str] | None = None,
) -> BoundsBundle:
    """Attach proximal bridge failure metadata to a fallback bounds bundle."""

    from polisyos.ir.analytics.proximal import (
        BridgeFailureMode,
        BridgeFallbackDisposition,
        BridgePlausibilityReport,
    )

    resolved_report = (
        report
        if isinstance(report, BridgePlausibilityReport)
        else BridgePlausibilityReport.model_validate(report)
    )

    marker_by_mode = {
        BridgeFailureMode.INFEASIBLE_EQUATION: "proximal_bridge_equation_infeasible",
        BridgeFailureMode.WEAK_COMPLETENESS: "proximal_completeness_unlikely",
        BridgeFailureMode.ILL_POSED: "proximal_bridge_ill_posed",
        BridgeFailureMode.NONUNIQUE_SOLUTION: "proximal_bridge_nonunique",
        BridgeFailureMode.UNKNOWN: "proximal_bridge_unresolved",
        BridgeFailureMode.NONE: "proximal_bridge_warning",
    }

    bundle_warnings = list(bundle.warnings)
    for warning in warnings or ():
        if warning not in bundle_warnings:
            bundle_warnings.append(warning)

    mode_warning = marker_by_mode[resolved_report.suspected_failure_mode]
    if mode_warning not in bundle_warnings:
        bundle_warnings.append(mode_warning)

    if resolved_report.fallback_disposition is BridgeFallbackDisposition.REQUIRE_BOUNDS:
        marker = "proximal_bounds_required"
        if marker not in bundle_warnings:
            bundle_warnings.append(marker)
    elif resolved_report.fallback_disposition is BridgeFallbackDisposition.BLOCK_POINT_ESTIMATE:
        marker = "proximal_point_estimate_blocked"
        if marker not in bundle_warnings:
            bundle_warnings.append(marker)
    elif resolved_report.fallback_disposition is BridgeFallbackDisposition.PROCEED_WITH_WARNING:
        marker = "proximal_point_estimate_warned"
        if marker not in bundle_warnings:
            bundle_warnings.append(marker)

    next_actions = list(bundle.rescue_actions)
    for action in (*resolved_report.recommended_rescue_actions, *(rescue_actions or ())):
        if action not in next_actions:
            next_actions.append(action)

    metadata = dict(bundle.metadata)
    metadata["proximal_bridge_plausibility"] = resolved_report.model_dump(mode="json")
    metadata["proximal_bridge_failure_mode"] = resolved_report.suspected_failure_mode.value
    metadata["proximal_fallback_disposition"] = (
        resolved_report.fallback_disposition.value
        if resolved_report.fallback_disposition is not None
        else None
    )

    return bundle.model_copy(
        update={
            "rescue_actions": next_actions,
            "warnings": bundle_warnings,
            "metadata": metadata,
        }
    )


def _sharpness_from_bounds_type(
    bounds_type: str,
    *,
    has_dual_certificate: bool = False,
) -> Literal["sharp", "inner_approx", "outer_approx", "unknown"]:
    normalized = str(bounds_type or "").strip().lower()
    if normalized == "sharp_lp":
        return "sharp" if has_dual_certificate else "unknown"
    if normalized == "relaxed_polynomial":
        return "outer_approx"
    if normalized == "manski":
        return "outer_approx"
    return "unknown"


def _tightest_method_summary(
    method_summaries: list[BoundsMethodSummary],
) -> BoundsMethodSummary | None:
    if not method_summaries:
        return None
    return min(method_summaries, key=lambda item: item.bound_width)


def _headline_method_summary(bundle: BoundsBundle) -> BoundsMethodSummary | None:
    claim = bundle.best_in_class_claim
    if (
        claim is not None
        and claim.selected_method is not None
        and claim.lower_bound is not None
        and claim.upper_bound is not None
    ):
        for summary in bundle.method_summaries:
            if (
                summary.method is claim.selected_method
                and abs(summary.lower_bound - claim.lower_bound) <= 1e-12
                and abs(summary.upper_bound - claim.upper_bound) <= 1e-12
            ):
                return summary
    return _tightest_method_summary(bundle.method_summaries)


def refresh_bounds_bundle_sharpness(bundle: BoundsBundle) -> BoundsBundle:
    """Recompute bundle sharpness from the tightest method and certificate availability."""

    tightest = _headline_method_summary(bundle)
    sharpness_status = (
        "unknown"
        if tightest is None
        else _sharpness_from_bounds_type(
            tightest.bounds_type,
            has_dual_certificate=bundle.dual_certificate_ref is not None,
        )
    )
    return bundle.model_copy(update={"sharpness_status": sharpness_status})


def attach_dual_certificate_ref(
    bundle: BoundsBundle,
    dual_certificate_ref: DualCertificateRef | None,
) -> BoundsBundle:
    """Attach a persisted dual-certificate ref and recompute sharpness."""

    method_summaries = list(bundle.method_summaries)
    headline = _headline_method_summary(bundle)
    if dual_certificate_ref is not None and headline is not None:
        method_summaries = [
            summary.model_copy(
                update={
                    "certificate_ref": dual_certificate_ref,
                    "certificate_kind": summary.certificate_kind or "lp_primal_dual",
                    "soundness_level": summary.soundness_level or BoundSoundnessLevel.CERTIFIED,
                }
            )
            if summary == headline
            else summary
            for summary in method_summaries
        ]
    return refresh_bounds_bundle_sharpness(
        bundle.model_copy(
            update={
                "dual_certificate_ref": dual_certificate_ref,
                "method_summaries": method_summaries,
            }
        )
    )


def attach_tightening_log_ref(
    bundle: BoundsBundle,
    tightening_log_ref: BoundsTighteningLogRef | None,
) -> BoundsBundle:
    """Attach a persisted certified-tightening log ref to the bundle and claim."""

    claim = bundle.best_in_class_claim
    updated_claim = (
        None if claim is None else claim.model_copy(update={"proof_ref": tightening_log_ref})
    )
    return bundle.model_copy(
        update={
            "tightening_log_ref": tightening_log_ref,
            "best_in_class_claim": updated_claim,
        }
    )


def persist_bounds_bundle(
    store: ArtifactStore,
    bundle: BoundsBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.bounds_bundle",
    schema_version: str = "1.0",
) -> BoundsBundleRef:
    """Persist bounds bundle helper."""
    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind="ir.bounds_bundle",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return BoundsBundleRef.model_validate(ref)


def persist_bounds_tightening_log(
    store: ArtifactStore,
    log: BoundsTighteningLog,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.bounds_tightening_log",
    schema_version: str = "1.0",
) -> BoundsTighteningLogRef:
    """Persist certified bounds-tightening proof-of-stopping log."""

    ref = put_json_artifact(
        store,
        log.model_dump(mode="json"),
        kind="ir.bounds_tightening_log",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return BoundsTighteningLogRef.model_validate(ref)


def load_bounds_tightening_log(
    store: ArtifactStore,
    ref: BoundsTighteningLogRef,
) -> BoundsTighteningLog:
    """Load certified bounds-tightening proof-of-stopping log."""

    payload = get_json_artifact(store, ref.artifact_id)
    return BoundsTighteningLog.model_validate(payload)


def bounds_tightening_log_from_claim(claim: BestInClassClaim) -> BoundsTighteningLog:
    """Build a persisted-log payload from an inline best-in-class claim."""

    return BoundsTighteningLog(
        class_name=claim.class_name,
        class_spec_hash=claim.class_spec_hash,
        status=claim.status,
        stop_reason=claim.stop_reason,
        proof_note=claim.proof_note,
        entries=list(claim.log),
        metadata=dict(claim.metadata),
    )


def hydrate_bounds_bundle_with_tightening_log(
    store: ArtifactStore,
    bundle: BoundsBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> tuple[BoundsBundle, list[InputRef]]:
    """Persist an inline best-in-class claim log and attach its ref."""

    resolved_inputs = list(inputs or [])
    if bundle.best_in_class_claim is None or bundle.tightening_log_ref is not None:
        return bundle, resolved_inputs
    log = bounds_tightening_log_from_claim(bundle.best_in_class_claim)
    log_ref = persist_bounds_tightening_log(store, log, inputs=resolved_inputs)
    resolved_inputs.append(InputRef(artifact_id=log_ref.artifact_id, role="bounds_tightening_log"))
    return attach_tightening_log_ref(bundle, log_ref), resolved_inputs


def load_bounds_bundle(
    store: ArtifactStore,
    ref: BoundsBundleRef,
) -> BoundsBundle:
    """Load bounds bundle."""
    payload = get_json_artifact(store, ref.artifact_id)
    return BoundsBundle.model_validate(payload)


def compute_manski_bounds(
    outcome_conditioned: np.ndarray,
    treatment_probs: np.ndarray,
    outcome_support: tuple[float, float] = (0.0, 1.0),
) -> PartialIdentificationResult:
    """Classic Manski (1990) worst-case bounds for ATE.

    Parameters
    ----------
    outcome_conditioned : (2,) array
        [E[Y|X=0], E[Y|X=1]] — conditional expectations.
    treatment_probs : (2,) array
        [P(X=0), P(X=1)] — marginal treatment probabilities.
    outcome_support : tuple
        (y_min, y_max) — support of the outcome variable.

    Returns
    -------
    PartialIdentificationResult with Manski bounds on ATE.
    """
    y_min, y_max = outcome_support
    e_y0, e_y1 = float(outcome_conditioned[0]), float(outcome_conditioned[1])
    p0, p1 = float(treatment_probs[0]), float(treatment_probs[1])

    # Manski bounds: ATE in [lower, upper]
    # Lower = p1*E[Y|X=1] + (1-p1)*y_min - p0*E[Y|X=0] - (1-p0)*y_max
    # Upper = p1*E[Y|X=1] + (1-p1)*y_max - p0*E[Y|X=0] - (1-p0)*y_min
    lower = (p1 * e_y1 + (1 - p1) * y_min) - (p0 * e_y0 + (1 - p0) * y_max)
    upper = (p1 * e_y1 + (1 - p1) * y_max) - (p0 * e_y0 + (1 - p0) * y_min)

    width = upper - lower
    confidence = max(0.0, min(1.0, 1.0 - width / (y_max - y_min) if y_max != y_min else 0.0))

    return PartialIdentificationResult(
        method=BoundMethod.MANSKI,
        lower_bound=lower,
        upper_bound=upper,
        confidence=confidence,
        assumptions_used=["no_assumptions_on_selection"],
        assumptions_violated=[],
        bounds_type="manski",
    )


__all__ = [
    "BoundMethod",
    "BoundSoundnessLevel",
    "BestInClassClaim",
    "BoundTighteningLogEntry",
    "BoundsTighteningLog",
    "BoundsBundle",
    "BoundsMethodSummary",
    "BoundsReport",
    "PartialIdentificationResult",
    "SensitivitySweepResult",
    "TighteningStatus",
    "TighteningStopReason",
    "attach_dual_certificate_ref",
    "attach_tightening_log_ref",
    "annotate_bounds_bundle_for_proximal_bridge_failure",
    "bounds_tightening_log_from_claim",
    "bounds_bundle_from_bounds_report",
    "bounds_bundle_from_partial_identification_result",
    "compute_manski_bounds",
    "hydrate_bounds_bundle_with_tightening_log",
    "load_bounds_bundle",
    "load_bounds_tightening_log",
    "persist_bounds_bundle",
    "persist_bounds_tightening_log",
    "refresh_bounds_bundle_sharpness",
]
