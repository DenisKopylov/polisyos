from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import pytest

from polisyos.scientist.agent.drafter import (
    FindingCategory,
    FindingSeverity,
    LLMDrafterAgent,
    MockDrafterAgent,
    MultiPassConfig,
    MultiPassLLMDrafter,
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


@pytest.mark.parametrize(
    "outcome",
    [
        "late_success",
        "managed_after_prepare_retry",
        "postprocess_failure",
        "unknown_settlement",
        "invalid_critique",
        "invalid_draft",
    ],
)
def test_actual_managed_drafter_has_no_outer_timeout_retry_or_fallback(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    import json
    from decimal import Decimal
    from types import SimpleNamespace

    import polisyos.scientist.agent._drafter_orchestrator as orchestrator_module
    from polisyos.core.llm.settlement import LLMManagedProducerOutcomeError
    from polisyos.runtime.quality.design_generation import RecordingLLMClient
    from polisyos.scientist.agent._drafter_orchestrator import (
        ManagedN4InvocationError,
        ManagedN4ResponseInvalidError,
    )
    from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
        FileBudgetLedger,
    )
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
    from polisyos.scientist.orchestration.llm.factory import (
        GatewayLLMConfig,
        create_traced_gateway_client,
        gateway_cache_reuse_scope,
    )
    from polisyos.scientist.orchestration.llm.gateway_client import (
        GatewayLLMClient,
        GatewayLLMResponse,
        GatewayUsage,
    )

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "0")

    async def _forbid_outer_wait_for(*_args, **_kwargs):
        raise AssertionError("managed N4 must use the transport-owned deadline")

    monkeypatch.setattr(
        orchestrator_module,
        "asyncio",
        SimpleNamespace(wait_for=_forbid_outer_wait_for),
    )

    frame = _problem_frame()
    valid_draft = json.dumps(
        {
            "draft_id": "managed-drafter-fixture",
            "problem_frame_ref": frame.frame_id,
            "narrative": "A cautious candidate plan.",
            "interventions": [{"kind": "tax_subsidy"}],
            "rationale": "Constrained candidate intervention.",
            "confidence": 0.5,
        }
    )
    if outcome == "invalid_draft":
        response_texts = ["not JSON"]
    elif outcome == "invalid_critique":
        response_texts = [valid_draft, "not JSON"]
    else:
        response_texts = [valid_draft, '{"findings":[],"confidence_adjustment":0.0}']
    raw_calls: list[dict[str, object]] = []
    transport_timeouts: list[float] = []
    prepare_attempts: list[tuple[str, int]] = []

    if outcome == "managed_after_prepare_retry":
        issue_producer_request = RecordingLLMClient._issue_producer_request

        def _fail_first_managed_prepare(
            self, *, stage: str, attempt: int, instance: str | None, request: object
        ) -> dict[str, object]:
            prepare_attempts.append((stage, attempt))
            if stage == "drafter_multipass" and attempt == 0:
                raise ValueError("transient pre-issue fixture failure")
            return issue_producer_request(
                self,
                stage=stage,
                attempt=attempt,
                instance=instance,
                request=request,
            )

        monkeypatch.setattr(
            RecordingLLMClient,
            "_issue_producer_request",
            _fail_first_managed_prepare,
        )
    elif outcome == "postprocess_failure":
        estimate_cost = MultiPassLLMDrafter._estimate_cost
        critique_response = '{"findings":[],"confidence_adjustment":0.0}'

        def _fail_postprocess(self, **kwargs):
            if kwargs.get("raw_response") == critique_response:
                raise RuntimeError("transient post-settlement consumer fixture failure")
            return estimate_cost(self, **kwargs)

        monkeypatch.setattr(MultiPassLLMDrafter, "_estimate_cost", _fail_postprocess)

    async def _dispatch(self, request_args, *, before_dispatch):
        transport_timeouts.append(self.timeout_s)
        call_index = len(raw_calls)
        raw_calls.append(dict(request_args))
        if call_index == 1:
            await asyncio.sleep(0.02)
        before_dispatch()
        usage = (
            GatewayUsage()
            if outcome == "unknown_settlement" and call_index == 1
            else GatewayUsage(
                prompt_tokens=5,
                completion_tokens=7,
                cost_usd=0.001,
                cost_status="known",
                usage_status="known",
            )
        )
        return GatewayLLMResponse(
            content=response_texts[call_index],
            usage=usage,
            model="managed-drafter-fixture",
            provider="declared-fixture",
            raw={},
        )

    monkeypatch.setattr(GatewayLLMClient, "_generate_single_dispatch", _dispatch)
    run_id = f"managed-drafter-{outcome}"
    budget_key = f"nl-run:{run_id}"
    ledger = FileBudgetLedger(tmp_path / f"{outcome}-ledger.json")
    settlement_store = BudgetMiddleware(
        BudgetState(limits={budget_key: BudgetLimit(key=budget_key, max_usd=Decimal("10"))}),
        ledger=ledger,
    )
    run_binding = BudgetLedgerProducerRunBinding(
        run_id=run_id,
        control_job_id=f"job-{run_id}",
        tenant_id="tenant",
        cell_id="tenant/cell",
        profile_id="managed-drafter-fixture",
    )
    observed_events: list[dict[str, object]] = []

    async def _run_managed() -> tuple[object, RecordingLLMClient, object]:
        with settlement_store.producer_run_binding_scope(run_binding, control_job_attempt=1):
            with gateway_cache_reuse_scope(
                authorizer=None,
                principal=None,
                context=None,
                cache=None,
                run_id=run_id,
                settlement_store=settlement_store,
                reuse_guard=lambda operation: operation(),
                validate_admission=lambda: None,
                intent_observer=lambda *_: None,
                validate_direct_dispatch=lambda _: None,
            ):
                inner = create_traced_gateway_client(
                    model_name="managed-drafter-fixture",
                    call_observer=observed_events.append,
                    config=GatewayLLMConfig(
                        base_url="http://fixture.invalid/v1",
                        api_key="fixture-key",
                        timeout_s=30.0,
                        max_retries=0,
                        cache_maxsize=0,
                        enable_prompt_sanitizer=False,
                    ),
                )
                assert inner is not None
                recorder = RecordingLLMClient(
                    inner,
                    model_id="managed-drafter-fixture",
                    producer_problem_ref="sha256:" + "a" * 64,
                )
                agent = create_drafter_agent(
                    recorder,
                    model_name="managed-drafter-fixture",
                    config=MultiPassConfig(
                        max_passes=2,
                        early_exit_confidence=1.0,
                        pass_timeout_s=0.001,
                        pass_retry_count=2,
                        constitution_enabled=False,
                        rag_enabled=False,
                    ),
                    multipass_mode="active",
                )
                try:
                    try:
                        result = await agent.draft_policy(frame)
                        outcome_value: object = result
                    except Exception as exc:
                        outcome_value = exc
                    return outcome_value, recorder, ledger.snapshot()
                finally:
                    await inner.aclose()

    result, recorder, snapshot = run(_run_managed())
    expected_calls = 1 if outcome == "invalid_draft" else 2
    assert len(raw_calls) == expected_calls
    assert len(recorder.calls) == expected_calls
    assert len(snapshot.producer_settlements) == expected_calls
    assert len(observed_events) == expected_calls
    assert all("pass_timeout_s" not in call for call in raw_calls)
    assert all("timeout" not in call for call in raw_calls)
    assert transport_timeouts == [30.0] * expected_calls
    if outcome == "managed_after_prepare_retry":
        assert prepare_attempts == [
            ("draft", 0),
            ("drafter_multipass", 0),
            ("drafter_multipass", 1),
        ]

    if outcome in {"late_success", "managed_after_prepare_retry"}:
        assert not isinstance(result, Exception)
        assert all(call.status == "success" for call in recorder.calls)
        assert all(
            settlement.status == "committed"
            for settlement in snapshot.producer_settlements.values()
        )
    elif outcome == "unknown_settlement":
        assert isinstance(result, LLMManagedProducerOutcomeError)
        assert result.reason == "managed_settlement_not_committed"
        statuses = {settlement.status for settlement in snapshot.producer_settlements.values()}
        assert statuses == {"committed", "unknown"}
    elif outcome == "postprocess_failure":
        assert isinstance(result, ManagedN4InvocationError)
        assert all(call.status == "success" for call in recorder.calls)
        assert all(
            settlement.status == "committed"
            for settlement in snapshot.producer_settlements.values()
        )
    else:
        assert isinstance(result, ManagedN4ResponseInvalidError)
        assert all(call.status == "success" for call in recorder.calls)


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


