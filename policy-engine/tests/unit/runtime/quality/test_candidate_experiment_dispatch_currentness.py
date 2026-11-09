"""Keep candidate-experiment reentry bound to its selected phase and live job."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobExecutionAdmission,
    ControlJobRecord,
    ControlPlaneStore,
)
from polisyos.runtime.quality import acquisition_evaluation as evaluation_module
from polisyos.runtime.quality import acquisition_evaluation_dispatch as dispatch
from polisyos.runtime.quality import acquisition_route_loop as route_loop_module
from polisyos.runtime.quality.acquisition_evaluation import (
    AcquisitionSelectedEvaluation,
    ResolvedAcquisitionEvaluation,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentPhaseReceipt,
)
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionCandidateSourceRoute,
    AcquisitionWorldGrowthBridge,
    CandidateExperimentPriorOwner,
)
from polisyos.runtime.quality.candidate_acquisition_action import (
    CANDIDATE_ACTION_KIND,
    CandidateAcquisitionActionReceipt,
)
from polisyos.runtime.quality.candidate_simulation import (
    CandidateSimulationScenarioProfile,
    CandidateSimulationSyntheticModelDeclarationV1,
    candidate_simulation_profile_ref,
)
from polisyos.runtime.quality.cycle_substrate import (
    ConfiguredCandidateSimulationContextAdmissionOwner,
)
from polisyos.runtime.quality.generation_cycle import (
    CandidateSourceBasisTransition,
    CandidateSourceReentryReceipt,
    GenerationCycleRecord,
    GenerationCycleRun,
)
from polisyos.runtime.quality.world_model_record import world_model_artifact_views
from tests.unit.runtime.quality.test_candidate_acquisition_world import (
    _candidate_world_case,
)
from tests.unit.runtime.quality.test_candidate_experiment_current_outcome import _selection_case
from tests.unit.runtime.quality.test_candidate_experiment_terminal_history import (
    _requested_phase,
)
from tests.unit.runtime.quality.test_candidate_source_basis import _inputs


def _hash(digit: str) -> str:
    return "sha256:" + digit * 64


def _selected_ref(kind: str, digit: str, *, profile_digit: str = "f") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=_hash(digit),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=_hash(profile_digit),
    )


def _reentry_receipts() -> tuple[
    AcquisitionCandidateExperimentPhaseReceipt,
    CandidateAcquisitionActionReceipt,
    ArtifactRef,
]:
    action_ref = _selected_ref(CANDIDATE_ACTION_KIND, "5")
    phase_ref = _selected_ref("runtime_quality.acquisition_candidate_experiment_phase_receipt", "6")
    phase_values = _requested_phase().model_dump(mode="python")
    phase_values.update(
        receipt_id="action-a.pending",
        predecessor_receipt_ref=_hash("e"),
        coarse_phase="candidate_input_prepared",
        receipt_phase="candidate_input_reentry_pending",
        recovery_state="reentry_recovery_required",
        owner_receipt_refs=(str(action_ref.artifact_id),),
        candidate_receipt_ref=action_ref,
    )
    phase = AcquisitionCandidateExperimentPhaseReceipt.model_validate(phase_values)
    selection = AcquisitionCandidateSourceRoute(
        tenant_id=phase.tenant_id,
        cell_id=phase.cell_id,
        run_id=phase.run_id,
        route_id=phase.route_id,
        design_problem_ref=phase.policy_scope.design_problem_ref,
        compiled_requirement_ref=phase.policy_scope.compiled_requirement_ref,
        requirement_id=phase.policy_scope.requirement_id,
        candidate_digest=phase.policy_scope.candidate_digest,
        profile_selection_ref=_hash("7"),
        canonical_variable_id="global.unemployment_rate",
        target_slot_id="global.unemployment_rate",
        country_code="USA",
        year=2024,
        population="labor",
        reentry_budget_usd=Decimal("1.00"),
    )
    action = CandidateAcquisitionActionReceipt(
        tenant_id=phase.tenant_id,
        cell_id=phase.cell_id,
        run_id=phase.run_id,
        source_job_id=phase.source_job_id,
        action_job_id=phase.job_id,
        action_generation=phase.action_generation,
        action_attempt=1,
        selection=selection,
        candidate_budget_window_id="1" * 64,
        candidate_budget_window_digest="2" * 64,
        route_id=phase.route_id,
        action_phase_ref=str(phase_ref.artifact_id),
        selected_action_phase_ref=phase_ref,
        decision_ref=str(phase.authority_decision_ref.artifact_id),
        route_binding_id="component-binding",
        route_binding={"component_only": True},
        attempt_id="component-attempt",
        compiled_requirement_ref=selection.compiled_requirement_ref,
        requirement_id=selection.requirement_id,
        candidate_digest=selection.candidate_digest,
        profile_selection_ref=selection.profile_selection_ref,
        canonical_variable_id=selection.canonical_variable_id,
        target_slot_id=selection.target_slot_id,
        candidate_source_ref=_selected_ref("runtime.quality.candidate_acquisition_source", "8"),
        compiler_report_ref=phase.policy_scope.compiler_report_ref,
        limitations=("component_only_no_live_effect",),
    )
    return phase, action, phase_ref


def _create_job(
    store: ControlPlaneStore,
    *,
    job_id: str,
    running: bool,
) -> ControlJobRecord | ControlJobExecutionAdmission:
    run_id = "run-a"
    actor = "actor-a"
    payload_ref = _hash("1")
    manifest_ref = _hash("2")
    scope = {
        "schema_version": "polisyos.runtime.control_execution_scope.v1",
        "status": "established",
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "actor_subject": actor,
        "actor_authenticated": True,
        "actor_roles": ["operator"],
    }
    creation_event = {
        "job_id": job_id,
        "run_id": run_id,
        "job_kind": "acquisition",
        "pipeline_id": None,
        "payload_ref": payload_ref,
        "submitted_by": actor,
        "requested_execution_profile": None,
        "effective_execution_profile": "dev",
        "policy_flags": {},
        "capability_manifest_ref": manifest_ref,
        "execution_scope": scope,
    }
    created = store.create_job(
        job_id=job_id,
        kind="acquisition",
        run_id=run_id,
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=manifest_ref,
        payload_ref=payload_ref,
        submitted_by=actor,
        creation_event_payload=creation_event,
    )
    if not running:
        return created

    worker_id = f"worker-{job_id}"
    store.mark_running(job_id=job_id, worker_id=worker_id, lease_seconds=120)
    leased = store.get_job(job_id)
    assert leased is not None and leased.state == "running"
    with store.job_execution_fence(
        job_id=job_id,
        worker_id=worker_id,
        attempt=leased.attempt,
    ):
        admission = store.current_execution_job_admission()
    return admission


def _selected_evaluation(
    *, changed: dict[str, object] | None = None
) -> ResolvedAcquisitionEvaluation:
    values: dict[str, object] = {
        "candidate_id": "candidate-a",
        "candidate_content_hash": _hash("1"),
        "design_problem_ref": _hash("2"),
        "world_model_record_hash": _hash("3"),
        "evaluation_job_id": "evaluation-a",
        "evaluation_run_id": "run-a",
        "generation_run_id": "generation-a",
        "cycle_index": 0,
        "n4_source_ref": _selected_ref("runtime.quality.n4_candidate_scenario_source", "4"),
        "context_job_ref": _selected_ref("runtime.quality.cycle_substrate_context_job", "5"),
        "n5_input_ref": _selected_ref("runtime.quality.candidate_simulation_n5_input", "6"),
        "n5_execution_ref": _selected_ref("runtime.quality.candidate_simulation_execution", "7"),
        "n5_result_ref": _selected_ref("polisyos.runtime.joint_simulation_result", "8"),
    }
    if changed is not None:
        values.update(changed)
    selected = AcquisitionSelectedEvaluation.model_validate(values)
    return ResolvedAcquisitionEvaluation(
        selected=selected,
        source=None,
        input_record=None,
        execution=None,
        result=None,
        handoff=None,
    )


def _profile_with_n5_seed(
    profile: CandidateSimulationScenarioProfile,
    *,
    seed: int,
) -> CandidateSimulationScenarioProfile:
    values = profile.model_dump(mode="json", exclude={"content_hash"})
    values["n5"]["seed"] = seed
    return CandidateSimulationScenarioProfile.model_validate(
        {**values, "content_hash": gy_content_hash(values)}
    )


def _declaration_for_profile(
    declaration: CandidateSimulationSyntheticModelDeclarationV1,
    profile: CandidateSimulationScenarioProfile,
    *,
    outcome_per_target_unit: float | None = None,
) -> CandidateSimulationSyntheticModelDeclarationV1:
    values = declaration.model_dump(mode="json", exclude={"content_hash"})
    values.update(
        profile_config_ref=candidate_simulation_profile_ref(profile),
        profile_content_hash=profile.content_hash,
        profile_selection_ref=profile.profile_selection_ref,
    )
    if outcome_per_target_unit is not None:
        values["outcome_per_target_unit"] = outcome_per_target_unit
    return CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        {**values, "content_hash": gy_content_hash(values)}
    )


def _prior_owner(
    *,
    profile: CandidateSimulationScenarioProfile,
    declaration: CandidateSimulationSyntheticModelDeclarationV1,
    store: FileSystemCAS,
    evaluation: ResolvedAcquisitionEvaluation,
) -> CandidateExperimentPriorOwner:
    context_owner = ConfiguredCandidateSimulationContextAdmissionOwner(
        profiles=(profile,),
        model_declarations=(declaration,),
        store=store,
    )
    return CandidateExperimentPriorOwner(
        profile=profile,
        model_declaration=declaration,
        context_owner=context_owner,
        generation_run=None,
        source_cycle=None,
        selected_evaluation=evaluation,
        first_n4_source=None,
    )


def test_prior_receiver_distinguishes_base_and_selected_scenario_worlds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the receiver join; upstream history and recipe are unit adapters.

    The controlled base is a real CAS world. Constructed transition wrappers and
    selected source adapters do not assert source custody or N5 execution.
    """
    world = _candidate_world_case(tmp_path / "world", monkeypatch)
    inputs = _inputs(world)
    profile, declaration = inputs.configured_profile, inputs.original_model_declaration
    owner = ConfiguredCandidateSimulationContextAdmissionOwner(
        profiles=(profile,), model_declarations=(declaration,), store=world.store
    )
    scenario_hash = _hash("3")
    assert scenario_hash != world.base.record.content_hash
    selected = _selected_evaluation(changed={"world_model_record_hash": scenario_hash}).selected
    origin, _ = _selection_case(2)
    scope = origin.policy_scope.model_copy(
        update={
            "candidate_id": selected.candidate_id,
            "candidate_content_hash": selected.candidate_content_hash,
        }
    )
    cycle = GenerationCycleRecord.model_construct(
        cycle_index=1,
        design_problem_ref=scope.design_problem_ref,
        design_problem_basis_ref=scope.design_problem_basis_ref,
        selected_candidate_ref=selected.candidate_id,
        selected_candidate_content_hash=selected.candidate_content_hash,
        terminal_kind="acquisition_required",
        simulation=SimpleNamespace(candidate_simulation_n5_input_ref=selected.n5_input_ref),
    )
    edge = CandidateSourceBasisTransition.model_construct()
    run = GenerationCycleRun.model_construct(cycles=(cycle,), basis_transitions=(edge,))
    transition = CandidateSourceReentryReceipt.model_construct(
        continued_generation_run=run,
        new_cycle=cycle,
        basis_transition=edge,
        action_job_id="component-action-b",
        n5_input_ref=selected.n5_input_ref,
        n5_execution_ref=selected.n5_execution_ref,
        n5_result_ref=selected.n5_result_ref,
        scenario_world_model_content_hash=scenario_hash,
        world_model_content_hash=world.base.record.content_hash,
        world_model_ref=world.base.record_ref,
        data_snapshot_ref=world_model_artifact_views(world.base.record).data_snapshot_ref,
    )
    history = replace(origin.candidate_terminal_history_chain[0], reentry=transition)
    origin = replace(
        origin,
        policy_scope=scope,
        design_problem_basis=world.problem,
        candidate_terminal_history_chain=(history,),
    )
    monkeypatch.setattr(
        route_loop_module, "_candidate_experiment_effective_source", lambda _origin: (run, cycle)
    )
    prior = ResolvedAcquisitionEvaluation(
        selected=selected,
        source=SimpleNamespace(
            job_id=transition.action_job_id,
            problem=world.problem,
            profile=profile,
            model_declaration=declaration,
        ),
        input_record=SimpleNamespace(profile=profile),
        execution=None,
        result=None,
        handoff=SimpleNamespace(model_declaration=declaration),
    )
    monkeypatch.setattr(
        evaluation_module, "resolve_selected_acquisition_evaluation_parts", lambda **_: prior
    )
    monkeypatch.setattr(
        ConfiguredCandidateSimulationContextAdmissionOwner,
        "prepare_context_for_acquired_world",
        lambda *_args, **_kwargs: SimpleNamespace(profile=profile, model_declaration=declaration),
    )
    bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
    bridge.artifact_store = world.store
    bridge.control_store = object()
    bridge.cycle_substrate_context_admission_owner = owner
    bridge._source_control_service = None
    selection = AcquisitionCandidateSourceRoute.model_construct(
        profile_selection_ref=profile.profile_selection_ref
    )

    def attempt(receipt: CandidateSourceReentryReceipt, expected: str) -> None:
        current_history = replace(history, reentry=receipt)
        current_origin = replace(origin, candidate_terminal_history_chain=(current_history,))
        with pytest.raises(ValueError, match=expected):
            bridge._candidate_experiment_prior_owner(origin=current_origin, selection=selection)

    # Reaching the absent budget owner proves the preceding receiver join passed;
    # this deliberately does not assert downstream permission or authority.
    attempt(transition, "candidate_experiment_prior_budget_owner_missing")
    attempt(
        transition.model_copy(
            update={"scenario_world_model_content_hash": world.base.record.content_hash}
        ),
        "candidate_experiment_prior_transition_not_latest",
    )
    attempt(
        transition.model_copy(update={"world_model_content_hash": scenario_hash}),
        "candidate_experiment_prior_world_selection_mismatch",
    )
    foreign_input = selected.n5_input_ref.model_copy(update={"manifest_profile_sha256": _hash("e")})
    attempt(
        transition.model_copy(update={"n5_input_ref": foreign_input}),
        "candidate_experiment_prior_transition_not_latest",
    )


