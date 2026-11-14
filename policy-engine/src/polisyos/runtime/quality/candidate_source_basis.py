"""Reopen candidate-source inputs for the existing acquisition basis comparator.

This adapter neither decides equality nor issues an evaluation, passport, epoch,
world, or context. Its values describe a declared candidate computation. Source
currentness, scientific independence, measurement validity, and publication
authority remain limited by the real source and snapshot owners.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from polisyos.core import artifacts, canon
from polisyos.core.contracts import (
    CandidateAcquisitionSourceDataSnapshotLineage,
    DataSnapshot,
    RetrievalSummary,
)
from polisyos.runtime.quality.candidate_simulation import (
    CandidateSimulationScenarioProfile,
    CandidateSimulationSyntheticModelDeclarationV1,
)
from polisyos.runtime.quality.data_state_substrate import CandidateAcquisitionSourceSlotBinding

if TYPE_CHECKING:
    from typing import Any

    from polisyos.core.contracts import FoundryInputBindingRule
    from polisyos.foundry.data_plane import InputBindingValuesPreparation
    from polisyos.ir.connectors import FetchResult
    from polisyos.runtime.quality.acquisition_route_loop import (
        VerifiedAcquisitionRouteClosure,
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
        CandidateAcquisitionWorldIntent,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        _VerifiedCurrentCandidateExperimentReentryAction,
    )
    from polisyos.runtime.quality.candidate_acquisition_source import CandidateAcquisitionSource
    from polisyos.runtime.quality.cycle_substrate import AcquiredCandidateModelValues
    from polisyos.runtime.quality.data_state_substrate import AcquiredObservationWorldPreparation
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.generation_cycle import CandidateSourceReentryReceipt
    from polisyos.runtime.quality.world_model_record import (
        WorldModelLimitations,
        WorldModelRecord,
    )

_PRODUCER = "polisyos.runtime.quality.data_state_substrate.build_candidate_acquisition_world"


class CandidateSourceBasisInputs(BaseModel):
    """Exact historical selectors and candidate configuration, without a live lease."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    configured_profile: CandidateSimulationScenarioProfile
    original_model_declaration: CandidateSimulationSyntheticModelDeclarationV1
    base_data_snapshot_ref: artifacts.ArtifactRef
    base_world_model_ref: artifacts.ArtifactRef | None = None
    candidate_source_ref: artifacts.ArtifactRef
    slot_binding: CandidateAcquisitionSourceSlotBinding
    transaction_time: AwareDatetime

    @model_validator(mode="after")
    def _selected_inputs(self) -> CandidateSourceBasisInputs:
        for ref, kind in (
            (self.base_data_snapshot_ref, "fabric.data_snapshot"),
            (self.candidate_source_ref, "runtime.quality.candidate_acquisition_source"),
        ):
            if (
                ref.manifest_profile_sha256 is None
                or ref.kind != kind
                or ref.media_type != "application/json"
            ):
                raise ValueError("candidate_source_basis_selected_input_missing")
        if self.base_world_model_ref is not None and (
            self.base_world_model_ref.kind != "runtime.quality.world_model_record"
            or self.base_world_model_ref.media_type != "application/json"
            or self.base_world_model_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("candidate_source_basis_selected_base_world_missing")
        return self


@dataclass(frozen=True)
class CandidateSourceBasisPredecessor:
    """One prior producer transaction and its exact selected output views.

    This is a replay input, not proof of a route, action, lease, or N5 result.
    The calling owner must independently establish those facts.
    """

    inputs: CandidateSourceBasisInputs
    data_snapshot_ref: artifacts.ArtifactRef
    world_model_ref: artifacts.ArtifactRef


@dataclass(frozen=True)
class CandidateSourceBasisValues:
    """Worker-local owner values; only the existing complete comparator may decide.

    The payload bytes are ephemeral input to the real Foundry preparer and are
    excluded from the repr. They are not a durable raw-source logging surface.
    A partial result must never be treated as evidence of equal computations.
    """

    predicate_provenance: Literal["recomputed", "not_established"]
    reason_codes: tuple[str, ...]
    inputs: CandidateSourceBasisInputs | None = None
    effective_values: dict[str, object] = field(default_factory=dict)
    prospective_values: InputBindingValuesPreparation | None = field(default=None, repr=False)
    prospective_model: AcquiredCandidateModelValues | None = field(default=None, repr=False)
    payload_json: bytes | None = field(default=None, repr=False)
    foundry_binding_rule: FoundryInputBindingRule | None = None
    produced_data_snapshot_ref: artifacts.ArtifactRef | None = None
    produced_world_model_ref: artifacts.ArtifactRef | None = None
    canonical_base_data_snapshot_ref: artifacts.ArtifactRef | None = None


def candidate_experiment_input_changed(
    *,
    prior: object,
    previous_source: object,
    current_source: object,
    prepared: CandidateSourceBasisValues,
) -> bool:
    """Detect an owner-derived numerical input change without asserting equivalence."""
    from polisyos.ir import candidate_ncm_spec_from_declaration, prepare_ncm_spec_selected_values
    from polisyos.runtime.quality.acquisition_evaluation import ResolvedAcquisitionEvaluation
    from polisyos.runtime.quality.candidate_acquisition_source import CandidateAcquisitionSource
    from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes

    if (
        type(prior) is not ResolvedAcquisitionEvaluation
        or type(previous_source) is not CandidateAcquisitionSource
        or type(current_source) is not CandidateAcquisitionSource
        or type(prepared) is not CandidateSourceBasisValues
        or prepared.predicate_provenance != "recomputed"
        or prepared.reason_codes
        or prepared.inputs is None
        or prepared.prospective_model is None
    ):
        raise ValueError("candidate_experiment_input_comparison_not_established")
    fields = (
        "tenant_id",
        "cell_id",
        "run_id",
        "route_id",
        "target_slot_id",
        "country_code",
        "year",
        "population",
        "denominator",
        "quantity_kind",
        "canonical_unit",
    )
    if any(getattr(previous_source, name) != getattr(current_source, name) for name in fields):
        raise ValueError("candidate_experiment_input_scope_changed")
    slot = current_source.target_slot_id
    if prepared.inputs.slot_binding.target_slot_id != slot:
        raise ValueError("candidate_experiment_input_slot_mismatch")
    old_values = prior.input_record.n5.baseline_state
    new_values = prepared.prospective_model.n5_config.baseline_state
    if slot not in old_values or slot not in new_values:
        raise ValueError("candidate_experiment_input_slot_missing")
    old_ncm = prepare_ncm_spec_selected_values(
        candidate_ncm_spec_from_declaration(prior.handoff.model_declaration)
    ).value_bytes
    new_ncm = prepare_ncm_spec_selected_values(prepared.prospective_model.ncm_spec).value_bytes
    return (
        exact_n5_content_bytes(old_values[slot]) != exact_n5_content_bytes(new_values[slot])
        or exact_n5_content_bytes(prior.input_record.n5)
        != exact_n5_content_bytes(prepared.prospective_model.n5_config)
        or exact_n5_content_bytes(prior.input_record.profile.rule)
        != exact_n5_content_bytes(prepared.prospective_model.rule)
        or old_ncm != new_ncm
    )


def _selected_n5_world_model_matches_exact_n4_context(
    *,
    selected_world_model_hash: str,
    n4_source_world_model_hash: str,
    context_world_model_hash: str,
    context_world_model_record_hash: str,
    n5_input_world_model_hash: str,
    n5_execution_world_model_hash: str,
) -> bool:
    """Bind selected N5 to the exact selected N4 source and context world."""
    return (
        selected_world_model_hash
        == n4_source_world_model_hash
        == context_world_model_hash
        == context_world_model_record_hash
        == n5_input_world_model_hash
        == n5_execution_world_model_hash
    )


def _selected_json(store: artifacts.ArtifactStore, ref: artifacts.ArtifactRef, kind: str) -> object:
    if (
        ref.kind != kind
        or ref.media_type != "application/json"
        or ref.manifest_profile_sha256 is None
        or artifacts.profile_bound_ref(store, ref) != ref
        or not store.verify(ref).ok
    ):
        raise ValueError("candidate_source_basis_selected_view_unverified")
    return artifacts.load_core_json_artifact(store, ref)


def _selected_data_snapshot(
    store: artifacts.ArtifactStore, ref: artifacts.ArtifactRef
) -> DataSnapshot:
    """Validate the exact selected snapshot through its Core JSON owner."""
    if (
        ref.kind != "fabric.data_snapshot"
        or ref.media_type != "application/json"
        or ref.manifest_profile_sha256 is None
        or artifacts.profile_bound_ref(store, ref) != ref
        or not store.verify(ref).ok
    ):
        raise ValueError("candidate_source_basis_selected_view_unverified")
    return artifacts.validate_core_model_json_artifact(DataSnapshot, store, ref)


def _same_view(
    store: artifacts.ArtifactStore, left: artifacts.ArtifactRef, right: artifacts.ArtifactRef
) -> bool:
    return artifacts.artifact_ref_identity_key(
        artifacts.profile_bound_ref(store, left)
    ) == artifacts.artifact_ref_identity_key(artifacts.profile_bound_ref(store, right))


def _source_values(
    store: artifacts.ArtifactStore, source: CandidateAcquisitionSource
) -> dict[str, object]:
    import polisyos.fabric.connectors as connectors
    from polisyos.data_forge.read_api import catalog
    from polisyos.runtime.quality.candidate_acquisition_source import _selected_compiler_candidate

    _, _, query, discovery, candidate = _selected_compiler_candidate(
        store,
        binding=source.requirement_basis_binding,
        compiler_report_ref=source.compiler_report_ref,
        requirement_id=source.requirement_id,
        candidate_digest=source.candidate_digest,
    )
    proof = source.live_source_execution
    if proof.schema_version != "polisyos.data_forge.live_source_execution_evidence.v2":
        raise ValueError("candidate_source_basis_execution_profile_not_established")
    # The source owner has already replayed raw -> normalized -> canonical and
    # verified the entire technical custody envelope. Decode through that same
    # connector owner. Keep ALL raw JSON metadata: unknown time, sampling, or
    # replication fields must not disappear merely because WDI's eight-column
    # numerical projection does not consume them.
    raw_values = json.loads(catalog.read_selected_live_raw_source(store, source.raw_source_ref))
    result = connectors.ResultSerializer.deserialize(store.get_bytes(source.normalized_source_ref))
    normalized_values = json.loads(catalog.normalized_acquisition_source_body(result))
    normalized_metadata = result.model_dump(
        mode="json",
        exclude={
            "data",
            "version",
            "fetched_at",
            "fetch_duration_ms",
            "bytes_transferred",
            "evidence_ref",
            "pii_scan",
        },
    )
    # DataVersion.timestamp is explicitly the time this version was recorded;
    # source_updated_at, raw release dates and version strategy/value survive.
    normalized_metadata["version"] = result.version.model_dump(mode="json", exclude={"timestamp"})
    normalized_metadata["pii_scan"] = (
        result.pii_scan.model_dump(mode="json", exclude={"scan_duration_ms"})
        if result.pii_scan is not None
        else None
    )
    source_values = source.model_dump(
        mode="json",
        exclude={
            "run_id",
            "job_id",
            "route_id",
            "requirement_basis_binding",
            "compiler_report_ref",
            "requirement_id",
            "candidate_digest",
            "resolved_source",
            "live_source_execution",
            "request_projection",
            "raw_source_ref",
            "normalized_source_ref",
            "source_snapshot_ref",
            "source_evidence_ref",
        },
    )
    return {
        "source": source_values,
        "requirement_query": query.model_dump(mode="json", by_alias=True),
        "requirement_basis_resolution": source.requirement_basis_binding.resolution.model_dump(
            mode="json"
        ),
        "discovery": discovery.model_dump(mode="json"),
        "selected_descriptor": candidate.model_dump(mode="json", exclude={"content_digest"}),
        "resolved_catalog_owner": source.resolved_source.model_dump(mode="json"),
        "request": source.request_projection,
        "raw_wdi_values": raw_values,
        "normalized_values": normalized_values,
        "normalized_metadata": normalized_metadata,
        "ingestion_provenance": _source_ingestion_values(store, source, result),
        "scientific_authority": {
            "observation_class": source.observation_class.value,
            "source_currentness": "not_established",
            "measurement_validity": "not_established",
            "independence": "not_established",
            "sample_denominator_evidence": "not_established",
            "publication_authority": False,
        },
    }


def _source_ingestion_values(
    store: artifacts.ArtifactStore,
    source: CandidateAcquisitionSource,
    result: FetchResult[Any],
) -> dict[str, object]:
    """Resolve full evidence/graph values, normalizing only verified writer clocks."""
    from polisyos.core.contracts import ProvenanceCoreRef
    from polisyos.fabric.ingestion import (
        build_connector_provenance_graph as _build_connector_provenance_graph,
    )
    from polisyos.fabric.ingestion import (
        canonicalize_ingestion_scalar as _canon_scalar,
    )
    from polisyos.fabric.ingestion import (
        load_provenance_graph,
        load_source_evidence_bundle,
        verify_live_ingestion_evidence_profile,
    )

    snapshot = _selected_data_snapshot(store, source.source_snapshot_ref)
    bundle, _manifest = load_source_evidence_bundle(
        store, source.source_evidence_ref, require_selected_profile=True
    )
    verify_live_ingestion_evidence_profile(store, source.source_evidence_ref, bundle)
    if bundle.transforms or bundle.execution_context is not None or bundle.provenance_ref is None:
        raise ValueError("candidate_source_basis_ingestion_transform_or_session_not_established")
    if snapshot.source_lineage is not None or any(
        getattr(snapshot, name) is not None
        for name in (
            "data_schema_ref",
            "uncertainty_ref",
            "uncertainty_envelope_ref",
            "warnings_ref",
            "input_bindings_ref",
        )
    ):
        raise ValueError("candidate_source_basis_ingestion_auxiliary_values_not_established")
    graph = load_provenance_graph(
        store,
        ProvenanceCoreRef.from_dict(bundle.provenance_ref.model_dump(mode="json")),
        require_selected_profile=True,
    )
    activity = graph.activities.get("connector_ingestion_run")
    dataset_id = source.resolved_source.registration.request_dataset_id
    dataset = graph.entities.get(f"dataset.worldbank.wdi.{dataset_id}")
    if activity is None or dataset is None or activity.ended_at is None:
        raise ValueError("candidate_source_basis_ingestion_recipe_not_established")
    attributes = dataset.attributes
    expected_attributes = {
        "fetch_status": "complete",
        "row_count": result.row_count,
        "completeness": _canon_scalar(result.completeness),
        "schema_id": result.schema_id,
        "schema_version": result.schema_version,
        "version_strategy": result.version.strategy.value,
        "version_value": result.version.value,
        "source_updated_at": result.source_updated_at.isoformat()
        if result.source_updated_at
        else None,
        "fetch_duration_ms": _canon_scalar(result.fetch_duration_ms),
        "data_artifact_id": source.normalized_source_ref.artifact_id.hex,
    }
    if any(attributes.get(name) != value for name, value in expected_attributes.items()):
        raise ValueError("candidate_source_basis_ingestion_result_relation_mismatch")
    # The owner constructor is deliberately the recipe denominator. Extra
    # agents, scientific transform nodes or metadata cannot be stripped into a
    # known profile: if that recipe cannot reproduce them, preparation is NE.
    dataset_values = {
        **attributes,
        "connector_id": "worldbank.wdi",
        "dataset_id": dataset_id,
        "fetched_at": result.fetched_at.isoformat(),
        "quality_flags": sorted(str(flag) for flag in result.quality_flags),
    }
    kwargs = {
        "source": source.request_projection["variable_id"],
        "license_name": source.resolved_source.license_id,
        "manifest_hash": activity.parameters.get("manifest_hash"),
    }
    kwargs["source"] = f"acquisition:{kwargs['source']}"
    expected = _build_connector_provenance_graph(
        datasets=[dataset_values],
        started_at=activity.started_at,
        ended_at=activity.ended_at,
        **kwargs,
    )
    if expected.to_dict() != graph.to_dict():
        raise ValueError("candidate_source_basis_ingestion_recipe_not_established")
    occurrence_time = datetime(2000, 1, 1, tzinfo=UTC)
    projected = _build_connector_provenance_graph(
        datasets=[
            {
                **dataset_values,
                "fetched_at": occurrence_time.isoformat(),
                "fetch_duration_ms": 0.0,
                "data_artifact_id": "owner-occurrence:normalized-result",
            }
        ],
        started_at=occurrence_time,
        ended_at=occurrence_time,
        **kwargs,
    ).to_dict()
    projected.pop("stable_id")
    summary_values = None
    if snapshot.quality_report_ref is not None:
        summary = RetrievalSummary.model_validate(
            _selected_json(store, snapshot.quality_report_ref, "fabric.retrieval_summary")
        )
        if summary.source_refs != [source.normalized_source_ref]:
            raise ValueError("candidate_source_basis_ingestion_summary_relation_mismatch")
        summary_values = summary.model_dump(mode="json", exclude={"source_refs"})
    return {
        "snapshot": snapshot.model_dump(
            mode="json", exclude={"data_ref", "evidence_ref", "quality_report_ref"}
        ),
        "evidence": bundle.model_dump(mode="json", exclude={"sources", "provenance_ref"}),
        "provenance": projected,
        "retrieval_summary": summary_values,
    }


def _data_values(
    *,
    payload: dict[str, object],
    base: DataSnapshot,
    inputs: CandidateSourceBasisInputs,
    canonical_base_ref: artifacts.ArtifactRef,
) -> dict[str, object]:
    # Round-trip into independent JSON values before touching only the exact
    # compartments constructed by _candidate_acquisition_snapshot_values.
    effective = json.loads(json.dumps(payload, allow_nan=False))
    selected = effective["acquisition"]["selected"]
    selected.pop("candidate_source_ref")
    selected.pop("candidate_digest")
    marker = effective["_policyos_candidate_acquisition"]
    marker.pop("candidate_source_ref")
    marker["base_data_snapshot_ref"] = canonical_base_ref.model_dump(mode="json")
    marker["slot_binding"].pop("candidate_digest")
    marker["materialized_at_transaction_time"] = "owner-occurrence:transaction-time"
    return {
        "payload_values": effective,
        "base_snapshot": base.model_dump(mode="json"),
        "binding": inputs.slot_binding.model_dump(mode="json", exclude={"candidate_digest"}),
    }


def _binding_values(
    *,
    payload: dict[str, object],
    data_values: dict[str, object],
    state_values: tuple[dict[str, object], ...],
    inputs: CandidateSourceBasisInputs,
    canonical_base_ref: artifacts.ArtifactRef,
    actual_binding_path: str | None = None,
) -> dict[str, object]:
    from polisyos.data_forge import read_api
    from polisyos.runtime.quality.data_state_substrate import (
        _DATA_FORGE_SNAPSHOT_PIPELINE,
        _candidate_acquisition_binding_semantics,
        _cas_data_forge_ref,
        _data_forge_payload_file_bytes,
        _data_forge_snapshot_manifest_extra,
    )

    payload_hash = (
        "sha256:"
        + hashlib.sha256(
            canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False))
        ).hexdigest()
    )
    lineage_refs = (
        _cas_data_forge_ref(inputs.base_data_snapshot_ref),
        _cas_data_forge_ref(inputs.candidate_source_ref),
        f"cas://sha256/{str(payload_hash).removeprefix('sha256:')}",
    )
    corpus_id, claim_requirement_bindings = _candidate_acquisition_binding_semantics(
        payload, inputs.slot_binding.canonical_variable_id
    )
    extra = _data_forge_snapshot_manifest_extra(
        corpus_id=corpus_id,
        builder_revision=(
            "polisyos.runtime.quality.data_state_substrate."
            "materialize_candidate_acquisition_snapshot"
        ),
        lineage_refs=lineage_refs,
        claim_requirement_bindings=claim_requirement_bindings,
        payload_content_hash=str(payload_hash),
    )
    artifact_meaning = {"candidate_source_data": data_values, "consumed_state": state_values}
    lineage_meanings = (
        canonical_base_ref.model_dump(mode="json"),
        "resolved_candidate_source_values",
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
        if canon.to_canonical_bytes(
            read_api.read_manifest(artifact_path), canon.CanonSpec(forbid_floats=False)
        ) != canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False)):
            raise ValueError("candidate_source_basis_publisher_payload_mismatch")
    manifest = read_api.prepare_publish_manifest(
        pipeline=_DATA_FORGE_SNAPSHOT_PIPELINE,
        artifacts=(artifact_path,),
        captured_artifact_bytes={artifact_path: content},
        extra=extra,
        published_at=inputs.transaction_time.astimezone(UTC).isoformat(),
    )
    kwargs = {
        "pipeline": _DATA_FORGE_SNAPSHOT_PIPELINE,
        "artifact_contents": (content,),
        "artifact_meanings": (artifact_meaning,),
        "expected_lineage_refs": lineage_refs,
        "lineage_meanings": lineage_meanings,
    }
    if actual_binding_path is not None:
        return read_api.read_snapshot_binding_meaning(
            binding_path=actual_binding_path, expected_manifest=manifest, **kwargs
        )
    return read_api.prepare_snapshot_binding_meaning(manifest=manifest, **kwargs)


