"""Native action context adapter for the existing Generic generation route.

The original configured profile remains configuration evidence. An acquired
candidate world, the current action lease, and a freshly generated N4 source
have separate identities. This module never manufactures an NL worker scope,
changes the configured profile map, fetches data, or invokes a numerical kernel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.core import artifacts
from polisyos.pdc import gy_content_hash

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.registry import RegistryBundleContent
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedAcquisitionRouteClosure
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
        NativeDerivedWorldSelection,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContext,
        CycleSubstrateContextArtifactOwner,
    )
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleNativeWorldContextHandoffV1,
        GenericCycleSimulationAdmissionOwner,
        GenericCycleSimulationN5InputV1,
        GenericCycleSimulationProfileV1,
    )


@dataclass(frozen=True)
class NativeSelectedProgramGraphLinkage:
    """Expose original configuration and separately replayed Native graph inputs."""

    handoff: GenericCycleNativeWorldContextHandoffV1
    compile_report_ref: artifacts.ArtifactRef
    registry_bundle_ref: artifacts.ArtifactRef
    registry_bundle_content: RegistryBundleContent
    compiled_singleton: bool

    @property
    def profile(self) -> GenericCycleSimulationProfileV1:
        """Return unchanged original configuration, never a projected artifact."""
        return self.handoff.profile

    @property
    def profile_ref(self) -> artifacts.ArtifactRef:
        """Return the exact original selected configuration view."""
        return self.handoff.profile_ref

    @property
    def context(self) -> CycleSubstrateContext:
        """Return the action-owned context, including its candidate limitations."""
        return self.handoff.context

    @property
    def context_job_ref(self) -> artifacts.ArtifactRef:
        """Return the actual acquisition-job context selector."""
        return self.handoff.context_job_ref

    @property
    def native_world_checkpoint_ref(self) -> artifacts.ArtifactRef:
        """Return the selected checkpoint independently replayed by this owner."""
        return self.handoff.native_world_checkpoint_ref

    @property
    def original_generic_input_ref(self) -> artifacts.ArtifactRef:
        """Return the genuine blocked Generic input from the original cycle."""
        return self.handoff.original_generic_input_ref

    @property
    def current_profile_selection_ref(self) -> str:
        """Return the current problem key independently of original configuration."""
        return self.handoff.current_profile_selection_ref


def _error(code: str) -> Exception:
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextOwnerError

    return CycleSubstrateContextOwnerError(code)


def _same_ref(left: artifacts.ArtifactRef, right: artifacts.ArtifactRef) -> bool:
    return artifacts.artifact_ref_identity_key(left) == artifacts.artifact_ref_identity_key(right)


def bind_native_world_history(
    owner: GenericCycleSimulationAdmissionOwner, *, control_store: object, event_log: object
) -> None:
    """Bind the existing immutable action-history backend, without current rights."""
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog

    if (
        type(event_log) is not RuntimeDiagnosticEventLog
        or event_log.artifact_store is not owner.store
        or event_log._store is not control_store
        or not callable(getattr(control_store, "get_acquisition_action_head_by_receipt", None))
    ):
        raise _error("generic_native_world_history_owner_mismatch")
    if owner._native_action_control_store is not None and (
        owner._native_action_control_store is not control_store
        or owner._native_action_event_log is not event_log
    ):
        raise _error("generic_native_world_history_owner_already_bound")
    owner._native_action_control_store = control_store
    owner._native_action_event_log = event_log


def bind_native_world_action_owner(
    owner: GenericCycleSimulationAdmissionOwner, service: object
) -> None:
    """Bind the actual Runtime Control owner, never a caller-supplied permission."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService

    if (
        type(service) is not ControlPlaneService
        or service._artifact_store is not owner.store
        or service._generic_cycle_simulation_admission_owner is not owner
    ):
        raise _error("generic_native_world_action_owner_mismatch")
    if (
        owner._native_world_action_owner is not None
        and owner._native_world_action_owner is not service
    ):
        raise _error("generic_native_world_action_owner_already_bound")
    bind_native_world_history(
        owner, control_store=service._control_store, event_log=service._diagnostic_event_log
    )
    owner._native_world_action_owner = service


