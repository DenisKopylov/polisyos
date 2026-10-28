from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests._helpers.controlled_candidate_profile import (
    ControlledCandidateGateway,
    _configured_procurement_profile,
    _current_compiler_problem,
    _seed_controlled_selected_skg_source,
)
from tests._helpers.generic_n4_served_replay import (
    _RECORDING_ID,
    REPO_ROOT,
    _generic_profile_for_selection,
)
from tools.quality.validation import (
    check_layer3_gy_design_generation_contract as n4_contract,
)


def test_contract_testing_source_attempt_setting_is_dev_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deployment profile cannot turn on the candidate-only test lane."""
    pytest.importorskip("fastapi")
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.execution_policy import RuntimeBootstrapError

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "research")
    with pytest.raises(
        RuntimeBootstrapError,
        match="Contract-testing Credal source attempts are restricted to the dev profile",
    ):
        create_runtime_api_app(enable_contract_testing_credal_source_attempts=True)


@pytest.fixture
def candidate_gateway(monkeypatch: pytest.MonkeyPatch):
    """Use a controlled compiler and preserve the actual terminal N4 source."""
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
def test_terminal_n4_attempt_stays_candidate_only_through_fresh_get(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    candidate_gateway: ControlledCandidateGateway,
) -> None:
    """An actual terminal N4 source is retained without a K_ref or authority claim."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.security import build_fixture_identity_claims
    from polisyos.runtime.http.services.control import generation_cycle as generation_cycle_service
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextOwnerError,
        VerifiedNLJobScope,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.substrate_registry import persist_substrate_registry
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests.unit.runtime.http.test_control_job_execution_intent import (
        _valid_intake_for_mode,
    )
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
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
    problem = _current_compiler_problem(recording)
    candidate_gateway.set_fixture(recording, problem=problem)
    model_id = str(recording["model_id"])
    fixture_claims = build_fixture_identity_claims()
    tenant_id = fixture_claims.tenant_id
    cell_id = fixture_claims.cell_id
    assert tenant_id and cell_id
    cas_root = tmp_path / ".polisyos"
    runtime_api_context = build_runtime_api_context(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
    )
    source_root = tmp_path / "credal-candidate-source"
    selected_skg_source = _seed_controlled_selected_skg_source(
        tmp_path,
        source_root=source_root,
        recorded_problem=problem,
    )
    base_profile, base_declaration = _configured_procurement_profile(
        recorded_problem=problem,
        tmp_path=tmp_path,
        source_root=source_root,
        selected_skg_source=selected_skg_source,
        artifact_store=runtime_api_context.store,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )
    base_inputs = base_profile.context_inputs
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        substrate_registry_ref = persist_substrate_registry(
            runtime_api_context.store,
            base_inputs.substrate_registry,
        )
    root_profile = _generic_profile_for_selection(
        tmp_path=tmp_path,
        source_root=source_root,
        selected_skg_source=selected_skg_source,
        base_profile=base_profile,
        base_declaration=base_declaration,
        profile_id="v6-credal-root",
        profile_selection_ref=cycle_job_profile_selection_ref(problem),
        profile_selection_kind="problem",
        target_world_slot=base_profile.rule.target_world_slot,
        operator_kind=base_profile.rule.operator_kind,
        store=runtime_api_context.store,
        substrate_registry_ref=substrate_registry_ref,
        tenant_id=tenant_id,
        cell_id=cell_id,
    )

    original_compiler = generation_cycle_service.build_design_problem_from_nl_request

    async def deterministic_compiler(**kwargs: Any):
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        return await original_compiler(**kwargs)

    monkeypatch.setattr(
        generation_cycle_service,
        "build_design_problem_from_nl_request",
        deterministic_compiler,
    )
    app = create_runtime_api_app(
        cas_root=cas_root,
        container_overrides=RuntimeContainerOverrides(runtime_api_context=runtime_api_context),
        allow_fixture_identity=True,
        generic_cycle_simulation_profiles=(root_profile,),
        generic_cycle_simulation_root_profile_id=root_profile.profile_id,
        enable_contract_testing_credal_source_attempts=True,
    )
    with TestClient(app) as client:
        accepted_response = client.post(
            "/api/v1/control/runs/nl",
            headers={"Idempotency-Key": "test-r216-18b79c44c24f4676a2ec907bc7954430"},
            json={
                "request": problem.nl_provenance.raw_request,
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
        service = app.state._control_service
        compiler_route_observations: list[dict[str, Any]] = []
        original_compile_route = service.compile_and_run_recursive_generation_cycle

        async def observe_compile_route(**kwargs: Any) -> Any:
            compiler_route_observations.append(
                {
                    "n4_proposal_only": kwargs["n4_proposal_only"],
                    "generic_cycle_simulation_handoff_resolver": kwargs[
                        "generic_cycle_simulation_handoff_resolver"
                    ],
                    "verified_nl_job_scope": kwargs["verified_nl_job_scope"],
                }
            )
            return await original_compile_route(**kwargs)

        monkeypatch.setattr(
            service,
            "compile_and_run_recursive_generation_cycle",
            observe_compile_route,
        )
        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=accepted["job_id"],
            )
            == accepted["job_id"]
        )
        job = service._control_store.get_job(accepted["job_id"])
        assert job is not None and job.state == "completed"
        assert len(compiler_route_observations) == 1
        route = compiler_route_observations[0]
        assert route["n4_proposal_only"] is False
        assert callable(route["generic_cycle_simulation_handoff_resolver"])
        verified_scope = route["verified_nl_job_scope"]
        assert type(verified_scope) is VerifiedNLJobScope
        assert verified_scope._was_issued_by_verified_nl_execution_owner
        assert verified_scope.tenant_id == tenant_id
        assert verified_scope.cell_id == cell_id

        admission_owner = service._generic_cycle_simulation_admission_owner
        assert admission_owner is not None
        with pytest.raises(
            CycleSubstrateContextOwnerError,
            match="generic_cycle_simulation_verified_worker_scope_not_established",
        ):
            admission_owner.admit_context(
                generic_simulation_profile_id=root_profile.profile_id,
                problem=problem,
                job_id=accepted["job_id"],
                run_id=str(job.run_id),
                tenant_id=tenant_id,
                cell_id="cell-v6-credal-attempt",
                verified_nl_job_scope=verified_scope,
            )

        run_id = job.progress["core_run_id"]

        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            compiled = CompiledRecursiveGenerationCycleRun.model_validate(
                from_canonical_bytes(
                    service._artifact_store.get_bytes(
                        job.progress["compiled_recursive_generation_cycle_ref"]
                    )
                )
            )
        handoff = compiled.generic_cycle_simulation_handoff
        source_ref = compiled.n4_recursive_source_ref
        assert handoff is not None
        assert source_ref is not None
        assert handoff.n4_child_profile_family_ref is None
        assert compiled.n4_recursive_source_result_status == "generation_unavailable"
        assert compiled.n4_credal_source_attempt_ref is not None
        assert compiled.n4_credal_source_attempt_ref.manifest_profile_sha256 is not None
        source_repository = GenerationSourceRepository(runtime_api_context.store)
        assert compiled.n4_recursive_source_run_id is not None
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            source = source_repository.load(
                source_ref,
                run_id=compiled.n4_recursive_source_run_id,
                expected_run_id=handoff.run_id,
                expected_job_id=handoff.job_id,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
                context_job_ref=handoff.context_job_ref,
                profile_ref=handoff.profile_ref,
                n4_child_profile_family_ref=handoff.n4_child_profile_family_ref,
            )
        assert source.problem == compiled.design_problem
        assert source.cycle_substrate_context == handoff.context
        assert source.generation_result.status == "generation_unavailable"
        assert source.generation_result.preflight.status == "supported"
        assert source.generation_result.lever_space_prompt_slice.status == "unavailable"
        assert (
            source.generation_result.lever_space_prompt_slice.failure_reason
            == "credal_reference_unavailable:ValueError"
        )
        assert source.generation_result.candidates == ()
        assert source.generation_result.grounding_dispositions == ()
        assert source.candidate_sources == ()
        assert source.credal_reference_payload is None
        assert source.reference() is None
        with (
            tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id),
            pytest.raises(
                ValueError,
                match="generation_source_generic_child_family_input_ref_invalid",
            ),
        ):
            source_repository.load(
                source_ref,
                run_id=compiled.n4_recursive_source_run_id,
                expected_run_id=handoff.run_id,
                expected_job_id=handoff.job_id,
                expected_tenant_id=tenant_id,
                expected_cell_id=cell_id,
                context_job_ref=handoff.context_job_ref,
                profile_ref=handoff.profile_ref,
                n4_child_profile_family_ref=source_ref,
            )

        details = client.get(f"/api/v1/runs/{run_id}")
        assert details.status_code == 200, details.text
        projection = details.json()["run"]["generic_cycle_simulation"]
        assert projection["artifact_status"] == "resolved"
        assert projection["authority_purpose"] == "cycle_input_candidate_only"
        assert projection["publication_authority"] is False
        assert projection["currentness_status"] == "not_established"
        assert projection["n4_source_status"] == "resolved"
        assert projection["child_profile_status"] == "not_established"
        assert projection.get("child_profile_family_ref") is None
        assert projection["child_profile_limitation_code"] == (
            "generic_n4_source_generation_not_complete"
        )
        assert projection["credal_source_status"] == "not_established"
        assert projection["credal_source_limitation_code"] == (
            "candidate_source_authority_not_established"
        )
        assert projection["credal_source_attempt_ref"]["kind"] == (
            "runtime.quality.candidate_credal_source_attempt"
        )
        assert projection["credal_source_attempt_ref"]["artifact_id"] == str(
            compiled.n4_credal_source_attempt_ref.artifact_id
        )
        assert projection["credal_source_attempt_ref"]["manifest_profile_sha256"] == (
            compiled.n4_credal_source_attempt_ref.manifest_profile_sha256
        )
        assert projection["n5_observations"] == []
        assert "credal_reference_ref" not in projection
        checkpoint = projection["recursive_cycle_checkpoint"]

        attempt_ref = projection["credal_source_attempt_ref"]
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            blob_path, _manifest_path = service._artifact_store._paths(
                ArtifactID.model_validate(attempt_ref["artifact_id"])
            )
            blob_path.write_bytes(b"corrupt-candidate-source-attempt")

        tampered = client.get(f"/api/v1/runs/{run_id}")
        assert tampered.status_code == 200, tampered.text
        tampered_projection = tampered.json()["run"]["generic_cycle_simulation"]
        assert tampered_projection["credal_source_status"] == "not_established"
        assert tampered_projection["credal_source_limitation_code"] == (
            "candidate_source_attempt_replay_not_established"
        )
        assert tampered_projection["n5_observations"] == []
        assert tampered_projection["recursive_cycle_checkpoint"] == checkpoint
