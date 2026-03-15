from __future__ import annotations

import logging
from pathlib import Path

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import ENTRY_POINT_GROUP_SCIENTIST_NODES
from polisyos.core.components.bootstrap import build_components_index
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext, new_run_id
from polisyos.core.security.tenant_context import (
    get_current_access_scope_or_none,
    get_current_cell_id,
    get_current_tenant_id_or_none,
)
from polisyos.scientist.adapters.fabric_bridge import DefaultFabricPort
from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
from polisyos.scientist.engine.builtins import builtin_nodes as engine_builtin_nodes
from polisyos.scientist.engine.checkpoint import (
    CASCheckpointHook,
    CheckpointPolicy,
    acquire_run_lock,
    normalize_checkpoint_policy,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.executor import WorkflowExecutionResult, WorkflowExecutor
from polisyos.scientist.engine.registry import NodeRegistry, discover_nodes
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import builtin_nodes as scientist_builtin_nodes
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_DATA_VIEW_REQUEST_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_REGISTRY_BUNDLE_REF,
)
from polisyos.scientist.workflows.causal_full import causal_full_workflow_spec
from polisyos.scientist.workflows.default import default_workflow_spec
from polisyos.scientist.workflows.selection import resolve_workflow_id as _resolve_workflow_id

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
        access_scope=get_current_access_scope_or_none(),
    )
    return ExecutionContext(
        store=store,
        run=run,
        logger=logger or get_logger("polisyos.scientist.engine"),
        tracer=tracer,
        foundry=foundry,
        fabric=fabric,
        scholar=scholar,
        lex=lex,
    )


def _propagate_runtime_run_metadata(ctx: ExecutionContext, state: ExperimentState) -> None:
    if state.execution_profile:
        ctx.run.run_manifest.execution_profile = str(state.execution_profile)
    if state.control_job_id:
        ctx.run.run_manifest.control_job_id = str(state.control_job_id)
    if state.capability_manifest_ref is not None:
        ctx.run.run_manifest.capability_manifest_ref = state.capability_manifest_ref


def build_registry_with_builtin_nodes(
    *,
    include_discovered_nodes: bool = True,
) -> NodeRegistry:
    registry = NodeRegistry()
    for node in engine_builtin_nodes():
        registry.register(node)
    for node in scientist_builtin_nodes():
        registry.register(node)

    if include_discovered_nodes:
        components_index, _ = build_components_index(
            groups=[ENTRY_POINT_GROUP_SCIENTIST_NODES],
            include_dev_scan=True,
        )
        discover_nodes(registry, components_index=components_index)

    return registry


def _ensure_snapshot_bind(state: ExperimentState) -> None:
    if (
        INPUT_DATA_SNAPSHOT_REF not in state.inputs
        and INPUT_INPUT_BINDINGS_REF not in state.inputs
        and INPUT_DATA_VIEW_REQUEST_REF not in state.inputs
    ):
        raise ValueError(
            "Missing snapshot input: provide data_snapshot_ref, input_bindings_ref, "
            "or data_view_request_ref"
        )


def resolve_workflow_id(initial_state: ExperimentState) -> str:
    return _resolve_workflow_id(initial_state)


def run_selected_workflow(
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
    workflow_id = resolve_workflow_id(initial_state)
    if workflow_id == "scientist_causal_full":
        return run_causal_full_workflow(
            initial_state,
            store=store,
            registry_bundle_ref=registry_bundle_ref,
            checkpoint_policy=checkpoint_policy,
            force_lock=force_lock,
            foundry=foundry,
            fabric=fabric,
            scholar=scholar,
            lex=lex,
            logger=logger,
            tracer=tracer,
        )
    return run_default_workflow(
        initial_state,
        store=store,
        registry_bundle_ref=registry_bundle_ref,
        checkpoint_policy=checkpoint_policy,
        force_lock=force_lock,
        foundry=foundry,
        fabric=fabric,
        scholar=scholar,
        lex=lex,
        logger=logger,
        tracer=tracer,
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
    state.params["workflow_id"] = "scientist_default"

    if registry_bundle_ref is None:
        registry_bundle_ref = state.inputs.get(INPUT_REGISTRY_BUNDLE_REF)
    if registry_bundle_ref is None:
        registry_bundle_ref = build_default_registry(store)
    state.inputs[INPUT_REGISTRY_BUNDLE_REF] = registry_bundle_ref

    _ensure_snapshot_bind(state)

    if foundry is None:
        foundry = DefaultFoundryPort()
    if fabric is None and INPUT_DATA_VIEW_REQUEST_REF in state.inputs:
        fabric = DefaultFabricPort()

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
        _propagate_runtime_run_metadata(ctx, state)

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


def run_causal_full_workflow(
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
    state.params["workflow_id"] = "scientist_causal_full"
    state.params.setdefault("allow_degraded_transport", False)

    if registry_bundle_ref is None:
        registry_bundle_ref = state.inputs.get(INPUT_REGISTRY_BUNDLE_REF)
    if registry_bundle_ref is None:
        registry_bundle_ref = build_default_registry(store)
    state.inputs[INPUT_REGISTRY_BUNDLE_REF] = registry_bundle_ref

    _ensure_snapshot_bind(state)

    if foundry is None:
        foundry = DefaultFoundryPort()
    if fabric is None and INPUT_DATA_VIEW_REQUEST_REF in state.inputs:
        fabric = DefaultFabricPort()

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
        _propagate_runtime_run_metadata(ctx, state)

        registry = build_registry_with_builtin_nodes()
        checkpoint_hook = CASCheckpointHook(
            store=store,
            run_dir=run_dir,
            sequence_start=0,
            checkpoint_policy=policy,
        )
        executor = WorkflowExecutor(ctx, registry, checkpoint_hook=checkpoint_hook)
        workflow = causal_full_workflow_spec()
        return executor.execute(workflow, state)
    finally:
        lock.release()


__all__ = [
    "build_default_registry",
    "build_execution_context",
    "build_registry_with_builtin_nodes",
    "resolve_workflow_id",
    "run_default_workflow",
    "run_causal_full_workflow",
    "run_selected_workflow",
]
