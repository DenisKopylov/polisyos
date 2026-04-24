from __future__ import annotations

import jax
import jax.numpy as jnp
import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import (
    ExecPlan,
    ProgramEdge,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
)
from polisyos.foundry.calibration.pure_executor import apply_nodes, compile_program
from polisyos.foundry.contracts.state import GlobalState
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
)


def _dummy_artifact_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + "1" * 64,
        kind="ir.trinity_bundle",
        media_type="application/json",
    )


def _build_graph_and_plan(
    nodes: list[ProgramNode],
    *,
    edges: list[ProgramEdge] | None = None,
    max_steps: int | None = None,
) -> tuple[ProgramGraph, ExecPlan]:
    program_graph = ProgramGraph(
        ir_ref=_dummy_artifact_ref(),
        nodes=nodes,
        edges=list(edges or []),
        entrypoints=[],
    )
    exec_plan = ExecPlan(
        program_ref=ProgramGraphRef(artifact_id="sha256:" + "2" * 64),
        order=[node.node_id for node in nodes],
        max_steps=max_steps,
    )
    return program_graph, exec_plan


def test_compile_program_uses_full_horizon_when_schedule_missing(monkeypatch) -> None:
    class _NoOpMechanism:
        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            return {}, key

    monkeypatch.setattr(
        "polisyos.foundry.calibration.pure_executor.create_mechanism_from_spec",
        lambda *args, **kwargs: _NoOpMechanism(),
    )
    graph, plan = _build_graph_and_plan(
        [
            ProgramNode(
                node_id="writer",
                node_kind="mechanism",
                mechanism_type="writer",
                outputs=[],
            )
        ],
        max_steps=4,
    )

    bundle = compile_program(
        graph,
        plan,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        base_state=GlobalState.empty(n_agents=2, n_firms=1),
        parameter_loader=lambda _: {"params": {}},
    )

    assert bundle.nodes[0].start == 0
    assert bundle.nodes[0].end == 3


def test_compile_program_requires_horizon_for_missing_schedule(monkeypatch) -> None:
    class _NoOpMechanism:
        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            return {}, key

    monkeypatch.setattr(
        "polisyos.foundry.calibration.pure_executor.create_mechanism_from_spec",
        lambda *args, **kwargs: _NoOpMechanism(),
    )
    graph, plan = _build_graph_and_plan(
        [
            ProgramNode(
                node_id="writer",
                node_kind="mechanism",
                mechanism_type="writer",
                outputs=[],
            )
        ]
    )

    with pytest.raises(ValueError, match="exec_plan.max_steps > 0"):
        compile_program(
            graph,
            plan,
            mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            base_state=GlobalState.empty(n_agents=2, n_firms=1),
            parameter_loader=lambda _: {"params": {}},
        )


def test_apply_nodes_flushes_visible_state_on_dependency_boundary(monkeypatch) -> None:
    class _IncomeWriter:
        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            delta = jnp.full_like(state.agents.income, 5.0)
            return {"agents.income": [{"delta": delta}]}, key

    class _IncomeReader:
        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            return {"agents.reported_income": [{"value": jnp.asarray(state.agents.income)}]}, key

    def _factory(mechanism_type, params, **kwargs):
        del params, kwargs
        if mechanism_type == "writer":
            return _IncomeWriter()
        if mechanism_type == "reader":
            return _IncomeReader()
        raise AssertionError(mechanism_type)

    monkeypatch.setattr(
        "polisyos.foundry.calibration.pure_executor.create_mechanism_from_spec",
        _factory,
    )
    graph, plan = _build_graph_and_plan(
        [
            ProgramNode(
                node_id="writer",
                node_kind="mechanism",
                mechanism_type="writer",
                outputs=["agents.income"],
            ),
            ProgramNode(
                node_id="reader",
                node_kind="mechanism",
                mechanism_type="reader",
                inputs=["agents.income"],
                outputs=["agents.reported_income"],
            ),
        ],
        edges=[ProgramEdge(src="writer", dst="reader", relation="depends_on")],
        max_steps=2,
    )
    bundle = compile_program(
        graph,
        plan,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        base_state=GlobalState.empty(n_agents=2, n_firms=1),
        parameter_loader=lambda _: {
            "params": {},
            "schedule": {"start_step": 0, "duration_steps": 1},
        },
    )

    next_state, _ = apply_nodes(
        GlobalState.empty(n_agents=2, n_firms=1),
        jax.random.PRNGKey(0),
        bundle=bundle,
        t=jnp.array(0, dtype=jnp.int32),
    )

    assert jnp.allclose(next_state.agents.income, jnp.array([5.0, 5.0], dtype=jnp.float32))
    assert jnp.allclose(
        next_state.agents.reported_income,
        jnp.array([5.0, 5.0], dtype=jnp.float32),
    )


def test_apply_nodes_preserves_batched_merge_for_independent_writers(monkeypatch) -> None:
    class _DeltaWriter:
        def __init__(self, offset: float) -> None:
            self._offset = offset

        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            delta = jnp.asarray(state.agents.income) + self._offset
            return {"agents.income": [{"delta": delta}]}, key

    def _factory(mechanism_type, params, **kwargs):
        del params, kwargs
        if mechanism_type == "left":
            return _DeltaWriter(1.0)
        if mechanism_type == "right":
            return _DeltaWriter(2.0)
        raise AssertionError(mechanism_type)

    monkeypatch.setattr(
        "polisyos.foundry.calibration.pure_executor.create_mechanism_from_spec",
        _factory,
    )
    graph, plan = _build_graph_and_plan(
        [
            ProgramNode(
                node_id="left",
                node_kind="mechanism",
                mechanism_type="left",
                outputs=["agents.income"],
            ),
            ProgramNode(
                node_id="right",
                node_kind="mechanism",
                mechanism_type="right",
                outputs=["agents.income"],
            ),
        ],
        max_steps=2,
    )
    bundle = compile_program(
        graph,
        plan,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        base_state=GlobalState.empty(n_agents=2, n_firms=1),
        parameter_loader=lambda _: {
            "params": {},
            "schedule": {"start_step": 0, "duration_steps": 1},
        },
    )

    next_state, _ = apply_nodes(
        GlobalState.empty(n_agents=2, n_firms=1),
        jax.random.PRNGKey(0),
        bundle=bundle,
        t=jnp.array(0, dtype=jnp.int32),
    )

    assert jnp.allclose(next_state.agents.income, jnp.array([3.0, 3.0], dtype=jnp.float32))
