"""Versioned world-model bridge over Fabric, Data Forge, IR, Foundry, and SKG.

This module owns only the lifecycle envelope. It does not store facts, own
runtime state, execute mechanisms, or replace SKG priors; it binds existing
substrates into one content-addressed world version that downstream simulation
and value steps can name and resolve.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
)

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, InputRef, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts import (
    ExecPlanRef,
    ExecuteRequest,
    FoundryInputBindingsRef,
)
from polisyos.pdc import (
    WORLD_MODEL_RECORD_ARTIFACT_KIND,
    WORLD_MODEL_RECORD_SCHEMA_NAME,
    WORLD_MODEL_RECORD_SCHEMA_VERSION,
    BranchMode,
    DataForgeBindingRef,
    DeploymentUpdateRefs,
    FabricWorldRef,
    FoundryBindingRef,
    PolicySlotBinding,
    ResolvedSubstrateEntryRef,
    SimulationModelRef,
    SkgCausalPriorRef,
    SubstrateRegistryRef,
    WorldModelLimitations,
    WorldModelRecord,
    gy_content_hash,
    world_model_record_content_hash_from_fields,
)
from polisyos.pdc import (
    SubstrateLayer as _SubstrateLayer,
)
from polisyos.pdc import (
    world_model_record_content_hash as _world_model_record_content_hash,
)
from polisyos.runtime.quality.substrate_registry import (
    SubstrateRegistry,
    SubstrateRegistryEntry,
    SubstrateRegistryError,
)

if TYPE_CHECKING:
    from polisyos.core.contracts import DataSnapshot, FoundryInputBindingRule, StateSnapshotRef
    from polisyos.ir import ModelSpec
    from polisyos.ir.kernel import SlotRegistry
    from polisyos.runtime.quality.intervention_atom_binding import InterventionAtomBinding

_DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION = "policyos.runtime.data_forge_snapshot_binding.v1"

# Compatibility exports preserve the historical Runtime module surface while
# PDC owns the exact objects.
SubstrateLayer = _SubstrateLayer
world_model_record_content_hash = _world_model_record_content_hash


class WorldModelRecordError(ValueError):
    """Fail-closed error raised when world substrates cannot form one version."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class _StrictModel(BaseModel):
    """Strict immutable base model for Runtime-owned consumer DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class WorldModelSimulationInput(_StrictModel):
    """Consumer DTO for running Foundry execution against a world record."""

    world_model_record_id: str
    world_model_record_content_hash: str
    schema_version: str
    branch_mode: BranchMode
    input_bindings_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    bound_state_snapshot_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    registry_bundle_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")

    def to_execute_request(self, *, exec_plan_ref: ExecPlanRef) -> ExecuteRequest:
        """Build a Foundry ``ExecuteRequest`` using this record's bound state."""

        return ExecuteRequest(
            exec_plan_ref=exec_plan_ref,
            input_bindings_ref=FoundryInputBindingsRef(artifact_id=self.input_bindings_ref),
            registry_bundle_ref=ArtifactRef(
                artifact_id=self.registry_bundle_ref,
                kind="core.registry_bundle",
                media_type="application/json",
            ),
            notes=[
                f"world_model_record_id:{self.world_model_record_id}",
                f"world_model_record_content_hash:{self.world_model_record_content_hash}",
            ],
        )


class ResolvedWorldModelAtomBinding(_StrictModel):
    """Resolved N2 atom hook with concrete world version and state paths."""

    world_model_record_id: str
    world_model_record_content_hash: str
    schema_version: str
    branch_mode: BranchMode
    target_slot_bindings: tuple[PolicySlotBinding, ...]
    input_bindings_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    bound_state_snapshot_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class WorldModelBuildResult:
    """Collect the record and real bound Foundry state emitted by the builder."""

    record: WorldModelRecord
    record_ref: ArtifactRef
    input_bindings_ref: FoundryInputBindingsRef
    input_binding_report_ref: ArtifactRef
    bound_state_snapshot_ref: StateSnapshotRef
    bound_global_state: object
    data_snapshot_ref: ArtifactRef


@dataclass(frozen=True)
class _ParsedSkgSnapshotRef:
    """Parsed local SKG snapshot locator resolved by the SKG owner."""

    db_path: Path
    version_id: int


@dataclass(frozen=True)
class _FabricWorldContentSignal:
    """Stable content signal from owner-resolved Fabric world query results."""

    digest: str
    row_count: int


