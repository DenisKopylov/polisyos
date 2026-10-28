"""Identical-input Runtime producer proof before distinct-candidate comparison."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from _helpers.completed_ex_ante_runtime import (
    launch_completed_ex_ante_source,
    launch_completed_workflow,
    reconcile_observed_method_occurrence,
)
from _helpers.control_worker import stop_embedded_control_worker
from unit.runtime.http.test_observational_method_runtime import (
    c48_isolated_runtime_api_env as c48_isolated_runtime_api_env,
)
from unit.scientist.nodes.builtins.decide.test_policy_runtime_method_metrics import (
    _exercise_public_execute_method_metric_source,
)

from polisyos.core.artifacts import artifact_ref_identity_key, validate_core_model_json_artifact
from polisyos.core.contracts.control import WorkflowRunRequest
from polisyos.core.contracts.foundry import ExecPlan, MethodExecutionBundle, ProgramGraph
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.execute import read_state_snapshot_inputs_bounded
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.runtime.http.security import build_fixture_identity_claims
from polisyos.scientist.nodes.builtins.decide import policy_runtime_method_metrics
from polisyos.scientist.orchestration.engine.state import ExperimentState


def test_identical_inputs_complete_two_real_sources_and_refuse_duplicate_ranking(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two real jobs reproduce mean1; duplicate identity never becomes a frontier."""
    env: dict[str, Any] = request.getfixturevalue("c48_isolated_runtime_api_env")
    service = env["app"].state._control_service
    stop_embedded_control_worker(service)
    store = service._artifact_store
    principal = RuntimePrincipal.from_user_claims(build_fixture_identity_claims())
    assert principal.authenticated and principal.fixture_identity
    assert (principal.tenant_id, principal.cell_id) == (env["tenant_a"], env["cell_a"])
    scope = {"tenant_id": principal.tenant_id, "cell_id": principal.cell_id}
    with tenant_scope(None, **scope):
        # Prepare once, then execute twice. No fabricated completion or owner is used.
        prepared = _exercise_public_execute_method_metric_source(
            tmp_path / "same-input",
            monkeypatch,
            artifact_store=store,
            scenario_values=(11.0, 18.0, 44.0),
            prepare_only=True,
        )
    sources = [launch_completed_ex_ante_source(service, prepared, principal) for _ in range(2)]
    assert len({row["launch"].job_id for row in sources}) == 2
    assert len({row["launch"].run_id for row in sources}) == 2
    contracts = []
    observed = []
    for row in sources:
        selected, score, launch = row["selected"], row["score"], row["launch"]
        assert selected.job_id == launch.job_id and selected.run_id == launch.run_id
        assert selected.attempt == row["job"].attempt
        assert selected.source_candidate_ref == prepared["candidate_ref"]
        with tenant_scope(None, **scope):
            current = service.read_current_admitted_method_metric_projection(
                run_id=launch.run_id, **scope
            )
            assert current.status == "selected" and len(current.observations) == 1
            bundle = validate_core_model_json_artifact(
                MethodExecutionBundle, store, selected.method_execution_bundle_ref
            )
            graph = validate_core_model_json_artifact(ProgramGraph, store, bundle.program_graph_ref)
            plan = validate_core_model_json_artifact(ExecPlan, store, bundle.exec_plan_ref)
            assert artifact_ref_identity_key(plan.program_ref) == artifact_ref_identity_key(
                bundle.program_graph_ref
            )
            assert {node.node_id for node in graph.nodes if node.node_kind == "method"} == {
                "ex_ante_node"
            }
            assert set(plan.order) == {node.node_id for node in graph.nodes}
            assert len(plan.order) == len(set(plan.order))
            occurrence = reconcile_observed_method_occurrence(
                store, bundle, occurrence_id=current.observations[0].occurrence_id
            )
            assert occurrence.status == "succeeded" and occurrence.node_id == "ex_ante_node"
            dispatch = occurrence.dispatch
            assert dispatch is not None and dispatch.outcome == "succeeded"
            assert dispatch.selected_backend == dispatch.actual_backend == "numpy"
            assert dispatch.seed_status == dispatch.backend_identity_status == "reconciled"
            assert dispatch.method_metric_input_capture_status == "captured"
            assert dispatch.input_state_ref is not None
            capture = read_state_snapshot_inputs_bounded(
                store,
                snapshot_ref=dispatch.input_state_ref,
                slot_ids=("baseline", "scenario"),
                max_manifest_bytes=16 * 1024 * 1024,
                max_snapshot_payload_bytes=16 * 1024 * 1024,
                max_state_blob_bytes=16 * 1024 * 1024,
                max_entries=32,
                max_elements=1_000_000,
            )
        arrays = dict(capture.arrays)
        baseline, scenario = arrays["baseline"].tolist(), arrays["scenario"].tolist()
        assert baseline == [10.0, 20.0, 40.0] and scenario == [11.0, 18.0, 44.0]
        assert arrays["baseline"].shape == arrays["scenario"].shape == (3,)
        exact = sum(
            (
                Fraction(right) - Fraction(left)
                for left, right in zip(baseline, scenario, strict=True)
            ),
            Fraction(),
        ) / len(baseline)
        assert exact == Fraction(1)
        assert selected.method_metric_projection is not None
        verifier_digest = (
            "sha256:"
            + hashlib.sha256(Path(policy_runtime_method_metrics.__file__).read_bytes()).hexdigest()
        )
        assert selected.method_metric_projection.verifier_implementation_sha256 == verifier_digest
        assert current.vector_ref is not None and score.source_vector_ref is not None
        assert artifact_ref_identity_key(current.vector_ref) == artifact_ref_identity_key(
            score.source_vector_ref
        )
        observation = current.observations[0]
        assert observation.source_status == "observed" and observation.value == float(exact)
        assert observation.objective_id == "objective_ex_ante_mean_change"
        assert observation.metric_id == "metric_ex_ante_mean_change"
        assert observation.input_capture_ref is not None
        assert observation.environment_manifest_ref is not None
        assert bundle.environment_manifest_ref is not None
        assert artifact_ref_identity_key(observation.environment_manifest_ref) == (
            artifact_ref_identity_key(bundle.environment_manifest_ref)
        )
        assert observation.verifier_code_digest == verifier_digest
        assert score.minimized_score == -float(exact) and score.maximizing_coordinate == float(
            exact
        )
        assert score.candidate_ref == prepared["candidate_ref"]
        assert score.revalidation_required is True and score.comparison_contract_sha256
        contracts.append(score.comparison_contract_sha256)
        observed.append(
            {"job_id": launch.job_id, "run_id": launch.run_id, "exact_mean": str(exact)}
        )
    assert contracts[0] == contracts[1]
    request = WorkflowRunRequest(
        data_source={"data_snapshot_ref": prepared["data_snapshot_ref"].model_dump(mode="json")},
        trinity_bundle_ref=prepared["trinity_ref"],
        registry_bundle_ref=prepared["registry_ref"],
        params={
            "control_plane_transition": "legacy_shadow",
            "workflow_id": "scientist_policy_design",
            "policy_candidate_schema": prepared["candidate"].model_dump(mode="json"),
            "policy_search_completed_ex_ante_comparison": {
                "sources": [
                    {
                        "source_run_id": row["launch"].run_id,
                        "candidate_ref": prepared["candidate_ref"].model_dump(mode="json"),
                    }
                    for row in sources
                ]
            },
        },
    )
    planner, job = launch_completed_workflow(service, request, principal)
    assert planner.job_id not in {row["launch"].job_id for row in sources}
    with tenant_scope(None, **scope):
        state_ref = service._legacy_scientist_final_state_ref(job=job)
        assert state_ref is not None
        state = validate_core_model_json_artifact(ExperimentState, store, state_ref)
        comparison = state.params["policy_search_result"]["completed_ex_ante_candidate_comparison"]
        runtime_context = getattr(env["app"].state, "runtime_api_ctx", None)
        if runtime_context is None:
            runtime_context = env["app"].state.runtime_container.runtime_api_context
        runtime_context.run_index.refresh(force=True)
        response = env["client"].get(f"/api/v1/runs/{planner.run_id}/method-metric-comparison")
    assert response.status_code == 200, response.text
    for result in (comparison, response.json()["candidate_comparison"]):
        assert result["status"] == "invalid", result
        assert result["limitations"] == ["completed_candidate_identity_duplicated"]
        assert result["frontier_candidate_hashes"] == []
        assert result["authority_status"] == "candidate_only"
    (tmp_path / "runtime-aa-observed.json").write_text(
        json.dumps(
            {"sources": observed, "contract": contracts[0], "planner_run_id": planner.run_id}
        )
        + "\n"
    )
