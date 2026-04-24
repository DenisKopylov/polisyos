"""Shared fixtures and configuration for PolicyOS benchmarks.

Can be used both as a pytest conftest (when running benchmarks as tests)
and as a standalone module importable by benchmark scripts.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap
# Make sure `policy-engine/src` is importable whether running via pytest
# from the repo root or directly as a script.
# ---------------------------------------------------------------------------

_BENCH_DIR = Path(__file__).resolve().parent
_SRC_DIR = _BENCH_DIR.parent / "src"

if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# ---------------------------------------------------------------------------
# Shared graph-builder helpers (mirrored from gold suite)
# ---------------------------------------------------------------------------

from polisyos.ir.analytics.causal_graph import (  # noqa: E402
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
)


def make_directed_edge(src: str, dst: str) -> CausalEdge:
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)


def make_bidirected_edge(src: str, dst: str) -> CausalEdge:
    return CausalEdge(src=src, dst=dst, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW)


def make_dag(
    edges: list[tuple[str, str]],
    *,
    extra_nodes: tuple[str, ...] = (),
) -> CausalGraphModel:
    """Build a DAG CausalGraphModel from a list of (src, dst) pairs."""
    nodes = sorted({n for pair in edges for n in pair} | set(extra_nodes))
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=nodes,
        edges=[make_directed_edge(s, d) for s, d in edges],
    )


def make_admg(
    nodes: list[str],
    edges: list[CausalEdge],
    *,
    metadata: dict | None = None,
) -> CausalGraphModel:
    """Build an ADMG CausalGraphModel."""
    return CausalGraphModel(
        graph_type=GraphType.ADMG,
        nodes=nodes,
        edges=edges,
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# Canonicalisation helpers (same as gold suite)
# ---------------------------------------------------------------------------


def canon(text: str | None) -> str | None:
    """Normalise LaTeX output for comparison (strip spaces, remove .0 suffixes)."""
    if text is None:
        return None
    return text.replace(" ", "").replace(".0", "")


def latex_from_result(result: object) -> str | None:
    """Extract LaTeX formula from an IdentificationResult or TransportabilityResult."""
    ast = getattr(result, "estimand_ast", None) or getattr(result, "recovery_estimand", None)
    if ast is None:
        return None
    return ast.to_latex()


def rule_names_from_result(result: object) -> list[str]:
    """Extract proof-step rule names from a result object."""
    return [step.rule_name for step in getattr(result, "proof_steps", [])]


def is_rule_subsequence(result: object, expected: tuple[str, ...]) -> bool:
    """Return True if ``expected`` is a subsequence of the proof-step rule names."""
    actual = rule_names_from_result(result)
    idx = 0
    for rule in actual:
        if idx < len(expected) and rule == expected[idx]:
            idx += 1
    return idx == len(expected)


# ---------------------------------------------------------------------------
# Optional dependency detection
# ---------------------------------------------------------------------------


def y0_available() -> bool:
    """True if the optional y0 library is installed."""
    try:
        import y0  # noqa: F401

        return True
    except ImportError:
        return False


def dowhy_available() -> bool:
    """True if the optional DoWhy library is installed."""
    try:
        import dowhy  # noqa: F401

        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Pytest fixtures (only active when running under pytest)
# ---------------------------------------------------------------------------

try:
    import pytest  # noqa: F401

    @pytest.fixture(scope="session")
    def bench_src_on_path() -> None:
        """Ensure src is on sys.path for the whole test session."""
        # The module-level code above already handles this; fixture is a no-op.

    @pytest.fixture()
    def require_y0(request: pytest.FixtureRequest) -> None:
        """Skip the test if y0 is not installed."""
        if not y0_available():
            pytest.skip("y0 not installed — skipping y0 comparison test")

    @pytest.fixture()
    def require_dowhy(request: pytest.FixtureRequest) -> None:
        """Skip the test if DoWhy is not installed."""
        if not dowhy_available():
            pytest.skip("DoWhy not installed — skipping DoWhy comparison test")

except ImportError:
    # Running outside pytest — fixtures are irrelevant
    pass
