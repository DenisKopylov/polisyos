"""Shared node execution logic for remote workers (Temporal & Ray).

Both ``temporal_runner.py`` and ``ray_runner.py`` delegate to this module
so that the node execution path is identical regardless of the dispatch
mechanism.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.runner.serialization import (
    _timeout_access_scope_from_wire,
    deserialize_outcome,
    deserialize_state,
    serialize_outcome,
    serialize_state,
    serialize_worker_execution_receipt,
    worker_dispatch_sha256,
)
from polisyos.scientist.orchestration.engine.runner.worker_pool import NodeTask

_logger = logging.getLogger(__name__)
_TRACE_IMPORT_ERRORS = (ImportError, ModuleNotFoundError, AttributeError)
_TRACE_RUNTIME_ERRORS = (RuntimeError, TypeError, ValueError)
_REGISTRY_REF_ERRORS = (ValidationError, TypeError, ValueError)
_METRICS_INIT_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_TIMEOUT_CONTEXT_WIRE_SCHEMA = "polisyos.scientist.timeout_context.v2"


class _StagedWorkerTraceSink:
    """Collect worker events in memory for parent admission after execution."""

    def __init__(self) -> None:
        self.records: list[Any] = []

    def emit(self, rec: Any) -> None:
        from polisyos.core.trace import TraceRecord

        if type(rec) is not TraceRecord:
            raise TypeError("timeout worker trace records must be typed")
        self.records.append(rec.model_copy(deep=True))

    def emit_many(self, records: Sequence[Any]) -> None:
        """Stage a typed batch in order without touching the parent writer."""
        staged = list(records)
        from polisyos.core.trace import TraceRecord

        if any(type(record) is not TraceRecord for record in staged):
            raise TypeError("timeout worker trace records must be typed")
        self.records.extend(record.model_copy(deep=True) for record in staged)

    def close(self) -> None:
        raise ValueError("timeout_worker_run_lifecycle_not_owned")


async def run_node_in_worker(
    payload: dict[str, Any],
    *,
    timeout_authority: tuple[Any, float] | None = None,
    parent_receipt: bool = False,
) -> bytes:
    """Execute one node and return its typed, serialised outcome.

    This is the async entry point used by Temporal activities.

    Parameters
    ----------
    payload:
        Dict with keys: node_id, alias, params, state_bytes,
        trace_carrier, timeout_s, max_retries, context_meta.

    Returns
    -------
    bytes
        Serialised ``NodeOutcome`` including native status and state.
    """
    node_id: str = payload["node_id"]
    alias: str = payload["alias"]
    params: dict[str, Any] = payload.get("params", {})
    state_bytes: bytes = payload["state_bytes"]
    trace_carrier: dict[str, str] = payload.get("trace_carrier", {})
    timeout_s: float | None = payload.get("timeout_s")
    context_meta: dict[str, Any] = payload.get("context_meta", {})
    receipt_invocation_id: str | None = None
    receipt_dispatch_sha256: str | None = None
    receipt_owner_snapshot_ref: Any = None
    staged_trace: _StagedWorkerTraceSink | None = None
    receipt_requested = timeout_authority is not None or parent_receipt
    if timeout_authority is not None and parent_receipt:
        raise ValueError("worker_receipt_mode_conflict")
    if receipt_requested:
        receipt_invocation_id = payload.get("worker_invocation_id")
        receipt_dispatch_sha256 = payload.get("worker_dispatch_sha256")
        if (
            not isinstance(receipt_invocation_id, str)
            or len(receipt_invocation_id) != 64
            or not isinstance(receipt_dispatch_sha256, str)
            or len(receipt_dispatch_sha256) != 64
        ):
            raise ValueError("timeout_worker_receipt_binding_required")
        expected_dispatch = worker_dispatch_sha256(
            node_id=node_id,
            alias=alias,
            params=params,
            state_bytes=state_bytes,
            trace_carrier=trace_carrier,
            timeout_s=timeout_s,
            max_retries=payload.get("max_retries", 0),
            context_meta=context_meta,
        )
        if expected_dispatch != receipt_dispatch_sha256:
            raise ValueError("timeout_worker_dispatch_digest_mismatch")

    tenant_scope_manager = None
    if parent_receipt:
        tenant_scope_meta = context_meta.get("tenant_scope")
        if (
            not isinstance(tenant_scope_meta, dict)
            or set(tenant_scope_meta) != {"tenant_id", "cell_id"}
            or not isinstance(tenant_scope_meta.get("tenant_id"), str)
            or not tenant_scope_meta["tenant_id"].strip()
            or (
                tenant_scope_meta.get("cell_id") is not None
                and not isinstance(tenant_scope_meta.get("cell_id"), str)
            )
        ):
            raise ValueError("worker_receipt_tenant_scope_invalid")
        from polisyos.core.security import tenant_scope

        tenant_scope_manager = tenant_scope(
            None,
            tenant_id=tenant_scope_meta["tenant_id"],
            cell_id=tenant_scope_meta["cell_id"],
        )
        tenant_scope_manager.__enter__()

    # Reconstruct state
    state = deserialize_state(state_bytes)

    # Restore parent trace context from carrier
    access_scope_token = None
    _token = _restore_parent_trace_context(
        trace_carrier,
        context_meta=context_meta,
        operation="restore_trace_context",
    )

    try:
        # Parent-receipt workers use the strict source-bound context wire and
        # stage all run events. Legacy distributed workers retain their
        # reconstruction contract until their caller adopts this receipt API.
        if not receipt_requested:
            ctx = _build_worker_context(context_meta)
        else:
            ctx = _build_timeout_worker_context(
                context_meta,
                invocation_id=receipt_invocation_id,
                dispatch_sha256=receipt_dispatch_sha256,
            )
            staged_trace = ctx.run.trace
            worker_binding = ctx.run.dispatch_binding
            receipt_owner_snapshot_ref = (
                None if worker_binding is None else worker_binding.owner_snapshot_ref
            )
            if not isinstance(staged_trace, _StagedWorkerTraceSink):
                raise ValueError("timeout_worker_staged_trace_required")
            if receipt_owner_snapshot_ref is None:
                raise ValueError("timeout_worker_owner_snapshot_required")
            from polisyos.core.security import set_current_access_scope

            access_scope_token = set_current_access_scope(ctx.run.access_scope)
            if ctx.run.run_manifest.run_id != state.run_id:
                raise ValueError("timeout_worker_run_id_mismatch")
            if timeout_authority is not None:
                from polisyos.scientist.orchestration.engine.retry import (
                    _AttemptAuthority,
                    _build_attempt_context,
                )

                authority = _AttemptAuthority(
                    timeout_authority[1],
                    shared_active=timeout_authority[0],
                )
                ctx = _build_attempt_context(ctx, authority)

        from polisyos.scientist.orchestration.engine.skg_snapshot import (
            SNAPSHOT_INPUT_KEY,
            bind_retained_skg_workflow_input,
        )

        if SNAPSHOT_INPUT_KEY in state.inputs:
            from polisyos.common import async_tools as common_async_tools

            state = await common_async_tools.run_blocking_async(
                bind_retained_skg_workflow_input,
                ctx,
                state,
                record_run_input=False,
                unbounded=True,
            )

        # Resolve and execute the node
        from polisyos.scientist.orchestration.engine.registry import (
            NodeRegistry,
            discover_nodes,
        )

        registry = NodeRegistry()
        if not receipt_requested:
            discover_nodes(registry)
        else:
            discover_nodes(
                registry,
                include_entry_points=False,
                include_builtin_nodes=True,
                include_dev_scan=False,
            )

        node = registry.get(node_id)

        # Apply params binding
        from polisyos.scientist.orchestration.engine.executor import bind_node_params

        node = bind_node_params(node, params)

        # Remote inputs cross the state wire without branch-local metadata.
        # Establish the same declared-write journal used by local executors
        # before the node can mutate its working state.
        from polisyos.scientist.orchestration.engine.state_branching import (
            _completed_producer_state,
            _completed_producer_value,
            branch_state,
        )

        state = branch_state(
            state,
            write_paths=getattr(node.spec, "state_writes", ()),
            enforce_write_scope=True,
        ).state

        # Execute with retry/timeout under a child span
        from polisyos.scientist.orchestration.engine.retry import (
            RetryPolicy,
            execute_with_retry_async,
        )

        retry_policy = RetryPolicy(max_retries=payload.get("max_retries", 0))

        # Create child span for this node execution
        tracer, span_attrs = _build_worker_tracer(
            alias=alias,
            node_id=node_id,
            context_meta=context_meta,
        )

        try:
            if tracer is not None:
                with tracer.start_as_current_span(
                    f"scientist.node.{alias}",
                    attributes=span_attrs,
                ):
                    outcome = await execute_with_retry_async(
                        node,
                        ctx,
                        state,
                        retry_policy=retry_policy,
                        timeout_s=timeout_s,
                        alias=alias,
                        dispatch_params=params,
                    )
            else:
                outcome = await execute_with_retry_async(
                    node,
                    ctx,
                    state,
                    retry_policy=retry_policy,
                    timeout_s=timeout_s,
                    alias=alias,
                    dispatch_params=params,
                )
        except Exception as exc:
            if not receipt_requested:
                raise
            from polisyos.scientist.orchestration.engine.retry import _worker_error_payload

            if (
                receipt_invocation_id is None
                or receipt_dispatch_sha256 is None
                or receipt_owner_snapshot_ref is None
                or staged_trace is None
            ):
                raise ValueError("timeout_worker_receipt_binding_required") from exc
            return serialize_worker_execution_receipt(
                error_payload=_worker_error_payload(exc),
                invocation_id=receipt_invocation_id,
                dispatch_sha256=receipt_dispatch_sha256,
                owner_snapshot_ref=receipt_owner_snapshot_ref,
                records=staged_trace.records,
            )

        completed = outcome.model_copy(
            update={
                "state": _completed_producer_state(outcome.state),
                "artifacts": _completed_producer_value(outcome.artifacts),
            }
        )
        outcome_bytes = cast("bytes", serialize_outcome(completed))
        if receipt_requested:
            if (
                receipt_invocation_id is None
                or receipt_dispatch_sha256 is None
                or receipt_owner_snapshot_ref is None
                or staged_trace is None
            ):
                raise ValueError("timeout_worker_receipt_binding_required")
            return serialize_worker_execution_receipt(
                outcome_bytes=outcome_bytes,
                invocation_id=receipt_invocation_id,
                dispatch_sha256=receipt_dispatch_sha256,
                owner_snapshot_ref=receipt_owner_snapshot_ref,
                records=staged_trace.records,
            )
        return outcome_bytes
    finally:
        try:
            if access_scope_token is not None:
                from polisyos.core.security import reset_current_access_scope

                reset_current_access_scope(access_scope_token)
            if _token is not None:
                _detach_parent_trace_context(
                    _token,
                    context_meta=context_meta,
                    operation="detach_trace_context",
                )
        finally:
            if tenant_scope_manager is not None:
                tenant_scope_manager.__exit__(None, None, None)


def run_node_in_worker_sync(payload: dict[str, Any], *, parent_receipt: bool = False) -> bytes:
    """Synchronous wrapper for Ray remote tasks."""
    return asyncio.run(run_node_in_worker(payload, parent_receipt=parent_receipt))


def run_node_task_in_timeout_worker_sync(
    task: NodeTask,
    *,
    authority_active: Any,
    deadline_monotonic: float,
) -> bytes:
    """Run one typed ``NodeTask`` with a strict reconstructed local context.

    This is the spawn-safe timeout entry point. It deliberately disables a
    nested timeout and requires the task's context metadata to identify the
    exact store and existing run trace.
    """
    from polisyos.core.security import tenant_scope

    tenant_scope_meta = task.context_meta.get("tenant_scope")
    if not isinstance(tenant_scope_meta, dict):
        raise ValueError("timeout_worker_tenant_scope_required")
    tenant_id = tenant_scope_meta.get("tenant_id")
    cell_id = tenant_scope_meta.get("cell_id")
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("timeout_worker_tenant_id_required")
    payload = {
        "node_id": task.node_id,
        "alias": task.alias,
        "params": task.params,
        "state_bytes": task.state_bytes,
        "trace_carrier": task.trace_carrier,
        "timeout_s": None,
        "max_retries": 0,
        "context_meta": task.context_meta,
        "worker_invocation_id": task.worker_invocation_id,
        "worker_dispatch_sha256": task.worker_dispatch_sha256,
    }
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        worker_dispatch_sha256,
    )

    actual_dispatch = worker_dispatch_sha256(
        node_id=task.node_id,
        alias=task.alias,
        params=task.params,
        state_bytes=task.state_bytes,
        trace_carrier=task.trace_carrier,
        timeout_s=None,
        max_retries=0,
        context_meta=task.context_meta,
    )
    if (
        not isinstance(task.worker_invocation_id, str)
        or len(task.worker_invocation_id) != 64
        or task.worker_dispatch_sha256 != actual_dispatch
    ):
        raise ValueError("timeout_worker_dispatch_digest_mismatch")
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        return asyncio.run(
            run_node_in_worker(
                payload,
                timeout_authority=(authority_active, deadline_monotonic),
            )
        )


async def run_node_state_in_worker(payload: dict[str, Any]) -> bytes:
    """Return the historical state-only activity result for old Temporal histories."""
    outcome_bytes = await run_node_in_worker(payload)
    outcome = deserialize_outcome(outcome_bytes)
    return serialize_state(outcome.state)


def run_node_state_in_worker_sync(payload: dict[str, Any]) -> bytes:
    """Synchronous wrapper for the history-compatible Temporal result."""
    return asyncio.run(run_node_state_in_worker(payload))


async def run_merge_checkpoint_tier_in_worker(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Merge one distributed tier and checkpoint when runtime metadata provides a hook."""
    context_meta: dict[str, Any] = payload.get("context_meta", {})
    trace_carrier: dict[str, str] = payload.get("trace_carrier", {})

    _token = _restore_parent_trace_context(
        trace_carrier,
        context_meta=context_meta,
        operation="restore_merge_trace_context",
    )

    try:
        from polisyos.scientist.orchestration.engine.checkpoint import (
            restore_checkpoint_hook_from_runtime_metadata,
        )

        checkpoint_meta = payload.get("checkpoint_hook_meta")
        checkpoint_hook = restore_checkpoint_hook_from_runtime_metadata(checkpoint_meta)

        from polisyos.scientist.orchestration.engine.registry import (
            NodeRegistry,
            discover_nodes,
        )
        from polisyos.scientist.orchestration.engine.runner.distributed_tier import (
            merge_and_checkpoint_tier,
            seed_runner_cache,
        )
        from polisyos.scientist.orchestration.engine.state_merge import (
            MergeConflictPolicy,
        )
        from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec

        workflow = WorkflowSpec.model_validate(payload["workflow_spec_json"])
        invocations = {inv.alias: inv for inv in workflow.nodes}
        result_format = payload.get("result_format", "state")
        if result_format not in {"node_outcome", "state"}:
            raise ValueError("distributed_result_format_unsupported")

        registry = NodeRegistry()
        discover_nodes(registry)

        cache = None
        if checkpoint_meta is not None:
            store = _build_worker_context(context_meta, store_only=True)
            seed_refs = []
            if isinstance(checkpoint_meta, dict):
                from polisyos.core.artifacts.manifest import ArtifactRef

                for raw_ref in checkpoint_meta.get("cache_entry_refs") or []:
                    if not isinstance(raw_ref, dict):
                        continue
                    try:
                        seed_refs.append(ArtifactRef.model_validate(raw_ref))
                    except _REGISTRY_REF_ERRORS as exc:
                        emit_degraded_path(
                            component="engine.runner.activity_worker",
                            operation="parse_checkpoint_cache_seed_ref",
                            reason="checkpoint_cache_seed_ref_invalid",
                            exc=exc,
                            details={
                                "run_id": str(context_meta.get("run_id") or "worker-run"),
                                "raw_ref": raw_ref,
                            },
                            log=_logger,
                        )
                        continue
            cache = seed_runner_cache(
                store=store,
                run_id=str(context_meta.get("run_id") or "worker-run"),
                checkpoint_cache_seed_refs=seed_refs,
                logger=_logger,
            )

        tier_result = merge_and_checkpoint_tier(
            workflow=workflow,
            tier_aliases=list(payload["tier_aliases"]),
            invocations=invocations,
            result_bytes_by_alias=dict(payload["result_bytes_by_alias"]),
            base_state_bytes=payload["base_state_bytes"],
            registry=registry,
            checkpoint_hook=checkpoint_hook,
            cache=cache,
            completed_nodes=list(payload.get("completed_nodes") or []),
            workflow_fingerprint=str(payload["workflow_fingerprint"]),
            conflict_policy=MergeConflictPolicy(payload["merge_conflict_policy"]),
            logger=_logger,
            result_format=result_format,
        )
        updated_checkpoint_meta = (
            checkpoint_hook.export_runtime_metadata() if checkpoint_hook is not None else None
        )
        return {
            "state_bytes": tier_result.state_bytes,
            "completed_nodes": tier_result.completed_nodes,
            "should_abort": tier_result.should_abort,
            "checkpoint_hook_meta": updated_checkpoint_meta,
        }
    finally:
        if _token is not None:
            _detach_parent_trace_context(
                _token,
                context_meta=context_meta,
                operation="detach_merge_trace_context",
            )


