"""Bundle the three Trinity artifacts as one validated policy payload.

``ProblemFrame`` defines **what** to optimize/protect, ``PolicySpec`` defines
the proposed intervention/governance surface, and ``ModelSpec`` defines **how**
the world is simulated. ``TrinityBundle`` keeps these contracts together for
loading, validation, and migration-safe persistence.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import Field

from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemFrame
from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.model_layer.model_spec import ModelSpec

if TYPE_CHECKING:
    from polisyos.ir.trinity.loaders import (
        load_trinity_bundle_artifact as load_trinity_bundle_artifact,
    )
    from polisyos.ir.trinity.loaders import (
        persist_trinity_bundle_artifact as persist_trinity_bundle_artifact,
    )

TRINITY_BUNDLE_SCHEMA_VERSION = "1.0"
SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


class TrinityBundle(KernelModel):
    """Validate and transport the ``ProblemFrame`` / ``PolicySpec`` / ``ModelSpec`` triple."""

    ARTIFACT_SCHEMA_NAME: ClassVar[str] = "polisyos.ir.TrinityBundle"
    ARTIFACT_SCHEMA_VERSION: ClassVar[str] = TRINITY_BUNDLE_SCHEMA_VERSION
    ARTIFACT_KIND: ClassVar[Literal["ir.trinity_bundle"]] = "ir.trinity_bundle"
    ARTIFACT_MEDIA_TYPE: ClassVar[Literal["application/json"]] = "application/json"

    schema_version: str = Field(
        default=TRINITY_BUNDLE_SCHEMA_VERSION, pattern=SCHEMA_VERSION_PATTERN
    )
    problem_frame: ProblemFrame
    policy_spec: PolicySpec
    model_spec: ModelSpec


__all__ = [
    "TRINITY_BUNDLE_SCHEMA_VERSION",
    "ModelSpec",
    "PolicySpec",
    "ProblemFrame",
    "TrinityBundle",
    "load_trinity_bundle_artifact",
    "persist_trinity_bundle_artifact",
]


def __getattr__(name: str) -> object:
    if name == "load_trinity_bundle_artifact":
        from polisyos.ir.trinity.loaders import load_trinity_bundle_artifact

        globals()[name] = load_trinity_bundle_artifact
        return load_trinity_bundle_artifact
    if name == "persist_trinity_bundle_artifact":
        from polisyos.ir.trinity.loaders import persist_trinity_bundle_artifact

        globals()[name] = persist_trinity_bundle_artifact
        return persist_trinity_bundle_artifact
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
