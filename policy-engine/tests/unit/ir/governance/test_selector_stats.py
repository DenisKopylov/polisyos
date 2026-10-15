from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.ir._internal.validation import (
    selector_stats,
    validate_selector_expr,
)
from polisyos.ir.governance.selector_expr import (
    SelectorAggregate,
    SelectorAll,
    SelectorAny,
    SelectorExpr,
    SelectorNot,
    SelectorPredicate,
    SelectorQuantifier,
    SelectorTemporalPredicate,
)


class _UnhashableSelectorKind(str):
    __hash__ = None


def _predicate() -> SelectorPredicate:
    return SelectorPredicate(kind="predicate", field="status", operator="==", value="active")


def _selector_tree() -> SelectorExpr:
    predicate = _predicate()
    return SelectorAll(
        clauses=[
            SelectorAny(clauses=[predicate, SelectorNot(clause=predicate)]),
            SelectorQuantifier(
                quantifier="exists",
                collection_field="members",
                clause=predicate,
            ),
            SelectorAggregate(
                aggregation="count",
                collection_field="members",
                operator=">=",
                value=1,
                where=SelectorTemporalPredicate(
                    temporal_operator="eventually_within",
                    clause=predicate,
                    upper_bound=3,
                    clock_field="time.step",
                ),
            ),
            SelectorTemporalPredicate(
                temporal_operator="eventually_within",
                clause=SelectorNot(clause=predicate),
                upper_bound=3,
                clock_field="time.step",
            ),
        ]
    )


def test_selector_stats_walks_every_canonical_node_type() -> None:
    selector = _selector_tree()

    assert selector_stats(selector) == (4, 13)
    validate_selector_expr(selector, label="policy selector", max_depth=4, max_nodes=13)


def test_selector_stats_enforces_depth_and_node_boundaries() -> None:
    selector = _selector_tree()

    with pytest.raises(ValueError, match="Selector depth 4"):
        validate_selector_expr(selector, label="policy selector", max_depth=3, max_nodes=13)
    with pytest.raises(ValueError, match="Selector nodes 13"):
        validate_selector_expr(selector, label="policy selector", max_depth=4, max_nodes=12)


def test_selector_stats_preserves_public_shape_dispatch() -> None:
    # `selector_stats` intentionally consumes the public shape, not class identity.
    wrapped = SimpleNamespace(kind="not", clause=_predicate())

    assert selector_stats(wrapped) == (2, 2)
    validate_selector_expr(wrapped, label="shape-compatible selector", max_depth=2, max_nodes=2)


def test_selector_stats_preserves_unhashable_string_subclass_dispatch() -> None:
    wrapped = SimpleNamespace(kind=_UnhashableSelectorKind("not"), clause=_predicate())

    assert selector_stats(wrapped) == (2, 2)
    validate_selector_expr(wrapped, label="shape-compatible selector", max_depth=2, max_nodes=2)
