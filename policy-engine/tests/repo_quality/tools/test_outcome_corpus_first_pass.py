from __future__ import annotations

# ruff: noqa: S101
from pathlib import Path

from polisyos.corpus import load_universal_corpus_fixtures
from tools.quality.validation import check_compilation_truthfulness as truthfulness
from tools.quality.validation import check_critic_ensemble_diversity as critic_diversity
from tools.quality.validation import check_domain_coverage_breadth as domain_breadth

REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS_ROOT = REPO_ROOT / "tests" / "fixtures" / "universal-corpus"


def test_i11_outcome_corpus_first_pass_exercises_truthfulness_breadth_and_diversity() -> None:
    fixtures = load_universal_corpus_fixtures(CORPUS_ROOT)
    assert len(fixtures) >= 12
    assert len({fixture.domain for fixture in fixtures}) >= 6

    truthfulness_report = truthfulness.build_compilation_truthfulness_report(
        repo_root=REPO_ROOT,
        corpus_path=CORPUS_ROOT,
    )
    truthfulness_validation = truthfulness.validate_compilation_truthfulness_report(
        truthfulness_report
    )
    assert truthfulness_validation["status"] == "pass", truthfulness_validation["issues"]

    compiled_cases = [
        case
        for case in truthfulness_report["cases"]
        if case["compilation_status"] == "pass"
        and case["producer_pipeline_status"] == "pass"
        and case["status"] != "blocked"
    ]
    assert len(compiled_cases) >= 3
    for case in compiled_cases[:3]:
        assert {
            "true_positive_obligations",
            "missed_obligations",
            "hallucinated_obligations",
            "scope_drift_obligations",
            "authority_drift_obligations",
        } <= set(case)
        assert isinstance(case["per_case_truthfulness_score"], int | float)

    breadth_report = domain_breadth.build_domain_coverage_breadth_report(
        repo_root=REPO_ROOT,
        corpus_path=CORPUS_ROOT,
        min_candidates_per_family_layer=1,
        min_family_layers=2,
    )
    breadth_validation = domain_breadth.validate_domain_coverage_breadth_report(
        breadth_report
    )
    assert breadth_validation["status"] == "pass", breadth_validation["issues"]
    assert breadth_report["summary"]["domain_coverage_breadth"] >= 3
    assert sum(1 for case in breadth_report["cases"] if case["non_trivial_graph"]) >= 3

    critic_report = critic_diversity.build_critic_ensemble_diversity_report(
        repo_root=REPO_ROOT,
        input_path=CORPUS_ROOT,
        diversity_floor=0.25,
    )
    critic_validation = critic_diversity.validate_critic_ensemble_diversity_report(
        critic_report
    )
    assert critic_validation["status"] == "pass", critic_validation["issues"]
    measured_critic_cases = [
        case
        for case in critic_report["cases"]
        if case["critic_count"] == 8 and case["unique_failure_mode_count"] > 0
    ]
    assert len(measured_critic_cases) >= 3
