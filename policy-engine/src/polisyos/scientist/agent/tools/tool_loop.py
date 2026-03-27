"""Tool-use execution loop: LLM -> tool calls -> results -> LLM -> ..."""

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger

from .registry import ToolCallResult, ToolRegistry

if TYPE_CHECKING:
    from polisyos.scientist.engine.convergence import ConvergenceConfig

    from .dependency_graph import ToolDependencyGraph

logger = get_logger(__name__)


@dataclass
class ToolLoopResult:
    """Final result of a tool-use loop."""

    content: str
    tool_calls_made: list[ToolCallResult] = field(default_factory=list)
    iterations: int = 0
    total_tokens: int = 0
    converged: bool = False
    convergence_reason: str = ""


@dataclass
class ParsedToolCall:
    """A single tool call extracted from an LLM response."""

    id: str
    name: str
    arguments: dict[str, Any]


def parse_tool_calls_from_response(response: Any) -> list[ParsedToolCall]:
    """Extract tool calls from an OpenAI-format gateway response.

    Handles both the ``tool_calls`` attribute and the ``raw`` dict.
    """
    # Try structured attribute first
    tool_calls_attr = getattr(response, "tool_calls", None)
    if tool_calls_attr:
        return [
            ParsedToolCall(
                id=getattr(tc, "id", str(i)),
                name=getattr(tc, "name", ""),
                arguments=getattr(tc, "arguments", {}),
            )
            for i, tc in enumerate(tool_calls_attr)
        ]

    # Fall back to raw dict
    raw = getattr(response, "raw", None)
    if not raw or not isinstance(raw, dict):
        return []

    choices = raw.get("choices", [])
    if not choices:
        return []

    message = choices[0].get("message", {})
    raw_tool_calls = message.get("tool_calls", [])
    if not raw_tool_calls:
        return []

    results: list[ParsedToolCall] = []
    for tc in raw_tool_calls:
        fn = tc.get("function", {})
        args_str = fn.get("arguments", "{}")
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
        except (json.JSONDecodeError, TypeError):
            args = {}
        results.append(
            ParsedToolCall(
                id=tc.get("id", ""),
                name=fn.get("name", ""),
                arguments=args,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Backoff helper
# ---------------------------------------------------------------------------

def _tool_backoff_delay(consecutive_failures: int) -> float:
    """Exponential backoff with full jitter for transient tool failures."""
    base = min(1.0 * (2.0 ** (consecutive_failures - 1)), 30.0)
    return base * random.random()


async def run_tool_loop(
    *,
    client: Any,
    system: str,
    user: str,
    tool_registry: ToolRegistry,
    max_iterations: int = 10,
    budget_enforcer: Any | None = None,
    audit_log: Any | None = None,
    convergence_config: "ConvergenceConfig | None" = None,
    persistent_memory: Any | None = None,
    tool_dependencies: "ToolDependencyGraph | None" = None,
) -> ToolLoopResult:
    """Run an agentic tool-use loop.

    1. Call the LLM with tool definitions.
    2. If the response contains tool calls, execute them.
    3. Inject tool results back as ``role="tool"`` messages.
    4. Repeat until no tool calls or ``max_iterations`` reached.

    Enhancements over the basic loop:

    * **Adaptive max iterations** — when *budget_enforcer* is provided, the
      effective ceiling is reduced as the budget is consumed.
    * **Exponential backoff** — transient per-tool failures trigger increasing
      delays before the next attempt.
    * **Tool dependency ordering** — when *tool_dependencies* is provided,
      tool calls within an iteration are sorted topologically.
    """
    from polisyos.scientist.engine.convergence import ConvergenceDetector

    tools = tool_registry.to_openai_tools()
    messages: list[dict[str, Any]] = []
    all_tool_calls: list[ToolCallResult] = []
    total_tokens = 0
    content = ""

    detector: ConvergenceDetector | None = None
    if convergence_config is not None:
        detector = ConvergenceDetector(convergence_config)

    # Per-tool consecutive failure tracking (for backoff)
    tool_failures: dict[str, int] = {}

    # Inject prior knowledge from persistent memory
    if persistent_memory is not None:
        try:
            from polisyos.scientist.agent.persistent_memory import MemoryQuery
            prior_entries = persistent_memory.query(
                MemoryQuery(query_text=user[:500], max_results=10),
            )
            if prior_entries:
                memory_block = persistent_memory.format_for_prompt(prior_entries)
                system = f"{system}\n\n{memory_block}"
        except Exception:
            logger.debug("Failed to inject persistent memory into tool loop")

    for iteration in range(max_iterations):
        # Adaptive max iterations: shrink ceiling based on budget usage
        if budget_enforcer is not None and iteration > 0 and total_tokens > 0:
            avg_tokens_per_iter = total_tokens / iteration
            remaining = getattr(budget_enforcer, "remaining_budget", None)
            if callable(remaining):
                try:
                    rem = remaining()
                    if rem is not None and avg_tokens_per_iter > 0:
                        budget_limited = max(2, int(rem / avg_tokens_per_iter))
                        if iteration >= budget_limited:
                            logger.debug(
                                "Adaptive iteration cap reached (%d >= %d)",
                                iteration, budget_limited,
                            )
                            break
                except Exception:
                    pass

        # Build generate kwargs
        generate_kwargs: dict[str, Any] = {
            "system": system,
            "user": user if iteration == 0 else None,
            "tools": tools,
        }
        if messages:
            generate_kwargs["messages"] = messages

        # Call LLM (through budget enforcer if provided)
        if budget_enforcer is not None:
            response = await budget_enforcer.generate(**generate_kwargs)
        else:
            response = await client.generate(**generate_kwargs)

        # Track tokens
        usage = getattr(response, "usage", None)
        if usage:
            total_tokens += getattr(usage, "total_tokens", 0)

        # Parse tool calls
        parsed_calls = parse_tool_calls_from_response(response)
        content = getattr(response, "content", "") or ""

        if not parsed_calls:
            # No tool calls — loop complete
            return ToolLoopResult(
                content=content,
                tool_calls_made=all_tool_calls,
                iterations=iteration + 1,
                total_tokens=total_tokens,
            )

        # Sort tool calls by dependency order if graph provided
        if tool_dependencies is not None:
            ordered_names = tool_dependencies.execution_order(
                [tc.name for tc in parsed_calls],
            )
            name_to_calls: dict[str, list[ParsedToolCall]] = {}
            for tc in parsed_calls:
                name_to_calls.setdefault(tc.name, []).append(tc)
            sorted_calls: list[ParsedToolCall] = []
            for name in ordered_names:
                sorted_calls.extend(name_to_calls.get(name, []))
            parsed_calls = sorted_calls

        # Execute tool calls
        completed_tools: set[str] = set()
        for tc in parsed_calls:
            # Dependency check
            if tool_dependencies is not None:
                if not tool_dependencies.can_execute(tc.name, completed_tools):
                    result = ToolCallResult(
                        tool_name=tc.name,
                        arguments=tc.arguments,
                        error=f"unmet dependency for {tc.name}",
                    )
                    all_tool_calls.append(result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps({"error": result.error}, default=str),
                    })
                    continue

            if audit_log:
                audit_log.append(
                    run_id="",
                    actor="tool_loop",
                    action="TOOL_INVOKED",
                    metadata={"tool": tc.name, "arguments": tc.arguments},
                )

            result = await tool_registry.aexecute(tc.name, tc.arguments)
            all_tool_calls.append(result)

            if result.error is not None:
                # Track consecutive failures for backoff
                tool_failures[tc.name] = tool_failures.get(tc.name, 0) + 1
                fail_count = tool_failures[tc.name]

                # Apply exponential backoff on transient failures
                if fail_count < 3:
                    delay = _tool_backoff_delay(fail_count)
                    if delay > 0.01:
                        await asyncio.sleep(delay)
            else:
                # Reset on success
                tool_failures.pop(tc.name, None)
                completed_tools.add(tc.name)

            if audit_log:
                action = "TOOL_COMPLETED" if result.error is None else "TOOL_FAILED"
                audit_log.append(
                    run_id="",
                    actor="tool_loop",
                    action=action,
                    metadata={
                        "tool": tc.name,
                        "duration_ms": result.duration_ms,
                        "error": result.error,
                    },
                )

            # Inject tool result as a message for the next LLM call
            result_content = json.dumps(
                result.result if result.error is None else {"error": result.error},
                default=str,
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_content,
                }
            )

        # Convergence check: use number of tool calls as activity metric.
        # A decreasing number of tool calls signals the agent is converging.
        if detector is not None:
            conv_state = detector.check(float(len(parsed_calls)))
            if conv_state.converged:
                return ToolLoopResult(
                    content=content,
                    tool_calls_made=all_tool_calls,
                    iterations=iteration + 1,
                    total_tokens=total_tokens,
                    converged=True,
                    convergence_reason=conv_state.reason,
                )

    # Max iterations reached
    return ToolLoopResult(
        content=content,
        tool_calls_made=all_tool_calls,
        iterations=max_iterations,
        total_tokens=total_tokens,
    )
