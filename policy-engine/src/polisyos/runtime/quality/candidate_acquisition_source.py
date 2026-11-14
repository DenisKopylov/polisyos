"""Candidate-only WDI source custody with historical, content-derived replay.

This is a bounded candidate simulation input, not an acquisition passport,
observed-data admission, source-currentness claim, or claim-evidence authority.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

import polisyos.fabric.connectors as connectors
import polisyos.fabric.data_plane as data_plane
from polisyos.core import artifacts, canon
from polisyos.core.contracts import DataSnapshot, EvidenceBundle
from polisyos.core.llm import SECRET_PII_DETECTOR_VERSION, scan_secret_and_pii
from polisyos.data_forge.read_api import catalog
from polisyos.data_requirement import DataRequirementCompilationReport, DataRequirementSpec
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionRequirementBasisBinding,
    validate_persisted_data_requirement_compilation_report,
)

if TYPE_CHECKING:
    from polisyos.core.contracts import (
        CapabilitySourceCandidate,
        CapabilitySourceDiscoveryResult,
        RequirementToCapabilityQuery,
    )

CANDIDATE_ACQUISITION_SOURCE_KIND = "runtime.quality.candidate_acquisition_source"
CANDIDATE_ACQUISITION_SOURCE_SCHEMA = "polisyos.runtime.candidate_acquisition_source.v1"
CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V2 = "polisyos.runtime.candidate_acquisition_source.v2"
CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V3 = "polisyos.runtime.candidate_acquisition_source.v3"
_CANON = canon.CanonSpec(forbid_floats=False, exclude_none=False)
_LIMITATIONS = (
    "candidate_only",
    "source_authority_not_established_without_live_registry",
    "source_currentness_not_established",
    "historical_transport_status_not_established",
    "historical_heartbeat_and_response_events_not_revalidated",
    "current_run_job_route_ownership_not_established",
    "population_is_declared_source_scope_not_sample_denominator_evidence",
    "measurement_validity_not_established",
    "causal_validity_not_established",
    "claim_evidence_not_established",
)


class CandidateAcquisitionSource(BaseModel):
    """Exact source, compiler and scope for one non-authoritative numeric input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[
        "polisyos.runtime.candidate_acquisition_source.v1",
        "polisyos.runtime.candidate_acquisition_source.v2",
        "polisyos.runtime.candidate_acquisition_source.v3",
    ] = CANDIDATE_ACQUISITION_SOURCE_SCHEMA
    status: Literal["candidate_only"] = "candidate_only"
    purpose: Literal["candidate_simulation"] = "candidate_simulation"
    observation_class: catalog.ObservationProvenanceClass = (
        catalog.ObservationProvenanceClass.MODEL_OUTPUT
    )
    source_currentness: Literal["source_currentness_not_established"] = (
        "source_currentness_not_established"
    )
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    route_id: str = Field(min_length=1)
    requirement_basis_binding: AcquisitionRequirementBasisBinding
    compiler_report_ref: artifacts.ArtifactRef
    requirement_id: str = Field(min_length=1)
    candidate_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    target_slot_id: str = Field(min_length=1)
    country_code: str = Field(min_length=1)
    year: int = Field(ge=1, le=9999)
    population: str = Field(min_length=1)
    denominator: str | None = Field(default=None, min_length=1)
    quantity_kind: Literal["unconstrained", "share_of_denominator"]
    canonical_unit: str = Field(min_length=1)
    pii_scan_detector_version: str = Field(min_length=1)
    observation: float = Field(allow_inf_nan=False)
    limitations: tuple[str, ...] = Field(min_length=1)
    resolved_source: catalog.ResolvedAcquisitionAuthority
    live_source_execution: catalog.LiveSourceExecutionEvidence
    request_projection: dict[str, Any]
    raw_source_ref: artifacts.ArtifactRef
    normalized_source_ref: artifacts.ArtifactRef
    source_snapshot_ref: artifacts.ArtifactRef
    source_evidence_ref: artifacts.ArtifactRef

    @model_validator(mode="after")
    def _denominator_matches_schema_and_quantity(self) -> CandidateAcquisitionSource:
        if self.schema_version != CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V3 and (
            self.observation_class is not catalog.ObservationProvenanceClass.MODEL_OUTPUT
        ):
            raise ValueError("candidate_acquisition_source_legacy_provenance_mismatch")
        if self.schema_version == CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V3 and (
            "observation_class" not in self.model_fields_set
        ):
            raise ValueError("candidate_acquisition_source_v3_requires_observation_class")
        if self.schema_version == CANDIDATE_ACQUISITION_SOURCE_SCHEMA and self.denominator is None:
            raise ValueError("candidate_acquisition_source_v1_requires_denominator")
        if self.quantity_kind == "share_of_denominator" and self.denominator is None:
            raise ValueError("candidate_acquisition_source_share_requires_denominator")
        return self


