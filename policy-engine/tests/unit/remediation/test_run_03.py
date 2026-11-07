"""RUN-03 regression witnesses for retry error normalization and baselines."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.errors import ErrorCategory
from polisyos.core.run.context import RunContext
from polisyos.core.run.manifest import RunManifest
from polisyos.core.trace.record import TraceRecord
from polisyos.core.trace.sink import JsonlTraceSink
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.errors import RetryExhaustedError
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome
from polisyos.scientist.orchestration.engine.retry import (
    RetryPolicy,
    _preserve_retry_spend,
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


def _durable_context(tmp_path):
    """Build a real RunContext whose JSONL sink can be read back as TraceRecord."""
    store = MagicMock()
    trace_path = tmp_path / "trace.jsonl"
    run = RunContext(
        store=store,
        trace=JsonlTraceSink(trace_path),
        run_manifest=RunManifest(
            run_id="run-03-durable",
            registry_bundle=ArtifactRef(
                artifact_id="sha256:" + "0" * 64,
                kind="registry",
                media_type="application/json",
            ),
        ),
    )
    return ExecutionContext(store=store, run=run, logger=MagicMock()), trace_path


def test_retry_module_imports_before_runner_facade() -> None:
    """The direct retry import must not initialize the runner facade first."""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from polisyos.scientist.orchestration.engine.retry "
                "import RetryPolicy; print(RetryPolicy.__name__)"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "RetryPolicy"


class _MutatingRetryNode:
    """Mutate declared state and fail once before succeeding."""

    spec = SimpleNamespace(
        metadata=SimpleNamespace(component_id="run-03-mutating"),
        state_writes=["params.counter", "params.attempt_history"],
    )

    def __init__(self) -> None:
        self.calls = 0
        self.sync_calls = 0
        self.async_calls = 0
        self.seen_counters: list[int] = []

    def execute(self, _ctx: object, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        self.sync_calls += 1
        state.params["counter"] = int(state.params.get("counter", 0)) + 1
        state.params.setdefault("attempt_history", []).append(self.calls)
        self.seen_counters.append(int(state.params["counter"]))
        return _fail(state) if self.calls == 1 else _ok(state)

    async def execute_async(self, ctx: object, state: ExperimentState) -> NodeOutcome:
        del ctx
        self.calls += 1
        self.async_calls += 1
        await asyncio.sleep(0)
        state.params["counter"] = int(state.params.get("counter", 0)) + 1
        state.params.setdefault("attempt_history", []).append(self.calls)
        self.seen_counters.append(int(state.params["counter"]))
        return _fail(state) if self.calls == 1 else _ok(state)


class _CostedRetryNode:
    """Record one spend on every attempt while mutating ordinary state."""

    spec = SimpleNamespace(
        metadata=SimpleNamespace(component_id="run-03-costed"),
        state_writes=["params.counter", "params.attempt_history", "budgets"],
    )

    def __init__(self) -> None:
        self.calls = 0
        self.sync_calls = 0
        self.async_calls = 0

    def execute(self, _ctx: object, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        self.sync_calls += 1
        state.params["counter"] = int(state.params.get("counter", 0)) + 1
        state.params.setdefault("attempt_history", []).append(self.calls)
        state.budgets["run_spent_usd"] = state.budgets.get(
            "run_spent_usd",
            Decimal("0"),
        ) + Decimal("0.25")
        return _fail(state) if self.calls == 1 else _ok(state)

    async def execute_async(self, ctx: object, state: ExperimentState) -> NodeOutcome:
        del ctx
        self.calls += 1
        self.async_calls += 1
        await asyncio.sleep(0)
        state.params["counter"] = int(state.params.get("counter", 0)) + 1
        state.params.setdefault("attempt_history", []).append(self.calls)
        state.budgets["run_spent_usd"] = state.budgets.get(
            "run_spent_usd",
            Decimal("0"),
        ) + Decimal("0.25")
        return _fail(state) if self.calls == 1 else _ok(state)


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
    assert node.sync_calls == 2
    assert node.async_calls == 0


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
    assert node.async_calls == 2
    assert node.sync_calls == 0


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


def test_sync_retry_preserves_failed_spend_in_durable_trace_and_result(tmp_path) -> None:
    """Retry isolation drops ordinary writes, not recorded attempt cost."""
    state = ExperimentState(run_id="run-03-cost-sync")
    node = _CostedRetryNode()
    context, trace_path = _durable_context(tmp_path)

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
    records = [
        TraceRecord.model_validate_json(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    retry_events = [record for record in records if record.event == "NODE_RETRY"]
    assert len(retry_events) == 1
    assert retry_events[0].phase == "scientist.node.run-03-cost-sync"
    assert retry_events[0].metrics["attempt"] == 1
    assert retry_events[0].metrics["failed_cost_usd"] == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_async_retry_preserves_failed_spend_in_durable_trace_and_result(tmp_path) -> None:
    """Async retry records failed spend while returning a clean success branch."""
    state = ExperimentState(run_id="run-03-cost-async")
    node = _CostedRetryNode()
    context, trace_path = _durable_context(tmp_path)
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
    assert node.async_calls == 2
    assert node.sync_calls == 0
    records = [
        TraceRecord.model_validate_json(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    retry_events = [record for record in records if record.event == "NODE_RETRY"]
    assert len(retry_events) == 1
    assert retry_events[0].phase == "scientist.node.run-03-cost-async"
    assert retry_events[0].metrics["attempt"] == 1
    assert retry_events[0].metrics["failed_cost_usd"] == pytest.approx(0.25)


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
    with (
        patch("polisyos.scientist.orchestration.engine.retry.time.sleep"),
        pytest.raises(RetryExhaustedError),
    ):
        execute_with_retry_sync(
            validation,
            _context(),
            ExperimentState(run_id="run-03-validation-classified"),
            retry_policy=RetryPolicy(max_retries=2, backoff_base_s=0.1, jitter="none"),
            timeout_s=None,
            alias="run-03-validation-classified",
        )
    assert validation.calls == 1


def test_terminal_spend_projection_excludes_failed_state_mutation() -> None:
    """Executor recovery carries spend, not a failed branch wholesale."""
    base = ExperimentState(
        run_id="run-03-terminal-projection",
        params={"keep": "baseline"},
        budgets={"prior_spent_usd": Decimal("1.00")},
    )
    terminal = base.model_copy(deep=True)
    terminal.params["counter"] = 1
    terminal.params["attempt_history"] = [1, 2]
    terminal.budgets["run_spent_usd"] = Decimal("0.50")

    preserved = _preserve_retry_spend(base, terminal)

    assert preserved.params == {"keep": "baseline"}
    assert preserved.budgets == {
        "prior_spent_usd": Decimal("1.00"),
        "run_spent_usd": Decimal("0.50"),
    }
    assert base.params == {"keep": "baseline"}
    assert base.budgets == {"prior_spent_usd": Decimal("1.00")}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cancel_at",
    [
        "first_body",
        "second_body",
        "second_start",
        "finish",
        "second_error_finish",
        "error_backoff",
        "first_error_finish_cost",
        "second_error_finish_cost",
        "finalizer_fails",
    ],
)
async def test_cancel_projects_only_known_completed_failure_spend(
    cancel_at: str, monkeypatch
) -> None:
    """Known failed work survives cancellation at every async callback boundary."""
    state = ExperimentState(
        run_id="run-03-cancel-settlement",
        params={"counter": 0, "items": []},
        budgets={"run_spent_usd": Decimal("5")},
    )

    class Node:
        spec = SimpleNamespace(
            metadata=SimpleNamespace(component_id="run-03-cancel"),
            state_writes=["params", "budgets"],
        )

        def __init__(self):
            self.calls = 0

        async def execute_async(self, _ctx, attempt_state):
            self.calls += 1
            attempt_state.params["counter"] += 1
            attempt_state.params["items"].append(self.calls)
            if self.calls == 1 and cancel_at != "first_body":
                attempt_state.budgets["run_spent_usd"] += Decimal("2")
                if cancel_at == "first_error_finish_cost":
                    raise RuntimeError("completed first failure")
                return _fail(attempt_state)
            if cancel_at == "second_error_finish_cost":
                attempt_state.budgets["run_spent_usd"] += Decimal("3")
                raise RuntimeError("completed second failure")
            if cancel_at in {"second_error_finish", "error_backoff"}:
                raise RuntimeError("controlled second attempt failure")
            attempt_state.budgets["run_spent_usd"] += Decimal("100")
            raise asyncio.CancelledError

    async def started(attempt_number, _state):
        if attempt_number == 2 and cancel_at == "second_start":
            raise asyncio.CancelledError
        return f"attempt-{attempt_number}"

    async def finished(attempt_id, outcome):
        if cancel_at == "finalizer_fails" and outcome is None:
            raise OSError("attempt finalization unavailable")
        if cancel_at in {"finish", "first_error_finish_cost"} or (
            cancel_at in {"second_error_finish", "second_error_finish_cost"}
            and attempt_id == "attempt-2"
        ):
            raise asyncio.CancelledError

    delay_calls = 0

    async def retry_delay(_delay, _deadline):
        nonlocal delay_calls
        delay_calls += 1
        if cancel_at == "error_backoff" and delay_calls == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(
        "polisyos.scientist.orchestration.engine.retry._retry_delay_async", retry_delay
    )
    node = Node()
    with pytest.raises(asyncio.CancelledError) as cancelled:
        await execute_with_retry_async(
            node,
            _context(),
            state,
            retry_policy=RetryPolicy(max_retries=2, backoff_base_s=0.1, jitter="none"),
            timeout_s=None,
            alias="cancel-settlement",
            attempt_started=started,
            attempt_completed=finished,
        )

    expected_spend = (
        Decimal("5")
        if cancel_at == "first_body"
        else Decimal("10")
        if cancel_at == "second_error_finish_cost"
        else Decimal("7")
    )
    if cancel_at == "finalizer_fails":
        assert cancelled.value.__cause__ is not None
        assert "finalization" in " ".join(cancelled.value.__notes__)
    assert state.budgets["run_spent_usd"] == expected_spend
    assert state.params == {"counter": 0, "items": []}
    assert node.calls == (
        2
        if cancel_at
        in {
            "second_body",
            "second_error_finish",
            "error_backoff",
            "second_error_finish_cost",
            "finalizer_fails",
        }
        else 1
    )


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("form", ["raise", "ipc", "return"])
def test_unknown_budget_settlement_never_redispatches_effect(mode: str, form: str) -> None:
    """An explicit retry filter cannot replay a producer's uncertain settlement."""
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerSettlementOutcomeUnknownError,
    )
    from polisyos.scientist.orchestration.engine.retry import (
        _worker_error_payload,
        _worker_node_error,
    )

    class Node:
        spec = SimpleNamespace(
            metadata=SimpleNamespace(component_id="run-03-budget-unknown"),
            state_writes=["params"],
        )

        def __init__(self):
            self.calls = 0

        def execute(self, _ctx, attempt_state):
            self.calls += 1
            error = BudgetLedgerSettlementOutcomeUnknownError("event", "digest")
            if form == "return":
                return _fail(attempt_state, code="node.budget_settlement_outcome_unknown")
            if form == "ipc":
                raise _worker_node_error(_worker_error_payload(error))
            raise error

        async def execute_async(self, ctx, attempt_state):
            return self.execute(ctx, attempt_state)

    node = Node()
    state = ExperimentState(run_id="run-03-budget-unknown")
    kwargs = {
        "retry_policy": RetryPolicy(
            max_retries=1,
            backoff_base_s=0.1,
            jitter="none",
            retry_on=["node.exception", "node.budget_settlement_outcome_unknown"],
        ),
        "timeout_s": None,
        "alias": "budget-unknown",
    }

    def invoke():
        if mode == "sync":
            return execute_with_retry_sync(node, _context(), state, **kwargs)
        return asyncio.run(execute_with_retry_async(node, _context(), state, **kwargs))

    if form == "return":
        assert invoke().status == "fail"
    else:
        with pytest.raises(RetryExhaustedError):
            invoke()
    assert node.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["retryable", "terminal", "success", "skip", "raised"])
