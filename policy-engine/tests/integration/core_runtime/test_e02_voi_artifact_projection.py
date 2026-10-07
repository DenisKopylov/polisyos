"""Persist the B11 candidate through Core and preserve its typed preview refusal."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.integration

TENANT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
CELL_ID = "cell-a"


@pytest.mark.asyncio
async def test_informative_voi_candidate_core_readback_and_preview_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Read back actual B11 values, then assert the unowned preview is refused.

    The B11 N6 producer run is real. This fixture manually dispatches a Core
    control-job lease callback to persist that run through the canonical
    compiled-recursive artifact writer; it does not claim an ordinary NL
    request invokes this B11 generator. The recursive wrapper is explicitly
    contract-testing scoped, and the generic content route's refusal is the
    expected boundary until an artifact owner supplies preview authority.
    """

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
        COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality import substrate_registry
    from polisyos.runtime.quality.design_axes.coupling_composition import (
        derive_recursive_design_graph,
    )
    from polisyos.runtime.quality.generation_cycle import JointSimulationPort
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveCycleBudget,
        RecursiveGenerationCycleController,
        RecursiveGenerationCycleRun,
    )
    from polisyos.scientist.methods.search.voi_scheduler import SimpleVOIScheduler
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests.integration.core_runtime.test_e02_hard_feasibility_before_voi import (
        _owner_fixture,
    )
    from tests.integration.core_runtime.test_e02_informative_voi_execution import (
        _bounded_budget,
        _controller,
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

    catalog_root = tmp_path / "voi-preview-catalog"
    catalog_api.build_slice0_fixture_catalog_graph(catalog_root).close()
    curated_root = tmp_path / "voi-preview-curated"
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

    producer_root = tmp_path / "b11-producer"
    producer_store, problem, substrate_context, _high, candidate = _owner_fixture(
        producer_root
    )
    cas_root = producer_root / "runtime-cas"
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    root_node_ref = f"design-problem://{problem_ref.removeprefix('sha256:')}"
    graph = derive_recursive_design_graph(
        design_ref=root_node_ref,
        module_refs=(),
        parent_child_edges=(),
        rule_version_ref="repo://rules/e02-voi-artifact-preview-contract-test",
    )
    cycle_controllers: dict[str, Any] = {}

    def build_cycle_controller(node_ref: str, _problem: object) -> Any:
        controller = _controller(
            store=producer_store,
            problem=problem,
            context=substrate_context,
            candidate=candidate,
            repo_root=repo_root,
        )
        cycle_controllers[node_ref] = controller
        return controller

    recursive_controller = RecursiveGenerationCycleController.for_contract_testing(
        cycle_controller_factory=build_cycle_controller,
        repo_root=repo_root,
        artifact_store=producer_store,
    )
    n5_calls: list[str] = []
    original_n5_call = JointSimulationPort.__call__

    def observe_real_n5_call(self: JointSimulationPort, **kwargs: Any) -> Any:
        n5_calls.append(str(kwargs["candidate"].candidate_id))
        return original_n5_call(self, **kwargs)

    monkeypatch.setattr(JointSimulationPort, "__call__", observe_real_n5_call)
    try:
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            recursive_run = await recursive_controller.run(
                graph,
                problems_by_node={root_node_ref: problem},
                budget_state=_bounded_budget("1.0"),
                recursive_budget=RecursiveCycleBudget(
                    max_depth=0,
                    max_nodes=1,
                    min_cycles_per_leaf=1,
                    max_cycles_per_leaf=1,
                ),
                cycle_substrate_contexts_by_node={root_node_ref: substrate_context},
                execution_intents_by_node={root_node_ref: "candidate_only"},
            )

        assert isinstance(recursive_run, RecursiveGenerationCycleRun)
        assert recursive_run.authority_scope == "contract_testing"
        leaf = recursive_run.leaf_nodes[0]
        assert leaf.cycle_run is not None
        n6_run = leaf.cycle_run
        summary = next(
            row
            for row in n6_run.candidate_summaries
            if row.candidate_id == candidate.candidate_id
        )
        cycle = n6_run.cycles[0]
        assert type(cycle_controllers[root_node_ref]._voi_scheduler) is SimpleVOIScheduler
        assert cycle.voi_decision.scheduler_action == "advance"
        assert cycle.voi_decision.scheduler_reason == "advance_by_information_value"
        assert cycle.simulation.status == "joint_simulated"
        assert cycle.value_port.status == "value_conditional"
        assert summary.proxy_score == 0.0
        assert summary.voi_estimate == 0.4
        assert not summary.certified_by_n9
        assert n5_calls == [candidate.candidate_id]

        compiled_payload = {
            "schema_version": COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
            "design_problem_ref": problem_ref,
            "design_problem": problem.model_dump(mode="json"),
            "cycle_substrate_context_ref": None,
            "recursive_run": recursive_run.model_dump(
                mode="json", exclude={"leaf_nodes"}
            ),
        }
        compiled = CompiledRecursiveGenerationCycleRun.model_validate(
            {**compiled_payload, "content_hash": gy_content_hash(compiled_payload)}
        )

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
                    "request": "Record a bounded candidate run for typed readback.",
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

            def persist_b11_run_for_owned_job(
                owner_service: Any,
                *,
                expected_job_id: str,
            ) -> None:
                admission = owner_service._control_store.current_execution_job_admission()
                job = admission.job
                scope = admission.scope
                assert job.job_id == expected_job_id
                assert scope.status == "established"
                assert (scope.tenant_id, scope.cell_id) == (TENANT_ID, CELL_ID)

                with owner_service._install_execution_scope(scope):
                    core_run_id, core_context = owner_service._start_generation_run_context(
                        job=job,
                        execution_scope=scope,
                    )
                    compiled_ref = owner_service._put_json_artifact_ref(
                        compiled.model_dump(mode="json"),
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
                        "status": "candidate_run_recorded",
                        "execution_band": "candidate",
                        "candidate_computation_status": "completed",
                        "execution_intent_band": "simulate_only",
                        "run_id": job.run_id,
                        "compiled_recursive_generation_cycle_ref": str(
                            compiled_ref.artifact_id
                        ),
                        "compiled_recursive_generation_cycle_artifact_ref": (
                            compiled_ref.model_dump(mode="json")
                        ),
                        "n5_status": cycle.simulation.status,
                        "n8_status": cycle.value_port.status,
                        "root_n9_status": "not_run",
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
                    handler=lambda _snapshot: persist_b11_run_for_owned_job(
                        service,
                        expected_job_id=accepted["job_id"],
                    ),
                    expected_job_id=accepted["job_id"],
                )
                == accepted["job_id"]
            )
            completed = service._control_store.get_job(accepted["job_id"])
            assert completed is not None and completed.state == "completed"
            core_run_id = str(completed.progress["core_run_id"])
            compiled_ref = compiled_refs[accepted["job_id"]]

        # The fresh context resolves the artifact from Core's attempt manifest,
        # not from the mutable progress summary or a test-only JSON artifact.
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
            fresh_service = fresh_app.state._control_service
            fresh_job = fresh_service._control_store.get_job(accepted["job_id"])
            assert fresh_job is not None and fresh_job.state == "completed"
            core_source = fresh_service.resolve_completed_control_job_core_run_source(
                fresh_job,
                expected_control_run_id=str(fresh_job.run_id or ""),
                tenant_id=TENANT_ID,
                cell_id=CELL_ID,
            )
            outputs = core_source.manifest.outputs
            assert len(outputs) == 1
            owned_ref = outputs[0]
            assert owned_ref.kind == "runtime.compiled_recursive_generation_cycle"
            assert artifact_ref_identity_key(owned_ref) == artifact_ref_identity_key(
                compiled_ref
            )

            with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
                assert fresh_context.store.verify(owned_ref).ok
                persisted_bytes = fresh_context.store.get_bytes(owned_ref)
            persisted = CompiledRecursiveGenerationCycleRun.model_validate(
                canon.from_canonical_bytes(persisted_bytes)
            )
            assert isinstance(persisted.recursive_run, RecursiveGenerationCycleRun)
            persisted_leaf = persisted.recursive_run.leaf_nodes[0]
            assert persisted_leaf.cycle_run is not None
            persisted_summary = next(
                row
                for row in persisted_leaf.cycle_run.candidate_summaries
                if row.candidate_id == candidate.candidate_id
            )
            assert persisted_summary.candidate_id == summary.candidate_id
            assert persisted_summary.content_hash == summary.content_hash
            assert persisted_summary.proxy_score == 0.0
            assert persisted_summary.voi_estimate == 0.4
            assert persisted_summary.certified_by_n9 is False

            artifact_id = str(owned_ref.artifact_id)
            preview_response = fresh_client.get(
                f"/api/v1/artifacts/{artifact_id}/content"
            )
            assert preview_response.status_code == 409, preview_response.text
            refusal = preview_response.json()
            assert refusal["code"] == "authority_surface_admission_blocked"
            decision = refusal["authority_surface_decision"]
            assert decision["surface"] == "artifact"
            assert decision["reason"] == "authority_surface_signal_missing"
            assert decision["blocking"] is True
            assert decision["visible_downgrade"] is True

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
            foreign_preview = fresh_client.get(
                f"/api/v1/artifacts/{artifact_id}/content",
                headers={"X-Tenant-ID": foreign_claims.tenant_id},
            )
            assert foreign_preview.status_code == 403, foreign_preview.text
            assert foreign_preview.json()["code"] == "artifact_tenant_mismatch"
    finally:
        producer_store.close()
