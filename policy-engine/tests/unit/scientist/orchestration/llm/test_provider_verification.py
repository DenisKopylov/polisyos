"""Tests for persistent provider capability verification artifacts."""

from __future__ import annotations

import asyncio
import importlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.scientist.orchestration.llm.provider_verification import (
    ProviderCapabilityVerification,
    ProviderPreflightReport,
    _probe_json_completion,
    _probe_response_healing,
    _run_named_check,
    is_provider_capability_verified,
    load_provider_verification,
    resolve_gonka_api_key,
    run_provider_preflight,
    save_provider_verification,
)


class _WrappedJSONProviderClient:
    async def generate(self, **kwargs: object) -> SimpleNamespace:
        del kwargs
        return SimpleNamespace(
            content='<think>provider text</think>{"status":"ok","sum":4}',
            request_id="req-wrapped-json",
            provider="test-provider",
            usage=SimpleNamespace(total_tokens=4),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("probe", [_probe_json_completion, _probe_response_healing])
async def test_provider_conformance_probes_reject_wrapped_json(probe) -> None:
    result = await probe(_WrappedJSONProviderClient())

    assert result["passed"] is False
    assert result["error"]


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url",
    [
        "file:///tmp/provider/v1",
        "ftp://provider.example/v1",
        "custom+provider://provider.example/v1",
        "https:///missing-host/v1",
        "https://preflight-user-secret:preflight-password-secret@provider.example/v1",
        "https://preflight-user-secret:preflight-password-secret@[broken/v1",
    ],
)
async def test_provider_preflight_rejects_non_http_or_ambiguous_base_url_before_fetch(
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
) -> None:
    module = importlib.import_module("polisyos.scientist.orchestration.llm.provider_verification")
    monkeypatch.delenv("POLISYOS_LLM_SIMULATION_MODE", raising=False)
    monkeypatch.setattr(module, "_PREFLIGHT_CACHE", {})
    fetch_calls: list[str] = []
    client_calls: list[str] = []

    async def fetch_json(url: str, **_kwargs: Any) -> dict[str, Any]:
        fetch_calls.append(url)
        return {"data": [{"id": "model"}]}

    def client_factory(**_kwargs: Any) -> object:
        client_calls.append("constructed")
        raise AssertionError("invalid provider URL must fail before completion client")

    report = await run_provider_preflight(
        models=["model"],
        base_url=base_url,
        api_key="sk-provider-preflight-test-key",
        fetch_json=fetch_json,
        client_factory=client_factory,
        ttl_s=0,
    )

    assert report.status == "failed"
    assert report.failure is not None
    assert report.checks[0].name == "health"
    assert report.checks[0].status == "failed"
    assert fetch_calls == []
    assert client_calls == []
    serialized_report = report.model_dump_json()
    assert "preflight-user-secret" not in serialized_report
    assert "preflight-password-secret" not in serialized_report
    assert report.failure is not None
    assert report.failure["code"] == "llm_provider_preflight_failed"
    assert "Provider preflight URLs" in report.failure["message"]
    if "[broken" in base_url:
        assert report.base_url == "<redacted-url>"
        assert report.checks[0].details["url"] == "<redacted-url>"
    elif "preflight-user-secret" in base_url:
        assert report.base_url == "https://provider.example/v1"
        assert report.checks[0].details["url"] == "https://provider.example/health"


@pytest.mark.asyncio
async def test_default_provider_fetch_rejects_file_url_before_request_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("polisyos.scientist.orchestration.llm.provider_verification")
    request_calls: list[str] = []

    def forbidden_request(*_args: Any, **_kwargs: Any) -> object:
        request_calls.append("constructed")
        raise AssertionError("URL validation must happen before Request construction")

    monkeypatch.setattr(module, "Request", forbidden_request)

    with pytest.raises(ValueError, match="Provider preflight URLs"):
        await module._default_fetch_json(
            "file:///tmp/provider.json",
            headers={"Authorization": "Bearer sk-provider-preflight-test-key"},
        )

    assert request_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("scheme", ["http", "https"])