@pytest.mark.parametrize("prior", [False, True])
@pytest.mark.parametrize("finalizer", ["cancel", "error"])
async def test_completed_outcome_cost_survives_finish_cancellation(kind, prior, finalizer):
    """All completed outcomes count even if their finalization is interrupted."""
    state = ExperimentState(
        run_id="run-03-all-completed",
        params={"base": "kept"},
        budgets={"run_spent_usd": Decimal("5")},
    )

    class Producer:
        spec = SimpleNamespace(
            metadata=SimpleNamespace(component_id="all-completed"),
            state_writes=["params", "budgets"],
        )

        def __init__(self):
            self.calls = 0

        async def execute_async(self, _ctx, attempt_state):
            self.calls += 1
            attempt_state.params["unaccepted"] = self.calls
            if prior and self.calls == 1:
                attempt_state.budgets["run_spent_usd"] += Decimal("2")
                return _fail(attempt_state)
            result = attempt_state.model_copy(deep=True)
            result.budgets["run_spent_usd"] += Decimal("3")
            if kind == "raised":
                attempt_state.budgets["run_spent_usd"] += Decimal("3")
                raise RuntimeError("completed raised failure")
            if kind in {"retryable", "terminal"}:
                return _fail(result, "node.exception" if kind == "retryable" else "node.permanent")
            return NodeOutcome(status="ok" if kind == "success" else "skip", state=result)

    async def started(n, _state):
        return f"attempt-{n}"

    finish_calls = 0

    async def finished(attempt_id, _outcome):
        nonlocal finish_calls
        target = "attempt-2" if prior else "attempt-1"
        if attempt_id != target:
            return
        finish_calls += 1
        if finish_calls > 1 and finalizer == "error":
            raise OSError("controlled finalizer error")
        raise asyncio.CancelledError

    node = Producer()
    with pytest.raises(asyncio.CancelledError):
        await execute_with_retry_async(
            node,
            _context(),
            state,
            retry_policy=RetryPolicy(max_retries=2, backoff_base_s=0.1, jitter="none"),
            timeout_s=None,
            alias="all-completed",
            attempt_started=started,
            attempt_completed=finished,
        )
    assert state.budgets["run_spent_usd"] == Decimal("10" if prior else "8")
    assert state.params == {"base": "kept"}


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["success", "skip", "terminal"])
async def test_zero_retry_copy_outcome_keeps_cost_on_finish_cancel(kind):
    state = ExperimentState(run_id="run-03-zero", budgets={"run_spent_usd": Decimal("5")})

    class Producer:
        async def execute_async(self, _ctx, attempt_state):
            result = attempt_state.model_copy(deep=True)
            result.budgets["run_spent_usd"] += Decimal("3")
            return (
                _fail(result, "node.permanent")
                if kind == "terminal"
                else NodeOutcome(status="ok" if kind == "success" else "skip", state=result)
            )

    async def started(_n, _state):
        return "attempt-1"

    async def finished(_attempt_id, _outcome):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await execute_with_retry_async(
            Producer(),
            _context(),
            state,
            retry_policy=RetryPolicy(max_retries=0),
            timeout_s=None,
            alias="zero-copy",
            attempt_started=started,
            attempt_completed=finished,
        )
    assert state.budgets["run_spent_usd"] == Decimal("8")


