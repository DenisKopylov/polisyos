from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("jax")

from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.calibration.report import (
    CalibrationFitMetrics,
    CalibrationFitQuality,
    CalibrationReport,
)
from polisyos.ir.analytics.calibration import (
    CalibrationConfig,
    CalibrationTarget,
    ConstraintLossConfig,
    GradNormConfig,
    MultiStartConfig,
    PriorLossConfig,
    TrainableParamRef,
)
from polisyos.scientist.methods.autotune import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSplitManifest,
    BenchmarkSuite,
    ChampionRegistry,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.calibration import (
    CalibrationMetaEvaluator,
    CalibrationMetaRuntimeLoader,
    CalibrationMetaSearchConfig,
    default_calibration_policy,
)
from polisyos.scientist.methods.autotune.models import load_model_artifact


def test_apply_to_config_uses_branch_local_nested_model_clones() -> None:
    base_config = CalibrationConfig(
        learning_rate=0.01,
        grad_norm=GradNormConfig(enabled=False, alpha=1.0, lr=0.1),
        constraint_loss=ConstraintLossConfig(enabled=True, weight=1.0),
        prior_loss=PriorLossConfig(enabled=True, weight=2.0),
        targets=[
            CalibrationTarget(
                target_id="outcome",
                model_metric_path="metrics.outcome",
                fabric_query={"dataset": {"metric": ["y"]}},
                trainables=[
                    TrainableParamRef(
                        param_id="target_param",
                        selector={"node_ids": ["n1"]},
                    )
                ],
            )
        ],
        trainables=[
            TrainableParamRef(
                param_id="global_param",
                selector={"slot_ids": ["s1"]},
            )
        ],
        time_axis=[1.0, 2.0],
        multi_start=MultiStartConfig(n_starts=3, perturbation_scale=0.2),
        constraint_values={"budget": 1.0},
        literature_priors={"global_param": {"prior_mean": 0.5, "studies": [1, 2]}},
    )
    overrides = CalibrationMetaSearchConfig(
        learning_rate=0.2,
        grad_norm_enabled=True,
        grad_norm_alpha=3.0,
        constraint_loss_weight=4.0,
        prior_loss_weight=5.0,
    )

    updated = overrides.apply_to_config(base_config)
    updated.grad_norm.alpha = 9.0
    updated.constraint_loss.weight = 8.0
    updated.prior_loss.weight = 7.0
    updated.targets[0].fabric_query["dataset"]["metric"][0] = "z"
    updated.targets[0].trainables[0].selector["node_ids"][0] = "n2"
    updated.trainables[0].selector["slot_ids"][0] = "s2"
    updated.time_axis[0] = 99.0
    updated.constraint_values["budget"] = 2.0
    updated.literature_priors["global_param"]["studies"][0] = 3

    assert base_config.learning_rate == 0.01
    assert base_config.grad_norm.enabled is False
    assert base_config.grad_norm.alpha == 1.0
    assert base_config.constraint_loss.weight == 1.0
    assert base_config.prior_loss.weight == 2.0
    assert base_config.targets[0].fabric_query == {"dataset": {"metric": ["y"]}}
    assert base_config.targets[0].trainables[0].selector == {"node_ids": ["n1"]}
    assert base_config.trainables[0].selector == {"slot_ids": ["s1"]}
    assert base_config.time_axis == [1.0, 2.0]
    assert base_config.constraint_values == {"budget": 1.0}
    assert base_config.literature_priors == {"global_param": {"prior_mean": 0.5, "studies": [1, 2]}}


