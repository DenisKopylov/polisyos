"""Status envelope and deficit crosswalk for runtime quality readers.

The envelope intentionally preserves producer-local statuses. The shared fields
below are composition axes for readers such as scorecard, approval, public
export, and closeout; they are not a replacement status enum for producers.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

STATUS_ENVELOPE_SCHEMA_VERSION = "policyos.runtime.status_envelope.v1"
DEFICIT_CROSSWALK_SCHEMA_VERSION = "policyos.runtime.deficit_crosswalk.v1"


class SharedSeverity(StrEnum):
    """Reader-facing severity axis for composed status effects."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Blockingness(StrEnum):
    """Reader-facing blocking axis that does not replace local statuses."""

    NON_BLOCKING = "non_blocking"
    REVIEW_BLOCKING = "review_blocking"
    CLOSEOUT_BLOCKING = "closeout_blocking"
    HARD_BLOCKING = "hard_blocking"


class PublicationEffect(StrEnum):
    """How a status or deficit constrains publication."""

    UNAFFECTED = "unaffected"
    INTERNAL_ONLY = "internal_only"
    PUBLISH_WITH_LIMITATION = "publish_with_limitation"
    REVIEW_BEFORE_PUBLICATION = "review_before_publication"
    REISSUE_REQUIRED = "reissue_required"
    PUBLICATION_BLOCKED = "publication_blocked"


class ReviewAction(StrEnum):
    """Review or repair action implied by the composed axes."""

    NONE = "none"
    HUMAN_REVIEW = "human_review"
    EXPERT_REVIEW = "expert_review"
    REISSUE = "reissue"
    HARD_BLOCK = "hard_block"


class CloseoutEffect(StrEnum):
    """Closeout effect implied by status composition."""

    CLOSEOUT_ALLOWED = "closeout_allowed"
    ACCEPTED_DEFICIT = "accepted_deficit"
    LIMITED_CLOSEOUT = "limited_closeout"
    REVIEW_REQUIRED = "review_required"
    REISSUE_REQUIRED = "reissue_required"
    CLOSEOUT_BLOCKED = "closeout_blocked"


class DeficitDisposition(StrEnum):
    """Authority-aware deficit disposition, distinct from local producer status."""

    ACCEPTED_DEFICIT = "accepted_deficit"
    PUBLISH_WITH_LIMITATION = "publish_with_limitation"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    EXPERT_REVIEW_REQUIRED = "expert_review_required"
    REISSUE_REQUIRED = "reissue_required"
    HARD_BLOCK = "hard_block"


@dataclass(frozen=True, slots=True)
class _AxisSpec:
    severity: SharedSeverity
    blockingness: Blockingness
    publication_effect: PublicationEffect
    review_action: ReviewAction
    closeout_effect: CloseoutEffect


_SEVERITY_ORDER = {
    SharedSeverity.INFO: 0,
    SharedSeverity.WARNING: 1,
    SharedSeverity.ERROR: 2,
    SharedSeverity.CRITICAL: 3,
}
_BLOCKING_ORDER = {
    Blockingness.NON_BLOCKING: 0,
    Blockingness.REVIEW_BLOCKING: 1,
    Blockingness.CLOSEOUT_BLOCKING: 2,
    Blockingness.HARD_BLOCKING: 3,
}
_PUBLICATION_ORDER = {
    PublicationEffect.UNAFFECTED: 0,
    PublicationEffect.PUBLISH_WITH_LIMITATION: 1,
    PublicationEffect.INTERNAL_ONLY: 2,
    PublicationEffect.REVIEW_BEFORE_PUBLICATION: 3,
    PublicationEffect.REISSUE_REQUIRED: 4,
    PublicationEffect.PUBLICATION_BLOCKED: 5,
}
_REVIEW_ORDER = {
    ReviewAction.NONE: 0,
    ReviewAction.HUMAN_REVIEW: 1,
    ReviewAction.EXPERT_REVIEW: 2,
    ReviewAction.REISSUE: 3,
    ReviewAction.HARD_BLOCK: 4,
}
_CLOSEOUT_ORDER = {
    CloseoutEffect.CLOSEOUT_ALLOWED: 0,
    CloseoutEffect.ACCEPTED_DEFICIT: 1,
    CloseoutEffect.LIMITED_CLOSEOUT: 2,
    CloseoutEffect.REVIEW_REQUIRED: 3,
    CloseoutEffect.REISSUE_REQUIRED: 4,
    CloseoutEffect.CLOSEOUT_BLOCKED: 5,
}

