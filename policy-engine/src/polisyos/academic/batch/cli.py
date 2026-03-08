"""CLI for staged academic knowledge pipeline."""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from polisyos.academic.batch.config import ALL_STAGES, AcademicBatchConfig

_STAGE_ALIAS = {
    "topic-select": "topic_select",
    "resolve-extract": "resolve_extract",
    "merge-dedup": "merge_dedup",
    "graph-load": "graph_load",
    "graph-index": "graph_index",
}


def _normalize_stage_name(name: str) -> str:
    return _STAGE_ALIAS.get(name, name.replace("-", "_"))


def _parse_stages(raw: str | None) -> frozenset[str]:
    if not raw:
        return ALL_STAGES
    items = [_normalize_stage_name(v.strip()) for v in raw.split(",") if v.strip()]
    return frozenset(items)


def _build_config(args: argparse.Namespace, *, stages: frozenset[str]) -> AcademicBatchConfig:
    run_id_value = str(getattr(args, "run_id", "")).strip()
    resolved_run_id = run_id_value or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    raw_keys = str(getattr(args, "gonka_api_keys", "")).strip()
    gonka_api_keys = [token.strip() for token in raw_keys.split(",") if token.strip()] if raw_keys else []

    return AcademicBatchConfig(
        snapshot_root=Path(args.snapshot_root),
        stages=stages,
        resume=bool(getattr(args, "resume", False)),
        topics_dir=Path(getattr(args, "topics_dir")) if getattr(args, "topics_dir", None) else None,
        topic_limit=int(getattr(args, "topic_limit")) if getattr(args, "topic_limit", None) is not None else None,
        target_per_topic=int(getattr(args, "target_per_topic", 150)),
        pass_name=str(getattr(args, "pass_name", "pass1_abstract")),
        run_id=resolved_run_id,
        openalex_email=str(getattr(args, "openalex_email", "")),
        openalex_max_rps=int(getattr(args, "openalex_max_rps", 10)),
        openalex_max_concurrent=int(getattr(args, "openalex_max_concurrent", 5)),
        openalex_timeout_seconds=int(getattr(args, "openalex_timeout", 60)),
        openalex_max_retries=int(getattr(args, "openalex_max_retries", 5)),
        openalex_backoff_seconds=float(getattr(args, "openalex_backoff_seconds", 5.0)),
        openalex_per_page=int(getattr(args, "openalex_per_page", 200)),
        gonka_api_key=str(getattr(args, "gonka_api_key", "")),
        gonka_api_keys=gonka_api_keys,
        gonka_base_url=str(getattr(args, "gonka_base_url", "https://api.gonkagate.com/v1")),
        llm_model=str(getattr(args, "llm_model", "qwen/qwen3-235b-a22b-instruct-2507-fp8")),
        llm_temperature=float(getattr(args, "llm_temperature", 0.1)),
        max_concurrent_llm=int(getattr(args, "max_concurrent_llm", 12)),
        llm_rate_limit_rps=float(getattr(args, "llm_rate_limit_rps", 5.0)),
        llm_max_retries=int(getattr(args, "llm_max_retries", 6)),
        article_screening_model=str(getattr(args, "article_screening_model", "qwen/qwen3-32b")),
        article_extraction_model=str(
            getattr(args, "article_extraction_model", "qwen/qwen3-235b-a22b-instruct-2507-fp8")
        ),
        article_max_concurrent_llm=int(getattr(args, "article_max_concurrent_llm", 20)),
        article_rate_limit_rps=float(getattr(args, "article_rate_limit_rps", 8.0)),
        article_max_retries=int(getattr(args, "article_max_retries", 7)),
        article_fulltext_timeout_seconds=int(getattr(args, "article_fulltext_timeout_seconds", 20)),
        article_target_fulltext_per_topic=int(getattr(args, "article_target_fulltext_per_topic", 50)),
        article_prefetch_candidates_per_topic=int(getattr(args, "article_prefetch_candidates_per_topic", 150)),
        article_max_completion_tokens=int(getattr(args, "article_max_completion_tokens", 8192)),
        article_evidence_bundle_sentence_budget=int(getattr(args, "article_evidence_bundle_sentence_budget", 28)),
        article_connect_timeout_seconds=int(getattr(args, "article_connect_timeout_seconds", 15)),
        article_read_timeout_seconds=int(getattr(args, "article_read_timeout_seconds", 120)),
        article_total_timeout_seconds=int(getattr(args, "article_total_timeout_seconds", 150)),
        fulltext_max_concurrent_fetches=int(getattr(args, "fulltext_max_concurrent_fetches", 24)),
        fulltext_acquisition_mode=str(getattr(args, "fulltext_acquisition_mode", "v3_legacy")),
        fulltext_metadata_resolvers_enabled=bool(getattr(args, "fulltext_metadata_resolvers_enabled", True)),
        fulltext_unpaywall_email=str(getattr(args, "fulltext_unpaywall_email", "")),
        fulltext_metadata_timeout_seconds=int(getattr(args, "fulltext_metadata_timeout_seconds", 20)),
        fulltext_max_candidate_urls_per_work=int(getattr(args, "fulltext_max_candidate_urls_per_work", 20)),
        fulltext_min_usable_chars=int(getattr(args, "fulltext_min_usable_chars", 1500)),
        fulltext_min_soft_usable_chars=int(getattr(args, "fulltext_min_soft_usable_chars", 700)),
        fulltext_soft_usable_requires_section_cues=bool(
            getattr(args, "fulltext_soft_usable_requires_section_cues", True)
        ),
        provider_circuit_breaker_failures=int(getattr(args, "provider_circuit_breaker_failures", 5)),
        provider_circuit_breaker_reset_seconds=int(getattr(args, "provider_circuit_breaker_reset_seconds", 60)),
        llm_gate_enabled=bool(getattr(args, "llm_gate_enabled", True)),
        llm_gate_mode=str(getattr(args, "llm_gate_mode", "balanced")),
        llm_gate_threshold=float(getattr(args, "llm_gate_threshold", 0.58)),
        llm_gate_max_share=float(getattr(args, "llm_gate_max_share", 0.20)),
        llm_gate_min_score_force_llm=float(getattr(args, "llm_gate_min_score_force_llm", 0.80)),
        llm_gate_audit_sample_rate=float(getattr(args, "llm_gate_audit_sample_rate", 0.02)),
        llm_gate_audit_max_miss_rate_pct=float(getattr(args, "llm_gate_audit_max_miss_rate_pct", 3.0)),
        llm_gate_auto_conf_threshold=float(getattr(args, "llm_gate_auto_conf_threshold", 0.85)),
        llm_gate_circuit_breaker_enabled=bool(getattr(args, "llm_gate_circuit_breaker_enabled", True)),
        fail_fast_qc=bool(getattr(args, "fail_fast", True)),
    )