def _effective_rule(
    rule: FoundryInputBindingRule, inputs: CandidateSourceBasisInputs
) -> dict[str, object]:
    values = rule.model_dump(mode="json")
    # Only generated report selectors are replaced. Scientific/limitation notes
    # and every field of all retained rules remain intact.
    occurrence_notes = {
        f"profile_selection_ref:{inputs.slot_binding.profile_selection_ref}",
        f"candidate_digest:{inputs.slot_binding.candidate_digest}",
        f"candidate_source_ref:{inputs.candidate_source_ref.artifact_id}",
    }
    values["notes"] = [note for note in rule.notes if note not in occurrence_notes]
    return values


def _verify_actual_world(
    *,
    store: artifacts.ArtifactStore,
    inputs: CandidateSourceBasisInputs,
    world_model_ref: artifacts.ArtifactRef,
    data_snapshot_ref: artifacts.ArtifactRef,
    payload: dict[str, object],
    plan: AcquiredObservationWorldPreparation,
    prospective: InputBindingValuesPreparation,
    limitations: WorldModelLimitations,
) -> WorldModelRecord:
    from polisyos.foundry.data_plane import load_input_bindings, prepare_input_bindings
    from polisyos.foundry.execute import load_state_snapshot, state_snapshot_value_projection
    from polisyos.runtime.quality.data_snapshot_lineage import validate_data_snapshot_owner_lineage
    from polisyos.runtime.quality.data_state_substrate import _verify_actual_acquired_native_world
    from polisyos.runtime.quality.world_model_record import (
        _prepare_world_simulation_model_ref,
        load_world_model_record,
        read_world_model_record_owner_values,
        world_model_artifact_views,
    )

    _selected_json(store, world_model_ref, "runtime.quality.world_model_record")
    world = load_world_model_record(store, world_model_ref)
    views = world_model_artifact_views(world)
    snapshot = _selected_data_snapshot(store, data_snapshot_ref)
    owner = read_world_model_record_owner_values(
        store,
        world_model_record=world,
        registry_bundle_ref=views.registry_bundle_ref,
        substrate_registry=inputs.configured_profile.context_inputs.substrate_registry,
    )
    lineage = validate_data_snapshot_owner_lineage(
        store,
        data_snapshot_ref,
        snapshot,
        candidate_only=True,
        binding_lineage_refs=owner.data_forge_binding.lineage_refs,
    )
    if (
        not isinstance(snapshot.source_lineage, CandidateAcquisitionSourceDataSnapshotLineage)
        or snapshot.source_lineage.base_data_snapshot_ref != inputs.base_data_snapshot_ref
        or snapshot.source_lineage.candidate_source_ref != inputs.candidate_source_ref
        or artifacts.load_core_json_artifact(store, snapshot.data_ref) != payload
        or views.data_snapshot_ref != data_snapshot_ref
    ):
        raise ValueError("candidate_source_basis_actual_snapshot_mismatch")
    bindings = load_input_bindings(store, views.input_bindings_ref)
    if bindings.schema_version == "1.4":
        raise ValueError("candidate_source_basis_unconsumed_method_inputs")
    if (
        any(
            not _same_view(store, getattr(bindings, name), getattr(views, name))
            for name in ("data_snapshot_ref", "registry_bundle_ref", "bound_state_snapshot_ref")
        )
        or tuple(bindings.rules) != prospective.effective_rules
    ):
        raise ValueError("candidate_source_basis_actual_binding_mismatch")
    replay = prepare_input_bindings(
        store,
        data_snapshot_ref=views.data_snapshot_ref,
        registry_bundle_ref=views.registry_bundle_ref,
        rules=list(bindings.rules),
        registered_sql_admission_ref=bindings.registered_sql_admission_ref,
        resolved_binding_manifest_ref=bindings.resolved_binding_manifest_ref,
    )
    actual_state = load_state_snapshot(store, snapshot_ref=views.bound_state_snapshot_ref)
    for current in (replay, prospective):
        if (
            current.effective_rules != tuple(bindings.rules)
            or current.applied_binding_ids != replay.applied_binding_ids
            or current.warnings != replay.warnings
            or state_snapshot_value_projection(current.materialized_state)
            != state_snapshot_value_projection(actual_state)
        ):
            raise ValueError("candidate_source_basis_actual_state_mismatch")
    base = inputs.configured_profile.context_inputs.world_model_record
    base_views = world_model_artifact_views(base)
    expected_model = plan.materialized_model(data_snapshot_ref)
    expected_simulation = _prepare_world_simulation_model_ref(
        model_spec=expected_model,
        model_spec_ref=views.model_spec_ref,
        registry_bundle_ref=base_views.registry_bundle_ref,
        mechanism_refs=base.simulation_model_ref.mechanism_refs,
        gcm_refs=base.simulation_model_ref.gcm_refs,
        ncm_refs=base.simulation_model_ref.ncm_refs,
        program_graph_refs=base.simulation_model_ref.program_graph_refs,
    )
    changed = {
        "schema_version",
        "world_model_record_id",
        "content_hash",
        "created_at",
        "producer_ref",
        "authority_status",
        "valid_time_scope",
        "tx_time_scope",
        "fabric_world_ref",
        "data_forge_binding_ref",
        "simulation_model_ref",
        "foundry_binding_ref",
        "limitations",
        "artifact_views",
        "substrate_registry_ref",
    }
    tx = inputs.transaction_time.astimezone(UTC).isoformat()
    if (
        world.model_dump(mode="json", exclude=changed)
        != base.model_dump(mode="json", exclude=changed)
        or world.producer_ref != _PRODUCER
        or world.authority_status != "limited"
        or world.valid_time_scope != "not_established"
        or world.tx_time_scope != tx
        or owner.model_spec != expected_model
        or world.simulation_model_ref != expected_simulation
        or views.registry_bundle_ref != base_views.registry_bundle_ref
        or views.ncm_refs != base_views.ncm_refs
        or views.program_graph_refs != base_views.program_graph_refs
        or world.fabric_world_ref.snapshot_id != snapshot.stats.get("snapshot_id")
        or world.fabric_world_ref.as_of_valid_time != base.fabric_world_ref.as_of_valid_time
        or world.fabric_world_ref.world_query_policy != base.fabric_world_ref.world_query_policy
        or world.substrate_registry_ref.model_dump(exclude={"registry_artifact_ref"})
        != base.substrate_registry_ref.model_dump(exclude={"registry_artifact_ref"})
        or world.limitations != limitations
        or not set(lineage.required_admissibility_blockers).issubset(
            world.limitations.admissibility_blockers
        )
    ):
        raise ValueError("candidate_source_basis_actual_world_recipe_mismatch")
    _verify_actual_acquired_native_world(world, str(snapshot.data_ref.artifact_id), tx)
    return world


