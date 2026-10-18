from __future__ import annotations

import json

import duckdb
import pytest

from polisyos.data_forge.domains.academic.batch.benchmark import run_benchmark
from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
from polisyos.data_forge.domains.academic.batch.qc import _finite_json_number, run_qc
from polisyos.data_forge.domains.academic.knowledge.skg_store import ensure_skg_schema
from polisyos.data_forge.domains.academic.openalex.selector import SelectedTopicWork
from polisyos.data_forge.kernel.pipeline.manifests import (
    write_raw_manifest,
    write_stage_manifest,
)


def test_academic_qc_passes_minimal_snapshot(tmp_path) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"qc"}),
    )

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
            json.dumps({"id": "W1", "abstract": "Some abstract", "estimates": [{"value": 0.2}]})
            + "\n"
        )
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
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"qc"}),
    )

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
        '{"id":"W1","abstract":"","estimates":[]}\n', encoding="utf-8"
    )
    with open(config.selected_topic_works_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"topic_id": "T1", "work_id": "W1"}) + "\n")

    report = run_qc(config, fail_fast=True)

    empty_check = next(check for check in report.checks if check.name == "empty_abstract_pct")
    assert empty_check.severity == "warning"
    assert report.passed is True


def test_academic_qc_fail_fast_on_manifest_mismatch(tmp_path) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"qc"}),
    )

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
    config.merged_records_path.write_text(
        '{"id":"W1","abstract":"x","estimates":[]}\n', encoding="utf-8"
    )
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


def test_academic_qc_canonical_metric_requires_approved_registry_names(
    tmp_path,
) -> None:
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
                    "causal_claims": [
                        {
                            "cause": "teacher_coaching_program",
                            "effect": "student_learning",
                        }
                    ],
                }
            )
            + "\n"
        )
    with open(config.selected_topic_works_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"topic_id": "T1", "work_id": "W1"}) + "\n")

    con = duckdb.connect(str(config.db_path))
    con.execute("CREATE TABLE IF NOT EXISTS ac_works (full_text_url VARCHAR, is_oa BOOLEAN)")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ac_skg_canonization_cache (
            raw_name VARCHAR PRIMARY KEY,
            canonical_name VARCHAR NOT NULL,
            approved BOOLEAN DEFAULT FALSE
        )
        """
    )
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(config, fail_fast=False)
    assert report.metrics["canonical_claim_variable_pct"] == 0.0


def test_academic_qc_uses_runtime_demanded_canonical_rate_as_blocking_metric(
    tmp_path,
) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")

    raw_dir = config.topic_raw_root("T1", "teacher_coaching") / "20260218T000000Z"
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
        json.dumps(
            {
                "id": "W1",
                "abstract": "Some abstract",
                "extraction_mode": "resolve_extract",
                "causal_claims": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    config.selected_topic_works_path.write_text(
        json.dumps({"topic_id": "T1", "work_id": "W1"}) + "\n", encoding="utf-8"
    )
    config.edge_synthesis_report_path.write_text(
        json.dumps({"canonization": {"resolution_rate_pct": 0.0}}, ensure_ascii=False),
        encoding="utf-8",
    )
    config.benchmark_report_path.write_text(
        json.dumps(
            {
                "kind": "academic_benchmark",
                "metrics": {
                    "runtime_demanded_canonical_resolution_rate_pct": 100.0,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    con = duckdb.connect(str(config.db_path))
    con.execute("CREATE TABLE IF NOT EXISTS ac_works (full_text_url VARCHAR, is_oa BOOLEAN)")
    con.execute("CHECKPOINT")
    con.close()

    report = run_qc(config, fail_fast=False)

    assert report.metrics["canonical_resolution_rate_pct"] == 100.0
    assert report.metrics["runtime_demanded_canonical_resolution_rate_pct"] == 100.0
    assert report.metrics["global_canonical_resolution_rate_pct"] == 0.0
    runtime_check = next(
        item for item in report.checks if item.name == "canonical_resolution_rate_pct"
    )
    global_check = next(
        item for item in report.checks if item.name == "global_canonical_resolution_rate_pct"
    )
    assert runtime_check.passed is True
    assert global_check.passed is False


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
                            "supporting_spans": [
                                {
                                    "section": "results",
                                    "text": "Higher tax rates reduce employment.",
                                }
                            ],
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
        json.dumps(
            {
                "id": "W1",
                "abstract": "Some abstract",
                "extraction_mode": "resolve_extract",
                "causal_claims": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    config.selected_topic_works_path.write_text(
        json.dumps({"topic_id": "T1", "work_id": "W1"}) + "\n", encoding="utf-8"
    )
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
                json.dumps(
                    {
                        "work_id": "W1",
                        "source_basis": "fulltext",
                        "source_kind": "fulltext_pdf",
                    }
                ),
                json.dumps(
                    {
                        "work_id": "W2",
                        "source_basis": "abstract_only",
                        "source_kind": "abstract_fallback",
                    }
                ),
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


def test_academic_qc_prefers_selected_global_works_for_unique_budget_metrics(
    tmp_path,
) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.selected_unique_budget = 2

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
        '{"id":"W1","abstract":"x","estimates":[]}\n', encoding="utf-8"
    )
    config.selected_topic_works_path.write_text(
        "\n".join(
            [
                json.dumps({"topic_id": "T1", "work_id": "W1"}),
                json.dumps({"topic_id": "T2", "work_id": "W1"}),
                json.dumps({"topic_id": "T2", "work_id": "W2"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config.selected_global_works_path.write_text(
        "\n".join(
            [
                json.dumps({"work_id": "W1", "work": {"id": "W1"}}),
                json.dumps({"work_id": "W2", "work": {"id": "W2"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = run_qc(config, fail_fast=False)

    assert report.metrics["selected_rows"] == 3
    assert report.metrics["selected_topic_unique_works"] == 2
    assert report.metrics["selected_global_rows"] == 2
    assert report.metrics["selected_global_unique_works"] == 2
    assert report.metrics["selected_unique_works"] == 2
    budget_check = next(item for item in report.checks if item.name == "selected_unique_budget_hit")
    assert budget_check.passed is True
    assert budget_check.value == 2


_STRICT_JSON_BAD_MEMBER_FRAGMENTS = (
    pytest.param("nan-token", '"__qc_probe__":NaN', id="nan-token"),
    pytest.param(
        "positive-infinity-token",
        '"__qc_probe__":Infinity',
        id="positive-infinity-token",
    ),
    pytest.param(
        "negative-infinity-token",
        '"__qc_probe__":-Infinity',
        id="negative-infinity-token",
    ),
    pytest.param("decimal-overflow", '"__qc_probe__":1e999', id="decimal-overflow"),
    pytest.param(
        "nested-nan-token",
        '"__qc_probe__":{"values":[NaN]}',
        id="nested-nan-token",
    ),
    pytest.param(
        "nested-decimal-overflow",
        '"__qc_probe__":{"values":[1e999]}',
        id="nested-decimal-overflow",
    ),
    pytest.param(
        "duplicate-root-key",
        '"__qc_probe__":1,"__qc_probe__":2',
        id="duplicate-root-key",
    ),
    pytest.param(
        "duplicate-nested-key",
        '"__qc_probe__":{"value":1,"value":2}',
        id="duplicate-nested-key",
    ),
    pytest.param(
        "duplicate-decoded-root-key",
        '"__qc_probe__":1,"\\u005f_qc_probe__":2',
        id="duplicate-decoded-root-key",
    ),
)


def _inject_json_member_fragment(record: bytes, fragment: str) -> bytes:
    """Append a candidate member while preserving the producer-shaped base object."""
    line = record.rstrip(b"\r\n")
    if not line.startswith(b"{") or not line.endswith(b"}"):
        raise AssertionError("expected one producer-shaped JSON object")
    prefix = line[:-1]
    separator = b"" if prefix == b"{" else b","
    return prefix + separator + fragment.encode("utf-8") + b"}\n"


_QC_JSONL_INPUT_FIELDS = (
    "merged_records_path",
    "published_claims_final_path",
    "published_claims_path",
    "selected_topic_works_path",
    "selected_global_works_path",
    "resolve_extract_results_path",
    "resolve_extract_final_results_path",
    "article_extraction_cache_path",
    "raw_claim_candidates_final_path",
    "raw_claim_candidates_path",
    "fulltext_fetch_log_path",
    "fulltext_resolved_path",
    "article_extraction_results_path",
)


def _valid_selected_topic_row() -> dict[str, object]:
    """Use the actual selection producer's typed row contract in QC fixtures."""
    return SelectedTopicWork(
        run_id="qc-test",
        topic_id="T1",
        topic_display_name="Test topic",
        topic_policy_block="",
        topic_policy_subblock="",
        source_file="topics.json",
        work_id="W1",
        rank=1,
        selection_score=1.0,
        batch_origin="topic_selection",
        selected_at="2026-10-10T00:00:00Z",
        work={"id": "W1", "title": "Test work"},
    ).to_dict()


