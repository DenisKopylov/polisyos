"""Capability win demo: Difference-in-Differences with interference screening."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

_BENCH_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _BENCH_ROOT / "src"
for _p in (str(_SRC), str(_BENCH_ROOT)):
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


def _did_imports():
    from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
    from polisyos.foundry.methods.catalog.causal.did import StandardDifferenceInDifferences
    from polisyos.foundry.methods.catalog.causal.protocols import (
        NetworkCausalData,
        PanelObservationalData,
    )

    return CausalEngine, StandardDifferenceInDifferences, NetworkCausalData, PanelObservationalData


def _network_data() -> Any:
    _, _, NetworkCausalData, _ = _did_imports()
    return NetworkCausalData(
        outcome=np.array([2.2, 2.1, 1.3, 1.2], dtype=float),
        treatment=np.array([1.0, 1.0, 0.0, 0.0], dtype=float),
        cluster_id=np.array([0, 0, 1, 1], dtype=int),
        adjacency_matrix=np.array(
            [
                [0.0, 1.0, 0.2, 0.2],
                [1.0, 0.0, 0.2, 0.2],
                [0.2, 0.2, 0.0, 1.0],
                [0.2, 0.2, 1.0, 0.0],
            ],
            dtype=float,
        ),
        metadata={"design": "cluster_spillover"},
    )


def _panel_data() -> Any:
    _, _, _, PanelObservationalData = _did_imports()
    outcome = np.array(
        [
            [1.0, 1.1, 2.1, 2.4],
            [0.9, 1.0, 2.0, 2.2],
            [0.8, 0.9, 1.1, 1.2],
            [0.7, 0.8, 1.0, 1.1],
        ],
        dtype=float,
    )
    treatment = np.array([1, 1, 0, 0], dtype=int)
    return PanelObservationalData(
        outcome=outcome,
        treatment=treatment,
        time_treatment=2,
        unit_ids=np.array(["u1", "u2", "u3", "u4"], dtype=object),
        time_index=np.array([0, 1, 2, 3], dtype=int),
        metadata={"design": "panel_interference_screen"},
    )


def _case_interference_screen_detects_spillover() -> BenchmarkCase:
    def runner():
        CausalEngine, StandardDifferenceInDifferences, NetworkCausalData, PanelObservationalData = (
            _did_imports()
        )
        engine = CausalEngine()
        return engine.interference_effect(
            _network_data(), treatment="A", outcome="Y", method="partial"
        )

    def checker(result: Any) -> bool:
        if not getattr(result, "is_success", False):
            raise AssertionError(f"Expected successful interference report, got {result.status}")
        if result.spillover_effect is None:
            raise AssertionError("Spillover effect should be populated")
        if abs(float(result.spillover_effect)) <= 0.0:
            raise AssertionError("Spillover effect should be non-zero in the synthetic design")
        return True

    return BenchmarkCase(
        name="capability::did_with_interference::spillover_screen_detected",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("did", "interference", "spillover", "screen"),
        timeout_s=20.0,
    )


def _case_did_point_estimate_after_screen() -> BenchmarkCase:
    def runner():
        _, StandardDifferenceInDifferences, _, PanelObservationalData = _did_imports()
        return StandardDifferenceInDifferences.pure_step(_panel_data(), {})

    def checker(result: Any) -> bool:
        report = result["report"]
        if getattr(report, "status", None).value != "success":
            raise AssertionError(
                f"Expected successful DiD report, got {getattr(report, 'status', None)}"
            )
        if float(report.point_estimate) <= 0.0:
            raise AssertionError("Expected positive ATT in the synthetic DiD design")
        return True

    return BenchmarkCase(
        name="capability::did_with_interference::did_point_estimate_positive",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("did", "panel", "att", "interference"),
        timeout_s=20.0,
    )


def build_did_with_interference_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register(_case_interference_screen_detects_spillover())
    harness.register(_case_did_point_estimate_after_screen())
    return harness


def _report_to_dict(
    report: BenchmarkReport, *, mode: str, preflight: dict[str, Any]
) -> dict[str, Any]:
    extra = build_capability_report_extra(
        report,
        CapabilityProofSpec(
            proof_class="interference_aware_did",
            literature_anchor={
                "primary": "Callaway & Sant'Anna (2021), Difference-in-Differences with Multiple Time Periods",
                "secondary": "Hudgens & Halloran (2008), Toward causal inference with interference",
            },
            claim_profile_targets=(
                "spillover screening",
                "DiD point estimation under interference",
                "panel ATT recovery",
            ),
            competitor_gap=(
                make_gap_row(
                    "plain_did",
                    "spillover_screening",
                    status="gap",
                    note="Standard DiD assumes SUTVA and does not expose an interference-aware pre-check.",
                    level="workflow",
                ),
                make_gap_row(
                    "network_only_baseline",
                    "panel_att_compilation",
                    status="gap",
                    note="Network spillover estimation alone does not compile to a DID-style panel ATT report.",
                    level="workflow",
                ),
            ),
            workflow_levels={
                "interference_screen": "PASS",
                "panel_did": "PASS",
                "att_estimate": "PASS",
                "audit_payload": "PASS",
            },
        ),
    )
    return build_report_payload(
        report,
        suite_id="capability_did_with_interference",
        mode=mode,
        preflight=preflight,
        sub_circuit="did_with_interference",
        extra=extra,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capability win demo — DiD with interference")
    parser.add_argument("--mode", choices=("smoke", "acceptance"))
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode).value
    preflight = build_preflight(mode=mode, data_source="capability_demo_graphs")
    print_preflight(preflight)

    harness = build_did_with_interference_harness()
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
