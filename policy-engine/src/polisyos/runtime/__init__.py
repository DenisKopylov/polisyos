from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "RunManifest",
    "append_audit",
    "finalize_run",
    "log_artifact",
    "resolve_artifact_path",
    "start_run",
    "update_budget_usage",
    "ReplayStrategy",
    "ReplayPlan",
    "CompletenessLevel",
    "CompletenessReport",
    "VerificationMode",
    "VerificationConfig",
    "VerificationResult",
    "build_replay_plan",
    "completeness_check",
    "verify_replay",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "append_audit": ("polisyos.runtime.api", "append_audit"),
    "finalize_run": ("polisyos.runtime.api", "finalize_run"),
    "log_artifact": ("polisyos.runtime.api", "log_artifact"),
    "resolve_artifact_path": ("polisyos.runtime.api", "resolve_artifact_path"),
    "start_run": ("polisyos.runtime.api", "start_run"),
    "update_budget_usage": ("polisyos.runtime.api", "update_budget_usage"),
    "RunManifest": ("polisyos.runtime.manifest", "RunManifest"),
    "CompletenessLevel": ("polisyos.runtime.replay", "CompletenessLevel"),
    "CompletenessReport": ("polisyos.runtime.replay", "CompletenessReport"),
    "ReplayPlan": ("polisyos.runtime.replay", "ReplayPlan"),
    "ReplayStrategy": ("polisyos.runtime.replay", "ReplayStrategy"),
    "VerificationConfig": ("polisyos.runtime.replay", "VerificationConfig"),
    "VerificationMode": ("polisyos.runtime.replay", "VerificationMode"),
    "VerificationResult": ("polisyos.runtime.replay", "VerificationResult"),
    "build_replay_plan": ("polisyos.runtime.replay", "build_replay_plan"),
    "completeness_check": ("polisyos.runtime.replay", "completeness_check"),
    "verify_replay": ("polisyos.runtime.replay", "verify_replay"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.runtime' has no attribute '{name}'")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
