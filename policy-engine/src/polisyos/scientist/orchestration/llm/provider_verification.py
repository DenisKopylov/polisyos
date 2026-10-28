"""Provider capability verification artifacts and live smoke helpers."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import threading
import time
from collections.abc import Mapping
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from polisyos.common.logger import get_logger
from polisyos.core.llm import LLMProducerEvent, TracedLLMClient
from polisyos.scholar.search.service import ScholarDeepSearchService
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerProducerRecord,
    BudgetLedgerProducerRunBinding,
)
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient
from polisyos.scientist.orchestration.llm.prepared_request import (
    PreparedLLMRequest,
    PreparedLLMResult,
    prepare_provider_call,
)
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CachingLLMClient,
    InMemoryPromptCache,
    PreparedCacheRequest,
    prepare_cached_request,
)

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

    @model_validator(mode="before")
    @classmethod
    def _redact_report_urls(cls, value: Any) -> Any:
        return _redact_preflight_report_urls(value)


class ProviderPreflightReport(BaseModel):
    """Additive runtime preflight report persisted with canary/control evidence."""

    model_config = ConfigDict(extra="forbid")

    status: str
    producer_completion_observation: Literal["not_started", "complete", "unavailable"] = Field(
        default="unavailable",
        description=(
            "Source-owned provider-completion state. not_started is emitted only "
            "before the completion request begins; complete requires its durable "
            "producer event; unavailable leaves settlement unresolved."
        ),
    )
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

    @model_validator(mode="before")
    @classmethod
    def _redact_report_urls(cls, value: Any) -> Any:
        return _redact_preflight_report_urls(value)


def _safe_preflight_report_url(url: str) -> str:
    """Render a report-safe URL without userinfo, query, or fragment data."""
    try:
        parts = urlsplit(url)
        hostname = parts.hostname
        port = parts.port
    except ValueError:
        return "<redacted-url>"
    if not parts.scheme or not parts.netloc or not hostname:
        return "<redacted-url>"
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname if port is None else f"{hostname}:{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


_PREFLIGHT_URL_IN_TEXT = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s\"'<>]+")


def _redact_preflight_report_urls(value: Any, *, field_name: str | None = None) -> Any:
    """Recursively redact URL-bearing keys and values before a preflight model is exposed."""
    if isinstance(value, Mapping):
        sanitized: dict[Any, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            safe_key = _redact_preflight_report_urls(key) if isinstance(key, str) else key
            if safe_key in sanitized:
                if not isinstance(safe_key, str):
                    safe_key = f"{safe_key}#redacted-{index}"
                else:
                    base_key = safe_key
                    suffix = 1
                    while safe_key in sanitized:
                        safe_key = f"{base_key}#redacted-{suffix}"
                        suffix += 1
            sanitized[safe_key] = _redact_preflight_report_urls(
                item,
                field_name=str(safe_key),
            )
        return sanitized
    if isinstance(value, list):
        return [_redact_preflight_report_urls(item, field_name=field_name) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_preflight_report_urls(item, field_name=field_name) for item in value)
    if isinstance(value, str):
        normalized_field = (field_name or "").lower()
        if normalized_field == "url" or normalized_field.endswith("_url"):
            return _safe_preflight_report_url(value)
        return _PREFLIGHT_URL_IN_TEXT.sub(
            lambda match: _safe_preflight_report_url(match.group(0)),
            value,
        )
    return value


def _is_preflight_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _preflight_event_from_reference(
    reference: Mapping[str, Any],
) -> LLMProducerEvent | None:
    """Rebuild a typed producer payload before trusting a retained cache reference."""
    required = {
        "amount",
        "budget_key",
        "cache_scope_digest",
        "cost_origin",
        "cost_usd",
        "durability",
        "event_id",
        "event_kind",
        "model",
        "origin_event_id",
        "origin_event_reference",
        "payload_digest",
        "producer_scope_digest",
        "provider",
        "receipts",
        "request_digest",
        "response_digest",
        "run_binding",
        "settlement_status",
        "version",
    }
    if set(reference) != required or reference.get("version") != 1:
        return None
    amount_wire = reference.get("amount")
    if amount_wire is None:
        amount = None
    elif isinstance(amount_wire, str):
        try:
            amount = Decimal(amount_wire)
        except (InvalidOperation, ValueError):
            return None
        if not amount.is_finite() or str(amount) != amount_wire:
            return None
    else:
        return None
    try:
        event = LLMProducerEvent(
            event_id=reference["event_id"],
            request_digest=reference["request_digest"],
            response_digest=reference["response_digest"],
            model=reference["model"],
            provider=reference["provider"],
            amount=amount,
            cost_origin=reference["cost_origin"],
            kind=reference["event_kind"],
            origin_event_id=reference["origin_event_id"],
        )
    except (TypeError, ValueError):
        return None
    expected_cost_usd = float(amount) if amount is not None else None
    if (
        event.payload_digest != reference.get("payload_digest")
        or reference.get("cost_usd") != expected_cost_usd
    ):
        return None
    return event


def _preflight_record_matches_event(
    record: Any,
    event: LLMProducerEvent,
    *,
    settlement_status: Any,
    run_binding: BudgetLedgerProducerRunBinding,
    budget_key: str,
) -> bool:
    if type(record) is not BudgetLedgerProducerRecord:
        return False
    if event.kind == "provider" and (
        event.cost_origin == "reuse" or event.origin_event_id is not None
    ):
        return False
    if event.kind == "reuse" and (
        event.cost_origin != "reuse"
        or event.amount != Decimal(0)
        or not isinstance(event.origin_event_id, str)
        or not event.origin_event_id.strip()
        or settlement_status != "committed"
    ):
        return False
    if event.kind == "provider" and (
        event.cost_origin not in {"reported", "estimated", "unknown"}
        or (event.amount is None) != (event.cost_origin == "unknown")
    ):
        return False
    if settlement_status not in {"committed", "unknown"}:
        return False
    if (settlement_status == "committed") != (event.amount is not None):
        return False
    return (
        record.event_id == event.event_id
        and record.request_digest == event.request_digest
        and record.payload_digest == event.payload_digest
        and record.key == budget_key
        and record.model == event.model
        and record.provider == event.provider
        and record.amount == event.amount
        and record.cost_origin == event.cost_origin
        and record.origin_event_id == event.origin_event_id
        and record.status == settlement_status
        and record.run_binding == run_binding
    )


def _preflight_event_reference_is_current(
    reference: Mapping[str, Any],
    *,
    producer_settlement_store: Any,
    expected_model: str,
    expected_provider: str,
    expected_budget_key: str,
    expected_run_binding: BudgetLedgerProducerRunBinding,
    expected_producer_scope_digest: str,
    expected_cache_scope_digest: str,
    expected_request_digest: str | None,
    required_event_kind: str | None = None,
) -> bool:
    """Resolve exact current ledger bytes before a preflight cache can authorize reuse."""
    if (
        reference.get("model") != expected_model
        or reference.get("provider") != expected_provider
        or reference.get("budget_key") != expected_budget_key
        or reference.get("run_binding") != expected_run_binding.model_dump(mode="json")
        or reference.get("producer_scope_digest") != expected_producer_scope_digest
        or reference.get("cache_scope_digest") != expected_cache_scope_digest
        or reference.get("durability") != "ledger"
        or reference.get("settlement_status") not in {"committed", "unknown"}
        or not isinstance(reference.get("receipts"), list)
        or any(not isinstance(item, str) for item in reference.get("receipts", []))
        or not _is_preflight_digest(reference.get("request_digest"))
        or not _is_preflight_digest(reference.get("payload_digest"))
        or not _is_preflight_digest(reference.get("response_digest"))
        or (
            expected_request_digest is not None
            and reference.get("request_digest") != expected_request_digest
        )
    ):
        return False
    event = _preflight_event_from_reference(reference)
    if event is None or event.model != expected_model or event.provider != expected_provider:
        return False
    if required_event_kind is not None and event.kind != required_event_kind:
        return False
    if not _preflight_record_matches_event(
        producer_settlement_store.resolve_producer_event_safe(event.event_id),
        event,
        settlement_status=reference.get("settlement_status"),
        run_binding=expected_run_binding,
        budget_key=expected_budget_key,
    ):
        return False
    expected_receipts = [event.event_id] if reference["settlement_status"] == "committed" else []
    if reference.get("receipts") != expected_receipts:
        return False
    origin_reference = reference.get("origin_event_reference")
    if event.kind == "provider":
        return origin_reference is None
    if not isinstance(origin_reference, Mapping):
        return False
    origin = _preflight_event_from_reference(origin_reference)
    return (
        origin is not None
        and origin.kind == "provider"
        and origin.event_id == event.origin_event_id
        and origin.request_digest == event.request_digest
        and origin.model == event.model
        and origin.provider == event.provider
        and origin_reference.get("run_binding") == reference.get("run_binding")
        and origin_reference.get("budget_key") == reference.get("budget_key")
        and _preflight_event_reference_is_current(
            origin_reference,
            producer_settlement_store=producer_settlement_store,
            expected_model=expected_model,
            expected_provider=expected_provider,
            expected_budget_key=expected_budget_key,
            expected_run_binding=expected_run_binding,
            expected_producer_scope_digest=expected_producer_scope_digest,
            expected_cache_scope_digest=expected_cache_scope_digest,
            expected_request_digest=expected_request_digest,
            required_event_kind="provider",
        )
    )


def _preflight_producer_event_reference(
    event: Mapping[str, Any],
    *,
    expected_model: str,
    expected_provider: str,
    expected_budget_key: str,
    expected_run_binding: BudgetLedgerProducerRunBinding,
    expected_producer_scope_digest: str,
    expected_cache_scope_digest: str,
    expected_request_digest: str | None,
    producer_settlement_store: Any,
    origin_event_reference: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Project one observed typed event only after resolving its exact durable ledger record."""
    producer_event = event.get("producer_event")
    if type(producer_event) is not LLMProducerEvent:
        return None
    if (
        event.get("event_id") != producer_event.event_id
        or event.get("producer_payload_digest") != producer_event.payload_digest
        or event.get("amount") != producer_event.amount
        or event.get("model") != expected_model
        or event.get("provider") != expected_provider
        or event.get("cost_origin") != producer_event.cost_origin
        or event.get("cost_usd")
        != (float(producer_event.amount) if producer_event.amount is not None else None)
        or event.get("origin_event_id") != producer_event.origin_event_id
        or event.get("durability") != "ledger"
    ):
        return None
    status = event.get("settlement_status")
    receipts = event.get("receipts")
    if not isinstance(receipts, (list, tuple)) or any(
        not isinstance(item, str) for item in receipts
    ):
        return None
    source_reference = None
    if producer_event.kind == "reuse":
        if not isinstance(origin_event_reference, Mapping):
            return None
        source_event = _preflight_event_from_reference(origin_event_reference)
        if (
            source_event is None
            or source_event.kind != "provider"
            or source_event.event_id != producer_event.origin_event_id
        ):
            return None
        source_reference = dict(origin_event_reference)
    reference = {
        "amount": str(producer_event.amount) if producer_event.amount is not None else None,
        "budget_key": expected_budget_key,
        "cache_scope_digest": expected_cache_scope_digest,
        "cost_origin": producer_event.cost_origin,
        "cost_usd": float(producer_event.amount) if producer_event.amount is not None else None,
        "durability": event.get("durability"),
        "event_id": producer_event.event_id,
        "event_kind": producer_event.kind,
        "model": producer_event.model,
        "origin_event_id": producer_event.origin_event_id,
        "origin_event_reference": source_reference,
        "payload_digest": producer_event.payload_digest,
        "producer_scope_digest": expected_producer_scope_digest,
        "provider": producer_event.provider,
        "receipts": list(receipts),
        "request_digest": producer_event.request_digest,
        "response_digest": producer_event.response_digest,
        "run_binding": expected_run_binding.model_dump(mode="json"),
        "settlement_status": status,
        "version": 1,
    }
    try:
        current = _preflight_event_reference_is_current(
            reference,
            producer_settlement_store=producer_settlement_store,
            expected_model=expected_model,
            expected_provider=expected_provider,
            expected_budget_key=expected_budget_key,
            expected_run_binding=expected_run_binding,
            expected_producer_scope_digest=expected_producer_scope_digest,
            expected_cache_scope_digest=expected_cache_scope_digest,
            expected_request_digest=expected_request_digest,
        )
    except Exception:
        current = False
    if not current:
        return None
    return reference


