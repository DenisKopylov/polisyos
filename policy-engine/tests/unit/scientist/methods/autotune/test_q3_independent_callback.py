"""Independent actual-calibration witness for active callback comparison basis."""

from __future__ import annotations

import json

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.calibration.report import (
    CalibrationFitMetrics,
    CalibrationFitQuality,
    CalibrationReport,
)
from polisyos.scientist.methods.autotune.calibration import (
    CalibrationMetaEvaluator,
    CalibrationMetaSearchConfig,
    default_calibration_policy,
)
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplitManifest,
    BenchmarkSuite,
    SearchLoopSpec,
    load_model_artifact,
    persist_benchmark_suite,
)
from polisyos.scientist.methods.autotune.registry import ChampionRegistry
from polisyos.scientist.methods.autotune.runtime import (
    PydanticMutationCodec,
    SearchLoopRunner,
    SequenceCandidateGenerator,
)


def _report(rmse: float) -> CalibrationReport:
    return CalibrationReport(
        calibrated_params={"node.param": 1.0},
        total_loss=rmse,
        fit_quality=CalibrationFitQuality(
            aggregate=CalibrationFitMetrics(mse=rmse**2, rmse=rmse, mae=rmse, r2=0.9, n=5)
        ),
        execution_context={"runtime_seconds": 0.0},
    )


def test_actual_calibration_callback_change_cannot_promote_weaker_candidate(tmp_path) -> None:
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text('{"case_id":"selection"}\n{"case_id":"holdout"}\n')
    split = tmp_path / "split.json"
    split.write_text(
        BenchmarkSplitManifest(
            suite_id="independent-callback",
            id_field="case_id",
            selection_ids=["selection"],
            holdout_ids=["holdout"],
        ).model_dump_json()
    )
    store = FileSystemCAS(tmp_path / "cas")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    suite = persist_benchmark_suite(
        store,
        BenchmarkSuite(
            suite_id="independent-callback",
            kind="calibration_meta",
            dataset_path=str(dataset),
            split_manifest_path=str(split),
        ),
    )
    evaluator = CalibrationMetaEvaluator(store=store, registry=registry)
    runner = SearchLoopRunner(store=store, registry=registry)

    def spec(learning_rate: float) -> SearchLoopSpec:
        return SearchLoopSpec(
            loop_id="calibration_meta",
            mutation_codec=PydanticMutationCodec(CalibrationMetaSearchConfig),
            candidate_generator=SequenceCandidateGenerator(
                [CalibrationMetaSearchConfig(learning_rate=learning_rate)]
            ),
            benchmark_evaluator=evaluator,
            promotion_policy=default_calibration_policy(),
        )

    def previous_runner(row, config, context):
        return _report(100.0)

    current_calls = []

    def active_runner(row, config, context):
        current_calls.append(config.learning_rate)
        return _report(0.1 if config.learning_rate == 0.01 else 0.5)

    first = runner.run(
        spec(0.01),
        suite_ref=suite,
        context={"calibration_runner": previous_runner},
        max_iterations=1,
    )
    assert first.iterations_completed == 1
    incumbent = registry.get("calibration_meta")
    assert incumbent is not None
    old_evaluation = load_model_artifact(store, incumbent.evaluation_ref, BenchmarkEvaluation)
    second = runner.run(
        spec(0.02), suite_ref=suite, context={"calibration_runner": active_runner}, max_iterations=1
    )
    assert second.iterations_completed == 1
    active_incumbent = evaluator.evaluate(
        incumbent.candidate_ref,
        suite,
        {"store": store, "registry": registry, "calibration_runner": active_runner},
    )
    observed = registry.get("calibration_meta")
    assert observed is not None
    observed_evaluation = load_model_artifact(store, observed.evaluation_ref, BenchmarkEvaluation)
    evidence = {
        "old_incumbent_score": old_evaluation.holdout_metrics["aggregate_fit_quality"],
        "active_incumbent_score": active_incumbent.holdout_metrics["aggregate_fit_quality"],
        "observed_champion_score": observed_evaluation.holdout_metrics["aggregate_fit_quality"],
        "class_module_basis_unchanged": (
            old_evaluation.comparison_basis == active_incumbent.comparison_basis
        ),
        "active_callback_learning_rates": current_calls,
        "incumbent_ref": incumbent.candidate_ref.model_dump(mode="json"),
        "observed_ref": observed.candidate_ref.model_dump(mode="json"),
    }
    print(json.dumps(evidence, sort_keys=True))
    # Same uncertainty and runtime inputs; RMSE/MAE .1 beats .5 under the
    # actual calibration metric. A class-module identity cannot certify the
    # context callback's old primary score as the active incumbent score.
    assert active_incumbent.holdout_metrics["aggregate_fit_quality"] > (
        0.7 / (1.0 + 0.5 + 0.5 + 0.1) + 0.3
    )
    assert observed.candidate_ref == incumbent.candidate_ref