def _write_valid_graph_load_manifest(config: AcademicBatchConfig, *, failures: int = 0) -> None:
    """Write a producer-shaped graph-load manifest with an explicit counter value."""
    write_stage_manifest(
        manifest_path=config.manifests_dir / "graph_load.json",
        stage="graph_load",
        status="ok",
        metrics={"json_validation_failures": failures},
    )


def _write_valid_qc_jsonl_inputs(
    config: AcademicBatchConfig,
    *,
    target_field: str,
) -> None:
    config.raw_dir.mkdir(parents=True, exist_ok=True)
    skipped_finals = {
        "published_claims_path": "published_claims_final_path",
        "raw_claim_candidates_path": "raw_claim_candidates_final_path",
    }
    skipped_final = skipped_finals.get(target_field)
    for field in _QC_JSONL_INPUT_FIELDS:
        if field == skipped_final:
            continue
        path = getattr(config, field)
        path.parent.mkdir(parents=True, exist_ok=True)
        if field == "selected_topic_works_path":
            path.write_text(
                json.dumps(_valid_selected_topic_row()) + "\n",
                encoding="utf-8",
            )
        elif field == "selected_global_works_path":
            path.write_text('{"work_id":"W1"}\n', encoding="utf-8")
        else:
            path.write_bytes(b"{}\n")


def test_academic_qc_refuses_missing_selected_topic_identity_on_unselected_row(
    tmp_path,
) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.selected_topic_works_path.parent.mkdir(parents=True, exist_ok=True)
    supplied = (
        json.dumps(_valid_selected_topic_row()).encode("utf-8")
        + b"\n"
        + b'{"topic_id":"T2","title":"unselected but malformed"}\n'
    )
    config.selected_topic_works_path.write_bytes(supplied)

    with pytest.raises(ValueError, match=r"selected-topic work JSONL row.*work_id"):
        run_qc(config, fail_fast=False)

    assert config.selected_topic_works_path.read_bytes() == supplied
    assert not config.qc_report_path.exists()