@pytest.mark.asyncio
async def test_completed_failure_cost_is_not_counted_twice_after_retry_event_error(monkeypatch):
    """An error after a completed attempt cannot turn one cost into two."""
    state = ExperimentState(run_id="run-03-once", budgets={"run_spent_usd": Decimal("5")})

    class Producer:
        spec = SimpleNamespace(
            metadata=SimpleNamespace(component_id="run-03-once"), state_writes=["budgets"]
        )

        async def execute_async(self, _ctx, attempt_state):
            attempt_state.budgets["run_spent_usd"] += Decimal("2")
            return _fail(attempt_state)

    context = _context()
    context.run.emit.side_effect = [RuntimeError("retry event unavailable"), None]

    async def cancelled_delay(_delay, _deadline):
        raise asyncio.CancelledError

    monkeypatch.setattr(
        "polisyos.scientist.orchestration.engine.retry._retry_delay_async", cancelled_delay
    )
    with pytest.raises(asyncio.CancelledError):
        await execute_with_retry_async(
            Producer(),
            context,
            state,
            retry_policy=RetryPolicy(max_retries=1, backoff_base_s=0.1, jitter="none"),
            timeout_s=None,
            alias="once",
        )
    assert state.budgets["run_spent_usd"] == Decimal("7")


@pytest.mark.asyncio
async def test_zero_retry_in_place_error_does_not_double_known_cost():
    """The circuit-breaker path preserves one completed in-place cost."""
    state = ExperimentState(run_id="run-03-zero-circuit", budgets={"run_spent_usd": Decimal("5")})

    class Producer:
        async def execute_async(self, _ctx, attempt_state):
            attempt_state.budgets["run_spent_usd"] += Decimal("2")
            raise RuntimeError("completed failure")

    breaker = MagicMock()
    breaker.allow_request.return_value = True
    with pytest.raises(RetryExhaustedError):
        await execute_with_retry_async(
            Producer(),
            _context(),
            state,
            retry_policy=RetryPolicy(max_retries=0),
            timeout_s=None,
            alias="zero-circuit",
            circuit_breaker=breaker,
        )
    assert state.budgets["run_spent_usd"] == Decimal("7")


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize(
    ("category", "expected_calls"),
    [
        (None, 2),
        (ErrorCategory.TRANSIENT, 2),
        (ErrorCategory.FATAL, 1),
        (ErrorCategory.VALIDATION, 1),
    ],
)
def test_returned_typed_category_composes_with_retry_filter(mode, category, expected_calls):
    """Declared categories constrain the existing filter; legacy remains code-only."""

    class Producer:
        spec = SimpleNamespace(
            metadata=SimpleNamespace(component_id="category-producer"), state_writes=[]
        )

        def __init__(self):
            self.calls = 0

        def execute(self, _ctx, state):
            self.calls += 1
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(code="node.exception", message="controlled", category=category),
            )

        async def execute_async(self, ctx, state):
            return self.execute(ctx, state)

    producer = Producer()
    kwargs = {
        "retry_policy": RetryPolicy(max_retries=1, backoff_base_s=0.1, jitter="none"),
        "timeout_s": None,
        "alias": "category-producer",
    }
    with patch("polisyos.scientist.orchestration.engine.retry.time.sleep"):
        if mode == "sync":
            result = execute_with_retry_sync(
                producer, _context(), ExperimentState(run_id="R_cat"), **kwargs
            )
        else:
            result = asyncio.run(
                execute_with_retry_async(
                    producer, _context(), ExperimentState(run_id="R_cat"), **kwargs
                )
            )
    assert result.status == "fail"
    assert producer.calls == expected_calls


