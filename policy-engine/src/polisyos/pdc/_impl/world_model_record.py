"""Canonical Policy Design Case world-model record contract.

The DTO binds the world version a Policy Design Case relies on. Runtime owns
resolution, building, persistence, and simulation adapters; this module owns
only the stable, content-addressed contract those adapters and Scientist
consumers share.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Pydantic resolves these selected CAS-view fields when it builds the schema.
from polisyos.core.artifacts import ArtifactRef
from polisyos.ir.kernel import SLOT_ID_PATTERN

from .gy_waist import gy_artifact_self_identity_projection, gy_content_hash

WORLD_MODEL_RECORD_SCHEMA_VERSION = "policyos.runtime.world_model_record.v1"
WORLD_MODEL_RECORD_SCHEMA_V2_VERSION = "policyos.runtime.world_model_record.v2"
WORLD_MODEL_RECORD_SCHEMA_NAME = "polisyos.runtime.quality.WorldModelRecord"
WORLD_MODEL_RECORD_ARTIFACT_KIND = "runtime.quality.world_model_record"


class SubstrateLayer(StrEnum):
    """Production-data substrate layer labels shared by PDC and Runtime."""

    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"
    L6 = "L6"


class BranchMode(StrEnum):
    """World branch semantics for the bound version."""

    OBSERVED = "observed"
    SCENARIO = "scenario"
    DEPLOYMENT_UPDATE = "deployment_update"


class _StrictModel(BaseModel):
    """Strict immutable base model for world-model subcontracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class FabricWorldRef(_StrictModel):
    """Reference the Fabric world snapshot/branch and bitemporal query context."""

    snapshot_root: str = Field(..., min_length=1)
    snapshot_id: str = Field(..., min_length=1)
    branch: str = Field(..., min_length=1)
    as_of_valid_time: str | None = None
    as_of_tx_time: str | None = None
    world_query_policy: str = Field(..., min_length=1)
    provenance_manifest_ref: str = Field(..., min_length=1)
    content_query_digest: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")
    content_query_row_count: int | None = Field(None, ge=0)


class DataForgeBindingRef(_StrictModel):
    """Reference one Data Forge snapshot/read-API binding row."""

    snapshot_id: str = Field(..., min_length=1)
    release_id: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    read_api_identity: str = Field(..., min_length=1)
    snapshot_ref: str = Field(..., min_length=1)
    merkle_root: str = Field(..., min_length=1)
    data_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    claim_requirement_bindings: tuple[dict[str, Any], ...] = ()
    quality_gate_refs: tuple[str, ...] = ()
    lineage_refs: tuple[str, ...] = ()
    provenance_manifest_ref: str = Field(..., min_length=1)
    binding_path: str | None = None


class SimulationModelRef(_StrictModel):
    """Reference the IR model contract and mechanism/program graph surfaces."""

    model_spec_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    model_spec_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    model_id: str = Field(..., min_length=1)
    data_snapshot_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    registry_bundle_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    mechanism_refs: tuple[str, ...] = ()
    gcm_refs: tuple[str, ...] = ()
    ncm_refs: tuple[str, ...] = ()
    program_graph_refs: tuple[str, ...] = ()
    assumptions: tuple[dict[str, Any], ...] = ()
    fidelity_level: str = Field(..., min_length=1)
    calibration_ref: str | None = Field(None, pattern=r"^sha256:[0-9a-f]{64}$")
    calibrated: bool = False


class WorldModelArtifactViews(_StrictModel):
    """Exact CAS views selected by a versioned world-model record.

    Domain IDs remain stable projections for existing consumers. This bundle
    carries the manifest profile selectors needed to custody selected bytes.
    """

    data_snapshot_ref: ArtifactRef
    registry_bundle_ref: ArtifactRef
    model_spec_ref: ArtifactRef
    input_bindings_ref: ArtifactRef
    bound_state_snapshot_ref: ArtifactRef
    input_binding_report_ref: ArtifactRef
    substrate_registry_ref: ArtifactRef | None = None
    program_graph_refs: tuple[ArtifactRef, ...] = ()
    ncm_refs: tuple[ArtifactRef, ...] = ()

    @field_validator("*", mode="before")
    @classmethod
    def _normalize_reference_subclasses(cls, value: object) -> object:
        """Normalize ArtifactRef subtypes without dropping selected-view data."""

        def normalize(item: object) -> object:
            if isinstance(item, ArtifactRef) and type(item) is not ArtifactRef:
                return ArtifactRef(**item.model_dump(mode="python"))
            return item

        if isinstance(value, ArtifactRef):
            return normalize(value)
        if isinstance(value, (tuple, list)):
            return tuple(normalize(item) for item in value)
        return value

    @model_validator(mode="after")
    def _validate_view_contract(self) -> WorldModelArtifactViews:
        typed_pairs = (
            (self.data_snapshot_ref, "fabric.data_snapshot"),
            (self.registry_bundle_ref, "core.registry_bundle"),
            (self.model_spec_ref, "ir.model_spec"),
            (self.input_bindings_ref, "foundry.input_bindings"),
            (self.bound_state_snapshot_ref, "foundry.state_snapshot"),
            (self.input_binding_report_ref, "foundry.input_binding_report"),
            *((ref, "foundry.program_graph") for ref in self.program_graph_refs),
            *((ref, "ir.ncm_spec") for ref in self.ncm_refs),
        )
        if any(
            ref.kind != expected_kind or ref.media_type != "application/json"
            for ref, expected_kind in typed_pairs
        ):
            raise ValueError("world_model_artifact_view_type_invalid")
        if self.substrate_registry_ref is not None and (
            self.substrate_registry_ref.kind != "runtime.quality.production_data_substrate_registry"
            or self.substrate_registry_ref.media_type != "application/json"
        ):
            raise ValueError("world_model_artifact_view_type_invalid")
        return self