def test_academic_qc_uses_actual_benchmark_metric_and_refuses_missing_metric(
    tmp_path,
) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.benchmark_suite_path.parent.mkdir(parents=True, exist_ok=True)
    config.benchmark_suite_path.write_text(
        json.dumps(
            {
                "suite_id": "qc-producer-consumer",
                "scenarios": [
                    {
                        "scenario_id": "unregistered-pair",
                        "title": "Unregistered pair",
                        "causal_edges": [
                            {
                                "cause": "qc_unregistered_cause_20261010",
                                "effect": "qc_unregistered_effect_20261010",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with duckdb.connect(str(config.db_path)) as con:
        ensure_skg_schema(con)
        con.execute("CREATE TABLE IF NOT EXISTS ac_works (full_text_url VARCHAR, is_oa BOOLEAN)")

    config.selected_topic_works_path.parent.mkdir(parents=True, exist_ok=True)
    config.selected_topic_works_path.write_text(
        json.dumps(_valid_selected_topic_row()) + "\n", encoding="utf-8"
    )
    config.edge_synthesis_report_path.write_text(
        json.dumps({"canonization": {"resolution_rate_pct": 100.0}}),
        encoding="utf-8",
    )

    produced = run_benchmark(config)
    produced_bytes = config.benchmark_report_path.read_bytes()
    produced_report = json.loads(produced_bytes)
    assert produced_report["kind"] == "academic_benchmark"
    produced_rate = produced.metrics["runtime_demanded_canonical_resolution_rate_pct"]
    assert (
        produced_report["metrics"]["runtime_demanded_canonical_resolution_rate_pct"]
        == produced_rate
    )
    assert float(produced_rate) < 100.0

    report = run_qc(config, fail_fast=False)
    assert report.metrics["canonical_resolution_rate_pct"] == produced_rate
    assert report.metrics["global_canonical_resolution_rate_pct"] == 100.0
    canonical_check = next(
        check for check in report.checks if check.name == "canonical_resolution_rate_pct"
    )
    assert canonical_check.value == produced_rate

    # Keep the report kind, readiness, counts, and other metrics while removing only the
    # producer-required canonical metric; an edge score of 100 must not repair that absence.
    malformed_report = dict(produced_report)
    malformed_report["metrics"] = dict(produced_report["metrics"])
    malformed_report["metrics"].pop("runtime_demanded_canonical_resolution_rate_pct")
    malformed_bytes = json.dumps(malformed_report).encode("utf-8")
    config.benchmark_report_path.write_bytes(malformed_bytes)
    config.qc_report_path.unlink()

    with pytest.raises(ValueError, match="runtime_demanded_canonical_resolution_rate_pct"):
        run_qc(config, fail_fast=False)

    assert config.benchmark_report_path.read_bytes() == malformed_bytes
    assert not config.qc_report_path.exists()


@pytest.mark.parametrize("input_field", _QC_JSONL_INPUT_FIELDS)
@pytest.mark.parametrize(
    "supplied",
    [
        pytest.param(b"[]\n", id="non-object"),
        pytest.param(b"{broken\n", id="malformed-json"),
        pytest.param(b"\xff\n", id="invalid-utf8"),
    ],
)
def test_academic_qc_refuses_malformed_rows_at_every_jsonl_input(
    tmp_path,
    input_field: str,
    supplied: bytes,
) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    _write_valid_qc_jsonl_inputs(config, target_field=input_field)
    target = getattr(config, input_field)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(supplied)

    with pytest.raises(ValueError, match=r"Malformed|must be an object"):
        run_qc(config, fail_fast=False)

    assert target.read_bytes() == supplied
    assert not config.qc_report_path.exists()


@pytest.mark.parametrize("input_field", _QC_JSONL_INPUT_FIELDS)
@pytest.mark.parametrize(("case", "fragment"), _STRICT_JSON_BAD_MEMBER_FRAGMENTS)
def test_academic_qc_decoder_rejects_nonfinite_and_ambiguous_jsonl_members(
    tmp_path,
    input_field: str,
    case: str,
    fragment: str,
) -> None:
    del case
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    _write_valid_qc_jsonl_inputs(config, target_field=input_field)
    target = getattr(config, input_field)
    producer_shaped_record = target.read_bytes()
    supplied = _inject_json_member_fragment(producer_shaped_record, fragment)
    target.write_bytes(supplied)

    with pytest.raises(ValueError, match="Malformed"):
        run_qc(config, fail_fast=False)

    assert target.read_bytes() == supplied
    assert not config.qc_report_path.exists()


def test_academic_qc_refuses_malformed_present_stage_manifest(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    manifest = config.manifests_dir / "graph_load.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest_bytes = b"{broken\n"
    manifest.write_bytes(manifest_bytes)

    with pytest.raises(ValueError, match="Malformed stage manifest"):
        run_qc(config, fail_fast=False)

    assert manifest.read_bytes() == manifest_bytes
    assert not config.qc_report_path.exists()


@pytest.mark.parametrize(
    "record",
    [
        pytest.param({"kind": "raw", "count": 1}, id="missing-payload"),
        pytest.param({"kind": "raw", "payload": "payload.jsonl"}, id="missing-count"),
        pytest.param(
            {"kind": "raw", "payload": "payload.jsonl", "count": "1"},
            id="string-count",
        ),
        pytest.param(
            {"kind": "raw", "payload": 1, "count": 1},
            id="non-string-payload",
        ),
    ],
)
def test_academic_qc_refuses_malformed_raw_manifest_fields(tmp_path, record) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    manifest = config.topic_raw_root("T1", "minimum_wage") / "20260218T000000Z" / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest_bytes = json.dumps(record).encode("utf-8")
    manifest.write_bytes(manifest_bytes)

    with pytest.raises(ValueError, match=r"raw manifest|Raw manifest"):
        run_qc(config, fail_fast=False)

    assert manifest.read_bytes() == manifest_bytes
    assert not config.qc_report_path.exists()


def test_academic_qc_marks_present_llm_gate_without_metrics_failed(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_bytes = b'{"kind":"llm_gate"}'
    config.llm_gate_manifest_path.write_bytes(manifest_bytes)

    report = run_qc(config, fail_fast=False)

    parse_check = next(check for check in report.checks if check.name == "llm_gate_manifest_parse")
    assert parse_check.passed is False
    assert parse_check.message == "Failed to parse llm_gate manifest"
    assert config.llm_gate_manifest_path.read_bytes() == manifest_bytes


def test_academic_qc_refuses_llm_gate_metrics_missing_required_outcome(
    tmp_path,
) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.raw_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "kind": "llm_gate",
        "metrics": {
            "llm_candidate_total": 1,
            "llm_sent": 0,
            "llm_saved_pct": 100.0,
        },
    }
    manifest_bytes = json.dumps(manifest).encode("utf-8")
    config.llm_gate_manifest_path.write_bytes(manifest_bytes)

    report = run_qc(config, fail_fast=False)

    parse_check = next(check for check in report.checks if check.name == "llm_gate_manifest_parse")
    assert parse_check.passed is False
    assert "audit_miss_rate_pct" not in report.metrics
    assert config.llm_gate_manifest_path.read_bytes() == manifest_bytes


_LLM_COUNT_INVALID_VALUES = (
    pytest.param(None, id="null"),
    pytest.param(False, id="boolean"),
    pytest.param("", id="empty-string"),
    pytest.param("2", id="numeric-string"),
    pytest.param(-1, id="negative-count"),
    pytest.param(1.5, id="fractional-count"),
    pytest.param(float("nan"), id="nan"),
    pytest.param(float("inf"), id="infinity"),
)
_LLM_PERCENTAGE_INVALID_VALUES = (
    pytest.param(None, id="null"),
    pytest.param(False, id="boolean"),
    pytest.param("", id="empty-string"),
    pytest.param("20", id="numeric-string"),
    pytest.param(-0.01, id="negative-percentage"),
    pytest.param(100.01, id="percentage-over-100"),
    pytest.param(float("nan"), id="nan"),
    pytest.param(float("inf"), id="infinity"),
)


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        *[
            (field, value)
            for field in ("llm_candidate_total", "llm_sent")
            for value in _LLM_COUNT_INVALID_VALUES
        ],
        *[
            (field, value)
            for field in ("llm_saved_pct", "audit_miss_rate_pct")
            for value in _LLM_PERCENTAGE_INVALID_VALUES
        ],
    ],
)
def test_academic_qc_refuses_invalid_present_llm_numeric_metrics(
    tmp_path, field: str, bad_value: object
) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"qc"}),
    )
    config.raw_dir.mkdir(parents=True, exist_ok=True)
    metrics: dict[str, object] = {
        "llm_candidate_total": 2,
        "llm_sent": 1,
        "llm_saved_pct": 50.0,
        "audit_miss_rate_pct": 0.0,
    }
    metrics[field] = bad_value
    manifest = {"kind": "llm_gate", "metrics": metrics}
    supplied = json.dumps(manifest).encode("utf-8")
    config.llm_gate_manifest_path.write_bytes(supplied)

    report = run_qc(config, fail_fast=False)

    parse_check = next(item for item in report.checks if item.name == "llm_gate_manifest_parse")
    assert parse_check.passed is False
    assert report.metrics.get("llm_candidate_total") is None
    assert report.metrics.get("llm_sent_total") is None
    assert report.metrics.get("llm_saved_pct") is None
    assert report.metrics.get("audit_miss_rate_pct") is None
    assert config.llm_gate_manifest_path.read_bytes() == supplied


@pytest.mark.parametrize(
    ("report_field", "record"),
    [
        pytest.param(
            "edge_synthesis_report_path",
            {"canonization": []},
            id="edge-report-nonobject-canonization",
        ),
        pytest.param(
            "edge_synthesis_report_path",
            {"canonization": {"resolution_rate_pct": "not-a-rate"}},
            id="edge-report-invalid-rate",
        ),
        pytest.param(
            "edge_synthesis_report_path",
            {"canonization": {}},
            id="edge-report-missing-required-rate",
        ),
        pytest.param(
            "benchmark_report_path",
            {"kind": "academic_benchmark", "metrics": []},
            id="benchmark-report-nonobject-metrics",
        ),
    ],
)
def test_academic_qc_refuses_malformed_present_derived_reports(
    tmp_path,
    report_field: str,
    record: dict[str, object],
) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    _write_valid_qc_jsonl_inputs(config, target_field="merged_records_path")
    report_path = getattr(config, report_field)
    report_path.write_text(json.dumps(record), encoding="utf-8")
    report_bytes = report_path.read_bytes()

    con = duckdb.connect(str(config.db_path))
    con.execute("CREATE TABLE IF NOT EXISTS ac_works (full_text_url VARCHAR, is_oa BOOLEAN)")
    con.execute("CHECKPOINT")
    con.close()

    with pytest.raises(ValueError, match="report"):
        run_qc(config, fail_fast=False)

    assert report_path.read_bytes() == report_bytes
    assert not config.qc_report_path.exists()


@pytest.mark.parametrize(
    "document_route",
    ["stage", "raw", "llm", "edge", "benchmark"],
)
@pytest.mark.parametrize(("case", "fragment"), _STRICT_JSON_BAD_MEMBER_FRAGMENTS)
def test_academic_qc_document_readers_reject_nonfinite_and_ambiguous_members(
    tmp_path,
    document_route: str,
    case: str,
    fragment: str,
) -> None:
    del case
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"qc"}),
    )
    if document_route == "stage":
        _write_valid_graph_load_manifest(config)
        target = config.manifests_dir / "graph_load.json"
    elif document_route == "raw":
        snapshot = config.topic_raw_root("T1", "minimum_wage") / "20261010T000000Z"
        snapshot.mkdir(parents=True, exist_ok=True)
        payload = snapshot / "payload.jsonl"
        payload.write_bytes(b"{}\n")
        target = snapshot / "manifest.json"
        target.write_text(
            json.dumps({"kind": "raw", "payload": str(payload), "count": 1}),
            encoding="utf-8",
        )
    elif document_route == "llm":
        config.raw_dir.mkdir(parents=True, exist_ok=True)
        target = config.llm_gate_manifest_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "kind": "llm_gate",
                    "metrics": {
                        "llm_candidate_total": 1,
                        "llm_sent": 1,
                        "llm_saved_pct": 0.0,
                        "audit_miss_rate_pct": 0.0,
                    },
                }
            ),
            encoding="utf-8",
        )
    elif document_route in {"edge", "benchmark"}:
        _write_valid_qc_jsonl_inputs(config, target_field="merged_records_path")
        _write_qc_database(config)
        if document_route == "edge":
            target = config.edge_synthesis_report_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps({"canonization": {"resolution_rate_pct": 95.0}}),
                encoding="utf-8",
            )
        else:
            config.edge_synthesis_report_path.parent.mkdir(parents=True, exist_ok=True)
            config.edge_synthesis_report_path.write_text(
                json.dumps({"canonization": {"resolution_rate_pct": 95.0}}),
                encoding="utf-8",
            )
            target = config.benchmark_report_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(
                    {
                        "kind": "academic_benchmark",
                        "metrics": {"runtime_demanded_canonical_resolution_rate_pct": 95.0},
                    }
                ),
                encoding="utf-8",
            )
    else:  # pragma: no cover - parameter is statically constrained above.
        raise AssertionError(f"unknown QC document route: {document_route}")

    original = target.read_bytes()
    supplied = _inject_json_member_fragment(original, fragment)
    target.write_bytes(supplied)

    if document_route == "llm":
        report = run_qc(config, fail_fast=False)
        parse_check = next(
            (item for item in report.checks if item.name == "llm_gate_manifest_parse"),
            None,
        )
        assert parse_check is not None
        assert parse_check.passed is False
        assert "llm_candidate_total" not in report.metrics
    else:
        with pytest.raises(ValueError, match="Malformed"):
            run_qc(config, fail_fast=False)
        assert not config.qc_report_path.exists()

    assert target.read_bytes() == supplied


