"""Complete consumed history, real public factory/CAS and fresh strategy restore."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.manifest_profile import artifact_manifest_profile_sha256
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon.canon_json import CanonSpec
from polisyos.scientist.methods.autotune.runtime import SequenceCandidateGenerator
from polisyos.scientist.methods.search.run_state import checkpoint_json
from polisyos.scientist.methods.search.service import _decode_checkpoint
from polisyos.scientist.methods.search.strategies.adapter import StrategyAdapter
from polisyos.scientist.methods.search.strategies.base import BaseSearchStrategy
from polisyos.scientist.methods.search.strategies.codec import ScalarParameterCodec
from polisyos.scientist.methods.search.strategies.grid import GridSearchStrategy
from polisyos.scientist.methods.search.strategies.rl_wrapper import (
    LinearDecay,
    RLConfig,
    RLStrategyWrapper,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    ParameterBounds,
    ParameterType,
    PolicyCandidate,
)
from tests.unit.scientist.methods.search.test_service_persistence import _runner


class _AccumulatingStrategy(BaseSearchStrategy):
    """Bounded protocol witness: each consumed update contributes to next value."""

    def __init__(self, space, seed=11):
        super().__init__(space, seed)
        self.consumed_values = []

    def suggest(self, evaluations, pending=None):
        self._iteration += 1
        value = 1 + sum(self.consumed_values)
        return PolicyCandidate(
            candidate_id=f"accumulator_{self._iteration}",
            params={"value": value},
            params_normalized=self._space.normalize({"value": value}),
            source_strategy="bounded_history_accumulator",
        )

    def suggest_batch(self, evaluations, batch_size):
        # A supported short batch owns one actual candidate per invocation.
        return [] if batch_size == 0 else [self.suggest(evaluations)]

    def update(self, evaluation):
        self.consumed_values.append(evaluation.params["value"])

    def get_state(self):
        state = super().get_state()
        state.metadata["consumed_values"] = list(self.consumed_values)
        state.metadata["consumed_sum"] = sum(self.consumed_values)
        return state

    def validate_consumed_history(self, rows, state):
        values = state.metadata.get("consumed_values")
        if (
            not isinstance(values, list)
            or any(type(value) is not int for value in values)
            or type(state.metadata.get("consumed_sum")) is not int
            or sum(values) != state.metadata["consumed_sum"]
            or [row["params"]["value"] for row in rows] != values
        ):
            raise ValueError("accumulator_checkpoint_consumed_corpus_mismatch")

    def set_state(self, state):
        values = state.metadata.get("consumed_values")
        if (
            not isinstance(values, list)
            or any(type(value) is not int for value in values)
            or type(state.metadata.get("consumed_sum")) is not int
            or sum(values) != state.metadata["consumed_sum"]
        ):
            raise ValueError("accumulator_checkpoint_consumed_state_invalid")
        super().set_state(state)
        self.consumed_values = list(values)


class _OpaqueStatefulStrategy(_AccumulatingStrategy):
    # Actual update has effects, while this profile exposes no pure custody port.
    validate_consumed_history = None


def _history_runner(root, *, opaque=False):
    runner, store, registry, suite, evaluator, spec = _runner(root)
    space = SearchSpace([ParameterBounds("value", 1, 128, ParameterType.INTEGER)])
    strategy = (_OpaqueStatefulStrategy if opaque else _AccumulatingStrategy)(space)
    adapter = StrategyAdapter(strategy, space, ScalarParameterCodec({"value": "value"}))
    spec = replace(spec, candidate_generator=adapter)
    return runner, store, registry, suite, evaluator, spec


def _three_actual_evaluations(root):
    runner, store, registry, suite, evaluator, spec = _history_runner(root)
    service = runner.create_service(spec, suite_ref=suite, max_iterations=10)
    for index, expected in enumerate((1, 2, 4)):
        proposals = service.ask(None, None, {})
        assert len(proposals) == 1
        proposal = proposals[0]
        assert proposal.payload["value"] == expected
        result = service.controller._evaluate_for_tell(
            proposal.payload, iteration=index, context={}
        )
        service.tell(proposal.candidate_id, result)
    assert [row.candidate["value"] for row in service.controller._history] == [1, 2, 4]
    assert service.controller._generator._strategy.consumed_values == [1, 2]
    return runner, store, registry, suite, evaluator, spec, service


def _republish(store, payload):
    ref = store.put_json(
        payload,
        ArtifactWriteOptions(
            kind="scientist.search.service_checkpoint",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.search.SearchServiceCheckpoint", version="2.0"
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    return ref.model_copy(
        update={
            "manifest_profile_sha256": artifact_manifest_profile_sha256(
                store.get_verified_snapshot(ref).manifest
            )
        }
    )


def _live_view(service):
    return {
        "generator": checkpoint_json(service.controller._generator.get_state()),
        "run_state": service.controller._run_state.checkpoint_state(),
        "pending": deepcopy(service._pending_candidates),
        "completed": set(service._completed_candidate_ids),
        "iteration": service._ask_iteration,
        "checkpoint": service.checkpoint_ref,
        "stopping": service.controller._config.stopping.checkpoint_state(),
    }


def test_real_factory_cas_fresh_restore_preserves_complete_consumption_and_unconsumed_tail(
    tmp_path,
):
    _, store, _, suite, _, _, source = _three_actual_evaluations(tmp_path)
    ref = source.checkpoint_ref
    original = store.get_bytes(ref)
    payload = _decode_checkpoint(original)
    state = payload["generator_state"]
    assert state["consumed_history_count"] == 2
    assert len(state["history_digests"]) == len(state["history_rows"]) == 2
    assert [row["params"]["value"] for row in state["history_rows"]] == [1, 2]
    assert len(payload["run_state"]["history"]) == 3
    expected = 1 + sum((1, 2, 4))  # Independent update-law arithmetic, not suggest().
    uninterrupted = source.ask(None, None, {})[0].payload["value"]
    runner, fresh_store, _, _, evaluator, spec = _history_runner(tmp_path)
    fresh = runner.create_service(spec, suite_ref=suite, max_iterations=10)
    fresh.restore(ref)
    assert fresh.controller._generator._strategy.consumed_values == [1, 2]
    proposal = fresh.ask(None, None, {})[0]
    assert uninterrupted == proposal.payload["value"] == expected == 8
    assert fresh.controller._generator._strategy.consumed_values == [1, 2, 4]
    assert evaluator.calls == []
    assert fresh_store.get_bytes(ref) == original
    print(
        json.dumps(
            {
                "checkpoint_ref": ref.model_dump(mode="json"),
                "next_value": expected,
                "consumed_prefix": [1, 2],
                "unconsumed_tail": [4],
                "fresh_evaluator_calls": evaluator.calls,
            },
            sort_keys=True,
        )
    )


@pytest.mark.parametrize(
    "corruption",
    [
        "empty_digests",
        "truncated_digests",
        "count_and_digests",
        "count_digests_and_corpus",
        "missing_count",
        "bool_count",
        "negative_count",
        "huge_count",
        "corpus_changed",
        "history_changed",
    ],
)
def test_actual_cas_complete_consumption_corruption_refuses_before_any_live_state(
    tmp_path, corruption
):
    _, store, _, suite, _, _, source = _three_actual_evaluations(tmp_path)
    original_ref = source.checkpoint_ref
    original = store.get_bytes(original_ref)
    payload = _decode_checkpoint(original)
    state = payload["generator_state"]
    original_strategy = state["strategy_state"]
    if corruption == "empty_digests":
        state["history_digests"] = []
    elif corruption == "truncated_digests":
        state["history_digests"] = state["history_digests"][:1]
    elif corruption == "count_and_digests":
        state["consumed_history_count"] = 1
        state["history_digests"] = state["history_digests"][:1]
    elif corruption == "count_digests_and_corpus":
        state["consumed_history_count"] = 1
        state["history_digests"] = state["history_digests"][:1]
        state["history_rows"] = state["history_rows"][:1]
    elif corruption == "missing_count":
        state.pop("consumed_history_count")
    elif corruption == "bool_count":
        state["consumed_history_count"] = True
    elif corruption == "negative_count":
        state["consumed_history_count"] = -1
    elif corruption == "huge_count":
        state["consumed_history_count"] = 10**400
    elif corruption == "corpus_changed":
        state["history_rows"][1]["params"]["value"] = 99
    else:
        payload["run_state"]["history"][1]["objective_value"] = 99.0
    assert state["strategy_state"] == original_strategy
    corrupted_ref = _republish(store, payload)
    runner, _, _, _, evaluator, spec = _history_runner(tmp_path)
    fresh = runner.create_service(spec, suite_ref=suite, max_iterations=10)
    before = _live_view(fresh)
    try:
        fresh.restore(corrupted_ref)
    except ValueError:
        pass
    else:
        observed = fresh.ask(None, None, {})[0].payload["value"]
        print(
            json.dumps(
                {
                    "corruption": corruption,
                    "incorrect_next_value": observed,
                    "original_checkpoint": original_ref.model_dump(mode="json"),
                    "corrupted_checkpoint": corrupted_ref.model_dump(mode="json"),
                },
                sort_keys=True,
            )
        )
        pytest.fail("corrupted complete consumed-history binding was accepted")
    assert _live_view(fresh) == before
    assert evaluator.calls == []
    assert store.get_bytes(original_ref) == original


def test_zero_consumed_initial_adapter_checkpoint_remains_real_cas_supported(tmp_path):
    runner, store, _, suite, _, spec = _history_runner(tmp_path)
    source = runner.create_service(spec, suite_ref=suite, max_iterations=10)
    proposal = source.ask(None, None, {})[0]
    ref = source.checkpoint_ref
    state = _decode_checkpoint(store.get_bytes(ref))["generator_state"]
    assert state["consumed_history_count"] == 0
    assert state["history_rows"] == state["history_digests"] == []
    fresh_runner, _, _, _, evaluator, fresh_spec = _history_runner(tmp_path)
    fresh = fresh_runner.create_service(fresh_spec, suite_ref=suite, max_iterations=10)
    fresh.restore(ref)
    assert fresh._pending_candidates == {proposal.candidate_id: proposal.payload}
    assert fresh.controller._generator._strategy.consumed_values == []
    assert evaluator.calls == []


def test_stateful_override_without_consumption_port_is_explicit_unsupported_resume(tmp_path):
    runner, store, _, suite, _, spec = _history_runner(tmp_path, opaque=True)
    source = runner.create_service(spec, suite_ref=suite, max_iterations=10)
    proposal = source.ask(None, None, {})[0]
    ref = source.checkpoint_ref
    assert proposal.payload["value"] == 1
    assert _decode_checkpoint(store.get_bytes(ref))["generator_state"] is None
    runner, _, _, _, evaluator, spec = _history_runner(tmp_path, opaque=True)
    fresh = runner.create_service(spec, suite_ref=suite, max_iterations=10)
    before = _live_view(fresh)
    with pytest.raises(ValueError, match="unsupported_generator_profile"):
        fresh.restore(ref)
    assert _live_view(fresh) == before
    assert evaluator.calls == []


def test_history_independent_sequence_real_public_factory_fresh_resume_keeps_next(tmp_path):
    runner, store, _, suite, _, spec = _runner(tmp_path)
    source = runner.create_service(spec, suite_ref=suite, max_iterations=3)
    first = source.ask(None, None, {})[0]
    actual = source.controller._evaluate_for_tell(first.payload, iteration=0, context={})
    source.tell(first.candidate_id, actual)
    ref = source.checkpoint_ref
    expected = source.ask(None, None, {})[0].payload["value"]
    fresh_runner, fresh_store, _, _, evaluator, fresh_spec = _runner(tmp_path)
    fresh = fresh_runner.create_service(fresh_spec, suite_ref=suite, max_iterations=3)
    fresh.restore(ref)
    assert fresh.ask(None, None, {})[0].payload["value"] == expected == 2
    assert evaluator.calls == []
    assert fresh_store.get_bytes(ref) == store.get_bytes(ref)


@pytest.mark.parametrize("opaque_base", [False, True])
def test_rl_actual_nested_update_profile_uses_real_factory_cas_or_refuses_resume(
    tmp_path, opaque_base
):
    def configured():
        runner, store, registry, suite, evaluator, spec = _runner(tmp_path)
        space = SearchSpace([ParameterBounds("value", 1, 5, ParameterType.INTEGER)])
        base = (
            _OpaqueStatefulStrategy(space)
            if opaque_base
            else GridSearchStrategy(space, points_per_dim=5)
        )
        strategy = RLStrategyWrapper(
            base, space, RLConfig(exploration_schedule=LinearDecay(0.0, 0.0))
        )
        adapter = StrategyAdapter(strategy, space, ScalarParameterCodec({"value": "value"}))
        return runner, store, suite, evaluator, replace(spec, candidate_generator=adapter)

    runner, store, suite, _, spec = configured()
    source = runner.create_service(spec, suite_ref=suite, max_iterations=5)
    first = source.ask(None, None, {})[0]
    result = source.controller._evaluate_for_tell(first.payload, iteration=0, context={})
    source.tell(first.candidate_id, result)
    ref = source.checkpoint_ref
    fresh_runner, _, _, evaluator, fresh_spec = configured()
    fresh = fresh_runner.create_service(fresh_spec, suite_ref=suite, max_iterations=5)
    before = _live_view(fresh)
    if opaque_base:
        assert _decode_checkpoint(store.get_bytes(ref))["generator_state"] is None
        with pytest.raises(ValueError, match="unsupported_generator_profile"):
            fresh.restore(ref)
        assert _live_view(fresh) == before
    else:
        expected = [proposal.payload["value"] for proposal in source.ask(None, None, {})]
        fresh.restore(ref)
        actual = [proposal.payload["value"] for proposal in fresh.ask(None, None, {})]
        assert actual == expected == [2, 3]
    assert evaluator.calls == []


class _UnvalidatedGenerator:
    def __init__(self):
        self.cursor = 0
        self.restore_calls = 0

    def generate(self, history, current_best, context):
        self.cursor += 1
        return {"loop_id": "resume", "value": self.cursor}

    def get_state(self):
        return {"profile": "opaque_unvalidated.v1", "cursor": self.cursor}

    def set_state(self, state):
        self.restore_calls += 1
        self.cursor = state["cursor"]


def test_generic_nonnull_generator_state_without_history_port_refuses_before_set_state(tmp_path):
    runner, store, _, suite, _, spec = _runner(tmp_path)
    spec = replace(spec, candidate_generator=_UnvalidatedGenerator())
    source = runner.create_service(spec, suite_ref=suite, max_iterations=3)
    source.ask(None, None, {})
    ref = source.checkpoint_ref
    assert _decode_checkpoint(store.get_bytes(ref))["generator_state"] is not None
    fresh_runner, _, _, _, evaluator, fresh_spec = _runner(tmp_path)
    generator = _UnvalidatedGenerator()
    fresh_spec = replace(fresh_spec, candidate_generator=generator)
    fresh = fresh_runner.create_service(fresh_spec, suite_ref=suite, max_iterations=3)
    before = _live_view(fresh)
    with pytest.raises(ValueError, match="unsupported_generator_profile"):
        fresh.restore(ref)
    assert _live_view(fresh) == before
    assert generator.restore_calls == 0
    assert evaluator.calls == []


class _CanonicalSequenceSubclass(SequenceCandidateGenerator):
    pass


class _HistorySequenceSubclass(SequenceCandidateGenerator):
    def __init__(self, candidates):
        super().__init__(candidates)
        self.total = 0

    def generate(self, history, current_best, context):
        self.total += sum(row.candidate["value"] for row in history)
        candidate = super().generate(history, current_best, context)
        candidate["value"] += self.total
        return candidate


@pytest.mark.parametrize("history_override", [False, True])
def test_sequence_inherited_validator_requires_actual_history_independent_body(
    tmp_path, history_override
):
    def configured():
        runner, store, registry, suite, evaluator, spec = _runner(tmp_path)
        cls = _HistorySequenceSubclass if history_override else _CanonicalSequenceSubclass
        generator = cls(spec.candidate_generator._candidates)
        return runner, store, suite, evaluator, replace(spec, candidate_generator=generator)

    runner, store, suite, _, spec = configured()
    source = runner.create_service(spec, suite_ref=suite, max_iterations=3)
    first = source.ask(None, None, {})[0]
    actual = source.controller._evaluate_for_tell(first.payload, iteration=0, context={})
    source.tell(first.candidate_id, actual)
    ref = source.checkpoint_ref
    runner, _, _, evaluator, spec = configured()
    fresh = runner.create_service(spec, suite_ref=suite, max_iterations=3)
    before = _live_view(fresh)
    if history_override:
        assert _decode_checkpoint(store.get_bytes(ref))["generator_state"] is None
        assert source.ask(None, None, {})[0].payload["value"] == 3
        with pytest.raises(ValueError, match="unsupported_generator_profile"):
            fresh.restore(ref)
        assert _live_view(fresh) == before
        assert fresh.controller._generator.total == 0
    else:
        expected = source.ask(None, None, {})[0].payload["value"]
        fresh.restore(ref)
        assert fresh.ask(None, None, {})[0].payload["value"] == expected == 2
    assert evaluator.calls == []
