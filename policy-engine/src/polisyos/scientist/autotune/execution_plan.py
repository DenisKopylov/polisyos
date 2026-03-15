from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.canon import CanonSpec, fingerprint
from polisyos.core.contracts.execution_plan import (
    ExecutionPlan,
    MethodDagEdge,
    MethodDagNode,
    PreflightReport,
)
from polisyos.scientist.governance.report import GovernanceReport

from .models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    BenchmarkedEvaluator,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    SearchLoopSpec,
    load_model_artifact,
    read_split_manifest,
)
from .registry import ChampionRegistry
from .runtime import PydanticMutationCodec

EXECUTION_PLAN_LOOP_ID = "execution_plan"


class ExecutionPlanSearchMode(str, Enum):
    PARAMS_ONLY = "params_only"
    TOPOLOGY_STEP = "topology_step"


class TopologyMutationKind(str, Enum):
    SWAP_METHOD = "swap_method"
    INSERT_ADAPTER = "insert_adapter"
    DROP_OPTIONAL_NODE = "drop_optional_node"


class TopologyMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: TopologyMutationKind
    node_id: str = Field(..., min_length=1)
    replacement_method_fqn: str | None = None
    adapter_method_fqn: str | None = None


class ExecutionPlanSearchConfig(MutationArtifact):
    model_config = ConfigDict(extra="forbid")

    loop_id: str = EXECUTION_PLAN_LOOP_ID
    mode: ExecutionPlanSearchMode = ExecutionPlanSearchMode.PARAMS_ONLY
    method_dag: list[MethodDagNode] = Field(default_factory=list)
    method_edges: list[MethodDagEdge] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    fixed_method_dag_hash: str | None = None
    topology_mutation: TopologyMutation | None = None

    @model_validator(mode="after")
    def _validate_mode_constraints(self) -> "ExecutionPlanSearchConfig":
        dag_hash = self.method_dag_hash
        if self.mode == ExecutionPlanSearchMode.PARAMS_ONLY:
            if self.topology_mutation is not None:
                raise ValueError("params_only mode cannot carry topology_mutation")
            if self.fixed_method_dag_hash is not None and self.fixed_method_dag_hash != dag_hash:
                raise ValueError("params_only mode must preserve fixed_method_dag_hash")
        elif self.topology_mutation is None:
            raise ValueError("topology_step mode requires exactly one topology_mutation")
        return self

    @property
    def method_dag_hash(self) -> str:
        return fingerprint(
            {
                "method_dag": [node.model_dump(mode="json") for node in self.method_dag],
                "method_edges": [edge.model_dump(mode="json") for edge in self.method_edges],
            },
            canon_spec=CanonSpec(forbid_floats=False),
        )

    def apply_to_execution_plan(self, base_plan: ExecutionPlan) -> ExecutionPlan:
        return base_plan.model_copy(
            update={
                "method_dag": list(self.method_dag),
                "method_edges": list(self.method_edges),
                "params": dict(self.params),
            }
        )


def build_baseline_execution_plan_config(context: dict[str, Any] | None = None) -> ExecutionPlanSearchConfig:
    baseline_plan = None if context is None else context.get("baseline_execution_plan")
    if isinstance(baseline_plan, ExecutionPlan):
        return ExecutionPlanSearchConfig(
            method_dag=list(baseline_plan.method_dag),
            method_edges=list(baseline_plan.method_edges),
            params=dict(baseline_plan.params),
            fixed_method_dag_hash=fingerprint(
                {
                    "method_dag": [node.model_dump(mode="json") for node in baseline_plan.method_dag],
                    "method_edges": [edge.model_dump(mode="json") for edge in baseline_plan.method_edges],
                },
                canon_spec=CanonSpec(forbid_floats=False),
            ),
        )
    return ExecutionPlanSearchConfig()


def default_execution_plan_policy() -> PromotionPolicy:
    return PromotionPolicy(
        loop_id=EXECUTION_PLAN_LOOP_ID,
        primary_metric="composite_score",
        direction=MetricDirection.MAXIMIZE,
        compare_split=BenchmarkSplit.HOLDOUT,
        min_improvement=0.0,
        min_sample_count=1,
        required_guardrails=[
            "no_new_blockers",
            "governance_not_degraded",
            "compatibility_ok",
        ],
    )