_INVALID_PERCENTAGE_VALUES = (
    pytest.param(None, id="null"),
    pytest.param(False, id="boolean"),
    pytest.param("", id="empty-string"),
    pytest.param("100", id="numeric-string"),
    pytest.param(-0.1, id="negative"),
    pytest.param(100.01, id="over-100-fraction"),
    pytest.param(101, id="over-100-integer"),
    pytest.param(float("nan"), id="nan"),
    pytest.param(float("inf"), id="infinity"),
)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(True, id="boolean"),
        pytest.param(None, id="null"),
        pytest.param("1.0", id="numeric-string"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="positive-infinity"),
        pytest.param(float("-inf"), id="negative-infinity"),
        pytest.param(10**400, id="integer-outside-float-range"),
    ],
)
def test_academic_qc_finite_number_predicate_rejects_non_numeric_or_unbounded_values(
    value: object,
) -> None:
    assert _finite_json_number(value) is None


@pytest.mark.parametrize("value", [0, -0.25, 1, 1.25])
def test_academic_qc_finite_number_predicate_preserves_finite_effect_values(
    value: int | float,
) -> None:
    assert _finite_json_number(value) == float(value)


def test_academic_qc_counts_boolean_estimate_as_malformed_without_rejecting_negative_effects(
    tmp_path,
) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    config.raw_dir.mkdir(parents=True, exist_ok=True)
    config.merged_records_path.parent.mkdir(parents=True, exist_ok=True)
    supplied = (
        b'{"extraction_mode":"resolve_extract","estimates":'
        b'[{"value":1.25},{"value":-0.25},{"value":true}]}\n'
    )
    config.merged_records_path.write_bytes(supplied)

    report = run_qc(config, fail_fast=False)

    malformed_check = next(item for item in report.checks if item.name == "malformed_estimate_pct")
    assert report.metrics["parameters_total"] == 3
    assert report.metrics["malformed_estimate_pct"] == round(100.0 / 3.0, 3)
    assert malformed_check.passed is False
    assert config.merged_records_path.read_bytes() == supplied


