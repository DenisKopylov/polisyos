"""Define causal effect reports, proof bundles, and readiness diagnostics."""
from __future__ import annotations

import math
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics.estimand import SideConditionKind
from polisyos.ir.analytics.transportability import TransportabilityResult
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import (
    CausalEffectReportRef,
    DataReadinessReportRef,
    ProofBundleRef,
)


class CausalMethod(str, Enum):
    """Declare which estimator family produced a ``CausalEffectReport``.

    Reporting, diagnostics, and uncertainty conversion use this enum to explain
    estimator provenance and to select method-specific governance checks.
    """

    SYNTHETIC_CONTROL = "synthetic_control"
    DIFFERENCE_IN_DIFFERENCES = "difference_in_differences"
    REGRESSION_DISCONTINUITY = "regression_discontinuity"
    STRUCTURAL_TIME_SERIES = "structural_time_series"
    DOWHY_BACKDOOR = "dowhy_backdoor"
    DOWHY_IV = "dowhy_iv"
    DOWHY_FRONTDOOR = "dowhy_frontdoor"
    CAUSAL_FOREST = "causal_forest"
    FOREST_DR = "forest_dr"
    CAUSAL_BCF = "causal_bcf"
    DOUBLE_ML = "double_ml"
    S_LEARNER = "s_learner"
    T_LEARNER = "t_learner"
    X_LEARNER = "x_learner"
    POLICY_TREE = "policy_tree"
    G_COMPUTATION = "g_computation"
    ICE_G_FORMULA = "ice_g_formula"
    LTMLE = "ltmle"
    G_ESTIMATION = "g_estimation"
    Q_LEARNING_DTR = "q_learning_dtr"
    A_LEARNING_DTR = "a_learning_dtr"
    OUTCOME_WEIGHTED_LEARNING = "outcome_weighted_learning"
    DOUBLY_ROBUST_DTR = "doubly_robust_dtr"
    OFF_POLICY_EVALUATION = "off_policy_evaluation"
    CAUSAL_BANDIT = "causal_bandit"


class EstimationStatus(str, Enum):
    """Report whether a causal run produced decision-grade output or failed a gate.

    ``CausalEffectReport`` and its uncertainty conversion read this enum to
    decide whether an estimate is gate-eligible or should emit a non-actionable
    failure envelope.
    """

    SUCCESS = "success"
    INPUT_INVALID = "input_invalid"
    ASSUMPTION_FAILED = "assumption_failed"
    NUMERICAL_FAILURE = "numerical_failure"


class RefutationTestType(str, Enum):
    """Identify which robustness/refutation check generated a diagnostic result."""

    PLACEBO_TREATMENT = "placebo_treatment"
    RANDOM_COMMON_CAUSE = "random_common_cause"
    DATA_SUBSET = "data_subset"
    BOOTSTRAP = "bootstrap"
    UNOBSERVED_COMMON_CAUSE = "unobserved_common_cause"


