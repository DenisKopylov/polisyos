"""Shared node execution logic for remote workers (Temporal & Ray).

Both ``temporal_runner.py`` and ``ray_runner.py`` delegate to this module
so that the node execution path is identical regardless of the dispatch
mechanism.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from polisyos.scientist.engine.runner.serialization import (
    deserialize_state,
    serialize_state,
)

_logger = logging.getLogger(__name__)


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
    _token = None
    try:
        if trace_carrier:
            from opentelemetry import context as otel_context
            from polisyos.core.observability.propagation import extract_headers
            parent_ctx = extract_headers(trace_carrier)
            _token = otel_context.attach(parent_ctx)
    except Exception:  # noqa: BLE001
        pass

    try:
        # Build a minimal execution context for this worker
        ctx = _build_worker_context(context_meta)

        # Resolve and execute the node
        from polisyos.scientist.engine.registry import NodeRegistry, discover_nodes

        registry = NodeRegistry()
        discover_nodes(registry)

        node = registry.get(node_id)

        # Apply params binding
        from polisyos.scientist.engine.executor import _bind_node_params

        node = _bind_node_params(node, params)

        # Execute with retry/timeout under a child span
        from polisyos.scientist.engine.retry import RetryPolicy, execute_with_retry_async

        retry_policy = RetryPolicy(max_retries=payload.get("max_retries", 0))

        # Create child span for this node execution
        try:
            from opentelemetry import trace as otel_trace
            from polisyos.scientist.engine.trace_attributes import build_node_span_attributes
            tracer = otel_trace.get_tracer("polisyos.scientist.worker")
            span_attrs = build_node_span_attributes(
                alias=alias, node_id=node_id,
                workflow_id=context_meta.get("workflow_id", ""),
                run_id=context_meta.get("run_id", ""),
            )
        except Exception:  # noqa: BLE001
            tracer = None
            span_attrs = {}

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
        return serialize_state(final_state)
    finally:
        if _token is not None:
            try:
                from opentelemetry import context as otel_context
                otel_context.detach(_token)
            except Exception:  # noqa: BLE001
                pass


def run_node_in_worker_sync(payload: dict[str, Any]) -> bytes:
    """Synchronous wrapper for Ray remote tasks."""
    return asyncio.get_event_loop().run_until_complete(run_node_in_worker(payload))


def _build_worker_context(meta: dict[str, Any]) -> Any:
    """Build a minimal ``ExecutionContext`` for a remote worker.

    The worker creates its own artifact store, logger, and run context
    from the metadata shipped in the payload.
    """
    import logging as _logging

    from polisyos.core.artifacts.local_cas import FileSystemCAS
    from polisyos.scientist.engine.context import ExecutionContext

    # Use a temp CAS for now — in production, workers would connect
    # to the shared CAS backend (S3/GCS) configured via env vars.
    import tempfile
    from pathlib import Path

    from polisyos.core.run.context import RunContext

    cas_dir = Path(tempfile.mkdtemp(prefix="polisyos_worker_"))
    store = FileSystemCAS(cas_dir)

    run_id = meta.get("run_id", "worker-run")
    run_ctx = RunContext.start(
        component="scientist.worker",
        run_id=run_id,
        store=store,
        tenant_id=meta.get("tenant_id"),
        cell_id=meta.get("cell_id"),
    )

    return ExecutionContext(
        store=store,
        run=run_ctx,
        logger=_logging.getLogger(f"polisyos.worker.{run_id}"),
        depth=meta.get("depth", 0),
    )
