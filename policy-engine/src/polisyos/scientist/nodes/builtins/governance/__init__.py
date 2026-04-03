"""Public builtins governance package API."""
from __future__ import annotations

from typing import Any

__all__ = [
    "DataPlaneGateNode",
    "LegalCheckNode",
    "RunNormativeArbitrationNode",
    "RunGovernanceNode",
]


def __getattr__(name: str) -> Any:
    if name == "DataPlaneGateNode":
        from .data_plane_gate import DataPlaneGateNode

        return DataPlaneGateNode
    if name == "LegalCheckNode":
        from .legal_check import LegalCheckNode

        return LegalCheckNode
    if name == "RunNormativeArbitrationNode":
        from .run_normative_arbitration import RunNormativeArbitrationNode

        return RunNormativeArbitrationNode
    if name == "RunGovernanceNode":
        from .run_governance import RunGovernanceNode

        return RunGovernanceNode
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
