"""Prompt-level response cache for LLM calls."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from polisyos.common.logger import get_logger
from polisyos.common.serialization import stable_json_dumps, to_python_data
from polisyos.core.llm.settlement import (
    _CacheFlightOutcome,
    _CacheFlightRegistration,
    _CacheReuseOwner,
)

from .gateway_client import GatewayLLMResponse, GatewayToolCall, GatewayUsage

try:
    import orjson
except ModuleNotFoundError:  # pragma: no cover - optional acceleration
    orjson = None  # type: ignore[assignment]

logger = get_logger(__name__)

_VOLATILE_CACHE_METADATA_KEYS = frozenset(
    {
        "attempt",
        "cache_buster",
        "created_at",
        "fetched_at",
        "generated_at",
        "request_id",
        "retrieved_at",
        "retry",
        "run_id",
        "session_id",
        "span_id",
        "timestamp",
        "trace_id",
        "updated_at",
    }
)
_VOLATILE_CACHE_METADATA_SUFFIXES = (
    "_at",
    "_ts",
    "_timestamp",
)


@dataclass(frozen=True, slots=True)
class _SerializedGatewayToolCall:
    id: str
    name: str
    arguments_json: bytes
    error_envelope_json: bytes | None = None


@dataclass(frozen=True, slots=True)
class _SerializedGatewayResponse:
    content: str
    usage_prompt_tokens: int
    usage_completion_tokens: int
    usage_total_tokens: int
    usage_cost_usd: float | None
    model: str
    provider: str | None
    request_id: str | None
    response_headers: dict[str, str] | None
    raw_json: bytes | None
    tool_calls: tuple[_SerializedGatewayToolCall, ...] = ()
    origin_event_id: str | None = None


@dataclass(frozen=True, slots=True)
class CacheReuseEvidence:
    """Immutable evidence selected for a snapshot-scoped cache reuse request."""

    ref: str
    version: str
    immutable: bool
    content: bytes
    content_hash: str


@dataclass(frozen=True, slots=True)
class CacheReuseRequest:
    """Exact actor, tenant, scope, purpose, model, parameters and evidence request."""

    actor_id: str
    tenant: str
    scope: str
    purpose: str
    model: str
    parameters_digest: str
    evidence: tuple[CacheReuseEvidence, ...]


@dataclass(frozen=True, slots=True)
class CacheReuseDecision:
    """Current authorization decision bound to one complete reuse request."""

    issuer: str
    epoch: str
    actor_id: str
    tenant: str
    scope: str
    purpose: str
    model: str
    parameters_digest: str
    evidence: tuple[CacheReuseEvidence, ...]


class CacheReuseAuthorizer(Protocol):
    """Authorize a cache reuse request after independently binding its evidence."""

    def authorize_reuse(self, request: CacheReuseRequest) -> CacheReuseDecision | None: ...


@dataclass(slots=True)
class _CacheFlight:
    task: asyncio.Task[Any]
    request_digest: str
    scope_key: tuple[str, ...]
    owner_registration: _CacheFlightRegistration
    registrations: list[_CacheFlightRegistration]
    producer_attempt_id: str
    origin_event_id: str
    cache_key: str
    outcome: _CacheFlightOutcome | None = None


class _CacheReuseGatewayResponse(GatewayLLMResponse):
    """Gateway response carrying cache-owned provenance outside provider raw data."""

    __slots__ = (
        "_polisyos_cache_hit",
        "_polisyos_cache_key",
        "_polisyos_reuse_event_id",
        "_polisyos_reuse_provenance",
    )

    def __init__(
        self,
        response: GatewayLLMResponse,
        *,
        cache_key: str,
        owner: _CacheReuseOwner,
        request_digest: str,
        origin_event_id: str,
        outcome: _CacheFlightOutcome | None = None,
    ) -> None:
        super().__init__(
            content=response.content,
            usage=response.usage,
            model=response.model,
            provider=response.provider,
            request_id=response.request_id,
            response_headers=response.response_headers,
            raw=response.raw,
            tool_calls=response.tool_calls,
            producer_event_id=response.producer_event_id,
        )
        self._polisyos_cache_hit = True
        self._polisyos_cache_key = cache_key
        self._polisyos_reuse_event_id = f"cache-reuse:{uuid.uuid4().hex}"
        self._polisyos_reuse_provenance = owner.issue(
            cache_key,
            request_digest,
            self._polisyos_reuse_event_id,
            origin_event_id,
            outcome,
        )


class PromptCacheProtocol(Protocol):
    """Protocol for prompt cache implementations."""

    def get(self, cache_key: str) -> GatewayLLMResponse | None: ...
    def put(self, cache_key: str, response: GatewayLLMResponse, ttl_s: float) -> None: ...


def compute_cache_key(
    *,
    prompt: Any | None = None,
    system: str | None = None,
    user: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    model: str = "",
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
    stream: bool | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    seed: int | None = None,
    response_format: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    extra_payload: dict[str, Any] | None = None,
) -> str:
    """Compute a deterministic cache key from prompt parameters.

    The key is a SHA-256 hex digest of a canonical JSON representation
    of the input parameters.
    """
    canonical = stable_json_dumps(
        {
            "prompt": to_python_data(prompt, sort_keys=True),
            "system": system or "",
            "user": user or "",
            "messages": to_python_data(messages or [], sort_keys=True),
            "model": model,
            "tools": to_python_data(tools or [], sort_keys=True),
            "tool_choice": to_python_data(tool_choice, sort_keys=True),
            "stream": stream,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "seed": seed,
            "response_format": to_python_data(response_format, sort_keys=True),
            "metadata": _sanitize_cache_metadata(metadata),
            "extra_payload": _sanitize_cache_metadata(extra_payload),
        },
        ensure_ascii=True,
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class PromptCacheTelemetry:
    """Observable prompt cache counters."""

    hits: int = 0
    misses: int = 0
    puts: int = 0
    skips: int = 0
    evictions: int = 0
    expired: int = 0
    skip_reasons: dict[str, int] = field(default_factory=dict)


class InMemoryPromptCache:
    """Thread-safe in-memory LRU prompt cache with TTL.

    Entries are evicted either when the cache exceeds ``maxsize`` (oldest
    first) or when their TTL expires.
    """

    def __init__(self, *, maxsize: int = 128, default_ttl_s: float = 300.0) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be >= 1")
        self._maxsize = maxsize
        self._default_ttl_s = max(default_ttl_s, 0.0)
        self._lock = threading.Lock()
        self._store: OrderedDict[str, tuple[_SerializedGatewayResponse, float]] = OrderedDict()
        self._telemetry = PromptCacheTelemetry()

    def get(self, cache_key: str) -> GatewayLLMResponse | None:
        """Return cached response or ``None`` if miss/expired."""
        with self._lock:
            entry = self._store.get(cache_key)
            if entry is None:
                self._telemetry.misses += 1
                return None
            response, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[cache_key]
                self._telemetry.expired += 1
                self._telemetry.misses += 1
                return None
            # Move to end (most recently used)
            self._store.move_to_end(cache_key)
            self._telemetry.hits += 1
            return _thaw_response(response)

    def put(
        self,
        cache_key: str,
        response: GatewayLLMResponse,
        ttl_s: float | None = None,
    ) -> None:
        """Cache *response* under *cache_key* with optional TTL override."""
        effective_ttl = ttl_s if ttl_s is not None else self._default_ttl_s
        expires_at = time.monotonic() + effective_ttl
        serialized = _freeze_response(response)
        with self._lock:
            if cache_key in self._store:
                self._store.move_to_end(cache_key)
            self._store[cache_key] = (serialized, expires_at)
            self._telemetry.puts += 1
            while len(self._store) > self._maxsize:
                self._store.popitem(last=False)
                self._telemetry.evictions += 1

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._telemetry = PromptCacheTelemetry()

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "hits": self._telemetry.hits,
                "misses": self._telemetry.misses,
                "puts": self._telemetry.puts,
                "skips": self._telemetry.skips,
                "evictions": self._telemetry.evictions,
                "expired": self._telemetry.expired,
                "skip_reasons": dict(self._telemetry.skip_reasons),
                "size": len(self._store),
            }

    def record_skip(self, reason: str) -> None:
        with self._lock:
            self._telemetry.skips += 1
            self._telemetry.skip_reasons[reason] = self._telemetry.skip_reasons.get(reason, 0) + 1


class CachingLLMClient:
    """Prompt-cache wrapper for deterministic non-tool `generate()` calls."""

    def __init__(
        self,
        client: Any,
        *,
        cache: PromptCacheProtocol,
        model: str,
        ttl_s: float = 300.0,
        inflight_timeout_s: float | None = None,
        reuse_authorizer: CacheReuseAuthorizer | Any | None = None,
    ) -> None:
        self._client = client
        self._cache = cache
        self._model = model
        self._ttl_s = max(float(ttl_s), 0.0)
        configured_timeout = inflight_timeout_s
        if configured_timeout is None:
            configured_timeout = getattr(client, "timeout_s", None)
        self._inflight_timeout_s = _coerce_timeout(configured_timeout)
        self._inflight: dict[str, _CacheFlight] = {}
        self._cache_reuse_authorizer = reuse_authorizer
        self._cache_reuse_owner = _CacheReuseOwner(self)
        self._producer_begin_hook: Any | None = None
        self._producer_settle_hook: Any | None = None
        self._producer_unknown_hook: Any | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def unwrap(self) -> Any:
        return self._client

    def set_producer_settlement_hooks(self, *, begin: Any, settle: Any, unknown: Any) -> None:
        """Bind producer-owned durable settlement before shielding provider work."""
        self._producer_begin_hook = begin
        self._producer_settle_hook = settle
        self._producer_unknown_hook = unknown

    def _request_digest(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        """Bind every provider request, including calls excluded from cache reuse."""

        return compute_cache_key(
            prompt=args[0] if args else kwargs.get("prompt"),
            system=kwargs.get("system"),
            user=kwargs.get("user"),
            messages=kwargs.get("messages"),
            model=self._model,
            tools=kwargs.get("tools"),
            tool_choice=kwargs.get("tool_choice"),
            stream=kwargs.get("stream"),
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens"),
            seed=kwargs.get("seed"),
            response_format=kwargs.get("response_format"),
            metadata=kwargs.get("metadata"),
            extra_payload={
                key: value
                for key, value in kwargs.items()
                if key
                not in {
                    "prompt",
                    "system",
                    "user",
                    "messages",
                    "tools",
                    "tool_choice",
                    "stream",
                    "temperature",
                    "max_tokens",
                    "seed",
                    "response_format",
                    "metadata",
                }
            },
        )

    async def _generate_uncached(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        request_digest: str | None = None,
    ) -> Any:
        """Run a non-reusable provider call through the same settlement hooks."""

        begin = self._producer_begin_hook
        settle = self._producer_settle_hook
        unknown = self._producer_unknown_hook
        event_id = f"llm-provider:{uuid.uuid4().hex}"
        digest = request_digest or self._request_digest(args, kwargs)
        intent_started = False
        try:
            if begin is not None:
                await _maybe_await(begin(event_id, digest, getattr(self._client, "provider", None)))
                intent_started = True
            response = await _maybe_await(self._client.generate(*args, **_provider_kwargs(kwargs)))
            if isinstance(response, GatewayLLMResponse) and intent_started:
                response.producer_event_id = event_id
            if settle is not None and intent_started:
                settlement = await _maybe_await(settle(event_id, digest, response))
                if isinstance(response, GatewayLLMResponse):
                    response.producer_settlement = settlement
            return response
        except BaseException as exc:
            if intent_started and unknown is not None:
                await _maybe_await(unknown(event_id, digest, exc))
            raise

    async def generate(self, *args: Any, **kwargs: Any) -> Any:
        args, kwargs = _normalize_prompt_call(args, kwargs)
        reason = _cache_skip_reason(
            model=self._model,
            args=args,
            kwargs=kwargs,
        )
        if reason is not None:
            _record_cache_skip(self._cache, reason)
            return await self._generate_uncached(args, kwargs)

        cache_key = self._request_digest(args, kwargs)
        reuse_context = _cache_reuse_context(kwargs.get("metadata"))
        if reuse_context is not None:
            admission = self._authorize_reuse(
                reuse_context,
                cache_key=cache_key,
                metadata=kwargs.get("metadata"),
            )
            if admission is None:
                _record_cache_skip(self._cache, "reuse_authorization_missing")
                return await self._generate_uncached(args, kwargs, request_digest=cache_key)
            scope_key, request_digest = admission
        else:
            scope_key = self._ordinary_scope_key()
            request_digest = cache_key

        internal_cache_key = hashlib.sha256(
            json.dumps(
                [cache_key, scope_key, request_digest], separators=(",", ":"), sort_keys=True
            ).encode()
        ).hexdigest()
        attempt_id = f"cache-attempt:{uuid.uuid4().hex}"
        registration = self._cache_reuse_owner.register_request(
            scope_key, request_digest, attempt_id
        )
        self._cache_reuse_owner.bind_request_key(registration, internal_cache_key)
        cached = self._cache.get(internal_cache_key)
        if cached is not None:
            logger.debug("Prompt cache hit model={} key={}", self._model, cache_key[:12])
            if isinstance(cached, GatewayLLMResponse):
                return self._reuse_response(
                    cached, cache_key=internal_cache_key, request_digest=request_digest
                )
            return cached

        provider_kwargs = _provider_kwargs(kwargs)
        flight = self._inflight.get(internal_cache_key)
        is_owner = flight is None
        if is_owner:
            self._cache_reuse_owner.dispatch(registration, attempt_id)
            producer_event_id = f"llm-provider:{uuid.uuid4().hex}"
            owner_task = asyncio.create_task(
                self._produce(
                    internal_cache_key,
                    args,
                    provider_kwargs,
                    request_digest=request_digest,
                    scope_key=scope_key,
                    producer_attempt_id=attempt_id,
                    producer_event_id=producer_event_id,
                )
            )
            flight = _CacheFlight(
                task=owner_task,
                request_digest=request_digest,
                scope_key=scope_key,
                owner_registration=registration,
                registrations=[registration],
                producer_attempt_id=attempt_id,
                origin_event_id=producer_event_id,
                cache_key=internal_cache_key,
            )
            self._inflight[internal_cache_key] = flight
            owner_task.add_done_callback(_consume_task_exception)
        else:
            self._cache_reuse_owner.join(
                registration,
                scope_key,
                request_digest,
                internal_cache_key,
                attempt_id,
            )
            flight.registrations.append(registration)

        response = await asyncio.shield(flight.task)
        if is_owner:
            return response

        # Followers receive a detached cache snapshot and the same provenance
        # marker as an ordinary cache hit.  They must not share the producer's
        # mutable response object or charge LLM-01 accounting as a miss.
        cached = self._cache.get(internal_cache_key)
        if cached is not None:
            if isinstance(cached, GatewayLLMResponse):
                return self._reuse_response(
                    cached,
                    cache_key=internal_cache_key,
                    request_digest=request_digest,
                    origin_event_id=flight.origin_event_id,
                    outcome=flight.outcome,
                )
            return cached
        if isinstance(response, GatewayLLMResponse):
            return self._reuse_response(
                response,
                cache_key=internal_cache_key,
                request_digest=request_digest,
                origin_event_id=flight.origin_event_id,
                outcome=flight.outcome,
            )
        return response

    def _ordinary_scope_key(self) -> tuple[str, ...]:
        try:
            from polisyos.core.security.tenant_context import get_current_access_scope_or_none

            scope = get_current_access_scope_or_none()
        except Exception:
            scope = None
        if scope is None:
            return ("ordinary", "anonymous")
        actor = scope.spiffe_id or scope.user_sub
        return ("ordinary", scope.tenant_id, scope.cell_id or "", actor)

    def _authorize_reuse(
        self, context: dict[str, Any], *, cache_key: str, metadata: Any
    ) -> tuple[tuple[str, ...], str] | None:
        authorizer = self._cache_reuse_authorizer
        authorize = getattr(authorizer, "authorize_reuse", None)
        if not callable(authorize):
            return None
        raw = metadata.get("cache_reuse") if isinstance(metadata, Mapping) else None
        snapshot = raw.get("snapshot") if isinstance(raw, Mapping) else None
        if not isinstance(snapshot, Mapping):
            return None
        try:
            from polisyos.core.security.tenant_context import get_current_access_scope_or_none

            principal = get_current_access_scope_or_none()
        except Exception:
            principal = None
        if principal is None:
            return None
        actor_id = principal.spiffe_id or principal.user_sub
        tenant = str(raw.get("tenant", ""))
        scope = str(raw.get("scope", ""))
        if tenant != principal.tenant_id or not actor_id or not scope:
            return None
        evidence = (
            CacheReuseEvidence(
                ref=str(snapshot.get("ref", "")),
                version=str(snapshot.get("version", "")),
                immutable=snapshot.get("immutable") is True,
                content=bytes(snapshot.get("content", b"")),
                content_hash=str(snapshot.get("content_hash", "")),
            ),
        )
        if (
            not evidence[0].ref
            or not evidence[0].version
            or not evidence[0].immutable
            or evidence[0].content_hash
            != "sha256:" + hashlib.sha256(evidence[0].content).hexdigest()
        ):
            return None
        request = CacheReuseRequest(
            actor_id=actor_id,
            tenant=tenant,
            scope=scope,
            purpose="llm_snapshot_reuse",
            model=self._model,
            parameters_digest=cache_key,
            evidence=evidence,
        )
        try:
            decision = authorize(request)
        except Exception:
            return None
        if (
            not isinstance(decision, CacheReuseDecision)
            or not decision.issuer
            or not decision.epoch
        ):
            return None
        if (
            decision.actor_id != request.actor_id
            or decision.tenant != request.tenant
            or decision.scope != request.scope
            or decision.purpose != request.purpose
            or decision.model != request.model
            or decision.parameters_digest != request.parameters_digest
            or decision.evidence != request.evidence
        ):
            return None
        scope_key = (
            decision.issuer,
            decision.epoch,
            decision.actor_id,
            decision.tenant,
            decision.scope,
            decision.purpose,
            str(raw.get("purpose", "")),
            decision.model,
            decision.parameters_digest,
            *tuple(item.content_hash for item in decision.evidence),
        )
        return scope_key, request.parameters_digest

    def _reuse_response(
        self,
        response: GatewayLLMResponse,
        *,
        cache_key: str,
        request_digest: str,
        origin_event_id: str | None = None,
        outcome: _CacheFlightOutcome | None = None,
    ) -> GatewayLLMResponse:
        if not isinstance(response, GatewayLLMResponse):
            return response
        origin = origin_event_id or response.producer_event_id or response.request_id
        origin = origin or f"legacy-origin:{uuid.uuid4().hex}"
        _mark_cache_response(response, status="hit", cache_key=cache_key)
        return _CacheReuseGatewayResponse(
            response,
            cache_key=cache_key,
            owner=self._cache_reuse_owner,
            request_digest=request_digest,
            origin_event_id=origin,
            outcome=outcome,
        )

    async def _produce(
        self,
        cache_key: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        request_digest: str,
        scope_key: tuple[str, ...],
        producer_attempt_id: str,
        producer_event_id: str,
    ) -> Any:
        """Produce and publish one cache miss, always releasing its flight."""

        current_task = asyncio.current_task()
        flight = self._inflight.get(cache_key)
        intent_started = False
        try:
            if self._producer_begin_hook is not None:
                await _maybe_await(
                    self._producer_begin_hook(
                        producer_event_id, request_digest, getattr(self._client, "provider", None)
                    )
                )
                intent_started = True
            response = await self._call_provider(args, kwargs)
            if isinstance(response, GatewayLLMResponse):
                response.producer_event_id = producer_event_id
                _mark_cache_response(response, status="miss", cache_key=cache_key)
            if self._producer_settle_hook is not None:
                settlement = await _maybe_await(
                    self._producer_settle_hook(producer_event_id, request_digest, response)
                )
                if isinstance(response, GatewayLLMResponse):
                    response.producer_settlement = settlement
            self._cache.put(cache_key, response, ttl_s=self._ttl_s)
            logger.debug("Prompt cache miss model={} key={}", self._model, cache_key[:12])
            if flight is not None:
                flight.outcome = self._cache_reuse_owner.settle_flight(
                    registrations=tuple(flight.registrations),
                    cache_key=cache_key,
                    request_digest=request_digest,
                    producer_attempt_id=producer_attempt_id,
                    terminal="success",
                    origin_event_id=producer_event_id,
                )
            return response
        except TimeoutError:
            if intent_started and self._producer_unknown_hook is not None:
                await _maybe_await(
                    self._producer_unknown_hook(producer_event_id, request_digest, TimeoutError())
                )
            if flight is not None:
                self._cache_reuse_owner.settle_flight(
                    registrations=tuple(flight.registrations),
                    cache_key=cache_key,
                    request_digest=request_digest,
                    producer_attempt_id=producer_attempt_id,
                    terminal="deadline",
                )
            raise
        except BaseException as exc:
            if intent_started and self._producer_unknown_hook is not None:
                await _maybe_await(
                    self._producer_unknown_hook(producer_event_id, request_digest, exc)
                )
            if flight is not None:
                self._cache_reuse_owner.settle_flight(
                    registrations=tuple(flight.registrations),
                    cache_key=cache_key,
                    request_digest=request_digest,
                    producer_attempt_id=producer_attempt_id,
                    terminal="cancelled" if asyncio.current_task().cancelling() else "error",
                )
            raise
        finally:
            if (
                self._inflight.get(cache_key) is flight
                and flight is not None
                and flight.task is current_task
            ):
                self._inflight.pop(cache_key, None)

    async def _call_provider(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        """Run one provider call under the configured in-flight deadline."""

        provider_call = _maybe_await(self._client.generate(*args, **kwargs))
        timeout = _coerce_timeout(kwargs.get("timeout")) or self._inflight_timeout_s
        if timeout is None:
            return await provider_call
        return await asyncio.wait_for(provider_call, timeout=timeout)


def _normalize_prompt_call(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Collapse an equivalent positional/named prompt pair before forwarding."""

    if len(args) > 1:
        raise TypeError("generate() accepts at most one positional prompt")
    normalized_kwargs = dict(kwargs)
    if not args or "prompt" not in normalized_kwargs:
        return args, normalized_kwargs
    if args[0] != normalized_kwargs["prompt"]:
        raise TypeError("generate() received conflicting prompt values")
    normalized_kwargs["prompt"] = args[0]
    return (), normalized_kwargs


