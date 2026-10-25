"""Candidate-only DecisionPacket projection reconciled to Runtime HTE ownership.

This HTTP-layer contract reads a selected DecisionPacket JSON profile and
compares its persisted candidate summary and complete owner association to the
fresh Runtime owner projection. It does not establish publication authority or
live source currentness.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from polisyos.core.artifacts import ArtifactRef

if TYPE_CHECKING:
    from polisyos.core.artifacts import CoreJsonArtifactBoundedRead
from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
from polisyos.core.contracts.owned_attempt_anchor import (
    OwnedAttemptAnchorProjectionAssociation,
)
from polisyos.core.contracts.runtime import (
    CompletedMethodHTESource,
    DirectMethodExecutionHTESummary,
)

DECISION_PACKET_KIND = "scientist.decision_packet"
DECISION_PACKET_SCHEMA_NAME = "polisyos.scientist.DecisionPacket"
DECISION_PACKET_SCHEMA_VERSION = "3.4"
DECISION_PACKET_CANDIDATE_READ_LIMITS = CoreJsonReadLimits(
    max_bytes=8 * 1024 * 1024,
    max_depth=64,
    max_elements=100_000,
    max_manifest_bytes=256 * 1024,
)


class CandidatePacketProjectionRefusalError(ValueError):
    """Raised when exact packet identity or owner reconciliation is not established."""

    def __init__(self, code: str) -> None:
        """Create one stable refusal code for a fail-closed candidate projection."""
        self.code = code
        super().__init__(code)


class CandidateDecisionPacketHTEProjection(BaseModel):
    """Strict response carrying one packet-bound HTE candidate, never authority."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1"] = "1"
    candidate_only: Literal[True] = True
    packet_run_id: str = Field(min_length=1, max_length=128)
    decision_packet_ref: ArtifactRef
    candidate_status: Literal["selected", "absent"]
    source: CompletedMethodHTESource | None = None
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    publication_authorization: Literal["not_established"] = "not_established"
    live_source_currentness: Literal["not_established"] = "not_established"
    reader_at: datetime

    @model_validator(mode="after")
    def _require_candidate_shape(self) -> CandidateDecisionPacketHTEProjection:
        """Keep candidate presence, profile identity, and reader time explicit."""
        if (self.candidate_status == "selected") != (self.source is not None):
            raise ValueError("candidate_packet_projection_status_shape_mismatch")
        if self.decision_packet_ref.manifest_profile_sha256 is None:
            raise ValueError("candidate_packet_projection_profile_required")
        if not _is_aware(self.reader_at):
            raise ValueError("candidate_packet_projection_reader_time_not_aware")
        return self


def require_exact_candidate_packet_ref(
    *,
    indexed_packet_ref: ArtifactRef | None,
    requested_packet_id: str,
    requested_manifest_profile_sha256: str,
) -> ArtifactRef:
    """Treat request IDs as equality selectors against the packet-owning RunIndex."""
    if type(indexed_packet_ref) is not ArtifactRef:
        raise CandidatePacketProjectionRefusalError("candidate_packet_output_not_indexed")
    if (
        indexed_packet_ref.kind != DECISION_PACKET_KIND
        or indexed_packet_ref.media_type != "application/json"
        or indexed_packet_ref.manifest_profile_sha256 is None
    ):
        raise CandidatePacketProjectionRefusalError("candidate_packet_index_ref_incomplete")
    if type(requested_packet_id) is not str or requested_packet_id != str(
        indexed_packet_ref.artifact_id
    ):
        raise CandidatePacketProjectionRefusalError("candidate_packet_id_index_mismatch")
    if (
        type(requested_manifest_profile_sha256) is not str
        or requested_manifest_profile_sha256 != indexed_packet_ref.manifest_profile_sha256
    ):
        raise CandidatePacketProjectionRefusalError("candidate_packet_profile_index_mismatch")
    return indexed_packet_ref


