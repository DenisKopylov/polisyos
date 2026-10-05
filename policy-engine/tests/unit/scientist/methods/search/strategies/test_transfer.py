"""CAS snapshot and consumer isolation checks for numerical transfer."""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from datetime import UTC, datetime

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.canon.canon_json import CanonSpec
from polisyos.scientist.agent.vector_memory import VectorMemoryStore
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    persist_benchmark_evaluation,
)
from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.transfer import (
    RunFingerprint,
    TransferHistoryError,
    TransferLearningManager,
)
from polisyos.scientist.methods.search.strategies.types import Evaluation, ParameterBounds


def test_real_cas_history_registration_preserves_finite_numeric_values(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    source = RunFingerprint(run_id="source", space_hash="space", objective_names=["score"])
    evaluation = Evaluation(
        candidate_id="candidate",
        params={"x": 0.5},
        params_normalized=(0.5,),
        objectives=[
            ObjectiveValue(name="score", raw_value=0.8, direction=OptimizationDirection.MINIMIZE)
        ],
        scalar_score=0.8,
        stage_a_passed=True,
    )
    ref = TransferLearningManager(store, None).register_run(source, [evaluation])
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    assert payload["evaluations"][0]["params"] == {"x": 0.5}
    assert payload["evaluations"][0]["scalar_score"] == 0.8


def test_reverse_benchmark_view_requires_resolvable_original_lineage():
    evaluation = Evaluation(
        candidate_id=f"sha256:{'c' * 64}",
        params={"x": 0.5},
        params_normalized=(0.5,),
        objectives=[
            ObjectiveValue(name="score", raw_value=0.8, direction=OptimizationDirection.MINIMIZE)
        ],
        scalar_score=0.8,
        stage_a_passed=True,
    )
    with pytest.raises(ValueError, match="Original benchmark store/reference"):
        WarmStartBridge.evaluations_to_benchmarks([evaluation], loop_id="target")


def _measured_history(tmp_path, *, direction="minimize", run_id="source"):
    """Persist bounded analytic measurements; no production benchmark claim."""
    pytest.importorskip("hnswlib")
    store = FileSystemCAS(tmp_path / "cas")
    space = SearchSpace([ParameterBounds(name="x", lower=0.0, upper=1.0)])
    fingerprint = RunFingerprint(
        run_id=run_id,
        space_hash=space.sobol_space_fingerprint(),
        bounds={"x": [0.0, 1.0]},
        objective_names=["score"],
        split="selection",
        units={"score": "analytic_units"},
        origin="bounded-analytic-quadratic-v1",
        tenant_id="isolated-test-tenant",
        objective_directions={"score": direction},
        embedding=[1.0, 0.0],
    )
    compatibility = {
        "search_space_fingerprint": fingerprint.space_hash,
        "input_transform_fingerprint": "Normalize[0,1]",
        "outcome_transform_fingerprint": "Standardize[m=1]",
        "noise_model_fingerprint": "GaussianLikelihood[inferred]",
        "objective_fingerprint": "scalar_score[minimize]",
        "context_fingerprint": fingerprint.numeric_context_fingerprint(),
    }
    evaluations = []
    originals = []
    for x in (0.1, 0.4, 0.7, 0.9):
        raw_score = 100.0 * x * x
        candidate_ref = store.put_json(
            {"params": {"x": x}},
            PutOptions(kind="search.candidate", media_type="application/json"),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        benchmark = BenchmarkEvaluation(
            loop_id=run_id,
            suite_id="bounded-analytic",
            suite_version="1.0",
            candidate_ref=candidate_ref,
            selection_metrics={"score": raw_score},
            runtime_split_type=BenchmarkSplit.SELECTION,
            metadata={
                "params": {"x": x},
                "directions": {"score": direction},
                "warm_start_compatibility": compatibility,
                "evaluated_at": "2026-10-05T00:00:00+00:00",
            },
        )
        origin_ref = persist_benchmark_evaluation(store, benchmark)
        originals.append(benchmark)
        evaluations.append(
            Evaluation(
                candidate_id=str(candidate_ref.artifact_id),
                params={"x": x},
                params_normalized=(x,),
                objectives=[
                    ObjectiveValue(
                        name="score",
                        raw_value=raw_score,
                        direction=OptimizationDirection(direction),
                    )
                ],
                scalar_score=-raw_score if direction == "maximize" else raw_score,
                stage_a_passed=True,
                provenance_ref=str(origin_ref.artifact_id),
                timestamp=datetime(2026, 10, 5, tzinfo=UTC),
                metadata={"source_run_id": run_id, "warm_start_compatibility": compatibility},
            )
        )
    index = VectorMemoryStore(dim=2, max_elements=1200)
    writer = TransferLearningManager(store, index)
    fingerprint.history_ref = writer.register_run(fingerprint, evaluations)
    return store, index, space, fingerprint, evaluations, originals


@pytest.mark.parametrize("direction,expected_x", [("minimize", 0.1), ("maximize", 0.9)])
def test_persisted_native_transfer_ranking_and_lineage(tmp_path, direction, expected_x):
    store, index, _, source, _, _ = _measured_history(tmp_path, direction=direction)
    target = source.model_copy(update={"run_id": "target", "history_ref": None})
    manager = TransferLearningManager(store, index)
    result = WarmStartBridge(manager, max_evals=1).load_warm_start(target)
    assert len(result) == 1
    assert result[0].is_valid
    assert result[0].params == {"x": expected_x}
    assert result[0].timestamp == datetime(2026, 10, 5, tzinfo=UTC)
    assert result[0].metadata["source_history_ref"] == str(source.history_ref.artifact_id)
    assert asdict(manager.last_restore_report) == {
        "loaded_rows": 4,
        "accepted_rows": 4,
        "rejected_rows": 0,
        "selected_rows": 1,
        "excluded_run_ids": (),
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("space_hash", "different"),
        ("bounds", {"x": [0.0, 2.0]}),
        ("split", "hidden_holdout"),
        ("units", {"score": "other"}),
        ("origin", "changed-data-snapshot"),
        ("tenant_id", "other-tenant"),
        ("objective_directions", {"score": "maximize"}),
        ("origin", None),
    ],
)
def test_near_history_cannot_cross_a_changed_numeric_basis(tmp_path, field, value):
    store, index, _, source, _, _ = _measured_history(tmp_path)
    target = source.model_copy(update={"run_id": "target", field: value})
    manager = TransferLearningManager(store, index)
    assert manager.get_warm_start_evaluations([source], target_fingerprint=target) == []
    assert manager.last_restore_report.excluded_run_ids == ("source",)


def test_forged_discovery_binding_cannot_override_actual_cas_history(tmp_path):
    store, index, _, source, _, _ = _measured_history(tmp_path)
    forged = source.model_copy(update={"origin": "claimed-other-snapshot"})
    target = forged.model_copy(update={"run_id": "target"})
    manager = TransferLearningManager(store, index)
    with pytest.raises(TransferHistoryError, match="snapshot experiment binding differs"):
        manager.get_warm_start_evaluations([forged], target_fingerprint=target)


def test_rewritten_history_basis_cannot_relabel_the_original_measurement(tmp_path):
    store, index, _, source, evaluations, _ = _measured_history(tmp_path)
    source.origin = "rewritten-source-declaration"
    for evaluation in evaluations:
        evaluation.metadata["warm_start_compatibility"]["context_fingerprint"] = (
            source.numeric_context_fingerprint()
        )
    source.history_ref = TransferLearningManager(store, index).register_run(source, evaluations)
    target = source.model_copy(update={"run_id": "target"})
    reader = TransferLearningManager(store, index)
    restored = reader.get_warm_start_evaluations([source], target_fingerprint=target)
    assert all(not evaluation.is_valid for evaluation in restored)
    assert reader.last_restore_report.accepted_rows == 0
    assert reader.last_restore_report.rejected_rows == 4


def test_original_measurement_tampering_is_a_visible_rejection(tmp_path):
    store, index, _, source, evaluations, _ = _measured_history(tmp_path)
    evaluations[0].objectives = [
        ObjectiveValue(name="score", raw_value=999.0, direction=OptimizationDirection.MINIMIZE)
    ]
    evaluations[0].scalar_score = 999.0
    writer = TransferLearningManager(store, index)
    source.history_ref = writer.register_run(source, evaluations)
    target = source.model_copy(update={"run_id": "target"})
    reader = TransferLearningManager(store, index)
    restored = reader.get_warm_start_evaluations([source], target_fingerprint=target)
    rejected = [ev for ev in restored if not ev.is_valid]
    assert len(rejected) == 1
    assert "content does not match" in rejected[0].metadata["transfer_error"]
    assert reader.last_restore_report.accepted_rows == 3
    assert reader.last_restore_report.rejected_rows == 1


def test_changed_scalar_cannot_relabel_an_unchanged_benchmark(tmp_path):
    store, index, _, source, evaluations, _ = _measured_history(tmp_path)
    evaluations[0].scalar_score = -999.0
    source.history_ref = TransferLearningManager(store, index).register_run(source, evaluations)
    target = source.model_copy(update={"run_id": "target"})
    reader = TransferLearningManager(store, index)
    result = reader.get_warm_start_evaluations([source], target_fingerprint=target)
    rejected = [evaluation for evaluation in result if not evaluation.is_valid]
    assert len(rejected) == 1
    assert "scalarization" in rejected[0].metadata["transfer_error"]


def test_rejected_source_does_not_consume_a_valid_sources_numeric_quota(tmp_path):
    store, index, _, source, evaluations, _ = _measured_history(tmp_path)
    rejected_source = source.model_copy(update={"run_id": "rejected-source"})
    for evaluation in evaluations:
        evaluation.metadata["source_run_id"] = "rejected-source"
        evaluation.provenance_ref = None
    rejected_source.history_ref = TransferLearningManager(store, index).register_run(
        rejected_source, evaluations
    )
    target = source.model_copy(update={"run_id": "target"})
    reader = TransferLearningManager(store, index)
    result = reader.get_warm_start_evaluations(
        [rejected_source, source], max_evals=1, target_fingerprint=target
    )
    assert len(result) == 1 and result[0].is_valid
    assert result[0].metadata["source_run_id"] == "source"
    assert reader.last_restore_report.accepted_rows == 4
    assert reader.last_restore_report.rejected_rows == 4


def test_reverse_transfer_resolves_original_benchmark_and_refuses_fabrication(tmp_path):
    store, index, _, source, _, originals = _measured_history(tmp_path)
    target = source.model_copy(update={"run_id": "target"})
    restored = WarmStartBridge(TransferLearningManager(store, index)).load_warm_start(target)
    views = WarmStartBridge.evaluations_to_benchmarks(restored, loop_id="target", store=store)
    assert [view.loop_id for view in views] == ["source"] * 4
    assert [view.selection_metrics for view in views] == [b.selection_metrics for b in originals]
    assert all(view.holdout_metrics == {} and not view.promotable for view in views)
    assert all(
        view.metadata["source_benchmark_ref"] == ev.provenance_ref
        for view, ev in zip(views, restored, strict=True)
    )
    with pytest.raises(TransferHistoryError, match="store/reference"):
        WarmStartBridge.evaluations_to_benchmarks(restored, loop_id="target")
    restored[0].objectives = [
        ObjectiveValue(name="score", raw_value=123.0, direction=OptimizationDirection.MINIMIZE)
    ]
    with pytest.raises(TransferHistoryError, match="measurements differ"):
        WarmStartBridge.evaluations_to_benchmarks(restored, loop_id="target", store=store)


def test_exact_history_address_survives_a_native_catalog_over_one_thousand(tmp_path):
    store, index, _, source, _, _ = _measured_history(tmp_path)
    for offset in range(1001):
        angle = 0.01 + ((offset * 137) % 1001) / 1001 * 1.5
        index.add(
            f"distractor-{offset}",
            [math.cos(angle), math.sin(angle)],
            {"objective_names": ["unrelated"]},
        )
    real_query = index.query
    calls = []

    def counted_query(embedding, top_k):
        calls.append((embedding, top_k))
        return real_query(embedding, top_k)

    index.query = counted_query
    for top_k in (1, 3):
        reader = TransferLearningManager(store, index)
        target = source.model_copy(update={"run_id": f"target-{top_k}"})
        similar = reader.find_similar_runs(target, top_k=top_k)
        assert similar[0].history_ref == source.history_ref
        restored = reader.get_warm_start_evaluations(similar, target_fingerprint=target)
        assert len(restored) == 4 and all(ev.is_valid for ev in restored)
    assert len(calls) == 2
    assert all(embedding == [1.0, 0.0] for embedding, _ in calls)


@pytest.mark.parametrize("failure", ["unavailable", "corrupt", "schema"])
def test_bad_exact_snapshot_is_distinguished_and_never_replaced(tmp_path, failure):
    store, index, _, source, _, _ = _measured_history(tmp_path)
    if failure == "unavailable":
        from polisyos.core.artifacts.manifest import ArtifactRef

        ref = ArtifactRef(
            artifact_id=f"sha256:{'a' * 64}",
            kind="search.transfer.history",
            media_type="application/json",
        )
    else:
        ref = store.put_bytes(
            b"{" if failure == "corrupt" else b"{}",
            PutOptions(kind="search.transfer.history", media_type="application/json"),
        )
    broken = source.model_copy(update={"history_ref": ref})
    target = source.model_copy(update={"run_id": "target"})
    reader = TransferLearningManager(store, index)
    with pytest.raises(TransferHistoryError) as caught:
        reader.get_warm_start_evaluations([broken], target_fingerprint=target)
    assert caught.value.artifact_id == str(ref.artifact_id)
    assert {"unavailable": "unavailable", "corrupt": "corrupt", "schema": "evaluations list"}[
        failure
    ] in caught.value.reason


def test_history_consumer_mutation_cannot_change_cached_snapshot(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(
        json.dumps(
            {
                "run_id": "run",
                "evaluations": [
                    {
                        "candidate_id": "candidate",
                        "params": {"x": 0.5},
                        "params_normalized": [0.5],
                        "scalar_score": 1.0,
                        "stage_a_passed": True,
                        "status": "success",
                        "objectives": [
                            {"name": "score", "raw_value": 1.0, "direction": "minimize"}
                        ],
                        "metadata": {"source_run_id": "run", "binding": {"basis": "original"}},
                    }
                ],
            }
        ).encode(),
        PutOptions(kind="search.transfer.history", media_type="application/json"),
    )
    fingerprint = RunFingerprint(
        run_id="run", space_hash="space", objective_names=["score"], history_ref=ref
    )
    manager = TransferLearningManager(store, None)
    first = manager.get_warm_start_evaluations([fingerprint])[0]
    first.params["x"] = 0.9
    first.metadata["binding"]["basis"] = "mutated"
    second = manager.get_warm_start_evaluations([fingerprint])[0]
    cold = TransferLearningManager(store, None).get_warm_start_evaluations([fingerprint])[0]
    assert second.params == cold.params == {"x": 0.5}
    assert second.metadata["binding"] == cold.metadata["binding"] == {"basis": "original"}