async def test_provider_preflight_default_transport_keeps_get_and_bearer_headers(
    monkeypatch: pytest.MonkeyPatch,
    scheme: str,
) -> None:
    module = importlib.import_module("polisyos.scientist.orchestration.llm.provider_verification")
    monkeypatch.delenv("POLISYOS_LLM_SIMULATION_MODE", raising=False)
    monkeypatch.setattr(module, "_PREFLIGHT_CACHE", {})
    observed: list[tuple[str, str, str | None]] = []
    api_key = "sk-provider-preflight-test-key"

    class _Response:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return self._payload

    def fake_urlopen(request: Any, *, timeout: float) -> _Response:
        del timeout
        observed.append(
            (
                request.full_url,
                request.get_method(),
                request.get_header("Authorization"),
            )
        )
        payload = b'{"data":[{"id":"model"}]}' if request.full_url.endswith("/v1/models") else b"{}"
        return _Response(payload)

    def fake_build_opener(redirect_handler: Any) -> Any:
        assert isinstance(redirect_handler, module._ProviderPreflightRedirectHandler)
        return SimpleNamespace(open=fake_urlopen)

    class _Client:
        async def generate(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(content='{"status":"ok"}', request_id="req-test")

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(module, "build_opener", fake_build_opener)
    report = await run_provider_preflight(
        models=["model"],
        base_url=f"{scheme}://provider.example/v1",
        api_key=api_key,
        client_factory=lambda **_kwargs: _Client(),
        ttl_s=0,
    )

    assert report.status == "ok"
    assert api_key not in report.model_dump_json()
    assert report.base_url == f"{scheme}://provider.example/v1"
    assert report.checks[0].details["url"] == f"{scheme}://provider.example/health"
    assert [url for url, _method, _authorization in observed] == [
        f"{scheme}://provider.example/health",
        f"{scheme}://provider.example/v1/models",
        f"{scheme}://provider.example/api/models/capabilities",
        f"{scheme}://provider.example/api/pricing",
    ]
    assert all(method == "GET" for _url, method, _authorization in observed)
    assert all(authorization == f"Bearer {api_key}" for _url, _method, authorization in observed)


@pytest.mark.asyncio
async def test_provider_preflight_redacts_nested_mapping_key_and_value_urls() -> None:
    module = importlib.import_module("polisyos.scientist.orchestration.llm.provider_verification")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.delenv("POLISYOS_LLM_SIMULATION_MODE", raising=False)
    monkeypatch.setattr(module, "_PREFLIGHT_CACHE", {})
    capability_payload = {
        "https://cap-user-one:cap-password-one@capabilities.example/v1?token=cap-query-one": {
            "nested": {
                "https://inner-user:inner-password@inner.example/endpoint?token=inner-query": (
                    "endpoint https://value-user:value-password@value.example/path"
                    "?token=value-query"
                )
            }
        },
        "https://cap-user-two:cap-password-two@capabilities.example/v1?token=cap-query-two": {
            "second": "retained",
        },
    }

    async def fetch_json(url: str, **_kwargs: Any) -> dict[str, Any]:
        if url.endswith("/models"):
            return {"data": [{"id": "model"}]}
        if url.endswith("/api/models/capabilities"):
            return capability_payload
        if url.endswith("/api/pricing"):
            return {
                "source": (
                    "pricing URL https://pricing-user:pricing-password@pricing.example/v1"
                    "?token=pricing-query"
                )
            }
        return {}

    class _Client:
        async def generate(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(content='{"status":"ok"}', request_id="req-test")

        async def aclose(self) -> None:
            return None

    try:
        report = await run_provider_preflight(
            models=["model"],
            base_url="https://provider.example/v1",
            api_key="sk-provider-preflight-test-key",
            fetch_json=fetch_json,
            client_factory=lambda **_kwargs: _Client(),
            ttl_s=0,
        )
    finally:
        monkeypatch.undo()

    serialized_report = report.model_dump_json()
    for secret in (
        "cap-user-one",
        "cap-password-one",
        "cap-query-one",
        "cap-user-two",
        "cap-password-two",
        "cap-query-two",
        "inner-user",
        "inner-password",
        "inner-query",
        "value-user",
        "value-password",
        "value-query",
        "pricing-user",
        "pricing-password",
        "pricing-query",
    ):
        assert secret not in serialized_report
    assert report.status == "ok"
    assert report.base_url == "https://provider.example/v1"
    assert report.checks[0].details["url"] == "https://provider.example/health"
    safe_capability_keys = list(report.capabilities)
    assert safe_capability_keys[0] == "https://capabilities.example/v1"
    assert safe_capability_keys[1].startswith("https://capabilities.example/v1#redacted-")
    assert report.capabilities[safe_capability_keys[1]] == {"second": "retained"}
    nested = report.capabilities[safe_capability_keys[0]]["nested"]
    assert nested["https://inner.example/endpoint"] == "endpoint https://value.example/path"
    assert report.pricing["source"] == "pricing URL https://pricing.example/v1"


def _isolate_loopback_preflight_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.delenv("POLISYOS_LLM_SIMULATION_MODE", raising=False)


@pytest.mark.asyncio
async def test_provider_preflight_does_not_forward_bearer_to_cross_origin_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json as json_module
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    _isolate_loopback_preflight_environment(monkeypatch)

    origin_authorizations: list[str | None] = []
    redirected_authorizations: list[str | None] = []

    class _TargetHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            redirected_authorizations.append(self.headers.get("Authorization"))
            payload = json_module.dumps({"data": [{"id": "model"}]}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format: str, *_args: object) -> None:
            return None

    target_server = ThreadingHTTPServer(("127.0.0.1", 0), _TargetHandler)
    target_thread = Thread(target=target_server.serve_forever, daemon=True)
    target_thread.start()
    target_url = f"http://127.0.0.1:{target_server.server_port}/redirected"

    class _OriginHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            origin_authorizations.append(self.headers.get("Authorization"))
            self.send_response(302 if self.path == "/health" else 200)
            if self.path == "/health":
                self.send_header("Location", target_url)
                payload = b""
            elif self.path == "/v1/models":
                payload = b'{"data":[{"id":"model"}]}'
            else:
                payload = b"{}"
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format: str, *_args: object) -> None:
            return None

    origin_server = ThreadingHTTPServer(("127.0.0.1", 0), _OriginHandler)
    origin_thread = Thread(target=origin_server.serve_forever, daemon=True)
    origin_thread.start()
    api_key = "sk-provider-preflight-test-key"

    class _Client:
        async def generate(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(content='{"status":"ok"}', request_id="req-test")

        async def aclose(self) -> None:
            return None

    try:
        report = await run_provider_preflight(
            models=["model"],
            base_url=f"http://127.0.0.1:{origin_server.server_port}/v1",
            api_key=api_key,
            client_factory=lambda **_kwargs: _Client(),
            ttl_s=0,
        )
    finally:
        origin_server.shutdown()
        origin_server.server_close()
        origin_thread.join(timeout=2)
        target_server.shutdown()
        target_server.server_close()
        target_thread.join(timeout=2)

    assert report.status == "failed"
    assert report.failure is not None
    assert origin_authorizations == [f"Bearer {api_key}"]
    assert redirected_authorizations == []
    assert "changed origin" in report.failure["message"]
    assert report.checks[0].status == "failed"
    assert report.checks[0].details["url"] == (
        f"http://127.0.0.1:{origin_server.server_port}/health"
    )


@pytest.mark.asyncio
async def test_provider_preflight_follows_same_origin_redirect_with_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json as json_module
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    _isolate_loopback_preflight_environment(monkeypatch)

    observed: list[tuple[str, str | None]] = []
    responses = {
        "/health-ready": {"status": "ok"},
        "/v1/models": {"data": [{"id": "model"}]},
        "/api/models/capabilities": {},
        "/api/pricing": {},
    }

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            observed.append((self.path, self.headers.get("Authorization")))
            if self.path == "/health":
                self.send_response(302)
                self.send_header(
                    "Location",
                    f"http://127.0.0.1:{self.server.server_port}/health-ready",
                )
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            payload = json_module.dumps(responses[self.path]).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format: str, *_args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    api_key = "sk-provider-preflight-test-key"

    class _Client:
        async def generate(self, **_kwargs: Any) -> Any:
            return SimpleNamespace(content='{"status":"ok"}', request_id="req-test")

        async def aclose(self) -> None:
            return None

    try:
        report = await run_provider_preflight(
            models=["model"],
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            api_key=api_key,
            client_factory=lambda **_kwargs: _Client(),
            ttl_s=0,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert report.status == "ok"
    assert report.failure is None
    assert report.checks[0].status == "ok"
    assert report.checks[0].details["url"] == (f"http://127.0.0.1:{server.server_port}/health")
    assert [path for path, _authorization in observed] == [
        "/health",
        "/health-ready",
        "/v1/models",
        "/api/models/capabilities",
        "/api/pricing",
    ]
    assert all(authorization == f"Bearer {api_key}" for _, authorization in observed)
    assert api_key not in report.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("usage", "expected_origin", "expected_amount_wire", "expected_status"),
    [
        (
            {"prompt_tokens": 2, "completion_tokens": 1, "cost_usd": 0.0},
            "reported",
            "0.0",
            "committed",
        ),
        (
            {"prompt_tokens": 2, "completion_tokens": 1},
            "estimated",
            "0.000015000000000000002",
            "committed",
        ),
        (None, "unknown", None, "unknown"),
    ],
)
async def test_provider_preflight_records_bound_gateway_completion_and_reuses_exact_event(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    usage: dict[str, Any] | None,
    expected_origin: str,
    expected_amount_wire: str | None,
    expected_status: str,
) -> None:
    import json as json_module
    from decimal import Decimal
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    from polisyos.core.llm.settlement import LLMProducerEvent
    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
        FileBudgetLedger,
    )
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    expected_amount = Decimal(expected_amount_wire) if expected_amount_wire is not None else None
    module = importlib.import_module("polisyos.scientist.orchestration.llm.provider_verification")
    gateway_module = importlib.import_module("polisyos.scientist.orchestration.llm.gateway_client")
    plans: list[Any] = []
    cache_clients: list[Any] = []
    gateway_preparations: list[tuple[Any, Any]] = []
    actual_prepare = module.prepare_cached_request
    actual_new_client = module._new_preflight_cached_client
    actual_gateway_prepare = gateway_module.GatewayLLMClient.prepare_cache_request

    def observe_prepare(*args: Any, **kwargs: Any) -> Any:
        request = actual_prepare(*args, **kwargs)
        plans.append(request)
        return request

    def observe_client(**kwargs: Any) -> Any:
        client = actual_new_client(**kwargs)
        cache_clients.append(client)
        return client

    def observe_gateway(client: Any, **kwargs: Any) -> Any:
        request = actual_gateway_prepare(client, **kwargs)
        gateway_preparations.append((client, request))
        return request

    monkeypatch.setattr(module, "prepare_cached_request", observe_prepare)
    monkeypatch.setattr(module, "_new_preflight_cached_client", observe_client)
    monkeypatch.setattr(gateway_module.GatewayLLMClient, "prepare_cache_request", observe_gateway)
    _isolate_loopback_preflight_environment(monkeypatch)
    monkeypatch.setattr(module, "_PREFLIGHT_CACHE", {})
    monkeypatch.setattr(module, "_PREFLIGHT_COMPLETION_CACHE", {})
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "300")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "128")
    observed: list[tuple[str, str | None]] = []
    completions: list[dict[str, Any]] = []
    api_key = "sk-provider-preflight-test-key"

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            observed.append((self.path, self.headers.get("Authorization")))
            if self.path == "/health":
                payload: dict[str, Any] = {"status": "ok"}
            elif self.path == "/v1/models":
                payload = {"data": [{"id": "gpt-4o"}]}
            elif self.path == "/api/models/capabilities":
                payload = {"models": [{"model": "gpt-4o"}]}
            elif self.path == "/api/pricing":
                payload = {"gpt-4o": {"source": "loopback fixture"}}
            else:
                self.send_error(404)
                return
            body = json_module.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            observed.append((self.path, self.headers.get("Authorization")))
            request_body = json_module.loads(self.rfile.read(int(self.headers["Content-Length"])))
            completions.append(request_body)
            payload: dict[str, Any] = {
                "model": "response-self-label-is-not-authority",
                "provider": "response-self-label-is-not-authority",
                "id": f"loopback-request-{len(completions)}",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": '{"status":"ok"}'},
                        "finish_reason": "stop",
                    }
                ],
            }
            if usage is not None:
                payload["usage"] = usage
            body = json_module.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("x-request-id", f"loopback-request-{len(completions)}")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    ledger_path = tmp_path / "preflight-ledger.json"
    store = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    binding = BudgetLedgerProducerRunBinding(
        run_id=f"preflight-{expected_origin}-run",
        tenant_id="tenant-fixture",
        cell_id="cell-fixture",
        profile_id="research",
        control_job_id=f"preflight-{expected_origin}-job",
    )
    base_url = f"http://127.0.0.1:{server.server_port}/v1"
    kwargs = {
        "models": ["gpt-4o"],
        "base_url": base_url,
        "provider": "configured-loopback-gateway",
        "api_key": api_key,
        "producer_settlement_store": store,
        "producer_run_binding": binding,
        "producer_budget_key": f"nl-run:{binding.run_id}",
        "require_producer_settlement": True,
        "ttl_s": 300,
    }
    try:
        report = await run_provider_preflight(**kwargs)
        cached_report = await run_provider_preflight(**kwargs)
        another_binding = binding.model_copy(
            update={
                "run_id": f"{binding.run_id}-other",
                "control_job_id": f"{binding.control_job_id}-other",
            }
        )
        other_report = await run_provider_preflight(
            **{
                **kwargs,
                "producer_run_binding": another_binding,
                "producer_budget_key": f"nl-run:{another_binding.run_id}",
            }
        )
        other_owner_store = BudgetMiddleware(
            BudgetState(),
            ledger=FileBudgetLedger(tmp_path / "other-owner-ledger.json"),
        )
        other_owner_report = await run_provider_preflight(
            **{**kwargs, "producer_settlement_store": other_owner_store}
        )
        alternate_provider_report = await run_provider_preflight(
            **{**kwargs, "provider": "configured-loopback-alias"}
        )
        valid_request_count = len(observed)
        cached_event_id = next(
            check.details["producer_event"]["event_id"]
            for check in cached_report.checks
            if check.name == "tiny_completion"
        )
        first_event_id = next(
            check.details["producer_event"]["event_id"]
            for check in report.checks
            if check.name == "tiny_completion"
        )
        original_ledger = ledger_path.read_bytes()
        try:
            ledger_payload = json_module.loads(original_ledger)
            ledger_payload["producer_settlements"][cached_event_id]["provider"] = "altered-provider"
            ledger_path.write_text(json_module.dumps(ledger_payload), encoding="utf-8")
            changed_event_report = await run_provider_preflight(**kwargs)
            assert changed_event_report.status == "unknown"
            assert len(observed) == valid_request_count
            assert len(completions) == 4

            ledger_payload = json_module.loads(original_ledger)
            del ledger_payload["producer_settlements"][first_event_id]
            ledger_path.write_text(json_module.dumps(ledger_payload), encoding="utf-8")
            missing_origin_report = await run_provider_preflight(**kwargs)
            assert missing_origin_report.status == "unknown"
            assert len(observed) == valid_request_count
            assert len(completions) == 4
        finally:
            ledger_path.write_bytes(original_ledger)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert report.status == "ok"
    assert cached_report.cache_hit is False
    assert other_report.status == "ok"
    assert other_owner_report.status == "ok"
    assert alternate_provider_report.status == "ok"
    assert other_owner_report.cache_hit is False
    assert alternate_provider_report.cache_hit is False
    first_tiny = next(check for check in report.checks if check.name == "tiny_completion")
    cached_tiny = next(check for check in cached_report.checks if check.name == "tiny_completion")
    other_tiny = next(check for check in other_report.checks if check.name == "tiny_completion")
    other_owner_tiny = next(
        check for check in other_owner_report.checks if check.name == "tiny_completion"
    )
    alternate_provider_tiny = next(
        check for check in alternate_provider_report.checks if check.name == "tiny_completion"
    )
    first_ref = first_tiny.details["producer_event"]
    # Every invocation prepares the actual gateway once. Successful calls use
    # fresh traced/cache wrappers, while only the exact same owner/request shares
    # a retained cache resource. The remaining plans are denied before any send.
    assert len(gateway_preparations) == len(plans)
    assert len({id(client) for client, _request in gateway_preparations}) == len(plans)
    assert len(cache_clients) == len({id(client) for client in cache_clients})
    assert cache_clients[0]._cache is cache_clients[1]._cache
    assert all(client._cache is not cache_clients[0]._cache for client in cache_clients[2:])
    successful_reports = (
        report,
        cached_report,
        other_report,
        other_owner_report,
        alternate_provider_report,
    )
    assert len(cache_clients) == len(successful_reports)
    for report_item, plan in zip(successful_reports, plans[: len(successful_reports)], strict=True):
        event_ref = next(check for check in report_item.checks if check.name == "tiny_completion")
        assert event_ref.details["producer_event"]["request_digest"] == plan.request_digest
    assert all(client._session is None for client, _request in gateway_preparations)
    cached_ref = cached_tiny.details["producer_event"]
    event_ids = {
        first_ref["event_id"],
        cached_ref["event_id"],
        other_tiny.details["producer_event"]["event_id"],
        other_owner_tiny.details["producer_event"]["event_id"],
        alternate_provider_tiny.details["producer_event"]["event_id"],
    }
    assert len(event_ids) == 5
    assert cached_ref["event_id"] != first_ref["event_id"]
    assert cached_ref["event_kind"] == "reuse"
    assert cached_ref["cost_origin"] == "reuse"
    assert cached_ref["amount"] == "0"
    assert cached_ref["settlement_status"] == "committed"
    assert cached_ref["origin_event_id"] == first_ref["event_id"]
    assert cached_ref["origin_event_reference"]["event_id"] == first_ref["event_id"]
    assert alternate_provider_tiny.details["producer_event"]["provider"] == (
        "configured-loopback-alias"
    )
    assert first_ref["model"] == "gpt-4o"
    assert first_ref["provider"] == "configured-loopback-gateway"
    assert first_ref["cost_origin"] == expected_origin
    assert first_ref["amount"] == expected_amount_wire
    if expected_origin == "estimated":
        assert first_ref["cost_usd"] == pytest.approx(float(expected_amount), rel=1e-15, abs=0.0)
    elif expected_amount is None:
        assert first_ref["cost_usd"] is None
    else:
        assert first_ref["cost_usd"] == float(expected_amount)
    assert first_ref["settlement_status"] == expected_status
    assert first_ref["durability"] == "ledger"
    assert first_ref["receipts"] == (
        [first_ref["event_id"]] if expected_status == "committed" else []
    )
    assert len(completions) == 4
    assert [path for path, _authorization in observed].count("/v1/chat/completions") == 4
    assert all(authorization == f"Bearer {api_key}" for _, authorization in observed)
    assert all(item["model"] == "gpt-4o" for item in completions)

    reopened = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    first_records = reopened.list_producer_events_for_run_safe(binding)
    other_records = reopened.list_producer_events_for_run_safe(another_binding)
    assert len(first_records) == 3
    assert len(other_records) == 1
    first_record = next(
        record for record in first_records if record.event_id == first_ref["event_id"]
    )
    ledger_wire = json_module.loads(ledger_path.read_bytes())
    stored_event = ledger_wire["producer_settlements"][first_ref["event_id"]]
    if expected_amount_wire is None:
        assert "amount" not in stored_event
    else:
        assert stored_event["amount"] == expected_amount_wire
    assert stored_event["payload_digest"] == first_ref["payload_digest"]
    recomputed_event = LLMProducerEvent(
        event_id=first_ref["event_id"],
        request_digest=first_ref["request_digest"],
        response_digest=first_ref["response_digest"],
        model=first_ref["model"],
        provider=first_ref["provider"],
        amount=expected_amount,
        cost_origin=expected_origin,
    )
    assert recomputed_event.payload_digest == first_ref["payload_digest"]
    assert first_record.payload_digest == recomputed_event.payload_digest
    other_record = other_records[0]
    alternate_provider_record = next(
        record
        for record in first_records
        if record.event_id == alternate_provider_tiny.details["producer_event"]["event_id"]
    )
    assert alternate_provider_record.provider == "configured-loopback-alias"
    owner_two_reopened = BudgetMiddleware(
        BudgetState(),
        ledger=FileBudgetLedger(tmp_path / "other-owner-ledger.json"),
    )
    owner_two_records = owner_two_reopened.list_producer_events_for_run_safe(binding)
    assert len(owner_two_records) == 1
    assert owner_two_records[0].event_id == other_owner_tiny.details["producer_event"]["event_id"]
    assert first_record.event_id == first_ref["event_id"]
    reuse_record = next(
        record for record in first_records if record.event_id == cached_ref["event_id"]
    )
    assert reuse_record.cost_origin == "reuse"
    assert reuse_record.amount == Decimal(0)
    assert reuse_record.origin_event_id == first_ref["event_id"]
    assert reuse_record.run_binding == binding
    assert first_record.key == f"nl-run:{binding.run_id}"
    assert first_record.run_binding == binding
    assert first_record.model == "gpt-4o"
    assert first_record.provider == "configured-loopback-gateway"
    assert first_record.cost_origin == expected_origin
    assert first_record.amount == expected_amount
    assert first_record.status == expected_status
    assert other_record.event_id == other_tiny.details["producer_event"]["event_id"]
    assert other_record.run_binding == another_binding
    assert len(FileBudgetLedger(ledger_path).snapshot().producer_settlements) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ledger_configured", "producer_budget_key", "expected_failure_message"),
    [
        (
            False,
            "nl-run:preflight-unavailable-run",
            "durable producer settlement is unavailable",
        ),
        (True, "nl-run:other-run", "budget key does not match its run"),
    ],
)
async def test_provider_preflight_required_accounting_refuses_before_provider_io(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    ledger_configured: bool,
    producer_budget_key: str,
    expected_failure_message: str,
) -> None:
    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
        FileBudgetLedger,
    )
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    module = importlib.import_module("polisyos.scientist.orchestration.llm.provider_verification")
    monkeypatch.delenv("POLISYOS_LLM_SIMULATION_MODE", raising=False)
    monkeypatch.setattr(module, "_PREFLIGHT_CACHE", {})
    fetch_calls: list[str] = []
    client_calls: list[str] = []
    store = (
        BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(tmp_path / "ledger.json"))
        if ledger_configured
        else BudgetMiddleware(BudgetState())
    )
    binding = BudgetLedgerProducerRunBinding(
        run_id="preflight-unavailable-run",
        tenant_id="tenant-fixture",
        cell_id="cell-fixture",
        profile_id="research",
        control_job_id="preflight-unavailable-job",
    )

    async def _fetch_json(url: str, **_kwargs: Any) -> dict[str, Any]:
        fetch_calls.append(url)
        return {"data": [{"id": "model-a"}]}

    def _client_factory(**_kwargs: Any) -> object:
        client_calls.append("constructed")
        raise AssertionError("provider client must not be constructed")

    report = await run_provider_preflight(
        models=["model-a"],
        base_url="http://127.0.0.1:1/v1",
        provider="configured-gateway",
        api_key="sk-provider-preflight-test-key",
        producer_settlement_store=store,
        producer_run_binding=binding,
        producer_budget_key=producer_budget_key,
        require_producer_settlement=True,
        fetch_json=_fetch_json,
        client_factory=_client_factory,
    )

    assert report.status == "failed"
    assert report.failure is not None
    assert expected_failure_message in report.failure["message"]
    assert fetch_calls == []
    assert client_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "expected_fetches"),
    [
        ("simulation", 0),
        ("missing_key", 0),
        ("health", 1),
        ("models", 2),
        ("pricing", 4),
        ("model_absent", 4),
    ],
)
async def test_preflight_attests_known_no_completion_before_provider_generation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    scenario: str,
    expected_fetches: int,
) -> None:
    """Every documented early preflight refusal proves generation was never entered."""
    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
        FileBudgetLedger,
    )
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    module = importlib.import_module("polisyos.scientist.orchestration.llm.provider_verification")
    monkeypatch.setattr(module, "_PREFLIGHT_CACHE", {})
    if scenario == "simulation":
        monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "true")
    else:
        monkeypatch.delenv("POLISYOS_LLM_SIMULATION_MODE", raising=False)
    if scenario == "missing_key":
        monkeypatch.delenv("POLISYOS_LLM_GATEWAY_API_KEY", raising=False)
    fetch_calls: list[str] = []
    client_calls: list[str] = []
    store = BudgetMiddleware(
        BudgetState(), ledger=FileBudgetLedger(tmp_path / f"{scenario}-ledger.json")
    )
    binding = BudgetLedgerProducerRunBinding(
        run_id=f"preflight-{scenario}-run",
        tenant_id="tenant-fixture",
        cell_id="cell-fixture",
        profile_id="research",
        control_job_id=f"preflight-{scenario}-job",
    )

    async def fetch_json(url: str, **_kwargs: Any) -> dict[str, Any]:
        fetch_calls.append(url)
        leaf = url.rsplit("/", 1)[-1]
        if scenario == "health" and leaf == "health":
            raise OSError("configured health endpoint unavailable")
        if scenario == "models" and leaf == "models":
            raise OSError("configured model endpoint unavailable")
        if scenario == "pricing" and leaf == "pricing":
            raise OSError("configured pricing endpoint unavailable")
        model_id = "different-model" if scenario == "model_absent" else "model-a"
        if leaf == "models":
            return {"data": [{"id": model_id}]}
        return {}

    def client_factory(**_kwargs: Any) -> object:
        client_calls.append("constructed")
        raise AssertionError("a known pre-completion refusal constructed an LLM client")

    report = await run_provider_preflight(
        models=["model-a"],
        base_url="http://127.0.0.1:1/v1",
        provider="configured-gateway",
        api_key=None if scenario == "missing_key" else "sk-provider-preflight-test-key",
        producer_settlement_store=store,
        producer_run_binding=binding,
        producer_budget_key=f"nl-run:{binding.run_id}",
        require_producer_settlement=True,
        fetch_json=fetch_json,
        client_factory=client_factory,
    )

    assert report.status in {"failed", "skipped"}
    assert report.producer_completion_observation == "not_started"
    assert len(fetch_calls) == expected_fetches
    assert client_calls == []


