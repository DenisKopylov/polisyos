"""Real HTTP completion numbers retain evidence before monetary admission."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from aiohttp import web

from polisyos.core.llm.response import extract_llm_response_data
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient
from polisyos.scientist.orchestration.llm.prompt_cache import _freeze_response, _thaw_response

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def _http_completion(payload: str) -> AsyncIterator[tuple[GatewayLLMClient, list[bytes]]]:
    requests: list[bytes] = []

    async def completion(request: web.Request) -> web.Response:
        requests.append(await request.read())
        return web.Response(
            body=payload.encode("utf-8"),
            content_type="application/json",
            headers={"x-request-id": "real-http-numeric-request"},
        )

    app = web.Application()
    app.router.add_post("/chat/completions", completion)
    runner = web.AppRunner(app)
    await runner.setup()
    # Port zero delegates allocation to the actual loopback socket.
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    address = runner.addresses[0]
    client = GatewayLLMClient(
        base_url=f"http://127.0.0.1:{address[1]}",
        api_key="synthetic-test-key",
        model="gpt-4o-mini",
        max_retries=0,
    )
    try:
        yield client, requests
    finally:
        await client.aclose()
        await runner.cleanup()


def _payload(cost_fields: str, *, usage_fields: str = "") -> str:
    return (
        '{"choices":[{"message":{"content":"obtained HTTP response"}}],'
        '"model":"gpt-4o-mini","provider":"loopback-provider",'
        f'"usage":{{{usage_fields}{cost_fields}}}}}'
    )


@pytest.mark.parametrize("lexeme", ["1e-1000", "-1e-1000", "1e1000", "-1e1000"])
@pytest.mark.parametrize("cost_field", ["total_cost_usd", "cost_usd", "cost"])
async def test_http_nonrepresentable_cost_is_unknown_not_reported_zero(
    lexeme: str, cost_field: str
) -> None:
    async with _http_completion(_payload(f'"{cost_field}":{lexeme}')) as (client, requests):
        response = await client.generate(user="perform one actual request")

    assert len(requests) == 1
    assert response.content == "obtained HTTP response"
    assert response.request_id == "real-http-numeric-request"
    assert response.raw is not None
    actual_number = response.raw["usage"][cost_field]
    print("GATEWAY_NUMERIC_ACTUAL", lexeme, repr(actual_number), response.usage)
    assert Decimal(str(actual_number)) == Decimal(lexeme)
    assert isinstance(actual_number, Decimal)
    assert response.usage.cost_usd is None
    assert response.usage.cost_status == "invalid"
    restored = _thaw_response(_freeze_response(response))
    assert restored.content == response.content
    assert restored.usage.cost_usd is None
    assert restored.usage.cost_status == "invalid"
    observed = extract_llm_response_data(restored)
    assert observed.cost_usd is None
    assert observed.cost_status == "invalid"


@pytest.mark.parametrize("lexeme", ["0", "0.0", "-0.0", "0e-1000", "0.02"])
async def test_http_reported_known_cost_remains_known(lexeme: str) -> None:
    async with _http_completion(_payload(f'"cost_usd":{lexeme}')) as (client, requests):
        response = await client.generate(user="known reported charge")
    assert len(requests) == 1
    assert response.usage.cost_status == "known"
    assert response.usage.cost_usd == float(Decimal(lexeme))
    restored = _thaw_response(_freeze_response(response))
    assert restored.usage.cost_status == "known"
    assert restored.usage.cost_usd == response.usage.cost_usd


@pytest.mark.parametrize("lexeme", ["true", "false", "NaN", "Infinity", "-Infinity"])
async def test_http_invalid_cost_does_not_gain_reported_zero_authority(lexeme: str) -> None:
    async with _http_completion(_payload(f'"cost_usd":{lexeme}')) as (client, requests):
        response = await client.generate(user="invalid provider report")
    assert len(requests) == 1
    assert response.usage.cost_status == "invalid"
    assert response.usage.cost_usd is None


@pytest.mark.parametrize("component", ["base_cost_usd", "platform_fee_usd"])
@pytest.mark.parametrize("lexeme", ["1e-1000", "-1e-1000"])
async def test_http_cost_component_preserves_invalid_nonzero_evidence(
    component: str, lexeme: str
) -> None:
    async with _http_completion(_payload(f'"{component}":{lexeme}')) as (client, requests):
        response = await client.generate(user="component cost")
    assert len(requests) == 1
    assert response.usage.cost_usd is None
    assert response.usage.cost_status == "invalid"


@pytest.mark.parametrize("lexeme", ["1e-1000", "-1e-1000", "0.9999999999999999999999"])
async def test_http_fractional_token_evidence_cannot_become_observed_integer_zero(
    lexeme: str,
) -> None:
    fields = f'"prompt_tokens":{lexeme},"completion_tokens":0'
    async with _http_completion(_payload(fields)) as (client, requests):
        response = await client.generate(user="usage knowledge")
    assert len(requests) == 1
    assert response.usage.usage_status == "invalid"
    assert response.usage.cost_status == "missing"
    assert response.usage.cost_usd is None


async def test_http_top_level_cost_and_ordinary_tool_arguments_keep_separate_contracts() -> None:
    payload = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": "ordinary tool response",
                        "tool_calls": [
                            {
                                "id": "tool-1",
                                "function": {
                                    "name": "measure",
                                    "arguments": '{"fraction":0.5,"count":7}',
                                },
                            }
                        ],
                    }
                }
            ],
            "provider": "loopback-provider",
            "cost_usd": "1e-1000",
        }
    ).replace('"cost_usd": "1e-1000"', '"cost_usd": 1e-1000')
    async with _http_completion(payload) as (client, requests):
        response = await client.generate(user="cost outside usage")
    assert len(requests) == 1
    assert response.usage.cost_status == "invalid"
    assert response.usage.cost_usd is None
    assert response.tool_calls is not None
    arguments: dict[str, Any] = response.tool_calls[0].arguments
    assert arguments == {"fraction": 0.5, "count": 7}
    assert isinstance(arguments["fraction"], float)
