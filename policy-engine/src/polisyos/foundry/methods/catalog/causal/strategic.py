"""Solve strategic-response causal contracts and report equilibrium-level diagnostics."""

from __future__ import annotations

import itertools
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics.abstraction import (
    AbstractionCertificate,
    AbstractionPreservationType,
    abstraction_allowed_intervention_family,
    abstraction_error_bound_spec,
    abstraction_estimand_error_bounds,
    abstraction_preserves_query,
    abstraction_recommendation_margin_required,
)
from polisyos.ir.analytics.strategic import (
    EquilibriumSelectionSummary,
    EquilibriumSetSummary,
    FiniteStrategicPayoffTable,
    MeanFieldEquilibriumCertificate,
    MeanFieldEquilibriumSolutionSummary,
    MeanFieldMacroSimulationConfig,
    MeanFieldMassConservationReport,
    MeanFieldPositivityStatus,
    MeanFieldProvenanceSummary,
    MeanFieldSelectionRule,
    MeanFieldSolveInput,
    MeanFieldSolverResidualReport,
    MeanFieldUniquenessStatus,
    PerformativeInstabilityReason,
    PerformativeLoopAnalysisScope,
    PerformativeLoopCertificate,
    PerformativeLoopProofFamily,
    PerformativeLoopRecommendedAction,
    PerformativeLoopStabilityStatus,
    PerformativeLoopWitnessStrength,
    PerformativeShiftSummary,
    PostAdaptationPolicyValueSummary,
    StrategicClosureSummary,
    StrategicComponentBoundsSummary,
    StrategicDecompositionCertificate,
    StrategicDecompositionComponent,
    StrategicDecompositionFailureCard,
    StrategicDecompositionSemantics,
    StrategicDecompositionStatus,
    StrategicEquilibriumConcept,
    StrategicEquilibriumDescriptor,
    StrategicFallbackMode,
    StrategicGameClass,
    StrategicResponseBundle,
    StrategicSCM,
    StrategicSolutionConcept,
    compile_intervention_spec_to_mean_field_perturbation,
    persist_equilibrium_selection_summary,
    persist_equilibrium_set_summary,
    persist_mean_field_equilibrium_certificate,
    persist_mean_field_macro_simulation_config,
    persist_mean_field_mass_conservation_report,
    persist_mean_field_solver_residual_report,
    persist_performative_shift_summary,
    persist_post_adaptation_policy_value_summary,
    persist_strategic_closure_summary,
    persist_strategic_component_bounds_summary,
    persist_strategic_decomposition_certificate,
    persist_strategic_decomposition_failure_card,
    persist_strategic_response_bundle,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    MeanFieldEquilibriumCertificateRef,
    StrategicResponseBundleRef,
)

MAX_STRATEGIC_ACTIONS_PER_AGENT = 8
MAX_STRATEGIC_PROFILE_ENUMERATIONS = 256
STRATEGIC_ABSTRACTION_TRANSFER_SCOPES = frozenset({"equilibrium", "regret", "policy_value"})
_STRATEGIC_TRANSFER_SCOPE_QUERIES: dict[str, tuple[str, ...]] = {
    "policy_value": ("policy_value", "policy_value:"),
    "regret": ("regret", "regret:"),
}
_DETERMINISTIC_SELECTION_DEPENDENCE = frozenset({"deterministic", "deterministic_selection"})


@dataclass(frozen=True)
class StrategicSolveResult:
    """Result of solving a strategic-response contract.

    Namespace:
        causal.strategic
    Version:
        1.0.0
    """

    fallback_mode: StrategicFallbackMode
    equilibrium_profiles: tuple[dict[str, str], ...]
    selected_equilibrium: dict[str, str] | None
    equilibrium_selection_dependence: str
    multiplicity_note: str | None
    blocked_reason: str | None
    performative_shift: float | None
    post_adaptation_policy_value: float | None
    bounds: tuple[float, float] | None
    closure_summary: dict[str, Any]
    baseline_policy_value: float | None = None
    equilibrium_mean_payoffs: tuple[float, ...] = ()
    warnings: tuple[str, ...] = ()
    performative_loop_certificate: PerformativeLoopCertificate | None = None
    mfg_equilibrium_certificate: MeanFieldEquilibriumCertificate | None = None
    mfg_macro_simulation_config: MeanFieldMacroSimulationConfig | None = None
    mfg_solver_residual_report: MeanFieldSolverResidualReport | None = None
    mfg_mass_conservation_report: MeanFieldMassConservationReport | None = None


