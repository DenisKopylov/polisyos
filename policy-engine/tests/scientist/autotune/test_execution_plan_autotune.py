from __future__ import annotations

import json

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.execution_plan import (
    ExecutionPlan,
    MethodDagNode,
    PreflightDiagnostic,
    PreflightReport,
)
from polisyos.foundry.methods import MethodRegistry
from polisyos.foundry.methods.catalog_snapshot import build_method_catalog_snapshot
from polisyos.scientist.autotune import (
    BenchmarkSplit,
    BenchmarkSplitManifest,
    BenchmarkSuite,
    CapabilityAwareExecutionPlanCandidateGenerator,
    ChampionRegistry,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
    suggest_execution_plan_topology_mutations,
)
from polisyos.scientist.autotune.execution_plan import (
    ExecutionPlanBenchmarkEvaluator,
    ExecutionPlanSearchConfig,
    ExecutionPlanSearchMode,
    TopologyMutation,
    TopologyMutationKind,
    _backend_for_method,
    _coerce_candidate_config,
    default_execution_plan_policy,
    execution_plan_search_loop_spec,
)
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.llm_cycle import preflight_execution_plan


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


def test_benchmark_split_manifest_supports_extended_runtime_splits() -> None:
    manifest = BenchmarkSplitManifest(
        suite_id="execution_plan_suite",
        id_field="case_id",
        selection_ids=["sel"],
        hidden_holdout_ids=["hidden"],
        rotating_challenge_ids=["rot"],
        adversarial_ids=["adv"],
        sentinel_ids=["sentinel"],
    )

    assert manifest.split_for("sel") is BenchmarkSplit.SELECTION
    assert manifest.split_for("hidden") is BenchmarkSplit.HIDDEN_HOLDOUT
    assert manifest.split_for("rot") is BenchmarkSplit.ROTATING_CHALLENGE
    assert manifest.split_for("adv") is BenchmarkSplit.ADVERSARIAL
    assert manifest.split_for("sentinel") is BenchmarkSplit.SENTINEL


def test_benchmark_split_manifest_rejects_duplicate_assignments() -> None:
    with pytest.raises(ValueError, match="assigned to both"):
        BenchmarkSplitManifest(
            suite_id="execution_plan_suite",
            id_field="case_id",
            selection_ids=["dup"],
            hidden_holdout_ids=["dup"],
        )


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


def test_suggest_execution_plan_topology_mutations_for_removed_wrapper() -> None:
    snapshot = build_method_catalog_snapshot(run_id="R_exec_autotune")
    config = ExecutionPlanSearchConfig(
        method_dag=[
            MethodDagNode(
                node_id="node_lp",
                method_fqn="optimization.resource_lp@1.0.0",
                notes=["optional_leaf"],
            )
        ]
    )
    report = preflight_execution_plan(
        ExecutionPlan(plan_id="plan_exec_autotune", method_dag=list(config.method_dag)),
        snapshot,
    )

    mutations = suggest_execution_plan_topology_mutations(
        config,
        preflight_report=report,
        catalog=snapshot,
    )

    assert any(
        mutation.kind is TopologyMutationKind.SWAP_METHOD
        and mutation.node_id == "node_lp"
        and mutation.replacement_method_fqn == "optimization.linear.resource_lp@1.0.0"
        for mutation in mutations
    )
    assert any(
        mutation.kind is TopologyMutationKind.DROP_OPTIONAL_NODE
        and mutation.node_id == "node_lp"
        for mutation in mutations
    )


def test_suggest_execution_plan_topology_mutations_accepts_registry_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = build_method_catalog_snapshot(run_id="R_exec_autotune_provider")
    config = ExecutionPlanSearchConfig(
        method_dag=[
            MethodDagNode(
                node_id="node_lp",
                method_fqn="optimization.resource_lp@1.0.0",
                notes=["optional_leaf"],
            )
        ]
    )
    report = preflight_execution_plan(
        ExecutionPlan(plan_id="plan_exec_autotune_provider", method_dag=list(config.method_dag)),
        snapshot,
    )
    registry = MethodRegistry()

    def _unexpected(cls, *args, **kwargs):
        del cls, args, kwargs
        raise AssertionError("global registry lookup should not be used")

    monkeypatch.setattr(MethodRegistry, "get_instance", classmethod(_unexpected))

    mutations = suggest_execution_plan_topology_mutations(
        config,
        preflight_report=report,
        catalog=snapshot,
        registry_provider=lambda: registry,
    )

    assert any(
        mutation.kind is TopologyMutationKind.SWAP_METHOD
        and mutation.node_id == "node_lp"
        for mutation in mutations
    )


