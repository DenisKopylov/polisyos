"""Actual prepared occurrences survive transforms; raw text never proves provenance."""

from __future__ import annotations

import asyncio
import copy
import re

import pytest

from polisyos.common.producer_request import (
    consume_producer_request_context,
    producer_request_scope,
)
from polisyos.core.llm import (
    PromptSanitizer,
    SanitizationRule,
    TracedLLMClient,
    scan_secret_and_pii,
)
from polisyos.runtime.quality.design_generation import _PREPARED_INPUT_KEY, RecordingLLMClient
from polisyos.scientist.orchestration.llm._n4_request import _request_args
from tests.unit.runtime.quality.test_n4_recorded_usage import _Metrics, _Tracer

_MODEL = "moonshotai/Kimi-K2.6"
_REF = "sha256:" + "a" * 64


class _Provider:
    def __init__(self):
        self.calls = []

    async def generate(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        return {"content": "{}", "usage": {"prompt_tokens": 2, "completion_tokens": 1}}


def _client(sanitizer=None):
    provider = _Provider()
    client = TracedLLMClient(
        provider,
        model_name=_MODEL,
        tracer=_Tracer(),
        metrics=_Metrics(),
        prompt_sanitizer=sanitizer,
    )
    return provider, client, RecordingLLMClient(client, model_id=_MODEL, producer_problem_ref=_REF)


def _wire_request(request):
    return {key: value for key, value in request.items() if key != _PREPARED_INPUT_KEY}


def test_actual_custom_transform_runs_once_for_the_owned_occurrence():
    sanitizer = PromptSanitizer(rules=(SanitizationRule("digits", re.compile(r"([0-9]+)")),))
    provider, _client_owner, recorder = _client(sanitizer)
    request = _request_args(recorder, stage="draft", attempt=12, user="123")
    expected = copy.deepcopy(_wire_request(request))
    assert request["user"] != "123"
    # The supported custom rule matches proper substrings of its own marker.
    # A text-idempotence exemption cannot correctly implement this occurrence.
    assert sanitizer.rules[0].pattern.search(request["user"])
    asyncio.run(recorder.generate(**request))
    assert provider.calls == [expected]
    assert provider.calls[0]["metadata"]["polisyos_producer_request"]["attempt"] == 12


def test_new_raw_literal_equal_to_an_issued_marker_is_still_sanitized_and_scanned():
    sanitizer = PromptSanitizer()
    issued = sanitizer.sanitize_payload({"secret": "alpha"})["secret"]
    scanned = scan_secret_and_pii(
        {"secret": issued},
        scope="connector request/response payloads",
        artifact_ref_or_route="fixture://prepared-input",
        sanitizer=sanitizer,
        redact=True,
    )
    assert scanned.has_findings
    assert scanned.redacted_payload["secret"] != issued
    assert any(report.redaction_applied for report in scanned.reports)
    assert sanitizer.restore_text(scanned.redacted_payload["secret"]) == issued
    provider, _owner, recorder = _client(sanitizer)
    request = _request_args(
        recorder, stage="draft", user="new raw marker", metadata={"secret": issued}
    )
    assert request["metadata"]["secret"] != issued
    asyncio.run(recorder.generate(**request))
    assert provider.calls[0]["metadata"]["secret"] == request["metadata"]["secret"]


@pytest.mark.parametrize("change", ["strip_context", "change_input", "added_messages"])
def test_prepared_occurrence_does_not_allow_a_second_call_quantity(change):
    provider, owner, recorder = _client(PromptSanitizer())
    request = _request_args(recorder, stage="draft", user="analyst@example.org")
    wire = _wire_request(request)
    context = consume_producer_request_context(wire, recorder._producer_request_binding)
    handle = request[_PREPARED_INPUT_KEY]
    with producer_request_scope(recorder._producer_request_binding, context, wire):
        with owner.prepared_producer_input(handle, wire):
            altered = copy.deepcopy(wire)
            if change == "strip_context":
                altered.pop("metadata")
            elif change == "change_input":
                altered["user"] = "new input"
            else:
                altered["messages"] = [{"role": "user", "content": "override"}]
            with pytest.raises(ValueError, match="producer_prepared_call_substituted"):
                asyncio.run(owner.generate(**altered))
    assert provider.calls == []
    # Scope cleanup cannot leave the previous occurrence as a privacy bypass.
    asyncio.run(owner.generate(user="analyst@example.org"))
    assert provider.calls[0]["user"] != "analyst@example.org"


def test_prepared_object_is_immutable_instance_owned_and_single_consumption():
    _provider, owner, recorder = _client(PromptSanitizer())
    request = _request_args(recorder, stage="draft", user="analyst@example.org")
    wire = _wire_request(request)
    context = consume_producer_request_context(wire, recorder._producer_request_binding)
    handle = request[_PREPARED_INPUT_KEY]
    with pytest.raises(AttributeError):
        handle._prepared_bytes = b"{}"
    with pytest.raises(TypeError):
        copy.copy(handle)
    _other_provider, other, _other_recorder = _client()
    with producer_request_scope(recorder._producer_request_binding, context, wire):
        with pytest.raises(ValueError, match="wrong_owner"):
            with other.prepared_producer_input(handle, wire):
                pass
        with owner.prepared_producer_input(handle, wire):
            asyncio.run(owner.generate(**wire))
        with pytest.raises(ValueError, match="not_issued_or_consumed"):
            with owner.prepared_producer_input(handle, wire):
                pass


def test_concurrent_source_occurrences_do_not_share_preparation_scope():
    provider, _owner, recorder = _client(PromptSanitizer())

    async def call(stage, attempt, text):
        request = _request_args(recorder, stage=stage, attempt=attempt, user=text)
        await asyncio.sleep(0)
        await recorder.generate(**request)
        return _wire_request(request)

    async def run():
        return await asyncio.gather(
            call("draft", 1, "one@example.org"), call("critic", 2, "two@example.org")
        )

    expected = asyncio.run(run())
    assert sorted(provider.calls, key=lambda x: x["user"]) == sorted(
        expected, key=lambda x: x["user"]
    )