_PASS = _AxisSpec(
    SharedSeverity.INFO,
    Blockingness.NON_BLOCKING,
    PublicationEffect.UNAFFECTED,
    ReviewAction.NONE,
    CloseoutEffect.CLOSEOUT_ALLOWED,
)
_LIMITED = _AxisSpec(
    SharedSeverity.WARNING,
    Blockingness.NON_BLOCKING,
    PublicationEffect.PUBLISH_WITH_LIMITATION,
    ReviewAction.NONE,
    CloseoutEffect.LIMITED_CLOSEOUT,
)
_INTERNAL_ONLY = _AxisSpec(
    SharedSeverity.WARNING,
    Blockingness.NON_BLOCKING,
    PublicationEffect.INTERNAL_ONLY,
    ReviewAction.NONE,
    CloseoutEffect.ACCEPTED_DEFICIT,
)
_REVIEW = _AxisSpec(
    SharedSeverity.ERROR,
    Blockingness.REVIEW_BLOCKING,
    PublicationEffect.REVIEW_BEFORE_PUBLICATION,
    ReviewAction.HUMAN_REVIEW,
    CloseoutEffect.REVIEW_REQUIRED,
)
_EXPERT_REVIEW = _AxisSpec(
    SharedSeverity.ERROR,
    Blockingness.REVIEW_BLOCKING,
    PublicationEffect.REVIEW_BEFORE_PUBLICATION,
    ReviewAction.EXPERT_REVIEW,
    CloseoutEffect.REVIEW_REQUIRED,
)
_REISSUE = _AxisSpec(
    SharedSeverity.ERROR,
    Blockingness.CLOSEOUT_BLOCKING,
    PublicationEffect.REISSUE_REQUIRED,
    ReviewAction.REISSUE,
    CloseoutEffect.REISSUE_REQUIRED,
)
_HARD_BLOCK = _AxisSpec(
    SharedSeverity.CRITICAL,
    Blockingness.HARD_BLOCKING,
    PublicationEffect.PUBLICATION_BLOCKED,
    ReviewAction.HARD_BLOCK,
    CloseoutEffect.CLOSEOUT_BLOCKED,
)

_STATUS_CROSSWALK: Mapping[tuple[str, str], _AxisSpec] = {
    ("claim_support", "strong"): _PASS,
    ("claim_support", "supported"): _PASS,
    ("claim_support", "weak"): _LIMITED,
    ("claim_support", "unsupported"): _HARD_BLOCK,
    ("claim_publishability", "publishable"): _PASS,
    ("claim_publishability", "publish_with_limitation"): _LIMITED,
    ("claim_publishability", "review_required"): _REVIEW,
    ("claim_publishability", "blocked"): _HARD_BLOCK,
    ("citation_faithfulness", "supports"): _PASS,
    ("citation_faithfulness", "partially_supports"): _LIMITED,
    ("citation_faithfulness", "scope_limited"): _LIMITED,
    ("citation_faithfulness", "contradicts"): _HARD_BLOCK,
    ("citation_faithfulness", "irrelevant"): _HARD_BLOCK,
    ("citation_faithfulness", "fabricated"): _HARD_BLOCK,
    ("citation_faithfulness", "unverifiable"): _HARD_BLOCK,
    ("semantic_binding", "pass"): _PASS,
    ("semantic_binding", "warn"): _REVIEW,
    ("semantic_binding", "degraded"): _REVIEW,
    ("semantic_binding", "blocked"): _HARD_BLOCK,
    ("semantic_binding", "fail"): _HARD_BLOCK,
    ("approval", "approval_ready"): _PASS,
    ("approval", "quality_warn"): _REVIEW,
    ("approval", "override_required"): _REVIEW,
    ("approval", "quality_failed"): _HARD_BLOCK,
    ("approval", "execution_failed"): _HARD_BLOCK,
    ("readiness", "deployment_ready"): _PASS,
    ("readiness", "recommendation_ready"): _PASS,
    ("readiness", "simulation_ready"): _LIMITED,
    ("readiness", "external_briefing"): _LIMITED,
    ("readiness", "analyst_advisory"): _INTERNAL_ONLY,
    ("readiness", "research_artifact"): _INTERNAL_ONLY,
    ("readiness", "blocked"): _HARD_BLOCK,
    ("proof_composability", "reusable"): _PASS,
    ("proof_composability", "revalidate"): _REVIEW,
    ("proof_composability", "rederive"): _REISSUE,
    ("proof_composability", "unknown"): _REVIEW,
    ("transportability", "identified"): _PASS,
    ("transportability", "partially_identified"): _LIMITED,
    ("transportability", "bounded_non_identified"): _REVIEW,
    ("transportability", "unsupported"): _HARD_BLOCK,
    ("decision_validity", "valid"): _PASS,
    ("decision_validity", "current"): _PASS,
    ("decision_validity", "pass"): _PASS,
    ("decision_validity", "warning"): _REVIEW,
    ("decision_validity", "review_required"): _REVIEW,
    ("decision_validity", "stale"): _REISSUE,
    ("decision_validity", "reissue_required"): _REISSUE,
    ("decision_validity", "superseded"): _REISSUE,
    ("decision_validity", "withdrawn"): _HARD_BLOCK,
    ("decision_validity", "invalid"): _HARD_BLOCK,
    ("scorecard", "pass"): _PASS,
    ("scorecard", "warn"): _REVIEW,
    ("scorecard", "fail"): _HARD_BLOCK,
}

