"""Public governance run normative arbitration module API."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.foundry import Metrics, SimulationResult
from polisyos.core.contracts.lex import LegalReport
from polisyos.ir.analytics.distributional import DistributionalReport, load_distributional_report
from polisyos.ir.analytics.normative_arbitration import (
    ArbitrationOption,
    HardConstraintAuditEntry,
    NormativeArbitrationResult,
    NormativeAuditStatus,
    NormativeModelCompleteness,
    NormativeProvenance,
    OptionOutcomeMatrix,
    PolicyOutcome,
    ResidualDissent,
    RightsAuditEntry,
    StakeholderUtilitySummary,
    TradeoffCertificate,
    persist_normative_arbitration_result,
)
from polisyos.ir.artifacts import InputRef
from polisyos.ir.governance.problem_frame import (
    ConstraintSpec,
    NormativeArbitrationPolicy,
    NormativeComparisonTarget,
    NormativeFrame,
    NormativeOutcomeChannel,
    ProblemFrame,
    StakeholderOutcomeBinding,
    StakeholderSpec,
    StakeholderUtilityTerm,
    UtilityDirection,
)
from polisyos.ir.refs import DistributionalReportRef
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_LEGAL_REPORT_REF,
)

logger = get_logger(__name__)
_NORMATIVE_ARTIFACT_ERRORS = (
    AttributeError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_normative_arbitration@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Normative Arbitration",
    description="Formalize normative tradeoffs between proposal and baseline.",
    tags=["builtin", "governance", "normative"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        f"inputs.{INPUT_TRINITY_BUNDLE_REF}",
        f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_METRICS_REF}",
        f"artifacts_index.{ARTIFACT_DISTRIBUTIONAL_REPORT_REF}",
        f"reports_index.{REPORT_LEGAL_REPORT_REF}",
    ],
    state_writes=[f"artifacts_index.{ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF}"],
    produces=[ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF],
)


@dataclass(frozen=True)
class _ResolvedBindingValue:
    binding: StakeholderOutcomeBinding
    baseline_value: float
    proposal_value: float


@dataclass(frozen=True)
class _ResolvedNormativeModel:
    frame: NormativeFrame
    source: str
    warnings: list[str]


@dataclass(frozen=True)
class RunNormativeArbitrationNode:
    """Run normative arbitration node implementation."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        trinity_ref = state.inputs.get(INPUT_TRINITY_BUNDLE_REF)
        if trinity_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info", message="No trinity_bundle_ref; skip normative arbitration"
                    )
                ],
            )

        try:
            trinity = TrinityBundle.model_validate(
                from_canonical_bytes(ctx.store.get_bytes(trinity_ref.artifact_id))
            )
        except _NORMATIVE_ARTIFACT_ERRORS as exc:
            emit_degraded_path(
                component="scientist.run_normative_arbitration",
                operation="load_trinity_bundle",
                reason="trinity_bundle_load_failed",
                exc=exc,
                details={"run_id": state.run_id},
                log=logger,
                metrics=ctx.metrics,
            )
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="warn",
                        message="Failed to parse trinity bundle for normative arbitration",
                    )
                ],
            )

        metrics = _load_metrics(ctx, state)
        simulation_result = _load_simulation_result(ctx, state)
        distributional_report = _load_distributional(ctx, state)
        _load_legal_report(ctx, state)

        if (
            _requires_explicit_normative_frame(state)
            and trinity.problem_frame.normative_frame is None
        ):
            return NodeOutcome(
                status="fail",
                state=state,
                events=[
                    NodeEvent(
                        level="error",
                        message=(
                            "Normative frame is required for serious execution profiles; "
                            "legacy synthesis is disabled."
                        ),
                    )
                ],
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message="Missing explicit normative frame for serious execution profile",
                    details={"execution_profile": state.execution_profile},
                ),
            )

        resolved_model = _resolve_normative_model(
            problem_frame=trinity.problem_frame,
            distributional_report=distributional_report,
        )
        binding_values, binding_warnings = _resolve_binding_values(
            ctx=ctx,
            frame=resolved_model.frame,
            problem_frame=trinity.problem_frame,
            metrics=metrics,
            simulation_result=simulation_result,
            distributional_report=distributional_report,
        )
        utility_summaries, utility_warnings = _compute_stakeholder_utilities(
            problem_frame=trinity.problem_frame,
            frame=resolved_model.frame,
            binding_values=binding_values,
        )
        rights_audit, rights_warnings = _audit_rights(
            problem_frame=trinity.problem_frame,
            frame=resolved_model.frame,
            binding_values=binding_values,
            utility_summaries=utility_summaries,
        )
        hard_constraint_audit, constraint_warnings = _audit_hard_constraints(
            problem_frame=trinity.problem_frame,
            frame=resolved_model.frame,
            metrics=metrics,
        )

        policy_outcomes = _evaluate_policies(
            frame=resolved_model.frame,
            utility_summaries=utility_summaries,
            rights_audit=rights_audit,
            hard_constraint_audit=hard_constraint_audit,
        )
        selected_policy = resolved_model.frame.default_policy
        selected_outcome = next(
            outcome for outcome in policy_outcomes if outcome.policy == selected_policy
        )

        winners = sorted(
            item.stakeholder_id for item in utility_summaries if item.delta_utility > 1e-9
        )
        losers = sorted(
            item.stakeholder_id for item in utility_summaries if item.delta_utility < -1e-9
        )
        residual_dissent = [
            ResidualDissent(
                policy=item.policy,
                preferred_option=item.selected_option,
                rationale=item.rationale,
            )
            for item in policy_outcomes
            if item.policy != selected_policy
            and item.selected_option != selected_outcome.selected_option
        ]

        warnings = _dedupe_strings(
            [
                *resolved_model.warnings,
                *binding_warnings,
                *utility_warnings,
                *rights_warnings,
                *constraint_warnings,
            ]
        )
        model_completeness = _resolve_model_completeness(
            source=resolved_model.source,
            warnings=warnings,
            rights_audit=rights_audit,
            hard_constraint_audit=hard_constraint_audit,
        )

        rights_violations = [
            item.right_id for item in rights_audit if item.status == NormativeAuditStatus.VIOLATED
        ]
        hard_constraint_violations = [
            item.constraint_id
            for item in hard_constraint_audit
            if item.status == NormativeAuditStatus.VIOLATED
        ]
        result = NormativeArbitrationResult(
            comparison_mode=resolved_model.frame.comparison_mode.value,
            model_completeness=model_completeness,
            option_matrix=[
                OptionOutcomeMatrix(
                    option=ArbitrationOption.BASELINE,
                    binding_values={
                        item.binding.binding_id: item.baseline_value
                        for item in binding_values.values()
                    },
                ),
                OptionOutcomeMatrix(
                    option=ArbitrationOption.PROPOSAL,
                    binding_values={
                        item.binding.binding_id: item.proposal_value
                        for item in binding_values.values()
                    },
                ),
            ],
            per_stakeholder_utility=utility_summaries,
            rights_audit=rights_audit,
            hard_constraint_audit=hard_constraint_audit,
            policy_outcomes=policy_outcomes,
            selected_policy=selected_policy,
            selected_option=selected_outcome.selected_option,
            winners=winners,
            losers=losers,
            residual_dissent=residual_dissent,
            warnings=warnings,
            tradeoff_certificate=TradeoffCertificate(
                selected_policy=selected_policy,
                selected_option=selected_outcome.selected_option,
                winners=winners,
                losers=losers,
                residual_dissent=residual_dissent,
                rights_violations=rights_violations,
                hard_constraint_violations=hard_constraint_violations,
                notes=_dedupe_strings(warnings),
            ),
            provenance=NormativeProvenance(
                trinity_bundle_ref=str(trinity_ref.artifact_id),
                distributional_report_ref=_ref_id(
                    state.artifacts_index.get(ARTIFACT_DISTRIBUTIONAL_REPORT_REF)
                ),
                legal_report_ref=_ref_id(state.reports_index.get(REPORT_LEGAL_REPORT_REF)),
                metrics_ref=_ref_id(state.artifacts_index.get(ARTIFACT_METRICS_REF)),
                simulation_result_ref=_ref_id(
                    state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
                ),
                uncertainty_refs=sorted(
                    str(ref.artifact_id)
                    for ref in (simulation_result.uncertainty_envelopes or {}).values()
                )
                if simulation_result is not None
                and simulation_result.uncertainty_envelopes is not None
                else [],
            ),
            metadata={
                "model_source": resolved_model.source,
                "default_policy": selected_policy.value,
                "enabled_policies": [
                    policy.value for policy in resolved_model.frame.enabled_policies
                ],
                "rights_violation_count": len(rights_violations),
                "hard_constraint_violation_count": len(hard_constraint_violations),
            },
        )

        inputs = _build_inputs(state, simulation_result=simulation_result)
        result_ref = persist_normative_arbitration_result(ctx.store, result, inputs=inputs)

        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.artifacts_index[ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF] = result_ref
        event_level = "warn" if warnings else "info"
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[result_ref],
            events=[
                NodeEvent(
                    level=event_level,
                    message=(
                        "Normative arbitration completed "
                        f"(policy={selected_policy.value}, option={selected_outcome.selected_option.value})"
                    ),
                )
            ],
        )