class FoundryBindingRef(_StrictModel):
    """Reference the actual Foundry input binding and bound GlobalState snapshot."""

    input_bindings_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    bound_state_snapshot_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    mapping_rules_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    state_slot_digest: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")


class SkgCausalPriorRef(_StrictModel):
    """Reference SKG/G2 causal priors and transport traces for this world."""

    skg_snapshot_ref: str = Field(..., min_length=1)
    skg_version_id: str = Field(..., min_length=1)
    source_data_snapshot_id: str = Field(..., min_length=1)
    edge_prior_refs: tuple[str, ...] = ()
    transport_score_refs: tuple[str, ...] = ()
    query_trace_refs: tuple[str, ...] = ()


class ResolvedSubstrateEntryRef(_StrictModel):
    """Resolved substrate registry entry consumed by a world-model version."""

    source_id: str = Field(..., min_length=1)
    family_id: str = Field(..., min_length=1)
    layer: SubstrateLayer
    coverage_score: float = Field(..., ge=0.0, le=1.0)
    trust_tier: str = Field(..., min_length=1)
    trust_cap: float = Field(..., ge=0.0, le=1.0)
    identification_mode: str = Field(..., min_length=1)
    schema_regime_id: str = Field(..., min_length=1)
    data_version: str = Field(..., min_length=1)
    snapshot_id: str = Field(..., min_length=1)
    source_snapshot_id: str = Field(..., min_length=1)
    entry_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")


class SubstrateRegistryRef(_StrictModel):
    """Name the production-data substrate registry version used by this world."""

    substrate_version_id: str = Field(..., pattern=r"^substrate_version_[a-f0-9]{16}$")
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    registry_artifact_ref: str | None = None
    resolved_entries: tuple[ResolvedSubstrateEntryRef, ...]

    @field_validator("resolved_entries")
    @classmethod
    def _resolved_entries_required(
        cls,
        value: tuple[ResolvedSubstrateEntryRef, ...],
    ) -> tuple[ResolvedSubstrateEntryRef, ...]:
        if not value:
            raise ValueError("substrate_registry_entries_missing")
        return value


class PolicySlotBinding(_StrictModel):
    """Bind a policy slot id to a concrete path in the bound Foundry state."""

    slot_id: str = Field(..., pattern=SLOT_ID_PATTERN)
    state_path: str = Field(..., min_length=1)
    unit: str | None = None
    entity_scope: str = Field(..., min_length=1)
    temporal_granularity: str = Field(..., min_length=1)


class WorldModelLimitations(_StrictModel):
    """Represent world-model limits that constrain admissibility and transport."""

    unavailable_data: tuple[str, ...] = ()
    transport_limits: tuple[str, ...] = ()
    calibration_envelope_status: Literal["unknown", "inside", "near_boundary", "outside"] = (
        "unknown"
    )
    unresolved_conflicts: tuple[str, ...] = ()
    admissibility_blockers: tuple[str, ...] = ()


class DeploymentUpdateRefs(_StrictModel):
    """Declare Phase-6 write-back refs without performing deployment updates."""

    phase: Literal["phase_6_forward_hook"] = "phase_6_forward_hook"
    feedback_refs: tuple[str, ...] = ()
    reissue_refs: tuple[str, ...] = ()
    refute_refs: tuple[str, ...] = ()
    incident_refs: tuple[str, ...] = ()
    posterior_update_refs: tuple[str, ...] = ()