_PREFLIGHT_CACHE: dict[
    tuple[str, tuple[str, ...], str, str | None], tuple[float, ProviderPreflightReport]
] = {}
type _PreflightCompletionCacheKey = tuple[str, tuple[str, ...], str, str | None, str]

_PREFLIGHT_COMPLETION_CACHE: dict[
    _PreflightCompletionCacheKey,
    tuple[InMemoryPromptCache, dict[str, Any]],
] = {}


def _preflight_completion_request_kwargs() -> dict[str, Any]:
    return {
        "system": "Return compact JSON only.",
        "user": 'Return {"status":"ok"} now.',
        "response_format": {"type": "json_object"},
        "max_tokens": 32,
        "temperature": 0.0,
    }


def _preflight_prompt_cache_settings(ttl_s: int) -> tuple[int, float] | None:
    """Mirror the existing gateway cache environment with a bounded preflight lifetime."""
    try:
        configured_ttl = float(os.getenv("POLISYOS_LLM_CACHE_TTL_S", "300").strip())
    except (TypeError, ValueError):
        configured_ttl = 300.0
    try:
        configured_size = int(os.getenv("POLISYOS_LLM_CACHE_MAXSIZE", "128").strip())
    except (TypeError, ValueError):
        configured_size = 128
    if configured_size <= 0 or not (configured_ttl > 0):
        return None
    effective_ttl = min(max(float(ttl_s), 0.0), configured_ttl)
    return (min(configured_size, 128), effective_ttl) if effective_ttl > 0 else None


