"""Lazy facade for Lex projections of Fabric evidence paths."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

__all__ = [
    "LexFabricEvidencePath",
    "lex_evidence_from_evidence_path",
    "lex_evidence_from_fabric_decision_data",
]

_EXPORTS = {
    "LexFabricEvidencePath": "LexFabricEvidencePath",
    "lex_evidence_from_evidence_path": "lex_evidence_from_evidence_path",
    "lex_evidence_from_fabric_decision_data": "lex_evidence_from_fabric_decision_data",
}

if TYPE_CHECKING:
    from .adapter import (
        LexFabricEvidencePath as LexFabricEvidencePath,
    )
    from .adapter import (
        lex_evidence_from_evidence_path as lex_evidence_from_evidence_path,
    )
    from .adapter import (
        lex_evidence_from_fabric_decision_data as lex_evidence_from_fabric_decision_data,
    )


def __getattr__(name: str) -> object:
    """Resolve a provenance adapter only when its symbol is requested."""
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(f"{__name__}.adapter")
    value = getattr(module, _EXPORTS[name])
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Return loaded names and the supported adapter exports."""
    return sorted(set(globals()) | set(__all__))
