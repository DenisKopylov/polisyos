"""DP distortion certificates for causal identification proof bundles."""

from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics.partial_identification import BoundMethod, BoundsBundle, BoundsMethodSummary
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import DPRobustnessCertificateRef

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal import DataReadinessReport, ProofBundle


class DPMechanismFamily(str, Enum):
    """Supported DP release families for proof-level robustness accounting."""

    LAPLACE = "laplace"
    GAUSSIAN = "gaussian"
    ANALYTIC_GAUSSIAN = "analytic_gaussian"
    RANDOMIZED_RESPONSE = "randomized_response"
    CUSTOM = "custom"


class DPAdjacency(str, Enum):
    """Neighboring-database relation used to calibrate the release."""

    ADD_REMOVE_ONE = "add_remove_one"
    REPLACE_ONE = "replace_one"
    USER_LEVEL = "user_level"
    CUSTOM = "custom"


class DPSensitivityNorm(str, Enum):
    """Sensitivity norm recorded in the DP certificate."""

    L1 = "l1"
    L2 = "l2"
    LINF = "linf"
    CUSTOM = "custom"


class DPCompositionAccountant(str, Enum):
    """Composition accountant used when a release spends multiple DP budgets."""

    BASIC = "basic"
    ADVANCED = "advanced"
    MOMENTS = "moments"
    RDP = "rdp"
    EXPLICIT_LEDGER = "explicit_ledger"
    UNKNOWN = "unknown"


class DPReleasedStatistics(str, Enum):
    """Shape of the privatized statistics made available to the proof kernel."""

    FULL_HISTOGRAM = "full_histogram"
    MARGINALS = "marginals"
    QUERY_SPECIFIC_SUFFICIENT_STATS = "query_specific_sufficient_stats"
    CUSTOM = "custom"


class DPGraphProvenanceSource(str, Enum):
    """How the causal graph was obtained relative to the private release."""

    TRUSTED_EXTERNAL = "trusted_external"
    NONPRIVATE_SCHEMA_REGISTRY = "graph_from_nonprivate_schema_registry"
    LEARNED_PRIVATE = "learned_private"
    LEARNED_UNTRUSTED_ON_PRIVATE_RELEASE = "learned_untrusted_on_private_release"
    UNKNOWN = "unknown"


class DPProofStepKind(str, Enum):
    """Robustness class of a proof-trace step under DP distortion."""

    GRAPH_ONLY = "graph_only"
    ALGEBRAIC = "algebraic"
    THRESHOLD_TEST = "threshold_test"


class DPRobustnessStatus(str, Enum):
    """Effective proof validity after the DP observation channel is considered."""

    IDENTIFIED = "identified"
    BOUNDED = "bounded"
    UNIDENTIFIABLE = "unidentifiable"
    BLOCKED = "blocked"


class DPHardBlockReason(str, Enum):
    """Machine-readable reasons that must stop estimation on DP-distorted data."""

    GRAPH_UNTRUSTED = "graph_untrusted"
    MECHANISM_UNKNOWN = "mechanism_unknown"
    NAIVE_CI_ON_PRIVATE_DATA = "naive_ci_on_private_data"
    PROOF_NOT_IDENTIFIED = "proof_not_identified"
    SUPPORT_MARGIN_FAILED = "support_margin_failed"
    THRESHOLD_STEP_UNCERTIFIED = "threshold_step_uncertified"
    UNCERTAINTY_CROSSES_NONID_BOUNDARY = "uncertainty_crosses_nonid_boundary"


class DPMechanismSpec(BaseModel):
    """Mechanism and accounting details used to derive the distortion radius."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    family: DPMechanismFamily
    epsilon: float = Field(gt=0.0)
    delta: float = Field(default=0.0, ge=0.0, lt=1.0)
    adjacency: DPAdjacency = DPAdjacency.ADD_REMOVE_ONE
    sensitivity_norm: DPSensitivityNorm
    sensitivity_value: float = Field(gt=0.0)
    composition_accountant: DPCompositionAccountant = DPCompositionAccountant.BASIC
    postprocessing: list[str] = Field(default_factory=list)
    calibration: dict[str, Any] = Field(default_factory=dict)


class DPReleaseScope(BaseModel):
    """Scope and sample size of the privatized statistics release."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    released_statistics: DPReleasedStatistics
    cell_count_k: int = Field(ge=1)
    sample_size_n: int = Field(ge=1)
    statistics_ref: str | None = None


