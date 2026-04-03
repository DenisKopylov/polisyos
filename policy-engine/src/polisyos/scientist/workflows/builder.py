"""Execution helpers that bind workflow specs, node registries, and runtime ports.

These functions are the stable launchpad beneath `run_experiment()`: they pin
cross-layer CAS refs, create `ExecutionContext`, register builtin/discovered
nodes, enforce run locks/checkpoint policy, and delegate to the selected
`WorkflowSpec`.
"""
from __future__ import annotations

import logging
from pathlib import Path

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.protocol import ArtifactStore
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
from polisyos.scientist.engine.runner.config import WorkflowRunnerConfig, build_workflow_runner
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import builtin_nodes as scientist_builtin_nodes
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_DATA_VIEW_REQUEST_REF,
    INPUT_GRAPH_PRIOR_BUNDLE_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_REGISTRY_BUNDLE_REF,
)
from polisyos.scientist.workflows.causal_full import causal_full_workflow_spec
from polisyos.scientist.workflows.discovery import discovery_workflow_spec
from polisyos.scientist.workflows.default import default_workflow_spec
from polisyos.scientist.workflows.policy_design import policy_design_workflow_spec
from polisyos.scientist.workflows.policy_verified import policy_verified_workflow_spec
from polisyos.scientist.workflows.selection import resolve_workflow_id as _resolve_workflow_id

DEFAULT_CAS_ROOT = Path(".polisyos")

# Global quota registry — shared across workflow invocations
_global_quota_registry: object | None = None


def _get_global_quota_registry() -> object | None:
    """Lazy-init global TenantQuotaRegistry."""
    global _global_quota_registry
    if _global_quota_registry is not None:
        return _global_quota_registry
    try:
        from polisyos.core.security.quota_registry import TenantQuotaRegistry
        _global_quota_registry = TenantQuotaRegistry()
        return _global_quota_registry
    except Exception:  # noqa: BLE001
        return None


def _maybe_enforce_quota() -> object | None:
    """Check and record quota for the current tenant if active.

    Returns the QuotaEnforcer (for calling record_run_end in finally),
    or None if no tenant context.
    """
    tenant_id = get_current_tenant_id_or_none()
    if tenant_id is None:
        return None
    registry = _get_global_quota_registry()
    if registry is None:
        return None
    try:
        enforcer = registry.get_enforcer(tenant_id)  # type: ignore[union-attr]
        enforcer.check_run_start()
        enforcer.record_run_start()
        return enforcer
    except Exception:
        raise


def _maybe_namespace_store(store: ArtifactStore) -> ArtifactStore:
    """Wrap store with namespace isolation if tenant context is active."""
    tenant_id = get_current_tenant_id_or_none()
    if tenant_id is None:
        return store
    try:
        from polisyos.core.security.namespace import NamespacedArtifactStore
        cell_id = get_current_cell_id()
        return NamespacedArtifactStore(inner=store, tenant_id=tenant_id, cell_id=cell_id)
    except Exception:  # noqa: BLE001
        return store


def _maybe_create_provenance_dag(run_id: str) -> object | None:
    """Try to create a RunProvenanceDAG; return None if unavailable."""
    try:
        from polisyos.scientist.provenance.run_dag import RunProvenanceDAG
        tenant_id = get_current_tenant_id_or_none()
        return RunProvenanceDAG(run_id=run_id, tenant_id=tenant_id)
    except Exception:  # noqa: BLE001
        return None


def _artifact_ref_or_none(value: object) -> ArtifactRef | None:
    if isinstance(value, ArtifactRef):
        return value
    if isinstance(value, dict):
        try:
            return ArtifactRef.model_validate(value)
        except Exception:  # noqa: BLE001
            return None
    return None


def _pin_cross_layer_input_ref(
    state: ExperimentState,
    *,
    input_key: str,
    provided_ref: ArtifactRef | None = None,
) -> ArtifactRef | None:
    input_ref = _artifact_ref_or_none(state.inputs.get(input_key))
    param_ref = _artifact_ref_or_none(state.params.get(input_key))
    resolved = next((ref for ref in (provided_ref, input_ref, param_ref) if ref is not None), None)

    if resolved is None:
        return None

    for candidate in (provided_ref, input_ref, param_ref):
        if candidate is not None and candidate != resolved:
            raise ValueError(
                f"{input_key} must be CAS-pinned before workflow start; received mismatched refs."
            )

    state.inputs[input_key] = resolved
    state.params[input_key] = resolved.model_dump(mode="json")
    return resolved


