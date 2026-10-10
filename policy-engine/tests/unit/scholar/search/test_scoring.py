"""Behavioral tests for Scholar source scoring and citation spans."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polisyos.scholar.search.models import FetchResult, WebSearchHit
from polisyos.scholar.search.scoring import (
    build_source_metadata,
    compress_page_to_snippets,
    detect_conflict_score,
    score_search_hit,
    source_rank_key,
)

_FETCHED_AT = datetime(2026, 10, 10, tzinfo=UTC)


def test_mixed_direction_snippets_are_contested_but_consistent_snippets_are_not() -> None:
    claim = "Employment increase is expected."

    consistent_score, consistent_note = detect_conflict_score(
        claim,
        ["Employment increase followed the policy.", "Employment increase continued."],
    )
    mixed_score, mixed_note = detect_conflict_score(
        claim,
        ["Employment increase followed the policy.", "Employment fell after the policy."],
    )

    assert consistent_score == 0.0
    assert consistent_note is None
    assert mixed_score == 0.75
    assert (
        mixed_note == "Evidence snippets contain both positive and negative directional language."
    )


@pytest.mark.parametrize(
    ("text", "expected_snippet"),
    [
        pytest.param(
            "a" * 9 + " " + "b" * 7 + "target" + "  " + "c" * 20,
            "bbbbbbbtarget",
            id="ascii-leading-and-trailing-whitespace",
        ),
        pytest.param(
            "λ" * 9 + "\u2003" + "β🙂—β🙂—β" + "target" + "\u3000 " + "γ" * 20,
            "β🙂—β🙂—βtarget",
            id="unicode-whitespace-and-codepoint-offsets",
        ),
        pytest.param(
            "m" * 9 + " " + "([x])!?" + "target" + ")!" + "n" * 20,
            "([x])!?target)!",
            id="punctuation-preserved-while-whitespace-is-trimmed",
        ),
    ],
)
def test_snippet_offsets_bind_the_exact_returned_text_window(
    text: str,
    expected_snippet: str,
) -> None:
    snippets = compress_page_to_snippets(
        source_id="synthetic-source",
        url="https://source.example.invalid/document",
        text=text,
        query_node_id="synthetic-query",
        perspective="test-only",
        query_terms=["target"],
        max_snippets=1,
        window_chars=16,
    )

    assert len(snippets) == 1
    snippet = snippets[0]
    assert 0 <= snippet.start_char < snippet.end_char <= len(text)
    assert snippet.text == expected_snippet
    assert text[snippet.start_char : snippet.end_char] == snippet.text


def test_snippet_offsets_shift_by_unicode_prefix_length_without_changing_span() -> None:
    text = "abcdefghij " + "b" * 7 + "target" + "  " + "c" * 20
    prefix = "🌐追加: "
    base_snippet = compress_page_to_snippets(
        source_id="synthetic-source",
        url="https://source.example.invalid/document",
        text=text,
        query_node_id="synthetic-query",
        perspective="test-only",
        query_terms=["target"],
        max_snippets=1,
        window_chars=16,
    )[0]
    shifted_text = prefix + text
    shifted_snippet = compress_page_to_snippets(
        source_id="synthetic-source",
        url="https://source.example.invalid/document",
        text=shifted_text,
        query_node_id="synthetic-query",
        perspective="test-only",
        query_terms=["target"],
        max_snippets=1,
        window_chars=16,
    )[0]

    assert shifted_snippet.text == base_snippet.text
    assert shifted_snippet.start_char == base_snippet.start_char + len(prefix)
    assert shifted_snippet.end_char == base_snippet.end_char + len(prefix)
    assert shifted_text[shifted_snippet.start_char : shifted_snippet.end_char] == (
        shifted_snippet.text
    )


def test_whitespace_only_fallback_does_not_emit_an_empty_citation() -> None:
    text = " " * 16 + "later substantive text"

    snippets = compress_page_to_snippets(
        source_id="synthetic-source",
        url="https://source.example.invalid/document",
        text=text,
        query_node_id="synthetic-query",
        perspective="test-only",
        query_terms=["absent"],
        max_snippets=1,
        window_chars=16,
    )

    assert snippets == []


def test_anti_seo_penalty_keeps_spam_below_clean_equal_rank_source() -> None:
    clean_hit = WebSearchHit(
        url="https://sources.example.invalid/clean-study",
        title="Policy evaluation",
        snippet="A measured result from a study.",
        provider="synthetic-provider",
        query="synthetic policy query",
        rank=3,
        source_type="web",
    )
    spam_hit = WebSearchHit(
        url="https://sources.example.invalid/spam-study",
        title="Best coupon promo ultimate guide",
        snippet="Sponsored content with a cheap top 10 offer.",
        provider="synthetic-provider",
        query="synthetic policy query",
        rank=3,
        source_type="web",
    )
    clean_fetch = FetchResult(
        url=clean_hit.url,
        final_url=str(clean_hit.url),
        title=clean_hit.title,
        text="A measured result from a study.",
        content_type="text/plain",
        fetched_at=_FETCHED_AT,
    )
    spam_fetch = FetchResult(
        url=spam_hit.url,
        final_url=str(spam_hit.url),
        title=spam_hit.title,
        text="Sponsored content with a cheap top 10 offer.",
        content_type="text/plain",
        fetched_at=_FETCHED_AT,
    )
    clean_source = build_source_metadata(
        source_id="clean-source",
        hit=clean_hit,
        fetch=clean_fetch,
    )
    spam_source = build_source_metadata(
        source_id="spam-source",
        hit=spam_hit,
        fetch=spam_fetch,
    )

    assert score_search_hit(clean_hit) > score_search_hit(spam_hit)
    assert clean_source.anti_seo_score == 0.0
    assert spam_source.anti_seo_score > clean_source.anti_seo_score
    assert source_rank_key(clean_source) < source_rank_key(spam_source)
