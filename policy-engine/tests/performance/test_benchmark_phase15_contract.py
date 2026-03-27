from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from benchmarks.harness import BenchmarkCircuit, BenchmarkReport, CaseResult, Verdict
from benchmarks.method_registry import (
    build_method_registry,
    canonical_method_name,
    infer_benchmark_role,
    infer_method_group,
)
from benchmarks.metrics import compute_accuracy_metrics
from benchmarks.claim_gate import build_publication_benchmark_card, evaluate_claim_gate
from benchmarks.comparators import (
    REQUIRED_ACCEPTANCE_COMPARATORS,
    build_research_acceptance_comparator_status,
    comparator_degraded_reasons,
    comparator_distribution_names,
    comparator_required_modules,
)
from benchmarks.reporting import WORKFLOW_LEVELS, build_preflight, build_report_payload, validate_publication_payload
from benchmarks.replay_scorecards import replay_bundle, replay_suite_payload
from benchmarks.research_metrics import summarize_calibration_metrics
from benchmarks.runtime import BenchmarkMode, BenchmarkTier, resolve_tier
from benchmarks.scorecards import (
    build_flagship_scorecard,
    compute_method_presence,
    compute_ranking_summary,
    summarize_method_metrics,
)
from benchmarks.suite_registry import alias_targets, canonical_suite_id, suites_for_claim_profile, suites_for_profile


def test_benchmark_report_results_alias_points_to_cases():
    case = CaseResult(
        name="symbolic::dummy",
        circuit=BenchmarkCircuit.SYMBOLIC,
        verdict=Verdict.PASS,
        elapsed_s=0.01,
        memory_delta_mb=0.0,
    )
    report = BenchmarkReport(
        circuits=[BenchmarkCircuit.SYMBOLIC],
        cases=[case],
        circuit_scores={},
    )
    assert report.results == report.cases
    assert report.results[0].name == "symbolic::dummy"


def test_accuracy_metrics_false_positive_rate_uses_exact_confusion_counts():
    metrics = compute_accuracy_metrics(
        [
            (True, True, True),
            (False, False, True),
            (False, True, True),
        ]
    )
    assert metrics.n_true_positive == 1
    assert metrics.n_true_negative == 1
    assert metrics.n_false_positive == 1
    assert metrics.n_false_negative == 0
    assert metrics.false_positive_rate == 0.5


def test_report_payload_uses_unified_schema():
    case = CaseResult(
        name="transport::demo",
        circuit=BenchmarkCircuit.TRANSPORT,
        verdict=Verdict.PASS,
        elapsed_s=0.02,
        memory_delta_mb=0.0,
    )
    report = BenchmarkReport(
        circuits=[BenchmarkCircuit.TRANSPORT],
        cases=[case],
        circuit_scores={},
    )
    preflight = build_preflight(
        mode="smoke",
        benchmark_tier="local_evidence",
        data_source="synthetic_suite",
        run_id="run-123",
        estimator_profile="flagship_competitive",
    )
    payload = build_report_payload(
        report,
        suite_id="transport_core",
        mode="smoke",
        preflight=preflight,
        sub_circuit="transport",
    )

    assert payload["suite_id"] == "transport_core"
    assert payload["run_id"] == "run-123"
    assert payload["mode"] == "smoke"
    assert payload["benchmark_tier"] == "local_evidence"
    assert payload["estimator_profile"] == "flagship_competitive"
    assert payload["core_circuits"] == ["transport"]
    assert payload["data_source"] == "synthetic_suite"
    assert payload["preflight"]["data_source"] == "synthetic_suite"
    assert payload["cases"][0]["name"] == "transport::demo"
    assert payload["cases"][0]["case_id"] == "transport::demo"
    assert payload["cases"][0]["status"] == "passed"
    assert payload["cases"][0]["runtime"]["elapsed_s"] == 0.02
    assert "blockers" in payload
    assert "aggregate_metrics" in payload
    assert "standardized_metrics" in payload
    assert "method_groups" in payload
    assert "method_manifest" in payload
    assert "gate_method_set" in payload
    assert "flagship_presence" in payload
    assert "exploratory_methods" in payload
    assert payload["proof_class"] == "standard"
    assert payload["claim_profile_targets"] == []
    assert payload["competitor_gap"] == {}
    assert payload["preflight"]["environment"]["python_version"]
    assert "run_config_hash" in payload["preflight"]
    assert "installed_comparator_versions" in payload["preflight"]