def build_default_registry(store: ArtifactStore) -> ArtifactRef:
    """Persist the default component registry bundle used by Scientist workflows.

    Args:
        store: Artifact store where the registry bundle should be persisted.

    Returns:
        CAS reference to the generated registry bundle.
    """
    bundle = build_default_registry_bundle(store)
    return bundle.bundle_ref


def _default_engine_metrics() -> object | None:
    """Try to create an OTel-backed engine metrics collector; fall back to None."""
    try:
        from polisyos.scientist.engine.metrics_otel import OTelEngineMetrics

        return OTelEngineMetrics()
    except Exception:  # noqa: BLE001
        return None


def build_execution_context(
    store: ArtifactStore,
    registry_bundle_ref: ArtifactRef,
    *,
    run_id: str,
    logger: logging.Logger | None = None,
    tracer: object | None = None,
    foundry: object | None = None,
    fabric: object | None = None,
    scholar: object | None = None,
    lex: object | None = None,
    metrics: object | None = None,
    audit: object | None = None,
    memory: object | None = None,
    depth: int = 0,
) -> ExecutionContext:
    """Create the engine execution context shared by all nodes in one run.

    Args:
        store: Artifact store used for node inputs, outputs, and checkpoints.
        registry_bundle_ref: Registry bundle ref pinned into the run manifest.
        run_id: Run identifier used by provenance, metrics, and artifact lineage.
        logger: Optional logger injected into node execution.
        tracer: Optional tracer propagated to the executor.
        foundry: Optional Foundry port override, otherwise nodes may use defaults.
        fabric: Optional Fabric port override.
        scholar: Optional scholar connector implementation.
        lex: Optional Lex connector implementation.
        metrics: Optional engine metrics collector.
        audit: Optional audit sink.
        memory: Optional memory backend.
        depth: Sub-workflow nesting depth for trace/debug metadata.

    Returns:
        Fully initialized `ExecutionContext` with a started `RunContext`.
    """
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
        depth=depth,
        metrics=metrics if metrics is not None else _default_engine_metrics(),
        audit=audit,
        fabric=fabric,
        foundry=foundry,
        scholar=scholar,
        lex=lex,
        memory=memory,
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
    """Register engine builtins, Scientist builtins, and optional plugin nodes.

    Args:
        include_discovered_nodes: When `True`, merge entry-point discovered
            `polisyos.scientist_nodes` implementations into the registry.

    Returns:
        `NodeRegistry` ready to resolve `WorkflowSpec.node_id` references.
    """
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
    """Select the workflow id implied by state params, execution profile, and inputs.

    Args:
        initial_state: Caller-provided state envelope before orchestration begins.

    Returns:
        One of the builtin workflow ids accepted by `run_selected_workflow()`.
    """
    return _resolve_workflow_id(initial_state)


