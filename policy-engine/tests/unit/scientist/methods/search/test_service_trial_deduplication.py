"""B124 actual native deduplication, context custody and physical evaluations."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import threading
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import Field

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.autotune.dedup import TrialDeduplicator
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    BenchmarkSplit,
    BenchmarkSuite,
    MutationArtifact,
    PromotionPolicy,
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
from polisyos.scientist.methods.search.frontier import policy_candidate_hash
from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry
from polisyos.scientist.methods.search.run_state import SearchRunState
from polisyos.scientist.methods.search.service import _decode_checkpoint


class _DatedMutation(MutationArtifact):
    value: int
    semantic: dict
    created_at: str = "2026-04-01"
    metadata: dict = Field(default_factory=dict)
    replicate_id: str | None = None
    seed: int | None = None


class _Evaluator:
    """Declared deterministic fixture; each call resolves the actual CAS inputs."""

    def __init__(self, *, scale=1, status="ok", include_metric=True, promotable=True):
        self.scale = scale
        self.status = status
        self.include_metric = include_metric
        self.promotable = promotable
        self.calls = []

    def checkpoint_configuration(self):
        return {
            "profile": "b124-controlled-physical-call.v1",
            "scale": self.scale,
            "status": self.status,
            "include_metric": self.include_metric,
            "promotable": self.promotable,
        }

    def evaluate(self, candidate_ref, suite_ref, context):
        candidate = load_model_artifact(context["store"], candidate_ref, _DatedMutation)
        suite = load_model_artifact(context["store"], suite_ref, BenchmarkSuite)
        self.calls.append(
            {
                "value": candidate.value,
                "starts_at": candidate.semantic["metadata"]["starts_at"],
                "replicate_id": candidate.replicate_id,
                "seed": candidate.seed,
                "candidate_ref": candidate_ref.model_dump(mode="json"),
                "suite_ref": suite_ref.model_dump(mode="json"),
            }
        )
        current = context["benchmark_comparison_incumbent"]
        return BenchmarkEvaluation(
            loop_id=candidate.loop_id,
            suite_id=suite.suite_id,
            candidate_ref=candidate_ref,
            holdout_metrics=(
                {
                    "score": float(
                        candidate.value * self.scale
                        + context.get("offset", 0)
                        + context.get("parameters", {}).get("offset", 0)
                    )
                }
                if self.include_metric
                else {}
            ),
            sample_counts={"holdout": 1},
            runtime_split_type=BenchmarkSplit.HOLDOUT,
            promotable=self.promotable,
            status=self.status,
            comparison_predecessor_candidate_ref=current.candidate_ref
            if current
            else None,
            comparison_predecessor_evaluation_ref=current.evaluation_ref
            if current
            else None,
        )


def _corpus():
    january = _DatedMutation(
        loop_id="dedup",
        value=1,
        semantic={
            "metadata": {"starts_at": "2026-01-01", "effective_date": "2026-01-15"}
        },
        notes=["first observation"],
        metadata={"loaded_at": "2026-04-01", "trace_id": "trace-first"},
    ).model_dump(mode="json")
    equivalent = deepcopy(january)
    equivalent["notes"] = ["different display note"]
    equivalent["created_at"] = "2026-05-01"
    equivalent["metadata"] = {"trace_id": "trace-second", "loaded_at": "2026-05-01"}
    equivalent["semantic"]["metadata"] = {
        "effective_date": "2026-01-15",
        "starts_at": "2026-01-01",
    }
    equivalent = dict(reversed(list(equivalent.items())))
    february = deepcopy(january)
    february["value"] = 2
    february["semantic"]["metadata"]["starts_at"] = "2026-02-01"
    first_replica = deepcopy(february)
    first_replica["replicate_id"] = "owner-declared-replica-one"
    second_replica = deepcopy(february)
    second_replica["replicate_id"] = "owner-declared-replica-two"
    return [january, equivalent, february, first_replica, second_replica]


def _runner(
    root,
    corpus=None,
    *,
    scale=1,
    suite_id="dedup",
    status="ok",
    include_metric=True,
    promotable=True,
):
    store = FileSystemCAS(root / "cas")
    registry = ChampionRegistry(root=root / "champions", store=store)
    suite = persist_benchmark_suite(
        store, BenchmarkSuite(suite_id=suite_id, data_basis="candidate_only")
    )
    evaluator = _Evaluator(
        scale=scale, status=status, include_metric=include_metric, promotable=promotable
    )
    spec = SearchLoopSpec(
        loop_id="dedup",
        mutation_codec=PydanticMutationCodec(_DatedMutation),
        candidate_generator=SequenceCandidateGenerator(corpus or _corpus()),
        benchmark_evaluator=evaluator,
        promotion_policy=PromotionPolicy(
            loop_id="dedup", primary_metric="score", unit="points"
        ),
    )
    return (
        SearchLoopRunner(store=store, registry=registry),
        store,
        registry,
        suite,
        evaluator,
        spec,
    )


def _values(evaluator):
    return [row["value"] for row in evaluator.calls]


def _identity_callback(value):
    return value


def _verify_history(store, result):
    for row in result.history:
        references = row.stage_b_result["simulation_results"]
        candidate_ref = ArtifactRef.model_validate(references["candidate_artifact_ref"])
        evaluation_ref = ArtifactRef.model_validate(
            references["evaluation_artifact_ref"]
        )
        candidate = load_model_artifact(store, candidate_ref, _DatedMutation)
        evaluation = load_model_artifact(store, evaluation_ref, BenchmarkEvaluation)
        assert evaluation.candidate_ref == candidate_ref
        assert candidate.semantic == row.candidate["semantic"]
        assert candidate.replicate_id == row.candidate["replicate_id"]
        assert evaluation.holdout_metrics == {"score": float(candidate.value)}


@pytest.mark.parametrize("entrypoint", ["run", "create_service"])
def test_native_dedup_uses_actual_semantic_content_and_retains_explicit_replicas(
    tmp_path, entrypoint
):
    runner, store, registry, suite, evaluator, spec = _runner(tmp_path)
    dedup = TrialDeduplicator()
    if entrypoint == "run":
        result = runner.run(spec, suite_ref=suite, max_iterations=4, dedup=dedup)
    else:
        service = runner.create_service(
            spec, suite_ref=suite, max_iterations=4, dedup=dedup
        )
        result = service.run_search(initial_context={})
    # Independent expected physical trace: Jan; Feb+incumbent Jan; two
    # explicit replicas, each rechecking the current incumbent Feb.
    assert _values(evaluator) == [1, 2, 1, 2, 2, 2, 2]
    assert len(result.history) == result.stage_b_evaluations == 4
    assert [
        row.candidate["semantic"]["metadata"]["starts_at"] for row in result.history
    ] == [
        "2026-01-01",
        "2026-02-01",
        "2026-02-01",
        "2026-02-01",
    ]
    assert [row.candidate["replicate_id"] for row in result.history] == [
        None,
        None,
        "owner-declared-replica-one",
        "owner-declared-replica-two",
    ]
    _verify_history(store, result)
    assert ChampionRegistry(
        root=tmp_path / "champions", store=FileSystemCAS(tmp_path / "cas")
    ).get("dedup").metrics == {"score": 2.0}
    fresh_runner, fresh_store, _, _, fresh_evaluator, fresh_spec = _runner(tmp_path)
    reopened = fresh_runner.resume(
        fresh_spec,
        suite_ref=suite,
        checkpoint_ref=ArtifactRef.model_validate(result.telemetry["checkpoint_ref"]),
        max_iterations=4,
        dedup=TrialDeduplicator(),
    )
    assert reopened.history == result.history
    assert fresh_evaluator.calls == []
    _verify_history(fresh_store, reopened)
    print(
        json.dumps(
            {
                "actual_calls": evaluator.calls,
                "history_count": 4,
                "checkpoint_ref": result.telemetry["checkpoint_ref"],
            },
            sort_keys=True,
        )
    )


def test_native_completed_duplicates_stop_without_fabricated_evaluation_or_free_cache_row(
    tmp_path,
):
    corpus = _corpus()[:2]
    runner, _, _, suite, evaluator, spec = _runner(tmp_path, corpus)
    result = runner.run(
        spec, suite_ref=suite, max_iterations=3, dedup=TrialDeduplicator()
    )
    assert _values(evaluator) == [1]
    assert (
        len(result.history)
        == result.stage_b_evaluations
        == result.iterations_completed
        == 1
    )
    assert result.stopping_reason == "generation_exhausted"
    print(
        json.dumps(
            {"actual_calls": evaluator.calls, "stopping_reason": result.stopping_reason}
        )
    )


def test_native_pending_membership_and_fresh_public_resume_derive_from_real_cas_history(
    tmp_path,
):
    corpus = _corpus()
    corpus.insert(
        3, deepcopy(corpus[2])
    )  # Same February subject while the original is pending.
    runner, store, _, suite, evaluator, spec = _runner(tmp_path, corpus)
    source = runner.create_service(
        spec, suite_ref=suite, max_iterations=3, dedup=TrialDeduplicator()
    )
    first = source.ask(None, None, {})[0]
    first_evaluation = source.controller._evaluate_for_tell(
        first.payload, iteration=0, context={}
    )
    source.tell(first.candidate_id, first_evaluation)
    assert source.ask(None, None, {}) == []  # Equivalent January has already completed.
    pending = source.ask(None, None, {})[0]
    assert pending.payload["value"] == 2
    assert source.ask(None, None, {}) == []  # Same February has not yet evaluated.
    checkpoint_ref = source.checkpoint_ref
    old_bytes = store.get_verified_snapshot(checkpoint_ref).data
    # The new process imports this unchanged, source-custodied producer profile.
    # No stateful dedup object or prepared EvaluationBundle crosses the boundary.
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(Path(__file__).parent), environment.get("PYTHONPATH", "")])
    )
    arguments = {
        "root": str(tmp_path),
        "corpus": corpus,
        "suite": suite.model_dump(mode="json"),
        "checkpoint": checkpoint_ref.model_dump(mode="json"),
    }
    script = r"""
