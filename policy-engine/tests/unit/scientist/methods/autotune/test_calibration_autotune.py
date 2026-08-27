from __future__ import annotations

import json

import pytest

pytest.importorskip("jax")

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
    BenchmarkSplitManifest,
    BenchmarkSuite,
    ChampionRegistry,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.calibration import (
    CalibrationMetaEvaluator,
    CalibrationMetaSearchConfig,
    default_calibration_policy,
)


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
    suite_ref = persist_benchmark_suite(store, _calibration_suite(tmp_path))
    evaluator = CalibrationMetaEvaluator(store=store, registry=registry)

    good_candidate_ref = persist_mutation_artifact(
        store, CalibrationMetaSearchConfig(learning_rate=0.01)
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
    good_eval_ref = persist_benchmark_evaluation(store, good_eval)
    good_decision = registry.consider_promotion(
        "calibration_meta",
        good_candidate_ref,
        good_eval_ref,
        default_calibration_policy(),
    )

    bad_candidate_ref = persist_mutation_artifact(
        store, CalibrationMetaSearchConfig(learning_rate=0.5)
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
    bad_eval_ref = persist_benchmark_evaluation(store, bad_eval)
    bad_decision = registry.consider_promotion(
        "calibration_meta",
        bad_candidate_ref,
        bad_eval_ref,
        default_calibration_policy(),
    )

    assert good_decision.promoted is True
    assert bad_eval.guardrails["no_divergence"] is False
    assert bad_decision.promoted is False