class WorldModelRecord(_StrictModel):
    """Name one versioned, simulatable world built from existing substrates."""

    world_model_record_id: str = Field(..., pattern=r"^world_model_record_[a-f0-9]{16}$")
    schema_version: Literal[
        "policyos.runtime.world_model_record.v1",
        "policyos.runtime.world_model_record.v2",
    ] = WORLD_MODEL_RECORD_SCHEMA_VERSION
    authority_status: Literal[
        "candidate_unverified",
        "bound",
        "limited",
        "contested",
        "blocked",
        "publishable",
    ] = "bound"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    producer_ref: str = Field(..., min_length=1)
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")

    region_or_jurisdiction: str = Field(..., min_length=1)
    population_scope: str = Field(..., min_length=1)
    policy_domain: str = Field(..., min_length=1)
    valid_time_scope: str = Field(..., min_length=1)
    tx_time_scope: str = Field(..., min_length=1)
    resolution: str = Field(..., min_length=1)
    branch_mode: BranchMode

    fabric_world_ref: FabricWorldRef
    data_forge_binding_ref: DataForgeBindingRef
    simulation_model_ref: SimulationModelRef
    foundry_binding_ref: FoundryBindingRef
    skg_causal_prior_ref: SkgCausalPriorRef
    substrate_registry_ref: SubstrateRegistryRef
    policy_slot_map: tuple[PolicySlotBinding, ...]
    limitations: WorldModelLimitations = Field(default_factory=WorldModelLimitations)
    deployment_update_refs: DeploymentUpdateRefs = Field(default_factory=DeploymentUpdateRefs)
    artifact_views: WorldModelArtifactViews | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )

    @field_validator("policy_slot_map")
    @classmethod
    def _policy_slot_map_must_be_unique(
        cls,
        value: tuple[PolicySlotBinding, ...],
    ) -> tuple[PolicySlotBinding, ...]:
        if not value:
            raise ValueError("policy_slot_map_missing")
        seen: set[str] = set()
        duplicates: list[str] = []
        for binding in value:
            if binding.slot_id in seen:
                duplicates.append(binding.slot_id)
            seen.add(binding.slot_id)
        if duplicates:
            raise ValueError(f"policy_slot_map_duplicate:{','.join(sorted(duplicates))}")
        return value

    @model_validator(mode="after")
    def _validate_content_hash(self) -> WorldModelRecord:
        if not self.fabric_world_ref.content_query_digest:
            raise ValueError("fabric_world_content_query_digest_missing")
        if not self.fabric_world_ref.content_query_row_count:
            raise ValueError("fabric_world_empty")
        if self.schema_version == WORLD_MODEL_RECORD_SCHEMA_VERSION:
            if self.artifact_views is not None:
                raise ValueError("world_model_v1_artifact_views_not_supported")
        elif self.schema_version == WORLD_MODEL_RECORD_SCHEMA_V2_VERSION:
            if self.artifact_views is None:
                raise ValueError("world_model_v2_artifact_views_missing")
            _validate_world_model_artifact_views(self)
        expected = world_model_record_content_hash(self)
        if self.content_hash != expected:
            raise ValueError(f"content_hash_mismatch: expected {expected}, got {self.content_hash}")
        return self

    def slot_binding(self, slot_id: str) -> PolicySlotBinding | None:
        """Return the state binding for ``slot_id`` if present."""

        for binding in self.policy_slot_map:
            if binding.slot_id == slot_id:
                return binding
        return None


def world_model_record_content_hash(record: WorldModelRecord) -> str:
    """Return the canonical, time-invariant hash for a world record."""

    return gy_content_hash(_content_payload_from_record(record))


def world_model_record_content_hash_from_fields(fields: Mapping[str, Any]) -> str:
    """Return the canonical hash for fields assembled by the Runtime builder."""

    return gy_content_hash(_content_payload_from_fields(fields))


def serialize_world_model_record_for_storage(
    record: WorldModelRecord,
) -> dict[str, Any]:
    """Serialize one versioned WMR without widening historical v1 bytes."""

    validated = WorldModelRecord.model_validate(record.model_dump(mode="json"))
    payload = validated.model_dump(mode="json")
    if validated.schema_version == WORLD_MODEL_RECORD_SCHEMA_VERSION:
        payload.pop("artifact_views", None)
    return payload


def _content_payload_from_record(record: WorldModelRecord) -> dict[str, Any]:
    payload = gy_artifact_self_identity_projection(record)
    if record.schema_version == WORLD_MODEL_RECORD_SCHEMA_VERSION:
        # V1 is a historical wire contract. A new optional field must not
        # perturb either its persisted bytes or its content hash.
        payload.pop("artifact_views", None)
    for field in ("world_model_record_id", "created_at", "producer_ref", "authority_status"):
        payload.pop(field, None)
    return _strip_non_content_locations(payload)


