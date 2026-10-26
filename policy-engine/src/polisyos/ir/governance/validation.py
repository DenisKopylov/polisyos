"""Validation-report contracts used when IR payload repair or schema checks fail."""

from __future__ import annotations

import difflib
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.ir.artifacts import ArtifactStore, InputRef  # noqa: TC001
from polisyos.ir.artifacts.contracts import ArtifactOwnerDeclaration, CanonInfo
from polisyos.ir.artifacts.io import _get_owned_json_artifact, _put_owned_json_artifact
from polisyos.ir.migrations.base import (
    CompatibilityMode,
    IRRepresentationRegistration,
    ResolvedSchemaAdmission,
    register_ir_representation,
    register_schema_version,
)
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ValidationReportRef

if TYPE_CHECKING:
    from collections.abc import Iterable


class ValidationIssue(BaseModel):
    """Represent one normalized validation failure that governance/reporting can persist."""

    loc: list[str | int]
    message: str
    error_type: str
    input_value: Any | None = None
    path: str | None = None
    code: str | None = None
    expected: Any | None = None
    actual: Any | None = None
    severity: str | None = None
    model_config = ConfigDict(extra="forbid")


Phase5ComponentStatus = Literal["pass", "warn", "fail", "blocked", "not_applicable", "not_run"]
Phase5ValidationVerdict = Literal["pass", "warn", "fail", "blocked"]
Phase5Readiness = Literal["ready", "monitor", "restricted", "blocked"]


class Phase5GateComponent(BaseModel):
    """One Phase-5 gate component projected into the additive ValidationReport v2 surface."""

    name: str
    status: Phase5ComponentStatus
    required: bool = True
    evidence_refs: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: str | None = None
    model_config = ConfigDict(extra="forbid")


class Phase5GateWaiver(BaseModel):
    """Explicit waiver for a Phase-5 gate component."""

    component: str
    reason: str
    approver: str
    expires_at: str
    evidence_refs: list[str] = Field(default_factory=list)
    model_config = ConfigDict(extra="forbid")


class ValidationReport(BaseModel):
    """Bundle issue summaries, optional repair notes, and diffs for a failed validation pass."""

    contract_id: ClassVar[str] = "scientist.validation_report.v2"

    schema_version: str = "2.0"
    error_summary: str
    issues: list[ValidationIssue]
    fairness_audit: dict[str, Any] | None = None
    repair_attempt: str | None = None
    diff_before_after: str | None = None
    normalized_payload: dict[str, Any] | None = None
    verdict: Phase5ValidationVerdict = "pass"
    readiness: Phase5Readiness = "ready"
    artifact_ref: str | None = None
    artifact_kind: str | None = None
    phase5_components: list[Phase5GateComponent] = Field(default_factory=list)
    gate_failures: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    judge_verdict_ref: str | None = None
    advisor_consensus: dict[str, Any] | None = None
    waivers: list[Phase5GateWaiver] = Field(default_factory=list)
    generated_for: str | None = None
    generated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    model_config = ConfigDict(extra="forbid")


def _json_dump(payload: object) -> list[str]:
    text = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)
    return text.splitlines()


def diff_payloads(before: object, after: object) -> str:
    """Render a unified diff so repair loops can compare pre- and post-validation payloads."""
    before_lines = _json_dump(before)
    after_lines = _json_dump(after)
    diff = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile="before",
        tofile="after",
        lineterm="",
    )
    return "\n".join(diff)


def issues_from_validation_error(error: ValidationError) -> list[ValidationIssue]:
    """Convert a Pydantic ``ValidationError`` into stable ``ValidationIssue`` records."""
    issues: list[ValidationIssue] = []
    for entry in error.errors():
        loc = list(entry.get("loc", ()))
        issues.append(
            ValidationIssue(
                loc=loc,
                message=entry.get("msg", ""),
                error_type=entry.get("type", ""),
                input_value=entry.get("input"),
                path=".".join(str(part) for part in loc),
                code=entry.get("type", ""),
                actual=entry.get("input"),
                severity="error",
            )
        )
    return issues


def summarize_issues(issues: Iterable[ValidationIssue]) -> str:
    """Collapse the first few validation issues into a short operator-facing summary."""
    issues_list = list(issues)
    if not issues_list:
        return "No validation issues."
    lines = [f"{len(issues_list)} validation issue(s)."]
    for issue in issues_list[:5]:
        loc = ".".join(str(part) for part in issue.loc) or "<root>"
        lines.append(f"{loc}: {issue.message}")
    return " ".join(lines)