_DEFICIT_AXIS: Mapping[DeficitDisposition, _AxisSpec] = {
    DeficitDisposition.ACCEPTED_DEFICIT: _INTERNAL_ONLY,
    DeficitDisposition.PUBLISH_WITH_LIMITATION: _LIMITED,
    DeficitDisposition.HUMAN_REVIEW_REQUIRED: _REVIEW,
    DeficitDisposition.EXPERT_REVIEW_REQUIRED: _EXPERT_REVIEW,
    DeficitDisposition.REISSUE_REQUIRED: _REISSUE,
    DeficitDisposition.HARD_BLOCK: _HARD_BLOCK,
}


class DeficitRecord(BaseModel):
    """Normalized C31 deficit record consumed by status readers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = DEFICIT_CROSSWALK_SCHEMA_VERSION
    deficit_id: str = Field(min_length=1)
    deficit_family: str = Field(min_length=1)
    deficit_code: str = Field(min_length=1)
    claim_ids: tuple[str, ...] = Field(default=())
    authority_level: str = Field(min_length=1)
    audience_scope: str = Field(min_length=1)
    disposition: DeficitDisposition
    support_cap: str | None = None
    readiness_cap: str | None = None
    max_audience: str | None = None
    owner: str = Field(min_length=1)
    ttl_expires_at: datetime
    runtime_event_ref: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)
    public_limitation_note: str | None = None
    review_refs: tuple[str, ...] = Field(default=())

    @model_validator(mode="before")
    @classmethod
    def _normalize_aliases(cls, payload: object) -> object:
        if not isinstance(payload, Mapping):
            return payload
        data = dict(payload)
        data["deficit_family"] = (
            data.get("deficit_family") or data.get("family") or data.get("kind")
        )
        data["deficit_code"] = (
            data.get("deficit_code") or data.get("code") or data.get("policy_code")
        )
        data["disposition"] = data.get("disposition") or data.get("decision")
        data["ttl_expires_at"] = data.get("ttl_expires_at") or data.get("expires_at")
        data.pop("expires_at", None)
        data["claim_ids"] = _claim_ids(data)
        return data

    @field_validator(
        "deficit_id",
        "deficit_family",
        "deficit_code",
        "authority_level",
        "audience_scope",
        "owner",
        "runtime_event_ref",
        "evidence_ref",
    )
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("support_cap", "readiness_cap", "max_audience", "public_limitation_note")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("claim_ids", "review_refs")
    @classmethod
    def _strip_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _text_tuple(values)


class StatusEnvelopeEntry(BaseModel):
    """One local producer status enriched with shared reader axes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_id: str = Field(min_length=1)
    producer: str = Field(min_length=1)
    status_family: str = Field(min_length=1)
    local_status: str = Field(min_length=1)
    severity: SharedSeverity
    blockingness: Blockingness
    publication_effect: PublicationEffect
    review_action: ReviewAction
    closeout_effect: CloseoutEffect
    owner: str | None = None
    ttl_expires_at: datetime | None = None
    ttl_state: Literal["active", "expired", "missing"] = "missing"
    message: str | None = None
    next_action: str | None = None
    evidence_ref: str | None = None
    claim_ids: tuple[str, ...] = Field(default=())
    deficit_id: str | None = None
    deficit_family: str | None = None
    deficit_disposition: DeficitDisposition | None = None

    @field_validator("entry_id", "producer", "status_family", "local_status")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator(
        "owner",
        "message",
        "next_action",
        "evidence_ref",
        "deficit_id",
        "deficit_family",
    )
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("claim_ids")
    @classmethod
    def _strip_claim_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _text_tuple(values)


