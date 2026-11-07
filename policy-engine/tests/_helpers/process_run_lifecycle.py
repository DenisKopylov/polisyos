"""Importable process worker and fixture for lifecycle-resume cache tests."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from decimal import Decimal
from pathlib import Path

from _helpers.execution_admission import AdmissionNode
from _helpers.run_lifecycle import interrupt_before_finalize
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.checkpoint import CASCheckpointHook, acquire_run_lock
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.protocol import (
    InputAwareNodeSpec,
    NodeEvent,
    NodeInputRule,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_CACHED_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_cached_counter@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Cached Counter",
    description="Test node for idempotency cache recovery",
    tags=["test"],
    capabilities=Capability.SCIENTIST_NODE,
)

_CACHED_SPEC = NodeSpec(
    metadata=_CACHED_METADATA,
    state_reads=["params.seed"],
    state_writes=["params.cached_counter"],
)


class CachedCounterNode:
    """Stable cache-node fixture shared by spawned producer and fresh receiver."""

    calls = 0

    @property
    def spec(self) -> NodeSpec:
        return _CACHED_SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        CachedCounterNode.calls += 1
        new_state = state.model_copy(deep=True)
        new_state.params["cached_counter"] = CachedCounterNode.calls
        return NodeOutcome(status="ok", state=new_state)


class CheckpointedCacheEffectNode(AdmissionNode):
    """Stable source-backed cache producer with a real durable SQLite effect."""

    def __init__(self, database: Path, ledger: Path, value: int = 7) -> None:
        super().__init__(database, value=value)
        self.ledger = ledger

    @property
    def spec(self) -> NodeSpec:
        original = super().spec
        return InputAwareNodeSpec(
            metadata=original.metadata,
            state_reads=["params.seed"],
            state_writes=["params"],
            produces=original.produces,
            input_rules=(NodeInputRule(path="params.seed"),),
        )

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        outcome = super().execute(ctx, state)
        operation_id = f"{state.run_id}/selected-operation-7"
        BudgetMiddleware(
            BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))}),
            ledger=FileBudgetLedger(self.ledger),
        ).settle_spend_safe(
            event_id=operation_id,
            key="run",
            amount=Decimal("2"),
            provider="local-test-producer",
            payload_digest=hashlib.sha256(operation_id.encode()).hexdigest(),
        )
        state.params["y"] = 4
        del state.params["drop"]
        state.params["null"] = None
        outcome.events.append(NodeEvent(code="test.physical_effect", message=operation_id))
        return outcome


class CheckpointCacheBaseMutator:
    """Prepare the actual warm base before the durable checkpoint."""

    spec = NodeSpec(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse("scientist.node_checkpoint_cache_mutator@1.0.0"),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            capabilities=Capability.SCIENTIST_NODE,
        ),
        state_writes=["params"],
    )

    def execute(self, _ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        state.params.update(
            {"y": 9, "drop": 99, "null": 88, "unwritten": "current", "unrelated": "new"}
        )
        state.params.pop("removed_elsewhere", None)
        return NodeOutcome(status="ok", state=state)


def checkpointed_cache_workflow() -> WorkflowSpec:
    """Use the same cache contract for two distinct original DAG aliases."""
    node_id = ComponentId.parse("scientist.node_admission_probe@1.0.0")
    return WorkflowSpec(
        workflow_id="cache_resume_after_process_loss",
        nodes=[
            NodeInvocation(alias="cold", node_id=node_id),
            NodeInvocation(
                alias="mutate",
                node_id=CheckpointCacheBaseMutator.spec.metadata.component_id,
                depends_on=["cold"],
            ),
            NodeInvocation(alias="warm", node_id=node_id, depends_on=["mutate"]),
        ],
    )


def checkpointed_cache_registry(database: Path, ledger: Path) -> NodeRegistry:
    registry = NodeRegistry()
    registry.register(CheckpointedCacheEffectNode(database, ledger, value=7))
    registry.register(CheckpointCacheBaseMutator())
    return registry


def produce_cached_checkpoint_then_exit(
    store_root: str, run_id: str, database: str, ledger: str
) -> None:
    """Stop a real process after cold commits its selected checkpoint and cache."""
    store = FileSystemCAS(Path(store_root))
    bundle = build_default_registry_bundle(store, return_selected_profile=True)
    run_dir = Path(store_root) / "runs" / run_id
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("cache_checkpoint"))

    class StopAfterMutation(CASCheckpointHook):
        async def on_node_complete_async(self, **kwargs):
            result = await super().on_node_complete_async(**kwargs)
            if kwargs["alias"] == "mutate":
                os._exit(73)
            return result

    lock = acquire_run_lock(run_dir, run_id=run_id, mode="execute")
    try:
        hook = StopAfterMutation(store=store, run_dir=run_dir)
        executor = AsyncWorkflowExecutor(
            ctx,
            checkpointed_cache_registry(Path(database), Path(ledger)),
            checkpoint_hook=hook,
            max_parallelism=1,
            capture_workflow_execution_admission=True,
        )
        asyncio.run(
            executor.execute(
                checkpointed_cache_workflow(),
                ExperimentState(
                    run_id=run_id,
                    inputs={"registry_bundle_ref": bundle.bundle_ref},
                    params={
                        "seed": 7,
                        "y": 4,
                        "drop": 1,
                        "null": 8,
                        "unwritten": "old",
                        "unrelated": "old",
                        "removed_elsewhere": "old",
                    },
                ),
            )
        )
        raise AssertionError("current-base checkpoint did not interrupt the worker")
    finally:
        lock.release()


def produce_cached_run_then_exit_before_finalize(store_root: str, run_id: str) -> None:
    """Write a real cache entry, suspend at finalize, and model process loss."""
    store = FileSystemCAS(Path(store_root))
    bundle = build_default_registry_bundle(store, return_selected_profile=True)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id=run_id)
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("idempotency_process_worker"),
    )
    registry = NodeRegistry()
    registry.register(CachedCounterNode())
    workflow = WorkflowSpec(
        workflow_id="cache_resume_after_process_loss",
        nodes=[
            NodeInvocation(
                alias="cached",
                node_id=ComponentId.parse("scientist.node_cached_counter@1.0.0"),
            ),
        ],
    )
    events = interrupt_before_finalize(
        run,
        lambda: WorkflowExecutor(ctx, registry).execute(
            workflow,
            ExperimentState(run_id=run_id, params={"seed": 7}),
        ),
    )
    assert sum(event.get("event") == "NODE_CACHE_STORE" for event in events) == 1
    os._exit(73)
