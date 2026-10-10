"""Normative arbitration binding and policy calculations."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts import Metrics, SimulationResult
from polisyos.ir.analytics import DistributionalReport
from polisyos.ir.analytics.normative_arbitration import (
    ArbitrationOption,
    HardConstraintAuditEntry,
    NormativeAuditStatus,
    NormativeModelCompleteness,
    PolicyOutcome,
    RightsAuditEntry,
    StakeholderUtilitySummary,
)
from polisyos.ir.analytics.uncertainty import load_simulation_result_uncertainty_admission
from polisyos.ir.governance.problem_frame import (
    ConstraintSpec,
    NormativeArbitrationPolicy,
    NormativeComparisonTarget,
    NormativeFrame,
    NormativeOutcomeChannel,
    ProblemFrame,
    StakeholderOutcomeBinding,
    StakeholderSpec,
    UtilityDirection,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path

logger = get_logger("polisyos.scientist.nodes.builtins.governance.run_normative_arbitration")

_NORMATIVE_ARTIFACT_ERRORS = (
    AttributeError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)


@dataclass(frozen=True)
class _ResolvedBindingValue:
    binding: StakeholderOutcomeBinding
    baseline_value: float
    proposal_value: float


@dataclass(frozen=True)
class _BindingValueContext:
    ctx: ExecutionContext
    metrics: Metrics | None
    simulation_result_ref: ArtifactRef | None
    distributional_report: DistributionalReport | None
    distributional_map: dict[str, float]
    synthesized_map: dict[str, float]


def _stakeholder_outcome_key(stakeholder: StakeholderSpec) -> str:
    raw = stakeholder.attributes.get("cohort_id") or stakeholder.attributes.get(
        "distributional_cohort_id"
    )
    if isinstance(raw, str) and raw:
        return raw
    return stakeholder.stakeholder_id


def _resolve_binding_values(
    *,
    ctx: ExecutionContext,
    frame: NormativeFrame,
    problem_frame: ProblemFrame,
    metrics: Metrics | None,
    simulation_result: SimulationResult | None,
    simulation_result_ref: ArtifactRef | None,
    distributional_report: DistributionalReport | None,
) -> tuple[dict[str, _ResolvedBindingValue], list[str]]:
    context = _BindingValueContext(
        ctx=ctx,
        metrics=metrics,
        simulation_result_ref=simulation_result_ref,
        distributional_report=distributional_report,
        distributional_map=_build_distributional_impact_map(distributional_report),
        synthesized_map=_build_synthesized_impact_map(problem_frame, distributional_report),
    )
    warnings: list[str] = []
    values: dict[str, _ResolvedBindingValue] = {}

    for binding in frame.stakeholder_bindings:
        proposal_value, binding_warnings = _resolve_binding_proposal_value(binding, context)
        warnings.extend(binding_warnings)

        if proposal_value is None or not math.isfinite(proposal_value):
            continue
        values[binding.binding_id] = _ResolvedBindingValue(
            binding=binding,
            baseline_value=0.0,
            proposal_value=proposal_value,
        )

    return values, _dedupe_strings(warnings)


def _resolve_binding_proposal_value(
    binding: StakeholderOutcomeBinding,
    context: _BindingValueContext,
) -> tuple[float | None, list[str]]:
    resolver = _BINDING_VALUE_RESOLVERS.get(binding.channel)
    if resolver is None:
        return None, []
    return resolver(binding, context)


def _resolve_simulation_metric(
    binding: StakeholderOutcomeBinding,
    context: _BindingValueContext,
) -> tuple[float | None, list[str]]:
    value = _metric_value(context.metrics, binding.outcome_key)
    warnings = [f"missing_binding_value:{binding.binding_id}"] if value is None else []
    return value, warnings


def _resolve_distributional_net_impact(
    binding: StakeholderOutcomeBinding,
    context: _BindingValueContext,
) -> tuple[float | None, list[str]]:
    value = context.distributional_map.get(binding.outcome_key)
    warnings = [f"missing_binding_value:{binding.binding_id}"] if value is None else []
    return value, warnings


def _resolve_distributional_losers_share(
    binding: StakeholderOutcomeBinding,
    context: _BindingValueContext,
) -> tuple[float | None, list[str]]:
    report = context.distributional_report
    value = report.winners_losers.total_losers_share if report is not None else None
    return value, []


def _resolve_distributional_winners_share(
    binding: StakeholderOutcomeBinding,
    context: _BindingValueContext,
) -> tuple[float | None, list[str]]:
    report = context.distributional_report
    value = report.winners_losers.total_winners_share if report is not None else None
    return value, []


def _resolve_distributional_gini_delta(
    binding: StakeholderOutcomeBinding,
    context: _BindingValueContext,
) -> tuple[float | None, list[str]]:
    report = context.distributional_report
    value = report.overall_gini_delta if report is not None else None
    return value, []


def _resolve_uncertainty_ratio_binding(
    binding: StakeholderOutcomeBinding,
    context: _BindingValueContext,
) -> tuple[float | None, list[str]]:
    value, limitations = _uncertainty_ratio(
        context.ctx,
        context.simulation_result_ref,
        binding.outcome_key,
    )
    warnings = [
        f"uncertainty_admission_limited:{binding.binding_id}:{reason}" for reason in limitations
    ]
    if value is None:
        warnings.append(f"missing_binding_value:{binding.binding_id}")
    return value, warnings


def _resolve_synthesized_binding(
    binding: StakeholderOutcomeBinding,
    context: _BindingValueContext,
) -> tuple[float | None, list[str]]:
    return context.synthesized_map.get(binding.outcome_key), []


_BindingValueResolver = Callable[
    [StakeholderOutcomeBinding, _BindingValueContext],
    tuple[float | None, list[str]],
]
_BINDING_VALUE_RESOLVERS: dict[NormativeOutcomeChannel, _BindingValueResolver] = {
    NormativeOutcomeChannel.SIMULATION_METRIC: _resolve_simulation_metric,
    NormativeOutcomeChannel.DISTRIBUTIONAL_NET_IMPACT: _resolve_distributional_net_impact,
    NormativeOutcomeChannel.DISTRIBUTIONAL_LOSERS_SHARE: _resolve_distributional_losers_share,
    NormativeOutcomeChannel.DISTRIBUTIONAL_WINNERS_SHARE: _resolve_distributional_winners_share,
    NormativeOutcomeChannel.DISTRIBUTIONAL_OVERALL_GINI_DELTA: _resolve_distributional_gini_delta,
    NormativeOutcomeChannel.UNCERTAINTY_CI_WIDTH_RATIO: _resolve_uncertainty_ratio_binding,
    NormativeOutcomeChannel.SYNTHESIZED: _resolve_synthesized_binding,
}


def _build_distributional_impact_map(
    distributional_report: DistributionalReport | None,
) -> dict[str, float]:
    if distributional_report is None:
        return {}
    entries = (
        distributional_report.winners_losers.winners
        + distributional_report.winners_losers.losers
        + distributional_report.winners_losers.neutral
    )
    return {entry.cohort_id: float(entry.net_impact) for entry in entries}


def _build_synthesized_impact_map(
    problem_frame: ProblemFrame,
    distributional_report: DistributionalReport | None,
) -> dict[str, float]:
    impact_map = _build_distributional_impact_map(distributional_report)
    for stakeholder in problem_frame.stakeholders:
        key = _stakeholder_outcome_key(stakeholder)
        if key in impact_map:
            continue
        direction = stakeholder.impact_direction
        if direction == "positive":
            impact_map[key] = 1.0
        elif direction == "negative":
            impact_map[key] = -1.0
        elif direction == "mixed" or direction == "neutral":
            impact_map[key] = 0.0
    return impact_map


def _metric_value(metrics: Metrics | None, key: str) -> float | None:
    if metrics is None:
        return None
    value = metrics.values.get(key)
    return _coerce_float(value)


def _uncertainty_ratio(
    ctx: ExecutionContext,
    simulation_result_ref: ArtifactRef | None,
    metric_id: str,
) -> tuple[float | None, tuple[str, ...]]:
    if simulation_result_ref is None:
        return None, ("simulation_result_ref_missing",)
    try:
        admission = load_simulation_result_uncertainty_admission(
            _ensure_ir_artifact_store(ctx.store),
            simulation_result_ref,
            metric_id,
        )
    except _NORMATIVE_ARTIFACT_ERRORS as exc:
        emit_degraded_path(
            component="scientist.run_normative_arbitration",
            operation="admit_simulation_uncertainty",
            reason="uncertainty_envelope_admission_failed",
            exc=exc,
            details={
                "metric_id": metric_id,
            },
            log=logger,
            metrics=ctx.metrics,
        )
        return None, ("persisted_uncertainty_admission_failed",)
    if not admission.admitted or admission.envelope is None:
        return None, admission.limitation_codes
    envelope = admission.envelope
    point = envelope.point_estimate
    lower, upper = envelope.confidence_interval
    width = upper - lower
    denom = max(abs(point), 1.0)
    return width / denom, ()


def _compute_stakeholder_utilities(
    *,
    problem_frame: ProblemFrame,
    frame: NormativeFrame,
    binding_values: dict[str, _ResolvedBindingValue],
) -> tuple[list[StakeholderUtilitySummary], list[str]]:
    warnings: list[str] = []
    stakeholder_ids = {stakeholder.stakeholder_id for stakeholder in problem_frame.stakeholders}
    stakeholder_ids.update(term.stakeholder_id for term in frame.utility_terms)

    utilities: list[StakeholderUtilitySummary] = []
    for stakeholder_id in sorted(stakeholder_ids):
        terms = [term for term in frame.utility_terms if term.stakeholder_id == stakeholder_id]
        baseline_utility = 0.0
        proposal_utility = 0.0
        welfare_weight = 1.0

        if not terms:
            warnings.append(f"missing_utility_terms:{stakeholder_id}")
            utilities.append(
                StakeholderUtilitySummary(
                    stakeholder_id=stakeholder_id,
                    baseline_utility=0.0,
                    proposal_utility=0.0,
                    delta_utility=0.0,
                    welfare_weight=1.0,
                    notes=["no_utility_terms"],
                )
            )
            continue

        weight_accumulator = 0.0
        for term in terms:
            term_binding_refs = term.binding_refs or [
                binding.binding_id
                for binding in frame.stakeholder_bindings
                if binding.stakeholder_id == stakeholder_id
            ]
            sign = 1.0 if term.direction == UtilityDirection.MAXIMIZE else -1.0
            coefficient = float(term.coefficient)
            term_weight = float(term.welfare_weight)
            weight_accumulator += term_weight
            for binding_ref in term_binding_refs:
                binding = binding_values.get(binding_ref)
                if binding is None:
                    warnings.append(f"missing_utility_binding:{term.term_id}:{binding_ref}")
                    continue
                baseline_utility += sign * coefficient * binding.baseline_value
                proposal_utility += sign * coefficient * binding.proposal_value
        if weight_accumulator > 0:
            welfare_weight = weight_accumulator

        utilities.append(
            StakeholderUtilitySummary(
                stakeholder_id=stakeholder_id,
                baseline_utility=baseline_utility,
                proposal_utility=proposal_utility,
                delta_utility=proposal_utility - baseline_utility,
                welfare_weight=welfare_weight,
            )
        )

    return utilities, _dedupe_strings(warnings)


def _audit_rights(
    *,
    problem_frame: ProblemFrame,
    frame: NormativeFrame,
    binding_values: dict[str, _ResolvedBindingValue],
    utility_summaries: list[StakeholderUtilitySummary],
) -> tuple[list[RightsAuditEntry], list[str]]:
    utility_by_stakeholder = {item.stakeholder_id: item for item in utility_summaries}
    warnings: list[str] = []
    audits: list[RightsAuditEntry] = []
    for right in frame.rights_catalog:
        observed_value: float | int | str | bool | None = None
        status = NormativeAuditStatus.UNEVALUATED
        notes: list[str] = []
        if right.binding_ref is not None:
            binding = binding_values.get(right.binding_ref)
            if binding is None:
                warnings.append(f"missing_right_binding:{right.right_id}")
            else:
                observed_value = _value_for_target(binding, right.compare_to)
        else:
            utility = utility_by_stakeholder.get(right.stakeholder_id)
            if utility is None:
                warnings.append(f"missing_right_utility:{right.right_id}")
            else:
                if right.compare_to == NormativeComparisonTarget.BASELINE:
                    observed_value = utility.baseline_utility
                elif right.compare_to == NormativeComparisonTarget.PROPOSAL:
                    observed_value = utility.proposal_utility
                else:
                    observed_value = utility.delta_utility

        if observed_value is not None:
            try:
                passed = _compare(observed_value, right.operator, right.threshold)
                status = NormativeAuditStatus.SATISFIED if passed else NormativeAuditStatus.VIOLATED
            except TypeError:
                status = NormativeAuditStatus.UNEVALUATED
                notes.append("comparison_type_mismatch")
                warnings.append(f"unevaluable_right:{right.right_id}")

        audits.append(
            RightsAuditEntry(
                right_id=right.right_id,
                stakeholder_id=right.stakeholder_id,
                binding_ref=right.binding_ref,
                status=status,
                compare_to=right.compare_to.value,
                operator=right.operator,
                threshold=_normalize_scalar(right.threshold),
                observed_value=_normalize_scalar(observed_value),
                notes=notes + (["soft_right"] if not right.hard else []),
            )
        )

    return audits, _dedupe_strings(warnings)


def _audit_hard_constraints(
    *,
    problem_frame: ProblemFrame,
    frame: NormativeFrame,
    metrics: Metrics | None,
) -> tuple[list[HardConstraintAuditEntry], list[str]]:
    constraints = {
        constraint.constraint_id: constraint
        for constraint in problem_frame.hard_constraints
        if constraint.constraint_id in frame.hard_constraint_refs
    }
    warnings: list[str] = []
    audits: list[HardConstraintAuditEntry] = []
    for constraint_id in frame.hard_constraint_refs:
        constraint = constraints.get(constraint_id)
        if constraint is None:
            warnings.append(f"missing_hard_constraint:{constraint_id}")
            audits.append(
                HardConstraintAuditEntry(
                    constraint_id=constraint_id,
                    status=NormativeAuditStatus.UNEVALUATED,
                    notes=["constraint_missing_from_problem_frame"],
                )
            )
            continue
        proposal_value = _constraint_value(metrics, constraint)
        status = NormativeAuditStatus.UNEVALUATED
        notes: list[str] = []
        if proposal_value is None:
            warnings.append(f"unevaluable_hard_constraint:{constraint.constraint_id}")
            notes.append("proposal_value_missing")
        elif constraint.operator is None:
            warnings.append(f"unevaluable_hard_constraint:{constraint.constraint_id}")
            notes.append("operator_missing")
        else:
            try:
                passed = _compare(proposal_value, constraint.operator, constraint.value)
                status = NormativeAuditStatus.SATISFIED if passed else NormativeAuditStatus.VIOLATED
            except TypeError:
                notes.append("comparison_type_mismatch")
                warnings.append(f"unevaluable_hard_constraint:{constraint.constraint_id}")

        audits.append(
            HardConstraintAuditEntry(
                constraint_id=constraint.constraint_id,
                status=status,
                operator=constraint.operator,
                threshold=_normalize_scalar(constraint.value),
                proposal_value=_normalize_scalar(proposal_value),
                baseline_value=None,
                notes=notes,
            )
        )
    return audits, _dedupe_strings(warnings)


def _constraint_value(
    metrics: Metrics | None, constraint: ConstraintSpec
) -> float | int | str | bool | None:
    if metrics is None:
        return None
    metric_key = constraint.slot_id or constraint.constraint_id
    return metrics.values.get(metric_key)


def _evaluate_policies(
    *,
    frame: NormativeFrame,
    utility_summaries: list[StakeholderUtilitySummary],
    rights_audit: list[RightsAuditEntry],
    hard_constraint_audit: list[HardConstraintAuditEntry],
) -> list[PolicyOutcome]:
    summary = _policy_evaluation_summary(
        utility_summaries=utility_summaries,
        rights_audit=rights_audit,
        hard_constraint_audit=hard_constraint_audit,
    )
    return [_evaluate_policy(policy, summary) for policy in frame.enabled_policies]


@dataclass(frozen=True)
class _PolicyEvaluationSummary:
    rights_violations: int
    hard_constraint_violations: int
    weighted_delta: float
    proposal_worst: float
    baseline_worst: float
    losers_count: int
    winners_count: int


def _policy_evaluation_summary(
    *,
    utility_summaries: list[StakeholderUtilitySummary],
    rights_audit: list[RightsAuditEntry],
    hard_constraint_audit: list[HardConstraintAuditEntry],
) -> _PolicyEvaluationSummary:
    return _PolicyEvaluationSummary(
        rights_violations=sum(
            1
            for item in rights_audit
            if item.status == NormativeAuditStatus.VIOLATED and "soft_right" not in item.notes
        ),
        hard_constraint_violations=sum(
            1 for item in hard_constraint_audit if item.status == NormativeAuditStatus.VIOLATED
        ),
        weighted_delta=sum(item.delta_utility * item.welfare_weight for item in utility_summaries),
        proposal_worst=min((item.proposal_utility for item in utility_summaries), default=0.0),
        baseline_worst=min((item.baseline_utility for item in utility_summaries), default=0.0),
        losers_count=sum(1 for item in utility_summaries if item.delta_utility < -1e-9),
        winners_count=sum(1 for item in utility_summaries if item.delta_utility > 1e-9),
    )


def _evaluate_policy(
    policy: NormativeArbitrationPolicy,
    summary: _PolicyEvaluationSummary,
) -> PolicyOutcome:
    if policy == NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS:
        selected_option, rationale, metrics = _lexicographic_rights_outcome(summary)
    elif policy == NormativeArbitrationPolicy.WEIGHTED_WELFARE:
        selected_option, rationale, metrics = _weighted_welfare_outcome(summary)
    elif policy == NormativeArbitrationPolicy.MAX_MIN_HARM:
        selected_option, rationale, metrics = _max_min_harm_outcome(summary)
    else:
        selected_option, rationale, metrics = _pareto_outcome(summary)
    return PolicyOutcome(
        policy=policy,
        selected_option=selected_option,
        confidence=None,
        rationale=rationale,
        metrics=metrics,
    )


def _lexicographic_rights_outcome(
    summary: _PolicyEvaluationSummary,
) -> tuple[ArbitrationOption, str, dict[str, float | int]]:
    if summary.rights_violations > 0 or summary.hard_constraint_violations > 0:
        selected_option = ArbitrationOption.BASELINE
        rationale = "proposal violates explicit rights or normative hard constraints"
    elif summary.weighted_delta > 1e-9:
        selected_option = ArbitrationOption.PROPOSAL
        rationale = "no rights blockers and weighted welfare favors proposal"
    elif summary.weighted_delta < -1e-9:
        selected_option = ArbitrationOption.BASELINE
        rationale = "no rights blockers but weighted welfare favors baseline"
    else:
        selected_option = ArbitrationOption.INDETERMINATE
        rationale = "rights tie and welfare tie"
    metrics = {
        "rights_violations": summary.rights_violations,
        "hard_constraint_violations": summary.hard_constraint_violations,
        "weighted_delta": summary.weighted_delta,
    }
    return selected_option, rationale, metrics


def _weighted_welfare_outcome(
    summary: _PolicyEvaluationSummary,
) -> tuple[ArbitrationOption, str, dict[str, float | int]]:
    if summary.weighted_delta > 1e-9:
        selected_option = ArbitrationOption.PROPOSAL
    elif summary.weighted_delta < -1e-9:
        selected_option = ArbitrationOption.BASELINE
    else:
        selected_option = ArbitrationOption.INDETERMINATE
    rationale = f"aggregate weighted welfare delta={summary.weighted_delta:.6f}"
    return selected_option, rationale, {"weighted_delta": summary.weighted_delta}


def _max_min_harm_outcome(
    summary: _PolicyEvaluationSummary,
) -> tuple[ArbitrationOption, str, dict[str, float | int]]:
    if summary.proposal_worst > summary.baseline_worst + 1e-9:
        selected_option = ArbitrationOption.PROPOSAL
    elif summary.proposal_worst < summary.baseline_worst - 1e-9:
        selected_option = ArbitrationOption.BASELINE
    else:
        selected_option = ArbitrationOption.INDETERMINATE
    rationale = (
        "choose option with better worst-case stakeholder utility "
        f"(proposal={summary.proposal_worst:.6f}, baseline={summary.baseline_worst:.6f})"
    )
    metrics = {
        "proposal_worst_utility": summary.proposal_worst,
        "baseline_worst_utility": summary.baseline_worst,
    }
    return selected_option, rationale, metrics


def _pareto_outcome(
    summary: _PolicyEvaluationSummary,
) -> tuple[ArbitrationOption, str, dict[str, float | int]]:
    if summary.losers_count > 0:
        selected_option = ArbitrationOption.BASELINE
        rationale = "proposal is not Pareto-admissible because some stakeholders lose"
    elif summary.winners_count > 0:
        selected_option = ArbitrationOption.PROPOSAL
        rationale = "proposal is Pareto-admissible and strictly helps at least one stakeholder"
    else:
        selected_option = ArbitrationOption.INDETERMINATE
        rationale = "proposal is Pareto-neutral"
    metrics = {
        "losers_count": summary.losers_count,
        "winners_count": summary.winners_count,
    }
    return selected_option, rationale, metrics


def _resolve_model_completeness(
    *,
    source: str,
    warnings: list[str],
    rights_audit: list[RightsAuditEntry],
    hard_constraint_audit: list[HardConstraintAuditEntry],
) -> NormativeModelCompleteness:
    if source != "declared":
        return NormativeModelCompleteness.PARTIAL
    if warnings:
        return NormativeModelCompleteness.PARTIAL
    if any(item.status == NormativeAuditStatus.UNEVALUATED for item in rights_audit):
        return NormativeModelCompleteness.PARTIAL
    if any(item.status == NormativeAuditStatus.UNEVALUATED for item in hard_constraint_audit):
        return NormativeModelCompleteness.PARTIAL
    return NormativeModelCompleteness.COMPLETE


def _value_for_target(
    binding: _ResolvedBindingValue,
    compare_to: NormativeComparisonTarget,
) -> float:
    if compare_to == NormativeComparisonTarget.BASELINE:
        return binding.baseline_value
    if compare_to == NormativeComparisonTarget.PROPOSAL:
        return binding.proposal_value
    return binding.proposal_value - binding.baseline_value


def _compare(
    left: float | int | str | bool,
    operator: str,
    right: Decimal | float | int | str | bool,
) -> bool:
    if isinstance(right, Decimal):
        right = float(right)
    if isinstance(left, Decimal):
        left = float(left)
    if operator == "<":
        return left < right
    if operator == "<=":
        return left <= right
    if operator == "==":
        return left == right
    if operator == "!=":
        return left != right
    if operator == ">=":
        return left >= right
    if operator == ">":
        return left > right
    raise TypeError(f"Unsupported operator {operator}")


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, Decimal):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


def _normalize_scalar(value: Any) -> float | int | str | bool | None:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (float, int, str, bool)) or value is None:
        return value
    return str(value)


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