class RefutationResult(BaseModel):
    """Outcome of a single causal refutation or robustness check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    test_type: RefutationTestType
    original_estimate: float
    refuted_estimate: float
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    passed: bool
    effect_ratio: float
    details: dict[str, Any] = Field(default_factory=dict)


class PlaceboResult(BaseModel):
    """Per-unit placebo diagnostic for synthetic-control style methods."""

    model_config = ConfigDict(extra="forbid")

    unit_id: str | int
    effect_estimate: float
    rmspe_pre: float | None = None
    rmspe_post: float | None = None
    rmspe_ratio: float | None = None


class DiagnosticTest(BaseModel):
    """Named diagnostic emitted alongside a causal estimate."""

    model_config = ConfigDict(extra="forbid")

    test_name: str
    statistic: float | None = None
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    passed: bool
    details: dict[str, Any] = Field(default_factory=dict)


class ProofBundle(BaseModel):
    """Canonical public proof artifact for causal identification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    proof_status: Literal["identified", "non_identified", "oracle_needed"]
    proof_stratum: Literal["A0_trusted", "A1_extended", "A2_oracle_backed"]
    theorem_family: str
    completeness_regime: Literal["complete", "sound_incomplete", "heuristic_backed"]
    implementation_coverage: str
    graph_ref: str | None = None
    query_ref: str | None = None
    estimand_ast: dict[str, Any] | None = None
    negative_certificate_summary: str | None = None
    proof_trace: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CausalEffectReport(BaseModel):
    """Canonical causal effect artifact emitted by Foundry methods.

    Combines the estimand, point estimate, uncertainty, diagnostics, placebo
    checks, and transportability context needed by Scientist governance and
    downstream reporting.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")

    method: CausalMethod
    status: EstimationStatus = EstimationStatus.SUCCESS
    status_reason: str | None = None

    estimand: str
    identified_estimand: str | None = None
    estimand_type: str | None = None
    graph_ref: str | None = None
    point_estimate: float | None = None
    standard_error: float | None = Field(default=None, ge=0.0)
    confidence_interval: tuple[float, float] | None = None
    confidence_level: float | None = Field(default=0.95, gt=0.0, lt=1.0)
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)

    inference_method: str
    n_bootstrap_samples: int | None = Field(default=None, ge=1)
    effect_size_cohen_d: float | None = None

    pre_treatment_fit: dict[str, float] = Field(default_factory=dict)
    diagnostics: list[DiagnosticTest] = Field(default_factory=list)
    refutation_results: list[RefutationResult] = Field(default_factory=list)
    placebo_results: list[PlaceboResult] = Field(default_factory=list)
    placebo_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    time_effects: dict[str, list[float]] = Field(default_factory=dict)

    method_params: dict[str, Any] = Field(default_factory=dict)
    assumptions: dict[str, str] = Field(default_factory=dict)
    sutva_assumed: bool = True
    sutva_violation_risk: Literal["high", "medium", "low"] | None = None
    transport_result: TransportabilityResult | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    sample_size: int = Field(ge=0)
    n_treated: int = Field(ge=0)
    n_control: int = Field(ge=0)
    pre_periods: int = Field(ge=0)
    post_periods: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_numbers(self) -> "CausalEffectReport":
        if self.status is EstimationStatus.SUCCESS:
            if self.point_estimate is None:
                raise ValueError("point_estimate is required for successful estimates")
            if self.confidence_interval is None:
                raise ValueError("confidence_interval is required for successful estimates")

        if self.confidence_interval is not None:
            lo, hi = self.confidence_interval
            if not math.isfinite(lo) or not math.isfinite(hi):
                raise ValueError("confidence_interval bounds must be finite")
            if lo > hi:
                raise ValueError("confidence_interval lower bound cannot exceed upper bound")
            if self.point_estimate is not None and not (lo <= self.point_estimate <= hi):
                raise ValueError("point_estimate must lie inside confidence_interval")

        if self.point_estimate is not None and not math.isfinite(self.point_estimate):
            raise ValueError("point_estimate must be finite")
        if self.standard_error is not None and not math.isfinite(self.standard_error):
            raise ValueError("standard_error must be finite")
        if self.effect_size_cohen_d is not None and not math.isfinite(self.effect_size_cohen_d):
            raise ValueError("effect_size_cohen_d must be finite")
        return self

    def to_uncertainty_envelope(self) -> UncertaintyEnvelope | None:
        if self.status is not EstimationStatus.SUCCESS:
            sentinel = 1.0e12
            point = 0.0 if self.point_estimate is None else float(self.point_estimate)
            point = max(-sentinel, min(sentinel, point))
            # Failure-mode envelope keeps governance visibility while remaining non-gate-eligible.
            return UncertaintyEnvelope(
                point_estimate=point,
                confidence_interval=(-sentinel, sentinel),
                confidence_level=None,
                distribution_family=DistributionFamily.UNKNOWN,
                source=UncertaintySource.CAUSAL,
                propagation_method=PropagationMethod.NONE,
                interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
                sample_size=self.sample_size if self.sample_size > 0 else None,
                is_heuristic_ci=True,
                gate_eligible=False,
                metadata={
                    "causal_method": self.method.value,
                    "estimand": self.estimand,
                    "inference_method": self.inference_method,
                    "status": self.status.value,
                    "status_reason": self.status_reason,
                    "failure_envelope": True,
                    "assumptions": dict(self.assumptions),
                },
            )
        if self.point_estimate is None or self.confidence_interval is None:
            return None

        family_map = {
            "placebo_permutation": DistributionFamily.BOOTSTRAP,
            "bootstrap": DistributionFamily.BOOTSTRAP,
            "asymptotic": DistributionFamily.NORMAL,
            "state_space_simulation": DistributionFamily.UNKNOWN,
            "bayesian_posterior": DistributionFamily.BAYESIAN,
        }
        family = family_map.get(self.inference_method, DistributionFamily.UNKNOWN)
        interval_semantics = (
            IntervalSemantics.CREDIBLE_INTERVAL
            if self.inference_method == "bayesian_posterior"
            else IntervalSemantics.CONFIDENCE_INTERVAL
        )

        return UncertaintyEnvelope(
            point_estimate=self.point_estimate,
            confidence_interval=self.confidence_interval,
            confidence_level=self.confidence_level,
            distribution_family=family,
            source=UncertaintySource.CAUSAL,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=interval_semantics,
            sample_size=self.sample_size if self.sample_size > 0 else None,
            is_heuristic_ci=False,
            gate_eligible=True,
            metadata={
                "causal_method": self.method.value,
                "estimand": self.estimand,
                "inference_method": self.inference_method,
                "status": self.status.value,
                "status_reason": self.status_reason,
                "p_value": self.p_value,
                "placebo_p_value": self.placebo_p_value,
                "assumptions": dict(self.assumptions),
            },
        )


def persist_causal_effect_report(
    store: ArtifactStore,
    report: CausalEffectReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.causal_effect_report",
    schema_version: str = "1.0",
) -> CausalEffectReportRef:
    """Persist a causal effect report as a typed JSON artifact reference."""
    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind="ir.causal_effect_report",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalEffectReportRef.model_validate(ref)


def load_causal_effect_report(
    store: ArtifactStore,
    ref: CausalEffectReportRef,
) -> CausalEffectReport:
    """Load causal effect report."""
    payload = get_json_artifact(store, ref.artifact_id)
    return CausalEffectReport.model_validate(payload)


def persist_proof_bundle(
    store: ArtifactStore,
    bundle: ProofBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.proof_bundle",
    schema_version: str = "1.0",
) -> ProofBundleRef:
    """Persist a proof bundle and return its typed artifact reference."""
    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind="ir.proof_bundle",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ProofBundleRef.model_validate(ref)


def load_proof_bundle(
    store: ArtifactStore,
    ref: ProofBundleRef,
) -> ProofBundle:
    """Load proof bundle."""
    payload = get_json_artifact(store, ref.artifact_id)
    return ProofBundle.model_validate(payload)


class PositivityDiagnosticReport(BaseModel):
    """Positivity / overlap diagnostic result for causal identification governance.

    Produced by ``causal.diagnostics.positivity_check@1.0.0`` and consumed by
    downstream estimators (AIPW, CrossFitOrchestrator) to gate estimation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    passes_positivity: bool
    """True when propensity scores are within (min_threshold, max_threshold) for all obs."""

    min_propensity_observed: float = Field(ge=0.0, le=1.0)
    max_propensity_observed: float = Field(ge=0.0, le=1.0)

    effective_sample_size: float = Field(ge=0.0)
    """Kish ESS = (Σw)² / Σw² where w = IPW weights."""

    ess_fraction: float = Field(ge=0.0, le=1.0)
    """ESS / n_obs — fraction of effective sample retained."""

    overlap_score: float = Field(ge=0.0, le=1.0)
    """Aggregate overlap: 1 = perfect, 0 = no common support."""

    n_obs: int = Field(ge=0)
    n_trimmed: int = Field(ge=0, default=0)
    """Number of observations trimmed due to extreme propensity."""

    recommendations: list[str] = Field(default_factory=list)
    side_conditions_violated: list[SideConditionKind] = Field(default_factory=list)


