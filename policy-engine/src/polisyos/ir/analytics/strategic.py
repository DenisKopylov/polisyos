"""Represent strategic-response games, admissibility descriptors, and persisted closure artifacts."""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir._internal.validation import ensure_finite_numeric, ensure_unique_ids
from polisyos.ir.analytics.abstraction import AbstractionPreservationType
from polisyos.ir.analytics.causal_queries import InterventionSpec, InterventionType
from polisyos.ir.analytics.dynamic_regime import RuntimeSupportStatus
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.kernel.base import ComputeBudget
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    MeanFieldEquilibriumCertificateRef,
    MeanFieldMacroSimulationConfigRef,
    MeanFieldPerturbationSpecRef,
    StrategicPayoffTableRef,
    StrategicResponseBundleRef,
    StrategicSCMRef,
)

_STRATEGIC_PAYOFF_TABLE_SCHEMA_NAME = "ir.strategic_payoff_table"
_STRATEGIC_PAYOFF_TABLE_SCHEMA_VERSION = "1.0"
_STRATEGIC_SCM_SCHEMA_NAME = "ir.strategic_scm"
_STRATEGIC_SCM_SCHEMA_VERSION = "1.1"
_STRATEGIC_RESPONSE_BUNDLE_SCHEMA_NAME = "ir.strategic_response_bundle"
_STRATEGIC_RESPONSE_BUNDLE_SCHEMA_VERSION = "1.1"
_MFG_EQUILIBRIUM_CERTIFICATE_SCHEMA_NAME = "ir.mean_field_equilibrium_certificate"
_MFG_EQUILIBRIUM_CERTIFICATE_SCHEMA_VERSION = "1.0"
_MFG_PERTURBATION_SPEC_SCHEMA_NAME = "ir.mean_field_perturbation_spec"
_MFG_PERTURBATION_SPEC_SCHEMA_VERSION = "1.0"
_MFG_MACRO_SIMULATION_CONFIG_SCHEMA_NAME = "ir.mean_field_macro_simulation_config"
_MFG_MACRO_SIMULATION_CONFIG_SCHEMA_VERSION = "1.0"
_MFG_SOLVER_RESIDUAL_REPORT_SCHEMA_NAME = "ir.mean_field_solver_residual_report"
_MFG_SOLVER_RESIDUAL_REPORT_SCHEMA_VERSION = "1.0"
_MFG_MASS_CONSERVATION_REPORT_SCHEMA_NAME = "ir.mean_field_mass_conservation_report"
_MFG_MASS_CONSERVATION_REPORT_SCHEMA_VERSION = "1.0"
_STRATEGIC_CLOSURE_SUMMARY_SCHEMA_NAME = "ir.strategic_closure_summary"
_STRATEGIC_CLOSURE_SUMMARY_SCHEMA_VERSION = "1.1"
_EQUILIBRIUM_SET_SUMMARY_SCHEMA_NAME = "ir.equilibrium_set_summary"
_EQUILIBRIUM_SET_SUMMARY_SCHEMA_VERSION = "1.0"
_EQUILIBRIUM_SELECTION_SUMMARY_SCHEMA_NAME = "ir.equilibrium_selection_summary"
_EQUILIBRIUM_SELECTION_SUMMARY_SCHEMA_VERSION = "1.0"
_PERFORMATIVE_SHIFT_SUMMARY_SCHEMA_NAME = "ir.performative_shift_summary"
_PERFORMATIVE_SHIFT_SUMMARY_SCHEMA_VERSION = "1.1"
_POST_ADAPTATION_POLICY_VALUE_SUMMARY_SCHEMA_NAME = "ir.post_adaptation_policy_value_summary"
_POST_ADAPTATION_POLICY_VALUE_SUMMARY_SCHEMA_VERSION = "1.0"
_STRATEGIC_DECOMPOSITION_CERTIFICATE_SCHEMA_NAME = "ir.strategic_decomposition_certificate"
_STRATEGIC_DECOMPOSITION_CERTIFICATE_SCHEMA_VERSION = "1.0"
_STRATEGIC_DECOMPOSITION_FAILURE_CARD_SCHEMA_NAME = "ir.strategic_decomposition_failure_card"
_STRATEGIC_DECOMPOSITION_FAILURE_CARD_SCHEMA_VERSION = "1.0"
_STRATEGIC_COMPONENT_BOUNDS_SUMMARY_SCHEMA_NAME = "ir.strategic_component_bounds_summary"
_STRATEGIC_COMPONENT_BOUNDS_SUMMARY_SCHEMA_VERSION = "1.0"


def _ensure_non_empty(value: str, *, field_name: str) -> str:
    candidate = str(value).strip()
    if not candidate:
        raise ValueError(f"{field_name} must be non-empty")
    return candidate


def _ensure_finite(value: float, *, field_name: str) -> float:
    return float(ensure_finite_numeric(value, field_name=field_name))


