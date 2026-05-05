"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "EvidenceSourcesConfig",
    "build_path_source_status",
    "merge_evidence_sources_payload",
    "normalize_evidence_sources_config",
    "update_source_status",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "EvidenceSourcesConfig": ("polisyos.scientist.evidence.sources", "EvidenceSourcesConfig"),
    "build_path_source_status": ("polisyos.scientist.evidence.sources", "build_path_source_status"),
    "merge_evidence_sources_payload": (
        "polisyos.scientist.evidence.sources",
        "merge_evidence_sources_payload",
    ),
    "normalize_evidence_sources_config": (
        "polisyos.scientist.evidence.sources",
        "normalize_evidence_sources_config",
    ),
    "update_source_status": ("polisyos.scientist.evidence.sources", "update_source_status"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(
            f"module 'polisyos.scientist.evidence_sources' has no attribute {name!r}"
        )
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