def run_merge_checkpoint_tier_in_worker_sync(payload: dict[str, Any]) -> dict[str, Any]:
    """Synchronous wrapper for distributed tier merge/checkpoint workers."""
    return asyncio.run(run_merge_checkpoint_tier_in_worker(payload))


def _build_worker_context(meta: dict[str, Any], *, store_only: bool = False) -> Any:
    """Build a minimal ``ExecutionContext`` for a remote worker.

    The worker creates its own artifact store, logger, and run context
    from the metadata shipped in the payload. Store-only consumers stop before
    claiming a RunContext lifecycle or appending a new RUN_STARTED event.
    """
    from polisyos.scientist.orchestration.engine.checkpoint import (
        CheckpointScopeMismatchError,
        _reconcile_checkpoint_scope,
    )

    owner_tenant_id = meta.get("tenant_id")
    owner_cell_id = meta.get("cell_id")
    if owner_tenant_id is not None and (
        not isinstance(owner_tenant_id, str) or not owner_tenant_id.strip()
    ):
        raise CheckpointScopeMismatchError("distributed worker tenant scope invalid")
    if owner_cell_id is not None and (
        not isinstance(owner_cell_id, str) or not owner_cell_id.strip()
    ):
        raise CheckpointScopeMismatchError("distributed worker cell scope invalid")
    if owner_cell_id is not None and owner_tenant_id is None:
        raise CheckpointScopeMismatchError("distributed worker cell requires tenant scope")
    tenant_id, cell_id = _reconcile_checkpoint_scope(
        owner_tenant_id,
        owner_cell_id,
        capture_active_when_unset=False,
        operation="distributed worker",
    )

    import logging as _logging
    from pathlib import Path

    from polisyos.core.artifacts.backends.config import (
        ArtifactStoreConfig,
        build_artifact_store,
    )
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.evidence.claims import build_default_claim_ledger_owner
    from polisyos.scientist.orchestration.engine.context import (
        ClaimCapableExecutionContext,
    )

    run_id = str(meta.get("run_id", "worker-run"))
    store_config_raw = meta.get("store_config")
    store_config_supplied = "store_config" in meta
    store_config: ArtifactStoreConfig | None = None
    if store_config_supplied:
        if not isinstance(store_config_raw, dict):
            raise CheckpointScopeMismatchError("distributed worker store config invalid")
        for owner_key, run_owner in (("tenant_id", tenant_id), ("cell_id", cell_id)):
            if owner_key in store_config_raw:
                if store_config_raw[owner_key] != run_owner:
                    raise CheckpointScopeMismatchError("distributed worker store owner mismatch")
                raise CheckpointScopeMismatchError(
                    "distributed worker owner must be carried by run metadata"
                )
        try:
            store_config = ArtifactStoreConfig.model_validate(store_config_raw)
        except (TypeError, ValueError, ValidationError) as exc:
            raise CheckpointScopeMismatchError("distributed worker store config invalid") from exc

    if store_config is not None and store_config_supplied:
        store_backend = meta.get("store_backend")
        if store_backend is not None and store_backend != store_config.backend:
            raise CheckpointScopeMismatchError("distributed worker store backend metadata mismatch")
        store_root = meta.get("store_root")
        if store_root is not None:
            if (
                not isinstance(store_root, str)
                or not store_root.strip()
                or store_config.backend != "filesystem"
            ):
                raise CheckpointScopeMismatchError(
                    "distributed worker store root metadata mismatch"
                )
            configured_root = (
                Path(store_config.root) if store_config.root else Path.cwd() / ".polisyos" / "cas"
            )
            if configured_root.resolve(strict=False) != Path(store_root).resolve(strict=False):
                raise CheckpointScopeMismatchError(
                    "distributed worker store root metadata mismatch"
                )

    if store_config is None:
        store_backend = meta.get("store_backend")
        store_root = meta.get("store_root")
        if store_backend == "filesystem" and isinstance(store_root, str) and store_root.strip():
            store_config = ArtifactStoreConfig(backend="filesystem", root=store_root)
        elif tenant_id is not None:
            raise CheckpointScopeMismatchError(
                "distributed worker owner scope requires a configured shared store"
            )
        else:
            import tempfile

            cas_dir = Path(tempfile.mkdtemp(prefix="polisyos_worker_"))
            store_config = ArtifactStoreConfig(backend="filesystem", root=str(cas_dir))

    if tenant_id is not None and store_config.backend != "filesystem":
        raise CheckpointScopeMismatchError(
            "distributed worker store backend cannot enforce tenant ownership"
        )
    store = build_artifact_store(store_config, tenant_id=tenant_id, cell_id=cell_id)
    if store_only:
        return store
    metrics = None
    try:
        from polisyos.scientist.orchestration.engine.metrics import build_engine_metrics

        metrics = build_engine_metrics()
    except _TRACE_IMPORT_ERRORS:
        metrics = None
    except _METRICS_INIT_ERRORS as exc:
        emit_degraded_path(
            component="engine.runner.activity_worker",
            operation="init_metrics",
            reason="worker_metrics_init_failed",
            exc=exc,
            details={"run_id": run_id},
            log=_logger,
        )
        metrics = None

    raw_registry_bundle = meta.get("registry_bundle_ref")
    registry_bundle_ref: ArtifactRef | None = None
    if isinstance(raw_registry_bundle, dict):
        try:
            registry_bundle_ref = ArtifactRef.model_validate(raw_registry_bundle)
        except _REGISTRY_REF_ERRORS as exc:
            emit_degraded_path(
                component="engine.runner.activity_worker",
                operation="parse_registry_bundle_ref",
                reason="registry_bundle_ref_invalid",
                exc=exc,
                details={"run_id": run_id, "raw_ref": raw_registry_bundle},
                log=_logger,
            )
            registry_bundle_ref = None
    if registry_bundle_ref is None:
        registry_bundle_ref = store.put_json(
            {"registry": "worker-bootstrap"},
            ArtifactWriteOptions(
                kind="core.registry_bundle",
                media_type="application/json",
            ),
        )
    run_ctx = RunContext.start(
        store=store,
        registry_bundle=registry_bundle_ref,
        run_id=run_id,
        tenant_id=meta.get("tenant_id"),
        cell_id=meta.get("cell_id"),
    )

    ctx = ClaimCapableExecutionContext(
        store=store,
        run=run_ctx,
        logger=_logging.getLogger(f"polisyos.worker.{run_id}"),
        metrics=metrics,
        depth=meta.get("depth", 0),
        claim_ledger_owner=build_default_claim_ledger_owner(store=store),
    )
    if metrics is not None:
        try:
            metrics.record_trace_correlation(
                runner_backend=str(meta.get("runner_backend") or "worker"),
                workflow_id=str(meta.get("workflow_id") or "unknown"),
                run_id=str(run_id),
                trace_id=meta.get("trace_id"),
                span_id=meta.get("span_id"),
            )
        except _METRICS_INIT_ERRORS as exc:
            emit_degraded_path(
                component="engine.runner.activity_worker",
                operation="record_trace_correlation",
                reason="worker_trace_correlation_failed",
                exc=exc,
                details={"run_id": run_id},
                log=_logger,
            )
    return ctx


