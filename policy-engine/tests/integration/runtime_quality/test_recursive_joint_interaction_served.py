from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path
from traceback import TracebackException
from typing import Any

import pytest

PHYSICAL_POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def controlled_candidate_gateway(monkeypatch: pytest.MonkeyPatch):
    """Route the served compiler and N4 calls through the local recording gateway."""
    from tests._helpers.controlled_candidate_profile import ControlledCandidateGateway

    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-synthetic-local-gateway-key")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_MAX_RETRIES", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "0")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "0")
    monkeypatch.setenv("POLISYOS_LLM_PROMPT_SANITIZER", "false")
    with ControlledCandidateGateway() as gateway:
        monkeypatch.setenv("POLISYOS_LLM_GATEWAY_BASE_URL", gateway.base_url)
        yield gateway


@pytest.mark.asyncio
async def test_three_atom_parent_n5_is_persisted_and_fresh_get_keeps_uncertainty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """A synthetic source-bound parent retains samples and a low-grade N8 candidate."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import read_core_json_artifact
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.routes import runs as runs_route
    from polisyos.runtime.http.security import build_fixture_identity_claims
    from polisyos.runtime.http.services.control import generation_cycle as compiler_owner
    from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
    from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.recursive_generation_cycle import (
        ParentJointCandidateSelectionV4,
    )
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests.integration.runtime_quality.test_joint_interaction_cubic_consumer import (
        _CANDIDATE_ONLY_SOURCE_QUOTE,
        _SUPPORTED_CANDIDATE_ONLY_CLAIMS,
        _ExactCandidateOnlySpanSupportClient,
    )

    helper_name = "tests._helpers.generic_n4_served_replay"
    helper_path = (
        Path(__file__).resolve().parents[3] / "tests" / "_helpers" / "generic_n4_served_replay.py"
    )
    helper_spec = importlib.util.spec_from_file_location(helper_name, helper_path)
    assert helper_spec is not None and helper_spec.loader is not None
    generic_n4_served_replay = importlib.util.module_from_spec(helper_spec)
    sys.modules[helper_name] = generic_n4_served_replay
    helper_spec.loader.exec_module(generic_n4_served_replay)
    generic_n4_served_replay.REPO_ROOT = PHYSICAL_POLICY_ENGINE_ROOT
    fixture_identity = build_fixture_identity_claims()
    prepared = await generic_n4_served_replay.prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id=fixture_identity.tenant_id,
        cell_id=fixture_identity.cell_id,
        child_count=3,
        materialize_source_parameters=True,
        synthetic_settled_provider=True,
        condition_synthetic_provider_on_child_sources=True,
    )
    assert prepared.app_kwargs["allow_fixture_identity"] is True
    assert prepared.tenant_id == fixture_identity.tenant_id
    assert prepared.cell_id == fixture_identity.cell_id
    assert len(prepared.children) == 3
    candidate_only_constraints = tuple(
        constraint
        for constraint in prepared.recorded_problem.constraints
        if constraint.constraint_id == "no_authority_without_a"
    )
    assert len(candidate_only_constraints) == 1
    (candidate_only_constraint,) = candidate_only_constraints
    assert candidate_only_constraint.source_text == _CANDIDATE_ONLY_SOURCE_QUOTE
    assert candidate_only_constraint.source_text in prepared.request_json["request"]
    assert candidate_only_constraint.description in _SUPPORTED_CANDIDATE_ONLY_CLAIMS

    # The bounded shared fixture supports only the declared claim/quote pair;
    # unsupported paraphrases abstain rather than bypassing grounding.
    span_support_client = _ExactCandidateOnlySpanSupportClient()
    compiler_exception_chains: list[str] = []
    original_compiler = compiler_owner.build_design_problem_from_nl_request

    async def compile_with_source_bound_span_support(**kwargs: Any) -> Any:
        kwargs["span_support_client"] = span_support_client
        try:
            return await original_compiler(**kwargs)
        except BaseException as exc:
            compiler_exception_chains.append(
                "".join(
                    TracebackException.from_exception(exc, capture_locals=False).format(chain=True)
                )
            )
            raise

    monkeypatch.setattr(
        compiler_owner,
        "build_design_problem_from_nl_request",
        compile_with_source_bound_span_support,
    )

    ncm_step_calls = 0
    ncm_query_interventions: list[dict[str, float]] = []

    def controlled_ncm_step(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        nonlocal ncm_step_calls
        ncm_step_calls += 1
        query = state["ncm_query_data"]
        assert len(query.interventions) == 1
        intervention = query.interventions[0]
        ncm_query_interventions.append(dict(intervention))
        seed = int(params["__seed__"])
        value = 0.0
        # This controlled test double supplies a synthetic joint response, not empirical evidence.
        if len(intervention) == 3:
            value = 1.0 if seed == prepared.root_profile.n5.seed else -1.0
        return {
            "counterfactual_result": {"world_summaries": [{query.query_vars[0]: {"mean": value}}]}
        }

    monkeypatch.setattr(NCMEngineMethod, "pure_step", staticmethod(controlled_ncm_step))
    request_payload = {
        **prepared.request_json,
        "joint_interaction_candidate_intent": "n4_unique_parent_source_members.v1",
    }
    app = create_runtime_api_app(**prepared.app_kwargs)
    with TestClient(app) as client:
        request_json = json.dumps(
            request_payload,
            sort_keys=True,
            separators=(",", ":"),
        )
        idempotency_key = "test-r218-" + hashlib.sha256(request_json.encode("utf-8")).hexdigest()
        response = client.post(
            "/api/v1/control/runs/nl",
            headers={
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            content=request_json,
        )
        assert response.status_code == 200, response.text
        accepted = response.json()
        assert accepted["status"] == "accepted"
        service = app.state._control_service
        dispatched = dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=accepted["job_id"],
        )
        assert dispatched == accepted["job_id"]
        job = service._control_store.get_job(accepted["job_id"])
        failure_details = (
            f"job_id={accepted['job_id']} state={getattr(job, 'state', 'missing')} "
            f"error_code={getattr(job, 'error_code', None)!r} "
            f"error_type={getattr(job, 'error_type', None)!r} "
            f"error_message={getattr(job, 'error_message', None)!r} "
            f"error={getattr(job, 'error', None)!r}\n" + "\n".join(compiler_exception_chains)
        )
        assert job is not None and job.state == "completed", failure_details
        assert not compiler_exception_chains
        assert span_support_client.observations
        assert all(
            claim in _SUPPORTED_CANDIDATE_ONLY_CLAIMS
            and span == _CANDIDATE_ONLY_SOURCE_QUOTE
            and decision == "entails"
            for claim, span, decision in span_support_client.observations
        )
        ncm_step_calls_after_producer = ncm_step_calls
        assert ncm_step_calls_after_producer > 0
        ncm_queries_after_producer = len(ncm_query_interventions)
        run_id = str(job.progress["core_run_id"])
        fresh_response = client.get(f"/api/v1/runs/{run_id}")
        assert fresh_response.status_code == 200, fresh_response.text
        projection = fresh_response.json()["run"]["generic_cycle_simulation"]
        served_compiled_ref = ArtifactRef.model_validate(projection["source_ref"])
        assert served_compiled_ref == ArtifactRef.model_validate(
            job.progress["compiled_recursive_generation_cycle_artifact_ref"]
        )
        assert (
            str(served_compiled_ref.artifact_id)
            == job.progress["compiled_recursive_generation_cycle_ref"]
        )
        store = service._artifact_store
        with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
            assert store.verify(served_compiled_ref).ok
            compiled = compiler_owner.CompiledRecursiveGenerationCycleRun.model_validate(
                read_core_json_artifact(store, served_compiled_ref).value
            )
        served_root_node_ref = "design-problem://" + cycle_job_design_problem_ref(
            compiled.design_problem
        ).removeprefix("sha256:")
        root_node = next(
            node for node in compiled.recursive_run.nodes if node.node_ref == served_root_node_ref
        )
        selection = root_node.joint_candidate_selection
        assert type(selection) is ParentJointCandidateSelectionV4
        baseline_parent = projection["joint_parent_observations"][0]
        assert baseline_parent["n8_status"] == "value_conditional"
        assert baseline_parent["n8_candidate_decision_grade"] == "low"

        def n5_row_identity(rows: list[dict[str, Any]]) -> tuple[tuple[Any, ...], ...]:
            return tuple(
                (
                    row["node_ref"],
                    row.get("candidate_id"),
                    (row.get("n5_execution_ref") or {}).get("artifact_id"),
                    (row.get("simulation_result_ref") or {}).get("artifact_id"),
                )
                for row in rows
            )

        n5_rows_before = n5_row_identity(projection["n5_observations"])
        selected_source_ref = selection.n4_source_ref
        assert selected_source_ref.manifest_profile_sha256 is not None
        original_raw_manifest = store.get_raw_manifest_bytes
        original_selection_projection = runs_route._parent_joint_candidate_selection_projection
        withheld_source_reads: list[str] = []

        def is_selected_source_ref(ref: Any) -> bool:
            return (
                getattr(ref, "artifact_id", None) == selected_source_ref.artifact_id
                and getattr(ref, "manifest_profile_sha256", None)
                == selected_source_ref.manifest_profile_sha256
            )

        def withhold_selected_source_for_parent_replay(**kwargs: Any) -> dict[str, Any]:
            def missing_selected_source(ref: Any, *args: Any, **read_kwargs: Any) -> bytes:
                if is_selected_source_ref(ref):
                    withheld_source_reads.append(str(selected_source_ref.artifact_id))
                    raise FileNotFoundError("synthetic selected source owner withheld")
                return original_raw_manifest(ref, *args, **read_kwargs)

            with monkeypatch.context() as source_owner_withheld:
                source_owner_withheld.setattr(
                    store, "get_raw_manifest_bytes", missing_selected_source
                )
                return original_selection_projection(**kwargs)

        with monkeypatch.context() as selected_source_withheld:
            selected_source_withheld.setattr(
                runs_route,
                "_parent_joint_candidate_selection_projection",
                withhold_selected_source_for_parent_replay,
            )
            missing_source_response = client.get(f"/api/v1/runs/{run_id}")
        assert missing_source_response.status_code == 200, missing_source_response.text
        assert withheld_source_reads
        withheld_projection = missing_source_response.json()["run"]["generic_cycle_simulation"]
        assert withheld_projection["joint_parent_status"] == "not_established"
        assert withheld_projection["joint_parent_limitation_code"] == (
            "generic_joint_parent_result_unavailable"
        )
        assert not withheld_projection.get("joint_parent_observations", [])
        assert not any(
            row["node_ref"] == baseline_parent["node_ref"]
            and (
                row.get("n8_status") == "value_conditional"
                or row.get("n8_candidate_value_ref") == baseline_parent["n8_candidate_value_ref"]
            )
            for row in withheld_projection["n5_observations"]
        )
        assert n5_row_identity(withheld_projection["n5_observations"]) == n5_rows_before
        assert ncm_step_calls == ncm_step_calls_after_producer
        assert len(ncm_query_interventions) == ncm_queries_after_producer

        restored_response = client.get(f"/api/v1/runs/{run_id}")
        assert restored_response.status_code == 200, restored_response.text
        restored_projection = restored_response.json()["run"]["generic_cycle_simulation"]
        assert (
            restored_projection["joint_parent_observations"]
            == projection["joint_parent_observations"]
        )
        assert n5_row_identity(restored_projection["n5_observations"]) == n5_rows_before
        assert ncm_step_calls == ncm_step_calls_after_producer
        assert len(ncm_query_interventions) == ncm_queries_after_producer

    counts_before_fresh_get = (ncm_step_calls, len(ncm_query_interventions))
    fresh_context = build_runtime_api_context(
        cas_root=prepared.cas_root,
        core_runs_root=prepared.runtime_api_context.core_runs_root,
    )
    assert fresh_context is not prepared.runtime_api_context
    assert fresh_context.store is not prepared.runtime_api_context.store
    assert fresh_context.run_index is not prepared.runtime_api_context.run_index
    fresh_app = create_runtime_api_app(
        **{
            **prepared.app_kwargs,
            "container_overrides": RuntimeContainerOverrides(runtime_api_context=fresh_context),
            "generic_cycle_simulation_profiles": (),
            "generic_cycle_simulation_root_profile_id": None,
        }
    )
    with TestClient(fresh_app) as fresh_client:
        fresh_response = fresh_client.get(f"/api/v1/runs/{run_id}")
        assert fresh_response.status_code == 200, fresh_response.text
        fresh_projection = fresh_response.json()["run"]["generic_cycle_simulation"]
        assert fresh_projection["joint_parent_status"] == "resolved"
        assert (
            fresh_projection["joint_parent_observations"] == projection["joint_parent_observations"]
        )
        assert n5_row_identity(fresh_projection["n5_observations"]) == n5_rows_before
        assert counts_before_fresh_get == (ncm_step_calls, len(ncm_query_interventions))
        fresh_compiled_ref = ArtifactRef.model_validate(fresh_projection["source_ref"])
        assert fresh_compiled_ref == served_compiled_ref
        with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
            assert fresh_context.store.verify(fresh_compiled_ref).ok
            compiled = compiler_owner.CompiledRecursiveGenerationCycleRun.model_validate(
                read_core_json_artifact(fresh_context.store, fresh_compiled_ref).value
            )
        projection = fresh_projection
        served_root_node_ref = "design-problem://" + cycle_job_design_problem_ref(
            compiled.design_problem
        ).removeprefix("sha256:")
        root_node = next(
            node for node in compiled.recursive_run.nodes if node.node_ref == served_root_node_ref
        )
        selection = root_node.joint_candidate_selection
        assert compiled.recursive_run.root_node_ref == served_root_node_ref
        assert type(selection) is ParentJointCandidateSelectionV4
        assert selection.schema_version == (
            "policyos.runtime.recursive_generation_cycle.parent_joint_candidate_selection.v4"
        )
        assert selection.candidate_intent == "n4_unique_parent_source_members.v1"
        assert selection.member_basis == "hypothetical_all_unique_n4_source_members"
        assert selection.source_candidate_relationship == "alternatives"
        assert selection.composition_status == "not_established"
        assert selection.child_to_parent_refinement_status == "not_established"
        selection_payload = selection.model_dump(mode="json")
        assert not {
            "request_payload_ref",
            "relation_ref",
            "relation_content_hash",
            "intent_digest",
        }.intersection(selection_payload)
        physical_request = root_node.joint_simulation_request
        assert physical_request is not None
        assert physical_request.candidate_intent == "n4_unique_parent_source_members.v1"
        assert physical_request.member_basis == "hypothetical_all_unique_n4_source_members"
        assert physical_request.source_candidate_relationship == "alternatives"
        assert physical_request.composition_status == "not_established"
        assert len(selection.component_materializations) == 3
        assert len(physical_request.intervention_atoms) == 3

        handoff = compiled.generic_cycle_simulation_handoff
        assert handoff is not None
        assert compiled.n4_recursive_source_ref is not None
        assert compiled.n4_recursive_source_run_id == handoff.run_id
        assert compiled.n4_recursive_source_job_id == handoff.job_id == accepted["job_id"]
        assert compiled.n4_recursive_source_tenant_id == handoff.tenant_id == prepared.tenant_id
        assert compiled.n4_recursive_source_cell_id == handoff.cell_id == prepared.cell_id
        assert compiled.n4_recursive_source_context_job_ref == handoff.context_job_ref
        assert compiled.n4_recursive_source_profile_config_ref == handoff.profile.profile_id
        assert compiled.n4_recursive_source_profile_selection_ref == (
            handoff.profile.profile_selection_ref
        )
        with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
            served_source = GenerationSourceRepository(fresh_context.store).load(
                compiled.n4_recursive_source_ref,
                run_id=handoff.run_id,
                expected_run_id=handoff.run_id,
                expected_job_id=handoff.job_id,
                expected_tenant_id=handoff.tenant_id,
                expected_cell_id=handoff.cell_id,
                context_job_ref=handoff.context_job_ref,
                profile_ref=handoff.profile_ref,
                n4_child_profile_family_ref=handoff.n4_child_profile_family_ref,
            )
        assert selection.n4_source_ref == compiled.n4_recursive_source_ref
        actual_source_result_hash = gy_content_hash(
            served_source.generation_result.model_dump(mode="json")
        )
        assert selection.n4_source_result_content_hash == actual_source_result_hash
        world_record = handoff.profile.context_inputs.world_model_record
        assert selection.context_job_ref == handoff.context_job_ref
        assert selection.profile_ref == handoff.profile_ref
        assert selection.profile_selection_ref == handoff.profile.profile_selection_ref
        assert selection.world_model_record_ref == world_record.world_model_record_id
        assert selection.world_model_record_content_hash == world_record.content_hash
        source_candidates_by_id = {
            candidate.candidate_id: candidate
            for candidate in served_source.generation_result.candidates
        }
        assert served_source.trinity_bundle is not None
        source_interventions = served_source.trinity_bundle.policy_spec.interventions
        source_interventions_by_id = {
            intervention.intervention_id: intervention for intervention in source_interventions
        }
        assert len(source_interventions_by_id) == len(source_interventions)
        assert len(source_candidates_by_id) == 3
        assert {member.source_candidate_id for member in selection.members} == set(
            source_candidates_by_id
        )
        slot_units = {slot.slot_id: slot.unit for slot in world_record.policy_slot_map}
        target_slots: set[str] = set()
        source_values_by_target: dict[str, Decimal] = {}
        assignments = []
        for member, materialization, derived_atom in zip(
            selection.members,
            selection.component_materializations,
            physical_request.intervention_atoms,
            strict=True,
        ):
            source_candidate = source_candidates_by_id[member.source_candidate_id]
            source_intervention = source_interventions_by_id[source_candidate.atom.intervention_id]
            assert source_intervention.intervention_id == derived_atom.intervention_id
            # The member binds full candidate JSON; materialization binds provenance content.
            assert member.source_candidate_content_hash == gy_content_hash(
                source_candidate.model_dump(mode="json")
            )
            assert materialization.candidate_id == source_candidate.candidate_id
            assert (
                materialization.original_candidate_hash == source_candidate.provenance.content_hash
            )
            assert materialization.original_atom_hash == source_candidate.atom.content_hash
            assert member.source_atom_content_hash == source_candidate.atom.content_hash
            assert derived_atom == materialization.derived_n5_atom
            assert derived_atom.content_hash != source_candidate.atom.content_hash
            assert derived_atom.problem_frame_ref == selection.parent_design_problem_ref
            assert derived_atom.world_model_record_ref == selection.world_model_record_ref
            assert materialization.profile_hash == handoff.profile.content_hash
            assert materialization.context_hash == handoff.context.content_hash
            assert materialization.context_job_ref == str(handoff.context_job_ref.artifact_id)
            assert materialization.source_handoff_ref == str(selection.n4_source_ref.artifact_id)
            assert materialization.world_model_record_hash == world_record.content_hash
            assert materialization.unit_id == slot_units[materialization.target_world_slot]
            target_slots.add(materialization.target_world_slot)
            atom_assignments = derived_atom.causal_do_expr.assignments
            assert len(atom_assignments) == 1
            (assignment,) = atom_assignments
            assert assignment.variable == materialization.target_world_slot
            assert assignment.value_expr is None
            assert assignment.value is not None
            assignment_value = Decimal(str(assignment.value))
            assert assignment_value.is_finite()
            source_parameter_value = Decimal(
                str(source_intervention.params[materialization.parameter_id])
            )
            assert source_parameter_value.is_finite()
            assert assignment_value == source_parameter_value
            assert Decimal(str(materialization.value)) == source_parameter_value
            assert materialization.target_world_slot not in source_values_by_target
            source_values_by_target[materialization.target_world_slot] = source_parameter_value
            assignments.append(assignment)
        assert len(target_slots) == 3
        assert len(assignments) == 3
        assert set(source_values_by_target) == target_slots
        expected_full_interventions = []
        for plan in physical_request.engine_plan:
            assert plan.ncm_spec is not None
            assert target_slots.issubset(plan.variable_map)
            planned_ncm_targets = {plan.variable_map[target] for target in target_slots}
            assert planned_ncm_targets.issubset(set(plan.ncm_spec.endogenous_vars))
            expected_intervention = {
                plan.variable_map[target]: float(source_values_by_target[target])
                for target in target_slots
            }
            assert len(expected_intervention) == 3
            expected_full_interventions.append(expected_intervention)
        observed_full_interventions = [
            intervention for intervention in ncm_query_interventions if len(intervention) == 3
        ]
        assert observed_full_interventions
        assert all(
            any(intervention == expected for expected in expected_full_interventions)
            for intervention in observed_full_interventions
        )

        parent_rows = projection["joint_parent_observations"]
        assert len(parent_rows) == 1
        parent = parent_rows[0]
        assert parent["node_ref"] == served_root_node_ref
        evidence = parent["n5_interaction_evidence"]
        assert len(parent["atom_ids"]) == 3
        assert len(evidence["interaction_terms"]) == 3
        assert evidence["checked_interaction_orders"] == [1, 2, 3]
        assert parent["n8_candidate_joint_selection_status"] == "resolved"
        assert parent["n8_candidate_joint_selection_content_hash"].startswith("sha256:")
        assert parent["n8_candidate_derived_atom_ids"] == [
            item.derived_n5_atom.atom_id for item in selection.component_materializations
        ]
        assert parent["n8_candidate_derived_atom_content_hashes"] == [
            item.derived_n5_atom.content_hash for item in selection.component_materializations
        ]
        assert parent.get("n8_authored_joint_relation_ref") is None
        assert parent.get("n8_authored_joint_request_payload_ref") is None
        assert parent.get("n8_authored_joint_intent_digest") is None
        assert len(parent["n8_candidate_parent_atom_ids"]) == 3
        assert len(parent["n8_candidate_parent_atom_content_hashes"]) == 3
        assert parent["n8_candidate_parent_intervention_ids"] == parent["atom_ids"]
        assert len(parent["n8_candidate_parent_child_refs"]) == 3
        assert parent["n8_candidate_member_basis"] == ("hypothetical_all_unique_n4_source_members")
        assert parent["n8_source_candidate_relationship"] == "alternatives"
        assert parent["n8_policy_composition_status"] == "not_established"
        assert parent["n8_policy_composition_limitation_code"] == (
            "n4_source_candidates_are_alternatives_not_authored_compound_design"
        )
        assert parent["n8_child_to_parent_refinement_status"] == "not_established"
        assert parent["n8_child_to_parent_refinement_limitation_code"] == (
            "child_to_parent_refinement_rule_not_established"
        )
        assert parent["n8_joint_scope_status"] == "not_established"
        assert parent["n8_joint_scope_limitation_code"] == (
            "parent_joint_coupling_evidence_not_established"
        )
        assert parent["n8_status"] == "value_conditional"
        assert parent["n8_candidate_decision_grade"] == "low"
        assert parent["n8_candidate_value_ref"] == parent["simulation_result_ref"]["artifact_id"]
        assert {
            "n5_execution_request_provenance_not_established",
            "n4_source_candidates_are_alternatives_not_authored_compound_design",
            "child_to_parent_refinement_rule_not_established",
        }.issubset(set(parent["n8_authority_blockers"]))
        assert parent["n8_numeric_interaction_basis"] == "finite_checked_model_point_estimate_only"
        expected_seeds = [physical_request.seed, physical_request.seed + 1]
        outcome = compiled.design_problem.outcome_of_interest.target_variable
        baseline = float(physical_request.baseline_state[outcome])
        assert physical_request.replications == 2
        assert physical_request.seed == handoff.profile.n5.seed
        assert physical_request.baseline_state == handoff.profile.n5.baseline_state
        assert physical_request.selected_outcomes == (outcome,)
        assert parent["replication_seeds"] == expected_seeds
        assert evidence["interaction_sampling_status"] == "estimated"
        expected_pair_keys = {
            frozenset((left, right))
            for index, left in enumerate(parent["atom_ids"])
            for right in parent["atom_ids"][index + 1 :]
        }
        served_pair_rows = evidence["interaction_terms"]
        assert len(served_pair_rows) == len(expected_pair_keys)
        assert {frozenset(term["atom_ids"]) for term in served_pair_rows} == expected_pair_keys
        for term in served_pair_rows:
            summary = term["replication_sampling_by_step"]["0"]
            assert summary["status"] == "estimated"
            assert summary["replicate_count"] == len(expected_seeds)
            assert summary["seeds"] == expected_seeds
            assert len(summary["samples"]) == len(summary["seeds"]) == summary["replicate_count"]
            assert summary["samples"] == [
                {"seed": expected_seeds[0], "value": baseline},
                {"seed": expected_seeds[1], "value": baseline},
            ]
            assert summary["mean"] == baseline
            assert summary["standard_error"] == 0.0

        served_residual = evidence["higher_order_residual_sampling"][outcome]["0"]
        assert served_residual["status"] == "estimated"
        assert served_residual["replicate_count"] == len(expected_seeds)
        assert served_residual["seeds"] == expected_seeds
        assert (
            len(served_residual["samples"])
            == len(served_residual["seeds"])
            == served_residual["replicate_count"]
        )
        assert served_residual["samples"] == [
            {"seed": expected_seeds[0], "value": 1.0 - baseline},
            {"seed": expected_seeds[1], "value": -1.0 - baseline},
        ]
        assert served_residual["mean"] == -baseline
        assert served_residual["standard_error"] == pytest.approx(1.0)

        result_ref = ArtifactRef.model_validate(parent["simulation_result_ref"])
        assert result_ref.manifest_profile_sha256 is not None
        assert parent["world_model_record_content_hash"] is not None
        with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
            persisted_result = load_joint_simulation_result(
                result_ref,
                store=fresh_context.store,
                expected_world_model_record_content_hash=parent["world_model_record_content_hash"],
                expected_atom_ids=tuple(parent["atom_ids"]),
                expected_selected_outcomes=tuple(parent["selected_outcomes"]),
            )
        persisted_residual = persisted_result.higher_order_residual_sampling[outcome][0]
        assert persisted_residual.status == served_residual["status"]
        assert persisted_residual.replicate_count == len(expected_seeds)
        assert persisted_residual.seeds == tuple(served_residual["seeds"])
        assert [sample.seed for sample in persisted_residual.samples] == expected_seeds
        assert [sample.effects["derived_effect"] for sample in persisted_residual.samples] == [
            sample["value"] for sample in served_residual["samples"]
        ]
        assert persisted_result.higher_order_residuals[outcome][0] == served_residual["mean"]
        assert persisted_residual.effects_standard_error["derived_effect"] == pytest.approx(
            served_residual["standard_error"]
        )
