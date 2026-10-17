"""Lazy facade for NormPack assembly and legal-authority operations."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

__all__ = [
    "NormPackBudgets",
    "NormPackBuildRequest",
    "NormPackBuildResult",
    "assemble_norm_pack",
    "build_legal_authority_report",
    "build_legal_authority_requirement_artifact",
    "build_policy_conflict_check_report",
    "normalize_policy_conflict_check_report",
]

_EXPORTS: dict[str, tuple[str, str]] = {
    "NormPackBudgets": ("types", "NormPackBudgets"),
    "NormPackBuildRequest": ("types", "NormPackBuildRequest"),
    "NormPackBuildResult": ("types", "NormPackBuildResult"),
    "assemble_norm_pack": ("assemble_pack", "assemble_norm_pack"),
    "build_legal_authority_report": ("legal_authority", "build_legal_authority_report"),
    "build_legal_authority_requirement_artifact": (
        "legal_authority",
        "build_legal_authority_requirement_artifact",
    ),
    "build_policy_conflict_check_report": (
        "conflict_check",
        "build_policy_conflict_check_report",
    ),
    "normalize_policy_conflict_check_report": (
        "conflict_check",
        "normalize_policy_conflict_check_report",
    ),
}

if TYPE_CHECKING:
    from .assemble_pack import assemble_norm_pack as assemble_norm_pack
    from .conflict_check import (
        build_policy_conflict_check_report as build_policy_conflict_check_report,
    )
    from .conflict_check import (
        normalize_policy_conflict_check_report as normalize_policy_conflict_check_report,
    )
    from .legal_authority import (
        build_legal_authority_report as build_legal_authority_report,
    )
    from .legal_authority import (
        build_legal_authority_requirement_artifact as build_legal_authority_requirement_artifact,
    )
    from .types import (
        NormPackBudgets as NormPackBudgets,
    )
    from .types import (
        NormPackBuildRequest as NormPackBuildRequest,
    )
    from .types import (
        NormPackBuildResult as NormPackBuildResult,
    )


def __getattr__(name: str) -> object:
    """Resolve a NormPack API symbol without eager implementation imports."""
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    module = importlib.import_module(f"{__name__}.{module_name}")
    value = getattr(module, attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return loaded names and the supported NormPack facade exports."""
    return sorted(set(globals()) | set(__all__))
