"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "DeadLetterCorruptedError",
    "DeadLetterError",
    "DeadLetterNotFoundError",
    "DeadLetterRecord",
    "ReplayBackendResult",
    "list_dead_letters",
    "load_dead_letter",
    "replay_dead_letter",
    "replay_packet",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "DeadLetterCorruptedError": ("polisyos.scientist.replay.backend", "DeadLetterCorruptedError"),
    "DeadLetterError": ("polisyos.scientist.replay.backend", "DeadLetterError"),
    "DeadLetterNotFoundError": ("polisyos.scientist.replay.backend", "DeadLetterNotFoundError"),
    "DeadLetterRecord": ("polisyos.scientist.replay.backend", "DeadLetterRecord"),
    "ReplayBackendResult": ("polisyos.scientist.replay.backend", "ReplayBackendResult"),
    "list_dead_letters": ("polisyos.scientist.replay.backend", "list_dead_letters"),
    "load_dead_letter": ("polisyos.scientist.replay.backend", "load_dead_letter"),
    "replay_dead_letter": ("polisyos.scientist.replay.backend", "replay_dead_letter"),
    "replay_packet": ("polisyos.scientist.replay.backend", "replay_packet"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(
            f"module 'polisyos.scientist.replay_backend' has no attribute {name!r}"
        )
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
