"""Strict subjects for bounded, exact-owner PUBLIC publication.

Institutional evidence and source addresses are private. Public proof metadata
depends only on the public document, public signing identity and random locator.
"""

from __future__ import annotations

from dataclasses import dataclass
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

from polisyos.core import artifacts

PUBLICATION_PURPOSE = "governed_public_record"
MANDATE_PURPOSE = "governed_public_record_mandate"
PUBLICATION_RULE = "governed-public-record.v1"
PUBLICATION_PROFILE = "exact_owner_ledger_v1"

_JSON_VALUE = TypeAdapter(JsonValue)


def _validate_governed_json_value(value: object, _handler: object) -> JsonValue:
    return _JSON_VALUE.validate_python(value, strict=True)


type GovernedPublicJsonValue = Annotated[
    str
    | int
    | float
    | bool
    | list[GovernedPublicJsonValue]
    | dict[str, GovernedPublicJsonValue]
    | None,
    WrapValidator(_validate_governed_json_value),
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class GovernedPublicRecordBoundaryRead(_StrictModel):
    """Private receipt of the actual read that supports an absence result."""

    operation: str
    selector: str
    outcome: Literal["read", "absent", "invalid", "unknown"]
    unresolved_by_construction: tuple[str, ...] = Field(
        default=("other_owner_stores", "unregistered_external_publications"),
        strict=False,
    )


class GovernedPublicRecordError(RuntimeError):
    """Fail-closed admission or readback result; receipts are never public DTOs."""

    def __init__(
        self, code: str, *, reads: tuple[GovernedPublicRecordBoundaryRead, ...] = ()
    ) -> None:
        super().__init__(code)
        self.code = code
        self.reads = reads


@dataclass(frozen=True, slots=True)
class PublicationTrustedKey:
    """Deployment trust policy, independently loaded from publication content."""

    public_key_pem: bytes
    issuer_id: str
    purposes: frozenset[str]
    revoked: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.public_key_pem) is not bytes
            or not self.public_key_pem
            or type(self.issuer_id) is not str
            or not self.issuer_id.strip()
            or type(self.purposes) is not frozenset
            or not self.purposes
            or any(type(item) is not str or not item.strip() for item in self.purposes)
            or type(self.revoked) is not bool
        ):
            raise ValueError("publication_trusted_key_invalid")


@dataclass(frozen=True, slots=True)
class PublicationSigningSlot:
    """Empty by default; possessing a signing key does not appoint its holder."""

    signer: artifacts.Ed25519Signer | None = None
    issuer_id: str | None = None
    publisher_trusted_keys: tuple[PublicationTrustedKey, ...] = ()
    mandate_trusted_keys: tuple[PublicationTrustedKey, ...] = ()
    mandate_ref: artifacts.ArtifactRef | None = None
    verifier_epoch: str | None = None
    purpose: Literal["governed_public_record"] = PUBLICATION_PURPOSE

    def __post_init__(self) -> None:
        if (
            (self.signer is not None and type(self.signer) is not artifacts.Ed25519Signer)
            or (
                self.issuer_id is not None
                and (type(self.issuer_id) is not str or not self.issuer_id.strip())
            )
            or (
                self.verifier_epoch is not None
                and (type(self.verifier_epoch) is not str or not self.verifier_epoch.strip())
            )
            or self.purpose != PUBLICATION_PURPOSE
            or type(self.publisher_trusted_keys) is not tuple
            or type(self.mandate_trusted_keys) is not tuple
            or any(
                type(key) is not PublicationTrustedKey
                for key in self.publisher_trusted_keys + self.mandate_trusted_keys
            )
            or (self.mandate_ref is not None and type(self.mandate_ref) is not artifacts.ArtifactRef)
        ):
            raise ValueError("publication_signing_slot_invalid")

    @classmethod
    def empty(cls) -> PublicationSigningSlot:
        """Return an explicitly unappointed production slot."""
        return cls()


class PublicationMandateStatement(_StrictModel):
    """Institution-signed appointment for one exact source and public document."""

    schema_version: Literal["polisyos.publication_mandate.v1"] = "polisyos.publication_mandate.v1"
    purpose: Literal["governed_public_record_mandate"] = MANDATE_PURPOSE
    authority_issuer_id: str = Field(min_length=1)
    authority_key_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    issuer_id: str = Field(min_length=1)
    signing_key_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    public_document_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    decision_packet_ref: artifacts.ArtifactRef
    owner_scope_ref: str = Field(min_length=1)
    ledger_artifact_ref: artifacts.ArtifactRef
    authority_basis: str = Field(min_length=1)
    permitted_uses: tuple[Literal["bounded_public_custody"], ...] = ("bounded_public_custody",)
    profile: Literal["exact_owner_ledger_v1"] = PUBLICATION_PROFILE
    rule_version: Literal["governed-public-record.v1"] = PUBLICATION_RULE
    issued_at: AwareDatetime
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    staleness_after_seconds: int = Field(gt=0)
    verifier_epoch: str = Field(min_length=1)

    @model_validator(mode="after")
    def _ordered_interval(self) -> Self:
        if self.valid_until <= self.valid_from or self.issued_at > self.valid_until:
            raise ValueError("publication_mandate_interval_invalid")
        if self.permitted_uses != ("bounded_public_custody",):
            raise ValueError("publication_mandate_uses_invalid")
        return self


