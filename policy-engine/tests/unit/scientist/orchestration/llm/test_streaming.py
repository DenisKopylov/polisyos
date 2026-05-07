"""Tests for SSE streaming parser."""

from __future__ import annotations

import json

import pytest
from polisyos.scientist.orchestration.llm.streaming import (
    StreamAccumulator,
    StreamChunk,
    parse_sse_stream,
)


def _make_sse_lines(*payloads: dict | str) -> bytes:
    """Build raw SSE bytes from payload dicts or raw strings."""
    lines: list[str] = []
    for p in payloads:
        if isinstance(p, dict):
            lines.append(f"data: {json.dumps(p)}")
        else:
            lines.append(p)
    lines.append("data: [DONE]")
    return "\n".join(lines).encode("utf-8")


class _FakeResponse:
    """Fake aiohttp response with an async content iterator."""

    def __init__(self, raw: bytes) -> None:
        self._raw = raw

    @property
    def content(self):
        parent = self

        class _Content:
            async def iter_chunks(self):
                yield parent._raw, True

        return _Content()


@pytest.mark.asyncio
async def test_parse_basic_content():
    payload = {
        "choices": [{"delta": {"content": "Hello"}, "finish_reason": None}],
    }
    resp = _FakeResponse(_make_sse_lines(payload))
    chunks = [c async for c in parse_sse_stream(resp)]
    assert len(chunks) == 1
    assert chunks[0].delta_content == "Hello"
    assert chunks[0].finish_reason is None


@pytest.mark.asyncio
async def test_parse_multiple_chunks():
    p1 = {"choices": [{"delta": {"content": "Hel"}, "finish_reason": None}]}
    p2 = {"choices": [{"delta": {"content": "lo"}, "finish_reason": None}]}
    p3 = {"choices": [{"delta": {}, "finish_reason": "stop"}]}
    resp = _FakeResponse(_make_sse_lines(p1, p2, p3))
    chunks = [c async for c in parse_sse_stream(resp)]
    assert len(chunks) == 3
    assert chunks[0].delta_content == "Hel"
    assert chunks[1].delta_content == "lo"
    assert chunks[2].finish_reason == "stop"


@pytest.mark.asyncio
async def test_parse_error_midstream():
    """Malformed JSON lines surface a degraded parsing envelope."""
    good = {"choices": [{"delta": {"content": "ok"}, "finish_reason": None}]}
    raw = f"data: {json.dumps(good)}\ndata: {{broken json\ndata: [DONE]\n".encode()
    resp = _FakeResponse.__new__(_FakeResponse)
    resp._raw = raw
    chunks = [c async for c in parse_sse_stream(resp)]
    assert len(chunks) == 2
    assert chunks[0].delta_content == "ok"
    assert chunks[1].error_envelope is not None
    assert chunks[1].error_envelope["reason"] == "json_decode_error"


@pytest.mark.asyncio
async def test_parse_empty_stream():
    resp = _FakeResponse(b"data: [DONE]\n")
    chunks = [c async for c in parse_sse_stream(resp)]
    assert chunks == []


@pytest.mark.asyncio
async def test_parse_tool_calls():
    payload = {
        "choices": [
            {
                "delta": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "tc_1",
                            "function": {"name": "search", "arguments": '{"q": "test"}'},
                        }
                    ],
                },
                "finish_reason": None,
            }
        ],
    }
    resp = _FakeResponse(_make_sse_lines(payload))
    chunks = [c async for c in parse_sse_stream(resp)]
    assert len(chunks) == 1
    assert chunks[0].tool_call_name == "search"
    assert chunks[0].tool_call_id == "tc_1"


@pytest.mark.asyncio
async def test_parse_usage_accumulation():
    p1 = {"choices": [{"delta": {"content": "a"}, "finish_reason": None}]}
    p_usage = {"usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
    resp = _FakeResponse(_make_sse_lines(p1, p_usage))
    chunks = [c async for c in parse_sse_stream(resp)]
    assert len(chunks) == 2
    assert chunks[1].usage_delta is not None
    assert chunks[1].usage_delta["total_tokens"] == 15


def test_stream_accumulator():
    acc = StreamAccumulator()
    acc.feed(StreamChunk(delta_content="Hello "))
    acc.feed(StreamChunk(delta_content="world"))
    acc.feed(StreamChunk(finish_reason="stop"))
    acc.feed(
        StreamChunk(usage_delta={"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8})
    )
    assert acc.content == "Hello world"
    assert acc.finish_reason == "stop"
    assert acc.total_tokens == 8
