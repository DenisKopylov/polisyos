from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.foundry.methods.catalog.causal.strategic import (
    StrategicSolveResult,
    solve_strategic_response,
)
from polisyos.ir.analytics.abstraction import AbstractionCertificate
from polisyos.ir.analytics.strategic import (
    FiniteStrategicPayoffTable,
    StrategicFallbackMode,
    StrategicSCM,
)
from polisyos.scientist.backtesting.adversarial import (
    MULTIPLICITY_DISCLOSURE_SUITE_ID,
    STRATEGIC_GAMING_SUITE_ID,
    ChallengeCase,
    ChallengeSuiteResult,
    build_challenge_case_result,
    build_challenge_suite_result,
)
from polisyos.scientist.doe.stress_report import VulnerabilityType

_ALLOWED_FALLBACK_MODES = {
    StrategicFallbackMode.EXACT_EQUILIBRIUM,
    StrategicFallbackMode.STRATEGIC_BOUNDS,
    StrategicFallbackMode.MACRO_ABSTRACTED,
    StrategicFallbackMode.BLOCKED,
}


def run_strategic_challenge_suites(
    *,
    candidate_ref: ArtifactRef,
    loop_id: str,
    run_id: str,
    params: Mapping[str, Any],
    strategic_summary: Mapping[str, Any] | None,
    abstraction_certificate: AbstractionCertificate | None,
) -> tuple[list[ChallengeSuiteResult], tuple[str, ...]]:
    del run_id

    contract = _coerce_strategic_contract(params.get("strategic_scm"))
    payoff_tables = _coerce_payoff_tables(params.get("strategic_payoff_tables"))
    macro_payoff_tables = _coerce_payoff_tables(params.get("macro_strategic_payoff_tables"))
    baseline_policy_value = _extract_baseline_policy_value(params)

    suite_results: list[ChallengeSuiteResult] = []
    warnings: list[str] = []

    if contract is None or payoff_tables is None:
        if strategic_summary is None:
            return [], ("phase_d4_strategic_suite_skipped_no_inputs",)
        warnings.append("phase_d4_strategic_suite_audit_only")
        suite_results.append(
            _build_strategic_gaming_suite_from_summary(
                candidate_ref=candidate_ref,
                loop_id=loop_id,
                strategic_summary=strategic_summary,
            )
        )
        suite_results.append(
            _build_multiplicity_suite_from_summary(
                candidate_ref=candidate_ref,
                loop_id=loop_id,
                strategic_summary=strategic_summary,
            )
        )
        return suite_results, tuple(warnings)

    suite_results.append(
        _build_strategic_gaming_suite_from_raw(
            candidate_ref=candidate_ref,
            loop_id=loop_id,
            contract=contract,
            payoff_tables=payoff_tables,
            macro_payoff_tables=macro_payoff_tables,
            abstraction_certificate=abstraction_certificate,
            baseline_policy_value=baseline_policy_value,
            strategic_summary=strategic_summary,
        )
    )
    suite_results.append(
        _build_multiplicity_suite_from_raw(
            candidate_ref=candidate_ref,
            loop_id=loop_id,
            contract=contract,
            payoff_tables=payoff_tables,
            baseline_policy_value=baseline_policy_value,
            strategic_summary=strategic_summary,
        )
    )
    return suite_results, tuple(warnings)


