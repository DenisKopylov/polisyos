"""Real cold plan persistence and typed intake, without historical-code authority."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from polisyos.core.artifacts import FileSystemCAS, artifact_manifest_profile_sha256
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.foundry.methods.artifacts import (
    CompiledChainPlan,
    load_compiled_chain_plan,
    store_compiled_chain_plan,
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
from polisyos.foundry.methods.exceptions import CyclicDependencyError
from polisyos.foundry.methods.selection.registry import MethodRegistry


@pytest.fixture(autouse=True)
def isolated_registry():
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


def _chain(*, data_flow: bool = False):
    calls = []

    def slot(name):
        return SlotSpec(
            name=name, slot_type=SlotType.SCALAR, unit=Unit(dimension="count", symbol="1")
        )

    def make_signature(name, *, inputs=(), requires=frozenset(), parameters=()):
        return MethodSignature(
            name=name,
            namespace="tests.compiled_plan",
            version="1.0.0",
            input_slots=frozenset(slot(name) for name in inputs),
            output_slots=frozenset({slot("product" if name == "produce" else "total")}),
            parameters=parameters,
            fidelity=FidelityLevel.LOW,
            complexity=ComplexityClass.O_N,
            backend=ComputeBackend.NUMPY,
            supports_jit=False,
            supports_vmap=False,
            supports_grad=False,
            requires=requires,
        )

    class Produce:
        signature: ClassVar = make_signature(
            "produce", parameters=(ParameterSpec(name="factor", default=2, is_static=True),)
        )
        metadata: ClassVar = MethodMetadata(description="Actual arithmetic producer")

        @staticmethod
        def pure_step(state: Any, params: dict[str, Any]) -> Any:
            calls.append(("produce", dict(params)))
            return {"product": state["x"] * params["factor"]}

    class Consume:
        signature: ClassVar = make_signature(
            "consume",
            inputs=("operand",) if data_flow else (),
            requires=frozenset({Produce.signature.fqn}),
            parameters=(ParameterSpec(name="offset", default=1, is_static=False),),
        )
        metadata: ClassVar = MethodMetadata(description="Actual arithmetic consumer")

        @staticmethod
        def pure_step(state: Any, params: dict[str, Any]) -> Any:
            calls.append(("consume", dict(params)))
            value = state if data_flow else state["product"]
            return {"total": value + params["offset"]}

    registry = MethodRegistry.get_instance()
    registry.register(Produce)
    registry.register(Consume)
    composer = MethodComposer(registry=registry)
    # Preserve a concrete consumer added before its unique required producer.
    consumer = composer.add(Consume.signature.fqn, offset=5)
    producer = composer.add(Produce.signature.fqn, factor=3)
    if data_flow:
        composer.connect(producer, consumer, {"product": "operand"})
    return SimpleNamespace(
        chain=composer.build(),
        registry=registry,
        calls=calls,
        producer=producer,
        consumer=consumer,
        classes=(Produce, Consume),
    )


def _selected_ref(cas, ref):
    return ArtifactRef(
        artifact_id=ref.artifact_id,
        kind=ref.kind,
        media_type=ref.media_type,
        manifest_profile_sha256=artifact_manifest_profile_sha256(cas.get_manifest(ref)),
    )


@pytest.mark.parametrize("data_flow", [False, True])
def test_real_cas_reopen_restores_payload_occurrences_and_executes(tmp_path, data_flow):
    fixture = _chain(data_flow=data_flow)
    plan = CompiledChainPlan.from_chain(fixture.chain)
    cas = FileSystemCAS(tmp_path / "cas")
    ref = store_compiled_chain_plan(cas, plan)
    assert ref.manifest_profile_sha256 is not None
    restored = load_compiled_chain_plan(
        FileSystemCAS(tmp_path / "cas"), ref, registry=fixture.registry
    )
    assert restored.execution_order == fixture.chain.execution_order
    assert restored.dag.predecessors == fixture.chain.dag.predecessors
    assert restored.get_node(fixture.producer.id).static_params == {"factor": 3}
    assert restored.get_node(fixture.consumer.id).params == {"offset": 5}
    result = restored.execute_heterogeneous(state={"x": 4}, registry=fixture.registry)
    assert result.final_state["total"] == 17
    assert [name for name, _params in fixture.calls] == ["produce", "consume"]


@pytest.mark.parametrize(
    "mutation",
    ["required-edge", "order", "cycle", "missing-node", "sparse", "foreign", "bool-index"],
)
def test_persisted_plan_mutation_refuses_before_body(tmp_path, mutation):
    fixture = _chain()
    payload = from_canonical_bytes(CompiledChainPlan.from_chain(fixture.chain).content)
    if mutation == "required-edge":
        payload["predecessors"][str(fixture.consumer.id)] = []
    elif mutation == "order":
        payload["execution_order"].reverse()
    elif mutation == "cycle":
        payload["predecessors"][str(fixture.producer.id)] = [str(fixture.consumer.id)]
    elif mutation == "missing-node":
        payload["predecessors"][str(fixture.consumer.id)] = ["missing-occurrence"]
    elif mutation == "sparse":
        del payload["nodes"][0]["params_json"]
    elif mutation == "foreign":
        payload["nodes"][0]["foreign_authority"] = True
    else:
        payload["nodes"][0]["instance_index"] = False
    cas = FileSystemCAS(tmp_path / "cas")
    ref = cas.put_bytes(
        to_canonical_bytes(payload, CanonSpec(forbid_floats=False, exclude_none=False)),
        PutOptions(
            kind="foundry.compiled_chain_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.compiled_chain_plan", version="1.0.0"),
        ),
    )
    with pytest.raises((ValueError, CyclicDependencyError)):
        load_compiled_chain_plan(
            FileSystemCAS(tmp_path / "cas"), _selected_ref(cas, ref), registry=fixture.registry
        )
    assert fixture.calls == []


def test_current_abi_drift_refuses_before_body(tmp_path):
    fixture = _chain()
    cas = FileSystemCAS(tmp_path / "cas")
    ref = store_compiled_chain_plan(cas, CompiledChainPlan.from_chain(fixture.chain))
    fixture.classes[1].signature = replace(fixture.classes[1].signature, requires=frozenset())
    with pytest.raises(ValueError, match="signature ABI mismatch"):
        load_compiled_chain_plan(cas, ref, registry=fixture.registry)
    assert fixture.calls == []


def test_repeated_fqn_occurrences_reopen_with_nearest_earlier_requirement(tmp_path):
    fixture = _chain()
    composer = MethodComposer(registry=fixture.registry)
    first = composer.add(fixture.classes[0].signature.fqn, factor=3)
    dependent = composer.add(fixture.classes[1].signature.fqn, offset=5)
    second = composer.add(fixture.classes[0].signature.fqn, factor=3)
    original = composer.build()
    cas = FileSystemCAS(tmp_path / "cas")
    ref = store_compiled_chain_plan(cas, CompiledChainPlan.from_chain(original))
    restored = load_compiled_chain_plan(
        FileSystemCAS(tmp_path / "cas"), ref, registry=fixture.registry
    )
    assert restored.dag.predecessors[dependent.id] == frozenset({first.id})
    assert restored.get_node(first.id).instance_index == 0
    assert restored.get_node(second.id).instance_index == 1
    assert restored.execution_order == original.execution_order
    result = restored.execute_heterogeneous(state={"x": 4}, registry=fixture.registry)
    assert result.final_state["total"] == 17
    names = [name for name, _params in fixture.calls]
    assert names.count("produce") == 2
    assert names.count("consume") == 1
    assert names[0] == "produce"
    assert names[-1] == "consume"


@pytest.mark.parametrize("schema_name", ["foreign-plan", "polisyos.foundry.compiled_chain_plan"])
def test_selected_manifest_schema_is_consumed(tmp_path, schema_name):
    fixture = _chain()
    cas = FileSystemCAS(tmp_path / "cas")
    ref = cas.put_bytes(
        CompiledChainPlan.from_chain(fixture.chain).content,
        PutOptions(
            kind="foundry.compiled_chain_plan",
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version="foreign-version"),
        ),
    )
    with pytest.raises(ValueError, match="manifest schema mismatch"):
        load_compiled_chain_plan(cas, _selected_ref(cas, ref), registry=fixture.registry)
    assert fixture.calls == []


@pytest.mark.parametrize("value", [float("nan"), (1, 2), {1: 2}, {"_type": "float"}])
def test_non_json_payload_refused_at_real_producer(value):
    fixture = _chain()
    node = fixture.consumer
    altered = replace(node, params={"offset": value})
    fixture.chain = replace(
        fixture.chain,
        dag=replace(fixture.chain.dag, nodes={**fixture.chain.dag.nodes, node.id: altered}),
    )
    with pytest.raises(ValueError, match="Compiled plan parameters"):
        CompiledChainPlan.from_chain(fixture.chain)
    assert fixture.calls == []


def test_cyclic_python_payload_refused_at_real_producer():
    values = []
    values.append(values)
    test_non_json_payload_refused_at_real_producer(values)


def test_unprofiled_reference_is_not_a_selected_plan(tmp_path):
    fixture = _chain()
    cas = FileSystemCAS(tmp_path / "cas")
    ref = store_compiled_chain_plan(cas, CompiledChainPlan.from_chain(fixture.chain))
    unprofiled = ArtifactRef(artifact_id=ref.artifact_id, kind=ref.kind, media_type=ref.media_type)
    with pytest.raises(ValueError, match="exact typed selected-manifest reference"):
        load_compiled_chain_plan(cas, unprofiled, registry=fixture.registry)
    assert fixture.calls == []
