"""Candidate-source re-entry refusal and intrinsic-history boundary controls."""

from __future__ import annotations

import json
from contextlib import nullcontext
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core import canon
from polisyos.core.artifacts import ArtifactID, ArtifactRef
from polisyos.runtime.quality import generation_cycle as generation_cycle_module
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
from polisyos.runtime.quality.generation_cycle import (
    JOINT_SIMULATION_RESULT_ARTIFACT_KIND,
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
from tests._helpers.lane01_candidate_action_served import (
    labor_candidate_profile,
    run_lane01_candidate_action_served,
)
from tests.unit.runtime.quality.historical_artifacts import historical_generation_cycle_v1


@pytest.mark.integration
def test_candidate_source_world_refuses_reentry_without_selected_prior_n4_v5(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A live acquired world cannot replace a missing N4/V5/context basis."""

    reentry_refusals: list[tuple[str, object]] = []
    n5_calls: list[object] = []
    reentry_n5_call_deltas: list[int] = []
    reenter = GenerationCycleController.reenter_after_candidate_acquisition_source
    simulate = JointSimulationPort.__call__

    async def inspect_reentry(
        controller: GenerationCycleController,
        *,
        bridge: object,
        closure: object,
        candidate_action_ref: object,
        source_world_handoff: object,
        budget_state: object,
    ) -> object:
        from polisyos.runtime.quality.acquisition_world_growth import (
            CandidateSourceWorldHandoff,
        )
        from polisyos.runtime.quality.candidate_acquisition_action import (
            read_candidate_acquisition_action,
        )

        assert type(bridge) is AcquisitionWorldGrowthBridge
        assert type(source_world_handoff) is CandidateSourceWorldHandoff
        source_cycle = closure.source_cycle
        assert source_cycle.simulation.candidate_simulation_n4_source_ref is None
        assert source_cycle.simulation.candidate_simulation_n5_input_ref is None
        assert source_cycle.simulation.candidate_simulation_context_job_ref is None
        assert controller._artifact_store is bridge.artifact_store
        assert type(controller._simulation_port) is JointSimulationPort
        assert controller._cycle_substrate_context == source_world_handoff.context
        assert controller._candidate_simulation_handoff == source_world_handoff.handoff
        assert source_world_handoff.currentness_resolver() is True

        action = bridge._require_selected_candidate_action(
            closure=closure,
            candidate_action_ref=candidate_action_ref,
        )
        assert (
            read_candidate_acquisition_action(
                bridge=bridge,
                closure=closure,
                receipt_ref=candidate_action_ref,
                require_current_action=True,
            )
            == action
        )
        assert source_world_handoff.candidate_source_ref == action.candidate_source_ref
        assert source_world_handoff.candidate_action_ref == candidate_action_ref
        assert source_world_handoff.world_model_record.content_hash != (
            source_world_handoff.context.world_model_record.content_hash
        )
        assert source_world_handoff.handoff.context.world_model_record.content_hash == (
            source_world_handoff.context.world_model_record.content_hash
        )

        store = bridge.artifact_store
        before_n5_inputs = store.manifest_inventory_snapshot(
            kind="runtime.quality.candidate_simulation_n5_input"
        )
        before_n5_results = store.manifest_inventory_snapshot(
            kind=JOINT_SIMULATION_RESULT_ARTIFACT_KIND
        )
        before_calls = len(n5_calls)
        with pytest.raises(GenerationCycleError) as refusal:
            await reenter(
                controller,
                bridge=bridge,
                closure=closure,
                candidate_action_ref=candidate_action_ref,
                source_world_handoff=source_world_handoff,
                budget_state=budget_state,
            )
        exc = refusal.value
        assert exc.code == "candidate_source_reentry_prior_evaluation_not_established"
        assert source_world_handoff.currentness_resolver() is True
        assert len(n5_calls) == before_calls
        assert (
            store.manifest_inventory_snapshot(kind="runtime.quality.candidate_simulation_n5_input")
            == before_n5_inputs
        )
        assert (
            store.manifest_inventory_snapshot(kind=JOINT_SIMULATION_RESULT_ARTIFACT_KIND)
            == before_n5_results
        )
        reentry_n5_call_deltas.append(len(n5_calls) - before_calls)
        reentry_refusals.append((exc.code, source_world_handoff))
        raise exc

    def count_n5(
        port: JointSimulationPort,
        *args: object,
        **kwargs: object,
    ) -> object:
        n5_calls.append(object())
        return simulate(port, *args, **kwargs)

    monkeypatch.setattr(
        GenerationCycleController,
        "reenter_after_candidate_acquisition_source",
        inspect_reentry,
    )
    monkeypatch.setattr(JointSimulationPort, "__call__", count_n5)

    def observe(ctx: Any) -> None:
        assert ctx.response.status_code in {200, 202}, ctx.response.text
        assert ctx.job is not None and ctx.job.state == "failed"
        assert len(reentry_refusals) == 1
        assert reentry_refusals[0][0] == (
            "candidate_source_reentry_prior_evaluation_not_established"
        )
        assert ctx.transport_calls == [
            (
                "GET",
                "https://api.worldbank.org/v2/country/USA/indicator/SL.UEM.TOTL.ZS",
                {"date": "2024:2024", "format": "json", "page": "1", "per_page": "1000"},
            )
        ]
        scope = {
            "tenant_id": ctx.closure.tenant_id,
            "cell_id": ctx.closure.cell_id,
            "run_id": ctx.closure.run_id,
            "source_job_id": ctx.closure.source_job_id,
            "route_id": ctx.closure.route_id,
        }
        outcome = ctx.control.acquisition_route_sink.current_action_outcome(**scope)
        assert outcome is not None
        assert outcome.latest_receipt.receipt_phase == "candidate_input_reentry_pending"
        assert getattr(outcome.latest_receipt, "reentry_receipt_ref", None) is None
        assert reentry_n5_call_deltas == [0]

        for forbidden_kind in (
            "runtime_quality.acquisition_world_growth_receipt",
            "epoch.prepared",
            "epoch.production_receipt",
            "epoch.acquisition_passport_snapshot",
        ):
            inventory = ctx.control._artifact_store.manifest_inventory_snapshot(kind=forbidden_kind)
            assert inventory.verdict == "pass"
            assert inventory.entries == (), forbidden_kind

    run_lane01_candidate_action_served(
        tmp_path,
        monkeypatch,
        observe,
        candidate_profile_builder=labor_candidate_profile,
    )


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
    from polisyos.scientist.orchestration.engine import ProducerBudgetObserver
    from tests.unit.runtime.quality.test_candidate_acquisition_world import _candidate_world_case
    from tests.unit.runtime.quality.test_candidate_experiment_current_outcome import _selection_case
    from tests.unit.runtime.quality.test_candidate_experiment_dispatch_currentness import (
        _reentry_receipts,
        _selected_ref,
    )

    world = _candidate_world_case(tmp_path / "world", monkeypatch)
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
        bridge.resolve_candidate_experiment_reentry_budget_window = lambda **_: SimpleNamespace(
            window_id=action.candidate_budget_window_id,
            record_digest=action.candidate_budget_window_digest,
            effective_limit_usd=Decimal("1"),
            scope=object(),
        )

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

        class Controller:
            def __init__(self, **_: object) -> None:
                pass

            async def reenter_after_candidate_acquisition_source(self, **_: object) -> object:
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

    exercise("recovered", recovered=True)
    exercise("costed-recovered", recovered=True, costed=True)
    exercise("new", recovered=False)
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
        match="recursive_leaf_generation_cycle_history_invalid:"
        "candidate_source_basis_transition_claims_current_authority",
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