class DPGraphProvenance(BaseModel):
    """Graph provenance needed to separate structural ID from private discovery."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: DPGraphProvenanceSource
    graph_ref: str | None = None
    graph_hash: str | None = None


class DPDistortionModel(BaseModel):
    """High-probability uncertainty set induced by the private release."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    confidence_level: float = Field(gt=0.0, lt=1.0)
    alpha: float = Field(gt=0.0, lt=1.0)
    norm: Literal["linf"] = "linf"
    radius: float = Field(ge=0.0)
    uncertainty_set_ref: str | None = None


class DPProofTraceAuditStep(BaseModel):
    """One proof-trace step classified by DP robustness requirements."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str
    kind: DPProofStepKind
    operation: str
    robust: bool
    requires_margin: bool = False
    margin_certified: bool | None = None
    dp_test_ref: str | None = None
    reason: str | None = None

    @property
    def is_uncertified_threshold_step(self) -> bool:
        """Return true when a discrete decision step lacks a DP-valid witness."""

        if self.kind is not DPProofStepKind.THRESHOLD_TEST:
            return False
        return not self.robust and self.dp_test_ref is None and self.margin_certified is not True


class DPLocalStability(BaseModel):
    """Local analytic stability data for the identifying functional."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    conditioning_depth: int = Field(default=0, ge=0)
    min_denominator_margin: float | None = Field(default=None, ge=0.0)
    decision_margin: float | None = Field(default=None, ge=0.0)
    lipschitz_upper_bound: float | None = Field(default=None, ge=0.0)
    policy_tolerance: float | None = Field(default=None, ge=0.0)


class DPEffectiveValidity(BaseModel):
    """Effective certificate status under the DP distortion model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: DPRobustnessStatus
    reason: str
    effect_interval: tuple[float, float] | None = None
    tolerance_met: bool | None = None

    @model_validator(mode="after")
    def _validate_interval_order(self) -> DPEffectiveValidity:
        if self.effect_interval is not None and self.effect_interval[0] > self.effect_interval[1]:
            raise ValueError("effect_interval lower bound must be <= upper bound")
        return self


class DPAmplificationRequirements(BaseModel):
    """Sample-size and privacy-budget requirements for non-degraded validity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    n_min_for_identified: int | None = Field(default=None, ge=1)
    epsilon_min_for_identified: float | None = Field(default=None, gt=0.0)
    sample_size_amplification_required: bool = False


class DPHardBlock(BaseModel):
    """Machine-actionable hard-block decision for unsafe estimation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    blocked: bool
    block_reason_code: DPHardBlockReason | None = None

    @model_validator(mode="after")
    def _validate_reason_presence(self) -> DPHardBlock:
        if self.blocked and self.block_reason_code is None:
            raise ValueError("blocked DP certificates require block_reason_code")
        if not self.blocked and self.block_reason_code is not None:
            raise ValueError("block_reason_code must be omitted when blocked is false")
        return self


class DPRobustnessCertificate(BaseModel):
    """Typed artifact recording proof validity under a DP-distorted distribution.

    ``ProofBundle.proof_status`` remains the structural identification verdict.
    This certificate is the runtime layer that decides whether a DP release still
    supports point estimation, only bounds, explanation-only output, or a hard
    execution block.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    mechanism: DPMechanismSpec
    release_scope: DPReleaseScope
    graph_provenance: DPGraphProvenance
    distortion_model: DPDistortionModel
    proof_trace_audit: list[DPProofTraceAuditStep] = Field(default_factory=list)
    local_stability: DPLocalStability = Field(default_factory=DPLocalStability)
    effective_validity: DPEffectiveValidity
    amplification_requirements: DPAmplificationRequirements = Field(
        default_factory=DPAmplificationRequirements
    )
    hard_block: DPHardBlock
    metadata: dict[str, Any] = Field(default_factory=dict)


