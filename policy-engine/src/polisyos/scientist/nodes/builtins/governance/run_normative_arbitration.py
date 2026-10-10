"""Public governance run normative arbitration module API."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
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
from polisyos.ir.analytics.uncertainty import load_simulation_result_uncertainty_admission
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
from polisyos.ir.registry.refs import DistributionalReportRef
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_NORMATIVE_ARBITRATION_RESULT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_LEGAL_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state

from .normative_arbitration_calculations import (
    _NORMATIVE_ARTIFACT_ERRORS as _NORMATIVE_ARTIFACT_ERRORS,
)
from .normative_arbitration_calculations import (
    _audit_hard_constraints as _audit_hard_constraints,
)
from .normative_arbitration_calculations import (
    _audit_rights as _audit_rights,
)
from .normative_arbitration_calculations import (
    _build_distributional_impact_map as _build_distributional_impact_map,
)
from .normative_arbitration_calculations import (
    _build_synthesized_impact_map as _build_synthesized_impact_map,
)
from .normative_arbitration_calculations import (
    _coerce_float as _coerce_float,
)
from .normative_arbitration_calculations import (
    _compare as _compare,
)
from .normative_arbitration_calculations import (
    _compute_stakeholder_utilities as _compute_stakeholder_utilities,
)
from .normative_arbitration_calculations import (
    _constraint_value as _constraint_value,
)
from .normative_arbitration_calculations import (
    _dedupe_strings as _dedupe_strings,
)
from .normative_arbitration_calculations import (
    _evaluate_policies as _evaluate_policies,
)
from .normative_arbitration_calculations import (
    _metric_value as _metric_value,
)
from .normative_arbitration_calculations import (
    _normalize_scalar as _normalize_scalar,
)
from .normative_arbitration_calculations import (
    _resolve_binding_values as _resolve_binding_values,
)
from .normative_arbitration_calculations import (
    _resolve_model_completeness as _resolve_model_completeness,
)
from .normative_arbitration_calculations import (
    _ResolvedBindingValue as _ResolvedBindingValue,
)
from .normative_arbitration_calculations import (
    _stakeholder_outcome_key as _stakeholder_outcome_key,
)
from .normative_arbitration_calculations import (
    _uncertainty_ratio as _uncertainty_ratio,
)
from .normative_arbitration_calculations import (
    _value_for_target as _value_for_target,
)

logger = get_logger(__name__)

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
                from_canonical_bytes(ctx.store.get_bytes(trinity_ref))
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
            simulation_result_ref=state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF),
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
        result_ref = persist_normative_arbitration_result(
            _ensure_ir_artifact_store(ctx.store), result, inputs=inputs
        )

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
        return Metrics.model_validate(from_canonical_bytes(ctx.store.get_bytes(ref)))
    except _NORMATIVE_ARTIFACT_ERRORS as exc:
        raise
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
        return SimulationResult.model_validate(from_canonical_bytes(ctx.store.get_bytes(ref)))
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
            _ensure_ir_artifact_store(ctx.store),
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
        return LegalReport.model_validate(from_canonical_bytes(ctx.store.get_bytes(ref)))
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
        if simulation_result.propagation_report_ref is not None:
            refs.append(
                InputRef(
                    artifact_id=str(simulation_result.propagation_report_ref.artifact_id),
                    role="propagation_report",
                )
            )
        if simulation_result.propagation_config_ref is not None:
            refs.append(
                InputRef(
                    artifact_id=str(simulation_result.propagation_config_ref.artifact_id),
                    role="propagation_config",
                )
            )
        for metric_id, ref in simulation_result.uncertainty_envelopes.items():
            refs.append(InputRef(artifact_id=str(ref.artifact_id), role=f"uncertainty.{metric_id}"))
    return refs


def _ref_id(ref: ArtifactRef | None) -> str | None:
    return str(ref.artifact_id) if ref is not None else None


__all__ = ["RunNormativeArbitrationNode"]
