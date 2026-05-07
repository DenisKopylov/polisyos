"""Scientist replay hub for dead-letter, diff, and verification helpers."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = (
    "ComparatorRegistry",
    "DeadLetterCorruptedError",
    "DeadLetterError",
    "DeadLetterNotFoundError",
    "DeadLetterRecord",
    "DiffToleranceConfig",
    "FieldDiff",
    "REPLAY_VERIFICATION_REPORT_SCHEMA_NAME",
    "ReplayBackendResult",
    "ReplayDiffInputError",
    "ReplayDiffResult",
    "ReplayRegistry",
    "ReplayRegistryEntry",
    "ReplayRegistrySnapshot",
    "ReplayVerificationReport",
    "build_replay_verification_report",
    "compute_replay_diff",
    "list_dead_letters",
    "load_dead_letter",
    "load_replay_verification_report",
    "persist_replay_verification_report",
    "replay_dead_letter",
    "replay_packet",
    "save_diff_report",
    "verify_and_persist_replay_bundle",
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
    "ComparatorRegistry": ("polisyos.scientist.replay.diff", "ComparatorRegistry"),
    "DiffToleranceConfig": ("polisyos.scientist.replay.diff", "DiffToleranceConfig"),
    "FieldDiff": ("polisyos.scientist.replay.diff", "FieldDiff"),
    "ReplayDiffInputError": ("polisyos.scientist.replay.diff", "ReplayDiffInputError"),
    "ReplayDiffResult": ("polisyos.scientist.replay.diff", "ReplayDiffResult"),
    "compute_replay_diff": ("polisyos.scientist.replay.diff", "compute_replay_diff"),
    "save_diff_report": ("polisyos.scientist.replay.diff", "save_diff_report"),
    "REPLAY_VERIFICATION_REPORT_SCHEMA_NAME": (
        "polisyos.scientist.replay.verification",
        "REPLAY_VERIFICATION_REPORT_SCHEMA_NAME",
    ),
    "ReplayRegistry": ("polisyos.scientist.replay.verification", "ReplayRegistry"),
    "ReplayRegistryEntry": ("polisyos.scientist.replay.verification", "ReplayRegistryEntry"),
    "ReplayRegistrySnapshot": (
        "polisyos.scientist.replay.verification",
        "ReplayRegistrySnapshot",
    ),
    "ReplayVerificationReport": (
        "polisyos.scientist.replay.verification",
        "ReplayVerificationReport",
    ),
    "build_replay_verification_report": (
        "polisyos.scientist.replay.verification",
        "build_replay_verification_report",
    ),
    "load_replay_verification_report": (
        "polisyos.scientist.replay.verification",
        "load_replay_verification_report",
    ),
    "persist_replay_verification_report": (
        "polisyos.scientist.replay.verification",
        "persist_replay_verification_report",
    ),
    "verify_and_persist_replay_bundle": (
        "polisyos.scientist.replay.verification",
        "verify_and_persist_replay_bundle",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.scientist.replay' has no attribute {name!r}")
    module_name, attr_name = _LAZY_IMPORTS[name]
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
