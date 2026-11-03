"""Tests for LLMBudgetEnforcer."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polisyos.scientist.orchestration.engine.budget import (
    BudgetExhaustedError,
    BudgetLimit,
    BudgetState,
)
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer


def _make_response_mock(prompt_tokens: int = 100, completion_tokens: int = 50):
    """Create a mock LLM response with usage data."""
    response = MagicMock()
    response.usage = MagicMock()
    response.usage.prompt_tokens = prompt_tokens
    response.usage.completion_tokens = completion_tokens
    response.usage.total_tokens = prompt_tokens + completion_tokens
    response.content = "test response"
    response.model = "test-model"
    # Make raw dict for extract_llm_response_data
    response.raw = {
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
    return response


def _make_response_with_provider_cost(
    *,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    cost_usd: float = 0.0003,
):
    response = _make_response_mock(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    response.usage.cost_usd = cost_usd
    response.raw["usage"]["total_cost_usd"] = cost_usd
    return response


class _FakeMetricRecorder:
    def __init__(self) -> None:
        self.records: list[tuple[object, dict[str, str]]] = []

    def record(self, value: object, attrs: dict[str, str]) -> None:
        self.records.append((value, attrs))


class _FakeMetricAdder:
    def __init__(self) -> None:
        self.records: list[tuple[object, dict[str, str]]] = []

    def add(self, value: object, attrs: dict[str, str]) -> None:
        self.records.append((value, attrs))


class _FakeMetricSetter:
    def __init__(self) -> None:
        self.records: list[tuple[object, dict[str, str]]] = []

    def set(self, value: object, attrs: dict[str, str]) -> None:
        self.records.append((value, attrs))


class _FakeBudgetMetrics:
    def __init__(self) -> None:
        self.llm_cost_usd = _FakeMetricRecorder()
        self.llm_calls_total = _FakeMetricAdder()
        self.llm_tokens_total = _FakeMetricAdder()
        self.scientist_llm_budget_utilization = _FakeMetricSetter()
        self.scientist_llm_cost_anomalies_total = _FakeMetricAdder()
        self.llm_latency_ms = _FakeMetricRecorder()


class _FakeOperationalMonitor:
    def __init__(self) -> None:
        self.alerts: list[dict[str, object]] = []

    def record_alert(
        self,
        *,
        alert_type: str,
        severity: str = "warn",
        workflow_id: str | None = None,
        run_id: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        self.alerts.append(
            {
                "alert_type": alert_type,
                "severity": severity,
                "workflow_id": workflow_id,
                "run_id": run_id,
                "details": details or {},
            }
        )


class TestLLMBudgetEnforcer:
    @pytest.mark.asyncio
    async def test_generate_within_budget(self):
        """Should pass through when budget is not exceeded."""
        client = AsyncMock()
        response = _make_response_mock()
        client.generate.return_value = response

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("100.00"))},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="test-model",
        )

        result = await enforcer.generate(system="test", user="hello")
        assert result is response
        client.generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_exceeds_budget(self):
        """Should raise BudgetExhaustedError when budget would be exceeded."""
        client = AsyncMock()

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("0.0001"))},
            spent={"run": Decimal("0.0001")},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="test-model",
        )

        with pytest.raises(BudgetExhaustedError):
            await enforcer.generate(system="test", user="hello", max_tokens=1000)

        client.generate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_records_spend_after_call(self):
        """After a successful call, spend should be recorded."""
        client = AsyncMock()
        response = _make_response_mock(prompt_tokens=100, completion_tokens=50)
        client.generate.return_value = response

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("100.00"))},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="test-model",
        )

        await enforcer.generate(system="test", user="hello")
        assert budget_state.spent.get("run", Decimal(0)) >= Decimal(0)

    @pytest.mark.asyncio
    async def test_post_record_prefers_provider_reported_cost(self):
        client = AsyncMock()
        response = _make_response_with_provider_cost(cost_usd=0.0006)
        client.generate.return_value = response

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("1.00"))},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        )

        await enforcer.generate(system="test", user="hello")
        assert budget_state.spent["run"] == Decimal("0.0006")

    @pytest.mark.asyncio
    async def test_post_record_falls_back_to_reserved_cost_when_accounting_breaks(self):
        client = AsyncMock()
        response = _make_response_mock(prompt_tokens=10, completion_tokens=5)
        client.generate.return_value = response

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("1.00"))},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="test-model",
        )

        with patch.object(
            enforcer,
            "_resolve_actual_cost",
            side_effect=ValueError("bad accounting payload"),
        ):
            await enforcer.generate(system="test", user="hello", max_tokens=10)

        assert budget_state.spent["run"] > Decimal("0")
        assert budget_state.reserved["run"] == Decimal("0")

    @pytest.mark.asyncio
    async def test_pre_check_counts_explicit_messages(self):
        client = AsyncMock()
        client.generate.return_value = _make_response_mock(prompt_tokens=1, completion_tokens=1)

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("1.00"))},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        )

        with patch(
            "polisyos.scientist.orchestration.llm.token_estimator.estimate_request_tokens",
            return_value=123,
        ) as estimate_mock:
            await enforcer.generate(
                messages=[
                    {"role": "system", "content": "sys"},
                    {"role": "user", "content": "hello"},
                ],
                max_tokens=20,
            )

        estimate_mock.assert_called_once()
        assert estimate_mock.call_args.kwargs["messages"] == [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hello"},
        ]

    @pytest.mark.asyncio
    async def test_audit_log_on_budget_check(self):
        """Audit log should receive reservation and compatibility events."""
        client = AsyncMock()
        response = _make_response_mock()
        client.generate.return_value = response

        audit = MagicMock()
        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("100.00"))},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="test-model",
            audit_log=audit,
        )

        await enforcer.generate(system="test", user="hello")
        reserved_calls = [
            c for c in audit.append.call_args_list if c[1].get("action") == "BUDGET_RESERVED"
        ]
        check_calls = [
            c for c in audit.append.call_args_list if c[1].get("action") == "BUDGET_CHECK"
        ]
        committed_calls = [
            c for c in audit.append.call_args_list if c[1].get("action") == "BUDGET_COMMITTED"
        ]
        assert len(reserved_calls) >= 1
        assert len(check_calls) >= 1
        assert len(committed_calls) >= 1

    @pytest.mark.asyncio
    async def test_audit_log_on_budget_exceeded(self):
        """Audit log should receive BUDGET_EXCEEDED event."""
        client = AsyncMock()
        audit = MagicMock()

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("0.0001"))},
            spent={"run": Decimal("0.0001")},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="test-model",
            audit_log=audit,
        )

        with pytest.raises(BudgetExhaustedError):
            await enforcer.generate(system="test", user="hello", max_tokens=1000)

        calls = [c for c in audit.append.call_args_list if c[1].get("action") == "BUDGET_EXCEEDED"]
        assert len(calls) >= 1

    @pytest.mark.asyncio
    async def test_strips_internal_kwargs(self):
        """Internal kwargs starting with _ should not be passed to the client."""
        client = AsyncMock()
        response = _make_response_mock()
        client.generate.return_value = response

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("100.00"))},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
        )

        await enforcer.generate(system="test", _run_id="r-001", _prompt_tokens_estimate=50)
        kwargs = client.generate.call_args[1]
        assert "_run_id" not in kwargs
        assert "_prompt_tokens_estimate" not in kwargs

    def test_budget_state_property(self):
        client = MagicMock()
        bs = BudgetState()
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=bs,
            budget_keys=["run"],
        )
        assert enforcer.budget_state is bs

    @pytest.mark.asyncio
    async def test_parallel_calls_do_not_overspend_reserved_budget(self):
        started = asyncio.Event()
        release = asyncio.Event()
        response = _make_response_with_provider_cost(cost_usd=1.0)

        async def _generate(**kwargs):
            started.set()
            await release.wait()
            return response

        client = AsyncMock()
        client.generate.side_effect = _generate

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("1.0"))},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="test-model",
        )

        with patch(
            "polisyos.scientist.orchestration.llm.budget_enforcer.estimate_llm_cost_usd",
            return_value=1.0,
        ):
            first_task = asyncio.create_task(enforcer.generate(system="sys", user="one"))
            await started.wait()
            second_task = asyncio.create_task(enforcer.generate(system="sys", user="two"))
            await asyncio.sleep(0)
            release.set()
            first_result, second_result = await asyncio.gather(
                first_task,
                second_task,
                return_exceptions=True,
            )

        assert first_result is response
        assert isinstance(second_result, BudgetExhaustedError)
        assert budget_state.spent["run"] == Decimal("1.0")
        assert budget_state.reserved.get("run", Decimal(0)) == Decimal(0)

    @pytest.mark.asyncio
    async def test_releases_reservation_when_generate_raises(self):
        client = AsyncMock()
        client.generate.side_effect = RuntimeError("boom")
        audit = MagicMock()

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("1.0"))},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="test-model",
            audit_log=audit,
        )

        with (
            patch(
                "polisyos.scientist.orchestration.llm.budget_enforcer.estimate_llm_cost_usd",
                return_value=0.4,
            ),
            pytest.raises(RuntimeError, match="boom"),
        ):
            await enforcer.generate(system="sys", user="hello")

        assert budget_state.spent.get("run", Decimal(0)) == Decimal(0)
        assert budget_state.reserved.get("run", Decimal(0)) == Decimal(0)
        release_calls = [
            c for c in audit.append.call_args_list if c[1].get("action") == "BUDGET_RELEASED"
        ]
        assert len(release_calls) >= 1

    @pytest.mark.asyncio
    async def test_releases_reservation_when_task_is_cancelled(self):
        started = asyncio.Event()

        async def _generate(**kwargs):
            started.set()
            await asyncio.Future()

        client = AsyncMock()
        client.generate.side_effect = _generate

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("1.0"))},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="test-model",
        )

        with patch(
            "polisyos.scientist.orchestration.llm.budget_enforcer.estimate_llm_cost_usd",
            return_value=0.4,
        ):
            task = asyncio.create_task(enforcer.generate(system="sys", user="hello"))
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        assert budget_state.spent.get("run", Decimal(0)) == Decimal(0)
        assert budget_state.reserved.get("run", Decimal(0)) == Decimal(0)

    @pytest.mark.asyncio
    async def test_actual_cost_commit_reconciles_estimate_delta(self):
        client = AsyncMock()
        response = _make_response_with_provider_cost(cost_usd=0.6)
        client.generate.return_value = response

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("2.0"))},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="test-model",
        )

        with patch(
            "polisyos.scientist.orchestration.llm.budget_enforcer.estimate_llm_cost_usd",
            return_value=0.4,
        ):
            await enforcer.generate(system="sys", user="hello")

        assert budget_state.spent["run"] == Decimal("0.6")
        assert budget_state.reserved.get("run", Decimal(0)) == Decimal(0)

    @pytest.mark.asyncio
    async def test_accepts_injected_metrics_and_operational_monitor(self, monkeypatch):
        async_client = AsyncMock()
        async_client.generate.return_value = _make_response_with_provider_cost(cost_usd=0.6)

        metrics = _FakeBudgetMetrics()
        monitor = _FakeOperationalMonitor()
        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("2.0"))},
        )
        enforcer = LLMBudgetEnforcer(
            client=async_client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="test-model",
            run_id="run-42",
            metrics=metrics,
            operational_monitor=monitor,
        )

        def _fail_get_metrics():
            raise AssertionError("global metrics lookup should not be used")

        def _fail_get_monitor():
            raise AssertionError("global operational monitor should not be used")

        monkeypatch.setattr("polisyos.core.observability.get_metrics", _fail_get_metrics)
        monkeypatch.setattr(
            "polisyos.scientist.orchestration.llm.budget_enforcer.get_operational_monitor",
            _fail_get_monitor,
        )

        with patch(
            "polisyos.scientist.orchestration.llm.budget_enforcer.CostAnomalyDetector.check",
            return_value=True,
        ):
            await enforcer.generate(system="sys", user="hello")

        assert metrics.llm_cost_usd.records
        assert metrics.llm_calls_total.records
        assert metrics.llm_tokens_total.records
        assert metrics.scientist_llm_budget_utilization.records
        assert metrics.scientist_llm_cost_anomalies_total.records
        assert metrics.llm_latency_ms.records
        assert monitor.alerts == [
            {
                "alert_type": "budget_anomaly",
                "severity": "warn",
                "workflow_id": None,
                "run_id": "run-42",
                "details": {
                    "model_id": "test-model",
                    "cost_usd": 0.6,
                },
            }
        ]

    @pytest.mark.asyncio
    async def test_post_record_failure_does_not_over_credit_budget(self):
        client = AsyncMock()
        response = _make_response_with_provider_cost(cost_usd=0.6)
        client.generate.return_value = response

        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("2.0"))},
        )
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=budget_state,
            budget_keys=["run"],
            model_name="test-model",
        )
        original_post_record = enforcer._post_record

        def _post_record_then_fail(*args, **kwargs):
            original_post_record(*args, **kwargs)
            raise RuntimeError("post record boom")

        with (
            patch(
                "polisyos.scientist.orchestration.llm.budget_enforcer.estimate_llm_cost_usd",
                return_value=0.4,
            ),
            patch.object(
                enforcer,
                "_post_record",
                side_effect=_post_record_then_fail,
            ),
            pytest.raises(RuntimeError, match="post record boom"),
        ):
            await enforcer.generate(system="sys", user="hello")

        assert budget_state.spent["run"] == Decimal("0.6")
        assert budget_state.reserved.get("run", Decimal(0)) == Decimal(0)


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["generate", "invoke"])
@pytest.mark.parametrize("fault", ["none", "latency", "cost", "diagnostic"])
async def test_optional_exports_preserve_actual_settlement_and_local_projection(
    tmp_path,
    method: str,
    fault: str,
) -> None:
    """A broken optional sink cannot spend again or skip mandatory recording."""
    from contextlib import nullcontext
    from types import SimpleNamespace

    from polisyos.core.llm.traced_client import TracedLLMClient
    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
    from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage

    class Provider:
        model = "fixture-model"
        provider = "fixture"
        calls = 0

        def invoke(self, prompt, **kwargs):
            self.calls += 1
            return GatewayLLMResponse(
                content="received once",
                usage=GatewayUsage(
                    prompt_tokens=2,
                    completion_tokens=3,
                    cost_usd=0.02,
                ),
                model=self.model,
                provider=self.provider,
            )

        async def generate(self, **kwargs):
            return self.invoke("frozen question", **kwargs)

    class Metrics(_FakeBudgetMetrics):
        def __init__(self):
            super().__init__()
            self.degraded = []
            if fault in {"latency", "diagnostic"}:
                self.llm_latency_ms.record = self.fail
            if fault == "cost":
                self.llm_cost_usd.record = self.fail

        def fail(self, *args, **kwargs):
            raise RuntimeError("optional export unavailable")

        def record_degraded_path(self, **kwargs):
            self.degraded.append(kwargs)
            if fault == "diagnostic":
                raise RuntimeError("optional diagnostic unavailable too")

        def record_llm_call(self, **kwargs):
            pass

    ledger_path = tmp_path / "settlement.json"
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    provider = Provider()
    metrics = Metrics()

    class Tracer:
        def start_as_current_span(self, *args, **kwargs):
            return nullcontext(
                SimpleNamespace(
                    set_attribute=lambda *args: None,
                    set_status=lambda *args: None,
                    record_exception=lambda *args: None,
                )
            )

    traced = TracedLLMClient(
        provider,
        producer_settlement_store=middleware,
        metrics=metrics,
        tracer=Tracer(),
    )
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1"))})
    enforcer = LLMBudgetEnforcer(
        client=traced,
        budget_state=state,
        budget_keys=["run"],
        metrics=metrics,
    )
    result = (
        (await enforcer.generate(user="frozen question"))
        if method == "generate"
        else (enforcer.invoke("frozen question"))
    )
    assert result.content == "received once"
    assert provider.calls == 1
    assert state.spent["run"] == Decimal("0.02")
    assert state.reserved["run"] == 0
    snapshot = FileBudgetLedger(ledger_path).snapshot()
    assert snapshot.state.spent["run"] == Decimal("0.02")
    assert len(snapshot.producer_settlements) == len(snapshot.spend_receipts) == 1
    assert next(iter(snapshot.producer_settlements.values())).status == "committed"
    if fault != "none":
        assert len(metrics.degraded) == 1
        assert metrics.degraded[0]["reason"] == "optional_observability_failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["generate", "invoke"])
async def test_optional_export_isolation_does_not_swallow_mandatory_audit(method: str) -> None:
    """The optional export guard must not cover the accounting/audit body."""

    class Provider:
        calls = 0

        def invoke(self, prompt, **kwargs):
            self.calls += 1
            return _make_response_with_provider_cost(cost_usd=0.02)

        async def generate(self, **kwargs):
            return self.invoke("question", **kwargs)

    failure = OSError("mandatory committed audit unavailable")

    class Audit:
        def append(self, **kwargs):
            if kwargs["action"] == "BUDGET_COMMITTED":
                raise failure

    provider = Provider()
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1"))})
    enforcer = LLMBudgetEnforcer(
        client=provider,
        budget_state=state,
        budget_keys=["run"],
        audit_log=Audit(),
        metrics=_FakeBudgetMetrics(),
    )

    async def call():
        if method == "generate":
            return await enforcer.generate(user="question")
        return enforcer.invoke("question")

    with pytest.raises(OSError, match="mandatory committed audit unavailable") as raised:
        await call()
    assert raised.value is failure
    assert provider.calls == 1
    assert state.spent["run"] == Decimal("0.02")
    assert state.reserved["run"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["generate", "invoke"])
async def test_optional_metric_resolution_and_diagnostic_resolution_preserve_post_record(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
) -> None:
    """A resolver failure cannot escape through its own degraded diagnostic."""
    attempts = []

    def unavailable():
        attempts.append("resolve")
        raise RuntimeError("optional metrics configuration unavailable")

    monkeypatch.setattr(
        "polisyos.scientist.orchestration.llm.budget_enforcer._default_metrics",
        unavailable,
    )
    response = _make_response_with_provider_cost(cost_usd=0.02)
    client = MagicMock()
    client.generate = AsyncMock(return_value=response)
    client.invoke.return_value = response
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1"))})
    enforcer = LLMBudgetEnforcer(
        client=client,
        budget_state=state,
        budget_keys=["run"],
    )
    result = (
        (await enforcer.generate(user="question"))
        if method == "generate"
        else (enforcer.invoke("question"))
    )
    assert result is response
    assert state.spent["run"] == Decimal("0.02")
    assert state.reserved["run"] == 0
    assert len(attempts) == 4  # latency/cost export, then each attempted diagnostic
    if method == "generate":
        client.generate.assert_awaited_once()
        client.invoke.assert_not_called()
    else:
        client.invoke.assert_called_once()
        client.generate.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["generate", "invoke"])
@pytest.mark.parametrize("fault", ["none", "warning", "warning_and_diagnostic"])
@pytest.mark.parametrize("mandatory_error", [False, True])
async def test_soft_limit_export_preserves_all_keys_and_mandatory_audit(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    fault: str,
    mandatory_error: bool,
) -> None:
    """Warning export cannot interrupt the multi-key commit or hide audit failure."""
    state = BudgetState(
        limits={
            key: BudgetLimit(key=key, max_usd=Decimal("1"), soft_limit_usd=Decimal("0.01"))
            for key in ("run", "parent")
        }
    )
    response = _make_response_with_provider_cost(cost_usd=0.02)
    client = MagicMock()
    client.generate = AsyncMock(return_value=response)
    client.invoke.return_value = response
    audit_events = []
    exports = []
    failure = OSError("mandatory commit audit failure")

    class Audit:
        def append(self, **kwargs):
            audit_events.append(kwargs)
            if kwargs["action"] == "BUDGET_COMMITTED" and mandatory_error:
                raise failure

    def warning(message, *args, **kwargs):
        operation = "soft" if message.startswith("Soft budget limit") else "diagnostic"
        exports.append(operation)
        if (operation == "soft" and fault != "none") or fault == "warning_and_diagnostic":
            raise RuntimeError(f"optional {operation} sink failure")

    monkeypatch.setattr(
        "polisyos.scientist.orchestration.llm.budget_enforcer.logger.warning", warning
    )
    enforcer = LLMBudgetEnforcer(
        client=client,
        budget_state=state,
        budget_keys=["run", "parent"],
        audit_log=Audit(),
        metrics=_FakeBudgetMetrics(),
    )

    async def call():
        if method == "generate":
            return await enforcer.generate(user="question")
        return enforcer.invoke("question")

    if mandatory_error:
        with pytest.raises(OSError, match="mandatory commit audit failure") as raised:
            await call()
        assert raised.value is failure
    else:
        assert await call() is response
        assert exports.count("soft") == 2
        if fault != "none":
            assert exports.count("diagnostic") == 2
    assert state.spent == {"run": Decimal("0.02"), "parent": Decimal("0.02")}
    assert state.reserved == {"run": Decimal(0), "parent": Decimal(0)}
    committed = [event for event in audit_events if event["action"] == "BUDGET_COMMITTED"]
    assert len(committed) == 1
    assert committed[0]["metadata"]["budget_charge_usd"] == "0.02"
    if method == "generate":
        client.generate.assert_awaited_once()
        client.invoke.assert_not_called()
    else:
        client.invoke.assert_called_once()
        client.generate.assert_not_awaited()
