"""Tests for async executor hardening (WS5.2)."""

from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from polisyos.scientist.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.engine.budget import BudgetExhaustedError, BudgetLimit, BudgetState
from polisyos.scientist.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.engine.errors import WorkflowTimeoutError
from polisyos.scientist.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.engine.registry import NodeRegistry
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata


# ── Helpers ───────────────────────────────────────────────────────────

def _node_spec(node_id: str = "test.node@1.0.0") -> NodeSpec:
    return NodeSpec(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse(node_id),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name="Test",
            description="Test node",
            tags=["test"],
            capabilities=Capability.SCIENTIST_NODE,
        ),
        state_reads=[],
        state_writes=[],
        produces=[],
    )


def _make_node(
    outcome_fn=None, *, node_id: str = "test.node@1.0.0", delay: float = 0,
):
    node = MagicMock()
    node.spec = _node_spec(node_id)

    def execute(ctx, state):
        if delay:
            time.sleep(delay)
        if outcome_fn:
            return outcome_fn(state)
        return NodeOutcome(status="ok", state=state)

    node.execute = execute
    return node


def _make_registry(*nodes_map) -> NodeRegistry:
    registry = MagicMock(spec=NodeRegistry)
    node_dict = {}
    for node_id, node in nodes_map:
        node_dict[node_id] = node
    registry.get = lambda nid: node_dict.get(str(nid), _make_node())
    return registry


def _make_ctx():
    ctx = MagicMock()
    ctx.run.emit = MagicMock()
    ctx.run.add_input = MagicMock()
    ctx.run.add_output = MagicMock()
    ctx.run.trace_path = None
    ctx.run.finalize = MagicMock(return_value=MagicMock())
    ctx.logger = MagicMock()
    ctx.metrics = None
    ctx.audit = None
    ctx.store.put_json = MagicMock(return_value=MagicMock(spec=ArtifactRef))
    ctx.store.put_json.return_value.kind = "test"
    ctx.store.put_json.return_value.artifact_id = "sha256:" + "a" * 64
    return ctx


def _make_workflow(*invocations, error_policy="fail_fast") -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="test_wf",
        nodes=list(invocations),
        error_policy=error_policy,
    )


# ── Per-task state isolation ──────────────────────────────────────────

class TestParallelStateIsolation:
    @pytest.mark.asyncio
    async def test_parallel_nodes_get_independent_copies(self):
        """Parallel nodes should not mutate each other's state."""
        mutations = {}

        class MutatingNode:
            def __init__(self, name: str, nid: str):
                self._name = name
                self.spec = _node_spec(nid)

            def execute(self, ctx, state):
                state.params[f"mutated_by_{self._name}"] = True
                mutations[self._name] = dict(state.params)
                return NodeOutcome(status="ok", state=state)

        node_a = MutatingNode("a", "test.a@1.0.0")
        node_b = MutatingNode("b", "test.b@1.0.0")

        registry = _make_registry(
            ("test.a@1.0.0", node_a),
            ("test.b@1.0.0", node_b),
        )
        ctx = _make_ctx()
        state = ExperimentState(run_id="iso-test")

        workflow = _make_workflow(
            NodeInvocation(alias="a", node_id="test.a@1.0.0"),
            NodeInvocation(alias="b", node_id="test.b@1.0.0"),
        )

        executor = AsyncWorkflowExecutor(ctx, registry, max_parallelism=2)
        await executor.execute(workflow, state)

        # Each node's mutations should be independent
        assert "mutated_by_a" in mutations["a"]
        assert "mutated_by_b" not in mutations["a"]
        assert "mutated_by_b" in mutations["b"]
        assert "mutated_by_a" not in mutations["b"]


# ── Tier savepoint rollback ───────────────────────────────────────────

