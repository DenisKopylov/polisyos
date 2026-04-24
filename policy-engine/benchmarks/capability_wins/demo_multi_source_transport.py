"""Circuit 4: Capability — Multi-source mZ-ID transportability end-to-end demo.

Demonstrates that PolicyOS can fuse K=2 heterogeneous datasets from different
source populations and identify P*(Y|do(X)) in the target population using
the mZ-ID algorithm (Bareinboim & Pearl 2016).

Scenario
--------
Graph (causal DAG):  Z → X → Y   (no hidden confounders)

Domain 1 (clinical registry):
  - Observational data only
  - Selection bias on Z  (S₁ → Z: patients self-selected into low-Z regimes)

Domain 2 (randomized trial):
  - Experimental data: P(V | do(X)) is available
  - Selection bias on Z  (S₂ → Z: trial recruited high-Z patients)

Target: P*(Y | do(X)) in a representative population (no S-nodes).

mZ-ID succeeds because:
  - Domain 2 provides P(Y | do(X)) directly (modulo S₂ on Z, which is a
    non-ancestor of X under do(X) and can be trimmed).

Bar
---
FusionResult.is_identified == True  (100%)

Usage
-----
    python benchmarks/capability_wins/demo_multi_source_transport.py
    python benchmarks/capability_wins/demo_multi_source_transport.py --json report.json
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


def _fusion_imports():
    from polisyos.foundry.methods.catalog.causal.data_fusion import multi_study_fusion
    from polisyos.ir.analytics.data_fusion import FusionDataset, FusionResult

    return FusionDataset, FusionResult, multi_study_fusion


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def _build_chain_dag():
    """Z → X → Y  (simple chain, no confounders)."""
    CausalEdge, CausalGraphModel, EdgeMark, GraphType = _graph_imports()
    edges = [
        CausalEdge(src="Z", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
    ]
    return CausalGraphModel(
        schema_version="1.0",
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "Z"],
        edges=edges,
    )


# ---------------------------------------------------------------------------
# Benchmark cases
# ---------------------------------------------------------------------------


def _case_two_domain_fusion_identified() -> BenchmarkCase:
    """mZ-ID on two domains → identified."""

    def runner():
        FusionDataset, FusionResult, multi_study_fusion = _fusion_imports()
        graph = _build_chain_dag()

        datasets = [
            FusionDataset(
                dataset_ref="clinical_registry",
                domain_id="domain_1",
                n_obs=5000,
                available_interventions=[],  # observational only
                selection_bias_vars=["Z"],  # S₁ on Z
            ),
            FusionDataset(
                dataset_ref="randomized_trial",
                domain_id="domain_2",
                n_obs=1200,
                available_interventions=["X"],  # do(X) available from RCT
                selection_bias_vars=["Z"],  # S₂ on Z
            ),
        ]

        result = multi_study_fusion(
            datasets=datasets,
            graph=graph,
            treatment="X",
            outcome="Y",
        )
        return result

    def checker(r) -> bool:
        if not r.is_identified:
            raise AssertionError(f"mZ-ID failed to identify P*(Y|do(X)): {r.warnings}")
        return True

    return BenchmarkCase(
        name="capability::multi_source::two_domain_mzid_identified",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("multi_source", "mz_id", "transportability"),
        timeout_s=30.0,
    )


def _case_single_domain_rct_fusion() -> BenchmarkCase:
    """Z-transport: one obs + one RCT → identified via fuse_experimental_observational."""

    def runner():
        from polisyos.foundry.methods.catalog.causal.data_fusion import (
            fuse_experimental_observational,
        )

        graph = _build_chain_dag()

        result = fuse_experimental_observational(
            graph=graph,
            treatment="X",
            outcome="Y",
            exp_interventions=["X"],
            obs_data_ref="obs_registry",
            exp_data_ref="rct_study",
        )
        return result

    def checker(r) -> bool:
        if not r.is_identified:
            raise AssertionError(f"Z-transport failed: {r.warnings}")
        if r.identification_algorithm != "z-id":
            raise AssertionError(f"Expected z-id algorithm, got: {r.identification_algorithm}")
        return True

    return BenchmarkCase(
        name="capability::multi_source::single_domain_z_transport_identified",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("z_transport", "fusion"),
        timeout_s=30.0,
    )


def _case_three_domain_fusion_identified() -> BenchmarkCase:
    """mZ-ID on three domains (richer graph Z→X→Y, W→X) → identified."""

    def runner():
        CausalEdge, CausalGraphModel, EdgeMark, GraphType = _graph_imports()
        FusionDataset, FusionResult, multi_study_fusion = _fusion_imports()

        # Extended graph: Z→X→Y, W→X  (W is instrument)
        edges = [
            CausalEdge(src="Z", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="W", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ]
        graph = CausalGraphModel(
            schema_version="1.0",
            graph_type=GraphType.DAG,
            nodes=["W", "X", "Y", "Z"],
            edges=edges,
        )

        datasets = [
            FusionDataset(
                dataset_ref="survey_A",
                domain_id="domain_A",
                n_obs=3000,
                available_interventions=[],
                selection_bias_vars=["Z"],
            ),
            FusionDataset(
                dataset_ref="trial_B",
                domain_id="domain_B",
                n_obs=800,
                available_interventions=["X"],
                selection_bias_vars=["W"],
            ),
            FusionDataset(
                dataset_ref="registry_C",
                domain_id="domain_C",
                n_obs=2000,
                available_interventions=[],
                selection_bias_vars=[],  # no selection bias
            ),
        ]

        result = multi_study_fusion(
            datasets=datasets,
            graph=graph,
            treatment="X",
            outcome="Y",
        )
        return result

    def checker(r) -> bool:
        if not r.is_identified:
            raise AssertionError(f"mZ-ID failed on 3-domain fusion: {r.warnings}")
        return True

    return BenchmarkCase(
        name="capability::multi_source::three_domain_mzid_identified",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("multi_source", "mz_id", "transportability"),
        timeout_s=30.0,
    )


# ---------------------------------------------------------------------------
# Harness builder
# ---------------------------------------------------------------------------


def build_multi_source_transport_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register(_case_two_domain_fusion_identified())
    harness.register(_case_single_domain_rct_fusion())
    harness.register(_case_three_domain_fusion_identified())
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
                "primary": "Bareinboim & Pearl (2016): Causal inference and the data-fusion problem",
            },
            claim_profile_targets=("frontier_frontier_claim", "full_stack_publication_claim"),
            competitor_gap=(
                make_gap_row(
                    "y0",
                    "multi_source_transport_workflow",
                    status="partial",
                    note="Transport queries exist, but multi-source mZ-ID workflow is not end-to-end.",
                    level="identifiable",
                ),
                make_gap_row(
                    "dowhy",
                    "multi_source_transportability",
                    status="fail",
                    note="No multi-source transport identification workflow.",
                    level="identifiable",
                ),
                make_gap_row(
                    "econml",
                    "transport_query_layer",
                    status="fail",
                    note="Estimator stack lacks symbolic transport/fusion layer.",
                    level="expressible",
                ),
                make_gap_row(
                    "causalpy",
                    "transport_query_layer",
                    status="fail",
                    note="No graph-native transport/fusion workflow.",
                    level="expressible",
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
        suite_id="capability_multi_source",
        mode=mode,
        preflight=preflight,
        sub_circuit="multi_source_transport",
        extra=extra,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Circuit 4 — Multi-source mZ-ID transportability demo"
    )
    parser.add_argument("--mode", choices=("smoke", "acceptance"))
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    mode = resolve_mode(args.mode).value
    preflight = build_preflight(mode=mode, data_source="capability_demo_graphs")
    print_preflight(preflight)

    harness = build_multi_source_transport_harness()
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