async def _run_stage(args: argparse.Namespace, stage: str) -> None:
    from polisyos.academic.batch.dedup import merge_and_dedup
    from polisyos.academic.batch.embedder import run_embed
    from polisyos.academic.batch.graph_builder import run_graph_index, run_graph_load
    from polisyos.academic.batch.harvester import harvest_all
    from polisyos.academic.batch.parser import parse_raw_sources
    from polisyos.academic.batch.pipeline import run_academic_pipeline
    from polisyos.academic.batch.publish import run_publish
    from polisyos.academic.batch.qc import run_qc
    from polisyos.academic.batch.resolve_extract import run_resolve_extract
    from polisyos.academic.batch.topic_select import run_topic_select

    stage_name = _normalize_stage_name(stage)
    if stage_name == "run":
        cfg = _build_config(args, stages=_parse_stages(getattr(args, "stages", None)))
        stats = await run_academic_pipeline(cfg, thermal=bool(getattr(args, "thermal", False)))
        print(f"Done in {stats.elapsed_seconds:.1f}s")
        for name, duration in sorted(stats.stage_times.items()):
            print(f"  {name}: {duration:.1f}s")
        return

    cfg = _build_config(args, stages=frozenset({stage_name}))
    if stage_name == "topic_select":
        out = await run_topic_select(cfg)
        print(f"Topics: {out.get('topics', 0)}")
        print(f"Selected rows: {out.get('selected_rows', 0)}")
        print(f"Unique works: {out.get('selected_unique', 0)}")
    elif stage_name == "harvest":
        out = await harvest_all(cfg)
        print(f"Harvested groups: {len(out)}")
        print(f"Records: {sum(len(v) for v in out.values())}")
    elif stage_name == "parse":
        counts = parse_raw_sources(cfg)
        print(f"Parsed sources: {len(counts)}")
        print(f"Records: {sum(counts.values())}")
    elif stage_name == "resolve_extract":
        resolve_stats = await run_resolve_extract(cfg)
        print(json_dumps_pretty(resolve_stats))
    elif stage_name == "merge_dedup":
        stats = merge_and_dedup(cfg)
        print(f"Merged works: {stats.get('merged_records', 0)}")
        print(f"Duplicates: {stats.get('duplicates', 0)}")
        print(f"Topic links: {stats.get('topic_links', 0)}")
    elif stage_name == "graph_load":
        gstats = run_graph_load(cfg)
        print(
            "Graph loaded: "
            f"works={gstats.works} estimates={gstats.estimates} claims={gstats.claims} "
            f"topic_selections={gstats.topic_selections}"
        )
    elif stage_name == "graph_index":
        run_graph_index(cfg)
        print("Graph indexes created")
    elif stage_name == "embed":
        count = run_embed(cfg, thermal=bool(getattr(args, "thermal", False)))
        print(f"Embedded works: {count}")
    elif stage_name == "qc":
        report = run_qc(cfg, fail_fast=bool(getattr(args, "fail_fast", True)))
        print(f"QC passed: {report.passed}")
        print(f"QC report: {cfg.qc_report_path}")
    elif stage_name == "publish":
        manifest = run_publish(cfg)
        print(f"Publish manifest: {manifest}")
    else:
        raise ValueError(f"Unsupported stage command: {stage}")