def test_unmanaged_drafter_pass_keeps_timeout_retry() -> None:
    llm = SequenceLLM(['{"findings":[],"confidence_adjustment":0.0}'], fail_calls={1})
    agent = MultiPassLLMDrafter(
        MockDrafterAgent(),
        config=MultiPassConfig(max_passes=2, pass_retry_count=1, pass_timeout_s=1.0),
        llm_client=llm,
    )

    result = run(agent.draft_policy(_problem_frame()))

    assert result.draft_id
    assert llm.call_count == 2


def test_multipass_drafter_accepts_injected_observability(monkeypatch) -> None:
    class _Span:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return None

        def set_attribute(self, name: str, value: object) -> None:
            del name, value

        def set_status(self, status: object) -> None:
            del status

        def record_exception(self, exc: BaseException) -> None:
            del exc

    class _Tracer:
        def __init__(self) -> None:
            self.names: list[str] = []

        def start_as_current_span(self, name: str, attributes=None):
            del attributes
            self.names.append(name)
            return _Span()

    class _Metrics:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def record_constitution_generated(
            self,
            *,
            domain: str,
            duration_seconds: float,
            section_counts: dict[str, int],
        ) -> None:
            self.calls.append(
                {
                    "domain": domain,
                    "duration_seconds": duration_seconds,
                    "section_counts": section_counts,
                }
            )

    monkeypatch.setattr(
        "polisyos.scientist.agent._drafter_orchestrator._default_tracer",
        lambda: (_ for _ in ()).throw(
            AssertionError("global tracer lookup should not run when tracer is injected")
        ),
    )
    monkeypatch.setattr(
        "polisyos.scientist.agent._drafter_orchestrator._default_metrics",
        lambda: (_ for _ in ()).throw(
            AssertionError("global metrics lookup should not run when metrics are injected")
        ),
    )
    monkeypatch.setattr(
        "polisyos.scientist.agent._drafter_passes._default_tracer",
        lambda: (_ for _ in ()).throw(
            AssertionError("global tracer lookup should not run when tracer is injected")
        ),
    )

    tracer = _Tracer()
    metrics = _Metrics()
    llm = SequenceLLM(['{"findings":[],"confidence_adjustment":0.0}'])
    agent = MultiPassLLMDrafter(
        MockDrafterAgent(),
        config=MultiPassConfig(
            max_passes=2,
            constitution_enabled=True,
            early_exit_confidence=0.99,
        ),
        llm_client=llm,
        tracer=tracer,
        metrics=metrics,
    )

    result = run(agent.draft_policy(_problem_frame()))

    assert result.problem_frame_ref == "pf_multipass_001"
    assert tracer.names
    assert metrics.calls


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
                '\\"Rates exceed threshold\\""}'
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
