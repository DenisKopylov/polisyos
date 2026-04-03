"""Public causal strategic module API."""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Any, Mapping

from polisyos.ir.analytics.abstraction import (
    AbstractionCertificate,
    AbstractionPreservationType,
)
from polisyos.ir.analytics.strategic import (
    FiniteStrategicPayoffTable,
    StrategicEquilibriumConcept,
    StrategicFallbackMode,
    StrategicResponseBundle,
    StrategicSCM,
)
from polisyos.ir.refs import ArtifactRefModel

MAX_STRATEGIC_ACTIONS_PER_AGENT = 8
MAX_STRATEGIC_PROFILE_ENUMERATIONS = 256


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
    warnings: tuple[str, ...] = ()


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
            raise ValueError("Payoff tables must use the same strategic_agents ordering as StrategicSCM")
        current = {
            name: tuple(actions)
            for name, actions in table.action_spaces.items()
        }
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
        _agent_payoff(tables, contract, profile, agent)
        for agent in contract.strategic_agents
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
            _agent_payoff(tables, contract, profile, follower)
            for profile in candidate_profiles
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
    multiplicity_note = (
        "multiple_best_response_fixed_points" if len(equilibria) > 1 else None
    )
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
    profile_values = [
        _mean_profile_payoff(tables, contract, profile)
        for profile in profiles
    ]
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
    )