def test_unclassified_node_error_preserves_legacy_serialized_shape():
    assert NodeError(code="node.old", message="old").model_dump(mode="json") == {
        "code": "node.old",
        "message": "old",
        "details": {},
    }


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("lost_at", ["before", "after"])
def test_live_owner_is_refreshed_at_dispatch_and_publication(mode, lost_at):
    """The actual retry consumer must stop on stale ownership, not just an event bit."""
    from threading import Event

    from polisyos.common.job_execution_interrupt import (
        JobExecutionInterrupt,
        JobExecutionInterrupted,
        job_execution_interrupt_scope,
    )

    owner_current = [lost_at != "before"]
    calls = []

    def check_owner():
        if not owner_current[0]:
            raise JobExecutionInterrupted("owner changed in external store")

    class Producer:
        def execute(self, _ctx, state):
            calls.append("executed")
            owner_current[0] = lost_at != "after"
            return _ok(state)

        async def execute_async(self, ctx, state):
            return self.execute(ctx, state)

    signal = JobExecutionInterrupt("job", "worker", 1, Event(), current_owner_check=check_owner)
    kwargs = {"retry_policy": RetryPolicy(max_retries=0), "timeout_s": None, "alias": "owner"}

    def invoke():
        if mode == "sync":
            execute_with_retry_sync(
                Producer(), _context(), ExperimentState(run_id="R_owner"), **kwargs
            )
        else:
            asyncio.run(
                execute_with_retry_async(
                    Producer(), _context(), ExperimentState(run_id="R_owner"), **kwargs
                )
            )

    with job_execution_interrupt_scope(signal), pytest.raises(JobExecutionInterrupted):
        invoke()
    assert calls == ([] if lost_at == "before" else ["executed"])
    assert signal.lost.is_set()


