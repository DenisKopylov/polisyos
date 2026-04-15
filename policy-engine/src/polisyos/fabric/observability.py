"""Fabric telemetry contract, health snapshots, and backend-agnostic alert hooks."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_metrics

logger = get_logger(__name__)

__all__ = [
    "FABRIC_TRACE_NAMES",
    "FABRIC_METRIC_NAMES",
    "FABRIC_LABEL_CARDINALITY_LIMITS",
    "FABRIC_ERROR_TAXONOMY",
    "AlertSeverity",
    "FabricAlert",
    "AlertSink",
    "NoOpAlertSink",
    "HealthComponentSnapshot",
    "FabricHealthSnapshot",
    "build_fabric_health_snapshot",
]


FABRIC_TRACE_NAMES = {
    "connector_fetch": "fabric.connector.fetch",
    "retry": "fabric.connector.retry",
    "circuit_transition": "fabric.connector.circuit.transition",
    "rate_limit_acquire": "fabric.connector.rate_limit.acquire",
    "cache_get": "fabric.cache.get",
    "cache_put": "fabric.cache.put",
    "cache_invalidate": "fabric.cache.invalidate",
    "cache_evict": "fabric.cache.evict",
    "transform_stage": "fabric.transform.stage",
    "federation_compose": "fabric.federation.compose",
    "retrieval_resolve": "fabric.retrieval.resolve",
    "retrieval_discover": "fabric.retrieval.discover",
    "retrieval_execute": "fabric.retrieval.execute",
    "data_plane_ingest": "fabric.data_plane.ingest",
    "segment_append": "fabric.world.segment.append",
    "materialize": "fabric.world.materialize",
    "query": "fabric.query.execute",
}

FABRIC_METRIC_NAMES = {
    "connector_fetch_latency": "polisyos_fabric_connector_fetch_duration_seconds",
    "connector_rows": "polisyos_fabric_connector_rows_total",
    "connector_bytes": "polisyos_fabric_connector_bytes_total",
    "query_latency": "polisyos_fabric_query_duration_seconds",
    "query_rows": "polisyos_fabric_query_rows_total",
    "materialization_lag": "polisyos_fabric_materialization_lag_seconds",
    "segment_count": "polisyos_fabric_segment_count",
    "quality_score": "polisyos_fabric_quality_score",
    "freshness_age": "polisyos_fabric_freshness_age_seconds",
    "lineage_nodes": "polisyos_fabric_lineage_graph_nodes",
    "lineage_edges": "polisyos_fabric_lineage_graph_edges",
    "prefetch_backlog": "polisyos_fabric_prefetch_backlog",
    "dlq_count": "polisyos_fabric_dlq_entries",
}

FABRIC_LABEL_CARDINALITY_LIMITS = {
    "connector_id": 256,
    "namespace": 64,
    "strategy": 32,
    "operation": 64,
    "status": 32,
    "component": 32,
    "severity": 8,
}

FABRIC_ERROR_TAXONOMY = {
    "validation_error": "Fabric input or contract validation failed.",
    "timeout": "Upstream call or materialization timed out.",
    "rate_limited": "Source signaled throttling or Retry-After.",
    "external_unavailable": "Connector dependency returned transient 5xx/transport failure.",
    "stale_data": "Only stale cache/source data is available.",
    "lineage_incomplete": "Lineage graph is missing required upstream/downstream edges.",
    "uncertain_state": "Mutable on-disk/runtime state could not be trusted after read error.",
    "internal_error": "Unexpected Fabric runtime exception.",
}


class AlertSeverity(str, Enum):
    """Fabric alert severity contract."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class FabricAlert:
    """Backend-neutral alert record."""

    component: str
    severity: AlertSeverity
    code: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)


class AlertSink(Protocol):
    """Hook for alert fan-out without coupling to a concrete backend."""

    def emit(self, alert: FabricAlert) -> None:
        ...


class NoOpAlertSink:
    """Default alert sink used when no backend is configured."""

    def emit(self, alert: FabricAlert) -> None:
        logger.debug(
            "Fabric alert emitted",
            component=alert.component,
            severity=alert.severity.value,
            code=alert.code,
            message=alert.message,
        )


@dataclass(frozen=True)
class HealthComponentSnapshot:
    """Health summary for one Fabric subsystem."""

    name: str
    healthy: bool
    reasons: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FabricHealthSnapshot:
    """Aggregated health snapshot across Fabric runtime subsystems."""

    healthy: bool
    components: tuple[HealthComponentSnapshot, ...]
    reasons: tuple[str, ...]