class StatusLifecycleIssue(BaseModel):
    """Owned-warning lifecycle issue emitted when a status lacks P09 metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    entry_id: str = Field(min_length=1)
    status_family: str = Field(min_length=1)
    local_status: str = Field(min_length=1)
    message: str = Field(min_length=1)
    next_action: str = Field(min_length=1)
    evidence_ref: str | None = None

    @field_validator("code", "entry_id", "status_family", "local_status", "message", "next_action")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("evidence_ref")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)


class DeficitCrosswalkRow(BaseModel):
    """One deficit row crosswalked to shared reader effects."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = DEFICIT_CROSSWALK_SCHEMA_VERSION
    deficit_id: str = Field(min_length=1)
    status_entry_id: str = Field(min_length=1)
    deficit_family: str = Field(min_length=1)
    deficit_code: str = Field(min_length=1)
    claim_ids: tuple[str, ...] = Field(default=())
    authority_level: str = Field(min_length=1)
    audience_scope: str = Field(min_length=1)
    disposition: DeficitDisposition
    severity: SharedSeverity
    blockingness: Blockingness
    publication_effect: PublicationEffect
    review_action: ReviewAction
    closeout_effect: CloseoutEffect
    support_cap: str | None = None
    readiness_cap: str | None = None
    max_audience: str | None = None
    owner: str = Field(min_length=1)
    ttl_expires_at: datetime
    runtime_event_ref: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)
    public_limitation_note: str | None = None
    review_refs: tuple[str, ...] = Field(default=())


class StatusEnvelopeSummary(BaseModel):
    """Aggregate status effects across local statuses and deficits."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_count: int = Field(ge=0)
    deficit_count: int = Field(ge=0)
    max_severity: SharedSeverity
    max_blockingness: Blockingness
    publication_effect: PublicationEffect
    review_action: ReviewAction
    closeout_effect: CloseoutEffect
    owners: tuple[str, ...] = Field(default=())
    ttl_expires_at: datetime | None = None
    blocking_entry_ids: tuple[str, ...] = Field(default=())
    reasons: tuple[str, ...] = Field(default=())


class StatusEnvelope(BaseModel):
    """Composed status envelope for runtime quality readers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = STATUS_ENVELOPE_SCHEMA_VERSION
    generated_at: datetime
    entries: tuple[StatusEnvelopeEntry, ...] = Field(default=())
    deficit_crosswalk: tuple[DeficitCrosswalkRow, ...] = Field(default=())
    lifecycle_issues: tuple[StatusLifecycleIssue, ...] = Field(default=())
    summary: StatusEnvelopeSummary


def build_status_envelope(
    *,
    local_statuses: Iterable[Mapping[str, Any]],
    deficits: Iterable[Mapping[str, Any]],
    now: datetime | None = None,
) -> StatusEnvelope:
    """Build a status envelope while preserving all local producer statuses."""

    generated_at = _utc(now)
    entries: list[StatusEnvelopeEntry] = []
    crosswalk: list[DeficitCrosswalkRow] = []
    lifecycle_issues: list[StatusLifecycleIssue] = []

    for index, raw_status in enumerate(local_statuses):
        entry, issues = _entry_from_local_status(raw_status, index=index, now=generated_at)
        entries.append(entry)
        lifecycle_issues.extend(issues)

    for index, raw_deficit in enumerate(deficits):
        record = DeficitRecord.model_validate(raw_deficit)
        entry = _entry_from_deficit(record, index=index, now=generated_at)
        entries.append(entry)
        row = _crosswalk_row(record, entry)
        crosswalk.append(row)
        lifecycle_issues.extend(_lifecycle_issues(entry, now=generated_at))

    summary = _summary(entries, crosswalk, lifecycle_issues)
    return StatusEnvelope(
        generated_at=generated_at,
        entries=tuple(entries),
        deficit_crosswalk=tuple(crosswalk),
        lifecycle_issues=tuple(lifecycle_issues),
        summary=summary,
    )


def status_envelope_scorecard_gates(envelope: StatusEnvelope) -> list[dict[str, Any]]:
    """Project status envelope effects into scorecard-readable gates."""

    gates: list[dict[str, Any]] = []
    lifecycle_entry_ids = {issue.entry_id for issue in envelope.lifecycle_issues}
    for issue in envelope.lifecycle_issues:
        gates.append(
            {
                "name": issue.code,
                "stage": "ops",
                "code": issue.code,
                "status": "fail",
                "layer": "status_envelope",
                "phase": "warning_lifecycle",
                "message": issue.message,
                "evidence_ref": issue.evidence_ref,
                "next_action": issue.next_action,
                "blocking": True,
                "blockingness": Blockingness.HARD_BLOCKING.value,
                "publication_effect": PublicationEffect.PUBLICATION_BLOCKED.value,
                "review_action": ReviewAction.HUMAN_REVIEW.value,
                "closeout_effect": CloseoutEffect.CLOSEOUT_BLOCKED.value,
            }
        )
    if envelope.lifecycle_issues:
        gates.append(
            {
                "name": "status_crosswalk_lifecycle_blocker",
                "stage": "ops",
                "code": "status_crosswalk_lifecycle_blocker",
                "status": "fail",
                "layer": "status_envelope",
                "phase": "warning_lifecycle",
                "message": "Status envelope contains warning lifecycle issues.",
                "evidence_ref": "status_envelope",
                "next_action": "Attach owner and TTL metadata or resolve the warning status.",
                "blocking": True,
                "blockingness": Blockingness.HARD_BLOCKING.value,
                "publication_effect": PublicationEffect.PUBLICATION_BLOCKED.value,
                "review_action": ReviewAction.HUMAN_REVIEW.value,
                "closeout_effect": CloseoutEffect.CLOSEOUT_BLOCKED.value,
            }
        )
    for row in envelope.deficit_crosswalk:
        gates.append(_deficit_gate(row))
    for entry in envelope.entries:
        if entry.deficit_id is not None or entry.entry_id in lifecycle_entry_ids:
            continue
        gate = _local_status_gate(entry)
        if gate is not None:
            gates.append(gate)
    return gates


