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

import copy
import os
from dataclasses import replace
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
    from polisyos.data_forge.read_api import catalog as catalog_api
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http import dev_identity_middleware
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.http.security import build_fixture_identity_claims
    from polisyos.runtime.http.services.control.generation_cycle import (
        COMPILED_RECURSIVE_GENERATION_CYCLE_PARTIAL_SCHEMA_VERSION,
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality import recursive_generation_cycle, substrate_registry
    from polisyos.runtime.quality.generation_cycle import (
        validate_generation_cycle_run_history,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
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

    if os.environ.get("POLISYOS_E02_NESTED_N6_HISTORY_REMOVAL") == "1":

        def removed_recursive_history_check(
            _payload: object,
        ) -> tuple[dict[str, Any], ...]:
            return ()

        monkeypatch.setattr(
            recursive_generation_cycle,
            "validate_generation_cycle_run_history",
            removed_recursive_history_check,
        )

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv(
        "POLISYOS_CONTROL_SQLITE_PATH", (tmp_path / "control.sqlite3").as_posix()
    )
    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())

    # App startup reads the substrate catalog even though this checkpoint path
    # does not acquire data. Give startup its own real, bounded Slice 0 catalog.
    catalog_root = tmp_path / "recursive-partial-catalog"
    catalog_api.build_slice0_fixture_catalog_graph(catalog_root).close()
    curated_root = tmp_path / "recursive-partial-curated"
    curated_root.mkdir()
    monkeypatch.setenv("POLISYOS_CURATED_DIR", curated_root.as_posix())
    monkeypatch.setattr(
        catalog_api,
        "default_acquisition_overlay_path",
        lambda _root: tmp_path / "absent-acquisition-overlay.duckdb",
    )
    default_catalog_paths = substrate_registry.default_substrate_catalog_paths
    repo_root = Path(__file__).resolve().parents[3]
    monkeypatch.setattr(
        substrate_registry,
        "default_substrate_catalog_paths",
        lambda root: (
            replace(
                default_catalog_paths(root),
                l1_dcat_path=catalog_root / "catalog.duckdb",
            )
            if Path(root).resolve() == repo_root
            else default_catalog_paths(root)
        ),
    )

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
    compiled_wire = compiled.model_dump(mode="json")
    leaf_promotion_statuses = {
        node.node_ref: node.cycle_run.promotion_port.status
        for node in partial_result.leaf_nodes
        if node.cycle_run is not None
    }

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
        compiled_refs: dict[str, ArtifactRef] = {}
        observed_job_scopes: dict[str, tuple[str | None, str | None]] = {}

        def persist_manual_partial_for_owned_job(
            owner_service: Any,
            *,
            expected_job_id: str,
            expected_tenant_id: str,
            expected_cell_id: str,
            artifact_payload: dict[str, Any] | None = None,
        ) -> None:
            admission = owner_service._control_store.current_execution_job_admission()
            job = admission.job
            scope = admission.scope
            assert job.job_id == expected_job_id
            assert scope.status == "established"
            assert (scope.tenant_id, scope.cell_id) == (
                expected_tenant_id,
                expected_cell_id,
            )
            observed_job_scopes[job.job_id] = (scope.tenant_id, scope.cell_id)

            with owner_service._install_execution_scope(scope):
                core_run_id, core_context = owner_service._start_generation_run_context(
                    job=job,
                    execution_scope=scope,
                )
                compiled_ref = owner_service._put_json_artifact_ref(
                    compiled_wire if artifact_payload is None else artifact_payload,
                    kind="runtime.compiled_recursive_generation_cycle",
                    schema_name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
                )
                core_manifest_ref = owner_service._publish_generation_run(
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
                    "root_n9_status": "not_run",
                    "leaf_promotion_statuses": leaf_promotion_statuses,
                    "publication_status": "not_run",
                    **owner_service._core_run_progress_fields(
                        job=job,
                        core_run_id=core_run_id,
                        manifest_ref=core_manifest_ref,
                    ),
                }
                owner_service._control_store.complete_job(
                    job_id=job.job_id,
                    run_id=job.run_id,
                    capability_manifest_ref=job.capability_manifest_ref,
                    progress=progress,
                )
                compiled_refs[job.job_id] = compiled_ref

        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=lambda _snapshot: persist_manual_partial_for_owned_job(
                    service,
                    expected_job_id=accepted["job_id"],
                    expected_tenant_id=TENANT_ID,
                    expected_cell_id=CELL_ID,
                ),
                expected_job_id=accepted["job_id"],
            )
            == accepted["job_id"]
        )
        completed = service._control_store.get_job(accepted["job_id"])
        assert completed is not None and completed.state == "completed"
        compiled_ref = compiled_refs[accepted["job_id"]]
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
        assert checkpoint["schema_version"] == "policyos.runtime.recursive_cycle_checkpoint.v1"
        assert checkpoint["status"] == "partial"
        assert checkpoint["pending_frontier"] == list(partial_result.frontier_node_refs)
        assert checkpoint["completed_design_refs"] == [
            node.node_ref for node in partial_result.leaf_nodes
        ]
        assert checkpoint["stop_node_ref"] == partial_result.budget_stop_node_ref
        assert checkpoint["root_design_problem_ref"] == problem_ref
        assert checkpoint["root_n9_status"] == "not_run"
        assert checkpoint["leaf_promotion_statuses"] == leaf_promotion_statuses
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
        assert persisted.recursive_run.schema_version == partial_result.schema_version
        assert persisted.recursive_run.content_hash == partial_result.content_hash
        assert persisted.recursive_run.terminal is None
        assert persisted.recursive_run.frontier_node_refs == partial_result.frontier_node_refs

        # The controller fixture emits an authentic stop projection on the
        # budget-stopped leaf. Each negative below changes one valid-enum
        # sibling projection while keeping the stop marker and terminal intact.
        stop_leaf_wire = next(
            node
            for node in compiled_wire["recursive_run"]["nodes"]
            if node["node_ref"] == partial_result.budget_stop_node_ref
        )
        stop_leaf_run = stop_leaf_wire["cycle_run"]
        stop_cycle = stop_leaf_run["cycles"][-1]
        assert stop_cycle["voi_decision"]["next_action"] == "stop"
        assert stop_cycle["refinement_decision"]["decision"] in {"stop", "abstain"}
        assert stop_cycle["search_iteration"]["status"] in {"stopped", "abstained"}
        assert validate_generation_cycle_run_history(stop_leaf_run) == ()

        def persist_corrupt_projection(
            *,
            projection_name: str,
            expected_history_issue: str,
            mutate: Any,
        ) -> None:
            corrupt_wire = copy.deepcopy(compiled_wire)
            recursive_wire = corrupt_wire["recursive_run"]
            corrupt_leaf = next(
                node
                for node in recursive_wire["nodes"]
                if node["node_ref"] == partial_result.budget_stop_node_ref
            )
            corrupt_cycle = corrupt_leaf["cycle_run"]["cycles"][-1]
            mutate(corrupt_cycle)

            # The terminal marker and the other projection remain authentic;
            # only one valid-enum nested N6 history field diverges.
            assert corrupt_cycle["voi_decision"]["next_action"] == "stop"
            assert corrupt_cycle["terminal_kind"] == stop_cycle["terminal_kind"]
            assert (
                validate_generation_cycle_run_history(corrupt_leaf["cycle_run"])[0]["code"]
                == expected_history_issue
            )

            partial_hash_payload = {
                key: value for key, value in recursive_wire.items() if key != "content_hash"
            }
            recursive_wire["content_hash"] = gy_content_hash(partial_hash_payload)
            compiled_hash_payload = {
                key: value for key, value in corrupt_wire.items() if key != "content_hash"
            }
            corrupt_wire["content_hash"] = gy_content_hash(compiled_hash_payload)

            negative_response = fresh_client.post(
                "/api/v1/control/runs/nl",
                json={
                    "request": "Read back a bounded recursive history refusal.",
                    "llm_model": "simulated-qwen",
                    "context": {
                        "evaluation_safety_attempt": _valid_intake_for_mode(
                            "simulate_only"
                        ).model_dump(mode="json")
                    },
                },
            )
            assert negative_response.status_code == 200, negative_response.text
            negative_job_id = negative_response.json()["job_id"]
            negative_service = fresh_app.state._control_service
            assert (
                dispatch_one_control_job(
                    store=negative_service._control_store,
                    handler=lambda _snapshot: persist_manual_partial_for_owned_job(
                        negative_service,
                        expected_job_id=negative_job_id,
                        expected_tenant_id=TENANT_ID,
                        expected_cell_id=CELL_ID,
                        artifact_payload=corrupt_wire,
                    ),
                    expected_job_id=negative_job_id,
                )
                == negative_job_id
            )
            negative_job = negative_service._control_store.get_job(negative_job_id)
            assert negative_job is not None and negative_job.state == "completed"
            negative_run_id = str(negative_job.progress["core_run_id"])
            negative_readback_context = build_runtime_api_context(
                cas_root=cas_root,
                core_runs_root=cas_root / "runs",
            )
            negative_readback_app = create_runtime_api_app(
                cas_root=cas_root,
                container_overrides=RuntimeContainerOverrides(
                    runtime_api_context=negative_readback_context
                ),
                allow_fixture_identity=True,
            )
            with TestClient(negative_readback_app) as negative_client:
                negative_get = negative_client.get(f"/api/v1/runs/{negative_run_id}")
                assert negative_get.status_code == 200, negative_get.text
                negative_run = negative_get.json()["run"]
                assert negative_run.get("recursive_cycle_checkpoint") is None, (
                    f"fresh GET projected a checkpoint after nested {projection_name} "
                    "diverged while outer and recursive hashes remained valid"
                )

        persist_corrupt_projection(
            projection_name="SearchIteration.status",
            expected_history_issue="generation_cycle_terminal_projection_mismatch",
            mutate=lambda cycle: cycle["search_iteration"].__setitem__(
                "status",
                "abstained" if stop_cycle["search_iteration"]["status"] == "stopped" else "stopped",
            ),
        )
        persist_corrupt_projection(
            projection_name="RefinementDecision.decision",
            expected_history_issue="generation_cycle_terminal_projection_mismatch",
            mutate=lambda cycle: cycle["refinement_decision"].__setitem__(
                "decision",
                "abstain" if stop_cycle["refinement_decision"]["decision"] == "stop" else "stop",
            ),
        )

        # Create a real completed Core attempt under another tenant, using the
        # same bounded typed checkpoint only as foreign-owner input. The target
        # run's resolver must not project this other job's Core output.
        foreign_claims = build_fixture_identity_claims().model_copy(
            update={
                "tenant_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "cell_id": "cell-b",
            }
        )
        monkeypatch.setattr(
            dev_identity_middleware,
            "build_fixture_identity_claims",
            lambda: foreign_claims,
        )
        foreign_accept_response = fresh_client.post(
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
        assert foreign_accept_response.status_code == 200, foreign_accept_response.text
        foreign_job_id = foreign_accept_response.json()["job_id"]
        foreign_service = fresh_app.state._control_service
        assert (
            dispatch_one_control_job(
                store=foreign_service._control_store,
                handler=lambda _snapshot: persist_manual_partial_for_owned_job(
                    foreign_service,
                    expected_job_id=foreign_job_id,
                    expected_tenant_id=foreign_claims.tenant_id,
                    expected_cell_id=foreign_claims.cell_id,
                ),
                expected_job_id=foreign_job_id,
            )
            == foreign_job_id
        )
        foreign_job = foreign_service._control_store.get_job(foreign_job_id)
        assert foreign_job is not None and foreign_job.state == "completed"
        assert observed_job_scopes[foreign_job_id] == (
            foreign_claims.tenant_id,
            foreign_claims.cell_id,
        )
        foreign_projection = foreign_service.resolve_recursive_cycle_checkpoint(
            core_run_id,
            control_job_id=foreign_job_id,
            expected_tenant_id=TENANT_ID,
            expected_cell_id=CELL_ID,
        )
        assert foreign_projection is None

        # An authenticated identity from that foreign tenant also cannot use
        # the ordinary GET surface to read the target run.
        denied = fresh_client.get(
            f"/api/v1/runs/{core_run_id}",
            headers={"X-Tenant-ID": foreign_claims.tenant_id},
        )
        assert denied.status_code == 403, denied.text
        assert denied.json()["code"] == "run_tenant_mismatch"
