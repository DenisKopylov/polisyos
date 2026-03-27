"""Semantic conventions for OpenTelemetry span attributes.

Centralises attribute keys for the scientist engine so that
``telemetry.py``, ``async_executor.py``, and distributed runners
all use the same vocabulary.  Follows the OTel naming convention:
``<domain>.<subsystem>.<attribute>``.
"""

from __future__ import annotations

# --- Node-level attributes ---
ATTR_NODE_ID = "polisyos.scientist.node_id"
ATTR_NODE_ALIAS = "polisyos.scientist.node_alias"
ATTR_TIER_INDEX = "polisyos.scientist.tier_index"
ATTR_RETRY_COUNT = "polisyos.scientist.retry_count"
ATTR_CACHE_HIT = "polisyos.scientist.cache_hit"

# --- Workflow-level attributes ---
ATTR_WORKFLOW_ID = "polisyos.scientist.workflow_id"
ATTR_RUN_ID = "polisyos.scientist.run_id"
ATTR_ERROR_POLICY = "polisyos.scientist.error_policy"

# --- Tenant attributes ---
ATTR_TENANT_ID = "polisyos.tenant_id"
ATTR_CELL_ID = "polisyos.cell_id"

# --- Runner attributes ---
ATTR_RUNNER_BACKEND = "polisyos.scientist.runner_backend"

# --- Status attributes ---
ATTR_NODE_STATUS = "polisyos.scientist.node_status"
ATTR_DURATION_MS = "polisyos.scientist.duration_ms"


def build_node_span_attributes(
    *,
    alias: str,
    node_id: str,
    workflow_id: str,
    tier_index: int = 0,
    run_id: str = "",
    tenant_id: str | None = None,
    cell_id: str | None = None,
) -> dict[str, str | int | bool]:
    """Build a dict of OTel attributes for a node execution span.

    Parameters
    ----------
    alias:
        Node alias within the workflow.
    node_id:
        Fully qualified node component ID.
    workflow_id:
        Workflow identifier.
    tier_index:
        Topological tier index (0-based).
    run_id:
        Experiment run identifier.
    tenant_id:
        Optional tenant identifier (multi-tenancy).
    cell_id:
        Optional cell/workspace identifier.

    Returns
    -------
    dict
        Attribute dict suitable for ``tracer.start_as_current_span(attributes=...)``.
    """
    attrs: dict[str, str | int | bool] = {
        ATTR_NODE_ALIAS: alias,
        ATTR_NODE_ID: node_id,
        ATTR_WORKFLOW_ID: workflow_id,
        ATTR_TIER_INDEX: tier_index,
        ATTR_RUN_ID: run_id,
    }
    if tenant_id is not None:
        attrs[ATTR_TENANT_ID] = tenant_id
    if cell_id is not None:
        attrs[ATTR_CELL_ID] = cell_id
    return attrs


def enrich_node_span_result(
    attrs: dict[str, str | int | bool],
    *,
    status: str,
    duration_ms: int,
    cache_hit: bool = False,
    retry_count: int = 0,
) -> dict[str, str | int | bool]:
    """Add post-execution attributes to a node span.

    Mutates and returns *attrs* for convenience.
    """
    attrs[ATTR_NODE_STATUS] = status
    attrs[ATTR_DURATION_MS] = duration_ms
    attrs[ATTR_CACHE_HIT] = cache_hit
    attrs[ATTR_RETRY_COUNT] = retry_count
    return attrs
