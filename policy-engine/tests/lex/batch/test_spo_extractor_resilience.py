from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from pathlib import Path

from polisyos.lex.batch.spo_extractor import _group_request_items, extract_spo_for_documents
from polisyos.lex.batch.structurer import ProvisionSpan
from polisyos.lex.batch.xml_parser import NPACard, NPADocument
from polisyos.lex.knowledge.types import SPOCandidate, SPOExtractionResult


class _FakeClient:
    model_id = "fake/model"


def _doc(doc_id: str, text: str) -> NPADocument:
    return NPADocument(
        card=NPACard(
            doc_id=doc_id,
            reestr_code=f"R-{doc_id}",
            date_acc="2026-01-01",
            reestr_date="2026-01-01",
            status="Чинний",
            doc_type="Закон",
            name=f"Doc {doc_id}",
            publisher=("ВРУ",),
            number="1",
            publication=(),
            keywords=(),
            reg_date="",
            reg_number="",
        ),
        text=text,
    )


def _span(anchor: str, text: str) -> ProvisionSpan:
    return ProvisionSpan(
        kind="article",
        number="1",
        anchor_path=anchor,
        citation_label=anchor,
        offset_start=0,
        offset_end=len(text),
        text=text,
        is_fallback_chunk=False,
        section_role="normative_unit",
        fallback_allowed_for_reasoning=True,
    )


def test_group_request_items_respects_char_budget() -> None:
    doc = _doc("doc-a", "base")
    items = [
        (doc, _span("art:1", "x" * 1200)),
        (doc, _span("art:2", "y" * 1200)),
        (doc, _span("art:3", "z" * 1200)),
    ]

    groups = _group_request_items(
        items,
        request_batch_size=4,
        request_batch_chars=1800,
    )

    assert [len(group) for group in groups] == [1, 1, 1]


def test_group_request_items_adaptive_downshift_reduces_medium_long_batches() -> None:
    doc = _doc("doc-b", "base")
    items = [
        (doc, _span(f"art:{idx}", "x" * 700))
        for idx in range(1, 6)
    ]

    baseline_groups = _group_request_items(
        items,
        request_batch_size=5,
        request_batch_chars=4800,
    )
    adaptive_groups = _group_request_items(
        items,
        request_batch_size=5,
        request_batch_chars=4800,
        adaptive_batch_downshift_enabled=True,
        adaptive_batch_soft_chars_share=0.80,
    )

    assert [len(group) for group in baseline_groups] == [5]
    assert [len(group) for group in adaptive_groups] == [4, 1]


def test_extract_spo_for_documents_uses_timeout_fallback(monkeypatch, tmp_path: Path) -> None:
    doc = _doc("doc-a", "Орган повинен виконати вимогу.")
    span = _span("art:1", "Орган повинен виконати вимогу.")

    async def _slow_group(*args, **kwargs):  # noqa: ANN002, ANN003
        del args, kwargs
        await asyncio.sleep(0.05)
        return []

    monkeypatch.setattr("polisyos.lex.batch.spo_extractor._extract_provision_group", _slow_group)

    results_dir = tmp_path / "spo_results"
    total, failed = asyncio.run(
        extract_spo_for_documents(
            _FakeClient(),
            [doc],
            {doc.card.doc_id: [span]},
            results_dir=results_dir,
            request_batch_size=1,
            request_batch_chars=1200,
            group_timeout_seconds=0.01,
            fallback_rows_by_anchor={
                doc.card.doc_id: {
                    span.anchor_path: {
                        "doc_id": doc.card.doc_id,
                        "provision_anchor": span.anchor_path,
                        "provision_citation": span.citation_label,
                        "statements": [{"predicate": "requires"}],
                        "low_confidence": True,
                        "low_confidence_reasons": ["llm_fallback_pending"],
                        "extraction_source": "llm_timeout_fallback",
                    }
                }
            },
        )
    )

    out_path = results_dir / doc.card.doc_id[:2].lower() / f"{doc.card.doc_id}.jsonl"
    rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert total == 1
    assert failed == set()
    assert len(rows) == 1
    assert rows[0]["extraction_source"] == "llm_timeout_fallback"
    assert "llm_group_timeout_fallback" in rows[0]["low_confidence_reasons"]