class GovernedPublicRecordDraft(_StrictModel):
    """Private candidate locator plus the exact bytes an institution may approve."""

    candidate_ref: artifacts.ArtifactRef
    public_document: dict[str, GovernedPublicJsonValue]
    public_document_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class GovernedPublicRecord(_StrictModel):
    """Public signed subject, containing no private source or authorization refs."""

    schema_version: Literal["polisyos.governed_public_record.v1"] = (
        "polisyos.governed_public_record.v1"
    )
    record_id: str = Field(pattern=r"^gpr_[A-Za-z0-9_-]{32}$")
    decision_id: str = Field(min_length=1)
    issuer_id: str = Field(min_length=1)
    signing_key_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    purpose: Literal["governed_public_record"] = PUBLICATION_PURPOSE
    rule_version: Literal["governed-public-record.v1"] = PUBLICATION_RULE
    issued_at: AwareDatetime
    public_document_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    publication_class: Literal["governed_public_record"] = PUBLICATION_PURPOSE


class GovernedPublicRecordDimensions(_StrictModel):
    """Independent PV-K01 components; this profile establishes only two."""

    issuer_issuance: Literal["established", "not_established"] = "not_established"
    projection_faithfulness: Literal["established", "not_established"] = "not_established"
    public_history_establishment: Literal["not_established"] = "not_established"
    durable_verifiability: Literal["not_established"] = "not_established"
    current_authority: Literal["not_established"] = "not_established"
    status_snapshot_selection: Literal["not_established"] = "not_established"
    public_evidence_obtainability: Literal["not_established"] = "not_established"


class GovernedPublicRecordVerificationResponse(_StrictModel):
    """Distinct positive wire branch; failed verification exposes no content."""

    publication_class: Literal["governed_public_record"] = PUBLICATION_PURPOSE
    record_id: str
    report_authentication: Literal["verified", "invalid", "not_established"]
    cryptographic_signature: Literal["valid", "invalid", "not_established"] = "not_established"
    report_key_status: Literal["trusted", "revoked", "untrusted", "not_established"] = (
        "not_established"
    )
    reason_codes: tuple[str, ...] = ()
    decision_id: str | None = None
    issuer_id: str | None = None
    issued_at: AwareDatetime | None = None
    public_document_digest: str | None = None
    public_document: dict[str, GovernedPublicJsonValue] | None = None
    promoted_record: GovernedPublicRecord | None = None
    dimensions: GovernedPublicRecordDimensions = Field(
        default_factory=GovernedPublicRecordDimensions
    )

    @model_validator(mode="after")
    def _bind_verified_payload(self) -> Self:
        payload = (
            self.decision_id,
            self.issuer_id,
            self.issued_at,
            self.public_document_digest,
            self.public_document,
            self.promoted_record,
        )
        if self.report_authentication == "verified":
            if (
                self.cryptographic_signature != "valid"
                or self.report_key_status not in {"trusted", "revoked"}
                or any(value is None for value in payload)
                or self.reason_codes
                or self.dimensions.issuer_issuance != "established"
                or self.dimensions.projection_faithfulness != "established"
            ):
                raise ValueError("governed_public_verified_payload_required")
            record = self.promoted_record
            assert record is not None
            for field in (
                "record_id",
                "decision_id",
                "issuer_id",
                "issued_at",
                "public_document_digest",
            ):
                if getattr(self, field) != getattr(record, field):
                    raise ValueError("governed_public_record_binding_invalid")
        elif (
            any(value is not None for value in payload)
            or self.dimensions != GovernedPublicRecordDimensions()
        ):
            raise ValueError("governed_public_unverified_payload_forbidden")
        return self


class GovernedPublicCustodyBinding(_StrictModel):
    """Private owner resolution consumed by the installed custody provider."""

    record_id: str = Field(pattern=r"^gpr_[A-Za-z0-9_-]{32}$")
    signature_ref: artifacts.ArtifactRef
    decision_packet_ref: artifacts.ArtifactRef
    affected_claim_ids: tuple[str, ...] = Field(min_length=1)
    published_at: AwareDatetime
    staleness_after_seconds: int = Field(gt=0)
