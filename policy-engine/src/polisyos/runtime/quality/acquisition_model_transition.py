"""Replay bounded candidate model and outcome revisions after acquisition.

This is a read-only composition of the existing acquisition-basis and N5
owners. It does not admit a source, establish causal grounding, or infer an
independent empirical replication from a new execution or observation ID.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Literal, TypedDict, Unpack

from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key
from polisyos.runtime.quality.acquisition_evaluation import (
    AcquisitionEvaluationBasis,
    AcquisitionEvaluationDecision,
    CandidateAcquisitionEvaluationBasis,
    CandidateAcquisitionEvaluationDecision,
    CandidateEvaluationTerminalHistory,
    _candidate_model_values_same,
    _candidate_ref_same,
    _declaration_meaning,
    read_acquisition_evaluation_artifact,
    replay_acquisition_basis_for_history,
    replay_candidate_acquisition_basis_for_history,
    resolve_selected_acquisition_evaluation_parts,
)
from polisyos.runtime.quality.n5_execution_basis import (
    exact_n5_content_bytes,
    read_n5_execution_implementation_witness,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import CoreJSONArtifactStore
    from polisyos.foundry.execute import StateSnapshotValueLeaf
    from polisyos.ir import NCMSpec
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality.acquisition_evaluation import ResolvedAcquisitionEvaluation
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateRouteLoopReceipt,
        VerifiedAcquisitionRouteClosure,
    )
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationScenarioProfile
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from polisyos.runtime.quality.generation_cycle import GenerationCycleRecord, GenerationCycleRun
    from polisyos.runtime.quality.n5_execution_basis import N5ExecutionImplementationWitness


@dataclass(frozen=True, slots=True)
class CandidateModelRevision:
    """Selected candidate-only references for a replayed model coefficient change."""

    previous_input_ref: ArtifactRef
    selected_input_ref: ArtifactRef
    previous_declaration_ref: ArtifactRef
    selected_declaration_ref: ArtifactRef
    previous_ncm_ref: ArtifactRef
    selected_ncm_ref: ArtifactRef
    previous_basis_ref: ArtifactRef
    selected_basis_ref: ArtifactRef
    changed_field: Literal["outcome_per_target_unit"] = "outcome_per_target_unit"
    authority_purpose: Literal["candidate_observation_only"] = "candidate_observation_only"


@dataclass(frozen=True, slots=True)
class AcquiredOutcomeRevision:
    """Selected candidate-only references for a changed acquired outcome baseline."""

    previous_input_ref: ArtifactRef
    selected_input_ref: ArtifactRef
    previous_declaration_ref: ArtifactRef
    selected_declaration_ref: ArtifactRef
    previous_ncm_ref: ArtifactRef
    selected_ncm_ref: ArtifactRef
    previous_basis_ref: ArtifactRef
    selected_basis_ref: ArtifactRef
    admitted_source_ref: ArtifactRef
    outcome_world_slot: str
    authority_purpose: Literal["candidate_observation_only"] = "candidate_observation_only"


@dataclass(frozen=True, slots=True)
class _CandidateModelSelection:
    """Select one existing declaration/NCM owner view without asserting an N5 result."""

    profile: CandidateSimulationScenarioProfile
    declaration_ref: ArtifactRef
    ncm_ref: ArtifactRef
    job_id: str


def _read_selected_candidate_coefficient_pair(
    *,
    artifact_store: CoreJSONArtifactStore,
    previous: _CandidateModelSelection,
    selected: _CandidateModelSelection,
    run_id: str,
    tenant_id: str,
    cell_id: str,
) -> tuple[NCMSpec, NCMSpec]:
    """Reopen selected model owners and allow only their coefficient to change.

    This component does not establish a route, source action or completed N5.
    Those owners must independently reconcile these same selected references.
    """
    from polisyos.ir import prepare_ncm_spec_selected_values
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    repository = GenerationSourceRepository(artifact_store)
    meanings = []
    ncms = []
    for selection in (previous, selected):
        if type(selection) is not _CandidateModelSelection or any(
            not _candidate_ref_same(ref, ref)
            or ref.kind != kind
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
            for ref, kind in (
                (
                    selection.declaration_ref,
                    "runtime.quality.candidate_simulation_model_declaration",
                ),
                (selection.ncm_ref, "ir.ncm_spec"),
            )
        ):
            raise ValueError("candidate_source_model_revision_selected_model_ref_required")
        declaration, ncm = repository.load_candidate_declared_ncm(
            declaration_ref=selection.declaration_ref,
            ncm_ref=selection.ncm_ref,
            expected_profile=selection.profile,
            expected_run_id=run_id,
            expected_job_id=selection.job_id,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
        )
        meanings.append(_declaration_meaning(declaration, selection.profile))
        ncms.append(ncm)
    old_value = meanings[0].pop("outcome_per_target_unit")
    new_value = meanings[1].pop("outcome_per_target_unit")
    if (
        exact_n5_content_bytes(meanings[0]) != exact_n5_content_bytes(meanings[1])
        or exact_n5_content_bytes(old_value) == exact_n5_content_bytes(new_value)
        or prepare_ncm_spec_selected_values(ncms[0]).value_bytes
        == prepare_ncm_spec_selected_values(ncms[1]).value_bytes
        or _candidate_ref_same(previous.declaration_ref, selected.declaration_ref)
        or _candidate_ref_same(previous.ncm_ref, selected.ncm_ref)
    ):
        raise ValueError("candidate_source_model_revision_coefficient_mismatch")
    return ncms[0], ncms[1]


def _read_completed_candidate_n5_witness(
    *,
    artifact_store: CoreJSONArtifactStore,
    evaluation: ResolvedAcquisitionEvaluation,
    run_id: str,
    tenant_id: str,
    cell_id: str,
) -> N5ExecutionImplementationWitness:
    """Require the actual numerical owner's completion before reading its witness."""
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    refs = (
        evaluation.selected.n4_source_ref,
        evaluation.selected.context_job_ref,
        evaluation.selected.n5_input_ref,
        evaluation.selected.n5_execution_ref,
        evaluation.selected.n5_result_ref,
        evaluation.input_record.model_declaration_ref,
        evaluation.input_record.ncm_ref,
    )
    if any(
        not _candidate_ref_same(ref, ref) or ref.manifest_profile_sha256 is None for ref in refs
    ):
        raise ValueError("candidate_source_model_revision_selected_n5_view_required")
    actual = GenerationSourceRepository(
        artifact_store
    )._read_candidate_simulation_v5_numerical_output(
        ref=evaluation.selected.n5_execution_ref,
        expected_run_id=run_id,
        expected_job_id=evaluation.source.job_id,
        expected_tenant_id=tenant_id,
        expected_cell_id=cell_id,
    )
    for observed, expected in (
        (actual.source, evaluation.source),
        (actual.input_record, evaluation.input_record),
        (actual.execution, evaluation.execution),
    ):
        # The source reader keeps non-persisted read provenance beside these
        # fields. Compare the complete persisted quantity, preserving all refs.
        if type(observed) is not type(expected) or exact_n5_content_bytes(
            observed.model_dump(mode="python")
        ) != exact_n5_content_bytes(expected.model_dump(mode="python")):
            raise ValueError("candidate_source_model_revision_completed_n5_mismatch")
    if exact_n5_content_bytes(actual.result.content_bound_payload()) != exact_n5_content_bytes(
        evaluation.result.content_bound_payload()
    ):
        raise ValueError("candidate_source_model_revision_completed_n5_mismatch")
    witness = read_n5_execution_implementation_witness(
        actual.result, input_ref=evaluation.selected.n5_input_ref
    )
    if witness.predicate_provenance != "recomputed" or witness.reason_codes:
        raise ValueError("candidate_source_model_revision_implementation_not_established")
    return witness


