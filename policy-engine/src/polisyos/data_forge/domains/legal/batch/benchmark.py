"""Authority-neutral legal benchmark fixtures and legacy retrieval diagnostic.

Lex owns semantic readiness. The Scientist retrieval consumer remains here only
until Round 7 moves it above Data Forge; its output is diagnostic and cannot
establish legal admissibility or publication readiness.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polisyos.data_forge.domains.legal.batch.benchmark_fixtures import (
    LegalSearchBenchmarkCase,
    legal_search_benchmark_cases,
)
from polisyos.data_forge.kernel.io import atomic_write_json
from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit


@dataclass(frozen=True, slots=True)
class RetrievalBenchmarkOutcome:
    """Scientist retrieval diagnostic with explicitly bounded authority."""

    report_path: Path
    metrics: dict[str, float | int]
    authoritative_for: tuple[str, ...] = ()
    may_not_use_for: tuple[str, ...] = (
        "legal_admissibility",
        "legal_publication_readiness",
    )


def _matches(result: Any, case: LegalSearchBenchmarkCase) -> bool:
    action = str(
        getattr(result, "action_canon", "") or getattr(result, "predicate", "") or ""
    ).lower()
    norm_type = str(
        getattr(result, "norm_type_canon", "") or getattr(result, "norm_type", "") or ""
    ).lower()
    domain = str(getattr(result, "top_domain", "") or "").lower()
    return bool(
        (not case.expected_actions or action in set(case.expected_actions))
        and (not case.expected_norm_types or norm_type in set(case.expected_norm_types))
        and (case.domain is None or domain == case.domain.lower())
    )


def run_retrieval_benchmark(
    *,
    toolkit: KnowledgeToolkit,
    output_dir: Path,
) -> RetrievalBenchmarkOutcome:
    """Run the bounded Scientist retrieval diagnostic pending Round 7."""
    rows: list[dict[str, object]] = []
    hits = 0
    cases = legal_search_benchmark_cases()
    for case in cases:
        results = toolkit.search_legal_facts(
            case.query,
            top_k=5,
            trust_tier="grounded_fact",
            domain=case.domain,
            include_candidates=False,
        )
        matched = any(_matches(result, case) for result in results)
        hits += int(matched)
        rows.append(
            {
                "case_id": case.case_id,
                "results_total": len(results),
                "matched": matched,
            }
        )

    total = len(cases)
    metrics: dict[str, float | int] = {
        "retrieval_cases_total": total,
        "retrieval_top5_relevance_pct": round((hits * 100.0) / total, 3),
    }
    report_path = output_dir / "scientist_retrieval_benchmark.json"
    atomic_write_json(
        report_path,
        {
            "kind": "scientist_retrieval_diagnostic",
            "metrics": metrics,
            "cases": rows,
            "authoritative_for": [],
            "may_not_use_for": [
                "legal_admissibility",
                "legal_publication_readiness",
            ],
        },
    )
    return RetrievalBenchmarkOutcome(report_path=report_path, metrics=metrics)


__all__ = [
    "LegalSearchBenchmarkCase",
    "RetrievalBenchmarkOutcome",
    "legal_search_benchmark_cases",
    "run_retrieval_benchmark",
]
