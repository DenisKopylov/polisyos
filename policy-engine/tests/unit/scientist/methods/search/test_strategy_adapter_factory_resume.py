"""Actual policy adapter, public factory, CAS and fresh Grid continuation."""

from __future__ import annotations

import json
import math
from dataclasses import replace

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.manifest_profile import artifact_manifest_profile_sha256
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon.canon_json import from_canonical_bytes
from polisyos.scientist.methods.autotune.models import (
    BenchmarkEvaluation,
    load_model_artifact,
)
from polisyos.scientist.methods.search.service import _decode_checkpoint
from polisyos.scientist.methods.search.strategies.adapter import StrategyAdapter
from polisyos.scientist.methods.search.strategies.codec import ScalarParameterCodec
from polisyos.scientist.methods.search.strategies.grid import GridSearchStrategy
from polisyos.scientist.methods.search.strategies.random import RandomSearchStrategy
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    ParameterBounds,
    ParameterType,
    StrategyState,
)
from tests.unit.scientist.methods.search.test_service_persistence import _direct, _runner


def _adapter_runner(root, *, changed=None):
    runner, store, registry, suite, evaluator, spec = _runner(root)
    space = SearchSpace(
        [
            ParameterBounds(
                name="value",
                lower=1,
                upper=6 if changed == "space" else 5,
                dtype=ParameterType.INTEGER,
            )
        ]
    )
    if changed == "strategy":
        strategy = RandomSearchStrategy(space, seed=11)
    else:
        strategy = GridSearchStrategy(
            space, seed=11, points_per_dim=4 if changed == "config" else 5, max_candidates=5
        )
    codec = ScalarParameterCodec(
        parameter_paths={"value": "other" if changed == "codec" else "value"}
    )
    adapter = StrategyAdapter(strategy, space, codec)
    return runner, store, registry, suite, evaluator, replace(spec, candidate_generator=adapter)


def _pending_after_one_actual_evaluation(root):
    runner, store, registry, suite, evaluator, spec = _adapter_runner(root)
    service = runner.create_service(spec, suite_ref=suite, max_iterations=5)
    first = service.ask(None, None, {})[0]
    assert first.payload["value"] == 1
    actual = service.controller._evaluate_for_tell(first.payload, iteration=0, context={})
    service.tell(first.candidate_id, actual)
    second_batch = service.ask(None, None, {})
    assert [item.payload["value"] for item in second_batch] == [2, 3]
    second = second_batch[0]
    assert service.controller._generator._strategy.get_state().metadata["cursor"] == 3
    return runner, store, registry, suite, evaluator, spec, service, second


