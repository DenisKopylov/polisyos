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

        # Exercise the same served run through parent profile faults. These are
        # targeted reader failures after the real worker persisted the parent and
        # independently readable children; no parent evidence is invented.
        parent_ref = ArtifactRef.model_validate(
            projection["joint_parent_observations"][0]["simulation_result_ref"]
        )
        from polisyos.core.artifacts import ArtifactOwnershipError
        from polisyos.core.artifacts.ownership import ArtifactReadOnlyUnavailableError
        from polisyos.runtime.http.routes import runs as runs_route

        def is_parent(ref: Any) -> bool:
            return (
                getattr(ref, "artifact_id", None) == parent_ref.artifact_id
                and getattr(ref, "manifest_profile_sha256", None)
                == parent_ref.manifest_profile_sha256
            )

        def checked_parent_limitation(response: Any, code: str) -> None:
            assert response.status_code == 200, response.text
            result = response.json()["run"]["generic_cycle_simulation"]
            assert result["joint_parent_status"] == "not_established"
            assert result["joint_parent_limitation_code"] == code
            assert not result.get("joint_parent_observations", [])
            assert {
                (row["node_ref"], row["candidate_id"]) for row in result["n5_observations"]
            } == before_keys
            assert any(
                row["n5_owner_join_status"] == "resolved" for row in result["n5_observations"]
            )

        def missing_parent(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if is_parent(ref):
                raise FileNotFoundError("synthetic selected parent missing")
            return original_raw_manifest(ref, *args, **kwargs)

        def invalid_parent(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if is_parent(ref):
                return b"{"
            return original_raw_manifest(ref, *args, **kwargs)

        def unavailable_parent(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if is_parent(ref):
                raise ArtifactReadOnlyUnavailableError("synthetic backend unavailable")
            return original_raw_manifest(ref, *args, **kwargs)

        for failure, expected_code in (
            (missing_parent, "generic_joint_parent_result_unavailable"),
            (invalid_parent, "generic_joint_parent_result_invalid"),
            (unavailable_parent, "generic_joint_parent_result_unavailable"),
        ):
            with monkeypatch.context() as fault:
                fault.setattr(store, "get_raw_manifest_bytes", failure)
                checked_parent_limitation(client.get(f"/api/v1/runs/{run_id}"), expected_code)

        def denied_parent(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if is_parent(ref):
                raise ArtifactOwnershipError("synthetic selected owner denial")
            return original_raw_manifest(ref, *args, **kwargs)

        with monkeypatch.context() as fault:
            fault.setattr(store, "get_raw_manifest_bytes", denied_parent)
            denied_response = client.get(f"/api/v1/runs/{run_id}")
        assert denied_response.status_code == 403, denied_response.text
        assert "n5_observations" not in json.dumps(denied_response.json())

        def inaccessible_parent(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if is_parent(ref):
                raise PermissionError("synthetic filesystem permission failure")
            return original_raw_manifest(ref, *args, **kwargs)

        with monkeypatch.context() as fault:
            fault.setattr(store, "get_raw_manifest_bytes", inaccessible_parent)
            unavailable_response = client.get(f"/api/v1/runs/{run_id}")
        assert unavailable_response.status_code == 503, unavailable_response.text
        assert "n5_observations" not in json.dumps(unavailable_response.json())

        # A denial on the first compiled-root read must not be swallowed by
        # the earlier non-generic projection before the generic sibling read.
        compiled_ref = ArtifactRef.model_validate(projection["source_ref"])
        for cause, expected_status in (
            (ArtifactOwnershipError("one-shot compiled owner denial"), 403),
            (PermissionError("one-shot compiled filesystem denial"), 503),
        ):
            compiled_denials: list[str] = []

            def deny_first_compiled(
                ref: Any,
                *args: Any,
                _calls: list[str] = compiled_denials,
                _cause: Exception = cause,
                **kwargs: Any,
            ) -> bytes:
                if (
                    not _calls
                    and getattr(ref, "artifact_id", None) == compiled_ref.artifact_id
                    and getattr(ref, "manifest_profile_sha256", None)
                    == compiled_ref.manifest_profile_sha256
                ):
                    _calls.append("denied")
                    raise _cause
                return original_raw_manifest(ref, *args, **kwargs)

            with monkeypatch.context() as fault:
                fault.setattr(store, "get_raw_manifest_bytes", deny_first_compiled)
                compiled_denial = client.get(f"/api/v1/runs/{run_id}")
            assert compiled_denials == ["denied"]
            assert compiled_denial.status_code == expected_status, compiled_denial.text
            assert "n5_observations" not in json.dumps(compiled_denial.json())

        # Reader-scope comparison after a valid selected manifest was opened:
        # the injected different tenant is a simulated fault, not evidence of a
        # real foreign owner grant. The actual selector and request are unchanged.
        original_profile_reader = runs_route.read_core_manifest_profile
        scope_checks: list[str] = []

        def foreign_scope(reader: Any, ref: Any, *args: Any, **kwargs: Any) -> Any:
            manifest, declaration = original_profile_reader(reader, ref, *args, **kwargs)
            if is_parent(ref):
                assert manifest.tenant_context is not None
                scope_checks.append("parent")
                foreign = manifest.tenant_context.model_copy(update={"cell_id": "foreign-cell"})
                manifest = manifest.model_copy(update={"tenant_context": foreign})
            return manifest, declaration

        with monkeypatch.context() as fault:
            fault.setattr(runs_route, "read_core_manifest_profile", foreign_scope)
            foreign_response = client.get(f"/api/v1/runs/{run_id}")
        assert scope_checks
        assert foreign_response.status_code == 403, foreign_response.text
        assert "n5_observations" not in json.dumps(foreign_response.json())

        # A dependency wrapper must not turn an explicitly caused owner denial
        # into candidate unavailability. A typed unavailable cause remains
        # unavailable, and an ordinary filesystem permission cause remains 503.
        from polisyos.runtime.http.errors import RuntimeDependencyUnavailableError

        execution_ref = ArtifactRef.model_validate(source_leaf["n5_execution_ref"])
        wrapped_calls: list[str] = []

        def wrapped_raw(target: ArtifactRef, cause: Exception):
            def read(ref: Any, *args: Any, **kwargs: Any) -> bytes:
                if (
                    getattr(ref, "artifact_id", None) == target.artifact_id
                    and getattr(ref, "manifest_profile_sha256", None)
                    == target.manifest_profile_sha256
                ):
                    wrapped_calls.append(str(target.artifact_id))
                    raise RuntimeDependencyUnavailableError("synthetic-cas") from cause
                return original_raw_manifest(ref, *args, **kwargs)

            return read

        def unavailable_from(cause: Exception) -> ArtifactReadOnlyUnavailableError:
            unavailable = ArtifactReadOnlyUnavailableError("selected read unavailable")
            unavailable.__cause__ = cause
            return unavailable

        for target in (parent_ref, execution_ref):
            for cause, expected_status in (
                (ArtifactOwnershipError("nested owner denial"), 403),
                (PermissionError("nested filesystem permission"), 503),
            ):
                wrapped_calls.clear()
                with monkeypatch.context() as fault:
                    fault.setattr(
                        store,
                        "get_raw_manifest_bytes",
                        wrapped_raw(target, unavailable_from(cause)),
                    )
                    nested_response = client.get(f"/api/v1/runs/{run_id}")
                assert wrapped_calls
                assert nested_response.status_code == expected_status, nested_response.text
                assert "n5_observations" not in json.dumps(nested_response.json())

            wrapped_calls.clear()
            with monkeypatch.context() as fault:
                fault.setattr(
                    store,
                    "get_raw_manifest_bytes",
                    wrapped_raw(target, ArtifactOwnershipError("owner denies selected view")),
                )
                wrapped_denial = client.get(f"/api/v1/runs/{run_id}")
            assert wrapped_calls
            assert wrapped_denial.status_code == 403, wrapped_denial.text
            assert "n5_observations" not in json.dumps(wrapped_denial.json())

            wrapped_calls.clear()
            with monkeypatch.context() as fault:
                fault.setattr(
                    store,
                    "get_raw_manifest_bytes",
                    wrapped_raw(target, PermissionError("filesystem refuses selected read")),
                )
                wrapped_permission = client.get(f"/api/v1/runs/{run_id}")
            assert wrapped_calls
            assert wrapped_permission.status_code == 503, wrapped_permission.text
            assert "n5_observations" not in json.dumps(wrapped_permission.json())

            wrapped_calls.clear()
            with monkeypatch.context() as fault:
                fault.setattr(
                    store,
                    "get_raw_manifest_bytes",
                    wrapped_raw(target, ArtifactReadOnlyUnavailableError("reader unavailable")),
                )
                wrapped_unavailable = client.get(f"/api/v1/runs/{run_id}")
            assert wrapped_calls
            if target == parent_ref:
                checked_parent_limitation(
                    wrapped_unavailable, "generic_joint_parent_result_unavailable"
                )
            else:
                assert wrapped_unavailable.status_code == 200, wrapped_unavailable.text
                wrapped_rows = wrapped_unavailable.json()["run"]["generic_cycle_simulation"][
                    "n5_observations"
                ]
                assert {
                    (row["node_ref"], row["candidate_id"]) for row in wrapped_rows
                } == before_keys
                wrapped_leaf = next(
                    row
                    for row in wrapped_rows
                    if row["node_ref"] == source_leaf["node_ref"]
                    and row["candidate_id"] == source_leaf["candidate_id"]
                )
                assert wrapped_leaf["n5_owner_join_status"] == "unavailable"
                assert (
                    "n5_execution_request_provenance_not_established"
                    in wrapped_leaf["authority_blockers"]
                )
                assert any(
                    row["node_ref"] != source_leaf["node_ref"]
                    and row["n5_owner_join_status"] == "resolved"
                    for row in wrapped_rows
                )

        # The second selected parent read denies access after the first succeeded.
        parent_reads: list[int] = []

        def denied_after_parent_read(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if is_parent(ref):
                parent_reads.append(1)
                if len(parent_reads) == 2:
                    raise ArtifactOwnershipError("synthetic post-read owner denial")
            return original_raw_manifest(ref, *args, **kwargs)

        with monkeypatch.context() as fault:
            fault.setattr(store, "get_raw_manifest_bytes", denied_after_parent_read)
            race_response = client.get(f"/api/v1/runs/{run_id}")
        assert len(parent_reads) == 2
        assert race_response.status_code == 403, race_response.text
        assert "n5_observations" not in json.dumps(race_response.json())

        # Deny a distinct child-source view after another sibling could have
        # been replayed. Permission refusal must suppress the whole response.
        last_leaf = max(candidate_before, key=lambda row: row["node_ref"])
        child_ref = ArtifactRef.model_validate(last_leaf["n4_source_ref"])
        child_denials: list[str] = []

        def denied_child_source(ref: Any, *args: Any, **kwargs: Any) -> bytes:
            if (
                getattr(ref, "artifact_id", None) == child_ref.artifact_id
                and getattr(ref, "manifest_profile_sha256", None)
                == child_ref.manifest_profile_sha256
            ):
                child_denials.append("denied")
                raise ArtifactOwnershipError("synthetic child source denial")
            return original_raw_manifest(ref, *args, **kwargs)

        with monkeypatch.context() as fault:
            fault.setattr(store, "get_raw_manifest_bytes", denied_child_source)
            child_denied_response = client.get(f"/api/v1/runs/{run_id}")
        assert child_denials
        assert child_denied_response.status_code == 403, child_denied_response.text
        assert "n5_observations" not in json.dumps(child_denied_response.json())

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
