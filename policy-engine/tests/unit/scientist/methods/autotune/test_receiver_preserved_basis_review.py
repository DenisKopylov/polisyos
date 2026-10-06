"""Independent receiver negatives with real CAS/basis and native GP boundaries.

The analytic producer is a conditional fixture. These controls establish type
faithfulness, not scientific measurement truth or institutional authorization.
"""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from botorch.models import SingleTaskGP

from polisyos.core import artifacts, canon
from polisyos.scientist.methods.autotune.bayesian_generator import (
    BayesianCandidateGenerator,
    SearchSpace,
)
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSplitManifest,
    BenchmarkSuite,
    MetricDirection,
    MutationArtifact,
    PromotionPolicy,
    benchmark_comparison_basis,
    benchmark_evaluator_profile,
    load_benchmark_inputs,
    load_model_artifact,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
    persist_split_manifest,
)
from polisyos.scientist.methods.autotune.registry import ChampionRegistry
from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
from tests.unit.scientist.methods.search.strategies.test_transfer import measured_history


class ReviewMutation(MutationArtifact):
    x: float


class ReviewDatasetEvaluator:
    """Execute a small declared measurement from persisted candidate/dataset bytes."""

    def evaluate(self, candidate_ref, suite_ref, context):
        store = context["store"]
        candidate = load_model_artifact(store, candidate_ref, ReviewMutation)
        suite = load_model_artifact(store, suite_ref, BenchmarkSuite)
        rows, split = load_benchmark_inputs(store, suite)
        selected = [row for row in rows if row["id"] in split.selection_ids]
        score = candidate.x**2 + sum(row["loss"] for row in selected) / len(selected)
        return BenchmarkEvaluation(
            loop_id="receiver-review",
            suite_id=suite.suite_id,
            candidate_ref=candidate_ref,
            selection_metrics={"score": score},
            sample_counts={"selection": len(selected)},
            guardrails={"finite": True},
            promotable=True,
            runtime_split_type=BenchmarkSplit.SELECTION,
            comparison_basis=benchmark_comparison_basis(
                store, suite_ref, context["policy"], benchmark_evaluator_profile(self)
            ),
        )


@pytest.mark.parametrize(
    ("section", "field", "malformed"),
    [
        ("selection_metrics", "score", True),
        ("sample_counts", "selection", True),
        ("guardrails", "finite", 1),
    ],
)
def test_cold_registry_refuses_raw_wrong_types_with_complete_consumed_basis(
    tmp_path, section, field, malformed
):
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    dataset_ref = store.put_bytes(
        b'{"id":"one","loss":0.2}\n',
        artifacts.PutOptions(
            kind="scientist.autotune.benchmark_dataset", media_type="application/x-ndjson"
        ),
    )
    split_ref = persist_split_manifest(
        store,
        BenchmarkSplitManifest(suite_id="receiver-review", selection_ids=["one"]),
        inputs=[artifacts.input_ref_from_artifact_ref(dataset_ref, role="benchmark_dataset")],
    )
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(
            suite_id="receiver-review",
            kind="review",
            data_basis="dataset",
            dataset_ref=dataset_ref,
            split_manifest_ref=split_ref,
        ),
    )
    candidate_ref = persist_mutation_artifact(
        store,
        ReviewMutation(loop_id="receiver-review", x=0.0),
        inputs=[artifacts.input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
    )
    policy = PromotionPolicy(
        loop_id="receiver-review",
        primary_metric="score",
        unit="fixture-loss",
        direction=MetricDirection.MINIMIZE,
        compare_split=BenchmarkSplit.SELECTION,
        min_sample_count=1,
        required_guardrails=["finite"],
    )
    evaluation = ReviewDatasetEvaluator().evaluate(
        candidate_ref, suite_ref, {"store": store, "policy": policy}
    )
    valid_ref = persist_benchmark_evaluation(store, evaluation)
    control = ChampionRegistry(tmp_path / "control", store=store).consider_promotion(
        policy.loop_id, candidate_ref, valid_ref, policy, suite_ref=suite_ref
    )
    assert control.promoted, control.reason
    payload = canon.from_canonical_bytes(store.get_bytes(valid_ref))
    payload[section][field] = malformed
    manifest = store.get_manifest(valid_ref)
    changed_ref = store.put_json(
        payload,
        artifacts.ArtifactWriteOptions(
            kind=valid_ref.kind,
            media_type=valid_ref.media_type,
            schema=manifest.artifact_schema,
            inputs=manifest.inputs,
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )
    assert store.get_manifest(changed_ref).inputs == manifest.inputs
    assert (
        canon.from_canonical_bytes(store.get_bytes(changed_ref))["comparison_basis"]
        == (payload["comparison_basis"])
    )
    registry = ChampionRegistry(tmp_path / "negative", store=store)
    try:
        decision = registry.consider_promotion(
            policy.loop_id, candidate_ref, changed_ref, policy, suite_ref=suite_ref
        )
    except (TypeError, ValueError):
        return
    print(
        json.dumps(
            {
                "section": section,
                "raw_value": malformed,
                "decision": decision.model_dump(mode="json"),
                "comparison_basis": payload["comparison_basis"],
            }
        )
    )
    assert not decision.promoted, "Wrong JSON primitive type reached champion admission"
    assert registry.get(policy.loop_id) is None


def test_public_generator_does_not_repair_stage_flag_before_real_cas_admission(tmp_path):
    _, _, manager, source, target, original, basis = measured_history(tmp_path, count=8)
    # Supply legitimate source metadata for the existing public current-history adapter.
    for row in original:
        row.metadata.update(
            source="search_iteration",
            params_normalized=list(row.params_normalized),
            candidate_id=row.candidate_id,
            provenance_ref=row.provenance_ref,
        )
    source.history_ref = manager.register_run(source, original)
    rows = manager.get_warm_start_evaluations([source], max_evals=8, target_fingerprint=target)
    bridge = WarmStartBridge(manager, max_evals=0)
    generator = BayesianCandidateGenerator(
        SearchSpace(bounds=basis.bounds["parameters"]),
        primary_metric="score",
        direction=MetricDirection.MINIMIZE,
        compare_split=BenchmarkSplit.SELECTION,
        n_initial=3,
        seed=19,
        warm_start_bridge=bridge,
        warm_start_fingerprint=target,
    )
    assert generator.botorch_available
    assert generator._optimizer._warm_evals == []
    generator._optimizer._config = replace(
        generator._optimizer._config,
        num_restarts=2,
        raw_samples=32,
        refit_interval=20,
        fallback_on_failure=False,
    )
    history = [
        SimpleNamespace(
            candidate={"params": row.params},
            stage_b_result=row.stage_b_result,
            metadata=row.metadata,
            objective_value=row.scalar_score,
            stage_a_passed=True,
            timestamp=row.timestamp,
            duration_seconds=row.wall_time_seconds,
        )
        for row in rows
    ]
    # Verify legitimate baseline eligibility without another GP fit or a mocked reader.
    valid = generator._history_to_evaluations(history)
    assert len(bridge.admit_warm_start(valid, basis)) == 8
    history[0].stage_a_passed = "false"
    generator.generate(history, None, {})
    model = generator._optimizer._model
    if model is None:
        return  # Controlled refusal of the malformed corpus is also safe.
    assert isinstance(model, SingleTaskGP)
    count = len(generator._optimizer._fitted_train_X)
    print(json.dumps({"native_fitted_rows": count, "malformed_stage_flag": "false"}))
    assert count == 7, "Malformed declared stage flag was coerced into an admitted true outcome"
