from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from polisyos.data_forge.domains.legal.batch.graph_builder import build_graph
from polisyos.data_forge.domains.legal.batch.postprocess import ground_spo_quotes
from polisyos.data_forge.domains.legal.batch.provisions_io import write_provisions
from polisyos.data_forge.domains.legal.source_relation import (
    LegalSourceRelationVerificationMissingError,
)
from polisyos.data_forge.read_api.legal import search_legal_knowledge_graph
from polisyos.lex.knowledge.search import LegalKnowledgeGraph

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _statement(
    *,
    statement_id: str,
    fact_text: str,
    quote: str,
    start: int | None,
    end: int | None,
    subject_en: str = "authority",
    subject_uk: str = "The authority",
    predicate: str = "requires",
    object_en: str = "annual_report",
    object_uk: str = "annual report",
    norm_type: str = "obligation",
    action_canon: str = "requires",
    norm_type_canon: str = "obligation",
) -> dict[str, object]:
    return {
        "statement_id": statement_id,
        "subject_en": subject_en,
        "subject_uk": subject_uk,
        "predicate": predicate,
        "object_en": object_en,
        "object_uk": object_uk,
        "fact_text": fact_text,
        "confidence": 0.99,
        "norm_type": norm_type,
        "norm_type_canon": norm_type_canon,
        "action_canon": action_canon,
        "canonical_status": "canonicalized",
        "source_quote_uk": quote,
        "source_quote_start": start,
        "source_quote_end": end,
        "grounding_status": "exact_quote",
        "trust_tier": "normative_fact",
    }


def test_source_bound_grounding_reaches_legal_search_without_forged_rows(tmp_path: Path) -> None:
    doc_id = "abdoc"
    anchor = "body:1/item:0001"
    provision_text = "The authority shall publish the annual report by March."
    provisions_dir = tmp_path / "provisions"
    raw_spo_dir = tmp_path / "raw_spo"
    grounded_spo_dir = tmp_path / "grounded_spo"
    db_path = tmp_path / "lex_knowledge_graph.duckdb"

    write_provisions(
        provisions_dir=provisions_dir,
        doc_id=doc_id,
        provisions=[
            {
                "anchor_path": anchor,
                "kind": "point",
                "text": provision_text,
                "is_fallback_chunk": False,
                "struct_kind": "enumeration_item",
                "section_role": "normative_unit",
                "fallback_allowed_for_reasoning": True,
            }
        ],
    )
    _write_jsonl(
        raw_spo_dir / doc_id[:2] / f"{doc_id}.jsonl",
        [
            {
                "doc_id": doc_id,
                "provision_anchor": anchor,
                "provision_citation": "controlled test source; not legal authority",
                "extraction_source": "rule_auto",
                "statements": [
                    _statement(
                        statement_id="source-grounded",
                        fact_text="Annual report must be published by March.",
                        quote=provision_text,
                        start=None,
                        end=None,
                    ),
                    _statement(
                        statement_id="forged-quote",
                        fact_text="Annual report deadline is March.",
                        quote="This quotation does not appear in the source provision.",
                        start=0,
                        end=1,
                    ),
                    _statement(
                        statement_id="unrelated-exact-quote",
                        fact_text="The agency must seize farmland.",
                        quote=provision_text,
                        start=None,
                        end=None,
                        subject_en="agency",
                        subject_uk="агентство",
                        object_en="farmland",
                        object_uk="землю",
                    ),
                    _statement(
                        statement_id="opposite-modality-exact-quote",
                        fact_text="The authority must not publish the annual report by March.",
                        quote=provision_text,
                        start=None,
                        end=None,
                        predicate="prohibits",
                        object_en="publication of annual report",
                        object_uk="оприлюднення річного звіту",
                        norm_type="prohibition",
                        action_canon="prohibits",
                        norm_type_canon="prohibition",
                    ),
                    _statement(
                        statement_id="negated-exact-quote",
                        fact_text="The authority is not required to publish the annual report.",
                        quote=provision_text,
                        start=None,
                        end=None,
                    ),
                    _statement(
                        statement_id="whole-provision-fallback",
                        fact_text="The agency must seize farmland.",
                        quote="",
                        start=None,
                        end=None,
                        subject_en="agency",
                        subject_uk="агентство",
                        object_en="farmland",
                        object_uk="землю",
                    ),
                ],
            }
        ],
    )

    ground_spo_quotes(
        spo_results_dir=raw_spo_dir,
        provisions_dir=provisions_dir,
        output_dir=grounded_spo_dir,
    )
    build_graph(
        spo_results_dir=grounded_spo_dir,
        provisions_dir=provisions_dir,
        references_dir=None,
        domains_dir=None,
        doc_metadata={},
        db_path=db_path,
    )

    graph = LegalKnowledgeGraph(db_path=db_path, index_dir=tmp_path / "indexes")
    with pytest.raises(LegalSourceRelationVerificationMissingError):
        graph.text_search("annual report", trust_tier="normative_fact")
    candidates = graph.text_search("annual report", trust_tier="search_candidate")

    with pytest.raises(LegalSourceRelationVerificationMissingError):
        search_legal_knowledge_graph(
            output_dir=tmp_path,
            query="annual report",
            top_k=10,
        )

    candidate_texts = {fact.fact_text for fact in candidates}
    assert {
        "Annual report must be published by March.",
        "Annual report deadline is March.",
        "The authority must not publish the annual report by March.",
        "The authority is not required to publish the annual report.",
    } <= candidate_texts

    with pytest.raises(LegalSourceRelationVerificationMissingError):
        graph.text_search("seize farmland", trust_tier="normative_fact")
    farmland_candidates = graph.text_search("seize farmland", trust_tier="search_candidate")
    assert "The agency must seize farmland." in {fact.fact_text for fact in farmland_candidates}