def status_envelope_payload(envelope: StatusEnvelope) -> dict[str, Any]:
    """Return JSON-compatible status envelope payload."""

    return envelope.model_dump(mode="json", exclude_none=True)


def _entry_from_local_status(
    status: Mapping[str, Any],
    *,
    index: int,
    now: datetime,
) -> tuple[StatusEnvelopeEntry, list[StatusLifecycleIssue]]:
    family = _required_text(
        status.get("status_family")
        or status.get("family")
        or status.get("local_status_family")
    ).casefold()
    local_status = _required_text(
        status.get("local_status") or status.get("status") or status.get("decision")
    ).casefold()
    spec = _explicit_axis_spec(status) or _STATUS_CROSSWALK.get((family, local_status))
    issues: list[StatusLifecycleIssue] = []
    if spec is None:
        spec = _HARD_BLOCK
    ttl_expires_at = _datetime_or_none(status.get("ttl_expires_at") or status.get("expires_at"))
    entry = StatusEnvelopeEntry(
        entry_id=_optional_text(status.get("entry_id")) or f"local_status:{index}:{family}",
        producer=_optional_text(status.get("producer")) or family,
        status_family=family,
        local_status=local_status,
        severity=spec.severity,
        blockingness=spec.blockingness,
        publication_effect=spec.publication_effect,
        review_action=spec.review_action,
        closeout_effect=spec.closeout_effect,
        owner=_optional_text(status.get("owner")),
        ttl_expires_at=ttl_expires_at,
        ttl_state=_ttl_state(ttl_expires_at, now),
        message=_optional_text(status.get("message")),
        next_action=_optional_text(status.get("next_action")),
        evidence_ref=_optional_text(status.get("evidence_ref") or status.get("artifact_ref")),
        claim_ids=_claim_ids(status),
    )
    crosswalk_missing = (
        _STATUS_CROSSWALK.get((family, local_status)) is None
        and _explicit_axis_spec(status) is None
    )
    if crosswalk_missing:
        issues.append(
            StatusLifecycleIssue(
                code="status_crosswalk_missing",
                entry_id=entry.entry_id,
                status_family=entry.status_family,
                local_status=entry.local_status,
                message=(
                    "Local producer status has no status-envelope crosswalk or "
                    "explicit shared effect axes."
                ),
                next_action="Add a composition rule and mixed-status test for this local status.",
                evidence_ref=entry.evidence_ref,
            )
        )
    issues.extend(_lifecycle_issues(entry, now=now))
    return entry, issues


def _entry_from_deficit(
    deficit: DeficitRecord,
    *,
    index: int,
    now: datetime,
) -> StatusEnvelopeEntry:
    spec = _DEFICIT_AXIS[deficit.disposition]
    return StatusEnvelopeEntry(
        entry_id=f"deficit:{index}:{deficit.deficit_id}",
        producer="runtime.quality.deficit_crosswalk",
        status_family="deficit",
        local_status=deficit.disposition.value,
        severity=spec.severity,
        blockingness=spec.blockingness,
        publication_effect=spec.publication_effect,
        review_action=spec.review_action,
        closeout_effect=spec.closeout_effect,
        owner=deficit.owner,
        ttl_expires_at=deficit.ttl_expires_at,
        ttl_state=_ttl_state(deficit.ttl_expires_at, now),
        message=deficit.public_limitation_note,
        next_action=_deficit_next_action(deficit),
        evidence_ref=deficit.evidence_ref,
        claim_ids=deficit.claim_ids,
        deficit_id=deficit.deficit_id,
        deficit_family=deficit.deficit_family,
        deficit_disposition=deficit.disposition,
    )


