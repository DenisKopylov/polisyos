"""Tool registry: register, look up, and execute tools."""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from polisyos.common.logger import get_logger

from .schema import ToolDefinition

if TYPE_CHECKING:
    from .tool_circuit_breaker import ToolCircuitBreakerRegistry

logger = get_logger(__name__)


class ToolCallResult(BaseModel):
    """Result of a single tool invocation."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: dict[str, Any]
    result: Any = None
    error: str | None = None
    duration_ms: int = 0


class ToolRegistry:
    """Registry mapping tool names to definitions and handlers.

    Thread-safe for reads; registration should happen at startup.
    """

    def __init__(
        self,
        circuit_breakers: ToolCircuitBreakerRegistry | None = None,
    ) -> None:
        self._tools: dict[str, tuple[ToolDefinition, Callable[..., Any]]] = {}
        self._circuit_breakers = circuit_breakers

    def register(
        self, definition: ToolDefinition, handler: Callable[..., Any]
    ) -> None:
        """Register a tool definition with its handler function."""
        self._tools[definition.name] = (definition, handler)

    def get(self, name: str) -> tuple[ToolDefinition, Callable[..., Any]]:
        """Look up a tool by name.  Raises ``KeyError`` if not found."""
        return self._tools[name]

    def list_definitions(self) -> list[ToolDefinition]:
        """Return all registered tool definitions."""
        return [defn for defn, _ in self._tools.values()]

    def to_openai_tools(self) -> list[dict[str, Any]]:
        """Return all tools in OpenAI function-calling format."""
        return [defn.to_openai_tool() for defn, _ in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolCallResult:
        """Execute a tool synchronously."""
        t0 = time.perf_counter()
        try:
            defn, handler = self._tools[name]
        except KeyError:
            return ToolCallResult(
                tool_name=name,
                arguments=arguments,
                error=f"unknown tool: {name}",
            )

        # Circuit breaker check
        if self._circuit_breakers is not None:
            if not self._circuit_breakers.allow_request(name):
                return ToolCallResult(
                    tool_name=name,
                    arguments=arguments,
                    error=f"circuit_breaker_open: {name}",
                )

        try:
            result = handler(**arguments)
            duration_ms = int((time.perf_counter() - t0) * 1000)
            if self._circuit_breakers is not None:
                self._circuit_breakers.record_success(name)
            return ToolCallResult(
                tool_name=name,
                arguments=arguments,
                result=_serialize_result(result),
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            logger.debug("Tool %s execution failed: %s", name, exc)
            if self._circuit_breakers is not None:
                self._circuit_breakers.record_failure(name)
            return ToolCallResult(
                tool_name=name,
                arguments=arguments,
                error=str(exc),
                duration_ms=duration_ms,
            )

    async def aexecute(self, name: str, arguments: dict[str, Any]) -> ToolCallResult:
        """Execute a tool, awaiting if the handler is async.

        Respects per-tool ``timeout_s`` and optional circuit breaker.
        """
        t0 = time.perf_counter()
        try:
            defn, handler = self._tools[name]
        except KeyError:
            return ToolCallResult(
                tool_name=name,
                arguments=arguments,
                error=f"unknown tool: {name}",
            )

        # Circuit breaker check
        if self._circuit_breakers is not None:
            if not self._circuit_breakers.allow_request(name):
                return ToolCallResult(
                    tool_name=name,
                    arguments=arguments,
                    error=f"circuit_breaker_open: {name}",
                )

        timeout = defn.timeout_s
        try:
            if inspect.iscoroutinefunction(handler):
                coro = handler(**arguments)
            else:
                coro = asyncio.get_event_loop().run_in_executor(
                    None, lambda: handler(**arguments)
                )
            result = await asyncio.wait_for(coro, timeout=timeout)
            duration_ms = int((time.perf_counter() - t0) * 1000)
            if self._circuit_breakers is not None:
                self._circuit_breakers.record_success(name)
            return ToolCallResult(
                tool_name=name,
                arguments=arguments,
                result=_serialize_result(result),
                duration_ms=duration_ms,
            )
        except asyncio.TimeoutError:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            logger.debug("Tool %s timed out after %.1fs", name, timeout)
            if self._circuit_breakers is not None:
                self._circuit_breakers.record_failure(name)
            return ToolCallResult(
                tool_name=name,
                arguments=arguments,
                error=f"timeout after {timeout}s",
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            logger.debug("Tool %s async execution failed: %s", name, exc)
            if self._circuit_breakers is not None:
                self._circuit_breakers.record_failure(name)
            return ToolCallResult(
                tool_name=name,
                arguments=arguments,
                error=str(exc),
                duration_ms=duration_ms,
            )


def _serialize_result(result: Any) -> Any:
    """Best-effort serialization for tool results."""
    if result is None:
        return None
    if isinstance(result, (str, int, float, bool)):
        return result
    if isinstance(result, (list, tuple)):
        return [_serialize_result(item) for item in result]
    if isinstance(result, dict):
        return {k: _serialize_result(v) for k, v in result.items()}
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json", exclude_none=True)
    return str(result)