def test_diagnostic_details_category_cannot_override_legacy_retry_policy():
    """Untrusted details are never promoted into a retry-authority category."""
    from polisyos.scientist.orchestration.engine.retry import _should_retry

    error = NodeError(code="node.exception", message="legacy", details={"category": "fatal"})
    assert error.category is None
    assert _should_retry(error, RetryPolicy(max_retries=1))


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("retries", [0, 1])
def test_settlement_unknown_remains_primary_when_completion_fails(mode, retries):
    """A completion error cannot launder the producer's unknown settlement."""
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerSettlementOutcomeUnknownError,
    )

    unknown = BudgetLedgerSettlementOutcomeUnknownError("event", "digest")
    state = ExperimentState(run_id="unknown-primary", budgets={"run_spent_usd": Decimal("5")})
    calls = []

    class Producer:
        def execute(self, _ctx, _state):
            calls.append("dispatch")
            raise unknown

        async def execute_async(self, ctx, state):
            return self.execute(ctx, state)

    def started(_n, _state):
        return "attempt-1"

    def failed_completion(_id, _outcome):
        raise OSError("completion unavailable")

    async def async_started(n, input_state):
        return started(n, input_state)

    async def async_finished(attempt_id, outcome):
        failed_completion(attempt_id, outcome)

    def invoke():
        kwargs = {
            "retry_policy": RetryPolicy(max_retries=retries),
            "timeout_s": None,
            "alias": "unknown",
        }
        if mode == "sync":
            execute_with_retry_sync(
                Producer(),
                _context(),
                state,
                attempt_started=started,
                attempt_completed=failed_completion,
                **kwargs,
            )
        else:
            asyncio.run(
                execute_with_retry_async(
                    Producer(),
                    _context(),
                    state,
                    attempt_started=async_started,
                    attempt_completed=async_finished,
                    **kwargs,
                )
            )

    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError) as raised:
        invoke()
    assert raised.value is unknown
    assert raised.value.__cause__ is not None
    assert len(calls) == 1
    assert state.budgets["run_spent_usd"] == Decimal("5")


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("retries", [0, 1])
def test_original_interruption_survives_owner_loss_during_finalization(mode, retries):
    """A second worker-loss signal cannot erase the producer's original interruption."""
    from polisyos.common.job_execution_interrupt import JobExecutionInterrupted

    class LostReply(BaseException):
        pass

    original = LostReply("effect outcome unknown")
    state = ExperimentState(run_id="original-interruption")
    calls = []

    class Producer:
        def execute(self, _ctx, _state):
            calls.append(1)
            raise original

        async def execute_async(self, ctx, attempt_state):
            return self.execute(ctx, attempt_state)

    def started(_n, _state):
        return "attempt-1"

    def finished(_id, _outcome):
        raise JobExecutionInterrupted("owner lost during attempt finalization")

    async def started_async(n, current_state):
        return started(n, current_state)

    async def finished_async(attempt_id, outcome):
        finished(attempt_id, outcome)

    def invoke():
        kwargs = {
            "retry_policy": RetryPolicy(max_retries=retries),
            "timeout_s": None,
            "alias": "primary",
        }
        if mode == "sync":
            execute_with_retry_sync(
                Producer(),
                _context(),
                state,
                attempt_started=started,
                attempt_completed=finished,
                **kwargs,
            )
        else:
            asyncio.run(
                execute_with_retry_async(
                    Producer(),
                    _context(),
                    state,
                    attempt_started=started_async,
                    attempt_completed=finished_async,
                    **kwargs,
                )
            )

    with pytest.raises(LostReply) as raised:
        invoke()
    assert raised.value is original
    assert isinstance(raised.value.__cause__, JobExecutionInterrupted)
    assert calls == [1]