class _PreflightGatewayClientAdapter:
    """Own one real prepared gateway dispatch and close it after physical settlement."""

    def __init__(
        self,
        *,
        client_factory: Any,
        base_url: str,
        api_key: str,
        model: str,
        provider: str,
        timeout_s: float,
    ) -> None:
        self.model, self.provider, self.timeout_s = model, provider, timeout_s
        self._client = client_factory(
            base_url=base_url,
            api_key=api_key,
            model=model,
            provider_hint=provider,
            max_retries=0,
            timeout_s=timeout_s,
        )
        self._lock = threading.Lock()
        self._prepared = False
        self._running = False
        self._closed = False
        self._client_closed = False

    def prepare_cache_request(self, *args: Any, **kwargs: Any) -> PreparedLLMRequest:
        """Delegate identity and actual send to this invocation's real provider owner."""
        with self._lock:
            if self._closed or self._prepared:
                raise ValueError("preflight_gateway_request_already_prepared_or_closed")
            self._prepared = True
        actual, _caller = prepare_provider_call(self._client, args, kwargs)

        async def execute() -> PreparedLLMResult:
            with self._lock:
                if self._closed or self._running:
                    raise ValueError("preflight_gateway_request_closed_or_running")
                self._running = True
            try:
                return await actual.execute()
            finally:
                with self._lock:
                    self._running = False
                await self.aclose()

        return PreparedLLMRequest(actual.identity, execute, actual.reusable)

    async def generate(self, *args: Any, **kwargs: Any) -> Any:
        return (await self.prepare_cache_request(*args, **kwargs).execute()).response

    async def aclose(self) -> None:
        """Disable new work, deferring close while an admitted physical call settles."""
        with self._lock:
            self._closed = True
            close_now = not self._running and not self._client_closed
            if close_now:
                self._client_closed = True
        if close_now:
            await self._client.aclose()


