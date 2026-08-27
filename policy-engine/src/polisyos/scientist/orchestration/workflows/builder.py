"""Execution helpers that bind workflow specs, node registries, and runtime ports.

These functions are the stable launchpad beneath `run_experiment()`: they pin
cross-layer CAS refs, create `ExecutionContext`, register builtin/discovered
nodes, enforce run locks/checkpoint policy, and delegate to the selected
`WorkflowSpec`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext, new_run_id
from polisyos.core.security import (
    get_current_access_scope_or_none,
    get_current_cell_id,
    get_current_tenant_id_or_none,
)
from polisyos.scientist.adapters.fabric_bridge import DefaultFabricPort
from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
from polisyos.scientist.methods.research_dag.projections import RESEARCH_DAG_FEATURE_FLAG
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_DATA_VIEW_REQUEST_REF,
    INPUT_GRAPH_PRIOR_BUNDLE_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_REGISTRY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.builtins import builtin_nodes as engine_builtin_nodes
from polisyos.scientist.orchestration.engine.checkpoint import (
    CASCheckpointHook,
    CheckpointPolicy,
    acquire_run_lock,
    normalize_checkpoint_policy,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import (
    WorkflowExecutionResult,
    WorkflowExecutor,
)
from polisyos.scientist.orchestration.engine.registry import NodeRegistry, discover_nodes
from polisyos.scientist.orchestration.engine.runner.config import (
    WorkflowRunnerConfig,
    build_workflow_runner,
)
from polisyos.scientist.orchestration.engine.state_branching import snapshot_state
from polisyos.scientist.orchestration.workflows.causal_full import causal_full_workflow_spec
from polisyos.scientist.orchestration.workflows.default import default_workflow_spec
from polisyos.scientist.orchestration.workflows.discovery import discovery_workflow_spec
from polisyos.scientist.orchestration.workflows.policy_design import policy_design_workflow_spec
from polisyos.scientist.orchestration.workflows.policy_verified import policy_verified_workflow_spec
from polisyos.scientist.orchestration.workflows.selection import (
    resolve_workflow_id as _resolve_workflow_id,
)

if TYPE_CHECKING:
    import logging
    from collections.abc import Callable
    from typing import Protocol

    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.core.security import AuditLog
    from polisyos.scientist.orchestration.engine.context import (
        FabricPort,
        FoundryPort,
        LexPort,
        ScholarPort,
        Tracer,
    )
    from polisyos.scientist.orchestration.engine.metrics_protocol import EngineMetricsCollector
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    class QuotaEnforcer(Protocol):
        def check_run_start(self) -> None: ...
        def record_run_start(self) -> None: ...
        def record_run_end(self) -> None: ...

    class QuotaRegistry(Protocol):
        def get_enforcer(self, tenant_id: str) -> QuotaEnforcer: ...


DEFAULT_CAS_ROOT = Path(".polisyos/cas")
_WORKFLOW_BUILDER_IMPORT_ERRORS = (ImportError, ModuleNotFoundError)
_WORKFLOW_BUILDER_NAMESPACE_ERRORS = (
    AttributeError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)
_WORKFLOW_BUILDER_PROVENANCE_ERRORS = (
    AttributeError,
    RuntimeError,
    TypeError,
    ValueError,
)
_WORKFLOW_BUILDER_ARTIFACT_REF_ERRORS = (TypeError, ValueError, ValidationError)
_SERIOUS_EXECUTION_PROFILES = frozenset({"research", "governed", "production"})


def _build_default_store() -> ArtifactStore:
    """Build the default workflow artifact store via the backend factory seam."""
    return cast(
        "ArtifactStore",
        build_artifact_store(
            ArtifactStoreConfig(
                backend="filesystem",
                root=str(DEFAULT_CAS_ROOT),
            )
        ),
    )


def _resolve_store(
    store: ArtifactStore | None,
    *,
    store_factory: Callable[[], ArtifactStore] | None = None,
) -> ArtifactStore:
    resolved_store = store
    if resolved_store is None:
        resolved_store = store_factory() if store_factory is not None else _build_default_store()
    return _maybe_namespace_store(resolved_store)


def _build_quota_registry() -> QuotaRegistry | None:
    """Construct a tenant quota registry only when quota enforcement is requested."""
    try:
        from polisyos.core.security import TenantQuotaRegistry
    except _WORKFLOW_BUILDER_IMPORT_ERRORS:  # pragma: no cover - optional dependency
        return None
    return cast("QuotaRegistry", TenantQuotaRegistry())


def _maybe_enforce_quota(*, quota_registry: QuotaRegistry | None = None) -> QuotaEnforcer | None:
    """Check and record quota for the current tenant if active.

    Returns the QuotaEnforcer (for calling record_run_end in finally),
    or None if no tenant context.
    """
    tenant_id = get_current_tenant_id_or_none()
    if tenant_id is None:
        return None
    registry = quota_registry if quota_registry is not None else _build_quota_registry()
    if registry is None:
        return None
    enforcer = registry.get_enforcer(tenant_id)
    enforcer.check_run_start()
    enforcer.record_run_start()
    return enforcer


def _maybe_namespace_store(store: ArtifactStore) -> ArtifactStore:
    """Wrap store with namespace isolation if tenant context is active."""
    tenant_id = get_current_tenant_id_or_none()
    if tenant_id is None:
        return store
    if _is_content_addressed_filesystem_store(store):
        return store
    try:
        from polisyos.core.security import NamespacedArtifactStore

        cell_id = get_current_cell_id()
        return cast(
            "ArtifactStore",
            NamespacedArtifactStore(inner=store, tenant_id=tenant_id, cell_id=cell_id),
        )
    except (*_WORKFLOW_BUILDER_IMPORT_ERRORS, *_WORKFLOW_BUILDER_NAMESPACE_ERRORS):
        return store


def _is_content_addressed_filesystem_store(store: ArtifactStore) -> bool:
    """Return true when namespace prefixes would corrupt content-addressed CAS IDs."""
    try:
        from polisyos.core.artifacts.store import FileSystemCAS
    except _WORKFLOW_BUILDER_IMPORT_ERRORS:  # pragma: no cover - optional dependency guard
        return False
    target = getattr(store, "_target", store)
    return isinstance(target, FileSystemCAS)


def _maybe_create_provenance_dag(run_id: str) -> object | None:
    """Try to create a RunProvenanceDAG; return None if unavailable."""
    try:
        from polisyos.scientist.evidence.provenance.run_dag import RunProvenanceDAG

        tenant_id = get_current_tenant_id_or_none()
        return cast("object", RunProvenanceDAG(run_id=run_id, tenant_id=tenant_id))
    except (*_WORKFLOW_BUILDER_IMPORT_ERRORS, *_WORKFLOW_BUILDER_PROVENANCE_ERRORS):
        return None


def _artifact_ref_or_none(value: object) -> ArtifactRef | None:
    if isinstance(value, ArtifactRef):
        return value
    if isinstance(value, dict):
        try:
            return ArtifactRef.model_validate(value)
        except _WORKFLOW_BUILDER_ARTIFACT_REF_ERRORS:
            return None
    return None


def _prepare_workflow_state(initial_state: ExperimentState, *, workflow_id: str) -> ExperimentState:
    state = snapshot_state(initial_state)
    if not state.run_id:
        state = state.model_copy(update={"run_id": new_run_id()})
    state.params["workflow_id"] = workflow_id
    if "research_dag_enabled" in state.params and RESEARCH_DAG_FEATURE_FLAG not in state.params:
        state.params[RESEARCH_DAG_FEATURE_FLAG] = state.params["research_dag_enabled"]
    return state


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


def _default_engine_metrics() -> EngineMetricsCollector | None:
    """Create the default Scientist metrics collector."""
    from polisyos.scientist.orchestration.engine.metrics import build_engine_metrics

    return cast("EngineMetricsCollector", build_engine_metrics())


def build_execution_context(
    store: ArtifactStore,
    registry_bundle_ref: ArtifactRef,
    *,
    run_id: str,
    logger: logging.Logger | None = None,
    tracer: Tracer | None = None,
    foundry: FoundryPort | None = None,
    fabric: FabricPort | None = None,
    scholar: ScholarPort | None = None,
    lex: LexPort | None = None,
    metrics: EngineMetricsCollector | None = None,
    engine_metrics_factory: Callable[[], EngineMetricsCollector | None] | None = None,
    audit: AuditLog | None = None,
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
    access_scope = get_current_access_scope_or_none()
    tenant_id = get_current_tenant_id_or_none()
    cell_id = get_current_cell_id()
    if access_scope is not None:
        tenant_id = tenant_id or access_scope.tenant_id
        cell_id = cell_id or access_scope.cell_id

    run = RunContext.start(
        store,
        registry_bundle_ref,
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        access_scope=access_scope,
    )
    resolved_metrics: EngineMetricsCollector | None = metrics
    if resolved_metrics is None and engine_metrics_factory is not None:
        resolved_metrics = engine_metrics_factory()

    return ExecutionContext(
        store=store,
        run=run,
        logger=cast(
            "logging.Logger",
            logger or get_logger("polisyos.scientist.orchestration.engine"),
        ),
        tracer=tracer,
        depth=depth,
        metrics=resolved_metrics if resolved_metrics is not None else _default_engine_metrics(),
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

    if include_discovered_nodes:
        discover_nodes(registry, include_dev_scan=True)
    else:
        discover_nodes(
            registry,
            include_entry_points=False,
            include_builtin_nodes=True,
            include_dev_scan=False,
        )

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


def _is_serious_execution_profile(value: object) -> bool:
    return str(value or "").strip().lower() in _SERIOUS_EXECUTION_PROFILES


def _existing_foundry_method_report_ref(state: ExperimentState) -> str | None:
    for source in (state.params, state.reports_index):
        value = source.get("foundry_method_report_ref")
        if isinstance(value, str) and value.strip():
            return value.strip()
        ref = _artifact_ref_or_none(value)
        if ref is not None:
            return str(ref.artifact_id)
    value = state.reports_index.get("foundry_method_report")
    ref = _artifact_ref_or_none(value)
    if ref is not None:
        return str(ref.artifact_id)
    return None


def _existing_foundry_method_obligation_report_ref(state: ExperimentState) -> str | None:
    for key in (
        "foundry_method_obligation_report_ref",
        "foundry_method_obligation_report",
    ):
        for source in (state.params, state.reports_index):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            ref = _artifact_ref_or_none(value)
            if ref is not None:
                return str(ref.artifact_id)
    return None


def _attach_foundry_method_obligation_report_if_required(
    state: ExperimentState,
    *,
    store: ArtifactStore,
) -> None:
    """Persist the pre-claim method-obligation report for serious executions."""
    if not _is_serious_execution_profile(state.execution_profile):
        return
    if _existing_foundry_method_obligation_report_ref(state):
        return

    from polisyos.foundry.validation.method_quality import (
        OBLIGATION_REPORT_REF_KEY,
        expected_method_expectations_from_state,
        persist_foundry_method_obligation_report_for_state,
    )

    expected_method_expectations = expected_method_expectations_from_state(state)
    if not expected_method_expectations:
        return

    report_ref, report = persist_foundry_method_obligation_report_for_state(
        store,
        state,
        expected_method_expectations=expected_method_expectations,
        canary_kind=str(state.execution_profile or "production"),
    )
    state.reports_index[OBLIGATION_REPORT_REF_KEY] = report_ref
    state.reports_index["foundry_method_obligation_report"] = report_ref
    state.params[OBLIGATION_REPORT_REF_KEY] = str(report_ref.artifact_id)
    state.params["foundry_method_obligation_report_status"] = str(report.get("status") or "")
    state.params["foundry_method_obligation_report_blocking_issue_count"] = int(
        report.get("blocking_issue_count") or 0
    )
    state.params["foundry_method_obligation_expected_method_expectations"] = list(
        report.get("expected_method_expectations") or []
    )
    state.params["foundry_method_obligations_requested_before_claims"] = True


def _attach_foundry_method_report_if_required(
    result: WorkflowExecutionResult,
    *,
    store: ArtifactStore,
) -> WorkflowExecutionResult:
    """Persist one Foundry method-quality report for serious workflow executions."""
    state = result.state
    if not _is_serious_execution_profile(state.execution_profile):
        return result
    if _existing_foundry_method_report_ref(state):
        return result

    from polisyos.foundry.validation.method_quality import (
        REPORT_REF_KEY,
        persist_foundry_method_report_for_state,
    )

    report_ref, report = persist_foundry_method_report_for_state(
        store,
        state,
        canary_kind=str(state.execution_profile or "production"),
    )
    state.reports_index[REPORT_REF_KEY] = report_ref
    state.reports_index["foundry_method_report"] = report_ref
    state.params[REPORT_REF_KEY] = str(report_ref.artifact_id)
    state.params["foundry_method_report_status"] = str(report.get("status") or "")
    state.params["foundry_method_report_blocking_issue_count"] = int(
        report.get("blocking_issue_count") or 0
    )
    return result


def resolve_workflow_id(initial_state: ExperimentState) -> str:
    """Select the workflow id implied by state params, execution profile, and inputs.

    Args:
        initial_state: Caller-provided state envelope before orchestration begins.

    Returns:
        One of the builtin workflow ids accepted by `run_selected_workflow()`.
    """
    return cast("str", _resolve_workflow_id(initial_state))


def run_selected_workflow(
    initial_state: ExperimentState,
    *,
    store: ArtifactStore | None = None,
    store_factory: Callable[[], ArtifactStore] | None = None,
    registry_bundle_ref: ArtifactRef | None = None,
    checkpoint_policy: CheckpointPolicy = "strict",
    force_lock: bool = False,
    foundry: FoundryPort | None = None,
    fabric: FabricPort | None = None,
    scholar: ScholarPort | None = None,
    lex: LexPort | None = None,
    logger: logging.Logger | None = None,
    tracer: Tracer | None = None,
    metrics: EngineMetricsCollector | None = None,
    quota_registry: QuotaRegistry | None = None,
    engine_metrics_factory: Callable[[], EngineMetricsCollector | None] | None = None,
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
            store_factory=store_factory,
            registry_bundle_ref=registry_bundle_ref,
            checkpoint_policy=checkpoint_policy,
            force_lock=force_lock,
            foundry=foundry,
            fabric=fabric,
            scholar=scholar,
            lex=lex,
            logger=logger,
            tracer=tracer,
            metrics=metrics,
            engine_metrics_factory=engine_metrics_factory,
        )
    if workflow_id == "scientist_discovery":
        return run_discovery_workflow(
            initial_state,
            store=store,
            store_factory=store_factory,
            registry_bundle_ref=registry_bundle_ref,
            checkpoint_policy=checkpoint_policy,
            force_lock=force_lock,
            foundry=foundry,
            fabric=fabric,
            scholar=scholar,
            lex=lex,
            logger=logger,
            tracer=tracer,
            metrics=metrics,
            engine_metrics_factory=engine_metrics_factory,
        )
    if workflow_id == "scientist_policy_verified":
        return run_policy_verified_workflow(
            initial_state,
            store=store,
            store_factory=store_factory,
            registry_bundle_ref=registry_bundle_ref,
            checkpoint_policy=checkpoint_policy,
            force_lock=force_lock,
            foundry=foundry,
            fabric=fabric,
            scholar=scholar,
            lex=lex,
            logger=logger,
            tracer=tracer,
            metrics=metrics,
            engine_metrics_factory=engine_metrics_factory,
        )
    if workflow_id == "scientist_causal_full":
        return run_causal_full_workflow(
            initial_state,
            store=store,
            store_factory=store_factory,
            registry_bundle_ref=registry_bundle_ref,
            checkpoint_policy=checkpoint_policy,
            force_lock=force_lock,
            foundry=foundry,
            fabric=fabric,
            scholar=scholar,
            lex=lex,
            logger=logger,
            tracer=tracer,
            metrics=metrics,
            engine_metrics_factory=engine_metrics_factory,
        )
    return run_default_workflow(
        initial_state,
        store=store,
        store_factory=store_factory,
        registry_bundle_ref=registry_bundle_ref,
        checkpoint_policy=checkpoint_policy,
        force_lock=force_lock,
        foundry=foundry,
        fabric=fabric,
        scholar=scholar,
        lex=lex,
        logger=logger,
        tracer=tracer,
        metrics=metrics,
        quota_registry=quota_registry,
        engine_metrics_factory=engine_metrics_factory,
    )


def run_policy_design_workflow(
    initial_state: ExperimentState,
    *,
    store: ArtifactStore | None = None,
    store_factory: Callable[[], ArtifactStore] | None = None,
    registry_bundle_ref: ArtifactRef | None = None,
    graph_prior_bundle_ref: ArtifactRef | None = None,
    checkpoint_policy: CheckpointPolicy = "strict",
    force_lock: bool = False,
    foundry: FoundryPort | None = None,
    fabric: FabricPort | None = None,
    scholar: ScholarPort | None = None,
    lex: LexPort | None = None,
    logger: logging.Logger | None = None,
    tracer: Tracer | None = None,
    metrics: EngineMetricsCollector | None = None,
    engine_metrics_factory: Callable[[], EngineMetricsCollector | None] | None = None,
) -> WorkflowExecutionResult:
    """Execute the `scientist_policy_design` DAG with search and translation stages."""
    store = _resolve_store(store, store_factory=store_factory)
    policy = normalize_checkpoint_policy(checkpoint_policy)

    state = _prepare_workflow_state(
        initial_state,
        workflow_id="scientist_policy_design",
    )
    state.params.setdefault("policy_mode", True)
    state.execution_profile = state.execution_profile or "policy_design"

    if registry_bundle_ref is None:
        registry_bundle_ref = state.inputs.get(INPUT_REGISTRY_BUNDLE_REF)
    if registry_bundle_ref is None:
        registry_bundle_ref = build_default_registry(store)
    registry_bundle_ref = (
        _pin_cross_layer_input_ref(
            state,
            input_key=INPUT_REGISTRY_BUNDLE_REF,
            provided_ref=registry_bundle_ref,
        )
        or registry_bundle_ref
    )
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
    _attach_foundry_method_obligation_report_if_required(state, store=store)

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
            metrics=metrics,
            engine_metrics_factory=engine_metrics_factory,
        )
        _propagate_runtime_run_metadata(ctx, state)

        registry = build_registry_with_builtin_nodes()
        checkpoint_hook = CASCheckpointHook(
            store=store,
            run_dir=run_dir,
            sequence_start=0,
            checkpoint_policy=policy,
            tenant_id=ctx.run.tenant_id,
            cell_id=ctx.run.cell_id,
        )
        executor = WorkflowExecutor(ctx, registry, checkpoint_hook=checkpoint_hook)
        workflow = policy_design_workflow_spec()
        result = executor.execute(workflow, state)
        return _attach_foundry_method_report_if_required(result, store=store)
    finally:
        lock.release()


def run_discovery_workflow(
    initial_state: ExperimentState,
    *,
    store: ArtifactStore | None = None,
    store_factory: Callable[[], ArtifactStore] | None = None,
    registry_bundle_ref: ArtifactRef | None = None,
    checkpoint_policy: CheckpointPolicy = "strict",
    force_lock: bool = False,
    foundry: FoundryPort | None = None,
    fabric: FabricPort | None = None,
    scholar: ScholarPort | None = None,
    lex: LexPort | None = None,
    logger: logging.Logger | None = None,
    tracer: Tracer | None = None,
    metrics: EngineMetricsCollector | None = None,
    engine_metrics_factory: Callable[[], EngineMetricsCollector | None] | None = None,
) -> WorkflowExecutionResult:
    """Execute the discovery-only DAG and persist prior-knowledge artifacts."""
    store = _resolve_store(store, store_factory=store_factory)
    policy = normalize_checkpoint_policy(checkpoint_policy)

    state = _prepare_workflow_state(
        initial_state,
        workflow_id="scientist_discovery",
    )
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
            metrics=metrics,
            engine_metrics_factory=engine_metrics_factory,
        )
        _propagate_runtime_run_metadata(ctx, state)

        registry = build_registry_with_builtin_nodes()
        checkpoint_hook = CASCheckpointHook(
            store=store,
            run_dir=run_dir,
            sequence_start=0,
            checkpoint_policy=policy,
            tenant_id=ctx.run.tenant_id,
            cell_id=ctx.run.cell_id,
        )
        executor = WorkflowExecutor(ctx, registry, checkpoint_hook=checkpoint_hook)
        workflow = discovery_workflow_spec()
        result = executor.execute(workflow, state)
        return _attach_foundry_method_report_if_required(result, store=store)
    finally:
        lock.release()


def run_default_workflow(
    initial_state: ExperimentState,
    *,
    store: ArtifactStore | None = None,
    store_factory: Callable[[], ArtifactStore] | None = None,
    registry_bundle_ref: ArtifactRef | None = None,
    checkpoint_policy: CheckpointPolicy = "strict",
    force_lock: bool = False,
    foundry: FoundryPort | None = None,
    fabric: FabricPort | None = None,
    scholar: ScholarPort | None = None,
    lex: LexPort | None = None,
    logger: logging.Logger | None = None,
    tracer: Tracer | None = None,
    metrics: EngineMetricsCollector | None = None,
    quota_registry: QuotaRegistry | None = None,
    engine_metrics_factory: Callable[[], EngineMetricsCollector | None] | None = None,
) -> WorkflowExecutionResult:
    """Execute the baseline simulation/governance DAG."""
    store = _resolve_store(store, store_factory=store_factory)
    policy = normalize_checkpoint_policy(checkpoint_policy)

    state = _prepare_workflow_state(
        initial_state,
        workflow_id="scientist_default",
    )

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
    _attach_foundry_method_obligation_report_if_required(state, store=store)

    if foundry is None:
        foundry = DefaultFoundryPort()
    if fabric is None and INPUT_DATA_VIEW_REQUEST_REF in state.inputs:
        fabric = DefaultFabricPort()

    enforcer = _maybe_enforce_quota(quota_registry=quota_registry)
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
            metrics=metrics,
            engine_metrics_factory=engine_metrics_factory,
        )
        _propagate_runtime_run_metadata(ctx, state)

        registry = build_registry_with_builtin_nodes()
        checkpoint_hook = CASCheckpointHook(
            store=store,
            run_dir=run_dir,
            sequence_start=0,
            checkpoint_policy=policy,
            tenant_id=ctx.run.tenant_id,
            cell_id=ctx.run.cell_id,
        )
        _maybe_create_provenance_dag(state.run_id)

        runner_config = WorkflowRunnerConfig.from_env()
        workflow = default_workflow_spec()
        if runner_config.backend != "local":
            import asyncio

            runner = build_workflow_runner(runner_config)
            result = asyncio.run(
                runner.execute_workflow(
                    workflow,
                    state,
                    ctx,
                    registry,
                    checkpoint_hook=checkpoint_hook,
                    max_parallelism=runner_config.max_parallelism,
                )
            )
            return _attach_foundry_method_report_if_required(result, store=store)

        executor = WorkflowExecutor(ctx, registry, checkpoint_hook=checkpoint_hook)
        result = executor.execute(workflow, state)
        return _attach_foundry_method_report_if_required(result, store=store)
    finally:
        lock.release()
        if enforcer is not None:
            enforcer.record_run_end()


def run_policy_verified_workflow(
    initial_state: ExperimentState,
    *,
    store: ArtifactStore | None = None,
    store_factory: Callable[[], ArtifactStore] | None = None,
    registry_bundle_ref: ArtifactRef | None = None,
    checkpoint_policy: CheckpointPolicy = "strict",
    force_lock: bool = False,
    foundry: FoundryPort | None = None,
    fabric: FabricPort | None = None,
    scholar: ScholarPort | None = None,
    lex: LexPort | None = None,
    logger: logging.Logger | None = None,
    tracer: Tracer | None = None,
    metrics: EngineMetricsCollector | None = None,
    engine_metrics_factory: Callable[[], EngineMetricsCollector | None] | None = None,
) -> WorkflowExecutionResult:
    """Execute the verified-policy DAG that omits hierarchical champion search."""
    store = _resolve_store(store, store_factory=store_factory)
    policy = normalize_checkpoint_policy(checkpoint_policy)

    state = _prepare_workflow_state(
        initial_state,
        workflow_id="scientist_policy_verified",
    )
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
    _attach_foundry_method_obligation_report_if_required(state, store=store)

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
            metrics=metrics,
            engine_metrics_factory=engine_metrics_factory,
        )
        _propagate_runtime_run_metadata(ctx, state)

        registry = build_registry_with_builtin_nodes()
        checkpoint_hook = CASCheckpointHook(
            store=store,
            run_dir=run_dir,
            sequence_start=0,
            checkpoint_policy=policy,
            tenant_id=ctx.run.tenant_id,
            cell_id=ctx.run.cell_id,
        )
        executor = WorkflowExecutor(ctx, registry, checkpoint_hook=checkpoint_hook)
        workflow = policy_verified_workflow_spec()
        result = executor.execute(workflow, state)
        return _attach_foundry_method_report_if_required(result, store=store)
    finally:
        lock.release()


def run_causal_full_workflow(
    initial_state: ExperimentState,
    *,
    store: ArtifactStore | None = None,
    store_factory: Callable[[], ArtifactStore] | None = None,
    registry_bundle_ref: ArtifactRef | None = None,
    checkpoint_policy: CheckpointPolicy = "strict",
    force_lock: bool = False,
    foundry: FoundryPort | None = None,
    fabric: FabricPort | None = None,
    scholar: ScholarPort | None = None,
    lex: LexPort | None = None,
    logger: logging.Logger | None = None,
    tracer: Tracer | None = None,
    metrics: EngineMetricsCollector | None = None,
    engine_metrics_factory: Callable[[], EngineMetricsCollector | None] | None = None,
) -> WorkflowExecutionResult:
    """Execute the full causal DAG with graph reconciliation and transport checks."""
    store = _resolve_store(store, store_factory=store_factory)
    policy = normalize_checkpoint_policy(checkpoint_policy)

    state = _prepare_workflow_state(
        initial_state,
        workflow_id="scientist_causal_full",
    )
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
    _attach_foundry_method_obligation_report_if_required(state, store=store)

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
            metrics=metrics,
            engine_metrics_factory=engine_metrics_factory,
        )
        _propagate_runtime_run_metadata(ctx, state)

        registry = build_registry_with_builtin_nodes()
        checkpoint_hook = CASCheckpointHook(
            store=store,
            run_dir=run_dir,
            sequence_start=0,
            checkpoint_policy=policy,
            tenant_id=ctx.run.tenant_id,
            cell_id=ctx.run.cell_id,
        )
        executor = WorkflowExecutor(ctx, registry, checkpoint_hook=checkpoint_hook)
        workflow = causal_full_workflow_spec()
        result = executor.execute(workflow, state)
        return _attach_foundry_method_report_if_required(result, store=store)
    finally:
        lock.release()


__all__ = [
    "build_default_registry",
    "build_execution_context",
    "build_registry_with_builtin_nodes",
    "resolve_workflow_id",
    "run_causal_full_workflow",
    "run_default_workflow",
    "run_policy_design_workflow",
    "run_policy_verified_workflow",
    "run_selected_workflow",
]
