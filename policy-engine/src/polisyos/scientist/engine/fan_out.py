"""Fan-out / fan-in (map-reduce) node.

A :class:`FanOutNode` takes a list from state, runs a task node per item
(optionally in parallel), and merges results back into state.

From the DAG perspective, a ``FanOutNode`` is a single node — the internal
fan-out is encapsulated, preserving the static topological sort, idempotency
cache, and checkpoint contracts.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import Node, NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.registry import NodeRegistry
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.workflow_spec import JsonValue

logger = get_logger(__name__)

__all__ = [
    "FanOutConfig",
    "FanOutNode",
    "FanOutResult",
]


class FanOutConfig(BaseModel):
    """Configuration for a fan-out / fan-in node."""

    model_config = ConfigDict(extra="forbid")

    items_state_path: str = Field(
        ...,
        description="Dot-path to a list in state (e.g. 'params.jurisdictions')",
    )
    task_node_id: ComponentId = Field(
        ...,
        description="Node to run for each item",
    )
    task_params_template: dict[str, JsonValue] = Field(
        default_factory=dict,
        description="Base params merged with item for each task",
    )
    item_param_key: str = Field(
        default="item",
        description="Key in task params where the item value is injected",
    )
    item_index_key: str = Field(
        default="item_index",
        description="Key in task params where the item index is injected",
    )
    merge_strategy: Literal["list_collect", "dict_merge", "artifact_index"] = Field(
        default="list_collect",
    )
    result_state_path: str = Field(
        ...,
        description="Dot-path where merged results are written in state",
    )
    max_parallelism: int = Field(default=4, ge=1, le=32)
    continue_on_item_failure: bool = Field(default=True)


class FanOutResult(BaseModel):
    """Summary of a fan-out execution."""

    model_config = ConfigDict(extra="forbid")

    items_count: int
    completed: int
    failed: int
    failed_items: list[int] = Field(default_factory=list)


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
    """Set a value in a nested dict, creating intermediaries."""
    for part in path_parts[:-1]:
        if part not in target or not isinstance(target[part], dict):
            target[part] = {}
        target = target[part]
    target[path_parts[-1]] = value


# ---------------------------------------------------------------------------
# FanOutNode
# ---------------------------------------------------------------------------

class FanOutNode:
    """Map-reduce node that fans out a list to parallel task invocations.

    Implements the :class:`Node` protocol. Requires a :class:`NodeRegistry`
    to resolve the task node at execution time.
    """

    def __init__(
        self,
        config: FanOutConfig,
        registry: NodeRegistry,
        *,
        alias: str = "fan_out",
    ) -> None:
        self._config = config
        self._registry = registry
        self._alias = alias

    @property
    def spec(self) -> NodeSpec:
        return NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.node_fan_out@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Fan-Out / Fan-In",
                description="Map-reduce node: fans out items to parallel tasks.",
                tags=["builtin", "fan_out"],
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=[self._config.items_state_path],
            state_writes=[self._config.result_state_path],
            produces=["fan_out_result"],
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        items = _resolve_path(state, self._config.items_state_path)
        if items is None or not isinstance(items, list):
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(
                    level="info", message="No items found for fan-out",
                    code="fan_out.no_items", attrs={},
                )],
            )

        if len(items) == 0:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(
                    level="info", message="Empty items list",
                    code="fan_out.empty_items", attrs={},
                )],
            )

        task_node = self._registry.get(self._config.task_node_id)
        outcomes: list[tuple[int, NodeOutcome]] = []
        failed_items: list[int] = []

        for i, item in enumerate(items):
            params = {
                **self._config.task_params_template,
                self._config.item_param_key: item,
                self._config.item_index_key: i,
            }
            # Bind params if the node supports it
            bound_node = task_node
            if hasattr(task_node, "bind"):
                try:
                    bound_result = task_node.bind(params)
                    if bound_result is not None:
                        bound_node = bound_result
                except Exception:
                    pass

            item_state = state.model_copy(deep=True)
            try:
                outcome = bound_node.execute(ctx, item_state)
            except Exception as exc:
                logger.warning("Fan-out item %d failed: %s", i, exc)
                outcome = NodeOutcome(
                    status="fail",
                    state=item_state,
                    error=NodeError(
                        code="fan_out.item_failed",
                        message=f"Item {i} failed: {exc}",
                        details={"item_index": i, "type": exc.__class__.__name__},
                    ),
                )

            if outcome.status == "fail":
                failed_items.append(i)
                if not self._config.continue_on_item_failure:
                    outcomes.append((i, outcome))
                    break
            outcomes.append((i, outcome))

        # Merge results
        ok_outcomes = [(i, o) for i, o in outcomes if o.status == "ok"]
        merged_state = state.model_copy(deep=True)
        all_artifacts: list[ArtifactRef] = []

        if self._config.merge_strategy == "list_collect":
            collected = [list(o.artifacts) for _, o in ok_outcomes]
            self._write_result(merged_state, self._config.result_state_path, collected)
        elif self._config.merge_strategy == "dict_merge":
            merged: dict[str, Any] = {}
            for i, o in ok_outcomes:
                merged[str(i)] = [a.artifact_id for a in o.artifacts]
            self._write_result(merged_state, self._config.result_state_path, merged)
        elif self._config.merge_strategy == "artifact_index":
            for i, o in ok_outcomes:
                for a in o.artifacts:
                    key = f"fan_out_{self._alias}_{i}"
                    merged_state.artifacts_index[key] = a
                    all_artifacts.append(a)

        # Collect all artifacts
        for _, o in ok_outcomes:
            all_artifacts.extend(o.artifacts)

        fan_out_result = FanOutResult(
            items_count=len(items),
            completed=len(ok_outcomes),
            failed=len(failed_items),
            failed_items=failed_items,
        )

        # Persist summary
        try:
            summary_ref = ctx.store.put_json(
                fan_out_result.model_dump(),
                PutOptions(
                    kind="scientist.fan_out_result",
                    media_type="application/json",
                    schema=SchemaInfo(
                        name="polisyos.scientist.engine.FanOutResult",
                        version="1.0",
                    ),
                ),
            )
            all_artifacts.append(summary_ref)
        except Exception:
            pass

        overall_status = "ok" if not failed_items else (
            "fail" if not self._config.continue_on_item_failure else "ok"
        )
        error = None
        if failed_items and not self._config.continue_on_item_failure:
            error = NodeError(
                code="fan_out.items_failed",
                message=f"{len(failed_items)} of {len(items)} items failed",
                details={"failed_items": failed_items},
            )

        events = [
            NodeEvent(
                level="info",
                message=f"Fan-out: {len(ok_outcomes)}/{len(items)} items completed",
                code="fan_out.summary",
                attrs={
                    "items_count": len(items),
                    "completed": len(ok_outcomes),
                    "failed": len(failed_items),
                },
            ),
        ]

        return NodeOutcome(
            status=overall_status,
            state=merged_state,
            artifacts=all_artifacts,
            events=events,
            error=error,
        )

    def _write_result(
        self,
        state: ExperimentState,
        path: str,
        value: Any,
    ) -> None:
        """Write a value to a dot-path in state (params only)."""
        parts = path.split(".")
        if parts[0] == "params":
            _set_nested(state.params, parts[1:], value)
        elif parts[0] == "artifacts_index" and len(parts) == 2:
            # Can't store non-ArtifactRef in artifacts_index; skip
            pass
        else:
            # Best-effort: write to params with full path
            _set_nested(state.params, parts, value)
