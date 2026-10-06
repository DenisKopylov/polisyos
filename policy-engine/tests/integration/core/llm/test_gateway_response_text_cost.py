"""Lossless paid-cost intake from actual HTTP response text, without billing authority."""

from decimal import Decimal

import pytest

from polisyos.core.llm.response import extract_llm_response_data
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient


class _HTTPResponse:
    status = 200

    def __init__(self, text):
        self.headers = {"x-request-id": "response-text-request"}
        self._text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def text(self):
        return self._text


class _HTTPSession:
    """The transport alone is fixture-controlled; _post_json/parser remain native."""

    def __init__(self, text):
        self._text = text
        self.calls = 0

    def post(self, *args, **kwargs):
        self.calls += 1
        return _HTTPResponse(self._text)

    async def close(self):
        pass


class TextGateway(GatewayLLMClient):
    def __init__(self, text, *, model="test-model"):
        super().__init__(
            base_url="https://fixture.invalid",
            api_key="",
            model=model,
            provider_hint="provider-a",
            max_retries=0,
        )
        self.transport = _HTTPSession(text)
        self.normalized_response = None

    async def _ensure_session(self, timeout_s):
        return self.transport

    async def generate(self, **kwargs):
        self.normalized_response = await super().generate(**kwargs)
        return self.normalized_response


def response_text(source, field, lexeme):
    usage = '"prompt_tokens":1,"completion_tokens":1'
    root = '"provider":"provider-a"'
    if source == "usage":
        usage += f',"{field}":{lexeme}'
    else:
        root += f',"{field}":{lexeme}'
    return (
        '{"choices":[{"message":{"content":"observed response"}}],'
        + root
        + ',"usage":{'
        + usage
        + "}}"
    )


@pytest.mark.parametrize("source", ["usage", "payload"])
@pytest.mark.parametrize(
    "field", ["total_cost_usd", "cost_usd", "cost", "base_cost_usd", "platform_fee_usd"]
)
@pytest.mark.parametrize("lexeme", ["1e-1000", "-1e-1000"])
@pytest.mark.asyncio
async def test_response_text_nonzero_cost_lexeme_never_becomes_free(source, field, lexeme):
    gateway = TextGateway(response_text(source, field, lexeme))
    response = await gateway.generate(user="hello", max_tokens=1)
    # This actual decoder assertion distinguishes the HTTP-text boundary from dict-only probes.
    raw = response.raw["usage"] if source == "usage" else response.raw
    assert Decimal(str(raw[field])) == Decimal(lexeme)
    assert gateway.transport.calls == 1
    with pytest.raises(ValueError, match="provider cost"):
        extract_llm_response_data(response)


def build_owned_enforcer(tmp_path, gateway):
    # Lazy D imports let the B parser owner run the lossless intake selector independently.
    from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
    from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer

    path = tmp_path / "ledger.json"
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))})
    owner = BudgetMiddleware(state, ledger=FileBudgetLedger(path))
    enforcer = LLMBudgetEnforcer(
        client=gateway,
        budget_state=state,
        budget_keys=["run"],
        run_id="response-text-run",
        model_name="test-model",
        budget_middleware=owner,
    )
    return path, enforcer


async def invoke(enforcer):
    return await enforcer.generate(
        user="hello",
        max_tokens=1,
        _prompt_tokens_estimate=1,
        _evaluation_id="response-text-evaluation",
    )


@pytest.mark.asyncio
async def test_response_text_underflow_cannot_settle_zero_in_fresh_ledger(tmp_path):
    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger

    gateway = TextGateway(response_text("usage", "cost_usd", "1e-1000"))
    path, enforcer = build_owned_enforcer(tmp_path, gateway)
    with pytest.raises(ValueError, match="provider cost"):
        await invoke(enforcer)
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.spent == {}
    assert snapshot.spend_receipts == {}
    # B1.1 retains anonymous reserved capacity; durable owner/attempt binding
    # remains an explicit integration request rather than a fixture-only API.
    assert snapshot.state.reserved["run"] > 0
    assert gateway.transport.calls == 1


@pytest.mark.parametrize("lexeme", ["0", "0.0", "1"])
@pytest.mark.asyncio
async def test_response_text_real_zero_or_paid_cost_reopens_exactly(tmp_path, lexeme):
    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger

    gateway = TextGateway(response_text("usage", "cost_usd", lexeme))
    path, enforcer = build_owned_enforcer(tmp_path, gateway)
    await invoke(enforcer)
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.spent["run"] == Decimal(lexeme)
    assert snapshot.state.remaining("run") == Decimal(5) - Decimal(lexeme)
    assert snapshot.state.reserved["run"] == 0
    receipt = next(iter(snapshot.spend_receipts.values()))
    assert receipt.amount == Decimal(lexeme)
    assert receipt.provider == "provider-a"
    assert len(receipt.payload_digest) == 64
    assert receipt.key == "run"
    assert gateway.transport.calls == 1
