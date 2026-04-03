"""Expose governance decision payloads emitted by Scientist validation stages.

This module is the boundary contract between workflow nodes, governance passes,
and downstream consumers that need a verdict plus links to persisted decision
artifacts. The models are intentionally compact so node-level reports and
calibration-specific reports can be normalized into the same public envelope.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.contracts.lex import ChangeProposalRef, LegalReportRef
from polisyos.core.contracts.scientist import (
    SourceVerificationReportRef,
    VerifiedPolicyReportRef,
)


class GovernanceReportLinks(BaseModel):
    """Reference bundle for optional governance artifacts attached to a verdict.

    The fields stay optional because different workflows materialize different
    evidence artifacts. For example, Lex-focused governance can attach legal and
    change-proposal refs, while Scientist calibration attaches verified-policy
    and source-verification refs when those reports exist.
    """
    model_config = ConfigDict(extra="forbid")

    legal_report_ref: LegalReportRef | None = None
    change_proposal_ref: ChangeProposalRef | None = None
    source_verification_report_ref: SourceVerificationReportRef | None = None
    verified_policy_report_ref: VerifiedPolicyReportRef | None = None


class GovernanceReport(BaseModel):
    """Serializable governance verdict and supporting diagnostics.

    The object is produced by governance-aware nodes and runners once validation
    passes finish. `verdict` carries the final control decision, `issues`
    captures pass findings, and `links` points at persisted review artifacts
    that callers can dereference when rendering decision traces.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    verdict: Literal["approve", "needs_revision", "reject", "human_gate"]
    issues: list[dict[str, Any]] = Field(default_factory=list)
    links: GovernanceReportLinks = Field(default_factory=GovernanceReportLinks)
    notes: list[str] = Field(default_factory=list)


__all__ = ["GovernanceReport", "GovernanceReportLinks"]
