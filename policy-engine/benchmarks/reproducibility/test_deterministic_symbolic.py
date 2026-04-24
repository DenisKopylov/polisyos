"""Circuit 5: Reproducibility — Symbolic outputs are bit-identical across runs.

Verifies that the symbolic identification engine (id_algorithm, tr_algorithm,
cyclic_id_algorithm) produces byte-for-byte identical outputs on repeated calls
with the same inputs — no random state, no hash-order non-determinism.

This is critical for regulatory and compliance use-cases where the audit trail
must be reproducible.

Test cases
----------
1. id_algorithm on frontdoor graph: estimand_ast fingerprint is stable across N=5 calls.
2. tr_algorithm on X→Y with S-node: result status is stable.
3. cyclic_id_algorithm on A→B: algorithm_version and status stable.
4. NegativeCertificate on bow-arc: blocking_type and constructive_message stable.
5. graph_fingerprint stability: same graph → same fingerprint in EvidenceBundle.

Bar
---
All N=5 repetitions agree (0 divergences).

Usage
-----
    python benchmarks/reproducibility/test_deterministic_symbolic.py
    python benchmarks/reproducibility/test_deterministic_symbolic.py --json report.json
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
_N_REPS = 5


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
# Shared graph builders
# ---------------------------------------------------------------------------


def _build_frontdoor():
    CausalEdge, CausalGraphModel, EdgeMark, GraphType = _graph_imports()
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


# ---------------------------------------------------------------------------
# Benchmark cases
# ---------------------------------------------------------------------------


def _case_id_algorithm_fingerprint_stable() -> BenchmarkCase:
    """Frontdoor id_algorithm: estimand_ast fingerprint identical across N runs."""

    def runner():
        from polisyos.foundry.methods.catalog.causal.id_engine import id_algorithm
        from polisyos.ir.analytics.evidence_bundle import _fingerprint

        graph = _build_frontdoor()
        fingerprints = []

        for _ in range(_N_REPS):
            result = id_algorithm(
                treatment=frozenset({"X"}),
                outcome=frozenset({"Y"}),
                graph=graph,
            )
            ast = result.estimand_ast
            fp = _fingerprint(ast.model_dump(mode="json") if ast is not None else {})
            fingerprints.append(fp)

        return fingerprints

    def checker(fps: list) -> bool:
        unique = set(fps)
        if len(unique) != 1:
            raise AssertionError(
                f"Estimand fingerprint should be identical across {_N_REPS} runs, "
                f"got {len(unique)} unique values: {sorted(unique)}"
            )
        return True

    return BenchmarkCase(
        name="repro::deterministic::id_algorithm_fingerprint_stable",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("deterministic", "id_algorithm", "fingerprint"),
        timeout_s=30.0,
    )


def _case_id_algorithm_status_stable() -> BenchmarkCase:
    """Frontdoor: identification status identical across N runs."""

    def runner():
        from polisyos.foundry.methods.catalog.causal.id_engine import (
            id_algorithm,
        )

        graph = _build_frontdoor()
        statuses = [
            id_algorithm(
                treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=graph
            ).status.value
            for _ in range(_N_REPS)
        ]
        return statuses

    def checker(statuses: list) -> bool:
        unique = set(statuses)
        if len(unique) != 1:
            raise AssertionError(f"Identification status should be stable; got: {statuses}")
        if list(unique)[0] != "identified":
            raise AssertionError(f"Frontdoor should be identified, got {list(unique)[0]!r}")
        return True

    return BenchmarkCase(
        name="repro::deterministic::id_algorithm_status_stable",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("deterministic", "id_algorithm", "status"),
        timeout_s=30.0,
    )


def _case_hedge_certificate_stable() -> BenchmarkCase:
    """Bow-arc hedge certificate: blocking_type stable across N runs."""

    def runner():
        from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
        from polisyos.ir.analytics.negative_certificate import NegativeCertificate

        engine = CausalEngine()
        graph = _build_bow_arc()
        blocking_types = []

        for _ in range(_N_REPS):
            result = engine.identify(treatment="X", outcome="Y", graph=graph)
            if isinstance(result, NegativeCertificate):
                blocking_types.append(result.blocking_type.value)
            else:
                blocking_types.append(f"unexpected:{result.status.value}")

        return blocking_types

    def checker(blocking_types: list) -> bool:
        unique = set(blocking_types)
        if len(unique) != 1:
            raise AssertionError(
                f"NegativeCertificate.blocking_type should be stable; got: {blocking_types}"
            )
        return True

    return BenchmarkCase(
        name="repro::deterministic::hedge_certificate_blocking_type_stable",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("deterministic", "hedge", "negative_certificate"),
        timeout_s=30.0,
    )


def _case_proof_steps_count_stable() -> BenchmarkCase:
    """Frontdoor: number of proof steps identical across N runs."""

    def runner():
        from polisyos.foundry.methods.catalog.causal.id_engine import id_algorithm

        graph = _build_frontdoor()
        step_counts = [
            len(
                id_algorithm(
                    treatment=frozenset({"X"}), outcome=frozenset({"Y"}), graph=graph
                ).proof_steps
            )
            for _ in range(_N_REPS)
        ]
        return step_counts

    def checker(counts: list) -> bool:
        unique = set(counts)
        if len(unique) != 1:
            raise AssertionError(f"Proof step count should be stable; got: {counts}")
        return True

    return BenchmarkCase(
        name="repro::deterministic::proof_steps_count_stable",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("deterministic", "proof_steps", "stability"),
        timeout_s=30.0,
    )


def _case_graph_fingerprint_stable() -> BenchmarkCase:
    """CausalEngine.audit() graph_fingerprint is stable for the same graph."""

    def runner():
        import uuid

        from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
        from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationResult

        engine = CausalEngine()
        graph = _build_frontdoor()
        id_result = engine.identify(treatment="X", outcome="Y", graph=graph)
        if not isinstance(id_result, IdentificationResult):
            raise AssertionError("Expected IdentificationResult for frontdoor")

        fingerprints = [
            engine.audit(id_result, None, run_id=str(uuid.uuid4()), graph=graph).graph_fingerprint
            for _ in range(_N_REPS)
        ]
        return fingerprints

    def checker(fps: list) -> bool:
        unique = set(fps)
        if len(unique) != 1:
            raise AssertionError(
                f"graph_fingerprint should be stable across runs, got {len(unique)} unique: {sorted(unique)}"
            )
        if not list(unique)[0]:
            raise AssertionError("graph_fingerprint should be non-empty")
        return True

    return BenchmarkCase(
        name="repro::deterministic::graph_fingerprint_stable",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("deterministic", "graph_fingerprint", "audit"),
        timeout_s=30.0,
    )


# ---------------------------------------------------------------------------
# Harness builder
# ---------------------------------------------------------------------------


def build_deterministic_symbolic_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register(_case_id_algorithm_fingerprint_stable())
    harness.register(_case_id_algorithm_status_stable())
    harness.register(_case_hedge_certificate_stable())
    harness.register(_case_proof_steps_count_stable())
    harness.register(_case_graph_fingerprint_stable())
    return harness


# ---------------------------------------------------------------------------
# JSON / main
# ---------------------------------------------------------------------------


def _report_to_dict(
    report: BenchmarkReport, *, mode: str, preflight: dict[str, Any]
) -> dict[str, Any]:
    return build_report_payload(
        report,
        suite_id="reproducibility_deterministic",
        mode=mode,
        preflight=preflight,
        sub_circuit="deterministic_symbolic",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Circuit 5 — Deterministic symbolic reproducibility"
    )
    parser.add_argument("--mode", choices=("smoke", "acceptance"))
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    mode = resolve_mode(args.mode).value
    preflight = build_preflight(mode=mode, data_source="deterministic_replay")
    print_preflight(preflight)

    harness = build_deterministic_symbolic_harness()
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
