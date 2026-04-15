"""Tests for web search providers and failover routing."""

from __future__ import annotations

import json

import pytest

from polisyos.scholar.search import providers as provider_module
from polisyos.scholar.search.models import SearchConstraints, WebSearchHit
from polisyos.scholar.search.providers import (
    BraveSearchProvider,
    DuckDuckGoHtmlSearchProvider,
    ProviderFailoverPolicy,
    WikipediaOpenSearchProvider,
)


class _FailingProvider:
    name = "failing"

    async def search(self, query, *, constraints, max_results, timeout_s):
        del query, constraints, max_results, timeout_s
        raise RuntimeError("boom")


class _WorkingProvider:
    name = "working"

    async def search(self, query, *, constraints, max_results, timeout_s):
        del constraints, timeout_s
        return [
            WebSearchHit(
                url="https://example.gov/report",
                title="Official report",
                snippet="Fiscal impact summary",
                provider=self.name,
                query=query,
                rank=1,
                source_type="government",
            )
        ][:max_results]


@pytest.mark.asyncio
async def test_provider_failover_policy_returns_secondary_hits():
    policy = ProviderFailoverPolicy([_FailingProvider(), _WorkingProvider()])

    provider_name, hits, error = await policy.search(
        "minimum wage",
        constraints=SearchConstraints(source_types=["government"]),
        max_results=5,
        timeout_s=5,
    )

    assert provider_name == "working"
    assert error is None
    assert len(hits) == 1
    assert str(hits[0].url) == "https://example.gov/report"


@pytest.mark.asyncio
async def test_duckduckgo_html_provider_parses_and_filters(monkeypatch):
    async def _fake_read_url_text(url, *, headers, timeout_s):
        del url, headers, timeout_s
        return """
        <a class="result__a" href="https://example.gov/report">Gov Report</a>
        <a class="result__snippet">Official evidence</a>
        <a class="result__a" href="https://spam.example/buy">Buy Now</a>
        <a class="result__snippet">Coupon page</a>
        """

    monkeypatch.setattr(
        "polisyos.scholar.search.providers._read_url_text",
        _fake_read_url_text,
    )

    provider = DuckDuckGoHtmlSearchProvider(endpoint="https://ddg.test/html/")
    hits = await provider.search(
        "housing vouchers",
        constraints=SearchConstraints(allowed_domains=["example.gov"]),
        max_results=10,
        timeout_s=5,
    )

    assert [hit.title for hit in hits] == ["Gov Report"]
    assert hits[0].source_type == "government"


@pytest.mark.asyncio
async def test_wikipedia_provider_parses_results(monkeypatch):
    async def _fake_read_url_text(url, *, headers, timeout_s):
        del url, headers, timeout_s
        return json.dumps(
            {
                "query": {
                    "search": [
                        {
                            "pageid": 42,
                            "title": "Minimum wage",
                            "snippet": "<span>Labor</span> policy",
                        }
                    ]
                }
            }
        )

    monkeypatch.setattr(
        "polisyos.scholar.search.providers._read_url_text",
        _fake_read_url_text,
    )

    provider = WikipediaOpenSearchProvider(endpoint="https://wiki.test/api.php")
    hits = await provider.search(
        "minimum wage",
        constraints=SearchConstraints(),
        max_results=5,
        timeout_s=5,
    )

    assert len(hits) == 1
    assert hits[0].title == "Minimum wage"
    assert "Labor policy" in hits[0].snippet
    assert str(hits[0].url) == "https://en.wikipedia.org/wiki/Minimum_wage"


@pytest.mark.asyncio
async def test_brave_provider_parses_json_results(monkeypatch):
    async def _fake_read_url_text(url, *, headers, timeout_s):
        assert "freshness=pw" in url
        assert headers["X-Subscription-Token"] == "secret"
        del timeout_s
        return json.dumps(
            {
                "web": {
                    "results": [
                        {
                            "url": "https://agency.gov/policy",
                            "title": "Agency policy",
                            "description": "Official guidance",
                        }
                    ]
                }
            }
        )

    monkeypatch.setattr(
        "polisyos.scholar.search.providers._read_url_text",
        _fake_read_url_text,
    )

    provider = BraveSearchProvider(api_key="secret", endpoint="https://brave.test/search")
    hits = await provider.search(
        "child tax credit",
        constraints=SearchConstraints(recency_days=7),
        max_results=5,
        timeout_s=5,
    )

    assert len(hits) == 1
    assert hits[0].provider == "brave"
    assert hits[0].source_type == "government"


@pytest.mark.asyncio
async def test_read_url_text_uses_shared_executor_bridge(monkeypatch):
    calls: list[tuple[object, float | None]] = []

    async def _fake_run_blocking_async(func, /, *args, timeout_seconds=None, **kwargs):
        del args, kwargs
        calls.append((func, timeout_seconds))
        return '{"ok": true}'

    monkeypatch.setattr(
        "polisyos.scholar.search.providers.run_blocking_async",
        _fake_run_blocking_async,
    )

    body = await provider_module._read_url_text(
        "https://example.gov/report",
        headers={"User-Agent": "test"},
        timeout_s=7,
    )

    assert body == '{"ok": true}'
    assert calls
    assert calls[0][1] == 7
