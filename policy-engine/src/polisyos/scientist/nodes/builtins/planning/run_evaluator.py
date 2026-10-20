"""Public planning run evaluator module API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.execution_plan import (
    IterationState,
)
from polisyos.scientist.governance.report import (
    GovernanceReport,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EVALUATOR_REPORT_REF,
    ARTIFACT_ITERATION_STATE_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.iteration_state_machine import transition
from polisyos.scientist.orchestration.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.llm.cycle import (
    evaluate_iteration,
    persist_evaluator_report,
    persist_iteration_state,
)

logger = get_logger(__name__)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_evaluator@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Evaluator",
    description="Evaluate run quality and decide next iteration action.",
    tags=["builtin", "planning", "evaluator"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        f"reports_index.{REPORT_GOVERNANCE_REPORT_REF}",
        "params.run_budget_usd",
        "params.run_cost_usd",
        "params.retrieval_candidates_filtered",
    ],
    state_writes=[
        "params.evaluator",
        "params.evaluator_verdict",
        "params.iteration_state_ref",
        f"artifacts_index.{ARTIFACT_EVALUATOR_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_ITERATION_STATE_REF}",
        "evaluator_report_ref",
        "iteration_state_ref",
    ],
    produces=[ARTIFACT_EVALUATOR_REPORT_REF, ARTIFACT_ITERATION_STATE_REF],
)

_GOVERNANCE_REPORT_LOAD_ERRORS = (
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
)
_ITERATION_TRANSITION_ERRORS = (
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
)
_NUMERIC_COERCE_ERRORS = (TypeError, ValueError)


@dataclass(frozen=True)
class RunEvaluatorNode:
    """Planning/control node that converts governance and budget signals into an iteration verdict.

    Reads governance reports plus budget/retrieval signals, then writes the
    evaluator report and iteration-state refs that tell the workflow whether to
    approve, replan, or stop for budget reasons.
    """

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        governance_verdict = "NEEDS_REVISION"
        governance_issues: list[dict[str, Any]] = []
        events: list[NodeEvent] = []
        governance_ref = state.reports_index.get(REPORT_GOVERNANCE_REPORT_REF)
        if governance_ref is not None:
            from polisyos.scientist.governance.report_currentness import (
                resolve_current_governance_report,
            )

            admission = resolve_current_governance_report(ctx, state, governance_ref)
            if admission.is_current and admission.report is not None:
                governance = admission.report
                governance_verdict = str(governance.verdict or "NEEDS_REVISION").upper()
                governance_issues = list(governance.issues)
            else:
                governance_verdict = "NEEDS_REVISION"
                governance_issues = [
                    {
                        "code": admission.reason_code,
                        "message": "Governance report source currentness is not established.",
                    }
                ]
                events.append(
                    NodeEvent(
                        level="warn",
                        code="EVALUATOR_GOVERNANCE_REPORT_NOT_CURRENT",
                        message=(
                            "Governance report is retained as candidate evidence; evaluator "
                            "requires a current producer-bound report."
                        ),
                        attrs={"status": admission.status, "reason": admission.reason_code},
                    )
                )
        issue_count = len(governance_issues)
        raw_filtered = state.params.get("retrieval_candidates_filtered")
        filtered = _coerce_json_int(raw_filtered) if raw_filtered else 0
        retrieval_quality = 1.0 if filtered == 0 else max(0.0, 1.0 - min(1.0, filtered / 100.0))
        budget_remaining_ratio = _budget_remaining_ratio(state.params)
        evaluator_report = evaluate_iteration(
            issue_count=issue_count,
            verdict=governance_verdict,
            retrieval_quality=retrieval_quality,
            budget_remaining_ratio=budget_remaining_ratio,
        )
        eval_ref = persist_evaluator_report(
            ctx.store,
            evaluator_report,
            inputs=[input_ref_from_artifact_ref(governance_ref, role="governance_report")]
            if governance_ref is not None
            else None,
        )

        iteration_state = IterationState(
            run_id=state.run_id,
            iteration=1,
            lifecycle_state="evaluating",
            evaluator_report_ref=eval_ref,
            updated_at=datetime.now(UTC),
        )
        try:
            if evaluator_report.verdict == "APPROVE":
                iteration_state = transition(
                    iteration_state,
                    "approve",
                    verdict=evaluator_report.verdict,
                    stop_reason="approved",
                )
            elif evaluator_report.verdict == "STOP_BUDGET":
                iteration_state = transition(
                    iteration_state,
                    "stop_budget",
                    verdict=evaluator_report.verdict,
                    stop_reason="budget_exhausted",
                )
            else:
                iteration_state = transition(
                    iteration_state,
                    "replan",
                    verdict=evaluator_report.verdict,
                )
        except _ITERATION_TRANSITION_ERRORS as exc:
            logger.warning("Evaluator transition degraded: %s", exc)
            events.append(
                NodeEvent(
                    level="warn",
                    code="EVALUATOR_TRANSITION_DEGRADED",
                    message=(
                        "Iteration state transition degraded; evaluator persisted the base "
                        "iteration state."
                    ),
                    attrs={"reason": str(exc)},
                )
            )
        iteration_ref = persist_iteration_state(
            ctx.store,
            iteration_state,
            inputs=[input_ref_from_artifact_ref(eval_ref, role="evaluator_report")],
        )

        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.params["evaluator"] = evaluator_report.model_dump(mode="json")
        new_state.params["evaluator_verdict"] = evaluator_report.verdict
        new_state.params["iteration_state_ref"] = str(iteration_ref.artifact_id)
        new_state.artifacts_index[ARTIFACT_EVALUATOR_REPORT_REF] = eval_ref
        new_state.artifacts_index[ARTIFACT_ITERATION_STATE_REF] = iteration_ref
        new_state.evaluator_report_ref = eval_ref
        new_state.iteration_state_ref = iteration_ref
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[eval_ref, iteration_ref],
            events=events
            + [
                NodeEvent(
                    level="info",
                    message=f"Evaluator verdict: {evaluator_report.verdict}",
                )
            ],
        )


def _budget_remaining_ratio(params: dict[str, Any]) -> float | None:
    run_budget = params.get("run_budget_usd")
    run_cost = params.get("run_cost_usd")
    try:
        budget = _coerce_json_float(run_budget)
    except _NUMERIC_COERCE_ERRORS:
        return None
    if budget <= 0:
        return None
    try:
        spent = _coerce_json_float(run_cost) if run_cost else 0.0
    except _NUMERIC_COERCE_ERRORS:
        spent = 0.0
    return max(0.0, (budget - spent) / budget)


def _coerce_json_int(value: object) -> int:
    if isinstance(value, (int, float, str, Decimal)):
        return int(value)
    raise TypeError("expected a JSON numeric or string value")


def _coerce_json_float(value: object) -> float:
    if isinstance(value, (int, float, str, Decimal)):
        return float(value)
    raise TypeError("expected a JSON numeric or string value")


__all__ = ["RunEvaluatorNode"]
