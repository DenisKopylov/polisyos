"""Immutable acquisition epochs layered over the read-only L1 catalog.

The production catalog is epoch zero and is never opened for writing here.
Admitted rows are persisted in a separate DuckDB file with passport and epoch
provenance.  Read attachment is owned separately so quarantine rows cannot
become visible merely by existing in CAS or in this module's inputs.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Protocol, Self

import duckdb
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core import artifacts, canon, contracts, scan_secret_and_pii
from polisyos.fabric import data_plane as fabric_data_plane

ArtifactID = artifacts.ArtifactID
ArtifactRef = artifacts.ArtifactRef
from_canonical_bytes = canon.from_canonical_bytes
epoch_contract = contracts.epoch
JournalEventRef = fabric_data_plane.JournalEventRef
content_sha256 = fabric_data_plane.content_sha256
resolve_raw_response_body = fabric_data_plane.resolve_raw_response_body
resolve_linked_request_event = fabric_data_plane.resolve_linked_request_event

OVERLAY_SCHEMA_VERSION = "polisyos.data_forge.acquisition_overlay.v2"
_LEGACY_OVERLAY_SCHEMA_VERSION = "polisyos.data_forge.acquisition_overlay.v1"
_PASSPORT_SCHEMA_VERSION = "polisyos.runtime.acquisition_admission_passport.v2"
_LEGACY_PASSPORT_SCHEMA_VERSION = "polisyos.runtime.acquisition_admission_passport.v1"
DEFAULT_ACQUISITION_OVERLAY_PATH = Path(
    "architecture/policy_design_case/layer3_gy_acquisition_overlay.duckdb"
)
_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_BASELINE_UNION_TABLES = (
    "ds_datasets",
    "ds_distributions",
    "ds_metric_bindings",
    "ds_observations",
    "ds_schema_profiles",
    "ds_variable_alignments",
)
_OBSERVATION_DECISIVE_COLUMNS = frozenset(
    {
        "observation_id",
        "dataset_id",
        "raw_variable",
        "canonical_var",
        "country_code",
        "value",
    }
)
_OVERLAY_AUDIT_TABLES = (
    "acquisition_overlay_metadata",
    "acquisition_epochs",
    "acquisition_passports",
    "acquisition_registrations",
    "acquisition_observation_provenance",
    "ds_metric_field_bindings",
    "acquisition_epoch_members",
    "acquisition_semantic_receipts",
)
_ACQUISITION_EPOCH_COLUMNS = (
    ("epoch_id", "BIGINT", "NO"),
    ("passport_id", "VARCHAR", "NO"),
    ("admission_content_sha256", "VARCHAR", "NO"),
    ("baseline_content_sha256", "VARCHAR", "NO"),
    ("admitted_observation_count", "BIGINT", "NO"),
    ("observation_class", "VARCHAR", "NO"),
    ("semantic_epoch_ref", "VARCHAR", "YES"),
    ("semantic_epoch_stamp_sha256", "VARCHAR", "YES"),
    ("semantic_epoch_stamp_json", "JSON", "YES"),
    ("prepared_semantic_epoch_ref", "JSON", "YES"),
    ("pending_overlay_receipt_ref", "JSON", "YES"),
    ("admitted_boundary_evidence_ref", "JSON", "YES"),
    ("semantic_epoch_production_receipt_ref", "JSON", "YES"),
    ("activated_overlay_receipt_ref", "JSON", "YES"),
    ("epoch_activation_state", "VARCHAR", "NO"),
)
_EPOCH_MEMBER_COLUMNS = (
    ("table_name", "VARCHAR", "NO"),
    ("canonical_primary_key_bytes", "BLOB", "NO"),
    ("canonical_primary_key_hash", "VARCHAR", "NO"),
    ("epoch_id", "BIGINT", "NO"),
    ("passport_id", "VARCHAR", "NO"),
)
_EPOCH_MEMBER_UNIQUE = (
    "table_name",
    "canonical_primary_key_hash",
    "epoch_id",
)
_EPOCH_STATE_PREDICATE = """
(
    epoch_activation_state = 'legacy_not_established'
    AND semantic_epoch_ref IS NULL
    AND semantic_epoch_stamp_sha256 IS NULL
    AND semantic_epoch_stamp_json IS NULL
    AND prepared_semantic_epoch_ref IS NULL
    AND pending_overlay_receipt_ref IS NULL
    AND admitted_boundary_evidence_ref IS NULL
    AND semantic_epoch_production_receipt_ref IS NULL
    AND activated_overlay_receipt_ref IS NULL
) OR (
    epoch_activation_state = 'pending_epoch_activation'
    AND semantic_epoch_ref IS NOT NULL
    AND semantic_epoch_stamp_sha256 IS NOT NULL
    AND semantic_epoch_stamp_json IS NOT NULL
    AND prepared_semantic_epoch_ref IS NOT NULL
    AND pending_overlay_receipt_ref IS NOT NULL
    AND semantic_epoch_production_receipt_ref IS NULL
    AND activated_overlay_receipt_ref IS NULL
) OR (
    epoch_activation_state = 'active'
    AND semantic_epoch_ref IS NOT NULL
    AND semantic_epoch_stamp_sha256 IS NOT NULL
    AND semantic_epoch_stamp_json IS NOT NULL
    AND prepared_semantic_epoch_ref IS NOT NULL
    AND pending_overlay_receipt_ref IS NOT NULL
    AND admitted_boundary_evidence_ref IS NOT NULL
    AND semantic_epoch_production_receipt_ref IS NOT NULL
    AND activated_overlay_receipt_ref IS NOT NULL
)
"""


class BaselineMutationError(RuntimeError):
    """Raised when immutable epoch-zero bytes no longer match their identity."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