def test_resolve_tier_defaults_follow_mode():
    assert resolve_tier(mode=BenchmarkMode.SMOKE) is BenchmarkTier.LOCAL_EVIDENCE
    assert resolve_tier(mode=BenchmarkMode.ACCEPTANCE) is BenchmarkTier.RESEARCH_ACCEPTANCE


def test_suite_registry_resolves_capability_and_legacy_aliases():
    assert canonical_suite_id("capability_pipeline_audit") == "capability_compiled_audit"
    ids = {spec.suite_id for spec in alias_targets("capability_demos")}
    assert "capability_symbolic_nonid" in ids
    assert "capability_compiled_audit" in ids
    publication_ids = {spec.suite_id for spec in alias_targets("publication_core")}
    assert "symbolic" in publication_ids
    assert "estimation_acic" in publication_ids
    assert "temporal_gold" in publication_ids
    assert "capability_multi_source" in publication_ids
    stress_ids = {spec.suite_id for spec in alias_targets("stress")}
    assert stress_ids == {"adversarial_symbolic_stress", "temporal_hidden"}
    temporal_ids = {spec.suite_id for spec in alias_targets("temporal")}
    assert temporal_ids == {"temporal_gold", "temporal_hidden"}
    frontier_ids = {spec.suite_id for spec in suites_for_claim_profile("frontier_frontier_claim", profile="air-m2")}
    assert "symbolic" in frontier_ids
    assert "temporal_gold" in frontier_ids
    assert "temporal_hidden" in frontier_ids
    assert "capability_symbolic_nonid" in frontier_ids


def test_method_registry_normalizes_flagship_aliases():
    assert canonical_method_name("policy_os_drlearner") == "policy_os_drlearner_cf"
    assert canonical_method_name("external_causal_forest_econml") == "policy_os_causal_forest"
    assert infer_method_group("external_dml_econml") == "external_comparators"
    assert infer_benchmark_role("policy_os_tmle_cf") == "production_challenger"
    registry = build_method_registry(
        {"policy_os_drlearner", "external_causal_forest_econml", "policy_os_causal_bcf", "policy_os_forestdr_cf"},
        benchmark_roles={"policy_os_causal_bcf": "flagship"},
    )
    assert registry["policy_os_drlearner"]["canonical_name"] == "policy_os_drlearner_cf"
    assert registry["external_causal_forest_econml"]["group"] == "policy_os_competitive"
    assert registry["policy_os_causal_bcf"]["group"] == "policy_os_competitive"
    assert registry["policy_os_forestdr_cf"]["group"] == "policy_os_competitive"
    assert registry["policy_os_causal_bcf"]["benchmark_role"] == "flagship"


def test_comparator_scaffold_covers_research_acceptance_env():
    status = build_research_acceptance_comparator_status()
    assert set(status) == set(REQUIRED_ACCEPTANCE_COMPARATORS)
    assert set(comparator_distribution_names()) == set(REQUIRED_ACCEPTANCE_COMPARATORS)
    assert set(comparator_required_modules()) == set(REQUIRED_ACCEPTANCE_COMPARATORS)
    degraded = comparator_degraded_reasons({"econml": "missing", "zepid": "available"})
    assert "econml comparator unavailable" in degraded


