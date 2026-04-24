"""SSE (Server-Sent Events) stream parser for OpenAI-compatible streaming responses."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from polisyos.common.logger import get_logger
from polisyos.scientist.error_semantics import emit_degraded_path

logger = get_logger(__name__)


@dataclass(slots=True)
class StreamChunk:
    """A single chunk from a streaming LLM response."""

    delta_content: str = ""
    finish_reason: str | None = None
    tool_call_index: int | None = None
    tool_call_id: str | None = None
    tool_call_name: str | None = None
    tool_call_arguments: str | None = None
    usage_delta: dict[str, int] | None = None
    error_envelope: dict[str, Any] | None = None


@dataclass(slots=True)
class StreamAccumulator:
    """Accumulates stream chunks into a final content string and usage."""

    content_parts: list[str] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    finish_reason: str | None = None
    model: str = "unknown"

    def feed(self, chunk: StreamChunk) -> None:
        if chunk.delta_content:
            self.content_parts.append(chunk.delta_content)
        if chunk.finish_reason:
            self.finish_reason = chunk.finish_reason
        if chunk.usage_delta:
            self.prompt_tokens += chunk.usage_delta.get("prompt_tokens", 0)
            self.completion_tokens += chunk.usage_delta.get("completion_tokens", 0)
            self.total_tokens += chunk.usage_delta.get("total_tokens", 0)

    @property
    def content(self) -> str:
        return "".join(self.content_parts)


async def parse_sse_stream(
    response: aiohttp.ClientResponse,
) -> AsyncIterator[StreamChunk]:
    """Parse an SSE stream from an OpenAI-compatible endpoint.

    Yields ``StreamChunk`` objects for each ``data:`` line that contains
    a valid JSON payload. Malformed JSON is surfaced as empty degraded
    chunks with an ``error_envelope``. Stops on ``data: [DONE]`` or stream end.
    """
    buffer = b""
    async for raw_bytes, _end_of_http_chunk in response.content.iter_chunks():
        buffer += raw_bytes
        while b"\n" in buffer:
            line_bytes, buffer = buffer.split(b"\n", 1)
            line = line_bytes.decode("utf-8", errors="replace").rstrip("\r")

            if not line.startswith("data:"):
                continue

            data_str = line[len("data:") :].strip()
            if data_str == "[DONE]":
                return
            if not data_str:
                continue

            try:
                payload = json.loads(data_str)
            except json.JSONDecodeError as exc:
                yield StreamChunk(
                    error_envelope=emit_degraded_path(
                        component="llm.streaming",
                        operation="parse_sse_stream",
                        reason="json_decode_error",
                        exc=exc,
                        details={"payload_preview": data_str[:200]},
                        log=logger,
                    )
                )
                continue

            chunk = _parse_sse_payload(payload)
            if chunk is not None:
                yield chunk

    # Process remaining buffer
    if buffer:
        line = buffer.decode("utf-8", errors="replace").rstrip("\r")
        if line.startswith("data:"):
            data_str = line[len("data:") :].strip()
            if data_str and data_str != "[DONE]":
                try:
                    payload = json.loads(data_str)
                    chunk = _parse_sse_payload(payload)
                    if chunk is not None:
                        yield chunk
                except json.JSONDecodeError as exc:
                    yield StreamChunk(
                        error_envelope=emit_degraded_path(
                            component="llm.streaming",
                            operation="parse_sse_stream",
                            reason="trailing_json_decode_error",
                            exc=exc,
                            details={"payload_preview": data_str[:200]},
                            log=logger,
                        )
                    )


def _parse_sse_payload(payload: dict[str, Any]) -> StreamChunk | None:
    """Extract a StreamChunk from an OpenAI-compatible SSE JSON payload."""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        # May be a usage-only final message
        usage = payload.get("usage")
        if isinstance(usage, dict):
            return StreamChunk(
                usage_delta={
                    "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                    "completion_tokens": int(usage.get("completion_tokens", 0)),
                    "total_tokens": int(usage.get("total_tokens", 0)),
                },
            )
        return None

    choice = choices[0]
    if not isinstance(choice, dict):
        return None

    delta = choice.get("delta", {})
    if not isinstance(delta, dict):
        delta = {}

    chunk = StreamChunk(
        delta_content=str(delta.get("content", "") or ""),
        finish_reason=choice.get("finish_reason"),
    )

    # Tool calls in streaming
    tool_calls = delta.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        tc = tool_calls[0]
        if isinstance(tc, dict):
            chunk.tool_call_index = tc.get("index")
            chunk.tool_call_id = tc.get("id")
            fn = tc.get("function", {})
            if isinstance(fn, dict):
                chunk.tool_call_name = fn.get("name")
                chunk.tool_call_arguments = fn.get("arguments")

    # Usage in chunk (some providers include it)
    usage = payload.get("usage") or choice.get("usage")
    if isinstance(usage, dict):
        chunk.usage_delta = {
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
            "total_tokens": int(usage.get("total_tokens", 0)),
        }

    return chunk


__all__ = [
    "StreamAccumulator",
    "StreamChunk",
    "parse_sse_stream",
]
