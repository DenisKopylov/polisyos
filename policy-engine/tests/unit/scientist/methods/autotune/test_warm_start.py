"""Tests for WarmStartBridge."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from polisyos.scientist.methods.autotune.models import BenchmarkSplit
from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies.transfer import (
    RunFingerprint,
    TransferLearningManager,
)
from polisyos.scientist.methods.search.strategies.types import Evaluation, EvaluationStatus


def _artifact_id(letter: str) -> str:
    return f"sha256:{letter * 64}"


def _make_eval(
    candidate_id: str,
    score: float,
    run_id: str = "",
    *,
    raw_score: float | None = None,
    direction: OptimizationDirection = OptimizationDirection.MINIMIZE,
    provenance_ref: str | None = None,
) -> Evaluation:
    return Evaluation(
        candidate_id=candidate_id,
        params={"x": 0.5},
        params_normalized=(0.5,),
        objectives=[
            ObjectiveValue(
                name="score",
                raw_value=score if raw_score is None else raw_score,
                direction=direction,
            )
        ],
        scalar_score=score,
        stage_a_passed=True,
        status=EvaluationStatus.SUCCESS,
        provenance_ref=provenance_ref,
        metadata={"source_run_id": run_id},
    )


def _fingerprint(run_id: str = "new_run") -> RunFingerprint:
    return RunFingerprint(
        run_id=run_id,
        space_hash="abc123",
        objective_names=["score"],
        embedding=[0.1, 0.2, 0.3],
    )


def _stored_eval(
    candidate_id: str,
    score: float,
    run_id: str,
    *,
    provenance_ref: str | None = None,
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "params": {"x": 0.5},
        "params_normalized": [0.5],
        "scalar_score": score,
        "stage_a_passed": True,
        "status": EvaluationStatus.SUCCESS.value,
        "objectives": [
            {
                "name": "score",
                "raw_value": score,
                "direction": OptimizationDirection.MINIMIZE.value,
            }
        ],
        "provenance_ref": provenance_ref or _artifact_id("p"),
        "metadata": {"source_run_id": run_id},
    }


def _manager_with_cache(rows_by_run: dict[str, list[dict[str, object]]]) -> TransferLearningManager:
    manager = object.__new__(TransferLearningManager)
    manager._eval_cache = rows_by_run
    return manager


class _MemoryArtifactStore:
    def __init__(self) -> None:
        self._payloads: dict[str, bytes] = {}

    def put_json(self, payload: dict[str, object], _options: object) -> SimpleNamespace:
        artifact_id = _artifact_id("h")
        self._payloads[artifact_id] = json.dumps(payload).encode("utf-8")
        return SimpleNamespace(artifact_id=artifact_id)

    def get_bytes(self, artifact_id: object) -> bytes:
        return self._payloads[str(artifact_id)]


class _MemoryVectorIndex:
    dim = 1

    def __init__(self) -> None:
        self._records: dict[str, dict[str, object]] = {}

    def add(self, *, key: str, embedding: list[float], metadata: dict[str, object]) -> None:
        del embedding
        self._records[key] = metadata

    def query(
        self, embedding: list[float], top_k: int
    ) -> list[tuple[str, float, dict[str, object]]]:
        del embedding
        return [(key, 0.0, metadata) for key, metadata in list(self._records.items())[:top_k]]


class TestWarmStartBridge:
    def test_loads_from_transfer_manager(self):
        manager = MagicMock()
        similar = [
            RunFingerprint(run_id="old1", space_hash="x", objective_names=["score"]),
        ]
        manager.find_similar_runs.return_value = similar
        manager.get_warm_start_evaluations.return_value = [
            _make_eval("c1", 0.8, "old1"),
            _make_eval("c2", 0.6, "old1"),
        ]

        bridge = WarmStartBridge(manager, max_evals=10)
        evals = bridge.load_warm_start(_fingerprint())
        assert len(evals) == 2
        manager.find_similar_runs.assert_called_once()

    def test_no_similar_runs(self):
        manager = MagicMock()
        manager.find_similar_runs.return_value = []
        bridge = WarmStartBridge(manager)
        evals = bridge.load_warm_start(_fingerprint())
        assert evals == []

    def test_partial_data(self):
        manager = MagicMock()
        manager.find_similar_runs.return_value = [
            RunFingerprint(run_id="old", space_hash="x", objective_names=["score"]),
        ]
        manager.get_warm_start_evaluations.return_value = [_make_eval("c1", 0.9)]
        bridge = WarmStartBridge(manager, max_evals=1)
        evals = bridge.load_warm_start(_fingerprint())
        assert len(evals) == 1

    def test_evaluations_to_benchmarks(self):
        candidate_id = _artifact_id("c")
        provenance_ref = _artifact_id("e")
        second_candidate_id = _artifact_id("d")
        second_provenance_ref = _artifact_id("f")
        evals = [
            _make_eval(candidate_id, 0.8, "run1", provenance_ref=provenance_ref),
            _make_eval(
                second_candidate_id,
                0.6,
                "run1",
                provenance_ref=second_provenance_ref,
            ),
        ]
        benchmarks = WarmStartBridge.evaluations_to_benchmarks(
            evals,
            loop_id="loop1",
            primary_metric="score",
        )
        assert len(benchmarks) == 2
        candidate_refs = {str(benchmark.candidate_ref.artifact_id) for benchmark in benchmarks}
        assert candidate_refs == {candidate_id, second_candidate_id}
        assert all(
            ref != f"sha256:{'0' * 64}"
            for ref in candidate_refs
        )
        benchmark = benchmarks[0]
        assert benchmark.loop_id == "loop1"
        assert str(benchmark.candidate_ref.artifact_id) == candidate_id
        assert benchmark.selection_metrics == {"score": 0.8}
        assert benchmark.holdout_metrics == {}
        assert benchmark.runtime_split_type is BenchmarkSplit.SELECTION
        assert benchmark.promotable is False
        assert benchmark.status == "warm_start_limited"
        assert benchmark.metadata["params"] == {"x": 0.5}
        assert benchmark.metadata["source_candidate_id"] == candidate_id
        assert benchmark.metadata["provenance_ref"] == provenance_ref
        assert benchmarks[1].metadata["provenance_ref"] == second_provenance_ref
        assert benchmarks[1].holdout_metrics == {}

    def test_evaluations_to_benchmarks_preserves_raw_maximize_value(self):
        candidate_id = _artifact_id("m")
        evaluation = _make_eval(
            candidate_id,
            -0.8,
            "run1",
            raw_score=0.8,
            direction=OptimizationDirection.MAXIMIZE,
        )

        benchmark = WarmStartBridge.evaluations_to_benchmarks(
            [evaluation],
            loop_id="loop1",
            primary_metric="score",
        )[0]

        assert benchmark.selection_metrics == {"score": 0.8}
        assert benchmark.metadata["direction"] == OptimizationDirection.MAXIMIZE.value


class TestTransferLearningManagerWarmStart:
    def test_register_run_persistence_rehydrates_native_fields(self):
        candidate_id = _artifact_id("a")
        provenance_ref = _artifact_id("b")
        evaluation = _make_eval(
            candidate_id,
            0.8,
            "old1",
            provenance_ref=provenance_ref,
        )
        evaluation.metadata["evidence_kind"] = "measured"
        fingerprint = RunFingerprint(
            run_id="old1",
            space_hash="space-v1",
            objective_names=["score"],
            bounds={"x": [0.0, 1.0]},
            split="selection",
            units={"score": "points"},
            origin="simulator-v1",
            tenant_id="tenant-a",
            embedding=[0.1],
        )
        store = _MemoryArtifactStore()
        index = _MemoryVectorIndex()
        writer = TransferLearningManager(store, index)
        writer.register_run(fingerprint, [evaluation])

        reader = TransferLearningManager(store, index)
        source = fingerprint.model_copy(update={"embedding": []})

        evaluations = reader.get_warm_start_evaluations(
            [source],
            max_evals=1,
            target_fingerprint=fingerprint,
        )

        assert len(evaluations) == 1
        evaluation = evaluations[0]
        assert evaluation.candidate_id == candidate_id
        assert evaluation.provenance_ref == provenance_ref
        assert evaluation.metadata["source_run_id"] == "old1"
        assert evaluation.metadata["evidence_kind"] == "measured"
        assert evaluation.objectives[0].name == "score"
        assert evaluation.objectives[0].raw_value == 0.8
        assert evaluation.objectives[0].direction is OptimizationDirection.MINIMIZE

    def test_selects_lowest_normalized_score_first(self):
        lower_id = _artifact_id("l")
        higher_id = _artifact_id("h")
        manager = _manager_with_cache(
            {
                "old1": [
                    _stored_eval(higher_id, 9.0, "old1"),
                    _stored_eval(lower_id, 1.0, "old1"),
                ]
            }
        )

        evaluations = manager.get_warm_start_evaluations(
            [RunFingerprint(run_id="old1", space_hash="x", objective_names=["score"])],
            max_evals=1,
        )

        assert [evaluation.candidate_id for evaluation in evaluations] == [lower_id]

    def test_redistributes_unused_per_run_quota(self):
        first_id = _artifact_id("1")
        second_id = _artifact_id("2")
        third_id = _artifact_id("3")
        fourth_id = _artifact_id("4")
        manager = _manager_with_cache(
            {
                "short": [_stored_eval(first_id, 1.0, "short")],
                "long": [
                    _stored_eval(second_id, 2.0, "long"),
                    _stored_eval(third_id, 3.0, "long"),
                    _stored_eval(fourth_id, 4.0, "long"),
                ],
            }
        )

        evaluations = manager.get_warm_start_evaluations(
            [
                RunFingerprint(run_id="short", space_hash="x", objective_names=["score"]),
                RunFingerprint(run_id="long", space_hash="x", objective_names=["score"]),
            ],
            max_evals=4,
        )

        assert len(evaluations) == 4
        assert {evaluation.candidate_id for evaluation in evaluations} == {
            first_id,
            second_id,
            third_id,
            fourth_id,
        }

    def test_malformed_row_is_reported_instead_of_silently_dropped(self):
        candidate_id = _artifact_id("r")
        malformed = _stored_eval(candidate_id, 0.8, "old1")
        malformed["objectives"] = [{"name": "score", "raw_value": 0.8}]
        manager = _manager_with_cache({"old1": [malformed]})

        evaluations = manager.get_warm_start_evaluations(
            [RunFingerprint(run_id="old1", space_hash="x", objective_names=["score"])],
            max_evals=1,
        )

        assert len(evaluations) == 1
        assert evaluations[0].is_valid is False
        assert evaluations[0].metadata["transfer_status"] == "rejected"
        assert evaluations[0].metadata["source_candidate_id"] == candidate_id
        assert "direction" in evaluations[0].metadata["transfer_error"]

    def test_similar_objectives_do_not_override_space_binding(self):
        target = RunFingerprint(
            run_id="new1",
            space_hash="space-v1",
            objective_names=["score"],
            bounds={"x": [0.0, 1.0]},
            split="selection",
            units={"score": "points"},
            origin="simulator-v1",
            tenant_id="tenant-a",
            embedding=[0.1],
        )

        mismatches = {
            "space_hash": "old-bounds",
            "bounds": {"x": [-1.0, 1.0]},
            "units": {"score": "percent"},
            "split": "holdout",
            "origin": "simulator-v2",
            "tenant_id": "tenant-b",
        }
        for field, value in mismatches.items():
            source_metadata = {
                "space_hash": target.space_hash,
                "objective_names": target.objective_names,
                "bounds": target.bounds,
                "split": target.split,
                "units": target.units,
                "origin": target.origin,
                "tenant_id": target.tenant_id,
                "objective_directions": target.objective_directions,
                "best_score": 0.1,
            }
            source_metadata[field] = value

            class Index:
                dim = 1

                def query(self, embedding, top_k):
                    del embedding, top_k
                    return [("old1", 0.01, source_metadata)]

            manager = object.__new__(TransferLearningManager)
            manager._index = Index()
            assert manager.find_similar_runs(target) == [], field