def _recorded_selection(
    owner: GenericCycleSimulationAdmissionOwner, checkpoint_ref: artifacts.ArtifactRef
) -> NativeDerivedWorldSelection:
    from polisyos.runtime.quality.acquisition_world_growth import (
        replay_native_derived_world_selection,
    )

    if owner._native_action_control_store is None or owner._native_action_event_log is None:
        raise _error("generic_native_world_history_owner_unavailable")
    return replay_native_derived_world_selection(
        owner.store,
        control_store=owner._native_action_control_store,
        event_log=owner._native_action_event_log,
        checkpoint_ref=checkpoint_ref,
    )


def _current_bridge(owner: GenericCycleSimulationAdmissionOwner) -> AcquisitionWorldGrowthBridge:
    from polisyos.runtime.http.services.acquisition_action_service import AcquisitionActionService
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge

    service = owner._native_world_action_owner
    if (
        type(service) is not ControlPlaneService
        or service._generic_cycle_simulation_admission_owner is not owner
        or service._artifact_store is not owner.store
    ):
        raise _error("generic_native_world_action_owner_unavailable")
    action = getattr(service._acquisition_job_handler, "__self__", None)
    if type(action) is not AcquisitionActionService or action.control_service is not service:
        raise _error("generic_native_world_action_handler_not_canonical")
    port = action._production_execution_port
    if type(port) is not WorldBankWDIAcquisitionExecutionPort or action._execution_port is not port:
        raise _error("generic_native_world_execution_port_not_canonical")
    bridge = port._world_growth_bridge
    if (
        type(bridge) is not AcquisitionWorldGrowthBridge
        or bridge._source_control_service is not service
        or bridge.artifact_store is not owner.store
        or bridge.control_store is not service._control_store
        or bridge.event_log is not service._diagnostic_event_log
        or bridge.action_head_sink is not service.acquisition_route_sink
    ):
        raise _error("generic_native_world_bridge_owner_mismatch")
    return bridge


def _current_selection(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    checkpoint_ref: artifacts.ArtifactRef,
    problem: DesignProblem,
    expected_bridge: AcquisitionWorldGrowthBridge | None = None,
    expected_closure: VerifiedAcquisitionRouteClosure | None = None,
) -> NativeDerivedWorldSelection:
    bridge = _current_bridge(owner)
    if expected_bridge is not None and bridge is not expected_bridge:
        raise _error("generic_native_world_bridge_owner_mismatch")
    return bridge.resolve_native_derived_world_selection(
        checkpoint_ref,
        problem=problem,
        expected_closure=expected_closure,
    )


def _context(
    selection: NativeDerivedWorldSelection, problem: DesignProblem
) -> CycleSubstrateContext:
    from polisyos.runtime.quality.cycle_substrate import (
        build_cycle_substrate_context,
        cycle_job_design_problem_ref,
        revalidate_cycle_substrate_context,
    )

    if selection.problem.model_dump(mode="python") != problem.model_dump(mode="python"):
        raise _error("generic_native_world_source_problem_mismatch")
    inputs = selection.original_profile.context_inputs
    if inputs.candidate_levers or inputs.transport_context is not None:
        raise _error("generic_native_world_context_evidence_reissue_required")
    context = build_cycle_substrate_context(
        design_problem_ref=cycle_job_design_problem_ref(problem),
        domain=problem.domain,
        substrate_registry=inputs.substrate_registry,
        selected_registry_entry_hashes=inputs.selected_registry_entry_hashes,
        world_model_record=selection.world_model_record,
        intervention_substrate=inputs.intervention_substrate,
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=inputs.source_pack_content_hash,
        substrate_input_content_hash=inputs.substrate_input_content_hash,
        additional_authority_denials=("native_derived_model_input_candidate_only",),
    )
    return revalidate_cycle_substrate_context(context)


def _handoff_matches_selection(
    handoff: GenericCycleNativeWorldContextHandoffV1, selection: NativeDerivedWorldSelection
) -> bool:
    checkpoint = selection.checkpoint
    return (
        _same_ref(handoff.native_world_checkpoint_ref, selection.checkpoint_ref)
        and _same_ref(handoff.original_generic_input_ref, selection.original_generic_input_ref)
        and handoff.profile == selection.original_profile
        and _same_ref(handoff.profile_ref, selection.original_profile_ref)
        and (
            handoff.job_id,
            handoff.run_id,
            handoff.tenant_id,
            handoff.cell_id,
            handoff.source_job_id,
        )
        == (
            checkpoint.action_job_id,
            checkpoint.run_id,
            checkpoint.tenant_id,
            checkpoint.cell_id,
            checkpoint.source_job_id,
        )
    )


