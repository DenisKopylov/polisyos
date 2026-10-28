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
async def test_cubic_joint_residual_survives_persisted_fresh_get_to_n8(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    controlled_candidate_gateway: Any,
) -> None:
    """A synthetic source-bound three-atom parent retains samples; N8 stays pending."""
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )
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
    source_inputs = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "n4-candidate-source-root"
    )
    prepared = await generic_n4_served_replay.prepare_generic_n4_served_replay(
        tmp_path=tmp_path,
        controlled_candidate_gateway=controlled_candidate_gateway,
        monkeypatch=monkeypatch,
        tenant_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        cell_id="cell-b26-joint-candidate",
        child_count=3,
        source_root=source_inputs.root,
    )
    assert prepared.source_root == source_inputs.root
    assert prepared.app_kwargs["repo_root"] == source_inputs.root
    assert prepared.source_root_witness["n4_repo_root"] == str(source_inputs.root)
    assert len(prepared.children) == 3

    def controlled_ncm_step(state: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
        query = state["ncm_query_data"]
        intervention = query.interventions[0]
        del params
        value = 0.0
        if len(intervention) == 3:
            value = 1.0
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
        fresh_run = fresh_response.json()["run"]
        projection = fresh_run["generic_cycle_simulation"]
        candidate_before = projection["n5_observations"]
        source_leaf = next(
            row for row in projection["n5_observations"] if row["n5_execution_ref"] is not None
        )
        assert source_leaf["n5_owner_join_status"] == "resolved"
        owner_artifact_id = str(source_leaf["n5_execution_ref"]["artifact_id"])
        store = service._artifact_store
        original_raw_manifest = store.get_raw_manifest_bytes
        missing_owner_calls: list[str] = []

        def missing_one_owner(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if str(getattr(ref, "artifact_id", "")) == owner_artifact_id:
                missing_owner_calls.append(owner_artifact_id)
                raise FileNotFoundError("synthetic missing selected owner manifest")
            return original_raw_manifest(ref, *args, **kwargs)

        with monkeypatch.context() as missing_owner:
            missing_owner.setattr(store, "get_raw_manifest_bytes", missing_one_owner)
            missing_response = client.get(f"/api/v1/runs/{run_id}")
        assert missing_response.status_code == 200, missing_response.text
        assert missing_owner_calls
        candidates_after = missing_response.json()["run"]["generic_cycle_simulation"][
            "n5_observations"
        ]
        before_keys = {(row["node_ref"], row["candidate_id"]) for row in candidate_before}
        after_keys = {(row["node_ref"], row["candidate_id"]) for row in candidates_after}
        assert len(before_keys) >= 2
        assert after_keys == before_keys
        limited_leaf = next(
            row
            for row in candidates_after
            if row["node_ref"] == source_leaf["node_ref"]
            and row["candidate_id"] == source_leaf["candidate_id"]
        )
        assert limited_leaf["status"] == "joint_simulated"
        assert limited_leaf["n5_owner_join_status"] == "unavailable"
        assert limited_leaf["simulation_result_ref"] is not None
        assert any(
            row["node_ref"] != source_leaf["node_ref"] and row["n5_owner_join_status"] == "resolved"
            for row in candidates_after
        )
        assert (
            "n5_execution_request_provenance_not_established" in limited_leaf["authority_blockers"]
        )

        # Present a foreign candidate expectation while the selected execution
        # view is unavailable. The real owner must compare the independently
        # readable input before returning an unknown execution limitation.
        from polisyos.runtime.quality.generic_simulation_admission import (
            GenericCycleSimulationAdmissionOwner,
        )

        resolve_owner = GenericCycleSimulationAdmissionOwner.resolve_n5_execution_join
        mismatches: list[str] = []

        def mismatched_owner(owner: Any, ref: Any, *, expected: Any) -> Any:
            if str(ref.artifact_id) == owner_artifact_id:
                mismatches.append(owner_artifact_id)
                expected = expected.model_copy(update={"candidate_id": "foreign-candidate"})
            return resolve_owner(owner, ref, expected=expected)

        missing_owner_calls.clear()
        with monkeypatch.context() as mismatch:
            mismatch.setattr(store, "get_raw_manifest_bytes", missing_one_owner)
            mismatch.setattr(
                GenericCycleSimulationAdmissionOwner, "resolve_n5_execution_join", mismatched_owner
            )
            mismatch_response = client.get(f"/api/v1/runs/{run_id}")
        assert mismatch_response.status_code == 200, mismatch_response.text
        assert mismatches
        conflict_projection = mismatch_response.json()["run"]["generic_cycle_simulation"]
        conflict_rows = conflict_projection["n5_observations"]
        assert {(row["node_ref"], row["candidate_id"]) for row in conflict_rows} == before_keys
        assert conflict_projection["publication_authority"] is False
        conflicting_leaf = next(
            row
            for row in conflict_rows
            if row["node_ref"] == source_leaf["node_ref"]
            and row["candidate_id"] == source_leaf["candidate_id"]
        )
        assert conflicting_leaf["status"] == "simulation_blocked"
        assert conflicting_leaf["n8_status"] == "value_blocked"
        assert conflicting_leaf["n5_owner_join_status"] == "mismatch"
        assert (
            conflicting_leaf["n5_owner_join_limitation_code"]
            == "generic_n5_input_cycle_join_mismatch"
        )
        assert not missing_owner_calls
        assert "n5_execution_request_provenance_conflict" in conflicting_leaf["authority_blockers"]

        # The input has a self-hashed complete profile. A different selected
        # seed in the independently supplied expected profile must be a known
        # conflict even when the later execution view is unavailable.
        from polisyos.pdc import gy_content_hash

        profile_mismatches: list[str] = []

        def different_profile(owner: Any, ref: Any, *, expected: Any) -> Any:
            if str(ref.artifact_id) == owner_artifact_id:
                assert expected.profile is not None
                profile_mismatches.append(owner_artifact_id)
                payload = expected.profile.model_dump(mode="json", exclude={"content_hash"})
                payload["n5"]["seed"] += 1
                foreign_profile = type(expected.profile).model_validate(
                    {**payload, "content_hash": gy_content_hash(payload)}
                )
                expected = expected.model_copy(update={"profile": foreign_profile})
            return resolve_owner(owner, ref, expected=expected)

        missing_owner_calls.clear()
        with monkeypatch.context() as mismatch:
            mismatch.setattr(store, "get_raw_manifest_bytes", missing_one_owner)
            mismatch.setattr(
                GenericCycleSimulationAdmissionOwner, "resolve_n5_execution_join", different_profile
            )
            profile_response = client.get(f"/api/v1/runs/{run_id}")
        assert profile_response.status_code == 200, profile_response.text
        assert profile_mismatches
        profile_rows = profile_response.json()["run"]["generic_cycle_simulation"]["n5_observations"]
        assert {(row["node_ref"], row["candidate_id"]) for row in profile_rows} == before_keys
        profile_leaf = next(
            row
            for row in profile_rows
            if row["node_ref"] == source_leaf["node_ref"]
            and row["candidate_id"] == source_leaf["candidate_id"]
        )
        assert profile_leaf["status"] == "simulation_blocked"
        assert profile_leaf["n5_owner_join_status"] == "mismatch"
        assert profile_leaf["n5_owner_join_limitation_code"] == (
            "generic_n5_input_cycle_join_mismatch"
        )
        assert any(
            row["node_ref"] != source_leaf["node_ref"] and row["n5_owner_join_status"] == "resolved"
            for row in profile_rows
        )
        assert not missing_owner_calls

    root_ref = "design-problem://" + cycle_job_design_problem_ref(
        prepared.recorded_problem
    ).removeprefix("sha256:")
    assert projection["joint_parent_status"] == "resolved"
    parent_rows = [
        row for row in projection["joint_parent_observations"] if row["node_ref"] == root_ref
    ]
    assert len(parent_rows) == 1
    parent = parent_rows[0]
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
    assert parent["n8_status"] == "value_conditional"
    assert parent["n8_candidate_decision_grade"] == "low"
    assert parent["n8_candidate_value_ref"] == parent["simulation_result_ref"]["artifact_id"]
    assert parent["n8_numeric_interaction_basis"] == "finite_checked_model_point_estimate_only"
    assert (
        "n4_source_candidates_are_alternatives_not_authored_compound_design"
        in parent["n8_authority_blockers"]
    )
    assert "n5_execution_request_provenance_not_established" in parent["n8_authority_blockers"]
    assert evidence["higher_order_residual_sampling_status"] == "estimated"
    assert evidence["numeric_interaction"] == "non_additive"
    assert evidence["numeric_interaction_basis"] == "finite_checked_model_point_estimate_only"

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
        assert summary["seeds"] == expected_seeds
        assert summary["samples"] == [
            {"seed": expected_seeds[0], "value": baseline},
            {"seed": expected_seeds[1], "value": baseline},
        ]
        assert summary["mean"] == baseline
        assert summary["standard_error"] == 0.0

    served_residual = evidence["higher_order_residual_sampling"][outcome]["0"]
    assert served_residual["status"] == "estimated"
    assert served_residual["seeds"] == expected_seeds
    assert served_residual["samples"] == [
        {"seed": expected_seeds[0], "value": 1.0 - baseline},
        {"seed": expected_seeds[1], "value": 1.0 - baseline},
    ]
    assert served_residual["mean"] == 1.0 - baseline
    assert served_residual["standard_error"] == pytest.approx(0.0)

    result_ref = ArtifactRef.model_validate(parent["simulation_result_ref"])
    assert result_ref.manifest_profile_sha256 is not None
    result_manifest = service._artifact_store.get_manifest(result_ref)
    assert result_manifest.tenant_context is not None
    assert result_manifest.tenant_context.tenant_id == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    assert result_manifest.tenant_context.cell_id == "cell-b26-joint-candidate"
    result = service._artifact_store.get_json(result_ref)
    residual = result["higher_order_residual_sampling"][outcome][0]
    assert residual["samples"] == [
        {"seed": expected_seeds[0], "value": 1.0 - baseline},
        {"seed": expected_seeds[1], "value": 1.0 - baseline},
    ]
    assert residual["mean"] == 1.0 - baseline
    assert residual["standard_error"] == pytest.approx(0.0)
