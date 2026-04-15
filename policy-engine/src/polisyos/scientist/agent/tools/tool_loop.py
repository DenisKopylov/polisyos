"""Tool-use execution loop: LLM -> tool calls -> results -> LLM -> ..."""

from __future__ import annotations

import asyncio
import copy
import json
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from polisyos.common.logger import get_logger
from polisyos.scientist.agent.reflexion_evaluator import (
    ReflexionScorecard,
    RubricReflexionEvaluator,
    build_reflexion_summary_text,
)
from polisyos.scientist.error_semantics import emit_degraded_path

from .registry import ToolCallResult, ToolRegistry

if TYPE_CHECKING:
    from polisyos.scientist.engine.convergence import ConvergenceConfig

    from .dependency_graph import ToolDependencyGraph

logger = get_logger(__name__)

_COMPACTION_NOTICE_MARKER = "TOOL TRANSCRIPT COMPACTION NOTICE"


@dataclass
class ToolLoopResult:
    """Final result of a tool-use loop."""

    content: str
    tool_calls_made: list[ToolCallResult] = field(default_factory=list)
    iterations: int = 0
    total_tokens: int = 0
    converged: bool = False
    convergence_reason: str = ""
    final_score: float = 0.0
    evaluation_history: list[dict[str, Any]] = field(default_factory=list)
    retrieved_memories: list[str] = field(default_factory=list)
    degraded_events: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ParsedToolCall:
    """A single tool call extracted from an LLM response."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolLoopCompactionConfig:
    """Transcript compaction policy for long-running tool loops."""

    max_messages: int = 48
    max_transcript_chars: int = 80_000
    keep_recent_tool_results: int = 6
    compacted_tool_result_chars: int = 1200
    compacted_assistant_chars: int = 800


def parse_tool_calls_from_response(
    response: Any,
    *,
    degraded_events: list[dict[str, Any]] | None = None,
) -> list[ParsedToolCall]:
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
        except (json.JSONDecodeError, TypeError) as exc:
            _tool_loop_degraded(
                operation="parse_tool_calls",
                reason="tool_arguments_parse_failed",
                exc=exc,
                degraded_events=degraded_events,
                details={
                    "tool_call_id": str(tc.get("id", "")),
                    "tool_name": str(fn.get("name", "")),
                },
            )
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


def _tool_loop_degraded(
    *,
    operation: str,
    reason: str,
    exc: BaseException,
    degraded_events: list[dict[str, Any]] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    envelope = emit_degraded_path(
        component="agent.tool_loop",
        operation=operation,
        reason=reason,
        exc=exc,
        details=details,
        log=logger,
    )
    if degraded_events is not None:
        degraded_events.append(envelope)
    return envelope


def _is_transient_tool_error(result: ToolCallResult) -> bool:
    return result.error is not None and result.error_type in {
        "timeout",
        "handler_error",
        "circuit_breaker_open",
    }


def _dependency_layers(
    parsed_calls: list[ParsedToolCall],
    tool_dependencies: "ToolDependencyGraph | None",
) -> list[list[ParsedToolCall]]:
    if tool_dependencies is None:
        return [list(parsed_calls)] if parsed_calls else []

    ordered_names = tool_dependencies.execution_order([tc.name for tc in parsed_calls])
    name_to_calls: dict[str, list[ParsedToolCall]] = {}
    for tc in parsed_calls:
        name_to_calls.setdefault(tc.name, []).append(tc)

    ordered_calls: list[ParsedToolCall] = []
    for name in ordered_names:
        ordered_calls.extend(name_to_calls.get(name, []))

    requested_names = {tc.name for tc in ordered_calls}
    completed_names: set[str] = set()
    pending = list(ordered_calls)
    layers: list[list[ParsedToolCall]] = []

    while pending:
        layer: list[ParsedToolCall] = []
        remaining: list[ParsedToolCall] = []
        for tc in pending:
            dependencies = [
                dep
                for dep in tool_dependencies.edges.get(tc.name, [])
                if dep in requested_names
            ]
            if all(dep in completed_names for dep in dependencies):
                layer.append(tc)
            else:
                remaining.append(tc)
        if not layer:
            unresolved = ", ".join(tc.name for tc in remaining)
            raise ValueError(f"cyclic tool dependencies detected: {unresolved}")
        layers.append(layer)
        completed_names.update(tc.name for tc in layer)
        pending = remaining

    return layers


def _dependencies_satisfied(
    tool_name: str,
    *,
    completed_tools: set[str],
    requested_tools: set[str],
    tool_dependencies: "ToolDependencyGraph | None",
) -> bool:
    if tool_dependencies is None:
        return True
    for dep in tool_dependencies.edges.get(tool_name, []):
        if dep in requested_tools and dep not in completed_tools:
            return False
    return True


async def _execute_tool_call(
    *,
    tool_registry: ToolRegistry,
    tool_call: ParsedToolCall,
    ready_at_by_tool: dict[str, float],
) -> ToolCallResult:
    ready_at = ready_at_by_tool.get(tool_call.name)
    if ready_at is not None:
        delay = ready_at - asyncio.get_running_loop().time()
        if delay > 0:
            await asyncio.sleep(delay)
    return await tool_registry.aexecute(tool_call.name, tool_call.arguments)


def _build_initial_messages(system: str, user: str) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    return messages


def _append_assistant_tool_call_message(
    *,
    messages: list[dict[str, Any]],
    content: str,
    parsed_calls: list[ParsedToolCall],
) -> None:
    messages.append(
        {
            "role": "assistant",
            "content": content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, default=str),
                    },
                }
                for tc in parsed_calls
            ],
        }
    )


def _tool_error_payload(result: ToolCallResult) -> dict[str, Any]:
    payload: dict[str, Any] = {"error": result.error}
    if result.error_type:
        payload["error_type"] = result.error_type
    if result.error_details is not None:
        payload["error_details"] = result.error_details
    return payload


def _score_loop_progress(
    *,
    content: str,
    tool_calls: list[ToolCallResult],
    reflexion_evaluator: RubricReflexionEvaluator | None,
    objective: str,
    previous_scorecard: ReflexionScorecard | None,
) -> tuple[float, ReflexionScorecard | None, bool, str]:
    """Score one loop state using rubric/evidence signals."""
    if reflexion_evaluator is None:
        success_count = sum(1 for item in tool_calls if item.error is None)
        tool_success_ratio = success_count / max(len(tool_calls), 1)
        content_score = min(1.0, len((content or "").strip()) / 240.0)
        evidence_count = len(_extract_citations_from_tool_calls(tool_calls))
        evidence_score = min(1.0, evidence_count / 3.0)
        score = 0.45 * tool_success_ratio + 0.35 * content_score + 0.20 * evidence_score
        return score, None, False, ""

    scorecard = reflexion_evaluator.evaluate_candidate(
        objective=objective,
        output_text=content or "",
        output_data={},
        citations=_extract_citations_from_tool_calls(tool_calls),
        tool_results=tool_calls,
    )
    should_stop, reason = reflexion_evaluator.should_stop(scorecard, previous_scorecard)
    return scorecard.overall_score, scorecard, should_stop, reason


def _feedback_message_from_scorecard(scorecard: ReflexionScorecard) -> str:
    feedback = scorecard.retry_advice.strip()
    if not feedback:
        feedback = (
            "Revise the answer with stronger task coverage, source grounding, "
            "and schema correctness."
        )
    return (
        "REFLEXION EVALUATOR FEEDBACK\n"
        f"Overall score: {scorecard.overall_score:.3f}\n"
        f"Blocking issues: {', '.join(scorecard.blocking_issues) or 'none'}\n"
        f"Retry instruction: {feedback}"
    )


def _extract_citations_from_tool_calls(
    tool_calls: list[ToolCallResult],
) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for item in tool_calls:
        if item.error is not None:
            continue
        citations.extend(_extract_citations_from_value(item.result))
    return citations


def _extract_citations_from_value(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        citations: list[dict[str, Any]] = []
        if "citations" in value and isinstance(value["citations"], list):
            for item in value["citations"]:
                if isinstance(item, dict):
                    citations.append(dict(item))
        if "snippets" in value and isinstance(value["snippets"], list):
            for item in value["snippets"]:
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url") or "")
                text = str(item.get("snippet") or item.get("text") or "")
                if url and text:
                    citations.append(
                        {
                            "url": url,
                            "snippet": text,
                            "source_id": str(item.get("source_id") or item.get("snippet_id") or ""),
                        }
                    )
        for nested in value.values():
            if isinstance(nested, (dict, list, tuple)):
                citations.extend(_extract_citations_from_value(nested))
        return citations
    if isinstance(value, (list, tuple)):
        citations = []
        for item in value:
            citations.extend(_extract_citations_from_value(item))
        return citations
    return []


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
    reflexion_evaluator: RubricReflexionEvaluator | None = None,
    compaction_config: ToolLoopCompactionConfig | None = None,
    tool_discovery_threshold: int = 24,
    tool_discovery_max_tools: int = 12,
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

    registry_size = len(tool_registry.list_definitions())
    if registry_size > max(0, int(tool_discovery_threshold)):
        tools = tool_registry.to_openai_tools(
            query_text=user,
            max_tools=max(1, int(tool_discovery_max_tools)),
        )
    else:
        tools = tool_registry.to_openai_tools()
    messages: list[dict[str, Any]] = []
    all_tool_calls: list[ToolCallResult] = []
    total_tokens = 0
    content = ""
    previous_scorecard: ReflexionScorecard | None = None
    evaluation_history: list[dict[str, Any]] = []
    retrieved_memories: list[str] = []
    degraded_events: list[dict[str, Any]] = []

    detector: ConvergenceDetector | None = None
    if convergence_config is not None:
        detector = ConvergenceDetector(convergence_config)

    # Per-tool consecutive failure tracking (for backoff)
    tool_failures: dict[str, int] = {}
    tool_retry_ready_at: dict[str, float] = {}
    completed_iterations = 0
    remaining_budget_fn = getattr(budget_enforcer, "remaining_budget", None)
    initial_remaining_budget: float | None = None
    if callable(remaining_budget_fn):
        try:
            raw_remaining = remaining_budget_fn()
            if asyncio.iscoroutine(raw_remaining):
                raw_remaining = await raw_remaining
        except Exception as exc:
            _tool_loop_degraded(
                operation="remaining_budget",
                reason="initial_budget_probe_failed",
                exc=exc,
                degraded_events=degraded_events,
            )
            raw_remaining = None
        if raw_remaining is not None:
            try:
                initial_remaining_budget = float(raw_remaining)
            except (TypeError, ValueError):
                initial_remaining_budget = None

    # Inject prior knowledge from persistent memory
    if persistent_memory is not None:
        try:
            from polisyos.scientist.agent.persistent_memory import MemoryQuery
            if hasattr(persistent_memory, "recall_reflexion_memories"):
                prior_entries = persistent_memory.recall_reflexion_memories(
                    problem_statement=user,
                    max_results=10,
                )
            else:
                prior_entries = persistent_memory.query(
                    MemoryQuery(query_text=user[:500], max_results=10),
                )
            if prior_entries:
                memory_block = persistent_memory.format_for_prompt(prior_entries)
                system = f"{system}\n\n{memory_block}"
                retrieved_memories = [entry.content for entry in prior_entries]
        except Exception as exc:
            _tool_loop_degraded(
                operation="persistent_memory_recall",
                reason="memory_injection_failed",
                exc=exc,
                degraded_events=degraded_events,
                details={"query_chars": len(user)},
            )

    messages = _build_initial_messages(system, user)

    for iteration in range(max_iterations):
        # Adaptive max iterations: shrink ceiling based on budget usage
        if iteration > 0 and initial_remaining_budget is not None and callable(remaining_budget_fn):
            try:
                remaining_value = remaining_budget_fn()
                if asyncio.iscoroutine(remaining_value):
                    remaining_value = await remaining_value
            except Exception as exc:
                _tool_loop_degraded(
                    operation="remaining_budget",
                    reason="adaptive_budget_probe_failed",
                    exc=exc,
                    degraded_events=degraded_events,
                    details={"iteration": iteration + 1},
                )
                remaining_value = None
            if remaining_value is not None:
                try:
                    current_remaining_budget = max(0.0, float(remaining_value))
                except (TypeError, ValueError):
                    current_remaining_budget = None
                if current_remaining_budget is not None:
                    consumed_budget = max(
                        0.0,
                        initial_remaining_budget - current_remaining_budget,
                    )
                    if consumed_budget > 0:
                        avg_budget_per_iter = consumed_budget / iteration
                        if current_remaining_budget < avg_budget_per_iter:
                            logger.debug(
                                "Adaptive iteration cap reached remaining_budget={:.6f} "
                                "avg_budget_per_iter={:.6f}",
                                current_remaining_budget,
                                avg_budget_per_iter,
                            )
                            break

        # Build generate kwargs
        generate_kwargs: dict[str, Any] = {
            "messages": copy.deepcopy(messages),
            "tools": tools,
        }

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
        parsed_calls = parse_tool_calls_from_response(
            response,
            degraded_events=degraded_events,
        )
        content = getattr(response, "content", "") or ""

        if not parsed_calls:
            score, scorecard, should_stop, stop_reason = _score_loop_progress(
                content=content,
                tool_calls=all_tool_calls,
                reflexion_evaluator=reflexion_evaluator,
                objective=user,
                previous_scorecard=previous_scorecard,
            )
            if scorecard is not None:
                evaluation_history.append(scorecard.model_dump(mode="json"))
                if persistent_memory is not None and not scorecard.passed:
                    try:
                        persistent_memory.store_reflexion_memory(
                            problem_statement=user,
                            reflection=build_reflexion_summary_text(
                                objective=user,
                                scorecard=scorecard,
                                failure_summary="low-scoring no-tool-call answer",
                                remediation=scorecard.retry_advice,
                            ),
                            trajectory_summary=(
                                f"iteration={iteration + 1}; "
                                f"score={scorecard.overall_score:.3f}; "
                                f"content={content[:500]}"
                            ),
                            source_run_id="tool_loop",
                            source_node_alias="tool_loop",
                            tool_error_patterns=scorecard.tool_error_patterns,
                            confidence=max(0.1, min(1.0, scorecard.overall_score)),
                        )
                    except Exception as exc:
                        _tool_loop_degraded(
                            operation="persistent_memory_store",
                            reason="reflexion_memory_store_failed",
                            exc=exc,
                            degraded_events=degraded_events,
                            details={"iteration": iteration + 1},
                        )
                if (
                    reflexion_evaluator is not None
                    and not should_stop
                    and iteration + 1 < max_iterations
                ):
                    messages.append({"role": "assistant", "content": content})
                    messages.append(
                        {
                            "role": "user",
                            "content": _feedback_message_from_scorecard(scorecard),
                        }
                    )
                    previous_scorecard = scorecard
                    continue
                previous_scorecard = scorecard

            # No tool calls and stop policy allows exit.
            completed_iterations = iteration + 1
            return ToolLoopResult(
                content=content,
                tool_calls_made=all_tool_calls,
                iterations=completed_iterations,
                total_tokens=total_tokens,
                converged=should_stop,
                convergence_reason=stop_reason,
                final_score=score,
                evaluation_history=evaluation_history,
                retrieved_memories=retrieved_memories,
                degraded_events=degraded_events,
            )

        for call_index, tc in enumerate(parsed_calls):
            if not tc.id:
                tc.id = f"tool-call-{iteration + 1}-{call_index + 1}"

        _append_assistant_tool_call_message(
            messages=messages,
            content=content,
            parsed_calls=parsed_calls,
        )

        # Execute tool calls
        completed_tools: set[str] = set()
        requested_tools = {tc.name for tc in parsed_calls}
        for layer in _dependency_layers(parsed_calls, tool_dependencies):
            immediate_results: dict[str, ToolCallResult] = {}
            executable_calls: list[ParsedToolCall] = []
            for tc in layer:
                if not _dependencies_satisfied(
                    tc.name,
                    completed_tools=completed_tools,
                    requested_tools=requested_tools,
                    tool_dependencies=tool_dependencies,
                ):
                    immediate_results[tc.id] = ToolCallResult(
                        tool_name=tc.name,
                        arguments=tc.arguments,
                        error=f"unmet dependency for {tc.name}",
                        error_type="unmet_dependency",
                        error_details={"tool_name": tc.name},
                    )
                    continue

                if audit_log:
                    audit_log.append(
                        run_id="",
                        actor="tool_loop",
                        action="TOOL_INVOKED",
                        metadata={"tool": tc.name, "arguments": tc.arguments},
                    )
                executable_calls.append(tc)

            executed_results = await asyncio.gather(
                *[
                    _execute_tool_call(
                        tool_registry=tool_registry,
                        tool_call=tc,
                        ready_at_by_tool=tool_retry_ready_at,
                    )
                    for tc in executable_calls
                ],
                return_exceptions=True,
            ) if executable_calls else []
            executed_by_id = {
                tc.id: (
                    result
                    if isinstance(result, ToolCallResult)
                    else ToolCallResult(
                        tool_name=tc.name,
                        arguments=tc.arguments,
                        error=f"{type(result).__name__}: {result}",
                        error_type="task_exception",
                        error_details={"tool_call_id": tc.id},
                    )
                )
                for tc, result in zip(executable_calls, executed_results, strict=True)
            }

            for tc in layer:
                result = immediate_results.get(tc.id) or executed_by_id.get(tc.id)
                if result is None:
                    result = ToolCallResult(
                        tool_name=tc.name,
                        arguments=tc.arguments,
                        error="tool execution did not produce a result",
                        error_type="missing_result",
                        error_details={"tool_call_id": tc.id},
                    )
                all_tool_calls.append(result)

                if result.error is None:
                    tool_failures.pop(tc.name, None)
                    tool_retry_ready_at.pop(tc.name, None)
                    completed_tools.add(tc.name)
                elif _is_transient_tool_error(result):
                    fail_count = tool_failures.get(tc.name, 0) + 1
                    tool_failures[tc.name] = fail_count
                    if fail_count < 3:
                        tool_retry_ready_at[tc.name] = (
                            asyncio.get_running_loop().time() + _tool_backoff_delay(fail_count)
                        )
                else:
                    tool_failures.pop(tc.name, None)
                    tool_retry_ready_at.pop(tc.name, None)

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

                result_content = json.dumps(
                    result.result if result.error is None else _tool_error_payload(result),
                    default=str,
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_content,
                    }
                )

        completed_iterations = iteration + 1

        # Convergence check over score/evidence signals rather than raw tool-call count.
        if detector is not None:
            score, scorecard, should_stop, stop_reason = _score_loop_progress(
                content=content,
                tool_calls=all_tool_calls,
                reflexion_evaluator=reflexion_evaluator,
                objective=user,
                previous_scorecard=previous_scorecard,
            )
            if scorecard is not None:
                evaluation_history.append(scorecard.model_dump(mode="json"))
                previous_scorecard = scorecard
            conv_state = detector.check(score)
            if conv_state.converged:
                return ToolLoopResult(
                    content=content,
                    tool_calls_made=all_tool_calls,
                    iterations=completed_iterations,
                    total_tokens=total_tokens,
                    converged=True,
                    convergence_reason=stop_reason or conv_state.reason,
                    final_score=score,
                    evaluation_history=evaluation_history,
                    retrieved_memories=retrieved_memories,
                    degraded_events=degraded_events,
                )
            if should_stop:
                return ToolLoopResult(
                    content=content,
                    tool_calls_made=all_tool_calls,
                    iterations=completed_iterations,
                    total_tokens=total_tokens,
                    converged=True,
                    convergence_reason=stop_reason,
                    final_score=score,
                    evaluation_history=evaluation_history,
                    retrieved_memories=retrieved_memories,
                    degraded_events=degraded_events,
                )
        elif reflexion_evaluator is not None:
            score, scorecard, should_stop, stop_reason = _score_loop_progress(
                content=content,
                tool_calls=all_tool_calls,
                reflexion_evaluator=reflexion_evaluator,
                objective=user,
                previous_scorecard=previous_scorecard,
            )
            if scorecard is not None:
                evaluation_history.append(scorecard.model_dump(mode="json"))
                previous_scorecard = scorecard
            if should_stop:
                return ToolLoopResult(
                    content=content,
                    tool_calls_made=all_tool_calls,
                    iterations=completed_iterations,
                    total_tokens=total_tokens,
                    converged=True,
                    convergence_reason=stop_reason,
                    final_score=score,
                    evaluation_history=evaluation_history,
                    retrieved_memories=retrieved_memories,
                    degraded_events=degraded_events,
                )

        if compaction_config is not None:
            _compact_tool_transcript(messages, compaction_config)

    # Max iterations reached
    return ToolLoopResult(
        content=content,
        tool_calls_made=all_tool_calls,
        iterations=completed_iterations,
        total_tokens=total_tokens,
        final_score=(previous_scorecard.overall_score if previous_scorecard is not None else 0.0),
        evaluation_history=evaluation_history,
        retrieved_memories=retrieved_memories,
        degraded_events=degraded_events,
    )


def _compact_tool_transcript(
    messages: list[dict[str, Any]],
    config: ToolLoopCompactionConfig,
) -> None:
    """Compact old assistant/tool messages in-place while preserving transcript shape."""
    if len(messages) <= 2:
        return
    total_chars = _transcript_chars(messages)
    if len(messages) <= config.max_messages and total_chars <= config.max_transcript_chars:
        return

    tool_indexes = [
        index
        for index, message in enumerate(messages)
        if message.get("role") == "tool"
    ]
    preserved_tool_indexes = set(tool_indexes[-config.keep_recent_tool_results:])
    compacted_rounds = 0
    scan_start = _compaction_prefix_length(messages)
    dropped_messages = 0

    for index, message in enumerate(messages[scan_start:], start=scan_start):
        role = message.get("role")
        if role == "tool" and index not in preserved_tool_indexes:
            raw_content = str(message.get("content") or "")
            if '"compacted_tool_result": true' not in raw_content:
                message["content"] = json.dumps(
                    {
                        "compacted_tool_result": True,
                        "original_chars": len(raw_content),
                        "preview": _truncate_text(
                            raw_content,
                            config.compacted_tool_result_chars,
                        ),
                    },
                    ensure_ascii=True,
                )
                compacted_rounds += 1
        elif role == "assistant" and "tool_calls" not in message:
            message["content"] = _truncate_text(
                str(message.get("content") or ""),
                config.compacted_assistant_chars,
            )

    summary_index = _compaction_summary_index(messages)
    summary_exists = (
        summary_index < len(messages)
        and messages[summary_index].get("role") == "system"
        and _COMPACTION_NOTICE_MARKER
        in str(messages[summary_index].get("content") or "")
    )

    reserve_summary_slots = 0 if summary_exists else 1
    if len(messages) + reserve_summary_slots > config.max_messages:
        tail_budget = max(
            2,
            config.max_messages - scan_start - reserve_summary_slots,
        )
        drop_until = max(scan_start, len(messages) - tail_budget)
        while drop_until < len(messages) and messages[drop_until].get("role") == "tool":
            drop_until += 1
        if drop_until > scan_start:
            dropped_messages = drop_until - scan_start
            del messages[scan_start:drop_until]

    if compacted_rounds <= 0 and dropped_messages <= 0:
        return
    summary_parts = [
        _COMPACTION_NOTICE_MARKER,
        (
            f"Older tool outputs were compacted in-place across {compacted_rounds} "
            "tool message(s)."
        ),
    ]
    if dropped_messages > 0:
        summary_parts.append(
            f"Dropped {dropped_messages} stale transcript message(s) beyond the tail window."
        )
    summary_parts.append("Recent tool outputs and all retained tool_call IDs were kept.")
    summary = {
        "role": "system",
        "content": "\n".join(summary_parts),
    }
    if (
        len(messages) > summary_index
        and messages[summary_index].get("role") == "system"
        and _COMPACTION_NOTICE_MARKER
        in str(messages[summary_index].get("content") or "")
    ):
        messages[summary_index] = summary
    else:
        messages.insert(summary_index, summary)


def _transcript_chars(messages: list[dict[str, Any]]) -> int:
    total = 0
    for message in messages:
        total += len(str(message.get("content") or ""))
        for tc in message.get("tool_calls") or []:
            if isinstance(tc, dict):
                fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                total += len(str(fn.get("arguments") or ""))
                total += len(str(fn.get("name") or ""))
    return total


def _truncate_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    if max_chars <= 3:
        return value[:max_chars]
    return value[: max_chars - 3] + "..."


def _compaction_prefix_length(messages: list[dict[str, Any]]) -> int:
    """Return the protected prompt/notice prefix length."""
    index = 0
    if (
        index < len(messages)
        and messages[index].get("role") == "system"
        and _COMPACTION_NOTICE_MARKER
        not in str(messages[index].get("content") or "")
    ):
        index += 1
    if (
        index < len(messages)
        and messages[index].get("role") == "system"
        and _COMPACTION_NOTICE_MARKER
        in str(messages[index].get("content") or "")
    ):
        index += 1
    if index < len(messages) and messages[index].get("role") == "user":
        index += 1
    return max(1, index)


def _compaction_summary_index(messages: list[dict[str, Any]]) -> int:
    """Return the insertion/replacement index for the compaction notice."""
    if (
        messages
        and messages[0].get("role") == "system"
        and _COMPACTION_NOTICE_MARKER
        in str(messages[0].get("content") or "")
    ):
        return 0
    if messages and messages[0].get("role") == "system":
        return 1
    return 0