def test_extract_spo_for_documents_retries_timed_out_group_with_smaller_batches(
    monkeypatch,
    tmp_path: Path,
) -> None:
    doc = _doc("doc-retry", "Орган повинен виконати вимогу.")
    span_1 = _span("art:1", "Орган повинен виконати вимогу.")
    span_2 = _span("art:2", "Орган повинен подати звіт.")
    telemetry: dict[str, int] = {}

    async def _group_result(_client, group, *, verify_mode, extract_mode, followup_pass_index):  # noqa: ANN001
        del _client, verify_mode, extract_mode, followup_pass_index
        if len(group) > 1:
            await asyncio.sleep(0.05)
            return []
        doc_item, provision = group[0]
        return [
            SPOExtractionResult(
                doc_id=doc_item.card.doc_id,
                provision_anchor=provision.anchor_path,
                provision_citation=provision.citation_label,
                statements=[
                    SPOCandidate(
                        subject_en="organ",
                        subject_uk="Орган",
                        predicate="requires",
                        object_en="requirement",
                        object_uk="вимогу",
                        fact_text=f"Recovered {provision.anchor_path}",
                        confidence=0.81,
                        norm_type="obligation",
                    )
                ],
                extraction_source="llm",
            )
        ]

    monkeypatch.setattr("polisyos.lex.batch.spo_extractor._extract_provision_group", _group_result)

    results_dir = tmp_path / "spo_results"
    total, failed = asyncio.run(
        extract_spo_for_documents(
            _FakeClient(),
            [doc],
            {doc.card.doc_id: [span_1, span_2]},
            results_dir=results_dir,
            request_batch_size=2,
            request_batch_chars=8000,
            group_timeout_seconds=0.01,
            timeout_retry_enabled=True,
            timeout_retry_batch_size=1,
            timeout_retry_chars=1200,
            telemetry=telemetry,
        )
    )

    out_path = results_dir / doc.card.doc_id[:2].lower() / f"{doc.card.doc_id}.jsonl"
    rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert total == 2
    assert failed == set()
    assert len(rows) == 2
    assert telemetry["timeout_retry_groups_total"] == 1
    assert telemetry["timeout_retry_success_total"] == 1
    assert telemetry.get("timeout_retry_failure_total", 0) == 0
    assert {row["provision_anchor"] for row in rows} == {span_1.anchor_path, span_2.anchor_path}


def test_extract_spo_for_documents_merges_gap_fill_with_baseline(monkeypatch, tmp_path: Path) -> None:
    doc = _doc("doc-b", "Орган повинен виконати вимогу.")
    span = _span("art:1", "Орган повинен виконати вимогу.")

    async def _group_result(*args, **kwargs):  # noqa: ANN002, ANN003
        del args, kwargs
        return [
            SPOExtractionResult(
                doc_id=doc.card.doc_id,
                provision_anchor=span.anchor_path,
                provision_citation=span.citation_label,
                statements=[
                    SPOCandidate(
                        subject_en="organ",
                        subject_uk="Орган",
                        predicate="requires",
                        object_en="requirement",
                        object_uk="вимогу",
                        fact_text="Organ requires compliance",
                        confidence=0.8,
                        norm_type="obligation",
                    ),
                    SPOCandidate(
                        subject_en="organ",
                        subject_uk="Орган",
                        predicate="grants",
                        object_en="permit",
                        object_uk="дозвіл",
                        fact_text="Organ grants permit",
                        confidence=0.72,
                        norm_type="permission",
                    ),
                ],
                extraction_source="llm_gap_fill",
            )
        ]

    monkeypatch.setattr("polisyos.lex.batch.spo_extractor._extract_provision_group", _group_result)

    results_dir = tmp_path / "spo_results"
    total, failed = asyncio.run(
        extract_spo_for_documents(
            _FakeClient(),
            [doc],
            {doc.card.doc_id: [span]},
            results_dir=results_dir,
            request_batch_size=1,
            extraction_source="llm_gap_fill",
            fallback_rows_by_anchor={
                doc.card.doc_id: {
                    span.anchor_path: {
                        "doc_id": doc.card.doc_id,
                        "provision_anchor": span.anchor_path,
                        "provision_citation": span.citation_label,
                        "statements": [{"predicate": "requires", "fact_text": "Organ requires compliance"}],
                        "extraction_source": "llm_gap_fill_timeout_fallback",
                    }
                }
            },
            merge_baseline_rows_by_anchor={
                doc.card.doc_id: {
                    span.anchor_path: {
                        "doc_id": doc.card.doc_id,
                        "provision_anchor": span.anchor_path,
                        "provision_citation": span.citation_label,
                        "statements": [{"predicate": "requires", "fact_text": "Organ requires compliance"}],
                        "extraction_source": "llm_gap_fill_timeout_fallback",
                    }
                }
            },
        )
    )

    out_path = results_dir / doc.card.doc_id[:2].lower() / f"{doc.card.doc_id}.jsonl"
    rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert total == 2
    assert failed == set()
    assert len(rows) == 1
    assert rows[0]["extraction_source"] == "llm_gap_fill"
    assert rows[0]["baseline_statement_count"] == 1
    assert rows[0]["llm_gap_fill_llm_statement_count"] == 2
    assert rows[0]["llm_gap_fill_added_statement_count"] == 1
    assert len(rows[0]["statements"]) == 2