class ExecutionPlanBenchmarkEvaluator(BenchmarkedEvaluator):
    def __init__(
        self,
        *,
        store: Any | None = None,
        registry: ChampionRegistry | None = None,
    ) -> None:
        self._store = store
        self._registry = registry

    def evaluate(self, candidate_ref, suite_ref, context: dict[str, Any]) -> BenchmarkEvaluation:
        store = context.get("store") or self._store
        if store is None:
            raise ValueError("ExecutionPlanBenchmarkEvaluator requires a CAS store")
        suite = load_model_artifact(store, suite_ref, BenchmarkSuite)
        config = load_model_artifact(store, candidate_ref, ExecutionPlanSearchConfig)
        if suite.dataset_path is None or suite.split_manifest_path is None:
            raise ValueError("Execution plan benchmark suite requires dataset_path and split_manifest_path")
        runner = context.get("execution_plan_runner")
        if not callable(runner):
            raise ValueError("context['execution_plan_runner'] must be callable")
        rows = _read_jsonl(Path(suite.dataset_path))
        split_manifest = read_split_manifest(Path(suite.split_manifest_path))
        champion_governance = self._champion_governance_score(
            candidate_ref=candidate_ref,
            suite=suite,
            rows=rows,
            runner=runner,
            split_manifest=split_manifest,
            context=context,
        )
        selection_cases = _run_execution_plan_cases(
            config=config,
            rows=[row for row in rows if split_manifest.split_for(str(row["case_id"])) == BenchmarkSplit.SELECTION],
            runner=runner,
            context=context,
        )
        holdout_cases = _run_execution_plan_cases(
            config=config,
            rows=[row for row in rows if split_manifest.split_for(str(row["case_id"])) == BenchmarkSplit.HOLDOUT],
            runner=runner,
            context=context,
        )
        selection_metrics = _execution_plan_metrics(selection_cases)
        holdout_metrics = _execution_plan_metrics(holdout_cases)
        guardrails = {
            "no_new_blockers": float(holdout_metrics.get("blocker_free_rate", 0.0)) >= 1.0,
            "governance_not_degraded": float(holdout_metrics.get("governance_score", 0.0)) >= champion_governance,
            "compatibility_ok": float(holdout_metrics.get("compatibility_rate", 0.0)) >= 1.0,
        }
        return BenchmarkEvaluation(
            loop_id=EXECUTION_PLAN_LOOP_ID,
            suite_id=suite.suite_id,
            suite_version=suite.suite_version,
            candidate_ref=candidate_ref,
            selection_metrics=selection_metrics,
            holdout_metrics=holdout_metrics,
            sample_counts={
                BenchmarkSplit.SELECTION.value: int(selection_metrics.get("sample_count", 0.0)),
                BenchmarkSplit.HOLDOUT.value: int(holdout_metrics.get("sample_count", 0.0)),
            },
            guardrails=guardrails,
            promotable=all(guardrails.values()),
        )

    def _champion_governance_score(
        self,
        *,
        candidate_ref,
        suite: BenchmarkSuite,
        rows: list[dict[str, Any]],
        runner: Any,
        split_manifest,
        context: dict[str, Any],
    ) -> float:
        registry = context.get("registry") or self._registry
        store = context.get("store") or self._store
        if registry is None or store is None:
            return 0.0
        champion = registry.get(EXECUTION_PLAN_LOOP_ID)
        if champion is None or champion.candidate_ref.artifact_id == candidate_ref.artifact_id:
            return 0.0
        cfg = load_model_artifact(store, champion.candidate_ref, ExecutionPlanSearchConfig)
        metrics = _execution_plan_metrics(
            _run_execution_plan_cases(
                config=cfg,
                rows=[row for row in rows if split_manifest.split_for(str(row["case_id"])) == BenchmarkSplit.HOLDOUT],
                runner=runner,
                context=context,
            )
        )
        return float(metrics.get("governance_score", 0.0))


def execution_plan_search_loop_spec(
    *,
    candidate_generator: Any | None = None,
    store: Any | None = None,
    registry: ChampionRegistry | None = None,
) -> SearchLoopSpec:
    return SearchLoopSpec(
        loop_id=EXECUTION_PLAN_LOOP_ID,
        mutation_codec=PydanticMutationCodec(ExecutionPlanSearchConfig),
        candidate_generator=candidate_generator,
        benchmark_evaluator=ExecutionPlanBenchmarkEvaluator(store=store, registry=registry),
        promotion_policy=default_execution_plan_policy(),
        runtime_loader=None,
    )


