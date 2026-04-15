"""Shared node execution logic for remote workers (Temporal & Ray).

Both ``temporal_runner.py`` and ``ray_runner.py`` delegate to this module
so that the node execution path is identical regardless of the dispatch
mechanism.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

from pydantic import ValidationError

from polisyos.scientist.engine.runner.serialization import (
    deserialize_state,
    serialize_state,
)
from polisyos.scientist.error_semantics import emit_degraded_path

_logger = logging.getLogger(__name__)
_TRACE_IMPORT_ERRORS = (ImportError, ModuleNotFoundError, AttributeError)
_TRACE_RUNTIME_ERRORS = (RuntimeError, TypeError, ValueError)
_REGISTRY_REF_ERRORS = (ValidationError, TypeError, ValueError)
_METRICS_INIT_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


async def run_node_in_worker(payload: dict[str, Any]) -> bytes:
    """Execute a single node and return serialised final state bytes.

    This is the async entry point used by Temporal activities.

    Parameters
    ----------
    payload:
        Dict with keys: node_id, alias, params, state_bytes,
        trace_carrier, timeout_s, max_retries, context_meta.

    Returns
    -------
    bytes
        Serialised ``ExperimentState`` after node execution.
    """
    node_id: str = payload["node_id"]
    alias: str = payload["alias"]
    params: dict[str, Any] = payload.get("params", {})
    state_bytes: bytes = payload["state_bytes"]
    trace_carrier: dict[str, str] = payload.get("trace_carrier", {})
    timeout_s: float | None = payload.get("timeout_s")
    context_meta: dict[str, Any] = payload.get("context_meta", {})

    # Reconstruct state
    state = deserialize_state(state_bytes)

    # Restore parent trace context from carrier
    _token = _restore_parent_trace_context(
        trace_carrier,
        context_meta=context_meta,
        operation="restore_trace_context",
    )

    try:
        # Build a minimal execution context for this worker
        ctx = _build_worker_context(context_meta)

        # Resolve and execute the node
        from polisyos.scientist.engine.registry import NodeRegistry, discover_nodes

        registry = NodeRegistry()
        discover_nodes(registry)

        node = registry.get(node_id)

        # Apply params binding
        from polisyos.scientist.engine.executor import bind_node_params

        node = bind_node_params(node, params)

        # Execute with retry/timeout under a child span
        from polisyos.scientist.engine.retry import RetryPolicy, execute_with_retry_async

        retry_policy = RetryPolicy(max_retries=payload.get("max_retries", 0))

        # Create child span for this node execution
        tracer, span_attrs = _build_worker_tracer(
            alias=alias,
            node_id=node_id,
            context_meta=context_meta,
        )

        if tracer is not None:
            with tracer.start_as_current_span(
                f"scientist.node.{alias}", attributes=span_attrs,
            ):
                outcome = await execute_with_retry_async(
                    node, ctx, state,
                    retry_policy=retry_policy,
                    timeout_s=timeout_s,
                    alias=alias,
                )
        else:
            outcome = await execute_with_retry_async(
                node, ctx, state,
                retry_policy=retry_policy,
                timeout_s=timeout_s,
                alias=alias,
            )

        # Return updated state
        final_state = outcome.state
        return cast("bytes", serialize_state(final_state))
    finally:
        if _token is not None:
            _detach_parent_trace_context(
                _token,
                context_meta=context_meta,
                operation="detach_trace_context",
            )


def run_node_in_worker_sync(payload: dict[str, Any]) -> bytes:
    """Synchronous wrapper for Ray remote tasks."""
    return asyncio.run(run_node_in_worker(payload))


async def run_merge_checkpoint_tier_in_worker(payload: dict[str, Any]) -> dict[str, Any]:
    """Merge one distributed tier and checkpoint it using serialized runtime metadata."""
    context_meta: dict[str, Any] = payload.get("context_meta", {})
    trace_carrier: dict[str, str] = payload.get("trace_carrier", {})

    _token = _restore_parent_trace_context(
        trace_carrier,
        context_meta=context_meta,
        operation="restore_merge_trace_context",
    )

    try:
        ctx = _build_worker_context(context_meta)

        from polisyos.scientist.engine.checkpoint import (
            restore_checkpoint_hook_from_runtime_metadata,
        )
        from polisyos.scientist.engine.registry import NodeRegistry, discover_nodes
        from polisyos.scientist.engine.runner.distributed_tier import (
            merge_and_checkpoint_tier,
            seed_runner_cache,
        )
        from polisyos.scientist.engine.state_merge import MergeConflictPolicy
        from polisyos.scientist.engine.workflow_spec import WorkflowSpec

        workflow = WorkflowSpec.model_validate(payload["workflow_spec_json"])
        invocations = {inv.alias: inv for inv in workflow.nodes}

        registry = NodeRegistry()
        discover_nodes(registry)

        checkpoint_meta = payload.get("checkpoint_hook_meta")
        checkpoint_hook = restore_checkpoint_hook_from_runtime_metadata(checkpoint_meta)
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
            store=ctx.store,
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
        )
        updated_checkpoint_meta = (
            checkpoint_hook.export_runtime_metadata()
            if checkpoint_hook is not None
            else None
        )
        return {
            "state_bytes": tier_result.state_bytes,
            "completed_nodes": tier_result.completed_nodes,
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


def _build_worker_context(meta: dict[str, Any]) -> Any:
    """Build a minimal ``ExecutionContext`` for a remote worker.

    The worker creates its own artifact store, logger, and run context
    from the metadata shipped in the payload.
    """
    import logging as _logging
    from pathlib import Path

    from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.engine.context import ExecutionContext

    run_id = str(meta.get("run_id", "worker-run"))
    store_config_raw = meta.get("store_config")
    store_config: ArtifactStoreConfig | None = None
    if isinstance(store_config_raw, dict):
        try:
            store_config = ArtifactStoreConfig.model_validate(store_config_raw)
        except (TypeError, ValueError, ValidationError) as exc:
            emit_degraded_path(
                component="engine.runner.activity_worker",
                operation="parse_store_config",
                reason="worker_store_config_invalid",
                exc=exc,
                details={"run_id": run_id},
                log=_logger,
            )

    if store_config is None:
        store_backend = meta.get("store_backend")
        store_root = meta.get("store_root")
        if store_backend == "filesystem" and isinstance(store_root, str) and store_root.strip():
            store_config = ArtifactStoreConfig(backend="filesystem", root=store_root)
        else:
            import tempfile

            cas_dir = Path(tempfile.mkdtemp(prefix="polisyos_worker_"))
            store_config = ArtifactStoreConfig(backend="filesystem", root=str(cas_dir))

    store = build_artifact_store(store_config)
    metrics = None
    try:
        from polisyos.scientist.engine.metrics import build_engine_metrics

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

    ctx = ExecutionContext(
        store=store,
        run=run_ctx,
        logger=_logging.getLogger(f"polisyos.worker.{run_id}"),
        metrics=metrics,
        depth=meta.get("depth", 0),
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

        from polisyos.core.observability.propagation import extract_headers

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

        from polisyos.scientist.engine.trace_attributes import build_node_span_attributes

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