@dataclass(frozen=True, slots=True)
class _CandidateDerivationContext:
    """Only the four fields used by the existing canonical value derivation."""

    epoch_id: int
    source_watermark: str
    dataset_version: str
    observation_class: catalog.ObservationProvenanceClass


def _selected(store: artifacts.ArtifactStore, ref: artifacts.ArtifactRef) -> artifacts.ArtifactRef:
    return artifacts.profile_bound_ref(store, ref)


def _as_ref(ref: object) -> artifacts.ArtifactRef:
    if isinstance(ref, BaseModel):
        return artifacts.ArtifactRef.model_validate(ref.model_dump(mode="json"))
    return artifacts.ArtifactRef.model_validate(ref)


def _read_selected(store: artifacts.ArtifactStore, ref: artifacts.ArtifactRef) -> bytes:
    if ref.manifest_profile_sha256 is None or _selected(store, ref) != ref:
        raise ValueError("candidate_source_selected_profile_missing")
    body = store.get_bytes(ref)
    if "sha256:" + hashlib.sha256(body).hexdigest() != str(ref.artifact_id):
        raise ValueError("candidate_source_artifact_digest_mismatch")
    return body


def _require_safe_connector_encoding(body: bytes, media_type: str) -> None:
    """Check the cache envelope before invoking a decoder with a pickle branch."""
    if len(body) < 4:
        raise ValueError("candidate_source_cache_envelope_invalid")
    envelope_length = int.from_bytes(body[:4], "big")
    if envelope_length <= 0 or envelope_length > len(body) - 4:
        raise ValueError("candidate_source_cache_envelope_invalid")
    envelope = canon.from_canonical_bytes(body[4 : 4 + envelope_length])
    data_media_type = media_type.removeprefix("application/vnd.polisyos.cached-result+")
    if (
        not isinstance(envelope, dict)
        or data_media_type not in {"application/json", "application/parquet"}
        or envelope.get("data_media_type") != data_media_type
    ):
        raise ValueError("candidate_source_cache_encoding_mismatch")


def _source_inputs(source: CandidateAcquisitionSource) -> list[artifacts.InputRef]:
    return [
        artifacts.input_ref_from_artifact_ref(ref, role=role)
        for role, ref in (
            ("compiler_report", source.compiler_report_ref),
            ("raw_source", source.raw_source_ref),
            ("normalized_source", source.normalized_source_ref),
            ("fabric_snapshot", source.source_snapshot_ref),
            ("fabric_evidence", source.source_evidence_ref),
        )
    ]


def _write_options(source: CandidateAcquisitionSource) -> artifacts.ArtifactWriteOptions:
    schema_name = source.schema_version
    schema_version = schema_name.rsplit(".v", maxsplit=1)[1]
    producer_version = schema_version + ".0"
    return artifacts.ArtifactWriteOptions(
        kind=CANDIDATE_ACQUISITION_SOURCE_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(name=schema_name, version=schema_version),
        canon=artifacts.CanonInfo.from_spec(_CANON),
        producer=artifacts.ProducerInfo(component=__name__, version=producer_version),
        inputs=_source_inputs(source),
        tenant_context=artifacts.ArtifactTenantContextInfo(
            tenant_id=source.tenant_id, cell_id=source.cell_id
        ),
        same_input_closure=artifacts.ArtifactSameInputClosureInfo(
            closure_id=f"candidate-acquisition-source:{source.run_id}:{source.job_id}:{source.route_id}",
            status="candidate_only",
            run_id=source.run_id,
            job_id=source.job_id,
            tenant_id=source.tenant_id,
            cell_id=source.cell_id,
        ),
    )


