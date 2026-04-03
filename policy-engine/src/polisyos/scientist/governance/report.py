"""Public governance report module API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.contracts.lex import ChangeProposalRef, LegalReportRef
from polisyos.core.contracts.scientist import (
    SourceVerificationReportRef,
    VerifiedPolicyReportRef,
)


class GovernanceReportLinks(BaseModel):
    """Governance report links public type."""
    model_config = ConfigDict(extra="forbid")

    legal_report_ref: LegalReportRef | None = None
    change_proposal_ref: ChangeProposalRef | None = None
    source_verification_report_ref: SourceVerificationReportRef | None = None
    verified_policy_report_ref: VerifiedPolicyReportRef | None = None


class GovernanceReport(BaseModel):
    """Scientist governance outcome payload (E1.7)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    verdict: Literal["approve", "needs_revision", "reject", "human_gate"]
    issues: list[dict[str, Any]] = Field(default_factory=list)
    links: GovernanceReportLinks = Field(default_factory=GovernanceReportLinks)
    notes: list[str] = Field(default_factory=list)


__all__ = ["GovernanceReport", "GovernanceReportLinks"]
