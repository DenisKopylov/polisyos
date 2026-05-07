from __future__ import annotations

import json

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.calibration.report import (
    CalibrationFitMetrics,
    CalibrationFitQuality,
    CalibrationReport,
)
from polisyos.ir.analytics.calibration import (
    CalibrationConfig,
    CalibrationTarget,
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
    apply_calibration_meta_overrides,
    default_calibration_policy,
)


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


def test_calibration_meta_overrides_do_not_change_trainables_or_targets() -> None:
    base = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="gdp",
                model_metric_path="state.gdp",
                fabric_query={"dataset": "x"},
            )
        ],
        trainables=[TrainableParamRef(param_id="beta", node_id="n1")],
    )

    updated = apply_calibration_meta_overrides(
        base,
        loader=type(
            "_Loader",
            (),
            {
                "load": lambda self, context=None: CalibrationMetaSearchConfig(
                    learning_rate=0.005,
                    early_stop_patience=5,
                )
            },
        )(),
    )

    assert updated.learning_rate == 0.005
    assert updated.early_stop_patience == 5
    assert updated.targets == base.targets
    assert updated.trainables == base.trainables


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
