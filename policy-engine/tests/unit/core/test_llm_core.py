from __future__ import annotations

import asyncio

import pytest

from polisyos.core.llm import estimate_cost, extract_llm_response_data, retry_async


class _Usage:
    def __init__(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _Response:
    def __init__(self, content: str, prompt_tokens: int, completion_tokens: int) -> None:
        self.content = content
        self.usage = _Usage(prompt_tokens, completion_tokens)


def test_extract_llm_response_data_from_object() -> None:
    data = extract_llm_response_data(_Response("ok", 10, 5))
    assert data.content == "ok"
    assert data.prompt_tokens == 10
    assert data.completion_tokens == 5
    assert data.total_tokens == 15


def test_extract_llm_response_data_from_dict() -> None:
    data = extract_llm_response_data(
        {"content": "n/a", "usage": {"prompt_tokens": 7, "completion_tokens": 3}}
    )
    # dict falls back to string content, but usage extraction should still work
    assert data.prompt_tokens == 7
    assert data.completion_tokens == 3


def test_estimate_cost_falls_back_to_text() -> None:
    value = estimate_cost(
        model="default",
        prompt_tokens=0,
        completion_tokens=0,
        response_text="abcdef",
    )
    assert value > 0.0


def test_retry_async_retries_then_succeeds() -> None:
    state = {"attempts": 0}

    async def _op() -> str:
        state["attempts"] += 1
        if state["attempts"] < 3:
            raise RuntimeError("try again")
        return "ok"

    result = asyncio.run(retry_async(_op, attempts=3))

    assert result == "ok"
    assert state["attempts"] == 3


def test_retry_async_raises_after_attempts() -> None:
    async def _op() -> str:
        raise RuntimeError("fail")

    with pytest.raises(RuntimeError, match="fail"):
        asyncio.run(retry_async(_op, attempts=2))
