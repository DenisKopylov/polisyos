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
    CalibrationUncertainty,
    put_calibration_config,
    put_calibration_report,
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


def test_calibration_meta_retains_fit_but_blocks_unverified_curvature_and_divergence(
    tmp_path,
) -> None:
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

    assert good_decision.promoted is False
    assert good_decision.reason == "guardrail_failed:uncertainty_not_worse"
    assert good_eval.holdout_metrics["fit_quality_score"] > 0
    assert good_eval.status == "limited"
    assert "uncertainty_conditioning_score" not in good_eval.holdout_metrics
    assert good_eval.runtime_split_type is BenchmarkSplit.HOLDOUT
    assert bad_eval.guardrails["no_divergence"] is False
    assert bad_decision.promoted is False
    assert bad_decision.reason == "guardrail_failed:no_divergence"
    champion = registry.get("calibration_meta")
    assert champion is None
    assert load_model_artifact(store, good_eval_ref, BenchmarkEvaluation) == good_eval
    assert {edge.role: edge for edge in store.get_manifest(good_eval_ref).inputs} == {
        "candidate": input_ref_from_artifact_ref(good_candidate_ref, role="candidate"),
        "benchmark_suite": input_ref_from_artifact_ref(suite_ref, role="benchmark_suite"),
    }
    assert CalibrationMetaRuntimeLoader(store=store, registry=registry).load().learning_rate is None


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
    assert evaluation.promotable is False
    assert evaluation.guardrails["uncertainty_not_worse"] is False
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
    assert decision.promoted is False
    if with_holdout:
        assert decision.reason == "guardrail_failed:uncertainty_not_worse"
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


def _conditional_report(condition: float | None, *, raw_status="finite", raw_value=1.0):
    report = _report(rmse=0.1, runtime_seconds=0.2)
    return report.model_copy(
        update={
            "uncertainties": CalibrationUncertainty(
                params=["node.param"],
                covariance=[[1.0]],
                correlation=[[1.0]],
                std=[1.0],
                hessian_rank=1,
                hessian_condition=condition,
            ),
            "execution_context": {
                **report.execution_context,
                "hessian": {
                    "raw_condition_status": raw_status,
                    "raw_condition_value": raw_value,
                    "method": "actual_selected_forward_hessian",
                    "non_authoritative": True,
                },
            },
        }
    )


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "raw_missing",
        "zero",
        "negative",
        "below_one",
        "nan",
        "infinite",
        "bad_projection",
    ],
)
def test_calibration_uncertainty_missing_or_bad_is_not_a_perfect_promotion_score(
    tmp_path, case
) -> None:
    reports = {
        "missing": _report(rmse=0.1, runtime_seconds=0.2),
        "raw_missing": _conditional_report(1.0).model_copy(
            update={"execution_context": {"runtime_seconds": 0.2}}
        ),
        "zero": _conditional_report(0.0, raw_value=0.0),
        "negative": _conditional_report(-1.0, raw_value=-1.0),
        "below_one": _conditional_report(0.5, raw_value=0.5),
        "nan": _conditional_report(float("nan"), raw_status="non_finite", raw_value=None),
        "infinite": _conditional_report(float("inf"), raw_status="non_finite", raw_value=None),
        "bad_projection": _conditional_report(1.0, raw_status="non_finite", raw_value=None),
    }
    store = FileSystemCAS(tmp_path / "uncertainty_guard")
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    suite_ref = persist_benchmark_suite(
        store, _calibration_suite(tmp_path), return_selected_profile=True
    )
    suite_input = input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")
    candidate_ref = persist_mutation_artifact(
        store, CalibrationMetaSearchConfig(), inputs=[suite_input], return_selected_profile=True
    )
    result = CalibrationMetaEvaluator(store=store, registry=registry).evaluate(
        candidate_ref,
        suite_ref,
        {"calibration_runner": lambda *_args: reports[case]},
    )
    assert result.guardrails["no_divergence"] is True
    assert result.guardrails["uncertainty_not_worse"] is False
    assert "uncertainty_conditioning_score" not in result.holdout_metrics
    assert result.holdout_metrics["fit_quality_score"] > 0
    assert result.status == "limited"
    assert result.promotable is False
    evaluation_ref = persist_benchmark_evaluation(store, result, inputs=[suite_input])
    decision = registry.consider_promotion(
        "calibration_meta",
        candidate_ref,
        evaluation_ref,
        default_calibration_policy(),
        suite_ref=suite_ref,
    )
    assert decision.promoted is False
    assert decision.reason == "guardrail_failed:uncertainty_not_worse"
    assert registry.get("calibration_meta") is None


