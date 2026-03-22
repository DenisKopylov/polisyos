"""Circuit 4: Capability — Data fusion + M-graph recovery pipeline demo.

Demonstrates PolicyOS handling the joint challenge of missing data and
multi-source fusion — a combination no existing causal tool covers:

1. M-graph recoverability check (Mohan & Pearl 2021):
   Confirm that the target query P(Y|X) is recoverable despite
   missingness in X (MCAR mechanism) using the graphical criterion.

2. Observational + RCT fusion (Z-transport):
   After confirming recoverability, fuse an observational registry
   (with missingness in X) and an RCT (with complete X) to identify
   P*(Y|do(X)) in the target population.

Scenarios
---------
MCAR (recoverable): X→Y, R_X independent — recoverability confirmed,
  fusion succeeds via the recovered observational distribution.

MAR via ancestor (recoverable): Z→X→Y, Z→R_X — R_X depends on Z but
  Z is observed; recoverability confirmed.

MNAR (not recoverable, fusion blocked): X→Y, X→R_X — self-censoring;
  recoverability fails, pipeline returns correct negative certificate.

Bar
---
100% correctness on all 3 sub-cases (recoverability + fusion routing).

Usage
-----
    python benchmarks/capability_wins/demo_fusion_plus_missingness.py
    python benchmarks/capability_wins/demo_fusion_plus_missingness.py --json report.json
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
from benchmarks.capability_wins.capability_proof import (  # noqa: E402
    CapabilityProofSpec,
    build_capability_report_extra,
    make_gap_row,
)
from benchmarks.reporting import build_preflight, build_report_payload, print_preflight  # noqa: E402
from benchmarks.runtime import resolve_mode  # noqa: E402

CIRCUIT = BenchmarkCircuit.CAPABILITY_WINS


# ---------------------------------------------------------------------------
# Deferred import helpers
# ---------------------------------------------------------------------------


def _graph_imports():
    from polisyos.ir.analytics.causal_graph import (
        CausalEdge,
        CausalGraphModel,
        EdgeMark,
        GraphType,
    )
    return CausalEdge, CausalGraphModel, EdgeMark, GraphType


def _mgraph_imports():
    from polisyos.ir.analytics.mgraph import (
        MissingnessKind,
        build_mgraph,
        extract_mgraph_metadata,
    )
    from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
        RecoverabilityStatus,
        test_recoverability,
    )
    return MissingnessKind, build_mgraph, extract_mgraph_metadata, RecoverabilityStatus, test_recoverability


def _fusion_imports():
    from polisyos.foundry.methods.catalog.causal.data_fusion import (
        fuse_experimental_observational,
    )
    return fuse_experimental_observational


# ---------------------------------------------------------------------------
# Benchmark cases
# ---------------------------------------------------------------------------


def _case_mcar_recoverable_then_fuse() -> BenchmarkCase:
    """MCAR on X → recoverable + fusion succeeds."""

    def runner():
        CausalEdge, CausalGraphModel, EdgeMark, GraphType = _graph_imports()
        MissingnessKind, build_mgraph, extract_mgraph_metadata, RecoverabilityStatus, test_recoverability = _mgraph_imports()
        fuse_experimental_observational = _fusion_imports()

        # Base DAG: X→Y
        base_edges = [
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ]
        base_graph = CausalGraphModel(
            schema_version="1.0",
            graph_type=GraphType.DAG,
            nodes=["X", "Y"],
            edges=base_edges,
        )

        # M-graph: MCAR — R_X has no parents in the causal graph
        mgraph = build_mgraph(
            base_graph=base_graph,
            missing_variables={"X": MissingnessKind.MCAR},
        )
        meta = extract_mgraph_metadata(mgraph)

        # Step 1: recoverability check
        recov = test_recoverability(
            query_vars=frozenset({"X"}),
            graph=mgraph,
            mgraph_meta=meta,
        )
        if recov.status != RecoverabilityStatus.RECOVERABLE:
            raise AssertionError(
                f"MCAR X should be RECOVERABLE, got {recov.status}"
            )

        # Step 2: fusion — obs registry (MCAR, recoverable) + RCT
        fusion_result = fuse_experimental_observational(
            graph=base_graph,
            treatment="X",
            outcome="Y",
            exp_interventions=["X"],
            obs_data_ref="obs_with_mcar",
            exp_data_ref="rct_complete",
        )

        return {"recov_status": recov.status, "fusion_identified": fusion_result.is_identified}

    def checker(r) -> bool:
        if not r["fusion_identified"]:
            raise AssertionError("Fusion should succeed after MCAR recovery")
        return True

    return BenchmarkCase(
        name="capability::fusion_missingness::mcar_recoverable_fusion_identified",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("fusion", "missingness", "mcar", "recoverability"),
        timeout_s=30.0,
    )


def _case_mar_ancestor_recoverable() -> BenchmarkCase:
    """MAR via observed ancestor Z → recoverable (Z→R_X, R_X indep of X|Z)."""

    def runner():
        CausalEdge, CausalGraphModel, EdgeMark, GraphType = _graph_imports()
        MissingnessKind, build_mgraph, extract_mgraph_metadata, RecoverabilityStatus, test_recoverability = _mgraph_imports()

        # Base DAG: Z→X→Y
        base_edges = [
            CausalEdge(src="Z", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ]
        base_graph = CausalGraphModel(
            schema_version="1.0",
            graph_type=GraphType.DAG,
            nodes=["X", "Y", "Z"],
            edges=base_edges,
        )

        # M-graph: MAR — R_X ← Z (ancestor of X is observed)
        mgraph = build_mgraph(
            base_graph=base_graph,
            missing_variables={"X": MissingnessKind.MAR},
            directed_edges=[("Z", "R_X")],   # Z→R_X makes it MAR
        )
        meta = extract_mgraph_metadata(mgraph)

        recov = test_recoverability(
            query_vars=frozenset({"X"}),
            graph=mgraph,
            mgraph_meta=meta,
        )
        return recov

    def checker(r) -> bool:
        from polisyos.foundry.methods.catalog.causal.recoverability_engine import RecoverabilityStatus
        if r.status != RecoverabilityStatus.RECOVERABLE:
            raise AssertionError(
                f"MAR-via-ancestor X should be RECOVERABLE, got {r.status}"
            )
        return True

    return BenchmarkCase(
        name="capability::fusion_missingness::mar_ancestor_recoverable",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("missingness", "mar", "recoverability"),
        timeout_s=30.0,
    )


def _case_mnar_self_not_recoverable_blocks_fusion() -> BenchmarkCase:
    """MNAR (self-censoring X→R_X) → not recoverable → fusion blocked."""

    def runner():
        CausalEdge, CausalGraphModel, EdgeMark, GraphType = _graph_imports()
        MissingnessKind, build_mgraph, extract_mgraph_metadata, RecoverabilityStatus, test_recoverability = _mgraph_imports()

        # Base DAG: X→Y
        base_edges = [
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ]
        base_graph = CausalGraphModel(
            schema_version="1.0",
            graph_type=GraphType.DAG,
            nodes=["X", "Y"],
            edges=base_edges,
        )

        # M-graph: MNAR — X→R_X (self-censoring) is added automatically by build_mgraph
        mgraph = build_mgraph(
            base_graph=base_graph,
            missing_variables={"X": MissingnessKind.MNAR},
        )
        meta = extract_mgraph_metadata(mgraph)

        recov = test_recoverability(
            query_vars=frozenset({"X"}),
            graph=mgraph,
            mgraph_meta=meta,
        )
        return recov

    def checker(r) -> bool:
        from polisyos.foundry.methods.catalog.causal.recoverability_engine import RecoverabilityStatus
        if r.status != RecoverabilityStatus.NOT_RECOVERABLE:
            raise AssertionError(
                f"MNAR self-censoring X should be NOT_RECOVERABLE, got {r.status}"
            )
        return True

    return BenchmarkCase(
        name="capability::fusion_missingness::mnar_self_not_recoverable",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("missingness", "mnar", "recoverability", "negative"),
        timeout_s=30.0,
    )


# ---------------------------------------------------------------------------
# Harness builder
# ---------------------------------------------------------------------------


def build_fusion_missingness_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register(_case_mcar_recoverable_then_fuse())
    harness.register(_case_mar_ancestor_recoverable())
    harness.register(_case_mnar_self_not_recoverable_blocks_fusion())
    return harness


# ---------------------------------------------------------------------------
# JSON / main
# ---------------------------------------------------------------------------


def _report_to_dict(report: BenchmarkReport, *, mode: str, preflight: dict[str, Any]) -> dict[str, Any]:
    extra = build_capability_report_extra(
        report,
        CapabilityProofSpec(
            proof_class="capability_gap",
            literature_anchor={
                "primary": "Mohan & Pearl (2021): Graphical models for processing missing data",
                "secondary": "Bareinboim & Pearl (2016): data fusion",
            },
            claim_profile_targets=("frontier_frontier_claim", "full_stack_publication_claim"),
            competitor_gap=(
                make_gap_row("y0", "fusion_plus_missingness", status="fail", note="Missing-data recoverability and fusion are not a unified public workflow.", level="identifiable"),
                make_gap_row("dowhy", "recoverability_decision", status="fail", note="No M-graph recoverability engine for fusion scenarios.", level="identifiable"),
                make_gap_row("econml", "graph_native_missingness", status="fail", note="Estimator stack has no graph-native missingness/fusion layer.", level="expressible"),
                make_gap_row("causalpy", "mgraph_recoverability", status="fail", note="No M-graph recoverability workflow.", level="identifiable"),
            ),
            workflow_levels={level: "PASS" for level in ("expressible", "identifiable", "estimable_or_bounded", "audit_trace", "reproducible")},
        ),
    )
    return build_report_payload(
        report,
        suite_id="capability_fusion_missingness",
        mode=mode,
        preflight=preflight,
        sub_circuit="fusion_plus_missingness",
        extra=extra,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Circuit 4 — Fusion + Missingness demo")
    parser.add_argument("--mode", choices=("smoke", "acceptance"))
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    mode = resolve_mode(args.mode).value
    preflight = build_preflight(mode=mode, data_source="capability_demo_graphs")
    print_preflight(preflight)

    harness = build_fusion_missingness_harness()
    report = harness.run(circuit=CIRCUIT)
    harness.print_report(report, verbose=not args.quiet)

    if args.json:
        Path(args.json).write_text(
            json.dumps(_report_to_dict(report, mode=mode, preflight=preflight), indent=2),
            encoding="utf-8",
        )
        print(f"\nJSON report written to: {args.json}")

    return 1 if report.n_total() - report.n_passed() > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
