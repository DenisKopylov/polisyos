"""Tests for WarmStartBridge."""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.methods.autotune.models import BenchmarkSplit
from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    GDPGrowthObjective,
    ObjectiveScoreStatus,
    ObjectiveValue,
    OptimizationDirection,
    configured_objective_rule_spec,
)
from polisyos.scientist.methods.search.strategies.multi_objective import MOBayesianOptimizer
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
    value = score if raw_score is None else raw_score
    source = (
        {"gdp_change": value, "metric_units": {"gdp_change": "points"}}
        if direction is OptimizationDirection.MAXIMIZE
        else {"budget_deficit": abs(value), "metric_units": {"budget_deficit": "points"}}
    )
    configured = (
        GDPGrowthObjective(expected_unit="points")
        if direction is OptimizationDirection.MAXIMIZE
        else BudgetDeficitObjective(expected_unit="points")
    ).evaluate(source)
    objective = ObjectiveValue(
        name="score",
        raw_value=float(configured.raw_value),
        direction=direction,
        weight=configured.weight,
        is_satisfied=configured.is_satisfied,
        threshold=configured.threshold,
        score_status=configured.score_status,
        score_assessment=configured.score_assessment,
    )
    return Evaluation(
        candidate_id=candidate_id,
        params={"x": 0.5},
        params_normalized=(0.5,),
        objectives=[objective],
        scalar_score=float(configured.raw_value),
        stage_a_passed=True,
        stage_b_result=source,
        status=EvaluationStatus.SUCCESS,
        provenance_ref=provenance_ref,
        metadata={"source_run_id": run_id},
        score_status=configured.score_status,
        score_assessment=configured.score_assessment,
    )


def _fingerprint(run_id: str = "new_run") -> RunFingerprint:
    return RunFingerprint(
        run_id=run_id,
        space_hash="abc123",
        objective_names=["score"],
        embedding=[0.1, 0.2, 0.3],
    )


def _complete_fingerprint(run_id: str, *, embedding: list[float]) -> RunFingerprint:
    return RunFingerprint(
        run_id=run_id,
        space_hash="space-v1",
        objective_names=["score"],
        bounds={"x": [0.0, 1.0]},
        split="selection",
        units={"score": "points"},
        origin="simulator-v1",
        tenant_id="tenant-a",
        objective_directions={"score": OptimizationDirection.MINIMIZE.value},
        objective_rule_specs={
            "score": configured_objective_rule_spec(BudgetDeficitObjective(expected_unit="points"))
            or ""
        },
        embedding=embedding,
    )


def _stored_eval(
    candidate_id: str,
    score: float,
    run_id: str,
    *,
    provenance_ref: str | None = None,
) -> dict[str, object]:
    source = {
        "budget_deficit": score,
        "metric_units": {"budget_deficit": "points"},
    }
    objective = BudgetDeficitObjective(expected_unit="points").evaluate(source)
    assert objective.score_assessment is not None
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
                "score_status": ObjectiveScoreStatus.AVAILABLE.value,
                "score_assessment": objective.score_assessment.to_payload(),
            }
        ],
        "score_status": ObjectiveScoreStatus.AVAILABLE.value,
        "score_assessment": objective.score_assessment.to_payload(),
        "stage_b_result": source,
        "provenance_ref": provenance_ref or _artifact_id("p"),
        "metadata": {"source_run_id": run_id},
    }


def _history_document(
    fingerprint: RunFingerprint,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    identity_fields = (
        "run_id",
        "space_hash",
        "objective_names",
        "bounds",
        "split",
        "units",
        "origin",
        "tenant_id",
        "objective_directions",
        "objective_rule_specs",
    )
    return {
        "history_schema_version": "5",
        **{field: getattr(fingerprint, field) for field in identity_fields},
        "evaluations": rows,
    }


class _CountingArtifactStore:
    def __init__(self, store: FileSystemCAS) -> None:
        self.store = store
        self.payload_reads: list[object] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self.store, name)

    def get_bytes(self, selector: Any) -> bytes:
        self.payload_reads.append(selector)
        return self.store.get_bytes(selector)


