"""Fan-out / fan-in (map-reduce) node.

A :class:`FanOutNode` takes a list from state, runs a task node per item
(optionally in parallel), and merges results back into state.

From the DAG perspective, a ``FanOutNode`` is a single node — the internal
fan-out is encapsulated, preserving the static topological sort, idempotency
cache, and checkpoint contracts.
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.async_tools import run_blocking_async
from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.error_semantics import emit_degraded_path
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.registry import NodeRegistry
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state
from polisyos.scientist.engine.state_merge import (
    MergeConflictPolicy,
    merge_parallel_outcomes,
)
from polisyos.scientist.engine.workflow_spec import JsonValue

logger = get_logger(__name__)

_FAN_OUT_RUNTIME_ERRORS = (
    ArithmeticError,
    AssertionError,
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)

__all__ = [
    "FanOutConfig",
    "FanOutNode",
    "FanOutResult",
    "MergeConflictPolicy",
]


class FanOutItemBindError(RuntimeError):
    """Binding one fan-out item to the task node failed."""

    def __init__(self, *, item_index: int, cause: BaseException) -> None:
        self.item_index = item_index
        self.error_type = cause.__class__.__name__
        super().__init__(f"item {item_index} bind failed: {cause}")


def _fan_out_degraded(
    *,
    operation: str,
    reason: str,
    exc: BaseException,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return emit_degraded_path(
        component="engine.fan_out",
        operation=operation,
        reason=reason,
        exc=exc,
        details=details,
        log=logger,
    )


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
    merge_conflict_policy: MergeConflictPolicy = Field(
        default=MergeConflictPolicy.LAST_WRITE_WINS,
    )


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
    parts = path.split(".")
    current: Any = state
    for part in parts:
        if isinstance(current, BaseModel):
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
                events=[
                    NodeEvent(
                        level="info",
                        message="No items found for fan-out",
                        code="fan_out.no_items",
                        attrs={},
                    )
                ],
            )

        if len(items) == 0:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="Empty items list",
                        code="fan_out.empty_items",
                        attrs={},
                    )
                ],
            )

        task_node = self._registry.get(self._config.task_node_id)
        outcomes: list[tuple[int, NodeOutcome, tuple[str, ...]]] = []
        failed_items: list[int] = []
        degraded_envelopes: list[dict[str, Any]] = []

        for i, item in enumerate(items):
            try:
                bound_node = self._bind_item(task_node, item, i)
            except FanOutItemBindError as exc:
                envelope = _fan_out_degraded(
                    operation="bind_item",
                    reason="item_bind_failed",
                    exc=exc,
                    details={"alias": self._alias, "item_index": i},
                )
                degraded_envelopes.append(envelope)
                outcome = NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code="fan_out.item_bind_failed",
                        message=str(exc),
                        details={"item_index": i, "type": exc.error_type},
                    ),
                )
                failed_items.append(i)
                outcomes.append((i, outcome, ()))
                if not self._config.continue_on_item_failure:
                    break
                continue
            item_write_paths = tuple(getattr(bound_node.spec, "state_writes", ()))
            item_state = branch_state(
                state,
                write_paths=item_write_paths,
            ).state
            try:
                outcome = bound_node.execute(ctx, item_state)
            except _FAN_OUT_RUNTIME_ERRORS as exc:
                envelope = _fan_out_degraded(
                    operation="execute_item",
                    reason="item_execution_failed",
                    exc=exc,
                    details={"alias": self._alias, "item_index": i},
                )
                degraded_envelopes.append(envelope)
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
                    outcomes.append((i, outcome, item_write_paths))
                    break
            outcomes.append((i, outcome, item_write_paths))

        return self._merge_outcomes(
            ctx,
            state,
            items,
            outcomes,
            failed_items,
            degraded_envelopes=degraded_envelopes,
        )

    async def execute_async(
        self,
        ctx: ExecutionContext,
        state: ExperimentState,
    ) -> NodeOutcome:
        """Async fan-out with real parallelism via asyncio.TaskGroup."""
        items = _resolve_path(state, self._config.items_state_path)
        if items is None or not isinstance(items, list):
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="No items found for fan-out",
                        code="fan_out.no_items",
                        attrs={},
                    )
                ],
            )

        if len(items) == 0:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="Empty items list",
                        code="fan_out.empty_items",
                        attrs={},
                    )
                ],
            )

        task_node = self._registry.get(self._config.task_node_id)
        semaphore = asyncio.Semaphore(self._config.max_parallelism)
        results: dict[int, tuple[NodeOutcome, tuple[str, ...]]] = {}
        cancel_event = asyncio.Event()
        degraded_envelopes: list[dict[str, Any]] = []

        async def _run_item(i: int, item: Any) -> None:
            if cancel_event.is_set():
                return
            async with semaphore:
                if cancel_event.is_set():
                    return
                try:
                    bound_node = self._bind_item(task_node, item, i)
                except FanOutItemBindError as exc:
                    envelope = _fan_out_degraded(
                        operation="bind_item_async",
                        reason="item_bind_failed",
                        exc=exc,
                        details={"alias": self._alias, "item_index": i},
                    )
                    degraded_envelopes.append(envelope)
                    outcome = NodeOutcome(
                        status="fail",
                        state=state,
                        error=NodeError(
                            code="fan_out.item_bind_failed",
                            message=str(exc),
                            details={"item_index": i, "type": exc.error_type},
                        ),
                    )
                    results[i] = (outcome, ())
                    if not self._config.continue_on_item_failure:
                        cancel_event.set()
                    return
                item_write_paths = tuple(getattr(bound_node.spec, "state_writes", ()))
                item_state = branch_state(
                    state,
                    write_paths=item_write_paths,
                ).state
                try:
                    outcome = await run_blocking_async(
                        bound_node.execute,
                        ctx,
                        item_state,
                    )
                except _FAN_OUT_RUNTIME_ERRORS as exc:
                    envelope = _fan_out_degraded(
                        operation="execute_item_async",
                        reason="item_execution_failed",
                        exc=exc,
                        details={"alias": self._alias, "item_index": i},
                    )
                    degraded_envelopes.append(envelope)
                    outcome = NodeOutcome(
                        status="fail",
                        state=item_state,
                        error=NodeError(
                            code="fan_out.item_failed",
                            message=f"Item {i} failed: {exc}",
                            details={"item_index": i, "type": exc.__class__.__name__},
                        ),
                    )
                results[i] = (outcome, item_write_paths)
                if outcome.status == "fail" and not self._config.continue_on_item_failure:
                    cancel_event.set()

        async with asyncio.TaskGroup() as tg:
            for i, item in enumerate(items):
                tg.create_task(_run_item(i, item))

        # Build ordered outcomes list
        outcomes: list[tuple[int, NodeOutcome, tuple[str, ...]]] = []
        failed_items: list[int] = []
        for i in range(len(items)):
            if i not in results:
                continue  # cancelled before execution
            outcome, item_write_paths = results[i]
            outcomes.append((i, outcome, item_write_paths))
            if outcome.status == "fail":
                failed_items.append(i)

        return self._merge_outcomes(
            ctx,
            state,
            items,
            outcomes,
            failed_items,
            degraded_envelopes=degraded_envelopes,
        )

    def _bind_item(
        self,
        task_node: Any,
        item: Any,
        index: int,
    ) -> Any:
        """Bind item params to a task node."""
        params = {
            **self._config.task_params_template,
            self._config.item_param_key: item,
            self._config.item_index_key: index,
        }
        bound_node = task_node
        if hasattr(task_node, "bind"):
            try:
                bound_result = task_node.bind(params)
                if bound_result is not None:
                    bound_node = bound_result
            except _FAN_OUT_RUNTIME_ERRORS as exc:
                raise FanOutItemBindError(item_index=index, cause=exc) from exc
        return bound_node

    def _merge_outcomes(
        self,
        ctx: ExecutionContext,
        state: ExperimentState,
        items: list[Any],
        outcomes: list[tuple[int, NodeOutcome, tuple[str, ...]]],
        failed_items: list[int],
        *,
        degraded_envelopes: list[dict[str, Any]] | None = None,
    ) -> NodeOutcome:
        """Merge item outcomes into a single NodeOutcome."""
        ok_outcomes = [(i, o, write_paths) for i, o, write_paths in outcomes if o.status == "ok"]
        all_artifacts: list[ArtifactRef] = []
        params_write: tuple[str, Any] | None = None
        artifact_index_updates: dict[str, ArtifactRef] = {}

        if self._config.merge_strategy == "list_collect":
            collected = [list(o.artifacts) for _, o, _ in ok_outcomes]
            params_write = (self._config.result_state_path, collected)
        elif self._config.merge_strategy == "dict_merge":
            merged: dict[str, Any] = {}
            for i, o, _ in ok_outcomes:
                key = str(i)
                if key in merged:
                    if self._config.merge_conflict_policy == MergeConflictPolicy.ERROR:
                        return NodeOutcome(
                            status="fail",
                            state=state,
                            error=NodeError(
                                code="fan_out.merge_conflict",
                                message=f"Merge conflict on key '{key}'",
                                details={"key": key},
                            ),
                        )
                    if self._config.merge_conflict_policy == MergeConflictPolicy.FIRST_WRITE_WINS:
                        continue
                merged[key] = [a.artifact_id for a in o.artifacts]
            params_write = (self._config.result_state_path, merged)
        elif self._config.merge_strategy == "artifact_index":
            for i, o, _ in ok_outcomes:
                for a in o.artifacts:
                    key = f"fan_out_{self._alias}_{i}"
                    if (
                        key in artifact_index_updates
                        and self._config.merge_conflict_policy == MergeConflictPolicy.ERROR
                    ):
                        return NodeOutcome(
                            status="fail",
                            state=state,
                            error=NodeError(
                                code="fan_out.merge_conflict",
                                message=f"Merge conflict on artifact key '{key}'",
                                details={"key": key},
                            ),
                        )
                    if (
                        key in artifact_index_updates
                        and self._config.merge_conflict_policy
                        == MergeConflictPolicy.FIRST_WRITE_WINS
                    ):
                        continue
                    artifact_index_updates[key] = a

        # Collect all artifacts
        for _, o, _ in ok_outcomes:
            all_artifacts.extend(o.artifacts)

        fan_out_result = FanOutResult(
            items_count=len(items),
            completed=len(ok_outcomes),
            failed=len(failed_items),
            failed_items=failed_items,
        )

        # Persist summary
        degraded_events: list[NodeEvent] = [
            NodeEvent(
                level="warn",
                message="Fan-out execution degraded",
                code="fan_out.execution_degraded",
                attrs={
                    "reason": str(envelope.get("reason", "fan_out_execution_degraded")),
                    "error_type": str(envelope.get("error_type", "runtime_error")),
                    "item_index": int(envelope.get("details", {}).get("item_index", -1)),
                },
            )
            for envelope in (degraded_envelopes or [])
        ]
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
        except _FAN_OUT_RUNTIME_ERRORS as exc:
            envelope = _fan_out_degraded(
                operation="persist_summary",
                reason="fan_out_summary_persist_failed",
                exc=exc,
                details={"alias": self._alias, "items_count": len(items)},
            )
            degraded_events.append(
                NodeEvent(
                    level="warn",
                    message="Fan-out summary persistence degraded",
                    code="fan_out.summary_persist_degraded",
                    attrs={
                        "reason": str(envelope.get("reason", "fan_out_summary_persist_failed")),
                        "error_type": str(envelope.get("error_type", "runtime_error")),
                    },
                )
            )

        overall_status = (
            "ok"
            if not failed_items
            else ("fail" if not self._config.continue_on_item_failure else "ok")
        )
        error = None
        if failed_items and not self._config.continue_on_item_failure:
            error = NodeError(
                code="fan_out.items_failed",
                message=f"{len(failed_items)} of {len(items)} items failed",
                details={"failed_items": failed_items},
            )

        apply_merged_state = error is None
        merged_state = state
        resolved_conflict_events: list[NodeEvent] = []
        if apply_merged_state:
            staged_outcomes = {f"item[{i}]": outcome for i, outcome, _ in ok_outcomes}
            staged_write_specs = {
                f"item[{i}]": list(write_paths) for i, _, write_paths in ok_outcomes
            }
            aggregate_write_paths: list[str] = []
            aggregate_state = state
            if params_write is not None or artifact_index_updates:
                if params_write is not None:
                    aggregate_write_paths.append(params_write[0])
                if artifact_index_updates:
                    aggregate_write_paths.append("artifacts_index")
                aggregate_state = branch_state(
                    state,
                    write_paths=aggregate_write_paths,
                ).state
                if params_write is not None:
                    try:
                        self._write_result(aggregate_state, params_write[0], params_write[1])
                    except ValueError as exc:
                        return NodeOutcome(
                            status="fail",
                            state=state,
                            error=NodeError(
                                code="fan_out.invalid_result_path",
                                message=str(exc),
                                details={"result_state_path": params_write[0]},
                            ),
                        )
                if artifact_index_updates:
                    aggregate_state.artifacts_index.update(artifact_index_updates)
                staged_outcomes["fan_out.aggregate"] = NodeOutcome(
                    status="ok",
                    state=aggregate_state,
                )
                staged_write_specs["fan_out.aggregate"] = aggregate_write_paths

            merge_result = merge_parallel_outcomes(
                state,
                staged_outcomes,
                staged_write_specs,
                conflict_policy=self._config.merge_conflict_policy,
            )
            if not merge_result.applied:
                return NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code="fan_out.merge_conflict",
                        message="fan-out merge conflict blocked atomic state application",
                        details={
                            "conflicts": [item.to_dict() for item in merge_result.conflict_details],
                        },
                    ),
                )
            merged_state = merge_result.state
            resolved_conflict_events = [
                NodeEvent(
                    level="warn",
                    message="Fan-out merge conflict resolved by policy",
                    code="fan_out.merge_conflict_resolved",
                    attrs={
                        "path": conflict.path,
                        "resolution": conflict.resolution.value,
                        "aliases": ",".join(conflict.aliases),
                    },
                )
                for conflict in merge_result.resolved_conflicts
            ]

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
            *resolved_conflict_events,
            *degraded_events,
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
            raise ValueError(
                "fan-out result_state_path cannot target artifacts_index for "
                "non-ArtifactRef merge results; use merge_strategy='artifact_index'",
            )
        else:
            raise ValueError(
                "fan-out result_state_path must target 'params.*' or "
                "'artifacts_index' with merge_strategy='artifact_index'"
            )
