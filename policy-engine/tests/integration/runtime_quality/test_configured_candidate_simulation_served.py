from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from _helpers.runtime_http import build_runtime_api_env, close_runtime_api_env

from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.quality.design_generation import N4CandidateProposalSource
from polisyos.runtime.quality.design_problem import (
    DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION,
)
from polisyos.runtime.quality.generation_source import (
    GenerationSourceRepository,
    N4CandidateProposalLocator,
    N4CandidateProposalSimulationRecord,
)
from polisyos.scientist.orchestration.llm import factory as llm_factory
from tools.quality.validation import (
    check_layer3_gy_design_generation_contract as n4_contract,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
_RECORDING_ID = "gy_n4_cgf_decisive_capture_1_20260704_092222_049411"


def _current_compiler_problem(recording: dict[str, object]):
    """Build honest current-schema compiler arguments without rewriting replay bytes."""

    historical = n4_contract._design_problem(recording)
    source_text = "all proposals remain candidate-only"
    assert source_text in historical.nl_provenance.raw_request
    constraints = [
        constraint.model_copy(
            update={
                "description": "All proposals remain candidate-only.",
                "source_text": source_text,
            }
        )
        if constraint.constraint_id == "no_authority_without_a"
        else constraint
        for constraint in historical.constraints
    ]
    return historical.model_copy(
        update={
            "schema_version": DESIGN_PROBLEM_CURRENT_SCHEMA_VERSION,
            "constraints": constraints,
        }
    )


def _controlled_procurement_recording(recording: dict[str, object]) -> dict[str, object]:
    """Keep the real N4 replay path while making its one direct value integer-only."""

    from polisyos.pdc import gy_content_hash

    controlled = copy.deepcopy(recording)
    responses = controlled.get("responses")
    assert isinstance(responses, list)
    for index in (4, 8):
        response = responses[index]
        assert isinstance(response, dict)
        raw = response.get("raw_response")
        assert isinstance(raw, str)
        trinity = json.loads(raw)
        interventions = trinity["policy_spec"]["interventions"]
        procurement = next(
            item
            for item in interventions
            if item.get("kind") == "procurement_shock_intensity"
        )
        procurement["params"] = {"intensity": 1}
        procurement["notes"] = [
            "do.target=cells.distress_score sign=decrease "
            "outcome=cells.output effect_path=cells.distress_score,cells.output"
        ]
        rewritten = json.dumps(trinity, sort_keys=True, separators=(",", ":"))
        response["raw_response"] = rewritten
        response["raw_response_hash"] = gy_content_hash(rewritten)
    return controlled


def test_profile_selection_ref_ignores_only_server_execution_ids() -> None:
    """Static selection is stable across job IDs and changes with semantic basis."""

    from polisyos.runtime.quality.cycle_substrate import (
        _cycle_job_v1_design_problem_ref,
        _cycle_job_v1_profile_selection_ref,
    )

    recording = next(
        item
        for item in n4_contract._load_recordings(REPO_ROOT)
        if item.get("design_problem_id") == _RECORDING_ID
    )
    problem = n4_contract._design_problem(recording)
    execution_ids = {
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "job_id": "job-a",
        "run_id": "run-a",
    }
    alternate_ids = {
        "tenant_id": "tenant-b",
        "cell_id": "cell-b",
        "job_id": "job-b",
        "run_id": "run-b",
    }

    def with_source_context(values: dict[str, object]):
        provenance = problem.nl_provenance.model_copy(
            update={"source_context": values}
        )
        return problem.model_copy(update={"nl_provenance": provenance})

    first = with_source_context(execution_ids)
    second = with_source_context(alternate_ids)
    assert _cycle_job_v1_profile_selection_ref(first) == (
        _cycle_job_v1_profile_selection_ref(second)
    )
    assert _cycle_job_v1_design_problem_ref(first) != _cycle_job_v1_design_problem_ref(second)

    for retained in (
        {"operator_note": "retained"},
        {"runtime_identity": {"tenant_id": "untrusted"}},
        {"candidate_context": {"population": "different"}},
    ):
        altered = with_source_context({**execution_ids, **retained})
        assert _cycle_job_v1_profile_selection_ref(altered) != (
            _cycle_job_v1_profile_selection_ref(first)
        )
    changed_time = problem.jurisdiction_time.model_copy(update={"as_of": "2026-06-30"})
    assert _cycle_job_v1_profile_selection_ref(
        problem.model_copy(update={"jurisdiction_time": changed_time})
    ) != _cycle_job_v1_profile_selection_ref(problem)
    changed_request = problem.nl_provenance.model_copy(
        update={"raw_request": problem.nl_provenance.raw_request + " revised"}
    )
    assert _cycle_job_v1_profile_selection_ref(
        problem.model_copy(update={"nl_provenance": changed_request})
    ) != _cycle_job_v1_profile_selection_ref(problem)


def _configured_procurement_profile(
    *,
    recorded_problem: object,
    cas_root: Path,
):
    """Compose a synthetic score NCM behind existing registry, L6 and WMR owners."""

    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.ir.analytics.ncm import (
        ExogenousSpec,
        NCMSpec,
        StructuralEquation,
        persist_ncm_spec,
    )
    from polisyos.pdc import gy_content_hash, world_model_record_content_hash
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateScenarioN5Config,
        CandidateScenarioSetToRule,
        CandidateSimulationContextInputs,
        CandidateSimulationScenarioProfile,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        _cycle_job_v1_profile_selection_ref,
    )
    from polisyos.runtime.quality.generation_cycle import (
        _build_boundary_world_model_record,
    )
    from polisyos.runtime.quality.intervention_substrate import (
        load_l6_intervention_substrate,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import HorizonSpec
    from tests.unit.runtime.quality.test_generation_cycle import (
        _cyc01_owner_bound_n5_case,
        _record_with_selected_ncm_ref,
    )

    base_problem, base_context, _candidate = _cyc01_owner_bound_n5_case(
        problem_seed=recorded_problem
    )
    ncm = NCMSpec(
        endogenous_vars=["cells.distress_score", "cells.output"],
        exogenous_specs=[
            ExogenousSpec(
                variable="u_distress",
                associated_endogenous="cells.distress_score",
                distribution_params={"mean": 0.0, "std": 0.01},
            ),
            ExogenousSpec(
                variable="u_output",
                associated_endogenous="cells.output",
                distribution_params={"mean": 0.0, "std": 0.01},
            ),
        ],
        structural_equations=[
            StructuralEquation(
                variable="cells.distress_score",
                parents=[],
                exogenous="u_distress",
                equation_type="linear",
                equation_params={"intercept": 0.0, "coefficients": {}},
            ),
            StructuralEquation(
                variable="cells.output",
                parents=["cells.distress_score"],
                exogenous="u_output",
                equation_type="linear",
                equation_params={
                    "intercept": 0.0,
                    "coefficients": {"cells.distress_score": 0.5},
                },
            ),
        ],
        is_acyclic=True,
        markov_condition_verified=True,
        independence_model="dag_markov",
        fit_method="synthetic_candidate_profile_fixture",
    )
    store = FileSystemCAS(cas_root)
    with tenant_scope(
        None,
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        cell_id="cell-a",
    ):
        ncm_ref = persist_ncm_spec(store, ncm)

    candidate_slots = tuple(
        dict.fromkeys(
            [lever.target_slot for lever in recorded_problem.candidate_lever_space.candidate_levers]
            + ["global.tax_rate", "cells.distress_score", "cells.output"]
        )
    )
    world = _build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=base_problem,
        outcome="cells.output",
        policy_slot_ids=candidate_slots,
        substrate_registry=base_context.substrate_registry,
        selected_registry_entry_hashes=base_context.selected_registry_entry_hashes,
    )
    bindings = tuple(
        item.model_copy(update={"unit": "synthetic_score"})
        for item in world.policy_slot_map
    )
    foundry = world.foundry_binding_ref.model_copy(
        update={
            "state_slot_digest": gy_content_hash(
                {
                    "boundary": "state_slots",
                    "slots": [item.model_dump(mode="json") for item in bindings],
                }
            )
        }
    )
    draft = world.model_copy(update={"policy_slot_map": bindings, "foundry_binding_ref": foundry})
    world = draft.model_copy(
        update={
            "content_hash": world_model_record_content_hash(draft),
            "world_model_record_id": (
                "world_model_record_"
                + world_model_record_content_hash(draft).removeprefix("sha256:")[:16]
            ),
        }
    )
    world = _record_with_selected_ncm_ref(world, str(ncm_ref.artifact_id))
    context_inputs = CandidateSimulationContextInputs(
        substrate_registry=base_context.substrate_registry,
        selected_registry_entry_hashes=base_context.selected_registry_entry_hashes,
        world_model_record=world,
        intervention_substrate=load_l6_intervention_substrate(REPO_ROOT),
        source_pack_content_hash=base_context.source_pack_content_hash,
        substrate_input_content_hash=base_context.substrate_input_content_hash,
    )
    rule = CandidateScenarioSetToRule(
        operator_kind="procurement_shock_intensity",
        parameter_id="intensity",
        target_world_slot="cells.distress_score",
        unit_id="synthetic_score",
        minimum=0,
        maximum=1,
    )
    n5 = CandidateScenarioN5Config(
        budget_ref="budget://r1/controlled-candidate-n5",
        horizon=HorizonSpec(start=0, end=0, step=1),
        baseline_state={"cells.output": 0.0},
        seed=11,
        replications=2,
    )
    fields = {
        "schema_version": "policyos.runtime.candidate_simulation_profile.v2",
        "profile_id": "r1.controlled.synthetic.procurement",
        "profile_selection_ref": _cycle_job_v1_profile_selection_ref(recorded_problem),
        "context_inputs": context_inputs,
        "rule": rule,
        "n5": n5,
        "limitations": (
            "scenario_only",
            "real_profile_not_established",
            "real_time_not_established",
            "grounding_not_established",
            "s8_blocked",
            "n9_not_admitted",
        ),
    }
    draft_profile = CandidateSimulationScenarioProfile.model_construct(
        **fields,
        content_hash="sha256:" + "0" * 64,
    )
    return CandidateSimulationScenarioProfile.model_validate(
        {
            **fields,
            "content_hash": gy_content_hash(
                draft_profile.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )


def test_served_unknown_candidate_profile_keeps_persisted_n4_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unconfigured scenario leaves the real N4 candidate front door available."""

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
    monkeypatch.setenv(
        "POLISYOS_CONTROL_SQLITE_PATH", (tmp_path / "control.sqlite3").as_posix()
    )
    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())

    recording = next(
        item
        for item in n4_contract._load_recordings(REPO_ROOT)
        if item.get("design_problem_id") == _RECORDING_ID
    )
    recorded_problem = _current_compiler_problem(recording)
    raw_request = recorded_problem.nl_provenance.raw_request
    model_id = str(recording["model_id"])
    compiler_gateway = _FakeDesignProblemGateway(
        models=[model_id],
        arguments=recorded_problem.model_dump(mode="json"),
    )
    recorded_n4_client = n4_contract.RecordedGenerationReplayClient(recording)

    from polisyos.runtime.http.services.control import generation_cycle as generation_cycle_service

    original_compiler = generation_cycle_service.build_design_problem_from_nl_request
    compiled_problems = []

    async def run_real_compiler(**kwargs):
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
        lambda **_kwargs: recorded_n4_client,
    )

    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={"candidate_simulation_profiles": ()},
    )
    try:
        client = env["client"]
        if client is None:
            pytest.skip("fastapi is not installed")
        app = env["app"]
        with client:
            response = client.post(
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
            assert response.status_code == 200, response.text
            accepted = response.json()
            assert accepted["status"] == "accepted"
            job_id = accepted["job_id"]
            service = app.state._control_service
            assert service._cycle_substrate_context_admission_owner is None
            assert dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=job_id,
            ) == job_id

            job = service._control_store.get_job(job_id)
            assert job is not None and job.state == "completed"
            assert len(compiled_problems) == 1
            compiled_problem = compiled_problems[0]
            progress = job.progress
            assert progress["execution_intent_band"] == "simulate_only_attempt"
            assert progress["candidate_computation_status"] == "completed"
            assert progress["stage"] == "n4_proposal_only"
            assert progress["candidate_proposal_ref"]
            assert progress["n5_status"] == "not_run"
            assert progress["n8_status"] == "not_run"
            assert progress["n9_status"] == "not_run"
            assert progress["s8_status"] == "not_run"

            locator = N4CandidateProposalLocator.model_validate(
                progress["candidate_proposal_ref"]
            )
            with tenant_scope(
                None,
                tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                cell_id="cell-a",
            ):
                proposal = GenerationSourceRepository(
                    service._artifact_store
                ).load_candidate_proposal_for_served_job(
                    locator,
                    job_id=job.job_id,
                    run_id=str(job.run_id),
                    tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    cell_id="cell-a",
                    raw_request=raw_request,
                )
            assert type(proposal) is N4CandidateProposalSimulationRecord
            assert proposal.problem == compiled_problem
            assert proposal.proposal.status == "candidate_limited"
            assert type(proposal.proposal) is N4CandidateProposalSource
            assert proposal.proposal.drafter_path == "model_generated"
            assert proposal.proposal.formalizer_path == "model_generated"
            assert proposal.proposal.critic_path == "model_generated"
            assert len(proposal.proposal.llm_calls) >= 3
            assert proposal.simulation_disposition.status == "simulation_unavailable"
            assert (
                proposal.simulation_disposition.reason_code
                == "cycle_substrate_context_not_established"
            )
            assert proposal.n5_status == proposal.n8_status == "not_run"
            assert proposal.n9_status == proposal.s8_status == "not_run"
            assert proposal.proposal.trinity_bundle.policy_spec.interventions
    finally:
        close_runtime_api_env(env)


def test_served_configured_profile_runs_real_n4_through_candidate_n5_and_rejects_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The verified worker joins one configured scenario without weakening N4 custody."""

    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core import canon
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.services.control import generation_cycle as generation_cycle_service
    from polisyos.runtime.quality.cycle_substrate import (
        CycleSubstrateContextJobArtifact,
        _cycle_job_v1_design_problem_ref,
        _cycle_job_v1_profile_selection_ref,
    )
    from polisyos.runtime.quality.generation_cycle import (
        JointSimulationPort,
        load_joint_simulation_result,
    )
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateProposalLocator,
        N4CandidateProposalSimulationRecord,
    )
    from polisyos.scientist.orchestration.llm import factory as llm_factory
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests.unit.runtime.http.test_control_job_execution_intent import (
        _valid_intake_for_mode,
    )
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
        _FakeDesignProblemGateway,
    )
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv(
        "POLISYOS_CONTROL_SQLITE_PATH", (tmp_path / "control.sqlite3").as_posix()
    )
    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())
    monkeypatch.setenv("JAX_PLATFORMS", "cpu")
    monkeypatch.setenv("OMP_NUM_THREADS", "1")

    recording = next(
        item
        for item in n4_contract._load_recordings(REPO_ROOT)
        if item.get("design_problem_id") == _RECORDING_ID
    )
    controlled_recording = _controlled_procurement_recording(recording)
    recorded_problem = _current_compiler_problem(recording)
    raw_request = recorded_problem.nl_provenance.raw_request
    model_id = str(recording["model_id"])
    compiler_gateway = _FakeDesignProblemGateway(
        models=[model_id],
        arguments=recorded_problem.model_dump(mode="json"),
    )
    cas_root = tmp_path / ".polisyos"
    profile = _configured_procurement_profile(
        recorded_problem=recorded_problem,
        cas_root=cas_root,
    )
    assert profile.profile_selection_ref == _cycle_job_v1_profile_selection_ref(
        recorded_problem
    )

    original_compiler = generation_cycle_service.build_design_problem_from_nl_request
    compiled_problems = []
    alter_next_compilation = [False]

    async def run_real_compiler(**kwargs):
        kwargs["gateway_client"] = compiler_gateway
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        problem = await original_compiler(**kwargs)
        if alter_next_compilation[0]:
            altered_time = problem.jurisdiction_time.model_copy(
                update={"as_of": "2026-06-30"}
            )
            problem = problem.model_copy(update={"jurisdiction_time": altered_time})
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
        lambda **_kwargs: n4_contract.RecordedGenerationReplayClient(
            controlled_recording
        ),
    )

    n5_calls = []
    original_n5_port = JointSimulationPort.__call__

    def observe_n5_port(port, *args, **kwargs):
        observation = original_n5_port(port, *args, **kwargs)
        input_record = kwargs.get("candidate_simulation_input")
        if input_record is not None:
            n5_calls.append((input_record, observation))
        return observation

    monkeypatch.setattr(JointSimulationPort, "__call__", observe_n5_port)

    app = create_runtime_api_app(
        cas_root=cas_root,
        allow_fixture_identity=True,
        candidate_simulation_profiles=(profile,),
    )
    with TestClient(app) as client:
        response = client.post(
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
        assert response.status_code == 200, response.text
        accepted = response.json()
        assert accepted["status"] == "accepted"
        service = app.state._control_service
        assert service._cycle_substrate_context_admission_owner is not None
        assert dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=accepted["job_id"],
        ) == accepted["job_id"]

        completed = service._control_store.get_job(accepted["job_id"])
        assert completed is not None and completed.state == "completed"
        assert len(compiled_problems) == 1
        compiled_problem = compiled_problems[0]
        progress = completed.progress
        assert progress["status"] == "simulation_only"
        assert progress["execution_intent_band"] == "simulate_only_attempt"
        assert progress["normative_disposition_status"] == "not_run"
        assert progress["s8_status"] == progress["publication_status"] == "not_run"
        context_job_ref = progress["cycle_substrate_context_job_ref"]
        context_job = CycleSubstrateContextJobArtifact.model_validate(
            canon.from_canonical_bytes(service._artifact_store.get_bytes(context_job_ref))
        )
        assert context_job.problem == compiled_problem
        assert context_job.design_problem_ref == _cycle_job_v1_design_problem_ref(
            compiled_problem
        )
        assert context_job.design_problem_ref != profile.profile_selection_ref
        assert context_job.job_id == completed.job_id
        assert context_job.run_id == str(completed.run_id)
        assert context_job.tenant_id == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        assert context_job.cell_id == "cell-a"
        assert context_job.problem.nl_provenance.source_context["job_id"] == completed.job_id
        assert context_job.problem.nl_provenance.source_context["run_id"] == str(
            completed.run_id
        )
        assert context_job.profile_admission_status == "not_established"
        assert context_job.s8_status == "blocked"

        assert n5_calls, "configured candidate profile did not reach the N5 port"
        input_record, observation = next(
            (item, result)
            for item, result in n5_calls
            if result.candidate_id == item.original_candidate_id
        )
        assert type(input_record).__name__ == "CandidateSimulationN5InputV2"
        assert type(observation).__name__ == "SimulationPortObservation"
        assert observation.status == "joint_simulated"
        assert observation.uncertainty_kind == "K_sim"
        assert observation.k_world_ref_before == observation.k_world_ref_after
        assert observation.k_world_ref_before == context_job.context.world_model_record.content_hash
        assert observation.simulation_result_ref is not None
        n5_result = load_joint_simulation_result(
            observation.simulation_result_ref,
            store=service._artifact_store,
            expected_world_model_record_content_hash=context_job.context.world_model_record.content_hash,
            expected_selected_outcomes=("cells.output",),
        )
        assert n5_result.uncertainty_kind == "K_sim"
        assert n5_result.world_credal_state_before == n5_result.world_credal_state_after
        effects = [
            point.effect["cells.output"]
            for trajectory in n5_result.trajectories
            for point in trajectory.points
            if "cells.output" in point.effect
        ]
        assert effects and any(abs(value) > 0.1 for value in effects)

        compiled_payload = canon.from_canonical_bytes(
            service._artifact_store.get_bytes(
                progress["compiled_recursive_generation_cycle_ref"]
            )
        )

        def refs_named(payload: object, key: str) -> list[str]:
            found: list[str] = []
            if isinstance(payload, dict):
                for name, value in payload.items():
                    if name == key and isinstance(value, str):
                        found.append(value)
                    else:
                        found.extend(refs_named(value, key))
            elif isinstance(payload, list):
                for value in payload:
                    found.extend(refs_named(value, key))
            return found

        execution_refs = refs_named(compiled_payload, "candidate_simulation_execution_ref")
        assert execution_refs
        execution = GenerationSourceRepository(
            service._artifact_store
        ).resolve_candidate_simulation_v2(
            ref=execution_refs[0],
            expected_run_id=str(completed.run_id),
            expected_job_id=completed.job_id,
            expected_tenant_id=context_job.tenant_id,
            expected_cell_id=context_job.cell_id,
        )
        assert type(execution).__name__ == "CandidateSimulationExecutionV2"
        assert execution.problem_ref == context_job.design_problem_ref
        assert execution.context_job_ref == context_job_ref
        assert execution.profile_config_ref.endswith(profile.content_hash)
        assert execution.k_world_ref_before == execution.k_world_ref_after

        # Removal probe: keep the configured profile and N4 markers fixed while
        # changing retained time semantics. N5 must not run; ordinary N4 stays usable.
        calls_before_drift = len(n5_calls)
        alter_next_compilation[0] = True
        second_response = client.post(
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
        assert second_response.status_code == 200, second_response.text
        second_job_id = second_response.json()["job_id"]
        assert dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=second_job_id,
        ) == second_job_id
        second_job = service._control_store.get_job(second_job_id)
        assert second_job is not None and second_job.state == "completed"
        assert len(compiled_problems) == 2
        assert _cycle_job_v1_profile_selection_ref(compiled_problems[1]) != (
            profile.profile_selection_ref
        )
        assert second_job.progress["stage"] == "n4_proposal_only"
        assert second_job.progress["candidate_proposal_ref"]
        assert "cycle_substrate_context_job_ref" not in second_job.progress
        assert len(n5_calls) == calls_before_drift

        locator = N4CandidateProposalLocator.model_validate(
            second_job.progress["candidate_proposal_ref"]
        )
        with tenant_scope(
            None,
            tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            cell_id="cell-a",
        ):
            proposal = GenerationSourceRepository(service._artifact_store).load_candidate_proposal_for_served_job(
                locator,
                job_id=second_job.job_id,
                run_id=str(second_job.run_id),
                tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                cell_id="cell-a",
                raw_request=raw_request,
            )
        assert type(proposal) is N4CandidateProposalSimulationRecord
        assert proposal.problem == compiled_problems[1]
        assert proposal.proposal.status == "candidate_limited"
        assert proposal.n5_status == proposal.n8_status == "not_run"
        assert proposal.n9_status == proposal.s8_status == "not_run"
