"""Served N4 alternative evaluation after a selected candidate input refusal."""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any

import pytest


@pytest.fixture
def controlled_candidate_gateway(monkeypatch: pytest.MonkeyPatch):
    """Serve the real compiler and recording replay from the local fixture gateway."""
    from tests._helpers.controlled_candidate_profile import ControlledCandidateGateway

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-synthetic-local-gateway-key")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "0")
    monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")
    with ControlledCandidateGateway() as gateway:
        monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", gateway.base_url)
        yield gateway


@pytest.mark.integration
@pytest.mark.asyncio
async def test_served_n4_alternative_runs_after_selected_candidate_input_refusal(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """Persist the first candidate's refusal while actually simulating its eligible sibling."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.services.control import (
        generation_cycle as generation_cycle_service,
    )
    from polisyos.runtime.quality.generation_cycle import (
        CandidateGroundingObservation,
        GenerationCycleController,
        JointSimulationPort,
        PolicyGroundingPort,
        SimulationPortObservation,
        _candidate_content_hash,
        _candidate_id,
        _grounding_unavailable,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationN5InputV1,
    )
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests._helpers.generic_n4_served_replay import prepare_generic_n4_served_replay
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )

    tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    cell_id = "b10-alternative-served-candidate"
    prepared = await prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id=tenant_id,
        cell_id=cell_id,
        child_count=2,
        recording_mode="original_second_capture",
    )
    prepared = replace(
        prepared,
        request_json={
            **prepared.request_json,
            "max_iterations": 1,
            "run_budget_usd": 10.0,
        },
    )

    initial_selections: list[dict[str, Any]] = []
    controlled_refusals: list[str] = []
    post_ground_selections: list[str] = []
    root_runs: list[Any] = []
    root_n5_calls: list[tuple[GenericCycleSimulationN5InputV1, SimulationPortObservation]] = []

    def is_prepared_root(controller: GenerationCycleController) -> bool:
        handoff = controller._generic_cycle_simulation_handoff
        return bool(
            handoff is not None
            and handoff.profile.profile_id == prepared.root_profile.profile_id
            and handoff.profile.profile_selection_kind == "problem"
        )

    original_build = generation_cycle_service.build_design_problem_from_nl_request

    async def build_with_controlled_spans(**kwargs: Any) -> Any:
        kwargs.setdefault("span_support_client", _DeterministicSpanSupportClient())
        return await original_build(**kwargs)

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        build_with_controlled_spans,
    )

    original_generate = GenerationCycleController._generate_node

    async def observe_actual_n4_selection(
        controller: GenerationCycleController,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        generated = await original_generate(controller, state)
        if is_prepared_root(controller) and int(state["cycle_index"]) == 0:
            candidates = tuple(generated["candidates"])
            rankings = generated["rankings"]
            selected = generated["selected_candidate"]

            def score_for(candidate: object) -> float:
                return rankings.get(_candidate_id(candidate), (0.0, 0.0))[0]

            max_score = max(score_for(candidate) for candidate in candidates)
            assert score_for(selected) == max_score
            initial_selections.append(
                {
                    "candidate_ids": tuple(_candidate_id(candidate) for candidate in candidates),
                    "rankings": dict(rankings),
                    "selected_candidate_id": _candidate_id(selected),
                }
            )
        return generated

    monkeypatch.setattr(
        GenerationCycleController,
        "_generate_node",
        observe_actual_n4_selection,
    )

    original_ground = GenerationCycleController._ground_node

    def ground_with_one_typed_missing_input(
        controller: GenerationCycleController,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        if not (
            is_prepared_root(controller) and int(state["cycle_index"]) == 0 and initial_selections
        ):
            return original_ground(controller, state)

        initially_selected_id = initial_selections[-1]["selected_candidate_id"]
        real_grounding_port = controller._grounding_port
        assert isinstance(real_grounding_port, PolicyGroundingPort)

        def selected_candidate_lacks_controlled_input(
            *,
            candidate: object,
            problem: object,
            cycle_index: int,
            generation_result: object,
        ) -> CandidateGroundingObservation:
            candidate_id = _candidate_id(candidate)
            if candidate_id != initially_selected_id:
                return real_grounding_port(
                    candidate=candidate,
                    problem=problem,
                    cycle_index=cycle_index,
                    generation_result=generation_result,
                )
            from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
            from polisyos.runtime.quality.design_problem import DesignProblem

            assert isinstance(problem, DesignProblem)
            controlled_refusals.append(candidate_id)
            return _grounding_unavailable(
                candidate_id,
                issue_codes=("b10_controlled_required_input_unavailable",),
                candidate_content_hash=_candidate_content_hash(candidate),
                design_problem_ref=cycle_job_design_problem_ref(problem),
                authority_level=problem.authority_profile.requested_authority_level,
            )

        controller._grounding_port = selected_candidate_lacks_controlled_input
        try:
            grounded = original_ground(controller, state)
        finally:
            controller._grounding_port = real_grounding_port
        post_ground_selections.append(_candidate_id(grounded["selected_candidate"]))
        return grounded

    monkeypatch.setattr(
        GenerationCycleController, "_ground_node", ground_with_one_typed_missing_input
    )

    original_run = GenerationCycleController.run

    async def observe_persistable_run(
        controller: GenerationCycleController,
        problem: object,
        **kwargs: Any,
    ) -> Any:
        run = await original_run(controller, problem, **kwargs)
        if is_prepared_root(controller):
            root_runs.append(run)
        return run

    monkeypatch.setattr(GenerationCycleController, "run", observe_persistable_run)

    original_simulation_call = JointSimulationPort.__call__

    def observe_actual_generic_n5(
        simulation_port: JointSimulationPort,
        **kwargs: Any,
    ) -> SimulationPortObservation:
        result = original_simulation_call(simulation_port, **kwargs)
        n5_input = kwargs.get("generic_cycle_simulation_input")
        if (
            type(n5_input) is GenericCycleSimulationN5InputV1
            and n5_input.profile.profile_id == prepared.root_profile.profile_id
        ):
            root_n5_calls.append((n5_input, result))
        return result

    monkeypatch.setattr(JointSimulationPort, "__call__", observe_actual_generic_n5)

    app = create_runtime_api_app(**prepared.app_kwargs)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/control/runs/nl",
            headers={"Idempotency-Key": uuid.uuid4().hex},
            json=prepared.request_json,
        )
        assert response.status_code == 200, response.text
        accepted = response.json()
        assert accepted.get("status") == "accepted"
        service = app.state._control_service
        dispatched = dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=accepted["job_id"],
        )
        assert dispatched == accepted["job_id"]
        job = service._control_store.get_job(accepted["job_id"])
        assert job is not None and job.state == "completed"
        run_id = str(job.progress["core_run_id"])
        get_response = client.get(f"/api/v1/runs/{run_id}")
        assert get_response.status_code == 200, get_response.text
        projected_run = get_response.json()["run"]
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            compiled_payload = service._load_payload_ref(
                job.progress["compiled_recursive_generation_cycle_ref"],
                kind="runtime.compiled_recursive_generation_cycle",
            )

    compiled = generation_cycle_service.CompiledRecursiveGenerationCycleRun.model_validate(
        compiled_payload
    )
    assert len(initial_selections) == 1
    assert len(controlled_refusals) == 1
    assert len(post_ground_selections) == 1
    assert len(root_runs) == 1
    assert len(root_n5_calls) == 1

    initial = initial_selections[0]
    initially_selected_id = initial["selected_candidate_id"]
    selected_after_grounding = post_ground_selections[0]
    source_candidate_ids = tuple(
        _candidate_id(candidate) for candidate in prepared.organ_run.result.candidates
    )
    assert len(source_candidate_ids) == 2
    assert initially_selected_id in source_candidate_ids
    assert initially_selected_id != selected_after_grounding
    assert selected_after_grounding in source_candidate_ids
    assert controlled_refusals == [initially_selected_id]

    root_node = next(
        node
        for node in compiled.recursive_run.nodes
        if node.node_ref == compiled.recursive_run.root_node_ref
    )
    assert root_node.cycle_run is not None
    root_run = root_node.cycle_run
    assert root_run.cycles
    cycle = root_run.cycles[0]
    assert set(cycle.candidate_ids) == set(initial["candidate_ids"])
    assert cycle.selected_candidate_ref == selected_after_grounding
    assert cycle.grounding.candidate_id == selected_after_grounding
    assert cycle.grounding.status == "grounded_shadow"
    assert cycle.simulation.status == "joint_simulated"
    assert cycle.simulation.generic_n4_source_ref is not None
    assert cycle.simulation.generic_n5_input_ref is not None
    assert cycle.simulation.generic_n5_execution_ref is not None
    assert cycle.simulation.simulation_result_ref is not None

    summaries = {row.candidate_id: row for row in root_run.candidate_summaries}
    unavailable = summaries[initially_selected_id]
    assert unavailable.grounding_status == "grounding_unavailable"
    assert "b10_controlled_required_input_unavailable" in unavailable.grounding_issue_codes
    assert unavailable.grounding_report_ref
    eligible = summaries[selected_after_grounding]
    assert eligible.grounding_status == "grounded_shadow"
    assert eligible.grounding_source == "cgf_firewall"
    assert eligible.grounding_report_ref

    n5_input, n5_result = root_n5_calls[0]
    assert n5_input.candidate_id == selected_after_grounding
    assert n5_input.profile.profile_selection_ref == prepared.root_profile.profile_selection_ref
    assert n5_input.n4_source_ref == cycle.simulation.generic_n4_source_ref
    assert n5_result.candidate_id == selected_after_grounding
    assert n5_result.status == "joint_simulated"
    root_projection_row = next(
        row
        for row in projected_run["generic_cycle_simulation"]["n5_observations"]
        if row["profile_selection_ref"] == prepared.root_profile.profile_selection_ref
    )
    assert root_projection_row["status"] == "joint_simulated"
    assert root_projection_row["n5_input_ref"] is not None
    assert root_projection_row["simulation_result_ref"] is not None