def _run_execution_plan_cases(
    *,
    config: ExecutionPlanSearchConfig,
    rows: list[dict[str, Any]],
    runner: Any,
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for row in rows:
        result = runner(row, config, context)
        if not isinstance(result, dict):
            raise TypeError("execution_plan_runner must return dict-like case results")
        cases.append(result)
    return cases


def _execution_plan_metrics(cases: list[dict[str, Any]]) -> dict[str, float]:
    if not cases:
        return {
            "sample_count": 0.0,
            "composite_score": 0.0,
            "preflight_pass_rate": 0.0,
            "governance_score": 0.0,
            "backtest_score": 0.0,
            "cross_graph_coverage": 0.0,
            "run_cost_score": 0.0,
            "blocker_free_rate": 0.0,
            "compatibility_rate": 0.0,
        }
    preflight_ready = []
    blocker_free = []
    governance_scores = []
    backtest_scores = []
    cross_graph_scores = []
    cost_scores = []
    compatibility_scores = []
    for case in cases:
        preflight = _coerce_preflight(case.get("preflight_report"))
        governance = _coerce_governance(case.get("governance_report"))
        backtest = _backtest_score(case.get("backtest_summary") or {})
        cross_graph = _cross_graph_score(case.get("cross_graph_summary") or {})
        cost = _run_cost_score(case.get("run_stats") or {})
        compatibility_ok = 1.0 if bool(case.get("compatibility_ok", True)) else 0.0
        preflight_ready.append(1.0 if preflight.ready_to_run else 0.0)
        blocker_free.append(1.0 if not _has_blocking_diagnostics(preflight) else 0.0)
        governance_scores.append(_governance_score(governance))
        backtest_scores.append(backtest)
        cross_graph_scores.append(cross_graph)
        cost_scores.append(cost)
        compatibility_scores.append(compatibility_ok)
    composite = (
        _avg(preflight_ready) * 0.20
        + _avg(governance_scores) * 0.20
        + _avg(backtest_scores) * 0.25
        + _avg(cross_graph_scores) * 0.20
        + _avg(cost_scores) * 0.15
    )
    return {
        "sample_count": float(len(cases)),
        "composite_score": composite,
        "preflight_pass_rate": _avg(preflight_ready),
        "governance_score": _avg(governance_scores),
        "backtest_score": _avg(backtest_scores),
        "cross_graph_coverage": _avg(cross_graph_scores),
        "run_cost_score": _avg(cost_scores),
        "blocker_free_rate": _avg(blocker_free),
        "compatibility_rate": _avg(compatibility_scores),
    }


def _coerce_preflight(raw: Any) -> PreflightReport:
    if isinstance(raw, PreflightReport):
        return raw
    if isinstance(raw, dict):
        return PreflightReport.model_validate(raw)
    return PreflightReport(ready_to_run=False, diagnostics=[], notes=["missing_preflight_report"])


def _coerce_governance(raw: Any) -> GovernanceReport:
    if isinstance(raw, GovernanceReport):
        return raw
    if isinstance(raw, dict):
        return GovernanceReport.model_validate(raw)
    return GovernanceReport(verdict="reject", issues=[{"message": "missing_governance_report"}])


def _has_blocking_diagnostics(report: PreflightReport) -> bool:
    return any(diag.severity in {"error", "blocker"} for diag in report.diagnostics)


def _governance_score(report: GovernanceReport) -> float:
    return {
        "approve": 1.0,
        "needs_revision": 0.5,
        "human_gate": 0.0,
        "reject": 0.0,
    }.get(report.verdict, 0.0)


def _backtest_score(summary: dict[str, Any]) -> float:
    if "score" in summary:
        return max(0.0, min(1.0, float(summary["score"])))
    rmse = float(summary.get("rmse", 1.0) or 1.0)
    coverage = float(summary.get("coverage_probability", summary.get("coverage", 0.0)) or 0.0)
    return max(0.0, min(1.0, (1.0 / (1.0 + rmse)) * 0.6 + coverage * 0.4))


def _cross_graph_score(summary: dict[str, Any]) -> float:
    if "score" in summary:
        return max(0.0, min(1.0, float(summary["score"])))
    candidates = [
        summary.get("causal_supported_ratio"),
        summary.get("parameter_supported_ratio"),
        summary.get("scholar_query_coverage_ratio"),
        summary.get("coverage"),
    ]
    values = [float(value) for value in candidates if value is not None]
    return _avg(values)


def _run_cost_score(stats: dict[str, Any]) -> float:
    if "score" in stats:
        return max(0.0, min(1.0, float(stats["score"])))
    usd = float(stats.get("cost_usd", 0.0) or 0.0)
    runtime_seconds = float(stats.get("runtime_seconds", 0.0) or 0.0)
    return max(0.0, min(1.0, 1.0 / (1.0 + usd + (runtime_seconds / 60.0))))


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


__all__ = [
    "EXECUTION_PLAN_LOOP_ID",
    "ExecutionPlanBenchmarkEvaluator",
    "ExecutionPlanSearchConfig",
    "ExecutionPlanSearchMode",
    "TopologyMutation",
    "TopologyMutationKind",
    "build_baseline_execution_plan_config",
    "default_execution_plan_policy",
    "execution_plan_search_loop_spec",
]
