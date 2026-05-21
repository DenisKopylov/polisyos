"""Provider capability verification artifacts and live smoke helpers."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from polisyos.common.logger import get_logger
from polisyos.scholar.search.service import ScholarDeepSearchService
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient

logger = get_logger(__name__)

_DEFAULT_VERIFICATION_DIR = Path(".polisyos/provider_verification")
_GONKA_SMOKE_LOCK = asyncio.Lock()
_MAX_VERIFICATION_REQUEST_IDS = 64
_MAX_VERIFICATION_NOTES = 64
_PROVIDER_VERIFICATION_LOAD_ERRORS = (
    OSError,
    TypeError,
    ValidationError,
    ValueError,
    json.JSONDecodeError,
)
_PROVIDER_VERIFICATION_CHECK_ERRORS = (
    asyncio.TimeoutError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_PROVIDER_VERIFICATION_PARSE_ERRORS = (
    TypeError,
    ValueError,
    json.JSONDecodeError,
)

__all__ = [
    "ProviderCapabilityVerification",
    "ProviderPreflightCheck",
    "ProviderPreflightReport",
    "ProviderSmokeCheck",
    "ProviderSmokeReport",
    "is_provider_capability_verified",
    "load_provider_verification",
    "provider_verification_path",
    "resolve_gonka_api_key",
    "run_gonka_provider_smoke",
    "run_provider_preflight",
    "save_provider_verification",
]


class ProviderCapabilityVerification(BaseModel):
    """Persistent provider/model verification artifact."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    model_id: str
    base_url: str
    tool_calling_verified: bool = False
    response_healing_verified: bool = False
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request_ids: list[str] = Field(default_factory=list)
    available_model_ids: list[str] = Field(default_factory=list)
    source_api_key_env: str | None = None
    verification_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _bound_retained_lists(self) -> ProviderCapabilityVerification:
        request_ids = [item for item in self.request_ids if isinstance(item, str) and item.strip()]
        verification_notes = [
            item for item in self.verification_notes if isinstance(item, str) and item.strip()
        ]
        self.request_ids = list(dict.fromkeys(request_ids))[-_MAX_VERIFICATION_REQUEST_IDS:]
        self.verification_notes = verification_notes[-_MAX_VERIFICATION_NOTES:]
        return self


