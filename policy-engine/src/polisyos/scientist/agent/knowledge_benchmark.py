"""Scientist-owned diagnostic evaluation of legal-knowledge retrieval."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from polisyos.data_forge.read_api import legal as legal_read_api
from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit

_RETRIEVAL_DIAGNOSTIC_THRESHOLD_PCT = 70.0
_MAY_NOT_USE_FOR = (
    "legal_admissibility",
    "legal_publication_readiness",
    "governance_admissibility",
    "method_validity",
)


class LegalBenchmarkConfig(Protocol):
    """Paths shared by the Lex semantic and Scientist diagnostic runners."""

    @property
    def output_dir(self) -> Path: ...


class LexSemanticOutcome(Protocol):
    """Persisted Lex semantic result consumed by the Scientist bridge."""

    report_path: Path
    metrics: dict[str, float | int]
    passed: bool
    failed_checks: list[str]


class LegalSearchToolkit(Protocol):
    """Narrow legal-search behavior required by the diagnostic."""

    def search_legal_facts(
        self,
        query: str,
        *,
        top_k: int,
        trust_tier: str,
        domain: str | None,
        include_candidates: bool,
    ) -> list[Any]: ...


@dataclass(frozen=True, slots=True)
class ScientistRetrievalBenchmarkOutcome:
    """Diagnostic projection whose pass state is inherited only from Lex."""

    report_path: Path
    metrics: dict[str, float | int]
    passed: bool
    failed_checks: list[str]
    lex_semantic_passed: bool
    authoritative_for: tuple[str, ...] = ()
    may_not_use_for: tuple[str, ...] = _MAY_NOT_USE_FOR

    def require_authority(self, purpose: str) -> None:
        """Reject use of a diagnostic result as authority evidence.

        Args:
            purpose: Authority slot a consumer proposes to fill.

        Raises:
            ValueError: Always, because this diagnostic publishes no authority.
        """
        raise ValueError(
            f"Scientist retrieval diagnostic is not authoritative for {purpose!r}"
        )


def _matches(result: Any, case: Any) -> bool:
    action = str(
        getattr(result, "action_canon", "") or getattr(result, "predicate", "") or ""
    ).lower()
    norm_type = str(
        getattr(result, "norm_type_canon", "")
        or getattr(result, "norm_type", "")
        or ""
    ).lower()
    domain = str(getattr(result, "top_domain", "") or "").lower()
    return bool(
        (not case.expected_actions or action in set(case.expected_actions))
        and (
            not case.expected_norm_types
            or norm_type in set(case.expected_norm_types)
        )
        and (case.domain is None or domain == case.domain.lower())
    )


def _read_lex_receipt(
    outcome: LexSemanticOutcome,
) -> tuple[dict[str, Any], str]:
    report_bytes = Path(outcome.report_path).read_bytes()
    payload = json.loads(report_bytes)
    if not isinstance(payload, dict):
        raise ValueError("Lex semantic receipt must be a JSON object")
    readiness = payload.get("readiness")
    if not isinstance(readiness, dict):
        raise ValueError("Lex semantic receipt is missing readiness")
    persisted_metrics = payload.get("metrics")
    persisted_failed = readiness.get("failed_checks")
    if (
        bool(readiness.get("passed")) != outcome.passed
        or persisted_metrics != outcome.metrics
        or persisted_failed != outcome.failed_checks
    ):
        raise ValueError("Lex semantic outcome disagrees with persisted receipt")
    return payload, hashlib.sha256(report_bytes).hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def run_retrieval_benchmark(
    *,
    toolkit: LegalSearchToolkit,
    output_dir: Path,
    lex_outcome: LexSemanticOutcome,
) -> ScientistRetrievalBenchmarkOutcome:
    """Persist a bounded retrieval diagnostic tied to a Lex semantic receipt."""
    _, lex_report_sha256 = _read_lex_receipt(lex_outcome)
    rows: list[dict[str, object]] = []
    hits = 0
    cases = tuple(legal_read_api.legal_search_benchmark_cases())
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
    relevance_pct = round((hits * 100.0) / total, 3) if total else 0.0
    diagnostic_passed = relevance_pct >= _RETRIEVAL_DIAGNOSTIC_THRESHOLD_PCT
    metrics: dict[str, float | int] = {
        **lex_outcome.metrics,
        "scientist_retrieval_cases_total": total,
        "scientist_retrieval_top5_relevance_pct": relevance_pct,
    }
    report_path = output_dir / "scientist_retrieval_benchmark.json"
    _atomic_write_json(
        report_path,
        {
            "kind": "scientist_retrieval_diagnostic",
            "lex_semantic_receipt": {
                "path": str(lex_outcome.report_path),
                "sha256": lex_report_sha256,
                "passed": lex_outcome.passed,
                "failed_checks": list(lex_outcome.failed_checks),
            },
            "retrieval_diagnostic": {
                "passed": diagnostic_passed,
                "threshold_pct": _RETRIEVAL_DIAGNOSTIC_THRESHOLD_PCT,
                "cases": rows,
            },
            "combined_readiness": {
                "passed": lex_outcome.passed,
                "rule": "lex_semantic_only_no_retrieval_promotion",
            },
            "metrics": metrics,
            "authoritative_for": [],
            "may_not_use_for": list(_MAY_NOT_USE_FOR),
        },
    )
    return ScientistRetrievalBenchmarkOutcome(
        report_path=report_path,
        metrics=metrics,
        passed=lex_outcome.passed,
        failed_checks=list(lex_outcome.failed_checks),
        lex_semantic_passed=lex_outcome.passed,
    )


class ScientistLegalBenchmarkRunner:
    """Compose the authoritative Lex result with a non-authoritative diagnostic."""

    def __init__(
        self,
        *,
        toolkit: KnowledgeToolkit,
        lex_runner: Callable[[LegalBenchmarkConfig], LexSemanticOutcome] | None = None,
    ) -> None:
        self._toolkit = toolkit
        self._lex_runner = lex_runner

    def __call__(
        self,
        config: LegalBenchmarkConfig,
    ) -> ScientistRetrievalBenchmarkOutcome:
        lex_runner = self._lex_runner
        if lex_runner is None:
            from polisyos import lex

            lex_runner = lex.run_legal_benchmark
        lex_outcome = lex_runner(config)
        return run_retrieval_benchmark(
            toolkit=self._toolkit,
            output_dir=config.output_dir,
            lex_outcome=lex_outcome,
        )


__all__ = [
    "ScientistLegalBenchmarkRunner",
    "ScientistRetrievalBenchmarkOutcome",
    "run_retrieval_benchmark",
]
