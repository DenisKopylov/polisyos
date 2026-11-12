"""Candidate-source re-entry refusal and intrinsic-history boundary controls."""

from __future__ import annotations

import hashlib
import json
from contextlib import nullcontext
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import pytest

from polisyos.core import canon
from polisyos.core.artifacts import ArtifactID, ArtifactRef
from polisyos.runtime.quality import generation_cycle as generation_cycle_module
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    CandidateSourceBasisTransition,
    GenerationCycleController,
    GenerationCycleError,
    GenerationCycleRun,
    JointSimulationPort,
    PendingN8ValuePort,
    validate_generation_cycle_run,
    validate_generation_cycle_run_history,
)
from tests._helpers.controlled_candidate_profile import _budget, _CgfGenerationPort, _problem
from tests.unit.runtime.quality.historical_artifacts import historical_generation_cycle_v1


class _AcquisitionRequiredGrounding:
    """Produce a real N6 acquisition terminal for an intrinsic-only history control."""

    def __call__(
        self,
        *,
        candidate: Any,
        problem: Any,
        cycle_index: int,
        generation_result: object | None = None,
    ) -> CandidateGroundingObservation:
        del problem, cycle_index, generation_result
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="grounding_gap",
            grounding_score=0.1,
            issue_codes=("acquire_data:intrinsic_history_fixture",),
            current_valid=False,
        )


def _intrinsic_ref(kind: str, identity: str) -> ArtifactRef:
    """Return a typed fake ref for pair-history tests, never owner evidence."""

    return ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex(identity * 64),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "f" * 64,
    )


def _candidate_reentry_configuration_case(
    monkeypatch: pytest.MonkeyPatch,
    *,
    consumed_configuration: dict[str, Any] | None,
) -> tuple[AcquisitionWorldGrowthBridge, Any, Any, Any, Any]:
    """Build a narrow method case around the typed historical N5 reader."""
    from polisyos.runtime.quality import acquisition_evaluation
    from polisyos.runtime.quality.acquisition_route_loop import (
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )
    from tests.unit.runtime.quality.test_n5_execution_basis import _historical_n5_result

    prepared = prepare_joint_simulation_configuration()
    input_ref = _intrinsic_ref("runtime.quality.candidate_simulation_n5_input", "a")
    execution_ref = _intrinsic_ref("runtime.quality.candidate_simulation_execution", "b")
    result_ref = _intrinsic_ref("polisyos.runtime.joint_simulation_result", "c")
    result, _witness = _historical_n5_result(
        input_ref,
        consumed_configuration=consumed_configuration,
    )
    selected = SimpleNamespace(
        selected=SimpleNamespace(
            n5_input_ref=input_ref,
            n5_execution_ref=execution_ref,
            n5_result_ref=result_ref,
        ),
        result=result,
    )
    monkeypatch.setattr(
        acquisition_evaluation,
        "resolve_selected_acquisition_evaluation_parts",
        lambda **_: selected,
    )

    bridge = object.__new__(AcquisitionWorldGrowthBridge)
    bridge.artifact_store = object()
    bridge.control_store = object()
    origin = object.__new__(VerifiedCandidateExperimentOrigin)
    object.__setattr__(origin, "tenant_id", "tenant-candidate-config")
    object.__setattr__(origin, "cell_id", "cell-candidate-config")
    object.__setattr__(origin, "run_id", "run-candidate-config")
    object.__setattr__(
        origin, "policy_scope", SimpleNamespace(design_problem_ref="sha256:" + "6" * 64)
    )
    receipt = SimpleNamespace(
        continued_generation_run=object(),
        new_cycle=object(),
        n5_input_ref=input_ref,
        n5_execution_ref=execution_ref,
        n5_result_ref=result_ref,
    )
    return bridge, origin, receipt, prepared, selected


def test_candidate_reentry_malformed_v3_never_falls_back_to_legacy_witness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A present invalid V3 marker cannot borrow a valid older witness."""
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )
    from polisyos.runtime.quality.n5_execution_basis import _exact_native_content

    prepared = prepare_joint_simulation_configuration()
    bridge, origin, receipt, prepared, selected = _candidate_reentry_configuration_case(
        monkeypatch, consumed_configuration=_exact_native_content(prepared)
    )
    selected.result.diagnostics["candidate_n5_execution_content_observation"] = {}
    with pytest.raises(ValueError):
        bridge._verify_candidate_reentry_prepared_configuration(
            closure=None,
            origin=origin,
            receipt=receipt,
            prepared_n5_configuration=prepared,
        )


def test_native_port_selection_reuses_controller_without_quota_or_n5(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Planning carries the real selected controller without admitting a call."""
    from polisyos.runtime.quality.generation_cycle import GenerationCycleController
    from polisyos.runtime.quality.joint_simulation_horizon import (
        HorizonSpec,
        JointSimulationHorizonController,
        prepare_joint_simulation_configuration,
    )
    from polisyos.scientist.orchestration.engine import ProducerBudgetObserver
    from tests.unit.runtime.quality.test_joint_simulation_horizon import _request

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("native comparison must not reserve quota or execute N5")

    monkeypatch.setattr(ProducerBudgetObserver, "admit", forbidden)
    monkeypatch.setattr(JointSimulationHorizonController, "run", forbidden)
    bridge = object.__new__(AcquisitionWorldGrowthBridge)
    bridge.repo_root = None
    prepared = prepare_joint_simulation_configuration()
    native = bridge._prepare_candidate_n5_native_context(prepared_configuration=prepared)
    request = _request().model_copy(update={"horizon": HorizonSpec(start=0, end=0, step=1)})
    selected = native.controller._select_engine(request)
    assert selected.decision.decision == "selected"
    controller = GenerationCycleController(
        simulation_port=native.port,
        _prepared_n5_configuration=prepared,
    )
    assert controller._simulation_port is native.port
    assert controller._simulation_port._controller is native.controller
    assert native.budget_observer is None and native.budget_state is None
    assert controller._simulation_port._controller._select_engine(request) == selected


def test_candidate_experiment_reentry_accepts_historical_observation_without_promoting_witness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality import acquisition_evaluation
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )
    from polisyos.runtime.quality.n5_execution_basis import (
        _exact_native_content,
        read_n5_execution_implementation_witness,
    )

    prepared = prepare_joint_simulation_configuration()
    bridge, origin, receipt, prepared, selected = _candidate_reentry_configuration_case(
        monkeypatch,
        consumed_configuration=_exact_native_content(prepared),
    )
    resolution_calls: list[object] = []

    def resolve_selected(**kwargs: object) -> object:
        resolution_calls.append(kwargs)
        return selected

    monkeypatch.setattr(
        acquisition_evaluation,
        "resolve_selected_acquisition_evaluation_parts",
        resolve_selected,
    )

    resolved = bridge._verify_candidate_reentry_prepared_configuration(
        closure=None,
        origin=origin,
        receipt=receipt,
        prepared_n5_configuration=prepared,
    )
    assert resolved is selected
    assert len(resolution_calls) == 1
    witness = read_n5_execution_implementation_witness(
        selected.result,
        input_ref=receipt.n5_input_ref,
    )
    assert witness.predicate_provenance == "not_established"


