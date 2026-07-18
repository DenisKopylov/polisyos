"""Canonical owner resolution for acquisition admission.

The acquisition registry may extend the catalog with last-mile field edges, but
it cannot mint source, license, L5, or transport authority.  Those properties
are re-resolved from the immutable baseline catalog and the canonical L5
measurement registry every time an entry is used.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Self

import duckdb
import pandas as pd
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, canon, contracts
from polisyos.fabric import connectors as fabric_connectors
from polisyos.fabric import data_plane as fabric_data_plane

from .overlay import (
    AcquisitionDatasetRegistration,
    MetricFieldBinding,
    build_metric_field_binding,
)

ArtifactID = artifacts.ArtifactID
ArtifactStore = artifacts.ArtifactStore
DataSnapshot = contracts.DataSnapshot
DataSnapshotRef = contracts.DataSnapshotRef
EvidenceBundle = contracts.EvidenceBundle
EvidenceBundleRef = contracts.EvidenceBundleRef
FetchResult = fabric_connectors.FetchResult
JournalEventRef = fabric_data_plane.JournalEventRef
LiveExecutionAuthorization = fabric_data_plane.LiveExecutionAuthorization
ResultSerializer = fabric_connectors.ResultSerializer
SourceProfileRegistry = fabric_connectors.SourceProfileRegistry
canonical_json_bytes = fabric_data_plane.canonical_json_bytes
from_canonical_bytes = canon.from_canonical_bytes

ACQUISITION_AUTHORITY_SCHEMA_VERSION = "polisyos.data_forge.acquisition_authority.v1"
ACQUISITION_AUTHORITY_PROVISION_SCHEMA_VERSION = (
    "polisyos.data_forge.acquisition_authority_provision.v1"
)
LIVE_SOURCE_EXECUTION_EVIDENCE_SCHEMA_VERSION = (
    "polisyos.data_forge.live_source_execution_evidence.v1"
)
LOCAL_SOURCE_RIGHTS_RECEIPT_SCHEMA_VERSION = (
    "polisyos.data_forge.local_source_rights_receipt.v1"
)
LOCAL_SOURCE_RIGHTS_DECLARATION_SCHEMA_VERSION = (
    "polisyos.data_forge.local_source_rights_declaration.v1"
)
LOCAL_RIGHTS_TRUST_REGISTRY_SCHEMA_VERSION = (
    "polisyos.data_forge.local_rights_trust_registry.v1"
)
DEFAULT_ACQUISITION_AUTHORITY_REGISTRY = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_registry.json"
)
DEFAULT_ACQUISITION_AUTHORITY_PROVISION = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_provision.json"
)
DEFAULT_LOCAL_RIGHTS_TRUST_REGISTRY = Path(
    "architecture/policy_design_case/layer3_gy_n13b_local_rights_trust.json"
)
DEFAULT_L5_MEASUREMENT_REGISTRY = Path(
    "production_data/canonical/local_data_20260501/"
    "ukraine_server_support_20260410/runtime_calibration_internals/"
    "calibration/d2/measurement_registry.json"
)
_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_PROVISION_CONSTRUCTION_TOKEN = object()


class AcquisitionAuthorityError(RuntimeError):
    """Fail-closed canonical authority resolution error."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail or code}")


class LicenseDisposition(StrEnum):
    """Disposition recomputed from a narrow known-license policy."""

    ADMISSIBLE_OPEN = "admissible_open"
    UNCLEAR = "unclear"
    RESTRICTED = "restricted"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AuthoritySchemaColumn(_StrictModel):
    """One declared normalized response field carried on the request."""

    name: str = Field(min_length=1)
    logical_types: tuple[str, ...] = Field(min_length=1)
    nullable: bool

    @model_validator(mode="after")
    def _types_are_normalized(self) -> Self:
        if self.logical_types != tuple(sorted(set(self.logical_types))):
            raise ValueError("schema logical types must be unique and sorted")
        return self


class LocalRightsTrustedAuthority(_StrictModel):
    """One signature trust root for independently owned local-source rights."""

    authority_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    rights_authority: str = Field(min_length=1)
    authority_ref: str = Field(pattern=r"^https://[^\s]+$")
    ed25519_public_key_base64: str = Field(min_length=1)
    admissible_license_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _trust_root_is_decisive(self) -> Self:
        if self.admissible_license_ids != tuple(
            sorted(set(self.admissible_license_ids))
        ):
            raise ValueError("trusted license ids must be unique and sorted")
        try:
            key = base64.b64decode(self.ed25519_public_key_base64, validate=True)
            Ed25519PublicKey.from_public_bytes(key)
        except Exception as exc:
            raise ValueError("trusted Ed25519 public key is invalid") from exc
        return self


class LocalRightsTrustRegistry(_StrictModel):
    """Content-derived trust roots used only for signed local rights evidence."""

    schema_version: Literal[
        "polisyos.data_forge.local_rights_trust_registry.v1"
    ] = LOCAL_RIGHTS_TRUST_REGISTRY_SCHEMA_VERSION
    authorities: tuple[LocalRightsTrustedAuthority, ...]
    content_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _registry_is_recomputed(self) -> Self:
        ids = tuple(authority.authority_id for authority in self.authorities)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("local rights trust roots must be unique and sorted")
        expected = fabric_data_plane.content_sha256(
            {
                "schema_version": self.schema_version,
                "authorities": [
                    authority.model_dump(mode="json")
                    for authority in self.authorities
                ],
            }
        )
        if self.content_sha256 != expected:
            raise ValueError("local rights trust registry identity must be recomputed")
        return self


class AcquisitionAuthorityProvision(_StrictModel):
    """Separately produced trust anchor for acquisition authority resolution."""

    schema_version: Literal[
        "polisyos.data_forge.acquisition_authority_provision.v1"
    ] = ACQUISITION_AUTHORITY_PROVISION_SCHEMA_VERSION
    provision_id: str = Field(
        pattern=r"^acquisition-authority-provision:sha256:[0-9a-f]{64}$"
    )
    baseline_owner_ref: str = Field(pattern=r"^(repo|provision)://[^\s]+$")
    baseline_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    local_rights_trust_anchor_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    authority_purpose: Literal[
        "resolve_baseline_and_local_rights_trust_only"
    ] = "resolve_baseline_and_local_rights_trust_only"
    may_not_use_for: tuple[
        Literal["acquisition_registry_self_authorization"]
    ] = ("acquisition_registry_self_authorization",)

    @model_validator(mode="after")
    def _identity_is_recomputed(self) -> Self:
        expected = "acquisition-authority-provision:" + (
            fabric_data_plane.content_sha256(self.identity_payload())
        )
        if self.provision_id != expected:
            raise ValueError("acquisition authority provision identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the trust projection defining this provision receipt."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "provision_id"
        }