def _mark_cache_response(
    response: GatewayLLMResponse,
    *,
    status: str,
    cache_key: str,
) -> None:
    """Attach cache provenance even when the provider returned no raw payload."""

    if response.raw is None:
        response.raw = {}
    marker = response.raw.setdefault("_polisyos_cache", {})
    if not isinstance(marker, dict):
        marker = {}
        response.raw["_polisyos_cache"] = marker
    marker.update(
        {
            "status": status,
            "cache_key": cache_key,
            "provider_call": status == "miss",
            "usage_origin": "provider",
        }
    )


def _cache_skip_reason(
    *,
    model: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> str | None:
    del model
    if len(args) > 1:
        return "unsupported_positional_call"
    if kwargs.get("tools"):
        return "tools_present"
    if kwargs.get("tool_choice") is not None:
        return "tool_choice_present"
    if bool(kwargs.get("stream")):
        return "streaming_call"
    temperature = kwargs.get("temperature")
    if temperature is not None:
        try:
            if float(temperature) != 0.0:
                return "non_deterministic_temperature"
        except (TypeError, ValueError):
            return "non_deterministic_temperature"
    metadata = kwargs.get("metadata")
    reuse_context = _cache_reuse_context(metadata)
    if isinstance(metadata, Mapping):
        if metadata.get("cacheable") is False:
            return "cache_disabled_by_metadata"
        if "cache_reuse" in metadata and reuse_context is None:
            return "invalid_cache_reuse_context"
        if any(
            key in metadata
            for key in (
                "retrieval_freshness",
                "retrieved_at",
                "freshness_deadline",
            )
        ):
            return "retrieval_freshness_guard"
    text_blob = stable_json_dumps(
        {
            "prompt": args[0] if args else kwargs.get("prompt") or "",
            "system": kwargs.get("system") or "",
            "user": kwargs.get("user") or "",
            "messages": kwargs.get("messages") or [],
        },
        ensure_ascii=True,
        sort_keys=True,
    ).lower()
    if (
        any(
            marker in text_blob
            for marker in (
                "http://",
                "https://",
                "fetched_at",
                "retrieved_at",
                "query_traces",
                "claim_supports",
                "uncertainty_notes",
                "recency_days",
            )
        )
        and reuse_context is None
    ):
        return "retrieval_freshness_guard"
    return None


def _record_cache_skip(cache: PromptCacheProtocol, reason: str) -> None:
    record = getattr(cache, "record_skip", None)
    if callable(record):
        record(reason)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _coerce_timeout(value: Any) -> float | None:
    """Return a positive timeout, treating absent/non-positive values as unset."""

    if value is None:
        return None
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return None
    return timeout if timeout > 0 else None


def _consume_task_exception(task: asyncio.Task[Any]) -> None:
    """Consume an unobserved producer exception after all waiters cancel."""

    if task.cancelled():
        return
    try:
        task.exception()
    except asyncio.CancelledError:
        return


def _provider_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Prepare provider kwargs without forwarding internal cache controls."""

    normalized = dict(kwargs)
    metadata = kwargs.get("metadata")
    if isinstance(metadata, Mapping):
        provider_metadata = {key: value for key, value in metadata.items() if key != "cacheable"}
        if "cache_reuse" in provider_metadata:
            provider_metadata = _normalize_cache_metadata(provider_metadata)
        if provider_metadata:
            normalized["metadata"] = provider_metadata
        else:
            normalized.pop("metadata", None)
    return normalized


def _cache_reuse_context(metadata: Any) -> dict[str, Any] | None:
    """Recompute and return a bounded immutable-snapshot reuse identity.

    The cache admission contract deliberately requires the actual snapshot
    bytes, their declared digest, and an explicit permission context.  A
    provider-supplied ``cacheable`` flag or a URI alone cannot establish this
    identity.  The returned value excludes bytes so it is safe for cache keys
    and provider payloads while retaining every substantive identity field.
    """

    if not isinstance(metadata, Mapping):
        return None
    raw_context = metadata.get("cache_reuse")
    if not isinstance(raw_context, Mapping):
        return None
    snapshot = raw_context.get("snapshot")
    permission = raw_context.get("permission")
    if not isinstance(snapshot, Mapping):
        return None

    content = snapshot.get("content")
    if not isinstance(content, (bytes, bytearray, memoryview)):
        return None
    content_bytes = bytes(content)
    expected_hash = "sha256:" + hashlib.sha256(content_bytes).hexdigest()
    if snapshot.get("content_hash") != expected_hash:
        return None
    if snapshot.get("immutable") is not True:
        return None

    ref = snapshot.get("ref")
    version = snapshot.get("version")
    tenant = raw_context.get("tenant")
    scope = raw_context.get("scope")
    outer_tenant = metadata.get("tenant")
    outer_scope = metadata.get("scope")
    if (outer_tenant is not None and outer_tenant != tenant) or (
        outer_scope is not None and outer_scope != scope
    ):
        return None
    purpose = raw_context.get("purpose")
    if not all(
        isinstance(value, str) and value for value in (ref, version, tenant, scope, purpose)
    ):
        return None
    # Caller-supplied permission metadata is consistency data only; the live
    # authorizer must independently bind actor, epoch, parameters and evidence.
    if permission is not None and (
        not isinstance(permission, Mapping)
        or permission.get("tenant") != tenant
        or permission.get("scope") != scope
    ):
        return None

    normalized_snapshot = {
        str(key): _normalize_cache_identity_value(value)
        for key, value in snapshot.items()
        if key != "content"
    }
    normalized_snapshot["content_hash"] = expected_hash
    normalized_permission = (
        {str(key): _normalize_cache_identity_value(value) for key, value in permission.items()}
        if isinstance(permission, Mapping)
        else None
    )
    normalized_context = {
        str(key): _normalize_cache_identity_value(value)
        for key, value in raw_context.items()
        if key not in {"snapshot", "permission"}
    }
    normalized_context["snapshot"] = normalized_snapshot
    if normalized_permission is not None:
        normalized_context["permission"] = normalized_permission
    return normalized_context


def _normalize_cache_identity_value(value: Any) -> Any:
    """Make substantive identity values deterministic without retaining bytes."""

    if isinstance(value, (bytes, bytearray, memoryview)):
        return "sha256:" + hashlib.sha256(bytes(value)).hexdigest()
    if isinstance(value, Mapping):
        return {str(key): _normalize_cache_identity_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_cache_identity_value(item) for item in value]
    return value


def _normalize_cache_metadata(value: Any) -> Any:
    """Normalize a valid reuse proof recursively, preserving other metadata."""

    if isinstance(value, Mapping):
        if "cache_reuse" in value:
            context = _cache_reuse_context(value)
            if context is not None:
                return {
                    str(key): (context if key == "cache_reuse" else _normalize_cache_metadata(item))
                    for key, item in value.items()
                }
            return {
                str(key): (
                    _normalize_invalid_reuse_context(item)
                    if key == "cache_reuse"
                    else _normalize_cache_metadata(item)
                )
                for key, item in value.items()
            }
        return {str(key): _normalize_cache_metadata(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_cache_metadata(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_cache_metadata(item) for item in value]
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "sha256:" + hashlib.sha256(bytes(value)).hexdigest()
    return value


def _normalize_invalid_reuse_context(value: Any) -> Any:
    """Strip non-JSON snapshot bytes from a rejected reuse proof."""

    if not isinstance(value, Mapping):
        return _normalize_cache_metadata(value)
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if key == "snapshot" and isinstance(item, Mapping):
            normalized[str(key)] = {
                str(snapshot_key): _normalize_cache_metadata(snapshot_value)
                for snapshot_key, snapshot_value in item.items()
                if snapshot_key != "content"
            }
        else:
            normalized[str(key)] = _normalize_cache_metadata(item)
    return normalized


def _freeze_response(response: GatewayLLMResponse) -> _SerializedGatewayResponse:
    return _SerializedGatewayResponse(
        content=response.content,
        usage_prompt_tokens=response.usage.prompt_tokens,
        usage_completion_tokens=response.usage.completion_tokens,
        usage_total_tokens=response.usage.total_tokens,
        usage_cost_usd=response.usage.cost_usd,
        model=response.model,
        provider=response.provider,
        request_id=response.request_id,
        response_headers=dict(response.response_headers) if response.response_headers else None,
        raw_json=_serialize_payload(response.raw),
        tool_calls=tuple(
            _SerializedGatewayToolCall(
                id=tool_call.id,
                name=tool_call.name,
                arguments_json=_serialize_payload(tool_call.arguments) or b"{}",
                error_envelope_json=_serialize_payload(tool_call.error_envelope),
            )
            for tool_call in (response.tool_calls or [])
        ),
        origin_event_id=response.producer_event_id,
    )


def _thaw_response(response: _SerializedGatewayResponse) -> GatewayLLMResponse:
    return GatewayLLMResponse(
        content=response.content,
        usage=GatewayUsage(
            prompt_tokens=response.usage_prompt_tokens,
            completion_tokens=response.usage_completion_tokens,
            total_tokens=response.usage_total_tokens,
            cost_usd=response.usage_cost_usd,
        ),
        model=response.model,
        provider=response.provider,
        request_id=response.request_id,
        response_headers=dict(response.response_headers) if response.response_headers else None,
        raw=_deserialize_payload(response.raw_json),
        producer_event_id=response.origin_event_id,
        tool_calls=[
            GatewayToolCall(
                id=tool_call.id,
                name=tool_call.name,
                arguments=_deserialize_payload(tool_call.arguments_json) or {},
                error_envelope=_deserialize_payload(tool_call.error_envelope_json),
            )
            for tool_call in response.tool_calls
        ]
        or None,
    )


def _serialize_payload(value: object | None) -> bytes | None:
    if value is None:
        return None
    normalized = to_python_data(value, sort_keys=False, unsupported="string")
    if orjson is not None:
        return orjson.dumps(normalized)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _deserialize_payload(payload: bytes | None) -> Any:
    if payload is None:
        return None
    if orjson is not None:
        return orjson.loads(payload)
    return json.loads(payload.decode("utf-8"))


def _sanitize_cache_metadata(value: Any) -> Any:
    normalized = to_python_data(_normalize_cache_metadata(value), sort_keys=True)
    return _strip_volatile_cache_metadata(normalized)


def _strip_volatile_cache_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for raw_key, raw_item in value.items():
            key = str(raw_key)
            key_lower = key.lower()
            if _is_volatile_cache_metadata_key(key_lower):
                continue
            sanitized[key] = _strip_volatile_cache_metadata(raw_item)
        return sanitized
    if isinstance(value, list):
        return [_strip_volatile_cache_metadata(item) for item in value]
    return value


def _is_volatile_cache_metadata_key(key: str) -> bool:
    if key in _VOLATILE_CACHE_METADATA_KEYS:
        return True
    return key.endswith(_VOLATILE_CACHE_METADATA_SUFFIXES)


__all__ = [
    "CachingLLMClient",
    "InMemoryPromptCache",
    "PromptCacheProtocol",
    "PromptCacheTelemetry",
    "compute_cache_key",
]