def _selected_compiler_candidate(
    store: artifacts.ArtifactStore,
    *,
    binding: AcquisitionRequirementBasisBinding,
    compiler_report_ref: artifacts.ArtifactRef,
    requirement_id: str,
    candidate_digest: str,
    compiled_requirement_ref: str | None = None,
    require_selected_writer_profile: bool = False,
) -> tuple[
    DataRequirementSpec | None,
    str | None,
    RequirementToCapabilityQuery,
    CapabilitySourceDiscoveryResult,
    CapabilitySourceCandidate,
]:
    if binding.compiler_report_ref.manifest_profile_sha256 is None:
        raise ValueError("candidate_source_compiler_profile_unselected")
    issues = validate_persisted_data_requirement_compilation_report(
        store, binding, require_selected_writer_profile=require_selected_writer_profile
    )
    if issues:
        raise ValueError(f"candidate_source_compiler_binding_invalid: {issues}")
    if _selected(store, binding.compiler_report_ref) != compiler_report_ref:
        raise ValueError("candidate_source_compiler_profile_mismatch")
    _read_selected(store, compiler_report_ref)
    report = DataRequirementCompilationReport.model_validate(
        artifacts.load_core_json_artifact(store, compiler_report_ref)
    )
    resolutions = tuple(
        item
        for item in (report.capability_requirement_resolutions or ())
        if item.query.requirement_id == requirement_id
    )
    if len(resolutions) != 1 or resolutions[0].candidate_discovery is None:
        raise ValueError("candidate_source_requirement_ambiguous_or_missing")
    resolution = resolutions[0]
    discovery = resolution.candidate_discovery
    candidates = tuple(
        candidate
        for candidate in discovery.candidates
        if candidate.content_digest == candidate_digest
    )
    if len(candidates) != 1:
        raise ValueError("candidate_source_descriptor_ambiguous_or_missing")
    spec = None
    if compiled_requirement_ref is not None:
        specs = tuple(
            item for item in report.specs if item.requirement_id == compiled_requirement_ref
        )
        if len(specs) != 1:
            raise ValueError("candidate_source_compiler_spec_ambiguous_or_missing")
        spec = specs[0]
        capability = spec.metadata.get("capability_binding")
        if (
            not isinstance(capability, Mapping)
            or capability.get("requirement_id") != resolution.query.requirement_id
            or not isinstance(capability.get("construct_ref"), str)
            or capability["construct_ref"].removeprefix("construct:") != resolution.query.construct
            or str(spec.metadata.get("construct_ref", "")).removeprefix("construct:")
            != resolution.query.construct
            or discovery.query != resolution.query
        ):
            raise ValueError("candidate_source_compiler_relation_mismatch")
    return spec, resolution.scope_profile_id, resolution.query, discovery, candidates[0]


def validate_candidate_compiler_relation(
    store: artifacts.ArtifactStore,
    *,
    requirement_basis_binding: AcquisitionRequirementBasisBinding,
    compiled_requirement_ref: str,
    requirement_id: str,
    candidate_digest: str,
) -> None:
    """Reopen one selected compiler spec, resolution, and candidate descriptor.

    This checks only their identity and relationship, never source permission,
    currentness, institutional authority, or observed-data admission.
    """
    if type(requirement_basis_binding) is not AcquisitionRequirementBasisBinding:
        raise TypeError("candidate_source_compiler_binding_required")
    if not isinstance(compiled_requirement_ref, str) or not compiled_requirement_ref.strip():
        raise ValueError("candidate_source_compiler_spec_ambiguous_or_missing")
    _selected_compiler_candidate(
        store,
        binding=requirement_basis_binding,
        compiler_report_ref=requirement_basis_binding.compiler_report_ref,
        compiled_requirement_ref=compiled_requirement_ref,
        requirement_id=requirement_id,
        candidate_digest=candidate_digest,
    )