def _build_strategic_gaming_suite_from_raw(
    *,
    candidate_ref: ArtifactRef,
    loop_id: str,
    contract: StrategicSCM,
    payoff_tables: dict[str, FiniteStrategicPayoffTable],
    macro_payoff_tables: dict[str, FiniteStrategicPayoffTable] | None,
    abstraction_certificate: AbstractionCertificate | None,
    baseline_policy_value: float | None,
    strategic_summary: Mapping[str, Any] | None,
) -> ChallengeSuiteResult:
    base_case = ChallengeCase(
        case_id="baseline_declared_hierarchy",
        challenge_family="strategic_gaming",
        expected_outcome="declared_hierarchy_without_static_fallback",
        severity="high",
    )
    base_result = solve_strategic_response(
        contract,
        payoff_tables,
        baseline_policy_value=baseline_policy_value,
        abstraction_certificate=abstraction_certificate,
        macro_payoff_tables=macro_payoff_tables,
    )
    case_results = [
        build_challenge_case_result(
            case=base_case,
            passed=_result_uses_declared_hierarchy(base_result),
            summary=_hierarchy_summary(base_result),
            metadata={
                "fallback_mode": base_result.fallback_mode.value,
                "blocked_reason": base_result.blocked_reason,
            },
        )
    ]

    budget_case = ChallengeCase(
        case_id="budget_exhaustion_blocks_cleanly",
        challenge_family="strategic_gaming",
        expected_outcome="blocked_without_static_fallback",
        severity="critical",
    )
    exhausted_contract = contract.model_copy(
        update={
            "compute_budget": contract.compute_budget.model_copy(
                update={"max_sim_runs": 0.0}
            )
        }
    )
    budget_result = solve_strategic_response(
        exhausted_contract,
        payoff_tables,
        baseline_policy_value=baseline_policy_value,
        abstraction_certificate=abstraction_certificate,
        macro_payoff_tables=macro_payoff_tables,
    )
    budget_reason = str(budget_result.blocked_reason or "")
    case_results.append(
        build_challenge_case_result(
            case=budget_case,
            passed=(
                budget_result.fallback_mode is StrategicFallbackMode.BLOCKED
                and ("budget" in budget_reason or "compute" in budget_reason)
            ),
            summary=(
                "Budget exhaustion blocked strategic solving without a silent static fallback."
                if budget_result.fallback_mode is StrategicFallbackMode.BLOCKED
                else "Budget exhaustion did not block the strategic solver as expected."
            ),
            metadata={
                "fallback_mode": budget_result.fallback_mode.value,
                "blocked_reason": budget_result.blocked_reason,
            },
        )
    )

    if strategic_summary is not None:
        summary_case = ChallengeCase(
            case_id="observed_summary_hierarchy_audit",
            challenge_family="strategic_gaming",
            expected_outcome="no_silent_static_fallback",
            severity="high",
        )
        summary_passed = _summary_uses_declared_hierarchy(strategic_summary)
        case_results.append(
            build_challenge_case_result(
                case=summary_case,
                passed=summary_passed,
                summary=(
                    "Observed strategic summary stayed inside the declared fallback hierarchy."
                    if summary_passed
                    else "Observed strategic summary suggests a silent fallback outside the declared hierarchy."
                ),
                metadata={
                    "fallback_mode": str(
                        strategic_summary.get("fallback_mode")
                        or (strategic_summary.get("closure_summary") or {}).get("mode")
                        or ""
                    )
                },
            )
        )

    return build_challenge_suite_result(
        suite_id=STRATEGIC_GAMING_SUITE_ID,
        suite_version="1.0",
        candidate_ref=candidate_ref,
        loop_id=loop_id,
        challenge_family="strategic_gaming",
        case_results=case_results,
        primary_failure_rate_name="silent_static_fallback_rate",
        vulnerability_type=VulnerabilityType.COMBINATORIAL,
        metadata={"suite_origin": "raw_inputs"},
    )


