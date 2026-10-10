"""Pure helpers shared by the symbolic benchmark runner and its unit tests."""

from __future__ import annotations

from typing import Any

from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)


def make_directed_edge(src: str, dst: str) -> CausalEdge:
    """Build a directed tail-to-arrow edge."""
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)


def make_bidirected_edge(src: str, dst: str) -> CausalEdge:
    """Build a bidirected arrow-to-arrow edge."""
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)


def make_dag(
    edges: list[tuple[str, str]],
    *,
    extra_nodes: tuple[str, ...] = (),
) -> CausalGraphModel:
    """Build a DAG model with unique, sorted nodes."""
    nodes = sorted({node for pair in edges for node in pair} | set(extra_nodes))
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=nodes,
        edges=[make_directed_edge(src, dst) for src, dst in edges],
    )


def make_admg(
    nodes: list[str],
    edges: list[CausalEdge],
    *,
    metadata: dict[str, Any] | None = None,
) -> CausalGraphModel:
    """Build an ADMG model with the supplied nodes, edges, and metadata."""
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=nodes,
        edges=edges,
        metadata=metadata or {},
    )


def canon(text: str | None) -> str | None:
    """Normalize LaTeX output for benchmark comparison."""
    if text is None:
        return None
    return text.replace(" ", "").replace(".0", "")


def latex_from_result(result: object) -> str | None:
    """Extract LaTeX from an identification or transportability result."""
    ast = getattr(result, "estimand_ast", None) or getattr(result, "recovery_estimand", None)
    if ast is None:
        return None
    return ast.to_latex()


def rule_names_from_result(result: object) -> list[str]:
    """Extract proof-step rule names from a result object."""
    return [step.rule_name for step in getattr(result, "proof_steps", [])]


def is_rule_subsequence(result: object, expected: tuple[str, ...]) -> bool:
    """Return whether expected proof rules occur in order in the result trace."""
    actual = rule_names_from_result(result)
    expected_index = 0
    for rule in actual:
        if expected_index < len(expected) and rule == expected[expected_index]:
            expected_index += 1
    return expected_index == len(expected)


def y0_available() -> bool:
    """Return whether the optional y0 comparator can be imported."""
    try:
        import y0  # noqa: F401

        return True
    except ImportError:
        return False


def dowhy_available() -> bool:
    """Return whether the optional DoWhy comparator can be imported."""
    try:
        import dowhy  # noqa: F401

        return True
    except ImportError:
        return False