class OverlayAdmissionError(RuntimeError):
    """Raised when a passport or row cannot enter the observed overlay."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {detail or code}")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ObservationProvenanceClass(StrEnum):
    """Authority-bearing distinction between observed, proxy, and derived values."""

    OBSERVED = "observed"
    PROXY = "proxy"
    DERIVED = "derived"
    MODEL_OUTPUT = "model_output"


class BaselineIdentity(_StrictModel):
    """Content identity of the immutable epoch-zero production catalog."""

    source_path: str = Field(min_length=1)
    content_sha256: str = Field(pattern=_SHA256_PATTERN)
    byte_size: int = Field(gt=0)
    epoch: Literal[0] = 0


class CatalogAcquisitionEpochProjection(_StrictModel):
    """Read-only metadata for one persisted acquisition epoch."""

    epoch_id: int
    passport_id: str
    admitted_observation_count: int
    epoch_activation_state: str
    semantic_epoch_ref: str | None = None


class CatalogAcquisitionPassportProjection(_StrictModel):
    """Narrow metadata projection of one content-bound admission passport."""

    schema_version: Literal[
        "polisyos.runtime.acquisition_admission_passport.v1",
        "polisyos.runtime.acquisition_admission_passport.v2",
    ]
    passport_id: str = Field(pattern=r"^passport:sha256:[0-9a-f]{64}$")
    epoch_id: int = Field(gt=0)
    variable_id: str = Field(min_length=1)
    source_lane: Literal["local_lift", "live_fetch"]
    observation_class: ObservationProvenanceClass
    status: Literal["admitted", "admitted_degraded", "quarantined"]
    rejection_codes: tuple[str, ...]


class CatalogAcquisitionEventProjection(_StrictModel):
    """Content-bound event metadata without its persisted statement payload."""

    receipt_ref: str = Field(pattern=_SHA256_PATTERN)
    receipt_kind: str = Field(min_length=1)
    receipt_content_hash: str = Field(pattern=_SHA256_PATTERN)


class CatalogAcquisitionStateProjection(_StrictModel):
    """Validated metadata-only projection of overlay/passport/event state."""

    schema_version: str = "polisyos.data_forge.acquisition_state_projection.v1"
    baseline: BaselineIdentity
    overlay_ref: str | None
    overlay_exists: bool
    epoch_count: int
    passport_count: int
    pending_epoch_count: int
    active_epoch_count: int
    admitted_observation_count: int
    semantic_receipt_count: int
    registration_count: int
    epochs: tuple[CatalogAcquisitionEpochProjection, ...]
    passports: tuple[CatalogAcquisitionPassportProjection, ...]
    events: tuple[CatalogAcquisitionEventProjection, ...]


class MetricFieldBinding(_StrictModel):
    """Measured distribution-field edge into one canonical variable."""

    binding_id: str = Field(pattern=r"^field-binding:sha256:[0-9a-f]{64}$")
    dataset_id: str = Field(min_length=1)
    distribution_id: str = Field(min_length=1)
    raw_field: str = Field(min_length=1)
    canonical_variable: str = Field(min_length=1)
    raw_unit: str
    canonical_unit: str
    unit_transform: str = Field(min_length=1)
    unit_transform_ref: str | None = None
    alignment_method: Literal["exact", "semantic", "meta_analytic"]
    alignment_confidence: float = Field(ge=0.0, le=1.0)
    calibrated_alignment_confidence: float = Field(ge=0.0, le=1.0)
    is_proxy: bool
    proxy_penalty: float = Field(ge=0.0, le=1.0)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    aggregation_method: Literal["identity", "mean", "sum", "last"] = "identity"
    valid_min: float | None = None
    valid_max: float | None = None

    @model_validator(mode="after")
    def _edge_is_owner_calibrated(self) -> Self:
        from polisyos.data_forge.domains.catalog.knowledge.variable_alignment import (
            AlignmentMethod,
            VariableAlignment,
            calibrate_alignment_confidence,
        )

        alignment = VariableAlignment(
            canonical_var=self.canonical_variable,
            dataset_var=self.raw_field,
            dataset_id=self.dataset_id,
            method=AlignmentMethod(self.alignment_method),
            confidence=self.alignment_confidence,
            evidence=";".join(self.evidence_refs),
            is_proxy=self.is_proxy,
            proxy_penalty=self.proxy_penalty,
        )
        expected_confidence = calibrate_alignment_confidence(alignment)
        if abs(self.calibrated_alignment_confidence - expected_confidence) > 1e-9:
            raise ValueError("calibrated alignment confidence must come from its owner")
        if self.alignment_method == "exact" and (
            self.raw_field != self.canonical_variable or abs(self.alignment_confidence - 1.0) > 1e-9
        ):
            raise ValueError("exact alignment requires identical variables and full confidence")
        if not self.is_proxy and self.proxy_penalty != 0.0:
            raise ValueError("non-proxy field bindings cannot carry a proxy penalty")
        if (
            self.valid_min is not None
            and self.valid_max is not None
            and self.valid_min > self.valid_max
        ):
            raise ValueError("field-binding valid range is inverted")
        expected_id = "field-binding:" + content_sha256(self.identity_payload())
        if self.binding_id != expected_id:
            raise ValueError("field-binding identity must be recomputed")
        return self

    def identity_payload(self) -> dict[str, object]:
        """Return the projection that defines this last-mile edge."""

        return {
            key: value for key, value in self.model_dump(mode="json").items() if key != "binding_id"
        }


class AcquisitionDatasetRegistration(_StrictModel):
    """Generic dataset/distribution/binding rows created by an admitted epoch."""

    catalog_dataset_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    agency: str = Field(min_length=1)
    request_dataset_id: str = Field(min_length=1)
    distribution_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    source_profile_id: str = Field(min_length=1)
    source_locator: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    metric_id: str = Field(min_length=1)
    execution_tier: Literal["fetchable", "transport_ready"]
    access_license: str = Field(min_length=1)
    country_codes: tuple[str, ...] = Field(min_length=1)
    temporal_start: str | None = None
    temporal_end: str | None = None
    field_binding: MetricFieldBinding

    @model_validator(mode="after")
    def _registration_edges_match(self) -> Self:
        if self.catalog_dataset_id != self.field_binding.dataset_id:
            raise ValueError("registration dataset must equal the field-binding dataset")
        if self.distribution_id != self.field_binding.distribution_id:
            raise ValueError("registration distribution must equal the field-binding distribution")
        if self.metric_id != self.field_binding.canonical_variable:
            raise ValueError("registration metric must equal the canonical field-binding variable")
        return self


class _LegacyAdmissionPassport(_StrictModel):
    """Strict private decoder for the historical v1 passport surface.

    A valid v1 row remains unresolved because it has no semantic stamp.  This
    decoder distinguishes that bounded historical case from arbitrary JSON
    carrying only the old schema marker.
    """

    schema_version: Literal["polisyos.runtime.acquisition_admission_passport.v1"]
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
    measured_profile: dict[str, object]
    field_binding: MetricFieldBinding
    raw_evidence_ref: JournalEventRef
    raw_evidence_verified: bool
    raw_artifact_id: str = Field(pattern=_SHA256_PATTERN)
    cas_evidence_verified: bool
    license_evidence: dict[str, object]
    pii_scan: dict[str, object]
    source_watermark: str
    dataset_version: str
    l5_trust: dict[str, object]
    schema_validation: dict[str, object]
    live_source_execution: dict[str, object] | None = None
    source_authority_verified: bool
    status: Literal["admitted", "admitted_degraded", "quarantined"]
    rejection_codes: tuple[str, ...]

    @model_validator(mode="after")
    def _legacy_surface_is_content_bound(self) -> Self:
        if (self.source_lane == "live_fetch") != (self.live_source_execution is not None):
            raise ValueError("legacy live-source evidence shape differs")
        if self.field_binding != self.registration.field_binding:
            raise ValueError("legacy field binding differs from registration")
        identity = {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key not in {"passport_id", "status", "rejection_codes"}
        }
        if self.passport_id != "passport:" + content_sha256(identity):
            raise ValueError("legacy passport identity is not recomputed")
        return self


class CanonicalAcquisitionObservation(_StrictModel):
    """One admitted overlay row plus its non-baseline provenance class."""

    observation_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    raw_variable: str = Field(min_length=1)
    canonical_var: str = Field(min_length=1)
    country_code: str = Field(min_length=1)
    year: int | None = None
    survey_year: int | None = None
    wave: int | None = None
    value: float
    condition_json: str = "{}"
    acquisition_method: str = Field(min_length=1)
    source_watermark: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    observation_class: ObservationProvenanceClass

    @field_validator("value")
    @classmethod
    def _value_is_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("acquired observation value must be finite")
        return value

    @model_validator(mode="after")
    def _time_and_condition_are_typed(self) -> Self:
        if self.year is None and self.survey_year is None and self.wave is None:
            raise ValueError("acquired observations require an owner time coordinate")
        try:
            parsed = json.loads(self.condition_json)
        except json.JSONDecodeError as exc:
            raise ValueError("condition_json must be valid JSON") from exc
        if not isinstance(parsed, Mapping):
            raise ValueError("condition_json must encode a mapping")
        return self


class OverlayAdmissionReceipt(epoch_contract.ActivatedOverlayAdmissionStatement):
    """Durable active statement plus call-local replay metadata."""

    receipt_ref: ArtifactRef
    receipt_content_hash: str = Field(pattern=_SHA256_PATTERN)
    replayed: bool


class PendingOverlayAdmissionReceipt(epoch_contract.PendingOverlayAdmissionStatement):
    """Durable hidden-admission statement plus call-local replay metadata."""

    receipt_ref: ArtifactRef
    receipt_content_hash: str = Field(pattern=_SHA256_PATTERN)
    replayed: bool


class _ArtifactStore(Protocol):
    def has(self, artifact_id: ArtifactID) -> bool: ...

    def get_bytes(self, artifact_id: ArtifactID) -> bytes: ...

    def get_manifest(self, artifact_id: ArtifactID) -> object: ...

    def verify(self, artifact_id: ArtifactID) -> object: ...

    def put_bytes(self, data: bytes, opts: object) -> ArtifactRef: ...


class _CanonicalAuthority(Protocol):
    def resolve(self, entry_id: str) -> object: ...

    def verify_source_body(self, entry_id: str, body: bytes) -> bool: ...

    def resolve_live_source_body(
        self,
        entry_id: str,
        evidence: object,
        artifact_store: object,
    ) -> bytes: ...


class _Passport(Protocol):
    epoch_id: int
    passport_id: str
    status: object
    observation_class: object
    variable_id: str
    source_lane: str
    authority_entry_id: str
    authority_registry_content_sha256: str
    upstream_catalog_projection_sha256: str
    baseline_content_sha256: str
    registration: AcquisitionDatasetRegistration
    field_binding: MetricFieldBinding
    raw_evidence_ref: JournalEventRef
    raw_evidence_verified: bool
    raw_artifact_id: str
    cas_evidence_verified: bool
    measured_profile: object
    pii_scan: object
    license_evidence: object
    l5_trust: object
    source_watermark: str
    dataset_version: str
    rejection_codes: tuple[str, ...]
    schema_validation: object
    live_source_execution: object | None
    source_authority_verified: bool
    semantic_boundary_candidate_ref: ArtifactRef
    semantic_boundary_candidate_content_hash: str
    semantic_epoch_stamp: epoch_contract.SemanticEpochStamp
    prepared_semantic_epoch_ref: ArtifactRef

    def recomputed_passport_id(self) -> str: ...

    def recomputed_rejection_codes(self) -> tuple[str, ...]: ...

    def model_dump(self, *, mode: str) -> dict[str, Any]: ...


class _PreparedSemanticEpoch(Protocol):
    prepared_epoch_ref: ArtifactRef
    prepared_content_hash: str
    query: object
    stamp: epoch_contract.SemanticEpochStamp
    boundary_candidate_refs: tuple[ArtifactRef, ...]
    status: object

    def model_dump(self, *, mode: str) -> dict[str, Any]: ...


class _SemanticEpochProductionReceipt(Protocol):
    receipt_ref: ArtifactRef
    receipt_content_hash: str
    status: object
    epoch_ref: str | None
    semantic_manifest_ref: ArtifactRef | None
    prepared_epoch_ref: ArtifactRef | None
    requested_query_context_ref: str


def _overlay_statement_payload(value: BaseModel | dict[str, object]) -> bytes:
    mapping = _model_json(value) if isinstance(value, BaseModel) else value
    canonical = fabric_data_plane.canonical_json_bytes(mapping)
    return len(canonical).to_bytes(8, "big") + canonical


def _overlay_statement_content_hash(value: BaseModel | dict[str, object]) -> str:
    mapping = _model_json(value) if isinstance(value, BaseModel) else value
    return content_sha256(mapping)


def _persist_external_statement(
    *, artifact_store: _ArtifactStore, value: BaseModel | dict[str, object], kind: str
) -> tuple[ArtifactRef, str]:
    payload = _overlay_statement_payload(value)
    ref = artifact_store.put_bytes(
        payload,
        artifacts.PutOptions(
            kind=kind,
            media_type="application/vnd.polisyos.epoch+json",
        ),
    )
    report = artifact_store.verify(ref.artifact_id)
    manifest = artifact_store.get_manifest(ref.artifact_id)
    readback = artifact_store.get_bytes(ref.artifact_id)
    if (
        not bool(getattr(report, "ok", False))
        or readback != payload
        or str(ref.artifact_id) != f"sha256:{hashlib.sha256(payload).hexdigest()}"
        or getattr(manifest, "artifact_id", None) != ref.artifact_id
        or getattr(manifest, "kind", None) != kind
        or getattr(manifest, "media_type", None) != "application/vnd.polisyos.epoch+json"
    ):
        raise OverlayAdmissionError("semantic_external_receipt_readback_failed", kind)
    return ref, _overlay_statement_content_hash(value)


def _persist_epoch_statement(
    *,
    artifact_store: _ArtifactStore,
    value: BaseModel | dict[str, object],
    kind: str,
    domain: str,
) -> tuple[ArtifactRef, str]:
    """Copy one owner-canonical epoch statement into CAS and read it back."""

    canonical = epoch_contract.canonical_epoch_bytes(value)
    payload = len(canonical).to_bytes(8, "big") + canonical
    ref = artifact_store.put_bytes(
        payload,
        artifacts.PutOptions(
            kind=kind,
            media_type="application/vnd.polisyos.epoch+json",
        ),
    )
    report = artifact_store.verify(ref.artifact_id)
    manifest = artifact_store.get_manifest(ref.artifact_id)
    if (
        not bool(getattr(report, "ok", False))
        or artifact_store.get_bytes(ref.artifact_id) != payload
        or getattr(manifest, "artifact_id", None) != ref.artifact_id
        or getattr(manifest, "kind", None) != kind
        or getattr(manifest, "media_type", None) != "application/vnd.polisyos.epoch+json"
    ):
        raise OverlayAdmissionError("semantic_external_receipt_readback_failed", kind)
    return ref, _semantic_content_hash(domain=domain, value=value)


def _store_external_statement_record(
    con: duckdb.DuckDBPyConnection,
    *,
    ref: ArtifactRef,
    kind: str,
    content_hash: str,
    value: BaseModel | dict[str, object],
) -> None:
    """Persist the exact float-admitting external statement bytes in owner storage."""

    payload = _overlay_statement_payload(value)
    mapping = _model_json(value) if isinstance(value, BaseModel) else value
    if (
        str(ref.artifact_id) != f"sha256:{hashlib.sha256(payload).hexdigest()}"
        or ref.kind != kind
        or ref.media_type != "application/vnd.polisyos.epoch+json"
    ):
        raise OverlayAdmissionError("semantic_record_ref_content_mismatch", kind)
    existing = con.execute(
        "SELECT receipt_kind, receipt_content_hash, receipt_json "
        "FROM acquisition_semantic_receipts WHERE receipt_ref = ?",
        [str(ref.artifact_id)],
    ).fetchone()
    expected = (kind, content_hash, mapping)
    if existing is not None:
        observed = (str(existing[0]), str(existing[1]), json.loads(str(existing[2])))
        if observed != expected:
            raise OverlayAdmissionError("semantic_record_identity_conflict", kind)
        return
    con.execute(
        "INSERT INTO acquisition_semantic_receipts VALUES (?, ?, ?, ?)",
        [str(ref.artifact_id), kind, content_hash, json.dumps(mapping)],
    )


def _load_external_statement_record(
    con: duckdb.DuckDBPyConnection,
    *,
    ref: ArtifactRef,
    expected_kind: str,
) -> tuple[dict[str, object], str]:
    row = con.execute(
        "SELECT receipt_kind, receipt_content_hash, receipt_json "
        "FROM acquisition_semantic_receipts WHERE receipt_ref = ?",
        [str(ref.artifact_id)],
    ).fetchone()
    if row is None or str(row[0]) != expected_kind:
        raise OverlayAdmissionError("semantic_owner_receipt_missing", expected_kind)
    mapping = json.loads(str(row[2]))
    if not isinstance(mapping, dict):
        raise OverlayAdmissionError("semantic_owner_receipt_not_mapping", expected_kind)
    if (
        str(ref.artifact_id)
        != f"sha256:{hashlib.sha256(_overlay_statement_payload(mapping)).hexdigest()}"
    ):
        raise OverlayAdmissionError("semantic_owner_receipt_ref_drift", expected_kind)
    return mapping, str(row[1])


def _persist_external_owner_record(
    con: duckdb.DuckDBPyConnection,
    *,
    kind: str,
    value: dict[str, object],
) -> tuple[ArtifactRef, str]:
    payload = _overlay_statement_payload(value)
    ref = _artifact_ref_for_payload(payload=payload, kind=kind)
    content_hash = _overlay_statement_content_hash(value)
    _store_external_statement_record(
        con,
        ref=ref,
        kind=kind,
        content_hash=content_hash,
        value=value,
    )
    return ref, content_hash


def _load_external_statement(
    *,
    artifact_store: _ArtifactStore,
    ref: ArtifactRef,
    expected_kind: str,
) -> dict[str, object]:
    if ref.kind != expected_kind or ref.media_type != "application/vnd.polisyos.epoch+json":
        raise OverlayAdmissionError("semantic_external_receipt_profile_mismatch")
    report = artifact_store.verify(ref.artifact_id)
    manifest = artifact_store.get_manifest(ref.artifact_id)
    payload = artifact_store.get_bytes(ref.artifact_id)
    if (
        not bool(getattr(report, "ok", False))
        or str(ref.artifact_id) != f"sha256:{hashlib.sha256(payload).hexdigest()}"
        or getattr(manifest, "artifact_id", None) != ref.artifact_id
        or getattr(manifest, "kind", None) != expected_kind
        or getattr(manifest, "media_type", None) != "application/vnd.polisyos.epoch+json"
    ):
        raise OverlayAdmissionError("semantic_external_receipt_readback_failed")
    return _single_framed_json(payload)


def _single_framed_json(payload: bytes) -> dict[str, object]:
    if len(payload) < 8:
        raise OverlayAdmissionError("semantic_receipt_frame_truncated")
    size = int.from_bytes(payload[:8], "big")
    if size != len(payload) - 8:
        raise OverlayAdmissionError("semantic_receipt_frame_denominator_mismatch")
    try:
        value = json.loads(payload[8:])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OverlayAdmissionError("semantic_receipt_json_invalid") from exc
    if not isinstance(value, dict):
        raise OverlayAdmissionError("semantic_receipt_not_mapping")
    return value


def _artifact_ref_for_payload(*, payload: bytes, kind: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID(f"sha256:{hashlib.sha256(payload).hexdigest()}"),
        kind=kind,
        media_type="application/vnd.polisyos.epoch+json",
    )


def _semantic_content_hash(*, domain: str, value: BaseModel | dict[str, object]) -> str:
    canonical = epoch_contract.canonical_epoch_bytes(value)
    digest = hashlib.sha256()
    digest.update(domain.encode())
    digest.update(b"\0")
    digest.update(canonical)
    return f"sha256:{digest.hexdigest()}"


def _store_semantic_record(
    con: duckdb.DuckDBPyConnection,
    *,
    ref: ArtifactRef,
    kind: str,
    content_hash: str,
    value: BaseModel | dict[str, object],
    media_type: str = "application/vnd.polisyos.epoch+json",
) -> None:
    """Persist one independently content-bound JSON record in owner storage."""

    canonical = epoch_contract.canonical_epoch_bytes(value)
    framed = len(canonical).to_bytes(8, "big") + canonical
    if (
        str(ref.artifact_id) != f"sha256:{hashlib.sha256(framed).hexdigest()}"
        or ref.kind != kind
        or ref.media_type != media_type
    ):
        raise OverlayAdmissionError("semantic_record_ref_content_mismatch", kind)
    payload = canonical.decode("utf-8")
    existing = con.execute(
        "SELECT receipt_kind, receipt_content_hash, receipt_json "
        "FROM acquisition_semantic_receipts WHERE receipt_ref = ?",
        [str(ref.artifact_id)],
    ).fetchone()
    expected = (kind, content_hash, json.loads(payload))
    if existing is not None:
        observed = (str(existing[0]), str(existing[1]), json.loads(str(existing[2])))
        if observed != expected:
            raise OverlayAdmissionError("semantic_record_identity_conflict", kind)
        return
    con.execute(
        "INSERT INTO acquisition_semantic_receipts VALUES (?, ?, ?, ?)",
        [str(ref.artifact_id), kind, content_hash, payload],
    )


def _persist_owner_record(
    con: duckdb.DuckDBPyConnection,
    *,
    kind: str,
    domain: str,
    value: BaseModel | dict[str, object],
) -> tuple[ArtifactRef, str]:
    canonical = epoch_contract.canonical_epoch_bytes(value)
    framed = len(canonical).to_bytes(8, "big") + canonical
    ref = _artifact_ref_for_payload(payload=framed, kind=kind)
    content_hash = _semantic_content_hash(domain=domain, value=value)
    _store_semantic_record(
        con,
        ref=ref,
        kind=kind,
        content_hash=content_hash,
        value=value,
    )
    return ref, content_hash


def _load_owner_record(
    con: duckdb.DuckDBPyConnection,
    *,
    ref: ArtifactRef,
    expected_kind: str,
) -> tuple[dict[str, object], str]:
    row = con.execute(
        "SELECT receipt_kind, receipt_content_hash, receipt_json "
        "FROM acquisition_semantic_receipts WHERE receipt_ref = ?",
        [str(ref.artifact_id)],
    ).fetchone()
    if row is None or str(row[0]) != expected_kind:
        raise OverlayAdmissionError("semantic_owner_receipt_missing", expected_kind)
    stored = json.loads(str(row[2]))
    if not isinstance(stored, dict):
        raise OverlayAdmissionError("semantic_owner_receipt_not_mapping", expected_kind)
    canonical = epoch_contract.canonical_epoch_bytes(stored)
    framed = len(canonical).to_bytes(8, "big") + canonical
    if str(ref.artifact_id) != f"sha256:{hashlib.sha256(framed).hexdigest()}":
        raise OverlayAdmissionError("semantic_owner_receipt_ref_drift", expected_kind)
    value = from_canonical_bytes(canonical)
    if not isinstance(value, dict):
        raise OverlayAdmissionError("semantic_owner_receipt_not_mapping", expected_kind)
    return value, str(row[1])


class CatalogAcquisitionOverlay:
    """Epoch transaction owner over a separate DuckDB acquisition overlay."""

    def __init__(self, baseline_path: Path, overlay_path: Path) -> None:
        self.baseline_path = Path(baseline_path)
        self.overlay_path = Path(overlay_path)
        if self.baseline_path.resolve() == self.overlay_path.resolve():
            raise BaselineMutationError(
                "overlay_path_equals_baseline",
                self.baseline_path.as_posix(),
            )
        self._baseline_identity = _baseline_identity(self.baseline_path)
        self._initialized = False

    def initialize(self) -> BaselineIdentity:
        """Create empty mirror tables while attaching epoch zero read-only."""

        self._require_baseline_unchanged()
        self.overlay_path.parent.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(str(self.overlay_path))
        try:
            _attach_read_only(con, self.baseline_path, alias="baseline")
            baseline_tables = {
                str(row[0]) for row in con.execute("show tables from baseline").fetchall()
            }
            missing = sorted(set(_BASELINE_UNION_TABLES) - baseline_tables)
            if missing:
                raise OverlayAdmissionError(
                    "baseline_catalog_contract_incomplete",
                    ",".join(missing),
                )
            con.execute("BEGIN TRANSACTION")
            for table in _BASELINE_UNION_TABLES:
                statement = (
                    f"CREATE TABLE IF NOT EXISTS {table} "  # noqa: S608
                    f"AS SELECT * FROM baseline.{table} WHERE FALSE"
                )
                con.execute(statement)
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS acquisition_overlay_metadata (
                    schema_version VARCHAR PRIMARY KEY,
                    baseline_content_sha256 VARCHAR NOT NULL,
                    baseline_byte_size BIGINT NOT NULL
                )
                """
            )
            con.execute(
                f"""
                CREATE TABLE IF NOT EXISTS acquisition_epochs (
                    epoch_id BIGINT PRIMARY KEY,
                    passport_id VARCHAR NOT NULL,
                    admission_content_sha256 VARCHAR NOT NULL,
                    baseline_content_sha256 VARCHAR NOT NULL,
                    admitted_observation_count BIGINT NOT NULL,
                    observation_class VARCHAR NOT NULL,
                    semantic_epoch_ref VARCHAR,
                    semantic_epoch_stamp_sha256 VARCHAR,
                    semantic_epoch_stamp_json JSON,
                    prepared_semantic_epoch_ref JSON,
                    pending_overlay_receipt_ref JSON,
                    admitted_boundary_evidence_ref JSON,
                    semantic_epoch_production_receipt_ref JSON,
                    activated_overlay_receipt_ref JSON,
                    epoch_activation_state VARCHAR NOT NULL,
                    CONSTRAINT acquisition_epoch_semantic_state_check
                    CHECK ({_EPOCH_STATE_PREDICATE})
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS acquisition_passports (
                    passport_id VARCHAR PRIMARY KEY,
                    epoch_id BIGINT NOT NULL,
                    passport_content_sha256 VARCHAR NOT NULL,
                    passport_json JSON NOT NULL
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS acquisition_epoch_members (
                    table_name VARCHAR NOT NULL,
                    canonical_primary_key_bytes BLOB NOT NULL,
                    canonical_primary_key_hash VARCHAR NOT NULL,
                    epoch_id BIGINT NOT NULL,
                    passport_id VARCHAR NOT NULL,
                    UNIQUE(table_name, canonical_primary_key_hash, epoch_id)
                )
                """
            )
            current_database = con.execute("SELECT current_database()").fetchone()
            if current_database is None:
                raise OverlayAdmissionError("overlay_database_identity_not_established")
            _require_epoch_member_contract(
                con,
                database_name=str(current_database[0]),
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS acquisition_semantic_receipts (
                    receipt_ref VARCHAR PRIMARY KEY,
                    receipt_kind VARCHAR NOT NULL,
                    receipt_content_hash VARCHAR NOT NULL,
                    receipt_json JSON NOT NULL
                )
                """
            )
            _migrate_epoch_table_v2(con)
            _derive_baseline_primary_key_spec(con)
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS acquisition_registrations (
                    catalog_dataset_id VARCHAR PRIMARY KEY,
                    registration_content_sha256 VARCHAR NOT NULL,
                    registration_json JSON NOT NULL
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS acquisition_observation_provenance (
                    observation_id VARCHAR PRIMARY KEY,
                    epoch_id BIGINT NOT NULL,
                    passport_id VARCHAR NOT NULL,
                    observation_class VARCHAR NOT NULL,
                    raw_evidence_event_sha256 VARCHAR NOT NULL,
                    raw_artifact_id VARCHAR NOT NULL,
                    l5_trust_tier VARCHAR NOT NULL,
                    effective_authority_score DOUBLE NOT NULL
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS ds_metric_field_bindings (
                    binding_id VARCHAR PRIMARY KEY,
                    epoch_id BIGINT NOT NULL,
                    dataset_id VARCHAR NOT NULL,
                    distribution_id VARCHAR NOT NULL,
                    raw_field VARCHAR NOT NULL,
                    canonical_variable VARCHAR NOT NULL,
                    raw_unit VARCHAR NOT NULL,
                    canonical_unit VARCHAR NOT NULL,
                    unit_transform VARCHAR NOT NULL,
                    unit_transform_ref VARCHAR,
                    alignment_method VARCHAR NOT NULL,
                    alignment_confidence DOUBLE NOT NULL,
                    calibrated_alignment_confidence DOUBLE NOT NULL,
                    is_proxy BOOLEAN NOT NULL,
                    proxy_penalty DOUBLE NOT NULL,
                    aggregation_method VARCHAR NOT NULL,
                    evidence_refs JSON NOT NULL,
                    passport_id VARCHAR NOT NULL,
                    effective_authority_score DOUBLE NOT NULL
                )
                """
            )
            rows = con.execute(
                "SELECT schema_version, baseline_content_sha256, baseline_byte_size "
                "FROM acquisition_overlay_metadata"
            ).fetchall()
            if not rows:
                con.execute(
                    "INSERT INTO acquisition_overlay_metadata VALUES (?, ?, ?)",
                    [
                        OVERLAY_SCHEMA_VERSION,
                        self._baseline_identity.content_sha256,
                        self._baseline_identity.byte_size,
                    ],
                )
            elif any(
                tuple(row[1:])
                != (
                    self._baseline_identity.content_sha256,
                    self._baseline_identity.byte_size,
                )
                for row in rows
            ):
                raise BaselineMutationError(
                    "overlay_baseline_identity_mismatch",
                    self.overlay_path.as_posix(),
                )
            else:
                con.execute(
                    "DELETE FROM acquisition_overlay_metadata WHERE schema_version = ?",
                    [_LEGACY_OVERLAY_SCHEMA_VERSION],
                )
                existing_v2 = con.execute(
                    "SELECT 1 FROM acquisition_overlay_metadata WHERE schema_version = ?",
                    [OVERLAY_SCHEMA_VERSION],
                ).fetchone()
                if existing_v2 is None:
                    con.execute(
                        "INSERT INTO acquisition_overlay_metadata VALUES (?, ?, ?)",
                        [
                            OVERLAY_SCHEMA_VERSION,
                            self._baseline_identity.content_sha256,
                            self._baseline_identity.byte_size,
                        ],
                    )
            con.execute("COMMIT")
            con.execute("DETACH baseline")
        finally:
            con.close()
        self._require_baseline_unchanged()
        self._initialized = True
        return self._baseline_identity

    def admit_epoch(
        self,
        *,
        passport: _Passport,
        prepared_epoch: _PreparedSemanticEpoch,
        boundary_candidate: epoch_contract.AcquisitionSemanticBoundaryCandidate,
        artifact_store: _ArtifactStore,
        authority: _CanonicalAuthority,
    ) -> PendingOverlayAdmissionReceipt:
        """Revalidate owners and commit one hidden pending native admission."""

        if not self._initialized:
            raise OverlayAdmissionError("overlay_not_initialized")
        before = self._require_baseline_unchanged()
        try:
            candidate_mapping = epoch_contract.load_verified_epoch_statement(
                store=artifact_store,
                ref=boundary_candidate.candidate_ref,
                expected_kind="epoch.acquisition_semantic_boundary_candidate",
            )
            persisted_candidate = (
                epoch_contract.AcquisitionSemanticBoundaryCandidateStatement.model_validate(
                    candidate_mapping
                )
            )
            prepared_mapping = epoch_contract.load_verified_epoch_statement(
                store=artifact_store,
                ref=prepared_epoch.prepared_epoch_ref,
                expected_kind="epoch.prepared",
            )
        except ValueError as exc:
            raise OverlayAdmissionError("prepared_epoch_candidate_cas_readback_failed") from exc
        expected_prepared = {
            name: value
            for name, value in prepared_epoch.model_dump(mode="python").items()
            if name not in {"prepared_epoch_ref", "prepared_content_hash"}
        }
        if (
            _enum_value(prepared_epoch.status) != "prepared"
            or persisted_candidate != boundary_candidate.statement
            or epoch_contract.canonical_epoch_bytes(prepared_mapping)
            != epoch_contract.canonical_epoch_bytes(expected_prepared)
            or prepared_epoch.prepared_content_hash
            != epoch_contract.epoch_semantic_content_hash(
                domain="polisyos.epoch.prepared.v1",
                value=expected_prepared,
            )
            or prepared_epoch.prepared_epoch_ref != passport.prepared_semantic_epoch_ref
            or prepared_epoch.stamp != passport.semantic_epoch_stamp
            or boundary_candidate.candidate_ref != passport.semantic_boundary_candidate_ref
            or boundary_candidate.candidate_content_hash
            != passport.semantic_boundary_candidate_content_hash
            or boundary_candidate.candidate_ref not in prepared_epoch.boundary_candidate_refs
        ):
            raise OverlayAdmissionError("prepared_epoch_candidate_binding_mismatch")
        statement = boundary_candidate.statement
        stamp = passport.semantic_epoch_stamp
        live_source = getattr(passport, "live_source_execution", None)
        expected_source_artifact_id = (
            str(passport.raw_artifact_id)
            if live_source is None
            else str(getattr(live_source, "normalized_data_artifact_id", ""))
        )
        if (
            statement.requested_query_context_ref != stamp.requested_query_context_ref
            or statement.authority_purpose != stamp.authority_purpose
            or str(statement.source_record_ref.artifact_id) != expected_source_artifact_id
        ):
            raise OverlayAdmissionError("semantic_candidate_query_context_mismatch")
        source_body = _validate_passport_owner_evidence(
            passport,
            artifact_store=artifact_store,
            authority=authority,
        )
        registration = passport.registration
        epoch_id = int(passport.epoch_id)
        if epoch_id <= 0:
            raise OverlayAdmissionError("epoch_stamp_required")
        passport_id = str(passport.passport_id)
        status = _enum_value(passport.status)
        if status not in {"admitted", "admitted_degraded"}:
            raise OverlayAdmissionError("passport_not_admitted", status)
        observation_class = ObservationProvenanceClass(_enum_value(passport.observation_class))
        if observation_class in {
            ObservationProvenanceClass.DERIVED,
            ObservationProvenanceClass.MODEL_OUTPUT,
        }:
            raise OverlayAdmissionError(
                "non_observed_provenance_class",
                observation_class.value,
            )
        passport_binding = passport.field_binding
        if passport_binding != registration.field_binding:
            raise OverlayAdmissionError("registration_field_binding_drift")
        if registration.metric_id != str(passport.variable_id):
            raise OverlayAdmissionError("registration_variable_drift")
        rows = derive_canonical_observations(
            source_body,
            passport=passport,
            registration=registration,
        )
        _validate_observations(
            rows,
            passport=passport,
            registration=registration,
            observation_class=observation_class,
        )
        admission_projection = {
            "schema_version": OVERLAY_SCHEMA_VERSION,
            "epoch_id": epoch_id,
            "passport": _model_json(passport),
            "registration": registration.model_dump(mode="json"),
            "observations": [row.model_dump(mode="json") for row in rows],
            "semantic_boundary_candidate_ref": boundary_candidate.candidate_ref.model_dump(
                mode="json"
            ),
            "semantic_epoch_stamp": stamp.model_dump(mode="json"),
            "prepared_semantic_epoch_ref": prepared_epoch.prepared_epoch_ref.model_dump(
                mode="json"
            ),
        }
        admission_hash = content_sha256(admission_projection)
        effective_authority_score = _effective_authority_score(passport)
        existing = _existing_epoch(self.overlay_path, epoch_id)
        if existing is not None:
            if existing[0] != admission_hash:
                raise OverlayAdmissionError("epoch_content_conflict", str(epoch_id))
            if existing[2] is None:
                raise OverlayAdmissionError("pending_overlay_receipt_not_established")
            pending_ref = ArtifactRef.model_validate(json.loads(str(existing[2])))
            pending_mapping = _load_external_statement(
                artifact_store=artifact_store,
                ref=pending_ref,
                expected_kind="epoch.pending_overlay_admission_receipt",
            )
            pending_statement = epoch_contract.PendingOverlayAdmissionStatement.model_validate(
                pending_mapping
            )
            member_keys, member_hash = _existing_member_denominator(
                self.overlay_path,
                epoch_id=epoch_id,
                passport_id=passport_id,
            )
            if (
                pending_statement.native_member_keys != member_keys
                or pending_statement.native_member_denominator_hash != member_hash
            ):
                raise OverlayAdmissionError("pending_epoch_receipt_binding_mismatch")
            con = duckdb.connect(str(self.overlay_path), read_only=True)
            try:
                owner_mapping, owner_hash = _load_external_statement_record(
                    con,
                    ref=pending_ref,
                    expected_kind="epoch.pending_overlay_admission_receipt",
                )
            finally:
                con.close()
            if owner_mapping != pending_mapping or owner_hash != _overlay_statement_content_hash(
                pending_mapping
            ):
                raise OverlayAdmissionError("pending_overlay_owner_copy_drift")
            return PendingOverlayAdmissionReceipt(
                **pending_mapping,
                receipt_ref=pending_ref,
                receipt_content_hash=owner_hash,
                replayed=True,
            )

        con = duckdb.connect(str(self.overlay_path))
        try:
            _attach_read_only(con, self.baseline_path, alias="baseline")
            con.execute("BEGIN TRANSACTION")
            _insert_registration(con, registration, passport)
            _insert_observations(
                con,
                rows,
                epoch_id=epoch_id,
                passport=passport,
            )
            passport_json = _model_json(passport)
            con.execute(
                "INSERT INTO acquisition_passports VALUES (?, ?, ?, ?)",
                [passport_id, epoch_id, content_sha256(passport_json), json.dumps(passport_json)],
            )
            _store_semantic_record(
                con,
                ref=boundary_candidate.candidate_ref,
                kind="epoch.acquisition_semantic_boundary_candidate",
                content_hash=boundary_candidate.candidate_content_hash,
                value=boundary_candidate.statement,
            )
            member_keys, member_hash = _insert_epoch_members(
                con,
                epoch_id=epoch_id,
                passport_id=passport_id,
                registration=registration,
                observations=rows,
            )
            pending_statement = epoch_contract.PendingOverlayAdmissionStatement(
                epoch_id=epoch_id,
                passport_id=passport_id,
                admission_content_sha256=admission_hash,
                admitted_observation_count=len(rows),
                observation_class=observation_class.value,
                effective_authority_score=effective_authority_score,
                baseline_before_sha256=before.content_sha256,
                baseline_after_sha256=before.content_sha256,
                semantic_epoch_stamp=stamp,
                prepared_semantic_epoch_ref=prepared_epoch.prepared_epoch_ref,
                boundary_candidate_ref=boundary_candidate.candidate_ref,
                native_member_keys=member_keys,
                native_member_denominator_hash=member_hash,
                native_member_count=len(member_keys),
                activation_state="pending_epoch_activation",
            )
            pending_ref, pending_hash = _persist_external_statement(
                artifact_store=artifact_store,
                value=pending_statement,
                kind="epoch.pending_overlay_admission_receipt",
            )
            _store_external_statement_record(
                con,
                ref=pending_ref,
                kind="epoch.pending_overlay_admission_receipt",
                content_hash=pending_hash,
                value=pending_statement,
            )
            con.execute(
                """
                INSERT INTO acquisition_epochs (
                    epoch_id, passport_id, admission_content_sha256,
                    baseline_content_sha256, admitted_observation_count,
                    observation_class, semantic_epoch_ref,
                    semantic_epoch_stamp_sha256, semantic_epoch_stamp_json,
                    prepared_semantic_epoch_ref,
                    pending_overlay_receipt_ref,
                    admitted_boundary_evidence_ref,
                    semantic_epoch_production_receipt_ref,
                    epoch_activation_state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    epoch_id,
                    passport_id,
                    admission_hash,
                    before.content_sha256,
                    len(rows),
                    observation_class.value,
                    stamp.epoch_ref,
                    epoch_contract.semantic_epoch_stamp_content_hash(stamp),
                    json.dumps(stamp.model_dump(mode="json")),
                    json.dumps(prepared_epoch.prepared_epoch_ref.model_dump(mode="json")),
                    json.dumps(pending_ref.model_dump(mode="json")),
                    None,
                    None,
                    "pending_epoch_activation",
                ],
            )
            # Recheck while the transaction can still roll back.  A concurrent
            # epoch-zero mutation must never leave partially admitted overlay
            # rows behind merely because it occurred after the entry fence.
            self._require_baseline_unchanged()
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        self._require_baseline_unchanged()
        return PendingOverlayAdmissionReceipt(
            **pending_statement.model_dump(mode="python"),
            receipt_ref=pending_ref,
            receipt_content_hash=pending_hash,
            replayed=False,
        )

    def activate_semantic_epoch(
        self,
        *,
        pending_receipt: PendingOverlayAdmissionReceipt,
        production_receipt: _SemanticEpochProductionReceipt,
        artifact_store: _ArtifactStore,
    ) -> OverlayAdmissionReceipt:
        """Expose one pending native admission after exact epoch proof readback."""

        if _enum_value(production_receipt.status) not in {"appended", "no_change"}:
            raise OverlayAdmissionError("semantic_epoch_production_not_positive")
        production_ref = production_receipt.receipt_ref
        if not artifact_store.has(production_ref.artifact_id):
            raise OverlayAdmissionError("semantic_epoch_production_receipt_missing")
        production_report = artifact_store.verify(production_ref.artifact_id)
        production_manifest = artifact_store.get_manifest(production_ref.artifact_id)
        production_raw = artifact_store.get_bytes(production_ref.artifact_id)
        if (
            not production_report.ok
            or production_manifest.artifact_id != production_ref.artifact_id
            or production_manifest.kind != production_ref.kind
            or production_manifest.media_type != production_ref.media_type
            or production_ref.kind != "epoch.production_receipt"
            or production_ref.media_type != "application/vnd.polisyos.epoch-production-receipt+json"
            or f"sha256:{hashlib.sha256(production_raw).hexdigest()}"
            != str(production_ref.artifact_id)
        ):
            raise OverlayAdmissionError("semantic_epoch_production_receipt_drift")
        persisted = _single_framed_json(production_raw)
        expected = {
            name: _model_json_value(getattr(production_receipt, name))
            for name in (
                "production_mode",
                "status",
                "prepared_epoch_ref",
                "admitted_boundary_evidence_ref",
                "epoch_ref",
                "semantic_manifest_ref",
                "owner_denominator_receipt_refs",
                "history_append_receipt_ref",
                "chronology_bundle_ref",
                "chronology_verification_ref",
                "requested_query_context_ref",
                "failure_codes",
            )
        }
        if persisted != expected:
            raise OverlayAdmissionError("semantic_epoch_production_receipt_drift")
        if production_receipt.receipt_content_hash != _semantic_content_hash(
            domain="polisyos.epoch.production-receipt.v1",
            value=expected,
        ):
            raise OverlayAdmissionError("semantic_epoch_production_content_hash_drift")
        if (
            production_receipt.epoch_ref != pending_receipt.semantic_epoch_stamp.epoch_ref
            or production_receipt.prepared_epoch_ref != pending_receipt.prepared_semantic_epoch_ref
            or production_receipt.requested_query_context_ref
            != pending_receipt.semantic_epoch_stamp.requested_query_context_ref
            or production_receipt.admitted_boundary_evidence_ref is None
        ):
            raise OverlayAdmissionError("semantic_epoch_production_binding_mismatch")
        after = self._require_baseline_unchanged()
        activated_statement = epoch_contract.ActivatedOverlayAdmissionStatement(
            epoch_id=pending_receipt.epoch_id,
            passport_id=pending_receipt.passport_id,
            admission_content_sha256=pending_receipt.admission_content_sha256,
            admitted_observation_count=pending_receipt.admitted_observation_count,
            observation_class=pending_receipt.observation_class,
            effective_authority_score=pending_receipt.effective_authority_score,
            baseline_before_sha256=pending_receipt.baseline_before_sha256,
            baseline_after_sha256=after.content_sha256,
            semantic_epoch_stamp=pending_receipt.semantic_epoch_stamp,
            prepared_semantic_epoch_ref=pending_receipt.prepared_semantic_epoch_ref,
            pending_overlay_receipt_ref=pending_receipt.receipt_ref,
            admitted_boundary_evidence_ref=(production_receipt.admitted_boundary_evidence_ref),
            semantic_epoch_production_receipt_ref=production_ref,
            activation_state="active",
        )
        activated_ref, activated_hash = _persist_external_statement(
            artifact_store=artifact_store,
            value=activated_statement,
            kind="epoch.activated_overlay_admission_receipt",
        )
        con = duckdb.connect(str(self.overlay_path))
        try:
            con.execute("BEGIN TRANSACTION")
            _attach_read_only(con, self.baseline_path, alias="baseline")
            key_spec = _derive_baseline_primary_key_spec(con)
            _store_semantic_record(
                con,
                ref=production_ref,
                kind="epoch.production_receipt",
                content_hash=production_receipt.receipt_content_hash,
                value=persisted,
                media_type="application/vnd.polisyos.epoch-production-receipt+json",
            )
            current = con.execute(
                """
                SELECT epoch_activation_state, pending_overlay_receipt_ref,
                       admitted_boundary_evidence_ref,
                       semantic_epoch_production_receipt_ref,
                       activated_overlay_receipt_ref,
                       admission_content_sha256, admitted_observation_count,
                       observation_class, baseline_content_sha256,
                       semantic_epoch_stamp_sha256, semantic_epoch_stamp_json,
                       prepared_semantic_epoch_ref
                FROM acquisition_epochs
                WHERE epoch_id = ? AND passport_id = ?
                """,
                [pending_receipt.epoch_id, pending_receipt.passport_id],
            ).fetchone()
            if current is None:
                raise OverlayAdmissionError("pending_epoch_not_found")
            member_rows = con.execute(
                """
                SELECT table_name, canonical_primary_key_bytes,
                       canonical_primary_key_hash
                FROM acquisition_epoch_members
                WHERE epoch_id = ? AND passport_id = ?
                ORDER BY table_name, canonical_primary_key_hash
                """,
                [pending_receipt.epoch_id, pending_receipt.passport_id],
            ).fetchall()
            _reconcile_physical_epoch_members(
                con,
                member_rows=member_rows,
                key_spec=key_spec,
            )
            normalized_members = tuple((str(row[0]), str(row[2])) for row in member_rows)
            member_raw = epoch_contract.canonical_epoch_bytes(
                {
                    "epoch_id": pending_receipt.epoch_id,
                    "passport_id": pending_receipt.passport_id,
                    "members": normalized_members,
                }
            )
            member_hash = f"sha256:{hashlib.sha256(member_raw).hexdigest()}"
            stored_stamp = json.loads(str(current[10]))
            stored_prepared = json.loads(str(current[11]))
            if (
                current[1] is None
                or json.loads(str(current[1]))
                != pending_receipt.receipt_ref.model_dump(mode="json")
                or current[2] is None
                or json.loads(str(current[2]))
                != production_receipt.admitted_boundary_evidence_ref.model_dump(mode="json")
                or str(current[5]) != pending_receipt.admission_content_sha256
                or int(current[6]) != pending_receipt.admitted_observation_count
                or str(current[7]) != _enum_value(pending_receipt.observation_class)
                or str(current[8]) != pending_receipt.baseline_before_sha256
                or str(current[9])
                != epoch_contract.semantic_epoch_stamp_content_hash(
                    pending_receipt.semantic_epoch_stamp
                )
                or stored_stamp != pending_receipt.semantic_epoch_stamp.model_dump(mode="json")
                or stored_prepared
                != pending_receipt.prepared_semantic_epoch_ref.model_dump(mode="json")
                or len(normalized_members) != pending_receipt.native_member_count
                or member_hash != pending_receipt.native_member_denominator_hash
            ):
                raise OverlayAdmissionError("pending_epoch_receipt_binding_mismatch")
            if str(current[0]) == "active":
                if current[3] is None or json.loads(str(current[3])) != production_ref.model_dump(
                    mode="json"
                ):
                    raise OverlayAdmissionError("active_epoch_production_receipt_conflict")
                if current[4] is None or json.loads(str(current[4])) != activated_ref.model_dump(
                    mode="json"
                ):
                    raise OverlayAdmissionError("active_epoch_receipt_conflict")
                replayed = True
            elif str(current[0]) != "pending_epoch_activation":
                raise OverlayAdmissionError("epoch_activation_state_not_pending")
            else:
                if current[3] is not None or current[4] is not None:
                    raise OverlayAdmissionError("pending_epoch_phase_ref_conflict")
                con.execute(
                    """
                    UPDATE acquisition_epochs
                    SET semantic_epoch_production_receipt_ref = ?,
                        activated_overlay_receipt_ref = ?,
                        epoch_activation_state = 'active'
                    WHERE epoch_id = ? AND passport_id = ?
                    """,
                    [
                        json.dumps(production_ref.model_dump(mode="json")),
                        json.dumps(activated_ref.model_dump(mode="json")),
                        pending_receipt.epoch_id,
                        pending_receipt.passport_id,
                    ],
                )
                replayed = False
            _store_external_statement_record(
                con,
                ref=activated_ref,
                kind="epoch.activated_overlay_admission_receipt",
                content_hash=activated_hash,
                value=activated_statement,
            )
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        self._require_baseline_unchanged()
        return OverlayAdmissionReceipt(
            **activated_statement.model_dump(mode="python"),
            receipt_ref=activated_ref,
            receipt_content_hash=activated_hash,
            replayed=replayed,
        )

    def resolve_native_membership(
        self,
        *,
        query: epoch_contract.AcquisitionBoundaryResolutionQuery,
        candidate: epoch_contract.AcquisitionSemanticBoundaryCandidate | None = None,
    ) -> epoch_contract.AcquisitionNativeMembershipReceipt:
        """Enumerate every owner-native acquisition row before query projection."""

        if not self._initialized:
            raise OverlayAdmissionError("overlay_not_initialized")
        self._require_baseline_unchanged()
        con = duckdb.connect(str(self.overlay_path))
        try:
            con.execute("BEGIN TRANSACTION")
            _attach_read_only(con, self.baseline_path, alias="baseline")
            key_spec = _derive_baseline_primary_key_spec(con)
            rows = con.execute(
                """
                WITH native_keys AS (
                    SELECT epoch_id, passport_id FROM acquisition_epochs
                    UNION
                    SELECT epoch_id, passport_id FROM acquisition_passports
                    UNION
                    SELECT epoch_id, passport_id FROM acquisition_epoch_members
                )
                SELECT k.epoch_id, k.passport_id,
                       e.admission_content_sha256,
                       e.baseline_content_sha256, e.admitted_observation_count,
                       e.observation_class, e.semantic_epoch_ref,
                       e.semantic_epoch_stamp_sha256, e.semantic_epoch_stamp_json,
                       e.prepared_semantic_epoch_ref,
                       e.semantic_epoch_production_receipt_ref,
                       e.epoch_activation_state, p.passport_content_sha256,
                       p.passport_json, e.epoch_id IS NOT NULL,
                       p.passport_id IS NOT NULL
                FROM native_keys AS k
                LEFT JOIN acquisition_epochs AS e
                  ON e.epoch_id = k.epoch_id AND e.passport_id = k.passport_id
                LEFT JOIN acquisition_passports AS p
                  ON p.epoch_id = k.epoch_id AND p.passport_id = k.passport_id
                ORDER BY k.epoch_id, k.passport_id
                """
            ).fetchall()
            source_rows: list[dict[str, object]] = []
            assessments: list[epoch_contract.AcquisitionNativeMemberAssessment] = []
            for row in rows:
                epoch_id = int(row[0])
                passport_id = str(row[1])
                member_rows = con.execute(
                    """
                    SELECT table_name, canonical_primary_key_bytes,
                           canonical_primary_key_hash
                    FROM acquisition_epoch_members
                    WHERE epoch_id = ? AND passport_id = ?
                    ORDER BY table_name, canonical_primary_key_hash
                    """,
                    [epoch_id, passport_id],
                ).fetchall()
                activation_state = "" if row[11] is None else str(row[11])
                epoch_present = bool(row[14])
                passport_present = bool(row[15])
                if member_rows or activation_state != "legacy_not_established":
                    _reconcile_physical_epoch_members(
                        con,
                        member_rows=member_rows,
                        key_spec=key_spec,
                    )
                observed_passport_hash = None if row[12] is None else str(row[12])
                observed_passport_json = None if row[13] is None else str(row[13])
                passport_mapping: dict[str, object] | None = None
                if observed_passport_json is not None:
                    try:
                        decoded_passport = json.loads(observed_passport_json)
                    except (TypeError, json.JSONDecodeError):
                        pass
                    else:
                        if isinstance(decoded_passport, dict):
                            passport_mapping = decoded_passport
                passport_ref: ArtifactRef | None = None
                passport_hash: str | None = None
                semantic_ref: ArtifactRef | None = None
                semantic_hash: str | None = None
                binding_status: Literal["bound", "legacy_unresolved", "invalid"]
                query_disposition: Literal["applicable", "not_applicable", "unresolved"]
                failure_code: str | None
                if passport_mapping is not None and observed_passport_hash != content_sha256(
                    passport_mapping
                ):
                    passport_mapping = None
                if passport_mapping is not None:
                    passport_ref, passport_hash = _persist_external_owner_record(
                        con,
                        kind="epoch.acquisition_passport_snapshot",
                        value=passport_mapping,
                    )
                if not epoch_present or not passport_present or passport_mapping is None:
                    binding_status = "invalid"
                    query_disposition = "unresolved"
                    failure_code = "acquisition_candidate_binding_mismatch"
                else:
                    passport_version = passport_mapping.get("schema_version")
                    raw_ref = passport_mapping.get("semantic_boundary_candidate_ref")
                    raw_hash = passport_mapping.get("semantic_boundary_candidate_content_hash")
                    semantic_fields = (
                        "semantic_boundary_candidate_ref",
                        "semantic_boundary_candidate_content_hash",
                        "semantic_epoch_ref",
                        "semantic_epoch_stamp_sha256",
                        "semantic_epoch_stamp",
                        "prepared_semantic_epoch_ref",
                    )
                    has_any_semantic_field = any(
                        field in passport_mapping for field in semantic_fields
                    )
                    has_every_semantic_field = all(
                        field in passport_mapping for field in semantic_fields
                    )
                    if (
                        passport_version == _LEGACY_PASSPORT_SCHEMA_VERSION
                        and not has_any_semantic_field
                    ):
                        try:
                            _LegacyAdmissionPassport.model_validate(passport_mapping)
                        except ValueError:
                            binding_status = "invalid"
                            query_disposition = "unresolved"
                            failure_code = "acquisition_candidate_binding_mismatch"
                        else:
                            table_has_semantic_carrier = any(
                                value is not None for value in row[6:10]
                            )
                            if (
                                table_has_semantic_carrier
                                or str(row[11]) != "legacy_not_established"
                            ):
                                binding_status = "invalid"
                                query_disposition = "unresolved"
                                failure_code = "acquisition_candidate_binding_mismatch"
                            else:
                                binding_status = "legacy_unresolved"
                                query_disposition = "unresolved"
                                failure_code = (
                                    "legacy_acquisition_candidate_identity_not_established"
                                )
                    elif (
                        passport_version != _PASSPORT_SCHEMA_VERSION
                        or not has_every_semantic_field
                        or raw_ref is None
                        or raw_hash is None
                    ):
                        binding_status = "invalid"
                        query_disposition = "unresolved"
                        failure_code = "acquisition_candidate_binding_mismatch"
                    else:
                        try:
                            stamp = epoch_contract.SemanticEpochStamp.model_validate(
                                passport_mapping["semantic_epoch_stamp"]
                            )
                            prepared_ref = ArtifactRef.model_validate(
                                passport_mapping["prepared_semantic_epoch_ref"]
                            )
                            if (
                                passport_mapping["semantic_epoch_ref"] != stamp.epoch_ref
                                or passport_mapping["semantic_epoch_stamp_sha256"]
                                != epoch_contract.semantic_epoch_stamp_content_hash(stamp)
                                or prepared_ref.kind != "epoch.prepared"
                                or prepared_ref.media_type != "application/vnd.polisyos.epoch+json"
                                or row[6] is None
                                or str(row[6]) != stamp.epoch_ref
                                or row[7] is None
                                or str(row[7])
                                != epoch_contract.semantic_epoch_stamp_content_hash(stamp)
                                or row[8] is None
                                or json.loads(str(row[8])) != stamp.model_dump(mode="json")
                                or row[9] is None
                                or json.loads(str(row[9])) != prepared_ref.model_dump(mode="json")
                                or str(row[11])
                                not in {
                                    "pending_epoch_activation",
                                    "active",
                                }
                            ):
                                raise ValueError("persisted v2 passport semantic binding differs")
                            semantic_ref = ArtifactRef.model_validate(raw_ref)
                            semantic_hash = str(raw_hash)
                            statement_mapping, stored_hash = _load_owner_record(
                                con,
                                ref=semantic_ref,
                                expected_kind=("epoch.acquisition_semantic_boundary_candidate"),
                            )
                            statement_model = (
                                epoch_contract.AcquisitionSemanticBoundaryCandidateStatement
                            )
                            statement = statement_model.model_validate(statement_mapping)
                            bound = epoch_contract.AcquisitionSemanticBoundaryCandidate(
                                candidate_ref=semantic_ref,
                                candidate_content_hash=semantic_hash,
                                statement=statement,
                            )
                            if stored_hash != bound.candidate_content_hash:
                                raise ValueError("candidate semantic hash changed")
                        except (TypeError, ValueError, OverlayAdmissionError):
                            binding_status = "invalid"
                            query_disposition = "unresolved"
                            failure_code = "acquisition_candidate_binding_mismatch"
                        else:
                            binding_status = "bound"
                            if (
                                statement.scope_identity_ref != query.scope_identity_ref
                                or statement.authority_purpose != query.authority_purpose
                            ):
                                query_disposition = "not_applicable"
                                failure_code = None
                            elif (
                                statement.valid_effect_coordinate_ref
                                != query.valid_effect_coordinate_ref
                                or statement.visibility_knowledge_cutoff_ref
                                != query.visibility_knowledge_cutoff_ref
                                or statement.purpose_admission_cutoff_ref
                                != query.purpose_admission_cutoff_ref
                                or statement.requested_query_context_ref
                                != query.requested_query_context_ref
                            ):
                                query_disposition = "unresolved"
                                failure_code = "acquisition_query_context_mismatch"
                            else:
                                query_disposition = "applicable"
                                failure_code = None
                native_mapping: dict[str, object] = {
                    "epoch_id": epoch_id,
                    "passport_id": passport_id,
                    "admission_content_sha256": (None if row[2] is None else str(row[2])),
                    "baseline_content_sha256": (None if row[3] is None else str(row[3])),
                    "admitted_observation_count": (None if row[4] is None else int(row[4])),
                    "observation_class": (None if row[5] is None else str(row[5])),
                    "semantic_epoch_ref": None if row[6] is None else str(row[6]),
                    "semantic_epoch_stamp_sha256": (None if row[7] is None else str(row[7])),
                    "semantic_epoch_stamp": (None if row[8] is None else json.loads(str(row[8]))),
                    "prepared_semantic_epoch_ref": (
                        None if row[9] is None else json.loads(str(row[9]))
                    ),
                    "semantic_epoch_production_receipt_ref": (
                        None if row[10] is None else json.loads(str(row[10]))
                    ),
                    "epoch_activation_state": (None if row[11] is None else str(row[11])),
                    "epoch_row_present": epoch_present,
                    "passport_row_present": passport_present,
                    "observed_passport_content_hash": observed_passport_hash,
                    "observed_passport_json": observed_passport_json,
                    "passport_ref": (
                        None if passport_ref is None else passport_ref.model_dump(mode="json")
                    ),
                    "passport_content_hash": passport_hash,
                    "members": [
                        {
                            "table_name": str(table),
                            "canonical_primary_key_bytes": bytes(key_bytes).hex(),
                            "canonical_primary_key_hash": str(key_hash),
                        }
                        for table, key_bytes, key_hash in member_rows
                    ],
                }
                source_rows.append(native_mapping)
                native_ref, native_hash = _persist_owner_record(
                    con,
                    kind="epoch.acquisition_native_member",
                    domain="polisyos.epoch.acquisition-native-member.v1",
                    value=native_mapping,
                )
                assessments.append(
                    epoch_contract.AcquisitionNativeMemberAssessment(
                        native_member_ref=native_ref,
                        native_member_content_hash=native_hash,
                        operational_epoch_id=epoch_id,
                        passport_ref=passport_ref,
                        passport_content_hash=passport_hash,
                        semantic_candidate_ref=semantic_ref,
                        semantic_candidate_content_hash=semantic_hash,
                        binding_status=binding_status,
                        query_disposition=query_disposition,
                        failure_code=failure_code,
                    )
                )
            snapshot = {"schema_version": OVERLAY_SCHEMA_VERSION, "rows": source_rows}
            snapshot_ref, snapshot_hash = _persist_owner_record(
                con,
                kind="epoch.acquisition_owner_snapshot",
                domain="polisyos.epoch.acquisition-owner-snapshot.v1",
                value=snapshot,
            )
            failures = tuple(sorted({row.failure_code for row in assessments if row.failure_code}))
            membership_hash = _semantic_content_hash(
                domain="polisyos.epoch.acquisition-native-membership.v1",
                value={
                    "query": query.model_dump(mode="json"),
                    "owner_source_snapshot_content_hash": snapshot_hash,
                    "assessments": [row.model_dump(mode="json") for row in assessments],
                },
            )
            receipt = epoch_contract.AcquisitionNativeMembershipReceipt(
                query=query,
                owner_source_snapshot_ref=snapshot_ref,
                owner_source_snapshot_content_hash=snapshot_hash,
                declared_native_member_count=len(assessments),
                assessments=tuple(assessments),
                native_membership_hash=membership_hash,
                status="unresolved" if failures else "resolved",
                failure_codes=failures,
                predicate_class="independently_reconciled",
            )
            _persist_owner_record(
                con,
                kind="epoch.acquisition_native_membership_receipt",
                domain="polisyos.epoch.acquisition-native-membership-receipt.v1",
                value=receipt,
            )
            con.execute("COMMIT")
            return receipt
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()

    def load_acquisition_owner_snapshot(self, *, ref: ArtifactRef) -> bytes:
        """Reload exact owner snapshot bytes for independent adapter reconciliation."""

        con = duckdb.connect(str(self.overlay_path), read_only=True)
        try:
            mapping, content_hash = _load_owner_record(
                con,
                ref=ref,
                expected_kind="epoch.acquisition_owner_snapshot",
            )
        finally:
            con.close()
        if content_hash != _semantic_content_hash(
            domain="polisyos.epoch.acquisition-owner-snapshot.v1",
            value=mapping,
        ):
            raise OverlayAdmissionError("acquisition_owner_snapshot_content_hash_drift")
        canonical = epoch_contract.canonical_epoch_bytes(mapping)
        return len(canonical).to_bytes(8, "big") + canonical

    def resolve_semantic_candidate_denominator(
        self,
        *,
        query: epoch_contract.AcquisitionBoundaryResolutionQuery,
        native_membership: epoch_contract.AcquisitionNativeMembershipReceipt,
        candidate: epoch_contract.AcquisitionSemanticBoundaryCandidate | None = None,
    ) -> epoch_contract.AcquisitionSemanticCandidateDenominatorReceipt:
        """Deduplicate stable candidates while retaining native gaps as failures."""

        current = self.resolve_native_membership(query=query, candidate=candidate)
        if current != native_membership:
            raise OverlayAdmissionError("acquisition_native_membership_receipt_stale")
        identities: dict[
            tuple[str, str], epoch_contract.AcquisitionSemanticCandidateAssessment
        ] = {}
        native_unresolved = current.status == "unresolved"
        for row in current.assessments:
            if row.semantic_candidate_ref is None or row.semantic_candidate_content_hash is None:
                continue
            key = (str(row.semantic_candidate_ref.artifact_id), row.semantic_candidate_content_hash)
            identities[key] = epoch_contract.AcquisitionSemanticCandidateAssessment(
                semantic_candidate_ref=row.semantic_candidate_ref,
                semantic_candidate_content_hash=row.semantic_candidate_content_hash,
                disposition=("unresolved" if native_unresolved else row.query_disposition),
                failure_code=("acquisition_member_unresolved" if native_unresolved else None),
            )
        if candidate is not None:
            statement = candidate.statement
            if (
                statement.scope_identity_ref != query.scope_identity_ref
                or statement.authority_purpose != query.authority_purpose
            ):
                disposition = "not_applicable"
                failure_code = None
            elif (
                statement.valid_effect_coordinate_ref != query.valid_effect_coordinate_ref
                or statement.visibility_knowledge_cutoff_ref
                != query.visibility_knowledge_cutoff_ref
                or statement.purpose_admission_cutoff_ref != query.purpose_admission_cutoff_ref
                or statement.requested_query_context_ref != query.requested_query_context_ref
            ):
                disposition = "unresolved"
                failure_code = "acquisition_query_context_mismatch"
            elif native_unresolved:
                disposition = "unresolved"
                failure_code = "acquisition_member_unresolved"
            else:
                disposition = "applicable"
                failure_code = None
            identities[
                (str(candidate.candidate_ref.artifact_id), candidate.candidate_content_hash)
            ] = epoch_contract.AcquisitionSemanticCandidateAssessment(
                semantic_candidate_ref=candidate.candidate_ref,
                semantic_candidate_content_hash=candidate.candidate_content_hash,
                disposition=disposition,
                failure_code=failure_code,
            )
        assessments = tuple(identities[key] for key in sorted(identities))
        failures = {row.failure_code for row in assessments if row.failure_code}
        if native_unresolved:
            failures.add("acquisition_member_unresolved")
        candidate_set_hash = _semantic_content_hash(
            domain="polisyos.epoch.acquisition-semantic-candidate-set.v1",
            value={
                "candidates": [
                    {
                        "semantic_candidate_ref": row.semantic_candidate_ref.model_dump(
                            mode="json"
                        ),
                        "semantic_candidate_content_hash": (row.semantic_candidate_content_hash),
                    }
                    for row in assessments
                ]
            },
        )
        denominator_hash = _semantic_content_hash(
            domain="polisyos.epoch.acquisition-semantic-denominator.v1",
            value={
                "query": query.model_dump(mode="json"),
                "semantic_candidate_set_hash": candidate_set_hash,
                "assessments": [row.model_dump(mode="json") for row in assessments],
            },
        )
        receipt = epoch_contract.AcquisitionSemanticCandidateDenominatorReceipt(
            query=query,
            semantic_candidate_set_hash=candidate_set_hash,
            declared_unique_candidate_count=len(assessments),
            assessments=assessments,
            denominator_hash=denominator_hash,
            status="unresolved" if failures else "resolved",
            failure_codes=tuple(sorted(failures)),
            predicate_class="independently_reconciled",
        )
        con = duckdb.connect(str(self.overlay_path))
        try:
            _persist_owner_record(
                con,
                kind="epoch.acquisition_semantic_denominator_receipt",
                domain="polisyos.epoch.acquisition-semantic-denominator-receipt.v1",
                value=receipt,
            )
        finally:
            con.close()
        return receipt

    def verify_semantic_projection(
        self,
        *,
        native_membership_ref: ArtifactRef,
        semantic_denominator_ref: ArtifactRef,
        prospective_candidate: epoch_contract.AcquisitionSemanticBoundaryCandidate | None,
    ) -> epoch_contract.AcquisitionSemanticProjectionVerificationReceipt:
        """Reload both owner receipts and prove the stable projection independently."""

        con = duckdb.connect(str(self.overlay_path))
        try:
            native_mapping, native_hash = _load_owner_record(
                con,
                ref=native_membership_ref,
                expected_kind="epoch.acquisition_native_membership_receipt",
            )
            semantic_mapping, semantic_hash = _load_owner_record(
                con,
                ref=semantic_denominator_ref,
                expected_kind="epoch.acquisition_semantic_denominator_receipt",
            )
        finally:
            con.close()
        native = epoch_contract.AcquisitionNativeMembershipReceipt.model_validate(native_mapping)
        semantic = epoch_contract.AcquisitionSemanticCandidateDenominatorReceipt.model_validate(
            semantic_mapping
        )
        current_native = self.resolve_native_membership(
            query=native.query,
            candidate=prospective_candidate,
        )
        current_semantic = self.resolve_semantic_candidate_denominator(
            query=native.query,
            native_membership=current_native,
            candidate=prospective_candidate,
        )
        verified = (
            native.query == semantic.query
            and current_native == native
            and current_semantic == semantic
        )
        provenance = epoch_contract.AcquisitionProjectionVerifierProvenance()
        con = duckdb.connect(str(self.overlay_path))
        try:
            provenance_ref, provenance_hash = _persist_owner_record(
                con,
                kind="epoch.acquisition_projection_verifier_provenance",
                domain="polisyos.epoch.acquisition-projection-verifier.v1",
                value=provenance,
            )
            receipt = epoch_contract.AcquisitionSemanticProjectionVerificationReceipt(
                native_membership_receipt_ref=native_membership_ref,
                native_membership_receipt_content_hash=native_hash,
                semantic_denominator_receipt_ref=semantic_denominator_ref,
                semantic_denominator_receipt_content_hash=semantic_hash,
                prospective_candidate_ref=(
                    None if prospective_candidate is None else prospective_candidate.candidate_ref
                ),
                prospective_candidate_content_hash=(
                    None
                    if prospective_candidate is None
                    else prospective_candidate.candidate_content_hash
                ),
                verifier_provenance_ref=provenance_ref,
                verifier_provenance_content_hash=provenance_hash,
                status="verified" if verified else "not_established",
            )
            _persist_owner_record(
                con,
                kind="epoch.acquisition_semantic_projection_verification_receipt",
                domain=("polisyos.epoch.acquisition-semantic-projection-verification-receipt.v1"),
                value=receipt,
            )
        finally:
            con.close()
        return receipt

    def emit_admitted_boundary_evidence(
        self,
        *,
        query: epoch_contract.AcquisitionBoundaryResolutionQuery,
        passport: _Passport,
        prepared_epoch: _PreparedSemanticEpoch,
        boundary_candidate: epoch_contract.AcquisitionSemanticBoundaryCandidate,
        pending_receipt: PendingOverlayAdmissionReceipt,
        artifact_store: _ArtifactStore,
    ) -> ArtifactRef:
        """Re-enumerate the admitted native row and persist the exact owner bridge."""

        pending_mapping = _load_external_statement(
            artifact_store=artifact_store,
            ref=pending_receipt.receipt_ref,
            expected_kind="epoch.pending_overlay_admission_receipt",
        )
        persisted_pending = epoch_contract.PendingOverlayAdmissionStatement.model_validate(
            pending_mapping
        )
        supplied_pending = epoch_contract.PendingOverlayAdmissionStatement.model_validate(
            {
                name: getattr(pending_receipt, name)
                for name in epoch_contract.PendingOverlayAdmissionStatement.model_fields
            }
        )
        con = duckdb.connect(str(self.overlay_path), read_only=True)
        try:
            owner_pending_mapping, owner_pending_hash = _load_external_statement_record(
                con,
                ref=pending_receipt.receipt_ref,
                expected_kind="epoch.pending_overlay_admission_receipt",
            )
        finally:
            con.close()
        if (
            persisted_pending != supplied_pending
            or owner_pending_mapping != pending_mapping
            or owner_pending_hash != pending_receipt.receipt_content_hash
            or owner_pending_hash != _overlay_statement_content_hash(pending_mapping)
        ):
            raise OverlayAdmissionError("pending_overlay_receipt_readback_drift")
        if (
            pending_receipt.epoch_id != passport.epoch_id
            or pending_receipt.passport_id != passport.passport_id
            or pending_receipt.prepared_semantic_epoch_ref != prepared_epoch.prepared_epoch_ref
            or pending_receipt.boundary_candidate_ref != boundary_candidate.candidate_ref
            or pending_receipt.semantic_epoch_stamp != prepared_epoch.stamp
        ):
            raise OverlayAdmissionError("admitted_boundary_pending_binding_mismatch")
        current_member_keys, current_member_hash = _existing_member_denominator(
            self.overlay_path,
            epoch_id=pending_receipt.epoch_id,
            passport_id=pending_receipt.passport_id,
        )
        if (
            current_member_keys != pending_receipt.native_member_keys
            or current_member_hash != pending_receipt.native_member_denominator_hash
            or len(current_member_keys) != pending_receipt.native_member_count
        ):
            raise OverlayAdmissionError("pending_native_membership_drift")
        native = self.resolve_native_membership(query=query, candidate=None)
        native_ref, native_hash = _persist_epoch_statement(
            artifact_store=artifact_store,
            value=native,
            kind="epoch.acquisition_native_membership",
            domain="polisyos.epoch.acquisition-native-membership-receipt.v1",
        )
        semantic = self.resolve_semantic_candidate_denominator(
            query=query,
            native_membership=native,
            candidate=None,
        )
        semantic_ref, semantic_hash = _persist_epoch_statement(
            artifact_store=artifact_store,
            value=semantic,
            kind="epoch.acquisition_semantic_denominator_receipt",
            domain="polisyos.epoch.acquisition-semantic-denominator-receipt.v1",
        )
        projection = self.verify_semantic_projection(
            native_membership_ref=native_ref,
            semantic_denominator_ref=semantic_ref,
            prospective_candidate=None,
        )
        if projection.status != "verified":
            raise OverlayAdmissionError("acquisition_semantic_projection_not_verified")
        projection_ref, projection_hash = _persist_epoch_statement(
            artifact_store=artifact_store,
            value=projection,
            kind="epoch.acquisition_semantic_projection_verification_receipt",
            domain=("polisyos.epoch.acquisition-semantic-projection-verification-receipt.v1"),
        )
        con = duckdb.connect(str(self.overlay_path), read_only=True)
        try:
            provenance_mapping, provenance_owner_hash = _load_owner_record(
                con,
                ref=projection.verifier_provenance_ref,
                expected_kind="epoch.acquisition_projection_verifier_provenance",
            )
        finally:
            con.close()
        provenance = epoch_contract.AcquisitionProjectionVerifierProvenance.model_validate(
            provenance_mapping
        )
        provenance_ref, provenance_hash = _persist_epoch_statement(
            artifact_store=artifact_store,
            value=provenance,
            kind="epoch.acquisition_projection_verifier_provenance",
            domain="polisyos.epoch.acquisition-projection-verifier.v1",
        )
        if (
            provenance_ref != projection.verifier_provenance_ref
            or provenance_hash != projection.verifier_provenance_content_hash
            or provenance_owner_hash != projection.verifier_provenance_content_hash
        ):
            raise OverlayAdmissionError("acquisition_projection_verifier_provenance_drift")
        matching = tuple(
            row
            for row in native.assessments
            if row.operational_epoch_id == passport.epoch_id
            and row.passport_ref is not None
            and row.semantic_candidate_ref == boundary_candidate.candidate_ref
            and row.semantic_candidate_content_hash == boundary_candidate.candidate_content_hash
            and row.binding_status == "bound"
        )
        if len(matching) != 1:
            raise OverlayAdmissionError("admitted_native_member_not_unique")
        member = matching[0]
        if member.passport_ref is None or member.passport_content_hash is None:
            raise OverlayAdmissionError("admitted_native_member_passport_missing")
        con = duckdb.connect(str(self.overlay_path), read_only=True)
        try:
            native_mapping, stored_native_hash = _load_owner_record(
                con,
                ref=member.native_member_ref,
                expected_kind="epoch.acquisition_native_member",
            )
            passport_mapping, stored_passport_hash = _load_external_statement_record(
                con,
                ref=member.passport_ref,
                expected_kind="epoch.acquisition_passport_snapshot",
            )
        finally:
            con.close()
        if (
            stored_native_hash != member.native_member_content_hash
            or stored_passport_hash != member.passport_content_hash
        ):
            raise OverlayAdmissionError("admitted_native_member_owner_hash_drift")
        mapped_member_keys, mapped_member_hash = _native_mapping_member_denominator(
            native_mapping,
            epoch_id=pending_receipt.epoch_id,
            passport_id=pending_receipt.passport_id,
        )
        if (
            mapped_member_keys != pending_receipt.native_member_keys
            or mapped_member_hash != pending_receipt.native_member_denominator_hash
            or len(mapped_member_keys) != pending_receipt.native_member_count
        ):
            raise OverlayAdmissionError("admitted_native_member_denominator_drift")
        native_member_ref, native_member_hash = _persist_epoch_statement(
            artifact_store=artifact_store,
            value=native_mapping,
            kind="epoch.acquisition_native_member",
            domain="polisyos.epoch.acquisition-native-member.v1",
        )
        passport_ref, passport_hash = _persist_external_statement(
            artifact_store=artifact_store,
            value=passport_mapping,
            kind="epoch.acquisition_passport_snapshot",
        )
        if (
            native_member_ref != member.native_member_ref
            or native_member_hash != member.native_member_content_hash
            or passport_ref != member.passport_ref
            or passport_hash != member.passport_content_hash
        ):
            raise OverlayAdmissionError("admitted_native_member_cas_copy_drift")
        evidence = epoch_contract.AdmittedAcquisitionBoundaryEvidence(
            semantic_candidate_ref=boundary_candidate.candidate_ref,
            semantic_candidate_content_hash=boundary_candidate.candidate_content_hash,
            epoch_id=passport.epoch_id,
            native_member_ref=native_member_ref,
            native_member_content_hash=native_member_hash,
            prepared_epoch_ref=prepared_epoch.prepared_epoch_ref,
            prepared_epoch_content_hash=prepared_epoch.prepared_content_hash,
            passport_ref=passport_ref,
            passport_content_hash=passport_hash,
            pending_overlay_receipt_ref=pending_receipt.receipt_ref,
            pending_overlay_receipt_content_hash=pending_receipt.receipt_content_hash,
            native_membership_receipt_ref=native_ref,
            native_membership_receipt_content_hash=native_hash,
            semantic_denominator_receipt_ref=semantic_ref,
            semantic_denominator_receipt_content_hash=semantic_hash,
            semantic_projection_verification_receipt_ref=projection_ref,
            semantic_projection_verification_receipt_content_hash=projection_hash,
            semantic_epoch_stamp=prepared_epoch.stamp,
            verifier_provenance_ref=provenance_ref,
            predicate_class="independently_reconciled",
        )
        evidence_ref, evidence_hash = _persist_epoch_statement(
            artifact_store=artifact_store,
            value=evidence,
            kind="epoch.admitted_acquisition_boundary_evidence",
            domain="polisyos.epoch.admitted-acquisition-boundary-evidence.v1",
        )
        con = duckdb.connect(str(self.overlay_path))
        try:
            con.execute("BEGIN TRANSACTION")
            row = con.execute(
                "SELECT epoch_activation_state, admitted_boundary_evidence_ref "
                "FROM acquisition_epochs WHERE epoch_id = ? AND passport_id = ?",
                [passport.epoch_id, passport.passport_id],
            ).fetchone()
            if row is None or str(row[0]) not in {
                "pending_epoch_activation",
                "active",
            }:
                raise OverlayAdmissionError("epoch_activation_state_not_pending")
            if row[1] is not None and json.loads(str(row[1])) != evidence_ref.model_dump(
                mode="json"
            ):
                raise OverlayAdmissionError("admitted_boundary_evidence_conflict")
            _store_semantic_record(
                con,
                ref=evidence_ref,
                kind="epoch.admitted_acquisition_boundary_evidence",
                content_hash=evidence_hash,
                value=evidence,
            )
            if str(row[0]) == "pending_epoch_activation":
                con.execute(
                    "UPDATE acquisition_epochs SET admitted_boundary_evidence_ref = ? "
                    "WHERE epoch_id = ? AND passport_id = ?",
                    [
                        json.dumps(evidence_ref.model_dump(mode="json")),
                        passport.epoch_id,
                        passport.passport_id,
                    ],
                )
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        return evidence_ref

    def _require_baseline_unchanged(self) -> BaselineIdentity:
        current = _baseline_identity(self.baseline_path)
        if current != self._baseline_identity:
            raise BaselineMutationError(
                "baseline_mutation_detected",
                (
                    f"expected {self._baseline_identity.content_sha256}, "
                    f"observed {current.content_sha256}"
                ),
            )
        return current

    def close(self) -> None:
        """Release the logical owner; connections are transaction-scoped."""

        self._initialized = False


def default_acquisition_overlay_path(repo_root: Path) -> Path:
    """Return the registered acquisition-overlay path beneath ``repo_root``."""

    return Path(repo_root) / DEFAULT_ACQUISITION_OVERLAY_PATH


_EXTERNAL_RECEIPT_KINDS = frozenset(
    {
        "epoch.activated_overlay_admission_receipt",
        "epoch.acquisition_passport_snapshot",
        "epoch.pending_overlay_admission_receipt",
    }
)
_SEMANTIC_RECEIPT_DOMAINS = {
    "epoch.acquisition_native_member": "polisyos.epoch.acquisition-native-member.v1",
    "epoch.acquisition_native_membership": (
        "polisyos.epoch.acquisition-native-membership-receipt.v1"
    ),
    "epoch.acquisition_native_membership_receipt": (
        "polisyos.epoch.acquisition-native-membership-receipt.v1"
    ),
    "epoch.acquisition_owner_snapshot": "polisyos.epoch.acquisition-owner-snapshot.v1",
    "epoch.acquisition_projection_verifier_provenance": (
        "polisyos.epoch.acquisition-projection-verifier.v1"
    ),
    "epoch.acquisition_semantic_denominator_receipt": (
        "polisyos.epoch.acquisition-semantic-denominator-receipt.v1"
    ),
    "epoch.acquisition_semantic_projection_verification_receipt": (
        "polisyos.epoch.acquisition-semantic-projection-verification-receipt.v1"
    ),
    "epoch.admitted_acquisition_boundary_evidence": (
        "polisyos.epoch.admitted-acquisition-boundary-evidence.v1"
    ),
    "epoch.production_receipt": "polisyos.epoch.production-receipt.v1",
}


def _validated_semantic_receipt_metadata(
    *,
    receipt_ref: object,
    receipt_kind: object,
    receipt_content_hash: object,
    receipt_json: object,
) -> CatalogAcquisitionEventProjection:
    """Validate persisted receipt bytes and return their metadata-only carrier."""

    kind = str(receipt_kind)
    try:
        payload = json.loads(str(receipt_json))
    except json.JSONDecodeError as exc:
        raise OverlayAdmissionError("overlay_semantic_receipt_json_invalid") from exc
    if not isinstance(payload, dict):
        raise OverlayAdmissionError("overlay_semantic_receipt_not_mapping")
    if kind in _EXTERNAL_RECEIPT_KINDS:
        framed = _overlay_statement_payload(payload)
        recomputed_hash = _overlay_statement_content_hash(payload)
    elif kind == "epoch.acquisition_semantic_boundary_candidate":
        try:
            statement = epoch_contract.AcquisitionSemanticBoundaryCandidateStatement.model_validate(
                payload
            )
        except ValueError as exc:
            raise OverlayAdmissionError("overlay_semantic_receipt_payload_invalid", kind) from exc
        canonical = epoch_contract.canonical_epoch_bytes(statement)
        framed = len(canonical).to_bytes(8, "big") + canonical
        recomputed_hash = epoch_contract.acquisition_semantic_candidate_content_hash(statement)
    elif domain := _SEMANTIC_RECEIPT_DOMAINS.get(kind):
        canonical = epoch_contract.canonical_epoch_bytes(payload)
        framed = len(canonical).to_bytes(8, "big") + canonical
        recomputed_hash = _semantic_content_hash(domain=domain, value=payload)
    else:
        raise OverlayAdmissionError("overlay_semantic_receipt_kind_not_supported", kind)
    if str(receipt_ref) != f"sha256:{hashlib.sha256(framed).hexdigest()}":
        raise OverlayAdmissionError("overlay_semantic_receipt_ref_content_mismatch", kind)
    if str(receipt_content_hash) != recomputed_hash:
        raise OverlayAdmissionError("overlay_semantic_receipt_content_hash_mismatch", kind)
    return CatalogAcquisitionEventProjection(
        receipt_ref=str(receipt_ref),
        receipt_kind=kind,
        receipt_content_hash=str(receipt_content_hash),
    )


def validate_overlay_admission_receipt(
    receipt: object,
) -> CatalogAcquisitionEventProjection:
    """Validate one active owner receipt and return its content-bound metadata."""

    if isinstance(receipt, BaseModel):
        candidate = receipt.model_dump(mode="python")
    elif isinstance(receipt, Mapping):
        candidate = dict(receipt)
    else:
        raise OverlayAdmissionError("overlay_admission_receipt_payload_invalid")
    try:
        validated = OverlayAdmissionReceipt.model_validate(candidate)
        statement = epoch_contract.ActivatedOverlayAdmissionStatement.model_validate(
            validated.model_dump(
                mode="python",
                exclude={"receipt_ref", "receipt_content_hash", "replayed"},
            )
        )
    except ValueError as exc:
        raise OverlayAdmissionError("overlay_admission_receipt_payload_invalid") from exc
    if (
        validated.receipt_ref.kind != "epoch.activated_overlay_admission_receipt"
        or validated.receipt_ref.media_type != "application/vnd.polisyos.epoch+json"
    ):
        raise OverlayAdmissionError("overlay_admission_receipt_kind_invalid")
    return _validated_semantic_receipt_metadata(
        receipt_ref=validated.receipt_ref.artifact_id,
        receipt_kind=validated.receipt_ref.kind,
        receipt_content_hash=validated.receipt_content_hash,
        receipt_json=json.dumps(statement.model_dump(mode="json")),
    )


def project_catalog_acquisition_state(
    baseline_path: Path,
    *,
    overlay_path: Path | None = None,
) -> CatalogAcquisitionStateProjection:
    """Project validated overlay metadata without opening any writer connection."""

    baseline = _baseline_identity(Path(baseline_path))
    selected = None if overlay_path is None else Path(overlay_path)
    if selected is None or not (selected.exists() or selected.is_symlink()):
        return CatalogAcquisitionStateProjection(
            baseline=baseline,
            overlay_ref=None if selected is None else selected.as_posix(),
            overlay_exists=False,
            epoch_count=0,
            passport_count=0,
            pending_epoch_count=0,
            active_epoch_count=0,
            admitted_observation_count=0,
            semantic_receipt_count=0,
            registration_count=0,
            epochs=(),
            passports=(),
            events=(),
        )
    con = open_catalog_read_session(Path(baseline_path), overlay_path=selected)
    try:
        raw_epochs = con.execute(
            "SELECT epoch_id, passport_id, admitted_observation_count, "
            "epoch_activation_state, semantic_epoch_ref FROM acquisition_epochs "
            "ORDER BY epoch_id"
        ).fetchall()
        raw_passports = con.execute(
            "SELECT passport_id, epoch_id, passport_content_sha256, passport_json "
            "FROM acquisition_passports ORDER BY epoch_id, passport_id"
        ).fetchall()
        epoch_owners = {(int(row[0]), str(row[1])) for row in raw_epochs}
        passports: list[CatalogAcquisitionPassportProjection] = []
        for passport_id, epoch_id, expected_hash, raw_json in raw_passports:
            try:
                payload = json.loads(str(raw_json))
            except json.JSONDecodeError as exc:
                raise OverlayAdmissionError("overlay_passport_json_invalid") from exc
            if not isinstance(payload, dict) or content_sha256(payload) != str(expected_hash):
                raise OverlayAdmissionError("overlay_passport_content_hash_mismatch")
            if (int(epoch_id), str(passport_id)) not in epoch_owners:
                raise OverlayAdmissionError("overlay_passport_epoch_binding_mismatch")
            if payload.get("passport_id") != str(passport_id) or int(
                payload.get("epoch_id") or -1
            ) != int(epoch_id):
                raise OverlayAdmissionError("overlay_passport_identity_mismatch")
            try:
                passports.append(
                    CatalogAcquisitionPassportProjection.model_validate(
                        {
                            field: payload.get(field)
                            for field in (
                                "schema_version",
                                "passport_id",
                                "epoch_id",
                                "variable_id",
                                "source_lane",
                                "observation_class",
                                "status",
                                "rejection_codes",
                            )
                        }
                    )
                )
            except ValueError as exc:
                raise OverlayAdmissionError("overlay_passport_metadata_invalid") from exc
        if len(raw_passports) != len(raw_epochs):
            raise OverlayAdmissionError("overlay_passport_denominator_mismatch")
        raw_receipts = con.execute(
            "SELECT receipt_ref, receipt_kind, receipt_content_hash, receipt_json "
            "FROM acquisition_semantic_receipts ORDER BY receipt_ref"
        ).fetchall()
        events = tuple(
            _validated_semantic_receipt_metadata(
                receipt_ref=receipt_ref,
                receipt_kind=receipt_kind,
                receipt_content_hash=receipt_content_hash,
                receipt_json=receipt_json,
            )
            for receipt_ref, receipt_kind, receipt_content_hash, receipt_json in raw_receipts
        )
        registration_count = int(
            con.execute("SELECT count(*) FROM acquisition_registrations").fetchone()[0]
        )
    finally:
        con.close()
    epochs = tuple(
        CatalogAcquisitionEpochProjection(
            epoch_id=int(epoch_id),
            passport_id=str(passport_id),
            admitted_observation_count=int(admitted_count),
            epoch_activation_state=str(state),
            semantic_epoch_ref=None if semantic_ref is None else str(semantic_ref),
        )
        for epoch_id, passport_id, admitted_count, state, semantic_ref in raw_epochs
    )
    return CatalogAcquisitionStateProjection(
        baseline=baseline,
        overlay_ref=selected.as_posix(),
        overlay_exists=True,
        epoch_count=len(epochs),
        passport_count=len(raw_passports),
        pending_epoch_count=sum(
            epoch.epoch_activation_state == "pending_epoch_activation" for epoch in epochs
        ),
        active_epoch_count=sum(epoch.epoch_activation_state == "active" for epoch in epochs),
        admitted_observation_count=sum(epoch.admitted_observation_count for epoch in epochs),
        semantic_receipt_count=len(events),
        registration_count=registration_count,
        epochs=epochs,
        passports=tuple(passports),
        events=events,
    )


def open_catalog_read_session(
    baseline_path: Path,
    *,
    overlay_path: Path | None = None,
) -> duckdb.DuckDBPyConnection:
    """Open one read-only union session over epoch zero and admitted epochs.

    A missing optional overlay means an epoch-zero-only session.  An existing
    overlay is authoritative only when its complete schema and recorded
    baseline content identity validate; malformed or cross-baseline overlays
    fail closed instead of silently falling back.
    """

    baseline = Path(baseline_path)
    selected_overlay = Path(overlay_path) if overlay_path is not None else None
    overlay_present = selected_overlay is not None and (
        selected_overlay.exists() or selected_overlay.is_symlink()
    )
    if selected_overlay is None or not overlay_present:
        if not baseline.is_file():
            raise BaselineMutationError("baseline_catalog_missing", baseline.as_posix())
        try:
            return duckdb.connect(str(baseline), read_only=True)
        except duckdb.Error as exc:
            raise BaselineMutationError(
                "baseline_catalog_unreadable",
                type(exc).__name__,
            ) from exc

    if not selected_overlay.is_file():
        raise OverlayAdmissionError(
            "overlay_catalog_unreadable",
            selected_overlay.as_posix(),
        )
    if selected_overlay.resolve() == baseline.resolve():
        raise BaselineMutationError(
            "overlay_path_equals_baseline",
            baseline.as_posix(),
        )

    con = duckdb.connect(":memory:")
    try:
        try:
            _attach_read_only(con, baseline, alias="baseline")
        except duckdb.Error as exc:
            raise BaselineMutationError(
                "baseline_catalog_unreadable",
                type(exc).__name__,
            ) from exc
        identity = _baseline_identity(baseline)
        _require_attached_tables(
            con,
            alias="baseline",
            expected=_BASELINE_UNION_TABLES,
            error_code="baseline_catalog_contract_incomplete",
        )

        try:
            _attach_read_only(con, selected_overlay, alias="acquisition_overlay")
        except duckdb.Error as exc:
            raise OverlayAdmissionError(
                "overlay_catalog_unreadable",
                type(exc).__name__,
            ) from exc
        _require_attached_tables(
            con,
            alias="acquisition_overlay",
            expected=(*_BASELINE_UNION_TABLES, *_OVERLAY_AUDIT_TABLES),
            error_code="overlay_catalog_contract_incomplete",
        )
        _require_overlay_baseline_identity(con, identity, selected_overlay)
        _require_overlay_epoch_contract(con)
        _require_epoch_member_contract(con, database_name="acquisition_overlay")

        key_spec = _derive_baseline_primary_key_spec(con)
        for table in _BASELINE_UNION_TABLES:
            key_bytes_sql = _sql_member_key_bytes(
                table=table,
                columns=key_spec[table],
                alias="overlay_row",
            )
            key_hash_sql = _sql_member_key_hash(
                table=table,
                columns=key_spec[table],
                alias="overlay_row",
            )
            source = (
                f"SELECT * FROM baseline.{table} "  # noqa: S608
                "UNION ALL BY NAME "
                f"SELECT overlay_row.* FROM acquisition_overlay.{table} AS overlay_row "
                "WHERE EXISTS ("
                "SELECT 1 FROM acquisition_overlay.acquisition_epoch_members AS member "
                "JOIN acquisition_overlay.acquisition_epochs AS admitted "
                "ON admitted.epoch_id = member.epoch_id "
                "AND admitted.passport_id = member.passport_id "
                f"WHERE member.table_name = '{table}' "
                f"AND member.canonical_primary_key_bytes = {key_bytes_sql} "
                f"AND member.canonical_primary_key_hash = {key_hash_sql} "
                "AND admitted.epoch_activation_state = 'active'"
                ")"
            )
            con.execute(f"CREATE TEMP VIEW {table} AS {source}")
        for table in _OVERLAY_AUDIT_TABLES:
            con.execute(
                f"CREATE TEMP VIEW {table} AS "  # noqa: S608
                f"SELECT * FROM acquisition_overlay.{table}"
            )

        return con
    except Exception:
        con.close()
        raise


def build_metric_field_binding(
    *,
    dataset_id: str,
    distribution_id: str,
    raw_field: str,
    canonical_variable: str,
    raw_unit: str,
    canonical_unit: str,
    unit_transform: str,
    unit_transform_ref: str | None,
    alignment_method: Literal["exact", "semantic", "meta_analytic"],
    alignment_confidence: float,
    is_proxy: bool,
    proxy_penalty: float,
    evidence_refs: tuple[str, ...],
    aggregation_method: Literal["identity", "mean", "sum", "last"] = "identity",
    valid_min: float | None = None,
    valid_max: float | None = None,
) -> MetricFieldBinding:
    """Build a field edge through the existing VariableAlignment calibrator."""

    from polisyos.data_forge.domains.catalog.knowledge.variable_alignment import (
        AlignmentMethod,
        VariableAlignment,
        calibrate_alignment_confidence,
    )

    alignment = VariableAlignment(
        canonical_var=canonical_variable,
        dataset_var=raw_field,
        dataset_id=dataset_id,
        method=AlignmentMethod(alignment_method),
        confidence=alignment_confidence,
        evidence=";".join(evidence_refs),
        is_proxy=is_proxy,
        proxy_penalty=proxy_penalty,
    )
    values: dict[str, object] = {
        "dataset_id": dataset_id,
        "distribution_id": distribution_id,
        "raw_field": raw_field,
        "canonical_variable": canonical_variable,
        "raw_unit": raw_unit,
        "canonical_unit": canonical_unit,
        "unit_transform": unit_transform,
        "unit_transform_ref": unit_transform_ref,
        "alignment_method": alignment_method,
        "alignment_confidence": alignment_confidence,
        "calibrated_alignment_confidence": calibrate_alignment_confidence(alignment),
        "is_proxy": is_proxy,
        "proxy_penalty": proxy_penalty,
        "evidence_refs": evidence_refs,
        "aggregation_method": aggregation_method,
        "valid_min": valid_min,
        "valid_max": valid_max,
    }
    return MetricFieldBinding(
        binding_id="field-binding:" + content_sha256(values),
        **values,
    )


def _validate_passport_owner_evidence(
    passport: _Passport,
    *,
    artifact_store: _ArtifactStore,
    authority: _CanonicalAuthority,
) -> bytes:
    raw_ref = passport.raw_evidence_ref
    if not isinstance(raw_ref, JournalEventRef):
        raise OverlayAdmissionError("raw_evidence_ref_unresolved")
    try:
        body = resolve_raw_response_body(raw_ref)
    except Exception as exc:
        raise OverlayAdmissionError("raw_evidence_ref_unresolved", type(exc).__name__) from exc
    if not passport.raw_evidence_verified:
        raise OverlayAdmissionError("raw_evidence_not_verified")
    raw_artifact_id = str(passport.raw_artifact_id)
    try:
        artifact_id = ArtifactID.model_validate(raw_artifact_id)
    except Exception as exc:
        raise OverlayAdmissionError("raw_artifact_id_invalid") from exc
    if not artifact_store.has(artifact_id) or artifact_store.get_bytes(artifact_id) != body:
        raise OverlayAdmissionError("raw_cas_evidence_unresolved")
    if not passport.cas_evidence_verified:
        raise OverlayAdmissionError("raw_cas_evidence_not_verified")
    raw_body_sha = f"sha256:{hashlib.sha256(body).hexdigest()}"
    if str(passport.source_watermark) != raw_body_sha:
        raise OverlayAdmissionError("source_watermark_content_drift")
    profile = passport.measured_profile
    if profile is None:
        raise OverlayAdmissionError("measured_profile_missing")
    if getattr(profile, "raw_evidence_event_sha256", None) != raw_ref.event_sha256:
        raise OverlayAdmissionError("measured_profile_event_drift")
    scan = scan_secret_and_pii(
        body,
        scope="connector request/response payloads",
        artifact_ref_or_route=raw_ref.event_sha256,
        redact=False,
        block_on_findings=True,
    )
    embedded_scan = passport.pii_scan
    if tuple(scan.finding_kinds) != tuple(getattr(embedded_scan, "finding_kinds", ())):
        raise OverlayAdmissionError("pii_scan_evidence_drift")
    try:
        resolved = authority.resolve(str(passport.authority_entry_id))
    except Exception as exc:
        raise OverlayAdmissionError("acquisition_authority_unresolved", type(exc).__name__) from exc
    authority_projection = (
        str(getattr(resolved, "authority_provision_id", "")),
        str(getattr(resolved, "authority_provision_content_sha256", "")),
        str(getattr(resolved, "registry_content_sha256", "")),
        str(getattr(resolved, "baseline_content_sha256", "")),
        str(getattr(resolved, "upstream_catalog_projection_sha256", "")),
        getattr(resolved, "registration", None),
        getattr(resolved, "field_binding", None),
    )
    embedded_projection = (
        str(passport.authority_provision_id),
        str(passport.authority_provision_content_sha256),
        str(passport.authority_registry_content_sha256),
        str(passport.baseline_content_sha256),
        str(passport.upstream_catalog_projection_sha256),
        passport.registration,
        passport.field_binding,
    )
    if authority_projection != embedded_projection:
        raise OverlayAdmissionError("acquisition_authority_drift")
    resolved_entry = getattr(resolved, "entry", None)
    resolved_source_lane = str(getattr(resolved_entry, "source_lane", ""))
    passport_source_lane = str(passport.source_lane)
    if resolved_source_lane != passport_source_lane:
        raise OverlayAdmissionError("acquisition_source_lane_drift")
    if passport_source_lane == "live_fetch":
        live_source_execution = passport.live_source_execution
        if live_source_execution is None:
            raise OverlayAdmissionError("live_source_execution_evidence_required")
        try:
            source_body = authority.resolve_live_source_body(
                str(passport.authority_entry_id),
                live_source_execution,
                artifact_store,
            )
        except Exception as exc:
            raise OverlayAdmissionError(
                "live_source_execution_unresolved",
                type(exc).__name__,
            ) from exc
        source_authority_verified = True
    elif passport_source_lane == "local_lift":
        if passport.live_source_execution is not None:
            raise OverlayAdmissionError("local_lift_live_execution_evidence_forbidden")
        source_body = body
        source_authority_verified = authority.verify_source_body(
            str(passport.authority_entry_id),
            body,
        )
    else:
        raise OverlayAdmissionError("acquisition_source_lane_invalid")
    source_body_sha = f"sha256:{hashlib.sha256(source_body).hexdigest()}"
    if getattr(profile, "sample_content_sha256", None) != source_body_sha:
        raise OverlayAdmissionError("measured_profile_content_drift")
    license_evidence = passport.license_evidence
    resolved_license = getattr(resolved, "license_disposition", None)
    if (
        str(getattr(resolved, "license_id", "")) != str(getattr(license_evidence, "license_id", ""))
        or _enum_value(resolved_license)
        != _enum_value(getattr(license_evidence, "disposition", ""))
        or str(getattr(resolved, "license_authority_ref", ""))
        != str(getattr(license_evidence, "authority_ref", ""))
        or str(getattr(resolved, "license_authority_content_sha256", ""))
        != str(getattr(license_evidence, "authority_content_sha256", ""))
    ):
        raise OverlayAdmissionError("license_authority_drift")
    resolved_l5 = getattr(resolved, "l5_trust", None)
    embedded_l5 = passport.l5_trust
    l5_projection = (
        str(getattr(resolved_l5, "family_id", "")),
        str(getattr(resolved_l5, "tier", "")),
        float(getattr(resolved_l5, "trust_cap", 0.0)),
        float(getattr(resolved_l5, "trust_multiplier", 0.0)),
        str(getattr(resolved_l5, "authority_ref", "")),
        str(getattr(resolved_l5, "owner_ref", "")),
    )
    if l5_projection != (
        str(getattr(embedded_l5, "family_id", "")),
        str(getattr(embedded_l5, "tier", "")),
        float(getattr(embedded_l5, "trust_cap", 0.0)),
        float(getattr(embedded_l5, "trust_multiplier", 0.0)),
        str(getattr(embedded_l5, "authority_ref", "")),
        str(getattr(embedded_l5, "owner_ref", "")),
    ):
        raise OverlayAdmissionError("l5_trust_evidence_drift")
    if not passport.source_authority_verified or not source_authority_verified:
        raise OverlayAdmissionError("source_authority_unverified")
    schema_validation = passport.schema_validation
    if not bool(getattr(schema_validation, "conformant", False)):
        raise OverlayAdmissionError("schema_contract_not_conformant")
    request_event = resolve_linked_request_event(raw_ref)
    request = request_event.get("request")
    schema_projection = getattr(resolved_entry, "schema_projection", None)
    if (
        not isinstance(request, Mapping)
        or not callable(schema_projection)
        or request.get("schema_contract") != schema_projection()
    ):
        raise OverlayAdmissionError("request_schema_contract_drift")
    recomputed_id = passport.recomputed_passport_id
    recomputed_rejections = passport.recomputed_rejection_codes
    if not callable(recomputed_id) or not callable(recomputed_rejections):
        raise OverlayAdmissionError("passport_recomputation_surface_missing")
    if recomputed_id() != str(passport.passport_id):
        raise OverlayAdmissionError("passport_identity_drift")
    if tuple(recomputed_rejections()) != tuple(passport.rejection_codes):
        raise OverlayAdmissionError("passport_rejection_drift")
    return source_body


def derive_canonical_observations(
    raw_body: bytes,
    *,
    passport: _Passport,
    registration: AcquisitionDatasetRegistration,
) -> tuple[CanonicalAcquisitionObservation, ...]:
    """Derive overlay rows from verified bytes and one registered field edge.

    This is the only raw-to-canonical value path.  Admission accepts no caller
    observation payload, so an in-range fabricated value cannot bypass the
    journal/CAS identity or the registered transformation and aggregation.
    """

    try:
        payload = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OverlayAdmissionError("raw_observations_not_json") from exc
    if isinstance(payload, Mapping):
        raw_rows: tuple[Mapping[str, object], ...] = (payload,)
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        if not payload or not all(isinstance(row, Mapping) for row in payload):
            raise OverlayAdmissionError("raw_observations_not_tabular")
        raw_rows = tuple(row for row in payload if isinstance(row, Mapping))
    else:
        raise OverlayAdmissionError("raw_observations_not_tabular")

    binding = registration.field_binding
    if binding.unit_transform != "identity":
        raise OverlayAdmissionError(
            "unit_transform_executor_unregistered",
            binding.unit_transform,
        )
    if binding.raw_unit != binding.canonical_unit:
        raise OverlayAdmissionError("identity_unit_transform_mismatch")

    measured: list[tuple[tuple[str, int | None, int | None, int | None, str], float]] = []
    for index, raw_row in enumerate(raw_rows):
        if binding.raw_field not in raw_row:
            raise OverlayAdmissionError("raw_field_missing", str(index))
        raw_value = raw_row[binding.raw_field]
        if isinstance(raw_value, bool):
            raise OverlayAdmissionError("raw_value_not_numeric", str(index))
        try:
            numeric_value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise OverlayAdmissionError("raw_value_not_numeric", str(index)) from exc
        if not math.isfinite(numeric_value):
            raise OverlayAdmissionError("raw_value_not_finite", str(index))
        country_code = str(raw_row.get("country_code") or "unknown")
        year = _optional_int(raw_row.get("year"), field="year", row_index=index)
        survey_year = _optional_int(
            raw_row.get("survey_year"), field="survey_year", row_index=index
        )
        wave = _optional_int(raw_row.get("wave"), field="wave", row_index=index)
        if year is None and survey_year is None and wave is None:
            raise OverlayAdmissionError("raw_time_coordinate_missing", str(index))
        condition = raw_row.get("condition_json", {})
        if isinstance(condition, str):
            try:
                condition = json.loads(condition)
            except json.JSONDecodeError as exc:
                raise OverlayAdmissionError("raw_condition_invalid", str(index)) from exc
        if not isinstance(condition, Mapping):
            raise OverlayAdmissionError("raw_condition_invalid", str(index))
        condition_json = json.dumps(
            dict(condition),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        measured.append(((country_code, year, survey_year, wave, condition_json), numeric_value))

    grouped: dict[tuple[str, int | None, int | None, int | None, str], list[float]] = {}
    for key, value in measured:
        grouped.setdefault(key, []).append(value)
    derived: list[CanonicalAcquisitionObservation] = []
    body_sha256 = f"sha256:{hashlib.sha256(raw_body).hexdigest()}"
    for key in sorted(grouped, key=lambda item: tuple(str(part) for part in item)):
        values = grouped[key]
        if binding.aggregation_method == "identity":
            if len(values) != 1:
                raise OverlayAdmissionError(
                    "identity_aggregation_not_unique",
                    repr(key),
                )
            canonical_value = values[0]
        elif binding.aggregation_method == "mean":
            canonical_value = sum(values) / len(values)
        elif binding.aggregation_method == "sum":
            canonical_value = sum(values)
        elif binding.aggregation_method == "last":
            canonical_value = values[-1]
        else:  # pragma: no cover - the strict binding enum owns the denominator.
            raise OverlayAdmissionError(
                "aggregation_executor_unregistered",
                str(binding.aggregation_method),
            )
        country_code, year, survey_year, wave, condition_json = key
        identity = {
            "epoch_id": int(passport.epoch_id),
            "dataset_id": registration.catalog_dataset_id,
            "raw_field": binding.raw_field,
            "canonical_variable": binding.canonical_variable,
            "country_code": country_code,
            "year": year,
            "survey_year": survey_year,
            "wave": wave,
            "condition_json": condition_json,
            "value": canonical_value,
            "raw_body_sha256": body_sha256,
            "binding_id": binding.binding_id,
        }
        derived.append(
            CanonicalAcquisitionObservation(
                observation_id="acquisition-observation:" + content_sha256(identity),
                dataset_id=registration.catalog_dataset_id,
                raw_variable=binding.raw_field,
                canonical_var=binding.canonical_variable,
                country_code=country_code,
                year=year,
                survey_year=survey_year,
                wave=wave,
                value=canonical_value,
                condition_json=condition_json,
                acquisition_method=(
                    f"registered_{binding.unit_transform}_{binding.aggregation_method}_lift"
                ),
                source_watermark=str(passport.source_watermark),
                dataset_version=str(passport.dataset_version),
                observation_class=ObservationProvenanceClass(
                    _enum_value(passport.observation_class)
                ),
            )
        )
    rows = tuple(derived)
    if not rows:
        raise OverlayAdmissionError("admitted_observations_missing")
    _validate_observations(
        rows,
        passport=passport,
        registration=registration,
        observation_class=ObservationProvenanceClass(_enum_value(passport.observation_class)),
    )
    return rows


def _optional_int(value: object, *, field: str, row_index: int) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise OverlayAdmissionError("raw_time_coordinate_invalid", f"{row_index}:{field}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise OverlayAdmissionError("raw_time_coordinate_invalid", f"{row_index}:{field}") from exc


def _validate_observations(
    observations: Sequence[CanonicalAcquisitionObservation],
    *,
    passport: _Passport,
    registration: AcquisitionDatasetRegistration,
    observation_class: ObservationProvenanceClass,
) -> None:
    seen: set[str] = set()
    binding = registration.field_binding
    for row in observations:
        if row.observation_id in seen:
            raise OverlayAdmissionError("duplicate_observation_id", row.observation_id)
        seen.add(row.observation_id)
        if row.dataset_id != registration.catalog_dataset_id:
            raise OverlayAdmissionError("observation_dataset_drift", row.observation_id)
        if row.raw_variable != binding.raw_field or row.canonical_var != binding.canonical_variable:
            raise OverlayAdmissionError("observation_field_binding_drift", row.observation_id)
        if row.observation_class is not observation_class:
            raise OverlayAdmissionError("observation_provenance_class_drift", row.observation_id)
        if row.source_watermark != str(passport.source_watermark):
            raise OverlayAdmissionError("observation_watermark_drift", row.observation_id)
        if row.dataset_version != str(passport.dataset_version):
            raise OverlayAdmissionError("observation_dataset_version_drift", row.observation_id)
        if binding.valid_min is not None and row.value < binding.valid_min:
            raise OverlayAdmissionError("observation_below_valid_range", row.observation_id)
        if binding.valid_max is not None and row.value > binding.valid_max:
            raise OverlayAdmissionError("observation_above_valid_range", row.observation_id)


def _migrate_epoch_table_v2(con: duckdb.DuckDBPyConnection) -> None:
    """Advance a complete v1 table to v2 inside the caller's transaction."""

    available = {
        str(row[0])
        for row in con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_catalog = current_database() "
            "AND table_schema = 'main' AND table_name = 'acquisition_epochs'"
        ).fetchall()
    }
    additions = {
        "semantic_epoch_ref": "VARCHAR",
        "semantic_epoch_stamp_sha256": "VARCHAR",
        "semantic_epoch_stamp_json": "JSON",
        "prepared_semantic_epoch_ref": "JSON",
        "pending_overlay_receipt_ref": "JSON",
        "admitted_boundary_evidence_ref": "JSON",
        "semantic_epoch_production_receipt_ref": "JSON",
        "activated_overlay_receipt_ref": "JSON",
        "epoch_activation_state": "VARCHAR",
    }
    for column, sql_type in additions.items():
        if column not in available:
            con.execute(f"ALTER TABLE acquisition_epochs ADD COLUMN {column} {sql_type}")
    partial = con.execute(
        """
        SELECT epoch_id
        FROM acquisition_epochs
        WHERE (semantic_epoch_ref IS NULL)::INTEGER
            + (semantic_epoch_stamp_sha256 IS NULL)::INTEGER
            + (semantic_epoch_stamp_json IS NULL)::INTEGER
          NOT IN (0, 3)
        LIMIT 1
        """
    ).fetchone()
    if partial is not None:
        raise OverlayAdmissionError("partial_semantic_stamp_columns", str(partial[0]))
    con.execute(
        """
        UPDATE acquisition_epochs
        SET epoch_activation_state = CASE
            WHEN semantic_epoch_ref IS NULL THEN 'legacy_not_established'
            ELSE COALESCE(epoch_activation_state, 'active')
        END
        WHERE epoch_activation_state IS NULL
        """
    )
    invalid = con.execute(
        """
        SELECT epoch_id FROM acquisition_epochs
        WHERE epoch_activation_state NOT IN (
            'legacy_not_established', 'pending_epoch_activation', 'active'
        )
        LIMIT 1
        """
    ).fetchone()
    if invalid is not None:
        raise OverlayAdmissionError("epoch_activation_state_invalid", str(invalid[0]))
    _ensure_epoch_state_constraint(con)
    migrated_columns = tuple(
        (str(name), str(data_type), str(nullable))
        for name, data_type, nullable in con.execute(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_catalog = current_database() "
            "AND table_schema = 'main' AND table_name = 'acquisition_epochs' "
            "ORDER BY ordinal_position"
        ).fetchall()
    )
    if migrated_columns != _ACQUISITION_EPOCH_COLUMNS:
        raise OverlayAdmissionError("overlay_epoch_schema_contract_incomplete")
    expected_constraint = _expected_epoch_state_constraint_text(con)
    migrated_checks = {
        str(row[0])
        for row in con.execute(
            "SELECT constraint_text FROM duckdb_constraints() "
            "WHERE database_name = current_database() "
            "AND schema_name = current_schema() "
            "AND table_name = 'acquisition_epochs' "
            "AND constraint_type = 'CHECK'"
        ).fetchall()
    }
    if expected_constraint not in migrated_checks:
        raise OverlayAdmissionError("overlay_epoch_state_constraint_not_established")


