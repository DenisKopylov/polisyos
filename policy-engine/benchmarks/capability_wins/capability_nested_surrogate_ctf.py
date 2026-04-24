"""Capability win demo: nested surrogate counterfactual transport.

This script keeps the scenario synthetic while exercising the nested
counterfactual path end-to-end:

- a plain nested Layer-3 query on a chain graph
- the same query routed through a surrogate source domain
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
        CtfQuery,
        IdentificationResult,
        IdentificationStatus,
        SourceDomain,
    )
    from polisyos.ir.analytics.estimand import NestedCounterfactualNode

    return (
        CausalEngine,
        CtfQuery,
        IdentificationResult,
        IdentificationStatus,
        SourceDomain,
        NestedCounterfactualNode,
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


def _nested_query() -> Any:
    _, CtfQuery, _, _, _, _ = _engine_imports()
    return CtfQuery(
        outcome="Y",
        intervention=(("X", 1.0),),
        reference_intervention=(("X", 0.0),),
        kind="nested",
        conditioning=("M",),
    )


def _proof_steps(result: Any) -> list[str]:
    return [step.rule_name for step in getattr(result, "proof_steps", ())]


def _case_nested_plain_identified() -> BenchmarkCase:
    def runner():
        (
            CausalEngine,
            CtfQuery,
            IdentificationResult,
            IdentificationStatus,
            SourceDomain,
            NestedCounterfactualNode,
        ) = _engine_imports()
        engine = CausalEngine()
        graph = _build_chain_graph()
        return engine.identify(
            treatment="X", outcome="Y", graph=graph, counterfactual_query=_nested_query()
        )

    def checker(result: Any) -> bool:
        _, _, IdentificationResult, IdentificationStatus, _, NestedCounterfactualNode = (
            _engine_imports()
        )
        if not isinstance(result, IdentificationResult):
            raise AssertionError(f"Expected IdentificationResult, got {type(result).__name__}")
        if result.status is not IdentificationStatus.IDENTIFIED:
            raise AssertionError(f"Expected IDENTIFIED, got {result.status}")
        if getattr(result.estimand_ast.root, "node_type", "") != "nested_counterfactual":
            raise AssertionError("Expected nested_counterfactual estimand root")
        return True

    return BenchmarkCase(
        name="capability::nested_surrogate_ctf::nested_plain_identified",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=_proof_steps,
        tags=("nested_ctf", "counterfactual", "identified"),
        timeout_s=15.0,
    )


def _case_nested_surrogate_domain_identified() -> BenchmarkCase:
    def runner():
        (
            CausalEngine,
            CtfQuery,
            IdentificationResult,
            IdentificationStatus,
            SourceDomain,
            NestedCounterfactualNode,
        ) = _engine_imports()
        engine = CausalEngine()
        graph = _build_chain_graph()
        source_domains = [
            SourceDomain(
                domain_id="surrogate_lab",
                z_interventions=frozenset({"M"}),
                dataset_ref="surrogate_lab",
            )
        ]
        return engine.identify(
            treatment="X",
            outcome="Y",
            graph=graph,
            counterfactual_query=_nested_query(),
            source_domains=source_domains,
        )

    def checker(result: Any) -> bool:
        _, _, IdentificationResult, IdentificationStatus, _, NestedCounterfactualNode = (
            _engine_imports()
        )
        if not isinstance(result, IdentificationResult):
            raise AssertionError(f"Expected IdentificationResult, got {type(result).__name__}")
        if result.status is not IdentificationStatus.IDENTIFIED:
            raise AssertionError(f"Expected IDENTIFIED, got {result.status}")
        if getattr(result.estimand_ast.root, "node_type", "") != "nested_counterfactual":
            raise AssertionError("Expected nested_counterfactual estimand root")
        if result.algorithm_version not in {"id_star_v2", "ctf_transport_v1", "sid_v1"}:
            raise AssertionError(f"Unexpected algorithm_version {result.algorithm_version!r}")
        return True

    return BenchmarkCase(
        name="capability::nested_surrogate_ctf::nested_surrogate_domain_identified",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=_proof_steps,
        tags=("nested_ctf", "surrogate", "transport", "identified"),
        timeout_s=15.0,
    )


def build_nested_surrogate_ctf_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register(_case_nested_plain_identified())
    harness.register(_case_nested_surrogate_domain_identified())
    return harness


def _report_to_dict(
    report: BenchmarkReport, *, mode: str, preflight: dict[str, Any]
) -> dict[str, Any]:
    extra = build_capability_report_extra(
        report,
        CapabilityProofSpec(
            proof_class="nested_counterfactual_transport",
            literature_anchor={
                "primary": "Correa, Lee & Bareinboim (2022), Counterfactual Transportability",
                "secondary": "Pearl (2009), Causality",
            },
            claim_profile_targets=(
                "nested counterfactual identification",
                "surrogate-domain transport",
                "layer-3 reduction",
            ),
            competitor_gap=(
                make_gap_row(
                    "baseline_counterfactual_id",
                    "nested_world_merging",
                    status="gap",
                    note="Nested world reductions are not first-class in baseline symbolic identification workflows.",
                    level="layer_3",
                ),
                make_gap_row(
                    "baseline_transport_only",
                    "surrogate_source_routing",
                    status="gap",
                    note="Plain transportability stacks do not preserve nested counterfactual structure through source domains.",
                    level="transport",
                ),
            ),
            workflow_levels={
                "graph_reduction": "PASS",
                "nested_world_build": "PASS",
                "transport_or_idstar": "PASS",
                "audit_payload": "PASS",
            },
        ),
    )
    return build_report_payload(
        report,
        suite_id="capability_nested_surrogate_ctf",
        mode=mode,
        preflight=preflight,
        sub_circuit="nested_surrogate_ctf",
        extra=extra,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capability win demo — nested surrogate CTF")
    parser.add_argument("--mode", choices=("smoke", "acceptance"))
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode).value
    preflight = build_preflight(mode=mode, data_source="capability_demo_graphs")
    print_preflight(preflight)

    harness = build_nested_surrogate_ctf_harness()
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
