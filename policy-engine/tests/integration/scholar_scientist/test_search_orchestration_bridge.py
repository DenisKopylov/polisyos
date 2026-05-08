from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scholar.search.models import (
    FetchResult,
    SearchBudgetControls,
    SearchConstraints,
    WebSearchHit,
)
from polisyos.scholar.search.providers import ProviderFailoverPolicy
from polisyos.scholar.search.service import ScholarDeepSearchService
from polisyos.scientist.methods.research_dag.models import ResearchEdgeType, ResearchNodeType
from polisyos.scientist.methods.research_dag.projections import (
    project_web_evidence_bundle_to_research_dag,
)

pytestmark = pytest.mark.integration

_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "_data"


class _FixtureProvider:
    name = "fixture"

    def __init__(self, article: dict[str, object]) -> None:
        self._article = article

    async def search(
        self,
        query: str,
        *,
        constraints: SearchConstraints,
        max_results: int,
        timeout_s: float,
    ) -> list[WebSearchHit]:
        del constraints, timeout_s
        return [
            WebSearchHit(
                url=str(self._article["openalex_id"]),
                title=str(self._article["title"]),
                snippet="Known policy article reports that policy affects employment.",
                provider=self.name,
                query=query,
                rank=1,
                source_type="academic",
            )
        ][:max_results]


@pytest.mark.asyncio
async def test_scholar_search_projects_into_scientist_research_dag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    article = json.loads(
        (_FIXTURE_ROOT / "phase0" / "known_article_expected_result.json").read_text(
            encoding="utf-8"
        )
    )

    async def _fixture_fetch_open_page(
        url: str,
        *,
        constraints: SearchConstraints,
        cache: object,
        timeout_s: float,
        user_agent: str,
        max_bytes: int,
        source_type_hint: str,
    ) -> FetchResult:
        del constraints, cache, timeout_s, user_agent, max_bytes
        return FetchResult(
            url=url,
            final_url=url,
            title=str(article["title"]),
            text=(
                "Known Policy Article. The article says policy affects employment "
                "and reports government spending and poverty rate evidence."
            ),
            content_type="text/html",
            status="ok",
            content_sha256="sha256:known-policy-article",
            source_type=source_type_hint,
        )

    monkeypatch.setattr(
        "polisyos.scholar.search.service.fetch_open_page",
        _fixture_fetch_open_page,
    )
    service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([_FixtureProvider(article)]),
        cas=FileSystemCAS(tmp_path / "cas"),
    )

    bundle = await service.deep_search(
        question="policy affects employment",
        claim_texts=["policy affects employment"],
        constraints=SearchConstraints(
            allowed_domains=["openalex.org"],
            source_types=["academic"],
        ),
        budgets=SearchBudgetControls(
            max_search_queries=1,
            max_fetch_pages=1,
            max_parallel_queries=1,
            max_parallel_fetches=1,
            max_depth=0,
        ),
    )
    dag = project_web_evidence_bundle_to_research_dag(
        bundle,
        run_id="scholar-scientist-bridge",
        workflow_id="scientist_deep_research",
    )

    node_types = {node.node_type for node in dag.nodes}
    support_nodes = [
        node for node in dag.nodes if node.producer == "scholar.claim_support"
    ]

    assert bundle.sources[0].domain == "openalex.org"
    assert bundle.claim_supports[0].snippet_ids
    assert ResearchNodeType.SOURCE_ACQUISITION in node_types
    assert ResearchNodeType.SOURCE_READ in node_types
    assert ResearchNodeType.EXTRACTION in node_types
    assert ResearchNodeType.VERIFICATION in node_types
    assert support_nodes[0].metadata["snippet_count"] == len(
        bundle.claim_supports[0].snippet_ids
    )
    assert any(edge.edge_type is ResearchEdgeType.SUPPORTS for edge in dag.edges)
    assert "government spending and poverty rate evidence" not in dag.model_dump_json()