def _native_facets(
    basis: AcquisitionEvaluationBasis | CandidateAcquisitionEvaluationBasis,
) -> dict[str, object]:
    """Read exact native facet encodings, rejecting malformed or duplicate keys."""

    try:
        return _native_mapping(json.loads(bytes.fromhex(basis.effective_native_values_hex)))
    except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("candidate_model_revision_native_facets_invalid") from exc


def _native_mapping(encoded: object) -> dict[str, object]:
    """Index one encoded mapping without dropping unknown or duplicate fields."""

    if not isinstance(encoded, dict) or set(encoded) != {"mapping"}:
        raise ValueError("candidate_revision_native_mapping_invalid")
    rows = encoded["mapping"]
    if not isinstance(rows, list):
        raise ValueError("candidate_revision_native_mapping_invalid")
    result: dict[str, object] = {}
    for row in rows:
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError("candidate_revision_native_mapping_invalid")
        key, value = row
        if not isinstance(key, dict) or set(key) != {"str"}:
            raise ValueError("candidate_revision_native_mapping_invalid")
        name = key["str"]
        if not isinstance(name, str) or name in result:
            raise ValueError("candidate_revision_native_mapping_invalid")
        result[name] = value
    return result


def _native_tuple(encoded: object) -> list[object]:
    if not isinstance(encoded, dict) or set(encoded) != {"tuple"}:
        raise ValueError("candidate_revision_native_tuple_invalid")
    values = encoded["tuple"]
    if not isinstance(values, list):
        raise ValueError("candidate_revision_native_tuple_invalid")
    return values


def is_prospective_candidate_model_revision(
    previous: AcquisitionEvaluationBasis | CandidateAcquisitionEvaluationBasis,
    prospective: AcquisitionEvaluationBasis | CandidateAcquisitionEvaluationBasis,
) -> bool:
    """Recognize a coefficient-only prospective change, without certifying its result.

    Both complete bases must already have been recomputed by their owners. The
    actual selected N5 output still has to pass ``resolve_candidate_model_revision``.
    Other differences remain on the ordinary acquisition evaluation path.
    """
    if (
        type(previous) not in {AcquisitionEvaluationBasis, CandidateAcquisitionEvaluationBasis}
        or type(prospective) is not type(previous)
        or previous.predicate_provenance != "recomputed"
        or prospective.predicate_provenance != "recomputed"
        or previous.reason_codes
        or prospective.reason_codes
    ):
        return False
    return _is_coefficient_only_native_change(_native_facets(previous), _native_facets(prospective))


def _is_coefficient_only_native_change(old: dict[str, object], new: dict[str, object]) -> bool:
    """Classify complete owner values without inventing an evaluation envelope."""
    model_fields = {"declared_model", "selected_native_ncm"}
    if (
        set(old) != set(new)
        or not model_fields.issubset(old)
        or any(old[name] != new[name] for name in old.keys() - model_fields)
        or old["selected_native_ncm"] == new["selected_native_ncm"]
    ):
        return False
    old_model = _native_mapping(old["declared_model"])
    new_model = _native_mapping(new["declared_model"])
    coefficient = "outcome_per_target_unit"
    return (
        set(old_model) == set(new_model)
        and coefficient in old_model
        and old_model[coefficient] != new_model[coefficient]
        and all(old_model[name] == new_model[name] for name in old_model.keys() - {coefficient})
    )


def _implementation_without_reconciled_ncm(
    implementation: dict[str, object], ncm: object
) -> dict[str, object]:
    """Remove only the selected engine's NCM after exact owner reconciliation."""

    value = deepcopy(implementation)
    try:
        selection = value["selected_engine_values"]
        if not isinstance(selection, dict) or selection.get("dataclass") != (
            "polisyos.runtime.quality.joint_simulation_horizon._SelectedEngine"
        ):
            raise ValueError
        plan = selection["fields"]["plan"]
        if not isinstance(plan, dict) or plan.get("model") != (
            "polisyos.runtime.quality.joint_simulation_horizon.EnginePlan"
        ):
            raise ValueError
        fields = plan["fields"]
        if (
            not isinstance(fields, dict)
            or fields.get("engine_kind")
            != json.loads(exact_n5_content_bytes("ncm_parallel_worlds"))
            or fields.get("ncm_spec") != json.loads(exact_n5_content_bytes(ncm))
        ):
            raise ValueError
        fields["ncm_spec"] = {"reconciled_selected_ncm": True}
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("candidate_model_revision_selected_engine_mismatch") from exc
    return value


def _require_model_revision_facets(
    previous: AcquisitionEvaluationBasis | CandidateAcquisitionEvaluationBasis,
    prospective: AcquisitionEvaluationBasis | CandidateAcquisitionEvaluationBasis,
    selected: AcquisitionEvaluationBasis | CandidateAcquisitionEvaluationBasis,
    *,
    previous_implementation: dict[str, object],
    selected_implementation: dict[str, object],
    previous_ncm: object,
    selected_ncm: object,
) -> None:
    """Compare complete replayed facets, reconciling only the owned model change."""

    if (
        type(previous)
        not in {
            AcquisitionEvaluationBasis,
            CandidateAcquisitionEvaluationBasis,
        }
        or type(prospective) is not type(previous)
        or type(selected) is not type(previous)
    ):
        raise ValueError("candidate_model_revision_basis_type_mismatch")
    old = _native_facets(previous)
    pending = _native_facets(prospective)
    new = _native_facets(selected)
    model_fields = {"declared_model", "selected_native_ncm"}
    implementation = "actual_live_implementation"
    if (
        set(old) != set(pending)
        or set(old) != set(new)
        or not (model_fields | {implementation}).issubset(old)
    ):
        raise ValueError("candidate_model_revision_facet_denominator_changed")
    if any(old[name] != new[name] for name in old.keys() - model_fields - {implementation}):
        raise ValueError("candidate_model_revision_non_model_basis_changed")
    if any(old[name] == new[name] for name in model_fields):
        raise ValueError("candidate_model_revision_model_difference_not_established")
    if any(pending[name] != new[name] for name in pending.keys() - {implementation}):
        raise ValueError("candidate_model_revision_prospective_actual_mismatch")
    if (
        old[implementation] != json.loads(exact_n5_content_bytes(previous_implementation))
        or pending[implementation] != json.loads(exact_n5_content_bytes(previous_implementation))
        or new[implementation] != json.loads(exact_n5_content_bytes(selected_implementation))
    ):
        raise ValueError("candidate_model_revision_implementation_binding_mismatch")
    previous_code = _implementation_without_reconciled_ncm(previous_implementation, previous_ncm)
    selected_code = _implementation_without_reconciled_ncm(selected_implementation, selected_ncm)
    if exact_n5_content_bytes(previous_code) != exact_n5_content_bytes(selected_code):
        raise ValueError("candidate_model_revision_implementation_changed")


