"""Imported module mutations must not reuse an incompatible actual checkpoint."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import ClassVar

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.backends.checkpointing import (
    ChainCheckpoint,
    CheckpointDigestMismatchError,
    CheckpointingChainExecutor,
)

from .test_checkpoint_identity import (
    _METADATA,
    _PRODUCER_SIGNATURE,
    _RecordingDispatcher,
    _chain,
    _strict_context,
)


def _original_multiplier(value):
    return value * 2


def _replacement_multiplier(value):
    return value * 3


class _ImportedSource:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": math._e02_b74_owner_multiplier(state["x"])}


def test_same_version_imported_member_change_refuses_actual_stale_prefix(tmp_path, monkeypatch):
    """The real cold result changes10 while stale resume would still produce7."""
    monkeypatch.setattr(math, "_e02_b74_owner_multiplier", _original_multiplier, raising=False)
    chain, registry = _chain()
    registry.register(_ImportedSource, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    dispatcher = _RecordingDispatcher()
    executor = CheckpointingChainExecutor(
        registry=registry,
        dispatcher=dispatcher,
        artifact_store=store,
        checkpoint_dir=tmp_path / "checkpoints",
    )
    original = executor.execute(chain, initial_state={"x": 3}, seed=7, artifact_context=context)
    pointer = next((tmp_path / "checkpoints").glob("*_0000_*.json"))
    checkpoint = ChainCheckpoint.load(pointer)
    original_pointer = pointer.read_bytes()
    unchanged = executor.execute(
        chain, initial_state={"x": 3}, checkpoint=checkpoint, seed=7, artifact_context=context
    )
    assert original.final_state["total"] == unchanged.final_state["total"] == 7
    assert unchanged.history_complete
    monkeypatch.setattr(math, "_e02_b74_owner_multiplier", _replacement_multiplier)
    cold = CheckpointingChainExecutor(registry=registry, artifact_store=store).execute(
        chain, initial_state={"x": 3}, seed=7, artifact_context=context
    )
    assert cold.final_state["total"] == 10
    dispatcher.calls.clear()
    with pytest.raises(CheckpointDigestMismatchError):
        executor.execute(
            chain, initial_state={"x": 3}, checkpoint=checkpoint, seed=7, artifact_context=context
        )
    assert dispatcher.calls == []
    assert pointer.read_bytes() == original_pointer


class _BuiltinSource:
    signature: ClassVar = replace(_PRODUCER_SIGNATURE, name="builtin")
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": math.fabs(state["x"]) * params["factor"]}


def test_unchanged_imported_builtin_retains_actual_arithmetic_resume(tmp_path):
    """A supported unchanged native member does not withdraw numerical reuse."""

    # Keep the same actual compiled FQN/required chain as the other profiles.
    class Source(_BuiltinSource):
        signature: ClassVar = _PRODUCER_SIGNATURE

    chain, registry = _chain()
    registry.register(Source, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    executor = CheckpointingChainExecutor(
        registry=registry, artifact_store=store, checkpoint_dir=tmp_path / "checkpoints"
    )
    original = executor.execute(chain, initial_state={"x": 3}, seed=7, artifact_context=context)
    checkpoint = ChainCheckpoint.load(next((tmp_path / "checkpoints").glob("*_0000_*.json")))
    resumed = executor.execute(
        chain, initial_state={"x": 3}, checkpoint=checkpoint, seed=7, artifact_context=context
    )
    assert original.final_state["total"] == resumed.final_state["total"] == 7
    assert resumed.history_complete
