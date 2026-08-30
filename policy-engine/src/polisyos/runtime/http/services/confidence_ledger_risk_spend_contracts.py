"""Strict reviewer transport shape for confidence-ledger risk-spend packets.

Parsing proves structural and self-hash coherence only. Owner provenance is
established online by ``ConfidenceLedgerRiskSpendProjectionService`` resolving
the current exact source and executing the isolated owner worker for every
request. The guarded DS17 source never reuses the generic governed-projection
validation cache. No offline DTO label or self-hash authenticates it.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Pydantic resolves the public DTO field
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.runtime.http.services.export_replay import (
    EXPORT_REPLAY_CONTRACT,
    build_export_replay_address,
    hash_export_projection,
)
from polisyos.runtime.http.services.governed_projections import (
    CONFIDENCE_LEDGER_GUARDED_SCHEMA_VERSION,
    CONFIDENCE_LEDGER_GUARDED_SOURCE_PATH,
    CONFIDENCE_LEDGER_GUARDED_VALIDATOR_ID,
    CONFIDENCE_LEDGER_GUARDED_VALIDATOR_VERSION,
    AudienceClass,
    ProjectionFreshness,
    ProjectionSourceIdentity,
)
from polisyos.runtime.quality.confidence_ledger_surface import (  # noqa: TC001
    ConfidenceLedgerRiskSpendProjection,
)

PACKET_SCHEMA_VERSION = "policyos.runtime.confidence_ledger_risk_spend_packet.v1"
PROJECTION_RULE_VERSION = "policyos.runtime.confidence_ledger_risk_spend.v1"
STABLE_ADDRESS = "/api/v1/exports/governed-projections/confidence-ledger-risk-spend"
PROJECTION_ID = "confidence-ledger-risk-spend"
_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_WORKER_RECEIPT_PATTERN = r"^owner-validation:sha256:[0-9a-f]{64}$"
AUTHORITATIVE_FOR = (
    "conditionality_disclosure",
    "declared_set_accounting",
    "source_validation_posture",
)
MAY_NOT_USE_FOR = (
    "promotion_authority",
    "publication_authority",
    "public_audience",
    "bounded_completeness",
)


class _StrictModel(BaseModel):
    """Immutable strict base for public DS17 HTTP DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ConfidenceLedgerRiskSpendAvailability(StrEnum):
    """Complete transport-state algebra for the specialized surface."""

    AVAILABLE = "available"
    SOURCE_BLOCKED = "source_blocked"
    ARTIFACT_MISSING = "artifact_missing"
    INVALID_SOURCE = "invalid_source"


class SourceBlockedReason(StrEnum):
    """Canonical source rejection that is safe to expose without source detail."""

    OVER_SPEND = "over_spend"


class ConfidenceLedgerRiskSpendReplayPins(_StrictModel):
    """Exact tuple required to replay one coherent transport projection."""

    artifact_content_hash: str = Field(pattern=_SHA256_PATTERN)
    source_dependency_hash: str = Field(pattern=_SHA256_PATTERN)
    projection_rule_version: Literal["policyos.runtime.confidence_ledger_risk_spend.v1"] = (
        PROJECTION_RULE_VERSION
    )
    projection_hash: str = Field(pattern=_SHA256_PATTERN)
    source_as_of: datetime


class _ConfidenceLedgerRiskSpendPacketBase(_StrictModel):
    """Authority, audience, and time fields shared by every transport arm."""

    packet_schema_version: Literal["policyos.runtime.confidence_ledger_risk_spend_packet.v1"] = (
        PACKET_SCHEMA_VERSION
    )
    export_replay_contract: Literal["policyos.runtime.export_replay_binding.v1"] = (
        EXPORT_REPLAY_CONTRACT
    )
    projection_id: Literal["confidence-ledger-risk-spend"] = PROJECTION_ID
    projection_rule_version: Literal["policyos.runtime.confidence_ledger_risk_spend.v1"] = (
        PROJECTION_RULE_VERSION
    )
    intended_audience: Literal[AudienceClass.REVIEWER] = AudienceClass.REVIEWER
    intended_audiences: tuple[
        Literal[AudienceClass.REVIEWER],
        Literal[AudienceClass.EXPERT],
        Literal["MACHINE"],
    ] = (
        AudienceClass.REVIEWER,
        AudienceClass.EXPERT,
        "MACHINE",
    )
    authoritative_for: tuple[
        Literal[
            "conditionality_disclosure",
            "declared_set_accounting",
            "source_validation_posture",
        ],
        ...,
    ] = AUTHORITATIVE_FOR
    may_not_use_for: tuple[
        Literal[
            "promotion_authority",
            "publication_authority",
            "public_audience",
            "bounded_completeness",
        ],
        ...,
    ] = MAY_NOT_USE_FOR
    source_schema_version: str | None
    source_rule_version: str | None
    as_of: datetime
    freshness: ProjectionFreshness
    stable_address: Literal["/api/v1/exports/governed-projections/confidence-ledger-risk-spend"] = (
        STABLE_ADDRESS
    )

    @model_validator(mode="after")
    def _bind_exact_authority(self) -> Self:
        if self.authoritative_for != AUTHORITATIVE_FOR or self.may_not_use_for != MAY_NOT_USE_FOR:
            raise ValueError("confidence_packet_authority_mismatch")
        return self


