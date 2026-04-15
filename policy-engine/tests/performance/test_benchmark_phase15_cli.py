from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BENCH_REPORT_DIR = REPO_ROOT / "benchmarks" / "_reports"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _env() -> dict[str, str]:
    env = os.environ.copy()
    pythonpath = f"{REPO_ROOT / 'src'}:{REPO_ROOT}"
    if env.get("PYTHONPATH"):
        pythonpath = f"{pythonpath}:{env['PYTHONPATH']}"
    env["PYTHONPATH"] = pythonpath
    env["BENCH_TEST_FAST"] = "1"
    return env


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=REPO_ROOT,
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )


def test_lbidd_cli_smoke_emits_unified_json(tmp_path: Path):
    out = tmp_path / "lbidd.json"
    result = _run(
        [
            "python3",
            "benchmarks/estimation/lbidd_benchmark.py",
            "--mode",
            "smoke",
            "--n-obs",
            "40",
            "--n-reps",
            "1",
            "--quiet",
            "--json",
            str(out),
        ]
    )
    assert out.exists(), result.stdout + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["suite_id"] == "estimation_lbidd"
    assert payload["mode"] == "smoke"
    assert payload["benchmark_tier"] == "local_evidence"
    assert payload["estimator_profile"] == "flagship_plus_production"
    assert payload["cases"]
    assert payload["preflight"]["data_source"] in {"synthetic_replica", "real_lbidd"}
    assert payload["preflight"]["dataset_family"] == "lbidd"
    assert payload["standardized_metrics"]
    assert payload["literature_anchor"]
    assert payload["method_profile"] == "production_estimation"
    assert "flagship_scorecard" in payload["aggregate_metrics"]
    assert "ranking_summary" in payload["aggregate_metrics"]


def test_lbidd_cli_acceptance_fails_fast_without_real_data():
    result = _run(
        [
            "python3",
            "benchmarks/estimation/lbidd_benchmark.py",
            "--mode",
            "acceptance",
            "--quiet",
        ]
    )
    assert result.returncode == 2
    assert "acceptance" in result.stdout.lower()
    assert "failed" in result.stdout.lower()


def test_realcause_cli_smoke_emits_unified_json(tmp_path: Path):
    out = tmp_path / "realcause.json"
    result = _run(
        [
            "python3",
            "benchmarks/estimation/realcause_benchmark.py",
            "--mode",
            "smoke",
            "--n-reps",
            "1",
            "--quiet",
            "--json",
            str(out),
        ]
    )
    assert out.exists(), result.stdout + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["suite_id"] == "estimation_realcause"
    assert payload["mode"] == "smoke"
    assert payload["benchmark_tier"] == "local_evidence"
    assert payload["estimator_profile"] == "flagship_plus_production"
    assert payload["cases"]
    assert payload["preflight"]["data_source"] in {"synthetic_replica", "real_realcause"}
    assert payload["preflight"]["dataset_family"] == "realcause"
    assert payload["standardized_metrics"]
    assert payload["literature_anchor"]
    assert payload["method_profile"] == "production_estimation"
    assert "flagship_scorecard" in payload["aggregate_metrics"]
    assert "distributional_ranking_summary" in payload["aggregate_metrics"]


def test_realcause_cli_acceptance_fails_fast_without_real_data():
    result = _run(
        [
            "python3",
            "benchmarks/estimation/realcause_benchmark.py",
            "--mode",
            "acceptance",
            "--quiet",
        ]
    )
    assert result.returncode == 2
    assert "acceptance" in result.stdout.lower()
    assert "failed" in result.stdout.lower()


def test_hte_cli_smoke_emits_unified_json(tmp_path: Path):
    out = tmp_path / "hte.json"
    result = _run(
        [
            "python3",
            "benchmarks/hte/interpretable_hte_benchmark.py",
            "--mode",
            "smoke",
            "--n-obs",
            "80",
            "--n-reps",
            "1",
            "--quiet",
            "--json",
            str(out),
        ]
    )
    assert out.exists(), result.stdout + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["suite_id"] == "hte_interpretable"
    assert payload["mode"] == "smoke"
    assert payload["benchmark_tier"] == "local_evidence"
    assert payload["estimator_profile"] == "production_hte"
    assert payload["cases"]
    assert payload["preflight"]["data_source"] == "synthetic_ground_truth"
    assert payload["preflight"]["dataset_family"] == "hte_interpretable"
    assert payload["literature_anchor"]
    assert payload["aggregate_metrics"]["acceptance_bar"]["checks"]
    assert "final_milestone_bar" in payload["aggregate_metrics"]


def test_acic_cli_smoke_emits_literature_anchor_and_production_profile(tmp_path: Path):
    out = tmp_path / "acic.json"
    result = _run(
        [
            "python3",
            "benchmarks/estimation/acic_benchmark.py",
            "--mode",
            "smoke",
            "--n-obs",
            "40",
            "--n-reps",
            "1",
            "--quiet",
            "--json",
            str(out),
        ]
    )
    assert out.exists(), result.stdout + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["suite_id"] == "estimation_acic"
    assert payload["literature_anchor"]
    assert payload["method_profile"] == "production_estimation"