def _write_qc_database(config: AcademicBatchConfig) -> None:
    with duckdb.connect(str(config.db_path)) as con:
        con.execute("CREATE TABLE IF NOT EXISTS ac_works (full_text_url VARCHAR, is_oa BOOLEAN)")


@pytest.mark.parametrize("bad_rate", _INVALID_PERCENTAGE_VALUES)
def test_academic_qc_refuses_present_edge_report_outside_percentage_contract(
    tmp_path, bad_rate: object
) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"qc"}),
    )
    _write_valid_qc_jsonl_inputs(config, target_field="merged_records_path")
    config.edge_synthesis_report_path.parent.mkdir(parents=True, exist_ok=True)
    config.edge_synthesis_report_path.write_text(
        json.dumps({"canonization": {"resolution_rate_pct": bad_rate}}),
        encoding="utf-8",
    )
    supplied = config.edge_synthesis_report_path.read_bytes()
    _write_qc_database(config)

    with pytest.raises(ValueError, match=r"Malformed|finite percentage between 0 and 100"):
        run_qc(config, fail_fast=False)

    assert config.edge_synthesis_report_path.read_bytes() == supplied
    assert not config.qc_report_path.exists()


@pytest.mark.parametrize("bad_rate", _INVALID_PERCENTAGE_VALUES)
def test_academic_qc_refuses_present_benchmark_rate_outside_percentage_contract(
    tmp_path, bad_rate: object
) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"qc"}),
    )
    _write_valid_qc_jsonl_inputs(config, target_field="merged_records_path")
    config.benchmark_report_path.parent.mkdir(parents=True, exist_ok=True)
    config.benchmark_report_path.write_text(
        json.dumps(
            {
                "kind": "academic_benchmark",
                "metrics": {"runtime_demanded_canonical_resolution_rate_pct": bad_rate},
            }
        ),
        encoding="utf-8",
    )
    supplied = config.benchmark_report_path.read_bytes()
    config.edge_synthesis_report_path.write_text(
        json.dumps({"canonization": {"resolution_rate_pct": 100.0}}),
        encoding="utf-8",
    )
    _write_qc_database(config)

    with pytest.raises(ValueError, match=r"Malformed|finite percentage between 0 and 100"):
        run_qc(config, fail_fast=False)

    assert config.benchmark_report_path.read_bytes() == supplied
    assert not config.qc_report_path.exists()


