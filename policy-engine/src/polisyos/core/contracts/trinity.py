"""
Trinity Contracts: Typed references for ProblemFrame, PolicySpec, ModelSpec.

These references follow the existing ArtifactRef pattern from foundry.py/fabric.py,
providing compile-time type safety and runtime validation.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..artifacts.manifest import ArtifactRef


class ProblemFrameRef(ArtifactRef):
    """
    Typed reference to a ProblemFrame artifact.

    Example:
        ref = ProblemFrameRef(
            artifact_id=artifact_id,
            kind="ir.problem_frame",
            media_type="application/json",
        )
    """

    kind: Literal["ir.problem_frame"] = "ir.problem_frame"
    media_type: Literal["application/json"] = "application/json"


class PolicySpecRef(ArtifactRef):
    """
    Typed reference to a PolicySpec artifact.

    Example:
        ref = PolicySpecRef(
            artifact_id=artifact_id,
            kind="ir.policy_spec",
            media_type="application/json",
        )
    """

    kind: Literal["ir.policy_spec"] = "ir.policy_spec"
    media_type: Literal["application/json"] = "application/json"


class ModelSpecRef(ArtifactRef):
    """
    Typed reference to a ModelSpec (WorldModel) artifact.

    Example:
        ref = ModelSpecRef(
            artifact_id=artifact_id,
            kind="ir.model_spec",
            media_type="application/json",
        )
    """

    kind: Literal["ir.model_spec"] = "ir.model_spec"
    media_type: Literal["application/json"] = "application/json"


class TrinityBundleRef(ArtifactRef):
    """
    Typed reference to a TrinityBundle artifact.

    Used when the bundle itself is stored as a single artifact in CAS.
    """

    kind: Literal["ir.trinity_bundle"] = "ir.trinity_bundle"
    media_type: Literal["application/json"] = "application/json"


class TrinityBundle(BaseModel):
    """
    Bundle containing references to all three Trinity artifacts.

    Used in DecisionPacket and other contexts where the complete
    problem/policy/model context is needed.
    """

    model_config = ConfigDict(extra="forbid")

    problem_frame_ref: ProblemFrameRef
    policy_spec_ref: PolicySpecRef
    model_spec_ref: ModelSpecRef

    compatible: bool = Field(True, description="Whether the three artifacts are compatible")
    compatibility_notes: list[str] = Field(default_factory=list)


class TrinityManifest(BaseModel):
    """
    Manifest linking Trinity artifacts with metadata.

    Provides a complete experiment context linking the "Why", "What", and "How".
    """

    model_config = ConfigDict(extra="forbid")

    manifest_id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    bundle: TrinityBundle

    experiment_name: str | None = None
    created_by: str | None = None
    created_at: str | None = None  # ISO 8601 timestamp

    notes: list[str] = Field(default_factory=list)