def admit_native_world_context(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    checkpoint_ref: artifacts.ArtifactRef,
    problem: DesignProblem,
    repo_root: Path | None,
) -> GenericCycleNativeWorldContextHandoffV1:
    """Persist an actual acquisition-job context using its existing owner."""
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleNativeWorldContextHandoffV1,
    )

    selection = _current_selection(owner, checkpoint_ref=checkpoint_ref, problem=problem)
    context = _context(selection, problem)
    service = owner._native_world_action_owner
    context_owner = CycleSubstrateContextArtifactOwner(
        store=owner.store, control_store=service._control_store
    )
    context_ref = context_owner.persist_for_current_job(
        context, problem=problem, repo_root=repo_root, return_selected_profile=True
    )
    handoff = GenericCycleNativeWorldContextHandoffV1(
        context=context,
        context_job_ref=context_ref,
        profile=selection.original_profile,
        profile_ref=selection.original_profile_ref,
        native_world_checkpoint_ref=selection.checkpoint_ref,
        original_generic_input_ref=selection.original_generic_input_ref,
        current_profile_selection_ref=cycle_job_profile_selection_ref(problem),
        source_job_id=selection.checkpoint.source_job_id,
        job_id=selection.checkpoint.action_job_id,
        run_id=selection.checkpoint.run_id,
        tenant_id=selection.checkpoint.tenant_id,
        cell_id=selection.checkpoint.cell_id,
    )
    return resolve_native_world_handoff(
        owner, handoff=handoff, problem=problem, context_owner=context_owner, repo_root=repo_root
    )


def resolve_native_world_handoff(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    handoff: GenericCycleNativeWorldContextHandoffV1,
    problem: DesignProblem,
    context_owner: CycleSubstrateContextArtifactOwner | None,
    repo_root: Path | None,
) -> GenericCycleNativeWorldContextHandoffV1:
    """Recheck current ownership separately from the saved original profile."""
    _resolve_native_world_handoff_selection(
        owner,
        handoff=handoff,
        problem=problem,
        context_owner=context_owner,
        repo_root=repo_root,
    )
    return handoff


def _resolve_native_world_handoff_selection(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    handoff: GenericCycleNativeWorldContextHandoffV1,
    problem: DesignProblem,
    context_owner: CycleSubstrateContextArtifactOwner | None = None,
    repo_root: Path | None = None,
    expected_bridge: AcquisitionWorldGrowthBridge | None = None,
    expected_closure: VerifiedAcquisitionRouteClosure | None = None,
) -> NativeDerivedWorldSelection:
    """Return the verified selection to a caller in the same live read."""
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleNativeWorldContextHandoffV1,
    )

    if type(handoff) is not GenericCycleNativeWorldContextHandoffV1:
        raise _error("generic_native_world_handoff_untyped")
    selection = _current_selection(
        owner,
        checkpoint_ref=handoff.native_world_checkpoint_ref,
        problem=problem,
        expected_bridge=expected_bridge,
        expected_closure=expected_closure,
    )
    service = owner._native_world_action_owner
    if context_owner is None:
        context_owner = CycleSubstrateContextArtifactOwner(
            store=owner.store, control_store=service._control_store
        )
    if (
        type(context_owner) is not CycleSubstrateContextArtifactOwner
        or context_owner._store is not owner.store
        or context_owner._control_store is not service._control_store
        or not _handoff_matches_selection(handoff, selection)
        or handoff.current_profile_selection_ref != cycle_job_profile_selection_ref(problem)
        or handoff.context != _context(selection, problem)
    ):
        raise _error("generic_native_world_handoff_binding_mismatch")
    resolved = context_owner.resolve_for_current_job(
        handoff.context_job_ref, problem=problem, repo_root=repo_root
    )
    if resolved.context != handoff.context or (
        resolved.job_id,
        resolved.run_id,
        resolved.tenant_id,
        resolved.cell_id,
    ) != (handoff.job_id, handoff.run_id, handoff.tenant_id, handoff.cell_id):
        raise _error("generic_native_world_context_current_readback_mismatch")
    return selection


