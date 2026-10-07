"""Owned CAS/API readback for a typed partial recursive checkpoint.

The production NL compiler currently builds a singleton graph. This test uses
the canonical recursive controller's contract-testing budget-stop fixture as
a bounded manual producer, then passes its typed V2 artifact through a real
tenant-scoped control-job lease, the existing Core/CAS writer, and a fresh
run-details app. It does not establish that an ordinary POST produces a
multi-node checkpoint, and the fixture's dependency edges carry no causal
claim.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.integration

TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
CELL_ID = "cell-a"


@pytest.mark.asyncio
async def test_partial_checkpoint_survives_owned_core_cas_and_fresh_run_details_get(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fresh GET preserves a partial checkpoint without manufacturing a root terminal."""

    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient

    from polisyos.core import canon
    from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.services.control.generation_cycle import (
        COMPILED_RECURSIVE_GENERATION_CYCLE_PARTIAL_SCHEMA_VERSION,
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveCycleNode,
        RecursiveGenerationCyclePartialRunV2,
    )
    from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests.integration.runtime_quality.test_e02_recursive_budget_frontier import (
        _recursive_fixture,
        _run_recursive_fixture,
    )
    from tests.unit.runtime.http.test_control_job_execution_intent import (
        _valid_intake_for_mode,
    )

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv(
        "POLISYOS_CONTROL_SQLITE_PATH", (tmp_path / "control.sqlite3").as_posix()
    )
    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())

    root_ref, _child_refs, problems, _request, _graph = _recursive_fixture()
    problem = problems[root_ref]
    partial_result, _partial_children, _partial_request, _factory = (
        await _run_recursive_fixture(
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("0"))}
            )
        )
    )
    assert type(partial_result) is RecursiveGenerationCyclePartialRunV2
    assert partial_result.authority_scope == "contract_testing"
    assert partial_result.terminal is None
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    assert partial_result.root_design_problem_ref == problem_ref

    compiled_payload = {
        "schema_version": COMPILED_RECURSIVE_GENERATION_CYCLE_PARTIAL_SCHEMA_VERSION,
        "design_problem_ref": problem_ref,
        "design_problem": problem.model_dump(mode="json"),
        "cycle_substrate_context_ref": None,
        "recursive_run": partial_result.model_dump(mode="json", exclude={"leaf_nodes"}),
    }
    compiled = CompiledRecursiveGenerationCycleRun.model_validate(
        {**compiled_payload, "content_hash": gy_content_hash(compiled_payload)}
    )

    cas_root = tmp_path / ".polisyos"
    first_context = build_runtime_api_context(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
    )
    first_app = create_runtime_api_app(
        cas_root=cas_root,
        container_overrides=RuntimeContainerOverrides(runtime_api_context=first_context),
        allow_fixture_identity=True,
    )
    with TestClient(first_app) as client:
        accepted_response = client.post(
            "/api/v1/control/runs/nl",
            json={
                "request": "Record a bounded recursive checkpoint for inspection.",
                "llm_model": "simulated-qwen",
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
        compiled_ref: ArtifactRef | None = None

        def persist_manual_partial_through_owned_core_writer(_leased_snapshot: object) -> None:
            nonlocal compiled_ref
            admission = service._control_store.current_execution_job_admission()
            job = admission.job
            scope = admission.scope
            assert job.job_id == accepted["job_id"]
            assert scope.status == "established"
            assert (scope.tenant_id, scope.cell_id) == (TENANT_ID, CELL_ID)

            with service._install_execution_scope(scope):
                core_run_id, core_context = service._start_generation_run_context(
                    job=job,
                    execution_scope=scope,
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
                    "status": "recursive_checkpoint_partial",
                    "execution_band": "candidate",
                    "candidate_computation_status": "completed",
                    "execution_intent_band": "simulate_only",
                    "run_id": job.run_id,
                    "compiled_recursive_generation_cycle_ref": str(compiled_ref.artifact_id),
                    "compiled_recursive_generation_cycle_artifact_ref": (
                        compiled_ref.model_dump(mode="json")
                    ),
                    "n5_status": "not_run_for_budget_stopped_leaf",
                    "n8_status": "not_run",
                    "n9_status": "not_run",
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

        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=persist_manual_partial_through_owned_core_writer,
                expected_job_id=accepted["job_id"],
            )
            == accepted["job_id"]
        )
        completed = service._control_store.get_job(accepted["job_id"])
        assert completed is not None and completed.state == "completed"
        assert compiled_ref is not None
        core_run_id = str(completed.progress["core_run_id"])

    # Reopen both CAS and control state in a fresh runtime/API context. The
    # GET consumer must follow Core's owned output ref, not a mutable progress
    # projection, and must preserve V2's no-terminal semantics.
    fresh_context = build_runtime_api_context(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
    )
    fresh_app = create_runtime_api_app(
        cas_root=cas_root,
        container_overrides=RuntimeContainerOverrides(runtime_api_context=fresh_context),
        allow_fixture_identity=True,
    )
    with TestClient(fresh_app) as fresh_client:
        response = fresh_client.get(f"/api/v1/runs/{core_run_id}")
        assert response.status_code == 200, response.text
        run = response.json()["run"]
        checkpoint = run["recursive_cycle_checkpoint"]
        assert checkpoint["schema_version"] == partial_result.schema_version
        assert checkpoint["status"] == "partial"
        assert checkpoint["pending_frontier"] == list(partial_result.frontier_node_refs)
        assert checkpoint["completed_design_refs"] == [
            node.node_ref
            for node in partial_result.nodes
            if isinstance(node, RecursiveCycleNode)
        ]
        assert checkpoint["stop_node_ref"] == partial_result.budget_stop_node_ref
        assert checkpoint["root_design_problem_ref"] == problem_ref
        projected_ref = ArtifactRef.model_validate(checkpoint["compiled_artifact_ref"])
        assert artifact_ref_identity_key(projected_ref) == artifact_ref_identity_key(
            compiled_ref
        )
        assert "terminal" not in checkpoint
        assert "terminal_status" not in checkpoint
        assert not run.get("conditional_simulation_values")
        assert run["control_job_id"] == completed.job_id

        with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
            raw = fresh_context.store.get_bytes(projected_ref)
        persisted = CompiledRecursiveGenerationCycleRun.model_validate(
            canon.from_canonical_bytes(raw)
        )
        assert type(persisted.recursive_run) is RecursiveGenerationCyclePartialRunV2
        assert persisted.recursive_run.content_hash == partial_result.content_hash
        assert persisted.recursive_run.terminal is None
        assert persisted.recursive_run.frontier_node_refs == partial_result.frontier_node_refs
