"""OpenAI-compatible gateway client for runtime LLM calls."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any

import aiohttp

from polisyos.common.logger import get_logger
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path

logger = get_logger(__name__)

if TYPE_CHECKING:
    from .streaming import StreamChunk


@dataclass(slots=True)
class GatewayUsage:
    """Gateway usage public type."""

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
    error_envelope: dict[str, Any] | None = None


@dataclass(slots=True)
class GatewayLLMResponse:
    """Normalized completion payload with usage, headers, and parsed tool calls."""

    content: str
    usage: GatewayUsage = field(default_factory=GatewayUsage)
    model: str = "unknown"
    provider: str | None = None
    request_id: str | None = None
    response_headers: dict[str, str] | None = None
    raw: dict[str, Any] | None = None
    tool_calls: list[GatewayToolCall] | None = None


class _HTTPError(RuntimeError):
    """Gateway HTTP error with status code for intelligent retry."""

    def __init__(
        self,
        message: str,
        status: int,
        *,
        error_code: str | None = None,
        error_body: str | None = None,
        retry_after_s: float | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.error_code = error_code
        self.error_body = error_body
        self.retry_after_s = retry_after_s
        self.request_id = request_id


_NON_RETRYABLE_ERROR_CODES = {
    "insufficient_quota",
    "invalid_api_key",
    "invalid_request_error",
    "model_not_found",
    "permission_denied",
}

_RETRYABLE_ERROR_CODES = {
    "rate_limit_exceeded",
    "transfer_agent_capacity_reached",
    "server_error",
    "timeout",
    "upstream_timeout",
    "service_unavailable",
}

_TRANSPORT_ERRORS = (
    aiohttp.ClientError,
    asyncio.TimeoutError,
    OSError,
)


def _gateway_degraded(
    *,
    operation: str,
    reason: str,
    exc: BaseException,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return emit_degraded_path(
        component="llm.gateway_client",
        operation=operation,
        reason=reason,
        exc=exc,
        details=details,
        log=logger,
    )


def _is_retryable_status(status: int, error_code: str | None = None) -> bool:
    """Return True for transport/provider failures that warrant a retry."""
    if error_code in _NON_RETRYABLE_ERROR_CODES:
        return False
    if error_code in _RETRYABLE_ERROR_CODES:
        return True
    return status == 429 or status >= 500


def _should_retry_without_response_format(
    status: int,
    error_code: str | None,
    raw_text: str,
    payload: dict[str, Any],
) -> bool:
    """Handle gateways where JSON mode is temporarily unavailable.

    Some OpenAI-compatible gateways still accept prompt-instructed JSON but
    reject the `response_format` control flag. Retrying without the flag keeps
    the same model/prompt path alive while preserving downstream JSON parsing.
    """
    if "response_format" not in payload:
        return False
    if status not in {400, 422}:
        return False
    normalized_error = (error_code or "").lower()
    normalized_body = raw_text.lower()
    if normalized_error not in {"invalid_request", "invalid_request_error", "bad_request"}:
        return False
    return "json_object" in normalized_body or "response_format" in normalized_body


class GatewayLLMClient:
    """Small async client for OpenAI-compatible /chat/completions gateways.

    Supports connection pooling (shared ``aiohttp.ClientSession``),
    intelligent retry (429/5xx retryable, 4xx fatal), and SSE streaming.
    """

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
        preset: str | None = None,
        default_plugins: list[dict[str, Any]] | None = None,
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
        self.preset = preset.strip() if isinstance(preset, str) and preset.strip() else None
        self.default_plugins = [
            dict(plugin) for plugin in (default_plugins or []) if isinstance(plugin, dict)
        ]
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self, timeout_s: float) -> aiohttp.ClientSession:
        """Return the shared session, creating it lazily if needed."""
        del timeout_s
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=None),
            )
        return self._session

    def _request_timeout(self, timeout_s: float) -> aiohttp.ClientTimeout:
        return aiohttp.ClientTimeout(total=max(float(timeout_s), 1.0))

    async def aclose(self) -> None:
        """Close the underlying HTTP session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    async def generate(
        self,
        *,
        system: str | None = None,
        user: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        stream: bool | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        seed: int | None = None,
        metadata: dict[str, Any] | None = None,
        preset: str | None = None,
        plugins: list[dict[str, Any]] | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> GatewayLLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(
                system=system,
                user=user,
                messages=messages,
            ),
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
        effective_preset = _resolve_preset(preset, self.preset)
        if effective_preset is not None:
            payload["preset"] = effective_preset
        merged_plugins = _merge_plugins(self.default_plugins, plugins)
        if merged_plugins:
            payload["plugins"] = merged_plugins
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

    async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
        """Fetch live model IDs from ``/v1/models``."""
        url = f"{self.base_url}/models"
        headers = {
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        session = await self._ensure_session(
            float(timeout) if timeout is not None else self.timeout_s,
        )
        async with session.get(
            url,
            headers=headers,
            timeout=self._request_timeout(
                float(timeout) if timeout is not None else self.timeout_s,
            ),
        ) as response:
            raw_text = await response.text()
            if response.status >= 400:
                raise RuntimeError(
                    f"Gateway model catalog request failed ({response.status}): {raw_text[:400]}"
                )
            if not raw_text:
                return []
            try:
                decoded = json.loads(raw_text)
            except json.JSONDecodeError as exc:
                _gateway_degraded(
                    operation="list_model_ids",
                    reason="model_catalog_parse_failed",
                    exc=exc,
                    details={"payload_preview": raw_text[:200]},
                )
                return []
            if not isinstance(decoded, dict):
                _gateway_degraded(
                    operation="list_model_ids",
                    reason="model_catalog_shape_invalid",
                    exc=TypeError("model catalog payload must be a JSON object"),
                    details={"payload_type": type(decoded).__name__},
                )
                return []
            raw_models = decoded.get("data")
            if not isinstance(raw_models, list):
                return []
            return [
                model_id
                for item in raw_models
                if isinstance(item, dict)
                if (model_id := _as_str(item.get("id"))) is not None
            ]

    async def generate_stream(
        self,
        *,
        system: str | None = None,
        user: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        response_format: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        seed: int | None = None,
        metadata: dict[str, Any] | None = None,
        preset: str | None = None,
        plugins: list[dict[str, Any]] | None = None,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion, yielding ``StreamChunk`` objects.

        Requires ``polisyos.scientist.orchestration.llm.streaming`` (imported lazily).
        """
        from .streaming import parse_sse_stream

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(
                system=system,
                user=user,
                messages=messages,
            ),
            "stream": True,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if temperature is not None:
            payload["temperature"] = float(temperature)
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)
        if seed is not None:
            payload["seed"] = int(seed)
        if metadata is not None:
            payload["metadata"] = metadata
        effective_preset = _resolve_preset(preset, self.preset)
        if effective_preset is not None:
            payload["preset"] = effective_preset
        merged_plugins = _merge_plugins(self.default_plugins, plugins)
        if merged_plugins:
            payload["plugins"] = merged_plugins
        for key, value in kwargs.items():
            if value is not None:
                payload[key] = value

        effective_timeout = float(timeout) if timeout is not None else self.timeout_s
        url = f"{self.base_url}/chat/completions"
        headers = self._build_request_headers()

        session = await self._ensure_session(effective_timeout)
        resp = await session.post(
            url,
            json=payload,
            headers=headers,
            timeout=self._request_timeout(effective_timeout),
        )
        try:
            if resp.status >= 400:
                text = await resp.text()
                raise _HTTPError(
                    f"Gateway stream request failed ({resp.status}): {text[:400]}",
                    status=resp.status,
                )
            async for chunk in parse_sse_stream(resp):
                yield chunk
        finally:
            resp.release()

    def _build_messages(
        self,
        *,
        system: str | None,
        user: str | None,
        messages: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        if messages is not None:
            copied = [dict(item) for item in messages if isinstance(item, dict)]
            return copied or [{"role": "user", "content": ""}]

        built_messages: list[dict[str, Any]] = []
        if system:
            built_messages.append({"role": "system", "content": system})
        if user:
            built_messages.append({"role": "user", "content": user})
        if not built_messages:
            built_messages.append({"role": "user", "content": ""})
        return built_messages

    async def _post_json(
        self,
        *,
        endpoint: str,
        payload: dict[str, Any],
        timeout_s: float,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        headers = self._build_request_headers(idempotency_key=uuid.uuid4().hex)

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                session = await self._ensure_session(timeout_s)
                async with session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self._request_timeout(timeout_s),
                ) as response:
                    raw_text = await response.text()
                    if response.status >= 400:
                        response_headers = getattr(response, "headers", {}) or {}
                        error_code = _extract_error_code(raw_text)
                        retry_after_s = _parse_retry_after_seconds(
                            response_headers.get("Retry-After"),
                        )
                        request_id = response_headers.get("x-request-id")
                        if request_id:
                            logger.warning(
                                "Gateway request failed status={} code={} request_id={}",
                                response.status,
                                error_code,
                                request_id,
                            )
                        err = _HTTPError(
                            f"Gateway request failed ({response.status}): {raw_text[:400]}",
                            status=response.status,
                            error_code=error_code,
                            error_body=raw_text[:1000],
                            retry_after_s=retry_after_s,
                            request_id=request_id,
                        )
                        if _should_retry_without_response_format(
                            response.status,
                            error_code,
                            raw_text,
                            payload,
                        ):
                            fallback_payload = dict(payload)
                            fallback_payload.pop("response_format", None)
                            _gateway_degraded(
                                operation="chat_completion",
                                reason="response_format_unsupported_retry_plain_json",
                                exc=err,
                                details={
                                    "status": response.status,
                                    "error_code": error_code,
                                    "request_id": request_id,
                                    "model": self.model,
                                },
                            )
                            return await self._post_json(
                                endpoint=endpoint,
                                payload=fallback_payload,
                                timeout_s=timeout_s,
                            )
                        if not _is_retryable_status(response.status, error_code):
                            raise err
                        raise err
                    if not raw_text:
                        return {}
                    decoded = json.loads(raw_text)
                    if isinstance(decoded, dict):
                        response_headers = {
                            str(key): str(value)
                            for key, value in (getattr(response, "headers", {}) or {}).items()
                        }
                        decoded.setdefault(
                            "_gateway_request_id",
                            response_headers.get("x-request-id"),
                        )
                        decoded.setdefault("_gateway_response_headers", response_headers)
                        return decoded
                    return {}
            except _HTTPError as exc:
                last_error = exc
                if not _is_retryable_status(exc.status, exc.error_code):
                    # 4xx (except 429): fail immediately, do not retry
                    raise RuntimeError(str(exc)) from exc
                if attempt >= self.max_retries:
                    break
                retry_delay = (
                    exc.retry_after_s
                    if exc.retry_after_s is not None
                    else min(0.5 * (attempt + 1), 2.0)
                )
                await asyncio.sleep(retry_delay)
            except _TRANSPORT_ERRORS as exc:  # pragma: no cover - network errors depend on env
                last_error = exc
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(min(0.5 * (attempt + 1), 2.0))
        raise RuntimeError(f"Failed LLM gateway call to {url}") from last_error

    def _build_request_headers(
        self,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if not any(
            key.lower() == "x-idempotency-key" and str(value).strip()
            for key, value in headers.items()
        ):
            headers["x-idempotency-key"] = (idempotency_key or uuid.uuid4().hex).strip()
        return headers

    def _parse_completion_payload(self, payload: dict[str, Any]) -> GatewayLLMResponse:
        choices = payload.get("choices")
        first_choice = choices[0] if isinstance(choices, list) and choices else {}
        message = first_choice.get("message") if isinstance(first_choice, dict) else {}
        raw_content = message.get("content") if isinstance(message, dict) else None
        content = self._normalize_content(raw_content)

        usage_payload = payload.get("usage")
        cost_usd = _as_float(
            _extract_usage_value(usage_payload, "total_cost_usd")
            or _extract_usage_value(usage_payload, "cost_usd")
            or payload.get("cost_usd")
            or payload.get("total_cost_usd")
            or payload.get("cost")
        )
        if cost_usd is None:
            base_cost = _as_float(_extract_usage_value(usage_payload, "base_cost_usd"))
            platform_fee = _as_float(_extract_usage_value(usage_payload, "platform_fee_usd"))
            if base_cost is not None or platform_fee is not None:
                cost_usd = (base_cost or 0.0) + (platform_fee or 0.0)
        usage = GatewayUsage(
            prompt_tokens=_as_int(_extract_usage_value(usage_payload, "prompt_tokens")),
            completion_tokens=_as_int(_extract_usage_value(usage_payload, "completion_tokens")),
            total_tokens=_as_int(_extract_usage_value(usage_payload, "total_tokens")),
            cost_usd=cost_usd,
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
                error_envelope = None
                try:
                    if isinstance(args_str, str):
                        args = json.loads(args_str)
                    elif isinstance(args_str, dict):
                        args = args_str
                    else:
                        args = {}
                except (json.JSONDecodeError, TypeError) as exc:
                    args = {}
                    error_envelope = _gateway_degraded(
                        operation="parse_tool_call_arguments",
                        reason="tool_call_arguments_parse_error",
                        exc=exc,
                        details={
                            "tool_call_id": str(tc.get("id", "")),
                            "tool_name": str(fn.get("name", "")),
                            "arguments_preview": (
                                args_str[:200]
                                if isinstance(args_str, str)
                                else str(type(args_str).__name__)
                            ),
                        },
                    )
                tool_calls.append(
                    GatewayToolCall(
                        id=str(tc.get("id", "")),
                        name=str(fn.get("name", "")),
                        arguments=args,
                        error_envelope=error_envelope,
                    )
                )

        return GatewayLLMResponse(
            content=content,
            usage=usage,
            model=str(payload.get("model") or self.model),
            provider=_as_str(payload.get("provider")) or self.provider_hint,
            request_id=_as_str(payload.get("_gateway_request_id")),
            response_headers=(
                dict(payload.get("_gateway_response_headers"))
                if isinstance(payload.get("_gateway_response_headers"), dict)
                else None
            ),
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
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, Decimal, str)):
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


def _extract_error_code(raw_text: str) -> str | None:
    if not raw_text:
        return None
    try:
        decoded = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(decoded, dict):
        return None
    err = decoded.get("error")
    if isinstance(err, dict):
        code = _as_str(err.get("code") or err.get("type"))
        if code:
            return code
    return _as_str(decoded.get("code"))


def _parse_retry_after_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    delta = parsed - datetime.now(tz=UTC)
    return max(0.0, delta.total_seconds())


def _resolve_preset(
    request_preset: str | None,
    default_preset: str | None,
) -> str | None:
    for candidate in (request_preset, default_preset):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _merge_plugins(
    default_plugins: list[dict[str, Any]],
    request_plugins: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for source in (default_plugins, request_plugins or []):
        for plugin in source:
            if not isinstance(plugin, dict):
                continue
            plugin_id = _as_str(plugin.get("id")) or json.dumps(
                plugin,
                sort_keys=True,
                ensure_ascii=True,
                default=str,
            )
            if plugin_id in seen_ids:
                continue
            seen_ids.add(plugin_id)
            merged.append(dict(plugin))
    return merged


__all__ = [
    "GatewayLLMClient",
    "GatewayLLMResponse",
    "GatewayToolCall",
    "GatewayUsage",
]