def _ensure_epoch_state_constraint(con: duckdb.DuckDBPyConnection) -> None:
    """Rebuild a legacy epoch table once so state/triple checks are physical."""

    expected_constraint = _expected_epoch_state_constraint_text(con)
    existing_rows = con.execute(
        "SELECT constraint_text FROM duckdb_constraints() "
        "WHERE database_name = current_database() "
        "AND schema_name = current_schema() "
        "AND constraint_type = 'CHECK' "
        "AND table_name = 'acquisition_epochs'"
    ).fetchall()
    if any(str(row[0]) == expected_constraint for row in existing_rows):
        return
    con.execute(
        f"""
        CREATE TABLE acquisition_epochs_v2_guarded (
            epoch_id BIGINT PRIMARY KEY,
            passport_id VARCHAR NOT NULL,
            admission_content_sha256 VARCHAR NOT NULL,
            baseline_content_sha256 VARCHAR NOT NULL,
            admitted_observation_count BIGINT NOT NULL,
            observation_class VARCHAR NOT NULL,
            semantic_epoch_ref VARCHAR,
            semantic_epoch_stamp_sha256 VARCHAR,
            semantic_epoch_stamp_json JSON,
            prepared_semantic_epoch_ref JSON,
            pending_overlay_receipt_ref JSON,
            admitted_boundary_evidence_ref JSON,
            semantic_epoch_production_receipt_ref JSON,
            activated_overlay_receipt_ref JSON,
            epoch_activation_state VARCHAR NOT NULL,
            CONSTRAINT acquisition_epoch_semantic_state_check
            CHECK ({_EPOCH_STATE_PREDICATE})
        )
        """
    )
    con.execute(
        "INSERT INTO acquisition_epochs_v2_guarded SELECT "
        "epoch_id, passport_id, admission_content_sha256, baseline_content_sha256, "
        "admitted_observation_count, observation_class, semantic_epoch_ref, "
        "semantic_epoch_stamp_sha256, semantic_epoch_stamp_json, "
        "prepared_semantic_epoch_ref, pending_overlay_receipt_ref, "
        "admitted_boundary_evidence_ref, semantic_epoch_production_receipt_ref, "
        "activated_overlay_receipt_ref, epoch_activation_state FROM acquisition_epochs"
    )
    con.execute("DROP TABLE acquisition_epochs")
    con.execute("ALTER TABLE acquisition_epochs_v2_guarded RENAME TO acquisition_epochs")