def _prepare_candidate_source_basis_step(
    *,
    store: artifacts.ArtifactStore,
    problem: DesignProblem,
    inputs: CandidateSourceBasisInputs,
    data_snapshot_ref: artifacts.ArtifactRef | None = None,
    world_model_ref: artifacts.ArtifactRef | None = None,
    previous: CandidateSourceBasisValues | None = None,
) -> CandidateSourceBasisValues:
    """Replay one candidate producer step, optionally after a verified step."""
    from polisyos.foundry.data_plane import load_input_bindings, prepare_json_input_binding_values
    from polisyos.foundry.execute import state_snapshot_value_projection
    from polisyos.ir import prepare_ncm_spec_selected_values
    from polisyos.runtime.quality.candidate_acquisition_source import (
        read_candidate_acquisition_source,
    )
    from polisyos.runtime.quality.candidate_simulation import prepare_candidate_n5_request_values
    from polisyos.runtime.quality.cycle_substrate import (
        ConfiguredCandidateSimulationContextAdmissionOwner,
    )
    from polisyos.runtime.quality.data_snapshot_lineage import (
        ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION,
        _candidate_source_limitations_for_payload_schema,
        validate_data_snapshot_owner_lineage,
    )
    from polisyos.runtime.quality.data_state_substrate import (
        _acquired_fabric_meaning,
        _acquired_model_dependency_values,
        _acquired_world_meaning,
        _candidate_acquisition_snapshot_values,
        _prepare_acquired_observation_world,
        _require_candidate_acquisition_world_scope,
    )
    from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes
    from polisyos.runtime.quality.world_model_record import (
        load_world_model_record,
        read_world_model_record_owner_values,
        world_model_artifact_views,
    )

    effective: dict[str, object] = {}
    try:
        if type(inputs) is not CandidateSourceBasisInputs:
            raise TypeError("candidate_source_basis_inputs_untyped")
        inputs = CandidateSourceBasisInputs.model_validate(inputs.model_dump(mode="python"))
        if (data_snapshot_ref is None) != (world_model_ref is None):
            raise ValueError("candidate_source_basis_actual_pair_incomplete")
        source = read_candidate_acquisition_source(store, source_ref=inputs.candidate_source_ref)
        configured = inputs.configured_profile
        base = configured.context_inputs.world_model_record
        if inputs.base_world_model_ref is not None:
            _selected_json(store, inputs.base_world_model_ref, "runtime.quality.world_model_record")
            selected_base = load_world_model_record(store, inputs.base_world_model_ref)
            if exact_n5_content_bytes(selected_base) != exact_n5_content_bytes(base):
                raise ValueError("candidate_source_basis_selected_base_world_mismatch")
        if previous is not None and (
            previous.predicate_provenance != "recomputed"
            or previous.inputs is None
            or previous.produced_data_snapshot_ref is None
            or previous.produced_world_model_ref is None
            or previous.canonical_base_data_snapshot_ref is None
            or inputs.base_world_model_ref is None
            or not _same_view(store, inputs.base_world_model_ref, previous.produced_world_model_ref)
            or not _same_view(
                store, inputs.base_data_snapshot_ref, previous.produced_data_snapshot_ref
            )
        ):
            raise ValueError("candidate_source_basis_predecessor_selection_mismatch")
        views = world_model_artifact_views(base)
        if load_input_bindings(store, views.input_bindings_ref).schema_version == "1.4":
            raise ValueError("candidate_source_basis_unconsumed_method_inputs")
        if inputs.base_data_snapshot_ref != views.data_snapshot_ref:
            raise ValueError("candidate_source_basis_base_selection_mismatch")
        _require_candidate_acquisition_world_scope(
            problem=problem, base=base, binding=inputs.slot_binding, source=source
        )
        base_snapshot = _selected_data_snapshot(store, inputs.base_data_snapshot_ref)
        base_lineage = validate_data_snapshot_owner_lineage(
            store, inputs.base_data_snapshot_ref, base_snapshot, candidate_only=True
        )
        base_owner = read_world_model_record_owner_values(
            store,
            world_model_record=base,
            registry_bundle_ref=views.registry_bundle_ref,
            substrate_registry=configured.context_inputs.substrate_registry,
        )
        payload, _stats, _notes, rule = _candidate_acquisition_snapshot_values(
            store,
            base_data_snapshot_ref=inputs.base_data_snapshot_ref,
            candidate_source_ref=inputs.candidate_source_ref,
            slot_binding=inputs.slot_binding,
            transaction_time=inputs.transaction_time,
        )
        plan = _prepare_acquired_observation_world(
            store,
            base_world_model_record=base,
            acquired_rule=rule,
            registry_bundle_ref=views.registry_bundle_ref,
            substrate_registry=base_owner.substrate_registry,
        )
        payload_json = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        prospective = prepare_json_input_binding_values(
            store,
            payload_json=payload_json,
            registry_bundle_ref=views.registry_bundle_ref,
            rules=list(plan.rules),
        )
        model_owner = ConfiguredCandidateSimulationContextAdmissionOwner(
            profiles=(configured,),
            model_declarations=(inputs.original_model_declaration,),
            store=store,
        )
        model = model_owner.prepare_model_values_for_acquired_state(
            problem=problem,
            profile_selection_ref=inputs.slot_binding.profile_selection_ref,
            source_world_model=base,
            state=prospective.materialized_state,
        )
        source_values = _source_values(store, source)
        same_previous = (
            previous is not None
            and previous.inputs is not None
            and exact_n5_content_bytes(previous.effective_values["candidate_source"])
            == exact_n5_content_bytes(source_values)
            and previous.inputs.slot_binding.model_dump(mode="json", exclude={"candidate_digest"})
            == inputs.slot_binding.model_dump(mode="json", exclude={"candidate_digest"})
        )
        canonical_base_ref = (
            previous.canonical_base_data_snapshot_ref
            if same_previous and previous is not None
            else inputs.base_data_snapshot_ref
        )
        if canonical_base_ref is None:  # pragma: no cover - checked above
            raise ValueError("candidate_source_basis_predecessor_base_missing")
        canonical_base = (
            _selected_data_snapshot(store, canonical_base_ref) if same_previous else base_snapshot
        )
        data_values = _data_values(
            payload=payload,
            base=canonical_base,
            inputs=inputs,
            canonical_base_ref=canonical_base_ref,
        )
        state_values = tuple(
            asdict(leaf) for leaf in state_snapshot_value_projection(prospective.materialized_state)
        )
        limitations = plan.limitations.model_copy(
            update={
                "admissibility_blockers": tuple(
                    dict.fromkeys(
                        (
                            *plan.limitations.admissibility_blockers,
                            ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION,
                            *_candidate_source_limitations_for_payload_schema(
                                payload["_policyos_candidate_acquisition"]["schema_version"]
                            ),
                            *source.limitations,
                            *base_lineage.required_admissibility_blockers,
                        )
                    )
                )
            }
        )
        actual = None
        if data_snapshot_ref is not None and world_model_ref is not None:
            actual = _verify_actual_world(
                store=store,
                inputs=inputs,
                world_model_ref=world_model_ref,
                data_snapshot_ref=data_snapshot_ref,
                payload=payload,
                plan=plan,
                prospective=prospective,
                limitations=limitations,
            )
        binding = _binding_values(
            payload=payload,
            data_values=data_values,
            state_values=state_values,
            inputs=inputs,
            canonical_base_ref=canonical_base_ref,
            actual_binding_path=actual.data_forge_binding_ref.binding_path
            if actual is not None
            else None,
        )
        model_values = json.loads(plan.model_values_json)
        if same_previous and previous is not None:
            owner_suffix = [
                "candidate_acquisition_world",
                "source_time_not_established",
                "causal_coupling_not_established",
            ]
            if model_values.get("notes") != [*base_owner.model_spec.notes, *owner_suffix]:
                raise ValueError("candidate_source_basis_model_note_recipe_mismatch")
            previous_world_values = previous.effective_values["world"]
            model_values["notes"] = previous_world_values["model_spec"]["notes"]
        world_values = _acquired_world_meaning(
            world=base,
            model_values=model_values,
            limitations=limitations,
            rules=plan.rules,
            state=prospective.materialized_state,
            registry_values=base_owner.registry_values,
            substrate_registry=base_owner.substrate_registry,
            data_values=data_values,
            fabric_values=_acquired_fabric_meaning(base),
            binding_values=binding,
        )
        world_values["inherited_world"]["producer_ref"] = _PRODUCER
        # The producer and its admissibility consumers compose blockers as a
        # set. Keep every blocker while ignoring only their generated order.
        limitation_values = world_values["inherited_world"]["limitations"]
        limitation_values["admissibility_blockers"] = sorted(
            set(limitation_values["admissibility_blockers"])
        )
        owned = tuple(item for item in plan.rules if item.target_slot_id == rule.target_slot_id)
        if owned != (rule,):
            raise ValueError("candidate_source_basis_owned_rule_mismatch")
        rule_values = tuple(
            _effective_rule(item, inputs) if item == rule else item.model_dump(mode="json")
            for item in plan.rules
        )
        world_values["rules"] = rule_values
        world_values["model_dependencies"] = _acquired_model_dependency_values(store, base)
        world_values["binding_execution"] = {
            "applied_binding_ids": prospective.applied_binding_ids,
            "warnings": prospective.warnings,
        }
        declaration_values = model.original_declaration.model_dump(
            mode="python", exclude={"profile_config_ref", "profile_content_hash", "content_hash"}
        )
        declaration_values.update(
            {
                item.name: getattr(model.declared_model_values, item.name)
                for item in fields(model.declared_model_values)
            }
        )
        effective = {
            "candidate_source": source_values,
            "world": world_values,
            "foundry_state": state_snapshot_value_projection(prospective.materialized_state),
            "applied_rules": rule_values,
            "selected_native_ncm": prepare_ncm_spec_selected_values(model.ncm_spec).value_bytes,
            "n5_request_values": prepare_candidate_n5_request_values(model.n5_config),
            "declared_model": declaration_values,
            "context_inputs": configured.context_inputs.model_dump(
                mode="python", exclude={"world_model_record"}
            ),
            "profile_schema": configured.schema_version,
            "profile_purpose": configured.purpose,
            "profile_limitations": configured.limitations,
        }
        exact_n5_content_bytes(effective)
        return CandidateSourceBasisValues(
            "recomputed",
            (),
            inputs,
            effective,
            prospective,
            model,
            payload_json,
            rule,
            data_snapshot_ref,
            world_model_ref,
            canonical_base_ref,
        )
    except (OSError, RuntimeError, TypeError, ValueError, KeyError, AttributeError) as exc:
        code = str(getattr(exc, "code", None) or exc)
        return CandidateSourceBasisValues(
            "not_established",
            (code,),
            inputs if type(inputs) is CandidateSourceBasisInputs else None,
            effective,
        )


