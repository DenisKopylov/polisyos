"""
Typed references for Scientist layer artifacts.

These provide type-safe references to CAS-stored artifacts,
enabling static analysis and IDE support while maintaining
the content-addressable architecture.
"""

from __future__ import annotations

from typing import Literal, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from polisyos.scientist.agent.failure_card import FailureCard


class ArtifactRef(BaseModel):
    """Base class for CAS artifact references."""

    ref_type: str = Field(description="Type discriminator for the reference")
    cas_hash: str = Field(
        pattern=r"^sha256:[a-f0-9]{64}$",
        description="Content-addressable storage hash",
    )
    artifact_type: str = Field(description="Type of artifact being referenced")


class FailureCardRef(ArtifactRef):
    """
    Typed reference to a FailureCard artifact in CAS.

    Used in state schemas to reference failure history without
    embedding full FailureCard objects in workflow state.
    """

    ref_type: Literal["failure_card"] = "failure_card"
    artifact_type: Literal["failure_card"] = "failure_card"

    # Denormalized fields for quick filtering without CAS lookup
    attempt_number: int = Field(ge=1, description="Which retry attempt this represents")
    error_code: str = Field(description="Error code for quick categorization")
    source_step: str = Field(description="Origin of the failure")
    can_retry: bool = Field(description="Whether this failure allowed retry")

    @classmethod
    def from_card(cls, card: "FailureCard") -> "FailureCardRef":
        """Create a reference from a FailureCard instance."""
        return cls(
            cas_hash=card.content_hash,
            attempt_number=card.attempt_number,
            error_code=card.error_code,
            source_step=card.source_step.value,
            can_retry=card.can_retry,
        )


class PolicyIRRef(ArtifactRef):
    """Reference to a PolicySurfaceIR artifact."""

    ref_type: Literal["policy_ir"] = "policy_ir"
    artifact_type: Literal["policy_ir"] = "policy_ir"

    version: int = Field(ge=1, description="Revision number of this IR")
    status: str = Field(description="Current status: draft, validated, rejected")


class CritiqueRef(ArtifactRef):
    """Reference to a Critic evaluation artifact."""

    ref_type: Literal["critique"] = "critique"
    artifact_type: Literal["critique"] = "critique"

    verdict: str = Field(description="Critic's verdict: approve, revise, reject")
    ir_ref: str = Field(description="CAS hash of the evaluated IR")
