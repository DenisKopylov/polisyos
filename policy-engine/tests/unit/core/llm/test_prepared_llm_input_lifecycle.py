"""Behavioral draft for prepared-input ownership and one-invocation scopes.

This assumes the R4 local carrier key `_polisyos_prepared_llm_input`. The key
must be popped by RecordingLLMClient before its prompt digest, context parsing,
call journal, or inner client invocation.
"""

from __future__ import annotations

import asyncio
import copy
import gc
import weakref
from contextlib import contextmanager

import pytest

from polisyos.common.producer_request import (
    consume_producer_request_context,
    producer_request_scope,
)
from polisyos.core.llm import PromptSanitizer, TracedLLMClient
from polisyos.runtime.quality.design_generation import RecordingLLMClient
from polisyos.scientist.orchestration.llm._n4_request import _request_args

_MODEL = "moonshotai/Kimi-K2.6"
_PROBLEM_REF = "sha256:" + "a" * 64
_PREPARED_INPUT_KEY = "_polisyos_prepared_llm_input"


class _Provider:
    def __init__(self, *, yield_before_response: bool = False):
        self.calls: list[dict[str, object]] = []
        self._yield_before_response = yield_before_response

    async def generate(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(copy.deepcopy(kwargs))
        if self._yield_before_response:
            await asyncio.sleep(0)
        return {"content": "{}", "usage": {"prompt_tokens": 2, "completion_tokens": 1}}


class _BlockingProvider(_Provider):
    def __init__(self):
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def generate(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(copy.deepcopy(kwargs))
        self.started.set()
        await self.release.wait()
        return {"content": "{}", "usage": {"prompt_tokens": 2, "completion_tokens": 1}}


class _Span:
    def set_attribute(self, *args: object) -> None:
        pass

    def set_status(self, *args: object) -> None:
        pass

    def record_exception(self, *args: object) -> None:
        pass


class _Tracer:
    @contextmanager
    def start_as_current_span(self, *args: object, **kwargs: object):
        yield _Span()


class _Metrics:
    def record_llm_call(self, **kwargs: object) -> None:
        pass


def _client(*, provider=None, yield_before_response: bool = False):
    provider = provider or _Provider(yield_before_response=yield_before_response)
    owner = TracedLLMClient(
        provider,
        model_name=_MODEL,
        tracer=_Tracer(),
        metrics=_Metrics(),
        prompt_sanitizer=PromptSanitizer(),
    )
    recorder = RecordingLLMClient(owner, model_id=_MODEL, producer_problem_ref=_PROBLEM_REF)
    return provider, owner, recorder


def _prepared_scope_inputs(recorder: RecordingLLMClient, **source: object):
    request = _request_args(recorder, stage="draft", attempt=1, **source)
    handle = request.pop(_PREPARED_INPUT_KEY)
    context = consume_producer_request_context(request, recorder._producer_request_binding)
    return request, handle, context


def test_preparing_and_abandoning_input_does_not_keep_handle_on_reused_client():
    _provider, owner, _recorder = _client()
    owner_ref = weakref.ref(owner)
    handle = owner.prepare_producer_input(user="private analyst@example.org")
    handle_ref = weakref.ref(handle)

    del handle
    gc.collect()

    assert owner_ref() is owner
    assert handle_ref() is None


def test_invalid_metadata_issuance_does_not_leave_owner_retained_handle(monkeypatch):
    _provider, owner, recorder = _client()
    owner_ref = weakref.ref(owner)
    prepared_refs = []
    prepare = owner.prepare_producer_input

    def observe_prepared_handle(**kwargs: object):
        handle = prepare(**kwargs)
        prepared_refs.append(weakref.ref(handle))
        return handle

    monkeypatch.setattr(owner, "prepare_producer_input", observe_prepared_handle)

    def issue_invalid_metadata() -> None:
        with pytest.raises(ValueError, match="producer_request_metadata_untyped"):
            _request_args(
                recorder,
                stage="draft",
                attempt=1,
                user="private analyst@example.org",
                metadata="invalid",
            )

    issue_invalid_metadata()
    gc.collect()

    assert len(prepared_refs) == 1
    assert prepared_refs[0]() is None
    assert owner_ref() is owner


def test_abandoning_issued_request_mapping_releases_its_prepared_handle():
    _provider, owner, recorder = _client()
    owner_ref = weakref.ref(owner)
    request = _request_args(
        recorder,
        stage="draft",
        attempt=1,
        user="private analyst@example.org",
    )
    handle_ref = weakref.ref(request[_PREPARED_INPUT_KEY])

    del request
    gc.collect()

    assert owner_ref() is owner
    assert handle_ref() is None


def test_closing_never_started_coroutine_releases_its_prepared_handle():
    provider, owner, recorder = _client()
    owner_ref = weakref.ref(owner)
    request = _request_args(
        recorder,
        stage="draft",
        attempt=1,
        user="private analyst@example.org",
    )
    handle_ref = weakref.ref(request[_PREPARED_INPUT_KEY])
    coroutine = recorder.generate(**request)
    del request

    assert handle_ref() is not None
    assert provider.calls == []
    coroutine.close()
    gc.collect()

    assert handle_ref() is None
    assert owner_ref() is owner


def test_cancel_before_first_coroutine_step_releases_handle_without_provider_call():
    provider, owner, recorder = _client()
    owner_ref = weakref.ref(owner)

    async def cancel_before_start() -> None:
        request = _request_args(
            recorder,
            stage="draft",
            attempt=1,
            user="private analyst@example.org",
        )
        handle_ref = weakref.ref(request[_PREPARED_INPUT_KEY])
        task = asyncio.create_task(recorder.generate(**request))
        del request
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)
        del task
        gc.collect()
        assert handle_ref() is None

    asyncio.run(cancel_before_start())

    assert provider.calls == []
    assert owner_ref() is owner


def test_deferred_recording_call_keeps_its_handle_until_success_then_releases_it():
    provider, owner, recorder = _client()
    owner_ref = weakref.ref(owner)
    request = _request_args(
        recorder,
        stage="draft",
        attempt=1,
        user="analyst@example.org",
    )
    handle_ref = weakref.ref(request[_PREPARED_INPUT_KEY])
    coroutine = recorder.generate(**request)
    del request

    assert provider.calls == []
    assert handle_ref() is not None

    asyncio.run(coroutine)
    del coroutine
    gc.collect()

    assert len(provider.calls) == 1
    assert _PREPARED_INPUT_KEY not in provider.calls[0]
    assert handle_ref() is None
    assert owner_ref() is owner


def test_cancellation_after_provider_entry_still_consumes_the_scope_invocation():
    provider = _BlockingProvider()
    _provider, owner, recorder = _client(provider=provider)
    request, handle, context = _prepared_scope_inputs(recorder, user="analyst@example.org")

    async def run_scope() -> None:
        with producer_request_scope(recorder._producer_request_binding, context, request):
            with owner.prepared_producer_input(handle, request):
                first = asyncio.create_task(owner.generate(**request))
                await provider.started.wait()
                first.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await first
                provider.release.set()
                with pytest.raises(
                    ValueError, match="producer_prepared_invocation_already_consumed"
                ):
                    await owner.generate(**request)

    asyncio.run(run_scope())

    assert len(provider.calls) == 1


def test_one_prepared_scope_refuses_a_second_sequential_generate():
    provider, owner, recorder = _client()
    request, handle, context = _prepared_scope_inputs(recorder, user="analyst@example.org")

    async def run_scope() -> None:
        with producer_request_scope(recorder._producer_request_binding, context, request):
            with owner.prepared_producer_input(handle, request):
                await owner.generate(**request)
                with pytest.raises(
                    ValueError, match="producer_prepared_invocation_already_consumed"
                ):
                    await owner.generate(**request)

    asyncio.run(run_scope())

    assert len(provider.calls) == 1
    # A fresh actual source occurrence remains usable after the refused duplicate.
    next_request = _request_args(recorder, stage="draft", attempt=2, user="new@example.org")
    asyncio.run(recorder.generate(**next_request))
    assert len(provider.calls) == 2
    assert provider.calls[-1]["metadata"]["polisyos_producer_request"]["attempt"] == 2


def test_one_prepared_scope_refuses_concurrent_inherited_generate_calls():
    provider, owner, recorder = _client(yield_before_response=True)
    request, handle, context = _prepared_scope_inputs(recorder, user="analyst@example.org")

    async def run_scope() -> list[object]:
        with producer_request_scope(recorder._producer_request_binding, context, request):
            with owner.prepared_producer_input(handle, request):
                tasks = [
                    asyncio.create_task(owner.generate(**request)),
                    asyncio.create_task(owner.generate(**request)),
                ]
                return await asyncio.gather(*tasks, return_exceptions=True)

    results = asyncio.run(run_scope())

    assert sum(not isinstance(result, BaseException) for result in results) == 1
    assert sum(isinstance(result, ValueError) for result in results) == 1
    rejected = next(result for result in results if isinstance(result, ValueError))
    assert str(rejected) == "producer_prepared_invocation_already_consumed"
    assert len(provider.calls) == 1
