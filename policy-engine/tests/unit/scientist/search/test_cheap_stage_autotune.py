from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune import (
    ChampionRegistry,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.cheap_stage import (
    CheapStageBenchmarkEvaluator,
    CheapStageRuntimeLoader,
    CheapStageTuningConfig,
    _spearman,
    default_cheap_stage_policy,
    resolve_cheap_stage_threshold,
    write_correlation_dataset,
)


def _records(
    total: int,
    *,
    good_score: float = 0.1,
    bad_score: float = 0.9,
    good_share: float = 0.2,
):
    rows = []
    cadence = max(1, int(round(1.0 / max(good_share, 0.01))))
    for idx in range(total):
        approved = (idx % cadence) == 0
        rows.append(
            {
                "candidate_hash": f"cand-{idx}",
                "stage_a_score": good_score if approved else bad_score,
                "stage_b_score": 0.2 if approved else 0.8,
                "stage_a_passed": False,
                "stage_b_approved": approved,
            }
        )
    return rows


def test_cheap_stage_falls_back_to_seeded_threshold_without_champion(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    loader = CheapStageRuntimeLoader(store=store, registry=registry)

    assert resolve_cheap_stage_threshold(None, loader=loader) == 0.5


def test_cheap_stage_no_promotion_when_sample_is_too_small(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(
        store,
        write_correlation_dataset(_records(50), output_dir=tmp_path / "small"),
    )
    candidate_ref = persist_mutation_artifact(store, CheapStageTuningConfig(threshold=0.4))
    evaluator = CheapStageBenchmarkEvaluator(store=store, registry=registry)

    evaluation = evaluator.evaluate(
        candidate_ref,
        suite_ref,
        {"store": store, "registry": registry},
    )
    evaluation_ref = persist_benchmark_evaluation(store, evaluation)
    decision = registry.consider_promotion(
        "cheap_stage",
        candidate_ref,
        evaluation_ref,
        default_cheap_stage_policy(),
    )

    assert evaluation.guardrails["sample_count_sufficient"] is False
    assert decision.promoted is False


def test_cheap_stage_promotes_only_when_tpr_and_eval_rate_constraints_hold(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    dataset = write_correlation_dataset(_records(250), output_dir=tmp_path / "large")
    suite_ref = persist_benchmark_suite(store, dataset)
    evaluator = CheapStageBenchmarkEvaluator(store=store, registry=registry)

    bad_candidate_ref = persist_mutation_artifact(store, CheapStageTuningConfig(threshold=1.0))
    bad_eval = evaluator.evaluate(
        bad_candidate_ref,
        suite_ref,
        {"store": store, "registry": registry},
    )
    bad_eval_ref = persist_benchmark_evaluation(store, bad_eval)
    bad_decision = registry.consider_promotion(
        "cheap_stage",
        bad_candidate_ref,
        bad_eval_ref,
        default_cheap_stage_policy(),
    )

    good_candidate_ref = persist_mutation_artifact(store, CheapStageTuningConfig(threshold=0.4))
    good_eval = evaluator.evaluate(
        good_candidate_ref,
        suite_ref,
        {"store": store, "registry": registry},
    )
    good_eval_ref = persist_benchmark_evaluation(store, good_eval)
    good_decision = registry.consider_promotion(
        "cheap_stage",
        good_candidate_ref,
        good_eval_ref,
        default_cheap_stage_policy(),
    )

    assert bad_eval.guardrails["true_positive_rate_floor"] is False
    assert bad_decision.promoted is False
    assert good_eval.guardrails["true_positive_rate_floor"] is True
    assert good_eval.guardrails["stage_b_eval_rate_delta_ok"] is True
    assert good_decision.promoted is True


def test_spearman_uses_average_ranks_for_ties() -> None:
    assert _spearman([1.0, 1.0, 2.0], [1.0, 2.0, 3.0]) == 0.8660254037844387