def coerce_dp_robustness_certificate(payload: Any | None) -> DPRobustnessCertificate | None:
    """Normalize DP robustness payloads from instances, dicts, or nested metadata."""

    if payload is None:
        return None
    if isinstance(payload, DPRobustnessCertificate):
        return payload

    candidate = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    if not isinstance(candidate, dict):
        return None

    nested = candidate.get("dp_robustness_certificate")
    if isinstance(nested, dict):
        candidate = nested

    required_keys = {
        "mechanism",
        "release_scope",
        "graph_provenance",
        "distortion_model",
        "effective_validity",
        "hard_block",
    }
    if not required_keys.issubset(candidate):
        return None

    try:
        return DPRobustnessCertificate.model_validate(candidate)
    except (TypeError, ValueError):
        return None


def dp_robustness_summary(
    certificate: DPRobustnessCertificate,
    *,
    ref: DPRobustnessCertificateRef | None = None,
) -> dict[str, Any]:
    """Return the compact machine-readable summary stored on proof/readiness artifacts."""

    return {
        "effective_status": certificate.effective_validity.status.value,
        "reason": certificate.effective_validity.reason,
        "block_reason": (
            certificate.hard_block.block_reason_code.value
            if certificate.hard_block.block_reason_code is not None
            else None
        ),
        "distortion_radius": certificate.distortion_model.radius,
        "distortion_norm": certificate.distortion_model.norm,
        "epsilon": certificate.mechanism.epsilon,
        "delta": certificate.mechanism.delta,
        "mechanism_family": certificate.mechanism.family.value,
        "n_min_for_identified": certificate.amplification_requirements.n_min_for_identified,
        "epsilon_min_for_identified": certificate.amplification_requirements.epsilon_min_for_identified,
        "sample_size_amplification_required": (
            certificate.amplification_requirements.sample_size_amplification_required
        ),
        "effect_interval": list(certificate.effective_validity.effect_interval)
        if certificate.effective_validity.effect_interval is not None
        else None,
        "dp_robustness_ref": ref.model_dump(mode="json") if ref is not None else None,
    }


def laplace_histogram_linf_radius(
    *,
    alpha: float,
    cell_count_k: int,
    sample_size_n: int,
    epsilon: float,
    sensitivity_value: float = 1.0,
) -> float:
    """High-probability L-infinity radius for normalized Laplace-noised counts."""

    _validate_radius_inputs(
        alpha=alpha,
        cell_count_k=cell_count_k,
        sample_size_n=sample_size_n,
        epsilon=epsilon,
        sensitivity_value=sensitivity_value,
    )
    return sensitivity_value * math.log(cell_count_k / alpha) / (sample_size_n * epsilon)


def classical_gaussian_sigma(
    *,
    epsilon: float,
    delta: float,
    l2_sensitivity: float = 1.0,
) -> float:
    """Classical Gaussian-mechanism standard deviation calibration."""

    if epsilon <= 0.0:
        raise ValueError("epsilon must be positive")
    if not 0.0 < delta < 1.0:
        raise ValueError("delta must be in (0, 1) for Gaussian calibration")
    if l2_sensitivity <= 0.0:
        raise ValueError("l2_sensitivity must be positive")
    return l2_sensitivity * math.sqrt(2.0 * math.log(1.25 / delta)) / epsilon


def gaussian_histogram_linf_radius(
    *,
    alpha: float,
    cell_count_k: int,
    sample_size_n: int,
    sigma: float,
) -> float:
    """High-probability L-infinity radius for normalized Gaussian-noised counts."""

    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    if cell_count_k < 1:
        raise ValueError("cell_count_k must be >= 1")
    if sample_size_n < 1:
        raise ValueError("sample_size_n must be >= 1")
    if sigma <= 0.0:
        raise ValueError("sigma must be positive")
    return sigma * math.sqrt(2.0 * math.log(cell_count_k / alpha)) / sample_size_n


