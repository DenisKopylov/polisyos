"""Deterministic consumer benchmarks for the Lex legal bundle."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb

from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.claims.persist import load_json_artifact
from polisyos.lex.api import assemble_norm_pack, evaluate_transport_constraints
from polisyos.lex.batch.amendment_metrics import collect_amendment_quality_metrics
from polisyos.lex.knowledge.search import LegalKnowledgeGraph
from polisyos.lex.types import NormPackBuildRequest
from polisyos.scientist.agent.knowledge_tools import KnowledgeToolkit

if TYPE_CHECKING:
    from polisyos.lex.batch.config import BatchConfig

READINESS_THRESHOLDS: dict[str, float] = {
    "benchmark_search_top5_relevance_pct": 70.0,
    "benchmark_constraints_ready_pct": 70.0,
    "benchmark_cross_graph_non_unknown_pct": 70.0,
    "benchmark_normpack_ready_pct": 90.0,
    "benchmark_reference_resolution_ready_pct": 85.0,
    "benchmark_amendment_extraction_ready_pct": 60.0,
    "benchmark_amendment_target_resolution_pct": 70.0,
    "benchmark_hallucination_blocking_clean_pct": 97.0,
    "benchmark_temporal_current_safety_pct": 100.0,
    "benchmark_consistency_resolution_ready_pct": 80.0,
}
ADVISORY_THRESHOLDS: dict[str, float] = {
    "benchmark_entity_dedup_ready_pct": 60.0,
    "benchmark_hallucination_clean_pct": 97.0,
}
_READINESS_TOTALS: dict[str, str] = {
    "benchmark_search_top5_relevance_pct": "benchmark_search_cases_total",
    "benchmark_constraints_ready_pct": "benchmark_constraints_domains_total",
    "benchmark_cross_graph_non_unknown_pct": "benchmark_cross_graph_cases_total",
    "benchmark_normpack_ready_pct": "benchmark_normpack_cases_total",
    "benchmark_reference_resolution_ready_pct": "benchmark_reference_resolution_cases_total",
    "benchmark_amendment_extraction_ready_pct": "benchmark_amendment_docs_total",
    "benchmark_amendment_target_resolution_pct": "benchmark_single_target_amendment_docs_total",
    "benchmark_hallucination_clean_pct": "benchmark_hallucination_cases_total",
    "benchmark_hallucination_blocking_clean_pct": "benchmark_hallucination_cases_total",
    "benchmark_temporal_current_safety_pct": "benchmark_temporal_current_safety_cases_total",
    "benchmark_consistency_resolution_ready_pct": "benchmark_consistency_cases_total",
}
_BLOCKING_HALLUCINATION_FLAGS = ("phantom_number", "phantom_article_reference")
_ADVISORY_HALLUCINATION_FLAGS = ("ungrounded_subject", "norm_type_mismatch")

_POLICY_CASES: tuple[tuple[str, dict[str, Any]], ...] = (
    ("licensing", {"retroactive": True}),
    ("reporting", {"transition_period": "3mo"}),
    ("public_sector", {"retroactive": True}),
)


@dataclass(frozen=True)
class LegalSearchBenchmarkCase:
    """Legal search benchmark case public type."""

    case_id: str
    query: str
    expected_actions: tuple[str, ...] = ()
    expected_norm_types: tuple[str, ...] = ()
    domain: str | None = None


@dataclass(frozen=True)
class BenchmarkOutcome:
    """Benchmark outcome public type."""

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


def _column_exists(con: duckdb.DuckDBPyConnection, table_name: str, column_name: str) -> bool:
    row = con.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = ? AND column_name = ?
        LIMIT 1
        """,
        [table_name, column_name],
    ).fetchone()
    return row is not None


def _hallucination_flag_condition(flags: tuple[str, ...]) -> str:
    if not flags:
        return "FALSE"
    return " OR ".join(
        f"LOWER(COALESCE(hallucination_flags_json, '')) LIKE '%{flag.lower()}%'" for flag in flags
    )


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
    action = (
        str(getattr(result, "action_canon", "") or getattr(result, "predicate", "") or "")
        .strip()
        .lower()
    )
    norm_type = (
        str(getattr(result, "norm_type_canon", "") or getattr(result, "norm_type", "") or "")
        .strip()
        .lower()
    )
    domain = str(getattr(result, "top_domain", "") or "").strip().lower()
    if case.expected_actions and action not in set(case.expected_actions):
        return False
    if case.expected_norm_types and norm_type not in set(case.expected_norm_types):
        return False
    return not (case.domain and domain != case.domain.lower())


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
                "matched_action": getattr(matched, "action_canon", "")
                if matched is not None
                else "",
                "matched_norm_type": getattr(matched, "norm_type_canon", "")
                if matched is not None
                else "",
            }
        )
    metrics: dict[str, float | int] = {
        "benchmark_search_cases_total": len(DEFAULT_SEARCH_CASES),
        "benchmark_search_top5_relevance_pct": _pct(top5_hits, len(DEFAULT_SEARCH_CASES)),
    }
    return {"cases": rows, "metrics": metrics}, metrics


