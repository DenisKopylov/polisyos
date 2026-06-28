"""Tests for first-party prompt/result sanitization."""

from __future__ import annotations

import pytest

from polisyos.core.llm import PromptSanitizer, scan_secret_and_pii
from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage


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
    original = "Bearer token-secret-value and email test@example.org and password = hunter2-secret"

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


def test_secret_pii_scan_reports_exact_fields_without_authority_false_positive():
    clean = scan_secret_and_pii(
        {"authority_role": "producer_authority", "authority_boundary": "runtime"},
        scope="DAG bundles",
        artifact_ref_or_route="gy-loop://clean-authority-payload",
        redact=False,
        block_on_findings=True,
    )

    assert clean.has_findings is False
    assert clean.reports[0].finding_kind == "none"
    assert set(clean.reports[0].model_dump()) == {
        "scope",
        "artifact_ref_or_route",
        "detector_version",
        "finding_kind",
        "redaction_applied",
        "authority_surface_blocked",
        "negative_fixture_result",
    }

    secret = scan_secret_and_pii(
        {
            "auth_credentials": {"token": "sk-testsecret1234567890"},
            "contact": "policy.fixture@example.org",
        },
        scope="connector request/response payloads",
        artifact_ref_or_route="connector://fixture",
        redact=True,
        block_on_findings=False,
    )

    assert secret.has_findings is True
    assert "policy.fixture@example.org" not in str(secret.redacted_payload)
    assert "sk-testsecret1234567890" not in str(secret.redacted_payload)
    assert {report.negative_fixture_result for report in secret.reports} == {"redacted"}


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
    assert response.raw == {"echo": "Contact test@example.org with sk-1234567890abcdefgh"}
