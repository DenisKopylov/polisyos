"""Checkpoint identity witnesses using actual registry methods and required edges."""

from __future__ import annotations

from dataclasses import replace
from typing import ClassVar
from uuid import uuid4

import pytest

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.methods.backends.checkpointing import (
    ChainCheckpoint,
    CheckpointArtifactContext,
    CheckpointDigestMismatchError,
    CheckpointError,
    CheckpointIdentityError,
    CheckpointingChainExecutor,
)
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.components.composer import MethodComposer
from polisyos.foundry.methods.selection.registry import MethodRegistry


def _slot(name):
    return SlotSpec(name, SlotType.SCALAR, Unit("count", "1"), shape=())


_PRODUCER_SIGNATURE = MethodSignature(
    name="source",
    namespace="tests.checkpoint_identity",
    version="1.0.0",
    input_slots=frozenset(),
    output_slots=frozenset({_slot("product")}),
    parameters=(ParameterSpec("factor", default=2, is_static=True),),
    backend=ComputeBackend.NUMPY,
    fidelity=FidelityLevel.LOW,
    complexity=ComplexityClass.O_1,
    supports_jit=False,
    supports_vmap=False,
    supports_grad=False,
)
_CONSUMER_SIGNATURE = replace(
    _PRODUCER_SIGNATURE,
    name="consumer",
    input_slots=frozenset({_slot("operand")}),
    output_slots=frozenset({_slot("total")}),
    parameters=(ParameterSpec("increment", default=1),),
    requires=frozenset({_PRODUCER_SIGNATURE.fqn}),
)
_METADATA = MethodMetadata(description="Checkpoint identity arithmetic", tags=frozenset({"test"}))


class _Original:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": state["x"] * params["factor"]}


class _Replacement:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": state["x"] * (params["factor"] + 1)}


class _ChangedABI:
    signature: ClassVar = replace(
        _PRODUCER_SIGNATURE, parameters=(ParameterSpec("factor", default=3, is_static=True),)
    )
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": state["x"] * params["factor"]}


class _Consumer:
    signature: ClassVar = _CONSUMER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"total": state + params["increment"]}


class _Unrelated:
    signature: ClassVar = replace(_PRODUCER_SIGNATURE, name="unrelated")
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"product": state["x"] + params["factor"]}


class _AttributeSource:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA
    multiplier: ClassVar = 2

    @staticmethod
    def pure_step(state, params):
        return {"product": state["x"] * _AttributeSource.multiplier}


class _ReplacementConsumer:
    signature: ClassVar = _CONSUMER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state, params):
        return {"total": state + params["increment"] + 10}


class _MutatingSource:
    signature: ClassVar = _PRODUCER_SIGNATURE
    metadata: ClassVar = _METADATA
    multiplier: ClassVar = 2

    @staticmethod
    def pure_step(state, params):
        product = state["x"] * _MutatingSource.multiplier
        _MutatingSource.multiplier += 1
        return {"product": product}


class _UnavailableRuntimeSource(_Original):
    runtime_stack: ClassVar = ("e02-intentionally-uninstalled-dependency",)


def _closed_source(factor):
    class ClosedSource:
        signature: ClassVar = _PRODUCER_SIGNATURE
        metadata: ClassVar = _METADATA

        @staticmethod
        def pure_step(state, params):
            return {"product": state["x"] * factor}

    return ClosedSource


class _RecordingDispatcher:
    def __init__(self):
        self.calls = []

    def dispatch(self, **kwargs):
        self.calls.append(kwargs["signature"].fqn)
        return MethodDispatcher.get_instance().dispatch(**kwargs)


def _chain():
    registry = MethodRegistry._create_fresh()
    registry.register(_Original)
    registry.register(_Consumer)
    composer = MethodComposer(registry=registry)
    first = composer.add(_Original.signature.fqn)
    second = composer.add(_Consumer.signature.fqn)
    composer.connect(first, second, {"product": "operand"})
    chain = composer.build(validate_semantics=False)
    assert chain.dag.predecessors[second.id] == frozenset({first.id})
    return chain, registry