def _expected_epoch_state_constraint_text(con: duckdb.DuckDBPyConnection) -> str:
    """Let DuckDB normalize the one canonical CHECK, then compare it exactly."""

    table = "gy_n12_expected_epoch_state_constraint"
    con.execute(
        f"""
        CREATE TEMP TABLE {table} (
            epoch_activation_state VARCHAR,
            semantic_epoch_ref VARCHAR,
            semantic_epoch_stamp_sha256 VARCHAR,
            semantic_epoch_stamp_json JSON,
            prepared_semantic_epoch_ref JSON,
            pending_overlay_receipt_ref JSON,
            admitted_boundary_evidence_ref JSON,
            semantic_epoch_production_receipt_ref JSON,
            activated_overlay_receipt_ref JSON,
            CHECK ({_EPOCH_STATE_PREDICATE})
        )
        """
    )
    try:
        rows = con.execute(
            "SELECT constraint_text FROM duckdb_constraints() "
            "WHERE table_name = ? AND constraint_type = 'CHECK'",
            [table],
        ).fetchall()
    finally:
        con.execute(f"DROP TABLE {table}")
    if len(rows) != 1:
        raise OverlayAdmissionError("epoch_state_constraint_normalization_failed")
    return str(rows[0][0])


def _derive_baseline_primary_key_spec(
    con: duckdb.DuckDBPyConnection,
) -> dict[str, tuple[str, ...]]:
    """Derive the exact live six-table native-key denominator from owner metadata."""

    rows = con.execute(
        """
        SELECT table_name, constraint_type, constraint_column_names
        FROM duckdb_constraints()
        WHERE database_name = 'baseline'
          AND constraint_type IN ('PRIMARY KEY', 'UNIQUE')
          AND list_contains(?, table_name)
        ORDER BY table_name, CASE constraint_type WHEN 'PRIMARY KEY' THEN 0 ELSE 1 END
        """,
        [list(_BASELINE_UNION_TABLES)],
    ).fetchall()
    grouped: dict[str, list[tuple[str, tuple[str, ...]]]] = {}
    for table, constraint_type, columns in rows:
        grouped.setdefault(str(table), []).append(
            (str(constraint_type), tuple(str(value) for value in columns))
        )
    missing = sorted(set(_BASELINE_UNION_TABLES) - set(grouped))
    selected: dict[str, tuple[str, ...]] = {}
    ambiguous: list[str] = []
    for table, candidates in grouped.items():
        primary = [columns for kind, columns in candidates if kind == "PRIMARY KEY"]
        unique = [columns for kind, columns in candidates if kind == "UNIQUE"]
        chosen = primary or unique
        if len(chosen) != 1:
            ambiguous.append(table)
        else:
            selected[table] = chosen[0]
    if missing or ambiguous:
        raise OverlayAdmissionError(
            "baseline_native_key_denominator_unresolved",
            json.dumps({"missing": missing, "ambiguous": ambiguous}, sort_keys=True),
        )
    return {table: selected[table] for table in _BASELINE_UNION_TABLES}