def solve_strategic_response(
    strategic_scm: StrategicSCM,
    payoff_tables: Mapping[str, FiniteStrategicPayoffTable],
    *,
    baseline_policy_value: float | None = None,
    abstraction_certificate: AbstractionCertificate | None = None,
    macro_payoff_tables: Mapping[str, FiniteStrategicPayoffTable] | None = None,
) -> StrategicSolveResult:
    """Solve a small strategic response game or disclose the fallback used."""

    action_spaces = _action_spaces(strategic_scm, payoff_tables)
    profiles = _enumerate_profiles(strategic_scm, action_spaces)

    exact_supported = strategic_scm.runtime_eligible
    exact_budget_ok, exact_budget_reason = _check_budget(
        strategic_scm,
        profile_count=len(profiles),
    )

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
            shift = _mean_profile_payoff(payoff_tables, strategic_scm, selected)
            post_value = _post_adaptation_value(
                baseline_policy_value=baseline_policy_value,
                performative_shift=shift,
            )
            closure_summary = {
                "mode": StrategicFallbackMode.EXACT_EQUILIBRIUM.value,
                "equilibrium_concept": strategic_scm.equilibrium_concept.value,
                "profile_count": len(profiles),
                "equilibrium_count": len(sorted_equilibria),
                "selected_equilibrium": dict(selected),
                "selected_mean_payoff": shift,
                "equilibrium_profiles": [dict(profile) for profile in sorted_equilibria],
            }
            return StrategicSolveResult(
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
            )

    if exact_block_reason is None:
        exact_block_reason = exact_budget_reason or (
            strategic_scm.runtime_blockers[0] if strategic_scm.runtime_blockers else "exact_equilibrium_unavailable"
        )

    bounds_budget_ok, bounds_budget_reason = _check_budget(
        strategic_scm,
        profile_count=len(profiles),
    )
    if bounds_budget_ok:
        return _strategic_bounds(
            strategic_scm,
            payoff_tables,
            profiles,
            baseline_policy_value=baseline_policy_value,
        )

    if macro_payoff_tables is not None:
        if abstraction_certificate is None or (
            abstraction_certificate.preservation_type is not AbstractionPreservationType.EXACT
        ):
            return StrategicSolveResult(
                fallback_mode=StrategicFallbackMode.BLOCKED,
                equilibrium_profiles=(),
                selected_equilibrium=None,
                equilibrium_selection_dependence="blocked_without_exact_abstraction_certificate",
                multiplicity_note=None,
                blocked_reason="macro_abstracted_requires_exact_abstraction_certificate",
                performative_shift=None,
                post_adaptation_policy_value=None,
                bounds=None,
                closure_summary={
                    "mode": StrategicFallbackMode.BLOCKED.value,
                    "blocked_reason": "macro_abstracted_requires_exact_abstraction_certificate",
                    "exact_block_reason": exact_block_reason,
                    "bounds_block_reason": bounds_budget_reason,
                },
            )

        macro_result = solve_strategic_response(
            strategic_scm,
            macro_payoff_tables,
            baseline_policy_value=baseline_policy_value,
            abstraction_certificate=None,
            macro_payoff_tables=None,
        )
        if macro_result.fallback_mode is StrategicFallbackMode.EXACT_EQUILIBRIUM:
            closure_summary = dict(macro_result.closure_summary)
            closure_summary["mode"] = StrategicFallbackMode.MACRO_ABSTRACTED.value
            closure_summary["abstraction_map_ref"] = str(
                abstraction_certificate.abstraction_map_ref.artifact_id
            )
            return StrategicSolveResult(
                fallback_mode=StrategicFallbackMode.MACRO_ABSTRACTED,
                equilibrium_profiles=macro_result.equilibrium_profiles,
                selected_equilibrium=macro_result.selected_equilibrium,
                equilibrium_selection_dependence=macro_result.equilibrium_selection_dependence,
                multiplicity_note=macro_result.multiplicity_note,
                blocked_reason=None,
                performative_shift=macro_result.performative_shift,
                post_adaptation_policy_value=macro_result.post_adaptation_policy_value,
                bounds=None,
                closure_summary=closure_summary,
                warnings=("macro_abstracted_equilibrium_used",),
            )

    return StrategicSolveResult(
        fallback_mode=StrategicFallbackMode.BLOCKED,
        equilibrium_profiles=(),
        selected_equilibrium=None,
        equilibrium_selection_dependence="strategic_complexity_blocked",
        multiplicity_note=None,
        blocked_reason=bounds_budget_reason or exact_block_reason or "unidentified_due_to_strategic_complexity",
        performative_shift=None,
        post_adaptation_policy_value=None,
        bounds=None,
        closure_summary={
            "mode": StrategicFallbackMode.BLOCKED.value,
            "exact_block_reason": exact_block_reason,
            "bounds_block_reason": bounds_budget_reason,
        },
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
    return summary


def build_strategic_response_bundle(
    *,
    causal_component_ref: ArtifactRefModel,
    strategic_closure_ref: ArtifactRefModel,
    equilibrium_set_ref: ArtifactRefModel,
    post_adaptation_policy_value_ref: ArtifactRefModel,
    result: StrategicSolveResult,
    behavioral_assumption_sensitivity_ref: ArtifactRefModel | None = None,
    selected_equilibrium_ref: ArtifactRefModel | None = None,
    performative_shift_ref: ArtifactRefModel | None = None,
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
        performative_shift_ref=performative_shift_ref,
        post_adaptation_policy_value_ref=post_adaptation_policy_value_ref,
        fallback_mode=result.fallback_mode,
        blocked_reason=result.blocked_reason,
        metadata={"closure_summary": dict(result.closure_summary)},
    )


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
        payoff_tables = _coerce_payoff_tables(params.get("strategic_payoff_tables"))
        abstraction_certificate = _coerce_abstraction_certificate(
            params.get("abstraction_certificate")
        )
        macro_payload = params.get("macro_strategic_payoff_tables")
        macro_tables = None if macro_payload is None else _coerce_payoff_tables(macro_payload)
        result = solve_strategic_response(
            contract,
            payoff_tables,
            baseline_policy_value=baseline_policy_value,
            abstraction_certificate=abstraction_certificate,
            macro_payoff_tables=macro_tables,
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
    "StrategicSolveResult",
    "build_strategic_response_bundle",
    "evaluate_strategic_hook",
    "solve_strategic_response",
    "strategic_result_summary",
]