def _selected_graph_for_handoff(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    handoff: GenericCycleNativeWorldContextHandoffV1,
    selection: NativeDerivedWorldSelection,
    problem: DesignProblem,
) -> NativeSelectedProgramGraphLinkage:
    """Reuse the complete compiler law after separately proving Native context."""
    effective = _effective_profile(selection, handoff.current_profile_selection_ref)
    # The ordinary graph owner checks its own context/profile law. Native's
    # actual context has additional candidate denials; it was independently
    # reproduced above and must not weaken the ordinary equality predicate.
    graph_context = owner.context_for_profile(effective, problem)
    selected = owner._load_selected_program_graph_linkage(
        profile_ref=handoff.profile_ref,
        profile=effective,
        context=graph_context,
        problem=problem,
    )
    return NativeSelectedProgramGraphLinkage(
        handoff=handoff,
        compile_report_ref=selected.compile_report_ref,
        registry_bundle_ref=selected.registry_bundle_ref,
        registry_bundle_content=selected.registry_bundle_content,
        compiled_singleton=selected.compiled_singleton,
    )


def resolve_native_selected_program_graph_linkage(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    handoff: GenericCycleNativeWorldContextHandoffV1,
    problem: DesignProblem,
    context_owner: CycleSubstrateContextArtifactOwner | None = None,
    repo_root: Path | None = None,
) -> NativeSelectedProgramGraphLinkage:
    """Reopen the unchanged graph under the current Native action's own lease."""
    handoff = resolve_native_world_handoff(
        owner,
        handoff=handoff,
        problem=problem,
        context_owner=context_owner,
        repo_root=repo_root,
    )
    selection = _recorded_selection(owner, handoff.native_world_checkpoint_ref)
    return _selected_graph_for_handoff(owner, handoff=handoff, selection=selection, problem=problem)


def resolve_native_selected_program_graph_linkage_historical(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    checkpoint_ref: artifacts.ArtifactRef,
    context_job_ref: artifacts.ArtifactRef,
    profile_ref: artifacts.ArtifactRef,
    expected_context: CycleSubstrateContext,
    problem: DesignProblem,
    job_id: str,
    run_id: str,
    tenant_id: str,
    cell_id: str,
) -> NativeSelectedProgramGraphLinkage:
    """Reproduce recorded Native inputs from actual action history, without rights."""
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleNativeWorldContextHandoffV1,
    )

    selection = _recorded_selection(owner, checkpoint_ref)
    context_record = CycleSubstrateContextArtifactOwner(
        store=owner.store
    ).resolve_historical_job_artifact(
        context_job_ref,
        problem=problem,
        expected_job_id=job_id,
        expected_run_id=run_id,
        expected_tenant_id=tenant_id,
        expected_cell_id=cell_id,
    )
    context = context_record.context
    if (
        not _same_ref(profile_ref, selection.original_profile_ref)
        or context != expected_context
        or context != _context(selection, problem)
    ):
        raise _error("generic_native_world_historical_context_mismatch")
    handoff = GenericCycleNativeWorldContextHandoffV1(
        context=context,
        context_job_ref=context_job_ref,
        profile=selection.original_profile,
        profile_ref=profile_ref,
        native_world_checkpoint_ref=checkpoint_ref,
        original_generic_input_ref=selection.original_generic_input_ref,
        current_profile_selection_ref=cycle_job_profile_selection_ref(problem),
        source_job_id=selection.checkpoint.source_job_id,
        job_id=job_id,
        run_id=run_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    if not _handoff_matches_selection(handoff, selection):
        raise _error("generic_native_world_historical_scope_mismatch")
    return _selected_graph_for_handoff(owner, handoff=handoff, selection=selection, problem=problem)


def _selection_for_input(
    owner: GenericCycleSimulationAdmissionOwner,
    input_record: GenericCycleSimulationN5InputV1,
    *,
    current: bool = False,
) -> NativeDerivedWorldSelection:
    from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref

    if input_record.native_world_checkpoint_ref is None:
        raise _error("generic_native_world_input_subject_missing")
    selection = _recorded_selection(owner, input_record.native_world_checkpoint_ref)
    if current:
        selection = _current_selection(
            owner,
            checkpoint_ref=input_record.native_world_checkpoint_ref,
            problem=selection.problem,
        )
    checkpoint = selection.checkpoint
    if (
        input_record.schema_version != "policyos.runtime.generic_cycle_simulation_n5_input.v2"
        or input_record.original_generic_input_ref is None
        or not _same_ref(
            input_record.original_generic_input_ref, selection.original_generic_input_ref
        )
        or input_record.profile != selection.original_profile
        or not _same_ref(input_record.profile_ref, selection.original_profile_ref)
        or input_record.native_current_profile_selection_ref
        != cycle_job_profile_selection_ref(selection.problem)
        or (input_record.job_id, input_record.run_id, input_record.tenant_id, input_record.cell_id)
        != (
            checkpoint.action_job_id,
            checkpoint.run_id,
            checkpoint.tenant_id,
            checkpoint.cell_id,
        )
    ):
        raise _error("generic_native_world_input_selection_mismatch")
    return selection


def effective_native_input_profile(
    owner: GenericCycleSimulationAdmissionOwner, input_record: GenericCycleSimulationN5InputV1
) -> GenericCycleSimulationProfileV1:
    """Project only the recorded world/current problem into builder inputs.

    This projection is not adopted configuration. The original profile bytes
    remain in the input, and this projection is reproducible from its separate
    selected checkpoint. No other numerical or operational setting changes.
    """
    selection = _selection_for_input(owner, input_record)
    return _effective_profile(selection, input_record.native_current_profile_selection_ref)


def _effective_profile(
    selection: NativeDerivedWorldSelection, current_profile_selection_ref: str
) -> GenericCycleSimulationProfileV1:
    """Own the one reproducible world/key projection for Native builders."""
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationProfileV1,
    )

    profile = selection.original_profile
    effective = profile.model_copy(
        update={
            "world_model_record_ref": selection.world_model_record_ref,
            "context_inputs": profile.context_inputs.model_copy(
                update={"world_model_record": selection.world_model_record}
            ),
            "profile_selection_ref": current_profile_selection_ref,
        },
        deep=True,
    )
    payload = effective.model_dump(mode="python")
    payload["content_hash"] = gy_content_hash(
        effective.model_dump(mode="json", exclude={"content_hash"})
    )
    return GenericCycleSimulationProfileV1.model_validate(payload)


