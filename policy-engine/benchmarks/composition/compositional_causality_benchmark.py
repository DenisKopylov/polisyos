"""Compositional causality benchmark backed by curated fixture cases."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

_BENCH_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _BENCH_ROOT / "src"
for _path in (str(_SRC), str(_BENCH_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from benchmarks.harness import BenchmarkCase, BenchmarkCircuit, BenchmarkHarness, BenchmarkReport  # noqa: E402
from benchmarks.reporting import build_preflight, build_report_payload, print_preflight  # noqa: E402
from benchmarks.runtime import BenchmarkMode, resolve_mode  # noqa: E402
from polisyos.foundry.methods.catalog.causal.graph_reconciliation import ComposeSCMFragments  # noqa: E402
from polisyos.foundry.methods.catalog.causal.protocols import FragmentCompositionData  # noqa: E402
from polisyos.foundry.methods.catalog.causal.query_preservation import (  # noqa: E402
    evaluate_query_preservation_batch,
    update_query_preservation_cache,
)
from polisyos.ir.analytics.alignment_certification import (  # noqa: E402
    AlignmentVerificationConfig,
    verify_fragment_bundle_alignment,
)
from polisyos.ir.analytics.causal_graph import CausalGraphModel  # noqa: E402
from polisyos.ir.analytics.causal_queries import CausalQuery  # noqa: E402
from polisyos.ir.analytics.cross_graph import SCMFragment  # noqa: E402
from polisyos.scientist.backtesting.composition_bridge import (  # noqa: E402
    normalize_alignment_report,
    normalize_composition_certificate,
    normalize_interface_mapping,
    replay_fragment_composition_case,
)


CIRCUIT = BenchmarkCircuit.CAPABILITY_WINS
_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "composition_cases.json"


@dataclasses.dataclass(frozen=True)
class CompositionBenchmarkSpec:
    name: str
    fragments: list[SCMFragment]
    fragment_graphs: dict[str, CausalGraphModel]
    expected_composition_status: str
    expected_needs_expert_review: bool = False
    query: CausalQuery | None = None
    expected_query_status: str | None = None
    config: AlignmentVerificationConfig | None = None
    ontology: tuple[dict[str, Any], ...] = ()
    expected_failure_types: tuple[str, ...] = ()
    expected_ontology_warning: bool = False
    use_scientist_bridge: bool = False
    direct_stitch_pairs: tuple[tuple[str, str], ...] = ()


def _specs() -> list[CompositionBenchmarkSpec]:
    payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    return [_spec_from_payload(item) for item in payload.get("cases", [])]


def _spec_from_payload(payload: dict[str, Any]) -> CompositionBenchmarkSpec:
    return CompositionBenchmarkSpec(
        name=str(payload["name"]),
        fragments=[SCMFragment.model_validate(item) for item in payload.get("fragments", [])],
        fragment_graphs={
            str(key): CausalGraphModel.model_validate(value)
            for key, value in dict(payload.get("fragment_graphs", {})).items()
        },
        expected_composition_status=str(payload["expected_composition_status"]),
        expected_needs_expert_review=bool(payload.get("expected_needs_expert_review", False)),
        query=(
            CausalQuery.model_validate(payload["query"])
            if payload.get("query") is not None
            else None
        ),
        expected_query_status=(
            str(payload["expected_query_status"])
            if payload.get("expected_query_status") is not None
            else None
        ),
        config=(
            AlignmentVerificationConfig.model_validate(payload["config"])
            if payload.get("config") is not None
            else None
        ),
        ontology=tuple(payload.get("ontology", ())),
        expected_failure_types=tuple(str(item) for item in payload.get("expected_failure_types", ())),
        expected_ontology_warning=bool(payload.get("expected_ontology_warning", False)),
        use_scientist_bridge=bool(payload.get("use_scientist_bridge", False)),
        direct_stitch_pairs=tuple(
            tuple(str(part) for part in item)
            for item in payload.get("direct_stitch_pairs", ())
        ),
    )


def _run_spec(spec: CompositionBenchmarkSpec) -> dict[str, Any]:
    report, mapping = verify_fragment_bundle_alignment(
        spec.fragments,
        config=spec.config,
        ontology=spec.ontology,
        stitch_pairs=spec.direct_stitch_pairs,
    )
    result = ComposeSCMFragments.pure_step(
        FragmentCompositionData(
            fragments=spec.fragments,
            fragment_graphs=spec.fragment_graphs,
            alignment_report=report,
            interface_mapping=mapping,
            direct_stitch_pairs=list(spec.direct_stitch_pairs),
            source_fragment_refs={
                fragment.fragment_id: f"fixture://fragment/{fragment.fragment_id}"
                for fragment in spec.fragments
            },
            source_fragment_graph_refs={
                fragment.fragment_id: str(fragment.graph_ref)
                for fragment in spec.fragments
            },
            metadata={
                "alignment_report_ref": f"artifact:alignment:{spec.name}",
                "interface_mapping_ref": f"artifact:mapping:{spec.name}",
            },
        ),
        params={},
    )

    certificate = result["composition_certificate"]
    composed_graph = result.get("composed_graph")
    query_statuses: dict[str, str] = {}
    query_reasons: dict[str, str] = {}
    query_traces: dict[str, Any] = {}
    if spec.query is not None and composed_graph is not None:
        traces = evaluate_query_preservation_batch(
            [spec.query],
            composed_graph=composed_graph,
            fragments=spec.fragments,
            fragment_graphs=spec.fragment_graphs,
            interface_mapping=mapping,
            composition_certificate=certificate,
        )
        certificate, query_statuses = update_query_preservation_cache(
            certificate,
            queries=[spec.query],
            composed_graph=composed_graph,
            fragments=spec.fragments,
            fragment_graphs=spec.fragment_graphs,
            interface_mapping=mapping,
        )
        query_reasons = {
            fingerprint: trace.reason_code
            for fingerprint, trace in sorted(traces.items())
        }
        query_traces = {
            fingerprint: {
                "status": trace.status,
                "reason_code": trace.reason_code,
                "source_fragment_id": trace.source_fragment_id,
                "witness_fragment_ids": list(trace.witness_fragment_ids),
                "source_witness_kind": trace.source_witness_kind,
                "assumption_boundary": trace.assumption_boundary,
            }
            for fingerprint, trace in sorted(traces.items())
        }

    failure_cards = [
        _failure_card_signature(card.model_dump(mode="json"))
        for card in result.get("failure_cards", [])
    ]

    payload: dict[str, Any] = {
        "mode": "direct",
        "composition_status": certificate.status,
        "composition_structure_status": certificate.structure_status,
        "composition_review_status": certificate.review_status,
        "needs_expert_review": bool(result.get("needs_expert_review", False)),
        "query_statuses": dict(query_statuses),
        "query_reasons": dict(query_reasons),
        "query_traces": dict(query_traces),
        "failure_cards": failure_cards,
        "blocking_reasons": [str(item) for item in result.get("blocking_reasons", [])],
        "ontology_warnings": list(report.ontology_mismatch_warnings),
        "alignment_signature": normalize_alignment_report(report),
        "interface_mapping_signature": normalize_interface_mapping(mapping),
        "composition_certificate_signature": normalize_composition_certificate(certificate),
        "composed_graph_signature": _graph_signature(composed_graph) if composed_graph is not None else None,
        "persisted_artifacts": {"composed_graph": composed_graph is not None},
    }

    if spec.use_scientist_bridge:
        with TemporaryDirectory(prefix="composition-bench-") as tmpdir:
            replay = replay_fragment_composition_case(
                fragments=spec.fragments,
                fragment_graphs=spec.fragment_graphs,
                queries=[spec.query] if spec.query is not None else [],
                alignment_verification_config=spec.config,
                precompute_alignment=True,
                direct_stitch_pairs=list(spec.direct_stitch_pairs),
                cas_root=tmpdir,
            )
        payload["mode"] = "scientist_bridge_compare"
        payload["persisted_artifacts"] = dict(replay.persisted_artifacts)
        payload["scientist_equivalent"] = bool(
            payload["composition_status"] == replay.composition_status
            and payload["composition_structure_status"] == replay.composition_structure_status
            and payload["composition_review_status"] == replay.composition_review_status
            and payload["needs_expert_review"] == replay.needs_expert_review
            and payload["query_statuses"] == replay.query_statuses
            and payload["query_reasons"] == replay.query_reasons
            and payload["query_traces"] == replay.query_traces
            and payload["failure_cards"] == replay.failure_cards
            and payload["alignment_signature"] == replay.alignment_signature
            and payload["interface_mapping_signature"] == replay.interface_mapping_signature
            and payload["composition_certificate_signature"] == replay.composition_certificate_signature
            and payload["composed_graph_signature"] == replay.composed_graph_signature
        )
    return payload


def _failure_card_signature(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "failure_type": str(card.get("failure_type")),
        "severity": str(card.get("severity")),
        "description": str(card.get("description")),
        "metadata": dict(card.get("metadata", {})),
    }


def _graph_signature(graph: CausalGraphModel) -> dict[str, Any]:
    return {
        "graph_type": graph.graph_type.value,
        "nodes": list(graph.nodes),
        "edges": [
            {
                "src": edge.src,
                "dst": edge.dst,
                "mark_src": edge.mark_src.value,
                "mark_dst": edge.mark_dst.value,
                "lag": int(edge.lag or 0),
            }
            for edge in sorted(
                graph.edges,
                key=lambda item: (
                    item.src,
                    item.dst,
                    item.mark_src.value,
                    item.mark_dst.value,
                    int(item.lag or 0),
                ),
            )
        ],
    }


def _checker(spec: CompositionBenchmarkSpec):
    def check(result: dict[str, Any]) -> bool:
        if result["composition_status"] != spec.expected_composition_status:
            raise AssertionError(
                f"expected composition status {spec.expected_composition_status}, got {result['composition_status']}"
            )
        if bool(result["needs_expert_review"]) != spec.expected_needs_expert_review:
            raise AssertionError(
                f"expected needs_expert_review={spec.expected_needs_expert_review}, got {result['needs_expert_review']}"
            )
        query_statuses = dict(result.get("query_statuses", {}))
        if spec.expected_query_status is not None:
            if len(query_statuses) != 1:
                raise AssertionError(f"expected exactly one query status, got {query_statuses}")
            observed_status = next(iter(query_statuses.values()))
            if observed_status != spec.expected_query_status:
                raise AssertionError(
                    f"expected query preservation {spec.expected_query_status}, got {observed_status}"
                )
        failure_types = {
            str(card.get("failure_type"))
            for card in result.get("failure_cards", [])
            if isinstance(card, dict)
        }
        for expected_failure_type in spec.expected_failure_types:
            if expected_failure_type not in failure_types:
                raise AssertionError(
                    f"expected failure card {expected_failure_type!r}, got {sorted(failure_types)}"
                )
        if spec.expected_ontology_warning and not result.get("ontology_warnings"):
            raise AssertionError("expected ontology warnings to be emitted")
        if spec.use_scientist_bridge:
            if not result.get("scientist_equivalent", False):
                raise AssertionError("scientist replay must match direct composition signatures")
            persisted = result.get("persisted_artifacts", {})
            if not persisted.get("composition_certificate", False):
                raise AssertionError("scientist bridge case must persist a composition certificate")
        return True

    return check


def _benchmark_case(spec: CompositionBenchmarkSpec) -> BenchmarkCase:
    return BenchmarkCase(
        name=spec.name,
        circuit=CIRCUIT,
        runner=lambda spec=spec: _run_spec(spec),
        checker=_checker(spec),
        tags=("composition", "semantic_alignment", *(("scientist_bridge",) if spec.use_scientist_bridge else ())),
        timeout_s=20.0,
    )


def build_harness() -> BenchmarkHarness:
    harness = BenchmarkHarness()
    harness.register_many([_benchmark_case(spec) for spec in _specs()])
    return harness


def _aggregate_metrics(report: BenchmarkReport) -> dict[str, Any]:
    composition_status_distribution = {
        "preserved": 0,
        "deferred": 0,
        "broken": 0,
        "unknown": 0,
    }
    query_status_distribution = {
        "preserved": 0,
        "broken": 0,
        "unknown": 0,
    }
    alignment_gate_outcomes = {
        "expert_review_required": 0,
        "fully_automated": 0,
    }
    composition_review_status_distribution = {
        "clear": 0,
        "pending_review": 0,
    }
    composition_structure_status_distribution = {
        "valid": 0,
        "invalid": 0,
    }
    failure_card_coverage = {
        "expected_negative_cases": 0,
        "cases_with_failure_cards": 0,
    }
    case_rows: list[dict[str, Any]] = []
    case_groups: dict[str, Any] = {}

    for case in report.cases:
        payload = case.result_payload or {}
        composition_status = str(payload.get("composition_status", "unknown"))
        composition_review_status = str(payload.get("composition_review_status", "clear"))
        composition_structure_status = str(payload.get("composition_structure_status", "valid"))
        composition_status_distribution.setdefault(composition_status, 0)
        composition_status_distribution[composition_status] += 1
        composition_review_status_distribution.setdefault(composition_review_status, 0)
        composition_review_status_distribution[composition_review_status] += 1
        composition_structure_status_distribution.setdefault(composition_structure_status, 0)
        composition_structure_status_distribution[composition_structure_status] += 1
        if payload.get("needs_expert_review"):
            alignment_gate_outcomes["expert_review_required"] += 1
        else:
            alignment_gate_outcomes["fully_automated"] += 1

        query_statuses = payload.get("query_statuses", {})
        if isinstance(query_statuses, dict):
            for status in query_statuses.values():
                token = str(status)
                query_status_distribution.setdefault(token, 0)
                query_status_distribution[token] += 1

        failure_cards = payload.get("failure_cards", [])
        if composition_status in {"broken", "deferred"}:
            failure_card_coverage["expected_negative_cases"] += 1
            if failure_cards:
                failure_card_coverage["cases_with_failure_cards"] += 1

        case_rows.append(
            {
                "case": case.name,
                "composition_status": composition_status,
                "composition_review_status": composition_review_status,
                "composition_structure_status": composition_structure_status,
                "needs_expert_review": bool(payload.get("needs_expert_review", False)),
                "query_statuses": dict(query_statuses) if isinstance(query_statuses, dict) else {},
                "failure_card_count": len(failure_cards) if isinstance(failure_cards, list) else 0,
                "ontology_warning_count": len(payload.get("ontology_warnings", [])),
                "mode": payload.get("mode"),
            }
        )
        case_groups[case.name] = {
            "policy_os_composition": {
                "composition_status": composition_status,
                "composition_review_status": composition_review_status,
                "composition_structure_status": composition_structure_status,
                "failure_card_count": len(failure_cards) if isinstance(failure_cards, list) else 0,
            }
        }

    return {
        "case_rows": case_rows,
        "composition_status_distribution": composition_status_distribution,
        "composition_review_status_distribution": composition_review_status_distribution,
        "composition_structure_status_distribution": composition_structure_status_distribution,
        "alignment_gate_outcomes": alignment_gate_outcomes,
        "query_preservation_status_distribution": query_status_distribution,
        "failure_card_coverage": failure_card_coverage,
        "ranking_summary": {
            "aggregate": {
                "policy_os_composition": {
                    "mean_rank": 1.0,
                    "worst_case_rank": 1.0,
                    "max_deviation_from_best": 0.0,
                    "top_quartile_failures": 0 if report.n_total() == report.n_passed() else 1,
                }
            }
        },
        "case_groups": case_groups,
    }


def _case_details_builder(case: Any) -> dict[str, Any]:
    payload = case.result_payload or {}
    return {
        "composition_status": payload.get("composition_status"),
        "composition_structure_status": payload.get("composition_structure_status"),
        "composition_review_status": payload.get("composition_review_status"),
        "needs_expert_review": bool(payload.get("needs_expert_review", False)),
        "n_failure_cards": len(payload.get("failure_cards", [])),
        "mode": payload.get("mode"),
    }


def _report_to_dict(report: BenchmarkReport, *, mode: str, preflight: dict[str, Any]) -> dict[str, Any]:
    return build_report_payload(
        report,
        suite_id="capability_compositional_causality",
        mode=mode,
        preflight=preflight,
        sub_circuit="compositional_causality",
        include_case_payload=True,
        aggregate_metrics=_aggregate_metrics(report),
        case_details_builder=_case_details_builder,
        extra={
            "benchmark_family": "composition",
            "proof_class": "supplementary_benchmark",
            "literature_anchor": [
                "Pearl (2009): graphical criteria for conditional independence",
                "Richardson & Spirtes (2002): ancestral graph Markov properties",
            ],
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compositional causality stitching benchmark")
    parser.add_argument("--mode", choices=[mode.value for mode in BenchmarkMode])
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    mode = resolve_mode(args.mode).value
    preflight = build_preflight(mode=mode, data_source="curated_composition_fixtures")
    print_preflight(preflight)

    harness = build_harness()
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
