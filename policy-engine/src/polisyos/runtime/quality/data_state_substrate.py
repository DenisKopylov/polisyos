"""Data-state substrate lift over real L1/L4/L5 production data.

This bridge owns the S1 orchestration boundary only. L1 DCAT remains the
coverage/availability authority, L5 remains the trust/identification/schema
authority, Data Forge owns snapshot binding evidence, Foundry owns
``GlobalState`` materialization, S0 owns substrate registration, and N3 owns
the ``WorldModelRecord`` lifecycle.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from dataclasses import asdict, dataclass, fields, replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from polisyos.core.contracts import FoundryInputBindingRule
    from polisyos.core.contracts.epoch import ActivatedOverlayAdmissionStatement
    from polisyos.data_forge.read_api.catalog import (
        ActivatedAcquisitionObservationProjection,
        CanonicalAcquisitionObservation,
    )
    from polisyos.fabric.world import WorldSnapshotFactWrite, WorldSnapshotNodeWrite
    from polisyos.foundry.contracts.state import GlobalState
    from polisyos.runtime.quality.acquisition_executor import (
        ActivatedSemanticEpochAdmissionReceipt,
        AdmissionPassport,
    )
    from polisyos.runtime.quality.world_model_record import WorldModelOwnerValues

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core import contracts as core_contracts
from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactStore,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import DataTrust, ValueOuterSet
from polisyos.core.contracts.fabric import (
    DataSnapshot,
    data_snapshot_owner_input_requirements,
    data_snapshot_reference_fields,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.substrate_registry import (
    L5CatalogAuthority,
    SubstrateRegistry,
    SubstrateRegistryError,
    _repo_relative_path,
    build_substrate_registry_from_existing_catalogs,
    default_substrate_catalog_paths,
    l5_owner_scope_identity_refs,
    load_l5_catalog_authority,
    persist_substrate_registry,
    resolve_l5_schema_regime_projection,
)
from polisyos.runtime.quality.world_model_record import (
    BranchMode,
    FabricWorldRef,
    SkgCausalPriorRef,
    WorldModelBuildResult,
    WorldModelLimitations,
    WorldModelRecord,
    WorldModelRecordError,
    WorldModelSimulationInput,
    _load_substrate_registry_artifact_ref,
    build_world_model_record,
    consume_world_model_record_for_simulation,
    world_model_artifact_views,
)

L5SchemaRegimeDenominatorReceipt = core_contracts.L5SchemaRegimeDenominatorReceipt
ScopedSchemaRegimeProjection = core_contracts.ScopedSchemaRegimeProjection
canonical_epoch_bytes = core_contracts.canonical_epoch_bytes

DATA_STATE_SUBSTRATE_SCHEMA_VERSION = "policyos.runtime.data_state_substrate.v1"
ACQUIRED_DATA_STATE_SCHEMA_VERSION = "policyos.runtime.acquisition_data_state.v2"
_DATA_FORGE_SNAPSHOT_PIPELINE = "ukraine"
ACQUIRED_DATA_STATE_LIMITATION_CODES = (
    "source_time_not_established",
    "source_to_target_measurement_contract_not_established",
    "causal_coupling_not_established",
    "acquired_source_row_revalidation_not_established",
)
DEFAULT_L4_SNAPSHOT_ID = "ukraine_server_support_20260410"
DEFAULT_DATA_STATE_PERIOD_START = "2021-12"
DEFAULT_DATA_STATE_PERIOD_END = "2023-07"
DEFAULT_DATA_STATE_VARIABLES = ("avg_income", "employment_rate", "tax_revenue")
DEFAULT_DATA_STATE_FAMILIES = (
    "budget_flows",
    "firm_fundamentals",
    "household_distribution",
    "distress_enforcement",
)
_ACADEMIC_SKG_DB = Path(
    "production_data/policyos_academic_runtime_slim_20260411T112032Z/"
    "academic/graph/scholar_knowledge.duckdb"
)


class DataStateSubstrateError(ValueError):
    """Fail-closed error raised when S1 would fabricate data or authority."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


def _require_workspace_output_path(workspace_root: Path, output_path: Path) -> Path:
    """Resolve one output and require its physical target beneath the caller workspace."""

    try:
        root = Path(workspace_root).resolve(strict=True)
        target = Path(output_path).expanduser()
        if not target.is_absolute():
            target = root / target
        resolved = target.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise DataStateSubstrateError(
            "selected_workspace_output_path_unavailable", str(output_path)
        ) from exc
    if not resolved.is_relative_to(root):
        raise DataStateSubstrateError("selected_workspace_output_path_escape", str(output_path))
    return resolved


def _require_workspace_output_tree(workspace_root: Path, output_root: Path) -> Path:
    """Reject any existing symlink below an output tree that resolves outside the workspace."""

    root = Path(workspace_root).resolve(strict=True)
    directory = _require_workspace_output_path(root, output_root)
    if not directory.exists():
        return directory
    if not directory.is_dir():
        raise DataStateSubstrateError(
            "selected_workspace_output_tree_not_directory", str(output_root)
        )
    try:
        for candidate in directory.rglob("*"):
            if candidate.is_symlink():
                _require_workspace_output_path(root, candidate)
    except (OSError, RuntimeError) as exc:
        raise DataStateSubstrateError(
            "selected_workspace_output_tree_unavailable", str(output_root)
        ) from exc
    return directory


def _data_forge_snapshot_role() -> str:
    """Resolve the canonical Data Forge role lazily through its public facade."""
    role_surface = data_forge_read_api.pipeline_binding_surface(_DATA_FORGE_SNAPSHOT_PIPELINE)
    if role_surface is None:
        raise DataStateSubstrateError(
            "data_forge_snapshot_pipeline_binding_missing",
            _DATA_FORGE_SNAPSHOT_PIPELINE,
        )
    return role_surface[0]


class _StrictModel(BaseModel):
    """Strict immutable base for data-state substrate DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class L1VariableAvailability(_StrictModel):
    """L1 DCAT coverage decision for one required canonical variable."""

    variable_id: str = Field(..., min_length=1)
    status: Literal["available", "unavailable"]
    dataset_count: int = Field(..., ge=0)
    metric_binding_count: int = Field(..., ge=0)
    observation_count: int = Field(..., ge=0)
    coverage_ref: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _status_matches_owner_counts(self) -> L1VariableAvailability:
        count = self.dataset_count + self.metric_binding_count + self.observation_count
        if self.status == "unavailable" and count != 0:
            raise ValueError("l1_unavailable_counts_nonzero")
        if self.status == "available" and count == 0:
            raise ValueError("l1_available_counts_empty")
        return self


class L5FamilyAuthority(_StrictModel):
    """L5 trust/identification cap for one bound observation family."""

    family_id: str = Field(..., min_length=1)
    coverage_score: float = Field(..., ge=0.0, le=1.0)
    trust_tier: str = Field(..., min_length=1)
    trust_cap: float = Field(..., ge=0.0, le=1.0)
    trust_multiplier: float = Field(..., ge=0.0, le=1.0)
    min_coverage: float | None = Field(None, ge=0.0, le=1.0)
    max_coverage: float | None = Field(None, ge=0.0, le=1.0)
    promotion_floor: float = Field(..., ge=0.0, le=1.0)
    identification_mode: str = Field(..., min_length=1)
    value_authority: Literal["point", "bounds", "proxy_bounds", "limited"]
    measurement_registry_ref: str = Field(..., min_length=1)
    identification_registry_ref: str = Field(..., min_length=1)


class L5FamilyBindingProfile(_StrictModel):
    """Combined L5 family authority and schema-regime decision for S1."""

    schema_version: str = DATA_STATE_SUBSTRATE_SCHEMA_VERSION
    period_start: str = Field(..., min_length=1)
    period_end: str = Field(..., min_length=1)
    schema_regime_status: Literal[
        "single_regime",
        "boundary_buffer_flagged",
        "spans_changepoint_flagged",
    ]
    regime_ids: tuple[str, ...]
    changepoint_id: str | None = None
    changepoint_period: str | None = None
    boundary_buffer_periods: int = Field(..., ge=0)
    families: tuple[L5FamilyAuthority, ...]

    @field_validator("families", "regime_ids")
    @classmethod
    def _not_empty(cls, value: tuple[Any, ...]) -> tuple[Any, ...]:
        if not value:
            raise ValueError("l5_binding_profile_empty")
        return value

    def family_authority(self, family_id: str) -> L5FamilyAuthority:
        """Return the L5 authority row for ``family_id``."""

        for family in self.families:
            if family.family_id == family_id:
                return family
        raise DataStateSubstrateError("l5_family_unidentified", family_id)


class ControlledAcquisitionSlotBinding(_StrictModel):
    """Declared candidate-only mapping from an admitted variable to a Foundry slot.

    This profile forwards one scalar without unit conversion. It records the
    requested target while keeping measurement and causal contracts unresolved.
    A production mapping requires its own admitted source contract; this DTO
    cannot make one authoritative.
    """

    schema_version: Literal["polisyos.runtime.controlled_acquisition_slot_binding.v1"] = (
        "polisyos.runtime.controlled_acquisition_slot_binding.v1"
    )
    profile_selection_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    canonical_variable_id: str = Field(..., min_length=1)
    target_slot_id: str = Field(..., min_length=1)
    source_to_target_semantics: Literal["candidate_value_forwarded_without_conversion"] = (
        "candidate_value_forwarded_without_conversion"
    )


@dataclass(frozen=True)
class DataStateMaterializationResult:
    """CAS and Data Forge artifacts emitted before N3 binds the world."""

    data_snapshot_ref: ArtifactRef
    data_forge_snapshot_binding_path: Path
    data_forge_role: str
    data_snapshot_stats: dict[str, Any]
    l1_availability: tuple[L1VariableAvailability, ...]
    l5_profile: L5FamilyBindingProfile
    payload_content_hash: str
    snapshot_id: str


@dataclass(frozen=True)
class AcquiredObservationDataSnapshotResult:
    """Candidate DataSnapshot emitted from one owner-activated observation."""

    data_snapshot_ref: ArtifactRef
    data_forge_snapshot_binding_path: Path
    data_forge_role: str
    snapshot_id: str
    payload_content_hash: str
    selected_dataset_id: str
    selected_observation_id: str
    source_time_status: Literal["not_established"]
    observation_projection: ActivatedAcquisitionObservationProjection
    foundry_binding_rule: FoundryInputBindingRule


@dataclass(frozen=True)
class AcquiredObservationDataPreparation:
    """Write-free, content-bound input prepared for acquisition materialization.

    The effective payload is retained as JSON bytes rather than a mutable
    mapping. Its recomputable digest detects content drift; it is not evidence
    of owner issuance or continuing eligibility. The materializer reconstructs
    the current owner preparation, compares every dataclass field, and consumes
    only that freshly resolved result before its first write.
    """

    payload_json: bytes
    payload_sha256: str
    preparation_sha256: str
    base_data_snapshot_ref: ArtifactRef
    receipt_ref: ArtifactRef
    selected_profile: ControlledAcquisitionSlotBinding
    observation_projection: ActivatedAcquisitionObservationProjection
    selected_dataset_id: str
    selected_observation_id: str
    selected_row_content_sha256: str
    base_snapshot_id: str
    transaction_time_text: str
    lineage_inputs: tuple[Any, ...]
    foundry_binding_rule: FoundryInputBindingRule

    def validate_content_binding(self) -> None:
        """Reject any changed field before the materializer's first write."""

        if _acquisition_preparation_sha256(self, include_digest=False) != self.preparation_sha256:
            raise DataStateSubstrateError("acquisition_preparation_content_changed")

    def payload(self) -> dict[str, Any]:
        """Return a fresh payload after checking the prepared content binding."""

        self.validate_content_binding()
        if hashlib.sha256(self.payload_json).hexdigest() != self.payload_sha256:
            raise DataStateSubstrateError("acquisition_preparation_content_changed")
        value = json.loads(self.payload_json)
        if not isinstance(value, dict):
            raise DataStateSubstrateError("acquisition_preparation_payload_not_object")
        return value