def test_grid_adapter_public_factory_cas_fresh_resume_preserves_physical_next(
    tmp_path, monkeypatch
):
    _, store, _, suite, first_evaluator, _, service, pending = _pending_after_one_actual_evaluation(
        tmp_path
    )
    ref = service.checkpoint_ref
    assert isinstance(ref, ArtifactRef)
    original = store.get_bytes(ref)
    assert first_evaluator.calls == [1]

    fresh_runner, fresh_store, fresh_registry, _, fresh_evaluator, fresh_spec = _adapter_runner(
        tmp_path
    )
    observer = fresh_runner.create_service(fresh_spec, suite_ref=suite, max_iterations=5)
    observer.restore(ref)
    assert observer._pending_candidates[pending.candidate_id] == pending.payload
    assert sorted(item["value"] for item in observer._pending_candidates.values()) == [2, 3]
    adapter = observer.controller._generator
    assert adapter._strategy.get_state().metadata["cursor"] == 3
    assert adapter._synced_len == 1
    observer_evaluator = fresh_evaluator
    assert observer_evaluator.calls == []

    # Public runner resume constructs another fresh service; it evaluates the
    # persisted physical second/third subjects, then generates true fourth/fifth.
    fresh_runner, fresh_store, fresh_registry, _, fresh_evaluator, fresh_spec = _adapter_runner(
        tmp_path
    )
    result = fresh_runner.resume(fresh_spec, suite_ref=suite, checkpoint_ref=ref, max_iterations=5)
    assert [row.candidate["value"] for row in result.history] == [1, 2, 3, 4, 5]
    assert fresh_evaluator.calls == [2, 1, 3, 2, 4, 3, 5, 4]
    assert result.best_candidate["value"] == 5
    assert result.iterations_completed == result.stage_b_evaluations == 5
    assert fresh_registry.get("resume").metrics == {"score": 5.0}
    assert fresh_store.get_bytes(ref) == original
    for row in result.history:
        evaluation_ref = ArtifactRef.model_validate(
            row.stage_b_result["simulation_results"]["evaluation_artifact_ref"]
        )
        evaluation = load_model_artifact(fresh_store, evaluation_ref, BenchmarkEvaluation)
        assert evaluation.holdout_metrics == {"score": float(row.candidate["value"])}

    control_runner, _, _, control_suite, _, control_spec = _adapter_runner(tmp_path / "whole")
    whole = control_runner.run(control_spec, suite_ref=control_suite, max_iterations=5)
    assert [row.candidate["value"] for row in whole.history] == [
        row.candidate["value"] for row in result.history
    ]
    assert result.stopping_reason == whole.stopping_reason
    # The first actual generate hydrates the saved prefix without replaying its
    # update. Only newly evaluated second/third physical subjects reach update.
    updates = []
    original_update = adapter._strategy.update

    def observe_update(row):
        updates.append(row.params["value"])
        return original_update(row)

    monkeypatch.setattr(adapter._strategy, "update", observe_update)
    actual_second = observer.controller._evaluate_for_tell(pending.payload, iteration=1, context={})
    observer.tell(pending.candidate_id, actual_second)
    third_id, third_payload = next(
        (key, value) for key, value in observer._pending_candidates.items() if value["value"] == 3
    )
    actual_third = observer.controller._evaluate_for_tell(third_payload, iteration=2, context={})
    observer.tell(third_id, actual_third)
    assert [item.payload["value"] for item in observer.ask(None, None, {})] == [4, 5]
    assert [row.params["value"] for row in adapter._evaluations] == [1, 2, 3]
    assert updates == [2, 3]
    assert observer_evaluator.calls[0] == 2
    print(
        json.dumps(
            {
                "checkpoint_ref": ref.model_dump(mode="json"),
                "resumed_physical_values": [1, 2, 3, 4, 5],
                "actual_evaluator_calls": fresh_evaluator.calls,
                "full_physical_values": [1, 2, 3, 4, 5],
            },
            sort_keys=True,
        )
    )


@pytest.mark.parametrize("changed", ["strategy", "space", "config", "codec"])
def test_grid_adapter_changed_owned_basis_refuses_before_restore_effect(tmp_path, changed):
    _, store, _, suite, _, _, service, _ = _pending_after_one_actual_evaluation(tmp_path)
    ref = service.checkpoint_ref
    original = store.get_bytes(ref)
    runner, _, _, _, evaluator, spec = _adapter_runner(tmp_path, changed=changed)
    target = runner.create_service(spec, suite_ref=suite, max_iterations=5)
    before = target.controller._generator._strategy.get_state().to_artifact()
    with pytest.raises(ValueError):
        target.restore(ref)
    assert target.controller._generator._strategy.get_state().to_artifact() == before
    assert target.controller._run_state.search_id == ""
    assert target.controller._history == []
    assert target._pending_candidates == {}
    assert evaluator.calls == []
    assert store.get_bytes(ref) == original


def _store_modified_checkpoint(store, raw):
    bad = store.put_bytes(
        raw,
        ArtifactWriteOptions(
            kind="scientist.search.service_checkpoint",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.search.SearchServiceCheckpoint", version="2.0"
            ),
        ),
    )
    return bad.model_copy(
        update={
            "manifest_profile_sha256": artifact_manifest_profile_sha256(
                store.get_verified_snapshot(bad).manifest
            )
        }
    )


@pytest.mark.parametrize("changed", ["history_objective", "prefix_digest"])
def test_adapter_actual_cas_history_prefix_tamper_refuses_before_effect(tmp_path, changed):
    _, store, _, suite, _, _, service, _ = _pending_after_one_actual_evaluation(tmp_path)
    original = store.get_bytes(service.checkpoint_ref)
    payload = from_canonical_bytes(original)
    if changed == "history_objective":
        payload["run_state"]["history"][0]["objective_value"] += 1
    else:
        payload["generator_state"]["history_digests"][0] = "0" * 64
    bad_bytes = json.dumps(payload, sort_keys=True).encode()
    bad = _store_modified_checkpoint(store, bad_bytes)
    runner, _, _, _, evaluator, spec = _adapter_runner(tmp_path)
    target = runner.create_service(spec, suite_ref=suite, max_iterations=5)
    before = target.controller._generator._strategy.get_state().to_artifact()
    with pytest.raises(ValueError, match="history_prefix_mismatch"):
        target.restore(bad)
    assert target.controller._generator._strategy.get_state().to_artifact() == before
    assert target.controller._run_state.search_id == ""
    assert target.controller._history == []
    assert target._pending_candidates == {}
    assert evaluator.calls == []
    assert store.get_bytes(bad) == bad_bytes
    assert store.get_bytes(service.checkpoint_ref) == original


