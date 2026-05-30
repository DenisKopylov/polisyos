"""Layer 2 S0 readiness contracts for the universal policy designer."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from polisyos.ir.kernel.base import ID_PATTERN, KernelModel

LAYER2_READINESS_SCHEMA_VERSION = "policyos.policy_design_case.layer2_readiness.v1"

Audience = Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]
AuthorityPosture = Literal["shadow", "advisory", "governed", "production"]
EpistemicRegime = Literal["risk", "uncertainty", "ambiguity", "ignorance", "contested_model"]
SourceAuthority = Literal[
    "deterministic_producer",
    "governed_config",
    "human_governance",
    "llm_candidate",
    "llm_critic",
    "llm_drafter",
]
FirewallDisposition = Literal["not_applicable", "pass", "warn", "limit", "block"]
CellMaturity = Literal["fail_closed", "predictive"]


class AuthorityBoundary(KernelModel):
    """Purpose-scoped authority boundary carried by Layer 2 records."""

    authoritative_for: list[str] = Field(..., min_length=1, max_length=20)
    may_not_use_for: list[str] = Field(..., min_length=1, max_length=20)
    source_authority: SourceAuthority
    posture: AuthorityPosture
    rule_version_refs: list[str] = Field(..., min_length=1, max_length=20)

    @model_validator(mode="after")
    def _validate_llm_firewall(self) -> AuthorityBoundary:
        if self.source_authority.startswith("llm_") and self.posture != "shadow":
            raise ValueError(f"{self.source_authority} cannot carry {self.posture} authority")
        return self


class ValueOfInformationEstimate(KernelModel):
    """Shared value-of-information currency consumed by downstream slices."""

    estimate_id: str = Field(..., pattern=ID_PATTERN)
    purpose: str = Field(..., min_length=1, max_length=200)
    budget_dimensions: list[str] = Field(..., min_length=1, max_length=10)
    used_by_sites: list[str] = Field(..., min_length=1, max_length=20)
    owner: str = Field(..., min_length=1, max_length=100)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class GovernanceDecisionClass(KernelModel):
    """Registry entry for a governance decision class."""

    decision_class_id: str = Field(..., pattern=ID_PATTERN)
    label: str = Field(..., min_length=1, max_length=120)
    required_role: str = Field(..., min_length=1, max_length=120)
    default_posture: AuthorityPosture
    high_stakes: bool
    authority_boundary: AuthorityBoundary


class AxisPositionDeclaration(KernelModel):
    """A declared position on a universal designer cluster axis."""

    cluster: str = Field(..., min_length=1, max_length=80)
    axis: str = Field(..., min_length=1, max_length=120)
    position: str = Field(..., min_length=1, max_length=200)
    evidence_refs: list[str] = Field(default_factory=list, max_length=40)
    authority_purpose: str = Field(..., min_length=1, max_length=200)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)

    @property
    def cell_ref(self) -> str:
        """Return the `CLUSTER.axis` reference."""

        return f"{self.cluster}.{self.axis}"


class AxisFirewallStatus(KernelModel):
    """Fail-closed or predictive firewall status for one axis."""

    cell_ref: str = Field(..., min_length=3, max_length=200)
    status: FirewallDisposition
    pattern_ids: list[str] = Field(default_factory=list, max_length=10)
    reason: str = Field(..., min_length=1, max_length=500)
    maturity: CellMaturity | None = None
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class CertifiedOperationEnvelope(KernelModel):
    """Certified operation envelope attached to a design record."""

    envelope_id: str = Field(..., pattern=ID_PATTERN)
    domains: list[str] = Field(..., min_length=1, max_length=20)
    posture_scopes: list[AuthorityPosture] = Field(..., min_length=1, max_length=4)
    epistemic_regime_scopes: list[EpistemicRegime] = Field(default_factory=list, max_length=20)
    actor_scopes: list[str] = Field(..., min_length=1, max_length=20)
    method_scopes: list[str] = Field(..., min_length=1, max_length=20)
    certified_for: list[str] = Field(..., min_length=1, max_length=20)
    not_certified_for: list[str] = Field(..., min_length=1, max_length=20)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class DesignRecordV0(KernelModel):
    """Minimal narrow-waist design record carried from S2 onward."""

    schema_version: str = LAYER2_READINESS_SCHEMA_VERSION
    record_id: str = Field(..., pattern=ID_PATTERN)
    candidate_ref: str = Field(..., min_length=1, max_length=300)
    candidate_source: SourceAuthority
    projection_status: AuthorityPosture
    authority_boundary: AuthorityBoundary
    axis_positions: list[AxisPositionDeclaration] = Field(default_factory=list, max_length=40)
    firewall_status: list[AxisFirewallStatus] = Field(default_factory=list, max_length=40)
    envelope: CertifiedOperationEnvelope
    ledger_refs: list[str] = Field(default_factory=list, max_length=40)
    projection_audiences: list[Audience] = Field(..., min_length=1, max_length=4)

    @model_validator(mode="after")
    def _validate_v0_authority(self) -> DesignRecordV0:
        if self.candidate_source.startswith("llm_") and self.projection_status != "shadow":
            raise ValueError(
                f"{self.candidate_source} cannot carry {self.projection_status} authority"
            )
        if self.projection_status == "production":
            raise ValueError("DesignRecordV0 cannot carry production authority")
        return self


class MinimalSeedManifest(KernelModel):
    """S0 manifest of algebra generators and launch budgets."""

    schema_version: str = LAYER2_READINESS_SCHEMA_VERSION
    manifest_id: str = Field(..., pattern=ID_PATTERN)
    facet_primitives: list[str] = Field(..., min_length=1, max_length=40)
    instrument_modality_primitives: list[str] = Field(..., min_length=1, max_length=40)
    projection_primitives: list[str] = Field(..., min_length=1, max_length=40)
    launch_firewalls: list[str] = Field(..., min_length=1, max_length=20)
    budgets: dict[str, str] = Field(..., min_length=1, max_length=20)
    principal_set_explore_exploit: str = Field(..., min_length=1, max_length=200)
    owned_by: str = Field(..., min_length=1, max_length=100)
    rule_version_refs: list[str] = Field(..., min_length=1, max_length=20)

    @model_validator(mode="after")
    def _validate_launch_firewalls(self) -> MinimalSeedManifest:
        required = {"P15", "P25"}
        if not required <= set(self.launch_firewalls):
            raise ValueError("launch_firewalls must include P15 and P25")
        return self
