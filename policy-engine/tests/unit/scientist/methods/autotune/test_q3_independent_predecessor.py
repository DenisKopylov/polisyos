"""Independent real-calibration race witness for predecessor-bound guardrails."""

from __future__ import annotations

import json
from threading import Event, Thread

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.calibration.report import (
    CalibrationFitMetrics,
    CalibrationFitQuality,
    CalibrationReport,
    CalibrationUncertainty,
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


def test_real_calibration_guardrails_cannot_change_predecessor_mid_evaluation(tmp_path) -> None:
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text('{"case_id":"selection"}\n{"case_id":"holdout"}\n')
    split = tmp_path / "split.json"
    split.write_text(
        BenchmarkSplitManifest(
            suite_id="independent-predecessor",
            id_field="case_id",
            selection_ids=["selection"],
            holdout_ids=["holdout"],
        ).model_dump_json()
    )
    store = FileSystemCAS(tmp_path / "cas")
    registry_root = tmp_path / "registry"
    registry = ChampionRegistry(root=registry_root, store=store)
    suite = persist_benchmark_suite(
        store,
        BenchmarkSuite(
            suite_id="independent-predecessor",
            kind="calibration_meta",
            dataset_path=str(dataset),
            split_manifest_path=str(split),
        ),
    )
    entered = Event()
    released = Event()
    results = []
    errors = []

    def actual_runner(row, config, context):
        del context
        if config.learning_rate == 0.03 and row["case_id"] == "selection":
            entered.set()
            assert released.wait(20), "competing native writer did not release the barrier"
        rmse, condition = {
            0.01: (10.0, 10.0),
            0.02: (1.0, 1.0),
            0.03: (0.0, 10 ** (2 / 3)),
        }[config.learning_rate]
        return CalibrationReport(
            total_loss=rmse,
            fit_quality=CalibrationFitQuality(
                aggregate=CalibrationFitMetrics(mse=rmse**2, rmse=rmse, mae=rmse, r2=0.9, n=5)
            ),
            uncertainties=CalibrationUncertainty(hessian_condition=condition),
            execution_context={"runtime_seconds": 0.0},
        )

    def run(learning_rate):
        return SearchLoopRunner(store=store, registry=registry).run(
            SearchLoopSpec(
                loop_id="calibration_meta",
                mutation_codec=PydanticMutationCodec(CalibrationMetaSearchConfig),
                candidate_generator=SequenceCandidateGenerator(
                    [CalibrationMetaSearchConfig(learning_rate=learning_rate)]
                ),
                benchmark_evaluator=CalibrationMetaEvaluator(store=store, registry=registry),
                promotion_policy=default_calibration_policy(),
            ),
            suite_ref=suite,
            context={"calibration_runner": actual_runner},
            max_iterations=1,
        )

    assert run(0.01).iterations_completed == 1
    predecessor = registry.get("calibration_meta")
    assert predecessor is not None

    def evaluate_challenger():
        try:
            results.append(run(0.03))
        except BaseException as error:
            errors.append(error)

    worker = Thread(target=evaluate_challenger)
    worker.start()
    try:
        assert entered.wait(20), "actual challenger did not reach the case barrier"
        assert run(0.02).iterations_completed == 1
        competing = registry.get("calibration_meta")
        assert competing is not None
        assert competing.candidate_ref != predecessor.candidate_ref
    finally:
        released.set()
        worker.join(20)
    assert not worker.is_alive()
    assert not errors
    assert len(results) == 1
    assert results[0].iterations_completed == 1
    stage_b = results[0].history[0].stage_b_result
    assert stage_b is not None
    challenger = load_model_artifact(
        store, stage_b["simulation_results"]["evaluation_ref"], BenchmarkEvaluation
    )
    competing_evaluation = load_model_artifact(store, competing.evaluation_ref, BenchmarkEvaluation)
    fresh = ChampionRegistry(root=registry_root, store=FileSystemCAS(tmp_path / "cas"))
    observed = fresh.get("calibration_meta")
    assert observed is not None
    print(
        json.dumps(
            {
                "predecessor_ref": predecessor.candidate_ref.model_dump(mode="json"),
                "competing_ref": competing.candidate_ref.model_dump(mode="json"),
                "observed_ref": observed.candidate_ref.model_dump(mode="json"),
                "challenger_metrics": challenger.holdout_metrics,
                "competing_metrics": competing_evaluation.holdout_metrics,
                "challenger_guardrails": challenger.guardrails,
                "decision": stage_b["feedback"]["promotion_decision"],
            },
            sort_keys=True,
        )
    )
    assert (
        challenger.holdout_metrics["aggregate_fit_quality"]
        > (competing_evaluation.holdout_metrics["aggregate_fit_quality"])
    )
    # Condition10**(2/3) has uncertainty score .6; condition1 has score1.
    # A higher primary fit cannot authorize weakening the real incumbent's
    # uncertainty guardrail by .4 when the declared allowance is only .05.
    assert challenger.holdout_metrics["uncertainty_conditioning_score"] < (
        competing_evaluation.holdout_metrics["uncertainty_conditioning_score"] - 0.05
    )
    assert observed.candidate_ref == competing.candidate_ref
