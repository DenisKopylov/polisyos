"""Capability win demo: surrogate experiments via stochastic interventions.

This entrypoint exercises the policy-layer identification path built on top of
standard ID:

- conditional surrogate policies get wrapped as conditional interventions
- shift policies get wrapped as stochastic interventions

Both cases remain synthetic, deterministic, and end-to-end.
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


def _engine_imports():
    from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
    from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationResult, IdentificationStatus
    from polisyos.ir.analytics.estimand import ConditionalInterventionNode, StochasticInterventionNode, StochasticPolicy

    return CausalEngine, IdentificationResult, IdentificationStatus, ConditionalInterventionNode, StochasticInterventionNode, StochasticPolicy


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


def _case_conditional_policy_identified() -> BenchmarkCase:
    def runner():
        CausalEngine, IdentificationResult, IdentificationStatus, ConditionalInterventionNode, StochasticInterventionNode, StochasticPolicy = _engine_imports()
        engine = CausalEngine()
        graph = _build_chain_graph()
        policy = StochasticPolicy(policy_type="conditional", conditioning_vars=("Z",), policy_expr="do(X|Z)")
        return engine.identify(treatment="X", outcome="Y", graph=graph, policy=policy)

    def checker(result: Any) -> bool:
        _, IdentificationResult, IdentificationStatus, ConditionalInterventionNode, _, _ = _engine_imports()
        if not isinstance(result, IdentificationResult):
            raise AssertionError(f"Expected IdentificationResult, got {type(result).__name__}")
        if result.status is not IdentificationStatus.IDENTIFIED:
            raise AssertionError(f"Expected IDENTIFIED, got {result.status}")
        if result.algorithm_version != "sid_conditional_v1":
            raise AssertionError(f"Expected sid_conditional_v1, got {result.algorithm_version!r}")
        if getattr(result.estimand_ast.root, "node_type", "") != "conditional_do":
            raise AssertionError("Expected conditional_do estimand root")
        return True

    return BenchmarkCase(
        name="capability::surrogate::conditional_policy_identified",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=_proof_steps,
        tags=("surrogate", "policy", "conditional", "identified"),
        timeout_s=15.0,
    )


def _case_shift_policy_identified() -> BenchmarkCase:
    def runner():
        CausalEngine, IdentificationResult, IdentificationStatus, ConditionalInterventionNode, StochasticInterventionNode, StochasticPolicy = _engine_imports()
        engine = CausalEngine()
        graph = _build_chain_graph()
        policy = StochasticPolicy(policy_type="shift", shift_delta=0.25, policy_expr="X + 0.25")
        return engine.identify(treatment="X", outcome="Y", graph=graph, policy=policy)

    def checker(result: Any) -> bool:
        _, IdentificationResult, IdentificationStatus, _, StochasticInterventionNode, _ = _engine_imports()
        if not isinstance(result, IdentificationResult):
            raise AssertionError(f"Expected IdentificationResult, got {type(result).__name__}")
        if result.status is not IdentificationStatus.IDENTIFIED:
            raise AssertionError(f"Expected IDENTIFIED, got {result.status}")
        if result.algorithm_version != "sid_v1":
            raise AssertionError(f"Expected sid_v1, got {result.algorithm_version!r}")
        if getattr(result.estimand_ast.root, "node_type", "") != "stochastic_intervention":
            raise AssertionError("Expected stochastic_intervention estimand root")
        return True

    return BenchmarkCase(
        name="capability::surrogate::shift_policy_identified",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        proof_step_extractor=_proof_steps,
        tags=("surrogate", "policy", "shift", "identified"),
        timeout_s=15.0,
    )


def build_surrogate_experiments_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register(_case_conditional_policy_identified())
    harness.register(_case_shift_policy_identified())
    return harness


def _report_to_dict(report: BenchmarkReport, *, mode: str, preflight: dict[str, Any]) -> dict[str, Any]:
    extra = build_capability_report_extra(
        report,
        CapabilityProofSpec(
            proof_class="stochastic_intervention_identification",
            literature_anchor={
                "primary": "Correa & Bareinboim (2020), A Calculus for Stochastic Interventions: Causal Effect Identification and Surrogate Experiments",
                "secondary": "Díaz & van der Laan (2012), Population Intervention Causal Effects Based on Stochastic Interventions",
            },
            claim_profile_targets=(
                "policy-layer identification",
                "surrogate experiment reduction",
                "stochastic intervention wrapping",
            ),
            competitor_gap=(
                make_gap_row(
                    "baseline_id_only",
                    "stochastic_policy_wrapping",
                    status="gap",
                    note="Standard do-calculus output does not expose the policy layer as a first-class estimand node.",
                    level="layer_3",
                ),
                make_gap_row(
                    "baseline_static_effect",
                    "conditional_policy_support",
                    status="gap",
                    note="Static ATE estimators do not model surrogate conditioning or shift policies.",
                    level="layer_2",
                ),
            ),
            workflow_levels={
                "graph_reduction": "PASS",
                "policy_wrap": "PASS",
                "identification": "PASS",
                "audit_payload": "PASS",
            },
        ),
    )
    return build_report_payload(
        report,
        suite_id="capability_surrogate_experiments",
        mode=mode,
        preflight=preflight,
        sub_circuit="surrogate_experiments",
        extra=extra,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capability win demo — surrogate experiments")
    parser.add_argument("--mode", choices=("smoke", "acceptance"))
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode).value
    preflight = build_preflight(mode=mode, data_source="capability_demo_graphs")
    print_preflight(preflight)

    harness = build_surrogate_experiments_harness()
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
