"""Actual complete-call and prepared-send controls, including stripped context."""

from __future__ import annotations

import asyncio
import copy
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from aiohttp import web

from polisyos.common._producer_request import (
    _binding_scope,
    _call_context,
    _ProducerBinding,
    _read_payload,
    _request_args,
)
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient

_REF = "sha256:" + "a" * 64
_MODEL = "fixture-model"
_KEY = "polisyos_producer_request"


def _client(subject=_REF):
    return SimpleNamespace(_producer_request_binding=_ProducerBinding(subject, _MODEL, "fixture"))


def _gateway(base_url="http://127.0.0.1:1/v1"):
    return GatewayLLMClient(base_url=base_url, api_key="", model=_MODEL, max_retries=0)


def _issued(client, *, stage="draft", attempt=0, **values):
    return _request_args(client, stage=stage, attempt=attempt, **values)


def _prepare(client, gateway, values):
    context = _call_context(values, client._producer_request_binding)
    with _binding_scope(client._producer_request_binding, context, values):
        return gateway.prepare_cache_request(**values)


@asynccontextmanager
async def _http(handler):
    app = web.Application()
    app.router.add_post("/v1/chat/completions", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    try:
        yield f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}/v1"
    finally:
        await runner.cleanup()


def _response():
    return web.json_response(
        {
            "choices": [{"message": {"content": "done"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
    )


@pytest.mark.parametrize("metadata", [None, {}, {"other": {"retained": True}}])
def test_complete_inputs_and_metadata_presence_reach_preparation(metadata):
    client = _client()
    values = _issued(client, user="actual input", metadata=metadata, plugins=[{"id": "x"}])
    context = _call_context(values, client._producer_request_binding)
    with _binding_scope(client._producer_request_binding, context, values):
        payload = _gateway().completion_request_payload(**values)
        assert _gateway().prepare_cache_request(**values).identity
    assert _read_payload(payload)["subject_ref"] == _REF
    assert payload["messages"][-1]["content"] == "actual input"
    assert payload["metadata"].get("other") == (metadata or {}).get("other")


@pytest.mark.parametrize(
    ("field", "value"), [("stage", "critic"), ("attempt", 9), ("subject_ref", "sha256:" + "b" * 64)]
)
def test_context_substitution_cannot_borrow_an_issued_identity(field, value):
    client = _client()
    values = _issued(client, user="same input")
    values["metadata"][_KEY][field] = value
    with pytest.raises(ValueError):
        _prepare(client, _gateway(), values)


@pytest.mark.parametrize("removal", ["reserved", "all_metadata"])
def test_owned_context_cannot_disappear_after_recorder_admission_at_prepare(removal):
    client = _client()
    values = _issued(client, user="original")
    context = _call_context(values, client._producer_request_binding)
    altered = copy.deepcopy(values)
    if removal == "reserved":
        altered["metadata"].pop(_KEY)
    else:
        altered.pop("metadata")
    with (
        _binding_scope(client._producer_request_binding, context, values),
        pytest.raises(ValueError, match="context_fields_invalid"),
    ):
        _gateway().prepare_cache_request(**altered)


@pytest.mark.parametrize(
    "extra",
    [
        {"messages": [{"role": "user", "content": "override"}]},
        {"future_option": "override"},
        {"future_option": None},
        {"tools": [{"type": "function", "function": {"name": "different"}}]},
    ],
)
def test_added_absent_inputs_cannot_hide_outside_an_old_name_projection(extra):
    client = _client()
    values = _issued(client, user="original")
    context = _call_context(values, client._producer_request_binding)
    with (
        _binding_scope(client._producer_request_binding, context, values),
        pytest.raises(ValueError, match="transport_input_substituted"),
    ):
        _gateway().prepare_cache_request(**{**values, **extra})


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["reserved", "metadata", "messages", "resigned_messages"])
async def test_real_send_rejects_changes_to_a_genuine_prepared_emission(mutation):
    client = _client()
    gateway = _gateway()
    values = _issued(client, user="original")
    original_send = gateway._post_json

    async def altered_send(**kwargs):
        payload = copy.deepcopy(kwargs["payload"])
        if mutation == "reserved":
            payload["metadata"].pop(_KEY)
        elif mutation == "metadata":
            payload.pop("metadata")
        else:
            payload["messages"][-1]["content"] = "different"
            if mutation == "resigned_messages":
                import hashlib
                import json

                context = payload["metadata"][_KEY]
                context.pop("payload_sha256")
                context["payload_sha256"] = hashlib.sha256(
                    json.dumps(
                        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
                    ).encode()
                ).hexdigest()
        return await original_send(**{**kwargs, "payload": payload})

    gateway._post_json = altered_send
    prepared = _prepare(client, gateway, values)
    with pytest.raises(
        ValueError, match=r"context_fields_invalid|payload_substituted|prepared_body_substituted"
    ):
        await prepared.execute()
    await gateway.aclose()


@pytest.mark.asyncio
async def test_real_deferred_execution_and_closed_response_format_fallback():
    received = []

    async def handler(request):
        payload = await request.json()
        received.append(payload)
        if "response_format" in payload:
            return web.json_response(
                {
                    "error": {
                        "code": "invalid_request_error",
                        "message": "response_format json_object unsupported",
                    }
                },
                status=422,
            )
        return _response()

    async with _http(handler) as url:
        gateway = _gateway(url)
        client = _client()
        values = _issued(
            client,
            user="x",
            response_format={"type": "json_object"},
            temperature=0.25,
            max_tokens=7,
            future_body_option={"retained": True},
        )
        prepared = _prepare(client, gateway, values)
        # Outside the original ContextVar scope: the opaque prepared obligation survives.
        result = await prepared.execute()
        assert result.response.content == "done"
        assert len(received) == 2
        assert "response_format" in received[0] and "response_format" not in received[1]
        assert _read_payload(received[0])["context_id"] == _read_payload(received[1])["context_id"]
        expected = copy.deepcopy(received[0])
        expected.pop("response_format")
        actual = copy.deepcopy(received[1])
        expected["metadata"][_KEY].pop("payload_sha256")
        actual["metadata"][_KEY].pop("payload_sha256")
        assert actual == expected
        await gateway.aclose()


@pytest.mark.asyncio
async def test_prepared_emission_cannot_be_borrowed_by_a_different_active_context():
    gateway = _gateway()
    first = _client()
    prepared = _prepare(first, gateway, _issued(first, user="first"))
    second = _client("sha256:" + "b" * 64)
    values = _issued(second, user="second")
    context = _call_context(values, second._producer_request_binding)
    with (
        _binding_scope(second._producer_request_binding, context, values),
        pytest.raises(ValueError, match="emission_scope_mismatch"),
    ):
        await prepared.execute()
    await gateway.aclose()


@pytest.mark.asyncio
async def test_concurrent_attempts_and_exceptional_exit_keep_scopes_isolated():
    async def prepare(subject, stage, attempt):
        client = _client(subject)
        values = _issued(client, stage=stage, attempt=attempt, user=subject)
        context = _call_context(values, client._producer_request_binding)
        with _binding_scope(client._producer_request_binding, context, values):
            await asyncio.sleep(0)
            payload = _gateway().completion_request_payload(**values)
            assert (_read_payload(payload)["subject_ref"], _read_payload(payload)["attempt"]) == (
                subject,
                attempt,
            )
        with pytest.raises(ValueError, match="payload_without_owner"):
            _gateway().completion_request_payload(**values)

    await asyncio.gather(prepare(_REF, "draft", 0), prepare("sha256:" + "b" * 64, "critic", 4))
    client = _client()
    values = _issued(client, user="x")
    context = _call_context(values, client._producer_request_binding)
    with (
        pytest.raises(RuntimeError),
        _binding_scope(client._producer_request_binding, context, values),
    ):
        raise RuntimeError("owner failed")
    with pytest.raises(ValueError, match="payload_without_owner"):
        _gateway().completion_request_payload(**values)


def test_equal_semantic_requests_keep_cache_identity_and_each_requires_issuance():
    client = _client()
    gateway = _gateway()
    first = _issued(client, user="same", attempt=2)
    second = _issued(client, user="same", attempt=2)
    assert first == second
    assert _prepare(client, gateway, first).identity == _prepare(client, gateway, second).identity
    with pytest.raises(ValueError, match="context_not_issued"):
        _prepare(client, gateway, first)


def test_unbound_call_shape_stays_compatible_and_reserved_namespace_cannot_override_owner():
    values = {"user": "ordinary", "metadata": {"other": True}, "temperature": 0.0}
    assert _request_args(object(), stage="not-n4", **values) == values
    assert _call_context(values, None) is None
    assert _gateway().completion_request_payload(**values) == {
        "model": _MODEL,
        "messages": [{"role": "user", "content": "ordinary"}],
        "metadata": {"other": True},
        "temperature": 0.0,
    }
    with pytest.raises(ValueError, match="namespace_reserved"):
        _issued(_client(), user="x", metadata={_KEY: {}})