def test_academic_qc_treats_explicit_zero_rates_as_measured_values(tmp_path) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"qc"}),
    )
    _write_valid_qc_jsonl_inputs(config, target_field="merged_records_path")
    config.edge_synthesis_report_path.parent.mkdir(parents=True, exist_ok=True)
    config.edge_synthesis_report_path.write_text(
        json.dumps({"canonization": {"resolution_rate_pct": 0.0}}),
        encoding="utf-8",
    )
    config.benchmark_report_path.write_text(
        json.dumps(
            {
                "kind": "academic_benchmark",
                "metrics": {"runtime_demanded_canonical_resolution_rate_pct": 0.0},
            }
        ),
        encoding="utf-8",
    )
    _write_qc_database(config)

    report = run_qc(config, fail_fast=False)
    persisted = json.loads(config.qc_report_path.read_text(encoding="utf-8"))
    checks = {item["name"]: item for item in persisted["checks"]}
    for name in (
        "canonical_resolution_rate_pct",
        "global_canonical_resolution_rate_pct",
    ):
        assert checks[name]["passed"] is False
        assert checks[name]["value"] == 0.0
        assert checks[name]["status"] == "failed"
    assert report.passed is False
    assert report.metrics["canonical_resolution_rate_pct"] == 0.0
    assert report.metrics["runtime_demanded_canonical_resolution_rate_pct"] == 0.0
    assert report.metrics["global_canonical_resolution_rate_pct"] == 0.0


def test_academic_qc_does_not_use_edge_rate_as_missing_benchmark_evidence(
    tmp_path,
) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"edge_synthesize", "benchmark", "qc"}),
    )
    _write_valid_qc_jsonl_inputs(config, target_field="merged_records_path")
    config.edge_synthesis_report_path.parent.mkdir(parents=True, exist_ok=True)
    config.edge_synthesis_report_path.write_text(
        json.dumps({"canonization": {"resolution_rate_pct": 100.0}}),
        encoding="utf-8",
    )
    _write_qc_database(config)

    with pytest.raises(RuntimeError, match="canonical_resolution_rate_pct"):
        run_qc(config, fail_fast=True)

    persisted = json.loads(config.qc_report_path.read_text(encoding="utf-8"))
    check = next(
        item for item in persisted["checks"] if item["name"] == "canonical_resolution_rate_pct"
    )
    assert persisted["passed"] is False
    assert check["passed"] is False
    assert check["severity"] == "critical"
    assert check["status"] == "not_established"
    assert check["value"] is None
    assert persisted["metrics"]["runtime_demanded_canonical_resolution_rate_pct"] is None
    assert persisted["metrics"]["global_canonical_resolution_rate_pct"] == 100.0


def test_academic_qc_marks_absent_scheduled_edge_and_benchmark_not_established(
    tmp_path,
) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"edge_synthesize", "benchmark", "qc"}),
    )
    _write_valid_qc_jsonl_inputs(config, target_field="merged_records_path")
    _write_qc_database(config)

    with pytest.raises(RuntimeError, match="canonical_resolution_rate_pct"):
        run_qc(config, fail_fast=True)

    persisted = json.loads(config.qc_report_path.read_text(encoding="utf-8"))
    checks = {item["name"]: item for item in persisted["checks"]}
    for name in (
        "canonical_resolution_rate_pct",
        "global_canonical_resolution_rate_pct",
    ):
        assert checks[name]["passed"] is False
        assert checks[name]["severity"] == "critical"
        assert checks[name]["status"] == "not_established"
        assert checks[name]["value"] is None
    assert persisted["metrics"]["canonical_resolution_rate_pct"] is None
    assert persisted["metrics"]["runtime_demanded_canonical_resolution_rate_pct"] is None
    assert persisted["metrics"]["global_canonical_resolution_rate_pct"] is None


