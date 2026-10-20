"""Expose governance decision payloads emitted by Scientist validation stages.

This module is the boundary contract between workflow nodes, governance passes,
and downstream consumers that need a verdict plus links to persisted decision
artifacts. The models are intentionally compact so node-level reports and
calibration-specific reports can be normalized into the same public envelope.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactStore,
    CoreArtifactOwnerProfile,
    validate_owned_core_model_json_artifact,
)
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
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
    claims_ref: ArtifactRef | None = None
    human_review_packet_ref: ArtifactRef | None = None
    human_review_decision_ref: ArtifactRef | None = None
    continuous_governance_report_ref: ArtifactRef | None = None
    reissue_packet_ref: ArtifactRef | None = None
    withdrawal_record_ref: ArtifactRef | None = None


class GovernanceReportInvocationBinding(BaseModel):
    """Engine-owned source identity for one governance report emission.

    This binding is only a lookup handle. Consumers must resolve it through the
    run owner chain, the successful invocation completion, and the current source
    projection before using the verdict as current.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1)
    attempt_id: str = Field(
        pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    attempt_basis_ref: ArtifactRef
    workflow_spec_ref: ArtifactRef
    input_state_ref: ArtifactRef
    node_alias: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    component_id: str = Field(min_length=1)
    source_basis_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _require_selected_profiles(self) -> GovernanceReportInvocationBinding:
        """Require every producer-chain edge to preserve its selected profile."""
        refs = (self.attempt_basis_ref, self.workflow_spec_ref, self.input_state_ref)
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("governance_report_invocation_profile_not_established")
        return self


class GovernanceReport(BaseModel):
    """Serializable governance verdict and supporting diagnostics.

    The object is produced by governance-aware nodes and runners once validation
    passes finish. `verdict` carries the final control decision, `issues`
    captures pass findings, and `links` points at persisted review artifacts
    that callers can dereference when rendering decision traces.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "2.0"] = "1.0"
    verdict: Literal["approve", "needs_revision", "reject", "human_gate"]
    invocation_binding: GovernanceReportInvocationBinding | None = None
    issues: list[dict[str, Any]] = Field(default_factory=list)
    links: GovernanceReportLinks = Field(default_factory=GovernanceReportLinks)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _bind_schema_to_invocation(self) -> GovernanceReport:
        """Keep historical v1 reports readable and require binding for v2."""
        if (self.schema_version == "1.0") != (self.invocation_binding is None):
            raise ValueError("governance_report_invocation_schema_mismatch")
        return self


GOVERNANCE_REPORT_OWNER_PROFILE = CoreArtifactOwnerProfile(
    kind="scientist.governance_report",
    media_type="application/json",
    schema_variants=(
        SchemaInfo(name="polisyos.scientist.GovernanceReport", version="1.0"),
        SchemaInfo(name="polisyos.scientist.GovernanceReport", version="2.0"),
    ),
    payload_schema_version_by_manifest=(
        (("polisyos.scientist.GovernanceReport", "1.0"), "1.0"),
        (("polisyos.scientist.GovernanceReport", "2.0"), "2.0"),
    ),
)


def load_governance_report_artifact(
    store: ArtifactStore,
    selector: ArtifactRef,
) -> GovernanceReport:
    """Read a governance report only through its producer-owned versioned ABI.

    The selected manifest and payload must match the finite producer profile above.
    A backend that cannot expose the selected raw manifest is refused by the shared
    owner validator. This confirms content and ABI conformity; it does not establish
    who produced the bytes or grant governance authority to the report.
    """
    return validate_owned_core_model_json_artifact(
        GovernanceReport,
        store,
        selector,
        expected_owner=GOVERNANCE_REPORT_OWNER_PROFILE,
    ).value


__all__ = [
    "GOVERNANCE_REPORT_OWNER_PROFILE",
    "GovernanceReport",
    "GovernanceReportLinks",
    "GovernanceReportInvocationBinding",
    "load_governance_report_artifact",
]