def _crosswalk_row(deficit: DeficitRecord, entry: StatusEnvelopeEntry) -> DeficitCrosswalkRow:
    return DeficitCrosswalkRow(
        deficit_id=deficit.deficit_id,
        status_entry_id=entry.entry_id,
        deficit_family=deficit.deficit_family,
        deficit_code=deficit.deficit_code,
        claim_ids=deficit.claim_ids,
        authority_level=deficit.authority_level,
        audience_scope=deficit.audience_scope,
        disposition=deficit.disposition,
        severity=entry.severity,
        blockingness=entry.blockingness,
        publication_effect=entry.publication_effect,
        review_action=entry.review_action,
        closeout_effect=entry.closeout_effect,
        support_cap=deficit.support_cap,
        readiness_cap=deficit.readiness_cap,
        max_audience=deficit.max_audience,
        owner=deficit.owner,
        ttl_expires_at=deficit.ttl_expires_at,
        runtime_event_ref=deficit.runtime_event_ref,
        evidence_ref=deficit.evidence_ref,
        public_limitation_note=deficit.public_limitation_note,
        review_refs=deficit.review_refs,
    )


def _lifecycle_issues(
    entry: StatusEnvelopeEntry,
    *,
    now: datetime,
) -> list[StatusLifecycleIssue]:
    if not _requires_lifecycle(entry):
        return []
    issues: list[StatusLifecycleIssue] = []
    if entry.owner is None:
        issues.append(
            StatusLifecycleIssue(
                code="status_lifecycle_owner_missing",
                entry_id=entry.entry_id,
                status_family=entry.status_family,
                local_status=entry.local_status,
                message="Warning-like or blocking status has no owner.",
                next_action="Attach an accountable owner to the status or resolve it.",
                evidence_ref=entry.evidence_ref,
            )
        )
    if entry.ttl_expires_at is None:
        issues.append(
            StatusLifecycleIssue(
                code="status_lifecycle_ttl_missing",
                entry_id=entry.entry_id,
                status_family=entry.status_family,
                local_status=entry.local_status,
                message="Warning-like or blocking status has no TTL.",
                next_action="Attach a TTL/escalation deadline to the status or resolve it.",
                evidence_ref=entry.evidence_ref,
            )
        )
    elif entry.ttl_expires_at <= now:
        issues.append(
            StatusLifecycleIssue(
                code="status_lifecycle_ttl_expired",
                entry_id=entry.entry_id,
                status_family=entry.status_family,
                local_status=entry.local_status,
                message="Warning-like or blocking status TTL has expired.",
                next_action="Escalate, reissue, or resolve the stale status before closeout.",
                evidence_ref=entry.evidence_ref,
            )
        )
    return issues


def _requires_lifecycle(entry: StatusEnvelopeEntry) -> bool:
    return (
        entry.severity is not SharedSeverity.INFO
        or entry.publication_effect is not PublicationEffect.UNAFFECTED
        or entry.review_action is not ReviewAction.NONE
        or entry.closeout_effect is not CloseoutEffect.CLOSEOUT_ALLOWED
    )


def _summary(
    entries: Sequence[StatusEnvelopeEntry],
    crosswalk: Sequence[DeficitCrosswalkRow],
    lifecycle_issues: Sequence[StatusLifecycleIssue],
) -> StatusEnvelopeSummary:
    severities = [entry.severity for entry in entries] or [SharedSeverity.INFO]
    blocking = [entry.blockingness for entry in entries] or [Blockingness.NON_BLOCKING]
    publications = [entry.publication_effect for entry in entries] or [
        PublicationEffect.UNAFFECTED
    ]
    reviews = [entry.review_action for entry in entries] or [ReviewAction.NONE]
    closeouts = [entry.closeout_effect for entry in entries] or [
        CloseoutEffect.CLOSEOUT_ALLOWED
    ]
    if lifecycle_issues:
        severities.append(SharedSeverity.CRITICAL)
        blocking.append(Blockingness.HARD_BLOCKING)
        publications.append(PublicationEffect.PUBLICATION_BLOCKED)
        reviews.append(ReviewAction.HUMAN_REVIEW)
        closeouts.append(CloseoutEffect.CLOSEOUT_BLOCKED)
    ttl_values = sorted(entry.ttl_expires_at for entry in entries if entry.ttl_expires_at)
    return StatusEnvelopeSummary(
        entry_count=len(entries),
        deficit_count=len(crosswalk),
        max_severity=_max_by(severities, _SEVERITY_ORDER),
        max_blockingness=_max_by(blocking, _BLOCKING_ORDER),
        publication_effect=_max_by(publications, _PUBLICATION_ORDER),
        review_action=_max_by(reviews, _REVIEW_ORDER),
        closeout_effect=_max_by(closeouts, _CLOSEOUT_ORDER),
        owners=tuple(sorted({entry.owner for entry in entries if entry.owner})),
        ttl_expires_at=ttl_values[0] if ttl_values else None,
        blocking_entry_ids=tuple(
            entry.entry_id
            for entry in entries
            if entry.blockingness is not Blockingness.NON_BLOCKING
        ),
        reasons=tuple(
            sorted(
                {
                    *(issue.code for issue in lifecycle_issues),
                    *(
                        f"deficit:{row.disposition.value}"
                        for row in crosswalk
                        if row.closeout_effect
                        is not CloseoutEffect.CLOSEOUT_ALLOWED
                    ),
                }
            )
        ),
    )


