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
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Protocol, Self

import duckdb
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core import artifacts, scan_secret_and_pii
from polisyos.fabric import data_plane as fabric_data_plane

ArtifactID = artifacts.ArtifactID
JournalEventRef = fabric_data_plane.JournalEventRef
content_sha256 = fabric_data_plane.content_sha256
resolve_raw_response_body = fabric_data_plane.resolve_raw_response_body
resolve_linked_request_event = fabric_data_plane.resolve_linked_request_event

OVERLAY_SCHEMA_VERSION = "polisyos.data_forge.acquisition_overlay.v1"
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
            self.raw_field != self.canonical_variable
            or abs(self.alignment_confidence - 1.0) > 1e-9
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
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "binding_id"
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


class OverlayAdmissionReceipt(_StrictModel):
    """Content-bound receipt for one idempotent overlay epoch transaction."""

    schema_version: Literal[OVERLAY_SCHEMA_VERSION] = OVERLAY_SCHEMA_VERSION
    epoch_id: int = Field(gt=0)
    passport_id: str = Field(min_length=1)
    admission_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    admitted_observation_count: int = Field(gt=0)
    observation_class: ObservationProvenanceClass
    effective_authority_score: float = Field(ge=0.0, le=1.0)
    baseline_before_sha256: str = Field(pattern=_SHA256_PATTERN)
    baseline_after_sha256: str = Field(pattern=_SHA256_PATTERN)
    replayed: bool


class _ArtifactStore(Protocol):
    def has(self, artifact_id: ArtifactID) -> bool: ...

    def get_bytes(self, artifact_id: ArtifactID) -> bytes: ...


class _CanonicalAuthority(Protocol):
    def resolve(self, entry_id: str) -> object: ...

    def verify_source_body(self, entry_id: str, body: bytes) -> bool: ...