def histogram_linf_radius_from_context(
    mechanism: DPMechanismSpec,
    release_scope: DPReleaseScope,
    *,
    alpha: float,
) -> float:
    """Compute a conservative histogram distortion radius for known mechanisms."""

    if mechanism.family is DPMechanismFamily.LAPLACE:
        return laplace_histogram_linf_radius(
            alpha=alpha,
            cell_count_k=release_scope.cell_count_k,
            sample_size_n=release_scope.sample_size_n,
            epsilon=mechanism.epsilon,
            sensitivity_value=mechanism.sensitivity_value,
        )

    if mechanism.family in {
        DPMechanismFamily.GAUSSIAN,
        DPMechanismFamily.ANALYTIC_GAUSSIAN,
    }:
        sigma_raw = mechanism.calibration.get("sigma")
        if sigma_raw is None:
            sigma = classical_gaussian_sigma(
                epsilon=mechanism.epsilon,
                delta=mechanism.delta,
                l2_sensitivity=mechanism.sensitivity_value,
            )
        else:
            sigma = float(sigma_raw)
        return gaussian_histogram_linf_radius(
            alpha=alpha,
            cell_count_k=release_scope.cell_count_k,
            sample_size_n=release_scope.sample_size_n,
            sigma=sigma,
        )

    raise ValueError(f"no built-in radius formula for DP mechanism '{mechanism.family.value}'")


def build_dp_distortion_model(
    mechanism: DPMechanismSpec,
    release_scope: DPReleaseScope,
    *,
    alpha: float,
    uncertainty_set_ref: str | None = None,
) -> DPDistortionModel:
    """Build a DP distortion model from mechanism/release metadata."""

    return DPDistortionModel(
        confidence_level=1.0 - alpha,
        alpha=alpha,
        radius=histogram_linf_radius_from_context(
            mechanism,
            release_scope,
            alpha=alpha,
        ),
        uncertainty_set_ref=uncertainty_set_ref,
    )


def evaluate_dp_effective_validity(
    *,
    proof_status: Literal["identified", "non_identified", "oracle_needed"],
    graph_provenance: DPGraphProvenance,
    distortion_model: DPDistortionModel,
    proof_trace_audit: list[DPProofTraceAuditStep] | None = None,
    local_stability: DPLocalStability | None = None,
) -> tuple[DPEffectiveValidity, DPHardBlock]:
    """Evaluate graceful degradation or hard block for a structural proof."""

    trace = list(proof_trace_audit or [])
    stability = local_stability or DPLocalStability()
    radius = distortion_model.radius

    if proof_status != "identified":
        status = DPEffectiveValidity(
            status=DPRobustnessStatus.UNIDENTIFIABLE,
            reason="structural proof is not identified; DP cannot upgrade the certificate",
            tolerance_met=False,
        )
        block = DPHardBlock(blocked=False)
        return status, block

    if graph_provenance.source in {
        DPGraphProvenanceSource.LEARNED_UNTRUSTED_ON_PRIVATE_RELEASE,
        DPGraphProvenanceSource.UNKNOWN,
    }:
        status = DPEffectiveValidity(
            status=DPRobustnessStatus.BLOCKED,
            reason="graph provenance is not trusted under the private release",
            tolerance_met=False,
        )
        block = DPHardBlock(
            blocked=True,
            block_reason_code=DPHardBlockReason.GRAPH_UNTRUSTED,
        )
        return status, block

    uncertified = [step for step in trace if step.is_uncertified_threshold_step]
    if uncertified:
        reason_code = _threshold_block_reason(uncertified)
        status = DPEffectiveValidity(
            status=DPRobustnessStatus.BLOCKED,
            reason="proof trace contains threshold/test decisions without DP calibration or margin",
            tolerance_met=False,
        )
        block = DPHardBlock(blocked=True, block_reason_code=reason_code)
        return status, block

    margin = stability.min_denominator_margin
    if margin is not None and margin <= 2.0 * radius:
        status = DPEffectiveValidity(
            status=DPRobustnessStatus.BLOCKED,
            reason="DP distortion radius reaches the support/positivity margin",
            tolerance_met=False,
        )
        block = DPHardBlock(
            blocked=True,
            block_reason_code=DPHardBlockReason.SUPPORT_MARGIN_FAILED,
        )
        return status, block

    lipschitz = stability.lipschitz_upper_bound
    tolerance = stability.policy_tolerance
    if lipschitz is None or tolerance is None:
        status = DPEffectiveValidity(
            status=DPRobustnessStatus.BOUNDED,
            reason=(
                "structural proof is identified, but no local Lipschitz/tolerance "
                "witness certifies point use under DP"
            ),
            tolerance_met=False,
        )
        block = DPHardBlock(blocked=False)
        return status, block

    error_bound = lipschitz * radius
    if error_bound <= tolerance:
        status = DPEffectiveValidity(
            status=DPRobustnessStatus.IDENTIFIED,
            reason=(
                "structural proof and DP distortion audit permit point estimation within tolerance"
            ),
            tolerance_met=True,
        )
        block = DPHardBlock(blocked=False)
        return status, block

    status = DPEffectiveValidity(
        status=DPRobustnessStatus.BOUNDED,
        reason=(
            "structural proof is identified, but DP distortion exceeds the point-estimate tolerance"
        ),
        tolerance_met=False,
    )
    block = DPHardBlock(blocked=False)
    return status, block


