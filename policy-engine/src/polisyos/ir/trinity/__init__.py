"""Bundle the three Trinity artifacts as one validated policy payload.

``ProblemFrame`` defines **what** to optimize/protect, ``PolicySpec`` defines
the proposed intervention/governance surface, and ``ModelSpec`` defines **how**
the world is simulated. ``TrinityBundle`` keeps these contracts together for
loading, validation, and migration-safe persistence.
"""

from __future__ import annotations

from pydantic import Field

from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemFrame
from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.model_spec import ModelSpec

TRINITY_BUNDLE_SCHEMA_VERSION = "1.0"
SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class TrinityBundle(KernelModel):
    """Validate and transport the ``ProblemFrame`` / ``PolicySpec`` / ``ModelSpec`` triple."""

    schema_version: str = Field(TRINITY_BUNDLE_SCHEMA_VERSION, pattern=SCHEMA_VERSION_PATTERN)
    problem_frame: ProblemFrame
    policy_spec: PolicySpec
    model_spec: ModelSpec


__all__ = [
    "TRINITY_BUNDLE_SCHEMA_VERSION",
    "ModelSpec",
    "PolicySpec",
    "ProblemFrame",
    "TrinityBundle",
]
