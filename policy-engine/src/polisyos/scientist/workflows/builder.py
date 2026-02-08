from __future__ import annotations

import logging
from pathlib import Path

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext, new_run_id
from polisyos.core.security.tenant_context import get_current_cell_id, get_current_tenant_id_or_none
from polisyos.scientist.engine.checkpoint import (
    CASCheckpointHook,
    CheckpointPolicy,
    acquire_run_lock,
    normalize_checkpoint_policy,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.executor import WorkflowExecutionResult, WorkflowExecutor
from polisyos.scientist.engine.registry import NodeRegistry
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.builtins import builtin_nodes as engine_builtin_nodes
from polisyos.scientist.foundry import DefaultFoundryPort
from polisyos.scientist.nodes.builtins import builtin_nodes as scientist_builtin_nodes
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_DATA_VIEW_REQUEST_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_STATE_SNAPSHOT_REF,
)
from polisyos.scientist.workflows.default import default_workflow_spec


DEFAULT_CAS_ROOT = Path(".polisyos")


def build_default_registry(store: FileSystemCAS) -> ArtifactRef:
    bundle = build_default_registry_bundle(store)
    return bundle.bundle_ref


def build_execution_context(
    store: FileSystemCAS,
    registry_bundle_ref: ArtifactRef,
    *,
    run_id: str,
    logger: logging.Logger | None = None,
    tracer: object | None = None,
    foundry: object | None = None,
    fabric: object | None = None,
    scholar: object | None = None,
    lex: object | None = None,
) -> ExecutionContext:
    run = RunContext.start(
        store,
        registry_bundle_ref,
        run_id=run_id,
        tenant_id=get_current_tenant_id_or_none(),
        cell_id=get_current_cell_id(),
    )
    return ExecutionContext(
        store=store,
        run=run,
        logger=logger or logging.getLogger("polisyos.scientist.engine"),
        tracer=tracer,
        foundry=foundry,
        fabric=fabric,
        scholar=scholar,
        lex=lex,
    )


def build_registry_with_builtin_nodes() -> NodeRegistry:
    registry = NodeRegistry()
    for node in engine_builtin_nodes():
        registry.register(node)
    for node in scientist_builtin_nodes():
        registry.register(node)
    return registry


def _ensure_snapshot_bind(state: ExperimentState) -> None:
    if (
        INPUT_DATA_SNAPSHOT_REF not in state.inputs
        and INPUT_STATE_SNAPSHOT_REF not in state.inputs
        and INPUT_DATA_VIEW_REQUEST_REF not in state.inputs
    ):
        raise ValueError(
            "Missing snapshot input: provide data_snapshot_ref, state_snapshot_ref, or data_view_request_ref"
        )


def run_default_workflow(
    initial_state: ExperimentState,
    *,
    store: FileSystemCAS | None = None,
    registry_bundle_ref: ArtifactRef | None = None,
    checkpoint_policy: CheckpointPolicy = "strict",
    force_lock: bool = False,
    foundry: object | None = None,
    fabric: object | None = None,
    scholar: object | None = None,
    lex: object | None = None,
    logger: logging.Logger | None = None,
    tracer: object | None = None,
) -> WorkflowExecutionResult:
    store = store or FileSystemCAS(DEFAULT_CAS_ROOT)
    policy = normalize_checkpoint_policy(checkpoint_policy)

    state = initial_state.model_copy(deep=True)
    if not state.run_id:
        state = state.model_copy(update={"run_id": new_run_id()})

    if registry_bundle_ref is None:
        registry_bundle_ref = state.inputs.get(INPUT_REGISTRY_BUNDLE_REF)
    if registry_bundle_ref is None:
        registry_bundle_ref = build_default_registry(store)
    state.inputs[INPUT_REGISTRY_BUNDLE_REF] = registry_bundle_ref

    _ensure_snapshot_bind(state)

    if foundry is None:
        foundry = DefaultFoundryPort()

    run_dir = store.root / "runs" / state.run_id
    lock = acquire_run_lock(run_dir, run_id=state.run_id, mode="run", force=force_lock)
    try:
        ctx = build_execution_context(
            store,
            registry_bundle_ref,
            run_id=state.run_id,
            logger=logger,
            tracer=tracer,
            foundry=foundry,
            fabric=fabric,
            scholar=scholar,
            lex=lex,
        )

        registry = build_registry_with_builtin_nodes()
        checkpoint_hook = CASCheckpointHook(
            store=store,
            run_dir=run_dir,
            sequence_start=0,
            checkpoint_policy=policy,
        )
        executor = WorkflowExecutor(ctx, registry, checkpoint_hook=checkpoint_hook)
        workflow = default_workflow_spec()
        return executor.execute(workflow, state)
    finally:
        lock.release()


__all__ = [
    "build_default_registry",
    "build_execution_context",
    "build_registry_with_builtin_nodes",
    "run_default_workflow",
]
