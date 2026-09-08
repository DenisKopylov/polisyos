"""Separate verifier-report authentication from PUBLIC decision authority.

This slice can issue a cryptographically authenticated report about retained
public-document bytes. It has no promoted PUBLIC decision record producer and
therefore cannot establish any of the seven PV-K01 authority dimensions.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    WrapValidator,
    model_validator,
)

_JSON_VALUE = TypeAdapter(JsonValue)


def _validate_public_decision_json_value(value: object, _handler: object) -> JsonValue:
    """Retain Pydantic's JSON validator while exposing its recursive wire type."""
    return _JSON_VALUE.validate_python(value, strict=True)


type PublicDecisionJsonValue = Annotated[
    str
    | int
    | float
    | bool
    | list[PublicDecisionJsonValue]
    | dict[str, PublicDecisionJsonValue]
    | None,
    WrapValidator(_validate_public_decision_json_value),
]

PUBLIC_VERIFICATION_PURPOSE = "public_decision_verification_record"
PUBLIC_VERIFICATION_RULE_VERSION = "public-decision-verification.v1"
PUBLIC_VERIFICATION_RECORD_KIND = "runtime.public_decision_verification_record"
PUBLIC_VERIFICATION_RECORD_SCHEMA = "polisyos.public_decision_verification_record"

PublicDecisionVerificationReason = Literal[
    "promoted_public_record_not_established",
    "client_token_not_server_issued",
    "record_not_issued",
    "issuance_index_invalid",
    "issuance_index_write_failed",
    "verification_issuer_not_configured",
    "public_document_invalid",
    "record_evidence_unavailable",
    "record_signature_missing",
    "record_signature_invalid",
    "record_key_untrusted",
    "record_key_revoked",
    "record_issuer_purpose_untrusted",
    "record_binding_invalid",
    "public_document_binding_invalid",
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class PublicDecisionVerificationDimensions(_StrictModel):
    """PV-K01 dimensions withheld until their actual owners provide evidence."""

    issuer_issuance: Literal["not_established"] = "not_established"
    projection_faithfulness: Literal["not_established"] = "not_established"
    public_history_establishment: Literal["not_established"] = "not_established"
    durable_verifiability: Literal["not_established"] = "not_established"
    current_authority: Literal["not_established"] = "not_established"
    status_snapshot_selection: Literal["not_established"] = "not_established"
    public_evidence_obtainability: Literal["not_established"] = "not_established"


class PublicDecisionVerificationRecord(_StrictModel):
    """Immutable signed report binding a public projection, never a promotion."""

    schema_version: Literal["polisyos.public_decision_verification_record.v1"] = (
        "polisyos.public_decision_verification_record.v1"
    )
    record_id: str = Field(pattern=r"^pvr_[A-Za-z0-9_-]{32}$")
    decision_id: str = Field(min_length=1, max_length=300)
    issuer_id: str = Field(min_length=1, max_length=300)
    signing_key_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    purpose: Literal["public_decision_verification_record"] = PUBLIC_VERIFICATION_PURPOSE
    rule_version: str = Field(min_length=1, max_length=100)
    issued_at: AwareDatetime
    public_document_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    publication_class: Literal["verification_report_only"] = "verification_report_only"
    promoted_record: Literal[None] = None


class PublicDecisionVerificationIssuanceIndex(_StrictModel):
    """Durable lookup binding an opaque issued ID to its expected signed subject."""

    record_id: str = Field(pattern=r"^pvr_[A-Za-z0-9_-]{32}$")
    record_artifact_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    decision_id: str = Field(min_length=1, max_length=300)
    issuer_id: str = Field(min_length=1, max_length=300)
    rule_version: str = Field(min_length=1, max_length=100)
    public_document_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class PublicDecisionVerificationResponse(_StrictModel):
    """Authentication result with document bytes exposed only after verification."""

    record_id: str
    report_authentication: Literal["verified", "invalid", "not_established"]
    cryptographic_signature: Literal["valid", "invalid", "not_established"] = "not_established"
    report_key_status: Literal["trusted", "revoked", "untrusted", "not_established"] = (
        "not_established"
    )
    reason_codes: tuple[PublicDecisionVerificationReason, ...]
    decision_id: str | None = None
    issuer_id: str | None = None
    issued_at: AwareDatetime | None = None
    public_document_digest: str | None = None
    public_document: dict[str, PublicDecisionJsonValue] | None = None
    promoted_record: Literal[None] = None
    dimensions: PublicDecisionVerificationDimensions = Field(
        default_factory=PublicDecisionVerificationDimensions
    )

    @model_validator(mode="after")
    def _require_authenticated_payload(self) -> Self:
        if self.report_authentication == "verified":
            if (
                self.cryptographic_signature != "valid"
                or self.report_key_status != "trusted"
                or self.public_document is None
                or self.decision_id is None
                or self.issuer_id is None
                or self.issued_at is None
                or self.public_document_digest is None
            ):
                raise ValueError("verified report requires authenticated document and identity")
        elif any(
            value is not None
            for value in (
                self.public_document,
                self.decision_id,
                self.issuer_id,
                self.issued_at,
                self.public_document_digest,
            )
        ):
            raise ValueError("unauthenticated report cannot expose signed payload")
        return self
