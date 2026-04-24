"""Circuit 5: Reproducibility — 3× repeat → 0 flaky tests.

Runs each benchmark case 3 times and verifies that verdicts are consistent
(no flip between PASS and FAIL across repetitions).  A case is considered
"flaky" if it produces different verdicts in different runs.

This catches non-determinism from:
- Random seed dependency without explicit seeding
- Race conditions or timing-dependent behaviour
- Hash-order non-determinism in Python dicts/sets

Test cases
----------
Each scenario runs 3 identical repetitions of a core algorithmic primitive
and checks that all 3 verdicts agree.

1. id_algorithm on frontdoor: 3 reps all IDENTIFIED.
2. Bow-arc non-ID: 3 reps all HEDGE_FOUND.
3. Cyclic ID on feedback loop: 3 reps same algorithm_version.
4. M-graph recoverability (MCAR): 3 reps all RECOVERABLE.
5. CTF transportability (PN query): 3 reps same status.

Bar
---
All 3 repetitions agree for every case (0 flaky).

Usage
-----
    python benchmarks/reproducibility/test_regression_no_flaky.py
    python benchmarks/reproducibility/test_regression_no_flaky.py --json report.json
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
from benchmarks.reporting import (  # noqa: E402
    build_preflight,
    build_report_payload,
    print_preflight,
)
from benchmarks.runtime import resolve_mode  # noqa: E402

CIRCUIT = BenchmarkCircuit.REPRODUCIBILITY
_N_REPS = 3


# ---------------------------------------------------------------------------
# Deferred graph helpers
# ---------------------------------------------------------------------------


def _build_frontdoor():
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType

    return CausalGraphModel(
        schema_version="1.0",
        graph_type=GraphType.ADMG,
        nodes=["M", "X", "Y"],
        edges=[
            CausalEdge(src="X", dst="M", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="M", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW),
        ],
    )


def _build_bow_arc():
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType

    return CausalGraphModel(
        schema_version="1.0",
        graph_type=GraphType.ADMG,
        nodes=["X", "Y"],
        edges=[
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW),
        ],
    )


def _build_xy_dag():
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType

    return CausalGraphModel(
        schema_version="1.0",
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)],
    )


# ---------------------------------------------------------------------------
# Benchmark cases
# ---------------------------------------------------------------------------


def _case_frontdoor_no_flaky() -> BenchmarkCase:
    """Frontdoor id_algorithm: 3 reps all return IDENTIFIED."""

    def runner():
        from polisyos.foundry.methods.catalog.causal.id_engine import id_algorithm

        graph = _build_frontdoor()
        statuses = [
            id_algorithm(
                treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=graph
            ).status.value
            for _ in range(_N_REPS)
        ]
        return statuses

    def checker(statuses: list) -> bool:
        flaky = [s for s in statuses if s != "identified"]
        if flaky:
            raise AssertionError(f"Frontdoor flaky: expected all 'identified', got {statuses}")
        if len(set(statuses)) != 1:
            raise AssertionError(f"Flaky! {_N_REPS} reps disagree: {statuses}")
        return True

    return BenchmarkCase(
        name="repro::no_flaky::frontdoor_3reps_all_identified",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("no_flaky", "id_algorithm", "frontdoor"),
        timeout_s=60.0,
    )


def _case_bow_arc_no_flaky() -> BenchmarkCase:
    """Bow-arc: 3 reps all return HEDGE_FOUND."""

    def runner():
        from polisyos.foundry.methods.catalog.causal.id_engine import id_algorithm

        graph = _build_bow_arc()
        statuses = [
            id_algorithm(
                treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=graph
            ).status.value
            for _ in range(_N_REPS)
        ]
        return statuses

    def checker(statuses: list) -> bool:
        if len(set(statuses)) != 1:
            raise AssertionError(f"Bow-arc flaky! {_N_REPS} reps disagree: {statuses}")
        if list(set(statuses))[0] != "hedge_found":
            raise AssertionError(f"Expected 'hedge_found', got {list(set(statuses))[0]!r}")
        return True

    return BenchmarkCase(
        name="repro::no_flaky::bow_arc_3reps_all_hedge_found",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("no_flaky", "id_algorithm", "hedge"),
        timeout_s=60.0,
    )


def _case_cyclic_id_no_flaky() -> BenchmarkCase:
    """Cyclic feedback A→B, B→A: 3 reps same algorithm_version."""

    def runner():
        from polisyos.foundry.methods.catalog.causal.cyclic_id import cyclic_id_algorithm
        from polisyos.ir.analytics.causal_graph import (
            CausalEdge,
            CausalGraphModel,
            EdgeMark,
            GraphType,
        )

        graph = CausalGraphModel(
            schema_version="1.0",
            graph_type=GraphType.ADMG,
            nodes=["A", "B"],
            edges=[
                CausalEdge(src="A", dst="B", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
                CausalEdge(src="B", dst="A", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            ],
        )
        versions = [
            cyclic_id_algorithm(
                treatment=frozenset({"A"}), outcome=frozenset({"B"}), graph=graph
            ).algorithm_version
            for _ in range(_N_REPS)
        ]
        return versions

    def checker(versions: list) -> bool:
        if len(set(versions)) != 1:
            raise AssertionError(f"cyclic_id algorithm_version is flaky: {versions}")
        return True

    return BenchmarkCase(
        name="repro::no_flaky::cyclic_id_3reps_same_algorithm_version",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("no_flaky", "cyclic_id", "algorithm_version"),
        timeout_s=60.0,
    )


def _case_mgraph_recoverability_no_flaky() -> BenchmarkCase:
    """MCAR X: 3 reps all RECOVERABLE."""

    def runner():
        from polisyos.foundry.methods.catalog.causal.recoverability_engine import (
            test_recoverability,
        )
        from polisyos.ir.analytics.mgraph import (
            MissingnessKind,
            build_mgraph,
            extract_mgraph_metadata,
        )

        graph = _build_xy_dag()
        statuses = []
        for _ in range(_N_REPS):
            mgraph = build_mgraph(base_graph=graph, missing_variables={"X": MissingnessKind.MCAR})
            meta = extract_mgraph_metadata(mgraph)
            result = test_recoverability(query_vars=frozenset({"X"}), graph=graph, mgraph_meta=meta)
            statuses.append(result.status.value)
        return statuses

    def checker(statuses: list) -> bool:
        if len(set(statuses)) != 1:
            raise AssertionError(f"MCAR recoverability is flaky: {statuses}")
        if list(set(statuses))[0] != "recoverable":
            raise AssertionError(f"MCAR should be recoverable, got {list(set(statuses))[0]!r}")
        return True

    return BenchmarkCase(
        name="repro::no_flaky::mgraph_mcar_3reps_all_recoverable",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("no_flaky", "mgraph", "recoverability"),
        timeout_s=60.0,
    )


def _case_ctf_transport_no_flaky() -> BenchmarkCase:
    """PN query on X→Y with S_Y: 3 reps same CTF status."""

    def runner():
        from polisyos.foundry.methods.catalog.causal.ctf_transport import (
            build_ctf_selection_diagram,
            ctf_transportability,
        )
        from polisyos.foundry.methods.catalog.causal.id_engine import CtfQuery
        from polisyos.ir.analytics.negative_certificate import NegativeCertificate
        from polisyos.ir.analytics.transportability import SNode

        graph = _build_xy_dag()
        query = CtfQuery(
            outcome="Y",
            intervention=(("X", 1.0),),
            evidence=(("Y", 1.0),),
            kind="pn",
        )
        s_node = SNode(
            target_variable="Y",
            context_dimension="mechanism_shift",
            source_value=0.0,
            target_value=1.0,
            delta=1.0,
            severity="medium",
        )
        statuses = []
        for _ in range(_N_REPS):
            diagram = build_ctf_selection_diagram(graph=graph, s_nodes=[s_node])
            result = ctf_transportability(query, diagram)
            if isinstance(result, NegativeCertificate):
                statuses.append(f"neg:{result.blocking_type.value}")
            else:
                statuses.append(result.status.value)
        return statuses

    def checker(statuses: list) -> bool:
        if len(set(statuses)) != 1:
            raise AssertionError(f"CTF transport status is flaky: {statuses}")
        return True

    return BenchmarkCase(
        name="repro::no_flaky::ctf_transport_pn_3reps_same_status",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("no_flaky", "ctf_transport", "pn"),
        timeout_s=60.0,
    )


# ---------------------------------------------------------------------------
# Harness builder
# ---------------------------------------------------------------------------


def build_no_flaky_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register(_case_frontdoor_no_flaky())
    harness.register(_case_bow_arc_no_flaky())
    harness.register(_case_cyclic_id_no_flaky())
    harness.register(_case_mgraph_recoverability_no_flaky())
    harness.register(_case_ctf_transport_no_flaky())
    return harness


# ---------------------------------------------------------------------------
# JSON / main
# ---------------------------------------------------------------------------


def _report_to_dict(
    report: BenchmarkReport, *, mode: str, preflight: dict[str, Any]
) -> dict[str, Any]:
    return build_report_payload(
        report,
        suite_id="reproducibility_regression",
        mode=mode,
        preflight=preflight,
        sub_circuit="no_flaky",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Circuit 5 — 3× repeat no-flaky test")
    parser.add_argument("--mode", choices=("smoke", "acceptance"))
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    mode = resolve_mode(args.mode).value
    preflight = build_preflight(mode=mode, data_source="deterministic_replay")
    print_preflight(preflight)

    harness = build_no_flaky_harness()
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
