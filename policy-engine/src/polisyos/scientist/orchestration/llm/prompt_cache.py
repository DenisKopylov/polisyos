"""Prompt-level response cache for LLM calls."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import math
import threading
import time
import uuid
import weakref
from collections import OrderedDict
from collections.abc import Callable, Mapping
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Any, Protocol

from polisyos.common.logger import get_logger
from polisyos.common.serialization import stable_json_dumps, to_python_data
from polisyos.core.llm import LLMSettlementOwnershipError
from polisyos.core.llm.cache_settlement import (
    CacheFlightOutcome,
    CacheFlightRegistration,
    CacheSettlementSession,
    bind_cache_settlement_client,
    cache_response_digest,
    cache_response_projection_bytes,
    session_for_cache_client,
)

from .gateway_client import GatewayLLMResponse, GatewayToolCall, GatewayUsage
from .prepared_request import (
    PreparedCallValues,
    PreparedLLMRequest,
    PreparedLLMResult,
    prepare_call_values,
    prepare_provider_call,
    thaw_wire_object,
)

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
class _SerializedGatewayResponse:
    payload_json: bytes


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
class CacheReusePrincipal:
    """Authenticated identity copied from the live control-job execution scope."""

    actor_id: str
    tenant: str
    scope: str

    def __post_init__(self) -> None:
        """Reject incomplete identities before they reach the cache owner."""
        if any(
            type(value) is not str or not value or value != value.strip()
            for value in (self.actor_id, self.tenant, self.scope)
        ):
            raise ValueError("cache_reuse_principal_incomplete")


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


class CacheReuseGuard(Protocol):
    """Run one synchronous reuse operation under its live owner fence."""

    def __call__[T](self, operation: Callable[[], T]) -> T: ...


@dataclass(frozen=True, slots=True)
class _CacheAdmission:
    response: GatewayLLMResponse | None
    cache_key: str
    scope_key: tuple[str, ...]
    request_digest: str
    publication_revision: int


def _unfenced_cache_operation[T](operation: Callable[[], T]) -> T:
    return operation()


@dataclass(slots=True)
class _CacheFlight:
    task: asyncio.Task[Any]
    result: Future[Any]
    request_digest: str
    scope_key: tuple[str, ...]
    owner_registration: CacheFlightRegistration
    registrations: list[CacheFlightRegistration]
    producer_attempt_id: str
    origin_event_id: str
    cache_key: str
    outcome: CacheFlightOutcome | None = None
    snapshot: _SerializedGatewayResponse | None = None
    waiters: int = 0
    released: bool = False


@dataclass(slots=True)
class _SharedCacheState:
    lock: Any = field(default_factory=threading.RLock)
    inflight: dict[str, _CacheFlight] = field(default_factory=dict)
    publication_revision: int = 0


_SHARED_CACHE_STATES_LOCK = threading.RLock()
_SHARED_CACHE_STATES: dict[int, tuple[weakref.ReferenceType[object], _SharedCacheState]] = {}


def _shared_cache_state(cache: object) -> _SharedCacheState:
    cache_id = id(cache)
    with _SHARED_CACHE_STATES_LOCK:
        current = _SHARED_CACHE_STATES.get(cache_id)
        if current is not None and current[0]() is cache:
            return current[1]
        state = _SharedCacheState()

        def discard(reference: weakref.ReferenceType[object]) -> None:
            with _SHARED_CACHE_STATES_LOCK:
                current = _SHARED_CACHE_STATES.get(cache_id)
                if current is not None and current[0] is reference:
                    del _SHARED_CACHE_STATES[cache_id]

        _SHARED_CACHE_STATES[cache_id] = (weakref.ref(cache, discard), state)
        return state


class _CacheReuseGatewayResponse(GatewayLLMResponse):
    """Gateway response carrying cache-owned provenance outside provider raw data."""

    __slots__ = (
        "__weakref__",
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
        session: CacheSettlementSession,
        request_digest: str,
        origin_event_id: str,
        outcome: CacheFlightOutcome | None = None,
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
        self._polisyos_reuse_provenance = session.issue_reuse_attestation(
            response=self,
            cache_key=cache_key,
            request_digest=request_digest,
            reuse_event_id=self._polisyos_reuse_event_id,
            origin_event_id=origin_event_id,
            outcome=outcome,
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
                self._forget_origin(cache_key)
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
                evicted_key, _ = self._store.popitem(last=False)
                self._forget_origin(evicted_key)
                self._telemetry.evictions += 1

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)

    def clear(self) -> None:
        with self._lock:
            for cache_key in self._store:
                self._forget_origin(cache_key)
            self._store.clear()
            self._telemetry = PromptCacheTelemetry()

    def _forget_origin(self, cache_key: str) -> None:
        session = session_for_cache_client(self)
        if session is not None:
            session.forget_cached_key(cache_key)

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


def _prepared_cache_request_digest(
    *,
    model: str,
    provider_route: str,
    prepared: PreparedLLMRequest,
    caller_snapshot: bytes,
    metadata: Any,
) -> str:
    payload = {
        "model": model,
        "provider_route": provider_route,
        "caller_input": thaw_wire_object(caller_snapshot),
        "prepared_dispatch": thaw_wire_object(prepared.identity),
        # Physical-only calls have no cache equivalence claim. In particular,
        # do not serialize/coerce an opaque Python caller's metadata for one.
        "private_cache_scope": _sanitize_cache_metadata(metadata) if prepared.reusable else None,
    }
    return hashlib.sha256(stable_json_dumps(payload).encode()).hexdigest()


@dataclass(slots=True)
class _PreparedCacheBinding:
    lock: Any = field(default_factory=threading.Lock)
    owner: weakref.ReferenceType[Any] | None = None
    used: bool = False


@dataclass(frozen=True, slots=True, eq=False)
class PreparedCacheRequest:
    """One detached cache call bound to its actual provider preparation and one wrapper.

    Construct through `prepare_cached_request`. Pre-bound wrappers use the ordinary
    call contract; live scoped clients prepare internally before admission. The
    exact native/control tree is immutable and type-preserving. Opaque calls
    cannot be pre-bound. The provider executor and its retry nonce
    are consumed once, including cache-hit calls that do not dispatch physically.
    """

    client: object = field(repr=False, compare=False)
    model: str
    provider_route: str
    provider_request: PreparedLLMRequest = field(repr=False, compare=False)
    caller_snapshot: bytes = field(repr=False)
    _call: PreparedCallValues = field(repr=False, compare=False)
    _bindable: bool = field(repr=False)
    _binding: _PreparedCacheBinding = field(
        default_factory=_PreparedCacheBinding, repr=False, compare=False
    )

    @property
    def request_digest(self) -> str:
        """Return the cache owner's exact digest for this ordinary prepared call."""
        return _prepared_cache_request_digest(
            model=self.model,
            provider_route=self.provider_route,
            prepared=self.provider_request,
            caller_snapshot=self.caller_snapshot,
            metadata=self.call_values()[1].get("metadata"),
        )

    def call_values(self) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """Copy exact native values or retain original opaque physical inputs."""
        return self._call.call_values()

    def _bind(self, client: object) -> None:
        if not self._bindable:
            raise ValueError("prepared_cache_request_input_not_bound")
        with self._binding.lock:
            if self._binding.owner is not None:
                raise ValueError("prepared_cache_request_already_bound")
            self._binding.owner = weakref.ref(client)

    def _consume(self, client: object, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        args, kwargs = _normalize_prompt_call(args, kwargs)
        invoked = prepare_call_values(args, kwargs)
        if not invoked.exact or invoked.identity != self._call.identity:
            raise ValueError("prepared_cache_request_call_mismatch")
        with self._binding.lock:
            if self._binding.owner is None or self._binding.owner() is not client:
                raise ValueError("prepared_cache_request_owner_mismatch")
            if self._binding.used:
                raise ValueError("prepared_cache_request_already_consumed")
            self._binding.used = True


def prepare_cached_request(
    client: object,
    *,
    model: str,
    provider_route: str | None = None,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any],
) -> PreparedCacheRequest:
    """Prepare one complete cache call before choosing a shared cache resource.

    Digest consumers and the cache executor use this same actual provider plan.
    Exact input equality uses a lossless Python value snapshot, independently
    of cache/evidence normalization. Only the actual Gateway owns JSON wire
    projection. Opaque Python calls stay physical-only with original objects.
    """
    args, kwargs = _normalize_prompt_call(args, kwargs)
    call = prepare_call_values(args, kwargs)
    has_prepared_owner = callable(getattr(client, "prepare_cache_request", None))
    provider_args, provider_kwargs = call.call_values() if has_prepared_owner else (args, kwargs)
    prepared, caller_snapshot = prepare_provider_call(
        client, provider_args, _provider_kwargs(provider_kwargs)
    )
    if not call.exact:
        prepared = PreparedLLMRequest(prepared.identity, prepared.execute, False)
    route = provider_route if provider_route is not None else getattr(client, "provider", None)
    if route is not None and (type(route) is not str or not route or route != route.strip()):
        raise ValueError("cache_provider_route_must_be_established_text")
    return PreparedCacheRequest(
        client,
        model,
        route or "unknown",
        prepared,
        caller_snapshot,
        call,
        call.exact and has_prepared_owner,
    )


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
        reuse_principal: CacheReusePrincipal | None = None,
        reuse_context: Mapping[str, Any] | None = None,
        require_reuse_authorization: bool = False,
        reuse_guard: CacheReuseGuard | None = None,
        origin_retention_limit: int = 128,
        provider_route: str | None = None,
        prepared_request: PreparedCacheRequest | None = None,
    ) -> None:
        self._client = client
        self._cache = cache
        self._model = model
        route = provider_route if provider_route is not None else getattr(client, "provider", None)
        if route is not None and (type(route) is not str or not route or route != route.strip()):
            raise ValueError("cache_provider_route_must_be_established_text")
        self._provider_route = route or "unknown"
        if prepared_request is not None:
            # Public pre-bound plans name an ordinary call's complete identity.
            # Scoped clients retain their live admission/injection path below.
            if require_reuse_authorization:
                raise ValueError("prepared_cache_request_requires_ordinary_binding")
            if type(prepared_request) is not PreparedCacheRequest or (
                prepared_request.client is not client
                or prepared_request.model != model
                or prepared_request.provider_route != self._provider_route
            ):
                raise ValueError("prepared_cache_request_configuration_mismatch")
            prepared_request._bind(self)
        self._prepared_request = prepared_request
        self._ttl_s = max(float(ttl_s), 0.0)
        configured_timeout = inflight_timeout_s
        if configured_timeout is None:
            configured_timeout = getattr(client, "timeout_s", None)
        self._inflight_timeout_s = _coerce_timeout(configured_timeout)
        self._shared_cache_state = _shared_cache_state(cache)
        # Legacy private inspection sees the actual cache-owned flights.
        self._inflight = self._shared_cache_state.inflight
        self._cache_reuse_authorizer = reuse_authorizer
        if reuse_principal is not None and type(reuse_principal) is not CacheReusePrincipal:
            raise TypeError("cache_reuse_principal_must_be_typed")
        if reuse_context is not None and not isinstance(reuse_context, Mapping):
            raise TypeError("cache_reuse_context_must_be_mapping")
        if type(require_reuse_authorization) is not bool:
            raise TypeError("cache_reuse_authorization_requirement_must_be_bool")
        self._cache_reuse_principal = reuse_principal
        self._trusted_reuse_context = dict(reuse_context) if reuse_context is not None else None
        self._require_reuse_authorization = require_reuse_authorization
        self._reuse_guard = reuse_guard
        # Provenance belongs to the configured cache lifetime, not to this
        # request's provider wrapper.  Wrappers sharing the exact cache can
        # therefore verify an origin retained by an earlier wrapper without
        # copying or re-attesting that origin.
        self._cache_settlement_session = bind_cache_settlement_client(
            cache, self, retention_limit=origin_retention_limit
        )
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

    def _request_digest(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        prepared: PreparedLLMRequest,
        caller_snapshot: bytes,
    ) -> str:
        """Bind the same detached call and selected dispatch that will execute."""
        del args
        return _prepared_cache_request_digest(
            model=self._model,
            provider_route=self._provider_route,
            prepared=prepared,
            caller_snapshot=caller_snapshot,
            metadata=kwargs.get("metadata"),
        )

    async def _generate_uncached(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        request_digest: str | None = None,
        provider_kwargs: dict[str, Any] | None = None,
        prepared: PreparedLLMRequest | None = None,
        caller_snapshot: bytes | None = None,
    ) -> Any:
        """Run a non-reusable provider call through the same settlement hooks."""

        begin = self._producer_begin_hook
        settle = self._producer_settle_hook
        unknown = self._producer_unknown_hook
        event_id = f"llm-provider:{uuid.uuid4().hex}"
        if prepared is None or caller_snapshot is None:
            prepared, caller_snapshot = prepare_provider_call(
                self._client,
                args,
                provider_kwargs if provider_kwargs is not None else _provider_kwargs(kwargs),
            )
        digest = request_digest or self._request_digest(
            args, kwargs, prepared=prepared, caller_snapshot=caller_snapshot
        )
        intent_started = False
        try:
            if begin is not None:
                await _maybe_await(begin(event_id, digest, getattr(self._client, "provider", None)))
                intent_started = True
            response = (await prepared.execute()).response
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
        call = self._prepared_request
        if call is not None:
            call._consume(self, args, kwargs)
        else:
            call = prepare_cached_request(
                self._client,
                model=self._model,
                provider_route=self._provider_route,
                args=args,
                kwargs=kwargs,
            )
        args, kwargs = call.call_values()
        # Exact native controls and the provider preparation are separate from
        # cache/evidence normalization. Opaque providers preserve original objects.
        prepared, caller_snapshot = call.provider_request, call.caller_snapshot
        provider_kwargs = _provider_kwargs(kwargs)
        if self._require_reuse_authorization and self._reuse_guard is None:
            raise LLMSettlementOwnershipError("live_reuse_owner_unavailable")
        if self._require_reuse_authorization:
            self._reuse_guard(lambda: None)
            authorize = getattr(self._cache_reuse_authorizer, "authorize_reuse", None)
            principal = self._cache_reuse_principal
            if not callable(authorize) or principal is None or self._trusted_reuse_context is None:
                _record_cache_skip(self._cache, "reuse_authorization_unavailable")
                return await self._generate_uncached(
                    args,
                    kwargs,
                    provider_kwargs=provider_kwargs,
                    prepared=prepared,
                    caller_snapshot=caller_snapshot,
                )
            metadata = kwargs.get("metadata")
            trusted_metadata = dict(metadata) if isinstance(metadata, Mapping) else {}
            # Preserve every caller-selected wire metadata value in identity,
            # including names that the private authorization metadata replaces.
            trusted_metadata["provider_metadata"] = provider_kwargs.get("metadata")
            trusted_metadata["tenant"] = principal.tenant
            trusted_metadata["scope"] = principal.scope
            trusted_metadata["cache_reuse"] = self._trusted_reuse_context
            kwargs["metadata"] = trusted_metadata
        if not prepared.reusable:
            _record_cache_skip(self._cache, "prepared_dispatch_not_established")
            return await self._generate_uncached(
                args,
                kwargs,
                provider_kwargs=provider_kwargs,
                prepared=prepared,
                caller_snapshot=caller_snapshot,
            )
        reason = _cache_skip_reason(
            model=self._model,
            args=args,
            kwargs=kwargs,
            strict_reuse=self._require_reuse_authorization,
            deterministic_default=self._has_deterministic_provider_default(),
        )
        if reason is not None:
            _record_cache_skip(self._cache, reason)
            return await self._generate_uncached(
                args,
                kwargs,
                provider_kwargs=provider_kwargs,
                prepared=prepared,
                caller_snapshot=caller_snapshot,
            )

        cache_key = self._request_digest(
            args, kwargs, prepared=prepared, caller_snapshot=caller_snapshot
        )
        reuse_context = _cache_reuse_context(kwargs.get("metadata"))
        guard = self._reuse_guard or _unfenced_cache_operation

        def admit_lookup() -> _CacheAdmission | None:
            if reuse_context is not None:
                admission = self._authorize_reuse(
                    reuse_context, cache_key=cache_key, metadata=kwargs.get("metadata")
                )
                if admission is None:
                    return None
                scope_key, request_digest = admission
            else:
                scope_key = self._ordinary_scope_key()
                request_digest = cache_key
            internal_cache_key = hashlib.sha256(
                json.dumps(
                    [cache_key, scope_key, request_digest], separators=(",", ":"), sort_keys=True
                ).encode()
            ).hexdigest()
            with self._shared_cache_state.lock:
                revision = self._shared_cache_state.publication_revision
            cached = self._cache.get(internal_cache_key)
            with self._shared_cache_state.lock:
                unchanged = revision == self._shared_cache_state.publication_revision
            if cached is not None and unchanged:
                try:
                    response = self._reuse_response(
                        cached, cache_key=internal_cache_key, request_digest=request_digest
                    )
                    return _CacheAdmission(
                        response, internal_cache_key, scope_key, request_digest, revision
                    )
                except (TypeError, ValueError):
                    _record_cache_skip(self._cache, "cache_origin_mismatch")
            return _CacheAdmission(None, internal_cache_key, scope_key, request_digest, revision)

        # Guard errors, including actual dependency timeouts and an absent current
        # lease, propagate. They never authorize replacement physical work.
        admitted = guard(admit_lookup)
        if admitted is None:
            _record_cache_skip(self._cache, "reuse_authorization_unavailable")
            return await self._generate_uncached(
                args,
                kwargs,
                request_digest=cache_key,
                provider_kwargs=provider_kwargs,
                prepared=prepared,
                caller_snapshot=caller_snapshot,
            )
        if admitted.response is not None:
            try:
                return self._verified_reuse_response(admitted.response, request_digest=cache_key)
            except (TypeError, ValueError):
                _record_cache_skip(self._cache, "cache_origin_mismatch")
                return await self._generate_uncached(
                    args,
                    kwargs,
                    request_digest=cache_key,
                    provider_kwargs=provider_kwargs,
                    prepared=prepared,
                    caller_snapshot=caller_snapshot,
                )
        try:
            internal_cache_key = admitted.cache_key
            scope_key = admitted.scope_key
            request_digest = admitted.request_digest
            flight_key = internal_cache_key
            with self._shared_cache_state.lock:
                if self._shared_cache_state.publication_revision != admitted.publication_revision:
                    raise ValueError("cache_head_changed_during_admission")
                self._cache_settlement_session.forget_cached_key(internal_cache_key)
                attempt_id = f"cache-attempt:{uuid.uuid4().hex}"
                registration = self._cache_settlement_session.register_request(
                    scope_key, request_digest, attempt_id
                )
                self._cache_settlement_session.bind_request_key(registration, internal_cache_key)
                flight = self._inflight.get(flight_key)
                is_owner = flight is None
                if is_owner:
                    self._cache_settlement_session.dispatch(registration, attempt_id)
                    producer_event_id = f"llm-provider:{uuid.uuid4().hex}"
                    owner_task = asyncio.create_task(
                        self._produce(
                            internal_cache_key,
                            prepared,
                            timeout=_coerce_timeout(provider_kwargs.get("timeout")),
                            request_digest=request_digest,
                            scope_key=scope_key,
                            producer_attempt_id=attempt_id,
                            producer_event_id=producer_event_id,
                        )
                    )
                    flight = _CacheFlight(
                        task=owner_task,
                        result=Future(),
                        request_digest=request_digest,
                        scope_key=scope_key,
                        owner_registration=registration,
                        registrations=[registration],
                        producer_attempt_id=attempt_id,
                        origin_event_id=producer_event_id,
                        cache_key=internal_cache_key,
                    )
                    self._inflight[flight_key] = flight
                    owner_task.add_done_callback(
                        lambda task: self._settle_shared_flight_result(flight, task)
                    )
                    owner_task.add_done_callback(_consume_task_exception)
                else:
                    self._cache_settlement_session.join(
                        registration, scope_key, request_digest, internal_cache_key, attempt_id
                    )
                    flight.registrations.append(registration)
                flight.waiters += 1

        except (OSError, RuntimeError, TypeError, ValueError):
            _record_cache_skip(self._cache, "reuse_admission_unavailable")
            return await self._generate_uncached(
                args,
                kwargs,
                request_digest=cache_key,
                provider_kwargs=provider_kwargs,
                prepared=prepared,
                caller_snapshot=caller_snapshot,
            )

        try:
            response = await asyncio.shield(asyncio.wrap_future(flight.result))
            if is_owner:
                return response

            # Every follower is a new reuse emission. Re-admit on the owner
            # worker after waiting; only that operation may issue its response.
            def admit_follower() -> GatewayLLMResponse | None:
                if reuse_context is not None and self._authorize_reuse(
                    reuse_context, cache_key=cache_key, metadata=kwargs.get("metadata")
                ) != (scope_key, request_digest):
                    return None
                with self._shared_cache_state.lock:
                    if flight.snapshot is None:
                        raise ValueError("cache_flight_response_unattested")
                    return self._reuse_response(
                        _thaw_response(flight.snapshot),
                        cache_key=internal_cache_key,
                        request_digest=request_digest,
                        origin_event_id=flight.origin_event_id,
                        outcome=flight.outcome,
                    )

            candidate = guard(admit_follower)
            if candidate is not None:
                try:
                    return self._verified_reuse_response(candidate, request_digest=cache_key)
                except (TypeError, ValueError):
                    _record_cache_skip(self._cache, "cache_origin_mismatch")
        finally:
            with self._shared_cache_state.lock:
                flight.waiters -= 1
                self._release_completed_flight(flight)
        return await self._generate_uncached(
            args,
            kwargs,
            request_digest=cache_key,
            provider_kwargs=provider_kwargs,
            prepared=prepared,
            caller_snapshot=caller_snapshot,
        )

    def _has_deterministic_provider_default(self) -> bool:
        """Recognize only the existing exact built-in deterministic simulator."""
        from .simulated_gateway import SimulatedGatewayLLMClient

        return type(self._client) is SimulatedGatewayLLMClient

    def _verified_reuse_response(
        self, response: GatewayLLMResponse, *, request_digest: str
    ) -> GatewayLLMResponse:
        """Require Core's exact response proof on every hit emission."""
        if not isinstance(response, GatewayLLMResponse):
            raise ValueError("cache_response_untyped")
        evidence = self._cache_settlement_session.verify_reuse_attestation(
            getattr(response, "_polisyos_reuse_provenance", None), response
        )
        if evidence is None or evidence.request_digest != request_digest:
            raise ValueError("cache_response_attestation_invalid")
        expected_key = hashlib.sha256(
            json.dumps(
                [request_digest, evidence.scope_key, request_digest],
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        principal = self._cache_reuse_principal
        if evidence.cache_key != expected_key or (
            self._require_reuse_authorization
            and (
                principal is None
                or evidence.scope_key[2:5]
                != (principal.actor_id, principal.tenant, principal.scope)
            )
        ):
            raise ValueError("cache_response_scope_mismatch")
        return response

    def _settle_shared_flight_result(self, flight: _CacheFlight, task: asyncio.Task[Any]) -> None:
        if task.cancelled():
            flight.result.set_exception(asyncio.CancelledError())
        elif (error := task.exception()) is not None:
            flight.result.set_exception(error)
        else:
            flight.result.set_result(task.result())
        self._release_completed_flight(flight)

    def _release_completed_flight(self, flight: _CacheFlight) -> None:
        with self._shared_cache_state.lock:
            if flight.waiters or not flight.task.done() or flight.released:
                return
            self._cache_settlement_session.release_flight(
                tuple(flight.registrations), flight.outcome
            )
            flight.released = True

    def _ordinary_scope_key(self) -> tuple[str, ...]:
        try:
            from polisyos.core.security import get_current_access_scope_or_none

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
        reuse_principal = self._cache_reuse_principal
        if reuse_principal is None:
            if self._require_reuse_authorization:
                return None
            try:
                from polisyos.core.security import get_current_access_scope_or_none

                ambient_principal = get_current_access_scope_or_none()
            except Exception:
                ambient_principal = None
            if ambient_principal is None:
                return None
            actor_id = ambient_principal.spiffe_id or ambient_principal.user_sub
            tenant = str(raw.get("tenant", ""))
            scope = str(raw.get("scope", ""))
            if tenant != ambient_principal.tenant_id or not actor_id or not scope:
                return None
        else:
            actor_id = reuse_principal.actor_id
            tenant = reuse_principal.tenant
            scope = reuse_principal.scope
            if (
                tenant != str(raw.get("tenant", ""))
                or scope != str(raw.get("scope", ""))
                or not actor_id
            ):
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
        if type(decision) is not CacheReuseDecision or any(
            type(value) is not str or not value or value != value.strip()
            for value in (
                decision.issuer,
                decision.epoch,
                decision.actor_id,
                decision.tenant,
                decision.scope,
                decision.purpose,
                decision.model,
                decision.parameters_digest,
            )
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
        outcome: CacheFlightOutcome | None = None,
    ) -> GatewayLLMResponse:
        if not isinstance(response, GatewayLLMResponse):
            raise ValueError("cache_response_untyped")
        origin = origin_event_id or response.producer_event_id
        if not origin:
            raise ValueError("cache_response_origin_missing")
        # Detach the entire admitted projection before minting a response proof.
        response = _thaw_response(_freeze_response(response))
        _mark_cache_response(response, status="hit", cache_key=cache_key)
        return _CacheReuseGatewayResponse(
            response,
            cache_key=cache_key,
            session=self._cache_settlement_session,
            request_digest=request_digest,
            origin_event_id=origin,
            outcome=outcome,
        )

    async def _produce(
        self,
        cache_key: str,
        prepared: PreparedLLMRequest,
        *,
        timeout: float | None,
        request_digest: str,
        scope_key: tuple[str, ...],
        producer_attempt_id: str,
        producer_event_id: str,
    ) -> Any:
        """Produce and publish one cache miss, always releasing its flight."""

        current_task = asyncio.current_task()
        flight_key = cache_key
        flight = self._inflight.get(flight_key)
        intent_started = False
        try:
            if self._producer_begin_hook is not None:
                await _maybe_await(
                    self._producer_begin_hook(
                        producer_event_id, request_digest, getattr(self._client, "provider", None)
                    )
                )
                intent_started = True
            physical = await self._call_provider(prepared, timeout=timeout)
            response = physical.response
            cacheable = isinstance(response, GatewayLLMResponse) and prepared.admits(physical)
            if not cacheable:
                _record_cache_skip(self._cache, "effective_dispatch_changed")
            if isinstance(response, GatewayLLMResponse):
                response.producer_event_id = producer_event_id
                _mark_cache_response(
                    response, status="miss" if cacheable else "uncached", cache_key=cache_key
                )
            if self._producer_settle_hook is not None:
                settlement = await _maybe_await(
                    self._producer_settle_hook(producer_event_id, request_digest, response)
                )
                if isinstance(response, GatewayLLMResponse):
                    response.producer_settlement = settlement
            frozen = _freeze_response(response) if cacheable else None
            response_digest = (
                cache_response_digest(response)
                if isinstance(response, GatewayLLMResponse)
                else None
            )
            with self._shared_cache_state.lock:
                if flight is not None:
                    flight.outcome = self._cache_settlement_session.settle_flight(
                        registrations=tuple(flight.registrations),
                        cache_key=cache_key,
                        request_digest=request_digest,
                        producer_attempt_id=producer_attempt_id,
                        terminal="success",
                        retain_for_s=self._ttl_s if cacheable else 0,
                        origin_event_id=producer_event_id,
                        response_digest=response_digest,
                    )
                    flight.snapshot = frozen
            try:
                if cacheable:
                    self._cache.put(cache_key, response, ttl_s=self._ttl_s)
                    with self._shared_cache_state.lock:
                        self._shared_cache_state.publication_revision += 1
            except BaseException:
                self._cache_settlement_session.forget_cached_key(cache_key)
                raise
            logger.debug("Prompt cache miss model={} key={}", self._model, cache_key[:12])
            return response
        except TimeoutError:
            if intent_started and self._producer_unknown_hook is not None:
                await _maybe_await(
                    self._producer_unknown_hook(producer_event_id, request_digest, TimeoutError())
                )
            if flight is not None:
                flight.outcome = self._cache_settlement_session.settle_flight(
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
                flight.outcome = self._cache_settlement_session.settle_flight(
                    registrations=tuple(flight.registrations),
                    cache_key=cache_key,
                    request_digest=request_digest,
                    producer_attempt_id=producer_attempt_id,
                    terminal="cancelled" if asyncio.current_task().cancelling() else "error",
                )
            raise
        finally:
            if (
                self._inflight.get(flight_key) is flight
                and flight is not None
                and flight.task is current_task
            ):
                with self._shared_cache_state.lock:
                    self._inflight.pop(flight_key, None)

    async def _call_provider(
        self,
        prepared: PreparedLLMRequest,
        *,
        timeout: float | None,
    ) -> PreparedLLMResult:
        """Run the frozen provider dispatch under its in-flight deadline."""
        deadline = timeout or self._inflight_timeout_s
        if deadline is None:
            return await prepared.execute()
        return await asyncio.wait_for(prepared.execute(), timeout=deadline)


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
            "provider_call": status != "hit",
            "usage_origin": "provider",
        }
    )


def _cache_skip_reason(
    *,
    model: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    strict_reuse: bool = False,
    deterministic_default: bool = False,
) -> str | None:
    del model
    if strict_reuse and kwargs.get("seed") is not None:
        return "independent_seed"
    if len(args) > 1:
        return "unsupported_positional_call"
    if kwargs.get("tools"):
        return "tools_present"
    if kwargs.get("tool_choice") is not None:
        return "tool_choice_present"
    if bool(kwargs.get("stream")):
        return "streaming_call"
    temperature = kwargs.get("temperature")
    if temperature is None:
        if not deterministic_default:
            return "sampling_policy_not_established"
    elif type(temperature) not in (int, float) or temperature != 0:
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
    if any(
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
    ) and (strict_reuse or reuse_context is None):
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
    return _SerializedGatewayResponse(cache_response_projection_bytes(response))


def _thaw_response(response: _SerializedGatewayResponse) -> GatewayLLMResponse:
    payload = json.loads(response.payload_json)
    payload["usage"] = GatewayUsage(**payload["usage"])
    if payload.get("tool_calls") is not None:
        payload["tool_calls"] = [GatewayToolCall(**item) for item in payload["tool_calls"]]
    return GatewayLLMResponse(**payload)


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
    "PreparedCacheRequest",
    "PromptCacheProtocol",
    "PromptCacheTelemetry",
    "compute_cache_key",
    "prepare_cached_request",
]