class ProviderSmokeCheck(BaseModel):
    """One smoke-check result included in the report."""

    model_config = ConfigDict(extra="forbid")

    name: str
    passed: bool = False
    request_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ProviderSmokeReport(BaseModel):
    """Machine-readable result of a live provider smoke run."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    model_id: str
    base_url: str
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    verification: ProviderCapabilityVerification
    checks: list[ProviderSmokeCheck] = Field(default_factory=list)


class ProviderPreflightCheck(BaseModel):
    """One runtime-gate check against the real LLM provider."""

    model_config = ConfigDict(extra="forbid")

    name: str
    status: str
    latency_ms: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ProviderPreflightReport(BaseModel):
    """Additive runtime preflight report persisted with canary/control evidence."""

    model_config = ConfigDict(extra="forbid")

    status: str
    provider: str
    base_url: str
    models: list[str] = Field(default_factory=list)
    checks: list[ProviderPreflightCheck] = Field(default_factory=list)
    pricing: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    retryable: bool = False
    failure: dict[str, Any] | None = None
    cache_hit: bool = False
    api_key_env: str | None = None
    api_key_fingerprint: str | None = None


_PREFLIGHT_CACHE: dict[tuple[str, tuple[str, ...], str], tuple[float, ProviderPreflightReport]] = {}


def provider_verification_path(
    *,
    provider: str,
    model_id: str,
    base_dir: str | Path | None = None,
) -> Path:
    root = Path(
        base_dir or os.getenv("POLISYOS_PROVIDER_VERIFICATION_DIR") or _DEFAULT_VERIFICATION_DIR
    )
    safe_provider = _safe_slug(provider)
    safe_model = _safe_slug(model_id)
    return root / f"{safe_provider}__{safe_model}.json"


def load_provider_verification(
    *,
    provider: str,
    model_id: str,
    base_dir: str | Path | None = None,
) -> ProviderCapabilityVerification | None:
    path = provider_verification_path(
        provider=provider,
        model_id=model_id,
        base_dir=base_dir,
    )
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ProviderCapabilityVerification.model_validate(payload)
    except _PROVIDER_VERIFICATION_LOAD_ERRORS as exc:
        emit_degraded_path(
            component="scientist.llm.provider_verification",
            operation="load_provider_verification",
            reason="verification_artifact_load_failed",
            exc=exc,
            details={"path": str(path), "provider": provider, "model_id": model_id},
            log=logger,
        )
        return None


def save_provider_verification(
    verification: ProviderCapabilityVerification,
    *,
    base_dir: str | Path | None = None,
) -> Path:
    path = provider_verification_path(
        provider=verification.provider,
        model_id=verification.model_id,
        base_dir=base_dir,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        verification.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )
    return path


def is_provider_capability_verified(
    *,
    provider: str,
    model_id: str,
    capability: str,
    base_dir: str | Path | None = None,
    max_age_days: int = 14,
) -> bool:
    verification = load_provider_verification(
        provider=provider,
        model_id=model_id,
        base_dir=base_dir,
    )
    if verification is None:
        return False
    freshness_cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    if verification.checked_at < freshness_cutoff:
        return False
    capability_key = f"{capability.strip().lower().replace('-', '_')}_verified"
    return bool(getattr(verification, capability_key, False))


def resolve_gonka_api_key() -> tuple[str | None, str | None]:
    """Resolve a Gonka smoke-test key without exposing secret values."""
    canonical_env = "POLISYOS_LLM_GATEWAY_API_KEY"
    canonical_value = os.getenv(canonical_env)
    if isinstance(canonical_value, str) and _looks_like_proxy_key(canonical_value):
        return canonical_value.strip(), canonical_env

    legacy_env = "GONKA_API_KEY_3"
    legacy_value = os.getenv(legacy_env)
    if isinstance(legacy_value, str) and legacy_value.strip():
        return legacy_value.strip(), legacy_env
    return None, None


def _secret_fingerprint(value: str | None) -> str | None:
    if not value:
        return None
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _looks_like_proxy_key(value: str) -> bool:
    key = value.strip()
    return key.startswith("sk-") and len(key) >= 16 and not any(char.isspace() for char in key)


def _provider_root_url(base_url: str) -> str:
    parts = urlsplit(base_url.rstrip("/"))
    path = parts.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3].rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _extract_model_ids(payload: Mapping[str, Any] | dict[str, Any]) -> list[str]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        data = payload.get("models") if isinstance(payload, dict) else None
    ids: list[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str) and item.strip():
                ids.append(item.strip())
            elif isinstance(item, dict):
                model_id = item.get("id") or item.get("model") or item.get("model_id")
                if isinstance(model_id, str) and model_id.strip():
                    ids.append(model_id.strip())
    return list(dict.fromkeys(ids))


def _preflight_failure_payload(
    *,
    message: str,
    provider: str,
    model: str | None,
    retryable: bool,
) -> dict[str, Any]:
    return {
        "code": "llm_provider_preflight_failed",
        "layer": "llm_gateway",
        "phase": "provider_preflight",
        "message": message,
        "retryable": retryable,
        "model": model,
        "provider": provider,
        "next_action": (
            "Retry after provider recovery or check gateway credentials, base URL, "
            "model id, and provider status."
            if retryable
            else "Check POLISYOS_LLM_GATEWAY_API_KEY, provider base URL, and configured model id."
        ),
    }


def _is_retryable_preflight_error(error: BaseException | str) -> bool:
    text = str(error).lower()
    return any(
        marker in text
        for marker in (
            "timeout",
            "timed out",
            "temporarily",
            "unavailable",
            "connection reset",
            "connection refused",
            "too many requests",
            "429",
            "500",
            "502",
            "503",
            "504",
        )
    )


async def _default_fetch_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout_s: float = 10.0,
) -> dict[str, Any]:
    def _fetch() -> dict[str, Any]:
        request = Request(url, headers=headers or {}, method="GET")
        with urlopen(request, timeout=timeout_s) as response:
            payload = response.read()
        parsed = json.loads(payload.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise RuntimeError(f"{url} returned non-object JSON")
        return parsed

    return await asyncio.to_thread(_fetch)


async def run_provider_preflight(
    *,
    models: list[str],
    base_url: str | None = None,
    provider: str | None = None,
    api_key: str | None = None,
    api_key_env: str | None = None,
    timeout_s: float = 10.0,
    ttl_s: int = 300,
    fetch_json: Any | None = None,
    client_factory: Any = GatewayLLMClient,
) -> ProviderPreflightReport:
    """Run a short real-provider gate before expensive NL workflows."""
    resolved_provider = (
        provider or os.getenv("POLISYOS_LLM_GATEWAY_PROVIDER") or "gateway"
    ).strip()
    resolved_base_url = (
        base_url or os.getenv("POLISYOS_LLM_GATEWAY_BASE_URL") or "https://proxy.gonka.gg/v1"
    ).strip().rstrip("/")
    requested_models = [item.strip() for item in models if isinstance(item, str) and item.strip()]
    checked_at = datetime.now(UTC)
    if not requested_models:
        failure = _preflight_failure_payload(
            message="No real LLM model id was configured for provider preflight.",
            provider=resolved_provider,
            model=None,
            retryable=False,
        )
        return ProviderPreflightReport(
            status="failed",
            provider=resolved_provider,
            base_url=resolved_base_url,
            models=[],
            checked_at=checked_at,
            retryable=False,
            failure=failure,
        )
    if os.getenv("POLISYOS_LLM_SIMULATION_MODE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return ProviderPreflightReport(
            status="skipped",
            provider=resolved_provider,
            base_url=resolved_base_url,
            models=requested_models,
            checks=[
                ProviderPreflightCheck(
                    name="simulation_mode",
                    status="skipped",
                    details={"reason": "POLISYOS_LLM_SIMULATION_MODE is enabled"},
                )
            ],
            checked_at=checked_at,
        )

    resolved_env = api_key_env or "POLISYOS_LLM_GATEWAY_API_KEY"
    resolved_api_key = api_key if api_key is not None else os.getenv(resolved_env)
    api_key_fingerprint = _secret_fingerprint(resolved_api_key)
    if not isinstance(resolved_api_key, str) or not _looks_like_proxy_key(resolved_api_key):
        failure = _preflight_failure_payload(
            message=(
                f"{resolved_env} is missing or does not look like an OpenAI-compatible "
                "provider key."
            ),
            provider=resolved_provider,
            model=requested_models[0] if requested_models else None,
            retryable=False,
        )
        return ProviderPreflightReport(
            status="failed",
            provider=resolved_provider,
            base_url=resolved_base_url,
            models=requested_models,
            checked_at=checked_at,
            retryable=False,
            failure=failure,
            api_key_env=resolved_env,
            api_key_fingerprint=api_key_fingerprint,
        )

    cache_key = (
        resolved_base_url,
        tuple(requested_models),
        api_key_fingerprint or "",
    )
    cached = _PREFLIGHT_CACHE.get(cache_key)
    now_monotonic = time.monotonic()
    if cached is not None and now_monotonic - cached[0] <= max(0, ttl_s):
        return cached[1].model_copy(update={"cache_hit": True})

    fetch = fetch_json or _default_fetch_json
    root_url = _provider_root_url(resolved_base_url)
    headers = {"Authorization": f"Bearer {resolved_api_key}"}
    checks: list[ProviderPreflightCheck] = []
    pricing: dict[str, Any] = {}
    capabilities: dict[str, Any] = {}

    async def _run_json_check(name: str, url: str) -> dict[str, Any] | None:
        started = time.perf_counter()
        try:
            payload = await fetch(url, headers=headers, timeout_s=timeout_s)
            if not isinstance(payload, dict):
                raise RuntimeError(f"{name} returned non-object JSON")
            checks.append(
                ProviderPreflightCheck(
                    name=name,
                    status="ok",
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    details={"url": url},
                )
            )
            return payload
        except Exception as exc:
            checks.append(
                ProviderPreflightCheck(
                    name=name,
                    status="failed",
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    details={"url": url},
                    error=str(exc),
                )
            )
            retryable = _is_retryable_preflight_error(exc)
            failure = _preflight_failure_payload(
                message=f"{name} check failed: {exc}",
                provider=resolved_provider,
                model=requested_models[0] if requested_models else None,
                retryable=retryable,
            )
            raise RuntimeError(json.dumps({"failure": failure, "retryable": retryable})) from exc

    try:
        await _run_json_check("health", _join_url(root_url, "/health"))
        models_payload = await _run_json_check("models", _join_url(resolved_base_url, "/models"))
        capabilities = await _run_json_check(
            "capabilities",
            _join_url(root_url, "/api/models/capabilities"),
        ) or {}
        pricing = await _run_json_check("pricing", _join_url(root_url, "/api/pricing")) or {}
    except RuntimeError as exc:
        try:
            failure_payload = json.loads(str(exc)).get("failure")
        except (TypeError, ValueError, json.JSONDecodeError):
            retryable = _is_retryable_preflight_error(exc)
            failure_payload = _preflight_failure_payload(
                message=str(exc),
                provider=resolved_provider,
                model=requested_models[0] if requested_models else None,
                retryable=retryable,
            )
        return ProviderPreflightReport(
            status="failed",
            provider=resolved_provider,
            base_url=resolved_base_url,
            models=requested_models,
            checks=checks,
            pricing=pricing,
            capabilities=capabilities,
            checked_at=checked_at,
            retryable=bool(failure_payload.get("retryable")),
            failure=failure_payload,
            api_key_env=resolved_env,
            api_key_fingerprint=api_key_fingerprint,
        )

    available_model_ids = _extract_model_ids(models_payload or {})
    missing_models = [item for item in requested_models if item not in set(available_model_ids)]
    if missing_models:
        model = missing_models[0]
        failure = _preflight_failure_payload(
            message=f"model_id '{model}' not returned by /v1/models",
            provider=resolved_provider,
            model=model,
            retryable=False,
        )
        checks.append(
            ProviderPreflightCheck(
                name="model_present",
                status="failed",
                details={
                    "requested_models": requested_models,
                    "available_models": available_model_ids[:64],
                    "missing_models": missing_models,
                },
                error=f"missing models: {', '.join(missing_models)}",
            )
        )
        return ProviderPreflightReport(
            status="failed",
            provider=resolved_provider,
            base_url=resolved_base_url,
            models=requested_models,
            checks=checks,
            pricing=pricing,
            capabilities=capabilities,
            checked_at=checked_at,
            retryable=False,
            failure=failure,
            api_key_env=resolved_env,
            api_key_fingerprint=api_key_fingerprint,
        )
    checks.append(
        ProviderPreflightCheck(
            name="model_present",
            status="ok",
            details={
                "requested_models": requested_models,
                "available_models": available_model_ids[:64],
            },
        )
    )

    client = client_factory(
        base_url=resolved_base_url,
        api_key=resolved_api_key,
        model=requested_models[0],
        provider_hint=resolved_provider,
        max_retries=0,
        timeout_s=timeout_s,
    )
    try:
        started = time.perf_counter()
        response = await client.generate(
            system="Return compact JSON only.",
            user='Return {"status":"ok"} now.',
            response_format={"type": "json_object"},
            max_tokens=32,
            temperature=0.0,
        )
        raw_response = getattr(response, "raw", None)
        degraded_events = (
            raw_response.get("_gateway_degraded_events")
            if isinstance(raw_response, dict)
            else None
        )
        details: dict[str, Any] = {
            "request_id": getattr(response, "request_id", None),
            "content_preview": str(getattr(response, "content", ""))[:80],
        }
        if isinstance(degraded_events, list) and degraded_events:
            details["degraded_events"] = degraded_events
            details["response_format_mode"] = "fallback_plain_json"
        else:
            details["response_format_mode"] = "json_object"
        checks.append(
            ProviderPreflightCheck(
                name="tiny_completion",
                status="ok",
                latency_ms=int((time.perf_counter() - started) * 1000),
                details=details,
            )
        )
    except Exception as exc:
        retryable = _is_retryable_preflight_error(exc)
        failure = _preflight_failure_payload(
            message=f"tiny completion failed: {exc}",
            provider=resolved_provider,
            model=requested_models[0] if requested_models else None,
            retryable=retryable,
        )
        checks.append(
            ProviderPreflightCheck(
                name="tiny_completion",
                status="failed",
                error=str(exc),
            )
        )
        return ProviderPreflightReport(
            status="failed",
            provider=resolved_provider,
            base_url=resolved_base_url,
            models=requested_models,
            checks=checks,
            pricing=pricing,
            capabilities=capabilities,
            checked_at=checked_at,
            retryable=retryable,
            failure=failure,
            api_key_env=resolved_env,
            api_key_fingerprint=api_key_fingerprint,
        )
    finally:
        aclose = getattr(client, "aclose", None)
        if callable(aclose):
            await aclose()

    report = ProviderPreflightReport(
        status="ok",
        provider=resolved_provider,
        base_url=resolved_base_url,
        models=requested_models,
        checks=checks,
        pricing=pricing,
        capabilities=capabilities,
        checked_at=checked_at,
        api_key_env=resolved_env,
        api_key_fingerprint=api_key_fingerprint,
    )
    _PREFLIGHT_CACHE[cache_key] = (now_monotonic, report)
    return report


async def run_gonka_provider_smoke(
    *,
    model_id: str,
    base_url: str = "https://api.gonkagate.com/v1",
    api_key: str | None = None,
    api_key_env: str | None = None,
    verification_dir: str | Path | None = None,
    include_web_search_smoke: bool = True,
) -> ProviderSmokeReport:
    """Run minimal serial smoke checks for Gonka/Qwen and persist a verification artifact."""
    async with _GONKA_SMOKE_LOCK:
        resolved_api_key = api_key
        resolved_env = api_key_env
        if not resolved_api_key:
            resolved_api_key, resolved_env = resolve_gonka_api_key()
        if not resolved_api_key:
            raise RuntimeError("No Gonka API key configured for live smoke")

        requested_model_id = model_id
        client = GatewayLLMClient(
            base_url=base_url,
            api_key=resolved_api_key,
            model=requested_model_id,
            provider_hint="gonka",
            max_retries=0,
            timeout_s=30.0,
        )
        checks: list[ProviderSmokeCheck] = []
        request_ids: list[str] = []
        available_model_ids: list[str] = []
        notes: list[str] = []
        tool_calling_verified = False
        response_healing_verified = False
        try:
            live_model_ids = await client.list_model_ids(timeout=20.0)
            available_model_ids = sorted(dict.fromkeys(live_model_ids))
            normalized_models = {item.lower(): item for item in available_model_ids}
            resolved_live_model_id = normalized_models.get(
                requested_model_id.lower(),
                requested_model_id,
            )
            if resolved_live_model_id != requested_model_id:
                notes.append(f"model_id_normalized_to_live_catalog:{resolved_live_model_id}")
                await client.aclose()
                client = GatewayLLMClient(
                    base_url=base_url,
                    api_key=resolved_api_key,
                    model=resolved_live_model_id,
                    provider_hint="gonka",
                    max_retries=0,
                    timeout_s=30.0,
                )

            model_check = ProviderSmokeCheck(
                name="models_catalog",
                passed=resolved_live_model_id in set(available_model_ids),
                details={
                    "returned_models": available_model_ids[:64],
                    "requested_model_id": requested_model_id,
                    "resolved_model_id": resolved_live_model_id,
                    "model_present": resolved_live_model_id in set(available_model_ids),
                },
            )
            if not model_check.passed:
                model_check.error = f"model_id '{requested_model_id}' not returned by /v1/models"
                notes.append("model_not_present_in_live_catalog")
            checks.append(model_check)

            checks.append(
                await _run_named_check(
                    "json_completion",
                    lambda: _probe_json_completion(client),
                    request_ids=request_ids,
                )
            )

            tool_check = await _run_named_check(
                "tool_calling",
                lambda: _probe_tool_calling(client),
                request_ids=request_ids,
            )
            checks.append(tool_check)
            tool_calling_verified = tool_check.passed

            healing_check = await _run_named_check(
                "response_healing",
                lambda: _probe_response_healing(client),
                request_ids=request_ids,
            )
            checks.append(healing_check)
            response_healing_verified = healing_check.passed

            if include_web_search_smoke:
                search_service = ScholarDeepSearchService()
                search_result = await search_service.scholar_web_search(
                    query="minimum wage policy evidence",
                    max_results=3,
                    source_types=["government", "academic", "reference"],
                )
                results = search_result.get("results") if isinstance(search_result, dict) else []
                passed = isinstance(results, list) and len(results) > 0
                checks.append(
                    ProviderSmokeCheck(
                        name="scholar_web_search",
                        passed=passed,
                        details={
                            "provider": (
                                search_result.get("provider")
                                if isinstance(search_result, dict)
                                else None
                            ),
                            "result_count": len(results) if isinstance(results, list) else 0,
                        },
                        error=None if passed else "search returned no results",
                    )
                )

            verification = ProviderCapabilityVerification(
                provider="gonka",
                model_id=resolved_live_model_id,
                base_url=base_url.rstrip("/"),
                tool_calling_verified=tool_calling_verified,
                response_healing_verified=response_healing_verified,
                checked_at=datetime.now(UTC),
                request_ids=sorted(dict.fromkeys(request_ids)),
                available_model_ids=available_model_ids,
                source_api_key_env=resolved_env,
                verification_notes=notes,
            )
            save_provider_verification(verification, base_dir=verification_dir)
            return ProviderSmokeReport(
                provider="gonka",
                model_id=model_id,
                base_url=base_url.rstrip("/"),
                checked_at=verification.checked_at,
                verification=verification,
                checks=checks,
            )
        finally:
            await client.aclose()


def _safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9._-]+", "_", (value or "").strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    return cleaned or "unknown"


async def _run_named_check(
    name: str,
    runner,
    *,
    request_ids: list[str],
) -> ProviderSmokeCheck:
    try:
        payload = await runner()
        request_id = payload.get("request_id")
        if isinstance(request_id, str) and request_id:
            request_ids.append(request_id)
        return ProviderSmokeCheck(
            name=name,
            passed=bool(payload.get("passed")),
            request_id=request_id,
            details=dict(payload.get("details") or {}),
            error=payload.get("error"),
        )
    except _PROVIDER_VERIFICATION_CHECK_ERRORS as exc:
        return ProviderSmokeCheck(
            name=name,
            passed=False,
            error=str(exc),
        )


async def _probe_json_completion(client: GatewayLLMClient) -> dict[str, Any]:
    response = await client.generate(
        system="Return a compact JSON object and nothing else.",
        user='Respond with {"status":"ok","sum":4,"provider":"gonka"}.',
        response_format={"type": "json_object"},
        max_tokens=64,
        temperature=0.0,
    )
    try:
        parsed = json.loads(response.content)
        passed = (
            isinstance(parsed, dict)
            and parsed.get("status") == "ok"
            and int(parsed.get("sum", 0)) == 4
        )
        error = None if passed else "unexpected JSON payload"
    except _PROVIDER_VERIFICATION_PARSE_ERRORS as exc:
        passed = False
        error = str(exc)
    return {
        "passed": passed,
        "request_id": response.request_id,
        "details": {
            "provider": response.provider,
            "usage_total_tokens": response.usage.total_tokens,
            "content_preview": response.content[:200],
        },
        "error": error,
    }


async def _probe_tool_calling(client: GatewayLLMClient) -> dict[str, Any]:
    response = await client.generate(
        system=(
            "Use the provided tool exactly once. "
            "Call `record_probe` with value 7 and do not answer in prose."
        ),
        user="Call the tool now.",
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "record_probe",
                    "description": "Records a smoke-test integer probe.",
                    "parameters": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["value"],
                        "properties": {
                            "value": {"type": "integer"},
                        },
                    },
                },
            }
        ],
        tool_choice={"type": "function", "function": {"name": "record_probe"}},
        max_tokens=96,
        temperature=0.0,
    )
    tool_calls = response.tool_calls or []
    passed = any(
        call.name == "record_probe" and int(call.arguments.get("value", 0)) == 7
        for call in tool_calls
    )
    return {
        "passed": passed,
        "request_id": response.request_id,
        "details": {
            "tool_calls": [
                {"id": item.id, "name": item.name, "arguments": item.arguments}
                for item in tool_calls
            ]
        },
        "error": None if passed else "expected tool call was not returned",
    }


async def _probe_response_healing(client: GatewayLLMClient) -> dict[str, Any]:
    response = await client.generate(
        system="Return valid JSON only.",
        user=(
            "Return a JSON object with keys "
            "`status`, `probe`, and `healed`. "
            "The JSON must be parseable."
        ),
        response_format={"type": "json_object"},
        plugins=[{"id": "response-healing"}],
        max_tokens=96,
        temperature=0.0,
    )
    try:
        parsed = json.loads(response.content)
        passed = isinstance(parsed, dict)
        error = None if passed else "response was not a JSON object"
    except _PROVIDER_VERIFICATION_PARSE_ERRORS as exc:
        passed = False
        error = str(exc)
    return {
        "passed": passed,
        "request_id": response.request_id,
        "details": {"content_preview": response.content[:200]},
        "error": error,
    }