def test_reentry_action_matches_selected_phase_generation_and_real_live_job(
    tmp_path: Path,
) -> None:
    """Use the phase generation; ControlJobRecord has no action_generation field."""
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    try:
        live_admission = _create_job(store, job_id="action-a", running=True)
        assert type(live_admission) is ControlJobExecutionAdmission
        job = live_admission.job
        assert type(job) is ControlJobRecord
        assert not hasattr(job, "action_generation")

        phase, action, phase_ref = _reentry_receipts()
        assert dispatch._candidate_experiment_reentry_execution_matches(
            action=action,
            phase=phase,
            job=job,
            selected_action_phase_ref=str(phase_ref.artifact_id),
        )

        action_at_other_generation = CandidateAcquisitionActionReceipt.model_validate(
            {**action.model_dump(mode="python"), "action_generation": 2}
        )
        phase_at_other_generation = AcquisitionCandidateExperimentPhaseReceipt.model_validate(
            {**phase.model_dump(mode="python"), "action_generation": 2}
        )
        phase_for_other_job = AcquisitionCandidateExperimentPhaseReceipt.model_validate(
            {**phase.model_dump(mode="python"), "job_id": "action-other"}
        )
        assert not dispatch._candidate_experiment_reentry_execution_matches(
            action=action_at_other_generation,
            phase=phase,
            job=job,
            selected_action_phase_ref=str(phase_ref.artifact_id),
        )
        assert not dispatch._candidate_experiment_reentry_execution_matches(
            action=action,
            phase=phase_at_other_generation,
            job=job,
            selected_action_phase_ref=str(phase_ref.artifact_id),
        )
        assert not dispatch._candidate_experiment_reentry_execution_matches(
            action=action,
            phase=phase,
            job=job,
            selected_action_phase_ref=_hash("9"),
        )
        assert not dispatch._candidate_experiment_reentry_execution_matches(
            action=action,
            phase=phase_for_other_job,
            job=job,
            selected_action_phase_ref=str(phase_ref.artifact_id),
        )

        pending_job = _create_job(store, job_id="action-pending", running=False)
        assert type(pending_job) is ControlJobRecord and pending_job.state == "pending"
        assert not dispatch._candidate_experiment_reentry_execution_matches(
            action=action,
            phase=phase,
            job=pending_job,
            selected_action_phase_ref=str(phase_ref.artifact_id),
        )

        foreign_admission = _create_job(store, job_id="action-foreign", running=True)
        assert type(foreign_admission) is ControlJobExecutionAdmission
        assert not dispatch._candidate_experiment_reentry_execution_matches(
            action=action,
            phase=phase,
            job=foreign_admission.job,
            selected_action_phase_ref=str(phase_ref.artifact_id),
        )
    finally:
        store.close()