def _deficit_gate(row: DeficitCrosswalkRow) -> dict[str, Any]:
    code = {
        DeficitDisposition.ACCEPTED_DEFICIT: "status_deficit_accepted",
        DeficitDisposition.PUBLISH_WITH_LIMITATION: (
            "status_deficit_publish_with_limitation"
        ),
        DeficitDisposition.HUMAN_REVIEW_REQUIRED: "status_deficit_review_required",
        DeficitDisposition.EXPERT_REVIEW_REQUIRED: "status_deficit_review_required",
        DeficitDisposition.REISSUE_REQUIRED: "status_deficit_reissue_required",
        DeficitDisposition.HARD_BLOCK: "status_deficit_hard_block",
    }[row.disposition]
    blocking = row.closeout_effect in {
        CloseoutEffect.REVIEW_REQUIRED,
        CloseoutEffect.REISSUE_REQUIRED,
        CloseoutEffect.CLOSEOUT_BLOCKED,
    }
    status = "fail" if blocking else "pass"
    return {
        "name": code,
        "stage": "ops",
        "code": code,
        "status": status,
        "layer": "status_envelope",
        "phase": "deficit_crosswalk",
        "message": _deficit_message(row),
        "evidence_ref": row.evidence_ref,
        "next_action": _deficit_gate_next_action(row),
        "blocking": blocking,
        "owner": row.owner,
        "deficit_id": row.deficit_id,
        "deficit_family": row.deficit_family,
        "deficit_disposition": row.disposition.value,
        "severity": row.severity.value,
        "blockingness": row.blockingness.value,
        "publication_effect": row.publication_effect.value,
        "review_action": row.review_action.value,
        "closeout_effect": row.closeout_effect.value,
        "support_cap": row.support_cap,
        "readiness_cap": row.readiness_cap,
        "max_audience": row.max_audience,
    }


def _local_status_gate(entry: StatusEnvelopeEntry) -> dict[str, Any] | None:
    if entry.closeout_effect in {
        CloseoutEffect.CLOSEOUT_ALLOWED,
        CloseoutEffect.ACCEPTED_DEFICIT,
        CloseoutEffect.LIMITED_CLOSEOUT,
    }:
        return None
    code = {
        CloseoutEffect.REVIEW_REQUIRED: "status_crosswalk_review_required",
        CloseoutEffect.REISSUE_REQUIRED: "status_crosswalk_reissue_required",
        CloseoutEffect.CLOSEOUT_BLOCKED: "status_crosswalk_closeout_blocked",
    }[entry.closeout_effect]
    return {
        "name": code,
        "stage": "ops",
        "code": code,
        "status": "fail",
        "layer": "status_envelope",
        "phase": entry.status_family,
        "message": (
            f"{entry.status_family} local status {entry.local_status} requires "
            f"{entry.closeout_effect.value}."
        ),
        "evidence_ref": entry.evidence_ref,
        "next_action": entry.next_action or "Resolve or review the local producer status.",
        "blocking": True,
        "owner": entry.owner,
        "severity": entry.severity.value,
        "blockingness": entry.blockingness.value,
        "publication_effect": entry.publication_effect.value,
        "review_action": entry.review_action.value,
        "closeout_effect": entry.closeout_effect.value,
    }


def _explicit_axis_spec(status: Mapping[str, Any]) -> _AxisSpec | None:
    if not any(
        key in status
        for key in (
            "severity",
            "blockingness",
            "publication_effect",
            "review_action",
            "closeout_effect",
        )
    ):
        return None
    return _AxisSpec(
        SharedSeverity(_required_text(status.get("severity"))),
        Blockingness(_required_text(status.get("blockingness"))),
        PublicationEffect(_required_text(status.get("publication_effect"))),
        ReviewAction(_required_text(status.get("review_action"))),
        CloseoutEffect(_required_text(status.get("closeout_effect"))),
    )