def _validate_scope(
    *,
    resolved: catalog.ResolvedAcquisitionAuthority,
    target_slot_id: str,
    country_code: str,
    year: int,
    population: str,
    denominator: str | None,
    quantity_kind: str,
    canonical_unit: str,
    query: RequirementToCapabilityQuery,
    discovery: CapabilitySourceDiscoveryResult,
    candidate: CapabilitySourceCandidate,
) -> None:
    from polisyos.runtime.quality.capability_index import EvidenceCapability
    from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver

    try:
        capability = EvidenceCapability.model_validate_json(
            json.dumps(candidate.descriptor, ensure_ascii=False, allow_nan=False)
        )
        replayed = RequirementToCapabilityResolver(
            capabilities=(capability,),
            capability_index_ref=discovery.capability_index_ref,
        ).discover_sources(query)
    except (TypeError, ValueError) as exc:
        raise ValueError("candidate_source_descriptor_scope_mismatch") from exc
    if tuple((item.capability_ref, item.content_digest) for item in replayed.candidates) != (
        (candidate.capability_ref, candidate.content_digest),
    ):
        raise ValueError("candidate_source_descriptor_scope_mismatch")
    if not set(replayed.limitations).issubset(discovery.limitations) or not set(
        replayed.candidates[0].limitations
    ).issubset(candidate.limitations):
        raise ValueError("candidate_source_scope_limitations_mismatch")
    entry = resolved.entry
    registration = resolved.registration
    projection = resolved.upstream_catalog_projection
    measure_scope = entry.source_measure_scope
    try:
        observation_class = catalog.resolve_source_observation_class(resolved)
    except (TypeError, ValueError) as exc:
        raise ValueError("candidate_source_owner_scope_mismatch") from exc
    descriptor = candidate.descriptor
    assets = candidate.source_assets
    if len(assets) != 1 or not isinstance(assets[0].get("metadata"), dict):
        raise ValueError("candidate_source_asset_ambiguous_or_missing")
    metadata = assets[0]["metadata"]
    # Capability evidence categories can be broader than source provenance:
    # the modeled labor panel is a derived capability with model_output bytes.
    # A source-level declaration wins; a canonical category is the fallback
    # for descriptors such as observed inputs that omit the redundant field.
    descriptor_provenance = metadata.get("observation_provenance", descriptor.get("evidence_mode"))
    scope = candidate.scope
    fetch = metadata.get("catalog_fetch_binding")
    expected_fetch = {
        "connector_id": registration.connector_id,
        "dataset_id": registration.request_dataset_id,
        "metric_id": entry.upstream_metric_id,
        "profile_id": registration.source_profile_id,
    }
    owner_start, owner_end = catalog.resolve_live_temporal_bounds(entry)
    if (
        entry.source_lane != "live_fetch"
        or measure_scope is None
        or measure_scope.population != population
        or measure_scope.denominator != denominator
        or measure_scope.temporal_granularity != "annual"
        or measure_scope.quantity_kind != quantity_kind
        or entry.target_variable != target_slot_id
        or entry.canonical_unit != canonical_unit
        or registration.metric_id != target_slot_id
        or registration.field_binding != resolved.field_binding
        or registration.field_binding.canonical_variable != entry.target_variable
        or registration.field_binding.raw_field != entry.raw_field
        or registration.field_binding.raw_unit != entry.raw_unit
        or registration.field_binding.canonical_unit != entry.canonical_unit
        or registration.field_binding.unit_transform != entry.unit_transform
        or registration.field_binding.unit_transform_ref != entry.unit_transform_ref
        or registration.field_binding.aggregation_method != entry.aggregation_method
        or country_code not in entry.country_codes
        or owner_start is None
        or owner_end is None
        or not owner_start <= year <= owner_end
        or registration.connector_id != "worldbank.wdi"
        or registration.source_profile_id != "worldbank_wdi"
        or not isinstance(projection, dict)
        or data_plane.content_sha256(projection) != resolved.upstream_catalog_projection_sha256
        or projection.get("source_catalog_dataset_id") != entry.source_catalog_dataset_id
        or projection.get("source_catalog_distribution_id") != entry.source_catalog_distribution_id
        or projection.get("request_dataset_id") != registration.request_dataset_id
        or projection.get("metric_id") != entry.upstream_metric_id
        or projection.get("connector_id") != registration.connector_id
        or projection.get("profile_id") != registration.source_profile_id
        or projection.get("title") != entry.title
        or projection.get("description") != entry.description
    ):
        raise ValueError("candidate_source_owner_scope_mismatch")
    if (
        candidate.construct_ref.removeprefix("construct:")
        != query.construct.removeprefix("construct:")
        or query.entity_scope != "country"
        or query.geography != country_code
        or dict(query.population_filter) != {"type": population}
        or query.time_window.start != f"{year:04d}-01-01"
        or query.time_window.end != f"{year:04d}-12-31"
        or scope.get("entity_scope") != "country"
        or scope.get("spatial_granularity") != "country"
        or scope.get("population") != population
        or scope.get("temporal_granularity") != "annual"
        or descriptor.get("capability_lifecycle", {}).get("state")
        not in {"draft", "governed", "active"}
        or fetch != expected_fetch
        or metadata.get("indicator_id") != registration.request_dataset_id
        or (
            descriptor.get("evidence_mode")
            in {
                catalog.ObservationProvenanceClass.OBSERVED.value,
                catalog.ObservationProvenanceClass.MODEL_OUTPUT.value,
            }
            and descriptor["evidence_mode"] != observation_class.value
        )
        or descriptor_provenance != observation_class.value
        or metadata.get("population_scope") != population
        or metadata.get("denominator") != denominator
        or metadata.get("quantity_kind", "unconstrained") != quantity_kind
        or metadata.get("temporal_granularity") != "annual"
        or metadata.get("target_world_slot") != target_slot_id
        or metadata.get("canonical_unit") != entry.canonical_unit
        or metadata.get("raw_unit") not in (entry.raw_unit, f"{entry.raw_unit}_of_{denominator}")
        or metadata.get("source_release") != "not_established"
    ):
        raise ValueError("candidate_source_descriptor_scope_mismatch")


