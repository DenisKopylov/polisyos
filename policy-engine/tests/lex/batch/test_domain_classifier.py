from __future__ import annotations

from polisyos.lex.batch.domain_classifier import classify_domains


def test_classify_domains_returns_top_domain() -> None:
    text = "Податок і бюджетний збір регулюються цим законом. Податок сплачується щомісяця."
    result = classify_domains(text=text, doc_id="doc1")
    assert result.doc_id == "doc1"
    assert result.top_domain == "fiscal"
    assert result.scores
    assert result.scores[0].domain == "fiscal"
    assert result.scores[0].hits > 0