def test_prior_owner_comparison_uses_selected_values_and_store_not_wrapper_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Check fieldwise replay equality only; fixtures do not establish authority."""
    world = _candidate_world_case(tmp_path / "world", monkeypatch)
    inputs = _inputs(world)
    profile = inputs.configured_profile
    declaration = inputs.original_model_declaration
    evaluation = _selected_evaluation()
    expected = _prior_owner(
        profile=profile,
        declaration=declaration,
        store=world.store,
        evaluation=evaluation,
    )
    fresh = _prior_owner(
        profile=profile,
        declaration=declaration,
        store=world.store,
        evaluation=_selected_evaluation(),
    )

    assert fresh.context_owner is not expected.context_owner
    assert dispatch._candidate_experiment_prior_owners_match(
        current=fresh,
        expected=expected,
        artifact_store=world.store,
    )

    wrong_store = FileSystemCAS(tmp_path / "foreign-cas")
    assert not dispatch._candidate_experiment_prior_owners_match(
        current=_prior_owner(
            profile=profile,
            declaration=declaration,
            store=wrong_store,
            evaluation=evaluation,
        ),
        expected=expected,
        artifact_store=world.store,
    )
    wrong_profile = _profile_with_n5_seed(profile, seed=profile.n5.seed + 1)
    wrong_profile_declaration = _declaration_for_profile(declaration, wrong_profile)
    assert not dispatch._candidate_experiment_prior_owners_match(
        current=_prior_owner(
            profile=wrong_profile,
            declaration=wrong_profile_declaration,
            store=world.store,
            evaluation=evaluation,
        ),
        expected=expected,
        artifact_store=world.store,
    )
    wrong_declaration = _declaration_for_profile(
        declaration,
        profile,
        outcome_per_target_unit=declaration.outcome_per_target_unit + 0.5,
    )
    assert not dispatch._candidate_experiment_prior_owners_match(
        current=_prior_owner(
            profile=profile,
            declaration=wrong_declaration,
            store=world.store,
            evaluation=evaluation,
        ),
        expected=expected,
        artifact_store=world.store,
    )

    selected = evaluation.selected
    wrong_n5_input_ref = ArtifactRef(
        artifact_id=selected.n5_input_ref.artifact_id,
        kind=selected.n5_input_ref.kind,
        media_type=selected.n5_input_ref.media_type,
        manifest_profile_sha256=_hash("e"),
    )
    wrong_selected_profile = AcquisitionSelectedEvaluation.model_validate(
        {
            **selected.model_dump(mode="python"),
            "n5_input_ref": wrong_n5_input_ref,
        }
    )
    wrong_selected_evaluation = replace(evaluation, selected=wrong_selected_profile)
    assert wrong_selected_profile.n5_input_ref.artifact_id == selected.n5_input_ref.artifact_id
    assert wrong_selected_profile.n5_input_ref.manifest_profile_sha256 != (
        selected.n5_input_ref.manifest_profile_sha256
    )
    assert not dispatch._candidate_experiment_prior_owners_match(
        current=_prior_owner(
            profile=profile,
            declaration=declaration,
            store=world.store,
            evaluation=wrong_selected_evaluation,
        ),
        expected=expected,
        artifact_store=world.store,
    )

    wrong_nested_evaluation = _selected_evaluation(changed={"world_model_record_hash": _hash("9")})
    assert not dispatch._candidate_experiment_prior_owners_match(
        current=_prior_owner(
            profile=profile,
            declaration=declaration,
            store=world.store,
            evaluation=wrong_nested_evaluation,
        ),
        expected=expected,
        artifact_store=world.store,
    )


def test_preflight_rejects_blocked_v2_frontier_before_source_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blocked V2 may preserve the frontier without selecting it as latest basis."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality import candidate_acquisition_action as actions
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceiptV2,
    )
    from tests.unit.runtime.quality.test_acquisition_route_loop import (
        _reuse_effective_source_case,
    )

    origin, _generation_run, _source_cycle, blocked_history, _frontier = (
        _reuse_effective_source_case("candidate_blocked")
    )
    assert type(origin) is route_loop_module.VerifiedCandidateExperimentOrigin
    assert type(blocked_history.terminal) is AcquisitionCandidateExperimentTerminalReceiptV2
    assert blocked_history.terminal.terminal_outcome == "candidate_blocked"
    assert blocked_history.frontier_after is not None
    assert blocked_history.selected_basis is None
    assert blocked_history.evaluation is None

    artifact_store, control_store, sink = object(), object(), object()
    service = object.__new__(ControlPlaneService)
    service._artifact_store = artifact_store
    service._control_store = control_store
    service._acquisition_route_sink = sink
    bridge = object.__new__(AcquisitionWorldGrowthBridge)
    bridge.artifact_store = artifact_store
    bridge.control_store = control_store
    bridge.action_head_sink = sink
    bridge._source_control_service = service
    selection = AcquisitionCandidateSourceRoute.model_construct()

    monkeypatch.setattr(
        dispatch,
        "_candidate_experiment_verified_prior_history",
        lambda **_kwargs: blocked_history,
    )
    monkeypatch.setattr(
        actions,
        "_candidate_experiment_source_selection",
        lambda *_args, **_kwargs: pytest.fail(
            "preflight selected a source despite the latest blocked V2 having no selected basis"
        ),
    )

    with pytest.raises(ValueError, match="candidate_experiment_evaluation_prior_not_selected"):
        dispatch.preflight_candidate_experiment_evaluation(
            bridge=bridge,
            origin=origin,
            selection=selection,
        )
