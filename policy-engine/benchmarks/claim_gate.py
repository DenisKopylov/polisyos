"""Evaluate benchmark bundles against claim-oriented proof profiles."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_BENCH_ROOT = Path(__file__).resolve().parent
for _p in (str(_BENCH_ROOT.parent), str(_BENCH_ROOT.parent / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from benchmarks.reporting import validate_publication_payload
from benchmarks.suite_registry import SuiteSpec, spec_by_suite_id, suites_for_claim_profile, suites_for_profile


CLAIM_PROFILES: dict[str, dict[str, Any]] = {
    "frontier_frontier_claim": {
        "label": "Pearl-Bareinboim frontier completeness claim",
        "headline": False,
    },
    "full_stack_publication_claim": {
        "label": "Publication-grade full-stack SOTA claim",
        "headline": True,
    },
}

DEFAULT_CLAIM_PROFILE = "frontier_frontier_claim"
HEADLINE_CLAIM_PROFILE = "full_stack_publication_claim"

EXACT_PASS_SUITES = {
    "symbolic",
    "missing_mgraph",
    "transport_core",
    "reproducibility_deterministic",
    "reproducibility_regression",
    "reproducibility_audit",
}

ESTIMATION_SUITES = {
    "estimation_acic",
    "estimation_lbidd",
    "estimation_realcause",
}

TEMPORAL_GOLD_SUITES = {
    "temporal_gold",
}

TEMPORAL_HIDDEN_SUITES = {
    "temporal_hidden",
}

CAPABILITY_SUITES = {
    "capability_multi_source",
    "capability_fusion_missingness",
    "capability_symbolic_nonid",
    "capability_ctf_transportability",
    "capability_compiled_audit",
    "capability_cyclic_feedback",
    "capability_surrogate_experiments",
    "capability_nested_surrogate_ctf",
    "capability_multiple_incomplete_sources",
    "capability_did_with_interference",
    "capability_nontransportability_bounds",
}

SUPPLEMENTARY_DISCOVERY_SUITES = {
    "discovery_sachs",
    "discovery_tuebingen",
    "discovery_causeme",
    "discovery_causalbench",
}


def evaluate_claim_gate(
    json_dir: Path,
    *,
    profile: str = "air-m2",
    claim_profile: str | None = None,
) -> dict[str, Any]:
    evaluated_profiles = (
        [claim_profile] if claim_profile else list(CLAIM_PROFILES.keys())
    )
    claim_profile_results: dict[str, Any] = {}

    for profile_name in evaluated_profiles:
        expected_specs = suites_for_claim_profile(profile_name, profile=profile)
        suite_status: dict[str, Any] = {}
        findings: list[dict[str, Any]] = []

        for spec in expected_specs:
            suite_result = _evaluate_suite_report(spec, json_dir=json_dir)
            suite_status[spec.suite_id] = suite_result
            if not suite_result["claim_ready"]:
                findings.append(
                    {
                        "suite_id": spec.suite_id,
                        "status": suite_result["status"],
                        "reason": suite_result["reason"],
                    }
                )

        discovery_guard = _evaluate_discovery_regression(json_dir=json_dir, profile=profile)
        if discovery_guard is not None:
            suite_status["_supplementary_discovery"] = discovery_guard
            if not discovery_guard["claim_ready"]:
                findings.append(
                    {
                        "suite_id": "_supplementary_discovery",
                        "status": discovery_guard["status"],
                        "reason": discovery_guard["reason"],
                    }
                )

        claim_profile_results[profile_name] = {
            "label": CLAIM_PROFILES[profile_name]["label"],
            "expected_suites": [spec.suite_id for spec in expected_specs],
            "suite_status": suite_status,
            "claim_ready": not findings,
            "findings": findings,
        }

    default_claim_profile = claim_profile or DEFAULT_CLAIM_PROFILE
    headline_claim_ready = claim_profile_results.get(HEADLINE_CLAIM_PROFILE, {}).get("claim_ready", False)
    result = {
        "profile": profile,
        "json_dir": str(json_dir),
        "default_claim_profile": default_claim_profile,
        "headline_claim_profile": HEADLINE_CLAIM_PROFILE,
        "claim_profiles": claim_profile_results,
        "claim_ready": claim_profile_results.get(default_claim_profile, {}).get("claim_ready", False),
        "headline_claim_ready": headline_claim_ready,
        "all_claims_ready": all(item["claim_ready"] for item in claim_profile_results.values()),
        "findings": claim_profile_results.get(default_claim_profile, {}).get("findings", []),
    }
    return result


def build_publication_benchmark_card(
    json_dir: Path,
    *,
    claim_result: dict[str, Any],
) -> dict[str, Any]:
    run_summary_path = json_dir / "run_summary.json"
    parent_run_summary = (
        json.loads(run_summary_path.read_text(encoding="utf-8"))
        if run_summary_path.exists()
        else None
    )
    suite_cards: dict[str, Any] = {}
    suite_sources: dict[str, Any] = {}
    overlay_run_ids: set[str] = set()

    for spec in suites_for_profile(claim_result["profile"]):
        report_path = json_dir / f"{spec.suite_id}.json"
        if not report_path.exists():
            continue
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        run_id = payload.get("run_id")
        if run_id:
            overlay_run_ids.add(str(run_id))
        suite_cards[spec.suite_id] = {
            "label": spec.label,
            "proof_class": payload.get("proof_class", spec.proof_class),
            "headline": spec.headline,
            "claim_profile_targets": payload.get("claim_profile_targets", list(spec.claim_profiles)),
            "benchmark_family": payload.get("benchmark_family"),
            "public_claim_eligible": payload.get("public_claim_eligible"),
            "pass_rate": payload.get("pass_rate"),
            "n_total": payload.get("n_total"),
            "n_passed": payload.get("n_passed"),
            "baseline_snapshot_ref": payload.get("baseline_snapshot_ref"),
            "literature_anchor": payload.get("literature_anchor"),
            "flagship_scorecard": payload.get("aggregate_metrics", {}).get("flagship_scorecard"),
            "acceptance_bar": payload.get("aggregate_metrics", {}).get("acceptance_bar"),
            "method_manifest": payload.get("method_manifest", payload.get("method_groups", {})),
            "gate_method_set": payload.get("gate_method_set", []),
            "flagship_presence": payload.get("flagship_presence", {}),
            "exploratory_methods": payload.get("exploratory_methods", []),
            "selection_manifest": payload.get("selection_manifest", {}),
            "overlap_diagnostics": payload.get("overlap_diagnostics", {}),
            "calibration_metrics": payload.get("calibration_metrics", {}),
            "prioritization_metrics": payload.get("prioritization_metrics", {}),
            "dataset_group_summaries": payload.get("dataset_group_summaries", {}),
            "competitor_gap": payload.get("competitor_gap", {}),
        }
        suite_sources[spec.suite_id] = {
            "report_path": str(report_path),
            "run_id": run_id,
            "json_dir": str(json_dir),
        }

    overlay_run_id = next(iter(overlay_run_ids)) if len(overlay_run_ids) == 1 else None
    overlay_parent_run_id = None
    if parent_run_summary and overlay_run_id and parent_run_summary.get("run_id") != overlay_run_id:
        overlay_parent_run_id = parent_run_summary.get("run_id")

    effective_run_summary = parent_run_summary
    if overlay_run_id and (
        parent_run_summary is None
        or parent_run_summary.get("run_id") != overlay_run_id
        or parent_run_summary.get("json_dir") != str(json_dir)
    ):
        effective_run_summary = {
            "run_id": overlay_run_id,
            "profile": claim_result["profile"],
            "json_dir": str(json_dir),
            "suites": [
                {
                    "suite_id": suite_id,
                    "report_path": source["report_path"],
                    "run_id": source["run_id"],
                    "n_total": suite_cards[suite_id].get("n_total"),
                    "n_passed": suite_cards[suite_id].get("n_passed"),
                    "pass_rate": suite_cards[suite_id].get("pass_rate"),
                }
                for suite_id, source in suite_sources.items()
            ],
        }

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "profile": claim_result["profile"],
        "json_dir": str(json_dir),
        "run_summary_path": (
            str(run_summary_path)
            if run_summary_path.exists()
            and parent_run_summary is not None
            and parent_run_summary.get("run_id") == overlay_run_id
            and parent_run_summary.get("json_dir") == str(json_dir)
            else None
        ),
        "run_summary": effective_run_summary,
        "overlay_parent_run_id": overlay_parent_run_id,
        "overlay_run_id": overlay_run_id,
        "effective_suite_sources": suite_sources,
        "default_claim_profile": claim_result["default_claim_profile"],
        "headline_claim_profile": claim_result["headline_claim_profile"],
        "headline_claim_ready": claim_result["headline_claim_ready"],
        "claim_profiles": claim_result["claim_profiles"],
        "suite_cards": suite_cards,
    }


def _evaluate_suite_report(spec: SuiteSpec, *, json_dir: Path) -> dict[str, Any]:
    report_path = json_dir / f"{spec.suite_id}.json"
    if not report_path.exists():
        return {
            "status": "missing_report",
            "claim_ready": False,
            "reason": "suite report missing from bundle",
            "validation_errors": [],
        }

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    validation_errors = validate_publication_payload(payload)
    if validation_errors:
        return {
            "status": "schema_validation_failed",
            "claim_ready": False,
            "reason": "; ".join(validation_errors),
            "validation_errors": validation_errors,
        }

    claim_ready, reason = _evaluate_suite_payload(spec, payload)
    return {
        "status": "passed" if claim_ready else "failed",
        "claim_ready": claim_ready,
        "reason": reason,
        "validation_errors": validation_errors,
    }


def _evaluate_suite_payload(spec: SuiteSpec, payload: dict[str, Any]) -> tuple[bool, str | None]:
    suite_id = spec.suite_id
    n_total = int(payload.get("n_total", 0) or 0)
    n_passed = int(payload.get("n_passed", 0) or 0)
    aggregate = payload.get("aggregate_metrics", {})

    if suite_id in EXACT_PASS_SUITES:
        ok = n_total > 0 and n_total == n_passed
        return ok, None if ok else "requires 100% pass rate"

    if suite_id in CAPABILITY_SUITES:
        competitor_gap = payload.get("competitor_gap", {})
        ok = (
            n_total > 0
            and n_total == n_passed
            and bool(competitor_gap)
            and payload.get("evidence_bundle_complete") is True
            and payload.get("public_claim_eligible") is True
        )
        return ok, None if ok else "capability-gap suite lacks proof-complete evidence"

    if suite_id in ESTIMATION_SUITES:
        scorecard = aggregate.get("flagship_scorecard", {})
        ok = bool(scorecard.get("passes_all"))
        if suite_id == "estimation_realcause":
            group_summaries = payload.get("dataset_group_summaries", {})
            required_groups = ("twins", "lalonde_cps", "lalonde_psid")
            missing_groups = [group for group in required_groups if group not in group_summaries]
            if missing_groups:
                return False, f"RealCause dataset_group_summaries missing required groups: {', '.join(missing_groups)}"
            group_failures = [
                group
                for group in required_groups
                if not bool((group_summaries.get(group) or {}).get("passes_all"))
            ]
            ok = ok and not group_failures
            return ok, None if ok else (
                "flagship scorecard does not meet suite thresholds"
                if not group_failures
                else f"RealCause grouped scorecards not green: {', '.join(group_failures)}"
            )
        return ok, None if ok else "flagship scorecard does not meet suite thresholds"

    if suite_id == "hte_interpretable":
        acceptance_bar = aggregate.get("acceptance_bar", {})
        ok = bool(acceptance_bar.get("passes_all"))
        return ok, None if ok else "HTE acceptance bar is not fully green"

    if suite_id in TEMPORAL_GOLD_SUITES:
        scorecard = aggregate.get("temporal_scorecard", {})
        ok = (
            n_total > 0
            and n_total == n_passed
            and bool(scorecard.get("passes_all"))
            and float(scorecard.get("engine_route_coverage_rate", 0.0)) == 1.0
            and float(scorecard.get("bundle_presence_rate", 0.0)) == 1.0
            and float(scorecard.get("artifact_loadability_rate", 0.0)) == 1.0
            and float(scorecard.get("policy_lineage_rate", 0.0)) == 1.0
            and float(scorecard.get("diagnostics_artifact_presence_rate", 0.0)) == 1.0
            and float(scorecard.get("truthful_fallback_disclosure_rate", 0.0)) == 1.0
            and payload.get("baseline_snapshot_ref") == "temporal_gold@synthetic-v1"
            and bool(payload.get("regression_guard"))
        )
        return ok, None if ok else "temporal gold scorecard is not fully green"

    if suite_id in TEMPORAL_HIDDEN_SUITES:
        summary = aggregate.get("hidden_temporal_summary", {})
        ok = (
            n_total > 0
            and n_total == n_passed
            and float(summary.get("safe_rejection_rate", 0.0)) == 1.0
            and float(summary.get("diagnostics_presence_rate", 0.0)) == 1.0
            and float(summary.get("fallback_success_rate", 0.0)) == 1.0
            and float(summary.get("artifact_reload_failure_rate", 1.0)) == 0.0
        )
        return ok, None if ok else "temporal hidden stress suite requires all hidden checks green"

    if suite_id in {"policy_natural_experiments", "policy_did_interference"}:
        scorecard = aggregate.get("flagship_scorecard", {})
        ok = (
            n_total > 0
            and n_total == n_passed
            and bool(scorecard.get("passes_all"))
            and bool(payload.get("baseline_snapshot_ref"))
            and bool(payload.get("regression_guard"))
        )
        return ok, None if ok else "policy benchmark suite lacks publication-grade scorecard or baseline guard"

    if suite_id == "adversarial_symbolic_stress":
        accuracy = aggregate.get("accuracy", {})
        false_positive_rate = accuracy.get("false_positive_rate", 1.0)
        if false_positive_rate is None:
            false_positive_rate = 1.0
        ok = (
            n_total > 0
            and n_total == n_passed
            and float(false_positive_rate) == 0.0
        )
        return ok, None if ok else "adversarial symbolic stress requires zero false positives"

    return False, "unhandled suite in claim gate"


def _evaluate_discovery_regression(*, json_dir: Path, profile: str) -> dict[str, Any] | None:
    available_specs = {spec.suite_id: spec for spec in suites_for_profile(profile)}
    relevant = [suite_id for suite_id in SUPPLEMENTARY_DISCOVERY_SUITES if suite_id in available_specs]
    if not relevant:
        return None

    findings: list[str] = []
    evaluated: dict[str, Any] = {}
    for suite_id in relevant:
        report_path = json_dir / f"{suite_id}.json"
        if not report_path.exists():
            findings.append(f"{suite_id}: missing discovery report")
            evaluated[suite_id] = {"status": "missing_report"}
            continue
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        errors = validate_publication_payload(payload)
        if errors:
            findings.append(f"{suite_id}: {'; '.join(errors)}")
            evaluated[suite_id] = {"status": "schema_validation_failed", "errors": errors}
            continue
        n_total = int(payload.get("n_total", 0) or 0)
        n_passed = int(payload.get("n_passed", 0) or 0)
        if n_total <= 0 or n_total != n_passed:
            findings.append(f"{suite_id}: discovery suite regressed from all-pass baseline")
            evaluated[suite_id] = {"status": "failed"}
        else:
            evaluated[suite_id] = {"status": "passed"}

    return {
        "status": "passed" if not findings else "failed",
        "claim_ready": not findings,
        "reason": None if not findings else "; ".join(findings),
        "evaluated": evaluated,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate benchmark claim readiness.")
    parser.add_argument("--json-dir", required=True)
    parser.add_argument("--profile", default="air-m2", choices=("air-m2", "extended"))
    parser.add_argument("--claim-profile", choices=tuple(CLAIM_PROFILES.keys()))
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    json_dir = Path(args.json_dir)
    result = evaluate_claim_gate(
        json_dir,
        profile=args.profile,
        claim_profile=args.claim_profile,
    )
    rendered = json.dumps(result, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(rendered + "\n", encoding="utf-8")
        card = build_publication_benchmark_card(json_dir, claim_result=result)
        card_path = output_path.with_name("publication_benchmark_card.json")
        card_path.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["claim_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