def prepare_candidate_source_basis_values(
    *,
    store: artifacts.ArtifactStore,
    problem: DesignProblem,
    inputs: CandidateSourceBasisInputs,
    data_snapshot_ref: artifacts.ArtifactRef | None = None,
    world_model_ref: artifacts.ArtifactRef | None = None,
    predecessors: tuple[CandidateSourceBasisPredecessor, ...] = (),
) -> CandidateSourceBasisValues:
    """Recompute candidate inputs, replaying any selected predecessor chain.

    Every predecessor is independently replayed through the actual snapshot,
    world, binding, source and model owners before its selected output can be
    used as the next base. Only a consecutive, semantically identical source
    step can reuse that verified step's occurrence-normalized base. The caller
    remains responsible for establishing route, action and N5 ownership.
    Unsupported or foreign predecessor views produce typed not-established.
    """
    if type(predecessors) is not tuple or len(predecessors) > 128:
        return CandidateSourceBasisValues(
            "not_established", ("candidate_source_basis_predecessor_chain_unavailable",)
        )
    previous: CandidateSourceBasisValues | None = None
    seen: set[tuple[str, str, str, str | None]] = set()
    for item in predecessors:
        if (
            type(item) is not CandidateSourceBasisPredecessor
            or type(item.inputs) is not CandidateSourceBasisInputs
            or not isinstance(item.data_snapshot_ref, artifacts.ArtifactRef)
            or not isinstance(item.world_model_ref, artifacts.ArtifactRef)
        ):
            return CandidateSourceBasisValues(
                "not_established", ("candidate_source_basis_predecessor_untyped",)
            )
        identity = artifacts.artifact_ref_identity_key(item.world_model_ref)
        if identity in seen:
            return CandidateSourceBasisValues(
                "not_established", ("candidate_source_basis_predecessor_cycle",)
            )
        seen.add(identity)
        previous = _prepare_candidate_source_basis_step(
            store=store,
            problem=problem,
            inputs=item.inputs,
            data_snapshot_ref=item.data_snapshot_ref,
            world_model_ref=item.world_model_ref,
            previous=previous,
        )
        if previous.predicate_provenance != "recomputed":
            return previous
    return _prepare_candidate_source_basis_step(
        store=store,
        problem=problem,
        inputs=inputs,
        data_snapshot_ref=data_snapshot_ref,
        world_model_ref=world_model_ref,
        previous=previous,
    )