@pytest.mark.parametrize("reference_field", ["n5_input_ref", "n5_execution_ref", "n5_result_ref"])
def test_candidate_reentry_configuration_refuses_same_bytes_with_wrong_profile(
    monkeypatch: pytest.MonkeyPatch,
    reference_field: str,
) -> None:
    from polisyos.runtime.quality import acquisition_evaluation, n5_execution_basis
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )
    from polisyos.runtime.quality.n5_execution_basis import _exact_native_content

    prepared = prepare_joint_simulation_configuration()
    bridge, origin, receipt, prepared, selected = _candidate_reentry_configuration_case(
        monkeypatch,
        consumed_configuration=_exact_native_content(prepared),
    )
    resolution_calls = 0

    def resolve_selected(**_: object) -> object:
        nonlocal resolution_calls
        resolution_calls += 1
        return selected

    monkeypatch.setattr(
        acquisition_evaluation,
        "resolve_selected_acquisition_evaluation_parts",
        resolve_selected,
    )
    assert (
        bridge._verify_candidate_reentry_prepared_configuration(
            closure=None,
            origin=origin,
            receipt=receipt,
            prepared_n5_configuration=prepared,
        )
        is selected
    )
    assert resolution_calls == 1

    refs = {
        name: getattr(selected.selected, name)
        for name in ("n5_input_ref", "n5_execution_ref", "n5_result_ref")
    }
    correct_ref = refs[reference_field]
    wrong_profile_ref = correct_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "0" * 64}
    )
    assert wrong_profile_ref.artifact_id == correct_ref.artifact_id
    assert wrong_profile_ref.kind == correct_ref.kind
    assert wrong_profile_ref.media_type == correct_ref.media_type
    assert wrong_profile_ref.manifest_profile_sha256 != correct_ref.manifest_profile_sha256
    refs[reference_field] = wrong_profile_ref
    wrong_profile_selection = SimpleNamespace(
        selected=SimpleNamespace(**refs), result=selected.result
    )
    monkeypatch.setattr(
        acquisition_evaluation,
        "resolve_selected_acquisition_evaluation_parts",
        lambda **_: wrong_profile_selection,
    )
    monkeypatch.setattr(
        n5_execution_basis,
        "read_n5_execution_implementation_witness",
        lambda *_args, **_kwargs: pytest.fail("wrong profile reached the N5 witness"),
    )

    with pytest.raises(
        ValueError,
        match=r"^candidate_source_reentry_configuration_witness_mismatch$",
    ):
        bridge._verify_candidate_reentry_prepared_configuration(
            closure=None,
            origin=origin,
            receipt=receipt,
            prepared_n5_configuration=prepared,
        )


def test_costed_closure_reentry_keeps_whole_implementation_witness_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality import acquisition_evaluation
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )
    from polisyos.runtime.quality.n5_execution_basis import _exact_native_content

    prepared = prepare_joint_simulation_configuration()
    bridge, _origin, receipt, prepared, selected = _candidate_reentry_configuration_case(
        monkeypatch,
        consumed_configuration=_exact_native_content(prepared),
    )
    closure = SimpleNamespace(candidate_basis_transitions=(), model_copy=lambda **_: object())
    monkeypatch.setattr(
        acquisition_evaluation,
        "resolve_selected_acquisition_evaluation",
        lambda **_: selected,
    )

    with pytest.raises(ValueError, match=r"^candidate_source_reentry_configuration_not_consumed$"):
        bridge._verify_candidate_reentry_prepared_configuration(
            closure=closure,
            origin=None,
            receipt=receipt,
            prepared_n5_configuration=prepared,
        )


def _reissue_transition(
    transition: CandidateSourceBasisTransition,
    **changes: object,
) -> CandidateSourceBasisTransition:
    """Recompute the edge digest after a test-only structural mutation."""

    payload = transition.model_dump(mode="python", exclude={"content_hash"})
    for field_name in (
        "prior_n4_source_ref",
        "prior_n5_input_ref",
        "prior_context_job_ref",
        "candidate_action_ref",
        "candidate_source_ref",
        "candidate_world_intent_ref",
        "candidate_world_checkpoint_ref",
        "data_snapshot_ref",
        "world_model_ref",
        "context_job_ref",
        "model_declaration_ref",
        "ncm_ref",
        "n4_source_ref",
        "n5_input_ref",
        "n5_execution_ref",
        "n5_result_ref",
    ):
        if payload[field_name] is not None:
            payload[field_name] = ArtifactRef.model_validate(payload[field_name])
    payload.update(changes)
    return CandidateSourceBasisTransition.issue(**payload)


def _intrinsic_v9_history(
    producer_run: GenerationCycleRun,
) -> tuple[GenerationCycleRun, dict[str, object]]:
    """Pair a real N6-produced source cycle with a deliberately fake typed target edge.

    This fixture exercises intrinsic N6 projection and pair semantics only. The
    fake, content-profiled refs do not establish acquisition-owner custody.
    """

    assert len(producer_run.cycles) == 1
    original_source_cycle = producer_run.cycles[0]
    assert original_source_cycle.terminal_kind == "acquisition_required"
    candidate_id = original_source_cycle.selected_candidate_ref
    source_hash = original_source_cycle.selected_candidate_content_hash
    target_hash = "sha256:" + "b" * 64
    assert target_hash != source_hash

    prior_n4_source_ref = _intrinsic_ref("runtime.quality.n4_candidate_scenario_source", "1")
    prior_n5_input_ref = _intrinsic_ref("runtime.quality.candidate_simulation_n5_input", "2")
    prior_context_job_ref = _intrinsic_ref("runtime.quality.cycle_substrate_context_job", "3")
    source_simulation = original_source_cycle.simulation.model_copy(
        update={
            "candidate_simulation_n4_source_ref": prior_n4_source_ref,
            "candidate_simulation_context_job_ref": prior_context_job_ref,
            "candidate_simulation_n5_input_ref": prior_n5_input_ref,
            "candidate_simulation_profile_config_ref": (
                "runtime-config:candidate-simulation/intrinsic-history@sha256:" + "4" * 64
            ),
            "candidate_simulation_profile_selection_ref": "sha256:" + "5" * 64,
            "cycle_substrate_context_job_ref": None,
            "generic_n4_source_ref": None,
            "generic_context_job_ref": None,
            "generic_profile_ref": None,
            "generic_n4_child_profile_family_ref": None,
            "generic_n4_child_profile_set_ref": None,
            "generic_n5_input_ref": None,
            "generic_profile_selection_ref": None,
            "generic_n5_execution_ref": None,
        }
    )
    source_cycle = original_source_cycle.model_copy(update={"simulation": source_simulation})
    target_simulation = source_simulation.model_copy(
        update={
            "status": "simulation_pending_n5",
            "simulation_ref": None,
            "candidate_simulation_n4_source_ref": None,
            "candidate_simulation_context_job_ref": None,
            "candidate_simulation_n5_input_ref": None,
            "candidate_simulation_profile_config_ref": None,
            "candidate_simulation_profile_selection_ref": None,
            "cycle_substrate_context_job_ref": None,
            "generic_n4_source_ref": None,
            "generic_context_job_ref": None,
            "generic_profile_ref": None,
            "generic_n4_child_profile_family_ref": None,
            "generic_n4_child_profile_set_ref": None,
            "generic_n5_input_ref": None,
            "generic_profile_selection_ref": None,
            "generic_n5_execution_ref": None,
            "simulation_result_ref": None,
            "k_world_ref_before": None,
            "k_world_ref_after": None,
            "world_model_record": None,
            "diagnostics": {},
        }
    )
    target_cycle = source_cycle.model_copy(
        update={
            "cycle_index": 1,
            "selected_candidate_content_hash": target_hash,
            "simulation": target_simulation,
            "driven_by_counterexample_ref": None,
            "introduced_grammar_elements": (),
            "revision_driver": "none",
        }
    )
    basis_ref = source_cycle.design_problem_basis_ref or source_cycle.design_problem_ref
    scenario_hash = "sha256:" + "6" * 64
    transition = CandidateSourceBasisTransition.issue(
        tenant_id="tenant:intrinsic-history-control",
        cell_id="cell:intrinsic-history-control",
        run_id=producer_run.run_id,
        action_job_id="job:intrinsic-history-control",
        route_id="sha256:" + "7" * 64,
        from_cycle_index=0,
        to_cycle_index=1,
        source_generation_run_content_hash=(
            generation_cycle_module.generation_cycle_run_content_hash(producer_run)
        ),
        source_candidate_ref=candidate_id,
        source_candidate_content_hash=source_hash,
        target_candidate_content_hash=target_hash,
        design_problem_basis_ref=basis_ref,
        prior_n4_source_ref=prior_n4_source_ref,
        prior_n5_input_ref=prior_n5_input_ref,
        prior_context_job_ref=prior_context_job_ref,
        prior_scenario_world_model_hash=(
            source_simulation.k_world_ref_before or "sha256:" + "8" * 64
        ),
        candidate_action_ref=_intrinsic_ref(
            "runtime_quality.acquisition_candidate_action_receipt", "9"
        ),
        candidate_source_ref=_intrinsic_ref("runtime.quality.candidate_acquisition_source", "a"),
        candidate_world_intent_ref=_intrinsic_ref(
            "runtime_quality.acquisition_candidate_world_intent", "b"
        ),
        candidate_world_checkpoint_ref=_intrinsic_ref(
            "runtime_quality.acquisition_candidate_world_checkpoint", "c"
        ),
        data_snapshot_ref=_intrinsic_ref("fabric.data_snapshot", "d"),
        world_model_ref=_intrinsic_ref("runtime.quality.world_model_record", "e"),
        world_model_content_hash="sha256:" + "1" * 64,
        context_job_ref=_intrinsic_ref("runtime.quality.cycle_substrate_context_job", "2"),
        scenario_world_model_content_hash=scenario_hash,
        model_declaration_ref=_intrinsic_ref(
            "runtime.quality.candidate_simulation_model_declaration", "3"
        ),
        ncm_ref=_intrinsic_ref("ir.ncm_spec", "4"),
        n5_input_ref=None,
        n5_execution_ref=None,
        n5_result_ref=None,
        limitations=("candidate_only", "intrinsic_history_control_not_owner_verified"),
    )

    source_summary = next(
        summary
        for summary in producer_run.candidate_summaries
        if summary.candidate_id == candidate_id
    )
    target_summary = source_summary.model_copy(
        update={
            "content_hash": target_hash,
            "source_content_hash": source_hash,
            "cycle_index": 1,
            "evaluation_attempt": None,
        }
    )
    run = producer_run.model_copy(
        update={
            "schema_version": "policyos.runtime.generation_cycle_controller.v9",
            "cycles": (source_cycle, target_cycle),
            "candidate_summaries": (*producer_run.candidate_summaries, target_summary),
            "basis_transitions": (transition,),
        }
    )
    payload = run.model_dump(mode="json")
    # The payload is validated by its real schema owner before history replay.
    return GenerationCycleRun.model_validate(payload), payload