def _manager_with_history(
    tmp_path,
    rows_by_run: dict[str, list[dict[str, object]]],
) -> tuple[TransferLearningManager, dict[str, RunFingerprint]]:
    store = FileSystemCAS(tmp_path / "cas")
    counted_store = _CountingArtifactStore(store)
    sources: dict[str, RunFingerprint] = {}
    for run_id, rows in rows_by_run.items():
        source = _complete_fingerprint(run_id, embedding=[0.1])
        history_ref = store.put_json(
            _history_document(source, rows),
            PutOptions(kind="search.transfer.history", media_type="application/json"),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        source.history_ref = history_ref
        sources[run_id] = source
    return TransferLearningManager(counted_store, _MemoryVectorIndex()), sources


class _MemoryVectorIndex:
    dim = 1

    def __init__(self) -> None:
        self._records: dict[str, dict[str, object]] = {}

    def add(self, *, key: str, embedding: list[float], metadata: dict[str, object]) -> None:
        del embedding
        self._records[key] = metadata

    def lookup_metadata(self, key: str) -> dict[str, object] | None:
        return self._records.get(key)

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
        assert (
            WarmStartBridge.evaluations_to_benchmarks(
                evals,
                loop_id="loop1",
                primary_metric="score",
            )
            == []
        )
        assert (
            WarmStartBridge.evaluations_to_benchmarks(
                evals,
                loop_id="loop1",
                primary_metric="score",
                objective_direction=OptimizationDirection.MINIMIZE,
                objective_rule_spec=configured_objective_rule_spec(
                    GDPGrowthObjective(expected_unit="points")
                ),
            )
            == []
        )
        benchmarks = WarmStartBridge.evaluations_to_benchmarks(
            evals,
            loop_id="loop1",
            primary_metric="score",
            objective_direction=OptimizationDirection.MINIMIZE,
            objective_rule_spec=configured_objective_rule_spec(
                BudgetDeficitObjective(expected_unit="points")
            ),
        )
        assert len(benchmarks) == 2
        candidate_refs = {str(benchmark.candidate_ref.artifact_id) for benchmark in benchmarks}
        assert candidate_refs == {candidate_id, second_candidate_id}
        assert all(ref != f"sha256:{'0' * 64}" for ref in candidate_refs)
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
        candidate_id = _artifact_id("9")
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
            objective_direction=OptimizationDirection.MAXIMIZE,
            objective_rule_spec=configured_objective_rule_spec(
                GDPGrowthObjective(expected_unit="points")
            ),
        )[0]

        assert benchmark.selection_metrics == {"score": 0.8}
        assert benchmark.metadata["direction"] == OptimizationDirection.MAXIMIZE.value


