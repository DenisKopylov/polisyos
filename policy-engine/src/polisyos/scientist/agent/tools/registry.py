"""Tool registry: register, look up, and execute tools."""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
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
    error_type: str | None = None
    error_details: dict[str, Any] | None = None
    duration_ms: int = 0


@dataclass(frozen=True, slots=True)
class _ToolValidationIssue:
    path: str
    message: str
    expected: Any = None
    actual: Any = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "message": self.message,
        }
        if self.expected is not None:
            payload["expected"] = self.expected
        if self.actual is not None:
            payload["actual"] = self.actual
        return payload


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

    def register(self, definition: ToolDefinition, handler: Callable[..., Any]) -> None:
        """Register a tool definition with its handler function."""
        self._tools[definition.name] = (definition, handler)

    def get(self, name: str) -> tuple[ToolDefinition, Callable[..., Any]]:
        """Look up a tool by name.  Raises ``KeyError`` if not found."""
        return self._tools[name]

    def list_definitions(self) -> list[ToolDefinition]:
        """Return all registered tool definitions."""
        return [defn for defn, _ in self._tools.values()]

    def select_definitions(
        self,
        *,
        query_text: str | None = None,
        max_tools: int | None = None,
    ) -> list[ToolDefinition]:
        """Return all or the top-ranked tool definitions for a query."""
        definitions = self.list_definitions()
        if max_tools is None or max_tools <= 0 or len(definitions) <= max_tools:
            return definitions
        if not query_text or not query_text.strip():
            return definitions[:max_tools]

        query_tokens = _tokenize_tool_text(query_text)
        ranked = sorted(
            definitions,
            key=lambda definition: (
                -_tool_definition_score(definition, query_tokens),
                definition.name,
            ),
        )
        return ranked[:max_tools]

    def to_openai_tools(
        self,
        *,
        query_text: str | None = None,
        max_tools: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return selected tools in OpenAI function-calling format."""
        return [
            defn.to_openai_tool()
            for defn in self.select_definitions(
                query_text=query_text,
                max_tools=max_tools,
            )
        ]

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolCallResult:
        """Execute a tool synchronously."""
        t0 = time.perf_counter()
        try:
            defn, handler = self._tools[name]
        except KeyError:
            return ToolCallResult(
                tool_name=name,
                arguments=arguments if isinstance(arguments, dict) else {},
                error=f"unknown tool: {name}",
                error_type="unknown_tool",
                error_details={"tool_name": name},
            )

        validation_error = _validate_arguments(defn.parameters, arguments)
        if validation_error is not None:
            return ToolCallResult(
                tool_name=name,
                arguments=arguments if isinstance(arguments, dict) else {},
                error=validation_error["message"],
                error_type="invalid_arguments",
                error_details=validation_error,
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )

        # Circuit breaker check
        if self._circuit_breakers is not None:
            if not self._circuit_breakers.allow_request(name):
                return ToolCallResult(
                    tool_name=name,
                    arguments=arguments,
                    error=f"circuit_breaker_open: {name}",
                    error_type="circuit_breaker_open",
                    error_details={"tool_name": name},
                )

        try:
            result = handler(**arguments)
            duration_ms = int((time.perf_counter() - t0) * 1000)
            if self._circuit_breakers is not None:
                self._circuit_breakers.record_success(name)
            return ToolCallResult(
                tool_name=name,
                arguments=arguments,
                result=_render_tool_result(result, defn),
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
                error_type="handler_error",
                error_details={"exception_type": type(exc).__name__},
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
                arguments=arguments if isinstance(arguments, dict) else {},
                error=f"unknown tool: {name}",
                error_type="unknown_tool",
                error_details={"tool_name": name},
            )

        validation_error = _validate_arguments(defn.parameters, arguments)
        if validation_error is not None:
            return ToolCallResult(
                tool_name=name,
                arguments=arguments if isinstance(arguments, dict) else {},
                error=validation_error["message"],
                error_type="invalid_arguments",
                error_details=validation_error,
                duration_ms=int((time.perf_counter() - t0) * 1000),
            )

        # Circuit breaker check
        if self._circuit_breakers is not None:
            if not self._circuit_breakers.allow_request(name):
                return ToolCallResult(
                    tool_name=name,
                    arguments=arguments,
                    error=f"circuit_breaker_open: {name}",
                    error_type="circuit_breaker_open",
                    error_details={"tool_name": name},
                )

        timeout = defn.timeout_s
        try:
            if inspect.iscoroutinefunction(handler):
                coro = handler(**arguments)
            else:
                coro = asyncio.get_event_loop().run_in_executor(None, lambda: handler(**arguments))
            result = await asyncio.wait_for(coro, timeout=timeout)
            duration_ms = int((time.perf_counter() - t0) * 1000)
            if self._circuit_breakers is not None:
                self._circuit_breakers.record_success(name)
            return ToolCallResult(
                tool_name=name,
                arguments=arguments,
                result=_render_tool_result(result, defn),
                duration_ms=duration_ms,
            )
        except TimeoutError:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            logger.debug("Tool %s timed out after %.1fs", name, timeout)
            if self._circuit_breakers is not None:
                self._circuit_breakers.record_failure(name)
            return ToolCallResult(
                tool_name=name,
                arguments=arguments,
                error=f"timeout after {timeout}s",
                error_type="timeout",
                error_details={"timeout_s": timeout},
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
                error_type="handler_error",
                error_details={"exception_type": type(exc).__name__},
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


def _render_tool_result(result: Any, definition: ToolDefinition) -> Any:
    """Serialize and compact a tool result according to tool response settings."""
    serialized = _serialize_result(result)
    if definition.response_verbosity == "concise":
        serialized = _concise_tool_result(serialized)
    if definition.response_max_chars is not None:
        serialized = _truncate_tool_result(serialized, definition.response_max_chars)
    return serialized


def _concise_tool_result(value: Any) -> Any:
    if isinstance(value, dict):
        compacted: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(item, list):
                compacted[key] = _concise_list(item)
            elif isinstance(item, dict):
                compacted[key] = _concise_mapping(item)
            elif isinstance(item, str):
                compacted[key] = _truncate_text(item, 600)
            else:
                compacted[key] = item
        return compacted
    if isinstance(value, list):
        return _concise_list(value)
    if isinstance(value, str):
        return _truncate_text(value, 600)
    return value


def _concise_list(items: list[Any]) -> list[Any] | dict[str, Any]:
    if len(items) <= 8:
        return [_concise_tool_result(item) for item in items]
    head = [_concise_tool_result(item) for item in items[:8]]
    return {
        "items": head,
        "omitted_count": len(items) - len(head),
        "total_count": len(items),
    }


def _concise_mapping(value: dict[str, Any]) -> dict[str, Any]:
    compacted: dict[str, Any] = {}
    for index, (key, item) in enumerate(value.items()):
        if index >= 16:
            compacted["__omitted_keys__"] = len(value) - index
            break
        if isinstance(item, str):
            compacted[key] = _truncate_text(item, 600)
        elif isinstance(item, (dict, list)):
            compacted[key] = _concise_tool_result(item)
        else:
            compacted[key] = item
    return compacted


def _truncate_tool_result(value: Any, max_chars: int) -> Any:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)
    if len(encoded) <= max_chars:
        return value
    if isinstance(value, str):
        return _truncate_text(value, max_chars)
    return {
        "truncated": True,
        "original_chars": len(encoded),
        "preview": _truncate_text(encoded, max_chars),
    }


def _truncate_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    if max_chars <= 3:
        return value[:max_chars]
    return value[: max_chars - 3] + "..."


def _validate_arguments(
    parameters_schema: dict[str, Any],
    arguments: dict[str, Any],
) -> dict[str, Any] | None:
    """Validate runtime tool arguments against a minimal JSON Schema subset."""
    if not isinstance(arguments, dict):
        return {
            "message": "$ must be object",
            "violations": [
                _ToolValidationIssue(
                    path="$",
                    message="$ must be object",
                    expected="object",
                    actual=type(arguments).__name__,
                ).to_dict()
            ],
        }
    issues = _validate_schema_value(
        arguments,
        parameters_schema if isinstance(parameters_schema, dict) else {},
        path="$",
    )
    if not issues:
        return None
    return {
        "message": "; ".join(issue.message for issue in issues),
        "violations": [issue.to_dict() for issue in issues],
    }


def _validate_schema_value(
    value: Any,
    schema: dict[str, Any],
    *,
    path: str,
) -> list[_ToolValidationIssue]:
    if not isinstance(schema, dict) or not schema:
        return []

    issues: list[_ToolValidationIssue] = []
    expected_type = schema.get("type")
    if expected_type is not None and not _matches_schema_type(value, expected_type):
        issues.append(
            _ToolValidationIssue(
                path=path,
                message=f"{path} must be {expected_type}",
                expected=expected_type,
                actual=type(value).__name__,
            )
        )
        return issues

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        issues.append(
            _ToolValidationIssue(
                path=path,
                message=f"{path} must be one of {enum_values}",
                expected=enum_values,
                actual=value,
            )
        )

    if isinstance(value, dict):
        required = schema.get("required")
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in value:
                    issues.append(
                        _ToolValidationIssue(
                            path=f"{path}.{key}",
                            message=f"{path}.{key} is required",
                            expected="present",
                        )
                    )

        properties = schema.get("properties")
        known_properties = properties if isinstance(properties, dict) else {}
        for key, nested_value in value.items():
            nested_schema = known_properties.get(key)
            if isinstance(nested_schema, dict):
                issues.extend(
                    _validate_schema_value(
                        nested_value,
                        nested_schema,
                        path=f"{path}.{key}",
                    )
                )
            elif schema.get("additionalProperties") is False:
                issues.append(
                    _ToolValidationIssue(
                        path=f"{path}.{key}",
                        message=f"{path}.{key} is not allowed",
                        expected="no additional properties",
                        actual=nested_value,
                    )
                )

    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                issues.extend(
                    _validate_schema_value(
                        item,
                        item_schema,
                        path=f"{path}[{index}]",
                    )
                )

    return issues


def _matches_schema_type(value: Any, expected_type: Any) -> bool:
    if isinstance(expected_type, list):
        return any(_matches_schema_type(value, item) for item in expected_type)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def _tokenize_tool_text(text: str) -> set[str]:
    normalized = text.lower().replace("_", " ").replace("-", " ")
    return {
        token.strip(".,:;!?()[]{}\"'")
        for token in normalized.split()
        if len(token.strip(".,:;!?()[]{}\"'")) >= 3
    }


def _tool_definition_score(
    definition: ToolDefinition,
    query_tokens: set[str],
) -> float:
    name_tokens = _tokenize_tool_text(definition.name)
    description_tokens = _tokenize_tool_text(definition.description)
    domain_tokens = _tokenize_tool_text(definition.domain)
    score = 0.0
    score += 4.0 * len(query_tokens & name_tokens)
    score += 1.5 * len(query_tokens & description_tokens)
    score += 2.0 * len(query_tokens & domain_tokens)
    return score