def _normalize_string_tuple(value: Any, *, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        raw_items = (value,)
    elif isinstance(value, (list, tuple, set)):
        raw_items = tuple(value)
    else:
        raise ValueError(f"{field_name} must be a string or tuple/list/set of strings")
    normalized = tuple(_ensure_non_empty(str(item), field_name=field_name) for item in raw_items)
    if normalized:
        ensure_unique_ids(normalized, key_fn=lambda item: item, label=field_name)
    return normalized


def _validate_unique_enum_tuple(values: tuple[Enum, ...], *, field_name: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must not contain duplicates")


def _validate_artifact_ref(ref: ArtifactRefModel, *, field_name: str) -> ArtifactRefModel:
    if not str(ref.kind).strip():
        raise ValueError(f"{field_name}.kind must be non-empty")
    if not str(ref.media_type).strip():
        raise ValueError(f"{field_name}.media_type must be non-empty")
    return ref


def _persist_strategic_leaf(
    store: ArtifactStore,
    payload: BaseModel,
    *,
    kind: str,
    schema_name: str,
    schema_version: str,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    ref = put_json_artifact(
        store,
        payload.model_dump(mode="json"),
        kind=kind,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ArtifactRefModel.model_validate(ref)


def _load_strategic_leaf(
    store: ArtifactStore,
    ref: ArtifactRefModel,
    model: type[BaseModel],
) -> Any:
    payload = get_json_artifact(store, ref.artifact_id)
    return model.model_validate(payload)


def encode_action_profile(
    profile: dict[str, str],
    *,
    agent_order: tuple[str, ...],
) -> str:
    """Encode a joint action profile using a stable agent order."""

    return "|".join(f"{agent}={profile[agent]}" for agent in agent_order)


def decode_action_profile(
    encoded: str,
    *,
    agent_order: tuple[str, ...],
) -> dict[str, str]:
    """Decode a joint action profile emitted by ``encode_action_profile``."""

    raw_parts = [part.strip() for part in str(encoded).split("|") if str(part).strip()]
    parsed: dict[str, str] = {}
    for part in raw_parts:
        if "=" not in part:
            raise ValueError(f"Invalid action profile fragment {part!r}")
        agent, action = part.split("=", 1)
        parsed[_ensure_non_empty(agent, field_name="profile.agent")] = _ensure_non_empty(
            action,
            field_name="profile.action",
        )
    if tuple(parsed) != agent_order:
        raise ValueError(
            "Action profile must specify every agent exactly once in strategic_agents order"
        )
    return parsed


class StrategicEquilibriumConcept(str, Enum):
    """Select the equilibrium notion used by strategic-response solvers."""

    NASH = "nash"
    STACKELBERG = "stackelberg"
    BEST_RESPONSE_FIXED_POINT = "best_response_fixed_point"
    MINIMAX_ZERO_SUM = "minimax_zero_sum"
    MIXED_NASH_FINITE_GENERAL_SUM = "mixed_nash_finite_general_sum"
    STACKELBERG_SINGLE_FOLLOWER_OPTIMISTIC = "stackelberg_single_follower_optimistic"
    STACKELBERG_SINGLE_FOLLOWER_PESSIMISTIC = "stackelberg_single_follower_pessimistic"
    PURE_NASH_POTENTIAL = "pure_nash_potential"
    VARIATIONAL_EQUILIBRIUM_MONOTONE = "variational_equilibrium_monotone"
    GNE_JOINTLY_CONVEX = "gne_jointly_convex"
    EPSILON_NASH_ANONYMOUS = "epsilon_nash_anonymous"


class StrategicFallbackMode(str, Enum):
    """Report whether strategic evaluation used exact, bounded, abstracted, or blocked fallback."""

    EXACT_EQUILIBRIUM = "exact_equilibrium"
    STRATEGIC_BOUNDS = "strategic_bounds"
    MACRO_ABSTRACTED = "macro_abstracted"
    BLOCKED = "blocked"


class StrategicDecompositionStatus(str, Enum):
    """Whether the causal/strategic split is point-identified, bounded, or blocked."""

    EXACT = "exact"
    SELECTOR_INVARIANT = "selector_invariant"
    BOUNDED = "bounded"
    BLOCKED = "blocked"


class StrategicDecompositionSemantics(str, Enum):
    """Semantics for strategic decomposition claims carried by the bundle."""

    FROZEN_BASELINE_STRATEGY = "frozen_baseline_strategy"


class StrategicGameClass(str, Enum):
    """Policy-relevant game family used to classify admissibility and fallback defaults."""

    ZERO_SUM = "zero_sum"
    NORMAL_FORM_GENERAL_SUM = "normal_form_general_sum"
    STACKELBERG_SINGLE_FOLLOWER = "stackelberg_single_follower"
    STACKELBERG_COMPLEX = "stackelberg_complex"
    POTENTIAL_CONGESTION = "potential_congestion"
    CONCAVE_VI = "concave_vi"
    GNE_JOINTLY_CONVEX = "gne_jointly_convex"
    GNE_NONCONVEX = "gne_nonconvex"
    ANONYMOUS_AGGREGATIVE = "anonymous_aggregative"
    SMALL_FINITE_BEST_RESPONSE = "small_finite_best_response"


class StrategicSolutionConcept(str, Enum):
    """Solution concept used inside one strategic game class."""

    MINIMAX = "minimax"
    MIXED_NASH = "mixed_nash"
    PURE_NASH = "pure_nash"
    STACKELBERG_OPTIMISTIC = "stackelberg_optimistic"
    STACKELBERG_PESSIMISTIC = "stackelberg_pessimistic"
    VARIATIONAL_EQUILIBRIUM = "variational_equilibrium"
    EPSILON_NASH = "epsilon_nash"
    BEST_RESPONSE_FIXED_POINT = "best_response_fixed_point"


class StrategicTractabilityClass(str, Enum):
    """Asymptotic tractability bucket used by the admissibility registry."""

    P = "P"
    POLY_EPSILON = "POLY_EPSILON"
    PPAD = "PPAD"
    PLS = "PLS"
    NP_HARD = "NP_HARD"
    GLOBAL_OPT = "GLOBAL_OPT"
    UNKNOWN = "UNKNOWN"


class PerformativeLoopAnalysisScope(str, Enum):
    """Scope under which a performative-loop certificate should be interpreted."""

    SINGLE_STEP_ONLY = "single_step_only"
    ITERATED_LOOP = "iterated_loop"


class PerformativeLoopProofFamily(str, Enum):
    """Proof family used to certify or diagnose a performative policy loop."""

    RRM_PARAMETRIC = "rrm_parametric"
    RGD_PARAMETRIC = "rgd_parametric"
    STATEFUL_LIPSCHITZ = "stateful_lipschitz"
    STATEFUL_MARKOV_SA = "stateful_markov_sa"
    MIXED_NO_REGRET_FALLBACK = "mixed_no_regret_fallback"


class PerformativeLoopStabilityStatus(str, Enum):
    """Closed-loop stability verdict for iterated performative deployment."""

    CERTIFIED_CONVERGENT = "certified_convergent"
    LOCALLY_CONVERGENT = "locally_convergent"
    UNCERTIFIED = "uncertified"
    CERTIFIED_UNSTABLE = "certified_unstable"
    MIXED_STABLE_ONLY = "mixed_stable_only"


class PerformativeInstabilityReason(str, Enum):
    """Machine-readable reason why the loop was or was not certified."""

    GLOBAL_CONTRACTION_FAILED = "global_contraction_failed"
    LOCAL_SPECTRAL_RADIUS_GT_ONE = "local_spectral_radius_gt_one"
    CYCLE_DETECTED = "cycle_detected"
    DIVERGENCE_DETECTED = "divergence_detected"
    HARDNESS_ZONE = "hardness_zone"
    INSUFFICIENT_MODELING_ASSUMPTIONS = "insufficient_modeling_assumptions"


class PerformativeLoopWitnessStrength(str, Enum):
    """Strength of the witness attached to the performative-loop verdict."""

    THEOREM = "theorem"
    LOCAL_LINEARIZATION = "local_linearization"
    SIMULATION = "simulation"
    MIXED_FALLBACK = "mixed_fallback"


class PerformativeLoopRecommendedAction(str, Enum):
    """Operational action recommended by the loop certificate."""

    ALLOW_AUTO_ITERATION = "allow_auto_iteration"
    ALLOW_WITH_HUMAN_REVIEW = "allow_with_human_review"
    BLOCK_AUTO_ITERATION = "block_auto_iteration"
    SWITCH_TO_MIXED_NO_REGRET = "switch_to_mixed_no_regret"
    SINGLE_SHOT_ONLY = "single_shot_only"


@dataclass(frozen=True)
class _StrategicAdmissibilityEntry:
    tractability_class: StrategicTractabilityClass
    default_fallback_mode: StrategicFallbackMode
    existence_theorem: str
    runtime_support_status: RuntimeSupportStatus
    equilibrium_concept_aliases: tuple[StrategicEquilibriumConcept, ...] = ()
    default_tie_breaking_rule: str | None = None
    required_existence_assumptions: tuple[str, ...] = ()
    macro_preservation_types: tuple[AbstractionPreservationType, ...] = (
        AbstractionPreservationType.EXACT,
    )


class StrategicAdmissibilityRecord(BaseModel):
    """Serializable registry row for policy-safe strategic game class admission."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    game_class: StrategicGameClass
    solution_concept: StrategicSolutionConcept
    tractability_class: StrategicTractabilityClass
    default_fallback_mode: StrategicFallbackMode
    existence_theorem: str = Field(min_length=1)
    runtime_support_status: RuntimeSupportStatus
    required_existence_assumptions: tuple[str, ...] = ()
    exactness_certificate_assumptions: tuple[str, ...] = ()
    equilibrium_concept_aliases: tuple[StrategicEquilibriumConcept, ...] = ()
    allowed_macro_preservation_types: tuple[AbstractionPreservationType, ...] = (
        AbstractionPreservationType.EXACT,
    )


_STRATEGIC_DEFAULT_EXACTNESS_CERTIFICATES: dict[StrategicGameClass, frozenset[str]] = {
    StrategicGameClass.CONCAVE_VI: frozenset(
        {"strong_monotonicity", "diagonal_strict_concavity", "unique_equilibrium"}
    ),
    StrategicGameClass.GNE_JOINTLY_CONVEX: frozenset(
        {
            "strong_monotonicity",
            "unique_variational_equilibrium",
            "jointly_convex_monotone_vi",
        }
    ),
}


_STRATEGIC_ADMISSIBILITY_REGISTRY: dict[
    tuple[StrategicGameClass, StrategicSolutionConcept],
    _StrategicAdmissibilityEntry,
] = {
    (
        StrategicGameClass.ZERO_SUM,
        StrategicSolutionConcept.MINIMAX,
    ): _StrategicAdmissibilityEntry(
        tractability_class=StrategicTractabilityClass.P,
        default_fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
        existence_theorem="minimax_value_exists",
        runtime_support_status=RuntimeSupportStatus.BLOCKED_UNSUPPORTED,
        equilibrium_concept_aliases=(StrategicEquilibriumConcept.MINIMAX_ZERO_SUM,),
        required_existence_assumptions=("zero_sum_payoffs", "finite_matrix_or_perfect_recall"),
    ),
    (
        StrategicGameClass.NORMAL_FORM_GENERAL_SUM,
        StrategicSolutionConcept.MIXED_NASH,
    ): _StrategicAdmissibilityEntry(
        tractability_class=StrategicTractabilityClass.PPAD,
        default_fallback_mode=StrategicFallbackMode.STRATEGIC_BOUNDS,
        existence_theorem="finite_mixed_nash_exists",
        runtime_support_status=RuntimeSupportStatus.BLOCKED_RESEARCH,
        equilibrium_concept_aliases=(
            StrategicEquilibriumConcept.NASH,
            StrategicEquilibriumConcept.MIXED_NASH_FINITE_GENERAL_SUM,
        ),
        required_existence_assumptions=("finite_game",),
    ),
    (
        StrategicGameClass.STACKELBERG_SINGLE_FOLLOWER,
        StrategicSolutionConcept.STACKELBERG_OPTIMISTIC,
    ): _StrategicAdmissibilityEntry(
        tractability_class=StrategicTractabilityClass.P,
        default_fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
        existence_theorem="single_follower_stackelberg_commitment_exists",
        runtime_support_status=RuntimeSupportStatus.SUPPORTED,
        equilibrium_concept_aliases=(
            StrategicEquilibriumConcept.STACKELBERG,
            StrategicEquilibriumConcept.STACKELBERG_SINGLE_FOLLOWER_OPTIMISTIC,
        ),
        default_tie_breaking_rule="optimistic_leader_favorable",
        required_existence_assumptions=("finite_action_space", "single_follower"),
    ),
    (
        StrategicGameClass.STACKELBERG_SINGLE_FOLLOWER,
        StrategicSolutionConcept.STACKELBERG_PESSIMISTIC,
    ): _StrategicAdmissibilityEntry(
        tractability_class=StrategicTractabilityClass.P,
        default_fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
        existence_theorem="single_follower_stackelberg_commitment_exists",
        runtime_support_status=RuntimeSupportStatus.BLOCKED_UNSUPPORTED,
        equilibrium_concept_aliases=(
            StrategicEquilibriumConcept.STACKELBERG_SINGLE_FOLLOWER_PESSIMISTIC,
        ),
        default_tie_breaking_rule="pessimistic_follower_favorable",
        required_existence_assumptions=("finite_action_space", "single_follower"),
    ),
    (
        StrategicGameClass.STACKELBERG_COMPLEX,
        StrategicSolutionConcept.STACKELBERG_OPTIMISTIC,
    ): _StrategicAdmissibilityEntry(
        tractability_class=StrategicTractabilityClass.NP_HARD,
        default_fallback_mode=StrategicFallbackMode.BLOCKED,
        existence_theorem="complex_stackelberg_requires_explicit_selection_rule",
        runtime_support_status=RuntimeSupportStatus.BLOCKED_RESEARCH,
        required_existence_assumptions=("follower_equilibrium_selection_rule",),
    ),
    (
        StrategicGameClass.STACKELBERG_COMPLEX,
        StrategicSolutionConcept.STACKELBERG_PESSIMISTIC,
    ): _StrategicAdmissibilityEntry(
        tractability_class=StrategicTractabilityClass.NP_HARD,
        default_fallback_mode=StrategicFallbackMode.BLOCKED,
        existence_theorem="complex_stackelberg_requires_explicit_selection_rule",
        runtime_support_status=RuntimeSupportStatus.BLOCKED_RESEARCH,
        required_existence_assumptions=("follower_equilibrium_selection_rule",),
    ),
    (
        StrategicGameClass.POTENTIAL_CONGESTION,
        StrategicSolutionConcept.PURE_NASH,
    ): _StrategicAdmissibilityEntry(
        tractability_class=StrategicTractabilityClass.PLS,
        default_fallback_mode=StrategicFallbackMode.STRATEGIC_BOUNDS,
        existence_theorem="potential_game_pure_nash_exists",
        runtime_support_status=RuntimeSupportStatus.BLOCKED_RESEARCH,
        equilibrium_concept_aliases=(StrategicEquilibriumConcept.PURE_NASH_POTENTIAL,),
        required_existence_assumptions=("exact_potential_or_congestion_game",),
    ),
    (
        StrategicGameClass.CONCAVE_VI,
        StrategicSolutionConcept.VARIATIONAL_EQUILIBRIUM,
    ): _StrategicAdmissibilityEntry(
        tractability_class=StrategicTractabilityClass.POLY_EPSILON,
        default_fallback_mode=StrategicFallbackMode.STRATEGIC_BOUNDS,
        existence_theorem="concave_game_equilibrium_exists",
        runtime_support_status=RuntimeSupportStatus.BLOCKED_UNSUPPORTED,
        equilibrium_concept_aliases=(StrategicEquilibriumConcept.VARIATIONAL_EQUILIBRIUM_MONOTONE,),
        required_existence_assumptions=(
            "compact_convex_strategy_sets",
            "continuous_payoffs",
            "concave_own_strategy",
            "monotone_vi",
        ),
    ),
    (
        StrategicGameClass.GNE_JOINTLY_CONVEX,
        StrategicSolutionConcept.VARIATIONAL_EQUILIBRIUM,
    ): _StrategicAdmissibilityEntry(
        tractability_class=StrategicTractabilityClass.POLY_EPSILON,
        default_fallback_mode=StrategicFallbackMode.STRATEGIC_BOUNDS,
        existence_theorem="jointly_convex_gne_exists",
        runtime_support_status=RuntimeSupportStatus.BLOCKED_UNSUPPORTED,
        equilibrium_concept_aliases=(StrategicEquilibriumConcept.GNE_JOINTLY_CONVEX,),
        required_existence_assumptions=(
            "shared_constraints_jointly_convex",
            "compact_convex_strategy_sets",
        ),
    ),
    (
        StrategicGameClass.GNE_NONCONVEX,
        StrategicSolutionConcept.VARIATIONAL_EQUILIBRIUM,
    ): _StrategicAdmissibilityEntry(
        tractability_class=StrategicTractabilityClass.GLOBAL_OPT,
        default_fallback_mode=StrategicFallbackMode.BLOCKED,
        existence_theorem="nonconvex_gne_requires_global_optimization_or_convexification",
        runtime_support_status=RuntimeSupportStatus.BLOCKED_RESEARCH,
        required_existence_assumptions=("nonconvex_or_mixed_integer_shared_constraints",),
    ),
    (
        StrategicGameClass.ANONYMOUS_AGGREGATIVE,
        StrategicSolutionConcept.EPSILON_NASH,
    ): _StrategicAdmissibilityEntry(
        tractability_class=StrategicTractabilityClass.POLY_EPSILON,
        default_fallback_mode=StrategicFallbackMode.MACRO_ABSTRACTED,
        existence_theorem="anonymous_game_ptas_or_macro_limit",
        runtime_support_status=RuntimeSupportStatus.SUPPORTED,
        equilibrium_concept_aliases=(StrategicEquilibriumConcept.EPSILON_NASH_ANONYMOUS,),
        required_existence_assumptions=("bounded_strategy_space",),
        macro_preservation_types=(
            AbstractionPreservationType.EXACT,
            AbstractionPreservationType.APPROXIMATE,
            AbstractionPreservationType.POLICY_VALUE_ONLY,
        ),
    ),
    (
        StrategicGameClass.SMALL_FINITE_BEST_RESPONSE,
        StrategicSolutionConcept.BEST_RESPONSE_FIXED_POINT,
    ): _StrategicAdmissibilityEntry(
        tractability_class=StrategicTractabilityClass.P,
        default_fallback_mode=StrategicFallbackMode.EXACT_EQUILIBRIUM,
        existence_theorem="finite_best_response_fixed_point_by_enumeration",
        runtime_support_status=RuntimeSupportStatus.SUPPORTED,
        equilibrium_concept_aliases=(StrategicEquilibriumConcept.BEST_RESPONSE_FIXED_POINT,),
        required_existence_assumptions=("finite_action_space", "finite_profile_enumeration"),
    ),
}


def _registry_entry(
    *,
    game_class: StrategicGameClass,
    solution_concept: StrategicSolutionConcept,
) -> _StrategicAdmissibilityEntry:
    key = (game_class, solution_concept)
    try:
        return _STRATEGIC_ADMISSIBILITY_REGISTRY[key]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported strategic admissibility pair: {game_class.value}/{solution_concept.value}"
        ) from exc


def _admissibility_record(
    *,
    game_class: StrategicGameClass,
    solution_concept: StrategicSolutionConcept,
) -> StrategicAdmissibilityRecord:
    entry = _registry_entry(game_class=game_class, solution_concept=solution_concept)
    return StrategicAdmissibilityRecord(
        game_class=game_class,
        solution_concept=solution_concept,
        tractability_class=entry.tractability_class,
        default_fallback_mode=entry.default_fallback_mode,
        existence_theorem=entry.existence_theorem,
        runtime_support_status=entry.runtime_support_status,
        required_existence_assumptions=entry.required_existence_assumptions,
        exactness_certificate_assumptions=tuple(
            sorted(_STRATEGIC_DEFAULT_EXACTNESS_CERTIFICATES.get(game_class, frozenset()))
        ),
        equilibrium_concept_aliases=entry.equilibrium_concept_aliases,
        allowed_macro_preservation_types=entry.macro_preservation_types,
    )


def strategic_admissibility_records() -> tuple[StrategicAdmissibilityRecord, ...]:
    """Return the Stage 6.1 strategic admissibility registry as serializable rows."""

    return tuple(
        _admissibility_record(game_class=game_class, solution_concept=solution_concept)
        for game_class, solution_concept in sorted(
            _STRATEGIC_ADMISSIBILITY_REGISTRY,
            key=lambda item: (item[0].value, item[1].value),
        )
    )


def strategic_admissibility_record_for(
    *,
    game_class: StrategicGameClass | str,
    solution_concept: StrategicSolutionConcept | str,
) -> StrategicAdmissibilityRecord:
    """Return the registry row for one `(game_class, solution_concept)` pair."""

    return _admissibility_record(
        game_class=StrategicGameClass(game_class),
        solution_concept=StrategicSolutionConcept(solution_concept),
    )


def _default_fallback_mode_for_descriptor_payload(
    *,
    game_class: StrategicGameClass,
    solution_concept: StrategicSolutionConcept,
    uniqueness_assumptions: tuple[str, ...],
) -> StrategicFallbackMode:
    entry = _registry_entry(game_class=game_class, solution_concept=solution_concept)
    exactness_certificates = _STRATEGIC_DEFAULT_EXACTNESS_CERTIFICATES.get(game_class, frozenset())
    if exactness_certificates and exactness_certificates.intersection(uniqueness_assumptions):
        return StrategicFallbackMode.EXACT_EQUILIBRIUM
    return entry.default_fallback_mode


def _descriptor_payload_from_legacy(
    value: StrategicEquilibriumConcept | str,
) -> dict[str, Any]:
    legacy = (
        value
        if isinstance(value, StrategicEquilibriumConcept)
        else StrategicEquilibriumConcept(value)
    )
    if legacy is StrategicEquilibriumConcept.MINIMAX_ZERO_SUM:
        game_class = StrategicGameClass.ZERO_SUM
        solution_concept = StrategicSolutionConcept.MINIMAX
        existence_assumptions = ("zero_sum_payoffs", "finite_matrix_or_perfect_recall")
        uniqueness_assumptions: tuple[str, ...] = ()
        tie_breaking_rule = None
        approximation_epsilon = None
    elif legacy in {
        StrategicEquilibriumConcept.NASH,
        StrategicEquilibriumConcept.MIXED_NASH_FINITE_GENERAL_SUM,
    }:
        game_class = StrategicGameClass.NORMAL_FORM_GENERAL_SUM
        solution_concept = StrategicSolutionConcept.MIXED_NASH
        existence_assumptions = ("finite_game",)
        uniqueness_assumptions = ()
        tie_breaking_rule = None
        approximation_epsilon = None
    elif legacy in {
        StrategicEquilibriumConcept.STACKELBERG,
        StrategicEquilibriumConcept.STACKELBERG_SINGLE_FOLLOWER_OPTIMISTIC,
    }:
        game_class = StrategicGameClass.STACKELBERG_SINGLE_FOLLOWER
        solution_concept = StrategicSolutionConcept.STACKELBERG_OPTIMISTIC
        existence_assumptions = ("finite_action_space", "single_follower")
        uniqueness_assumptions = ()
        tie_breaking_rule = "optimistic_leader_favorable"
        approximation_epsilon = None
    elif legacy is StrategicEquilibriumConcept.STACKELBERG_SINGLE_FOLLOWER_PESSIMISTIC:
        game_class = StrategicGameClass.STACKELBERG_SINGLE_FOLLOWER
        solution_concept = StrategicSolutionConcept.STACKELBERG_PESSIMISTIC
        existence_assumptions = ("finite_action_space", "single_follower")
        uniqueness_assumptions = ()
        tie_breaking_rule = "pessimistic_follower_favorable"
        approximation_epsilon = None
    elif legacy is StrategicEquilibriumConcept.PURE_NASH_POTENTIAL:
        game_class = StrategicGameClass.POTENTIAL_CONGESTION
        solution_concept = StrategicSolutionConcept.PURE_NASH
        existence_assumptions = ("exact_potential_or_congestion_game",)
        uniqueness_assumptions = ()
        tie_breaking_rule = None
        approximation_epsilon = None
    elif legacy is StrategicEquilibriumConcept.VARIATIONAL_EQUILIBRIUM_MONOTONE:
        game_class = StrategicGameClass.CONCAVE_VI
        solution_concept = StrategicSolutionConcept.VARIATIONAL_EQUILIBRIUM
        existence_assumptions = (
            "compact_convex_strategy_sets",
            "continuous_payoffs",
            "concave_own_strategy",
            "monotone_vi",
        )
        uniqueness_assumptions = ()
        tie_breaking_rule = None
        approximation_epsilon = None
    elif legacy is StrategicEquilibriumConcept.GNE_JOINTLY_CONVEX:
        game_class = StrategicGameClass.GNE_JOINTLY_CONVEX
        solution_concept = StrategicSolutionConcept.VARIATIONAL_EQUILIBRIUM
        existence_assumptions = (
            "shared_constraints_jointly_convex",
            "compact_convex_strategy_sets",
        )
        uniqueness_assumptions = ()
        tie_breaking_rule = None
        approximation_epsilon = None
    elif legacy is StrategicEquilibriumConcept.EPSILON_NASH_ANONYMOUS:
        game_class = StrategicGameClass.ANONYMOUS_AGGREGATIVE
        solution_concept = StrategicSolutionConcept.EPSILON_NASH
        existence_assumptions = ("bounded_strategy_space",)
        uniqueness_assumptions = ()
        tie_breaking_rule = None
        approximation_epsilon = 0.05
    else:
        game_class = StrategicGameClass.SMALL_FINITE_BEST_RESPONSE
        solution_concept = StrategicSolutionConcept.BEST_RESPONSE_FIXED_POINT
        existence_assumptions = ("finite_action_space", "finite_profile_enumeration")
        uniqueness_assumptions = ()
        tie_breaking_rule = None
        approximation_epsilon = None
    entry = _registry_entry(game_class=game_class, solution_concept=solution_concept)
    return {
        "game_class": game_class,
        "solution_concept": solution_concept,
        "tractability_class": entry.tractability_class,
        "existence_theorem": entry.existence_theorem,
        "existence_assumptions": existence_assumptions,
        "uniqueness_assumptions": uniqueness_assumptions,
        "approximation_epsilon": approximation_epsilon,
        "tie_breaking_rule": tie_breaking_rule,
        "default_fallback_mode": _default_fallback_mode_for_descriptor_payload(
            game_class=game_class,
            solution_concept=solution_concept,
            uniqueness_assumptions=uniqueness_assumptions,
        ),
    }


class StrategicEquilibriumDescriptor(BaseModel):
    """Typed strategic admissibility descriptor used by `StrategicSCM`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    game_class: StrategicGameClass
    solution_concept: StrategicSolutionConcept
    tractability_class: StrategicTractabilityClass
    existence_theorem: str = Field(min_length=1)
    existence_assumptions: tuple[str, ...] = ()
    uniqueness_assumptions: tuple[str, ...] = ()
    approximation_epsilon: float | None = None
    tie_breaking_rule: str | None = None
    default_fallback_mode: StrategicFallbackMode

    @model_validator(mode="before")
    @classmethod
    def _coerce_descriptor_payload(cls, value: Any) -> Any:
        if isinstance(value, StrategicEquilibriumDescriptor):
            return value.model_dump(mode="python")
        if isinstance(value, StrategicEquilibriumConcept):
            return _descriptor_payload_from_legacy(value)
        if isinstance(value, str):
            return _descriptor_payload_from_legacy(value)
        if not isinstance(value, Mapping):
            raise ValueError(
                "equilibrium_descriptor must be a mapping or a legacy equilibrium shorthand"
            )
        payload = dict(value)
        if "game_class" not in payload or "solution_concept" not in payload:
            raise ValueError("equilibrium_descriptor requires game_class and solution_concept")
        game_class = StrategicGameClass(payload["game_class"])
        solution_concept = StrategicSolutionConcept(payload["solution_concept"])
        entry = _registry_entry(game_class=game_class, solution_concept=solution_concept)
        uniqueness_assumptions = _normalize_string_tuple(
            payload.get("uniqueness_assumptions"),
            field_name="uniqueness_assumptions",
        )
        payload["tractability_class"] = payload.get("tractability_class", entry.tractability_class)
        payload["existence_theorem"] = payload.get("existence_theorem", entry.existence_theorem)
        payload["existence_assumptions"] = _normalize_string_tuple(
            payload.get("existence_assumptions"),
            field_name="existence_assumptions",
        )
        payload["uniqueness_assumptions"] = uniqueness_assumptions
        if payload.get("tie_breaking_rule") is None and entry.default_tie_breaking_rule is not None:
            payload["tie_breaking_rule"] = entry.default_tie_breaking_rule
        payload["default_fallback_mode"] = payload.get(
            "default_fallback_mode",
            _default_fallback_mode_for_descriptor_payload(
                game_class=game_class,
                solution_concept=solution_concept,
                uniqueness_assumptions=uniqueness_assumptions,
            ),
        )
        return payload

    @field_validator("existence_assumptions", "uniqueness_assumptions", mode="before")
    @classmethod
    def _validate_assumption_tuple(cls, value: Any, info: Any) -> tuple[str, ...]:
        return _normalize_string_tuple(value, field_name=str(info.field_name))

    @field_validator("approximation_epsilon", mode="before")
    @classmethod
    def _validate_approximation_epsilon(cls, value: Any) -> Any:
        if value is None:
            return None
        candidate = _ensure_finite(float(value), field_name="approximation_epsilon")
        if candidate <= 0.0:
            raise ValueError("approximation_epsilon must be strictly positive")
        return candidate

    @field_validator("tie_breaking_rule", mode="before")
    @classmethod
    def _validate_tie_breaking_rule(cls, value: Any) -> Any:
        if value is None:
            return None
        return _ensure_non_empty(str(value), field_name="tie_breaking_rule")

    @field_validator("existence_theorem", mode="before")
    @classmethod
    def _validate_existence_theorem(cls, value: Any) -> str:
        return _ensure_non_empty(str(value), field_name="existence_theorem")

    @model_validator(mode="after")
    def _validate_descriptor_contract(self) -> StrategicEquilibriumDescriptor:
        entry = _registry_entry(
            game_class=self.game_class,
            solution_concept=self.solution_concept,
        )
        expected_fallback = _default_fallback_mode_for_descriptor_payload(
            game_class=self.game_class,
            solution_concept=self.solution_concept,
            uniqueness_assumptions=self.uniqueness_assumptions,
        )
        if self.tractability_class is not entry.tractability_class:
            raise ValueError("tractability_class must match the admissibility registry")
        if self.existence_theorem != entry.existence_theorem:
            raise ValueError("existence_theorem must match the admissibility registry")
        if self.default_fallback_mode is not expected_fallback:
            raise ValueError("default_fallback_mode must match the admissibility registry")
        missing_assumptions = sorted(
            set(entry.required_existence_assumptions).difference(self.existence_assumptions)
        )
        if missing_assumptions:
            raise ValueError(
                "existence_assumptions must include registry-required assumptions: "
                + ", ".join(missing_assumptions)
            )
        if (
            self.solution_concept is StrategicSolutionConcept.EPSILON_NASH
            and self.approximation_epsilon is None
        ):
            raise ValueError("approximation_epsilon is required for epsilon_nash")
        return self

    @property
    def runtime_support_status(self) -> RuntimeSupportStatus:
        return _registry_entry(
            game_class=self.game_class,
            solution_concept=self.solution_concept,
        ).runtime_support_status

    @property
    def legacy_equilibrium_concept(self) -> StrategicEquilibriumConcept | None:
        aliases = _registry_entry(
            game_class=self.game_class,
            solution_concept=self.solution_concept,
        ).equilibrium_concept_aliases
        return aliases[0] if aliases else None

    @property
    def equilibrium_concept_aliases(self) -> tuple[StrategicEquilibriumConcept, ...]:
        return _registry_entry(
            game_class=self.game_class,
            solution_concept=self.solution_concept,
        ).equilibrium_concept_aliases

    @property
    def allowed_macro_preservation_types(self) -> tuple[AbstractionPreservationType, ...]:
        return _registry_entry(
            game_class=self.game_class,
            solution_concept=self.solution_concept,
        ).macro_preservation_types


class FiniteStrategicPayoffTable(BaseModel):
    """Dense normal-form payoff surface over finite action spaces."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    agent: str = Field(min_length=1)
    strategic_agents: tuple[str, ...]
    action_spaces: dict[str, tuple[str, ...]]
    payoffs: dict[str, float]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("agent", mode="before")
    @classmethod
    def _validate_agent(cls, value: Any) -> str:
        return _ensure_non_empty(str(value), field_name="agent")

    @model_validator(mode="after")
    def _validate_dense_surface(self) -> FiniteStrategicPayoffTable:
        if not self.strategic_agents:
            raise ValueError("strategic_agents must be non-empty")
        ensure_unique_ids(
            self.strategic_agents,
            key_fn=lambda item: item,
            label="strategic_agents",
        )
        if self.agent not in self.strategic_agents:
            raise ValueError("agent must be listed in strategic_agents")
        expected_agents = set(self.strategic_agents)
        if set(self.action_spaces) != expected_agents:
            raise ValueError("action_spaces must match strategic_agents exactly")

        normalized_action_spaces: dict[str, tuple[str, ...]] = {}
        for agent in self.strategic_agents:
            actions = tuple(
                _ensure_non_empty(action, field_name=f"action_spaces.{agent}")
                for action in self.action_spaces[agent]
            )
            if not actions:
                raise ValueError(f"action_spaces.{agent} must be non-empty")
            ensure_unique_ids(
                actions,
                key_fn=lambda item: item,
                label=f"action_spaces.{agent}",
            )
            normalized_action_spaces[agent] = actions

        expected_profiles = {
            encode_action_profile(
                dict(zip(self.strategic_agents, action_tuple, strict=True)),
                agent_order=self.strategic_agents,
            )
            for action_tuple in itertools.product(
                *(normalized_action_spaces[agent] for agent in self.strategic_agents)
            )
        }
        observed_profiles = set(self.payoffs)
        missing = sorted(expected_profiles - observed_profiles)
        extra = sorted(observed_profiles - expected_profiles)
        if missing or extra:
            raise ValueError(
                f"payoffs must define a dense normal-form table; missing={missing}, extra={extra}"
            )
        for key, value in self.payoffs.items():
            decode_action_profile(key, agent_order=self.strategic_agents)
            _ensure_finite(value, field_name=f"payoffs.{key}")
        return self


class StrategicSCM(BaseModel):
    """Strategic augmentation of a causal policy rule plus admissibility metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.1", pattern=r"^\d+\.\d+$")
    base_graph_ref: ArtifactRefModel
    strategic_agents: tuple[str, ...]
    utility_refs: dict[str, StrategicPayoffTableRef]
    macro_utility_refs: dict[str, StrategicPayoffTableRef] | None = None
    policy_rule_ref: ArtifactRefModel
    equilibrium_concept: StrategicEquilibriumConcept | None = None
    equilibrium_descriptor: StrategicEquilibriumDescriptor | None = None
    compute_budget: ComputeBudget = Field(default_factory=ComputeBudget)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _normalize_equilibrium_spec(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        payload = dict(value)
        raw_concept = payload.get("equilibrium_concept")
        raw_descriptor = payload.get("equilibrium_descriptor")
        if raw_concept is None and raw_descriptor is None:
            raise ValueError("either equilibrium_concept or equilibrium_descriptor is required")

        normalized_concept = (
            None
            if raw_concept is None
            else (
                raw_concept
                if isinstance(raw_concept, StrategicEquilibriumConcept)
                else StrategicEquilibriumConcept(raw_concept)
            )
        )

        if raw_descriptor is None:
            if normalized_concept is None:
                raise ValueError(
                    "equilibrium_descriptor is required when equilibrium_concept is omitted"
                )
            descriptor = StrategicEquilibriumDescriptor.model_validate(normalized_concept)
        else:
            descriptor = StrategicEquilibriumDescriptor.model_validate(raw_descriptor)

        aliases = descriptor.equilibrium_concept_aliases
        if normalized_concept is not None and aliases and normalized_concept not in aliases:
            raise ValueError(
                "equilibrium_concept must agree with equilibrium_descriptor when both are provided"
            )

        payload["equilibrium_concept"] = normalized_concept or descriptor.legacy_equilibrium_concept
        payload["equilibrium_descriptor"] = descriptor.model_dump(mode="python")
        return payload

    @model_validator(mode="after")
    def _validate_contract(self) -> StrategicSCM:
        _validate_artifact_ref(self.base_graph_ref, field_name="base_graph_ref")
        _validate_artifact_ref(self.policy_rule_ref, field_name="policy_rule_ref")
        if not self.strategic_agents:
            raise ValueError("strategic_agents must be non-empty")
        ensure_unique_ids(
            self.strategic_agents,
            key_fn=lambda item: item,
            label="strategic_agents",
        )
        if set(self.utility_refs) != set(self.strategic_agents):
            raise ValueError("utility_refs keys must match strategic_agents exactly")
        for agent, ref in self.utility_refs.items():
            _ensure_non_empty(agent, field_name="utility_refs.agent")
            _validate_artifact_ref(ref, field_name=f"utility_refs.{agent}")
        if self.macro_utility_refs is not None:
            if set(self.macro_utility_refs) != set(self.strategic_agents):
                raise ValueError("macro_utility_refs keys must match strategic_agents exactly")
            for agent, ref in self.macro_utility_refs.items():
                _ensure_non_empty(agent, field_name="macro_utility_refs.agent")
                _validate_artifact_ref(ref, field_name=f"macro_utility_refs.{agent}")
        if self.equilibrium_descriptor is None:
            raise ValueError("equilibrium_descriptor must be normalized before validation")
        return self

    @property
    def runtime_blockers(self) -> tuple[str, ...]:
        descriptor = self.equilibrium_descriptor
        if descriptor is None:
            return ("missing_equilibrium_descriptor",)
        if descriptor.runtime_support_status is RuntimeSupportStatus.BLOCKED_RESEARCH:
            if StrategicEquilibriumConcept.NASH in descriptor.equilibrium_concept_aliases:
                return ("research_gated_equilibrium_concept",)
            return ("research_gated_game_class",)
        if descriptor.runtime_support_status is RuntimeSupportStatus.BLOCKED_UNSUPPORTED:
            return ("unsupported_game_class_runtime",)
        return ()

    @property
    def runtime_support_status(self) -> RuntimeSupportStatus:
        if self.equilibrium_descriptor is None:
            return RuntimeSupportStatus.BLOCKED_UNSUPPORTED
        return self.equilibrium_descriptor.runtime_support_status

    @property
    def runtime_eligible(self) -> bool:
        return self.runtime_support_status is RuntimeSupportStatus.SUPPORTED

    @property
    def default_fallback_mode(self) -> StrategicFallbackMode:
        if self.equilibrium_descriptor is None:
            return StrategicFallbackMode.BLOCKED
        return self.equilibrium_descriptor.default_fallback_mode

    @property
    def allowed_macro_preservation_types(self) -> tuple[AbstractionPreservationType, ...]:
        if self.equilibrium_descriptor is None:
            return (AbstractionPreservationType.EXACT,)
        return self.equilibrium_descriptor.allowed_macro_preservation_types


class StrategicClosureSummary(BaseModel):
    """Persisted strategic fallback / equilibrium closure summary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.1", pattern=r"^\d+\.\d+$")
    fallback_mode: StrategicFallbackMode
    equilibrium_concept: StrategicEquilibriumConcept | None = None
    equilibrium_descriptor: StrategicEquilibriumDescriptor | None = None
    equilibrium_selection_dependence: str = Field(min_length=1)
    profile_count: int = Field(default=0, ge=0)
    equilibrium_count: int = Field(default=0, ge=0)
    blocked_reason: str | None = None
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "equilibrium_selection_dependence",
        "blocked_reason",
        mode="before",
    )
    @classmethod
    def _validate_strings(cls, value: Any, info: Any) -> Any:
        if value is None:
            return None
        return _ensure_non_empty(str(value), field_name=str(info.field_name))


class EquilibriumSetSummary(BaseModel):
    """Persisted equilibrium surface disclosure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    equilibrium_profiles: tuple[dict[str, str], ...] = ()
    equilibrium_count: int = Field(default=0, ge=0)
    multiplicity_note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("multiplicity_note", mode="before")
    @classmethod
    def _validate_multiplicity_note(cls, value: Any) -> Any:
        if value is None:
            return None
        return _ensure_non_empty(str(value), field_name="multiplicity_note")

    @model_validator(mode="after")
    def _validate_profiles(self) -> EquilibriumSetSummary:
        if self.equilibrium_count != len(self.equilibrium_profiles):
            raise ValueError("equilibrium_count must match equilibrium_profiles length")
        return self


class EquilibriumSelectionSummary(BaseModel):
    """Persisted selected equilibrium disclosure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    selected_equilibrium: dict[str, str]
    equilibrium_selection_dependence: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("equilibrium_selection_dependence", mode="before")
    @classmethod
    def _validate_selection_dependence(cls, value: Any) -> str:
        return _ensure_non_empty(str(value), field_name="equilibrium_selection_dependence")

    @model_validator(mode="after")
    def _validate_selected_equilibrium(self) -> EquilibriumSelectionSummary:
        if not self.selected_equilibrium:
            raise ValueError("selected_equilibrium must be non-empty")
        for agent, action in self.selected_equilibrium.items():
            _ensure_non_empty(agent, field_name="selected_equilibrium.agent")
            _ensure_non_empty(action, field_name="selected_equilibrium.action")
        return self


class PerformativeLoopCertificate(BaseModel):
    """Typed certificate describing performative-loop convergence or instability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_scope: PerformativeLoopAnalysisScope = PerformativeLoopAnalysisScope.SINGLE_STEP_ONLY
    proof_family: PerformativeLoopProofFamily | None = None
    stability_status: PerformativeLoopStabilityStatus | None = None
    reason_code: PerformativeInstabilityReason | None = None
    contraction_upper_bound: float | None = None
    local_spectral_radius_estimate: float | None = None
    witness_strength: PerformativeLoopWitnessStrength | None = None
    simulation_horizon: int | None = Field(default=None, ge=1)
    detected_cycle_period: int | None = Field(default=None, ge=2)
    transient_gain_upper: float | None = None
    convergence_rate_upper: float | None = None
    iterations_to_delta_bound: int | None = Field(default=None, ge=0)
    hardness_flag: bool = False
    recommended_action: PerformativeLoopRecommendedAction | None = None
    human_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_certificate_values(self) -> PerformativeLoopCertificate:
        for field_name in (
            "contraction_upper_bound",
            "local_spectral_radius_estimate",
            "transient_gain_upper",
            "convergence_rate_upper",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _ensure_finite(value, field_name=field_name)
        if self.human_summary is not None:
            _ensure_non_empty(self.human_summary, field_name="human_summary")
        return self


class PerformativeShiftSummary(PerformativeLoopCertificate):
    """Persisted strategic performative shift disclosure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.1", pattern=r"^\d+\.\d+$")
    performative_shift: float | None = None
    baseline_policy_value: float | None = None
    post_adaptation_policy_value: float | None = None

    @model_validator(mode="after")
    def _validate_shift_values(self) -> PerformativeShiftSummary:
        if self.performative_shift is not None:
            _ensure_finite(self.performative_shift, field_name="performative_shift")
        if self.baseline_policy_value is not None:
            _ensure_finite(self.baseline_policy_value, field_name="baseline_policy_value")
        if self.post_adaptation_policy_value is not None:
            _ensure_finite(
                self.post_adaptation_policy_value,
                field_name="post_adaptation_policy_value",
            )
        return self


class MeanFieldInterventionKind(str, Enum):
    """How an SCM intervention perturbs a mean-field game."""

    COEFFICIENT = "coefficient"
    DISTRIBUTIONAL = "distributional"
    MIXED = "mixed"


class MeanFieldModelClass(str, Enum):
    """Restricted mean-field-game family disclosed by the certificate."""

    FIRST_ORDER = "first_order"
    SECOND_ORDER = "second_order"
    COMMON_NOISE = "common_noise"
    CONTROLS = "controls"


class MeanFieldMonotonicityType(str, Enum):
    """Well-posedness witness family for the perturbed MFG."""

    LASRY_LIONS = "lasry_lions"
    DISPLACEMENT = "displacement"
    STABLE_LINEARIZATION = "stable_linearization"


class MeanFieldUniquenessStatus(str, Enum):
    """Whether the post-intervention equilibrium is unique or branch-dependent."""

    UNIQUE = "unique"
    MULTIPLE = "multiple"
    LOCAL_STABLE_BRANCH = "local_stable_branch"


class MeanFieldGraphSemantics(str, Enum):
    """Graph semantics used for identification against an MFG background."""

    D_SEPARATION = "d_separation"
    SIGMA_SEPARATION = "sigma_separation"
    LOCAL_INDEPENDENCE = "local_independence"


class MeanFieldPositivityStatus(str, Enum):
    """Overlap strength for the intervened policy kernel."""

    VERIFIED = "verified"
    WEAK = "weak"
    FAILED = "failed"


class MeanFieldSelectionRule(str, Enum):
    """Equilibrium-selection rule disclosed when the MFG is non-unique."""

    NONE = "none"
    STABLE_BRANCH = "stable_branch"
    FINITE_PLAYER_LIMIT = "finite_player_limit"
    USER_DECLARED = "user_declared"


class MeanFieldStabilityBoundType(str, Enum):
    """Family of convergence certificate attached to the FP evolution."""

    ERGODIC_EXPONENTIAL = "ergodic_exponential"
    FINITE_HORIZON_LIPSCHITZ = "finite_horizon_lipschitz"
    NONE = "none"


class MeanFieldStabilityMetric(str, Enum):
    """Metric used in the convergence certificate."""

    W1 = "W1"
    L2 = "L2"
    DUAL_NORM = "dual_norm"


class MeanFieldPerturbationChannel(str, Enum):
    """Structural location in the HJB-FP system that the policy perturbs."""

    DRIFT = "drift"
    DIFFUSION = "diffusion"
    RUNNING_COST = "running_cost"
    TERMINAL_PAYOFF = "terminal_payoff"
    INITIAL_DISTRIBUTION = "initial_distribution"
    ENTRY_FLOW = "entry_flow"
    POLICY_KERNEL = "policy_kernel"


class MeanFieldNumericsScheme(str, Enum):
    """Discretization family used for reproducible MFG numerics."""

    FINITE_DIFFERENCE = "finite_difference"
    SEMI_IMPLICIT_FINITE_DIFFERENCE = "semi_implicit_finite_difference"
    SEMI_LAGRANGIAN = "semi_lagrangian"
    PARTICLE_METHOD = "particle_method"


class MeanFieldFixedPointMethod(str, Enum):
    """Fixed-point routine used to couple the HJB and FP solves."""

    FORWARD_BACKWARD_SWEEP = "forward_backward_sweep"
    POLICY_ITERATION = "policy_iteration"
    NEWTON_LINEARIZATION = "newton_linearization"


class MeanFieldRuntimeMode(str, Enum):
    """Fabric execution posture for replayable macro-simulation runs."""

    RECORD = "record"
    REPLAY = "replay"


class MeanFieldPerturbationSpec(BaseModel):
    """Compile a causal intervention into an equilibrium-resolving MFG perturbation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    source_intervention_type: InterventionType
    intervention_kind: MeanFieldInterventionKind
    source_intervention_ref: ArtifactRefModel | None = None
    baseline_policy_ref: ArtifactRefModel | None = None
    causal_background_assumption: str = Field("endogenous_mean_field", min_length=1)
    representative_agent_channels: tuple[MeanFieldPerturbationChannel, ...] = ()
    population_channels: tuple[MeanFieldPerturbationChannel, ...] = ()
    requires_equilibrium_resolve: bool = True
    preserves_baseline_initial_measure: bool = True
    policy_kernel_overlap_required: bool = False
    notes: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("causal_background_assumption", mode="before")
    @classmethod
    def _validate_causal_background_assumption(cls, value: Any) -> str:
        candidate = _ensure_non_empty(str(value), field_name="causal_background_assumption")
        if candidate != "endogenous_mean_field":
            raise ValueError("causal_background_assumption must be 'endogenous_mean_field'")
        return candidate

    @field_validator("notes", mode="before")
    @classmethod
    def _validate_notes(cls, value: Any) -> tuple[str, ...]:
        return _normalize_string_tuple(value, field_name="notes")

    @model_validator(mode="after")
    def _validate_perturbation_spec(self) -> MeanFieldPerturbationSpec:
        if self.source_intervention_ref is not None:
            _validate_artifact_ref(
                self.source_intervention_ref,
                field_name="source_intervention_ref",
            )
        if self.baseline_policy_ref is not None:
            _validate_artifact_ref(self.baseline_policy_ref, field_name="baseline_policy_ref")
        _validate_unique_enum_tuple(
            self.representative_agent_channels,
            field_name="representative_agent_channels",
        )
        _validate_unique_enum_tuple(
            self.population_channels,
            field_name="population_channels",
        )
        if not self.requires_equilibrium_resolve:
            raise ValueError("requires_equilibrium_resolve must remain true for MFG perturbations")
        if self.intervention_kind is MeanFieldInterventionKind.COEFFICIENT:
            if not self.representative_agent_channels:
                raise ValueError(
                    "representative_agent_channels are required for coefficient interventions"
                )
            if self.population_channels:
                raise ValueError(
                    "population_channels must be omitted for coefficient interventions"
                )
        elif self.intervention_kind is MeanFieldInterventionKind.DISTRIBUTIONAL:
            if not self.population_channels:
                raise ValueError(
                    "population_channels are required for distributional interventions"
                )
            if self.representative_agent_channels:
                raise ValueError(
                    "representative_agent_channels must be omitted for distributional interventions"
                )
        else:
            if not self.representative_agent_channels or not self.population_channels:
                raise ValueError(
                    "mixed interventions require both representative_agent_channels and population_channels"
                )
        if self.policy_kernel_overlap_required and (
            MeanFieldPerturbationChannel.POLICY_KERNEL not in self.population_channels
        ):
            raise ValueError(
                "policy_kernel_overlap_required requires policy_kernel in population_channels"
            )
        return self


class MeanFieldMacroSimulationConfig(BaseModel):
    """Reproducible Fabric/Foundry numerics config for one MFG solve."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    population_measure_snapshot_ref: ArtifactRefModel
    coefficient_field_ref: ArtifactRefModel
    policy_kernel_ref: ArtifactRefModel | None = None
    numerics_scheme: MeanFieldNumericsScheme = (
        MeanFieldNumericsScheme.SEMI_IMPLICIT_FINITE_DIFFERENCE
    )
    fixed_point_method: MeanFieldFixedPointMethod = MeanFieldFixedPointMethod.FORWARD_BACKWARD_SWEEP
    runtime_mode: MeanFieldRuntimeMode = MeanFieldRuntimeMode.REPLAY
    time_horizon: float | None = None
    time_steps: int | None = None
    state_grid_shape: tuple[int, ...] = ()
    max_fixed_point_iterations: int = Field(default=200, ge=1)
    residual_tolerance: float = Field(default=1.0e-8, gt=0.0)
    mass_conservation_tolerance: float = Field(default=1.0e-8, gt=0.0)
    warm_start_from_baseline: bool = True
    publish_master_equation: bool = False
    publish_solver_residual: bool = True
    publish_mass_conservation: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("time_horizon", mode="before")
    @classmethod
    def _coerce_optional_time_horizon(cls, value: Any) -> Any:
        if value is None:
            return None
        casted = _ensure_finite(float(value), field_name="time_horizon")
        if casted <= 0.0:
            raise ValueError("time_horizon must be > 0")
        return casted

    @field_validator("state_grid_shape", mode="before")
    @classmethod
    def _validate_state_grid_shape(cls, value: Any) -> tuple[int, ...]:
        if value in (None, (), []):
            return ()
        if not isinstance(value, (tuple, list)):
            raise ValueError("state_grid_shape must be a tuple/list of positive integers")
        normalized = tuple(int(item) for item in value)
        if any(item <= 0 for item in normalized):
            raise ValueError("state_grid_shape entries must be > 0")
        return normalized

    @model_validator(mode="after")
    def _validate_macro_simulation_config(self) -> MeanFieldMacroSimulationConfig:
        _validate_artifact_ref(
            self.population_measure_snapshot_ref,
            field_name="population_measure_snapshot_ref",
        )
        _validate_artifact_ref(self.coefficient_field_ref, field_name="coefficient_field_ref")
        if self.policy_kernel_ref is not None:
            _validate_artifact_ref(self.policy_kernel_ref, field_name="policy_kernel_ref")
        if self.time_steps is not None and self.time_steps <= 0:
            raise ValueError("time_steps must be > 0")
        return self


def compile_intervention_spec_to_mean_field_perturbation(
    intervention_spec: InterventionSpec,
    *,
    source_intervention_ref: ArtifactRefModel | None = None,
    baseline_policy_ref: ArtifactRefModel | None = None,
    metadata: dict[str, Any] | None = None,
) -> MeanFieldPerturbationSpec:
    """Compile a causal intervention payload into the MFG perturbation contract."""

    notes = [
        "mean_field_is_endogenous_macro_state",
        "post_intervention_outcome_requires_new_fixed_point",
    ]
    if intervention_spec.type is InterventionType.ATOMIC:
        notes.append("deterministic_policy_replacement")
        return MeanFieldPerturbationSpec(
            source_intervention_type=intervention_spec.type,
            intervention_kind=MeanFieldInterventionKind.COEFFICIENT,
            source_intervention_ref=source_intervention_ref,
            baseline_policy_ref=baseline_policy_ref,
            representative_agent_channels=(
                MeanFieldPerturbationChannel.RUNNING_COST,
                MeanFieldPerturbationChannel.TERMINAL_PAYOFF,
            ),
            preserves_baseline_initial_measure=True,
            notes=tuple(notes),
            metadata=dict(metadata or {}),
        )
    if intervention_spec.type is InterventionType.SHIFTED:
        notes.append("comparative_statics_policy_shift")
        return MeanFieldPerturbationSpec(
            source_intervention_type=intervention_spec.type,
            intervention_kind=MeanFieldInterventionKind.COEFFICIENT,
            source_intervention_ref=source_intervention_ref,
            baseline_policy_ref=baseline_policy_ref,
            representative_agent_channels=(
                MeanFieldPerturbationChannel.RUNNING_COST,
                MeanFieldPerturbationChannel.TERMINAL_PAYOFF,
            ),
            preserves_baseline_initial_measure=True,
            notes=tuple(notes),
            metadata=dict(metadata or {}),
        )
    if intervention_spec.type is InterventionType.TRUNCATED:
        notes.append("support_truncation_reweights_population_mass")
        return MeanFieldPerturbationSpec(
            source_intervention_type=intervention_spec.type,
            intervention_kind=MeanFieldInterventionKind.MIXED,
            source_intervention_ref=source_intervention_ref,
            baseline_policy_ref=baseline_policy_ref,
            representative_agent_channels=(MeanFieldPerturbationChannel.RUNNING_COST,),
            population_channels=(
                MeanFieldPerturbationChannel.POLICY_KERNEL,
                MeanFieldPerturbationChannel.INITIAL_DISTRIBUTION,
            ),
            preserves_baseline_initial_measure=False,
            policy_kernel_overlap_required=True,
            notes=tuple(notes),
            metadata=dict(metadata or {}),
        )
    notes.append("stochastic_policy_kernel_shift")
    return MeanFieldPerturbationSpec(
        source_intervention_type=intervention_spec.type,
        intervention_kind=MeanFieldInterventionKind.DISTRIBUTIONAL,
        source_intervention_ref=source_intervention_ref,
        baseline_policy_ref=baseline_policy_ref,
        population_channels=(
            MeanFieldPerturbationChannel.POLICY_KERNEL,
            MeanFieldPerturbationChannel.INITIAL_DISTRIBUTION,
        ),
        preserves_baseline_initial_measure=False,
        policy_kernel_overlap_required=True,
        notes=tuple(notes),
        metadata=dict(metadata or {}),
    )


class MeanFieldWellPosednessSummary(BaseModel):
    """Existence and uniqueness disclosure for the perturbed mean-field game."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scm_solvability_ref: ArtifactRefModel
    monotonicity_type: MeanFieldMonotonicityType
    convexity_verified: bool = False
    regularity_scope: str = Field(min_length=1)
    uniqueness_status: MeanFieldUniquenessStatus

    @field_validator("regularity_scope", mode="before")
    @classmethod
    def _validate_regularity_scope(cls, value: Any) -> str:
        return _ensure_non_empty(str(value), field_name="regularity_scope")

    @model_validator(mode="after")
    def _validate_well_posedness(self) -> MeanFieldWellPosednessSummary:
        _validate_artifact_ref(self.scm_solvability_ref, field_name="scm_solvability_ref")
        return self


class MeanFieldIdentificationSummary(BaseModel):
    """Identification-side disclosure for MFG-based policy effects."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    graph_semantics: MeanFieldGraphSemantics
    positivity_status: MeanFieldPositivityStatus
    selection_rule: MeanFieldSelectionRule = MeanFieldSelectionRule.NONE
    identified_estimands: tuple[str, ...] = ()

    @field_validator("identified_estimands", mode="before")
    @classmethod
    def _validate_identified_estimands(cls, value: Any) -> tuple[str, ...]:
        return _normalize_string_tuple(value, field_name="identified_estimands")

    @model_validator(mode="after")
    def _validate_identification_summary(self) -> MeanFieldIdentificationSummary:
        if self.positivity_status is MeanFieldPositivityStatus.FAILED and self.identified_estimands:
            raise ValueError("identified_estimands must be omitted when positivity_status=failed")
        return self


class MeanFieldEquilibriumSolutionSummary(BaseModel):
    """Numerical artifacts that witness one solved HJB-FP equilibrium."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hjb_solution_ref: ArtifactRefModel | None = None
    fp_solution_ref: ArtifactRefModel | None = None
    master_equation_ref: ArtifactRefModel | None = None
    solver_residual_ref: ArtifactRefModel | None = None
    mass_conservation_ref: ArtifactRefModel | None = None

    @model_validator(mode="after")
    def _validate_solution_refs(self) -> MeanFieldEquilibriumSolutionSummary:
        for field_name in (
            "hjb_solution_ref",
            "fp_solution_ref",
            "master_equation_ref",
            "solver_residual_ref",
            "mass_conservation_ref",
        ):
            ref = getattr(self, field_name)
            if ref is not None:
                _validate_artifact_ref(ref, field_name=field_name)
        return self


class MeanFieldSolverResidualReport(BaseModel):
    """Numerical residual evidence for a discrete mean-field fixed point."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    solver_family: str = Field(
        default="policy.agent_sim.mean_field_equilibrium@1.0.0",
        min_length=1,
    )
    converged: bool
    iterations: int = Field(ge=0)
    tolerance: float = Field(gt=0.0)
    value_residual_max_abs: float = Field(ge=0.0)
    policy_fixed_point_residual_max_abs: float = Field(ge=0.0)
    residual_threshold: float = Field(gt=0.0)
    within_tolerance: bool
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_solver_residual_report(self) -> MeanFieldSolverResidualReport:
        for field_name in (
            "tolerance",
            "value_residual_max_abs",
            "policy_fixed_point_residual_max_abs",
            "residual_threshold",
        ):
            _ensure_finite(getattr(self, field_name), field_name=field_name)
        expected_within_tolerance = (
            bool(self.converged)
            and self.value_residual_max_abs <= self.residual_threshold
            and self.policy_fixed_point_residual_max_abs <= self.residual_threshold
        )
        if self.within_tolerance != expected_within_tolerance:
            raise ValueError("within_tolerance must match solver residual threshold checks")
        return self


class MeanFieldMassConservationReport(BaseModel):
    """Mass and stationarity evidence for the solved mean-field population law."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    solver_family: str = Field(
        default="policy.agent_sim.mean_field_equilibrium@1.0.0",
        min_length=1,
    )
    mass_sum: float
    mass_sum_error: float = Field(ge=0.0)
    min_mass: float
    stationary_distribution_residual_max_abs: float = Field(ge=0.0)
    residual_threshold: float = Field(gt=0.0)
    mass_threshold: float = Field(gt=0.0)
    within_tolerance: bool
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_mass_conservation_report(self) -> MeanFieldMassConservationReport:
        for field_name in (
            "mass_sum",
            "mass_sum_error",
            "min_mass",
            "stationary_distribution_residual_max_abs",
            "residual_threshold",
            "mass_threshold",
        ):
            _ensure_finite(getattr(self, field_name), field_name=field_name)
        expected_within_tolerance = (
            self.mass_sum_error <= self.mass_threshold
            and self.min_mass >= -self.mass_threshold
            and self.stationary_distribution_residual_max_abs <= self.residual_threshold
        )
        if self.within_tolerance != expected_within_tolerance:
            raise ValueError("within_tolerance must match mass conservation threshold checks")
        return self


class MeanFieldStabilitySummary(BaseModel):
    """Convergence disclosure for the post-intervention Fokker-Planck flow."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    bound_type: MeanFieldStabilityBoundType = MeanFieldStabilityBoundType.NONE
    constant_c: float | None = Field(
        default=None,
        alias="constant_C",
        serialization_alias="constant_C",
    )
    decay_rate: float | None = None
    metric: MeanFieldStabilityMetric | None = None

    @model_validator(mode="after")
    def _validate_stability_summary(self) -> MeanFieldStabilitySummary:
        if self.constant_c is not None:
            _ensure_finite(self.constant_c, field_name="constant_C")
            if self.constant_c < 0.0:
                raise ValueError("constant_C must be >= 0")
        if self.decay_rate is not None:
            _ensure_finite(self.decay_rate, field_name="decay_rate")
            if self.decay_rate < 0.0:
                raise ValueError("decay_rate must be >= 0")
        if self.bound_type is MeanFieldStabilityBoundType.NONE:
            if (
                self.constant_c is not None
                or self.decay_rate is not None
                or self.metric is not None
            ):
                raise ValueError(
                    "constant_C, decay_rate, and metric must be omitted when bound_type=none"
                )
            return self
        if self.constant_c is None or self.metric is None:
            raise ValueError("constant_C and metric are required for nontrivial stability bounds")
        if (
            self.bound_type is MeanFieldStabilityBoundType.ERGODIC_EXPONENTIAL
            and self.decay_rate is None
        ):
            raise ValueError("decay_rate is required for ergodic_exponential bounds")
        return self


class MeanFieldProvenanceSummary(BaseModel):
    """Fabric/data-plane provenance required to reproduce an MFG solve."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    data_snapshot_ref: ArtifactRefModel | None = None
    calibration_bundle_ref: ArtifactRefModel | None = None
    numerics_config_ref: ArtifactRefModel | None = None

    @model_validator(mode="after")
    def _validate_provenance_refs(self) -> MeanFieldProvenanceSummary:
        for field_name in (
            "data_snapshot_ref",
            "calibration_bundle_ref",
            "numerics_config_ref",
        ):
            ref = getattr(self, field_name)
            if ref is not None:
                _validate_artifact_ref(ref, field_name=field_name)
        return self


class MeanFieldSolveInput(BaseModel):
    """Executable mean-field runtime contract for anonymous-aggregative strategic solves."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    reward_matrix: tuple[tuple[float, ...], ...]
    transition_tensor: tuple[tuple[tuple[float, ...], ...], ...]
    congestion_costs: tuple[float, ...] = ()
    intervention_spec: InterventionSpec
    intervention_spec_ref: ArtifactRefModel
    baseline_policy_ref: ArtifactRefModel | None = None
    mean_field_model_class: MeanFieldModelClass
    well_posedness: MeanFieldWellPosednessSummary
    identification: MeanFieldIdentificationSummary
    stability: MeanFieldStabilitySummary = Field(default_factory=MeanFieldStabilitySummary)
    provenance: MeanFieldProvenanceSummary | None = None
    macro_simulation_config: MeanFieldMacroSimulationConfig | None = None
    discount: float = Field(default=0.95, gt=0.0, lt=1.0)
    temperature: float = Field(default=0.5, gt=0.0)
    max_iter: int = Field(default=200, ge=1)
    tol: float = Field(default=1.0e-8, gt=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("reward_matrix", mode="before")
    @classmethod
    def _normalize_reward_matrix(
        cls,
        value: Any,
    ) -> tuple[tuple[float, ...], ...]:
        if not isinstance(value, (tuple, list)) or not value:
            raise ValueError("reward_matrix must be a non-empty matrix")
        normalized: list[tuple[float, ...]] = []
        width: int | None = None
        for row_index, row in enumerate(value):
            if not isinstance(row, (tuple, list)) or not row:
                raise ValueError("reward_matrix rows must be non-empty sequences")
            casted_row = tuple(
                _ensure_finite(
                    float(cell),
                    field_name=f"reward_matrix[{row_index}]",
                )
                for cell in row
            )
            if width is None:
                width = len(casted_row)
            elif len(casted_row) != width:
                raise ValueError("reward_matrix rows must have equal length")
            normalized.append(casted_row)
        return tuple(normalized)

    @field_validator("transition_tensor", mode="before")
    @classmethod
    def _normalize_transition_tensor(
        cls,
        value: Any,
    ) -> tuple[tuple[tuple[float, ...], ...], ...]:
        if not isinstance(value, (tuple, list)) or not value:
            raise ValueError("transition_tensor must be a non-empty rank-3 tensor")
        normalized_tensor: list[tuple[tuple[float, ...], ...]] = []
        for action_index, matrix in enumerate(value):
            if not isinstance(matrix, (tuple, list)) or not matrix:
                raise ValueError("transition_tensor action slices must be non-empty matrices")
            normalized_matrix: list[tuple[float, ...]] = []
            width: int | None = None
            for row_index, row in enumerate(matrix):
                if not isinstance(row, (tuple, list)) or not row:
                    raise ValueError("transition_tensor rows must be non-empty sequences")
                casted_row = tuple(
                    _ensure_finite(
                        float(cell),
                        field_name=f"transition_tensor[{action_index}][{row_index}]",
                    )
                    for cell in row
                )
                if width is None:
                    width = len(casted_row)
                elif len(casted_row) != width:
                    raise ValueError("transition_tensor rows must have equal length")
                normalized_matrix.append(casted_row)
            normalized_tensor.append(tuple(normalized_matrix))
        return tuple(normalized_tensor)

    @field_validator("congestion_costs", mode="before")
    @classmethod
    def _normalize_congestion_costs(
        cls,
        value: Any,
    ) -> tuple[float, ...]:
        if value in (None, (), []):
            return ()
        if not isinstance(value, (tuple, list)):
            raise ValueError("congestion_costs must be a vector")
        return tuple(_ensure_finite(float(cell), field_name="congestion_costs") for cell in value)

    @model_validator(mode="after")
    def _validate_mean_field_solve_input(self) -> MeanFieldSolveInput:
        _validate_artifact_ref(
            self.intervention_spec_ref,
            field_name="intervention_spec_ref",
        )
        if self.baseline_policy_ref is not None:
            _validate_artifact_ref(
                self.baseline_policy_ref,
                field_name="baseline_policy_ref",
            )
        n_states = len(self.reward_matrix)
        n_actions = len(self.reward_matrix[0]) if self.reward_matrix else 0
        if n_states == 0 or n_actions == 0:
            raise ValueError("reward_matrix must have positive dimensions")
        if len(self.transition_tensor) != n_actions:
            raise ValueError("transition_tensor must provide one transition matrix per action")
        for _action_index, matrix in enumerate(self.transition_tensor):
            if len(matrix) != n_states:
                raise ValueError("transition_tensor matrices must have one row per state")
            for _row_index, row in enumerate(matrix):
                if len(row) != n_states:
                    raise ValueError("transition_tensor rows must have one column per state")
        if self.congestion_costs and len(self.congestion_costs) != n_states:
            raise ValueError("congestion_costs must have one entry per state")
        if (
            self.macro_simulation_config is not None
            and self.provenance is not None
            and self.provenance.numerics_config_ref is not None
        ):
            raise ValueError(
                "macro_simulation_config must be omitted when provenance already carries numerics_config_ref"
            )
        return self


class MeanFieldEquilibriumCertificate(BaseModel):
    """Typed certificate for macro-policy mean-field-equilibrium reasoning."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    equilibrium_concept: str = Field("mean_field_equilibrium", min_length=1)
    intervention_kind: MeanFieldInterventionKind
    baseline_policy_ref: ArtifactRefModel | None = None
    intervention_spec_ref: ArtifactRefModel
    mean_field_model_class: MeanFieldModelClass
    well_posedness: MeanFieldWellPosednessSummary
    identification: MeanFieldIdentificationSummary
    equilibrium_solution: MeanFieldEquilibriumSolutionSummary | None = None
    stability: MeanFieldStabilitySummary = Field(default_factory=MeanFieldStabilitySummary)
    provenance: MeanFieldProvenanceSummary | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("equilibrium_concept", mode="before")
    @classmethod
    def _validate_equilibrium_concept(cls, value: Any) -> str:
        candidate = _ensure_non_empty(str(value), field_name="equilibrium_concept")
        if candidate != "mean_field_equilibrium":
            raise ValueError("equilibrium_concept must be 'mean_field_equilibrium'")
        return candidate

    @model_validator(mode="after")
    def _validate_certificate(self) -> MeanFieldEquilibriumCertificate:
        _validate_artifact_ref(self.intervention_spec_ref, field_name="intervention_spec_ref")
        if self.baseline_policy_ref is not None:
            _validate_artifact_ref(self.baseline_policy_ref, field_name="baseline_policy_ref")
        if (
            self.well_posedness.uniqueness_status is MeanFieldUniquenessStatus.UNIQUE
            and self.identification.selection_rule is not MeanFieldSelectionRule.NONE
        ):
            raise ValueError("selection_rule must be none when uniqueness_status=unique")
        if (
            self.well_posedness.uniqueness_status is MeanFieldUniquenessStatus.LOCAL_STABLE_BRANCH
            and self.identification.selection_rule is MeanFieldSelectionRule.NONE
        ):
            raise ValueError(
                "selection_rule is required when uniqueness_status=local_stable_branch"
            )
        if self.provenance is not None and self.provenance.numerics_config_ref is not None:
            if self.equilibrium_solution is None:
                raise ValueError(
                    "equilibrium_solution is required when numerics_config_ref is provided"
                )
            if self.equilibrium_solution.solver_residual_ref is None:
                raise ValueError(
                    "solver_residual_ref is required when numerics_config_ref is provided"
                )
            if self.equilibrium_solution.mass_conservation_ref is None:
                raise ValueError(
                    "mass_conservation_ref is required when numerics_config_ref is provided"
                )
        return self


class PostAdaptationPolicyValueSummary(BaseModel):
    """Persisted post-adaptation policy-value disclosure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    fallback_mode: StrategicFallbackMode
    baseline_policy_value: float | None = None
    point_value: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    blocked_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("blocked_reason", mode="before")
    @classmethod
    def _validate_blocked_reason(cls, value: Any) -> Any:
        if value is None:
            return None
        return _ensure_non_empty(str(value), field_name="blocked_reason")

    @model_validator(mode="after")
    def _validate_value_summary(self) -> PostAdaptationPolicyValueSummary:
        for field_name in (
            "baseline_policy_value",
            "point_value",
            "lower_bound",
            "upper_bound",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _ensure_finite(value, field_name=field_name)
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.lower_bound > self.upper_bound
        ):
            raise ValueError("lower_bound must be <= upper_bound")
        if self.fallback_mode is StrategicFallbackMode.BLOCKED:
            if self.blocked_reason is None:
                raise ValueError("blocked_reason is required when fallback_mode=blocked")
        elif self.blocked_reason is not None:
            raise ValueError("blocked_reason is only allowed when fallback_mode=blocked")
        return self


class StrategicDecompositionComponent(str, Enum):
    """Component label for bounded causal/strategic decomposition artifacts."""

    CAUSAL = "causal"
    STRATEGIC = "strategic"


class StrategicDecompositionCertificate(BaseModel):
    """Certificate that licenses a point or bounded causal/strategic decomposition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    decomposition_status: StrategicDecompositionStatus
    decomposition_semantics: StrategicDecompositionSemantics = (
        StrategicDecompositionSemantics.FROZEN_BASELINE_STRATEGY
    )
    theorem_family: str = Field(
        default="policyos_t5_3_frozen_baseline_strategy",
        min_length=1,
    )
    cross_world_anchor_defined: bool
    selector_invariant: bool = False
    equilibrium_selector_justified: bool = False
    assumptions_checked: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("theorem_family", mode="before")
    @classmethod
    def _validate_theorem_family(cls, value: Any) -> str:
        return _ensure_non_empty(str(value), field_name="theorem_family")

    @model_validator(mode="after")
    def _validate_certificate(self) -> StrategicDecompositionCertificate:
        if self.decomposition_status is StrategicDecompositionStatus.BLOCKED:
            raise ValueError("decomposition certificate cannot use blocked status")
        if (
            self.decomposition_status
            in {
                StrategicDecompositionStatus.EXACT,
                StrategicDecompositionStatus.SELECTOR_INVARIANT,
            }
            and not self.cross_world_anchor_defined
        ):
            raise ValueError(
                "cross_world_anchor_defined is required for exact or selector_invariant decomposition"
            )
        if (
            self.decomposition_status is StrategicDecompositionStatus.SELECTOR_INVARIANT
            and not self.selector_invariant
        ):
            raise ValueError(
                "selector_invariant must be true when decomposition_status=selector_invariant"
            )
        return self


class StrategicDecompositionFailureCard(BaseModel):
    """Failure card explaining why point-valued decomposition is unavailable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    failure_code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    decomposition_semantics: StrategicDecompositionSemantics = (
        StrategicDecompositionSemantics.FROZEN_BASELINE_STRATEGY
    )
    fallback_mode: StrategicFallbackMode
    equilibrium_selection_dependence: str = Field(min_length=1)
    multiplicity_note: str | None = None
    blocked_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "failure_code",
        "message",
        "equilibrium_selection_dependence",
        "multiplicity_note",
        "blocked_reason",
        mode="before",
    )
    @classmethod
    def _validate_failure_strings(cls, value: Any, info: Any) -> Any:
        if value is None:
            return None
        return _ensure_non_empty(str(value), field_name=str(info.field_name))


class StrategicComponentBoundsSummary(BaseModel):
    """Bounded causal or strategic component under frozen-baseline semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    component: StrategicDecompositionComponent
    decomposition_semantics: StrategicDecompositionSemantics = (
        StrategicDecompositionSemantics.FROZEN_BASELINE_STRATEGY
    )
    lower_bound: float
    upper_bound: float
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_bounds(self) -> StrategicComponentBoundsSummary:
        _ensure_finite(self.lower_bound, field_name="lower_bound")
        _ensure_finite(self.upper_bound, field_name="upper_bound")
        if self.lower_bound > self.upper_bound:
            raise ValueError("lower_bound must be <= upper_bound")
        return self


class StrategicResponseBundle(BaseModel):
    """Disclosed strategic closure around a causal policy recommendation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.1", pattern=r"^\d+\.\d+$")
    causal_component_ref: ArtifactRefModel
    strategic_closure_ref: ArtifactRefModel
    equilibrium_selection_dependence: str = Field(min_length=1)
    behavioral_assumption_sensitivity_ref: ArtifactRefModel | None = None
    equilibrium_set_ref: ArtifactRefModel
    selected_equilibrium_ref: ArtifactRefModel | None = None
    multiplicity_note: str | None = None
    mfg_equilibrium_ref: MeanFieldEquilibriumCertificateRef | None = None
    performative_shift_ref: ArtifactRefModel | None = None
    post_adaptation_policy_value_ref: ArtifactRefModel
    decomposition_status: StrategicDecompositionStatus
    decomposition_semantics: StrategicDecompositionSemantics = (
        StrategicDecompositionSemantics.FROZEN_BASELINE_STRATEGY
    )
    decomposition_certificate_ref: ArtifactRefModel | None = None
    decomposition_failure_card_ref: ArtifactRefModel | None = None
    equilibrium_selector_ref: ArtifactRefModel | None = None
    anchor_equilibrium_ref: ArtifactRefModel | None = None
    causal_component_bounds_ref: ArtifactRefModel | None = None
    strategic_component_bounds_ref: ArtifactRefModel | None = None
    fallback_mode: StrategicFallbackMode = StrategicFallbackMode.EXACT_EQUILIBRIUM
    blocked_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "equilibrium_selection_dependence",
        "multiplicity_note",
        "blocked_reason",
        mode="before",
    )
    @classmethod
    def _validate_strings(cls, value: Any, info: Any) -> Any:
        if value is None:
            return None
        return _ensure_non_empty(str(value), field_name=str(info.field_name))

    @model_validator(mode="after")
    def _validate_bundle(self) -> StrategicResponseBundle:
        _validate_artifact_ref(self.causal_component_ref, field_name="causal_component_ref")
        _validate_artifact_ref(self.strategic_closure_ref, field_name="strategic_closure_ref")
        _validate_artifact_ref(self.equilibrium_set_ref, field_name="equilibrium_set_ref")
        _validate_artifact_ref(
            self.post_adaptation_policy_value_ref,
            field_name="post_adaptation_policy_value_ref",
        )
        if self.behavioral_assumption_sensitivity_ref is not None:
            _validate_artifact_ref(
                self.behavioral_assumption_sensitivity_ref,
                field_name="behavioral_assumption_sensitivity_ref",
            )
        if self.performative_shift_ref is not None:
            _validate_artifact_ref(
                self.performative_shift_ref,
                field_name="performative_shift_ref",
            )
        if self.mfg_equilibrium_ref is not None:
            _validate_artifact_ref(
                self.mfg_equilibrium_ref,
                field_name="mfg_equilibrium_ref",
            )
        if self.selected_equilibrium_ref is not None:
            _validate_artifact_ref(
                self.selected_equilibrium_ref,
                field_name="selected_equilibrium_ref",
            )
        if self.decomposition_certificate_ref is not None:
            _validate_artifact_ref(
                self.decomposition_certificate_ref,
                field_name="decomposition_certificate_ref",
            )
        if self.decomposition_failure_card_ref is not None:
            _validate_artifact_ref(
                self.decomposition_failure_card_ref,
                field_name="decomposition_failure_card_ref",
            )
        if self.equilibrium_selector_ref is not None:
            _validate_artifact_ref(
                self.equilibrium_selector_ref,
                field_name="equilibrium_selector_ref",
            )
        if self.anchor_equilibrium_ref is not None:
            _validate_artifact_ref(
                self.anchor_equilibrium_ref,
                field_name="anchor_equilibrium_ref",
            )
        if self.causal_component_bounds_ref is not None:
            _validate_artifact_ref(
                self.causal_component_bounds_ref,
                field_name="causal_component_bounds_ref",
            )
        if self.strategic_component_bounds_ref is not None:
            _validate_artifact_ref(
                self.strategic_component_bounds_ref,
                field_name="strategic_component_bounds_ref",
            )
        if self.fallback_mode is StrategicFallbackMode.BLOCKED:
            if self.blocked_reason is None:
                raise ValueError("blocked_reason is required when fallback_mode=blocked")
            if self.selected_equilibrium_ref is not None:
                raise ValueError("selected_equilibrium_ref must be omitted when blocked")
            if self.mfg_equilibrium_ref is not None:
                raise ValueError("mfg_equilibrium_ref must be omitted when blocked")
        elif self.blocked_reason is not None:
            raise ValueError("blocked_reason is only allowed when fallback_mode=blocked")
        if self.selected_equilibrium_ref is not None and self.mfg_equilibrium_ref is not None:
            raise ValueError(
                "selected_equilibrium_ref and mfg_equilibrium_ref are mutually exclusive"
            )
        if (
            self.fallback_mode is StrategicFallbackMode.EXACT_EQUILIBRIUM
            and self.selected_equilibrium_ref is None
            and self.mfg_equilibrium_ref is None
        ):
            raise ValueError(
                "selected_equilibrium_ref or mfg_equilibrium_ref is required for exact_equilibrium"
            )
        if self.decomposition_status is StrategicDecompositionStatus.BLOCKED:
            if self.decomposition_failure_card_ref is None:
                raise ValueError(
                    "decomposition_failure_card_ref is required when decomposition_status=blocked"
                )
            if self.decomposition_certificate_ref is not None:
                raise ValueError(
                    "decomposition_certificate_ref must be omitted when decomposition_status=blocked"
                )
            if (
                self.causal_component_bounds_ref is not None
                or self.strategic_component_bounds_ref is not None
            ):
                raise ValueError(
                    "component bounds refs must be omitted when decomposition_status=blocked"
                )
        elif self.decomposition_status is StrategicDecompositionStatus.BOUNDED:
            if (
                self.causal_component_bounds_ref is None
                or self.strategic_component_bounds_ref is None
            ):
                raise ValueError(
                    "both component bounds refs are required when decomposition_status=bounded"
                )
            if self.decomposition_failure_card_ref is not None:
                raise ValueError(
                    "decomposition_failure_card_ref must be omitted when decomposition_status=bounded"
                )
        else:
            if self.decomposition_certificate_ref is None:
                raise ValueError(
                    "decomposition_certificate_ref is required for exact or selector_invariant decomposition"
                )
            if self.anchor_equilibrium_ref is None:
                raise ValueError(
                    "anchor_equilibrium_ref is required for exact or selector_invariant decomposition"
                )
            if self.decomposition_failure_card_ref is not None:
                raise ValueError(
                    "decomposition_failure_card_ref must be omitted for exact or selector_invariant decomposition"
                )
            if (
                self.causal_component_bounds_ref is not None
                or self.strategic_component_bounds_ref is not None
            ):
                raise ValueError(
                    "component bounds refs must be omitted for exact or selector_invariant decomposition"
                )
        return self




def persist_strategic_payoff_table(
    store: ArtifactStore,
    table: FiniteStrategicPayoffTable,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _STRATEGIC_PAYOFF_TABLE_SCHEMA_NAME,
    schema_version: str = _STRATEGIC_PAYOFF_TABLE_SCHEMA_VERSION,
) -> StrategicPayoffTableRef:
    """Persist one finite payoff table and return its typed artifact reference."""
    ref = put_json_artifact(
        store,
        table.model_dump(mode="json"),
        kind="ir.strategic_payoff_table",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return StrategicPayoffTableRef.model_validate(ref)


def load_strategic_payoff_table(
    store: ArtifactStore,
    ref: StrategicPayoffTableRef,
) -> FiniteStrategicPayoffTable:
    """Load strategic payoff table."""
    payload = get_json_artifact(store, ref.artifact_id)
    return FiniteStrategicPayoffTable.model_validate(payload)


def persist_strategic_scm(
    store: ArtifactStore,
    contract: StrategicSCM,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _STRATEGIC_SCM_SCHEMA_NAME,
    schema_version: str = _STRATEGIC_SCM_SCHEMA_VERSION,
) -> StrategicSCMRef:
    """Persist a strategic SCM contract and return its typed artifact reference."""
    ref = put_json_artifact(
        store,
        contract.model_dump(mode="json"),
        kind="ir.strategic_scm",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return StrategicSCMRef.model_validate(ref)


def load_strategic_scm(
    store: ArtifactStore,
    ref: StrategicSCMRef,
) -> StrategicSCM:
    """Load strategic scm."""
    payload = get_json_artifact(store, ref.artifact_id)
    return StrategicSCM.model_validate(payload)


def persist_strategic_response_bundle(
    store: ArtifactStore,
    bundle: StrategicResponseBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _STRATEGIC_RESPONSE_BUNDLE_SCHEMA_NAME,
    schema_version: str = _STRATEGIC_RESPONSE_BUNDLE_SCHEMA_VERSION,
) -> StrategicResponseBundleRef:
    """Persist the top-level strategic-response bundle for downstream reporting."""
    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind="ir.strategic_response_bundle",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return StrategicResponseBundleRef.model_validate(ref)


def load_strategic_response_bundle(
    store: ArtifactStore,
    ref: StrategicResponseBundleRef,
) -> StrategicResponseBundle:
    """Load strategic response bundle."""
    payload = get_json_artifact(store, ref.artifact_id)
    return StrategicResponseBundle.model_validate(payload)


def persist_mean_field_perturbation_spec(
    store: ArtifactStore,
    spec: MeanFieldPerturbationSpec,
    *,
    inputs: list[InputRef] | None = None,
) -> MeanFieldPerturbationSpecRef:
    """Persist a compiled MFG perturbation spec."""
    ref = _persist_strategic_leaf(
        store,
        spec,
        kind=_MFG_PERTURBATION_SPEC_SCHEMA_NAME,
        schema_name=_MFG_PERTURBATION_SPEC_SCHEMA_NAME,
        schema_version=_MFG_PERTURBATION_SPEC_SCHEMA_VERSION,
        inputs=inputs,
    )
    return MeanFieldPerturbationSpecRef.model_validate(ref.model_dump(mode="json"))


def load_mean_field_perturbation_spec(
    store: ArtifactStore,
    ref: MeanFieldPerturbationSpecRef,
) -> MeanFieldPerturbationSpec:
    """Load a compiled MFG perturbation spec."""
    return MeanFieldPerturbationSpec.model_validate(
        _load_strategic_leaf(store, ref, MeanFieldPerturbationSpec)
    )


def persist_mean_field_macro_simulation_config(
    store: ArtifactStore,
    config: MeanFieldMacroSimulationConfig,
    *,
    inputs: list[InputRef] | None = None,
) -> MeanFieldMacroSimulationConfigRef:
    """Persist a reproducible MFG numerics config."""
    ref = _persist_strategic_leaf(
        store,
        config,
        kind=_MFG_MACRO_SIMULATION_CONFIG_SCHEMA_NAME,
        schema_name=_MFG_MACRO_SIMULATION_CONFIG_SCHEMA_NAME,
        schema_version=_MFG_MACRO_SIMULATION_CONFIG_SCHEMA_VERSION,
        inputs=inputs,
    )
    return MeanFieldMacroSimulationConfigRef.model_validate(ref.model_dump(mode="json"))


def load_mean_field_macro_simulation_config(
    store: ArtifactStore,
    ref: MeanFieldMacroSimulationConfigRef,
) -> MeanFieldMacroSimulationConfig:
    """Load a reproducible MFG numerics config."""
    return MeanFieldMacroSimulationConfig.model_validate(
        _load_strategic_leaf(store, ref, MeanFieldMacroSimulationConfig)
    )


def persist_mean_field_solver_residual_report(
    store: ArtifactStore,
    report: MeanFieldSolverResidualReport,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist a mean-field solver residual evidence report."""
    return _persist_strategic_leaf(
        store,
        report,
        kind=_MFG_SOLVER_RESIDUAL_REPORT_SCHEMA_NAME,
        schema_name=_MFG_SOLVER_RESIDUAL_REPORT_SCHEMA_NAME,
        schema_version=_MFG_SOLVER_RESIDUAL_REPORT_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_mean_field_solver_residual_report(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> MeanFieldSolverResidualReport:
    """Load a mean-field solver residual evidence report."""
    return MeanFieldSolverResidualReport.model_validate(
        _load_strategic_leaf(store, ref, MeanFieldSolverResidualReport)
    )


def persist_mean_field_mass_conservation_report(
    store: ArtifactStore,
    report: MeanFieldMassConservationReport,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist a mean-field mass conservation evidence report."""
    return _persist_strategic_leaf(
        store,
        report,
        kind=_MFG_MASS_CONSERVATION_REPORT_SCHEMA_NAME,
        schema_name=_MFG_MASS_CONSERVATION_REPORT_SCHEMA_NAME,
        schema_version=_MFG_MASS_CONSERVATION_REPORT_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_mean_field_mass_conservation_report(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> MeanFieldMassConservationReport:
    """Load a mean-field mass conservation evidence report."""
    return MeanFieldMassConservationReport.model_validate(
        _load_strategic_leaf(store, ref, MeanFieldMassConservationReport)
    )


def persist_mean_field_equilibrium_certificate(
    store: ArtifactStore,
    certificate: MeanFieldEquilibriumCertificate,
    *,
    inputs: list[InputRef] | None = None,
) -> MeanFieldEquilibriumCertificateRef:
    """Persist a mean-field-equilibrium certificate leaf artifact."""
    ref = _persist_strategic_leaf(
        store,
        certificate,
        kind=_MFG_EQUILIBRIUM_CERTIFICATE_SCHEMA_NAME,
        schema_name=_MFG_EQUILIBRIUM_CERTIFICATE_SCHEMA_NAME,
        schema_version=_MFG_EQUILIBRIUM_CERTIFICATE_SCHEMA_VERSION,
        inputs=inputs,
    )
    return MeanFieldEquilibriumCertificateRef.model_validate(ref.model_dump(mode="json"))


def load_mean_field_equilibrium_certificate(
    store: ArtifactStore,
    ref: MeanFieldEquilibriumCertificateRef,
) -> MeanFieldEquilibriumCertificate:
    """Load mean-field-equilibrium certificate."""
    return MeanFieldEquilibriumCertificate.model_validate(
        _load_strategic_leaf(store, ref, MeanFieldEquilibriumCertificate)
    )


def persist_strategic_closure_summary(
    store: ArtifactStore,
    summary: StrategicClosureSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist a strategic closure summary leaf artifact."""
    return _persist_strategic_leaf(
        store,
        summary,
        kind=_STRATEGIC_CLOSURE_SUMMARY_SCHEMA_NAME,
        schema_name=_STRATEGIC_CLOSURE_SUMMARY_SCHEMA_NAME,
        schema_version=_STRATEGIC_CLOSURE_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_strategic_closure_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> StrategicClosureSummary:
    """Load strategic closure summary."""
    return StrategicClosureSummary.model_validate(
        _load_strategic_leaf(store, ref, StrategicClosureSummary)
    )


def persist_equilibrium_set_summary(
    store: ArtifactStore,
    summary: EquilibriumSetSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist an equilibrium-set disclosure leaf artifact."""
    return _persist_strategic_leaf(
        store,
        summary,
        kind=_EQUILIBRIUM_SET_SUMMARY_SCHEMA_NAME,
        schema_name=_EQUILIBRIUM_SET_SUMMARY_SCHEMA_NAME,
        schema_version=_EQUILIBRIUM_SET_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_equilibrium_set_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> EquilibriumSetSummary:
    """Load equilibrium set summary."""
    return EquilibriumSetSummary.model_validate(
        _load_strategic_leaf(store, ref, EquilibriumSetSummary)
    )


def persist_equilibrium_selection_summary(
    store: ArtifactStore,
    summary: EquilibriumSelectionSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist the selected-equilibrium disclosure leaf artifact."""
    return _persist_strategic_leaf(
        store,
        summary,
        kind=_EQUILIBRIUM_SELECTION_SUMMARY_SCHEMA_NAME,
        schema_name=_EQUILIBRIUM_SELECTION_SUMMARY_SCHEMA_NAME,
        schema_version=_EQUILIBRIUM_SELECTION_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_equilibrium_selection_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> EquilibriumSelectionSummary:
    """Load equilibrium selection summary."""
    return EquilibriumSelectionSummary.model_validate(
        _load_strategic_leaf(store, ref, EquilibriumSelectionSummary)
    )


def persist_performative_shift_summary(
    store: ArtifactStore,
    summary: PerformativeShiftSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist a performative-shift disclosure leaf artifact."""
    return _persist_strategic_leaf(
        store,
        summary,
        kind=_PERFORMATIVE_SHIFT_SUMMARY_SCHEMA_NAME,
        schema_name=_PERFORMATIVE_SHIFT_SUMMARY_SCHEMA_NAME,
        schema_version=_PERFORMATIVE_SHIFT_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_performative_shift_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> PerformativeShiftSummary:
    """Load performative shift summary."""
    return PerformativeShiftSummary.model_validate(
        _load_strategic_leaf(store, ref, PerformativeShiftSummary)
    )


def persist_post_adaptation_policy_value_summary(
    store: ArtifactStore,
    summary: PostAdaptationPolicyValueSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist the post-adaptation policy-value disclosure leaf artifact."""
    return _persist_strategic_leaf(
        store,
        summary,
        kind=_POST_ADAPTATION_POLICY_VALUE_SUMMARY_SCHEMA_NAME,
        schema_name=_POST_ADAPTATION_POLICY_VALUE_SUMMARY_SCHEMA_NAME,
        schema_version=_POST_ADAPTATION_POLICY_VALUE_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_post_adaptation_policy_value_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> PostAdaptationPolicyValueSummary:
    """Load post adaptation policy value summary."""
    return PostAdaptationPolicyValueSummary.model_validate(
        _load_strategic_leaf(store, ref, PostAdaptationPolicyValueSummary)
    )


def persist_strategic_decomposition_certificate(
    store: ArtifactStore,
    certificate: StrategicDecompositionCertificate,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist a strategic decomposition certificate leaf artifact."""
    return _persist_strategic_leaf(
        store,
        certificate,
        kind=_STRATEGIC_DECOMPOSITION_CERTIFICATE_SCHEMA_NAME,
        schema_name=_STRATEGIC_DECOMPOSITION_CERTIFICATE_SCHEMA_NAME,
        schema_version=_STRATEGIC_DECOMPOSITION_CERTIFICATE_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_strategic_decomposition_certificate(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> StrategicDecompositionCertificate:
    """Load strategic decomposition certificate."""
    return StrategicDecompositionCertificate.model_validate(
        _load_strategic_leaf(store, ref, StrategicDecompositionCertificate)
    )


def persist_strategic_decomposition_failure_card(
    store: ArtifactStore,
    card: StrategicDecompositionFailureCard,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist a strategic decomposition failure-card leaf artifact."""
    return _persist_strategic_leaf(
        store,
        card,
        kind=_STRATEGIC_DECOMPOSITION_FAILURE_CARD_SCHEMA_NAME,
        schema_name=_STRATEGIC_DECOMPOSITION_FAILURE_CARD_SCHEMA_NAME,
        schema_version=_STRATEGIC_DECOMPOSITION_FAILURE_CARD_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_strategic_decomposition_failure_card(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> StrategicDecompositionFailureCard:
    """Load strategic decomposition failure card."""
    return StrategicDecompositionFailureCard.model_validate(
        _load_strategic_leaf(store, ref, StrategicDecompositionFailureCard)
    )


def persist_strategic_component_bounds_summary(
    store: ArtifactStore,
    summary: StrategicComponentBoundsSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRefModel:
    """Persist a bounded causal/strategic component leaf artifact."""
    return _persist_strategic_leaf(
        store,
        summary,
        kind=_STRATEGIC_COMPONENT_BOUNDS_SUMMARY_SCHEMA_NAME,
        schema_name=_STRATEGIC_COMPONENT_BOUNDS_SUMMARY_SCHEMA_NAME,
        schema_version=_STRATEGIC_COMPONENT_BOUNDS_SUMMARY_SCHEMA_VERSION,
        inputs=inputs,
    )


def load_strategic_component_bounds_summary(
    store: ArtifactStore,
    ref: ArtifactRefModel,
) -> StrategicComponentBoundsSummary:
    """Load strategic component bounds summary."""
    return StrategicComponentBoundsSummary.model_validate(
        _load_strategic_leaf(store, ref, StrategicComponentBoundsSummary)
    )


__all__ = [
    "EquilibriumSelectionSummary",
    "EquilibriumSetSummary",
    "FiniteStrategicPayoffTable",
    "MeanFieldEquilibriumCertificate",
    "MeanFieldEquilibriumSolutionSummary",
    "MeanFieldFixedPointMethod",
    "MeanFieldGraphSemantics",
    "MeanFieldIdentificationSummary",
    "MeanFieldInterventionKind",
    "MeanFieldMacroSimulationConfig",
    "MeanFieldMassConservationReport",
    "MeanFieldModelClass",
    "MeanFieldMonotonicityType",
    "MeanFieldNumericsScheme",
    "MeanFieldPerturbationChannel",
    "MeanFieldPerturbationSpec",
    "MeanFieldPositivityStatus",
    "MeanFieldProvenanceSummary",
    "MeanFieldRuntimeMode",
    "MeanFieldSelectionRule",
    "MeanFieldSolveInput",
    "MeanFieldSolverResidualReport",
    "MeanFieldStabilityBoundType",
    "MeanFieldStabilityMetric",
    "MeanFieldStabilitySummary",
    "MeanFieldUniquenessStatus",
    "MeanFieldWellPosednessSummary",
    "PerformativeInstabilityReason",
    "PerformativeLoopAnalysisScope",
    "PerformativeLoopCertificate",
    "PerformativeLoopProofFamily",
    "PerformativeLoopRecommendedAction",
    "PerformativeLoopStabilityStatus",
    "PerformativeLoopWitnessStrength",
    "PerformativeShiftSummary",
    "PostAdaptationPolicyValueSummary",
    "StrategicAdmissibilityRecord",
    "StrategicClosureSummary",
    "StrategicComponentBoundsSummary",
    "StrategicDecompositionCertificate",
    "StrategicDecompositionComponent",
    "StrategicDecompositionFailureCard",
    "StrategicDecompositionSemantics",
    "StrategicDecompositionStatus",
    "StrategicEquilibriumConcept",
    "StrategicEquilibriumDescriptor",
    "StrategicFallbackMode",
    "StrategicGameClass",
    "StrategicResponseBundle",
    "StrategicSCM",
    "StrategicSolutionConcept",
    "StrategicTractabilityClass",
    "compile_intervention_spec_to_mean_field_perturbation",
    "decode_action_profile",
    "encode_action_profile",
    "load_equilibrium_selection_summary",
    "load_equilibrium_set_summary",
    "load_mean_field_equilibrium_certificate",
    "load_mean_field_macro_simulation_config",
    "load_mean_field_mass_conservation_report",
    "load_mean_field_perturbation_spec",
    "load_mean_field_solver_residual_report",
    "load_performative_shift_summary",
    "load_post_adaptation_policy_value_summary",
    "load_strategic_closure_summary",
    "load_strategic_component_bounds_summary",
    "load_strategic_decomposition_certificate",
    "load_strategic_decomposition_failure_card",
    "load_strategic_payoff_table",
    "load_strategic_response_bundle",
    "load_strategic_scm",
    "persist_equilibrium_selection_summary",
    "persist_equilibrium_set_summary",
    "persist_mean_field_equilibrium_certificate",
    "persist_mean_field_macro_simulation_config",
    "persist_mean_field_mass_conservation_report",
    "persist_mean_field_perturbation_spec",
    "persist_mean_field_solver_residual_report",
    "persist_performative_shift_summary",
    "persist_post_adaptation_policy_value_summary",
    "persist_strategic_closure_summary",
    "persist_strategic_component_bounds_summary",
    "persist_strategic_decomposition_certificate",
    "persist_strategic_decomposition_failure_card",
    "persist_strategic_payoff_table",
    "persist_strategic_response_bundle",
    "persist_strategic_scm",
    "strategic_admissibility_record_for",
    "strategic_admissibility_records",
]
