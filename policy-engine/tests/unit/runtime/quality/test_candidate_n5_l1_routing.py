"""Real L1-owner routing projection; selected N5 refs here are controlled inputs."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import (
    ArtifactOwnershipError,
    ArtifactReadOnlyUnavailableError,
    ArtifactRef,
    FileSystemCAS,
)
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import acquisition_planner as planner
from polisyos.runtime.quality import generation_cycle as owner
from polisyos.runtime.quality.intervention_atom_binding import InterventionAtomBinding
from polisyos.runtime.quality.substrate_registry import catalog_serving_source_scope
from tests.unit.runtime.quality.test_catalog_source_identity import (
    _actual_profile_gateway_inputs,
    _selected_fixture,
)
from tests.unit.runtime.quality.test_value_gate import _world_record


def _ref(digit: str, kind: str, *, selected: bool = True) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + digit * 64,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=("sha256:" + digit * 64 if selected else None),
    )


def _simulation(candidate_id: str) -> owner.SimulationPortObservation:
    source = _ref("1", "runtime.quality.n4_candidate_scenario_source")
    context = _ref("2", "runtime.quality.cycle_substrate_context_job")
    n5_input = _ref("3", "runtime.quality.candidate_simulation_n5_input")
    execution = _ref("4", "runtime.quality.candidate_simulation_execution")
    result = _ref("5", "polisyos.runtime.joint_simulation_result")
    return owner.SimulationPortObservation(
        candidate_id=candidate_id,
        status="joint_simulated",
        candidate_simulation_n4_source_ref=source,
        candidate_simulation_context_job_ref=context,
        candidate_simulation_n5_input_ref=n5_input,
        candidate_simulation_profile_config_ref="fixture://candidate-n5-config",
        candidate_simulation_profile_selection_ref="sha256:" + "6" * 64,
        simulation_result_ref=result,
        diagnostics={
            "candidate_simulation_execution_selected_ref": execution.model_dump(mode="json"),
            "candidate_simulation_purpose": "candidate_scenario_n5_only",
        },
        world_model_record=_world_record(),
    )


def _controller(code: Path, source: Any, current: Any) -> owner.GenerationCycleController:
    # This component fixture exercises the real catalog owner. It does not
    # represent these controlled ref-shaped inputs as an executed N5.
    controller = owner.GenerationCycleController.__new__(owner.GenerationCycleController)
    controller._repo_root = code
    controller._catalog_serving_source = source
    controller._artifact_store = None
    controller._candidate_simulation_currentness_resolver = current
    return controller


def test_real_l1_gap_keeps_candidate_n5_limitation_and_legacy_wire(tmp_path: Path) -> None:
    code, _owner, source = _selected_fixture(tmp_path)
    _gateway_type, problem, candidate = _actual_profile_gateway_inputs()
    simulation = _simulation(candidate.candidate_id)
    controller = _controller(code, source, lambda: True)
    with catalog_serving_source_scope(source):
        observed = controller._observe_candidate_n5_l1_routing(
            candidate=candidate, problem=problem, simulation=simulation
        )
    assert observed is not None
    assert observed.requirement_gap.metadata["source"] == "l1_dcat_variable_availability"
    assert observed.requirement_gap.metadata["availability"]["variable_id"] == "government.balance"
    assert observed.historical_catalog_absence == observed.catalog_currentness == "not_established"
    value = owner.ValuePortObservation(
        status="value_pending_n8",
        candidate_id=candidate.candidate_id,
        authority_blockers=("candidate_scenario_n5_only",),
        reason="candidate_scenario_n5_only",
        candidate_n5_l1_routing=observed,
    )
    assert value.acquisition_requirement is None
    assert owner.ValuePortObservation.model_validate(value.model_dump(mode="json")) == value
    legacy = owner._configured_candidate_value_observation(candidate.candidate_id, simulation)
    assert "candidate_n5_l1_routing" not in legacy.model_dump(mode="json")
    with pytest.raises(ValueError, match="candidate_n5_l1_value_projection_mismatch"):
        owner.ValuePortObservation.model_validate(
            {**value.model_dump(mode="json"), "status": "value_ready"}
        )
    from tests.unit.runtime.quality.test_generation_cycle_historical_projection_fail_closed import (
        _v3_fixture,
    )

    _raw, historical = _v3_fixture()
    historical["value_port"]["candidate_n5_l1_routing"] = observed.model_dump(mode="json")
    with pytest.raises(ValueError, match="historical_generation_cannot_carry_candidate_n5_l1"):
        owner.GenerationCycleRun.model_validate(historical)


def test_no_l1_gap_is_invented_for_available_or_unavailable_source(tmp_path: Path) -> None:
    code, _owner, source = _selected_fixture(tmp_path, populated=True)
    _gateway_type, problem, candidate = _actual_profile_gateway_inputs()
    simulation = _simulation(candidate.candidate_id)
    controller = _controller(code, source, lambda: True)
    with catalog_serving_source_scope(source):
        assert (
            controller._observe_candidate_n5_l1_routing(
                candidate=candidate, problem=problem, simulation=simulation
            )
            is None
        )
        source.database_path.with_name(source.database_path.name + ".wal").write_bytes(b"pending")
        assert (
            controller._observe_candidate_n5_l1_routing(
                candidate=candidate, problem=problem, simulation=simulation
            )
            is None
        )


def test_lost_worker_scope_and_unselected_context_cannot_emit_gap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    code, _owner, source = _selected_fixture(tmp_path)
    _gateway_type, problem, candidate = _actual_profile_gateway_inputs()
    simulation = _simulation(candidate.candidate_id)
    current = {"value": True}
    controller = _controller(code, source, lambda: current["value"])
    real_load = owner.RealValueOwnerGateway.load_value_data_profile

    def lose_scope_after_real_read(self: object, **kwargs: Any) -> Any:
        try:
            return real_load(self, **kwargs)
        finally:
            current["value"] = False

    monkeypatch.setattr(
        owner.RealValueOwnerGateway, "load_value_data_profile", lose_scope_after_real_read
    )
    with catalog_serving_source_scope(source):
        assert (
            controller._observe_candidate_n5_l1_routing(
                candidate=candidate, problem=problem, simulation=simulation
            )
            is None
        )
        current["value"] = True
        unselected = simulation.model_copy(
            update={
                "candidate_simulation_context_job_ref": _ref(
                    "2", "runtime.quality.cycle_substrate_context_job", selected=False
                )
            }
        )
        assert (
            controller._observe_candidate_n5_l1_routing(
                candidate=candidate, problem=problem, simulation=unselected
            )
            is None
        )
        assert current["value"] is True


@pytest.mark.asyncio
async def test_mixed_request_keeps_both_sources_and_rejects_rebinding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.unit.runtime.quality.test_n7_descriptor_emission import _emitted_cycle

    problem, l1_gap, controller, original, cas_root = await _emitted_cycle(tmp_path)
    candidate_id = original.selected_candidate_ref
    simulation = _simulation(candidate_id)
    selected_execution = ArtifactRef.model_validate(
        simulation.diagnostics["candidate_simulation_execution_selected_ref"]
    )
    l1 = owner._CandidateN5L1RoutingObservation(
        source_ref=simulation.candidate_simulation_n4_source_ref,
        context_job_ref=simulation.candidate_simulation_context_job_ref,
        n5_input_ref=simulation.candidate_simulation_n5_input_ref,
        n5_execution_ref=selected_execution,
        n5_result_ref=simulation.simulation_result_ref,
        requirement_gap=l1_gap,
    )
    value = owner.ValuePortObservation(
        status="value_pending_n8",
        candidate_id=candidate_id,
        authority_blockers=("candidate_scenario_n5_only",),
        reason="candidate_scenario_n5_only",
        candidate_n5_l1_routing=l1,
    )
    cov_gap = planner.grounding_coverage_requirement_gap(
        candidate_id=candidate_id,
        candidate_content_hash=original.selected_candidate_content_hash,
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        issue_codes=("cgf_disposition_missing",),
        evidence_refs=("fixture://controlled-grounding-evidence",),
        grounding_report_ref="fixture://controlled-grounding-report",
        authority_level=problem.authority_profile.requested_authority_level,
    )
    grounding = owner.CandidateGroundingObservation(
        candidate_id=candidate_id,
        status="grounding_gap",
        grounding_score=0.0,
        issue_codes=("cgf_disposition_missing",),
        evidence_refs=("fixture://controlled-grounding-evidence",),
        report_ref="fixture://controlled-grounding-report",
        acquisition_requirement=cov_gap,
    )
    terminal = owner._select_terminal_kind(grounding=grounding, proxy_score=0.0, value_port=value)
    counterexample = owner._counterexample_record(
        problem=problem,
        cycle_index=0,
        candidate_id=candidate_id,
        grounding=grounding,
        value_port=value,
    )
    revision = owner._default_revision_request(
        problem=problem,
        cycle_index=0,
        candidate_id=candidate_id,
        terminal_kind=terminal,
        counterexample=counterexample,
        grounding=grounding,
        value_port=value,
    )
    candidate = original.model_copy(
        update={
            "grounding": grounding,
            "simulation": simulation,
            "value_port": value,
            "terminal_kind": terminal,
            "counterexample": counterexample,
            "revision_request": revision,
        }
    )
    cycle = owner.GenerationCycleRecord.model_validate(candidate.model_dump(mode="json"))
    original_failure = ArtifactOwnershipError("private-storage-location")
    with pytest.raises(owner.GenerationCycleError) as captured_failure:
        raise owner._n7_planner_persistence_refusal(original_failure) from original_failure
    assert captured_failure.value.__cause__ is original_failure
    assert captured_failure.value.source_refusal_code == "artifact_ownership_refused"
    failed_cycle = owner._cycle_with_n7_route_failure(
        cycle,
        reason=(f"{captured_failure.value.code}.{captured_failure.value.source_refusal_code}"),
    )
    assert failed_cycle.counterexample.diagnostic.code == (
        "n6.acquisition.n7_planner_report_persistence_refused.artifact_ownership_refused"
    )
    assert "private-storage-location" not in failed_cycle.counterexample.diagnostic.message
    request = cycle.revision_request.strategy_payload["acquisition_request"]
    assert request["n7_source_join_rule"] == planner._N7_CANDIDATE_N5_L1_OBLIGATIONS_RULE
    assert request["driver"] == "acquire_data:value_panel_data_missing"
    assert request["requirement_gap"] == l1_gap.model_dump(mode="json")
    assert request["accompanying_requirement_gaps"] == [cov_gap.model_dump(mode="json")]
    assert owner._n7_cycle_source_gap(problem, cycle=cycle, acquisition_request=request) == (
        l1_gap,
        None,
    )
    for changed in (
        {**request, "accompanying_requirement_gaps": []},
        {**request, "accompanying_requirement_gaps": [cov_gap.model_dump(mode="json")] * 2},
        {**request, "n7_source_join_rule": planner._N7_SOURCE_JOIN_RULE},
        {**request, "driver": "acquire_data:global.unemployment_rate"},
    ):
        assert owner._n7_cycle_source_gap(problem, cycle=cycle, acquisition_request=changed) == (
            None,
            "unbound_requirement_input_refused",
        )
    tampered = cycle.model_dump(mode="json")
    tampered["simulation"]["candidate_simulation_context_job_ref"]["manifest_profile_sha256"] = (
        "sha256:" + "f" * 64
    )
    with pytest.raises(ValueError, match="cycle_candidate_n5_l1_binding_mismatch"):
        owner.GenerationCycleRecord.model_validate(tampered)

    retention = controller._retained_configured_cheap_continuation(
        original_run=None,
        source_cycle=cycle,
        problem=problem,
        budget_state=None,
        current_basis_ref=simulation.candidate_simulation_n5_input_ref,
        admitted_source_ref=simulation.candidate_simulation_n4_source_ref,
        growth_ref=simulation.simulation_result_ref,
    )
    assert retention.status == "not_established"
    assert retention.reason_code == "retained_cheap_l1_obligation_not_established"
    legacy_retention = controller._retained_configured_cheap_continuation(
        original_run=None,
        source_cycle=original,
        problem=problem,
        budget_state=None,
        current_basis_ref=simulation.candidate_simulation_n5_input_ref,
        admitted_source_ref=simulation.candidate_simulation_n4_source_ref,
        growth_ref=simulation.simulation_result_ref,
    )
    assert legacy_retention.status == "not_established"
    assert legacy_retention.reason_code == "retained_cheap_profile_not_established"

    # Exercise the actual cycle's configured-source failure boundary with a
    # controlled engine result. A missing owner view may withhold the source;
    # a wrapped access denial must retain its identity rather than masquerade
    # as the same ordinary nonreceipt.
    async def completed_engine(_state: object) -> dict[str, object]:
        return {
            "cycle": cycle,
            "candidate_summaries": (),
            "_n7_candidate_port_source_ref": object(),
        }

    for failure in (
        ArtifactOwnershipError("controlled selected source denial"),
        ArtifactReadOnlyUnavailableError("controlled selected source unavailable"),
    ):

        def fail_capture(*_args: object, _failure: Exception = failure, **_kwargs: object) -> None:
            raise RuntimeError("controlled source wrapper") from _failure

        with monkeypatch.context() as access_check:
            access_check.setattr(controller, "_engine", SimpleNamespace(run_async=completed_engine))
            access_check.setattr(controller, "_authority_scope", "production")
            access_check.setattr(
                controller, "_capture_n7_configured_candidate_port_source", fail_capture
            )
            controller._n7_configured_candidate_port_refs[0] = simulation.simulation_result_ref
            if isinstance(failure, ArtifactReadOnlyUnavailableError):
                observed_cycle, summaries = await controller._run_cycle(
                    problem, cycle_index=0, budget_state=None, previous_cycle=None
                )
                assert observed_cycle is cycle and summaries == ()
            else:
                with pytest.raises(ArtifactOwnershipError) as captured_denial:
                    await controller._run_cycle(
                        problem, cycle_index=0, budget_state=None, previous_cycle=None
                    )
                assert captured_denial.value is failure
            assert 0 not in controller._n7_configured_candidate_port_refs

    # The older retained reader is reused by the new candidate owner. These
    # adapter inputs stop at the actual repository read; they do not claim a
    # real selected N5 or a protected retained action.
    from polisyos.runtime.quality.candidate_simulation import CandidateSimulationContextHandoff
    from tests.unit.runtime.quality.test_generation_cycle import _budget

    context = {"fixture": "controlled-retained-context"}
    handoff = CandidateSimulationContextHandoff.model_construct(
        context=context,
        context_job_ref=simulation.candidate_simulation_context_job_ref,
        run_id="fixture-run",
        job_id="fixture-job",
        tenant_id="fixture-tenant",
        cell_id="fixture-cell",
    )
    retained_simulation = simulation.model_copy(
        update={
            "diagnostics": {
                **simulation.diagnostics,
                "candidate_simulation_n4_source_selected_ref": (
                    simulation.candidate_simulation_n4_source_ref.model_dump(mode="json")
                ),
            }
        }
    )
    retained_cycle = cycle.model_copy(
        update={
            "simulation": retained_simulation,
            "value_port": owner._configured_candidate_value_observation(
                candidate_id, retained_simulation
            ),
        }
    )
    prior = SimpleNamespace(
        cycles=(retained_cycle,),
        candidate_summaries=(
            SimpleNamespace(
                cycle_index=0,
                candidate_id=candidate_id,
                content_hash=retained_cycle.selected_candidate_content_hash,
                generation_channel="n4_owner",
            ),
        ),
    )
    for failure in (
        ArtifactOwnershipError("controlled retained source denial"),
        ArtifactReadOnlyUnavailableError("controlled retained source unavailable"),
    ):

        def fail_selected_read(
            *_args: object, _failure: Exception = failure, **_kwargs: object
        ) -> None:
            raise RuntimeError("controlled retained source wrapper") from _failure

        with monkeypatch.context() as access_check:
            access_check.setattr(controller, "_grounding_port", owner.PolicyGroundingPort())
            access_check.setattr(controller, "_candidate_simulation_handoff", handoff)
            access_check.setattr(controller, "_cycle_substrate_context", context)
            access_check.setattr(
                controller._source_repository,
                "load_candidate_scenario_source_in_owner_scope",
                fail_selected_read,
            )

            def call():
                return controller._retained_configured_cheap_continuation(
                    original_run=prior,
                    source_cycle=retained_cycle,
                    problem=problem,
                    budget_state=_budget(),
                    current_basis_ref=simulation.candidate_simulation_n5_input_ref,
                    admitted_source_ref=simulation.candidate_simulation_n4_source_ref,
                    growth_ref=simulation.simulation_result_ref,
                )

            if isinstance(failure, ArtifactReadOnlyUnavailableError):
                refusal = call()
                assert refusal.reason_code == "retained_cheap_prior_source_unresolved"
            else:
                with pytest.raises(ArtifactOwnershipError) as captured_denial:
                    call()
                assert captured_denial.value is failure

    # Capture through the real source and checkpoint writers, then reopen in a
    # fresh same-owner CAS. The N5-shaped inputs above remain controlled test
    # inputs; the served test is responsible for real N5 qualification.
    store = controller._n7_runtime_artifact_store()
    prior_selection = controller._n7_candidate_selections[0]
    prior_source = planner._n7_load_candidate_source(
        store, prior_selection.source_ref, source_type=planner._N7CandidatePortSource
    )
    selected_atom = InterventionAtomBinding.model_validate(prior_source.candidate_atom)
    captured = controller._capture_n7_candidate_port_source(
        {
            "selected_grounding": grounding,
            "value_port": value,
            "selected_candidate": SimpleNamespace(candidate_id=candidate_id, atom=selected_atom),
            "problem": problem,
            "cycle_index": 0,
        }
    )
    port_ref = captured["_n7_candidate_port_source_ref"]
    checkpoint = planner._N7CandidateCycleCheckpoint(
        source_ref=port_ref,
        source_run_id=prior_source.source_run_id,
        cycle_index=0,
        cycle=cycle.model_dump(mode="json"),
    )
    checkpoint_ref = planner._n7_put_candidate_source(store, checkpoint)
    basis = controller._n7_data_requirement_basis_with_report(
        problem, acquisition_request=request, cycle=cycle
    )
    assert basis.routing_limitation_code is None and not basis.unbound_input_fields

    # The real planner reaches compiler persistence with this mixed cycle. A
    # wrapped ownership denial must not be presented as a missing compiler
    # report; a genuinely unavailable owner remains a typed planner refusal.
    for failure in (
        ArtifactOwnershipError("controlled compiler owner denial"),
        ArtifactReadOnlyUnavailableError("controlled compiler owner unavailable"),
    ):

        def fail_compiler(*_args: object, _failure: Exception = failure, **_kwargs: object) -> None:
            raise RuntimeError("controlled compiler wrapper") from _failure

        with monkeypatch.context() as access_check:
            access_check.setattr(
                owner, "persist_and_verify_data_requirement_compilation_report", fail_compiler
            )
            if isinstance(failure, ArtifactReadOnlyUnavailableError):
                with pytest.raises(owner.GenerationCycleError) as refused:
                    controller._plan_n7_requirement_gap_if_requested(problem, cycle=cycle)
                assert refused.value.code == "n7_compiler_report_persistence_refused"
            else:
                with pytest.raises(ArtifactOwnershipError) as captured_denial:
                    controller._plan_n7_requirement_gap_if_requested(problem, cycle=cycle)
                assert captured_denial.value is failure

    binding = planner.persist_and_verify_data_requirement_compilation_report(
        store, basis.compilation_report, expected_scenario_id=problem.design_problem_id
    )
    gaps = planner._n7_candidate_n5_l1_obligation_gaps(
        source_gap=l1_gap,
        accompanying_requirement_gaps=(cov_gap,),
        specs=basis.specs,
        capability_resolutions=basis.capability_resolutions,
    )
    report = planner.plan_evidence_acquisition(
        run_id=f"n7-cycle:{problem.design_problem_id}:0",
        gaps=gaps,
        requirement_basis_binding=binding,
        generated_at=datetime(2026, 11, 3, tzinfo=UTC),
    )
    report_ref = planner.persist_and_verify_acquisition_planner_report(store, report)
    selected_request = {
        **request,
        "cycle_index": 0,
        "n7_candidate_source_ref": checkpoint_ref.model_dump(mode="json"),
    }
    fresh = FileSystemCAS(cas_root).for_tenant("tenant-source", cell_id="cell-source")
    reopened = planner.load_acquisition_planner_report(fresh, report_ref)
    replay = {
        "store": fresh,
        "checkpoint_ref": checkpoint_ref,
        "run_id": report.run_id,
        "problem": problem,
        "specs": basis.specs,
        "capability_resolutions": basis.capability_resolutions,
        "report": reopened,
        "require_current": False,
    }
    assert planner._n7_validate_candidate_checkpoint(request=selected_request, **replay) == l1_gap
    assert any(
        row.requirement_gap_ref == cov_gap.requirement_gap_id
        for row in reopened.acquisition_records
    )
    for changed in (
        {**selected_request, "accompanying_requirement_gaps": []},
        {
            **selected_request,
            "accompanying_requirement_gaps": [cov_gap.model_dump(mode="json")] * 2,
        },
        {**selected_request, "n7_source_join_rule": planner._N7_SOURCE_JOIN_RULE},
        {**selected_request, "driver": "acquire_data:global.unemployment_rate"},
    ):
        with pytest.raises(ValueError):
            planner._n7_validate_candidate_checkpoint(request=changed, **replay)