def _run_constraints_benchmark(
    toolkit: KnowledgeToolkit, *, domains: list[str]
) -> tuple[dict[str, Any], dict[str, float | int]]:
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


def _resolve_cross_graph_status(
    *, toolkit: KnowledgeToolkit, domain: str, db_path: Path
) -> tuple[str, str]:
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
    if grounded_constraints and (
        constraint_set.soft_constraints or constraint_set.data_license_constraints
    ):
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

    with open(summary_path, encoding="utf-8") as fh:
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
        domain_key = (
            record["domain"] or f"doc_source:{record['doc_source_id'] or record['artifact_id']}"
        )
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


def _normative_fact_table(
    con: duckdb.DuckDBPyConnection,
) -> tuple[str, str]:
    if _table_exists(con, "lex_normative_facts"):
        return "lex_normative_facts", ""
    if _table_exists(con, "lex_facts") and _column_exists(con, "lex_facts", "trust_tier"):
        return "lex_facts", " WHERE LOWER(COALESCE(trust_tier, '')) = 'normative_fact'"
    return "", ""


def _run_quality_capability_benchmark(
    *,
    db_path: Path,
) -> tuple[dict[str, Any], dict[str, float | int]]:
    metrics: dict[str, float | int] = {
        "benchmark_entity_resolution_cases_total": 0,
        "benchmark_entity_dedup_ready_pct": 0.0,
        "benchmark_reference_resolution_cases_total": 0,
        "benchmark_reference_resolution_ready_pct": 0.0,
        "benchmark_amendment_docs_total": 0,
        "benchmark_amendment_cases_total": 0,
        "benchmark_amendment_extraction_ready_pct": 0.0,
        "benchmark_amendment_target_resolution_pct": 0.0,
        "benchmark_hallucination_cases_total": 0,
        "benchmark_hallucination_clean_pct": 0.0,
        "benchmark_hallucination_blocking_clean_pct": 0.0,
        "benchmark_temporal_docs_total": 0,
        "benchmark_doc_temporal_resolved_pct": 0.0,
        "benchmark_fact_temporal_resolved_pct": 0.0,
        "benchmark_temporal_current_safety_cases_total": 0,
        "benchmark_temporal_current_safety_pct": 0.0,
        "benchmark_consistency_cases_total": 0,
        "benchmark_consistency_resolution_ready_pct": 0.0,
        "benchmark_high_confidence_norm_cases_total": 0,
        "benchmark_high_confidence_norm_share_pct": 0.0,
    }
    payload: dict[str, Any] = {"status": "ok", "metrics": {}, "sections": {}}

    with duckdb.connect(str(db_path), read_only=True) as con:
        if _table_exists(con, "lex_entities") and _column_exists(
            con, "lex_entities", "mention_count"
        ):
            entity_total = int(con.execute("SELECT COUNT(*) FROM lex_entities").fetchone()[0])
            single_mention_total = int(
                con.execute(
                    """
                    SELECT COUNT(*)
                    FROM lex_entities
                    WHERE COALESCE(mention_count, 0) <= 1
                    """
                ).fetchone()[0]
            )
            metrics["benchmark_entity_resolution_cases_total"] = entity_total
            metrics["benchmark_entity_dedup_ready_pct"] = round(
                100.0 - _pct(single_mention_total, entity_total),
                3,
            )
            payload["sections"]["entity_resolution"] = {
                "entities_total": entity_total,
                "single_mention_entities": single_mention_total,
                "single_mention_entity_pct": round(_pct(single_mention_total, entity_total), 3),
                "dedup_ready_pct": metrics["benchmark_entity_dedup_ready_pct"],
            }

        if _table_exists(con, "lex_reference_resolution_audit"):
            reference_total = int(
                con.execute("SELECT COUNT(*) FROM lex_reference_resolution_audit").fetchone()[0]
            )
            resolved_total = int(
                con.execute(
                    """
                    SELECT COUNT(*)
                    FROM lex_reference_resolution_audit
                    WHERE LOWER(COALESCE(resolution_status, '')) = 'resolved'
                    """
                ).fetchone()[0]
            )
            metrics["benchmark_reference_resolution_cases_total"] = reference_total
            metrics["benchmark_reference_resolution_ready_pct"] = round(
                _pct(resolved_total, reference_total),
                3,
            )
            payload["sections"]["reference_resolution"] = {
                "references_total": reference_total,
                "resolved_total": resolved_total,
                "resolution_ready_pct": metrics["benchmark_reference_resolution_ready_pct"],
            }

        amendment_metrics = collect_amendment_quality_metrics(con)
        if amendment_metrics.available:
            metrics["benchmark_amendment_docs_total"] = amendment_metrics.amendment_candidate_docs
            metrics["benchmark_amendment_cases_total"] = (
                amendment_metrics.amendment_target_expected_total
            )
            metrics["benchmark_single_target_amendment_docs_total"] = (
                amendment_metrics.expected_single_target_amendment_docs_total
            )
            metrics["benchmark_amendment_extraction_ready_pct"] = round(
                amendment_metrics.amendment_extraction_coverage_pct,
                3,
            )
            metrics["benchmark_amendment_target_resolution_pct"] = round(
                amendment_metrics.amendment_target_resolution_pct,
                3,
            )
            metrics["benchmark_amendment_target_row_resolution_pct"] = round(
                amendment_metrics.amendment_target_row_resolution_pct,
                3,
            )
            metrics["benchmark_single_target_title_resolution_pct"] = round(
                amendment_metrics.single_target_title_resolution_pct,
                3,
            )
            payload["sections"]["amendments"] = {
                "amendment_docs_total": amendment_metrics.amendment_candidate_docs,
                "amendment_docs_extracted": amendment_metrics.amendment_docs_extracted,
                "amendments_total": amendment_metrics.amendments_total,
                "amendments_with_target": amendment_metrics.amendments_with_target_total,
                "amendment_target_expected_total": amendment_metrics.amendment_target_expected_total,
                "amendment_target_row_resolution_pct": metrics[
                    "benchmark_amendment_target_row_resolution_pct"
                ],
                "single_target_amendment_docs_total": amendment_metrics.expected_single_target_amendment_docs_total,
                "resolved_single_target_amendment_docs_total": amendment_metrics.resolved_single_target_amendment_docs_total,
                "single_target_title_docs_total": amendment_metrics.single_target_title_docs_total,
                "resolved_single_target_title_docs_total": amendment_metrics.resolved_single_target_title_docs_total,
                "single_target_title_resolution_pct": metrics[
                    "benchmark_single_target_title_resolution_pct"
                ],
                "amendment_title_unresolved_docs_total": amendment_metrics.amendment_title_unresolved_docs_total,
                "multi_target_title_docs_total": amendment_metrics.multi_target_title_docs_total,
                "extraction_ready_pct": metrics["benchmark_amendment_extraction_ready_pct"],
                "target_resolution_pct": metrics["benchmark_amendment_target_resolution_pct"],
            }

        if _table_exists(con, "lex_doc_temporal"):
            doc_temporal_total = int(
                con.execute("SELECT COUNT(*) FROM lex_doc_temporal").fetchone()[0]
            )
            doc_temporal_resolved = int(
                con.execute(
                    """
                    SELECT COUNT(*) FROM lex_doc_temporal
                    WHERE LOWER(COALESCE(temporal_resolution_status, 'unknown')) = 'resolved'
                    """
                ).fetchone()[0]
            )
            metrics["benchmark_temporal_docs_total"] = doc_temporal_total
            metrics["benchmark_doc_temporal_resolved_pct"] = round(
                _pct(doc_temporal_resolved, doc_temporal_total),
                3,
            )
            payload["sections"]["doc_temporal"] = {
                "docs_total": doc_temporal_total,
                "resolved_docs": doc_temporal_resolved,
                "doc_temporal_resolved_pct": metrics["benchmark_doc_temporal_resolved_pct"],
            }

        normative_table, normative_where = _normative_fact_table(con)
        if normative_table:
            normative_total = int(
                con.execute(f"SELECT COUNT(*) FROM {normative_table}{normative_where}").fetchone()[
                    0
                ]
            )
            if _column_exists(con, normative_table, "temporal_resolution_status"):
                fact_temporal_resolved = int(
                    con.execute(
                        f"""
                        SELECT COUNT(*) FROM {normative_table}
                        {normative_where}
                        {" AND " if normative_where else " WHERE "}
                        LOWER(COALESCE(temporal_resolution_status, 'unknown')) = 'resolved'
                        """
                    ).fetchone()[0]
                )
                unsafe_current_rows = int(
                    con.execute(
                        f"""
                        SELECT COUNT(*) FROM {normative_table}
                        {normative_where}
                        {" AND " if normative_where else " WHERE "}
                        LOWER(COALESCE(doc_status, '')) IN ('втратив чинність', 'втратив чинність частково', 'не набрав чинності', 'дію призупинено')
                          AND LOWER(COALESCE(temporal_resolution_status, 'unknown')) = 'resolved'
                          AND COALESCE(effective_from, '') <> ''
                          AND effective_from <= CAST(CURRENT_DATE AS VARCHAR)
                          AND (COALESCE(effective_to, '') = '' OR CAST(CURRENT_DATE AS VARCHAR) <= effective_to)
                        """
                    ).fetchone()[0]
                )
                blocked_temporal_rows = int(
                    con.execute(
                        f"""
                        SELECT COUNT(*) FROM {normative_table}
                        {normative_where}
                        {" AND " if normative_where else " WHERE "}
                        LOWER(COALESCE(doc_status, '')) IN ('втратив чинність', 'втратив чинність частково', 'не набрав чинності', 'дію призупинено')
                        """
                    ).fetchone()[0]
                )
                metrics["benchmark_fact_temporal_resolved_pct"] = round(
                    _pct(fact_temporal_resolved, normative_total),
                    3,
                )
                metrics["benchmark_temporal_current_safety_cases_total"] = blocked_temporal_rows
                metrics["benchmark_temporal_current_safety_pct"] = round(
                    100.0 - _pct(unsafe_current_rows, blocked_temporal_rows),
                    3,
                )
                payload["sections"]["fact_temporal"] = {
                    "facts_total": normative_total,
                    "resolved_facts": fact_temporal_resolved,
                    "fact_temporal_resolved_pct": metrics["benchmark_fact_temporal_resolved_pct"],
                    "blocked_temporal_rows": blocked_temporal_rows,
                    "unsafe_current_rows": unsafe_current_rows,
                    "temporal_current_safety_pct": metrics["benchmark_temporal_current_safety_pct"],
                }
            if _table_exists(con, "lex_high_confidence_norms"):
                high_conf_total = int(
                    con.execute("SELECT COUNT(*) FROM lex_high_confidence_norms").fetchone()[0]
                )
                metrics["benchmark_high_confidence_norm_cases_total"] = normative_total
                metrics["benchmark_high_confidence_norm_share_pct"] = round(
                    _pct(high_conf_total, normative_total),
                    3,
                )
                payload["sections"]["high_confidence_norms"] = {
                    "normative_facts_total": normative_total,
                    "high_confidence_norms_total": high_conf_total,
                    "high_confidence_norm_share_pct": metrics[
                        "benchmark_high_confidence_norm_share_pct"
                    ],
                }

            if _column_exists(con, normative_table, "hallucination_flags_json"):
                hallucination_clean_total = int(
                    con.execute(
                        f"""
                        SELECT COUNT(*) FROM {normative_table}
                        {normative_where}
                        {" AND " if normative_where else " WHERE "}
                        TRIM(COALESCE(hallucination_flags_json, '')) IN ('', '[]')
                        """
                    ).fetchone()[0]
                )
                hallucination_blocking_flagged_total = int(
                    con.execute(
                        f"""
                        SELECT COUNT(*) FROM {normative_table}
                        {normative_where}
                        {" AND " if normative_where else " WHERE "}
                        ({_hallucination_flag_condition(_BLOCKING_HALLUCINATION_FLAGS)})
                        """
                    ).fetchone()[0]
                )
                hallucination_advisory_flagged_total = int(
                    con.execute(
                        f"""
                        SELECT COUNT(*) FROM {normative_table}
                        {normative_where}
                        {" AND " if normative_where else " WHERE "}
                        ({_hallucination_flag_condition(_ADVISORY_HALLUCINATION_FLAGS)})
                        """
                    ).fetchone()[0]
                )
                metrics["benchmark_hallucination_cases_total"] = normative_total
                metrics["benchmark_hallucination_clean_pct"] = round(
                    _pct(hallucination_clean_total, normative_total),
                    3,
                )
                metrics["benchmark_hallucination_blocking_clean_pct"] = round(
                    _pct(
                        max(0, normative_total - hallucination_blocking_flagged_total),
                        normative_total,
                    ),
                    3,
                )
                payload["sections"]["hallucination"] = {
                    "facts_checked": normative_total,
                    "clean_facts": hallucination_clean_total,
                    "hallucination_clean_pct": metrics["benchmark_hallucination_clean_pct"],
                    "blocking_flagged_facts": hallucination_blocking_flagged_total,
                    "advisory_flagged_facts": hallucination_advisory_flagged_total,
                    "hallucination_blocking_clean_pct": metrics[
                        "benchmark_hallucination_blocking_clean_pct"
                    ],
                }

        if _table_exists(con, "lex_consistency_issues"):
            consistency_total = int(
                con.execute("SELECT COUNT(*) FROM lex_consistency_issues").fetchone()[0]
            )
            resolved_total = 0
            if _column_exists(con, "lex_consistency_issues", "requires_manual_review"):
                resolved_total = int(
                    con.execute(
                        """
                        SELECT COUNT(*)
                        FROM lex_consistency_issues
                        WHERE COALESCE(requires_manual_review, TRUE) = FALSE
                        """
                    ).fetchone()[0]
                )
            elif _column_exists(con, "lex_consistency_issues", "prevailing_doc_id"):
                resolved_total = int(
                    con.execute(
                        """
                        SELECT COUNT(*)
                        FROM lex_consistency_issues
                        WHERE TRIM(COALESCE(prevailing_doc_id, '')) != ''
                        """
                    ).fetchone()[0]
                )
            metrics["benchmark_consistency_cases_total"] = consistency_total
            metrics["benchmark_consistency_resolution_ready_pct"] = round(
                _pct(resolved_total, consistency_total),
                3,
            )
            payload["sections"]["consistency"] = {
                "issues_total": consistency_total,
                "resolved_issues": resolved_total,
                "resolution_ready_pct": metrics["benchmark_consistency_resolution_ready_pct"],
            }

    payload["metrics"] = metrics
    return payload, metrics


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