def _canonical_primary_key_bytes(
    *, table: str, columns: tuple[str, ...], values: Mapping[str, object]
) -> bytes:
    missing = [column for column in columns if column not in values]
    if missing:
        raise OverlayAdmissionError(
            "overlay_native_key_value_missing",
            f"{table}:{','.join(missing)}",
        )
    parts = [table]
    parts.extend(
        f"{column}={str(values[column]).encode('utf-8').hex().upper()}" for column in columns
    )
    return "|".join(parts).encode("ascii")


def _sql_member_key_hash(*, table: str, columns: tuple[str, ...], alias: str) -> str:
    return (
        "'sha256:' || sha256("
        + _sql_member_key_text(table=table, columns=columns, alias=alias)
        + ")"
    )


def _sql_member_key_bytes(*, table: str, columns: tuple[str, ...], alias: str) -> str:
    return "encode(" + _sql_member_key_text(table=table, columns=columns, alias=alias) + ")"


def _sql_member_key_text(*, table: str, columns: tuple[str, ...], alias: str) -> str:
    pieces = [f"'{table}'"]
    for column in columns:
        if not column.replace("_", "").isalnum():
            raise OverlayAdmissionError("baseline_native_key_identifier_invalid", column)
        pieces.extend(
            [
                "'|'",
                f"'{column}='",
                f"upper(hex(encode(cast({alias}.{column} AS VARCHAR))))",
            ]
        )
    return "concat(" + ", ".join(pieces) + ")"


