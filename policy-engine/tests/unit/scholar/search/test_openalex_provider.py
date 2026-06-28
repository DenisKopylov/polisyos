"""Tests for the OpenAlex scholar provider and search traces."""

from __future__ import annotations

import json
import urllib.parse
from pathlib import Path

import duckdb
import pytest

from polisyos.data_forge.domains.academic.knowledge.skg_store import (
    ensure_skg_schema,
    ingest_openalex_no_hit_frontier,
)
from polisyos.scholar.search.models import (
    QueryGraph,
    QueryNode,
    ResearchBrief,
    SearchBudgetControls,
    SearchConstraints,
)
from polisyos.scholar.search.providers import OpenAlexWorksProvider, ProviderFailoverPolicy
from polisyos.scholar.search.service import ScholarDeepSearchService

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "scholar" / "openalex"


def _fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_openalex_provider_normalizes_real_recorded_works_for_different_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads = {
        "loan guarantees SMEs firm survival impact evaluation": _fixture(
            "credit_guarantee_firm_survival.json"
        ),
        "minimum wage employment effect": _fixture("minimum_wage_employment.json"),
    }
    requested_urls: list[str] = []

    async def _fake_read_url_text(url: str, *, headers: dict[str, str], timeout_s: float) -> str:
        del headers, timeout_s
        requested_urls.append(url)
        params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        query = params["search"][0]
        return json.dumps(payloads[query])

    monkeypatch.setattr(
        "polisyos.scholar.search.providers._read_url_text",
        _fake_read_url_text,
    )

    provider = OpenAlexWorksProvider(endpoint="https://openalex.test/works", mailto="ops@test")
    credit_hits = await provider.search(
        "loan guarantees SMEs firm survival impact evaluation",
        constraints=SearchConstraints(source_types=["academic"]),
        max_results=3,
        timeout_s=5,
    )
    wage_hits = await provider.search(
        "minimum wage employment effect",
        constraints=SearchConstraints(source_types=["academic"]),
        max_results=3,
        timeout_s=5,
    )

    assert credit_hits
    assert wage_hits
    assert credit_hits[0].provider == "openalex"
    assert credit_hits[0].source_type == "academic"
    assert str(credit_hits[0].url).startswith("https://openalex.org/W")
    assert "debt finance" in credit_hits[0].snippet
    assert "minimum wage" in wage_hits[0].title.lower()
    assert {str(hit.url) for hit in credit_hits} != {str(hit.url) for hit in wage_hits}
    assert all("filter=" in url and "has_abstract" in url for url in requested_urls)


@pytest.mark.asyncio
async def test_openalex_no_hit_query_records_trace_and_frontier(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def _fake_read_url_text(url: str, *, headers: dict[str, str], timeout_s: float) -> str:
        del url, headers, timeout_s
        return json.dumps(_fixture("no_hits.json"))

    monkeypatch.setattr(
        "polisyos.scholar.search.providers._read_url_text",
        _fake_read_url_text,
    )
    con = duckdb.connect(str(tmp_path / "skg.duckdb"))
    ensure_skg_schema(con)

    def _record_no_hit(trace, frontier) -> None:
        assert frontier.reason == "provider_returned_no_hits"
        ingest_openalex_no_hit_frontier(con, query_trace=trace)

    provider = OpenAlexWorksProvider(endpoint="https://openalex.test/works")
    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([provider]),
        search_timeout_s=5,
        fetch_timeout_s=5,
        no_hit_recorder=_record_no_hit,
    )
    brief = ResearchBrief(question="zzzxxy policyos nonexistent phrase qwertyuiopasdfgh 123456789")
    graph = QueryGraph(
        brief=brief,
        nodes=[
            QueryNode(
                node_id="q0",
                query=brief.question,
                perspective="root",
            )
        ],
        root_node_ids=["q0"],
    )

    bundle = await service.deep_search(
        brief=brief,
        query_graph=graph,
        constraints=SearchConstraints(source_types=["academic"]),
        budgets=SearchBudgetControls(
            max_search_queries=1,
            max_fetch_pages=1,
            max_depth=0,
            max_wall_time_s=5,
        ),
    )

    assert bundle.query_traces[0].provider == "openalex"
    assert bundle.query_traces[0].hit_count == 0
    assert bundle.no_hit_frontier
    assert bundle.no_hit_frontier[0].provider == "openalex"
    assert bundle.no_hit_frontier[0].reason == "provider_returned_no_hits"
    rows = con.execute(
        "SELECT query, provider, reason FROM ac_skg_no_hit_frontier"
    ).fetchall()
    assert rows == [(brief.question, "openalex", "provider_returned_no_hits")]
    con.close()