class AvailableConfidenceLedgerRiskSpendPacket(_ConfidenceLedgerRiskSpendPacketBase):
    """Wire shape emitted after the online service owner-admits the source."""

    availability: Literal[ConfidenceLedgerRiskSpendAvailability.AVAILABLE]
    source: ProjectionSourceIdentity
    source_dependency_hash: str = Field(pattern=_SHA256_PATTERN)
    registry_content_hash: str = Field(pattern=_SHA256_PATTERN)
    registry_projection_hash: str = Field(pattern=_SHA256_PATTERN)
    frozen_semantic_projection_hash: str = Field(pattern=_SHA256_PATTERN)
    worker_validation_receipt_ref: str = Field(pattern=_WORKER_RECEIPT_PATTERN)
    worker_validation_receipt_hash: str = Field(pattern=_SHA256_PATTERN)
    payload: ConfidenceLedgerRiskSpendProjection
    replay_pins: ConfidenceLedgerRiskSpendReplayPins
    projection_hash: str = Field(pattern=_SHA256_PATTERN)
    replay_address: str
    source_blocked_reason: None = None
    absence_reason: None = None

    @model_validator(mode="after")
    def _bind_available_packet(self) -> Self:
        validation = self.source.validation
        if (
            self.source_schema_version != CONFIDENCE_LEDGER_GUARDED_SCHEMA_VERSION
            or self.source_rule_version is not None
            or self.source.relative_path != CONFIDENCE_LEDGER_GUARDED_SOURCE_PATH
            or validation.validator_id != CONFIDENCE_LEDGER_GUARDED_VALIDATOR_ID
            or validation.validator_version != CONFIDENCE_LEDGER_GUARDED_VALIDATOR_VERSION
            or validation.status != "passed"
            or validation.issue_codes != ()
            or validation.source_payload_equal is not True
        ):
            raise ValueError("available_confidence_source_structure_mismatch")
        if (
            self.source.artifact_content_hash != self.replay_pins.artifact_content_hash
            or validation.bound_artifact_content_hash != self.source.artifact_content_hash
            or self.source_dependency_hash != self.replay_pins.source_dependency_hash
            or validation.bound_dependency_aggregate_identity != self.source_dependency_hash
            or self.projection_rule_version != self.replay_pins.projection_rule_version
            or self.projection_hash != self.replay_pins.projection_hash
            or self.as_of != self.replay_pins.source_as_of
            or validation.worker_validation_receipt_hash != self.worker_validation_receipt_hash
            or validation.registry_content_hash != self.registry_content_hash
            or validation.registry_projection_hash != self.registry_projection_hash
            or validation.frozen_semantic_projection_hash != self.frozen_semantic_projection_hash
            or validation.semantic_projection_hash != self.frozen_semantic_projection_hash
            or self.payload.registry_content_hash != self.registry_content_hash
            or self.payload.source_projection_hash != self.frozen_semantic_projection_hash
        ):
            raise ValueError("available_confidence_packet_binding_mismatch")
        if self.worker_validation_receipt_ref != (
            f"owner-validation:{self.worker_validation_receipt_hash}"
        ):
            raise ValueError("confidence_worker_receipt_ref_mismatch")
        _validate_packet_identity(self)
        return self


class SourceBlockedConfidenceLedgerRiskSpendPacket(_ConfidenceLedgerRiskSpendPacketBase):
    """Safe over-spend rejection without rejected-source semantic detail."""

    availability: Literal[ConfidenceLedgerRiskSpendAvailability.SOURCE_BLOCKED]
    source_blocked_reason: Literal[SourceBlockedReason.OVER_SPEND]
    source_artifact_content_hash: str = Field(pattern=_SHA256_PATTERN)
    source_dependency_hash: str = Field(pattern=_SHA256_PATTERN)
    worker_validation_receipt_ref: str = Field(pattern=_WORKER_RECEIPT_PATTERN)
    worker_validation_receipt_hash: str = Field(pattern=_SHA256_PATTERN)
    replay_pins: ConfidenceLedgerRiskSpendReplayPins
    projection_hash: str = Field(pattern=_SHA256_PATTERN)
    replay_address: str
    absence_reason: None = None

    @model_validator(mode="after")
    def _bind_blocked_packet(self) -> Self:
        if (
            self.source_artifact_content_hash != self.replay_pins.artifact_content_hash
            or self.source_dependency_hash != self.replay_pins.source_dependency_hash
            or self.projection_rule_version != self.replay_pins.projection_rule_version
            or self.projection_hash != self.replay_pins.projection_hash
            or self.as_of != self.replay_pins.source_as_of
        ):
            raise ValueError("blocked_confidence_packet_binding_mismatch")
        if self.worker_validation_receipt_ref != (
            f"owner-validation:{self.worker_validation_receipt_hash}"
        ):
            raise ValueError("confidence_worker_receipt_ref_mismatch")
        _validate_packet_identity(self)
        return self


