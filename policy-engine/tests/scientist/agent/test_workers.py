from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.scholar.search.models import (
    ClaimSupportLink,
    QueryGraph,
    QueryNode,
    ResearchBrief,
    SourceMetadata,
    SourceSnippet,
    WebEvidenceBundle,
)
from polisyos.scientist.agent.workers import (
    WorkerBudgetHints,
    WorkerCitation,
    WorkerExecutionMode,
    WorkerSourcePolicy,
    WorkerTaskEnvelope,
    WorkerTaskResult,
    build_reflexion_evaluator_worker_handler,
    build_scholar_search_worker_handler,
    build_sectioned_worker_envelopes,
    build_self_moa_worker_envelopes,
    build_worker_tool_registry,
)


@pytest.mark.asyncio
async def test_worker_tool_registry_enforces_expected_output_schema() -> None:
    async def worker(task: WorkerTaskEnvelope) -> WorkerTaskResult:
        return WorkerTaskResult(
            task_id=task.task_id,
            worker_name=task.worker_name,
            output_text="done",
            output_data={"wrong_key": True},
        )

    registry = build_worker_tool_registry({"schema_worker": worker})
    result = await registry.aexecute(
        "schema_worker",
        {
            "envelope": WorkerTaskEnvelope(
                task_id="task-1",
                worker_name="schema_worker",
                objective="produce structured output",
                expected_output_schema={
                    "type": "object",
                    "required": ["answer"],
                    "properties": {"answer": {"type": "string"}},
                },
            ).model_dump(mode="json", exclude_none=True)
        },
    )

    assert result.error is None
    payload = WorkerTaskResult.model_validate(result.result)
    assert payload.success is False
    assert payload.error_type == "invalid_worker_output"
    assert payload.error == "output_data missing required keys: answer"


@pytest.mark.asyncio
async def test_worker_tool_registry_enforces_source_policy() -> None:
    async def worker(task: WorkerTaskEnvelope) -> WorkerTaskResult:
        return WorkerTaskResult(
            task_id=task.task_id,
            worker_name=task.worker_name,
            output_text="claim",
            citations=[
                WorkerCitation(
                    url="https://blocked.example/report",
                    snippet="blocked source",
                )
            ],
        )

    registry = build_worker_tool_registry({"policy_worker": worker})
    result = await registry.aexecute(
        "policy_worker",
        {
            "envelope": WorkerTaskEnvelope(
                task_id="task-1",
                worker_name="policy_worker",
                objective="collect evidence",
                source_policy=WorkerSourcePolicy(
                    require_citations=True,
                    min_citations=1,
                    blocked_domains=["blocked.example"],
                ),
            ).model_dump(mode="json", exclude_none=True)
        },
    )

    assert result.error is None
    payload = WorkerTaskResult.model_validate(result.result)
    assert payload.success is False
    assert payload.error_type == "source_policy_violation"
    assert payload.error == "blocked citation domain: blocked.example"


def test_sectioned_and_self_moa_envelope_builders() -> None:
    sectioned = build_sectioned_worker_envelopes(
        worker_name="research_worker",
        objective="parent objective",
        sections={"macro": "macro policy", "legal": "legal policy"},
        shared_constraints=["cite sources"],
        source_policy=WorkerSourcePolicy(require_citations=True),
        budget_hints=WorkerBudgetHints(max_cost_usd=Decimal("0.001")),
    )

    assert [item.section_id for item in sectioned] == ["macro", "legal"]
    assert sectioned[0].mode == WorkerExecutionMode.SECTIONING
    assert sectioned[0].constraints == ["cite sources"]
    assert sectioned[0].budget_hints.max_cost_usd == Decimal("0.001")

    replicas = build_self_moa_worker_envelopes(
        sectioned[0].model_copy(update={"vote_group_id": "policy_vote"}),
        replicas=3,
    )
    assert [item.task_id for item in replicas] == [
        f"{sectioned[0].task_id}__replica_0",
        f"{sectioned[0].task_id}__replica_1",
        f"{sectioned[0].task_id}__replica_2",
    ]
    assert all(item.mode == WorkerExecutionMode.SELF_MOA for item in replicas)
    assert all(item.vote_group_id == "policy_vote" for item in replicas)


@pytest.mark.asyncio
async def test_scholar_search_worker_handler_adapts_web_evidence_bundle() -> None:
    class FakeSearchService:
        async def deep_search(self, **kwargs):
            del kwargs
            brief = ResearchBrief(question="policy question")
            graph = QueryGraph(
                brief=brief,
                nodes=[
                    QueryNode(
                        node_id="q0",
                        query="policy question",
                        perspective="overview",
                    )
                ],
                root_node_ids=["q0"],
            )
            return WebEvidenceBundle(
                bundle_id="bundle-1",
                brief=brief,
                query_graph=graph,
                sources=[
                    SourceMetadata(
                        source_id="src-1",
                        url="https://example.org/report",
                        title="Example Report",
                        domain="example.org",
                    )
                ],
                snippets=[
                    SourceSnippet(
                        snippet_id="sn-1",
                        source_id="src-1",
                        url="https://example.org/report",
                        query_node_id="q0",
                        perspective="overview",
                        text="Observed policy evidence.",
                        start_char=10,
                        end_char=35,
                        relevance_score=0.9,
                    )
                ],
                claim_supports=[
                    ClaimSupportLink(
                        claim_id="claim-1",
                        claim_text="policy question",
                        snippet_ids=["sn-1"],
                        source_ids=["src-1"],
                        support_score=0.9,
                    )
                ],
            )

    handler = build_scholar_search_worker_handler(FakeSearchService())
    result = await handler(
        WorkerTaskEnvelope(
            task_id="task-1",
            worker_name="scholar_worker",
            objective="policy question",
            source_policy=WorkerSourcePolicy(require_citations=True, min_citations=1),
            budget_hints=WorkerBudgetHints(max_tokens=4096, timeout_s=5.0),
        )
    )

    assert result.success is True
    assert result.confidence == 0.9
    assert result.citations == [
        WorkerCitation(
            url="https://example.org/report",
            title="Example Report",
            snippet="Observed policy evidence.",
            source_id="src-1",
            start_char=10,
            end_char=35,
            score=0.9,
        )
    ]
    assert result.output_data["bundle_id"] == "bundle-1"


@pytest.mark.asyncio
async def test_reflexion_evaluator_worker_handler_returns_scorecard() -> None:
    handler = build_reflexion_evaluator_worker_handler()
    result = await handler(
        WorkerTaskEnvelope(
            task_id="eval-task",
            worker_name="reflexion_eval",
            objective="Evaluate a policy answer",
            input_payload={
                "objective": "Explain subsidy tradeoffs",
                "output_text": "A subsidy can shift investment but needs fiscal caps.",
                "output_data": {"answer": "ok"},
                "citations": [
                    {
                        "url": "https://example.org/policy",
                        "snippet": "Fiscal caps matter.",
                    }
                ],
                "expected_output_schema": {
                    "type": "object",
                    "required": ["answer"],
                },
            },
        )
    )

    assert result.success is True
    assert result.confidence == result.output_data["scorecard"]["overall_score"]
    assert "grounding_score" in result.output_data["scorecard"]