def prepare_candidate_source_numerical_basis_values_v2(
    *,
    store: artifacts.ArtifactStore,
    problem: DesignProblem,
    inputs: CandidateSourceBasisInputs,
    data_snapshot_ref: artifacts.ArtifactRef | None = None,
    world_model_ref: artifacts.ArtifactRef | None = None,
    predecessors: tuple[CandidateSourceBasisPredecessor, ...] = (),
) -> CandidateSourceBasisValues:
    """Replay the owner chain and project only the declared numerical facets.

    This candidate-only quantity is not a permission or occurrence check. The
    caller must still verify current rights, semantic bindings and selected
    evidence on every use. The complete v1 projection remains unchanged.
    """
    from dataclasses import replace

    from polisyos.runtime.quality.acquisition_evaluation import _foundry_binding_numerical_values
    from polisyos.runtime.quality.candidate_simulation import (
        prepare_candidate_n5_request_projection_v2,
    )
    from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes

    prepared = prepare_candidate_source_basis_values(
        store=store,
        problem=problem,
        inputs=inputs,
        data_snapshot_ref=data_snapshot_ref,
        world_model_ref=world_model_ref,
        predecessors=predecessors,
    )
    if prepared.predicate_provenance != "recomputed" or prepared.prospective_model is None:
        return prepared
    try:
        values = {
            name: prepared.effective_values[name]
            for name in ("foundry_state", "applied_rules", "selected_native_ncm", "declared_model")
        }
        rules = values["applied_rules"]
        if not isinstance(rules, tuple):
            raise ValueError("acquisition_numerical_rule_census_not_established")
        values["applied_rules"] = tuple(_foundry_binding_numerical_values(rule) for rule in rules)
        values["n5_request_values"] = prepare_candidate_n5_request_projection_v2(
            prepared.prospective_model.n5_config
        ).numerical
        exact_n5_content_bytes(values)
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        return replace(
            prepared,
            predicate_provenance="not_established",
            reason_codes=(str(getattr(exc, "code", None) or exc),),
            effective_values={},
        )
    return replace(prepared, effective_values=values)