@pytest.mark.asyncio
async def test_v9_intrinsic_history_binds_adjacent_pair_and_refuses_authority() -> None:
    """Structural history binds the exact pair while leaving owner/currentness unresolved."""

    producer_run = await GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        grounding_port=_AcquisitionRequiredGrounding(),
        value_port=PendingN8ValuePort(),
        authority_scope="contract_testing",
    ).run(_problem("candidate_source_intrinsic_history"), budget_state=_budget(), max_cycles=1)

    typed_run, payload = _intrinsic_v9_history(producer_run)
    assert typed_run.schema_version == "policyos.runtime.generation_cycle_controller.v9"
    assert typed_run.cycles[0].design_problem_ref == typed_run.cycles[1].design_problem_ref
    assert (
        typed_run.cycles[0].design_problem_basis_ref == typed_run.cycles[1].design_problem_basis_ref
    )
    assert typed_run.cycles[0].grammar_elements == typed_run.cycles[1].grammar_elements
    assert typed_run.cycles[1].introduced_grammar_elements == ()
    assert validate_generation_cycle_run_history(payload) == ()

    strict_issue_codes = {issue["code"] for issue in validate_generation_cycle_run(typed_run)}
    assert "candidate_source_basis_transition_owner_not_established" in strict_issue_codes
    with pytest.raises(
        GenerationCycleError,
        match="candidate_source_basis_transition_owner_not_established",
    ):
        generation_cycle_module.eligible_n9_source_for_run(typed_run)


