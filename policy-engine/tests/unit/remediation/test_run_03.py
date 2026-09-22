"""RUN-03 regression witnesses for retry error normalization and baselines."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from polisyos.core.errors import ErrorCategory
from polisyos.scientist.orchestration.engine.errors import RetryExhaustedError
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome
from polisyos.scientist.orchestration.engine.retry import (
    RetryPolicy,
    execute_with_retry_async,
    execute_with_retry_sync,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _fail(state: ExperimentState, code: str = "node.exception") -> NodeOutcome:
    return NodeOutcome(
        status="fail",
        state=state,
        error=NodeError(code=code, message="controlled failure"),
    )


def _ok(state: ExperimentState) -> NodeOutcome:
    return NodeOutcome(status="ok", state=state)


def _context() -> MagicMock:
    context = MagicMock()
    context.run.emit = MagicMock()
    return context


class _MutatingRetryNode:
    """Mutate declared state and fail once before succeeding."""

    spec = SimpleNamespace(
        metadata=SimpleNamespace(component_id="run-03-mutating"),
        state_writes=["params.counter", "params.attempt_history"],
    )

    def __init__(self) -> None:
        self.calls = 0
        self.seen_counters: list[int] = []

    def execute(self, _ctx: object, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        state.params["counter"] = int(state.params.get("counter", 0)) + 1
        state.params.setdefault("attempt_history", []).append(self.calls)
        self.seen_counters.append(int(state.params["counter"]))
        return _fail(state) if self.calls == 1 else _ok(state)

    async def execute_async(self, ctx: object, state: ExperimentState) -> NodeOutcome:
        return self.execute(ctx, state)


class _CostedRetryNode:
    """Record one spend on every attempt while mutating ordinary state."""

    spec = SimpleNamespace(
        metadata=SimpleNamespace(component_id="run-03-costed"),
        state_writes=["params.counter", "params.attempt_history", "budgets"],
    )

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, _ctx: object, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        state.params["counter"] = int(state.params.get("counter", 0)) + 1
        state.params.setdefault("attempt_history", []).append(self.calls)
        state.budgets["run_spent_usd"] = state.budgets.get(
            "run_spent_usd",
            Decimal("0"),
        ) + Decimal("0.25")
        return _fail(state) if self.calls == 1 else _ok(state)

    async def execute_async(self, ctx: object, state: ExperimentState) -> NodeOutcome:
        return self.execute(ctx, state)


def test_sync_retry_starts_each_attempt_from_one_logical_baseline() -> None:
    """A failed mutation is not presented to the next retry."""
    state = ExperimentState(run_id="run-03-sync")
    node = _MutatingRetryNode()

    with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
        result = execute_with_retry_sync(
            node,
            _context(),
            state,
            retry_policy=RetryPolicy(max_retries=1, backoff_base_s=0.1, jitter="none"),
            timeout_s=None,
            alias="run-03-sync",
        )

    assert result.status == "ok"
    assert node.seen_counters == [1, 1]
    assert result.state.params["counter"] == 1
    assert result.state.params["attempt_history"] == [2]
    assert state.params == {}


@pytest.mark.asyncio
async def test_async_retry_starts_each_attempt_from_one_logical_baseline() -> None:
    """The async wrapper gives every retry the same logical input too."""
    state = ExperimentState(run_id="run-03-async")
    node = _MutatingRetryNode()

    result = await execute_with_retry_async(
        node,
        _context(),
        state,
        retry_policy=RetryPolicy(max_retries=1, backoff_base_s=0.1, jitter="none"),
        timeout_s=None,
        alias="run-03-async",
    )

    assert result.status == "ok"
    assert node.seen_counters == [1, 1]
    assert result.state.params["counter"] == 1
    assert result.state.params["attempt_history"] == [2]
    assert state.params == {}


@pytest.mark.parametrize("mode", ["return", "raise"])
def test_permanent_error_shape_does_not_change_retry_count(mode: str) -> None:
    """A permanent contract defect is not retried only because it was raised."""

    class _PermanentNode:
        spec = SimpleNamespace(
            metadata=SimpleNamespace(component_id="run-03-permanent"),
            state_writes=[],
        )

        def __init__(self) -> None:
            self.calls = 0

        def execute(self, _ctx: object, state: ExperimentState) -> NodeOutcome:
            self.calls += 1
            if mode == "raise":
                raise ValueError("invalid input contract")
            return _fail(state, code="node.invalid_state")

    node = _PermanentNode()
    policy = RetryPolicy(max_retries=2, backoff_base_s=0.1, jitter="none")

    with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
        if mode == "raise":
            with pytest.raises(RetryExhaustedError):
                execute_with_retry_sync(
                    node,
                    _context(),
                    ExperimentState(run_id="run-03-permanent"),
                    retry_policy=policy,
                    timeout_s=None,
                    alias="run-03-permanent",
                )
        else:
            result = execute_with_retry_sync(
                node,
                _context(),
                ExperimentState(run_id="run-03-permanent"),
                retry_policy=policy,
                timeout_s=None,
                alias="run-03-permanent",
            )
            assert result.status == "fail"

    assert node.calls == 1


def test_sync_retry_preserves_failed_spend_in_durable_trace_and_result() -> None:
    """Retry isolation drops ordinary writes, not recorded attempt cost."""
    state = ExperimentState(run_id="run-03-cost-sync")
    node = _CostedRetryNode()
    context = _context()

    with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
        result = execute_with_retry_sync(
            node,
            context,
            state,
            retry_policy=RetryPolicy(max_retries=1, backoff_base_s=0.1, jitter="none"),
            timeout_s=None,
            alias="run-03-cost-sync",
        )

    assert result.status == "ok"
    assert result.state.params["counter"] == 1
    assert result.state.params["attempt_history"] == [2]
    assert result.state.budgets["run_spent_usd"] == Decimal("0.50")
    assert state.params == {}
    assert state.budgets == {}
    retry_events = [
        call for call in context.run.emit.call_args_list if call[0][1] == "NODE_RETRY"
    ]
    assert len(retry_events) == 1
    assert retry_events[0][1]["metrics"]["failed_cost_usd"] == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_async_retry_preserves_failed_spend_in_durable_trace_and_result() -> None:
    """Async retry records failed spend while returning a clean success branch."""
    state = ExperimentState(run_id="run-03-cost-async")
    node = _CostedRetryNode()
    context = _context()
    retry_stats: dict[str, int] = {}

    result = await execute_with_retry_async(
        node,
        context,
        state,
        retry_policy=RetryPolicy(max_retries=1, backoff_base_s=0.1, jitter="none"),
        timeout_s=None,
        alias="run-03-cost-async",
        retry_stats=retry_stats,
    )

    assert result.status == "ok"
    assert result.state.params["counter"] == 1
    assert result.state.params["attempt_history"] == [2]
    assert result.state.budgets["run_spent_usd"] == Decimal("0.50")
    assert retry_stats == {"attempts": 2}
    retry_events = [
        call for call in context.run.emit.call_args_list if call[0][1] == "NODE_RETRY"
    ]
    assert len(retry_events) == 1
    assert retry_events[0][1]["metrics"]["failed_cost_usd"] == pytest.approx(0.25)


def test_typed_transient_and_validation_categories_control_raised_retry() -> None:
    """Typed categories distinguish retryable ValueError from validation."""

    class _TransientValueError(ValueError):
        default_category = ErrorCategory.TRANSIENT

    class _ValidationRuntimeError(RuntimeError):
        default_category = ErrorCategory.VALIDATION

    class _RaisedNode:
        spec = SimpleNamespace(
            metadata=SimpleNamespace(component_id="run-03-classified"),
            state_writes=[],
        )

        def __init__(self, error: BaseException) -> None:
            self.error = error
            self.calls = 0

        def execute(self, _ctx: object, state: ExperimentState) -> NodeOutcome:
            self.calls += 1
            if self.calls == 1 or isinstance(self.error, _ValidationRuntimeError):
                raise self.error
            return _ok(state)

    transient = _RaisedNode(_TransientValueError("temporary transport value"))
    with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
        result = execute_with_retry_sync(
            transient,
            _context(),
            ExperimentState(run_id="run-03-transient-classified"),
            retry_policy=RetryPolicy(max_retries=1, backoff_base_s=0.1, jitter="none"),
            timeout_s=None,
            alias="run-03-transient-classified",
        )
    assert result.status == "ok"
    assert transient.calls == 2

    validation = _RaisedNode(_ValidationRuntimeError("invalid contract"))
    with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
        with pytest.raises(RetryExhaustedError):
            execute_with_retry_sync(
                validation,
                _context(),
                ExperimentState(run_id="run-03-validation-classified"),
                retry_policy=RetryPolicy(max_retries=2, backoff_base_s=0.1, jitter="none"),
                timeout_s=None,
                alias="run-03-validation-classified",
            )
    assert validation.calls == 1
