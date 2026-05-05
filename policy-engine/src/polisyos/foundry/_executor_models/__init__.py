"""Compatibility shim for a Phase 5/6 decomposition module move."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "ApplyArtifacts",
    "ExecuteArtifacts",
    "ExecutionStrictness",
    "FailureCard",
    "FailureKind",
    "FailureSeverity",
    "artifact_id",
    "get_state_path",
    "load_model",
    "load_payload",
    "load_tensor",
    "put_tensor",
    "set_state_path",
)

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "ApplyArtifacts": ("polisyos.foundry.execute._models", "ApplyArtifacts"),
    "ExecuteArtifacts": ("polisyos.foundry.execute._models", "ExecuteArtifacts"),
    "ExecutionStrictness": ("polisyos.foundry.execute._models", "ExecutionStrictness"),
    "FailureCard": ("polisyos.foundry.execute._models", "FailureCard"),
    "FailureKind": ("polisyos.foundry.execute._models", "FailureKind"),
    "FailureSeverity": ("polisyos.foundry.execute._models", "FailureSeverity"),
    "artifact_id": ("polisyos.foundry.execute._models", "artifact_id"),
    "get_state_path": ("polisyos.foundry.execute._models", "get_state_path"),
    "load_model": ("polisyos.foundry.execute._models", "load_model"),
    "load_payload": ("polisyos.foundry.execute._models", "load_payload"),
    "load_tensor": ("polisyos.foundry.execute._models", "load_tensor"),
    "put_tensor": ("polisyos.foundry.execute._models", "put_tensor"),
    "set_state_path": ("polisyos.foundry.execute._models", "set_state_path"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(
            f"module 'polisyos.foundry._executor_models' has no attribute {name!r}"
        )
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