@pytest.mark.parametrize("singular", [False, True])
def test_selected_report_finite_declarations_remain_diagnostic_without_curvature_replay(
    tmp_path, singular
) -> None:
    import jax
    import jax.numpy as jnp

    # The singular adversary changes the actual model curvature while preserving every
    # producer-declared finite field. A selected hash authenticates those bytes, not the claim.
    coefficient = 0.0 if singular else 1.0
    actual = jax.hessian(lambda x: coefficient * jnp.sum(x * x) / 2)(jnp.asarray([0.0]))
    assert float(actual[0, 0]) == coefficient
    report = _conditional_report(1.0)
    store = FileSystemCAS(tmp_path / "selected_guard")
    config_ref = put_calibration_config(store, CalibrationConfig(), return_selected_profile=True)
    report_ref = put_calibration_report(
        store, report, inputs=[input_ref_from_artifact_ref(config_ref, role="calibration_config")]
    )
    suite_ref = persist_benchmark_suite(
        store, _calibration_suite(tmp_path), return_selected_profile=True
    )
    suite_input = input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")
    candidate_ref = persist_mutation_artifact(
        store, CalibrationMetaSearchConfig(), inputs=[suite_input], return_selected_profile=True
    )
    registry = ChampionRegistry(root=tmp_path / "registry", store=store)
    result = CalibrationMetaEvaluator(
        store=FileSystemCAS(tmp_path / "selected_guard"), registry=registry
    ).evaluate(
        candidate_ref, suite_ref, {"calibration_runner": lambda *_args: (report, report_ref)}
    )
    assert result.guardrails["no_divergence"] is True
    assert result.holdout_metrics["uncertainty_conditioning_score"] == 1.0
    assert result.guardrails["uncertainty_not_worse"] is False
    assert result.holdout_metrics["fit_quality_score"] > 0
    assert result.promotable is False
    assert "calibration_hessian_curvature_verification_missing" in result.notes
    result_ref = persist_benchmark_evaluation(store, result, inputs=[suite_input])
    fresh = load_model_artifact(
        FileSystemCAS(tmp_path / "selected_guard"), result_ref, BenchmarkEvaluation
    )
    assert fresh == result
    assert fresh.metadata["calibration_uncertainty"]["holdout"][0]["gate_eligible"] is False
    assert (
        registry.consider_promotion(
            "calibration_meta",
            candidate_ref,
            result_ref,
            default_calibration_policy(),
            suite_ref=suite_ref,
        ).promoted
        is False
    )


def _forged_calibration_champion(tmp_path):
    from polisyos.scientist.methods.autotune.models import ChampionPointer

    store = FileSystemCAS(tmp_path / "champion_cas")
    registry_root = tmp_path / "champions"
    suite_ref = persist_benchmark_suite(
        store, _calibration_suite(tmp_path), return_selected_profile=True
    )
    suite_input = input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")
    candidate_ref = persist_mutation_artifact(
        store,
        CalibrationMetaSearchConfig(learning_rate=0.4),
        inputs=[suite_input],
        return_selected_profile=True,
    )
    evaluation = BenchmarkEvaluation(
        loop_id="calibration_meta",
        suite_id="calibration_suite",
        candidate_ref=candidate_ref,
        holdout_metrics={"aggregate_fit_quality": 0.99},
        sample_counts={"holdout": 1},
        guardrails={"no_divergence": True, "uncertainty_not_worse": True},
        promotable=True,
        runtime_split_type=BenchmarkSplit.HOLDOUT,
    )
    evaluation_ref = persist_benchmark_evaluation(
        store, evaluation, inputs=[suite_input], return_selected_profile=True
    )
    pointer = ChampionPointer(
        loop_id="calibration_meta",
        candidate_ref=candidate_ref,
        evaluation_ref=evaluation_ref,
        metrics=dict(evaluation.holdout_metrics),
        metadata={"seeded_baseline": True},
    )
    return store, registry_root, suite_ref, pointer


def test_calibration_registry_rejects_correctly_bound_stale_green_evaluation(tmp_path) -> None:
    store, registry_root, suite_ref, pointer = _forged_calibration_champion(tmp_path)
    registry = ChampionRegistry(root=registry_root, store=store)
    result = registry.consider_promotion(
        "calibration_meta",
        pointer.candidate_ref,
        pointer.evaluation_ref,
        default_calibration_policy(),
        suite_ref=suite_ref,
    )
    assert result.promoted is False
    assert result.reason == "calibration_hessian_curvature_verification_missing"
    assert not (registry_root / "calibration_meta/champion.json").exists()