def validate_bounded_candidate_packet(
    *,
    bounded_read: CoreJsonArtifactBoundedRead,
    selected_ref: ArtifactRef,
) -> dict[str, object]:
    """Require one bounded CAS read to preserve exact packet profile and schema."""
    if (
        type(selected_ref) is not ArtifactRef
        or selected_ref.kind != DECISION_PACKET_KIND
        or selected_ref.media_type != "application/json"
        or selected_ref.manifest_profile_sha256 is None
    ):
        raise CandidatePacketProjectionRefusalError("candidate_packet_profile_required")
    try:
        effective_ref = bounded_read.effective_ref
        manifest = bounded_read.manifest
        payload = bounded_read.value
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise CandidatePacketProjectionRefusalError(
            "candidate_packet_bounded_read_unavailable"
        ) from exc
    artifact_schema = manifest.artifact_schema
    if (
        effective_ref != selected_ref
        or getattr(manifest, "artifact_id", None) != selected_ref.artifact_id
        or getattr(manifest, "kind", None) != DECISION_PACKET_KIND
        or getattr(manifest, "media_type", None) != "application/json"
        or getattr(artifact_schema, "name", None) != DECISION_PACKET_SCHEMA_NAME
        or getattr(artifact_schema, "version", None) != DECISION_PACKET_SCHEMA_VERSION
    ):
        raise CandidatePacketProjectionRefusalError("candidate_packet_manifest_identity_mismatch")
    if type(payload) is not dict or payload.get("schema_version") != DECISION_PACKET_SCHEMA_VERSION:
        raise CandidatePacketProjectionRefusalError("candidate_packet_schema_mismatch")
    return payload


def require_candidate_projection_scope(
    *,
    scope_tenant_id: str | None,
    scope_cell_id: str | None,
    packet_tenant_id: str | None,
    packet_cell_id: str | None,
    source_tenant_id: str | None,
    source_cell_id: str | None,
) -> None:
    """Require both independently authorized runs to match the active tenant/cell."""
    values = (
        scope_tenant_id,
        scope_cell_id,
        packet_tenant_id,
        packet_cell_id,
        source_tenant_id,
        source_cell_id,
    )
    if any(type(value) is not str or not value for value in values):
        raise CandidatePacketProjectionRefusalError("candidate_packet_run_scope_not_established")
    if (
        scope_tenant_id != packet_tenant_id
        or scope_cell_id != packet_cell_id
        or scope_tenant_id != source_tenant_id
        or scope_cell_id != source_cell_id
    ):
        raise CandidatePacketProjectionRefusalError("candidate_packet_run_scope_mismatch")


def candidate_packet_source_selector(
    packet_payload: object,
) -> tuple[Literal["selected", "verification_missing"], str]:
    """Resolve the packet-declared source run before any owner-state lookup."""
    if type(packet_payload) is not dict:
        raise CandidatePacketProjectionRefusalError("candidate_packet_payload_invalid")
    basis_summary = _basis_summary(packet_payload)
    status = basis_summary.get("completed_hte_source_status")
    if status == "selected":
        field_name = "completed_hte_source_run_id"
    elif status == "verification_missing":
        field_name = "completed_hte_requested_source_run_id"
    else:
        raise CandidatePacketProjectionRefusalError("candidate_packet_source_status_unrecognized")
    source_run_id = basis_summary.get(field_name)
    if type(source_run_id) is not str or not source_run_id:
        raise CandidatePacketProjectionRefusalError("candidate_packet_source_run_missing")
    return status, source_run_id


def require_same_candidate_source_run(*, packet_run_id: str, source_run_id: str) -> str:
    """Refuse cross-run candidate resolution until independent permission is owned."""
    if (
        type(packet_run_id) is not str
        or not packet_run_id
        or type(source_run_id) is not str
        or not source_run_id
    ):
        raise CandidatePacketProjectionRefusalError("candidate_packet_run_identity_invalid")
    if packet_run_id != source_run_id:
        raise CandidatePacketProjectionRefusalError("cross_run_authorization_not_established")
    return packet_run_id