def validate_candidate_acquisition_selection(
    store: artifacts.ArtifactStore,
    *,
    requirement_basis_binding: AcquisitionRequirementBasisBinding,
    compiled_requirement_ref: str,
    requirement_id: str,
    candidate_digest: str,
    authority: catalog.CanonicalAcquisitionAuthority,
    entry_id: str,
    target_slot_id: str,
    country_code: str,
    year: int,
    population: str,
) -> tuple[CapabilitySourceCandidate, catalog.ResolvedAcquisitionAuthority]:
    """Check the exact candidate source and declared scope before any fetch.

    This resolves the current local authority owner and checks typed compiler,
    descriptor, and owner-declared scope consistency. It does not grant source
    permission or establish freshness, measurement validity, or claim-evidence
    authority.
    """
    if type(requirement_basis_binding) is not AcquisitionRequirementBasisBinding:
        raise TypeError("candidate_source_compiler_binding_required")
    if type(authority) is not catalog.CanonicalAcquisitionAuthority:
        raise TypeError("candidate_source_canonical_authority_required")
    if not isinstance(entry_id, str) or not entry_id.strip():
        raise ValueError("candidate_source_owner_entry_required")
    if not isinstance(compiled_requirement_ref, str) or not compiled_requirement_ref.strip():
        raise ValueError("candidate_source_compiler_spec_ambiguous_or_missing")
    spec, scope_profile_id, query, discovery, candidate = _selected_compiler_candidate(
        store,
        binding=requirement_basis_binding,
        compiler_report_ref=requirement_basis_binding.compiler_report_ref,
        compiled_requirement_ref=compiled_requirement_ref,
        requirement_id=requirement_id,
        candidate_digest=candidate_digest,
        require_selected_writer_profile=True,
    )
    if spec is None:
        raise ValueError("candidate_source_compiler_spec_ambiguous_or_missing")
    try:
        resolved_source = authority.resolve(entry_id)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("candidate_source_live_owner_unavailable") from exc
    profile = spec.metadata.get("scope_profile")
    constructs = profile.get("required_constructs") if isinstance(profile, Mapping) else None
    if (
        not isinstance(profile, Mapping)
        or not isinstance(constructs, list | tuple)
        or any(not isinstance(construct, str) or not construct for construct in constructs)
        or not query.source_family_alias
        or query.source_family_alias not in spec.required_data_families
        or not scope_profile_id
        or profile.get("profile_id") != scope_profile_id
        or profile.get("jurisdiction") != country_code
        or profile.get("population") != population
        or profile.get("entity_scope") != query.entity_scope
        or profile.get("granularity") != "annual"
        or profile.get("time_role") != "observation_time"
        or profile.get("time_window") != {"start": f"{year:04d}-01-01", "end": f"{year:04d}-12-31"}
        or query.construct not in constructs
        or spec.scope.jurisdiction != country_code
        or spec.scope.population != population
    ):
        raise ValueError("candidate_source_compiler_relation_mismatch")
    measure = resolved_source.entry.source_measure_scope
    if measure is None or (
        measure.quantity_kind == "share_of_denominator" and measure.denominator is None
    ):
        raise ValueError("candidate_source_owner_measure_scope_missing")
    _validate_scope(
        resolved=resolved_source,
        target_slot_id=target_slot_id,
        country_code=country_code,
        year=year,
        population=population,
        denominator=measure.denominator,
        quantity_kind=measure.quantity_kind,
        canonical_unit=resolved_source.entry.canonical_unit,
        query=query,
        discovery=discovery,
        candidate=candidate,
    )
    return candidate, resolved_source


