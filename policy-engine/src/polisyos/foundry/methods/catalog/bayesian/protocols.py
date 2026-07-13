"""Define posterior-result contracts and small sampling utilities for Bayesian methods."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, ClassVar

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.observability.truthfulness import (
    TruthfulnessReceipt,
    validate_truthfulness_receipt,
)
from polisyos.core.observability.truthfulness import (
    TruthfulnessTier as ReceiptTruthfulnessTier,
)
from polisyos.core.observability.truthfulness import (
    parse_truthfulness_tier as parse_receipt_truthfulness_tier,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    NativeValueEstimandBinding,
    OutputContractDeclaration,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    ValueUncertaintyProjectionKind,
    value_uncertainty_output_contract,
)
from polisyos.ir.model_layer.canon import CanonSpec, content_hash, to_canonical_bytes

from .prior_sensitivity import (
    PriorSensitivityReport,
    infer_bayesian_policy_model_family,
    not_run_prior_sensitivity_report,
)


class TruthfulnessTier(StrEnum):
    """Typed runtime guarantees for posterior summaries."""

    EXACT = "EXACT"
    ASYMPTOTIC = "ASYMPTOTIC"
    APPROXIMATE_CALIBRATED = "APPROXIMATE_CALIBRATED"
    APPROXIMATE_UNCALIBRATED = "APPROXIMATE_UNCALIBRATED"


class TruthfulnessEvidence(BaseModel):
    """Structured evidence backing a runtime truthfulness assignment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tier: TruthfulnessTier = TruthfulnessTier.APPROXIMATE_UNCALIBRATED
    basis: str = "safe_default_without_runtime_evidence"
    assumptions_checked: dict[str, bool] = Field(default_factory=dict)
    diagnostics: dict[str, float | int | str | bool] = Field(default_factory=dict)
    downgrade_reasons: list[str] = Field(default_factory=list)
    benchmark_regime: str | None = None
    coverage_tolerance: float | None = None


class SimulatorDiagnosticArtifact(BaseModel):
    """Regime-aware simulator diagnostic artifact for policy SBI posteriors."""

    contract_id: ClassVar[str] = "foundry.sbi.simulator_diagnostic.v1"
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    schema_id: str = Field(default=contract_id, alias="schema")
    observed_regime: dict[str, Any] = Field(default_factory=dict)
    support_quantile: float | None = None
    knn_radius_mahalanobis: float | None = None
    effective_local_simulations: int | None = None
    local_c2st_score: float | None = None
    posterior_sbc_error: float | None = None
    tarp_coverage_error: float | None = None
    ppc_mahalanobis: float | None = None
    status: str = "unknown"
    failure_mode: tuple[str, ...] = ()
    recommended_action: tuple[str, ...] = ()
    artifact_ref: str | None = None


class MultimodalityState(StrEnum):
    """Conservative posterior geometry state for sampled-support diagnostics."""

    NOT_ASSESSED = "not_assessed"
    INCONCLUSIVE_SAMPLING_GEOMETRY = "inconclusive_sampling_geometry"
    INCONCLUSIVE_LOW_ESS = "inconclusive_low_ess"
    INCONCLUSIVE_UNVISITED_MODES_POSSIBLE = "inconclusive_unvisited_modes_possible"
    NOT_DETECTED_IN_VISITED_SUPPORT = "not_detected_in_visited_support"
    AMBIGUOUS = "ambiguous"
    MULTIMODALITY_DETECTED = "multimodality_detected"
    MULTIMODALITY_DETECTED_POLICY_INVARIANT = "multimodality_detected_policy_invariant"
    MULTIMODALITY_DETECTED_POLICY_RELEVANT = "multimodality_detected_policy_relevant"


class MultimodalityScope(StrEnum):
    """Draw space used by a multimodality diagnostic."""

    JOINT_UNCONSTRAINED_PARAMETERS = "joint_unconstrained_parameters"
    SELECTED_PARAMETERS = "selected_parameters"
    GENERATED_QUANTITIES = "generated_quantities"
    POLICY_FUNCTIONS = "policy_functions"
    LP_ENERGY = "lp_energy"


class ModeWeightReliability(StrEnum):
    """Semantics of reported mode weights."""

    RELIABLE_POSTERIOR_MASS = "reliable_posterior_mass"
    OBSERVED_DRAW_FRACTION_ONLY = "observed_draw_fraction_only"
    STACKED_PREDICTIVE_ONLY = "stacked_predictive_only"
    UNKNOWN = "unknown"


class PolicyRelevanceClassification(StrEnum):
    """Whether detected posterior modes affect policy choice."""

    NOT_ASSESSED = "not_assessed"
    POLICY_INVARIANT = "policy_invariant"
    POLICY_SENSITIVE = "policy_sensitive"
    WEIGHT_SENSITIVE = "weight_sensitive"
    UNKNOWN = "unknown"


class PosteriorReadiness(StrEnum):
    """Readiness downgrade emitted by posterior geometry diagnostics."""

    UNCHANGED = "unchanged"
    CAUTION = "caution"
    CONDITIONAL = "conditional"
    NOT_READY = "not_ready"
    REFUSE_SINGLE_POLICY = "refuse_single_policy"


class MultimodalityTestMetadata(BaseModel):
    """Configuration and calibration metadata for PMD-HMC-like diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = "PMD-HMC"
    version: str = "0.1.0"
    p_global: float | None = None
    alpha_detect: float = 0.01
    alpha_warn: float = 0.10
    view_count: int = 0
    observer_strategy: str = "not_assessed"
    projection_strategy: str = "not_assessed"
    calibration_method: str = "not_assessed"
    n_eff_used: float | None = None
    null_reference: tuple[str, ...] = ()


class SamplerAdequacyStatus(BaseModel):
    """Sampler-adequacy gate used before interpreting multimodality evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rhat_max: float | None = None
    bulk_ess_min: float | None = None
    tail_ess_min: float | None = None
    divergences: float | None = None
    bfmi_min: float | None = None
    max_treedepth_saturation_rate: float | None = None
    passed: bool = False


class DetectedModesStatus(BaseModel):
    """Lower-bound mode-count disclosure for sampled posterior support."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    n_detected_lower_bound: int = 0
    mode_ids: tuple[str, ...] = ()
    assignments_available: bool = False
    mode_weight_reliability: ModeWeightReliability = ModeWeightReliability.UNKNOWN


class PolicyRelevanceStatus(BaseModel):
    """Policy relevance disclosure for detected posterior modes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assessed: bool = False
    classification: PolicyRelevanceClassification = PolicyRelevanceClassification.NOT_ASSESSED
    single_recommendation_allowed: bool = False


class MultimodalityDowngrade(BaseModel):
    """Deterministic readiness policy derived from posterior geometry state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    posterior_readiness: PosteriorReadiness = PosteriorReadiness.UNCHANGED
    ordinary_mean_summary_allowed: bool = True
    mode_conditional_reporting_required: bool = False
    summary_policy: str = "ordinary_posterior_summaries_allowed"
    recommendation_policy: str = "single_policy_recommendation_allowed"


class MultimodalityStatus(BaseModel):
    """Contract for sampled-support multimodality and posterior geometry reporting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: MultimodalityState = MultimodalityState.NOT_ASSESSED
    scope: tuple[MultimodalityScope, ...] = ()
    test: MultimodalityTestMetadata = Field(default_factory=MultimodalityTestMetadata)
    sampler_adequacy: SamplerAdequacyStatus = Field(default_factory=SamplerAdequacyStatus)
    modes: DetectedModesStatus = Field(default_factory=DetectedModesStatus)
    policy_relevance: PolicyRelevanceStatus = Field(default_factory=PolicyRelevanceStatus)
    downgrade: MultimodalityDowngrade = Field(default_factory=MultimodalityDowngrade)
    evidence_strength: str = "not_assessed"
    limitations: tuple[str, ...] = (
        "Sample-only test cannot exclude unvisited modes.",
        "Mode count is a lower bound.",
    )


class PosteriorModeWeight(BaseModel):
    """Weight disclosure for a detected posterior mode."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    estimate: float
    ci_90: tuple[float, float] | None = None
    method: str = "observed_draw_fraction"


class PosteriorModeSummary(BaseModel):
    """Mode-conditional posterior summary carried by PosteriorResult."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode_id: str
    draw_count: int
    ess_bulk_min: float | None = None
    weight: PosteriorModeWeight
    center: dict[str, float] = Field(default_factory=dict)
    covariance_summary: dict[str, float] = Field(default_factory=dict)
    parameter_summaries: dict[str, dict[str, float]] = Field(default_factory=dict)
    policy_summaries: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


def validate_simulator_diagnostic_artifact(
    value: SimulatorDiagnosticArtifact | Mapping[str, Any] | None,
) -> SimulatorDiagnosticArtifact | None:
    """Validate a mapping-or-model simulator diagnostic artifact."""

    if value is None:
        return None
    if isinstance(value, SimulatorDiagnosticArtifact):
        return value
    if isinstance(value, Mapping):
        return SimulatorDiagnosticArtifact.model_validate(dict(value))
    raise TypeError(
        "simulator diagnostic artifact must be a mapping or SimulatorDiagnosticArtifact"
    )


def canonical_simulator_diagnostic_artifact(
    diagnostic: SimulatorDiagnosticArtifact | Mapping[str, Any],
) -> tuple[str, dict[str, Any], str]:
    """Encode an SBI simulator diagnostic as a canonical hash-addressed artifact."""

    artifact_model = validate_simulator_diagnostic_artifact(diagnostic)
    if artifact_model is None:
        raise ValueError("simulator diagnostic artifact is required")
    artifact = artifact_model.model_dump(
        mode="python",
        by_alias=True,
        exclude_none=True,
        exclude={"artifact_ref"},
    )
    canonical_bytes = to_canonical_bytes(artifact, spec=CanonSpec(forbid_floats=False))
    digest = content_hash(canonical_bytes, prefix=True)
    ref = f"artifact://foundry/sbi/simulator_diagnostic/{digest}"
    return ref, artifact, digest


