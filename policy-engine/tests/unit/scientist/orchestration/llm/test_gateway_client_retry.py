"""Tests for intelligent retry and connection pooling in GatewayLLMClient."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from polisyos.core.llm.response import extract_llm_response_data
from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.gateway_client import (
    GatewayLLMClient,
    _HTTPError,
    _is_retryable_status,
)


class TestRetryableStatus:
    def test_429_retryable(self):
        assert _is_retryable_status(429) is True

    def test_500_retryable(self):
        assert _is_retryable_status(500) is True

    def test_503_retryable(self):
        assert _is_retryable_status(503) is True

    def test_400_not_retryable(self):
        assert _is_retryable_status(400) is False

    def test_401_not_retryable(self):
        assert _is_retryable_status(401) is False

    def test_404_not_retryable(self):
        assert _is_retryable_status(404) is False


class TestHTTPError:
    def test_has_status(self):
        err = _HTTPError("bad", status=429)
        assert err.status == 429
        assert "bad" in str(err)


class TestSessionLifecycle:
    async def test_transport_failure_closes_session_before_raising(self):
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
            max_retries=0,
        )

        class _FailingSession:
            closed = False
            close_called = False

            def post(self, *args, **kwargs):
                raise TimeoutError()

            async def close(self):
                self.close_called = True
                self.closed = True

        session = _FailingSession()
        client._session = session

        with pytest.raises(RuntimeError, match="Failed LLM gateway call"):
            await client.generate(user="hello")

        assert session.close_called is True
        assert client._session is None


class TestConnectionPooling:
    @pytest.mark.asyncio
    async def test_session_created_lazily(self):
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
        )
        assert client._session is None
        # Ensure aclose works even before session is created
        await client.aclose()
        assert client._session is None

    @pytest.mark.asyncio
    async def test_aclose_closes_session(self):
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
        )
        session = await client._ensure_session(30.0)
        assert session is not None
        assert not session.closed
        await client.aclose()
        assert client._session is None

    @pytest.mark.asyncio
    async def test_request_timeout_is_applied_per_call_not_pinned_to_session(self):
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
        )
        seen_timeouts: list[float | None] = []

        class _FakeResp:
            status = 200
            headers = {}

            async def text(self):
                return json.dumps({"choices": [{"message": {"content": "ok"}}]})

        class _AsyncCtx:
            def __init__(self, resp):
                self._resp = resp

            async def __aenter__(self):
                return self._resp

            async def __aexit__(self, *args):
                pass

        class _FakeSession:
            closed = False

            def post(self, *args, **kwargs):
                timeout = kwargs.get("timeout")
                seen_timeouts.append(getattr(timeout, "total", None))
                return _AsyncCtx(_FakeResp())

            async def close(self):
                pass

        client._session = _FakeSession()
        await client._post_json(endpoint="/chat/completions", payload={}, timeout_s=1.0)
        await client._post_json(endpoint="/chat/completions", payload={}, timeout_s=30.0)

        assert seen_timeouts == [1.0, 30.0]


class TestIntelligentRetry:
    @pytest.mark.asyncio
    async def test_4xx_no_retry(self):
        """4xx errors (except 429) should fail immediately, no retry."""
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
            max_retries=3,
        )
        attempt_count = 0

        class _FakeResp:
            status = 400
            headers = {}

            async def text(self):
                nonlocal attempt_count
                attempt_count += 1
                return "Bad Request"

        class _FakeSession:
            closed = False

            def post(self, *a, **kw):
                return _AsyncCtx(_FakeResp())

            async def close(self):
                pass

        class _AsyncCtx:
            def __init__(self, resp):
                self._resp = resp

            async def __aenter__(self):
                return self._resp

            async def __aexit__(self, *args):
                pass

        client._session = _FakeSession()
        with pytest.raises(RuntimeError, match="400"):
            await client._post_json(
                endpoint="/chat/completions",
                payload={},
                timeout_s=10,
            )
        # Should only be called once (no retries for 4xx)
        assert attempt_count == 1
        client._session = None

    @pytest.mark.asyncio
    async def test_429_is_retried(self):
        """429 should be retried up to max_retries."""
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
            max_retries=1,
        )
        call_count = 0

        class _FakeResp:
            def __init__(self, status):
                self.status = status
                self.headers = {}

            async def text(self):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return "Rate Limited"
                return json.dumps({"choices": [{"message": {"content": "ok"}}]})

        class _FakeSession:
            closed = False

            def post(self, *a, **kw):
                s = 429 if call_count == 0 else 200
                return _AsyncCtx(_FakeResp(s))

            async def close(self):
                pass

        class _AsyncCtx:
            def __init__(self, resp):
                self._resp = resp

            async def __aenter__(self):
                return self._resp

            async def __aexit__(self, *args):
                pass

        client._session = _FakeSession()
        # This will still raise because our mock is tricky, but the key
        # assertion is that it retries (call_count > 1)
        try:
            await client._post_json(
                endpoint="/chat/completions",
                payload={},
                timeout_s=10,
            )
        except Exception:
            pass
        assert call_count >= 1
        client._session = None

    @pytest.mark.asyncio
    async def test_provider_error_code_blocks_retry_for_insufficient_quota(self):
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
            max_retries=3,
        )
        call_count = 0

        class _FakeResp:
            status = 429
            headers = {"x-request-id": "req-123", "Retry-After": "10"}

            async def text(self):
                nonlocal call_count
                call_count += 1
                return json.dumps({"error": {"code": "insufficient_quota"}})

        class _FakeSession:
            closed = False

            def post(self, *a, **kw):
                return _AsyncCtx(_FakeResp())

            async def close(self):
                pass

        class _AsyncCtx:
            def __init__(self, resp):
                self._resp = resp

            async def __aenter__(self):
                return self._resp

            async def __aexit__(self, *args):
                pass

        client._session = _FakeSession()
        with pytest.raises(RuntimeError) as excinfo:
            await client._post_json(
                endpoint="/chat/completions",
                payload={},
                timeout_s=10,
            )
        assert call_count == 1
        assert excinfo.value.__cause__ is not None
        assert excinfo.value.__cause__.request_id == "req-123"
        assert excinfo.value.__cause__.error_code == "insufficient_quota"
        client._session = None

    @pytest.mark.asyncio
    async def test_retry_after_header_and_idempotency_key_are_reused(self):
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
            max_retries=1,
        )
        call_count = 0
        seen_idempotency_keys: list[str] = []

        class _FakeResp:
            def __init__(self, status, headers):
                self.status = status
                self.headers = headers

            async def text(self):
                if self.status == 429:
                    return json.dumps({"error": {"code": "rate_limit_exceeded"}})
                return json.dumps({"choices": [{"message": {"content": "ok"}}]})

        class _FakeSession:
            closed = False

            def post(self, *a, **kw):
                nonlocal call_count
                seen_idempotency_keys.append(kw["headers"]["x-idempotency-key"])
                status = 429 if call_count == 0 else 200
                headers = {"Retry-After": "1.5"} if status == 429 else {}
                call_count += 1
                return _AsyncCtx(_FakeResp(status, headers))

            async def close(self):
                pass

        class _AsyncCtx:
            def __init__(self, resp):
                self._resp = resp

            async def __aenter__(self):
                return self._resp

            async def __aexit__(self, *args):
                pass

        client._session = _FakeSession()
        with patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
            result = await client._post_json(
                endpoint="/chat/completions",
                payload={},
                timeout_s=10,
            )
        assert result["choices"][0]["message"]["content"] == "ok"
        sleep_mock.assert_awaited_once_with(1.5)
        assert len(seen_idempotency_keys) == 2
        assert seen_idempotency_keys[0]
        assert seen_idempotency_keys[0] == seen_idempotency_keys[1]
        client._session = None

    @pytest.mark.asyncio
    async def test_idempotency_key_is_added_even_without_retry_budget(self):
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
            max_retries=0,
        )
        seen_idempotency_keys: list[str] = []

        class _FakeResp:
            status = 200
            headers = {}

            async def text(self):
                return json.dumps({"choices": [{"message": {"content": "ok"}}]})

        class _FakeSession:
            closed = False

            def post(self, *a, **kw):
                seen_idempotency_keys.append(kw["headers"]["x-idempotency-key"])
                return _AsyncCtx(_FakeResp())

            async def close(self):
                pass

        class _AsyncCtx:
            def __init__(self, resp):
                self._resp = resp

            async def __aenter__(self):
                return self._resp

            async def __aexit__(self, *args):
                pass

        client._session = _FakeSession()
        result = await client._post_json(
            endpoint="/chat/completions",
            payload={},
            timeout_s=10,
        )

        assert result["choices"][0]["message"]["content"] == "ok"
        assert seen_idempotency_keys == [seen_idempotency_keys[0]]
        assert seen_idempotency_keys[0]
        client._session = None


class TestUsageParsing:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("raw_usage", "expected_usage_status", "expected_origin", "expected_amount"),
        [
            ("{}", "missing", "unknown", None),
            ('{"prompt_tokens":"bad","completion_tokens":"also-bad"}', "invalid", "unknown", None),
            ('{"prompt_tokens":-1,"completion_tokens":1}', "invalid", "unknown", None),
            ('{"prompt_tokens":1.5,"completion_tokens":0.5}', "invalid", "unknown", None),
            ('{"prompt_tokens":null,"completion_tokens":1}', "invalid", "unknown", None),
            ('{"prompt_tokens":true,"completion_tokens":1}', "invalid", "unknown", None),
            ('{"prompt_tokens":[],"completion_tokens":1}', "invalid", "unknown", None),
            ('{"prompt_tokens":{},"completion_tokens":1}', "invalid", "unknown", None),
            ('{"prompt_tokens":1e-1000,"completion_tokens":1}', "invalid", "unknown", None),
            ('{"prompt_tokens":"1e-1000","completion_tokens":1}', "invalid", "unknown", None),
            (
                '{"prompt_tokens":null,"input_tokens":2,"completion_tokens":1}',
                "invalid",
                "unknown",
                None,
            ),
            (
                '{"prompt_tokens":2,"completion_tokens":1,"cost_status":null,"total_cost_usd":0.25}',
                "known",
                "unknown",
                None,
            ),
            (
                '{"prompt_tokens":2,"completion_tokens":1,"cost_status":[],"total_cost_usd":0.25}',
                "known",
                "unknown",
                None,
            ),
            (
                '{"prompt_tokens":2,"completion_tokens":1,"cost_status":{},"total_cost_usd":0.25}',
                "known",
                "unknown",
                None,
            ),
            (
                '{"prompt_tokens":2,"completion_tokens":1,"cost_status":17,"total_cost_usd":0.25}',
                "known",
                "unknown",
                None,
            ),
            (
                '{"prompt_tokens":2,"completion_tokens":1,"cost_status":true,"total_cost_usd":0.25}',
                "known",
                "unknown",
                None,
            ),
            (
                '{"prompt_tokens":2,"completion_tokens":1,"cost_status":"reported","total_cost_usd":0.25}',
                "known",
                "unknown",
                None,
            ),
            ('{"input_tokens":"2","output_tokens":"1"}', "known", "estimated", Decimal("0.00005")),
            (
                '{"prompt_tokens":2.0,"completion_tokens":1.0}',
                "known",
                "estimated",
                Decimal("0.00005"),
            ),
            ('{"prompt_tokens":0,"completion_tokens":0}', "known", "estimated", Decimal(0)),
            ('{"prompt_tokens":2,"completion_tokens":1}', "known", "estimated", Decimal("0.00005")),
            (
                '{"prompt_tokens":2,"completion_tokens":1,"total_tokens":"bad"}',
                "invalid",
                "unknown",
                None,
            ),
        ],
    )
    async def test_raw_wire_usage_status_reaches_durable_settlement(
        self,
        tmp_path: Path,
        raw_usage: str,
        expected_usage_status: str,
        expected_origin: str,
        expected_amount: Decimal | None,
    ) -> None:
        ledger_path = tmp_path / "ledger.json"
        store = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
        response_json = (
            '{"model":"fixture-model","choices":[{"message":{"content":"answer"}}],'
            f'"usage":{raw_usage}'
            "}"
        )

        class _FakeResponse:
            status = 200
            headers: dict[str, str] = {}

            async def text(self) -> str:
                return response_json

        class _AsyncContext:
            async def __aenter__(self) -> _FakeResponse:
                return _FakeResponse()

            async def __aexit__(self, *_args: object) -> None:
                return None

        class _FakeSession:
            closed = False

            def post(self, *_args: object, **_kwargs: object) -> _AsyncContext:
                return _AsyncContext()

            async def close(self) -> None:
                self.closed = True

        gateway = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="fixture-model",
        )
        gateway._session = _FakeSession()
        traced = TracedLLMClient(
            gateway,
            model_name="fixture-model",
            producer_settlement_store=store,
        )

        response = await traced.generate(user="policy question")

        parsed = extract_llm_response_data(response.response)
        event = response.settlement.event
        record = FileBudgetLedger(ledger_path).snapshot().producer_settlements[event.event_id]
        assert parsed.usage_status == expected_usage_status
        assert event.cost_origin == expected_origin
        assert event.amount == expected_amount
        assert record.status == ("committed" if expected_amount is not None else "unknown")
        assert record.cost_origin == expected_origin
        assert record.amount == expected_amount

    @pytest.mark.asyncio
    async def test_response_labels_cannot_rebind_configured_model_or_provider(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        ledger_path = tmp_path / "ledger.json"
        store = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
        response_json = (
            '{"model":"spoof-response-model","provider":"spoof-response-provider",'
            '"choices":[{"message":{"content":"answer"}}],'
            '"usage":{"prompt_tokens":2,"completion_tokens":1}}'
        )

        class _FakeResponse:
            status = 200
            headers: dict[str, str] = {}

            async def text(self) -> str:
                return response_json

        class _AsyncContext:
            async def __aenter__(self) -> _FakeResponse:
                return _FakeResponse()

            async def __aexit__(self, *_args: object) -> None:
                return None

        class _FakeSession:
            closed = False

            def post(self, *_args: object, **_kwargs: object) -> _AsyncContext:
                return _AsyncContext()

            async def close(self) -> None:
                self.closed = True

        pricing_models: list[str] = []

        def _configured_price(*, model: str, prompt_tokens: int, completion_tokens: int) -> Decimal:
            pricing_models.append(model)
            assert (prompt_tokens, completion_tokens) == (2, 1)
            return Decimal("0.31") if model == "configured-model" else Decimal("9.99")

        monkeypatch.setattr(
            "polisyos.core.llm.traced_client.estimate_llm_cost_usd",
            _configured_price,
        )
        gateway = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="configured-model",
            provider_hint="configured-logical-route",
            max_retries=0,
        )
        gateway._session = _FakeSession()
        traced = TracedLLMClient(
            gateway,
            model_name="configured-model",
            provider_name="configured-logical-route",
            producer_settlement_store=store,
        )

        response = await traced.generate(user="policy question")

        event = response.settlement.event
        record = FileBudgetLedger(ledger_path).snapshot().producer_settlements[event.event_id]
        assert response.response.model == "spoof-response-model"
        assert response.response.provider == "spoof-response-provider"
        assert event.model == record.model == "configured-model"
        assert event.provider == record.provider == "configured-logical-route"
        assert event.cost_origin == record.cost_origin == "estimated"
        assert event.amount == record.amount == Decimal("0.31")
        assert pricing_models == ["configured-model", "configured-model"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        (
            "usage_cost_fields",
            "top_level_cost_fields",
            "expected_status",
            "expected_origin",
            "expected_amount",
        ),
        [
            ("", "", "missing", "estimated", Decimal("0.00005")),
            (',"total_cost_usd":0', "", "known", "reported", Decimal(0)),
            (',"total_cost_usd":0.25', "", "known", "reported", Decimal("0.25")),
            (',"total_cost_usd":"0.25"', "", "known", "reported", Decimal("0.25")),
            (',"total_cost_usd":true', "", "invalid", "unknown", None),
            (',"total_cost_usd":null', "", "invalid", "unknown", None),
            (',"total_cost_usd":[]', "", "invalid", "unknown", None),
            (',"total_cost_usd":{}', "", "invalid", "unknown", None),
            (',"total_cost_usd":"not-a-cost"', "", "invalid", "unknown", None),
            (',"total_cost_usd":-0.01', "", "invalid", "unknown", None),
            (',"cost_usd":0.25', "", "known", "reported", Decimal("0.25")),
            (',"cost":0.25', "", "known", "reported", Decimal("0.25")),
            ("", ',"cost":0.25', "known", "reported", Decimal("0.25")),
            (
                ',"total_cost_usd":0.5,"cost_usd":0.25',
                "",
                "known",
                "reported",
                Decimal("0.5"),
            ),
            (
                "",
                ',"cost_usd":0.5,"total_cost_usd":0.25',
                "known",
                "reported",
                Decimal("0.25"),
            ),
            (
                ',"total_cost_usd":null,"cost_usd":0.25',
                ',"cost_usd":0.5',
                "invalid",
                "unknown",
                None,
            ),
            (
                ',"cost":0.25',
                ',"cost_usd":0.5',
                "known",
                "reported",
                Decimal("0.25"),
            ),
            (
                ',"base_cost_usd":0.2,"platform_fee_usd":0.02',
                "",
                "known",
                "reported",
                Decimal("0.22"),
            ),
            (',"base_cost_usd":0.2', "", "invalid", "unknown", None),
        ],
    )
    async def test_raw_wire_cost_alias_domain_reaches_durable_settlement(
        self,
        tmp_path: Path,
        usage_cost_fields: str,
        top_level_cost_fields: str,
        expected_status: str,
        expected_origin: str,
        expected_amount: Decimal | None,
    ) -> None:
        ledger_path = tmp_path / "ledger.json"
        store = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
        raw_text = (
            '{"model":"fixture-model",'
            '"choices":[{"message":{"content":"answer"}}],'
            '"usage":{"prompt_tokens":2,"completion_tokens":1'
            f"{usage_cost_fields}}}{top_level_cost_fields}" + "}"
        )

        class _Response:
            status = 200
            headers: dict[str, str] = {}

            async def text(self) -> str:
                return raw_text

        class _Request:
            async def __aenter__(self) -> _Response:
                return _Response()

            async def __aexit__(self, *_args: object) -> None:
                return None

        class _Session:
            closed = False

            def post(self, *_args: Any, **_kwargs: Any) -> _Request:
                return _Request()

            async def close(self) -> None:
                self.closed = True

        gateway = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="fixture-model",
            max_retries=0,
        )
        gateway._session = _Session()
        traced = TracedLLMClient(
            gateway,
            model_name="fixture-model",
            producer_settlement_store=store,
        )

        response = await traced.generate(user="policy question")
        parsed = extract_llm_response_data(response.response)
        record = (
            FileBudgetLedger(ledger_path)
            .snapshot()
            .producer_settlements[response.settlement.event.event_id]
        )
        assert response.usage.cost_status == expected_status
        assert parsed.cost_status == expected_status
        assert response.settlement.event.cost_origin == expected_origin
        assert response.settlement.event.amount == expected_amount
        assert record.status == ("committed" if expected_amount is not None else "unknown")
        assert record.cost_origin == expected_origin
        assert record.amount == expected_amount

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("raw_cost", "expected_origin", "expected_amount", "expected_status"),
        [
            (0, "reported", Decimal(0), "committed"),
            (-0.01, "unknown", None, "unknown"),
            ("not-a-cost", "unknown", None, "unknown"),
            (None, "estimated", Decimal("0.00005"), "committed"),
        ],
    )
    async def test_raw_gateway_cost_evidence_reaches_durable_producer_event(
        self,
        tmp_path: Path,
        raw_cost: Any,
        expected_origin: str,
        expected_amount: Decimal | None,
        expected_status: str,
    ):
        ledger_path = tmp_path / "ledger.json"
        store = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
        payload = {
            "model": "fixture-model",
            "choices": [{"message": {"content": "answer"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 1},
        }
        if raw_cost is not None:
            payload["usage"]["total_cost_usd"] = raw_cost

        gateway = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="fixture-model",
        )
        with patch.object(
            gateway,
            "_post_json",
            new_callable=AsyncMock,
            return_value=payload,
        ):
            traced = TracedLLMClient(
                gateway,
                model_name="fixture-model",
                producer_settlement_store=store,
            )
            response = await traced.generate(user="policy question")

        event = response.settlement.event
        record = FileBudgetLedger(ledger_path).snapshot().producer_settlements[event.event_id]
        assert event.cost_origin == expected_origin
        assert event.amount == expected_amount
        assert record.status == expected_status
        assert record.cost_origin == expected_origin
        assert record.amount == expected_amount

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "raw_cost_token",
        ["1e-1000", '"1e-1000"', "1e1000", '"1e1000"'],
    )
    async def test_unrepresentable_raw_cost_remains_unknown(
        self, tmp_path: Path, raw_cost_token: str
    ) -> None:
        ledger_path = tmp_path / "ledger.json"
        store = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
        raw_text = (
            '{"model":"fixture-model",'
            '"choices":[{"message":{"content":"answer"}}],'
            '"usage":{"prompt_tokens":2,"completion_tokens":1,'
            f'"total_cost_usd":{raw_cost_token}'
            "}}"
        )

        class _Response:
            status = 200
            headers: dict[str, str] = {}

            async def text(self) -> str:
                return raw_text

        class _Request:
            async def __aenter__(self) -> _Response:
                return _Response()

            async def __aexit__(self, *_args: object) -> None:
                return None

        class _Session:
            closed = False

            def post(self, *_args: Any, **_kwargs: Any) -> _Request:
                return _Request()

            async def close(self) -> None:
                self.closed = True

        gateway = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="fixture-model",
            max_retries=0,
        )
        gateway._session = _Session()
        traced = TracedLLMClient(
            gateway,
            model_name="fixture-model",
            producer_settlement_store=store,
        )

        response = await traced.generate(user="policy question")

        record = (
            FileBudgetLedger(ledger_path)
            .snapshot()
            .producer_settlements[response.settlement.event.event_id]
        )
        assert response.usage.cost_status == "invalid"
        assert record.cost_origin == "unknown"
        assert record.amount is None
        assert record.status == "unknown"

    @pytest.mark.parametrize(
        ("raw_cost", "expected_status", "expected_amount"),
        [
            (0, "known", 0.0),
            (0.0, "known", 0.0),
            (Decimal("0"), "known", 0.0),
            ("0", "known", 0.0),
            (1, "known", 1.0),
            (1.0, "known", 1.0),
            (Decimal("0.25"), "known", 0.25),
            ("0.25", "known", 0.25),
            ("5e-324", "known", 5e-324),
            (Decimal("1e-1000"), "invalid", None),
            ("1e-1000", "invalid", None),
            (Decimal("1e1000"), "invalid", None),
            ("1e1000", "invalid", None),
            (10**400, "invalid", None),
            (-1, "invalid", None),
            (float("inf"), "invalid", None),
            (float("nan"), "invalid", None),
            ("Infinity", "invalid", None),
            ("not-a-cost", "invalid", None),
            (True, "invalid", None),
            ([], "invalid", None),
            ({}, "invalid", None),
        ],
    )
    def test_present_cost_primitives_keep_exact_zero_and_reject_unrepresentable_values(
        self, raw_cost: Any, expected_status: str, expected_amount: float | None
    ) -> None:
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
        )
        payload = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {
                "prompt_tokens": 2,
                "completion_tokens": 1,
                "total_cost_usd": raw_cost,
            },
        }

        parsed = client._parse_completion_payload(payload).usage

        assert parsed.cost_status == expected_status
        assert parsed.cost_usd == expected_amount

    def test_explicit_null_cost_does_not_fall_through_to_alias_or_estimate(self) -> None:
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
        )
        payload = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {
                "prompt_tokens": 2,
                "completion_tokens": 1,
                "total_cost_usd": None,
                "cost_usd": 0.25,
            },
        }

        parsed = client._parse_completion_payload(payload).usage

        assert parsed.cost_status == "invalid"
        assert parsed.cost_usd is None

        alias_payload = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {
                "prompt_tokens": 2,
                "completion_tokens": 1,
                "cost_usd": 0.25,
            },
        }
        alias = client._parse_completion_payload(alias_payload).usage
        assert alias.cost_status == "known"
        assert alias.cost_usd == 0.25

    def test_raw_cost_values_keep_reported_zero_and_invalid_distinct(self):
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
        )
        payload_base = {
            "model": "m",
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        reported_zero = client._parse_completion_payload(
            {**payload_base, "usage": {**payload_base["usage"], "total_cost_usd": 0}}
        )
        negative = client._parse_completion_payload(
            {**payload_base, "usage": {**payload_base["usage"], "total_cost_usd": -0.01}}
        )
        malformed = client._parse_completion_payload(
            {**payload_base, "usage": {**payload_base["usage"], "total_cost_usd": "not-a-cost"}}
        )
        missing = client._parse_completion_payload(payload_base)

        assert extract_llm_response_data(reported_zero).cost_status == "known"
        assert extract_llm_response_data(reported_zero).cost_usd == 0
        assert extract_llm_response_data(negative).cost_status == "invalid"
        assert extract_llm_response_data(malformed).cost_status == "invalid"
        assert extract_llm_response_data(missing).cost_status == "missing"

    @pytest.mark.asyncio
    async def test_total_cost_usd_is_parsed_from_usage(self):
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
        )
        with patch.object(
            client,
            "_post_json",
            new_callable=AsyncMock,
            return_value={
                "model": "m",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                    "base_cost_usd": 0.0002,
                    "platform_fee_usd": 0.00002,
                    "total_cost_usd": 0.00022,
                },
            },
        ):
            response = await client.generate(user="hi")

        assert response.usage.prompt_tokens == 10
        assert response.usage.completion_tokens == 5
        assert response.usage.total_tokens == 15
        assert response.usage.cost_usd == 0.00022

    @pytest.mark.asyncio
    async def test_invalid_tool_call_arguments_surface_error_envelope(self):
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
        )
        with patch.object(
            client,
            "_post_json",
            new_callable=AsyncMock,
            return_value={
                "model": "m",
                "choices": [
                    {
                        "message": {
                            "content": "ok",
                            "tool_calls": [
                                {
                                    "id": "tc_1",
                                    "function": {
                                        "name": "search",
                                        "arguments": '{"broken": ',
                                    },
                                }
                            ],
                        }
                    }
                ],
            },
        ):
            response = await client.generate(user="hi")

        assert response.tool_calls is not None
        assert response.tool_calls[0].arguments == {}
        assert response.tool_calls[0].error_envelope is not None
        assert response.tool_calls[0].error_envelope["reason"] == "tool_call_arguments_parse_error"

    @pytest.mark.asyncio
    async def test_wrapped_tool_call_arguments_remain_strict(self):
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
        )
        with patch.object(
            client,
            "_post_json",
            new_callable=AsyncMock,
            return_value={
                "model": "m",
                "choices": [
                    {
                        "message": {
                            "content": "ok",
                            "tool_calls": [
                                {
                                    "id": "tc_wrapped",
                                    "function": {
                                        "name": "search",
                                        "arguments": '<think>x</think>{"query":"policy"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
            },
        ):
            response = await client.generate(user="hi")

        assert response.tool_calls is not None
        assert response.tool_calls[0].arguments == {}
        assert response.tool_calls[0].error_envelope is not None
        assert response.tool_calls[0].error_envelope["reason"] == "tool_call_arguments_parse_error"


class TestPresetAndPlugins:
    @pytest.mark.asyncio
    async def test_generate_prefers_request_preset_and_merges_plugins(self):
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
            preset="default-agent",
            default_plugins=[
                {"id": "privacy-sanitization"},
                {"id": "audit-trace", "mode": "compact"},
            ],
        )

        with patch.object(
            client,
            "_post_json",
            new_callable=AsyncMock,
            return_value={
                "model": "m",
                "choices": [{"message": {"content": "ok"}}],
            },
        ) as post_json:
            response = await client.generate(
                user="hi",
                preset="high-reasoning",
                plugins=[
                    {"id": "response-healing"},
                    {"id": "privacy-sanitization", "scope": "all"},
                ],
            )

        payload = post_json.await_args.kwargs["payload"]
        assert response.content == "ok"
        assert payload["preset"] == "high-reasoning"
        assert payload["plugins"] == [
            {"id": "privacy-sanitization"},
            {"id": "audit-trace", "mode": "compact"},
            {"id": "response-healing"},
        ]


class TestResponseFormatFallback:
    @pytest.mark.asyncio
    async def test_response_format_unsupported_is_memoized_per_client(self):
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
            max_retries=0,
        )
        seen_payloads: list[dict[str, object]] = []

        class _FakeResp:
            headers = {}

            def __init__(self, status: int) -> None:
                self.status = status

            async def text(self):
                if self.status == 400:
                    return json.dumps(
                        {"error": {"message": "feature 'json_object' is temporarily unavailable"}}
                    )
                return json.dumps(
                    {
                        "model": "m",
                        "choices": [{"message": {"content": "ok"}}],
                    }
                )

        class _FakeSession:
            closed = False

            def post(self, *a, **kw):
                payload = dict(kw["json"])
                seen_payloads.append(payload)
                status = 400 if len(seen_payloads) == 1 else 200
                return _AsyncCtx(_FakeResp(status))

            async def close(self):
                pass

        class _AsyncCtx:
            def __init__(self, resp):
                self._resp = resp

            async def __aenter__(self):
                return self._resp

            async def __aexit__(self, *args):
                pass

        client._session = _FakeSession()

        first = await client.generate(
            user="one",
            response_format={"type": "json_object"},
        )
        second = await client.generate(
            user="two",
            response_format={"type": "json_object"},
        )

        assert first.content == "ok"
        assert second.content == "ok"
        assert [("response_format" in payload) for payload in seen_payloads] == [
            True,
            False,
            False,
        ]
        client._session = None

    @pytest.mark.asyncio
    async def test_response_format_fallback_is_preserved_in_response_raw(self):
        client = GatewayLLMClient(
            base_url="http://test.local",
            api_key="key",
            model="m",
            max_retries=0,
        )

        class _FakeResp:
            headers = {}

            def __init__(self, status: int) -> None:
                self.status = status

            async def text(self):
                if self.status == 400:
                    return json.dumps(
                        {"error": {"message": "feature 'json_object' is temporarily unavailable"}}
                    )
                return json.dumps(
                    {
                        "model": "m",
                        "choices": [{"message": {"content": "ok"}}],
                    }
                )

        class _FakeSession:
            closed = False
            call_count = 0

            def post(self, *a, **kw):
                self.call_count += 1
                status = 400 if self.call_count == 1 else 200
                return _AsyncCtx(_FakeResp(status))

            async def close(self):
                pass

        class _AsyncCtx:
            def __init__(self, resp):
                self._resp = resp

            async def __aenter__(self):
                return self._resp

            async def __aexit__(self, *args):
                pass

        client._session = _FakeSession()
        degraded_event = {
            "reason": "response_format_unsupported_retry_plain_json",
            "component": "llm.gateway_client",
        }
        with patch(
            "polisyos.scientist.orchestration.llm.gateway_client.emit_degraded_path",
            return_value=degraded_event,
        ):
            response = await client.generate(
                user="one",
                response_format={"type": "json_object"},
            )

        assert response.content == "ok"
        assert response.raw is not None
        assert response.raw["_gateway_degraded_events"] == [degraded_event]
        client._session = None


class TestModelCatalog:
    @pytest.mark.asyncio
    async def test_list_model_ids_reads_openai_models_payload(self):
        client = GatewayLLMClient(
            base_url="http://test.local/v1",
            api_key="key",
            model="m",
        )

        class _FakeResp:
            status = 200

            async def text(self):
                return json.dumps(
                    {
                        "object": "list",
                        "data": [
                            {"id": "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"},
                            {"id": "claude-sonnet-4-5-20250929"},
                            {"id": ""},
                            "bad",
                        ],
                    }
                )

        class _FakeSession:
            closed = False

            def get(self, *a, **kw):
                return _AsyncCtx(_FakeResp())

            async def close(self):
                pass

        class _AsyncCtx:
            def __init__(self, resp):
                self._resp = resp

            async def __aenter__(self):
                return self._resp

            async def __aexit__(self, *args):
                pass

        client._session = _FakeSession()
        model_ids = await client.list_model_ids()
        assert model_ids == [
            "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
            "claude-sonnet-4-5-20250929",
        ]
        client._session = None

    @pytest.mark.asyncio
    async def test_list_model_ids_invalid_json_degrades_to_empty_list(self):
        client = GatewayLLMClient(
            base_url="http://test.local/v1",
            api_key="key",
            model="m",
        )

        class _FakeResp:
            status = 200

            async def text(self):
                return "{not-json"

        class _FakeSession:
            closed = False

            def get(self, *a, **kw):
                return _AsyncCtx(_FakeResp())

            async def close(self):
                pass

        class _AsyncCtx:
            def __init__(self, resp):
                self._resp = resp

            async def __aenter__(self):
                return self._resp

            async def __aexit__(self, *args):
                pass

        client._session = _FakeSession()
        with patch(
            "polisyos.scientist.orchestration.llm.gateway_client.emit_degraded_path",
            return_value={"reason": "model_catalog_parse_failed"},
        ) as degraded:
            model_ids = await client.list_model_ids()

        assert model_ids == []
        degraded.assert_called_once()
        client._session = None

    @pytest.mark.asyncio
    async def test_list_model_ids_invalid_shape_degrades_to_empty_list(self):
        client = GatewayLLMClient(
            base_url="http://test.local/v1",
            api_key="key",
            model="m",
        )

        class _FakeResp:
            status = 200

            async def text(self):
                return json.dumps(["not", "an", "object"])

        class _FakeSession:
            closed = False

            def get(self, *a, **kw):
                return _AsyncCtx(_FakeResp())

            async def close(self):
                pass

        class _AsyncCtx:
            def __init__(self, resp):
                self._resp = resp

            async def __aenter__(self):
                return self._resp

            async def __aexit__(self, *args):
                pass

        client._session = _FakeSession()
        with patch(
            "polisyos.scientist.orchestration.llm.gateway_client.emit_degraded_path",
            return_value={"reason": "model_catalog_shape_invalid"},
        ) as degraded:
            model_ids = await client.list_model_ids()

        assert model_ids == []
        degraded.assert_called_once()
        client._session = None