def _new_preflight_cached_client(
    *,
    adapter: _PreflightGatewayClientAdapter,
    prepared: PreparedCacheRequest,
    cache_settings: tuple[int, float],
    cache: InMemoryPromptCache | None = None,
) -> CachingLLMClient:
    maxsize, cache_ttl = cache_settings
    return CachingLLMClient(
        adapter,
        cache=cache
        if cache is not None
        else InMemoryPromptCache(maxsize=maxsize, default_ttl_s=cache_ttl),
        model=prepared.model,
        provider_route=prepared.provider_route,
        ttl_s=cache_ttl,
        inflight_timeout_s=adapter.timeout_s,
        origin_retention_limit=maxsize,
        prepared_request=prepared,
    )


def _store_preflight_cached_client(
    cache_key: _PreflightCompletionCacheKey,
    cache: InMemoryPromptCache,
    producer_event_reference: dict[str, Any],
    *,
    max_entries: int,
) -> None:
    _PREFLIGHT_COMPLETION_CACHE.pop(cache_key, None)
    _PREFLIGHT_COMPLETION_CACHE[cache_key] = (
        cache,
        json.loads(json.dumps(producer_event_reference)),
    )
    while len(_PREFLIGHT_COMPLETION_CACHE) > max_entries:
        del _PREFLIGHT_COMPLETION_CACHE[next(iter(_PREFLIGHT_COMPLETION_CACHE))]