def build_dp_robustness_certificate(
    *,
    proof_status: Literal["identified", "non_identified", "oracle_needed"],
    mechanism: DPMechanismSpec,
    release_scope: DPReleaseScope,
    graph_provenance: DPGraphProvenance,
    distortion_model: DPDistortionModel,
    proof_trace_audit: list[DPProofTraceAuditStep] | None = None,
    local_stability: DPLocalStability | None = None,
    amplification_requirements: DPAmplificationRequirements | None = None,
    metadata: dict[str, Any] | None = None,
) -> DPRobustnessCertificate:
    """Construct a certificate and compute its effective DP validity status."""

    trace = list(proof_trace_audit or [])
    stability = local_stability or DPLocalStability()
    effective, hard_block = evaluate_dp_effective_validity(
        proof_status=proof_status,
        graph_provenance=graph_provenance,
        distortion_model=distortion_model,
        proof_trace_audit=trace,
        local_stability=stability,
    )
    requirements = amplification_requirements or amplification_requirements_for_identified(
        mechanism=mechanism,
        release_scope=release_scope,
        distortion_model=distortion_model,
        local_stability=stability,
    )
    return DPRobustnessCertificate(
        mechanism=mechanism,
        release_scope=release_scope,
        graph_provenance=graph_provenance,
        distortion_model=distortion_model,
        proof_trace_audit=trace,
        local_stability=stability,
        effective_validity=effective,
        amplification_requirements=requirements,
        hard_block=hard_block,
        metadata=dict(metadata or {}),
    )


def bounds_bundle_from_dp_robustness_certificate(
    certificate: DPRobustnessCertificate,
    *,
    estimand_type: str = "causal_effect",
) -> BoundsBundle | None:
    """Lift a bounded DP certificate into the canonical bounds surface."""

    interval = certificate.effective_validity.effect_interval
    if interval is None:
        return None

    lower, upper = interval
    width = upper - lower
    return BoundsBundle(
        estimand_type=estimand_type,
        point_identified=abs(width) <= 1e-12,
        lower_bound=lower,
        upper_bound=upper,
        consensus_lower=lower,
        consensus_upper=upper,
        sharpness_status="outer_approx",
        method_summaries=[
            BoundsMethodSummary(
                method=BoundMethod.DP_ROBUSTNESS,
                lower_bound=lower,
                upper_bound=upper,
                bound_width=width,
                assumptions_used=list(
                    dict(certificate.metadata).get("assumptions_used", [])
                ),
                bounds_type="dp_distortion",
                display_label="DP Robustness Bounds",
            )
        ],
        warnings=["dp_bounds_only"],
        metadata={
            "dp_effective_status": certificate.effective_validity.status.value,
            "dp_distortion_radius": certificate.distortion_model.radius,
            "dp_block_reason": (
                certificate.hard_block.block_reason_code.value
                if certificate.hard_block.block_reason_code is not None
                else None
            ),
            "dp_mechanism_family": certificate.mechanism.family.value,
        },
    )