def _acquisition_preparation_sha256(
    prepared: AcquiredObservationDataPreparation,
    *,
    include_digest: bool,
) -> str:
    """Bind every prepared field without retaining a mutable semantic mapping."""

    fields = {
        "payload_sha256": prepared.payload_sha256,
        "base_data_snapshot_ref": prepared.base_data_snapshot_ref.model_dump(mode="json"),
        "receipt_ref": prepared.receipt_ref.model_dump(mode="json"),
        "selected_profile": prepared.selected_profile.model_dump(mode="json"),
        "observation_projection": prepared.observation_projection.model_dump(mode="json"),
        "selected_dataset_id": prepared.selected_dataset_id,
        "selected_observation_id": prepared.selected_observation_id,
        "selected_row_content_sha256": prepared.selected_row_content_sha256,
        "base_snapshot_id": prepared.base_snapshot_id,
        "transaction_time_text": prepared.transaction_time_text,
        "lineage_inputs": [item.model_dump(mode="json") for item in prepared.lineage_inputs],
        "foundry_binding_rule": prepared.foundry_binding_rule.model_dump(mode="json"),
    }
    if include_digest:
        fields["preparation_sha256"] = prepared.preparation_sha256
    encoded = json.dumps(fields, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class AcquiredObservationWorldBuildResult:
    """Candidate-limited WMR and Foundry state for an admitted acquisition row."""

    materialization: AcquiredObservationDataSnapshotResult
    world_model: WorldModelBuildResult
    simulation_input: WorldModelSimulationInput
    model_spec: ModelSpec
    registry_bundle_ref: ArtifactRef
    substrate_registry_ref: ArtifactRef


@dataclass(frozen=True)
class ProductionDataStateWorldBuildResult:
    """End-to-end S1 world build result with the N3/Foundry outputs."""

    materialization: DataStateMaterializationResult
    world_model: WorldModelBuildResult
    simulation_input: WorldModelSimulationInput
    model_spec: ModelSpec
    registry_bundle_ref: ArtifactRef
    substrate_registry_ref: ArtifactRef

    @property
    def data_snapshot_stats(self) -> dict[str, Any]:
        """Return materialization stats for probe assertions."""

        return self.materialization.data_snapshot_stats


@dataclass(frozen=True)
class _DataStatePaths:
    """Canonical real-data paths consumed by S1."""

    l1_dcat_path: Path
    agent_registry_full: Path
    firm_fundamentals_annual: Path
    budget_flows_monthly_sparse: Path
    corrected_firm_panels: Path
    calibrated_household_cells: Path


def l1_dcat_variable_availability(
    repo_root: Path,
    variable_id: str,
    *,
    overlay_path: Path | None = None,
    production_data_root: Path | None = None,
) -> L1VariableAvailability:
    """Resolve required-vs-available status from one selected L1 catalog.

    ``repo_root`` remains the code and acquisition-overlay owner. The optional
    ``production_data_root`` selects only the catalog input; it does not grant
    source authority or establish currentness.
    """

    variable = variable_id.strip()
    if not variable:
        raise DataStateSubstrateError("l1_variable_empty")
    code_root = Path(repo_root).resolve()
    data_root = (
        Path(production_data_root).resolve() if production_data_root is not None else code_root
    )
    dcat_path = default_substrate_catalog_paths(
        code_root,
        source_owner_root=data_root if production_data_root is not None else None,
    ).l1_dcat_path
    from polisyos.runtime.quality.substrate_registry import (
        current_catalog_serving_source,
    )

    catalog_source = current_catalog_serving_source()
    if not dcat_path.exists():
        raise DataStateSubstrateError("l1_dcat_missing", dcat_path.as_posix())
    if production_data_root is not None:
        try:
            _repo_relative_path(dcat_path, repo_root=data_root)
        except SubstrateRegistryError as exc:
            raise DataStateSubstrateError("l1_dcat_source_path_unbound", str(exc)) from exc

    selected_overlay = overlay_path or (
        data_forge_read_api.catalog.default_acquisition_overlay_path(code_root)
    )
    from polisyos.runtime.quality.substrate_registry import catalog_source_reader

    try:
        with catalog_source_reader(
            code_root,
            overlay_path=selected_overlay,
            production_data_root=data_root if production_data_root is not None else None,
        ) as reader:
            metric_binding_count, observation_count, dataset_count = (
                reader.variable_availability_counts(variable)
            )
    except data_forge_read_api.catalog.CatalogSelectionError as exc:
        count_errors = {
            "catalog_variable_count_row_missing": "l1_dcat_scalar_row_missing",
            "catalog_variable_count_row_shape_invalid": "l1_dcat_scalar_row_shape_invalid",
            "catalog_variable_count_value_invalid": "l1_dcat_scalar_value_invalid",
        }
        raise DataStateSubstrateError(
            count_errors.get(exc.code, "l1_dcat_read_session_invalid"), str(exc)
        ) from exc

    return L1VariableAvailability(
        variable_id=variable,
        status=(
            "available"
            if metric_binding_count > 0 or observation_count > 0 or dataset_count > 0
            else "unavailable"
        ),
        dataset_count=dataset_count,
        metric_binding_count=metric_binding_count,
        observation_count=observation_count,
        coverage_ref=(
            f"catalog_source://{dcat_path.as_posix()}#variable/{variable}"
            if catalog_source is not None
            and catalog_source.selection_basis == "explicit_path_candidate_only"
            else (
                f"repo://production_data/datasets_full_phase3full_20260327_183054/"
                f"dataset_catalog.duckdb#variable/{variable}"
            )
        ),
    )


def build_l5_family_binding_profile(
    repo_root: Path,
    *,
    families: Sequence[str],
    period_start: str,
    period_end: str,
    scope_identity_ref: str | None = None,
    production_data_root: Path | None = None,
) -> L5FamilyBindingProfile:
    """Build the L5 honesty profile from the code root and selected data owner."""

    code_root = Path(repo_root).resolve()
    data_root = (
        Path(production_data_root).resolve() if production_data_root is not None else code_root
    )
    l5 = load_l5_catalog_authority(
        default_substrate_catalog_paths(
            code_root,
            source_owner_root=data_root if production_data_root is not None else None,
        ),
        repo_root=code_root,
        source_owner_root=data_root if production_data_root is not None else None,
    )
    owner_scopes = l5_owner_scope_identity_refs(l5)
    if scope_identity_ref is None:
        if len(owner_scopes) != 1:
            raise DataStateSubstrateError("l5_scope_identity_not_established")
        scope_identity_ref = owner_scopes[0]
    elif scope_identity_ref not in owner_scopes:
        raise DataStateSubstrateError("l5_scope_identity_not_owner_declared")
    resolved_families: list[L5FamilyAuthority] = []
    for family_id in families:
        family = str(family_id).strip()
        if not family:
            raise DataStateSubstrateError("l5_family_empty")
        if family not in l5.coverage_rules or family not in l5.identification_modes:
            raise DataStateSubstrateError("l5_family_unidentified", family)
        tier = l5.expected_trust_tier(family)
        mode = l5.identification_modes[family]
        resolved_families.append(
            L5FamilyAuthority(
                family_id=family,
                coverage_score=float(l5.coverage_rules[family]),
                trust_tier=tier.tier,
                trust_cap=tier.trust_cap,
                trust_multiplier=tier.trust_multiplier,
                min_coverage=tier.min_coverage,
                max_coverage=tier.max_coverage,
                promotion_floor=l5.minimum_positive_coverage_floor(default=1.0),
                identification_mode=mode,
                value_authority=_value_authority_for_identification(mode),
                measurement_registry_ref=f"{l5.measurement_registry_ref}#/coverage_rules/{family}",
                identification_registry_ref=f"{l5.identification_mode_registry_ref}#/{family}",
            )
        )
    receipt, projection = resolve_l5_schema_regime_projection(
        l5,
        scope_identity_ref=scope_identity_ref,
        valid_effect_value=date.fromisoformat(f"{period_end}-01"),
        authority_purpose="data_state_binding",
    )
    regime = _schema_regime_decision(
        l5,
        receipt=receipt,
        projection=projection,
        period_start=period_start,
        period_end=period_end,
    )
    return L5FamilyBindingProfile(
        period_start=period_start,
        period_end=period_end,
        families=tuple(resolved_families),
        **regime,
    )


def materialize_l4_data_state_snapshot(
    store: FileSystemCAS,
    *,
    repo_root: Path,
    workspace_dir: Path,
    agent_limit: int | None = 1024,
    required_l1_variables: Sequence[str] = DEFAULT_DATA_STATE_VARIABLES,
    families: Sequence[str] = DEFAULT_DATA_STATE_FAMILIES,
    substrate_registry: SubstrateRegistry | None = None,
    period_start: str = DEFAULT_DATA_STATE_PERIOD_START,
    period_end: str = DEFAULT_DATA_STATE_PERIOD_END,
    production_data_root: Path | None = None,
) -> DataStateMaterializationResult:
    """Persist a real L4 data-state ``DataSnapshot`` and Data Forge binding.

    ``agent_limit`` may be ``None`` for a full local materialization, but probe
    runs should pass a representative bound so the same production binding path
    remains cheap enough for targeted verification.
    """

    if agent_limit is not None and agent_limit <= 0:
        raise DataStateSubstrateError("production_data_state_empty")
    root = repo_root.resolve()
    data_root = Path(production_data_root).resolve() if production_data_root is not None else root
    if production_data_root is not None:
        _require_split_data_workspace(
            workspace_dir,
            code_root=root,
            data_root=data_root,
            cas_root=store.root,
        )
        _require_workspace_output_tree(workspace_dir, store.root)
    paths = _default_data_state_paths(
        root,
        production_data_root=data_root if production_data_root is not None else None,
    )
    _require_paths(
        paths,
        production_data_root=data_root if production_data_root is not None else None,
    )
    availability = tuple(
        l1_dcat_variable_availability(
            root,
            variable,
            production_data_root=data_root if production_data_root is not None else None,
        )
        for variable in required_l1_variables
    )
    unavailable = [item.variable_id for item in availability if item.status == "unavailable"]
    if unavailable:
        raise DataStateSubstrateError("l1_variable_unavailable", ",".join(unavailable))
    l5_profile = build_l5_family_binding_profile(
        root,
        families=families,
        period_start=period_start,
        period_end=period_end,
        production_data_root=data_root if production_data_root is not None else None,
    )
    if substrate_registry is None:
        substrate_registry = build_substrate_registry_from_existing_catalogs(
            root,
            source_owner_root=data_root if production_data_root is not None else None,
        )
    world_preimage_ref = _world_preimage_ref(
        substrate_version_id=substrate_registry.substrate_version_id,
        agent_limit=agent_limit,
        required_l1_variables=required_l1_variables,
        families=families,
        period_start=period_start,
        period_end=period_end,
        branch_mode=BranchMode.OBSERVED.value,
    )

    payload, stats = _project_real_l4_payload(
        paths,
        agent_limit=agent_limit,
        l5_profile=l5_profile,
        world_model_record_ref=world_preimage_ref,
    )
    bound_agent_count = int(stats.get("bound_agent_count") or 0)
    if bound_agent_count <= 0:
        raise DataStateSubstrateError("production_data_state_empty")

    profile_hash = gy_content_hash(l5_profile.model_dump(mode="json"))
    payload_with_meta = {
        **payload,
        "_policyos_data_state": {
            "schema_version": DATA_STATE_SUBSTRATE_SCHEMA_VERSION,
            "source_mode": "real_l4_representative_slice"
            if agent_limit is not None
            else "real_l4_full_projection",
            "l1_availability": [item.model_dump(mode="json") for item in availability],
            "l5_profile": l5_profile.model_dump(mode="json"),
            "l5_profile_hash": profile_hash,
            "world_preimage_ref": world_preimage_ref,
            "source_paths": _relative_source_paths(paths, data_root),
            "stats": stats,
        },
    }
    if production_data_root is not None:
        _require_workspace_output_tree(workspace_dir, store.root)
    payload_ref = store.put_json(
        payload_with_meta,
        PutOptions(
            kind="fabric.production_data_state_payload",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.runtime.quality.DataStatePayload",
                version=DATA_STATE_SUBSTRATE_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    _require_selected_profile(payload_ref, "data_state_payload_profile_unverified")
    if production_data_root is not None:
        _require_workspace_output_tree(workspace_dir, store.root)
    payload_content_hash = str(payload_ref.artifact_id)
    snapshot_id = _snapshot_id(agent_limit=agent_limit, payload_hash=payload_content_hash)
    data_snapshot = DataSnapshot(
        data_ref=payload_ref,
        stats={
            "snapshot_id": snapshot_id,
            "source_mode": str(payload_with_meta["_policyos_data_state"]["source_mode"]),
            "bound_agent_count": bound_agent_count,
            "l4_total_rows.agent_registry_full": int(stats["l4_total_rows"]["agent_registry_full"]),
            "l4_total_rows.budget_flows_monthly_sparse": int(
                stats["l4_total_rows"]["budget_flows_monthly_sparse"]
            ),
            "l5_profile_hash": profile_hash,
            "world_preimage_ref": world_preimage_ref,
        },
        notes=[
            "gy_s1_real_l4_data_state",
            "data_forge_snapshot_binding:finalize_snapshot",
            "foundry_binding_owner:polisyos.foundry.data_plane.bindings.build_input_bindings",
            f"schema_regime_status:{l5_profile.schema_regime_status}",
        ],
    )
    if production_data_root is not None:
        _require_workspace_output_tree(workspace_dir, store.root)
    data_snapshot_ref = store.put_json(
        data_snapshot,
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=[input_ref_from_artifact_ref(payload_ref, role="payload.real_l4")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    _require_selected_profile(data_snapshot_ref, "data_state_snapshot_profile_unverified")
    if production_data_root is not None:
        _require_workspace_output_tree(workspace_dir, store.root)
    binding_path = _write_data_forge_snapshot_binding(
        workspace_dir=workspace_dir,
        snapshot_id=snapshot_id,
        payload=payload_with_meta,
        payload_content_hash=payload_content_hash,
        confine_outputs=production_data_root is not None,
    )
    if production_data_root is not None:
        _require_workspace_output_tree(workspace_dir, store.root)
    stats = {
        **stats,
        "source_mode": data_snapshot.stats["source_mode"],
        "payload_content_hash": payload_content_hash,
        "snapshot_id": snapshot_id,
        "l5_profile_hash": profile_hash,
        "world_preimage_ref": world_preimage_ref,
    }
    return DataStateMaterializationResult(
        data_snapshot_ref=data_snapshot_ref,
        data_forge_snapshot_binding_path=binding_path,
        data_forge_role=_data_forge_snapshot_role(),
        data_snapshot_stats=stats,
        l1_availability=availability,
        l5_profile=l5_profile,
        payload_content_hash=payload_content_hash,
        snapshot_id=snapshot_id,
    )


def prepare_acquired_observation_snapshot(
    store: ArtifactStore,
    *,
    base_data_snapshot_ref: ArtifactRef,
    overlay: object,
    receipt_ref: ArtifactRef,
    passport: object,
    authority: object,
    observation_id: str,
    slot_binding: ControlledAcquisitionSlotBinding,
    transaction_time: datetime,
) -> AcquiredObservationDataPreparation:
    """Prepare an owner-verified acquired observation without writing artifacts.

    The projection is resolved again through Data Forge's canonical active-state
    reader. This S1 owner checks the selected row against that owner readback,
    preserves the existing snapshot payload, and prepares the exact lineage and
    Foundry rule later consumed by the materializer. It emits no artifact or
    workspace file.
    Source time, source-to-target measurement equivalence, and causal coupling
    remain declared limitations. ``transaction_time`` records only this
    materialization event; it is never substituted for source observation time.

    Args:
        store: The exact runtime-supplied ArtifactStore used by the tenant.
        base_data_snapshot_ref: Current DataSnapshot whose world payload is
            extended by the admitted observation.
        overlay: Canonical Data Forge ``CatalogAcquisitionOverlay`` owner.
        receipt_ref: Exact activated receipt selected by the world-growth owner.
        passport: Owner-verified acquisition passport for ``receipt_ref``.
        authority: The same canonical acquisition authority used for admission.
        observation_id: Exact row identity selected from the active projection.
        slot_binding: Explicit controlled-candidate map to one Foundry slot.
        transaction_time: Time this controlled candidate snapshot is emitted.

    Returns:
        Immutable, content-bound inputs for the existing materializer.

    Raises:
        DataStateSubstrateError: If the base snapshot, selected row, candidate
            mapping, or transaction time cannot be verified.
    """
    from polisyos.data_forge.read_api.catalog import (
        ActivatedAcquisitionObservationProjection,
        CatalogAcquisitionOverlay,
    )
    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport

    if not isinstance(slot_binding, ControlledAcquisitionSlotBinding):
        raise DataStateSubstrateError("acquisition_slot_binding_untyped")
    if type(overlay) is not CatalogAcquisitionOverlay:
        raise DataStateSubstrateError("acquisition_overlay_owner_untyped")
    if type(passport) is not AdmissionPassport:
        raise DataStateSubstrateError("acquisition_passport_owner_untyped")
    if not isinstance(receipt_ref, ArtifactRef):
        raise DataStateSubstrateError("acquisition_activation_ref_untyped")
    _require_selected_profile(receipt_ref, "acquisition_activation_profile_unselected")
    try:
        owner_projection = overlay.read_activated_semantic_epoch_observations(
            receipt_ref=receipt_ref,
            artifact_store=store,
            passport=passport,
            authority=authority,
        )
        selected_profile = ControlledAcquisitionSlotBinding.model_validate(
            slot_binding.model_dump(mode="python")
        )
        selected_projection = ActivatedAcquisitionObservationProjection.model_validate(
            owner_projection.model_dump(mode="python")
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise DataStateSubstrateError(
            "acquisition_projection_or_mapping_invalid", str(exc)
        ) from exc
    return _prepare_acquired_observation_snapshot_from_projection(
        store,
        base_data_snapshot_ref=base_data_snapshot_ref,
        selected_projection=selected_projection,
        selected_profile=selected_profile,
        observation_id=observation_id,
        receipt_ref=receipt_ref,
        transaction_time=transaction_time,
    )


def _prepare_acquired_observation_snapshot_from_projection(
    store: ArtifactStore,
    *,
    base_data_snapshot_ref: ArtifactRef,
    selected_projection: ActivatedAcquisitionObservationProjection,
    selected_profile: ControlledAcquisitionSlotBinding,
    observation_id: str,
    receipt_ref: ArtifactRef,
    transaction_time: datetime,
) -> AcquiredObservationDataPreparation:
    """Shared actual payload/history/rule construction after source-owner replay."""
    from polisyos.core.artifacts import load_core_json_artifact

    _require_selected_profile(
        selected_projection.receipt_ref,
        "acquisition_receipt_profile_unselected",
    )
    _require_selected_profile(
        selected_projection.passport_ref,
        "acquisition_passport_profile_unselected",
    )
    if not observation_id.strip():
        raise DataStateSubstrateError("acquisition_observation_id_empty")
    if (
        selected_projection.source_time_status != "not_established"
        or selected_projection.variable_id != selected_profile.canonical_variable_id
    ):
        raise DataStateSubstrateError("acquisition_projection_mapping_mismatch")
    selected_rows = [
        row
        for row in selected_projection.observations
        if row.observation.observation_id == observation_id
    ]
    if len(selected_rows) != 1:
        raise DataStateSubstrateError(
            "acquisition_selected_observation_not_unique",
            observation_id,
        )
    selected_row = selected_rows[0]
    observation = selected_row.observation
    if observation.canonical_var != selected_profile.canonical_variable_id:
        raise DataStateSubstrateError("acquisition_selected_variable_mismatch")
    if transaction_time.tzinfo is None or transaction_time.utcoffset() is None:
        raise DataStateSubstrateError("acquisition_transaction_time_must_be_aware")

    _require_selected_profile(
        base_data_snapshot_ref,
        "acquisition_base_snapshot_profile_unselected",
    )
    try:
        base_manifest = store.get_manifest_by_profile(
            base_data_snapshot_ref.artifact_id,
            base_data_snapshot_ref.manifest_profile_sha256,
        )
        if (
            base_manifest.kind != "fabric.data_snapshot"
            or base_manifest.media_type != "application/json"
            or any(edge.manifest_profile_sha256 is None for edge in base_manifest.inputs)
        ):
            raise DataStateSubstrateError("acquisition_base_snapshot_profile_unselected")
        base_snapshot = DataSnapshot.model_validate(
            load_core_json_artifact(store, base_data_snapshot_ref)
        )
        _require_selected_profile(
            base_snapshot.data_ref,
            "acquisition_base_snapshot_child_profile_unselected",
        )
        # A generic schema-0.2 snapshot has no schema-0.3 owner-lineage DTO.
        # Reconcile its actual typed references, then let the same version-aware
        # canonical owner verifier below validate all transport/owner relations.
        selected_children = tuple(
            ref
            for name in data_snapshot_reference_fields()
            if (ref := getattr(base_snapshot, name)) is not None
        )
        if base_snapshot.source_lineage is not None:
            selected_children += tuple(
                ref for ref, _role in data_snapshot_owner_input_requirements(base_snapshot)
            )
        if any(ref.manifest_profile_sha256 is None for ref in selected_children):
            raise DataStateSubstrateError("acquisition_base_snapshot_child_profile_unselected")
        from polisyos.runtime.quality.data_snapshot_lineage import (
            validate_data_snapshot_owner_lineage,
        )

        try:
            validate_data_snapshot_owner_lineage(
                store,
                base_data_snapshot_ref,
                base_snapshot,
                candidate_only=True,
            )
        except (OSError, TypeError, ValueError, RuntimeError) as exc:
            raise DataStateSubstrateError(
                "acquisition_base_snapshot_owner_lineage_invalid", str(exc)
            ) from exc
        snapshot_stats = base_snapshot.stats
        base_snapshot_id = (
            str(snapshot_stats.get("snapshot_id") or snapshot_stats.get("version_id") or "")
            if isinstance(snapshot_stats, dict)
            else ""
        )
        if not base_snapshot_id:
            raise DataStateSubstrateError("acquisition_base_snapshot_version_missing")
        base_payload_manifest = store.get_manifest_by_profile(
            base_snapshot.data_ref.artifact_id,
            base_snapshot.data_ref.manifest_profile_sha256,
        )
        if base_payload_manifest.media_type != "application/json":
            raise DataStateSubstrateError("acquisition_base_payload_not_json")
        raw_payload = load_core_json_artifact(store, base_snapshot.data_ref)
    except DataStateSubstrateError:
        raise
    except Exception as exc:
        raise DataStateSubstrateError("acquisition_base_snapshot_unresolved", str(exc)) from exc
    if not isinstance(raw_payload, dict):
        raise DataStateSubstrateError("acquisition_base_payload_not_object")

    payload = dict(raw_payload)
    raw_acquisition = payload.get("acquisition", {})
    if not isinstance(raw_acquisition, dict):
        raise DataStateSubstrateError("acquisition_payload_owner_field_invalid")
    acquisition = dict(raw_acquisition)
    history = payload.get("_policyos_acquisition_history", [])
    if not isinstance(history, list) or any(not isinstance(item, dict) for item in history):
        raise DataStateSubstrateError("acquisition_history_invalid")
    prior_rows = [
        item
        for item in history
        if item.get("dataset_id") == observation.dataset_id
        and item.get("observation_id") == observation.observation_id
    ]
    if prior_rows and any(
        item.get("row_content_sha256") != selected_row.row_content_sha256 for item in prior_rows
    ):
        raise DataStateSubstrateError("acquisition_observation_identity_reused")
    if not prior_rows:
        history.append(
            {
                "observation_id": observation.observation_id,
                "dataset_id": observation.dataset_id,
                "row_content_sha256": selected_row.row_content_sha256,
                "projection_content_sha256": (selected_projection.projection_content_sha256),
                "observation": observation.model_dump(mode="json"),
            }
        )
    selected_value = _acquired_observation_selected_value(
        observation, selected_row.row_content_sha256
    )
    acquisition["selected"] = selected_value
    payload["acquisition"] = acquisition
    payload["_policyos_acquisition_history"] = history
    transaction_time_text = transaction_time.astimezone(UTC).isoformat()
    payload["_policyos_acquisition"] = {
        "schema_version": ACQUIRED_DATA_STATE_SCHEMA_VERSION,
        "base_data_snapshot_id": str(base_data_snapshot_ref.artifact_id),
        "base_data_snapshot_ref": base_data_snapshot_ref.model_dump(mode="json"),
        "source_time_status": "not_established",
        "selected_observation_id": observation.observation_id,
        "selected_dataset_id": observation.dataset_id,
        "selected_row_content_sha256": selected_row.row_content_sha256,
        "projection_content_sha256": selected_projection.projection_content_sha256,
        "receipt_ref": selected_projection.receipt_ref.model_dump(mode="json"),
        "receipt_content_sha256": selected_projection.receipt_content_sha256,
        "passport_ref": selected_projection.passport_ref.model_dump(mode="json"),
        "passport_content_sha256": selected_projection.passport_content_sha256,
        "admission_content_sha256": selected_projection.admission_content_sha256,
        "epoch_id": selected_projection.epoch_id,
        "slot_binding": selected_profile.model_dump(mode="json"),
        "materialized_at_transaction_time": transaction_time_text,
        "limitation_codes": list(ACQUIRED_DATA_STATE_LIMITATION_CODES),
    }

    lineage_inputs = (
        input_ref_from_artifact_ref(base_data_snapshot_ref, role="input.base_data_snapshot"),
        input_ref_from_artifact_ref(
            selected_projection.receipt_ref,
            role="evidence.overlay_admission_receipt",
        ),
        input_ref_from_artifact_ref(
            selected_projection.passport_ref,
            role="evidence.acquisition_passport",
        ),
    )
    foundry_binding_rule = acquired_observation_binding_rule(
        observation=observation,
        slot_binding=selected_profile,
    )
    payload_json = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    prepared = AcquiredObservationDataPreparation(
        payload_json=payload_json,
        payload_sha256=hashlib.sha256(payload_json).hexdigest(),
        preparation_sha256="",
        base_data_snapshot_ref=base_data_snapshot_ref,
        receipt_ref=receipt_ref,
        selected_profile=selected_profile,
        observation_projection=selected_projection,
        selected_dataset_id=observation.dataset_id,
        selected_observation_id=observation.observation_id,
        selected_row_content_sha256=selected_row.row_content_sha256,
        base_snapshot_id=base_snapshot_id,
        transaction_time_text=transaction_time_text,
        lineage_inputs=lineage_inputs,
        foundry_binding_rule=foundry_binding_rule,
    )
    return replace(
        prepared,
        preparation_sha256=_acquisition_preparation_sha256(prepared, include_digest=False),
    )


def acquired_observation_binding_rule(
    *,
    observation: CanonicalAcquisitionObservation,
    slot_binding: ControlledAcquisitionSlotBinding,
) -> FoundryInputBindingRule:
    """Build the exact existing controlled rule, including occurrence notes.

    Callers must compare this entire rule with the selected actual Foundry rule
    before using its purpose-specific effective projection.
    """
    from polisyos.core.contracts import FoundryInputBindingRule
    from polisyos.data_forge.read_api.catalog import CanonicalAcquisitionObservation

    if type(observation) is not CanonicalAcquisitionObservation:
        raise DataStateSubstrateError("acquisition_semantic_observation_untyped")
    if type(slot_binding) is not ControlledAcquisitionSlotBinding:
        raise DataStateSubstrateError("acquisition_slot_binding_untyped")
    observation = CanonicalAcquisitionObservation.model_validate(
        observation.model_dump(mode="python")
    )
    slot_binding = ControlledAcquisitionSlotBinding.model_validate(
        slot_binding.model_dump(mode="python")
    )
    if observation.canonical_var != slot_binding.canonical_variable_id:
        raise DataStateSubstrateError("acquisition_selected_variable_mismatch")
    token = re.sub(r"[^a-zA-Z0-9_-]+", "_", observation.canonical_var).strip("_")
    return FoundryInputBindingRule(
        binding_id=f"acquisition.{token}.candidate",
        source_path="acquisition.selected.value",
        target_slot_id=slot_binding.target_slot_id,
        required=True,
        notes=[
            "candidate_only_controlled_mapping",
            "source_time_not_established",
            "source_to_target_measurement_contract_not_established",
            f"profile_selection_ref:{slot_binding.profile_selection_ref}",
            f"dataset_id:{observation.dataset_id}",
            f"observation_id:{observation.observation_id}",
        ],
    )


def _acquired_observation_selected_value(
    observation: CanonicalAcquisitionObservation, row_content_sha256: str
) -> dict[str, object]:
    """Build the exact owner-selected payload value used by the materializer."""
    return {
        "value": observation.value,
        "canonical_variable_id": observation.canonical_var,
        "observation_id": observation.observation_id,
        "dataset_id": observation.dataset_id,
        "row_content_sha256": row_content_sha256,
        "source_time_status": "not_established",
        "reported_time_coordinate": {
            "year": observation.year,
            "survey_year": observation.survey_year,
            "wave": observation.wave,
        },
    }


def _prepared_acquired_observation(
    prepared: AcquiredObservationDataPreparation,
) -> CanonicalAcquisitionObservation:
    """Reconcile all selected row and payload bindings on one preparation."""
    from polisyos.data_forge.read_api.catalog import ActivatedAcquisitionObservationProjection
    from polisyos.fabric import data_plane

    if type(prepared) is not AcquiredObservationDataPreparation:
        raise DataStateSubstrateError("acquisition_preparation_untyped")
    prepared.validate_content_binding()
    projection = ActivatedAcquisitionObservationProjection.model_validate(
        prepared.observation_projection.model_dump(mode="python")
    )
    selected = tuple(
        row
        for row in projection.observations
        if row.observation.observation_id == prepared.selected_observation_id
        and row.observation.dataset_id == prepared.selected_dataset_id
    )
    if len(selected) != 1:
        raise DataStateSubstrateError("acquisition_semantic_selected_row_not_unique")
    row = selected[0]
    observation = row.observation
    payload = prepared.payload()
    acquisition = payload.get("acquisition")
    if (
        row.row_content_sha256 != prepared.selected_row_content_sha256
        or data_plane.content_sha256(observation.model_dump(mode="json"))
        != prepared.selected_row_content_sha256
        or not isinstance(acquisition, dict)
        or acquisition.get("selected")
        != _acquired_observation_selected_value(observation, prepared.selected_row_content_sha256)
    ):
        raise DataStateSubstrateError("acquisition_semantic_selected_payload_mismatch")
    expected_rule = acquired_observation_binding_rule(
        observation=observation, slot_binding=prepared.selected_profile
    )
    if prepared.foundry_binding_rule != expected_rule:
        raise DataStateSubstrateError("acquisition_semantic_full_binding_rule_mismatch")
    return observation


def acquired_observation_binding_rule_values(
    prepared: AcquiredObservationDataPreparation,
) -> dict[str, object]:
    """Project effective rule values only after full generated-rule reconciliation.

    ``notes`` is one known owner-produced report field. No note value or prefix
    is selectively stripped. An added or changed note refuses before projection.
    """
    observation = _prepared_acquired_observation(prepared)
    rule = acquired_observation_binding_rule(
        observation=observation, slot_binding=prepared.selected_profile
    )
    return dict(rule.model_dump(mode="json", exclude={"notes"}))


def _acquired_observation_semantic_values(
    *,
    observation: CanonicalAcquisitionObservation,
    slot_binding: ControlledAcquisitionSlotBinding,
    projection_row_count: int,
) -> dict[str, object]:
    """Compose the narrow one-selected-row purpose without occurrence identity."""
    rule = acquired_observation_binding_rule(observation=observation, slot_binding=slot_binding)
    wire = observation.model_dump(mode="json")
    # Walk the complete typed row. The sole excluded field is the occurrence ID;
    # dataset, watermark, all coordinates and transform evidence stay decisive.
    row_values = {
        name: wire.get(name) for name in type(observation).model_fields if name != "observation_id"
    }
    return {
        "purpose_profile": "policyos.runtime.acquired_observation_semantic_values.v1",
        "observation_codec": "CanonicalAcquisitionObservation.model_dump:json",
        "observation": row_values,
        "selected_row_count": 1,
        "source_projection_row_count": projection_row_count,
        "slot_binding": slot_binding.model_dump(mode="json"),
        "binding_rule": rule.model_dump(mode="json", exclude={"notes"}),
        "source_time_status": "not_established",
    }


def prepare_acquired_observation_semantic_values(
    prepared: AcquiredObservationDataPreparation,
) -> dict[str, object]:
    """Return candidate semantic values from the real owner preparation.

    Equality covers one selected controlled numerical row and its mapping. It
    grants no independence, native-currentness, or publication authority. The
    materializer recomputes and reconciles the same preparation before writing.
    """
    observation = _prepared_acquired_observation(prepared)
    return _acquired_observation_semantic_values(
        observation=observation,
        slot_binding=prepared.selected_profile,
        projection_row_count=len(prepared.observation_projection.observations),
    )


def _historical_owner_ref_matches_selected_view(
    store: ArtifactStore,
    *,
    owner_ref: ArtifactRef | None,
    selected_ref: ArtifactRef,
    expected_kind: str,
) -> bool:
    """Reconcile the real owner default or selected view with one admitted view.

    A profileless owner-native reference names the store's actual default. It
    does not authorize selecting an arbitrary same-content sidecar. Both views
    must resolve to the same full identity and pass the epoch content reader.
    """
    from polisyos.core.artifacts import artifact_ref_for_manifest, read_core_manifest_profile
    from polisyos.core.contracts import epoch

    if (
        not isinstance(owner_ref, ArtifactRef)
        or not isinstance(selected_ref, ArtifactRef)
        or selected_ref.manifest_profile_sha256 is None
        or owner_ref.kind != expected_kind
        or selected_ref.kind != expected_kind
        or owner_ref.artifact_id != selected_ref.artifact_id
        or owner_ref.media_type != selected_ref.media_type
    ):
        return False
    try:
        owner_manifest, _ = read_core_manifest_profile(store, owner_ref)
        if artifact_ref_for_manifest(owner_manifest) != selected_ref:
            return False
        owner_value = epoch.load_verified_epoch_statement(
            store=store,
            ref=owner_ref,
            expected_kind=expected_kind,
            expected_media_type=owner_ref.media_type,
        )
        selected_value = epoch.load_verified_epoch_statement(
            store=store,
            ref=selected_ref,
            expected_kind=expected_kind,
            expected_media_type=selected_ref.media_type,
        )
        final_manifest, _ = read_core_manifest_profile(store, owner_ref)
        return (
            owner_value == selected_value
            and artifact_ref_for_manifest(final_manifest) == selected_ref
        )
    except (OSError, RuntimeError, TypeError, ValueError):
        return False


def _verify_historical_acquisition_activation(
    store: ArtifactStore,
    *,
    receipt: ActivatedOverlayAdmissionStatement,
    passport: AdmissionPassport,
    receipt_ref: ArtifactRef,
    passport_ref: ArtifactRef,
    activation: ActivatedSemanticEpochAdmissionReceipt | None,
) -> None:
    """Reconcile immutable activation evidence without a current native permit."""
    from polisyos.core.contracts import epoch
    from polisyos.fabric import data_plane
    from polisyos.runtime.quality.acquisition_executor import ActivatedSemanticEpochAdmissionReceipt

    def read(ref: ArtifactRef, kind: str) -> dict[str, Any]:
        # Nested owner-native refs can predate their CAS copy. The Core reader
        # owns the exact declared default-profile law; never invent a selector.
        return epoch.load_verified_epoch_statement(
            store=store,
            ref=ref,
            expected_kind=kind,
            expected_media_type=ref.media_type,
        )

    production = epoch.SemanticEpochProductionReceiptStatement.model_validate(
        read(receipt.semantic_epoch_production_receipt_ref, "epoch.production_receipt")
    )
    if (
        production.production_mode != "acquisition_finalization"
        or production.status not in {"appended", "no_change"}
        or production.admitted_boundary_evidence_ref != receipt.admitted_boundary_evidence_ref
        or production.prepared_epoch_ref != receipt.prepared_semantic_epoch_ref
        or production.epoch_ref != receipt.semantic_epoch_stamp.epoch_ref
        or production.semantic_manifest_ref != receipt.semantic_epoch_stamp.semantic_manifest_ref
        or production.requested_query_context_ref
        != receipt.semantic_epoch_stamp.requested_query_context_ref
    ):
        raise DataStateSubstrateError("acquisition_historical_production_binding_mismatch")
    admitted = epoch.AdmittedAcquisitionBoundaryEvidence.model_validate(
        read(receipt.admitted_boundary_evidence_ref, "epoch.admitted_acquisition_boundary_evidence")
    )
    actual_activation = ActivatedSemanticEpochAdmissionReceipt(
        passport_ref=passport_ref,
        prepared_epoch_ref=admitted.prepared_epoch_ref,
        pending_overlay_receipt_ref=admitted.pending_overlay_receipt_ref,
        semantic_epoch_production_receipt_ref=receipt.semantic_epoch_production_receipt_ref,
        overlay_admission_receipt_ref=receipt_ref,
        native_membership_receipt_ref=admitted.native_membership_receipt_ref,
        semantic_denominator_receipt_ref=admitted.semantic_denominator_receipt_ref,
        semantic_projection_verification_receipt_ref=admitted.semantic_projection_verification_receipt_ref,
        semantic_epoch_stamp=admitted.semantic_epoch_stamp,
        activation_state="active",
    )
    if (
        activation is not None
        and actual_activation
        != ActivatedSemanticEpochAdmissionReceipt.model_validate(
            activation.model_dump(mode="python")
        )
    ):
        raise DataStateSubstrateError("acquisition_historical_growth_activation_mismatch")
    if (
        admitted.passport_ref != passport_ref
        or admitted.passport_content_hash
        != data_plane.content_sha256(passport.model_dump(mode="json"))
        or admitted.epoch_id != passport.epoch_id
        or admitted.prepared_epoch_ref != passport.prepared_semantic_epoch_ref
        or admitted.pending_overlay_receipt_ref != receipt.pending_overlay_receipt_ref
        or admitted.semantic_candidate_ref != passport.semantic_boundary_candidate_ref
        or admitted.semantic_candidate_content_hash
        != passport.semantic_boundary_candidate_content_hash
        or admitted.semantic_epoch_stamp != passport.semantic_epoch_stamp
    ):
        raise DataStateSubstrateError("acquisition_historical_admitted_binding_mismatch")
    loaded: dict[str, Any] = {}
    recipe = (
        ("prepared_epoch", "epoch.prepared", None, "polisyos.epoch.prepared.v1"),
        (
            "native_member",
            "epoch.acquisition_native_member",
            None,
            "polisyos.epoch.acquisition-native-member.v1",
        ),
        (
            "pending_overlay_receipt",
            "epoch.pending_overlay_admission_receipt",
            epoch.PendingOverlayAdmissionStatement,
            None,
        ),
        (
            "native_membership_receipt",
            "epoch.acquisition_native_membership",
            epoch.AcquisitionNativeMembershipReceipt,
            "polisyos.epoch.acquisition-native-membership-receipt.v1",
        ),
        (
            "semantic_denominator_receipt",
            "epoch.acquisition_semantic_denominator_receipt",
            epoch.AcquisitionSemanticCandidateDenominatorReceipt,
            "polisyos.epoch.acquisition-semantic-denominator-receipt.v1",
        ),
        (
            "semantic_projection_verification_receipt",
            "epoch.acquisition_semantic_projection_verification_receipt",
            epoch.AcquisitionSemanticProjectionVerificationReceipt,
            "polisyos.epoch.acquisition-semantic-projection-verification-receipt.v1",
        ),
    )
    for name, kind, model, domain in recipe:
        mapping = read(getattr(admitted, name + "_ref"), kind)
        value = model.model_validate(mapping) if model is not None else mapping
        loaded[name] = value
        observed = (
            epoch.epoch_semantic_content_hash(domain=domain, value=value)
            if domain is not None
            else data_plane.content_sha256(mapping)
        )
        if observed != getattr(admitted, name + "_content_hash"):
            raise DataStateSubstrateError("acquisition_historical_evidence_content_mismatch")
    native = loaded["native_membership_receipt"]
    semantic = loaded["semantic_denominator_receipt"]
    projection = loaded["semantic_projection_verification_receipt"]
    pending = loaded["pending_overlay_receipt"]
    owner_snapshot = read(native.owner_source_snapshot_ref, "epoch.acquisition_owner_snapshot")
    owner_rows = owner_snapshot.get("rows")
    if (
        owner_snapshot.get("schema_version") != pending.schema_version
        or not isinstance(owner_rows, list)
        or len(owner_rows) != native.declared_native_member_count
        or len(owner_rows) != len(native.assessments)
        or epoch.epoch_semantic_content_hash(
            domain="polisyos.epoch.acquisition-owner-snapshot.v1", value=owner_snapshot
        )
        != native.owner_source_snapshot_content_hash
    ):
        raise DataStateSubstrateError("acquisition_historical_native_snapshot_mismatch")
    assessments = {str(row.native_member_ref.artifact_id): row for row in native.assessments}
    if len(assessments) != len(owner_rows):
        raise DataStateSubstrateError("acquisition_historical_native_snapshot_mismatch")
    for owner_row in owner_rows:
        if not isinstance(owner_row, dict):
            raise DataStateSubstrateError("acquisition_historical_native_row_malformed")
        encoded = epoch.canonical_epoch_bytes(owner_row)
        framed = len(encoded).to_bytes(8, "big") + encoded
        row_id = "sha256:" + hashlib.sha256(framed).hexdigest()
        assessment = assessments.get(row_id)
        if (
            assessment is None
            or read(assessment.native_member_ref, "epoch.acquisition_native_member") != owner_row
            or epoch.epoch_semantic_content_hash(
                domain="polisyos.epoch.acquisition-native-member.v1", value=owner_row
            )
            != assessment.native_member_content_hash
        ):
            raise DataStateSubstrateError("acquisition_historical_native_row_binding_mismatch")
    provenance = epoch.AcquisitionProjectionVerifierProvenance.model_validate(
        read(admitted.verifier_provenance_ref, "epoch.acquisition_projection_verifier_provenance")
    )
    if (
        native.status != "resolved"
        or semantic.status != "resolved"
        or projection.status != "verified"
        or native.query != semantic.query
        or native.query.requested_query_context_ref
        != passport.semantic_epoch_stamp.requested_query_context_ref
        or projection.native_membership_receipt_ref != admitted.native_membership_receipt_ref
        or projection.native_membership_receipt_content_hash
        != admitted.native_membership_receipt_content_hash
        or projection.semantic_denominator_receipt_ref != admitted.semantic_denominator_receipt_ref
        or projection.semantic_denominator_receipt_content_hash
        != admitted.semantic_denominator_receipt_content_hash
        or not _historical_owner_ref_matches_selected_view(
            store,
            owner_ref=projection.verifier_provenance_ref,
            selected_ref=admitted.verifier_provenance_ref,
            expected_kind="epoch.acquisition_projection_verifier_provenance",
        )
        or projection.verifier_provenance_content_hash
        != epoch.epoch_semantic_content_hash(
            domain="polisyos.epoch.acquisition-projection-verifier.v1", value=provenance
        )
        or pending.epoch_id != passport.epoch_id
        or pending.passport_id != passport.passport_id
        or pending.boundary_candidate_ref != admitted.semantic_candidate_ref
        or pending.prepared_semantic_epoch_ref != admitted.prepared_epoch_ref
        or pending.semantic_epoch_stamp != admitted.semantic_epoch_stamp
        or receipt.baseline_before_sha256 != receipt.baseline_after_sha256
        or pending.baseline_before_sha256 != receipt.baseline_before_sha256
        or pending.baseline_after_sha256 != receipt.baseline_after_sha256
        or pending.admission_content_sha256 != receipt.admission_content_sha256
        or not any(
            row.semantic_candidate_ref == admitted.semantic_candidate_ref
            and row.semantic_candidate_content_hash == admitted.semantic_candidate_content_hash
            and row.operational_epoch_id == passport.epoch_id
            and row.passport_content_hash == admitted.passport_content_hash
            and _historical_owner_ref_matches_selected_view(
                store,
                owner_ref=row.passport_ref,
                selected_ref=passport_ref,
                expected_kind="epoch.acquisition_passport_snapshot",
            )
            and row.binding_status == "bound"
            and _historical_owner_ref_matches_selected_view(
                store,
                owner_ref=row.native_member_ref,
                selected_ref=admitted.native_member_ref,
                expected_kind="epoch.acquisition_native_member",
            )
            and row.native_member_content_hash == admitted.native_member_content_hash
            for row in native.assessments
        )
        or not any(
            row.semantic_candidate_ref == admitted.semantic_candidate_ref
            and row.semantic_candidate_content_hash == admitted.semantic_candidate_content_hash
            for row in semantic.assessments
        )
    ):
        raise DataStateSubstrateError("acquisition_historical_projection_binding_mismatch")


def _replay_acquired_observation_projection(
    store: ArtifactStore,
    *,
    receipt_ref: ArtifactRef,
    passport_ref: ArtifactRef,
    boundary_candidate_ref: ArtifactRef | None = None,
    expected_source_ref: ArtifactRef | None = None,
    activation: ActivatedSemanticEpochAdmissionReceipt | None = None,
) -> ActivatedAcquisitionObservationProjection:
    """Replay source and typed activation history without a present native permit."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.contracts import epoch
    from polisyos.fabric import connectors, data_plane
    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport
    from polisyos.runtime.quality.data_snapshot_lineage import validate_data_snapshot_owner_lineage

    _require_selected_profile(receipt_ref, "acquisition_receipt_profile_unselected")
    _require_selected_profile(passport_ref, "acquisition_passport_profile_unselected")
    passport = AdmissionPassport.model_validate(
        epoch.load_verified_epoch_statement(
            store=store,
            ref=passport_ref,
            expected_kind="epoch.acquisition_passport_snapshot",
        )
    )
    receipt = epoch.ActivatedOverlayAdmissionStatement.model_validate(
        epoch.load_verified_epoch_statement(
            store=store,
            ref=receipt_ref,
            expected_kind="epoch.activated_overlay_admission_receipt",
        )
    )
    if (
        receipt.epoch_id != passport.epoch_id
        or receipt.passport_id != passport.passport_id
        or receipt.prepared_semantic_epoch_ref != passport.prepared_semantic_epoch_ref
        or receipt.semantic_epoch_stamp != passport.semantic_epoch_stamp
        or receipt.activation_state != "active"
    ):
        raise DataStateSubstrateError("acquisition_historical_activation_binding_mismatch")
    if (
        boundary_candidate_ref is not None
        and boundary_candidate_ref != passport.semantic_boundary_candidate_ref
    ):
        raise DataStateSubstrateError("acquisition_historical_boundary_binding_mismatch")
    _verify_historical_acquisition_activation(
        store,
        receipt=receipt,
        passport=passport,
        receipt_ref=receipt_ref,
        passport_ref=passport_ref,
        activation=activation,
    )
    candidate = epoch.AcquisitionSemanticBoundaryCandidateStatement.model_validate(
        epoch.load_verified_epoch_statement(
            store=store,
            ref=passport.semantic_boundary_candidate_ref,
            expected_kind="epoch.acquisition_semantic_boundary_candidate",
        )
    )
    if (
        epoch.acquisition_semantic_candidate_content_hash(candidate)
        != passport.semantic_boundary_candidate_content_hash
    ):
        raise DataStateSubstrateError("acquisition_semantic_source_candidate_mismatch")
    source_ref = candidate.source_record_ref
    if expected_source_ref is not None and source_ref != expected_source_ref:
        raise DataStateSubstrateError("acquisition_historical_source_binding_mismatch")
    source_manifest = store.get_manifest(source_ref)
    source_body = store.get_bytes(source_ref)
    codec = epoch.acquisition_artifact_codec(source_ref.kind, media_type=source_ref.media_type)
    if (
        codec is None
        or not store.verify(source_ref).ok
        or str(source_ref.artifact_id) != candidate.source_record_content_hash
        or "sha256:" + hashlib.sha256(source_body).hexdigest()
        != candidate.source_record_content_hash
        or source_manifest.kind != source_ref.kind
        or source_manifest.media_type != source_ref.media_type
        or source_ref.media_type != codec.media_type
        or (codec.canon is not None and source_manifest.canon != codec.canon)
        or (
            codec.schema_name is not None
            and source_manifest.artifact_schema
            != SchemaInfo(name=codec.schema_name, version=codec.schema_version or "")
        )
    ):
        raise DataStateSubstrateError("acquisition_semantic_source_unverified")
    if passport.source_lane == "local_lift":
        if (
            source_ref.kind != "fabric.acquisition.raw_evidence"
            or source_ref.media_type != "application/json"
            or str(source_ref.artifact_id) != passport.raw_artifact_id
        ):
            raise DataStateSubstrateError("acquisition_semantic_source_codec_unsupported")
    else:
        live = passport.live_source_execution
        if (
            live is None
            or source_ref.kind != "connector_cache.payload"
            or codec.payload_format != "connector_cache_payload"
            or source_ref.media_type
            not in {
                "application/vnd.polisyos.cached-result+application/json",
                "application/vnd.polisyos.cached-result+application/parquet",
            }
        ):
            raise DataStateSubstrateError("acquisition_semantic_source_codec_unsupported")
        _require_selected_profile(source_ref, "acquisition_semantic_source_profile_unselected")
        live_snapshot = DataSnapshot.model_validate(
            load_core_json_artifact(store, live.data_snapshot_ref)
        )
        if (
            live_snapshot.data_ref != source_ref
            or str(source_ref.artifact_id) != live.normalized_data_artifact_id
            or live_snapshot.evidence_ref != live.evidence_bundle_ref
        ):
            raise DataStateSubstrateError("acquisition_semantic_source_snapshot_mismatch")
        validate_data_snapshot_owner_lineage(
            store, live.data_snapshot_ref, live_snapshot, candidate_only=True
        )
        result = connectors.ResultSerializer.deserialize(source_body)
        replay_bytes, replay_media = connectors.ResultSerializer.serialize(result)
        if replay_bytes != source_body or replay_media != source_ref.media_type:
            raise DataStateSubstrateError("acquisition_semantic_source_codec_mismatch")
        source_body = data_forge_read_api.catalog.normalized_acquisition_source_body(result)
    derived = data_forge_read_api.catalog.derive_canonical_observations(
        source_body, passport=passport, registration=passport.registration
    )
    return data_forge_read_api.catalog.ActivatedAcquisitionObservationProjection.issue(
        receipt_ref=receipt_ref,
        receipt_content_sha256=data_plane.content_sha256(receipt.model_dump(mode="json")),
        passport_ref=passport_ref,
        passport_content_sha256=data_plane.content_sha256(passport.model_dump(mode="json")),
        variable_id=passport.variable_id,
        epoch_id=passport.epoch_id,
        passport_id=passport.passport_id,
        admission_content_sha256=receipt.admission_content_sha256,
        observations=derived,
    )


def replay_acquired_observation_snapshot_preparation(
    store: ArtifactStore,
    *,
    base_data_snapshot_ref: ArtifactRef,
    receipt_ref: ArtifactRef,
    passport_ref: ArtifactRef,
    boundary_candidate_ref: ArtifactRef,
    source_ref: ArtifactRef,
    observation_id: str,
    slot_binding: ControlledAcquisitionSlotBinding,
    transaction_time: datetime,
    activation: ActivatedSemanticEpochAdmissionReceipt | None = None,
) -> AcquiredObservationDataPreparation:
    """Recompute actual historical preparation from compact source selectors, write-free.

    This proves historical consumed meaning only. Current native admission,
    revocation, frontier and permission remain the live Runtime owner's checks.
    """
    if not isinstance(boundary_candidate_ref, ArtifactRef) or not isinstance(
        source_ref, ArtifactRef
    ):
        raise DataStateSubstrateError("acquisition_historical_source_selectors_missing")
    if type(slot_binding) is not ControlledAcquisitionSlotBinding:
        raise DataStateSubstrateError("acquisition_slot_binding_untyped")
    if not isinstance(transaction_time, datetime):
        raise DataStateSubstrateError("acquisition_transaction_time_untyped")
    slot_binding = ControlledAcquisitionSlotBinding.model_validate(
        slot_binding.model_dump(mode="python")
    )
    projection = _replay_acquired_observation_projection(
        store,
        receipt_ref=receipt_ref,
        passport_ref=passport_ref,
        boundary_candidate_ref=boundary_candidate_ref,
        expected_source_ref=source_ref,
        activation=activation,
    )
    return _prepare_acquired_observation_snapshot_from_projection(
        store,
        base_data_snapshot_ref=base_data_snapshot_ref,
        selected_projection=projection,
        selected_profile=slot_binding,
        observation_id=observation_id,
        receipt_ref=receipt_ref,
        transaction_time=transaction_time,
    )


def _read_acquired_observation_selection(
    store: ArtifactStore, data_snapshot_ref: ArtifactRef
) -> tuple[CanonicalAcquisitionObservation, ControlledAcquisitionSlotBinding, int]:
    """Replay the actual selected snapshot, source codec and canonical row owner."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.data_forge.read_api.catalog import CanonicalAcquisitionObservation
    from polisyos.fabric import data_plane
    from polisyos.runtime.quality.data_snapshot_lineage import (
        validate_data_snapshot_owner_lineage,
    )

    _require_selected_profile(data_snapshot_ref, "acquisition_semantic_snapshot_profile_unselected")
    try:
        snapshot = DataSnapshot.model_validate(load_core_json_artifact(store, data_snapshot_ref))
        lineage = snapshot.source_lineage
        if not isinstance(lineage, core_contracts.AcquiredObservationDataSnapshotLineage):
            raise DataStateSubstrateError("acquisition_semantic_snapshot_owner_unsupported")
        validate_data_snapshot_owner_lineage(
            store, data_snapshot_ref, snapshot, candidate_only=True
        )
        payload = load_core_json_artifact(store, snapshot.data_ref)
        if not isinstance(payload, dict):
            raise DataStateSubstrateError("acquisition_semantic_payload_not_object")
        owner = payload.get("_policyos_acquisition")
        history = payload.get("_policyos_acquisition_history")
        acquisition = payload.get("acquisition")
        if not isinstance(owner, dict) or not isinstance(history, list):
            raise DataStateSubstrateError("acquisition_semantic_owner_fields_missing")
        if owner.get("schema_version") != ACQUIRED_DATA_STATE_SCHEMA_VERSION:
            raise DataStateSubstrateError("acquisition_semantic_payload_epoch_unsupported")
        selected = tuple(
            row
            for row in history
            if isinstance(row, dict)
            and row.get("observation_id") == owner.get("selected_observation_id")
            and row.get("dataset_id") == owner.get("selected_dataset_id")
        )
        if len(selected) != 1:
            raise DataStateSubstrateError("acquisition_semantic_selected_row_not_unique")
        row = selected[0]
        observation = CanonicalAcquisitionObservation.model_validate(row.get("observation"))
        row_digest = data_plane.content_sha256(observation.model_dump(mode="json"))
        slot_binding = ControlledAcquisitionSlotBinding.model_validate(owner.get("slot_binding"))
        if (
            observation.observation_id != owner.get("selected_observation_id")
            or observation.dataset_id != owner.get("selected_dataset_id")
            or row.get("row_content_sha256") != row_digest
            or owner.get("selected_row_content_sha256") != row_digest
            or row.get("projection_content_sha256") != owner.get("projection_content_sha256")
            or not isinstance(acquisition, dict)
            or acquisition.get("selected")
            != _acquired_observation_selected_value(observation, row_digest)
            or any(
                snapshot.stats.get(field) != owner.get(field)
                for field in (
                    "selected_observation_id",
                    "selected_dataset_id",
                    "selected_row_content_sha256",
                    "projection_content_sha256",
                    "source_time_status",
                )
            )
        ):
            raise DataStateSubstrateError("acquisition_semantic_selected_payload_mismatch")
        projection = _replay_acquired_observation_projection(
            store,
            receipt_ref=lineage.overlay_admission_receipt_ref,
            passport_ref=lineage.passport_ref,
        )
        derived = tuple(row.observation for row in projection.observations)
        selected_source_rows = tuple(
            row for row in derived if row.observation_id == observation.observation_id
        )
        if len(selected_source_rows) != 1 or selected_source_rows[0] != observation:
            raise DataStateSubstrateError("acquisition_semantic_source_row_mismatch")
        if projection.projection_content_sha256 != owner.get("projection_content_sha256"):
            raise DataStateSubstrateError("acquisition_semantic_source_projection_mismatch")
        # Re-run the exact full generated rule before its report-only field is projected.
        acquired_observation_binding_rule(observation=observation, slot_binding=slot_binding)
        return observation, slot_binding, len(derived)
    except DataStateSubstrateError:
        raise
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise DataStateSubstrateError("acquisition_semantic_snapshot_unresolved", str(exc)) from exc


def read_acquired_observation_semantic_values(
    store: ArtifactStore, data_snapshot_ref: ArtifactRef
) -> dict[str, object]:
    """Read historical consumed values, without asserting present native eligibility."""
    observation, binding, count = _read_acquired_observation_selection(store, data_snapshot_ref)
    return _acquired_observation_semantic_values(
        observation=observation, slot_binding=binding, projection_row_count=count
    )


def read_acquired_observation_binding_rule(
    store: ArtifactStore, data_snapshot_ref: ArtifactRef
) -> FoundryInputBindingRule:
    """Rebuild the whole historical rule for comparison with actual Foundry input."""
    observation, binding, _count = _read_acquired_observation_selection(store, data_snapshot_ref)
    return acquired_observation_binding_rule(observation=observation, slot_binding=binding)


def materialize_acquired_observation_snapshot(
    store: ArtifactStore,
    *,
    base_data_snapshot_ref: ArtifactRef,
    overlay: object,
    receipt_ref: ArtifactRef,
    passport: object,
    authority: object,
    observation_id: str,
    slot_binding: ControlledAcquisitionSlotBinding,
    workspace_dir: Path,
    transaction_time: datetime,
    prepared: AcquiredObservationDataPreparation | None = None,
) -> AcquiredObservationDataSnapshotResult:
    """Extend an existing S1 snapshot with one activated row for candidate work.

    The projection is resolved again through Data Forge's canonical active-state
    reader. This S1 owner checks the selected row against that owner readback,
    preserves the existing snapshot payload, emits a new owner DataSnapshot,
    and asks Data Forge's existing snapshot finalizer to issue the binding.
    Source time, source-to-target measurement equivalence, and causal coupling
    remain declared limitations. ``transaction_time`` records only this
    materialization event; it is never substituted for source observation time.

    Args:
        store: The exact runtime-supplied ArtifactStore used by the tenant.
        base_data_snapshot_ref: Current DataSnapshot whose world payload is
            extended by the admitted observation.
        overlay: Canonical Data Forge ``CatalogAcquisitionOverlay`` owner.
        receipt_ref: Exact activated receipt selected by the world-growth owner.
        passport: Owner-verified acquisition passport for ``receipt_ref``.
        authority: The same canonical acquisition authority used for admission.
        observation_id: Exact row identity selected from the active projection.
        slot_binding: Explicit controlled-candidate map to one Foundry slot.
        workspace_dir: Per-job workspace for Data Forge's normal snapshot owner.
        transaction_time: Time this controlled candidate snapshot is emitted.
        prepared: Optional caller-constructible comparison candidate. Its digest
            is not authority. The active owner is reread and all preparation
            fields must agree; only freshly owner-resolved values are written.

    Returns:
        The new DataSnapshot and Data Forge binding plus the required Foundry
        rule that consumes the selected row.

    Raises:
        DataStateSubstrateError: If the base snapshot, selected row, candidate
            mapping, transaction time or supplied preparation cannot be verified.
    """

    if prepared is not None and type(prepared) is not AcquiredObservationDataPreparation:
        raise DataStateSubstrateError("acquisition_preparation_untyped")
    current = prepare_acquired_observation_snapshot(
        store,
        base_data_snapshot_ref=base_data_snapshot_ref,
        overlay=overlay,
        receipt_ref=receipt_ref,
        passport=passport,
        authority=authority,
        observation_id=observation_id,
        slot_binding=slot_binding,
        transaction_time=transaction_time,
    )
    if prepared is not None and prepared != current:
        raise DataStateSubstrateError("acquisition_preparation_owner_state_changed")
    prepared = current
    prepare_acquired_observation_semantic_values(prepared)
    transaction_time_text = prepared.transaction_time_text
    payload = prepared.payload()
    selected_projection = prepared.observation_projection
    selected_profile = prepared.selected_profile
    lineage_inputs = prepared.lineage_inputs
    payload_ref = store.put_json(
        payload,
        PutOptions(
            kind="fabric.production_data_state_payload",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.runtime.quality.AcquisitionDataStatePayload",
                version=ACQUIRED_DATA_STATE_SCHEMA_VERSION,
            ),
            inputs=list(lineage_inputs),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    _require_selected_profile(payload_ref, "acquisition_payload_profile_unverified")
    payload_content_hash = str(payload_ref.artifact_id)
    snapshot_id = "gy-s1-acquisition-overlay-" + payload_content_hash.removeprefix("sha256:")[:20]
    data_snapshot = core_contracts.DataSnapshotOwnerBound(
        data_ref=payload_ref,
        source_lineage=core_contracts.AcquiredObservationDataSnapshotLineage(
            base_data_snapshot_ref=base_data_snapshot_ref,
            overlay_admission_receipt_ref=selected_projection.receipt_ref,
            passport_ref=selected_projection.passport_ref,
        ),
        stats={
            "snapshot_id": snapshot_id,
            "source_mode": "candidate_acquisition_overlay",
            "base_snapshot_id": prepared.base_snapshot_id,
            "selected_observation_id": prepared.selected_observation_id,
            "selected_dataset_id": prepared.selected_dataset_id,
            "selected_row_content_sha256": prepared.selected_row_content_sha256,
            "projection_content_sha256": selected_projection.projection_content_sha256,
            "source_time_status": "not_established",
            "materialized_at_transaction_time": transaction_time_text,
        },
        notes=[
            "candidate_acquisition_overlay",
            "source_time_status:not_established",
            "source_to_target_measurement_contract_not_established",
            "causal_coupling_not_established",
            "data_forge_snapshot_binding:finalize_snapshot",
            "foundry_binding_owner:polisyos.foundry.data_plane.build_input_bindings",
        ],
    )
    data_snapshot_ref = store.put_json(
        data_snapshot,
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.3.0"),
            inputs=[
                input_ref_from_artifact_ref(
                    payload_ref,
                    role="payload.acquired_observation_candidate",
                ),
                *lineage_inputs,
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    _require_selected_profile(data_snapshot_ref, "acquisition_snapshot_profile_unverified")
    binding_path = _write_data_forge_snapshot_binding(
        workspace_dir=workspace_dir,
        snapshot_id=snapshot_id,
        payload=payload,
        payload_content_hash=payload_content_hash,
        published_at=transaction_time_text,
        corpus_id="candidate-acquisition-observation-overlay",
        builder_revision=(
            "polisyos.runtime.quality.data_state_substrate."
            "materialize_acquired_observation_snapshot"
        ),
        lineage_refs=(
            _cas_data_forge_ref(base_data_snapshot_ref),
            _cas_data_forge_ref(selected_projection.receipt_ref),
            _cas_data_forge_ref(selected_projection.passport_ref),
            _cas_data_forge_ref(payload_ref),
        ),
        claim_requirement_bindings=_acquired_claim_requirement_bindings(
            selected_profile.canonical_variable_id
        ),
    )
    return AcquiredObservationDataSnapshotResult(
        data_snapshot_ref=data_snapshot_ref,
        data_forge_snapshot_binding_path=binding_path,
        data_forge_role=_data_forge_snapshot_role(),
        snapshot_id=snapshot_id,
        payload_content_hash=payload_content_hash,
        selected_dataset_id=prepared.selected_dataset_id,
        selected_observation_id=prepared.selected_observation_id,
        source_time_status="not_established",
        observation_projection=selected_projection,
        foundry_binding_rule=prepared.foundry_binding_rule,
    )


@dataclass(frozen=True)
class AcquiredObservationWorldPreparation:
    """Actual acquired-world constructor inputs before source-dependent writes."""

    model_values_json: bytes
    rules: tuple[FoundryInputBindingRule, ...]
    limitations: WorldModelLimitations
    base_world_model: WorldModelRecord
    registry_bundle_ref: ArtifactRef
    owner_values: WorldModelOwnerValues | None

    def materialized_model(self, data_snapshot_ref: ArtifactRef) -> ModelSpec:
        """Bind the sole late source slot after its real materializer has emitted it."""
        return ModelSpec.model_validate(
            {
                **json.loads(self.model_values_json),
                "data_snapshot_ref": str(data_snapshot_ref.artifact_id),
            }
        )


def _prepare_acquired_observation_world(
    store: ArtifactStore,
    *,
    base_world_model_record: WorldModelRecord,
    acquired_rule: FoundryInputBindingRule,
    registry_bundle_ref: ArtifactRef,
    substrate_registry: SubstrateRegistry | None,
) -> AcquiredObservationWorldPreparation:
    """Construct the existing producer's full model/rules/limitations without writes."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.foundry.data_plane import load_input_bindings

    if type(base_world_model_record) is not WorldModelRecord:
        raise DataStateSubstrateError("acquisition_world_base_record_untyped")
    base = WorldModelRecord.model_validate(base_world_model_record.model_dump(mode="json"))
    views = world_model_artifact_views(base)
    if acquired_rule.target_slot_id not in {binding.slot_id for binding in base.policy_slot_map}:
        raise DataStateSubstrateError("acquisition_target_slot_not_in_base_world")
    if views.registry_bundle_ref != registry_bundle_ref:
        raise DataStateSubstrateError("acquisition_world_registry_selection_mismatch")
    model_manifest = store.get_manifest(views.model_spec_ref)
    if model_manifest.kind != "ir.model_spec" or not store.verify(views.model_spec_ref).ok:
        raise DataStateSubstrateError("acquisition_base_model_spec_unverified")
    model_spec = ModelSpec.model_validate(load_core_json_artifact(store, views.model_spec_ref))
    if (
        gy_content_hash(model_spec.model_dump(mode="json"))
        != base.simulation_model_ref.model_spec_hash
    ):
        raise DataStateSubstrateError("acquisition_base_model_spec_hash_mismatch")
    payload = model_spec.model_dump(mode="json")
    # All model fields survive. Only the source slot is late-bound to the actual
    # new DataSnapshot; its entire numerical value is separately prepared below.
    payload.pop("data_snapshot_ref")
    payload.update(
        {
            "calibrated": False,
            "calibration_ref": None,
            "notes": [
                *model_spec.notes,
                "candidate_acquisition_world",
                "source_time_not_established",
                "causal_coupling_not_established",
            ],
        }
    )
    bindings = load_input_bindings(store, world_model_artifact_views(base).input_bindings_ref)
    rules = (
        *(rule for rule in bindings.rules if rule.target_slot_id != acquired_rule.target_slot_id),
        acquired_rule,
    )
    limitations = base.limitations.model_copy(
        update={
            "admissibility_blockers": tuple(
                sorted(
                    set(base.limitations.admissibility_blockers)
                    | set(ACQUIRED_DATA_STATE_LIMITATION_CODES)
                )
            )
        }
    )
    return AcquiredObservationWorldPreparation(
        model_values_json=json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode(),
        rules=rules,
        limitations=limitations,
        base_world_model=base,
        registry_bundle_ref=registry_bundle_ref,
        owner_values=None,
    )


def _acquired_world_meaning(
    *,
    world: WorldModelRecord,
    model_values: dict[str, object],
    limitations: WorldModelLimitations,
    rules: tuple[FoundryInputBindingRule, ...],
    state: object,
    registry_values: dict[str, object],
    substrate_registry: SubstrateRegistry,
    data_values: dict[str, object],
    fabric_values: dict[str, object],
    binding_values: dict[str, object],
) -> dict[str, object]:
    """Project all inherited fields and all complete owner-resolved value facets."""
    from polisyos.foundry.contracts.state import GlobalState
    from polisyos.foundry.execute import state_snapshot_value_projection

    if type(state) is not GlobalState:
        raise DataStateSubstrateError("acquisition_world_state_values_untyped")
    # These are the existing constructor's generated occurrence compartments.
    # They are replaced below by their separately resolved full value owners;
    # every other typed WMR field is retained generically, including future ones.
    inherited = world.model_dump(
        mode="json",
        exclude={
            "world_model_record_id",
            "content_hash",
            "created_at",
            "tx_time_scope",
            "fabric_world_ref",
            "data_forge_binding_ref",
            "simulation_model_ref",
            "foundry_binding_ref",
            "artifact_views",
            "substrate_registry_ref",
        },
    )
    inherited.update(
        {
            "schema_version": "policyos.runtime.world_model_record.v2",
            "authority_status": "limited",
            "valid_time_scope": "not_established",
            "producer_ref": (
                "polisyos.runtime.quality.data_state_substrate."
                "build_acquired_observation_candidate_world"
            ),
            "limitations": limitations.model_dump(mode="json"),
        }
    )
    return {
        "inherited_world": inherited,
        "model_spec": model_values,
        "rules": tuple(rule.model_dump(mode="json") for rule in rules),
        "state": tuple(asdict(leaf) for leaf in state_snapshot_value_projection(state)),
        "registry": registry_values,
        "substrate_registry": substrate_registry.model_dump(mode="json"),
        "data": data_values,
        "fabric": fabric_values,
        "data_forge_binding": binding_values,
    }


def _world_not_established(
    codes: tuple[str, ...], values: dict[str, object] | None = None
) -> dict[str, object]:
    """Return an explicit partial preparation; it cannot be treated as equality proof."""
    return {
        "status": "not_established",
        "predicate_provenance": "not_established",
        "reason_codes": codes,
        "effective_values": values or {},
    }


def _prepared_config_value(value: object) -> object:
    """Freeze complete structural config values without coercion; unknown natives refuse."""
    if value is None or type(value) in {str, int, bool, bytes}:
        return (type(value).__name__, value)
    if type(value) is float:
        return ("float64", struct.pack("!d", value))
    if isinstance(value, BaseModel):
        return (
            type(value).__module__,
            type(value).__qualname__,
            tuple(
                (name, _prepared_config_value(getattr(value, name)))
                for name in type(value).model_fields
            ),
        )
    if isinstance(value, (tuple, list)) and type(value) in {tuple, list}:
        return (type(value).__name__, tuple(_prepared_config_value(item) for item in value))
    if isinstance(value, dict) and type(value) is dict and all(type(key) is str for key in value):
        return ("dict", tuple((key, _prepared_config_value(value[key])) for key in sorted(value)))
    raise DataStateSubstrateError("acquisition_world_config_native_value_not_established")


def prepare_acquired_observation_world_semantic_values(
    *,
    store: ArtifactStore,
    base_world_model_record: WorldModelRecord,
    data_preparation: AcquiredObservationDataPreparation,
    prepared_state_values: object,
    registry_bundle_ref: ArtifactRef,
    substrate_registry: SubstrateRegistry | None = None,
) -> dict[str, object]:
    """Prepare the actual acquired-world inputs without state/context/N4/N5 emission.

    Unsupported binding/fact/graph roles remain explicit not-established facets.
    The caller-supplied state preparation is compared with the real Foundry owner;
    it is never accepted as completeness or authority by declaration.
    """
    from polisyos.foundry.data_plane import prepare_json_input_binding_values
    from polisyos.foundry.execute import state_snapshot_value_projection

    try:
        data_values = prepare_acquired_observation_semantic_values(data_preparation)
        plan = _prepare_acquired_observation_world(
            store,
            base_world_model_record=base_world_model_record,
            acquired_rule=data_preparation.foundry_binding_rule,
            registry_bundle_ref=registry_bundle_ref,
            substrate_registry=substrate_registry,
        )
        from polisyos.runtime.quality.world_model_record import read_world_model_record_owner_values

        plan = replace(
            plan,
            owner_values=read_world_model_record_owner_values(
                store,
                world_model_record=base_world_model_record,
                registry_bundle_ref=registry_bundle_ref,
                substrate_registry=substrate_registry,
            ),
        )
        current = prepare_json_input_binding_values(
            store,
            payload_json=data_preparation.payload_json,
            registry_bundle_ref=registry_bundle_ref,
            rules=list(plan.rules),
        )
        if type(prepared_state_values) is not type(current):
            raise DataStateSubstrateError("acquisition_world_prepared_state_owner_mismatch")
        for field in fields(current):
            actual_value = getattr(current, field.name)
            supplied_value = getattr(prepared_state_values, field.name)
            if field.name == "materialized_state":
                equal = state_snapshot_value_projection(
                    actual_value
                ) == state_snapshot_value_projection(supplied_value)
            else:
                equal = _prepared_config_value(actual_value) == _prepared_config_value(
                    supplied_value
                )
            if not equal:
                raise DataStateSubstrateError("acquisition_world_prepared_state_owner_mismatch")
        return _prepare_acquired_world_semantic_result(
            store=store,
            plan=plan,
            data_values=data_values,
            state=current.materialized_state,
            data_preparation=data_preparation,
            binding_execution={
                "applied_binding_ids": current.applied_binding_ids,
                "warnings": current.warnings,
            },
        )
    except (
        DataStateSubstrateError,
        WorldModelRecordError,
        TypeError,
        ValueError,
        OSError,
        RuntimeError,
    ) as exc:
        return _world_not_established(
            (getattr(exc, "code", "acquisition_world_values_unresolved"),)
        )


def _effective_acquired_world_rules(
    rules: tuple[FoundryInputBindingRule, ...],
    acquired_rule: FoundryInputBindingRule,
) -> tuple[dict[str, object], ...]:
    """Verify the full occurrence rule before projecting its generated report field."""
    matching = tuple(rule for rule in rules if rule.target_slot_id == acquired_rule.target_slot_id)
    if matching != (acquired_rule,):
        raise DataStateSubstrateError("acquisition_world_full_rule_mismatch")
    return tuple(
        rule.model_dump(mode="json", exclude={"notes"} if rule == acquired_rule else set())
        for rule in rules
    )


def _acquired_fabric_meaning(world: WorldModelRecord) -> dict[str, object]:
    """Instantiate the exact producer recipe with explicit local occurrence roles."""
    node, facts = _acquired_candidate_fabric_rows(
        snapshot_id="owner-occurrence:snapshot",
        payload_hash="owner-occurrence:payload",
        transaction_time="owner-occurrence:transaction-time",
    )
    return {
        "as_of_valid_time": world.fabric_world_ref.as_of_valid_time,
        "world_query_policy": world.fabric_world_ref.world_query_policy,
        "branch": "candidate",
        "valid_time_scope": "not_established",
        "node": node.model_dump(mode="json"),
        "facts": tuple(fact.model_dump(mode="json") for fact in facts),
    }


def _acquired_binding_meaning(
    *,
    payload: dict[str, Any],
    owner: dict[str, Any],
    data_values: dict[str, object],
    state_values: tuple[dict[str, object], ...],
    actual_binding_path: str | None = None,
) -> dict[str, object]:
    """Bind source bytes/meaning before the existing finalizer projects occurrence roles."""
    from polisyos.core.canon import to_canonical_bytes

    payload_hash = (
        "sha256:"
        + hashlib.sha256(to_canonical_bytes(payload, CanonSpec(forbid_floats=False))).hexdigest()
    )
    base_ref = ArtifactRef.model_validate(owner["base_data_snapshot_ref"])
    receipt_ref = ArtifactRef.model_validate(owner["receipt_ref"])
    passport_ref = ArtifactRef.model_validate(owner["passport_ref"])
    lineage_refs = (
        _cas_data_forge_ref(base_ref),
        _cas_data_forge_ref(receipt_ref),
        _cas_data_forge_ref(passport_ref),
        f"cas://sha256/{payload_hash.removeprefix('sha256:')}",
    )
    extra = _data_forge_snapshot_manifest_extra(
        corpus_id="candidate-acquisition-observation-overlay",
        builder_revision=(
            "polisyos.runtime.quality.data_state_substrate."
            "materialize_acquired_observation_snapshot"
        ),
        lineage_refs=lineage_refs,
        claim_requirement_bindings=_acquired_claim_requirement_bindings(
            str(owner["slot_binding"]["canonical_variable_id"])
        ),
        payload_content_hash=payload_hash,
    )
    artifact_meaning = {"observation": data_values, "consumed_state": state_values}
    lineage_meanings = (
        base_ref.model_dump(mode="json"),
        data_values,
        data_values,
        artifact_meaning,
    )
    if actual_binding_path is None:
        artifact_path = Path("data_state_payload.json")
        content = _data_forge_payload_file_bytes(payload)
    else:
        artifact_path = (
            Path(actual_binding_path).parent
            / _DATA_FORGE_SNAPSHOT_PIPELINE
            / "data_state_payload.json"
        )
        content = artifact_path.read_bytes()
        # This is a plain publisher JSON file, parsed by its existing DataForge
        # manifest reader. Core canonical bytes bind it to the selected CAS value.
        if to_canonical_bytes(
            data_forge_read_api.read_manifest(artifact_path), CanonSpec(forbid_floats=False)
        ) != to_canonical_bytes(payload, CanonSpec(forbid_floats=False)):
            raise DataStateSubstrateError("acquisition_world_publisher_payload_mismatch")
    manifest = data_forge_read_api.prepare_publish_manifest(
        pipeline=_DATA_FORGE_SNAPSHOT_PIPELINE,
        artifacts=(artifact_path,),
        captured_artifact_bytes={artifact_path: content},
        extra=extra,
        published_at=str(owner["materialized_at_transaction_time"]),
    )
    if actual_binding_path is None:
        return data_forge_read_api.prepare_snapshot_binding_meaning(
            manifest=manifest,
            pipeline=_DATA_FORGE_SNAPSHOT_PIPELINE,
            artifact_contents=(content,),
            artifact_meanings=(artifact_meaning,),
            expected_lineage_refs=lineage_refs,
            lineage_meanings=lineage_meanings,
        )
    return data_forge_read_api.read_snapshot_binding_meaning(
        binding_path=actual_binding_path,
        expected_manifest=manifest,
        pipeline=_DATA_FORGE_SNAPSHOT_PIPELINE,
        artifact_contents=(content,),
        artifact_meanings=(artifact_meaning,),
        expected_lineage_refs=lineage_refs,
        lineage_meanings=lineage_meanings,
    )


def _acquired_model_dependency_values(
    store: ArtifactStore, world: WorldModelRecord
) -> dict[str, object]:
    """Resolve complete supported NCM values; unknown executable graph roles refuse."""
    from polisyos.ir import NCMSpecRef, load_ncm_spec, prepare_ncm_spec_selected_values

    simulation = world.simulation_model_ref
    if simulation.mechanism_refs or simulation.gcm_refs or simulation.program_graph_refs:
        raise DataStateSubstrateError("acquisition_world_executable_graph_profile_not_established")
    if (
        world.skg_causal_prior_ref.edge_prior_refs
        or world.skg_causal_prior_ref.transport_score_refs
        or world.skg_causal_prior_ref.query_trace_refs
    ):
        raise DataStateSubstrateError("acquisition_world_skg_consumed_values_not_established")
    views = world_model_artifact_views(world)
    return {
        "ncm_values": tuple(
            prepare_ncm_spec_selected_values(
                load_ncm_spec(store, NCMSpecRef.model_validate(ref.model_dump(mode="json")))
            ).value_bytes
            for ref in views.ncm_refs
        ),
        "skg_causal_prior": world.skg_causal_prior_ref.model_dump(mode="json"),
    }


def _prepare_acquired_world_semantic_result(
    *,
    store: ArtifactStore,
    plan: AcquiredObservationWorldPreparation,
    data_values: dict[str, object],
    state: GlobalState,
    data_preparation: AcquiredObservationDataPreparation,
    binding_execution: dict[str, object],
) -> dict[str, object]:
    """Compose the supported current producer's complete owner value quantities."""
    from polisyos.foundry.execute import state_snapshot_value_projection

    owner_values = plan.owner_values
    if owner_values is None:
        raise DataStateSubstrateError("acquisition_world_owner_values_not_established")
    payload = data_preparation.payload()
    state_values = tuple(asdict(leaf) for leaf in state_snapshot_value_projection(state))
    dependencies = _acquired_model_dependency_values(store, plan.base_world_model)
    binding = _acquired_binding_meaning(
        payload=payload,
        owner=payload["_policyos_acquisition"],
        data_values=data_values,
        state_values=state_values,
    )
    effective = _acquired_world_meaning(
        world=plan.base_world_model,
        model_values=json.loads(plan.model_values_json),
        limitations=plan.limitations,
        rules=plan.rules,
        state=state,
        registry_values=owner_values.registry_values,
        substrate_registry=owner_values.substrate_registry,
        data_values=data_values,
        fabric_values=_acquired_fabric_meaning(plan.base_world_model),
        binding_values=binding,
    )
    effective["rules"] = _effective_acquired_world_rules(
        plan.rules, data_preparation.foundry_binding_rule
    )
    effective["model_dependencies"] = dependencies
    effective["binding_execution"] = binding_execution
    return {
        "status": "established",
        "predicate_provenance": "recomputed",
        "reason_codes": (),
        "effective_values": effective,
    }


def _verify_actual_acquired_native_world(
    world: WorldModelRecord, payload_hash: str, transaction_time: str
) -> None:
    """Compare every typed emitted native field with the shared concrete recipe."""
    import polisyos.fabric as fabric
    from polisyos.fabric.world import WorldSnapshotFactWrite, WorldSnapshotNodeWrite
    from polisyos.runtime.quality.world_model_record import _json_scalar

    node, facts = _acquired_candidate_fabric_rows(
        snapshot_id=world.fabric_world_ref.snapshot_id,
        payload_hash=payload_hash,
        transaction_time=transaction_time,
    )
    with fabric.SimulationDB(db_path=":memory:") as database:
        actual = []
        for table, model, expected in (
            ("world_nodes", WorldSnapshotNodeWrite, (node,)),
            ("world_facts", WorldSnapshotFactWrite, facts),
        ):
            frame = fabric.execute_world_query(
                database,
                fabric.WorldQueryRequest(
                    table=table,
                    columns=tuple(model.model_fields),
                    snapshot_root=Path(world.fabric_world_ref.snapshot_root),
                    snapshot_id=world.fabric_world_ref.snapshot_id,
                    limit=2,
                ),
            )
            rows = []
            for raw in frame.to_dict(orient="records"):
                values = {key: _json_scalar(value) for key, value in raw.items()}
                for name in ("provenance_json", "trust_json", "legal_json"):
                    if name in values and isinstance(values[name], str):
                        values[name] = json.loads(values[name])
                rows.append(model.model_validate(values))
            if tuple(rows) != expected:
                raise DataStateSubstrateError("acquisition_world_native_recipe_mismatch")
            actual.append(rows)
    ref = world.fabric_world_ref
    if (
        ref.branch != "candidate"
        or ref.as_of_tx_time != transaction_time
        or ref.provenance_manifest_ref != f"cas://{payload_hash.removeprefix('sha256:')}"
    ):
        raise DataStateSubstrateError("acquisition_world_native_scope_mismatch")


def read_acquired_observation_world_semantic_values(
    *,
    store: ArtifactStore,
    world_model_record: WorldModelRecord,
    registry_bundle_ref: ArtifactRef,
) -> dict[str, object]:
    """Reconcile actual produced WMR, state, native rows and binding before projection."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.foundry.data_plane import load_input_bindings, prepare_input_bindings
    from polisyos.foundry.execute import load_state_snapshot, state_snapshot_value_projection
    from polisyos.runtime.quality.world_model_record import read_world_model_record_owner_values

    try:
        values = read_world_model_record_owner_values(
            store,
            world_model_record=world_model_record,
            registry_bundle_ref=registry_bundle_ref,
        )
        world = values.record
        if (
            world.producer_ref
            != (
                "polisyos.runtime.quality.data_state_substrate."
                "build_acquired_observation_candidate_world"
            )
            or world.authority_status != "limited"
            or world.valid_time_scope != "not_established"
            or values.model_spec.calibrated
            or values.model_spec.calibration_ref is not None
            or values.model_spec.notes[-3:]
            != [
                "candidate_acquisition_world",
                "source_time_not_established",
                "causal_coupling_not_established",
            ]
        ):
            raise DataStateSubstrateError("acquisition_world_producer_profile_not_established")
        views = world_model_artifact_views(world)
        snapshot = DataSnapshot.model_validate(
            load_core_json_artifact(store, views.data_snapshot_ref)
        )
        payload = load_core_json_artifact(store, snapshot.data_ref)
        data_values = read_acquired_observation_semantic_values(store, views.data_snapshot_ref)
        acquired_rule = read_acquired_observation_binding_rule(store, views.data_snapshot_ref)
        bindings = load_input_bindings(store, views.input_bindings_ref)
        prepared = prepare_input_bindings(
            store,
            data_snapshot_ref=views.data_snapshot_ref,
            registry_bundle_ref=registry_bundle_ref,
            rules=list(bindings.rules),
        )
        state = load_state_snapshot(store, snapshot_ref=views.bound_state_snapshot_ref)
        if state_snapshot_value_projection(
            prepared.materialized_state
        ) != state_snapshot_value_projection(state):
            raise DataStateSubstrateError("acquisition_world_state_readback_mismatch")
        _effective_acquired_world_rules(tuple(bindings.rules), acquired_rule)
        owner = payload["_policyos_acquisition"]
        _verify_actual_acquired_native_world(
            world,
            str(snapshot.data_ref.artifact_id),
            str(owner["materialized_at_transaction_time"]),
        )
        model_values = values.model_spec.model_dump(mode="json")
        if model_values.pop("data_snapshot_ref") != str(views.data_snapshot_ref.artifact_id):
            raise DataStateSubstrateError("acquisition_world_model_snapshot_mismatch")
        binding = _acquired_binding_meaning(
            payload=payload,
            owner=owner,
            data_values=data_values,
            state_values=tuple(asdict(leaf) for leaf in state_snapshot_value_projection(state)),
            actual_binding_path=values.data_forge_binding.binding_path,
        )
        effective = _acquired_world_meaning(
            world=world,
            model_values=model_values,
            limitations=world.limitations,
            rules=tuple(bindings.rules),
            state=state,
            registry_values=values.registry_values,
            substrate_registry=values.substrate_registry,
            data_values=data_values,
            fabric_values=_acquired_fabric_meaning(world),
            binding_values=binding,
        )
        effective["rules"] = _effective_acquired_world_rules(tuple(bindings.rules), acquired_rule)
        effective["model_dependencies"] = _acquired_model_dependency_values(store, world)
        report = load_core_json_artifact(store, views.input_binding_report_ref)
        if (
            not isinstance(report, dict)
            or report.get("warnings") != list(prepared.warnings)
            or report.get("applied_binding_ids") != list(prepared.applied_binding_ids)
        ):
            raise DataStateSubstrateError("acquisition_world_binding_report_mismatch")
        effective["binding_execution"] = {
            "applied_binding_ids": prepared.applied_binding_ids,
            "warnings": prepared.warnings,
        }
        return {
            "status": "established",
            "predicate_provenance": "recomputed",
            "reason_codes": (),
            "effective_values": effective,
        }
    except (
        DataStateSubstrateError,
        WorldModelRecordError,
        TypeError,
        ValueError,
        OSError,
        RuntimeError,
    ) as exc:
        return _world_not_established(
            (getattr(exc, "code", "acquisition_world_values_unresolved"),)
        )


def build_acquired_observation_candidate_world(
    store: ArtifactStore,
    *,
    base_world_model: WorldModelRecord,
    substrate_registry: SubstrateRegistry,
    substrate_registry_artifact_ref: ArtifactRef,
    materialization: AcquiredObservationDataSnapshotResult,
    workspace_dir: Path,
    transaction_time: datetime,
) -> AcquiredObservationWorldBuildResult:
    """Extend the existing WMR owner with one admitted row as limited candidate state.

    The prior SKG snapshot is retained byte-for-byte. Its source DataSnapshot
    remains the prior version and the resulting WMR carries
    ``causal_coupling_not_established``; this builder never relabels a prior as
    current causal evidence. Fabric facts use unknown valid time and the
    supplied transaction time only for the snapshot transaction.
    """

    if transaction_time.tzinfo is None or transaction_time.utcoffset() is None:
        raise DataStateSubstrateError("acquisition_transaction_time_must_be_aware")
    base = WorldModelRecord.model_validate(base_world_model.model_dump(mode="json"))
    base_views = world_model_artifact_views(base)
    selected_slot = materialization.foundry_binding_rule.target_slot_id
    base_slots = tuple(binding.slot_id for binding in base.policy_slot_map)
    if selected_slot not in base_slots:
        raise DataStateSubstrateError("acquisition_target_slot_not_in_base_world")

    registry_bundle_ref = base_views.registry_bundle_ref
    plan = _prepare_acquired_observation_world(
        store,
        base_world_model_record=base,
        acquired_rule=materialization.foundry_binding_rule,
        registry_bundle_ref=registry_bundle_ref,
        substrate_registry=substrate_registry,
    )
    model_spec = plan.materialized_model(materialization.data_snapshot_ref)
    retained_rules = list(plan.rules)
    tx_time = transaction_time.astimezone(UTC).isoformat()
    fabric_root = _write_acquired_candidate_fabric_snapshot(
        workspace_dir=workspace_dir,
        snapshot_id=materialization.snapshot_id,
        payload_hash=materialization.payload_content_hash,
        transaction_time=tx_time,
        as_of_valid_time=base.fabric_world_ref.as_of_valid_time,
    )
    limitations = plan.limitations
    data_snapshot_ref = materialization.data_snapshot_ref
    built = build_world_model_record(
        store,
        fabric_world_ref=FabricWorldRef(
            snapshot_root=str(fabric_root),
            snapshot_id=materialization.snapshot_id,
            branch="candidate",
            as_of_valid_time=base.fabric_world_ref.as_of_valid_time,
            as_of_tx_time=tx_time,
            world_query_policy=base.fabric_world_ref.world_query_policy,
            provenance_manifest_ref=f"cas://{materialization.payload_content_hash.removeprefix('sha256:')}",
        ),
        data_forge_snapshot_binding_path=(materialization.data_forge_snapshot_binding_path),
        data_snapshot_ref=data_snapshot_ref,
        model_spec=model_spec,
        skg_causal_prior_ref=base.skg_causal_prior_ref,
        substrate_registry=substrate_registry,
        region_or_jurisdiction=base.region_or_jurisdiction,
        population_scope=base.population_scope,
        policy_domain=base.policy_domain,
        valid_time_scope="not_established",
        tx_time_scope=tx_time,
        resolution=base.resolution,
        branch_mode=base.branch_mode,
        policy_slot_ids=base_slots,
        producer_ref=(
            "polisyos.runtime.quality.data_state_substrate."
            "build_acquired_observation_candidate_world"
        ),
        data_forge_role=materialization.data_forge_role,
        substrate_registry_artifact_ref=substrate_registry_artifact_ref,
        registry_bundle_artifact_ref=registry_bundle_ref,
        _loaded_substrate_registry=substrate_registry,
        foundry_binding_rules=retained_rules,
        mechanism_refs=base.simulation_model_ref.mechanism_refs,
        gcm_refs=base.simulation_model_ref.gcm_refs,
        ncm_refs=base.simulation_model_ref.ncm_refs,
        program_graph_refs=base.simulation_model_ref.program_graph_refs,
        program_graph_view_refs=(
            base_views.program_graph_refs
            if base.schema_version == "policyos.runtime.world_model_record.v2"
            else None
        ),
        ncm_view_refs=(
            base_views.ncm_refs
            if base.schema_version == "policyos.runtime.world_model_record.v2"
            else None
        ),
        limitations=limitations,
        candidate_only=True,
        deployment_update_refs=base.deployment_update_refs,
    )
    if built.record.skg_causal_prior_ref != base.skg_causal_prior_ref:
        raise DataStateSubstrateError("acquisition_candidate_skg_prior_changed")
    if built.record.authority_status != "limited":
        raise DataStateSubstrateError("acquisition_candidate_world_not_limited")
    return AcquiredObservationWorldBuildResult(
        materialization=materialization,
        world_model=built,
        simulation_input=consume_world_model_record_for_simulation(built.record),
        model_spec=model_spec,
        registry_bundle_ref=registry_bundle_ref,
        substrate_registry_ref=substrate_registry_artifact_ref,
    )


def build_production_data_state_world_model_record(
    store: FileSystemCAS,
    *,
    repo_root: Path,
    workspace_dir: Path,
    agent_limit: int | None = 1024,
    required_l1_variables: Sequence[str] = DEFAULT_DATA_STATE_VARIABLES,
    required_substrate_families: Sequence[str] = DEFAULT_DATA_STATE_FAMILIES,
    substrate_registry_artifact_ref: ArtifactRef | str | None = None,
    period_start: str = DEFAULT_DATA_STATE_PERIOD_START,
    period_end: str = DEFAULT_DATA_STATE_PERIOD_END,
    production_data_root: Path | None = None,
) -> ProductionDataStateWorldBuildResult:
    """Build an N3 ``WorldModelRecord`` over the real S1 data-state substrate."""

    data_root = (
        Path(production_data_root).resolve()
        if production_data_root is not None
        else Path(repo_root).resolve()
    )
    if production_data_root is not None:
        _require_workspace_output_tree(workspace_dir, store.root)
    try:
        if substrate_registry_artifact_ref is None:
            materialized = materialize_l4_data_state_snapshot(
                store,
                repo_root=repo_root,
                workspace_dir=workspace_dir,
                agent_limit=agent_limit,
                required_l1_variables=required_l1_variables,
                families=DEFAULT_DATA_STATE_FAMILIES,
                period_start=period_start,
                period_end=period_end,
                production_data_root=data_root if production_data_root is not None else None,
            )
            registry = build_substrate_registry_from_existing_catalogs(
                repo_root,
                source_owner_root=data_root if production_data_root is not None else None,
            )
            persisted_registry_ref = persist_substrate_registry(store, registry)
        else:
            persisted_registry_ref, registry = _load_substrate_registry_artifact_ref(
                store,
                substrate_registry_artifact_ref,
            )
            materialized = materialize_l4_data_state_snapshot(
                store,
                repo_root=repo_root,
                workspace_dir=workspace_dir,
                agent_limit=agent_limit,
                required_l1_variables=required_l1_variables,
                families=DEFAULT_DATA_STATE_FAMILIES,
                substrate_registry=registry,
                period_start=period_start,
                period_end=period_end,
                production_data_root=data_root if production_data_root is not None else None,
            )
        registry_bundle = build_default_registry_bundle(store)
        model_spec = ModelSpec(
            model_id="model_ua_real_l4_data_state",
            data_snapshot_ref=str(materialized.data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry_bundle.bundle_ref.artifact_id),
            calibrated=True,
            calibration_ref=materialized.data_snapshot_stats["l5_profile_hash"],
            notes=[
                "gy_s1_real_l4_data_state",
                f"schema_regime_status:{materialized.l5_profile.schema_regime_status}",
            ],
        )
        fabric_root = _write_fabric_world_snapshot(
            workspace_dir=workspace_dir,
            snapshot_id=materialized.snapshot_id,
            payload_hash=materialized.payload_content_hash,
            stats=materialized.data_snapshot_stats,
            confine_outputs=production_data_root is not None,
        )
        skg_ref = _production_skg_ref(data_root, snapshot_id=materialized.snapshot_id)
        limitations = WorldModelLimitations(
            unavailable_data=tuple(
                f"l1:{item.variable_id}"
                for item in materialized.l1_availability
                if item.status == "unavailable"
            ),
            calibration_envelope_status=(
                "near_boundary"
                if materialized.l5_profile.schema_regime_status != "single_regime"
                else "inside"
            ),
            unresolved_conflicts=(
                (f"schema_regime:{materialized.l5_profile.schema_regime_status}",)
                if materialized.l5_profile.schema_regime_status != "single_regime"
                else ()
            ),
        )
        world_model = build_world_model_record(
            store,
            fabric_world_ref=FabricWorldRef(
                snapshot_root=str(fabric_root),
                snapshot_id=materialized.snapshot_id,
                branch="observed",
                as_of_valid_time="2026-05-01T00:00:00+00:00",
                as_of_tx_time="2026-05-01T00:00:00+00:00",
                world_query_policy="gy_s1_real_data_state_non_empty",
                provenance_manifest_ref=f"cas://{materialized.payload_content_hash}",
            ),
            data_forge_snapshot_binding_path=materialized.data_forge_snapshot_binding_path,
            data_snapshot_ref=materialized.data_snapshot_ref,
            model_spec=model_spec,
            skg_causal_prior_ref=skg_ref,
            substrate_registry=registry,
            substrate_registry_artifact_ref=persisted_registry_ref,
            _loaded_substrate_registry=registry,
            region_or_jurisdiction="UA",
            population_scope="ukraine_real_l4_representative_firms",
            policy_domain="fiscal_credit",
            valid_time_scope=f"{period_start}/{period_end}",
            tx_time_scope="2026-05-01T00:00:00+00:00",
            resolution="firm_month",
            branch_mode=BranchMode.OBSERVED,
            policy_slot_ids=(
                "agents.income",
                "agents.reported_income",
                "agents.skill_level",
                "agents.risk_aversion",
                "agents.is_employed",
                "agents.employer_id",
                "firms.labor_count",
                "firms.wage_offer",
                "cells.output",
                "cells.employment",
                "cells.distress_score",
                "household_cells.disposable_income",
                "household_cells.transfer_intensity",
                "household_cells.value_outer_set",
                "government.balance",
                "global.tax_rate",
            ),
            producer_ref=(
                "polisyos.runtime.quality.data_state_substrate."
                "build_production_data_state_world_model_record"
            ),
            data_forge_role=materialized.data_forge_role,
            required_substrate_families=required_substrate_families,
            limitations=limitations,
        )
    except (WorldModelRecordError, SubstrateRegistryError) as exc:
        code = getattr(exc, "code", type(exc).__name__)
        raise DataStateSubstrateError(str(code), str(exc)) from exc
    if production_data_root is not None:
        _require_workspace_output_tree(workspace_dir, store.root)
    return ProductionDataStateWorldBuildResult(
        materialization=materialized,
        world_model=world_model,
        simulation_input=consume_world_model_record_for_simulation(world_model.record),
        model_spec=model_spec,
        registry_bundle_ref=registry_bundle.bundle_ref,
        substrate_registry_ref=persisted_registry_ref,
    )


def _project_real_l4_payload(
    paths: _DataStatePaths,
    *,
    agent_limit: int | None,
    l5_profile: L5FamilyBindingProfile,
    world_model_record_ref: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    import duckdb

    params: list[object] = [agent_limit]
    query = """
        WITH latest_firm AS (
            SELECT
                agent_id,
                registration_code,
                period_id,
                revenue,
                assets,
                liabilities,
                employees,
                row_number() OVER (
                    PARTITION BY agent_id
                    ORDER BY
                        period_id DESC,
                        source_snapshot_id DESC,
                        record_hash,
                        registration_code,
                        revenue,
                        assets,
                        liabilities,
                        employees
                ) AS rn
            FROM read_parquet(?)
            WHERE revenue IS NOT NULL AND revenue > 0
        ),
        distress AS (
            SELECT
                agent_id,
                avg(CAST(corrected_exit_bias AS DOUBLE)) AS distress_score,
                max(period_id) AS distress_period_id
            FROM read_parquet(?)
            GROUP BY agent_id
        ),
        agent_registry_conflicts AS (
            SELECT
                agent_id,
                count(*) AS registry_row_count,
                count(DISTINCT COALESCE(CAST(region_code AS VARCHAR), '__NULL__'))
                    AS region_value_count,
                count(DISTINCT COALESCE(CAST(sector_id AS VARCHAR), '__NULL__'))
                    AS sector_value_count
            FROM read_parquet(?)
            GROUP BY agent_id
        ),
        agent_registry_ranked AS (
            SELECT
                agent_id,
                registration_code,
                region_code,
                sector_id,
                row_number() OVER (
                    PARTITION BY agent_id
                    ORDER BY
                        period_id DESC,
                        source_snapshot_id DESC,
                        record_hash,
                        registration_code,
                        region_code,
                        sector_id,
                        agent_id
                ) AS registry_rn
            FROM read_parquet(?)
            WHERE agent_id IS NOT NULL
        ),
        agent_registry AS (
            SELECT
                r.agent_id,
                CASE
                    WHEN c.region_value_count > 1 THEN 'ambiguous_region'
                    ELSE COALESCE(CAST(r.region_code AS VARCHAR), 'unknown_region')
                END AS region_code,
                CASE
                    WHEN c.sector_value_count > 1 THEN 'ambiguous_sector'
                    ELSE COALESCE(CAST(r.sector_id AS VARCHAR), 'unknown_sector')
                END AS sector_id,
                c.registry_row_count,
                c.region_value_count,
                c.sector_value_count
            FROM agent_registry_ranked r
            JOIN agent_registry_conflicts c USING (agent_id)
            WHERE r.registry_rn = 1
        ),
        firm_registry AS (
            SELECT
                f.agent_id,
                f.registration_code,
                a.region_code,
                a.sector_id,
                f.period_id,
                f.revenue,
                f.assets,
                f.liabilities,
                f.employees,
                a.registry_row_count,
                a.region_value_count,
                a.sector_value_count
            FROM latest_firm f
            JOIN agent_registry a USING (agent_id)
            WHERE f.rn = 1
        ),
        sample_population AS (
            SELECT
                *,
                md5(
                    COALESCE(CAST(region_code AS VARCHAR), '')
                    || ':'
                    || COALESCE(CAST(registration_code AS VARCHAR), '')
                    || ':'
                    || COALESCE(CAST(agent_id AS VARCHAR), '')
                ) AS sample_key,
                row_number() OVER (
                    PARTITION BY region_code
                    ORDER BY
                        md5(
                            COALESCE(CAST(region_code AS VARCHAR), '')
                            || ':'
                            || COALESCE(CAST(registration_code AS VARCHAR), '')
                            || ':'
                            || COALESCE(CAST(agent_id AS VARCHAR), '')
                        ),
                        registration_code,
                        agent_id
                ) AS stratum_rank,
                count(*) OVER (PARTITION BY region_code) AS stratum_population
            FROM firm_registry
        ),
        ranked_sample AS (
            SELECT
                *,
                row_number() OVER (
                    ORDER BY stratum_rank, region_code, sample_key, registration_code, agent_id
                ) AS representative_rank
            FROM sample_population
        ),
        firm_sample AS (
            SELECT *
            FROM ranked_sample
            ORDER BY representative_rank
            LIMIT COALESCE(CAST(? AS BIGINT), 9223372036854775807)
        )
        SELECT
            f.agent_id,
            f.registration_code,
            CAST(f.region_code AS VARCHAR) AS region_code,
            CAST(f.sector_id AS VARCHAR) AS sector_id,
            CAST(f.revenue AS DOUBLE) AS revenue,
            CAST(f.assets AS DOUBLE) AS assets,
            CAST(f.liabilities AS DOUBLE) AS liabilities,
            CAST(f.employees AS DOUBLE) AS employees,
            CAST(COALESCE(d.distress_score, 0.0) AS DOUBLE) AS distress_score,
            f.period_id,
            d.distress_period_id,
            f.registry_row_count,
            f.region_value_count,
            f.sector_value_count,
            f.sample_key,
            f.stratum_rank,
            f.stratum_population,
            f.representative_rank
        FROM firm_sample f
        LEFT JOIN distress d USING (agent_id)
        ORDER BY f.representative_rank, f.registration_code, f.agent_id
    """
    con = duckdb.connect(database=":memory:")
    try:
        rows = con.execute(
            query,
            [
                str(paths.firm_fundamentals_annual),
                str(paths.corrected_firm_panels),
                str(paths.agent_registry_full),
                str(paths.agent_registry_full),
                *params,
            ],
        ).fetchall()
        agent_total = int(
            con.execute(
                "SELECT count(*) FROM read_parquet(?)",
                [str(paths.agent_registry_full)],
            ).fetchone()[0]
            or 0
        )
        firm_total = int(
            con.execute(
                "SELECT count(*) FROM read_parquet(?)",
                [str(paths.firm_fundamentals_annual)],
            ).fetchone()[0]
            or 0
        )
        distress_total = int(
            con.execute(
                "SELECT count(*) FROM read_parquet(?)",
                [str(paths.corrected_firm_panels)],
            ).fetchone()[0]
            or 0
        )
        budget_total = int(
            con.execute(
                "SELECT count(*) FROM read_parquet(?)",
                [str(paths.budget_flows_monthly_sparse)],
            ).fetchone()[0]
            or 0
        )
        budget_slice = con.execute(
            """
            SELECT
                count(*) AS row_count,
                COALESCE(sum(CAST(amount AS DOUBLE)), 0.0) AS amount_sum
            FROM (
                SELECT amount
                FROM read_parquet(?)
                LIMIT 100000
            )
            """,
            [str(paths.budget_flows_monthly_sparse)],
        ).fetchone()
        household_rows = con.execute(
            """
            SELECT
                cell_id,
                region_code,
                household_income_mean,
                household_weight_sum,
                measurement_bias_flag,
                trust_weight,
                market_income_mean,
                total_expenditure_mean
            FROM read_parquet(?)
            ORDER BY period_id DESC, region_code, cell_id
            LIMIT 100
            """,
            [str(paths.calibrated_household_cells)],
        ).fetchall()
    finally:
        con.close()
    if not rows:
        return {}, {
            "bound_agent_count": 0,
            "l4_total_rows": {
                "agent_registry_full": 0,
                "firm_fundamentals_annual": 0,
                "corrected_firm_panels": 0,
                "budget_flows_monthly_sparse": 0,
            },
        }
    return _payload_from_rows(
        rows=rows,
        household_rows=household_rows,
        l5_profile=l5_profile,
        world_model_record_ref=world_model_record_ref,
        budget_slice_count=int(budget_slice[0] or 0),
        budget_slice_amount_sum=float(budget_slice[1] or 0.0),
        totals={
            "agent_registry_full": agent_total,
            "firm_fundamentals_annual": firm_total,
            "corrected_firm_panels": distress_total,
            "budget_flows_monthly_sparse": budget_total,
        },
    )


def _payload_from_rows(
    *,
    rows: Sequence[Sequence[Any]],
    household_rows: Sequence[Sequence[Any]],
    l5_profile: L5FamilyBindingProfile,
    world_model_record_ref: str,
    budget_slice_count: int,
    budget_slice_amount_sum: float,
    totals: Mapping[str, int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    sector_ids = sorted({str(row[3] or "unknown") for row in rows})
    sector_index = {sector: idx for idx, sector in enumerate(sector_ids)}
    cell_keys = sorted({(str(row[2] or "0"), str(row[3] or "unknown")) for row in rows})
    cell_index = {key: idx for idx, key in enumerate(cell_keys)}

    income: list[float] = []
    reported_income: list[float] = []
    skill_level: list[float] = []
    risk_aversion: list[float] = []
    is_employed: list[bool] = []
    employer_id: list[int] = []
    household_cell_id: list[int] = []
    firms_labor_count: list[float] = []
    firms_wage_offer: list[float] = []
    firms_active: list[bool] = []
    firms_firm_id: list[int] = []
    firms_cell_id: list[int] = []
    firms_type_id: list[int] = []
    cell_accumulators = {
        key: {"count": 0.0, "employment": 0.0, "output": 0.0, "distress": []} for key in cell_keys
    }
    for idx, row in enumerate(rows):
        (
            _agent_id,
            _registration_code,
            region_code,
            sector_id,
            revenue,
            assets,
            liabilities,
            employees,
            distress_score,
            _period_id,
            _distress_period_id,
            _registry_row_count,
            _region_value_count,
            _sector_value_count,
            _sample_key,
            _stratum_rank,
            _stratum_population,
            _representative_rank,
        ) = row
        revenue_f = max(0.0, float(revenue or 0.0))
        employees_f = max(0.0, float(employees or 0.0))
        assets_f = max(0.0, float(assets or 0.0))
        liabilities_f = max(0.0, float(liabilities or 0.0))
        sector = str(sector_id or "unknown")
        key = (str(region_code or "0"), sector)
        cell_id = cell_index[key]
        income.append(revenue_f)
        reported_income.append(revenue_f)
        skill_level.append(max(1.0, min(10.0, employees_f + 1.0)))
        risk_aversion.append(max(0.1, min(0.9, liabilities_f / max(assets_f, 1.0))))
        is_employed.append(employees_f > 0.0)
        employer_id.append(idx)
        household_cell_id.append(-1)
        firms_labor_count.append(employees_f)
        firms_wage_offer.append(revenue_f / max(employees_f, 1.0) / 12.0)
        firms_active.append(True)
        firms_firm_id.append(idx)
        firms_cell_id.append(cell_id)
        firms_type_id.append(sector_index[sector])
        acc = cell_accumulators[key]
        acc["count"] = float(acc["count"]) + 1.0
        acc["employment"] = float(acc["employment"]) + employees_f
        acc["output"] = float(acc["output"]) + revenue_f
        acc["distress"].append(float(distress_score or 0.0))

    cell_region_code = [_region_numeric(key[0]) for key in cell_keys]
    cell_sector_id = [sector_index[key[1]] for key in cell_keys]
    cell_population = [float(cell_accumulators[key]["count"]) for key in cell_keys]
    cell_employment = [float(cell_accumulators[key]["employment"]) for key in cell_keys]
    cell_output = [float(cell_accumulators[key]["output"]) for key in cell_keys]
    cell_distress = [_mean_or_zero(cell_accumulators[key]["distress"]) for key in cell_keys]

    household_authority = l5_profile.family_authority("household_distribution")
    household_payload = _household_payload(
        household_rows,
        household_authority,
        l5_profile=l5_profile,
        world_model_record_ref=world_model_record_ref,
    )
    household_value_set = household_payload.get("value_outer_set", {})
    household_interval_widths = [
        max(0.0, float(width))
        for coordinate, width in zip(
            household_value_set.get("coordinates", ()),
            household_value_set.get("width", ()),
            strict=False,
        )
        if str(coordinate).startswith("household_cells.disposable_income[")
    ]
    payload = {
        "agents": {
            "income": income,
            "reported_income": reported_income,
            "skill_level": skill_level,
            "risk_aversion": risk_aversion,
            "is_employed": is_employed,
            "employer_id": employer_id,
            "household_cell_id": household_cell_id,
        },
        "firms": {
            "active": firms_active,
            "firm_id": firms_firm_id,
            "cell_id": firms_cell_id,
            "firm_type_id": firms_type_id,
            "labor_count": firms_labor_count,
            "wage_offer": firms_wage_offer,
        },
        "cells": {
            "active": [True for _ in cell_keys],
            "region_code": cell_region_code,
            "sector_id": cell_sector_id,
            "population": cell_population,
            "employment": cell_employment,
            "output": cell_output,
            "distress_score": cell_distress,
            "public_service_index": [1.0 for _ in cell_keys],
            "firm_count": cell_population,
        },
        "government_balance": budget_slice_amount_sum,
        "tax_rate": 0.0,
    }
    if household_payload:
        payload["household_cells"] = household_payload
    stats = {
        "bound_agent_count": len(rows),
        "bound_firm_count": len(rows),
        "bound_cell_count": len(cell_keys),
        "bound_household_cell_count": len(household_payload.get("cell_id", ())),
        "agent_registry_resolution_strategy": (
            "canonical_latest_record_then_ambiguous_region_sector_for_conflicts"
        ),
        "selected_agent_registry_duplicate_count": sum(1 for row in rows if int(row[11] or 0) > 1),
        "selected_agent_registry_inconsistent_count": sum(
            1 for row in rows if int(row[12] or 0) > 1 or int(row[13] or 0) > 1
        ),
        "ambiguous_region_agent_count": sum(
            1 for row in rows if str(row[2] or "") == "ambiguous_region"
        ),
        "ambiguous_sector_agent_count": sum(
            1 for row in rows if str(row[3] or "") == "ambiguous_sector"
        ),
        "sample_strategy": "deterministic_region_stratified_hash",
        "sample_stratification": "region_code",
        "bound_region_count": len({str(row[2] or "unknown_region") for row in rows}),
        "bound_sector_count": len(sector_ids),
        "household_identification_mode": household_authority.identification_mode,
        "household_value_authority": household_authority.value_authority,
        "household_trust_tier": household_authority.trust_tier,
        "household_trust_cap": household_authority.trust_cap,
        "household_proxy_bound_count": sum(1 for width in household_interval_widths if width > 0.0),
        "household_point_tight_count": sum(
            1 for width in household_interval_widths if width == 0.0
        ),
        "household_disposable_income_interval_width_sum": round(
            sum(household_interval_widths),
            6,
        ),
        "budget_slice_row_count": budget_slice_count,
        "budget_slice_amount_sum": round(float(budget_slice_amount_sum), 6),
        "l4_total_rows": dict(totals),
        "d3_bias_corrected_sources": [
            "corrected_firm_panels.parquet",
            "calibrated_household_cells.parquet",
        ],
    }
    return payload, stats


def _household_payload(
    rows: Sequence[Sequence[Any]],
    authority: L5FamilyAuthority,
    *,
    l5_profile: L5FamilyBindingProfile,
    world_model_record_ref: str,
) -> dict[str, Any]:
    if not rows:
        return {}
    point_authority = authority.value_authority == "point"

    household_count: list[float] = []
    disposable_income: list[float] = []
    income_interval_lower: list[float] = []
    income_interval_upper: list[float] = []
    poverty_rate: list[float] = []
    poverty_interval_lower: list[float] = []
    poverty_interval_upper: list[float] = []
    transfer_intensity: list[float] = []
    transfer_interval_lower: list[float] = []
    transfer_interval_upper: list[float] = []
    for row in rows:
        income = max(0.0, float(row[2] or 0.0))
        weight = max(0.0, float(row[3] or 0.0))
        biased = bool(row[4])
        trust_weight = _clamp(float(row[5] or 0.0), 0.0, 1.0)
        market_income = max(0.0, float(row[6] or income))
        expenditure = max(0.0, float(row[7] or income))
        effective_trust = min(trust_weight, authority.trust_cap)
        uncertainty = max(0.0, 1.0 - effective_trust)

        if point_authority:
            income_lower = income_upper = income
            poverty_lower = poverty_upper = 1.0 if biased else 0.0
            transfer = _clamp(1.0 - trust_weight, 0.0, 1.0)
            transfer_lower = transfer_upper = transfer
        else:
            candidate_values = [income, market_income, expenditure]
            d3_lower = min(candidate_values)
            d3_upper = max(candidate_values)
            margin = max(
                income * uncertainty * 0.25,
                income * (0.05 if biased else 0.0),
                1.0 if income > 0.0 else 0.0,
            )
            income_lower = max(0.0, min(d3_lower, income - margin))
            income_upper = max(income_lower, d3_upper, income + margin)

            poverty = 1.0 if biased else 0.0
            poverty_margin = max(0.02, uncertainty * 0.25, 0.10 if biased else 0.0)
            poverty_lower = _clamp(poverty - poverty_margin, 0.0, 1.0)
            poverty_upper = max(poverty_lower, _clamp(poverty + poverty_margin, 0.0, 1.0))

            transfer = _clamp(1.0 - trust_weight, 0.0, 1.0)
            transfer_margin = max(0.02, uncertainty * 0.5)
            transfer_lower = _clamp(transfer - transfer_margin, 0.0, 1.0)
            transfer_upper = max(
                transfer_lower,
                _clamp(transfer + transfer_margin, 0.0, 1.0),
            )

        household_count.append(weight)
        disposable_income.append(income)
        income_interval_lower.append(income_lower)
        income_interval_upper.append(income_upper)
        poverty_rate.append(1.0 if biased else 0.0)
        poverty_interval_lower.append(poverty_lower)
        poverty_interval_upper.append(poverty_upper)
        transfer = _clamp(1.0 - trust_weight, 0.0, 1.0)
        transfer_intensity.append(transfer)
        transfer_interval_lower.append(transfer_lower)
        transfer_interval_upper.append(transfer_upper)

    coordinates: list[str] = []
    lower: list[float] = []
    upper: list[float] = []
    for idx in range(len(rows)):
        coordinates.extend(
            [
                f"household_cells.disposable_income[{idx}]",
                f"household_cells.poverty_rate[{idx}]",
                f"household_cells.transfer_intensity[{idx}]",
            ]
        )
        lower.extend(
            [
                income_interval_lower[idx],
                poverty_interval_lower[idx],
                transfer_interval_lower[idx],
            ]
        )
        upper.extend(
            [
                income_interval_upper[idx],
                poverty_interval_upper[idx],
                transfer_interval_upper[idx],
            ]
        )

    regime_scope = (
        l5_profile.regime_ids[0]
        if l5_profile.schema_regime_status == "single_regime" and l5_profile.regime_ids
        else f"{l5_profile.schema_regime_status}:{'|'.join(l5_profile.regime_ids)}"
    )
    value_outer_set = ValueOuterSet.interval_box(
        coordinates=tuple(coordinates),
        lower=tuple(lower),
        upper=tuple(upper),
        identification_mode=authority.identification_mode,
        assumptions=(
            "d3_bias_corrected_household_cells",
            f"l5_identification_mode:{authority.identification_mode}",
            f"schema_regime_status:{l5_profile.schema_regime_status}",
        ),
        assumption_status="externally_supported",
        calibration_scope={
            "population": "ukraine_household_cells",
            "regime": regime_scope,
            "measurement": authority.family_id,
        },
        data_trust=DataTrust(
            tier=authority.trust_tier,
            trust_cap=authority.trust_cap,
            trust_multiplier=authority.trust_multiplier,
            min_coverage=authority.min_coverage,
            max_coverage=authority.max_coverage,
            promotion_floor=authority.promotion_floor,
            authority_ref=authority.measurement_registry_ref,
        ),
        world_model_record_ref=world_model_record_ref,
        epoch=regime_scope,
        representation_status="certified",
    )

    return {
        "active": [True for _ in rows],
        "cell_id": [idx for idx, _row in enumerate(rows)],
        "household_count": household_count,
        "disposable_income": disposable_income,
        "poverty_rate": poverty_rate,
        "transfer_intensity": transfer_intensity,
        "value_outer_set": value_outer_set.model_dump(mode="json"),
    }


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _data_forge_snapshot_manifest_extra(
    *,
    corpus_id: str,
    builder_revision: str,
    lineage_refs: Sequence[str] | None,
    claim_requirement_bindings: Sequence[Mapping[str, Any]] | None,
    payload_content_hash: str,
) -> dict[str, object]:
    """Construct the existing publisher extra values without side effects."""
    return {
        "corpus_id": corpus_id,
        "builder_revision": builder_revision,
        "lineage_refs": list(
            lineage_refs
            if lineage_refs is not None
            else (
                payload_content_hash,
                "repo://production_data/canonical/local_data_20260501/"
                "ukraine_server_support_20260410/normalized_corpus",
                "repo://production_data/datasets_full_phase3full_20260327_183054/"
                "dataset_catalog.duckdb",
            )
        ),
        "claim_requirement_bindings": [
            dict(item)
            for item in (
                claim_requirement_bindings
                if claim_requirement_bindings is not None
                else (
                    {
                        "claim_id": "gy-s1-real-l4-data-state",
                        "requirement_id": "gy-s1-l1-l4-l5-data-state",
                        "requirement_kind": "production_data_state",
                        "authority_level": "closeout",
                        "time_role": "observation_time",
                    },
                )
            )
        ],
    }


def _data_forge_payload_file_bytes(payload: Mapping[str, Any]) -> bytes:
    """Use the existing publisher file encoding, also for prospective captured bytes."""
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _acquired_claim_requirement_bindings(variable_id: str) -> tuple[dict[str, str], ...]:
    """Construct the existing candidate-only claim row before finalizer defaults."""
    return (
        {
            "claim_id": "candidate-acquired-world-state",
            "requirement_id": f"candidate-observation:{variable_id}",
            "requirement_kind": "candidate_acquisition_observation",
            "authority_level": "candidate",
            "time_role": "transaction_time",
        },
    )


def _write_data_forge_snapshot_binding(
    *,
    workspace_dir: Path,
    snapshot_id: str,
    payload: Mapping[str, Any],
    payload_content_hash: str,
    published_at: str = "2026-05-01T00:00:00+00:00",
    corpus_id: str = "ukraine-real-l4-data-state",
    builder_revision: str = (
        "polisyos.runtime.quality.data_state_substrate.materialize_l4_data_state_snapshot"
    ),
    lineage_refs: Sequence[str] | None = None,
    claim_requirement_bindings: Sequence[Mapping[str, Any]] | None = None,
    confine_outputs: bool = False,
) -> Path:
    snapshot_root = workspace_dir / snapshot_id
    pipeline_root = snapshot_root / _DATA_FORGE_SNAPSHOT_PIPELINE
    artifact_path = pipeline_root / "data_state_payload.json"
    manifest_path = pipeline_root / "publish" / "manifest.json"
    if confine_outputs:
        snapshot_root = _require_workspace_output_tree(workspace_dir, snapshot_root)
        artifact_path = _require_workspace_output_path(workspace_dir, artifact_path)
        manifest_path = _require_workspace_output_path(workspace_dir, manifest_path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    if confine_outputs:
        artifact_path = _require_workspace_output_path(workspace_dir, artifact_path)
        manifest_path = _require_workspace_output_path(workspace_dir, manifest_path)
    artifact_path.write_bytes(_data_forge_payload_file_bytes(payload))
    if confine_outputs:
        _require_workspace_output_tree(workspace_dir, snapshot_root)
    data_forge_read_api.write_publish_manifest(
        manifest_path=manifest_path,
        pipeline=_DATA_FORGE_SNAPSHOT_PIPELINE,
        artifacts=(artifact_path,),
        published_at=published_at,
        extra=_data_forge_snapshot_manifest_extra(
            corpus_id=corpus_id,
            builder_revision=builder_revision,
            lineage_refs=lineage_refs,
            claim_requirement_bindings=claim_requirement_bindings,
            payload_content_hash=payload_content_hash,
        ),
    )
    if confine_outputs:
        _require_workspace_output_tree(workspace_dir, snapshot_root)
    data_forge_read_api.finalize_snapshot(
        snapshot_root,
        update_latest_symlink=False,
        pipelines=(_DATA_FORGE_SNAPSHOT_PIPELINE,),
    )
    binding_path = snapshot_root / "data_forge_snapshot_binding.json"
    if confine_outputs:
        binding_path = _require_workspace_output_path(workspace_dir, binding_path)
        _require_workspace_output_tree(workspace_dir, snapshot_root)
    return binding_path


def _cas_data_forge_ref(ref: ArtifactRef) -> str:
    """Return the Data Forge CAS URI form for one content-addressed artifact."""

    digest = str(ref.artifact_id).removeprefix("sha256:")
    return f"cas://sha256/{digest}"


def _write_fabric_world_snapshot(
    *,
    workspace_dir: Path,
    snapshot_id: str,
    payload_hash: str,
    stats: Mapping[str, Any],
    confine_outputs: bool = False,
) -> Path:
    from polisyos.fabric.world import (
        WorldSnapshotFactWrite,
        WorldSnapshotNodeWrite,
        WorldSnapshotWriteRequest,
        write_world_snapshot,
    )

    snapshot_root = workspace_dir / "fabric-world"
    native_db_root = workspace_dir / "fabric-world-db"
    if confine_outputs:
        snapshot_root = _require_workspace_output_tree(workspace_dir, snapshot_root)
        native_db_root = _require_workspace_output_tree(workspace_dir, native_db_root)
        db_path = native_db_root / "fabric-world.duckdb"
    else:
        db_path = workspace_dir / "fabric-world.duckdb"
    temp_root = db_path.with_name(db_path.name + ".tmp")
    if confine_outputs:
        temp_root = _require_workspace_output_tree(workspace_dir, temp_root)
    snapshot_root.mkdir(parents=True, exist_ok=True)
    if confine_outputs:
        native_db_root.mkdir(parents=True, exist_ok=True)
        native_db_root = _require_workspace_output_tree(workspace_dir, native_db_root)
        temp_root = _require_workspace_output_tree(workspace_dir, temp_root)
        temp_root.mkdir(parents=True, exist_ok=True)
        temp_root = _require_workspace_output_tree(workspace_dir, temp_root)
        # The entire physical database parent is the preflight boundary. This
        # catches WAL and future sidecars before SimulationDB opens anything.
        native_db_root = _require_workspace_output_tree(workspace_dir, native_db_root)
        db_path = _require_workspace_output_path(workspace_dir, db_path)
    else:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    node_id = f"world.data_state.{snapshot_id}"
    world_node = WorldSnapshotNodeWrite(
        node_id=node_id,
        kind="data_state",
        label="GY-S1 real L4 data-state substrate",
        artifact_id=payload_hash,
        props_ref=None,
    )
    bound_agent_count_fact = WorldSnapshotFactWrite(
        fact_id=f"fact:{snapshot_id}:bound_agent_count",
        schema_version="1.0",
        subject_id=node_id,
        predicate_id="data_state.bound_agent_count",
        object_value=str(stats.get("bound_agent_count") or 0),
        target_id=None,
        valid_time="2026-05-01T00:00:00Z",
        tx_time="2026-05-01T00:00:00Z",
        provenance_json={"producer": "data_state_substrate"},
        trust_json=None,
        legal_json=None,
        segment_id=f"seg:{snapshot_id}:count",
    )
    payload_hash_fact = WorldSnapshotFactWrite(
        fact_id=f"fact:{snapshot_id}:payload_hash",
        schema_version="1.0",
        subject_id=node_id,
        predicate_id="data_state.payload_hash",
        object_value=payload_hash,
        target_id=None,
        valid_time="2026-05-01T00:00:00Z",
        tx_time="2026-05-01T00:00:00Z",
        provenance_json={"producer": "data_state_substrate"},
        trust_json=None,
        legal_json=None,
        segment_id=f"seg:{snapshot_id}:hash",
    )
    request = WorldSnapshotWriteRequest(
        snapshot_root=snapshot_root,
        snapshot_id=snapshot_id,
        branch_name="observed",
        as_of_valid_time="2026-05-01T00:00:00+00:00",
        as_of_tx_time="2026-05-01T00:00:00+00:00",
        provenance={"producer": "polisyos.runtime.quality.data_state_substrate"},
        nodes=(world_node,),
        facts=(bound_agent_count_fact, payload_hash_fact),
    )
    if confine_outputs:
        _require_workspace_output_tree(workspace_dir, snapshot_root)
        _require_workspace_output_tree(workspace_dir, native_db_root)
        write_world_snapshot(db_path, request, temp_directory=temp_root)
        _require_workspace_output_tree(workspace_dir, native_db_root)
        _require_workspace_output_tree(workspace_dir, snapshot_root)
        _require_workspace_output_path(workspace_dir, db_path)
    else:
        write_world_snapshot(db_path, request)
    return snapshot_root


def _acquired_candidate_fabric_rows(
    *,
    snapshot_id: str,
    payload_hash: str,
    transaction_time: str,
) -> tuple[WorldSnapshotNodeWrite, tuple[WorldSnapshotFactWrite, ...]]:
    """Prepare the actual native rows; no world is written by this constructor."""
    from polisyos.fabric.world import WorldSnapshotFactWrite, WorldSnapshotNodeWrite

    node_id = f"world.acquisition-candidate.{snapshot_id}"
    node = WorldSnapshotNodeWrite(
        node_id=node_id,
        kind="candidate_acquired_data_state",
        label="Candidate state with unresolved source time and causal coupling",
        artifact_id=payload_hash,
        props_ref=None,
    )
    facts = (
        WorldSnapshotFactWrite(
            fact_id=f"fact:{snapshot_id}:candidate_data_snapshot",
            schema_version="1.0",
            subject_id=node_id,
            predicate_id="data_state.candidate_snapshot",
            object_value=payload_hash,
            target_id=None,
            valid_time=None,
            tx_time=transaction_time,
            provenance_json={"producer": "data_state_substrate"},
            trust_json=None,
            legal_json=None,
            segment_id=f"seg:{snapshot_id}:candidate",
        ),
    )
    return node, facts


def _write_acquired_candidate_fabric_snapshot(
    *,
    workspace_dir: Path,
    snapshot_id: str,
    payload_hash: str,
    transaction_time: str,
    as_of_valid_time: str | None,
) -> Path:
    """Use Fabric's snapshot writer with unknown valid time for acquired facts."""
    from polisyos.fabric.world import (
        WorldSnapshotWriteRequest,
        write_world_snapshot,
    )

    snapshot_root = workspace_dir / "fabric-world"
    db_path = workspace_dir / "fabric-world.duckdb"
    # Materialize the caller-owned job workspace before the file-backed writer.
    snapshot_root.mkdir(parents=True, exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    node, facts = _acquired_candidate_fabric_rows(
        snapshot_id=snapshot_id,
        payload_hash=payload_hash,
        transaction_time=transaction_time,
    )
    write_world_snapshot(
        db_path,
        WorldSnapshotWriteRequest(
            snapshot_root=snapshot_root,
            snapshot_id=snapshot_id,
            branch_name="candidate",
            as_of_valid_time=as_of_valid_time,
            as_of_tx_time=transaction_time,
            provenance={
                "producer": "polisyos.runtime.quality.data_state_substrate",
                "source_time_status": "not_established",
                "valid_time_role": "unknown",
            },
            nodes=(node,),
            facts=facts,
        ),
    )
    return snapshot_root


def _production_skg_ref(repo_root: Path, *, snapshot_id: str) -> SkgCausalPriorRef:
    from polisyos.data_forge.read_api.academic import SKGQuery

    db_path = repo_root / _ACADEMIC_SKG_DB
    if not db_path.exists():
        raise DataStateSubstrateError("skg_prior_ref_unresolved", db_path.as_posix())
    query = SKGQuery(db_path=db_path, index_dir=db_path.parent / "index")
    try:
        version_id = query.latest_skg_version_id()
        snapshot_ref = query.skg_snapshot_ref(version_id=version_id)
    finally:
        query.close()
    if snapshot_ref is None:
        raise DataStateSubstrateError("skg_prior_ref_unresolved", "missing SKG snapshot ref")
    return SkgCausalPriorRef(
        skg_snapshot_ref=snapshot_ref,
        skg_version_id=str(version_id),
        source_data_snapshot_id=snapshot_id,
        edge_prior_refs=("skg-edge://gy-s1-forward-hook",),
        transport_score_refs=("skg-transport://gy-s1-forward-hook",),
        query_trace_refs=("g2-skg-query-trace://gy-s1-forward-hook",),
    )


def _schema_regime_decision(
    l5: L5CatalogAuthority,
    *,
    receipt: L5SchemaRegimeDenominatorReceipt,
    projection: ScopedSchemaRegimeProjection,
    period_start: str,
    period_end: str,
) -> dict[str, Any]:
    start_month = _month_ordinal(period_start)
    end_month = _month_ordinal(period_end)
    if start_month > end_month:
        raise DataStateSubstrateError("schema_regime_period_order_invalid")
    if projection.status != "resolved":
        raise DataStateSubstrateError("l5_schema_regime_projection_unresolved")
    if (
        l5.resolve_schema_regime_denominator(query=receipt.query) != receipt
        or l5.project_scoped_schema_regimes(receipt=receipt) != projection
    ):
        raise DataStateSubstrateError("l5_schema_regime_projection_not_owner_recomputed")
    regimes = []
    for regime_id, observed_hash in zip(
        projection.applicable_regime_ids,
        projection.applicable_regime_content_hashes,
        strict=True,
    ):
        regime = l5.schema_regimes.get(regime_id)
        row = l5.schema_regime_rows.get(regime_id)
        if regime is None or row is None:
            raise DataStateSubstrateError("l5_schema_regime_projection_unknown", regime_id)
        expected_hash = f"sha256:{hashlib.sha256(canonical_epoch_bytes(dict(row))).hexdigest()}"
        if observed_hash != expected_hash:
            raise DataStateSubstrateError(
                "l5_schema_regime_projection_hash_mismatch",
                regime_id,
            )
        regimes.append(regime)
    selected = tuple(
        regime
        for regime in regimes
        if (regime.effective_start is None or _month_ordinal(regime.effective_start) <= end_month)
        and (regime.effective_end is None or _month_ordinal(regime.effective_end) >= start_month)
    )
    changepoints_by_ref = {
        f"sha256:{hashlib.sha256(canonical_epoch_bytes(dict(row))).hexdigest()}": row
        for row in l5.schema_regime_changepoints
        if row.get("effective_date") is not None
    }
    if len(changepoints_by_ref) != len(
        tuple(row for row in l5.schema_regime_changepoints if row.get("effective_date") is not None)
    ):
        raise DataStateSubstrateError("l5_schema_regime_changepoint_hash_ambiguous")
    try:
        changepoints = tuple(changepoints_by_ref[ref] for ref in projection.changepoint_refs)
    except KeyError as exc:
        raise DataStateSubstrateError("l5_schema_regime_changepoint_ref_unknown") from exc
    crossing = tuple(
        row
        for row in changepoints
        if start_month < _month_ordinal(str(row["effective_date"])) <= end_month
    )
    linked_ids = {
        str(row[key])
        for row in crossing
        for key in ("from_schema_regime_id", "to_schema_regime_id")
        if row.get(key) is not None
    }
    if linked_ids:
        try:
            linked = tuple(l5.schema_regimes[regime_id] for regime_id in linked_ids)
        except KeyError as exc:
            raise DataStateSubstrateError("l5_schema_regime_changepoint_target_unknown") from exc
        selected = tuple(
            sorted(
                {row.schema_regime_id: row for row in (*selected, *linked)}.values(),
                key=lambda row: row.effective_start or "",
            )
        )
    if not selected:
        raise DataStateSubstrateError("l5_schema_regime_missing")
    nearest = min(
        changepoints,
        key=lambda row: min(
            abs(start_month - _month_ordinal(str(row["effective_date"]))),
            abs(end_month - _month_ordinal(str(row["effective_date"]))),
        ),
        default=None,
    )
    boundary_buffer = max((regime.boundary_buffer_periods or 0 for regime in selected), default=0)
    near_boundary = (
        nearest is not None
        and min(
            abs(start_month - _month_ordinal(str(nearest["effective_date"]))),
            abs(end_month - _month_ordinal(str(nearest["effective_date"]))),
        )
        <= boundary_buffer
    )
    if crossing or len(selected) > 1:
        status = "spans_changepoint_flagged"
    elif near_boundary:
        status = "boundary_buffer_flagged"
    else:
        status = "single_regime"
    changepoint = crossing[0] if crossing else nearest
    return {
        "schema_regime_status": status,
        "regime_ids": tuple(regime.schema_regime_id for regime in selected),
        "changepoint_id": None if changepoint is None else str(changepoint["changepoint_id"]),
        "changepoint_period": (
            None if changepoint is None else str(changepoint["effective_date"])[:7]
        ),
        "boundary_buffer_periods": boundary_buffer,
    }


def _default_data_state_paths(
    repo_root: Path,
    *,
    production_data_root: Path | None = None,
) -> _DataStatePaths:
    code_root = Path(repo_root).resolve()
    data_root = (
        Path(production_data_root).resolve() if production_data_root is not None else code_root
    )
    base = (
        data_root / "production_data/canonical/local_data_20260501/ukraine_server_support_20260410"
    )
    normalized = base / "normalized_corpus/normalized"
    d3 = base / "runtime_calibration_internals/calibration/d3"
    l1 = default_substrate_catalog_paths(
        code_root,
        source_owner_root=data_root if production_data_root is not None else None,
    ).l1_dcat_path
    return _DataStatePaths(
        l1_dcat_path=l1,
        agent_registry_full=normalized / "edr_current/agent_registry_full.parquet",
        firm_fundamentals_annual=(normalized / "dps_financials/firm_fundamentals_annual.parquet"),
        budget_flows_monthly_sparse=(
            normalized / "spending_full/budget_flows_monthly_sparse.parquet"
        ),
        corrected_firm_panels=d3 / "corrected_firm_panels.parquet",
        calibrated_household_cells=d3 / "calibrated_household_cells.parquet",
    )


def _require_paths(
    paths: _DataStatePaths,
    *,
    production_data_root: Path | None = None,
) -> None:
    required_paths = (
        paths.l1_dcat_path,
        paths.agent_registry_full,
        paths.firm_fundamentals_annual,
        paths.budget_flows_monthly_sparse,
        paths.corrected_firm_panels,
        paths.calibrated_household_cells,
    )
    for path in required_paths:
        if not path.exists():
            raise DataStateSubstrateError("production_data_path_missing", path.as_posix())
    if production_data_root is not None:
        for path in required_paths:
            try:
                _repo_relative_path(path, repo_root=production_data_root)
            except SubstrateRegistryError as exc:
                raise DataStateSubstrateError("production_data_path_unbound", str(exc)) from exc


def _require_split_data_workspace(
    workspace_dir: Path,
    *,
    code_root: Path,
    data_root: Path,
    cas_root: Path,
) -> None:
    """Keep split-source outputs inside an isolated caller-owned workspace."""

    try:
        workspace = Path(workspace_dir).resolve(strict=True)
        code = Path(code_root).resolve(strict=True)
        data = Path(data_root).resolve(strict=True)
        cas = Path(cas_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise DataStateSubstrateError("split_data_workspace_unavailable") from exc
    if not workspace.is_dir():
        raise DataStateSubstrateError("split_data_workspace_not_directory")
    if any(
        workspace == source_root
        or source_root in workspace.parents
        or workspace in source_root.parents
        for source_root in (code, data)
    ):
        raise DataStateSubstrateError("split_data_workspace_overlaps_source_root")
    if cas != workspace and workspace not in cas.parents:
        raise DataStateSubstrateError("split_data_cas_outside_workspace")


def _relative_source_paths(paths: _DataStatePaths, root: Path) -> dict[str, str]:
    return {
        key: path.relative_to(root).as_posix()
        for key, path in {
            "l1_dcat_path": paths.l1_dcat_path,
            "agent_registry_full": paths.agent_registry_full,
            "firm_fundamentals_annual": paths.firm_fundamentals_annual,
            "budget_flows_monthly_sparse": paths.budget_flows_monthly_sparse,
            "corrected_firm_panels": paths.corrected_firm_panels,
            "calibrated_household_cells": paths.calibrated_household_cells,
        }.items()
    }


def _world_preimage_ref(
    *,
    substrate_version_id: str,
    agent_limit: int | None,
    required_l1_variables: Sequence[str],
    families: Sequence[str],
    period_start: str,
    period_end: str,
    branch_mode: str,
) -> str:
    preimage = {
        "schema_version": DATA_STATE_SUBSTRATE_SCHEMA_VERSION,
        "world_identity_kind": "gy-n3-world-preimage",
        "substrate_version_id": substrate_version_id,
        "slice": {
            "agent_limit": "full" if agent_limit is None else int(agent_limit),
            "sample_strategy": "deterministic_region_stratified_hash",
        },
        "required_l1_variables": tuple(sorted(str(item) for item in required_l1_variables)),
        "families": tuple(sorted(str(item) for item in families)),
        "period_start": period_start,
        "period_end": period_end,
        "branch_mode": branch_mode,
    }
    return f"gy-n3:world-preimage:{gy_content_hash(preimage)}"


def _snapshot_id(*, agent_limit: int | None, payload_hash: str) -> str:
    prefix = "gy-s1-l4-data-state"
    limit = "full" if agent_limit is None else str(agent_limit)
    suffix = payload_hash.removeprefix("sha256:")[:16]
    return f"{prefix}-{limit}-{suffix}"


def _require_selected_profile(ref: ArtifactRef, error_code: str) -> None:
    if not isinstance(ref, ArtifactRef) or ref.manifest_profile_sha256 is None:
        raise DataStateSubstrateError(error_code)


def _value_authority_for_identification(
    mode: str,
) -> Literal["point", "bounds", "proxy_bounds", "limited"]:
    if mode == "point_identified":
        return "point"
    if mode == "proxy_identified":
        return "proxy_bounds"
    if mode in {"partially_identified", "bounds_only"}:
        return "bounds"
    return "limited"


def _month_ordinal(period: str) -> int:
    parts = period.split("-")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise DataStateSubstrateError("schema_regime_period_invalid", period)
    return int(parts[0]) * 12 + int(parts[1])


def _region_numeric(value: str) -> int:
    digits = "".join(char for char in value if char.isdigit())
    return int(digits or 0)


def _mean_or_zero(values: object) -> float:
    if not isinstance(values, list) or not values:
        return 0.0
    return float(sum(float(value) for value in values) / len(values))


__all__ = [
    "ACQUIRED_DATA_STATE_LIMITATION_CODES",
    "ACQUIRED_DATA_STATE_SCHEMA_VERSION",
    "DATA_STATE_SUBSTRATE_SCHEMA_VERSION",
    "AcquiredObservationDataPreparation",
    "AcquiredObservationDataSnapshotResult",
    "ControlledAcquisitionSlotBinding",
    "DataStateMaterializationResult",
    "DataStateSubstrateError",
    "L1VariableAvailability",
    "L5FamilyAuthority",
    "L5FamilyBindingProfile",
    "ProductionDataStateWorldBuildResult",
    "build_l5_family_binding_profile",
    "build_production_data_state_world_model_record",
    "l1_dcat_variable_availability",
    "materialize_acquired_observation_snapshot",
    "materialize_l4_data_state_snapshot",
    "prepare_acquired_observation_snapshot",
]
