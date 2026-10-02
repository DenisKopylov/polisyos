from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, get_args

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


def _controlled_procurement_recording(
    recording: dict[str, object], *, outcome_variable: str, intensity: int = 1
) -> dict[str, object]:
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
        procurement["params"] = {"intensity": intensity}
        procurement["notes"] = [
            "do.target=cells.distress_score sign=decrease "
            f"outcome={outcome_variable} "
            f"effect_path=cells.distress_score,{outcome_variable}"
        ]
        rewritten = json.dumps(trinity, sort_keys=True, separators=(",", ":"))
        response["raw_response"] = rewritten
        response["raw_response_hash"] = gy_content_hash(rewritten)
    return controlled


def _read_private_artifact_in_job_scope(
    *,
    service: Any,
    operation: Callable[[str, str], Any],
    job_id: str,
    run_id: str,
) -> Any:
    """Read private CAS data in the job-created scope admitted by the worker."""
    from polisyos.runtime.http.services.control_plane_store import (
        _control_job_execution_scope_from_event,
    )

    event = service._control_store.get_job_created_event_payload(job_id)
    outbox = service._control_store.get_job_created_outbox_event(job_id)
    assert outbox is not None
    assert event.get("job_id") == job_id
    assert event.get("run_id") == run_id
    assert outbox.job_id == job_id and outbox.run_id == run_id
    scope = _control_job_execution_scope_from_event(event)
    outbox_scope = _control_job_execution_scope_from_event(outbox.payload)
    assert outbox_scope == scope
    assert scope.status == "established"
    assert scope.tenant_id and scope.cell_id
    with tenant_scope(None, tenant_id=scope.tenant_id, cell_id=scope.cell_id):
        return operation(scope.tenant_id, scope.cell_id)