class _FabricQueryFrame(Protocol):
    """Minimal DataFrame surface returned by Fabric world queries."""

    columns: Sequence[object]

    def to_dict(self, orient: str = "dict") -> object:
        """Return rows in a pandas-compatible dictionary orientation."""
        ...


def build_world_model_record(
    store: FileSystemCAS,
    *,
    fabric_world_ref: FabricWorldRef,
    data_forge_snapshot_binding_path: str | Path,
    data_snapshot_ref: ArtifactRef,
    model_spec: ModelSpec,
    skg_causal_prior_ref: SkgCausalPriorRef,
    substrate_registry: SubstrateRegistry,
    region_or_jurisdiction: str,
    population_scope: str,
    policy_domain: str,
    valid_time_scope: str,
    tx_time_scope: str,
    resolution: str,
    branch_mode: BranchMode,
    policy_slot_ids: Sequence[str],
    producer_ref: str,
    data_forge_role: str = "academic",
    required_substrate_sources: Sequence[str] = (),
    required_substrate_families: Sequence[str] = (),
    substrate_registry_artifact_ref: ArtifactRef | str | None = None,
    foundry_binding_rules: Sequence[FoundryInputBindingRule] | None = None,
    mechanism_refs: Sequence[str] = (),
    gcm_refs: Sequence[str] = (),
    ncm_refs: Sequence[str] = (),
    program_graph_refs: Sequence[str] = (),
    limitations: WorldModelLimitations | None = None,
    deployment_update_refs: DeploymentUpdateRefs | None = None,
) -> WorldModelBuildResult:
    """Build and persist one versioned world record from existing substrates.

    Args:
        store: CAS store containing the Fabric ``DataSnapshot`` and receiving
            the Foundry bindings plus record artifact.
        fabric_world_ref: Fabric world snapshot/branch/as-of reference.
        data_forge_snapshot_binding_path: Path to the Data Forge binding file
            emitted by ``data_forge.kernel.snapshot``.
        data_snapshot_ref: CAS ref to the Fabric ``DataSnapshot`` consumed by
            Foundry.
        model_spec: Existing IR simulation contract for this world.
        skg_causal_prior_ref: SKG/G2 prior and transport trace reference.
        substrate_registry: S0 production-data substrate registry this world
            version resolves against.
        region_or_jurisdiction: Jurisdiction this world version represents.
        population_scope: Population this world version represents.
        policy_domain: Policy domain of the world version.
        valid_time_scope: Valid-time scope carried into bitemporal consumers.
        tx_time_scope: Transaction-time scope carried into audit consumers.
        resolution: World-model resolution, such as ``firm_month``.
        branch_mode: Observed/scenario/deployment-update branch semantics.
        policy_slot_ids: Slots that candidate atoms may target in this world.
        producer_ref: Producer reference for the lifecycle bridge.
        data_forge_role: Binding row role to select from the Data Forge report.
        required_substrate_sources: Source ids that must resolve in S0.
        required_substrate_families: Family ids that must resolve in S0.
        substrate_registry_artifact_ref: Optional CAS ref to the persisted S0
            registry artifact.
        foundry_binding_rules: Optional explicit Foundry input binding rules.
        mechanism_refs: Existing mechanism refs to name; mechanisms remain
            owned by Foundry/IR registries.
        gcm_refs: Existing GCM refs to name.
        ncm_refs: Existing NCM refs to name.
        program_graph_refs: Existing program graph refs to name.
        limitations: Explicit limitation record, if already known.
        deployment_update_refs: Phase-6 forward hooks, not write-back logic.

    Raises:
        WorldModelRecordError: If any required substrate is missing or versions
            do not content-correspond.

    Returns:
        ``WorldModelBuildResult`` containing the persisted record and the real
        bound ``GlobalState`` emitted by Foundry input bindings.
    """

    if not model_spec.registry_bundle_ref:
        raise WorldModelRecordError(
            "model_spec_registry_bundle_missing",
            "ModelSpec must name the registry bundle used by Foundry binding",
        )
    data_snapshot = _load_data_snapshot(store, data_snapshot_ref)
    data_snapshot_id = _data_snapshot_version_id(data_snapshot)
    if not data_snapshot_id:
        raise WorldModelRecordError(
            "data_snapshot_version_missing",
            "DataSnapshot must carry stats.snapshot_id or notes snapshot_id:<id>",
        )
    data_forge_binding_ref = _load_data_forge_binding_ref(
        data_forge_snapshot_binding_path,
        role=data_forge_role,
    )
    resolved_fabric_world_ref = _resolve_fabric_world_ref(fabric_world_ref)
    _resolve_skg_causal_prior_ref(skg_causal_prior_ref)
    substrate_registry_ref = _resolve_substrate_registry_ref(
        substrate_registry,
        required_sources=required_substrate_sources,
        required_families=required_substrate_families,
        registry_artifact_ref=substrate_registry_artifact_ref,
    )
    _assert_same_world_version(
        fabric_world_ref=resolved_fabric_world_ref,
        data_forge_binding_ref=data_forge_binding_ref,
        model_spec=model_spec,
        data_snapshot_ref=data_snapshot_ref,
        data_snapshot_id=data_snapshot_id,
        skg_causal_prior_ref=skg_causal_prior_ref,
    )

    registry_bundle_ref = ArtifactRef(
        artifact_id=model_spec.registry_bundle_ref,
        kind="core.registry_bundle",
        media_type="application/json",
    )
    from polisyos.core.registry import load_registry_bundle_content
    from polisyos.foundry.data_plane import build_input_bindings, load_input_bindings
    from polisyos.foundry.execute.executor import load_state_snapshot

    registry_content = load_registry_bundle_content(store, registry_bundle_ref)
    policy_slot_map = _policy_slot_map(
        registry_content.slot_registry,
        policy_slot_ids=policy_slot_ids,
    )
    input_bindings = build_input_bindings(
        store,
        data_snapshot_ref=data_snapshot_ref,
        registry_bundle_ref=registry_bundle_ref,
        rules=list(foundry_binding_rules or []),
        notes=[f"world_model_record_snapshot_id:{data_snapshot_id}"],
    )
    persisted_bindings = load_input_bindings(store, input_bindings.input_bindings_ref)
    if str(persisted_bindings.data_snapshot_ref.artifact_id) != str(data_snapshot_ref.artifact_id):
        raise WorldModelRecordError(
            "world_substrate_version_mismatch",
            "Foundry input bindings do not point at the requested DataSnapshot",
        )

    model_spec_ref = store.put_json(
        model_spec,
        PutOptions(
            kind="ir.model_spec",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.ir.model_layer.ModelSpec",
                version=model_spec.schema_version,
            ),
        ),
    )
    state_slot_digest = gy_content_hash(
        {
            "bound_state_snapshot_ref": str(input_bindings.bound_state_snapshot_ref.artifact_id),
            "policy_slot_map": [binding.model_dump(mode="json") for binding in policy_slot_map],
        }
    )
    fields: dict[str, Any] = {
        "schema_version": WORLD_MODEL_RECORD_SCHEMA_VERSION,
        "authority_status": "bound",
        "producer_ref": producer_ref,
        "region_or_jurisdiction": region_or_jurisdiction,
        "population_scope": population_scope,
        "policy_domain": policy_domain,
        "valid_time_scope": valid_time_scope,
        "tx_time_scope": tx_time_scope,
        "resolution": resolution,
        "branch_mode": branch_mode,
        "fabric_world_ref": resolved_fabric_world_ref,
        "data_forge_binding_ref": data_forge_binding_ref,
        "simulation_model_ref": SimulationModelRef(
            model_spec_ref=str(model_spec_ref.artifact_id),
            model_spec_hash=gy_content_hash(model_spec.model_dump(mode="json")),
            model_id=model_spec.model_id,
            data_snapshot_ref=model_spec.data_snapshot_ref,
            registry_bundle_ref=str(registry_bundle_ref.artifact_id),
            mechanism_refs=tuple(mechanism_refs),
            gcm_refs=tuple(gcm_refs),
            ncm_refs=tuple(ncm_refs),
            program_graph_refs=tuple(program_graph_refs),
            assumptions=tuple(
                assumption.model_dump(mode="json") for assumption in model_spec.assumptions
            ),
            fidelity_level=str(model_spec.fidelity_level.value),
            calibration_ref=model_spec.calibration_ref,
            calibrated=model_spec.calibrated,
        ),
        "foundry_binding_ref": FoundryBindingRef(
            input_bindings_ref=str(input_bindings.input_bindings_ref.artifact_id),
            bound_state_snapshot_ref=str(input_bindings.bound_state_snapshot_ref.artifact_id),
            mapping_rules_ref=str(input_bindings.input_binding_report_ref.artifact_id),
            state_slot_digest=state_slot_digest,
        ),
        "skg_causal_prior_ref": skg_causal_prior_ref,
        "substrate_registry_ref": substrate_registry_ref,
        "policy_slot_map": tuple(policy_slot_map),
        "limitations": limitations or WorldModelLimitations(),
        "deployment_update_refs": deployment_update_refs or DeploymentUpdateRefs(),
    }
    content_hash = world_model_record_content_hash_from_fields(fields)
    record = WorldModelRecord(
        world_model_record_id=f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **fields,
    )
    record_ref = persist_world_model_record(
        store,
        record,
        inputs=[
            InputRef(artifact_id=data_snapshot_ref.artifact_id, role="input.data_snapshot_ref"),
            InputRef(artifact_id=registry_bundle_ref.artifact_id, role="input.registry_bundle_ref"),
            InputRef(artifact_id=model_spec_ref.artifact_id, role="input.model_spec_ref"),
            InputRef(
                artifact_id=input_bindings.input_bindings_ref.artifact_id,
                role="artifact.input_bindings_ref",
            ),
            InputRef(
                artifact_id=input_bindings.bound_state_snapshot_ref.artifact_id,
                role="artifact.bound_state_snapshot_ref",
            ),
        ],
    )
    bound_state = load_state_snapshot(store, snapshot_ref=input_bindings.bound_state_snapshot_ref)
    return WorldModelBuildResult(
        record=record,
        record_ref=record_ref,
        input_bindings_ref=input_bindings.input_bindings_ref,
        input_binding_report_ref=input_bindings.input_binding_report_ref,
        bound_state_snapshot_ref=input_bindings.bound_state_snapshot_ref,
        bound_global_state=bound_state,
        data_snapshot_ref=data_snapshot_ref,
    )


