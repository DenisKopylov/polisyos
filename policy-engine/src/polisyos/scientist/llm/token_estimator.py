"""Pre-request token estimation for LLM budget checks."""

from __future__ import annotations

import math
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.scientist.error_semantics import emit_degraded_path

logger = get_logger(__name__)

_TOKENIZER_FALLBACK_ERRORS = (
    AttributeError,
    ImportError,
    LookupError,
    ModuleNotFoundError,
    RuntimeError,
    ValueError,
)


def estimate_tokens(
    text: str,
    *,
    model: str | None = None,
    provider_hint: str | None = None,
) -> int:
    """Estimate the number of tokens in *text*.

    Uses ``tiktoken`` with model-aware encoding when available,
    otherwise falls back to a conservative provider-aware heuristic.
    """
    if not text:
        return 0
    try:
        return _tiktoken_count(text, model=model)
    except _TOKENIZER_FALLBACK_ERRORS as exc:
        emit_degraded_path(
            component="llm.token_estimator",
            operation="estimate_tokens",
            reason="tokenizer_fallback",
            exc=exc,
            details={
                "model": model,
                "provider_hint": provider_hint,
                "text_chars": len(text),
            },
            log=logger,
        )
        return _fallback_token_estimate(
            text,
            model=model,
            provider_hint=provider_hint,
        )


def estimate_request_tokens(
    *,
    system: str | None = None,
    user: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    tools: list[dict[str, Any]] | None = None,
    model: str | None = None,
    provider_hint: str | None = None,
) -> int:
    """Estimate total prompt tokens for a chat completion request.

    Accounts for conservative message framing overhead
    and tool schema serialization.
    """
    total = 12
    if messages is not None:
        total += _estimate_messages_tokens(
            messages,
            model=model,
            provider_hint=provider_hint,
        )
    else:
        if system:
            total += estimate_tokens(
                system,
                model=model,
                provider_hint=provider_hint,
            ) + 8
        if user:
            total += estimate_tokens(
                user,
                model=model,
                provider_hint=provider_hint,
            ) + 8
    if tools:
        import json
        tools_text = json.dumps(tools, ensure_ascii=False, default=str)
        total += estimate_tokens(
            tools_text,
            model=model,
            provider_hint=provider_hint,
        ) + 24
    return max(total, 1)


def _estimate_messages_tokens(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    provider_hint: str | None = None,
) -> int:
    import json

    total = 0
    for message in messages:
        if not isinstance(message, dict):
            total += estimate_tokens(
                str(message),
                model=model,
                provider_hint=provider_hint,
            ) + 8
            continue
        total += estimate_tokens(
            str(message.get("role") or ""),
            model=model,
            provider_hint=provider_hint,
        ) + 8
        content = message.get("content")
        if isinstance(content, str):
            total += estimate_tokens(
                content,
                model=model,
                provider_hint=provider_hint,
            )
        elif content is not None:
            total += estimate_tokens(
                json.dumps(content, ensure_ascii=False, default=str),
                model=model,
                provider_hint=provider_hint,
            )
        for field_name in ("name", "tool_call_id"):
            value = message.get(field_name)
            if value:
                total += estimate_tokens(
                    str(value),
                    model=model,
                    provider_hint=provider_hint,
                )
        tool_calls = message.get("tool_calls")
        if tool_calls:
            total += estimate_tokens(
                json.dumps(tool_calls, ensure_ascii=False, default=str),
                model=model,
                provider_hint=provider_hint,
            ) + 12
    return total


def _fallback_token_estimate(
    text: str,
    *,
    model: str | None = None,
    provider_hint: str | None = None,
) -> int:
    provider = _normalize_provider_hint(model=model, provider_hint=provider_hint)
    encoded_len = len(text.encode("utf-8"))
    units = max(len(text), encoded_len)
    chars_per_token = {
        "anthropic": 2.7,
        "google": 2.8,
        "openai": 3.0,
        "azure-openai": 3.0,
        "xai": 3.0,
        "cohere": 3.1,
        "mistral": 3.1,
        "default": 3.0,
    }.get(provider or "default", 3.0)
    return max(int(math.ceil(units / chars_per_token)), 1)


def _normalize_provider_hint(
    *,
    model: str | None = None,
    provider_hint: str | None = None,
) -> str | None:
    raw_provider = (provider_hint or "").strip().lower()
    if raw_provider:
        return raw_provider
    raw_model = (model or "").strip().lower()
    if raw_model.startswith("claude") or "anthropic" in raw_model:
        return "anthropic"
    if raw_model.startswith("gemini") or "google" in raw_model:
        return "google"
    if raw_model.startswith("gpt") or raw_model.startswith("o") or "openai" in raw_model:
        return "openai"
    if raw_model.startswith("grok") or "xai" in raw_model:
        return "xai"
    if raw_model.startswith("command") or "cohere" in raw_model:
        return "cohere"
    if raw_model.startswith("mistral"):
        return "mistral"
    return None


def _tiktoken_count(text: str, *, model: str | None = None) -> int:
    """Count tokens using tiktoken (lazy-loaded)."""
    import tiktoken  # type: ignore[import-untyped]

    if model:
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
    else:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


__all__ = [
    "estimate_tokens",
    "estimate_request_tokens",
]