@pytest.mark.parametrize("replacement", [_Replacement, _ChangedABI], ids=["source", "abi"])
def test_actual_registry_source_or_abi_replacement_refuses_original_history(tmp_path, replacement):
    chain, registry = _chain()
    dispatcher = _RecordingDispatcher()
    producer = CheckpointingChainExecutor(
        registry=registry, dispatcher=dispatcher, checkpoint_dir=tmp_path
    )
    original = producer.execute(chain, initial_state={"x": 3}, seed=7)
    assert [row.output for _, row in original.node_results] == [{"product": 6}, {"total": 7}]
    checkpoint = ChainCheckpoint.load(next(tmp_path.glob("*_0001_*.json")))
    registry.register(replacement, override=True)
    if replacement is _Replacement:
        cold = CheckpointingChainExecutor(registry=registry).execute(
            chain, initial_state={"x": 3}, seed=7
        )
        assert cold.final_state["total"] == 10
        assert (
            replacement.signature.stable_digest()
            == chain.get_signature(chain.execution_order[0]).stable_digest()
        )
    dispatcher.calls.clear()
    with pytest.raises(CheckpointDigestMismatchError):
        producer.execute(chain, initial_state={"x": 3}, checkpoint=checkpoint, seed=7)
    assert dispatcher.calls == []


def test_unrelated_registration_preserves_exact_effective_checkpoint_request(tmp_path):
    chain, registry = _chain()
    dispatcher = _RecordingDispatcher()
    executor = CheckpointingChainExecutor(
        registry=registry, dispatcher=dispatcher, checkpoint_dir=tmp_path
    )
    original = executor.execute(chain, initial_state={"x": 3}, seed=7)
    checkpoint = ChainCheckpoint.load(next(tmp_path.glob("*_0001_*.json")))
    registry.register(_Unrelated)
    dispatcher.calls.clear()
    resumed = executor.execute(chain, initial_state={"x": 3}, checkpoint=checkpoint, seed=7)
    assert dispatcher.calls == []
    assert resumed.final_state["total"] == 7
    assert [row.reproducibility for _, row in resumed.node_results] == [
        row.reproducibility for _, row in original.node_results
    ]


def _put(store, payload, *, kind="test.checkpoint_identity.input", producer="original"):
    ref = store.put_bytes(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            producer=ProducerInfo(component="test.checkpoint_identity", version=producer),
        ),
    )
    # A default CAS selector is legitimate for general reads. This strict
    # checkpoint declaration explicitly selects the corresponding stored view.
    manifest = store.get_manifest(ref)
    return ArtifactRef(
        artifact_id=ref.artifact_id,
        kind=ref.kind,
        media_type=ref.media_type,
        manifest_profile_sha256=artifact_manifest_profile_sha256(manifest),
    )


def _strict_context(store, chain):
    first = chain.execution_order[0]
    return CheckpointArtifactContext(
        input_refs={"x": _put(store, b'{"x":3}')},
        config_refs={
            "factor": _put(store, b'{"factor":2}', kind="test.checkpoint_identity.config")
        },
        origin_ref=_put(
            store, b'{"acquisition":"fixture-a"}', kind="test.checkpoint_identity.origin"
        ),
        dependency_refs={
            "abi": _put(
                store, b'{"dependency":"1.0.0"}', kind="test.checkpoint_identity.dependency"
            )
        },
        cache_refs={first: _put(store, b'{"product":6}', kind="test.checkpoint_identity.output")},
    )