def consume_world_model_record_for_simulation(
    record: WorldModelRecord,
) -> WorldModelSimulationInput:
    """Return the Foundry execution boundary resolved from a world record."""

    validated = WorldModelRecord.model_validate(record.model_dump(mode="json"))
    return WorldModelSimulationInput(
        world_model_record_id=validated.world_model_record_id,
        world_model_record_content_hash=validated.content_hash,
        schema_version=validated.schema_version,
        branch_mode=validated.branch_mode,
        input_bindings_ref=validated.foundry_binding_ref.input_bindings_ref,
        bound_state_snapshot_ref=validated.foundry_binding_ref.bound_state_snapshot_ref,
        registry_bundle_ref=validated.simulation_model_ref.registry_bundle_ref,
    )


def resolve_intervention_atom_world_binding(
    atom: InterventionAtomBinding,
    record: WorldModelRecord,
) -> ResolvedWorldModelAtomBinding:
    """Resolve an N2 atom's world hook and target slots against a concrete record.

    Args:
        atom: ``InterventionAtomBinding`` carrying the forward
            ``world_model_record_ref`` and target slots.
        record: Concrete world record candidate to bind against.

    Raises:
        WorldModelRecordError: If the atom references a different world version
            or any target slot lacks a state path in the policy-slot map.

    Returns:
        Resolved target slot bindings and Foundry state refs.
    """

    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
    )

    try:
        if not isinstance(atom, InterventionAtomBinding):
            raise TypeError("intervention_atom_binding_contract_required")
        validated_atom = InterventionAtomBinding.model_validate(atom.model_dump(mode="python"))
    except (AttributeError, TypeError, ValidationError) as exc:
        raise WorldModelRecordError(
            "intervention_atom_binding_invalid",
            str(exc),
        ) from exc
    if not validated_atom.target_world_slots:
        raise WorldModelRecordError(
            "world_slot_binding_missing",
            "an atom must resolve at least one target world slot",
        )
    validated = WorldModelRecord.model_validate(record.model_dump(mode="json"))
    accepted_refs = {
        validated.world_model_record_id,
        validated.content_hash,
    }
    if validated_atom.world_model_record_ref not in accepted_refs:
        raise WorldModelRecordError(
            "world_model_record_ref_unresolved",
            (
                f"{validated_atom.world_model_record_ref} does not name "
                f"{validated.world_model_record_id}"
            ),
        )
    resolved: list[PolicySlotBinding] = []
    for slot_id in validated_atom.target_world_slots:
        binding = validated.slot_binding(slot_id)
        if binding is None or not binding.state_path:
            raise WorldModelRecordError(
                "world_slot_state_path_missing",
                f"slot {slot_id!r} has no state_path in WorldModelRecord",
            )
        resolved.append(binding)
    return ResolvedWorldModelAtomBinding(
        world_model_record_id=validated.world_model_record_id,
        world_model_record_content_hash=validated.content_hash,
        schema_version=validated.schema_version,
        branch_mode=validated.branch_mode,
        target_slot_bindings=tuple(resolved),
        input_bindings_ref=validated.foundry_binding_ref.input_bindings_ref,
        bound_state_snapshot_ref=validated.foundry_binding_ref.bound_state_snapshot_ref,
    )


