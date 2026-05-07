"""Compatibility helpers for Scientist package moves."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from typing import Any

SHIM_SUNSET_DATE = "2026-12-31"
SHIM_ISSUE = (
    "docs/plans/archive/2026-05-07-repository-best-in-class-remediation-master-plan.md"
    "#phase-45---scientist-engine-llm-compute-and-orchestration-lane"
)


def _public_names(module: ModuleType) -> tuple[str, ...]:
    exported = getattr(module, "__all__", None)
    if exported is not None:
        return tuple(str(name) for name in exported)
    return tuple(name for name in vars(module) if not name.startswith("_"))


def reexport_package(
    shim_name: str,
    canonical_name: str,
    target_globals: dict[str, Any],
) -> ModuleType:
    """Re-export a moved package while preserving the legacy package path."""
    module = importlib.import_module(canonical_name)
    target_globals["__all__"] = _public_names(module)
    target_globals["__canonical_module__"] = canonical_name
    target_globals["__shim_sunset_date__"] = SHIM_SUNSET_DATE
    target_globals["__shim_issue__"] = SHIM_ISSUE
    if getattr(module, "__doc__", None):
        target_globals["__doc__"] = module.__doc__
    module_vars = vars(module)
    for name in target_globals["__all__"]:
        if name in module_vars:
            target_globals[name] = module_vars[name]
    for name in ("__getattr__", "__dir__"):
        if hasattr(module, name):
            target_globals[name] = getattr(module, name)
    return module


def alias_module(
    shim_name: str,
    canonical_name: str,
    target_globals: dict[str, Any],
) -> ModuleType:
    """Alias a moved module so old and canonical imports share identity."""
    module = importlib.import_module(canonical_name)
    module.__canonical_module__ = canonical_name  # type: ignore[attr-defined]
    module.__shim_sunset_date__ = SHIM_SUNSET_DATE  # type: ignore[attr-defined]
    module.__shim_issue__ = SHIM_ISSUE  # type: ignore[attr-defined]
    target_globals.update(module.__dict__)
    target_globals["__canonical_module__"] = canonical_name
    target_globals["__shim_sunset_date__"] = SHIM_SUNSET_DATE
    target_globals["__shim_issue__"] = SHIM_ISSUE
    sys.modules[shim_name] = module
    return module
