"""Fail-closed admission kernel for local-lift and live acquisition evidence.

This module is data-plane only.  It measures quarantined owner bytes, resolves
license/L5/CAS/journal evidence, derives a passport, and leaves persistence to
the catalog overlay and existing Fabric quarantine owners.  It does not build,
mutate, or simulate a policy world.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal, Protocol, Self

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, canon, contracts, scan_secret_and_pii
from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.fabric import connectors as fabric_connectors
from polisyos.fabric import data_plane as fabric_data_plane
from polisyos.fabric import ingestion as fabric_ingestion

epoch_contract = contracts.epoch

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.runtime.quality.semantic_epoch import (
        EpochResolutionQuery,
        EpochScopeIdentity,
        PersistedSemanticEpochProductionReceipt,
        SemanticEpochService,
    )

ArtifactID = artifacts.ArtifactID
ArtifactRef = artifacts.ArtifactRef
ArtifactWriteOptions = artifacts.PutOptions
FileSystemCAS = artifacts.FileSystemCAS
DataSnapshot = contracts.DataSnapshot
EvidenceBundle = contracts.EvidenceBundle
FetchRequest = fabric_connectors.FetchRequest
FetchResult = fabric_connectors.FetchResult
ResultSerializer = fabric_connectors.ResultSerializer
SourceProfileRegistry = fabric_connectors.SourceProfileRegistry
ConnectorManifestSpec = fabric_ingestion.ConnectorManifestSpec
DatasetFetchSpec = fabric_ingestion.DatasetFetchSpec
JournalEventRef = fabric_data_plane.JournalEventRef
MetricFieldBinding = data_forge_read_api.catalog.MetricFieldBinding
AcquisitionAuthorityEntry = data_forge_read_api.catalog.AcquisitionAuthorityEntry
ObservationProvenanceClass = data_forge_read_api.catalog.ObservationProvenanceClass
AcquisitionDatasetRegistration = data_forge_read_api.catalog.AcquisitionDatasetRegistration
ResolvedAcquisitionAuthority = data_forge_read_api.catalog.ResolvedAcquisitionAuthority
ResolvedLiveHarnessReceipt = data_forge_read_api.catalog.ResolvedLiveHarnessReceipt
LiveSourceExecutionEvidence = data_forge_read_api.catalog.LiveSourceExecutionEvidence
content_sha256 = fabric_data_plane.content_sha256
resolve_linked_request_event = fabric_data_plane.resolve_linked_request_event
resolve_raw_response_body = fabric_data_plane.resolve_raw_response_body
QuarantineRecord = fabric_data_plane.QuarantineRecord
persist_quarantine_record = fabric_data_plane.persist_quarantine_record
run_orchestrated_ingestion = fabric_data_plane.run_orchestrated_ingestion
from_canonical_bytes = canon.from_canonical_bytes
resolve_connection_config = fabric_connectors.resolve_connection_config
normalize_worldbank_records = fabric_connectors.normalize_worldbank_records

PASSPORT_SCHEMA_VERSION = "polisyos.runtime.acquisition_admission_passport.v2"
_LEGACY_PASSPORT_SCHEMA_VERSION = "polisyos.runtime.acquisition_admission_passport.v1"
ALIGNMENT_ADMISSION_FLOOR = 0.55
ALIGNMENT_DECISIVE_FLOOR = 0.8
_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"


class LiveAcquisitionExecutionError(RuntimeError):
    """Typed refusal raised before live evidence can enter admission."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail or code
        super().__init__(f"{code}: {self.detail}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LiveCatalogExecutionConstraints(_StrictModel):
    """Bounded request-side scope for one catalog-resolved live variable."""

    country_code: str = Field(pattern=r"^[A-Z]{3}$")
    start_year: int = Field(ge=1960, le=2200)
    end_year: int = Field(ge=1960, le=2200)
    page_size: int = Field(gt=0, le=20_000)
    max_response_bytes: int = Field(gt=0)
    max_decompressed_bytes: int = Field(gt=0)
    timeout_cap_seconds: float = Field(ge=1.0)
    heartbeat_cap_seconds: float = Field(ge=0.1)

    @model_validator(mode="after")
    def _scope_is_bounded(self) -> Self:
        if self.end_year < self.start_year:
            raise ValueError("live execution year bounds are reversed")
        if self.max_decompressed_bytes > self.max_response_bytes:
            raise ValueError("decompressed response cap exceeds the raw cap")
        if self.heartbeat_cap_seconds > self.timeout_cap_seconds:
            raise ValueError("heartbeat cap exceeds the timeout cap")
        return self

    @property
    def date_start(self) -> str:
        """Return the inclusive owner request start date."""

        return f"{self.start_year:04d}-01-01"

    @property
    def date_end(self) -> str:
        """Return the inclusive owner request end date."""

        return f"{self.end_year:04d}-12-31"


class AdmissionStatus(StrEnum):
    """Passport result recomputed from all decisive evidence."""

    ADMITTED = "admitted"
    ADMITTED_DEGRADED = "admitted_degraded"
    QUARANTINED = "quarantined"


class LicenseDisposition(StrEnum):
    """Owner registry result for one source license."""

    ADMISSIBLE_OPEN = "admissible_open"
    UNCLEAR = "unclear"
    RESTRICTED = "restricted"


class MeasuredColumn(_StrictModel):
    """One column measured from the first quarantined sample."""

    name: str = Field(min_length=1)
    logical_type: str = Field(min_length=1)
    nullable: bool


class MeasuredSchemaProfile(_StrictModel):
    """Structure measured from journaled bytes, never inferred from metadata alone."""

    measurement_id: str = Field(pattern=r"^measurement:sha256:[0-9a-f]{64}$")
    dataset_id: str = Field(min_length=1)
    distribution_id: str = Field(min_length=1)
    source_profile_id: str = Field(min_length=1)
    columns: tuple[MeasuredColumn, ...] = Field(min_length=1)
    sample_row_count: int = Field(ge=0)
    sample_content_sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    raw_evidence_event_sha256: str = Field(pattern=_SHA256_PATTERN)
    inference_mode: Literal["measured_quarantine", "metadata_only"]
    parser_mode: str = Field(min_length=1)

    @model_validator(mode="after")
    def _measurement_identity_is_recomputed(self) -> Self:
        names = tuple(column.name for column in self.columns)
        if names != tuple(sorted(set(names))):
            raise ValueError("measured columns must be unique and sorted")
        expected = "measurement:" + content_sha256(self.identity_payload())
        if self.measurement_id != expected:
            raise ValueError("measurement identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the projection defining this measured profile."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "measurement_id"
        }


class LicenseEvidence(_StrictModel):
    """License decision resolved from a content-bound authority."""

    license_id: str = Field(min_length=1)
    normalized_license_id: str = Field(min_length=1)
    disposition: LicenseDisposition
    authority_ref: str = Field(min_length=1)
    authority_content_sha256: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _identifier_is_normalized(self) -> Self:
        if self.normalized_license_id != _normalize_license(self.license_id):
            raise ValueError("license identifier normalization must be recomputed")
        return self


class PIIScanEvidence(_StrictModel):
    """Pre-admission secret/PII scan evidence over exact raw bytes."""

    scope: Literal["connector request/response payloads"] = "connector request/response payloads"
    artifact_ref_or_route: str = Field(min_length=1)
    detector_version: str = Field(min_length=1)
    finding_kinds: tuple[str, ...]
    blocked: bool

    @model_validator(mode="after")
    def _blocked_is_recomputed(self) -> Self:
        if self.finding_kinds != tuple(sorted(set(self.finding_kinds))):
            raise ValueError("PII findings must be unique and sorted")
        if self.blocked != bool(self.finding_kinds):
            raise ValueError("PII block status must be recomputed from findings")
        return self


class L5TrustEvidence(_StrictModel):
    """L5 owner projection that caps admitted data authority."""

    family_id: str = Field(min_length=1)
    resolved: bool
    tier: str
    trust_cap: float = Field(ge=0.0, le=1.0)
    trust_multiplier: float = Field(ge=0.0, le=1.0)
    authority_ref: str
    owner_ref: str

    @model_validator(mode="after")
    def _resolved_projection_is_complete(self) -> Self:
        complete = bool(self.tier and self.authority_ref and self.owner_ref)
        if self.resolved != complete:
            raise ValueError("L5 resolution status must be recomputed from owner fields")
        return self


class SchemaValidationEvidence(_StrictModel):
    """Declared-vs-measured schema result recomputed from owner request bytes."""

    request_event_sha256: str = Field(pattern=_SHA256_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    schema_contract_ref: str = Field(min_length=1)
    schema_contract_sha256: str = Field(pattern=_SHA256_PATTERN)
    authority_entry_id: str = Field(min_length=1)
    authority_registry_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    drift_codes: tuple[str, ...]
    conformant: bool

    @model_validator(mode="after")
    def _conformance_is_recomputed(self) -> Self:
        if self.drift_codes != tuple(sorted(set(self.drift_codes))):
            raise ValueError("schema drift codes must be unique and sorted")
        if self.conformant != (not self.drift_codes):
            raise ValueError("schema conformance must be recomputed from drift")
        return self


class AdmissionPassport(_StrictModel):
    """Complete fail-closed passport required before any row enters L1."""

    schema_version: Literal[PASSPORT_SCHEMA_VERSION] = PASSPORT_SCHEMA_VERSION
    passport_id: str = Field(pattern=r"^passport:sha256:[0-9a-f]{64}$")
    epoch_id: int = Field(gt=0)
    variable_id: str = Field(min_length=1)
    source_lane: Literal["local_lift", "live_fetch"]
    observation_class: ObservationProvenanceClass
    authority_entry_id: str = Field(min_length=1)
    authority_provision_id: str = Field(
        pattern=r"^acquisition-authority-provision:sha256:[0-9a-f]{64}$"
    )
    authority_provision_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    authority_registry_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    upstream_catalog_projection_sha256: str = Field(pattern=_SHA256_PATTERN)
    baseline_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    registration: AcquisitionDatasetRegistration
    measured_profile: MeasuredSchemaProfile
    field_binding: MetricFieldBinding
    raw_evidence_ref: JournalEventRef
    raw_evidence_verified: bool
    raw_artifact_id: str = Field(pattern=_SHA256_PATTERN)
    cas_evidence_verified: bool
    license_evidence: LicenseEvidence
    pii_scan: PIIScanEvidence
    source_watermark: str
    dataset_version: str
    l5_trust: L5TrustEvidence
    schema_validation: SchemaValidationEvidence
    live_source_execution: LiveSourceExecutionEvidence | None = None
    source_authority_verified: bool
    semantic_boundary_candidate_ref: ArtifactRef
    semantic_boundary_candidate_content_hash: str = Field(pattern=_SHA256_PATTERN)
    semantic_epoch_ref: str = Field(pattern=_SHA256_PATTERN)
    semantic_epoch_stamp_sha256: str = Field(pattern=_SHA256_PATTERN)
    semantic_epoch_stamp: epoch_contract.SemanticEpochStamp
    prepared_semantic_epoch_ref: ArtifactRef
    status: AdmissionStatus
    rejection_codes: tuple[str, ...]

    @model_validator(mode="after")
    def _passport_is_recomputed(self) -> Self:
        if self.source_lane == "live_fetch":
            if self.live_source_execution is None:
                raise ValueError("live source execution evidence is required")
            live = self.live_source_execution
            if (
                live.raw_evidence_ref != self.raw_evidence_ref
                or str(live.raw_artifact_id) != self.raw_artifact_id
                or live.baseline_after_sha256 != self.baseline_content_sha256
                or live.raw_body_sha256 != self.source_watermark
                or live.normalized_result_content_sha256 != self.dataset_version
            ):
                raise ValueError("live source execution evidence must bind the passport")
        elif self.live_source_execution is not None:
            raise ValueError("local-lift passport cannot carry live execution evidence")
        if self.semantic_epoch_ref != self.semantic_epoch_stamp.epoch_ref:
            raise ValueError("passport semantic epoch ref differs from its stamp")
        expected_stamp_hash = epoch_contract.semantic_epoch_stamp_content_hash(
            self.semantic_epoch_stamp
        )
        if self.semantic_epoch_stamp_sha256 != expected_stamp_hash:
            raise ValueError("passport semantic epoch stamp hash is not recomputed")
        if (
            self.semantic_boundary_candidate_ref.kind
            != "epoch.acquisition_semantic_boundary_candidate"
            or self.semantic_boundary_candidate_ref.media_type
            != "application/vnd.polisyos.epoch+json"
            or self.prepared_semantic_epoch_ref.kind != "epoch.prepared"
            or self.prepared_semantic_epoch_ref.media_type != "application/vnd.polisyos.epoch+json"
        ):
            raise ValueError("passport semantic handshake artifact profile differs")
        expected_rejections = self.recomputed_rejection_codes()
        if self.rejection_codes != expected_rejections:
            raise ValueError("rejection codes must be recomputed from decisive evidence")
        expected_status = _derive_status(
            rejection_codes=expected_rejections,
            field_binding=self.field_binding,
            observation_class=self.observation_class,
            l5_trust=self.l5_trust,
            schema_validation=self.schema_validation,
            source_authority_verified=self.source_authority_verified,
        )
        if self.status is not expected_status:
            raise ValueError("status must be recomputed from decisive evidence")
        if self.passport_id != self.recomputed_passport_id():
            raise ValueError("passport identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the narrow evidence projection defining passport identity."""

        return {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key not in {"passport_id", "status", "rejection_codes"}
        }

    def recomputed_passport_id(self) -> str:
        """Recompute this passport's content identity."""

        return "passport:" + content_sha256(self.identity_payload())

    def recomputed_rejection_codes(self) -> tuple[str, ...]:
        """Recompute every admission refusal from nested owner evidence."""

        return _derive_rejection_codes(
            variable_id=self.variable_id,
            observation_class=self.observation_class,
            measured_profile=self.measured_profile,
            field_binding=self.field_binding,
            raw_evidence_verified=self.raw_evidence_verified,
            cas_evidence_verified=self.cas_evidence_verified,
            license_evidence=self.license_evidence,
            pii_scan=self.pii_scan,
            source_watermark=self.source_watermark,
            dataset_version=self.dataset_version,
            l5_trust=self.l5_trust,
            schema_validation=self.schema_validation,
            source_authority_verified=self.source_authority_verified,
        )


class ActivatedSemanticEpochAdmissionReceipt(_StrictModel):
    """Exact positive bridge after owner visibility activation."""

    passport_ref: ArtifactRef
    prepared_epoch_ref: ArtifactRef
    pending_overlay_receipt_ref: ArtifactRef
    semantic_epoch_production_receipt_ref: ArtifactRef
    overlay_admission_receipt_ref: ArtifactRef
    native_membership_receipt_ref: ArtifactRef
    semantic_denominator_receipt_ref: ArtifactRef
    semantic_projection_verification_receipt_ref: ArtifactRef
    semantic_epoch_stamp: epoch_contract.SemanticEpochStamp
    activation_state: Literal["active"]


SemanticEpochAdmissionFailureCode = Literal[
    "resolver_unavailable",
    "scope_unresolved",
    "basis_mismatch",
    "query_context_mismatch",
    "epoch_ref_mismatch",
    "predicate_not_authority_grade",
]


class SemanticEpochAdmissionResolutionError(RuntimeError):
    """Typed fail-closed disposition before an epoch can become visible."""

    def __init__(self, code: SemanticEpochAdmissionFailureCode, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class _ArtifactStore(Protocol):
    def has(self, artifact_id: ArtifactID) -> bool: ...

    def get_bytes(self, artifact_id: ArtifactID) -> bytes: ...

    def get_manifest(self, artifact_id: ArtifactID) -> object: ...

    def verify(self, artifact_id: ArtifactID) -> object: ...

    def put_bytes(self, data: bytes, opts: object) -> ArtifactRef: ...


class _PreparedSemanticEpoch(Protocol):
    prepared_epoch_ref: ArtifactRef
    prepared_content_hash: str
    query: EpochResolutionQuery
    stamp: epoch_contract.SemanticEpochStamp
    boundary_candidate_refs: tuple[ArtifactRef, ...]
    status: object

    def model_dump(self, *, mode: str) -> dict[str, Any]: ...


class _CatalogAcquisitionOverlay(Protocol):
    """Structural Data Forge owner seam used by the runtime orchestrator."""

    def admit_epoch(
        self,
        *,
        passport: AdmissionPassport,
        prepared_epoch: _PreparedSemanticEpoch,
        boundary_candidate: epoch_contract.AcquisitionSemanticBoundaryCandidate,
        artifact_store: _ArtifactStore,
        authority: _CanonicalAuthority,
    ) -> _PendingOverlayAdmissionReceipt: ...

    def emit_admitted_boundary_evidence(
        self,
        *,
        query: epoch_contract.AcquisitionBoundaryResolutionQuery,
        passport: AdmissionPassport,
        prepared_epoch: _PreparedSemanticEpoch,
        boundary_candidate: epoch_contract.AcquisitionSemanticBoundaryCandidate,
        pending_receipt: _PendingOverlayAdmissionReceipt,
        artifact_store: _ArtifactStore,
    ) -> ArtifactRef: ...

    def activate_semantic_epoch(
        self,
        *,
        pending_receipt: _PendingOverlayAdmissionReceipt,
        production_receipt: PersistedSemanticEpochProductionReceipt,
        artifact_store: _ArtifactStore,
    ) -> _ActivatedOverlayAdmissionReceipt: ...


class _PendingOverlayAdmissionReceipt(Protocol):
    receipt_ref: ArtifactRef


class _ActivatedOverlayAdmissionReceipt(Protocol):
    receipt_ref: ArtifactRef


class _CanonicalAuthority(Protocol):
    baseline_path: Path

    def resolve(self, entry_id: str) -> object: ...

    def verify_source_body(self, entry_id: str, body: bytes) -> bool: ...

    def resolve_live_harness_receipt(
        self,
        entry_id: str,
        attempt_id: str,
    ) -> object: ...

    def resolve_live_source_body(
        self,
        entry_id: str,
        evidence: object,
        artifact_store: object,
    ) -> bytes: ...

    def resolve_live_source_execution(
        self,
        entry_id: str,
        evidence: object,
        artifact_store: object,
    ) -> object: ...


class _LiveHTTPExecutionObserver:
    """Journal one exact HTTP carrier before any response interpretation."""

    def __init__(
        self,
        *,
        journal: fabric_data_plane.AppendOnlyEvidenceJournal,
        request_ref: JournalEventRef,
        authorization: fabric_data_plane.LiveExecutionAuthorization,
        artifact_store: FileSystemCAS,
        expected_connector_id: str,
        expected_url: str,
        expected_params: Mapping[str, str],
    ) -> None:
        self.journal = journal
        self.request_ref = request_ref
        self.authorization = authorization
        self.artifact_store = artifact_store
        self.expected_connector_id = expected_connector_id
        self.expected_url = expected_url
        self.expected_params = dict(expected_params)
        self.started_at = time.monotonic()
        self.transport_attempt_count = 0
        self.transport_ref: JournalEventRef | None = None
        self.raw_evidence_ref: JournalEventRef | None = None
        self.raw_artifact_ref: ArtifactRef | None = None
        self.raw_body: bytes | None = None
        self.raw_status_code: int | None = None
        self._last_elapsed_seconds = 0.0

    @property
    def max_response_bytes(self) -> int:
        """Return the owner-derived encoded response limit."""

        return self.authorization.budget.max_response_bytes

    @property
    def max_decompressed_bytes(self) -> int:
        """Return the owner-derived decoded response limit."""

        return self.authorization.budget.max_decompressed_bytes

    @property
    def heartbeat_interval_seconds(self) -> float:
        """Return the owner-derived interval for in-flight waiting heartbeats."""

        return self.authorization.budget.heartbeat_interval_seconds

    def before_request(
        self,
        connector_id: str,
        url: str,
        params: Mapping[str, str],
    ) -> None:
        """Persist every attempted transport, then enforce its exact scope."""

        transport_ref = self.journal.append_transport_attempt(
            attempt_id=self.authorization.attempt_id,
            request_ref=self.request_ref,
            connector_id=connector_id,
            url=url,
            params=params,
        )
        self.transport_attempt_count += 1
        if self.transport_attempt_count > self.authorization.budget.call_budget:
            raise LiveAcquisitionExecutionError(
                "live_call_budget_exceeded",
                self.authorization.attempt_id,
            )
        self.journal.append_heartbeat(
            attempt_id=self.authorization.attempt_id,
            phase="attempt_started",
            progress_bytes=0,
            elapsed_seconds=self._elapsed_seconds(),
        )
        self.transport_ref = transport_ref
        self._require_transport_scope(connector_id, url, params)

    def on_response_headers(
        self,
        connector_id: str,
        url: str,
        params: Mapping[str, str],
        status_code: int,
        response_headers: Mapping[str, str],
    ) -> None:
        """Journal the first response milestone without classifying it."""

        del status_code, response_headers
        self._require_transport_scope(connector_id, url, params)
        self.journal.append_heartbeat(
            attempt_id=self.authorization.attempt_id,
            phase="response_headers",
            progress_bytes=0,
            elapsed_seconds=self._elapsed_seconds(),
        )

    def on_waiting(
        self,
        connector_id: str,
        url: str,
        params: Mapping[str, str],
        elapsed_seconds: float,
    ) -> None:
        """Journal bounded in-flight progress before response headers arrive."""

        del elapsed_seconds
        self._require_transport_scope(connector_id, url, params)
        self.journal.append_heartbeat(
            attempt_id=self.authorization.attempt_id,
            phase="waiting",
            progress_bytes=0,
            elapsed_seconds=self._elapsed_seconds(),
        )

    def on_body_progress(
        self,
        connector_id: str,
        url: str,
        params: Mapping[str, str],
        bytes_read: int,
    ) -> None:
        """Journal monotone body progress while the authorized call is alive."""

        self._require_transport_scope(connector_id, url, params)
        self.journal.append_heartbeat(
            attempt_id=self.authorization.attempt_id,
            phase="body_progress",
            progress_bytes=bytes_read,
            elapsed_seconds=self._elapsed_seconds(),
        )

    def on_raw_response(
        self,
        connector_id: str,
        url: str,
        params: Mapping[str, str],
        status_code: int,
        response_headers: Mapping[str, str],
        body: bytes,
    ) -> None:
        """Persist exact bounded bytes to the journal before writing their CAS copy."""

        self._require_transport_scope(connector_id, url, params)
        if self.transport_ref is None:
            raise LiveAcquisitionExecutionError(
                "live_transport_attempt_missing",
                self.authorization.attempt_id,
            )
        raw_ref = self.journal.append_raw_evidence(
            attempt_id=self.authorization.attempt_id,
            request_ref=self.request_ref,
            transport_ref=self.transport_ref,
            payload=body,
            status_code=status_code,
            response_headers=response_headers,
            budget=self.authorization.budget,
        )
        raw_artifact_ref = self.artifact_store.put_bytes(
            body,
            ArtifactWriteOptions(
                kind="fabric.acquisition.raw_evidence",
                media_type="application/json",
            ),
        )
        self.raw_evidence_ref = raw_ref
        self.raw_artifact_ref = raw_artifact_ref
        self.raw_body = body
        self.raw_status_code = status_code

    def _require_transport_scope(
        self,
        connector_id: str,
        url: str,
        params: Mapping[str, str],
    ) -> None:
        normalized_params = {str(key): str(value) for key, value in params.items()}
        if (
            connector_id != self.expected_connector_id
            or url != self.expected_url
            or normalized_params != self.expected_params
        ):
            raise LiveAcquisitionExecutionError(
                "live_transport_request_drift",
                f"{connector_id}:{url}",
            )

    def _elapsed_seconds(self) -> float:
        elapsed = max(time.monotonic() - self.started_at, self._last_elapsed_seconds)
        self._last_elapsed_seconds = elapsed
        return elapsed


def execute_live_catalog_acquisition(
    *,
    authority: _CanonicalAuthority,
    entry_id: str,
    attempt_id: str,
    constraints: LiveCatalogExecutionConstraints,
    journal_path: Path,
    cas_root: Path,
) -> LiveSourceExecutionEvidence:
    """Execute one catalog-owned variable through Fabric and return quarantine evidence.

    The function does not admit observations.  It creates the exact raw journal/CAS
    carrier and Fabric snapshot required by the independent passport owner.
    """

    resolved = ResolvedAcquisitionAuthority.model_validate(authority.resolve(entry_id))
    entry = resolved.entry
    registration = resolved.registration
    if entry.source_lane != "live_fetch":
        raise LiveAcquisitionExecutionError("live_source_lane_required", entry_id)
    _require_constraints_within_authority_scope(entry, constraints)
    if registration.connector_id != "worldbank.wdi":
        raise LiveAcquisitionExecutionError(
            "live_connector_family_not_implemented",
            registration.connector_id,
        )
    if resolved.license_disposition.value != "admissible_open":
        raise LiveAcquisitionExecutionError(
            "live_license_not_admissible",
            resolved.license_id,
        )
    profile = SourceProfileRegistry.get_instance().get(registration.source_profile_id)
    if profile is None:
        raise LiveAcquisitionExecutionError(
            "live_source_profile_unresolved",
            registration.source_profile_id,
        )
    if not profile.base_url.startswith("https://"):
        raise LiveAcquisitionExecutionError(
            "live_profile_transport_not_https",
            profile.profile_id,
        )

    try:
        harness_receipt = ResolvedLiveHarnessReceipt.model_validate(
            authority.resolve_live_harness_receipt(entry_id, attempt_id)
        )
    except Exception as exc:
        raise LiveAcquisitionExecutionError(
            "live_harness_receipt_unresolved",
            type(exc).__name__,
        ) from exc
    base_connection_config = resolve_connection_config(profile)
    if harness_receipt.source_profile_family != str(profile.connector_family):
        raise LiveAcquisitionExecutionError(
            "live_harness_profile_family_drift",
            harness_receipt.source_profile_family,
        )
    if harness_receipt.connection_config_content_sha256 != content_sha256(
        base_connection_config.to_dict(redact=True)
    ):
        raise LiveAcquisitionExecutionError(
            "live_harness_connection_config_drift",
            profile.profile_id,
        )
    dry_run_request = FetchRequest(dataset_id=registration.request_dataset_id)
    if harness_receipt.fetch_request_key != dry_run_request.request_key:
        raise LiveAcquisitionExecutionError(
            "live_harness_fetch_request_drift",
            registration.request_dataset_id,
        )
    family_receipt = harness_receipt.family_receipt

    baseline_before_sha256 = resolved.baseline_content_sha256
    request = _live_request_projection(
        resolved,
        constraints=constraints,
    )
    authorization = fabric_data_plane.build_live_execution_authorization(
        attempt_id=attempt_id,
        connector_id=registration.connector_id,
        request_dataset_id=registration.request_dataset_id,
        request=request,
        schema_contract=entry.schema_projection(),
        source_profile=profile,
        baseline_sha256=baseline_before_sha256,
        family_receipt=family_receipt,
        timeout_cap_seconds=constraints.timeout_cap_seconds,
        heartbeat_cap_seconds=constraints.heartbeat_cap_seconds,
        max_response_bytes=constraints.max_response_bytes,
        max_decompressed_bytes=constraints.max_decompressed_bytes,
    )
    journal = fabric_data_plane.AppendOnlyEvidenceJournal(journal_path)
    request_ref = journal.append_request(attempt_id=attempt_id, request=request)
    store = FileSystemCAS(cas_root)
    expected_url = (
        profile.base_url.rstrip("/")
        + f"/country/{constraints.country_code}/indicator/"
        + registration.request_dataset_id
    )
    expected_params = {
        "date": f"{constraints.start_year}:{constraints.end_year}",
        "format": "json",
        "page": "1",
        "per_page": str(constraints.page_size),
    }
    observer = _LiveHTTPExecutionObserver(
        journal=journal,
        request_ref=request_ref,
        authorization=authorization,
        artifact_store=store,
        expected_connector_id=registration.connector_id,
        expected_url=expected_url,
        expected_params=expected_params,
    )
    manifest = ConnectorManifestSpec(
        datasets=[
            DatasetFetchSpec(
                connector_id=registration.connector_id,
                dataset_id=registration.request_dataset_id,
                filters={"country": [constraints.country_code]},
                date_start=constraints.date_start,
                date_end=constraints.date_end,
                retryable=False,
                page_size=constraints.page_size,
            )
        ]
    )
    connection_config = replace(
        base_connection_config,
        timeout_seconds=max(1, int(authorization.budget.timeout_seconds)),
        max_retries=1,
        max_connections=1,
    )
    try:
        evidence = _execute_authorized_live_acquisition(
            authority=authority,
            entry_id=entry_id,
            resolved=resolved,
            constraints=constraints,
            journal=journal,
            request_ref=request_ref,
            store=store,
            observer=observer,
            authorization=authorization,
            family_receipt=family_receipt,
            manifest=manifest,
            connection_config=connection_config,
            cas_root=cas_root,
        )
        journal.append_classification(
            attempt_id=attempt_id,
            evidence_ref=evidence.raw_evidence_ref,
            classification={
                "state": "measured_pending_passport",
                "live_source_execution_content_sha256": evidence.content_sha256,
                "normalized_data_artifact_id": str(evidence.normalized_data_artifact_id),
                "response_admitted": False,
            },
        )
        journal.append_failure_terminal(
            attempt_id=attempt_id,
            request_ref=request_ref,
            raw_evidence_ref=evidence.raw_evidence_ref,
            failure_code="measured_pending_passport",
        )
        return evidence
    except Exception as exc:
        failure_code = _live_failure_code(exc)
        try:
            journal.append_failure_terminal(
                attempt_id=attempt_id,
                request_ref=request_ref,
                raw_evidence_ref=observer.raw_evidence_ref,
                failure_code=failure_code,
            )
        except Exception as terminal_exc:
            raise LiveAcquisitionExecutionError(
                "live_failure_terminal_persistence_failed",
                type(terminal_exc).__name__,
            ) from exc
        if isinstance(exc, LiveAcquisitionExecutionError):
            raise
        raise LiveAcquisitionExecutionError(
            failure_code,
            type(exc).__name__,
        ) from exc


def _execute_authorized_live_acquisition(
    *,
    authority: _CanonicalAuthority,
    entry_id: str,
    resolved: ResolvedAcquisitionAuthority,
    constraints: LiveCatalogExecutionConstraints,
    journal: fabric_data_plane.AppendOnlyEvidenceJournal,
    request_ref: JournalEventRef,
    store: FileSystemCAS,
    observer: _LiveHTTPExecutionObserver,
    authorization: fabric_data_plane.LiveExecutionAuthorization,
    family_receipt: Mapping[str, Any],
    manifest: ConnectorManifestSpec,
    connection_config: fabric_connectors.ConnectionConfig,
    cas_root: Path,
) -> LiveSourceExecutionEvidence:
    """Execute and independently reopen one already-authorized live carrier."""

    entry = resolved.entry
    attempt_id = authorization.attempt_id
    captured_result: FetchResult[Any] | None = None
    captured_page_count: int | None = None

    def _capture_result(
        connector_id: str,
        dataset_id: str,
        fetch_request: FetchRequest,
        result: FetchResult[Any],
    ) -> None:
        nonlocal captured_result, captured_page_count
        if observer.raw_evidence_ref is None or observer.raw_body is None:
            raise LiveAcquisitionExecutionError(
                "live_result_before_raw_evidence",
                attempt_id,
            )
        if captured_result is not None:
            raise LiveAcquisitionExecutionError(
                "live_result_sink_duplicate",
                attempt_id,
            )
        captured_page_count = _validate_live_result_scope(
            resolved=resolved,
            constraints=constraints,
            connector_id=connector_id,
            dataset_id=dataset_id,
            fetch_request=fetch_request,
            result=result,
            raw_body=observer.raw_body,
            raw_status_code=observer.raw_status_code,
        )
        captured_result = result

    baseline_before_sha256 = resolved.baseline_content_sha256
    baseline_after_sha256: str | None = None
    try:
        ingestion_result = run_orchestrated_ingestion(
            connector_manifest=manifest,
            source=f"acquisition:{entry.target_variable}",
            license_name=resolved.license_id,
            cas_root=cas_root,
            connection_config=connection_config,
            produce_snapshot=True,
            raw_result_sink=_capture_result,
            raw_http_response_observer=observer,
        )
    finally:
        try:
            after_authority = ResolvedAcquisitionAuthority.model_validate(
                authority.resolve(entry_id)
            )
        except Exception as exc:
            raise LiveAcquisitionExecutionError(
                "live_baseline_identity_drift",
                type(exc).__name__,
            ) from exc
        baseline_after_sha256 = after_authority.baseline_content_sha256
        if baseline_after_sha256 != baseline_before_sha256:
            raise LiveAcquisitionExecutionError(
                "live_baseline_identity_drift",
                baseline_after_sha256,
            )
    if captured_result is None or captured_page_count is None:
        raise LiveAcquisitionExecutionError("live_result_sink_not_invoked", attempt_id)
    if (
        observer.raw_evidence_ref is None
        or observer.raw_artifact_ref is None
        or observer.raw_body is None
    ):
        raise LiveAcquisitionExecutionError("live_raw_evidence_missing", attempt_id)
    if (
        ingestion_result.evidence_bundle_ref is None
        or ingestion_result.data_snapshot_ref is None
        or ingestion_result.datasets_fetched != 1
    ):
        raise LiveAcquisitionExecutionError(
            "live_ingestion_snapshot_missing",
            attempt_id,
        )
    if baseline_after_sha256 is None:  # pragma: no cover - finally assigns or raises
        raise LiveAcquisitionExecutionError("live_baseline_identity_drift")
    snapshot = DataSnapshot.model_validate(
        from_canonical_bytes(store.get_bytes(ingestion_result.data_snapshot_ref.artifact_id))
    )
    evidence_bundle = EvidenceBundle.model_validate(
        from_canonical_bytes(store.get_bytes(ingestion_result.evidence_bundle_ref.artifact_id))
    )
    if snapshot.evidence_ref != ingestion_result.evidence_bundle_ref:
        raise LiveAcquisitionExecutionError(
            "live_snapshot_evidence_ref_drift",
            attempt_id,
        )
    if evidence_bundle.sources != [snapshot.data_ref]:
        raise LiveAcquisitionExecutionError(
            "live_evidence_bundle_source_drift",
            attempt_id,
        )
    normalized_bytes = store.get_bytes(snapshot.data_ref.artifact_id)
    normalized_result = ResultSerializer.deserialize(normalized_bytes)
    _require_same_fetch_result(captured_result, normalized_result)
    raw_body_sha256 = "sha256:" + hashlib.sha256(observer.raw_body).hexdigest()
    transport_trace = fabric_data_plane.resolve_live_transport_trace(observer.raw_evidence_ref)
    evidence = data_forge_read_api.catalog.build_live_source_execution_evidence(
        authorization=authorization,
        family_receipt=family_receipt,
        request_ref=request_ref,
        raw_evidence_ref=observer.raw_evidence_ref,
        transport_trace=transport_trace,
        raw_artifact_id=observer.raw_artifact_ref.artifact_id,
        evidence_bundle_ref=ingestion_result.evidence_bundle_ref,
        data_snapshot_ref=ingestion_result.data_snapshot_ref,
        normalized_data_artifact_id=snapshot.data_ref.artifact_id,
        variable_count=len(authorization.request_variables),
        page_count=captured_page_count,
        baseline_before_sha256=baseline_before_sha256,
        baseline_after_sha256=baseline_after_sha256,
        raw_body_sha256=raw_body_sha256,
        normalized_result_content_sha256=normalized_result.version.content_hash,
    )
    authority.resolve_live_source_execution(entry_id, evidence, store)
    return evidence


def _live_failure_code(exc: Exception) -> str:
    """Preserve a typed failure code or derive a syntax-safe terminal code."""

    value = getattr(exc, "code", None)
    raw = value if isinstance(value, str) and value.strip() else type(exc).__name__
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", raw)
    normalized = re.sub(r"[^a-z0-9]+", "_", snake.lower()).strip("_")
    if not normalized or not normalized[0].isalpha():
        normalized = f"failure_{normalized or 'unknown'}"
    if len(normalized) > 120:
        suffix = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
        normalized = f"{normalized[:107].rstrip('_')}_{suffix}"
    return normalized


def _live_request_projection(
    resolved: ResolvedAcquisitionAuthority,
    *,
    constraints: LiveCatalogExecutionConstraints,
) -> dict[str, object]:
    entry = resolved.entry
    registration = resolved.registration
    return {
        "authority_entry_id": entry.entry_id,
        "authority_registry_content_sha256": resolved.registry_content_sha256,
        "variable_id": entry.target_variable,
        "request_variables": [registration.request_dataset_id],
        "source_lane": "live_fetch",
        "dataset_id": entry.landing_dataset_id,
        "distribution_id": entry.landing_distribution_id,
        "connector_id": registration.connector_id,
        "profile_id": registration.source_profile_id,
        "request_dataset_id": registration.request_dataset_id,
        "filters": {"country": [constraints.country_code]},
        "date_start": constraints.date_start,
        "date_end": constraints.date_end,
        "page_size": constraints.page_size,
        "schema_contract": entry.schema_projection(),
    }


def _require_constraints_within_authority_scope(
    entry: AcquisitionAuthorityEntry,
    constraints: LiveCatalogExecutionConstraints,
) -> None:
    if constraints.country_code not in entry.country_codes:
        raise LiveAcquisitionExecutionError(
            "live_request_outside_authority_countries",
            constraints.country_code,
        )
    try:
        owner_start, owner_end = data_forge_read_api.catalog.resolve_live_temporal_bounds(entry)
    except Exception as exc:
        raise LiveAcquisitionExecutionError(
            "live_authority_temporal_scope_invalid",
        ) from exc
    if owner_start is None or owner_end is None:
        return
    if constraints.start_year < owner_start or constraints.end_year > owner_end:
        raise LiveAcquisitionExecutionError(
            "live_request_outside_authority_period",
            f"{constraints.start_year}:{constraints.end_year}",
        )


def _validate_live_result_scope(
    *,
    resolved: ResolvedAcquisitionAuthority,
    constraints: LiveCatalogExecutionConstraints,
    connector_id: str,
    dataset_id: str,
    fetch_request: FetchRequest,
    result: FetchResult[Any],
    raw_body: bytes,
    raw_status_code: int | None,
) -> int:
    registration = resolved.registration
    entry = resolved.entry
    expected_start = datetime(constraints.start_year, 1, 1, tzinfo=UTC)
    expected_end = datetime(constraints.end_year, 12, 31, tzinfo=UTC)
    if (
        connector_id != registration.connector_id
        or dataset_id != registration.request_dataset_id
        or fetch_request.dataset_id != registration.request_dataset_id
        or dict(fetch_request.filters) != {"country": (constraints.country_code,)}
        or fetch_request.date_start != expected_start
        or fetch_request.date_end != expected_end
        or fetch_request.page_size != constraints.page_size
        or fetch_request.retryable is not False
    ):
        raise LiveAcquisitionExecutionError(
            "live_normalized_request_drift",
            registration.request_dataset_id,
        )
    if raw_status_code is None or not 200 <= raw_status_code < 300:
        raise LiveAcquisitionExecutionError(
            "live_http_status_not_success",
            str(raw_status_code),
        )
    try:
        raw_payload = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LiveAcquisitionExecutionError(
            "live_raw_response_not_json",
            type(exc).__name__,
        ) from exc
    if (
        not isinstance(raw_payload, list)
        or len(raw_payload) < 2
        or not isinstance(raw_payload[0], Mapping)
        or not isinstance(raw_payload[1], list)
    ):
        raise LiveAcquisitionExecutionError("live_raw_response_shape_drift")
    metadata = raw_payload[0]
    raw_rows = raw_payload[1]
    try:
        page = int(str(metadata.get("page")))
        pages = int(str(metadata.get("pages")))
        per_page = int(str(metadata.get("per_page")))
        total = int(str(metadata.get("total")))
    except (TypeError, ValueError) as exc:
        raise LiveAcquisitionExecutionError(
            "live_raw_page_metadata_drift",
        ) from exc
    if page != 1 or pages != 1 or per_page != constraints.page_size or total != len(raw_rows):
        raise LiveAcquisitionExecutionError("live_raw_page_metadata_drift")
    if any(
        not _raw_worldbank_row_in_scope(
            row,
            indicator_id=registration.request_dataset_id,
            country_code=constraints.country_code,
            start_year=constraints.start_year,
            end_year=constraints.end_year,
        )
        for row in raw_rows
    ):
        raise LiveAcquisitionExecutionError("live_normalized_scope_drift")
    normalized_rows = _normalized_result_rows(result.data)
    if (
        result.row_count != len(normalized_rows)
        or len(raw_rows) != len(normalized_rows)
        or any(
            row.get("indicator_id") != registration.request_dataset_id
            or row.get("country_code") != constraints.country_code
            or not _year_in_scope(
                row.get("year"),
                start_year=constraints.start_year,
                end_year=constraints.end_year,
            )
            for row in normalized_rows
        )
    ):
        raise LiveAcquisitionExecutionError("live_normalized_scope_drift")
    if any(not isinstance(row, Mapping) for row in raw_rows):
        raise LiveAcquisitionExecutionError("live_normalized_raw_projection_drift")
    expected_frame = normalize_worldbank_records(
        [row for row in raw_rows if isinstance(row, Mapping)],
        registration.request_dataset_id,
    )
    if isinstance(result.data, pd.DataFrame):
        actual_frame = result.data
    else:
        actual_frame = pd.DataFrame(normalized_rows)
    if list(actual_frame.columns) != list(expected_frame.columns) or not actual_frame.reset_index(
        drop=True
    ).equals(expected_frame.reset_index(drop=True)):
        raise LiveAcquisitionExecutionError("live_normalized_raw_projection_drift")
    schema_ref = entry.schema_contract_ref
    if not schema_ref.startswith("fabric://") or "@" not in schema_ref:
        raise LiveAcquisitionExecutionError("live_schema_contract_ref_invalid")
    schema_id, schema_version = schema_ref.removeprefix("fabric://").rsplit("@", 1)
    raw_sha256 = "sha256:" + hashlib.sha256(raw_body).hexdigest()
    if (
        result.schema_id != schema_id
        or result.schema_version != schema_version
        or result.version.content_hash != raw_sha256
        or result.has_more
        or result.next_page_token is not None
    ):
        raise LiveAcquisitionExecutionError("live_normalized_contract_drift")
    return pages


def _raw_worldbank_row_in_scope(
    row: object,
    *,
    indicator_id: str,
    country_code: str,
    start_year: int,
    end_year: int,
) -> bool:
    if not isinstance(row, Mapping):
        return False
    indicator = row.get("indicator")
    return bool(
        isinstance(indicator, Mapping)
        and indicator.get("id") == indicator_id
        and row.get("countryiso3code") == country_code
        and _year_in_scope(
            row.get("date"),
            start_year=start_year,
            end_year=end_year,
        )
    )


def _year_in_scope(value: object, *, start_year: int, end_year: int) -> bool:
    if isinstance(value, bool):
        return False
    try:
        year = int(str(value))
    except (TypeError, ValueError):
        return False
    return start_year <= year <= end_year


def _normalized_result_rows(data: object) -> list[dict[str, object]]:
    if hasattr(data, "to_dict"):
        records = data.to_dict(orient="records")
    elif isinstance(data, Sequence) and not isinstance(
        data,
        (str, bytes, bytearray),
    ):
        records = list(data)
    else:
        raise LiveAcquisitionExecutionError("live_normalized_rows_unresolved")
    if any(not isinstance(row, Mapping) for row in records):
        raise LiveAcquisitionExecutionError("live_normalized_rows_unresolved")
    return [{str(key): value for key, value in row.items()} for row in records]


def _require_same_fetch_result(
    captured: FetchResult[Any],
    persisted: FetchResult[Any],
) -> None:
    captured_bytes, captured_media_type = ResultSerializer.serialize(captured)
    persisted_bytes, persisted_media_type = ResultSerializer.serialize(persisted)
    if captured_media_type != persisted_media_type or captured_bytes != persisted_bytes:
        raise LiveAcquisitionExecutionError("live_normalized_result_drift")


def measure_quarantined_sample(
    raw_evidence_ref: JournalEventRef,
    *,
    dataset_id: str,
    distribution_id: str,
    source_profile_id: str,
) -> MeasuredSchemaProfile:
    """Measure columns and row count from exact journaled response bytes."""

    body = resolve_raw_response_body(raw_evidence_ref)
    return _measure_quarantined_body(
        body,
        raw_evidence_ref=raw_evidence_ref,
        dataset_id=dataset_id,
        distribution_id=distribution_id,
        source_profile_id=source_profile_id,
        parser_mode="owner_response_json",
    )


def _measure_quarantined_body(
    body: bytes,
    *,
    raw_evidence_ref: JournalEventRef,
    dataset_id: str,
    distribution_id: str,
    source_profile_id: str,
    parser_mode: str,
) -> MeasuredSchemaProfile:
    """Measure one quarantined carrier chosen by the canonical lane owner."""

    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("quarantined_sample_not_json") from exc
    if isinstance(payload, Mapping):
        records: list[Mapping[str, Any]] = [payload]
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        records = [row for row in payload if isinstance(row, Mapping)]
        if len(records) != len(payload):
            raise ValueError("quarantined_sample_rows_not_mappings")
    else:
        raise ValueError("quarantined_sample_not_tabular")
    if not records:
        raise ValueError("quarantined_sample_empty")
    names = sorted({str(key) for row in records for key in row})
    columns = tuple(
        MeasuredColumn(
            name=name,
            logical_type=_logical_type([row.get(name) for row in records]),
            nullable=any(name not in row or row.get(name) is None for row in records),
        )
        for name in names
    )
    values: dict[str, object] = {
        "dataset_id": dataset_id,
        "distribution_id": distribution_id,
        "source_profile_id": source_profile_id,
        "columns": [column.model_dump(mode="json") for column in columns],
        "sample_row_count": len(records),
        "sample_content_sha256": f"sha256:{hashlib.sha256(body).hexdigest()}",
        "raw_evidence_event_sha256": raw_evidence_ref.event_sha256,
        "inference_mode": "measured_quarantine",
        "parser_mode": parser_mode,
    }
    return MeasuredSchemaProfile(
        measurement_id="measurement:" + content_sha256(values),
        **values,
    )


def build_metadata_schema_profile(
    *,
    dataset_id: str,
    distribution_id: str,
    source_profile_id: str,
    columns: Sequence[MeasuredColumn],
    raw_evidence_event_sha256: str,
) -> MeasuredSchemaProfile:
    """Represent an unearned metadata-only profile for fail-closed admission."""

    ordered = tuple(sorted(columns, key=lambda column: column.name))
    values: dict[str, object] = {
        "dataset_id": dataset_id,
        "distribution_id": distribution_id,
        "source_profile_id": source_profile_id,
        "columns": [column.model_dump(mode="json") for column in ordered],
        "sample_row_count": 0,
        "sample_content_sha256": None,
        "raw_evidence_event_sha256": raw_evidence_event_sha256,
        "inference_mode": "metadata_only",
        "parser_mode": "metadata_only",
    }
    return MeasuredSchemaProfile(
        measurement_id="measurement:" + content_sha256(values),
        **values,
    )


def _require_semantic_handshake(
    *,
    artifact_store: _ArtifactStore,
    boundary_candidate: epoch_contract.AcquisitionSemanticBoundaryCandidate,
    prepared_epoch: _PreparedSemanticEpoch,
) -> None:
    """Reload and bind the pre-passport candidate and prepared epoch bytes."""

    if str(getattr(prepared_epoch.status, "value", prepared_epoch.status)) != "prepared":
        raise ValueError("semantic_epoch_preparation_not_established")
    if boundary_candidate.candidate_ref not in prepared_epoch.boundary_candidate_refs:
        raise ValueError("semantic_candidate_not_bound_by_prepared_epoch")
    try:
        candidate_mapping = epoch_contract.load_verified_epoch_statement(
            store=artifact_store,
            ref=boundary_candidate.candidate_ref,
            expected_kind="epoch.acquisition_semantic_boundary_candidate",
        )
    except ValueError as exc:
        raise ValueError("semantic_boundary_candidate_cas_binding_mismatch") from exc
    candidate_statement = (
        epoch_contract.AcquisitionSemanticBoundaryCandidateStatement.model_validate(
            candidate_mapping
        )
    )
    if (
        candidate_statement != boundary_candidate.statement
        or epoch_contract.acquisition_semantic_candidate_content_hash(candidate_statement)
        != boundary_candidate.candidate_content_hash
    ):
        raise ValueError("semantic_boundary_candidate_cas_binding_mismatch")
    if (
        candidate_statement.scope_identity_ref
        != prepared_epoch.query.scope_identity.scope_identity_ref
        or candidate_statement.authority_purpose != prepared_epoch.query.authority_purpose
        or candidate_statement.requested_query_context_ref
        != prepared_epoch.query.requested_query_context_ref
    ):
        raise SemanticEpochAdmissionResolutionError(
            "query_context_mismatch",
            "semantic candidate belongs to another prepared query",
        )
    try:
        prepared_mapping = epoch_contract.load_verified_epoch_statement(
            store=artifact_store,
            ref=prepared_epoch.prepared_epoch_ref,
            expected_kind="epoch.prepared",
        )
    except ValueError as exc:
        raise ValueError("prepared_semantic_epoch_cas_binding_mismatch") from exc
    raw_stamp = prepared_mapping.get("stamp")
    if not isinstance(raw_stamp, Mapping):
        raise SemanticEpochAdmissionResolutionError(
            "basis_mismatch",
            "prepared epoch stamp is absent or malformed",
        )
    predicate_class = raw_stamp.get("predicate_provenance_class")
    if predicate_class in {
        "consumer_asserted",
        "institutionally_supplied",
        "not_established",
    }:
        raise SemanticEpochAdmissionResolutionError(
            "predicate_not_authority_grade",
            f"prepared epoch predicate class is {predicate_class}",
        )
    try:
        stamp = epoch_contract.SemanticEpochStamp.model_validate(raw_stamp)
        manifest_mapping = epoch_contract.load_verified_epoch_statement(
            store=artifact_store,
            ref=stamp.semantic_manifest_ref,
            expected_kind="epoch.semantic_manifest",
        )
        epoch_runtime = importlib.import_module("polisyos.runtime.quality.semantic_epoch")
        manifest = epoch_runtime.SemanticEpochManifest.model_validate(manifest_mapping)
    except (AttributeError, ImportError, TypeError, ValueError) as exc:
        raise SemanticEpochAdmissionResolutionError(
            "basis_mismatch",
            "prepared epoch manifest basis is not verified",
        ) from exc
    if stamp.epoch_ref != manifest.epoch_ref:
        raise SemanticEpochAdmissionResolutionError(
            "epoch_ref_mismatch",
            "prepared epoch stamp does not identify its semantic manifest",
        )
    if stamp.semantic_manifest_hash != manifest.manifest_content_hash:
        raise SemanticEpochAdmissionResolutionError(
            "basis_mismatch",
            "prepared epoch stamp carries another manifest content hash",
        )
    expected_mapping = {
        name: value
        for name, value in prepared_epoch.model_dump(mode="python").items()
        if name not in {"prepared_epoch_ref", "prepared_content_hash"}
    }
    if epoch_contract.canonical_epoch_bytes(
        prepared_mapping
    ) != epoch_contract.canonical_epoch_bytes(
        expected_mapping
    ) or prepared_epoch.prepared_content_hash != epoch_contract.epoch_semantic_content_hash(
        domain="polisyos.epoch.prepared.v1",
        value=expected_mapping,
    ):
        raise ValueError("prepared_semantic_epoch_cas_binding_mismatch")


def build_admission_passport(
    *,
    epoch_id: int,
    raw_evidence_ref: JournalEventRef,
    artifact_store: _ArtifactStore,
    raw_artifact_id: str,
    authority: _CanonicalAuthority,
    boundary_candidate: epoch_contract.AcquisitionSemanticBoundaryCandidate,
    prepared_epoch: _PreparedSemanticEpoch,
    live_source_execution: LiveSourceExecutionEvidence | None = None,
) -> AdmissionPassport:
    """Resolve canonical owners and derive a measured admission passport."""

    _require_semantic_handshake(
        artifact_store=artifact_store,
        boundary_candidate=boundary_candidate,
        prepared_epoch=prepared_epoch,
    )

    try:
        body = resolve_raw_response_body(raw_evidence_ref)
        request_event = resolve_linked_request_event(raw_evidence_ref)
    except Exception as exc:
        raise ValueError("raw_evidence_ref_unresolved") from exc
    request = request_event.get("request")
    if not isinstance(request, Mapping):
        raise ValueError("acquisition_request_contract_missing")
    entry_id = str(request.get("authority_entry_id") or "")
    if not entry_id:
        raise ValueError("acquisition_authority_entry_missing")
    try:
        resolved = ResolvedAcquisitionAuthority.model_validate(authority.resolve(entry_id))
    except Exception as exc:
        raise ValueError("acquisition_authority_unresolved") from exc
    entry = resolved.entry
    if entry.source_lane == "live_fetch":
        if live_source_execution is None:
            raise ValueError("live_source_execution_evidence_required")
        try:
            normalized_body = authority.resolve_live_source_body(
                entry_id,
                live_source_execution,
                artifact_store,
            )
        except Exception as exc:
            raise ValueError("live_source_execution_unresolved") from exc
        measured_profile = _measure_quarantined_body(
            normalized_body,
            raw_evidence_ref=raw_evidence_ref,
            dataset_id=entry.landing_dataset_id,
            distribution_id=entry.landing_distribution_id,
            source_profile_id=resolved.registration.source_profile_id,
            parser_mode="fabric_normalized_fetch_result",
        )
    else:
        if live_source_execution is not None:
            raise ValueError("local_lift_live_execution_evidence_forbidden")
        measured_profile = measure_quarantined_sample(
            raw_evidence_ref,
            dataset_id=entry.landing_dataset_id,
            distribution_id=entry.landing_distribution_id,
            source_profile_id=resolved.registration.source_profile_id,
        )
    schema_validation = _validate_request_and_measured_schema(
        request_event=request_event,
        request=request,
        measured_profile=measured_profile,
        resolved=resolved,
    )
    source_authority_verified = bool(
        schema_validation.conformant
        and (
            live_source_execution is not None
            if entry.source_lane == "live_fetch"
            else authority.verify_source_body(entry_id, body)
        )
    )
    raw_verified = True
    cas_verified = _cas_bytes_match(
        artifact_store,
        artifact_id=raw_artifact_id,
        expected=body,
    )
    scan = scan_secret_and_pii(
        body,
        scope="connector request/response payloads",
        artifact_ref_or_route=raw_evidence_ref.event_sha256,
        redact=False,
        block_on_findings=True,
    )
    detector_version = scan.reports[0].detector_version if scan.reports else "owner_scan_unresolved"
    pii_evidence = PIIScanEvidence(
        artifact_ref_or_route=raw_evidence_ref.event_sha256,
        detector_version=detector_version,
        finding_kinds=tuple(sorted(scan.finding_kinds)),
        blocked=scan.has_findings,
    )
    license_id = resolved.license_id
    normalized_license = _normalize_license(license_id)
    license_evidence = LicenseEvidence(
        license_id=license_id,
        normalized_license_id=normalized_license,
        disposition=LicenseDisposition(resolved.license_disposition.value),
        authority_ref=resolved.license_authority_ref,
        authority_content_sha256=resolved.license_authority_content_sha256,
    )
    l5_evidence = L5TrustEvidence(
        family_id=resolved.l5_trust.family_id,
        resolved=True,
        tier=resolved.l5_trust.tier,
        trust_cap=resolved.l5_trust.trust_cap,
        trust_multiplier=resolved.l5_trust.trust_multiplier,
        authority_ref=resolved.l5_trust.authority_ref,
        owner_ref=resolved.l5_trust.owner_ref,
    )
    observation_class = (
        ObservationProvenanceClass.PROXY
        if resolved.field_binding.is_proxy
        else ObservationProvenanceClass.OBSERVED
    )
    body_sha = f"sha256:{hashlib.sha256(body).hexdigest()}"
    dataset_version = (
        live_source_execution.normalized_result_content_sha256
        if live_source_execution is not None
        else resolved.upstream_catalog_projection_sha256
    )
    values: dict[str, object] = {
        "schema_version": PASSPORT_SCHEMA_VERSION,
        "epoch_id": epoch_id,
        "variable_id": entry.target_variable,
        "source_lane": entry.source_lane,
        "observation_class": observation_class,
        "authority_entry_id": entry.entry_id,
        "authority_provision_id": resolved.authority_provision_id,
        "authority_provision_content_sha256": (resolved.authority_provision_content_sha256),
        "authority_registry_content_sha256": resolved.registry_content_sha256,
        "upstream_catalog_projection_sha256": (resolved.upstream_catalog_projection_sha256),
        "baseline_content_sha256": resolved.baseline_content_sha256,
        "registration": resolved.registration,
        "measured_profile": measured_profile,
        "field_binding": resolved.field_binding,
        "raw_evidence_ref": raw_evidence_ref,
        "raw_evidence_verified": raw_verified,
        "raw_artifact_id": raw_artifact_id,
        "cas_evidence_verified": cas_verified,
        "license_evidence": license_evidence,
        "pii_scan": pii_evidence,
        "source_watermark": body_sha,
        "dataset_version": dataset_version,
        "l5_trust": l5_evidence,
        "schema_validation": schema_validation,
        "live_source_execution": live_source_execution,
        "source_authority_verified": source_authority_verified,
        "semantic_boundary_candidate_ref": boundary_candidate.candidate_ref,
        "semantic_boundary_candidate_content_hash": (boundary_candidate.candidate_content_hash),
        "semantic_epoch_ref": prepared_epoch.stamp.epoch_ref,
        "semantic_epoch_stamp_sha256": epoch_contract.semantic_epoch_stamp_content_hash(
            prepared_epoch.stamp
        ),
        "semantic_epoch_stamp": prepared_epoch.stamp,
        "prepared_semantic_epoch_ref": prepared_epoch.prepared_epoch_ref,
    }
    rejection_codes = _derive_rejection_codes(
        variable_id=entry.target_variable,
        observation_class=observation_class,
        measured_profile=measured_profile,
        field_binding=resolved.field_binding,
        raw_evidence_verified=raw_verified,
        cas_evidence_verified=cas_verified,
        license_evidence=license_evidence,
        pii_scan=pii_evidence,
        source_watermark=body_sha,
        dataset_version=dataset_version,
        l5_trust=l5_evidence,
        schema_validation=schema_validation,
        source_authority_verified=source_authority_verified,
    )
    status = _derive_status(
        rejection_codes=rejection_codes,
        field_binding=resolved.field_binding,
        observation_class=observation_class,
        l5_trust=l5_evidence,
        schema_validation=schema_validation,
        source_authority_verified=source_authority_verified,
    )
    identity_payload = {key: _json_value(value) for key, value in values.items()}
    return AdmissionPassport(
        passport_id="passport:" + content_sha256(identity_payload),
        **values,
        status=status,
        rejection_codes=rejection_codes,
    )


def admit_acquisition_with_semantic_epoch(
    *,
    epoch_id: int,
    raw_evidence_ref: JournalEventRef,
    artifact_store: _ArtifactStore,
    authority: _CanonicalAuthority,
    overlay: _CatalogAcquisitionOverlay,
    epoch_service: SemanticEpochService,
    epoch_query: EpochResolutionQuery,
    live_source_execution: LiveSourceExecutionEvidence | None = None,
) -> ActivatedSemanticEpochAdmissionReceipt | PersistedSemanticEpochProductionReceipt:
    """Run the real two-phase acquisition bridge and preserve typed negatives."""

    raw_body = resolve_raw_response_body(raw_evidence_ref)
    raw_artifact_id = ArtifactID(f"sha256:{hashlib.sha256(raw_body).hexdigest()}")
    if not artifact_store.has(raw_artifact_id):
        raise ValueError("raw_cas_evidence_unresolved")
    source_artifact_id = (
        raw_artifact_id
        if live_source_execution is None
        else ArtifactID(str(live_source_execution.normalized_data_artifact_id))
    )
    source_manifest = artifact_store.get_manifest(source_artifact_id)
    source_payload = artifact_store.get_bytes(source_artifact_id)
    source_report = artifact_store.verify(source_artifact_id)
    source_ref = ArtifactRef(
        artifact_id=source_artifact_id,
        kind=str(getattr(source_manifest, "kind", "")),
        media_type=str(getattr(source_manifest, "media_type", "")),
    )
    if (
        not bool(getattr(source_report, "ok", False))
        or f"sha256:{hashlib.sha256(source_payload).hexdigest()}" != str(source_artifact_id)
        or getattr(source_manifest, "artifact_id", None) != source_artifact_id
    ):
        raise ValueError("semantic_candidate_source_record_unverified")
    native_query = epoch_service.acquisition_owner_query(query=epoch_query)
    if (
        native_query.scope_identity_ref != epoch_query.scope_identity.scope_identity_ref
        or native_query.authority_purpose != epoch_query.authority_purpose
        or native_query.requested_query_context_ref != epoch_query.requested_query_context_ref
    ):
        raise SemanticEpochAdmissionResolutionError(
            "query_context_mismatch",
            "acquisition owner query belongs to another epoch request",
        )
    statement = epoch_contract.AcquisitionSemanticBoundaryCandidateStatement(
        source_record_ref=source_ref,
        source_record_content_hash=str(source_artifact_id),
        scope_identity_ref=native_query.scope_identity_ref,
        authority_purpose=native_query.authority_purpose,
        valid_effect_coordinate_ref=native_query.valid_effect_coordinate_ref,
        visibility_knowledge_cutoff_ref=(native_query.visibility_knowledge_cutoff_ref),
        purpose_admission_cutoff_ref=native_query.purpose_admission_cutoff_ref,
        requested_query_context_ref=native_query.requested_query_context_ref,
    )
    candidate_bytes = epoch_contract.acquisition_semantic_candidate_bytes(statement)
    candidate_ref = artifact_store.put_bytes(
        candidate_bytes,
        ArtifactWriteOptions(
            kind="epoch.acquisition_semantic_boundary_candidate",
            media_type="application/vnd.polisyos.epoch+json",
        ),
    )
    candidate = epoch_contract.AcquisitionSemanticBoundaryCandidate(
        candidate_ref=candidate_ref,
        candidate_content_hash=(
            epoch_contract.acquisition_semantic_candidate_content_hash(statement)
        ),
        statement=statement,
    )
    prepared = epoch_service.prepare_acquisition_candidate(
        query=epoch_query,
        candidate_ref=candidate_ref,
    )
    passport = build_admission_passport(
        epoch_id=epoch_id,
        raw_evidence_ref=raw_evidence_ref,
        artifact_store=artifact_store,
        raw_artifact_id=str(raw_artifact_id),
        authority=authority,
        boundary_candidate=candidate,
        prepared_epoch=prepared,
        live_source_execution=live_source_execution,
    )
    pending = overlay.admit_epoch(
        passport=passport,
        prepared_epoch=prepared,
        boundary_candidate=candidate,
        artifact_store=artifact_store,
        authority=authority,
    )
    admitted_ref = overlay.emit_admitted_boundary_evidence(
        query=native_query,
        passport=passport,
        prepared_epoch=prepared,
        boundary_candidate=candidate,
        pending_receipt=pending,
        artifact_store=artifact_store,
    )
    production = epoch_service.finalize_admitted_epoch(
        prepared_epoch_ref=prepared.prepared_epoch_ref,
        admitted_boundary_evidence_ref=admitted_ref,
    )
    if production.requested_query_context_ref != prepared.stamp.requested_query_context_ref:
        raise SemanticEpochAdmissionResolutionError(
            "query_context_mismatch",
            "epoch production receipt belongs to another prepared query",
        )
    if (
        production.status in {"appended", "no_change"}
        and production.epoch_ref != prepared.stamp.epoch_ref
    ):
        raise SemanticEpochAdmissionResolutionError(
            "epoch_ref_mismatch",
            "positive epoch production receipt identifies another epoch",
        )
    if production.status not in {"appended", "no_change"}:
        return production
    activated = overlay.activate_semantic_epoch(
        pending_receipt=pending,
        production_receipt=production,
        artifact_store=artifact_store,
    )
    admitted_mapping = epoch_contract.load_verified_epoch_statement(
        store=artifact_store,
        ref=admitted_ref,
        expected_kind="epoch.admitted_acquisition_boundary_evidence",
    )
    admitted = epoch_contract.AdmittedAcquisitionBoundaryEvidence.model_validate(admitted_mapping)
    return ActivatedSemanticEpochAdmissionReceipt(
        passport_ref=admitted.passport_ref,
        prepared_epoch_ref=prepared.prepared_epoch_ref,
        pending_overlay_receipt_ref=pending.receipt_ref,
        semantic_epoch_production_receipt_ref=production.receipt_ref,
        overlay_admission_receipt_ref=activated.receipt_ref,
        native_membership_receipt_ref=admitted.native_membership_receipt_ref,
        semantic_denominator_receipt_ref=admitted.semantic_denominator_receipt_ref,
        semantic_projection_verification_receipt_ref=(
            admitted.semantic_projection_verification_receipt_ref
        ),
        semantic_epoch_stamp=prepared.stamp,
        activation_state="active",
    )


def admit_acquisition_with_production_semantic_epoch(
    *,
    repo_root: Path,
    epoch_id: int,
    raw_evidence_ref: JournalEventRef,
    artifact_store: FileSystemCAS,
    authority: _CanonicalAuthority,
    overlay_path: Path,
    epoch_history_root: Path,
    epoch_scope_identity: EpochScopeIdentity,
    authority_purpose: str,
    valid_effect_coordinate_evidence_ref: ArtifactRef,
    visibility_knowledge_cutoff_evidence_ref: ArtifactRef,
    purpose_admission_cutoff_evidence_ref: ArtifactRef,
    facet_source_refs: Mapping[str, ArtifactRef],
    live_source_execution: LiveSourceExecutionEvidence | None = None,
) -> ActivatedSemanticEpochAdmissionReceipt | PersistedSemanticEpochProductionReceipt:
    """Compose and invoke the production epoch adapter without policy self-admission.

    Operational paths and evidence selectors are explicit inputs.  All semantic
    coordinate digests are independently recomputed, and the canonical empty
    predicate-policy admission index therefore yields ``policy_admission_missing``
    until an institutional owner is appointed.
    """

    from polisyos.runtime.quality import chronology_qualification
    from polisyos.runtime.quality import semantic_epoch as epoch_runtime
    from polisyos.runtime.quality.semantic_epoch_store import (
        FileSemanticEpochHistoryRepository,
    )
    from polisyos.runtime.quality.substrate_registry import (
        DEFAULT_L3_LEX_KG_PATH,
        default_substrate_catalog_paths,
        load_l5_catalog_authority,
    )

    root = repo_root.resolve()
    boundary_path = (
        root / "architecture/policy_design_case/layer3_gy_epoch_boundary_source_registry.json"
    )
    facet_path = root / "architecture/policy_design_case/layer3_gy_semantic_facet_registry.json"
    lex_store: Any | None = None
    try:
        boundary_registry = epoch_runtime.load_boundary_registry(boundary_path)
        facet_registry = epoch_runtime.load_facet_registry(facet_path)
        if set(facet_source_refs) != {
            row.source_binding_ref for row in facet_registry.registrations
        }:
            raise SemanticEpochAdmissionResolutionError(
                "resolver_unavailable",
                "semantic facet source-binding denominator differs",
            )
        l5_owner = load_l5_catalog_authority(default_substrate_catalog_paths(root))
        lex_module = importlib.import_module("polisyos.lex.knowledge.store")
        lex_path = root / DEFAULT_L3_LEX_KG_PATH
        lex_store = lex_module.LegalKnowledgeStore(
            lex_path,
            lex_path.parent,
            canonical_db_ref_path=DEFAULT_L3_LEX_KG_PATH,
        )
        overlay = data_forge_read_api.catalog.CatalogAcquisitionOverlay(
            authority.baseline_path,
            overlay_path,
        )
        overlay.initialize()
        history = FileSemanticEpochHistoryRepository(
            root=epoch_history_root,
            artifacts=artifact_store,
        )
    except SemanticEpochAdmissionResolutionError:
        raise
    except (ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise SemanticEpochAdmissionResolutionError(
            "resolver_unavailable",
            type(exc).__name__,
        ) from exc
    try:
        try:
            query = epoch_runtime.build_epoch_resolution_query_from_evidence(
                artifact_store=artifact_store,
                scope_identity=epoch_scope_identity,
                authority_purpose=authority_purpose,
                valid_effect_coordinate_evidence_ref=(valid_effect_coordinate_evidence_ref),
                visibility_knowledge_cutoff_evidence_ref=(visibility_knowledge_cutoff_evidence_ref),
                purpose_admission_cutoff_evidence_ref=(purpose_admission_cutoff_evidence_ref),
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise SemanticEpochAdmissionResolutionError(
                "basis_mismatch",
                type(exc).__name__,
            ) from exc
        chronology_adapter = (
            epoch_runtime.SemanticEpochQualificationAdapter.from_unallocated_policy_authority(
                history=history,
                artifacts=artifact_store,
            )
        )
        service = epoch_runtime.SemanticEpochService(
            boundary_registry=boundary_registry,
            boundary_adapters={
                "l5_schema_regime": epoch_runtime.L5EpochBoundaryOwnerAdapter(
                    owner=l5_owner,
                    artifacts=artifact_store,
                ),
                "lex_amendment_window": epoch_runtime.LexEpochBoundaryOwnerAdapter(
                    owner=lex_store,
                    artifacts=artifact_store,
                ),
                "catalog_acquisition": (
                    epoch_runtime.CatalogAcquisitionEpochBoundaryOwnerAdapter(
                        owner=overlay,
                        artifacts=artifact_store,
                    )
                ),
            },
            facet_registry=facet_registry,
            facet_provider=epoch_runtime.ArtifactSemanticFacetProvider(
                artifacts=artifact_store,
                source_refs=facet_source_refs,
            ),
            history=history,
            artifact_store=artifact_store,
            qualification_consumer=(
                chronology_qualification.QualificationConsumer.from_unallocated_policy_authority()
            ),
            chronology_adapter=chronology_adapter,
        )
        try:
            return admit_acquisition_with_semantic_epoch(
                epoch_id=epoch_id,
                raw_evidence_ref=raw_evidence_ref,
                artifact_store=artifact_store,
                authority=authority,
                overlay=overlay,
                epoch_service=service,
                epoch_query=query,
                live_source_execution=live_source_execution,
            )
        except SemanticEpochAdmissionResolutionError:
            raise
        except ValueError as exc:
            raise SemanticEpochAdmissionResolutionError(
                "scope_unresolved",
                type(exc).__name__,
            ) from exc
    finally:
        if lex_store is not None:
            lex_store.close()


def revalidate_admission_passport(
    passport: AdmissionPassport,
    *,
    artifact_store: _ArtifactStore,
    authority: _CanonicalAuthority,
) -> AdmissionPassport:
    """Resolve decisive owners again immediately before overlay admission."""

    try:
        body = resolve_raw_response_body(passport.raw_evidence_ref)
    except Exception as exc:
        raise ValueError("raw_evidence_ref_unresolved") from exc
    if not passport.raw_evidence_verified:
        raise ValueError("raw_evidence_not_verified")
    if not _cas_bytes_match(
        artifact_store,
        artifact_id=passport.raw_artifact_id,
        expected=body,
    ):
        raise ValueError("raw_cas_evidence_unresolved")
    if not passport.cas_evidence_verified:
        raise ValueError("raw_cas_evidence_not_verified")
    if (
        passport.measured_profile.raw_evidence_event_sha256
        != passport.raw_evidence_ref.event_sha256
    ):
        raise ValueError("measured_profile_event_drift")
    scan = scan_secret_and_pii(
        body,
        scope="connector request/response payloads",
        artifact_ref_or_route=passport.raw_evidence_ref.event_sha256,
        redact=False,
        block_on_findings=True,
    )
    if tuple(sorted(scan.finding_kinds)) != passport.pii_scan.finding_kinds:
        raise ValueError("pii_scan_evidence_drift")
    try:
        resolved = ResolvedAcquisitionAuthority.model_validate(
            authority.resolve(passport.authority_entry_id)
        )
    except Exception as exc:
        raise ValueError("acquisition_authority_unresolved") from exc
    if (
        resolved.authority_provision_id != passport.authority_provision_id
        or resolved.authority_provision_content_sha256
        != passport.authority_provision_content_sha256
        or resolved.registry_content_sha256 != passport.authority_registry_content_sha256
        or resolved.baseline_content_sha256 != passport.baseline_content_sha256
        or resolved.upstream_catalog_projection_sha256
        != passport.upstream_catalog_projection_sha256
        or resolved.registration != passport.registration
        or resolved.field_binding != passport.field_binding
        or resolved.entry.source_lane != passport.source_lane
    ):
        raise ValueError("acquisition_authority_drift")
    if passport.source_lane == "live_fetch":
        if passport.live_source_execution is None:
            raise ValueError("live_source_execution_evidence_required")
        try:
            measurement_body = authority.resolve_live_source_body(
                passport.authority_entry_id,
                passport.live_source_execution,
                artifact_store,
            )
        except Exception as exc:
            raise ValueError("live_source_execution_unresolved") from exc
        source_authority_verified = True
    else:
        if passport.live_source_execution is not None:
            raise ValueError("local_lift_live_execution_evidence_forbidden")
        measurement_body = body
        source_authority_verified = authority.verify_source_body(
            passport.authority_entry_id,
            body,
        )
    measurement_sha = f"sha256:{hashlib.sha256(measurement_body).hexdigest()}"
    if passport.measured_profile.sample_content_sha256 != measurement_sha:
        raise ValueError("measured_profile_content_drift")
    raw_body_sha = f"sha256:{hashlib.sha256(body).hexdigest()}"
    if passport.source_watermark != raw_body_sha:
        raise ValueError("source_watermark_content_drift")
    if (
        resolved.license_id != passport.license_evidence.license_id
        or resolved.license_disposition.value != passport.license_evidence.disposition.value
        or resolved.license_authority_ref != passport.license_evidence.authority_ref
        or resolved.license_authority_content_sha256
        != passport.license_evidence.authority_content_sha256
    ):
        raise ValueError("license_authority_drift")
    l5_projection = (
        resolved.l5_trust.family_id,
        resolved.l5_trust.tier,
        resolved.l5_trust.trust_cap,
        resolved.l5_trust.trust_multiplier,
        resolved.l5_trust.authority_ref,
        resolved.l5_trust.owner_ref,
    )
    embedded_l5 = (
        passport.l5_trust.family_id,
        passport.l5_trust.tier,
        passport.l5_trust.trust_cap,
        passport.l5_trust.trust_multiplier,
        passport.l5_trust.authority_ref,
        passport.l5_trust.owner_ref,
    )
    if l5_projection != embedded_l5:
        raise ValueError("l5_trust_evidence_drift")
    request_event = resolve_linked_request_event(passport.raw_evidence_ref)
    request = request_event.get("request")
    if not isinstance(request, Mapping):
        raise ValueError("acquisition_request_contract_missing")
    schema_validation = _validate_request_and_measured_schema(
        request_event=request_event,
        request=request,
        measured_profile=passport.measured_profile,
        resolved=resolved,
    )
    if schema_validation != passport.schema_validation:
        raise ValueError("schema_validation_evidence_drift")
    if source_authority_verified != passport.source_authority_verified:
        raise ValueError("source_authority_evidence_drift")
    return AdmissionPassport.model_validate(passport.model_dump(mode="python"))


def persist_acquisition_quarantine(
    artifact_store: object,
    *,
    passport: AdmissionPassport,
    raw_payload: object,
) -> object:
    """Persist a refused passport through Fabric's existing quarantine owner."""

    validated = AdmissionPassport.model_validate(passport.model_dump(mode="python"))
    if validated.status is not AdmissionStatus.QUARANTINED:
        raise ValueError("only quarantined passports may enter the quarantine owner")
    reason = validated.rejection_codes[0] if validated.rejection_codes else "passport_quarantined"
    record = QuarantineRecord.new(
        reason=reason,
        severity="error",
        source="runtime.acquisition_executor",
        schema_version=validated.schema_version,
        downstream_impacts=("L1_admission_blocked",),
        context={
            "passport_id": validated.passport_id,
            "epoch_id": validated.epoch_id,
            "variable_id": validated.variable_id,
            "rejection_codes": list(validated.rejection_codes),
        },
    )
    return persist_quarantine_record(
        artifact_store,
        record=record,
        raw_payload=raw_payload,
        input_artifact_ids=(validated.raw_artifact_id,),
    )


def _validate_request_and_measured_schema(
    *,
    request_event: Mapping[str, object],
    request: Mapping[str, object],
    measured_profile: MeasuredSchemaProfile,
    resolved: object,
) -> SchemaValidationEvidence:
    authority = ResolvedAcquisitionAuthority.model_validate(resolved)
    entry = authority.entry
    drift: set[str] = set()
    expected_request = {
        "authority_entry_id": entry.entry_id,
        "authority_registry_content_sha256": authority.registry_content_sha256,
        "variable_id": entry.target_variable,
        "source_lane": entry.source_lane,
        "dataset_id": entry.landing_dataset_id,
        "distribution_id": entry.landing_distribution_id,
        "connector_id": authority.registration.connector_id,
        "profile_id": authority.registration.source_profile_id,
        "request_dataset_id": authority.registration.request_dataset_id,
    }
    for field, expected in expected_request.items():
        if request.get(field) != expected:
            drift.add(f"request_{field}_drift")
    declared_schema = request.get("schema_contract")
    expected_schema = entry.schema_projection()
    if declared_schema != expected_schema:
        drift.add("request_schema_contract_drift")
    declared_columns = {column.name: column for column in entry.schema_columns}
    measured_columns = {column.name: column for column in measured_profile.columns}
    for name in sorted(declared_columns.keys() - measured_columns.keys()):
        drift.add(f"declared_field_missing:{name}")
    for name in sorted(measured_columns.keys() - declared_columns.keys()):
        drift.add(f"unexpected_response_field:{name}")
    for name in sorted(declared_columns.keys() & measured_columns.keys()):
        declared = declared_columns[name]
        measured = measured_columns[name]
        if measured.logical_type not in declared.logical_types:
            drift.add(f"logical_type_drift:{name}")
        if measured.nullable and not declared.nullable:
            drift.add(f"nullability_drift:{name}")
    request_sha = content_sha256(request)
    if request_event.get("request_sha256") != request_sha:
        drift.add("request_content_hash_drift")
    schema_sha = content_sha256(expected_schema)
    return SchemaValidationEvidence(
        request_event_sha256=content_sha256(request_event),
        request_sha256=request_sha,
        schema_contract_ref=entry.schema_contract_ref,
        schema_contract_sha256=schema_sha,
        authority_entry_id=entry.entry_id,
        authority_registry_content_sha256=authority.registry_content_sha256,
        drift_codes=tuple(sorted(drift)),
        conformant=not drift,
    )


def _derive_rejection_codes(
    *,
    variable_id: str,
    observation_class: ObservationProvenanceClass,
    measured_profile: MeasuredSchemaProfile,
    field_binding: MetricFieldBinding,
    raw_evidence_verified: bool,
    cas_evidence_verified: bool,
    license_evidence: LicenseEvidence,
    pii_scan: PIIScanEvidence,
    source_watermark: str,
    dataset_version: str,
    l5_trust: L5TrustEvidence,
    schema_validation: SchemaValidationEvidence,
    source_authority_verified: bool,
) -> tuple[str, ...]:
    codes: set[str] = set()
    if not raw_evidence_verified:
        codes.add("raw_evidence_unresolved")
    if not cas_evidence_verified:
        codes.add("raw_cas_evidence_unresolved")
    if (
        measured_profile.inference_mode != "measured_quarantine"
        or measured_profile.sample_row_count <= 0
        or measured_profile.sample_content_sha256 is None
    ):
        codes.add("measured_profile_required")
    measured_fields = {column.name for column in measured_profile.columns}
    if field_binding.raw_field not in measured_fields:
        codes.add("raw_field_not_measured")
    if field_binding.dataset_id != measured_profile.dataset_id:
        codes.add("field_binding_dataset_mismatch")
    if field_binding.distribution_id != measured_profile.distribution_id:
        codes.add("field_binding_distribution_mismatch")
    if field_binding.canonical_variable != variable_id:
        codes.add("field_binding_canonical_variable_mismatch")
    if not field_binding.raw_unit or not field_binding.canonical_unit:
        codes.add("unit_evidence_missing")
    units_differ = field_binding.raw_unit != field_binding.canonical_unit
    if (
        units_differ and field_binding.unit_transform == "identity"
    ) or not field_binding.unit_transform_ref:
        codes.add("unit_transform_uncertified")
    if field_binding.calibrated_alignment_confidence < ALIGNMENT_ADMISSION_FLOOR:
        codes.add("alignment_confidence_below_owner_floor")
    if license_evidence.disposition is not LicenseDisposition.ADMISSIBLE_OPEN:
        codes.add("license_not_admissible")
    if pii_scan.blocked:
        codes.add("pii_scan_blocked")
    if not source_watermark.strip():
        codes.add("source_watermark_missing")
    if not dataset_version.strip():
        codes.add("dataset_version_missing")
    if not l5_trust.resolved or l5_trust.trust_cap <= 0.0:
        codes.add("l5_trust_unresolved")
    if not schema_validation.conformant:
        codes.update(f"schema:{code}" for code in schema_validation.drift_codes)
    if not source_authority_verified:
        codes.add("source_authority_unverified")
    codes.update(derive_observation_provenance_rejections(observation_class))
    if field_binding.is_proxy and observation_class is ObservationProvenanceClass.OBSERVED:
        codes.add("proxy_cannot_masquerade_as_observed")
    if observation_class is ObservationProvenanceClass.PROXY and not field_binding.is_proxy:
        codes.add("proxy_class_without_proxy_edge")
    if field_binding.is_proxy and field_binding.proxy_penalty <= 0.0:
        codes.add("proxy_penalty_missing")
    return tuple(sorted(codes))


def derive_observation_provenance_rejections(
    observation_class: ObservationProvenanceClass,
) -> tuple[str, ...]:
    """Derive fail-closed observed-overlay rejections from provenance class."""

    provenance = ObservationProvenanceClass(observation_class)
    if provenance is ObservationProvenanceClass.DERIVED:
        return ("derived_cannot_enter_observed_overlay",)
    if provenance is ObservationProvenanceClass.MODEL_OUTPUT:
        return ("model_output_not_observation",)
    return ()


def _derive_status(
    *,
    rejection_codes: Sequence[str],
    field_binding: MetricFieldBinding,
    observation_class: ObservationProvenanceClass,
    l5_trust: L5TrustEvidence,
    schema_validation: SchemaValidationEvidence,
    source_authority_verified: bool,
) -> AdmissionStatus:
    if rejection_codes or not schema_validation.conformant or not source_authority_verified:
        return AdmissionStatus.QUARANTINED
    if (
        field_binding.is_proxy
        or observation_class is ObservationProvenanceClass.PROXY
        or field_binding.calibrated_alignment_confidence < ALIGNMENT_DECISIVE_FLOOR
        or l5_trust.trust_cap < 1.0
        or l5_trust.trust_multiplier < 1.0
    ):
        return AdmissionStatus.ADMITTED_DEGRADED
    return AdmissionStatus.ADMITTED


def _cas_bytes_match(
    artifact_store: _ArtifactStore,
    *,
    artifact_id: str,
    expected: bytes,
) -> bool:
    try:
        parsed = ArtifactID.model_validate(artifact_id)
        return artifact_store.has(parsed) and artifact_store.get_bytes(parsed) == expected
    except Exception:
        return False


def _normalize_license(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def _logical_type(values: Sequence[object]) -> str:
    kinds: set[str] = set()
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            kinds.add("boolean")
        elif isinstance(value, int):
            kinds.add("integer")
        elif isinstance(value, float):
            kinds.add("number")
        elif isinstance(value, str):
            kinds.add("string")
        elif isinstance(value, Mapping):
            kinds.add("object")
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            kinds.add("array")
        else:
            kinds.add(type(value).__name__)
    if not kinds:
        return "null"
    if kinds <= {"integer", "number"}:
        return "number" if "number" in kinds else "integer"
    return next(iter(kinds)) if len(kinds) == 1 else "mixed[" + ",".join(sorted(kinds)) + "]"


def _json_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item) for item in value]
    return value


__all__ = [
    "ALIGNMENT_ADMISSION_FLOOR",
    "ALIGNMENT_DECISIVE_FLOOR",
    "PASSPORT_SCHEMA_VERSION",
    "ActivatedSemanticEpochAdmissionReceipt",
    "AdmissionPassport",
    "AdmissionStatus",
    "L5TrustEvidence",
    "LicenseDisposition",
    "MeasuredColumn",
    "MeasuredSchemaProfile",
    "ObservationProvenanceClass",
    "PIIScanEvidence",
    "SemanticEpochAdmissionResolutionError",
    "admit_acquisition_with_production_semantic_epoch",
    "admit_acquisition_with_semantic_epoch",
    "build_admission_passport",
    "build_metadata_schema_profile",
    "derive_observation_provenance_rejections",
    "measure_quarantined_sample",
    "persist_acquisition_quarantine",
    "revalidate_admission_passport",
]