class ArtifactMissingConfidenceLedgerRiskSpendPacket(_ConfidenceLedgerRiskSpendPacketBase):
    """Typed absence of the one governed N11 source."""

    availability: Literal[ConfidenceLedgerRiskSpendAvailability.ARTIFACT_MISSING]
    source_schema_version: None = None
    source_rule_version: None = None
    source_artifact_content_hash: None = None
    source_dependency_hash: None = None
    worker_validation_receipt_ref: None = None
    worker_validation_receipt_hash: None = None
    replay_pins: None = None
    projection_hash: None = None
    replay_address: None = None
    source_blocked_reason: None = None
    absence_reason: Literal["governed confidence-ledger source is absent"]


class InvalidConfidenceLedgerRiskSpendPacket(_ConfidenceLedgerRiskSpendPacketBase):
    """Generic fail-closed rejection with no untrusted diagnostic detail."""

    availability: Literal[ConfidenceLedgerRiskSpendAvailability.INVALID_SOURCE]
    source_artifact_content_hash: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    source_dependency_hash: None = None
    worker_validation_receipt_ref: str | None = Field(
        default=None,
        pattern=_WORKER_RECEIPT_PATTERN,
    )
    worker_validation_receipt_hash: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    replay_pins: None = None
    projection_hash: None = None
    replay_address: None = None
    source_blocked_reason: None = None
    absence_reason: Literal["confidence-ledger source failed owner admission"]

    @model_validator(mode="after")
    def _receipt_pair_is_complete(self) -> Self:
        if (self.worker_validation_receipt_ref is None) != (
            self.worker_validation_receipt_hash is None
        ):
            raise ValueError("confidence_invalid_worker_receipt_pair_incomplete")
        if self.worker_validation_receipt_ref is not None and (
            self.worker_validation_receipt_ref
            != f"owner-validation:{self.worker_validation_receipt_hash}"
        ):
            raise ValueError("confidence_worker_receipt_ref_mismatch")
        return self


ConfidenceLedgerRiskSpendPacketCandidate = Annotated[
    AvailableConfidenceLedgerRiskSpendPacket
    | SourceBlockedConfidenceLedgerRiskSpendPacket
    | ArtifactMissingConfidenceLedgerRiskSpendPacket
    | InvalidConfidenceLedgerRiskSpendPacket,
    Field(discriminator="availability"),
]
# Owner-emitted responses use the same wire shape. Parsing this alias offline
# still yields only a structural candidate; it is never an owner-admission API.
ConfidenceLedgerRiskSpendPacket = ConfidenceLedgerRiskSpendPacketCandidate


def packet_semantic_projection(
    packet: AvailableConfidenceLedgerRiskSpendPacket | SourceBlockedConfidenceLedgerRiskSpendPacket,
) -> dict[str, object]:
    """Return the non-self-referential semantics used for coherence hashing."""

    body = packet.model_dump(
        mode="json",
        exclude={"projection_hash", "replay_pins", "replay_address"},
    )
    freshness = body.get("freshness")
    if isinstance(freshness, dict):
        freshness.pop("observed_at", None)
    return body


def _validate_packet_identity(
    packet: AvailableConfidenceLedgerRiskSpendPacket | SourceBlockedConfidenceLedgerRiskSpendPacket,
) -> None:
    expected_hash = hash_export_projection(packet_semantic_projection(packet))
    if packet.projection_hash != expected_hash:
        raise ValueError("confidence_packet_projection_hash_mismatch")
    expected_replay = build_export_replay_address(
        STABLE_ADDRESS,
        packet.replay_pins.model_dump(mode="json"),
    )
    if packet.replay_address != expected_replay:
        raise ValueError("confidence_packet_replay_address_mismatch")


__all__ = [
    "AUTHORITATIVE_FOR",
    "MAY_NOT_USE_FOR",
    "PACKET_SCHEMA_VERSION",
    "PROJECTION_ID",
    "PROJECTION_RULE_VERSION",
    "STABLE_ADDRESS",
    "ArtifactMissingConfidenceLedgerRiskSpendPacket",
    "AvailableConfidenceLedgerRiskSpendPacket",
    "ConfidenceLedgerRiskSpendAvailability",
    "ConfidenceLedgerRiskSpendPacket",
    "ConfidenceLedgerRiskSpendPacketCandidate",
    "ConfidenceLedgerRiskSpendReplayPins",
    "InvalidConfidenceLedgerRiskSpendPacket",
    "SourceBlockedConfidenceLedgerRiskSpendPacket",
    "SourceBlockedReason",
    "packet_semantic_projection",
]