@pytest.mark.parametrize("token", ["1e-1000", "-1e-1000"])
def test_adapter_nested_strategy_json_underflow_refuses_before_effect(tmp_path, token):
    _, store, _, suite, _, _, service, _ = _pending_after_one_actual_evaluation(tmp_path)
    original = store.get_bytes(service.checkpoint_ref)
    payload = from_canonical_bytes(original)
    inner = payload["generator_state"]["strategy_state"]
    assert '"gauss_next": null' in inner
    # Preserve all cursor/space/config/history/RNG markers. Only this actual
    # cached Python RNG numeric token changes inside the nested JSON string.
    payload["generator_state"]["strategy_state"] = inner.replace(
        '"gauss_next": null', '"gauss_next": ' + token
    )
    bad_bytes = json.dumps(payload, sort_keys=True).encode()
    bad = _store_modified_checkpoint(store, bad_bytes)
    runner, _, _, _, evaluator, spec = _adapter_runner(tmp_path)
    target = runner.create_service(spec, suite_ref=suite, max_iterations=5)
    before = target.controller._generator._strategy.get_state().to_artifact()
    with pytest.raises(ValueError, match="numeric_underflow"):
        target.restore(bad)
    assert target.controller._generator._strategy.get_state().to_artifact() == before
    assert target.controller._run_state.search_id == ""
    assert target.controller._history == []
    assert target._pending_candidates == {}
    assert evaluator.calls == []
    assert store.get_bytes(bad) == bad_bytes
    assert store.get_bytes(service.checkpoint_ref) == original


@pytest.mark.parametrize("profile", ["policy_codec", "custom_extractor", "both"])
def test_nonpersisted_actual_policy_codec_and_callback_controller_stay_operational(profile):
    from polisyos.scientist.policy_design.search import PolicyParameterCodec

    space = SearchSpace(
        [ParameterBounds(name="cost", lower=1, upper=3, dtype=ParameterType.INTEGER)]
    )
    strategy = GridSearchStrategy(space, seed=11, points_per_dim=3, max_candidates=3)
    extractor_calls = []

    def extract(iteration):
        extractor_calls.append(iteration.iteration)
        return list(iteration.objective_details)

    codec = (
        PolicyParameterCodec({"cost": "cost"}, {"cost": 0})
        if profile in {"policy_codec", "both"}
        else ScalarParameterCodec(parameter_paths={"cost": "cost"})
    )
    adapter = StrategyAdapter(
        strategy,
        space,
        codec=codec,
        objective_extractor=extract if profile in {"custom_extractor", "both"} else None,
    )
    controller = _direct(None, generator=adapter).controller
    result = controller.run(initial_context={})
    assert [row.candidate["cost"] for row in result.history] == [1, 2]
    assert result.iterations_completed == result.stage_b_evaluations == 2
    assert result.best_candidate["cost"] == 1
    assert result.best_objective == 1
    if profile in {"custom_extractor", "both"}:
        assert extractor_calls == [0]
    assert adapter.get_state() is None


@pytest.mark.parametrize("token", ["0", "0.0", "5e-324"])
def test_adapter_nested_representable_rng_control_fresh_resume(tmp_path, token):
    _, store, _, suite, _, _, service, _ = _pending_after_one_actual_evaluation(tmp_path)
    payload = from_canonical_bytes(store.get_bytes(service.checkpoint_ref))
    inner = payload["generator_state"]["strategy_state"]
    assert '"gauss_next": null' in inner
    payload["generator_state"]["strategy_state"] = inner.replace(
        '"gauss_next": null', '"gauss_next": ' + token
    )
    control_bytes = json.dumps(payload, sort_keys=True).encode()
    control = _store_modified_checkpoint(store, control_bytes)
    runner, _, registry, _, evaluator, spec = _adapter_runner(tmp_path)
    observer = runner.create_service(spec, suite_ref=suite, max_iterations=5)
    observer.restore(control)
    actual_cache = observer.controller._generator._strategy._rng.getstate()[2]
    assert actual_cache == float(token)
    if token == "5e-324":
        assert actual_cache > 0
    assert evaluator.calls == []
    result = runner.resume(spec, suite_ref=suite, checkpoint_ref=control, max_iterations=5)
    assert [row.candidate["value"] for row in result.history] == [1, 2, 3, 4, 5]
    assert result.best_candidate["value"] == 5
    assert registry.get("resume").metrics == {"score": 5.0}
    assert store.get_bytes(control) == control_bytes