def test_academic_qc_marks_unscheduled_benchmark_rate_not_applicable(tmp_path) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"qc"}),
    )
    _write_valid_qc_jsonl_inputs(config, target_field="merged_records_path")
    config.edge_synthesis_report_path.parent.mkdir(parents=True, exist_ok=True)
    config.edge_synthesis_report_path.write_text(
        json.dumps({"canonization": {"resolution_rate_pct": 100.0}}),
        encoding="utf-8",
    )
    _write_qc_database(config)

    report = run_qc(config, fail_fast=False)

    check = next(item for item in report.checks if item.name == "canonical_resolution_rate_pct")
    assert check.passed is False
    assert check.severity == "warning"
    assert check.status == "not_applicable"
    assert check.value is None
    assert report.metrics["runtime_demanded_canonical_resolution_rate_pct"] is None


def test_academic_qc_marks_unscheduled_edge_rate_not_applicable(tmp_path) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"qc"}),
    )
    _write_valid_qc_jsonl_inputs(config, target_field="merged_records_path")
    _write_qc_database(config)

    report = run_qc(config, fail_fast=False)

    check = next(
        item for item in report.checks if item.name == "global_canonical_resolution_rate_pct"
    )
    assert check.passed is False
    assert check.severity == "warning"
    assert check.status == "not_applicable"
    assert check.value is None
    assert report.metrics["global_canonical_resolution_rate_pct"] is None


def test_academic_qc_marks_scheduled_database_metrics_not_established(tmp_path) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"edge_synthesize", "benchmark", "qc"}),
    )

    with pytest.raises(RuntimeError, match="canonical_resolution_rate_pct"):
        run_qc(config, fail_fast=True)

    persisted = json.loads(config.qc_report_path.read_text(encoding="utf-8"))
    checks = {item["name"]: item for item in persisted["checks"]}
    for name in (
        "canonical_resolution_rate_pct",
        "global_canonical_resolution_rate_pct",
    ):
        assert checks[name]["passed"] is False
        assert checks[name]["severity"] == "critical"
        assert checks[name]["status"] == "not_established"
        assert checks[name]["value"] is None
    assert persisted["passed"] is False
    assert persisted["metrics"]["canonical_resolution_rate_pct"] is None
    assert persisted["metrics"]["runtime_demanded_canonical_resolution_rate_pct"] is None
    assert persisted["metrics"]["global_canonical_resolution_rate_pct"] is None


def test_academic_qc_marks_unscheduled_database_metrics_not_applicable(
    tmp_path,
) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"qc"}),
    )

    config.selected_topic_works_path.parent.mkdir(parents=True, exist_ok=True)
    config.selected_topic_works_path.write_text(
        json.dumps(_valid_selected_topic_row()) + "\n",
        encoding="utf-8",
    )

    report = run_qc(config, fail_fast=True)
    checks = {item.name: item for item in report.checks}
    for name in (
        "canonical_resolution_rate_pct",
        "global_canonical_resolution_rate_pct",
    ):
        assert checks[name].passed is False
        assert checks[name].severity == "warning"
        assert checks[name].status == "not_applicable"
        assert checks[name].value is None
    assert report.passed is True
    assert report.metrics["canonical_resolution_rate_pct"] is None
    assert report.metrics["runtime_demanded_canonical_resolution_rate_pct"] is None
    assert report.metrics["global_canonical_resolution_rate_pct"] is None


def test_academic_qc_marks_absent_scheduled_graph_load_not_established(
    tmp_path,
) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"graph_load", "qc"}),
    )

    with pytest.raises(RuntimeError, match="json_validation_failures"):
        run_qc(config, fail_fast=True)

    persisted = json.loads(config.qc_report_path.read_text(encoding="utf-8"))
    check = next(item for item in persisted["checks"] if item["name"] == "json_validation_failures")
    assert persisted["passed"] is False
    assert check["passed"] is False
    assert check["severity"] == "critical"
    assert check["status"] == "not_established"
    assert check["value"] is None
    assert persisted["metrics"]["json_validation_failures"] is None


def test_academic_qc_marks_unscheduled_graph_load_not_applicable(tmp_path) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"qc"}),
    )

    config.selected_topic_works_path.parent.mkdir(parents=True, exist_ok=True)
    config.selected_topic_works_path.write_text(
        json.dumps(_valid_selected_topic_row()) + "\n",
        encoding="utf-8",
    )

    report = run_qc(config, fail_fast=True)
    persisted = json.loads(config.qc_report_path.read_text(encoding="utf-8"))

    check = next(item for item in report.checks if item.name == "json_validation_failures")
    persisted_check = next(
        item for item in persisted["checks"] if item["name"] == "json_validation_failures"
    )
    assert check.passed is False
    assert check.severity == "warning"
    assert check.status == "not_applicable"
    assert check.value is None
    assert report.metrics["json_validation_failures"] is None
    assert persisted["passed"] is True
    assert persisted_check["passed"] is False
    assert persisted_check["status"] == "not_applicable"
    assert persisted["metrics"]["json_validation_failures"] is None


