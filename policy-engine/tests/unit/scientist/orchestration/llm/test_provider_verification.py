"""Tests for persistent provider capability verification artifacts."""

from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.scientist.orchestration.llm.provider_verification import (
    ProviderCapabilityVerification,
    ProviderPreflightReport,
    _run_named_check,
    is_provider_capability_verified,
    load_provider_verification,
    resolve_gonka_api_key,
    run_provider_preflight,
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

    module = importlib.import_module(
        "polisyos.scientist.orchestration.llm.profiles.builtin_profiles"
    )
    module = importlib.reload(module)
    profile = next(
        item for item in module.BUILTIN_MODEL_PROFILES if item.profile_id == "qwen3_235b_gonka"
    )

    assert "tool_calling" in profile.capabilities


def test_gateway_response_request_id_is_preserved():
    from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient

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


def test_resolve_gonka_api_key_prefers_canonical_runtime_gateway_key(monkeypatch) -> None:
    monkeypatch.setenv("GONKA_API_KEY_3", "gp-test")
    monkeypatch.setenv("POLISYOS_LLM_GATEWAY_API_KEY", "sk-runtime-test-key")

    value, env_name = resolve_gonka_api_key()

    assert value == "sk-runtime-test-key"
    assert env_name == "POLISYOS_LLM_GATEWAY_API_KEY"


def test_resolve_gonka_api_key_keeps_legacy_smoke_key_fallback(monkeypatch) -> None:
    monkeypatch.setenv("GONKA_API_KEY_3", "gp-test")
    monkeypatch.delenv("POLISYOS_LLM_GATEWAY_API_KEY", raising=False)

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


@pytest.mark.asyncio
async def test_provider_preflight_missing_canonical_key_fails_without_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POLISYOS_LLM_GATEWAY_API_KEY", raising=False)
    constructed = False

    def _client_factory(**_kwargs: Any) -> object:
        nonlocal constructed
        constructed = True
        raise AssertionError("gateway client must not be constructed without an API key")

    report = await run_provider_preflight(
        models=["Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"],
        base_url="https://proxy.gonka.gg/v1",
        provider="gonka_proxy",
        api_key=None,
        api_key_env="POLISYOS_LLM_GATEWAY_API_KEY",
        client_factory=_client_factory,
    )

    assert isinstance(report, ProviderPreflightReport)
    assert report.status == "failed"
    assert report.failure is not None
    assert report.failure["code"] == "llm_provider_preflight_failed"
    assert report.failure["phase"] == "provider_preflight"
    assert report.failure["retryable"] is False
    assert constructed is False


@pytest.mark.asyncio
async def test_provider_preflight_model_absent_fails_before_completion() -> None:
    completion_called = False

    async def _fetch_json(url: str, **_kwargs: Any) -> dict[str, Any]:
        if url.endswith("/health"):
            return {"status": "ok"}
        if url.endswith("/v1/models") or url.endswith("/models"):
            return {"data": [{"id": "other-model"}]}
        if url.endswith("/api/models/capabilities"):
            return {"models": []}
        if url.endswith("/api/pricing"):
            return {"prices": []}
        raise AssertionError(f"unexpected URL: {url}")

    class _Client:
        async def generate(self, *_args: Any, **_kwargs: Any) -> object:
            nonlocal completion_called
            completion_called = True
            return SimpleNamespace(content='{"status":"ok"}', request_id="req-1")

        async def aclose(self) -> None:
            return None

    report = await run_provider_preflight(
        models=["missing-model"],
        base_url="https://proxy.gonka.gg/v1",
        provider="gonka_proxy",
        api_key="sk-test-provider-key",
        api_key_env="POLISYOS_LLM_GATEWAY_API_KEY",
        fetch_json=_fetch_json,
        client_factory=lambda **_kwargs: _Client(),
    )

    assert report.status == "failed"
    assert report.failure is not None
    assert report.failure["model"] == "missing-model"
    assert "not returned" in report.failure["message"]
    assert completion_called is False


@pytest.mark.asyncio
async def test_provider_preflight_success_is_cached_by_model_base_url_and_key() -> None:
    calls: list[str] = []

    async def _fetch_json(url: str, **_kwargs: Any) -> dict[str, Any]:
        calls.append(url)
        if url.endswith("/health"):
            return {"status": "ok"}
        if url.endswith("/v1/models") or url.endswith("/models"):
            return {"data": [{"id": "model-a"}]}
        if url.endswith("/api/models/capabilities"):
            return {"models": [{"model": "model-a", "context": 240000}]}
        if url.endswith("/api/pricing"):
            return {"model-a": {"per_token": 0.0}}
        raise AssertionError(f"unexpected URL: {url}")

    class _Client:
        async def generate(self, *_args: Any, **_kwargs: Any) -> object:
            calls.append("completion")
            return SimpleNamespace(
                content='{"status":"ok"}',
                request_id="req-success",
                provider="gonka_proxy",
                usage=SimpleNamespace(total_tokens=4),
            )

        async def aclose(self) -> None:
            return None

    kwargs = {
        "models": ["model-a"],
        "base_url": "https://proxy.gonka.gg/v1",
        "provider": "gonka_proxy",
        "api_key": "sk-test-provider-key",
        "api_key_env": "POLISYOS_LLM_GATEWAY_API_KEY",
        "fetch_json": _fetch_json,
        "client_factory": lambda **_kwargs: _Client(),
    }
    first = await run_provider_preflight(**kwargs)
    second = await run_provider_preflight(**kwargs)

    assert first.status == "ok"
    assert second.status == "ok"
    assert second.cache_hit is True
    assert calls.count("completion") == 1


@pytest.mark.asyncio
async def test_provider_preflight_completion_timeout_is_retryable() -> None:
    async def _fetch_json(url: str, **_kwargs: Any) -> dict[str, Any]:
        if url.endswith("/health"):
            return {"status": "ok"}
        if url.endswith("/v1/models") or url.endswith("/models"):
            return {"data": [{"id": "model-a"}]}
        if url.endswith("/api/models/capabilities"):
            return {"models": [{"model": "model-a"}]}
        if url.endswith("/api/pricing"):
            return {"model-a": {"per_token": 0.0}}
        raise AssertionError(f"unexpected URL: {url}")

    class _Client:
        async def generate(self, *_args: Any, **_kwargs: Any) -> object:
            raise TimeoutError("provider timed out")

        async def aclose(self) -> None:
            return None

    report = await run_provider_preflight(
        models=["model-a"],
        base_url="https://proxy.gonka.gg/v1",
        provider="gonka_proxy",
        api_key="sk-test-provider-key-timeout",
        api_key_env="POLISYOS_LLM_GATEWAY_API_KEY",
        fetch_json=_fetch_json,
        client_factory=lambda **_kwargs: _Client(),
    )

    assert report.status == "failed"
    assert report.retryable is True
    assert report.failure is not None
    assert report.failure["retryable"] is True


@pytest.mark.asyncio
async def test_provider_preflight_records_tiny_completion_degraded_events() -> None:
    async def _fetch_json(url: str, **_kwargs: Any) -> dict[str, Any]:
        if url.endswith("/health"):
            return {"status": "ok"}
        if url.endswith("/v1/models") or url.endswith("/models"):
            return {"data": [{"id": "model-a"}]}
        if url.endswith("/api/models/capabilities"):
            return {"models": [{"model": "model-a"}]}
        if url.endswith("/api/pricing"):
            return {"model-a": {"per_token": 0.0}}
        raise AssertionError(f"unexpected URL: {url}")

    class _Client:
        async def generate(self, *_args: Any, **_kwargs: Any) -> object:
            return SimpleNamespace(
                content='{"status":"ok"}',
                request_id="req-degraded",
                raw={
                    "_gateway_degraded_events": [
                        {
                            "reason": "response_format_unsupported_retry_plain_json",
                            "component": "llm.gateway_client",
                        }
                    ]
                },
            )

        async def aclose(self) -> None:
            return None

    report = await run_provider_preflight(
        models=["model-a"],
        base_url="https://proxy.gonka.gg/v1",
        provider="gonka_proxy",
        api_key="sk-test-provider-key-degraded",
        api_key_env="POLISYOS_LLM_GATEWAY_API_KEY",
        fetch_json=_fetch_json,
        client_factory=lambda **_kwargs: _Client(),
    )

    assert report.status == "ok"
    tiny_completion = next(check for check in report.checks if check.name == "tiny_completion")
    assert tiny_completion.details["response_format_mode"] == "fallback_plain_json"
    assert tiny_completion.details["degraded_events"] == [
        {
            "reason": "response_format_unsupported_retry_plain_json",
            "component": "llm.gateway_client",
        }
    ]
