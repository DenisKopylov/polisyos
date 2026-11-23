from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from typing import Any, get_args

import pytest
from pydantic import ValidationError

import polisyos.core.contracts.runtime as runtime_contracts
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts import RunGenericCycleSimulationN6CycleHistoryEntry
from polisyos.pdc._impl.gy_waist import SearchTerminalKind
from polisyos.pdc._impl.layer2_design_search import RefinementDecisionKind, SearchIteration
from polisyos.runtime.quality.generation_cycle import (
    GroundingStatus,
    LoopNextAction,
    TerminalStatus,
    ValuePortObservation,
    ValuePortStatus,
)


def test_served_n6_status_types_cover_the_complete_producer_denominator() -> None:
    assert (
        RunGenericCycleSimulationN6CycleHistoryEntry
        is runtime_contracts.RunGenericCycleSimulationN6CycleHistoryEntry
    )
    assert set(get_args(runtime_contracts.RunN6CycleSearchTerminalKind)) == {
        member.value for member in SearchTerminalKind
    }
    assert set(get_args(runtime_contracts.RunN6CycleRefinementDecision)) == set(
        get_args(RefinementDecisionKind)
    )
    assert set(get_args(runtime_contracts.RunN6CycleSearchIterationStatus)) == set(
        get_args(SearchIteration.model_fields["status"].annotation)
    )
    assert set(get_args(runtime_contracts.RunN6CycleGroundingStatus)) == set(
        get_args(GroundingStatus)
    )
    assert set(get_args(runtime_contracts.RunN6CycleValueStatus)) == set(get_args(ValuePortStatus))
    source_decision_grade = get_args(
        get_args(ValuePortObservation.model_fields["decision_grade"].annotation)[0]
    )
    assert set(get_args(runtime_contracts.RunN6CycleValueDecisionGrade)) == set(
        source_decision_grade
    )
    assert set(get_args(runtime_contracts.RunN6CycleVoiAction)) == set(get_args(LoopNextAction))
    assert set(get_args(runtime_contracts.RunN6CycleRunTerminalStatus)) == set(
        get_args(TerminalStatus)
    )


def test_removing_n6_history_rows_while_resolved_marker_remains_is_rejected() -> None:
    source_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="runtime.compiled_recursive_generation_cycle",
        media_type="application/json",
    )
    with pytest.raises(
        ValidationError,
        match="run_generic_projection_n6_history_resolved_without_rows",
    ):
        runtime_contracts.RunGenericCycleSimulationProjection(
            schema_version="policyos.runtime.run_generic_cycle_simulation_projection.v3",
            run_id="controlled-removal",
            artifact_status="resolved",
            source_ref=source_ref,
            source_content_hash="sha256:" + "b" * 64,
            child_profile_status="not_established",
            child_profile_limitation_code="controlled-child-profile-limitation",
            n6_cycle_history_status="resolved",
            n6_cycle_history=(),
        )


def test_credal_v2_projection_keeps_its_existing_schema_without_n6_extension() -> None:
    compiled_ref = ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="runtime.compiled_recursive_generation_cycle",
        media_type="application/json",
    )
    attempt_ref = ArtifactRef(
        artifact_id="sha256:" + "b" * 64,
        kind="runtime.quality.candidate_credal_source_attempt",
        media_type="application/json",
    )
    projection = runtime_contracts.RunGenericCycleSimulationProjection(
        schema_version="policyos.runtime.run_generic_cycle_simulation_projection.v2",
        run_id="credal-v2-compatibility",
        artifact_status="resolved",
        source_ref=compiled_ref,
        source_content_hash="sha256:" + "c" * 64,
        credal_source_attempt_ref=attempt_ref,
        credal_source_status="not_established",
        credal_source_limitation_code="candidate_source_authority_not_established",
        child_profile_status="not_established",
        child_profile_limitation_code="generic_n4_source_generation_not_complete",
        n5_limitation_code="generic_n4_source_generation_not_complete",
        limitation_code="candidate_source_authority_not_established",
    )
    assert (
        projection.schema_version == "policyos.runtime.run_generic_cycle_simulation_projection.v2"
    )
    assert projection.n6_cycle_history_status is None
    assert projection.n6_cycle_history == ()