def test_profile_selection_ref_ignores_only_server_execution_ids() -> None:
    """Static selection is stable across job IDs and changes with semantic basis."""

    from polisyos.runtime.quality.cycle_substrate import (
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
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
    assert cycle_job_profile_selection_ref(first) == (
        cycle_job_profile_selection_ref(second)
    )
    assert cycle_job_design_problem_ref(first) != cycle_job_design_problem_ref(second)

    for retained in (
        {"operator_note": "retained"},
        {"runtime_identity": {"tenant_id": "untrusted"}},
        {"candidate_context": {"population": "different"}},
    ):
        altered = with_source_context({**execution_ids, **retained})
        assert cycle_job_profile_selection_ref(altered) != (
            cycle_job_profile_selection_ref(first)
        )
    changed_time = problem.jurisdiction_time.model_copy(update={"as_of": "2026-06-30"})
    assert cycle_job_profile_selection_ref(
        problem.model_copy(update={"jurisdiction_time": changed_time})
    ) != cycle_job_profile_selection_ref(problem)
    changed_request = problem.nl_provenance.model_copy(
        update={"raw_request": problem.nl_provenance.raw_request + " revised"}
    )
    assert cycle_job_profile_selection_ref(
        problem.model_copy(update={"nl_provenance": changed_request})
    ) != cycle_job_profile_selection_ref(problem)


def _configured_procurement_profile(
    *,
    recorded_problem: object,
    cas_root: Path,
):
    """Return a configured candidate profile and its explicit synthetic SCM."""

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
        CandidateSimulationSyntheticModelDeclarationV1,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        cycle_job_profile_selection_ref,
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
    outcome_variable = recorded_problem.outcome_of_interest.target_variable
    ncm = NCMSpec(
        endogenous_vars=["cells.distress_score", outcome_variable],
        exogenous_specs=[
            ExogenousSpec(
                variable="u_distress",
                associated_endogenous="cells.distress_score",
                distribution_params={"mean": 0.0, "std": 0.01},
            ),
            ExogenousSpec(
                variable="u_output",
                associated_endogenous=outcome_variable,
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
                variable=outcome_variable,
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
            [
                lever.target_slot
                for lever in recorded_problem.candidate_lever_space.candidate_levers
            ]
            + ["global.tax_rate", "cells.distress_score", outcome_variable]
        )
    )
    world = _build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=base_problem,
        outcome=outcome_variable,
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
        baseline_state={"cells.distress_score": 0.0, outcome_variable: 0.0},
        seed=11,
        replications=2,
    )
    fields = {
        "schema_version": "policyos.runtime.candidate_simulation_profile.v2",
        "profile_id": "r1.controlled.synthetic.procurement",
        "profile_selection_ref": cycle_job_profile_selection_ref(recorded_problem),
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
    profile = CandidateSimulationScenarioProfile.model_validate(
        {
            **fields,
            "content_hash": gy_content_hash(
                draft_profile.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    declaration_fields = {
        "schema_version": (
            "policyos.runtime.candidate_simulation.synthetic_model_declaration.v1"
        ),
        "profile_config_ref": candidate_simulation_profile_ref(profile),
        "profile_content_hash": profile.content_hash,
        "profile_selection_ref": profile.profile_selection_ref,
        "target_world_slot": rule.target_world_slot,
        "outcome_variable": outcome_variable,
        "target_unit_id": rule.unit_id,
        "outcome_unit_id": rule.unit_id,
        "target_baseline": 0.0,
        "outcome_baseline": 0.0,
        "outcome_per_target_unit": 0.5,
        "outcome_noise_stddev": 0.01,
        "assumption": "declared_candidate_scm_not_empirically_grounded",
    }
    declaration_draft = CandidateSimulationSyntheticModelDeclarationV1.model_construct(
        **declaration_fields,
        content_hash="sha256:" + "0" * 64,
    )
    declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        {
            **declaration_fields,
            "content_hash": gy_content_hash(
                declaration_draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    return profile, declaration


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
            proposal = _read_private_artifact_in_job_scope(
                service=service,
                operation=lambda tenant_id, cell_id: GenerationSourceRepository(
                    service._artifact_store
                ).load_candidate_proposal_for_served_job(
                    locator,
                    job_id=job.job_id,
                    run_id=str(job.run_id),
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    raw_request=raw_request,
                ),
                job_id=job.job_id,
                run_id=str(job.run_id),
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


def test_served_unrefreshable_profile_evidence_keeps_n4_and_blocks_n5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A selected profile with stale context evidence remains N4-only with a typed reason."""

    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        CandidateLeverEvidence,
        cycle_job_design_problem_ref,
        cycle_substrate_context_binding_hash,
    )
    from polisyos.runtime.quality.generation_cycle import JointSimulationPort
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

    profile, declaration = _configured_procurement_profile(
        recorded_problem=recorded_problem,
        cas_root=tmp_path / ".polisyos",
    )
    inputs = profile.context_inputs
    context_binding = cycle_substrate_context_binding_hash(
        design_problem_ref=cycle_job_design_problem_ref(recorded_problem),
        domain=recorded_problem.domain,
        substrate_input_content_hash=inputs.substrate_input_content_hash,
        substrate_registry_content_hash=inputs.substrate_registry.content_hash,
        world_model_record_id=inputs.world_model_record.world_model_record_id,
        world_model_record_content_hash=inputs.world_model_record.content_hash,
        world_model_record_authority_status=inputs.world_model_record.authority_status,
        selected_registry_entry_hashes=inputs.selected_registry_entry_hashes,
    )
    stale_evidence = CandidateLeverEvidence(
        lever_id="procurement_shock_intensity",
        instrument="procurement_shock_intensity",
        target_concept="cells.distress_score",
        entry_content_hash=gy_content_hash({"fixture": "R6 lever row"}),
        substrate_input_content_hash=inputs.substrate_input_content_hash,
        selected_registry_entry_hash=inputs.selected_registry_entry_hashes[0],
        context_binding_hash=context_binding,
        source_refs=("fixture://R6/unrefreshable-profile-evidence",),
    )
    profile_payload = profile.model_dump(mode="json", exclude={"content_hash"})
    profile_payload["context_inputs"]["candidate_levers"] = [
        stale_evidence.model_dump(mode="json")
    ]
    profile_payload["content_hash"] = gy_content_hash(profile_payload)
    profile = CandidateSimulationScenarioProfile.model_validate(profile_payload)

    declaration_payload = declaration.model_dump(mode="json", exclude={"content_hash"})
    declaration_payload.update(
        {
            "profile_config_ref": candidate_simulation_profile_ref(profile),
            "profile_content_hash": profile.content_hash,
        }
    )
    declaration_payload["content_hash"] = gy_content_hash(declaration_payload)
    declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
        declaration_payload
    )

    n5_calls = []

    def reject_n5_call(_port, *args, **kwargs):
        n5_calls.append((args, kwargs))
        raise AssertionError("unrefreshable candidate evidence must stop before N5")

    monkeypatch.setattr(JointSimulationPort, "__call__", reject_n5_call)
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={
            "candidate_simulation_profiles": (profile,),
            "candidate_simulation_model_declarations": (declaration,),
        },
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
            service = app.state._control_service
            assert service._cycle_substrate_context_admission_owner is not None
            job_id = accepted["job_id"]
            assert dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=job_id,
            ) == job_id

            job = service._control_store.get_job(job_id)
            assert job is not None and job.state == "completed"
            assert len(compiled_problems) == 1
            progress = job.progress
            assert progress["execution_intent_band"] == "simulate_only_attempt"
            assert progress["candidate_computation_status"] == "completed"
            assert progress["stage"] == "n4_proposal_only"
            assert progress["candidate_proposal_ref"]
            locator = N4CandidateProposalLocator.model_validate(
                progress["candidate_proposal_ref"]
            )
            proposal = _read_private_artifact_in_job_scope(
                service=service,
                operation=lambda tenant_id, cell_id: GenerationSourceRepository(
                    service._artifact_store
                ).load_candidate_proposal_for_served_job(
                    locator,
                    job_id=job.job_id,
                    run_id=str(job.run_id),
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                    raw_request=raw_request,
                ),
                job_id=job.job_id,
                run_id=str(job.run_id),
            )
            assert type(proposal) is N4CandidateProposalSimulationRecord
            assert proposal.problem == compiled_problems[0]
            assert proposal.proposal.status == "candidate_limited"
            assert proposal.simulation_disposition.reason_code == (
                "cycle_substrate_context_not_established"
            )
            assert proposal.n5_status == proposal.n8_status == "not_run"
            assert proposal.n9_status == proposal.s8_status == "not_run"
            assert progress["target_world_scope_profile_status"] == (
                "profile_refresh_unavailable"
            )
            assert progress["target_world_scope_profile_status"] != (
                "profile_not_requested"
            )
            assert progress["target_world_scope_profile_limitation_code"] == (
                "candidate_simulation_context_evidence_refresh_not_established"
            )
            assert progress["n5_status"] == "not_run"
            assert progress["n8_status"] == "not_run"
            assert progress["n9_status"] == "not_run"
            assert progress["s8_status"] == "not_run"
            assert not progress.get("cycle_substrate_context_job_ref")
            assert n5_calls == []
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
    from polisyos.core.artifacts.manifest import (
        ArtifactRef,
        artifact_ref_identity_key,
        input_ref_from_artifact_ref,
    )
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.services.control import generation_cycle as generation_cycle_service
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        _control_job_execution_scope_from_event,
    )
    from polisyos.runtime.quality import design_generation as design_generation_module
    from polisyos.runtime.quality.candidate_simulation import (
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
        parse_cycle_substrate_context_job_artifact,
    )
    from polisyos.runtime.quality.generation_cycle import (
        FoundryValuePort,
        GenerationCycleController,
        JointSimulationPort,
        _DefaultSimulationBoundFoundryValuePort,
        load_joint_simulation_result,
    )
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateProposalLocator,
        N4CandidateProposalSimulationRecord,
        N4CandidateScenarioSourceLocator,
        N4CandidateScenarioSourceRecordV1,
        N4CandidateScenarioSourceRecordV2,
        _candidate_simulation_write_options,
    )
    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
        intervention_atom_content_hash,
    )
    from polisyos.runtime.quality.promotion_sequence import CanonicalN9PromotionPort
    from polisyos.scientist.methods.search.voi_scheduler import SchedulingDecision
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
    recorded_problem = _current_compiler_problem(recording)
    outcome_variable = recorded_problem.outcome_of_interest.target_variable
    controlled_recording = _controlled_procurement_recording(
        recording,
        outcome_variable=outcome_variable,
    )
    raw_request = recorded_problem.nl_provenance.raw_request
    model_id = str(recording["model_id"])
    compiler_gateway = _FakeDesignProblemGateway(
        models=[model_id],
        arguments=recorded_problem.model_dump(mode="json"),
    )
    cas_root = tmp_path / ".polisyos"
    profile, model_declaration = _configured_procurement_profile(
        recorded_problem=recorded_problem,
        cas_root=cas_root,
    )
    assert profile.profile_selection_ref == cycle_job_profile_selection_ref(
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
    n8_owner_calls: list[str] = []
    n9_owner_calls: list[str] = []
    candidate_leaf_controllers: list[GenerationCycleController] = []

    original_controller_init = GenerationCycleController.__init__

    def observe_leaf_controller(controller, *args, **kwargs):
        original_controller_init(controller, *args, **kwargs)
        if kwargs.get("candidate_simulation_handoff") is not None:
            candidate_leaf_controllers.append(controller)

    def reject_n8_owner_call(port, *args, **kwargs):
        del args, kwargs
        n8_owner_calls.append(type(port).__qualname__)
        raise AssertionError("candidate_scenario_n5_only_must_not_call_n8")

    def reject_n9_owner_call(port, *args, **kwargs):
        del args, kwargs
        n9_owner_calls.append(type(port).__qualname__)
        raise AssertionError("candidate_scenario_n5_only_must_not_call_n9")

    # Observe the concrete owners built by the served recursive controller. The
    # sentinels retain the real classes and fail if the candidate-only branch
    # ever crosses into N8 or N9, even while purpose/progress markers remain.
    monkeypatch.setattr(GenerationCycleController, "__init__", observe_leaf_controller)
    monkeypatch.setattr(FoundryValuePort, "__call__", reject_n8_owner_call)
    monkeypatch.setattr(
        _DefaultSimulationBoundFoundryValuePort, "__call__", reject_n8_owner_call
    )
    monkeypatch.setattr(CanonicalN9PromotionPort, "__call__", reject_n9_owner_call)

    def read_private_artifact_in_job_scope(
        operation: Callable[[], Any], *, job_id: str, run_id: str
    ) -> Any:
        """Read one artifact under the persisted, admitted job-created scope."""
        return _read_private_artifact_in_job_scope(
            service=service,
            operation=lambda _tenant_id, _cell_id: operation(),
            job_id=job_id,
            run_id=run_id,
        )

    original_n5_port = JointSimulationPort.__call__

    def observe_n5_port(port, *args, **kwargs):
        observation = original_n5_port(port, *args, **kwargs)
        input_record = kwargs.get("candidate_simulation_input")
        if input_record is not None:
            n5_calls.append(
                (input_record, observation, kwargs.get("candidate_simulation_input_ref"))
            )
        return observation

    monkeypatch.setattr(JointSimulationPort, "__call__", observe_n5_port)

    app = create_runtime_api_app(
        cas_root=cas_root,
        allow_fixture_identity=True,
        candidate_simulation_profiles=(profile,),
        candidate_simulation_model_declarations=(model_declaration,),
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
        context_job_selected_ref = ArtifactRef.model_validate(
            progress["cycle_substrate_context_job_selected_ref"]
        )
        assert str(context_job_selected_ref.artifact_id) == context_job_ref
        assert context_job_selected_ref.manifest_profile_sha256 is None
        context_job_bytes = read_private_artifact_in_job_scope(
            lambda: service._artifact_store.get_bytes(context_job_selected_ref),
            job_id=completed.job_id,
            run_id=str(completed.run_id),
        )
        context_job = parse_cycle_substrate_context_job_artifact(
            canon.from_canonical_bytes(context_job_bytes)
        )
        assert context_job.problem == compiled_problem
        assert context_job.design_problem_ref == cycle_job_design_problem_ref(
            compiled_problem
        )
        assert context_job.design_problem_ref != profile.profile_selection_ref
        assert context_job.job_id == completed.job_id
        assert context_job.run_id == str(completed.run_id)
        admitted_event = service._control_store.get_job_created_event_payload(
            completed.job_id
        )
        admitted_scope = _control_job_execution_scope_from_event(admitted_event)
        assert context_job.tenant_id == admitted_scope.tenant_id
        assert context_job.cell_id == admitted_scope.cell_id
        assert context_job.problem.nl_provenance.source_context["job_id"] == completed.job_id
        assert context_job.problem.nl_provenance.source_context["run_id"] == str(
            completed.run_id
        )
        assert context_job.profile_admission_status == "not_established"
        assert context_job.s8_status == "blocked"
        assert context_job.context.world_model_record.authority_status == "limited"
        assert context_job.context.world_model_record.simulation_model_ref.calibrated is False

        compiled_payload_bytes = read_private_artifact_in_job_scope(
            lambda: service._artifact_store.get_bytes(
                progress["compiled_recursive_generation_cycle_ref"]
            ),
            job_id=completed.job_id,
            run_id=str(completed.run_id),
        )
        compiled_payload = canon.from_canonical_bytes(compiled_payload_bytes)
        compiled_record = CompiledRecursiveGenerationCycleRun.model_validate(
            compiled_payload
        )
        leaf_nodes = compiled_record.recursive_run.leaf_nodes
        assert len(leaf_nodes) == 1
        leaf_run = leaf_nodes[0].cycle_run
        assert leaf_run is not None
        voi_decision = leaf_run.cycles[-1].voi_decision
        scheduler_actions = set(
            get_args(
                SchedulingDecision.model_fields["recommended_action"].annotation
            )
        )
        assert voi_decision.scheduler_action in scheduler_actions
        assert voi_decision.scheduler_action == "reject"
        assert voi_decision.scheduler_reason == "roi_below_threshold"
        assert voi_decision.next_action == "blocked"
        assert voi_decision.reason == "candidate_scenario_n5_only"

        assert n5_calls, "configured candidate profile did not reach the N5 port"
        input_record, observation, port_input_ref = next(
            (item, result, selected_ref)
            for item, result, selected_ref in n5_calls
            if result.candidate_id == item.original_candidate_id
        )
        assert type(input_record).__name__ == "CandidateSimulationN5InputV5"
        assert input_record.authority_purpose == "candidate_scenario_n5_only"
        assert isinstance(input_record.n4_source_ref, ArtifactRef)
        assert isinstance(input_record.context_job_ref, ArtifactRef)
        assert isinstance(input_record.model_declaration_ref, ArtifactRef)
        assert isinstance(input_record.ncm_ref, ArtifactRef)
        assert isinstance(port_input_ref, ArtifactRef)
        assert input_record.n4_source_ref.manifest_profile_sha256 is None
        assert input_record.context_job_ref.manifest_profile_sha256 is None
        assert input_record.model_declaration_ref.manifest_profile_sha256 is None
        assert input_record.ncm_ref.manifest_profile_sha256 is None
        assert port_input_ref.manifest_profile_sha256 is None
        assert str(input_record.ncm_ref.artifact_id) in (
            context_job.context.world_model_record.simulation_model_ref.ncm_refs
        )
        assert any(
            item.get("declaration_content_hash") == model_declaration.content_hash
            and item.get("status") == "candidate_only_not_empirically_grounded"
            for item in context_job.context.world_model_record.simulation_model_ref.assumptions
        )
        assert artifact_ref_identity_key(input_record.context_job_ref) == (
            artifact_ref_identity_key(context_job_selected_ref)
        )
        assert artifact_ref_identity_key(input_record.materialization.context_job_ref) == (
            artifact_ref_identity_key(context_job_selected_ref)
        )
        assert artifact_ref_identity_key(input_record.materialization.n4_source_ref) == (
            artifact_ref_identity_key(input_record.n4_source_ref)
        )

        # This source kind is distinct from full CGF generation custody: it
        # retains the selected profile/context joins and the typed L2 vintage
        # restriction without forwarding historic confidence into the proposal.
        selected_source = read_private_artifact_in_job_scope(
            lambda: GenerationSourceRepository(
                service._artifact_store
            ).load_candidate_scenario_source_v2(
                input_record.n4_source_ref,
                expected_run_id=str(completed.run_id),
                expected_job_id=completed.job_id,
                expected_tenant_id=admitted_scope.tenant_id,
                expected_cell_id=admitted_scope.cell_id,
            ),
            job_id=completed.job_id,
            run_id=str(completed.run_id),
        )
        assert type(selected_source) is N4CandidateScenarioSourceRecordV2
        assert selected_source.model_declaration == model_declaration
        assert selected_source.model_declaration_ref == input_record.model_declaration_ref
        assert selected_source.ncm_ref == input_record.ncm_ref
        assert selected_source.world_model_record_id == (
            context_job.context.world_model_record.world_model_record_id
        )
        ncm_manifest = read_private_artifact_in_job_scope(
            lambda: service._artifact_store.get_manifest(input_record.ncm_ref),
            job_id=completed.job_id,
            run_id=str(completed.run_id),
        )
        assert len(ncm_manifest.inputs) == 1
        assert (
            ncm_manifest.inputs[0].role,
            str(ncm_manifest.inputs[0].artifact_id),
            ncm_manifest.inputs[0].manifest_profile_sha256,
        ) == (
            "candidate_model_declaration",
            str(input_record.model_declaration_ref.artifact_id),
            input_record.model_declaration_ref.manifest_profile_sha256,
        )
        wrong_closure_job_id = "candidate-ncm-wrong-closure-job"
        wrong_closure_run_id = "candidate-ncm-wrong-closure-run"
        ncm_body = read_private_artifact_in_job_scope(
            lambda: service._artifact_store.get_bytes(input_record.ncm_ref),
            job_id=completed.job_id,
            run_id=str(completed.run_id),
        )
        wrong_closure_options = _candidate_simulation_write_options(
            kind="ir.ncm_spec",
            schema_name="ir.ncm_spec",
            schema_version="1.0",
            job_id=wrong_closure_job_id,
            run_id=wrong_closure_run_id,
            tenant_id=admitted_scope.tenant_id,
            cell_id=admitted_scope.cell_id,
            source_ref=model_declaration.profile_content_hash,
            input_refs=(
                input_ref_from_artifact_ref(
                    input_record.model_declaration_ref,
                    role="candidate_model_declaration",
                ),
            ),
        )
        wrong_closure_ncm_ref = read_private_artifact_in_job_scope(
            lambda: service._artifact_store.put_bytes(
                ncm_body,
                wrong_closure_options,
            ),
            job_id=completed.job_id,
            run_id=str(completed.run_id),
        )
        wrong_closure_manifest = read_private_artifact_in_job_scope(
            lambda: service._artifact_store.get_manifest(wrong_closure_ncm_ref),
            job_id=completed.job_id,
            run_id=str(completed.run_id),
        )
        assert wrong_closure_ncm_ref.artifact_id == input_record.ncm_ref.artifact_id
        assert read_private_artifact_in_job_scope(
            lambda: service._artifact_store.get_bytes(wrong_closure_ncm_ref),
            job_id=completed.job_id,
            run_id=str(completed.run_id),
        ) == ncm_body
        assert wrong_closure_manifest.tenant_context == ncm_manifest.tenant_context
        assert wrong_closure_manifest.inputs == ncm_manifest.inputs
        assert wrong_closure_manifest.same_input_closure.run_id == wrong_closure_run_id
        assert wrong_closure_manifest.same_input_closure.job_id == wrong_closure_job_id
        wrong_closure_source = GenerationSourceRepository(
            service._artifact_store
        ).create_candidate_scenario_source_v2(
            source_record=selected_source.source_record,
            model_declaration=selected_source.model_declaration,
            model_declaration_ref=selected_source.model_declaration_ref,
            ncm_ref=wrong_closure_ncm_ref,
            world_model_record_id=selected_source.world_model_record_id,
        )
        wrong_closure_source_ref = read_private_artifact_in_job_scope(
            lambda: GenerationSourceRepository(
                service._artifact_store
            ).persist_candidate_scenario_source_v2(
                source_record=wrong_closure_source
            ),
            job_id=completed.job_id,
            run_id=str(completed.run_id),
        )
        with pytest.raises(
            ValueError,
            match="n4_candidate_scenario_source_v2_ncm_owner_profile_mismatch",
        ):
            read_private_artifact_in_job_scope(
                lambda: GenerationSourceRepository(
                    service._artifact_store
                ).load_candidate_scenario_source_v2(
                    wrong_closure_source_ref,
                    expected_run_id=str(completed.run_id),
                    expected_job_id=completed.job_id,
                    expected_tenant_id=admitted_scope.tenant_id,
                    expected_cell_id=admitted_scope.cell_id,
                ),
                job_id=completed.job_id,
                run_id=str(completed.run_id),
            )
        n4_source = selected_source.source_record
        assert type(n4_source) is N4CandidateScenarioSourceRecordV1
        assert n4_source.authority_purpose == "candidate_scenario_n5_only"
        assert n4_source.profile.content_hash == profile.content_hash
        assert artifact_ref_identity_key(n4_source.context_job_ref) == (
            artifact_ref_identity_key(context_job_selected_ref)
        )
        assert n4_source.context_hash == context_job.context.content_hash
        assert n4_source.world_model_record_hash == (
            context_job.context.world_model_record.content_hash
        )
        assert n4_source.k_ref_limitation_code == (
            "full_credal_reference_not_established"
        )
        assert n4_source.l2_confidence_vintage is None
        assert n4_source.l2_confidence_forwarded is False
        assert n4_source.credal_reference_payload is None
        assert n4_source.candidate is not None
        full_interventions = n4_source.proposal.trinity_bundle.policy_spec.interventions
        assert {
            intervention.kind for intervention in full_interventions
        } == {
            "procurement_shock_intensity",
            "tax_relief_rate",
            "credit_guarantee",
        }
        selected_interventions = tuple(
            intervention
            for intervention in full_interventions
            if intervention.intervention_id == n4_source.candidate.intervention_id
        )
        assert len(selected_interventions) == 1
        selected_intervention = selected_interventions[0]
        assert selected_intervention.kind == profile.rule.operator_kind
        assert selected_intervention.params == {profile.rule.parameter_id: 1}
        selected_policy_spec = n4_source.proposal.trinity_bundle.policy_spec.model_copy(
            update={"interventions": [selected_intervention]}
        )
        selected_policy_spec_ref = gy_content_hash(
            selected_policy_spec.model_dump(mode="json")
        )
        full_bundle_ref = gy_content_hash(
            n4_source.proposal.trinity_bundle.model_dump(mode="json")
        )
        proposal_ref = gy_content_hash(n4_source.proposal.model_dump(mode="json"))
        assert n4_source.candidate.atom.policy_spec_ref == selected_policy_spec_ref
        assert n4_source.candidate.atom.intervention_id == selected_intervention.intervention_id
        assert n4_source.candidate.atom.direct_effect_bundle.params == (
            selected_intervention.params
        )
        assert n4_source.candidate.atom.target_world_slots == (
            profile.rule.target_world_slot,
        )
        assert full_bundle_ref in n4_source.candidate.atom.provenance_refs
        assert proposal_ref in n4_source.candidate.atom.provenance_refs
        assert input_record.original_n4_atom_hash == n4_source.candidate.atom.content_hash
        assert input_record.materialization.operator_kind == selected_intervention.kind
        assert input_record.materialization.parameter_id == profile.rule.parameter_id
        assert input_record.materialization.value == 1
        assert input_record.materialization.target_world_slot == profile.rule.target_world_slot
        assert input_record.materialization.unit_id == profile.rule.unit_id

        assert type(observation).__name__ == "SimulationPortObservation"
        assert observation.status == "joint_simulated"
        assert observation.uncertainty_kind == "K_sim"
        assert observation.k_world_ref_before == observation.k_world_ref_after
        assert observation.k_world_ref_before == context_job.context.world_model_record.content_hash
        assert observation.simulation_result_ref is not None
        assert isinstance(observation.simulation_result_ref, ArtifactRef)
        assert observation.simulation_result_ref.manifest_profile_sha256 is None
        n5_result = read_private_artifact_in_job_scope(
            lambda: load_joint_simulation_result(
                observation.simulation_result_ref,
                store=service._artifact_store,
                expected_world_model_record_content_hash=context_job.context.world_model_record.content_hash,
                expected_selected_outcomes=(outcome_variable,),
            ),
            job_id=completed.job_id,
            run_id=str(completed.run_id),
        )
        assert n5_result.uncertainty_kind == "K_sim"
        assert n5_result.world_credal_state_before == n5_result.world_credal_state_after
        effects = [
            point.effect[outcome_variable]
            for trajectory in n5_result.trajectories
            for point in trajectory.points
            if outcome_variable in point.effect
        ]
        profile_target_baseline = profile.n5.baseline_state[
            model_declaration.target_world_slot
        ]
        assert profile_target_baseline == model_declaration.target_baseline
        assert (
            profile.n5.baseline_state[model_declaration.outcome_variable]
            == model_declaration.outcome_baseline
        )
        expected_effect = model_declaration.outcome_per_target_unit * (
            input_record.materialization.value - profile_target_baseline
        )
        assert expected_effect == pytest.approx(0.5, abs=1e-12)
        assert len(effects) == profile.n5.replications
        assert effects == pytest.approx(
            [expected_effect] * profile.n5.replications,
            abs=0.02,
        )

        assert leaf_run.terminal_status == "blocked"
        assert leaf_run.value_port.status == "value_pending_n8"
        assert leaf_run.value_port.authority_blockers == (
            "candidate_scenario_n5_only",
        )
        assert leaf_run.promotion_port.status == "not_promoted"
        assert leaf_run.promotion_port.reason.startswith(
            "generation_cycle_blocked_before_n9:"
        )
        assert leaf_run.promotion_port.certified_candidate_ids == ()
        assert leaf_run.fronts.decision.candidate_ids == ()
        assert all(
            not summary.certified_by_n9 for summary in leaf_run.candidate_summaries
        )
        assert all(
            summary.front != "decision" for summary in leaf_run.candidate_summaries
        )
        assert len(candidate_leaf_controllers) == 1
        actual_leaf_controller = candidate_leaf_controllers[0]
        assert type(actual_leaf_controller._value_port) in {
            FoundryValuePort,
            _DefaultSimulationBoundFoundryValuePort,
        }
        assert type(actual_leaf_controller._promotion_port) is CanonicalN9PromotionPort
        assert n8_owner_calls == []
        assert n9_owner_calls == []

        # A content-valid atom that names neither the exact selected projection
        # nor the complete historical source PolicySpec must stop at N5. The
        # N4 source and candidate-only status markers remain persisted.
        original_candidate_builder = (
            design_generation_module.build_candidate_scenario_proposal_candidate
        )
        foreign_policy_spec_ref = "sha256:" + "f" * 64

        def issue_candidate_with_foreign_policy_ref(*args, **kwargs):
            candidate = original_candidate_builder(*args, **kwargs)
            if candidate is None:
                return None
            foreign_atom_draft = candidate.atom.model_copy(
                update={"policy_spec_ref": foreign_policy_spec_ref}
            )
            foreign_atom_hash = intervention_atom_content_hash(foreign_atom_draft)
            foreign_atom_payload = foreign_atom_draft.model_dump(mode="python")
            foreign_atom_payload.update(
                {
                    "atom_id": f"atom_{foreign_atom_hash.removeprefix('sha256:')[:16]}",
                    "content_hash": foreign_atom_hash,
                }
            )
            foreign_atom = InterventionAtomBinding.model_validate(foreign_atom_payload)
            return candidate.model_copy(update={"atom": foreign_atom})

        monkeypatch.setattr(
            design_generation_module,
            "build_candidate_scenario_proposal_candidate",
            issue_candidate_with_foreign_policy_ref,
        )
        n5_calls_before_foreign_ref = len(n5_calls)
        foreign_ref_response = client.post(
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
        assert foreign_ref_response.status_code == 200, foreign_ref_response.text
        foreign_ref_job_id = foreign_ref_response.json()["job_id"]
        assert dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=foreign_ref_job_id,
        ) == foreign_ref_job_id
        foreign_ref_job = service._control_store.get_job(foreign_ref_job_id)
        assert foreign_ref_job is not None and foreign_ref_job.state == "completed"
        assert len(n5_calls) == n5_calls_before_foreign_ref
        assert n8_owner_calls == []
        assert n9_owner_calls == []
        foreign_ref_locator = N4CandidateScenarioSourceLocator.model_validate(
            foreign_ref_job.progress["candidate_proposal_ref"]
        )
        foreign_ref_event = service._control_store.get_job_created_event_payload(
            foreign_ref_job.job_id
        )
        foreign_ref_scope = _control_job_execution_scope_from_event(foreign_ref_event)
        foreign_ref_source = read_private_artifact_in_job_scope(
            lambda: GenerationSourceRepository(
                service._artifact_store
            ).load_candidate_proposal_projection_for_served_job(
                foreign_ref_locator,
                job_id=foreign_ref_job.job_id,
                run_id=str(foreign_ref_job.run_id),
                tenant_id=foreign_ref_scope.tenant_id,
                cell_id=foreign_ref_scope.cell_id,
                raw_request=raw_request,
                expected_design_problem=compiled_problems[1],
            ),
            job_id=foreign_ref_job.job_id,
            run_id=str(foreign_ref_job.run_id),
        )
        assert type(foreign_ref_source) is N4CandidateScenarioSourceRecordV2
        foreign_ref_source = foreign_ref_source.source_record
        assert foreign_ref_source.candidate is not None
        assert foreign_ref_source.candidate.atom.policy_spec_ref == foreign_policy_spec_ref
        assert foreign_ref_source.authority_purpose == "candidate_scenario_n5_only"
        assert foreign_ref_source.n5_status == foreign_ref_source.n8_status == "not_run"
        assert foreign_ref_source.n9_status == "not_admitted"
        assert foreign_ref_source.s8_status == "blocked"
        monkeypatch.setattr(
            design_generation_module,
            "build_candidate_scenario_proposal_candidate",
            original_candidate_builder,
        )

        currentness_guard = (
            actual_leaf_controller._candidate_simulation_currentness_resolver
        )
        assert callable(currentness_guard)
        # The context remains persisted, but cannot authorize N5 after the
        # served worker lease has ended.
        assert currentness_guard() is False

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

        purpose_markers = refs_named(compiled_payload, "candidate_simulation_purpose")
        assert purpose_markers
        assert set(purpose_markers) == {"candidate_scenario_n5_only"}

        def typed_refs_named(payload: object, key: str) -> list[dict[str, object]]:
            found: list[dict[str, object]] = []
            if isinstance(payload, dict):
                for name, value in payload.items():
                    if name == key and isinstance(value, dict):
                        found.append(value)
                    else:
                        found.extend(typed_refs_named(value, key))
            elif isinstance(payload, list):
                for value in payload:
                    found.extend(typed_refs_named(value, key))
            return found

        source_repository = GenerationSourceRepository(service._artifact_store)
        input_refs = typed_refs_named(
            compiled_payload, "candidate_simulation_n5_input_selected_ref"
        )
        input_ref = None
        for reference_payload in input_refs:
            selected_ref = ArtifactRef.model_validate(reference_payload)
            selected_input = read_private_artifact_in_job_scope(
                lambda selected_ref=selected_ref: source_repository.resolve_candidate_simulation_v5(
                    ref=selected_ref,
                    expected_run_id=str(completed.run_id),
                    expected_job_id=completed.job_id,
                    expected_tenant_id=admitted_scope.tenant_id,
                    expected_cell_id=admitted_scope.cell_id,
                ),
                job_id=completed.job_id,
                run_id=str(completed.run_id),
            )
            if (
                type(selected_input).__name__ == "CandidateSimulationN5InputV5"
                and selected_input.original_candidate_id == input_record.original_candidate_id
            ):
                input_ref = selected_ref
                break
        assert input_ref is not None
        assert input_ref.manifest_profile_sha256 is None
        assert artifact_ref_identity_key(port_input_ref) == artifact_ref_identity_key(
            input_ref
        )
        assert str(input_ref.artifact_id) in refs_named(
            compiled_payload, "candidate_simulation_n5_input_ref"
        )

        execution_refs = typed_refs_named(
            compiled_payload, "candidate_simulation_execution_selected_ref"
        )
        assert execution_refs
        execution_ref = None
        execution = None
        for reference_payload in execution_refs:
            selected_ref = ArtifactRef.model_validate(reference_payload)
            selected_execution = read_private_artifact_in_job_scope(
                lambda selected_ref=selected_ref: source_repository.resolve_candidate_simulation_v5(
                    ref=selected_ref,
                    expected_run_id=str(completed.run_id),
                    expected_job_id=completed.job_id,
                    expected_tenant_id=admitted_scope.tenant_id,
                    expected_cell_id=admitted_scope.cell_id,
                ),
                job_id=completed.job_id,
                run_id=str(completed.run_id),
            )
            if selected_execution.original_candidate_id == input_record.original_candidate_id:
                execution_ref = selected_ref
                execution = selected_execution
                break
        assert execution_ref is not None
        assert execution is not None
        assert execution_ref.manifest_profile_sha256 is None
        assert str(execution_ref.artifact_id) in refs_named(
            compiled_payload, "candidate_simulation_execution_ref"
        )
        assert type(execution).__name__ == "CandidateSimulationExecutionV5"
        assert execution.authority_purpose == "candidate_scenario_n5_only"
        assert execution.problem_ref == context_job.design_problem_ref
        assert artifact_ref_identity_key(execution.context_job_ref) == (
            artifact_ref_identity_key(context_job_selected_ref)
        )
        assert artifact_ref_identity_key(execution.n5_input_ref) == (
            artifact_ref_identity_key(input_ref)
        )
        assert artifact_ref_identity_key(execution.n4_source_ref) == (
            artifact_ref_identity_key(input_record.n4_source_ref)
        )
        assert artifact_ref_identity_key(execution.n5_result_ref) == (
            artifact_ref_identity_key(observation.simulation_result_ref)
        )
        input_manifest = read_private_artifact_in_job_scope(
            lambda: service._artifact_store.get_manifest(input_ref),
            job_id=completed.job_id,
            run_id=str(completed.run_id),
        )
        assert {
            (item.role, str(item.artifact_id), item.manifest_profile_sha256)
            for item in input_manifest.inputs
        } == {
            (
                "n4_source",
                str(input_record.n4_source_ref.artifact_id),
                input_record.n4_source_ref.manifest_profile_sha256,
            ),
            (
                "cycle_substrate_context_job",
                str(context_job_selected_ref.artifact_id),
                context_job_selected_ref.manifest_profile_sha256,
            ),
            (
                "candidate_model_declaration",
                str(input_record.model_declaration_ref.artifact_id),
                input_record.model_declaration_ref.manifest_profile_sha256,
            ),
            (
                "candidate_ncm_spec",
                str(input_record.ncm_ref.artifact_id),
                input_record.ncm_ref.manifest_profile_sha256,
            ),
        }
        execution_manifest = read_private_artifact_in_job_scope(
            lambda: service._artifact_store.get_manifest(execution_ref),
            job_id=completed.job_id,
            run_id=str(completed.run_id),
        )
        assert {
            (item.role, str(item.artifact_id), item.manifest_profile_sha256)
            for item in execution_manifest.inputs
        } == {
            ("n5_input", str(input_ref.artifact_id), input_ref.manifest_profile_sha256),
            (
                "n4_source",
                str(input_record.n4_source_ref.artifact_id),
                input_record.n4_source_ref.manifest_profile_sha256,
            ),
            (
                "cycle_substrate_context_job",
                str(context_job_selected_ref.artifact_id),
                context_job_selected_ref.manifest_profile_sha256,
            ),
            (
                "candidate_model_declaration",
                str(input_record.model_declaration_ref.artifact_id),
                input_record.model_declaration_ref.manifest_profile_sha256,
            ),
            (
                "candidate_ncm_spec",
                str(input_record.ncm_ref.artifact_id),
                input_record.ncm_ref.manifest_profile_sha256,
            ),
            (
                "n5_result",
                str(observation.simulation_result_ref.artifact_id),
                observation.simulation_result_ref.manifest_profile_sha256,
            ),
        }
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
        assert len(compiled_problems) == 3
        assert cycle_job_profile_selection_ref(compiled_problems[2]) != (
            profile.profile_selection_ref
        )
        assert second_job.progress["stage"] == "n4_proposal_only"
        assert second_job.progress["candidate_proposal_ref"]
        assert "cycle_substrate_context_job_ref" not in second_job.progress
        assert len(n5_calls) == calls_before_drift

        locator = N4CandidateProposalLocator.model_validate(
            second_job.progress["candidate_proposal_ref"]
        )
        second_event = service._control_store.get_job_created_event_payload(
            second_job.job_id
        )
        second_scope = _control_job_execution_scope_from_event(second_event)
        second_outbox = service._control_store.get_job_created_outbox_event(
            second_job.job_id
        )
        assert second_outbox is not None
        assert _control_job_execution_scope_from_event(second_outbox.payload) == second_scope
        assert second_scope.status == "established"
        assert second_scope.tenant_id and second_scope.cell_id
        proposal = read_private_artifact_in_job_scope(
            lambda: GenerationSourceRepository(
                service._artifact_store
            ).load_candidate_proposal_for_served_job(
                locator,
                job_id=second_job.job_id,
                run_id=str(second_job.run_id),
                tenant_id=second_scope.tenant_id,
                cell_id=second_scope.cell_id,
                raw_request=raw_request,
            ),
            job_id=second_job.job_id,
            run_id=str(second_job.run_id),
        )
        assert type(proposal) is N4CandidateProposalSimulationRecord
        assert proposal.problem == compiled_problems[2]
        assert proposal.proposal.status == "candidate_limited"
        assert proposal.n5_status == proposal.n8_status == "not_run"
        assert proposal.n9_status == proposal.s8_status == "not_run"

        # A selected profile whose exact set_to rule does not match the real N4
        # proposal must expose that original limited proposal and stop before
        # grammar fallback or downstream candidate processing.
        alter_next_compilation[0] = False
        controlled_recording = _controlled_procurement_recording(
            recording,
            intensity=2,
        )
        calls_before_nonmatch = len(n5_calls)
        third_response = client.post(
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
        assert third_response.status_code == 200, third_response.text
        third_job_id = third_response.json()["job_id"]
        assert dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=third_job_id,
        ) == third_job_id
        third_job = service._control_store.get_job(third_job_id)
        assert third_job is not None and third_job.state == "completed"
        assert len(compiled_problems) == 4
        assert cycle_job_profile_selection_ref(compiled_problems[3]) == (
            profile.profile_selection_ref
        )
        assert third_job.progress["stage"] == "n4_proposal_only"
        assert third_job.progress["status"] == "candidate_limited"
        assert (
            third_job.progress["candidate_proposal_limitation_code"]
            == "candidate_scenario_profile_action_not_matched"
        )
        assert third_job.progress["candidate_proposal_ref"]
        assert third_job.progress["n5_status"] == "not_run"
        assert third_job.progress["n8_status"] == "not_run"
        assert third_job.progress["n9_status"] == "not_admitted"
        assert third_job.progress["s8_status"] == "blocked"
        assert len(n5_calls) == calls_before_nonmatch
        assert n8_owner_calls == []
        assert n9_owner_calls == []

        scenario_locator = N4CandidateScenarioSourceLocator.model_validate(
            third_job.progress["candidate_proposal_ref"]
        )
        third_event = service._control_store.get_job_created_event_payload(
            third_job.job_id
        )
        third_scope = _control_job_execution_scope_from_event(third_event)
        third_outbox = service._control_store.get_job_created_outbox_event(
            third_job.job_id
        )
        assert third_outbox is not None
        assert _control_job_execution_scope_from_event(third_outbox.payload) == third_scope
        assert third_scope.status == "established"
        assert third_scope.tenant_id and third_scope.cell_id
        scenario_source = read_private_artifact_in_job_scope(
            lambda: GenerationSourceRepository(
                service._artifact_store
            ).load_candidate_proposal_projection_for_served_job(
                scenario_locator,
                job_id=third_job.job_id,
                run_id=str(third_job.run_id),
                tenant_id=third_scope.tenant_id,
                cell_id=third_scope.cell_id,
                raw_request=raw_request,
                expected_design_problem=compiled_problems[3],
            ),
            job_id=third_job.job_id,
            run_id=str(third_job.run_id),
        )
        assert type(scenario_source) is N4CandidateScenarioSourceRecordV2
        scenario_source = scenario_source.source_record
        assert scenario_source.status == "candidate_limited"
        assert scenario_source.candidate is None
        assert (
            scenario_source.candidate_limitation_code
            == "candidate_scenario_profile_action_not_matched"
        )
        assert scenario_source.proposal.trinity_bundle.policy_spec.interventions
        assert any(
            intervention.kind == "procurement_shock_intensity"
            and intervention.params["intensity"] == 2
            for intervention in scenario_source.proposal.trinity_bundle.policy_spec.interventions
        )
        assert any(
            intervention.kind == "credit_guarantee"
            for intervention in scenario_source.proposal.trinity_bundle.policy_spec.interventions
        )
        assert scenario_source.n5_status == "not_run"
        assert scenario_source.n8_status == "not_run"
        assert scenario_source.n9_status == "not_admitted"
        assert scenario_source.s8_status == "blocked"

        # If the typed source owner cannot persist, keep the original N4 work
        # as a declared limitation; no generated grammar or downstream owner
        # may fill the missing handoff.
        original_persist_candidate_scenario = (
            GenerationSourceRepository.persist_candidate_scenario_source_v2
        )

        def refuse_scenario_source_persistence(_repository, *, source_record):
            del source_record
            raise OSError

        monkeypatch.setattr(
            GenerationSourceRepository,
            "persist_candidate_scenario_source_v2",
            refuse_scenario_source_persistence,
        )
        controlled_recording = _controlled_procurement_recording(recording)
        calls_before_persistence_refusal = len(n5_calls)
        fourth_response = client.post(
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
        assert fourth_response.status_code == 200, fourth_response.text
        fourth_job_id = fourth_response.json()["job_id"]
        assert dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=fourth_job_id,
        ) == fourth_job_id
        fourth_job = service._control_store.get_job(fourth_job_id)
        assert fourth_job is not None and fourth_job.state == "completed"
        assert len(compiled_problems) == 5
        assert fourth_job.progress["stage"] == "n4_proposal_only"
        assert fourth_job.progress["status"] == "not_established"
        assert fourth_job.progress["candidate_proposal_ref"] is None
        assert fourth_job.progress["proposal_persistence_status"] == "not_established"
        assert (
            fourth_job.progress["candidate_proposal_limitation_code"]
            == "candidate_scenario_source_persistence_not_established"
        )
        assert fourth_job.progress["n5_status"] == "not_run"
        assert fourth_job.progress["n8_status"] == "not_run"
        assert fourth_job.progress["n9_status"] == "not_admitted"
        assert fourth_job.progress["s8_status"] == "blocked"
        assert len(n5_calls) == calls_before_persistence_refusal
        assert n8_owner_calls == []
        assert n9_owner_calls == []
        monkeypatch.setattr(
            GenerationSourceRepository,
            "persist_candidate_scenario_source_v2",
            original_persist_candidate_scenario,
        )

        # An explicit zero-dollar request is a real N6 budget limit, not a
        # missing value that may fall through to the HTTP owner's default.
        calls_before_zero_budget = len(n5_calls)
        controllers_before_zero_budget = len(candidate_leaf_controllers)
        compiled_problems_before_zero_budget = len(compiled_problems)
        zero_budget_response = client.post(
            "/api/v1/control/runs/nl",
            json={
                "request": raw_request,
                "llm_model": model_id,
                "run_budget_usd": 0.0,
                "context": {
                    "evaluation_safety_attempt": _valid_intake_for_mode(
                        "simulate_only"
                    ).model_dump(mode="json")
                },
            },
        )
        assert zero_budget_response.status_code == 200, zero_budget_response.text
        zero_budget_job_id = zero_budget_response.json()["job_id"]
        assert dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=zero_budget_job_id,
        ) == zero_budget_job_id

        zero_budget_job = service._control_store.get_job(zero_budget_job_id)
        assert zero_budget_job is not None and zero_budget_job.state == "completed"
        assert zero_budget_job.progress["status"] == "simulation_only"
        assert zero_budget_job.progress["s8_status"] == "not_run"
        assert zero_budget_job.progress["publication_status"] == "not_run"
        assert len(n5_calls) == calls_before_zero_budget
        assert len(compiled_problems) == compiled_problems_before_zero_budget + 1

        # Prove this is the configured profile path with the worker's exact
        # persisted context/job handoff, rather than an ordinary no-profile
        # simulation-only request that happened not to call N5.
        zero_budget_controllers = tuple(
            controller
            for controller in candidate_leaf_controllers[
                controllers_before_zero_budget:
            ]
            if controller._candidate_simulation_handoff.job_id
            == zero_budget_job.job_id
        )
        assert len(zero_budget_controllers) == 1
        zero_budget_controller = zero_budget_controllers[0]
        zero_budget_handoff = zero_budget_controller._candidate_simulation_handoff
        assert zero_budget_handoff is not None
        zero_budget_context_job_selected_ref = ArtifactRef.model_validate(
            zero_budget_job.progress["cycle_substrate_context_job_selected_ref"]
        )
        assert artifact_ref_identity_key(zero_budget_handoff.context_job_ref) == (
            artifact_ref_identity_key(zero_budget_context_job_selected_ref)
        )

        zero_budget_event = service._control_store.get_job_created_event_payload(
            zero_budget_job.job_id
        )
        zero_budget_scope = _control_job_execution_scope_from_event(zero_budget_event)
        assert (
            zero_budget_handoff.profile,
            zero_budget_handoff.profile_config_ref,
            zero_budget_handoff.model_declaration,
            zero_budget_handoff.model_declaration_ref,
            zero_budget_handoff.ncm_ref,
            zero_budget_handoff.job_id,
            zero_budget_handoff.run_id,
            zero_budget_handoff.tenant_id,
            zero_budget_handoff.cell_id,
        ) == (
            profile,
            candidate_simulation_profile_ref(profile),
            model_declaration,
            zero_budget_handoff.model_declaration_ref,
            zero_budget_handoff.ncm_ref,
            zero_budget_job.job_id,
            str(zero_budget_job.run_id),
            zero_budget_scope.tenant_id,
            zero_budget_scope.cell_id,
        )
        zero_budget_source_refs = tuple(
            zero_budget_controller._candidate_scenario_source_refs.values()
        )
        assert len(zero_budget_source_refs) == 1
        zero_budget_source = read_private_artifact_in_job_scope(
            lambda: GenerationSourceRepository(
                service._artifact_store
            ).load_candidate_scenario_source_v2(
                zero_budget_source_refs[0],
                expected_run_id=str(zero_budget_job.run_id),
                expected_job_id=zero_budget_job.job_id,
                expected_tenant_id=zero_budget_scope.tenant_id,
                expected_cell_id=zero_budget_scope.cell_id,
            ),
            job_id=zero_budget_job.job_id,
            run_id=str(zero_budget_job.run_id),
        )
        assert type(zero_budget_source) is N4CandidateScenarioSourceRecordV2
        zero_budget_v1 = zero_budget_source.source_record
        assert zero_budget_source.model_declaration == model_declaration
        assert zero_budget_source.model_declaration_ref == (
            zero_budget_handoff.model_declaration_ref
        )
        assert zero_budget_source.ncm_ref == zero_budget_handoff.ncm_ref
        assert zero_budget_source.status == "candidate_unverified"
        assert zero_budget_v1.candidate is not None
        assert (
            zero_budget_v1.profile,
            zero_budget_v1.profile_config_ref,
            zero_budget_v1.problem,
            zero_budget_v1.profile.profile_selection_ref,
            zero_budget_v1.context_hash,
            zero_budget_v1.job_id,
            zero_budget_v1.run_id,
            zero_budget_v1.tenant_id,
            zero_budget_v1.cell_id,
            artifact_ref_identity_key(zero_budget_v1.context_job_ref),
        ) == (
            profile,
            zero_budget_handoff.profile_config_ref,
            compiled_problems[-1],
            cycle_job_profile_selection_ref(compiled_problems[-1]),
            zero_budget_handoff.context.content_hash,
            zero_budget_handoff.job_id,
            zero_budget_handoff.run_id,
            zero_budget_scope.tenant_id,
            zero_budget_scope.cell_id,
            artifact_ref_identity_key(zero_budget_context_job_selected_ref),
        )

        zero_budget_compiled_bytes = read_private_artifact_in_job_scope(
            lambda: service._artifact_store.get_bytes(
                zero_budget_job.progress["compiled_recursive_generation_cycle_ref"]
            ),
            job_id=zero_budget_job.job_id,
            run_id=str(zero_budget_job.run_id),
        )
        zero_budget_compiled_record = (
            CompiledRecursiveGenerationCycleRun.model_validate(
                canon.from_canonical_bytes(zero_budget_compiled_bytes)
            )
        )
        zero_budget_leaf_nodes = zero_budget_compiled_record.recursive_run.leaf_nodes
        assert len(zero_budget_leaf_nodes) == 1
        zero_budget_leaf = zero_budget_leaf_nodes[0].cycle_run
        assert zero_budget_leaf is not None
        zero_budget_cycle = zero_budget_leaf.cycles[-1]
        assert zero_budget_cycle.simulation.status == "simulation_blocked"
        assert zero_budget_cycle.simulation.diagnostics == {
            "port": "N6",
            "reason": "budget_exhausted_for_next_level",
            "scheduler_action": "defer",
            "scheduler_priority": 0.0,
        }
        assert zero_budget_cycle.value_port.status == "value_blocked"
        assert zero_budget_cycle.value_port.authority_blockers == (
            "budget_exhausted_for_next_level",
        )
        assert zero_budget_cycle.voi_decision.scheduler_action == "defer"
        assert (
            zero_budget_cycle.voi_decision.scheduler_reason
            == "budget_exhausted_for_next_level"
        )
        assert zero_budget_cycle.voi_decision.next_action == "blocked"
        assert (
            zero_budget_cycle.voi_decision.reason
            == "budget_exhausted_for_next_level"
        )
        assert zero_budget_leaf.terminal_status == "blocked"
        assert zero_budget_leaf.value_port.status == "value_blocked"
        assert n8_owner_calls == []
        assert n9_owner_calls == []