def _require_outcome_owner_values(
    old: dict[str, object],
    new: dict[str, object],
    *,
    previous_state: tuple[StateSnapshotValueLeaf, ...],
    selected_state: tuple[StateSnapshotValueLeaf, ...],
    state_path: str,
) -> None:
    """Limit the world delta to one owner-replayed source and one state leaf."""

    previous_leaves = {leaf.path: leaf for leaf in previous_state}
    selected_leaves = {leaf.path: leaf for leaf in selected_state}
    if (
        len(previous_leaves) != len(previous_state)
        or len(selected_leaves) != len(selected_state)
        or set(previous_leaves) != set(selected_leaves)
        or state_path not in previous_leaves
        or {path for path in previous_leaves if previous_leaves[path] != selected_leaves[path]}
        != {state_path}
        or previous_leaves[state_path].dtype != selected_leaves[state_path].dtype
        or previous_leaves[state_path].shape != selected_leaves[state_path].shape
    ):
        raise ValueError("acquired_outcome_revision_unrelated_state_changed")

    observations = []
    worlds = []
    bindings = []
    for facets, leaves in ((old, previous_state), (new, selected_state)):
        observation = _native_mapping(facets["controlled_observation"])
        row = _native_mapping(observation["observation"])
        observations.append((observation, row))
        world = _native_mapping(facets["world"])
        if (
            world.get("data") != facets["controlled_observation"]
            or world.get("state")
            != json.loads(exact_n5_content_bytes(tuple(asdict(leaf) for leaf in leaves)))
            or facets["foundry_state"] != json.loads(exact_n5_content_bytes(leaves))
        ):
            raise ValueError("acquired_outcome_revision_world_state_binding_mismatch")
        binding = _native_mapping(world["data_forge_binding"])
        if set(binding) != {"manifest", "row", "artifact_meanings", "lineage_meanings"}:
            raise ValueError("acquired_outcome_revision_binding_denominator_changed")
        artifacts = _native_tuple(binding["artifact_meanings"])
        lineages = _native_tuple(binding["lineage_meanings"])
        expected_artifact = json.loads(
            exact_n5_content_bytes({"observation": None, "consumed_state": None})
        )
        # Compare the two owner-declared value positions without guessing from
        # names in an arbitrary nested payload.
        expected_map = _native_mapping(expected_artifact)
        expected_map["observation"] = world["data"]
        expected_map["consumed_state"] = world["state"]
        if (
            len(artifacts) != 1
            or len(lineages) != 4
            or _native_mapping(artifacts[0]) != expected_map
            or lineages[1] != world["data"]
            or lineages[2] != world["data"]
            or _native_mapping(lineages[3]) != expected_map
        ):
            raise ValueError("acquired_outcome_revision_binding_values_mismatch")
        worlds.append(world)
        bindings.append((binding, lineages[0]))

    old_observation, old_row = observations[0]
    new_observation, new_row = observations[1]
    source_changes = {"value", "source_watermark", "dataset_version"}
    if (
        set(old_observation) != set(new_observation)
        or any(
            old_observation[name] != new_observation[name]
            for name in old_observation.keys() - {"observation"}
        )
        or set(old_row) != set(new_row)
        or not source_changes.issubset(old_row)
        or any(old_row[name] != new_row[name] for name in old_row.keys() - source_changes)
        or old_row["value"] == new_row["value"]
    ):
        raise ValueError("acquired_outcome_revision_source_scope_changed")
    old_world, new_world = worlds
    if (
        set(old_world) != set(new_world)
        or any(
            old_world[name] != new_world[name]
            for name in old_world.keys() - {"data", "state", "data_forge_binding"}
        )
        or bindings[0][0]["manifest"] != bindings[1][0]["manifest"]
        or bindings[0][0]["row"] != bindings[1][0]["row"]
        or bindings[0][1] != bindings[1][1]
    ):
        raise ValueError("acquired_outcome_revision_world_dependency_changed")