def test_academic_qc_accepts_explicit_zero_from_stage_manifest(tmp_path) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"graph_load", "qc"}),
    )
    _write_valid_graph_load_manifest(config)

    report = run_qc(config, fail_fast=False)

    check = next(item for item in report.checks if item.name == "json_validation_failures")
    assert check.passed is True
    assert check.value == 0
    assert report.metrics["json_validation_failures"] == 0


@pytest.mark.parametrize(
    ("bad_value", "expected_error"),
    [
        pytest.param(
            None,
            "json_validation_failures must be a non-negative integer",
            id="null",
        ),
        pytest.param(
            False,
            "json_validation_failures must be a non-negative integer",
            id="boolean",
        ),
        pytest.param(
            "",
            "json_validation_failures must be a non-negative integer",
            id="empty-string",
        ),
        pytest.param(
            "0",
            "json_validation_failures must be a non-negative integer",
            id="numeric-string",
        ),
        pytest.param(
            -1,
            "json_validation_failures must be a non-negative integer",
            id="negative-count",
        ),
        pytest.param(
            0.0,
            "json_validation_failures must be a non-negative integer",
            id="float-count",
        ),
        pytest.param(
            1.5,
            "json_validation_failures must be a non-negative integer",
            id="fractional-count",
        ),
        pytest.param(float("nan"), "Malformed stage manifest", id="nan"),
        pytest.param(float("inf"), "Malformed stage manifest", id="infinity"),
    ],
)
def test_academic_qc_refuses_invalid_graph_load_count(
    tmp_path,
    bad_value: object,
    expected_error: str,
) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"graph_load", "qc"}),
    )
    manifest_path = config.manifests_dir / "graph_load.json"
    write_stage_manifest(
        manifest_path=manifest_path,
        stage="graph_load",
        status="ok",
        metrics={"json_validation_failures": bad_value},
    )
    supplied = manifest_path.read_bytes()

    with pytest.raises(ValueError, match=expected_error):
        run_qc(config, fail_fast=False)

    assert manifest_path.read_bytes() == supplied
    assert not config.qc_report_path.exists()


def test_academic_qc_requires_existing_raw_payload_for_zero_count(tmp_path) -> None:
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"qc"}),
    )
    raw_dir = config.topic_raw_root("T1", "minimum_wage") / "20261010T000000Z"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = raw_dir / "payload.jsonl"
    payload.write_bytes(b"")
    manifest_path = raw_dir / "manifest.json"
    write_raw_manifest(
        manifest_path=manifest_path,
        source="openalex",
        endpoint="https://api.openalex.org/works",
        payload_path=payload,
        count=0,
    )

    report = run_qc(config, fail_fast=False)
    parity = next(item for item in report.checks if item.name == "manifest_count_parity")
    assert parity.passed is True

    malformed = json.loads(manifest_path.read_text(encoding="utf-8"))
    malformed["payload"] = str(raw_dir / "missing-payload.jsonl")
    supplied = json.dumps(malformed).encode("utf-8")
    manifest_path.write_bytes(supplied)
    config.qc_report_path.unlink()

    with pytest.raises(ValueError, match="references a missing payload file"):
        run_qc(config, fail_fast=False)

    assert manifest_path.read_bytes() == supplied
    assert not config.qc_report_path.exists()


def test_academic_qc_primary_resolve_attempts_path_uses_strict_reader(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    primary_path = tmp_path / "primary-attempts.jsonl"
    monkeypatch.setattr(
        AcademicBatchConfig,
        "resolve_extract_attempts_path",
        property(lambda _self: primary_path),
    )
    config = AcademicBatchConfig(
        snapshot_root=tmp_path / "snap",
        stages=frozenset({"qc"}),
    )
    _write_valid_qc_jsonl_inputs(config, target_field="merged_records_path")
    config.resolve_extract_results_path.parent.mkdir(parents=True, exist_ok=True)
    config.resolve_extract_results_path.write_bytes(b'{"work_id":"fallback"}\n')
    primary_path.write_bytes(b"[]\n")
    primary_supplied = primary_path.read_bytes()

    with pytest.raises(ValueError, match=r"resolve-extract attempt JSONL row.*must be an object"):
        run_qc(config, fail_fast=False)

    assert primary_path.read_bytes() == primary_supplied
    assert config.resolve_extract_results_path.read_bytes() == b'{"work_id":"fallback"}\n'
    assert not config.qc_report_path.exists()


def test_academic_qc_refuses_present_stage_manifest_without_metrics(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    manifest = config.manifests_dir / "graph_load.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest_bytes = b'{"kind":"stage","stage":"graph_load","status":"ok"}'
    manifest.write_bytes(manifest_bytes)

    with pytest.raises(ValueError, match="metrics"):
        run_qc(config, fail_fast=False)

    assert manifest.read_bytes() == manifest_bytes
    assert not config.qc_report_path.exists()


def test_academic_qc_refuses_stage_manifest_without_required_metric(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    manifest = config.manifests_dir / "graph_load.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest_bytes = json.dumps(
        {"kind": "stage", "stage": "graph_load", "status": "ok", "metrics": {}}
    ).encode("utf-8")
    manifest.write_bytes(manifest_bytes)

    with pytest.raises(ValueError, match="json_validation_failures"):
        run_qc(config, fail_fast=False)

    assert manifest.read_bytes() == manifest_bytes
    assert not config.qc_report_path.exists()
