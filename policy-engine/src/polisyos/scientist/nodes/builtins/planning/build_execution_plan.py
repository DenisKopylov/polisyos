"""Public planning build execution plan module API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.control import DataNeed
from polisyos.core.contracts.execution_plan import ExecutionPlan, ExecutionPlanRef
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_EXECUTION_PLAN_REF,
    INPUT_EXECUTION_PLAN_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.llm.cycle import (
    build_default_execution_plan,
    persist_candidate_execution_plan,
    persist_execution_plan,
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
    state_reads=[
        "run_id",
        "params.execution_plan",
        "params.stop_criteria",
        "params.governance_constraints",
        "params.expected_outputs",
        f"inputs.{INPUT_TRINITY_BUNDLE_REF}",
    ],
    state_writes=[
        "params.execution_plan_ref",
        f"inputs.{INPUT_EXECUTION_PLAN_REF}",
        f"inputs.{INPUT_TRINITY_BUNDLE_REF}",
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
        candidate_ref = state.inputs.get(INPUT_TRINITY_BUNDLE_REF)
        events: list[NodeEvent] = []
        if isinstance(existing, str) and existing:
            existing_ref = state.inputs.get(INPUT_EXECUTION_PLAN_REF) or ExecutionPlanRef(
                artifact_id=existing,
                kind="scientist.execution_plan",
                media_type="application/json",
            )
            new_state = branch_state(state, write_paths=_SPEC.state_writes).state
            if candidate_ref is not None:
                try:
                    from polisyos.core.artifacts import validate_core_model_json_artifact

                    source_plan = ExecutionPlanRef.model_validate(
                        existing_ref.model_dump(mode="python")
                    )
                    plan = validate_core_model_json_artifact(ExecutionPlan, ctx.store, source_plan)
                    plan_ref, exact_candidate_ref = persist_candidate_execution_plan(
                        ctx.store,
                        plan,
                        candidate_ref,
                        source_plan_ref=source_plan,
                    )
                except Exception as exc:
                    return _plan_failure(
                        state,
                        "execution_plan_candidate_binding_failed",
                        str(exc),
                    )
                new_state.inputs[INPUT_TRINITY_BUNDLE_REF] = exact_candidate_ref
                new_state.inputs[INPUT_EXECUTION_PLAN_REF] = plan_ref
                new_state.artifacts_index[ARTIFACT_EXECUTION_PLAN_REF] = plan_ref
                new_state.execution_plan_ref = plan_ref
                new_state.params["execution_plan_ref"] = str(plan_ref.artifact_id)
                return NodeOutcome(status="ok", state=new_state, artifacts=[plan_ref])
            new_state.inputs[INPUT_EXECUTION_PLAN_REF] = existing_ref
            events = [NodeEvent(level="info", message="Execution plan already provided")]
            return NodeOutcome(status="ok", state=new_state, events=events)

        raw_plan = state.params.get("execution_plan")
        if isinstance(raw_plan, dict):
            try:
                plan = ExecutionPlan.model_validate(raw_plan).model_copy(
                    update={"run_id": state.run_id, "iteration": 1}
                )
            except _EXECUTION_PLAN_VALIDATION_ERRORS as exc:
                if "method_dag" in raw_plan or "method_edges" in raw_plan:
                    return _plan_failure(
                        state,
                        "execution_plan_method_payload_invalid",
                        str(exc),
                    )
                plan = build_default_execution_plan(
                    run_id=state.run_id,
                    data_needs=[],
                    governance_constraints=_list_of_dict(
                        state.params.get("governance_constraints")
                    ),
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

        exact_candidate_ref: ArtifactRef | None = None
        try:
            if candidate_ref is None:
                plan_ref = persist_execution_plan(ctx.store, plan)
            else:
                plan_ref, exact_candidate_ref = persist_candidate_execution_plan(
                    ctx.store,
                    plan,
                    candidate_ref,
                )
        except Exception as exc:
            return _plan_failure(
                state,
                "execution_plan_candidate_binding_failed",
                str(exc),
            )
        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        if exact_candidate_ref is not None:
            new_state.inputs[INPUT_TRINITY_BUNDLE_REF] = exact_candidate_ref
        new_state.inputs[INPUT_EXECUTION_PLAN_REF] = plan_ref
        new_state.artifacts_index[ARTIFACT_EXECUTION_PLAN_REF] = plan_ref
        new_state.execution_plan_ref = plan_ref
        new_state.params["execution_plan_ref"] = str(plan_ref.artifact_id)
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[plan_ref],
            events=events
            + [
                NodeEvent(
                    level="info",
                    message="Execution plan created",
                    attrs={"method_dag_nodes": len(plan.method_dag)},
                )
            ],
        )


def _plan_failure(state: ExperimentState, code: str, reason: str) -> NodeOutcome:
    """Fail a selected plan source without silently replacing its contents."""
    return NodeOutcome(
        status="fail",
        state=state,
        error=NodeError(code=code, message=reason[:512]),
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