@pytest.mark.asyncio
async def test_pinned_physical_worker_keeps_resource_until_running_body_stops():
    """A cancelled waiter cannot close a resource used by its live worker."""
    import threading

    from polisyos.scientist.orchestration.engine import retry as retry_module

    started = threading.Event()
    finish = threading.Event()
    released = threading.Event()
    calls: list[str] = []

    class Node:
        def execute(self, _ctx, state):
            started.set()
            assert finish.wait(10)
            calls.append("body_finished")
            return _ok(state)

    def pin():
        calls.append("pinned")

        def release():
            calls.append("released")
            released.set()

        return release

    task = asyncio.create_task(
        retry_module._run_pinned_blocking(
            Node(), _context(), ExperimentState(run_id="pin-running"), pin
        )
    )
    try:
        for _ in range(500):
            if started.is_set():
                break
            await asyncio.sleep(0.01)
        assert started.is_set()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        assert not released.is_set()
        finish.set()
        for _ in range(500):
            if released.is_set():
                break
            await asyncio.sleep(0.01)
        assert calls == ["pinned", "body_finished", "released"]
    finally:
        finish.set()


@pytest.mark.asyncio
async def test_pinned_submit_error_abandons_enqueued_body_and_releases_once(monkeypatch):
    """An enqueue-then-error cannot later start against a released resource."""
    from polisyos.scientist.orchestration.engine import retry as retry_module

    queued = []
    calls: list[str] = []

    async def submit_then_raise(func, *args, **_kwargs):
        queued.append((func, args))
        raise RuntimeError("submit_reply_lost")

    class Node:
        def execute(self, _ctx, state):
            calls.append("body")
            return _ok(state)

    monkeypatch.setattr(retry_module, "run_blocking_async", submit_then_raise)
    with pytest.raises(RuntimeError, match="submit_reply_lost"):
        await retry_module._run_pinned_blocking(
            Node(),
            _context(),
            ExperimentState(run_id="pin-submit"),
            lambda: lambda: calls.append("release"),
        )
    assert calls == ["release"]
    func, args = queued[0]
    with pytest.raises(RuntimeError, match="physical_resource_call_abandoned"):
        func(*args)
    assert calls == ["release"]


