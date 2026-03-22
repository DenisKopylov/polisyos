from __future__ import annotations

from pathlib import Path

from polisyos.lex.batch.config import BatchConfig
from polisyos.lex.batch.pipeline import (
    _build_spo_doc_routing_plan,
    _extract_provisions_worker,
    _group_docs_by_spo_settings,
    _should_route_llm_gap_fill,
    _should_skip_audit_for_span,
    _should_extract_spo_from_span,
)
from polisyos.lex.batch.smoke import SMOKE_PROFILES
from polisyos.lex.batch.structurer import ProvisionSpan
from polisyos.lex.batch.xml_parser import NPACard, NPADocument


def _doc(*, doc_id: str, title: str, doc_type: str = "Постанова") -> NPADocument:
    return NPADocument(
        card=NPACard(
            doc_id=doc_id,
            reestr_code="1",
            date_acc="2026-01-01",
            reestr_date="2026-01-02",
            status="чинний",
            doc_type=doc_type,
            name=title,
            publisher=("Кабінет Міністрів України",),
            number="1",
            publication=(),
            keywords=(),
            reg_date="2026-01-02",
            reg_number="1/1",
        ),
        text=title,
    )


def _span(index: int, text: str, *, kind: str = "point", section_role: str = "") -> ProvisionSpan:
    return ProvisionSpan(
        kind=kind,
        number=str(index),
        anchor_path=f"{kind}:{index}",
        citation_label=f"Пункт {index}",
        offset_start=index * 10,
        offset_end=index * 10 + len(text),
        text=text,
        token_est=max(1, len(text.split())),
        text_hash=f"hash-{index}",
        struct_kind=kind,
        section_role=section_role,
        lineage_path=f"{kind}:{index}",
        fallback_allowed_for_reasoning=True,
    )


def test_acceptance_safe_profile_exists() -> None:
    profile = SMOKE_PROFILES["acceptance_safe"]
    assert profile.parallel_llm == 4
    assert profile.gonka_rate_limit_rps == 1.2
    assert profile.spo_request_batch_size == 2


def test_production_gap_fill_wide_profile_exists() -> None:
    profile = SMOKE_PROFILES["production_gap_fill_wide"]
    assert profile.llm_gap_fill_mode == "wide"
    assert profile.llm_gap_fill_max_share == 0.8
    assert profile.parallel_llm == 10


def test_build_spo_doc_routing_plan_caps_mega_catalog_and_disables_llm(tmp_path: Path) -> None:
    config = BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=tmp_path / "lex",
        stages=frozenset({"spo"}),
        spo_task_batch_size=64,
        spo_request_batch_size=4,
        spo_request_batch_chars=4800,
        spo_group_timeout_seconds=90.0,
        spo_max_provisions_per_doc=14,
    )
    doc = _doc(
        doc_id="mega000000000001",
        title="Про затвердження Списків виробництв, робіт, професій і посад",
    )
    reasoning_spans = [
        _span(i, "Затвердити список виробництв та визначити порядок застосування.", kind="point")
        for i in range(12)
    ]
    prov_rows = [{"kind": "full_chunk", "fallback_allowed_for_reasoning": False} for _ in range(1490)]
    prov_rows.extend({"kind": "point", "fallback_allowed_for_reasoning": True} for _ in reasoning_spans)

    plan = _build_spo_doc_routing_plan(
        doc=doc,
        prov_rows=prov_rows,
        reasoning_spans=reasoning_spans,
        quality_family="appendix_heavy",
        config=config,
    )

    assert "mega_outlier" in plan.flags
    assert plan.llm_allowed is False
    assert len(plan.reasoning_spans) <= 6
    assert plan.llm_settings.request_batch_size == 1
    assert plan.llm_settings.request_batch_chars == 2200


def test_group_docs_by_spo_settings_separates_outliers(tmp_path: Path) -> None:
    config = BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=tmp_path / "lex-group",
        stages=frozenset({"spo"}),
        spo_task_batch_size=64,
        spo_request_batch_size=4,
        spo_request_batch_chars=4800,
        spo_group_timeout_seconds=90.0,
        spo_max_provisions_per_doc=14,
    )
    normal_doc = _doc(doc_id="norm000000000001", title="Про порядок ліцензування", doc_type="Закон України")
    outlier_doc = _doc(
        doc_id="mega000000000002",
        title="Про перелік об'єктів, які не підлягають приватизації",
    )
    normal_spans = [_span(i, "Орган ліцензування зобов'язаний видати рішення.", kind="article") for i in range(6)]
    outlier_spans = [_span(i, "Перелік об'єктів державної власності.", kind="point", section_role="catalog_entry") for i in range(10)]
    normal_plan = _build_spo_doc_routing_plan(
        doc=normal_doc,
        prov_rows=[{"kind": "article", "fallback_allowed_for_reasoning": True} for _ in range(8)],
        reasoning_spans=normal_spans,
        quality_family="law",
        config=config,
    )
    outlier_plan = _build_spo_doc_routing_plan(
        doc=outlier_doc,
        prov_rows=[{"kind": "full_chunk", "fallback_allowed_for_reasoning": False} for _ in range(1200)],
        reasoning_spans=outlier_spans,
        quality_family="appendix_heavy",
        config=config,
    )

    grouped = _group_docs_by_spo_settings(
        {
            normal_doc.card.doc_id: normal_doc,
            outlier_doc.card.doc_id: outlier_doc,
        },
        {
            normal_doc.card.doc_id: normal_plan.llm_settings,
            outlier_doc.card.doc_id: outlier_plan.llm_settings,
        },
    )

    assert len(grouped) == 2
    request_sizes = sorted(settings.request_batch_size for settings, _docs in grouped)
    assert request_sizes == [1, 4]


