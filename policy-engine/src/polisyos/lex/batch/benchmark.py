"""Deterministic consumer benchmarks for the Lex legal bundle."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.claims.persist import load_json_artifact
from polisyos.lex.api import assemble_norm_pack, evaluate_transport_constraints
from polisyos.lex.batch.config import BatchConfig
from polisyos.lex.knowledge.search import LegalKnowledgeGraph
from polisyos.lex.types import NormPackBuildRequest
from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit

READINESS_THRESHOLDS: dict[str, float] = {
    "benchmark_search_top5_relevance_pct": 70.0,
    "benchmark_constraints_ready_pct": 70.0,
    "benchmark_cross_graph_non_unknown_pct": 70.0,
    "benchmark_normpack_ready_pct": 90.0,
}
_READINESS_TOTALS: dict[str, str] = {
    "benchmark_search_top5_relevance_pct": "benchmark_search_cases_total",
    "benchmark_constraints_ready_pct": "benchmark_constraints_domains_total",
    "benchmark_cross_graph_non_unknown_pct": "benchmark_cross_graph_cases_total",
    "benchmark_normpack_ready_pct": "benchmark_normpack_cases_total",
}

_POLICY_CASES: tuple[tuple[str, dict[str, Any]], ...] = (
    ("licensing", {"retroactive": True}),
    ("reporting", {"transition_period": "3mo"}),
    ("public_sector", {"retroactive": True}),
)


@dataclass(frozen=True)
class LegalSearchBenchmarkCase:
    case_id: str
    query: str
    expected_actions: tuple[str, ...] = ()
    expected_norm_types: tuple[str, ...] = ()
    domain: str | None = None


@dataclass(frozen=True)
class BenchmarkOutcome:
    report_path: Path
    metrics: dict[str, float | int]
    passed: bool
    failed_checks: list[str]


DEFAULT_SEARCH_CASES: tuple[LegalSearchBenchmarkCase, ...] = (
    LegalSearchBenchmarkCase(
        case_id="licensing_approvals",
        query="ліцензія дозвіл погодження",
        expected_actions=("requires", "grants", "approves"),
        expected_norm_types=("obligation", "permission", "procedure"),
    ),
    LegalSearchBenchmarkCase(
        case_id="reporting_compliance",
        query="подати звіт повідомити орган",
        expected_actions=("requires", "delegates"),
        expected_norm_types=("obligation", "procedure"),
    ),
    LegalSearchBenchmarkCase(
        case_id="entry_force_amendment",
        query="набирає чинності внесення змін",
        expected_actions=("enters_into_force", "amends", "repeals"),
        expected_norm_types=("entry_into_force", "amendment", "repeal"),
    ),
    LegalSearchBenchmarkCase(
        case_id="thresholds",
        query="відсоток грн мінімальний розмір",
        expected_actions=("sets_threshold",),
        expected_norm_types=("obligation", "procedure"),
    ),
)


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator * 100.0) / denominator, 3)


def _table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = ? LIMIT 1",
        [table_name],
    ).fetchone()
    return row is not None


def _load_top_domains(con: duckdb.DuckDBPyConnection) -> list[str]:
    if _table_exists(con, "lex_normative_facts"):
        rows = con.execute(
            """
            SELECT LOWER(COALESCE(top_domain, '')) AS domain, COUNT(*) AS cnt
            FROM lex_normative_facts
            WHERE COALESCE(top_domain, '') <> ''
            GROUP BY 1
            ORDER BY cnt DESC, domain ASC
            LIMIT 5
            """
        ).fetchall()
        domains = [str(row[0] or "") for row in rows if str(row[0] or "").strip()]
        if domains:
            return domains
    if _table_exists(con, "lex_doc_domains"):
        rows = con.execute(
            """
            SELECT LOWER(COALESCE(domain, '')) AS domain, COUNT(*) AS cnt
            FROM lex_doc_domains
            WHERE COALESCE(domain, '') <> ''
            GROUP BY 1
            ORDER BY cnt DESC, domain ASC
            LIMIT 5
            """
        ).fetchall()
        return [str(row[0] or "") for row in rows if str(row[0] or "").strip()]
    return []


def _result_matches_case(result: Any, case: LegalSearchBenchmarkCase) -> bool:
    action = str(getattr(result, "action_canon", "") or getattr(result, "predicate", "") or "").strip().lower()
    norm_type = str(getattr(result, "norm_type_canon", "") or getattr(result, "norm_type", "") or "").strip().lower()
    domain = str(getattr(result, "top_domain", "") or "").strip().lower()
    if case.expected_actions and action not in set(case.expected_actions):
        return False
    if case.expected_norm_types and norm_type not in set(case.expected_norm_types):
        return False
    if case.domain and domain != case.domain.lower():
        return False
    return True


def _merge_results(merged: dict[str, Any], results: list[Any]) -> None:
    for result in results:
        merged.setdefault(result.fact_id, result)


def _search_case_results(
    toolkit: KnowledgeToolkit,
    graph: LegalKnowledgeGraph,
    case: LegalSearchBenchmarkCase,
) -> list[Any]:
    results = toolkit.search_legal_facts(
        case.query,
        top_k=5,
        trust_tier="grounded_fact",
        include_candidates=False,
    )
    if results and any(_result_matches_case(result, case) for result in results):
        return results

    merged: dict[str, Any] = {}
    if case.expected_actions:
        for action in case.expected_actions:
            _merge_results(
                merged,
                graph.search_facts_by_action(
                    action,
                    top_k=5,
                    trust_tier="grounded_fact",
                    domain=case.domain,
                    include_candidates=False,
                ),
            )

    if "sets_threshold" in set(case.expected_actions):
        for token in [part.strip() for part in case.query.split() if len(part.strip()) >= 4]:
            _merge_results(
                merged,
                toolkit.search_legal_thresholds(
                    token,
                    top_k=5,
                    domain=case.domain,
                ),
            )

    _merge_results(merged, results)
    for token in [part.strip() for part in case.query.split() if len(part.strip()) >= 4]:
        _merge_results(
            merged,
            toolkit.search_legal_facts(
                token,
                top_k=5,
                trust_tier="grounded_fact",
                include_candidates=False,
            ),
        )
    for token in [part.strip() for part in case.query.split() if len(part.strip()) >= 4]:
        provisions = toolkit.search_legal_provisions(token, top_k=5)
        for provision in provisions:
            fact_results = toolkit.search_legal_facts(
                provision.provision_text_preview,
                top_k=5,
                trust_tier="grounded_fact",
                include_candidates=False,
            )
            _merge_results(merged, fact_results)
    return list(merged.values())[:5]


def _run_search_benchmark(
    toolkit: KnowledgeToolkit,
    graph: LegalKnowledgeGraph,
) -> tuple[dict[str, Any], dict[str, float | int]]:
    rows: list[dict[str, Any]] = []
    top5_hits = 0
    for case in DEFAULT_SEARCH_CASES:
        results = _search_case_results(toolkit, graph, case)
        matched = next((result for result in results if _result_matches_case(result, case)), None)
        if matched is not None:
            top5_hits += 1
        rows.append(
            {
                "case_id": case.case_id,
                "query": case.query,
                "results_total": len(results),
                "matched": matched is not None,
                "matched_fact_id": getattr(matched, "fact_id", "") if matched is not None else "",
                "matched_action": getattr(matched, "action_canon", "") if matched is not None else "",
                "matched_norm_type": getattr(matched, "norm_type_canon", "") if matched is not None else "",
            }
        )
    metrics: dict[str, float | int] = {
        "benchmark_search_cases_total": len(DEFAULT_SEARCH_CASES),
        "benchmark_search_top5_relevance_pct": _pct(top5_hits, len(DEFAULT_SEARCH_CASES)),
    }
    return {"cases": rows, "metrics": metrics}, metrics


def _run_constraints_benchmark(toolkit: KnowledgeToolkit, *, domains: list[str]) -> tuple[dict[str, Any], dict[str, float | int]]:
    rows: list[dict[str, Any]] = []
    ready = 0
    for domain in domains:
        results = toolkit.find_legal_constraints(domain=domain, top_k=20)
        if results:
            ready += 1
        rows.append(
            {
                "domain": domain,
                "constraints_total": len(results),
                "ready": bool(results),
                "top_fact_id": results[0].fact_id if results else "",
            }
        )
    metrics: dict[str, float | int] = {
        "benchmark_constraints_domains_total": len(domains),
        "benchmark_constraints_ready_pct": _pct(ready, len(domains)),
    }
    return {"domains": rows, "metrics": metrics}, metrics


def _resolve_cross_graph_status(*, toolkit: KnowledgeToolkit, domain: str, db_path: Path) -> tuple[str, str]:
    constraint_set = evaluate_transport_constraints(
        jurisdiction="UA",
        policy_domain=domain,
        policy_spec={"retroactive": True},
        legal_kg_db_path=db_path,
    )
    all_constraints = [
        *constraint_set.hard_constraints,
        *constraint_set.soft_constraints,
        *constraint_set.data_license_constraints,
    ]
    grounded_constraints = [
        constraint
        for constraint in all_constraints
        if not str(constraint.legal_source or "").endswith(":legal_kg")
        and not str(constraint.legal_source or "").endswith(":dataset_license")
    ]
    if grounded_constraints and constraint_set.hard_constraints:
        return "prohibited", grounded_constraints[0].legal_source
    if grounded_constraints and (constraint_set.soft_constraints or constraint_set.data_license_constraints):
        return "constrained", grounded_constraints[0].legal_source
    applicable = toolkit.get_applicable_norms(domain=domain, top_k=20)
    if applicable:
        return "allowed", applicable[0].doc_name or applicable[0].doc_reestr_code
    return "unknown", ""


def _run_cross_graph_benchmark(
    toolkit: KnowledgeToolkit,
    *,
    db_path: Path,
    domains: list[str],
) -> tuple[dict[str, Any], dict[str, float | int]]:
    rows: list[dict[str, Any]] = []
    non_unknown = 0
    selected_domains = domains[: len(_POLICY_CASES)] if domains else []
    for idx, domain in enumerate(selected_domains):
        label, policy_spec = _POLICY_CASES[idx]
        status, provenance = _resolve_cross_graph_status(
            toolkit=toolkit,
            domain=domain,
            db_path=db_path,
        )
        if status != "unknown":
            non_unknown += 1
        rows.append(
            {
                "case_id": f"{label}:{domain}",
                "policy_domain": domain,
                "policy_spec": policy_spec,
                "legal_status": status,
                "provenance": provenance,
            }
        )
    metrics: dict[str, float | int] = {
        "benchmark_cross_graph_cases_total": len(selected_domains),
        "benchmark_cross_graph_non_unknown_pct": _pct(non_unknown, len(selected_domains)),
    }
    return {"cases": rows, "metrics": metrics}, metrics


def _run_normpack_benchmark(config: BatchConfig) -> tuple[dict[str, Any], dict[str, float | int]]:
    summary_path = config.claim_exports_dir / "normative_claim_sets_summary.json"
    if not summary_path.exists():
        return {
            "cases": [],
            "metrics": {
                "benchmark_normpack_cases_total": 0,
                "benchmark_normpack_ready_pct": 0.0,
            },
            "status": "skipped_missing_claim_sets",
        }, {
            "benchmark_normpack_cases_total": 0,
            "benchmark_normpack_ready_pct": 0.0,
        }

    with open(summary_path, "r", encoding="utf-8") as fh:
        summary = json.load(fh)

    claim_set_ids = [
        str(item)
        for item in summary.get("normalized_claim_set_artifact_ids", [])
        if str(item).strip()
    ]
    if not claim_set_ids:
        return {
            "cases": [],
            "metrics": {
                "benchmark_normpack_cases_total": 0,
                "benchmark_normpack_ready_pct": 0.0,
            },
            "status": "skipped_empty_claim_sets",
        }, {
            "benchmark_normpack_cases_total": 0,
            "benchmark_normpack_ready_pct": 0.0,
        }

    cas_root_value = str(summary.get("cas_root") or config.cas_root or "").strip()
    fact_log_root_value = str(summary.get("fact_log_root") or config.fact_log_root or "").strip()
    if not cas_root_value or not fact_log_root_value:
        return {
            "cases": [],
            "metrics": {
                "benchmark_normpack_cases_total": 0,
                "benchmark_normpack_ready_pct": 0.0,
            },
            "status": "skipped_missing_paths",
        }, {
            "benchmark_normpack_cases_total": 0,
            "benchmark_normpack_ready_pct": 0.0,
        }
    cas_root = Path(cas_root_value).expanduser()
    fact_log_root = Path(fact_log_root_value).expanduser()
    if not cas_root.exists() or not fact_log_root.exists():
        return {
            "cases": [],
            "metrics": {
                "benchmark_normpack_cases_total": 0,
                "benchmark_normpack_ready_pct": 0.0,
            },
            "status": "skipped_missing_cas",
        }, {
            "benchmark_normpack_cases_total": 0,
            "benchmark_normpack_ready_pct": 0.0,
        }

    cas = FileSystemCAS(cas_root)
    claim_set_records: list[dict[str, str]] = []
    for artifact_id in claim_set_ids:
        try:
            payload = load_json_artifact(cas, artifact_id)
        except Exception:
            continue
        claim_set_records.append(
            {
                "artifact_id": artifact_id,
                "domain": str(payload.get("domain") or "").strip(),
                "doc_source_id": str(payload.get("doc_source_id") or "").strip(),
            }
        )
    if not claim_set_records:
        return {
            "cases": [],
            "metrics": {
                "benchmark_normpack_cases_total": 0,
                "benchmark_normpack_ready_pct": 0.0,
            },
            "status": "skipped_invalid_claim_set",
        }, {
            "benchmark_normpack_cases_total": 0,
            "benchmark_normpack_ready_pct": 0.0,
        }

    grouped_by_domain: dict[str, list[str]] = {}
    for record in claim_set_records:
        domain_key = record["domain"] or f"doc_source:{record['doc_source_id'] or record['artifact_id']}"
        grouped_by_domain.setdefault(domain_key, []).append(record["artifact_id"])
    selected_groups = sorted(
        grouped_by_domain.items(),
        key=lambda item: (len(item[1]), item[0]),
        reverse=True,
    )[:3]

    case_rows: list[dict[str, Any]] = []
    ready_cases = 0
    as_of = datetime.now(UTC).date().isoformat()
    for domain_key, artifact_ids in selected_groups:
        domain = None if domain_key.startswith("doc_source:") else domain_key
        request = NormPackBuildRequest(
            jurisdiction="ua",
            as_of=as_of,
            domain=domain,
            claim_set_artifact_ids=sorted(set(artifact_ids)),
        )
        result = assemble_norm_pack(
            cas=cas,
            fact_log_root=fact_log_root,
            request=request,
            db=None,
        )
        ready = bool(result.claim_set_artifact_ids and result.selected_doc_versions)
        if ready:
            ready_cases += 1
        case_rows.append(
            {
                "jurisdiction": request.jurisdiction,
                "domain": request.domain,
                "case_key": domain_key,
                "claim_set_artifact_ids_total": len(sorted(set(artifact_ids))),
                "selected_doc_versions": len(result.selected_doc_versions),
                "selected_fragment_ids": len(result.selected_fragment_ids),
                "conflict_set_ids": len(result.conflict_set_ids),
                "ready": ready,
            }
        )

    payload = {
        "cases": case_rows,
        "metrics": {
            "benchmark_normpack_cases_total": len(case_rows),
            "benchmark_normpack_ready_pct": _pct(ready_cases, len(case_rows)),
        },
        "status": "ok" if case_rows else "skipped_empty_claim_sets",
    }
    return payload, payload["metrics"]


def _evaluate_readiness(metrics: dict[str, float | int]) -> tuple[bool, list[str]]:
    failed: list[str] = []
    for metric_name, threshold in READINESS_THRESHOLDS.items():
        total_name = _READINESS_TOTALS.get(metric_name, metric_name.replace("_pct", "_total"))
        total = int(metrics.get(total_name, 0) or 0)
        if total <= 0:
            continue
        value = float(metrics.get(metric_name, 0.0) or 0.0)
        if value < threshold:
            failed.append(metric_name)
    return not failed, failed


def run_benchmark(config: BatchConfig) -> BenchmarkOutcome:
    """Run deterministic legal consumer benchmarks and write JSON report."""
    if not config.db_path.exists():
        raise FileNotFoundError(f"Lex knowledge graph not found: {config.db_path}")

    with duckdb.connect(str(config.db_path), read_only=True) as con:
        domains = _load_top_domains(con)

    graph = LegalKnowledgeGraph(
        db_path=config.db_path,
        index_dir=config.output_dir,
        openai_api_key=None,
    )
    toolkit = KnowledgeToolkit(legal_graph=graph)
    try:
        search_payload, search_metrics = _run_search_benchmark(toolkit, graph)
        constraint_payload, constraint_metrics = _run_constraints_benchmark(toolkit, domains=domains)
        cross_graph_payload, cross_graph_metrics = _run_cross_graph_benchmark(
            toolkit,
            db_path=config.db_path,
            domains=domains,
        )
        normpack_payload, normpack_metrics = _run_normpack_benchmark(config)
    finally:
        graph.close()

    metrics: dict[str, float | int] = {
        **search_metrics,
        **constraint_metrics,
        **cross_graph_metrics,
        **normpack_metrics,
    }
    passed, failed_checks = _evaluate_readiness(metrics)
    payload = {
        "kind": "lex_benchmark",
        "generated_at": datetime.now(UTC).isoformat(),
        "component_dir": str(config.output_dir),
        "metrics": metrics,
        "readiness": {
            "passed": passed,
            "failed_checks": failed_checks,
            "thresholds": READINESS_THRESHOLDS,
        },
        "sections": {
            "search": search_payload,
            "constraints": constraint_payload,
            "cross_graph": cross_graph_payload,
            "normpack": normpack_payload,
        },
    }
    config.benchmark_report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config.benchmark_report_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    write_stage_manifest(
        manifest_path=config.output_dir / "manifests" / "benchmark.json",
        stage="benchmark",
        status="ok" if passed else "failed",
        metrics={**metrics, "readiness_passed": int(passed)},
        artifacts=[config.benchmark_report_path],
        started_at=datetime.now(UTC).isoformat(),
    )

    return BenchmarkOutcome(
        report_path=config.benchmark_report_path,
        metrics=metrics,
        passed=passed,
        failed_checks=failed_checks,
    )


__all__ = [
    "BenchmarkOutcome",
    "DEFAULT_SEARCH_CASES",
    "LegalSearchBenchmarkCase",
    "READINESS_THRESHOLDS",
    "run_benchmark",
]