def test_reentry_receiver_uses_effective_run_and_reconciles_persisted_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise both receiver branches through explicitly adapted upstream owners.

    Actual typed N6 continuation hash checks and the receipt serialization are
    retained. Structural edge/summary checks and historical authority replay are
    adapted here; they remain the responsibility of their own owners and the
    served integration scenario. No physical N5 or source authority is claimed.
    """
    from polisyos.core import artifacts
    from polisyos.data_forge import read_api as data_forge_read_api
    from polisyos.runtime.quality import acquisition_evaluation
    from polisyos.runtime.quality import acquisition_route_loop as route_loop
    from polisyos.runtime.quality import acquisition_world_growth as growth
    from polisyos.runtime.quality import candidate_acquisition_action as actions
    from polisyos.runtime.quality import candidate_source_reentry_history as history
    from polisyos.runtime.quality.generation_cycle import (
        CandidateSourceReentryReceipt,
        GenerationCycleRecord,
        SimulationPortObservation,
        generation_cycle_run_content_hash,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )
    from polisyos.runtime.quality.n5_execution_basis import _exact_native_content
    from polisyos.scientist.orchestration.engine import ProducerBudgetObserver
    from tests.unit.runtime.quality.test_candidate_acquisition_world import _candidate_world_case
    from tests.unit.runtime.quality.test_candidate_experiment_current_outcome import _selection_case
    from tests.unit.runtime.quality.test_candidate_experiment_dispatch_currentness import (
        _reentry_receipts,
        _selected_ref,
    )
    from tests.unit.runtime.quality.test_n5_execution_basis import _historical_n5_result

    world = _candidate_world_case(tmp_path / "world", monkeypatch)
    prepared_n5_configuration = prepare_joint_simulation_configuration()
    n5_input_ref = _intrinsic_ref("runtime.quality.candidate_simulation_n5_input", "a")
    n5_execution_ref = _intrinsic_ref("runtime.quality.candidate_simulation_execution", "b")
    n5_result_ref = _intrinsic_ref("polisyos.runtime.joint_simulation_result", "c")
    n5_result, _witness = _historical_n5_result(
        n5_input_ref,
        consumed_configuration=_exact_native_content(prepared_n5_configuration),
    )
    selected_evaluation = SimpleNamespace(
        selected=SimpleNamespace(
            n5_input_ref=n5_input_ref,
            n5_execution_ref=n5_execution_ref,
            n5_result_ref=n5_result_ref,
        ),
        result=n5_result,
    )
    selected_resolution_calls: list[object] = []

    def resolve_selected_evaluation(**kwargs: object) -> object:
        selected_resolution_calls.append(kwargs)
        return selected_evaluation

    monkeypatch.setattr(
        acquisition_evaluation,
        "resolve_selected_acquisition_evaluation_parts",
        resolve_selected_evaluation,
    )
    context_ref = _intrinsic_ref("runtime.quality.cycle_substrate_context_job", "2")
    simulation = SimulationPortObservation(
        candidate_id="candidate-a",
        status="joint_simulated",
        simulation_result_ref=_intrinsic_ref("polisyos.runtime.joint_simulation_result", "4"),
        cycle_substrate_context_job_ref=context_ref,
        candidate_simulation_n4_source_ref=_intrinsic_ref(
            "runtime.quality.n4_candidate_scenario_source", "1"
        ),
        candidate_simulation_context_job_ref=context_ref,
        candidate_simulation_n5_input_ref=_intrinsic_ref(
            "runtime.quality.candidate_simulation_n5_input", "3"
        ),
        candidate_simulation_profile_config_ref="runtime-config:component-control",
        candidate_simulation_profile_selection_ref="sha256:" + "5" * 64,
        k_world_ref_before=world.base.record.content_hash,
        k_world_ref_after=world.base.record.content_hash,
        world_model_record=world.base.record,
    )
    parsed_simulation = SimulationPortObservation.model_validate_json(simulation.model_dump_json())
    assert simulation.world_model_record == world.base.record
    assert parsed_simulation.world_model_record is None
    assert simulation != parsed_simulation
    assert simulation.model_dump(mode="json") == parsed_simulation.model_dump(mode="json")

    problem_ref = "sha256:" + "1" * 64
    basis_ref = "sha256:" + "2" * 64

    def cycle(index: int, observation: SimulationPortObservation) -> GenerationCycleRecord:
        return GenerationCycleRecord.model_construct(
            cycle_index=index,
            design_problem_ref=problem_ref,
            design_problem_basis_ref=basis_ref,
            selected_candidate_ref="candidate-a",
            simulation=observation,
        )

    a = cycle(0, parsed_simulation)
    b = cycle(1, parsed_simulation)
    c = cycle(2, simulation)
    parsed_c = cycle(2, parsed_simulation)
    first_edge = CandidateSourceBasisTransition.model_construct(to_cycle_index=1)
    second_edge = CandidateSourceBasisTransition.model_construct(to_cycle_index=2)
    root = GenerationCycleRun.model_construct(
        run_id="component-run",
        design_problem_ref=problem_ref,
        cycles=(a,),
        basis_transitions=(),
        candidate_summaries=(),
        fronts=None,
    )
    effective = root.model_copy(update={"cycles": (a, b), "basis_transitions": (first_edge,)})
    continued = effective.model_copy(
        update={"cycles": (a, b, c), "basis_transitions": (first_edge, second_edge)}
    )
    parsed_continued = continued.model_copy(update={"cycles": (a, b, parsed_c)})
    receipt = CandidateSourceReentryReceipt.model_construct(
        source_generation_run_id=effective.run_id,
        design_problem_ref=problem_ref,
        design_problem_basis_ref=basis_ref,
        source_cycle_index=1,
        source_candidate_ref="candidate-a",
        source_generation_run_content_hash=generation_cycle_run_content_hash(effective),
        continued_generation_run=continued,
        new_cycle=c,
        basis_transition=second_edge,
        candidate_summaries=(),
        limitations=("component_only",),
        n5_input_ref=n5_input_ref,
        n5_execution_ref=n5_execution_ref,
        n5_result_ref=n5_result_ref,
    )
    parsed_receipt = receipt.model_copy(
        update={"new_cycle": parsed_c, "continued_generation_run": parsed_continued}
    )
    assert receipt != parsed_receipt
    assert receipt.model_dump(mode="json") == parsed_receipt.model_dump(mode="json")
    monkeypatch.setattr(
        generation_cycle_module, "_candidate_source_basis_edge_matches", lambda *_: True
    )
    monkeypatch.setattr(
        generation_cycle_module, "_candidate_source_basis_cycle_summary_matches", lambda **_: True
    )
    monkeypatch.setattr(generation_cycle_module, "_derive_candidate_source_fronts", lambda *_: None)
    # The unmodified canonical validator accepts the effective run and rejects
    # the immutable root even when their run ID and problem are the same.
    generation_cycle_module.validate_candidate_source_continuation(effective, receipt)
    with pytest.raises(GenerationCycleError, match="candidate_source_reentry_history_mismatch"):
        generation_cycle_module.validate_candidate_source_continuation(root, receipt)

    origin, _ = _selection_case(1)
    origin = replace(origin, generation_run=root, source_cycle=a)
    monkeypatch.setattr(
        route_loop, "_candidate_experiment_effective_source", lambda _: (effective, b)
    )
    _, action, _ = _reentry_receipts()
    action_ref = _selected_ref("runtime_quality.acquisition_candidate_action_receipt", "5")
    selected_ref = _selected_ref("runtime_quality.candidate_source_reentry_receipt", "6")
    selection = object()
    monkeypatch.setattr(actions, "read_candidate_experiment_acquisition_action", lambda **_: action)
    monkeypatch.setattr(actions, "_candidate_experiment_source_selection", lambda *_: selection)
    monkeypatch.setattr(
        data_forge_read_api.catalog, "acquisition_overlay_admission_fence", lambda _: nullcontext()
    )
    monkeypatch.setattr(artifacts, "load_core_json_artifact", lambda *_: {"llm_models": ["test"]})
    monkeypatch.setattr(growth, "candidate_source_reentry_inputs", lambda _: ())

    def exercise(
        name: str,
        *,
        recovered: bool,
        produced: CandidateSourceReentryReceipt = receipt,
        readback: CandidateSourceReentryReceipt = parsed_receipt,
        expected_error: str | None = None,
        costed: bool = False,
        prepared_configuration: bool = False,
        checkpoint: Literal["selected", "missing", "corrupt", "foreign_fence"] | None = None,
    ) -> None:
        folder = tmp_path / name
        folder.mkdir()
        calls: list[str] = []
        event = SimpleNamespace(
            event=SimpleNamespace(artifact_refs=(str(selected_ref.artifact_id),))
        )
        bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
        bridge.event_log = SimpleNamespace(list_events=lambda **_: [event] if recovered else [])
        bridge.artifact_store = world.store
        bridge.control_store = object()
        bridge.repo_root = tmp_path
        bridge.promotion_runtime = None
        bridge._paths = lambda _: (folder / "overlay.sqlite", None)
        bridge._sync_directory = lambda _: None
        bridge._write_candidate_world_pointer = lambda *_args, **_kwargs: calls.append("pointer")
        bridge._recover_unique_candidate_owner_view = lambda **kwargs: (
            selected_ref,
            kwargs["verify"](selected_ref),
        )
        bridge._persist_candidate_experiment_receipt = lambda **_: selected_ref
        bridge._reconcile_candidate_experiment_source_reentry_budget = lambda **_: calls.append(
            "reconciled"
        )
        window = SimpleNamespace(
            window_id=action.candidate_budget_window_id,
            record_digest=action.candidate_budget_window_digest,
            effective_limit_usd=Decimal("1"),
            scope=object(),
        )
        bridge.resolve_candidate_experiment_reentry_budget_window = lambda **_: window

        def preflight(**_: object) -> ProducerBudgetObserver:
            calls.append("preflight")
            return ProducerBudgetObserver.__new__(ProducerBudgetObserver)

        bridge.candidate_experiment_source_reentry_preflight = preflight
        bridge.candidate_source_reentry_preflight = preflight
        handoff = SimpleNamespace(context=None, handoff=None, currentness_resolver=lambda: True)
        bridge.candidate_source_context_handoff = lambda **_: handoff
        bridge.verify_candidate_source_context_handoff = lambda **_: handoff
        bridge.candidate_source_selection = lambda _: selection
        bridge._require_selected_candidate_action = lambda **_: action
        if checkpoint is not None:
            action_digest = hashlib.sha256(
                canon.to_canonical_bytes(action_ref.model_dump(mode="json"))
            ).hexdigest()
            fence = folder / (action_digest + ".candidate-source-reentry.started")
            fenced_action = selected_ref if checkpoint == "foreign_fence" else action_ref
            fence.write_text(fenced_action.model_dump_json() + "\n", encoding="utf-8")
            fence_identity = (fence.stat().st_ino, fence.read_bytes())
            pending = SimpleNamespace(budget_window=window)
            handoff.experiment_reentry_budget = SimpleNamespace(
                observer=ProducerBudgetObserver.__new__(ProducerBudgetObserver)
            )
            bridge._resolve_candidate_experiment_reentry_action_context = lambda **_: pending
            bridge._candidate_experiment_n5_checkpoint_control_store = lambda: bridge.control_store

            def locate(**kwargs: object) -> ArtifactRef | None:
                assert kwargs["reentry_context"] is pending
                calls.append("checkpoint_locator")
                if checkpoint == "corrupt":
                    raise ValueError("candidate_reentry_n5_checkpoint_selected_profile_mismatch")
                return context_ref if checkpoint == "selected" else None

            def reopen(**kwargs: object) -> SimpleNamespace:
                assert kwargs["existing_context_ref"] == context_ref
                assert kwargs["reentry_budget_scope"] is window.scope
                calls.append("reopen_world")
                return handoff

            monkeypatch.setattr(
                history, "locate_candidate_source_reentry_n5_checkpoint_context", locate
            )
            bridge._candidate_source_context_handoff = reopen

        class Controller:
            def __init__(self, **_: object) -> None:
                pass

            async def reenter_after_candidate_acquisition_source(self, **kwargs: object) -> object:
                assert kwargs.get("require_n5_checkpoint", False) is (checkpoint == "selected")
                calls.append("producer")
                return produced

        monkeypatch.setattr(growth, "GenerationCycleController", Controller)

        def verify(**_: object) -> CandidateSourceReentryReceipt:
            calls.append("historical_reader")
            return readback

        monkeypatch.setattr(history, "verify_candidate_experiment_source_reentry_history", verify)
        monkeypatch.setattr(history, "verify_candidate_source_reentry_history", verify)
        closure = SimpleNamespace(
            generation_run=effective,
            tenant_id=origin.tenant_id,
            cell_id=origin.cell_id,
            run_id=origin.run_id,
            source_job_id=origin.source_job_id,
            route_id=origin.route_id,
        )
        identity = {"closure": closure} if costed else {"origin": origin}
        if expected_error:
            with pytest.raises((ValueError, GenerationCycleError), match=expected_error):
                bridge._prepare_candidate_source_reentry(
                    **identity, candidate_action_ref=action_ref
                )
            assert "reconciled" not in calls
        else:
            if prepared_configuration:
                resolutions_before = len(selected_resolution_calls)
                assert bridge._prepare_candidate_source_reentry_with_evaluation(
                    **identity,
                    candidate_action_ref=action_ref,
                    prepared_n5_configuration=prepared_n5_configuration,
                ) == (selected_ref, readback, selected_evaluation)
                assert len(selected_resolution_calls) == resolutions_before + 1
            else:
                assert bridge._prepare_candidate_source_reentry(
                    **identity, candidate_action_ref=action_ref
                ) == (selected_ref, readback)
            assert "historical_reader" in calls
            assert "pointer" in calls
            if recovered:
                assert not {"preflight", "producer", "reconciled"}.intersection(calls)
            else:
                assert calls.count("producer") == 1
                assert "reconciled" in calls
        if checkpoint is not None:
            assert (fence.stat().st_ino, fence.read_bytes()) == fence_identity
            assert "preflight" not in calls
            assert ("reopen_world" in calls) is (checkpoint == "selected")
            assert ("producer" in calls) is (checkpoint == "selected")
            assert ("checkpoint_locator" in calls) is (checkpoint != "foreign_fence")

    exercise("recovered", recovered=True)
    exercise("costed-recovered", recovered=True, costed=True)
    exercise("recovered-prepared", recovered=True, prepared_configuration=True)
    exercise("new", recovered=False)
    exercise("new-prepared", recovered=False, prepared_configuration=True)
    exercise("after-n5", recovered=False, checkpoint="selected")
    exercise(
        "unselected-n5",
        recovered=False,
        checkpoint="missing",
        expected_error="candidate_source_reentry_outcome_not_established",
    )
    exercise(
        "corrupt-n5-selection",
        recovered=False,
        checkpoint="corrupt",
        expected_error="candidate_reentry_n5_checkpoint_selected_profile_mismatch",
    )
    exercise(
        "foreign-fence",
        recovered=False,
        checkpoint="foreign_fence",
        expected_error="candidate_source_reentry_fence_identity_mismatch",
    )
    wrong_root = receipt.model_copy(
        update={"source_generation_run_content_hash": generation_cycle_run_content_hash(root)}
    )
    exercise(
        "wrong-root",
        recovered=False,
        produced=wrong_root,
        expected_error="candidate_source_reentry_history_mismatch",
    )
    changed_readback = parsed_receipt.model_copy(update={"limitations": ("changed",)})
    exercise(
        "changed-readback",
        recovered=False,
        readback=changed_readback,
        expected_error="candidate_source_reentry_readback_changed",
    )


@pytest.mark.parametrize(
    ("case", "expected_error"),
    [
        ("positive", None),
        ("standard_exact_cap", "candidate_experiment_reentry_n5_capacity_not_established"),
        ("missing_profile", "candidate_experiment_reentry_n5_capacity_not_established"),
        ("wrong_profile_digest", "candidate_experiment_reentry_n5_capacity_not_established"),
        ("usd_exact_cap", "candidate_experiment_reentry_budget_exhausted"),
        ("changed_budget_state", "control_nl_budget_run_limit_changed"),
    ],
)
def test_candidate_experiment_reentry_preflight_uses_real_budget_and_quota_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    expected_error: str | None,
) -> None:
    """Adapt source/action reconciliation only; keep ledger, USD, and quota reads real."""
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
    )
    from polisyos.scientist.orchestration.engine import (
        BudgetInvocationQuotaPolicy,
        BudgetLedgerInvocationProfile,
    )
    from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
    from polisyos.scientist.orchestration.engine.producer_budget import (
        ProducerBudgetObserver,
        ProducerBudgetSourceError,
    )
    from tests.unit.runtime.quality.test_acquisition_candidate_budget_window import (
        _prepare,
        _settle,
        _unit_window,
    )

    total_units, protected_units = (2, 1) if case == "standard_exact_cap" else (3, 1)
    budget_case = _unit_window(tmp_path / case, monkeypatch)
    _settle(
        budget_case,
        "candidate-reentry-preflight-baseline",
        Decimal("0.02"),
    )
    window = _prepare(budget_case)
    if case == "usd_exact_cap":
        _settle(
            budget_case,
            "candidate-reentry-preflight-window-cap",
            window.fresh_limit_usd,
        )
    budget_state = BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=window.effective_limit_usd)}
    )
    profile = BudgetLedgerInvocationProfile.from_policy(
        budget_case.binding,
        BudgetInvocationQuotaPolicy(
            allocation_id=f"candidate-reentry-preflight-{case}",
            total_units=total_units,
            protected_units=protected_units,
        ),
    )
    selected_profile = None if case == "missing_profile" else profile
    observer = ProducerBudgetObserver(
        settlement_store=budget_case.service._llm_producer_settlement_store,
        producer_run_binding=budget_case.binding,
        budget_state=budget_state,
        invocation_quota_profile=selected_profile,
        reentry_budget_scope=window.scope,
    )
    if case == "standard_exact_cap":
        operation_id = "b" * 64
        request_digest = "a" * 64
        reservation = observer.reserve_invocation(operation_id, request_digest)
        assert reservation is not None and reservation.units == 1
        observer.finish_invocation(operation_id, request_digest, "completed")
        exhausted = observer.observe_standard_invocation_capacity()
        assert exhausted.status == "exhausted"
        assert exhausted.standard_remaining_units == 0
        assert exhausted.protected_remaining_units == 1
    if case == "changed_budget_state":
        budget_state.limits["run"] = BudgetLimit(key="run", max_usd=Decimal("0.09"))

    bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
    origin = object()
    candidate_action_ref = object()
    reentry_budget_scope = object()
    boundary_calls: list[tuple[object, object, object, object]] = []

    def adapt_upstream_reconciliation(**values: object) -> object:
        boundary_calls.append(
            (
                values["origin"],
                values["candidate_action_ref"],
                values["budget_state"],
                values["reentry_budget_scope"],
            )
        )
        return SimpleNamespace(observer=observer)

    monkeypatch.setattr(
        bridge,
        "_reconcile_candidate_experiment_source_reentry_budget",
        adapt_upstream_reconciliation,
        raising=False,
    )
    if case == "wrong_profile_digest":
        observe_capacity = ProducerBudgetObserver.observe_standard_invocation_capacity
        actual_capacity = observe_capacity(observer)
        assert actual_capacity.status == "available"
        assert actual_capacity.profile_digest == profile.profile_digest

        def wrong_digest(current: ProducerBudgetObserver):
            observation = observe_capacity(current)
            return type(observation).model_validate(
                {**observation.model_dump(), "profile_digest": "0" * 64}
            )

        monkeypatch.setattr(
            ProducerBudgetObserver,
            "observe_standard_invocation_capacity",
            wrong_digest,
        )

    def run_preflight() -> object:
        return bridge.candidate_experiment_source_reentry_preflight(
            origin=origin,
            candidate_action_ref=candidate_action_ref,
            budget_state=budget_state,
            reentry_budget_scope=reentry_budget_scope,
        )

    if case == "changed_budget_state":
        with pytest.raises(ProducerBudgetSourceError, match=expected_error or ""):
            run_preflight()
    elif expected_error is not None:
        with pytest.raises(ValueError, match=expected_error):
            run_preflight()
    else:
        assert run_preflight() is observer
        assert observer.invocation_quota_profile == profile
        capacity = observer.observe_standard_invocation_capacity()
        assert capacity.status == "available"
        assert capacity.standard_limit_units == 2
        assert capacity.standard_remaining_units == 2
        assert capacity.protected_limit_units == 1
        assert capacity.protected_remaining_units == 1

    assert boundary_calls == [(origin, candidate_action_ref, budget_state, reentry_budget_scope)]


@pytest.mark.parametrize(
    (
        "selected_profile_present",
        "late_owner_change",
        "final_cas_removed",
        "locator_state",
        "require_existing_quota",
    ),
    [
        (True, False, False, "current", False),
        (False, False, False, "current", False),
        (True, True, False, "current", False),
        (True, False, True, "current", False),
        (True, False, False, "missing", False),
        (True, False, False, "stale", False),
        (True, False, False, "current", True),
        (False, False, False, "current", True),
    ],
)
def test_reentry_budget_reconcile_reuses_window_and_keeps_final_owner_fence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selected_profile_present: bool,
    late_owner_change: bool,
    final_cas_removed: bool,
    locator_state: str,
    require_existing_quota: bool,
) -> None:
    """Reuse exact selected quota; retain the full fallback and final owner fence."""
    from polisyos.runtime.quality import candidate_acquisition_action as actions
    from polisyos.scientist.orchestration.engine import (
        BudgetInvocationQuotaPolicy,
        BudgetLedgerInvocationProfile,
    )
    from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
    from polisyos.scientist.orchestration.engine.producer_budget import ProducerBudgetObserver
    from tests.unit.runtime.quality.test_acquisition_candidate_budget_window import (
        _prepare,
        _settle,
        _unit_window,
    )
    from tests.unit.runtime.quality.test_candidate_experiment_current_outcome import (
        _selection_case,
    )

    budget_case = _unit_window(tmp_path / "reuse-verified-reentry-window", monkeypatch)
    _settle(budget_case, "candidate-reentry-reuse-baseline", Decimal("0.02"))
    window = _prepare(budget_case)
    origin, outcomes = _selection_case(1)
    pending = outcomes[-1]
    quota = BudgetInvocationQuotaPolicy(
        allocation_id="candidate-reentry-reuse-context",
        total_units=3,
        protected_units=1,
    )
    profile = BudgetLedgerInvocationProfile.from_policy(budget_case.binding, quota)
    if selected_profile_present:
        budget_case.service._llm_producer_settlement_store.configure_invocation_profile_safe(
            profile
        )
    budget_state = BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=window.effective_limit_usd)}
    )
    observer = ProducerBudgetObserver(
        settlement_store=budget_case.service._llm_producer_settlement_store,
        producer_run_binding=budget_case.binding,
        budget_state=budget_state,
        invocation_selection_pending=True,
        reentry_budget_scope=window.scope,
    )
    selection = object()
    changed_selection = object()
    phase = pending.latest_receipt
    admission = SimpleNamespace(same_execution_identity=lambda other: other is admission)
    action = SimpleNamespace(
        selection=selection,
        candidate_budget_window_id=window.window_id,
        candidate_budget_window_digest=window.record_digest,
    )
    context_calls: list[object] = []

    def current_context(*args: object) -> object:
        context_calls.append(object())
        if args[2] != pending.head.receipt_ref:
            raise ValueError("candidate_experiment_reentry_action_not_current")
        selected = changed_selection if late_owner_change and len(context_calls) == 2 else selection
        return SimpleNamespace(
            selection=selected,
            phase=phase,
            admission=admission,
            action=action,
            budget_window=window,
        )

    monkeypatch.setattr(
        actions, "_current_candidate_experiment_reentry_action_context", current_context
    )
    assert type(profile) is BudgetLedgerInvocationProfile
    final_action_calls: list[object] = []

    def current_action(*args: object, **kwargs: object) -> tuple[object, ...]:
        final_action_calls.append(object())
        if final_cas_removed:
            raise FileNotFoundError("selected action CAS disappeared before the final fence")
        context = current_context(*args, **kwargs)
        return context.selection, context.phase, context.admission, context.action

    monkeypatch.setattr(actions, "_current_candidate_experiment_reentry_action", current_action)
    fast_builder_calls: list[object] = []
    full_builder_calls: list[object] = []

    def build_from_context(**kwargs: object) -> ProducerBudgetObserver:
        assert kwargs["context"] is not None
        fast_builder_calls.append(kwargs["candidate_action_ref"])
        return observer

    def build_with_full_action_read(**kwargs: object) -> ProducerBudgetObserver:
        assert (
            budget_case.ledger.snapshot().invocation_profiles.get(budget_case.binding.run_id)
            is None
        )
        current_action(
            None,
            kwargs["origin"],
            pending.head.receipt_ref,
            kwargs["candidate_action_ref"],
        )
        full_builder_calls.append(kwargs["candidate_action_ref"])
        return observer

    head_scope = {
        "tenant_id": origin.tenant_id,
        "cell_id": origin.cell_id,
        "run_id": origin.run_id,
        "source_job_id": origin.source_job_id,
        "route_id": origin.route_id,
        "action_generation": len(origin.candidate_terminal_history_chain) + 1,
    }
    head_reads: list[dict[str, object]] = []

    def get_head(**scope: object) -> object:
        head_reads.append(scope)
        if locator_state == "missing":
            return None
        if locator_state == "stale":
            return replace(pending.head, receipt_ref="sha256:" + "f" * 64)
        return pending.head

    service = SimpleNamespace(
        acquisition_route_sink=SimpleNamespace(
            experiment_action_outcomes=lambda **_: pytest.fail(
                "locator lookup replayed the full action history"
            )
        ),
        _control_store=SimpleNamespace(
            get_acquisition_action_head=get_head,
        ),
        _build_candidate_experiment_reentry_budget_observer_from_context=build_from_context,
        build_candidate_experiment_reentry_budget_observer=build_with_full_action_read,
    )
    prior_owner = SimpleNamespace(
        profile=SimpleNamespace(
            n5=SimpleNamespace(invocation_quota_policy=quota, invocation_purpose="standard")
        )
    )
    bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
    bridge._source_control_service = service
    bridge.control_store = SimpleNamespace(get_acquisition_action_head=get_head)
    bridge._candidate_experiment_prior_owner = lambda **_: prior_owner
    bridge.resolve_candidate_experiment_reentry_budget_window = lambda **_: pytest.fail(
        "reconciliation repeated the already verified window resolution"
    )

    def execute() -> object:
        return bridge._reconcile_candidate_experiment_source_reentry_budget(
            origin=origin,
            candidate_action_ref=pending.latest_receipt.candidate_receipt_ref,
            budget_state=budget_state,
            reentry_budget_scope=window.scope,
            require_existing_quota=require_existing_quota,
        )

    strict_missing_profile = require_existing_quota and not selected_profile_present
    if locator_state in {"missing", "stale"}:
        with pytest.raises(
            ValueError,
            match="candidate_experiment_reentry_action_not_current",
        ):
            execute()
    elif final_cas_removed:
        with pytest.raises(FileNotFoundError, match="selected action CAS disappeared"):
            execute()
    elif late_owner_change:
        with pytest.raises(ValueError, match="candidate_experiment_reentry_owner_changed"):
            execute()
    elif strict_missing_profile:
        with pytest.raises(ValueError, match="candidate_experiment_reentry_budget_not_established"):
            execute()
    else:
        result = execute()
        assert result.observer is observer
    assert head_reads == [head_scope]
    assert len(fast_builder_calls) == (0 if locator_state != "current" else 1)
    assert len(full_builder_calls) == (
        0 if locator_state != "current" or selected_profile_present or require_existing_quota else 1
    )
    if locator_state == "missing":
        expected_context_calls = 0
    elif locator_state == "stale" or final_cas_removed or strict_missing_profile:
        expected_context_calls = 1
    elif selected_profile_present:
        expected_context_calls = 2
    else:
        expected_context_calls = 3
    assert len(context_calls) == expected_context_calls
    if locator_state != "current" or strict_missing_profile:
        expected_final_action_calls = 0
    elif selected_profile_present:
        expected_final_action_calls = 1
    else:
        expected_final_action_calls = 2
    assert len(final_action_calls) == expected_final_action_calls
    assert budget_case.ledger.snapshot().invocation_profiles.get(budget_case.binding.run_id) == (
        None if strict_missing_profile else profile
    )


@pytest.mark.parametrize(
    ("locator_state", "expected_error"),
    [
        ("current", None),
        ("missing", "candidate_experiment_action_history_not_current"),
        ("stale", "candidate_experiment_reentry_action_not_current"),
        ("wrong_scope", "candidate_experiment_action_history_not_current"),
        ("wrong_phase", "candidate_experiment_reentry_pending_phase_missing"),
    ],
)
def test_resolve_reentry_window_uses_locator_then_current_action_context(
    monkeypatch: pytest.MonkeyPatch,
    locator_state: str,
    expected_error: str | None,
) -> None:
    """Resolve the current action window once, with a scoped head only as locator."""
    from polisyos.runtime.quality import candidate_acquisition_action as actions
    from tests.unit.runtime.quality.test_candidate_experiment_current_outcome import (
        _selection_case,
    )

    origin, outcomes = _selection_case(1)
    pending = outcomes[-1]
    selection = object()
    action = SimpleNamespace(selection=selection)
    phase = SimpleNamespace(
        receipt_phase=(
            "candidate_input_reentry_pending" if locator_state != "wrong_phase" else "executing"
        )
    )
    window = object()
    locator_scope = {
        "tenant_id": origin.tenant_id,
        "cell_id": origin.cell_id,
        "run_id": origin.run_id,
        "source_job_id": origin.source_job_id,
        "route_id": origin.route_id,
        "action_generation": len(origin.candidate_terminal_history_chain) + 1,
    }
    locator_reads: list[dict[str, object]] = []
    action_context_reads: list[tuple[object, ...]] = []

    def get_head(**scope: object) -> object:
        locator_reads.append(scope)
        if locator_state == "missing":
            return None
        if locator_state == "stale":
            return replace(pending.head, receipt_ref="sha256:" + "f" * 64)
        if locator_state == "wrong_scope":
            return replace(pending.head, tenant_id="foreign-tenant")
        return pending.head

    def current_action_context(*args: object) -> object:
        action_context_reads.append(args)
        if args[2] != pending.head.receipt_ref:
            raise ValueError("candidate_experiment_reentry_action_not_current")
        return SimpleNamespace(
            selection=selection,
            phase=phase,
            action=action,
            budget_window=window,
        )

    monkeypatch.setattr(
        actions,
        "_current_candidate_experiment_reentry_action_context",
        current_action_context,
    )
    service = SimpleNamespace(
        acquisition_route_sink=SimpleNamespace(
            experiment_action_outcomes=lambda **_: pytest.fail(
                "budget-window resolution replayed action history"
            )
        )
    )
    bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
    bridge._source_control_service = service
    bridge.control_store = SimpleNamespace(get_acquisition_action_head=get_head)

    if expected_error is None:
        assert (
            bridge.resolve_candidate_experiment_reentry_budget_window(
                origin=origin,
                candidate_action_ref=pending.latest_receipt.candidate_receipt_ref,
            )
            is window
        )
    else:
        with pytest.raises(ValueError, match=expected_error):
            bridge.resolve_candidate_experiment_reentry_budget_window(
                origin=origin,
                candidate_action_ref=pending.latest_receipt.candidate_receipt_ref,
            )

    assert locator_reads == [locator_scope]
    if locator_state in {"missing", "wrong_scope"}:
        assert action_context_reads == []
    else:
        assert len(action_context_reads) == 1
        expected_locator_ref = (
            "sha256:" + "f" * 64 if locator_state == "stale" else pending.head.receipt_ref
        )
        assert action_context_reads[0][2] == expected_locator_ref


@pytest.mark.parametrize("ledger_profile", ["selected", "missing", "foreign"])
def test_terminal_reentry_binds_exact_selected_quota_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ledger_profile: str,
) -> None:
    """Terminal budget reconciliation binds only the selected existing quota."""
    from polisyos.scientist.orchestration.engine import (
        BudgetInvocationQuotaPolicy,
        BudgetLedgerInvocationProfile,
    )
    from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
    from polisyos.scientist.orchestration.engine.producer_budget import (
        ProducerBudgetObserver,
        ProducerBudgetSourceError,
    )
    from tests.unit.runtime.quality.test_acquisition_candidate_budget_window import (
        _prepare,
        _settle,
        _unit_window,
    )

    budget_case = _unit_window(tmp_path / ledger_profile, monkeypatch)
    _settle(budget_case, "terminal-reentry-quota-baseline", Decimal("0.02"))
    window = _prepare(budget_case)
    quota = BudgetInvocationQuotaPolicy(
        allocation_id="terminal-reentry-selected-standard",
        total_units=5,
        protected_units=1,
    )
    selected_profile = BudgetLedgerInvocationProfile.from_policy(budget_case.binding, quota)
    if ledger_profile == "foreign":
        budget_case.service._llm_producer_settlement_store.configure_invocation_profile_safe(
            BudgetLedgerInvocationProfile.from_policy(
                budget_case.binding,
                BudgetInvocationQuotaPolicy(
                    allocation_id="terminal-reentry-different-standard",
                    total_units=5,
                    protected_units=1,
                ),
            )
        )
    elif ledger_profile == "selected":
        producer = ProducerBudgetObserver(
            settlement_store=budget_case.service._llm_producer_settlement_store,
            producer_run_binding=budget_case.binding,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=window.effective_limit_usd)}
            ),
            invocation_quota_profile=selected_profile,
            reentry_budget_scope=window.scope,
        )
        for index in range(4):
            operation_id = f"{index + 1:064x}"
            request_digest = f"{index + 101:064x}"
            reservation = producer.reserve_invocation(operation_id, request_digest)
            assert reservation is not None
            producer.finish_invocation(operation_id, request_digest, "completed")

    prior_owner = SimpleNamespace(
        profile=SimpleNamespace(
            n5=SimpleNamespace(
                invocation_quota_policy=quota,
                invocation_purpose="standard",
            )
        )
    )
    selected_quota = AcquisitionWorldGrowthBridge._candidate_experiment_standard_quota_policy(
        prior_owner
    )
    assert selected_quota == quota

    terminal_state = BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=window.effective_limit_usd)}
    )
    terminal_observer = ProducerBudgetObserver(
        settlement_store=budget_case.service._llm_producer_settlement_store,
        producer_run_binding=budget_case.binding,
        budget_state=terminal_state,
        invocation_selection_pending=True,
        reentry_budget_scope=window.scope,
    )
    ledger_before_read = budget_case.ledger_path.read_bytes()
    unbound_capacity = ProducerBudgetObserver.observe_standard_invocation_capacity(
        terminal_observer
    )
    assert unbound_capacity.status == "not_established"
    assert unbound_capacity.reason_code == "quota_profile_not_established"
    if ledger_profile != "selected":
        with pytest.raises(ProducerBudgetSourceError, match="n5_invocation_selection_not_current"):
            ProducerBudgetObserver.bind_existing_invocation_policy_from_selected_owner(
                terminal_observer,
                selected_quota,
                purpose="standard",
            )
        assert terminal_observer.invocation_quota_profile is None
    else:
        bound_profile = ProducerBudgetObserver.bind_existing_invocation_policy_from_selected_owner(
            terminal_observer,
            selected_quota,
            purpose="standard",
        )
        assert bound_profile == selected_profile
        observation = ProducerBudgetObserver.observe(terminal_observer)
        capacity = ProducerBudgetObserver.observe_standard_invocation_capacity(terminal_observer)
        assert observation.predicate_basis == "independently_reconciled"
        assert capacity.status == "exhausted"
        assert capacity.profile_digest == selected_profile.profile_digest
        assert capacity.standard_limit_units == 4
        assert capacity.standard_remaining_units == 0
        assert len(capacity.terminal_witnesses) == 4
        assert capacity.exhaustion_witness is not None
        assert ProducerBudgetObserver.verify_standard_invocation_exhaustion(
            terminal_observer,
            capacity.exhaustion_witness,
        )
    assert budget_case.ledger_path.read_bytes() == ledger_before_read


@pytest.mark.asyncio
async def test_v9_intrinsic_history_rejects_pair_and_entry_hint_mutations() -> None:
    """Rehashed mutations cannot detach the edge from its adjacent source history."""

    producer_run = await GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        grounding_port=_AcquisitionRequiredGrounding(),
        value_port=PendingN8ValuePort(),
        authority_scope="contract_testing",
    ).run(
        _problem("candidate_source_intrinsic_history_mutations"),
        budget_state=_budget(),
        max_cycles=1,
    )
    typed_run, payload = _intrinsic_v9_history(producer_run)
    transition = typed_run.basis_transitions[0]

    removed = dict(payload)
    removed.pop("basis_transitions")
    assert validate_generation_cycle_run_history(removed)[0]["code"] == (
        "generation_cycle_historical_projection_invalid"
    )

    reindexed = json.loads(json.dumps(payload))
    reindexed_transition = _reissue_transition(
        transition,
        from_cycle_index=1,
        to_cycle_index=2,
    )
    reindexed["basis_transitions"] = [reindexed_transition.model_dump(mode="json")]
    assert "candidate_source_basis_transition_binding_mismatch" in {
        issue["code"] for issue in validate_generation_cycle_run_history(reindexed)
    }

    foreign_candidate = json.loads(json.dumps(payload))
    foreign_transition = _reissue_transition(
        transition,
        source_candidate_ref="candidate://foreign-selected-entry",
    )
    foreign_candidate["basis_transitions"] = [foreign_transition.model_dump(mode="json")]
    assert "candidate_source_basis_transition_binding_mismatch" in {
        issue["code"] for issue in validate_generation_cycle_run_history(foreign_candidate)
    }

    foreign_prior_ref = json.loads(json.dumps(payload))
    foreign_transition = _reissue_transition(
        transition,
        prior_context_job_ref=_intrinsic_ref("runtime.quality.cycle_substrate_context_job", "5"),
    )
    foreign_prior_ref["basis_transitions"] = [foreign_transition.model_dump(mode="json")]
    assert "candidate_source_basis_transition_binding_mismatch" in {
        issue["code"] for issue in validate_generation_cycle_run_history(foreign_prior_ref)
    }

    problem_hint = json.loads(json.dumps(payload))
    forged_basis = "sha256:" + "c" * 64
    problem_hint["cycles"][1]["design_problem_basis_ref"] = forged_basis
    problem_hint["basis_transitions"] = [
        _reissue_transition(transition, design_problem_basis_ref=forged_basis).model_dump(
            mode="json"
        )
    ]
    assert "candidate_source_basis_transition_binding_mismatch" in {
        issue["code"] for issue in validate_generation_cycle_run_history(problem_hint)
    }

    foreign_subject = json.loads(json.dumps(payload))
    foreign_subject["cycles"][1]["design_problem_ref"] = "sha256:" + "d" * 64
    assert "candidate_source_basis_transition_binding_mismatch" in {
        issue["code"] for issue in validate_generation_cycle_run_history(foreign_subject)
    }

    changed_grammar = json.loads(json.dumps(payload))
    changed_grammar["cycles"][1]["grammar_elements"].append("entry_hint:foreign")
    assert "candidate_source_basis_transition_binding_mismatch" in {
        issue["code"] for issue in validate_generation_cycle_run_history(changed_grammar)
    }


@pytest.mark.asyncio
async def test_v9_transition_history_cannot_carry_forged_n9_promotion() -> None:
    """A self-consistent candidate edge never upgrades forged N9 front claims."""

    producer_run = await GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        grounding_port=_AcquisitionRequiredGrounding(),
        value_port=PendingN8ValuePort(),
        authority_scope="contract_testing",
    ).run(_problem("candidate_source_forged_n9_history"), budget_state=_budget(), max_cycles=1)
    typed_run, _payload = _intrinsic_v9_history(producer_run)
    candidate_id = typed_run.cycles[-1].selected_candidate_ref
    forged_summary = typed_run.candidate_summaries[-1].model_copy(
        update={
            "certified_by_n9": True,
            "current_valid": True,
            "front": "decision",
        }
    )
    forged_run = typed_run.model_copy(
        update={
            "candidate_summaries": (*typed_run.candidate_summaries[:-1], forged_summary),
            "fronts": typed_run.fronts.model_copy(
                update={
                    "decision": typed_run.fronts.decision.model_copy(
                        update={"candidate_ids": (candidate_id,)}
                    ),
                    "quarantine": typed_run.fronts.quarantine.model_copy(
                        update={
                            "candidate_ids": tuple(
                                candidate
                                for candidate in typed_run.fronts.quarantine.candidate_ids
                                if candidate != candidate_id
                            )
                        }
                    ),
                }
            ),
            "promotion_port": typed_run.promotion_port.model_copy(
                update={
                    "status": "certified_current_valid",
                    "certified_candidate_ids": (candidate_id,),
                    "reason": "forged transition-to-N9 promotion",
                    "receipts": ({"authority": "forged"},),
                }
            ),
        }
    )

    history_codes = {
        issue["code"]
        for issue in validate_generation_cycle_run_history(forged_run.model_dump(mode="json"))
    }
    assert "candidate_source_basis_transition_binding_mismatch" not in history_codes
    assert "candidate_source_basis_transition_claims_current_authority" in history_codes

    codes = {issue["code"] for issue in validate_generation_cycle_run(forged_run)}
    assert "candidate_source_basis_transition_owner_not_established" in codes
    assert "candidate_source_basis_transition_claims_current_authority" in codes
    with pytest.raises(
        GenerationCycleError,
        match="candidate_source_basis_transition_owner_not_established",
    ):
        generation_cycle_module.eligible_n9_source_for_run(forged_run)

    from polisyos.runtime.quality.recursive_generation_cycle import RecursiveCycleNode

    with pytest.raises(
        ValueError,
        match=(
            r"recursive_leaf_generation_cycle_history_invalid:.*"
            r"candidate_source_basis_transition_claims_current_authority"
        ),
    ):
        RecursiveCycleNode(
            node_ref="node:forged-candidate-transition",
            parent_ref=None,
            depth=0,
            child_refs=(),
            design_problem_ref=forged_run.design_problem_ref,
            cycle_run=forged_run,
            terminal=generation_cycle_module.generation_cycle_terminal_state(forged_run),
        )


@pytest.mark.asyncio
async def test_active_overlay_reentry_refuses_candidate_basis_before_overlay_or_n5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Candidate-basis history is refused before observed-overlay work can start.

    The existing owner-backed observed-only control remains in
    ``test_generation_cycle.py::test_active_overlay_reentry_is_exact_direct_and_read_only``.
    This adversarial run has a real N6-produced source cycle and fake intrinsic
    refs; it is not evidence of acquisition-owner custody.
    """

    problem = _problem("candidate_basis_overlay_reentry_refusal")
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        grounding_port=_AcquisitionRequiredGrounding(),
        value_port=PendingN8ValuePort(),
        authority_scope="contract_testing",
    )
    producer_run = await controller.run(problem, budget_state=_budget(), max_cycles=1)
    typed_run, _payload = _intrinsic_v9_history(producer_run)
    assert producer_run.basis_transitions == ()
    assert typed_run.basis_transitions

    overlay_reads: list[object] = []
    n5_calls: list[object] = []

    def forbidden_overlay_read(*args: object, **kwargs: object) -> None:
        del args, kwargs
        overlay_reads.append(object())
        raise AssertionError("candidate_basis_reached_overlay_reader")

    def forbidden_n6_cycle(*args: object, **kwargs: object) -> None:
        del args, kwargs
        n5_calls.append(object())
        raise AssertionError("candidate_basis_reached_n6_or_n5")

    simulate = JointSimulationPort.__call__

    def count_n5(
        port: JointSimulationPort,
        *args: object,
        **kwargs: object,
    ) -> object:
        n5_calls.append(object())
        return simulate(port, *args, **kwargs)

    monkeypatch.setattr(controller, "_run_cycle", forbidden_n6_cycle)
    monkeypatch.setattr(
        generation_cycle_module.data_forge_read_api.catalog,
        "project_catalog_acquisition_state",
        forbidden_overlay_read,
    )
    monkeypatch.setattr(JointSimulationPort, "__call__", count_n5)

    with pytest.raises(
        GenerationCycleError,
        match="acquisition_reentry_after_candidate_basis_not_established",
    ):
        await controller.reenter_after_active_acquisition_overlay(
            original_run=typed_run,
            source_cycle=typed_run.cycles[-1],
            problem=problem,
            overlay_receipt=object(),
            observation_projection=object(),
            baseline_path=tmp_path / "baseline.duckdb",
            overlay_path=tmp_path / "overlay.duckdb",
            budget_state=_budget(),
        )

    assert overlay_reads == []
    assert n5_calls == []

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextArtifactOwner

    context_owner = CycleSubstrateContextArtifactOwner(
        store=FileSystemCAS(tmp_path / "candidate-history-context-cas")
    )
    context_history = generation_cycle_module.resolve_generation_cycle_run_context_history(
        typed_run,
        context_owner=context_owner,
        initial_problem=problem,
        expected_job_id="job:intrinsic-history-control",
        expected_run_id=typed_run.run_id,
        expected_tenant_id="tenant:intrinsic-history-control",
        expected_cell_id="cell:intrinsic-history-control",
    )
    assert context_history.status == "not_established"
    assert "candidate_source_basis_transition_owner_not_established" in {
        issue["code"] for issue in context_history.issues
    }


def test_existing_legacy_history_fixtures_keep_transition_field_omitted() -> None:
    """Real v1–v3 projections retain their frozen bytes without a v9 transition field."""

    product_root = Path(__file__).resolve().parents[4]
    v1 = historical_generation_cycle_v1()["generation_cycle_run"]
    v2 = json.loads(
        (
            product_root
            / "architecture/policy_design_case/layer3_gy_generation_cycle_contract.json"
        ).read_text(encoding="utf-8")
    )["generation_cycle_run"]
    v3 = canon.from_canonical_bytes(
        (
            Path(__file__).parent / "fixtures/generation_cycle_controller_v3.json.fixture"
        ).read_bytes()
    )

    spec = canon.CanonSpec(forbid_floats=False)
    for payload in (v1, v2, v3):
        parsed = GenerationCycleRun.model_validate(payload)
        serialized = parsed.model_dump(mode="json")
        historical_projection = generation_cycle_module._historical_generation_cycle_run_projection(
            parsed
        )
        assert parsed.basis_transitions == ()
        assert "basis_transitions" not in serialized
        assert canon.to_canonical_bytes(historical_projection, spec) == canon.to_canonical_bytes(
            payload,
            spec,
        )
        assert validate_generation_cycle_run_history(payload) == ()
