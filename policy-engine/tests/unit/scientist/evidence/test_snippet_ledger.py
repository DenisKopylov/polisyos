from __future__ import annotations

from polisyos.scholar.search.models import SourceSnippet
from polisyos.scientist.evidence.snippet_ledger import (
    build_snippet_ledger,
    stable_snippet_id,
    validate_snippet_spans,
)


def _snippet(snippet_id: str = "snip.1") -> SourceSnippet:
    return SourceSnippet(
        snippet_id=snippet_id,
        source_id="src.1",
        url="https://example.org/report",
        query_node_id="q1",
        perspective="overview",
        text="evidence span",
        start_char=5,
        end_char=18,
    )


def test_stable_snippet_id_depends_on_source_span_and_text() -> None:
    one = stable_snippet_id(
        source_id="src.1",
        start_char=5,
        end_char=18,
        text="evidence span",
    )
    two = stable_snippet_id(
        source_id="src.1",
        start_char=5,
        end_char=18,
        text="evidence span",
    )

    assert one == two
    assert one.startswith("snip.")


def test_snippet_ledger_preserves_span_metadata() -> None:
    entry = build_snippet_ledger([_snippet()])[0]

    assert entry.snippet_id == "snip.1"
    assert entry.start_char == 5
    assert entry.end_char == 18


def test_snippet_span_validation_checks_source_text_bounds() -> None:
    result = validate_snippet_spans(
        [_snippet()],
        source_text_by_id={"src.1": "01234evidence span more text"},
    )

    assert result.passed is True
    assert result.violations == []


def test_snippet_span_validation_reports_missing_source_text() -> None:
    result = validate_snippet_spans([_snippet()], source_text_by_id={})

    assert result.passed is False
    assert "missing_source_text:src.1" in result.violations
