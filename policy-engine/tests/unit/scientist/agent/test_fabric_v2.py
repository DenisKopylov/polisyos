"""Integration tests for the Scientist v2 orchestration facade."""

from __future__ import annotations

from decimal import Decimal

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scholar.search.models import FetchResult, SearchConstraints, WebSearchHit
from polisyos.scholar.search.providers import ProviderFailoverPolicy
from polisyos.scholar.search.service import ScholarDeepSearchService
from polisyos.scientist.agent.critic import MockCriticAgent
from polisyos.scientist.agent.drafter_clients import MockDrafterAgent
from polisyos.scientist.agent.fabric import (
    ScientistAgentFabric,
    ScientistAgentFabricConfig,
    ScientistAgentFabricRequest,
)
from polisyos.scientist.agent.formalizer import MockFormalizerAgent
from polisyos.scientist.agent.pi import MockPIAgent


class _StaticProvider:
    name = "static"

    async def search(self, query, *, constraints, max_results, timeout_s):
        del constraints, timeout_s
        return [
            WebSearchHit(
                url="https://agency.gov/policy",
                title="Agency policy evidence",
                snippet=f"Evidence for {query}",
                provider=self.name,
                query=query,
                rank=1,
                source_type="government",
            )
        ][:max_results]


async def _fake_fetch_open_page(
    url,
    *,
    constraints,
    cache,
    timeout_s,
    user_agent,
    max_bytes,
    source_type_hint,
):
    del constraints, cache, timeout_s, user_agent, max_bytes
    return FetchResult(
        url=url,
        final_url=url,
        title="Agency report",
        text="Targeted support increased earnings and reduced hardship.",
        content_type="text/html",
        status="ok",
        content_sha256="hash-policy",
        source_type=source_type_hint,
    )


@pytest.mark.asyncio
async def test_scientist_agent_fabric_runs_with_web_swarm_and_reflexion(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "polisyos.scholar.search.service.fetch_open_page",
        _fake_fetch_open_page,
    )
    cas = FileSystemCAS(tmp_path / "cas")
    search_service = ScholarDeepSearchService(
        provider_policy=ProviderFailoverPolicy([_StaticProvider()]),
        cas=cas,
    )
    problem_frame = await MockPIAgent().create_problem_frame(
        "Reduce poverty with targeted transfers",
        domain_hint="economic",
    )
    fabric = ScientistAgentFabric(
        config=ScientistAgentFabricConfig(
            enabled=True,
            web_search_enabled=True,
            swarm_enabled=True,
            reflexion_enabled=True,
            max_reflexion_iterations=2,
            max_swarm_budget_usd=Decimal("0.01"),
            memory_index_path=tmp_path / "memory_index.txt",
        )
    )

    result = await fabric.run(
        ScientistAgentFabricRequest(
            run_id="R_test",
            variant_id="variant_1",
            model_name=None,
            llm_client=None,
            problem_frame=problem_frame,
            data_context={"metrics": []},
            drafter=MockDrafterAgent(),
            formalizer=MockFormalizerAgent(),
            critic=MockCriticAgent(default_verdict="APPROVE"),
            artifact_store=cas,
            max_iterations=2,
            search_service=search_service,
            search_constraints=SearchConstraints(allowed_domains=["agency.gov"]),
        )
    )

    assert result.result["verdict"] in {"APPROVE", "NEEDS_REVISION"}
    assert "web_evidence" in result.traces
    assert "supervisor" in result.traces
    assert "memory_index_ref" in result.traces
    assert result.draft.citations
    assert result.critique.citations
