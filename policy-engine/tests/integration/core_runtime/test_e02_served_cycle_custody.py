from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests._helpers.controlled_candidate_profile import (
    _configured_procurement_profile,
    _controlled_procurement_recording,
    _current_compiler_problem,
)
from tools.quality.validation import (
    check_layer3_gy_design_generation_contract as n4_contract,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
_RECORDING_ID = "gy_n4_cgf_decisive_capture_1_20260704_092222_049411"
_TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_CELL_ID = "cell-a"


def test_served_candidate_value_is_recomputed_from_n5_cas_on_fresh_get(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ordinary run-details route replays one candidate-only value from CAS."""

    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core import canon
    from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http import jwt_auth_middleware
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.security import PolicyOSRole, build_fixture_identity_claims
    from polisyos.runtime.http.services.control import generation_cycle as generation_cycle_service
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        _control_job_execution_scope_from_event,
    )
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationN5InputV5,
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.conditional_simulation_replay import (
        replay_conditional_simulation_values,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generation_cycle import (
        JointSimulationPort,
        _DefaultSimulationBoundFoundryValuePort,
    )
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateScenarioSourceRecordV2,
        N4CandidateScenarioSourceRecordV3,
    )
    from polisyos.runtime.quality.intervention_atom_binding import (
        derive_candidate_scenario_atom,
    )
    from polisyos.runtime.quality.promotion_sequence import CanonicalN9PromotionPort
    from polisyos.scientist.orchestration.llm import factory as llm_factory
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests.unit.runtime.http.test_control_job_execution_intent import (
        _valid_intake_for_mode,
    )
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
        _FakeDesignProblemGateway,
    )

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", (tmp_path / "control.sqlite3").as_posix())
    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())
    monkeypatch.setenv("JAX_PLATFORMS", "cpu")
    monkeypatch.setenv("OMP_NUM_THREADS", "1")

    recording = next(
        item
        for item in n4_contract._load_recordings(REPO_ROOT)
        if item.get("design_problem_id") == _RECORDING_ID
    )
    recorded_problem = _current_compiler_problem(recording)
    controlled_recording = _controlled_procurement_recording(
        recording,
        outcome_variable=recorded_problem.outcome_of_interest.target_variable,
    )
    raw_request = recorded_problem.nl_provenance.raw_request
    model_id = str(recording["model_id"])
    compiler_gateway = _FakeDesignProblemGateway(
        models=[model_id],
        arguments=recorded_problem.model_dump(mode="json"),
    )
    cas_root = tmp_path / ".polisyos"
    first_context = build_runtime_api_context(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
    )
    profile, model_declaration = _configured_procurement_profile(
        recorded_problem=recorded_problem,
        artifact_store=first_context.store,
        tenant_id=_TENANT_ID,
        cell_id=_CELL_ID,
    )
    assert profile.profile_selection_ref == cycle_job_profile_selection_ref(recorded_problem)

    original_compiler = generation_cycle_service.build_design_problem_from_nl_request
    compiled_problems: list[Any] = []

    async def run_real_compiler(**kwargs: Any) -> Any:
        kwargs["gateway_client"] = compiler_gateway
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        problem = await original_compiler(**kwargs)
        compiled_problems.append(problem)
        return problem

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        run_real_compiler,
    )
    monkeypatch.setattr(
        llm_factory,
        "create_traced_gateway_client",
        lambda **_kwargs: n4_contract.RecordedGenerationReplayClient(controlled_recording),
    )

    n5_calls: list[tuple[object, object]] = []
    n8_calls: list[dict[str, object]] = []
    n9_calls: list[str] = []
    original_n5 = JointSimulationPort.__call__
    original_n8 = _DefaultSimulationBoundFoundryValuePort.__call__
    original_n9 = CanonicalN9PromotionPort.__call__

    def observe_n5(port: object, *args: Any, **kwargs: Any) -> object:
        observation = original_n5(port, *args, **kwargs)
        input_record = kwargs.get("candidate_simulation_input")
        if input_record is not None:
            n5_calls.append((input_record, observation))
        return observation

    def observe_n8(port: object, *args: Any, **kwargs: Any) -> object:
        observation = original_n8(port, *args, **kwargs)
        n8_calls.append(
            {
                "candidate": kwargs.get("candidate"),
                "simulation": kwargs.get("simulation"),
                "problem": kwargs.get("problem"),
                "cycle_index": kwargs.get("cycle_index"),
                "observation": observation,
            }
        )
        return observation

    def observe_n9(port: object, *args: Any, **kwargs: Any) -> object:
        n9_calls.append(type(port).__qualname__)
        return original_n9(port, *args, **kwargs)

    monkeypatch.setattr(JointSimulationPort, "__call__", observe_n5)
    monkeypatch.setattr(_DefaultSimulationBoundFoundryValuePort, "__call__", observe_n8)
    monkeypatch.setattr(CanonicalN9PromotionPort, "__call__", observe_n9)

    first_app = create_runtime_api_app(
        cas_root=cas_root,
        container_overrides=RuntimeContainerOverrides(runtime_api_context=first_context),
        allow_fixture_identity=True,
        candidate_simulation_profiles=(profile,),
        candidate_simulation_model_declarations=(model_declaration,),
    )
    with TestClient(first_app) as client:
        accepted_response = client.post(
            "/api/v1/control/runs/nl",
            json={
                "request": raw_request,
                "llm_model": model_id,
                "context": {
                    "evaluation_safety_attempt": _valid_intake_for_mode("simulate_only").model_dump(
                        mode="json"
                    )
                },
            },
        )
        assert accepted_response.status_code == 200, accepted_response.text
        accepted = accepted_response.json()
        assert accepted["status"] == "accepted"
        service = first_app.state._control_service
        assert service._cycle_substrate_context_admission_owner is not None
        assert service._cycle_substrate_context_admission_owner.store is first_context.store
        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=accepted["job_id"],
            )
            == accepted["job_id"]
        )

        completed = service._control_store.get_job(accepted["job_id"])
        assert completed is not None and completed.state == "completed"
        assert completed.run_id is not None
        assert len(compiled_problems) == 1
        assert profile.profile_selection_ref == cycle_job_profile_selection_ref(
            compiled_problems[0]
        )
        assert len(n5_calls) == 1
        input_record, simulation = n5_calls[0]
        assert type(input_record) is CandidateSimulationN5InputV5
        assert input_record.authority_purpose == "candidate_scenario_n5_only"
        with tenant_scope(None, tenant_id=_TENANT_ID, cell_id=_CELL_ID):
            n4_source = GenerationSourceRepository(
                store=first_context.store
            ).load_candidate_scenario_source_for_n5(
                input_record.n4_source_ref,
                expected_run_id=completed.run_id,
                expected_job_id=completed.job_id,
                expected_tenant_id=_TENANT_ID,
                expected_cell_id=_CELL_ID,
            )
        n4_source_v2 = (
            n4_source.source_record
            if type(n4_source) is N4CandidateScenarioSourceRecordV3
            else n4_source
        )
        assert type(n4_source_v2) is N4CandidateScenarioSourceRecordV2
        n4_candidate = n4_source_v2.source_record.candidate
        assert n4_candidate is not None
        derived_atom = input_record.materialization.derived_n5_atom
        assert derived_atom == derive_candidate_scenario_atom(
            n4_candidate.atom,
            target_world_slot=input_record.materialization.target_world_slot,
            value=input_record.materialization.value,
        )
        assert derived_atom.intervention_id == n4_candidate.atom.intervention_id
        assert derived_atom.content_hash != n4_candidate.atom.content_hash
        assert simulation.status == "joint_simulated"
        assert simulation.uncertainty_kind == "K_sim"
        assert simulation.simulation_result_ref is not None
        assert simulation.world_model_record is not None
        assert len(n8_calls) == 1
        first_value = n8_calls[0]["observation"]
        assert first_value.status == "value_conditional"
        assert "candidate_scenario_n5_only" in first_value.authority_blockers
        assert first_value.evaluation_mode == "simulate_only"
        assert first_value.decision_grade == "low"
        assert first_value.value_receipt is None
        assert first_value.method_selection_receipt is None
        assert n9_calls == []

        event = service._control_store.get_job_created_event_payload(completed.job_id)
        scope = _control_job_execution_scope_from_event(event)
        assert scope.status == "established"
        assert (scope.tenant_id, scope.cell_id) == (_TENANT_ID, _CELL_ID)
        compiled_ref_value = completed.progress.get(
            "compiled_recursive_generation_cycle_artifact_ref"
        ) or completed.progress.get("compiled_recursive_generation_cycle_ref")
        assert compiled_ref_value is not None
        compiled_ref = ArtifactRef.model_validate(compiled_ref_value)
        with tenant_scope(None, tenant_id=scope.tenant_id, cell_id=scope.cell_id):
            compiled_bytes = service._artifact_store.get_bytes(compiled_ref)
        compiled_run = CompiledRecursiveGenerationCycleRun.model_validate(
            canon.from_canonical_bytes(compiled_bytes)
        )
        selected_cycles = tuple(
            cycle
            for leaf in compiled_run.recursive_run.leaf_nodes
            if leaf.cycle_run is not None
            for cycle in leaf.cycle_run.cycles
            if cycle.simulation.diagnostics.get("candidate_simulation_purpose")
            == "candidate_scenario_n5_only"
        )
        assert len(selected_cycles) == 1
        selected_cycle = selected_cycles[0]
        diagnostics = selected_cycle.simulation.diagnostics
        assert selected_cycle.selected_candidate_ref == input_record.original_candidate_id
        assert (
            selected_cycle.selected_candidate_content_hash == input_record.original_candidate_hash
        )
        assert diagnostics["candidate_simulation_profile_ref"] == input_record.profile_config_ref
        execution_ref = ArtifactRef.model_validate(
            diagnostics["candidate_simulation_execution_selected_ref"]
        )
        assert str(execution_ref.artifact_id) == diagnostics["candidate_simulation_execution_ref"]
        assert artifact_ref_identity_key(
            selected_cycle.simulation.simulation_result_ref
        ) == artifact_ref_identity_key(simulation.simulation_result_ref)

    # Rebuild the read-side app and CAS owner. The GET must resolve and consume
    # N5 again instead of trusting the value_port status stored in the cycle.
    fresh_context = build_runtime_api_context(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
    )
    fresh_app = create_runtime_api_app(
        cas_root=cas_root,
        container_overrides=RuntimeContainerOverrides(runtime_api_context=fresh_context),
        allow_fixture_identity=True,
        candidate_simulation_profiles=(profile,),
        candidate_simulation_model_declarations=(model_declaration,),
    )
    run_path = f"/api/v1/runs/{completed.run_id}"
    with TestClient(fresh_app) as fresh_client:
        response = fresh_client.get(run_path)
        assert response.status_code == 200, response.text
        run = response.json()["run"]
        values = run["conditional_simulation_values"]
        assert len(values) == 1
        row = values[0]
        assert row["candidate_id"] == input_record.original_candidate_id
        assert row["job_id"] == completed.job_id
        assert row["run_id"] == completed.run_id
        assert row["profile_config_ref"] == input_record.profile_config_ref
        assert row["world_model_record_content_hash"] == (
            input_record.materialization.world_model_record_hash
        )
        projected_result_ref = ArtifactRef.model_validate(row["n5_result_ref"])
        assert artifact_ref_identity_key(projected_result_ref) == artifact_ref_identity_key(
            simulation.simulation_result_ref
        )
        observation = row["observation"]
        assert observation["status"] == "value_conditional"
        assert "candidate_scenario_n5_only" in observation["authority_blockers"]
        assert observation["evaluation_mode"] == "simulate_only"
        assert observation["predicate_basis"] == "recomputed"
        assert observation["authority_purpose"] == "conditional_simulation_only"
        assert len(n8_calls) == 2
        assert n9_calls == []

        # A sibling candidate hash in the selected cycle cannot borrow this
        # run's otherwise-valid N5 execution or reach the N8 consumer.
        candidate_leaf = next(
            leaf
            for leaf in compiled_run.recursive_run.leaf_nodes
            if leaf.cycle_run is not None and selected_cycle in leaf.cycle_run.cycles
        )
        candidate_leaf_run = candidate_leaf.cycle_run
        assert candidate_leaf_run is not None
        mismatched_cycle = selected_cycle.model_copy(
            update={"selected_candidate_content_hash": "sha256:" + "0" * 64}
        )
        mismatched_leaf_run = candidate_leaf_run.model_copy(
            update={
                "cycles": tuple(
                    mismatched_cycle if cycle == selected_cycle else cycle
                    for cycle in candidate_leaf_run.cycles
                )
            }
        )
        mismatched_nodes = tuple(
            node.model_copy(update={"cycle_run": mismatched_leaf_run})
            if node.node_ref == candidate_leaf.node_ref
            else node
            for node in compiled_run.recursive_run.nodes
        )
        sibling_hash_run = compiled_run.recursive_run.model_copy(update={"nodes": mismatched_nodes})
        replay_owner = fresh_app.state._control_service
        with tenant_scope(None, tenant_id=scope.tenant_id, cell_id=scope.cell_id):
            sibling_hash_rows = replay_conditional_simulation_values(
                sibling_hash_run,
                store=fresh_context.store,
                context_owner=CycleSubstrateContextArtifactOwner(store=fresh_context.store),
                admission_owner=replay_owner._cycle_substrate_context_admission_owner,
                expected_job_id=completed.job_id,
                expected_run_id=completed.run_id,
                expected_tenant_id=_TENANT_ID,
                expected_cell_id=_CELL_ID,
            )
        assert len(sibling_hash_rows) == 1
        assert sibling_hash_rows[0].projection_source == "not_established"
        assert sibling_hash_rows[0].observation.status == "value_blocked"
        assert len(n8_calls) == 2
        fallback_atom_cycle = selected_cycle.model_copy(
            update={"selected_candidate_ref": "candidate_ffffffffffffffff"}
        )
        fallback_leaf_run = candidate_leaf_run.model_copy(
            update={
                "cycles": tuple(
                    fallback_atom_cycle if cycle == selected_cycle else cycle
                    for cycle in candidate_leaf_run.cycles
                )
            }
        )
        fallback_nodes = tuple(
            node.model_copy(update={"cycle_run": fallback_leaf_run})
            if node.node_ref == candidate_leaf.node_ref
            else node
            for node in compiled_run.recursive_run.nodes
        )
        fallback_atom_run = compiled_run.recursive_run.model_copy(update={"nodes": fallback_nodes})
        with tenant_scope(None, tenant_id=scope.tenant_id, cell_id=scope.cell_id):
            fallback_atom_rows = replay_conditional_simulation_values(
                fallback_atom_run,
                store=fresh_context.store,
                context_owner=CycleSubstrateContextArtifactOwner(store=fresh_context.store),
                admission_owner=replay_owner._cycle_substrate_context_admission_owner,
                expected_job_id=completed.job_id,
                expected_run_id=completed.run_id,
                expected_tenant_id=_TENANT_ID,
                expected_cell_id=_CELL_ID,
            )
        assert len(fallback_atom_rows) == 1
        assert fallback_atom_rows[0].projection_source == "not_established"
        assert fallback_atom_rows[0].observation.status == "value_blocked"
        assert len(n8_calls) == 2

        # A different server-configured profile for the same problem cannot
        # reinterpret the persisted candidate run on the ordinary GET surface.
        foreign_profile_payload = profile.model_dump(mode="json", exclude={"content_hash"})
        foreign_profile_payload["profile_id"] = f"{profile.profile_id}.foreign"
        foreign_profile_payload["content_hash"] = gy_content_hash(foreign_profile_payload)
        foreign_profile = CandidateSimulationScenarioProfile.model_validate(foreign_profile_payload)
        foreign_declaration_payload = model_declaration.model_dump(
            mode="json", exclude={"content_hash"}
        )
        foreign_declaration_payload.update(
            {
                "profile_config_ref": candidate_simulation_profile_ref(foreign_profile),
                "profile_content_hash": foreign_profile.content_hash,
                "profile_selection_ref": foreign_profile.profile_selection_ref,
            }
        )
        foreign_declaration_payload["content_hash"] = gy_content_hash(foreign_declaration_payload)
        foreign_declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
            foreign_declaration_payload
        )
        foreign_profile_context = build_runtime_api_context(
            cas_root=cas_root,
            core_runs_root=cas_root / "runs",
        )
        foreign_profile_app = create_runtime_api_app(
            cas_root=cas_root,
            container_overrides=RuntimeContainerOverrides(
                runtime_api_context=foreign_profile_context
            ),
            allow_fixture_identity=True,
            candidate_simulation_profiles=(foreign_profile,),
            candidate_simulation_model_declarations=(foreign_declaration,),
        )
        with TestClient(foreign_profile_app) as foreign_profile_client:
            foreign_profile_response = foreign_profile_client.get(run_path)
        assert foreign_profile_response.status_code == 200
        foreign_profile_value = foreign_profile_response.json()["run"][
            "conditional_simulation_values"
        ][0]["observation"]
        assert foreign_profile_value["status"] == "value_blocked"
        assert foreign_profile_value["value_ref"] is None
        assert foreign_profile_value["predicate_basis"] == "not_established"
        assert len(n8_calls) == 2

        # A persisted result for the configured outcome cannot be re-used for
        # a different outcome merely because the same candidate and WMR remain.
        from polisyos.runtime.quality.generation_cycle import ValuePortObservation

        first_n8_input = n8_calls[0]
        original_problem = first_n8_input["problem"]
        candidate = first_n8_input["candidate"]
        n5_simulation = first_n8_input["simulation"]
        unknown_outcome = original_problem.outcome_of_interest.model_copy(
            update={"target_variable": "unknown.outcome"}
        )
        mismatched_problem = original_problem.model_copy(
            update={"outcome_of_interest": unknown_outcome}
        )
        with tenant_scope(None, tenant_id=scope.tenant_id, cell_id=scope.cell_id):
            refused_unknown_outcome = _DefaultSimulationBoundFoundryValuePort(
                repo_root=None,
                cycle_substrate_context=None,
                artifact_store=fresh_context.store,
            )(
                candidate=candidate,
                simulation=n5_simulation,
                problem=mismatched_problem,
                cycle_index=int(first_n8_input["cycle_index"]),
            )
        assert type(refused_unknown_outcome) is ValuePortObservation
        assert refused_unknown_outcome.status == "value_blocked"
        assert refused_unknown_outcome.value_ref is None
        assert any("outcome" in item for item in refused_unknown_outcome.authority_blockers)
        assert n9_calls == []

        # A different tenant cannot use the new projection surface to read the
        # run. The fixture identity remains signed by the ordinary auth middleware.
        foreign_claims = build_fixture_identity_claims().model_copy(
            update={"tenant_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "cell_id": "cell-b"}
        )
        monkeypatch.setattr(
            jwt_auth_middleware,
            "build_fixture_identity_claims",
            lambda: foreign_claims,
        )
        foreign = fresh_client.get(
            run_path,
            headers={"X-Tenant-ID": foreign_claims.tenant_id},
        )
        assert foreign.status_code == 403
        assert foreign.json()["code"] == "tenant_not_found"

        # The same ordinary launch route still denies a principal without the
        # required run-launch permission before a job or candidate is created.
        viewer_claims = build_fixture_identity_claims().model_copy(
            update={
                "roles": frozenset({PolicyOSRole.VIEWER}),
                "tenant_id": _TENANT_ID,
                "cell_id": _CELL_ID,
            }
        )
        monkeypatch.setattr(
            jwt_auth_middleware,
            "build_fixture_identity_claims",
            lambda: viewer_claims,
        )
        denied = fresh_client.post(
            "/api/v1/control/runs/nl",
            json={
                "request": raw_request,
                "llm_model": model_id,
                "context": {
                    "evaluation_safety_attempt": _valid_intake_for_mode("simulate_only").model_dump(
                        mode="json"
                    )
                },
            },
            headers={"X-Tenant-ID": _TENANT_ID},
        )
        assert denied.status_code == 403
        assert denied.json()["code"] == "action_permission_denied"

        # Corrupt only the bytes returned for the selected N5 result. The
        # content-addressed readback must refuse a conditional projection.
        result_id = str(simulation.simulation_result_ref.artifact_id)
        original_get_bytes = fresh_context.store.get_bytes

        def return_tampered_result(ref: object) -> bytes:
            body = original_get_bytes(ref)
            ref_id = str(getattr(ref, "artifact_id", ref))
            return body + b" " if ref_id == result_id else body

        monkeypatch.setattr(fresh_context.store, "get_bytes", return_tampered_result)
        tampered = fresh_client.get(run_path)
        assert tampered.status_code == 200, tampered.text
        tampered_values = tampered.json()["run"]["conditional_simulation_values"]
        assert len(tampered_values) == 1
        assert tampered_values[0]["observation"]["status"] == "value_blocked"
        assert tampered_values[0]["observation"]["value_ref"] is None
        assert tampered_values[0]["observation"]["predicate_basis"] == "not_established"
        assert n9_calls == []
