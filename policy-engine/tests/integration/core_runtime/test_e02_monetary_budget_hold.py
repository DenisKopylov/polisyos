"""Exercise gateway budget behavior over the default factory's HTTP path."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

import pytest
from aiohttp import web

from polisyos.core.llm.response import extract_llm_response_data
from polisyos.core.llm.traced_client import LLMAccountingError, TracedLLMClient
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.factory import (
    GatewayLLMConfig,
    create_traced_gateway_client,
)
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient

pytestmark = pytest.mark.integration

MODEL_NAME = "gpt-4o"
PROVIDER_NAME = "loopback-provider"


@asynccontextmanager
async def _gateway_http(
    payloads: list[bytes],
) -> AsyncIterator[tuple[str, list[dict[str, Any]]]]:
    """Serve gateway completion payloads over a local HTTP socket."""
    requests: list[dict[str, Any]] = []

    async def completion(request: web.Request) -> web.Response:
        body = await request.read()
        ordinal = len(requests)
        requests.append(
            {
                "body": body,
                "idempotency_key": request.headers.get("x-idempotency-key"),
            }
        )
        if ordinal >= len(payloads):
            return web.Response(status=500, text="unexpected extra provider request")
        return web.Response(
            body=payloads[ordinal],
            content_type="application/json",
            headers={"x-request-id": f"loopback-request-{ordinal + 1}"},
        )

    app = web.Application()
    app.router.add_post("/v1/chat/completions", completion)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    address = runner.addresses[0]
    try:
        yield f"http://127.0.0.1:{address[1]}", requests
    finally:
        await runner.cleanup()


def _completion_payload(*, cost_lexeme: str | None = None, usage: bool = True) -> bytes:
    """Build an OpenAI-compatible response without rewriting numeric cost bytes."""
    fields = ['"prompt_tokens":1', '"completion_tokens":1'] if usage else []
    if cost_lexeme is not None:
        fields.append(f'"cost_usd":{cost_lexeme}')
    usage_field = f',"usage":{{{",".join(fields)}}}' if usage else ""
    return (
        '{"model":"gpt-4o","provider":"loopback-provider",'
        '"choices":[{"message":{"role":"assistant",'
        '"content":"loopback answer"},"finish_reason":"stop"}]'
        f"{usage_field}"
        "}"
    ).encode()


def _default_factory_client(base_url: str) -> TracedLLMClient:
    """Build the configured gateway, tracing, and cache stack used by callers."""
    client = create_traced_gateway_client(
        model_name=MODEL_NAME,
        provider_hint=PROVIDER_NAME,
        run_id="e02-monetary-budget-hold",
        config=GatewayLLMConfig(
            base_url=f"{base_url}/v1",
            api_key="sk-e02-local-budget-hold",
            timeout_s=5.0,
            max_retries=0,
            default_provider=PROVIDER_NAME,
            cache_ttl_s=60.0,
            cache_maxsize=4,
            enable_prompt_sanitizer=False,
        ),
    )
    assert client is not None
    assert isinstance(client, TracedLLMClient)
    assert isinstance(client.unwrap(), GatewayLLMClient)
    return client


def _budget_state() -> BudgetState:
    return BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1.00"))})


@pytest.mark.asyncio
async def test_unknown_successful_http_completion_keeps_budget_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An obtained reply without cost or usage remains unknown and holds budget."""
    monkeypatch.delenv("POLISYOS_LLM_SIMULATION_MODE", raising=False)
    async with _gateway_http([_completion_payload(usage=False)]) as (base_url, requests):
        client = _default_factory_client(base_url)
        gateway = client.unwrap()
        state = _budget_state()
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=state,
            budget_keys=["run"],
            model_name=MODEL_NAME,
            run_id="e02-unknown-http-completion",
        )
        accounting_error: LLMAccountingError | None = None
        response: Any = None
        try:
            try:
                response = await enforcer.generate(
                    user="actual loopback request",
                    max_tokens=2,
                    _prompt_tokens_estimate=1,
                    _run_id="e02-unknown-http-completion",
                )
            except LLMAccountingError as exc:
                accounting_error = exc
                response = exc.response

            assert len(requests) == 1
            assert state.reserved.get("run", Decimal(0)) > 0
            assert state.spent.get("run", Decimal(0)) == 0
            assert accounting_error is not None
            assert accounting_error.response is response
            assert accounting_error.event["settlement_status"] == "unknown"
            assert extract_llm_response_data(response).content == "loopback answer"
        finally:
            await gateway.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cost_lexeme", "expected_spend"),
    [("0.02", Decimal("0.02")), ("0", Decimal("0"))],
    ids=["reported-cost", "reported-zero"],
)
async def test_known_http_cost_controls_commit_and_release_reservation(
    monkeypatch: pytest.MonkeyPatch,
    cost_lexeme: str,
    expected_spend: Decimal,
) -> None:
    """Reported cost and reported zero are valid controls on the same owner path."""
    monkeypatch.delenv("POLISYOS_LLM_SIMULATION_MODE", raising=False)
    async with _gateway_http([_completion_payload(cost_lexeme=cost_lexeme)]) as (
        base_url,
        requests,
    ):
        client = _default_factory_client(base_url)
        gateway = client.unwrap()
        state = _budget_state()
        enforcer = LLMBudgetEnforcer(
            client=client,
            budget_state=state,
            budget_keys=["run"],
            model_name=MODEL_NAME,
            run_id="e02-known-http-completion",
        )
        try:
            response = await enforcer.generate(
                user="actual loopback request",
                max_tokens=2,
                _prompt_tokens_estimate=1,
                _run_id="e02-known-http-completion",
            )

            assert len(requests) == 1
            assert extract_llm_response_data(response).content == "loopback answer"
            assert state.spent["run"] == expected_spend
            assert state.reserved.get("run", Decimal(0)) == 0
        finally:
            await gateway.aclose()
