"""Capability win demo: multi-source fusion from incomplete source domains.

This keeps the scenario synthetic but exercises the multi-domain transport path
with one incomplete source alone and two complementary sources together.
"""

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


def _graph_imports():
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType

    return CausalEdge, CausalGraphModel, EdgeMark, GraphType


def _engine_imports():
    from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
    from polisyos.foundry.methods.catalog.causal.id_engine import (
        IdentificationResult,
        IdentificationStatus,
        SourceDomain,
    )

    return CausalEngine, IdentificationResult, IdentificationStatus, SourceDomain


def _fusion_imports():
    from polisyos.foundry.methods.catalog.causal.data_fusion import multi_study_fusion
    from polisyos.ir.analytics.data_fusion import FusionDataset

    return FusionDataset, multi_study_fusion


def _build_chain_graph():
    CausalEdge, CausalGraphModel, EdgeMark, GraphType = _graph_imports()
    return CausalGraphModel(
        schema_version="1.0",
        graph_type=GraphType.DAG,
        nodes=["Z", "X", "Y"],
        edges=[
            CausalEdge(src="Z", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
        ],
    )


def _proof_steps(result: Any) -> list[str]:
    return [step.rule_name for step in getattr(result, "proof_steps", ())]


def _registry_domain() -> Any:
    _, _, _, SourceDomain = _engine_imports()
    return SourceDomain(
        domain_id="registry_a",
        s_nodes=frozenset({"Z"}),
        dataset_ref="registry_a",
    )


def _trial_domain() -> Any:
    _, _, _, SourceDomain = _engine_imports()
    return SourceDomain(
        domain_id="trial_b",
        z_interventions=frozenset({"X"}),
        dataset_ref="trial_b",
    )


def _case_single_source_blocks() -> BenchmarkCase:
    def runner():
        CausalEngine, IdentificationResult, IdentificationStatus, SourceDomain = _engine_imports()
        engine = CausalEngine()
        CausalEdge, CausalGraphModel, EdgeMark, GraphType = _graph_imports()
        graph = CausalGraphModel(
            schema_version="1.0",
            graph_type=GraphType.ADMG,
            nodes=["X", "Y"],
            edges=[
                CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
                CausalEdge(src="X", dst="Y", mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW),
            ],
        )
        return engine.identify(
            treatment="X",
            outcome="Y",
            graph=graph,
            source_domains=[
                SourceDomain(
                    domain_id="registry_a", s_nodes=frozenset({"Y"}), dataset_ref="registry_a"
                )
            ],
        )

    def checker(result: Any) -> bool:
        _, IdentificationResult, IdentificationStatus, _ = _engine_imports()
        if (
            isinstance(result, IdentificationResult)
            and result.status is IdentificationStatus.IDENTIFIED
        ):
            raise AssertionError(
                "Single incomplete source should not fully identify the target effect"
            )
        return True

    return BenchmarkCase(
        name="capability::multi_source::single_incomplete_source_blocks",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=_proof_steps,
        tags=("multi_source", "incomplete_source", "negative_control"),
        timeout_s=15.0,
    )


def _case_two_source_fusion_identified() -> BenchmarkCase:
    def runner():
        FusionDataset, multi_study_fusion = _fusion_imports()
        graph = _build_chain_graph()
        datasets = [
            FusionDataset(
                dataset_ref="clinical_registry",
                domain_id="domain_1",
                n_obs=5000,
                available_interventions=[],
                selection_bias_vars=["Z"],
            ),
            FusionDataset(
                dataset_ref="randomized_trial",
                domain_id="domain_2",
                n_obs=1200,
                available_interventions=["X"],
                selection_bias_vars=["Z"],
            ),
        ]
        return multi_study_fusion(
            datasets=datasets,
            graph=graph,
            treatment="X",
            outcome="Y",
        )

    def checker(result: Any) -> bool:
        if not getattr(result, "is_identified", False):
            raise AssertionError(
                f"Expected identified fusion result, got {getattr(result, 'warnings', None)}"
            )
        return True

    return BenchmarkCase(
        name="capability::multi_source::two_complementary_sources_identified",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=_proof_steps,
        tags=("multi_source", "fusion", "identified"),
        timeout_s=20.0,
    )


def build_multiple_incomplete_sources_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register(_case_single_source_blocks())
    harness.register(_case_two_source_fusion_identified())
    return harness


def _report_to_dict(
    report: BenchmarkReport, *, mode: str, preflight: dict[str, Any]
) -> dict[str, Any]:
    extra = build_capability_report_extra(
        report,
        CapabilityProofSpec(
            proof_class="multi_source_transport",
            literature_anchor={
                "primary": "Bareinboim & Pearl (2014/2016), Meta transportability and multi-source fusion",
                "secondary": "Bareinboim & Pearl (2012), Transportability of Causal Effects: Completeness Results",
            },
            claim_profile_targets=(
                "multi-source fusion",
                "incomplete-source complementarity",
                "transportability via source-domain aggregation",
            ),
            competitor_gap=(
                make_gap_row(
                    "single_source_baseline",
                    "complementary_source_aggregation",
                    status="gap",
                    note="A single incomplete domain cannot cover both the selection and intervention gaps.",
                    level="source_fusion",
                ),
                make_gap_row(
                    "manual_two_stage_pipeline",
                    "machine_readable_source_selection",
                    status="gap",
                    note="Manual workflows do not expose a structured cross-domain proof trace for the fusion decision.",
                    level="audit",
                ),
            ),
            workflow_levels={
                "single_source_screen": "PASS",
                "multi_source_fusion": "PASS",
                "identification": "PASS",
                "audit_payload": "PASS",
            },
        ),
    )
    return build_report_payload(
        report,
        suite_id="capability_multiple_incomplete_sources",
        mode=mode,
        preflight=preflight,
        sub_circuit="multiple_incomplete_sources",
        extra=extra,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capability win demo — multiple incomplete sources"
    )
    parser.add_argument("--mode", choices=("smoke", "acceptance"))
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode).value
    preflight = build_preflight(mode=mode, data_source="capability_demo_graphs")
    print_preflight(preflight)

    harness = build_multiple_incomplete_sources_harness()
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
