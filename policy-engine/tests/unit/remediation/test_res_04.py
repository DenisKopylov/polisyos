"""Behavioral RED witnesses for RES-04 checkpoint identity and sidecars."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import UUID, uuid4

import numpy as np
import pytest

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodSignature,
)
from polisyos.foundry.methods.backends.checkpointing import (
    ChainCheckpoint,
    CheckpointDigestMismatchError,
    CheckpointError,
    CheckpointLoadError,
    CheckpointSaveError,
    CheckpointingChainExecutor,
    _compute_chain_digest,
)
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodTiming,
    ReproducibilityInfo,
)
from polisyos.foundry.methods.backends.validated import (
    ValidatedBound,
    ValidatedMethodFamily,
    ValidatedStatus,
)
from polisyos.foundry.methods.components.composer import (
    CompiledMethodChain,
    CompositionDAG,
    MethodNode,
)


class _FakeChain:
    def __init__(self, fqns: list[str]) -> None:
        self.execution_order = [uuid4() for _ in fqns]
        self._nodes = {
            node_id: SimpleNamespace(method_fqn=fqn, params={})
            for node_id, fqn in zip(self.execution_order, fqns, strict=True)
        }

    def get_node(self, node_id: UUID):
        return self._nodes[node_id]


def _chain() -> _FakeChain:
    chain = _FakeChain(["demo.multiply@1.0.0", "demo.add@1.0.0"])
    chain.get_node(chain.execution_order[0]).params = {"factor": 2}
    chain.get_node(chain.execution_order[1]).params = {"delta": 1}
    return chain


def _runtime_registry(chain: _FakeChain):
    runtime_by_fqn = {
        node.method_fqn: type(
            "FakeMethod",
            (),
            {
                "method_fqn": node.method_fqn,
                "signature": SimpleNamespace(backend=ComputeBackend.NUMPY),
            },
        )
        for node in chain._nodes.values()
    }
    return SimpleNamespace(get=lambda fqn: runtime_by_fqn[fqn])


class _Dispatcher:
    def dispatch(self, *, method_class, signature, state, params, seed):
        value = int(state["value"])
        if method_class.method_fqn.endswith("multiply@1.0.0"):
            output = {"value": value * int(params["factor"])}
        else:
            output = {"value": value + int(params["delta"])}
        return MethodResult(
            output=output,
            timing=MethodTiming(wall_time_ms=1.0),
            reproducibility=ReproducibilityInfo(
                backend=signature.backend,
                determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
                seed=seed,
            ),
        )


def _executor(chain: _FakeChain, checkpoint_dir=None) -> CheckpointingChainExecutor:
    return CheckpointingChainExecutor(
        checkpoint_dir=checkpoint_dir,
        registry=_runtime_registry(chain),
        dispatcher=_Dispatcher(),
    )


def _first_checkpoint(tmp_path, chain: _FakeChain) -> ChainCheckpoint:
    path = next(tmp_path.glob(f"checkpoint_{_compute_chain_digest(chain)[:8]}_0000_*.json"))
    return ChainCheckpoint.load(path)


def test_changed_effective_parameter_does_not_reuse_checkpoint(tmp_path) -> None:
    """A changed multiplier must not resume the old value 6 and yield 7."""
    chain = _chain()
    executor = _executor(chain, tmp_path)
    executor.execute(chain, initial_state={"value": 3}, seed=7)
    checkpoint = _first_checkpoint(tmp_path, chain)

    try:
        resumed = executor.execute(
            chain,
            initial_state={"value": 3},
            params_per_node={chain.execution_order[0]: {"factor": 3}},
            checkpoint=checkpoint,
            seed=7,
        )
    except CheckpointError:
        return

    assert resumed.final_state == {"value": 10}
    assert [result.output for _, result in resumed.node_results] == [
        {"value": 9},
        {"value": 10},
    ]


def test_changed_initial_input_does_not_reuse_checkpoint(tmp_path) -> None:
    """A changed initial state must not reuse the old intermediate state 6."""
    chain = _chain()
    executor = _executor(chain, tmp_path)
    executor.execute(chain, initial_state={"value": 3}, seed=7)
    checkpoint = _first_checkpoint(tmp_path, chain)

    try:
        resumed = executor.execute(
            chain,
            initial_state={"value": 4},
            checkpoint=checkpoint,
            seed=7,
        )
    except CheckpointError:
        return

    assert resumed.final_state == {"value": 9}
    assert [result.output for _, result in resumed.node_results] == [
        {"value": 8},
        {"value": 9},
    ]


def test_resume_preserves_original_per_node_outputs_and_seed(tmp_path) -> None:
    """Resume must retain A=6/B=7 and the original seed=7 history."""
    chain = _chain()
    executor = _executor(chain, tmp_path)
    executor.execute(chain, initial_state={"value": 3}, seed=7)
    checkpoint_path = next(
        tmp_path.glob(f"checkpoint_{_compute_chain_digest(chain)[:8]}_0001_*.json")
    )
    checkpoint = ChainCheckpoint.load(checkpoint_path)

    with pytest.raises(CheckpointError):
        executor.execute(
            chain,
            initial_state={"value": 0},
            checkpoint=checkpoint,
            seed=99,
        )

    resumed = executor.execute(
        chain,
        initial_state={"value": 3},
        checkpoint=checkpoint,
        seed=7,
    )

    assert [result.output for _, result in resumed.node_results] == [
        {"value": 6},
        {"value": 7},
    ]
    assert [result.reproducibility.seed for _, result in resumed.node_results] == [7, 7]


@pytest.mark.parametrize("change", ["input", "parameter", "seed"])
def test_legacy_checkpoint_fails_closed_for_unbound_request(tmp_path, change) -> None:
    """Pre-identity checkpoints must never reuse an unverifiable state."""
    chain = _chain()
    checkpoint = ChainCheckpoint(
        chain_digest=_compute_chain_digest(chain),
        completed_fqns=["demo.multiply@1.0.0"],
        completed_node_ids=[str(chain.execution_order[0])],
        intermediate_state={"value": 6},
        node_timing_ms=[1.0],
    )
    initial_state = {"value": 4 if change == "input" else 3}
    params = (
        {chain.execution_order[0]: {"factor": 3}}
        if change == "parameter"
        else None
    )
    seed = 99 if change == "seed" else 7

    with pytest.raises(CheckpointDigestMismatchError, match="lacks execution identity"):
        _executor(chain, tmp_path).execute(
            chain,
            initial_state=initial_state,
            params_per_node=params,
            checkpoint=checkpoint,
            seed=seed,
        )


def test_no_checkpoint_path_does_not_require_stable_input_digest() -> None:
    """Plain execution keeps accepting dispatcher-owned opaque state values."""
    chain = _chain()
    result = _executor(chain).execute(
        chain,
        initial_state={"value": 3, "opaque": object()},
        seed=7,
    )

    assert result.final_state["value"] == 7


def test_real_compiled_chain_round_trips_native_result_and_validated_bound(tmp_path) -> None:
    """The persisted history path handles a compiled chain and typed result payload."""
    node_id = uuid4()
    method_fqn = "demo.real@1.0.0"
    node = MethodNode(node_id, method_fqn, params={}, static_params={})
    dag = CompositionDAG()
    dag.add_node(node)
    signature = MethodSignature(
        name="real",
        namespace="demo",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    chain = CompiledMethodChain(
        dag=dag.freeze(),
        signatures={node_id: signature},
        execution_order=(node_id,),
        bindings=(),
        warnings=(),
    )
    method_class = type("RealFakeMethod", (), {"method_fqn": method_fqn, "signature": signature})
    registry = SimpleNamespace(get=lambda _fqn: method_class)
    bound = ValidatedBound(
        status=ValidatedStatus.RIGOROUS_ENCLOSURE,
        quantity="value",
        lower=(0.1, 0.2),
        upper=(0.3, 0.4),
        contains_point_estimate=True,
        method_family=ValidatedMethodFamily.INTERVAL,
        engine="test-engine",
    )

    class _Dispatcher:
        def dispatch(self, *, method_class, signature, state, params, seed):
            return MethodResult(
                output={"value": np.array([1.0])},
                timing=MethodTiming(wall_time_ms=1.0),
                reproducibility=ReproducibilityInfo(
                    backend=signature.backend,
                    determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
                    seed=seed,
                ),
                artifacts={"native": np.array([2.0])},
                validated_bound=bound,
            )

    producer = CheckpointingChainExecutor(
        checkpoint_dir=tmp_path,
        registry=registry,
        dispatcher=_Dispatcher(),
    )
    producer.execute(chain, initial_state={}, seed=13)
    checkpoint = ChainCheckpoint.load(next(tmp_path.glob("*_0000_*.json")))

    resumed = CheckpointingChainExecutor(
        checkpoint_dir=None,
        registry=registry,
        dispatcher=_Dispatcher(),
    ).execute(chain, initial_state={}, checkpoint=checkpoint, seed=13)

    restored = resumed.node_results[0][1]
    np.testing.assert_array_equal(restored.output["value"], np.array([1.0]))
    np.testing.assert_array_equal(restored.artifacts["native"], np.array([2.0]))
    assert restored.validated_bound is not None
    assert restored.validated_bound.lower == (0.1, 0.2)


def test_resume_rejects_completed_ids_that_are_not_the_chain_prefix(tmp_path) -> None:
    """A count-only skip cannot accept a checkpoint for a non-prefix node."""
    chain = _chain()
    checkpoint = ChainCheckpoint(
        chain_digest=_compute_chain_digest(chain),
        completed_fqns=["demo.multiply@1.0.0"],
        completed_node_ids=[str(chain.execution_order[1])],
        intermediate_state={"value": 6},
        node_timing_ms=[1.0],
    )

    with pytest.raises(CheckpointError):
        _executor(chain).execute(
            chain,
            initial_state={"value": 3},
            checkpoint=checkpoint,
            seed=7,
        )


@pytest.mark.parametrize("reference", ["../foreign.npy", "/tmp/foreign.npy"])
def test_sidecar_reference_cannot_escape_checkpoint_directory(tmp_path, reference) -> None:
    path = tmp_path / "checkpoint_path_boundary.json"
    ChainCheckpoint(
        chain_digest="path-boundary",
        completed_fqns=[],
        completed_node_ids=[],
        intermediate_state={"arr": np.array([1.0])},
    ).save(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["intermediate_state"]["arr"]["__npy_ref__"] = reference
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(CheckpointLoadError, match="escapes its directory"):
        ChainCheckpoint.load(path)


def test_sidecar_symlink_is_rejected_before_load(tmp_path) -> None:
    path = tmp_path / "checkpoint_symlink.json"
    ChainCheckpoint(
        chain_digest="symlink",
        completed_fqns=[],
        completed_node_ids=[],
        intermediate_state={"arr": np.array([1.0])},
    ).save(path)
    sidecar = tmp_path / "checkpoint_symlink_arr.npy"
    foreign = tmp_path.parent / "foreign-sidecar.npy"
    np.save(foreign, np.array([9.0]))
    sidecar.unlink()
    sidecar.symlink_to(foreign)

    with pytest.raises(CheckpointLoadError, match="symlink"):
        ChainCheckpoint.load(path)


def test_foreign_sidecar_content_is_rejected(tmp_path) -> None:
    path = tmp_path / "checkpoint_content_binding.json"
    ChainCheckpoint(
        chain_digest="content-binding",
        completed_fqns=[],
        completed_node_ids=[],
        intermediate_state={"arr": np.array([1.0])},
    ).save(path)
    np.save(tmp_path / "checkpoint_content_binding_arr.npy", np.array([9.0]))

    with pytest.raises(CheckpointLoadError, match="content mismatch"):
        ChainCheckpoint.load(path)


def test_same_manifest_concurrent_saves_publish_complete_generations(tmp_path) -> None:
    path = tmp_path / "checkpoint_concurrent.json"

    def save(value: float) -> None:
        ChainCheckpoint(
            chain_digest="concurrent",
            completed_fqns=[],
            completed_node_ids=[],
            intermediate_state={"arr": np.array([value])},
        ).save(path)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(save, (1.0, 2.0)))

    loaded = ChainCheckpoint.load(path)
    assert loaded.intermediate_state["arr"].tolist() in ([1.0], [2.0])
    assert len(list(tmp_path.glob("checkpoint_concurrent*.npy"))) >= 2


def test_sidecar_encoding_keeps_flat_and_nested_paths_distinct(tmp_path) -> None:
    """The paths ``a_b`` and ``a -> b`` must not share one sidecar."""
    path = tmp_path / "checkpoint_collision.json"
    checkpoint = ChainCheckpoint(
        chain_digest="collision",
        completed_fqns=[],
        completed_node_ids=[],
        intermediate_state={
            "a_b": np.array([1.0]),
            "a": {"b": np.array([2.0])},
        },
    )

    checkpoint.save(path)
    loaded = ChainCheckpoint.load(path)

    np.testing.assert_array_equal(loaded.intermediate_state["a_b"], np.array([1.0]))
    np.testing.assert_array_equal(loaded.intermediate_state["a"]["b"], np.array([2.0]))


def test_failed_new_save_leaves_previous_snapshot_readable(tmp_path, monkeypatch) -> None:
    """A failed publish cannot replace sidecars referenced by the old JSON."""
    path = tmp_path / "checkpoint_generation.json"
    old = ChainCheckpoint(
        chain_digest="generation",
        completed_fqns=[],
        completed_node_ids=[],
        intermediate_state={"arr": np.array([1.0])},
    )
    old.save(path)

    def _fail_publish(*_args, **_kwargs):
        raise OSError("publish failed")

    import polisyos.foundry.methods.backends.checkpointing as checkpointing

    monkeypatch.setattr(checkpointing, "_atomic_write_bytes", _fail_publish)
    with pytest.raises(CheckpointSaveError):
        ChainCheckpoint(
            chain_digest="generation",
            completed_fqns=[],
            completed_node_ids=[],
            intermediate_state={"arr": np.array([2.0])},
        ).save(path)

    loaded = ChainCheckpoint.load(path)
    np.testing.assert_array_equal(loaded.intermediate_state["arr"], np.array([1.0]))