class PerformativeLoopSpec(BaseModel):
    """Configurable performative-loop analysis request for strategic recommendations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_scope: PerformativeLoopAnalysisScope = PerformativeLoopAnalysisScope.ITERATED_LOOP
    proof_family: PerformativeLoopProofFamily
    adaptive_model: str | None = None
    update_rule: str | None = None
    simulation_horizon: int | None = Field(default=None, ge=1)
    delta_target: float | None = Field(default=None, gt=0.0)
    initial_distance_upper: float | None = Field(default=None, ge=0.0)
    beta: float | None = None
    gamma: float | None = None
    epsilon: float | None = None
    step_size: float | None = None
    l_theta: float | None = None
    l_s: float | None = None
    l_psi: float | None = None
    local_spectral_radius_estimate: float | None = None
    detected_cycle_period: int | None = Field(default=None, ge=2)
    divergence_detected: bool = False
    transient_gain_upper: float | None = None
    mixed_fallback_available: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_spec(self) -> PerformativeLoopSpec:
        for field_name in (
            "delta_target",
            "initial_distance_upper",
            "beta",
            "gamma",
            "epsilon",
            "step_size",
            "l_theta",
            "l_s",
            "l_psi",
            "local_spectral_radius_estimate",
            "transient_gain_upper",
        ):
            value = getattr(self, field_name)
            if value is None:
                continue
            if not math.isfinite(float(value)):
                raise ValueError(f"{field_name} must be finite")
            if float(value) < 0.0:
                raise ValueError(f"{field_name} must be >= 0")
        if self.proof_family is PerformativeLoopProofFamily.RRM_PARAMETRIC:
            for field_name in ("beta", "gamma", "epsilon"):
                if getattr(self, field_name) is None:
                    raise ValueError(f"{field_name} is required for rrm_parametric analysis")
            if float(self.gamma or 0.0) <= 0.0:
                raise ValueError("gamma must be > 0 for rrm_parametric analysis")
        elif self.proof_family is PerformativeLoopProofFamily.RGD_PARAMETRIC:
            for field_name in ("beta", "gamma", "epsilon", "step_size"):
                if getattr(self, field_name) is None:
                    raise ValueError(f"{field_name} is required for rgd_parametric analysis")
            if float(self.gamma or 0.0) <= 0.0:
                raise ValueError("gamma must be > 0 for rgd_parametric analysis")
            if float(self.step_size or 0.0) <= 0.0:
                raise ValueError("step_size must be > 0 for rgd_parametric analysis")
        elif self.proof_family is PerformativeLoopProofFamily.STATEFUL_LIPSCHITZ:
            has_global_bound = all(
                getattr(self, field_name) is not None for field_name in ("l_theta", "l_s", "l_psi")
            )
            has_local_or_simulation_witness = (
                self.local_spectral_radius_estimate is not None
                or self.detected_cycle_period is not None
                or self.divergence_detected
            )
            if not has_global_bound and not has_local_or_simulation_witness:
                raise ValueError(
                    "stateful_lipschitz analysis requires global Lipschitz constants "
                    "or a local/simulation witness"
                )
        return self


def _coerce_performative_loop_spec(payload: Any) -> PerformativeLoopSpec | None:
    if payload is None:
        return None
    if isinstance(payload, PerformativeLoopSpec):
        return payload
    return PerformativeLoopSpec.model_validate(payload)


def _resolve_performative_loop_spec(
    strategic_scm: StrategicSCM,
    payload: Any,
) -> PerformativeLoopSpec | None:
    if payload is not None:
        return _coerce_performative_loop_spec(payload)
    metadata = strategic_scm.metadata if isinstance(strategic_scm.metadata, Mapping) else {}
    return _coerce_performative_loop_spec(metadata.get("performative_loop_spec"))


def _iterations_to_delta_bound(
    *,
    contraction: float,
    initial_distance_upper: float | None,
    delta_target: float | None,
) -> int | None:
    if initial_distance_upper is None or delta_target is None or contraction >= 1.0:
        return None
    if initial_distance_upper <= delta_target:
        return 0
    if contraction <= 0.0:
        return 1
    return int(math.ceil(math.log(delta_target / initial_distance_upper) / math.log(contraction)))


def _default_loop_action(
    status: PerformativeLoopStabilityStatus,
) -> PerformativeLoopRecommendedAction:
    if status is PerformativeLoopStabilityStatus.CERTIFIED_CONVERGENT:
        return PerformativeLoopRecommendedAction.ALLOW_AUTO_ITERATION
    if status is PerformativeLoopStabilityStatus.LOCALLY_CONVERGENT:
        return PerformativeLoopRecommendedAction.ALLOW_WITH_HUMAN_REVIEW
    if status is PerformativeLoopStabilityStatus.CERTIFIED_UNSTABLE:
        return PerformativeLoopRecommendedAction.BLOCK_AUTO_ITERATION
    if status is PerformativeLoopStabilityStatus.MIXED_STABLE_ONLY:
        return PerformativeLoopRecommendedAction.SWITCH_TO_MIXED_NO_REGRET
    return PerformativeLoopRecommendedAction.SINGLE_SHOT_ONLY


def _augment_with_local_witness(
    *,
    spec: PerformativeLoopSpec,
    certificate: PerformativeLoopCertificate,
    contraction_upper_bound: float | None,
    metadata: dict[str, Any],
) -> PerformativeLoopCertificate:
    local_rho = spec.local_spectral_radius_estimate
    if local_rho is not None and local_rho > 1.0:
        return PerformativeLoopCertificate(
            analysis_scope=spec.analysis_scope,
            proof_family=spec.proof_family,
            stability_status=PerformativeLoopStabilityStatus.CERTIFIED_UNSTABLE,
            reason_code=PerformativeInstabilityReason.LOCAL_SPECTRAL_RADIUS_GT_ONE,
            contraction_upper_bound=contraction_upper_bound,
            local_spectral_radius_estimate=local_rho,
            witness_strength=PerformativeLoopWitnessStrength.LOCAL_LINEARIZATION,
            simulation_horizon=spec.simulation_horizon,
            detected_cycle_period=spec.detected_cycle_period,
            transient_gain_upper=spec.transient_gain_upper,
            hardness_flag=True,
            recommended_action=PerformativeLoopRecommendedAction.BLOCK_AUTO_ITERATION,
            human_summary=(
                "Closed-loop Jacobian exceeds unit spectral radius; deterministic "
                "auto-iteration should be blocked."
            ),
            metadata=metadata,
        )
    if spec.detected_cycle_period is not None:
        return PerformativeLoopCertificate(
            analysis_scope=spec.analysis_scope,
            proof_family=spec.proof_family,
            stability_status=PerformativeLoopStabilityStatus.CERTIFIED_UNSTABLE,
            reason_code=PerformativeInstabilityReason.CYCLE_DETECTED,
            contraction_upper_bound=contraction_upper_bound,
            local_spectral_radius_estimate=local_rho,
            witness_strength=PerformativeLoopWitnessStrength.SIMULATION,
            simulation_horizon=spec.simulation_horizon,
            detected_cycle_period=spec.detected_cycle_period,
            transient_gain_upper=spec.transient_gain_upper,
            hardness_flag=True,
            recommended_action=PerformativeLoopRecommendedAction.BLOCK_AUTO_ITERATION,
            human_summary=(
                "Dry-run detected a persistent policy loop cycle; automatic retraining "
                "must not proceed without intervention."
            ),
            metadata=metadata,
        )
    if spec.divergence_detected:
        return PerformativeLoopCertificate(
            analysis_scope=spec.analysis_scope,
            proof_family=spec.proof_family,
            stability_status=PerformativeLoopStabilityStatus.CERTIFIED_UNSTABLE,
            reason_code=PerformativeInstabilityReason.DIVERGENCE_DETECTED,
            contraction_upper_bound=contraction_upper_bound,
            local_spectral_radius_estimate=local_rho,
            witness_strength=PerformativeLoopWitnessStrength.SIMULATION,
            simulation_horizon=spec.simulation_horizon,
            detected_cycle_period=spec.detected_cycle_period,
            transient_gain_upper=spec.transient_gain_upper,
            hardness_flag=True,
            recommended_action=PerformativeLoopRecommendedAction.BLOCK_AUTO_ITERATION,
            human_summary=(
                "Dry-run perturbations grow across iterations; deterministic "
                "auto-iteration is unsafe."
            ),
            metadata=metadata,
        )
    if (
        local_rho is not None
        and local_rho < 1.0
        and certificate.stability_status is PerformativeLoopStabilityStatus.UNCERTIFIED
    ):
        return PerformativeLoopCertificate(
            analysis_scope=spec.analysis_scope,
            proof_family=spec.proof_family,
            stability_status=PerformativeLoopStabilityStatus.LOCALLY_CONVERGENT,
            reason_code=certificate.reason_code,
            contraction_upper_bound=contraction_upper_bound,
            local_spectral_radius_estimate=local_rho,
            witness_strength=PerformativeLoopWitnessStrength.LOCAL_LINEARIZATION,
            simulation_horizon=spec.simulation_horizon,
            detected_cycle_period=spec.detected_cycle_period,
            transient_gain_upper=spec.transient_gain_upper,
            convergence_rate_upper=certificate.convergence_rate_upper,
            iterations_to_delta_bound=certificate.iterations_to_delta_bound,
            hardness_flag=certificate.hardness_flag,
            recommended_action=PerformativeLoopRecommendedAction.ALLOW_WITH_HUMAN_REVIEW,
            human_summary=(
                "Global convergence is not certified, but the local linearization "
                "is stable near the candidate fixed point."
            ),
            metadata=metadata,
        )
    return certificate


def analyze_performative_loop(
    spec_payload: Any,
) -> PerformativeLoopCertificate:
    """Analyze convergence or instability of an iterated performative policy loop."""

    spec = _coerce_performative_loop_spec(spec_payload)
    if spec is None:
        raise ValueError("performative loop analysis requires a non-empty spec")

    metadata = dict(spec.metadata)
    if spec.adaptive_model is not None:
        metadata.setdefault("adaptive_model", str(spec.adaptive_model))
    if spec.update_rule is not None:
        metadata.setdefault("update_rule", str(spec.update_rule))

    contraction_upper_bound: float | None = None
    convergence_rate_upper: float | None = None
    iterations_to_delta: int | None = None

    if spec.proof_family is PerformativeLoopProofFamily.RRM_PARAMETRIC:
        contraction_upper_bound = (
            float(spec.epsilon or 0.0) * float(spec.beta or 0.0) / float(spec.gamma or 1.0)
        )
        metadata.setdefault("beta", float(spec.beta or 0.0))
        metadata.setdefault("gamma", float(spec.gamma or 0.0))
        metadata.setdefault("epsilon", float(spec.epsilon or 0.0))
    elif spec.proof_family is PerformativeLoopProofFamily.RGD_PARAMETRIC:
        base_gradient_contraction = max(
            abs(1.0 - float(spec.step_size or 0.0) * float(spec.gamma or 0.0)),
            abs(1.0 - float(spec.step_size or 0.0) * float(spec.beta or 0.0)),
        )
        contraction_upper_bound = base_gradient_contraction + float(spec.step_size or 0.0) * float(
            spec.beta or 0.0
        ) * float(spec.epsilon or 0.0)
        metadata.setdefault("beta", float(spec.beta or 0.0))
        metadata.setdefault("gamma", float(spec.gamma or 0.0))
        metadata.setdefault("epsilon", float(spec.epsilon or 0.0))
        metadata.setdefault("step_size", float(spec.step_size or 0.0))
        metadata.setdefault("base_gradient_contraction", base_gradient_contraction)
    elif spec.proof_family is PerformativeLoopProofFamily.STATEFUL_LIPSCHITZ:
        if all(getattr(spec, field_name) is not None for field_name in ("l_theta", "l_s", "l_psi")):
            contraction_upper_bound = float(spec.l_s or 0.0) + float(spec.l_theta or 0.0) * float(
                spec.l_psi or 0.0
            )
            metadata.setdefault("L_theta", float(spec.l_theta or 0.0))
            metadata.setdefault("L_s", float(spec.l_s or 0.0))
            metadata.setdefault("L_Psi", float(spec.l_psi or 0.0))
    elif spec.proof_family is PerformativeLoopProofFamily.MIXED_NO_REGRET_FALLBACK:
        return PerformativeLoopCertificate(
            analysis_scope=spec.analysis_scope,
            proof_family=spec.proof_family,
            stability_status=PerformativeLoopStabilityStatus.MIXED_STABLE_ONLY,
            witness_strength=PerformativeLoopWitnessStrength.MIXED_FALLBACK,
            simulation_horizon=spec.simulation_horizon,
            detected_cycle_period=spec.detected_cycle_period,
            transient_gain_upper=spec.transient_gain_upper,
            recommended_action=PerformativeLoopRecommendedAction.SWITCH_TO_MIXED_NO_REGRET,
            human_summary=(
                "Deterministic loop stability is unavailable; only mixed-policy no-regret "
                "stability is supported."
            ),
            metadata=metadata,
        )
    else:
        return PerformativeLoopCertificate(
            analysis_scope=spec.analysis_scope,
            proof_family=spec.proof_family,
            stability_status=PerformativeLoopStabilityStatus.UNCERTIFIED,
            reason_code=PerformativeInstabilityReason.INSUFFICIENT_MODELING_ASSUMPTIONS,
            simulation_horizon=spec.simulation_horizon,
            local_spectral_radius_estimate=spec.local_spectral_radius_estimate,
            detected_cycle_period=spec.detected_cycle_period,
            transient_gain_upper=spec.transient_gain_upper,
            recommended_action=PerformativeLoopRecommendedAction.SINGLE_SHOT_ONLY,
            human_summary=(
                "Performative-loop analysis for this proof family is research-gated; "
                "deterministic auto-iteration remains uncertified."
            ),
            metadata=metadata,
        )

    if contraction_upper_bound is not None and contraction_upper_bound < 1.0:
        convergence_rate_upper = contraction_upper_bound
        iterations_to_delta = _iterations_to_delta_bound(
            contraction=contraction_upper_bound,
            initial_distance_upper=spec.initial_distance_upper,
            delta_target=spec.delta_target,
        )
        certificate = PerformativeLoopCertificate(
            analysis_scope=spec.analysis_scope,
            proof_family=spec.proof_family,
            stability_status=PerformativeLoopStabilityStatus.CERTIFIED_CONVERGENT,
            contraction_upper_bound=contraction_upper_bound,
            local_spectral_radius_estimate=spec.local_spectral_radius_estimate,
            witness_strength=PerformativeLoopWitnessStrength.THEOREM,
            simulation_horizon=spec.simulation_horizon,
            detected_cycle_period=spec.detected_cycle_period,
            transient_gain_upper=spec.transient_gain_upper,
            convergence_rate_upper=convergence_rate_upper,
            iterations_to_delta_bound=iterations_to_delta,
            recommended_action=PerformativeLoopRecommendedAction.ALLOW_AUTO_ITERATION,
            human_summary=(
                "Closed-loop contraction is certified below one; repeated deployment "
                "converges under the declared adaptive model."
            ),
            metadata=metadata,
        )
    elif contraction_upper_bound is not None:
        certificate = PerformativeLoopCertificate(
            analysis_scope=spec.analysis_scope,
            proof_family=spec.proof_family,
            stability_status=PerformativeLoopStabilityStatus.UNCERTIFIED,
            reason_code=PerformativeInstabilityReason.GLOBAL_CONTRACTION_FAILED,
            contraction_upper_bound=contraction_upper_bound,
            local_spectral_radius_estimate=spec.local_spectral_radius_estimate,
            witness_strength=PerformativeLoopWitnessStrength.THEOREM,
            simulation_horizon=spec.simulation_horizon,
            detected_cycle_period=spec.detected_cycle_period,
            transient_gain_upper=spec.transient_gain_upper,
            hardness_flag=contraction_upper_bound > 1.0,
            recommended_action=_default_loop_action(PerformativeLoopStabilityStatus.UNCERTIFIED),
            human_summary=(
                "Global contraction could not be certified for the declared adaptive "
                "response; repeated deployment should remain single-shot only."
            ),
            metadata=metadata,
        )
    else:
        certificate = PerformativeLoopCertificate(
            analysis_scope=spec.analysis_scope,
            proof_family=spec.proof_family,
            stability_status=PerformativeLoopStabilityStatus.UNCERTIFIED,
            reason_code=PerformativeInstabilityReason.INSUFFICIENT_MODELING_ASSUMPTIONS,
            local_spectral_radius_estimate=spec.local_spectral_radius_estimate,
            witness_strength=PerformativeLoopWitnessStrength.THEOREM,
            simulation_horizon=spec.simulation_horizon,
            detected_cycle_period=spec.detected_cycle_period,
            transient_gain_upper=spec.transient_gain_upper,
            recommended_action=_default_loop_action(PerformativeLoopStabilityStatus.UNCERTIFIED),
            human_summary=(
                "Loop analysis lacks a complete global contraction witness; "
                "deterministic auto-iteration remains uncertified."
            ),
            metadata=metadata,
        )
    return _augment_with_local_witness(
        spec=spec,
        certificate=certificate,
        contraction_upper_bound=contraction_upper_bound,
        metadata=metadata,
    )


def _with_performative_loop_analysis(
    result: StrategicSolveResult,
    *,
    strategic_scm: StrategicSCM,
    performative_loop_spec: Any,
) -> StrategicSolveResult:
    spec = _resolve_performative_loop_spec(strategic_scm, performative_loop_spec)
    if spec is None:
        return result
    return StrategicSolveResult(
        fallback_mode=result.fallback_mode,
        equilibrium_profiles=result.equilibrium_profiles,
        selected_equilibrium=result.selected_equilibrium,
        equilibrium_selection_dependence=result.equilibrium_selection_dependence,
        multiplicity_note=result.multiplicity_note,
        blocked_reason=result.blocked_reason,
        performative_shift=result.performative_shift,
        post_adaptation_policy_value=result.post_adaptation_policy_value,
        bounds=result.bounds,
        baseline_policy_value=result.baseline_policy_value,
        equilibrium_mean_payoffs=result.equilibrium_mean_payoffs,
        closure_summary=dict(result.closure_summary),
        warnings=result.warnings,
        performative_loop_certificate=analyze_performative_loop(spec),
        mfg_equilibrium_certificate=result.mfg_equilibrium_certificate,
        mfg_macro_simulation_config=result.mfg_macro_simulation_config,
        mfg_solver_residual_report=result.mfg_solver_residual_report,
        mfg_mass_conservation_report=result.mfg_mass_conservation_report,
    )


def _coerce_strategic_contract(payload: Any) -> StrategicSCM:
    return payload if isinstance(payload, StrategicSCM) else StrategicSCM.model_validate(payload)


def _coerce_abstraction_certificate(payload: Any) -> AbstractionCertificate | None:
    if payload is None:
        return None
    return (
        payload
        if isinstance(payload, AbstractionCertificate)
        else AbstractionCertificate.model_validate(payload)
    )


def _coerce_payoff_tables(payload: Any) -> dict[str, FiniteStrategicPayoffTable]:
    if not isinstance(payload, Mapping) or not payload:
        raise ValueError("strategic_payoff_tables must be a non-empty mapping")
    tables: dict[str, FiniteStrategicPayoffTable] = {}
    for agent, table_payload in payload.items():
        table = (
            table_payload
            if isinstance(table_payload, FiniteStrategicPayoffTable)
            else FiniteStrategicPayoffTable.model_validate(table_payload)
        )
        tables[str(agent)] = table
    return tables


def _coerce_mean_field_inputs(payload: Any) -> MeanFieldSolveInput | None:
    if payload is None:
        return None
    return (
        payload
        if isinstance(payload, MeanFieldSolveInput)
        else MeanFieldSolveInput.model_validate(payload)
    )


def _requires_mean_field_runtime(strategic_scm: StrategicSCM) -> bool:
    descriptor = strategic_scm.equilibrium_descriptor
    if descriptor is None:
        return False
    return (
        descriptor.game_class is StrategicGameClass.ANONYMOUS_AGGREGATIVE
        and descriptor.solution_concept is StrategicSolutionConcept.EPSILON_NASH
    )


@dataclass(frozen=True)
class _MeanFieldDiagnostics:
    solver_residual_report: MeanFieldSolverResidualReport
    mass_conservation_report: MeanFieldMassConservationReport


def _softmax_rows(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    exp_values = np.exp(shifted)
    return exp_values / np.maximum(np.sum(exp_values, axis=1, keepdims=True), 1.0e-12)


def _mean_field_solution_diagnostics(
    inputs: MeanFieldSolveInput,
    solver_payload: Mapping[str, Any],
) -> _MeanFieldDiagnostics | None:
    reward = np.asarray(inputs.reward_matrix, dtype=float)
    transition = np.asarray(inputs.transition_tensor, dtype=float)
    n_states, n_actions = reward.shape
    congestion = (
        np.zeros(n_states, dtype=float)
        if not inputs.congestion_costs
        else np.asarray(inputs.congestion_costs, dtype=float)
    )
    stationary_distribution = np.asarray(
        solver_payload.get("stationary_distribution"),
        dtype=float,
    )
    policy_matrix = np.asarray(solver_payload.get("policy_matrix"), dtype=float)
    value_function = np.asarray(solver_payload.get("value_function"), dtype=float)
    arrays = (
        reward,
        transition,
        congestion,
        stationary_distribution,
        policy_matrix,
        value_function,
    )
    if not all(np.all(np.isfinite(array)) for array in arrays):
        return None
    if (
        transition.shape != (n_actions, n_states, n_states)
        or congestion.shape != (n_states,)
        or stationary_distribution.shape != (n_states,)
        or policy_matrix.shape != (n_states, n_actions)
        or value_function.shape != (n_states,)
    ):
        return None

    row_sums = np.sum(transition, axis=2, keepdims=True)
    normalized_transition = transition / np.maximum(row_sums, 1.0e-12)
    q_values = np.empty_like(reward)
    congestion_penalty = congestion * stationary_distribution
    for action_index in range(n_actions):
        q_values[:, action_index] = (
            reward[:, action_index]
            - congestion_penalty
            + float(inputs.discount) * (normalized_transition[action_index] @ value_function)
        )

    implied_policy = _softmax_rows(q_values / max(float(inputs.temperature), 1.0e-6))
    value_fixed_point = np.sum(policy_matrix * q_values, axis=1)
    policy_transition = np.einsum("sa,ask->sk", policy_matrix, normalized_transition)
    next_distribution = stationary_distribution @ policy_transition

    value_residual = float(np.max(np.abs(value_fixed_point - value_function)))
    policy_residual = float(np.max(np.abs(implied_policy - policy_matrix)))
    stationary_residual = float(np.max(np.abs(next_distribution - stationary_distribution)))
    mass_sum = float(np.sum(stationary_distribution))
    mass_sum_error = float(abs(mass_sum - 1.0))
    min_mass = float(np.min(stationary_distribution))
    residual_threshold = max(1.0e-5, 1000.0 * float(inputs.tol))
    mass_threshold = max(1.0e-6, 100.0 * float(inputs.tol))
    metadata = {
        "diagnostic_family": "discrete_anonymous_aggregative_mfg_v1",
        "states": int(n_states),
        "actions": int(n_actions),
        "discount": float(inputs.discount),
        "temperature": float(inputs.temperature),
    }
    solver_report = MeanFieldSolverResidualReport(
        converged=bool(solver_payload.get("converged", False)),
        iterations=int(solver_payload.get("iterations", 0) or 0),
        tolerance=float(inputs.tol),
        value_residual_max_abs=value_residual,
        policy_fixed_point_residual_max_abs=policy_residual,
        residual_threshold=residual_threshold,
        within_tolerance=(
            bool(solver_payload.get("converged", False))
            and value_residual <= residual_threshold
            and policy_residual <= residual_threshold
        ),
        metadata=metadata,
    )
    mass_report = MeanFieldMassConservationReport(
        mass_sum=mass_sum,
        mass_sum_error=mass_sum_error,
        min_mass=min_mass,
        stationary_distribution_residual_max_abs=stationary_residual,
        residual_threshold=residual_threshold,
        mass_threshold=mass_threshold,
        within_tolerance=(
            mass_sum_error <= mass_threshold
            and min_mass >= -mass_threshold
            and stationary_residual <= residual_threshold
        ),
        metadata=metadata,
    )
    return _MeanFieldDiagnostics(
        solver_residual_report=solver_report,
        mass_conservation_report=mass_report,
    )


def _solve_mean_field_equilibrium(
    strategic_scm: StrategicSCM,
    *,
    baseline_policy_value: float | None,
    mean_field_inputs: MeanFieldSolveInput | Mapping[str, Any] | None,
) -> StrategicSolveResult:
    inputs = _coerce_mean_field_inputs(mean_field_inputs)
    descriptor = strategic_scm.equilibrium_descriptor
    if inputs is None:
        return StrategicSolveResult(
            fallback_mode=StrategicFallbackMode.BLOCKED,
            equilibrium_profiles=(),
            selected_equilibrium=None,
            equilibrium_selection_dependence="mean_field_payload_missing",
            multiplicity_note=None,
            blocked_reason="missing_mean_field_game_payload",
            performative_shift=None,
            post_adaptation_policy_value=None,
            bounds=None,
            closure_summary={
                "mode": StrategicFallbackMode.BLOCKED.value,
                "runtime_branch": "mean_field_equilibrium",
                "reason": "missing_mean_field_game_payload",
                "game_class": None if descriptor is None else descriptor.game_class.value,
                "solution_concept": (
                    None if descriptor is None else descriptor.solution_concept.value
                ),
            },
        )

    if inputs.identification.positivity_status is MeanFieldPositivityStatus.FAILED:
        return StrategicSolveResult(
            fallback_mode=StrategicFallbackMode.BLOCKED,
            equilibrium_profiles=(),
            selected_equilibrium=None,
            equilibrium_selection_dependence="mean_field_positivity_failed",
            multiplicity_note=None,
            blocked_reason="mean_field_positivity_failed",
            performative_shift=None,
            post_adaptation_policy_value=None,
            bounds=None,
            closure_summary={
                "mode": StrategicFallbackMode.BLOCKED.value,
                "runtime_branch": "mean_field_equilibrium",
                "reason": "mean_field_positivity_failed",
                "positivity_status": inputs.identification.positivity_status.value,
            },
        )

    uniqueness_status = inputs.well_posedness.uniqueness_status
    selection_rule = inputs.identification.selection_rule
    if (
        uniqueness_status is not MeanFieldUniquenessStatus.UNIQUE
        and selection_rule is MeanFieldSelectionRule.NONE
    ):
        return StrategicSolveResult(
            fallback_mode=StrategicFallbackMode.BLOCKED,
            equilibrium_profiles=(),
            selected_equilibrium=None,
            equilibrium_selection_dependence="mean_field_selection_rule_required",
            multiplicity_note=None,
            blocked_reason="mean_field_selection_rule_required",
            performative_shift=None,
            post_adaptation_policy_value=None,
            bounds=None,
            closure_summary={
                "mode": StrategicFallbackMode.BLOCKED.value,
                "runtime_branch": "mean_field_equilibrium",
                "reason": "mean_field_selection_rule_required",
                "uniqueness_status": uniqueness_status.value,
            },
        )

    perturbation = compile_intervention_spec_to_mean_field_perturbation(
        inputs.intervention_spec,
        source_intervention_ref=inputs.intervention_spec_ref,
        baseline_policy_ref=inputs.baseline_policy_ref,
        metadata={
            **dict(inputs.metadata),
            "strategic_game_class": (None if descriptor is None else descriptor.game_class.value),
            "strategic_solution_concept": (
                None if descriptor is None else descriptor.solution_concept.value
            ),
        },
    )

    from polisyos.foundry.methods.catalog.policy.frontier import (
        MeanFieldEquilibriumEstimator,
    )

    solver_payload = MeanFieldEquilibriumEstimator.pure_step(
        {
            "reward_matrix": [list(row) for row in inputs.reward_matrix],
            "transition_tensor": [
                [list(row) for row in matrix] for matrix in inputs.transition_tensor
            ],
            "congestion_costs": list(inputs.congestion_costs),
        },
        {
            "discount": inputs.discount,
            "temperature": inputs.temperature,
            "max_iter": inputs.max_iter,
            "tol": inputs.tol,
        },
    )["result"]

    if not bool(solver_payload.get("converged", False)):
        return StrategicSolveResult(
            fallback_mode=StrategicFallbackMode.BLOCKED,
            equilibrium_profiles=(),
            selected_equilibrium=None,
            equilibrium_selection_dependence="mean_field_solver_nonconvergent",
            multiplicity_note=None,
            blocked_reason="mean_field_solver_nonconvergent",
            performative_shift=None,
            post_adaptation_policy_value=None,
            bounds=None,
            closure_summary={
                "mode": StrategicFallbackMode.BLOCKED.value,
                "runtime_branch": "mean_field_equilibrium",
                "reason": "mean_field_solver_nonconvergent",
                "iterations": int(solver_payload.get("iterations", 0) or 0),
            },
        )

    diagnostics = _mean_field_solution_diagnostics(inputs, solver_payload)
    if (
        diagnostics is None
        or not diagnostics.solver_residual_report.within_tolerance
        or not diagnostics.mass_conservation_report.within_tolerance
    ):
        diagnostic_summary: dict[str, Any] = {}
        if diagnostics is not None:
            diagnostic_summary = {
                "value_residual_max_abs": diagnostics.solver_residual_report.value_residual_max_abs,
                "policy_fixed_point_residual_max_abs": (
                    diagnostics.solver_residual_report.policy_fixed_point_residual_max_abs
                ),
                "stationary_distribution_residual_max_abs": (
                    diagnostics.mass_conservation_report.stationary_distribution_residual_max_abs
                ),
                "mass_sum_error": diagnostics.mass_conservation_report.mass_sum_error,
                "min_mass": diagnostics.mass_conservation_report.min_mass,
            }
        return StrategicSolveResult(
            fallback_mode=StrategicFallbackMode.BLOCKED,
            equilibrium_profiles=(),
            selected_equilibrium=None,
            equilibrium_selection_dependence="mean_field_solution_diagnostics_failed",
            multiplicity_note=None,
            blocked_reason="mean_field_solution_diagnostics_failed",
            performative_shift=None,
            post_adaptation_policy_value=None,
            bounds=None,
            closure_summary={
                "mode": StrategicFallbackMode.BLOCKED.value,
                "runtime_branch": "mean_field_equilibrium",
                "reason": "mean_field_solution_diagnostics_failed",
                "diagnostics": diagnostic_summary,
            },
        )

    mean_value = float(solver_payload["mean_value"])
    post_value = _post_adaptation_value(
        baseline_policy_value=baseline_policy_value,
        performative_shift=mean_value,
    )
    selection_dependence = (
        "deterministic"
        if uniqueness_status is MeanFieldUniquenessStatus.UNIQUE
        else "deterministic_selection"
    )
    multiplicity_note = (
        None
        if uniqueness_status is MeanFieldUniquenessStatus.UNIQUE
        else f"mean_field_selection_rule:{selection_rule.value}"
    )

    macro_simulation_config = None
    if inputs.macro_simulation_config is not None:
        macro_simulation_config = inputs.macro_simulation_config.model_copy(
            update={
                "metadata": {
                    **dict(inputs.macro_simulation_config.metadata),
                    "solver_converged": True,
                    "solver_iterations": int(solver_payload["iterations"]),
                    "mean_value": mean_value,
                    "stationary_distribution": list(solver_payload["stationary_distribution"]),
                    "policy_matrix": list(solver_payload["policy_matrix"]),
                }
            }
        )

    certificate = MeanFieldEquilibriumCertificate(
        intervention_kind=perturbation.intervention_kind,
        baseline_policy_ref=inputs.baseline_policy_ref,
        intervention_spec_ref=inputs.intervention_spec_ref,
        mean_field_model_class=inputs.mean_field_model_class,
        well_posedness=inputs.well_posedness,
        identification=inputs.identification,
        equilibrium_solution=MeanFieldEquilibriumSolutionSummary(),
        stability=inputs.stability,
        provenance=inputs.provenance,
        metadata={
            **dict(inputs.metadata),
            "runtime_branch": "policy.agent_sim.mean_field_equilibrium@1.0.0",
            "solver_converged": True,
            "solver_iterations": int(solver_payload["iterations"]),
            "mean_value": mean_value,
            "stationary_distribution": list(solver_payload["stationary_distribution"]),
            "policy_matrix": list(solver_payload["policy_matrix"]),
            "value_function": list(solver_payload["value_function"]),
            "solver_residual": diagnostics.solver_residual_report.model_dump(mode="json"),
            "mass_conservation": diagnostics.mass_conservation_report.model_dump(mode="json"),
            "selection_rule": selection_rule.value,
            "uniqueness_status": uniqueness_status.value,
            "perturbation": perturbation.model_dump(mode="json"),
        },
    )
    return StrategicSolveResult(
        fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
        equilibrium_profiles=(),
        selected_equilibrium=None,
        equilibrium_selection_dependence=selection_dependence,
        multiplicity_note=multiplicity_note,
        blocked_reason=None,
        performative_shift=mean_value,
        post_adaptation_policy_value=post_value,
        bounds=None,
        closure_summary={
            "mode": StrategicFallbackMode.EXACT_EQUILIBRIUM.value,
            "runtime_branch": "mean_field_equilibrium",
            "game_class": None if descriptor is None else descriptor.game_class.value,
            "solution_concept": None if descriptor is None else descriptor.solution_concept.value,
            "mean_field_model_class": inputs.mean_field_model_class.value,
            "intervention_kind": perturbation.intervention_kind.value,
            "selection_rule": selection_rule.value,
            "uniqueness_status": uniqueness_status.value,
            "positivity_status": inputs.identification.positivity_status.value,
            "solver_iterations": int(solver_payload["iterations"]),
            "mean_value": mean_value,
            "converged": True,
            "value_residual_max_abs": diagnostics.solver_residual_report.value_residual_max_abs,
            "policy_fixed_point_residual_max_abs": (
                diagnostics.solver_residual_report.policy_fixed_point_residual_max_abs
            ),
            "stationary_distribution_residual_max_abs": (
                diagnostics.mass_conservation_report.stationary_distribution_residual_max_abs
            ),
            "mass_sum_error": diagnostics.mass_conservation_report.mass_sum_error,
        },
        baseline_policy_value=baseline_policy_value,
        equilibrium_mean_payoffs=(mean_value,),
        mfg_equilibrium_certificate=certificate,
        mfg_macro_simulation_config=macro_simulation_config,
        mfg_solver_residual_report=diagnostics.solver_residual_report,
        mfg_mass_conservation_report=diagnostics.mass_conservation_report,
    )


def _action_spaces(
    contract: StrategicSCM,
    tables: Mapping[str, FiniteStrategicPayoffTable],
) -> dict[str, tuple[str, ...]]:
    action_spaces: dict[str, tuple[str, ...]] | None = None
    for agent in contract.strategic_agents:
        table = tables.get(agent)
        if table is None:
            raise ValueError(f"Missing payoff table for strategic agent {agent!r}")
        if tuple(table.strategic_agents) != tuple(contract.strategic_agents):
            raise ValueError(
                "Payoff tables must use the same strategic_agents ordering as StrategicSCM"
            )
        current = {name: tuple(actions) for name, actions in table.action_spaces.items()}
        if action_spaces is None:
            action_spaces = current
        elif action_spaces != current:
            raise ValueError("All payoff tables must share the same action_spaces")
    if action_spaces is None:
        raise ValueError("At least one payoff table is required")
    for agent, actions in action_spaces.items():
        if len(actions) > MAX_STRATEGIC_ACTIONS_PER_AGENT:
            raise ValueError(
                f"action_spaces.{agent} exceeds per-agent limit ({MAX_STRATEGIC_ACTIONS_PER_AGENT})"
            )
    return action_spaces


def _enumerate_profiles(
    contract: StrategicSCM,
    action_spaces: Mapping[str, tuple[str, ...]],
) -> tuple[dict[str, str], ...]:
    profiles = []
    for action_tuple in itertools.product(
        *(action_spaces[agent] for agent in contract.strategic_agents)
    ):
        profiles.append(dict(zip(contract.strategic_agents, action_tuple, strict=True)))
    return tuple(profiles)


def _profile_key(contract: StrategicSCM, profile: Mapping[str, str]) -> str:
    return "|".join(f"{agent}={profile[agent]}" for agent in contract.strategic_agents)


def _agent_payoff(
    tables: Mapping[str, FiniteStrategicPayoffTable],
    contract: StrategicSCM,
    profile: Mapping[str, str],
    agent: str,
) -> float:
    return float(tables[agent].payoffs[_profile_key(contract, profile)])


def _mean_profile_payoff(
    tables: Mapping[str, FiniteStrategicPayoffTable],
    contract: StrategicSCM,
    profile: Mapping[str, str],
) -> float:
    payoffs = [
        _agent_payoff(tables, contract, profile, agent) for agent in contract.strategic_agents
    ]
    return float(sum(payoffs) / len(payoffs))


def _profile_sort_key(contract: StrategicSCM, profile: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(profile[agent] for agent in contract.strategic_agents)


def _check_budget(
    contract: StrategicSCM,
    *,
    profile_count: int,
) -> tuple[bool, str | None]:
    if profile_count > MAX_STRATEGIC_PROFILE_ENUMERATIONS:
        return False, "strategic_profile_enumeration_limit_exceeded"
    budget = contract.compute_budget
    sim_budget = int(math.floor(float(budget.max_sim_runs)))
    if sim_budget <= 0:
        return False, "strategic_compute_budget_exhausted"
    if profile_count > sim_budget:
        return False, "strategic_compute_budget_exceeded"
    return True, None


def _strategic_abstraction_transfer_scope(
    abstraction_certificate: AbstractionCertificate,
) -> str | None:
    if abstraction_certificate.preservation_type is AbstractionPreservationType.EXACT:
        return "equilibrium"
    if abstraction_certificate.preservation_type is AbstractionPreservationType.POLICY_VALUE_ONLY:
        return "policy_value"
    raw_scope = abstraction_certificate.metadata.get("strategic_transfer_scope")
    if raw_scope is None:
        return None
    scope = str(raw_scope).strip().lower()
    if scope not in STRATEGIC_ABSTRACTION_TRANSFER_SCOPES:
        return None
    return scope


def _certificate_supports_transfer_scope(
    abstraction_certificate: AbstractionCertificate,
    *,
    transfer_scope: str,
) -> bool:
    if transfer_scope == "equilibrium":
        return abstraction_certificate.preservation_type is AbstractionPreservationType.EXACT
    required_queries = _STRATEGIC_TRANSFER_SCOPE_QUERIES.get(transfer_scope)
    if required_queries is None:
        return False
    return any(
        abstraction_preserves_query(
            abstraction_certificate,
            required_query,
            allow_prefix_match=True,
        )
        for required_query in required_queries
    )


def _solve_stackelberg(
    contract: StrategicSCM,
    tables: Mapping[str, FiniteStrategicPayoffTable],
    action_spaces: Mapping[str, tuple[str, ...]],
) -> tuple[tuple[dict[str, str], ...], str, str | None]:
    if len(contract.strategic_agents) != 2:
        raise ValueError("stackelberg_exact_supports_two_agents_only")
    leader, follower = contract.strategic_agents
    follower_table = tables[follower]
    leader_profiles: list[dict[str, str]] = []
    leader_values: list[float] = []
    multiplicity_note: str | None = None

    for leader_action in action_spaces[leader]:
        candidate_profiles = [
            {leader: leader_action, follower: follower_action}
            for follower_action in action_spaces[follower]
        ]
        follower_payoffs = [
            _agent_payoff(tables, contract, profile, follower) for profile in candidate_profiles
        ]
        max_follower_payoff = max(follower_payoffs)
        follower_best_profiles = [
            profile
            for profile, payoff in zip(candidate_profiles, follower_payoffs, strict=True)
            if math.isclose(payoff, max_follower_payoff, rel_tol=0.0, abs_tol=1e-12)
        ]
        if len(follower_best_profiles) > 1:
            multiplicity_note = "multiple_follower_best_responses"
        best_leader_profile = max(
            follower_best_profiles,
            key=lambda profile: _agent_payoff(tables, contract, profile, leader),
        )
        leader_profiles.append(best_leader_profile)
        leader_values.append(_agent_payoff(tables, contract, best_leader_profile, leader))

    max_leader_value = max(leader_values)
    equilibria = tuple(
        profile
        for profile, leader_value in zip(leader_profiles, leader_values, strict=True)
        if math.isclose(leader_value, max_leader_value, rel_tol=0.0, abs_tol=1e-12)
    )
    selection_dependence = (
        "follower_best_response_tie_breaking"
        if multiplicity_note is not None or len(equilibria) > 1
        else "deterministic"
    )
    if len(equilibria) > 1:
        multiplicity_note = "multiple_stackelberg_equilibria"
    return equilibria, selection_dependence, multiplicity_note


def _solve_best_response_fixed_point(
    contract: StrategicSCM,
    tables: Mapping[str, FiniteStrategicPayoffTable],
    profiles: tuple[dict[str, str], ...],
) -> tuple[tuple[dict[str, str], ...], str, str | None]:
    equilibria: list[dict[str, str]] = []
    for profile in profiles:
        profile_is_fixed_point = True
        for agent in contract.strategic_agents:
            restricted_profiles = [
                candidate
                for candidate in profiles
                if all(
                    candidate[other_agent] == profile[other_agent]
                    for other_agent in contract.strategic_agents
                    if other_agent != agent
                )
            ]
            agent_payoffs = [
                _agent_payoff(tables, contract, candidate, agent)
                for candidate in restricted_profiles
            ]
            max_payoff = max(agent_payoffs)
            current_payoff = _agent_payoff(tables, contract, profile, agent)
            if not math.isclose(current_payoff, max_payoff, rel_tol=0.0, abs_tol=1e-12):
                profile_is_fixed_point = False
                break
        if profile_is_fixed_point:
            equilibria.append(profile)
    if not equilibria:
        raise ValueError("best_response_fixed_point_not_found")
    multiplicity_note = "multiple_best_response_fixed_points" if len(equilibria) > 1 else None
    selection_dependence = "best_response_tie_breaking" if multiplicity_note else "deterministic"
    return tuple(equilibria), selection_dependence, multiplicity_note


def _post_adaptation_value(
    *,
    baseline_policy_value: float | None,
    performative_shift: float,
) -> float:
    if baseline_policy_value is None:
        return float(performative_shift)
    return float(baseline_policy_value) + float(performative_shift)


def _strategic_bounds(
    contract: StrategicSCM,
    tables: Mapping[str, FiniteStrategicPayoffTable],
    profiles: tuple[dict[str, str], ...],
    *,
    baseline_policy_value: float | None,
) -> StrategicSolveResult:
    profile_values = [_mean_profile_payoff(tables, contract, profile) for profile in profiles]
    lower_shift = min(profile_values)
    upper_shift = max(profile_values)
    lower = _post_adaptation_value(
        baseline_policy_value=baseline_policy_value,
        performative_shift=lower_shift,
    )
    upper = _post_adaptation_value(
        baseline_policy_value=baseline_policy_value,
        performative_shift=upper_shift,
    )
    closure_summary = {
        "mode": StrategicFallbackMode.STRATEGIC_BOUNDS.value,
        "profile_count": len(profiles),
        "bounds": [lower, upper],
    }
    return StrategicSolveResult(
        fallback_mode=StrategicFallbackMode.STRATEGIC_BOUNDS,
        equilibrium_profiles=(),
        selected_equilibrium=None,
        equilibrium_selection_dependence="worst_case_and_best_case_envelope",
        multiplicity_note="strategic_bounds_used_instead_of_selected_equilibrium",
        blocked_reason=None,
        performative_shift=None,
        post_adaptation_policy_value=None,
        bounds=(lower, upper),
        closure_summary=closure_summary,
        baseline_policy_value=baseline_policy_value,
    )


def solve_strategic_response(
    strategic_scm: StrategicSCM,
    payoff_tables: Mapping[str, FiniteStrategicPayoffTable],
    *,
    baseline_policy_value: float | None = None,
    abstraction_certificate: AbstractionCertificate | None = None,
    macro_payoff_tables: Mapping[str, FiniteStrategicPayoffTable] | None = None,
    performative_loop_spec: PerformativeLoopSpec | Mapping[str, Any] | None = None,
    mean_field_inputs: MeanFieldSolveInput | Mapping[str, Any] | None = None,
) -> StrategicSolveResult:
    """Solve a small strategic response game or disclose the fallback used."""

    descriptor = strategic_scm.equilibrium_descriptor
    if _requires_mean_field_runtime(strategic_scm):
        return _with_performative_loop_analysis(
            _solve_mean_field_equilibrium(
                strategic_scm,
                baseline_policy_value=baseline_policy_value,
                mean_field_inputs=mean_field_inputs,
            ),
            strategic_scm=strategic_scm,
            performative_loop_spec=performative_loop_spec,
        )

    action_spaces = _action_spaces(strategic_scm, payoff_tables)
    profiles = _enumerate_profiles(strategic_scm, action_spaces)

    exact_supported = strategic_scm.runtime_eligible
    exact_budget_ok, exact_budget_reason = _check_budget(
        strategic_scm,
        profile_count=len(profiles),
    )
    macro_block_reason: str | None = None

    exact_block_reason: str | None = None
    if exact_supported and exact_budget_ok:
        if strategic_scm.equilibrium_concept is StrategicEquilibriumConcept.STACKELBERG:
            equilibria, selection_dependence, multiplicity_note = _solve_stackelberg(
                strategic_scm,
                payoff_tables,
                action_spaces,
            )
        elif (
            strategic_scm.equilibrium_concept
            is StrategicEquilibriumConcept.BEST_RESPONSE_FIXED_POINT
        ):
            equilibria, selection_dependence, multiplicity_note = _solve_best_response_fixed_point(
                strategic_scm,
                payoff_tables,
                profiles,
            )
        else:
            exact_block_reason = "research_gated_equilibrium_concept"
            equilibria = ()
            selection_dependence = "blocked_research_scope"
            multiplicity_note = None

        if exact_block_reason is None:
            sorted_equilibria = tuple(
                sorted(equilibria, key=lambda profile: _profile_sort_key(strategic_scm, profile))
            )
            selected = sorted_equilibria[0]
            equilibrium_mean_payoffs = tuple(
                _mean_profile_payoff(payoff_tables, strategic_scm, profile)
                for profile in sorted_equilibria
            )
            shift = equilibrium_mean_payoffs[0]
            post_value = _post_adaptation_value(
                baseline_policy_value=baseline_policy_value,
                performative_shift=shift,
            )
            closure_summary = {
                "mode": StrategicFallbackMode.EXACT_EQUILIBRIUM.value,
                "equilibrium_concept": (
                    None
                    if strategic_scm.equilibrium_concept is None
                    else strategic_scm.equilibrium_concept.value
                ),
                "game_class": None if descriptor is None else descriptor.game_class.value,
                "solution_concept": None
                if descriptor is None
                else descriptor.solution_concept.value,
                "profile_count": len(profiles),
                "equilibrium_count": len(sorted_equilibria),
                "selected_equilibrium": dict(selected),
                "selected_mean_payoff": shift,
                "equilibrium_profiles": [dict(profile) for profile in sorted_equilibria],
            }
            return _with_performative_loop_analysis(
                StrategicSolveResult(
                    fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
                    equilibrium_profiles=sorted_equilibria,
                    selected_equilibrium=dict(selected),
                    equilibrium_selection_dependence=selection_dependence,
                    multiplicity_note=multiplicity_note,
                    blocked_reason=None,
                    performative_shift=shift,
                    post_adaptation_policy_value=post_value,
                    bounds=None,
                    closure_summary=closure_summary,
                    baseline_policy_value=baseline_policy_value,
                    equilibrium_mean_payoffs=equilibrium_mean_payoffs,
                ),
                strategic_scm=strategic_scm,
                performative_loop_spec=performative_loop_spec,
            )

    if exact_block_reason is None:
        exact_block_reason = exact_budget_reason or (
            strategic_scm.runtime_blockers[0]
            if strategic_scm.runtime_blockers
            else "exact_equilibrium_unavailable"
        )

    def _try_macro_abstracted() -> StrategicSolveResult | None:
        nonlocal macro_block_reason
        if macro_payoff_tables is None:
            return None
        allowed_preservation_types = strategic_scm.allowed_macro_preservation_types
        if abstraction_certificate is None or (
            abstraction_certificate.preservation_type not in allowed_preservation_types
        ):
            if allowed_preservation_types == (AbstractionPreservationType.EXACT,):
                macro_block_reason = "macro_abstracted_requires_exact_abstraction_certificate"
            else:
                macro_block_reason = "macro_abstracted_requires_supported_abstraction_certificate"
            return None
        if (
            abstraction_certificate.preservation_type is not AbstractionPreservationType.EXACT
            and abstraction_certificate.error_bound is None
        ):
            macro_block_reason = "macro_abstracted_requires_error_bound_for_non_exact_abstraction"
            return None
        transfer_scope = _strategic_abstraction_transfer_scope(abstraction_certificate)
        if transfer_scope is None:
            macro_block_reason = "macro_abstracted_requires_strategic_transfer_scope"
            return None
        if not _certificate_supports_transfer_scope(
            abstraction_certificate,
            transfer_scope=transfer_scope,
        ):
            macro_block_reason = "macro_abstracted_requires_supported_preserved_queries"
            return None

        macro_result = solve_strategic_response(
            strategic_scm,
            macro_payoff_tables,
            baseline_policy_value=baseline_policy_value,
            abstraction_certificate=None,
            macro_payoff_tables=None,
            mean_field_inputs=None,
        )
        macro_bounds_allowed = (
            macro_preferred and macro_result.fallback_mode is StrategicFallbackMode.STRATEGIC_BOUNDS
        )
        if (
            macro_result.fallback_mode is not StrategicFallbackMode.EXACT_EQUILIBRIUM
            and not macro_bounds_allowed
        ):
            macro_block_reason = (
                macro_result.blocked_reason or "macro_abstracted_requires_exact_macro_equilibrium"
            )
            return None

        closure_summary = dict(macro_result.closure_summary)
        closure_summary["mode"] = StrategicFallbackMode.MACRO_ABSTRACTED.value
        closure_summary["abstraction_map_ref"] = str(
            abstraction_certificate.abstraction_map_ref.artifact_id
        )
        if abstraction_certificate.error_bound is not None:
            closure_summary["abstraction_error_bound"] = float(abstraction_certificate.error_bound)
        closure_summary["abstraction_preservation_type"] = (
            abstraction_certificate.preservation_type.value
        )
        closure_summary["abstraction_preserved_queries"] = list(
            abstraction_certificate.preserved_queries
        )
        closure_summary["abstraction_transfer_scope"] = transfer_scope
        allowed_intervention_family = abstraction_allowed_intervention_family(
            abstraction_certificate
        )
        if allowed_intervention_family is not None:
            closure_summary["abstraction_allowed_intervention_family"] = allowed_intervention_family
        estimand_error_bounds = abstraction_estimand_error_bounds(abstraction_certificate)
        if estimand_error_bounds:
            closure_summary["abstraction_estimand_error_bounds"] = estimand_error_bounds
        error_bound_spec = abstraction_error_bound_spec(abstraction_certificate)
        if error_bound_spec:
            closure_summary["abstraction_error_bound_spec"] = error_bound_spec
        recommendation_margin_required = abstraction_recommendation_margin_required(
            abstraction_certificate
        )
        if recommendation_margin_required is not None:
            closure_summary["abstraction_recommendation_margin_required"] = (
                recommendation_margin_required
            )
        return _with_performative_loop_analysis(
            StrategicSolveResult(
                fallback_mode=StrategicFallbackMode.MACRO_ABSTRACTED,
                equilibrium_profiles=macro_result.equilibrium_profiles,
                selected_equilibrium=macro_result.selected_equilibrium,
                equilibrium_selection_dependence=macro_result.equilibrium_selection_dependence,
                multiplicity_note=macro_result.multiplicity_note,
                blocked_reason=None,
                performative_shift=macro_result.performative_shift,
                post_adaptation_policy_value=macro_result.post_adaptation_policy_value,
                bounds=macro_result.bounds,
                closure_summary=closure_summary,
                baseline_policy_value=macro_result.baseline_policy_value,
                equilibrium_mean_payoffs=macro_result.equilibrium_mean_payoffs,
                warnings=(
                    "macro_abstracted_bounds_used"
                    if macro_bounds_allowed
                    else "macro_abstracted_equilibrium_used",
                ),
            ),
            strategic_scm=strategic_scm,
            performative_loop_spec=performative_loop_spec,
        )

    macro_preferred = strategic_scm.default_fallback_mode is StrategicFallbackMode.MACRO_ABSTRACTED
    if macro_preferred:
        macro_candidate = _try_macro_abstracted()
        if macro_candidate is not None:
            return macro_candidate

    if strategic_scm.default_fallback_mode is StrategicFallbackMode.BLOCKED:
        bounds_budget_ok = False
        bounds_budget_reason = "strategic_game_class_default_blocked"
    else:
        bounds_budget_ok, bounds_budget_reason = _check_budget(
            strategic_scm,
            profile_count=len(profiles),
        )
        if bounds_budget_ok:
            return _with_performative_loop_analysis(
                _strategic_bounds(
                    strategic_scm,
                    payoff_tables,
                    profiles,
                    baseline_policy_value=baseline_policy_value,
                ),
                strategic_scm=strategic_scm,
                performative_loop_spec=performative_loop_spec,
            )

    if not macro_preferred:
        macro_candidate = _try_macro_abstracted()
        if macro_candidate is not None:
            return macro_candidate

    return _with_performative_loop_analysis(
        StrategicSolveResult(
            fallback_mode=StrategicFallbackMode.BLOCKED,
            equilibrium_profiles=(),
            selected_equilibrium=None,
            equilibrium_selection_dependence="strategic_complexity_blocked",
            multiplicity_note=None,
            blocked_reason=macro_block_reason
            or bounds_budget_reason
            or exact_block_reason
            or "unidentified_due_to_strategic_complexity",
            performative_shift=None,
            post_adaptation_policy_value=None,
            bounds=None,
            closure_summary={
                "mode": StrategicFallbackMode.BLOCKED.value,
                "exact_block_reason": exact_block_reason,
                "bounds_block_reason": bounds_budget_reason,
                "macro_block_reason": macro_block_reason,
            },
        ),
        strategic_scm=strategic_scm,
        performative_loop_spec=performative_loop_spec,
    )


def strategic_result_summary(result: StrategicSolveResult) -> dict[str, Any]:
    """Project a `StrategicSolveResult` into a JSON-friendly summary payload."""

    summary: dict[str, Any] = {
        "fallback_mode": result.fallback_mode.value,
        "equilibrium_selection_dependence": result.equilibrium_selection_dependence,
        "multiplicity_note": result.multiplicity_note,
        "blocked_reason": result.blocked_reason,
        "closure_summary": dict(result.closure_summary),
        "warnings": list(result.warnings),
    }
    summary.update(strategic_decomposition_summary(result))
    if result.selected_equilibrium is not None:
        summary["selected_equilibrium"] = dict(result.selected_equilibrium)
    if result.performative_shift is not None:
        summary["performative_shift"] = float(result.performative_shift)
    if result.post_adaptation_policy_value is not None:
        summary["post_adaptation_policy_value"] = float(result.post_adaptation_policy_value)
    if result.bounds is not None:
        summary["bounds"] = [float(result.bounds[0]), float(result.bounds[1])]
    if result.equilibrium_profiles:
        summary["equilibrium_profiles"] = [dict(profile) for profile in result.equilibrium_profiles]
    if result.performative_loop_certificate is not None:
        summary["performative_loop"] = result.performative_loop_certificate.model_dump(mode="json")
    if result.mfg_equilibrium_certificate is not None:
        summary["mfg_equilibrium"] = {
            "mean_field_model_class": (
                result.mfg_equilibrium_certificate.mean_field_model_class.value
            ),
            "positivity_status": (
                result.mfg_equilibrium_certificate.identification.positivity_status.value
            ),
            "selection_rule": (
                result.mfg_equilibrium_certificate.identification.selection_rule.value
            ),
            "has_solver_residual": result.mfg_solver_residual_report is not None,
            "has_mass_conservation": result.mfg_mass_conservation_report is not None,
        }
    return summary


def strategic_decomposition_summary(result: StrategicSolveResult) -> dict[str, Any]:
    """Project the current strategic solve into a decomposition disclosure."""

    baseline_value = result.baseline_policy_value
    equilibrium_payoffs = tuple(float(value) for value in result.equilibrium_mean_payoffs)
    if not equilibrium_payoffs and result.performative_shift is not None:
        equilibrium_payoffs = (float(result.performative_shift),)
    selected_equilibrium = (
        dict(result.selected_equilibrium) if result.selected_equilibrium is not None else None
    )

    if result.fallback_mode is StrategicFallbackMode.STRATEGIC_BOUNDS:
        failure_code = "decomposition_only_total_bounds_available"
        message = (
            "Only total post-adaptation bounds are available; causal and strategic "
            "components are not separately licensed."
        )
        status = StrategicDecompositionStatus.BLOCKED
    elif result.fallback_mode is StrategicFallbackMode.MACRO_ABSTRACTED:
        failure_code = "decomposition_abstraction_not_preserving"
        message = (
            "Macro abstraction does not, by itself, certify decomposition-preserving "
            "transport of the causal and strategic components."
        )
        status = StrategicDecompositionStatus.BLOCKED
    elif result.fallback_mode is StrategicFallbackMode.BLOCKED:
        failure_code = "decomposition_no_equilibrium"
        message = (
            "Strategic runtime did not produce an equilibrium closure that could anchor "
            "causal/strategic decomposition."
        )
        status = StrategicDecompositionStatus.BLOCKED
    elif baseline_value is None or selected_equilibrium is None:
        failure_code = "decomposition_cross_world_anchor_undefined"
        message = (
            "Point decomposition requires a baseline policy-value anchor and an "
            "explicit frozen-baseline equilibrium anchor."
        )
        status = StrategicDecompositionStatus.BLOCKED
    elif len(equilibrium_payoffs) == 1:
        return {
            "decomposition_status": StrategicDecompositionStatus.EXACT.value,
            "decomposition_semantics": StrategicDecompositionSemantics.FROZEN_BASELINE_STRATEGY.value,
            "decomposition_message": (
                "Causal and strategic components are point-identified under the "
                "frozen-baseline equilibrium anchor."
            ),
            "cross_world_anchor_defined": True,
            "selector_invariant": False,
            "causal_component_value": float(baseline_value),
            "strategic_component_value": float(equilibrium_payoffs[0]),
            "anchor_equilibrium": selected_equilibrium,
        }
    elif max(equilibrium_payoffs) - min(equilibrium_payoffs) <= 1.0e-12:
        return {
            "decomposition_status": StrategicDecompositionStatus.SELECTOR_INVARIANT.value,
            "decomposition_semantics": StrategicDecompositionSemantics.FROZEN_BASELINE_STRATEGY.value,
            "decomposition_message": (
                "Multiplicity remains, but every admissible equilibrium induces the "
                "same causal/strategic component pair."
            ),
            "cross_world_anchor_defined": True,
            "selector_invariant": True,
            "causal_component_value": float(baseline_value),
            "strategic_component_value": float(equilibrium_payoffs[0]),
            "anchor_equilibrium": selected_equilibrium,
        }
    elif equilibrium_payoffs:
        return {
            "decomposition_status": StrategicDecompositionStatus.BOUNDED.value,
            "decomposition_semantics": StrategicDecompositionSemantics.FROZEN_BASELINE_STRATEGY.value,
            "decomposition_message": (
                "Equilibrium multiplicity changes the strategic response, so the "
                "runtime exposes interval-valued decomposition only."
            ),
            "cross_world_anchor_defined": True,
            "selector_invariant": False,
            "causal_component_bounds": [float(baseline_value), float(baseline_value)],
            "strategic_component_bounds": [
                float(min(equilibrium_payoffs)),
                float(max(equilibrium_payoffs)),
            ],
            "anchor_equilibrium": selected_equilibrium,
        }
    else:
        failure_code = "decomposition_selector_dependence_nontrivial"
        message = (
            "Different admissible equilibrium selections may induce different causal/strategic "
            "component pairs, but no honest component interval artifacts were available."
        )
        status = StrategicDecompositionStatus.BLOCKED

    return {
        "decomposition_status": status.value,
        "decomposition_semantics": StrategicDecompositionSemantics.FROZEN_BASELINE_STRATEGY.value,
        "decomposition_failure_code": failure_code,
        "decomposition_message": message,
    }


def build_strategic_response_bundle(
    *,
    causal_component_ref: ArtifactRefModel,
    strategic_closure_ref: ArtifactRefModel,
    equilibrium_set_ref: ArtifactRefModel,
    post_adaptation_policy_value_ref: ArtifactRefModel,
    result: StrategicSolveResult,
    decomposition_status: StrategicDecompositionStatus,
    behavioral_assumption_sensitivity_ref: ArtifactRefModel | None = None,
    selected_equilibrium_ref: ArtifactRefModel | None = None,
    performative_shift_ref: ArtifactRefModel | None = None,
    mfg_equilibrium_ref: MeanFieldEquilibriumCertificateRef | None = None,
    decomposition_certificate_ref: ArtifactRefModel | None = None,
    decomposition_failure_card_ref: ArtifactRefModel | None = None,
    equilibrium_selector_ref: ArtifactRefModel | None = None,
    anchor_equilibrium_ref: ArtifactRefModel | None = None,
    causal_component_bounds_ref: ArtifactRefModel | None = None,
    strategic_component_bounds_ref: ArtifactRefModel | None = None,
) -> StrategicResponseBundle:
    """Build the persisted IR bundle for a solved strategic-response contract."""

    # StrategicResponseBundle is a blueprint-runtime artifact. Method-layer helpers
    # should emit summaries only and must not fabricate persisted strategic refs.
    return StrategicResponseBundle(
        causal_component_ref=causal_component_ref,
        strategic_closure_ref=strategic_closure_ref,
        equilibrium_selection_dependence=result.equilibrium_selection_dependence,
        behavioral_assumption_sensitivity_ref=behavioral_assumption_sensitivity_ref,
        equilibrium_set_ref=equilibrium_set_ref,
        selected_equilibrium_ref=selected_equilibrium_ref,
        multiplicity_note=result.multiplicity_note,
        mfg_equilibrium_ref=mfg_equilibrium_ref,
        performative_shift_ref=performative_shift_ref,
        post_adaptation_policy_value_ref=post_adaptation_policy_value_ref,
        decomposition_status=decomposition_status,
        decomposition_certificate_ref=decomposition_certificate_ref,
        decomposition_failure_card_ref=decomposition_failure_card_ref,
        equilibrium_selector_ref=equilibrium_selector_ref,
        anchor_equilibrium_ref=anchor_equilibrium_ref,
        causal_component_bounds_ref=causal_component_bounds_ref,
        strategic_component_bounds_ref=strategic_component_bounds_ref,
        fallback_mode=result.fallback_mode,
        blocked_reason=result.blocked_reason,
        metadata={"closure_summary": dict(result.closure_summary)},
    )


def _default_strategic_decomposition_failure_card(
    result: StrategicSolveResult,
    *,
    metadata: dict[str, Any],
) -> StrategicDecompositionFailureCard:
    summary = strategic_decomposition_summary(result)
    return StrategicDecompositionFailureCard(
        failure_code=str(summary["decomposition_failure_code"]),
        message=str(summary["decomposition_message"]),
        fallback_mode=result.fallback_mode,
        equilibrium_selection_dependence=result.equilibrium_selection_dependence,
        multiplicity_note=result.multiplicity_note,
        blocked_reason=result.blocked_reason,
        metadata={
            **metadata,
            "decomposition_status": str(summary["decomposition_status"]),
        },
    )


def persist_strategic_solve_artifacts(
    store: ArtifactStore,
    *,
    causal_component_ref: ArtifactRefModel,
    result: StrategicSolveResult,
    equilibrium_concept: StrategicEquilibriumConcept | None,
    equilibrium_descriptor: StrategicEquilibriumDescriptor | None = None,
    baseline_policy_value: float | None = None,
    inputs: list[InputRef] | None = None,
    metadata: dict[str, Any] | None = None,
    decomposition_status: StrategicDecompositionStatus | None = None,
    decomposition_certificate: StrategicDecompositionCertificate | None = None,
    decomposition_failure_card: StrategicDecompositionFailureCard | None = None,
    anchor_equilibrium: EquilibriumSelectionSummary | None = None,
    equilibrium_selector_ref: ArtifactRefModel | None = None,
    causal_component_bounds: StrategicComponentBoundsSummary | None = None,
    strategic_component_bounds: StrategicComponentBoundsSummary | None = None,
    mfg_equilibrium_certificate: MeanFieldEquilibriumCertificate | None = None,
    mfg_macro_simulation_config: MeanFieldMacroSimulationConfig | None = None,
    mfg_solver_residual_report: MeanFieldSolverResidualReport | None = None,
    mfg_mass_conservation_report: MeanFieldMassConservationReport | None = None,
) -> tuple[StrategicResponseBundle, StrategicResponseBundleRef]:
    """Persist the strategic closure, equilibrium set, and policy-value summaries."""
    bundle_metadata = {
        **dict(getattr(result, "closure_summary", {}) or {}),
        **dict(metadata or {}),
    }
    closure_summary = StrategicClosureSummary(
        fallback_mode=result.fallback_mode,
        equilibrium_concept=equilibrium_concept,
        equilibrium_descriptor=equilibrium_descriptor,
        equilibrium_selection_dependence=result.equilibrium_selection_dependence,
        profile_count=int(result.closure_summary.get("profile_count") or 0),
        equilibrium_count=int(
            result.closure_summary.get("equilibrium_count") or len(result.equilibrium_profiles)
        ),
        blocked_reason=result.blocked_reason,
        warnings=tuple(str(item) for item in result.warnings),
        metadata=bundle_metadata,
    )
    strategic_closure_ref = persist_strategic_closure_summary(store, closure_summary, inputs=inputs)
    equilibrium_set_ref = persist_equilibrium_set_summary(
        store,
        EquilibriumSetSummary(
            equilibrium_profiles=tuple(dict(profile) for profile in result.equilibrium_profiles),
            equilibrium_count=len(result.equilibrium_profiles),
            multiplicity_note=result.multiplicity_note,
            metadata=bundle_metadata,
        ),
        inputs=inputs,
    )
    selected_equilibrium_ref = None
    if result.selected_equilibrium is not None and mfg_equilibrium_certificate is None:
        selected_equilibrium_ref = persist_equilibrium_selection_summary(
            store,
            EquilibriumSelectionSummary(
                selected_equilibrium=dict(result.selected_equilibrium),
                equilibrium_selection_dependence=result.equilibrium_selection_dependence,
                metadata=bundle_metadata,
            ),
            inputs=inputs,
        )
    performative_shift_ref = None
    if (
        result.performative_shift is not None
        or getattr(result, "performative_loop_certificate", None) is not None
    ):
        certificate_payload = {}
        certificate_metadata: dict[str, Any] = {}
        if getattr(result, "performative_loop_certificate", None) is not None:
            certificate_payload = result.performative_loop_certificate.model_dump(mode="json")
            certificate_metadata = dict(certificate_payload.pop("metadata", {}) or {})
        performative_shift_ref = persist_performative_shift_summary(
            store,
            PerformativeShiftSummary(
                **certificate_payload,
                performative_shift=(
                    None if result.performative_shift is None else float(result.performative_shift)
                ),
                baseline_policy_value=baseline_policy_value,
                post_adaptation_policy_value=result.post_adaptation_policy_value,
                metadata={**bundle_metadata, **certificate_metadata},
            ),
            inputs=inputs,
        )
    post_adaptation_policy_value_ref = persist_post_adaptation_policy_value_summary(
        store,
        PostAdaptationPolicyValueSummary(
            fallback_mode=result.fallback_mode,
            baseline_policy_value=baseline_policy_value,
            point_value=result.post_adaptation_policy_value if result.bounds is None else None,
            lower_bound=None if result.bounds is None else float(result.bounds[0]),
            upper_bound=None if result.bounds is None else float(result.bounds[1]),
            blocked_reason=result.blocked_reason,
            metadata=bundle_metadata,
        ),
        inputs=inputs,
    )
    decomposition_summary = strategic_decomposition_summary(result)
    resolved_decomposition_status = (
        decomposition_status
        if decomposition_status is not None
        else StrategicDecompositionStatus(str(decomposition_summary["decomposition_status"]))
    )
    if decomposition_certificate is None and resolved_decomposition_status in {
        StrategicDecompositionStatus.EXACT,
        StrategicDecompositionStatus.SELECTOR_INVARIANT,
    }:
        decomposition_certificate = StrategicDecompositionCertificate(
            decomposition_status=resolved_decomposition_status,
            cross_world_anchor_defined=bool(
                decomposition_summary.get("cross_world_anchor_defined", False)
            ),
            selector_invariant=bool(decomposition_summary.get("selector_invariant", False)),
            equilibrium_selector_justified=(
                str(getattr(result, "equilibrium_selection_dependence", "")).strip().lower()
                in {"deterministic", "deterministic_selection"}
            ),
            assumptions_checked=("frozen_baseline_strategy_anchor",),
            metadata={
                **bundle_metadata,
                "causal_component_value": decomposition_summary.get("causal_component_value"),
                "strategic_component_value": decomposition_summary.get("strategic_component_value"),
            },
        )
    if (
        anchor_equilibrium is None
        and resolved_decomposition_status
        in {
            StrategicDecompositionStatus.EXACT,
            StrategicDecompositionStatus.SELECTOR_INVARIANT,
        }
        and getattr(result, "selected_equilibrium", None) is not None
    ):
        anchor_equilibrium = EquilibriumSelectionSummary(
            selected_equilibrium=dict(result.selected_equilibrium),
            equilibrium_selection_dependence=str(
                getattr(result, "equilibrium_selection_dependence", "deterministic")
            ),
            metadata={
                **bundle_metadata,
                "decomposition_semantics": StrategicDecompositionSemantics.FROZEN_BASELINE_STRATEGY.value,
            },
        )
    if resolved_decomposition_status is StrategicDecompositionStatus.BOUNDED:
        causal_bounds_payload = decomposition_summary.get("causal_component_bounds")
        strategic_bounds_payload = decomposition_summary.get("strategic_component_bounds")
        if (
            causal_component_bounds is None
            and isinstance(causal_bounds_payload, list)
            and len(causal_bounds_payload) == 2
        ):
            causal_component_bounds = StrategicComponentBoundsSummary(
                component=StrategicDecompositionComponent.CAUSAL,
                lower_bound=float(causal_bounds_payload[0]),
                upper_bound=float(causal_bounds_payload[1]),
                metadata=bundle_metadata,
            )
        if (
            strategic_component_bounds is None
            and isinstance(strategic_bounds_payload, list)
            and len(strategic_bounds_payload) == 2
        ):
            strategic_component_bounds = StrategicComponentBoundsSummary(
                component=StrategicDecompositionComponent.STRATEGIC,
                lower_bound=float(strategic_bounds_payload[0]),
                upper_bound=float(strategic_bounds_payload[1]),
                metadata=bundle_metadata,
            )
    decomposition_certificate_ref = None
    if decomposition_certificate is not None:
        decomposition_certificate_ref = persist_strategic_decomposition_certificate(
            store,
            decomposition_certificate,
            inputs=inputs,
        )
    decomposition_failure_card_ref = None
    if (
        decomposition_failure_card is None
        and resolved_decomposition_status is StrategicDecompositionStatus.BLOCKED
    ):
        decomposition_failure_card = _default_strategic_decomposition_failure_card(
            result,
            metadata=bundle_metadata,
        )
    if decomposition_failure_card is not None:
        decomposition_failure_card_ref = persist_strategic_decomposition_failure_card(
            store,
            decomposition_failure_card,
            inputs=inputs,
        )
    anchor_equilibrium_ref = None
    if anchor_equilibrium is not None:
        anchor_equilibrium_ref = persist_equilibrium_selection_summary(
            store,
            anchor_equilibrium,
            inputs=inputs,
        )
    causal_component_bounds_ref = None
    if causal_component_bounds is not None:
        causal_component_bounds_ref = persist_strategic_component_bounds_summary(
            store,
            causal_component_bounds,
            inputs=inputs,
        )
    strategic_component_bounds_ref = None
    if strategic_component_bounds is not None:
        strategic_component_bounds_ref = persist_strategic_component_bounds_summary(
            store,
            strategic_component_bounds,
            inputs=inputs,
        )
    mfg_equilibrium_ref = None
    if mfg_equilibrium_certificate is not None:
        if (
            mfg_macro_simulation_config is not None
            and mfg_equilibrium_certificate.provenance is not None
            and mfg_equilibrium_certificate.provenance.numerics_config_ref is not None
        ):
            raise ValueError(
                "mfg_macro_simulation_config must be omitted when certificate provenance already carries numerics_config_ref"
            )
        resolved_mfg_certificate = mfg_equilibrium_certificate
        mfg_equilibrium_solution = (
            resolved_mfg_certificate.equilibrium_solution or MeanFieldEquilibriumSolutionSummary()
        )
        if mfg_solver_residual_report is not None:
            solver_residual_ref = persist_mean_field_solver_residual_report(
                store,
                mfg_solver_residual_report,
                inputs=inputs,
            )
            mfg_equilibrium_solution = mfg_equilibrium_solution.model_copy(
                update={"solver_residual_ref": solver_residual_ref}
            )
        if mfg_mass_conservation_report is not None:
            mass_conservation_ref = persist_mean_field_mass_conservation_report(
                store,
                mfg_mass_conservation_report,
                inputs=inputs,
            )
            mfg_equilibrium_solution = mfg_equilibrium_solution.model_copy(
                update={"mass_conservation_ref": mass_conservation_ref}
            )
        resolved_mfg_certificate = resolved_mfg_certificate.model_copy(
            update={"equilibrium_solution": mfg_equilibrium_solution}
        )
        if mfg_macro_simulation_config is not None:
            numerics_config_ref = persist_mean_field_macro_simulation_config(
                store,
                mfg_macro_simulation_config,
                inputs=inputs,
            )
            provenance = resolved_mfg_certificate.provenance
            if provenance is None:
                provenance = MeanFieldProvenanceSummary(
                    numerics_config_ref=numerics_config_ref,
                )
            else:
                provenance = provenance.model_copy(
                    update={"numerics_config_ref": numerics_config_ref}
                )
            resolved_mfg_certificate = resolved_mfg_certificate.model_copy(
                update={"provenance": provenance}
            )
        resolved_mfg_certificate = MeanFieldEquilibriumCertificate.model_validate(
            resolved_mfg_certificate.model_dump(mode="json")
        )
        mfg_equilibrium_ref = persist_mean_field_equilibrium_certificate(
            store,
            resolved_mfg_certificate,
            inputs=inputs,
        )
    bundle = build_strategic_response_bundle(
        causal_component_ref=causal_component_ref,
        strategic_closure_ref=strategic_closure_ref,
        equilibrium_set_ref=equilibrium_set_ref,
        post_adaptation_policy_value_ref=post_adaptation_policy_value_ref,
        selected_equilibrium_ref=selected_equilibrium_ref,
        performative_shift_ref=performative_shift_ref,
        mfg_equilibrium_ref=mfg_equilibrium_ref,
        decomposition_status=resolved_decomposition_status,
        decomposition_certificate_ref=decomposition_certificate_ref,
        decomposition_failure_card_ref=decomposition_failure_card_ref,
        equilibrium_selector_ref=equilibrium_selector_ref,
        anchor_equilibrium_ref=anchor_equilibrium_ref,
        causal_component_bounds_ref=causal_component_bounds_ref,
        strategic_component_bounds_ref=strategic_component_bounds_ref,
        result=result,
    ).model_copy(update={"metadata": bundle_metadata})
    bundle_ref = persist_strategic_response_bundle(store, bundle, inputs=inputs)
    return bundle, bundle_ref


def evaluate_strategic_hook(
    *,
    params: Mapping[str, Any],
    baseline_policy_value: float | None,
) -> tuple[dict[str, Any] | None, tuple[str, ...], StrategicResponseBundle | None]:
    """Best-effort strategic hook that never raises on malformed optional inputs."""

    strategic_payload = params.get("strategic_scm")
    if strategic_payload is None:
        return None, (), None

    try:
        contract = _coerce_strategic_contract(strategic_payload)
        abstraction_certificate = _coerce_abstraction_certificate(
            params.get("abstraction_certificate")
        )
        mean_field_payload = params.get("mean_field_game")
        macro_payload = params.get("macro_strategic_payoff_tables")
        macro_tables = None if macro_payload is None else _coerce_payoff_tables(macro_payload)
        if params.get("strategic_payoff_tables") is None and (
            mean_field_payload is not None or _requires_mean_field_runtime(contract)
        ):
            payoff_tables: dict[str, FiniteStrategicPayoffTable] = {}
        else:
            payoff_tables = _coerce_payoff_tables(params.get("strategic_payoff_tables"))
        result = solve_strategic_response(
            contract,
            payoff_tables,
            baseline_policy_value=baseline_policy_value,
            abstraction_certificate=abstraction_certificate,
            macro_payoff_tables=macro_tables,
            performative_loop_spec=params.get("performative_loop_spec"),
            mean_field_inputs=mean_field_payload,
        )
        return strategic_result_summary(result), result.warnings, None
    except Exception as exc:
        blocked = StrategicSolveResult(
            fallback_mode=StrategicFallbackMode.BLOCKED,
            equilibrium_profiles=(),
            selected_equilibrium=None,
            equilibrium_selection_dependence="strategic_hook_invalid_input",
            multiplicity_note=None,
            blocked_reason="strategic_hook_invalid_input",
            performative_shift=None,
            post_adaptation_policy_value=None,
            bounds=None,
            closure_summary={"mode": StrategicFallbackMode.BLOCKED.value, "reason": str(exc)},
            warnings=("strategic_hook_invalid_input",),
        )
        return strategic_result_summary(blocked), blocked.warnings, None


__all__ = [
    "MAX_STRATEGIC_ACTIONS_PER_AGENT",
    "MAX_STRATEGIC_PROFILE_ENUMERATIONS",
    "PerformativeLoopSpec",
    "StrategicSolveResult",
    "analyze_performative_loop",
    "build_strategic_response_bundle",
    "evaluate_strategic_hook",
    "solve_strategic_response",
    "strategic_decomposition_summary",
    "strategic_result_summary",
]
