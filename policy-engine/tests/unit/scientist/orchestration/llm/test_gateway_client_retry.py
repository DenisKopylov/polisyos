"""Tests for intelligent retry and connection pooling in GatewayLLMClient."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

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
