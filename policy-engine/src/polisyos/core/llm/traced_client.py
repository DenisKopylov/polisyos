"""
TracedLLMClient — Observability wrapper for LLM API calls.

Intercepts LLM calls to record:
- CLIENT span with model/prompt metadata
- Token usage metrics (prompt + completion)
- Call status (success/failure)
"""

from __future__ import annotations

import asyncio
import contextvars
import hashlib
import inspect
import json
import logging
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any

from polisyos.core.observability import get_metrics, get_tracer
from polisyos.core.observability.pricing import estimate_llm_cost_usd
from polisyos.core.security.tenant_context import (
    get_current_access_scope_or_none,
    get_current_cell_id,
    get_current_tenant_id_or_none,
)

from .cache_settlement import CacheSettlementSession, session_for_cache_client
from .protocols import LLMClientProtocol
from .response import LLMResponseData, extract_llm_response_data
from .settlement import (
    LLMProducerAdmissionGuard,
    LLMProducerEvent,
    LLMProducerIntent,
    LLMProducerSettlement,
    LLMSettledResponse,
    LLMSettlementAck,
    LLMSettlementIntegrityError,
    LLMSettlementOwnershipError,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer

    from .sanitization import PromptSanitizer


def _load_runtime_trace_types() -> tuple[Any, Any, Any]:
    try:
        from opentelemetry.trace import SpanKind, Status, StatusCode
    except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency

        class _FallbackSpanKind(str, Enum):
            CLIENT = "CLIENT"

        class _FallbackStatusCode(str, Enum):
            OK = "OK"
            ERROR = "ERROR"

        class _FallbackStatus:
            def __init__(
                self,
                status_code: _FallbackStatusCode,
                description: str | None = None,
            ) -> None:
                self.status_code = status_code
                self.description = description

        return _FallbackSpanKind, _FallbackStatus, _FallbackStatusCode
    return SpanKind, Status, StatusCode


_RuntimeSpanKind, _RuntimeStatus, _RuntimeStatusCode = _load_runtime_trace_types()


class LLMAccountingError(RuntimeError):
    """A provider result was received but mandatory accounting did not commit.

    The response is attached so callers can persist or reconcile the received
    result without treating the provider operation as if it never happened.
    """

    def __init__(
        self,
        *,
        response: Any,
        event: dict[str, Any],
        cause: BaseException,
    ) -> None:
        self.response = response
        self.event = event
        self.cause = cause
        super().__init__(
            "LLM provider result received but mandatory accounting failed; "
            f"reconciliation required: {cause}",
        )


@dataclass
class _ProducerSettlementRoute:
    """One call-scoped owner selected from the actual nested client chain."""

    clients: tuple[TracedLLMClient, ...]
    owner: TracedLLMClient
    store: Any | None
    required_accounting: Any | None
    metrics: Any | None
    call_observer: Any | None
    intent: Any | None = None
    readback_record: Any | None = None
    settlement: LLMProducerSettlement | None = None


_ACTIVE_PRODUCER_ROUTE: contextvars.ContextVar[_ProducerSettlementRoute | None] = (
    contextvars.ContextVar("polisyos_active_llm_producer_route", default=None)
)


@contextmanager
def _producer_route_scope(route: _ProducerSettlementRoute) -> Iterator[None]:
    token = _ACTIVE_PRODUCER_ROUTE.set(route)
    try:
        yield
    finally:
        _ACTIVE_PRODUCER_ROUTE.reset(token)


def _settlement_ack(
    event: LLMProducerEvent,
    result: Any,
    *,
    required: bool,
) -> LLMSettlementAck:
    if isinstance(result, LLMSettlementAck):
        if result.event_id != event.event_id or result.payload_digest != event.payload_digest:
            return LLMSettlementAck(event.event_id, event.payload_digest, "unknown")
        return result
    receipt_event_id = getattr(result, "event_id", None)
    receipt_digest = getattr(result, "payload_digest", None)
    if receipt_event_id == event.event_id and receipt_digest == event.payload_digest:
        return LLMSettlementAck(
            event.event_id,
            event.payload_digest,
            "committed",
            receipts=(str(receipt_event_id),),
            durability="ledger",
        )
    if isinstance(result, dict):
        status = result.get("status")
        if isinstance(status, str) and status in {"committed", "unknown", "unmanaged"}:
            durability = result.get("durability", "none")
            if not isinstance(durability, str) or durability not in {"ledger", "memory", "none"}:
                durability = "none"
            raw_receipts = result.get("receipts", ())
            receipts = (
                tuple(map(str, raw_receipts)) if isinstance(raw_receipts, (tuple, list)) else ()
            )
            ack = LLMSettlementAck(
                event_id=str(result.get("event_id", "")),
                payload_digest=str(result.get("payload_digest", "")),
                status=status,
                receipts=receipts,
                durability=durability,
            )
            if ack.event_id == event.event_id and ack.payload_digest == event.payload_digest:
                return ack
    return LLMSettlementAck(
        event.event_id,
        event.payload_digest,
        "unknown" if required else "unmanaged",
        durability="none",
    )


def _default_tracer() -> PolicyOSTracer:
    return get_tracer()


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


class TracedLLMClient:
    """
    Observability wrapper for LLM clients.

    Intercepts invoke/ainvoke/generate calls to:
    1. Create CLIENT span with prompt metadata
    2. Record token usage to MetricsRegistry
    3. Record call status (success/failure)
    """

    def __init__(
        self,
        client: Any,
        model_name: str | None = None,
        capture_prompt: bool = False,
        max_prompt_length: int = 200,
        run_id: str | None = None,
        model_variant_id: str | None = None,
        provider_name: str | None = None,
        call_observer: Callable[[dict[str, Any]], None] | None = None,
        prompt_sanitizer: PromptSanitizer | None = None,
        tracer: PolicyOSTracer | Any | None = None,
        metrics: MetricsRegistry | Any | None = None,
        required_accounting: Callable[[dict[str, Any]], None] | None = None,
        prompt_mode: str = "auto",
        cache_settlement_session: CacheSettlementSession | None = None,
        producer_settlement_store: Any | None = None,
        producer_budget_key: str = "run",
        producer_admission_guard: LLMProducerAdmissionGuard | None = None,
        producer_intent_observer: Callable[[LLMProducerIntent, object], None] | None = None,
        producer_begin_executor: LLMProducerAdmissionGuard | None = None,
    ) -> None:
        if prompt_mode not in {"auto", "native", "user"}:
            raise ValueError("prompt_mode must be 'auto', 'native', or 'user'")
        self._client = client
        if cache_settlement_session is None:
            cache_settlement_session = session_for_cache_client(client)
        if cache_settlement_session is not None and (
            type(cache_settlement_session) is not CacheSettlementSession
            or not cache_settlement_session.owns(client)
        ):
            raise ValueError("cache settlement session must own the exact wrapped producer client")
        self._cache_settlement_session = cache_settlement_session
        self._producer_settlement_store = producer_settlement_store
        self._producer_budget_key = producer_budget_key
        self._producer_admission_guard = producer_admission_guard
        self._producer_intent_observer = producer_intent_observer
        self._producer_begin_executor = producer_begin_executor
        self._producer_intents_by_event: dict[str, Any] = {}
        self._pending_ledger_observation_ids: set[str] = set()
        self._producer_intents_lock = threading.Lock()
        self._cache_settlement_hooks = False
        configure_hooks = getattr(type(client), "set_producer_settlement_hooks", None)
        if producer_settlement_store is not None and callable(configure_hooks):
            configure_hooks(
                client,
                begin=self._begin_provider_event,
                settle=self._settle_provider_response,
                unknown=self._settle_unknown_provider_event,
            )
            self._cache_settlement_hooks = True
        self._model_name = model_name or self._detect_model_name()
        self._capture_prompt = capture_prompt
        self._max_prompt_length = max_prompt_length
        self._run_id = run_id
        self._model_variant_id = model_variant_id
        self._provider_name = provider_name
        self._call_observer = call_observer
        self._observed_call_event_ids: set[str] = set()
        self._prompt_sanitizer = prompt_sanitizer
        self._tracer = tracer if tracer is not None else _default_tracer()
        if metrics is not None:
            self._metrics = metrics
        else:
            try:
                self._metrics = _default_metrics()
            except Exception:
                self._metrics = None
        self._required_accounting = required_accounting
        self._prompt_mode = (
            self._detect_prompt_mode(client) if prompt_mode == "auto" else prompt_mode
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def unwrap(self) -> Any:
        current = self._client
        while hasattr(current, "unwrap") and callable(current.unwrap):
            next_client = current.unwrap()
            if next_client is current:
                break
            current = next_client
        return current

    @property
    def _accounting_flight_owner(self) -> CacheSettlementSession | None:
        """Expose only the opaque Core session bound to this exact client chain."""
        return self._cache_settlement_session

    async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
        """Forward gateway model preflight through the tracing wrapper."""

        guard = self._producer_admission_guard
        if guard is not None:
            guard(lambda: None)
        list_models = self._client.list_model_ids
        result = list_models(timeout=timeout)
        if inspect.isawaitable(result):
            result = await result
        return [str(item) for item in result]

    def _detect_model_name(self) -> str:
        for attr in ("model_name", "model", "model_id"):
            value = getattr(self._client, attr, None)
            if value:
                return str(value)
        return "unknown"

    @staticmethod
    def _detect_prompt_mode(client: Any) -> str:
        """Use the Gateway chat contract when a known gateway is wrapped."""

        current = client
        visited: set[int] = set()
        while id(current) not in visited:
            visited.add(id(current))
            client_type = type(current)
            if client_type.__module__ == "unittest.mock":
                return "native"
            if client_type.__name__ in {
                "FallbackRouter",
                "GatewayLLMClient",
                "SimulatedGatewayLLMClient",
            }:
                return "user"
            module = client_type.__module__
            if module.endswith(".gateway_client") or module.endswith(".simulated_gateway"):
                return "user"
            nested = getattr(current, "_client", None)
            if nested is None or nested is current or type(nested).__module__ == "unittest.mock":
                break
            current = nested
        return "native"

    def _detect_provider(self, parsed_provider: str | None = None) -> str:
        if parsed_provider:
            return parsed_provider
        if self._provider_name:
            return self._provider_name
        for attr in ("provider", "provider_name", "vendor"):
            value = getattr(self._client, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
        client_type = type(self._client).__name__.lower()
        if "gateway" in client_type:
            return "gateway"
        if "openai" in client_type:
            return "openai"
        if "anthropic" in client_type:
            return "anthropic"
        if "mock" in client_type:
            return "mock"
        return "unknown"

    def _build_prompt_text(self, prompt: str | None = None, **kwargs: Any) -> str:
        if prompt is not None:
            prompt_text = str(prompt)
        else:
            system = kwargs.get("system")
            user = kwargs.get("user")
            parts = []
            if system:
                parts.append(str(system))
            if user:
                parts.append(str(user))
            prompt_text = "\n\n".join(parts)
        if self._prompt_sanitizer is not None:
            prompt_text = self._prompt_sanitizer.sanitize_text(prompt_text)
        return prompt_text

    def _sanitize_call_args(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        if self._prompt_sanitizer is None:
            return args, dict(kwargs)
        sanitized_args = tuple(self._prompt_sanitizer.sanitize_payload(arg) for arg in args)
        sanitized_kwargs = {
            key: self._prompt_sanitizer.sanitize_payload(value) for key, value in kwargs.items()
        }
        return sanitized_args, sanitized_kwargs

    def _restore_response(self, response: Any) -> Any:
        if self._prompt_sanitizer is None:
            return response
        return self._prompt_sanitizer.restore_response(response)

    def _build_span_attributes(
        self,
        prompt_text: str,
        *,
        provider: str | None = None,
    ) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "polisyos.llm.model": self._model_name,
            "polisyos.llm.provider": provider or self._detect_provider(),
            "polisyos.llm.prompt_length": len(prompt_text),
        }
        if self._run_id:
            attrs["polisyos.run_id"] = self._run_id
        if self._model_variant_id:
            attrs["polisyos.llm.model_variant_id"] = self._model_variant_id
        if self._capture_prompt:
            truncated = prompt_text[: self._max_prompt_length]
            if len(prompt_text) > self._max_prompt_length:
                truncated += "..."
            attrs["polisyos.llm.prompt_preview"] = truncated
        return attrs

    def _estimate_cost_usd(self, *, prompt_tokens: int, completion_tokens: int) -> float:
        return float(
            estimate_llm_cost_usd(
                model=self._model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        )

    @staticmethod
    def _request_digest(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
        access_scope = get_current_access_scope_or_none()
        payload = json.dumps(
            {
                "args": args,
                "kwargs": kwargs,
                "tenant_binding": {
                    "tenant_id": (
                        access_scope.tenant_id
                        if access_scope is not None
                        else get_current_tenant_id_or_none()
                    ),
                    "cell_id": (
                        access_scope.cell_id if access_scope is not None else get_current_cell_id()
                    ),
                },
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
        return hashlib.sha256(payload).hexdigest()

    def _begin_provider_event(
        self,
        event_id: str,
        request_digest: str,
        provider: str | None = None,
        *,
        route: _ProducerSettlementRoute | None = None,
    ) -> Any | None:
        store = self._producer_settlement_store
        if store is None:
            return None
        begin = getattr(store, "begin_producer_event_safe", None)
        if not callable(begin):
            raise TypeError("producer settlement store lacks durable begin operation")
        active_route = route or _ACTIVE_PRODUCER_ROUTE.get()
        if (
            active_route is not None
            and active_route.owner is self
            and active_route.store is not store
        ):
            raise LLMSettlementOwnershipError("producer_settlement_owner_conflict")

        def begin_owned() -> Any:
            selected_provider = self._provider_name or provider or self._detect_provider()

            def durable_begin() -> Any:
                return begin(
                    event_id,
                    request_digest,
                    key=self._producer_budget_key,
                    model=self._model_name,
                    provider=selected_provider,
                )

            executor = self._producer_begin_executor
            intent = executor(durable_begin) if executor is not None else durable_begin()
            observer = self._producer_intent_observer
            if observer is not None:
                observer(
                    LLMProducerIntent(
                        event_id,
                        request_digest,
                        self._producer_budget_key,
                        self._model_name,
                        selected_provider,
                    ),
                    intent,
                )
            return intent

        guard = self._producer_admission_guard
        intent = guard(begin_owned) if guard is not None else begin_owned()
        if active_route is not None and active_route.owner is self:
            active_route.intent = intent
        with self._producer_intents_lock:
            self._producer_intents_by_event[event_id] = intent
        return intent

    def _settle_provider_response(
        self, event_id: str, request_digest: str, response: Any
    ) -> LLMProducerSettlement:
        parsed = extract_llm_response_data(response)
        intent = self._producer_intent_for_event(event_id)
        if parsed.cost_status == "known" and parsed.cost_usd is not None:
            cost_origin = "reported"
            amount = Decimal(str(parsed.cost_usd))
        elif parsed.cost_status == "missing" and parsed.usage_status == "known":
            cost_origin = "estimated"
            amount = Decimal(
                str(
                    self._estimate_cost_usd(
                        prompt_tokens=parsed.prompt_tokens,
                        completion_tokens=parsed.completion_tokens,
                    )
                )
            )
        else:
            cost_origin = "unknown"
            amount = None
        # Response-declared labels are untrusted metadata. The durable begin
        # record pins the logical route and selected model before dispatch.
        provider = intent.provider if intent is not None else self._detect_provider()
        model = intent.model if intent is not None else self._model_name
        event = LLMProducerEvent(
            event_id=event_id,
            request_digest=request_digest,
            response_digest=hashlib.sha256(parsed.content.encode("utf-8")).hexdigest(),
            model=model,
            provider=provider,
            amount=amount,
            cost_origin=cost_origin,
        )
        route = _ACTIVE_PRODUCER_ROUTE.get()
        settlement = self._persist_producer_event(event, route=route)
        self._observe_provider_settlement(parsed, settlement, route=route)
        return settlement

    def _start_direct_producer_event(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        provider: str,
        route: _ProducerSettlementRoute,
    ) -> tuple[str, str] | None:
        if self._producer_settlement_store is None or route.owner is not self:
            return None
        event_id = f"llm-provider:{uuid.uuid4().hex}"
        request_digest = self._request_digest(args, kwargs)
        self._begin_provider_event(event_id, request_digest, provider, route=route)
        return event_id, request_digest

    def _traced_client_chain(self) -> tuple[TracedLLMClient, ...]:
        """Return traced wrappers discoverable through the actual `_client` chain."""
        clients = [self]
        current = self._client
        visited: set[int] = set()
        while id(current) not in visited:
            visited.add(id(current))
            if isinstance(current, TracedLLMClient):
                clients.append(current)
            nested = getattr(current, "_client", None)
            if nested is None or nested is current:
                break
            current = nested
        return tuple(clients)

    def _resolve_producer_route(self) -> _ProducerSettlementRoute:
        """Select one real wrapper/store owner and reject ambiguous nested stores."""
        guard = self._producer_admission_guard
        if guard is not None:
            guard(lambda: None)
        clients = self._traced_client_chain()
        inherited = _ACTIVE_PRODUCER_ROUTE.get()
        if inherited is not None and any(client is self for client in inherited.clients):
            if any(
                client._producer_settlement_store is not None
                and client._producer_settlement_store is not inherited.store
                for client in clients
            ):
                raise LLMSettlementOwnershipError("producer_settlement_owner_conflict")
            return inherited

        stores = [
            (client, client._producer_settlement_store)
            for client in clients
            if client._producer_settlement_store is not None
        ]
        if stores:
            selected_store = stores[0][1]
            if any(store is not selected_store for _, store in stores[1:]):
                raise LLMSettlementOwnershipError("producer_settlement_owner_conflict")
            owner = stores[-1][0]
            store = selected_store
        else:
            owner = self
            store = None

        def selected(attribute: str) -> Any | None:
            preferred = getattr(owner, attribute)
            if preferred is not None:
                return preferred
            return next(
                (
                    getattr(client, attribute)
                    for client in clients
                    if getattr(client, attribute) is not None
                ),
                None,
            )

        return _ProducerSettlementRoute(
            clients=clients,
            owner=owner,
            store=store,
            required_accounting=selected("_required_accounting"),
            metrics=selected("_metrics"),
            call_observer=selected("_call_observer"),
        )

    def _validate_nested_owner_response(
        self,
        response: Any,
        route: _ProducerSettlementRoute,
    ) -> None:
        """Admit a nested result only when bytes and live owner readback agree."""
        if type(response) is not LLMSettledResponse:
            raise LLMSettlementIntegrityError("producer_settlement_owner_ack_missing")
        settlement = response.settlement
        if route.settlement is None or settlement is not route.settlement:
            raise LLMSettlementIntegrityError("producer_settlement_owner_ack_mismatch")
        parsed = extract_llm_response_data(
            response,
            cache_settlement_session=route.owner._cache_settlement_session,
        )
        response_digest = hashlib.sha256(parsed.content.encode("utf-8")).hexdigest()
        if settlement.event.response_digest != response_digest:
            raise LLMSettlementIntegrityError("producer_response_digest_mismatch")

        ack = settlement.ack
        if route.store is None:
            if ack.status == "committed" and ack.durability == "ledger":
                raise LLMSettlementIntegrityError("producer_settlement_readback_missing")
            return

        resolve = getattr(route.store, "resolve_producer_event_safe", None)
        if not callable(resolve):
            if ack.status == "committed":
                raise LLMSettlementIntegrityError("producer_settlement_readback_missing")
            return
        try:
            current = resolve(settlement.event.event_id)
        except Exception as exc:
            raise LLMSettlementIntegrityError("producer_settlement_readback_unavailable") from exc
        if current is None:
            if ack.status == "committed" or ack.durability == "ledger":
                raise LLMSettlementIntegrityError("producer_settlement_readback_missing")
            return
        owner = route.owner
        if current != route.readback_record or not owner._readback_matches_producer_event(
            current,
            route.intent,
            settlement.event,
        ):
            raise LLMSettlementIntegrityError("producer_settlement_readback_mismatch")
        if current.status == "committed":
            if (
                ack.status != "committed"
                or ack.durability != "ledger"
                or ack.receipts != (settlement.event.event_id,)
            ):
                raise LLMSettlementIntegrityError("producer_settlement_ack_status_mismatch")
        elif ack.status != "unknown" or ack.durability != "ledger" or ack.receipts:
            raise LLMSettlementIntegrityError("producer_settlement_ack_status_mismatch")

    def _nested_owner_is_below(
        self,
        route: _ProducerSettlementRoute,
    ) -> bool:
        return any(client is route.owner for client in self._traced_client_chain()[1:])

    def _settle_unknown_provider_event(
        self,
        event_id: str,
        request_digest: str,
        error: BaseException,
        *,
        route: _ProducerSettlementRoute | None = None,
    ) -> LLMProducerSettlement | None:
        intent = self._producer_intent_for_event(event_id)
        provider = intent.provider if intent is not None else self._detect_provider()
        model = intent.model if intent is not None else self._model_name
        event = LLMProducerEvent(
            event_id=event_id,
            request_digest=request_digest,
            response_digest=hashlib.sha256(
                f"{request_digest}\0{type(error).__name__}".encode()
            ).hexdigest(),
            model=model,
            provider=provider,
            amount=None,
            cost_origin="unknown",
        )
        try:
            active_route = route or _ACTIVE_PRODUCER_ROUTE.get()
            settlement = self._persist_producer_event(event, route=active_route)
            self._observe_provider_settlement(
                None,
                settlement,
                status="error",
                route=active_route,
            )
            self._clear_pending_ledger_observation(event_id)
            return settlement
        except Exception:
            logging.getLogger(__name__).warning(
                "Unable to persist unknown provider outcome", exc_info=True
            )
            return None

    def _observe_provider_settlement(
        self,
        parsed: LLMResponseData | None,
        settlement: LLMProducerSettlement,
        *,
        status: str = "success",
        route: _ProducerSettlementRoute | None = None,
    ) -> None:
        """Expose the durable provider outcome even if its waiter is cancelled."""

        producer_event = settlement.event
        if self._has_pending_ledger_observation(producer_event.event_id):
            return
        amount = producer_event.amount
        prompt_tokens = (
            parsed.prompt_tokens if parsed is not None and parsed.prompt_tokens is not None else 0
        )
        completion_tokens = (
            parsed.completion_tokens
            if parsed is not None and parsed.completion_tokens is not None
            else 0
        )
        origin_prompt_tokens = (
            parsed.origin_prompt_tokens
            if parsed is not None and parsed.origin_prompt_tokens is not None
            else prompt_tokens
        )
        origin_completion_tokens = (
            parsed.origin_completion_tokens
            if parsed is not None and parsed.origin_completion_tokens is not None
            else completion_tokens
        )
        event = {
            "model": producer_event.model,
            "provider": producer_event.provider,
            "status": status,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "origin_prompt_tokens": origin_prompt_tokens,
            "origin_completion_tokens": origin_completion_tokens,
            "origin_total_tokens": origin_prompt_tokens + origin_completion_tokens,
            "cost_usd": float(amount) if amount is not None else None,
            "cost_origin": producer_event.cost_origin,
            "cost_status": parsed.cost_status if parsed is not None else "missing",
            "amount": amount,
            "event_id": producer_event.event_id,
            "producer_event": producer_event,
            "producer_payload_digest": producer_event.payload_digest,
            "origin_event_id": producer_event.origin_event_id,
            "origin_cost_usd": (
                float(parsed.origin_cost_usd)
                if parsed is not None and parsed.origin_cost_usd is not None
                else None
            ),
            "estimated_cost_usd": (
                float(amount)
                if producer_event.cost_origin == "estimated" and amount is not None
                else None
            ),
            "cost_delta_usd": None,
            "latency_ms": 0,
            "run_id": self._run_id,
            "model_variant_id": self._model_variant_id,
            "request_id": parsed.request_id if parsed is not None else None,
            "cache_hit": False,
            "provider_call": True,
            "usage_origin": parsed.usage_origin if parsed is not None else "unknown",
            "reuse_event_id": None,
            "cache_key": None,
            "event_identity": parsed.request_id if parsed is not None else None,
            "settlement_status": settlement.ack.status,
            "durability": settlement.ack.durability,
            "receipts": list(settlement.ack.receipts),
            "settlement_durability": settlement.ack.durability,
            "settlement_receipts": list(settlement.ack.receipts),
        }
        self._notify_call_observer(event, observer=route.call_observer if route else None)

    def _notify_call_observer(
        self,
        event: dict[str, Any],
        *,
        observer: Any | None = None,
    ) -> None:
        """Deliver one observed call event per immutable producer event ID."""
        event_id = event.get("event_id")
        if isinstance(event_id, str):
            with self._producer_intents_lock:
                if event_id in self._pending_ledger_observation_ids:
                    self._pending_ledger_observation_ids.discard(event_id)
                    return
        selected_observer = observer if observer is not None else self._call_observer
        if selected_observer is None:
            return
        if isinstance(event_id, str):
            if event_id in self._observed_call_event_ids:
                return
            self._observed_call_event_ids.add(event_id)
        try:
            selected_observer(dict(event))
        except Exception:
            # Observability callback must never break agent execution.
            logging.getLogger(__name__).debug(
                "Observability callback failed",
                exc_info=True,
            )

    def _has_pending_ledger_observation(self, event_id: str) -> bool:
        with self._producer_intents_lock:
            return event_id in self._pending_ledger_observation_ids

    def _clear_pending_ledger_observation(self, event_id: str) -> None:
        with self._producer_intents_lock:
            self._pending_ledger_observation_ids.discard(event_id)

    def _producer_intent_for_event(self, event_id: str) -> Any | None:
        """Return the immutable begin record that owns this response event."""
        with self._producer_intents_lock:
            return self._producer_intents_by_event.get(event_id)

    async def _await_direct_provider(
        self, result: Any, intent: tuple[str, str] | None
    ) -> tuple[Any, LLMProducerSettlement | None]:
        if not inspect.isawaitable(result):
            settlement = (
                self._settle_provider_response(*intent, result) if intent is not None else None
            )
            return result, settlement
        if intent is None:
            return await result, None
        task = asyncio.create_task(result)
        try:
            response = await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                response = await asyncio.shield(task)
            except BaseException as error:
                self._settle_unknown_provider_event(*intent, error)
            else:
                self._settle_provider_response(*intent, response)
                self._clear_pending_ledger_observation(intent[0])
            raise
        except BaseException as error:
            self._settle_unknown_provider_event(*intent, error)
            raise
        return response, self._settle_provider_response(*intent, response)

    def _persist_producer_event(
        self,
        event: LLMProducerEvent,
        *,
        route: _ProducerSettlementRoute | None = None,
        cache_reuse_response: object | None = None,
    ) -> LLMProducerSettlement:
        store = self._producer_settlement_store
        if store is None:
            ack = LLMSettlementAck(
                event.event_id, event.payload_digest, "unmanaged", durability="none"
            )
            return LLMProducerSettlement(event, ack)
        settle = getattr(store, "settle_producer_event_safe", None)
        if not callable(settle):
            raise TypeError("producer settlement store lacks durable settlement operation")
        with self._producer_intents_lock:
            intent = self._producer_intents_by_event.get(event.event_id)
        active_route = route or _ACTIVE_PRODUCER_ROUTE.get()
        if active_route is not None and active_route.owner is self:
            if active_route.store is not store:
                raise LLMSettlementOwnershipError("producer_settlement_owner_conflict")
            active_route.readback_record = None
        try:
            reuse_kwargs = (
                {
                    "cache_reuse_session": self._cache_settlement_session,
                    "cache_reuse_response": cache_reuse_response,
                }
                if cache_reuse_response is not None
                else {}
            )
            record = settle(
                event.event_id,
                event.request_digest,
                event.payload_digest,
                key=self._producer_budget_key,
                model=event.model,
                provider=event.provider,
                amount=event.amount,
                cost_origin=event.cost_origin,
                origin_event_id=event.origin_event_id,
                **reuse_kwargs,
            )
            if self._readback_matches_producer_event(record, intent, event):
                if active_route is not None and active_route.owner is self:
                    active_route.readback_record = record
                status = "committed" if record.status == "committed" else "unknown"
                durability = "ledger"
                receipts = (event.event_id,) if status == "committed" else ()
            else:
                status = "unknown"
                durability = "none"
                receipts = ()
        except Exception:
            status = "unknown"
            durability = "none"
            receipts = ()
            try:
                resolve = getattr(store, "resolve_producer_event_safe", None)
                record = resolve(event.event_id) if callable(resolve) else None
            except Exception:
                record = None
            if self._readback_matches_producer_event(record, intent, event):
                if active_route is not None and active_route.owner is self:
                    active_route.readback_record = record
                if record.status == "pending":
                    with self._producer_intents_lock:
                        self._pending_ledger_observation_ids.add(event.event_id)
                elif record.status in {"committed", "unknown"}:
                    status = record.status
                    durability = "ledger"
                    receipts = (event.event_id,) if status == "committed" else ()
        finally:
            with self._producer_intents_lock:
                self._producer_intents_by_event.pop(event.event_id, None)
        ack = LLMSettlementAck(
            event.event_id,
            event.payload_digest,
            status,
            receipts=receipts,
            durability=durability,
        )
        return LLMProducerSettlement(event, ack)

    def _readback_matches_producer_event(
        self,
        record: Any,
        intent: Any,
        event: LLMProducerEvent,
    ) -> bool:
        """Accept readback only when it binds the exact intent and terminal payload."""
        if record is None or intent is None:
            return False
        common_fields_match = (
            record.event_id == event.event_id == intent.event_id
            and record.request_digest == event.request_digest == intent.request_digest
            and record.key == self._producer_budget_key == intent.key
            and record.model == event.model == intent.model
            and record.provider == event.provider == intent.provider
            and record.run_binding == intent.run_binding
        )
        if not common_fields_match:
            return False
        if record.status == "pending":
            return (
                record.payload_digest is None
                and record.amount is None
                and record.cost_origin == "unknown"
                and record.origin_event_id is None
            )
        return (
            record.status in {"committed", "unknown"}
            and record.payload_digest == event.payload_digest
            and record.amount == event.amount
            and record.cost_origin == event.cost_origin
            and record.origin_event_id == event.origin_event_id
        )

    def _record_tokens(
        self,
        span: Any,
        metrics: Any,
        parsed: LLMResponseData,
        latency_ms: int,
        status: str,
        provider: str,
        response: Any,
        producer_event_id: str | None = None,
        request_digest: str | None = None,
        prior_settlement: LLMProducerSettlement | None = None,
        route: _ProducerSettlementRoute | None = None,
    ) -> LLMProducerSettlement:
        prompt_tokens = parsed.origin_prompt_tokens
        if prompt_tokens is None:
            prompt_tokens = parsed.prompt_tokens
        completion_tokens = parsed.origin_completion_tokens
        if completion_tokens is None:
            completion_tokens = parsed.completion_tokens
        estimated_cost_usd = (
            self._estimate_cost_usd(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            if parsed.usage_status == "known" and parsed.cost_status == "missing"
            else None
        )
        origin_cost_usd = parsed.origin_cost_usd
        provider_call = not parsed.cache_hit
        billable_prompt_tokens = parsed.prompt_tokens if provider_call else 0
        billable_completion_tokens = parsed.completion_tokens if provider_call else 0
        if parsed.cache_hit:
            cost_origin = "reuse"
            amount = Decimal(0)
            billable_cost_usd: float | None = 0.0
        elif parsed.cost_status == "known" and parsed.cost_usd is not None:
            cost_origin = "reported"
            amount = Decimal(str(parsed.cost_usd))
            billable_cost_usd = parsed.cost_usd
        elif estimated_cost_usd is not None:
            cost_origin = "estimated"
            amount = Decimal(str(estimated_cost_usd))
            billable_cost_usd = estimated_cost_usd
        else:
            cost_origin = "unknown"
            amount = None
            billable_cost_usd = None
        cost_delta_usd = (
            float(origin_cost_usd) - float(estimated_cost_usd)
            if origin_cost_usd is not None and estimated_cost_usd is not None
            else None
        )

        passthrough_settlement = (
            response.settlement if type(response) is LLMSettledResponse else None
        )
        prior = (
            prior_settlement
            or passthrough_settlement
            or getattr(response, "producer_settlement", None)
        )
        if type(prior) is not LLMProducerSettlement:
            prior = None
        provider_event_id = producer_event_id or getattr(response, "producer_event_id", None)
        event_id = (
            parsed.reuse_event_id
            if parsed.cache_hit and parsed.reuse_event_id
            else provider_event_id or parsed.request_id or f"llm-event:{uuid.uuid4().hex}"
        )
        resolved_request_digest = (
            request_digest
            or hashlib.sha256(
                f"{self._model_name}\0{provider}\0{parsed.request_id or ''}".encode()
            ).hexdigest()
        )
        if parsed.cache_hit and parsed.reuse_request_digest:
            resolved_request_digest = parsed.reuse_request_digest
        response_digest = hashlib.sha256(parsed.content.encode("utf-8")).hexdigest()
        if prior is not None and prior.event.response_digest != response_digest:
            raise LLMSettlementIntegrityError("producer_response_digest_mismatch")
        producer_event = (
            prior.event
            if prior is not None
            else LLMProducerEvent(
                event_id=event_id,
                request_digest=resolved_request_digest,
                response_digest=response_digest,
                model=self._model_name,
                provider=provider,
                amount=amount,
                cost_origin=cost_origin,
                kind="reuse" if parsed.cache_hit else "provider",
                origin_event_id=parsed.origin_event_id if parsed.cache_hit else None,
            )
        )

        event = {
            "model": producer_event.model,
            "provider": producer_event.provider,
            "status": "cache_hit" if parsed.cache_hit else status,
            "prompt_tokens": billable_prompt_tokens,
            "completion_tokens": billable_completion_tokens,
            "total_tokens": billable_prompt_tokens + billable_completion_tokens,
            "origin_prompt_tokens": prompt_tokens,
            "origin_completion_tokens": completion_tokens,
            "origin_total_tokens": prompt_tokens + completion_tokens,
            "cost_usd": billable_cost_usd,
            "cost_origin": cost_origin,
            "cost_status": parsed.cost_status,
            "amount": amount,
            "event_id": producer_event.event_id,
            "producer_event": producer_event,
            "producer_payload_digest": producer_event.payload_digest,
            "origin_event_id": producer_event.origin_event_id,
            "origin_cost_usd": (float(origin_cost_usd) if origin_cost_usd is not None else None),
            "estimated_cost_usd": estimated_cost_usd,
            "cost_delta_usd": cost_delta_usd,
            "latency_ms": latency_ms,
            "run_id": self._run_id,
            "model_variant_id": self._model_variant_id,
            "request_id": parsed.request_id,
            "cache_hit": parsed.cache_hit,
            "provider_call": provider_call,
            "usage_origin": parsed.usage_origin,
            "reuse_event_id": parsed.reuse_event_id,
            "cache_key": parsed.cache_key,
            "event_identity": parsed.reuse_event_id or parsed.request_id,
        }

        callback_result: Any = prior.ack if prior is not None else None
        if parsed.cache_hit and prior is None and self._producer_settlement_store is not None:
            try:
                self._begin_provider_event(
                    producer_event.event_id,
                    producer_event.request_digest,
                    provider,
                    route=route,
                )
            except Exception:
                if self._producer_admission_guard is not None:
                    raise
                logging.getLogger(__name__).warning(
                    "Unable to persist cache reuse intent", exc_info=True
                )
                callback_result = LLMSettlementAck(
                    producer_event.event_id,
                    producer_event.payload_digest,
                    "unknown",
                    durability="ledger",
                )
            else:
                prior = self._persist_producer_event(
                    producer_event, route=route, cache_reuse_response=response
                )
                callback_result = prior.ack
        required_accounting = (
            route.required_accounting if route is not None else self._required_accounting
        )
        if required_accounting is not None:
            try:
                callback_result = required_accounting(dict(event))
            except Exception as exc:
                raise LLMAccountingError(
                    response=response,
                    event=event,
                    cause=exc,
                ) from exc

        span.set_attribute("polisyos.llm.tokens.prompt", prompt_tokens)
        span.set_attribute("polisyos.llm.tokens.completion", completion_tokens)
        span.set_attribute("polisyos.llm.tokens.total", prompt_tokens + completion_tokens)
        span.set_attribute("polisyos.llm.billable_tokens.prompt", billable_prompt_tokens)
        span.set_attribute("polisyos.llm.billable_tokens.completion", billable_completion_tokens)
        span.set_attribute(
            "polisyos.llm.billable_tokens.total",
            billable_prompt_tokens + billable_completion_tokens,
        )
        span.set_attribute("polisyos.llm.latency_ms", latency_ms)
        if billable_cost_usd is not None:
            span.set_attribute("polisyos.llm.cost_usd", billable_cost_usd)
        if origin_cost_usd is not None:
            span.set_attribute("polisyos.llm.origin_cost_usd", float(origin_cost_usd))
        if estimated_cost_usd is not None:
            span.set_attribute("polisyos.llm.estimated_cost_usd", float(estimated_cost_usd))
        if cost_delta_usd is not None:
            span.set_attribute("polisyos.llm.cost_delta_usd", float(cost_delta_usd))
        span.set_attribute("polisyos.llm.cache_hit", parsed.cache_hit)
        span.set_attribute("polisyos.llm.provider_call", provider_call)
        span.set_attribute("polisyos.llm.usage_origin", parsed.usage_origin)

        metrics_status = "not_configured"
        selected_metrics = route.metrics if route is not None else metrics
        if selected_metrics is not None and passthrough_settlement is None:
            try:
                selected_metrics.record_llm_call(
                    model=producer_event.model,
                    status=event["status"],
                    prompt_tokens=billable_prompt_tokens,
                    completion_tokens=billable_completion_tokens,
                    provider=producer_event.provider,
                    run_id=self._run_id,
                    model_variant_id=self._model_variant_id,
                    cost_usd=billable_cost_usd,
                    latency_ms=latency_ms,
                )
                metrics_status = "recorded"
            except Exception:
                metrics_status = "degraded"
                logging.getLogger(__name__).warning(
                    "Optional LLM metrics sink failed",
                    exc_info=True,
                )
        span.set_attribute("polisyos.llm.metrics_status", metrics_status)
        event["metrics_status"] = metrics_status
        ack = (
            prior.ack
            if prior is not None
            else _settlement_ack(
                producer_event, callback_result, required=required_accounting is not None
            )
        )
        event["settlement_status"] = ack.status
        event["durability"] = ack.durability
        event["receipts"] = list(ack.receipts)
        event["settlement_durability"] = ack.durability
        event["settlement_receipts"] = list(ack.receipts)
        if passthrough_settlement is None:
            self._notify_call_observer(
                event,
                observer=route.call_observer if route is not None else None,
            )
        settlement = LLMProducerSettlement(producer_event, ack)
        if route is not None and route.owner is self:
            route.settlement = settlement
        return settlement

    def invoke(self, prompt: str, **kwargs: Any) -> Any:
        prompt_text = self._build_prompt_text(prompt)
        provider = self._detect_provider()
        route = self._resolve_producer_route()
        span_attrs = self._build_span_attributes(prompt_text, provider=provider)
        start = time.perf_counter()

        with self._tracer.start_as_current_span(
            f"llm.invoke.{self._model_name}",
            attributes=span_attrs,
            kind=_RuntimeSpanKind.CLIENT,
        ) as span:
            producer_intent: tuple[str, str] | None = None
            try:
                call_args, call_kwargs = self._sanitize_call_args((prompt,), kwargs)
                producer_intent = self._start_direct_producer_event(
                    call_args, call_kwargs, provider, route
                )
                with _producer_route_scope(route):
                    response = self._client.invoke(*call_args, **call_kwargs)
                    prior_settlement = (
                        self._settle_provider_response(*producer_intent, response)
                        if producer_intent is not None
                        else None
                    )
                if route.owner is not self:
                    if self._nested_owner_is_below(route):
                        self._validate_nested_owner_response(response, route)
                    span.set_status(_RuntimeStatus(_RuntimeStatusCode.OK))
                    return response
                parsed = extract_llm_response_data(
                    response, cache_settlement_session=self._cache_settlement_session
                )
                provider = self._detect_provider()
                latency_ms = max(0, int((time.perf_counter() - start) * 1000))
                settlement = self._record_tokens(
                    span,
                    self._metrics,
                    parsed,
                    latency_ms,
                    "success",
                    provider,
                    response,
                    producer_event_id=producer_intent[0] if producer_intent else None,
                    request_digest=producer_intent[1] if producer_intent else None,
                    prior_settlement=prior_settlement,
                    route=route,
                )
                route.settlement = settlement
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.OK))
                return LLMSettledResponse(self._restore_response(response), settlement)
            except (LLMSettlementIntegrityError, LLMSettlementOwnershipError) as exc:
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                raise
            except LLMAccountingError as exc:
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                raise
            except Exception as exc:
                if producer_intent is not None:
                    self._settle_unknown_provider_event(*producer_intent, exc, route=route)
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                self._record_error_metric(
                    provider=provider,
                    latency_ms=max(0, int((time.perf_counter() - start) * 1000)),
                )
                raise

    async def ainvoke(self, prompt: str, **kwargs: Any) -> Any:
        prompt_text = self._build_prompt_text(prompt)
        provider = self._detect_provider()
        route = self._resolve_producer_route()
        span_attrs = self._build_span_attributes(prompt_text, provider=provider)
        start = time.perf_counter()

        with self._tracer.start_as_current_span(
            f"llm.ainvoke.{self._model_name}",
            attributes=span_attrs,
            kind=_RuntimeSpanKind.CLIENT,
        ) as span:
            producer_intent: tuple[str, str] | None = None
            try:
                call_args, call_kwargs = self._sanitize_call_args((prompt,), kwargs)
                producer_intent = self._start_direct_producer_event(
                    call_args, call_kwargs, provider, route
                )
                with _producer_route_scope(route):
                    response, prior_settlement = await self._await_direct_provider(
                        self._client.ainvoke(*call_args, **call_kwargs), producer_intent
                    )
                if route.owner is not self:
                    if self._nested_owner_is_below(route):
                        self._validate_nested_owner_response(response, route)
                    span.set_status(_RuntimeStatus(_RuntimeStatusCode.OK))
                    return response
                parsed = extract_llm_response_data(
                    response, cache_settlement_session=self._cache_settlement_session
                )
                provider = self._detect_provider()
                latency_ms = max(0, int((time.perf_counter() - start) * 1000))
                settlement = self._record_tokens(
                    span,
                    self._metrics,
                    parsed,
                    latency_ms,
                    "success",
                    provider,
                    response,
                    producer_event_id=producer_intent[0] if producer_intent else None,
                    request_digest=producer_intent[1] if producer_intent else None,
                    prior_settlement=prior_settlement,
                    route=route,
                )
                route.settlement = settlement
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.OK))
                return LLMSettledResponse(self._restore_response(response), settlement)
            except (LLMSettlementIntegrityError, LLMSettlementOwnershipError) as exc:
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                raise
            except LLMAccountingError as exc:
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                raise
            except Exception as exc:
                if producer_intent is not None:
                    self._settle_unknown_provider_event(*producer_intent, exc, route=route)
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                self._record_error_metric(
                    provider=provider,
                    latency_ms=max(0, int((time.perf_counter() - start) * 1000)),
                )
                raise

    async def generate(self, *args: Any, **kwargs: Any) -> Any:
        call_args, call_kwargs = self._normalize_generate_call(args, kwargs)
        prompt = call_args[0] if call_args else call_kwargs.get("prompt")
        prompt_kwargs = dict(call_kwargs)
        prompt_kwargs.pop("prompt", None)
        prompt_text = self._build_prompt_text(prompt, **prompt_kwargs)
        provider = self._detect_provider()
        route = self._resolve_producer_route()
        span_attrs = self._build_span_attributes(prompt_text, provider=provider)
        start = time.perf_counter()

        with self._tracer.start_as_current_span(
            f"llm.generate.{self._model_name}",
            attributes=span_attrs,
            kind=_RuntimeSpanKind.CLIENT,
        ) as span:
            producer_intent: tuple[str, str] | None = None
            try:
                sanitized_args, sanitized_kwargs = self._sanitize_call_args(
                    call_args,
                    call_kwargs,
                )
                if not self._cache_settlement_hooks:
                    producer_intent = self._start_direct_producer_event(
                        sanitized_args, sanitized_kwargs, provider, route
                    )
                with _producer_route_scope(route):
                    response, prior_settlement = await self._await_direct_provider(
                        self._client.generate(*sanitized_args, **sanitized_kwargs),
                        producer_intent,
                    )
                if route.owner is not self:
                    if self._nested_owner_is_below(route):
                        self._validate_nested_owner_response(response, route)
                    span.set_status(_RuntimeStatus(_RuntimeStatusCode.OK))
                    return response
                parsed = extract_llm_response_data(
                    response, cache_settlement_session=self._cache_settlement_session
                )
                provider = self._detect_provider()
                latency_ms = max(0, int((time.perf_counter() - start) * 1000))
                settlement = self._record_tokens(
                    span,
                    self._metrics,
                    parsed,
                    latency_ms,
                    "success",
                    provider,
                    response,
                    producer_event_id=producer_intent[0] if producer_intent else None,
                    request_digest=producer_intent[1] if producer_intent else None,
                    prior_settlement=prior_settlement,
                    route=route,
                )
                route.settlement = settlement
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.OK))
                return LLMSettledResponse(self._restore_response(response), settlement)
            except (LLMSettlementIntegrityError, LLMSettlementOwnershipError) as exc:
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                raise
            except LLMAccountingError as exc:
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                raise
            except Exception as exc:
                if producer_intent is not None:
                    self._settle_unknown_provider_event(*producer_intent, exc, route=route)
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                self._record_error_metric(
                    provider=provider,
                    latency_ms=max(0, int((time.perf_counter() - start) * 1000)),
                )
                raise

    def _normalize_generate_call(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """Normalize the supported positional/named prompt forms once."""

        if len(args) > 1:
            raise TypeError("generate() accepts at most one positional prompt")
        normalized_kwargs = dict(kwargs)
        has_named_prompt = "prompt" in normalized_kwargs
        if args and has_named_prompt:
            positional_prompt = args[0]
            named_prompt = normalized_kwargs["prompt"]
            if positional_prompt != named_prompt:
                raise TypeError("generate() received conflicting prompt values")
            prompt_value = positional_prompt
        elif args:
            prompt_value = args[0]
        elif has_named_prompt:
            prompt_value = normalized_kwargs["prompt"]
        else:
            return args, normalized_kwargs

        if self._prompt_mode == "user":
            if (
                normalized_kwargs.get("user") is not None
                or normalized_kwargs.get("messages") is not None
            ):
                raise TypeError("prompt cannot be combined with user or messages")
            normalized_kwargs.pop("prompt", None)
            normalized_kwargs["user"] = prompt_value
            return (), normalized_kwargs

        if not args or not has_named_prompt:
            return args, normalized_kwargs
        normalized_kwargs["prompt"] = prompt_value
        return (), normalized_kwargs

    def _record_error_metric(self, *, provider: str, latency_ms: int) -> None:
        """Best-effort error metric; provider failures remain the primary error."""

        if self._metrics is None:
            return
        try:
            self._metrics.record_llm_call(
                model=self._model_name,
                status="error",
                prompt_tokens=0,
                completion_tokens=0,
                provider=provider,
                run_id=self._run_id,
                model_variant_id=self._model_variant_id,
                latency_ms=latency_ms,
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "Optional LLM error metrics sink failed",
                exc_info=True,
            )


__all__ = [
    "LLMAccountingError",
    "LLMClientProtocol",
    "TracedLLMClient",
]
