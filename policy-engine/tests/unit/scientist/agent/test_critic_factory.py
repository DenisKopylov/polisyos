from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

import polisyos.scientist.agent.critic as critic_module
import polisyos.scientist.agent.formalizer as formalizer_module
from polisyos.core.llm.settlement import LLMManagedProducerOutcomeError
from polisyos.core.llm.traced_client import has_managed_prepared_producer_request
from polisyos.runtime.quality.design_generation import RecordingLLMClient
from polisyos.scientist.agent.critic import (
    LLMCriticAgent,
    MockCriticAgent,
    create_critic_agent,
    create_mock_problem_frame,
)
from polisyos.scientist.agent.formalizer import (
    FormalizerSchemaValidationError,
    LLMFormalizerAgent,
    MockFormalizerAgent,
    create_mock_draft,
)
from polisyos.scientist.agent.informed_critic import InformedCriticAgent
from polisyos.scientist.agent.protocols import CritiqueSeverity
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


class StubLLM:
    async def generate(self, **kwargs):
        del kwargs
        return type("Resp", (), {"content": "{}"})()


class JSONLLM:
    def __init__(self, payload: dict[str, object] | str) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    async def generate(self, **kwargs):
        self.calls.append(dict(kwargs))
        return GatewayLLMResponse(
            content=(self.payload if isinstance(self.payload, str) else json.dumps(self.payload)),
            usage=GatewayUsage(),
            raw={},
        )


class FailingLLM:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def generate(self, **kwargs):
        self.calls.append(dict(kwargs))
        raise RuntimeError("provider unavailable")


class BareMarkerJSONLLM(JSONLLM):
    def __init__(
        self,
        payload: dict[str, object] | str,
        *,
        delay_s: float = 0.0,
        error: Exception | None = None,
    ) -> None:
        super().__init__(payload)
        self.delay_s = delay_s
        self.error = error
        self.capability_requests: list[dict[str, object]] = []

    def _has_owned_prepared_transport(self, request_args: dict[str, object]) -> bool:
        self.capability_requests.append(dict(request_args))
        return True

    async def generate(self, **kwargs):
        self.calls.append(dict(kwargs))
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.error is not None:
            raise self.error
        return GatewayLLMResponse(
            content=(self.payload if isinstance(self.payload, str) else json.dumps(self.payload)),
            usage=GatewayUsage(),
            raw={},
        )


def _forbid_outer_wait_for(awaitable: object, *, timeout: float) -> object:
    del timeout
    close = getattr(awaitable, "close", None)
    if callable(close):
        close()
    raise AssertionError("managed critic request used an outer wait_for")


