"""Bounded classification of evaluation exception graphs."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from polisyos.core.errors import ErrorCategory, PolicyOSError

EXCEPTION_CHAIN_NODE_LIMIT = 64
"""Maximum distinct exceptions retained while classifying one failure."""

EXCEPTION_CHAIN_EDGE_LIMIT = 256
"""Maximum cause, context, and exception-group links traversed per failure."""

EvaluationFailureScope = Literal["transient", "sample_domain", "global", "unknown"]


@dataclass(frozen=True)
class EvaluationFailureClassification:
    """Describe the bounded evidence available for one evaluation failure."""

    scope: EvaluationFailureScope
    chain: tuple[BaseException, ...]
    chain_complete: bool
    cycle_detected: bool


def _exception_children(exc: BaseException) -> Iterator[BaseException]:
    """Yield the directed cause, context, and group-member links of an exception."""
    if exc.__cause__ is not None:
        yield exc.__cause__
    if exc.__context__ is not None:
        yield exc.__context__
    if isinstance(exc, BaseExceptionGroup):
        yield from exc.exceptions


def _exception_graph(
    exc: BaseException,
) -> tuple[tuple[BaseException, ...], bool, bool]:
    """Traverse a bounded exception graph, allowing shared descendants but detecting cycles."""
    chain: list[BaseException] = []
    visited: set[int] = set()
    active: set[int] = set()
    stack: list[tuple[BaseException, Iterator[BaseException] | None]] = [(exc, None)]
    edge_count = 0
    chain_complete = True
    cycle_detected = False

    while stack:
        current, children = stack[-1]
        if children is None:
            current_id = id(current)
            if current_id in active:
                cycle_detected = True
                stack.pop()
                continue
            if current_id in visited:
                stack.pop()
                continue
            if len(chain) >= EXCEPTION_CHAIN_NODE_LIMIT:
                chain_complete = False
                break
            visited.add(current_id)
            active.add(current_id)
            chain.append(current)
            stack[-1] = (current, iter(_exception_children(current)))
            continue

        try:
            child = next(children)
        except StopIteration:
            active.remove(id(current))
            stack.pop()
            continue

        edge_count += 1
        if edge_count > EXCEPTION_CHAIN_EDGE_LIMIT:
            chain_complete = False
            break
        child_id = id(child)
        if child_id in active:
            cycle_detected = True
            continue
        if child_id in visited:
            continue
        stack.append((child, None))

    return tuple(chain), chain_complete, cycle_detected


def classify_evaluation_failure(
    exc: BaseException,
    *,
    sample_domain_error_type: type[BaseException] | None = None,
    additional_global_error_types: tuple[type[BaseException], ...] = (),
) -> EvaluationFailureClassification:
    """Classify explicit retry, input-domain, and global evaluation failures.

    Known global failures anywhere in the bounded graph take precedence. A typed
    sample-domain or transient classification is accepted only for the root
    exception and only when its graph is complete and acyclic. All other cases,
    including cycles and truncated graphs, remain unknown.
    """
    chain, chain_complete, cycle_detected = _exception_graph(exc)

    global_types = (OSError, ValidationError, *additional_global_error_types)
    for cause in chain:
        if isinstance(cause, global_types):
            scope: EvaluationFailureScope = "global"
            break
        if isinstance(cause, PolicyOSError) and cause.category in {
            ErrorCategory.FATAL,
            ErrorCategory.VALIDATION,
        }:
            scope = "global"
            break
    else:
        if cycle_detected or not chain_complete:
            scope = "unknown"
        elif sample_domain_error_type is not None and isinstance(exc, sample_domain_error_type):
            scope = "sample_domain"
        elif isinstance(exc, PolicyOSError) and exc.category is ErrorCategory.TRANSIENT:
            scope = "transient"
        else:
            scope = "unknown"

    return EvaluationFailureClassification(
        scope=scope,
        chain=chain,
        chain_complete=chain_complete,
        cycle_detected=cycle_detected,
    )
