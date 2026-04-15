"""Tests for first-party prompt/result sanitization."""

from __future__ import annotations

import pytest

from polisyos.core.llm import PromptSanitizer
from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.scientist.llm.gateway_client import GatewayLLMResponse, GatewayUsage


class _EchoLLMClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def generate(self, **kwargs):
        self.calls.append(dict(kwargs))
        return GatewayLLMResponse(
            content=str(kwargs.get("user") or ""),
            usage=GatewayUsage(),
            raw={"echo": kwargs.get("user") or ""},
        )


def test_prompt_sanitizer_uses_stable_placeholders_and_restores_payloads():
    sanitizer = PromptSanitizer()
    original = (
        "Bearer token-secret-value and email test@example.org and "
        "password = hunter2-secret"
    )

    sanitized_once = sanitizer.sanitize_text(original)
    sanitized_twice = sanitizer.sanitize_text(original)

    assert sanitized_once == sanitized_twice
    assert "test@example.org" not in sanitized_once
    assert "hunter2-secret" not in sanitized_once
    assert "[POLISYOS_SECRET_" in sanitized_once
    assert sanitizer.restore_text(sanitized_once) == original

    payload = sanitizer.sanitize_payload(
        {
            "tuple_value": ("test@example.org", "plain"),
            "nested": ["Bearer token-secret-value"],
        }
    )

    assert isinstance(payload["tuple_value"], tuple)
    assert sanitizer.restore_payload(payload) == {
        "tuple_value": ("test@example.org", "plain"),
        "nested": ["Bearer token-secret-value"],
    }


def test_traced_client_sanitizes_positional_prompt_preview_text():
    traced = TracedLLMClient(
        _EchoLLMClient(),
        model_name="m",
        prompt_sanitizer=PromptSanitizer(),
    )

    prompt_text = traced._build_prompt_text("Contact test@example.org")

    assert "test@example.org" not in prompt_text
    assert "[POLISYOS_SECRET_" in prompt_text


@pytest.mark.asyncio
async def test_traced_client_sanitizes_requests_and_restores_responses():
    base_client = _EchoLLMClient()
    traced = TracedLLMClient(
        base_client,
        model_name="m",
        prompt_sanitizer=PromptSanitizer(),
    )

    response = await traced.generate(
        system="internal",
        user="Contact test@example.org with sk-1234567890abcdefgh",
    )

    assert len(base_client.calls) == 1
    sent_user = str(base_client.calls[0]["user"])
    assert "test@example.org" not in sent_user
    assert "sk-1234567890abcdefgh" not in sent_user
    assert "[POLISYOS_SECRET_" in sent_user

    assert response.content == "Contact test@example.org with sk-1234567890abcdefgh"
    assert response.raw == {
        "echo": "Contact test@example.org with sk-1234567890abcdefgh"
    }
