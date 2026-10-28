"""Deployment slots for the bounded registered-SQL source service."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts import ArtifactRef


class RegisteredSQLSourceSlot(BaseModel):
    """One configured service principal and exact registered view/use scope.

    A slot is a source selector and deployment policy input, not a verified
    producer observation or a source-admission authority by itself.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    slot_id: str = Field(min_length=1, max_length=256)
    issuer: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    registration_key: str = Field(min_length=1)
    registration_event_id: str = Field(min_length=1, max_length=256)
    issuer_key: str = Field(min_length=1, max_length=1024)
    effective_view_contract_ref: ArtifactRef
    use_contract_ref: ArtifactRef

    @field_validator(
        "slot_id",
        "issuer",
        "audience",
        "subject",
        "tenant_id",
        "cell_id",
        "provider_id",
        "connector_id",
        "registration_key",
        "registration_event_id",
        "issuer_key",
    )
    @classmethod
    def _require_canonical_identifiers(cls, value: str) -> str:
        if (
            not value
            or value != value.strip()
            or value.casefold()
            in {"unknown", "none", "null", "anonymous", "tenant-unknown", "cell-unknown"}
        ):
            raise ValueError("registered_sql_slot_identity_invalid")
        return value

    @model_validator(mode="after")
    def _require_selected_contracts(self) -> RegisteredSQLSourceSlot:
        if self.issuer != self.issuer.rstrip("/"):
            raise ValueError("registered_sql_slot_issuer_not_canonical")
        if (
            self.effective_view_contract_ref.manifest_profile_sha256 is None
            or self.use_contract_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("registered_sql_slot_selected_contract_required")
        return self

    @property
    def identity_key(self) -> tuple[str, str, str, str, str]:
        """Return the same identity tuple owned by deployment service grants."""
        return self.issuer, self.audience, self.subject, self.tenant_id, self.cell_id