@pytest.mark.asyncio
async def test_fresh_run_details_serves_produced_n6_terminal_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A new API reads scoped N6 history and refuses each altered stop sibling."""
    from collections.abc import Callable

    from polisyos.core.artifacts import ArtifactWriteOptions
    from polisyos.core.artifacts.manifest import (
        ArtifactTenantContextInfo,
        SchemaInfo,
        artifact_ref_identity_key,
    )
    from polisyos.core.canon import CanonSpec
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.routes import runs as run_routes
    from polisyos.runtime.http.services.control import generation_cycle as cycle_service
    from polisyos.runtime.quality.design_axes.coupling_composition import (
        derive_recursive_design_graph,
    )
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        PendingN8ValuePort,
        ValuePort,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveCycleBudget,
        RecursiveGenerationCycleController,
        RecursiveGenerationCycleRun,
    )
    from tests._helpers.controlled_candidate_profile import (
        _budget,
        _problem,
        _StableShadowGrounding,
    )
    from tests._helpers.runtime_http import (
        _record_fixture_owner,
        _runtime_api_request,
        build_runtime_api_env,
        build_runtime_api_env_from_fixture_seed,
        close_runtime_api_env,
    )
    from tests.unit.runtime.quality.test_generation_cycle import (
        REPO_ROOT,
        _BudgetExhaustedValuePort,
        _CounterexampleAwareGenerator,
        _ReadyValuePort,
    )

    def unexpected_n5(*_args: object, **_kwargs: object) -> None:
        pytest.fail("terminal history replay must not start physical N5")

    monkeypatch.setattr(JointSimulationHorizonController, "run", unexpected_n5)
    monkeypatch.setenv("POLISYOS_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", str(tmp_path / "control.sqlite3"))

    cases = (
        ("frontier_stable", _ReadyValuePort, "stop", "stopped"),
        ("budget_exhausted", _BudgetExhaustedValuePort, "stop", "stopped"),
        ("grounded_abstention", PendingN8ValuePort, "abstain", "abstained"),
    )

    with ExitStack() as resources:
        seed = build_runtime_api_env(
            tmp_path / "runtime", include_test_client=False, seed_ledger_cost_events=False
        )
        resources.callback(close_runtime_api_env, seed)
        context = seed["app"].state.runtime_api_ctx
        assert seed["app"].state._control_service._worker is None
        tenant_id, cell_id = seed["tenant_a"], seed["cell_a"]

        async def persist_stop(
            terminal: str, value_port: Callable[[], ValuePort]
        ) -> tuple[str, ArtifactRef, str]:
            problem = _problem(f"b29_terminal_history_{terminal}")
            root_ref = f"design://b29/terminal-history/{terminal}"
            graph = derive_recursive_design_graph(
                design_ref=root_ref,
                module_refs=(),
                parent_child_edges=(),
                rule_version_ref="repo://policyos/test/cyc05-terminal-history",
            )

            def build_cycle(_node_ref: str, _problem: DesignProblem) -> GenerationCycleController:
                return GenerationCycleController(
                    generation_port=_CounterexampleAwareGenerator(),
                    grounding_port=_StableShadowGrounding(),
                    value_port=value_port(),
                )

            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                controller = RecursiveGenerationCycleController.for_contract_testing(
                    cycle_controller_factory=build_cycle,
                    repo_root=REPO_ROOT,
                    artifact_store=context.store,
                )
                recursive_run = await controller.run(
                    graph,
                    problems_by_node={root_ref: problem},
                    budget_state=_budget(),
                    recursive_budget=RecursiveCycleBudget(
                        max_depth=0, max_nodes=1, min_cycles_per_leaf=1, max_cycles_per_leaf=1
                    ),
                )
                assert recursive_run.terminal.kind.value == terminal
                problem_payload = problem.model_dump(mode="json")
                payload = {
                    "schema_version": (
                        cycle_service.COMPILED_RECURSIVE_GENERATION_CYCLE_GENERIC_PROFILE_SCHEMA_VERSION
                    ),
                    "design_problem_ref": gy_content_hash(problem_payload),
                    "design_problem": problem_payload,
                    "cycle_substrate_context_ref": None,
                    "recursive_run": recursive_run.model_dump(mode="json", exclude={"leaf_nodes"}),
                    # The bounded fixture provides no qualified generic N4 source or child profile.
                    "generic_n4_child_profile_status": "not_established",
                    "generic_n4_child_profile_limitation_code": (
                        "generic_n4_child_profile_not_resolved"
                    ),
                }
                compiled = cycle_service.CompiledRecursiveGenerationCycleRun.model_validate(
                    {
                        **payload,
                        "recursive_run": recursive_run,
                        "content_hash": gy_content_hash(payload),
                    }
                )
                ref = context.store.put_json(
                    compiled.model_dump(mode="json"),
                    ArtifactWriteOptions(
                        kind="runtime.compiled_recursive_generation_cycle",
                        media_type="application/json",
                        schema=SchemaInfo(
                            name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
                            version="1.0",
                        ),
                        tenant_context=ArtifactTenantContextInfo(
                            tenant_id=tenant_id, cell_id=cell_id
                        ),
                    ),
                    canon_spec=CanonSpec(forbid_floats=False),
                    return_selected_profile=True,
                )
                _record_fixture_owner(
                    context.store, ref, tenant_id=tenant_id, cell_id=cell_id, runtime_api_env=seed
                )
            runs, _ = context.run_index.list_runs(
                tenant_id=tenant_id, q="R_fixture_artifact_owner_"
            )
            (run_id,) = (
                run.run_id
                for run in runs
                if ref in context.run_index.get_run(run.run_id).details.root_artifacts
            )
            return run_id, ref, compiled.content_hash

        saved = {
            terminal: await persist_stop(terminal, factory) for terminal, factory, _, _ in cases
        }
        close_runtime_api_env(seed)
        fresh = build_runtime_api_env_from_fixture_seed(seed)
        resources.callback(close_runtime_api_env, fresh)
        assert fresh["app"].state.runtime_api_ctx.store is not context.store
        assert fresh["app"].state._control_service._worker is None

        project_history = run_routes._generic_n6_cycle_history_fields

        def reject_mutation(path: str, field: str, invalid: str) -> None:
            def corrupt_sibling(recursive_run: RecursiveGenerationCycleRun) -> dict[str, Any]:
                fields = project_history(recursive_run)
                (history,) = fields["n6_cycle_history"]
                assert getattr(history, field) != invalid
                return {**fields, "n6_cycle_history": ({**history.model_dump(), field: invalid},)}

            with monkeypatch.context() as corruption:
                corruption.setattr(run_routes, "_generic_n6_cycle_history_fields", corrupt_sibling)
                refusal = _runtime_api_request(fresh, fresh["client"].get, path)
                assert refusal.status_code == 400, refusal.text
                assert "run_generic_n6_stop_projection_mismatch" in refusal.json()["detail"]

        for terminal, _, decision, iteration_status in cases:
            run_id, ref, content_hash = saved[terminal]
            path = f"/api/v1/runs/{run_id}"
            response = _runtime_api_request(fresh, fresh["client"].get, path)
            assert response.status_code == 200, response.text
            wire_run = response.json()["run"]
            assert wire_run["run_id"] == run_id
            projection = wire_run["generic_cycle_simulation"]
            assert projection["artifact_status"] == "resolved", projection
            served_ref = ArtifactRef.model_validate(projection["source_ref"])
            assert artifact_ref_identity_key(served_ref) == artifact_ref_identity_key(ref)
            assert projection["source_content_hash"] == content_hash
            assert projection["child_profile_status"] == "not_established"
            assert projection["n6_cycle_history_status"] == "resolved"
            assert projection["currentness_status"] == "not_established"
            assert projection["authority_purpose"] == "cycle_input_candidate_only"
            assert projection["publication_authority"] is False
            (history,) = projection["n6_cycle_history"]
            assert history["terminal_kind"] == terminal
            assert history["refinement_decision"] == decision
            assert history["search_iteration_status"] == iteration_status
            if terminal == "budget_exhausted":
                assert history["value_authority_blockers"] == ["budget_exhausted_for_next_level"]

            invalid_decision = "stop" if decision == "abstain" else "abstain"
            reject_mutation(path, "refinement_decision", invalid_decision)
            invalid_status = "stopped" if iteration_status == "abstained" else "abstained"
            reject_mutation(path, "search_iteration_status", invalid_status)
            restored = _runtime_api_request(fresh, fresh["client"].get, path)
            assert restored.status_code == 200, restored.text
            assert restored.json()["run"]["generic_cycle_simulation"] == projection
            (tmp_path / f"{terminal}.json").write_bytes(restored.content)
