"""Lazily export service helpers behind runtime HTTP endpoints."""

from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "ArtifactInspectorService": (
        "polisyos.runtime.http.services.artifact_inspector",
        "ArtifactInspectorService",
    ),
    "AttractorAnalysisService": (
        "polisyos.runtime.http.services.attractors",
        "AttractorAnalysisService",
    ),
    "DebugService": ("polisyos.runtime.http.services.debug", "DebugService"),
    "IndexedRunRecord": ("polisyos.runtime.http.services.run_index", "IndexedRunRecord"),
    "LineageService": ("polisyos.runtime.http.services.lineage", "LineageService"),
    "MobilityService": ("polisyos.runtime.http.services.mobility", "MobilityService"),
    "RunIndexService": ("polisyos.runtime.http.services.run_index", "RunIndexService"),
    "ScenarioService": ("polisyos.runtime.http.services.scenarios", "ScenarioService"),
    "TemporalService": ("polisyos.runtime.http.services.temporal", "TemporalService"),
    "TimelineService": ("polisyos.runtime.http.services.timeline", "TimelineService"),
}


def __getattr__(name: str) -> object:
    """Resolve a public service only when a caller requests it."""
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return public service names without resolving their implementations."""
    return sorted({*globals(), *_EXPORTS})

__all__ = [
    "ArtifactInspectorService",
    "AttractorAnalysisService",
    "DebugService",
    "IndexedRunRecord",
    "LineageService",
    "MobilityService",
    "RunIndexService",
    "ScenarioService",
    "TemporalService",
    "TimelineService",
]