def test_exact_selected_artifact_view_resumes_real_required_suffix_and_joint_generation(tmp_path):
    import json

    chain, registry = _chain()
    store = FileSystemCAS(tmp_path / "cas").with_ambient_ownership_enforcement()
    dispatcher = _RecordingDispatcher()
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        context = _strict_context(store, chain)
        executor = CheckpointingChainExecutor(
            registry=registry,
            dispatcher=dispatcher,
            checkpoint_dir=tmp_path / "checkpoints",
            artifact_store=store,
        )
        original = executor.execute(chain, initial_state={"x": 3}, seed=7, artifact_context=context)
        path = next((tmp_path / "checkpoints").glob("*_0000_*.json"))
        pointer = json.loads(path.read_text())
        snapshot = json.loads((path.parent / pointer["snapshot_ref"]).read_text())
        checkpoint = ChainCheckpoint.load(path)
        assert snapshot["completed_node_ids"] == [str(chain.execution_order[0])]
        assert snapshot["intermediate_state"]["product"] == 6
        assert snapshot["node_results"][0]["output"] == {"product": 6}
        assert snapshot["identity_snapshot"] == checkpoint.identity_snapshot
        assert checkpoint.identity_snapshot["scope"] == {
            "tenant_id": "tenant-a",
            "cell_id": "cell-a",
        }
        cache_ref = checkpoint.identity_snapshot["artifacts"]["cache_refs"][
            str(chain.execution_order[0])
        ]
        assert (
            cache_ref["ref"][-1]
            == context.cache_refs[chain.execution_order[0]].manifest_profile_sha256
        )
        dispatcher.calls.clear()
        resumed = executor.execute(
            chain, initial_state={"x": 3}, checkpoint=checkpoint, seed=7, artifact_context=context
        )
    assert dispatcher.calls == [_CONSUMER_SIGNATURE.fqn]
    assert resumed.final_state["total"] == 7
    assert [row.output for _, row in resumed.node_results] == [
        row.output for _, row in original.node_results
    ]
    assert [row.reproducibility.seed for _, row in resumed.node_results] == [7, 7]
    assert resumed.history_complete


@pytest.mark.parametrize(
    "change",
    [
        "input-content",
        "input-view",
        "config-content",
        "config-origin",
        "same-content-new-origin",
        "dependency",
        "cache-content",
        "cache-view",
        "input-role",
        "legacy-profile",
    ],
)
def test_actual_cas_identity_change_refuses_before_required_suffix(tmp_path, change):
    chain, registry = _chain()
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    dispatcher = _RecordingDispatcher()
    executor = CheckpointingChainExecutor(
        registry=registry,
        dispatcher=dispatcher,
        checkpoint_dir=tmp_path / "checkpoints",
        artifact_store=store,
    )
    executor.execute(chain, initial_state={"x": 3}, seed=7, artifact_context=context)
    path = next((tmp_path / "checkpoints").glob("*_0000_*.json"))
    checkpoint = ChainCheckpoint.load(path)
    selected_bytes = path.read_bytes()
    first = chain.execution_order[0]
    if change == "input-content":
        changed = context.model_copy(update={"input_refs": {"x": _put(store, b'{"x":4}')}})
    elif change == "input-view":
        changed = context.model_copy(
            update={"input_refs": {"x": _put(store, b'{"x":3}', kind="test.changed.input")}}
        )
        assert changed.input_refs["x"].artifact_id == context.input_refs["x"].artifact_id
    elif change == "config-content":
        changed = context.model_copy(
            update={
                "config_refs": {
                    "factor": _put(store, b'{"factor":3}', kind="test.checkpoint_identity.config")
                }
            }
        )
    elif change == "config-origin":
        changed = context.model_copy(
            update={
                "config_refs": {
                    "factor": _put(
                        store,
                        b'{"factor":2}',
                        kind="test.checkpoint_identity.config",
                        producer="replacement",
                    )
                }
            }
        )
    elif change == "same-content-new-origin":
        changed = context.model_copy(
            update={
                "origin_ref": _put(
                    store,
                    b'{"acquisition":"fixture-a"}',
                    kind="test.checkpoint_identity.origin",
                    producer="replacement",
                )
            }
        )
        assert changed.origin_ref.artifact_id == context.origin_ref.artifact_id
        assert (
            changed.origin_ref.manifest_profile_sha256 != context.origin_ref.manifest_profile_sha256
        )
    elif change == "dependency":
        changed = context.model_copy(
            update={
                "dependency_refs": {
                    "abi": _put(
                        store, b'{"dependency":"2.0.0"}', kind="test.checkpoint_identity.dependency"
                    )
                }
            }
        )
    elif change == "cache-content":
        changed = context.model_copy(
            update={
                "cache_refs": {
                    first: _put(store, b'{"product":9}', kind="test.checkpoint_identity.output")
                }
            }
        )
    elif change == "cache-view":
        changed = context.model_copy(
            update={
                "cache_refs": {first: _put(store, b'{"product":6}', kind="test.changed.output")}
            }
        )
    elif change == "input-role":
        changed = context.model_copy(
            update={"input_refs": {"different-role": context.input_refs["x"]}}
        )
    else:
        changed = None
    dispatcher.calls.clear()
    with pytest.raises(CheckpointDigestMismatchError):
        executor.execute(
            chain, initial_state={"x": 3}, checkpoint=checkpoint, seed=7, artifact_context=changed
        )
    assert dispatcher.calls == []
    assert path.read_bytes() == selected_bytes
    assert store.get_bytes(context.input_refs["x"]) == b'{"x":3}'