import json, sys
from pathlib import Path
from test_service_trial_deduplication import (
    _runner, _verify_history, _values, ArtifactRef, TrialDeduplicator
)
packet = json.loads(sys.argv[1])
runner, store, _, _, evaluator, spec = _runner(Path(packet["root"]), packet["corpus"])
result = runner.resume(spec, suite_ref=ArtifactRef.model_validate(packet["suite"]),
                      checkpoint_ref=ArtifactRef.model_validate(packet["checkpoint"]),
                      max_iterations=3, dedup=TrialDeduplicator())
assert [row.candidate["value"] for row in result.history] == [1, 2, 2]
assert _values(evaluator) == [2, 1, 2, 2]
assert len(result.history) == result.stage_b_evaluations == 3
_verify_history(store, result)
print("FRESH_DEDUP_RECEIPT:" + json.dumps({"actual_calls": evaluator.calls,
      "history_values": [row.candidate["value"] for row in result.history],
      "checkpoint_ref": result.telemetry["checkpoint_ref"]}))
"""
    fresh = subprocess.run(
        [sys.executable, "-c", script, json.dumps(arguments)],
        capture_output=True,
        text=True,
        env=environment,
    )
    print(
        json.dumps(
            {
                "fresh_stdout": fresh.stdout,
                "fresh_stderr": fresh.stderr,
                "fresh_returncode": fresh.returncode,
            },
            sort_keys=True,
        )
    )
    assert fresh.returncode == 0, fresh.stdout + fresh.stderr
    fresh_line = next(
        line
        for line in fresh.stdout.splitlines()
        if line.startswith("FRESH_DEDUP_RECEIPT:")
    )
    fresh_receipt = json.loads(fresh_line.removeprefix("FRESH_DEDUP_RECEIPT:"))
    assert fresh_receipt["history_values"] == [1, 2, 2]
    assert _values(evaluator) == [1]
    fresh_store = FileSystemCAS(tmp_path / "cas")
    assert fresh_store.get_verified_snapshot(checkpoint_ref).data == old_bytes
    print(
        json.dumps(
            {
                "parent_calls": evaluator.calls,
                "fresh_calls": fresh_receipt["actual_calls"],
                "pending_checkpoint_ref": checkpoint_ref.model_dump(mode="json"),
            }
        )
    )


@pytest.mark.parametrize(
    "changed", ["context", "evaluator", "suite", "policy", "opaque"]
)
def test_native_dedup_changed_effective_basis_refuses_before_cursor_or_evaluator(
    tmp_path, changed
):
    runner, _, _, suite, _, spec = _runner(tmp_path)
    source = runner.create_service(
        spec, suite_ref=suite, max_iterations=4, dedup=TrialDeduplicator()
    )
    source.ask(None, None, {"offset": 0})
    checkpoint_ref = source.checkpoint_ref
    fresh_runner, _, _, fresh_suite, evaluator, fresh_spec = _runner(
        tmp_path,
        scale=2 if changed == "evaluator" else 1,
        suite_id="different-suite" if changed == "suite" else "dedup",
    )
    context = {"offset": 1 if changed == "context" else 0}
    if changed == "opaque":
        context["unbound_port"] = object()
    if changed == "policy":
        fresh_spec = replace(
            fresh_spec,
            promotion_policy=PromotionPolicy(
                loop_id="dedup", primary_metric="score", unit="different-points"
            ),
        )
    target = fresh_runner.create_service(
        fresh_spec, suite_ref=fresh_suite, max_iterations=4, dedup=TrialDeduplicator()
    )
    with pytest.raises(ValueError, match="configuration_mismatch|unsupported|dedup"):
        target.restore(checkpoint_ref, context=context)
    assert target.controller._generator.get_state()["index"] == 0
    assert target.controller._history == [] and target._pending_candidates == {}
    assert evaluator.calls == []


def test_native_dedup_live_context_change_refuses_before_next_proposal_effect(tmp_path):
    runner, _, _, suite, evaluator, spec = _runner(tmp_path)
    service = runner.create_service(
        spec, suite_ref=suite, max_iterations=4, dedup=TrialDeduplicator()
    )
    service.ask(None, None, {"offset": 0})
    before = service.controller._generator.get_state()
    with pytest.raises(ValueError, match="configuration_mismatch|context|dedup"):
        service.ask(None, None, {"offset": 1})
    assert service.controller._generator.get_state() == before
    assert evaluator.calls == []


def test_valid_returned_hash_markers_cannot_replace_actual_candidate_dates():
    january, equivalent, february, _, _ = _corpus()
    # The independent expected relation is read from these explicit fixture fields,
    # rather than deriving its denominator by calling the production hash helper.
    marker = "sha256:" + "a" * 64
    assert policy_candidate_hash(
        january, metadata_hash=marker
    ) != policy_candidate_hash(february, metadata_hash=marker)
    # The fingerprint's notes exclusion belongs to trial admission, while the
    # semantic frontier relation still observes the complete actual subject.
    dedup = TrialDeduplicator()
    assert dedup.fingerprint(january) == dedup.fingerprint(equivalent)
    february["value"] = january[
        "value"
    ]  # Temporal identity is the only semantic delta.
    assert dedup.fingerprint(january) != dedup.fingerprint(february)


def test_completed_duplicate_admission_resolves_actual_cas_before_skipping_evaluation(
    tmp_path,
):
    runner, store, _, suite, evaluator, spec = _runner(tmp_path)
    service = runner.create_service(
        spec, suite_ref=suite, max_iterations=4, dedup=TrialDeduplicator()
    )
    proposal = service.ask(None, None, {})[0]
    measured = service.controller._evaluate_for_tell(
        proposal.payload, iteration=0, context={}
    )
    service.tell(proposal.candidate_id, measured)
    reference = ArtifactRef.model_validate(
        service.controller._history[0].stage_b_result["simulation_results"][
            "evaluation_artifact_ref"
        ]
    )
    blob, _ = store._paths(reference.artifact_id)
    original = blob.read_bytes()
    assert hashlib.sha256(original).hexdigest() == str(
        reference.artifact_id
    ).removeprefix("sha256:")
    blob.write_bytes(
        original + b"\n"
    )  # Same valid reference/manifest, still parseable JSON.
    before = service.controller._generator.get_state()
    with pytest.raises(ValueError, match="sha256|integrity|mismatch"):
        service.ask(None, None, {})
    assert service.controller._generator.get_state() == before
    assert _values(evaluator) == [1]
    assert len(service.controller._history) == 1


def test_returned_hash_marker_cannot_collapse_actual_native_dates_cas_and_fresh_registry(
    tmp_path,
):
    import polisyos

    product = Path(polisyos.__file__).resolve().parents[2]
    path = (
        product
        / "tests/unit/scientist/methods/search/test_semantic_dates_persisted_consumers.py"
    )
    name = "_existing_b124_date_owner_fixture"
    module_spec = importlib.util.spec_from_file_location(name, path)
    owner = importlib.util.module_from_spec(module_spec)
    sys.modules[name] = owner
    module_spec.loader.exec_module(owner)
    registry = ParetoRegistry(tmp_path / "registry")
    source = owner._date_service(tmp_path / "cas", registry)
    actual = owner._date_stage_b
    marker = "sha256:" + "a" * 64

    def preserve_marker(candidate, context):
        result = actual(candidate, context)
        evaluation = result["policy_evaluation"]
        result["policy_evaluation"] = evaluation.model_copy(
            update={"metadata": {**evaluation.metadata, "candidate_hash": marker}}
        )
        return result

    source.controller._stage_b = preserve_marker
    result = source.run_search(initial_context={})
    fresh_snapshot = FileSystemCAS(tmp_path / "cas").get_verified_snapshot(
        source.checkpoint_ref
    )
    state = SearchRunState.from_checkpoint(
        _decode_checkpoint(fresh_snapshot.data)["run_state"]
    )
    fresh_registry = ParetoRegistry(tmp_path / "registry").get_snapshot(
        result.search_id
    )
    assert len(state.history) == 3
    assert [row.policy_evaluation.candidate_id for row in state.history] == [
        "full-fixture-evaluation-1",
        "full-fixture-evaluation-2",
        "full-fixture-evaluation-3",
    ]
    assert all(
        row.policy_evaluation.metadata["candidate_hash"] == marker
        for row in state.history
    )
    assert len(fresh_registry.entries) == 2
    assert {
        entry.seed_payload["semantic"]["metadata"]["starts_at"]
        for entry in fresh_registry.entries.values()
    } == {"2026-01-01", "2026-02-01"}
    print(
        json.dumps(
            {
                "source_fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "provided_marker": marker,
                "fresh_subjects": len(fresh_registry.entries),
                "physical_history": len(state.history),
                "checkpoint_ref": source.checkpoint_ref.model_dump(mode="json"),
            }
        )
    )


@pytest.mark.parametrize("replica_key", ["replicate_id", "replica_id", "seed"])
def test_explicit_native_proposal_replicas_survive_technical_identity_projection(
    replica_key,
):
    dedup = TrialDeduplicator()
    first = {
        "value": 1,
        "_strategy_metadata": {"candidate_id": "run:one", replica_key: 1},
    }
    equivalent = {
        "value": 1,
        "_strategy_metadata": {"candidate_id": "run:two", replica_key: 1},
    }
    independent = {
        "value": 1,
        "_strategy_metadata": {"candidate_id": "run:three", replica_key: 2},
    }
    assert dedup.fingerprint(first) == dedup.fingerprint(equivalent)
    assert dedup.fingerprint(first) != dedup.fingerprint(independent)


@pytest.mark.parametrize(
    "outcome", ["error", "unknown", "unavailable", "completed", "missing_metric"]
)
def test_unavailable_actual_outcome_cannot_make_equivalent_next_proposal_free(
    tmp_path, outcome
):
    runner, store, _, suite, evaluator, spec = _runner(
        tmp_path,
        status="ok" if outcome == "missing_metric" else outcome,
        include_metric=outcome != "missing_metric",
        promotable=False,
    )
    source = runner.create_service(
        spec, suite_ref=suite, max_iterations=4, dedup=TrialDeduplicator()
    )
    first = source.ask(None, None, {})[0]
    measured = source.controller._evaluate_for_tell(
        first.payload, iteration=0, context={}
    )
    source.tell(first.candidate_id, measured)
    artifact = ArtifactRef.model_validate(
        source.controller._history[0].stage_b_result["simulation_results"][
            "evaluation_artifact_ref"
        ]
    )
    actual = load_model_artifact(store, artifact, BenchmarkEvaluation)
    assert actual.status == ("ok" if outcome == "missing_metric" else outcome)
    assert bool(actual.holdout_metrics) is (outcome != "missing_metric")
    second = source.ask(None, None, {})[0]
    assert second.payload["semantic"] == first.payload["semantic"]
    assert second.payload["value"] == first.payload["value"]
    second_measurement = source.controller._evaluate_for_tell(
        second.payload, iteration=1, context={}
    )
    source.tell(second.candidate_id, second_measurement)
    assert _values(evaluator) == [1, 1]
    assert len(source.controller._history) == 2
    print(
        json.dumps(
            {
                "outcome": outcome,
                "actual_calls": evaluator.calls,
                "evaluation_ref": artifact.model_dump(mode="json"),
            }
        )
    )


def test_completed_finite_nonpromotable_measurement_is_not_a_missing_or_failed_outcome(
    tmp_path,
):
    runner, store, _, suite, evaluator, spec = _runner(tmp_path, promotable=False)
    source = runner.create_service(
        spec, suite_ref=suite, max_iterations=4, dedup=TrialDeduplicator()
    )
    first = source.ask(None, None, {})[0]
    measured = source.controller._evaluate_for_tell(
        first.payload, iteration=0, context={}
    )
    source.tell(first.candidate_id, measured)
    artifact = ArtifactRef.model_validate(
        source.controller._history[0].stage_b_result["simulation_results"][
            "evaluation_artifact_ref"
        ]
    )
    actual = load_model_artifact(store, artifact, BenchmarkEvaluation)
    assert actual.status == "ok" and actual.promotable is False
    assert actual.holdout_metrics == {"score": 1.0}
    assert source.ask(None, None, {}) == []
    assert _values(evaluator) == [1]
    assert len(source.controller._history) == 1


@pytest.mark.parametrize(
    ("profile", "present", "status", "value"),
    [
        ("missing", False, "ok", 1),
        ("status_not_ok", True, "error", 1),
        ("genuine_zero", True, "ok", 0),
        ("ordinary_one", True, "ok", 1),
    ],
)
def test_actual_native_primary_quantity_preserves_unavailable_zero_and_fresh_cas_basis(
    tmp_path, profile, present, status, value
):
    corpus = _corpus()[:1]
    corpus[0]["value"] = value
    runner, store, _, suite, evaluator, spec = _runner(
        tmp_path, corpus, status=status, include_metric=present, promotable=True
    )
    result = runner.run(spec, suite_ref=suite, max_iterations=1)
    assert _values(evaluator) == [value]
    assert len(result.history) == result.stage_b_evaluations == 1
    row = result.history[0]
    simulation = row.stage_b_result["simulation_results"]
    assessment = simulation["primary_metric_assessment"]
    assert assessment["metric"] == "score"
    assert assessment["split"] == "holdout"
    assert assessment["direction"] == "maximize"
    assert assessment["unit"] == "points"
    evaluation_ref = ArtifactRef.model_validate(simulation["evaluation_artifact_ref"])
    candidate_ref = ArtifactRef.model_validate(simulation["candidate_artifact_ref"])
    fresh_store = FileSystemCAS(tmp_path / "cas")
    actual = load_model_artifact(fresh_store, evaluation_ref, BenchmarkEvaluation)
    candidate = load_model_artifact(fresh_store, candidate_ref, _DatedMutation)
    assert actual.candidate_ref == candidate_ref
    assert actual.status == status
    assert (
        actual.promotable is True
    )  # Retain the positive producer marker on unavailable outcomes.
    assert actual.holdout_metrics == ({"score": float(value)} if present else {})
    assert candidate.value == value
    checkpoint_ref = ArtifactRef.model_validate(result.telemetry["checkpoint_ref"])
    saved_snapshot = fresh_store.get_verified_snapshot(checkpoint_ref)
    saved = SearchRunState.from_checkpoint(
        _decode_checkpoint(saved_snapshot.data)["run_state"]
    )
    fresh_pointer = ChampionRegistry(
        root=tmp_path / "champions", store=fresh_store
    ).get("dedup")
    # This is an observed quantity/state relation, not a declaration flag probe:
    # genuine zero has finite history, best and frontier; absence/error has none.
    if profile in {"missing", "status_not_ok"}:
        assert assessment["status"] == "unavailable"
        assert assessment["reason"] == (
            "primary_metric_missing"
            if profile == "missing"
            else "evaluation_status_not_comparable"
        )
        assert simulation["score"] is None
        assert row.is_promising is saved.history[0].is_promising is False
        assert row.stage_b_result["feedback"]["verdict"] == "REJECT"
        assert math.isnan(row.objective_value)
        assert math.isnan(saved.history[0].objective_value)
        assert row.objective_details[0].is_satisfied is False
        assert saved.best_candidate is None and not saved.pareto_points
        assert result.best_candidate is None and not result.pareto_front
        assert fresh_pointer is None
    else:
        assert assessment["status"] == "available" and assessment["reason"] is None
        assert row.is_promising is saved.history[0].is_promising is True
        assert row.stage_b_result["feedback"]["verdict"] == "APPROVE"
        assert simulation["score"] == float(value)
        assert row.objective_value == saved.history[0].objective_value == -float(value)
        assert row.objective_details[0].is_satisfied is True
        assert result.best_objective == saved.best_objective == -float(value)
        assert result.best_candidate["value"] == value
        assert len(saved.pareto_points) == len(result.pareto_front) == 1
        assert result.pareto_front[0]["objectives"][0]["raw_value"] == -float(value)
        assert fresh_pointer.metrics == {"score": float(value)}
    fresh_runner, _, _, _, fresh_evaluator, fresh_spec = _runner(
        tmp_path, corpus, status=status, include_metric=present, promotable=True
    )
    observer = fresh_runner.create_service(
        fresh_spec, suite_ref=suite, max_iterations=1
    )
    observer.restore(checkpoint_ref)
    reopened = observer.resume_search()
    assert fresh_evaluator.calls == []
    assert len(reopened.history) == 1
    assert reopened.best_candidate == result.best_candidate
    assert fresh_store.get_verified_snapshot(checkpoint_ref).data == saved_snapshot.data
    print(
        json.dumps(
            {
                "profile": profile,
                "actual_metrics": actual.holdout_metrics,
                "actual_status": actual.status,
                "actual_calls": evaluator.calls,
                "quantity_assessment": assessment,
                "checkpoint_ref": checkpoint_ref.model_dump(mode="json"),
                "evaluation_ref": evaluation_ref.model_dump(mode="json"),
            }
        )
    )


@pytest.mark.parametrize("position", ["direct", "nested_mapping", "nested_sequence"])
def test_optional_dedup_opaque_callback_context_refuses_before_generation_or_evaluation(
    tmp_path, position
):
    runner, _, _, suite, evaluator, spec = _runner(tmp_path)
    service = runner.create_service(
        spec, suite_ref=suite, max_iterations=4, dedup=TrialDeduplicator()
    )
    value = _identity_callback
    if position == "nested_mapping":
        value = {"inner": value}
    elif position == "nested_sequence":
        value = [{"inner": value}]
    with pytest.raises(ValueError, match="opaque_callback_context_unsupported"):
        service.ask(None, None, {"caller_port": value})
    assert service.controller._generator.get_state()["index"] == 0
    assert service.controller._history == [] and service._pending_candidates == {}
    assert evaluator.calls == []


@pytest.mark.parametrize("entrypoint", ["ask", "tell", "checkpoint", "resume_pending"])
def test_live_evaluator_configuration_cannot_rebind_old_measurement_membership(
    tmp_path, entrypoint
):
    runner, store, _, suite, evaluator, spec = _runner(tmp_path)
    service = runner.create_service(
        spec, suite_ref=suite, max_iterations=4, dedup=TrialDeduplicator()
    )
    first = service.ask(None, None, {})[0]
    measured = service.controller._evaluate_for_tell(
        first.payload, iteration=0, context={}
    )
    service.tell(first.candidate_id, measured)
    if entrypoint in {"tell", "resume_pending"}:
        assert (
            service.ask(None, None, {}) == []
        )  # The actual measured January duplicate.
        pending = service.ask(None, None, {})[0]
        if entrypoint == "tell":
            pending_measurement = service.controller._evaluate_for_tell(
                pending.payload, iteration=1, context={}
            )  # Actual valid old-profile result, prepared before drift.
    acknowledged = service.checkpoint_ref
    snapshot = store.get_verified_snapshot(acknowledged)
    before_generator = service.controller._generator.get_state()
    before_history = deepcopy(service.controller._history)
    before_pending = deepcopy(service._pending_candidates)
    before_calls = deepcopy(evaluator.calls)
    original_profile = _decode_checkpoint(snapshot.data)["configuration"][
        "replay_profile"
    ]
    assert original_profile["evaluator_configuration"]["configuration"]["scale"] == 1
    evaluator.scale = (
        2  # Same class/source bytes, new actual effective evaluator parameter.
    )

    def changed_profile_operation():
        if entrypoint == "ask":
            service.ask(None, None, {})
        elif entrypoint == "tell":
            service.tell(pending.candidate_id, pending_measurement)
        elif entrypoint == "resume_pending":
            service.resume_search(context={})
        else:
            service.checkpoint()

    with pytest.raises(ValueError, match="configuration_mismatch|dedup"):
        changed_profile_operation()
    assert service.controller._generator.get_state() == before_generator
    assert service.controller._history == before_history
    assert service._pending_candidates == before_pending
    assert evaluator.calls == before_calls
    assert service.checkpoint_ref == acknowledged
    assert (
        FileSystemCAS(tmp_path / "cas").get_verified_snapshot(acknowledged).data
        == snapshot.data
    )
    print(
        json.dumps(
            {
                "actual_calls": evaluator.calls,
                "entrypoint": entrypoint,
                "old_evaluator_scale": 1,
                "new_evaluator_scale": evaluator.scale,
                "retained_checkpoint_ref": acknowledged.model_dump(mode="json"),
            }
        )
    )


@pytest.mark.parametrize("entrypoint", ["ask", "tell", "checkpoint", "resume_pending"])
def test_nested_context_alias_cannot_rebind_acknowledged_pending_scope(
    tmp_path, entrypoint
):
    runner, store, _, suite, evaluator, spec = _runner(tmp_path)
    service = runner.create_service(
        spec, suite_ref=suite, max_iterations=4, dedup=TrialDeduplicator()
    )
    context = {"parameters": {"offset": 1}}
    first = service.ask(None, None, context)[0]
    if entrypoint == "tell":
        pending_measurement = service.controller._evaluate_for_tell(
            first.payload, iteration=0, context=context
        )  # Real old-profile measurement before nested mutation.
    acknowledged = service.checkpoint_ref
    snapshot = store.get_verified_snapshot(acknowledged)
    before_generator = service.controller._generator.get_state()
    before_pending = deepcopy(service._pending_candidates)
    before_calls = deepcopy(evaluator.calls)
    original_profile = _decode_checkpoint(snapshot.data)["configuration"][
        "replay_profile"
    ]
    assert original_profile["evaluation_context"]["parameters"]["offset"] == 1
    context["parameters"]["offset"] = 2  # Same caller mapping and shallow nested alias.

    def changed_profile_operation():
        if entrypoint == "ask":
            service.ask(None, None, context)
        elif entrypoint == "tell":
            service.tell(first.candidate_id, pending_measurement)
        elif entrypoint == "resume_pending":
            service.resume_search(context=context)
        else:
            service.checkpoint()

    with pytest.raises(ValueError, match="configuration_mismatch|dedup"):
        changed_profile_operation()
    assert service.controller._generator.get_state() == before_generator
    assert (
        service._pending_candidates
        == before_pending
        == {first.candidate_id: first.payload}
    )
    assert service.controller._history == [] and evaluator.calls == before_calls
    assert service.checkpoint_ref == acknowledged
    assert (
        FileSystemCAS(tmp_path / "cas").get_verified_snapshot(acknowledged).data
        == snapshot.data
    )
    print(
        json.dumps(
            {
                "actual_calls": evaluator.calls,
                "entrypoint": entrypoint,
                "old_nested_offset": 1,
                "new_nested_offset": context["parameters"]["offset"],
                "retained_checkpoint_ref": acknowledged.model_dump(mode="json"),
            }
        )
    )


def test_explicit_new_run_admits_new_declared_profile_without_rebinding_old_checkpoint(
    tmp_path,
):
    runner, store, _, suite, evaluator, spec = _runner(tmp_path)
    service = runner.create_service(
        spec, suite_ref=suite, max_iterations=1, dedup=TrialDeduplicator()
    )
    original = service.run_search(initial_context={})
    old_ref = service.checkpoint_ref
    old_snapshot = store.get_verified_snapshot(old_ref)
    old_checkpoint = _decode_checkpoint(old_snapshot.data)
    assert original.history[0].objective_value == -1.0
    assert (
        old_checkpoint["configuration"]["replay_profile"]["evaluator_configuration"][
            "configuration"
        ]["scale"]
        == 1
    )
    before_calls = deepcopy(evaluator.calls)
    evaluator.scale = 2
    fresh_run = service.run_search(initial_context={})
    new_ref = service.checkpoint_ref
    fresh_snapshot = FileSystemCAS(tmp_path / "cas").get_verified_snapshot(new_ref)
    new_checkpoint = _decode_checkpoint(fresh_snapshot.data)
    assert fresh_run.search_id != original.search_id
    assert len(fresh_run.history) == 1 and fresh_run.history[0].objective_value == -2.0
    assert len(evaluator.calls) > len(before_calls)
    actual_ref = ArtifactRef.model_validate(
        fresh_run.history[0].stage_b_result["simulation_results"][
            "evaluation_artifact_ref"
        ]
    )
    actual = load_model_artifact(
        FileSystemCAS(tmp_path / "cas"), actual_ref, BenchmarkEvaluation
    )
    assert actual.holdout_metrics == {"score": 2.0}
    assert new_ref != old_ref
    assert (
        new_checkpoint["configuration"]["replay_profile"]["evaluator_configuration"][
            "configuration"
        ]["scale"]
        == 2
    )
    assert (
        FileSystemCAS(tmp_path / "cas").get_verified_snapshot(old_ref).data
        == old_snapshot.data
    )
    old_state = SearchRunState.from_checkpoint(
        _decode_checkpoint(old_snapshot.data)["run_state"]
    )
    assert len(old_state.history) == 1 and old_state.history[0].objective_value == -1.0
    print(
        json.dumps(
            {
                "actual_calls": evaluator.calls,
                "old_checkpoint_ref": old_ref.model_dump(mode="json"),
                "new_checkpoint_ref": new_ref.model_dump(mode="json"),
                "old_scale": 1,
                "new_scale": 2,
            }
        )
    )


def test_proposal_failure_after_initial_ack_retains_basis_and_fresh_restore(
    tmp_path, monkeypatch
):
    runner, store, _, suite, evaluator, spec = _runner(tmp_path)
    service = runner.create_service(
        spec, suite_ref=suite, max_iterations=1, dedup=TrialDeduplicator()
    )
    actual_generate = service.controller._generate_candidates

    def proposal_failure(**kwargs):
        raise RuntimeError("injected_failure_after_initial_ack")

    monkeypatch.setattr(service.controller, "_generate_candidates", proposal_failure)
    with pytest.raises(RuntimeError, match="injected_failure_after_initial_ack"):
        service.ask(None, None, {"offset": 1})
    acknowledged = service.checkpoint_ref
    assert acknowledged is not None
    snapshot = FileSystemCAS(tmp_path / "cas").get_verified_snapshot(acknowledged)
    saved = _decode_checkpoint(snapshot.data)
    assert saved["configuration"]["replay_profile"]["evaluation_context"] == {
        "offset": 1
    }
    assert saved["run_state"]["history"] == [] and saved["pending_candidates"] == {}
    before_generator = service.controller._generator.get_state()
    assert before_generator["index"] == 0 and evaluator.calls == []
    with pytest.raises(
        (RuntimeError, ValueError), match="reopen|dedup|configuration_mismatch"
    ):
        service.ask(None, None, {"offset": 2})
    assert service.checkpoint_ref == acknowledged
    assert service.controller._generator.get_state() == before_generator
    assert service.controller._history == [] and service._pending_candidates == {}
    assert evaluator.calls == []
    assert store.get_verified_snapshot(acknowledged).data == snapshot.data
    monkeypatch.setattr(service.controller, "_generate_candidates", actual_generate)
    fresh_runner, fresh_store, _, _, fresh_evaluator, fresh_spec = _runner(tmp_path)
    fresh = fresh_runner.create_service(
        fresh_spec, suite_ref=suite, max_iterations=1, dedup=TrialDeduplicator()
    )
    fresh.restore(acknowledged, context={"offset": 1})
    resumed = fresh.resume_search(context={"offset": 1})
    assert _values(fresh_evaluator) == [1]
    assert len(resumed.history) == 1 and resumed.history[0].objective_value == -2.0
    assert fresh_store.get_verified_snapshot(acknowledged).data == snapshot.data
    print(
        json.dumps(
            {
                "failed_call_evaluations": evaluator.calls,
                "restored_actual_calls": fresh_evaluator.calls,
                "retained_checkpoint_ref": acknowledged.model_dump(mode="json"),
                "saved_context": saved["configuration"]["replay_profile"][
                    "evaluation_context"
                ],
            }
        )
    )


def test_shared_helper_membership_is_isolated_by_actual_run_with_barrier(
    tmp_path, monkeypatch
):
    runner, store, _, suite, evaluator_a, spec_a = _runner(tmp_path)
    evaluator_b = _Evaluator()
    spec_b = replace(
        spec_a,
        candidate_generator=SequenceCandidateGenerator([_corpus()[2]]),
        benchmark_evaluator=evaluator_b,
    )
    shared = TrialDeduplicator()
    source_a = runner.create_service(
        spec_a, suite_ref=suite, max_iterations=4, dedup=shared
    )
    source_b = runner.create_service(
        spec_b, suite_ref=suite, max_iterations=4, dedup=shared
    )
    initial = source_a.ask(None, None, {})[0]
    measured = source_a.controller._evaluate_for_tell(
        initial.payload, iteration=0, context={}
    )
    source_a.tell(initial.candidate_id, measured)
    paused = threading.Event()
    release = threading.Event()
    actual_lookup = shared.is_duplicate
    results = []
    failures = []

    def lookup_with_barrier(candidate, loop_id=""):
        if threading.current_thread().name == "native-run-A":
            paused.set()
            if not release.wait(10):
                raise RuntimeError("shared_helper_barrier_not_released")
        return actual_lookup(candidate, loop_id)

    def next_a():
        try:
            results.extend(source_a.ask(None, None, {}))
        except BaseException as exc:
            failures.append(exc)

    monkeypatch.setattr(shared, "is_duplicate", lookup_with_barrier)
    worker = threading.Thread(target=next_a, name="native-run-A")
    worker.start()
    try:
        assert paused.wait(10), "actual A lookup never reached the barrier"
        b_pending = source_b.ask(None, None, {})
        assert len(b_pending) == 1 and b_pending[0].payload["value"] == 2
        assert (
            source_a.controller._run_state.search_id
            != source_b.controller._run_state.search_id
        )
    finally:
        release.set()
        worker.join(10)
    assert not worker.is_alive() and failures == []
    # On the unisolated source A yields its measured January subject again.
    # Exercise the actual producer in that case before the deciding assertion,
    # so the discriminator includes the extra physical evaluation, not a flag.
    for proposal in results:
        retry = source_a.controller._evaluate_for_tell(
            proposal.payload, iteration=1, context={}
        )
        source_a.tell(proposal.candidate_id, retry)
    fresh_snapshot = FileSystemCAS(tmp_path / "cas").get_verified_snapshot(
        source_a.checkpoint_ref
    )
    saved = SearchRunState.from_checkpoint(
        _decode_checkpoint(fresh_snapshot.data)["run_state"]
    )
    b_snapshot = FileSystemCAS(tmp_path / "cas").get_verified_snapshot(
        source_b.checkpoint_ref
    )
    assert (
        _decode_checkpoint(fresh_snapshot.data)["configuration"]
        == _decode_checkpoint(b_snapshot.data)["configuration"]
    )
    print(
        json.dumps(
            {
                "actual_A_calls": evaluator_a.calls,
                "actual_B_calls": evaluator_b.calls,
                "actual_A_proposals": [p.payload for p in results],
                "A_run": source_a.controller._run_state.search_id,
                "B_run": source_b.controller._run_state.search_id,
                "A_checkpoint_ref": source_a.checkpoint_ref.model_dump(mode="json"),
                "B_checkpoint_ref": source_b.checkpoint_ref.model_dump(mode="json"),
                "fresh_A_history_count": len(saved.history),
            }
        )
    )
    assert _values(evaluator_a) == [1]
    assert evaluator_b.calls == []
    assert results == [] and len(saved.history) == 1
    assert store.get_verified_snapshot(source_b.checkpoint_ref).data == b_snapshot.data