def test_extract_spo_for_documents_retries_retryable_failed_results_in_followup_pass(
    monkeypatch,
    tmp_path: Path,
) -> None:
    doc = _doc("doc-followup", "Орган повинен виконати вимогу.")
    span = _span("art:1", "Орган повинен виконати вимогу.")
    telemetry: dict[str, int] = {}

    async def _group_result(_client, group, *, verify_mode, extract_mode, followup_pass_index):  # noqa: ANN001
        del _client, verify_mode, extract_mode
        doc_item, provision = group[0]
        if followup_pass_index == 0:
            return [
                SPOExtractionResult(
                    doc_id=doc_item.card.doc_id,
                    provision_anchor=provision.anchor_path,
                    provision_citation=provision.citation_label,
                    statements=[],
                    raw_llm_response="Gonka request failed after retries",
                    extraction_source="llm",
                    llm_error_class="provider_http_5xx",
                    llm_error_retryable=True,
                    llm_error_http_status=503,
                )
            ]
        return [
            SPOExtractionResult(
                doc_id=doc_item.card.doc_id,
                provision_anchor=provision.anchor_path,
                provision_citation=provision.citation_label,
                statements=[
                    SPOCandidate(
                        subject_en="organ",
                        subject_uk="Орган",
                        predicate="requires",
                        object_en="requirement",
                        object_uk="вимогу",
                        fact_text="Recovered in follow-up lane",
                        confidence=0.84,
                        norm_type="obligation",
                    )
                ],
                extraction_source="llm",
            )
        ]

    monkeypatch.setattr("polisyos.lex.batch.spo_extractor._extract_provision_group", _group_result)

    results_dir = tmp_path / "spo_results"
    total, failed = asyncio.run(
        extract_spo_for_documents(
            _FakeClient(),
            [doc],
            {doc.card.doc_id: [span]},
            results_dir=results_dir,
            request_batch_size=1,
            retryable_followup_passes=1,
            retryable_followup_delay_seconds=0.0,
            telemetry=telemetry,
        )
    )

    out_path = results_dir / doc.card.doc_id[:2].lower() / f"{doc.card.doc_id}.jsonl"
    rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert total == 1
    assert failed == set()
    assert len(rows) == 1
    assert rows[0]["statements"][0]["fact_text"] == "Recovered in follow-up lane"
    assert telemetry["retry_followup_passes_run"] == 1
    assert telemetry["retry_followup_pending_items_total"] == 1
    assert telemetry["retry_followup_recovered_items_total"] == 1
    assert telemetry.get("retry_followup_items_exhausted_total", 0) == 0


def test_extract_spo_for_documents_uses_retry_lane_context(monkeypatch, tmp_path: Path) -> None:
    doc = _doc("doc-lane", "Орган повинен виконати вимогу.")
    span = _span("art:1", "Орган повинен виконати вимогу.")
    seen_lanes: list[tuple[str, float, float]] = []

    class _LaneClient(_FakeClient):
        @contextmanager
        def request_lane(
            self,
            *,
            lane_name: str = "primary",
            rate_scale: float = 1.0,
            concurrency_scale: float = 1.0,
        ):
            seen_lanes.append((lane_name, rate_scale, concurrency_scale))
            yield self

    async def _group_result(_client, group, *, verify_mode, extract_mode, followup_pass_index):  # noqa: ANN001
        del _client, verify_mode, extract_mode
        doc_item, provision = group[0]
        if followup_pass_index == 0:
            return [
                SPOExtractionResult(
                    doc_id=doc_item.card.doc_id,
                    provision_anchor=provision.anchor_path,
                    provision_citation=provision.citation_label,
                    statements=[],
                    raw_llm_response="retryable failure",
                    extraction_source="llm",
                    llm_error_class="provider_http_429",
                    llm_error_retryable=True,
                    llm_error_http_status=429,
                )
            ]
        return [
            SPOExtractionResult(
                doc_id=doc_item.card.doc_id,
                provision_anchor=provision.anchor_path,
                provision_citation=provision.citation_label,
                statements=[
                    SPOCandidate(
                        subject_en="organ",
                        subject_uk="Орган",
                        predicate="requires",
                        object_en="requirement",
                        object_uk="вимогу",
                        fact_text="Recovered with retry lane",
                        confidence=0.84,
                        norm_type="obligation",
                    )
                ],
                extraction_source="llm",
            )
        ]

    monkeypatch.setattr("polisyos.lex.batch.spo_extractor._extract_provision_group", _group_result)

    results_dir = tmp_path / "spo_results"
    total, failed = asyncio.run(
        extract_spo_for_documents(
            _LaneClient(),
            [doc],
            {doc.card.doc_id: [span]},
            results_dir=results_dir,
            request_batch_size=1,
            retryable_followup_passes=1,
            retryable_followup_delay_seconds=0.0,
            retryable_followup_worker_scale=0.4,
            retryable_followup_dispatch_rps_scale=0.3,
            retryable_followup_client_rate_scale=0.25,
            retryable_followup_client_concurrency_scale=0.5,
        )
    )

    assert total == 1
    assert failed == set()
    assert seen_lanes[0] == ("primary", 1.0, 1.0)
    assert seen_lanes[1] == ("retry_followup", 0.25, 0.5)