def _preflight_unknown_report(
    *,
    provider: str,
    base_url: str,
    models: list[str],
    checked_at: datetime,
    api_key_env: str,
    api_key_fingerprint: str | None,
    message: str,
    checks: list[ProviderPreflightCheck] | None = None,
) -> ProviderPreflightReport:
    failure = _preflight_failure_payload(
        message=message,
        provider=provider,
        model=models[0] if models else None,
        retryable=False,
    )
    failure["code"] = "llm_provider_preflight_settlement_unknown"
    failure["next_action"] = (
        "Reopen the durable producer event and reconcile its exact run binding before retrying."
    )
    return ProviderPreflightReport(
        status="unknown",
        provider=provider,
        base_url=base_url,
        models=models,
        checks=checks or [],
        checked_at=checked_at,
        retryable=False,
        failure=failure,
        api_key_env=api_key_env,
        api_key_fingerprint=api_key_fingerprint,
    )


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
    try:
        parts = urlsplit(base_url.rstrip("/"))
    except ValueError:
        return base_url.rstrip("/")
    path = parts.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3].rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _validate_preflight_url(url: str) -> None:
    """Require an absolute HTTP(S) provider endpoint without URL credentials."""
    invalid_message = "Provider preflight URLs must be absolute HTTP(S) URLs without credentials"
    if not url or url != url.strip() or any(character.isspace() for character in url):
        raise ValueError(invalid_message)
    try:
        parts = urlsplit(url)
        hostname = parts.hostname
        _ = parts.port
    except ValueError as exc:
        raise ValueError(invalid_message) from exc
    if (
        parts.scheme.lower() not in {"http", "https"}
        or not parts.netloc
        or not hostname
        or any(character.isspace() for character in hostname)
        or parts.username is not None
        or parts.password is not None
    ):
        raise ValueError(invalid_message)


def _preflight_url_origin(url: str) -> tuple[str, str, int]:
    _validate_preflight_url(url)
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    port = parts.port
    if port is None:
        port = 443 if scheme == "https" else 80
    return scheme, str(parts.hostname).lower(), port


