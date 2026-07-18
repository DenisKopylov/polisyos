"""Fail-closed admission kernel for local-lift and live acquisition evidence.

This module is data-plane only.  It measures quarantined owner bytes, resolves
license/L5/CAS/journal evidence, derives a passport, and leaves persistence to
the catalog overlay and existing Fabric quarantine owners.  It does not build,
mutate, or simulate a policy world.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, scan_secret_and_pii
from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.fabric import data_plane as fabric_data_plane

ArtifactID = artifacts.ArtifactID
JournalEventRef = fabric_data_plane.JournalEventRef
MetricFieldBinding = data_forge_read_api.catalog.MetricFieldBinding
ObservationProvenanceClass = data_forge_read_api.catalog.ObservationProvenanceClass
AcquisitionDatasetRegistration = data_forge_read_api.catalog.AcquisitionDatasetRegistration
ResolvedAcquisitionAuthority = data_forge_read_api.catalog.ResolvedAcquisitionAuthority
LiveSourceExecutionEvidence = data_forge_read_api.catalog.LiveSourceExecutionEvidence
content_sha256 = fabric_data_plane.content_sha256
resolve_linked_request_event = fabric_data_plane.resolve_linked_request_event
resolve_raw_response_body = fabric_data_plane.resolve_raw_response_body
QuarantineRecord = fabric_data_plane.QuarantineRecord
persist_quarantine_record = fabric_data_plane.persist_quarantine_record

PASSPORT_SCHEMA_VERSION = "polisyos.runtime.acquisition_admission_passport.v1"
ALIGNMENT_ADMISSION_FLOOR = 0.55
ALIGNMENT_DECISIVE_FLOOR = 0.8
_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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

    scope: Literal["connector request/response payloads"] = (
        "connector request/response payloads"
    )
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


class _ArtifactStore(Protocol):
    def has(self, artifact_id: ArtifactID) -> bool: ...

    def get_bytes(self, artifact_id: ArtifactID) -> bytes: ...


class _CanonicalAuthority(Protocol):
    def resolve(self, entry_id: str) -> object: ...

    def verify_source_body(self, entry_id: str, body: bytes) -> bool: ...

    def resolve_live_source_body(
        self,
        entry_id: str,
        evidence: object,
        artifact_store: object,
    ) -> bytes: ...


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


def build_admission_passport(
    *,
    epoch_id: int,
    raw_evidence_ref: JournalEventRef,
    artifact_store: _ArtifactStore,
    raw_artifact_id: str,
    authority: _CanonicalAuthority,
    live_source_execution: LiveSourceExecutionEvidence | None = None,
) -> AdmissionPassport:
    """Resolve canonical owners and derive a measured admission passport."""

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
    detector_version = (
        scan.reports[0].detector_version if scan.reports else "owner_scan_unresolved"
    )
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
        "authority_provision_content_sha256": (
            resolved.authority_provision_content_sha256
        ),
        "authority_registry_content_sha256": resolved.registry_content_sha256,
        "upstream_catalog_projection_sha256": (
            resolved.upstream_catalog_projection_sha256
        ),
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
    identity_payload = {
        key: _json_value(value)
        for key, value in values.items()
    }
    return AdmissionPassport(
        passport_id="passport:" + content_sha256(identity_payload),
        **values,
        status=status,
        rejection_codes=rejection_codes,
    )


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
        or resolved.registry_content_sha256
        != passport.authority_registry_content_sha256
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
        or resolved.license_disposition.value
        != passport.license_evidence.disposition.value
        or resolved.license_authority_ref
        != passport.license_evidence.authority_ref
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
        (units_differ and field_binding.unit_transform == "identity")
        or not field_binding.unit_transform_ref
    ):
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
    if observation_class is ObservationProvenanceClass.DERIVED:
        codes.add("derived_cannot_enter_observed_overlay")
    if observation_class is ObservationProvenanceClass.MODEL_OUTPUT:
        codes.add("model_output_not_observation")
    if field_binding.is_proxy and observation_class is ObservationProvenanceClass.OBSERVED:
        codes.add("proxy_cannot_masquerade_as_observed")
    if observation_class is ObservationProvenanceClass.PROXY and not field_binding.is_proxy:
        codes.add("proxy_class_without_proxy_edge")
    if field_binding.is_proxy and field_binding.proxy_penalty <= 0.0:
        codes.add("proxy_penalty_missing")
    return tuple(sorted(codes))


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
    "AdmissionPassport",
    "AdmissionStatus",
    "L5TrustEvidence",
    "LicenseDisposition",
    "MeasuredColumn",
    "MeasuredSchemaProfile",
    "ObservationProvenanceClass",
    "PIIScanEvidence",
    "build_admission_passport",
    "build_metadata_schema_profile",
    "measure_quarantined_sample",
    "persist_acquisition_quarantine",
    "revalidate_admission_passport",
]
