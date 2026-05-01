"""Expose Scholar enrichment entrypoints and contracts via lazy imports.

The Scholar package facade is intentionally narrow: it exports enrichment
results, policy knobs, domain-specific exceptions, and the `ScholarService`
boundary used by runtime and CLI callers. Lazy imports avoid loading the
document/claim pipeline until a caller actually invokes Scholar APIs.

Names listed in `__all__` are the supported package-level surface.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "EnrichResultV1",
    "EnrichmentReportV1",
    "KnowledgeBundlePayloadV1",
    "ScholarAcquireError",
    "ScholarBundleError",
    "ScholarClaimsError",
    "ScholarDiscoverError",
    "ScholarDocsError",
    "ScholarError",
    "ScholarFabricCitation",
    "ScholarPolicy",
    "ScholarReconcileError",
    "ScholarService",
    "ScholarValidationError",
    "enrich_topic",
    "scholar_citation_from_fabric_decision_data",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "ScholarService": ("polisyos.scholar.api", "ScholarService"),
    "enrich_topic": ("polisyos.scholar.api", "enrich_topic"),
    "ScholarAcquireError": ("polisyos.scholar.errors", "ScholarAcquireError"),
    "ScholarBundleError": ("polisyos.scholar.errors", "ScholarBundleError"),
    "ScholarClaimsError": ("polisyos.scholar.errors", "ScholarClaimsError"),
    "ScholarDiscoverError": ("polisyos.scholar.errors", "ScholarDiscoverError"),
    "ScholarDocsError": ("polisyos.scholar.errors", "ScholarDocsError"),
    "ScholarError": ("polisyos.scholar.errors", "ScholarError"),
    "ScholarReconcileError": ("polisyos.scholar.errors", "ScholarReconcileError"),
    "ScholarValidationError": ("polisyos.scholar.errors", "ScholarValidationError"),
    "ScholarPolicy": ("polisyos.scholar.policies", "ScholarPolicy"),
    "ScholarFabricCitation": ("polisyos.scholar.provenance", "ScholarFabricCitation"),
    "scholar_citation_from_fabric_decision_data": (
        "polisyos.scholar.provenance",
        "scholar_citation_from_fabric_decision_data",
    ),
    "EnrichResultV1": ("polisyos.scholar.types", "EnrichResultV1"),
    "EnrichmentReportV1": ("polisyos.scholar.types", "EnrichmentReportV1"),
    "KnowledgeBundlePayloadV1": ("polisyos.scholar.types", "KnowledgeBundlePayloadV1"),
}


def __getattr__(name: str) -> Any:
    """Resolve one exported Scholar symbol and cache it on the package."""
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.scholar' has no attribute '{name}'")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return loaded globals plus deferred Scholar exports."""
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