_EXACT_METHOD_BASES = {
    "gp_regression": "closed_form_gaussian_process_posterior",
}
_ASYMPTOTIC_METHOD_BASES = {
    "bayesian_autoregression": "asymptotic_sampler_runtime_diagnostics",
    "bayesian_bart_regression": "asymptotic_sampler_runtime_diagnostics",
    "bayesian_hierarchical_regression": "asymptotic_sampler_runtime_diagnostics",
    "bayesian_hmc_regression": "asymptotic_sampler_runtime_diagnostics",
    "bayesian_linear_regression": "asymptotic_sampler_runtime_diagnostics",
    "bayesian_nuts_regression": "asymptotic_sampler_runtime_diagnostics",
}
_APPROXIMATE_METHOD_BASES = {
    "affine_normalizing_flow": "flow_approximation_without_runtime_calibration",
    "bayesian_gaussian_mixture": "mixture_plugin_posterior_without_reference_calibration",
    "bbvi": "variational_approximation_without_runtime_calibration",
    "dirichlet_process_mixture": "mixture_plugin_posterior_without_reference_calibration",
    "expectation_propagation_gaussian": "ep_site_approximation_without_near_gaussian_certificate",
    "factor_graph_belief_propagation": "loopy_belief_propagation_without_exact_graph_certificate",
    "mean_field_vi": "variational_approximation_without_runtime_calibration",
    "simulation_based_nle": "amortized_sbi_without_conditional_calibration",
    "simulation_based_npe": "amortized_sbi_without_conditional_calibration",
    "simulation_based_nre": "amortized_sbi_without_conditional_calibration",
    "sparse_gp_regression": "sparse_gp_approximation_without_reference_calibration",
    "svgd_regression": "svgd_particle_approximation_without_stein_calibration",
}


def _normalise_truthfulness_value(value: Any) -> float | int | str | bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        scalar = float(value)
        if np.isfinite(scalar):
            return scalar
        return "nan" if np.isnan(scalar) else ("inf" if scalar > 0 else "-inf")
    return str(value)


def _safe_truthfulness_diagnostics(
    payload: Mapping[str, Any],
) -> dict[str, float | int | str | bool]:
    return {str(key): _normalise_truthfulness_value(value) for key, value in payload.items()}


def _truthfulness_benchmark_regime(metadata: Mapping[str, Any]) -> str | None:
    raw = metadata.get("benchmark_regime")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _truthfulness_coverage_tolerance(metadata: Mapping[str, Any]) -> float | None:
    raw = metadata.get("coverage_tolerance")
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) else None


def extract_truthfulness_hints(*sources: Mapping[str, Any] | None) -> dict[str, Any]:
    """Merge optional truthfulness-hint mappings passed through params/state."""

    merged: dict[str, Any] = {}
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        raw = source.get("truthfulness_hints")
        if isinstance(raw, Mapping):
            merged.update(dict(raw))
    return merged


def split_truthfulness_hints(
    hints: Mapping[str, Any] | None,
) -> tuple[dict[str, float], dict[str, Any]]:
    """Project hint payloads into numeric diagnostics plus metadata."""

    if not isinstance(hints, Mapping):
        return {}, {}
    diagnostics: dict[str, float] = {}
    metadata = dict(hints)
    for key, value in hints.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float, np.integer, np.floating)):
            scalar = float(value)
            if np.isfinite(scalar):
                diagnostics[str(key)] = scalar
    return diagnostics, metadata


def weighted_quantile(
    values: np.ndarray,
    quantiles: float | tuple[float, ...] | list[float] | np.ndarray,
    *,
    sample_weight: np.ndarray | None = None,
) -> np.ndarray:
    """Compute weighted quantiles for 1D arrays."""

    arr = np.asarray(values, dtype=float).reshape(-1)
    probs = np.atleast_1d(np.asarray(quantiles, dtype=float))
    if arr.size == 0:
        raise ValueError("weighted_quantile requires at least one sample")
    if sample_weight is None:
        result = np.quantile(arr, probs)
        return np.asarray(result, dtype=float)
    weights = np.asarray(sample_weight, dtype=float).reshape(-1)
    if weights.shape[0] != arr.shape[0]:
        raise ValueError("sample_weight must align with values")
    if np.any(weights < 0.0) or not np.all(np.isfinite(weights)):
        raise ValueError("sample_weight must be finite and non-negative")
    total = float(np.sum(weights))
    if total <= 0.0:
        raise ValueError("sample_weight must sum to a positive value")
    order = np.argsort(arr)
    sorted_values = arr[order]
    sorted_weights = weights[order]
    cumulative = np.cumsum(sorted_weights) / total
    result = np.interp(np.clip(probs, 0.0, 1.0), cumulative, sorted_values)
    return np.asarray(result, dtype=float)


def relative_interval_shift_max(
    base_intervals: Mapping[str, tuple[float, float]],
    candidate_intervals: Mapping[str, tuple[float, float]],
) -> float:
    """Return the largest relative endpoint shift between aligned intervals."""

    shifts: list[float] = []
    for name, base_interval in base_intervals.items():
        candidate = candidate_intervals.get(name)
        if candidate is None:
            continue
        base_lower, base_upper = map(float, base_interval)
        cand_lower, cand_upper = map(float, candidate)
        width = max(abs(base_upper - base_lower), 1e-12)
        shifts.append(max(abs(cand_lower - base_lower), abs(cand_upper - base_upper)) / width)
    return float(max(shifts)) if shifts else float("inf")


def pareto_tail_shape(
    log_weights: np.ndarray,
    *,
    tail_fraction: float = 0.2,
) -> float:
    """Approximate Pareto tail index from raw importance log-weights."""

    arr = np.asarray(log_weights, dtype=float).reshape(-1)
    arr = arr[np.isfinite(arr)]
    if arr.size < 8:
        return float("inf")
    weights = np.exp(arr - float(np.max(arr)))
    weights = weights[np.isfinite(weights) & (weights > 0.0)]
    if weights.size < 8:
        return float("inf")
    tail_count = max(4, int(np.ceil(float(tail_fraction) * weights.size)))
    tail = np.sort(weights)[-tail_count:]
    threshold = max(float(tail[0]), 1e-12)
    return float(np.mean(np.log(np.maximum(tail, threshold) / threshold)))


def _truthfulness_metric(
    *sources: Mapping[str, Any],
    key: str,
) -> float | None:
    for source in sources:
        raw = source.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if np.isfinite(value):
            return value
    return None


def _truthfulness_flag(
    *sources: Mapping[str, Any],
    key: str,
) -> bool | None:
    for source in sources:
        raw = source.get(key)
        if raw is None:
            continue
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, (int, float, np.integer, np.floating)):
            value = float(raw)
            if np.isfinite(value):
                return value >= 1.0
            continue
        text = str(raw).strip().lower()
        if text in {"true", "pass", "passed", "ok", "yes"}:
            return True
        if text in {"false", "fail", "failed", "no"}:
            return False
    return None