@pytest.mark.parametrize("scope", [("tenant-b", "cell-a"), ("tenant-a", "cell-b")])
def test_protected_checkpoint_refuses_changed_actual_ambient_scope(tmp_path, scope):
    chain, registry = _chain()
    store = FileSystemCAS(tmp_path / "cas").with_ambient_ownership_enforcement()
    dispatcher = _RecordingDispatcher()
    executor = CheckpointingChainExecutor(
        registry=registry,
        dispatcher=dispatcher,
        checkpoint_dir=tmp_path / "checkpoints",
        artifact_store=store,
    )
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        context = _strict_context(store, chain)
        executor.execute(chain, initial_state={"x": 3}, seed=7, artifact_context=context)
    checkpoint = ChainCheckpoint.load(next((tmp_path / "checkpoints").glob("*_0000_*.json")))
    dispatcher.calls.clear()
    with tenant_scope(None, tenant_id=scope[0], cell_id=scope[1]), pytest.raises(CheckpointError):
        executor.execute(
            chain, initial_state={"x": 3}, checkpoint=checkpoint, seed=7, artifact_context=context
        )
    assert dispatcher.calls == []


@pytest.mark.parametrize(
    "invalid",
    [
        "no-store",
        "selector-missing",
        "unknown-cache-node",
        "tampered-blob",
        "missing-selected-view",
        "forged-kind",
    ],
)
def test_strict_unestablished_ref_identity_refuses_before_any_dispatch(tmp_path, invalid):
    chain, registry = _chain()
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    ref = context.input_refs["x"]
    if invalid == "selector-missing":
        context = context.model_copy(
            update={"input_refs": {"x": ref.model_copy(update={"manifest_profile_sha256": None})}}
        )
    elif invalid == "unknown-cache-node":
        context = context.model_copy(
            update={"cache_refs": {uuid4(): next(iter(context.cache_refs.values()))}}
        )
    elif invalid == "tampered-blob":
        blob, _manifest = store._paths(ref.artifact_id)
        blob.write_bytes(b'{"x":9}')
    elif invalid == "missing-selected-view":
        store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256).unlink()
    elif invalid == "forged-kind":
        context = context.model_copy(
            update={"input_refs": {"x": ref.model_copy(update={"kind": "forged.kind"})}}
        )
    dispatcher = _RecordingDispatcher()
    executor = CheckpointingChainExecutor(
        registry=registry,
        dispatcher=dispatcher,
        checkpoint_dir=tmp_path / "checkpoints",
        artifact_store=None if invalid == "no-store" else store,
    )
    with pytest.raises(CheckpointIdentityError):
        executor.execute(chain, initial_state={"x": 3}, seed=7, artifact_context=context)
    assert dispatcher.calls == []
    assert not (tmp_path / "checkpoints").exists()