def test_create_critic_agent_returns_base_llm_critic_when_flag_off(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_INFORMED_CRITIC_ENABLED", "false")

    critic = create_critic_agent(StubLLM())

    assert isinstance(critic, LLMCriticAgent)


def test_create_critic_agent_wraps_informed_critic_when_flag_on(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_INFORMED_CRITIC_ENABLED", "true")

    critic = create_critic_agent(StubLLM())

    assert isinstance(critic, InformedCriticAgent)


def test_create_critic_agent_honors_mock_mode(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_INFORMED_CRITIC_ENABLED", "false")
    monkeypatch.setenv("POLISYOS_CRITIC_MODE", "mock")

    critic = create_critic_agent(StubLLM())

    assert isinstance(critic, MockCriticAgent)


@pytest.mark.asyncio
async def test_llm_critic_suppresses_stale_schema_blockers_from_valid_bundle() -> None:
    draft = create_mock_draft(
        interventions=[
            {
                "intervention_id": "adaptive_support",
                "kind": "adaptive_agent",
                "params": {
                    "observation_space": ["agents.income", "agents.skill_level"],
                    "action_space": {
                        "type": "continuous",
                        "affects": ["agents.income"],
                    },
                    "utility": "maximize_survival_and_fairness",
                    "learning_rate": "0.05",
                    "stochastic": True,
                },
            }
        ]
    )
    bundle = await MockFormalizerAgent().formalize(draft)
    llm = JSONLLM(
        {
            "verdict": "REJECT",
            "issues": [
                {
                    "issue_id": "stale_problem_frame_ref",
                    "category": "SCHEMA",
                    "severity": "BLOCKER",
                    "message": "Missing required policy_spec.problem_frame_ref",
                    "location": "policy_spec.problem_frame_ref",
                },
                {
                    "issue_id": "stale_adaptive_agent",
                    "category": "COMPLIANCE",
                    "severity": "BLOCKER",
                    "message": "adaptive_agent is unsupported by the runtime",
                    "location": "policy_spec.interventions[0].kind",
                },
                {
                    "issue_id": "stale_weight",
                    "category": "SCHEMA",
                    "severity": "BLOCKER",
                    "message": "Objective weight must be numeric, not a string",
                    "location": "problem_frame.objectives[0].weight",
                },
                {
                    "issue_id": "stale_target",
                    "category": "SCHEMA",
                    "severity": "BLOCKER",
                    "message": "Objective target cannot be null",
                    "location": "problem_frame.objectives[0].target",
                },
                {
                    "issue_id": "stale_success_criteria",
                    "category": "SCHEMA",
                    "severity": "BLOCKER",
                    "message": "success_criteria is an empty array and must be omitted",
                    "location": "problem_frame.success_criteria",
                },
                {
                    "issue_id": "stale_boundary_assumption",
                    "category": "SCHEMA",
                    "severity": "BLOCKER",
                    "message": "assumption_type boundary is invalid; allowed values are structural",
                    "location": "model_spec.assumptions[2].assumption_type",
                },
                {
                    "issue_id": "stale_tax_subsidy_semantics",
                    "category": "COMPLIANCE",
                    "severity": "BLOCKER",
                    "message": (
                        "Multiple interventions use tax_subsidy for non-tax "
                        "instruments; use direct_transfer."
                    ),
                    "location": "policy_spec.interventions[1].kind",
                },
                {
                    "issue_id": "high_rate",
                    "category": "FEASIBILITY",
                    "severity": "WARNING",
                    "message": "Subsidy rate may be fiscally aggressive",
                    "location": "policy_spec.interventions[0].params.rate",
                },
            ],
            "alignment_score": 0.82,
            "completeness_score": 0.85,
            "overall_quality": 0.8,
            "reflexion_hint": "Fix schema blockers first.",
        }
    )

    report = await LLMCriticAgent(llm).critique(bundle, create_mock_problem_frame())

    assert report.verdict == "APPROVE"
    assert report.metadata["suppressed_stale_contract_issue_count"] == 7
    assert [issue.issue_id for issue in report.issues] == ["high_rate"]
    assert not any(issue.severity == CritiqueSeverity.BLOCKER for issue in report.issues)


@pytest.mark.asyncio
async def test_llm_critic_falls_back_when_gateway_fails(monkeypatch) -> None:
    monkeypatch.setenv("POLISYOS_CRITIC_LLM_TIMEOUT_S", "1")
    draft = create_mock_draft()
    bundle = await MockFormalizerAgent().formalize(draft)
    llm = FailingLLM()

    report = await LLMCriticAgent(llm).critique(bundle, create_mock_problem_frame())

    assert llm.calls
    assert llm.calls[0]["timeout"] == 1.0
    assert report.report_id.startswith("critique_")
    assert report.problem_frame_ref
    assert report.metadata["generator_path"] == "degraded_mock_fallback"
    assert report.metadata["degraded_reason"] == "llm_call_failed"


@pytest.mark.asyncio
async def test_critic_ignores_untrusted_client_managed_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = await MockFormalizerAgent().formalize(create_mock_draft())
    client = BareMarkerJSONLLM(
        {
            "report_id": "critique_managed_slow_admission",
            "verdict": "APPROVE",
            "issues": [],
            "alignment_score": 0.9,
            "completeness_score": 0.8,
            "overall_quality": 0.85,
        },
        delay_s=0.02,
    )
    agent = LLMCriticAgent(client)
    agent._timeout_s = 0.001
    observed_outer_timeouts: list[float] = []

    async def _record_outer_wait(awaitable: object, *, timeout: float) -> object:
        observed_outer_timeouts.append(timeout)
        return await awaitable  # type: ignore[misc]

    monkeypatch.setattr(
        critic_module,
        "asyncio",
        SimpleNamespace(wait_for=_record_outer_wait),
    )

    report = await agent.critique(bundle, create_mock_problem_frame())

    assert report.report_id == "critique_managed_slow_admission"
    assert report.verdict == "APPROVE"
    assert len(client.calls) == 1
    assert client.capability_requests == []
    assert client.calls[0]["timeout"] == 0.001
    assert observed_outer_timeouts == [5.001]


@pytest.mark.asyncio
async def test_critic_propagates_managed_settlement_failure_without_fallback() -> None:
    bundle = await MockFormalizerAgent().formalize(create_mock_draft())
    expected_error = LLMManagedProducerOutcomeError("managed_settlement_not_committed")
    client = BareMarkerJSONLLM("{}", error=expected_error)

    with pytest.raises(LLMManagedProducerOutcomeError) as exc_info:
        await LLMCriticAgent(client).critique(bundle, create_mock_problem_frame())

    assert exc_info.value is expected_error
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_formalizer_and_critic_use_exact_managed_owner_and_ledger_ack(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "0")
    draft = create_mock_draft(draft_id="draft_exact_managed_owner")
    expected_bundle = await MockFormalizerAgent().formalize(draft)
    response_texts = [
        expected_bundle.model_dump_json(),
        json.dumps(
            {
                "report_id": "critique_exact_managed_owner",
                "verdict": "APPROVE",
                "issues": [],
                "alignment_score": 0.9,
                "completeness_score": 0.8,
                "overall_quality": 0.85,
            }
        ),
        "not a JSON object",
        "not a JSON object",
    ]
    raw_calls: list[dict[str, object]] = []

    async def _single_managed_dispatch(self, request_args, *, before_dispatch):
        del self
        await asyncio.sleep(0.02)
        before_dispatch()
        raw_calls.append(dict(request_args))
        response_index = len(raw_calls) - 1
        return GatewayLLMResponse(
            content=response_texts[response_index],
            usage=GatewayUsage(
                prompt_tokens=5,
                completion_tokens=7,
                cost_usd=0.001,
                cost_status="known",
                usage_status="known",
            ),
            model="managed-fixture-model",
            provider="declared-fixture",
            raw={},
        )

    monkeypatch.setattr(GatewayLLMClient, "_generate_single_dispatch", _single_managed_dispatch)
    run_id = "n4-managed-owner-test"
    budget_key = f"nl-run:{run_id}"
    ledger = FileBudgetLedger(tmp_path / "managed-owner-ledger.json")
    settlement_store = BudgetMiddleware(
        BudgetState(limits={budget_key: BudgetLimit(key=budget_key, max_usd=Decimal("10"))}),
        ledger=ledger,
    )
    run_binding = BudgetLedgerProducerRunBinding(
        run_id=run_id,
        tenant_id="tenant-managed-test",
        cell_id="cell-managed-test",
        profile_id="profile-managed-test",
        control_job_id="job-managed-test",
    )
    observed_events: list[dict[str, object]] = []
    verifier_results: list[bool] = []

    def _observe_exact_verifier(client: object, request: object) -> bool:
        result = has_managed_prepared_producer_request(client, request)
        verifier_results.append(result)
        return result

    monkeypatch.setattr(
        formalizer_module,
        "has_managed_prepared_producer_request",
        _observe_exact_verifier,
    )
    monkeypatch.setattr(
        critic_module,
        "has_managed_prepared_producer_request",
        _observe_exact_verifier,
    )
    monkeypatch.setattr(
        formalizer_module,
        "asyncio",
        SimpleNamespace(wait_for=_forbid_outer_wait_for),
    )
    monkeypatch.setattr(
        critic_module,
        "asyncio",
        SimpleNamespace(wait_for=_forbid_outer_wait_for),
    )

    inner = None
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
                model_name="managed-fixture-model",
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
                model_id="managed-fixture-model",
                producer_problem_ref="sha256:" + "a" * 64,
            )
            formalizer = LLMFormalizerAgent(recorder, model_name="managed-fixture-model")
            formalizer._timeout_s = 0.001
            formalized = await formalizer.formalize(draft)
            assert formalized == expected_bundle

            critic = LLMCriticAgent(recorder, model_name="managed-fixture-model")
            critic._timeout_s = 0.001
            report = await critic.critique(formalized, create_mock_problem_frame())
            assert report.report_id == "critique_exact_managed_owner"
            assert report.metadata["generator_path"] == "model_generated"

            conservative_report = await critic.critique(formalized, create_mock_problem_frame())
            assert conservative_report.verdict == "NEEDS_REVISION"
            assert [issue.issue_id for issue in conservative_report.issues] == ["parse_error"]
            assert conservative_report.metadata["degraded_reason"] == "llm_parse_failed"

            with pytest.raises(FormalizerSchemaValidationError) as exc_info:
                await formalizer.formalize(draft)
            assert exc_info.value.failure["retryable"] is False
            assert len(recorder.calls) == 4
            await inner.aclose()

    assert verifier_results == [True, True, True, True]
    assert len(raw_calls) == 4
    assert all(call["timeout"] == 0.001 for call in raw_calls)
    assert len(observed_events) == 4
    for event in observed_events:
        event_id = str(event["event_id"])
        assert event["settlement_status"] == "committed"
        assert event["durability"] == "ledger"
        assert event["receipts"] == [event_id]
        durable = settlement_store.resolve_producer_event_safe(event_id)
        assert durable is not None
        assert durable.status == "committed"
    durable_events = settlement_store.list_producer_events_for_run_safe(run_binding)
    assert len(durable_events) == 4
    assert all(event.status == "committed" for event in durable_events)


@pytest.mark.asyncio
async def test_llm_critic_parses_think_prefixed_json() -> None:
    bundle = await MockFormalizerAgent().formalize(create_mock_draft())
    raw = "<think>critic reasoning</think>" + json.dumps(
        {
            "report_id": "critique_think_prefixed",
            "verdict": "APPROVE",
            "issues": [],
            "alignment_score": 0.9,
            "completeness_score": 0.8,
            "overall_quality": 0.85,
        }
    )

    report = await LLMCriticAgent(JSONLLM(raw)).critique(
        bundle,
        create_mock_problem_frame(),
    )

    assert report.report_id == "critique_think_prefixed"
    assert report.verdict == "APPROVE"
    assert report.metadata["generator_path"] == "model_generated"
    assert report.metadata["raw_llm_response"] == raw


@pytest.mark.asyncio
async def test_llm_critic_invalid_json_returns_conservative_parse_error() -> None:
    bundle = await MockFormalizerAgent().formalize(create_mock_draft())

    report = await LLMCriticAgent(JSONLLM("no object exists")).critique(
        bundle,
        create_mock_problem_frame(),
    )

    assert report.verdict == "NEEDS_REVISION"
    assert [issue.issue_id for issue in report.issues] == ["parse_error"]
    assert report.metadata["generator_path"] == "degraded_mock_fallback"
    assert report.metadata["degraded_reason"] == "llm_parse_failed"
    assert report.metadata["raw_llm_response"] == "no object exists"


@pytest.mark.asyncio
async def test_explicit_mock_critic_is_stamped_non_promotable() -> None:
    bundle = await MockFormalizerAgent().formalize(create_mock_draft())

    report = await MockCriticAgent().critique(bundle, create_mock_problem_frame())

    assert report.metadata["generator_path"] == "degraded_mock_fallback"
