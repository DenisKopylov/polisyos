"""Prompt-level response cache for LLM calls."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from polisyos.common.logger import get_logger
from polisyos.common.serialization import stable_json_dumps, to_python_data
from polisyos.core.llm.response import LLMUsageStatus, extract_llm_response_data
from polisyos.core.llm.settlement import (
    LLMProducerSettlement,
    LLMSettledResponse,
    _CacheFlightRegistration,
    _CacheReuseOwner,
    _CacheReuseProvenance,
    _completion_amount,
    _current_producer_completion,
    _current_settlement_owner,
    _observe_cache_flight,
    _request_digest,
    producer_settlement,
)
from polisyos.core.security.tenant_context import get_current_access_scope_or_none

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
class CacheReuseEvidence:
    """Exact immutable evidence bytes submitted to the operational policy owner."""

    ref: str
    version: str
    content_hash: str
    content: bytes


@dataclass(frozen=True, slots=True)
class CacheReuseRequest:
    """Actual principal and exact purpose/ref/request identity requiring permission."""

    actor_id: str
    tenant: str
    scope: str
    purpose: str
    model: str
    parameters_digest: str
    evidence: tuple[CacheReuseEvidence, ...]


@dataclass(frozen=True, slots=True)
class CacheReuseDecision:
    """Versioned decision supplied by the trusted deployment permission owner."""

    issuer: str
    epoch: str
    actor_id: str
    tenant: str
    scope: str
    purpose: str
    model: str
    parameters_digest: str
    evidence: tuple[CacheReuseEvidence, ...]

    def binds(self, request: CacheReuseRequest) -> bool:
        return bool(self.issuer and self.epoch) and (
            self.actor_id,
            self.tenant,
            self.scope,
            self.purpose,
            self.model,
            self.parameters_digest,
            self.evidence,
        ) == (
            request.actor_id,
            request.tenant,
            request.scope,
            request.purpose,
            request.model,
            request.parameters_digest,
            request.evidence,
        )

    def key_payload(self) -> dict[str, Any]:
        return {
            "issuer": self.issuer,
            "epoch": self.epoch,
            "actor_id": self.actor_id,
            "tenant": self.tenant,
            "scope": self.scope,
            "purpose": self.purpose,
            "model": self.model,
            "parameters_digest": self.parameters_digest,
            "evidence": [
                {"ref": e.ref, "version": e.version, "content_hash": e.content_hash}
                for e in self.evidence
            ],
        }


class CacheReuseAuthorizer(Protocol):
    """Trusted operational owner; metadata declarations are never a decision."""

    def authorize_reuse(self, request: CacheReuseRequest) -> CacheReuseDecision | None: ...


class CacheReuseDeniedError(PermissionError):
    """The current owner decision no longer permits this reuse or flight join."""


class _ProducerGatewayResponse(GatewayLLMResponse):
    __slots__ = ("_polisyos_settlement",)

    def __init__(self, response: GatewayLLMResponse, settlement: LLMProducerSettlement) -> None:
        super().__init__(
            content=response.content,
            usage=response.usage,
            model=response.model,
            provider=response.provider,
            request_id=response.request_id,
            response_headers=response.response_headers,
            raw=response.raw,
            tool_calls=response.tool_calls,
        )
        self._polisyos_settlement = settlement


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
    usage_status: LLMUsageStatus | None = None
    cost_status: LLMUsageStatus | None = None
    tool_calls: tuple[_SerializedGatewayToolCall, ...] = ()
    settlement: LLMProducerSettlement | None = None


class _CacheReuseGatewayResponse(GatewayLLMResponse):
    """Gateway response carrying cache-owned provenance outside provider raw data."""

    __slots__ = (
        "_polisyos_cache_hit",
        "_polisyos_cache_key",
        "_polisyos_cache_reuse_provenance",
        "_polisyos_reuse_event_id",
        "_polisyos_settlement",
    )

    def __init__(
        self,
        response: GatewayLLMResponse,
        *,
        cache_key: str,
        provenance: _CacheReuseProvenance,
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
        )
        self._polisyos_settlement = producer_settlement(response)
        self._polisyos_cache_hit = True
        self._polisyos_cache_key = cache_key
        self._polisyos_reuse_event_id = provenance.reuse_event_id
        self._polisyos_cache_reuse_provenance = provenance


class PromptCacheProtocol(Protocol):
    """Protocol for prompt cache implementations."""

    def get(self, cache_key: str) -> GatewayLLMResponse | None: ...
    def put(
        self,
        cache_key: str,
        response: GatewayLLMResponse,
        ttl_s: float,
        *,
        admission_check: Callable[[], None] | None = None,
    ) -> None:
        """Check admission at the atomic storage boundary, after serialization/lock waits."""
        ...


class CacheAdmissionUnsupportedError(RuntimeError):
    """The configured cache cannot accept the required atomic admission contract."""


@dataclass(slots=True)
class _FlightObservation:
    """Written only by the actual producer, before any result emission check."""

    settlement: LLMProducerSettlement | None = None
    response: Any = None
    error: BaseException | None = None


@dataclass(frozen=True, slots=True)
class _ProducerFlight:
    task: asyncio.Task[Any]
    deadline: float | None
    request_digest: str
    scope_key: tuple[str, ...]
    producer_attempt_id: str | None
    observation: _FlightObservation
    registration: _CacheFlightRegistration | None


@dataclass(slots=True)
class _CacheParticipation:
    """Local request role; no caller or response can set this execution state."""

    cache_key: str = ""
    role: Literal["producer", "joined", "not_dispatched"] = "not_dispatched"
    flight: _ProducerFlight | None = None
    registration: _CacheFlightRegistration | None = None


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
        *,
        admission_check: Callable[[], None] | None = None,
    ) -> None:
        """Cache *response* under *cache_key* with optional TTL override."""
        effective_ttl = ttl_s if ttl_s is not None else self._default_ttl_s
        expires_at = time.monotonic() + effective_ttl
        serialized = _freeze_response(response)
        with self._lock:
            if admission_check is not None:
                admission_check()
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
        reuse_authorizer: CacheReuseAuthorizer | None = None,
    ) -> None:
        self._client = client
        self._cache = cache
        self._model = model
        self._ttl_s = max(float(ttl_s), 0.0)
        configured_timeout = inflight_timeout_s
        if configured_timeout is None:
            configured_timeout = getattr(client, "timeout_s", None)
        self._inflight_timeout_s = _coerce_timeout(configured_timeout)
        self._inflight: dict[str, _ProducerFlight] = {}
        self._reuse_authorizer = reuse_authorizer
        self._cache_reuse_owner = _CacheReuseOwner(self)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def unwrap(self) -> Any:
        return self._client

    def _reuse_admission(
        self, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> tuple[CacheReuseRequest, CacheReuseDecision] | None:
        metadata = kwargs.get("metadata")
        if not isinstance(metadata, Mapping):
            return None
        context = _cache_reuse_context(metadata)
        if context is None or self._reuse_authorizer is None:
            return None
        principal = get_current_access_scope_or_none()
        if principal is None or principal.tenant_id != context["tenant"]:
            return None
        actor = principal.user_sub or principal.spiffe_id
        if not actor:
            return None
        snapshot = metadata["cache_reuse"]["snapshot"]
        evidence = CacheReuseEvidence(
            ref=context["snapshot"]["ref"],
            version=context["snapshot"]["version"],
            content_hash=context["snapshot"]["content_hash"],
            content=bytes(snapshot["content"]),
        )
        request = CacheReuseRequest(
            actor_id=actor,
            tenant=principal.tenant_id,
            scope=context["scope"],
            purpose="llm_snapshot_reuse",
            model=self._model,
            parameters_digest=compute_cache_key(
                prompt=args[0] if args else None,
                model=self._model,
                extra_payload={k: v for k, v in kwargs.items() if k != "metadata"},
            ),
            evidence=(evidence,),
        )
        decision = self._reuse_authorizer.authorize_reuse(request)
        if not isinstance(decision, CacheReuseDecision) or not decision.binds(request):
            return None
        return request, decision

    def _require_current_reuse(
        self, admission: tuple[CacheReuseRequest, CacheReuseDecision] | None
    ) -> None:
        if admission is None:
            return
        request, admitted = admission
        current = (
            self._reuse_authorizer.authorize_reuse(request) if self._reuse_authorizer else None
        )
        if (
            current != admitted
            or not isinstance(current, CacheReuseDecision)
            or not current.binds(request)
        ):
            raise CacheReuseDeniedError("snapshot reuse permission changed before consumption")

    async def generate(self, *args: Any, **kwargs: Any) -> Any:
        owner = _current_settlement_owner()
        participation = _CacheParticipation()
        if (
            owner is not None
            and owner.flight_owner is self._cache_reuse_owner
            and owner.attempt_id
            and owner.request_digest
        ):
            participation.registration = self._cache_reuse_owner.register_request(
                owner.scope_key, owner.request_digest, owner.attempt_id
            )
        response = None
        error = None
        try:
            response = await self._generate(args, kwargs, participation)
            return response
        except BaseException as exc:
            error = exc
            raise
        finally:
            if owner is not None:
                flight = participation.flight
                _observe_cache_flight(
                    self._cache_reuse_owner,
                    registration=flight.registration if flight else participation.registration,
                    cache_key=participation.cache_key,
                    request_digest=flight.request_digest if flight else owner.request_digest or "",
                    scope_key=flight.scope_key if flight else owner.scope_key,
                    producer_attempt_id=(
                        flight.producer_attempt_id
                        if flight
                        else owner.attempt_id
                        if participation.role == "producer"
                        else None
                    ),
                    role=participation.role,
                    settlement=flight.observation.settlement
                    if flight
                    else producer_settlement(response),
                    response=flight.observation.response if flight else response,
                    error=flight.observation.error or error if flight else error,
                )

    async def _generate(
        self, args: tuple[Any, ...], kwargs: dict[str, Any], participation: _CacheParticipation
    ) -> Any:
        args, kwargs = _normalize_prompt_call(args, kwargs)
        timeout = _coerce_timeout(kwargs.get("timeout")) or self._inflight_timeout_s
        deadline = asyncio.get_running_loop().time() + timeout if timeout is not None else None
        reason = _cache_skip_reason(
            model=self._model,
            args=args,
            kwargs=kwargs,
        )
        admission = self._reuse_admission(args, kwargs)
        metadata = kwargs.get("metadata")
        if isinstance(metadata, Mapping) and "cache_reuse" in metadata and admission is None:
            reason = reason or "permission_owner_unavailable_or_denied"
        if reason is not None:
            _record_cache_skip(self._cache, reason)
            participation.role = "producer"
            owner = _current_settlement_owner()
            if participation.registration is not None and owner is not None and owner.attempt_id:
                self._cache_reuse_owner.dispatch(participation.registration, owner.attempt_id)
            response = await _maybe_await(self._client.generate(*args, **_provider_kwargs(kwargs)))
            return self._complete_physical_response(response)

        self._require_producer_budget(deadline)
        if deadline is not None or admission is not None:
            try:
                inspect.signature(self._cache.put).bind(
                    "", None, ttl_s=self._ttl_s, admission_check=lambda: None
                )
            except (TypeError, ValueError) as error:
                raise CacheAdmissionUnsupportedError(
                    "bounded or permission-scoped reuse requires atomic cache admission"
                ) from error

        completion = _current_producer_completion()
        request_digest = (
            completion.request_digest
            if completion is not None
            else _request_digest({"args": args, "kwargs": kwargs})
        )
        principal = get_current_access_scope_or_none()
        runtime_scope = principal.to_dict() if principal is not None else None
        cache_key = compute_cache_key(
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
                "accounting_owner_scope": completion.scope_key if completion is not None else None,
                "runtime_principal_scope": runtime_scope,
                "reuse_decision": admission[1].key_payload() if admission is not None else None,
                "request": {
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
            },
        )
        participation.cache_key = cache_key
        if participation.registration is not None:
            self._cache_reuse_owner.bind_request_key(participation.registration, cache_key)
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._require_emission_admission(deadline, admission)
            logger.debug("Prompt cache hit model={} key={}", self._model, cache_key[:12])
            if isinstance(cached, GatewayLLMResponse):
                _mark_cache_response(cached, status="hit", cache_key=cache_key)
                return _CacheReuseGatewayResponse(
                    cached,
                    cache_key=cache_key,
                    provenance=self._cache_reuse_owner.issue(cache_key, request_digest),
                )
            return cached

        provider_kwargs = _provider_kwargs(kwargs)
        flight = self._inflight.get(cache_key)
        is_owner = flight is None
        if is_owner:
            self._require_emission_admission(deadline, admission)
            observation = _FlightObservation()
            owner = _current_settlement_owner()
            if participation.registration is not None and owner is not None and owner.attempt_id:
                self._cache_reuse_owner.dispatch(participation.registration, owner.attempt_id)
            owner_task = asyncio.create_task(
                self._produce(
                    cache_key,
                    args,
                    provider_kwargs,
                    admission,
                    deadline,
                    observation,
                )
            )
            flight = _ProducerFlight(
                owner_task,
                deadline,
                request_digest,
                owner.scope_key if owner is not None else (),
                owner.attempt_id if owner is not None else None,
                observation,
                participation.registration,
            )
            self._inflight[cache_key] = flight
            owner_task.add_done_callback(_consume_task_exception)

        assert flight is not None
        participation.role = "producer" if is_owner else "joined"
        participation.flight = flight
        if not is_owner and flight.registration is not None:
            owner = _current_settlement_owner()
            if owner is not None and owner.attempt_id:
                self._cache_reuse_owner.join(
                    flight.registration,
                    owner.scope_key,
                    request_digest,
                    cache_key,
                    owner.attempt_id,
                )
        response = await asyncio.shield(flight.task)
        self._require_producer_budget(flight.deadline)
        if is_owner:
            return response

        # Followers receive a detached cache snapshot and the same provenance
        # marker as an ordinary cache hit.  They must not share the producer's
        # mutable response object or charge LLM-01 accounting as a miss.
        cached = self._cache.get(cache_key)
        self._require_emission_admission(flight.deadline, admission)
        if cached is not None:
            if isinstance(cached, GatewayLLMResponse):
                _mark_cache_response(cached, status="hit", cache_key=cache_key)
                return _CacheReuseGatewayResponse(
                    cached,
                    cache_key=cache_key,
                    provenance=self._cache_reuse_owner.issue(cache_key, request_digest),
                )
            return cached
        if isinstance(response, GatewayLLMResponse):
            detached = _thaw_response(_freeze_response(response))
            return _CacheReuseGatewayResponse(
                detached,
                cache_key=cache_key,
                provenance=self._cache_reuse_owner.issue(cache_key, request_digest),
            )
        return response

    async def _produce(
        self,
        cache_key: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        admission: tuple[CacheReuseRequest, CacheReuseDecision] | None,
        deadline: float | None,
        observation: _FlightObservation,
    ) -> Any:
        """Produce and publish one cache miss, always releasing its flight."""

        current_task = asyncio.current_task()
        try:
            async with asyncio.timeout_at(deadline):
                response = await self._call_provider(args, kwargs)
                observation.response = response
                response = self._complete_physical_response(response)
                observation.settlement = producer_settlement(response)
                if isinstance(response, GatewayLLMResponse):
                    _mark_cache_response(response, status="miss", cache_key=cache_key)

                amount, _ = _completion_amount(extract_llm_response_data(response), self._model)
                if amount is None:
                    from polisyos.core.llm.traced_client import LLMAccountingError

                    raise LLMAccountingError(
                        response=response,
                        event={"settlement_status": "unknown", "cost_origin": "unknown"},
                        cause=RuntimeError(
                            "unknown provider amount cannot publish a reusable result"
                        ),
                    )

                def admit() -> None:
                    self._require_emission_admission(deadline, admission)

                try:
                    admit()
                    logger.debug("Prompt cache miss model={} key={}", self._model, cache_key[:12])
                    if deadline is not None or admission is not None:
                        self._cache.put(
                            cache_key, response, ttl_s=self._ttl_s, admission_check=admit
                        )
                    else:
                        self._cache.put(cache_key, response, ttl_s=self._ttl_s)
                except CacheReuseDeniedError:
                    # A fresh actual provider completion is billable even when
                    # its permission to publish reusable evidence was revoked.
                    self._require_producer_budget(deadline)
                return response
        except BaseException as exc:
            observation.error = exc
            raise
        finally:
            flight = self._inflight.get(cache_key)
            if flight is not None and flight.task is current_task:
                self._inflight.pop(cache_key, None)

    @staticmethod
    def _complete_physical_response(response: Any) -> Any:
        """Settle actual provider work before any reusable result can be emitted."""
        completion = _current_producer_completion()
        if completion is None:
            return response
        completed = completion.complete(response, True)
        raw_response = completed.response
        if isinstance(raw_response, GatewayLLMResponse):
            return _ProducerGatewayResponse(raw_response, completed._polisyos_settlement)
        return completed

    @staticmethod
    def _require_producer_budget(deadline: float | None) -> None:
        if deadline is not None and asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError("LLM producer deadline expired before result admission")

    def _require_emission_admission(
        self,
        deadline: float | None,
        admission: tuple[CacheReuseRequest, CacheReuseDecision] | None,
    ) -> None:
        self._require_producer_budget(deadline)
        self._require_current_reuse(admission)
        self._require_producer_budget(deadline)

    async def _call_provider(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        """Run the actual provider inside the producer's single deadline owner."""
        return await _maybe_await(self._client.generate(*args, **kwargs))


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
    """Prepare provider kwargs without forwarding snapshot content bytes."""

    normalized = dict(kwargs)
    metadata = kwargs.get("metadata")
    if isinstance(metadata, Mapping) and "cache_reuse" in metadata:
        normalized["metadata"] = _normalize_cache_metadata(metadata)
    return normalized


