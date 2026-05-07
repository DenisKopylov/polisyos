from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodSignature,
)
from polisyos.foundry.methods.composer import CompositionDAG, MethodNode
from polisyos.foundry.methods.compiler.plan_optimizer import ExecutionPlanOptimizer, MethodCostModel


def _make_signature(
    fqn: str,
    *,
    backend: ComputeBackend = ComputeBackend.JAX,
    supports_jit: bool = True,
) -> MethodSignature:
    namespace_name, version = fqn.split("@", 1)
    namespace, name = namespace_name.rsplit(".", 1)
    return MethodSignature(
        name=name,
        namespace=namespace,
        version=version,
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        backend=backend,
        supports_jit=supports_jit,
        supports_vmap=False,
        supports_grad=False,
    )


class _RegistryStub:
    def __init__(self, *signatures: MethodSignature) -> None:
        self._signatures = {signature.fqn: signature for signature in signatures}

    def get(self, fqn: str) -> object:
        return SimpleNamespace(signature=self._signatures[fqn])


def test_graph_heuristic_scales_linearly_without_topology_metadata() -> None:
    model = MethodCostModel()

    smaller, cls_small = model.estimate("causal.discovery.pc", {"x": (2000,)})
    larger, cls_large = model.estimate("causal.discovery.pc", {"x": (4000,)})

    assert cls_small == "graph"
    assert cls_large == "graph"
    assert larger == pytest.approx(smaller * 2.0)


def test_iterative_heuristic_scales_linearly_without_topology_metadata() -> None:
    model = MethodCostModel()

    smaller, cls_small = model.estimate("bayesian.mcmc.foo", {"x": (2000,)})
    larger, cls_large = model.estimate("bayesian.mcmc.foo", {"x": (4000,)})

    assert cls_small == "iterative"
    assert cls_large == "iterative"
    assert larger == pytest.approx(smaller * 2.0)


def test_optimizer_emits_fused_and_batched_execution_kernels() -> None:
    optimizer = ExecutionPlanOptimizer(check_circuit_breakers=False)

    fqn_a = "tests.plan.a@1.0.0"
    fqn_b = "tests.plan.b@1.0.0"
    fqn_c = "tests.plan.c@1.0.0"
    fqn_batch = "tests.plan.batch@1.0.0"
    registry = _RegistryStub(
        _make_signature(fqn_a),
        _make_signature(fqn_b),
        _make_signature(fqn_c),
        _make_signature(fqn_batch),
    )

    dag = CompositionDAG()
    node_a = MethodNode(id=uuid4(), method_fqn=fqn_a, params={}, static_params={})
    node_b = MethodNode(id=uuid4(), method_fqn=fqn_b, params={}, static_params={})
    node_c = MethodNode(id=uuid4(), method_fqn=fqn_c, params={}, static_params={})
    node_batch_1 = MethodNode(id=uuid4(), method_fqn=fqn_batch, params={}, static_params={"bin": 1})
    node_batch_2 = MethodNode(id=uuid4(), method_fqn=fqn_batch, params={}, static_params={"bin": 1})

    for node in (node_a, node_b, node_c, node_batch_1, node_batch_2):
        dag.add_node(node)
    dag.add_edge(node_a.id, node_b.id, SimpleNamespace())
    dag.add_edge(node_b.id, node_c.id, SimpleNamespace())

    plan = optimizer.optimize(
        dag=dag,
        registry=registry,
        input_shapes={"features": (1000, 4)},
    )

    assert len(plan.fusion_groups) == 1
    assert plan.fusion_groups[0] == (node_a.id, node_b.id, node_c.id)
    assert len(plan.batch_groups) == 1
    assert set(plan.batch_groups[0]) == {node_batch_1.id, node_batch_2.id}
    assert {kernel.kind for kernel in plan.execution_kernels} == {"fused_chain", "batched_level"}
    assert len(plan.execution_kernels) == 2
    assert len(plan.fusable_pairs) == 2
    assert plan.estimated_optimized_cost_ms is not None
    assert plan.estimated_optimized_cost_ms <= plan.estimated_cost_ms