def _candidate_source_predecessors_from_selected_transitions(
    *,
    store: artifacts.ArtifactStore,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    source_job_id: str,
    route_id: str,
    transitions: tuple[CandidateSourceReentryReceipt, ...],
) -> tuple[CandidateSourceBasisPredecessor, ...]:
    """Reopen the exact selected producer artifacts of an already verified prefix."""
    from polisyos.runtime.quality.acquisition_world_growth import (
        CandidateAcquisitionWorldCheckpoint,
        CandidateAcquisitionWorldIntent,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        CandidateAcquisitionActionReceipt,
    )
    from polisyos.runtime.quality.data_state_substrate import CandidateAcquisitionSourceSlotBinding
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views

    rows: list[CandidateSourceBasisPredecessor] = []
    preceding_world_ref: artifacts.ArtifactRef | None = None
    for receipt in transitions:
        action = CandidateAcquisitionActionReceipt.model_validate(
            _selected_json(
                store,
                receipt.candidate_action_ref,
                "runtime_quality.acquisition_candidate_action_receipt",
            )
        )
        intent = CandidateAcquisitionWorldIntent.model_validate(
            _selected_json(
                store,
                receipt.candidate_world_intent_ref,
                "runtime_quality.acquisition_candidate_world_intent",
            )
        )
        checkpoint = CandidateAcquisitionWorldCheckpoint.model_validate(
            _selected_json(
                store,
                receipt.candidate_world_checkpoint_ref,
                "runtime_quality.acquisition_candidate_world_checkpoint",
            )
        )
        scope = (tenant_id, cell_id, run_id, route_id)
        if (
            any(
                (item.tenant_id, item.cell_id, item.run_id, item.route_id) != scope
                for item in (receipt, action, intent, checkpoint)
            )
            or receipt.source_job_id != source_job_id
            or action.source_job_id != source_job_id
            or action.action_job_id != receipt.action_job_id
            or action.action_generation != receipt.action_generation
            or intent.action_job_id != action.action_job_id
            or checkpoint.action_job_id != action.action_job_id
            or intent.action_phase_ref != action.action_phase_ref
            or checkpoint.action_phase_ref != action.action_phase_ref
            or intent.transaction_time != checkpoint.transaction_time
            or intent.configured_profile.profile_selection_ref != action.profile_selection_ref
            or not _same_view(store, intent.candidate_action_ref, receipt.candidate_action_ref)
            or not _same_view(store, checkpoint.candidate_action_ref, receipt.candidate_action_ref)
            or not _same_view(store, checkpoint.intent_ref, receipt.candidate_world_intent_ref)
            or not _same_view(store, action.candidate_source_ref, receipt.candidate_source_ref)
            or not _same_view(store, checkpoint.candidate_source_ref, receipt.candidate_source_ref)
            or not _same_view(store, checkpoint.data_snapshot_ref, receipt.data_snapshot_ref)
            or not _same_view(store, checkpoint.world_model_ref, receipt.world_model_ref)
            or not _same_view(
                store,
                checkpoint.base_data_snapshot_ref,
                world_model_artifact_views(
                    intent.configured_profile.context_inputs.world_model_record
                ).data_snapshot_ref,
            )
        ):
            raise ValueError("candidate_source_basis_prior_owner_binding_mismatch")
        rows.append(
            CandidateSourceBasisPredecessor(
                inputs=CandidateSourceBasisInputs(
                    configured_profile=intent.configured_profile,
                    original_model_declaration=intent.original_model_declaration,
                    base_data_snapshot_ref=checkpoint.base_data_snapshot_ref,
                    base_world_model_ref=preceding_world_ref,
                    candidate_source_ref=receipt.candidate_source_ref,
                    slot_binding=CandidateAcquisitionSourceSlotBinding(
                        profile_selection_ref=action.profile_selection_ref,
                        candidate_digest=action.candidate_digest,
                        canonical_variable_id=action.canonical_variable_id,
                        target_slot_id=action.target_slot_id,
                    ),
                    transaction_time=intent.transaction_time,
                ),
                data_snapshot_ref=receipt.data_snapshot_ref,
                world_model_ref=receipt.world_model_ref,
            )
        )
        preceding_world_ref = receipt.world_model_ref
    return tuple(rows)


def _candidate_source_predecessors_for_verified_closure(
    *, store: artifacts.ArtifactStore, closure: VerifiedAcquisitionRouteClosure
) -> tuple[CandidateSourceBasisPredecessor, ...]:
    """Reopen only an owner-verified route's actual candidate transitions.

    This adapter supplies replay inputs, not route, lease or N5 authority.
    """
    return _candidate_source_predecessors_from_selected_transitions(
        store=store,
        tenant_id=closure.tenant_id,
        cell_id=closure.cell_id,
        run_id=closure.run_id,
        source_job_id=closure.source_job_id,
        route_id=closure.route_id,
        transitions=closure.candidate_basis_transitions,
    )


def _candidate_source_predecessors_for_verified_experiment_origin(
    *,
    store: artifacts.ArtifactStore,
    origin: VerifiedCandidateExperimentOrigin,
    before_action_generation: int | None = None,
) -> tuple[CandidateSourceBasisPredecessor, ...]:
    """Replay real producer edges from a verified experiment prefix, excluding retention.

    The caller independently authenticates the complete experiment history.
    A selected older basis uses the prefix before its own action generation;
    cheap retained continuations never manufacture a world/source transaction.
    """
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceiptV2,
        VerifiedCandidateExperimentOrigin,
        _candidate_experiment_effective_source,
    )
    from polisyos.runtime.quality.generation_cycle import CandidateSourceReentryReceipt

    if type(origin) is not VerifiedCandidateExperimentOrigin:
        raise TypeError("candidate_source_basis_experiment_origin_untyped")
    # Reuse the canonical prefix/cycle projection; this does not authenticate
    # history or grant permission. Its caller already performed owner replay.
    _candidate_experiment_effective_source(origin)
    chain = origin.candidate_terminal_history_chain
    if before_action_generation is not None and (
        type(before_action_generation) is not int
        or before_action_generation < 1
        or before_action_generation > len(chain) + 1
    ):
        raise ValueError("candidate_source_basis_experiment_cut_invalid")
    cutoff = len(chain) if before_action_generation is None else before_action_generation - 1
    transitions: list[CandidateSourceReentryReceipt] = []
    scope = (origin.tenant_id, origin.cell_id, origin.run_id, origin.source_job_id, origin.route_id)
    for generation, history in enumerate(chain[:cutoff], start=1):
        receipt = history.reentry
        if receipt is None:
            if (
                history.terminal.terminal_outcome == "candidate_blocked"
                and history.decision is not None
                and history.decision.comparison_result == "not_established"
                and history.decision.predicate_provenance == "not_established"
                and history.terminal.blocker_ref is not None
                and history.terminal.blocker_reason
                == "candidate_experiment_input_change_not_established"
                and history.decision.reason_codes
                and "candidate_experiment_input_change_not_established"
                in history.decision.reason_codes
                and history.continuation is None
                and history.evaluation is None
                and history.frontier_before is None
                and history.frontier_after is None
            ):
                continue
            if type(history.terminal) is AcquisitionCandidateExperimentTerminalReceiptV2:
                # The owner replay above proves a V2 blocker retains the exact
                # predecessor frontier/source. It contributes no physical
                # producer edge and cannot become the selected numerical basis.
                if (
                    history.terminal.terminal_outcome == "candidate_blocked"
                    and history.budget_window is None
                    and history.reuse_occurrence is not None
                    and history.reuse_occurrence_ref is not None
                ):
                    continue
                if (
                    history.terminal.terminal_outcome == "candidate_evaluation_retained"
                    and history.continuation is not None
                    and history.budget_window is None
                    and history.reuse_occurrence is not None
                    and history.reuse_occurrence_ref is not None
                ):
                    continue
            if (
                history.terminal.terminal_outcome != "candidate_evaluation_retained"
                or history.continuation is None
            ):
                raise ValueError("candidate_source_basis_experiment_transition_missing")
            continue
        if (
            type(receipt) is not CandidateSourceReentryReceipt
            or history.terminal.terminal_outcome != "candidate_reentry_completed"
            or receipt.action_generation != generation
            or receipt.action_job_id != history.head.job_id
            or (
                receipt.tenant_id,
                receipt.cell_id,
                receipt.run_id,
                receipt.source_job_id,
                receipt.route_id,
            )
            != scope
            or not _same_view(
                store, history.terminal.candidate_action_ref, receipt.candidate_action_ref
            )
        ):
            raise ValueError("candidate_source_basis_experiment_transition_invalid")
        transitions.append(receipt)
    return _candidate_source_predecessors_from_selected_transitions(
        store=store,
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        run_id=origin.run_id,
        source_job_id=origin.source_job_id,
        route_id=origin.route_id,
        transitions=tuple(transitions),
    )


