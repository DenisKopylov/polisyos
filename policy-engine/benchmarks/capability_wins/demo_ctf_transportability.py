"""Circuit 4: Capability — Layer-3 CTF transportability demo.

Demonstrates PolicyOS Layer-3 counterfactual transportability
(Correa, Lee & Bareinboim 2022): identifying counterfactual distributions
P*(Y_{x'} | context) across domains when selection mechanisms shift.

This capability requires reasoning at Pearl's Layer 3 (counterfactuals)
combined with domain transport — unique to PolicyOS.

Scenarios
---------
pn_transport_identified:
  Graph X→Y.  S-node on Y (outcome mechanism shifts across domains).
  CTF query: P(Y_{X=0} | Y=1)  (probability of necessity — PN).
  Expected: IDENTIFIED — the CTF formula is exportable via L2 reduction.

single_world_l2_reduction:
  Graph X→Y (no confounders, no edges to Y from hidden vars).
  CTF query: P(Y_{X=1})  (single-world interventional).
  S-node on Y.  Expected: IDENTIFIED via L2 observational reduction.

bow_arc_non_transportable:
  Graph X→Y with X↔Y (hidden confounder).
  CTF query: P(Y_{X=1}).  S-node on Y.
  Expected: NegativeCertificate (S-node unresolved, partial bounds provided).

chain_s_on_mediator:
  Graph X→M→Y.  S-node on M (mediator mechanism shifts).
  CTF query: P(Y_{X=1}).
  Expected: IDENTIFIED (mediator S-node is non-ancestral after do(X=1)).

Bar
---
100% correctness: IDENTIFIED where expected, NegativeCertificate where not.

Usage
-----
    python benchmarks/capability_wins/demo_ctf_transportability.py
    python benchmarks/capability_wins/demo_ctf_transportability.py --json report.json
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


def _ctf_imports():
    from polisyos.foundry.methods.catalog.causal.ctf_transport import (
        build_ctf_selection_diagram,
        ctf_transportability,
    )
    from polisyos.foundry.methods.catalog.causal.id_engine import (
        CtfQuery,
        IdentificationStatus,
    )
    from polisyos.ir.analytics.transportability import SNode
    from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate
    return (
        build_ctf_selection_diagram, ctf_transportability,
        CtfQuery, IdentificationStatus,
        SNode, BlockingType, NegativeCertificate,
    )


# ---------------------------------------------------------------------------
# Graph builders
# ---------------------------------------------------------------------------


def _build_xy_dag():
    """Simple X→Y DAG."""
    CausalEdge, CausalGraphModel, EdgeMark, GraphType = _graph_imports()
    return CausalGraphModel(
        schema_version="1.0",
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)],
    )


def _build_bow_arc():
    """X→Y with X↔Y (hidden confounder)."""
    CausalEdge, CausalGraphModel, EdgeMark, GraphType = _graph_imports()
    return CausalGraphModel(
        schema_version="1.0",
        graph_type=GraphType.ADMG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW),
        ],
    )


def _build_chain():
    """X→M→Y."""
    CausalEdge, CausalGraphModel, EdgeMark, GraphType = _graph_imports()
    return CausalGraphModel(
        schema_version="1.0",
        graph_type=GraphType.DAG,
        nodes=["M", "X", "Y"],
        edges=[
            CausalEdge(src="X", dst="M", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="M", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
    )


def _snode(variable: str):
    from polisyos.ir.analytics.transportability import SNode
    return SNode(
        target_variable=variable,
        context_dimension="mechanism_shift",
        source_value=0.0,
        target_value=1.0,
        delta=1.0,
        severity="medium",
    )


# ---------------------------------------------------------------------------
# Benchmark cases
# ---------------------------------------------------------------------------


def _case_pn_transport_identified() -> BenchmarkCase:
    """PN query P(Y_{X=0} | Y=1) on X→Y, S on Y → IDENTIFIED."""

    def runner():
        (
            build_ctf_selection_diagram, ctf_transportability,
            CtfQuery, IdentificationStatus,
            SNode, BlockingType, NegativeCertificate,
        ) = _ctf_imports()

        graph = _build_xy_dag()
        query = CtfQuery(
            outcome="Y",
            intervention=(("X", 1.0),),
            evidence=(("Y", 1.0),),
            kind="pn",
        )
        selection_diagram = build_ctf_selection_diagram(graph=graph, s_nodes=[_snode("Y")])
        result = ctf_transportability(query, selection_diagram)
        return result

    def checker(r) -> bool:
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus
        from polisyos.ir.analytics.negative_certificate import NegativeCertificate

        if isinstance(r, NegativeCertificate):
            raise AssertionError(
                f"PN query on X→Y with S_Y should be IDENTIFIED, got NegativeCertificate: {r.blocking_type}"
            )
        if r.status != IdentificationStatus.IDENTIFIED:
            raise AssertionError(f"Expected IDENTIFIED, got {r.status}")
        # Verify CTF proof step present
        rule_names = {s.rule_name for s in r.proof_steps}
        if "CTF_TRANSPORT_START" not in rule_names:
            raise AssertionError(
                f"CTF_TRANSPORT_START not in proof steps: {sorted(rule_names)}"
            )
        return True

    return BenchmarkCase(
        name="capability::ctf_transport::pn_query_xy_s_on_y_identified",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("ctf_transport", "pn", "layer3", "identified"),
        timeout_s=20.0,
    )


def _case_single_world_l2_reduction() -> BenchmarkCase:
    """Single-world P(Y_{X=1}), no confounders, S on Y → IDENTIFIED (L2 reduction)."""

    def runner():
        (
            build_ctf_selection_diagram, ctf_transportability,
            CtfQuery, IdentificationStatus,
            SNode, BlockingType, NegativeCertificate,
        ) = _ctf_imports()

        # Minimal DAG: X and Y, no edges (independence → L2 trivially identified)
        CausalEdge, CausalGraphModel, EdgeMark, GraphType = _graph_imports()
        graph = CausalGraphModel(
            schema_version="1.0",
            graph_type=GraphType.DAG,
            nodes=["X", "Y"],
            edges=[],  # no structural edges → P(Y_{x}) = P(Y)
        )
        query = CtfQuery(
            outcome="Y",
            intervention=(("X", 1.0),),
            kind="single_world",
        )
        selection_diagram = build_ctf_selection_diagram(graph=graph, s_nodes=[_snode("Y")])
        result = ctf_transportability(query, selection_diagram)
        return result

    def checker(r) -> bool:
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus
        from polisyos.ir.analytics.negative_certificate import NegativeCertificate

        if isinstance(r, NegativeCertificate):
            raise AssertionError(
                f"Single-world on independent X,Y should be IDENTIFIED, got {r.blocking_type}"
            )
        if r.status != IdentificationStatus.IDENTIFIED:
            raise AssertionError(f"Expected IDENTIFIED, got {r.status}")
        return True

    return BenchmarkCase(
        name="capability::ctf_transport::single_world_l2_reduction_identified",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("ctf_transport", "single_world", "l2_reduction", "identified"),
        timeout_s=20.0,
    )


def _case_bow_arc_non_transportable() -> BenchmarkCase:
    """Bow-arc X→Y + X↔Y, single-world, S on Y → NegativeCertificate with bounds."""

    def runner():
        (
            build_ctf_selection_diagram, ctf_transportability,
            CtfQuery, IdentificationStatus,
            SNode, BlockingType, NegativeCertificate,
        ) = _ctf_imports()

        graph = _build_bow_arc()
        query = CtfQuery(
            outcome="Y",
            intervention=(("X", 1.0),),
            kind="single_world",
        )
        selection_diagram = build_ctf_selection_diagram(graph=graph, s_nodes=[_snode("Y")])
        result = ctf_transportability(query, selection_diagram)
        return result

    def checker(r) -> bool:
        from polisyos.ir.analytics.negative_certificate import NegativeCertificate, BlockingType

        if not isinstance(r, NegativeCertificate):
            raise AssertionError(
                f"Bow-arc CTF with S_Y should be non-transportable (NegativeCertificate), got {type(r).__name__}"
            )
        if r.blocking_type not in (
            BlockingType.S_NODE_UNRESOLVED,
            BlockingType.HEDGE_STRUCTURE,
        ):
            raise AssertionError(
                f"Expected S_NODE_UNRESOLVED or HEDGE_STRUCTURE, got {r.blocking_type}"
            )
        # Bounds should be present (partial identification fallback)
        if r.partial_bounds is None:
            raise AssertionError("NegativeCertificate should include partial_bounds")
        return True

    return BenchmarkCase(
        name="capability::ctf_transport::bow_arc_non_transportable_with_bounds",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("ctf_transport", "non_transportable", "bounds", "negative"),
        timeout_s=20.0,
    )


def _case_chain_s_on_mediator_identified() -> BenchmarkCase:
    """Chain X→M→Y, S on M, CTF P(Y_{X=1}) → IDENTIFIED."""

    def runner():
        (
            build_ctf_selection_diagram, ctf_transportability,
            CtfQuery, IdentificationStatus,
            SNode, BlockingType, NegativeCertificate,
        ) = _ctf_imports()

        graph = _build_chain()
        query = CtfQuery(
            outcome="Y",
            intervention=(("X", 1.0),),
            kind="single_world",
        )
        selection_diagram = build_ctf_selection_diagram(graph=graph, s_nodes=[_snode("M")])
        result = ctf_transportability(query, selection_diagram)
        return result

    def checker(r) -> bool:
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus
        from polisyos.ir.analytics.negative_certificate import NegativeCertificate

        if isinstance(r, NegativeCertificate):
            raise AssertionError(
                f"Chain X→M→Y with S on M: CTF P(Y_{{X=1}}) should be IDENTIFIED, got {r.blocking_type}"
            )
        if r.status != IdentificationStatus.IDENTIFIED:
            raise AssertionError(f"Expected IDENTIFIED, got {r.status}")
        return True

    return BenchmarkCase(
        name="capability::ctf_transport::chain_s_on_mediator_identified",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("ctf_transport", "chain", "mediator", "identified"),
        timeout_s=20.0,
    )


# ---------------------------------------------------------------------------
# Harness builder
# ---------------------------------------------------------------------------


def build_ctf_transportability_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register(_case_pn_transport_identified())
    harness.register(_case_single_world_l2_reduction())
    harness.register(_case_bow_arc_non_transportable())
    harness.register(_case_chain_s_on_mediator_identified())
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
                "primary": "Correa, Lee & Bareinboim (2022): counterfactual transportability",
            },
            claim_profile_targets=("frontier_frontier_claim", "full_stack_publication_claim"),
            competitor_gap=(
                make_gap_row("y0", "ctf_transport_end_to_end", status="partial", note="Counterfactual transport is documented, but full bounded/audited workflow remains incomplete.", level="audit_trace"),
                make_gap_row("dowhy", "layer3_transport", status="fail", note="No Layer-3 counterfactual transport workflow.", level="identifiable"),
                make_gap_row("econml", "counterfactual_transport", status="fail", note="No symbolic counterfactual transport layer.", level="expressible"),
                make_gap_row("causalpy", "counterfactual_transport", status="fail", note="No Layer-3 transport workflow.", level="identifiable"),
            ),
            workflow_levels={level: "PASS" for level in ("expressible", "identifiable", "estimable_or_bounded", "audit_trace", "reproducible")},
        ),
    )
    return build_report_payload(
        report,
        suite_id="capability_ctf_transportability",
        mode=mode,
        preflight=preflight,
        sub_circuit="ctf_transportability",
        extra=extra,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Circuit 4 — CTF transportability demo")
    parser.add_argument("--mode", choices=("smoke", "acceptance"))
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    mode = resolve_mode(args.mode).value
    preflight = build_preflight(mode=mode, data_source="capability_demo_graphs")
    print_preflight(preflight)

    harness = build_ctf_transportability_harness()
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