class _ProviderPreflightRedirectHandler(HTTPRedirectHandler):
    """Follow provider endpoint redirects only while the origin remains fixed."""

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request:
        try:
            target_origin = _preflight_url_origin(newurl)
            request_origin = _preflight_url_origin(req.full_url)
        except ValueError as exc:
            raise HTTPError(
                req.full_url,
                code,
                "provider preflight redirect target is not an absolute HTTP(S) URL",
                headers,
                fp,
            ) from exc
        if target_origin != request_origin:
            raise HTTPError(
                req.full_url,
                code,
                "provider preflight redirect changed origin",
                headers,
                fp,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


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
    _validate_preflight_url(url)

    def _fetch() -> dict[str, Any]:
        # Both URL-consuming calls are guarded by the absolute HTTP(S) check above.
        request = Request(url, headers=headers or {}, method="GET")  # noqa: S310
        opener = build_opener(_ProviderPreflightRedirectHandler())
        with opener.open(request, timeout=timeout_s) as response:
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
    producer_settlement_store: Any | None = None,
    producer_run_binding: BudgetLedgerProducerRunBinding | None = None,
    pre_admission_attempt_id: str | None = None,
    producer_budget_key: str | None = None,
    require_producer_settlement: bool = False,
) -> ProviderPreflightReport:
    """Run a short real-provider gate before expensive NL workflows."""
    resolved_provider = (
        provider or os.getenv("POLISYOS_LLM_GATEWAY_PROVIDER") or "gateway"
    ).strip()
    resolved_base_url = (
        (base_url or os.getenv("POLISYOS_LLM_GATEWAY_BASE_URL") or "https://proxy.gonka.gg/v1")
        .strip()
        .rstrip("/")
    )
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
            producer_completion_observation="not_started",
            checked_at=checked_at,
            retryable=False,
            failure=failure,
        )
    if os.getenv("POLISYOS_LLM_SIMULATION_MODE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
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
            producer_completion_observation="not_started",
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
            producer_completion_observation="not_started",
            checked_at=checked_at,
            retryable=False,
            failure=failure,
            api_key_env=resolved_env,
            api_key_fingerprint=api_key_fingerprint,
        )

    producer_accounting_requested = (
        require_producer_settlement
        or producer_settlement_store is not None
        or producer_run_binding is not None
        or producer_budget_key is not None
    )
    accounting_failure: str | None = None
    resolved_producer_budget_key: str | None = None
    producer_scope_key: str | None = None
    if producer_accounting_requested:
        if (
            producer_settlement_store is None
            or type(producer_run_binding) is not BudgetLedgerProducerRunBinding
        ):
            accounting_failure = (
                "Provider preflight requires a durable producer ledger and a "
                "server-issued run binding."
            )
        else:
            expected_budget_key = f"nl-run:{producer_run_binding.run_id}"
            resolved_producer_budget_key = producer_budget_key or expected_budget_key
            if resolved_producer_budget_key != expected_budget_key:
                accounting_failure = (
                    "Provider preflight producer budget key does not match its run."
                )
            else:
                required_store_operations = (
                    "begin_producer_event_safe",
                    "settle_producer_event_safe",
                    "resolve_producer_event_safe",
                    "producer_run_binding_scope",
                )
                try:
                    owner_identity = producer_settlement_store.settlement_owner_identity
                    has_store_operations = all(
                        callable(getattr(producer_settlement_store, operation, None))
                        for operation in required_store_operations
                    )
                except Exception:
                    owner_identity = None
                    has_store_operations = False
                if (
                    not isinstance(owner_identity, tuple)
                    or len(owner_identity) != 3
                    or any(not isinstance(item, str) or not item.strip() for item in owner_identity)
                    or not has_store_operations
                ):
                    accounting_failure = (
                        "Provider preflight durable producer settlement is unavailable."
                    )
                else:
                    binding_bytes = json.dumps(
                        {
                            "provider": resolved_provider,
                            "run_binding": producer_run_binding.model_dump(mode="json"),
                            "settlement_owner_identity": owner_identity,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                    producer_scope_key = hashlib.sha256(binding_bytes).hexdigest()
    if accounting_failure is not None:
        failure = _preflight_failure_payload(
            message=accounting_failure,
            provider=resolved_provider,
            model=requested_models[0],
            retryable=False,
        )
        return ProviderPreflightReport(
            status="failed",
            provider=resolved_provider,
            base_url=resolved_base_url,
            models=requested_models,
            producer_completion_observation="not_started",
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
        producer_scope_key,
    )
    accounting_enabled = producer_scope_key is not None
    cache_scope_bytes = json.dumps(
        {
            "api_key_fingerprint": api_key_fingerprint or "",
            "base_url": resolved_base_url,
            "models": requested_models,
            "producer_scope_key": producer_scope_key,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    cache_scope_digest = hashlib.sha256(cache_scope_bytes).hexdigest()
    cached = _PREFLIGHT_CACHE.get(cache_key) if not accounting_enabled else None
    now_monotonic = time.monotonic()
    if cached is not None and now_monotonic - cached[0] <= max(0, ttl_s):
        return cached[1].model_copy(update={"cache_hit": True})

    completion_cache_settings = (
        _preflight_prompt_cache_settings(ttl_s)
        if accounting_enabled and client_factory is GatewayLLMClient
        else None
    )
    completion_cache_key: _PreflightCompletionCacheKey | None = None
    completion_cache_client: CachingLLMClient | None = None
    completion_cache_resource: InMemoryPromptCache | None = None
    prior_completion_reference: dict[str, Any] | None = None
    completion_request_kwargs = _preflight_completion_request_kwargs()
    expected_completion_request_digest: str | None = None
    if completion_cache_settings is not None:
        adapter = _PreflightGatewayClientAdapter(
            client_factory=client_factory,
            base_url=resolved_base_url,
            api_key=resolved_api_key,
            model=requested_models[0],
            provider=resolved_provider,
            timeout_s=timeout_s,
        )
        prepared = prepare_cached_request(
            adapter,
            model=requested_models[0],
            provider_route=resolved_provider,
            kwargs=completion_request_kwargs,
        )
        expected_completion_request_digest = prepared.request_digest
        _, completion_request_kwargs = prepared.call_values()
        # Current transport/body identity is part of lookup, not reconstructed
        # from a retained wrapper or a report's declaration after dispatch.
        completion_cache_key = (*cache_key, expected_completion_request_digest)
        completion_entry = _PREFLIGHT_COMPLETION_CACHE.get(completion_cache_key)
        if completion_entry is not None:
            try:
                completion_cache_resource, prior_completion_reference = completion_entry
                if type(completion_cache_resource) is not InMemoryPromptCache or not isinstance(
                    prior_completion_reference, Mapping
                ):
                    raise TypeError("cached producer resource/reference is malformed")
                current_reference = _preflight_event_reference_is_current(
                    prior_completion_reference,
                    producer_settlement_store=producer_settlement_store,
                    expected_model=requested_models[0],
                    expected_provider=resolved_provider,
                    expected_budget_key=resolved_producer_budget_key or "run",
                    expected_run_binding=producer_run_binding,
                    expected_producer_scope_digest=producer_scope_key or "",
                    expected_cache_scope_digest=cache_scope_digest,
                    expected_request_digest=expected_completion_request_digest,
                )
            except Exception:
                current_reference = False
            if not current_reference:
                await adapter.aclose()
                return _preflight_unknown_report(
                    provider=resolved_provider,
                    base_url=resolved_base_url,
                    models=requested_models,
                    checked_at=checked_at,
                    api_key_env=resolved_env,
                    api_key_fingerprint=api_key_fingerprint,
                    message=(
                        "The retained preflight producer event is missing, malformed, or no longer "
                        "matches the exact durable run, request, provider, and profile scope."
                    ),
                )
        if completion_cache_resource is None:
            completion_cache_resource = InMemoryPromptCache(
                maxsize=completion_cache_settings[0], default_ttl_s=completion_cache_settings[1]
            )
        completion_cache_client = _new_preflight_cached_client(
            adapter=adapter,
            prepared=prepared,
            cache_settings=completion_cache_settings,
            cache=completion_cache_resource,
        )

    fetch = fetch_json or _default_fetch_json
    root_url = _provider_root_url(resolved_base_url)
    headers = {"Authorization": f"Bearer {resolved_api_key}"}
    checks: list[ProviderPreflightCheck] = []
    pricing: dict[str, Any] = {}
    capabilities: dict[str, Any] = {}

    async def _run_json_check(name: str, url: str) -> dict[str, Any] | None:
        started = time.perf_counter()
        try:
            _validate_preflight_url(url)
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
        capabilities = (
            await _run_json_check(
                "capabilities",
                _join_url(root_url, "/api/models/capabilities"),
            )
            or {}
        )
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
        if completion_cache_client is not None:
            await completion_cache_client.aclose()
        return ProviderPreflightReport(
            status="failed",
            provider=resolved_provider,
            base_url=resolved_base_url,
            models=requested_models,
            checks=checks,
            pricing=pricing,
            capabilities=capabilities,
            producer_completion_observation="not_started",
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
        if completion_cache_client is not None:
            await completion_cache_client.aclose()
        return ProviderPreflightReport(
            status="failed",
            provider=resolved_provider,
            base_url=resolved_base_url,
            models=requested_models,
            checks=checks,
            pricing=pricing,
            capabilities=capabilities,
            producer_completion_observation="not_started",
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

    client: Any = completion_cache_client
    if client is None:
        client = client_factory(
            base_url=resolved_base_url,
            api_key=resolved_api_key,
            model=requested_models[0],
            provider_hint=resolved_provider,
            max_retries=0,
            timeout_s=timeout_s,
        )
    observed_producer_events: list[dict[str, Any]] = []
    preflight_client: Any = client
    if accounting_enabled:
        preflight_client = TracedLLMClient(
            client,
            model_name=requested_models[0],
            run_id=producer_run_binding.run_id,
            provider_name=resolved_provider,
            prompt_mode="user",
            producer_settlement_store=producer_settlement_store,
            producer_budget_key=resolved_producer_budget_key or "run",
            call_observer=observed_producer_events.append,
        )
    producer_scope = (
        producer_settlement_store.producer_run_binding_scope(
            producer_run_binding,
            pre_admission_attempt_id=pre_admission_attempt_id,
        )
        if accounting_enabled
        else nullcontext()
    )
    producer_completion_observation: Literal["not_started", "complete", "unavailable"] = (
        "unavailable"
    )
    try:
        started = time.perf_counter()
        with producer_scope:
            response = await preflight_client.generate(**completion_request_kwargs)
        raw_response = getattr(response, "raw", None)
        degraded_events = (
            raw_response.get("_gateway_degraded_events") if isinstance(raw_response, dict) else None
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
        origin_reference = None
        if prior_completion_reference is not None:
            if prior_completion_reference.get("event_kind") == "provider":
                origin_reference = prior_completion_reference
            else:
                origin_reference = prior_completion_reference.get("origin_event_reference")
        producer_event_reference = (
            _preflight_producer_event_reference(
                observed_producer_events[0],
                expected_model=requested_models[0],
                expected_provider=resolved_provider,
                expected_budget_key=resolved_producer_budget_key or "run",
                expected_run_binding=producer_run_binding,
                expected_producer_scope_digest=producer_scope_key or "",
                expected_cache_scope_digest=cache_scope_digest,
                expected_request_digest=expected_completion_request_digest,
                producer_settlement_store=producer_settlement_store,
                origin_event_reference=origin_reference,
            )
            if accounting_enabled and len(observed_producer_events) == 1
            else None
        )
        if accounting_enabled and producer_event_reference is not None:
            details["producer_event"] = producer_event_reference
            producer_completion_observation = "complete"
        if accounting_enabled and producer_event_reference is None:
            message = (
                "Provider preflight completion has no exact durable producer settlement; "
                "reconcile the ledger before launching the run."
            )
            checks.append(
                ProviderPreflightCheck(
                    name="tiny_completion",
                    status="unknown",
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    details=details,
                    error=message,
                )
            )
            return _preflight_unknown_report(
                provider=resolved_provider,
                base_url=resolved_base_url,
                models=requested_models,
                checked_at=checked_at,
                api_key_env=resolved_env,
                api_key_fingerprint=api_key_fingerprint,
                message=message,
                checks=checks,
            )
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
        failure_details: dict[str, Any] = {}
        if accounting_enabled:
            producer_event_reference = None
            if len(observed_producer_events) == 1:
                producer_event_reference = _preflight_producer_event_reference(
                    observed_producer_events[0],
                    expected_model=requested_models[0],
                    expected_provider=resolved_provider,
                    expected_budget_key=resolved_producer_budget_key or "run",
                    expected_run_binding=producer_run_binding,
                    expected_producer_scope_digest=producer_scope_key or "",
                    expected_cache_scope_digest=cache_scope_digest,
                    expected_request_digest=expected_completion_request_digest,
                    producer_settlement_store=producer_settlement_store,
                )
            if producer_event_reference is None:
                message = (
                    "Provider preflight completion failed without an exact durable producer "
                    "settlement; reconcile the event before retrying."
                )
                checks.append(
                    ProviderPreflightCheck(
                        name="tiny_completion",
                        status="unknown",
                        latency_ms=int((time.perf_counter() - started) * 1000),
                        details={},
                        error=message,
                    )
                )
                return _preflight_unknown_report(
                    provider=resolved_provider,
                    base_url=resolved_base_url,
                    models=requested_models,
                    checked_at=checked_at,
                    api_key_env=resolved_env,
                    api_key_fingerprint=api_key_fingerprint,
                    message=message,
                    checks=checks,
                )
            producer_completion_observation = "complete"
            failure_details["producer_event"] = producer_event_reference
        checks.append(
            ProviderPreflightCheck(
                name="tiny_completion",
                status="failed",
                details=failure_details,
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
            producer_completion_observation=producer_completion_observation,
            api_key_env=resolved_env,
            api_key_fingerprint=api_key_fingerprint,
        )
    finally:
        aclose = getattr(preflight_client, "aclose", None)
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
        producer_completion_observation=producer_completion_observation,
        api_key_env=resolved_env,
        api_key_fingerprint=api_key_fingerprint,
    )
    if accounting_enabled:
        if completion_cache_key is not None and completion_cache_resource is not None:
            _store_preflight_cached_client(
                completion_cache_key,
                completion_cache_resource,
                producer_event_reference,
                max_entries=completion_cache_settings[0],
            )
    else:
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