@pytest.mark.asyncio
async def test_pinned_started_submit_error_is_unknown_and_never_replays(monkeypatch):
    """A lost submit acknowledgment cannot replay an already running body."""
    import threading

    from polisyos.scientist.orchestration.engine import retry as retry_module

    started = threading.Event()
    finish = threading.Event()
    released = threading.Event()
    calls = []
    workers = []
    worker_errors = []

    async def submit_then_raise(func, *args, **_kwargs):
        def run():
            try:
                func(*args)
            except BaseException as exc:
                worker_errors.append(exc)

        worker = threading.Thread(target=run)
        workers.append(worker)
        worker.start()
        for _ in range(500):
            if started.is_set():
                break
            await asyncio.sleep(0.01)
        assert started.is_set()
        raise RuntimeError("submit_reply_lost")

    class Node:
        def execute(self, _ctx, state):
            calls.append("body")
            started.set()
            assert finish.wait(10)
            return _ok(state)

    monkeypatch.setattr(retry_module, "run_blocking_async", submit_then_raise)
    try:
        with pytest.raises(RetryExhaustedError) as failure:
            await execute_with_retry_async(
                Node(),
                _context(),
                ExperimentState(run_id="pin-started-submit"),
                retry_policy=RetryPolicy(max_retries=2, retry_on=["node.exception"]),
                timeout_s=None,
                alias="pin",
                physical_resource_pin=lambda: released.set,
            )
        assert isinstance(failure.value.__cause__, retry_module._WorkerOutcomeUnknown)
        assert calls == ["body"]
        assert not released.is_set()
    finally:
        finish.set()
        for worker in workers:
            worker.join(timeout=5)
    assert released.is_set()
    assert calls == ["body"]


