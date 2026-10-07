"""Manual candidate-only N5 CAS producer consumed by a fresh RunDetails GET.

This is a bounded owner/consumer integration fixture, not evidence that the
ordinary POST worker completes N4/N5 against the production L6 bundle. It uses
the recorded N4 proposal-only path (which does not invoke K_ref), the configured
synthetic candidate profile, the real V5 source/input/execution owners, the
canonical N5 port, Core's owned compiled artifact, and the ordinary fresh GET
consumer. Candidate-only values remain limited and cannot carry N9 authority.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from tests._helpers.controlled_candidate_profile import (
    _candidate_only_procurement_intervention_bundle,
    _configured_procurement_profile,
    _controlled_procurement_recording,
    _current_compiler_problem,
)
from tools.quality.validation import (
    check_layer3_gy_design_generation_contract as n4_contract,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
RECORDING_ID = "gy_n4_cgf_decisive_capture_1_20260704_092222_049411"
TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
CELL_ID = "cell-a"


@pytest.mark.integration
def test_manual_n5_interaction_evidence_is_recomputed_by_fresh_run_details_get(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fresh GET replays the actual one-atom N5 trajectory and its bounded grid."""

    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core import canon
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.security import build_fixture_identity_claims
    from polisyos.runtime.http.services.control.generation_cycle import (
        COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationContextHandoff,
        CandidateSimulationContextOffer,
        CandidateSimulationN5InputV5,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextArtifactOwner,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.design_axes.coupling_composition import (
        derive_recursive_design_graph,
    )
    from polisyos.runtime.quality.design_generation import (
        N4CandidateProposalSource,
        N4CandidateScenarioProposalRun,
        generate_design_candidate_proposal_under_a,
    )
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        JointSimulationPort,
        ValuePortObservation,
        _DefaultSimulationBoundFoundryValuePort,
        load_joint_simulation_result,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationResult
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveCycleBudget,
        RecursiveGenerationCycleController,
        RecursiveGenerationCycleRun,
    )
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests.integration.core_runtime.test_e02_informative_voi_execution import (
        _bounded_budget,
    )
    from tests.unit.runtime.http.test_control_job_execution_intent import (
        _valid_intake_for_mode,
    )

    @contextmanager
    def owner_scoped_test_client(app: Any) -> Iterator[Any]:
        """Keep the fixture tenant active while each app owns its runtime store."""

        with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID), TestClient(app) as client:
            yield client

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv(
        "POLISYOS_CONTROL_SQLITE_PATH", (tmp_path / "control.sqlite3").as_posix()
    )
    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())
    monkeypatch.setenv("JAX_PLATFORMS", "cpu")
    monkeypatch.setenv("OMP_NUM_THREADS", "1")

    from tests._helpers.bounded_run_catalog import bind_bounded_run_api_catalog

    bind_bounded_run_api_catalog(tmp_path=tmp_path, monkeypatch=monkeypatch)

    recording = next(
        item
        for item in n4_contract._load_recordings(REPO_ROOT)
        if item.get("design_problem_id") == RECORDING_ID
    )
    problem = _current_compiler_problem(recording)
    raw_request = problem.nl_provenance.raw_request
    model_id = str(recording["model_id"])
    controlled_recording = _controlled_procurement_recording(
        recording,
        outcome_variable=problem.outcome_of_interest.target_variable,
    )

    cas_root = tmp_path / ".polisyos"
    first_context = build_runtime_api_context(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
    )
    profile, model_declaration = _configured_procurement_profile(
        recorded_problem=problem,
        artifact_store=first_context.store,
        tenant_id=TENANT_ID,
        cell_id=CELL_ID,
        intervention_substrate=_candidate_only_procurement_intervention_bundle(),
    )
    assert profile.profile_selection_ref == cycle_job_profile_selection_ref(problem)
    assert profile.context_inputs.intervention_substrate is not None

    first_app = create_runtime_api_app(
        cas_root=cas_root,
        container_overrides=RuntimeContainerOverrides(runtime_api_context=first_context),
        allow_fixture_identity=True,
        candidate_simulation_profiles=(profile,),
        candidate_simulation_model_declarations=(model_declaration,),
    )
    n5_calls: list[str] = []
    n8_calls: list[ValuePortObservation] = []
    original_n5 = JointSimulationPort.__call__
    original_n8 = _DefaultSimulationBoundFoundryValuePort.__call__

    def observe_n5(port: object, *args: Any, **kwargs: Any) -> object:
        candidate = kwargs.get("candidate")
        n5_calls.append(str(getattr(candidate, "candidate_id", "")))
        return original_n5(port, *args, **kwargs)

    def observe_n8(
        port: object, *args: Any, **kwargs: Any
    ) -> ValuePortObservation:
        observation = original_n8(port, *args, **kwargs)
        assert isinstance(observation, ValuePortObservation)
        n8_calls.append(observation)
        return observation

    monkeypatch.setattr(JointSimulationPort, "__call__", observe_n5)
    monkeypatch.setattr(_DefaultSimulationBoundFoundryValuePort, "__call__", observe_n8)

    with owner_scoped_test_client(first_app) as client:
        accepted_response = client.post(
            "/api/v1/control/runs/nl",
            json={
                "request": raw_request,
                "llm_model": model_id,
                "context": {
                    "evaluation_safety_attempt": _valid_intake_for_mode(
                        "simulate_only"
                    ).model_dump(mode="json")
                },
            },
        )
        assert accepted_response.status_code == 200, accepted_response.text
        accepted = accepted_response.json()
        assert accepted["status"] == "accepted"
        service = first_app.state._control_service
        admission_owner = service._cycle_substrate_context_admission_owner
        assert admission_owner is not None
        assert admission_owner.store is first_context.store

        compiled_refs: dict[str, ArtifactRef] = {}
        produced_inputs: dict[str, CandidateSimulationN5InputV5] = {}
        produced_results: dict[str, JointSimulationResult] = {}
        produced_world_model_ids: dict[str, str] = {}
        produced_result_refs: dict[str, ArtifactRef] = {}

        def produce_manual_candidate_run_for_owned_job(_snapshot: object) -> None:
            admission = service._control_store.current_execution_job_admission()
            job = admission.job
            scope = admission.scope
            assert job.job_id == accepted["job_id"]
            assert job.kind == "natural_language_run"
            assert scope.status == "established"
            assert (scope.tenant_id, scope.cell_id) == (TENANT_ID, CELL_ID)

            with service._install_execution_scope(scope):
                core_run_id, core_context = service._start_generation_run_context(
                    job=job,
                    execution_scope=scope,
                )
                context_owner = CycleSubstrateContextArtifactOwner(
                    store=service._artifact_store,
                    control_store=service._control_store,
                )
                offer = admission_owner.admit_context(
                    problem=problem,
                    job_id=job.job_id,
                    run_id=str(job.run_id),
                    tenant_id=TENANT_ID,
                    cell_id=CELL_ID,
                )
                assert type(offer) is CandidateSimulationContextOffer
                context_ref = context_owner.persist_for_current_job(
                    offer.context,
                    problem=problem,
                )
                resolved_context = context_owner.resolve_for_current_job(
                    context_ref,
                    problem=problem,
                )
                assert resolved_context.context == offer.context
                handoff = CandidateSimulationContextHandoff(
                    context=resolved_context.context,
                    context_job_ref=context_ref,
                    profile=offer.profile,
                    profile_config_ref=offer.profile_config_ref,
                    job_id=job.job_id,
                    run_id=str(job.run_id),
                    tenant_id=TENANT_ID,
                    cell_id=CELL_ID,
                    model_declaration=offer.model_declaration,
                    model_declaration_ref=offer.model_declaration_ref,
                    ncm_ref=offer.ncm_ref,
                )

                def current_owner_binding_is_exact() -> bool:
                    try:
                        current = service._control_store.current_execution_job_admission()
                        current_context = context_owner.resolve_for_current_job(
                            context_ref,
                            problem=problem,
                        )
                        current_offer = admission_owner.admit_context(
                            problem=problem,
                            job_id=job.job_id,
                            run_id=str(job.run_id),
                            tenant_id=TENANT_ID,
                            cell_id=CELL_ID,
                        )
                    except (OSError, RuntimeError, TypeError, ValueError):
                        return False
                    return (
                        type(current_offer) is CandidateSimulationContextOffer
                        and current.job.job_id == handoff.job_id
                        and current.job.run_id == handoff.run_id
                        and current.job.state == "running"
                        and current.job.attempt == job.attempt
                        and current.scope.status == "established"
                        and (current.scope.tenant_id, current.scope.cell_id)
                        == (handoff.tenant_id, handoff.cell_id)
                        and current_context.context == handoff.context
                        and current_offer.context == handoff.context
                        and current_offer.profile == handoff.profile
                        and current_offer.profile_config_ref == handoff.profile_config_ref
                        and current_offer.model_declaration == handoff.model_declaration
                        and current_offer.model_declaration_ref
                        == handoff.model_declaration_ref
                        and current_offer.ncm_ref == handoff.ncm_ref
                    )

                proposal = asyncio.run(
                    generate_design_candidate_proposal_under_a(
                        problem,
                        model_id=model_id,
                        llm_client=n4_contract.RecordedGenerationReplayClient(
                            controlled_recording
                        ),
                        repo_root=REPO_ROOT,
                    )
                )
                assert type(proposal) is N4CandidateProposalSource
                proposal_run = N4CandidateScenarioProposalRun(
                    proposal=proposal,
                    l2_confidence_vintage=None,
                    k_ref_limitation_code="candidate_scenario_l2_not_consumed",
                )
                root_ref = (
                    "design-problem://"
                    + gy_content_hash(problem.model_dump(mode="json")).removeprefix("sha256:")
                )
                graph = derive_recursive_design_graph(
                    design_ref=root_ref,
                    module_refs=(),
                    parent_child_edges=(),
                    rule_version_ref="polisyos.runtime.recursive_generation_cycle.v1",
                )

                def build_cycle_controller(node_ref: str, node_problem: object) -> Any:
                    assert node_ref == root_ref
                    assert node_problem == problem

                    def replay_recorded_proposal(
                        replay_problem: object,
                        *,
                        cycle_index: int,
                    ) -> N4CandidateScenarioProposalRun:
                        assert replay_problem == problem
                        assert cycle_index == 0
                        return proposal_run

                    return GenerationCycleController(
                        generation_port=replay_recorded_proposal,
                        repo_root=REPO_ROOT,
                        artifact_store=service._artifact_store,
                        cycle_substrate_context=handoff.context,
                        candidate_simulation_handoff=handoff,
                        candidate_simulation_currentness_resolver=(
                            current_owner_binding_is_exact
                        ),
                        promotion_runtime=service._promotion_runtime,
                        eval_safety_verifier=(
                            service._evaluation_safety_admission_verifier
                        ),
                    )

                recursive_controller = (
                    RecursiveGenerationCycleController.for_contract_testing(
                        cycle_controller_factory=build_cycle_controller,
                        repo_root=REPO_ROOT,
                        artifact_store=service._artifact_store,
                    )
                )
                recursive_run = asyncio.run(
                    recursive_controller.run(
                        graph,
                        problems_by_node={root_ref: problem},
                        budget_state=_bounded_budget("1.0"),
                        recursive_budget=RecursiveCycleBudget(
                            max_depth=0,
                            max_nodes=1,
                            min_cycles_per_leaf=1,
                            max_cycles_per_leaf=1,
                        ),
                        cycle_substrate_contexts_by_node={
                            root_ref: handoff.context,
                        },
                        execution_intents_by_node={root_ref: "simulate_only"},
                    )
                )
                assert type(recursive_run) is RecursiveGenerationCycleRun
                assert recursive_run.authority_scope == "contract_testing"
                leaf = recursive_run.leaf_nodes[0]
                assert leaf.cycle_run is not None
                cycle = leaf.cycle_run.cycles[0]
                assert cycle.simulation.status == "joint_simulated"
                assert cycle.value_port.status == "value_conditional"
                assert not cycle.promotion_port.receipts
                assert not any(
                    summary.certified_by_n9
                    for summary in leaf.cycle_run.candidate_summaries
                )

                diagnostics = cycle.simulation.diagnostics
                input_ref = ArtifactRef.model_validate(
                    diagnostics["candidate_simulation_n5_input_selected_ref"]
                )
                with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
                    input_record = CandidateSimulationN5InputV5.model_validate(
                        canon.from_canonical_bytes(
                            service._artifact_store.get_bytes(input_ref)
                        )
                    )
                    result_ref = cycle.simulation.simulation_result_ref
                    assert result_ref is not None
                    result = load_joint_simulation_result(
                        result_ref,
                        store=service._artifact_store,
                    )
                assert result.atom_ids == (
                    input_record.materialization.derived_n5_atom.intervention_id,
                )
                assert result.selected_outcomes == (input_record.outcome_variable,)
                compiled_payload: dict[str, object] = {
                    "schema_version": COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
                    "design_problem_ref": gy_content_hash(
                        problem.model_dump(mode="json")
                    ),
                    "design_problem": problem.model_dump(mode="json"),
                    "cycle_substrate_context_ref": handoff.context.content_hash,
                    "recursive_run": recursive_run.model_dump(
                        mode="json",
                        exclude={"leaf_nodes"},
                    ),
                }
                compiled = CompiledRecursiveGenerationCycleRun.model_validate(
                    {
                        **compiled_payload,
                        "recursive_run": recursive_run,
                        "content_hash": gy_content_hash(compiled_payload),
                    }
                )
                compiled_ref = service._put_json_artifact_ref(
                    compiled.model_dump(mode="json"),
                    kind="runtime.compiled_recursive_generation_cycle",
                    schema_name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
                )
                core_manifest_ref = service._publish_generation_run(
                    job=job,
                    payload={},
                    execution_scope=scope,
                    core_run_id=core_run_id,
                    run_context=core_context,
                    compiled_run_ref=compiled_ref,
                )
                progress: dict[str, Any] = {
                    "state": "completed",
                    "phase": "natural_language_run",
                    "status": "manual_candidate_only_n5_recorded",
                    "execution_band": "candidate",
                    "candidate_computation_status": "completed",
                    "execution_intent_band": "simulate_only",
                    "run_id": job.run_id,
                    "compiled_recursive_generation_cycle_ref": str(
                        compiled_ref.artifact_id
                    ),
                    "compiled_recursive_generation_cycle_artifact_ref": (
                        compiled_ref.model_dump(mode="json")
                    ),
                    "n5_status": cycle.simulation.status,
                    "n8_status": cycle.value_port.status,
                    "root_n9_status": "not_promoted",
                    "publication_status": "not_run",
                    **service._core_run_progress_fields(
                        job=job,
                        core_run_id=core_run_id,
                        manifest_ref=core_manifest_ref,
                    ),
                }
                service._control_store.complete_job(
                    job_id=job.job_id,
                    run_id=job.run_id,
                    capability_manifest_ref=job.capability_manifest_ref,
                    progress=progress,
                )
                compiled_refs[job.job_id] = compiled_ref
                produced_inputs[job.job_id] = input_record
                produced_results[job.job_id] = result
                produced_world_model_ids[job.job_id] = (
                    handoff.context.world_model_record.world_model_record_id
                )
                produced_result_refs[job.job_id] = result_ref

        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=produce_manual_candidate_run_for_owned_job,
                expected_job_id=accepted["job_id"],
            )
            == accepted["job_id"]
        )
        completed = service._control_store.get_job(accepted["job_id"])
        assert completed is not None and completed.state == "completed"
        assert completed.run_id is not None
        compiled_ref = compiled_refs[completed.job_id]
        assert str(compiled_ref.artifact_id) == completed.progress[
            "compiled_recursive_generation_cycle_ref"
        ]
        input_record = produced_inputs[completed.job_id]
        n5_result = produced_results[completed.job_id]
        world_model_record_id = produced_world_model_ids[completed.job_id]
        n5_result_ref = produced_result_refs[completed.job_id]

    assert len(n5_calls) == 1
    assert len(n8_calls) == 1
    assert n5_calls[0] == input_record.original_candidate_id

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
    with owner_scoped_test_client(fresh_app) as fresh_client:
        response = fresh_client.get(run_path)
        assert response.status_code == 200, response.text
        run = response.json()["run"]
        rows = run["conditional_simulation_values"]
        assert len(rows) == 1
        row = rows[0]
        assert row["job_id"] == completed.job_id
        assert row["run_id"] == completed.run_id
        assert row["candidate_id"] == input_record.original_candidate_id
        assert row["profile_config_ref"] == input_record.profile_config_ref
        assert row["profile_config_ref"] == candidate_simulation_profile_ref(profile)
        assert ArtifactRef.model_validate(row["n5_result_ref"]).artifact_id == (
            n5_result_ref.artifact_id
        )
        assert row["world_model_record_content_hash"] == (
            input_record.materialization.world_model_record_hash
        )
        assert row["world_model_record_id"] == str(world_model_record_id)
        observation = row["observation"]
        assert observation["status"] == "value_conditional"
        assert observation["value_ref"] == str(n5_result_ref.artifact_id)
        assert "candidate_scenario_n5_only" in observation["authority_blockers"]
        assert observation["evaluation_mode"] == "simulate_only"
        assert observation["predicate_basis"] == "recomputed"
        assert observation["authority_purpose"] == "conditional_simulation_only"

        evidence = observation["conditional_interaction_evidence"]
        horizon = input_record.profile.n5.horizon
        requested_steps = tuple(horizon.steps())
        observed_steps = tuple(
            point.step
            for trajectory in n5_result.trajectories
            if trajectory.run_level == "joint"
            for point in trajectory.points
        )
        assert evidence["schema_version"] == (
            "policyos.runtime.conditional_simulation_interaction_evidence.v1"
        )
        assert evidence["horizon_start"] == horizon.start
        assert evidence["horizon_end"] == horizon.end
        assert evidence["horizon_step"] == horizon.step
        assert evidence["requested_steps"] == list(requested_steps)
        assert evidence["observed_steps"] == list(observed_steps)
        assert evidence["trajectory_scope_count"] == len(n5_result.trajectories)
        assert evidence["checked_interaction_orders"] == [1]
        assert evidence["max_checked_interaction_order"] == 1
        assert evidence["higher_order_residuals"] == {}
        assert evidence["residual_scope"] == "no_higher_order"
        assert evidence["predicate_provenance"] == "recomputed"
        assert evidence["authority_purpose"] == "conditional_simulation_only"
        assert evidence["unit_binding_status"] == "not_established"
        assert evidence["time_binding_status"] == "not_established"
        assert evidence["sampling_uncertainty_status"] == "not_established"
        assert len(n8_calls) == 2
        assert len(n5_calls) == 1
        readback_evidence = n8_calls[1].conditional_interaction_evidence
        assert readback_evidence is not None
        assert readback_evidence.model_dump(mode="json") == evidence

        foreign_claims = build_fixture_identity_claims().model_copy(
            update={
                "tenant_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "cell_id": "cell-b",
            }
        )
        from polisyos.runtime.http import jwt_auth_middleware

        monkeypatch.setattr(
            jwt_auth_middleware,
            "build_fixture_identity_claims",
            lambda: foreign_claims,
        )
        foreign_response = fresh_client.get(
            run_path,
            headers={"X-Tenant-ID": foreign_claims.tenant_id},
        )
        assert foreign_response.status_code == 403, foreign_response.text
        assert foreign_response.json()["code"] == "tenant_not_found"
        assert len(n8_calls) == 2