def test_strict_unavailable_actual_source_is_typed_refusal_not_artifact_authority(tmp_path):
    chain, registry = _chain()
    namespace = {"signature": _PRODUCER_SIGNATURE, "metadata": _METADATA}
    exec(
        "def pure_step(state, params):\n    return {'product': state['x'] * params['factor']}\n",
        namespace,
    )
    unknown = type(
        "UninspectableMethod",
        (),
        {
            "signature": _PRODUCER_SIGNATURE,
            "metadata": _METADATA,
            "pure_step": staticmethod(namespace["pure_step"]),
        },
    )
    registry.register(unknown, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    dispatcher = _RecordingDispatcher()
    with pytest.raises(CheckpointIdentityError, match="source identity is unavailable"):
        CheckpointingChainExecutor(
            registry=registry, dispatcher=dispatcher, artifact_store=store
        ).execute(chain, initial_state={"x": 3}, seed=7, artifact_context=context)
    assert dispatcher.calls == []


def test_same_source_signature_new_immutable_capture_refuses_actual_stale_output(tmp_path):
    chain, registry = _chain()
    registry.register(_closed_source(2), override=True)
    dispatcher = _RecordingDispatcher()
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    executor = CheckpointingChainExecutor(
        registry=registry,
        dispatcher=dispatcher,
        artifact_store=store,
        checkpoint_dir=tmp_path / "checkpoints",
    )
    executor.execute(chain, initial_state={"x": 3}, seed=7, artifact_context=context)
    checkpoint = ChainCheckpoint.load(next((tmp_path / "checkpoints").glob("*_0000_*.json")))
    registry.register(_closed_source(3), override=True)
    cold = CheckpointingChainExecutor(registry=registry).execute(
        chain, initial_state={"x": 3}, seed=7
    )
    assert cold.final_state["total"] == 10
    dispatcher.calls.clear()
    with pytest.raises(CheckpointDigestMismatchError):
        executor.execute(
            chain, initial_state={"x": 3}, checkpoint=checkpoint, seed=7, artifact_context=context
        )
    assert dispatcher.calls == []


def test_source_class_attribute_change_refuses_actual_stale_output(tmp_path):
    chain, registry = _chain()
    registry.register(_AttributeSource, override=True)
    dispatcher = _RecordingDispatcher()
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    executor = CheckpointingChainExecutor(
        registry=registry,
        dispatcher=dispatcher,
        artifact_store=store,
        checkpoint_dir=tmp_path / "checkpoints",
    )
    executor.execute(chain, initial_state={"x": 3}, seed=7, artifact_context=context)
    checkpoint = ChainCheckpoint.load(next((tmp_path / "checkpoints").glob("*_0000_*.json")))
    try:
        _AttributeSource.multiplier = 3
        cold = CheckpointingChainExecutor(registry=registry).execute(
            chain, initial_state={"x": 3}, seed=7
        )
        assert cold.final_state["total"] == 10
        dispatcher.calls.clear()
        with pytest.raises(CheckpointDigestMismatchError):
            executor.execute(
                chain,
                initial_state={"x": 3},
                checkpoint=checkpoint,
                seed=7,
                artifact_context=context,
            )
        assert dispatcher.calls == []
    finally:
        _AttributeSource.multiplier = 2


@pytest.mark.parametrize("descriptor", ["static", "class", "method", "property"])
def test_actual_class_helper_replacement_refuses_stale_required_resume(tmp_path, descriptor):
    """The same class/entrypoint calls a replaced descriptor in real arithmetic."""

    def original_helper(*args):
        return 2

    def changed_helper(*args):
        return 3

    wrappers = {
        "static": staticmethod,
        "class": classmethod,
        "method": lambda fn: fn,
        "property": property,
    }

    class Source:
        signature: ClassVar = _PRODUCER_SIGNATURE
        metadata: ClassVar = _METADATA

        @staticmethod
        def pure_step(state, params):
            instance = Source()
            factor = instance.helper if descriptor == "property" else instance.helper()
            return {"product": state["x"] * factor}

    Source.helper = wrappers[descriptor](original_helper)
    chain, registry = _chain()
    registry.register(Source, override=True)
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
    path = next((tmp_path / "checkpoints").glob("*_0000_*.json"))
    checkpoint = ChainCheckpoint.load(path)
    pointer = path.read_bytes()
    unchanged = executor.execute(
        chain, initial_state={"x": 3}, checkpoint=checkpoint, seed=7, artifact_context=context
    )
    assert original.final_state["total"] == unchanged.final_state["total"] == 7
    assert unchanged.history_complete
    Source.helper = wrappers[descriptor](changed_helper)
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
    assert path.read_bytes() == pointer


def test_actual_consumed_frozen_metadata_change_refuses_stale_resume(tmp_path):
    class Source:
        signature: ClassVar = _PRODUCER_SIGNATURE
        metadata: ClassVar = MethodMetadata(description="2")

        @staticmethod
        def pure_step(state, params):
            return {"product": state["x"] * int(Source.metadata.description)}

    chain, registry = _chain()
    registry.register(Source, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    dispatcher = _RecordingDispatcher()
    executor = CheckpointingChainExecutor(
        registry=registry,
        dispatcher=dispatcher,
        artifact_store=store,
        checkpoint_dir=tmp_path / "checkpoints",
    )
    assert (
        executor.execute(chain, initial_state={"x": 3}, artifact_context=context).final_state[
            "total"
        ]
        == 7
    )
    checkpoint = ChainCheckpoint.load(next((tmp_path / "checkpoints").glob("*_0000_*.json")))
    Source.metadata = MethodMetadata(description="3")
    assert (
        CheckpointingChainExecutor(registry=registry)
        .execute(chain, initial_state={"x": 3})
        .final_state["total"]
        == 10
    )
    dispatcher.calls.clear()
    with pytest.raises(CheckpointDigestMismatchError):
        executor.execute(
            chain, initial_state={"x": 3}, checkpoint=checkpoint, artifact_context=context
        )
    assert dispatcher.calls == []


def test_mutable_source_capture_is_explicit_strict_boundary(tmp_path):
    chain, registry = _chain()
    factors = [2]

    class MutableSource:
        signature: ClassVar = _PRODUCER_SIGNATURE
        metadata: ClassVar = _METADATA

        @staticmethod
        def pure_step(state, params):
            return {"product": state["x"] * factors[0]}

    registry.register(MutableSource, override=True)
    assert (
        CheckpointingChainExecutor(registry=registry)
        .execute(chain, initial_state={"x": 3})
        .final_state["total"]
        == 7
    )
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    dispatcher = _RecordingDispatcher()
    with pytest.raises(CheckpointIdentityError, match="source identity is unavailable for list"):
        CheckpointingChainExecutor(
            registry=registry, dispatcher=dispatcher, artifact_store=store
        ).execute(chain, initial_state={"x": 3}, artifact_context=context)
    assert dispatcher.calls == []


def test_registry_change_during_actual_producer_uses_pinned_source_snapshot(tmp_path):
    chain, registry = _chain()
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    used_classes = []

    class ReplacingDispatcher:
        def dispatch(self, **kwargs):
            used_classes.append(kwargs["method_class"])
            result = MethodDispatcher.get_instance().dispatch(**kwargs)
            if kwargs["signature"].fqn == _PRODUCER_SIGNATURE.fqn:
                registry.register(_ReplacementConsumer, override=True)
            return result

    result = CheckpointingChainExecutor(
        registry=registry,
        dispatcher=ReplacingDispatcher(),
        artifact_store=store,
        checkpoint_dir=tmp_path / "checkpoints",
    ).execute(chain, initial_state={"x": 3}, seed=7, artifact_context=context)
    assert result.final_state["total"] == 7
    assert used_classes == [_Original, _Consumer]
    assert registry.get(_CONSUMER_SIGNATURE.fqn) is _ReplacementConsumer
    # Removing the race produces the same genuine arithmetic/history path.
    assert (
        CheckpointingChainExecutor(registry=registry)
        .execute(chain, initial_state={"x": 3})
        .final_state["total"]
        == 17
    )


def test_actual_source_mutation_during_dispatch_cannot_ack_old_identity(tmp_path):
    chain, registry = _chain()
    registry.register(_MutatingSource, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    dispatcher = _RecordingDispatcher()
    try:
        with pytest.raises(CheckpointIdentityError, match="changed during"):
            CheckpointingChainExecutor(
                registry=registry,
                dispatcher=dispatcher,
                artifact_store=store,
                checkpoint_dir=tmp_path / "checkpoints",
            ).execute(chain, initial_state={"x": 3}, seed=7, artifact_context=context)
        assert _MutatingSource.multiplier == 3  # Actual producer ran.
        assert dispatcher.calls == [_PRODUCER_SIGNATURE.fqn]
        assert not (tmp_path / "checkpoints").exists()
    finally:
        _MutatingSource.multiplier = 2


def test_declared_runtime_dependency_without_exact_version_refuses_strict_dispatch(tmp_path):
    chain, registry = _chain()
    registry.register(_UnavailableRuntimeSource, override=True)
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    dispatcher = _RecordingDispatcher()
    with pytest.raises(CheckpointIdentityError, match="runtime dependency version is unavailable"):
        CheckpointingChainExecutor(
            registry=registry, dispatcher=dispatcher, artifact_store=store
        ).execute(chain, initial_state={"x": 3}, seed=7, artifact_context=context)
    assert dispatcher.calls == []


def test_operational_checkpoint_policy_change_reuses_actual_numerical_prefix(tmp_path):
    chain, registry = _chain()
    store = FileSystemCAS(tmp_path / "cas")
    context = _strict_context(store, chain)
    original = CheckpointingChainExecutor(
        registry=registry,
        checkpoint_dir=tmp_path / "checkpoints",
        artifact_store=store,
        checkpoint_every=1,
        fail_on_checkpoint_error=True,
    ).execute(chain, initial_state={"x": 3}, seed=7, artifact_context=context)
    checkpoint = ChainCheckpoint.load(next((tmp_path / "checkpoints").glob("*_0000_*.json")))
    dispatcher = _RecordingDispatcher()
    resumed = CheckpointingChainExecutor(
        registry=registry,
        dispatcher=dispatcher,
        checkpoint_dir=tmp_path / "resumed",
        artifact_store=store,
        checkpoint_every=999,
        fail_on_checkpoint_error=False,
    ).execute(
        chain, initial_state={"x": 3}, checkpoint=checkpoint, seed=7, artifact_context=context
    )
    assert dispatcher.calls == [_CONSUMER_SIGNATURE.fqn]
    assert resumed.final_state["total"] == original.final_state["total"] == 7
    assert [row.output for _, row in resumed.node_results] == [
        row.output for _, row in original.node_results
    ]
    assert resumed.history_complete
    persisted = ChainCheckpoint.load(next((tmp_path / "resumed").glob("*_0001_*.json")))
    assert persisted.identity_snapshot == checkpoint.identity_snapshot
