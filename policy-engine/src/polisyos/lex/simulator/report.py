from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from polisyos.core.contracts.lex import ComplianceIssue


class ComplianceTransition(str, Enum):
    PASS_TO_FAIL = "pass_to_fail"
    FAIL_TO_PASS = "fail_to_pass"
    NEW_ISSUE = "new_issue"
    RESOLVED_ISSUE = "resolved_issue"
    SEVERITY_CHANGE = "severity_change"
    UNCHANGED = "unchanged"


class ComplianceDelta(BaseModel):
    norm_id: str
    pass_id: str
    fingerprint: str
    transition: ComplianceTransition
    old_issue: ComplianceIssue | None = None
    new_issue: ComplianceIssue | None = None


class AffectedKPI(BaseModel):
    kpi_id: str
    description: str
    affected_norm_ids: list[str] = Field(default_factory=list)
    estimated_direction: str = "unknown"


class NormImpactReport(BaseModel):
    schema_version: str = "1.0"
    report_id: str
    old_pack_id: str
    new_pack_id: str
    jurisdiction: str

    norm_diff_ref: str | None = None
    norms_added: int = 0
    norms_removed: int = 0
    norms_modified: int = 0

    compliance_deltas: list[ComplianceDelta] = Field(default_factory=list)
    new_blockers: int = 0
    resolved_blockers: int = 0
    new_warnings: int = 0
    resolved_warnings: int = 0
    severity_changed: int = 0

    affected_kpis: list[AffectedKPI] = Field(default_factory=list)
    passes_executed: list[str] = Field(default_factory=list)

    decision_packet_ref: str | None = None
    cas_artifact_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @property
    def has_new_blockers(self) -> bool:
        return self.new_blockers > 0