def _build_timeout_worker_context(
    meta: dict[str, Any],
    *,
    invocation_id: str | None = None,
    dispatch_sha256: str | None = None,
) -> Any:
    """Reconstruct only the exact filesystem/run context admitted for timeout work."""
    from polisyos.core import run as core_run
    from polisyos.core.artifacts import FileSystemCAS, SigningConfig
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.observability import is_hpc_observability_enabled
    from polisyos.core.run.worker_lifecycle import WorkerLifecycleCapability
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

    if set(meta) != {
        "schema",
        "depth",
        "logger_name",
        "run_id",
        "workflow_id",
        "store",
        "run",
        "tenant_scope",
    }:
        raise ValueError("timeout_worker_context_fields_invalid")
    if meta.get("schema") != _TIMEOUT_CONTEXT_WIRE_SCHEMA:
        raise ValueError("timeout_worker_context_schema_unsupported")
    depth = meta.get("depth")
    logger_name = meta.get("logger_name")
    store_meta = meta.get("store")
    run_meta = meta.get("run")
    tenant_scope_meta = meta.get("tenant_scope")
    if type(depth) is not int or depth < 0 or not isinstance(logger_name, str):
        raise ValueError("timeout_worker_context_identity_invalid")
    if not isinstance(store_meta, dict) or set(store_meta) != {
        "backend",
        "root",
        "tenant_id",
        "cell_id",
        "ownership_enforced",
        "ownership_requires_scope",
        "signing_config",
        "hpc_observability_enabled",
    }:
        raise ValueError("timeout_worker_store_context_invalid")
    if not isinstance(run_meta, dict) or set(run_meta) != {
        "manifest",
        "trace_path",
        "tenant_id",
        "cell_id",
        "owner_snapshot_ref",
        "access_scope",
    }:
        raise ValueError("timeout_worker_run_context_invalid")
    access_scope = _timeout_access_scope_from_wire(run_meta["access_scope"])
    owner_ref_payload = run_meta["owner_snapshot_ref"]
    owner_ref_fields = {
        "artifact_id",
        "kind",
        "media_type",
        "manifest_profile_sha256",
    }
    if type(owner_ref_payload) is not dict or set(owner_ref_payload) != owner_ref_fields:
        raise ValueError("timeout_worker_owner_snapshot_ref_invalid")
    try:
        owner_snapshot_ref = ArtifactRef.model_validate(owner_ref_payload)
    except (TypeError, ValueError, ValidationError) as exc:
        raise ValueError("timeout_worker_owner_snapshot_ref_invalid") from exc
    if (
        owner_snapshot_ref.kind != "core.run_owner_snapshot"
        or owner_snapshot_ref.media_type != "application/json"
        or owner_snapshot_ref.manifest_profile_sha256 is None
        or owner_snapshot_ref.model_dump(mode="json", by_alias=True, exclude_none=False)
        != owner_ref_payload
    ):
        raise ValueError("timeout_worker_owner_snapshot_ref_invalid")
    if not isinstance(tenant_scope_meta, dict) or set(tenant_scope_meta) != {
        "tenant_id",
        "cell_id",
    }:
        raise ValueError("timeout_worker_tenant_scope_invalid")
    if store_meta.get("backend") != "filesystem":
        raise ValueError("timeout_worker_filesystem_cas_required")
    root_raw = store_meta.get("root")
    trace_raw = run_meta.get("trace_path")
    if not isinstance(root_raw, str) or not isinstance(trace_raw, str):
        raise ValueError("timeout_worker_store_paths_required")
    root = Path(root_raw)
    trace_path = Path(trace_raw)
    if not root.is_absolute() or not trace_path.is_absolute():
        raise ValueError("timeout_worker_absolute_paths_required")
    root = root.resolve(strict=True)
    trace_path = trace_path.resolve(strict=False)
    try:
        trace_path.relative_to(root)
    except ValueError as exc:
        raise ValueError("timeout_worker_trace_path_outside_store") from exc

    tenant_id = store_meta.get("tenant_id")
    cell_id = store_meta.get("cell_id")
    if (tenant_id, cell_id) != (run_meta.get("tenant_id"), run_meta.get("cell_id")):
        raise ValueError("timeout_worker_store_run_owner_mismatch")
    if access_scope is not None and (access_scope.tenant_id, access_scope.cell_id) != (
        tenant_id,
        cell_id,
    ):
        raise ValueError("timeout_worker_access_scope_owner_mismatch")
    ambient_tenant = tenant_scope_meta.get("tenant_id")
    ambient_cell = tenant_scope_meta.get("cell_id")
    if not isinstance(ambient_tenant, str) or not ambient_tenant.strip():
        raise ValueError("timeout_worker_ambient_tenant_required")
    for owner_tenant, owner_cell in (
        (tenant_id, cell_id),
        (run_meta.get("tenant_id"), run_meta.get("cell_id")),
    ):
        if owner_tenant is not None and (
            ambient_tenant != owner_tenant
            or (owner_cell is not None and ambient_cell != owner_cell)
        ):
            raise ValueError("timeout_worker_ambient_owner_mismatch")
    ownership_enforced = store_meta.get("ownership_enforced")
    ownership_requires_scope = store_meta.get("ownership_requires_scope")
    hpc_observability_enabled = store_meta.get("hpc_observability_enabled")
    if (
        type(ownership_enforced) is not bool
        or type(ownership_requires_scope) is not bool
        or type(hpc_observability_enabled) is not bool
    ):
        raise ValueError("timeout_worker_store_ownership_invalid")
    if is_hpc_observability_enabled() != hpc_observability_enabled:
        raise ValueError("timeout_worker_observability_setting_mismatch")
    try:
        signing_config = SigningConfig.model_validate(store_meta.get("signing_config"))
        run_manifest = core_run.RunManifest.model_validate(run_meta.get("manifest"))
    except (TypeError, ValueError, ValidationError) as exc:
        raise ValueError("timeout_worker_context_model_invalid") from exc
    if run_manifest.tenant_id != run_meta.get("tenant_id") or run_manifest.cell_id != run_meta.get(
        "cell_id"
    ):
        raise ValueError("timeout_worker_manifest_owner_mismatch")
    if access_scope is not None and (access_scope.tenant_id, access_scope.cell_id) != (
        run_manifest.tenant_id,
        run_manifest.cell_id,
    ):
        raise ValueError("timeout_worker_access_scope_owner_mismatch")
    if not isinstance(meta.get("run_id"), str) or meta["run_id"] != run_manifest.run_id:
        raise ValueError("timeout_worker_run_id_required")
    if not isinstance(meta.get("workflow_id"), str):
        raise ValueError("timeout_worker_workflow_id_invalid")

    store = FileSystemCAS(
        root,
        signing_config=signing_config,
        tenant_id=tenant_id,
        cell_id=cell_id,
        ownership_enforced=ownership_enforced,
        ownership_requires_scope=ownership_requires_scope,
    )
    if store._hpc_enabled != hpc_observability_enabled:
        raise ValueError("timeout_worker_observability_setting_mismatch")
    staged_trace = _StagedWorkerTraceSink()
    lifecycle = WorkerLifecycleCapability.for_worker_context(
        store=store,
        trace=staged_trace,
        run_manifest=run_manifest,
        trace_path=trace_path,
        owner_snapshot_ref=owner_snapshot_ref,
        invocation_id=invocation_id,
        dispatch_sha256=dispatch_sha256,
        tenant_id=tenant_id,
        cell_id=cell_id,
        access_scope=access_scope,
    )
    return ExecutionContext(
        store=store,
        run=lifecycle.worker_view(),
        logger=logging.getLogger(logger_name),
        depth=depth,
    )