def _build_multiplicity_suite_from_raw(
    *,
    candidate_ref: ArtifactRef,
    loop_id: str,
    contract: StrategicSCM,
    payoff_tables: dict[str, FiniteStrategicPayoffTable],
    baseline_policy_value: float | None,
    strategic_summary: Mapping[str, Any] | None,
) -> ChallengeSuiteResult:
    multiplicity_case = ChallengeCase(
        case_id="synthetic_multi_equilibrium_surface",
        challenge_family="multiplicity_disclosure",
        expected_outcome="explicit_multiplicity_or_bounds_disclosure",
        severity="critical",
    )
    uniform_tables = {
        agent: table.model_copy(update={"payoffs": {key: 1.0 for key in table.payoffs}})
        for agent, table in payoff_tables.items()
    }
    multiplicity_result = solve_strategic_response(
        contract,
        uniform_tables,
        baseline_policy_value=baseline_policy_value,
    )
    case_results = [
        build_challenge_case_result(
            case=multiplicity_case,
            passed=_result_has_multiplicity_disclosure(multiplicity_result),
            summary=(
                "Synthetic multiplicity case disclosed either equilibrium multiplicity, bounds, or a block reason."
                if _result_has_multiplicity_disclosure(multiplicity_result)
                else "Synthetic multiplicity case did not disclose equilibrium multiplicity or fallback bounds."
            ),
            metadata={
                "fallback_mode": multiplicity_result.fallback_mode.value,
                "is_disclosure_failure": not _result_has_multiplicity_disclosure(multiplicity_result),
            },
        )
    ]

    if strategic_summary is not None:
        observed_case = ChallengeCase(
            case_id="observed_summary_disclosure_audit",
            challenge_family="multiplicity_disclosure",
            expected_outcome="no_undisclosed_multiplicity",
            severity="high",
        )
        summary_passed = _summary_has_multiplicity_disclosure(strategic_summary)
        case_results.append(
            build_challenge_case_result(
                case=observed_case,
                passed=summary_passed,
                summary=(
                    "Observed strategic summary exposed multiplicity-sensitive information."
                    if summary_passed
                    else "Observed strategic summary appears to hide multiplicity-sensitive behavior."
                ),
                metadata={"is_disclosure_failure": not summary_passed},
            )
        )

    return build_challenge_suite_result(
        suite_id=MULTIPLICITY_DISCLOSURE_SUITE_ID,
        suite_version="1.0",
        candidate_ref=candidate_ref,
        loop_id=loop_id,
        challenge_family="multiplicity_disclosure",
        case_results=case_results,
        primary_failure_rate_name="undisclosed_multiplicity_rate",
        vulnerability_type=VulnerabilityType.COMBINATORIAL,
        metadata={"suite_origin": "raw_inputs"},
    )


def _build_strategic_gaming_suite_from_summary(
    *,
    candidate_ref: ArtifactRef,
    loop_id: str,
    strategic_summary: Mapping[str, Any],
) -> ChallengeSuiteResult:
    case = ChallengeCase(
        case_id="observed_summary_hierarchy_audit",
        challenge_family="strategic_gaming",
        expected_outcome="declared_hierarchy_without_static_fallback",
        severity="high",
    )
    passed = _summary_uses_declared_hierarchy(strategic_summary)
    return build_challenge_suite_result(
        suite_id=STRATEGIC_GAMING_SUITE_ID,
        suite_version="1.0",
        candidate_ref=candidate_ref,
        loop_id=loop_id,
        challenge_family="strategic_gaming",
        case_results=[
            build_challenge_case_result(
                case=case,
                passed=passed,
                summary=(
                    "Observed strategic summary stayed inside the declared fallback hierarchy."
                    if passed
                    else "Observed strategic summary suggests a silent static or out-of-scope fallback."
                ),
            )
        ],
        primary_failure_rate_name="silent_static_fallback_rate",
        vulnerability_type=VulnerabilityType.COMBINATORIAL,
        metadata={"suite_origin": "summary_audit"},
    )


def _build_multiplicity_suite_from_summary(
    *,
    candidate_ref: ArtifactRef,
    loop_id: str,
    strategic_summary: Mapping[str, Any],
) -> ChallengeSuiteResult:
    case = ChallengeCase(
        case_id="observed_summary_disclosure_audit",
        challenge_family="multiplicity_disclosure",
        expected_outcome="no_undisclosed_multiplicity",
        severity="high",
    )
    passed = _summary_has_multiplicity_disclosure(strategic_summary)
    return build_challenge_suite_result(
        suite_id=MULTIPLICITY_DISCLOSURE_SUITE_ID,
        suite_version="1.0",
        candidate_ref=candidate_ref,
        loop_id=loop_id,
        challenge_family="multiplicity_disclosure",
        case_results=[
            build_challenge_case_result(
                case=case,
                passed=passed,
                summary=(
                    "Observed strategic summary exposed multiplicity-sensitive information."
                    if passed
                    else "Observed strategic summary appears to hide multiplicity-sensitive behavior."
                ),
                metadata={"is_disclosure_failure": not passed},
            )
        ],
        primary_failure_rate_name="undisclosed_multiplicity_rate",
        vulnerability_type=VulnerabilityType.COMBINATORIAL,
        metadata={"suite_origin": "summary_audit"},
    )


