"""OpenAI-compatible gateway client for runtime LLM calls."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import aiohttp


@dataclass(slots=True)
class GatewayUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float | None = None


@dataclass(slots=True)
class GatewayToolCall:
    """A single tool call from an LLM response."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class GatewayLLMResponse:
    content: str
    usage: GatewayUsage = field(default_factory=GatewayUsage)
    model: str = "unknown"
    provider: str | None = None
    raw: dict[str, Any] | None = None
    tool_calls: list[GatewayToolCall] | None = None


class GatewayLLMClient:
    """Small async client for OpenAI-compatible /chat/completions gateways."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float = 60.0,
        max_retries: int = 1,
        provider_hint: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        normalized_base = base_url.rstrip("/")
        if not normalized_base:
            raise ValueError("LLM gateway base_url must not be empty")
        if not model.strip():
            raise ValueError("LLM model must not be empty")
        self.base_url = normalized_base
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.timeout_s = max(float(timeout_s), 1.0)
        self.max_retries = max(int(max_retries), 0)
        self.provider_hint = provider_hint
        self.extra_headers = dict(extra_headers or {})

    async def generate(
        self,
        *,
        system: str | None = None,
        user: str | None = None,
        response_format: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        stream: bool | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        seed: int | None = None,
        metadata: dict[str, Any] | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> GatewayLLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(system=system, user=user),
        }
        if response_format is not None:
            payload["response_format"] = response_format
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if stream is not None:
            payload["stream"] = bool(stream)
        if temperature is not None:
            payload["temperature"] = float(temperature)
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)
        if seed is not None:
            payload["seed"] = int(seed)
        if metadata is not None:
            payload["metadata"] = metadata
        # Preserve forward-compatibility with additional OpenAI-compatible fields.
        for key, value in kwargs.items():
            if value is not None:
                payload[key] = value

        raw = await self._post_json(
            endpoint="/chat/completions",
            payload=payload,
            timeout_s=float(timeout) if timeout is not None else self.timeout_s,
        )
        return self._parse_completion_payload(raw)

    def _build_messages(
        self,
        *,
        system: str | None,
        user: str | None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        if user:
            messages.append({"role": "user", "content": user})
        if not messages:
            messages.append({"role": "user", "content": ""})
        return messages

    async def _post_json(
        self,
        *,
        endpoint: str,
        payload: dict[str, Any],
        timeout_s: float,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                client_timeout = aiohttp.ClientTimeout(total=max(timeout_s, 1.0))
                async with aiohttp.ClientSession(timeout=client_timeout) as session:
                    async with session.post(url, json=payload, headers=headers) as response:
                        raw_text = await response.text()
                        if response.status >= 400:
                            raise RuntimeError(
                                f"Gateway request failed ({response.status}): {raw_text[:400]}"
                            )
                        if not raw_text:
                            return {}
                        decoded = json.loads(raw_text)
                        return decoded if isinstance(decoded, dict) else {}
            except Exception as exc:  # pragma: no cover - network errors depend on env
                last_error = exc
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(min(0.5 * (attempt + 1), 2.0))
        raise RuntimeError(f"Failed LLM gateway call to {url}") from last_error

    def _parse_completion_payload(self, payload: dict[str, Any]) -> GatewayLLMResponse:
        choices = payload.get("choices")
        first_choice = choices[0] if isinstance(choices, list) and choices else {}
        message = first_choice.get("message") if isinstance(first_choice, dict) else {}
        raw_content = message.get("content") if isinstance(message, dict) else None
        content = self._normalize_content(raw_content)

        usage_payload = payload.get("usage")
        usage = GatewayUsage(
            prompt_tokens=_as_int(_extract_usage_value(usage_payload, "prompt_tokens")),
            completion_tokens=_as_int(_extract_usage_value(usage_payload, "completion_tokens")),
            total_tokens=_as_int(_extract_usage_value(usage_payload, "total_tokens")),
            cost_usd=_as_float(
                _extract_usage_value(usage_payload, "cost_usd")
                or payload.get("cost_usd")
                or payload.get("cost")
            ),
        )
        if usage.total_tokens <= 0:
            usage.total_tokens = usage.prompt_tokens + usage.completion_tokens

        # Parse tool calls if present
        tool_calls: list[GatewayToolCall] | None = None
        raw_tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
        if isinstance(raw_tool_calls, list) and raw_tool_calls:
            tool_calls = []
            for tc in raw_tool_calls:
                fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                args_str = fn.get("arguments", "{}")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else (args_str if isinstance(args_str, dict) else {})
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(
                    GatewayToolCall(
                        id=str(tc.get("id", "")),
                        name=str(fn.get("name", "")),
                        arguments=args,
                    )
                )

        return GatewayLLMResponse(
            content=content,
            usage=usage,
            model=str(payload.get("model") or self.model),
            provider=_as_str(payload.get("provider")) or self.provider_hint,
            raw=payload,
            tool_calls=tool_calls,
        )

    def _normalize_content(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(parts)
        return ""


def _extract_usage_value(payload: Any, key: str) -> Any:
    if isinstance(payload, dict):
        return payload.get(key)
    return getattr(payload, key, None)


def _as_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return 0.0
    return parsed


def _as_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


__all__ = [
    "GatewayLLMClient",
    "GatewayLLMResponse",
    "GatewayUsage",
]