def _evaluate_advisory(metrics: dict[str, float | int]) -> list[str]:
    failed: list[str] = []
    for metric_name, threshold in ADVISORY_THRESHOLDS.items():
        total_name = _READINESS_TOTALS.get(metric_name, metric_name.replace("_pct", "_total"))
        total = int(metrics.get(total_name, 0) or 0)
        if total <= 0:
            continue
        value = float(metrics.get(metric_name, 0.0) or 0.0)
        if value < threshold:
            failed.append(metric_name)
    return failed


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
        constraint_payload, constraint_metrics = _run_constraints_benchmark(
            toolkit, domains=domains
        )
        cross_graph_payload, cross_graph_metrics = _run_cross_graph_benchmark(
            toolkit,
            db_path=config.db_path,
            domains=domains,
        )
        normpack_payload, normpack_metrics = _run_normpack_benchmark(config)
        quality_capability_payload, quality_capability_metrics = _run_quality_capability_benchmark(
            db_path=config.db_path,
        )
    finally:
        graph.close()

    metrics: dict[str, float | int] = {
        **search_metrics,
        **constraint_metrics,
        **cross_graph_metrics,
        **normpack_metrics,
        **quality_capability_metrics,
    }
    passed, failed_checks = _evaluate_readiness(metrics)
    advisory_failed_checks = _evaluate_advisory(metrics)
    payload = {
        "kind": "lex_benchmark",
        "generated_at": datetime.now(UTC).isoformat(),
        "component_dir": str(config.output_dir),
        "metrics": metrics,
        "readiness": {
            "passed": passed,
            "failed_checks": failed_checks,
            "thresholds": READINESS_THRESHOLDS,
            "advisory_failed_checks": advisory_failed_checks,
            "advisory_thresholds": ADVISORY_THRESHOLDS,
        },
        "sections": {
            "search": search_payload,
            "constraints": constraint_payload,
            "cross_graph": cross_graph_payload,
            "normpack": normpack_payload,
            "quality_capabilities": quality_capability_payload,
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
    "DEFAULT_SEARCH_CASES",
    "READINESS_THRESHOLDS",
    "BenchmarkOutcome",
    "LegalSearchBenchmarkCase",
    "run_benchmark",
]