def test_unclassified_preflight_report_does_not_default_to_no_call() -> None:
    """A missing producer observation remains unavailable, never an absence claim."""
    report = ProviderPreflightReport(
        status="failed",
        provider="configured-gateway",
        base_url="https://gateway.example/v1",
    )

    assert report.producer_completion_observation == "unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ledger_settlement_fails", "expected_status"),
    [(False, "failed"), (True, "unknown")],
)
async def test_provider_preflight_gateway_exception_preserves_unknown_settlement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    ledger_settlement_fails: bool,
    expected_status: str,
) -> None:
    import json as json_module
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
        FileBudgetLedger,
    )
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    _isolate_loopback_preflight_environment(monkeypatch)
    monkeypatch.setattr(
        importlib.import_module("polisyos.scientist.orchestration.llm.provider_verification"),
        "_PREFLIGHT_CACHE",
        {},
    )
    observed: list[tuple[str, str | None]] = []

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            observed.append((self.path, self.headers.get("Authorization")))
            if self.path == "/health":
                payload: dict[str, Any] = {"status": "ok"}
            elif self.path == "/v1/models":
                payload = {"data": [{"id": "gpt-4o"}]}
            elif self.path == "/api/models/capabilities":
                payload = {"models": [{"model": "gpt-4o"}]}
            elif self.path == "/api/pricing":
                payload = {"gpt-4o": {"source": "loopback fixture"}}
            else:
                self.send_error(404)
                return
            body = json_module.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            observed.append((self.path, self.headers.get("Authorization")))
            self.rfile.read(int(self.headers["Content-Length"]))
            body = json_module.dumps(
                {"error": {"message": "controlled loopback provider exception"}}
            ).encode("utf-8")
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    ledger_path = tmp_path / "preflight-exception-ledger.json"
    store = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    binding = BudgetLedgerProducerRunBinding(
        run_id=f"preflight-exception-{ledger_settlement_fails}",
        tenant_id="tenant-fixture",
        cell_id="cell-fixture",
        profile_id="research",
        control_job_id=f"preflight-exception-job-{ledger_settlement_fails}",
    )
    api_key = "sk-provider-preflight-test-key"
    base_url = f"http://127.0.0.1:{server.server_port}/v1"
    if ledger_settlement_fails:

        def _fail_settlement(*_args: object, **_kwargs: object) -> object:
            raise OSError("controlled ledger append failure")

        monkeypatch.setattr(store, "settle_producer_event_safe", _fail_settlement)

    try:
        report = await run_provider_preflight(
            models=["gpt-4o"],
            base_url=base_url,
            provider="configured-loopback-gateway",
            api_key=api_key,
            producer_settlement_store=store,
            producer_run_binding=binding,
            producer_budget_key=f"nl-run:{binding.run_id}",
            require_producer_settlement=True,
            ttl_s=300,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert len(observed) == 5
    assert [path for path, _authorization in observed[:4]] == [
        "/health",
        "/v1/models",
        "/api/models/capabilities",
        "/api/pricing",
    ]
    assert observed[4][0].endswith("/chat/completions")
    assert all(authorization == f"Bearer {api_key}" for _, authorization in observed)
    tiny = next(check for check in report.checks if check.name == "tiny_completion")

    assert report.status == expected_status
    if ledger_settlement_fails:
        assert tiny.status == "unknown"
        assert report.producer_completion_observation == "unavailable"
        assert report.failure is not None
        assert report.failure["code"] == "llm_provider_preflight_settlement_unknown"
        assert "producer_event" not in tiny.details
        records = store.list_producer_events_for_run_safe(binding)
        assert len(records) == 1
        assert records[0].status == "pending"
        assert records[0].payload_digest is None
        assert records[0].run_binding == binding
    else:
        assert tiny.status == "failed"
        assert report.producer_completion_observation == "complete"
        event_reference = tiny.details["producer_event"]
        assert event_reference["event_kind"] == "provider"
        assert event_reference["cost_origin"] == "unknown"
        assert event_reference["settlement_status"] == "unknown"
        assert event_reference["durability"] == "ledger"
        assert event_reference["run_binding"] == binding.model_dump(mode="json")
        records = store.list_producer_events_for_run_safe(binding)
        assert len(records) == 1
        assert records[0].status == "unknown"
        assert records[0].run_binding == binding


@pytest.fixture
async def prepared_preflight_gateway(monkeypatch, tmp_path):
    """Use actual catalog/completion HTTP and ledger owners for bridge controls."""
    from aiohttp import web

    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
        FileBudgetLedger,
    )
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    module = importlib.import_module("polisyos.scientist.orchestration.llm.provider_verification")
    _isolate_loopback_preflight_environment(monkeypatch)
    monkeypatch.setattr(module, "_PREFLIGHT_CACHE", {})
    monkeypatch.setattr(module, "_PREFLIGHT_COMPLETION_CACHE", {})
    monkeypatch.setenv("POLISYOS_LLM_CACHE_TTL_S", "300")
    monkeypatch.setenv("POLISYOS_LLM_CACHE_MAXSIZE", "128")
    state: dict[str, Any] = {
        "reject_format": False,
        "wait_for_response": False,
        "bodies": [],
        "gateways": [],
        "entered": asyncio.Event(),
        "release": asyncio.Event(),
    }
    actual_prepare = module.GatewayLLMClient.prepare_cache_request

    def observe_gateway(client: Any, **kwargs: Any) -> Any:
        state["gateways"].append(client)
        return actual_prepare(client, **kwargs)

    monkeypatch.setattr(module.GatewayLLMClient, "prepare_cache_request", observe_gateway)

    async def catalog(request: web.Request) -> web.Response:
        assert request.headers.get("Authorization") == "Bearer sk-preflight-prepared-local-key"
        if request.path == "/v1/models":
            return web.json_response({"data": [{"id": "gpt-4o"}]})
        return web.json_response({"status": "ok"})

    async def completion(request: web.Request) -> web.Response:
        assert request.headers.get("Authorization") == "Bearer sk-preflight-prepared-local-key"
        body = await request.json()
        state["bodies"].append(body)
        if "response_format" in body and state["reject_format"]:
            return web.json_response(
                {"error": {"message": "response_format json_object unavailable"}}, status=400
            )
        state["entered"].set()
        if state["wait_for_response"]:
            await state["release"].wait()
        return web.json_response(
            {
                "model": "gpt-4o",
                "id": f"prepared-{len(state['bodies'])}",
                "choices": [{"message": {"content": '{"status":"ok"}'}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1, "cost_usd": 0.001},
            }
        )

    app = web.Application()
    app.router.add_get("/{tail:.*}", catalog)
    app.router.add_post("/v1/chat/completions", completion)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    assert site._server is not None
    port = site._server.sockets[0].getsockname()[1]
    ledger_path = tmp_path / "prepared-preflight.json"
    store = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
    binding = BudgetLedgerProducerRunBinding(
        run_id="prepared-run",
        tenant_id="tenant-a",
        cell_id="cell-a",
        profile_id="research",
        control_job_id="prepared-job",
    )
    kwargs = {
        "models": ["gpt-4o"],
        "base_url": f"http://127.0.0.1:{port}/v1",
        "provider": "prepared-local-gateway",
        "api_key": "sk-preflight-prepared-local-key",
        "producer_settlement_store": store,
        "producer_run_binding": binding,
        "producer_budget_key": "nl-run:prepared-run",
        "require_producer_settlement": True,
        "pre_admission_attempt_id": "a" * 32,
    }
    try:
        yield module, kwargs, state, ledger_path, binding
    finally:
        state["release"].set()
        await runner.cleanup()


def _prepared_preflight_event(report: Any) -> dict[str, Any]:
    assert report.status == "ok"
    return next(check for check in report.checks if check.name == "tiny_completion").details[
        "producer_event"
    ]


@pytest.mark.asyncio
async def test_preflight_uses_its_exact_prepared_request_across_catalog_waits(
    monkeypatch,
    prepared_preflight_gateway,
) -> None:
    module, kwargs, state, ledger_path, binding = prepared_preflight_gateway
    actual_request = module._preflight_completion_request_kwargs()
    actual_request["metadata"] = {"cache_buster": "A", "nested": {"policy_at": "A"}}
    monkeypatch.setattr(module, "_preflight_completion_request_kwargs", lambda: actual_request)
    fetch = module._default_fetch_json
    changed = False

    async def change_after_health(url: str, **options: Any) -> Any:
        nonlocal changed
        result = await fetch(url, **options)
        if url.endswith("/health") and not changed:
            actual_request["metadata"]["cache_buster"] = "B"
            actual_request["metadata"]["nested"]["policy_at"] = "B"
            changed = True
        return result

    first = await run_provider_preflight(**kwargs, fetch_json=change_after_health)
    second = await run_provider_preflight(**kwargs)
    third = await run_provider_preflight(**kwargs)
    different_transport = await run_provider_preflight(**kwargs, timeout_s=11)
    rows = [
        _prepared_preflight_event(report) for report in (first, second, third, different_transport)
    ]
    assert [row["event_kind"] for row in rows] == ["provider", "provider", "reuse", "provider"]
    assert len(state["bodies"]) == 3
    assert state["bodies"][0]["metadata"] == {"cache_buster": "A", "nested": {"policy_at": "A"}}
    assert all(
        body["metadata"] == {"cache_buster": "B", "nested": {"policy_at": "B"}}
        for body in state["bodies"][1:]
    )
    assert rows[0]["request_digest"] != rows[1]["request_digest"]
    assert rows[1]["request_digest"] == rows[2]["request_digest"]
    assert rows[3]["request_digest"] != rows[2]["request_digest"]
    assert rows[2]["origin_event_id"] == rows[1]["event_id"]
    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger

    persisted = FileBudgetLedger(ledger_path).list_producer_events_for_run(binding)
    assert {row.event_id for row in persisted} == {row["event_id"] for row in rows}
    assert all(
        row.run_binding == binding and row.pre_admission_attempt_id == "a" * 32 for row in persisted
    )
    assert all(client._session is None for client in state["gateways"])


@pytest.mark.asyncio
async def test_preflight_negotiated_success_cannot_supply_requested_format_reuse(
    prepared_preflight_gateway,
) -> None:
    _module, kwargs, state, _ledger_path, _binding = prepared_preflight_gateway
    state["reject_format"] = True
    first = await run_provider_preflight(**kwargs)
    state["reject_format"] = False
    second = await run_provider_preflight(**kwargs)
    third = await run_provider_preflight(**kwargs)
    rows = [_prepared_preflight_event(report) for report in (first, second, third)]
    assert [row["event_kind"] for row in rows] == ["provider", "provider", "reuse"]
    assert rows[2]["origin_event_id"] == rows[1]["event_id"]
    assert rows[2]["origin_event_id"] != rows[0]["event_id"]
    assert ["response_format" in body for body in state["bodies"]] == [True, False, True]
    assert all(client._session is None for client in state["gateways"])


@pytest.mark.asyncio
async def test_cancelled_preflight_waiter_preserves_admitted_gateway_settlement_and_close(
    prepared_preflight_gateway,
) -> None:
    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger

    _module, kwargs, state, ledger_path, binding = prepared_preflight_gateway
    state["wait_for_response"] = True
    pending = asyncio.create_task(run_provider_preflight(**kwargs))
    try:
        await asyncio.wait_for(state["entered"].wait(), timeout=3)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        records = FileBudgetLedger(ledger_path).list_producer_events_for_run(binding)
        assert len(records) == 1 and records[0].status == "pending"
        assert records[0].pre_admission_attempt_id == "a" * 32
        assert any(
            client._session is not None and not client._session.closed
            for client in state["gateways"]
        )
    finally:
        state["release"].set()
        if not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)

    async def settled_and_closed() -> Any:
        while True:
            records = FileBudgetLedger(ledger_path).list_producer_events_for_run(binding)
            if (
                records
                and records[0].status == "committed"
                and all(client._session is None for client in state["gateways"])
            ):
                return records[0]
            await asyncio.sleep(0.01)

    final = await asyncio.wait_for(settled_and_closed(), timeout=3)
    assert final.event_id == records[0].event_id
    assert final.run_binding == binding and final.pre_admission_attempt_id == "a" * 32
    assert final.cost_origin == "reported" and final.amount is not None
    assert len(state["bodies"]) == 1