def _replay_source(
    store: artifacts.ArtifactStore, source: CandidateAcquisitionSource
) -> tuple[float, tuple[str, ...]]:
    _, _, query, discovery, candidate = _selected_compiler_candidate(
        store,
        binding=source.requirement_basis_binding,
        compiler_report_ref=source.compiler_report_ref,
        requirement_id=source.requirement_id,
        candidate_digest=source.candidate_digest,
    )
    _validate_scope(
        resolved=source.resolved_source,
        target_slot_id=source.target_slot_id,
        country_code=source.country_code,
        year=source.year,
        population=source.population,
        denominator=source.denominator,
        quantity_kind=source.quantity_kind,
        canonical_unit=source.canonical_unit,
        query=query,
        discovery=discovery,
        candidate=candidate,
    )
    proof = source.live_source_execution
    resolved = source.resolved_source
    entry = resolved.entry
    observation_class = catalog.resolve_source_observation_class(resolved)
    if source.observation_class is not observation_class:
        raise ValueError("candidate_source_provenance_mismatch")
    registration = resolved.registration
    request = source.request_projection
    if (
        data_plane.content_sha256(request) != proof.authorization.request_sha256
        or request.get("authority_entry_id") != entry.entry_id
        or request.get("authority_registry_content_sha256") != resolved.registry_content_sha256
        or request.get("variable_id") != entry.target_variable
        or request.get("source_lane") != "live_fetch"
        or request.get("dataset_id") != entry.landing_dataset_id
        or request.get("distribution_id") != entry.landing_distribution_id
        or request.get("connector_id") != registration.connector_id
        or request.get("profile_id") != registration.source_profile_id
        or request.get("request_dataset_id") != registration.request_dataset_id
        or request.get("request_variables") != [registration.request_dataset_id]
        or request.get("filters") != {"country": [source.country_code]}
        or request.get("date_start") != f"{source.year:04d}-01-01"
        or request.get("date_end") != f"{source.year:04d}-12-31"
        or type(request.get("page_size")) is not int
        or not 0 < request["page_size"] <= 20_000
        or request.get("schema_contract") != entry.schema_projection()
        or proof.authorization.schema_contract_sha256
        != data_plane.content_sha256(entry.schema_projection())
        or proof.authorization.connector_id != registration.connector_id
        or proof.authorization.profile_id != registration.source_profile_id
        or proof.authorization.request_variables != (registration.request_dataset_id,)
        or proof.baseline_before_sha256 != resolved.baseline_content_sha256
        or not proof.authorization.authorized
    ):
        raise ValueError("candidate_source_request_binding_mismatch")
    request_event = {
        "sequence": proof.request_ref.sequence,
        "event_kind": "request",
        "attempt_id": proof.authorization.attempt_id,
        "request": request,
        "request_sha256": proof.authorization.request_sha256,
    }
    if (
        data_plane.content_sha256(request_event) != proof.request_ref.event_sha256
        or len(data_plane.canonical_json_bytes(request_event)) != proof.request_ref.byte_length
    ):
        raise ValueError("candidate_source_request_event_mismatch")
    trace = proof.transport_trace
    if (
        trace.url
        != f"https://api.worldbank.org/v2/country/{source.country_code}/indicator/{registration.request_dataset_id}"
        or trace.params
        != {
            "date": f"{source.year}:{source.year}",
            "format": "json",
            "page": "1",
            "per_page": str(request.get("page_size")),
        }
    ):
        raise ValueError("candidate_source_transport_scope_mismatch")
    transport_event = {
        "sequence": trace.transport_attempt_ref.sequence,
        "event_kind": "transport_attempt",
        "attempt_id": proof.authorization.attempt_id,
        "transport_attempt": {
            "request_event_sha256": proof.request_ref.event_sha256,
            "connector_id": trace.connector_id,
            "url": trace.url,
            "params": trace.params,
            "params_sha256": trace.params_sha256,
        },
    }
    if (
        data_plane.content_sha256(transport_event) != trace.transport_attempt_ref.event_sha256
        or len(data_plane.canonical_json_bytes(transport_event))
        != trace.transport_attempt_ref.byte_length
    ):
        raise ValueError("candidate_source_transport_event_mismatch")
    if (
        proof.schema_version != "polisyos.data_forge.live_source_execution_evidence.v2"
        or proof.raw_artifact_ref is None
        or source.raw_source_ref != proof.raw_artifact_ref
        or source.raw_source_ref.manifest_profile_sha256 is None
        or source.raw_source_ref.kind != "fabric.acquisition.raw_evidence"
        or source.raw_source_ref.media_type != "application/json"
        or source.raw_source_ref.artifact_id != proof.raw_artifact_id
        or source.normalized_source_ref.kind != "connector_cache.payload"
        or source.normalized_source_ref.media_type
        not in {
            "application/vnd.polisyos.cached-result+application/json",
            "application/vnd.polisyos.cached-result+application/parquet",
        }
        or source.normalized_source_ref.artifact_id != proof.normalized_data_artifact_id
        or _as_ref(proof.data_snapshot_ref) != source.source_snapshot_ref
        or _as_ref(proof.evidence_bundle_ref) != source.source_evidence_ref
    ):
        raise ValueError("candidate_source_artifact_binding_mismatch")
    raw = catalog.read_selected_live_raw_source(store, source.raw_source_ref)
    normalized = _read_selected(store, source.normalized_source_ref)
    if len(raw) > proof.authorization.budget.max_decompressed_bytes:
        raise ValueError("candidate_source_raw_budget_exceeded")
    raw_scan = scan_secret_and_pii(
        raw,
        scope="connector request/response payloads",
        artifact_ref_or_route=proof.raw_evidence_ref.event_sha256,
        redact=False,
        block_on_findings=True,
    )
    if (
        raw_scan.has_findings
        or not raw_scan.reports
        or any(
            report.detector_version != source.pii_scan_detector_version
            for report in raw_scan.reports
        )
    ):
        raise ValueError("candidate_source_raw_pii_or_scan_version_unresolved")
    _require_safe_connector_encoding(normalized, source.normalized_source_ref.media_type)
    _read_selected(store, source.source_snapshot_ref)
    _read_selected(store, source.source_evidence_ref)
    snapshot = artifacts.validate_core_model_json_artifact(
        DataSnapshot, store, source.source_snapshot_ref
    )
    bundle = EvidenceBundle.model_validate(
        artifacts.load_core_json_artifact(store, source.source_evidence_ref)
    )
    from polisyos.runtime.quality.data_snapshot_lineage import validate_data_snapshot_owner_lineage

    validate_data_snapshot_owner_lineage(
        store, source.source_snapshot_ref, snapshot, candidate_only=True
    )
    if (
        _as_ref(snapshot.data_ref) != source.normalized_source_ref
        or _as_ref(snapshot.evidence_ref) != source.source_evidence_ref
        or len(bundle.sources) != 1
        or _as_ref(bundle.sources[0]) != source.normalized_source_ref
        or snapshot.stats.get("datasets_fetched") != 1
        or "sha256:" + hashlib.sha256(raw).hexdigest() != proof.raw_body_sha256
    ):
        raise ValueError("candidate_source_snapshot_binding_mismatch")
    payload = json.loads(raw)
    structured_scan = scan_secret_and_pii(
        payload,
        scope="connector request/response payloads",
        artifact_ref_or_route=proof.raw_evidence_ref.event_sha256,
        redact=False,
        block_on_findings=True,
    )
    if (
        structured_scan.has_findings
        or not structured_scan.reports
        or any(
            report.detector_version != source.pii_scan_detector_version
            for report in structured_scan.reports
        )
    ):
        raise ValueError("candidate_source_raw_pii_or_scan_version_unresolved")
    if (
        not isinstance(payload, list)
        or len(payload) != 2
        or not isinstance(payload[0], dict)
        or not isinstance(payload[1], list)
        or len(payload[1]) != 1
        or not isinstance(payload[1][0], dict)
    ):
        raise ValueError("candidate_source_wdi_envelope_invalid")
    page, rows = payload
    row = rows[0]
    if (
        tuple(int(page.get(key, 0)) for key in ("page", "pages", "per_page", "total"))
        != (1, 1, request.get("page_size"), 1)
        or not isinstance(row.get("indicator"), dict)
        or row["indicator"].get("id") != registration.request_dataset_id
        or row.get("countryiso3code") != source.country_code
        or str(row.get("date")) != str(source.year)
        or row.get("unit") not in (None, "", entry.raw_unit)
    ):
        raise ValueError("candidate_source_wdi_scope_mismatch")
    result = connectors.ResultSerializer.deserialize(normalized)
    reencoded, media = connectors.ResultSerializer.serialize(result)
    expected_frame = connectors.normalize_worldbank_records(rows, registration.request_dataset_id)
    if (
        media != source.normalized_source_ref.media_type
        or reencoded != normalized
        or not expected_frame.equals(result.data)
        or result.row_count != 1
        or result.has_more
        or result.next_page_token is not None
        or result.version.content_hash != proof.raw_body_sha256
        or result.version.content_hash != proof.normalized_result_content_sha256
        or f"fabric://{result.schema_id}@{result.schema_version}" != entry.schema_contract_ref
    ):
        raise ValueError("candidate_source_normalized_projection_mismatch")
    normalized_body = catalog.normalized_acquisition_source_body(result)
    (derived,) = catalog.derive_canonical_observations(
        normalized_body,
        passport=_CandidateDerivationContext(
            epoch_id=0,
            source_watermark=proof.raw_body_sha256,
            dataset_version="source_release_not_established",
            observation_class=observation_class,
        ),
        registration=registration,
    )
    if (
        derived.country_code != source.country_code
        or derived.year != source.year
        or derived.canonical_var != source.target_slot_id
        or derived.observation_class is not observation_class
    ):
        raise ValueError("candidate_source_derived_scope_mismatch")
    if source.quantity_kind == "share_of_denominator" and not 0.0 <= derived.value <= 1.0:
        raise ValueError("candidate_source_share_out_of_bounds")
    limitations = tuple(
        dict.fromkeys(
            (
                *_LIMITATIONS,
                *discovery.limitations,
                *candidate.limitations,
                *candidate.descriptor.get("limitations", ()),
            )
        )
    )
    return derived.value, limitations


