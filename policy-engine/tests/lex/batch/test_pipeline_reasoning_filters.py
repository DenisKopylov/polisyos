from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.lex.batch.config import BatchConfig
from polisyos.lex.batch.pipeline import (
    StructureQualityStats,
    _check_structure_quality_gate,
    _should_extract_spo_from_span,
)
from polisyos.lex.batch.structurer import ProvisionSpan


def _span(
    *,
    anchor_path: str,
    text: str,
    kind: str = "paragraph",
    is_fallback_chunk: bool = False,
    section_role: str = "normative_unit",
    fallback_allowed_for_reasoning: bool = True,
) -> ProvisionSpan:
    return ProvisionSpan(
        kind=kind,
        number="1",
        anchor_path=anchor_path,
        citation_label=anchor_path,
        offset_start=0,
        offset_end=len(text),
        text=text,
        is_fallback_chunk=is_fallback_chunk,
        section_role=section_role,
        fallback_allowed_for_reasoning=fallback_allowed_for_reasoning,
    )


def test_should_extract_spo_from_span_skips_search_only_units() -> None:
    assert _should_extract_spo_from_span(
        _span(
            anchor_path="appendix:1/table:001/header:0001",
            text="Назва   Значення",
            section_role="table_header",
            fallback_allowed_for_reasoning=False,
        )
    ) is False
    assert _should_extract_spo_from_span(
        _span(
            anchor_path="full/chunk:0001",
            text="Суцільний текст без структури",
            kind="full_text",
            is_fallback_chunk=True,
            section_role="fallback_recall",
            fallback_allowed_for_reasoning=False,
        )
    ) is False
    assert _should_extract_spo_from_span(
        _span(
            anchor_path="art:1/pt:1",
            text="Орган зобов'язаний надати дозвіл.",
            kind="point",
            section_role="normative_unit",
            fallback_allowed_for_reasoning=True,
        )
    ) is True


def test_structure_quality_gate_fails_fast_on_full_only_docs(tmp_path: Path) -> None:
    config = BatchConfig(
        cards_path=tmp_path / "cards.xml",
        texts_path=tmp_path / "texts.xml",
        output_dir=tmp_path / "lex",
        stages=frozenset({"structure"}),
        quality_min_provision_docs_for_doc_rate=2,
        quality_structure_gate_enabled=True,
        quality_structure_fail_fast=True,
    )
    stats = StructureQualityStats(
        provision_docs_total=2,
        full_only_docs=2,
        duplicate_anchor_docs=0,
    )

    with pytest.raises(RuntimeError, match="Structure quality gate failed"):
        _check_structure_quality_gate(config=config, stats=stats)
