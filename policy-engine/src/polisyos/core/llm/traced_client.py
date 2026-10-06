"""
TracedLLMClient — Observability wrapper for LLM API calls.

Intercepts LLM calls to record:
- CLIENT span with model/prompt metadata
- Token usage metrics (prompt + completion)
- Call status (success/failure)
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any

from polisyos.core.observability import get_metrics, get_tracer
from polisyos.core.observability.pricing import estimate_llm_cost_usd

from .protocols import LLMClientProtocol
from .response import LLMResponseData, extract_llm_response_data
from .settlement import (
    LLMProducerEvent,
    LLMProducerSettlement,
    LLMSettledResponse,
    LLMSettlementAck,
    _current_settlement_owner,
    _new_producer_id,
    _producer_completion_context,
    _request_digest,
    producer_settlement,
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


def _default_tracer() -> PolicyOSTracer:
    return get_tracer()


def _default_metrics() -> MetricsRegistry:
    return get_metrics()


class _OptionalSpan:
    def __init__(self, span: Any) -> None:
        self._span = span

    def __getattr__(self, name: str) -> Any:
        def optional(*args: Any, **kwargs: Any) -> Any:
            if self._span is None:
                return None
            try:
                return getattr(self._span, name)(*args, **kwargs)
            except Exception:
                logging.getLogger(__name__).warning(
                    "Optional LLM span operation failed", exc_info=True
                )
                return None

        return optional


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
    ) -> None:
        if prompt_mode not in {"auto", "native", "user"}:
            raise ValueError("prompt_mode must be 'auto', 'native', or 'user'")
        self._client = client
        self._model_name = model_name or self._detect_model_name()
        self._capture_prompt = capture_prompt
        self._max_prompt_length = max_prompt_length
        self._run_id = run_id
        self._model_variant_id = model_variant_id
        self._provider_name = provider_name
        self._call_observer = call_observer
        self._prompt_sanitizer = prompt_sanitizer
        try:
            self._tracer = tracer if tracer is not None else _default_tracer()
        except Exception:
            self._tracer = None
        self._owned_calls: set[asyncio.Task[Any]] = set()
        self._pending_accounting: dict[
            str, tuple[tuple[tuple[str, Any], ...], LLMAccountingError]
        ] = {}
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

    @contextmanager
    def _optional_span(self, *args: Any, **kwargs: Any) -> Iterator[_OptionalSpan]:
        manager = None
        span = None
        try:
            if self._tracer is not None:
                manager = self._tracer.start_as_current_span(*args, **kwargs)
                span = manager.__enter__()
        except Exception:
            manager = None
            logging.getLogger(__name__).warning("Optional LLM tracing sink failed", exc_info=True)
        try:
            yield _OptionalSpan(span)
        except BaseException as primary:
            if manager is not None:
                try:
                    manager.__exit__(type(primary), primary, primary.__traceback__)
                except Exception:
                    logging.getLogger(__name__).warning(
                        "Optional LLM tracing exit failed", exc_info=True
                    )
            raise
        else:
            if manager is not None:
                try:
                    manager.__exit__(None, None, None)
                except Exception:
                    logging.getLogger(__name__).warning(
                        "Optional LLM tracing exit failed", exc_info=True
                    )

    async def _await_owned_call(self, operation: Any) -> Any:
        try:
            self._require_accounting_ready()
        except BaseException:
            operation.close()
            raise
        task = asyncio.create_task(operation)
        self._owned_calls.add(task)

        def completed(done: asyncio.Task[Any]) -> None:
            self._owned_calls.discard(done)
            if not done.cancelled():
                done.exception()

        task.add_done_callback(completed)
        return await asyncio.shield(task)

    def _require_accounting_ready(self) -> None:
        if self._pending_accounting:
            raise next(iter(self._pending_accounting.values()))[1]

    def reconcile_accounting(self, event_identity: str) -> None:
        """Redeliver one retained event through the trusted mandatory callback.

        This is operational delivery, not a durable ledger acknowledgement. The
        callback owner must reconcile ambiguous prior effects by this exact event
        identity. No caller can replace the retained payload or the callback.
        """
        frozen, failure = self._pending_accounting[event_identity]
        if self._required_accounting is None:
            raise RuntimeError("mandatory accounting owner is unavailable")
        try:
            self._required_accounting(dict(frozen))
        except Exception as cause:
            raise LLMAccountingError(
                response=failure.response, event=dict(frozen), cause=cause
            ) from cause
        del self._pending_accounting[event_identity]

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

    async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
        """Forward gateway model preflight through the tracing wrapper."""

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
        if isinstance(response, LLMSettledResponse):
            restored = self._prompt_sanitizer.restore_response(response.response)
            return LLMSettledResponse(restored, response._polisyos_settlement)
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

    def _record_tokens(
        self,
        span: Any,
        metrics: Any,
        parsed: LLMResponseData,
        latency_ms: int,
        status: str,
        provider: str,
        response: Any,
        producer_event: LLMProducerEvent | None = None,
    ) -> LLMProducerSettlement | None:
        prompt_tokens = parsed.origin_prompt_tokens
        if prompt_tokens is None:
            prompt_tokens = parsed.prompt_tokens
        completion_tokens = parsed.origin_completion_tokens
        if completion_tokens is None:
            completion_tokens = parsed.completion_tokens
        estimated_cost_usd = self._estimate_cost_usd(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        origin_cost_usd = parsed.origin_cost_usd
        provider_call = not parsed.cache_hit
        billable_prompt_tokens = parsed.prompt_tokens if provider_call else 0
        billable_completion_tokens = parsed.completion_tokens if provider_call else 0
        if provider_call:
            billable_cost_usd = (
                float(parsed.cost_usd) if parsed.cost_usd is not None else float(estimated_cost_usd)
            )
        else:
            billable_cost_usd = 0.0
        cost_delta_usd = (
            float(origin_cost_usd) - float(estimated_cost_usd)
            if origin_cost_usd is not None
            else None
        )

        event = {
            "model": self._model_name,
            "provider": provider,
            "status": "cache_hit" if parsed.cache_hit else status,
            "prompt_tokens": billable_prompt_tokens,
            "completion_tokens": billable_completion_tokens,
            "total_tokens": billable_prompt_tokens + billable_completion_tokens,
            "origin_prompt_tokens": prompt_tokens,
            "origin_completion_tokens": completion_tokens,
            "origin_total_tokens": prompt_tokens + completion_tokens,
            "cost_usd": billable_cost_usd,
            "origin_cost_usd": (float(origin_cost_usd) if origin_cost_usd is not None else None),
            "estimated_cost_usd": float(estimated_cost_usd),
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
            "event_identity": (
                producer_event.event_id
                if producer_event is not None
                else parsed.reuse_event_id or parsed.request_id
            ),
        }
        settlement = None
        if producer_event is not None:
            owner = _current_settlement_owner()
            ack = LLMSettlementAck(
                producer_event.event_id, producer_event.payload_digest, "unmanaged"
            )
            if owner is not None:
                try:
                    received = owner.settle(producer_event, response)
                    if not isinstance(received, LLMSettlementAck):
                        raise ValueError("mandatory settlement acknowledgement is absent")
                    settlement = LLMProducerSettlement(producer_event, received)
                    if received.status != "committed":
                        raise ValueError("mandatory settlement is unknown")
                    ack = received
                except Exception as exc:
                    event["settlement_status"] = "unknown"
                    event["producer_event"] = producer_event
                    event["payload_digest"] = producer_event.payload_digest
                    raise LLMAccountingError(response=response, event=event, cause=exc) from exc
            settlement = LLMProducerSettlement(producer_event, ack)
            event["producer_event_id"] = producer_event.event_id
            event["payload_digest"] = producer_event.payload_digest
            event["settlement_status"] = ack.status

        if self._required_accounting is not None:
            try:
                self._required_accounting(dict(event))
            except Exception as exc:
                failure = LLMAccountingError(
                    response=response,
                    event={**event, "required_accounting_status": "unknown"},
                    cause=exc,
                )
                identity = str(event["event_identity"])
                self._pending_accounting[identity] = (tuple(event.items()), failure)
                raise failure from exc

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
        span.set_attribute("polisyos.llm.cost_usd", billable_cost_usd)
        if origin_cost_usd is not None:
            span.set_attribute("polisyos.llm.origin_cost_usd", float(origin_cost_usd))
        span.set_attribute("polisyos.llm.estimated_cost_usd", float(estimated_cost_usd))
        if cost_delta_usd is not None:
            span.set_attribute("polisyos.llm.cost_delta_usd", float(cost_delta_usd))
        span.set_attribute("polisyos.llm.cache_hit", parsed.cache_hit)
        span.set_attribute("polisyos.llm.provider_call", provider_call)
        span.set_attribute("polisyos.llm.usage_origin", parsed.usage_origin)

        metrics_status = "not_configured"
        if metrics is not None:
            try:
                metrics.record_llm_call(
                    model=self._model_name,
                    status=event["status"],
                    prompt_tokens=billable_prompt_tokens,
                    completion_tokens=billable_completion_tokens,
                    provider=provider,
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
        if self._call_observer is not None:
            try:
                self._call_observer(dict(event))
            except Exception:
                # Observability callback must never break agent execution.
                logging.getLogger(__name__).debug(
                    "Observability callback failed",
                    exc_info=True,
                )

        return settlement

    def invoke(self, prompt: str, **kwargs: Any) -> Any:
        self._require_accounting_ready()
        prompt_text = self._build_prompt_text(prompt)
        provider = self._detect_provider()
        span_attrs = self._build_span_attributes(prompt_text, provider=provider)
        start = time.perf_counter()

        with self._optional_span(
            f"llm.invoke.{self._model_name}",
            attributes=span_attrs,
            kind=_RuntimeSpanKind.CLIENT,
        ) as span:
            try:
                call_args, call_kwargs = self._sanitize_call_args((prompt,), kwargs)
                response = self._client.invoke(*call_args, **call_kwargs)
                parsed = extract_llm_response_data(response)
                provider = self._detect_provider(parsed.provider)
                latency_ms = max(0, int((time.perf_counter() - start) * 1000))
                settled = self._record_tokens(
                    span,
                    self._metrics,
                    parsed,
                    latency_ms,
                    "success",
                    provider,
                    response,
                    self._completion_event(parsed, (prompt,), kwargs),
                )
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.OK))
                if _current_settlement_owner() is not None and settled is not None:
                    response = LLMSettledResponse(response, settled)
                return self._restore_response(response)
            except LLMAccountingError as exc:
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                raise
            except Exception as exc:
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                self._record_error_metric(
                    provider=provider,
                    latency_ms=max(0, int((time.perf_counter() - start) * 1000)),
                )
                raise

    async def ainvoke(self, prompt: str, **kwargs: Any) -> Any:
        return await self._await_owned_call(self._ainvoke_owned(prompt, kwargs))

    async def _ainvoke_owned(self, prompt: str, kwargs: dict[str, Any]) -> Any:
        self._require_accounting_ready()
        prompt_text = self._build_prompt_text(prompt)
        provider = self._detect_provider()
        span_attrs = self._build_span_attributes(prompt_text, provider=provider)
        start = time.perf_counter()

        with self._optional_span(
            f"llm.ainvoke.{self._model_name}",
            attributes=span_attrs,
            kind=_RuntimeSpanKind.CLIENT,
        ) as span:
            try:
                call_args, call_kwargs = self._sanitize_call_args((prompt,), kwargs)
                response = await self._client.ainvoke(*call_args, **call_kwargs)
                parsed = extract_llm_response_data(response)
                provider = self._detect_provider(parsed.provider)
                latency_ms = max(0, int((time.perf_counter() - start) * 1000))
                settled = self._record_tokens(
                    span,
                    self._metrics,
                    parsed,
                    latency_ms,
                    "success",
                    provider,
                    response,
                    self._completion_event(parsed, (prompt,), kwargs),
                )
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.OK))
                if _current_settlement_owner() is not None and settled is not None:
                    response = LLMSettledResponse(response, settled)
                return self._restore_response(response)
            except LLMAccountingError as exc:
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                raise
            except Exception as exc:
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                self._record_error_metric(
                    provider=provider,
                    latency_ms=max(0, int((time.perf_counter() - start) * 1000)),
                )
                raise

    def _completion_event(
        self, parsed: LLMResponseData, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> LLMProducerEvent:
        return LLMProducerEvent(
            event_id=parsed.reuse_event_id or _new_producer_id(),
            request_digest=_request_digest({"args": args, "kwargs": kwargs}),
            response_digest="sha256:" + hashlib.sha256(str(parsed.content).encode()).hexdigest(),
            model=parsed.model or self._model_name,
            provider=self._detect_provider(parsed.provider),
            amount=Decimal(0)
            if parsed.cache_hit
            else Decimal(
                str(
                    parsed.cost_usd
                    if parsed.cost_usd is not None
                    else self._estimate_cost_usd(
                        prompt_tokens=parsed.prompt_tokens,
                        completion_tokens=parsed.completion_tokens,
                    )
                )
            ),
            cost_origin="reuse"
            if parsed.cache_hit
            else ("reported" if parsed.cost_usd is not None else "estimated"),
            kind="reuse" if parsed.cache_hit else "provider",
        )

    async def generate(self, *args: Any, **kwargs: Any) -> Any:
        call_args, call_kwargs = self._normalize_generate_call(args, kwargs)
        return await self._await_owned_call(self._generate_owned(call_args, call_kwargs))

    async def _generate_owned(self, call_args: tuple[Any, ...], call_kwargs: dict[str, Any]) -> Any:
        self._require_accounting_ready()
        prompt = call_args[0] if call_args else call_kwargs.get("prompt")
        prompt_kwargs = dict(call_kwargs)
        prompt_kwargs.pop("prompt", None)
        prompt_text = self._build_prompt_text(prompt, **prompt_kwargs)
        provider = self._detect_provider()
        span_attrs = self._build_span_attributes(prompt_text, provider=provider)
        start = time.perf_counter()
        request_digest = _request_digest({"args": call_args, "kwargs": call_kwargs})
        provider_id = _new_producer_id()
        completion_recorded = False
        accounting_owner = _current_settlement_owner()
        scope = (
            "traced-owner",
            str(id(self)),
            self._run_id or "",
            self._model_variant_id or "",
            *(accounting_owner.scope_key if accounting_owner is not None else ()),
        )

        with self._optional_span(
            f"llm.generate.{self._model_name}",
            attributes=span_attrs,
            kind=_RuntimeSpanKind.CLIENT,
        ) as span:

            def complete(response: Any) -> LLMSettledResponse:
                nonlocal completion_recorded
                parsed = extract_llm_response_data(response)
                resolved_provider = self._detect_provider(parsed.provider)
                origin = producer_settlement(response)
                amount = (
                    Decimal(0)
                    if parsed.cache_hit
                    else Decimal(
                        str(
                            parsed.cost_usd
                            if parsed.cost_usd is not None
                            else self._estimate_cost_usd(
                                prompt_tokens=parsed.prompt_tokens,
                                completion_tokens=parsed.completion_tokens,
                            )
                        )
                    )
                )
                producer_event = LLMProducerEvent(
                    event_id=(parsed.reuse_event_id or _new_producer_id())
                    if parsed.cache_hit
                    else provider_id,
                    request_digest=request_digest,
                    response_digest="sha256:" + hashlib.sha256(parsed.content.encode()).hexdigest(),
                    model=parsed.model or self._model_name,
                    provider=resolved_provider,
                    amount=amount,
                    cost_origin=(
                        "reuse"
                        if parsed.cache_hit
                        else "reported"
                        if parsed.cost_usd is not None
                        else "estimated"
                    ),
                    kind="reuse" if parsed.cache_hit else "provider",
                    origin_event_id=origin.event.event_id if origin is not None else None,
                )
                settled = self._record_tokens(
                    span,
                    self._metrics,
                    parsed,
                    max(0, int((time.perf_counter() - start) * 1000)),
                    "success",
                    resolved_provider,
                    response,
                    producer_event,
                )
                completion_recorded = True
                if settled is None:
                    raise RuntimeError("producer completion did not retain settlement identity")
                return LLMSettledResponse(response, settled)

            try:
                sanitized_args, sanitized_kwargs = self._sanitize_call_args(call_args, call_kwargs)
                with _producer_completion_context(scope, complete):
                    response = self._client.generate(*sanitized_args, **sanitized_kwargs)
                    if inspect.isawaitable(response):
                        response = await response
                if not completion_recorded:
                    completed = complete(response)
                    # Keep the legacy response API unless a durable owner was supplied.
                    response = completed if accounting_owner is not None else response
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.OK))
                return self._restore_response(response)
            except LLMAccountingError as exc:
                span.set_status(_RuntimeStatus(_RuntimeStatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                raise
            except Exception as exc:
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
