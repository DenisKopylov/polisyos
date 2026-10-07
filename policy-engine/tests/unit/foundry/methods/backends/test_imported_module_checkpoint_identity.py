"""Real checkpoint consumers distinguish imported-member code from module versions."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import Any, ClassVar

import pytest

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.foundry.methods.backends.checkpointing import (
    ChainCheckpoint,
    CheckpointArtifactContext,
    CheckpointDigestMismatchError,
    CheckpointIdentityError,
    CheckpointingChainExecutor,
)
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

_IMPORTED_HELPERS = math


def _original_increment(value: int, effect_path: str) -> int:
    with open(effect_path, "a", encoding="utf-8") as output:
        output.write("original\n")
    return value + 1


def _replacement_increment(value: int, effect_path: str) -> int:
    with open(effect_path, "a", encoding="utf-8") as output:
        output.write("replacement\n")
    return value + 101


def _slot(name: str) -> SlotSpec:
    return SlotSpec(name, SlotType.SCALAR, Unit("count", "1"), shape=())


_SOURCE_SIGNATURE = MethodSignature(
    name="multiply",
    namespace="tests.imported_checkpoint",
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
    _SOURCE_SIGNATURE,
    name="imported_increment",
    input_slots=frozenset({_slot("operand")}),
    output_slots=frozenset({_slot("total")}),
    parameters=(ParameterSpec("effect_path", default=""),),
    requires=frozenset({_SOURCE_SIGNATURE.fqn}),
)
_METADATA = MethodMetadata(description="Imported-helper checkpoint consumer", tags=frozenset())


class _Source:
    signature: ClassVar = _SOURCE_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state: dict[str, Any], params: dict[str, Any]) -> dict[str, int]:
        return {"product": state["x"] * params["factor"]}


class _ImportedConsumer:
    signature: ClassVar = _CONSUMER_SIGNATURE
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state: int, params: dict[str, Any]) -> dict[str, int]:
        return {"total": _IMPORTED_HELPERS._e02_b74_checkpoint_helper(state, params["effect_path"])}


class _BuiltinConsumer:
    signature: ClassVar = replace(_CONSUMER_SIGNATURE, name="builtin_absolute")
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state: int, params: dict[str, Any]) -> dict[str, float]:
        return {"total": _IMPORTED_HELPERS.fabs(state)}


class _DynamicImportConsumer:
    signature: ClassVar = replace(_CONSUMER_SIGNATURE, name="dynamic_import_increment")
    metadata: ClassVar = _METADATA

    @staticmethod
    def pure_step(state: int, params: dict[str, Any]) -> dict[str, int]:
        return {
            "total": __import__("math")._e02_b74_checkpoint_helper(state, params["effect_path"])
        }


def _chain(consumer: type):
    registry = MethodRegistry._create_fresh()
    registry.register(_Source)
    registry.register(consumer)
    composer = MethodComposer(registry=registry)
    first = composer.add(_Source.signature.fqn)
    second = composer.add(consumer.signature.fqn)
    composer.connect(first, second, {"product": "operand"})
    return composer.build(validate_semantics=False), registry, second.id


def _selected_input(store: FileSystemCAS) -> ArtifactRef:
    ref = store.put_bytes(
        b'{"x":3}',
        PutOptions(
            kind="test.imported_checkpoint.input",
            media_type="application/json",
            producer=ProducerInfo(component="test.imported_checkpoint", version="1.0.0"),
        ),
    )
    manifest = store.get_manifest(ref)
    return ArtifactRef(
        artifact_id=ref.artifact_id,
        kind=ref.kind,
        media_type=ref.media_type,
        manifest_profile_sha256=artifact_manifest_profile_sha256(manifest),
    )


def _saved_prefix(tmp_path: Path, consumer: type, effect_path: Path):
    chain, registry, second_id = _chain(consumer)
    store = FileSystemCAS(tmp_path / "cas")
    context = CheckpointArtifactContext(input_refs={"x": _selected_input(store)})
    params = {second_id: {"effect_path": str(effect_path)}}
    executor = CheckpointingChainExecutor(
        registry=registry,
        artifact_store=store,
        checkpoint_dir=tmp_path / "checkpoints",
    )
    original = executor.execute(
        chain, initial_state={"x": 3}, params_per_node=params, seed=7, artifact_context=context
    )
    path = next((tmp_path / "checkpoints").glob("*_0000_*.json"))
    checkpoint = ChainCheckpoint.load(path)
    assert checkpoint.n_completed == 1
    assert checkpoint.completed_node_ids == [str(chain.execution_order[0])]
    assert checkpoint.intermediate_state["product"] == 6
    assert checkpoint.node_results[0]["output"] == {"product": 6}
    fresh_store = FileSystemCAS(tmp_path / "cas")
    assert fresh_store.get_bytes(context.input_refs["x"]) == b'{"x":3}'
    reopened = CheckpointingChainExecutor(registry=registry, artifact_store=fresh_store)
    return original, chain, params, context, checkpoint, path, reopened


def test_unchanged_imported_member_resumes_real_persisted_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr(math, "_e02_b74_checkpoint_helper", _original_increment, raising=False)
    effects = tmp_path / "effects.txt"
    original, chain, params, context, checkpoint, path, reopened = _saved_prefix(
        tmp_path, _ImportedConsumer, effects
    )
    pointer = path.read_bytes()
    resumed = reopened.execute(
        chain,
        initial_state={"x": 3},
        params_per_node=params,
        checkpoint=checkpoint,
        seed=7,
        artifact_context=context,
    )
    assert original.final_state["total"] == resumed.final_state["total"] == 3 * 2 + 1
    assert resumed.history_complete
    assert effects.read_text() == "original\noriginal\n"
    assert path.read_bytes() == pointer


def test_same_version_imported_member_change_refuses_before_replacement_effect(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(math, "_e02_b74_checkpoint_helper", _original_increment, raising=False)
    effects = tmp_path / "effects.txt"
    original, chain, params, context, checkpoint, path, reopened = _saved_prefix(
        tmp_path, _ImportedConsumer, effects
    )
    assert original.final_state["total"] == 7
    pointer = path.read_bytes()
    original_effects = effects.read_bytes()
    original_name = math.__name__
    # Keep the actual imported module and runtime version. Change only the
    # callable member which the not-yet-completed consumer actually resolves.
    monkeypatch.setattr(math, "_e02_b74_checkpoint_helper", _replacement_increment)
    assert math.__name__ == original_name
    try:
        with pytest.raises((CheckpointDigestMismatchError, CheckpointIdentityError)):
            wrongly_resumed = reopened.execute(
                chain,
                initial_state={"x": 3},
                params_per_node=params,
                checkpoint=checkpoint,
                seed=7,
                artifact_context=context,
            )
            # This branch exists only when the refusal property is absent.
            print("WRONGLY_RESUMED_TOTAL", wrongly_resumed.final_state["total"])  # noqa: T201
    finally:
        # Retain the physical-effect discriminator in the deciding pytest log.
        print("REPLACEMENT_EFFECTS", effects.read_text().splitlines())  # noqa: T201
    assert effects.read_bytes() == original_effects
    assert path.read_bytes() == pointer
    # This direct actual method consumer establishes that the replacement is
    # substantive. It runs only after the checkpoint refusal assertions pass.
    cold = _ImportedConsumer.pure_step(6, {"effect_path": str(effects)})
    assert cold["total"] == 107
    assert effects.read_text().splitlines()[-1] == "replacement"


def test_unchanged_imported_builtin_has_real_cold_resume_parity(tmp_path):
    original, chain, params, context, checkpoint, path, reopened = _saved_prefix(
        tmp_path, _BuiltinConsumer, tmp_path / "unused-effects.txt"
    )
    pointer = path.read_bytes()
    resumed = reopened.execute(
        chain,
        initial_state={"x": 3},
        params_per_node=params,
        checkpoint=checkpoint,
        seed=7,
        artifact_context=context,
    )
    assert original.final_state["total"] == resumed.final_state["total"] == 6.0
    assert path.read_bytes() == pointer


def test_dynamic_import_is_refused_before_any_checkpoint_consumer_effect(tmp_path, monkeypatch):
    monkeypatch.setattr(math, "_e02_b74_checkpoint_helper", _original_increment, raising=False)
    effects = tmp_path / "dynamic-effects.txt"
    try:
        original, chain, params, context, checkpoint, path, reopened = _saved_prefix(
            tmp_path, _DynamicImportConsumer, effects
        )
    except CheckpointIdentityError as error:
        # The declared static graph has no identity for namespace-producing
        # runtime lookup. Correct refusal must precede every physical body.
        assert "source identity is unavailable" in str(error)
        assert not effects.exists()
        assert not (tmp_path / "checkpoints").exists()
        return
    # Keep the real checkpoint/resume discriminator when the unsupported cold
    # intake was incorrectly admitted. This is not a module marker assertion.
    assert original.final_state["total"] == 7
    pointer = path.read_bytes()
    monkeypatch.setattr(math, "_e02_b74_checkpoint_helper", _replacement_increment)
    try:
        resumed = reopened.execute(
            chain,
            initial_state={"x": 3},
            params_per_node=params,
            checkpoint=checkpoint,
            seed=7,
            artifact_context=context,
        )
    except (CheckpointDigestMismatchError, CheckpointIdentityError):
        pytest.fail("Dynamic namespace cold intake ran despite the static-only identity profile")
    assert path.read_bytes() == pointer
    # Retain the counterexample's real return value and physical effects.
    print("DYNAMIC_RESUMED_TOTAL", resumed.final_state["total"])  # noqa: T201
    print("DYNAMIC_EFFECTS", effects.read_text().splitlines())  # noqa: T201
    pytest.fail("Dynamic import was admitted and resumed changed imported implementation")
