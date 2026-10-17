"""Expose Scholar orchestration helpers through a lazy package facade."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

__all__ = [
    "build_knowledge_bundle_payload",
    "compute_bundle_id",
    "enrich_topic",
    "persist_bundle_and_event",
]

if TYPE_CHECKING:
    from .bundle import (
        build_knowledge_bundle_payload as build_knowledge_bundle_payload,
    )
    from .bundle import (
        compute_bundle_id as compute_bundle_id,
    )
    from .bundle import (
        persist_bundle_and_event as persist_bundle_and_event,
    )
    from .enrich import enrich_topic as enrich_topic

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "build_knowledge_bundle_payload": (".bundle", "build_knowledge_bundle_payload"),
    "compute_bundle_id": (".bundle", "compute_bundle_id"),
    "enrich_topic": (".enrich", "enrich_topic"),
    "persist_bundle_and_event": (".bundle", "persist_bundle_and_event"),
}


def __getattr__(name: str) -> object:
    """Resolve one exported orchestration symbol on demand."""
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.scholar.orchestrator' has no attribute '{name}'")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return loaded globals plus deferred orchestration exports."""
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
