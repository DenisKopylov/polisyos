"""Prompt-level response cache for LLM calls."""

from __future__ import annotations

import hashlib
import inspect
import json
import threading
import time
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from polisyos.common.logger import get_logger
from polisyos.common.serialization import stable_json_dumps, to_python_data

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
    ) -> None:
        self._client = client
        self._cache = cache
        self._model = model
        self._ttl_s = max(float(ttl_s), 0.0)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def unwrap(self) -> Any:
        return self._client

    async def generate(self, *args: Any, **kwargs: Any) -> Any:
        reason = _cache_skip_reason(
            model=self._model,
            args=args,
            kwargs=kwargs,
        )
        if reason is not None:
            _record_cache_skip(self._cache, reason)
            return await _maybe_await(self._client.generate(*args, **kwargs))

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
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("Prompt cache hit model={} key={}", self._model, cache_key[:12])
            if isinstance(cached, GatewayLLMResponse) and cached.raw is not None:
                cached.raw.setdefault("_polisyos_cache", {})["status"] = "hit"
                cached.raw["_polisyos_cache"]["cache_key"] = cache_key
            return cached

        response = await _maybe_await(self._client.generate(*args, **kwargs))
        self._cache.put(cache_key, response, ttl_s=self._ttl_s)
        if isinstance(response, GatewayLLMResponse) and response.raw is not None:
            response.raw.setdefault("_polisyos_cache", {})["status"] = "miss"
            response.raw["_polisyos_cache"]["cache_key"] = cache_key
        logger.debug("Prompt cache miss model={} key={}", self._model, cache_key[:12])
        return response


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
    if isinstance(metadata, dict):
        if metadata.get("cacheable") is False:
            return "cache_disabled_by_metadata"
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
    normalized = to_python_data(value, sort_keys=True)
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