class LocalSourceRightsDeclaration(_StrictModel):
    """Owner-supplied, content-derived declaration for one local source."""

    schema_version: Literal[
        "polisyos.data_forge.local_source_rights_declaration.v1"
    ] = LOCAL_SOURCE_RIGHTS_DECLARATION_SCHEMA_VERSION
    declaration_id: str = Field(
        pattern=r"^local-rights-declaration:sha256:[0-9a-f]{64}$"
    )
    source_path: str = Field(min_length=1)
    source_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    license_id: str = Field(min_length=1)
    authority_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    rights_authority: str = Field(min_length=1)
    authority_ref: str = Field(pattern=r"^https://[^\s]+$")
    signature_base64: str = Field(min_length=1)

    @model_validator(mode="after")
    def _identity_and_path_are_recomputed(self) -> Self:
        path = Path(self.source_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("local rights declaration path must be repo-relative")
        try:
            signature = base64.b64decode(self.signature_base64, validate=True)
        except Exception as exc:
            raise ValueError("local rights declaration signature is invalid") from exc
        if len(signature) != 64:
            raise ValueError("local rights declaration signature is invalid")
        expected = "local-rights-declaration:" + fabric_data_plane.content_sha256(
            self.identity_payload()
        )
        if self.declaration_id != expected:
            raise ValueError("local rights declaration identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the projection defining this owner declaration."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "declaration_id"
        }

    def signed_payload(self) -> dict[str, object]:
        """Return exact bytes that the owner signature must cover."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key not in {"declaration_id", "signature_base64"}
        }


class LocalSourceRightsReceipt(_StrictModel):
    """Verifier-produced evidence binding a source to an owner declaration."""

    schema_version: Literal[
        "polisyos.data_forge.local_source_rights_receipt.v1"
    ] = LOCAL_SOURCE_RIGHTS_RECEIPT_SCHEMA_VERSION
    receipt_id: str = Field(pattern=r"^local-rights:sha256:[0-9a-f]{64}$")
    source_path: str = Field(min_length=1)
    source_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    license_id: str = Field(min_length=1)
    authority_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    rights_authority: str = Field(min_length=1)
    authority_ref: str = Field(pattern=r"^https://[^\s]+$")
    rights_document_path: str = Field(min_length=1)
    rights_document_sha256: str = Field(pattern=_SHA256_PATTERN)
    rights_declaration_id: str = Field(
        pattern=r"^local-rights-declaration:sha256:[0-9a-f]{64}$"
    )
    trust_registry_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    public_key_sha256: str = Field(pattern=_SHA256_PATTERN)
    verifier_ref: Literal[
        "polisyos.data_forge.verify_local_source_rights/v1"
    ] = "polisyos.data_forge.verify_local_source_rights/v1"
    verification_method: Literal["content_bound_owner_document"] = (
        "content_bound_owner_document"
    )

    @model_validator(mode="after")
    def _identity_and_paths_are_recomputed(self) -> Self:
        for value in (self.source_path, self.rights_document_path):
            path = Path(value)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("local rights receipt paths must be repo-relative")
        expected = "local-rights:" + fabric_data_plane.content_sha256(
            self.identity_payload()
        )
        if self.receipt_id != expected:
            raise ValueError("local rights receipt identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the projection defining this rights receipt."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "receipt_id"
        }


class AcquisitionAuthorityEntry(_StrictModel):
    """Registry-owned last-mile edge whose upstream facts remain owner-resolved."""

    entry_id: str = Field(pattern=r"^acquisition-authority:sha256:[0-9a-f]{64}$")
    source_lane: Literal["local_lift", "live_fetch"]
    target_variable: str = Field(min_length=1)
    landing_dataset_id: str = Field(min_length=1)
    landing_distribution_id: str = Field(min_length=1)
    source_catalog_dataset_id: str | None = None
    source_catalog_distribution_id: str | None = None
    upstream_metric_id: str | None = None
    catalog_raw_variable: str | None = None
    raw_field: str = Field(min_length=1)
    raw_unit: str = Field(min_length=1)
    canonical_unit: str = Field(min_length=1)
    unit_transform: str = Field(min_length=1)
    unit_transform_ref: str = Field(min_length=1)
    alignment_method: Literal["exact", "semantic", "meta_analytic"]
    alignment_confidence: float = Field(ge=0.0, le=1.0)
    is_proxy: bool
    proxy_penalty: float = Field(ge=0.0, le=1.0)
    aggregation_method: Literal["identity", "mean", "sum", "last"]
    valid_min: float | None = None
    valid_max: float | None = None
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    schema_contract_ref: str = Field(min_length=1)
    schema_columns: tuple[AuthoritySchemaColumn, ...] = Field(min_length=1)
    l5_family_id: str = Field(min_length=1)
    local_source_path: str | None = None
    local_source_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    local_license_id: str | None = None
    local_rights_receipt_path: str | None = None
    local_rights_receipt_sha256: str | None = Field(
        default=None,
        pattern=_SHA256_PATTERN,
    )
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    country_codes: tuple[str, ...] = Field(min_length=1)
    temporal_start: str | None = None
    temporal_end: str | None = None

    @model_validator(mode="after")
    def _entry_is_narrow_and_content_bound(self) -> Self:
        names = tuple(column.name for column in self.schema_columns)
        if names != tuple(sorted(set(names))):
            raise ValueError("authority schema columns must be unique and sorted")
        if self.raw_field not in names:
            raise ValueError("authority raw field must travel in the schema contract")
        if self.alignment_method == "exact" and (
            self.raw_field != self.target_variable
            or abs(self.alignment_confidence - 1.0) > 1e-9
        ):
            raise ValueError("exact authority alignment requires an identical variable")
        if any(ref.startswith(("self://", "inline://")) for ref in self.evidence_refs):
            raise ValueError("authority evidence cannot be self-authored")
        if not self.unit_transform_ref.startswith(("repo://", "fabric://")):
            raise ValueError("unit transform requires a resolvable owner ref")
        live_fields = (
            self.source_catalog_dataset_id,
            self.source_catalog_distribution_id,
            self.upstream_metric_id,
            self.catalog_raw_variable,
        )
        if self.source_lane == "live_fetch" and not all(live_fields):
            raise ValueError("live authority entry requires its complete catalog edge")
        local_fields = (
            self.local_source_path,
            self.local_source_sha256,
            self.local_license_id,
            self.local_rights_receipt_path,
            self.local_rights_receipt_sha256,
        )
        if self.source_lane == "live_fetch" and any(local_fields):
            raise ValueError("live authority entry cannot carry local authority fields")
        if self.source_lane == "local_lift" and any(live_fields):
            raise ValueError("local authority entry cannot carry live catalog fields")
        if self.source_lane == "local_lift" and not (
            all(local_fields)
        ):
            raise ValueError(
                "local authority entry requires independent content-bound rights evidence"
            )
        if self.entry_id != "acquisition-authority:" + fabric_data_plane.content_sha256(
            self.identity_payload()
        ):
            raise ValueError("authority entry identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the narrow projection defining this last-mile entry."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "entry_id"
        }

    def schema_projection(self) -> dict[str, object]:
        """Return the C1 schema projection that must travel with a request."""

        return {
            "schema_contract_ref": self.schema_contract_ref,
            "columns": [column.model_dump(mode="json") for column in self.schema_columns],
        }


class AcquisitionAuthorityRegistry(_StrictModel):
    """Content-bound registry of all executable acquisition field edges."""

    schema_version: Literal[ACQUISITION_AUTHORITY_SCHEMA_VERSION] = (
        ACQUISITION_AUTHORITY_SCHEMA_VERSION
    )
    baseline_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    l5_measurement_registry_sha256: str = Field(pattern=_SHA256_PATTERN)
    entries: tuple[AcquisitionAuthorityEntry, ...]
    content_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _registry_is_recomputed(self) -> Self:
        ids = tuple(entry.entry_id for entry in self.entries)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("authority entries must be unique and sorted")
        expected = fabric_data_plane.content_sha256(
            {
                "schema_version": self.schema_version,
                "baseline_content_sha256": self.baseline_content_sha256,
                "l5_measurement_registry_sha256": self.l5_measurement_registry_sha256,
                "entries": [entry.model_dump(mode="json") for entry in self.entries],
            }
        )
        if self.content_sha256 != expected:
            raise ValueError("authority registry identity must be recomputed")
        return self


class ResolvedL5Trust(_StrictModel):
    """L5 trust projection recomputed from the canonical measurement registry."""

    family_id: str
    tier: str
    trust_cap: float = Field(ge=0.0, le=1.0)
    trust_multiplier: float = Field(ge=0.0, le=1.0)
    authority_ref: str
    owner_ref: str
    owner_content_sha256: str = Field(pattern=_SHA256_PATTERN)


class ResolvedAcquisitionAuthority(_StrictModel):
    """Independent owner result consumed by passport and overlay admission."""

    entry: AcquisitionAuthorityEntry
    authority_provision_id: str = Field(
        pattern=r"^acquisition-authority-provision:sha256:[0-9a-f]{64}$"
    )
    authority_provision_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    registry_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    baseline_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    field_binding: MetricFieldBinding
    registration: AcquisitionDatasetRegistration
    license_id: str
    license_disposition: LicenseDisposition
    license_authority_ref: str = Field(min_length=1)
    license_authority_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    l5_trust: ResolvedL5Trust
    upstream_catalog_projection_sha256: str = Field(pattern=_SHA256_PATTERN)
    effective_authority_score: float = Field(ge=0.0, le=1.0)


class LiveSourceExecutionEvidence(_StrictModel):
    """Content-derived proof binding raw HTTP and normalized Fabric carriers."""

    schema_version: Literal[
        "polisyos.data_forge.live_source_execution_evidence.v1"
    ] = LIVE_SOURCE_EXECUTION_EVIDENCE_SCHEMA_VERSION
    authorization: LiveExecutionAuthorization
    family_receipt: dict[str, Any]
    family_receipt_sha256: str = Field(pattern=_SHA256_PATTERN)
    request_ref: JournalEventRef
    raw_evidence_ref: JournalEventRef
    raw_artifact_id: ArtifactID
    evidence_bundle_ref: EvidenceBundleRef
    data_snapshot_ref: DataSnapshotRef
    normalized_data_artifact_id: ArtifactID
    call_count: Literal[1]
    variable_count: Literal[1]
    page_count: Literal[1]
    baseline_before_sha256: str = Field(pattern=_SHA256_PATTERN)
    baseline_after_sha256: str = Field(pattern=_SHA256_PATTERN)
    raw_body_sha256: str = Field(pattern=_SHA256_PATTERN)
    normalized_result_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    content_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _identity_and_decisive_links_are_recomputed(self) -> Self:
        receipt_hash = fabric_data_plane.content_sha256(self.family_receipt)
        if (
            self.family_receipt_sha256 != receipt_hash
            or self.authorization.harness.family_receipt_sha256 != receipt_hash
        ):
            raise ValueError("live execution family receipt identity must be recomputed")
        if self.request_ref.event_kind != "request":
            raise ValueError("live execution request ref must address a request event")
        if self.raw_evidence_ref.event_kind != "raw_response":
            raise ValueError("live execution raw ref must address a raw-response event")
        if (
            self.request_ref.journal_path != self.raw_evidence_ref.journal_path
            or self.request_ref.sequence >= self.raw_evidence_ref.sequence
        ):
            raise ValueError("live execution journal refs must form one ordered carrier")
        if (
            self.baseline_before_sha256 != self.baseline_after_sha256
            or self.baseline_before_sha256 != self.authorization.baseline_sha256
        ):
            raise ValueError("live execution baseline must remain immutable")
        if self.raw_body_sha256 != self.normalized_result_content_sha256:
            raise ValueError("normalized result must version the exact raw HTTP body")
        if self.content_sha256 != fabric_data_plane.content_sha256(
            self.identity_payload()
        ):
            raise ValueError("live execution evidence identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return every decisive field except the derived evidence identity."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "content_sha256"
        }


def build_live_source_execution_evidence(
    *,
    authorization: LiveExecutionAuthorization,
    family_receipt: Mapping[str, Any],
    request_ref: JournalEventRef,
    raw_evidence_ref: JournalEventRef,
    raw_artifact_id: str | ArtifactID,
    evidence_bundle_ref: EvidenceBundleRef,
    data_snapshot_ref: DataSnapshotRef,
    normalized_data_artifact_id: str | ArtifactID,
    call_count: int,
    variable_count: int,
    page_count: int,
    baseline_before_sha256: str,
    baseline_after_sha256: str,
    raw_body_sha256: str,
    normalized_result_content_sha256: str,
) -> LiveSourceExecutionEvidence:
    """Build strict dual-carrier evidence without accepting a caller-pinned identity."""

    values = {
        "authorization": authorization,
        "family_receipt": dict(family_receipt),
        "family_receipt_sha256": fabric_data_plane.content_sha256(family_receipt),
        "request_ref": request_ref,
        "raw_evidence_ref": raw_evidence_ref,
        "raw_artifact_id": ArtifactID.model_validate(raw_artifact_id),
        "evidence_bundle_ref": evidence_bundle_ref,
        "data_snapshot_ref": data_snapshot_ref,
        "normalized_data_artifact_id": ArtifactID.model_validate(
            normalized_data_artifact_id
        ),
        "call_count": call_count,
        "variable_count": variable_count,
        "page_count": page_count,
        "baseline_before_sha256": baseline_before_sha256,
        "baseline_after_sha256": baseline_after_sha256,
        "raw_body_sha256": raw_body_sha256,
        "normalized_result_content_sha256": normalized_result_content_sha256,
    }
    provisional = LiveSourceExecutionEvidence.model_construct(
        **values,
        content_sha256="sha256:" + "0" * 64,
    )
    return LiveSourceExecutionEvidence(
        **values,
        content_sha256=fabric_data_plane.content_sha256(
            provisional.identity_payload()
        ),
    )


def build_authority_entry(**values: object) -> AcquisitionAuthorityEntry:
    """Build one content-bound authority entry without accepting a pinned id."""

    provisional = AcquisitionAuthorityEntry.model_construct(
        entry_id="acquisition-authority:sha256:" + "0" * 64,
        **values,
    )
    identity = provisional.identity_payload()
    return AcquisitionAuthorityEntry(
        entry_id="acquisition-authority:" + fabric_data_plane.content_sha256(identity),
        **values,
    )


def build_acquisition_authority_provision(
    **values: object,
) -> AcquisitionAuthorityProvision:
    """Build the separately persisted resolver provision without a pinned id."""

    provisional = AcquisitionAuthorityProvision.model_construct(
        provision_id="acquisition-authority-provision:sha256:" + "0" * 64,
        **values,
    )
    return AcquisitionAuthorityProvision(
        provision_id=(
            "acquisition-authority-provision:"
            + fabric_data_plane.content_sha256(provisional.identity_payload())
        ),
        **values,
    )


def build_local_source_rights_declaration(
    **values: object,
) -> LocalSourceRightsDeclaration:
    """Format an owner declaration; authority is earned only when it is resolved."""

    provisional = LocalSourceRightsDeclaration.model_construct(
        declaration_id="local-rights-declaration:sha256:" + "0" * 64,
        **values,
    )
    return LocalSourceRightsDeclaration(
        declaration_id=(
            "local-rights-declaration:"
            + fabric_data_plane.content_sha256(provisional.identity_payload())
        ),
        **values,
    )


def build_local_rights_trust_registry(
    *,
    authorities: tuple[LocalRightsTrustedAuthority, ...],
) -> LocalRightsTrustRegistry:
    """Build a byte-stable registry from separately provisioned public keys."""

    ordered = tuple(sorted(authorities, key=lambda item: item.authority_id))
    projection = {
        "schema_version": LOCAL_RIGHTS_TRUST_REGISTRY_SCHEMA_VERSION,
        "authorities": [item.model_dump(mode="json") for item in ordered],
    }
    return LocalRightsTrustRegistry(
        authorities=ordered,
        content_sha256=fabric_data_plane.content_sha256(projection),
    )


def verify_local_source_rights(
    *,
    repo_root: Path,
    source_path: str,
    rights_document_path: str,
    trust_registry_path: str = DEFAULT_LOCAL_RIGHTS_TRUST_REGISTRY.as_posix(),
) -> LocalSourceRightsReceipt:
    """Reopen source and owner declaration bytes and derive a verifier receipt."""

    root = Path(repo_root).resolve()
    source_relative = _safe_repo_relative_path(source_path, code="local_source_path")
    document_relative = _safe_repo_relative_path(
        rights_document_path,
        code="local_rights_document_path",
    )
    trust_relative = _safe_repo_relative_path(
        trust_registry_path,
        code="local_rights_trust_registry_path",
    )
    receipt, _, _ = _derive_local_source_rights_receipt(
        root=root,
        source_relative=source_relative,
        document_relative=document_relative,
        trust_relative=trust_relative,
        expected_trust_file_sha256=None,
    )
    return receipt


def build_authority_registry(
    *,
    baseline_content_sha256: str,
    l5_measurement_registry_sha256: str,
    entries: tuple[AcquisitionAuthorityEntry, ...],
) -> AcquisitionAuthorityRegistry:
    """Build a byte-stable registry model from sorted entries."""

    ordered = tuple(sorted(entries, key=lambda entry: entry.entry_id))
    projection = {
        "schema_version": ACQUISITION_AUTHORITY_SCHEMA_VERSION,
        "baseline_content_sha256": baseline_content_sha256,
        "l5_measurement_registry_sha256": l5_measurement_registry_sha256,
        "entries": [entry.model_dump(mode="json") for entry in ordered],
    }
    return AcquisitionAuthorityRegistry(
        baseline_content_sha256=baseline_content_sha256,
        l5_measurement_registry_sha256=l5_measurement_registry_sha256,
        entries=ordered,
        content_sha256=fabric_data_plane.content_sha256(projection),
    )


class CanonicalAcquisitionAuthority:
    """Resolver that reopens every decisive owner instead of trusting callers."""

    def __init__(
        self,
        *,
        repo_root: Path,
        baseline_path: Path,
        provision: AcquisitionAuthorityProvision,
        provision_content_sha256: str,
        _construction_token: object,
    ) -> None:
        if _construction_token is not _PROVISION_CONSTRUCTION_TOKEN:
            raise TypeError("use CanonicalAcquisitionAuthority.from_provision")
        self.repo_root = Path(repo_root).resolve()
        self.baseline_path = Path(baseline_path).resolve()
        self.provision = provision
        self.provision_content_sha256 = provision_content_sha256
        self.baseline_owner_ref = provision.baseline_owner_ref
        self.local_rights_trust_anchor_sha256 = (
            provision.local_rights_trust_anchor_sha256
        )
        self.registry_path = self.repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
        self.local_rights_trust_path = (
            self.repo_root / DEFAULT_LOCAL_RIGHTS_TRUST_REGISTRY
        )
        self.l5_path = self.repo_root / DEFAULT_L5_MEASUREMENT_REGISTRY

    @classmethod
    def from_provision(
        cls,
        *,
        repo_root: Path,
        baseline_path: Path,
    ) -> CanonicalAcquisitionAuthority:
        """Load the canonical provision receipt; callers cannot choose its anchors."""

        root = Path(repo_root).resolve()
        provision, provision_content_sha256 = _load_authority_provision(
            root / DEFAULT_ACQUISITION_AUTHORITY_PROVISION
        )
        baseline = Path(baseline_path).resolve()
        if _file_sha256(baseline) != provision.baseline_content_sha256:
            raise AcquisitionAuthorityError("provision_baseline_identity_drift")
        return cls(
            repo_root=root,
            baseline_path=baseline,
            provision=provision,
            provision_content_sha256=provision_content_sha256,
            _construction_token=_PROVISION_CONSTRUCTION_TOKEN,
        )

    def resolve(self, entry_id: str) -> ResolvedAcquisitionAuthority:
        """Resolve one entry against fresh registry, catalog, license, and L5 bytes."""

        self._require_provision_unchanged()
        registry = self._load_registry()
        matches = [entry for entry in registry.entries if entry.entry_id == entry_id]
        if len(matches) != 1:
            raise AcquisitionAuthorityError("authority_entry_unresolved", entry_id)
        entry = matches[0]
        if entry.source_lane == "live_fetch":
            (
                projection,
                license_id,
                license_authority_ref,
                license_authority_sha256,
                registration,
            ) = self._resolve_live_catalog(entry)
        else:
            (
                projection,
                license_id,
                license_authority_ref,
                license_authority_sha256,
                registration,
            ) = self._resolve_local_source(
                entry,
                expected_trust_registry_sha256=(
                    self.local_rights_trust_anchor_sha256
                ),
            )
        self._require_landing_identifiers_new(entry)
        disposition = _license_disposition(license_id)
        if disposition is not LicenseDisposition.ADMISSIBLE_OPEN:
            raise AcquisitionAuthorityError("license_not_admissible", license_id)
        l5 = self._resolve_l5(
            entry.l5_family_id,
            expected_content_sha256=registry.l5_measurement_registry_sha256,
        )
        binding = build_metric_field_binding(
            dataset_id=entry.landing_dataset_id,
            distribution_id=entry.landing_distribution_id,
            raw_field=entry.raw_field,
            canonical_variable=entry.target_variable,
            raw_unit=entry.raw_unit,
            canonical_unit=entry.canonical_unit,
            unit_transform=entry.unit_transform,
            unit_transform_ref=entry.unit_transform_ref,
            alignment_method=entry.alignment_method,
            alignment_confidence=entry.alignment_confidence,
            is_proxy=entry.is_proxy,
            proxy_penalty=entry.proxy_penalty,
            evidence_refs=entry.evidence_refs,
            aggregation_method=entry.aggregation_method,
            valid_min=entry.valid_min,
            valid_max=entry.valid_max,
        )
        registration = registration.model_copy(update={"field_binding": binding})
        proxy_factor = 1.0 - entry.proxy_penalty if entry.is_proxy else 1.0
        score = round(
            min(
                l5.trust_cap,
                binding.calibrated_alignment_confidence
                * proxy_factor
                * l5.trust_multiplier,
            ),
            6,
        )
        return ResolvedAcquisitionAuthority(
            entry=entry,
            authority_provision_id=self.provision.provision_id,
            authority_provision_content_sha256=self.provision_content_sha256,
            registry_content_sha256=registry.content_sha256,
            baseline_content_sha256=registry.baseline_content_sha256,
            field_binding=binding,
            registration=registration,
            license_id=license_id,
            license_disposition=disposition,
            license_authority_ref=license_authority_ref,
            license_authority_content_sha256=license_authority_sha256,
            l5_trust=l5,
            upstream_catalog_projection_sha256=fabric_data_plane.content_sha256(projection),
            effective_authority_score=score,
        )

    def _require_provision_unchanged(self) -> None:
        provision, content_sha256 = _load_authority_provision(
            self.repo_root / DEFAULT_ACQUISITION_AUTHORITY_PROVISION
        )
        if provision != self.provision or content_sha256 != self.provision_content_sha256:
            raise AcquisitionAuthorityError("acquisition_authority_provision_drift")
        if _file_sha256(self.baseline_path) != provision.baseline_content_sha256:
            raise AcquisitionAuthorityError("provision_baseline_identity_drift")

    def _require_landing_identifiers_new(
        self,
        entry: AcquisitionAuthorityEntry,
    ) -> None:
        """Keep acquisition identities disjoint from immutable epoch zero."""

        con = duckdb.connect(str(self.baseline_path), read_only=True)
        try:
            dataset_collision = int(
                con.execute(
                    "SELECT count(*) FROM ds_datasets WHERE id = ?",
                    [entry.landing_dataset_id],
                ).fetchone()[0]
                or 0
            )
            distribution_collision = int(
                con.execute(
                    "SELECT count(*) FROM ds_distributions WHERE id = ?",
                    [entry.landing_distribution_id],
                ).fetchone()[0]
                or 0
            )
        finally:
            con.close()
        if dataset_collision or distribution_collision:
            raise AcquisitionAuthorityError(
                "landing_identifier_collides_with_epoch_zero",
                f"{entry.landing_dataset_id}:{entry.landing_distribution_id}",
            )

    def verify_source_body(self, entry_id: str, body: bytes) -> bool:
        """Verify local carrier bytes directly; live carriers require E7 authorization."""

        resolved = self.resolve(entry_id)
        if resolved.entry.source_lane != "local_lift":
            return False
        source_path = self.repo_root / str(resolved.entry.local_source_path)
        return source_path.read_bytes() == body

    def resolve_live_source_execution(
        self,
        entry_id: str,
        evidence: LiveSourceExecutionEvidence,
        artifact_store: ArtifactStore,
    ) -> FetchResult[Any]:
        """Reopen and verify both carriers of one authorized live execution.

        The raw HTTP response remains the journal/CAS evidence carrier.  The
        normalized ``FetchResult`` is accepted only through the exact
        ``DataSnapshot.data_ref`` produced by Fabric orchestration.  No caller
        supplied rows participate in this decision.
        """

        try:
            proof = LiveSourceExecutionEvidence.model_validate(
                evidence.model_dump(mode="json")
                if isinstance(evidence, LiveSourceExecutionEvidence)
                else evidence
            )
            resolved = self.resolve(entry_id)
            if resolved.entry.source_lane != "live_fetch":
                raise AcquisitionAuthorityError("live_source_lane_required")
            self._verify_live_owner_projection(resolved, proof)
            self._verify_live_journal_carrier(resolved, proof)
            raw_body = fabric_data_plane.resolve_raw_response_body(
                proof.raw_evidence_ref
            )
            raw_hash = f"sha256:{hashlib.sha256(raw_body).hexdigest()}"
            if raw_hash != proof.raw_body_sha256:
                raise AcquisitionAuthorityError("live_raw_body_identity_drift")
            raw_cas = self._reopen_artifact(
                artifact_store,
                proof.raw_artifact_id,
                expected_kind="fabric.acquisition.raw_evidence",
            )
            if raw_cas != raw_body:
                raise AcquisitionAuthorityError("live_raw_journal_cas_mismatch")

            evidence_bundle = EvidenceBundle.model_validate(
                from_canonical_bytes(
                    self._reopen_artifact_ref(
                        artifact_store,
                        proof.evidence_bundle_ref,
                        expected_kind="fabric.evidence_bundle",
                    )
                )
            )
            snapshot = DataSnapshot.model_validate(
                from_canonical_bytes(
                    self._reopen_artifact_ref(
                        artifact_store,
                        proof.data_snapshot_ref,
                        expected_kind="fabric.data_snapshot",
                    )
                )
            )
            if snapshot.evidence_ref != proof.evidence_bundle_ref:
                raise AcquisitionAuthorityError("live_snapshot_evidence_ref_drift")
            if snapshot.data_ref.artifact_id != proof.normalized_data_artifact_id:
                raise AcquisitionAuthorityError("live_snapshot_data_ref_drift")
            if evidence_bundle.sources != [snapshot.data_ref]:
                raise AcquisitionAuthorityError("live_evidence_bundle_source_drift")
            if snapshot.stats.get("datasets_fetched") != 1:
                raise AcquisitionAuthorityError("live_snapshot_not_one_call")

            normalized_bytes = self._reopen_artifact_ref(
                artifact_store,
                snapshot.data_ref,
            )
            result = ResultSerializer.deserialize(normalized_bytes)
            self._verify_live_normalized_result(resolved, proof, result)
            return result
        except AcquisitionAuthorityError:
            raise
        except Exception as exc:
            raise AcquisitionAuthorityError(
                "live_source_execution_invalid",
                type(exc).__name__,
            ) from exc

    def resolve_live_source_body(
        self,
        entry_id: str,
        evidence: LiveSourceExecutionEvidence,
        artifact_store: ArtifactStore,
    ) -> bytes:
        """Return deterministic normalized rows after full dual-carrier verification."""

        result = self.resolve_live_source_execution(entry_id, evidence, artifact_store)
        return _normalized_fetch_result_body(result)

    def _verify_live_owner_projection(
        self,
        resolved: ResolvedAcquisitionAuthority,
        proof: LiveSourceExecutionEvidence,
    ) -> None:
        actual_baseline = _file_sha256(self.baseline_path)
        if (
            actual_baseline != resolved.baseline_content_sha256
            or actual_baseline != proof.baseline_before_sha256
            or actual_baseline != proof.baseline_after_sha256
            or actual_baseline != proof.authorization.baseline_sha256
        ):
            raise AcquisitionAuthorityError("live_baseline_identity_drift")
        try:
            fabric_data_plane.require_authorized_execution(
                proof.authorization,
                family_receipt=proof.family_receipt,
            )
        except Exception as exc:
            raise AcquisitionAuthorityError(
                "live_harness_authorization_invalid",
                type(exc).__name__,
            ) from exc
        registration = resolved.registration
        authorization = proof.authorization
        if (
            authorization.connector_id != registration.connector_id
            or authorization.profile_id != registration.source_profile_id
            or authorization.request_variables
            != (registration.request_dataset_id,)
        ):
            raise AcquisitionAuthorityError("live_authorization_catalog_drift")
        profile = SourceProfileRegistry.get_instance().get(
            registration.source_profile_id
        )
        if profile is None:
            raise AcquisitionAuthorityError("live_source_profile_unresolved")
        if (
            fabric_data_plane.content_sha256(profile)
            != authorization.source_profile_sha256
        ):
            raise AcquisitionAuthorityError("live_source_profile_identity_drift")

    def _verify_live_journal_carrier(
        self,
        resolved: ResolvedAcquisitionAuthority,
        proof: LiveSourceExecutionEvidence,
    ) -> None:
        request_event = fabric_data_plane.resolve_journal_event_ref(proof.request_ref)
        raw_event = fabric_data_plane.resolve_journal_event_ref(proof.raw_evidence_ref)
        linked_request = fabric_data_plane.resolve_linked_request_event(
            proof.raw_evidence_ref
        )
        if linked_request != request_event:
            raise AcquisitionAuthorityError("live_request_raw_link_drift")
        if (
            raw_event.get("attempt_id") != proof.authorization.attempt_id
            or request_event.get("attempt_id") != proof.authorization.attempt_id
        ):
            raise AcquisitionAuthorityError("live_attempt_identity_drift")
        raw_projection = raw_event.get("raw_response")
        if not isinstance(raw_projection, Mapping):
            raise AcquisitionAuthorityError("live_raw_response_missing")
        if raw_projection.get("request_event_sha256") != proof.request_ref.event_sha256:
            raise AcquisitionAuthorityError("live_request_event_ref_drift")
        request_value = request_event.get("request")
        if not isinstance(request_value, Mapping):
            raise AcquisitionAuthorityError("live_request_missing")
        request = {str(key): value for key, value in request_value.items()}
        if (
            request_event.get("request_sha256")
            != fabric_data_plane.content_sha256(request)
            or request_event.get("request_sha256")
            != proof.authorization.request_sha256
        ):
            raise AcquisitionAuthorityError("live_request_identity_drift")
        entry = resolved.entry
        registration = resolved.registration
        expected = {
            "authority_entry_id": entry.entry_id,
            "authority_registry_content_sha256": resolved.registry_content_sha256,
            "variable_id": entry.target_variable,
            "source_lane": "live_fetch",
            "dataset_id": entry.landing_dataset_id,
            "distribution_id": entry.landing_distribution_id,
            "connector_id": registration.connector_id,
            "profile_id": registration.source_profile_id,
            "request_dataset_id": registration.request_dataset_id,
            "schema_contract": entry.schema_projection(),
        }
        if any(request.get(key) != value for key, value in expected.items()):
            raise AcquisitionAuthorityError("live_request_owner_projection_drift")
        if (
            fabric_data_plane.content_sha256(entry.schema_projection())
            != proof.authorization.schema_contract_sha256
        ):
            raise AcquisitionAuthorityError("live_request_schema_contract_drift")

    def _verify_live_normalized_result(
        self,
        resolved: ResolvedAcquisitionAuthority,
        proof: LiveSourceExecutionEvidence,
        result: FetchResult[Any],
    ) -> None:
        contract = resolved.entry.schema_contract_ref
        if not contract.startswith("fabric://") or "@" not in contract:
            raise AcquisitionAuthorityError("live_schema_contract_ref_invalid")
        schema_id, schema_version = contract.removeprefix("fabric://").rsplit("@", 1)
        if (
            result.schema_id != schema_id
            or result.schema_version != schema_version
        ):
            raise AcquisitionAuthorityError("live_normalized_schema_contract_drift")
        if (
            result.version.content_hash != proof.raw_body_sha256
            or result.version.content_hash
            != proof.normalized_result_content_sha256
        ):
            raise AcquisitionAuthorityError("live_normalized_raw_version_drift")
        if result.has_more or result.next_page_token is not None:
            raise AcquisitionAuthorityError("live_result_not_one_page")
        if result.row_count != _normalized_result_row_count(result.data):
            raise AcquisitionAuthorityError("live_normalized_row_count_drift")

    @staticmethod
    def _reopen_artifact(
        artifact_store: ArtifactStore,
        artifact_id: ArtifactID,
        *,
        expected_kind: str | None = None,
    ) -> bytes:
        if not artifact_store.has(artifact_id):
            raise AcquisitionAuthorityError("live_artifact_unresolved", str(artifact_id))
        manifest = artifact_store.get_manifest(artifact_id)
        if expected_kind is not None and manifest.kind != expected_kind:
            raise AcquisitionAuthorityError("live_artifact_kind_drift", manifest.kind)
        return artifact_store.get_bytes(artifact_id)

    @classmethod
    def _reopen_artifact_ref(
        cls,
        artifact_store: ArtifactStore,
        ref: object,
        *,
        expected_kind: str | None = None,
    ) -> bytes:
        artifact_id = getattr(ref, "artifact_id", None)
        kind = getattr(ref, "kind", None)
        media_type = getattr(ref, "media_type", None)
        if not isinstance(artifact_id, ArtifactID):
            raise AcquisitionAuthorityError("live_artifact_ref_invalid")
        manifest = artifact_store.get_manifest(artifact_id)
        if manifest.kind != kind or manifest.media_type != media_type:
            raise AcquisitionAuthorityError("live_artifact_ref_manifest_drift")
        if expected_kind is not None and kind != expected_kind:
            raise AcquisitionAuthorityError("live_artifact_kind_drift", str(kind))
        return cls._reopen_artifact(
            artifact_store,
            artifact_id,
            expected_kind=expected_kind,
        )

    def _load_registry(self) -> AcquisitionAuthorityRegistry:
        if not self.registry_path.is_file():
            raise AcquisitionAuthorityError(
                "authority_registry_missing", self.registry_path.as_posix()
            )
        try:
            payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
            registry = AcquisitionAuthorityRegistry.model_validate(payload)
        except Exception as exc:
            raise AcquisitionAuthorityError(
                "authority_registry_invalid", type(exc).__name__
            ) from exc
        actual_baseline = _file_sha256(self.baseline_path)
        if actual_baseline != registry.baseline_content_sha256:
            raise AcquisitionAuthorityError("authority_baseline_identity_drift")
        return registry

    def _resolve_live_catalog(
        self,
        entry: AcquisitionAuthorityEntry,
    ) -> tuple[
        dict[str, object],
        str,
        str,
        str,
        AcquisitionDatasetRegistration,
    ]:
        con = duckdb.connect(str(self.baseline_path), read_only=True)
        try:
            row = con.execute(
                """
                SELECT d.source, d.agency, d.title, d.description,
                       d.access_license, d.execution_tier,
                       x.connector_type, x.profile_id, x.source_locator,
                       b.request_dataset_id, b.metric_id, b.confidence,
                       a.raw_variable, a.canonical_var, a.method,
                       a.confidence, a.evidence, a.is_proxy, a.proxy_penalty
                FROM ds_datasets d
                JOIN ds_distributions x ON x.dataset_id = d.id
                JOIN ds_metric_bindings b
                  ON b.dataset_id = d.id AND b.distribution_id = x.id
                JOIN ds_variable_alignments a ON a.dataset_id = d.id
                WHERE d.id = ? AND x.id = ? AND b.metric_id = ?
                  AND a.raw_variable = ? AND a.canonical_var = ?
                """,
                [
                    entry.source_catalog_dataset_id,
                    entry.source_catalog_distribution_id,
                    entry.upstream_metric_id,
                    entry.catalog_raw_variable,
                    entry.upstream_metric_id,
                ],
            ).fetchall()
            if len(row) != 1:
                raise AcquisitionAuthorityError("catalog_authority_edge_unresolved")
            values = row[0]
        finally:
            con.close()
        (
            source,
            agency,
            title,
            description,
            license_id,
            execution_tier,
            connector_id,
            profile_id,
            source_locator,
            request_dataset_id,
            metric_id,
            binding_confidence,
            catalog_raw_variable,
            canonical_var,
            alignment_method,
            alignment_confidence,
            alignment_evidence,
            is_proxy,
            proxy_penalty,
        ) = values
        if str(execution_tier) not in {"fetchable", "transport_ready"}:
            raise AcquisitionAuthorityError("catalog_execution_tier_not_executable")
        if float(entry.alignment_confidence) > float(alignment_confidence) + 1e-9:
            raise AcquisitionAuthorityError("authority_alignment_inflated")
        projection = {
            "source_catalog_dataset_id": entry.source_catalog_dataset_id,
            "source_catalog_distribution_id": entry.source_catalog_distribution_id,
            "source": source,
            "agency": agency,
            "title": title,
            "description": description,
            "license_id": license_id,
            "execution_tier": execution_tier,
            "connector_id": connector_id,
            "profile_id": profile_id,
            "source_locator": source_locator,
            "request_dataset_id": request_dataset_id,
            "metric_id": metric_id,
            "binding_confidence": binding_confidence,
            "catalog_raw_variable": catalog_raw_variable,
            "canonical_var": canonical_var,
            "alignment_method": alignment_method,
            "alignment_confidence": alignment_confidence,
            "alignment_evidence": alignment_evidence,
            "is_proxy": is_proxy,
            "proxy_penalty": proxy_penalty,
        }
        placeholder = build_metric_field_binding(
            dataset_id=entry.landing_dataset_id,
            distribution_id=entry.landing_distribution_id,
            raw_field=entry.raw_field,
            canonical_variable=entry.target_variable,
            raw_unit=entry.raw_unit,
            canonical_unit=entry.canonical_unit,
            unit_transform=entry.unit_transform,
            unit_transform_ref=entry.unit_transform_ref,
            alignment_method=entry.alignment_method,
            alignment_confidence=entry.alignment_confidence,
            is_proxy=entry.is_proxy,
            proxy_penalty=entry.proxy_penalty,
            evidence_refs=entry.evidence_refs,
            aggregation_method=entry.aggregation_method,
            valid_min=entry.valid_min,
            valid_max=entry.valid_max,
        )
        registration = AcquisitionDatasetRegistration(
            catalog_dataset_id=entry.landing_dataset_id,
            source=str(source),
            agency=str(agency or ""),
            request_dataset_id=str(request_dataset_id),
            distribution_id=entry.landing_distribution_id,
            connector_id=str(connector_id),
            source_profile_id=str(profile_id),
            source_locator=str(source_locator),
            title=entry.title,
            description=entry.description,
            metric_id=entry.target_variable,
            execution_tier=str(execution_tier),
            access_license=str(license_id),
            country_codes=entry.country_codes,
            temporal_start=entry.temporal_start,
            temporal_end=entry.temporal_end,
            field_binding=placeholder,
        )
        license_projection = {
            "dataset_id": entry.source_catalog_dataset_id,
            "access_license": str(license_id),
        }
        if self.baseline_owner_ref is None:
            raise AcquisitionAuthorityError("baseline_owner_ref_unprovisioned")
        return (
            projection,
            str(license_id),
            (
                f"{self.baseline_owner_ref}"
                "#ds_datasets/"
                f"{entry.source_catalog_dataset_id}/access_license"
            ),
            fabric_data_plane.content_sha256(license_projection),
            registration,
        )

    def _resolve_local_source(
        self,
        entry: AcquisitionAuthorityEntry,
        *,
        expected_trust_registry_sha256: str | None,
    ) -> tuple[
        dict[str, object],
        str,
        str,
        str,
        AcquisitionDatasetRegistration,
    ]:
        relative = Path(str(entry.local_source_path))
        if relative.is_absolute() or ".." in relative.parts:
            raise AcquisitionAuthorityError("local_source_path_unsafe")
        source_path = (self.repo_root / relative).resolve()
        if not source_path.is_relative_to(self.repo_root):
            raise AcquisitionAuthorityError("local_source_path_unsafe")
        source_hash = _file_sha256(source_path)
        if source_hash != entry.local_source_sha256:
            raise AcquisitionAuthorityError("local_source_content_drift")
        receipt_relative = Path(str(entry.local_rights_receipt_path))
        if receipt_relative.is_absolute() or ".." in receipt_relative.parts:
            raise AcquisitionAuthorityError("local_rights_receipt_path_unsafe")
        receipt_path = (self.repo_root / receipt_relative).resolve()
        if not receipt_path.is_relative_to(self.repo_root):
            raise AcquisitionAuthorityError("local_rights_receipt_path_unsafe")
        if _file_sha256(receipt_path) != entry.local_rights_receipt_sha256:
            raise AcquisitionAuthorityError("local_rights_receipt_content_drift")
        try:
            rights = LocalSourceRightsReceipt.model_validate_json(
                receipt_path.read_bytes()
            )
        except Exception as exc:
            raise AcquisitionAuthorityError(
                "local_rights_receipt_invalid",
                type(exc).__name__,
            ) from exc
        if not expected_trust_registry_sha256:
            raise AcquisitionAuthorityError("local_rights_trust_anchor_unprovisioned")
        trust_relative = DEFAULT_LOCAL_RIGHTS_TRUST_REGISTRY
        document_relative = _safe_repo_relative_path(
            rights.rights_document_path,
            code="local_rights_document_path",
        )
        recomputed_rights, declaration, trust_registry = (
            _derive_local_source_rights_receipt(
                root=self.repo_root,
                source_relative=relative,
                document_relative=document_relative,
                trust_relative=trust_relative,
                expected_trust_file_sha256=expected_trust_registry_sha256,
            )
        )
        if (
            rights != recomputed_rights
            or rights.source_content_sha256 != source_hash
            or rights.license_id != entry.local_license_id
        ):
            raise AcquisitionAuthorityError("local_rights_receipt_recomputation_drift")
        placeholder = build_metric_field_binding(
            dataset_id=entry.landing_dataset_id,
            distribution_id=entry.landing_distribution_id,
            raw_field=entry.raw_field,
            canonical_variable=entry.target_variable,
            raw_unit=entry.raw_unit,
            canonical_unit=entry.canonical_unit,
            unit_transform=entry.unit_transform,
            unit_transform_ref=entry.unit_transform_ref,
            alignment_method=entry.alignment_method,
            alignment_confidence=entry.alignment_confidence,
            is_proxy=entry.is_proxy,
            proxy_penalty=entry.proxy_penalty,
            evidence_refs=entry.evidence_refs,
            aggregation_method=entry.aggregation_method,
            valid_min=entry.valid_min,
            valid_max=entry.valid_max,
        )
        registration = AcquisitionDatasetRegistration(
            catalog_dataset_id=entry.landing_dataset_id,
            source="policyos_acquisition_local_lift",
            agency="PolicyOS owner-validated local source",
            request_dataset_id=source_path.name,
            distribution_id=entry.landing_distribution_id,
            connector_id="local.parquet",
            source_profile_id="local_parquet",
            source_locator=f"repo://{relative.as_posix()}",
            title=entry.title,
            description=entry.description,
            metric_id=entry.target_variable,
            execution_tier="transport_ready",
            access_license=rights.license_id,
            country_codes=entry.country_codes,
            temporal_start=entry.temporal_start,
            temporal_end=entry.temporal_end,
            field_binding=placeholder,
        )
        projection = {
            "local_source_path": relative.as_posix(),
            "local_source_sha256": source_hash,
            "local_rights_receipt_id": rights.receipt_id,
            "local_rights_receipt_sha256": entry.local_rights_receipt_sha256,
            "local_rights_document_sha256": rights.rights_document_sha256,
            "local_rights_declaration_id": declaration.declaration_id,
            "local_rights_trust_registry_sha256": trust_registry.content_sha256,
            "local_rights_public_key_sha256": rights.public_key_sha256,
        }
        return (
            projection,
            rights.license_id,
            f"repo://{document_relative.as_posix()}",
            rights.rights_document_sha256,
            registration,
        )

    def _resolve_l5(
        self,
        family_id: str,
        *,
        expected_content_sha256: str,
    ) -> ResolvedL5Trust:
        if not self.l5_path.is_file():
            raise AcquisitionAuthorityError("l5_measurement_registry_missing")
        raw = self.l5_path.read_bytes()
        owner_hash = f"sha256:{hashlib.sha256(raw).hexdigest()}"
        if owner_hash != expected_content_sha256:
            raise AcquisitionAuthorityError("l5_measurement_registry_content_drift")
        try:
            payload = json.loads(raw)
            coverage = float(_mapping(payload.get("coverage_rules"))[family_id])
            tiers = _mapping(payload.get("trust_tiers"))
        except Exception as exc:
            raise AcquisitionAuthorityError("l5_family_unresolved", family_id) from exc
        eligible: list[tuple[float, float, float, str, Mapping[str, object]]] = []
        for tier_id, value in tiers.items():
            if not isinstance(value, Mapping):
                continue
            lower = float(value.get("min_coverage") or 0.0)
            upper = float(value.get("max_coverage") or 1.0)
            if lower - 1e-9 <= coverage <= upper + 1e-9:
                eligible.append(
                    (
                        lower,
                        float(value.get("trust_cap") or 0.0),
                        float(value.get("trust_multiplier") or 0.0),
                        str(tier_id),
                        value,
                    )
                )
        if not eligible:
            raise AcquisitionAuthorityError("l5_trust_tier_unresolved", family_id)
        _, trust_cap, trust_multiplier, tier_id, row = max(eligible)
        relative = self.l5_path.relative_to(self.repo_root).as_posix()
        return ResolvedL5Trust(
            family_id=family_id,
            tier=str(row.get("tier") or tier_id),
            trust_cap=trust_cap,
            trust_multiplier=trust_multiplier,
            authority_ref=f"repo://{relative}#/trust_tiers/{tier_id}",
            owner_ref=f"repo://{relative}",
            owner_content_sha256=owner_hash,
        )


def _license_disposition(value: str) -> LicenseDisposition:
    normalized = value.strip().lower().replace("_", "-")
    if normalized in {
        "cc-by-4.0",
        "cc-by-3.0",
        "cc0-1.0",
        "odc-by-1.0",
        "pddl-1.0",
    }:
        return LicenseDisposition.ADMISSIBLE_OPEN
    if normalized in {"all-rights-reserved", "proprietary", "restricted"}:
        return LicenseDisposition.RESTRICTED
    return LicenseDisposition.UNCLEAR


def _normalized_result_row_count(data: object) -> int:
    if isinstance(data, pd.DataFrame):
        return len(data.index)
    if isinstance(data, Mapping):
        return 1
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        return len(data)
    raise AcquisitionAuthorityError(
        "live_normalized_payload_unsupported",
        type(data).__name__,
    )


def _normalized_fetch_result_body(result: FetchResult[Any]) -> bytes:
    data = result.data
    if isinstance(data, pd.DataFrame):
        # Round through pandas' JSON encoder so numpy scalars and timestamps
        # become plain JSON values before canonicalization.
        payload: object = json.loads(
            data.to_json(
                orient="records",
                date_format="iso",
                date_unit="us",
                double_precision=15,
            )
        )
    elif isinstance(data, Mapping):
        payload = dict(data)
    elif isinstance(data, Sequence) and not isinstance(
        data,
        (str, bytes, bytearray),
    ):
        payload = list(data)
    else:
        raise AcquisitionAuthorityError(
            "live_normalized_payload_unsupported",
            type(data).__name__,
        )
    return canonical_json_bytes(payload)


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        raise AcquisitionAuthorityError("authority_source_missing", path.as_posix())
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _load_authority_provision(
    path: Path,
) -> tuple[AcquisitionAuthorityProvision, str]:
    if not path.is_file():
        raise AcquisitionAuthorityError(
            "acquisition_authority_provision_missing",
            path.as_posix(),
        )
    raw = path.read_bytes()
    try:
        provision = AcquisitionAuthorityProvision.model_validate_json(raw)
    except Exception as exc:
        raise AcquisitionAuthorityError(
            "acquisition_authority_provision_invalid",
            type(exc).__name__,
        ) from exc
    return provision, f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _derive_local_source_rights_receipt(
    *,
    root: Path,
    source_relative: Path,
    document_relative: Path,
    trust_relative: Path,
    expected_trust_file_sha256: str | None,
) -> tuple[
    LocalSourceRightsReceipt,
    LocalSourceRightsDeclaration,
    LocalRightsTrustRegistry,
]:
    """Single behavioral verifier shared by receipt writing and admission."""

    if document_relative == source_relative:
        raise AcquisitionAuthorityError("local_rights_document_is_source")
    source = _resolve_repo_file(root, source_relative, code="local_source_path")
    document = _resolve_repo_file(
        root,
        document_relative,
        code="local_rights_document_path",
    )
    source_sha = _file_sha256(source)
    document_sha = _file_sha256(document)
    try:
        declaration = LocalSourceRightsDeclaration.model_validate_json(
            document.read_bytes()
        )
    except Exception as exc:
        raise AcquisitionAuthorityError(
            "local_rights_document_invalid",
            type(exc).__name__,
        ) from exc
    if (
        declaration.source_path != source_relative.as_posix()
        or declaration.source_content_sha256 != source_sha
    ):
        raise AcquisitionAuthorityError("local_rights_document_source_drift")
    trust_path = _resolve_repo_file(
        root,
        trust_relative,
        code="local_rights_trust_registry_path",
    )
    trust_registry = _load_local_rights_trust_registry(
        trust_path,
        expected_file_sha256=expected_trust_file_sha256,
    )
    trusted = _verify_local_rights_declaration(
        declaration,
        trust_registry=trust_registry,
    )
    public_key = base64.b64decode(
        trusted.ed25519_public_key_base64,
        validate=True,
    )
    values: dict[str, object] = {
        "source_path": source_relative.as_posix(),
        "source_content_sha256": source_sha,
        "license_id": declaration.license_id,
        "authority_id": declaration.authority_id,
        "rights_authority": declaration.rights_authority,
        "authority_ref": declaration.authority_ref,
        "rights_document_path": document_relative.as_posix(),
        "rights_document_sha256": document_sha,
        "rights_declaration_id": declaration.declaration_id,
        "trust_registry_content_sha256": trust_registry.content_sha256,
        "public_key_sha256": f"sha256:{hashlib.sha256(public_key).hexdigest()}",
    }
    provisional = LocalSourceRightsReceipt.model_construct(
        receipt_id="local-rights:sha256:" + "0" * 64,
        **values,
    )
    receipt = LocalSourceRightsReceipt(
        receipt_id=(
            "local-rights:"
            + fabric_data_plane.content_sha256(provisional.identity_payload())
        ),
        **values,
    )
    return receipt, declaration, trust_registry


def _load_local_rights_trust_registry(
    path: Path,
    *,
    expected_file_sha256: str | None = None,
) -> LocalRightsTrustRegistry:
    if not path.is_file():
        raise AcquisitionAuthorityError(
            "local_rights_trust_registry_missing",
            path.as_posix(),
        )
    try:
        registry = LocalRightsTrustRegistry.model_validate_json(path.read_bytes())
    except Exception as exc:
        raise AcquisitionAuthorityError(
            "local_rights_trust_registry_invalid",
            type(exc).__name__,
        ) from exc
    actual = _file_sha256(path)
    if expected_file_sha256 is not None and actual != expected_file_sha256:
        raise AcquisitionAuthorityError("local_rights_trust_registry_content_drift")
    return registry


def _verify_local_rights_declaration(
    declaration: LocalSourceRightsDeclaration,
    *,
    trust_registry: LocalRightsTrustRegistry,
) -> LocalRightsTrustedAuthority:
    matches = tuple(
        authority
        for authority in trust_registry.authorities
        if authority.authority_id == declaration.authority_id
    )
    if len(matches) != 1:
        raise AcquisitionAuthorityError("local_rights_signing_authority_unresolved")
    trusted = matches[0]
    if (
        declaration.rights_authority != trusted.rights_authority
        or declaration.authority_ref != trusted.authority_ref
        or declaration.license_id not in trusted.admissible_license_ids
    ):
        raise AcquisitionAuthorityError("local_rights_signing_authority_drift")
    try:
        public_key = base64.b64decode(
            trusted.ed25519_public_key_base64,
            validate=True,
        )
        signature = base64.b64decode(declaration.signature_base64, validate=True)
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature,
            canonical_json_bytes(declaration.signed_payload()),
        )
    except (InvalidSignature, ValueError) as exc:
        raise AcquisitionAuthorityError("local_rights_signature_invalid") from exc
    return trusted


def _safe_repo_relative_path(value: str, *, code: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise AcquisitionAuthorityError(f"{code}_unsafe")
    return path


def _resolve_repo_file(root: Path, relative: Path, *, code: str) -> Path:
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        raise AcquisitionAuthorityError(f"{code}_unsafe")
    if not resolved.is_file():
        raise AcquisitionAuthorityError(f"{code}_missing", resolved.as_posix())
    return resolved


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AcquisitionAuthorityError("authority_mapping_required")
    return {str(key): item for key, item in value.items()}


__all__ = [
    "ACQUISITION_AUTHORITY_PROVISION_SCHEMA_VERSION",
    "ACQUISITION_AUTHORITY_SCHEMA_VERSION",
    "DEFAULT_ACQUISITION_AUTHORITY_PROVISION",
    "DEFAULT_ACQUISITION_AUTHORITY_REGISTRY",
    "DEFAULT_LOCAL_RIGHTS_TRUST_REGISTRY",
    "LIVE_SOURCE_EXECUTION_EVIDENCE_SCHEMA_VERSION",
    "LOCAL_RIGHTS_TRUST_REGISTRY_SCHEMA_VERSION",
    "LOCAL_SOURCE_RIGHTS_DECLARATION_SCHEMA_VERSION",
    "LOCAL_SOURCE_RIGHTS_RECEIPT_SCHEMA_VERSION",
    "AcquisitionAuthorityEntry",
    "AcquisitionAuthorityError",
    "AcquisitionAuthorityProvision",
    "AcquisitionAuthorityRegistry",
    "AuthoritySchemaColumn",
    "CanonicalAcquisitionAuthority",
    "LicenseDisposition",
    "LiveSourceExecutionEvidence",
    "LocalRightsTrustRegistry",
    "LocalRightsTrustedAuthority",
    "LocalSourceRightsDeclaration",
    "LocalSourceRightsReceipt",
    "ResolvedAcquisitionAuthority",
    "ResolvedL5Trust",
    "build_acquisition_authority_provision",
    "build_authority_entry",
    "build_authority_registry",
    "build_live_source_execution_evidence",
    "build_local_rights_trust_registry",
    "build_local_source_rights_declaration",
    "verify_local_source_rights",
]