class _Passport(Protocol):
    epoch_id: int
    passport_id: str
    status: object
    observation_class: object
    variable_id: str
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
    source_authority_verified: bool

    def recomputed_passport_id(self) -> str: ...

    def recomputed_rejection_codes(self) -> tuple[str, ...]: ...

    def model_dump(self, *, mode: str) -> dict[str, Any]: ...


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
                str(row[0])
                for row in con.execute("show tables from baseline").fetchall()
            }
            missing = sorted(set(_BASELINE_UNION_TABLES) - baseline_tables)
            if missing:
                raise OverlayAdmissionError(
                    "baseline_catalog_contract_incomplete",
                    ",".join(missing),
                )
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
                """
                CREATE TABLE IF NOT EXISTS acquisition_epochs (
                    epoch_id BIGINT PRIMARY KEY,
                    passport_id VARCHAR NOT NULL,
                    admission_content_sha256 VARCHAR NOT NULL,
                    baseline_content_sha256 VARCHAR NOT NULL,
                    admitted_observation_count BIGINT NOT NULL,
                    observation_class VARCHAR NOT NULL
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
                "SELECT baseline_content_sha256, baseline_byte_size "
                "FROM acquisition_overlay_metadata WHERE schema_version = ?",
                [OVERLAY_SCHEMA_VERSION],
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
            elif rows[0] != (
                self._baseline_identity.content_sha256,
                self._baseline_identity.byte_size,
            ):
                raise BaselineMutationError(
                    "overlay_baseline_identity_mismatch",
                    self.overlay_path.as_posix(),
                )
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
        artifact_store: _ArtifactStore,
        authority: _CanonicalAuthority,
    ) -> OverlayAdmissionReceipt:
        """Revalidate owners, then atomically append one observed/proxy epoch."""

        if not self._initialized:
            raise OverlayAdmissionError("overlay_not_initialized")
        before = self._require_baseline_unchanged()
        raw_body = _validate_passport_owner_evidence(
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
        observation_class = ObservationProvenanceClass(
            _enum_value(passport.observation_class)
        )
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
            raw_body,
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
        }
        admission_hash = content_sha256(admission_projection)
        effective_authority_score = _effective_authority_score(passport)
        existing = _existing_epoch(self.overlay_path, epoch_id)
        if existing is not None:
            if existing[0] != admission_hash:
                raise OverlayAdmissionError("epoch_content_conflict", str(epoch_id))
            after = self._require_baseline_unchanged()
            return OverlayAdmissionReceipt(
                epoch_id=epoch_id,
                passport_id=passport_id,
                admission_content_sha256=admission_hash,
                admitted_observation_count=len(rows),
                observation_class=observation_class,
                effective_authority_score=effective_authority_score,
                baseline_before_sha256=before.content_sha256,
                baseline_after_sha256=after.content_sha256,
                replayed=True,
            )

        con = duckdb.connect(str(self.overlay_path))
        try:
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
            con.execute(
                "INSERT INTO acquisition_epochs VALUES (?, ?, ?, ?, ?, ?)",
                [
                    epoch_id,
                    passport_id,
                    admission_hash,
                    before.content_sha256,
                    len(rows),
                    observation_class.value,
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
        after = self._require_baseline_unchanged()
        return OverlayAdmissionReceipt(
            epoch_id=epoch_id,
            passport_id=passport_id,
            admission_content_sha256=admission_hash,
            admitted_observation_count=len(rows),
            observation_class=observation_class,
            effective_authority_score=effective_authority_score,
            baseline_before_sha256=before.content_sha256,
            baseline_after_sha256=after.content_sha256,
            replayed=False,
        )

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
    profile = passport.measured_profile
    if profile is None:
        raise OverlayAdmissionError("measured_profile_missing")
    body_sha = f"sha256:{hashlib.sha256(body).hexdigest()}"
    if getattr(profile, "sample_content_sha256", None) != body_sha:
        raise OverlayAdmissionError("measured_profile_content_drift")
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
        raise OverlayAdmissionError(
            "acquisition_authority_unresolved", type(exc).__name__
        ) from exc
    authority_projection = (
        str(getattr(resolved, "registry_content_sha256", "")),
        str(getattr(resolved, "baseline_content_sha256", "")),
        str(getattr(resolved, "upstream_catalog_projection_sha256", "")),
        getattr(resolved, "registration", None),
        getattr(resolved, "field_binding", None),
    )
    embedded_projection = (
        str(passport.authority_registry_content_sha256),
        str(passport.baseline_content_sha256),
        str(passport.upstream_catalog_projection_sha256),
        passport.registration,
        passport.field_binding,
    )
    if authority_projection != embedded_projection:
        raise OverlayAdmissionError("acquisition_authority_drift")
    license_evidence = passport.license_evidence
    resolved_license = getattr(resolved, "license_disposition", None)
    if (
        str(getattr(resolved, "license_id", ""))
        != str(getattr(license_evidence, "license_id", ""))
        or _enum_value(resolved_license)
        != _enum_value(getattr(license_evidence, "disposition", ""))
    ):
        raise OverlayAdmissionError("license_disposition_drift")
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
    if not passport.source_authority_verified or not authority.verify_source_body(
        str(passport.authority_entry_id), body
    ):
        raise OverlayAdmissionError("source_authority_unverified")
    schema_validation = passport.schema_validation
    if not bool(getattr(schema_validation, "conformant", False)):
        raise OverlayAdmissionError("schema_contract_not_conformant")
    request_event = resolve_linked_request_event(raw_ref)
    request = request_event.get("request")
    entry = getattr(resolved, "entry", None)
    schema_projection = getattr(entry, "schema_projection", None)
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
    return body


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
    elif isinstance(payload, Sequence) and not isinstance(
        payload, (str, bytes, bytearray)
    ):
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
        measured.append(
            ((country_code, year, survey_year, wave, condition_json), numeric_value)
        )

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
        observation_class=ObservationProvenanceClass(
            _enum_value(passport.observation_class)
        ),
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
        raise OverlayAdmissionError(
            "raw_time_coordinate_invalid", f"{row_index}:{field}"
        ) from exc


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


def _insert_registration(
    con: duckdb.DuckDBPyConnection,
    registration: AcquisitionDatasetRegistration,
    passport: _Passport,
) -> None:
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
    columns_json = [
        column.model_dump(mode="json")
        for column in getattr(profile, "columns", ())
    ]
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
        str(row[1])
        for row in con.execute(f"PRAGMA table_info('{table}')").fetchall()
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


def _existing_epoch(path: Path, epoch_id: int) -> tuple[str] | None:
    con = duckdb.connect(str(path), read_only=True)
    try:
        row = con.execute(
            "SELECT admission_content_sha256 FROM acquisition_epochs WHERE epoch_id = ?",
            [epoch_id],
        ).fetchone()
    finally:
        con.close()
    return None if row is None else (str(row[0]),)


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


__all__ = [
    "OVERLAY_SCHEMA_VERSION",
    "AcquisitionDatasetRegistration",
    "BaselineIdentity",
    "BaselineMutationError",
    "CanonicalAcquisitionObservation",
    "CatalogAcquisitionOverlay",
    "MetricFieldBinding",
    "ObservationProvenanceClass",
    "OverlayAdmissionError",
    "OverlayAdmissionReceipt",
    "build_metric_field_binding",
    "derive_canonical_observations",
]