def test_adapter_fresh_checkpoint_unknown_and_duplicate_ids_preserve_pending(tmp_path):
    _, store, _, suite, _, _, service, pending = _pending_after_one_actual_evaluation(tmp_path)
    ref = service.checkpoint_ref
    original = store.get_bytes(ref)
    runner, _, _, _, evaluator, spec = _adapter_runner(tmp_path)
    target = runner.create_service(spec, suite_ref=suite, max_iterations=5)
    target.restore(ref)
    before = target.controller._generator._strategy.get_state().to_artifact()
    before_history = list(target.controller._history)
    with pytest.raises(KeyError, match="not-an-owned-id"):
        target.tell("not-an-owned-id", None)
    completed = next(iter(target._completed_candidate_ids))
    with pytest.raises(ValueError, match="duplicate"):
        target.tell(completed, None)
    assert target.controller._generator._strategy.get_state().to_artifact() == before
    assert target.controller._history == before_history
    assert target._pending_candidates == service._pending_candidates
    assert evaluator.calls == []
    assert store.get_bytes(ref) == original


def _actual_rng_artifact_with_numeric_token(token):
    space = SearchSpace(
        [ParameterBounds(name="value", lower=1, upper=3, dtype=ParameterType.INTEGER)]
    )
    artifact = (
        GridSearchStrategy(space, seed=11, points_per_dim=3, max_candidates=3)
        .get_state()
        .to_artifact()
    )
    assert b'"gauss_next": null' in artifact
    return artifact.replace(b'"gauss_next": null', b'"gauss_next": ' + token.encode())


def _decode_actual_numeric_seam(artifact, seam):
    if seam == "outer":
        # The public service decoder reads a raw JSON numeric token directly.
        return _decode_checkpoint(artifact)["rng_state"]["python"]["gauss_next"]
    # The public outer decoder sees an opaque inner JSON string; actual
    # StrategyState.from_artifact must independently admit its raw token.
    outer = json.dumps({"generator_state": {"strategy_state": artifact.decode()}}).encode()
    saved = _decode_checkpoint(outer)
    state = StrategyState.from_artifact(saved["generator_state"]["strategy_state"].encode())
    return state.rng_state["python"]["gauss_next"]


@pytest.mark.parametrize("seam", ["outer", "inner"])
@pytest.mark.parametrize(
    "token",
    [
        "1e-1000",
        "-1e-1000",
        "1e-999999999999999999999",
        "-1e-999999999999999999999",
        "1e1000",
        "-1e1000",
        "1e999999999999999999999",
        "-1e999999999999999999999",
        "NaN",
        "Infinity",
        "-Infinity",
    ],
)
def test_existing_checkpoint_decoders_refuse_raw_invalid_numeric_token(tmp_path, seam, token):
    artifact = _actual_rng_artifact_with_numeric_token(token)
    (tmp_path / "actual-strategy-artifact.json").write_bytes(artifact)
    assert b'"cursor": 0' in artifact
    with pytest.raises(ValueError):
        _decode_actual_numeric_seam(artifact, seam)
    print(json.dumps({"seam": seam, "raw_token": token, "result": "refused"}, sort_keys=True))


@pytest.mark.parametrize("seam", ["outer", "inner"])
@pytest.mark.parametrize("token", ["0", "-0", "0.0", "-0.0", "5e-324", "-5e-324"])
def test_existing_checkpoint_decoders_keep_genuine_zero_and_representable_rng(
    tmp_path, seam, token
):
    artifact = _actual_rng_artifact_with_numeric_token(token)
    (tmp_path / "actual-strategy-artifact.json").write_bytes(artifact)
    value = _decode_actual_numeric_seam(artifact, seam)
    assert type(value) in (int, float)
    assert value == float(token)
    if "5e-324" in token:
        assert value != 0
    if token in {"0.0", "-0.0"}:
        assert math.copysign(1, value) == math.copysign(1, float(token))
    print(json.dumps({"seam": seam, "raw_token": token, "value_repr": repr(value)}, sort_keys=True))