def _insert_epoch_members(
    con: duckdb.DuckDBPyConnection,
    *,
    epoch_id: int,
    passport_id: str,
    registration: AcquisitionDatasetRegistration,
    observations: Sequence[CanonicalAcquisitionObservation],
) -> tuple[tuple[epoch_contract.OverlayNativeMemberKey, ...], str]:
    spec = _derive_baseline_primary_key_spec(con)
    binding = registration.field_binding
    rows: dict[str, tuple[Mapping[str, object], ...]] = {
        "ds_datasets": ({"id": registration.catalog_dataset_id},),
        "ds_distributions": ({"id": registration.distribution_id},),
        "ds_metric_bindings": (
            {
                "metric_id": registration.metric_id,
                "dataset_id": registration.catalog_dataset_id,
                "distribution_id": registration.distribution_id,
            },
        ),
        "ds_observations": tuple({"observation_id": row.observation_id} for row in observations),
        "ds_schema_profiles": ({"distribution_id": registration.distribution_id},),
        "ds_variable_alignments": (
            {
                "dataset_id": registration.catalog_dataset_id,
                "raw_variable": binding.raw_field,
                "canonical_var": binding.canonical_variable,
            },
        ),
    }
    if set(rows) != set(_BASELINE_UNION_TABLES):
        raise OverlayAdmissionError("overlay_member_table_denominator_mismatch")
    encoded: list[tuple[str, bytes, str]] = []
    for table in _BASELINE_UNION_TABLES:
        for values in rows[table]:
            key_bytes = _canonical_primary_key_bytes(
                table=table,
                columns=spec[table],
                values=values,
            )
            encoded.append((table, key_bytes, f"sha256:{hashlib.sha256(key_bytes).hexdigest()}"))
    con.executemany(
        """
        INSERT INTO acquisition_epoch_members
        (table_name, canonical_primary_key_bytes, canonical_primary_key_hash, epoch_id, passport_id)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT DO NOTHING
        """,
        [
            [table, key_bytes, key_hash, epoch_id, passport_id]
            for table, key_bytes, key_hash in encoded
        ],
    )
    actual = con.execute(
        """
        SELECT table_name, canonical_primary_key_hash
        FROM acquisition_epoch_members
        WHERE epoch_id = ? AND passport_id = ?
        ORDER BY table_name, canonical_primary_key_hash
        """,
        [epoch_id, passport_id],
    ).fetchall()
    expected = tuple(sorted((table, key_hash) for table, _, key_hash in encoded))
    if tuple((str(table), str(key_hash)) for table, key_hash in actual) != expected:
        raise OverlayAdmissionError("overlay_member_denominator_incomplete")
    denominator_raw = epoch_contract.canonical_epoch_bytes(
        {"epoch_id": epoch_id, "passport_id": passport_id, "members": expected}
    )
    member_keys = tuple(
        epoch_contract.OverlayNativeMemberKey(
            table_name=table,
            canonical_primary_key_hash=key_hash,
        )
        for table, key_hash in expected
    )
    return member_keys, f"sha256:{hashlib.sha256(denominator_raw).hexdigest()}"