def test_capability_aware_generator_emits_topology_candidate_for_missing_method() -> None:
    snapshot = build_method_catalog_snapshot(run_id="R_exec_autotune")
    baseline_plan = ExecutionPlan(
        plan_id="plan_exec_generator",
        method_dag=[
            MethodDagNode(
                node_id="node_lp",
                method_fqn="optimization.resource_lp@1.0.0",
            )
        ],
    )
    report = preflight_execution_plan(baseline_plan, snapshot)

    payload = CapabilityAwareExecutionPlanCandidateGenerator().generate(
        history=[],
        current_best=None,
        context={
            "baseline_execution_plan": baseline_plan,
            "catalog_snapshot": snapshot,
            "preflight_report": report,
        },
    )
    candidate = ExecutionPlanSearchConfig.model_validate(payload)

    assert candidate.mode is ExecutionPlanSearchMode.TOPOLOGY_STEP
    assert candidate.topology_mutation is not None
    assert candidate.topology_mutation.kind is TopologyMutationKind.SWAP_METHOD
    assert candidate.topology_mutation.replacement_method_fqn == "optimization.linear.resource_lp@1.0.0"


def test_execution_plan_search_loop_defaults_to_capability_aware_generator() -> None:
    spec = execution_plan_search_loop_spec()
    assert isinstance(spec.candidate_generator, CapabilityAwareExecutionPlanCandidateGenerator)


def test_with_topology_mutation_uses_branch_local_method_dag_clone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = MethodDagNode(
        node_id="node_lp",
        method_fqn="optimization.resource_lp@1.0.0",
        params={"nested": {"thresholds": [1, 2]}},
        depends_on=["upstream"],
        notes=["optional_leaf"],
    )
    config = ExecutionPlanSearchConfig(method_dag=[original])
    registry = MethodRegistry()

    class _FakeMethod:
        signature = type(
            "Sig",
            (),
            {
                "execution_backend": type("Backend", (), {"value": "local"})(),
                "input_slot_names": {"policy"},
                "output_slot_names": {"result"},
            },
        )()

    monkeypatch.setattr(registry, "get", lambda fqn: _FakeMethod())

    mutated = config.with_topology_mutation(
        TopologyMutation(
            kind=TopologyMutationKind.SWAP_METHOD,
            node_id="node_lp",
            replacement_method_fqn="optimization.linear.resource_lp@1.0.0",
        ),
        registry=registry,
    )

    mutated.method_dag[0].params["nested"]["thresholds"][0] = 99
    mutated.method_dag[0].depends_on.append("later")

    assert config.method_dag[0].method_fqn == "optimization.resource_lp@1.0.0"
    assert config.method_dag[0].params["nested"]["thresholds"] == [1, 2]
    assert config.method_dag[0].depends_on == ["upstream"]
    assert mutated.method_dag[0].backend == "local"


def test_with_topology_mutation_does_not_swallow_registry_assertion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = ExecutionPlanSearchConfig(
        method_dag=[MethodDagNode(node_id="node_lp", method_fqn="optimization.resource_lp@1.0.0")]
    )
    registry = MethodRegistry()

    def _boom(_fqn: str):
        raise AssertionError("registry invariant failed")

    monkeypatch.setattr(registry, "get", _boom)

    with pytest.raises(AssertionError, match="registry invariant failed"):
        config.with_topology_mutation(
            TopologyMutation(
                kind=TopologyMutationKind.SWAP_METHOD,
                node_id="node_lp",
                replacement_method_fqn="optimization.linear.resource_lp@1.0.0",
            ),
            registry=registry,
        )


def test_coerce_candidate_config_does_not_swallow_assertion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(_payload):
        raise AssertionError("candidate validation invariant failed")

    monkeypatch.setattr(ExecutionPlanSearchConfig, "model_validate", _boom)

    with pytest.raises(AssertionError, match="candidate validation invariant failed"):
        _coerce_candidate_config({"mode": "params_only"})


def test_backend_for_method_does_not_swallow_assertion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = MethodRegistry()

    def _boom(_fqn: str):
        raise AssertionError("backend invariant failed")

    monkeypatch.setattr(registry, "get", _boom)

    with pytest.raises(AssertionError, match="backend invariant failed"):
        _backend_for_method(registry, "optimization.linear.resource_lp@1.0.0")
