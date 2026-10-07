"""Real CAS and cold registry controls for primitive evidence admission."""

from __future__ import annotations

import json
from typing import get_args

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.methods.autotune import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    ChampionRegistry,
    MutationArtifact,
    PromotionPolicy,
    persist_benchmark_evaluation,
    persist_benchmark_suite,
    persist_mutation_artifact,
)
from polisyos.scientist.methods.autotune.calibration import CalibrationMetaSearchConfig
from polisyos.scientist.methods.autotune.cheap_stage import CheapStageTuningConfig
from polisyos.scientist.methods.autotune.claim_adjudication import ClaimAdjudicationSearchConfig
from polisyos.scientist.methods.autotune.models import (
    benchmark_comparison_basis,
    load_model_artifact,
)


def _valid_artifacts(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    suite_ref = persist_benchmark_suite(
        store, BenchmarkSuite(suite_id="primitive-suite", data_basis="candidate_only")
    )
    candidate_ref = persist_mutation_artifact(
        store,
        MutationArtifact(loop_id="primitive-witness"),
        inputs=[input_ref_from_artifact_ref(suite_ref, role="benchmark_suite")],
    )
    policy = PromotionPolicy(
        loop_id="primitive-witness",
        primary_metric="score",
        compare_split=BenchmarkSplit.HOLDOUT,
        min_sample_count=1,
        required_guardrails=["finite"],
    )
    evaluation = BenchmarkEvaluation(
        loop_id=policy.loop_id,
        suite_id="primitive-suite",
        candidate_ref=candidate_ref,
        selection_metrics={"score": 1},
        holdout_metrics={"score": 1},
        sample_counts={"selection": 1, "holdout": 1},
        guardrails={"finite": True},
        promotable=True,
        runtime_split_type=BenchmarkSplit.HOLDOUT,
        comparison_basis=benchmark_comparison_basis(
            store, suite_ref, policy, SchemaInfo(name="fixture.numeric", version="1.0")
        ),
    )
    ref = persist_benchmark_evaluation(store, evaluation)
    return store, suite_ref, candidate_ref, policy, ref


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("selection_metrics", "score", True),
        ("selection_metrics", "score", "1"),
        ("holdout_metrics", "score", False),
        ("holdout_metrics", "score", "1"),
        ("sample_counts", "selection", True),
        ("sample_counts", "holdout", "1"),
        ("sample_counts", "holdout", 1.0),
        ("guardrails", "finite", 1),
        ("guardrails", "finite", "true"),
        (None, "promotable", 1),
        (None, "promotable", "true"),
        (None, "suite_version", True),
        ("comparison_basis", "schema_version", "benchmark-comparison.v2"),
    ],
)
def test_raw_primitive_refusal_preserves_complete_basis_and_cold_pointer(
    tmp_path, section, field, value
):
    store, suite, candidate, policy, valid_ref = _valid_artifacts(tmp_path)
    control = ChampionRegistry(tmp_path / "control", store=store).consider_promotion(
        policy.loop_id, candidate, valid_ref, policy, suite_ref=suite
    )
    assert control.promoted, control.reason
    payload = from_canonical_bytes(store.get_bytes(valid_ref))
    if section is None:
        payload[field] = value
    else:
        payload[section][field] = value
    manifest = store.get_manifest(valid_ref)
    malformed = store.put_json(
        payload,
        ArtifactWriteOptions(
            kind=valid_ref.kind,
            media_type=valid_ref.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
            inputs=manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    assert store.get_manifest(malformed).inputs == manifest.inputs
    with pytest.raises((TypeError, ValueError)):
        load_model_artifact(store, malformed, BenchmarkEvaluation)
    root = tmp_path / "negative"
    with pytest.raises((TypeError, ValueError)):
        ChampionRegistry(root, store=store).consider_promotion(
            policy.loop_id, candidate, malformed, policy, suite_ref=suite
        )
    assert ChampionRegistry(root, store=FileSystemCAS(tmp_path / "cas")).get(policy.loop_id) is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("section", ["selection_metrics", "holdout_metrics"])
def test_nonfinite_evidence_refused_before_producer_persistence(tmp_path, section, value):
    store, _, _, _, ref = _valid_artifacts(tmp_path)
    payload = from_canonical_bytes(store.get_bytes(ref))
    payload[section]["score"] = value
    with pytest.raises(ValidationError):
        BenchmarkEvaluation.model_validate(payload)


def test_declared_builtin_mutation_numeric_fields_refuse_coercion_in_real_cas(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    exercised = []
    for model in (
        CalibrationMetaSearchConfig,
        CheapStageTuningConfig,
        ClaimAdjudicationSearchConfig,
    ):
        baseline = model()
        ref = persist_mutation_artifact(store, baseline)
        assert load_model_artifact(store, ref, model) == baseline
        for name, field in model.model_fields.items():
            primitives = {field.annotation, *get_args(field.annotation)} & {bool, int, float}
            if not primitives:
                continue
            malformed = baseline.model_dump(mode="json")
            malformed[name] = 1 if bool in primitives else True
            manifest = store.get_manifest(ref)
            bad_ref = store.put_json(
                malformed,
                ArtifactWriteOptions(
                    kind=ref.kind,
                    media_type=ref.media_type,
                    schema=manifest.artifact_schema,
                    producer=manifest.producer,
                    inputs=manifest.inputs,
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
            with pytest.raises((TypeError, ValueError)):
                load_model_artifact(store, bad_ref, model)
            exercised.append(f"{model.__name__}.{name}")
    assert exercised
    print(json.dumps({"actual_builtin_numeric_fields": exercised}))


def test_fresh_pointer_reader_refuses_boolean_cached_metric_without_rewrite(tmp_path):
    store, suite, candidate, policy, ref = _valid_artifacts(tmp_path)
    root = tmp_path / "registry"
    assert (
        ChampionRegistry(root, store=store)
        .consider_promotion(policy.loop_id, candidate, ref, policy, suite_ref=suite)
        .promoted
    )
    path = root / policy.loop_id / "champion.json"
    payload = json.loads(path.read_bytes())
    payload["metrics"]["score"] = True
    path.write_text(json.dumps(payload))
    before = path.read_bytes()
    with pytest.raises(ValidationError):
        ChampionRegistry(root, store=FileSystemCAS(tmp_path / "cas")).get(policy.loop_id)
    assert path.read_bytes() == before
