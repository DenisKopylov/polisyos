"""Fabric adapter over the canonical core observability contract."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from polisyos.core.observability import get_current_trace_context, get_metrics, get_tracer


@dataclass(frozen=True)
class FabricObservabilityAdapter:
    """Package-local access point for Fabric telemetry callers."""

    component: str = "fabric"

    def metrics(self) -> Any:
        """Return the canonical process-wide metrics registry."""
        return get_metrics()

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
        span_name = operation if operation.startswith(f"{self.component}.") else (
            f"{self.component}.{operation}"
        )
        span_attributes = {"polisyos.package": self.component, **dict(attributes or {})}
        with get_tracer().start_as_current_span(
            span_name,
            attributes=span_attributes,
        ) as span:
            yield span


def get_fabric_observability_adapter() -> FabricObservabilityAdapter:
    """Return the default Fabric observability adapter."""
    return FabricObservabilityAdapter()


__all__ = ["FabricObservabilityAdapter", "get_fabric_observability_adapter"]