def _existing_member_denominator(
    overlay_path: Path, *, epoch_id: int, passport_id: str
) -> tuple[tuple[epoch_contract.OverlayNativeMemberKey, ...], str]:
    con = duckdb.connect(str(overlay_path), read_only=True)
    try:
        rows = con.execute(
            """
            SELECT table_name, canonical_primary_key_hash
            FROM acquisition_epoch_members
            WHERE epoch_id = ? AND passport_id = ?
            ORDER BY table_name, canonical_primary_key_hash
            """,
            [epoch_id, passport_id],
        ).fetchall()
    finally:
        con.close()
    tables = {str(row[0]) for row in rows}
    if tables != set(_BASELINE_UNION_TABLES):
        raise OverlayAdmissionError("overlay_member_denominator_incomplete")
    normalized = tuple((str(table), str(key_hash)) for table, key_hash in rows)
    raw = epoch_contract.canonical_epoch_bytes(
        {"epoch_id": epoch_id, "passport_id": passport_id, "members": normalized}
    )
    member_keys = tuple(
        epoch_contract.OverlayNativeMemberKey(
            table_name=table,
            canonical_primary_key_hash=key_hash,
        )
        for table, key_hash in normalized
    )
    return member_keys, f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _native_mapping_member_denominator(
    mapping: Mapping[str, object],
    *,
    epoch_id: int,
    passport_id: str,
) -> tuple[tuple[epoch_contract.OverlayNativeMemberKey, ...], str]:
    """Recompute a persisted native snapshot's relation-key denominator."""

    raw_members = mapping.get("members")
    if not isinstance(raw_members, list):
        raise OverlayAdmissionError("admitted_native_member_list_missing")
    member_keys: list[epoch_contract.OverlayNativeMemberKey] = []
    for raw_member in raw_members:
        if not isinstance(raw_member, dict) or set(raw_member) != {
            "table_name",
            "canonical_primary_key_bytes",
            "canonical_primary_key_hash",
        }:
            raise OverlayAdmissionError("admitted_native_member_shape_invalid")
        member_keys.append(
            epoch_contract.OverlayNativeMemberKey(
                table_name=str(raw_member["table_name"]),
                canonical_primary_key_hash=str(raw_member["canonical_primary_key_hash"]),
            )
        )
    ordered = tuple(member_keys)
    if tuple(sorted(ordered, key=lambda row: (row.table_name, row.canonical_primary_key_hash))) != (
        ordered
    ):
        raise OverlayAdmissionError("admitted_native_member_order_invalid")
    raw = epoch_contract.canonical_epoch_bytes(
        {
            "epoch_id": epoch_id,
            "passport_id": passport_id,
            "members": [(row.table_name, row.canonical_primary_key_hash) for row in ordered],
        }
    )
    return ordered, f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _reconcile_physical_epoch_members(
    con: duckdb.DuckDBPyConnection,
    *,
    member_rows: Sequence[tuple[object, ...]],
    key_spec: Mapping[str, tuple[str, ...]],
) -> None:
    """Require every owner relation key to resolve to one physical native row."""

    tables = {str(row[0]) for row in member_rows}
    if tables != set(_BASELINE_UNION_TABLES):
        raise OverlayAdmissionError("overlay_member_denominator_incomplete")
    for raw_table, raw_key_bytes, raw_key_hash in member_rows:
        table = str(raw_table)
        if table not in _BASELINE_UNION_TABLES or table not in key_spec:
            raise OverlayAdmissionError("overlay_member_table_unregistered", table)
        key_bytes_sql = _sql_member_key_bytes(
            table=table,
            columns=key_spec[table],
            alias="native_row",
        )
        key_hash_sql = _sql_member_key_hash(
            table=table,
            columns=key_spec[table],
            alias="native_row",
        )
        count = con.execute(
            f"SELECT count(*) FROM {table} AS native_row "  # noqa: S608
            f"WHERE {key_bytes_sql} = ? AND {key_hash_sql} = ?",
            [bytes(raw_key_bytes), str(raw_key_hash)],
        ).fetchone()
        if count is None or int(count[0]) != 1:
            raise OverlayAdmissionError(
                "overlay_native_member_physical_row_mismatch",
                f"{table}:{raw_key_hash}",
            )


def _require_exact_projection_row(
    con: duckdb.DuckDBPyConnection,
    *,
    table: str,
    columns: tuple[str, ...],
    key_column: str,
    key: object,
    expected: tuple[object, ...],
) -> None:
    """Reject reused metadata whose physical owner row drifted in place."""

    if table not in {*_BASELINE_UNION_TABLES, "ds_metric_field_bindings"}:
        raise OverlayAdmissionError("overlay_registration_projection_table_unowned", table)
    if key_column not in columns:
        raise OverlayAdmissionError("overlay_registration_projection_key_unbound", table)
    selected = ", ".join(columns)
    rows = con.execute(
        f"SELECT {selected} FROM {table} WHERE {key_column} = ?",  # noqa: S608
        [key],
    ).fetchall()
    if len(rows) != 1:
        raise OverlayAdmissionError(
            "overlay_registration_physical_projection_conflict",
            f"{table}:row_denominator",
        )
    observed = tuple(rows[0])
    for column, actual, wanted in zip(columns, observed, expected, strict=True):
        same = (
            abs(float(actual) - float(wanted)) <= 1e-6
            if isinstance(actual, int | float | Decimal)
            and not isinstance(actual, bool)
            and isinstance(wanted, int | float | Decimal)
            and not isinstance(wanted, bool)
            else actual == wanted
        )
        if not same:
            raise OverlayAdmissionError(
                "overlay_registration_physical_projection_conflict",
                f"{table}:{column}",
            )