@pytest.mark.asyncio
async def test_pinned_release_failure_after_success_cannot_replay_effect():
    """A completed body plus failed cleanup cannot be retried as a provider error."""
    calls = []

    class Node:
        def execute(self, _ctx, state):
            calls.append("body")
            return _ok(state)

    def pin():
        def release():
            raise OSError("close_failed")

        return release

    with pytest.raises(RetryExhaustedError) as failure:
        await execute_with_retry_async(
            Node(),
            _context(),
            ExperimentState(run_id="pin-release-failure"),
            retry_policy=RetryPolicy(max_retries=2, retry_on=["node.exception"]),
            timeout_s=None,
            alias="pin",
            physical_resource_pin=pin,
        )
    from polisyos.scientist.orchestration.engine import retry as retry_module

    assert isinstance(failure.value.__cause__, retry_module._WorkerOutcomeUnknown)
    assert calls == ["body"]


@pytest.mark.asyncio
async def test_queued_pinned_cancellation_releases_once_and_refuses_late_body(monkeypatch):
    """Queued cancellation closes admission even if the queued callable is later run."""
    from polisyos.scientist.orchestration.engine import retry as retry_module

    entered = asyncio.Event()
    queued = []
    calls = []

    async def queued_call(func, *args, **_kwargs):
        queued.append((func, args))
        entered.set()
        await asyncio.Future()

    class Node:
        def execute(self, _ctx, state):
            calls.append("body")
            return _ok(state)

    monkeypatch.setattr(retry_module, "run_blocking_async", queued_call)
    task = asyncio.create_task(
        retry_module._run_pinned_blocking(
            Node(),
            _context(),
            ExperimentState(run_id="pin-queued"),
            lambda: lambda: calls.append("release"),
        )
    )
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls == ["release"]
    func, args = queued[0]
    with pytest.raises(RuntimeError, match="physical_resource_call_abandoned"):
        func(*args)
    assert calls == ["release"]


@pytest.mark.asyncio
async def test_managed_child_rejects_prepared_resource_before_dispatch():
    """Managed child may not silently discard the caller's physical pin."""
    from polisyos.scientist.orchestration.engine.child_workflow import _ManagedSubWorkflowDispatch
    from polisyos.scientist.orchestration.engine.errors import NodeTimeoutError

    node = object.__new__(_ManagedSubWorkflowDispatch)
    pin = MagicMock(side_effect=AssertionError("unsupported path must not acquire pin"))
    with pytest.raises(NodeTimeoutError) as refused:
        await execute_with_retry_async(
            node,
            _context(),
            ExperimentState(run_id="pin-child"),
            retry_policy=RetryPolicy(max_retries=0),
            timeout_s=None,
            alias="managed",
            physical_resource_pin=pin,
        )
    assert refused.value.details["reason"] == "prepared_managed_child_lifetime_not_established"
    pin.assert_not_called()
