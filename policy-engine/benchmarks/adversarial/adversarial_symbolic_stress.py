"""Adversarial symbolic stress benchmark entrypoint.

Small graphs that try to provoke false positives or confuse the identification
engine with decoy structure. The goal is to keep the suite lightweight while
still exercising hedge detection, frontdoor recovery, and proof trace handling.
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
from benchmarks.metrics import compute_accuracy_metrics  # noqa: E402
from benchmarks.reporting import build_preflight, build_report_payload, print_preflight  # noqa: E402
from benchmarks.runtime import BenchmarkMode, resolve_mode  # noqa: E402
from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus, id_algorithm  # noqa: E402
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType  # noqa: E402


CIRCUIT = BenchmarkCircuit.SYMBOLIC


def _graph(
    *,
    nodes: list[str],
    edges: list[CausalEdge],
    metadata: dict[str, Any] | None = None,
) -> CausalGraphModel:
    return CausalGraphModel(
        schema_version="1.0",
        graph_type=GraphType.ADMG,
        nodes=nodes,
        edges=edges,
        metadata=metadata or {},
    )


def _identify(graph: CausalGraphModel):
    return id_algorithm(
        treatment=frozenset({"X"}),
        outcome=frozenset({"Y"}),
        graph=graph,
    )


def _artifact_from_payload(result: Any) -> Any:
    if isinstance(result, dict):
        return result.get("artifact")
    return result


def _proof_steps_from_payload(result: Any) -> list[str]:
    artifact = _artifact_from_payload(result)
    return [step.rule_name for step in getattr(artifact, "proof_steps", ())]


def _is_identified_from_payload(result: Any) -> bool:
    return getattr(_artifact_from_payload(result), "status", None) is IdentificationStatus.IDENTIFIED


def _has_estimand_ast(result: Any) -> bool:
    return getattr(_artifact_from_payload(result), "estimand_ast", None) is not None


def _case_bow_arc_false_positive_guard() -> BenchmarkCase:
    graph = _graph(
        nodes=["X", "Y"],
        edges=[
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW),
        ],
        metadata={"pattern": "bow_arc"},
    )

    def runner() -> dict[str, Any]:
        artifact = _identify(graph)
        return {
            "artifact": artifact,
            "artifact_kind": "symbolic_identification",
            "expected_status": IdentificationStatus.HEDGE_FOUND.value,
            "pattern": "bow_arc",
        }

    def checker(result: dict[str, Any]) -> bool:
        artifact = result["artifact"]
        if artifact.status is not IdentificationStatus.HEDGE_FOUND:
            raise AssertionError(f"bow-arc should be rejected, got {artifact.status.value}")
        if artifact.proof_steps is None or len(artifact.proof_steps) == 0:
            raise AssertionError("bow-arc should still emit proof steps")
        return True

    return BenchmarkCase(
        name="adversarial::symbolic::bow_arc_false_positive_guard",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=_proof_steps_from_payload,
        is_identifiable_ground_truth=False,
        is_identifiable_extractor=_is_identified_from_payload,
        tags=("symbolic", "adversarial", "hedge", "false_positive_guard"),
        timeout_s=10.0,
    )


def _case_frontdoor_with_decoys() -> BenchmarkCase:
    graph = _graph(
        nodes=["X", "M", "Y", "U", "V"],
        edges=[
            CausalEdge(src="X", dst="M", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="M", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="U", dst="V", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
        metadata={"pattern": "frontdoor_with_decoys"},
    )

    def runner() -> dict[str, Any]:
        artifact = _identify(graph)
        return {
            "artifact": artifact,
            "artifact_kind": "symbolic_identification",
            "expected_status": IdentificationStatus.IDENTIFIED.value,
            "pattern": "frontdoor_with_decoys",
        }

    def checker(result: dict[str, Any]) -> bool:
        artifact = result["artifact"]
        if artifact.status is not IdentificationStatus.IDENTIFIED:
            raise AssertionError(f"frontdoor case should identify, got {artifact.status.value}")
        if artifact.estimand_ast is None:
            raise AssertionError("frontdoor case should produce an estimand AST")
        return True

    return BenchmarkCase(
        name="adversarial::symbolic::frontdoor_with_decoys",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=_proof_steps_from_payload,
        is_identifiable_ground_truth=True,
        is_identifiable_extractor=_is_identified_from_payload,
        formula_correct_extractor=_has_estimand_ast,
        tags=("symbolic", "adversarial", "frontdoor", "decoys"),
        timeout_s=10.0,
    )


def _case_compound_hedge_with_decoys() -> BenchmarkCase:
    graph = _graph(
        nodes=["X", "Y", "A", "B", "C", "D"],
        edges=[
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="A", dst="B", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="B", dst="C", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="D", dst="A", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
        metadata={"pattern": "compound_hedge"},
    )

    def runner() -> dict[str, Any]:
        artifact = _identify(graph)
        return {
            "artifact": artifact,
            "artifact_kind": "symbolic_identification",
            "expected_status": IdentificationStatus.HEDGE_FOUND.value,
            "pattern": "compound_hedge",
        }

    def checker(result: dict[str, Any]) -> bool:
        artifact = result["artifact"]
        if artifact.status is not IdentificationStatus.HEDGE_FOUND:
            raise AssertionError(
                f"compound hedge should remain non-identifiable, got {artifact.status.value}"
            )
        if len(artifact.proof_steps) < 1:
            raise AssertionError("compound hedge should emit proof trace")
        return True

    return BenchmarkCase(
        name="adversarial::symbolic::compound_hedge_with_decoys",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=_proof_steps_from_payload,
        is_identifiable_ground_truth=False,
        is_identifiable_extractor=_is_identified_from_payload,
        tags=("symbolic", "adversarial", "hedge", "decoys"),
        timeout_s=10.0,
    )


def build_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register_many(
        [
            _case_bow_arc_false_positive_guard(),
            _case_frontdoor_with_decoys(),
            _case_compound_hedge_with_decoys(),
        ]
    )
    return harness


def _aggregate_metrics(report: BenchmarkReport) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    proof_counts: list[int] = []
    identified = 0
    non_identified = 0
    for case in report.cases:
        payload = case.result_payload or {}
        artifact = payload.get("artifact")
        if artifact is None:
            continue
        status = getattr(artifact, "status", None)
        if status is IdentificationStatus.IDENTIFIED:
            identified += 1
        elif status is IdentificationStatus.HEDGE_FOUND:
            non_identified += 1

        proof_count = len(getattr(artifact, "proof_steps", ()) or ())
        proof_counts.append(proof_count)
        rows.append(
            {
                "case": case.name,
                "pattern": payload.get("pattern"),
                "status": status.value if hasattr(status, "value") else str(status),
                "proof_step_count": proof_count,
                "expected_status": payload.get("expected_status"),
                "false_positive_blocker": bool(
                    getattr(case, "is_identifiable_gt", None) is False
                    and getattr(case, "is_identifiable_pred", None) is True
                ),
            }
        )

    accuracy = compute_accuracy_metrics(
        [
            (
                bool(case.is_identifiable_gt),
                bool(case.is_identifiable_pred),
                bool(case.formula_correct if case.formula_correct is not None else True),
            )
            for case in report.cases
            if case.is_identifiable_gt is not None and case.is_identifiable_pred is not None
        ]
    )

    return {
        "case_rows": rows,
        "n_identified": identified,
        "n_non_identified": non_identified,
        "false_positive_blockers": len(report.blocker_cases()),
        "mean_proof_step_count": float(sum(proof_counts) / len(proof_counts)) if proof_counts else None,
        "accuracy": {
            "n_total": accuracy.n_total,
            "n_true_positive": accuracy.n_true_positive,
            "n_true_negative": accuracy.n_true_negative,
            "n_false_positive": accuracy.n_false_positive,
            "n_false_negative": accuracy.n_false_negative,
            "false_positive_rate": accuracy.false_positive_rate,
        },
    }


def _report_to_dict(report: BenchmarkReport, *, mode: str, preflight: dict[str, Any]) -> dict[str, Any]:
    return build_report_payload(
        report,
        suite_id="adversarial_symbolic_stress",
        mode=mode,
        preflight=preflight,
        sub_circuit="adversarial_symbolic_stress",
        include_case_payload=True,
        aggregate_metrics=_aggregate_metrics(report),
        extra={
            "benchmark_family": "adversarial_symbolic",
            "proof_class": "stress_evidence",
            "claim_profile_targets": ["frontier_frontier_claim", "full_stack_publication_claim"],
            "dataset_regime": "synthetic_canonical_graphs",
            "baseline_snapshot_ref": "adversarial_symbolic_stress@synthetic-v1",
            "regression_guard": {
                "max_false_positive_blockers": 0,
                "min_identified_cases": 1,
                "min_non_identified_cases": 2,
            },
            "literature_anchor": [
                "Pearl (2009): Causality",
                "Shpitser & Pearl (2006): identification of causal effects",
            ],
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Adversarial symbolic stress benchmark")
    parser.add_argument("--mode", choices=[mode.value for mode in BenchmarkMode])
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode)
    preflight = build_preflight(mode=mode.value, data_source="synthetic_adversarial_symbolic_suite")
    print_preflight(preflight)

    harness = build_harness()
    report = harness.run(circuit=CIRCUIT)
    harness.print_report(report, verbose=not args.quiet)

    if args.json:
        Path(args.json).write_text(
            json.dumps(_report_to_dict(report, mode=mode.value, preflight=preflight), indent=2),
            encoding="utf-8",
        )
        print(f"\nJSON report written to: {args.json}")

    failures = report.n_total() - report.n_passed()
    if failures > 0:
        print(f"\n[FAIL] {failures} adversarial symbolic case(s) failed.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
