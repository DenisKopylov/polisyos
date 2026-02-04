"""
TracedLLMClient — Observability wrapper for LLM API calls.

Intercepts LLM calls to record:
- CLIENT span with model/prompt metadata
- Token usage metrics (prompt + completion)
- Call status (success/failure)
"""
from __future__ import annotations

import inspect
from enum import Enum
from typing import Any, Optional, Protocol, runtime_checkable

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


@runtime_checkable
class LLMClientProtocol(Protocol):
    """Protocol for LLM clients that can be wrapped."""

    async def generate(self, **kwargs: Any) -> Any:  # pragma: no cover - protocol
        ...

    def invoke(self, prompt: str, **kwargs: Any) -> Any:  # pragma: no cover - protocol
        ...

    async def ainvoke(self, prompt: str, **kwargs: Any) -> Any:  # pragma: no cover - protocol
        ...


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
    ) -> None:
        self._client = client
        self._model_name = model_name or self._detect_model_name()
        self._capture_prompt = capture_prompt
        self._max_prompt_length = max_prompt_length

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def _detect_model_name(self) -> str:
        for attr in ("model_name", "model", "model_id"):
            value = getattr(self._client, attr, None)
            if value:
                return str(value)
        return "unknown"

    def _detect_provider(self) -> str:
        client_type = type(self._client).__name__.lower()
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

    def _build_span_attributes(self, prompt_text: str) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "polisyos.llm.model": self._model_name,
            "polisyos.llm.provider": self._detect_provider(),
            "polisyos.llm.prompt_length": len(prompt_text),
        }
        if self._capture_prompt:
            truncated = prompt_text[: self._max_prompt_length]
            if len(prompt_text) > self._max_prompt_length:
                truncated += "..."
            attrs["polisyos.llm.prompt_preview"] = truncated
        return attrs

    def _extract_token_usage(self, response: Any) -> tuple[int, int]:
        prompt_tokens = 0
        completion_tokens = 0

        try:
            if hasattr(response, "usage"):
                usage = response.usage
                prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            elif isinstance(response, dict):
                usage = response.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0) or 0
                completion_tokens = usage.get("completion_tokens", 0) or 0
            elif hasattr(response, "input_tokens"):
                prompt_tokens = getattr(response, "input_tokens", 0) or 0
                completion_tokens = getattr(response, "output_tokens", 0) or 0
        except Exception:
            pass

        return prompt_tokens, completion_tokens

    def _record_tokens(
        self,
        span: Any,
        metrics: Any,
        prompt_tokens: int,
        completion_tokens: int,
        status: str,
    ) -> None:
        span.set_attribute("polisyos.llm.tokens.prompt", prompt_tokens)
        span.set_attribute("polisyos.llm.tokens.completion", completion_tokens)
        span.set_attribute("polisyos.llm.tokens.total", prompt_tokens + completion_tokens)

        metrics.record_llm_call(
            model=self._model_name,
            status=status,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def invoke(self, prompt: str, **kwargs: Any) -> Any:
        tracer = get_tracer()
        metrics = get_metrics()
        prompt_text = self._build_prompt_text(prompt)
        span_attrs = self._build_span_attributes(prompt_text)

        with tracer.start_as_current_span(
            f"llm.invoke.{self._model_name}",
            attributes=span_attrs,
            kind=SpanKind.CLIENT,
        ) as span:
            try:
                response = self._client.invoke(prompt, **kwargs)
                prompt_tokens, completion_tokens = self._extract_token_usage(response)
                self._record_tokens(span, metrics, prompt_tokens, completion_tokens, "success")
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
                )
                raise

    async def ainvoke(self, prompt: str, **kwargs: Any) -> Any:
        tracer = get_tracer()
        metrics = get_metrics()
        prompt_text = self._build_prompt_text(prompt)
        span_attrs = self._build_span_attributes(prompt_text)

        with tracer.start_as_current_span(
            f"llm.ainvoke.{self._model_name}",
            attributes=span_attrs,
            kind=SpanKind.CLIENT,
        ) as span:
            try:
                response = await self._client.ainvoke(prompt, **kwargs)
                prompt_tokens, completion_tokens = self._extract_token_usage(response)
                self._record_tokens(span, metrics, prompt_tokens, completion_tokens, "success")
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
                )
                raise

    async def generate(self, *args: Any, **kwargs: Any) -> Any:
        tracer = get_tracer()
        metrics = get_metrics()
        prompt_text = self._build_prompt_text(args[0] if args else kwargs.get("prompt"), **kwargs)
        span_attrs = self._build_span_attributes(prompt_text)

        with tracer.start_as_current_span(
            f"llm.generate.{self._model_name}",
            attributes=span_attrs,
            kind=SpanKind.CLIENT,
        ) as span:
            try:
                response = self._client.generate(*args, **kwargs)
                if inspect.isawaitable(response):
                    response = await response
                prompt_tokens, completion_tokens = self._extract_token_usage(response)
                self._record_tokens(span, metrics, prompt_tokens, completion_tokens, "success")
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
                )
                raise