def _require_reused_registration_projection(
    con: duckdb.DuckDBPyConnection,
    *,
    registration: AcquisitionDatasetRegistration,
) -> None:
    """Recompute all creator-owned metadata projections before row reuse."""

    creator = con.execute(
        "SELECT epoch_id, passport_id FROM ds_metric_field_bindings WHERE binding_id = ?",
        [registration.field_binding.binding_id],
    ).fetchall()
    if len(creator) != 1:
        raise OverlayAdmissionError("overlay_registration_creator_not_established")
    creator_epoch_id, creator_passport_id = int(creator[0][0]), str(creator[0][1])
    persisted = con.execute(
        "SELECT passport_content_sha256, passport_json FROM acquisition_passports "
        "WHERE epoch_id = ? AND passport_id = ?",
        [creator_epoch_id, creator_passport_id],
    ).fetchall()
    if len(persisted) != 1:
        raise OverlayAdmissionError("overlay_registration_creator_passport_not_established")
    try:
        passport = json.loads(str(persisted[0][1]))
        if (
            not isinstance(passport, dict)
            or content_sha256(passport) != str(persisted[0][0])
            or AcquisitionDatasetRegistration.model_validate(passport["registration"])
            != registration
        ):
            raise ValueError("creator passport differs")
        profile = passport["measured_profile"]
        l5 = passport["l5_trust"]
        if not isinstance(profile, dict) or not isinstance(l5, dict):
            raise ValueError("creator projection sources are not mappings")
        binding = registration.field_binding
        score = round(
            min(
                float(l5["trust_cap"]),
                binding.calibrated_alignment_confidence
                * (1.0 - binding.proxy_penalty if binding.is_proxy else 1.0)
                * float(l5["trust_multiplier"]),
            ),
            6,
        )
        columns_json = profile["columns"]
        if not isinstance(columns_json, list):
            raise ValueError("creator schema columns are not a list")
    except (KeyError, TypeError, ValueError) as exc:
        raise OverlayAdmissionError("overlay_registration_creator_projection_invalid") from exc

    dataset_columns = (
        "id",
        "source",
        "agency",
        "dataset_id",
        "source_dataset_id",
        "dedup_key",
        "title",
        "description",
        "publisher",
        "spatial",
        "temporal_start",
        "temporal_end",
        "license",
        "source_portal",
        "execution_tier",
        "update_frequency",
        "last_updated",
        "polisyos_metrics",
        "keywords",
        "themes",
        "variables",
        "formats",
        "coverage_countries",
        "coverage_regions",
        "coverage_time_start",
        "coverage_time_end",
        "coverage_granularity",
        "access_api_endpoint",
        "access_bulk_download_url",
        "access_license",
        "access_auth_required",
        "quality_description_score",
        "quality_machine_readable_score",
        "quality_parser_support_score",
        "quality_freshness_score",
        "quality_execution_readiness_score",
        "preferred_distribution_id",
    )
    _require_exact_projection_row(
        con,
        table="ds_datasets",
        columns=dataset_columns,
        key_column="id",
        key=registration.catalog_dataset_id,
        expected=(
            registration.catalog_dataset_id,
            registration.source,
            registration.agency,
            registration.request_dataset_id,
            registration.request_dataset_id,
            registration.catalog_dataset_id,
            registration.title,
            registration.description,
            registration.agency,
            ",".join(registration.country_codes),
            registration.temporal_start,
            registration.temporal_end,
            registration.access_license,
            registration.source_locator,
            registration.execution_tier,
            "acquisition_epoch",
            registration.temporal_end,
            [registration.metric_id],
            ["acquisition", "owner_validated"],
            ["acquisition"],
            [binding.raw_field],
            ["overlay"],
            list(registration.country_codes),
            [],
            registration.temporal_start,
            registration.temporal_end,
            "owner_declared",
            None,
            None,
            registration.access_license,
            False,
            score,
            score,
            score,
            score,
            score,
            registration.distribution_id,
        ),
    )
    _require_exact_projection_row(
        con,
        table="ds_distributions",
        columns=(
            "id",
            "dataset_id",
            "url",
            "format",
            "name",
            "connector_type",
            "connector_params",
            "source_locator",
            "profile_id",
            "media_type",
            "machine_readable",
            "parser_supported",
            "size_estimate_bytes",
            "checksum",
            "default_filters",
            "quality_score",
        ),
        key_column="id",
        key=registration.distribution_id,
        expected=(
            registration.distribution_id,
            registration.catalog_dataset_id,
            registration.source_locator,
            "overlay",
            registration.title,
            registration.connector_id,
            json.dumps({}),
            registration.source_locator,
            registration.source_profile_id,
            "application/vnd.apache.parquet",
            True,
            True,
            None,
            str(passport["raw_artifact_id"]),
            json.dumps({}),
            score,
        ),
    )
    _require_exact_projection_row(
        con,
        table="ds_metric_bindings",
        columns=(
            "metric_id",
            "dataset_id",
            "distribution_id",
            "connector_id",
            "profile_id",
            "request_dataset_id",
            "confidence",
            "metric_inference_confidence",
            "default_filters",
            "execution_tier",
            "source",
        ),
        key_column="metric_id",
        key=registration.metric_id,
        expected=(
            registration.metric_id,
            registration.catalog_dataset_id,
            registration.distribution_id,
            registration.connector_id,
            registration.source_profile_id,
            registration.request_dataset_id,
            score,
            score,
            json.dumps({}),
            registration.execution_tier,
            registration.source,
        ),
    )
    _require_exact_projection_row(
        con,
        table="ds_schema_profiles",
        columns=(
            "distribution_id",
            "dataset_id",
            "columns_json",
            "inferred_time_column",
            "inferred_geography_column",
            "inferred_value_columns",
            "sample_row_count",
            "preview_sample_hash",
            "inference_mode",
            "parser_mode",
            "format_notes_json",
        ),
        key_column="distribution_id",
        key=registration.distribution_id,
        expected=(
            registration.distribution_id,
            registration.catalog_dataset_id,
            json.dumps(columns_json),
            "year" if any(row.get("name") == "year" for row in columns_json) else None,
            (
                "country_code"
                if any(row.get("name") == "country_code" for row in columns_json)
                else None
            ),
            [binding.raw_field],
            int(profile["sample_row_count"]),
            str(profile["sample_content_sha256"]),
            "measured_quarantine",
            "acquisition_passport",
            json.dumps({"passport_id": creator_passport_id}),
        ),
    )
    _require_exact_projection_row(
        con,
        table="ds_variable_alignments",
        columns=(
            "dataset_id",
            "raw_variable",
            "canonical_var",
            "method",
            "confidence",
            "evidence",
            "is_proxy",
            "proxy_penalty",
        ),
        key_column="dataset_id",
        key=registration.catalog_dataset_id,
        expected=(
            registration.catalog_dataset_id,
            binding.raw_field,
            binding.canonical_variable,
            binding.alignment_method,
            binding.calibrated_alignment_confidence,
            ";".join(binding.evidence_refs),
            binding.is_proxy,
            binding.proxy_penalty,
        ),
    )
    _require_exact_projection_row(
        con,
        table="ds_metric_field_bindings",
        columns=(
            "binding_id",
            "epoch_id",
            "dataset_id",
            "distribution_id",
            "raw_field",
            "canonical_variable",
            "raw_unit",
            "canonical_unit",
            "unit_transform",
            "unit_transform_ref",
            "alignment_method",
            "alignment_confidence",
            "calibrated_alignment_confidence",
            "is_proxy",
            "proxy_penalty",
            "aggregation_method",
            "evidence_refs",
            "passport_id",
            "effective_authority_score",
        ),
        key_column="binding_id",
        key=binding.binding_id,
        expected=(
            binding.binding_id,
            creator_epoch_id,
            binding.dataset_id,
            binding.distribution_id,
            binding.raw_field,
            binding.canonical_variable,
            binding.raw_unit,
            binding.canonical_unit,
            binding.unit_transform,
            binding.unit_transform_ref,
            binding.alignment_method,
            binding.alignment_confidence,
            binding.calibrated_alignment_confidence,
            binding.is_proxy,
            binding.proxy_penalty,
            binding.aggregation_method,
            json.dumps(list(binding.evidence_refs)),
            creator_passport_id,
            score,
        ),
    )


def _insert_registration(
    con: duckdb.DuckDBPyConnection,
    registration: AcquisitionDatasetRegistration,
    passport: _Passport,
) -> None:
    registration_payload = registration.model_dump(mode="json")
    registration_hash = content_sha256(registration_payload)
    existing = con.execute(
        "SELECT registration_content_sha256 FROM acquisition_registrations "
        "WHERE catalog_dataset_id = ?",
        [registration.catalog_dataset_id],
    ).fetchone()
    if existing is not None:
        if str(existing[0]) != registration_hash:
            raise OverlayAdmissionError(
                "overlay_registration_content_conflict",
                registration.catalog_dataset_id,
            )
        _require_reused_registration_projection(con, registration=registration)
        return
    con.execute(
        "INSERT INTO acquisition_registrations VALUES (?, ?, ?)",
        [
            registration.catalog_dataset_id,
            registration_hash,
            json.dumps(registration_payload),
        ],
    )
    binding = registration.field_binding
    effective_authority_score = _effective_authority_score(passport)
    con.execute(
        """
        INSERT INTO ds_datasets (
            id, source, agency, dataset_id, source_dataset_id, dedup_key,
            title, description, publisher, spatial, temporal_start, temporal_end,
            license, source_portal, execution_tier, update_frequency, last_updated,
            polisyos_metrics, keywords, themes, variables, formats,
            coverage_countries, coverage_regions, coverage_time_start,
            coverage_time_end, coverage_granularity, access_api_endpoint,
            access_bulk_download_url, access_license, access_auth_required,
            quality_description_score, quality_machine_readable_score,
            quality_parser_support_score, quality_freshness_score,
            quality_execution_readiness_score, preferred_distribution_id
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        [
            registration.catalog_dataset_id,
            registration.source,
            registration.agency,
            registration.request_dataset_id,
            registration.request_dataset_id,
            registration.catalog_dataset_id,
            registration.title,
            registration.description,
            registration.agency,
            ",".join(registration.country_codes),
            registration.temporal_start,
            registration.temporal_end,
            registration.access_license,
            registration.source_locator,
            registration.execution_tier,
            "acquisition_epoch",
            registration.temporal_end,
            [registration.metric_id],
            ["acquisition", "owner_validated"],
            ["acquisition"],
            [binding.raw_field],
            ["overlay"],
            list(registration.country_codes),
            [],
            registration.temporal_start,
            registration.temporal_end,
            "owner_declared",
            None,
            None,
            registration.access_license,
            False,
            effective_authority_score,
            effective_authority_score,
            effective_authority_score,
            effective_authority_score,
            effective_authority_score,
            registration.distribution_id,
        ],
    )
    con.execute(
        """
        INSERT INTO ds_distributions (
            id, dataset_id, url, format, name, connector_type, connector_params,
            source_locator, profile_id, media_type, machine_readable,
            parser_supported, size_estimate_bytes, checksum, default_filters,
            quality_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            registration.distribution_id,
            registration.catalog_dataset_id,
            registration.source_locator,
            "overlay",
            registration.title,
            registration.connector_id,
            json.dumps({}),
            registration.source_locator,
            registration.source_profile_id,
            "application/vnd.apache.parquet",
            True,
            True,
            None,
            str(passport.raw_artifact_id),
            json.dumps({}),
            effective_authority_score,
        ],
    )
    con.execute(
        "INSERT INTO ds_metric_bindings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            registration.metric_id,
            registration.catalog_dataset_id,
            registration.distribution_id,
            registration.connector_id,
            registration.source_profile_id,
            registration.request_dataset_id,
            effective_authority_score,
            effective_authority_score,
            json.dumps({}),
            registration.execution_tier,
            registration.source,
        ],
    )
    profile = passport.measured_profile
    columns_json = [column.model_dump(mode="json") for column in getattr(profile, "columns", ())]
    con.execute(
        "INSERT INTO ds_schema_profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            registration.distribution_id,
            registration.catalog_dataset_id,
            json.dumps(columns_json),
            "year" if any(row.get("name") == "year" for row in columns_json) else None,
            "country_code"
            if any(row.get("name") == "country_code" for row in columns_json)
            else None,
            [binding.raw_field],
            int(profile.sample_row_count),
            str(profile.sample_content_sha256),
            "measured_quarantine",
            "acquisition_passport",
            json.dumps({"passport_id": passport.passport_id}),
        ],
    )
    con.execute(
        "INSERT INTO ds_variable_alignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            registration.catalog_dataset_id,
            binding.raw_field,
            binding.canonical_variable,
            binding.alignment_method,
            binding.calibrated_alignment_confidence,
            ";".join(binding.evidence_refs),
            binding.is_proxy,
            binding.proxy_penalty,
        ],
    )
    con.execute(
        (
            "INSERT INTO ds_metric_field_bindings VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        [
            binding.binding_id,
            int(passport.epoch_id),
            binding.dataset_id,
            binding.distribution_id,
            binding.raw_field,
            binding.canonical_variable,
            binding.raw_unit,
            binding.canonical_unit,
            binding.unit_transform,
            binding.unit_transform_ref,
            binding.alignment_method,
            binding.alignment_confidence,
            binding.calibrated_alignment_confidence,
            binding.is_proxy,
            binding.proxy_penalty,
            binding.aggregation_method,
            json.dumps(list(binding.evidence_refs)),
            str(passport.passport_id),
            effective_authority_score,
        ],
    )


def _insert_observations(
    con: duckdb.DuckDBPyConnection,
    observations: Sequence[CanonicalAcquisitionObservation],
    *,
    epoch_id: int,
    passport: _Passport,
) -> None:
    _insert_schema_projected_rows(
        con,
        table="ds_observations",
        rows=[
            {
                "observation_id": row.observation_id,
                "dataset_id": row.dataset_id,
                "raw_variable": row.raw_variable,
                "canonical_var": row.canonical_var,
                "country_code": row.country_code,
                "year": row.year,
                "survey_year": row.survey_year,
                "wave": row.wave,
                "value": row.value,
                "condition_json": row.condition_json,
                "acquisition_method": row.acquisition_method,
                "source_watermark": row.source_watermark,
                "dataset_version": row.dataset_version,
            }
            for row in observations
        ],
    )
    con.executemany(
        "INSERT INTO acquisition_observation_provenance VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            [
                row.observation_id,
                epoch_id,
                str(passport.passport_id),
                row.observation_class.value,
                passport.raw_evidence_ref.event_sha256,
                str(passport.raw_artifact_id),
                str(passport.l5_trust.tier),
                _effective_authority_score(passport),
            ]
            for row in observations
        ],
    )


def _insert_schema_projected_rows(
    con: duckdb.DuckDBPyConnection,
    *,
    table: str,
    rows: Sequence[Mapping[str, object]],
) -> None:
    """Insert the intersection with the attached baseline table schema."""

    if table not in _BASELINE_UNION_TABLES:
        raise OverlayAdmissionError("overlay_table_not_owned", table)
    available = tuple(
        str(row[1]) for row in con.execute(f"PRAGMA table_info('{table}')").fetchall()
    )
    if table == "ds_observations":
        missing = sorted(_OBSERVATION_DECISIVE_COLUMNS - set(available))
        if missing or not {"year", "survey_year", "wave"} & set(available):
            raise OverlayAdmissionError(
                "overlay_observation_schema_incomplete",
                ",".join(missing or ["year|survey_year|wave"]),
            )
    columns = tuple(column for column in available if all(column in row for row in rows))
    if not columns:
        raise OverlayAdmissionError("overlay_schema_projection_empty", table)
    column_sql = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    statement = f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})"  # noqa: S608
    con.executemany(statement, [[row[column] for column in columns] for row in rows])


def _baseline_identity(path: Path) -> BaselineIdentity:
    if not path.is_file():
        raise BaselineMutationError("baseline_catalog_missing", path.as_posix())
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return BaselineIdentity(
        source_path=path.as_posix(),
        content_sha256=f"sha256:{digest.hexdigest()}",
        byte_size=path.stat().st_size,
        epoch=0,
    )


def _effective_authority_score(passport: _Passport) -> float:
    binding = passport.field_binding
    l5 = passport.l5_trust
    alignment = float(binding.calibrated_alignment_confidence)
    proxy_factor = 1.0 - float(binding.proxy_penalty) if binding.is_proxy else 1.0
    l5_cap = float(getattr(l5, "trust_cap", 0.0))
    l5_multiplier = float(getattr(l5, "trust_multiplier", 0.0))
    return round(min(l5_cap, alignment * proxy_factor * l5_multiplier), 6)


def _attach_read_only(con: duckdb.DuckDBPyConnection, path: Path, *, alias: str) -> None:
    escaped = path.as_posix().replace("'", "''")
    con.execute(f"ATTACH '{escaped}' AS {alias} (READ_ONLY)")


def _require_attached_tables(
    con: duckdb.DuckDBPyConnection,
    *,
    alias: str,
    expected: Sequence[str],
    error_code: str,
) -> None:
    available = {str(row[0]) for row in con.execute(f"SHOW TABLES FROM {alias}").fetchall()}
    missing = sorted(set(expected) - available)
    if missing:
        raise OverlayAdmissionError(error_code, ",".join(missing))


def _require_overlay_baseline_identity(
    con: duckdb.DuckDBPyConnection,
    baseline: BaselineIdentity,
    overlay_path: Path,
) -> None:
    rows = con.execute(
        "SELECT schema_version, baseline_content_sha256, baseline_byte_size "
        "FROM acquisition_overlay.acquisition_overlay_metadata"
    ).fetchall()
    expected = (
        OVERLAY_SCHEMA_VERSION,
        baseline.content_sha256,
        baseline.byte_size,
    )
    if len(rows) != 1 or tuple(rows[0]) != expected:
        raise BaselineMutationError(
            "overlay_baseline_identity_mismatch",
            overlay_path.as_posix(),
        )


def _require_overlay_epoch_contract(con: duckdb.DuckDBPyConnection) -> None:
    """Reject attached overlays whose v2 state machine is only nominal."""

    columns = tuple(
        (str(name), str(data_type), str(nullable))
        for name, data_type, nullable in con.execute(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_catalog = 'acquisition_overlay' "
            "AND table_schema = 'main' AND table_name = 'acquisition_epochs' "
            "ORDER BY ordinal_position"
        ).fetchall()
    )
    if columns != _ACQUISITION_EPOCH_COLUMNS:
        raise OverlayAdmissionError("overlay_epoch_schema_contract_incomplete")
    checks = tuple(
        str(row[0])
        for row in con.execute(
            "SELECT constraint_text FROM duckdb_constraints() "
            "WHERE database_name = 'acquisition_overlay' "
            "AND schema_name = 'main' AND table_name = 'acquisition_epochs' "
            "AND constraint_type = 'CHECK'"
        ).fetchall()
    )
    expected_constraint = _expected_epoch_state_constraint_text(con)
    if expected_constraint not in checks:
        raise OverlayAdmissionError("overlay_epoch_state_constraint_not_established")
    invalid = con.execute(
        f"""
        SELECT epoch_id FROM acquisition_overlay.acquisition_epochs
        WHERE NOT ({_EPOCH_STATE_PREDICATE})
        LIMIT 1
        """  # noqa: S608 -- one module-owned invariant, not caller SQL.
    ).fetchone()
    if invalid is not None:
        raise OverlayAdmissionError("overlay_epoch_state_constraint_violated", str(invalid[0]))


def _require_epoch_member_contract(
    con: duckdb.DuckDBPyConnection,
    *,
    database_name: str,
) -> None:
    """Require the exact physical owner relation used by every native row."""

    columns = tuple(
        (str(name), str(data_type), str(nullable))
        for name, data_type, nullable in con.execute(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_catalog = ? AND table_schema = 'main' "
            "AND table_name = 'acquisition_epoch_members' "
            "ORDER BY ordinal_position",
            [database_name],
        ).fetchall()
    )
    if columns != _EPOCH_MEMBER_COLUMNS:
        raise OverlayAdmissionError("overlay_epoch_member_schema_contract_incomplete")
    unique_denominator = tuple(
        tuple(str(column) for column in columns)
        for (columns,) in con.execute(
            "SELECT constraint_column_names FROM duckdb_constraints() "
            "WHERE database_name = ? AND schema_name = 'main' "
            "AND table_name = 'acquisition_epoch_members' "
            "AND constraint_type = 'UNIQUE'",
            [database_name],
        ).fetchall()
    )
    if unique_denominator != (_EPOCH_MEMBER_UNIQUE,):
        raise OverlayAdmissionError("overlay_epoch_member_unique_not_established")


def _existing_epoch(path: Path, epoch_id: int) -> tuple[str, str, object | None] | None:
    con = duckdb.connect(str(path), read_only=True)
    try:
        row = con.execute(
            "SELECT admission_content_sha256, epoch_activation_state, "
            "pending_overlay_receipt_ref FROM acquisition_epochs WHERE epoch_id = ?",
            [epoch_id],
        ).fetchone()
    finally:
        con.close()
    return None if row is None else (str(row[0]), str(row[1]), row[2])


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _model_json(value: object) -> dict[str, Any]:
    model_dump = getattr(value, "model_dump", None)
    if not callable(model_dump):
        raise OverlayAdmissionError("passport_model_surface_missing")
    payload = model_dump(mode="json")
    if not isinstance(payload, dict):
        raise OverlayAdmissionError("passport_payload_invalid")
    return payload


def _model_json_value(value: object) -> object:
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="json")
    if isinstance(value, tuple | list):
        return [_model_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _model_json_value(item) for key, item in value.items()}
    return getattr(value, "value", value)


__all__ = [
    "DEFAULT_ACQUISITION_OVERLAY_PATH",
    "OVERLAY_SCHEMA_VERSION",
    "AcquisitionDatasetRegistration",
    "BaselineIdentity",
    "BaselineMutationError",
    "CanonicalAcquisitionObservation",
    "CatalogAcquisitionEpochProjection",
    "CatalogAcquisitionEventProjection",
    "CatalogAcquisitionOverlay",
    "CatalogAcquisitionPassportProjection",
    "CatalogAcquisitionStateProjection",
    "MetricFieldBinding",
    "ObservationProvenanceClass",
    "OverlayAdmissionError",
    "OverlayAdmissionReceipt",
    "build_metric_field_binding",
    "default_acquisition_overlay_path",
    "derive_canonical_observations",
    "open_catalog_read_session",
    "project_catalog_acquisition_state",
    "validate_overlay_admission_receipt",
]