class TestTransferLearningManagerWarmStart:
    def test_register_run_persistence_rehydrates_native_fields(self, tmp_path):
        candidate_id = _artifact_id("a")
        provenance_ref = _artifact_id("b")
        evaluation = _make_eval(
            candidate_id,
            0.8,
            "old1",
            provenance_ref=provenance_ref,
        )
        evaluation.metadata["evidence_kind"] = "measured"
        fingerprint = _complete_fingerprint("old1", embedding=[0.1])
        store = FileSystemCAS(tmp_path / "cas")
        index = _MemoryVectorIndex()
        writer = TransferLearningManager(store, index)
        history_ref = writer.register_run(fingerprint, [evaluation])

        assert history_ref is not None
        assert history_ref.manifest_profile_sha256 is not None
        assert (
            index._records["old1"]["manifest_profile_sha256"] == history_ref.manifest_profile_sha256
        )

        reader = TransferLearningManager(store, index)
        source = fingerprint.model_copy(update={"embedding": []})
        evaluations = reader.get_warm_start_evaluations(
            [source],
            max_evals=1,
            target_fingerprint=fingerprint,
        )

        assert len(evaluations) == 1
        result = evaluations[0]
        assert result.candidate_id == candidate_id
        assert result.provenance_ref == provenance_ref
        assert result.metadata["source_run_id"] == "old1"
        assert result.metadata["evidence_kind"] == "measured"
        assert result.objectives[0].name == "score"
        assert result.objectives[0].raw_value == 0.8
        assert result.objectives[0].direction is OptimizationDirection.MINIMIZE

    def test_indexed_history_positive_reconciles_full_header_before_warm_start(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        index = _MemoryVectorIndex()
        writer = TransferLearningManager(store, index)
        source = _complete_fingerprint("source-run", embedding=[0.1])
        candidate_id = _artifact_id("7")
        history_ref = writer.register_run(source, [_make_eval(candidate_id, 0.8, "source-run")])
        assert history_ref is not None

        target = source.model_copy(update={"run_id": "target-run"})
        warm_start = WarmStartBridge(TransferLearningManager(store, index)).load_warm_start(target)

        assert len(warm_start) == 1
        assert warm_start[0].candidate_id == candidate_id
        assert warm_start[0].metadata["source_run_id"] == "source-run"

    @pytest.mark.parametrize(
        ("field", "replacement"),
        [
            ("run_id", "other-run"),
            ("space_hash", "other-space"),
            ("objective_names", ["score", "other-score"]),
            ("bounds", {"x": [-1.0, 1.0]}),
            ("split", "holdout"),
            ("units", {"score": "percent"}),
            ("origin", "other-simulator"),
            ("tenant_id", "other-tenant"),
            ("objective_directions", {"score": OptimizationDirection.MAXIMIZE.value}),
            (
                "objective_rule_specs",
                {
                    "score": configured_objective_rule_spec(
                        GDPGrowthObjective(expected_unit="points")
                    )
                },
            ),
        ],
    )
    def test_indexed_history_payload_header_must_match_selected_index(
        self, tmp_path, field, replacement
    ):
        store = FileSystemCAS(tmp_path / "cas")
        index = _MemoryVectorIndex()
        writer = TransferLearningManager(store, index)
        source = _complete_fingerprint("source-run", embedding=[0.1])
        history_ref = writer.register_run(
            source, [_make_eval(_artifact_id("8"), 0.8, "source-run")]
        )
        assert history_ref is not None

        mutated = from_canonical_bytes(store.get_bytes(history_ref))
        mutated[field] = replacement
        replacement_ref = store.put_json(
            mutated,
            PutOptions(kind="search.transfer.history", media_type="application/json"),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        assert replacement_ref.artifact_id != history_ref.artifact_id
        # Keep index claims stable while selecting a separately content-addressed payload.
        index._records["source-run"]["artifact_id"] = replacement_ref.artifact_id
        index._records["source-run"]["manifest_profile_sha256"] = (
            replacement_ref.manifest_profile_sha256
        )

        reader = TransferLearningManager(store, index)
        target = source.model_copy(update={"run_id": "target-run"})
        selected = reader.find_similar_runs(target)
        assert len(selected) == 1
        with pytest.raises(ValueError, match=field):
            reader.get_warm_start_evaluations(selected, max_evals=1, target_fingerprint=target)

    def test_malformed_present_header_field_is_not_defaulted(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        index = _MemoryVectorIndex()
        writer = TransferLearningManager(store, index)
        source = _complete_fingerprint("source-run", embedding=[0.1])
        history_ref = writer.register_run(
            source, [_make_eval(_artifact_id("9"), 0.8, "source-run")]
        )
        assert history_ref is not None

        malformed = from_canonical_bytes(store.get_bytes(history_ref))
        malformed["tenant_id"] = ["tenant-a"]
        replacement_ref = store.put_json(
            malformed,
            PutOptions(kind="search.transfer.history", media_type="application/json"),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        index._records["source-run"]["artifact_id"] = replacement_ref.artifact_id
        index._records["source-run"]["manifest_profile_sha256"] = (
            replacement_ref.manifest_profile_sha256
        )

        target = source.model_copy(update={"run_id": "target-run"})
        reader = TransferLearningManager(store, index)
        with pytest.raises(ValueError, match="tenant_id"):
            reader.get_warm_start_evaluations(
                reader.find_similar_runs(target), max_evals=1, target_fingerprint=target
            )

    def test_incomplete_explicit_fingerprint_cannot_be_indexed_for_transfer(self):
        writer = TransferLearningManager(object(), _MemoryVectorIndex())
        incomplete = RunFingerprint(
            run_id="source-run", space_hash="space-v1", objective_names=["score"], embedding=[0.1]
        )
        with pytest.raises(ValueError, match="complete run fingerprint"):
            writer.register_run(incomplete, [_make_eval(_artifact_id("6"), 0.8, "source-run")])

    def test_warm_start_requires_complete_target_before_history_read(self, tmp_path):
        manager, sources = _manager_with_history(
            tmp_path,
            {"source-run": [_stored_eval(_artifact_id("t"), 0.8, "source-run")]},
        )
        source = sources["source-run"]
        store = manager._store

        with pytest.raises(TypeError):
            manager.get_warm_start_evaluations([source], max_evals=1)
        assert (
            manager.get_warm_start_evaluations([source], max_evals=1, target_fingerprint=None) == []
        )
        assert store.payload_reads == []

        incomplete = RunFingerprint(
            run_id="target-run",
            space_hash=source.space_hash,
            objective_names=list(source.objective_names),
        )
        assert (
            manager.get_warm_start_evaluations(
                [source],
                max_evals=1,
                target_fingerprint=incomplete,
            )
            == []
        )
        malformed = source.model_copy(update={"tenant_id": ["tenant-a"]})
        assert (
            manager.get_warm_start_evaluations(
                [source],
                max_evals=1,
                target_fingerprint=malformed,
            )
            == []
        )
        cross_tenant = source.model_copy(update={"run_id": "target-run", "tenant_id": "tenant-b"})
        assert (
            manager.get_warm_start_evaluations(
                [source],
                max_evals=1,
                target_fingerprint=cross_tenant,
            )
            == []
        )
        assert store.payload_reads == []

        target = source.model_copy(update={"run_id": "target-run"})
        evaluations = manager.get_warm_start_evaluations(
            [source],
            max_evals=1,
            target_fingerprint=target,
        )

        assert [evaluation.candidate_id for evaluation in evaluations] == [_artifact_id("t")]
        assert store.payload_reads == [source.history_ref]

    def test_selects_lowest_normalized_score_first(self, tmp_path):
        lower_id = _artifact_id("l")
        higher_id = _artifact_id("h")
        manager, sources = _manager_with_history(
            tmp_path,
            {
                "old1": [
                    _stored_eval(higher_id, 9.0, "old1"),
                    _stored_eval(lower_id, 1.0, "old1"),
                ]
            },
        )

        evaluations = manager.get_warm_start_evaluations(
            [sources["old1"]],
            max_evals=1,
            target_fingerprint=sources["old1"],
        )

        assert [evaluation.candidate_id for evaluation in evaluations] == [lower_id]

    def test_redistributes_unused_per_run_quota(self, tmp_path):
        first_id = _artifact_id("1")
        second_id = _artifact_id("2")
        third_id = _artifact_id("3")
        fourth_id = _artifact_id("4")
        manager, sources = _manager_with_history(
            tmp_path,
            {
                "short": [_stored_eval(first_id, 1.0, "short")],
                "long": [
                    _stored_eval(second_id, 2.0, "long"),
                    _stored_eval(third_id, 3.0, "long"),
                    _stored_eval(fourth_id, 4.0, "long"),
                ],
            },
        )

        target = _complete_fingerprint("target-run", embedding=[])
        evaluations = manager.get_warm_start_evaluations(
            [sources["short"], sources["long"]],
            max_evals=4,
            target_fingerprint=target,
        )

        assert len(evaluations) == 4
        assert {evaluation.candidate_id for evaluation in evaluations} == {
            first_id,
            second_id,
            third_id,
            fourth_id,
        }

    def test_malformed_row_is_reported_instead_of_silently_dropped(self, tmp_path):
        candidate_id = _artifact_id("r")
        malformed = _stored_eval(candidate_id, 0.8, "old1")
        malformed["objectives"] = [{"name": "score", "raw_value": 0.8}]
        manager, sources = _manager_with_history(
            tmp_path,
            {"old1": [malformed]},
        )

        evaluations = manager.get_warm_start_evaluations(
            [sources["old1"]],
            max_evals=1,
            target_fingerprint=sources["old1"],
        )

        assert len(evaluations) == 1
        assert evaluations[0].is_valid is False
        assert evaluations[0].metadata["transfer_status"] == "rejected"
        assert evaluations[0].metadata["source_candidate_id"] == candidate_id
        assert "direction" in evaluations[0].metadata["transfer_error"]

    def test_history_cache_refuses_changed_selected_blob(self, tmp_path):
        manager, sources = _manager_with_history(
            tmp_path, {"source": [_stored_eval(_artifact_id("a"), 0.8, "source")]}
        )
        source = sources["source"]
        assert manager.get_warm_start_evaluations([source], target_fingerprint=source)
        assert manager._eval_cache
        blob, _ = manager._store.store._paths(source.history_ref.artifact_id)
        blob.write_bytes(b"changed history bytes while preserving its selected manifest")
        with pytest.raises(ValueError, match="live CAS verification failed"):
            manager.get_warm_start_evaluations([source], target_fingerprint=source)
        assert not manager._eval_cache

    def test_history_cache_identity_includes_selected_manifest_profile(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        source = _complete_fingerprint("source-run", embedding=[0.1])
        rows = [_stored_eval(_artifact_id("p"), 0.8, "source-run")]
        payload = _history_document(source, rows)
        opts = PutOptions(kind="search.transfer.history", media_type="application/json")
        first_ref = store.put_json(
            payload,
            opts,
            canon_spec=CanonSpec(forbid_floats=False, max_depth=64),
            return_selected_profile=True,
        )
        second_ref = store.put_json(
            payload,
            opts,
            canon_spec=CanonSpec(forbid_floats=False, max_depth=63),
            return_selected_profile=True,
        )
        assert first_ref.artifact_id == second_ref.artifact_id
        assert first_ref.manifest_profile_sha256 != second_ref.manifest_profile_sha256

        counted_store = _CountingArtifactStore(store)
        manager = TransferLearningManager(counted_store, _MemoryVectorIndex())
        first_view = source.model_copy(update={"history_ref": first_ref})
        second_view = source.model_copy(update={"history_ref": second_ref})

        with pytest.raises(ValueError, match="duplicate source run"):
            manager.get_warm_start_evaluations(
                [first_view, second_view], max_evals=2, target_fingerprint=source
            )

        assert [
            row.candidate_id
            for row in manager.get_warm_start_evaluations(
                [first_view], max_evals=1, target_fingerprint=source
            )
        ] == [_artifact_id("p")]
        assert [
            row.candidate_id
            for row in manager.get_warm_start_evaluations(
                [second_view], max_evals=1, target_fingerprint=source
            )
        ] == [_artifact_id("p")]
        manager.get_warm_start_evaluations([first_view], max_evals=1, target_fingerprint=source)

        assert len(manager._eval_cache) == 2
        assert counted_store.payload_reads == [first_ref, second_ref]

    def test_history_cache_uses_lru_order_and_measured_byte_total(self, tmp_path, monkeypatch):
        monkeypatch.setattr(TransferLearningManager, "_MAX_HISTORY_CACHE_ENTRIES", 2)
        manager, sources = _manager_with_history(
            tmp_path,
            {
                run_id: [_stored_eval(_artifact_id(letter), 0.8, run_id)]
                for run_id, letter in (("first", "a"), ("second", "b"), ("third", "c"))
            },
        )

        for run_id in ("first", "second", "first", "third"):
            manager.get_warm_start_evaluations(
                [sources[run_id]], max_evals=1, target_fingerprint=sources[run_id]
            )

        first_ref = sources["first"].history_ref
        second_ref = sources["second"].history_ref
        third_ref = sources["third"].history_ref
        assert first_ref is not None and second_ref is not None and third_ref is not None
        first_key = manager._history_cache_key(first_ref, sources["first"])
        second_key = manager._history_cache_key(second_ref, sources["second"])
        third_key = manager._history_cache_key(third_ref, sources["third"])
        assert tuple(manager._eval_cache) == (first_key, third_key)
        assert second_key not in manager._eval_cache
        assert len(manager._eval_cache) <= 2
        assert manager._eval_cache_bytes == sum(
            len(payload) for payload in manager._eval_cache.values()
        )
        assert manager._eval_cache_bytes <= manager._MAX_HISTORY_CACHE_BYTES

        manager.get_warm_start_evaluations(
            [sources["second"]], max_evals=1, target_fingerprint=sources["second"]
        )
        assert manager._eval_cache_bytes == sum(
            len(payload) for payload in manager._eval_cache.values()
        )
        assert len(manager._eval_cache) <= 2
        assert len(manager._store.payload_reads) == 4

    def test_history_cache_evicts_to_stay_within_aggregate_byte_budget(
        self,
        tmp_path,
        monkeypatch,
    ):
        manager, sources = _manager_with_history(
            tmp_path,
            {
                "first": [_stored_eval(_artifact_id("a"), 0.8, "first")],
                "second": [_stored_eval(_artifact_id("b"), 0.8, "second")],
            },
        )
        first_ref = sources["first"].history_ref
        second_ref = sources["second"].history_ref
        assert first_ref is not None and second_ref is not None
        first_size = len(manager._store.store.get_bytes(first_ref))
        second_size = len(manager._store.store.get_bytes(second_ref))
        byte_budget = max(first_size, second_size) + 1
        assert first_size + second_size > byte_budget
        monkeypatch.setattr(TransferLearningManager, "_MAX_HISTORY_CACHE_BYTES", byte_budget)

        manager.get_warm_start_evaluations(
            [sources["first"]], max_evals=1, target_fingerprint=sources["first"]
        )
        manager.get_warm_start_evaluations(
            [sources["second"]], max_evals=1, target_fingerprint=sources["second"]
        )

        first_key = manager._history_cache_key(first_ref, sources["first"])
        second_key = manager._history_cache_key(second_ref, sources["second"])
        assert first_key not in manager._eval_cache
        assert tuple(manager._eval_cache) == (second_key,)
        assert manager._eval_cache_bytes == second_size
        assert manager._eval_cache_bytes <= byte_budget

    def test_history_cache_bypasses_oversized_verified_payload(self, tmp_path, monkeypatch):
        monkeypatch.setattr(TransferLearningManager, "_MAX_HISTORY_CACHE_BYTES", 512)
        large_row = _stored_eval(_artifact_id("d"), 0.8, "large-run")
        large_row["metadata"]["large_value"] = "x" * 2048
        manager, sources = _manager_with_history(
            tmp_path,
            {"large-run": [large_row]},
        )
        source = sources["large-run"]
        assert source.history_ref is not None
        payload_size = len(manager._store.store.get_bytes(source.history_ref))
        assert payload_size > manager._MAX_HISTORY_CACHE_BYTES

        for _ in range(2):
            manager.get_warm_start_evaluations([source], max_evals=1, target_fingerprint=source)

        assert manager._eval_cache == {}
        assert manager._eval_cache_bytes == 0
        assert manager._store.payload_reads == [source.history_ref, source.history_ref]

    def test_history_cache_resource_limits_are_explicit(self):
        assert TransferLearningManager._MAX_HISTORY_CACHE_ENTRIES == 128
        assert TransferLearningManager._MAX_HISTORY_CACHE_BYTES == 32 * 1024 * 1024

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
            objective_directions={"score": OptimizationDirection.MINIMIZE.value},
            objective_rule_specs={
                "score": configured_objective_rule_spec(
                    BudgetDeficitObjective(expected_unit="points")
                )
                or ""
            },
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
        managers = []
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
                "objective_rule_specs": target.objective_rule_specs,
                "best_score": 0.1,
            }
            source_metadata[field] = value

            class Index:
                dim = 1

                def __init__(self, metadata):
                    self.metadata = metadata

                def query(self, embedding, top_k):
                    del embedding, top_k
                    return [("old1", 0.01, self.metadata)]

            manager = object.__new__(TransferLearningManager)
            manager._index = Index(source_metadata)
            managers.append((field, manager))

        # Query after the loop so each index must retain its own cohort metadata.
        # A method that closes over ``source_metadata`` would see only the last row.
        for field, manager in managers:
            assert manager.find_similar_runs(target) == [], field


def test_transfer_and_mo_accept_arbitrary_label_when_selected_rule_matches(tmp_path) -> None:
    source = {"gdp_change": 0.8, "metric_units": {"gdp_change": "points"}}
    configured = GDPGrowthObjective(expected_unit="points").evaluate(source)
    selected = ObjectiveValue(
        name="score",
        raw_value=configured.raw_value,
        direction=configured.direction,
        score_status=configured.score_status,
        score_assessment=configured.score_assessment,
    )
    evaluation = Evaluation(
        candidate_id="configured-custom-label",
        params={"x": 0.25},
        params_normalized=(0.25,),
        objectives=[selected],
        scalar_score=configured.raw_value,
        stage_a_passed=True,
        stage_b_result=source,
        score_status=configured.score_status,
        score_assessment=configured.score_assessment,
    )
    rule_spec = configured_objective_rule_spec(GDPGrowthObjective(expected_unit="points")) or ""
    fingerprint = RunFingerprint(
        run_id="configured-source-run",
        space_hash="space-v1",
        objective_names=["score"],
        bounds={"x": [0.0, 1.0]},
        split="selection",
        units={"score": "points"},
        origin="configured-candidate",
        tenant_id="tenant-a",
        objective_directions={"score": OptimizationDirection.MAXIMIZE.value},
        objective_rule_specs={"score": rule_spec},
        embedding=[0.1],
    )
    assert TransferLearningManager._has_complete_binding_basis(fingerprint)
    assert not TransferLearningManager._has_complete_binding_basis(
        fingerprint.model_copy(update={"units": {}})
    )
    assert not TransferLearningManager._has_complete_binding_basis(
        fingerprint.model_copy(update={"units": {"score": "other-points"}})
    )
    wrong_source_unit = replace(
        evaluation,
        stage_b_result={
            **source,
            "metric_units": {"gdp_change": "other-points"},
        },
    )
    assert not TransferLearningManager._evaluation_matches_fingerprint(
        wrong_source_unit, fingerprint
    )

    index = _MemoryVectorIndex()
    store = FileSystemCAS(tmp_path / "cas")
    writer = TransferLearningManager(store, index)
    assert writer.register_run(fingerprint, [evaluation]) is not None
    target = fingerprint.model_copy(update={"run_id": "configured-target-run"})
    transferred = TransferLearningManager(store, index).get_warm_start_evaluations(
        [fingerprint], max_evals=1, target_fingerprint=target
    )
    assert len(transferred) == 1 and transferred[0].is_valid

    optimizer = object.__new__(MOBayesianOptimizer)
    optimizer._objective_names = ["score"]
    optimizer._directions = [OptimizationDirection.MAXIMIZE]
    optimizer._objective_rule_specs = {"score": rule_spec}
    optimizer._negate_mask = [-1.0]
    assert optimizer._has_complete_objective_basis(transferred[0])
    assert optimizer._objective_vector(transferred[0]) == [-0.8]


def test_transfer_restore_and_mo_reject_coordinate_rule_mismatch(tmp_path) -> None:
    source = {
        "gdp_change": 0.0,
        "gov_balance": -100.0,
        "budget_deficit": 100.0,
        "metric_units": {
            "gdp_change": "points",
            "gov_balance": "points",
            "budget_deficit": "points",
        },
    }
    gdp = GDPGrowthObjective(expected_unit="points").evaluate(source)
    assert gdp.score_assessment is not None
    wrong_coordinate = ObjectiveValue(
        name="budget_deficit",
        raw_value=gdp.raw_value,
        direction=gdp.direction,
        score_status=gdp.score_status,
        score_assessment=gdp.score_assessment,
    )
    evaluation = Evaluation(
        candidate_id="mismatched-coordinate",
        params={"x": 0.25},
        params_normalized=(0.25,),
        objectives=[wrong_coordinate],
        scalar_score=gdp.raw_value,
        stage_a_passed=True,
        stage_b_result=source,
        score_status=gdp.score_status,
        score_assessment=gdp.score_assessment,
    )
    budget_rule = (
        configured_objective_rule_spec(BudgetDeficitObjective(expected_unit="points")) or ""
    )
    target = RunFingerprint(
        run_id="target-run",
        space_hash="space-v1",
        objective_names=["budget_deficit"],
        bounds={"x": [0.0, 1.0]},
        split="selection",
        units={"budget_deficit": "points"},
        origin="configured-candidate",
        tenant_id="tenant-a",
        objective_directions={
            "budget_deficit": BudgetDeficitObjective(expected_unit="points").direction.value
        },
        objective_rule_specs={"budget_deficit": budget_rule},
        embedding=[0.1],
    )
    index = _MemoryVectorIndex()
    writer = TransferLearningManager(FileSystemCAS(tmp_path / "cas"), index)
    assert writer.register_run(target, [evaluation]) is None

    # A stored header cannot upgrade a row carrying a self-consistent but differently
    # selected GDP rule. Rehydration keeps the row visible as diagnostic, but no score.
    row = TransferLearningManager._serialize_evaluation(evaluation)
    history = _history_document(target, [row])
    ref = writer._store.put_json(
        history,
        PutOptions(kind="search.transfer.history", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    index.add(
        key=target.run_id,
        embedding=target.embedding,
        metadata={
            "space_hash": target.space_hash,
            "objective_names": target.objective_names,
            "bounds": target.bounds,
            "split": target.split,
            "units": target.units,
            "origin": target.origin,
            "tenant_id": target.tenant_id,
            "objective_directions": target.objective_directions,
            "objective_rule_specs": target.objective_rule_specs,
            "artifact_id": ref.artifact_id,
            "manifest_profile_sha256": ref.manifest_profile_sha256,
        },
    )
    reader = TransferLearningManager(writer._store, index)
    target_query = target.model_copy(update={"run_id": "query-run"})
    similar = reader.find_similar_runs(target_query)
    assert len(similar) == 1
    restored = reader.get_warm_start_evaluations(
        similar, max_evals=1, target_fingerprint=target_query
    )[0]
    assert restored.score_status is ObjectiveScoreStatus.NOT_ESTABLISHED
    assert not restored.is_valid

    optimizer = object.__new__(MOBayesianOptimizer)
    optimizer._objective_names = ["budget_deficit"]
    optimizer._directions = [BudgetDeficitObjective(expected_unit="points").direction]
    optimizer._objective_rule_specs = {"budget_deficit": budget_rule}
    optimizer._negate_mask = [1.0]
    assert not optimizer._has_complete_objective_basis(restored)
    with pytest.raises(ValueError, match="not reconciled"):
        optimizer._objective_vector(restored)