class TestTierSavepoints:
    @pytest.mark.asyncio
    async def test_tier_rollback_on_failure(self):
        """On fail_fast, state should revert to tier savepoint."""
        def mutating_ok(state):
            state.params["tier1_done"] = True
            return NodeOutcome(status="ok", state=state)

        def failing(state):
            state.params["tier2_mutation"] = True
            return NodeOutcome(
                status="fail", state=state,
                error=NodeError(code="node.exception", message="boom", details={}),
            )

        node_a = _make_node(mutating_ok, node_id="test.a@1.0.0")
        node_b = _make_node(failing, node_id="test.b@1.0.0")

        registry = _make_registry(
            ("test.a@1.0.0", node_a),
            ("test.b@1.0.0", node_b),
        )
        ctx = _make_ctx()
        state = ExperimentState(run_id="rollback-test")

        workflow = _make_workflow(
            NodeInvocation(alias="a", node_id="test.a@1.0.0"),
            NodeInvocation(alias="b", node_id="test.b@1.0.0", depends_on=["a"]),
            error_policy="fail_fast",
        )

        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        # tier1 should have completed
        assert result.state.params.get("tier1_done") is True
        # tier2 mutation should be rolled back
        assert result.state.params.get("tier2_mutation") is None


# ── Workflow timeout ──────────────────────────────────────────────────

class TestWorkflowTimeout:
    @pytest.mark.asyncio
    async def test_workflow_timeout_raises(self):
        node = _make_node(delay=2.0, node_id="test.slow@1.0.0")
        registry = _make_registry(("test.slow@1.0.0", node))
        ctx = _make_ctx()
        state = ExperimentState(run_id="timeout-test")

        workflow = _make_workflow(
            NodeInvocation(alias="slow", node_id="test.slow@1.0.0"),
        )

        executor = AsyncWorkflowExecutor(
            ctx, registry, workflow_timeout_s=0.1,
        )
        with pytest.raises(WorkflowTimeoutError):
            await executor.execute(workflow, state)

    @pytest.mark.asyncio
    async def test_no_timeout_by_default(self):
        node = _make_node(node_id="test.fast@1.0.0")
        registry = _make_registry(("test.fast@1.0.0", node))
        ctx = _make_ctx()
        state = ExperimentState(run_id="no-timeout-test")

        workflow = _make_workflow(
            NodeInvocation(alias="fast", node_id="test.fast@1.0.0"),
        )

        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)
        assert result.report.status == "ok"


# ── Budget integration ────────────────────────────────────────────────

class TestBudgetIntegration:
    @pytest.mark.asyncio
    async def test_budget_exhausted_fails_node(self):
        bs = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("100"))},
            spent={"run": Decimal("100")},
        )
        mw = BudgetMiddleware(bs)

        node = _make_node(node_id="test.node@1.0.0")
        registry = _make_registry(("test.node@1.0.0", node))
        ctx = _make_ctx()
        state = ExperimentState(run_id="budget-test")

        workflow = _make_workflow(
            NodeInvocation(alias="a", node_id="test.node@1.0.0"),
        )

        executor = AsyncWorkflowExecutor(ctx, registry, budget_middleware=mw)
        result = await executor.execute(workflow, state)
        assert result.report.status == "fail"
        failed_node = [n for n in result.report.nodes if n.status == "fail"]
        assert len(failed_node) == 1
        assert failed_node[0].error.code == "node.budget_exhausted"


# ── New init params backward compatibility ────────────────────────────

class TestBackwardCompat:
    @pytest.mark.asyncio
    async def test_new_params_have_defaults(self):
        """Existing callers should work without new params."""
        node = _make_node(node_id="test.node@1.0.0")
        registry = _make_registry(("test.node@1.0.0", node))
        ctx = _make_ctx()
        state = ExperimentState(run_id="compat-test")

        workflow = _make_workflow(
            NodeInvocation(alias="a", node_id="test.node@1.0.0"),
        )

        # Old-style call (no new params)
        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)
        assert result.report.status == "ok"
