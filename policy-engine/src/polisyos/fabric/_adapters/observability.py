"""Fabric telemetry contract, health snapshots, and backend-agnostic alert hooks."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from math import isfinite
from pathlib import Path
from typing import Any, Protocol

from polisyos.common.logger import get_logger
from polisyos.core.observability import get_current_trace_context, get_metrics, get_tracer

logger = get_logger(__name__)


@dataclass(frozen=True)
class FabricObservabilityAdapter:
    """Package-local access point for Fabric telemetry callers."""

    component: str = "fabric"

    def metrics(self) -> Any:
        """Return the canonical process-wide metrics registry."""
        return _default_metrics()

    def trace_context(self) -> dict[str, str | None]:
        """Return the active canonical trace context for Fabric records."""
        return dict(get_current_trace_context())

    @contextmanager
    def span(
        self,
        operation: str,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[Any]:
        """Start a Fabric-namespaced span using the canonical tracer."""
        span_name = (
            operation
            if operation.startswith(f"{self.component}.")
            else f"{self.component}.{operation}"
        )
        span_attributes = {"polisyos.package": self.component, **dict(attributes or {})}
        with _default_tracer().start_as_current_span(
            span_name,
            attributes=span_attributes,
        ) as span:
            yield span


def get_fabric_observability_adapter() -> FabricObservabilityAdapter:
    """Return the default Fabric observability adapter."""
    return FabricObservabilityAdapter()

__all__ = [
    "DEFAULT_FABRIC_SLO_TARGETS",
    "FABRIC_ERROR_TAXONOMY",
    "FABRIC_LABEL_CARDINALITY_LIMITS",
    "FABRIC_METRIC_NAMES",
    "FABRIC_TRACE_NAMES",
    "AlertSeverity",
    "AlertSink",
    "FabricAlert",
    "FabricHealthSnapshot",
    "FabricReliabilityBudgetError",
    "FabricReliabilityReport",
    "FabricSLIName",
    "FabricSLIObservation",
    "FabricSLOAssessment",
    "FabricSLOTarget",
    "FabricObservabilityAdapter",
    "HealthComponentSnapshot",
    "NoOpAlertSink",
    "assert_fabric_feature_expansion_allowed",
    "build_fabric_health_snapshot",
    "evaluate_fabric_reliability_budget",
    "get_fabric_observability_adapter",
]


def _default_metrics():
    return get_metrics()


def _default_tracer():
    return get_tracer()


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
    "sli_value": "polisyos_fabric_sli_value",
    "error_budget_burn": "polisyos_fabric_error_budget_burn_ratio",
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

    def emit(self, alert: FabricAlert) -> None: ...


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


class FabricSLIName(str, Enum):
    """Named Fabric SLIs that Phase 4 treats as release-blocking signals."""

    FETCH_SUCCESS = "fetch_success"
    SCHEMA_COMPLIANCE = "schema_compliance"
    DATA_FRESHNESS = "data_freshness"
    MATERIALIZATION_FRESHNESS = "materialization_freshness"
    LINEAGE_COVERAGE = "lineage_coverage"
    REPLAY_SUCCESS = "replay_success"
    QUARANTINE_RATE = "quarantine_rate"
    QUERY_LATENCY = "query_latency"


class FabricReliabilityBudgetError(RuntimeError):
    """Raised when a P0/P1 Fabric SLO breach should pause feature expansion."""


def _finite_non_negative(value: float, *, what: str) -> None:
    if not isinstance(value, (int, float)) or not isfinite(float(value)) or float(value) < 0:
        raise ValueError(f"{what} must be a finite non-negative number")


@dataclass(frozen=True)
class FabricSLOTarget:
    """One SLO target in the Fabric reliability policy.

    ``direction`` is ``at_least`` for success/coverage ratios and ``at_most``
    for latency, freshness age, and quarantine rate.
    """

    name: FabricSLIName
    objective: float
    direction: str
    priority: str
    window: str
    unit: str = "ratio"
    description: str = ""

    def __post_init__(self) -> None:
        if self.direction not in {"at_least", "at_most"}:
            raise ValueError(f"Unsupported SLO direction: {self.direction}")
        if self.priority not in {"P0", "P1", "P2", "P3"}:
            raise ValueError(f"Unsupported SLO priority: {self.priority}")
        _finite_non_negative(self.objective, what=f"{self.name.value} objective")
        if self.direction == "at_least" and not 0.0 <= self.objective <= 1.0:
            raise ValueError(f"{self.name.value} ratio objective must be between 0 and 1")


@dataclass(frozen=True)
class FabricSLIObservation:
    """One SLI measurement for a rolling Fabric reliability window."""

    name: FabricSLIName
    value: float
    sample_count: int = 1
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    labels: Mapping[str, str] = field(default_factory=dict)
    reason: str = ""

    def __post_init__(self) -> None:
        _finite_non_negative(self.value, what=f"{self.name.value} value")
        if self.sample_count <= 0:
            raise ValueError("sample_count must be positive")
        if self.name in _RATIO_SLI_NAMES and not 0.0 <= self.value <= 1.0:
            raise ValueError(f"{self.name.value} ratio value must be between 0 and 1")
        observed_at = self.observed_at
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        object.__setattr__(self, "observed_at", observed_at.astimezone(UTC))
        object.__setattr__(
            self,
            "labels",
            {str(key): str(value) for key, value in dict(self.labels).items()},
        )


@dataclass(frozen=True)
class FabricSLOAssessment:
    """Evaluation of one SLI observation against its SLO target."""

    name: FabricSLIName
    target: FabricSLOTarget
    observed_value: float | None
    healthy: bool
    burn_ratio: float | None
    reason: str

    @property
    def priority(self) -> str:
        return self.target.priority


@dataclass(frozen=True)
class FabricReliabilityReport:
    """Release-readiness report for Fabric SLOs."""

    generated_at: datetime
    assessments: tuple[FabricSLOAssessment, ...]
    feature_expansion_allowed: bool
    paused_priorities: tuple[str, ...]
    reasons: tuple[str, ...]

    def assessment_for(self, name: FabricSLIName | str) -> FabricSLOAssessment:
        resolved = FabricSLIName(name)
        for assessment in self.assessments:
            if assessment.name == resolved:
                return assessment
        raise KeyError(resolved.value)


_RATIO_SLI_NAMES = {
    FabricSLIName.FETCH_SUCCESS,
    FabricSLIName.SCHEMA_COMPLIANCE,
    FabricSLIName.LINEAGE_COVERAGE,
    FabricSLIName.REPLAY_SUCCESS,
    FabricSLIName.QUARANTINE_RATE,
}

DEFAULT_FABRIC_SLO_TARGETS: tuple[FabricSLOTarget, ...] = (
    FabricSLOTarget(
        name=FabricSLIName.FETCH_SUCCESS,
        objective=0.995,
        direction="at_least",
        priority="P0",
        window="rolling_7d",
        description="Successful connector fetches divided by attempted fetches.",
    ),
    FabricSLOTarget(
        name=FabricSLIName.SCHEMA_COMPLIANCE,
        objective=0.999,
        direction="at_least",
        priority="P0",
        window="rolling_7d",
        description="Connector payloads that satisfy their active schema contract.",
    ),
    FabricSLOTarget(
        name=FabricSLIName.DATA_FRESHNESS,
        objective=86_400.0,
        direction="at_most",
        priority="P1",
        window="rolling_24h",
        unit="seconds",
        description="P95 age of source/cache data used for decision-bearing reads.",
    ),
    FabricSLOTarget(
        name=FabricSLIName.MATERIALIZATION_FRESHNESS,
        objective=3_600.0,
        direction="at_most",
        priority="P1",
        window="rolling_24h",
        unit="seconds",
        description="P95 lag between accepted segment arrival and materialized visibility.",
    ),
    FabricSLOTarget(
        name=FabricSLIName.LINEAGE_COVERAGE,
        objective=0.99,
        direction="at_least",
        priority="P1",
        window="rolling_7d",
        description="Decision-bearing outputs with source-to-query lineage coverage.",
    ),
    FabricSLOTarget(
        name=FabricSLIName.REPLAY_SUCCESS,
        objective=0.99,
        direction="at_least",
        priority="P1",
        window="rolling_7d",
        description="Replay jobs that reproduce accepted source fixtures deterministically.",
    ),
    FabricSLOTarget(
        name=FabricSLIName.QUARANTINE_RATE,
        objective=0.01,
        direction="at_most",
        priority="P1",
        window="rolling_24h",
        description="Quarantined rows/messages divided by accepted plus quarantined inputs.",
    ),
    FabricSLOTarget(
        name=FabricSLIName.QUERY_LATENCY,
        objective=1.0,
        direction="at_most",
        priority="P1",
        window="rolling_24h",
        unit="seconds",
        description="P95 latency for governed Fabric query paths.",
    ),
)


def evaluate_fabric_reliability_budget(
    observations: Mapping[FabricSLIName | str, float | FabricSLIObservation]
    | Sequence[FabricSLIObservation],
    *,
    targets: Sequence[FabricSLOTarget] = DEFAULT_FABRIC_SLO_TARGETS,
    gate_priorities: Sequence[str] = ("P0", "P1"),
    generated_at: datetime | None = None,
) -> FabricReliabilityReport:
    """Evaluate Fabric SLIs and decide whether P0/P1 expansion may continue."""

    grouped = _group_sli_observations(observations)
    assessments = tuple(_assess_sli(target, grouped.get(target.name, ())) for target in targets)
    gated = set(gate_priorities)
    reasons = tuple(
        assessment.reason
        for assessment in assessments
        if not assessment.healthy and assessment.priority in gated
    )
    paused = tuple(
        sorted({assessment.priority for assessment in assessments if not assessment.healthy})
    )
    stamp = generated_at or datetime.now(UTC)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return FabricReliabilityReport(
        generated_at=stamp.astimezone(UTC),
        assessments=assessments,
        feature_expansion_allowed=not reasons,
        paused_priorities=paused,
        reasons=reasons,
    )


def assert_fabric_feature_expansion_allowed(
    report_or_observations: FabricReliabilityReport
    | Mapping[FabricSLIName | str, float | FabricSLIObservation]
    | Sequence[FabricSLIObservation],
    *,
    targets: Sequence[FabricSLOTarget] = DEFAULT_FABRIC_SLO_TARGETS,
    gate_priorities: Sequence[str] = ("P0", "P1"),
) -> FabricReliabilityReport:
    """Raise if P0/P1 expansion should pause because Fabric is burning budget."""

    report = (
        report_or_observations
        if isinstance(report_or_observations, FabricReliabilityReport)
        else evaluate_fabric_reliability_budget(
            report_or_observations,
            targets=targets,
            gate_priorities=gate_priorities,
        )
    )
    if not report.feature_expansion_allowed:
        joined = "; ".join(report.reasons)
        raise FabricReliabilityBudgetError(joined or "Fabric reliability budget is burned")
    return report


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
    sli_observations: Mapping[FabricSLIName | str, float | FabricSLIObservation]
    | Sequence[FabricSLIObservation]
    | None = None,
    alert_sink: AlertSink | None = None,
    metrics: Any | None = None,
) -> FabricHealthSnapshot:
    """Aggregate connector/cache/world/data-plane/retrieval health into one snapshot."""
    sink = alert_sink or NoOpAlertSink()
    components: list[HealthComponentSnapshot] = []

    connector_component = _connector_health_component(registry)
    cache_component = _cache_health_component(cache_store)
    world_component = _world_health_component(fact_log_root)
    data_plane_component = _data_plane_health_component(cursor_store)
    retrieval_component = _retrieval_health_component(retrieval_service)
    slo_component = _slo_health_component(sli_observations)

    for component in (
        connector_component,
        cache_component,
        world_component,
        data_plane_component,
        retrieval_component,
        slo_component,
    ):
        if component is not None:
            components.append(component)
            if not component.healthy:
                sink.emit(
                    FabricAlert(
                        component=component.name,
                        severity=(
                            AlertSeverity.CRITICAL
                            if component.name == "slo"
                            else AlertSeverity.WARNING
                        ),
                        code="health_degraded",
                        message="Fabric component reported degraded health",
                        context={
                            "reasons": list(component.reasons),
                            **component.details,
                        },
                    )
                )

    reasons = tuple(
        reason for component in components if not component.healthy for reason in component.reasons
    )
    snapshot = FabricHealthSnapshot(
        healthy=all(component.healthy for component in components) if components else True,
        components=tuple(components),
        reasons=reasons,
    )
    _record_health_metrics(snapshot, metrics=metrics)
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


def _slo_health_component(
    observations: Mapping[FabricSLIName | str, float | FabricSLIObservation]
    | Sequence[FabricSLIObservation]
    | None,
) -> HealthComponentSnapshot | None:
    if observations is None:
        return None
    report = evaluate_fabric_reliability_budget(observations)
    return HealthComponentSnapshot(
        name="slo",
        healthy=report.feature_expansion_allowed,
        reasons=report.reasons,
        details={
            "paused_priorities": list(report.paused_priorities),
            "assessments": [
                {
                    "name": item.name.value,
                    "observed_value": item.observed_value,
                    "objective": item.target.objective,
                    "direction": item.target.direction,
                    "priority": item.priority,
                    "window": item.target.window,
                    "healthy": item.healthy,
                    "burn_ratio": item.burn_ratio,
                }
                for item in report.assessments
            ],
        },
    )


def _record_health_metrics(
    snapshot: FabricHealthSnapshot,
    *,
    metrics: Any | None = None,
) -> None:
    resolved_metrics = metrics if metrics is not None else _default_metrics()
    if resolved_metrics is None:
        return
    for component in snapshot.components:
        if component.name == "world" and getattr(
            resolved_metrics,
            "set_fabric_segment_count",
            None,
        ):
            resolved_metrics.set_fabric_segment_count(
                float(component.details.get("segment_count", 0))
            )  # type: ignore[misc]
        if component.name == "retrieval" and getattr(
            resolved_metrics,
            "set_fabric_dlq_count",
            None,
        ):
            resolved_metrics.set_fabric_dlq_count(0.0)  # type: ignore[misc]
        if component.name == "slo" and getattr(
            resolved_metrics,
            "record_fabric_slo_assessment",
            None,
        ):
            for assessment in component.details.get("assessments", []):
                resolved_metrics.record_fabric_slo_assessment(
                    sli_name=str(assessment.get("name")),
                    observed_value=assessment.get("observed_value"),
                    burn_ratio=assessment.get("burn_ratio"),
                    healthy=bool(assessment.get("healthy")),
                    priority=str(assessment.get("priority")),
                    window=str(assessment.get("window", "unknown")),
                )  # type: ignore[misc]


def _group_sli_observations(
    observations: Mapping[FabricSLIName | str, float | FabricSLIObservation]
    | Sequence[FabricSLIObservation],
) -> dict[FabricSLIName, tuple[FabricSLIObservation, ...]]:
    grouped: dict[FabricSLIName, list[FabricSLIObservation]] = {}
    if isinstance(observations, Mapping):
        iterable = []
        for raw_name, raw_value in observations.items():
            name = FabricSLIName(raw_name)
            if isinstance(raw_value, FabricSLIObservation):
                observation = raw_value
                if observation.name != name:
                    raise ValueError("SLI mapping key and observation name disagree")
            else:
                observation = FabricSLIObservation(name=name, value=float(raw_value))
            iterable.append(observation)
    else:
        iterable = list(observations)

    for observation in iterable:
        if not isinstance(observation, FabricSLIObservation):
            raise TypeError("observations must contain FabricSLIObservation instances")
        grouped.setdefault(observation.name, []).append(observation)
    return {name: tuple(values) for name, values in grouped.items()}


def _assess_sli(
    target: FabricSLOTarget,
    observations: Sequence[FabricSLIObservation],
) -> FabricSLOAssessment:
    if not observations:
        return FabricSLOAssessment(
            name=target.name,
            target=target,
            observed_value=None,
            healthy=False,
            burn_ratio=None,
            reason=f"{target.name.value}: missing SLI observation for {target.window}",
        )

    total_samples = sum(item.sample_count for item in observations)
    observed = sum(item.value * item.sample_count for item in observations) / total_samples
    if target.direction == "at_least":
        healthy = observed >= target.objective
        error_budget = max(1.0 - target.objective, 1e-12)
        burn_ratio = (1.0 - observed) / error_budget
    else:
        healthy = observed <= target.objective
        burn_ratio = observed / max(target.objective, 1e-12)
    reason = ""
    if not healthy:
        comparison = ">=" if target.direction == "at_least" else "<="
        reason = (
            f"{target.name.value}: observed {observed:.6g} must be "
            f"{comparison} {target.objective:.6g} over {target.window}"
        )
    return FabricSLOAssessment(
        name=target.name,
        target=target,
        observed_value=observed,
        healthy=healthy,
        burn_ratio=max(0.0, float(burn_ratio)),
        reason=reason,
    )
