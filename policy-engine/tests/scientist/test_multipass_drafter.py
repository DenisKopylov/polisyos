from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import pytest

from polisyos.scientist.agent.drafter import (
    LLMDrafterAgent,
    FindingCategory,
    FindingSeverity,
    MultiPassConfig,
    MultiPassLLMDrafter,
    MockDrafterAgent,
    create_drafter_agent,
)
from polisyos.scientist.agent.memory import ShortTermMemory
from polisyos.scientist.agent.protocols import (
    CritiqueCategory,
    CritiqueIssue,
    CritiqueReport,
    CritiqueSeverity,
    DrafterAgent,
    ProblemFrame,
)
from polisyos.scientist.agent.rag import (
    CASRAGIndex,
    HashEmbeddingBackend,
    ProblemFrameTextualizer,
    RAGCaseEntry,
)


def run(coro):
    return asyncio.run(coro)


def _problem_frame() -> ProblemFrame:
    return ProblemFrame(
        frame_id="pf_multipass_001",
        domain="economic",
        problem_statement="Reduce poverty while preserving fiscal stability",
        actors=("government", "citizens"),
        goals=("Reduce poverty", "Stay within budget"),
        constraints=("Budget <= 1_000_000", "No extreme tax rates"),
        success_criteria={"poverty_reduction": 0.2},
        assumptions=("Stable macro conditions",),
        created_at=datetime.utcnow(),
    )


