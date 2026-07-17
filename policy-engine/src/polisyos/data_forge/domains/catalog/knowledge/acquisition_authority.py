"""Canonical owner resolution for acquisition admission.

The acquisition registry may extend the catalog with last-mile field edges, but
it cannot mint source, license, L5, or transport authority.  Those properties
are re-resolved from the immutable baseline catalog and the canonical L5
measurement registry every time an entry is used.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

import duckdb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.fabric import data_plane as fabric_data_plane

from .overlay import (
    AcquisitionDatasetRegistration,
    MetricFieldBinding,
    build_metric_field_binding,
)

ACQUISITION_AUTHORITY_SCHEMA_VERSION = "polisyos.data_forge.acquisition_authority.v1"
DEFAULT_ACQUISITION_AUTHORITY_REGISTRY = Path(
    "architecture/policy_design_case/layer3_gy_n13b_acquisition_registry.json"
)
DEFAULT_L5_MEASUREMENT_REGISTRY = Path(
    "production_data/canonical/local_data_20260501/"
    "ukraine_server_support_20260410/runtime_calibration_internals/"
    "calibration/d2/measurement_registry.json"
)
_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"


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
        if self.source_lane == "local_lift" and not (
            self.local_source_path
            and self.local_source_sha256
            and self.local_license_id
        ):
            raise ValueError("local authority entry requires content and license evidence")
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
    registry_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    baseline_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    field_binding: MetricFieldBinding
    registration: AcquisitionDatasetRegistration
    license_id: str
    license_disposition: LicenseDisposition
    l5_trust: ResolvedL5Trust
    upstream_catalog_projection_sha256: str = Field(pattern=_SHA256_PATTERN)
    effective_authority_score: float = Field(ge=0.0, le=1.0)


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

    def __init__(self, *, repo_root: Path, baseline_path: Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.baseline_path = Path(baseline_path).resolve()
        self.registry_path = self.repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
        self.l5_path = self.repo_root / DEFAULT_L5_MEASUREMENT_REGISTRY

    def resolve(self, entry_id: str) -> ResolvedAcquisitionAuthority:
        """Resolve one entry against fresh registry, catalog, license, and L5 bytes."""

        registry = self._load_registry()
        matches = [entry for entry in registry.entries if entry.entry_id == entry_id]
        if len(matches) != 1:
            raise AcquisitionAuthorityError("authority_entry_unresolved", entry_id)
        entry = matches[0]
        if entry.source_lane == "live_fetch":
            projection, license_id, registration = self._resolve_live_catalog(entry)
        else:
            projection, license_id, registration = self._resolve_local_source(entry)
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
            registry_content_sha256=registry.content_sha256,
            baseline_content_sha256=registry.baseline_content_sha256,
            field_binding=binding,
            registration=registration,
            license_id=license_id,
            license_disposition=disposition,
            l5_trust=l5,
            upstream_catalog_projection_sha256=fabric_data_plane.content_sha256(projection),
            effective_authority_score=score,
        )

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
    ) -> tuple[dict[str, object], str, AcquisitionDatasetRegistration]:
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
        return projection, str(license_id), registration

    def _resolve_local_source(
        self,
        entry: AcquisitionAuthorityEntry,
    ) -> tuple[dict[str, object], str, AcquisitionDatasetRegistration]:
        relative = Path(str(entry.local_source_path))
        if relative.is_absolute() or ".." in relative.parts:
            raise AcquisitionAuthorityError("local_source_path_unsafe")
        source_path = (self.repo_root / relative).resolve()
        if not source_path.is_relative_to(self.repo_root):
            raise AcquisitionAuthorityError("local_source_path_unsafe")
        source_hash = _file_sha256(source_path)
        if source_hash != entry.local_source_sha256:
            raise AcquisitionAuthorityError("local_source_content_drift")
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
            access_license=str(entry.local_license_id),
            country_codes=entry.country_codes,
            temporal_start=entry.temporal_start,
            temporal_end=entry.temporal_end,
            field_binding=placeholder,
        )
        projection = {
            "local_source_path": relative.as_posix(),
            "local_source_sha256": source_hash,
        }
        return projection, str(entry.local_license_id), registration

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


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        raise AcquisitionAuthorityError("authority_source_missing", path.as_posix())
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AcquisitionAuthorityError("authority_mapping_required")
    return {str(key): item for key, item in value.items()}


__all__ = [
    "ACQUISITION_AUTHORITY_SCHEMA_VERSION",
    "DEFAULT_ACQUISITION_AUTHORITY_REGISTRY",
    "AcquisitionAuthorityEntry",
    "AcquisitionAuthorityError",
    "AcquisitionAuthorityRegistry",
    "AuthoritySchemaColumn",
    "CanonicalAcquisitionAuthority",
    "LicenseDisposition",
    "ResolvedAcquisitionAuthority",
    "ResolvedL5Trust",
    "build_authority_entry",
    "build_authority_registry",
]