def project_candidate_hte_packet(
    *,
    packet_payload: object,
    packet_run_id: str,
    packet_ref: ArtifactRef,
    source_run_id_selector: str,
    fresh_source: CompletedMethodHTESource | None,
    reader_at: datetime,
) -> CandidateDecisionPacketHTEProjection:
    """Build a strict projection only when packet content matches the fresh owner.

    The current DecisionPacket writer persists the selected HTE summary in
    the hte field and the complete association plus source markers in the
    decision-validity data-basis summary. Its temporary source object is
    consumed before persistence and is therefore not read here.
    """
    if (
        type(packet_payload) is not dict
        or type(packet_run_id) is not str
        or not packet_run_id
        or type(source_run_id_selector) is not str
        or not source_run_id_selector
        or type(packet_ref) is not ArtifactRef
        or packet_ref.kind != DECISION_PACKET_KIND
        or packet_ref.media_type != "application/json"
        or packet_ref.manifest_profile_sha256 is None
    ):
        raise CandidatePacketProjectionRefusalError("candidate_packet_projection_input_invalid")
    if not _is_aware(reader_at):
        raise CandidatePacketProjectionRefusalError("candidate_packet_reader_time_not_aware")

    basis_summary = _basis_summary(packet_payload)
    _packet_status, persisted_source_run_id = candidate_packet_source_selector(packet_payload)
    if persisted_source_run_id != source_run_id_selector:
        raise CandidatePacketProjectionRefusalError("candidate_packet_source_selector_mismatch")
    require_same_candidate_source_run(
        packet_run_id=packet_run_id,
        source_run_id=persisted_source_run_id,
    )
    status = basis_summary.get("completed_hte_source_status")
    if status == "verification_missing":
        return _project_absent_candidate(
            basis_summary=basis_summary,
            packet_payload=packet_payload,
            packet_run_id=packet_run_id,
            packet_ref=packet_ref,
            source_run_id_selector=source_run_id_selector,
            reader_at=reader_at,
            fresh_source=fresh_source,
        )
    if status != "selected":
        raise CandidatePacketProjectionRefusalError("candidate_packet_source_status_unrecognized")
    if type(fresh_source) is not CompletedMethodHTESource:
        raise CandidatePacketProjectionRefusalError("candidate_packet_fresh_owner_missing")

    try:
        return _project_selected_candidate(
            packet_payload=packet_payload,
            basis_summary=basis_summary,
            packet_run_id=packet_run_id,
            packet_ref=packet_ref,
            source_run_id_selector=source_run_id_selector,
            fresh_source=fresh_source,
            reader_at=reader_at,
        )
    except CandidatePacketProjectionRefusalError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, ValidationError) as exc:
        raise CandidatePacketProjectionRefusalError(
            "candidate_packet_candidate_wire_invalid"
        ) from exc


def _project_absent_candidate(
    *,
    basis_summary: dict[str, object],
    packet_payload: dict[str, object],
    packet_run_id: str,
    packet_ref: ArtifactRef,
    source_run_id_selector: str,
    reader_at: datetime,
    fresh_source: CompletedMethodHTESource | None,
) -> CandidateDecisionPacketHTEProjection:
    """Preserve explicit persisted absence without resolving or inventing a source."""
    requested_source = basis_summary.get("completed_hte_requested_source_run_id")
    if (
        requested_source != source_run_id_selector
        or packet_payload.get("hte") is not None
        or basis_summary.get("completed_hte_owner_association") is not None
        or fresh_source is not None
        or basis_summary.get("completed_hte_publication_authorization") != "not_established"
        or basis_summary.get("completed_hte_authority_purpose") != "candidate_method_evidence"
    ):
        raise CandidatePacketProjectionRefusalError("candidate_packet_absence_content_mismatch")
    limitations = basis_summary.get("completed_hte_limitations")
    if (
        type(limitations) is not list
        or len(limitations) > 32
        or any(type(item) is not str or not item for item in limitations)
    ):
        raise CandidatePacketProjectionRefusalError("candidate_packet_absence_limitations_invalid")
    try:
        return CandidateDecisionPacketHTEProjection(
            packet_run_id=packet_run_id,
            decision_packet_ref=packet_ref,
            candidate_status="absent",
            source=None,
            limitations=tuple(limitations),
            reader_at=reader_at,
        )
    except ValidationError as exc:
        raise CandidatePacketProjectionRefusalError("candidate_packet_projection_invalid") from exc


