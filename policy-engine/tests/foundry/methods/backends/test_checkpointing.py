from __future__ import annotations

import os
import time
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import pytest

from polisyos.foundry.methods.backends.checkpointing import (
    ChainCheckpoint,
    CheckpointingChainExecutor,
    CheckpointLoadError,
    CheckpointSaveError,
    _compute_chain_digest,
)


class _FakeChain:
    def __init__(self, fqns: list[str]) -> None:
        self.execution_order = [uuid4() for _ in fqns]
        self._nodes = {
            node_id: SimpleNamespace(method_fqn=fqn, params={})
            for node_id, fqn in zip(self.execution_order, fqns, strict=True)
        }

    def get_node(self, node_id):
        return self._nodes[node_id]


def test_chain_checkpoint_round_trips_numpy_sidecars_atomically(tmp_path) -> None:
    path = tmp_path / "checkpoint_abc_0000.json"
    checkpoint = ChainCheckpoint(
        chain_digest="abc",
        completed_fqns=["demo.method@1.0.0"],
        completed_node_ids=[str(uuid4())],
        intermediate_state={"nested": {"arr": np.array([1.0, 2.0])}, "ok": True},
        node_timing_ms=[1.5],
    )

    checkpoint.save(path)
    loaded = ChainCheckpoint.load(path)

    assert loaded.checkpoint_path == path
    assert loaded.intermediate_state["ok"] is True
    np.testing.assert_allclose(loaded.intermediate_state["nested"]["arr"], np.array([1.0, 2.0]))
    assert not list(tmp_path.glob("*.tmp"))


def test_chain_checkpoint_load_rejects_missing_sidecar(tmp_path) -> None:
    path = tmp_path / "checkpoint_abc_0000.json"
    checkpoint = ChainCheckpoint(
        chain_digest="abc",
        completed_fqns=["demo.method@1.0.0"],
        completed_node_ids=[str(uuid4())],
        intermediate_state={"arr": np.array([1.0, 2.0])},
    )
    checkpoint.save(path)
    for sidecar in tmp_path.glob("checkpoint_abc_0000_arr.npy"):
        sidecar.unlink()

    with pytest.raises(CheckpointLoadError, match="sidecar missing"):
        ChainCheckpoint.load(path)


def test_find_latest_checkpoint_skips_corrupt_latest_and_records_issue(tmp_path) -> None:
    chain = _FakeChain(["demo.a@1.0.0", "demo.b@1.0.0"])
    digest = _compute_chain_digest(chain)
    older = tmp_path / f"checkpoint_{digest[:8]}_0001_20200101T000000.json"
    newer = tmp_path / f"checkpoint_{digest[:8]}_0002_20200101T000001.json"
    ChainCheckpoint(
        chain_digest=digest,
        completed_fqns=["demo.a@1.0.0"],
        completed_node_ids=[str(chain.execution_order[0])],
        intermediate_state={"value": 1},
    ).save(older)
    newer.write_text("{not-json", encoding="utf-8")
    now = time.time()
    os.utime(older, (now - 10, now - 10))
    os.utime(newer, (now, now))

    executor = CheckpointingChainExecutor(checkpoint_dir=tmp_path)
    recovered = executor.find_latest_checkpoint(chain)

    assert recovered is not None
    assert recovered.checkpoint_path == older
    assert executor.checkpoint_issues
    assert executor.checkpoint_issues[-1].operation == "load"


def test_checkpoint_save_failure_is_diagnostic_and_can_fail_closed(tmp_path, monkeypatch) -> None:
    chain = _FakeChain(["demo.a@1.0.0"])
    digest = _compute_chain_digest(chain)
    node_id = chain.execution_order[0]
    result = SimpleNamespace(timing=SimpleNamespace(wall_time_ms=2.0))

    def _boom(self, path):
        raise CheckpointSaveError("disk full")

    monkeypatch.setattr(ChainCheckpoint, "save", _boom)
    executor = CheckpointingChainExecutor(checkpoint_dir=tmp_path, fail_on_checkpoint_error=False)
    executor._save_checkpoint(
        chain=chain,
        chain_digest=digest,
        completed_up_to_idx=0,
        execution_order=chain.execution_order,
        all_node_results=[(node_id, result)],
        state={"value": 1},
    )

    assert executor.checkpoint_issues
    assert executor.checkpoint_issues[-1].operation == "save"

    strict_executor = CheckpointingChainExecutor(checkpoint_dir=tmp_path)
    with pytest.raises(CheckpointSaveError, match="disk full"):
        strict_executor._save_checkpoint(
            chain=chain,
            chain_digest=digest,
            completed_up_to_idx=0,
            execution_order=chain.execution_order,
            all_node_results=[(node_id, result)],
            state={"value": 1},
        )


def test_execute_resumes_with_checkpoint_stub_results(tmp_path) -> None:
    from polisyos.core.observability.determinism import DeterminismTier
    from polisyos.foundry.methods.backends.protocol import (
        MethodResult,
        MethodTiming,
        ReproducibilityInfo,
    )
    from polisyos.foundry.methods.base import ComputeBackend

    chain = _FakeChain(["demo.a@1.0.0", "demo.b@1.0.0"])
    checkpoint_path = tmp_path / "checkpoint_resume.json"
    ChainCheckpoint(
        chain_digest=_compute_chain_digest(chain),
        completed_fqns=["demo.a@1.0.0"],
        completed_node_ids=[str(chain.execution_order[0])],
        intermediate_state={"value": 1},
        node_timing_ms=[3.5],
    ).save(checkpoint_path)
    checkpoint = ChainCheckpoint.load(checkpoint_path)

    method_class = type(
        "FakeMethod",
        (),
        {"signature": SimpleNamespace(backend=ComputeBackend.NUMPY)},
    )
    registry = SimpleNamespace(get=lambda _fqn: method_class)

    class _Dispatcher:
        def dispatch(self, *, method_class, signature, state, params, seed):
            return MethodResult(
                output={"value": int(state["value"]) + 1},
                timing=MethodTiming(wall_time_ms=1.25),
                reproducibility=ReproducibilityInfo(
                    backend=signature.backend,
                    determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
                    seed=seed,
                ),
            )

    executor = CheckpointingChainExecutor(
        checkpoint_dir=None,
        registry=registry,
        dispatcher=_Dispatcher(),
    )

    result = executor.execute(
        chain,
        initial_state={"value": 0},
        checkpoint=checkpoint,
        seed=11,
    )

    assert len(result.node_results) == 2
    restored = result.node_results[0][1]
    assert restored.warnings == ("restored_from_checkpoint",)
    assert restored.artifacts["checkpoint_restore"]["status"] == "restored_from_checkpoint"
    assert restored.reproducibility.backend == ComputeBackend.NUMPY
    assert result.final_state["value"] == 2
    assert result.reproducibility_contract["determinism_tier"] == "library_deterministic"
    assert result.reproducibility_contract["node_count"] == 2
    assert result.reproducibility_contract["composition_kind"] == "serial"
