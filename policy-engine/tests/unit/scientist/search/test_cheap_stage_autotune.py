from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune import (
    BenchmarkEvaluation,
    BenchmarkSplit,
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
from polisyos.scientist.methods.autotune.models import load_model_artifact


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
        return_selected_profile=True,
    )
    candidate_ref = persist_mutation_artifact(
        store,
        CheapStageTuningConfig(threshold=0.4),
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    evaluator = CheapStageBenchmarkEvaluator(store=store, registry=registry)

    evaluation = evaluator.evaluate(
        candidate_ref,
        suite_ref,
        {"store": store, "registry": registry},
    )
    evaluation_ref = persist_benchmark_evaluation(
        store,
        evaluation,
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    decision = registry.consider_promotion(
        "cheap_stage",
        candidate_ref,
        evaluation_ref,
        default_cheap_stage_policy(),
        suite_ref=suite_ref,
    )

    assert evaluation.guardrails["sample_count_sufficient"] is False
    assert decision.promoted is False
    assert decision.reason == "guardrail_failed:sample_count_sufficient"


def test_cheap_stage_promotes_only_when_tpr_and_eval_rate_constraints_hold(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    dataset = write_correlation_dataset(_records(250), output_dir=tmp_path / "large")
    suite_ref = persist_benchmark_suite(store, dataset, return_selected_profile=True)
    evaluator = CheapStageBenchmarkEvaluator(store=store, registry=registry)

    bad_candidate_ref = persist_mutation_artifact(
        store,
        CheapStageTuningConfig(threshold=1.0),
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    bad_eval = evaluator.evaluate(
        bad_candidate_ref,
        suite_ref,
        {"store": store, "registry": registry},
    )
    bad_eval_ref = persist_benchmark_evaluation(
        store,
        bad_eval,
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    bad_decision = registry.consider_promotion(
        "cheap_stage",
        bad_candidate_ref,
        bad_eval_ref,
        default_cheap_stage_policy(),
        suite_ref=suite_ref,
    )

    good_candidate_ref = persist_mutation_artifact(
        store,
        CheapStageTuningConfig(threshold=0.4),
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    good_eval = evaluator.evaluate(
        good_candidate_ref,
        suite_ref,
        {"store": store, "registry": registry},
    )
    good_eval_ref = persist_benchmark_evaluation(
        store,
        good_eval,
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    missing_split_ref = persist_benchmark_evaluation(
        store,
        good_eval.model_copy(update={"runtime_split_type": None}),
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    assert store.get_manifest(missing_split_ref).inputs == store.get_manifest(good_eval_ref).inputs
    missing_split_decision = registry.consider_promotion(
        "cheap_stage",
        good_candidate_ref,
        missing_split_ref,
        default_cheap_stage_policy(),
        suite_ref=suite_ref,
    )
    assert missing_split_decision.promoted is False
    assert missing_split_decision.reason == "runtime_split_mismatch"
    assert registry.get("cheap_stage") is None
    good_decision = registry.consider_promotion(
        "cheap_stage",
        good_candidate_ref,
        good_eval_ref,
        default_cheap_stage_policy(),
        suite_ref=suite_ref,
    )

    assert bad_eval.guardrails["true_positive_rate_floor"] is False
    assert bad_decision.promoted is False
    assert bad_decision.reason == "guardrail_failed:true_positive_rate_floor"
    assert good_eval.guardrails["true_positive_rate_floor"] is True
    assert good_eval.guardrails["stage_b_eval_rate_delta_ok"] is True
    assert good_decision.promoted is True
    assert good_eval.runtime_split_type is BenchmarkSplit.HOLDOUT
    champion = registry.get("cheap_stage")
    assert champion is not None
    assert champion.candidate_ref == good_candidate_ref
    assert champion.evaluation_ref == good_eval_ref
    assert load_model_artifact(store, champion.evaluation_ref, BenchmarkEvaluation) == good_eval
    assert {edge.role: edge for edge in store.get_manifest(champion.evaluation_ref).inputs} == {
        "candidate": input_ref_from_artifact_ref(good_candidate_ref, role="candidate"),
        "benchmark_suite": input_ref_from_artifact_ref(suite_ref, role="benchmark_suite"),
    }
    assert CheapStageRuntimeLoader(store=store, registry=registry).load().threshold == 0.4


@pytest.mark.parametrize(
    ("binding", "reason"),
    [
        ("suite_ref_missing", "suite_ref_required"),
        ("candidate_unbound", "suite_basis_mismatch"),
        ("evaluation_unbound", "suite_basis_mismatch"),
        ("foreign_suite", "suite_basis_mismatch"),
    ],
)
def test_cheap_stage_promotion_requires_the_actual_suite_binding(tmp_path, binding, reason) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    suite = write_correlation_dataset(_records(250), output_dir=tmp_path / "dataset")
    suite_ref = persist_benchmark_suite(store, suite, return_selected_profile=True)
    suite_input = input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")
    candidate_ref = persist_mutation_artifact(
        store,
        CheapStageTuningConfig(threshold=0.4),
        inputs=[] if binding == "candidate_unbound" else [suite_input],
        return_selected_profile=True,
    )
    evaluation = CheapStageBenchmarkEvaluator(store=store, registry=registry).evaluate(
        candidate_ref, suite_ref, {}
    )
    assert evaluation.promotable is True
    assert evaluation.runtime_split_type is BenchmarkSplit.HOLDOUT
    evaluation_ref = persist_benchmark_evaluation(
        store,
        evaluation,
        inputs=[] if binding == "evaluation_unbound" else [suite_input],
        return_selected_profile=True,
    )
    admitted_suite_ref = suite_ref
    if binding == "suite_ref_missing":
        admitted_suite_ref = None
    elif binding == "foreign_suite":
        admitted_suite_ref = persist_benchmark_suite(
            store,
            suite.model_copy(update={"metadata": {"basis": "foreign"}}),
            return_selected_profile=True,
        )
    decision = registry.consider_promotion(
        "cheap_stage",
        candidate_ref,
        evaluation_ref,
        default_cheap_stage_policy(),
        suite_ref=admitted_suite_ref,
    )
    assert decision.promoted is False
    assert decision.reason == reason
    assert registry.get("cheap_stage") is None


@pytest.mark.parametrize(
    ("corruption", "reason"),
    [
        ("suite_id", "benchmark_split_suite_id_mismatch"),
        ("suite_version", "benchmark_split_suite_version_mismatch"),
        ("duplicate_assignment", "benchmark_split_duplicate_assignment"),
        ("absent_row", "benchmark_split_dataset_ids_mismatch"),
        ("unassigned_row", "benchmark_split_dataset_ids_mismatch"),
        ("duplicate_row", "benchmark_split_duplicate_row_id"),
        ("missing_id_field", "benchmark_split_row_id_missing"),
        ("invalid_id_field", "benchmark_split_row_id_invalid"),
    ],
)
def test_cheap_stage_rejects_foreign_or_incomplete_row_partitions(
    tmp_path, corruption, reason
) -> None:
    suite = write_correlation_dataset(_records(250), output_dir=tmp_path / "dataset")
    split_path = Path(suite.split_manifest_path)
    dataset_path = Path(suite.dataset_path)
    split = json.loads(split_path.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines()]
    if corruption == "suite_id":
        split["suite_id"] = "foreign_suite"
    elif corruption == "suite_version":
        split["suite_version"] = "2.0"
    elif corruption == "duplicate_assignment":
        split["holdout_ids"].append(split["holdout_ids"][0])
    elif corruption == "absent_row":
        split["holdout_ids"].append("absent")
    elif corruption == "unassigned_row":
        rows.append({**rows[0], "candidate_hash": "unassigned"})
    elif corruption == "duplicate_row":
        rows.append(dict(rows[0]))
    elif corruption == "missing_id_field":
        del rows[0]["candidate_hash"]
    else:
        rows[0]["candidate_hash"] = 1
    split_path.write_text(json.dumps(split), encoding="utf-8")
    dataset_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    store = FileSystemCAS(tmp_path / ".polisyos")
    suite_ref = persist_benchmark_suite(store, suite, return_selected_profile=True)
    candidate_ref = persist_mutation_artifact(store, CheapStageTuningConfig(threshold=0.4))
    with pytest.raises(ValueError, match=reason):
        CheapStageBenchmarkEvaluator(store=store).evaluate(candidate_ref, suite_ref, {})


@pytest.mark.parametrize("with_holdout", [True, False])
def test_cheap_stage_split_follows_declared_row_ids_and_materialized_holdout(
    tmp_path, with_holdout
) -> None:
    suite = write_correlation_dataset(_records(250), output_dir=tmp_path / "dataset")
    split_path = Path(suite.split_manifest_path)
    split = json.loads(split_path.read_text(encoding="utf-8"))
    split["id_field"] = "observed_candidate"
    if not with_holdout:
        split["selection_ids"] += split["holdout_ids"]
        split["holdout_ids"] = []
    split_path.write_text(json.dumps(split), encoding="utf-8")
    dataset_path = Path(suite.dataset_path)
    rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        row["observed_candidate"] = row.pop("candidate_hash")
    dataset_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    suite_ref = persist_benchmark_suite(store, suite, return_selected_profile=True)
    suite_input = input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")
    candidate_ref = persist_mutation_artifact(
        store,
        CheapStageTuningConfig(threshold=0.4),
        inputs=[suite_input],
        return_selected_profile=True,
    )
    evaluation = CheapStageBenchmarkEvaluator(store=store, registry=registry).evaluate(
        candidate_ref, suite_ref, {}
    )
    evaluation_ref = persist_benchmark_evaluation(
        store, evaluation, inputs=[suite_input], return_selected_profile=True
    )
    decision = registry.consider_promotion(
        "cheap_stage",
        candidate_ref,
        evaluation_ref,
        default_cheap_stage_policy(),
        suite_ref=suite_ref,
    )
    assert evaluation.sample_counts["holdout"] == (50 if with_holdout else 0)
    assert evaluation.runtime_split_type is (
        BenchmarkSplit.HOLDOUT if with_holdout else BenchmarkSplit.SELECTION
    )
    assert decision.promoted is with_holdout
    if not with_holdout:
        assert decision.reason == "runtime_split_mismatch"
        assert registry.get("cheap_stage") is None


def test_spearman_uses_average_ranks_for_ties() -> None:
    assert _spearman([1.0, 1.0, 2.0], [1.0, 2.0, 3.0]) == 0.8660254037844387
