from __future__ import annotations

import json
from pathlib import Path

import duckdb

from polisyos.data_forge.domains.legal.batch.publish import run_publish


def test_run_publish_writes_consumer_readiness_manifest(tmp_path) -> None:
    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    with duckdb.connect(str(db_path)) as con:
        con.execute("CREATE TABLE lex_fact_candidates (fact_id VARCHAR)")
        con.execute("CREATE TABLE lex_fact_grounded (fact_id VARCHAR)")
        con.execute("CREATE TABLE lex_normative_facts (fact_id VARCHAR)")
        con.execute("CREATE TABLE lex_reference_edges (reference_edge_id VARCHAR)")
        con.execute("CREATE TABLE lex_doc_versions (version_row_id VARCHAR)")
        con.execute("INSERT INTO lex_fact_candidates VALUES ('f1')")
        con.execute("INSERT INTO lex_fact_grounded VALUES ('f1')")
        con.execute("INSERT INTO lex_normative_facts VALUES ('f1')")
        con.execute("INSERT INTO lex_reference_edges VALUES ('r1')")
        con.execute("INSERT INTO lex_doc_versions VALUES ('v1')")

    (tmp_path / "qc_report.json").write_text(
        json.dumps(
            {
                "passed": True,
                "metrics": {
                    "doc_family_breakdown": {
                        "law": {"empty_statement_rows_pct": 5.0},
                    },
                    "llm_gap_fill_sent_total": 12,
                    "llm_gap_fill_added_statements_total": 7,
                    "baseline_vs_gap_fill_added_statements_total": 7,
                    "top_gap_fill_subtypes": [
                        {"legal_unit_subtype": "core_normative_clause", "count": 8}
                    ],
                },
                "checks": [],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "benchmark_report.json").write_text(
        json.dumps(
            {
                "metrics": {
                    "benchmark_search_cases_total": 4,
                    "benchmark_search_top5_relevance_pct": 100.0,
                    "benchmark_constraints_domains_total": 2,
                    "benchmark_constraints_ready_pct": 100.0,
                    "benchmark_cross_graph_cases_total": 2,
                    "benchmark_cross_graph_non_unknown_pct": 100.0,
                },
                "readiness": {"passed": True, "failed_checks": []},
            }
        ),
        encoding="utf-8",
    )

    manifest_path = run_publish(tmp_path, require_embeddings=False)
    assert manifest_path.exists()

    readiness_path = tmp_path / "publish" / "consumer_readiness.json"
    assert readiness_path.exists()
    payload = json.loads(readiness_path.read_text(encoding="utf-8"))
    assert payload["readiness"]["consumer_ready"] is True
    assert payload["release_readiness"]["release_ready"] is False
    assert (
        "legal_source_relation_verification_not_established"
        in payload["release_readiness"]["release_failed_checks"]
    )
    assert payload["table_counts"]["lex_normative_facts"] == 1
    assert payload["quality_summary"]["llm_gap_fill_metrics"]["llm_gap_fill_sent_total"] == 12
    assert (
        payload["quality_summary"]["top_gap_fill_subtypes"][0]["legal_unit_subtype"]
        == "core_normative_clause"
    )


def test_run_publish_ignores_optional_embedding_failures_for_smoke(tmp_path) -> None:
    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    with duckdb.connect(str(db_path)) as con:
        con.execute("CREATE TABLE lex_fact_candidates (fact_id VARCHAR)")
        con.execute("CREATE TABLE lex_fact_grounded (fact_id VARCHAR)")
        con.execute("CREATE TABLE lex_normative_facts (fact_id VARCHAR)")
        con.execute("CREATE TABLE lex_reference_edges (reference_edge_id VARCHAR)")
        con.execute("CREATE TABLE lex_doc_versions (version_row_id VARCHAR)")
        con.execute("INSERT INTO lex_fact_candidates VALUES ('f1')")
        con.execute("INSERT INTO lex_fact_grounded VALUES ('f1')")
        con.execute("INSERT INTO lex_normative_facts VALUES ('f1')")
        con.execute("INSERT INTO lex_reference_edges VALUES ('r1')")
        con.execute("INSERT INTO lex_doc_versions VALUES ('v1')")

    (tmp_path / "qc_report.json").write_text(
        json.dumps(
            {
                "passed": False,
                "metrics": {
                    "qc_failed_checks": ["embedding_artifacts_present"],
                    "release_failed_checks": ["embedding_artifacts_present"],
                    "quality_gate_passed": True,
                },
                "checks": [
                    {
                        "name": "embedding_artifacts_present",
                        "passed": False,
                        "severity": "warning",
                        "status": "failed",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "benchmark_report.json").write_text(
        json.dumps({"metrics": {}, "readiness": {"passed": True, "failed_checks": []}}),
        encoding="utf-8",
    )

    run_publish(tmp_path, require_embeddings=False)
    payload = json.loads(
        (tmp_path / "publish" / "consumer_readiness.json").read_text(encoding="utf-8")
    )
    assert payload["release_readiness"]["qc_failed_checks"] == []
    assert payload["release_readiness"]["release_failed_checks"] == [
        "legal_source_relation_verification_not_established"
    ]
    assert payload["release_readiness"]["qc_passed"] is True
    assert payload["release_readiness"]["release_ready"] is False


def test_run_publish_withholds_stale_legal_authority_artifacts(tmp_path) -> None:
    db_path = tmp_path / "lex_knowledge_graph.duckdb"
    with duckdb.connect(str(db_path)) as con:
        con.execute("CREATE TABLE lex_fact_candidates (fact_id VARCHAR)")
        con.execute("CREATE TABLE lex_fact_grounded (fact_id VARCHAR)")
        con.execute("CREATE TABLE lex_normative_facts (fact_id VARCHAR)")
        con.execute("CREATE TABLE lex_normative_ready_facts (fact_id VARCHAR)")
        con.execute("INSERT INTO lex_fact_candidates VALUES ('candidate-1')")
        con.execute("INSERT INTO lex_fact_grounded VALUES ('candidate-1')")
        con.execute("INSERT INTO lex_normative_facts VALUES ('unverified-1')")
        con.execute("INSERT INTO lex_normative_ready_facts VALUES ('unverified-1')")

    stale_artifacts = {
        "claim_exports/normative_claims.jsonl": b'{"claim_id":"stale"}\n',
        "claim_exports/normative_claims_summary.json": b'{"status":"ok"}',
        "claim_exports/normative_claim_sets_summary.json": b'{"status":"ok"}',
    }
    for relative_path, content in stale_artifacts.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    (tmp_path / "qc_report.json").write_text(
        json.dumps({"passed": True, "metrics": {"quality_gate_passed": True}}),
        encoding="utf-8",
    )
    (tmp_path / "benchmark_report.json").write_text(
        json.dumps({"readiness": {"passed": True, "failed_checks": []}}),
        encoding="utf-8",
    )

    manifest_path = run_publish(tmp_path, require_embeddings=False)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    readiness = json.loads(
        (tmp_path / "publish" / "consumer_readiness.json").read_text(encoding="utf-8")
    )
    published_paths = {Path(artifact["path"]).resolve() for artifact in manifest["artifacts"]}
    withheld_paths = {(tmp_path / path).resolve() for path in stale_artifacts}

    assert not published_paths.intersection(withheld_paths)
    assert all(
        (tmp_path / path).read_bytes() == content for path, content in stale_artifacts.items()
    )
    assert readiness["readiness"]["candidate_layer_ready"] is True
    assert readiness["readiness"]["normative_layer_ready"] is False
    assert readiness["release_readiness"]["release_ready"] is False
    assert readiness["legal_relation_refusal"] == {
        "code": "legal_source_relation_verification_not_established",
        "status": "verification_missing",
    }
