"""Conditional technical transfer admission through real CAS and native HNSW.

The measured fixtures use an explicit analytic function. They establish content
identity and replay behavior, not production performance or source authority.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pytest

from polisyos.core import artifacts, canon
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.agent.vector_memory import VectorMemoryStore
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    persist_benchmark_evaluation,
)
from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.transfer import (
    NumericTransferBasis,
    RunFingerprint,
    TransferLearningManager,
)
from polisyos.scientist.methods.search.strategies.types import Evaluation, ParameterBounds


def measured_history(tmp_path, *, direction=OptimizationDirection.MINIMIZE, count=8):
    """Persist actual candidate, original BenchmarkEvaluation and complete role refs."""
    store = FileSystemCAS(tmp_path / "cas")
    space = SearchSpace(bounds=[ParameterBounds(name="x", lower=0.0, upper=1.0)])
    refs = {
        role + "_ref": store.put_json(
            {"role": role, "profile": "analytic-transfer-fixture.v1"},
            artifacts.PutOptions(kind="fixture.numeric." + role, media_type="application/json"),
        )
        for role in ("data", "model", "evaluator", "split", "scalarizer", "owner")
    }
    basis = NumericTransferBasis(
        search_space_fingerprint=space.sobol_space_fingerprint(),
        bounds={
            "parameters": [
                {
                    "name": "x",
                    "lower": 0.0,
                    "upper": 1.0,
                    "dtype": "continuous",
                    "log_scale": False,
                    "categories": None,
                }
            ]
        },
        metric="score",
        unit="analytic-loss",
        direction=direction,
        origin="analytic-measurement.v1",
        owner_id="fixture-owner",
        tenant_id="tenant-a",
        **refs,
    )
    source = RunFingerprint(
        run_id="source",
        space_hash=basis.search_space_fingerprint,
        objective_names=[basis.metric],
        bounds=deepcopy(basis.bounds),
        split=basis.split,
        units={basis.metric: basis.unit},
        origin=basis.origin,
        tenant_id=basis.tenant_id,
        objective_directions={basis.metric: basis.direction.value},
        embedding=[1.0, 0.0],
        numeric_basis=basis,
    )
    target = source.model_copy(deep=True, update={"run_id": "target"})
    evaluations = []
    for number in range(count):
        x = (number + 1) / (count + 1)
        raw = (x - 0.37) ** 2 + 0.01
        candidate = store.put_json(
            {"x": x},
            artifacts.PutOptions(kind="search.candidate", media_type="application/json"),
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )
        metadata = {
            "numeric_transfer_basis": basis.model_dump(mode="json"),
            "params": {"x": x},
            "source_run_id": source.run_id,
            "replica_id": number,
        }
        original = BenchmarkEvaluation(
            loop_id="analytic",
            suite_id="measured-selection",
            suite_version="1.0",
            candidate_ref=candidate,
            selection_metrics={"score": raw},
            sample_counts={"selection": 11},
            guardrails={"finite": True},
            status="ok",
            runtime_split_type=BenchmarkSplit.SELECTION,
            notes=["analytic fixture measurement"],
            metadata=metadata,
        )
        measurement = persist_benchmark_evaluation(store, original)
        evaluations.append(
            Evaluation(
                candidate_id=str(candidate.artifact_id),
                params={"x": x},
                params_normalized=space.normalize({"x": x}),
                objectives=[ObjectiveValue(name="score", raw_value=raw, direction=direction)],
                scalar_score=raw if direction == OptimizationDirection.MINIMIZE else -raw,
                stage_a_passed=True,
                stage_b_result={"guardrails": {"finite": True}},
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                wall_time_seconds=0.125,
                provenance_ref=str(measurement.artifact_id),
                metadata={
                    **deepcopy(metadata),
                    "candidate_ref": candidate.model_dump(mode="json"),
                    "evaluation_ref": measurement.model_dump(mode="json"),
                },
            )
        )
    index = VectorMemoryStore(dim=2, max_elements=10)
    manager = TransferLearningManager(store, index)
    source.history_ref = manager.register_run(source, evaluations)
    return store, index, manager, source, target, evaluations, basis


def changed_history(store, source, mutate):
    payload = canon.from_canonical_bytes(store.get_bytes(source.history_ref))
    mutate(payload)
    ref = store.put_json(
        payload,
        artifacts.PutOptions(kind="search.transfer.history", media_type="application/json"),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )
    return source.model_copy(deep=True, update={"history_ref": ref})


@pytest.mark.parametrize("direction", list(OptimizationDirection))
def test_exact_history_faithfully_rehydrates_and_ranks_direction_normalized_minima(
    tmp_path, direction
):
    _, index, manager, source, target, originals, basis = measured_history(
        tmp_path, direction=direction
    )
    discovered = manager.find_similar_runs(target)
    assert discovered[0].history_ref == source.history_ref
    rows = manager.get_warm_start_evaluations(discovered, target_fingerprint=target)
    assert [row.scalar_score for row in rows] == sorted(row.scalar_score for row in originals)
    by_id = {row.candidate_id: row for row in originals}
    for row in rows:
        original = by_id[row.candidate_id]
        assert row.params == original.params and row.params_normalized == original.params_normalized
        assert (
            row.timestamp == original.timestamp
            and row.wall_time_seconds == original.wall_time_seconds
        )
        assert (
            row.stage_b_result == original.stage_b_result
            and row.provenance_ref == original.provenance_ref
        )
        assert row.metadata["numeric_transfer_basis"] == basis.model_dump(mode="json")
    assert manager.admit_warm_start(rows, basis) == rows
    assert index.metadata_for_key("source")["history_ref"] == source.history_ref.model_dump(
        mode="json"
    )


@pytest.mark.parametrize(
    "field",
    [
        "data_ref",
        "model_ref",
        "evaluator_ref",
        "split_ref",
        "scalarizer_ref",
        "owner_ref",
        "unit",
        "direction",
        "origin",
        "owner_id",
        "tenant_id",
        "metric",
    ],
)
def test_each_complete_target_basis_identity_is_required(tmp_path, field):
    store, _, manager, source, target, _, basis = measured_history(tmp_path, count=2)
    payload = basis.model_dump(mode="json")
    if field.endswith("_ref"):
        changed = store.put_json(
            {"different": field},
            artifacts.PutOptions(kind="fixture.numeric.changed", media_type="application/json"),
        )
        payload[field] = changed.model_dump(mode="json")
    elif field == "direction":
        payload[field] = OptimizationDirection.MAXIMIZE.value
    else:
        payload[field] += ".different"
    different = NumericTransferBasis.model_validate(payload)
    different_target = target.model_copy(
        deep=True,
        update={
            "numeric_basis": different,
            "objective_names": [different.metric],
            "units": {different.metric: different.unit},
            "origin": different.origin,
            "tenant_id": different.tenant_id,
            "objective_directions": {different.metric: different.direction.value},
        },
    )
    assert manager.get_warm_start_evaluations([source], target_fingerprint=different_target) == []
    assert manager.last_admission_report["rejected"] == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("stage_a_passed", "false"),
        ("scalar_score", "0.1"),
        ("params_normalized", [True]),
        ("timestamp", 0),
        ("status", True),
        ("wall_time_seconds", False),
    ],
)
def test_malformed_declared_types_are_visible_refusals(tmp_path, field, value):
    store, _, manager, source, target, _, _ = measured_history(tmp_path, count=2)
    altered = changed_history(
        store, source, lambda payload: payload["evaluations"][0].update({field: value})
    )
    rows = manager.get_warm_start_evaluations([altered], target_fingerprint=target)
    assert len(rows) == 1
    assert manager.last_admission_report["loaded"] == 2
    assert manager.last_admission_report["rejected"] == 1


def test_candidate_content_not_ref_markers_binds_the_physical_input(tmp_path):
    store, _, manager, source, target, _, _ = measured_history(tmp_path, count=2)
    false_candidate = store.put_json(
        {"x": 0.95},
        artifacts.PutOptions(kind="search.candidate", media_type="application/json"),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )

    def alter(payload):
        row = payload["evaluations"][0]
        row["candidate_id"] = str(false_candidate.artifact_id)
        row["metadata"]["candidate_ref"] = false_candidate.model_dump(mode="json")
        original_ref = artifacts.ArtifactRef.model_validate(row["metadata"]["evaluation_ref"])
        original = BenchmarkEvaluation.model_validate(
            canon.from_canonical_bytes(store.get_bytes(original_ref))
        )
        changed = persist_benchmark_evaluation(
            store, original.model_copy(update={"candidate_ref": false_candidate})
        )
        row["provenance_ref"] = str(changed.artifact_id)
        row["metadata"]["evaluation_ref"] = changed.model_dump(mode="json")

    altered = changed_history(store, source, alter)
    assert len(manager.get_warm_start_evaluations([altered], target_fingerprint=target)) == 1
    assert (
        "physical parameters disagree" in manager.last_admission_report["rejections"][0]["reason"]
    )


def test_checkpoint_replay_re_resolves_original_artifacts_on_cache_hit(tmp_path):
    store, _, manager, source, target, _, basis = measured_history(tmp_path, count=2)
    rows = manager.get_warm_start_evaluations([source], target_fingerprint=target)
    assert manager.admit_warm_start(rows, basis) == rows
    original = artifacts.ArtifactRef.model_validate(rows[0].metadata["evaluation_ref"])
    blob, _ = store._paths(original.artifact_id)
    blob.write_bytes(b"changed source measurement under the same reference")
    assert len(manager.admit_warm_start(rows, basis)) == 1
    assert manager.last_admission_report["rejected"] == 1


def test_cache_full_identity_copy_lru_budget_and_exact_alias_lookup(tmp_path, monkeypatch):
    store, index, _, source, target, _, _ = measured_history(tmp_path, count=2)
    manager = TransferLearningManager(store, index, cache_max_entries=1, cache_max_bytes=100000)
    old = manager._load_run_evaluations(source)
    old[0]["metadata"]["params"]["x"] = 999
    assert manager._load_run_evaluations(source)[0]["metadata"]["params"]["x"] != 999
    newer = changed_history(store, source, lambda payload: payload["evaluations"].reverse())
    manager._load_run_evaluations(newer)
    assert manager.cache_info["entries"] == 1
    monkeypatch.setattr(
        index, "query", lambda *args, **kwargs: pytest.fail("known alias cannot perform ANN")
    )
    assert (
        manager._load_run_evaluations("source")[0]["candidate_id"]
        == manager._load_run_evaluations(source)[0]["candidate_id"]
    )
    bypass = TransferLearningManager(store, index, cache_max_bytes=1)
    assert len(bypass.get_warm_start_evaluations([source], target_fingerprint=target)) == 2
    assert bypass.cache_info == {"entries": 0, "serialized_bytes": 0}
    blob, _ = store._paths(source.history_ref.artifact_id)
    blob.write_bytes(b"changed history under the same ref")
    with pytest.raises(Exception, match="(sha256|mismatch|integrity)"):
        manager._load_run_evaluations(source)


def test_missing_basis_never_uses_first_source_as_target(tmp_path):
    _, _, manager, source, target, _, _ = measured_history(tmp_path, count=2)
    target.numeric_basis = None
    with pytest.raises(ValueError, match="Configured target"):
        manager.target_basis(target)
    assert manager.get_warm_start_evaluations([source]) == []
    assert manager.last_admission_report["rejected"] == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("promotable", "false"),
        ("guardrails", {"finite": "true"}),
        ("guardrails", {"finite": False}),
        ("selection_metrics", {"score": "0.1"}),
        ("sample_counts", {"selection": True}),
        ("runtime_split_type", "holdout"),
    ],
)
def test_original_benchmark_outcome_is_admitted_without_dto_coercion(tmp_path, field, value):
    store, _, manager, source, target, _, _ = measured_history(tmp_path, count=2)

    def mutate(payload):
        row = payload["evaluations"][0]
        original_ref = artifacts.ArtifactRef.model_validate(row["metadata"]["evaluation_ref"])
        original = canon.from_canonical_bytes(store.get_bytes(original_ref))
        original[field] = value
        manifest = store.get_manifest(original_ref)
        ref = store.put_json(
            original,
            artifacts.PutOptions(
                kind=manifest.kind, media_type=manifest.media_type, schema=manifest.artifact_schema
            ),
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )
        row["metadata"]["evaluation_ref"] = ref.model_dump(mode="json")
        row["provenance_ref"] = str(ref.artifact_id)

    altered = changed_history(store, source, mutate)
    assert len(manager.get_warm_start_evaluations([altered], target_fingerprint=target)) == 1
    assert manager.last_admission_report["rejected"] == 1


@pytest.mark.parametrize(
    "role", ["data_ref", "model_ref", "evaluator_ref", "split_ref", "scalarizer_ref", "owner_ref"]
)
def test_every_role_ref_is_resolved_again_on_checkpoint_restore(tmp_path, role):
    store, _, manager, source, target, _, basis = measured_history(tmp_path, count=2)
    rows = manager.get_warm_start_evaluations([source], target_fingerprint=target)
    blob, _ = store._paths(getattr(basis, role).artifact_id)
    blob.write_bytes(b"changed actual role content")
    assert manager.admit_warm_start(rows, basis) == []
    assert manager.last_admission_report["rejected"] == 2


def test_physical_out_of_bounds_cannot_hide_behind_clipped_normalization(tmp_path):
    store, _, manager, source, target, _, _ = measured_history(tmp_path, count=2)
    candidate = store.put_json(
        {"x": 2.0},
        artifacts.PutOptions(kind="search.candidate", media_type="application/json"),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )

    def mutate(payload):
        row = payload["evaluations"][0]
        row.update(
            candidate_id=str(candidate.artifact_id), params={"x": 2.0}, params_normalized=[1.0]
        )
        original_ref = artifacts.ArtifactRef.model_validate(row["metadata"]["evaluation_ref"])
        original = BenchmarkEvaluation.model_validate(
            canon.from_canonical_bytes(store.get_bytes(original_ref))
        )
        metadata = {**original.metadata, "params": {"x": 2.0}}
        ref = persist_benchmark_evaluation(
            store, original.model_copy(update={"candidate_ref": candidate, "metadata": metadata})
        )
        row["metadata"].update(
            candidate_ref=candidate.model_dump(mode="json"),
            evaluation_ref=ref.model_dump(mode="json"),
            params={"x": 2.0},
        )
        row["provenance_ref"] = str(ref.artifact_id)

    altered = changed_history(store, source, mutate)
    assert len(manager.get_warm_start_evaluations([altered], target_fingerprint=target)) == 1
    assert "outside its actual bounds" in manager.last_admission_report["rejections"][0]["reason"]


def test_unknown_history_codec_refuses_before_caching_or_training(tmp_path):
    store, _, manager, source, target, _, _ = measured_history(tmp_path, count=2)
    altered = changed_history(store, source, lambda payload: payload.update(schema_version="3.0"))
    assert manager.get_warm_start_evaluations([altered], target_fingerprint=target) == []
    assert manager.last_admission_report["unavailable"] == 1
    assert manager.cache_info["entries"] == 0


def test_original_benchmark_physical_input_cannot_coerce_boolean_to_number(tmp_path):
    store, _, manager, source, target, _, _ = measured_history(tmp_path, count=2)
    candidate = store.put_json(
        {"x": 1.0},
        artifacts.PutOptions(kind="search.candidate", media_type="application/json"),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )

    def mutate(payload):
        row = payload["evaluations"][0]
        row.update(
            candidate_id=str(candidate.artifact_id), params={"x": 1.0}, params_normalized=[1.0]
        )
        original_ref = artifacts.ArtifactRef.model_validate(row["metadata"]["evaluation_ref"])
        original = BenchmarkEvaluation.model_validate(
            canon.from_canonical_bytes(store.get_bytes(original_ref))
        )
        ref = persist_benchmark_evaluation(
            store,
            original.model_copy(
                update={
                    "candidate_ref": candidate,
                    "metadata": {**original.metadata, "params": {"x": True}},
                }
            ),
        )
        row["metadata"].update(
            candidate_ref=candidate.model_dump(mode="json"),
            evaluation_ref=ref.model_dump(mode="json"),
            params={"x": 1.0},
        )
        row["provenance_ref"] = str(ref.artifact_id)

    altered = changed_history(store, source, mutate)
    assert len(manager.get_warm_start_evaluations([altered], target_fingerprint=target)) == 1
    assert manager.last_admission_report["rejected"] == 1