class _Usage:
    def __init__(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _Response:
    def __init__(self, content: str, prompt_tokens: int, completion_tokens: int) -> None:
        self.content = content
        self.usage = _Usage(prompt_tokens, completion_tokens)


class SequenceLLM:
    def __init__(
        self,
        responses: list[str],
        *,
        prompt_tokens: int = 500,
        completion_tokens: int = 300,
        fail_calls: set[int] | None = None,
        model_name: str = "gpt-4o",
    ) -> None:
        self._responses = responses
        self._prompt_tokens = prompt_tokens
        self._completion_tokens = completion_tokens
        self._fail_calls = fail_calls or set()
        self.model_name = model_name
        self.call_count = 0

    async def generate(self, **kwargs: Any) -> _Response:
        del kwargs
        self.call_count += 1
        if self.call_count in self._fail_calls:
            raise TimeoutError("mock timeout")
        idx = min(self.call_count - 1, len(self._responses) - 1)
        return _Response(
            self._responses[idx],
            self._prompt_tokens,
            self._completion_tokens,
        )


class HighConfidenceDrafter(MockDrafterAgent):
    async def draft_policy(
        self,
        problem_frame: ProblemFrame,
        *,
        data_context: dict[str, Any] | None = None,
        hints: list[str] | None = None,
        prior_drafts=None,
    ):
        draft = await super().draft_policy(
            problem_frame,
            data_context=data_context,
            hints=hints,
            prior_drafts=prior_drafts,
        )
        draft.confidence = 0.95
        return draft


def test_protocol_conformance() -> None:
    agent = MultiPassLLMDrafter(
        MockDrafterAgent(),
        config=MultiPassConfig(max_passes=1),
    )
    assert isinstance(agent, DrafterAgent)


def test_pass1_delegates_to_inner() -> None:
    inner = MockDrafterAgent()
    agent = MultiPassLLMDrafter(inner, config=MultiPassConfig(max_passes=1))

    result = run(agent.draft_policy(_problem_frame()))

    assert result.problem_frame_ref == "pf_multipass_001"
    assert inner.draft_count == 1


def test_pass1_injects_rag_few_shot_hint() -> None:
    class RecordingDrafter(MockDrafterAgent):
        def __init__(self) -> None:
            super().__init__()
            self.last_hints: list[str] = []

        async def draft_policy(
            self,
            problem_frame: ProblemFrame,
            *,
            data_context: dict[str, Any] | None = None,
            hints: list[str] | None = None,
            prior_drafts=None,
        ):
            self.last_hints = list(hints or [])
            return await super().draft_policy(
                problem_frame,
                data_context=data_context,
                hints=hints,
                prior_drafts=prior_drafts,
            )

    embedder = HashEmbeddingBackend(dimension=32)
    rag_index = CASRAGIndex(embedder, similarity_threshold=0.0)
    rag_index.add_entry(
        RAGCaseEntry(
            decision_packet_ref="sha256:" + ("a" * 64),
            trinity_bundle_ref="sha256:" + ("b" * 64),
            run_id="run_rag_1",
            domain="economic",
            problem_text=ProblemFrameTextualizer.to_text(_problem_frame()),
            problem_summary="Reduce poverty under budget constraints",
            intervention_summary="tax_subsidy + income_tax",
            lesson_learned="gdp_change=0.02",
            confidence=0.9,
            indexed_at=datetime.utcnow().isoformat(),
        )
    )

    inner = RecordingDrafter()
    agent = MultiPassLLMDrafter(
        inner,
        config=MultiPassConfig(max_passes=1, rag_enabled=True, rag_similarity_threshold=0.0),
        rag_index=rag_index,
    )
    _ = run(agent.draft_policy(_problem_frame()))
    assert inner.last_hints
    assert any("SIMILAR PAST DECISIONS" in hint for hint in inner.last_hints)


def test_all_four_passes_execute() -> None:
    llm = SequenceLLM(
        [
            (
                '{"findings":[{"category":"side_effect","severity":"medium","description":"'
                'Risk to elderly households","suggested_fix":"Add targeted support",'
                '"anchor":"none"}],"confidence_adjustment":-0.05}'
            ),
            (
                '{"findings":[{"category":"constraint_conflict","severity":"low","description":"'
                'Minor parameter mismatch","suggested_fix":"Normalize rate format",'
                '"anchor":"field:interventions[0].params.rate"}],"confidence_adjustment":-0.01}'
            ),
            (
                '{"narrative":"Updated narrative after consolidation","interventions":[{"kind":"'
                'tax_subsidy"}],"rationale":"updated rationale","alternatives_considered":["x"],'
                '"confidence":0.66}'
            ),
        ]
    )
    agent = MultiPassLLMDrafter(
        MockDrafterAgent(),
        config=MultiPassConfig(max_passes=4, early_exit_confidence=0.99),
        llm_client=llm,
    )

    result = run(agent.draft_policy(_problem_frame()))

    assert llm.call_count == 3
    assert "Updated narrative after consolidation" in result.narrative


def test_early_exit_on_high_confidence() -> None:
    llm = SequenceLLM(['{"findings":[],"confidence_adjustment":0.0}'])
    agent = MultiPassLLMDrafter(
        HighConfidenceDrafter(),
        config=MultiPassConfig(max_passes=4, early_exit_confidence=0.9),
        llm_client=llm,
    )

    _ = run(agent.draft_policy(_problem_frame()))

    assert llm.call_count == 1


def test_early_exit_blocked_by_critical_finding() -> None:
    llm = SequenceLLM(
        [
            (
                '{"findings":[{"category":"budget_violation","severity":"critical","description":"'
                'Budget overflow by 40%","suggested_fix":"Reduce subsidy envelope",'
                '"anchor":"constraint:1"}],"confidence_adjustment":-0.2}'
            ),
            '{"findings":[],"confidence_adjustment":0.0}',
            (
                '{"narrative":"Consolidated critical fix","interventions":[{"kind":"tax_subsidy"}],'
                '"rationale":"reduced budget pressure","alternatives_considered":[],"confidence":0.55}'
            ),
        ]
    )
    agent = MultiPassLLMDrafter(
        HighConfidenceDrafter(),
        config=MultiPassConfig(
            max_passes=4,
            early_exit_confidence=0.9,
            finding_severity_threshold=FindingSeverity.HIGH,
        ),
        llm_client=llm,
    )

    result = run(agent.draft_policy(_problem_frame()))

    assert llm.call_count == 3
    assert "Consolidated critical fix" in result.narrative


def test_budget_exceeded_stops_pipeline() -> None:
    llm = SequenceLLM(
        ['{"findings":[],"confidence_adjustment":0.0}'],
        prompt_tokens=6000,
        completion_tokens=4000,
    )
    agent = MultiPassLLMDrafter(
        MockDrafterAgent(),
        config=MultiPassConfig(max_passes=4, budget_limit_usd=0.01, early_exit_confidence=0.99),
        llm_client=llm,
    )

    _ = run(agent.draft_policy(_problem_frame()))

    assert llm.call_count == 1


def test_findings_parsed_correctly() -> None:
    agent = MultiPassLLMDrafter(MockDrafterAgent(), config=MultiPassConfig(max_passes=1))
    findings, confidence_adjustment, parse_ok = agent._parse_findings(  # type: ignore[attr-defined]
        (
            '{"findings":[{"category":"unknown_cat","severity":"critical","description":"Critical'
            ' issue","suggested_fix":"Fix now","anchor":"field:x"}]}'
        ),
        pass_name="test",
    )

    assert parse_ok is True
    assert confidence_adjustment is None
    assert len(findings) == 1
    assert findings[0].category == FindingCategory.OTHER
    assert findings[0].severity == FindingSeverity.CRITICAL


def test_malformed_llm_response_handled() -> None:
    llm = SequenceLLM(["not-json-at-all"])
    agent = MultiPassLLMDrafter(
        MockDrafterAgent(),
        config=MultiPassConfig(max_passes=2),
        llm_client=llm,
    )

    result = run(agent.draft_policy(_problem_frame()))

    assert result.draft_id
    assert llm.call_count == 1


def test_consolidation_skipped_no_findings() -> None:
    llm = SequenceLLM(
        [
            '{"findings":[],"confidence_adjustment":0.0}',
            '{"findings":[],"confidence_adjustment":0.0}',
        ]
    )
    agent = MultiPassLLMDrafter(
        MockDrafterAgent(),
        config=MultiPassConfig(max_passes=4, early_exit_confidence=0.99),
        llm_client=llm,
    )

    _ = run(agent.draft_policy(_problem_frame()))

    assert llm.call_count == 2


def test_refine_draft_delegates() -> None:
    inner = MockDrafterAgent()
    agent = MultiPassLLMDrafter(inner, config=MultiPassConfig(max_passes=1))
    draft = run(inner.draft_policy(_problem_frame()))
    critique = CritiqueReport(
        report_id="rep_001",
        ir_ref="ir_001",
        problem_frame_ref=draft.problem_frame_ref,
        verdict="NEEDS_REVISION",
        issues=[
            CritiqueIssue(
                issue_id="issue_001",
                category=CritiqueCategory.COMPLETENESS,
                severity=CritiqueSeverity.WARNING,
                message="Missing coverage",
                suggestion="Add explicit intervention",
            )
        ],
        reflexion_hint="Improve population coverage",
    )

    _ = run(agent.refine_draft(draft, critique))

    assert inner.refine_count == 1


def test_memory_logging() -> None:
    llm = SequenceLLM(
        [
            (
                '{"findings":[{"category":"side_effect","severity":"medium","description":"'
                'Potential inequity","suggested_fix":"Add compensating measure","anchor":"none"}],'
                '"confidence_adjustment":-0.05}'
            )
        ]
    )
    memory = ShortTermMemory()
    agent = MultiPassLLMDrafter(
        MockDrafterAgent(),
        config=MultiPassConfig(max_passes=2, enable_memory_logging=True),
        memory=memory,
        llm_client=llm,
    )

    _ = run(agent.draft_policy(_problem_frame()))
    history = memory.get_history_as_text()

    assert "[SELF_CRITIQUE]" in history
    assert "Self-Critique:side_effects_check" in history


def test_pass3_code_verification_adds_findings_to_memory() -> None:
    llm = SequenceLLM(
        [
            '{"findings":[],"confidence_adjustment":0.0}',
            (
                '{"findings":[],"confidence_adjustment":0.0,'
                '"verification_code":"assert sum(intervention_rates) <= 0.1, '
                '\\\"Rates exceed threshold\\\""}'
            ),
            (
                '{"narrative":"Consolidated with verifier feedback","interventions":[{"kind":"'
                'tax_subsidy"}],"rationale":"updated","alternatives_considered":[],"confidence":0.6}'
            ),
        ]
    )
    memory = ShortTermMemory()
    agent = MultiPassLLMDrafter(
        MockDrafterAgent(),
        config=MultiPassConfig(
            max_passes=4,
            early_exit_confidence=0.99,
            code_verification_enabled=True,
        ),
        memory=memory,
        llm_client=llm,
    )

    result = run(agent.draft_policy(_problem_frame()))

    assert llm.call_count == 3
    assert "Consolidated with verifier feedback" in result.narrative
    history = memory.get_history_as_text()
    assert "code_verification" in history


def test_otel_spans_created(in_memory_exporter, monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_OTEL_ENABLED", "true")
    llm = SequenceLLM(
        [
            '{"findings":[],"confidence_adjustment":0.0}',
            '{"findings":[],"confidence_adjustment":0.0}',
        ]
    )
    agent = MultiPassLLMDrafter(
        MockDrafterAgent(),
        config=MultiPassConfig(max_passes=4, early_exit_confidence=0.99),
        llm_client=llm,
    )

    _ = run(agent.draft_policy(_problem_frame()))

    spans = in_memory_exporter.get_finished_spans()
    if not spans:
        pytest.skip("In-memory tracer provider is not active in this runtime")
    names = {span.name for span in spans}
    assert "drafter.multi_pass" in names
    assert "drafter.pass.naive_draft" in names
    assert "drafter.pass.side_effects_check" in names
    assert "drafter.pass.constraint_verify" in names


def test_max_passes_1_returns_naive() -> None:
    llm = SequenceLLM(['{"findings":[],"confidence_adjustment":0.0}'])
    agent = MultiPassLLMDrafter(
        MockDrafterAgent(),
        config=MultiPassConfig(max_passes=1),
        llm_client=llm,
    )

    result = run(agent.draft_policy(_problem_frame()))

    assert result.narrative
    assert llm.call_count == 0


def test_shadow_mode_returns_pass1_draft() -> None:
    llm = SequenceLLM(
        [
            '{"findings":[],"confidence_adjustment":0.0}',
            '{"findings":[],"confidence_adjustment":0.0}',
            (
                '{"narrative":"Should not be returned in shadow mode","interventions":[{"kind":"x"}],'
                '"rationale":"x","alternatives_considered":[],"confidence":0.9}'
            ),
        ]
    )
    agent = MultiPassLLMDrafter(
        MockDrafterAgent(),
        config=MultiPassConfig(max_passes=4, early_exit_confidence=0.99, shadow_mode=True),
        llm_client=llm,
    )

    result = run(agent.draft_policy(_problem_frame()))

    assert llm.call_count == 2
    assert "Should not be returned in shadow mode" not in result.narrative


def test_create_drafter_agent_uses_feature_flag(monkeypatch) -> None:
    class StubClient:
        async def generate(self, **kwargs: Any):
            del kwargs
            return _Response("{}", 1, 1)

    client = StubClient()
    monkeypatch.setenv("POLISYOS_DRAFTER_MULTIPASS_MODE", "off")
    agent_off = create_drafter_agent(client)
    assert isinstance(agent_off, LLMDrafterAgent)

    monkeypatch.setenv("POLISYOS_DRAFTER_MULTIPASS_MODE", "active")
    agent_active = create_drafter_agent(client)
    assert isinstance(agent_active, MultiPassLLMDrafter)
