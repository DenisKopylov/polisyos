"""Qualify a stock N6 limited research stop and its retained consumer."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

import pytest

from tests.integration.runtime_quality.test_generic_n4_child_profile_set_served import (
    controlled_candidate_gateway as controlled_candidate_gateway,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from httpx import Response

    from polisyos.runtime.quality.design_problem import DesignProblem
    from tests._helpers.controlled_candidate_profile import ControlledCandidateGateway

_OUTCOME = "employment_retention"
_ESTIMAND = "conditional_model_outcome_difference.v1"
_FIXTURE_INPUT = (
    "For Ukraine in 2026, compare the simulated employment_retention of an industrial tax "
    "relief, procurement or budget allocation action with no actuation in the same selected model. "
    "Use conditional_model_outcome_difference.v1 and condition on baseline employment_retention. "
    "Maximize employment_retention for Ukrainian industrial workers. Use model-only research."
)
_TRAP = "cyc05_limited_outcome_preflight_only"
_MODEL_AXES = {
    "cells.distress_score": (1.5, -0.5),
    "global.tax_rate": (0.5, -0.5),
    "government.balance": (0.0, 0.5),
}


def _research_problem(template: DesignProblem) -> DesignProblem:
    """Declare a model contrast as a new controlled question over retained provider stages."""
    from polisyos.runtime.quality.design_problem import DesignProblem

    payload = template.model_dump(mode="python")
    payload.update(
        design_problem_id="controlled_n4_parent_limited_research",
        problem_statement=_FIXTURE_INPUT,
        constraints=[],
        evidence_acquisition_needs={"needs": []},
    )
    payload["nl_provenance"].update(
        raw_request=_FIXTURE_INPUT,
        source_surface="runtime.control.nl_request",
    )
    payload["runtime_hints"].pop("n4_controlled_parent_scope", None)
    payload["objectives"][0].update(
        description="Maximize model employment retention.",
        metric_id=_OUTCOME,
        direction="maximize",
    )
    payload["outcome_of_interest"].update(
        target_variable=_OUTCOME,
        metric_id=_OUTCOME,
        estimand=_ESTIMAND,
        direction="maximize",
        conditioning_variables=[_OUTCOME],
    )
    return DesignProblem.model_validate(payload)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_served_limited_research_stop_and_fresh_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: ControlledCandidateGateway,  # noqa: F811
) -> None:
    """Reopen one completed research result and reject its altered history."""
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import (
        ArtifactRef,
        load_core_json_artifact,
        read_core_manifest_profile,
    )
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http import dependencies
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.routes import runs as run_routes
    from polisyos.runtime.http.security import build_fixture_identity_claims
    from polisyos.runtime.http.services.control import generation_cycle as service_owner
    from polisyos.runtime.quality.generation_cycle import (
        N4GenerationPort,
        PolicyGroundingPort,
        _grounded_candidate_for_evaluation,
        load_joint_simulation_result,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleN5RequestProfileV3,
        GenericCycleSimulationAdmissionOwner,
        GenericCycleSimulationN5InputV1,
        GenericCycleSimulationProfileV1,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationControllerError,
        JointSimulationHorizonController,
        JointSimulationRequest,
        JointSimulationResult,
        NCMConditionalComparatorProfile,
        _assignment_numeric_limitations,
        _ncm_comparator_input,
        _ncm_intervention,
    )
    from polisyos.runtime.quality.limited_research_outcome import _matches_selected_n5_atom
    from polisyos.runtime.quality.recursive_generation_cycle import RecursiveGenerationCycleRun
    from polisyos.scientist.orchestration.engine.budget_ledger import BudgetInvocationQuotaPolicy
    from polisyos.scientist.orchestration.engine.producer_budget import ProducerBudgetObserver
    from tests._helpers import generic_n4_served_replay as fixture
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests.unit.runtime.http.test_nl_pipeline_materialization import (
        _DeterministicSpanSupportClient,
    )

    preflight_only = os.environ.get("POLISYOS_TEST_CYC05_STOP_BEFORE_PHYSICAL") == "1"
    model_seeds: list[int] = []
    original_kernel = NCMEngineMethod.pure_step

    def observe_kernel(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        assert not preflight_only, "CYC-05 prepare crossed the NCM execution boundary"
        assert len(model_seeds) < 4, "CYC-05 spent more than four physical model units"
        model_seeds.append(params["__seed__"])
        return original_kernel(state, params)

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(observe_kernel))
    claims = build_fixture_identity_claims()
    tenant_id, cell_id = claims.tenant_id, claims.cell_id
    assert tenant_id and cell_id
    source = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "source",
        include_owner_slot_manifest=True,
        owner_knob_dictionary=fixture._declared_generic_component_knobs("controlled_overlay"),
    )
    original_fixture_problem = fixture._current_compiler_problem
    with monkeypatch.context() as input_scope:
        input_scope.setattr(
            fixture,
            "_current_compiler_problem",
            lambda recording: _research_problem(original_fixture_problem(recording)),
        )
        prepared = await fixture.prepare_generic_n4_served_replay(
            tmp_path=tmp_path,
            controlled_candidate_gateway=controlled_candidate_gateway,
            monkeypatch=monkeypatch,
            tenant_id=tenant_id,
            cell_id=cell_id,
            child_count=3,
            recording_mode="controlled_overlay",
            source_root=source.root,
            synthetic_settled_provider=True,
        )
    problem = prepared.recorded_problem
    generation = prepared.organ_run.result
    assert generation.status == "generated"
    ground = PolicyGroundingPort()
    first = _grounded_candidate_for_evaluation(
        candidates=generation.candidates,
        grounding_by_candidate={
            item.candidate_id: ground(
                candidate=item, problem=problem, cycle_index=0, generation_result=generation
            )
            for item in generation.candidates
        },
        rankings={
            item.candidate_id: (item.score, item.voi_estimate)
            for item in generation.surrogate_rankings
        },
        fallback=generation.candidates[0],
    )
    (target,) = first.atom.target_world_slots
    (child,) = (
        item for item in prepared.children if first.atom.content_hash in item.source_atom_refs
    )
    target_baseline, coefficient = _MODEL_AXES[target]
    template = fixture._generic_profile_for_selection(
        tmp_path=tmp_path,
        source_root=source.root,
        base_profile=prepared.base_profile,
        base_declaration=prepared.base_declaration,
        profile_id="cyc05-root-limited-research",
        profile_selection_ref=prepared.root_profile.profile_selection_ref,
        profile_selection_kind="problem",
        target_world_slot=target,
        operator_kind=first.atom.operator_kind.trinity_kind,
        store=prepared.runtime_api_context.store,
        substrate_registry_ref=prepared.root_profile.substrate_registry_ref,
        selected_skg_source=prepared.selected_skg_source,
        tenant_id=tenant_id,
        cell_id=cell_id,
        candidate_scm_overrides={
            "target_baseline": target_baseline,
            "outcome_per_target_unit": coefficient,
            "outcome_noise_stddev": 0.0,
        },
        component_rule_spec=fixture._source_component_rule_spec(prepared.organ_run, child),
    )
    n5 = template.n5
    assert type(n5) is GenericCycleN5RequestProfileV3
    slot = template.context_inputs.world_model_record.slot_binding(_OUTCOME)
    assert slot is not None and slot.unit
    profile = fixture._hashed_model(
        GenericCycleSimulationProfileV1,
        {
            **{
                name: getattr(template, name)
                for name in type(template).model_fields
                if name != "content_hash"
            },
            "n5": n5.model_copy(
                update={
                    "evidence_state": {_OUTCOME: n5.baseline_state[_OUTCOME]},
                    "comparator_profile": NCMConditionalComparatorProfile(
                        outcome_units={_OUTCOME: slot.unit}
                    ),
                    "invocation_quota_policy": BudgetInvocationQuotaPolicy(
                        allocation_id="cyc05-root-limited-research",
                        total_units=5,
                        protected_units=1,
                    ),
                    "invocation_purpose": "standard",
                }
            ),
        },
        hash_fn=gy_content_hash,
    )
    app_kwargs = {
        **prepared.app_kwargs,
        "generic_cycle_simulation_profiles": (profile,),
        "generic_cycle_simulation_root_profile_id": profile.profile_id,
    }
    original_compiler = service_owner.build_design_problem_from_nl_request

    async def compile_request(**kwargs: Any) -> DesignProblem:
        kwargs["span_support_client"] = _DeterministicSpanSupportClient()
        return await original_compiler(**kwargs)

    monkeypatch.setattr(service_owner, "build_design_problem_from_nl_request", compile_request)

    original_n4 = N4GenerationPort.__call__
    served_n4: list[tuple[DesignProblem, Any]] = []

    async def observe_n4(
        port: N4GenerationPort, active_problem: DesignProblem, **kwargs: Any
    ) -> Any:
        organ = await original_n4(port, active_problem, **kwargs)
        served_n4.append((active_problem, organ.result))
        return organ

    monkeypatch.setattr(N4GenerationPort, "__call__", observe_n4)
    persist_input = GenericCycleSimulationAdmissionOwner.persist_n5_input
    admitted_inputs: list[tuple[ArtifactRef, GenericCycleSimulationN5InputV1]] = []

    def observe_input(owner: GenericCycleSimulationAdmissionOwner, **kwargs: Any) -> ArtifactRef:
        ref = persist_input(owner, **kwargs)
        recorded = GenericCycleSimulationN5InputV1.model_validate(
            load_core_json_artifact(owner.store, ref)
        )
        admitted_inputs.append((ref, owner.resolve_n5_input(ref, expected=recorded)))
        return ref

    monkeypatch.setattr(GenericCycleSimulationAdmissionOwner, "persist_n5_input", observe_input)
    original_n5 = JointSimulationHorizonController.run
    observed_requests: list[JointSimulationRequest] = []
    expected_effects: list[float] = []
    budget_owners: list[ProducerBudgetObserver] = []

    def observe_n5(
        controller: JointSimulationHorizonController, request: JointSimulationRequest
    ) -> JointSimulationResult:
        assert not observed_requests
        observed_requests.append(request)
        active_problem, result = served_n4[-1]
        (atom,) = request.intervention_atoms
        ((input_ref, input_record),) = admitted_inputs
        (candidate,) = (
            item for item in result.candidates if item.candidate_id == input_record.candidate_id
        )
        assert candidate.atom.content_hash == input_record.candidate_atom_hash
        assert candidate.atom.content_hash != atom.content_hash
        assert _matches_selected_n5_atom(input_record, request)
        other = next(
            item for item in result.candidates if item.candidate_id != candidate.candidate_id
        )
        graft = input_record.model_copy(
            update={
                "candidate_id": other.candidate_id,
                "candidate_atom_hash": other.atom.content_hash,
            }
        )
        assert not _matches_selected_n5_atom(graft, request)
        grounding = ground(
            candidate=candidate,
            problem=active_problem,
            cycle_index=0,
            generation_result=result,
        )
        assert grounding.status == "grounded_shadow"
        assert grounding.grounding_disposition == "shadow_bound"
        assert grounding.report_ref and grounding.cgf_certificate_refs
        assert active_problem.outcome_of_interest.estimand == _ESTIMAND
        assert (
            not active_problem.constraints and not active_problem.evidence_acquisition_needs.needs
        )
        assert request.horizon.steps() == (0,) and request.replications == 2
        assert request.comparator_profile == profile.n5.comparator_profile
        assert request.selected_outcomes == (_OUTCOME,)
        assert request.world_model_record == profile.context_inputs.world_model_record
        selected = controller._select_engine(request)
        assert selected.decision.decision == "selected", selected.decision
        assert selected.decision.engine_kind == "ncm_parallel_worlds"
        assert not _assignment_numeric_limitations((atom,), selected.decision.engine_kind)
        comparator = _ncm_comparator_input(request, selected.plan)
        assert comparator.interventions == [{}]
        ((selected_target, actuation),) = _ncm_intervention((atom,), selected.plan).items()
        (selected_outcome,) = comparator.query_vars
        spec = selected.plan.ncm_spec
        assert spec is not None and spec.scm_spec is not None
        (outcome_mechanism,) = (
            row for row in spec.scm_spec.mechanisms if row.variable == selected_outcome
        )
        assert outcome_mechanism.family_params["coefficients"] == {selected_target: coefficient}
        assert outcome_mechanism.family_params["noise_std"] == 0.0
        assert request.baseline_state[target] == target_baseline
        expected = coefficient * (actuation - target_baseline)
        assert expected > 0.0
        expected_effects.append(expected)
        (tmp_path / "selected-n5-preflight.json").write_text(
            json.dumps(
                {
                    "source_recording_id": prepared.source_recording_id,
                    "source_recording_content_hash": prepared.source_recording_content_hash,
                    "original_candidate_atom_hash": candidate.atom.content_hash,
                    "executed_atom_hash": atom.content_hash,
                    "selected_n5_input_ref": input_ref.model_dump(mode="json"),
                    "grounding": grounding.model_dump(mode="json"),
                    "request": request.model_dump(mode="json"),
                    "selected_engine": selected.decision.model_dump(mode="json"),
                    "comparator_input": comparator.model_dump(mode="json"),
                    "expected_effect": expected,
                    "physical_run_requested": not preflight_only,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        if preflight_only:
            raise JointSimulationControllerError(_TRAP)
        budget_owner = controller._producer_budget_observer
        assert type(budget_owner) is ProducerBudgetObserver
        budget_owners.append(budget_owner)
        return original_n5(controller, request)

    monkeypatch.setattr(JointSimulationHorizonController, "run", observe_n5)
    app = create_runtime_api_app(**app_kwargs)
    with TestClient(app) as client:
        accepted = client.post(
            "/api/v1/control/runs/nl",
            headers={"Idempotency-Key": "cyc05-stock-limited-research"},
            json={**prepared.request_json, "max_iterations": 2},
        )
        assert accepted.status_code == 200, accepted.text
        job_id = accepted.json()["job_id"]
        service = app.state._control_service
        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=job_id,
            )
            == job_id
        )
        job = service._control_store.get_job(job_id)
        assert job is not None
        assert len(observed_requests) == len(expected_effects) == 1, job.progress
        if preflight_only:
            # The real controller did not run, so this diagnostic cannot qualify the stop.
            assert model_seeds == []
            return
        assert job.state == "completed", job.progress
        run_id = job.progress["core_run_id"]
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            payload = service._load_payload_ref(
                job.progress["compiled_recursive_generation_cycle_ref"],
                kind="runtime.compiled_recursive_generation_cycle",
            )
            compiled = service_owner.CompiledRecursiveGenerationCycleRun.model_validate(payload)
            recursive = compiled.recursive_run
            assert isinstance(recursive, RecursiveGenerationCycleRun)
            (leaf,) = recursive.leaf_nodes
            assert leaf.cycle_run is not None
            (cycle,) = leaf.cycle_run.cycles
            assert cycle.terminal_kind == "grounded_partial_admissible"
            limited = cycle.value_port.limited_research_outcome
            assert limited is not None
            store = prepared.runtime_api_context.store
            result = load_joint_simulation_result(
                limited.result_ref, store=store, expected_request=observed_requests[0]
            )
            joint = result.trajectory_for("joint", result.atom_ids)
            assert joint.points[0].effect[_OUTCOME] == pytest.approx(expected_effects[0])
            assert len(result.physical_work_observations) == 4
            seed = observed_requests[0].seed
            assert sorted(model_seeds) == [seed, seed, seed + 1, seed + 1]
            assert all(work.status == "completed" for work in result.physical_work_observations)
            (budget_owner,) = budget_owners
            capacity = budget_owner.observe_standard_invocation_capacity()
            assert capacity.status == "exhausted"
            assert capacity.predicate_basis == "independently_reconciled"
            assert (capacity.standard_limit_units, capacity.standard_remaining_units) == (4, 0)
            assert (capacity.protected_limit_units, capacity.protected_remaining_units) == (1, 1)
            work_operations = {
                work.invocation_quota_operation_id for work in result.physical_work_observations
            }
            assert len(work_operations) == len(capacity.terminal_witnesses) == 4
            assert work_operations == {operation for operation, _ in capacity.terminal_witnesses}
            (tmp_path / "stock-budget-capacity.json").write_text(
                capacity.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
            assert leaf.cycle_run.terminal_status == "completed"
            assert leaf.terminal.kind.value == "grounded_partial_admissible"
            promotion = leaf.cycle_run.promotion_port
            assert promotion.status == "not_promoted"
            assert promotion.reason == "limited_research_outcome_candidate_only"
            assert not promotion.certified_candidate_ids and not promotion.receipts
            assert not leaf.cycle_run.fronts.decision.candidate_ids
            manifest, _ = read_core_manifest_profile(store, limited.result_ref)
            (comparator_edge,) = (
                item for item in manifest.inputs if item.role == "ncm_comparator_result"
            )

    def refuse_physical_n5(*_args: object, **_kwargs: object) -> None:
        pytest.fail("historical replay attempted physical N5")

    monkeypatch.setattr(JointSimulationHorizonController, "run", refuse_physical_n5)
    cold_context = dependencies.build_runtime_api_context(
        cas_root=prepared.cas_root, core_runs_root=prepared.cas_root / "runs"
    )
    cold = create_runtime_api_app(
        **{
            **app_kwargs,
            "container_overrides": RuntimeContainerOverrides(runtime_api_context=cold_context),
        }
    )
    assert cold_context.store is not prepared.runtime_api_context.store
    path = f"/api/v1/runs/{run_id}"
    with TestClient(cold, raise_server_exceptions=False) as reader:
        assert cold.state._control_service._worker is None
        http_statuses: dict[str, int] = {}

        def read_details(name: str) -> Response:
            response = reader.get(path)
            (tmp_path / f"{name}.json").write_bytes(response.content)
            http_statuses[name] = response.status_code
            (tmp_path / "fresh-http-statuses.json").write_text(
                json.dumps(http_statuses, indent=2) + "\n", encoding="utf-8"
            )
            return response

        positive = read_details("fresh-run-details")
        original_projection = run_routes._generic_n6_cycle_history_fields

        def read_corruption(field: str, invalid: str) -> Response:
            with monkeypatch.context() as corruption:

                def corrupt_sibling(run: RecursiveGenerationCycleRun) -> dict[str, Any]:
                    fields = original_projection(run)
                    (history,) = fields["n6_cycle_history"]
                    return {
                        **fields,
                        "n6_cycle_history": ({**history.model_dump(), field: invalid},),
                    }

                corruption.setattr(run_routes, "_generic_n6_cycle_history_fields", corrupt_sibling)
                return read_details(f"fresh-refusal-{invalid}")

        wrong_siblings = (
            read_corruption("refinement_decision", "abstain"),
            read_corruption("search_iteration_status", "abstained"),
            read_corruption("refinement_decision", "block_candidate"),
            read_corruption("search_iteration_status", "blocked_no_retry"),
        )

        blob, _ = FileSystemCAS(prepared.cas_root)._paths(comparator_edge.artifact_id)
        assert blob.is_relative_to(tmp_path) and blob.is_file() and not blob.is_symlink()
        temporarily_removed = blob.with_suffix(".held")
        assert not temporarily_removed.exists()
        blob.rename(temporarily_removed)
        try:
            missing = read_details("fresh-comparator-missing")
        finally:
            temporarily_removed.rename(blob)
        restored = read_details("fresh-run-details-restored")

    assert positive.status_code == 200, positive.text
    projection = positive.json()["run"]["generic_cycle_simulation"]
    assert projection["n6_cycle_history_status"] == "resolved", projection
    assert projection["currentness_status"] == "not_established"
    assert projection["publication_authority"] is False
    (row,) = projection["n6_cycle_history"]
    assert (
        row["terminal_kind"],
        row["refinement_decision"],
        row["search_iteration_status"],
    ) == (
        "grounded_partial_admissible",
        "stop",
        "stopped",
    )
    assert row["voi_next_action"] == "stop"
    assert row["generation_cycle_run_terminal_status"] == "completed"

    for wrong in wrong_siblings:
        assert wrong.status_code == 400, wrong.text
        assert "run_generic_n6_stop_projection_mismatch" in wrong.json()["detail"]

    assert missing.status_code == 200, missing.text
    refused = missing.json()["run"]["generic_cycle_simulation"]
    assert refused["artifact_status"] == "not_established"
    assert refused["limitation_code"] == "limited_research_outcome_replay_not_established"
    assert refused.get("n6_cycle_history", []) == []
    assert restored.status_code == 200, restored.text
    assert restored.json()["run"]["generic_cycle_simulation"] == projection
    assert len(observed_requests) == 1 and len(model_seeds) == 4
