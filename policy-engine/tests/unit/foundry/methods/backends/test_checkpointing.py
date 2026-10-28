from __future__ import annotations

import json
import os
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import numpy as np
import pytest

from polisyos.foundry.methods.backends.checkpointing import (
    ChainCheckpoint,
    CheckpointDigestMismatchError,
    CheckpointingChainExecutor,
    CheckpointLoadError,
    CheckpointSaveError,
    _compute_chain_digest,
)
from polisyos.foundry.methods.base import _stable_digest
from polisyos.foundry.methods.components.composer import (
    CompiledMethodChain,
    MethodNode,
    SemanticValidationLevel,
    ValidationContext,
)


def _validation_context() -> ValidationContext:
    return ValidationContext(
        schema_version=1,
        mode=SemanticValidationLevel.WARN,
        ruleset="polisyos.foundry.composition@1",
        diagnostics_digest=_stable_digest([]),
    )


class _FakeChain(CompiledMethodChain):
    """Typed compiler-built fixture; runtime behavior stays in the test dispatcher."""

    def __init__(self, fqns: list[str]) -> None:
        from types import MappingProxyType

        from polisyos.foundry.methods.base import (
            ComplexityClass,
            ComputeBackend,
            FidelityLevel,
            MethodSignature,
        )
        from polisyos.foundry.methods.components.composer import MethodComposer

        composer = MethodComposer()
        nodes = {}
        for index, fqn in enumerate(fqns):
            path, version = fqn.rsplit("@", 1)
            namespace, name = path.rsplit(".", 1)
            node = MethodNode(uuid4(), fqn, params={}, static_params={}, _insertion_order=index)
            nodes[node.id] = node
            composer._dag.add_node(node)
            composer._signatures[node.id] = MethodSignature(
                name=name,
                namespace=namespace,
                version=version,
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
        compiled = composer.build(validate_semantics=SemanticValidationLevel.WARN)
        super().__init__(
            dag=replace(compiled.dag, nodes=MappingProxyType(nodes)),
            signatures=compiled.signatures,
            execution_order=compiled.execution_order,
            bindings=compiled.bindings,
            warnings=compiled.warnings,
            cache_keys=compiled.cache_keys,
            validation_context=compiled.validation_context,
            linker_config=compiled.linker_config,
        )
        object.__setattr__(self, "_nodes", nodes)

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


def test_execute_rejects_legacy_checkpoint_stub_results(tmp_path) -> None:
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

    with pytest.raises(CheckpointDigestMismatchError, match="lacks execution identity"):
        executor.execute(
            chain,
            initial_state={"value": 0},
            checkpoint=checkpoint,
            seed=11,
        )


def test_execute_resumes_fully_bound_checkpoint_with_native_results(tmp_path) -> None:
    from polisyos.core.observability.determinism import DeterminismTier
    from polisyos.foundry.methods.backends.protocol import (
        MethodResult,
        MethodTiming,
        ReproducibilityInfo,
    )
    from polisyos.foundry.methods.base import ComputeBackend

    chain = _FakeChain(["demo.a@1.0.0", "demo.b@1.0.0"])
    method_class = type(
        "FakeMethod",
        (),
        {
            "signature": SimpleNamespace(backend=ComputeBackend.NUMPY),
        },
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

    producer = CheckpointingChainExecutor(
        checkpoint_dir=tmp_path,
        registry=registry,
        dispatcher=_Dispatcher(),
    )
    producer.execute(chain, initial_state={"value": 0}, seed=11)
    checkpoint = ChainCheckpoint.load(next(tmp_path.glob("*_0000_*.json")))

    consumer = CheckpointingChainExecutor(
        checkpoint_dir=None,
        registry=registry,
        dispatcher=_Dispatcher(),
    )
    result = consumer.execute(
        chain,
        initial_state={"value": 0},
        checkpoint=checkpoint,
        seed=11,
    )

    assert [item.output for _, item in result.node_results] == [{"value": 1}, {"value": 2}]
    assert result.node_results[0][1].reproducibility.seed == 11
    assert result.final_state["value"] == 2
    assert result.reproducibility_contract["determinism_tier"] == "library_deterministic"
    assert result.reproducibility_contract["node_count"] == 2
    assert result.reproducibility_contract["composition_kind"] == "serial"


class _BoundExecutionChain(CompiledMethodChain):
    """Real typed compiler artifact with distinguishing request identities."""

    def __init__(
        self,
        *,
        factor=2,
        static_params=None,
        signature_digest="signature-v1",
        cache_key="cache-v1",
        target_slot="value",
        has_dependency=True,
        second_node_value=0xB74002,
        compatibility_digest="compat-v1",
    ) -> None:
        from polisyos.foundry.methods.base import (
            ComplexityClass,
            ComputeBackend,
            FidelityLevel,
            MethodSignature,
            SlotSpec,
            SlotType,
            Unit,
        )
        from polisyos.foundry.methods.components.composer import MethodComposer

        first_id, second_id = UUID(int=0xB74001), UUID(int=second_node_value)
        slot = lambda name: SlotSpec(name, SlotType.SCALAR, Unit("bound", compatibility_digest))

        def signature(name, *, inputs=(), outputs=(), family="fixture"):
            return MethodSignature(
                name=name,
                namespace="demo",
                version="1.0.0",
                input_slots=frozenset(inputs),
                output_slots=frozenset(outputs),
                parameters=(),
                fidelity=FidelityLevel.LOW,
                complexity=ComplexityClass.O_1,
                backend=ComputeBackend.NUMPY,
                supports_jit=False,
                supports_vmap=False,
                supports_grad=False,
                family=family,
            )

        composer = MethodComposer()
        first = MethodNode(
            first_id,
            "demo.scale@1.0.0",
            params={"factor": factor},
            static_params={"precision": "float64"} if static_params is None else static_params,
            _insertion_order=0,
        )
        second = MethodNode(
            second_id, "demo.finish@1.0.0", params={}, static_params={}, _insertion_order=1
        )
        for node, sig in (
            (first, signature("scale", outputs=(slot("value"),), family=signature_digest)),
            (second, signature("finish", inputs=(slot(target_slot),))),
        ):
            composer._dag.add_node(node)
            composer._signatures[node.id] = sig
        composer.connect(first, second, {"value": target_slot})
        compiled = composer.build(validate_semantics=SemanticValidationLevel.WARN)
        dag = compiled.dag
        if not has_dependency:
            dag = replace(dag, predecessors={first_id: frozenset(), second_id: frozenset()})
        super().__init__(
            dag=dag,
            signatures=compiled.signatures,
            execution_order=compiled.execution_order,
            bindings=compiled.bindings,
            warnings=compiled.warnings,
            cache_keys={first_id: cache_key, second_id: "finish-cache-v1"},
            validation_context=compiled.validation_context,
            linker_config=compiled.linker_config,
        )
        object.__setattr__(self, "_nodes", dict(dag.nodes))
        object.__setattr__(self, "_signatures", dict(compiled.signatures))


def _arithmetic_executor(checkpoint_dir, *, calls=None):
    """Build the real checkpoint executor with a deterministic distinguishing dispatcher."""
    from polisyos.core.observability.determinism import DeterminismTier
    from polisyos.foundry.methods.backends.protocol import (
        MethodResult,
        MethodTiming,
        ReproducibilityInfo,
    )
    from polisyos.foundry.methods.base import ComputeBackend

    signature = SimpleNamespace(backend=ComputeBackend.NUMPY)
    methods = {
        "demo.scale@1.0.0": SimpleNamespace(signature=signature, operation="scale"),
        "demo.finish@1.0.0": SimpleNamespace(signature=signature, operation="finish"),
    }
    registry = SimpleNamespace(get=lambda fqn: methods[fqn])

    class _ArithmeticDispatcher:
        def dispatch(self, *, method_class, signature, state, params, seed):
            if calls is not None:
                calls.append(method_class.operation)
            value = int(state["value"] if isinstance(state, dict) else state)
            if method_class.operation == "scale":
                result_value = value * int(params["factor"]) + seed
            else:
                result_value = value + 1
            return MethodResult(
                output={"value": result_value},
                slot_outputs={"value": result_value},
                timing=MethodTiming(wall_time_ms=1.0),
                reproducibility=ReproducibilityInfo(
                    backend=signature.backend,
                    determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
                    seed=seed,
                ),
            )

    return CheckpointingChainExecutor(
        checkpoint_dir=checkpoint_dir,
        registry=registry,
        dispatcher=_ArithmeticDispatcher(),
    )


def test_effective_request_resume_matches_cold_execution(tmp_path) -> None:
    chain = _BoundExecutionChain()
    initial_state = {"value": 3}
    producer = _arithmetic_executor(tmp_path)
    producer.execute(chain, initial_state=initial_state, seed=11)
    checkpoint = ChainCheckpoint.load(next(tmp_path.glob("*_0000_*.json")))

    resumed = _arithmetic_executor(None).execute(
        chain,
        initial_state=initial_state,
        checkpoint=checkpoint,
        seed=11,
    )
    cold = _arithmetic_executor(None).execute(
        chain,
        initial_state=initial_state,
        seed=11,
    )

    assert resumed.final_state == cold.final_state == {"value": 18}
    assert [result.output for _, result in resumed.node_results] == [
        result.output for _, result in cold.node_results
    ]


@pytest.mark.parametrize(
    "change",
    (
        "node_params",
        "params_per_node",
        "initial_state",
        "seed",
        "static_params",
        "signature",
        "cache_key",
        "binding",
        "binding_compatibility",
        "dag",
        "node_occurrence",
    ),
)
def test_execute_rejects_checkpoint_after_effective_request_change(tmp_path, change) -> None:
    original_chain = _BoundExecutionChain()
    initial_state = {"value": 3}
    producer = _arithmetic_executor(tmp_path)
    producer.execute(original_chain, initial_state=initial_state, seed=11)
    checkpoint = ChainCheckpoint.load(next(tmp_path.glob("*_0000_*.json")))

    current_chain = original_chain
    current_state = initial_state
    current_overrides = {}
    current_seed = 11
    if change == "node_params":
        current_chain = _BoundExecutionChain(factor=3)
    elif change == "params_per_node":
        current_overrides = {original_chain.execution_order[0]: {"factor": 3}}
    elif change == "initial_state":
        current_state = {"value": 4}
    elif change == "seed":
        current_seed = 12
    elif change == "static_params":
        current_chain = _BoundExecutionChain(static_params={"precision": "float32"})
    elif change == "signature":
        current_chain = _BoundExecutionChain(signature_digest="signature-v2")
    elif change == "cache_key":
        current_chain = _BoundExecutionChain(cache_key="cache-v2")
    elif change == "binding":
        current_chain = _BoundExecutionChain(target_slot="alternate-value")
    elif change == "binding_compatibility":
        current_chain = _BoundExecutionChain(compatibility_digest="compat-v2")
    elif change == "dag":
        current_chain = _BoundExecutionChain(has_dependency=False)
    elif change == "node_occurrence":
        current_chain = _BoundExecutionChain(second_node_value=0xB74003)

    # Keep the legacy filename digest and completed prefix identical so the
    # execution-identity check, rather than an earlier guard, decides the case.
    assert _compute_chain_digest(current_chain) == checkpoint.chain_digest
    calls = []
    consumer = _arithmetic_executor(None, calls=calls)

    with pytest.raises(CheckpointDigestMismatchError, match="execution identity|validation"):
        consumer.execute(
            current_chain,
            initial_state=current_state,
            params_per_node=current_overrides,
            checkpoint=checkpoint,
            seed=current_seed,
        )
    assert calls == []


def test_execute_rejects_checkpoint_with_invalid_completed_prefix(tmp_path) -> None:
    chain = _BoundExecutionChain()
    producer = _arithmetic_executor(tmp_path)
    producer.execute(chain, initial_state={"value": 3}, seed=11)
    checkpoint = ChainCheckpoint.load(next(tmp_path.glob("*_0000_*.json")))
    checkpoint.completed_node_ids[0] = str(UUID(int=0xB74099))

    with pytest.raises(CheckpointLoadError, match="not the current execution prefix"):
        _arithmetic_executor(None).execute(
            chain,
            initial_state={"value": 3},
            checkpoint=checkpoint,
            seed=11,
        )


def test_execution_identity_removal_control_reproduces_stale_resume(tmp_path, monkeypatch) -> None:
    def _structural_only_digest(chain, *, initial_state, params_per_node, seed):
        del initial_state, params_per_node, seed
        return _compute_chain_digest(chain)

    monkeypatch.setattr(
        "polisyos.foundry.methods.backends.checkpointing._compute_execution_digest",
        _structural_only_digest,
    )
    original_chain = _BoundExecutionChain(factor=2)
    producer = _arithmetic_executor(tmp_path)
    producer.execute(original_chain, initial_state={"value": 3}, seed=11)
    checkpoint = ChainCheckpoint.load(next(tmp_path.glob("*_0000_*.json")))

    changed_chain = _BoundExecutionChain(factor=3)
    assert checkpoint.execution_digest == checkpoint.chain_digest
    assert checkpoint.execution_digest is not None

    stale_resume = _arithmetic_executor(None).execute(
        changed_chain,
        initial_state={"value": 3},
        checkpoint=checkpoint,
        seed=11,
    )
    cold = _arithmetic_executor(None).execute(
        changed_chain,
        initial_state={"value": 3},
        seed=11,
    )

    assert stale_resume.final_state == {"value": 18}
    assert cold.final_state == {"value": 21}
    assert stale_resume.final_state != cold.final_state

    observation_root = os.environ.get("E02_B_PROPERTY_REMOVAL_OBSERVATION")
    if observation_root:
        observation_dir = Path(observation_root)
        observation_dir.mkdir(parents=True, exist_ok=True)
        observation = {
            "observation_schema": "e02.prepared_b.removal_observation.v1",
            "case_id": "b74-effective-checkpoint-input-binding",
            "checkpoint_execution_digest": checkpoint.execution_digest,
            "checkpoint_structural_chain_digest": checkpoint.chain_digest,
            "stale_resume_final_state": stale_resume.final_state,
            "cold_execution_final_state": cold.final_state,
            "changed_chain_factor": changed_chain.get_node(changed_chain.execution_order[0]).params[
                "factor"
            ],
            "original_chain_factor": original_chain.get_node(
                original_chain.execution_order[0]
            ).params["factor"],
        }
        (observation_dir / "b74-effective-checkpoint-input-binding.json").write_text(
            json.dumps(observation, sort_keys=True) + "\n", encoding="utf-8"
        )
