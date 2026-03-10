from __future__ import annotations

import json

import duckdb

from polisyos.batch_common.manifest import write_raw_manifest
from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.batch.qc import run_qc


def test_academic_qc_passes_minimal_snapshot(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")

    raw_dir = config.topic_raw_root("T1", "minimum_wage") / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"W1"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="openalex",
        endpoint="https://api.openalex.org/works",
        payload_path=payload,
        count=1,
    )

    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config.merged_records_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": "W1", "abstract": "Some abstract", "estimates": [{"value": 0.2}]}) + "\n")
    with open(config.selected_topic_works_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"topic_id": "T1", "work_id": "W1"}) + "\n")

    con = duckdb.connect(str(config.db_path))
    con.execute("CREATE TABLE IF NOT EXISTS ac_works (full_text_url VARCHAR, is_oa BOOLEAN)")
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(config, fail_fast=True)
    assert report.passed is True
    assert config.qc_report_path.exists()


def test_academic_qc_empty_abstract_is_warning_only(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")

    raw_dir = config.topic_raw_root("T1", "minimum_wage") / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"W1"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="openalex",
        endpoint="https://api.openalex.org/works",
        payload_path=payload,
        count=1,
    )

    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    config.merged_records_path.write_text('{"id":"W1","abstract":"","estimates":[]}\n', encoding="utf-8")
    with open(config.selected_topic_works_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"topic_id": "T1", "work_id": "W1"}) + "\n")

    report = run_qc(config, fail_fast=True)

    empty_check = next(check for check in report.checks if check.name == "empty_abstract_pct")
    assert empty_check.severity == "warning"
    assert report.passed is True


def test_academic_qc_fail_fast_on_manifest_mismatch(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")

    raw_dir = config.topic_raw_root("T1", "minimum_wage") / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"W1"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="openalex",
        endpoint="https://api.openalex.org/works",
        payload_path=payload,
        count=2,
    )

    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    config.merged_records_path.write_text('{"id":"W1","abstract":"x","estimates":[]}\n', encoding="utf-8")
    with open(config.selected_topic_works_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"topic_id": "T1", "work_id": "W1"}) + "\n")

    try:
        run_qc(config, fail_fast=True)
    except RuntimeError as exc:
        assert "manifest_count_parity" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for fail-fast QC")


def test_academic_qc_strict_phase0_makes_0d_checks_blocking(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")

    raw_dir = config.topic_raw_root("T1", "minimum_wage") / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"W1"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="openalex",
        endpoint="https://api.openalex.org/works",
        payload_path=payload,
        count=1,
    )

    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config.merged_records_path, "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "id": "W1",
                    "abstract": "Some abstract",
                    "extraction_mode": "resolve_extract",
                    "estimates": [{"value": 0.2}],
                    "causal_claims": [{"cause": "gdp_growth", "effect": "employment"}],
                }
            )
            + "\n"
        )
    with open(config.selected_topic_works_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"topic_id": "T1", "work_id": "W1"}) + "\n")

    con = duckdb.connect(str(config.db_path))
    con.execute("CREATE TABLE IF NOT EXISTS ac_works (full_text_url VARCHAR, is_oa BOOLEAN)")
    con.execute("CHECKPOINT")
    con.close()

    try:
        run_qc(config, fail_fast=True, strict_phase0=True)
    except RuntimeError as exc:
        assert "resolve_extract_count_50" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for strict phase-0 QC gates")


