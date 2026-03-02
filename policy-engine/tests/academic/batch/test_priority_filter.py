from __future__ import annotations

from polisyos.academic.openalex.priority_filter import should_process


def _work(*, topic_names: list[str], cited_by_count: int) -> dict:
    return {
        "topics": [{"display_name": topic_name} for topic_name in topic_names],
        "cited_by_count": cited_by_count,
    }


def test_should_process_tier1_by_display_name() -> None:
    work = _work(topic_names=["Fiscal policy in OECD"], cited_by_count=25)
    decision, reason = should_process(work)
    assert decision is True
    assert reason == "tier1"


def test_should_process_tier1_low_citations_rejected() -> None:
    work = _work(topic_names=["Public policy"], cited_by_count=3)
    decision, reason = should_process(work, min_citations=10)
    assert decision is False
    assert reason == "skip_low_citation"


def test_should_process_tier2_domain_match() -> None:
    work = _work(topic_names=["Trade policy in energy markets"], cited_by_count=7)
    decision, reason = should_process(work, domain_filter=["energy"], min_citations=10)
    assert decision is True
    assert reason == "tier2_domain_match"


def test_should_process_irrelevant() -> None:
    work = _work(topic_names=["Computational geometry"], cited_by_count=500)
    decision, reason = should_process(work)
    assert decision is False
    assert reason == "skip_irrelevant"
