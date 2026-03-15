from __future__ import annotations

import graphlib
from datetime import datetime, timezone
from typing import Any

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, fingerprint
from polisyos.core.contracts.control import DataNeed
from polisyos.core.contracts.execution_plan import (
    BudgetSpec,
    EvaluatorReport,
    EvaluatorReportRef,
    EvaluatorScores,
    EvaluatorVerdict,
    ExecutionPlan,
    ExecutionPlanRef,
    IterationState,
    IterationStateRef,
    MethodCatalogSnapshot,
    MethodCatalogSnapshotRef,
    MethodDagNode,
    PlanDataNeed,
    PreflightDiagnostic,
    PreflightReport,
    PreflightReportRef,
    ReproducibilityManifest,
    ReproducibilityManifestRef,
    StopCriteria,
)
from polisyos.foundry.methods import MethodRegistry, check_linkable


def build_default_execution_plan(
    *,
    run_id: str,
    data_needs: list[DataNeed],
    method_dag: list[MethodDagNode] | None = None,
    params: dict[str, Any] | None = None,
    max_iterations: int = 3,
    run_budget_usd: float | None = None,
    per_model_budget_usd: float | None = None,
    governance_constraints: list[dict[str, Any]] | None = None,
    expected_outputs: list[dict[str, Any]] | None = None,
) -> ExecutionPlan:
    payload_needs = [
        PlanDataNeed(
            metric=item.metric,
            geography=item.geography,
            time_start=item.time_start,
            time_end=item.time_end,
            granularity=item.granularity,
            quality_min=item.quality_min,
            purpose=item.purpose,
        )
        for item in data_needs
    ]
    return ExecutionPlan(
        plan_id=f"plan_{run_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        run_id=run_id,
        iteration=1,
        data_needs=payload_needs,
        method_dag=list(method_dag or []),
        params=dict(params or {}),
        budgets=BudgetSpec(
            max_iterations=max(1, int(max_iterations)),
            run_budget_usd=run_budget_usd,
            per_model_budget_usd=per_model_budget_usd,
        ),
        stop_criteria=StopCriteria(),
        governance_constraints=list(governance_constraints or []),
        expected_outputs=list(expected_outputs or []),
    )


