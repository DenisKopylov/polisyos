from __future__ import annotations

import json

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.execution_plan import MethodDagNode, PreflightDiagnostic, PreflightReport
from polisyos.scientist.autotune import (
    BenchmarkSplitManifest,
    BenchmarkSuite,
    ChampionRegistry,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
)
from polisyos.scientist.autotune.execution_plan import (
    ExecutionPlanBenchmarkEvaluator,
    ExecutionPlanSearchConfig,
    ExecutionPlanSearchMode,
    TopologyMutation,
    TopologyMutationKind,
    default_execution_plan_policy,
)
from polisyos.scientist.governance.report import GovernanceReport


def _suite(tmp_path):
    dataset_path = tmp_path / "execution_plan_cases.jsonl"
    split_path = tmp_path / "split_manifest.json"
    rows = [{"case_id": "sel"}, {"case_id": "hold"}]
    with open(dataset_path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    split_path.write_text(
        BenchmarkSplitManifest(
            suite_id="execution_plan_suite",
            suite_version="1.0",
            id_field="case_id",
            selection_ids=["sel"],
            holdout_ids=["hold"],
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    return BenchmarkSuite(
        suite_id="execution_plan_suite",
        suite_version="1.0",
        kind="execution_plan",
        dataset_path=str(dataset_path),
        split_manifest_path=str(split_path),
    )


def test_execution_plan_params_only_preserves_method_dag_hash() -> None:
    node = MethodDagNode(node_id="n1", method_fqn="method.a")
    config = ExecutionPlanSearchConfig(
        mode=ExecutionPlanSearchMode.PARAMS_ONLY,
        method_dag=[node],
        fixed_method_dag_hash=ExecutionPlanSearchConfig(method_dag=[node]).method_dag_hash,
        params={"alpha": 1.0},
    )

    assert config.fixed_method_dag_hash == config.method_dag_hash


def test_execution_plan_topology_step_requires_single_mutation() -> None:
    node = MethodDagNode(node_id="n1", method_fqn="method.a")
    config = ExecutionPlanSearchConfig(
        mode=ExecutionPlanSearchMode.TOPOLOGY_STEP,
        method_dag=[node],
        topology_mutation=TopologyMutation(
            kind=TopologyMutationKind.SWAP_METHOD,
            node_id="n1",
            replacement_method_fqn="method.b",
        ),
    )

    assert config.topology_mutation is not None
    assert config.topology_mutation.kind is TopologyMutationKind.SWAP_METHOD


def test_execution_plan_promotion_is_blocked_when_new_blocker_appears(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(store, _suite(tmp_path))
    evaluator = ExecutionPlanBenchmarkEvaluator(store=store, registry=registry)
    candidate_ref = persist_mutation_artifact(
        store,
        ExecutionPlanSearchConfig(
            mode=ExecutionPlanSearchMode.PARAMS_ONLY,
            method_dag=[MethodDagNode(node_id="n1", method_fqn="method.a")],
            params={"trigger_blocker": True},
        ),
    )

    def runner(row, config, context):
        del context
        blocked = row["case_id"] == "hold" and bool(config.params.get("trigger_blocker"))
        preflight = PreflightReport(
            ready_to_run=not blocked,
            diagnostics=(
                [
                    PreflightDiagnostic(
                        code="blocked",
                        severity="blocker",
                        message="blocked by test",
                    )
                ]
                if blocked
                else []
            ),
        )
        return {
            "preflight_report": preflight,
            "governance_report": GovernanceReport(verdict="approve"),
            "backtest_summary": {"score": 0.8},
            "cross_graph_summary": {"score": 0.7},
            "run_stats": {"score": 0.9},
            "compatibility_ok": True,
        }

    evaluation = evaluator.evaluate(
        candidate_ref,
        suite_ref,
        {"store": store, "registry": registry, "execution_plan_runner": runner},
    )
    evaluation_ref = persist_benchmark_evaluation(store, evaluation)
    decision = registry.consider_promotion(
        "execution_plan",
        candidate_ref,
        evaluation_ref,
        default_execution_plan_policy(),
    )

    assert evaluation.guardrails["no_new_blockers"] is False
    assert decision.promoted is False