def test_academic_qc_tracks_adjudication_publishability_metrics(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")

    raw_dir = config.topic_raw_root("T1", "minimum_wage") / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"W1"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="openalex",
        endpoint="https://api.openalex.org/works",
        payload_path=payload,
        count=1,
    )

    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config.merged_records_path, "w", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "id": "W1",
                    "abstract": "Some abstract",
                    "extraction_mode": "resolve_extract",
                    "metadata": {"source_basis": "fulltext"},
                    "estimates": [{"value": 0.2}],
                    "causal_claims": [
                        {
                            "claim_id": "c1",
                            "cause": "tax_rate",
                            "effect": "employment",
                            "supporting_spans": [{"section": "results", "text": "Higher tax rates reduce employment."}],
                        }
                    ],
                }
            )
            + "\n"
        )
    with open(config.selected_topic_works_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"topic_id": "T1", "work_id": "W1"}) + "\n")
    config.raw_claim_candidates_path.write_text(
        json.dumps(
            {
                "claim_id": "c1",
                "work_id": "W1",
                "cause_text": "tax_rate",
                "effect_text": "employment",
                "source_basis": "fulltext",
                "claim_type": "causal_claim",
                "design_family_hint": "did",
                "design_quality_tier": 1,
                "publish_to_graph": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    config.published_claims_path.write_text(
        json.dumps(
            {
                "claim_id": "c1",
                "work_id": "W1",
                "cause_text": "tax_rate",
                "effect_text": "employment",
                "source_basis": "fulltext",
                "claim_type": "causal_claim",
                "design_family_hint": "did",
                "design_quality_tier": 1,
                "publish_to_graph": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    con = duckdb.connect(str(config.db_path))
    con.execute("CREATE TABLE IF NOT EXISTS ac_works (full_text_url VARCHAR, is_oa BOOLEAN)")
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(config, fail_fast=False)
    assert report.metrics["supporting_span_coverage_pct"] == 100.0
    assert report.metrics["fulltext_publishable_share_pct"] == 100.0
    assert report.metrics["design_tier_distribution"] == {"1": 1}
    assert report.metrics["published_claims_by_design_tier"] == {"1": 1}
    assert report.metrics["published_tier4_share_pct"] == 0.0


def test_academic_qc_warns_when_published_tier4_share_is_high(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")

    raw_dir = config.topic_raw_root("T1", "minimum_wage") / "20260218T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_text('{"id":"W1"}\n', encoding="utf-8")
    write_raw_manifest(
        manifest_path=raw_dir / "manifest.json",
        source="openalex",
        endpoint="https://api.openalex.org/works",
        payload_path=payload,
        count=1,
    )

    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    config.merged_records_path.write_text(
        json.dumps({"id": "W1", "abstract": "Some abstract", "extraction_mode": "resolve_extract", "causal_claims": []}) + "\n",
        encoding="utf-8",
    )
    config.selected_topic_works_path.write_text(json.dumps({"topic_id": "T1", "work_id": "W1"}) + "\n", encoding="utf-8")
    config.raw_claim_candidates_path.write_text(
        json.dumps({"claim_id": "c1", "design_quality_tier": 4, "source_basis": "fulltext"}) + "\n",
        encoding="utf-8",
    )
    config.published_claims_path.write_text(
        json.dumps({"claim_id": "c1", "design_quality_tier": 4, "source_basis": "fulltext"}) + "\n",
        encoding="utf-8",
    )

    con = duckdb.connect(str(config.db_path))
    con.execute("CREATE TABLE IF NOT EXISTS ac_works (full_text_url VARCHAR, is_oa BOOLEAN)")
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(config, fail_fast=False)
    check = next(item for item in report.checks if item.name == "published_tier4_share_pct")
    assert check.passed is False
    assert report.metrics["published_tier4_share_pct"] == 100.0


def test_academic_qc_tracks_v7_acquisition_metrics(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")

    config.fulltext_fetch_log_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "work_id": "W1",
                        "attempt_kind": "metadata",
                        "candidate_priority": 5,
                        "candidate_url": "https://api.unpaywall.org/v2/10.1%2Fa",
                        "source_kind": "metadata_unpaywall",
                        "http_status": 200,
                        "fetch_error_class": "",
                        "latency_ms": 10.0,
                        "redirected_to": "",
                        "discovered_pdf_count": 1,
                        "discovered_canonical_count": 0,
                        "text_chars": 0,
                        "usable_text": False,
                        "final_for_work": False,
                    }
                ),
                json.dumps(
                    {
                        "work_id": "W2",
                        "attempt_kind": "seed",
                        "candidate_priority": 2,
                        "candidate_url": "https://doi.org/example",
                        "source_kind": "openalex_landing_page",
                        "http_status": 200,
                        "fetch_error_class": "redirect_placeholder",
                        "latency_ms": 11.0,
                        "redirected_to": "",
                        "discovered_pdf_count": 0,
                        "discovered_canonical_count": 1,
                        "text_chars": 12,
                        "usable_text": False,
                        "final_for_work": False,
                    }
                ),
                json.dumps(
                    {
                        "work_id": "W3",
                        "attempt_kind": "seed",
                        "candidate_priority": 2,
                        "candidate_url": "https://publisher.example",
                        "source_kind": "publisher_html",
                        "http_status": 403,
                        "fetch_error_class": "publisher_blocked_403",
                        "latency_ms": 8.0,
                        "redirected_to": "",
                        "discovered_pdf_count": 0,
                        "discovered_canonical_count": 0,
                        "text_chars": 0,
                        "usable_text": False,
                        "final_for_work": False,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config.fulltext_resolved_path.write_text(
        "\n".join(
            [
                json.dumps({"work_id": "W1", "source_basis": "fulltext", "source_kind": "fulltext_pdf"}),
                json.dumps({"work_id": "W2", "source_basis": "abstract_only", "source_kind": "abstract_fallback"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = run_qc(config, fail_fast=False)

    assert report.metrics["usable_fulltext_resolved"] == 1
    assert report.metrics["recoverable_landing_pages"] == 1
    assert report.metrics["metadata_resolver_hit_rate"] == 100.0
    assert report.metrics["metadata_pdf_recovery_rate"] == 100.0
    assert report.metrics["redirect_placeholder_recovery_rate"] == 0.0
    assert report.metrics["publisher_403_rate"] > 0.0
    assert report.metrics["final_abstract_fallback_rate"] == 50.0