def run_selected_workflow(
    initial_state: ExperimentState,
    *,
    store: ArtifactStore | None = None,
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
    """Dispatch to the builtin workflow runner chosen by `resolve_workflow_id()`.

    Args:
        initial_state: Initial `ExperimentState` payload.
        store: Optional artifact store override.
        registry_bundle_ref: Optional registry bundle override; otherwise a default
            bundle is generated or reused from state inputs.
        checkpoint_policy: Checkpoint/replay policy enforced by the executor.
        force_lock: Break an existing run lock when recovering an interrupted run.
        foundry: Optional Foundry port override.
        fabric: Optional Fabric port override.
        scholar: Optional scholar adapter.
        lex: Optional Lex adapter.
        logger: Optional workflow logger.
        tracer: Optional tracer object.

    Returns:
        `WorkflowExecutionResult` from the concrete DAG runner.
    """
    workflow_id = resolve_workflow_id(initial_state)
    if workflow_id == "scientist_policy_design":
        return run_policy_design_workflow(
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
    if workflow_id == "scientist_discovery":
        return run_discovery_workflow(
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
    if workflow_id == "scientist_policy_verified":
        return run_policy_verified_workflow(
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


def run_policy_design_workflow(
    initial_state: ExperimentState,
    *,
    store: ArtifactStore | None = None,
    registry_bundle_ref: ArtifactRef | None = None,
    graph_prior_bundle_ref: ArtifactRef | None = None,
    checkpoint_policy: CheckpointPolicy = "strict",
    force_lock: bool = False,
    foundry: object | None = None,
    fabric: object | None = None,
    scholar: object | None = None,
    lex: object | None = None,
    logger: logging.Logger | None = None,
    tracer: object | None = None,
) -> WorkflowExecutionResult:
    """Execute the `scientist_policy_design` DAG with search and translation stages."""
    store = store or FileSystemCAS(DEFAULT_CAS_ROOT)
    store = _maybe_namespace_store(store)
    policy = normalize_checkpoint_policy(checkpoint_policy)

    state = initial_state.model_copy(deep=True)
    if not state.run_id:
        state = state.model_copy(update={"run_id": new_run_id()})
    state.params["workflow_id"] = "scientist_policy_design"
    state.params.setdefault("policy_mode", True)
    state.execution_profile = state.execution_profile or "policy_design"

    if registry_bundle_ref is None:
        registry_bundle_ref = state.inputs.get(INPUT_REGISTRY_BUNDLE_REF)
    if registry_bundle_ref is None:
        registry_bundle_ref = build_default_registry(store)
    registry_bundle_ref = _pin_cross_layer_input_ref(
        state,
        input_key=INPUT_REGISTRY_BUNDLE_REF,
        provided_ref=registry_bundle_ref,
    ) or registry_bundle_ref
    if graph_prior_bundle_ref is None:
        graph_prior_bundle_ref = _artifact_ref_or_none(
            state.inputs.get(INPUT_GRAPH_PRIOR_BUNDLE_REF)
        )
    _pin_cross_layer_input_ref(
        state,
        input_key=INPUT_GRAPH_PRIOR_BUNDLE_REF,
        provided_ref=graph_prior_bundle_ref,
    )

    _ensure_snapshot_bind(state)

    if foundry is None:
        foundry = DefaultFoundryPort()
    if fabric is None and INPUT_DATA_VIEW_REQUEST_REF in state.inputs:
        fabric = DefaultFabricPort()

    run_dir = getattr(store, "root", Path(".")) / "runs" / state.run_id
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
        workflow = policy_design_workflow_spec()
        return executor.execute(workflow, state)
    finally:
        lock.release()


def run_discovery_workflow(
    initial_state: ExperimentState,
    *,
    store: ArtifactStore | None = None,
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
    """Execute the discovery-only DAG and persist prior-knowledge artifacts."""
    store = store or FileSystemCAS(DEFAULT_CAS_ROOT)
    store = _maybe_namespace_store(store)
    policy = normalize_checkpoint_policy(checkpoint_policy)

    state = initial_state.model_copy(deep=True)
    if not state.run_id:
        state = state.model_copy(update={"run_id": new_run_id()})
    state.params["workflow_id"] = "scientist_discovery"
    state.execution_profile = state.execution_profile or "discovery"

    if registry_bundle_ref is None:
        registry_bundle_ref = state.inputs.get(INPUT_REGISTRY_BUNDLE_REF)
    if registry_bundle_ref is None:
        registry_bundle_ref = build_default_registry(store)
    _pin_cross_layer_input_ref(
        state,
        input_key=INPUT_REGISTRY_BUNDLE_REF,
        provided_ref=registry_bundle_ref,
    )

    run_dir = getattr(store, "root", Path(".")) / "runs" / state.run_id
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
        workflow = discovery_workflow_spec()
        return executor.execute(workflow, state)
    finally:
        lock.release()

def run_default_workflow(
    initial_state: ExperimentState,
    *,
    store: ArtifactStore | None = None,
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
    """Execute the baseline simulation/governance DAG."""
    store = store or FileSystemCAS(DEFAULT_CAS_ROOT)
    store = _maybe_namespace_store(store)
    policy = normalize_checkpoint_policy(checkpoint_policy)

    state = initial_state.model_copy(deep=True)
    if not state.run_id:
        state = state.model_copy(update={"run_id": new_run_id()})
    state.params["workflow_id"] = "scientist_default"

    if registry_bundle_ref is None:
        registry_bundle_ref = state.inputs.get(INPUT_REGISTRY_BUNDLE_REF)
    if registry_bundle_ref is None:
        registry_bundle_ref = build_default_registry(store)
    _pin_cross_layer_input_ref(
        state,
        input_key=INPUT_REGISTRY_BUNDLE_REF,
        provided_ref=registry_bundle_ref,
    )

    _ensure_snapshot_bind(state)

    if foundry is None:
        foundry = DefaultFoundryPort()
    if fabric is None and INPUT_DATA_VIEW_REQUEST_REF in state.inputs:
        fabric = DefaultFabricPort()

    enforcer = _maybe_enforce_quota()
    run_dir = getattr(store, "root", Path(".")) / "runs" / state.run_id
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
        provenance_dag = _maybe_create_provenance_dag(state.run_id)

        runner_config = WorkflowRunnerConfig.from_env()
        workflow = default_workflow_spec()
        if runner_config.backend != "local":
            import asyncio
            runner = build_workflow_runner(runner_config)
            return asyncio.run(runner.execute_workflow(
                workflow, state, ctx, registry,
                checkpoint_hook=checkpoint_hook,
                max_parallelism=runner_config.max_parallelism,
            ))

        executor = WorkflowExecutor(ctx, registry, checkpoint_hook=checkpoint_hook)
        return executor.execute(workflow, state)
    finally:
        lock.release()
        if enforcer is not None:
            enforcer.record_run_end()


def run_policy_verified_workflow(
    initial_state: ExperimentState,
    *,
    store: ArtifactStore | None = None,
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
    """Execute the verified-policy DAG that omits hierarchical champion search."""
    store = store or FileSystemCAS(DEFAULT_CAS_ROOT)
    store = _maybe_namespace_store(store)
    policy = normalize_checkpoint_policy(checkpoint_policy)

    state = initial_state.model_copy(deep=True)
    if not state.run_id:
        state = state.model_copy(update={"run_id": new_run_id()})
    state.params["workflow_id"] = "scientist_policy_verified"
    state.execution_profile = state.execution_profile or "policy_verified_async"
    state.params.setdefault("policy_answer_mode", "verified_async")
    state.params.setdefault("allow_hypotheses", True)
    state.params.setdefault("policy_request_jurisdiction", "UA")
    state.params.setdefault("max_candidate_queries", 40)
    state.params.setdefault("max_source_docs", 120)
    state.params.setdefault("max_source_anchors", 400)
    state.params.setdefault("max_reference_hops", 2)
    state.params.setdefault("max_verifier_calls", 500)
    state.params.setdefault("max_gap_review_calls", 80)
    state.params.setdefault("verification_cycles_completed", 0)

    if registry_bundle_ref is None:
        registry_bundle_ref = state.inputs.get(INPUT_REGISTRY_BUNDLE_REF)
    if registry_bundle_ref is None:
        registry_bundle_ref = build_default_registry(store)
    _pin_cross_layer_input_ref(
        state,
        input_key=INPUT_REGISTRY_BUNDLE_REF,
        provided_ref=registry_bundle_ref,
    )

    _ensure_snapshot_bind(state)

    if foundry is None:
        foundry = DefaultFoundryPort()
    if fabric is None and INPUT_DATA_VIEW_REQUEST_REF in state.inputs:
        fabric = DefaultFabricPort()

    run_dir = getattr(store, "root", Path(".")) / "runs" / state.run_id
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
        workflow = policy_verified_workflow_spec()
        return executor.execute(workflow, state)
    finally:
        lock.release()


def run_causal_full_workflow(
    initial_state: ExperimentState,
    *,
    store: ArtifactStore | None = None,
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
    """Execute the full causal DAG with graph reconciliation and transport checks."""
    store = store or FileSystemCAS(DEFAULT_CAS_ROOT)
    store = _maybe_namespace_store(store)
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
    _pin_cross_layer_input_ref(
        state,
        input_key=INPUT_REGISTRY_BUNDLE_REF,
        provided_ref=registry_bundle_ref,
    )

    _ensure_snapshot_bind(state)

    if foundry is None:
        foundry = DefaultFoundryPort()
    if fabric is None and INPUT_DATA_VIEW_REQUEST_REF in state.inputs:
        fabric = DefaultFabricPort()

    run_dir = getattr(store, "root", Path(".")) / "runs" / state.run_id
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
    "run_policy_design_workflow",
    "run_policy_verified_workflow",
    "run_selected_workflow",
]