def _live_candidate_source_predecessors(
    *, bridge: AcquisitionWorldGrowthBridge, closure: VerifiedAcquisitionRouteClosure
) -> tuple[CandidateSourceBasisPredecessor, ...]:
    """Apply the same predecessor replay after the live action owner is checked."""
    return _candidate_source_predecessors_for_verified_closure(
        store=bridge.artifact_store, closure=closure
    )


def prepare_live_candidate_source_basis_values(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    closure: VerifiedAcquisitionRouteClosure,
    candidate_action_ref: artifacts.ArtifactRef,
    transaction_time: datetime,
) -> CandidateSourceBasisValues:
    """Use the real selected-action/live-source owners before pure preparation."""
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.runtime.quality.candidate_acquisition_source import (
        read_candidate_acquisition_source,
    )
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views

    try:
        if type(bridge) is not AcquisitionWorldGrowthBridge:
            raise TypeError("candidate_source_basis_live_bridge_untyped")
        receipt = bridge._require_selected_candidate_action(
            closure=closure, candidate_action_ref=candidate_action_ref
        )
        selection = bridge.candidate_source_selection(closure)
        if selection is None:
            raise ValueError("candidate_source_basis_configured_owner_unavailable")
        source = read_candidate_acquisition_source(
            bridge.artifact_store,
            source_ref=receipt.candidate_source_ref,
            authority=bridge.authority,
        )
        if (
            source.tenant_id != closure.tenant_id
            or source.cell_id != closure.cell_id
            or source.run_id != closure.run_id
            or source.job_id != receipt.action_job_id
            or source.route_id != closure.route_id
            or source.candidate_digest != selection.candidate_digest
            or receipt.profile_selection_ref != selection.profile_selection_ref
            or receipt.canonical_variable_id != selection.canonical_variable_id
            or receipt.target_slot_id != selection.target_slot_id
        ):
            raise ValueError("candidate_source_basis_live_source_scope_mismatch")
        profile, declaration, _owner = bridge._candidate_source_prior_owner(closure=closure)
        predecessors = _live_candidate_source_predecessors(bridge=bridge, closure=closure)
        inputs = CandidateSourceBasisInputs(
            configured_profile=profile,
            original_model_declaration=declaration,
            base_data_snapshot_ref=world_model_artifact_views(
                profile.context_inputs.world_model_record
            ).data_snapshot_ref,
            base_world_model_ref=(predecessors[-1].world_model_ref if predecessors else None),
            candidate_source_ref=receipt.candidate_source_ref,
            slot_binding=CandidateAcquisitionSourceSlotBinding(
                profile_selection_ref=selection.profile_selection_ref,
                candidate_digest=selection.candidate_digest,
                canonical_variable_id=selection.canonical_variable_id,
                target_slot_id=selection.target_slot_id,
            ),
            transaction_time=transaction_time,
        )
        result = prepare_candidate_source_basis_values(
            store=bridge.artifact_store,
            problem=closure.design_problem_basis,
            inputs=inputs,
            predecessors=predecessors,
        )
        # Numerical preparation can take time; the actual pending head and live
        # worker fence must still select this exact action when values return.
        if (
            bridge._require_selected_candidate_action(
                closure=closure, candidate_action_ref=candidate_action_ref
            )
            != receipt
        ):
            raise ValueError("candidate_source_basis_live_action_changed")
        fresh_profile, fresh_declaration, _fresh_owner = bridge._candidate_source_prior_owner(
            closure=closure
        )
        if fresh_profile != profile or fresh_declaration != declaration:
            raise ValueError("candidate_source_basis_live_prior_changed")
        return result
    except (OSError, RuntimeError, TypeError, ValueError, KeyError, AttributeError) as exc:
        return CandidateSourceBasisValues(
            "not_established", (str(getattr(exc, "code", None) or exc),)
        )