def _cmd_stats(args: argparse.Namespace) -> None:
    import duckdb

    con = duckdb.connect(str(args.db_path), read_only=True)
    try:
        works = con.execute("SELECT count(*) FROM ac_works").fetchone()[0]
        estimates = con.execute("SELECT count(*) FROM ac_parameter_estimates").fetchone()[0]
        claims = con.execute("SELECT count(*) FROM ac_causal_claims").fetchone()[0]
        topic_links = con.execute("SELECT count(*) FROM ac_topic_selections").fetchone()[0]
    finally:
        con.close()

    print(f"Works: {works}")
    print(f"Estimates: {estimates}")
    print(f"Claims: {claims}")
    print(f"Topic selections: {topic_links}")


def _cmd_search(args: argparse.Namespace) -> None:
    from polisyos.academic.knowledge.search import ScholarKnowledgeGraph

    graph = ScholarKnowledgeGraph(db_path=Path(args.db_path), index_dir=Path(args.db_path).parent)
    try:
        rows = graph.find_relevant_works(args.query, top_k=args.top_k)
    finally:
        graph.close()

    if not rows:
        print("No results")
        return
    for i, row in enumerate(rows, start=1):
        print(f"[{i}] {row.title} ({row.year})")
        print(f"    trust={row.trust_score:.3f} cited={row.cited_by_count} similarity={row.similarity:.3f}")