def persist_candidate_acquisition_source(
    store: artifacts.ArtifactStore,
    *,
    authority: catalog.CanonicalAcquisitionAuthority,
    entry_id: str,
    live_source_execution: catalog.LiveSourceExecutionEvidence,
    requirement_basis_binding: AcquisitionRequirementBasisBinding,
    requirement_id: str,
    candidate_digest: str,
    target_slot_id: str,
    country_code: str,
    year: int,
    population: str,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    job_id: str,
    route_id: str,
) -> artifacts.ArtifactRef:
    """Persist live-verified source provenance without observed-data authority."""
    if type(authority) is not catalog.CanonicalAcquisitionAuthority:
        raise TypeError("candidate_source_canonical_authority_required")
    if type(live_source_execution) is not catalog.LiveSourceExecutionEvidence:
        raise TypeError("candidate_source_live_execution_evidence_required")
    if type(requirement_basis_binding) is not AcquisitionRequirementBasisBinding:
        raise TypeError("candidate_source_compiler_binding_required")
    if requirement_basis_binding.compiler_report_ref.manifest_profile_sha256 is None:
        raise ValueError("candidate_source_compiler_profile_unselected")
    proof = catalog.LiveSourceExecutionEvidence.model_validate(
        live_source_execution.model_dump(mode="json")
    )
    if (
        proof.schema_version != "polisyos.data_forge.live_source_execution_evidence.v2"
        or proof.raw_artifact_ref is None
        or proof.raw_artifact_ref.manifest_profile_sha256 is None
    ):
        raise ValueError("candidate_source_raw_profile_unselected")
    resolved = authority.resolve(entry_id)
    try:
        observation_class = catalog.resolve_source_observation_class(resolved)
    except (TypeError, ValueError) as exc:
        raise ValueError("candidate_source_owner_scope_mismatch") from exc
    if resolved.entry.source_measure_scope is None or (
        resolved.entry.source_measure_scope.quantity_kind == "share_of_denominator"
        and resolved.entry.source_measure_scope.denominator is None
    ):
        raise ValueError("candidate_source_owner_measure_scope_missing")
    authority.resolve_live_source_execution(entry_id, proof, store)
    request_event = data_plane.resolve_journal_event_ref(proof.request_ref)
    request = request_event.get("request")
    if not isinstance(request, dict):
        raise ValueError("candidate_source_request_missing")
    snapshot_ref = _selected(store, _as_ref(proof.data_snapshot_ref))
    evidence_ref = _selected(store, _as_ref(proof.evidence_bundle_ref))
    snapshot = artifacts.validate_core_model_json_artifact(DataSnapshot, store, snapshot_ref)
    source = CandidateAcquisitionSource(
        schema_version=(
            CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V3
            if observation_class is not catalog.ObservationProvenanceClass.MODEL_OUTPUT
            else (
                CANDIDATE_ACQUISITION_SOURCE_SCHEMA_V2
                if resolved.entry.source_measure_scope.denominator is None
                else CANDIDATE_ACQUISITION_SOURCE_SCHEMA
            )
        ),
        observation_class=observation_class,
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        job_id=job_id,
        route_id=route_id,
        requirement_basis_binding=requirement_basis_binding,
        compiler_report_ref=_selected(store, requirement_basis_binding.compiler_report_ref),
        requirement_id=requirement_id,
        candidate_digest=candidate_digest,
        target_slot_id=target_slot_id,
        country_code=country_code,
        year=year,
        population=population,
        denominator=resolved.entry.source_measure_scope.denominator,
        quantity_kind=resolved.entry.source_measure_scope.quantity_kind,
        canonical_unit=resolved.entry.canonical_unit,
        pii_scan_detector_version=SECRET_PII_DETECTOR_VERSION,
        observation=0.0,
        limitations=_LIMITATIONS,
        resolved_source=resolved,
        live_source_execution=proof,
        request_projection=request,
        raw_source_ref=proof.raw_artifact_ref,
        normalized_source_ref=_selected(store, _as_ref(snapshot.data_ref)),
        source_snapshot_ref=snapshot_ref,
        source_evidence_ref=evidence_ref,
    )
    observation, limitations = _replay_source(store, source)
    source = source.model_copy(update={"observation": observation, "limitations": limitations})
    ref = store.put_json(
        source, _write_options(source), canon_spec=_CANON, return_selected_profile=True
    )
    read_candidate_acquisition_source(store, source_ref=ref, authority=authority)
    return ref