def _load_metrics(ctx: ExecutionContext, state: ExperimentState) -> Metrics | None:
    ref = state.artifacts_index.get(ARTIFACT_METRICS_REF)
    if ref is None:
        return None
    try:
        return Metrics.model_validate(from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id)))
    except _NORMATIVE_ARTIFACT_ERRORS as exc:
        emit_degraded_path(
            component="scientist.run_normative_arbitration",
            operation="load_metrics",
            reason="metrics_load_failed",
            exc=exc,
            details={"run_id": state.run_id},
            log=logger,
            metrics=ctx.metrics,
        )
        return None


def _load_simulation_result(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> SimulationResult | None:
    ref = state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
    if ref is None:
        return None
    try:
        return SimulationResult.model_validate(
            from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
        )
    except _NORMATIVE_ARTIFACT_ERRORS as exc:
        emit_degraded_path(
            component="scientist.run_normative_arbitration",
            operation="load_simulation_result",
            reason="simulation_result_load_failed",
            exc=exc,
            details={"run_id": state.run_id},
            log=logger,
            metrics=ctx.metrics,
        )
        return None


def _load_distributional(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> DistributionalReport | None:
    ref = state.artifacts_index.get(ARTIFACT_DISTRIBUTIONAL_REPORT_REF)
    if ref is None:
        return None
    try:
        return load_distributional_report(
            ctx.store,
            DistributionalReportRef(artifact_id=ref.artifact_id),
        )
    except _NORMATIVE_ARTIFACT_ERRORS as exc:
        emit_degraded_path(
            component="scientist.run_normative_arbitration",
            operation="load_distributional_report",
            reason="distributional_report_load_failed",
            exc=exc,
            details={"run_id": state.run_id},
            log=logger,
            metrics=ctx.metrics,
        )
        return None


def _load_legal_report(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> LegalReport | None:
    ref = state.reports_index.get(REPORT_LEGAL_REPORT_REF)
    if ref is None:
        return None
    try:
        return LegalReport.model_validate(
            from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
        )
    except _NORMATIVE_ARTIFACT_ERRORS as exc:
        emit_degraded_path(
            component="scientist.run_normative_arbitration",
            operation="load_legal_report",
            reason="legal_report_load_failed",
            exc=exc,
            details={"run_id": state.run_id},
            log=logger,
            metrics=ctx.metrics,
        )
        return None


def _resolve_normative_model(
    *,
    problem_frame: ProblemFrame,
    distributional_report: DistributionalReport | None,
) -> _ResolvedNormativeModel:
    if problem_frame.normative_frame is not None:
        return _ResolvedNormativeModel(
            frame=problem_frame.normative_frame,
            source="declared",
            warnings=[],
        )

    frame = _synthesize_legacy_normative_frame(problem_frame, distributional_report)
    return _ResolvedNormativeModel(
        frame=frame,
        source="legacy_synthesized",
        warnings=["legacy_normative_synthesizer_used"],
    )


def _requires_explicit_normative_frame(state: ExperimentState) -> bool:
    profile = (
        str(state.execution_profile or state.params.get("execution_profile") or "").strip().lower()
    )
    return profile in {"governed", "production"}


def _synthesize_legacy_normative_frame(
    problem_frame: ProblemFrame,
    distributional_report: DistributionalReport | None,
) -> NormativeFrame:
    stakeholders = list(problem_frame.stakeholders)
    if not stakeholders and distributional_report is not None:
        for entry in (
            distributional_report.winners_losers.winners
            + distributional_report.winners_losers.losers
            + distributional_report.winners_losers.neutral
        ):
            stakeholders.append(
                StakeholderSpec(
                    stakeholder_id=entry.cohort_id,
                    entity_type="agent",
                    role="distributional_cohort",
                    impact_direction=entry.impact_direction.value,
                    attributes={"cohort_id": entry.cohort_id},
                )
            )

    bindings: list[StakeholderOutcomeBinding] = []
    terms: list[StakeholderUtilityTerm] = []
    for stakeholder in stakeholders:
        binding_id = f"{stakeholder.stakeholder_id}_legacy_impact"
        bindings.append(
            StakeholderOutcomeBinding(
                binding_id=binding_id,
                stakeholder_id=stakeholder.stakeholder_id,
                channel=NormativeOutcomeChannel.SYNTHESIZED,
                outcome_key=_stakeholder_outcome_key(stakeholder),
                weight=Decimal(str(max(1, stakeholder.priority))),
                notes=["legacy_synthesized_binding"],
            )
        )
        terms.append(
            StakeholderUtilityTerm(
                term_id=f"{stakeholder.stakeholder_id}_legacy_utility",
                stakeholder_id=stakeholder.stakeholder_id,
                binding_refs=[binding_id],
                direction=UtilityDirection.MAXIMIZE,
                coefficient=Decimal("1"),
                welfare_weight=Decimal(str(max(1, stakeholder.priority))),
                notes=["legacy_synthesized_utility"],
            )
        )

    return NormativeFrame(
        default_policy=NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS,
        enabled_policies=[
            NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS,
            NormativeArbitrationPolicy.WEIGHTED_WELFARE,
            NormativeArbitrationPolicy.MAX_MIN_HARM,
            NormativeArbitrationPolicy.PARETO_FILTER,
        ],
        stakeholder_bindings=bindings,
        utility_terms=terms,
        rights_catalog=[],
        hard_constraint_refs=[item.constraint_id for item in problem_frame.hard_constraints],
        notes=["legacy_normative_synthesizer_used"],
    )


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
    distributional_report: DistributionalReport | None,
) -> tuple[dict[str, _ResolvedBindingValue], list[str]]:
    warnings: list[str] = []
    synthesized_map = _build_synthesized_impact_map(problem_frame, distributional_report)
    distributional_map = _build_distributional_impact_map(distributional_report)
    values: dict[str, _ResolvedBindingValue] = {}

    for binding in frame.stakeholder_bindings:
        baseline_value = 0.0
        proposal_value: float | None = None
        if binding.channel == NormativeOutcomeChannel.SIMULATION_METRIC:
            proposal_value = _metric_value(metrics, binding.outcome_key)
            if proposal_value is None:
                warnings.append(f"missing_binding_value:{binding.binding_id}")
        elif binding.channel == NormativeOutcomeChannel.DISTRIBUTIONAL_NET_IMPACT:
            proposal_value = distributional_map.get(binding.outcome_key)
            if proposal_value is None:
                warnings.append(f"missing_binding_value:{binding.binding_id}")
        elif binding.channel == NormativeOutcomeChannel.DISTRIBUTIONAL_LOSERS_SHARE:
            if distributional_report is not None:
                proposal_value = distributional_report.winners_losers.total_losers_share
        elif binding.channel == NormativeOutcomeChannel.DISTRIBUTIONAL_WINNERS_SHARE:
            if distributional_report is not None:
                proposal_value = distributional_report.winners_losers.total_winners_share
        elif binding.channel == NormativeOutcomeChannel.DISTRIBUTIONAL_OVERALL_GINI_DELTA:
            if distributional_report is not None:
                proposal_value = distributional_report.overall_gini_delta
        elif binding.channel == NormativeOutcomeChannel.UNCERTAINTY_CI_WIDTH_RATIO:
            proposal_value = _uncertainty_ratio(ctx, simulation_result, binding.outcome_key)
        elif binding.channel == NormativeOutcomeChannel.SYNTHESIZED:
            proposal_value = synthesized_map.get(binding.outcome_key)

        if proposal_value is None or not math.isfinite(proposal_value):
            continue
        values[binding.binding_id] = _ResolvedBindingValue(
            binding=binding,
            baseline_value=baseline_value,
            proposal_value=proposal_value,
        )

    return values, _dedupe_strings(warnings)


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
    simulation_result: SimulationResult | None,
    metric_id: str,
) -> float | None:
    if simulation_result is None or not simulation_result.uncertainty_envelopes:
        return None
    envelope_ref = simulation_result.uncertainty_envelopes.get(metric_id)
    if envelope_ref is None:
        return None
    try:
        payload = from_canonical_bytes(ctx.store.get_bytes(envelope_ref.artifact_id))
    except _NORMATIVE_ARTIFACT_ERRORS as exc:
        emit_degraded_path(
            component="scientist.run_normative_arbitration",
            operation="load_uncertainty_envelope",
            reason="uncertainty_envelope_load_failed",
            exc=exc,
            details={
                "run_id": getattr(simulation_result, "run_id", None),
                "metric_id": metric_id,
            },
            log=logger,
            metrics=ctx.metrics,
        )
        return None
    if not isinstance(payload, dict):
        return None
    point = _coerce_float(payload.get("point_estimate"))
    interval = payload.get("confidence_interval")
    if point is None or not isinstance(interval, (list, tuple)) or len(interval) != 2:
        return None
    lower = _coerce_float(interval[0])
    upper = _coerce_float(interval[1])
    if lower is None or upper is None:
        return None
    width = upper - lower
    denom = max(abs(point), 1.0)
    return width / denom


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
    outcomes: list[PolicyOutcome] = []
    rights_violations = sum(
        1
        for item in rights_audit
        if item.status == NormativeAuditStatus.VIOLATED and "soft_right" not in item.notes
    )
    hard_constraint_violations = sum(
        1 for item in hard_constraint_audit if item.status == NormativeAuditStatus.VIOLATED
    )
    weighted_delta = sum(item.delta_utility * item.welfare_weight for item in utility_summaries)
    proposal_worst = min((item.proposal_utility for item in utility_summaries), default=0.0)
    baseline_worst = min((item.baseline_utility for item in utility_summaries), default=0.0)
    losers_count = sum(1 for item in utility_summaries if item.delta_utility < -1e-9)
    winners_count = sum(1 for item in utility_summaries if item.delta_utility > 1e-9)

    for policy in frame.enabled_policies:
        if policy == NormativeArbitrationPolicy.LEXICOGRAPHIC_RIGHTS:
            if rights_violations > 0 or hard_constraint_violations > 0:
                selected_option = ArbitrationOption.BASELINE
                rationale = "proposal violates explicit rights or normative hard constraints"
            elif weighted_delta > 1e-9:
                selected_option = ArbitrationOption.PROPOSAL
                rationale = "no rights blockers and weighted welfare favors proposal"
            elif weighted_delta < -1e-9:
                selected_option = ArbitrationOption.BASELINE
                rationale = "no rights blockers but weighted welfare favors baseline"
            else:
                selected_option = ArbitrationOption.INDETERMINATE
                rationale = "rights tie and welfare tie"
            metrics = {
                "rights_violations": rights_violations,
                "hard_constraint_violations": hard_constraint_violations,
                "weighted_delta": weighted_delta,
            }
        elif policy == NormativeArbitrationPolicy.WEIGHTED_WELFARE:
            if weighted_delta > 1e-9:
                selected_option = ArbitrationOption.PROPOSAL
            elif weighted_delta < -1e-9:
                selected_option = ArbitrationOption.BASELINE
            else:
                selected_option = ArbitrationOption.INDETERMINATE
            rationale = f"aggregate weighted welfare delta={weighted_delta:.6f}"
            metrics = {"weighted_delta": weighted_delta}
        elif policy == NormativeArbitrationPolicy.MAX_MIN_HARM:
            if proposal_worst > baseline_worst + 1e-9:
                selected_option = ArbitrationOption.PROPOSAL
            elif proposal_worst < baseline_worst - 1e-9:
                selected_option = ArbitrationOption.BASELINE
            else:
                selected_option = ArbitrationOption.INDETERMINATE
            rationale = (
                "choose option with better worst-case stakeholder utility "
                f"(proposal={proposal_worst:.6f}, baseline={baseline_worst:.6f})"
            )
            metrics = {
                "proposal_worst_utility": proposal_worst,
                "baseline_worst_utility": baseline_worst,
            }
        else:
            if losers_count > 0:
                selected_option = ArbitrationOption.BASELINE
                rationale = "proposal is not Pareto-admissible because some stakeholders lose"
            elif winners_count > 0:
                selected_option = ArbitrationOption.PROPOSAL
                rationale = (
                    "proposal is Pareto-admissible and strictly helps at least one stakeholder"
                )
            else:
                selected_option = ArbitrationOption.INDETERMINATE
                rationale = "proposal is Pareto-neutral"
            metrics = {"losers_count": losers_count, "winners_count": winners_count}

        outcomes.append(
            PolicyOutcome(
                policy=policy,
                selected_option=selected_option,
                confidence=None,
                rationale=rationale,
                metrics=metrics,
            )
        )
    return outcomes


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


def _build_inputs(
    state: ExperimentState,
    *,
    simulation_result: SimulationResult | None,
) -> list[InputRef]:
    refs: list[InputRef] = []
    ref_map: tuple[tuple[str, ArtifactRef | None], ...] = (
        ("trinity_bundle", state.inputs.get(INPUT_TRINITY_BUNDLE_REF)),
        ("distributional_report", state.artifacts_index.get(ARTIFACT_DISTRIBUTIONAL_REPORT_REF)),
        ("legal_report", state.reports_index.get(REPORT_LEGAL_REPORT_REF)),
        ("metrics", state.artifacts_index.get(ARTIFACT_METRICS_REF)),
        ("simulation_result", state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)),
    )
    for role, ref in ref_map:
        if ref is not None:
            refs.append(InputRef(artifact_id=str(ref.artifact_id), role=role))
    if simulation_result is not None and simulation_result.uncertainty_envelopes is not None:
        for metric_id, ref in simulation_result.uncertainty_envelopes.items():
            refs.append(InputRef(artifact_id=str(ref.artifact_id), role=f"uncertainty.{metric_id}"))
    return refs


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


def _ref_id(ref: ArtifactRef | None) -> str | None:
    return str(ref.artifact_id) if ref is not None else None


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


__all__ = ["RunNormativeArbitrationNode"]
