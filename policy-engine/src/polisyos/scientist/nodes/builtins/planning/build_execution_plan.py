"""Public planning build execution plan module API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.control import DataNeed
from polisyos.core.contracts.execution_plan import ExecutionPlan
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state
from polisyos.scientist.llm_cycle import build_default_execution_plan, persist_execution_plan
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EXECUTION_PLAN_REF,
    INPUT_EXECUTION_PLAN_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_build_execution_plan@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Build Execution Plan",
    description="Create/persist ExecutionPlan as first-class CAS artifact.",
    tags=["builtin", "planning"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=["params.execution_plan", "params.stop_criteria", "params.governance_constraints", "params.expected_outputs"],
    state_writes=[
        "params.execution_plan_ref",
        f"inputs.{INPUT_EXECUTION_PLAN_REF}",
        f"artifacts_index.{ARTIFACT_EXECUTION_PLAN_REF}",
        "execution_plan_ref",
    ],
    produces=[ARTIFACT_EXECUTION_PLAN_REF],
)

_EXECUTION_PLAN_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)


@dataclass(frozen=True)
class BuildExecutionPlanNode:
    """Planning DAG node that persists the normalized execution plan for later preflight and execution.

    Reads `params.execution_plan` plus stop criteria and expected outputs, then
    writes the execution-plan artifact ref into both params and workflow inputs
    so simulation-stage nodes can reuse the same contract.
    """
    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        existing = state.params.get("execution_plan_ref")
        events: list[NodeEvent] = []
        if isinstance(existing, str) and existing:
            new_state = branch_state(state, write_paths=_SPEC.state_writes).state
            new_state.inputs[INPUT_EXECUTION_PLAN_REF] = new_state.inputs.get(
                INPUT_EXECUTION_PLAN_REF
            ) or ArtifactRef(
                artifact_id=existing,
                kind="scientist.execution_plan",
                media_type="application/json",
            )
            events = [NodeEvent(level="info", message="Execution plan already provided")]
            return NodeOutcome(status="ok", state=new_state, events=events)

        raw_plan = state.params.get("execution_plan")
        if isinstance(raw_plan, dict):
            try:
                plan = ExecutionPlan.model_validate(raw_plan).model_copy(
                    update={"run_id": state.run_id, "iteration": 1}
                )
            except _EXECUTION_PLAN_VALIDATION_ERRORS as exc:
                plan = build_default_execution_plan(
                    run_id=state.run_id,
                    data_needs=[],
                    governance_constraints=_list_of_dict(state.params.get("governance_constraints")),
                    expected_outputs=_list_of_dict(state.params.get("expected_outputs")),
                )
                events.append(
                    NodeEvent(
                        level="warn",
                        code="EXECUTION_PLAN_INVALID",
                        message=(
                            "Invalid params.execution_plan payload; default execution plan was used."
                        ),
                        attrs={"reason": str(exc)},
                    )
                )
        else:
            data_needs, invalid_data_needs = _data_needs_from_params(state.params)
            plan = build_default_execution_plan(
                run_id=state.run_id,
                data_needs=data_needs,
                governance_constraints=_list_of_dict(state.params.get("governance_constraints")),
                expected_outputs=_list_of_dict(state.params.get("expected_outputs")),
            )
            if invalid_data_needs:
                events.append(
                    NodeEvent(
                        level="warn",
                        code="DATA_NEEDS_INVALID",
                        message=(
                            "Some params.data_needs entries were invalid and were ignored while "
                            "building the default execution plan."
                        ),
                        attrs={"invalid_count": invalid_data_needs},
                    )
                )

        plan_ref = persist_execution_plan(ctx.store, plan)
        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.inputs[INPUT_EXECUTION_PLAN_REF] = plan_ref
        new_state.artifacts_index[ARTIFACT_EXECUTION_PLAN_REF] = plan_ref
        new_state.execution_plan_ref = plan_ref
        new_state.params["execution_plan_ref"] = str(plan_ref.artifact_id)
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[plan_ref],
            events=events + [
                NodeEvent(
                    level="info",
                    message="Execution plan created",
                    attrs={"method_dag_nodes": len(plan.method_dag)},
                )
            ],
        )


def _list_of_dict(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            result.append(dict(item))
    return result


def _data_needs_from_params(params: dict[str, Any]) -> tuple[list[DataNeed], int]:
    raw = params.get("data_needs")
    if not isinstance(raw, list):
        return [], 0
    result: list[DataNeed] = []
    invalid_count = 0
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            result.append(DataNeed.model_validate(item))
        except _EXECUTION_PLAN_VALIDATION_ERRORS:
            invalid_count += 1
            continue
    return result, invalid_count


__all__ = ["BuildExecutionPlanNode"]
