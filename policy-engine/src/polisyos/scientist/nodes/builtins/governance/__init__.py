from __future__ import annotations

from typing import Any

__all__ = ["LegalCheckNode", "RunGovernanceNode"]


def __getattr__(name: str) -> Any:
    if name == "LegalCheckNode":
        from .legal_check import LegalCheckNode

        return LegalCheckNode
    if name == "RunGovernanceNode":
        from .run_governance import RunGovernanceNode

        return RunGovernanceNode
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
