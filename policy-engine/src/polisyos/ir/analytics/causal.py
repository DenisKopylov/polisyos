"""Define causal effect reports, proof bundles, and readiness diagnostics."""
from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir._validation import ensure_confidence_interval, ensure_finite_numeric
from polisyos.ir.analytics.administrative_missingness import (
    MissingnessAssessmentReport,
    MissingnessAssessmentStatus,
)
from polisyos.ir.analytics.dynamic_causal_semantics import (
    DynamicReductionStatus,
    DynamicSemanticsAttachment,
)
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
    BridgePlausibilityReportRef,
    CausalEffectReportRef,
    DataReadinessReportRef,
    DPRobustnessCertificateRef,
    EvidenceBundleRef,
    FrontierSketchRef,
    JointDecisionCertificateRef,
    ProofBundleRef,
    ProofComposabilityCertificateRef,
    ProofWitnessIndexRef,
    ProximalIdentificationCertificateRef,
    RecoverabilityCertificateRef,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from polisyos.ir.analytics.proximal import (
        ProximalIdentificationCertificate,
        ProximalMediationCertificate,
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
    PROXIMAL_BRIDGE = "proximal_bridge"
    DISTRIBUTIONAL_TREATMENT_EFFECT = "distributional_treatment_effect"
    KERNEL_CME = "kernel_cme"
    KERNEL_FRONTDOOR = "kernel_frontdoor"
    KERNEL_TRANSPORT = "kernel_transport"
    KERNEL_DR_CME = "kernel_dr_cme"
    KERNEL_IV = "kernel_iv"
    KERNEL_PROXIMAL_MINIMAX = "kernel_proximal_minimax"
    INTERFERENCE_CATE = "interference_cate"
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
    proof_stratum: Literal["A0_trusted", "A1_extended", "A1_dynamic", "A2_oracle_backed"]
    theorem_family: str
    completeness_regime: Literal["complete", "sound_incomplete", "heuristic_backed"]
    implementation_coverage: str
    graph_ref: str | None = None
    query_ref: str | None = None
    proof_trace_ref: EvidenceBundleRef | None = None
    dp_robustness_ref: DPRobustnessCertificateRef | None = None
    frontier_sketch_ref: FrontierSketchRef | None = None
    bridge_plausibility_report_ref: BridgePlausibilityReportRef | None = None
    proximal_certificate_ref: ProximalIdentificationCertificateRef | None = None
    recoverability_certificate_ref: RecoverabilityCertificateRef | None = None
    joint_decision_ref: JointDecisionCertificateRef | None = None
    composability_certificate_ref: ProofComposabilityCertificateRef | None = None
    witness_index_ref: ProofWitnessIndexRef | None = None
    estimand_ast: dict[str, Any] | None = None
    dynamic_semantics: DynamicSemanticsAttachment | None = None
    negative_certificate_summary: str | None = None
    proof_trace: list[str] = Field(default_factory=list)
    composability_status: Literal["reusable", "revalidate", "rederive", "unknown"] = "unknown"
    proof_support_projection_hash: str | None = None
    invalidated_by_graph_hashes: list[str] = Field(default_factory=list)
    uniform_probe_class_ref: str | None = None
    operator_lift_allowed: bool = False
    operator_lift_scope: Literal["none", "finite_audit_basis", "whole_probe_space"] = "none"
    operator_lift_reason: str | None = None
    operator_lift_failure_reason: str | None = None
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
            ensure_confidence_interval(
                self.confidence_interval,
                label="confidence_interval",
                point_estimate=self.point_estimate,
            )

        if self.point_estimate is not None:
            ensure_finite_numeric(self.point_estimate, field_name="point_estimate")
        if self.standard_error is not None:
            ensure_finite_numeric(self.standard_error, field_name="standard_error")
        if self.effect_size_cohen_d is not None:
            ensure_finite_numeric(self.effect_size_cohen_d, field_name="effect_size_cohen_d")
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
    recoverability: dict[str, Any] | None = None
    missingness_assessment: MissingnessAssessmentReport | None = None
    recoverability_certificate_ref: RecoverabilityCertificateRef | None = None
    joint_decision_ref: JointDecisionCertificateRef | None = None
    dp_distortion: dict[str, Any] | None = None
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
    proof_trace_ref: EvidenceBundleRef | None = None,
    recoverability_certificate: Any | None = None,
    recoverability_certificate_ref: RecoverabilityCertificateRef | None = None,
    joint_decision_ref: JointDecisionCertificateRef | None = None,
    composability_certificate: Any | None = None,
    composability_certificate_ref: ProofComposabilityCertificateRef | None = None,
    witness_index_ref: ProofWitnessIndexRef | None = None,
) -> ProofBundle:
    """Translate an internal identification result into the canonical proof surface."""
    status_raw = _status_value(getattr(result, "status", "oracle_needed"))
    algorithm_version = str(getattr(result, "algorithm_version", "") or "")
    theorem_family = algorithm_version or "id_unknown"
    dynamic_semantics = _extract_dynamic_semantics(getattr(result, "metadata", None))
    proof_status: Literal["identified", "non_identified", "oracle_needed"]
    if status_raw == "identified":
        proof_status = "identified"
    elif status_raw in {"hedge_found", "not_recoverable"}:
        proof_status = "non_identified"
    elif status_raw in {"oracle_needed", "pag_ambiguous"}:
        proof_status = "oracle_needed"
    else:
        proof_status = "oracle_needed"
    completeness_regime = _completeness_regime_for_result(
        status_raw=status_raw,
        theorem_family=theorem_family,
        dynamic_semantics=dynamic_semantics,
    )

    proof_stratum = _proof_stratum_for_result(
        status_raw=status_raw,
        theorem_family=theorem_family,
        dynamic_semantics=dynamic_semantics,
    )
    estimand_ast = getattr(result, "estimand_ast", None)
    assumptions = _extract_assumptions_from_estimand(estimand_ast)
    result_metadata = dict(getattr(result, "metadata", {}) or {})
    resolved_proof_trace_ref = _typed_ref_from_payload(
        proof_trace_ref or result_metadata.get("proof_trace_ref"),
        EvidenceBundleRef,
    )
    resolved_recoverability_ref = _typed_ref_from_payload(
        recoverability_certificate_ref or result_metadata.get("recoverability_certificate_ref"),
        RecoverabilityCertificateRef,
    )
    resolved_joint_decision_ref = _typed_ref_from_payload(
        joint_decision_ref or result_metadata.get("joint_decision_ref"),
        JointDecisionCertificateRef,
    )
    resolved_frontier_sketch_ref = _typed_ref_from_payload(
        result_metadata.get("frontier_sketch_ref"),
        FrontierSketchRef,
    )
    resolved_bridge_plausibility_report_ref = _typed_ref_from_payload(
        result_metadata.get("bridge_plausibility_report_ref"),
        BridgePlausibilityReportRef,
    )
    resolved_composability_ref = _typed_ref_from_payload(
        composability_certificate_ref or result_metadata.get("composability_certificate_ref"),
        ProofComposabilityCertificateRef,
    )
    resolved_witness_index_ref = _typed_ref_from_payload(
        witness_index_ref
        or result_metadata.get("witness_index_ref")
        or getattr(composability_certificate, "witness_index_ref", None),
        ProofWitnessIndexRef,
    )
    resolved_composability_status = _normalize_composability_status(
        result_metadata.get("composability_status")
        or getattr(composability_certificate, "status", None)
    )
    proof_support_projection_hash = (
        str(
            result_metadata.get("proof_support_projection_hash")
            or getattr(composability_certificate, "proof_support_projection_hash", "")
            or ""
        ).strip()
        or None
    )
    invalidated_by_graph_hashes = _normalize_string_list(
        result_metadata.get("invalidated_by_graph_hashes")
        or getattr(composability_certificate, "invalidated_by_graph_hashes", None)
    )
    operator_lift_contract = _derive_operator_lift_contract(
        estimand_ast=estimand_ast,
        status_raw=status_raw,
        result_metadata=result_metadata,
    )
    uniform_probe_class_ref = operator_lift_contract["uniform_probe_class_ref"]
    operator_lift_allowed = operator_lift_contract["operator_lift_allowed"]
    operator_lift_scope = operator_lift_contract["operator_lift_scope"]
    operator_lift_reason = operator_lift_contract["operator_lift_reason"]
    operator_lift_failure_reason = operator_lift_contract["operator_lift_failure_reason"]
    recoverability_summary = _recoverability_summary(
        recoverability_certificate
        if recoverability_certificate is not None
        else result_metadata.get("recoverability_certificate")
    )
    joint_decision_summary = _joint_decision_summary(result_metadata.get("joint_decision"))
    return ProofBundle(
        proof_status=proof_status,
        proof_stratum=proof_stratum,
        theorem_family=theorem_family,
        completeness_regime=completeness_regime,
        implementation_coverage=_implementation_coverage_for_result(
            status_raw=status_raw,
            theorem_family=theorem_family,
            dynamic_semantics=dynamic_semantics,
        ),
        graph_ref=graph_ref,
        query_ref=query_ref or getattr(result, "query_str", None),
        proof_trace_ref=resolved_proof_trace_ref,
        frontier_sketch_ref=resolved_frontier_sketch_ref,
        bridge_plausibility_report_ref=resolved_bridge_plausibility_report_ref,
        recoverability_certificate_ref=resolved_recoverability_ref,
        joint_decision_ref=resolved_joint_decision_ref,
        composability_certificate_ref=resolved_composability_ref,
        witness_index_ref=resolved_witness_index_ref,
        estimand_ast=(
            estimand_ast.model_dump(mode="json")
            if hasattr(estimand_ast, "model_dump")
            else estimand_ast
        ),
        dynamic_semantics=dynamic_semantics,
        negative_certificate_summary=negative_certificate_summary,
        proof_trace=list(getattr(result, "trace", []) or []),
        composability_status=resolved_composability_status,
        proof_support_projection_hash=proof_support_projection_hash,
        invalidated_by_graph_hashes=invalidated_by_graph_hashes,
        uniform_probe_class_ref=uniform_probe_class_ref,
        operator_lift_allowed=operator_lift_allowed,
        operator_lift_scope=operator_lift_scope,
        operator_lift_reason=operator_lift_reason,
        operator_lift_failure_reason=operator_lift_failure_reason,
        assumptions=assumptions,
        metadata={
            **result_metadata,
            "status": status_raw,
            "required_distributions_count": len(
                getattr(result, "required_distributions", []) or []
            ),
            **(
                {"proof_trace_ref": resolved_proof_trace_ref.model_dump(mode="json")}
                if resolved_proof_trace_ref is not None
                else {}
            ),
            **(
                {
                    "bridge_plausibility_report_ref": resolved_bridge_plausibility_report_ref.model_dump(
                        mode="json"
                    )
                }
                if resolved_bridge_plausibility_report_ref is not None
                else {}
            ),
            **(
                {"recoverability": recoverability_summary}
                if recoverability_summary is not None
                else {}
            ),
            **(
                {"recoverability_certificate_ref": resolved_recoverability_ref.model_dump(mode="json")}
                if resolved_recoverability_ref is not None
                else {}
            ),
            **(
                {"joint_decision": joint_decision_summary}
                if joint_decision_summary is not None
                else {}
            ),
            **(
                {"joint_decision_ref": resolved_joint_decision_ref.model_dump(mode="json")}
                if resolved_joint_decision_ref is not None
                else {}
            ),
            **(
                {"frontier_sketch_ref": resolved_frontier_sketch_ref.model_dump(mode="json")}
                if resolved_frontier_sketch_ref is not None
                else {}
            ),
            **(
                {
                    "composability_certificate_ref": resolved_composability_ref.model_dump(
                        mode="json"
                    )
                }
                if resolved_composability_ref is not None
                else {}
            ),
            **(
                {"witness_index_ref": resolved_witness_index_ref.model_dump(mode="json")}
                if resolved_witness_index_ref is not None
                else {}
            ),
            "composability_status": resolved_composability_status,
            "proof_support_projection_hash": proof_support_projection_hash,
            "invalidated_by_graph_hashes": invalidated_by_graph_hashes,
            "uniform_probe_class_ref": uniform_probe_class_ref,
            "operator_lift_allowed": operator_lift_allowed,
            "operator_lift_scope": operator_lift_scope,
            "operator_lift_reason": operator_lift_reason,
            "operator_lift_failure_reason": operator_lift_failure_reason,
            **(
                {
                    "operator_audit_basis_probe_refs": operator_lift_contract[
                        "operator_audit_basis_probe_refs"
                    ]
                }
                if operator_lift_contract["operator_audit_basis_probe_refs"]
                else {}
            ),
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
    resolved_status = str(
        status_raw or diagnostics.get("identification_status") or ""
    ).strip().lower()
    if not resolved_status:
        resolved_status = "non_identified"
    resolved_theorem_family = (
        str(theorem_family or diagnostics.get("algorithm_version") or "").strip()
        or f"negative_{blocking_type or 'certificate'}"
    )
    dynamic_semantics = _extract_dynamic_semantics(diagnostics)
    if resolved_status in {"oracle_needed", "pag_ambiguous"}:
        proof_status: Literal["identified", "non_identified", "oracle_needed"] = "oracle_needed"
    else:
        proof_status = "non_identified"
    completeness_regime = _completeness_regime_for_result(
        status_raw=resolved_status,
        theorem_family=resolved_theorem_family,
        dynamic_semantics=dynamic_semantics,
    )

    proof_trace = diagnostics.get("proof_trace")
    if not isinstance(proof_trace, list):
        proof_trace = []
    metadata = {
        key: value
        for key, value in diagnostics.items()
        if key != "proof_trace"
    }
    recoverability_summary = _recoverability_summary(
        metadata.get("recoverability")
        or metadata.get("recoverability_certificate")
        or metadata.get("joint_decision")
    )
    recoverability_certificate_ref = _typed_ref_from_payload(
        metadata.get("recoverability_certificate_ref"),
        RecoverabilityCertificateRef,
    )
    joint_decision_ref = _typed_ref_from_payload(
        metadata.get("joint_decision_ref"),
        JointDecisionCertificateRef,
    )
    frontier_sketch_ref = _typed_ref_from_payload(
        metadata.get("frontier_sketch_ref"),
        FrontierSketchRef,
    )
    bridge_plausibility_report_ref = _typed_ref_from_payload(
        metadata.get("bridge_plausibility_report_ref"),
        BridgePlausibilityReportRef,
    )
    joint_decision_summary = _joint_decision_summary(metadata.get("joint_decision"))

    return ProofBundle(
        proof_status=proof_status,
        proof_stratum=_proof_stratum_for_result(
            status_raw=resolved_status,
            theorem_family=resolved_theorem_family,
            dynamic_semantics=dynamic_semantics,
        ),
        theorem_family=resolved_theorem_family,
        completeness_regime=completeness_regime,
        implementation_coverage=_implementation_coverage_for_result(
            status_raw=resolved_status,
            theorem_family=resolved_theorem_family,
            dynamic_semantics=dynamic_semantics,
        ),
        graph_ref=graph_ref,
        query_ref=query_ref,
        frontier_sketch_ref=frontier_sketch_ref,
        bridge_plausibility_report_ref=bridge_plausibility_report_ref,
        recoverability_certificate_ref=recoverability_certificate_ref,
        joint_decision_ref=joint_decision_ref,
        estimand_ast=None,
        dynamic_semantics=dynamic_semantics,
        negative_certificate_summary=(
            certificate.to_summary() if hasattr(certificate, "to_summary") else None
        ),
        proof_trace=[str(item) for item in proof_trace],
        assumptions=[],
        metadata={
            **metadata,
            "status": resolved_status,
            "blocking_type": blocking_type,
            "constructive_message": str(
                getattr(certificate, "constructive_message", "") or ""
            ),
            **(
                {
                    "bridge_plausibility_report_ref": bridge_plausibility_report_ref.model_dump(
                        mode="json"
                    )
                }
                if bridge_plausibility_report_ref is not None
                else {}
            ),
            **(
                {"recoverability": recoverability_summary}
                if recoverability_summary is not None
                else {}
            ),
            **(
                {"recoverability_certificate_ref": recoverability_certificate_ref.model_dump(mode="json")}
                if recoverability_certificate_ref is not None
                else {}
            ),
            **(
                {"joint_decision": joint_decision_summary}
                if joint_decision_summary is not None
                else {}
            ),
            **(
                {"joint_decision_ref": joint_decision_ref.model_dump(mode="json")}
                if joint_decision_ref is not None
                else {}
            ),
            **(
                {"frontier_sketch_ref": frontier_sketch_ref.model_dump(mode="json")}
                if frontier_sketch_ref is not None
                else {}
            ),
        },
    )


def proof_bundle_from_proximal_certificate(
    certificate: ProximalIdentificationCertificate,
    *,
    graph_ref: str | None = None,
    query_ref: str | None = None,
    certificate_ref: ProximalIdentificationCertificateRef | None = None,
    frontier_sketch_ref: FrontierSketchRef | None = None,
) -> ProofBundle:
    """Translate a proximal bridge certificate into the public proof surface."""
    cert_payload = certificate.model_dump(mode="json")
    return ProofBundle(
        proof_status="identified",
        proof_stratum="A1_extended",
        theorem_family="proximal_id_pci_core",
        completeness_regime="sound_incomplete",
        implementation_coverage="proximal_bridge_v1_pci_core",
        graph_ref=graph_ref,
        query_ref=query_ref,
        frontier_sketch_ref=frontier_sketch_ref,
        proximal_certificate_ref=certificate_ref,
        estimand_ast=None,
        negative_certificate_summary=None,
        proof_trace=list(certificate.proof_trace),
        assumptions=list(certificate.assumptions),
        metadata={
            "status": "identified",
            "method": CausalMethod.PROXIMAL_BRIDGE.value,
            "proximal_certificate": cert_payload,
            **(
                {"proximal_certificate_ref": certificate_ref.model_dump(mode="json")}
                if certificate_ref is not None
                else {}
            ),
            **(
                {"frontier_sketch_ref": frontier_sketch_ref.model_dump(mode="json")}
                if frontier_sketch_ref is not None
                else {}
            ),
            "bridge_functions_count": len(certificate.bridge_functions),
            "graph_checks_count": len(certificate.graph_checks),
        },
    )


def proof_bundle_from_proximal_mediation_certificate(
    certificate: "ProximalMediationCertificate",
    *,
    graph_ref: str | None = None,
    query_ref: str | None = None,
    oracle_assumptions_accepted: bool = False,
    frontier_sketch_ref: FrontierSketchRef | None = None,
) -> ProofBundle:
    """Translate a proximal mediation certificate into the public proof surface."""

    cert_payload = certificate.model_dump(mode="json")
    proof_status: Literal["identified", "oracle_needed"] = (
        "identified" if oracle_assumptions_accepted else "oracle_needed"
    )
    return ProofBundle(
        proof_status=proof_status,
        proof_stratum="A1_extended" if oracle_assumptions_accepted else "A2_oracle_backed",
        theorem_family="proximal_mediation_thm1_dukes_2023",
        completeness_regime=(
            "sound_incomplete" if oracle_assumptions_accepted else "heuristic_backed"
        ),
        implementation_coverage="proximal_mediation_v1_single_mediator",
        graph_ref=graph_ref,
        query_ref=query_ref,
        frontier_sketch_ref=frontier_sketch_ref,
        estimand_ast=None,
        negative_certificate_summary=None,
        proof_trace=list(certificate.proof_trace),
        assumptions=[
            "consistency",
            "positivity",
            "latent_exchangeability_given_U_X",
            "latent_cross_world_given_U_X",
            "proximal_mediation_bridge_existence",
            *[item.name for item in certificate.completeness_conditions],
        ],
        metadata={
            "status": proof_status,
            "method": "proximal_mediation",
            "proximal_mediation_certificate": cert_payload,
            "oracle_assumptions_accepted": oracle_assumptions_accepted,
            "bridge_equations_count": len(certificate.bridge_equations),
            "graph_checks_count": len(certificate.graph_checks),
            **(
                {"frontier_sketch_ref": frontier_sketch_ref.model_dump(mode="json")}
                if frontier_sketch_ref is not None
                else {}
            ),
        },
    )


def build_dynamic_proof_bundle(
    *,
    dynamic_semantics: DynamicSemanticsAttachment,
    theorem_family: str,
    proof_status: Literal["identified", "non_identified", "oracle_needed"],
    graph_ref: str | None = None,
    query_ref: str | None = None,
    estimand_ast: Any = None,
    negative_certificate_summary: str | None = None,
    proof_trace: list[str] | None = None,
    assumptions: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    frontier_sketch_ref: FrontierSketchRef | None = None,
) -> ProofBundle:
    """Construct a proof bundle directly from a dynamic-semantics attachment."""
    payload_metadata = dict(metadata or {})
    payload_metadata.setdefault("status", proof_status)
    if frontier_sketch_ref is not None:
        payload_metadata.setdefault(
            "frontier_sketch_ref",
            frontier_sketch_ref.model_dump(mode="json"),
        )
    return ProofBundle(
        proof_status=proof_status,
        proof_stratum=_proof_stratum_for_result(
            status_raw=proof_status,
            theorem_family=theorem_family,
            dynamic_semantics=dynamic_semantics,
        ),
        theorem_family=theorem_family,
        completeness_regime=_completeness_regime_for_result(
            status_raw=proof_status,
            theorem_family=theorem_family,
            dynamic_semantics=dynamic_semantics,
        ),
        implementation_coverage=_implementation_coverage_for_result(
            status_raw=proof_status,
            theorem_family=theorem_family,
            dynamic_semantics=dynamic_semantics,
        ),
        graph_ref=graph_ref,
        query_ref=query_ref,
        frontier_sketch_ref=frontier_sketch_ref,
        estimand_ast=(
            estimand_ast.model_dump(mode="json")
            if hasattr(estimand_ast, "model_dump")
            else estimand_ast
        ),
        dynamic_semantics=dynamic_semantics,
        negative_certificate_summary=negative_certificate_summary,
        proof_trace=list(proof_trace or []),
        assumptions=list(assumptions or []),
        metadata=payload_metadata,
    )


def build_data_readiness_report(
    *,
    positivity: PositivityDiagnosticReport | dict[str, Any] | None = None,
    support_mismatch: dict[str, Any] | None = None,
    recoverability_certificate: Any | None = None,
    missingness_assessment: MissingnessAssessmentReport | dict[str, Any] | None = None,
    recoverability_certificate_ref: RecoverabilityCertificateRef | dict[str, Any] | None = None,
    joint_decision: Any | None = None,
    joint_decision_ref: JointDecisionCertificateRef | dict[str, Any] | None = None,
    sample_size: int | None = None,
    measurement_quality: Literal["known_good", "proxy_only", "unknown"] = "unknown",
    fallback_data_available: bool = False,
    extra_metrics: dict[str, float] | None = None,
) -> DataReadinessReport:
    """Aggregate existing causal diagnostics into a canonical readiness gate."""
    positivity_report, positivity_warning = _normalize_positivity(positivity)
    missingness_report, missingness_warning = _normalize_missingness_assessment(
        missingness_assessment
    )
    metrics = dict(extra_metrics or {})
    blocking_reasons: list[str] = []
    warnings: list[str] = []
    if positivity_warning is not None:
        warnings.append(positivity_warning)
    if missingness_warning is not None:
        warnings.append(missingness_warning)

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
                warnings.append("support_mismatch_score_invalid")
                logger.warning(
                    "Data readiness report received non-numeric support_mismatch_score=%r",
                    support_score,
                )
        if not passes_support:
            blocking_reasons.append("support_mismatch_failed")

    recoverability_summary = _recoverability_summary(recoverability_certificate)
    if recoverability_summary is None:
        recoverability_summary = _recoverability_summary(joint_decision)
    resolved_recoverability_ref = _typed_ref_from_payload(
        recoverability_certificate_ref,
        RecoverabilityCertificateRef,
    )
    resolved_joint_decision_ref = _typed_ref_from_payload(
        joint_decision_ref,
        JointDecisionCertificateRef,
    )
    if recoverability_summary is not None:
        status = str(recoverability_summary.get("status", "") or "")
        blocking_count = recoverability_summary.get("blocking_r_nodes_count")
        repair_count = recoverability_summary.get("minimal_repair_set_count")
        try:
            metrics.setdefault(
                "recoverability_blocking_r_nodes_count",
                float(blocking_count or 0.0),
            )
        except (TypeError, ValueError):
            warnings.append("recoverability_blocking_count_invalid")
        try:
            metrics.setdefault("recoverability_repair_set_count", float(repair_count or 0.0))
        except (TypeError, ValueError):
            warnings.append("recoverability_repair_count_invalid")
        if status == "not_recoverable":
            blocking_reasons.append("not_recoverable_missingness")
        elif status == "recoverable_under_assumptions":
            warnings.append("assumption_dependent_missingness_recovery")

    if missingness_report is not None:
        metrics.setdefault("missingness_scenario_confidence", missingness_report.scenario_confidence)
        metrics.setdefault(
            "missingness_covariates_present_count",
            float(len(missingness_report.administrative_covariates_present)),
        )
        metrics.setdefault(
            "missingness_covariates_missing_count",
            float(len(missingness_report.administrative_covariates_missing)),
        )
        if missingness_report.testability_audit is not None:
            metrics.setdefault(
                "missingness_implications_tested",
                float(missingness_report.testability_audit.implications_tested),
            )
            metrics.setdefault(
                "missingness_implications_failed",
                float(len(missingness_report.testability_audit.implications_failed)),
            )
            if not missingness_report.testability_audit.overall_valid:
                warnings.append("missingness_implications_failed")
        if missingness_report.status is MissingnessAssessmentStatus.NOT_RECOVERABLE:
            blocking_reasons.append("missingness_not_recoverable")
        elif missingness_report.status is MissingnessAssessmentStatus.UNKNOWN:
            warnings.append("missingness_model_underspecified")
        elif missingness_report.status is MissingnessAssessmentStatus.PARTIALLY_RECOVERABLE:
            warnings.append("missingness_partially_recoverable")

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

    if (
        positivity_report is None
        and positivity is None
        and support_mismatch is None
        and recoverability_summary is None
        and missingness_report is None
        and sample_size is None
    ):
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
        recoverability=recoverability_summary,
        missingness_assessment=missingness_report,
        recoverability_certificate_ref=resolved_recoverability_ref,
        joint_decision_ref=resolved_joint_decision_ref,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        metrics=metrics,
    )


def _normalize_positivity(
    positivity: PositivityDiagnosticReport | dict[str, Any] | None,
) -> tuple[PositivityDiagnosticReport | None, str | None]:
    if positivity is None:
        return None, None
    if isinstance(positivity, PositivityDiagnosticReport):
        return positivity, None
    try:
        return PositivityDiagnosticReport.model_validate(positivity), None
    except (TypeError, ValueError) as exc:
        logger.warning("Failed to parse positivity payload for readiness report: %s", exc)
        return None, "positivity_parse_failed"


def _recoverability_summary(payload: Any) -> dict[str, Any] | None:
    if payload is None:
        return None
    if hasattr(payload, "to_summary_dict"):
        candidate = payload.to_summary_dict()
    elif hasattr(payload, "model_dump"):
        candidate = payload.model_dump(mode="json")
    elif isinstance(payload, dict):
        candidate = dict(payload)
    else:
        return None
    if "recoverability" in candidate and isinstance(candidate["recoverability"], dict):
        candidate = dict(candidate["recoverability"])
    return candidate


def _normalize_missingness_assessment(
    missingness_assessment: MissingnessAssessmentReport | dict[str, Any] | None,
) -> tuple[MissingnessAssessmentReport | None, str | None]:
    if missingness_assessment is None:
        return None, None
    if isinstance(missingness_assessment, MissingnessAssessmentReport):
        return missingness_assessment, None
    try:
        return MissingnessAssessmentReport.model_validate(missingness_assessment), None
    except (TypeError, ValueError) as exc:
        logger.warning("Failed to parse missingness assessment for readiness report: %s", exc)
        return None, "missingness_assessment_parse_failed"


def _joint_decision_summary(payload: Any) -> dict[str, Any] | None:
    if payload is None:
        return None
    if hasattr(payload, "to_summary_dict"):
        candidate = payload.to_summary_dict()
    elif hasattr(payload, "model_dump"):
        candidate = payload.model_dump(mode="json")
    elif isinstance(payload, dict):
        candidate = dict(payload)
    else:
        return None
    if "verdict" not in candidate:
        return None
    return candidate


def _typed_ref_from_payload(payload: Any, ref_cls: type[Any]) -> Any | None:
    if payload is None:
        return None
    if isinstance(payload, ref_cls):
        return payload
    try:
        if hasattr(payload, "model_dump") and not isinstance(payload, dict):
            payload = payload.model_dump(mode="json")
        return ref_cls.model_validate(payload)
    except (TypeError, ValueError):
        return None


def _normalize_composability_status(payload: Any) -> Literal["reusable", "revalidate", "rederive", "unknown"]:
    candidate = str(getattr(payload, "value", payload) or "").strip().lower()
    if candidate in {"reusable", "revalidate", "rederive"}:
        return candidate
    return "unknown"


def _derive_operator_lift_contract(
    *,
    estimand_ast: Any,
    status_raw: str,
    result_metadata: dict[str, Any],
) -> dict[str, Any]:
    operator_target = _extract_operator_target_node(estimand_ast)
    if operator_target is None:
        return {
            "uniform_probe_class_ref": None,
            "operator_lift_allowed": False,
            "operator_lift_scope": "none",
            "operator_lift_reason": None,
            "operator_lift_failure_reason": None,
            "operator_audit_basis_probe_refs": [],
        }

    identification_method = str(
        getattr(estimand_ast, "identification_method", "")
        or result_metadata.get("identification_method")
        or ""
    ).strip().lower()
    uniform_probe_class_ref = (
        str(result_metadata.get("uniform_probe_class_ref") or "").strip()
        or _default_uniform_probe_class_ref(operator_target)
    )
    operator_audit_basis_probe_refs = _normalize_string_list(
        result_metadata.get("operator_audit_basis_probe_refs")
    ) or _default_operator_audit_basis(operator_target)
    probe_contract_declared = (
        operator_target.probe_space_ref.kind == "rkhs"
        and bool(operator_target.probe_space_ref.kernel_ref)
        and operator_target.probe_space_ref.bounded_evaluation is not False
    )
    whole_space_allowed = bool(
        status_raw == "identified"
        and operator_target.identification_scope == "backdoor"
        and operator_target.operator_semantics == "conditional_mean_embedding_operator"
        and identification_method in {"backdoor", "g_formula"}
        and probe_contract_declared
        and uniform_probe_class_ref
    )
    if whole_space_allowed:
        return {
            "uniform_probe_class_ref": uniform_probe_class_ref,
            "operator_lift_allowed": True,
            "operator_lift_scope": "whole_probe_space",
            "operator_lift_reason": "backdoor_uniform_probe_class_identified",
            "operator_lift_failure_reason": None,
            "operator_audit_basis_probe_refs": operator_audit_basis_probe_refs,
        }

    if status_raw != "identified":
        failure_reason = "operator_lift_requires_identified_proof"
    elif operator_target.identification_scope != "backdoor":
        failure_reason = (
            f"operator_lift_scope_deferred:{operator_target.identification_scope}"
        )
    elif operator_target.operator_semantics != "conditional_mean_embedding_operator":
        failure_reason = (
            f"operator_lift_semantics_deferred:{operator_target.operator_semantics}"
        )
    elif not probe_contract_declared:
        failure_reason = "operator_probe_contract_missing"
    else:
        failure_reason = "operator_lift_degraded_to_audit_basis"
    return {
        "uniform_probe_class_ref": uniform_probe_class_ref,
        "operator_lift_allowed": False,
        "operator_lift_scope": "finite_audit_basis",
        "operator_lift_reason": None,
        "operator_lift_failure_reason": failure_reason,
        "operator_audit_basis_probe_refs": operator_audit_basis_probe_refs,
    }


def _extract_operator_target_node(estimand_ast: Any) -> Any | None:
    root = getattr(estimand_ast, "root", None)
    if root is None:
        return None
    node_type = getattr(root, "node_type", None)
    if node_type == "operator_target":
        return root
    if node_type == "operator_apply":
        operator = getattr(root, "operator", None)
        if getattr(operator, "node_type", None) == "operator_target":
            return operator
    return None


def _default_uniform_probe_class_ref(operator_target: Any) -> str | None:
    probe_space = getattr(operator_target, "probe_space_ref", None)
    if probe_space is None:
        return None
    space_id = str(getattr(probe_space, "space_id", "") or "").strip()
    if not space_id:
        return None
    return f"rkhs://{space_id}/unit-ball"


def _default_operator_audit_basis(operator_target: Any) -> list[str]:
    probe_space = getattr(operator_target, "probe_space_ref", None)
    space_id = str(getattr(probe_space, "space_id", "") or "").strip() or "probe_space"
    return [f"{space_id}::audit_basis::coord_0"]


def _normalize_operator_lift_scope(
    payload: Any,
) -> Literal["none", "finite_audit_basis", "whole_probe_space"]:
    candidate = str(getattr(payload, "value", payload) or "").strip().lower()
    if candidate in {"finite_audit_basis", "whole_probe_space"}:
        return candidate
    return "none"


def _normalize_string_list(payload: Any) -> list[str]:
    if payload in (None, ""):
        return []
    if not isinstance(payload, (list, tuple, set)):
        return []
    return sorted({str(item).strip() for item in payload if str(item).strip()})


def _status_value(status: Any) -> str:
    return str(getattr(status, "value", status) or "").strip().lower()


def _extract_dynamic_semantics(payload: Any) -> DynamicSemanticsAttachment | None:
    if payload is None:
        return None
    if isinstance(payload, DynamicSemanticsAttachment):
        return payload
    if isinstance(payload, dict):
        if "dynamic_semantics" not in payload:
            return None
        candidate = payload.get("dynamic_semantics")
    else:
        candidate = getattr(payload, "dynamic_semantics", None)
        if candidate is None:
            candidate = getattr(payload, "metadata", None)
            if isinstance(candidate, dict):
                candidate = candidate.get("dynamic_semantics")
    if candidate is None:
        return None
    if isinstance(candidate, DynamicSemanticsAttachment):
        return candidate
    if hasattr(candidate, "model_dump"):
        candidate = candidate.model_dump(mode="json")
    if not isinstance(candidate, dict):
        return None
    try:
        return DynamicSemanticsAttachment.model_validate(candidate)
    except (TypeError, ValueError):
        logger.warning("Failed to parse dynamic semantics attachment", exc_info=True)
        return None


def _completeness_regime_for_result(
    *,
    status_raw: str,
    theorem_family: str,
    dynamic_semantics: DynamicSemanticsAttachment | None,
) -> Literal["complete", "sound_incomplete", "heuristic_backed"]:
    if dynamic_semantics is not None:
        if dynamic_semantics.reduction_status is DynamicReductionStatus.VALIDATED_REDUCTION:
            return "sound_incomplete"
        return "heuristic_backed"
    if status_raw in {"identified", "hedge_found", "not_recoverable"}:
        return "complete"
    if status_raw in {"oracle_needed", "pag_ambiguous"}:
        return "heuristic_backed"
    family = theorem_family.lower()
    if any(token in family for token in ("sigma", "cyclic", "local_independence", "dynamic")):
        return "heuristic_backed"
    return "sound_incomplete"


def _proof_stratum_for_result(
    *,
    status_raw: str,
    theorem_family: str,
    dynamic_semantics: DynamicSemanticsAttachment | None = None,
) -> Literal["A0_trusted", "A1_extended", "A1_dynamic", "A2_oracle_backed"]:
    family = theorem_family.lower()
    if status_raw in {"oracle_needed", "pag_ambiguous"}:
        return "A2_oracle_backed"
    if dynamic_semantics is not None or any(
        token in family for token in ("sigma", "cyclic", "local_independence", "dynamic")
    ):
        return "A1_dynamic"
    if any(
        token in family
        for token in (
            "sigma",
            "cyclic",
            "recover",
            "id_star",
            "idc_star",
            "ctf",
            "dist_",
            "proximal",
        )
    ):
        return "A1_extended"
    return "A0_trusted"


def _implementation_coverage_for_result(
    *,
    status_raw: str,
    theorem_family: str,
    dynamic_semantics: DynamicSemanticsAttachment | None = None,
) -> str:
    if dynamic_semantics is not None:
        if dynamic_semantics.reduction_status is DynamicReductionStatus.VALIDATED_REDUCTION:
            return f"declared-dynamic-scope:{theorem_family or 'dynamic'}"
        if dynamic_semantics.reduction_status is DynamicReductionStatus.BLOCKED:
            return f"dynamic-research-boundary:{theorem_family or 'dynamic'}"
        return f"heuristic-dynamic-scope:{theorem_family or 'dynamic'}"
    if status_raw == "oracle_needed":
        return f"conditional-coverage:{theorem_family or 'oracle'}"
    if status_raw == "pag_ambiguous":
        return "sound only under oriented-equivalence handling policy"
    return f"declared-scope:{theorem_family or 'native_id'}"


def _extract_assumptions_from_estimand(estimand_ast: Any) -> list[str]:
    if estimand_ast is None:
        return []
    if isinstance(estimand_ast, dict):
        payload = estimand_ast.get("assumptions")
        if isinstance(payload, (list, tuple, set)):
            return [str(item).strip() for item in payload if str(item).strip()]
        return []
    payload = getattr(estimand_ast, "assumptions", None)
    if isinstance(payload, (list, tuple, set)):
        return [str(item).strip() for item in payload if str(item).strip()]
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
    "build_dynamic_proof_bundle",
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
    "proof_bundle_from_proximal_mediation_certificate",
    "proof_bundle_from_proximal_certificate",
]
