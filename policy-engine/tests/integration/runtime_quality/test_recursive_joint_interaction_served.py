from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
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
    """A synthetic source-bound three-atom parent retains samples; N8 stays pending."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts import read_core_json_artifact
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.services.control import generation_cycle as compiler_owner
    from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
    from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result
    from tests._helpers.control_worker import dispatch_one_control_job

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
    prepared = await generic_n4_served_replay.prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        cell_id="cell-b26-joint-candidate",
        child_count=3,
    )
    assert len(prepared.children) == 3

    def controlled_ncm_step(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        query = state["ncm_query_data"]
        intervention = query.interventions[0]
        seed = int(params["__seed__"])
        value = 0.0
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
        assert job is not None and job.state == "completed"
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
    with tenant_scope(None, tenant_id=prepared.tenant_id, cell_id=prepared.cell_id):
        assert service._artifact_store.verify(served_compiled_ref).ok
        compiled = compiler_owner.CompiledRecursiveGenerationCycleRun.model_validate(
            read_core_json_artifact(service._artifact_store, served_compiled_ref).value
        )
    served_root_node_ref = "design-problem://" + cycle_job_design_problem_ref(
        compiled.design_problem
    ).removeprefix("sha256:")
    assert compiled.recursive_run.root_node_ref == served_root_node_ref
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
    assert parent["n8_status"] == "value_pending_n8"
    assert parent["n8_numeric_interaction_basis"] == "finite_checked_model_point_estimate_only"
    expected_seeds = [prepared.root_profile.n5.seed, prepared.root_profile.n5.seed + 1]
    outcome = prepared.recorded_problem.outcome_of_interest.target_variable
    baseline = float(prepared.root_profile.n5.baseline_state[outcome])
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
            store=service._artifact_store,
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
