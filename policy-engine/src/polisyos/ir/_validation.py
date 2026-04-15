"""Shared invariant helpers for IR contracts.

These helpers are intentionally small and dependency-light so governance,
kernel, observation, and analytics contracts can share one message policy for
common invariant categories.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Collection, Iterable, Sequence
from decimal import Decimal, InvalidOperation
from typing import TypeVar

from polisyos.ir.types import SelectorOperator

T = TypeVar("T")
K = TypeVar("K", str, int, float, bool, Decimal, tuple)

MAX_SELECTOR_FIELD_DEPTH = 8
MAX_SELECTOR_COLLECTION_ITEMS = 64


def ensure_unique_ids(
    items: Iterable[T],
    key_fn: Callable[[T], K],
    label: str,
) -> None:
    """Raise when ``items`` contain duplicate keys derived via ``key_fn``."""

    seen: set[K] = set()
    for item in items:
        key = key_fn(item)
        if key in seen:
            raise ValueError(f"duplicate {label}: {key}")
        seen.add(key)


def ensure_finite_numeric(value: object, *, field_name: str) -> object:
    """Raise when ``value`` cannot be interpreted as a finite numeric scalar."""

    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ValueError(f"{field_name} must be finite") from exc
    if not math.isfinite(numeric):
        raise ValueError(f"{field_name} must be finite")
    return value


def ensure_interval_monotonicity(
    start: object | None,
    end: object | None,
    *,
    label: str,
    start_name: str | None = None,
    end_name: str | None = None,
) -> None:
    """Raise when ``end < start`` for comparable interval endpoints."""

    if start is None or end is None:
        return
    try:
        inverted = end < start
    except TypeError as exc:
        raise ValueError(f"{label} endpoints must be comparable") from exc
    if inverted:
        if start_name is not None and end_name is not None:
            raise ValueError(f"{end_name} must be >= {start_name}")
        raise ValueError(f"{label} lower bound cannot exceed upper bound")


def ensure_confidence_interval(
    bounds: tuple[object, object],
    *,
    label: str,
    point_estimate: object | None = None,
    point_label: str = "point_estimate",
) -> None:
    """Validate finite, monotone confidence/bounds intervals."""

    lower, upper = bounds
    ensure_finite_numeric(lower, field_name=f"{label} lower bound")
    ensure_finite_numeric(upper, field_name=f"{label} upper bound")
    ensure_interval_monotonicity(lower, upper, label=label)
    if point_estimate is None:
        return
    ensure_finite_numeric(point_estimate, field_name=point_label)
    point = float(point_estimate)
    if not (float(lower) <= point <= float(upper)):
        raise ValueError(f"{point_label} must lie inside {label}")


def ensure_non_empty_path(
    path: Sequence[str],
    *,
    label: str,
    max_depth: int | None = None,
) -> tuple[str, ...]:
    """Normalize and validate a sequence of path segments."""

    if isinstance(path, str) or not path:
        raise ValueError(f"{label} must be a non-empty path")
    normalized = tuple(str(segment).strip() for segment in path)
    if any(not segment for segment in normalized):
        raise ValueError(f"{label} contains empty path segment")
    if max_depth is not None and len(normalized) > max_depth:
        raise ValueError(f"{label} depth {len(normalized)} exceeds limit {max_depth}")
    return normalized


def ensure_non_empty_dotted_path(
    value: str,
    *,
    field_name: str,
    max_depth: int | None = None,
) -> str:
    """Normalize and validate a dot-delimited path string."""

    candidate = str(value).strip()
    if not candidate or candidate.startswith(".") or candidate.endswith(".") or ".." in candidate:
        raise ValueError(f"{field_name} must be a non-empty dotted path")
    segments = ensure_non_empty_path(
        candidate.split("."),
        label=field_name,
        max_depth=max_depth,
    )
    return ".".join(segments)


def ensure_pairwise_disjoint(
    groups: Sequence[tuple[str, Collection[K]]],
    *,
    label: str,
) -> None:
    """Raise when the collections in ``groups`` overlap."""

    seen: dict[K, str] = {}
    for group_name, values in groups:
        for value in values:
            if value in seen:
                raise ValueError(
                    f"{label} must be pairwise disjoint; {value!r} appears in "
                    f"{seen[value]} and {group_name}"
                )
            seen[value] = group_name


def ensure_disjoint_sets(
    left: Collection[K],
    right: Collection[K],
    *,
    label: str,
) -> None:
    """Raise when two collections have non-empty intersection."""

    shared = sorted(set(left) & set(right), key=repr)
    if shared:
        raise ValueError(f"{label} must be disjoint; overlapping={shared}")


def selector_stats(node: object) -> tuple[int, int]:
    """Compute selector AST depth and node count using the public shape only."""

    kind = getattr(node, "kind", None)
    if kind == "predicate":
        return 1, 1
    if kind == "not":
        depth, nodes = selector_stats(getattr(node, "clause"))
        return depth + 1, nodes + 1
    if kind == "quantifier":
        depth, nodes = selector_stats(getattr(node, "clause"))
        return depth + 1, nodes + 1
    if kind == "temporal":
        depth, nodes = selector_stats(getattr(node, "clause"))
        return depth + 1, nodes + 1
    if kind == "aggregate":
        where = getattr(node, "where")
        if where is None:
            return 1, 1
        depth, nodes = selector_stats(where)
        return depth + 1, nodes + 1
    if kind in {"all_of", "any_of"}:
        depths: list[int] = []
        total = 1
        for clause in getattr(node, "clauses"):
            depth, nodes = selector_stats(clause)
            depths.append(depth)
            total += nodes
        return (max(depths) + 1 if depths else 1), total
    return 1, 1


def validate_selector_expr(
    node: object,
    *,
    label: str,
    max_depth: int,
    max_nodes: int,
) -> None:
    """Validate selector AST size limits."""

    depth, nodes = selector_stats(node)
    if depth > max_depth:
        raise ValueError(f"Selector depth {depth} in {label} exceeds limit {max_depth}")
    if nodes > max_nodes:
        raise ValueError(f"Selector nodes {nodes} in {label} exceeds limit {max_nodes}")


def validate_selector_predicate_shape(
    *,
    field: str,
    operator: SelectorOperator,
    value: object,
    max_field_depth: int = MAX_SELECTOR_FIELD_DEPTH,
    max_collection_items: int = MAX_SELECTOR_COLLECTION_ITEMS,
) -> None:
    """Validate selector operator/value combinations and field-path guardrails."""

    ensure_non_empty_dotted_path(
        field,
        field_name="selector field",
        max_depth=max_field_depth,
    )

    if operator in {
        SelectorOperator.EQUALS,
        SelectorOperator.NOT_EQUALS,
    }:
        if isinstance(value, list):
            raise ValueError(f"operator '{operator.value}' requires a scalar value")
        return

    if operator in {
        SelectorOperator.GREATER_THAN,
        SelectorOperator.LESS_THAN,
        SelectorOperator.GREATER_EQUAL,
        SelectorOperator.LESS_EQUAL,
    }:
        if isinstance(value, list) or not _is_numeric_selector_scalar(value):
            raise ValueError(f"operator '{operator.value}' requires a numeric scalar value")
        return

    if operator in {
        SelectorOperator.IN,
        SelectorOperator.NOT_IN,
        SelectorOperator.CONTAINS,
    }:
        if not isinstance(value, list) or not value:
            raise ValueError(f"operator '{operator.value}' requires a non-empty list")
        if len(value) > max_collection_items:
            raise ValueError(
                f"operator '{operator.value}' list size {len(value)} exceeds limit "
                f"{max_collection_items}"
            )
        ensure_unique_ids(value, key_fn=lambda item: item, label=f"selector {operator.value} value")
        return

    if operator is SelectorOperator.BETWEEN:
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError("operator 'between' requires a list of two values")
        lower, upper = value
        if _is_numeric_selector_scalar(lower) and _is_numeric_selector_scalar(upper):
            ensure_interval_monotonicity(lower, upper, label="selector between")
            return
        if type(lower) is not type(upper):
            raise ValueError("operator 'between' requires comparable boundary types")
        ensure_interval_monotonicity(lower, upper, label="selector between")


def validate_selector_quantifier_shape(
    *,
    collection_field: str,
    quantifier: object,
    threshold: int | None,
    max_field_depth: int = MAX_SELECTOR_FIELD_DEPTH,
) -> None:
    """Validate quantifier field/path and threshold policy."""

    ensure_non_empty_dotted_path(
        collection_field,
        field_name="selector collection_field",
        max_depth=max_field_depth,
    )
    normalized = getattr(quantifier, "value", str(quantifier))
    if normalized in {"exists", "for_all"}:
        if threshold is not None:
            raise ValueError(f"quantifier '{normalized}' does not accept threshold")
        return
    if threshold is None:
        raise ValueError(f"quantifier '{normalized}' requires threshold")


def validate_selector_aggregation_shape(
    *,
    collection_field: str,
    aggregation: object,
    value_field: str | None,
    operator: SelectorOperator,
    value: object,
    max_field_depth: int = MAX_SELECTOR_FIELD_DEPTH,
) -> None:
    """Validate aggregation selector policy."""

    ensure_non_empty_dotted_path(
        collection_field,
        field_name="selector collection_field",
        max_depth=max_field_depth,
    )
    normalized = getattr(aggregation, "value", str(aggregation))
    if normalized == "count":
        if value_field is not None:
            ensure_non_empty_dotted_path(
                value_field,
                field_name="selector value_field",
                max_depth=max_field_depth,
            )
    else:
        if value_field is None:
            raise ValueError(f"aggregation '{normalized}' requires value_field")
        ensure_non_empty_dotted_path(
            value_field,
            field_name="selector value_field",
            max_depth=max_field_depth,
        )
    validate_selector_predicate_shape(
        field=value_field or collection_field,
        operator=operator,
        value=value,
        max_field_depth=max_field_depth,
    )


def validate_selector_temporal_shape(
    *,
    clock_field: str | None,
    lower_bound: int,
    upper_bound: int | None,
    max_field_depth: int = MAX_SELECTOR_FIELD_DEPTH,
) -> None:
    """Validate selector temporal-window policy."""

    if lower_bound < 0:
        raise ValueError("selector temporal lower_bound must be >= 0")
    if upper_bound is not None and upper_bound < lower_bound:
        raise ValueError("selector temporal upper_bound must be >= lower_bound")
    if clock_field is not None:
        ensure_non_empty_dotted_path(
            clock_field,
            field_name="selector clock_field",
            max_depth=max_field_depth,
        )


def _is_numeric_selector_scalar(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, Decimal)):
        return True
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return False
        try:
            Decimal(candidate)
        except InvalidOperation:
            return False
        return True
    return False