def _simulator_diagnostic_ref(metadata: Mapping[str, Any]) -> str | None:
    raw = metadata.get("simulator_diagnostic_ref")
    if raw is None:
        diagnostic = metadata.get("simulator_diagnostic")
        if isinstance(diagnostic, Mapping):
            raw = diagnostic.get("artifact_ref") or diagnostic.get("ref")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _simulator_diagnostic_payload(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = metadata.get("simulator_diagnostic")
    return raw if isinstance(raw, Mapping) else {}


def _simulator_diagnostic_status(metadata: Mapping[str, Any]) -> str | None:
    for raw in (
        metadata.get("simulator_diagnostic_status"),
        metadata.get("diagnostic_status"),
        _simulator_diagnostic_payload(metadata).get("status"),
        metadata.get("status"),
    ):
        if raw is None:
            continue
        text = str(raw).strip().lower()
        if text:
            return text
    return None


def _simulator_diagnostic_failure_modes(metadata: Mapping[str, Any]) -> tuple[str, ...]:
    candidates = (
        metadata.get("failure_mode"),
        metadata.get("simulator_failure_mode"),
        metadata.get("simulator_diagnostic_failure_mode"),
        _simulator_diagnostic_payload(metadata).get("failure_mode"),
    )
    modes: list[str] = []
    for raw in candidates:
        if raw is None:
            continue
        values = raw if isinstance(raw, (list, tuple, set, frozenset)) else (raw,)
        for value in values:
            text = str(value).strip().lower()
            if text:
                modes.append(text)
    return tuple(dict.fromkeys(modes))


def _sbi_regime_aware_required(metadata: Mapping[str, Any]) -> bool:
    if bool(metadata.get("regime_aware_calibration_required")):
        return True
    diagnostic_contract = metadata.get("diagnostic_contract")
    if isinstance(diagnostic_contract, Mapping) and bool(
        diagnostic_contract.get("support_required")
    ):
        return True
    return bool(metadata.get("simulator_regime_schema"))


def _sbi_support_threshold(metadata: Mapping[str, Any], key: str, default: float) -> float:
    raw = metadata.get(key)
    diagnostic_contract = metadata.get("diagnostic_contract")
    if raw is None and isinstance(diagnostic_contract, Mapping):
        thresholds = diagnostic_contract.get("thresholds")
        if isinstance(thresholds, Mapping):
            raw = thresholds.get(key)
    if raw is None:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return value if np.isfinite(value) else default


def _sbi_status_override(payload: Mapping[str, Any]) -> tuple[str | None, str | None]:
    method_name = str(payload.get("method_name", "")).strip()
    if method_name not in {"simulation_based_npe", "simulation_based_nle", "simulation_based_nre"}:
        return None, None
    metadata = payload.get("metadata", {}) or {}
    if not isinstance(metadata, Mapping):
        return None, None
    modes = set(_simulator_diagnostic_failure_modes(metadata))
    support_failure_modes = {"unreachable_observation", "regime_extrapolation"}
    if modes & support_failure_modes:
        return "degraded", "simulator_support_failure"
    return None, None


def _sample_size_aware_psis_threshold(num_samples: float | None) -> float:
    samples = max(float(num_samples or 0.0), 10.0)
    adaptive = 1.0 - 1.0 / max(np.log10(samples), 1.0)
    return float(np.clip(max(0.7, adaptive), 0.7, 0.95))


def _approximate_shift_tolerance(coverage_tolerance: float | None) -> float:
    if coverage_tolerance is None or not np.isfinite(coverage_tolerance):
        return 0.05
    return float(np.clip(2.0 * coverage_tolerance, 0.02, 0.2))


def _approximate_benchmark_assessment(
    *,
    diagnostics: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> tuple[bool, dict[str, bool], list[str]]:
    benchmark_regime = _truthfulness_benchmark_regime(metadata)
    coverage_tolerance = _truthfulness_coverage_tolerance(metadata)
    explicit = _truthfulness_flag(diagnostics, metadata, key="offline_calibration_passed")
    if explicit is None:
        explicit = _truthfulness_flag(diagnostics, metadata, key="benchmark_passed")
    coverage_error = _truthfulness_metric(diagnostics, metadata, key="offline_coverage_error_max")
    tail_error = _truthfulness_metric(diagnostics, metadata, key="offline_tail_coverage_error_max")
    posterior_sbc_error = _truthfulness_metric(diagnostics, metadata, key="posterior_sbc_error")
    evidence_present = explicit is not None or any(
        metric is not None for metric in (coverage_error, tail_error, posterior_sbc_error)
    )
    if explicit is not None:
        offline_ok = (
            bool(explicit) and benchmark_regime is not None and coverage_tolerance is not None
        )
    else:
        offline_ok = (
            benchmark_regime is not None
            and coverage_tolerance is not None
            and evidence_present
            and (coverage_error is None or coverage_error <= coverage_tolerance)
            and (
                tail_error is None
                or tail_error <= max(coverage_tolerance, 1.5 * coverage_tolerance)
            )
            and (posterior_sbc_error is None or posterior_sbc_error <= coverage_tolerance)
        )
    assumptions = {
        "benchmark_regime_declared": benchmark_regime is not None,
        "coverage_tolerance_declared": coverage_tolerance is not None,
        "offline_benchmark_evidence_present": evidence_present,
        "offline_benchmark_ok": offline_ok,
    }
    downgrade_reasons: list[str] = []
    if benchmark_regime is None:
        downgrade_reasons.append("benchmark_regime_missing")
    if coverage_tolerance is None:
        downgrade_reasons.append("coverage_tolerance_missing")
    if not evidence_present:
        downgrade_reasons.append("offline_benchmark_evidence_missing")
    elif not offline_ok:
        downgrade_reasons.append("offline_benchmark_failed")
    return offline_ok, assumptions, downgrade_reasons


def _source_truthfulness_support(metadata: Mapping[str, Any]) -> tuple[bool, str | None]:
    candidate = metadata.get("source_truthfulness_receipt")
    source_tier = parse_receipt_truthfulness_tier(metadata.get("source_truthfulness_tier"))
    if candidate is not None:
        try:
            receipt = validate_truthfulness_receipt(candidate)
        except (TypeError, ValueError):
            receipt = None
        if receipt is not None:
            source_tier = (
                receipt.effective_truthfulness_tier
                or receipt.runtime_truthfulness_tier
                or receipt.declared_truthfulness_tier
            )
    if source_tier is None:
        return False, None
    if source_tier is ReceiptTruthfulnessTier.UNVERIFIED:
        return False, source_tier.value
    return True, source_tier.value


def _reshape_chain_array(value: Any, *, num_chains: int, num_samples: int) -> np.ndarray:
    arr = np.asarray(value, dtype=float)
    if arr.ndim >= 2 and arr.shape[0] == num_chains and arr.shape[1] == num_samples:
        return arr.reshape(num_chains, num_samples, -1)
    if arr.ndim >= 1 and arr.shape[0] == num_chains * num_samples:
        return arr.reshape(num_chains, num_samples, -1)
    if num_chains == 1 and arr.ndim >= 1 and arr.shape[0] == num_samples:
        return arr.reshape(1, num_samples, -1)
    raise ValueError(
        "posterior samples could not be reshaped into chains with "
        f"num_chains={num_chains} and num_samples={num_samples}"
    )


def _stack_posterior_chains(
    samples: Mapping[str, Any],
    *,
    num_chains: int,
    num_samples: int,
) -> np.ndarray:
    blocks = [
        _reshape_chain_array(samples[name], num_chains=num_chains, num_samples=num_samples)
        for name in sorted(samples)
    ]
    if not blocks:
        raise ValueError("at least one posterior sample array is required for chain diagnostics")
    return np.concatenate(blocks, axis=2)


def _split_chains(chains: np.ndarray) -> np.ndarray:
    if chains.ndim != 3:
        raise ValueError("chains must have shape (n_chains, n_draws, n_parameters)")
    draws = chains.shape[1]
    if draws < 4:
        return chains
    usable = (draws // 2) * 2
    trimmed = chains[:, :usable, :]
    return trimmed.reshape(trimmed.shape[0] * 2, usable // 2, trimmed.shape[2])


def _autocovariance_1d(values: np.ndarray) -> np.ndarray:
    centred = np.asarray(values, dtype=float) - float(np.mean(values))
    draws = centred.shape[0]
    if draws == 0:
        return np.zeros(0, dtype=float)
    return np.asarray(
        [np.dot(centred[: draws - lag], centred[lag:]) / draws for lag in range(draws)],
        dtype=float,
    )


def _rhat_for_dimension(chains_2d: np.ndarray) -> float:
    chains, draws = chains_2d.shape
    if chains < 2 or draws < 2:
        return 1.0
    within = np.var(chains_2d, axis=1, ddof=1)
    w = float(np.mean(within))
    if not np.isfinite(w) or w <= 1e-12:
        return 1.0
    between = float(draws * np.var(np.mean(chains_2d, axis=1), ddof=1))
    var_hat = ((draws - 1.0) / draws) * w + between / draws
    return float(np.sqrt(max(var_hat / w, 1.0)))


def _ess_for_dimension(chains_2d: np.ndarray) -> float:
    chains, draws = chains_2d.shape
    if draws < 4:
        return float(chains * draws)
    within = np.var(chains_2d, axis=1, ddof=1)
    w = float(np.mean(within))
    if not np.isfinite(w) or w <= 1e-12:
        return float(chains * draws)
    between = float(draws * np.var(np.mean(chains_2d, axis=1), ddof=1)) if chains > 1 else 0.0
    var_hat = ((draws - 1.0) / draws) * w + between / max(draws, 1)
    if not np.isfinite(var_hat) or var_hat <= 1e-12:
        return float(chains * draws)
    mean_acov = np.mean(
        np.vstack([_autocovariance_1d(chains_2d[idx]) for idx in range(chains)]),
        axis=0,
    )
    positive_rhos: list[float] = []
    for lag in range(1, max(draws - 1, 1), 2):
        rho_1 = 1.0 - (w - mean_acov[lag]) / var_hat
        rho_2 = 0.0
        if lag + 1 < draws:
            rho_2 = 1.0 - (w - mean_acov[lag + 1]) / var_hat
        if rho_1 + rho_2 < 0.0:
            break
        positive_rhos.extend(
            (
                float(np.clip(rho_1, -0.999, 0.999)),
                float(np.clip(rho_2, -0.999, 0.999)),
            )
        )
    tau_hat = 1.0 + 2.0 * float(np.sum(positive_rhos))
    if not np.isfinite(tau_hat) or tau_hat <= 0.0:
        return float(chains * draws)
    return float(min(chains * draws, (chains * draws) / tau_hat))


def _quantile_stability_relative_max(chains: np.ndarray, *, credible_mass: float) -> float:
    alpha = max(1e-6, 1.0 - float(credible_mass))
    probs = (alpha / 2.0, 1.0 - alpha / 2.0)
    flat = chains.reshape(-1, chains.shape[2])
    relatives: list[float] = []
    for dim in range(chains.shape[2]):
        lower_full, upper_full = np.quantile(flat[:, dim], probs)
        width = max(float(upper_full - lower_full), 1e-12)
        lower_by_chain = np.asarray(
            [np.quantile(chains[idx, :, dim], probs[0]) for idx in range(chains.shape[0])],
            dtype=float,
        )
        upper_by_chain = np.asarray(
            [np.quantile(chains[idx, :, dim], probs[1]) for idx in range(chains.shape[0])],
            dtype=float,
        )
        lower_std = float(np.std(lower_by_chain, ddof=1)) if lower_by_chain.shape[0] > 1 else 0.0
        upper_std = float(np.std(upper_by_chain, ddof=1)) if upper_by_chain.shape[0] > 1 else 0.0
        relatives.append(max(lower_std, upper_std) / width)
    return float(max(relatives)) if relatives else 0.0


def compute_sampler_chain_diagnostics(
    samples: Mapping[str, Any],
    *,
    num_chains: int,
    num_samples: int,
    credible_mass: float,
) -> dict[str, float]:
    """Compute finite-run chain diagnostics from posterior sample arrays."""

    split_chains = _split_chains(
        _stack_posterior_chains(
            samples,
            num_chains=max(1, int(num_chains)),
            num_samples=max(1, int(num_samples)),
        )
    )
    rhat_values = np.asarray(
        [_rhat_for_dimension(split_chains[:, :, dim]) for dim in range(split_chains.shape[2])],
        dtype=float,
    )
    ess_bulk_values = np.asarray(
        [_ess_for_dimension(split_chains[:, :, dim]) for dim in range(split_chains.shape[2])],
        dtype=float,
    )
    alpha = max(1e-6, 1.0 - float(credible_mass))
    flat = split_chains.reshape(-1, split_chains.shape[2])
    ess_tail_values: list[float] = []
    for dim in range(split_chains.shape[2]):
        lower = float(np.quantile(flat[:, dim], alpha / 2.0))
        upper = float(np.quantile(flat[:, dim], 1.0 - alpha / 2.0))
        lower_indicator = (split_chains[:, :, dim] <= lower).astype(float)
        upper_indicator = (split_chains[:, :, dim] >= upper).astype(float)
        ess_tail_values.append(
            min(
                _ess_for_dimension(lower_indicator),
                _ess_for_dimension(upper_indicator),
            )
        )
    total_draws = float(split_chains.shape[0] * split_chains.shape[1])
    return {
        "rhat_max": float(np.max(rhat_values)) if rhat_values.size else 1.0,
        "ess_bulk_min": float(np.min(ess_bulk_values)) if ess_bulk_values.size else total_draws,
        "ess_tail_min": float(np.min(np.asarray(ess_tail_values, dtype=float)))
        if ess_tail_values
        else total_draws,
        "quantile_mcse_relative_max": _quantile_stability_relative_max(
            split_chains,
            credible_mass=credible_mass,
        ),
        "num_split_chains": float(split_chains.shape[0]),
        "draws_per_split_chain": float(split_chains.shape[1]),
    }


def augment_sampler_diagnostics(
    samples: Mapping[str, Any],
    *,
    diagnostics: Mapping[str, Any],
    num_chains: int,
    num_samples: int,
    credible_mass: float,
) -> dict[str, float]:
    """Merge existing sampler diagnostics with finite-run chain diagnostics."""

    merged = {str(key): float(value) for key, value in diagnostics.items()}
    merged.update(
        compute_sampler_chain_diagnostics(
            samples,
            num_chains=num_chains,
            num_samples=num_samples,
            credible_mass=credible_mass,
        )
    )
    return merged


def _approximate_calibrated_requested(
    *,
    diagnostics: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> bool:
    if bool(metadata.get("truthfulness_calibrated")):
        return True
    try:
        return float(diagnostics.get("calibration_passed", 0.0)) >= 1.0
    except (TypeError, ValueError):
        return False


def _build_approximate_evidence(
    *,
    tier_basis: str,
    diagnostics: Mapping[str, Any],
    metadata: Mapping[str, Any],
    assumptions_checked: Mapping[str, bool],
    downgrade_reasons: list[str],
) -> TruthfulnessEvidence:
    tier = (
        TruthfulnessTier.APPROXIMATE_CALIBRATED
        if not downgrade_reasons
        else TruthfulnessTier.APPROXIMATE_UNCALIBRATED
    )
    return TruthfulnessEvidence(
        tier=tier,
        basis=tier_basis,
        assumptions_checked=dict(assumptions_checked),
        diagnostics=_safe_truthfulness_diagnostics(diagnostics),
        downgrade_reasons=downgrade_reasons,
        benchmark_regime=_truthfulness_benchmark_regime(metadata),
        coverage_tolerance=_truthfulness_coverage_tolerance(metadata),
    )


def _infer_variational_evidence(
    *,
    diagnostics: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> TruthfulnessEvidence:
    benchmark_ok, benchmark_assumptions, benchmark_reasons = _approximate_benchmark_assessment(
        diagnostics=diagnostics,
        metadata=metadata,
    )
    coverage_tolerance = _truthfulness_coverage_tolerance(metadata)
    shift_tolerance = _approximate_shift_tolerance(coverage_tolerance)
    num_importance_samples = _truthfulness_metric(
        diagnostics,
        metadata,
        key="importance_sample_size",
    ) or _truthfulness_metric(diagnostics, metadata, key="num_samples")
    psis_threshold = _sample_size_aware_psis_threshold(num_importance_samples)
    joint_psis = _truthfulness_metric(diagnostics, metadata, key="joint_psis_pareto_k")
    posthoc_shift = (
        _truthfulness_metric(diagnostics, metadata, key="posthoc_interval_shift_max")
        or _truthfulness_metric(diagnostics, metadata, key="psis_interval_shift_max")
        or _truthfulness_metric(diagnostics, metadata, key="reference_interval_shift_max")
    )
    converged = _truthfulness_flag(diagnostics, metadata, key="converged")
    assumptions_checked = {
        **benchmark_assumptions,
        "joint_psis_present": joint_psis is not None,
        "joint_psis_ok": joint_psis is not None and joint_psis <= psis_threshold,
        "posthoc_interval_shift_present": posthoc_shift is not None,
        "posthoc_interval_shift_ok": posthoc_shift is not None and posthoc_shift <= shift_tolerance,
        "optimizer_converged": converged is not False,
    }
    downgrade_reasons = list(benchmark_reasons)
    if joint_psis is None:
        downgrade_reasons.append("joint_psis_missing")
    elif joint_psis > psis_threshold:
        downgrade_reasons.append("joint_psis_too_high")
    if posthoc_shift is None:
        downgrade_reasons.append("posthoc_interval_shift_missing")
    elif posthoc_shift > shift_tolerance:
        downgrade_reasons.append("posthoc_interval_shift_too_large")
    if converged is False:
        downgrade_reasons.append("optimizer_not_converged")
    basis = (
        "variational_reference_posterior_calibration"
        if _truthfulness_metric(diagnostics, metadata, key="reference_interval_shift_max")
        is not None
        else "variational_joint_psis_calibration"
    )
    if not benchmark_ok and basis == "variational_reference_posterior_calibration":
        basis = "variational_reference_posterior_without_benchmark_certificate"
    return _build_approximate_evidence(
        tier_basis=basis,
        diagnostics=diagnostics,
        metadata=metadata,
        assumptions_checked=assumptions_checked,
        downgrade_reasons=downgrade_reasons,
    )


def _infer_ep_evidence(
    *,
    diagnostics: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> TruthfulnessEvidence:
    benchmark_ok, benchmark_assumptions, benchmark_reasons = _approximate_benchmark_assessment(
        diagnostics=diagnostics,
        metadata=metadata,
    )
    cavity_precision_min = _truthfulness_metric(diagnostics, metadata, key="cavity_precision_min")
    site_precision_cv = _truthfulness_metric(diagnostics, metadata, key="site_precision_cv")
    site_residual = _truthfulness_metric(diagnostics, metadata, key="site_mean_z_residual_max")
    skewness_proxy = _truthfulness_metric(diagnostics, metadata, key="site_skewness_proxy")
    kurtosis_proxy = _truthfulness_metric(diagnostics, metadata, key="site_kurtosis_proxy")
    assumptions_checked = {
        **benchmark_assumptions,
        "cavity_precision_positive": cavity_precision_min is not None
        and cavity_precision_min > 0.0,
        "site_precision_stable": site_precision_cv is not None and site_precision_cv <= 1.5,
        "site_residual_small": site_residual is not None and site_residual <= 1.0,
        "near_gaussian_proxy_ok": (
            skewness_proxy is not None
            and kurtosis_proxy is not None
            and abs(skewness_proxy) <= 0.5
            and abs(kurtosis_proxy) <= 1.0
        ),
    }
    downgrade_reasons = list(benchmark_reasons)
    if cavity_precision_min is None or cavity_precision_min <= 0.0:
        downgrade_reasons.append("cavity_precision_not_positive")
    if site_precision_cv is None:
        downgrade_reasons.append("site_precision_stability_missing")
    elif site_precision_cv > 1.5:
        downgrade_reasons.append("site_precision_unstable")
    if site_residual is None:
        downgrade_reasons.append("site_residual_missing")
    elif site_residual > 1.0:
        downgrade_reasons.append("site_residual_too_large")
    if skewness_proxy is None or kurtosis_proxy is None:
        downgrade_reasons.append("near_gaussian_proxy_missing")
    elif abs(skewness_proxy) > 0.5 or abs(kurtosis_proxy) > 1.0:
        downgrade_reasons.append("near_gaussian_proxy_failed")
    if not benchmark_ok:
        pass
    return _build_approximate_evidence(
        tier_basis="ep_near_gaussian_runtime_calibration",
        diagnostics=diagnostics,
        metadata=metadata,
        assumptions_checked=assumptions_checked,
        downgrade_reasons=downgrade_reasons,
    )


def _infer_svgd_evidence(
    *,
    diagnostics: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> TruthfulnessEvidence:
    benchmark_ok, benchmark_assumptions, benchmark_reasons = _approximate_benchmark_assessment(
        diagnostics=diagnostics,
        metadata=metadata,
    )
    coverage_tolerance = _truthfulness_coverage_tolerance(metadata)
    shift_tolerance = _approximate_shift_tolerance(coverage_tolerance)
    ksd = _truthfulness_metric(diagnostics, metadata, key="ksd_rbf")
    unique_fraction = _truthfulness_metric(diagnostics, metadata, key="unique_particle_fraction")
    split_shift = _truthfulness_metric(diagnostics, metadata, key="split_interval_shift_max")
    posthoc_shift = _truthfulness_metric(diagnostics, metadata, key="posthoc_interval_shift_max")
    assumptions_checked = {
        **benchmark_assumptions,
        "ksd_present": ksd is not None,
        "ksd_ok": ksd is not None and ksd <= max(0.1, 4.0 * (coverage_tolerance or 0.05)),
        "particle_uniqueness_ok": unique_fraction is not None and unique_fraction >= 0.75,
        "split_interval_stability_ok": split_shift is not None and split_shift <= shift_tolerance,
        "posthoc_interval_shift_ok": posthoc_shift is not None and posthoc_shift <= shift_tolerance,
    }
    downgrade_reasons = list(benchmark_reasons)
    if ksd is None:
        downgrade_reasons.append("ksd_missing")
    elif ksd > max(0.1, 4.0 * (coverage_tolerance or 0.05)):
        downgrade_reasons.append("ksd_too_large")
    if unique_fraction is None:
        downgrade_reasons.append("particle_uniqueness_missing")
    elif unique_fraction < 0.75:
        downgrade_reasons.append("particle_collapse_detected")
    if split_shift is None:
        downgrade_reasons.append("split_interval_stability_missing")
    elif split_shift > shift_tolerance:
        downgrade_reasons.append("split_interval_instability")
    if posthoc_shift is None:
        downgrade_reasons.append("posthoc_interval_shift_missing")
    elif posthoc_shift > shift_tolerance:
        downgrade_reasons.append("posthoc_interval_shift_too_large")
    return _build_approximate_evidence(
        tier_basis="svgd_stein_runtime_calibration",
        diagnostics=diagnostics,
        metadata=metadata,
        assumptions_checked=assumptions_checked,
        downgrade_reasons=downgrade_reasons,
    )


def _infer_flow_evidence(
    *,
    diagnostics: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> TruthfulnessEvidence:
    benchmark_ok, benchmark_assumptions, benchmark_reasons = _approximate_benchmark_assessment(
        diagnostics=diagnostics,
        metadata=metadata,
    )
    source_supported, source_tier = _source_truthfulness_support(metadata)
    coverage_tolerance = _truthfulness_coverage_tolerance(metadata)
    shift_tolerance = _approximate_shift_tolerance(coverage_tolerance)
    mean_shift = _truthfulness_metric(diagnostics, metadata, key="source_mean_shift_max")
    cov_error = _truthfulness_metric(diagnostics, metadata, key="source_covariance_error_fro")
    interval_shift = _truthfulness_metric(diagnostics, metadata, key="source_interval_shift_max")
    condition_number = _truthfulness_metric(diagnostics, metadata, key="jacobian_condition_number")
    support_ok = benchmark_ok or source_supported
    assumptions_checked = {
        **benchmark_assumptions,
        "source_truthfulness_supported": source_supported,
        "support_evidence_ok": support_ok,
        "source_mean_shift_ok": mean_shift is not None and mean_shift <= 0.5,
        "source_covariance_match_ok": cov_error is not None and cov_error <= 0.35,
        "source_interval_shift_ok": interval_shift is not None
        and interval_shift <= shift_tolerance,
        "jacobian_conditioning_ok": condition_number is not None and condition_number <= 1.0e6,
    }
    downgrade_reasons = [] if source_supported else list(benchmark_reasons)
    if not support_ok:
        downgrade_reasons.append("source_or_benchmark_evidence_missing")
    if mean_shift is None:
        downgrade_reasons.append("source_mean_shift_missing")
    elif mean_shift > 0.5:
        downgrade_reasons.append("source_mean_shift_too_large")
    if cov_error is None:
        downgrade_reasons.append("source_covariance_error_missing")
    elif cov_error > 0.35:
        downgrade_reasons.append("source_covariance_error_too_large")
    if interval_shift is None:
        downgrade_reasons.append("source_interval_shift_missing")
    elif interval_shift > shift_tolerance:
        downgrade_reasons.append("source_interval_shift_too_large")
    if condition_number is None:
        downgrade_reasons.append("flow_conditioning_missing")
    elif condition_number > 1.0e6:
        downgrade_reasons.append("flow_conditioning_too_ill_conditioned")
    basis = "flow_source_posterior_preservation_certificate"
    if not source_supported:
        basis = "flow_joint_discrepancy_runtime_calibration"
    if source_tier is not None:
        assumptions_checked["source_truthfulness_tier_known"] = True
    return _build_approximate_evidence(
        tier_basis=basis,
        diagnostics=diagnostics,
        metadata=metadata,
        assumptions_checked=assumptions_checked,
        downgrade_reasons=downgrade_reasons,
    )


def _infer_sbi_evidence(
    *,
    diagnostics: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> TruthfulnessEvidence:
    benchmark_ok, benchmark_assumptions, benchmark_reasons = _approximate_benchmark_assessment(
        diagnostics=diagnostics,
        metadata=metadata,
    )
    neighborhood_count = _truthfulness_metric(
        diagnostics, metadata, key="observed_neighborhood_count"
    )
    neighborhood_radius = _truthfulness_metric(
        diagnostics, metadata, key="observed_neighborhood_radius_quantile"
    )
    posterior_sbc_error = _truthfulness_metric(diagnostics, metadata, key="posterior_sbc_error")
    tarp_coverage_error = _truthfulness_metric(diagnostics, metadata, key="tarp_coverage_error")
    local_c2st = _truthfulness_metric(diagnostics, metadata, key="local_c2st_score")
    ppc_mahalanobis = _truthfulness_metric(diagnostics, metadata, key="ppc_mahalanobis")
    support_quantile = _truthfulness_metric(diagnostics, metadata, key="support_quantile")
    knn_radius_mahalanobis = _truthfulness_metric(
        diagnostics, metadata, key="knn_radius_mahalanobis"
    )
    effective_local_simulations = _truthfulness_metric(
        diagnostics, metadata, key="effective_local_simulations"
    )
    regime_required = _sbi_regime_aware_required(metadata)
    observed_regime = metadata.get("observed_regime")
    observed_regime_present = isinstance(observed_regime, Mapping) and bool(observed_regime)
    simulator_ref = _simulator_diagnostic_ref(metadata)
    diagnostic_status = _simulator_diagnostic_status(metadata)
    failure_modes = set(_simulator_diagnostic_failure_modes(metadata))
    support_quantile_min = _sbi_support_threshold(metadata, "support_quantile_min", 0.01)
    knn_radius_max = _sbi_support_threshold(metadata, "knn_radius_mahalanobis_max", 4.0)
    min_effective_local = _sbi_support_threshold(metadata, "min_effective_local_simulations", 16.0)
    coverage_tolerance = _truthfulness_coverage_tolerance(metadata)
    support_failure = bool(failure_modes & {"unreachable_observation", "regime_extrapolation"})
    local_miscalibration = "local_miscalibration" in failure_modes
    structural_misspecification = "structural_misspecification" in failure_modes
    support_metrics_required = regime_required
    support_metrics_ok = (
        support_quantile is not None
        and support_quantile >= support_quantile_min
        and knn_radius_mahalanobis is not None
        and knn_radius_mahalanobis <= knn_radius_max
        and effective_local_simulations is not None
        and effective_local_simulations >= min_effective_local
    )
    tarp_ok = (
        tarp_coverage_error is not None
        and coverage_tolerance is not None
        and tarp_coverage_error <= coverage_tolerance
    )
    assumptions_checked = {
        **benchmark_assumptions,
        "observed_regime_present": (not regime_required) or observed_regime_present,
        "simulator_diagnostic_ref_present": (not regime_required) or simulator_ref is not None,
        "simulator_support_gate_ok": not support_failure
        and ((not support_metrics_required) or support_metrics_ok),
        "observed_neighborhood_ok": (
            neighborhood_count is not None
            and neighborhood_count >= 16.0
            and neighborhood_radius is not None
            and neighborhood_radius <= 0.25
        ),
        "posterior_sbc_ok": posterior_sbc_error is not None
        and (coverage_tolerance is not None and posterior_sbc_error <= coverage_tolerance),
        "tarp_coverage_ok": (not regime_required) or tarp_ok,
        "local_c2st_ok": local_c2st is not None and local_c2st <= 0.6 and not local_miscalibration,
        "ppc_ok": ppc_mahalanobis is not None
        and ppc_mahalanobis <= 2.5
        and not structural_misspecification,
    }
    downgrade_reasons = list(benchmark_reasons)
    if regime_required and not observed_regime_present:
        downgrade_reasons.append("observed_regime_missing")
    if regime_required and simulator_ref is None:
        downgrade_reasons.append("simulator_diagnostic_ref_missing")
    if support_failure:
        downgrade_reasons.append("simulator_support_failure")
    if diagnostic_status == "fail" and not failure_modes:
        downgrade_reasons.append("simulator_diagnostic_failed")
    if support_metrics_required:
        if support_quantile is None:
            downgrade_reasons.append("support_quantile_missing")
        elif support_quantile < support_quantile_min:
            downgrade_reasons.append("support_quantile_too_low")
        if knn_radius_mahalanobis is None:
            downgrade_reasons.append("knn_radius_mahalanobis_missing")
        elif knn_radius_mahalanobis > knn_radius_max:
            downgrade_reasons.append("knn_radius_mahalanobis_too_large")
        if effective_local_simulations is None:
            downgrade_reasons.append("effective_local_simulations_missing")
        elif effective_local_simulations < min_effective_local:
            downgrade_reasons.append("effective_local_simulations_too_low")
    if neighborhood_count is None or neighborhood_radius is None:
        downgrade_reasons.append("observed_neighborhood_diagnostics_missing")
    elif neighborhood_count < 16.0 or neighborhood_radius > 0.25:
        downgrade_reasons.append("observed_neighborhood_out_of_support")
    if posterior_sbc_error is None:
        downgrade_reasons.append("posterior_sbc_missing")
    elif coverage_tolerance is None or posterior_sbc_error > coverage_tolerance:
        downgrade_reasons.append("posterior_sbc_failed")
    if regime_required:
        if tarp_coverage_error is None:
            downgrade_reasons.append("tarp_coverage_missing")
        elif coverage_tolerance is None or tarp_coverage_error > coverage_tolerance:
            downgrade_reasons.append("tarp_coverage_failed")
    if local_c2st is None:
        downgrade_reasons.append("local_c2st_missing")
    elif local_c2st > 0.6 or local_miscalibration:
        downgrade_reasons.append("local_c2st_failed")
    if ppc_mahalanobis is None:
        downgrade_reasons.append("ppc_diagnostic_missing")
    elif ppc_mahalanobis > 2.5 or structural_misspecification:
        downgrade_reasons.append("ppc_diagnostic_failed")
    return _build_approximate_evidence(
        tier_basis="sbi_conditional_runtime_calibration",
        diagnostics=diagnostics,
        metadata=metadata,
        assumptions_checked=assumptions_checked,
        downgrade_reasons=downgrade_reasons,
    )


def _infer_factor_graph_approximate_evidence(
    *,
    diagnostics: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> TruthfulnessEvidence:
    benchmark_ok, benchmark_assumptions, benchmark_reasons = _approximate_benchmark_assessment(
        diagnostics=diagnostics,
        metadata=metadata,
    )
    final_delta = _truthfulness_metric(diagnostics, metadata, key="final_delta")
    message_tol = _truthfulness_metric(diagnostics, metadata, key="message_residual_tolerance")
    if message_tol is None:
        message_tol = _truthfulness_metric(metadata, key="graph_exact_tolerance")
    crosscheck_error = _truthfulness_metric(
        diagnostics, metadata, key="subgraph_crosscheck_max_error"
    )
    coverage_tolerance = _truthfulness_coverage_tolerance(metadata)
    assumptions_checked = {
        **benchmark_assumptions,
        "message_residual_ok": final_delta is not None
        and message_tol is not None
        and final_delta <= message_tol,
        "subgraph_crosscheck_ok": (
            crosscheck_error is not None
            and coverage_tolerance is not None
            and crosscheck_error <= coverage_tolerance
        ),
    }
    downgrade_reasons = list(benchmark_reasons)
    if final_delta is None or message_tol is None:
        downgrade_reasons.append("message_residual_missing")
    elif final_delta > message_tol:
        downgrade_reasons.append("message_residual_too_large")
    if crosscheck_error is None:
        downgrade_reasons.append("subgraph_crosscheck_missing")
    elif coverage_tolerance is None or crosscheck_error > coverage_tolerance:
        downgrade_reasons.append("subgraph_crosscheck_failed")
    return _build_approximate_evidence(
        tier_basis="factor_graph_crosscheck_runtime_calibration",
        diagnostics=diagnostics,
        metadata=metadata,
        assumptions_checked=assumptions_checked,
        downgrade_reasons=downgrade_reasons,
    )


def _infer_mixture_evidence(
    *,
    diagnostics: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> TruthfulnessEvidence:
    benchmark_ok, benchmark_assumptions, benchmark_reasons = _approximate_benchmark_assessment(
        diagnostics=diagnostics,
        metadata=metadata,
    )
    shift_tolerance = _approximate_shift_tolerance(_truthfulness_coverage_tolerance(metadata))
    weight_shift = _truthfulness_metric(diagnostics, metadata, key="multistart_weight_shift_max")
    mean_shift = _truthfulness_metric(diagnostics, metadata, key="multistart_mean_shift_max")
    collapse_fraction = _truthfulness_metric(
        diagnostics, metadata, key="component_collapse_fraction"
    )
    responsibility_entropy = _truthfulness_metric(diagnostics, metadata, key="entropy")
    assumptions_checked = {
        **benchmark_assumptions,
        "multistart_weight_stable": weight_shift is not None and weight_shift <= shift_tolerance,
        "multistart_mean_stable": mean_shift is not None and mean_shift <= 0.5,
        "component_collapse_ok": collapse_fraction is not None and collapse_fraction <= 0.25,
        "responsibility_entropy_ok": responsibility_entropy is not None
        and responsibility_entropy >= 0.05,
    }
    downgrade_reasons = list(benchmark_reasons)
    if weight_shift is None:
        downgrade_reasons.append("multistart_weight_stability_missing")
    elif weight_shift > shift_tolerance:
        downgrade_reasons.append("multistart_weight_instability")
    if mean_shift is None:
        downgrade_reasons.append("multistart_mean_stability_missing")
    elif mean_shift > 0.5:
        downgrade_reasons.append("multistart_mean_instability")
    if collapse_fraction is None:
        downgrade_reasons.append("component_collapse_metric_missing")
    elif collapse_fraction > 0.25:
        downgrade_reasons.append("component_collapse_detected")
    if responsibility_entropy is None:
        downgrade_reasons.append("responsibility_entropy_missing")
    elif responsibility_entropy < 0.05:
        downgrade_reasons.append("responsibility_entropy_too_low")
    return _build_approximate_evidence(
        tier_basis="mixture_multistart_runtime_calibration",
        diagnostics=diagnostics,
        metadata=metadata,
        assumptions_checked=assumptions_checked,
        downgrade_reasons=downgrade_reasons,
    )


def _infer_asymptotic_evidence(
    *,
    basis: str,
    diagnostics: Mapping[str, Any],
    metadata: Mapping[str, Any],
    diagnostic_gates: Mapping[str, Any],
    diagnostics_summary: Mapping[str, Any],
) -> TruthfulnessEvidence:
    if diagnostic_gates:
        assumptions_checked = {str(key): bool(value) for key, value in diagnostic_gates.items()}
        downgrade_reasons = [
            f"diagnostic_gate_failed:{name}"
            for name, passed in assumptions_checked.items()
            if not passed
        ]
        evidence_payload = diagnostics_summary or diagnostics
        tier = (
            TruthfulnessTier.ASYMPTOTIC
            if not downgrade_reasons
            else TruthfulnessTier.APPROXIMATE_UNCALIBRATED
        )
        return TruthfulnessEvidence(
            tier=tier,
            basis=basis,
            assumptions_checked=assumptions_checked,
            diagnostics=_safe_truthfulness_diagnostics(evidence_payload),
            downgrade_reasons=downgrade_reasons,
            benchmark_regime=_truthfulness_benchmark_regime(metadata),
            coverage_tolerance=_truthfulness_coverage_tolerance(metadata),
        )

    rhat = float(diagnostics.get("rhat_max", np.nan))
    ess_bulk = float(diagnostics.get("ess_bulk_min", np.nan))
    ess_tail = float(diagnostics.get("ess_tail_min", np.nan))
    quantile_mcse = float(diagnostics.get("quantile_mcse_relative_max", np.nan))
    divergences = float(diagnostics.get("divergences", 0.0))
    assumptions_checked = {
        "finite_run_diagnostics_present": all(
            np.isfinite(value) for value in (rhat, ess_bulk, ess_tail, quantile_mcse)
        ),
        "rhat_ok": np.isfinite(rhat) and rhat <= 1.05,
        "ess_bulk_ok": np.isfinite(ess_bulk) and ess_bulk >= 20.0,
        "ess_tail_ok": np.isfinite(ess_tail) and ess_tail >= 10.0,
        "quantile_mcse_ok": np.isfinite(quantile_mcse) and quantile_mcse <= 0.25,
        "divergences_ok": np.isfinite(divergences) and divergences <= 0.0,
    }
    downgrade_reasons = []
    if not assumptions_checked["finite_run_diagnostics_present"]:
        downgrade_reasons.append("finite_run_diagnostics_missing")
    if not assumptions_checked["rhat_ok"]:
        downgrade_reasons.append("rhat_above_threshold")
    if not assumptions_checked["ess_bulk_ok"]:
        downgrade_reasons.append("bulk_ess_too_low")
    if not assumptions_checked["ess_tail_ok"]:
        downgrade_reasons.append("tail_ess_too_low")
    if not assumptions_checked["quantile_mcse_ok"]:
        downgrade_reasons.append("quantile_mcse_too_high")
    if not assumptions_checked["divergences_ok"]:
        downgrade_reasons.append("divergences_detected")
    tier = (
        TruthfulnessTier.ASYMPTOTIC
        if not downgrade_reasons
        else TruthfulnessTier.APPROXIMATE_UNCALIBRATED
    )
    return TruthfulnessEvidence(
        tier=tier,
        basis=basis,
        assumptions_checked=assumptions_checked,
        diagnostics=_safe_truthfulness_diagnostics(diagnostics),
        downgrade_reasons=downgrade_reasons,
        benchmark_regime=_truthfulness_benchmark_regime(metadata),
        coverage_tolerance=_truthfulness_coverage_tolerance(metadata),
    )


def _infer_truthfulness_evidence(payload: Mapping[str, Any]) -> TruthfulnessEvidence:
    method_name = str(payload.get("method_name", "")).strip()
    diagnostics = payload.get("diagnostics", {}) or {}
    metadata = dict(payload.get("metadata", {}) or {})
    simulator_diagnostic_ref = payload.get("simulator_diagnostic_ref")
    if simulator_diagnostic_ref is not None:
        metadata["simulator_diagnostic_ref"] = simulator_diagnostic_ref
    diagnostic_gates = payload.get("diagnostic_gates", {}) or {}
    diagnostics_summary = payload.get("diagnostics_summary", {}) or {}
    sampler_family = str(payload.get("sampler_family", "") or "").strip().lower()

    if method_name == "factor_graph_belief_propagation" and bool(
        metadata.get("graph_exact_regime")
    ):
        assumptions_checked = {
            "graph_exact_regime": True,
            "messages_converged": float(diagnostics.get("final_delta", np.inf))
            <= float(metadata.get("graph_exact_tolerance", np.inf)),
        }
        tier = (
            TruthfulnessTier.EXACT
            if all(assumptions_checked.values())
            else TruthfulnessTier.APPROXIMATE_UNCALIBRATED
        )
        return TruthfulnessEvidence(
            tier=tier,
            basis="tree_sum_product_exact_certificate",
            assumptions_checked=assumptions_checked,
            diagnostics=_safe_truthfulness_diagnostics(diagnostics),
            downgrade_reasons=[]
            if tier is TruthfulnessTier.EXACT
            else ["exact_graph_regime_not_certified"],
            benchmark_regime=_truthfulness_benchmark_regime(metadata),
            coverage_tolerance=_truthfulness_coverage_tolerance(metadata),
        )

    if method_name in _EXACT_METHOD_BASES:
        return TruthfulnessEvidence(
            tier=TruthfulnessTier.EXACT,
            basis=_EXACT_METHOD_BASES[method_name],
            assumptions_checked={"exact_regime": True},
            diagnostics=_safe_truthfulness_diagnostics(diagnostics),
            benchmark_regime=_truthfulness_benchmark_regime(metadata),
            coverage_tolerance=_truthfulness_coverage_tolerance(metadata),
        )

    if sampler_family == "mcmc" or method_name in _ASYMPTOTIC_METHOD_BASES:
        return _infer_asymptotic_evidence(
            basis=_ASYMPTOTIC_METHOD_BASES.get(
                method_name, "asymptotic_sampler_runtime_diagnostics"
            ),
            diagnostics=diagnostics,
            metadata=metadata,
            diagnostic_gates=diagnostic_gates,
            diagnostics_summary=diagnostics_summary,
        )

    if method_name in {"mean_field_vi", "bbvi"}:
        return _infer_variational_evidence(diagnostics=diagnostics, metadata=metadata)
    if method_name == "expectation_propagation_gaussian":
        return _infer_ep_evidence(diagnostics=diagnostics, metadata=metadata)
    if method_name == "svgd_regression":
        return _infer_svgd_evidence(diagnostics=diagnostics, metadata=metadata)
    if method_name == "affine_normalizing_flow":
        return _infer_flow_evidence(diagnostics=diagnostics, metadata=metadata)
    if method_name in {"simulation_based_npe", "simulation_based_nle", "simulation_based_nre"}:
        return _infer_sbi_evidence(diagnostics=diagnostics, metadata=metadata)
    if method_name in {"bayesian_gaussian_mixture", "dirichlet_process_mixture"}:
        return _infer_mixture_evidence(diagnostics=diagnostics, metadata=metadata)
    if method_name == "factor_graph_belief_propagation":
        return _infer_factor_graph_approximate_evidence(diagnostics=diagnostics, metadata=metadata)

    tier = (
        TruthfulnessTier.APPROXIMATE_CALIBRATED
        if _approximate_calibrated_requested(diagnostics=diagnostics, metadata=metadata)
        else TruthfulnessTier.APPROXIMATE_UNCALIBRATED
    )
    return TruthfulnessEvidence(
        tier=tier,
        basis=_APPROXIMATE_METHOD_BASES.get(
            method_name, "approximation_without_runtime_calibration"
        ),
        assumptions_checked={
            "runtime_calibration_passed": tier is TruthfulnessTier.APPROXIMATE_CALIBRATED,
            "benchmark_regime_declared": _truthfulness_benchmark_regime(metadata) is not None,
        },
        diagnostics=_safe_truthfulness_diagnostics(diagnostics),
        downgrade_reasons=[]
        if tier is TruthfulnessTier.APPROXIMATE_CALIBRATED
        else ["runtime_calibration_evidence_missing"],
        benchmark_regime=_truthfulness_benchmark_regime(metadata),
        coverage_tolerance=_truthfulness_coverage_tolerance(metadata),
    )


def _ensure_prior_sensitivity_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    updated = dict(payload)
    if "prior_sensitivity" in updated:
        return updated
    method_name = str(updated.get("method_name", "") or "")
    family = infer_bayesian_policy_model_family(method_name)
    updated["prior_sensitivity"] = not_run_prior_sensitivity_report(
        model_family=family,
        selected_prior_id="not_declared",
        admissible_prior_class_id=f"{family.value}_prior_policy_v1"
        if family.value != "unknown"
        else "not_declared",
    ).model_dump(mode="python")
    return updated


class PosteriorResult(BaseModel):
    """Store posterior draws, intervals, diagnostics, and model metadata."""

    contract_id: ClassVar[str] = "foundry.bayesian.posterior_result.v2"
    output_contract_declaration: ClassVar[OutputContractDeclaration] = (
        value_uncertainty_output_contract(
            contract_id,
            projection_kind=ValueUncertaintyProjectionKind.POSTERIOR,
        )
    )
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    method_name: str
    posterior_means: dict[str, float] = Field(default_factory=dict)
    posterior_stds: dict[str, float] = Field(default_factory=dict)
    credible_intervals: dict[str, tuple[float, float]] = Field(default_factory=dict)
    diagnostics: dict[str, float] = Field(default_factory=dict)
    sampler_family: str | None = None
    sampler_kernel: str | None = None
    draws_ref: str | None = None
    warmup_draws_ref: str | None = None
    simulator_diagnostic_ref: str | None = None
    draw_layout: dict[str, Any] = Field(default_factory=dict)
    diagnostics_per_chain: dict[str, dict[str, float]] = Field(default_factory=dict)
    diagnostics_summary: dict[str, float] = Field(default_factory=dict)
    diagnostic_gates: dict[str, bool] = Field(default_factory=dict)
    reproducibility: dict[str, Any] = Field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    status: str = "ok"
    degradation_reason: str | None = None
    multimodality_status: MultimodalityStatus = Field(default_factory=MultimodalityStatus)
    modes: tuple[PosteriorModeSummary, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)
    prior_sensitivity: PriorSensitivityReport = Field(
        default_factory=not_run_prior_sensitivity_report
    )
    truthfulness_tier: TruthfulnessTier = TruthfulnessTier.APPROXIMATE_UNCALIBRATED
    truthfulness: TruthfulnessEvidence = Field(default_factory=TruthfulnessEvidence)
    truthfulness_receipt: TruthfulnessReceipt | None = None

    @model_validator(mode="before")
    @classmethod
    def _populate_truthfulness(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = _ensure_prior_sensitivity_payload(value)
        status_override, degradation_reason = _sbi_status_override(payload)
        if status_override is not None and "status" not in payload:
            payload["status"] = status_override
        if degradation_reason is not None and "degradation_reason" not in payload:
            payload["degradation_reason"] = degradation_reason
        if "truthfulness" in payload and "truthfulness_tier" not in payload:
            evidence = TruthfulnessEvidence.model_validate(payload["truthfulness"])
            payload["truthfulness"] = evidence
            payload["truthfulness_tier"] = evidence.tier
            return payload
        if "truthfulness_tier" in payload and "truthfulness" not in payload:
            raw_tier = payload["truthfulness_tier"]
            tier = (
                raw_tier
                if isinstance(raw_tier, TruthfulnessTier)
                else TruthfulnessTier(str(raw_tier))
            )
            payload["truthfulness_tier"] = tier
            payload["truthfulness"] = TruthfulnessEvidence(
                tier=tier,
                basis="explicit_truthfulness_tier_assignment",
            )
            return payload
        if "truthfulness" in payload and "truthfulness_tier" in payload:
            raw_tier = payload["truthfulness_tier"]
            payload["truthfulness_tier"] = (
                raw_tier
                if isinstance(raw_tier, TruthfulnessTier)
                else TruthfulnessTier(str(raw_tier))
            )
            payload["truthfulness"] = TruthfulnessEvidence.model_validate(payload["truthfulness"])
            return payload
        evidence = _infer_truthfulness_evidence(payload)
        payload["truthfulness_tier"] = evidence.tier
        payload["truthfulness"] = evidence
        return payload

    @model_validator(mode="after")
    def _validate_truthfulness_consistency(self) -> PosteriorResult:
        if self.truthfulness_tier is not self.truthfulness.tier:
            raise ValueError("truthfulness_tier must match truthfulness.tier")
        return self

    @staticmethod
    def _receipt_tier_from_posterior_tier(tier: TruthfulnessTier) -> ReceiptTruthfulnessTier:
        return {
            TruthfulnessTier.EXACT: ReceiptTruthfulnessTier.EXACT,
            TruthfulnessTier.ASYMPTOTIC: ReceiptTruthfulnessTier.ASYMPTOTIC,
            TruthfulnessTier.APPROXIMATE_CALIBRATED: ReceiptTruthfulnessTier.APPROXIMATE_CALIBRATED,
            TruthfulnessTier.APPROXIMATE_UNCALIBRATED: ReceiptTruthfulnessTier.UNVERIFIED,
        }[tier]

    def to_truthfulness_receipt(self) -> TruthfulnessReceipt | None:
        if self.truthfulness_receipt is not None:
            return self.truthfulness_receipt
        candidate = self.metadata.get("truthfulness_receipt")
        if candidate is not None:
            return validate_truthfulness_receipt(candidate)
        return TruthfulnessReceipt(
            runtime_truthfulness_tier=self._receipt_tier_from_posterior_tier(
                self.truthfulness_tier
            ),
            truthfulness_scope="posterior",
            diagnostics={
                **self.truthfulness.diagnostics,
                "basis": self.truthfulness.basis,
                **(
                    {"simulator_diagnostic_ref": self.simulator_diagnostic_ref}
                    if self.simulator_diagnostic_ref is not None
                    else {}
                ),
            },
            degradation_reasons=tuple(self.truthfulness.downgrade_reasons),
            evidence_ref=self.simulator_diagnostic_ref,
        )

    def to_uncertainty_envelope(
        self, *, param_name: str | None = None
    ) -> UncertaintyEnvelope | None:
        candidate = param_name
        if candidate is None:
            ordered = [
                name
                for name in sorted(self.posterior_means)
                if name not in {"sigma", "obs_noise", "noise_scale"}
            ]
            if not ordered:
                ordered = sorted(self.posterior_means)
            if not ordered:
                return None
            candidate = ordered[0]
        if candidate not in self.posterior_means:
            return None
        interval = self.credible_intervals.get(candidate)
        if interval is None:
            return None
        lower, upper = sorted((float(interval[0]), float(interval[1])))
        point_estimate = float(self.posterior_means[candidate])
        lower = min(lower, point_estimate)
        upper = max(upper, point_estimate)
        return UncertaintyEnvelope(
            point_estimate=point_estimate,
            confidence_interval=(lower, upper),
            confidence_level=float(self.diagnostics.get("credible_mass", 0.9)),
            distribution_family=DistributionFamily.UNKNOWN,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.MONTE_CARLO,
            interval_semantics=IntervalSemantics.CREDIBLE_INTERVAL,
            sample_size=int(self.diagnostics.get("num_samples", 0)),
            metadata={
                "method_name": self.method_name,
                "parameter": candidate,
                "num_chains": self.diagnostics.get("num_chains"),
                "truthfulness_tier": self.truthfulness_tier.value,
                "truthfulness_basis": self.truthfulness.basis,
                "simulator_diagnostic_ref": self.simulator_diagnostic_ref,
            },
        )

    def to_value_uncertainty(
        self,
        *,
        estimand: object,
        projection_binding: NativeValueEstimandBinding,
    ) -> UncertaintyEnvelope | None:
        """Project only the exact parameter named by the requested value estimand."""

        estimand_id = getattr(estimand, "estimand_id", None)
        if not isinstance(estimand_id, str) or not estimand_id:
            return None
        if (
            projection_binding.native_contract_id != self.contract_id
            or not projection_binding.matches(estimand)
        ):
            return None
        envelope = self.to_uncertainty_envelope(param_name=estimand_id)
        if envelope is None:
            return None
        return envelope.model_copy(
            update={
                "metadata": {
                    **envelope.metadata,
                    "value_estimand_binding_content_hash": (
                        projection_binding.content_hash
                    ),
                    "value_estimand_binding_native_contract_id": (
                        projection_binding.native_contract_id
                    ),
                    "value_estimand_binding_producer_method_fqn": (
                        projection_binding.producer_method_fqn
                    ),
                }
            }
        )

    def to_consensus_target(self, query: Any) -> Any:
        """Expose this posterior on the canonical cross-method consensus surface."""

        from polisyos.foundry.methods.components.consensus import target_from_posterior_result

        return target_from_posterior_result(self, query)


def credible_interval(samples: np.ndarray, *, credible_mass: float) -> tuple[float, float]:
    """Credible interval helper."""
    arr = np.asarray(samples, dtype=float)
    try:
        import arviz as az

        interval = np.asarray(az.hdi(arr, hdi_prob=credible_mass), dtype=float)
        if interval.shape == (2,):
            return float(interval[0]), float(interval[1])
    except Exception:
        pass
    alpha = max(1e-6, 1.0 - float(credible_mass))
    lower, upper = np.quantile(arr, [alpha / 2.0, 1.0 - alpha / 2.0])
    return float(lower), float(upper)


def summarize_posterior_samples(
    samples: Mapping[str, Any],
    *,
    credible_mass: float,
) -> tuple[dict[str, float], dict[str, float], dict[str, tuple[float, float]]]:
    """Summarize posterior samples helper."""
    means: dict[str, float] = {}
    stds: dict[str, float] = {}
    intervals: dict[str, tuple[float, float]] = {}

    for name, value in samples.items():
        arr = np.asarray(value, dtype=float)
        if arr.ndim == 0:
            arr = arr.reshape(1)
        flat = arr.reshape(arr.shape[0], -1)
        labels = [name] if flat.shape[1] == 1 else [f"{name}_{idx}" for idx in range(flat.shape[1])]
        for idx, label in enumerate(labels):
            column = flat[:, idx]
            means[label] = float(np.mean(column))
            stds[label] = float(np.std(column, ddof=1)) if column.shape[0] > 1 else 0.0
            intervals[label] = credible_interval(column, credible_mass=credible_mass)
    return means, stds, intervals


def flatten_chain_draws(samples: Mapping[str, Any]) -> dict[str, np.ndarray]:
    """Flatten chain-major samples into draw-major arrays for summary statistics."""
    flattened: dict[str, np.ndarray] = {}
    for name, value in samples.items():
        arr = np.asarray(value, dtype=float)
        if arr.ndim < 2:
            raise ValueError(f"{name} must be chain-major with shape (chains, draws, ...)")
        flattened[name] = arr.reshape(arr.shape[0] * arr.shape[1], *arr.shape[2:])
    return flattened


def canonical_draws_artifact(
    samples: Mapping[str, Any],
    *,
    method_name: str,
    sampler_kernel: str,
    stage: str,
) -> tuple[str, dict[str, Any], str, dict[str, Any]]:
    """Encode chain-major draws into a canonical, hash-addressed artifact payload."""
    layout = {
        "axis_order": ["chain", "draw", "parameter"],
        "array_order": "C",
        "dtype": "<f8",
        "canonicalization_version": "foundry.bayesian.draws.v1",
    }
    parameters: dict[str, Any] = {}
    for name, value in sorted(samples.items()):
        arr = np.ascontiguousarray(np.asarray(value, dtype=np.dtype("<f8")))
        if arr.ndim < 2:
            raise ValueError(f"{name} must be chain-major with shape (chains, draws, ...)")
        parameters[str(name)] = {
            "shape": [int(dim) for dim in arr.shape],
            "dtype": arr.dtype.str,
            "data_base64": base64.b64encode(arr.tobytes(order="C")).decode("ascii"),
        }

    artifact = {
        "schema": "foundry.bayesian.draws.v1",
        "method_name": method_name,
        "sampler_kernel": sampler_kernel,
        "stage": stage,
        "draw_layout": layout,
        "parameters": parameters,
    }
    canonical_bytes = to_canonical_bytes(artifact, spec=CanonSpec(forbid_floats=False))
    digest = content_hash(canonical_bytes, prefix=True)
    ref = f"artifact://foundry/bayesian/{stage}/{digest}"
    return ref, artifact, digest, layout


def metropolis_sample(
    *,
    log_density: Any,
    initial_state: np.ndarray,
    proposal_scale: float | np.ndarray,
    rng: np.random.Generator,
    num_warmup: int,
    num_samples: int,
    num_chains: int,
) -> tuple[np.ndarray, float]:
    """Metropolis sample helper."""
    initial = np.asarray(initial_state, dtype=float)
    scale = np.broadcast_to(np.asarray(proposal_scale, dtype=float), initial.shape)
    draws: list[np.ndarray] = []
    accepted = 0
    attempted = 0
    for _ in range(max(1, int(num_chains))):
        current = initial + rng.normal(scale=np.maximum(scale * 0.25, 1e-6), size=initial.shape)
        current_lp = float(log_density(current))
        chain_draws: list[np.ndarray] = []
        for step in range(max(0, int(num_warmup)) + max(1, int(num_samples))):
            proposal = current + rng.normal(scale=np.maximum(scale, 1e-6), size=current.shape)
            proposal_lp = float(log_density(proposal))
            if np.log(max(rng.uniform(), 1e-12)) < (proposal_lp - current_lp):
                current = proposal
                current_lp = proposal_lp
                accepted += 1
            attempted += 1
            if step >= max(0, int(num_warmup)):
                chain_draws.append(current.copy())
        draws.append(np.asarray(chain_draws, dtype=float))
    return np.concatenate(draws, axis=0), accepted / max(attempted, 1)


__all__ = [
    "DetectedModesStatus",
    "ModeWeightReliability",
    "MultimodalityDowngrade",
    "MultimodalityScope",
    "MultimodalityState",
    "MultimodalityStatus",
    "MultimodalityTestMetadata",
    "PolicyRelevanceClassification",
    "PolicyRelevanceStatus",
    "PosteriorModeSummary",
    "PosteriorModeWeight",
    "PosteriorReadiness",
    "PosteriorResult",
    "PriorSensitivityReport",
    "SamplerAdequacyStatus",
    "SimulatorDiagnosticArtifact",
    "TruthfulnessEvidence",
    "TruthfulnessTier",
    "augment_sampler_diagnostics",
    "canonical_draws_artifact",
    "canonical_simulator_diagnostic_artifact",
    "compute_sampler_chain_diagnostics",
    "credible_interval",
    "flatten_chain_draws",
    "metropolis_sample",
    "summarize_posterior_samples",
    "validate_simulator_diagnostic_artifact",
]