class DataReadinessReport(BaseModel):
    """Canonical pre-estimation readiness gate for causal execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    decision: Literal["pass", "warn", "block", "unknown"]
    can_compile_estimation: bool
    can_run_estimation: bool
    sample_size: int | None = Field(default=None, ge=0)
    measurement_quality: Literal["known_good", "proxy_only", "unknown"] = "unknown"
    fallback_data_available: bool = False
    positivity: PositivityDiagnosticReport | None = None
    support_mismatch: dict[str, Any] | None = None
    blocking_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)


def persist_data_readiness_report(
    store: ArtifactStore,
    report: DataReadinessReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.data_readiness_report",
    schema_version: str = "1.0",
) -> DataReadinessReportRef:
    """Persist a data-readiness report used by pre-estimation governance gates."""
    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind="ir.data_readiness_report",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return DataReadinessReportRef.model_validate(ref)


def load_data_readiness_report(
    store: ArtifactStore,
    ref: DataReadinessReportRef,
) -> DataReadinessReport:
    """Load data readiness report."""
    payload = get_json_artifact(store, ref.artifact_id)
    return DataReadinessReport.model_validate(payload)


def proof_bundle_from_identification_result(
    result: Any,
    *,
    graph_ref: str | None = None,
    query_ref: str | None = None,
    negative_certificate_summary: str | None = None,
) -> ProofBundle:
    """Translate an internal identification result into the canonical proof surface."""
    status_raw = _status_value(getattr(result, "status", "oracle_needed"))
    algorithm_version = str(getattr(result, "algorithm_version", "") or "")
    theorem_family = algorithm_version or "id_unknown"
    proof_status: Literal["identified", "non_identified", "oracle_needed"]
    completeness_regime: Literal["complete", "sound_incomplete", "heuristic_backed"]
    if status_raw == "identified":
        proof_status = "identified"
        completeness_regime = "complete"
    elif status_raw in {"hedge_found", "not_recoverable"}:
        proof_status = "non_identified"
        completeness_regime = "complete"
    elif status_raw in {"oracle_needed", "pag_ambiguous"}:
        proof_status = "oracle_needed"
        completeness_regime = "heuristic_backed"
    else:
        proof_status = "oracle_needed"
        completeness_regime = "sound_incomplete"

    proof_stratum = _proof_stratum_for_result(status_raw=status_raw, theorem_family=theorem_family)
    estimand_ast = getattr(result, "estimand_ast", None)
    assumptions = _extract_assumptions_from_estimand(estimand_ast)
    return ProofBundle(
        proof_status=proof_status,
        proof_stratum=proof_stratum,
        theorem_family=theorem_family,
        completeness_regime=completeness_regime,
        implementation_coverage=_implementation_coverage_for_result(
            status_raw=status_raw,
            theorem_family=theorem_family,
        ),
        graph_ref=graph_ref,
        query_ref=query_ref or getattr(result, "query_str", None),
        estimand_ast=(
            estimand_ast.model_dump(mode="json")
            if hasattr(estimand_ast, "model_dump")
            else estimand_ast
        ),
        negative_certificate_summary=negative_certificate_summary,
        proof_trace=list(getattr(result, "trace", []) or []),
        assumptions=assumptions,
        metadata={
            "status": status_raw,
            "required_distributions_count": len(getattr(result, "required_distributions", []) or []),
        },
    )


def proof_bundle_from_negative_certificate(
    certificate: Any,
    *,
    graph_ref: str | None = None,
    query_ref: str | None = None,
    theorem_family: str | None = None,
    status_raw: str | None = None,
) -> ProofBundle:
    """Translate a canonical impossibility artifact into the public proof surface."""
    diagnostics = dict(getattr(certificate, "quantitative_diagnostics", {}) or {})
    blocking_type = str(getattr(getattr(certificate, "blocking_type", None), "value", "") or "")
    resolved_status = str(status_raw or diagnostics.get("identification_status") or "").strip().lower()
    if not resolved_status:
        resolved_status = "non_identified"
    resolved_theorem_family = (
        str(theorem_family or diagnostics.get("algorithm_version") or "").strip()
        or f"negative_{blocking_type or 'certificate'}"
    )
    if resolved_status in {"oracle_needed", "pag_ambiguous"}:
        proof_status: Literal["identified", "non_identified", "oracle_needed"] = "oracle_needed"
        completeness_regime: Literal["complete", "sound_incomplete", "heuristic_backed"] = (
            "heuristic_backed"
        )
    else:
        proof_status = "non_identified"
        completeness_regime = "complete"

    proof_trace = diagnostics.get("proof_trace")
    if not isinstance(proof_trace, list):
        proof_trace = []

    return ProofBundle(
        proof_status=proof_status,
        proof_stratum=_proof_stratum_for_result(
            status_raw=resolved_status,
            theorem_family=resolved_theorem_family,
        ),
        theorem_family=resolved_theorem_family,
        completeness_regime=completeness_regime,
        implementation_coverage=_implementation_coverage_for_result(
            status_raw=resolved_status,
            theorem_family=resolved_theorem_family,
        ),
        graph_ref=graph_ref,
        query_ref=query_ref,
        estimand_ast=None,
        negative_certificate_summary=(
            certificate.to_summary() if hasattr(certificate, "to_summary") else None
        ),
        proof_trace=[str(item) for item in proof_trace],
        assumptions=[],
        metadata={
            "status": resolved_status,
            "blocking_type": blocking_type,
            "constructive_message": str(
                getattr(certificate, "constructive_message", "") or ""
            ),
        },
    )


def build_data_readiness_report(
    *,
    positivity: PositivityDiagnosticReport | dict[str, Any] | None = None,
    support_mismatch: dict[str, Any] | None = None,
    sample_size: int | None = None,
    measurement_quality: Literal["known_good", "proxy_only", "unknown"] = "unknown",
    fallback_data_available: bool = False,
    extra_metrics: dict[str, float] | None = None,
) -> DataReadinessReport:
    """Aggregate existing causal diagnostics into a canonical readiness gate."""
    positivity_report = _normalize_positivity(positivity)
    metrics = dict(extra_metrics or {})
    blocking_reasons: list[str] = []
    warnings: list[str] = []

    if positivity_report is not None:
        metrics.setdefault("ess_fraction", positivity_report.ess_fraction)
        metrics.setdefault("overlap_score", positivity_report.overlap_score)
        metrics.setdefault(
            "effective_sample_size",
            float(positivity_report.effective_sample_size),
        )
        if not positivity_report.passes_positivity:
            blocking_reasons.append("positivity_failed")
        if positivity_report.ess_fraction < 0.30:
            blocking_reasons.append("low_ess_fraction")
        elif positivity_report.ess_fraction < 0.50:
            warnings.append("ess_fraction_warn")
        if positivity_report.overlap_score < 0.50:
            blocking_reasons.append("low_overlap_score")
        elif positivity_report.overlap_score < 0.70:
            warnings.append("overlap_score_warn")

    if support_mismatch is not None:
        passes_support = bool(support_mismatch.get("passes_support_check", True))
        support_score = support_mismatch.get("support_mismatch_score")
        if support_score is not None:
            try:
                metrics.setdefault("support_mismatch_score", float(support_score))
            except (TypeError, ValueError):
                pass
        if not passes_support:
            blocking_reasons.append("support_mismatch_failed")

    if sample_size is not None:
        metrics.setdefault("sample_size", float(sample_size))
        if sample_size < 50:
            warnings.append("small_sample_size")

    if measurement_quality == "unknown":
        warnings.append("measurement_quality_unknown")
    elif measurement_quality == "proxy_only":
        warnings.append("proxy_measurement_only")

    if not fallback_data_available:
        warnings.append("fallback_arrays_unavailable")

    if positivity_report is None and support_mismatch is None and sample_size is None:
        decision: Literal["pass", "warn", "block", "unknown"] = "unknown"
    elif blocking_reasons:
        decision = "block"
    elif warnings:
        decision = "warn"
    else:
        decision = "pass"

    can_run_estimation = decision in {"pass", "warn"}
    return DataReadinessReport(
        decision=decision,
        can_compile_estimation=can_run_estimation,
        can_run_estimation=can_run_estimation,
        sample_size=sample_size,
        measurement_quality=measurement_quality,
        fallback_data_available=fallback_data_available,
        positivity=positivity_report,
        support_mismatch=dict(support_mismatch) if support_mismatch is not None else None,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        metrics=metrics,
    )


def _normalize_positivity(
    positivity: PositivityDiagnosticReport | dict[str, Any] | None,
) -> PositivityDiagnosticReport | None:
    if positivity is None:
        return None
    if isinstance(positivity, PositivityDiagnosticReport):
        return positivity
    try:
        return PositivityDiagnosticReport.model_validate(positivity)
    except Exception:
        return None


def _status_value(status: Any) -> str:
    return str(getattr(status, "value", status) or "").strip().lower()


def _proof_stratum_for_result(
    *,
    status_raw: str,
    theorem_family: str,
) -> Literal["A0_trusted", "A1_extended", "A2_oracle_backed"]:
    family = theorem_family.lower()
    if status_raw in {"oracle_needed", "pag_ambiguous"}:
        return "A2_oracle_backed"
    if any(token in family for token in ("sigma", "cyclic", "recover", "id_star", "idc_star", "ctf")):
        return "A1_extended"
    return "A0_trusted"


def _implementation_coverage_for_result(
    *,
    status_raw: str,
    theorem_family: str,
) -> str:
    if status_raw == "oracle_needed":
        return f"conditional-coverage:{theorem_family or 'oracle'}"
    if status_raw == "pag_ambiguous":
        return "sound only under oriented-equivalence handling policy"
    return f"declared-scope:{theorem_family or 'native_id'}"


def _extract_assumptions_from_estimand(estimand_ast: Any) -> list[str]:
    if estimand_ast is None:
        return []
    side_conditions = getattr(estimand_ast, "side_conditions", None)
    if not side_conditions:
        return []
    assumptions: list[str] = []
    for item in side_conditions:
        kind = getattr(item, "kind", None)
        value = getattr(kind, "value", kind)
        if value is not None:
            assumptions.append(str(value))
    return assumptions


__all__ = [
    "CausalMethod",
    "DataReadinessReport",
    "EstimationStatus",
    "RefutationTestType",
    "RefutationResult",
    "PlaceboResult",
    "DiagnosticTest",
    "CausalEffectReport",
    "PositivityDiagnosticReport",
    "ProofBundle",
    "TransportabilityResult",
    "build_data_readiness_report",
    "persist_data_readiness_report",
    "persist_causal_effect_report",
    "persist_proof_bundle",
    "load_data_readiness_report",
    "load_causal_effect_report",
    "load_proof_bundle",
    "proof_bundle_from_identification_result",
    "proof_bundle_from_negative_certificate",
]
