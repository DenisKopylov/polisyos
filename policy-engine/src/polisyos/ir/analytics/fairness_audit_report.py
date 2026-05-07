"""Machine-readable fairness audit report contract for validation-stage gates."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.references import FairnessAuditReportRef

FairnessAuditStatus = Literal[
    "PASS",
    "WARN",
    "REFUSE",
    "NOT_COMPUTABLE",
    "NOT_APPLICABLE",
]

FairnessCheckStatus = Literal[
    "PASS",
    "WARN",
    "FAIL",
    "INSUFFICIENT_N",
    "NOT_COMPUTABLE",
    "NOT_APPLICABLE",
]


class FairnessAuditReport(BaseModel):
    """Validation-stage fairness audit consumed by deployment and runtime gates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str = "1.0.0"
    kind: Literal["scientist.fairness_audit_report"] = "scientist.fairness_audit_report"
    status: FairnessAuditStatus
    deployable: bool
    auto_decision_allowed: bool
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    model_id: str | None = None
    dataset_id: str | None = None
    audit_id: str
    config: dict[str, object] = Field(default_factory=dict)
    input_summary: dict[str, object] = Field(default_factory=dict)
    group_metrics: list[dict[str, object]] = Field(default_factory=list)
    parity_tests: list[dict[str, object]] = Field(default_factory=list)
    causal_audits: dict[str, object] = Field(default_factory=dict)
    diagnostics: list[dict[str, object]] = Field(default_factory=list)
    refusal_policy: dict[str, object] = Field(default_factory=dict)
    required_actions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    artifacts: dict[str, object] = Field(default_factory=dict)

    def to_validation_report_payload(self) -> dict[str, object]:
        """Return the payload shape embedded as ``ValidationReport.fairness_audit``."""

        return self.model_dump(mode="json", exclude={"kind"})


def persist_fairness_audit_report(
    store: ArtifactStore,
    report: FairnessAuditReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "polisyos.scientist.fairness_audit_report",
    schema_version: str = "1.0",
) -> FairnessAuditReportRef:
    """Persist a fairness audit report and return its typed CAS reference."""

    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind="scientist.fairness_audit_report",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return FairnessAuditReportRef.model_validate(ref)


def load_fairness_audit_report(
    store: ArtifactStore,
    ref: FairnessAuditReportRef,
) -> FairnessAuditReport:
    """Load a persisted fairness audit report from CAS."""

    payload = get_json_artifact(store, ref.artifact_id)
    return FairnessAuditReport.model_validate(payload)


__all__ = [
    "FairnessAuditReport",
    "FairnessAuditReportRef",
    "FairnessAuditStatus",
    "FairnessCheckStatus",
    "load_fairness_audit_report",
    "persist_fairness_audit_report",
]
