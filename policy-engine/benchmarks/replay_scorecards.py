"""Replay suite scorecards from saved benchmark JSON without re-running methods."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from benchmarks.claim_gate import build_publication_benchmark_card, evaluate_claim_gate
from benchmarks.harness import BenchmarkCircuit, BenchmarkReport, CaseResult, Verdict
from benchmarks.scorecards import (
    build_flagship_scorecard,
    compute_method_presence,
    compute_ranking_summary,
    summarize_method_metrics,
)


def replay_suite_payload(payload: dict[str, Any]) -> dict[str, Any]:
    suite_id = str(payload.get("suite_id") or "")
    report = _report_from_payload(payload)

    if suite_id == "estimation_acic":
        from benchmarks.estimation.acic_benchmark import (
            ACIC_FLAGSHIP_METHOD,
            ACIC_GATE_METHOD_SET,
        )

        aggregate, standardized, grouped = summarize_method_metrics(
            report,
            metric_getters={
                "ate_rmse": lambda result: getattr(result, "ate_rmse", float("nan")),
                "ci_coverage": lambda result: getattr(result, "ci_coverage", float("nan")),
                "ci_width": lambda result: getattr(
                    result, "ci_width_mean", getattr(result, "ci_width", float("nan"))
                ),
                "pehe": lambda result: getattr(
                    result, "pehe_mean", getattr(result, "pehe", float("nan"))
                ),
            },
            standardized_metrics={"ate_rmse"},
            scale_getter=lambda result: getattr(result, "ate_true", float("nan")),
            case_group_getter=lambda case_name: case_name.split("::", 1)[-1],
        )
        ranking = compute_ranking_summary(
            report,
            primary_metric="ate_rmse_standardized",
            metric_getter=lambda result: getattr(result, "ate_rmse", float("nan")),
            scale_getter=lambda result: getattr(result, "ate_true", float("nan")),
            standardized=True,
        )
        presence = compute_method_presence(report, ACIC_GATE_METHOD_SET)
        payload["standardized_metrics"] = standardized
        payload.setdefault("aggregate_metrics", {})
        payload["aggregate_metrics"].update(
            {
                "method_summary": aggregate,
                "ranking_summary": ranking,
                "case_groups": grouped,
                "flagship_scorecard": build_flagship_scorecard(
                    flagship_method=ACIC_FLAGSHIP_METHOD,
                    aggregate_metrics=aggregate,
                    ranking_summary=ranking,
                    thresholds={
                        "mean_rank_max": 2,
                        "max_deviation_from_best_max": 0.10,
                        "top_quartile_failures_max": 0,
                        "ci_coverage_mean_min": 0.80,
                    },
                    gate_method_set=ACIC_GATE_METHOD_SET,
                    method_presence=presence,
                ),
            }
        )
        payload["flagship_presence"] = presence.get(ACIC_FLAGSHIP_METHOD, {})
        payload["blockers"] = [case.name for case in report.cases if not case.passed]
        return payload

    if suite_id == "estimation_lbidd":
        from benchmarks.estimation.lbidd_benchmark import (
            LBIDD_FLAGSHIP_METHOD,
            LBIDD_GATE_METHOD_SET,
            _lbidd_case_group,
            _lbidd_joint_score,
        )

        aggregate, standardized, grouped = summarize_method_metrics(
            report,
            metric_getters={
                "ate_rmse": lambda result: getattr(result, "ate_rmse", float("nan")),
                "pehe": lambda result: getattr(
                    result, "pehe_mean", getattr(result, "pehe", float("nan"))
                ),
                "ci_coverage": lambda result: getattr(result, "ci_coverage", float("nan")),
                "failure_rate": lambda result: getattr(result, "failure_rate", float("nan")),
            },
            standardized_metrics={"ate_rmse", "pehe"},
            scale_getter=lambda result: getattr(result, "ate_true", float("nan")),
            case_group_getter=_lbidd_case_group,
        )
        ranking = compute_ranking_summary(
            report,
            primary_metric="joint_score_standardized",
            metric_getter=_lbidd_joint_score,
            scale_getter=lambda result: getattr(result, "ate_true", float("nan")),
        )
        presence = compute_method_presence(report, LBIDD_GATE_METHOD_SET)
        payload["standardized_metrics"] = standardized
        payload.setdefault("aggregate_metrics", {})
        payload["aggregate_metrics"].update(
            {
                "method_summary": aggregate,
                "ranking_summary": ranking,
                "case_groups": grouped,
                "flagship_scorecard": build_flagship_scorecard(
                    flagship_method=LBIDD_FLAGSHIP_METHOD,
                    aggregate_metrics=aggregate,
                    ranking_summary=ranking,
                    thresholds={
                        "mean_rank_max": 2,
                        "max_deviation_from_best_max": 0.10,
                        "top_quartile_failures_max": 0,
                        "failure_rate_mean_max": 0.25,
                    },
                    gate_method_set=LBIDD_GATE_METHOD_SET,
                    method_presence=presence,
                ),
            }
        )
        payload["flagship_presence"] = presence.get(LBIDD_FLAGSHIP_METHOD, {})
        payload["blockers"] = [case.name for case in report.cases if not case.passed]
        return payload

    if suite_id == "estimation_realcause":
        from benchmarks.estimation.realcause_benchmark import (
            REALCAUSE_FLAGSHIP_METHOD,
            REALCAUSE_GATE_METHOD_SET,
            _build_dataset_group_summaries,
            _realcause_case_group,
        )

        aggregate, standardized, grouped = summarize_method_metrics(
            report,
            metric_getters={
                "ate_rmse": lambda result: getattr(result, "ate_rmse", float("nan")),
                "pehe": lambda result: getattr(
                    result, "pehe_mean", getattr(result, "pehe", float("nan"))
                ),
                "ci_coverage": lambda result: getattr(result, "ci_coverage", float("nan")),
                "failure_rate": lambda result: getattr(result, "failure_rate", float("nan")),
                "kl_mean": lambda result: getattr(
                    result, "kl_mean_mean", getattr(result, "kl_mean", float("nan"))
                ),
            },
            standardized_metrics={"ate_rmse", "pehe"},
            scale_getter=lambda result: getattr(result, "ate_true", float("nan")),
            case_group_getter=_realcause_case_group,
        )
        ranking = compute_ranking_summary(
            report,
            primary_metric="ate_rmse_standardized",
            metric_getter=lambda result: getattr(result, "ate_rmse", float("nan")),
            scale_getter=lambda result: getattr(result, "ate_true", float("nan")),
            standardized=True,
        )
        presence = compute_method_presence(report, REALCAUSE_GATE_METHOD_SET)
        payload["standardized_metrics"] = standardized
        payload.setdefault("aggregate_metrics", {})
        payload["aggregate_metrics"].update(
            {
                "method_summary": aggregate,
                "ranking_summary": ranking,
                "case_groups": grouped,
                "flagship_scorecard": build_flagship_scorecard(
                    flagship_method=REALCAUSE_FLAGSHIP_METHOD,
                    aggregate_metrics=aggregate,
                    ranking_summary=ranking,
                    thresholds={
                        "mean_rank_max": 2,
                        "max_deviation_from_best_max": 0.10,
                        "top_quartile_failures_max": 0,
                        "ci_coverage_mean_min": 0.75,
                        "failure_rate_mean_max": 0.30,
                    },
                    gate_method_set=REALCAUSE_GATE_METHOD_SET,
                    method_presence=presence,
                ),
            }
        )
        payload["dataset_group_summaries"] = _build_dataset_group_summaries(report, grouped)
        payload["flagship_presence"] = presence.get(REALCAUSE_FLAGSHIP_METHOD, {})
        payload["blockers"] = [case.name for case in report.cases if not case.passed]
        return payload

    raise ValueError(f"Unsupported suite for replay: {suite_id}")


def replay_suite_path(path: Path, *, write: bool = False) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    updated = replay_suite_payload(payload)
    if write:
        path.write_text(json.dumps(updated, indent=2), encoding="utf-8")
    return updated


def replay_bundle(
    json_dir: Path,
    *,
    write: bool = False,
    profile: str = "air-m2",
) -> dict[str, Any]:
    suite_paths = sorted(json_dir.glob("estimation_*.json"))
    for path in suite_paths:
        replay_suite_path(path, write=write)
    claim_result = evaluate_claim_gate(json_dir, profile=profile)
    publication_card = build_publication_benchmark_card(json_dir, claim_result=claim_result)
    if write:
        (json_dir / "claim_gate.json").write_text(
            json.dumps(claim_result, indent=2), encoding="utf-8"
        )
        (json_dir / "publication_benchmark_card.json").write_text(
            json.dumps(publication_card, indent=2),
            encoding="utf-8",
        )
    return {
        "replayed_suites": [path.name for path in suite_paths],
        "claim_gate": claim_result,
        "publication_benchmark_card": publication_card,
    }


def _report_from_payload(payload: dict[str, Any]) -> BenchmarkReport:
    cases: list[CaseResult] = []
    for case in payload.get("cases", []):
        verdict_value = str(case.get("verdict", "ERROR"))
        try:
            verdict = Verdict(verdict_value)
        except Exception:
            verdict = Verdict.ERROR
        cases.append(
            CaseResult(
                name=str(case.get("name") or case.get("case_id") or "unknown"),
                circuit=BenchmarkCircuit(str(case.get("circuit") or "estimation")),
                verdict=verdict,
                elapsed_s=float(case.get("elapsed_s") or 0.0),
                memory_delta_mb=float(case.get("memory_delta_mb") or 0.0),
                error_msg=case.get("error_msg"),
                result_payload=_result_payload_from_case(case.get("result_payload")),
            )
        )
    circuits = [
        BenchmarkCircuit(str(item))
        for item in payload.get("core_circuits", [payload.get("sub_circuit") or "estimation"])
        if item
    ]
    if not circuits:
        circuits = [BenchmarkCircuit.ESTIMATION]
    return BenchmarkReport(circuits=circuits, cases=cases, circuit_scores={})


def _namespaceify(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(**{str(key): _namespaceify(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_namespaceify(item) for item in value]
    return value


def _result_payload_from_case(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): _namespaceify(item) for key, item in value.items()}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay estimation scorecards from saved suite JSON"
    )
    parser.add_argument("paths", nargs="+", help="Suite JSON files or directories")
    parser.add_argument("--write", action="store_true", help="Rewrite JSON files in place")
    parser.add_argument(
        "--profile", default="air-m2", help="Claim-gate profile to recompute for directories"
    )
    parser.add_argument(
        "--write-claim-artifacts",
        action="store_true",
        help="When a directory is provided, also rewrite claim_gate.json and publication_benchmark_card.json",
    )
    args = parser.parse_args()

    target_paths: list[Path] = []
    for raw in args.paths:
        path = Path(raw)
        if path.is_dir():
            bundle_result = replay_bundle(
                path,
                write=args.write or args.write_claim_artifacts,
                profile=args.profile,
            )
            if not (args.write or args.write_claim_artifacts):
                print(f"===== {path} =====")
                print(json.dumps(bundle_result["claim_gate"], indent=2))
        else:
            target_paths.append(path)

    for path in target_paths:
        updated = replay_suite_path(path, write=args.write)
        if not args.write:
            print(f"===== {path} =====")
            print(
                json.dumps(
                    updated.get("aggregate_metrics", {}).get("flagship_scorecard", {}), indent=2
                )
            )


if __name__ == "__main__":
    main()