@pytest.mark.parametrize("route", ["write_pointer", "seed_baseline"])
def test_calibration_registry_manual_routes_cannot_admit_an_unverified_replacement(
    tmp_path, route
) -> None:
    store, registry_root, _, pointer = _forged_calibration_champion(tmp_path)
    registry = ChampionRegistry(root=registry_root, store=store)
    if route == "write_pointer":
        with pytest.raises(ValueError, match="calibration_hessian_curvature_verification_missing"):
            registry.write_pointer("calibration_meta", pointer)
    else:
        with pytest.raises(ValueError, match="calibration_hessian_curvature_verification_missing"):
            registry.seed_baseline(
                "calibration_meta",
                candidate_ref=pointer.candidate_ref,
                evaluation_ref=pointer.evaluation_ref,
                metadata={"seeded_baseline": True},
            )
    assert not (registry_root / "calibration_meta/champion.json").exists()


@pytest.mark.parametrize("loader_kind", ["specific", "generic"])
def test_stale_calibration_pointer_is_retained_but_cannot_reach_runtime(
    tmp_path, loader_kind
) -> None:
    from polisyos.scientist.methods.autotune.calibration import (
        build_baseline_calibration_meta_config,
    )
    from polisyos.scientist.methods.autotune.runtime import ChampionBackedRuntimeLoader

    store, registry_root, _, pointer = _forged_calibration_champion(tmp_path)
    path = registry_root / "calibration_meta/champion.json"
    path.parent.mkdir(parents=True)
    original = pointer.model_dump_json().encode()
    path.write_bytes(original)
    registry = ChampionRegistry(root=registry_root, store=store)
    loader = (
        CalibrationMetaRuntimeLoader(store=store, registry=registry)
        if loader_kind == "specific"
        else ChampionBackedRuntimeLoader(
            loop_id="calibration_meta",
            model_cls=CalibrationMetaSearchConfig,
            baseline_factory=build_baseline_calibration_meta_config,
            store=store,
            registry=registry,
        )
    )
    assert loader.load() == build_baseline_calibration_meta_config()
    assert path.read_bytes() == original
    with pytest.raises(ValueError, match="calibration_hessian_curvature_verification_missing"):
        registry.get("calibration_meta")


def test_calibration_builtin_baseline_and_same_identity_metadata_update_remain_usable(
    tmp_path,
) -> None:
    from polisyos.scientist.methods.autotune.calibration import (
        build_baseline_calibration_meta_config,
    )

    store = FileSystemCAS(tmp_path / "baseline")
    registry = ChampionRegistry(root=tmp_path / "champions", store=store)
    loader = CalibrationMetaRuntimeLoader(store=store, registry=registry)
    assert loader.load() == build_baseline_calibration_meta_config()
    pointer = registry.get("calibration_meta")
    assert pointer is not None
    updated = pointer.model_copy(update={"metadata": {**pointer.metadata, "judge": "retained"}})
    registry.write_pointer("calibration_meta", updated)
    assert registry.get("calibration_meta") == updated
    assert loader.load() == build_baseline_calibration_meta_config()


def test_calibration_manual_replacement_preserves_an_existing_real_baseline(tmp_path) -> None:
    store, registry_root, _, forged = _forged_calibration_champion(tmp_path)
    registry = ChampionRegistry(root=registry_root, store=store)
    loader = CalibrationMetaRuntimeLoader(store=store, registry=registry)
    original_config = loader.load()
    original_pointer = registry.get("calibration_meta")
    path = registry_root / "calibration_meta/champion.json"
    original_bytes = path.read_bytes()
    assert original_pointer is not None
    replacement = original_pointer.model_copy(
        update={"candidate_ref": forged.candidate_ref, "evaluation_ref": forged.evaluation_ref}
    )
    with pytest.raises(ValueError, match="calibration_hessian_curvature_verification_missing"):
        registry.write_pointer("calibration_meta", replacement)
    assert path.read_bytes() == original_bytes
    assert registry.get("calibration_meta") == original_pointer
    assert loader.load() == original_config


def test_calibration_baseline_label_and_default_config_do_not_authorize_a_green_evaluation(
    tmp_path,
) -> None:
    from polisyos.scientist.methods.autotune.calibration import (
        build_baseline_calibration_meta_config,
    )

    store = FileSystemCAS(tmp_path / "counterfeit_baseline")
    registry_root = tmp_path / "champions"
    registry = ChampionRegistry(root=registry_root, store=store)
    candidate_ref = persist_mutation_artifact(store, build_baseline_calibration_meta_config())
    evaluation_ref = persist_benchmark_evaluation(
        store,
        BenchmarkEvaluation(
            loop_id="calibration_meta",
            suite_id="calibration_meta.baseline",
            candidate_ref=candidate_ref,
            status="seeded_baseline",
            promotable=True,
            holdout_metrics={"aggregate_fit_quality": 0.99},
            guardrails={"uncertainty_not_worse": True},
            metadata={"seeded_baseline": True},
        ),
    )
    with pytest.raises(ValueError, match="calibration_hessian_curvature_verification_missing"):
        registry.seed_baseline(
            "calibration_meta",
            candidate_ref=candidate_ref,
            evaluation_ref=evaluation_ref,
            metadata={"seeded_baseline": True},
        )
    assert not (registry_root / "calibration_meta/champion.json").exists()


