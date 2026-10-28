"""Strict request and outcome types for registered-SQL admission."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.contracts.decision_validity import (
    SourceAdmissionCarrier,
    SourceAdmissionReceipt,
    SourceRegistrationReceipt,
)
from polisyos.core.contracts.fabric import DataViewRequestRef


class RegisteredSQLRegistrationRequest(BaseModel):
    """Request the configured source slot's idempotent genesis."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    slot_id: str = Field(min_length=1, max_length=256)
    event_id: str = Field(min_length=1, max_length=256)

    @field_validator("slot_id", "event_id")
    @classmethod
    def _canonical_identity(cls, value: str) -> str:
        if value != value.strip() or any(ord(character) < 33 for character in value):
            raise ValueError("registered_sql_request_identity_invalid")
        return value


class RegisteredSQLWithdrawalRequest(BaseModel):
    """Withdraw one exact original owner carrier at a given scope predecessor."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    slot_id: str = Field(min_length=1, max_length=256)
    event_id: str = Field(min_length=1, max_length=256)
    expected_predecessor: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    target: SourceAdmissionCarrier

    @field_validator("slot_id", "event_id")
    @classmethod
    def _canonical_identity(cls, value: str) -> str:
        if value != value.strip() or any(ord(character) < 33 for character in value):
            raise ValueError("registered_sql_request_identity_invalid")
        return value


class RegisteredSQLRegistrationResponse(BaseModel):
    """Return the committed source-owner genesis receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    registration: SourceRegistrationReceipt


class RegisteredSQLWithdrawalResponse(BaseModel):
    """Return the original committed withdrawal receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    receipt: SourceAdmissionReceipt

    @model_validator(mode="after")
    def _withdrawal(self) -> RegisteredSQLWithdrawalResponse:
        if self.receipt.operation != "withdraw":
            raise ValueError("registered_sql_withdrawal_receipt_mismatch")
        return self


class RegisteredSQLMaterializationRequest(BaseModel):
    """Request one exact registered source occurrence under a configured slot."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    slot_id: str = Field(min_length=1, max_length=256)
    request_ref: DataViewRequestRef
    event_id: str = Field(min_length=1, max_length=256)
    occurrence_id: str = Field(min_length=1, max_length=256)
    expected_predecessor: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("slot_id", "event_id", "occurrence_id")
    @classmethod
    def _canonical_identifier(cls, value: str) -> str:
        if value != value.strip() or any(ord(character) < 33 for character in value):
            raise ValueError("registered_sql_request_identity_invalid")
        return value

    @model_validator(mode="after")
    def _selected_request(self) -> RegisteredSQLMaterializationRequest:
        ref = self.request_ref
        if (
            ref.kind != "ir.data_view_request"
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
        ):
            raise ValueError("registered_sql_selected_request_required")
        return self


class RegisteredSQLMaterializationResponse(BaseModel):
    """Return source history and transport without claiming current use."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: Literal["committed"] = "committed"
    receipt: SourceAdmissionReceipt
    binding_ref: ArtifactRef
    current_use: Literal["not_checked"] = "not_checked"
    external_database_currentness: Literal["not_established"] = "not_established"

    @model_validator(mode="after")
    def _selected_binding(self) -> RegisteredSQLMaterializationResponse:
        if (
            self.receipt.operation != "admit"
            or self.receipt.carrier is None
            or self.binding_ref.kind != "fabric.registered_sql_admission_binding"
            or self.binding_ref.media_type != "application/json"
            or self.binding_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("registered_sql_receipt_not_bound")
        return self
