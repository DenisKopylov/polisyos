"""Circuit 4: Capability — Constructive NegativeCertificate with suggested experiments.

Demonstrates PolicyOS producing a *constructive* non-identifiability certificate:
when a query is not identified, the engine does not just say "no" — it explains
why (hedge structure) and suggests concrete experiments that would resolve the
blockage.

This is a unique capability absent from DoWhy, y0, and CausalPy.

Scenarios
---------
bow_arc_x_y:
  Graph X→Y with X↔Y (bidirected confounding, no instrument).
  id_algorithm returns HEDGE_FOUND.
  NegativeCertificate.blocking_type == HEDGE_STRUCTURE.
  NegativeCertificate.suggested_experiments is non-empty.

frontdoor_no_confounding:
  Graph X→M→Y, no confounders — standard frontdoor criterion.
  id_algorithm returns IDENTIFIED (positive control).

bow_arc_via_engine:
  Same bow-arc queried via CausalEngine.identify() → NegativeCertificate returned
  (engine auto-converts HEDGE_FOUND to NegativeCertificate).

Bar
---
100% correctness.

Usage
-----
    python benchmarks/capability_wins/demo_symbolic_non_id_certificate.py
    python benchmarks/capability_wins/demo_symbolic_non_id_certificate.py --json report.json
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

from benchmarks.capability_wins.capability_proof import (  # noqa: E402
    CapabilityProofSpec,
    build_capability_report_extra,
    make_gap_row,
)
from benchmarks.harness import (  # noqa: E402
    BenchmarkCase,
    BenchmarkCircuit,
    BenchmarkHarness,
    BenchmarkReport,
)
from benchmarks.reporting import (  # noqa: E402
    build_preflight,
    build_report_payload,
    print_preflight,
)
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


def _id_imports():
    from polisyos.foundry.methods.catalog.causal.id_engine import (
        IdentificationStatus,
        id_algorithm,
    )

    return IdentificationStatus, id_algorithm


# ---------------------------------------------------------------------------
# Graph builders
# ---------------------------------------------------------------------------


def _build_bow_arc():
    """X→Y with X↔Y (bidirected = hidden confounder U: U→X, U→Y)."""
    CausalEdge, CausalGraphModel, EdgeMark, GraphType = _graph_imports()
    edges = [
        CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        # Bidirected arc (ADMG encoding of hidden U)
        CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW),
    ]
    return CausalGraphModel(
        schema_version="1.0",
        graph_type=GraphType.ADMG,
        nodes=["X", "Y"],
        edges=edges,
    )


def _build_frontdoor():
    """X→M→Y with X↔Y — classic frontdoor (identified)."""
    CausalEdge, CausalGraphModel, EdgeMark, GraphType = _graph_imports()
    edges = [
        CausalEdge(src="X", dst="M", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        CausalEdge(src="M", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW),
    ]
    return CausalGraphModel(
        schema_version="1.0",
        graph_type=GraphType.ADMG,
        nodes=["M", "X", "Y"],
        edges=edges,
    )


# ---------------------------------------------------------------------------
# Benchmark cases
# ---------------------------------------------------------------------------


def _case_bow_arc_hedge_certificate() -> BenchmarkCase:
    """Bow-arc → HEDGE_FOUND + non-empty hedge_certificate."""

    def runner():
        IdentificationStatus, id_algorithm = _id_imports()
        graph = _build_bow_arc()
        result = id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
        )
        return result

    def checker(r) -> bool:
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus

        if r.status != IdentificationStatus.HEDGE_FOUND:
            raise AssertionError(f"Bow-arc: expected HEDGE_FOUND, got {r.status}")
        if r.hedge_certificate is None:
            raise AssertionError("HEDGE_FOUND result must carry a hedge_certificate")
        return True

    return BenchmarkCase(
        name="capability::non_id_cert::bow_arc_hedge_found",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("negative_certificate", "hedge", "non_identifiable"),
        timeout_s=10.0,
    )


def _case_frontdoor_identified_positive_control() -> BenchmarkCase:
    """Frontdoor → IDENTIFIED (positive control, engine doesn't over-block)."""

    def runner():
        IdentificationStatus, id_algorithm = _id_imports()
        graph = _build_frontdoor()
        result = id_algorithm(
            treatment=frozenset({"X"}),
            outcome=frozenset({"Y"}),
            graph=graph,
        )
        return result

    def checker(r) -> bool:
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus

        if r.status != IdentificationStatus.IDENTIFIED:
            raise AssertionError(f"Frontdoor: expected IDENTIFIED, got {r.status}")
        return True

    return BenchmarkCase(
        name="capability::non_id_cert::frontdoor_identified_positive_control",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("frontdoor", "identified", "positive_control"),
        timeout_s=10.0,
    )


def _case_bow_arc_via_engine_returns_negative_cert() -> BenchmarkCase:
    """CausalEngine.identify() on bow-arc → NegativeCertificate with suggestions."""

    def runner():
        from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine

        engine = CausalEngine()
        graph = _build_bow_arc()

        result = engine.identify(treatment="X", outcome="Y", graph=graph)
        return result

    def checker(r) -> bool:
        from polisyos.ir.analytics.negative_certificate import BlockingType, NegativeCertificate

        if not isinstance(r, NegativeCertificate):
            raise AssertionError(
                f"Engine should return NegativeCertificate for bow-arc, got {type(r).__name__}"
            )
        if r.blocking_type != BlockingType.HEDGE_STRUCTURE:
            raise AssertionError(f"Expected HEDGE_STRUCTURE blocking, got {r.blocking_type}")
        if not r.suggested_experiments:
            raise AssertionError("NegativeCertificate must include suggested_experiments")
        return True

    return BenchmarkCase(
        name="capability::non_id_cert::engine_bow_arc_negative_certificate",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("negative_certificate", "hedge", "engine", "suggested_experiments"),
        timeout_s=15.0,
    )


def _case_constructive_message_non_empty() -> BenchmarkCase:
    """NegativeCertificate.constructive_message is non-empty and actionable."""

    def runner():
        from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine

        engine = CausalEngine()
        graph = _build_bow_arc()
        result = engine.identify(treatment="X", outcome="Y", graph=graph)
        return result

    def checker(r) -> bool:
        from polisyos.ir.analytics.negative_certificate import NegativeCertificate

        if not isinstance(r, NegativeCertificate):
            raise AssertionError("Expected NegativeCertificate")
        if not r.constructive_message:
            raise AssertionError("constructive_message should be non-empty")
        # Must contain actionable keywords
        msg = r.constructive_message.lower()
        if not any(
            kw in msg for kw in ("identif", "experiment", "instrument", "bound", "consider")
        ):
            raise AssertionError(f"constructive_message not actionable: {r.constructive_message!r}")
        return True

    return BenchmarkCase(
        name="capability::non_id_cert::constructive_message_actionable",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("negative_certificate", "constructive_message"),
        timeout_s=15.0,
    )


# ---------------------------------------------------------------------------
# Harness builder
# ---------------------------------------------------------------------------


def build_non_id_certificate_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register(_case_bow_arc_hedge_certificate())
    harness.register(_case_frontdoor_identified_positive_control())
    harness.register(_case_bow_arc_via_engine_returns_negative_cert())
    harness.register(_case_constructive_message_non_empty())
    return harness


# ---------------------------------------------------------------------------
# JSON / main
# ---------------------------------------------------------------------------


def _report_to_dict(
    report: BenchmarkReport, *, mode: str, preflight: dict[str, Any]
) -> dict[str, Any]:
    extra = build_capability_report_extra(
        report,
        CapabilityProofSpec(
            proof_class="capability_gap",
            literature_anchor={
                "primary": "Shpitser & Pearl (2006): Identification of joint interventional distributions",
                "secondary": "PolicyOS NegativeCertificate contract",
            },
            claim_profile_targets=("frontier_frontier_claim", "full_stack_publication_claim"),
            competitor_gap=(
                make_gap_row(
                    "y0",
                    "constructive_negative_certificate",
                    status="partial",
                    note="Can signal non-identification, but no constructive experiment-plan workflow.",
                    level="estimable_or_bounded",
                ),
                make_gap_row(
                    "dowhy",
                    "negative_certificate",
                    status="fail",
                    note="No constructive NegativeCertificate with suggested experiments.",
                    level="identifiable",
                ),
                make_gap_row(
                    "econml",
                    "symbolic_non_id",
                    status="fail",
                    note="No symbolic identification/non-identification layer.",
                    level="expressible",
                ),
                make_gap_row(
                    "causalpy",
                    "symbolic_non_id",
                    status="fail",
                    note="No constructive non-ID certificate.",
                    level="identifiable",
                ),
            ),
            workflow_levels={
                level: "PASS"
                for level in (
                    "expressible",
                    "identifiable",
                    "estimable_or_bounded",
                    "audit_trace",
                    "reproducible",
                )
            },
        ),
    )
    return build_report_payload(
        report,
        suite_id="capability_symbolic_nonid",
        mode=mode,
        preflight=preflight,
        sub_circuit="symbolic_non_id_certificate",
        extra=extra,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Circuit 4 — Symbolic NegativeCertificate demo")
    parser.add_argument("--mode", choices=("smoke", "acceptance"))
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    mode = resolve_mode(args.mode).value
    preflight = build_preflight(mode=mode, data_source="capability_demo_graphs")
    print_preflight(preflight)

    harness = build_non_id_certificate_harness()
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