def _deficit_message(row: DeficitCrosswalkRow) -> str:
    if row.disposition is DeficitDisposition.ACCEPTED_DEFICIT:
        return "Deficit is accepted for this authority profile and remains visible."
    if row.disposition is DeficitDisposition.PUBLISH_WITH_LIMITATION:
        return "Deficit permits publication only with an explicit limitation."
    if row.disposition in {
        DeficitDisposition.HUMAN_REVIEW_REQUIRED,
        DeficitDisposition.EXPERT_REVIEW_REQUIRED,
    }:
        return "Deficit requires review before closeout or publication."
    if row.disposition is DeficitDisposition.REISSUE_REQUIRED:
        return "Deficit requires reissue before closeout or publication."
    return "Deficit is hard-blocking for closeout and publication."


def _deficit_gate_next_action(row: DeficitCrosswalkRow) -> str:
    if row.disposition is DeficitDisposition.ACCEPTED_DEFICIT:
        return "Keep accepted deficit, owner, TTL, and evidence refs attached."
    if row.disposition is DeficitDisposition.PUBLISH_WITH_LIMITATION:
        return "Publish only with the recorded limitation and audience cap."
    if row.review_action is ReviewAction.EXPERT_REVIEW:
        return "Route the deficit to expert review before closeout."
    if row.review_action is ReviewAction.HUMAN_REVIEW:
        return "Route the deficit to human review before closeout."
    if row.review_action is ReviewAction.REISSUE:
        return "Reissue the affected decision artifacts before closeout."
    return "Resolve the hard-blocking deficit before closeout."


def _deficit_next_action(deficit: DeficitRecord) -> str:
    row = DeficitCrosswalkRow(
        deficit_id=deficit.deficit_id,
        status_entry_id=deficit.deficit_id,
        deficit_family=deficit.deficit_family,
        deficit_code=deficit.deficit_code,
        claim_ids=deficit.claim_ids,
        authority_level=deficit.authority_level,
        audience_scope=deficit.audience_scope,
        disposition=deficit.disposition,
        severity=_DEFICIT_AXIS[deficit.disposition].severity,
        blockingness=_DEFICIT_AXIS[deficit.disposition].blockingness,
        publication_effect=_DEFICIT_AXIS[deficit.disposition].publication_effect,
        review_action=_DEFICIT_AXIS[deficit.disposition].review_action,
        closeout_effect=_DEFICIT_AXIS[deficit.disposition].closeout_effect,
        support_cap=deficit.support_cap,
        readiness_cap=deficit.readiness_cap,
        max_audience=deficit.max_audience,
        owner=deficit.owner,
        ttl_expires_at=deficit.ttl_expires_at,
        runtime_event_ref=deficit.runtime_event_ref,
        evidence_ref=deficit.evidence_ref,
        public_limitation_note=deficit.public_limitation_note,
        review_refs=deficit.review_refs,
    )
    return _deficit_gate_next_action(row)


def _ttl_state(value: datetime | None, now: datetime) -> Literal["active", "expired", "missing"]:
    if value is None:
        return "missing"
    return "expired" if value <= now else "active"


def _claim_ids(payload: Mapping[str, Any]) -> tuple[str, ...]:
    raw = (
        payload.get("claim_ids")
        or payload.get("claims")
        or payload.get("affected_claims")
        or payload.get("claim_id")
    )
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (_required_text(raw),)
    if isinstance(raw, Sequence) and not isinstance(raw, (bytes, bytearray)):
        values: list[str] = []
        for item in raw:
            value = item.get("claim_id") or item.get("id") if isinstance(item, Mapping) else item
            text = _optional_text(value)
            if text is not None:
                values.append(text)
        return tuple(dict.fromkeys(values))
    return ()


def _datetime_or_none(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _utc(value)
    text = _optional_text(value)
    if text is None:
        return None
    return _utc(datetime.fromisoformat(text.replace("Z", "+00:00")))


def _utc(value: datetime | None) -> datetime:
    candidate = value or datetime.now(UTC)
    if candidate.tzinfo is None:
        return candidate.replace(tzinfo=UTC)
    return candidate.astimezone(UTC)


def _max_by[T](values: Iterable[T], order: Mapping[T, int]) -> T:
    return max(values, key=lambda value: order[value])


def _required_text(value: object) -> str:
    text = _optional_text(value)
    if text is None:
        raise ValueError("expected non-empty text")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_tuple(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(text for value in values if (text := _optional_text(value))))


__all__ = [
    "DEFICIT_CROSSWALK_SCHEMA_VERSION",
    "STATUS_ENVELOPE_SCHEMA_VERSION",
    "Blockingness",
    "CloseoutEffect",
    "DeficitCrosswalkRow",
    "DeficitDisposition",
    "DeficitRecord",
    "PublicationEffect",
    "ReviewAction",
    "SharedSeverity",
    "StatusEnvelope",
    "StatusEnvelopeEntry",
    "StatusEnvelopeSummary",
    "StatusLifecycleIssue",
    "build_status_envelope",
    "status_envelope_payload",
    "status_envelope_scorecard_gates",
]