def _coerce_strategic_contract(payload: Any) -> StrategicSCM | None:
    if payload is None:
        return None
    try:
        return payload if isinstance(payload, StrategicSCM) else StrategicSCM.model_validate(payload)
    except Exception:
        return None


def _coerce_payoff_tables(payload: Any) -> dict[str, FiniteStrategicPayoffTable] | None:
    if payload is None:
        return None
    if not isinstance(payload, Mapping) or not payload:
        return None
    tables: dict[str, FiniteStrategicPayoffTable] = {}
    try:
        for agent, table_payload in payload.items():
            tables[str(agent)] = (
                table_payload
                if isinstance(table_payload, FiniteStrategicPayoffTable)
                else FiniteStrategicPayoffTable.model_validate(table_payload)
            )
    except Exception:
        return None
    return tables


def _extract_baseline_policy_value(params: Mapping[str, Any]) -> float | None:
    for key in ("baseline_policy_value", "policy_value", "selection_score"):
        value = params.get(key)
        try:
            if value is not None:
                return float(value)
        except Exception:
            continue
    return None


def _result_uses_declared_hierarchy(result: StrategicSolveResult) -> bool:
    return (
        result.fallback_mode in _ALLOWED_FALLBACK_MODES
        and not _contains_static_fallback_token(result.blocked_reason)
        and not _contains_static_fallback_token(result.equilibrium_selection_dependence)
        and not _contains_static_fallback_token(result.closure_summary)
    )


def _hierarchy_summary(result: StrategicSolveResult) -> str:
    if _result_uses_declared_hierarchy(result):
        return (
            "Strategic solver respected the declared fallback hierarchy "
            f"via '{result.fallback_mode.value}'."
        )
    return "Strategic solver suggested an out-of-hierarchy or silent static fallback."


def _result_has_multiplicity_disclosure(result: StrategicSolveResult) -> bool:
    return bool(
        result.multiplicity_note
        or result.equilibrium_profiles
        or result.bounds is not None
        or result.blocked_reason
    )


def _summary_uses_declared_hierarchy(summary: Mapping[str, Any]) -> bool:
    fallback_mode = str(
        summary.get("fallback_mode") or (summary.get("closure_summary") or {}).get("mode") or ""
    ).strip()
    if fallback_mode not in {mode.value for mode in _ALLOWED_FALLBACK_MODES}:
        return False
    return not _contains_static_fallback_token(summary)


def _summary_has_multiplicity_disclosure(summary: Mapping[str, Any]) -> bool:
    closure_summary = summary.get("closure_summary") if isinstance(summary.get("closure_summary"), Mapping) else {}
    equilibrium_count = closure_summary.get("equilibrium_count")
    try:
        multiplicity_signaled = int(equilibrium_count) > 1
    except Exception:
        multiplicity_signaled = False
    multiplicity_signaled = multiplicity_signaled or "tie_breaking" in str(
        summary.get("equilibrium_selection_dependence") or ""
    )
    disclosure_present = bool(
        summary.get("multiplicity_note")
        or summary.get("equilibrium_profiles")
        or summary.get("bounds")
        or summary.get("blocked_reason")
    )
    return disclosure_present or not multiplicity_signaled


def _contains_static_fallback_token(payload: Any) -> bool:
    if payload is None:
        return False
    if isinstance(payload, Mapping):
        return any(_contains_static_fallback_token(value) for value in payload.values())
    if isinstance(payload, (list, tuple, set)):
        return any(_contains_static_fallback_token(item) for item in payload)
    normalized = str(payload).strip().lower()
    return "static" in normalized and "ate" in normalized


__all__ = ["run_strategic_challenge_suites"]