def apply_dp_readiness_gate(
    report: DataReadinessReport,
    certificate: DPRobustnessCertificate,
) -> DataReadinessReport:
    """Project DP runtime validity into the causal readiness gate."""

    summary = dp_robustness_summary(certificate)
    warnings = list(report.warnings)
    blocking_reasons = list(report.blocking_reasons)
    metrics = dict(report.metrics)
    metrics.setdefault("dp_distortion_radius", certificate.distortion_model.radius)
    metrics.setdefault("dp_epsilon", certificate.mechanism.epsilon)
    metrics.setdefault(
        "dp_sample_size_amplification_required",
        1.0 if certificate.amplification_requirements.sample_size_amplification_required else 0.0,
    )

    status = certificate.effective_validity.status
    decision = report.decision
    can_compile = report.can_compile_estimation
    can_run = report.can_run_estimation

    if status is DPRobustnessStatus.BOUNDED:
        if "dp_bounds_only" not in warnings:
            warnings.append("dp_bounds_only")
        if decision != "block":
            decision = "warn"
        can_run = False
    elif status is DPRobustnessStatus.UNIDENTIFIABLE:
        blocking_reasons.append("dp_unidentifiable")
        decision = "block"
        can_compile = False
        can_run = False
    elif status is DPRobustnessStatus.BLOCKED:
        code = (
            certificate.hard_block.block_reason_code.value
            if certificate.hard_block.block_reason_code is not None
            else "dp_blocked"
        )
        blocking_reasons.append(code)
        decision = "block"
        can_compile = False
        can_run = False

    return report.model_copy(
        update={
            "decision": decision,
            "can_compile_estimation": can_compile,
            "can_run_estimation": can_run,
            "blocking_reasons": blocking_reasons,
            "warnings": warnings,
            "metrics": metrics,
            "dp_distortion": summary,
        }
    )


def amplification_requirements_for_identified(
    *,
    mechanism: DPMechanismSpec,
    release_scope: DPReleaseScope,
    distortion_model: DPDistortionModel,
    local_stability: DPLocalStability,
) -> DPAmplificationRequirements:
    """Compute sufficient sample-size and epsilon requirements for point validity."""

    rho_star = _rho_star(local_stability)
    if rho_star is None:
        return DPAmplificationRequirements(sample_size_amplification_required=True)

    alpha = distortion_model.alpha
    k = release_scope.cell_count_k
    epsilon_min: float | None = None
    n_min: int | None = None

    if mechanism.family is DPMechanismFamily.LAPLACE:
        numerator = mechanism.sensitivity_value * math.log(k / alpha)
        n_min = math.ceil(numerator / (mechanism.epsilon * rho_star))
        epsilon_min = numerator / (release_scope.sample_size_n * rho_star)
    elif mechanism.family in {
        DPMechanismFamily.GAUSSIAN,
        DPMechanismFamily.ANALYTIC_GAUSSIAN,
    }:
        sigma_raw = mechanism.calibration.get("sigma")
        sigma = (
            float(sigma_raw)
            if sigma_raw is not None
            else classical_gaussian_sigma(
                epsilon=mechanism.epsilon,
                delta=mechanism.delta,
                l2_sensitivity=mechanism.sensitivity_value,
            )
        )
        n_min = math.ceil(sigma * math.sqrt(2.0 * math.log(k / alpha)) / rho_star)

    return DPAmplificationRequirements(
        n_min_for_identified=n_min,
        epsilon_min_for_identified=epsilon_min,
        sample_size_amplification_required=(n_min is None or release_scope.sample_size_n < n_min),
    )


