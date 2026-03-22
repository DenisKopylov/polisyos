from __future__ import annotations

from polisyos.lex.batch.jurisdictions import get_jurisdiction_plugin
from polisyos.lex.batch.jurisdictions.eu import EUJurisdiction
from polisyos.lex.batch.reference_extractor import extract_references
from polisyos.lex.batch.structurer import extract_provisions


def test_get_jurisdiction_plugin_returns_eu_plugin() -> None:
    plugin = get_jurisdiction_plugin("EU")
    assert isinstance(plugin, EUJurisdiction)
    assert plugin.jurisdiction_code == "EU"


def test_extract_provisions_supports_eu_article_structure() -> None:
    spans = extract_provisions(
        "Article 1\nMember States shall ensure access to the register.",
        jurisdiction="EU",
        doc_type="Regulation",
        doc_name="Regulation (EU) 2024/1234",
    )

    assert spans
    assert spans[0].citation_label == "Article 1"
    assert spans[0].legal_unit_subtype == "core_normative_clause"
    assert spans[0].route_class in {"deterministic_then_llm_retry", "llm_primary"}


def test_extract_references_uses_eu_plugin_patterns() -> None:
    hits = extract_references(
        text="In accordance with Article 7 of Regulation (EU) 2024/1234, Member States shall report annually.",
        doc_id="eu-doc",
        anchor_path="article:1",
        jurisdiction_plugin=get_jurisdiction_plugin("EU"),
    )

    assert hits
    assert hits[0].target_raw
    assert hits[0].relation_hint == "references"