def _cache_reuse_context(metadata: Any) -> dict[str, Any] | None:
    """Recompute and return a bounded immutable-snapshot reuse identity.

    The cache admission contract deliberately requires the actual snapshot
    bytes and their declared digest. Permission is independently decided by the
    injected operational owner, never the caller's permission declaration. The
    returned value excludes bytes so it is safe for cache keys
    and provider payloads while retaining every substantive identity field.
    """

    if not isinstance(metadata, Mapping):
        return None
    raw_context = metadata.get("cache_reuse")
    if not isinstance(raw_context, Mapping):
        return None
    snapshot = raw_context.get("snapshot")
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
    if not all(isinstance(value, str) and value for value in (ref, version, tenant, scope)):
        return None
    normalized_snapshot = {
        str(key): _normalize_cache_identity_value(value)
        for key, value in snapshot.items()
        if key != "content"
    }
    normalized_snapshot["content_hash"] = expected_hash
    normalized_context = {
        str(key): _normalize_cache_identity_value(value)
        for key, value in raw_context.items()
        if key not in {"snapshot", "permission"}
    }
    normalized_context["snapshot"] = normalized_snapshot
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
        usage_status=response.usage.usage_status,
        cost_status=response.usage.cost_status,
        settlement=producer_settlement(response),
        tool_calls=tuple(
            _SerializedGatewayToolCall(
                id=tool_call.id,
                name=tool_call.name,
                arguments_json=_serialize_payload(tool_call.arguments) or b"{}",
                error_envelope_json=_serialize_payload(tool_call.error_envelope),
            )
            for tool_call in (response.tool_calls or [])
        ),
    )


def _thaw_response(response: _SerializedGatewayResponse) -> GatewayLLMResponse:
    restored = GatewayLLMResponse(
        content=response.content,
        usage=GatewayUsage(
            prompt_tokens=response.usage_prompt_tokens,
            completion_tokens=response.usage_completion_tokens,
            total_tokens=response.usage_total_tokens,
            cost_usd=response.usage_cost_usd,
            usage_status=response.usage_status,
            cost_status=response.cost_status,
        ),
        model=response.model,
        provider=response.provider,
        request_id=response.request_id,
        response_headers=dict(response.response_headers) if response.response_headers else None,
        raw=_deserialize_payload(response.raw_json),
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
    if response.settlement is not None:
        return _ProducerGatewayResponse(restored, response.settlement)
    return restored


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