def require_current_native_input(
    owner: GenericCycleSimulationAdmissionOwner, input_record: GenericCycleSimulationN5InputV1
) -> None:
    """Require the original current adoption and the current acquisition lease."""
    _selection_for_input(owner, input_record, current=True)


def persist_native_n5_input(
    owner: GenericCycleSimulationAdmissionOwner,
    *,
    handoff: GenericCycleNativeWorldContextHandoffV1,
    source_ref: artifacts.ArtifactRef,
    source_run_id: str,
    problem: DesignProblem,
    cycle_index: int,
    candidate_id: str,
    candidate_atom_hash: str,
    outcome_variable: str,
) -> artifacts.ArtifactRef:
    """Bind a fresh actual N4 source to the independently selected action world."""
    from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.generic_simulation_admission import (
        _PROFILE_CANON,
        GenericCycleSimulationN5InputV1,
    )

    handoff = resolve_native_world_handoff(
        owner, handoff=handoff, problem=problem, context_owner=None, repo_root=None
    )
    source = GenerationSourceRepository(owner.store, native_world_owner=owner).load(
        source_ref,
        run_id=source_run_id,
        expected_job_id=handoff.job_id,
        expected_run_id=handoff.run_id,
        expected_tenant_id=handoff.tenant_id,
        expected_cell_id=handoff.cell_id,
        context_job_ref=handoff.context_job_ref,
        profile_ref=handoff.profile_ref,
    )
    if (
        source.problem.model_dump(mode="python") != problem.model_dump(mode="python")
        or source.cycle_substrate_context != handoff.context
        or source.cycle_index != cycle_index
        or len(
            [
                candidate
                for candidate in source.generation_result.candidates
                if getattr(candidate, "candidate_id", None) == candidate_id
                and getattr(getattr(candidate, "atom", None), "content_hash", None)
                == candidate_atom_hash
            ]
        )
        != 1
    ):
        raise _error("generic_native_world_fresh_n4_source_mismatch")
    payload = {
        "schema_version": "policyos.runtime.generic_cycle_simulation_n5_input.v2",
        "authority_purpose": "cycle_input_candidate_only",
        "native_world_checkpoint_ref": handoff.native_world_checkpoint_ref,
        "original_generic_input_ref": handoff.original_generic_input_ref,
        "native_current_profile_selection_ref": handoff.current_profile_selection_ref,
        "job_id": handoff.job_id,
        "run_id": handoff.run_id,
        "source_run_id": source_run_id,
        "tenant_id": handoff.tenant_id,
        "cell_id": handoff.cell_id,
        "design_problem_ref": cycle_job_design_problem_ref(problem),
        "cycle_index": cycle_index,
        "n4_source_ref": source_ref,
        "context_job_ref": handoff.context_job_ref,
        "profile_ref": handoff.profile_ref,
        "profile": handoff.profile,
        "candidate_id": candidate_id,
        "candidate_atom_hash": candidate_atom_hash,
        "outcome_variable": outcome_variable,
        "n5": handoff.profile.n5,
    }
    provisional = GenericCycleSimulationN5InputV1.model_construct(
        **payload, content_hash="sha256:" + "0" * 64
    )
    normalized = provisional.model_dump(mode="json", exclude={"content_hash"})
    record = GenericCycleSimulationN5InputV1.model_validate(
        {**normalized, "content_hash": gy_content_hash(normalized)}
    )
    ref = owner.store.put_json(
        record.model_dump(mode="json"),
        owner._n5_input_write_options(record),
        canon_spec=_PROFILE_CANON,
        return_selected_profile=True,
    )
    owner.resolve_n5_input(ref, expected=record)
    replay_native_n5_input_sources(owner, record)
    return ref


