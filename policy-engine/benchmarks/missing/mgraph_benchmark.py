"""Circuit 4 (Capability): Missing Data / M-graph recoverability benchmark.

Tests the PolicyOS ``test_recoverability()`` engine against the canonical
recoverability and non-recoverability cases from Mohan & Pearl (2021).

The benchmark is NOT about imputation accuracy — it tests the correctness
of the graph-based recoverability decision: does the system correctly
determine whether P(S) is recoverable from incomplete data P*(V)?

Cases covered
-------------
Recoverable (system must return RECOVERABLE):
  1. MCAR — X→Y, R_X has no parents (MCAR)
  2. MAR_INDEPENDENT — R_X depends on W (independent of X path)
  3. MCAR_BOTH — X→Y, both X and Y are MCAR
  4. MAR_CHAIN — Z→X→Y, R_X from Z (Z is ancestor of X, not descendant)
  5. FULLY_OBSERVED — plain DAG, no R-nodes at all

Not recoverable (system must return NOT_RECOVERABLE):
  6. MNAR_SELF — X→R_X direct (self-affecting missingness)
  7. MNAR_OUTCOME — X→Y, Y→R_Y (outcome MNAR)
  8. MAR_DESCENDANT — X→Y, Y→R_X (Mohan-Pearl: R_X ∈ desc(X) via Y)  ← KEY CASE
  9. MNAR_BOTH — X→Y, both MNAR
  10. MNAR_CHAIN — X→Z→R_X (missingness via chain descendant)

KEY INSIGHT (case 8): "MAR" in the classical definition (R_X doesn't directly
depend on X) does NOT guarantee recoverability.  When R_X depends on a
*descendant* of X (e.g. Y in X→Y, Y→R_X), the Mohan-Pearl criterion detects
non-recoverability because R_X ∈ desc(X) in G[V∪R\\proxy_nodes].

Bar
---
100 % correctness on all recoverability detection cases — the primary bar for
ownable missing-data territory.

References
----------
Mohan, K. & Pearl, J. (2021). Graphical Models for Processing Missing Data.
    JASA.
Mohan, K., Pearl, J. & Tian, J. (2013). Missing Data as a Causal and
    Probabilistic Problem. UAI.

Usage
-----
    python benchmarks/missing/mgraph_benchmark.py
    python benchmarks/missing/mgraph_benchmark.py --json report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------

_BENCH_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _BENCH_ROOT / "src"
for _p in [str(_SRC), str(_BENCH_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from benchmarks.harness import (  # noqa: E402
    BenchmarkCase,
    BenchmarkCircuit,
    BenchmarkHarness,
    BenchmarkReport,
)
from benchmarks.reporting import build_preflight, build_report_payload, print_preflight  # noqa: E402
from benchmarks.runtime import resolve_mode  # noqa: E402

CIRCUIT = BenchmarkCircuit.MISSING


# ---------------------------------------------------------------------------
# Graph / engine imports (deferred to runner to isolate import errors)
# ---------------------------------------------------------------------------


def _imports() -> tuple[Any, Any, Any, Any, Any, Any]:
    from polisyos.ir.analytics.mgraph import (  # noqa: PLC0415
        MissingnessKind,
        build_mgraph,
        extract_mgraph_metadata,
    )
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import (  # noqa: PLC0415
        RecoverabilityStatus,
        test_recoverability,
    )
    from polisyos.ir.analytics.causal_graph import (  # noqa: PLC0415
        CausalEdge,
        CausalGraphModel,
        GraphType,
    )
    return (MissingnessKind, build_mgraph, extract_mgraph_metadata,
            RecoverabilityStatus, test_recoverability, CausalGraphModel)


# ---------------------------------------------------------------------------
# Case definitions
# ---------------------------------------------------------------------------


def _build_case(
    *,
    name: str,
    description: str,
    build_graph_fn: Any,            # () -> CausalGraphModel
    query_vars_fn: Any,             # (graph) -> frozenset[str]
    expected_status_str: str,       # "recoverable" | "not_recoverable"
    tags: tuple[str, ...] = (),
) -> BenchmarkCase:
    def runner() -> dict[str, Any]:
        (MissingnessKind, build_mgraph, extract_mgraph_metadata,
         RecoverabilityStatus, test_recoverability, _) = _imports()

        graph = build_graph_fn(MissingnessKind, build_mgraph)
        meta = extract_mgraph_metadata(graph)
        query_vars = query_vars_fn(meta)

        result = test_recoverability(
            query_vars=query_vars,
            graph=graph,
            mgraph_meta=meta,
        )
        return {
            "status": result.status.value,
            "blocking_r_nodes": sorted(result.blocking_r_nodes),
            "expected": expected_status_str,
            "case_name": name,
        }

    def checker(r: dict[str, Any]) -> bool:
        got = r["status"]
        exp = r["expected"]
        if got != exp:
            blocking = r["blocking_r_nodes"]
            raise AssertionError(
                f"{name}: expected recoverability={exp!r}, got {got!r}"
                + (f" (blocking: {blocking})" if blocking else "")
            )
        return True

    return BenchmarkCase(
        name=f"mgraph::{name}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("mgraph", "recoverability") + tags,
        timeout_s=10.0,
    )


# ---------------------------------------------------------------------------
# Individual M-graph case factories
# ---------------------------------------------------------------------------


def _case_mcar_simple() -> BenchmarkCase:
    """MCAR: X→Y, R_X has no parents → RECOVERABLE."""
    def build(M, bm):
        return bm(
            substantive_vars=["X", "Y"],
            directed_edges=[("X", "Y")],
            missingness_map={"X": M.MCAR},
        )
    def qv(meta): return frozenset(v.target_variable for v in meta.r_nodes)
    return _build_case(
        name="mcar_simple",
        description="X→Y, R_X MCAR (no parents) — trivially recoverable",
        build_graph_fn=build, query_vars_fn=qv,
        expected_status_str="recoverable",
        tags=("mcar",),
    )


def _case_mar_independent() -> BenchmarkCase:
    """MAR from independent W: W→R_X, W has no path from X → RECOVERABLE."""
    def build(M, bm):
        # Graph: X→Y, W→R_X  (W is exogenous — no edge from X to W or R_X via X)
        return bm(
            substantive_vars=["X", "Y", "W"],
            directed_edges=[("X", "Y"), ("W", "R_X")],
            missingness_map={"X": M.MAR},
        )
    def qv(meta): return frozenset(["X"])
    return _build_case(
        name="mar_independent_w",
        description="X→Y, W→R_X (W exogenous) — R_X not in desc(X) → RECOVERABLE",
        build_graph_fn=build, query_vars_fn=qv,
        expected_status_str="recoverable",
        tags=("mar",),
    )


def _case_mcar_both() -> BenchmarkCase:
    """Both X and Y MCAR: X→Y → RECOVERABLE for both."""
    def build(M, bm):
        return bm(
            substantive_vars=["X", "Y"],
            directed_edges=[("X", "Y")],
            missingness_map={"X": M.MCAR, "Y": M.MCAR},
        )
    def qv(meta): return frozenset(v.target_variable for v in meta.r_nodes)
    return _build_case(
        name="mcar_both",
        description="X→Y, both MCAR → RECOVERABLE",
        build_graph_fn=build, query_vars_fn=qv,
        expected_status_str="recoverable",
        tags=("mcar",),
    )


def _case_mar_chain() -> BenchmarkCase:
    """MAR chain: Z→X→Y, R_X from Z (Z is ancestor of X, not descendant).

    desc(X) = {Y}.  R_X depends on Z via Z→R_X edge.
    Z is not a descendant of X, so the path X→...→R_X does NOT exist.
    → RECOVERABLE.
    """
    def build(M, bm):
        return bm(
            substantive_vars=["Z", "X", "Y"],
            directed_edges=[("Z", "X"), ("X", "Y"), ("Z", "R_X")],
            missingness_map={"X": M.MAR},
        )
    def qv(meta): return frozenset(["X"])
    return _build_case(
        name="mar_chain_from_ancestor",
        description="Z→X→Y, Z→R_X (Z is ancestor of X) → RECOVERABLE",
        build_graph_fn=build, query_vars_fn=qv,
        expected_status_str="recoverable",
        tags=("mar",),
    )


def _case_fully_observed() -> BenchmarkCase:
    """Plain DAG, no R-nodes — all variables trivially RECOVERABLE."""
    def build(M, bm):
        # Build a plain DAG (no missingness) — no R-nodes added
        return bm(
            substantive_vars=["X", "Y", "Z"],
            directed_edges=[("X", "Y"), ("X", "Z"), ("Y", "Z")],
            missingness_map={},  # no missing variables
        )
    def qv(meta): return frozenset(["X", "Y", "Z"])

    # Special: build_mgraph with empty missingness_map still creates an MGRAPH
    # but with no R-nodes, so all variables are trivially recoverable.
    return _build_case(
        name="fully_observed",
        description="No R-nodes — all variables trivially observable → RECOVERABLE",
        build_graph_fn=build, query_vars_fn=qv,
        expected_status_str="recoverable",
        tags=("trivial",),
    )


def _case_mnar_self() -> BenchmarkCase:
    """MNAR self-loop: X→Y, X→R_X (auto-added) → NOT_RECOVERABLE."""
    def build(M, bm):
        return bm(
            substantive_vars=["X", "Y"],
            directed_edges=[("X", "Y")],
            missingness_map={"X": M.MNAR},
        )
    def qv(meta): return frozenset(["X"])
    return _build_case(
        name="mnar_self",
        description="X→Y, X→R_X (MNAR direct) — R_X ∈ desc(X) → NOT_RECOVERABLE",
        build_graph_fn=build, query_vars_fn=qv,
        expected_status_str="not_recoverable",
        tags=("mnar",),
    )


def _case_mnar_outcome() -> BenchmarkCase:
    """MNAR outcome: X→Y, Y→R_Y (auto-added) → NOT_RECOVERABLE for Y."""
    def build(M, bm):
        return bm(
            substantive_vars=["X", "Y"],
            directed_edges=[("X", "Y")],
            missingness_map={"Y": M.MNAR},
        )
    def qv(meta): return frozenset(["Y"])
    return _build_case(
        name="mnar_outcome",
        description="X→Y, Y→R_Y (outcome MNAR) → NOT_RECOVERABLE",
        build_graph_fn=build, query_vars_fn=qv,
        expected_status_str="not_recoverable",
        tags=("mnar",),
    )


def _case_mar_descendant() -> BenchmarkCase:
    """KEY CASE — Mohan-Pearl insight: MAR on descendant is NOT recoverable.

    Graph: X→Y, Y→R_X  (R_X depends on Y, which is a descendant of X)
    Classical MAR definition: R_X doesn't directly depend on X. ✓
    Mohan-Pearl criterion: R_X ∈ desc(X) via X→Y→R_X.  → NOT_RECOVERABLE.

    This is the crucial case that distinguishes the Mohan-Pearl framework from
    naive missingness classification.
    """
    def build(M, bm):
        return bm(
            substantive_vars=["X", "Y"],
            directed_edges=[("X", "Y"), ("Y", "R_X")],
            missingness_map={"X": M.MAR},
        )
    def qv(meta): return frozenset(["X"])
    return _build_case(
        name="mar_on_descendant",
        description="X→Y, Y→R_X (MAR but R_X in desc(X)) → NOT_RECOVERABLE",
        build_graph_fn=build, query_vars_fn=qv,
        expected_status_str="not_recoverable",
        tags=("mar", "mohan_pearl_key"),
    )


def _case_mnar_both() -> BenchmarkCase:
    """MNAR for both X and Y → NOT_RECOVERABLE."""
    def build(M, bm):
        return bm(
            substantive_vars=["X", "Y"],
            directed_edges=[("X", "Y")],
            missingness_map={"X": M.MNAR, "Y": M.MNAR},
        )
    def qv(meta): return frozenset(v.target_variable for v in meta.r_nodes)
    return _build_case(
        name="mnar_both",
        description="X→Y, both MNAR → NOT_RECOVERABLE",
        build_graph_fn=build, query_vars_fn=qv,
        expected_status_str="not_recoverable",
        tags=("mnar",),
    )


def _case_mnar_chain() -> BenchmarkCase:
    """MNAR via chain: X→Z→R_X (missingness via intermediate descendant)."""
    def build(M, bm):
        # X→Z is a substantive edge; Z→R_X makes R_X a descendant of X via chain.
        # We use MAR kind but add the chain edge manually.
        return bm(
            substantive_vars=["X", "Z", "Y"],
            directed_edges=[("X", "Z"), ("Z", "Y"), ("Z", "R_X")],
            missingness_map={"X": M.MAR},
        )
    def qv(meta): return frozenset(["X"])
    return _build_case(
        name="mnar_via_chain",
        description="X→Z→R_X (chain descendant path) → NOT_RECOVERABLE",
        build_graph_fn=build, query_vars_fn=qv,
        expected_status_str="not_recoverable",
        tags=("mnar", "chain"),
    )


def _case_partial_mnar() -> BenchmarkCase:
    """Partial MNAR: X MCAR (recoverable), Y MNAR (not recoverable).

    Query covers both X and Y → overall NOT_RECOVERABLE because Y blocks it.
    """
    def build(M, bm):
        return bm(
            substantive_vars=["X", "Y"],
            directed_edges=[("X", "Y")],
            missingness_map={"X": M.MCAR, "Y": M.MNAR},
        )
    def qv(meta): return frozenset(v.target_variable for v in meta.r_nodes)
    return _build_case(
        name="partial_mnar",
        description="X MCAR (ok), Y MNAR (blocks) → overall NOT_RECOVERABLE",
        build_graph_fn=build, query_vars_fn=qv,
        expected_status_str="not_recoverable",
        tags=("mnar", "mixed"),
    )


# ---------------------------------------------------------------------------
# Harness builder
# ---------------------------------------------------------------------------


def build_mgraph_harness() -> BenchmarkHarness:
    """Build M-graph recoverability benchmark harness (10 cases, 100% bar)."""
    harness = BenchmarkHarness()
    for case_fn in [
        _case_mcar_simple,
        _case_mar_independent,
        _case_mcar_both,
        _case_mar_chain,
        _case_fully_observed,
        _case_mnar_self,
        _case_mnar_outcome,
        _case_mar_descendant,       # KEY Mohan-Pearl case
        _case_mnar_both,
        _case_mnar_chain,
        _case_partial_mnar,
    ]:
        harness.register(case_fn())
    return harness


# ---------------------------------------------------------------------------
# JSON / main
# ---------------------------------------------------------------------------


def _report_to_dict(
    report: BenchmarkReport,
    *,
    mode: str,
    preflight: dict[str, Any],
) -> dict[str, Any]:
    return build_report_payload(
        report,
        suite_id="missing_mgraph",
        mode=mode,
        preflight=preflight,
        sub_circuit="mgraph_recoverability",
        extra={"bar": "100% correctness on all recoverability detection cases"},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Circuit 4 (Missing) — M-graph recoverability benchmark"
    )
    parser.add_argument("--mode", choices=("smoke", "acceptance"))
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    mode = resolve_mode(args.mode).value
    preflight = build_preflight(mode=mode, data_source="canonical_mgraph_suite")
    print_preflight(preflight)

    harness = build_mgraph_harness()
    report = harness.run(circuit=CIRCUIT)
    harness.print_report(report, verbose=not args.quiet)

    if args.json:
        Path(args.json).write_text(
            json.dumps(_report_to_dict(report, mode=mode, preflight=preflight), indent=2),
            encoding="utf-8",
        )
        print(f"\nJSON report written to: {args.json}")

    n_failed = report.n_total() - report.n_passed()
    if n_failed > 0:
        print(f"\n[FAIL] {n_failed} recoverability case(s) incorrect — 100% bar required.")
    return 1 if n_failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
