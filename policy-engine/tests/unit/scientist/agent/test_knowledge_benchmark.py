from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.data_forge.domains.legal.batch.config import BatchConfig
from polisyos.data_forge.domains.legal.batch.pipeline import run_batch_pipeline
from polisyos.scientist import ScientistLegalBenchmarkRunner


class _PerfectRetrievalToolkit:
    def search_legal_facts(
        self,
        query: str,
        *,
        top_k: int,
        trust_tier: str,
        domain: str | None,
        include_candidates: bool,
    ) -> list[SimpleNamespace]:
        del query, top_k, trust_tier, include_candidates
        return [
            SimpleNamespace(
                action_canon="requires",
                norm_type_canon="obligation",
                top_domain=domain or "",
            ),
            SimpleNamespace(
                action_canon="enters_into_force",
                norm_type_canon="entry_into_force",
                top_domain=domain or "",
            ),
            SimpleNamespace(
                action_canon="sets_threshold",
                norm_type_canon="procedure",
                top_domain=domain or "",
            ),
        ]


def _failed_lex_runner(config: SimpleNamespace) -> SimpleNamespace:
    report_path = Path(config.benchmark_report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    metrics = {
        "benchmark_search_top5_relevance_pct": 100.0,
        "benchmark_normpack_ready_pct": 0.0,
        "benchmark_constraints_ready_pct": 100.0,
    }
    failed_checks = ["benchmark_normpack_ready_pct"]
    report_path.write_text(
        json.dumps(
            {
                "kind": "lex_benchmark",
                "metrics": metrics,
                "readiness": {
                    "passed": False,
                    "failed_checks": failed_checks,
                },
            }
        ),
        encoding="utf-8",
    )
    return SimpleNamespace(
        report_path=report_path,
        metrics=metrics,
        passed=False,
        failed_checks=failed_checks,
    )


def test_perfect_retrieval_cannot_promote_failed_lex_semantics(tmp_path) -> None:
    config = SimpleNamespace(
        output_dir=tmp_path,
        benchmark_report_path=tmp_path / "lex_benchmark.json",
    )
    runner = ScientistLegalBenchmarkRunner(
        toolkit=_PerfectRetrievalToolkit(),
        lex_runner=_failed_lex_runner,
    )

    outcome = runner(config)

    assert outcome.metrics["scientist_retrieval_top5_relevance_pct"] == 100.0
    assert outcome.passed is False
    assert outcome.failed_checks == ["benchmark_normpack_ready_pct"]
    assert outcome.lex_semantic_passed is False
    assert outcome.authoritative_for == ()
    assert set(outcome.may_not_use_for) >= {
        "legal_admissibility",
        "legal_publication_readiness",
        "governance_admissibility",
        "method_validity",
    }

    with pytest.raises(ValueError, match="method_validity"):
        outcome.require_authority("method_validity")
    with pytest.raises(ValueError, match="governance_admissibility"):
        outcome.require_authority("governance_admissibility")

    payload = json.loads(outcome.report_path.read_text(encoding="utf-8"))
    assert payload["lex_semantic_receipt"]["passed"] is False
    assert payload["retrieval_diagnostic"]["passed"] is True
    assert payload["combined_readiness"]["passed"] is False


def test_scientist_runner_rejects_lex_result_that_disagrees_with_receipt(tmp_path) -> None:
    config = SimpleNamespace(
        output_dir=tmp_path,
        benchmark_report_path=tmp_path / "lex_benchmark.json",
    )

    def _lying_runner(config: SimpleNamespace) -> SimpleNamespace:
        result = _failed_lex_runner(config)
        return SimpleNamespace(
            report_path=result.report_path,
            metrics=result.metrics,
            passed=True,
            failed_checks=[],
        )

    runner = ScientistLegalBenchmarkRunner(
        toolkit=_PerfectRetrievalToolkit(),
        lex_runner=_lying_runner,
    )

    with pytest.raises(ValueError, match="disagrees with persisted receipt"):
        runner(config)


def test_data_forge_pipeline_consumes_scientist_owned_retrieval_bridge(tmp_path) -> None:
    config = BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=tmp_path,
        stages=frozenset({"benchmark"}),
    )
    runner = ScientistLegalBenchmarkRunner(
        toolkit=_PerfectRetrievalToolkit(),
        lex_runner=_failed_lex_runner,
    )

    stats = asyncio.run(run_batch_pipeline(config, benchmark_runner=runner))

    assert stats.benchmark_passed is False
    assert stats.benchmark_failed_checks == ["benchmark_normpack_ready_pct"]
    assert stats.benchmark_metrics["scientist_retrieval_top5_relevance_pct"] == 100.0
