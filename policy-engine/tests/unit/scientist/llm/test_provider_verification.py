"""Tests for persistent provider capability verification artifacts."""

from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime

import pytest
from polisyos.scientist.llm.provider_verification import (
    ProviderCapabilityVerification,
    _run_named_check,
    is_provider_capability_verified,
    load_provider_verification,
    resolve_gonka_api_key,
    save_provider_verification,
)


def test_provider_verification_round_trip(tmp_path):
    verification = ProviderCapabilityVerification(
        provider="gonka",
        model_id="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        base_url="https://api.gonkagate.com/v1",
        tool_calling_verified=True,
        response_healing_verified=True,
        checked_at=datetime.now(UTC),
        request_ids=["req-1", "req-2"],
    )

    path = save_provider_verification(verification, base_dir=tmp_path)
    loaded = load_provider_verification(
        provider="gonka",
        model_id="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        base_dir=tmp_path,
    )

    assert path.exists()
    assert loaded is not None
    assert loaded.tool_calling_verified is True
    assert loaded.response_healing_verified is True
    assert loaded.request_ids == ["req-1", "req-2"]


def test_provider_capability_verified_respects_artifact_freshness(tmp_path):
    verification = ProviderCapabilityVerification(
        provider="gonka",
        model_id="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        base_url="https://api.gonkagate.com/v1",
        tool_calling_verified=True,
        checked_at=datetime.now(UTC),
    )
    save_provider_verification(verification, base_dir=tmp_path)

    assert is_provider_capability_verified(
        provider="gonka",
        model_id="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        capability="tool_calling",
        base_dir=tmp_path,
    )


def test_builtin_qwen_profile_enables_tool_calling_from_verification_artifact(
    tmp_path,
    monkeypatch,
):
    verification = ProviderCapabilityVerification(
        provider="gonka",
        model_id="Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
        base_url="https://api.gonkagate.com/v1",
        tool_calling_verified=True,
        checked_at=datetime.now(UTC),
    )
    save_provider_verification(verification, base_dir=tmp_path)

    monkeypatch.setenv("POLISYOS_PROVIDER_VERIFICATION_DIR", str(tmp_path))
    monkeypatch.delenv("POLISYOS_QWEN_GONKA_TOOL_CALLING_VERIFIED", raising=False)
    monkeypatch.delenv("POLISYOS_QWEN_GONKA_TOOL_CALLING_EMERGENCY_OVERRIDE", raising=False)

    module = importlib.import_module("polisyos.scientist.llm.profiles.builtin_profiles")
    module = importlib.reload(module)
    profile = next(
        item for item in module.BUILTIN_MODEL_PROFILES if item.profile_id == "qwen3_235b_gonka"
    )

    assert "tool_calling" in profile.capabilities


def test_gateway_response_request_id_is_preserved():
    from polisyos.scientist.llm.gateway_client import GatewayLLMClient

    client = GatewayLLMClient(
        base_url="https://api.gonkagate.com/v1",
        api_key="key",
        model="m",
    )
    response = client._parse_completion_payload(
        {
            "model": "m",
            "_gateway_request_id": "req-123",
            "_gateway_response_headers": {"x-request-id": "req-123"},
            "choices": [{"message": {"content": json.dumps({"ok": True})}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2},
        }
    )

    assert response.request_id == "req-123"
    assert response.response_headers == {"x-request-id": "req-123"}


def test_resolve_gonka_api_key_uses_only_designated_smoke_key(monkeypatch) -> None:
    monkeypatch.setenv("GONKA_API_KEY_3", "gp-test")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "should-not-be-used")

    value, env_name = resolve_gonka_api_key()

    assert value == "gp-test"
    assert env_name == "GONKA_API_KEY_3"


def test_provider_verification_binds_request_ids_and_notes() -> None:
    verification = ProviderCapabilityVerification(
        provider="gonka",
        model_id="model",
        base_url="https://api.gonkagate.com/v1",
        request_ids=[f"req-{idx}" for idx in range(80)],
        verification_notes=["", *[f"note-{idx}" for idx in range(80)]],
    )

    assert len(verification.request_ids) == 64
    assert verification.request_ids[0] == "req-16"
    assert len(verification.verification_notes) == 64
    assert verification.verification_notes[0] == "note-16"


def test_load_provider_verification_invalid_json_returns_none(tmp_path) -> None:
    target = tmp_path / "gonka__model.json"
    target.write_text("{invalid json", encoding="utf-8")

    loaded = load_provider_verification(
        provider="gonka",
        model_id="model",
        base_dir=tmp_path,
    )

    assert loaded is None


@pytest.mark.asyncio
async def test_run_named_check_does_not_swallow_assertion_errors() -> None:
    async def _runner() -> dict[str, object]:
        raise AssertionError("bug")

    with pytest.raises(AssertionError, match="bug"):
        await _run_named_check("check", _runner, request_ids=[])
