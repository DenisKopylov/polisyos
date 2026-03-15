"""
TracedLLMClient — Observability wrapper for LLM API calls.

Intercepts LLM calls to record:
- CLIENT span with model/prompt metadata
- Token usage metrics (prompt + completion)
- Call status (success/failure)
"""
from __future__ import annotations

import inspect
import time
from enum import Enum
from typing import Any, Callable, Optional

try:
    from opentelemetry.trace import SpanKind, Status, StatusCode
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    class SpanKind(str, Enum):
        CLIENT = "CLIENT"

    class StatusCode(str, Enum):
        OK = "OK"
        ERROR = "ERROR"

    class Status:  # type: ignore[override]
        def __init__(self, status_code: StatusCode, description: str | None = None) -> None:
            self.status_code = status_code
            self.description = description

from polisyos.core.observability import get_metrics, get_tracer
from polisyos.core.observability.pricing import estimate_llm_cost_usd

from .protocols import LLMClientProtocol
from .response import LLMResponseData, extract_llm_response_data


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
    ) -> None:
        self._client = client
        self._model_name = model_name or self._detect_model_name()
        self._capture_prompt = capture_prompt
        self._max_prompt_length = max_prompt_length
        self._run_id = run_id
        self._model_variant_id = model_variant_id
        self._provider_name = provider_name
        self._call_observer = call_observer

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def unwrap(self) -> Any:
        return self._client

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

    def _build_prompt_text(self, prompt: Optional[str] = None, **kwargs: Any) -> str:
        if prompt is not None:
            return prompt
        system = kwargs.get("system")
        user = kwargs.get("user")
        parts = []
        if system:
            parts.append(str(system))
        if user:
            parts.append(str(user))
        return "\n\n".join(parts)

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
        return estimate_llm_cost_usd(
            model=self._model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def _record_tokens(
        self,
        span: Any,
        metrics: Any,
        parsed: LLMResponseData,
        latency_ms: int,
        status: str,
        provider: str,
    ) -> None:
        prompt_tokens = parsed.prompt_tokens
        completion_tokens = parsed.completion_tokens
        cost_usd = parsed.cost_usd
        if cost_usd is None:
            cost_usd = self._estimate_cost_usd(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

        span.set_attribute("polisyos.llm.tokens.prompt", prompt_tokens)
        span.set_attribute("polisyos.llm.tokens.completion", completion_tokens)
        span.set_attribute("polisyos.llm.tokens.total", prompt_tokens + completion_tokens)
        span.set_attribute("polisyos.llm.latency_ms", latency_ms)
        span.set_attribute("polisyos.llm.cost_usd", float(cost_usd))

        metrics.record_llm_call(
            model=self._model_name,
            status=status,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            provider=provider,
            run_id=self._run_id,
            model_variant_id=self._model_variant_id,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )
        if self._call_observer is not None:
            try:
                self._call_observer(
                    {
                        "model": self._model_name,
                        "provider": provider,
                        "status": status,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens,
                        "latency_ms": latency_ms,
                        "cost_usd": float(cost_usd),
                        "run_id": self._run_id,
                        "model_variant_id": self._model_variant_id,
                    }
                )
            except Exception:
                # Observability callback must never break agent execution.
                import logging as _logging
                _logging.getLogger(__name__).debug(
                    "Observability callback failed", exc_info=True,
                )

    def invoke(self, prompt: str, **kwargs: Any) -> Any:
        tracer = get_tracer()
        metrics = get_metrics()
        prompt_text = self._build_prompt_text(prompt)
        provider = self._detect_provider()
        span_attrs = self._build_span_attributes(prompt_text, provider=provider)
        start = time.perf_counter()

        with tracer.start_as_current_span(
            f"llm.invoke.{self._model_name}",
            attributes=span_attrs,
            kind=SpanKind.CLIENT,
        ) as span:
            try:
                response = self._client.invoke(prompt, **kwargs)
                parsed = extract_llm_response_data(response)
                provider = self._detect_provider(parsed.provider)
                latency_ms = max(0, int((time.perf_counter() - start) * 1000))
                self._record_tokens(
                    span,
                    metrics,
                    parsed,
                    latency_ms,
                    "success",
                    provider,
                )
                span.set_status(Status(StatusCode.OK))
                return response
            except Exception as exc:
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                metrics.record_llm_call(
                    model=self._model_name,
                    status="error",
                    prompt_tokens=0,
                    completion_tokens=0,
                    provider=provider,
                    run_id=self._run_id,
                    model_variant_id=self._model_variant_id,
                    latency_ms=max(0, int((time.perf_counter() - start) * 1000)),
                )
                raise

    async def ainvoke(self, prompt: str, **kwargs: Any) -> Any:
        tracer = get_tracer()
        metrics = get_metrics()
        prompt_text = self._build_prompt_text(prompt)
        provider = self._detect_provider()
        span_attrs = self._build_span_attributes(prompt_text, provider=provider)
        start = time.perf_counter()

        with tracer.start_as_current_span(
            f"llm.ainvoke.{self._model_name}",
            attributes=span_attrs,
            kind=SpanKind.CLIENT,
        ) as span:
            try:
                response = await self._client.ainvoke(prompt, **kwargs)
                parsed = extract_llm_response_data(response)
                provider = self._detect_provider(parsed.provider)
                latency_ms = max(0, int((time.perf_counter() - start) * 1000))
                self._record_tokens(
                    span,
                    metrics,
                    parsed,
                    latency_ms,
                    "success",
                    provider,
                )
                span.set_status(Status(StatusCode.OK))
                return response
            except Exception as exc:
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                metrics.record_llm_call(
                    model=self._model_name,
                    status="error",
                    prompt_tokens=0,
                    completion_tokens=0,
                    provider=provider,
                    run_id=self._run_id,
                    model_variant_id=self._model_variant_id,
                    latency_ms=max(0, int((time.perf_counter() - start) * 1000)),
                )
                raise

    async def generate(self, *args: Any, **kwargs: Any) -> Any:
        tracer = get_tracer()
        metrics = get_metrics()
        prompt_text = self._build_prompt_text(args[0] if args else kwargs.get("prompt"), **kwargs)
        provider = self._detect_provider()
        span_attrs = self._build_span_attributes(prompt_text, provider=provider)
        start = time.perf_counter()

        with tracer.start_as_current_span(
            f"llm.generate.{self._model_name}",
            attributes=span_attrs,
            kind=SpanKind.CLIENT,
        ) as span:
            try:
                response = self._client.generate(*args, **kwargs)
                if inspect.isawaitable(response):
                    response = await response
                parsed = extract_llm_response_data(response)
                provider = self._detect_provider(parsed.provider)
                latency_ms = max(0, int((time.perf_counter() - start) * 1000))
                self._record_tokens(
                    span,
                    metrics,
                    parsed,
                    latency_ms,
                    "success",
                    provider,
                )
                span.set_status(Status(StatusCode.OK))
                return response
            except Exception as exc:
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                metrics.record_llm_call(
                    model=self._model_name,
                    status="error",
                    prompt_tokens=0,
                    completion_tokens=0,
                    provider=provider,
                    run_id=self._run_id,
                    model_variant_id=self._model_variant_id,
                    latency_ms=max(0, int((time.perf_counter() - start) * 1000)),
                )
                raise


__all__ = [
    "LLMClientProtocol",
    "TracedLLMClient",
]