def read_candidate_acquisition_source(
    store: artifacts.ArtifactStore,
    *,
    source_ref: artifacts.ArtifactRef,
    authority: catalog.CanonicalAcquisitionAuthority | None = None,
) -> CandidateAcquisitionSource:
    """Replay immutable source bytes; optionally also resolve the live source owner.

    Historical replay never establishes live authority, release freshness, a
    sampled denominator, causal validity, or claim-evidence admissibility.
    """
    if (
        source_ref.kind != CANDIDATE_ACQUISITION_SOURCE_KIND
        or source_ref.media_type != "application/json"
    ):
        raise ValueError("candidate_source_ref_profile_mismatch")
    source_payload = _read_selected(store, source_ref)
    source = CandidateAcquisitionSource.model_validate(
        artifacts.load_core_json_artifact(
            store,
            source_ref,
            raw_payload_bytes=source_payload,
        )
    )
    manifest = store.get_manifest(source_ref)
    opts = _write_options(source)
    if (
        manifest.artifact_schema != opts.schema
        or manifest.canon != opts.canon
        or manifest.inputs != opts.inputs
        or manifest.tenant_context != opts.tenant_context
        or manifest.same_input_closure != opts.same_input_closure
        or manifest.producer != opts.producer
    ):
        raise ValueError("candidate_source_manifest_binding_mismatch")
    observation, limitations = _replay_source(store, source)
    if observation != source.observation or limitations != source.limitations:
        raise ValueError("candidate_source_derived_value_or_limitations_mismatch")
    if authority is not None:
        if type(authority) is not catalog.CanonicalAcquisitionAuthority:
            raise TypeError("candidate_source_canonical_authority_required")
        proof = source.live_source_execution
        if authority.resolve(source.resolved_source.entry.entry_id) != source.resolved_source:
            raise ValueError("candidate_source_live_owner_mismatch")
        live = authority.resolve_live_source_execution(
            source.resolved_source.entry.entry_id, proof, store
        )
        if (
            data_plane.resolve_journal_event_ref(proof.request_ref).get("request")
            != source.request_projection
            or data_plane.resolve_raw_response_body(proof.raw_evidence_ref)
            != _read_selected(store, source.raw_source_ref)
            or catalog.normalized_acquisition_source_body(live)
            != catalog.normalized_acquisition_source_body(
                connectors.ResultSerializer.deserialize(
                    _read_selected(store, source.normalized_source_ref)
                )
            )
        ):
            raise ValueError("candidate_source_live_carrier_mismatch")
    return source
