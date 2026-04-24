"""Tests for async executor hardening (WS5.2)."""

from __future__ import annotations

import time
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.engine.errors import WorkflowTimeoutError
from polisyos.scientist.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.engine.registry import NodeRegistry
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_merge import MergeConflictPolicy
from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec

# ── Helpers ───────────────────────────────────────────────────────────


def _node_spec(
    node_id: str = "test.node@1.0.0",
    *,
    state_writes: list[str] | None = None,
) -> NodeSpec:
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
        state_writes=list(state_writes or []),
        produces=[],
    )


def _make_node(
    outcome_fn=None,
    *,
    node_id: str = "test.node@1.0.0",
    delay: float = 0,
    state_writes: list[str] | None = None,
):
    node = MagicMock()
    node.spec = _node_spec(node_id, state_writes=state_writes)

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

    @pytest.mark.asyncio
    async def test_bind_failure_becomes_typed_node_error(self):
        task_node = MagicMock()
        task_node.spec = _node_spec("test.bind_fail@1.0.0")

        def _bind(_params):
            raise RuntimeError("bind exploded")

        task_node.bind.side_effect = _bind
        task_node.execute.side_effect = AssertionError("execute should not run when bind fails")

        registry = _make_registry(("test.bind_fail@1.0.0", task_node))
        ctx = _make_ctx()
        state = ExperimentState(run_id="bind-fail-test")
        workflow = _make_workflow(
            NodeInvocation(
                alias="bind_fail",
                node_id="test.bind_fail@1.0.0",
                params={"country": "UA"},
            ),
            error_policy="continue",
        )

        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        assert result.report.status == "fail"
        record = result.report.nodes[0]
        assert record.status == "fail"
        assert record.error is not None
        assert record.error.code == "node.bind_failed"
        assert record.error.details["type"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_runtime_lookup_failure_becomes_typed_node_error(self):
        task_node = MagicMock()
        task_node.spec = _node_spec("test.lookup_fail@1.0.0")
        task_node.execute.side_effect = LookupError("missing dependency")

        registry = _make_registry(("test.lookup_fail@1.0.0", task_node))
        ctx = _make_ctx()
        state = ExperimentState(run_id="lookup-fail-test")
        workflow = _make_workflow(
            NodeInvocation(alias="lookup_fail", node_id="test.lookup_fail@1.0.0"),
            error_policy="continue",
        )

        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        assert result.report.status == "fail"
        record = result.report.nodes[0]
        assert record.status == "fail"
        assert record.error is not None
        assert record.error.code == "node.exception"
        assert record.error.details["type"] == "LookupError"


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
                status="fail",
                state=state,
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

    @pytest.mark.asyncio
    async def test_rollback_compensation_hook_receives_fail_fast_event(self):
        def ok(state):
            state.params["tier1_done"] = True
            return NodeOutcome(status="ok", state=state)

        def fail(state):
            state.params["tier2_mutation"] = True
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="node.exception", message="boom", details={}),
            )

        events = []

        class Hook:
            def on_tier_rollback(self, *, event, restored_state):
                events.append((event, restored_state.model_dump(mode="python")))

        registry = _make_registry(
            ("test.ok@1.0.0", _make_node(ok, node_id="test.ok@1.0.0")),
            ("test.fail@1.0.0", _make_node(fail, node_id="test.fail@1.0.0")),
        )
        ctx = _make_ctx()
        workflow = _make_workflow(
            NodeInvocation(alias="ok", node_id="test.ok@1.0.0"),
            NodeInvocation(alias="fail", node_id="test.fail@1.0.0", depends_on=["ok"]),
            error_policy="fail_fast",
        )

        executor = AsyncWorkflowExecutor(
            ctx,
            registry,
            compensation_hook=Hook(),
        )
        await executor.execute(workflow, ExperimentState(run_id="rollback-hook"))

        assert len(events) == 1
        event, restored_state = events[0]
        assert event.reason == "single_node_fail_fast"
        assert event.failed_aliases == ("fail",)
        assert event.completed_before_tier == ("ok",)
        assert restored_state["params"] == {"tier1_done": True}

    @pytest.mark.asyncio
    async def test_failed_single_node_does_not_commit_state_in_continue_mode(self):
        def failing(state):
            state.params["leaked"] = True
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="node.exception", message="boom", details={}),
            )

        node = _make_node(failing, node_id="test.fail@1.0.0")
        registry = _make_registry(("test.fail@1.0.0", node))
        ctx = _make_ctx()
        state = ExperimentState(run_id="single-fail-rollback", params={"baseline": True})

        workflow = _make_workflow(
            NodeInvocation(alias="fail", node_id="test.fail@1.0.0"),
            error_policy="continue",
        )

        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        assert result.report.status == "fail"
        assert result.state.params == {"baseline": True}

    @pytest.mark.asyncio
    async def test_parallel_merge_conflict_rolls_back_whole_tier(self):
        def write_alpha(state):
            state.params["shared"] = "alpha"
            return NodeOutcome(status="ok", state=state)

        def write_beta(state):
            state.params["shared"] = "beta"
            return NodeOutcome(status="ok", state=state)

        node_a = _make_node(
            write_alpha,
            node_id="test.a@1.0.0",
            state_writes=["params.shared"],
        )
        node_b = _make_node(
            write_beta,
            node_id="test.b@1.0.0",
            state_writes=["params.shared"],
        )

        registry = _make_registry(
            ("test.a@1.0.0", node_a),
            ("test.b@1.0.0", node_b),
        )
        ctx = _make_ctx()
        state = ExperimentState(run_id="merge-conflict-test", params={"baseline": True})

        workflow = _make_workflow(
            NodeInvocation(alias="a", node_id="test.a@1.0.0"),
            NodeInvocation(alias="b", node_id="test.b@1.0.0"),
            error_policy="continue",
        )

        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        assert result.report.status == "fail"
        assert result.state.params == {"baseline": True}
        records = {record.alias: record for record in result.report.nodes}
        assert records["a"].status == "fail"
        assert records["b"].status == "fail"
        assert records["a"].error is not None
        assert records["a"].error.code == "node.parallel_merge_conflict"
        assert ctx.store.put_json.call_count >= 3

    @pytest.mark.asyncio
    async def test_parallel_merge_policy_can_resolve_conflict(self):
        def write_alpha(state):
            state.params["shared"] = "alpha"
            return NodeOutcome(status="ok", state=state)

        def write_beta(state):
            state.params["shared"] = "beta"
            return NodeOutcome(status="ok", state=state)

        node_a = _make_node(
            write_alpha,
            node_id="test.a@1.0.0",
            state_writes=["params.shared"],
        )
        node_b = _make_node(
            write_beta,
            node_id="test.b@1.0.0",
            state_writes=["params.shared"],
        )
        registry = _make_registry(
            ("test.a@1.0.0", node_a),
            ("test.b@1.0.0", node_b),
        )
        ctx = _make_ctx()
        state = ExperimentState(run_id="merge-policy-test")
        workflow = _make_workflow(
            NodeInvocation(alias="a", node_id="test.a@1.0.0"),
            NodeInvocation(alias="b", node_id="test.b@1.0.0"),
            error_policy="continue",
        )

        executor = AsyncWorkflowExecutor(
            ctx,
            registry,
            merge_conflict_policy=MergeConflictPolicy.LAST_WRITE_WINS,
        )
        result = await executor.execute(workflow, state)

        assert result.report.status == "ok"
        assert result.state.params["shared"] == "beta"


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
            ctx,
            registry,
            workflow_timeout_s=0.1,
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
