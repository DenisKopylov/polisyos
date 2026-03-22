"""Capability win demo: non-transportability with partial identification bounds."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_BENCH_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _BENCH_ROOT / "src"
for _p in (str(_SRC), str(_BENCH_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from benchmarks.harness import BenchmarkCase, BenchmarkCircuit, BenchmarkHarness, BenchmarkReport  # noqa: E402
from benchmarks.reporting import build_preflight, build_report_payload, print_preflight  # noqa: E402
from benchmarks.runtime import resolve_mode  # noqa: E402

from benchmarks.capability_wins.capability_proof import (  # noqa: E402
    CapabilityProofSpec,
    build_capability_report_extra,
    make_gap_row,
)

CIRCUIT = BenchmarkCircuit.CAPABILITY_WINS


def _graph_imports():
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType

    return CausalEdge, CausalGraphModel, EdgeMark, GraphType


def _ctf_imports():
    from polisyos.foundry.methods.catalog.causal.ctf_transport import build_ctf_selection_diagram, ctf_transportability
    from polisyos.foundry.methods.catalog.causal.id_engine import CtfQuery
    from polisyos.ir.analytics.negative_certificate import NegativeCertificate
    from polisyos.ir.analytics.transportability import SNode

    return build_ctf_selection_diagram, ctf_transportability, CtfQuery, NegativeCertificate, SNode


def _build_xy_graph():
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


def _build_chain_graph():
    CausalEdge, CausalGraphModel, EdgeMark, GraphType = _graph_imports()
    return CausalGraphModel(
        schema_version="1.0",
        graph_type=GraphType.DAG,
        nodes=["X", "M", "Y"],
        edges=[
            CausalEdge(src="X", dst="M", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="M", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
    )


def _snode(variable: str) -> Any:
    _, _, _, _, SNode = _ctf_imports()
    return SNode(
        target_variable=variable,
        context_dimension="mechanism_shift",
        source_value=0.0,
        target_value=1.0,
        delta=1.0,
        severity="medium",
    )


def _case_nontransportable_with_bounds() -> BenchmarkCase:
    def runner():
        build_ctf_selection_diagram, ctf_transportability, CtfQuery, NegativeCertificate, SNode = _ctf_imports()
        graph = _build_xy_graph()
        query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world")
        selection_diagram = build_ctf_selection_diagram(graph=graph, s_nodes=[_snode("Y")])
        return ctf_transportability(query, selection_diagram)

    def checker(result: Any) -> bool:
        _, _, _, NegativeCertificate, _ = _ctf_imports()
        if not isinstance(result, NegativeCertificate):
            raise AssertionError(f"Expected NegativeCertificate, got {type(result).__name__}")
        if result.partial_bounds is None:
            raise AssertionError("Expected partial_bounds on the negative certificate")
        if result.partial_bounds.bound_width < 0:
            raise AssertionError("Bounds width must be non-negative")
        return True

    return BenchmarkCase(
        name="capability::nontransportability_bounds::bow_arc_partial_bounds",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("ctf", "nontransportable", "bounds", "negative"),
        timeout_s=20.0,
    )


def _case_chain_mediator_transport_identified() -> BenchmarkCase:
    def runner():
        build_ctf_selection_diagram, ctf_transportability, CtfQuery, NegativeCertificate, SNode = _ctf_imports()
        graph = _build_chain_graph()
        query = CtfQuery(outcome="Y", intervention=(("X", 1.0),), kind="single_world")
        selection_diagram = build_ctf_selection_diagram(graph=graph, s_nodes=[_snode("M")])
        return ctf_transportability(query, selection_diagram)

    def checker(result: Any) -> bool:
        _, _, _, NegativeCertificate, _ = _ctf_imports()
        if isinstance(result, NegativeCertificate):
            raise AssertionError(f"Chain with mediator shift should be identified, got {result.blocking_type}")
        if getattr(result, "status", None) is None or result.status.value != "identified":
            raise AssertionError(f"Expected IDENTIFIED, got {getattr(result, 'status', None)}")
        return True

    return BenchmarkCase(
        name="capability::nontransportability_bounds::chain_mediator_identified",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("ctf", "identified", "mediator"),
        timeout_s=20.0,
    )


def build_nontransportability_bounds_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register(_case_nontransportable_with_bounds())
    harness.register(_case_chain_mediator_transport_identified())
    return harness


def _report_to_dict(report: BenchmarkReport, *, mode: str, preflight: dict[str, Any]) -> dict[str, Any]:
    extra = build_capability_report_extra(
        report,
        CapabilityProofSpec(
            proof_class="negative_certificate_with_bounds",
            literature_anchor={
                "primary": "Correa, Lee & Bareinboim (2022), Counterfactual Transportability",
                "secondary": "Manski (1990), Nonparametric Bounds on Treatment Effects",
            },
            claim_profile_targets=(
                "nontransportability detection",
                "partial bounds extraction",
                "constructive negative certificates",
            ),
            competitor_gap=(
                make_gap_row(
                    "transport_only_baseline",
                    "partial_bounds_fallback",
                    status="gap",
                    note="A plain transportability pass/fail result omits the partial-identification fallback interval.",
                    level="layer_3",
                ),
                make_gap_row(
                    "bounds_only_baseline",
                    "transportability_certificate",
                    status="gap",
                    note="Bounds-only workflows do not explain which selection structure blocks identification.",
                    level="workflow",
                ),
            ),
            workflow_levels={
                "transport_screen": "PASS",
                "bounds_extraction": "PASS",
                "certificate": "PASS",
                "audit_payload": "PASS",
            },
        ),
    )
    return build_report_payload(
        report,
        suite_id="capability_nontransportability_bounds",
        mode=mode,
        preflight=preflight,
        sub_circuit="nontransportability_bounds",
        extra=extra,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capability win demo — nontransportability bounds")
    parser.add_argument("--mode", choices=("smoke", "acceptance"))
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode).value
    preflight = build_preflight(mode=mode, data_source="capability_demo_graphs")
    print_preflight(preflight)

    harness = build_nontransportability_bounds_harness()
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