def _restore_parent_trace_context(
    trace_carrier: dict[str, str],
    *,
    context_meta: dict[str, Any],
    operation: str,
) -> object | None:
    if not trace_carrier:
        return None
    try:
        from opentelemetry import context as otel_context

        from polisyos.core.observability import extract_headers

        parent_ctx = extract_headers(trace_carrier)
        return cast("object", otel_context.attach(parent_ctx))
    except _TRACE_IMPORT_ERRORS:
        return None
    except _TRACE_RUNTIME_ERRORS as exc:
        emit_degraded_path(
            component="engine.runner.activity_worker",
            operation=operation,
            reason="trace_context_restore_failed",
            exc=exc,
            details={"run_id": str(context_meta.get("run_id") or "worker-run")},
            log=_logger,
        )
        return None


def _detach_parent_trace_context(
    token: object,
    *,
    context_meta: dict[str, Any],
    operation: str,
) -> None:
    try:
        from opentelemetry import context as otel_context

        otel_context.detach(cast("Any", token))
    except _TRACE_IMPORT_ERRORS:
        return
    except _TRACE_RUNTIME_ERRORS as exc:
        emit_degraded_path(
            component="engine.runner.activity_worker",
            operation=operation,
            reason="trace_context_detach_failed",
            exc=exc,
            details={"run_id": str(context_meta.get("run_id") or "worker-run")},
            log=_logger,
        )


def _build_worker_tracer(
    *,
    alias: str,
    node_id: str,
    context_meta: dict[str, Any],
) -> tuple[Any | None, dict[str, Any]]:
    try:
        from opentelemetry import trace as otel_trace

        from polisyos.scientist.orchestration.engine.trace_attributes import (
            build_node_span_attributes,
        )

        tracer = otel_trace.get_tracer("polisyos.scientist.worker")
        span_attrs = build_node_span_attributes(
            alias=alias,
            node_id=node_id,
            workflow_id=context_meta.get("workflow_id", ""),
            run_id=context_meta.get("run_id", ""),
        )
        return tracer, span_attrs
    except _TRACE_IMPORT_ERRORS:
        return None, {}
    except _TRACE_RUNTIME_ERRORS as exc:
        emit_degraded_path(
            component="engine.runner.activity_worker",
            operation="build_child_tracer",
            reason="trace_span_init_failed",
            exc=exc,
            details={
                "run_id": str(context_meta.get("run_id") or "worker-run"),
                "alias": alias,
                "node_id": node_id,
            },
            log=_logger,
        )
        return None, {}