def attach_dp_robustness_to_proof_bundle(
    bundle: ProofBundle,
    ref: DPRobustnessCertificateRef | None,
    certificate: DPRobustnessCertificate,
) -> ProofBundle:
    """Attach DP robustness metadata/ref while preserving structural proof status."""

    metadata = dict(bundle.metadata)
    summary = dp_robustness_summary(certificate, ref=ref)
    metadata["dp_context"] = {
        "mechanism_family": summary["mechanism_family"],
        "epsilon": summary["epsilon"],
        "delta": summary["delta"],
        "distortion_norm": summary["distortion_norm"],
        "distortion_radius": summary["distortion_radius"],
    }
    metadata["dp_robustness_ref"] = summary["dp_robustness_ref"]
    metadata["dp_effective_status"] = summary["effective_status"]
    metadata["dp_block_reason"] = summary["block_reason"]
    return bundle.model_copy(update={"dp_robustness_ref": ref, "metadata": metadata})


def persist_dp_robustness_certificate(
    store: ArtifactStore,
    certificate: DPRobustnessCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.dp_robustness_certificate",
    schema_version: str = "1.0",
) -> DPRobustnessCertificateRef:
    """Persist a DP robustness certificate and return its typed artifact reference."""

    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.dp_robustness_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return DPRobustnessCertificateRef.model_validate(ref)


def load_dp_robustness_certificate(
    store: ArtifactStore,
    ref: DPRobustnessCertificateRef,
) -> DPRobustnessCertificate:
    """Load a persisted DP robustness certificate."""

    payload = get_json_artifact(store, ref.artifact_id)
    return DPRobustnessCertificate.model_validate(payload)


def _rho_star(local_stability: DPLocalStability) -> float | None:
    candidates: list[float] = []
    if local_stability.min_denominator_margin is not None:
        candidates.append(local_stability.min_denominator_margin / 2.0)
    if (
        local_stability.policy_tolerance is not None
        and local_stability.lipschitz_upper_bound is not None
        and local_stability.lipschitz_upper_bound > 0.0
    ):
        candidates.append(local_stability.policy_tolerance / local_stability.lipschitz_upper_bound)
    if local_stability.decision_margin is not None:
        candidates.append(local_stability.decision_margin)
    if not candidates:
        return None
    return min(candidates)


def _threshold_block_reason(
    steps: list[DPProofTraceAuditStep],
) -> DPHardBlockReason:
    operations = {step.operation.lower() for step in steps}
    if any("ci" in operation or "independ" in operation for operation in operations):
        return DPHardBlockReason.NAIVE_CI_ON_PRIVATE_DATA
    return DPHardBlockReason.THRESHOLD_STEP_UNCERTIFIED


def _validate_radius_inputs(
    *,
    alpha: float,
    cell_count_k: int,
    sample_size_n: int,
    epsilon: float,
    sensitivity_value: float,
) -> None:
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    if cell_count_k < 1:
        raise ValueError("cell_count_k must be >= 1")
    if sample_size_n < 1:
        raise ValueError("sample_size_n must be >= 1")
    if epsilon <= 0.0:
        raise ValueError("epsilon must be positive")
    if sensitivity_value <= 0.0:
        raise ValueError("sensitivity_value must be positive")


__all__ = [
    "DPAdjacency",
    "DPAmplificationRequirements",
    "DPCompositionAccountant",
    "DPDistortionModel",
    "DPEffectiveValidity",
    "DPGraphProvenance",
    "DPGraphProvenanceSource",
    "DPHardBlock",
    "DPHardBlockReason",
    "DPLocalStability",
    "DPMechanismFamily",
    "DPMechanismSpec",
    "DPProofStepKind",
    "DPProofTraceAuditStep",
    "DPReleaseScope",
    "DPReleasedStatistics",
    "DPRobustnessCertificate",
    "DPRobustnessStatus",
    "DPSensitivityNorm",
    "amplification_requirements_for_identified",
    "apply_dp_readiness_gate",
    "attach_dp_robustness_to_proof_bundle",
    "bounds_bundle_from_dp_robustness_certificate",
    "build_dp_distortion_model",
    "build_dp_robustness_certificate",
    "classical_gaussian_sigma",
    "coerce_dp_robustness_certificate",
    "dp_robustness_summary",
    "evaluate_dp_effective_validity",
    "gaussian_histogram_linf_radius",
    "histogram_linf_radius_from_context",
    "laplace_histogram_linf_radius",
    "load_dp_robustness_certificate",
    "persist_dp_robustness_certificate",
]