def persist_world_model_record(
    store: FileSystemCAS,
    record: WorldModelRecord,
    *,
    inputs: Sequence[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a ``WorldModelRecord`` as a typed CAS artifact."""

    validated = WorldModelRecord.model_validate(record.model_dump(mode="json"))
    return store.put_json(
        validated,
        PutOptions(
            kind=WORLD_MODEL_RECORD_ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=WORLD_MODEL_RECORD_SCHEMA_NAME,
                version=validated.schema_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_world_model_record(store: FileSystemCAS, ref: ArtifactRef | str) -> WorldModelRecord:
    """Load a persisted ``WorldModelRecord`` from CAS and verify its hash."""

    artifact_id = ref.artifact_id if isinstance(ref, ArtifactRef) else ref
    payload = from_canonical_bytes(store.get_bytes(artifact_id))
    return WorldModelRecord.model_validate(payload)


def _load_data_snapshot(store: FileSystemCAS, ref: ArtifactRef) -> DataSnapshot:
    from polisyos.core.contracts import DataSnapshot

    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return DataSnapshot.model_validate(payload)


def _data_snapshot_version_id(snapshot: DataSnapshot) -> str:
    stats = getattr(snapshot, "stats", None)
    if isinstance(stats, Mapping):
        value = stats.get("snapshot_id") or stats.get("version_id")
        if value:
            return str(value)
    notes = getattr(snapshot, "notes", None) or []
    for note in notes:
        text = str(note)
        if text.startswith("snapshot_id:"):
            return text.split(":", 1)[1].strip()
    return ""


def _load_data_forge_binding_ref(path: str | Path, *, role: str) -> DataForgeBindingRef:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != _DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION:
        raise WorldModelRecordError(
            "data_forge_snapshot_binding_schema_mismatch",
            str(payload.get("schema_version")),
        )
    rows = payload.get("bindings")
    if not isinstance(rows, list) or not rows:
        raise WorldModelRecordError("data_forge_snapshot_binding_missing")
    selected = None
    for row in rows:
        if isinstance(row, Mapping) and str(row.get("role") or "") == role:
            selected = row
            break
    if selected is None:
        raise WorldModelRecordError(
            "data_forge_snapshot_binding_role_missing",
            f"role {role!r} not found",
        )
    snapshot_id = str(payload.get("snapshot_id") or "")
    row_snapshot_id = str(selected.get("snapshot_id") or "")
    if not snapshot_id or row_snapshot_id != snapshot_id:
        raise WorldModelRecordError(
            "data_forge_snapshot_binding_snapshot_mismatch",
            f"{row_snapshot_id!r} != {snapshot_id!r}",
        )
    return DataForgeBindingRef(
        snapshot_id=snapshot_id,
        release_id=str(payload.get("release_id") or selected.get("release_id") or ""),
        role=role,
        read_api_identity=str(selected.get("read_api_identity") or ""),
        snapshot_ref=str(selected.get("snapshot_ref") or ""),
        merkle_root=str(selected.get("merkle_root") or ""),
        data_hash=str(selected.get("data_hash") or ""),
        claim_requirement_bindings=tuple(
            dict(item)
            for item in selected.get("claim_requirement_bindings") or []
            if isinstance(item, Mapping)
        ),
        quality_gate_refs=_quality_gate_refs(selected.get("quality_gates")),
        lineage_refs=tuple(str(item) for item in selected.get("lineage_refs") or []),
        provenance_manifest_ref=str(
            selected.get("provenance_manifest_ref") or payload.get("provenance_manifest_ref") or ""
        ),
        binding_path=str(Path(path)),
    )


def _quality_gate_refs(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    refs: list[str] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        ref = item.get("artifact_id") or item.get("name")
        if ref:
            refs.append(str(ref))
    return tuple(refs)


def _resolve_fabric_world_ref(fabric_world_ref: FabricWorldRef) -> FabricWorldRef:
    """Resolve Fabric snapshot and branch refs through the Fabric owner."""

    root = Path(fabric_world_ref.snapshot_root)
    if not root.exists():
        raise WorldModelRecordError(
            "fabric_world_snapshot_unresolved",
            f"snapshot_root does not exist: {root}",
        )

    import polisyos.fabric as fabric

    try:
        exact_snapshot = fabric.resolve_world_snapshot(
            root,
            snapshot_id=fabric_world_ref.snapshot_id,
        )
        branch_snapshot = fabric.resolve_world_snapshot(
            root,
            branch_name=fabric_world_ref.branch,
            as_of_tx_time=fabric_world_ref.as_of_tx_time,
            as_of_valid_time=fabric_world_ref.as_of_valid_time,
        )
        if branch_snapshot.snapshot_id != exact_snapshot.snapshot_id:
            raise WorldModelRecordError(
                "fabric_world_snapshot_unresolved",
                (
                    f"branch {fabric_world_ref.branch!r} resolves to "
                    f"{branch_snapshot.snapshot_id!r}, not {fabric_world_ref.snapshot_id!r}"
                ),
            )
        with fabric.SimulationDB(db_path=":memory:") as fabric_db:
            exact_frame = fabric.execute_world_query(
                fabric_db,
                fabric.WorldQueryRequest(
                    table="world_nodes",
                    columns=("node_id", "kind", "label", "artifact_id", "props_ref"),
                    order_by=("node_id",),
                    snapshot_root=root,
                    snapshot_id=fabric_world_ref.snapshot_id,
                    limit=100_000,
                ),
            )
            branch_frame = fabric.execute_world_query(
                fabric_db,
                fabric.WorldQueryRequest(
                    table="world_nodes",
                    columns=("node_id", "kind", "label", "artifact_id", "props_ref"),
                    order_by=("node_id",),
                    snapshot_root=root,
                    branch=fabric_world_ref.branch,
                    as_of_tx_time=fabric_world_ref.as_of_tx_time,
                    as_of_valid_time=fabric_world_ref.as_of_valid_time,
                    limit=100_000,
                ),
            )
        signal = _fabric_world_content_signal(
            exact_frame=exact_frame,
            branch_frame=branch_frame,
        )
        return fabric_world_ref.model_copy(
            update={
                "content_query_digest": signal.digest,
                "content_query_row_count": signal.row_count,
            }
        )
    except WorldModelRecordError:
        raise
    except fabric.WorldQueryError as exc:
        raise WorldModelRecordError("fabric_world_not_queryable", str(exc)) from exc
    except (FileNotFoundError, TypeError, ValueError, OSError) as exc:
        raise WorldModelRecordError("fabric_world_snapshot_unresolved", str(exc)) from exc


def _fabric_world_content_signal(
    *,
    exact_frame: _FabricQueryFrame,
    branch_frame: _FabricQueryFrame,
) -> _FabricWorldContentSignal:
    exact_rows = _fabric_query_rows(exact_frame, label="snapshot_id")
    branch_rows = _fabric_query_rows(branch_frame, label="branch")
    if not exact_rows:
        raise WorldModelRecordError(
            "fabric_world_empty",
            "Fabric snapshot query returned no world_nodes rows",
        )
    if not branch_rows:
        raise WorldModelRecordError(
            "fabric_world_as_of_empty",
            "Fabric branch/as-of query returned no world_nodes rows",
        )
    return _FabricWorldContentSignal(
        digest=gy_content_hash(
            {
                "fabric_world_content_query": {
                    "table": "world_nodes",
                    "exact_snapshot_rows": exact_rows,
                    "exact_snapshot_row_count": len(exact_rows),
                    "branch_as_of_rows": branch_rows,
                    "branch_as_of_row_count": len(branch_rows),
                }
            }
        ),
        row_count=len(exact_rows),
    )


def _fabric_query_rows(
    frame: _FabricQueryFrame,
    *,
    label: str,
) -> tuple[dict[str, Any], ...]:
    if not hasattr(frame, "to_dict") or not hasattr(frame, "columns"):
        raise WorldModelRecordError(
            "fabric_world_not_queryable",
            f"Fabric {label} query did not return a DataFrame-like result",
        )
    columns = tuple(str(column) for column in frame.columns)
    if "node_id" not in columns:
        raise WorldModelRecordError(
            "fabric_world_not_queryable",
            f"Fabric {label} query result is missing node_id",
        )
    raw_rows = frame.to_dict(orient="records")
    if not isinstance(raw_rows, list):
        raise WorldModelRecordError(
            "fabric_world_not_queryable",
            f"Fabric {label} query result cannot be serialized",
        )
    return tuple(
        {
            str(key): _json_scalar(value)
            for key, value in sorted(row.items(), key=lambda item: str(item[0]))
        }
        for row in raw_rows
        if isinstance(row, Mapping)
    )


def _json_scalar(value: object) -> object:
    if value is None:
        return None
    try:
        if value != value:
            return None
    except (TypeError, ValueError):
        pass
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except (TypeError, ValueError):
            pass
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    return value


def _resolve_skg_causal_prior_ref(skg_causal_prior_ref: SkgCausalPriorRef) -> None:
    """Resolve SKG snapshot refs and versions through the SKG query owner."""

    try:
        parsed = _parse_skg_snapshot_ref(skg_causal_prior_ref.skg_snapshot_ref)
    except WorldModelRecordError as exc:
        raise WorldModelRecordError("skg_prior_ref_unresolved", str(exc)) from exc
    if str(parsed.version_id) != str(skg_causal_prior_ref.skg_version_id):
        raise WorldModelRecordError(
            "skg_prior_ref_unresolved",
            (
                "skg_snapshot_ref version does not match skg_version_id: "
                f"{parsed.version_id} != {skg_causal_prior_ref.skg_version_id}"
            ),
        )
    if not parsed.db_path.exists():
        raise WorldModelRecordError(
            "skg_prior_ref_unresolved",
            f"SKG DuckDB path does not exist: {parsed.db_path}",
        )

    import polisyos.data_forge as data_forge

    query = data_forge.read_api.academic.SKGQuery(
        db_path=parsed.db_path,
        index_dir=parsed.db_path.parent / "index",
    )
    try:
        if not query.has_skg_version_id(version_id=parsed.version_id):
            raise WorldModelRecordError(
                "skg_prior_ref_unresolved",
                f"SKG version not found: {parsed.version_id}",
            )
        owner_ref = query.skg_snapshot_ref(version_id=parsed.version_id)
    except WorldModelRecordError:
        raise
    except (TypeError, ValueError, OSError) as exc:
        raise WorldModelRecordError("skg_prior_ref_unresolved", str(exc)) from exc
    finally:
        query.close()
    if owner_ref is None:
        raise WorldModelRecordError(
            "skg_prior_ref_unresolved",
            f"SKG owner returned no snapshot ref for version {parsed.version_id}",
        )
    if _normalize_skg_snapshot_ref(owner_ref) != _normalize_skg_snapshot_ref(
        skg_causal_prior_ref.skg_snapshot_ref
    ):
        raise WorldModelRecordError(
            "skg_prior_ref_unresolved",
            f"{skg_causal_prior_ref.skg_snapshot_ref!r} does not resolve to {owner_ref!r}",
        )


def _resolve_substrate_registry_ref(
    substrate_registry: SubstrateRegistry,
    *,
    required_sources: Sequence[str],
    required_families: Sequence[str],
    registry_artifact_ref: ArtifactRef | str | None,
) -> SubstrateRegistryRef:
    validated = SubstrateRegistry.model_validate(substrate_registry.model_dump(mode="json"))
    resolved: list[SubstrateRegistryEntry] = []
    try:
        for source_id in required_sources:
            resolved.extend(validated.resolve(source_id=source_id))
        for family_id in required_families:
            resolved.extend(validated.resolve(family_id=family_id))
    except SubstrateRegistryError as exc:
        raise WorldModelRecordError(exc.code, str(exc)) from exc
    if not required_sources and not required_families:
        resolved = list(validated.entries)
    unique = {
        entry.registry_key: entry
        for entry in sorted(
            resolved,
            key=lambda item: (item.layer.value, item.source_id, item.family_id),
        )
    }
    if not unique:
        raise WorldModelRecordError("substrate_registry_entries_missing")
    return SubstrateRegistryRef(
        substrate_version_id=validated.substrate_version_id,
        content_hash=validated.content_hash,
        registry_artifact_ref=_artifact_ref_text(registry_artifact_ref),
        resolved_entries=tuple(
            ResolvedSubstrateEntryRef(
                source_id=entry.source_id,
                family_id=entry.family_id,
                layer=entry.layer,
                coverage_score=entry.coverage.coverage_score,
                trust_tier=entry.trust_tier.tier,
                trust_cap=entry.trust_tier.trust_cap,
                identification_mode=entry.identification_mode,
                schema_regime_id=entry.schema_regime.schema_regime_id,
                data_version=entry.data_version,
                snapshot_id=entry.snapshot_id,
                source_snapshot_id=entry.source_snapshot_id,
                entry_content_hash=entry.entry_content_hash,
            )
            for entry in unique.values()
        ),
    )


def _artifact_ref_text(ref: ArtifactRef | str | None) -> str | None:
    if ref is None:
        return None
    if isinstance(ref, ArtifactRef):
        return str(ref.artifact_id)
    return str(ref)


def _parse_skg_snapshot_ref(raw_ref: str) -> _ParsedSkgSnapshotRef:
    prefix = "duckdb://"
    if not raw_ref.startswith(prefix):
        raise WorldModelRecordError("skg_prior_ref_unresolved", "SKG ref must use duckdb://")
    locator = raw_ref.removeprefix(prefix)
    path_text, separator, version_text = locator.partition("#v")
    if not path_text or separator != "#v" or not version_text:
        raise WorldModelRecordError(
            "skg_prior_ref_unresolved",
            f"SKG ref must include a DuckDB path and #v version: {raw_ref}",
        )
    try:
        version_id = int(version_text)
    except ValueError as exc:
        raise WorldModelRecordError(
            "skg_prior_ref_unresolved",
            f"SKG version is not an integer: {version_text}",
        ) from exc
    return _ParsedSkgSnapshotRef(db_path=Path(path_text), version_id=version_id)


def _assert_same_world_version(
    *,
    fabric_world_ref: FabricWorldRef,
    data_forge_binding_ref: DataForgeBindingRef,
    model_spec: ModelSpec,
    data_snapshot_ref: ArtifactRef,
    data_snapshot_id: str,
    skg_causal_prior_ref: SkgCausalPriorRef,
) -> None:
    snapshot_ids = {
        "fabric_world_ref.snapshot_id": fabric_world_ref.snapshot_id,
        "data_forge_binding_ref.snapshot_id": data_forge_binding_ref.snapshot_id,
        "data_snapshot_ref.snapshot_id": data_snapshot_id,
        "skg_causal_prior_ref.source_data_snapshot_id": (
            skg_causal_prior_ref.source_data_snapshot_id
        ),
    }
    if len(set(snapshot_ids.values())) != 1:
        raise WorldModelRecordError(
            "world_substrate_version_mismatch",
            json.dumps(snapshot_ids, sort_keys=True),
        )
    if model_spec.data_snapshot_ref != str(data_snapshot_ref.artifact_id):
        raise WorldModelRecordError(
            "world_substrate_version_mismatch",
            (
                "ModelSpec.data_snapshot_ref does not match the Fabric "
                f"DataSnapshot CAS ref: {model_spec.data_snapshot_ref} != "
                f"{data_snapshot_ref.artifact_id}"
            ),
        )


def _policy_slot_map(
    slot_registry: SlotRegistry,
    *,
    policy_slot_ids: Sequence[str],
) -> tuple[PolicySlotBinding, ...]:
    if not policy_slot_ids:
        raise WorldModelRecordError("policy_slot_map_missing")
    bindings: list[PolicySlotBinding] = []
    for slot_id in policy_slot_ids:
        slot = slot_registry.slots.get(str(slot_id))
        if slot is None or not getattr(slot, "state_path", None):
            raise WorldModelRecordError(
                "world_slot_state_path_missing",
                f"slot {slot_id!r} has no state_path in registry",
            )
        unit = getattr(getattr(slot, "unit", None), "unit_id", None)
        scope = getattr(getattr(slot, "scope", None), "value", getattr(slot, "scope", None))
        kind = getattr(getattr(slot, "kind", None), "value", getattr(slot, "kind", None))
        bindings.append(
            PolicySlotBinding(
                slot_id=str(slot_id),
                state_path=str(slot.state_path),
                unit=None if unit is None else str(unit),
                entity_scope=str(scope),
                temporal_granularity=str(kind or "unspecified"),
            )
        )
    return tuple(bindings)


def _normalize_skg_snapshot_ref(raw_ref: str) -> str:
    try:
        parsed = _parse_skg_snapshot_ref(raw_ref)
    except WorldModelRecordError:
        return raw_ref
    return f"duckdb://{parsed.db_path.name}#v{parsed.version_id}"
