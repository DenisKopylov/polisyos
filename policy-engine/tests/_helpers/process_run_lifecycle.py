"""Importable process worker and fixture for lifecycle-resume cache tests."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from _helpers.run_lifecycle import interrupt_before_finalize
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
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
