"""
TracedLLMClient — Observability wrapper for LLM API calls.

Intercepts LLM calls to record:
- CLIENT span with model/prompt metadata
- Token usage metrics (prompt + completion)
- Call status (success/failure)
"""

from __future__ import annotations

import inspect
import logging
import time
from enum import Enum
from typing import TYPE_CHECKING, Any

from polisyos.core.observability import get_metrics, get_tracer
from polisyos.core.observability.pricing import estimate_llm_cost_usd

from .protocols import LLMClientProtocol
from .response import LLMResponseData, extract_llm_response_data

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
    ) -> None:
        self._client = client
        self._model_name = model_name or self._detect_model_name()
        self._capture_prompt = capture_prompt
        self._max_prompt_length = max_prompt_length
        self._run_id = run_id
        self._model_variant_id = model_variant_id
        self._provider_name = provider_name
        self._call_observer = call_observer
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

    def _record_tokens(
        self,
        span: Any,
        metrics: Any,
        parsed: LLMResponseData,
        latency_ms: int,
        status: str,
        provider: str,
        response: Any,
    ) -> None:
        prompt_tokens = parsed.prompt_tokens
        completion_tokens = parsed.completion_tokens
        estimated_cost_usd = self._estimate_cost_usd(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        origin_cost_usd = parsed.cost_usd if parsed.cost_usd is not None else estimated_cost_usd
        provider_call = not parsed.cache_hit
        billable_prompt_tokens = prompt_tokens if provider_call else 0
        billable_completion_tokens = completion_tokens if provider_call else 0
        billable_cost_usd = float(origin_cost_usd) if provider_call else 0.0
        cost_delta_usd = float(origin_cost_usd) - float(estimated_cost_usd)

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
            "origin_cost_usd": float(origin_cost_usd),
            "estimated_cost_usd": float(estimated_cost_usd),
            "cost_delta_usd": float(cost_delta_usd),
            "latency_ms": latency_ms,
            "run_id": self._run_id,
            "model_variant_id": self._model_variant_id,
            "request_id": parsed.request_id,
            "cache_hit": parsed.cache_hit,
            "provider_call": provider_call,
            "usage_origin": parsed.usage_origin,
        }

        if self._required_accounting is not None:
            try:
                self._required_accounting(dict(event))
            except Exception as exc:
                raise LLMAccountingError(
                    response=response,
                    event=event,
                    cause=exc,
                ) from exc

        span.set_attribute("polisyos.llm.tokens.prompt", prompt_tokens)
        span.set_attribute("polisyos.llm.tokens.completion", completion_tokens)
        span.set_attribute("polisyos.llm.tokens.total", prompt_tokens + completion_tokens)
        span.set_attribute("polisyos.llm.latency_ms", latency_ms)
        span.set_attribute("polisyos.llm.cost_usd", billable_cost_usd)
        span.set_attribute("polisyos.llm.origin_cost_usd", float(origin_cost_usd))
        span.set_attribute("polisyos.llm.estimated_cost_usd", float(estimated_cost_usd))
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

    def invoke(self, prompt: str, **kwargs: Any) -> Any:
        prompt_text = self._build_prompt_text(prompt)
        provider = self._detect_provider()
        span_attrs = self._build_span_attributes(prompt_text, provider=provider)
        start = time.perf_counter()

        with self._tracer.start_as_current_span(
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
                self._record_tokens(
                    span,
                    self._metrics,
                    parsed,
                    latency_ms,
                    "success",
                    provider,
                    response,
                )
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

    async def ainvoke(self, prompt: str, **kwargs: Any) -> Any:
        prompt_text = self._build_prompt_text(prompt)
        provider = self._detect_provider()
        span_attrs = self._build_span_attributes(prompt_text, provider=provider)
        start = time.perf_counter()

        with self._tracer.start_as_current_span(
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
                self._record_tokens(
                    span,
                    self._metrics,
                    parsed,
                    latency_ms,
                    "success",
                    provider,
                    response,
                )
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

    async def generate(self, *args: Any, **kwargs: Any) -> Any:
        call_args, call_kwargs = self._normalize_generate_call(args, kwargs)
        prompt = call_args[0] if call_args else call_kwargs.get("prompt")
        prompt_kwargs = dict(call_kwargs)
        prompt_kwargs.pop("prompt", None)
        prompt_text = self._build_prompt_text(prompt, **prompt_kwargs)
        provider = self._detect_provider()
        span_attrs = self._build_span_attributes(prompt_text, provider=provider)
        start = time.perf_counter()

        with self._tracer.start_as_current_span(
            f"llm.generate.{self._model_name}",
            attributes=span_attrs,
            kind=_RuntimeSpanKind.CLIENT,
        ) as span:
            try:
                sanitized_args, sanitized_kwargs = self._sanitize_call_args(
                    call_args,
                    call_kwargs,
                )
                response = self._client.generate(*sanitized_args, **sanitized_kwargs)
                if inspect.isawaitable(response):
                    response = await response
                parsed = extract_llm_response_data(response)
                provider = self._detect_provider(parsed.provider)
                latency_ms = max(0, int((time.perf_counter() - start) * 1000))
                self._record_tokens(
                    span,
                    self._metrics,
                    parsed,
                    latency_ms,
                    "success",
                    provider,
                    response,
                )
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

    @staticmethod
    def _normalize_generate_call(
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> tuple[tuple[Any, ...], dict[str, Any]]:
        """Normalize the supported positional/named prompt forms once."""

        if len(args) > 1:
            raise TypeError("generate() accepts at most one positional prompt")
        normalized_kwargs = dict(kwargs)
        if not args or "prompt" not in normalized_kwargs:
            return args, normalized_kwargs
        positional_prompt = args[0]
        named_prompt = normalized_kwargs["prompt"]
        if positional_prompt != named_prompt:
            raise TypeError("generate() received conflicting prompt values")
        normalized_kwargs["prompt"] = positional_prompt
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