def test_build_spo_doc_routing_plan_keeps_law_soft_cap_above_acceptance_default(tmp_path: Path) -> None:
    config = BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=tmp_path / "lex-law",
        stages=frozenset({"spo"}),
        spo_task_batch_size=48,
        spo_request_batch_size=2,
        spo_request_batch_chars=2600,
        spo_group_timeout_seconds=75.0,
        spo_max_provisions_per_doc=10,
    )
    law_doc = _doc(
        doc_id="law000000000001",
        title="Конституція України",
        doc_type="Конституція",
    )
    law_spans = [
        _span(i, "Громадяни України мають право на свободу об'єднання у політичні партії.", kind="article")
        for i in range(40)
    ]

    plan = _build_spo_doc_routing_plan(
        doc=law_doc,
        prov_rows=[{"kind": "article", "fallback_allowed_for_reasoning": True} for _ in range(40)],
        reasoning_spans=law_spans,
        quality_family="law",
        config=config,
    )

    assert len(plan.reasoning_spans) == 24
    assert plan.llm_allowed is True


def test_extract_provisions_worker_passes_jurisdiction(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def _fake_extract_provisions(text: str, **kwargs):  # noqa: ANN003
        del text
        captured["jurisdiction"] = str(kwargs.get("jurisdiction") or "")
        return [
            ProvisionSpan(
                kind="article",
                number="1",
                anchor_path="article:1",
                citation_label="Стаття 1",
                offset_start=0,
                offset_end=10,
                text="Sample text",
                token_est=2,
                text_hash="hash-worker",
                struct_kind="article",
                section_role="normative_unit",
                lineage_path="article:1",
                fallback_allowed_for_reasoning=True,
            )
        ]

    monkeypatch.setattr("polisyos.lex.batch.structurer.extract_provisions", _fake_extract_provisions)

    rows = _extract_provisions_worker(
        {
            "text": "Article 1 sample",
            "doc_type": "Regulation",
            "doc_name": "Sample",
            "publisher": ["Authority"],
            "jurisdiction": "EU",
            "enable_paragraphs": True,
            "fallback_chunk_chars": 1800,
            "fallback_chunk_overlap": 200,
        }
    )

    assert captured["jurisdiction"] == "EU"
    assert len(rows) == 1
    assert rows[0]["anchor_path"] == "article:1"


def test_should_extract_spo_from_small_fallback_approval_bundle() -> None:
    span = ProvisionSpan(
        kind="fallback_unit",
        number=None,
        anchor_path="full/chunk:0001",
        citation_label="Повний текст",
        offset_start=0,
        offset_end=120,
        text="ЗАТВЕРДЖЕНО наказом Міністерства охорони здоров'я України Перелік лікарських засобів.",
        token_est=12,
        text_hash="fallback-approval",
        is_fallback_chunk=True,
        struct_kind="fallback_unit",
        section_role="fallback_recall",
        lineage_path="full/chunk:0001",
        fallback_allowed_for_reasoning=False,
        legal_unit_subtype="approval_bundle",
        route_class="deterministic_only",
    )

    assert _should_extract_spo_from_span(span) is True


def test_should_skip_audit_for_low_signal_form_label() -> None:
    span = ProvisionSpan(
        kind="paragraph",
        number=None,
        anchor_path="appendix:2/para:0010",
        citation_label="Додаток 2",
        offset_start=0,
        offset_end=40,
        text="Назва об'єднання фінансових установ",
        token_est=4,
        text_hash="form-label",
        struct_kind="paragraph",
        section_role="procedure",
        lineage_path="appendix:2/para:0010",
        fallback_allowed_for_reasoning=True,
        legal_unit_subtype="application_requirement",
        route_class="deterministic_only",
    )

    assert _should_skip_audit_for_span(span) is True


def test_should_route_llm_gap_fill_for_single_fact_tail(tmp_path: Path) -> None:
    config = BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=tmp_path / "lex-gap",
        stages=frozenset({"spo"}),
        llm_gap_fill_enabled=True,
        llm_gap_fill_mode="wide",
        llm_gap_fill_max_share=0.8,
    )
    span = ProvisionSpan(
        kind="article",
        number="1",
        anchor_path="art:1",
        citation_label="Стаття 1",
        offset_start=0,
        offset_end=120,
        text="Орган видає посвідчення. Порядок їх видачі встановлюється Кабінетом Міністрів України.",
        token_est=18,
        text_hash="gap-tail",
        struct_kind="article",
        section_role="normative_unit",
        lineage_path="art:1",
        fallback_allowed_for_reasoning=True,
        legal_unit_subtype="core_normative_clause",
        route_class="deterministic_then_llm_retry",
    )

    should_route, priority, reasons = _should_route_llm_gap_fill(
        config=config,
        span=span,
        quality_family="law",
        deterministic_candidates=[{"predicate": "requires"}],
    )

    assert should_route is True
    assert priority == 2
    assert "single_fact_tail" in reasons