def test_run_all_estimation_filter_matches_suites(tmp_path: Path):
    json_dir = tmp_path / "estimation-run"
    result = _run(
        [
            "bash",
            "benchmarks/run_all_benchmarks.sh",
            "--mode",
            "acceptance",
            "--circuit",
            "estimation",
            "--json-dir",
            str(json_dir),
            "--quiet",
        ]
    )
    assert result.returncode != 0
    summary = json.loads((json_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["filter"] == "estimation"
    assert summary["mode"] == "acceptance"
    assert summary["tier"] == "research_acceptance"
    assert summary["matched"] == 3
    assert len(summary["suite_results"]) == 3


def test_run_all_research_tier_is_reflected_in_summary(tmp_path: Path):
    json_dir = tmp_path / "research-tier"
    result = _run(
        [
            "bash",
            "benchmarks/run_all_benchmarks.sh",
            "--mode",
            "smoke",
            "--tier",
            "research_acceptance",
            "--circuit",
            "missing_mgraph",
            "--json-dir",
            str(json_dir),
            "--quiet",
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads((json_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["filter"] == "missing_mgraph"
    assert summary["tier"] == "research_acceptance"


def test_suite_registry_cli_emits_extended_contour_fields():
    result = _run(
        [
            "python3",
            "benchmarks/suite_registry.py",
            "--format",
            "json",
            "--validation-contour",
            "academic",
            "--alias",
            "proof_closure",
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert {item["suite_id"] for item in payload} == {
        "proof_closure_public",
        "proof_closure_hidden_release",
    }
    assert all(item["validation_contours"] == ["academic"] for item in payload)
    assert {item["visibility"] for item in payload} == {"public", "hidden_release"}


def test_run_all_contour_and_visibility_filters_are_reflected_in_summary(tmp_path: Path):
    json_dir = tmp_path / "academic-hidden"
    result = _run(
        [
            "bash",
            "benchmarks/run_all_benchmarks.sh",
            "--mode",
            "smoke",
            "--contour",
            "academic",
            "--visibility",
            "hidden_release",
            "--circuit",
            "proof_closure",
            "--json-dir",
            str(json_dir),
            "--quiet",
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads((json_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["validation_contour"] == "academic"
    assert summary["visibility"] == "hidden_release"
    assert summary["matched"] == 1
    assert summary["suite_results"][0]["suite_id"] == "proof_closure_hidden_release"


def test_run_all_invalid_filter_fails(tmp_path: Path):
    json_dir = tmp_path / "invalid-filter"
    result = _run(
        [
            "bash",
            "benchmarks/run_all_benchmarks.sh",
            "--mode",
            "smoke",
            "--circuit",
            "does-not-exist",
            "--json-dir",
            str(json_dir),
            "--quiet",
        ]
    )
    assert result.returncode == 2
    assert "No benchmark suites matched" in (result.stdout + result.stderr)


def test_run_all_estimation_acceptance_fails_fast(tmp_path: Path):
    json_dir = tmp_path / "acceptance-estimation"
    result = _run(
        [
            "bash",
            "benchmarks/run_all_benchmarks.sh",
            "--mode",
            "acceptance",
            "--circuit",
            "estimation",
            "--json-dir",
            str(json_dir),
            "--quiet",
        ]
    )
    assert result.returncode != 0
    assert "acceptance" in result.stdout.lower()


def test_run_all_legacy_suite_filter_resolves_to_canonical_last_suite_summary(tmp_path: Path):
    json_dir = tmp_path / "legacy-suite"
    result = _run(
        [
            "bash",
            "benchmarks/run_all_benchmarks.sh",
            "--mode",
            "smoke",
            "--circuit",
            "repro_deterministic",
            "--json-dir",
            str(json_dir),
            "--quiet",
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads((json_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["matched"] == 1
    assert summary["suite_results"][0]["suite_id"] == "reproducibility_deterministic"
    last_suite = json.loads((json_dir / "last_suite_summary.json").read_text(encoding="utf-8"))
    assert last_suite["suite_id"] == "reproducibility_deterministic"


def test_suite_registry_cli_supports_alias_and_claim_profile_filters():
    alias_result = _run(
        [
            "python3",
            "benchmarks/suite_registry.py",
            "--profile",
            "air-m2",
            "--alias",
            "stress",
            "--format",
            "json",
        ]
    )
    assert alias_result.returncode == 0, alias_result.stdout + alias_result.stderr
    alias_payload = json.loads(alias_result.stdout)
    assert {item["suite_id"] for item in alias_payload} == {
        "adversarial_symbolic_stress",
        "temporal_hidden",
    }

    claim_result = _run(
        [
            "python3",
            "benchmarks/suite_registry.py",
            "--profile",
            "air-m2",
            "--claim-profile",
            "frontier_frontier_claim",
            "--format",
            "json",
        ]
    )
    assert claim_result.returncode == 0, claim_result.stdout + claim_result.stderr
    claim_payload = json.loads(claim_result.stdout)
    suite_ids = {item["suite_id"] for item in claim_payload}
    assert "symbolic" in suite_ids
    assert "adversarial_symbolic_stress" in suite_ids
    assert "temporal_gold" in suite_ids
    assert "temporal_hidden" in suite_ids
    assert "estimation_acic" not in suite_ids


def test_temporal_gold_cli_smoke_emits_publication_payload(tmp_path: Path):
    out = tmp_path / "temporal_gold.json"
    result = _run(
        [
            "python3",
            "benchmarks/temporal/temporal_gold_benchmark.py",
            "--mode",
            "smoke",
            "--quiet",
            "--json",
            str(out),
        ]
    )
    assert out.exists(), result.stdout + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["suite_id"] == "temporal_gold"
    assert payload["benchmark_family"] == "temporal_causal_dynamics"
    assert payload["baseline_snapshot_ref"] == "temporal_gold@synthetic-v1"
    assert payload["public_claim_eligible"] is True
    assert payload["literature_anchor"]
    scorecard = payload["aggregate_metrics"]["temporal_scorecard"]
    assert scorecard["engine_route_coverage_rate"] == 1.0
    assert scorecard["bundle_presence_rate"] == 1.0
    assert scorecard["artifact_loadability_rate"] == 1.0
    assert scorecard["policy_lineage_rate"] == 1.0
    assert scorecard["diagnostics_artifact_presence_rate"] == 1.0
    assert scorecard["truthful_fallback_disclosure_rate"] == 1.0
    assert payload["regression_guard"]


def test_temporal_hidden_cli_smoke_emits_hidden_summary(tmp_path: Path):
    out = tmp_path / "temporal_hidden.json"
    result = _run(
        [
            "python3",
            "benchmarks/temporal/temporal_hidden_benchmark.py",
            "--mode",
            "smoke",
            "--quiet",
            "--json",
            str(out),
        ]
    )
    assert out.exists(), result.stdout + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["suite_id"] == "temporal_hidden"
    assert payload["benchmark_family"] == "temporal_causal_dynamics"
    assert payload["baseline_snapshot_ref"] == "temporal_hidden@synthetic-v1"
    assert payload["public_claim_eligible"] is False
    assert "hidden_temporal_summary" in payload["aggregate_metrics"]
    assert payload["aggregate_metrics"]["hidden_temporal_summary"]["artifact_reload_failure_rate"] == 0.0
    assert all(case["case_id"].startswith("temporal_hidden::case_") for case in payload["cases"])


@pytest.mark.parametrize("suite_id", ["temporal_gold", "temporal_hidden"])
def test_run_all_temporal_filters_execute_single_suite(tmp_path: Path, suite_id: str):
    json_dir = tmp_path / suite_id
    result = _run(
        [
            "bash",
            "benchmarks/run_all_benchmarks.sh",
            "--mode",
            "smoke",
            "--circuit",
            suite_id,
            "--json-dir",
            str(json_dir),
            "--quiet",
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads((json_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["matched"] == 1
    assert summary["suite_results"][0]["suite_id"] == suite_id


def test_honest_cli_supports_unified_benchmark_contract(tmp_path: Path, monkeypatch):
    from benchmarks.honest_comparison.metrics import AggregatedMetrics
    from benchmarks.honest_comparison import run_honest_benchmark as honest_cli

    raw_result = {
        "metrics": {
            "best_effort": [
                AggregatedMetrics(
                    method_name="policyos_tmle",
                    dataset_name="lalonde_n500",
                    tier="best_effort",
                    n_replications=3,
                    n_failed=0,
                    ate_bias=0.01,
                    ate_bias_se=0.0,
                    ate_rmse=0.02,
                    ate_rmse_se=0.0,
                    ci_coverage=1.0,
                    ci_coverage_se=0.0,
                    ci_width_mean=0.5,
                    pehe=None,
                    pehe_se=None,
                    wall_time_mean=0.1,
                    wall_time_p95=0.1,
                    failure_rate=0.0,
                    per_rep_ate_error=[],
                    per_rep_sq_error=[],
                )
            ]
        },
        "pairwise": {},
        "env": {"python_version": "test"},
    }

    monkeypatch.setattr(honest_cli, "run_benchmark", lambda cfg, output_path=None: raw_result)
    out = tmp_path / "honest.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_honest_benchmark.py",
            "--mode",
            "smoke",
            "--quiet",
            "--json",
            str(out),
        ],
    )

    assert honest_cli.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["suite_id"] == "honest_comparison"
    assert payload["overall_status"] == "passed"
    assert payload["cases"]
