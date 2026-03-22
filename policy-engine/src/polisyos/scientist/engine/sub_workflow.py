"""Sub-workflow nesting — workflow-as-node.

A :class:`SubWorkflowNode` wraps a :class:`WorkflowSpec` and runs it as a
child workflow within a single DAG node.  State is mapped in/out so the parent
workflow sees the child's results without coupling.

From the executor's perspective this is just another ``Node``.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.common.logger import get_logger
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.errors import EngineError
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.registry import NodeRegistry
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.workflow_spec import ErrorPolicy, WorkflowSpec

logger = get_logger(__name__)

__all__ = [
    "StateMapping",
    "SubWorkflowConfig",
    "SubWorkflowNode",
]


class StateMapping(BaseModel):
    """Maps a dot-path from one state to another."""

    model_config = ConfigDict(extra="forbid")

    source_path: str = Field(..., description="Dot-path in source state")
    target_path: str = Field(..., description="Dot-path in target state")


class SubWorkflowConfig(BaseModel):
    """Configuration for a sub-workflow node."""

    model_config = ConfigDict(extra="forbid")

    workflow: WorkflowSpec
    input_mappings: list[StateMapping] = Field(default_factory=list)
    output_mappings: list[StateMapping] = Field(default_factory=list)
    max_depth: int = Field(default=3, ge=1, le=10)
    error_policy_override: ErrorPolicy | None = None


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _resolve_path(state: ExperimentState, path: str) -> Any:
    from pydantic import BaseModel as _BM

    parts = path.split(".")
    current: Any = state
    for part in parts:
        if isinstance(current, _BM):
            current = getattr(current, part, None)
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _set_nested(target: dict[str, Any], path_parts: list[str], value: Any) -> None:
    for part in path_parts[:-1]:
        if part not in target or not isinstance(target[part], dict):
            target[part] = {}
        target = target[part]
    target[path_parts[-1]] = value


def _write_to_state(state: ExperimentState, path: str, value: Any) -> None:
    parts = path.split(".")
    if parts[0] == "params":
        _set_nested(state.params, parts[1:], value)
    elif parts[0] == "inputs" and len(parts) == 2:
        state.inputs[parts[1]] = value
    elif parts[0] == "artifacts_index" and len(parts) == 2:
        state.artifacts_index[parts[1]] = value
    else:
        _set_nested(state.params, parts, value)


# ---------------------------------------------------------------------------
# SubWorkflowNode
# ---------------------------------------------------------------------------

class SubWorkflowNode:
    """Meta-node that runs a child workflow as a single DAG step.

    Implements the :class:`Node` protocol.
    """

    def __init__(
        self,
        config: SubWorkflowConfig,
        registry: NodeRegistry,
        *,
        alias: str = "sub_workflow",
    ) -> None:
        self._config = config
        self._registry = registry
        self._alias = alias

    @property
    def spec(self) -> NodeSpec:
        return NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.node_sub_workflow@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Sub-Workflow",
                description="Runs a child workflow as a single node.",
                tags=["builtin", "sub_workflow"],
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=[m.source_path for m in self._config.input_mappings],
            state_writes=[m.target_path for m in self._config.output_mappings],
            produces=["sub_workflow_report"],
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        # Depth check
        if ctx.depth + 1 > self._config.max_depth:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="sub_workflow.max_depth",
                    message=(
                        f"Max nesting depth {self._config.max_depth} exceeded "
                        f"(current depth: {ctx.depth})"
                    ),
                    details={"max_depth": self._config.max_depth, "depth": ctx.depth},
                ),
            )

        # Build child state with mapped inputs
        child_state = ExperimentState(
            run_id=f"{state.run_id}__sub_{self._alias}",
        )
        for mapping in self._config.input_mappings:
            value = _resolve_path(state, mapping.source_path)
            if value is not None:
                _write_to_state(child_state, mapping.target_path, value)

        # Build child context with incremented depth
        import dataclasses
        child_ctx = dataclasses.replace(
            ctx,
            depth=ctx.depth + 1,
            logger=logging.getLogger(f"{ctx.logger.name}.sub_{self._alias}"),
        )

        # Execute child workflow
        from polisyos.scientist.engine.executor import WorkflowExecutor

        child_workflow = self._config.workflow
        if self._config.error_policy_override is not None:
            child_workflow = child_workflow.model_copy(
                update={"error_policy": self._config.error_policy_override},
            )

        executor = WorkflowExecutor(child_ctx, self._registry)
        try:
            result = executor.execute(child_workflow, child_state)
        except EngineError as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code="sub_workflow.execution_failed",
                    message=f"Child workflow failed: {exc}",
                    details={"alias": self._alias},
                ),
            )

        # Map child output state back to parent
        merged_state = state.model_copy(deep=True)
        for mapping in self._config.output_mappings:
            value = _resolve_path(result.state, mapping.source_path)
            if value is not None:
                _write_to_state(merged_state, mapping.target_path, value)

        # Collect child artifacts
        child_artifacts = []
        for node_record in result.report.nodes:
            if hasattr(node_record, "artifacts"):
                child_artifacts.extend(node_record.artifacts)

        child_status = result.report.status
        if child_status == "fail":
            return NodeOutcome(
                status="fail",
                state=merged_state,
                error=NodeError(
                    code="sub_workflow.child_failed",
                    message=f"Child workflow completed with status: {child_status}",
                    details={"alias": self._alias, "child_run_id": result.state.run_id},
                ),
                events=[NodeEvent(
                    level="warn",
                    message=f"Sub-workflow '{self._alias}' failed",
                    code="sub_workflow.failed",
                )],
            )

        events = [
            NodeEvent(
                level="info",
                message=(
                    f"Sub-workflow '{self._alias}' completed: "
                    f"{len(result.report.nodes)} nodes executed"
                ),
                code="sub_workflow.completed",
                attrs={
                    "child_run_id": result.state.run_id,
                    "child_nodes": len(result.report.nodes),
                },
            ),
        ]

        return NodeOutcome(
            status="ok",
            state=merged_state,
            artifacts=child_artifacts,
            events=events,
        )