def test_calibration_valid_baseline_cannot_overwrite_retained_stale_pointer(tmp_path) -> None:
    store, registry_root, _, stale = _forged_calibration_champion(tmp_path)
    valid_registry = ChampionRegistry(root=tmp_path / "valid", store=store)
    CalibrationMetaRuntimeLoader(store=store, registry=valid_registry).load()
    valid = valid_registry.get("calibration_meta")
    assert valid is not None
    path = registry_root / "calibration_meta/champion.json"
    path.parent.mkdir(parents=True)
    original = stale.model_dump_json().encode()
    path.write_bytes(original)
    registry = ChampionRegistry(root=registry_root, store=store)
    with pytest.raises(ValueError, match="calibration_hessian_curvature_verification_missing"):
        registry.write_pointer("calibration_meta", valid)
    assert path.read_bytes() == original


def test_calibration_baseline_keeps_selected_views_when_the_default_candidate_view_is_foreign(
    tmp_path,
) -> None:
    from polisyos.scientist.methods.autotune.calibration import (
        build_baseline_calibration_meta_config,
    )

    store = FileSystemCAS(tmp_path / "baseline_profiles")
    baseline = build_baseline_calibration_meta_config()
    suite_ref = persist_benchmark_suite(
        store, _calibration_suite(tmp_path), return_selected_profile=True
    )
    foreign_edge = input_ref_from_artifact_ref(suite_ref, role="foreign_context")
    foreign = persist_mutation_artifact(
        store, baseline, inputs=[foreign_edge], return_selected_profile=True
    )
    registry_root = tmp_path / "champions"
    registry = ChampionRegistry(root=registry_root, store=store)
    assert CalibrationMetaRuntimeLoader(store=store, registry=registry).load() == baseline
    pointer = registry.get("calibration_meta")
    assert pointer is not None
    assert pointer.candidate_ref.artifact_id == foreign.artifact_id
    assert pointer.candidate_ref.manifest_profile_sha256 is not None
    assert pointer.candidate_ref.manifest_profile_sha256 != foreign.manifest_profile_sha256
    assert pointer.evaluation_ref.manifest_profile_sha256 is not None
    assert store.get_manifest(pointer.candidate_ref.artifact_id).inputs == [foreign_edge]
    assert store.get_manifest(pointer.candidate_ref).inputs == []
    evaluation = load_model_artifact(store, pointer.evaluation_ref, BenchmarkEvaluation)
    alternate = persist_benchmark_evaluation(
        store, evaluation, inputs=[foreign_edge], return_selected_profile=True
    )
    assert alternate.artifact_id == pointer.evaluation_ref.artifact_id
    assert alternate.manifest_profile_sha256 != pointer.evaluation_ref.manifest_profile_sha256
    fresh = FileSystemCAS(tmp_path / "baseline_profiles")
    fresh_registry = ChampionRegistry(root=registry_root, store=fresh)
    assert fresh_registry.get("calibration_meta") == pointer
    assert CalibrationMetaRuntimeLoader(store=fresh, registry=fresh_registry).load() == baseline


def test_safely_resolved_legacy_unprofiled_calibration_baseline_remains_readable(tmp_path) -> None:
    from polisyos.scientist.methods.autotune.calibration import (
        build_baseline_calibration_meta_config,
    )
    from polisyos.scientist.methods.autotune.runtime import _build_baseline_evaluation

    store = FileSystemCAS(tmp_path / "legacy_baseline")
    baseline = build_baseline_calibration_meta_config()
    candidate_ref = persist_mutation_artifact(store, baseline)
    evaluation_ref = persist_benchmark_evaluation(
        store,
        _build_baseline_evaluation(
            loop_id="calibration_meta", candidate_ref=candidate_ref, suite_version="1.0"
        ),
    )
    assert candidate_ref.manifest_profile_sha256 is None
    assert evaluation_ref.manifest_profile_sha256 is None
    registry_root = tmp_path / "champions"
    registry = ChampionRegistry(root=registry_root, store=store)
    pointer = registry.seed_baseline(
        "calibration_meta", candidate_ref=candidate_ref, evaluation_ref=evaluation_ref
    )
    fresh = FileSystemCAS(tmp_path / "legacy_baseline")
    fresh_registry = ChampionRegistry(root=registry_root, store=fresh)
    assert fresh_registry.get("calibration_meta") == pointer
    assert CalibrationMetaRuntimeLoader(store=fresh, registry=fresh_registry).load() == baseline