def replay_native_n5_input_sources(
    owner: GenericCycleSimulationAdmissionOwner, input_record: GenericCycleSimulationN5InputV1
) -> tuple[object, object, CycleSubstrateContext, object]:
    """Replay the fresh N4 source and recorded action world, without new rights."""
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.design_generation import ShadowGeneratedCandidate
    from polisyos.runtime.quality.generation_cycle import JointSimulationPort
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleNativeWorldContextHandoffV1,
    )

    selection = _selection_for_input(owner, input_record)
    source = GenerationSourceRepository(owner.store, native_world_owner=owner).load(
        input_record.n4_source_ref,
        run_id=input_record.source_run_id,
        expected_job_id=input_record.job_id,
        expected_run_id=input_record.run_id,
        expected_tenant_id=input_record.tenant_id,
        expected_cell_id=input_record.cell_id,
        context_job_ref=input_record.context_job_ref,
        profile_ref=input_record.profile_ref,
    )
    problem = source.problem
    if (
        problem.model_dump(mode="python") != selection.problem.model_dump(mode="python")
        or cycle_job_design_problem_ref(problem) != input_record.design_problem_ref
        or input_record.native_current_profile_selection_ref
        != cycle_job_profile_selection_ref(problem)
        or source.cycle_index != input_record.cycle_index
    ):
        raise _error("generic_native_world_recorded_problem_mismatch")
    context_record = CycleSubstrateContextArtifactOwner(
        store=owner.store
    ).resolve_historical_job_artifact(
        input_record.context_job_ref,
        problem=problem,
        expected_job_id=input_record.job_id,
        expected_run_id=input_record.run_id,
        expected_tenant_id=input_record.tenant_id,
        expected_cell_id=input_record.cell_id,
    )
    context = context_record.context
    if context != _context(selection, problem) or source.cycle_substrate_context != context:
        raise _error("generic_native_world_recorded_context_mismatch")
    candidates = tuple(
        candidate
        for candidate in source.generation_result.candidates
        if getattr(candidate, "candidate_id", None) == input_record.candidate_id
        and getattr(getattr(candidate, "atom", None), "content_hash", None)
        == input_record.candidate_atom_hash
    )
    if len(candidates) != 1 or type(candidates[0]) is not ShadowGeneratedCandidate:
        raise _error("generic_native_world_recorded_candidate_mismatch")
    handoff = GenericCycleNativeWorldContextHandoffV1(
        context=context,
        context_job_ref=input_record.context_job_ref,
        profile=input_record.profile,
        profile_ref=input_record.profile_ref,
        native_world_checkpoint_ref=input_record.native_world_checkpoint_ref,
        original_generic_input_ref=input_record.original_generic_input_ref,
        current_profile_selection_ref=input_record.native_current_profile_selection_ref,
        source_job_id=selection.checkpoint.source_job_id,
        job_id=input_record.job_id,
        run_id=input_record.run_id,
        tenant_id=input_record.tenant_id,
        cell_id=input_record.cell_id,
    )
    port = JointSimulationPort(
        cycle_substrate_context=context,
        artifact_store=owner.store,
        generic_cycle_simulation_admission_owner=owner,
        generic_cycle_simulation_handoff=handoff,
    )
    return source, candidates[0], context, port