def _content_payload_from_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    payload = gy_artifact_self_identity_projection({**fields, "content_hash": "pending"})
    if fields.get("schema_version", WORLD_MODEL_RECORD_SCHEMA_VERSION) == (
        WORLD_MODEL_RECORD_SCHEMA_VERSION
    ):
        payload.pop("artifact_views", None)
    return _strip_non_content_locations(
        {
            key: _json_ready(value)
            for key, value in payload.items()
            if key
            not in {
                "world_model_record_id",
                "created_at",
                "producer_ref",
                "authority_status",
            }
        }
    )


def _validate_world_model_artifact_views(record: WorldModelRecord) -> None:
    views = record.artifact_views
    if views is None:
        raise ValueError("world_model_v2_artifact_views_missing")
    simulation = record.simulation_model_ref
    foundry = record.foundry_binding_ref
    pairs = (
        (views.data_snapshot_ref, simulation.data_snapshot_ref),
        (views.registry_bundle_ref, simulation.registry_bundle_ref),
        (views.model_spec_ref, simulation.model_spec_ref),
        (views.input_bindings_ref, foundry.input_bindings_ref),
        (views.bound_state_snapshot_ref, foundry.bound_state_snapshot_ref),
        (views.input_binding_report_ref, foundry.mapping_rules_ref),
    )
    if any(str(ref.artifact_id) != identifier for ref, identifier in pairs):
        raise ValueError("world_model_artifact_view_id_mismatch")
    substrate_id = record.substrate_registry_ref.registry_artifact_ref
    if (views.substrate_registry_ref is None) != (substrate_id is None):
        raise ValueError("world_model_substrate_registry_view_mismatch")
    if views.substrate_registry_ref is not None and str(
        views.substrate_registry_ref.artifact_id
    ) != substrate_id:
        raise ValueError("world_model_substrate_registry_view_mismatch")
    graph_ids = tuple(str(ref.artifact_id) for ref in views.program_graph_refs)
    ncm_ids = tuple(str(ref.artifact_id) for ref in views.ncm_refs)
    if graph_ids != simulation.program_graph_refs:
        raise ValueError("world_model_program_graph_view_id_mismatch")
    if ncm_ids != simulation.ncm_refs:
        raise ValueError("world_model_ncm_view_id_mismatch")


def _strip_non_content_locations(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(payload)
    fabric = cleaned.get("fabric_world_ref")
    if isinstance(fabric, dict):
        fabric = dict(fabric)
        fabric.pop("snapshot_root", None)
        cleaned["fabric_world_ref"] = fabric
    data_forge = cleaned.get("data_forge_binding_ref")
    if isinstance(data_forge, dict):
        data_forge = dict(data_forge)
        data_forge.pop("binding_path", None)
        data_forge.pop("provenance_manifest_ref", None)
        data_forge.pop("quality_gate_refs", None)
        cleaned["data_forge_binding_ref"] = data_forge
    skg = cleaned.get("skg_causal_prior_ref")
    if isinstance(skg, dict):
        skg = dict(skg)
        skg["skg_snapshot_ref"] = _normalize_skg_snapshot_ref(
            str(skg.get("skg_snapshot_ref") or "")
        )
        cleaned["skg_causal_prior_ref"] = skg
    substrate = cleaned.get("substrate_registry_ref")
    if isinstance(substrate, dict):
        substrate = dict(substrate)
        substrate.pop("registry_artifact_ref", None)
        cleaned["substrate_registry_ref"] = substrate
    return cleaned


def _normalize_skg_snapshot_ref(raw_ref: str) -> str:
    prefix = "duckdb://"
    if not raw_ref.startswith(prefix):
        return raw_ref
    locator = raw_ref.removeprefix(prefix)
    path_text, separator, version_text = locator.partition("#v")
    if not path_text or separator != "#v" or not version_text:
        return raw_ref
    try:
        version_id = int(version_text)
    except ValueError:
        return raw_ref
    return f"duckdb://{Path(path_text).name}#v{version_id}"


def _json_ready(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    return value


__all__ = [
    "WORLD_MODEL_RECORD_ARTIFACT_KIND",
    "WORLD_MODEL_RECORD_SCHEMA_NAME",
    "WORLD_MODEL_RECORD_SCHEMA_V2_VERSION",
    "WORLD_MODEL_RECORD_SCHEMA_VERSION",
    "BranchMode",
    "DataForgeBindingRef",
    "DeploymentUpdateRefs",
    "FabricWorldRef",
    "FoundryBindingRef",
    "PolicySlotBinding",
    "ResolvedSubstrateEntryRef",
    "SimulationModelRef",
    "SkgCausalPriorRef",
    "SubstrateLayer",
    "SubstrateRegistryRef",
    "WorldModelArtifactViews",
    "WorldModelLimitations",
    "WorldModelRecord",
    "serialize_world_model_record_for_storage",
    "world_model_record_content_hash",
    "world_model_record_content_hash_from_fields",
]