def _cmd_prior(args: argparse.Namespace) -> None:
    from polisyos.academic.knowledge.search import ScholarKnowledgeGraph

    graph = ScholarKnowledgeGraph(db_path=Path(args.db_path), index_dir=Path(args.db_path).parent)
    try:
        prior = graph.get_parameter_prior(args.variable, domain=args.domain, country=args.country)
    finally:
        graph.close()

    if prior is None:
        print("No prior found")
        return
    print(prior.model_dump_json(indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Academic staged CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--snapshot-root", required=True)
    common.add_argument("--topics-dir", default="/Users/deniskopylov/polisyos/relevant_topics_domain_files")
    common.add_argument("--topic-limit", type=int, default=None)
    common.add_argument("--target-per-topic", type=int, default=150)
    common.add_argument("--pass-name", default="pass1_abstract")
    common.add_argument("--run-id", default="")
    common.add_argument("--openalex-email", default="")
    common.add_argument("--openalex-max-rps", type=int, default=10)
    common.add_argument("--openalex-max-concurrent", type=int, default=5)
    common.add_argument("--openalex-timeout", type=int, default=60)
    common.add_argument("--openalex-max-retries", type=int, default=5)
    common.add_argument("--openalex-backoff-seconds", type=float, default=5.0)
    common.add_argument("--openalex-per-page", type=int, default=200)

    common.add_argument("--gonka-api-key", default="")
    common.add_argument("--gonka-api-keys", default="")
    common.add_argument("--gonka-base-url", default="https://api.gonkagate.com/v1")
    common.add_argument("--llm-model", default="qwen/qwen3-235b-a22b-instruct-2507-fp8")
    common.add_argument("--llm-temperature", type=float, default=0.1)
    common.add_argument("--max-concurrent-llm", type=int, default=12)
    common.add_argument("--llm-rate-limit-rps", type=float, default=5.0)
    common.add_argument("--llm-max-retries", type=int, default=6)
    common.add_argument("--article-screening-model", default="qwen/qwen3-32b")
    common.add_argument("--article-extraction-model", default="qwen/qwen3-235b-a22b-instruct-2507-fp8")
    common.add_argument("--article-max-concurrent-llm", type=int, default=20)
    common.add_argument("--article-rate-limit-rps", type=float, default=8.0)
    common.add_argument("--article-max-retries", type=int, default=7)
    common.add_argument("--article-fulltext-timeout-seconds", type=int, default=20)
    common.add_argument("--article-target-fulltext-per-topic", type=int, default=50)
    common.add_argument("--article-prefetch-candidates-per-topic", type=int, default=150)
    common.add_argument("--article-max-completion-tokens", type=int, default=8192)
    common.add_argument("--article-evidence-bundle-sentence-budget", type=int, default=28)
    common.add_argument("--article-connect-timeout-seconds", type=int, default=15)
    common.add_argument("--article-read-timeout-seconds", type=int, default=120)
    common.add_argument("--article-total-timeout-seconds", type=int, default=150)
    common.add_argument("--fulltext-max-concurrent-fetches", type=int, default=24)
    common.add_argument("--fulltext-acquisition-mode", default="v3_legacy", choices=["v3_legacy", "v7_http_metadata"])
    common.add_argument(
        "--fulltext-metadata-resolvers-enabled",
        dest="fulltext_metadata_resolvers_enabled",
        action="store_true",
    )
    common.add_argument(
        "--no-fulltext-metadata-resolvers-enabled",
        dest="fulltext_metadata_resolvers_enabled",
        action="store_false",
    )
    common.set_defaults(fulltext_metadata_resolvers_enabled=True)
    common.add_argument("--fulltext-unpaywall-email", default="")
    common.add_argument("--fulltext-metadata-timeout-seconds", type=int, default=20)
    common.add_argument("--fulltext-max-candidate-urls-per-work", type=int, default=20)
    common.add_argument("--fulltext-min-usable-chars", type=int, default=1500)
    common.add_argument("--fulltext-min-soft-usable-chars", type=int, default=700)
    common.add_argument(
        "--fulltext-soft-usable-requires-section-cues",
        dest="fulltext_soft_usable_requires_section_cues",
        action="store_true",
    )
    common.add_argument(
        "--no-fulltext-soft-usable-requires-section-cues",
        dest="fulltext_soft_usable_requires_section_cues",
        action="store_false",
    )
    common.set_defaults(fulltext_soft_usable_requires_section_cues=True)
    common.add_argument("--provider-circuit-breaker-failures", type=int, default=5)
    common.add_argument("--provider-circuit-breaker-reset-seconds", type=int, default=60)

    common.add_argument("--llm-gate-enabled", dest="llm_gate_enabled", action="store_true")
    common.add_argument("--no-llm-gate-enabled", dest="llm_gate_enabled", action="store_false")
    common.set_defaults(llm_gate_enabled=True)
    common.add_argument("--llm-gate-mode", default="balanced", choices=["off", "balanced", "aggressive"])
    common.add_argument("--llm-gate-threshold", type=float, default=0.58)
    common.add_argument("--llm-gate-max-share", type=float, default=0.20)
    common.add_argument("--llm-gate-min-score-force-llm", type=float, default=0.80)
    common.add_argument("--llm-gate-audit-sample-rate", type=float, default=0.02)
    common.add_argument("--llm-gate-audit-max-miss-rate-pct", type=float, default=3.0)
    common.add_argument("--llm-gate-auto-conf-threshold", type=float, default=0.85)
    common.add_argument(
        "--llm-gate-circuit-breaker-enabled",
        dest="llm_gate_circuit_breaker_enabled",
        action="store_true",
    )
    common.add_argument(
        "--no-llm-gate-circuit-breaker-enabled",
        dest="llm_gate_circuit_breaker_enabled",
        action="store_false",
    )
    common.set_defaults(llm_gate_circuit_breaker_enabled=True)

    common.add_argument("--resume", action="store_true")

    sub.add_parser("topic-select", parents=[common], help="Select topic works from OpenAlex")
    sub.add_parser("harvest", parents=[common], help="Harvest OpenAlex snapshots")
    sub.add_parser("parse", parents=[common], help="Parse raw snapshots")
    sub.add_parser("resolve-extract", parents=[common], help="Streaming fulltext-first one-call extraction")
    sub.add_parser("merge-dedup", parents=[common], help="Merge parsed records and dedup by work_id")
    sub.add_parser("graph-load", parents=[common], help="Load merged works into DuckDB")
    sub.add_parser("graph-index", parents=[common], help="Build DuckDB indexes")

    embed = sub.add_parser("embed", parents=[common], help="Build local embeddings and HNSW")
    embed.add_argument("--thermal", action="store_true")

    qc = sub.add_parser("qc", parents=[common], help="Run QC checks")
    qc.add_argument("--fail-fast", dest="fail_fast", action="store_true")
    qc.add_argument("--no-fail-fast", dest="fail_fast", action="store_false")
    qc.set_defaults(fail_fast=True)

    sub.add_parser("publish", parents=[common], help="Write publish manifest")

    run = sub.add_parser("run", parents=[common], help="Thin wrapper over staged commands")
    run.add_argument("--stages", default=None, help="Comma-separated stages")
    run.add_argument("--thermal", action="store_true")
    run.add_argument("--fail-fast", dest="fail_fast", action="store_true")
    run.add_argument("--no-fail-fast", dest="fail_fast", action="store_false")
    run.set_defaults(fail_fast=True)

    stats = sub.add_parser("stats", help="Show DB counts")
    stats.add_argument("--db-path", required=True)

    search = sub.add_parser("search", help="Search works")
    search.add_argument("--db-path", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--top-k", type=int, default=10)

    prior = sub.add_parser("prior", help="Compute parameter prior")
    prior.add_argument("--db-path", required=True)
    prior.add_argument("--variable", required=True)
    prior.add_argument("--domain", default=None)
    prior.add_argument("--country", default=None)

    return parser


def json_dumps_pretty(payload: dict) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = _build_parser()
    args = parser.parse_args()

    if args.command in {
        "topic-select",
        "harvest",
        "parse",
        "resolve-extract",
        "merge-dedup",
        "graph-load",
        "graph-index",
        "embed",
        "qc",
        "publish",
        "run",
    }:
        asyncio.run(_run_stage(args, args.command))
        return

    if args.command == "stats":
        _cmd_stats(args)
        return
    if args.command == "search":
        _cmd_search(args)
        return
    if args.command == "prior":
        _cmd_prior(args)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