def test_y0_reference_suite_agrees_when_installed():
    pytest = __import__("pytest")
    pytest.importorskip("y0")
    from benchmarks.symbolic.run_symbolic_benchmark import _run_y0_comparison

    summary = _run_y0_comparison(None)
    assert summary["skipped"] is False
    assert summary["all_agreed"] is True


def test_scorecards_compute_standardized_metrics_and_flagship_bars():
    case_a = CaseResult(
        name="acic::case_a",
        circuit=BenchmarkCircuit.ESTIMATION,
        verdict=Verdict.PASS,
        elapsed_s=0.01,
        memory_delta_mb=0.0,
        result_payload={
            "policy_os_tmle_cf": SimpleNamespace(ate_rmse=0.10, ci_coverage=0.90, ate_true=1.0),
            "baseline": SimpleNamespace(ate_rmse=0.20, ci_coverage=0.85, ate_true=1.0),
        },
    )
    case_b = CaseResult(
        name="acic::case_b",
        circuit=BenchmarkCircuit.ESTIMATION,
        verdict=Verdict.PASS,
        elapsed_s=0.01,
        memory_delta_mb=0.0,
        result_payload={
            "policy_os_tmle_cf": SimpleNamespace(ate_rmse=0.15, ci_coverage=0.95, ate_true=1.5),
            "baseline": SimpleNamespace(ate_rmse=0.30, ci_coverage=0.80, ate_true=1.5),
        },
    )
    report = BenchmarkReport(
        circuits=[BenchmarkCircuit.ESTIMATION],
        cases=[case_a, case_b],
        circuit_scores={},
    )

    aggregate, standardized, grouped = summarize_method_metrics(
        report,
        metric_getters={
            "ate_rmse": lambda result: getattr(result, "ate_rmse", float("nan")),
            "ci_coverage": lambda result: getattr(result, "ci_coverage", float("nan")),
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
    scorecard = build_flagship_scorecard(
        flagship_method="policy_os_tmle_cf",
        aggregate_metrics=aggregate,
        ranking_summary=ranking,
        thresholds={
            "mean_rank_max": 2,
            "max_deviation_from_best_max": 0.10,
            "top_quartile_failures_max": 0,
            "ci_coverage_mean_min": 0.80,
        },
    )

    assert aggregate["policy_os_tmle_cf"]["ate_rmse_mean"] == 0.125
    assert "ate_rmse_standardized_mean" in standardized["policy_os_tmle_cf"]
    assert grouped["case_a"]["policy_os_tmle_cf"]["ate_rmse_mean"] == 0.10
    assert ranking["aggregate"]["policy_os_tmle_cf"]["mean_rank"] == 1.0
    assert scorecard["checks"]["ci_coverage_mean"] is True
    assert scorecard["passes_all"] is True


def test_scorecard_marks_missing_flagship_instead_of_null() -> None:
    case = CaseResult(
        name="realcause::lalonde_cps_sample0",
        circuit=BenchmarkCircuit.ESTIMATION,
        verdict=Verdict.PASS,
        elapsed_s=0.01,
        memory_delta_mb=0.0,
        result_payload={
            "policy_os_tmle_cf": SimpleNamespace(ate_rmse=0.10, ci_coverage=0.90, ate_true=1.0),
            "baseline": SimpleNamespace(ate_rmse=0.20, ci_coverage=0.80, ate_true=1.0),
        },
    )
    report = BenchmarkReport(
        circuits=[BenchmarkCircuit.ESTIMATION],
        cases=[case],
        circuit_scores={},
    )
    aggregate, _, _ = summarize_method_metrics(
        report,
        metric_getters={
            "ate_rmse": lambda result: getattr(result, "ate_rmse", float("nan")),
            "ci_coverage": lambda result: getattr(result, "ci_coverage", float("nan")),
        },
    )
    ranking = compute_ranking_summary(
        report,
        primary_metric="ate_rmse",
        metric_getter=lambda result: getattr(result, "ate_rmse", float("nan")),
    )
    method_presence = compute_method_presence(
        report,
        ["policy_os_xlearner_cf", "policy_os_tmle_cf"],
    )
    scorecard = build_flagship_scorecard(
        flagship_method="policy_os_xlearner_cf",
        aggregate_metrics=aggregate,
        ranking_summary=ranking,
        thresholds={
            "mean_rank_max": 2,
            "ci_coverage_mean_min": 0.80,
        },
        gate_method_set=["policy_os_tmle_cf"],
        method_presence=method_presence,
    )

    assert scorecard["flagship_status"] == "flagship_missing"
    assert scorecard["passes_all"] is False
    assert scorecard["selected_gate_method"] == "policy_os_tmle_cf"
    assert scorecard["flagship_presence"]["present"] is False


def test_ranking_summary_stabilizes_near_zero_best_values() -> None:
    case = CaseResult(
        name="acic::near_zero",
        circuit=BenchmarkCircuit.ESTIMATION,
        verdict=Verdict.PASS,
        elapsed_s=0.01,
        memory_delta_mb=0.0,
        result_payload={
            "best": SimpleNamespace(ate_rmse=0.0),
            "challenger": SimpleNamespace(ate_rmse=1e-4),
        },
    )
    report = BenchmarkReport(
        circuits=[BenchmarkCircuit.ESTIMATION],
        cases=[case],
        circuit_scores={},
    )
    ranking = compute_ranking_summary(
        report,
        primary_metric="ate_rmse",
        metric_getter=lambda result: getattr(result, "ate_rmse", float("nan")),
    )

    assert ranking["aggregate"]["challenger"]["max_deviation_from_best"] == 0.1


def test_ranking_summary_for_standardized_metrics_does_not_double_normalize() -> None:
    case = CaseResult(
        name="acic::scaled_case",
        circuit=BenchmarkCircuit.ESTIMATION,
        verdict=Verdict.PASS,
        elapsed_s=0.01,
        memory_delta_mb=0.0,
        result_payload={
            "best": SimpleNamespace(ate_rmse=0.0, ate_true=10.0),
            "challenger": SimpleNamespace(ate_rmse=0.1, ate_true=10.0),
        },
    )
    report = BenchmarkReport(
        circuits=[BenchmarkCircuit.ESTIMATION],
        cases=[case],
        circuit_scores={},
    )
    ranking = compute_ranking_summary(
        report,
        primary_metric="ate_rmse_standardized",
        metric_getter=lambda result: getattr(result, "ate_rmse", float("nan")),
        scale_getter=lambda result: getattr(result, "ate_true", float("nan")),
        standardized=True,
    )

    assert ranking["aggregate"]["challenger"]["max_deviation_from_best"] == 0.01


def test_summarize_calibration_metrics_merges_weighted_summary_records() -> None:
    summary = summarize_calibration_metrics(
        [
            {
                "ci_coverage_mean": 0.5,
                "ci_width_mean": 1.0,
                "eceth_mean": 0.2,
                "calibration_mode_counts": {"isotonic": 2},
                "n_records": 2,
            },
            {
                "ci_coverage_mean": 1.0,
                "ci_width_mean": 2.0,
                "eceth_mean": 0.4,
                "calibration_mode_counts": {"identity": 1},
                "n_records": 1,
            },
        ]
    )

    assert summary["ci_coverage_mean"] == 2.0 / 3.0
    assert summary["ci_width_mean"] == 4.0 / 3.0
    assert summary["eceth_mean"] == 0.8 / 3.0
    assert summary["calibration_mode_counts"] == {"isotonic": 2, "identity": 1}


def test_validate_publication_payload_rejects_capability_without_gap_matrix():
    payload = {
        "suite_id": "capability_multi_source",
        "proof_class": "capability_gap",
        "workflow_levels": list(WORKFLOW_LEVELS),
        "competitor_gap": {},
        "evidence_bundle_complete": False,
        "public_claim_eligible": False,
    }
    errors = validate_publication_payload(payload)
    assert any("competitor_gap" in error for error in errors)
    assert any("evidence_bundle_complete" in error for error in errors)


def test_validate_publication_payload_requires_literature_anchor_for_public_claim_suite() -> None:
    errors = validate_publication_payload(
        {
            "suite_id": "estimation_acic",
            "public_claim_eligible": True,
            "aggregate_metrics": {"flagship_scorecard": {"passes_all": True}},
            "selection_manifest": {},
            "overlap_diagnostics": {},
            "calibration_metrics": {},
            "blockers": [],
        }
    )
    assert "public_claim_eligible suites require literature_anchor" in errors


def test_validate_publication_payload_requires_temporal_suite_fields() -> None:
    gold_errors = validate_publication_payload(
        {
            "suite_id": "temporal_gold",
            "aggregate_metrics": {"temporal_scorecard": {}},
            "proof_class": "publication_benchmark",
        }
    )
    assert "temporal_gold requires baseline_snapshot_ref=temporal_gold@synthetic-v1" in gold_errors
    assert (
        "temporal_gold requires aggregate_metrics.temporal_scorecard.engine_route_coverage_rate"
        in gold_errors
    )
    assert (
        "temporal_gold requires aggregate_metrics.temporal_scorecard.artifact_loadability_rate"
        in gold_errors
    )

    hidden_errors = validate_publication_payload(
        {
            "suite_id": "temporal_hidden",
            "aggregate_metrics": {"hidden_temporal_summary": {}, "accuracy": {}},
            "proof_class": "stress_evidence",
            "benchmark_family": "temporal_causal_dynamics",
            "public_claim_eligible": True,
        }
    )
    assert "temporal_hidden requires baseline_snapshot_ref=temporal_hidden@synthetic-v1" in hidden_errors
    assert "temporal_hidden requires public_claim_eligible=false" in hidden_errors
    assert (
        "temporal_hidden requires aggregate_metrics.hidden_temporal_summary.artifact_reload_failure_rate"
        in hidden_errors
    )


def test_claim_gate_marks_complete_air_m2_bundle_as_ready(tmp_path: Path):
    for spec in suites_for_profile("air-m2"):
        payload = {
            "suite_id": spec.suite_id,
            "n_total": 1,
            "n_passed": 1,
            "aggregate_metrics": {},
            "proof_class": spec.proof_class,
            "claim_profile_targets": list(spec.claim_profiles),
        }
        if spec.suite_id.startswith("estimation_"):
            payload["aggregate_metrics"]["flagship_scorecard"] = {"passes_all": True}
            payload["selection_manifest"] = {"policy_os_xlearner_cf": {"n_records": 1}}
            payload["overlap_diagnostics"] = {"policy_os_xlearner_cf": {"n_records": 1}}
            payload["calibration_metrics"] = {"policy_os_xlearner_cf": {"n_records": 1}}
            payload["public_claim_eligible"] = True
            payload["literature_anchor"] = "synthetic estimation anchor"
            if spec.suite_id == "estimation_realcause":
                payload["dataset_group_summaries"] = {
                    "twins": {"passes_all": True},
                    "lalonde_cps": {"passes_all": True},
                    "lalonde_psid": {"passes_all": True},
                }
        elif spec.suite_id == "hte_interpretable":
            payload["aggregate_metrics"]["acceptance_bar"] = {"passes_all": True}
            payload["selection_manifest"] = {"policy_os_xlearner_cf": {"n_records": 1}}
            payload["calibration_metrics"] = {"policy_os_xlearner_cf": {"n_records": 1}}
            payload["prioritization_metrics"] = {"policy_os_xlearner_cf": {"n_records": 1}}
            payload["blockers"] = []
            payload["public_claim_eligible"] = True
            payload["literature_anchor"] = "synthetic hte anchor"
            payload["cases"] = [
                {
                    "case_id": "hte_cate::demo",
                    "name": "hte_cate::demo",
                    "status": "passed",
                    "verdict": "PASS",
                    "acceptance": {"passed": True},
                    "metrics": {"method_summary": {}},
                    "runtime": {"elapsed_s": 0.1},
                }
            ]
        elif spec.suite_id in {"policy_natural_experiments", "policy_did_interference"}:
            payload["aggregate_metrics"]["flagship_scorecard"] = {"passes_all": True}
            payload["aggregate_metrics"]["ranking_summary"] = {"aggregate": {"policy_os_flagship": {"mean_rank": 1.0}}}
            payload["aggregate_metrics"]["case_groups"] = {"dev_batch": {"policy_os_flagship": {"ate_rmse_mean": 0.1}}}
            payload["benchmark_family"] = spec.suite_id
            payload["dataset_regime"] = "synthetic_policy_regime"
            payload["baseline_snapshot_ref"] = f"{spec.suite_id}-v1"
            payload["regression_guard"] = {"rule": "no_regression"}
        elif spec.suite_id == "temporal_gold":
            payload["aggregate_metrics"]["temporal_scorecard"] = {
                "passes_all": True,
                "engine_route_coverage_rate": 1.0,
                "bundle_presence_rate": 1.0,
                "artifact_loadability_rate": 1.0,
                "policy_lineage_rate": 1.0,
                "diagnostics_artifact_presence_rate": 1.0,
                "truthful_fallback_disclosure_rate": 1.0,
            }
            payload["benchmark_family"] = "temporal_causal_dynamics"
            payload["baseline_snapshot_ref"] = "temporal_gold@synthetic-v1"
            payload["regression_guard"] = {"rule": "no_regression"}
            payload["public_claim_eligible"] = True
            payload["literature_anchor"] = "synthetic temporal anchor"
        elif spec.suite_id == "temporal_hidden":
            payload["aggregate_metrics"]["hidden_temporal_summary"] = {
                "n_total": 1,
                "n_passed": 1,
                "safe_rejection_rate": 1.0,
                "diagnostics_presence_rate": 1.0,
                "fallback_success_rate": 1.0,
                "artifact_reload_failure_rate": 0.0,
                "passes_all": True,
            }
            payload["aggregate_metrics"]["accuracy"] = {"n_total": 1, "n_passed": 1, "pass_rate": 1.0}
            payload["benchmark_family"] = "temporal_causal_dynamics"
            payload["baseline_snapshot_ref"] = "temporal_hidden@synthetic-v1"
            payload["regression_guard"] = {"rule": "no_regression"}
            payload["public_claim_eligible"] = False
        elif spec.suite_id == "adversarial_symbolic_stress":
            payload["aggregate_metrics"]["accuracy"] = {"false_positive_rate": 0.0}
            payload["benchmark_family"] = "adversarial_symbolic"
            payload["baseline_snapshot_ref"] = "adversarial-v1"
        elif spec.suite_id.startswith("capability_"):
            payload["workflow_levels"] = list(WORKFLOW_LEVELS)
            payload["competitor_gap"] = {
                "y0": {level: {"status": "unsupported" if level != "expressible" else "partial"} for level in WORKFLOW_LEVELS}
            }
            payload["evidence_bundle_complete"] = True
            payload["public_claim_eligible"] = True
            payload["literature_anchor"] = "synthetic capability anchor"
        elif spec.suite_id.startswith("discovery_"):
            payload["benchmark_family"] = spec.suite_id
            payload["baseline_snapshot_ref"] = f"{spec.suite_id}-v1"
            payload["regression_guard"] = {"rule": "no_regression"}
        (tmp_path / f"{spec.suite_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    result = evaluate_claim_gate(tmp_path, profile="air-m2")
    assert result["claim_ready"] is True
    assert result["findings"] == []
    assert result["claim_profiles"]["frontier_frontier_claim"]["claim_ready"] is True
    card = build_publication_benchmark_card(tmp_path, claim_result=result)
    assert card["suite_cards"]["symbolic"]["proof_class"] == "frontier_correctness"
    assert card["suite_cards"]["capability_multi_source"]["public_claim_eligible"] is True


def test_validate_publication_payload_requires_research_fields_for_estimation_and_hte() -> None:
    estimation_errors = validate_publication_payload(
        {
            "suite_id": "estimation_acic",
            "aggregate_metrics": {"flagship_scorecard": {"passes_all": True}},
            "proof_class": "standard",
        }
    )
    assert "estimation suites require selection_manifest" in estimation_errors
    assert "estimation suites require overlap_diagnostics" in estimation_errors
    assert "estimation suites require calibration_metrics" in estimation_errors

    hte_errors = validate_publication_payload(
        {
            "suite_id": "hte_interpretable",
            "aggregate_metrics": {"acceptance_bar": {"passes_all": True}},
            "proof_class": "standard",
        }
    )
    assert "hte_interpretable requires selection_manifest" in hte_errors
    assert "hte_interpretable requires calibration_metrics" in hte_errors
    assert "hte_interpretable requires prioritization_metrics" in hte_errors
    assert "hte_interpretable requires non-empty cases" in hte_errors


def test_publication_card_tracks_overlay_suite_sources(tmp_path: Path) -> None:
    (tmp_path / "run_summary.json").write_text(
        json.dumps({"run_id": "parent-run", "json_dir": str(tmp_path.parent)}),
        encoding="utf-8",
    )
    suite_payload = {
        "suite_id": "estimation_realcause",
        "run_id": "overlay-run",
        "n_total": 1,
        "n_passed": 1,
        "proof_class": "standard",
        "aggregate_metrics": {"flagship_scorecard": {"passes_all": True}},
        "selection_manifest": {"policy_os_xlearner_cf": {"n_records": 2}},
        "overlap_diagnostics": {"policy_os_xlearner_cf": {"n_records": 2}},
        "calibration_metrics": {"policy_os_xlearner_cf": {"n_records": 2}},
        "dataset_group_summaries": {
            "twins": {"passes_all": True},
            "lalonde_cps": {"passes_all": True},
            "lalonde_psid": {"passes_all": True},
        },
    }
    (tmp_path / "estimation_realcause.json").write_text(json.dumps(suite_payload), encoding="utf-8")
    claim_result = {
        "profile": "air-m2",
        "default_claim_profile": "frontier_frontier_claim",
        "headline_claim_profile": "full_stack_publication_claim",
        "headline_claim_ready": False,
        "claim_profiles": {},
    }

    card = build_publication_benchmark_card(tmp_path, claim_result=claim_result)
    assert card["overlay_parent_run_id"] == "parent-run"
    assert card["overlay_run_id"] == "overlay-run"
    assert card["run_summary"]["run_id"] == "overlay-run"


def test_replay_bundle_recomputes_claim_artifacts_for_directory(tmp_path: Path) -> None:
    suite_payload = {
        "suite_id": "estimation_acic",
        "run_id": "overlay-run",
        "core_circuits": ["estimation"],
        "benchmark_tier": "local_evidence",
        "public_claim_eligible": True,
        "literature_anchor": "synthetic estimation anchor",
        "claim_profile_targets": ["full_stack_publication_claim"],
        "cases": [
            {
                "case_id": "acic::demo",
                "name": "acic::demo",
                "circuit": "estimation",
                "verdict": "PASS",
                "elapsed_s": 0.1,
                "memory_delta_mb": 0.0,
                "result_payload": {
                    "policy_os_xlearner_cf": {"ate_rmse": 0.1, "ci_coverage": 0.9, "ate_true": 1.0},
                    "policy_os_tmle_cf": {"ate_rmse": 0.2, "ci_coverage": 0.8, "ate_true": 1.0},
                },
            }
        ],
        "aggregate_metrics": {},
        "selection_manifest": {"policy_os_xlearner_cf": {"n_records": 1}},
        "overlap_diagnostics": {"policy_os_xlearner_cf": {"n_records": 1}},
        "calibration_metrics": {"policy_os_xlearner_cf": {"n_records": 1}},
        "blockers": [],
    }
    (tmp_path / "estimation_acic.json").write_text(json.dumps(suite_payload), encoding="utf-8")

    replayed = replay_bundle(tmp_path, write=True, profile="air-m2")

    assert (tmp_path / "claim_gate.json").exists()
    assert (tmp_path / "publication_benchmark_card.json").exists()
    assert replayed["claim_gate"]["profile"] == "air-m2"


def test_replay_suite_payload_recomputes_acic_scorecard() -> None:
    payload = {
        "suite_id": "estimation_acic",
        "cases": [
            {
                "name": "acic::case_a",
                "case_id": "acic::case_a",
                "circuit": "estimation",
                "verdict": "PASS",
                "elapsed_s": 0.01,
                "memory_delta_mb": 0.0,
                "result_payload": {
                    "policy_os_xlearner_cf": {"ate_rmse": 0.1, "ci_coverage": 1.0, "ci_width_mean": 1.0, "pehe_mean": 0.5, "ate_true": 1.0},
                    "policy_os_tmle_cf": {"ate_rmse": 0.2, "ci_coverage": 0.8, "ci_width_mean": 0.5, "ate_true": 1.0},
                    "policy_os_aipw_cf": {"ate_rmse": 0.3, "ci_coverage": 0.8, "ci_width_mean": 0.5, "ate_true": 1.0},
                    "policy_os_causal_forest": {"ate_rmse": 0.4, "ci_coverage": 1.0, "ci_width_mean": 0.5, "pehe_mean": 0.7, "ate_true": 1.0},
                },
            }
        ],
        "aggregate_metrics": {},
        "standardized_metrics": {},
    }

    updated = replay_suite_payload(payload)
    scorecard = updated["aggregate_metrics"]["flagship_scorecard"]
    assert scorecard["flagship_method"] == "policy_os_xlearner_cf"
    assert scorecard["flagship_presence"]["present"] is True
    assert updated["blockers"] == []


def test_claim_gate_full_stack_fails_without_new_policy_suites(tmp_path: Path):
    frontier_specs = suites_for_claim_profile("frontier_frontier_claim", profile="air-m2")
    for spec in frontier_specs:
        payload = {
            "suite_id": spec.suite_id,
            "n_total": 1,
            "n_passed": 1,
            "aggregate_metrics": {},
            "proof_class": spec.proof_class,
            "claim_profile_targets": list(spec.claim_profiles),
        }
        if spec.suite_id == "adversarial_symbolic_stress":
            payload["aggregate_metrics"]["accuracy"] = {"false_positive_rate": 0.0}
            payload["benchmark_family"] = "adversarial_symbolic"
            payload["baseline_snapshot_ref"] = "adversarial-v1"
        elif spec.suite_id.startswith("capability_"):
            payload["workflow_levels"] = list(WORKFLOW_LEVELS)
            payload["competitor_gap"] = {"y0": {level: {"status": "unsupported"} for level in WORKFLOW_LEVELS}}
            payload["evidence_bundle_complete"] = True
            payload["public_claim_eligible"] = True
            payload["literature_anchor"] = "synthetic capability anchor"
        (tmp_path / f"{spec.suite_id}.json").write_text(json.dumps(payload), encoding="utf-8")

    result = evaluate_claim_gate(tmp_path, profile="air-m2", claim_profile="full_stack_publication_claim")
    assert result["claim_ready"] is False
    assert any(item["status"] == "missing_report" for item in result["findings"])
