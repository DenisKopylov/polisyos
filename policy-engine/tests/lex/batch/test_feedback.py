from __future__ import annotations

import json

from polisyos.lex.batch.feedback import build_feedback_queue_rows, write_candidate_patterns


def test_build_feedback_queue_rows_clusters_audit_misses() -> None:
    rows = build_feedback_queue_rows(
        [
            {
                "miss": True,
                "doc_id": "doc-1",
                "provision_anchor": "article:1",
                "quality_family": "law",
                "legal_unit_subtype": "core_normative_clause",
                "route_class": "deterministic_then_llm_retry",
                "gate_reason_codes": ["retry_route_priority"],
                "llm_count": 2,
                "baseline_count": 0,
                "miss_categories": ["reference", "threshold"],
                "empty_spo_only": True,
                "reference_bearing": True,
                "threshold_bearing": True,
            },
            {
                "miss": False,
                "doc_id": "doc-2",
                "provision_anchor": "article:2",
            },
        ]
    )

    assert len(rows) == 1
    assert rows[0]["cluster_key"] == "law:core_normative_clause:reference,threshold"
    assert rows[0]["suggestion_family"] == "reference"
    assert rows[0]["llm_delta"] == 2


def test_write_candidate_patterns_emits_clustered_feedback_payload(tmp_path) -> None:
    out_path = write_candidate_patterns(
        feedback_rows=[
            {
                "doc_id": "doc-1",
                "provision_anchor": "article:1",
                "cluster_key": "law:core_normative_clause:reference",
                "suggestion_family": "reference",
                "miss_categories": ["reference"],
            },
            {
                "doc_id": "doc-2",
                "provision_anchor": "article:3",
                "cluster_key": "law:core_normative_clause:reference",
                "suggestion_family": "reference",
                "miss_categories": ["reference"],
            },
        ],
        output_dir=tmp_path / "patterns" / "ua" / "candidates",
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["generated_from_feedback"] is True
    assert payload["clusters"][0]["cluster_key"] == "law:core_normative_clause:reference"
    assert payload["clusters"][0]["count"] == 2