def build_fabric_health_snapshot(
    *,
    registry: Any | None = None,
    cache_store: Any | None = None,
    fact_log_root: Path | None = None,
    cursor_store: Any | None = None,
    retrieval_service: Any | None = None,
    alert_sink: AlertSink | None = None,
) -> FabricHealthSnapshot:
    """Aggregate connector/cache/world/data-plane/retrieval health into one snapshot."""
    sink = alert_sink or NoOpAlertSink()
    components: list[HealthComponentSnapshot] = []

    connector_component = _connector_health_component(registry)
    cache_component = _cache_health_component(cache_store)
    world_component = _world_health_component(fact_log_root)
    data_plane_component = _data_plane_health_component(cursor_store)
    retrieval_component = _retrieval_health_component(retrieval_service)

    for component in (
        connector_component,
        cache_component,
        world_component,
        data_plane_component,
        retrieval_component,
    ):
        if component is not None:
            components.append(component)
            if not component.healthy:
                sink.emit(
                    FabricAlert(
                        component=component.name,
                        severity=AlertSeverity.WARNING,
                        code="health_degraded",
                        message="Fabric component reported degraded health",
                        context={
                            "reasons": list(component.reasons),
                            **component.details,
                        },
                    )
                )

    reasons = tuple(
        reason
        for component in components
        if not component.healthy
        for reason in component.reasons
    )
    snapshot = FabricHealthSnapshot(
        healthy=all(component.healthy for component in components) if components else True,
        components=tuple(components),
        reasons=reasons,
    )
    _record_health_metrics(snapshot)
    return snapshot


def _connector_health_component(registry: Any | None) -> HealthComponentSnapshot | None:
    if registry is None:
        return None
    entries = list(getattr(getattr(registry, "_connectors", None), "values", lambda: [])())
    details = {
        "registered_connectors": len(entries),
        "healthy_connectors": 0,
        "degraded_connectors": 0,
    }
    reasons: list[str] = []
    for entry in entries:
        health = getattr(entry, "health_status", None)
        if health is None:
            continue
        if getattr(health, "healthy", False):
            details["healthy_connectors"] += 1
        else:
            details["degraded_connectors"] += 1
            message = str(getattr(health, "message", "") or "connector unhealthy")
            reasons.append(f"{entry.fqid}: {message}")
    return HealthComponentSnapshot(
        name="connectors",
        healthy=details["degraded_connectors"] == 0,
        reasons=tuple(reasons),
        details=details,
    )


def _cache_health_component(cache_store: Any | None) -> HealthComponentSnapshot | None:
    if cache_store is None:
        return None
    reasons: list[str] = []
    details: dict[str, Any] = {"closed": bool(getattr(cache_store, "closed", False))}
    if details["closed"]:
        reasons.append("cache store is closed")
    try:
        stats = cache_store.stats()
    except Exception as exc:
        reasons.append(f"cache stats unavailable: {exc}")
    else:
        details.update(
            {
                "total_entries": getattr(stats, "total_entries", 0),
                "total_size_bytes": getattr(stats, "total_size_bytes", 0),
                "hit_rate": getattr(stats, "hit_rate", 0.0),
                "eviction_count": getattr(stats, "eviction_count", 0),
            }
        )
    return HealthComponentSnapshot(
        name="cache",
        healthy=not reasons,
        reasons=tuple(reasons),
        details=details,
    )


def _world_health_component(fact_log_root: Path | None) -> HealthComponentSnapshot | None:
    if fact_log_root is None:
        return None
    from polisyos.fabric.world.store.segments import load_world_fact_manifests

    reasons: list[str] = []
    details: dict[str, Any] = {"fact_log_root": str(fact_log_root)}
    try:
        manifests = load_world_fact_manifests(fact_log_root)
    except Exception as exc:
        reasons.append(f"world segment index unavailable: {exc}")
        manifests = []
    details["segment_count"] = len(manifests)
    return HealthComponentSnapshot(
        name="world",
        healthy=not reasons,
        reasons=tuple(reasons),
        details=details,
    )


def _data_plane_health_component(cursor_store: Any | None) -> HealthComponentSnapshot | None:
    if cursor_store is None:
        return None
    reasons: list[str] = []
    details: dict[str, Any] = {}
    try:
        cursors = cursor_store.list_cursors()
    except Exception as exc:
        reasons.append(f"cursor store unavailable: {exc}")
        cursors = []
    details["cursor_count"] = len(cursors)
    return HealthComponentSnapshot(
        name="data_plane",
        healthy=not reasons,
        reasons=tuple(reasons),
        details=details,
    )


def _retrieval_health_component(retrieval_service: Any | None) -> HealthComponentSnapshot | None:
    if retrieval_service is None:
        return None
    reasons: list[str] = []
    details: dict[str, Any] = {}
    try:
        stats = retrieval_service.get_index_stats()
    except Exception as exc:
        reasons.append(f"retrieval index unavailable: {exc}")
    else:
        details.update(
            {
                "index_docs_total": getattr(stats, "index_docs_total", 0),
                "index_size_bytes": getattr(stats, "index_size_bytes", 0),
                "indexed_sources": getattr(stats, "indexed_sources", 0),
            }
        )
    return HealthComponentSnapshot(
        name="retrieval",
        healthy=not reasons,
        reasons=tuple(reasons),
        details=details,
    )


def _record_health_metrics(snapshot: FabricHealthSnapshot) -> None:
    metrics = get_metrics()
    if metrics is None:
        return
    if getattr(metrics, "set_fabric_segment_count", None):
        for component in snapshot.components:
            if component.name == "world":
                metrics.set_fabric_segment_count(
                    float(component.details.get("segment_count", 0))
                )  # type: ignore[misc]
            if component.name == "retrieval" and getattr(metrics, "set_fabric_dlq_count", None):
                metrics.set_fabric_dlq_count(0.0)  # type: ignore[misc]
