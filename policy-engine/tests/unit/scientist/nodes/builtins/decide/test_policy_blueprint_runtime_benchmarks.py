from __future__ import annotations

import logging
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    CrossGraphEvidenceSummary,
    EvidenceSourceKind,
    EvidenceSourceState,
    EvidenceSourceStatus,
)
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.evidence.sources import EvidenceSourcesConfig
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    persist_benchmark_evaluation,
)
from polisyos.scientist.methods.search.benchmark_registry import BenchmarkRegistry
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_benchmarks import (
    _maybe_register_benchmark_evaluation,
    _resolve_policy_runtime_source_statuses,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)


def _candidate() -> PolicyCandidateSchema:
    return PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id="problem_benchmark_scope",
                domain=ProblemDomain.FISCAL,
            ),
            policy_spec=PolicySpec(policy_id="policy_benchmark_scope"),
            model_spec=ModelSpec(
                model_id="model_benchmark_scope",
                data_snapshot_ref="sha256:" + "3" * 64,
            ),
        ),
        candidate_id="candidate_benchmark_scope",
    )


def _context(tmp_path: Path, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(tmp_path / run_id)
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext

    registry_ref = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    return ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(f"test.{run_id}"),
    )


def _register(
    *,
    ctx: ExecutionContext,
    registry: BenchmarkRegistry,
    ref,
    run_id: str,
    expected_loop_id: str,
) -> None:
    _maybe_register_benchmark_evaluation(
        ctx,
        benchmark_registry=registry,
        ref=ref,
        split_type=BenchmarkSplit.HIDDEN_HOLDOUT,
        run_id=run_id,
        expected_loop_id=expected_loop_id,
        family="causal_core",
        query_type="policy",
        estimator_name="matching",
        readiness_target="release",
    )


def test_source_statuses_are_per_source_and_choose_the_configured_benchmark_report(
    tmp_path: Path,
) -> None:
    benchmark_report = tmp_path / "benchmark-report.json"
    benchmark_report.write_text('{"suite":"native"}', encoding="utf-8")
    missing_suite = tmp_path / "missing-suite.json"
    missing_legal_db = tmp_path / "missing-legal.sqlite"
    supplied_legal_status = EvidenceSourceStatus(
        source=EvidenceSourceKind.LEGAL,
        configured=True,
        status=EvidenceSourceState.QUERY_FAILED,
        path=str(missing_legal_db),
        detail="profile query failed",
    )
    profile = CrossGraphEvidenceProfile(
        summary=CrossGraphEvidenceSummary(),
        source_statuses={EvidenceSourceKind.LEGAL.value: supplied_legal_status},
    )
    sources = EvidenceSourcesConfig(
        legal_db_path=str(missing_legal_db),
        benchmark_suite_path=str(missing_suite),
        benchmark_report_path=str(benchmark_report),
    )

    statuses = _resolve_policy_runtime_source_statuses(
        cross_graph_profile=profile,
        evidence_sources=sources,
    )

    assert statuses[EvidenceSourceKind.LEGAL.value] == EvidenceSourceState.QUERY_FAILED.value
    assert statuses[EvidenceSourceKind.BENCHMARK.value] == EvidenceSourceState.AVAILABLE.value
    assert statuses[EvidenceSourceKind.ACADEMIC.value] == EvidenceSourceState.MISSING_CONFIG.value
    assert supplied_legal_status.status is EvidenceSourceState.QUERY_FAILED
    assert str(benchmark_report) == sources.benchmark_report_path


def test_benchmark_admission_requires_exact_loop_and_split_and_keeps_scope_filters(
    tmp_path: Path,
) -> None:
    ctx = _context(tmp_path, "run_benchmark_admission")
    candidate_ref = persist_policy_candidate_schema(ctx.store, _candidate())
    registry = BenchmarkRegistry(tmp_path / "search_registry" / "benchmarks")
    current_run = "run_current_scope"
    expected_loop = "loop_current_scope"
    accepted = BenchmarkEvaluation(
        loop_id=expected_loop,
        suite_id="native_hidden_holdout",
        candidate_ref=candidate_ref,
        runtime_split_type=BenchmarkSplit.HIDDEN_HOLDOUT,
        holdout_metrics={"policy_value": 0.25},
        sample_counts={BenchmarkSplit.HIDDEN_HOLDOUT.value: 12},
    )
    accepted_ref = persist_benchmark_evaluation(ctx.store, accepted)

    _register(
        ctx=ctx,
        registry=registry,
        ref=accepted_ref,
        run_id=current_run,
        expected_loop_id=expected_loop,
    )

    assert (
        registry.latest(
            BenchmarkSplit.HIDDEN_HOLDOUT.value,
            run_id=current_run,
            loop_id=expected_loop,
            family="causal_core",
            query_type="policy",
            estimator_name="matching",
            readiness_target="release",
        )
        == accepted_ref
    )
    assert (
        registry.latest(
            BenchmarkSplit.HIDDEN_HOLDOUT.value,
            run_id=current_run,
            loop_id=expected_loop,
            family="other_family",
            query_type="policy",
            estimator_name="matching",
            readiness_target="release",
        )
        is None
    )

    wrong_loop = accepted.model_copy(update={"loop_id": "loop_other"})
    wrong_loop_ref = persist_benchmark_evaluation(ctx.store, wrong_loop)
    _register(
        ctx=ctx,
        registry=registry,
        ref=wrong_loop_ref,
        run_id="run_wrong_loop",
        expected_loop_id=expected_loop,
    )
    assert (
        registry.latest(
            BenchmarkSplit.HIDDEN_HOLDOUT.value,
            run_id="run_wrong_loop",
        )
        is None
    )

    wrong_split = accepted.model_copy(
        update={
            "suite_id": "native_selection",
            "runtime_split_type": BenchmarkSplit.SELECTION,
        }
    )
    wrong_split_ref = persist_benchmark_evaluation(ctx.store, wrong_split)
    _register(
        ctx=ctx,
        registry=registry,
        ref=wrong_split_ref,
        run_id="run_wrong_split",
        expected_loop_id=expected_loop,
    )
    assert (
        registry.latest(
            BenchmarkSplit.HIDDEN_HOLDOUT.value,
            run_id="run_wrong_split",
        )
        is None
    )