def _require_outcome_state_baselines(
    previous_state_value: object,
    selected_state_value: object,
    previous_baseline: object,
    selected_baseline: object,
) -> None:
    """Apply the model owner's scalar extraction law to both selected states."""

    try:
        previous = float(previous_state_value)
        selected = float(selected_state_value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("acquired_outcome_revision_state_value_unresolved") from exc
    if exact_n5_content_bytes(previous) != exact_n5_content_bytes(
        previous_baseline
    ) or exact_n5_content_bytes(selected) != exact_n5_content_bytes(selected_baseline):
        raise ValueError("acquired_outcome_revision_state_baseline_mismatch")


def _require_outcome_revision_facets(
    previous: AcquisitionEvaluationBasis,
    prospective: AcquisitionEvaluationBasis,
    selected: AcquisitionEvaluationBasis,
    *,
    previous_implementation: dict[str, object],
    selected_implementation: dict[str, object],
    previous_ncm: object,
    selected_ncm: object,
    previous_state: tuple[StateSnapshotValueLeaf, ...],
    selected_state: tuple[StateSnapshotValueLeaf, ...],
    state_path: str,
) -> None:
    """Bind changed source/state/model values to the actual selected N5 execution."""

    old = _native_facets(previous)
    pending = _native_facets(prospective)
    new = _native_facets(selected)
    implementation = "actual_live_implementation"
    changed = {
        "controlled_observation",
        "foundry_state",
        "declared_model",
        "selected_native_ncm",
        "n5_request_values",
        "world",
    }
    if (
        set(old) != set(pending)
        or set(old) != set(new)
        or not (changed | {implementation}).issubset(old)
    ):
        raise ValueError("acquired_outcome_revision_facet_denominator_changed")
    if any(old[name] == new[name] for name in changed):
        raise ValueError("acquired_outcome_revision_source_state_model_not_changed")
    if any(old[name] != new[name] for name in old.keys() - changed - {implementation}):
        raise ValueError("acquired_outcome_revision_unrelated_basis_changed")
    _require_outcome_owner_values(
        old,
        new,
        previous_state=previous_state,
        selected_state=selected_state,
        state_path=state_path,
    )
    if any(pending[name] != new[name] for name in pending.keys() - {implementation}):
        raise ValueError("acquired_outcome_revision_prospective_actual_mismatch")
    if (
        old[implementation] != json.loads(exact_n5_content_bytes(previous_implementation))
        or pending[implementation] != json.loads(exact_n5_content_bytes(previous_implementation))
        or new[implementation] != json.loads(exact_n5_content_bytes(selected_implementation))
    ):
        raise ValueError("acquired_outcome_revision_implementation_binding_mismatch")
    previous_code = _implementation_without_reconciled_ncm(previous_implementation, previous_ncm)
    selected_code = _implementation_without_reconciled_ncm(selected_implementation, selected_ncm)
    if exact_n5_content_bytes(previous_code) != exact_n5_content_bytes(selected_code):
        raise ValueError("acquired_outcome_revision_implementation_changed")


def _resolve_candidate_revision(
    *,
    artifact_store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    control_store: ControlPlaneStore,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    design_problem_ref: str,
    action_job_id: str,
    action_generation: int,
    route_id: str,
    decision_ref: ArtifactRef,
    selected_basis_ref: ArtifactRef,
    previous_run: GenerationCycleRun,
    previous_cycle: GenerationCycleRecord,
    selected_run: GenerationCycleRun,
    selected_cycle: GenerationCycleRecord,
    transition_kind: Literal["candidate_model_revision", "acquired_outcome_revision"],
) -> CandidateModelRevision | AcquiredOutcomeRevision:
    """Reopen the exact owner chain for a bounded candidate revision.

    The selected action's existing decision and its prospective and actual
    bases must replay. Both complete N5 evaluations are resolved from their
    owner-bound cycle artifacts. Both revisions check their real changed
    declaration and resulting NCM; neither establishes a general method
    change or an independently sampled empirical observation.

    Raises:
        ValueError: If any selected evidence, action scope, or supported
            semantic difference cannot be independently established.
    """
    from polisyos.ir import prepare_ncm_spec_selected_values
    from polisyos.runtime.quality.generation_cycle import _cycle_basis_ref
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    # The caller must independently resolve the selected action terminal and
    # re-entry receipt. Preserve the existing append-only cycle relationship
    # here as well; a pair of unrelated owner-valid cycles is not a revision.
    if (
        not previous_run.cycles
        or not selected_run.cycles
        or previous_run.cycles[-1] != previous_cycle
        or selected_run.cycles[-1] != selected_cycle
        or selected_run.cycles[:-1] != previous_run.cycles
        or selected_run.run_id != previous_run.run_id
        or selected_run.design_problem_ref != previous_run.design_problem_ref
    ):
        raise ValueError("candidate_model_revision_continuation_mismatch")

    decision = read_acquisition_evaluation_artifact(
        store=artifact_store,
        event_log=event_log,
        ref=decision_ref,
        record_type=AcquisitionEvaluationDecision,
    )
    if (
        type(decision) is not AcquisitionEvaluationDecision
        or decision.comparison_result != "different"
        or decision.predicate_provenance != "recomputed"
        or decision.reason_codes
        or decision.prior_basis_ref is None
        or decision.prior_evaluation is None
        or decision.prior_evaluation.basis_ref != decision.prior_basis_ref
        or (decision.tenant_id, decision.cell_id, decision.run_id) != (tenant_id, cell_id, run_id)
        or decision.design_problem_ref != design_problem_ref
        or decision.design_problem_basis_ref != _cycle_basis_ref(previous_cycle)
        or decision.design_problem_basis_ref != _cycle_basis_ref(selected_cycle)
        or decision.action_job_id != action_job_id
        or decision.action_generation != action_generation
        or decision.route_id != route_id
    ):
        raise ValueError("candidate_model_revision_decision_not_established")

    scope = {
        "artifact_store": artifact_store,
        "control_store": control_store,
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "run_id": run_id,
        "design_problem_ref": design_problem_ref,
    }
    previous = resolve_selected_acquisition_evaluation_parts(
        **scope, generation_run=previous_run, source_cycle=previous_cycle
    )
    selected = resolve_selected_acquisition_evaluation_parts(
        **scope, generation_run=selected_run, source_cycle=selected_cycle
    )
    previous_origin = previous.source.origin_source_ref or previous.selected.n4_source_ref
    if (
        decision.candidate_id != previous.selected.candidate_id
        or previous.selected.candidate_id != selected.selected.candidate_id
        or decision.prior_evaluation.model_dump(exclude={"basis_ref"})
        != previous.selected.model_dump(exclude={"basis_ref"})
        or previous.source.stable_subject_ref != selected.source.stable_subject_ref
        or previous.source.semantic_identity_hash != selected.source.semantic_identity_hash
        or previous.source.problem != selected.source.problem
        or selected.source.origin_source_ref is None
        or artifact_ref_identity_key(previous_origin)
        != artifact_ref_identity_key(selected.source.origin_source_ref)
        or previous.source.candidate_occurrence_hash == selected.source.candidate_occurrence_hash
        or previous.source.world_model_record_hash == selected.source.world_model_record_hash
        or selected_cycle.cycle_index != previous_cycle.cycle_index + 1
        or selected.source.job_id != action_job_id
    ):
        raise ValueError("candidate_model_revision_evaluation_scope_mismatch")

    previous_basis = read_acquisition_evaluation_artifact(
        store=artifact_store,
        event_log=event_log,
        ref=decision.prior_basis_ref,
        record_type=AcquisitionEvaluationBasis,
    )
    prospective_basis = read_acquisition_evaluation_artifact(
        store=artifact_store,
        event_log=event_log,
        ref=decision.current_basis_ref,
        record_type=AcquisitionEvaluationBasis,
    )
    selected_basis = read_acquisition_evaluation_artifact(
        store=artifact_store,
        event_log=event_log,
        ref=selected_basis_ref,
        record_type=AcquisitionEvaluationBasis,
    )
    if not all(
        type(value) is AcquisitionEvaluationBasis
        for value in (previous_basis, prospective_basis, selected_basis)
    ):
        raise ValueError("candidate_model_revision_basis_untyped")
    if (
        previous_basis.evaluation != previous.selected
        or prospective_basis.evaluation is not None
        or selected_basis.evaluation != selected.selected
        or prospective_basis.preparation_inputs != selected_basis.preparation_inputs
        or prospective_basis.growth_receipt_ref != decision.growth_receipt_ref
        or selected_basis.growth_receipt_ref != decision.growth_receipt_ref
        or prospective_basis.admitted_source_ref != decision.admitted_source_ref
        or selected_basis.admitted_source_ref != decision.admitted_source_ref
        or any(
            basis.predicate_provenance != "recomputed" or basis.reason_codes
            for basis in (previous_basis, prospective_basis, selected_basis)
        )
    ):
        raise ValueError("candidate_model_revision_prospective_actual_mismatch")
    if any(
        (basis.tenant_id, basis.cell_id, basis.run_id, basis.source_job_id)
        != (tenant_id, cell_id, run_id, decision.source_job_id)
        or basis.candidate_id != decision.candidate_id
        or basis.design_problem_ref != decision.design_problem_basis_ref
        for basis in (previous_basis, prospective_basis, selected_basis)
    ):
        raise ValueError("candidate_model_revision_basis_scope_mismatch")

    for basis, evaluation in (
        (previous_basis, previous),
        (prospective_basis, previous),
        (selected_basis, selected),
    ):
        replay_acquisition_basis_for_history(
            artifact_store=artifact_store,
            event_log=event_log,
            control_store=control_store,
            basis=basis,
            prior_evaluation=evaluation,
        )
    repository = GenerationSourceRepository(artifact_store)
    declarations = []
    native_ncms = []
    ncms = []
    for evaluation in (previous, selected):
        input_record = evaluation.input_record
        declaration, ncm = repository.load_candidate_declared_ncm(
            declaration_ref=input_record.model_declaration_ref,
            ncm_ref=input_record.ncm_ref,
            expected_profile=input_record.profile,
            expected_run_id=run_id,
            expected_job_id=evaluation.source.job_id,
            expected_tenant_id=tenant_id,
            expected_cell_id=cell_id,
        )
        declarations.append(_declaration_meaning(declaration, input_record.profile))
        native_ncms.append(prepare_ncm_spec_selected_values(ncm).value_bytes)
        ncms.append(ncm)

    changed_field = (
        "outcome_per_target_unit"
        if transition_kind == "candidate_model_revision"
        else "outcome_baseline"
    )
    old_value = declarations[0].pop(changed_field)
    new_value = declarations[1].pop(changed_field)
    if (
        exact_n5_content_bytes(declarations[0]) != exact_n5_content_bytes(declarations[1])
        or exact_n5_content_bytes(old_value) == exact_n5_content_bytes(new_value)
        or native_ncms[0] == native_ncms[1]
        or artifact_ref_identity_key(previous.input_record.model_declaration_ref)
        == artifact_ref_identity_key(selected.input_record.model_declaration_ref)
        or artifact_ref_identity_key(previous.input_record.ncm_ref)
        == artifact_ref_identity_key(selected.input_record.ncm_ref)
    ):
        raise ValueError("candidate_model_revision_declaration_difference_not_established")

    previous_witness = read_n5_execution_implementation_witness(
        previous.result, input_ref=previous.selected.n5_input_ref
    )
    selected_witness = read_n5_execution_implementation_witness(
        selected.result, input_ref=selected.selected.n5_input_ref
    )
    if (
        previous_witness.predicate_provenance != "recomputed"
        or selected_witness.predicate_provenance != "recomputed"
    ):
        raise ValueError("candidate_model_revision_implementation_not_established")
    comparison = {
        "previous_implementation": previous_witness.implementation,
        "selected_implementation": selected_witness.implementation,
        "previous_ncm": ncms[0],
        "selected_ncm": ncms[1],
    }
    refs = {
        "previous_input_ref": previous.selected.n5_input_ref,
        "selected_input_ref": selected.selected.n5_input_ref,
        "previous_declaration_ref": previous.input_record.model_declaration_ref,
        "selected_declaration_ref": selected.input_record.model_declaration_ref,
        "previous_ncm_ref": previous.input_record.ncm_ref,
        "selected_ncm_ref": selected.input_record.ncm_ref,
        "previous_basis_ref": decision.prior_basis_ref,
        "selected_basis_ref": selected_basis_ref,
    }
    if transition_kind == "candidate_model_revision":
        _require_model_revision_facets(
            previous_basis, prospective_basis, selected_basis, **comparison
        )
        return CandidateModelRevision(**refs)

    outcome = selected.source.problem.outcome_of_interest.target_variable
    target = selected.input_record.profile.rule.target_world_slot
    old_config = previous.input_record.n5
    new_config = selected.input_record.n5
    old_baseline = old_config.baseline_state
    new_baseline = new_config.baseline_state
    if (
        outcome == target
        or selected_basis.preparation_inputs.slot_binding.target_slot_id != outcome
        or previous.input_record.profile.rule.target_world_slot != target
        or outcome not in old_baseline
        or outcome not in new_baseline
        or target not in old_baseline
        or target not in new_baseline
        or set(old_baseline) != set(new_baseline)
        or exact_n5_content_bytes(old_config.model_dump(exclude={"baseline_state"}))
        != exact_n5_content_bytes(new_config.model_dump(exclude={"baseline_state"}))
        or any(
            exact_n5_content_bytes(old_baseline[slot]) != exact_n5_content_bytes(new_baseline[slot])
            for slot in old_baseline.keys() - {outcome}
        )
        or exact_n5_content_bytes(old_baseline[outcome]) != exact_n5_content_bytes(old_value)
        or exact_n5_content_bytes(new_baseline[outcome]) != exact_n5_content_bytes(new_value)
    ):
        raise ValueError("acquired_outcome_revision_selected_slot_mismatch")
    from polisyos.foundry.execute import (
        get_state_path,
        load_state_snapshot,
        state_snapshot_value_projection,
    )
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views

    old_world = previous.input_record.profile.context_inputs.world_model_record
    new_world = selected.input_record.profile.context_inputs.world_model_record
    slot_bindings = tuple(
        binding for binding in old_world.policy_slot_map if binding.slot_id == outcome
    )
    if old_world.policy_slot_map != new_world.policy_slot_map or len(slot_bindings) != 1:
        raise ValueError("acquired_outcome_revision_world_slot_mismatch")
    old_state_value = load_state_snapshot(
        artifact_store,
        snapshot_ref=world_model_artifact_views(old_world).bound_state_snapshot_ref,
    )
    new_state_value = load_state_snapshot(
        artifact_store,
        snapshot_ref=world_model_artifact_views(new_world).bound_state_snapshot_ref,
    )
    state_path = slot_bindings[0].state_path
    try:
        _require_outcome_state_baselines(
            get_state_path(old_state_value, state_path),
            get_state_path(new_state_value, state_path),
            old_value,
            new_value,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("acquired_outcome_revision_state_baseline_mismatch") from exc
    _require_outcome_revision_facets(
        previous_basis,
        prospective_basis,
        selected_basis,
        **comparison,
        previous_state=state_snapshot_value_projection(old_state_value),
        selected_state=state_snapshot_value_projection(new_state_value),
        state_path=state_path,
    )
    return AcquiredOutcomeRevision(
        **refs,
        admitted_source_ref=decision.admitted_source_ref,
        outcome_world_slot=outcome,
    )


class _CandidateRevisionArguments(TypedDict):
    artifact_store: CoreJSONArtifactStore
    event_log: RuntimeDiagnosticEventLog
    control_store: ControlPlaneStore
    tenant_id: str
    cell_id: str
    run_id: str
    design_problem_ref: str
    action_job_id: str
    action_generation: int
    route_id: str
    decision_ref: ArtifactRef
    selected_basis_ref: ArtifactRef
    previous_run: GenerationCycleRun
    previous_cycle: GenerationCycleRecord
    selected_run: GenerationCycleRun
    selected_cycle: GenerationCycleRecord


def resolve_candidate_model_revision(
    **kwargs: Unpack[_CandidateRevisionArguments],
) -> CandidateModelRevision:
    """Replay a coefficient-only candidate model revision through existing owners."""

    result = _resolve_candidate_revision(**kwargs, transition_kind="candidate_model_revision")
    if type(result) is not CandidateModelRevision:
        raise RuntimeError("candidate_model_revision_result_untyped")
    return result


def resolve_candidate_source_model_revision(
    *,
    artifact_store: CoreJSONArtifactStore,
    event_log: RuntimeDiagnosticEventLog,
    control_store: ControlPlaneStore,
    control_service: ControlPlaneService,
    terminal: AcquisitionCandidateRouteLoopReceipt,
    prior_closure: VerifiedAcquisitionRouteClosure,
) -> CandidateModelRevision:
    """Replay the bounded coefficient-only revision for a candidate-source route.

    The route sink must independently bind this terminal to its actual action
    transaction. This read-only verifier checks the previous, prospective and
    selected source/model/N5 owners; it does not admit data or certify a new
    empirical observation.
    """
    from polisyos.runtime.http.services.control.run_lifecycle import (
        AcquisitionRouteLoopAuthoritySink,
        ControlPlaneService,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateRouteLoopReceipt,
        VerifiedAcquisitionRouteClosure,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        CandidateAcquisitionWorldCheckpoint,
        CandidateAcquisitionWorldIntent,
    )
    from polisyos.runtime.quality.candidate_source_basis import (
        _candidate_source_predecessors_for_verified_closure,
    )
    from polisyos.runtime.quality.candidate_source_reentry_history import (
        _read_historical_action,
        verify_candidate_source_reentry_history,
    )
    from polisyos.runtime.quality.data_state_substrate import CandidateAcquisitionSourceSlotBinding
    from polisyos.runtime.quality.generation_cycle import validate_candidate_source_continuation

    if (
        type(control_service) is not ControlPlaneService
        or control_service._artifact_store is not artifact_store
        or control_service._control_store is not control_store
        or control_service._diagnostic_event_log is not event_log
        or type(terminal) is not AcquisitionCandidateRouteLoopReceipt
        or type(prior_closure) is not VerifiedAcquisitionRouteClosure
        or terminal.terminal_outcome != "candidate_reentry_completed"
        or terminal.candidate_reentry_ref is None
        or terminal.selected_evaluation is None
        or type(control_service.acquisition_route_sink) is not AcquisitionRouteLoopAuthoritySink
    ):
        raise ValueError("candidate_source_model_revision_owner_not_established")
    sink = control_service.acquisition_route_sink
    if (
        sink._artifact_store is not artifact_store
        or sink._control_store is not control_store
        or sink._event_log is not event_log
        or getattr(sink._core_source_resolver, "__self__", None) is not control_service
        or sink._candidate_prior_closure(terminal) != prior_closure
    ):
        raise ValueError("candidate_source_model_revision_prior_route_changed")
    reentry = verify_candidate_source_reentry_history(
        artifact_store=artifact_store,
        event_log=event_log,
        control_store=control_store,
        receipt_ref=terminal.candidate_reentry_ref,
        expected_tenant_id=terminal.tenant_id,
        expected_cell_id=terminal.cell_id,
        expected_run_id=terminal.run_id,
        expected_source_job_id=terminal.source_job_id,
        expected_action_job_id=terminal.job_id,
        expected_route_id=terminal.route_id,
        expected_action_generation=terminal.action_generation,
        expected_selected_action_ref=terminal.candidate_action_ref,
    )
    validate_candidate_source_continuation(prior_closure.generation_run, reentry)
    decision = read_acquisition_evaluation_artifact(
        store=artifact_store,
        event_log=event_log,
        ref=terminal.evaluation_decision_ref,
        record_type=CandidateAcquisitionEvaluationDecision,
    )
    if (
        type(decision) is not CandidateAcquisitionEvaluationDecision
        or decision.comparison_result != "different"
        or decision.predicate_provenance != "recomputed"
        or decision.reason_codes
        or decision.prior_basis_ref is None
        or decision.prior_evaluation is None
        or not _candidate_ref_same(decision.candidate_action_ref, terminal.candidate_action_ref)
        or not _candidate_ref_same(decision.candidate_source_ref, reentry.candidate_source_ref)
        or not _candidate_ref_same(
            decision.candidate_world_intent_ref, reentry.candidate_world_intent_ref
        )
        or (decision.tenant_id, decision.cell_id, decision.run_id, decision.source_job_id)
        != (terminal.tenant_id, terminal.cell_id, terminal.run_id, terminal.source_job_id)
        or decision.action_job_id != terminal.job_id
        or decision.action_generation != terminal.action_generation
        or decision.route_id != terminal.route_id
        or decision.compiled_ref != terminal.compiled_ref
        or decision.design_problem_ref != prior_closure.design_problem_ref
        or decision.design_problem_basis_ref != prior_closure.design_problem_basis_ref
        or decision.candidate_id != prior_closure.source_cycle.selected_candidate_ref
        or decision.source_candidate_content_hash
        != prior_closure.source_cycle.selected_candidate_content_hash
    ):
        raise ValueError("candidate_source_model_revision_decision_mismatch")
    prior = resolve_selected_acquisition_evaluation_parts(
        artifact_store=artifact_store,
        control_store=control_store,
        tenant_id=prior_closure.tenant_id,
        cell_id=prior_closure.cell_id,
        run_id=prior_closure.run_id,
        generation_run=prior_closure.generation_run,
        source_cycle=prior_closure.source_cycle,
        design_problem_ref=prior_closure.design_problem_ref,
    )
    selected = resolve_selected_acquisition_evaluation_parts(
        artifact_store=artifact_store,
        control_store=control_store,
        tenant_id=terminal.tenant_id,
        cell_id=terminal.cell_id,
        run_id=terminal.run_id,
        generation_run=reentry.continued_generation_run,
        source_cycle=reentry.new_cycle,
        design_problem_ref=prior_closure.design_problem_ref,
    )
    previous_origin = prior.source.origin_source_ref or prior.selected.n4_source_ref
    if (
        not _candidate_model_values_same(
            decision.prior_evaluation,
            prior.selected.model_copy(update={"basis_ref": decision.prior_basis_ref}),
        )
        or not _candidate_model_values_same(
            terminal.selected_evaluation,
            selected.selected.model_copy(update={"basis_ref": terminal.selected_basis_ref}),
        )
        or not _candidate_ref_same(
            terminal.selected_evaluation_witness_ref, selected.selected.n5_execution_ref
        )
        or prior.source.stable_subject_ref != selected.source.stable_subject_ref
        or prior.source.semantic_identity_hash != selected.source.semantic_identity_hash
        or prior.source.problem != selected.source.problem
        or selected.source.origin_source_ref is None
        or artifact_ref_identity_key(previous_origin)
        != artifact_ref_identity_key(selected.source.origin_source_ref)
        or reentry.new_cycle.cycle_index != prior_closure.source_cycle.cycle_index + 1
        or selected.source.job_id != terminal.job_id
    ):
        raise ValueError("candidate_source_model_revision_selected_n5_mismatch")
    previous_basis = read_acquisition_evaluation_artifact(
        store=artifact_store,
        event_log=event_log,
        ref=decision.prior_basis_ref,
        record_type=CandidateAcquisitionEvaluationBasis,
    )
    prospective_basis = read_acquisition_evaluation_artifact(
        store=artifact_store,
        event_log=event_log,
        ref=decision.current_basis_ref,
        record_type=CandidateAcquisitionEvaluationBasis,
    )
    selected_basis = read_acquisition_evaluation_artifact(
        store=artifact_store,
        event_log=event_log,
        ref=terminal.selected_basis_ref,
        record_type=CandidateAcquisitionEvaluationBasis,
    )
    if (
        any(
            type(basis) is not CandidateAcquisitionEvaluationBasis
            for basis in (previous_basis, prospective_basis, selected_basis)
        )
        or not prior_closure.candidate_basis_transitions
    ):
        raise ValueError("candidate_source_model_revision_basis_not_established")
    previous_receipt = prior_closure.candidate_basis_transitions[-1]
    predecessors = _candidate_source_predecessors_for_verified_closure(
        store=artifact_store, closure=prior_closure
    )
    if (
        not predecessors
        or previous_basis.basis_role != "evaluated"
        or not _candidate_model_values_same(previous_basis.evaluation, prior.selected)
        or not _candidate_ref_same(
            previous_basis.candidate_action_ref, previous_receipt.candidate_action_ref
        )
        or not _candidate_ref_same(
            previous_basis.candidate_world_intent_ref, previous_receipt.candidate_world_intent_ref
        )
        or not _candidate_ref_same(
            previous_basis.candidate_source_ref, previous_receipt.candidate_source_ref
        )
        or not _candidate_ref_same(
            previous_basis.selected_data_snapshot_ref, previous_receipt.data_snapshot_ref
        )
        or not _candidate_ref_same(
            previous_basis.selected_world_model_ref, previous_receipt.world_model_ref
        )
        or not _candidate_model_values_same(
            previous_basis.preparation_inputs, predecessors[-1].inputs
        )
        or prospective_basis.basis_role != "prospective"
        or prospective_basis.evaluation is not None
        or selected_basis.basis_role != "evaluated"
        or not _candidate_model_values_same(selected_basis.evaluation, selected.selected)
        or not _candidate_model_values_same(
            prospective_basis.preparation_inputs, selected_basis.preparation_inputs
        )
        or prospective_basis.prepared_n5_configuration != selected_basis.prepared_n5_configuration
        or not _candidate_ref_same(
            prospective_basis.candidate_action_ref, terminal.candidate_action_ref
        )
        or not _candidate_ref_same(
            selected_basis.candidate_action_ref, terminal.candidate_action_ref
        )
        or not _candidate_ref_same(
            prospective_basis.candidate_source_ref, reentry.candidate_source_ref
        )
        or not _candidate_ref_same(
            selected_basis.candidate_source_ref, reentry.candidate_source_ref
        )
        or not _candidate_ref_same(
            prospective_basis.candidate_world_intent_ref, reentry.candidate_world_intent_ref
        )
        or not _candidate_ref_same(
            selected_basis.candidate_world_intent_ref, reentry.candidate_world_intent_ref
        )
        or not _candidate_ref_same(
            selected_basis.selected_data_snapshot_ref, reentry.data_snapshot_ref
        )
        or not _candidate_ref_same(selected_basis.selected_world_model_ref, reentry.world_model_ref)
        or not set(previous_basis.limitations).issubset(prospective_basis.limitations)
        or not (set(prospective_basis.limitations) | set(reentry.limitations)).issubset(
            selected_basis.limitations
        )
    ):
        raise ValueError("candidate_source_model_revision_basis_binding_mismatch")
    for basis in (previous_basis, prospective_basis, selected_basis):
        if (
            (basis.tenant_id, basis.cell_id, basis.run_id, basis.source_job_id)
            != (terminal.tenant_id, terminal.cell_id, terminal.run_id, terminal.source_job_id)
            or basis.route_id != terminal.route_id
            or basis.candidate_id != decision.candidate_id
            or basis.design_problem_ref != decision.design_problem_ref
            or basis.design_problem_basis_ref != decision.design_problem_basis_ref
            or basis.predicate_provenance != "recomputed"
            or basis.reason_codes
        ):
            raise ValueError("candidate_source_model_revision_basis_scope_mismatch")
    for basis in (prospective_basis, selected_basis):
        if (
            basis.action_job_id != terminal.job_id
            or basis.action_generation != terminal.action_generation
            or basis.source_candidate_content_hash != decision.source_candidate_content_hash
        ):
            raise ValueError("candidate_source_model_revision_action_scope_mismatch")
    histories = getattr(prior_closure, "candidate_terminal_history", None)
    if (
        type(histories) is not tuple
        or not histories
        or any(type(item) is not CandidateEvaluationTerminalHistory for item in histories)
    ):
        raise ValueError("candidate_source_model_revision_frontier_not_established")
    latest = histories[-1]
    if (
        not _candidate_ref_same(latest.terminal.selected_basis_ref, decision.prior_basis_ref)
        or not _candidate_model_values_same(latest.selected_basis, previous_basis)
        or not _candidate_model_values_same(latest.evaluation, prior)
        or not _candidate_model_values_same(
            latest.terminal.selected_evaluation, decision.prior_evaluation
        )
        or latest.frontier.frontier_ref != decision.expected_frontier_ref
        or latest.frontier.revision != decision.expected_frontier_revision
        or latest.frontier.basis_ref != str(decision.prior_basis_ref.artifact_id)
        or latest.frontier.basis_content_hash != previous_basis.content_hash
        or latest.frontier.selected_evaluation_witness_ref
        != str(prior.selected.n5_execution_ref.artifact_id)
        or latest.frontier.selected_evaluation_content_hash != prior.execution.content_hash
    ):
        raise ValueError("candidate_source_model_revision_frontier_mismatch")
    inherited_limitations = set(previous_basis.limitations)
    retained = tuple(
        history
        for history in histories
        if history.head.action_generation > previous_receipt.action_generation
    )
    if tuple(history.head.action_generation for history in retained) != tuple(
        range(previous_receipt.action_generation + 1, terminal.action_generation)
    ):
        raise ValueError("candidate_source_model_revision_limitations_not_established")
    for history in retained:
        if (
            history.continuation is None
            or history.terminal.terminal_outcome != "candidate_evaluation_retained"
            or not _candidate_ref_same(
                history.terminal.selected_basis_ref, decision.prior_basis_ref
            )
            or not _candidate_model_values_same(history.selected_basis, previous_basis)
            or not _candidate_model_values_same(history.evaluation, prior)
            or not (inherited_limitations | set(history.current_basis.limitations)).issubset(
                history.continuation.limitations
            )
        ):
            raise ValueError("candidate_source_model_revision_limitations_not_established")
        inherited_limitations.update(history.continuation.limitations)
    if not inherited_limitations.issubset(prospective_basis.limitations):
        raise ValueError("candidate_source_model_revision_limitations_not_established")
    previous_action, _ = _read_historical_action(
        store=artifact_store,
        event_log=event_log,
        action_ref=previous_receipt.candidate_action_ref,
    )
    current_action, _ = _read_historical_action(
        store=artifact_store, event_log=event_log, action_ref=terminal.candidate_action_ref
    )
    from polisyos.core.artifacts import load_core_json_artifact

    # The re-entry history verifier above has already checked the exact
    # selected intent/checkpoint profiles, owner events and their parent links.
    # Reopen those same selected views to bind every prospective basis input.
    intent = CandidateAcquisitionWorldIntent.model_validate(
        load_core_json_artifact(artifact_store, reentry.candidate_world_intent_ref)
    )
    checkpoint = CandidateAcquisitionWorldCheckpoint.model_validate(
        load_core_json_artifact(artifact_store, reentry.candidate_world_checkpoint_ref)
    )
    inputs = prospective_basis.preparation_inputs
    expected_slot = CandidateAcquisitionSourceSlotBinding(
        profile_selection_ref=current_action.profile_selection_ref,
        candidate_digest=current_action.candidate_digest,
        canonical_variable_id=current_action.canonical_variable_id,
        target_slot_id=current_action.target_slot_id,
    )
    if (
        not _candidate_model_values_same(inputs.configured_profile, intent.configured_profile)
        or not _candidate_model_values_same(
            inputs.original_model_declaration, intent.original_model_declaration
        )
        or inputs.transaction_time != intent.transaction_time
        or not _candidate_ref_same(inputs.base_data_snapshot_ref, checkpoint.base_data_snapshot_ref)
        or not _candidate_ref_same(inputs.base_world_model_ref, predecessors[-1].world_model_ref)
        or not _candidate_ref_same(inputs.candidate_source_ref, current_action.candidate_source_ref)
        or not _candidate_model_values_same(inputs.slot_binding, expected_slot)
    ):
        raise ValueError("candidate_source_model_revision_preparation_owner_mismatch")
    control_service.verify_candidate_source_budget_window_historical(
        closure=prior_closure, action=previous_action
    )
    control_service.verify_candidate_source_budget_window_historical(
        closure=prior_closure, action=current_action
    )
    global_limit = control_service.acquisition_source_global_budget_usd(closure=prior_closure)
    for basis, evaluation, preceding, fresh_limit in (
        (previous_basis, prior, predecessors[:-1], previous_action.selection.reentry_budget_usd),
        (prospective_basis, prior, predecessors, current_action.selection.reentry_budget_usd),
        (selected_basis, selected, predecessors, current_action.selection.reentry_budget_usd),
    ):
        replay_candidate_acquisition_basis_for_history(
            artifact_store=artifact_store,
            problem=prior_closure.design_problem_basis,
            basis=basis,
            predecessors=preceding,
            selected_evaluation=evaluation,
            fresh_limit_usd=fresh_limit,
            global_limit_usd=global_limit,
        )
    if not is_prospective_candidate_model_revision(previous_basis, prospective_basis):
        raise ValueError("candidate_source_model_revision_not_coefficient_only")
    ncms = _read_selected_candidate_coefficient_pair(
        artifact_store=artifact_store,
        previous=_CandidateModelSelection(
            prior.input_record.profile,
            prior.input_record.model_declaration_ref,
            prior.input_record.ncm_ref,
            prior.source.job_id,
        ),
        selected=_CandidateModelSelection(
            selected.input_record.profile,
            selected.input_record.model_declaration_ref,
            selected.input_record.ncm_ref,
            selected.source.job_id,
        ),
        run_id=terminal.run_id,
        tenant_id=terminal.tenant_id,
        cell_id=terminal.cell_id,
    )
    old_witness = _read_completed_candidate_n5_witness(
        artifact_store=artifact_store,
        evaluation=prior,
        run_id=terminal.run_id,
        tenant_id=terminal.tenant_id,
        cell_id=terminal.cell_id,
    )
    new_witness = _read_completed_candidate_n5_witness(
        artifact_store=artifact_store,
        evaluation=selected,
        run_id=terminal.run_id,
        tenant_id=terminal.tenant_id,
        cell_id=terminal.cell_id,
    )
    _require_model_revision_facets(
        previous_basis,
        prospective_basis,
        selected_basis,
        previous_implementation=old_witness.implementation,
        selected_implementation=new_witness.implementation,
        previous_ncm=ncms[0],
        selected_ncm=ncms[1],
    )
    return CandidateModelRevision(
        previous_input_ref=prior.selected.n5_input_ref,
        selected_input_ref=selected.selected.n5_input_ref,
        previous_declaration_ref=prior.input_record.model_declaration_ref,
        selected_declaration_ref=selected.input_record.model_declaration_ref,
        previous_ncm_ref=prior.input_record.ncm_ref,
        selected_ncm_ref=selected.input_record.ncm_ref,
        previous_basis_ref=decision.prior_basis_ref,
        selected_basis_ref=terminal.selected_basis_ref,
    )


def resolve_acquired_outcome_revision(
    **kwargs: Unpack[_CandidateRevisionArguments],
) -> AcquiredOutcomeRevision:
    """Replay an acquired outcome-baseline change through existing owners."""

    result = _resolve_candidate_revision(**kwargs, transition_kind="acquired_outcome_revision")
    if type(result) is not AcquiredOutcomeRevision:
        raise RuntimeError("acquired_outcome_revision_result_untyped")
    return result
