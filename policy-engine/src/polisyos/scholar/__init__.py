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
    "ScholarPolicy",
    "ScholarReconcileError",
    "ScholarService",
    "ScholarValidationError",
    "enrich_topic",
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
    "EnrichResultV1": ("polisyos.scholar.types", "EnrichResultV1"),
    "EnrichmentReportV1": ("polisyos.scholar.types", "EnrichmentReportV1"),
    "KnowledgeBundlePayloadV1": ("polisyos.scholar.types", "KnowledgeBundlePayloadV1"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.scholar' has no attribute '{name}'")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