def _project_selected_candidate(
    *,
    packet_payload: dict[str, object],
    basis_summary: dict[str, object],
    packet_run_id: str,
    packet_ref: ArtifactRef,
    source_run_id_selector: str,
    fresh_source: CompletedMethodHTESource,
    reader_at: datetime,
) -> CandidateDecisionPacketHTEProjection:
    """Bind the exact persisted typed summary and full stable association."""
    if (
        basis_summary.get("completed_hte_authority_purpose") != "candidate_method_evidence"
        or basis_summary.get("completed_hte_publication_authorization") != "not_established"
        or basis_summary.get("completed_hte_currentness_status") != "reconciled_at_completed_event"
    ):
        raise CandidatePacketProjectionRefusalError("candidate_packet_selected_markers_invalid")

    expected_scalars: tuple[tuple[str, object], ...] = (
        ("completed_hte_source_run_id", fresh_source.source_run_id),
        ("completed_hte_requested_source_run_id", fresh_source.source_run_id),
        ("completed_hte_source_job_id", fresh_source.source_job_id),
        ("completed_hte_source_attempt", fresh_source.source_attempt),
        ("completed_hte_completion_event_id", fresh_source.completed_event_id),
        (
            "completed_hte_completion_event_payload_sha256",
            fresh_source.completed_event_payload_sha256,
        ),
        ("completed_hte_outcome_kind", fresh_source.summary.kind),
        ("completed_hte_method_profile_id", fresh_source.summary.method_profile_id),
    )
    if fresh_source.source_run_id != source_run_id_selector:
        raise CandidatePacketProjectionRefusalError("candidate_packet_source_selector_mismatch")
    for key, expected in expected_scalars:
        actual = basis_summary.get(key)
        if type(actual) is not type(expected) or actual != expected:
            raise CandidatePacketProjectionRefusalError("candidate_packet_source_identity_mismatch")

    summary_wire = packet_payload.get("hte")
    association_wire = basis_summary.get("completed_hte_owner_association")
    if type(summary_wire) is not dict or type(association_wire) is not dict:
        raise CandidatePacketProjectionRefusalError("candidate_packet_owner_source_missing")
    wire_json = _wire_json(summary_wire, code="candidate_packet_summary_wire_invalid")
    association_json = _wire_json(
        association_wire,
        code="candidate_packet_association_wire_invalid",
    )
    packet_summary = DirectMethodExecutionHTESummary.model_validate_json(
        wire_json,
        strict=True,
    )
    packet_association = OwnedAttemptAnchorProjectionAssociation.model_validate_json(
        association_json,
        strict=True,
    )
    if packet_summary != fresh_source.summary:
        raise CandidatePacketProjectionRefusalError("candidate_packet_summary_owner_mismatch")
    if packet_association.model_dump(
        mode="python", exclude={"verified_at"}
    ) != fresh_source.association.model_dump(mode="python", exclude={"verified_at"}):
        raise CandidatePacketProjectionRefusalError("candidate_packet_association_owner_mismatch")

    packet_verified_at = packet_association.verified_at
    owner_verified_at = fresh_source.association.verified_at
    if not _is_aware(packet_verified_at) or not _is_aware(owner_verified_at):
        raise CandidatePacketProjectionRefusalError("candidate_packet_verified_at_not_aware")
    if owner_verified_at <= packet_verified_at or reader_at < owner_verified_at:
        raise CandidatePacketProjectionRefusalError("candidate_packet_verified_at_order_invalid")

    try:
        return CandidateDecisionPacketHTEProjection(
            packet_run_id=packet_run_id,
            decision_packet_ref=packet_ref,
            candidate_status="selected",
            source=fresh_source,
            limitations=tuple(fresh_source.summary.limitations),
            reader_at=reader_at,
        )
    except ValidationError as exc:
        raise CandidatePacketProjectionRefusalError("candidate_packet_projection_invalid") from exc


def _basis_summary(packet_payload: dict[str, object]) -> dict[str, object]:
    """Resolve the exact persisted decision-validity basis summary."""
    envelope = packet_payload.get("decision_validity_envelope")
    if type(envelope) is not dict:
        raise CandidatePacketProjectionRefusalError("candidate_packet_basis_missing")
    basis = envelope.get("data_basis")
    if type(basis) is not dict:
        raise CandidatePacketProjectionRefusalError("candidate_packet_basis_missing")
    summary = basis.get("summary")
    if type(summary) is not dict:
        raise CandidatePacketProjectionRefusalError("candidate_packet_basis_summary_missing")
    return summary


def _wire_json(value: dict[str, object], *, code: str) -> str:
    """Encode one decoded JSON object so strict models use JSON rather than Python mode."""
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise CandidatePacketProjectionRefusalError(code) from exc


def _is_aware(value: datetime) -> bool:
    """Return whether a datetime has a usable explicit UTC offset."""
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


__all__ = [
    "DECISION_PACKET_CANDIDATE_READ_LIMITS",
    "CandidateDecisionPacketHTEProjection",
    "CandidatePacketProjectionRefusalError",
    "candidate_packet_source_selector",
    "project_candidate_hte_packet",
    "require_candidate_projection_scope",
    "require_exact_candidate_packet_ref",
    "require_same_candidate_source_run",
    "validate_bounded_candidate_packet",
]
