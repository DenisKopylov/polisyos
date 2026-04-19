"""Expose replay/runtime contracts without importing heavy implementations eagerly.

`polisyos.runtime` is the package-level facade for replay planning and
verification APIs. Exports are resolved lazily from `polisyos.runtime.replay`
to keep import-time side effects predictable for CLI tools and libraries.

The symbols listed in `__all__` are the stable replay surface for callers.
"""
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .replay import (
        CompletenessLevel,
        CompletenessReport,
        ReplayPlan,
        ReplayStrategy,
        VerificationConfig,
        VerificationMode,
        VerificationResult,
        build_replay_plan,
        completeness_check,
        verify_replay,
    )

__all__ = [
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
    """Resolve one lazily exported replay symbol.

    Raises:
        AttributeError: If `name` is not part of the runtime facade contract.
    """
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.runtime' has no attribute '{name}'")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return loaded globals plus deferred replay exports."""
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