def preflight_execution_plan(
    plan: ExecutionPlan,
    catalog: MethodCatalogSnapshot,
) -> PreflightReport:
    diagnostics: list[PreflightDiagnostic] = []
    registry = MethodRegistry.get_instance()

    available = {entry.fqn for entry in catalog.entries}
    catalog_entries = {entry.fqn: entry for entry in catalog.entries}
    node_by_id = {node.node_id: node for node in plan.method_dag}
    graph: dict[str, set[str]] = {}

    for node in plan.method_dag:
        deps = set(node.depends_on)
        for dep in deps:
            if dep not in node_by_id:
                diagnostics.append(
                    PreflightDiagnostic(
                        code="method_dag.missing_dependency",
                        severity="error",
                        message=f"Node '{node.node_id}' depends on unknown node '{dep}'",
                        path=["method_dag", node.node_id, "depends_on"],
                        replanning_hints=["Remove unknown dependency or add missing node"],
                    )
                )
        graph[node.node_id] = deps
        if node.method_fqn not in available:
            diagnostics.append(
                PreflightDiagnostic(
                    code="method_catalog.method_missing",
                    severity="error",
                    message=f"Method '{node.method_fqn}' not found in method catalog snapshot",
                    path=["method_dag", node.node_id, "method_fqn"],
                    replanning_hints=["Pick a method from live catalog snapshot"],
                )
            )
            continue
        entry = catalog_entries.get(node.method_fqn)
        if entry is not None and entry.causal_available is False:
            diagnostics.append(
                PreflightDiagnostic(
                    code="method_catalog.causal_capability_unavailable",
                    severity="error",
                    message=(
                        f"Method '{node.method_fqn}' requires unavailable causal runtime "
                        f"capabilities: {entry.causal_capability_requirements}"
                    ),
                    path=["method_dag", node.node_id, "method_fqn"],
                    replanning_hints=[
                        "Install the required causal profile or choose a method without symbolic transport requirements",
                    ],
                    data={
                        "causal_requirements": list(entry.causal_capability_requirements),
                        "disabled_reasons": list(entry.causal_disabled_reasons),
                        "causal_capability_hash": catalog.causal_capability_hash,
                    },
                )
            )

    try:
        _ = list(graphlib.TopologicalSorter(graph).static_order())
    except Exception as exc:
        diagnostics.append(
            PreflightDiagnostic(
                code="method_dag.cycle_detected",
                severity="blocker",
                message=f"Method DAG is cyclic: {exc}",
                path=["method_dag"],
                replanning_hints=["Break cycles; keep DAG acyclic"],
            )
        )

    for node in plan.method_dag:
        for dep_id in node.depends_on:
            source = node_by_id.get(dep_id)
            if source is None:
                continue
            try:
                source_sig = registry.get(source.method_fqn).signature
                target_sig = registry.get(node.method_fqn).signature
            except Exception as exc:
                diagnostics.append(
                    PreflightDiagnostic(
                        code="method_registry.lookup_failed",
                        severity="error",
                        message=f"Registry lookup failed: {exc}",
                        path=["method_dag", node.node_id],
                        replanning_hints=["Refresh method versions", "Use method fqn@version"],
                    )
                )
                continue
            if not check_linkable(source_sig, target_sig):
                diagnostics.append(
                    PreflightDiagnostic(
                        code="slot_linker.not_linkable",
                        severity="error",
                        message=(
                            f"Output slots from '{source.method_fqn}' are not linkable "
                            f"to '{node.method_fqn}' input slots"
                        ),
                        path=["method_dag", node.node_id, "depends_on"],
                        replanning_hints=[
                            "Insert adapter method",
                            "Choose compatible upstream method",
                        ],
                    )
                )

    ready = not any(item.severity in {"error", "blocker"} for item in diagnostics)
    notes = [f"diagnostics:{len(diagnostics)}", f"ready:{str(ready).lower()}"]
    return PreflightReport(
        ready_to_run=ready,
        diagnostics=diagnostics,
        notes=notes,
    )


def evaluate_iteration(
    *,
    issue_count: int,
    verdict: str,
    retrieval_quality: float = 1.0,
    budget_remaining_ratio: float | None = None,
) -> EvaluatorReport:
    normalized_verdict = str(verdict or "").strip().upper()
    if normalized_verdict == "APPROVE":
        eval_verdict: EvaluatorVerdict = "APPROVE"
    elif budget_remaining_ratio is not None and budget_remaining_ratio <= 0.0:
        eval_verdict = "STOP_BUDGET"
    elif retrieval_quality < 0.35:
        eval_verdict = "REPLAN_DATA"
    elif issue_count > 2:
        eval_verdict = "REPLAN_PARAMS"
    else:
        eval_verdict = "REPLAN_METHOD"
    budget_score = max(0.0, min(1.0, float(budget_remaining_ratio))) if budget_remaining_ratio is not None else 1.0
    base = max(0.0, min(1.0, retrieval_quality))
    penalty = max(0.0, min(1.0, float(issue_count) / 10.0))
    total = max(0.0, min(1.0, (base * 0.4) + (1.0 - penalty) * 0.4 + budget_score * 0.2))
    scores = EvaluatorScores(
        kpi_score=max(0.0, 1.0 - penalty),
        uncertainty_score=base,
        constraints_score=max(0.0, 1.0 - penalty),
        data_quality_score=base,
        budget_score=budget_score,
        total_score=total,
    )
    reasons = [f"critic_verdict:{normalized_verdict or 'UNKNOWN'}", f"issue_count:{issue_count}"]
    replanning_hints: list[str] = []
    if eval_verdict.startswith("REPLAN"):
        replanning_hints.append("Adjust plan and rerun preflight")
    if eval_verdict == "REPLAN_DATA":
        replanning_hints.append("Refresh data needs and sources before next iteration")
    if eval_verdict == "REPLAN_METHOD":
        replanning_hints.append("Select compatible methods from live catalog")
    if eval_verdict == "REPLAN_PARAMS":
        replanning_hints.append("Tune method params and constraints")
    if eval_verdict == "STOP_BUDGET":
        replanning_hints.append("Budget exhausted, stop execution")
    return EvaluatorReport(
        verdict=eval_verdict,
        scores=scores,
        reasons=reasons,
        replanning_hints=replanning_hints,
    )