def _calibration_suite(tmp_path):
    dataset_path = tmp_path / "calibration_cases.jsonl"
    split_path = tmp_path / "split_manifest.json"
    with open(dataset_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"case_id": "sel"}) + "\n")
        fh.write(json.dumps({"case_id": "hold"}) + "\n")
    split_path.write_text(
        BenchmarkSplitManifest(
            suite_id="calibration_suite",
            suite_version="1.0",
            id_field="case_id",
            selection_ids=["sel"],
            holdout_ids=["hold"],
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    return BenchmarkSuite(
        suite_id="calibration_suite",
        suite_version="1.0",
        kind="calibration_meta",
        dataset_path=str(dataset_path),
        split_manifest_path=str(split_path),
    )


def _report(
    *, rmse: float, runtime_seconds: float, diagnostics: list[str] | None = None
) -> CalibrationReport:
    return CalibrationReport(
        calibrated_params={"node.param": 1.0},
        total_loss=rmse,
        fit_quality=CalibrationFitQuality(
            aggregate=CalibrationFitMetrics(
                mse=rmse**2,
                rmse=rmse,
                mae=rmse,
                r2=0.9,
                n=5,
            )
        ),
        diagnostics=list(diagnostics or []),
        execution_context={"runtime_seconds": runtime_seconds},
    )


def test_calibration_meta_promotion_uses_fit_quality_and_blocks_divergence(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / ".polisyos" / "search_registry", store=store)
    suite_ref = persist_benchmark_suite(
        store, _calibration_suite(tmp_path), return_selected_profile=True
    )
    evaluator = CalibrationMetaEvaluator(store=store, registry=registry)

    good_candidate_ref = persist_mutation_artifact(
        store,
        CalibrationMetaSearchConfig(learning_rate=0.01),
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )

    def good_runner(row, config, context):
        del row, context
        return _report(
            rmse=0.1 if config.learning_rate == 0.01 else 0.6,
            runtime_seconds=2.0,
        )

    good_eval = evaluator.evaluate(
        good_candidate_ref,
        suite_ref,
        {"store": store, "registry": registry, "calibration_runner": good_runner},
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
        "calibration_meta",
        good_candidate_ref,
        missing_split_ref,
        default_calibration_policy(),
        suite_ref=suite_ref,
    )
    assert missing_split_decision.promoted is False
    assert missing_split_decision.reason == "runtime_split_mismatch"
    assert registry.get("calibration_meta") is None
    good_decision = registry.consider_promotion(
        "calibration_meta",
        good_candidate_ref,
        good_eval_ref,
        default_calibration_policy(),
        suite_ref=suite_ref,
    )

    bad_candidate_ref = persist_mutation_artifact(
        store,
        CalibrationMetaSearchConfig(learning_rate=0.5),
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )

    def bad_runner(row, config, context):
        del row, context, config
        return _report(
            rmse=0.05, runtime_seconds=1.0, diagnostics=["Non-finite gradients at step 3"]
        )

    bad_eval = evaluator.evaluate(
        bad_candidate_ref,
        suite_ref,
        {"store": store, "registry": registry, "calibration_runner": bad_runner},
    )
    bad_eval_ref = persist_benchmark_evaluation(
        store,
        bad_eval,
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
        return_selected_profile=True,
    )
    bad_decision = registry.consider_promotion(
        "calibration_meta",
        bad_candidate_ref,
        bad_eval_ref,
        default_calibration_policy(),
        suite_ref=suite_ref,
    )

    assert good_decision.promoted is True
    assert good_eval.runtime_split_type is BenchmarkSplit.HOLDOUT
    assert bad_eval.guardrails["no_divergence"] is False
    assert bad_decision.promoted is False
    assert bad_decision.reason == "guardrail_failed:no_divergence"
    champion = registry.get("calibration_meta")
    assert champion is not None
    assert champion.candidate_ref == good_candidate_ref
    assert champion.evaluation_ref == good_eval_ref
    assert load_model_artifact(store, champion.evaluation_ref, BenchmarkEvaluation) == good_eval
    assert {edge.role: edge for edge in store.get_manifest(champion.evaluation_ref).inputs} == {
        "candidate": input_ref_from_artifact_ref(good_candidate_ref, role="candidate"),
        "benchmark_suite": input_ref_from_artifact_ref(suite_ref, role="benchmark_suite"),
    }
    assert CalibrationMetaRuntimeLoader(store=store, registry=registry).load().learning_rate == 0.01


@pytest.mark.parametrize(
    ("binding", "reason"),
    [
        ("suite_ref_missing", "suite_ref_required"),
        ("candidate_unbound", "suite_basis_mismatch"),
        ("evaluation_unbound", "suite_basis_mismatch"),
        ("foreign_suite", "suite_basis_mismatch"),
    ],
)
def test_calibration_promotion_requires_the_actual_suite_binding(tmp_path, binding, reason) -> None:
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    suite = _calibration_suite(tmp_path)
    suite_ref = persist_benchmark_suite(store, suite, return_selected_profile=True)
    suite_input = input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")
    candidate_ref = persist_mutation_artifact(
        store,
        CalibrationMetaSearchConfig(learning_rate=0.01),
        inputs=[] if binding == "candidate_unbound" else [suite_input],
        return_selected_profile=True,
    )
    evaluation = CalibrationMetaEvaluator(store=store, registry=registry).evaluate(
        candidate_ref,
        suite_ref,
        {"calibration_runner": lambda *_args: _report(rmse=0.1, runtime_seconds=2.0)},
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
        "calibration_meta",
        candidate_ref,
        evaluation_ref,
        default_calibration_policy(),
        suite_ref=admitted_suite_ref,
    )
    assert decision.promoted is False
    assert decision.reason == reason
    assert registry.get("calibration_meta") is None


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
def test_calibration_rejects_foreign_or_incomplete_row_partitions(
    tmp_path, corruption, reason
) -> None:
    suite = _calibration_suite(tmp_path)
    split_path = Path(suite.split_manifest_path)
    dataset_path = Path(suite.dataset_path)
    split = json.loads(split_path.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines()]
    if corruption == "suite_id":
        split["suite_id"] = "foreign_suite"
    elif corruption == "suite_version":
        split["suite_version"] = "2.0"
    elif corruption == "duplicate_assignment":
        split["holdout_ids"].append("hold")
    elif corruption == "absent_row":
        split["holdout_ids"].append("absent")
    elif corruption == "unassigned_row":
        rows.append({"case_id": "unassigned"})
    elif corruption == "duplicate_row":
        rows.append(dict(rows[0]))
    elif corruption == "missing_id_field":
        rows[0] = {"other_id": "sel"}
    else:
        rows[0]["case_id"] = 1
    split_path.write_text(json.dumps(split), encoding="utf-8")
    dataset_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    store = FileSystemCAS(tmp_path / ".polisyos")
    suite_ref = persist_benchmark_suite(store, suite, return_selected_profile=True)
    candidate_ref = persist_mutation_artifact(store, CalibrationMetaSearchConfig())
    calls = []

    def runner(row, _config, _context):
        calls.append(row)
        return _report(rmse=0.1, runtime_seconds=2.0)

    with pytest.raises(ValueError, match=reason):
        CalibrationMetaEvaluator(store=store).evaluate(
            candidate_ref, suite_ref, {"calibration_runner": runner}
        )
    assert calls == []


@pytest.mark.parametrize("with_holdout", [True, False])
def test_calibration_split_follows_declared_row_ids_and_materialized_holdout(
    tmp_path, with_holdout
) -> None:
    suite = _calibration_suite(tmp_path)
    split_path = Path(suite.split_manifest_path)
    split = json.loads(split_path.read_text(encoding="utf-8"))
    split["id_field"] = "sample_key"
    if not with_holdout:
        split["selection_ids"] += split["holdout_ids"]
        split["holdout_ids"] = []
    split_path.write_text(json.dumps(split), encoding="utf-8")
    Path(suite.dataset_path).write_text(
        '{"sample_key": "sel"}\n{"sample_key": "hold"}\n', encoding="utf-8"
    )
    store = FileSystemCAS(tmp_path / ".polisyos")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    suite_ref = persist_benchmark_suite(store, suite, return_selected_profile=True)
    suite_input = input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")
    candidate_ref = persist_mutation_artifact(
        store,
        CalibrationMetaSearchConfig(learning_rate=0.01),
        inputs=[suite_input],
        return_selected_profile=True,
    )
    evaluation = CalibrationMetaEvaluator(store=store, registry=registry).evaluate(
        candidate_ref,
        suite_ref,
        {"calibration_runner": lambda *_args: _report(rmse=0.1, runtime_seconds=2.0)},
    )
    evaluation_ref = persist_benchmark_evaluation(
        store, evaluation, inputs=[suite_input], return_selected_profile=True
    )
    decision = registry.consider_promotion(
        "calibration_meta",
        candidate_ref,
        evaluation_ref,
        default_calibration_policy(),
        suite_ref=suite_ref,
    )
    assert evaluation.sample_counts["holdout"] == (1 if with_holdout else 0)
    assert evaluation.runtime_split_type is (
        BenchmarkSplit.HOLDOUT if with_holdout else BenchmarkSplit.SELECTION
    )
    assert decision.promoted is with_holdout
    if not with_holdout:
        assert decision.reason == "runtime_split_mismatch"
        assert registry.get("calibration_meta") is None


def test_unselected_new_batch_report_is_explicitly_limited_without_scoring(tmp_path) -> None:
    from polisyos.foundry.calibration.report import CalibrationOrderedBatchReport

    store = FileSystemCAS(tmp_path / "unselected_batch")
    suite_ref = persist_benchmark_suite(store, _calibration_suite(tmp_path))
    candidate_ref = persist_mutation_artifact(store, CalibrationMetaSearchConfig())
    payload = _report(rmse=0.0, runtime_seconds=0.0).model_dump(mode="python")
    payload.update(
        schema_version="2.1",
        ordered_batch_execution=CalibrationOrderedBatchReport(
            consumed_profile_sha256="0" * 64,
            input_status="in_memory_input_only",
        ),
    )
    report = CalibrationReport.model_validate(payload)
    result = CalibrationMetaEvaluator(store=store).evaluate(
        candidate_ref,
        suite_ref,
        {
            "calibration_runner": lambda *_args: report,
        },
    )
    assert result.status == "limited"
    assert result.promotable is False
    assert result.guardrails["calibration_metric_sources_ready"] is False
    assert "aggregate_fit_quality" not in result.holdout_metrics
    assert result.sample_counts == {"selection": 0, "holdout": 0}
    assert "ordered_autotune_metrics_require_selected_report_and_store" in result.notes
    ref = persist_benchmark_evaluation(store, result)
    from polisyos.core.canon import from_canonical_bytes

    persisted = from_canonical_bytes(FileSystemCAS(tmp_path / "unselected_batch").get_bytes(ref))
    assert (
        persisted["metadata"]["calibration_metric_sources"]["holdout"][0]["metric_source_status"]
        == "not_established"
    )
