"""The parent attempt budget is fixed once and never renewed by child work."""

from contextvars import copy_context
from threading import Event, RLock
from types import SimpleNamespace

import pytest

from polisyos.common.job_execution_interrupt import JobExecutionInterrupt
from polisyos.runtime.http.services.control import child_execution_budget as owner


def _claim() -> owner.ChildBudgetClaimLocator:
    return owner.ChildBudgetClaimLocator(
        job_id="job-a",
        run_id="run-a",
        attempt=1,
        worker_id="worker-a",
        event_id=1,
        policy_id="test-policy",
        policy_version="1",
        duration_seconds=10.0,
    )


def test_attempt_budget_is_fixed_once_and_cannot_cross_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [100.0]
    monkeypatch.setattr(owner.time, "monotonic", lambda: now[0])
    policy = owner.ChildExecutionBudgetPolicy("test-policy", "1", 10.0)
    job = SimpleNamespace(
        job_id="job-a", run_id="run-a", attempt=1, lease_owner="worker-a", kind="workflow_run"
    )
    interrupt = JobExecutionInterrupt("job-a", "worker-a", 1, Event())
    revoked = Event()
    owner_store = object()
    with owner._attempt_budget_scope(
        policy,
        job,
        interrupt,
        revoked,
        Event(),
        claim=_claim(),
        control_store=owner_store,
        transition_lock=RLock(),
    ):
        budget = owner._require_attempt_budget("job-a", "run-a", 1)
        assert budget.control_store is owner_store
        assert budget.deadline_monotonic == 110.0
        now[0] = 109.0
        assert owner._require_attempt_budget("job-a", "run-a", 1) is budget
        for bad_binding in (("job-b", "run-a", 1), ("job-a", "run-b", 1), ("job-a", "run-a", 2)):
            with pytest.raises(RuntimeError, match="child_execution_budget_unavailable"):
                owner._require_attempt_budget(*bad_binding)
        with (
            pytest.raises(RuntimeError, match="child_execution_budget_nested_scope"),
            owner._attempt_budget_scope(
                policy,
                job,
                interrupt,
                revoked,
                Event(),
                claim=_claim(),
                control_store=object(),
                transition_lock=RLock(),
            ),
        ):
            pytest.fail("nested attempt renewed budget")
        now[0] = 110.0
        with pytest.raises(RuntimeError, match="child_execution_budget_unavailable"):
            owner._require_attempt_budget("job-a", "run-a", 1)
    with pytest.raises(RuntimeError, match="child_execution_budget_unavailable"):
        owner._require_attempt_budget("job-a", "run-a", 1)


def test_missing_or_invalid_policy_does_not_mint_a_budget() -> None:
    job = SimpleNamespace(
        job_id="job-a", run_id="run-a", attempt=1, lease_owner="worker-a", kind="workflow_run"
    )
    interrupt = JobExecutionInterrupt("job-a", "worker-a", 1, Event())
    with (
        owner._attempt_budget_scope(None, job, interrupt, Event(), Event()),
        pytest.raises(RuntimeError, match="child_execution_budget_unavailable"),
    ):
        owner._require_attempt_budget("job-a", "run-a", 1)
    for duration in (0.0, -1.0, float("inf"), float("nan"), True):
        with pytest.raises(ValueError, match="child_execution_budget_policy_invalid"):
            owner.ChildExecutionBudgetPolicy("test-policy", "1", duration)


def test_attempt_budget_refuses_actual_owner_lease_loss() -> None:
    job = SimpleNamespace(
        job_id="job-a", run_id="run-a", attempt=1, lease_owner="worker-a", kind="workflow_run"
    )
    interrupt = JobExecutionInterrupt("job-a", "worker-a", 1, Event())
    policy = owner.ChildExecutionBudgetPolicy("test-policy", "1", 10.0)
    revoked = Event()
    with owner._attempt_budget_scope(
        policy,
        job,
        interrupt,
        revoked,
        Event(),
        claim=_claim(),
        control_store=object(),
        transition_lock=RLock(),
    ):
        owner._require_attempt_budget("job-a", "run-a", 1)
        interrupt.lost.set()
        with pytest.raises(RuntimeError, match="child_execution_budget_unavailable"):
            owner._require_attempt_budget("job-a", "run-a", 1)


def test_copied_context_cannot_outlive_the_worker_attempt() -> None:
    job = SimpleNamespace(
        job_id="job-a", run_id="run-a", attempt=1, lease_owner="worker-a", kind="workflow_run"
    )
    interrupt = JobExecutionInterrupt("job-a", "worker-a", 1, Event())
    revoked = Event()
    uncertain = Event()
    with owner._attempt_budget_scope(
        owner.ChildExecutionBudgetPolicy("test-policy", "1", 10.0),
        job,
        interrupt,
        revoked,
        uncertain,
        claim=_claim(),
        control_store=object(),
        transition_lock=RLock(),
    ):
        inherited_context = copy_context()
        assert inherited_context.run(owner._require_attempt_budget, "job-a", "run-a", 1)
    assert revoked.is_set() and not uncertain.is_set()
    with pytest.raises(RuntimeError, match="child_execution_budget_unavailable"):
        inherited_context.run(owner._require_attempt_budget, "job-a", "run-a", 1)


def test_non_workflow_job_does_not_receive_composition_budget() -> None:
    job = SimpleNamespace(
        job_id="job-a", run_id="run-a", attempt=1, lease_owner="worker-a", kind="acquisition"
    )
    interrupt = JobExecutionInterrupt("job-a", "worker-a", 1, Event())
    with (
        owner._attempt_budget_scope(
            owner.ChildExecutionBudgetPolicy("test-policy", "1", 10.0),
            job,
            interrupt,
            Event(),
            Event(),
        ),
        pytest.raises(RuntimeError, match="child_execution_budget_unavailable"),
    ):
        owner._require_attempt_budget("job-a", "run-a", 1)


def test_actual_app_bootstrap_passes_the_exact_trusted_policy(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from polisyos.runtime.http.app import create_runtime_api_app

    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "embedded")
    policy = owner.ChildExecutionBudgetPolicy("test-policy", "1", 10.0)
    app = create_runtime_api_app(
        cas_root=tmp_path / "cas",
        enable_security_middlewares=False,
        child_execution_budget_policy=policy,
    )
    with TestClient(app) as client:
        service = client.app.state.runtime_container.control_service
        assert service._child_execution_budget_policy is policy
        assert service._worker._child_execution_budget_policy is policy