def build_validation_report(
    error: ValidationError,
    *,
    before: object | None = None,
    after: object | None = None,
    repair_attempt: str | None = None,
) -> ValidationReport:
    """Build validation report."""
    issues = issues_from_validation_error(error)
    diff_text = None
    if before is not None or after is not None:
        diff_text = diff_payloads(before or {}, after or {})
    return ValidationReport(
        error_summary=summarize_issues(issues),
        issues=issues,
        verdict="fail" if issues else "pass",
        readiness="blocked" if issues else "ready",
        repair_attempt=repair_attempt,
        diff_before_after=diff_text,
    )


_OWNER_SCHEMA_NAME = "polisyos.scientist.validation_report"
_OWNER_SCHEMA_VERSION = "2.0"
_OWNER_WIRE_POLICY = ("ir.owner.validationreport.wire", "1")


def _owner_payload_version(payload: object) -> str:
    """Require an embedded source version; a DTO default is not historical evidence."""
    if not isinstance(payload, dict):
        raise TypeError("Owned ValidationReport payload must be a JSON object")
    version = payload.get("schema_version")
    if type(version) is not str or not version.strip():
        raise ValueError("Owned ValidationReport payload requires an explicit schema_version")
    return version


def _validate_owner_source(payload: object, admission: ResolvedSchemaAdmission) -> ValidationReport:
    """Validate bytes only under this owner exact registered source representation."""
    registration = admission.source_registration
    if registration.schema_name != _OWNER_SCHEMA_NAME:
        raise ValueError("Owned ValidationReport source has the wrong schema name")
    if registration.payload_version != _owner_payload_version(payload):
        raise ValueError("Owned ValidationReport payload version disagrees with its representation")
    return ValidationReport.model_validate(payload)


def _project_owner_source(
    source: ValidationReport,
    admission: ResolvedSchemaAdmission,
) -> ValidationReport:
    """Preserve the validated source value when no semantic projection is declared."""
    if not isinstance(source, ValidationReport):
        raise TypeError("Owned ValidationReport source was not validated by its owner")
    if admission.source_registration.payload_version != source.schema_version:
        raise ValueError("Owned ValidationReport projection would change the source version")
    return source


def _validate_owner_profile(
    profile: CanonInfo,
    registration: IRRepresentationRegistration,
) -> bool:
    """Accept only the canonical profile used by this family real writer."""
    expected = CanonInfo.from_spec(CanonSpec(forbid_floats=False))
    return registration.profile_ref is None and profile == expected


_validationreport_owner = ArtifactOwnerDeclaration(
    contract_id="scientist.validation_report.v2",
    dto_fqn="polisyos.ir.governance.validation.ValidationReport",
    abi_key="polisyos.scientist.validation_report",
    registry_key="polisyos.scientist.validation_report",
    kind="scientist.validation_report",
    media_type="application/json",
    purpose="scientist.validation_report.typed_consumer",
    policy_revision="scientist.validation_report.v2.owner-admission.v1",
    accepted_wire_policies=(_OWNER_WIRE_POLICY,),
    payload_version_of=_owner_payload_version,
    validate_source=_validate_owner_source,
    project_for_consumer=_project_owner_source,
    validate_profile=_validate_owner_profile,
)


register_schema_version(
    _OWNER_SCHEMA_NAME,
    _OWNER_SCHEMA_VERSION,
    compatibility=CompatibilityMode.NONE,
    notes=(
        (
            "ValidationReport current owner-admitted representati"
            "on; historical predecessors are not registered."
        ),
    ),
)
register_ir_representation(
    registry_key=_validationreport_owner.registry_key,
    owner_ref=_validationreport_owner.contract_id,
    dto_abi=_validationreport_owner.dto_fqn,
    wire_policy_ref=_OWNER_WIRE_POLICY[0],
    wire_policy_revision=_OWNER_WIRE_POLICY[1],
    schema_name=_OWNER_SCHEMA_NAME,
    schema_version=_OWNER_SCHEMA_VERSION,
    payload_version=_OWNER_SCHEMA_VERSION,
    profile_ref=None,
    readable=True,
    writable=True,
    current=True,
    default_write=True,
)


def persist_validation_report(
    store: ArtifactStore,
    report: ValidationReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "polisyos.scientist.validation_report",
    schema_version: str = "2.0",
) -> ValidationReportRef:
    """Persist a source-validated ValidationReport under its exact owned representation."""
    selected = _put_owned_json_artifact(
        store,
        report.model_dump(mode="json"),
        owner=_validationreport_owner,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ValidationReportRef.model_validate(selected)


def load_validation_report(store: ArtifactStore, ref: ValidationReportRef) -> ValidationReport:
    """Read ValidationReport only after its trusted owner admits the stored representation."""
    return _get_owned_json_artifact(store, ref, owner=_validationreport_owner)
