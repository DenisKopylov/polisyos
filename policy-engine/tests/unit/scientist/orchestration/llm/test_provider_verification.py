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
    nested = report.capabilities[safe_capability_keys[0]]["nested"]
    assert nested["https://inner.example/endpoint"] == "endpoint https://value.example/path"
    assert report.pricing["source"] == "pricing URL https://pricing.example/v1"


@pytest.mark.asyncio
async def test_provider_preflight_does_not_forward_bearer_to_cross_origin_redirect() -> None:
    import json as json_module
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

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
