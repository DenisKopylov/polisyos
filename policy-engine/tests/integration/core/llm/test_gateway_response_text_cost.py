"""Lossless paid-cost intake from actual HTTP response text, without billing authority."""

from decimal import Decimal

import pytest

from polisyos.core.llm.response import extract_llm_response_data
from polisyos.core.llm.traced_client import LLMAccountingError
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
    if lexeme is not None:
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
    observed = extract_llm_response_data(response)
    assert observed.cost_usd is None and observed.cost_status == "invalid"


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
    with pytest.raises(LLMAccountingError) as failure:
        await invoke(enforcer)
    event = failure.value.event["producer_event"]
    assert event.amount is None and event.cost_origin == "unknown"
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.spent == {}
    assert snapshot.spend_receipts == {}
    assert snapshot.schema_version == "1.2"
    assert snapshot.state.reserved["run"] > 0
    record = next(iter(snapshot.completion_obligations.values()))
    assert record.event_payload["event_id"] == event.event_id
    assert record.event_payload["amount"] is None
    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    fresh = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
    with pytest.raises(RuntimeError, match="completion requires reconciliation"):
        fresh.pre_check("actual-next-work", "run")
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


@pytest.mark.parametrize(
    "cost_fields",
    [
        '"cost_usd":-1e-1000',
        '"cost_usd":null',
        '"cost_usd":true',
        '"cost_usd":{}',
        '"cost_usd":"malformed"',
        '"cost_usd":0,"total_cost_usd":1',
        '"cost_usd":0,"cost":1e-1000',
        '"cost_usd":0,"base_cost_usd":1,"platform_fee_usd":1',
    ],
)
@pytest.mark.asyncio
async def test_response_text_invalid_present_or_conflict_keeps_unknown_until_owner_resolution(
    tmp_path, cost_fields
):
    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    text = (
        '{"choices":[{"message":{"content":"received paid operation"}}],'
        '"provider":"provider-a","usage":{"prompt_tokens":1,"completion_tokens":1,'
        + cost_fields
        + "}}"
    )
    gateway = TextGateway(text)
    path, enforcer = build_owned_enforcer(tmp_path, gateway)
    with pytest.raises(LLMAccountingError) as failure:
        await invoke(enforcer)
    event = failure.value.event["producer_event"]
    assert gateway.transport.calls == 1
    assert failure.value.response is not None
    assert event.amount is None and event.cost_origin == "unknown"
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.spent == {} and snapshot.spend_receipts == {}
    assert snapshot.state.reserved["run"] > 0
    pending = next(iter(snapshot.completion_obligations.values()))
    assert pending.event_payload["event_id"] == event.event_id
    assert pending.event_payload["amount"] is None
    fresh = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
    before = path.read_bytes()
    with pytest.raises(RuntimeError, match="completion requires reconciliation"):
        fresh.pre_check("fresh-next-work", "run")
    with pytest.raises(LLMAccountingError):
        await invoke(enforcer)
    assert gateway.transport.calls == 1 and path.read_bytes() == before