def prepare_live_candidate_experiment_source_basis_values(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
    candidate_action_ref: artifacts.ArtifactRef,
    pending_phase_ref: str,
    initial_reentry_context: _VerifiedCurrentCandidateExperimentReentryAction | None = None,
) -> tuple[
    CandidateSourceBasisValues,
    artifacts.ArtifactRef | None,
    CandidateAcquisitionWorldIntent | None,
]:
    """Prepare the actual selected source basis for a live experiment action.

    The current-phase/source owner verifies the complete experiment prefix.
    Only its real reentry transactions become predecessor inputs; a retained
    continuation contributes no new world. The original empty prefix remains
    unchanged and is never inferred from arbitrary world ancestry.
    """
    from polisyos.runtime.http.services.control.run_lifecycle import (
        VerifiedAcquisitionActionOutcome,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionActionHeadRecord,
        ControlJobExecutionAdmission,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
        VerifiedCandidateExperimentOrigin,
        _candidate_experiment_effective_source,
    )
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.runtime.quality.candidate_acquisition_action import (
        CandidateAcquisitionActionReceipt,
        _candidate_experiment_source_selection,
        _current_candidate_experiment_reentry_action,
        _current_candidate_experiment_reentry_action_context,
        _read_candidate_experiment_action_in_operation,
        _VerifiedCurrentCandidateExperimentReentryAction,
        read_candidate_experiment_acquisition_action,
    )
    from polisyos.runtime.quality.candidate_acquisition_source import (
        read_candidate_acquisition_source,
    )
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views

    if (
        type(bridge) is not AcquisitionWorldGrowthBridge
        or type(origin) is not VerifiedCandidateExperimentOrigin
    ):
        raise TypeError("candidate_experiment_source_basis_live_owner_untyped")
    try:
        reentry_context = initial_reentry_context
        if reentry_context is None:
            reentry_context = _current_candidate_experiment_reentry_action_context(
                bridge,
                origin,
                pending_phase_ref,
                candidate_action_ref,
            )
        if (
            type(reentry_context) is not _VerifiedCurrentCandidateExperimentReentryAction
            or type(reentry_context.head) is not AcquisitionActionHeadRecord
            or type(reentry_context.phase) is not AcquisitionCandidateExperimentPhaseReceipt
            or type(reentry_context.admission) is not ControlJobExecutionAdmission
            or type(reentry_context.action) is not CandidateAcquisitionActionReceipt
            or type(reentry_context.outcome) is not VerifiedAcquisitionActionOutcome
        ):
            raise ValueError("candidate_experiment_source_basis_reentry_context_untyped")
        expected_scope = (
            origin.tenant_id,
            origin.cell_id,
            origin.run_id,
            origin.source_job_id,
            origin.route_id,
            len(origin.candidate_terminal_history_chain) + 1,
        )
        head_scope = (
            reentry_context.head.tenant_id,
            reentry_context.head.cell_id,
            reentry_context.head.run_id,
            reentry_context.head.source_job_id,
            reentry_context.head.route_id,
            reentry_context.head.action_generation,
        )
        phase_scope = (
            reentry_context.phase.tenant_id,
            reentry_context.phase.cell_id,
            reentry_context.phase.run_id,
            reentry_context.phase.source_job_id,
            reentry_context.phase.route_id,
            reentry_context.phase.action_generation,
        )
        job = reentry_context.admission.job
        if (
            head_scope != expected_scope
            or phase_scope != expected_scope
            or reentry_context.head.receipt_ref != pending_phase_ref
            or reentry_context.head.receipt_phase != "candidate_input_reentry_pending"
            or reentry_context.head.receipt_manifest_profile_sha256 is None
            or reentry_context.phase.receipt_phase != "candidate_input_reentry_pending"
            or reentry_context.phase.job_id != reentry_context.head.job_id
            or reentry_context.phase.candidate_receipt_ref != candidate_action_ref
            or (
                reentry_context.phase.source_payload_ref,
                reentry_context.phase.capability_manifest_ref,
                reentry_context.phase.request_content_hash,
                reentry_context.phase.policy_scope,
                reentry_context.phase.policy_ref,
            )
            != (
                origin.source_payload_ref,
                origin.capability_manifest_ref,
                origin.request_content_hash,
                origin.policy_scope,
                origin.policy_ref,
            )
            or reentry_context.outcome.head != reentry_context.head
            or reentry_context.outcome.latest_receipt != reentry_context.phase
            or reentry_context.action.selection != reentry_context.selection
            or reentry_context.action.action_job_id != reentry_context.phase.job_id
            or reentry_context.action.action_generation != reentry_context.phase.action_generation
            or job.job_id != reentry_context.phase.job_id
            or job.kind != "acquisition"
            or job.run_id != origin.run_id
            or job.state != "running"
            or reentry_context.admission.scope.status != "established"
            or reentry_context.admission.scope.actor_authenticated is not True
            or not reentry_context.admission.scope.actor_subject
            or reentry_context.admission.scope.tenant_id != origin.tenant_id
            or reentry_context.admission.scope.cell_id != origin.cell_id
            or reentry_context.admission.attempt < reentry_context.action.action_attempt
        ):
            raise ValueError("candidate_experiment_source_basis_reentry_context_not_current")
        if initial_reentry_context is not None:
            current_head = bridge.control_store.get_acquisition_action_head(
                tenant_id=origin.tenant_id,
                cell_id=origin.cell_id,
                run_id=origin.run_id,
                source_job_id=origin.source_job_id,
                route_id=origin.route_id,
                action_generation=len(origin.candidate_terminal_history_chain) + 1,
            )
            current_admission = bridge.control_store.current_execution_job_admission()
            if (
                type(current_head) is not AcquisitionActionHeadRecord
                or current_head != reentry_context.head
                or type(current_admission) is not ControlJobExecutionAdmission
                or current_admission.job.state != "running"
                or not current_admission.same_execution_identity(reentry_context.admission)
            ):
                raise ValueError("candidate_experiment_source_basis_reentry_context_not_current")
        selection, action = reentry_context.selection, reentry_context.action
        # An initial context alone grants no reuse. Only an operation-owned
        # context can guard each read; expired or foreign carriers fail there.
        read_context = (
            reentry_context if reentry_context._read_operation_guard is not None else None
        )
        if read_context is None:
            current_action = read_candidate_experiment_acquisition_action(
                bridge=bridge,
                origin=origin,
                receipt_ref=candidate_action_ref,
                require_current_action=False,
            )
        else:
            current_action = _read_candidate_experiment_action_in_operation(
                bridge=bridge,
                origin=origin,
                receipt_ref=candidate_action_ref,
                context=read_context,
            )
        if current_action != action or action.selection != selection:
            raise ValueError("candidate_experiment_source_basis_action_changed")
        selected = _candidate_experiment_source_selection(bridge, origin)
        if selected != selection:
            raise ValueError("candidate_experiment_source_basis_selection_changed")
        source = read_candidate_acquisition_source(
            bridge.artifact_store,
            source_ref=action.candidate_source_ref,
            authority=bridge.authority,
        )
        if (
            source.tenant_id != origin.tenant_id
            or source.cell_id != origin.cell_id
            or source.run_id != origin.run_id
            or source.job_id != action.action_job_id
            or source.route_id != origin.route_id
            or source.candidate_digest != selection.candidate_digest
            or action.profile_selection_ref != selection.profile_selection_ref
            or action.canonical_variable_id != selection.canonical_variable_id
            or action.target_slot_id != selection.target_slot_id
        ):
            raise ValueError("candidate_experiment_source_basis_source_scope_mismatch")
        effective_generation_run, effective_source_cycle = _candidate_experiment_effective_source(
            origin
        )
        prior_owner = bridge._candidate_experiment_prior_owner(
            origin=origin,
            selection=selection,
        )
        if (
            prior_owner.generation_run != effective_generation_run
            or prior_owner.source_cycle != effective_source_cycle
        ):
            raise ValueError("candidate_source_basis_effective_source_changed")
        profile = prior_owner.profile
        declaration = prior_owner.model_declaration
        prior_evaluation = prior_owner.selected_evaluation
        if prior_evaluation is not None and (
            prior_evaluation.selected.candidate_id
            != prior_owner.source_cycle.selected_candidate_ref
            or prior_evaluation.selected.candidate_content_hash
            != prior_owner.source_cycle.selected_candidate_content_hash
            or not _selected_n5_world_model_matches_exact_n4_context(
                selected_world_model_hash=(prior_evaluation.selected.world_model_record_hash),
                n4_source_world_model_hash=(prior_evaluation.source.world_model_record_hash),
                context_world_model_hash=(
                    prior_evaluation.handoff.context.world_model_record_content_hash
                ),
                context_world_model_record_hash=(
                    prior_evaluation.handoff.context.world_model_record.content_hash
                ),
                n5_input_world_model_hash=(
                    prior_evaluation.input_record.materialization.world_model_record_hash
                ),
                n5_execution_world_model_hash=(prior_evaluation.execution.world_model_record_hash),
            )
        ):
            raise ValueError("candidate_experiment_source_basis_prior_n5_changed")
        intent_ref, intent = bridge._candidate_world_materialization_intent(
            origin=origin,
            candidate_action_ref=candidate_action_ref,
            configured_profile=profile,
            original_model_declaration=declaration,
            _read_context=read_context,
        )
        if intent.action_phase_ref != action.action_phase_ref:
            raise ValueError("candidate_experiment_source_basis_intent_phase_mismatch")
        predecessors = _candidate_source_predecessors_for_verified_experiment_origin(
            store=bridge.artifact_store, origin=origin
        )
        inputs = CandidateSourceBasisInputs(
            configured_profile=profile,
            original_model_declaration=declaration,
            base_data_snapshot_ref=world_model_artifact_views(
                profile.context_inputs.world_model_record
            ).data_snapshot_ref,
            base_world_model_ref=(predecessors[-1].world_model_ref if predecessors else None),
            candidate_source_ref=action.candidate_source_ref,
            slot_binding=CandidateAcquisitionSourceSlotBinding(
                profile_selection_ref=selection.profile_selection_ref,
                candidate_digest=selection.candidate_digest,
                canonical_variable_id=selection.canonical_variable_id,
                target_slot_id=selection.target_slot_id,
            ),
            transaction_time=intent.transaction_time,
        )
        prepared = prepare_candidate_source_basis_values(
            store=bridge.artifact_store,
            problem=origin.design_problem_basis,
            inputs=inputs,
            predecessors=predecessors,
        )
        # Preparation can be lengthy. An active operation repeats its live
        # guard; an ordinary caller still performs the full canonical replay.
        if read_context is None:
            fresh_selection, _fresh_phase, _fresh_admission, fresh_action = (
                _current_candidate_experiment_reentry_action(
                    bridge,
                    origin,
                    pending_phase_ref,
                    candidate_action_ref,
                )
            )
        else:
            fresh_action = _read_candidate_experiment_action_in_operation(
                bridge=bridge,
                origin=origin,
                receipt_ref=candidate_action_ref,
                context=read_context,
            )
            fresh_selection = _candidate_experiment_source_selection(bridge, origin)
        fresh_prior_owner = bridge._candidate_experiment_prior_owner(
            origin=origin, selection=fresh_selection
        )
        fresh_profile = fresh_prior_owner.profile
        fresh_declaration = fresh_prior_owner.model_declaration
        fresh_intent_ref, fresh_intent = bridge._candidate_world_materialization_intent(
            origin=origin,
            candidate_action_ref=candidate_action_ref,
            configured_profile=fresh_profile,
            original_model_declaration=fresh_declaration,
            create=False,
            _read_context=read_context,
        )
        if (
            fresh_action != action
            or fresh_selection != selection
            or fresh_profile != profile
            or fresh_declaration != declaration
            or fresh_prior_owner.generation_run != prior_owner.generation_run
            or fresh_prior_owner.source_cycle != prior_owner.source_cycle
            or fresh_prior_owner.selected_evaluation != prior_owner.selected_evaluation
            or fresh_prior_owner.first_n4_source != prior_owner.first_n4_source
            or fresh_intent_ref != intent_ref
            or fresh_intent != intent
            or _candidate_source_predecessors_for_verified_experiment_origin(
                store=bridge.artifact_store, origin=origin
            )
            != predecessors
        ):
            raise ValueError("candidate_experiment_source_basis_owner_changed")
        return prepared, intent_ref, intent
    except (OSError, RuntimeError, TypeError, ValueError, KeyError, AttributeError) as exc:
        return (
            CandidateSourceBasisValues(
                "not_established", (str(getattr(exc, "code", None) or exc),)
            ),
            None,
            None,
        )