def persist_execution_plan(
    store: FileSystemCAS,
    plan: ExecutionPlan,
    *,
    inputs: list[InputRef] | None = None,
) -> ExecutionPlanRef:
    payload_ref = store.put_json(
        plan,
        PutOptions(
            kind="scientist.execution_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ExecutionPlan", version="1.0"),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ExecutionPlanRef(artifact_id=payload_ref.artifact_id)


def persist_preflight_report(
    store: FileSystemCAS,
    report: PreflightReport,
    *,
    inputs: list[InputRef] | None = None,
) -> PreflightReportRef:
    payload_ref = store.put_json(
        report,
        PutOptions(
            kind="scientist.preflight_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.PreflightReport", version="1.0"),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return PreflightReportRef(artifact_id=payload_ref.artifact_id)


def persist_evaluator_report(
    store: FileSystemCAS,
    report: EvaluatorReport,
    *,
    inputs: list[InputRef] | None = None,
) -> EvaluatorReportRef:
    payload_ref = store.put_json(
        report,
        PutOptions(
            kind="scientist.evaluator_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.EvaluatorReport", version="1.0"),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return EvaluatorReportRef(artifact_id=payload_ref.artifact_id)


def persist_iteration_state(
    store: FileSystemCAS,
    state: IterationState,
    *,
    inputs: list[InputRef] | None = None,
) -> IterationStateRef:
    payload_ref = store.put_json(
        state,
        PutOptions(
            kind="scientist.iteration_state",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.IterationState", version="1.0"),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return IterationStateRef(artifact_id=payload_ref.artifact_id)


def build_reproducibility_manifest(
    *,
    run_id: str,
    iteration: int,
    seed: int,
    plan: ExecutionPlan,
    registry_bundle_ref: str | None,
    method_catalog_snapshot_ref: str | None,
    data_snapshot_ref: str | None,
    input_bindings_ref: str | None,
) -> ReproducibilityManifest:
    return ReproducibilityManifest(
        run_id=run_id,
        iteration=iteration,
        seed=seed,
        plan_hash=plan.stable_hash(),
        registry_bundle_ref=registry_bundle_ref,
        registry_hash=fingerprint(registry_bundle_ref or ""),
        method_catalog_snapshot_ref=method_catalog_snapshot_ref,
        method_catalog_hash=fingerprint(method_catalog_snapshot_ref or ""),
        data_snapshot_ref=data_snapshot_ref,
        data_snapshot_hash=fingerprint(data_snapshot_ref or ""),
        input_bindings_ref=input_bindings_ref,
        input_bindings_hash=fingerprint(input_bindings_ref or ""),
    )


def persist_reproducibility_manifest(
    store: FileSystemCAS,
    manifest: ReproducibilityManifest,
    *,
    inputs: list[InputRef] | None = None,
) -> ReproducibilityManifestRef:
    payload_ref = store.put_json(
        manifest,
        PutOptions(
            kind="scientist.reproducibility_manifest",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ReproducibilityManifest", version="1.0"),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ReproducibilityManifestRef(artifact_id=payload_ref.artifact_id)


__all__ = [
    "build_default_execution_plan",
    "preflight_execution_plan",
    "evaluate_iteration",
    "persist_execution_plan",
    "persist_preflight_report",
    "persist_evaluator_report",
    "persist_iteration_state",
    "build_reproducibility_manifest",
    "persist_reproducibility_manifest",
]
