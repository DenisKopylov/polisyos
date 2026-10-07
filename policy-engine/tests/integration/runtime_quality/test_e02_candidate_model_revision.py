"""Served-job integration coverage for same-candidate model revision reentry."""

from __future__ import annotations

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
_RECORDING_ID = "gy_n4_cgf_decisive_capture_1_20260704_092222_049411"
_TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_CELL_ID = "cell-a"


def _ncm_direct_effect(ncm_spec: Any, *, target: str, outcome: str, seed: int) -> float:
    """Compute the same one-step do-effect from an admitted NCM with fixed seed."""

    from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
    from polisyos.foundry.methods.catalog.causal.protocols import NCMQueryData

    query = NCMQueryData(
        ncm_spec=ncm_spec,
        interventions=[{target: 0.0}, {target: 1.0}],
        query_vars=[outcome],
        n_samples=512,
    )
    result = NCMEngineMethod.pure_step(
        {"ncm_query_data": query},
        {"__seed__": seed},
    )["counterfactual_result"]
    worlds = result["world_summaries"]
    return float(worlds[1][outcome]["mean"] - worlds[0][outcome]["mean"])


def test_same_candidate_model_revision_reenters_only_for_changed_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A synthetic candidate-only model change reenters served, owner-bound N5.

    This exercises the configured candidate owner, current-job CAS, and retained
    N4 occurrence using explicit synthetic inputs; it makes no factual L6 or
    empirical claim and does not substitute for the factual served-path check.
    """

    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts.manifest import artifact_ref_identity_key
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.ir.analytics.ncm import (
        NCMSpecRef,
        candidate_ncm_spec_from_declaration,
        load_ncm_spec,
        load_ncm_spec_selected_view,
    )
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.services.control import (
        generation_cycle as generation_cycle_service,
    )
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationContextHandoff,
        CandidateSimulationContextOffer,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        ConfiguredCandidateSimulationContextAdmissionOwner,
        CycleSubstrateContextArtifactOwner,
        VerifiedNLJobScope,
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
    )
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        GenerationCycleError,
        JointSimulationPort,
    )
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateScenarioSourceRecordV3,
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
    model_id = str(recording["model_id"])
    recorded_problem = _current_compiler_problem(recording)
    outcome_variable = recorded_problem.outcome_of_interest.target_variable
    raw_request = recorded_problem.nl_provenance.raw_request
    compiler_gateway = _FakeDesignProblemGateway(
        models=[model_id],
        arguments=recorded_problem.model_dump(mode="json"),
    )
    controlled_recording = n4_contract.RecordedGenerationReplayClient(
        _controlled_procurement_recording(
            recording,
            outcome_variable=outcome_variable,
        )
    )
    cas_root = tmp_path / ".polisyos"
    runtime_api_context = build_runtime_api_context(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
    )
    candidate_only_bundle = _candidate_only_procurement_intervention_bundle()
    profile, model_declaration = _configured_procurement_profile(
        recorded_problem=recorded_problem,
        artifact_store=runtime_api_context.store,
        tenant_id=_TENANT_ID,
        cell_id=_CELL_ID,
        intervention_substrate=candidate_only_bundle,
    )
    compiled_problems: list[Any] = []
    original_compiler = generation_cycle_service.build_design_problem_from_nl_request

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
        lambda **_kwargs: controlled_recording,
    )

    def with_execution_ids(values: dict[str, str]) -> Any:
        provenance = recorded_problem.nl_provenance.model_copy(
            update={"source_context": values}
        )
        return recorded_problem.model_copy(update={"nl_provenance": provenance})

    first_execution_context = with_execution_ids(
        {
            "tenant_id": _TENANT_ID,
            "cell_id": _CELL_ID,
            "job_id": "candidate-job-first",
            "run_id": "candidate-run-first",
        }
    )
    second_execution_context = with_execution_ids(
        {
            "tenant_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "cell_id": "cell-b",
            "job_id": "candidate-job-second",
            "run_id": "candidate-run-second",
        }
    )
    assert cycle_job_profile_selection_ref(first_execution_context) == (
        cycle_job_profile_selection_ref(second_execution_context)
    )
    assert cycle_job_design_problem_ref(first_execution_context) != (
        cycle_job_design_problem_ref(second_execution_context)
    )

    original_run = GenerationCycleController.run
    original_persist = CycleSubstrateContextArtifactOwner.persist_for_current_job
    original_n5 = JointSimulationPort.__call__
    persisted_owner_bindings: list[tuple[Any, Any]] = []
    n5_calls: list[tuple[Any, Any, Any]] = []
    receipts: list[Any] = []
    attempts = 0

    def capture_context_owner(
        owner: CycleSubstrateContextArtifactOwner,
        context: Any,
        *,
        problem: Any,
        verified_nl_job_scope: VerifiedNLJobScope | None = None,
    ) -> Any:
        ref = original_persist(
            owner,
            context,
            problem=problem,
            verified_nl_job_scope=verified_nl_job_scope,
        )
        if verified_nl_job_scope is not None and not persisted_owner_bindings:
            persisted_owner_bindings.append((owner, verified_nl_job_scope))
        return ref

    def record_n5(port: JointSimulationPort, *args: Any, **kwargs: Any) -> Any:
        result = original_n5(port, *args, **kwargs)
        candidate_input = kwargs.get("candidate_simulation_input")
        if candidate_input is not None:
            n5_calls.append(
                (
                    candidate_input,
                    result,
                    kwargs.get("candidate_simulation_input_ref"),
                )
            )
        return result

    async def run_and_reenter(
        controller: GenerationCycleController,
        problem: Any,
        *,
        budget_state: Any,
        **kwargs: Any,
    ) -> Any:
        nonlocal attempts
        original_run_result = await original_run(
            controller,
            problem,
            budget_state=budget_state,
            **kwargs,
        )
        if attempts or controller._candidate_simulation_handoff is None:
            return original_run_result
        attempts += 1
        assert persisted_owner_bindings, "served path did not issue a job-scoped context"
        context_owner, verified_scope = persisted_owner_bindings[0]
        handoff = controller._candidate_simulation_handoff
        assert type(handoff) is CandidateSimulationContextHandoff
        assert type(verified_scope) is VerifiedNLJobScope
        assert verified_scope._was_issued_by_verified_nl_execution_owner
        assert (handoff.job_id, handoff.run_id, handoff.tenant_id, handoff.cell_id) == (
            verified_scope.job_id,
            verified_scope.run_id,
            verified_scope.tenant_id,
            verified_scope.cell_id,
        )
        assert (verified_scope.tenant_id, verified_scope.cell_id) == (_TENANT_ID, _CELL_ID)
        assert original_run_result.cycles
        source_cycle = original_run_result.cycles[-1]
        source_run_payload = original_run_result.model_dump(mode="json")
        source_calls_before_reentry = len(n5_calls)

        # Reissuing the same accepted declaration/context is the negative
        # semantic control. A V5/CAS occurrence is not a new model basis.
        same_basis_owner = ConfiguredCandidateSimulationContextAdmissionOwner(
            profiles=(handoff.profile,),
            model_declarations=(handoff.model_declaration,),
            store=context_owner._store,
        )
        saved_run_cycle = controller._run_cycle

        async def forbid_same_basis_n5(*_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("unchanged_candidate_model_must_stop_before_n5")

        controller._run_cycle = forbid_same_basis_n5  # type: ignore[method-assign]
        try:
            with (
                tenant_scope(
                    None,
                    tenant_id=verified_scope.tenant_id,
                    cell_id=verified_scope.cell_id,
                ),
                pytest.raises(GenerationCycleError) as unchanged,
            ):
                await controller.reenter_after_candidate_model_revision(
                    original_run=original_run_result,
                    source_cycle=source_cycle,
                    problem=problem,
                    admission_owner=same_basis_owner,
                    context_owner=context_owner,
                    verified_nl_job_scope=verified_scope,
                    budget_state=budget_state,
                )
            assert unchanged.value.code == "candidate_model_revision_basis_unchanged"
        finally:
            controller._run_cycle = saved_run_cycle  # type: ignore[method-assign]
        assert len(n5_calls) == source_calls_before_reentry

        # The positive control changes the declared structural coefficient.
        # The fixture builder must carry it into both the typed declaration and
        # the prebound model bytes before the configured owner admits either.
        profile, declaration = _configured_procurement_profile(
            recorded_problem=problem,
            artifact_store=context_owner._store,
            tenant_id=verified_scope.tenant_id,
            cell_id=verified_scope.cell_id,
            outcome_per_target_unit=1.0,
            intervention_substrate=candidate_only_bundle,
        )
        assert declaration.outcome_per_target_unit == 1.0
        prebound_ncm_refs = (
            profile.context_inputs.world_model_record.simulation_model_ref.ncm_refs
        )
        assert len(prebound_ncm_refs) == 1
        with tenant_scope(
            None,
            tenant_id=verified_scope.tenant_id,
            cell_id=verified_scope.cell_id,
        ):
            prebound_ncm = load_ncm_spec(
                context_owner._store,
                NCMSpecRef(artifact_id=prebound_ncm_refs[0]),
            )
        assert prebound_ncm.structural_equations[1].equation_params[
            "coefficients"
        ][declaration.target_world_slot] == 1.0

        revised_owner = ConfiguredCandidateSimulationContextAdmissionOwner(
            profiles=(profile,),
            model_declarations=(declaration,),
            store=context_owner._store,
        )
        with tenant_scope(
            None,
            tenant_id=verified_scope.tenant_id,
            cell_id=verified_scope.cell_id,
        ):
            offer = revised_owner.admit_context(
                problem=problem,
                job_id=verified_scope.job_id,
                run_id=verified_scope.run_id,
                tenant_id=verified_scope.tenant_id,
                cell_id=verified_scope.cell_id,
            )
        assert type(offer) is CandidateSimulationContextOffer
        with tenant_scope(
            None,
            tenant_id=verified_scope.tenant_id,
            cell_id=verified_scope.cell_id,
        ):
            context_ref = context_owner.persist_for_current_job(
                offer.context,
                problem=problem,
                verified_nl_job_scope=verified_scope,
            )
            replayed_context = context_owner.resolve_for_current_job(
                context_ref,
                problem=problem,
                verified_nl_job_scope=verified_scope,
            )
        assert replayed_context.context == offer.context
        revised_handoff = CandidateSimulationContextHandoff(
            context=replayed_context.context,
            context_job_ref=context_ref,
            profile=offer.profile,
            profile_config_ref=offer.profile_config_ref,
            job_id=verified_scope.job_id,
            run_id=verified_scope.run_id,
            tenant_id=verified_scope.tenant_id,
            cell_id=verified_scope.cell_id,
            model_declaration=offer.model_declaration,
            model_declaration_ref=offer.model_declaration_ref,
            ncm_ref=offer.ncm_ref,
        )

        def resolve_revised_currentness() -> bool:
            if not verified_scope._was_issued_by_verified_nl_execution_owner:
                return False
            try:
                selected_context = context_owner.resolve_for_current_job(
                    context_ref,
                    problem=problem,
                    verified_nl_job_scope=verified_scope,
                )
                current_offer = revised_owner.admit_context(
                    problem=problem,
                    job_id=verified_scope.job_id,
                    run_id=verified_scope.run_id,
                    tenant_id=verified_scope.tenant_id,
                    cell_id=verified_scope.cell_id,
                )
            except Exception:
                return False
            return (
                type(current_offer) is CandidateSimulationContextOffer
                and selected_context.problem == problem
                and selected_context.context == current_offer.context == revised_handoff.context
                and current_offer.profile == revised_handoff.profile
                and current_offer.profile_config_ref == revised_handoff.profile_config_ref
                and current_offer.model_declaration == revised_handoff.model_declaration
                and current_offer.model_declaration_ref == revised_handoff.model_declaration_ref
                and current_offer.ncm_ref == revised_handoff.ncm_ref
                and artifact_ref_identity_key(context_ref)
                == artifact_ref_identity_key(revised_handoff.context_job_ref)
            )

        revised_controller = GenerationCycleController(
            model_id=controller._generation_port._model_id,
            repo_root=controller._repo_root,
            cycle_substrate_context=revised_handoff.context,
            promotion_runtime=controller._promotion_runtime,
            candidate_simulation_handoff=revised_handoff,
            candidate_simulation_currentness_resolver=resolve_revised_currentness,
        )
        with tenant_scope(
            None,
            tenant_id=verified_scope.tenant_id,
            cell_id=verified_scope.cell_id,
        ):
            assert resolve_revised_currentness()
        with tenant_scope(
            None,
            tenant_id=verified_scope.tenant_id,
            cell_id=verified_scope.cell_id,
        ):
            receipt = await revised_controller.reenter_after_candidate_model_revision(
                original_run=original_run_result,
                source_cycle=source_cycle,
                problem=problem,
                admission_owner=revised_owner,
                context_owner=context_owner,
                verified_nl_job_scope=verified_scope,
                budget_state=budget_state,
            )
        receipts.append(receipt)
        assert len(n5_calls) == source_calls_before_reentry + 1
        assert original_run_result.model_dump(mode="json") == source_run_payload
        assert receipt.job_id == verified_scope.job_id
        assert receipt.run_id == verified_scope.run_id
        assert receipt.tenant_id == verified_scope.tenant_id
        assert receipt.cell_id == verified_scope.cell_id
        assert receipt.source_run_id == original_run_result.run_id
        assert receipt.design_problem_ref == original_run_result.design_problem_ref
        assert receipt.source_cycle_index == source_cycle.cycle_index
        assert receipt.new_cycle.cycle_index == source_cycle.cycle_index + 1
        assert receipt.new_cycle.design_problem_ref == original_run_result.design_problem_ref
        assert artifact_ref_identity_key(receipt.source_context_job_ref) == (
            artifact_ref_identity_key(handoff.context_job_ref)
        )
        assert artifact_ref_identity_key(receipt.new_context_job_ref) == (
            artifact_ref_identity_key(context_ref)
        )

        old_input = n5_calls[source_calls_before_reentry - 1][0]
        new_input = n5_calls[-1][0]
        assert old_input.original_candidate_id == new_input.original_candidate_id
        assert old_input.original_candidate_hash != new_input.original_candidate_hash
        assert old_input.original_n4_atom_hash != new_input.original_n4_atom_hash
        assert artifact_ref_identity_key(old_input.n4_source_ref) == (
            artifact_ref_identity_key(receipt.source_n4_source_ref)
        )
        assert artifact_ref_identity_key(new_input.n4_source_ref) == (
            artifact_ref_identity_key(receipt.new_n4_source_ref)
        )

        source_repository = GenerationSourceRepository(context_owner._store)
        expected_scope = {
            "expected_run_id": verified_scope.run_id,
            "expected_job_id": verified_scope.job_id,
            "expected_tenant_id": verified_scope.tenant_id,
            "expected_cell_id": verified_scope.cell_id,
        }
        with tenant_scope(
            None,
            tenant_id=verified_scope.tenant_id,
            cell_id=verified_scope.cell_id,
        ):
            old_source = source_repository.load_candidate_scenario_source_for_n5(
                receipt.source_n4_source_ref,
                **expected_scope,
            )
            new_source = source_repository.load_candidate_scenario_source_for_n5(
                receipt.new_n4_source_ref,
                **expected_scope,
            )
        assert type(old_source) is type(new_source) is N4CandidateScenarioSourceRecordV3
        assert old_source.origin_source_ref is None
        assert new_source.origin_source_ref is not None
        assert artifact_ref_identity_key(new_source.origin_source_ref) == (
            artifact_ref_identity_key(receipt.source_n4_source_ref)
        )
        assert old_source.semantic_identity_hash == new_source.semantic_identity_hash
        assert old_source.stable_subject_ref == new_source.stable_subject_ref
        assert old_source.profile_selection_ref == new_source.profile_selection_ref
        assert old_source.candidate_occurrence_hash != new_source.candidate_occurrence_hash
        assert (
            old_source.source_record.world_model_record_hash
            != new_source.source_record.world_model_record_hash
        )
        assert old_source.candidate_occurrence_hash == (
            old_source.source_record.candidate.atom.content_hash
        )
        assert new_source.candidate_occurrence_hash == (
            new_source.source_record.candidate.atom.content_hash
        )
        assert old_source.source_record.candidate.candidate_id == (
            new_source.source_record.candidate.candidate_id
        )
        old_declaration = old_source.source_record.model_declaration
        new_declaration = new_source.source_record.model_declaration
        assert old_declaration is not None and new_declaration is not None
        assert old_declaration.outcome_per_target_unit == 0.5
        assert new_declaration.outcome_per_target_unit == 1.0
        assert artifact_ref_identity_key(old_source.source_ref) != artifact_ref_identity_key(
            new_source.source_ref
        )
        with tenant_scope(
            None,
            tenant_id=verified_scope.tenant_id,
            cell_id=verified_scope.cell_id,
        ):
            old_inner_source = source_repository.load_candidate_scenario_source_v2(
                old_source.source_ref,
                **expected_scope,
            )
            new_inner_source = source_repository.load_candidate_scenario_source_v2(
                new_source.source_ref,
                **expected_scope,
            )
        assert old_inner_source == old_source.source_record
        assert new_inner_source == new_source.source_record
        assert (
            old_source.source_record.proposal.trinity_bundle
            == new_source.source_record.proposal.trinity_bundle
        )
        old_intervention = next(
            item
            for item in old_source.source_record.proposal.trinity_bundle.policy_spec.interventions
            if item.intervention_id
            == old_source.source_record.candidate.intervention_id
        )
        new_intervention = next(
            item
            for item in new_source.source_record.proposal.trinity_bundle.policy_spec.interventions
            if item.intervention_id
            == new_source.source_record.candidate.intervention_id
        )
        assert old_intervention == new_intervention

        with tenant_scope(
            None,
            tenant_id=verified_scope.tenant_id,
            cell_id=verified_scope.cell_id,
        ):
            old_execution = source_repository.resolve_candidate_simulation_v5(
                ref=receipt.source_execution_ref,
                **expected_scope,
            )
            new_execution = source_repository.resolve_candidate_simulation_v5(
                ref=receipt.new_execution_ref,
                **expected_scope,
            )
        assert old_execution.n4_source_ref == receipt.source_n4_source_ref
        assert new_execution.n4_source_ref == receipt.new_n4_source_ref
        assert old_execution.model_declaration_ref == receipt.source_model_declaration_ref
        assert new_execution.model_declaration_ref == receipt.new_model_declaration_ref
        assert old_execution.ncm_ref == receipt.source_ncm_ref
        assert new_execution.ncm_ref == receipt.new_ncm_ref
        assert old_execution.original_candidate_id == new_execution.original_candidate_id
        assert old_execution.original_candidate_hash != new_execution.original_candidate_hash
        assert old_execution.original_n4_atom_hash != new_execution.original_n4_atom_hash

        with tenant_scope(
            None,
            tenant_id=verified_scope.tenant_id,
            cell_id=verified_scope.cell_id,
        ):
            old_ncm = load_ncm_spec_selected_view(
                context_owner._store,
                receipt.source_ncm_ref,
                expected_tenant_id=verified_scope.tenant_id,
                expected_cell_id=verified_scope.cell_id,
                expected_declaration_ref=receipt.source_model_declaration_ref,
            )
            new_ncm = load_ncm_spec_selected_view(
                context_owner._store,
                receipt.new_ncm_ref,
                expected_tenant_id=verified_scope.tenant_id,
                expected_cell_id=verified_scope.cell_id,
                expected_declaration_ref=receipt.new_model_declaration_ref,
            )
        assert old_ncm.model_dump(mode="json") == candidate_ncm_spec_from_declaration(
            old_declaration
        ).model_dump(mode="json")
        assert new_ncm.model_dump(mode="json") == candidate_ncm_spec_from_declaration(
            new_declaration
        ).model_dump(mode="json")
        assert (
            old_source.source_record.profile.n5.seed
            == new_source.source_record.profile.n5.seed
        )
        assert (
            old_source.source_record.profile.n5.horizon
            == new_source.source_record.profile.n5.horizon
        )
        old_effect = _ncm_direct_effect(
            old_ncm,
            target=old_declaration.target_world_slot,
            outcome=old_declaration.outcome_variable,
            seed=old_source.source_record.profile.n5.seed,
        )
        new_effect = _ncm_direct_effect(
            new_ncm,
            target=new_declaration.target_world_slot,
            outcome=new_declaration.outcome_variable,
            seed=new_source.source_record.profile.n5.seed,
        )
        assert old_effect == pytest.approx(0.5, abs=0.02)
        assert new_effect == pytest.approx(1.0, abs=0.02)
        assert new_effect != pytest.approx(old_effect, abs=0.1)
        return original_run_result

    monkeypatch.setattr(
        CycleSubstrateContextArtifactOwner,
        "persist_for_current_job",
        capture_context_owner,
    )
    monkeypatch.setattr(JointSimulationPort, "__call__", record_n5)
    monkeypatch.setattr(GenerationCycleController, "run", run_and_reenter)

    app = create_runtime_api_app(
        cas_root=cas_root,
        container_overrides=RuntimeContainerOverrides(
            runtime_api_context=runtime_api_context
        ),
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
        assert dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=accepted["job_id"],
        ) == accepted["job_id"]
        completed = service._control_store.get_job(accepted["job_id"])
        assert completed is not None and completed.state == "completed"
        assert len(compiled_problems) == 1
        assert compiled_problems[0].outcome_of_interest.target_variable == outcome_variable
        assert completed.progress["status"] == "simulation_only"
        assert len(n5_calls) == 2
    assert attempts == 1
    assert len(receipts) == 1
