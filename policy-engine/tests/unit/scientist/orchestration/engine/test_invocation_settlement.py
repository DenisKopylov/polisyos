"""Real CAS and ledger controls for the engine-issued invocation settlement view."""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from polisyos.core.artifacts import input_ref_from_artifact_ref
from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine._invocation_settlement import (
    _invocation_spend_identity,
    _issue_invocation_settlement_view,
    _verify_invocation_settlement_receipt,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerSettlementOutcomeUnknownError,
    BudgetLedgerSpendReceipt,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.runner.error_classifier import (
    RemoteErrorCategory,
    classify_remote_error,
)


@pytest.fixture
def invocation(tmp_path: Path, request: pytest.FixtureRequest):
    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store, return_selected_profile=True)
    job_bound = getattr(request, "param", None) == "job-bound"
    run = RunContext.start(
        store=store,
        registry_bundle=bundle.bundle_ref,
        run_id="run-issued",
        tenant_id="fixture-tenant" if job_bound else None,
        cell_id="fixture-cell" if job_bound else None,
    )
    if job_bound:
        run.update_manifest(control_job_id="fixture-job")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    ledger = FileBudgetLedger(tmp_path / "budget.json", ledger_id="ledger:owner")
    budget = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    middleware = BudgetMiddleware(
        budget, ledger=ledger, invocation_settlement_profile="single_owner_local_v1"
    )
    middleware.record_spend_safe("run", Decimal("5"))
    owner, resource, (revision, digest) = middleware.continuation_binding()
    workflow = store.put_json(
        {"workflow": "fixture"},
        ArtifactWriteOptions(kind="fixture.workflow", media_type="application/json"),
        return_selected_profile=True,
    )
    state = store.put_json(
        {"run_id": "run-issued"},
        ArtifactWriteOptions(kind="fixture.state", media_type="application/json"),
        return_selected_profile=True,
    )
    attempt_id = str(uuid4())
    basis = run._record_runtime_invocation_started(
        attempt_id=attempt_id,
        attempt_number=1,
        workflow_spec_ref=workflow,
        node_alias="effect",
        component_id="scientist.fixture_effect@1.0.0",
        input_state_ref=state,
        execution_budget_contract="admitted_workflow_budget_v1",
        budget_middleware_active=True,
        budget_owner_identity=owner,
        budget_resource_identity=resource,
        budget_start_revision=revision,
        budget_start_snapshot_sha256=digest,
        invocation_settlement_profile=middleware.invocation_settlement_profile,
    )
    payload = store.put_json(
        {"effect": "actual"},
        ArtifactWriteOptions(kind="fixture.effect", media_type="application/json"),
        return_selected_profile=True,
    )
    try:
        yield ctx, middleware, ledger, attempt_id, basis, payload
    finally:
        run.suspend_for_resume()


def test_real_engine_view_issues_attempt_bound_receipt_once(invocation) -> None:
    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    view = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    assert view.settlement_attempted is False
    assert view._settlement_uncertain is False
    assert view._verify_acknowledged_settlement() is None
    receipt_ref = view.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")
    assert view.settlement_attempted is True
    assert view._settlement_uncertain is False
    verified = view._verify_acknowledged_settlement()
    assert verified is not None
    assert (verified.amount, verified.total) == (Decimal("2"), Decimal("7"))
    assert (verified.payload_ref, verified.receipt_ref) == (payload, receipt_ref)
    verified.payload_ref.kind = "fixture.detached-copy"
    verified_again = view._verify_acknowledged_settlement()
    assert verified_again is not None and verified_again.payload_ref == payload
    repeated = view.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")
    assert repeated == receipt_ref
    receipt = _verify_invocation_settlement_receipt(
        ctx.store,
        receipt_ref,
        [payload, receipt_ref],
        run_id="run-issued",
        alias="effect",
        attempt_id=attempt_id,
        basis_ref=basis,
        snapshot=ledger.snapshot(),
    )
    assert receipt.amount == Decimal("2")
    assert ledger.resolve_spend(receipt.event_id) == receipt
    assert view.spent == Decimal("7")
    assert not hasattr(view, "ledger")
    assert not hasattr(view, "load_or_bootstrap")


def test_real_receipt_rejects_wrong_attempt_and_unselected_effect(invocation) -> None:
    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    view = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    receipt_ref = view.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")
    with pytest.raises(ValueError, match="budget_invocation_receipt_attempt_mismatch"):
        _verify_invocation_settlement_receipt(
            ctx.store,
            receipt_ref,
            [payload, receipt_ref],
            run_id="run-issued",
            alias="effect",
            attempt_id=str(uuid4()),
            basis_ref=basis,
            snapshot=ledger.snapshot(),
        )
    unselected = ArtifactRef(
        artifact_id=payload.artifact_id,
        kind=payload.kind,
        media_type=payload.media_type,
    )
    with pytest.raises(ValueError, match="budget_invocation_payload_not_owned"):
        _verify_invocation_settlement_receipt(
            ctx.store,
            receipt_ref,
            [unselected, receipt_ref],
            run_id="run-issued",
            alias="effect",
            attempt_id=attempt_id,
            basis_ref=basis,
            snapshot=ledger.snapshot(),
        )


def test_peer_cannot_issue_view_for_a_different_core_attempt(invocation) -> None:
    ctx, middleware, _ledger, attempt_id, basis, _payload = invocation
    with pytest.raises(ValueError, match="budget_invocation_basis_not_owner_linked"):
        _issue_invocation_settlement_view(
            middleware, ctx, alias="effect", attempt_id=str(uuid4()), basis_ref=basis
        )
    with pytest.raises(ValueError, match="budget_invocation_not_active"):
        _issue_invocation_settlement_view(
            middleware, ctx, alias="other", attempt_id=attempt_id, basis_ref=basis
        )


def test_fake_middleware_cannot_mint_authority_from_real_core_basis(invocation) -> None:
    ctx, _middleware, _ledger, attempt_id, basis, _payload = invocation

    class FakeMiddleware:
        invocation_settlement_profile = "single_owner_local_v1"

        def __init__(self) -> None:
            self.called = False

        def _arm_engine_guard(self, *_args) -> None:
            self.called = True

        def _issue_engine_settlement_writer(self):
            return lambda *_args: None

        def _read_engine_spent(self) -> Decimal:
            return Decimal("0")

    fake = FakeMiddleware()
    with pytest.raises(ValueError, match="budget_ledger_engine_owner_not_supported"):
        _issue_invocation_settlement_view(
            fake,
            ctx,
            alias="effect",
            attempt_id=attempt_id,
            basis_ref=basis,  # type: ignore[arg-type]
        )
    assert fake.called is False


def test_two_costed_attempts_charge_separately_and_each_reconciles_once(invocation) -> None:
    ctx, middleware, ledger, first_id, first_basis, payload = invocation
    first = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=first_id, basis_ref=first_basis
    )
    first_ref = first.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")
    assert (
        first.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture") == first_ref
    )
    first_start = ctx.run.read_runtime_invocation_attempts()[0].basis
    ctx.run._record_runtime_invocation_completed(
        attempt_id=first_id,
        attempt_number=1,
        basis_ref=first_basis,
        status="fail",
        outcome_state_ref=first_start.input_state_ref,
        output_refs=[payload, first_ref],
    )
    with pytest.raises(ValueError, match="budget_invocation_not_active"):
        first.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")

    owner, resource, (revision, digest) = middleware.continuation_binding()
    second_id = str(uuid4())
    second_basis = ctx.run._record_runtime_invocation_started(
        attempt_id=second_id,
        attempt_number=2,
        workflow_spec_ref=first_start.workflow_spec_ref,
        node_alias="effect",
        component_id=first_start.component_id,
        input_state_ref=first_start.input_state_ref,
        execution_budget_contract="admitted_workflow_budget_v1",
        budget_middleware_active=True,
        budget_owner_identity=owner,
        budget_resource_identity=resource,
        budget_start_revision=revision,
        budget_start_snapshot_sha256=digest,
        invocation_settlement_profile=middleware.invocation_settlement_profile,
    )
    second = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=second_id, basis_ref=second_basis
    )
    second_ref = second.settle_spend(Decimal("1"), payload_ref=payload, provider="local-fixture")
    assert (
        second.settle_spend(Decimal("1"), payload_ref=payload, provider="local-fixture")
        == second_ref
    )
    first_receipt = _verify_invocation_settlement_receipt(
        ctx.store,
        first_ref,
        [payload, first_ref],
        run_id="run-issued",
        alias="effect",
        attempt_id=first_id,
        basis_ref=first_basis,
        snapshot=ledger.snapshot(),
    )
    second_receipt = _verify_invocation_settlement_receipt(
        ctx.store,
        second_ref,
        [payload, second_ref],
        run_id="run-issued",
        alias="effect",
        attempt_id=second_id,
        basis_ref=second_basis,
        snapshot=ledger.snapshot(),
    )
    assert first_receipt.event_id != second_receipt.event_id
    assert ledger.resolve_spend(first_receipt.event_id) == first_receipt
    assert ledger.resolve_spend(second_receipt.event_id) == second_receipt
    assert second.spent == Decimal("8")


@pytest.mark.parametrize("error_type", [OSError, RuntimeError, ValueError, TypeError])
def test_receipt_delivery_failure_is_unknown_and_same_attempt_reconciles(
    invocation, monkeypatch: pytest.MonkeyPatch, error_type: type[Exception]
) -> None:
    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    view = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    put_json = ctx.store.put_json
    delivered: list[ArtifactRef] = []

    def lose_first_ack(*args, **kwargs):
        ref = put_json(*args, **kwargs)
        if not delivered:
            delivered.append(ref)
            raise error_type("receipt delivery lost after actual ledger and CAS write")
        return ref

    monkeypatch.setattr(ctx.store, "put_json", lose_first_ack)
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError) as caught:
        view.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")
    assert view.settlement_attempted is True
    assert view._settlement_uncertain is True
    assert view._acknowledged_settlement() is None
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError) as inspected:
        view._verify_acknowledged_settlement()
    assert (inspected.value.event_id, inspected.value.payload_digest) == (
        caught.value.event_id,
        caught.value.payload_digest,
    )
    assert classify_remote_error(caught.value) is RemoteErrorCategory.FATAL
    assert len(delivered) == 1
    receipt_ref = view.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")
    receipt = _verify_invocation_settlement_receipt(
        ctx.store,
        receipt_ref,
        [payload, receipt_ref],
        run_id="run-issued",
        alias="effect",
        attempt_id=attempt_id,
        basis_ref=basis,
        snapshot=ledger.snapshot(),
    )
    assert caught.value.event_id == receipt.event_id
    assert caught.value.payload_digest == receipt.payload_digest
    assert ledger.resolve_spend(receipt.event_id) == receipt
    assert view.spent == Decimal("7")
    assert view._settlement_uncertain is False
    verified = view._verify_acknowledged_settlement()
    assert verified is not None and (verified.amount, verified.total) == (
        Decimal("2"),
        Decimal("7"),
    )


def test_failed_repeat_preserves_known_receipt_but_remains_uncertain(invocation) -> None:
    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    view = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    receipt_ref = view.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
        view.settle_spend(Decimal("3"), payload_ref=payload, provider="local-fixture")
    assert view._acknowledged_settlement() == (payload, receipt_ref)
    assert view._settlement_uncertain is True
    prior = view._verify_prior_acknowledged_settlement()
    assert prior is not None and (prior.amount, prior.total) == (Decimal("2"), Decimal("7"))
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
        view._verify_acknowledged_settlement()
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
        view._reconcile_pending_settlement()
    assert ledger.snapshot().state.spent["run"] == Decimal("7")
    assert (
        view.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")
        == receipt_ref
    )
    assert view._settlement_uncertain is False
    verified = view._verify_acknowledged_settlement()
    assert verified is not None and (verified.amount, verified.total) == (
        Decimal("2"),
        Decimal("7"),
    )


@pytest.mark.parametrize("mode", ["recover", "unavailable", "absent", "ledger_unavailable"])
def test_owner_reconciles_only_existing_exact_event_after_lost_ack(
    invocation, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """Reconciliation may republish evidence but never redispatch or create a charge."""
    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    view = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    put_json, settle = ctx.store.put_json, ledger._settle_spend
    calls = {"settle": 0, "receipt": 0}

    def selected_receipt_ack(obj, opts, canon_spec=None, *, return_selected_profile=False):
        ref = put_json(
            obj, opts, canon_spec=canon_spec, return_selected_profile=return_selected_profile
        )
        if opts.kind == "scientist.budget_spend_receipt":
            calls["receipt"] += 1
            if mode == "unavailable" or calls["receipt"] == 1:
                raise OSError("actual selected receipt write committed; response unavailable")
        return ref

    def settle_once(*args, **kwargs):
        calls["settle"] += 1
        if mode == "absent":
            raise OSError("settlement failed before event publication")
        return settle(*args, **kwargs)

    monkeypatch.setattr(ctx.store, "put_json", selected_receipt_ack)
    monkeypatch.setattr(ledger, "_settle_spend", settle_once)
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError) as first:
        view.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")
    assert view._acknowledged_settlement() is None
    assert view._settlement_uncertain is True
    if mode == "ledger_unavailable":
        from polisyos.scientist.orchestration.engine import budget_ledger as ledger_module

        sync = ledger_module._fsync_dir

        def fail_sync(_directory: Path) -> None:
            raise OSError("ledger readback cannot confirm directory sync")

        monkeypatch.setattr(ledger_module, "_fsync_dir", fail_sync)
    if mode == "recover":
        verified = view._reconcile_pending_settlement()
        assert verified is not None and (verified.amount, verified.total) == (
            Decimal("2"),
            Decimal("7"),
        )
        assert verified.payload_ref == payload
        assert (
            ledger.resolve_spend(first.value.event_id).payload_digest == first.value.payload_digest
        )
        assert view._settlement_uncertain is False
        assert calls == {"settle": 1, "receipt": 2}
    else:
        with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError) as unresolved:
            view._reconcile_pending_settlement()
        assert (unresolved.value.event_id, unresolved.value.payload_digest) == (
            first.value.event_id,
            first.value.payload_digest,
        )
        assert view._settlement_uncertain is True
        assert calls["settle"] == 1
        if mode == "ledger_unavailable":
            assert isinstance(unresolved.value.__cause__, BudgetLedgerSettlementOutcomeUnknownError)
            assert unresolved.value.__cause__.event_id == "ledger-snapshot"
            monkeypatch.setattr(ledger_module, "_fsync_dir", sync)
        expected = Decimal("5") if mode == "absent" else Decimal("7")
        assert ledger.snapshot().state.spent["run"] == expected


@pytest.mark.parametrize("control", ["locked", "remove_view_lock"])
def test_concurrent_reconciliation_cannot_erase_a_later_unknown(
    invocation, monkeypatch: pytest.MonkeyPatch, control: str
) -> None:
    """A stale reconciliation must not clear a distinct later unresolved call."""
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import nullcontext
    from threading import Event

    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    view = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    if control == "remove_view_lock":
        monkeypatch.setattr(view, "_InvocationSettlementView__lock", nullcontext())
    put_json = ctx.store.put_json
    reconcile_entered, release_reconcile = Event(), Event()
    second_started, second_finished = Event(), Event()
    receipt_calls = 0

    def gated_receipt(obj, opts, canon_spec=None, *, return_selected_profile=False):
        nonlocal receipt_calls
        if opts.kind == "scientist.budget_spend_receipt":
            receipt_calls += 1
            if receipt_calls == 2:
                reconcile_entered.set()
                assert release_reconcile.wait(timeout=5)
        ref = put_json(
            obj, opts, canon_spec=canon_spec, return_selected_profile=return_selected_profile
        )
        if opts.kind == "scientist.budget_spend_receipt" and receipt_calls == 1:
            raise OSError("first selected receipt committed but acknowledgment was lost")
        return ref

    monkeypatch.setattr(ctx.store, "put_json", gated_receipt)
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
        view.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")

    def conflicting_settlement() -> None:
        second_started.set()
        try:
            view.settle_spend(Decimal("3"), payload_ref=payload, provider="local-fixture")
        finally:
            second_finished.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(view._reconcile_pending_settlement)
        try:
            assert reconcile_entered.wait(timeout=5)
            second = pool.submit(conflicting_settlement)
            assert second_started.wait(timeout=5)
            if control == "locked":
                assert not second_finished.wait(timeout=0.25)
            else:
                assert second_finished.wait(timeout=5)
                with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
                    second.result(timeout=5)
        finally:
            release_reconcile.set()
        verified = first.result(timeout=5)
        if control == "locked":
            with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
                second.result(timeout=5)

    assert verified is not None and (verified.amount, verified.total) == (
        Decimal("2"),
        Decimal("7"),
    )
    assert ledger.snapshot().state.spent["run"] == Decimal("7")
    assert view._settlement_uncertain is (control == "locked")
    if control == "locked":
        with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
            view._verify_acknowledged_settlement()
        prior = view._verify_prior_acknowledged_settlement()
        assert prior is not None and prior.amount == Decimal("2")
    else:
        # The removal control exposes the exact stale-clear failure, without
        # presenting its false acknowledgment as a product success.
        assert view._verify_acknowledged_settlement() is not None


@pytest.mark.parametrize("lost_on_check", [1, 2])
def test_reconciliation_does_not_publish_proof_after_owner_is_lost(
    invocation, monkeypatch: pytest.MonkeyPatch, lost_on_check: int
) -> None:
    """Synthetic lease loss is preserved before CAS publication and before proof return."""
    from threading import Event

    from polisyos.common.job_execution_interrupt import (
        JobExecutionInterrupt,
        JobExecutionInterrupted,
        job_execution_interrupt_scope,
    )

    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    view = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    put_json = ctx.store.put_json
    calls = {"receipt": 0, "owner": 0}

    def selected_receipt_ack(obj, opts, canon_spec=None, *, return_selected_profile=False):
        ref = put_json(
            obj, opts, canon_spec=canon_spec, return_selected_profile=return_selected_profile
        )
        if opts.kind == "scientist.budget_spend_receipt":
            calls["receipt"] += 1
            if calls["receipt"] == 1:
                raise OSError("actual receipt committed but its acknowledgment was lost")
        return ref

    def current_owner_check() -> None:
        calls["owner"] += 1
        if calls["owner"] == lost_on_check:
            raise JobExecutionInterrupted("controlled owner loss")

    monkeypatch.setattr(ctx.store, "put_json", selected_receipt_ack)
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
        view.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")
    signal = JobExecutionInterrupt(
        job_id="fixture-job",
        worker_id="fixture-owner",
        attempt=1,
        lost=Event(),
        current_owner_check=current_owner_check,
    )
    with (
        job_execution_interrupt_scope(signal),
        pytest.raises(JobExecutionInterrupted, match="controlled owner loss"),
    ):
        view._reconcile_pending_settlement()
    assert signal.lost.is_set()
    assert calls["owner"] == lost_on_check
    assert calls["receipt"] == lost_on_check
    assert view._settlement_uncertain is True
    assert view._acknowledged_settlement() is None
    assert ledger.snapshot().state.spent["run"] == Decimal("7")


@pytest.mark.parametrize("invocation", ["job-bound"], indirect=True)
@pytest.mark.parametrize("operation", ["issue", "settle", "reconcile"])
@pytest.mark.parametrize("scope_name", ["missing", "event_only", "foreign", "matching"])
def test_job_bound_settlement_requires_the_same_live_job_owner(
    invocation, monkeypatch: pytest.MonkeyPatch, operation: str, scope_name: str
) -> None:
    """A protected job ID restricts the actual issuer, write and recovery paths."""
    from contextlib import nullcontext
    from threading import Event

    from polisyos.common.job_execution_interrupt import (
        JobExecutionInterrupt,
        JobExecutionOwnerNotEstablishedError,
        job_execution_interrupt_scope,
    )

    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    assert ctx.run.run_manifest.control_job_id == "fixture-job"
    put_json, settle = ctx.store.put_json, ledger._settle_spend
    calls = {"receipt": 0, "settle": 0, "owner": 0}

    def current_owner_check() -> None:
        calls["owner"] += 1

    def selected_receipt_ack(obj, opts, canon_spec=None, *, return_selected_profile=False):
        ref = put_json(
            obj, opts, canon_spec=canon_spec, return_selected_profile=return_selected_profile
        )
        if opts.kind == "scientist.budget_spend_receipt":
            calls["receipt"] += 1
            if operation == "reconcile" and calls["receipt"] == 1:
                raise OSError("receipt persisted but its acknowledgment was lost")
        return ref

    def observe_settle(*args, **kwargs):
        calls["settle"] += 1
        return settle(*args, **kwargs)

    monkeypatch.setattr(ctx.store, "put_json", selected_receipt_ack)
    monkeypatch.setattr(ledger, "_settle_spend", observe_settle)

    def signal(job_id: str, *, with_check: bool = True) -> JobExecutionInterrupt:
        return JobExecutionInterrupt(
            job_id=job_id,
            worker_id="fixture-owner",
            attempt=1,
            lost=Event(),
            current_owner_check=current_owner_check if with_check else None,
        )

    view = None
    first_unknown = None
    if operation != "issue":
        with job_execution_interrupt_scope(signal("fixture-job")):
            view = _issue_invocation_settlement_view(
                middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
            )
            if operation == "reconcile":
                with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError) as first:
                    view.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")
                first_unknown = first.value
    calls["owner"] = 0
    scope = {
        "missing": nullcontext(),
        "event_only": job_execution_interrupt_scope(signal("fixture-job", with_check=False)),
        "foreign": job_execution_interrupt_scope(signal("other-job")),
        "matching": job_execution_interrupt_scope(signal("fixture-job")),
    }[scope_name]

    def invoke():
        if operation == "issue":
            return _issue_invocation_settlement_view(
                middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
            )
        assert view is not None
        if operation == "settle":
            return view.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")
        return view._reconcile_pending_settlement()

    with scope:
        if scope_name == "matching":
            result = invoke()
            assert result is not None and calls["owner"] > 0
        elif operation == "reconcile":
            with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError) as unresolved:
                invoke()
            assert first_unknown is not None
            assert (unresolved.value.event_id, unresolved.value.payload_digest) == (
                first_unknown.event_id,
                first_unknown.payload_digest,
            )
            assert isinstance(unresolved.value.__cause__, JobExecutionOwnerNotEstablishedError)
        else:
            with pytest.raises(JobExecutionOwnerNotEstablishedError):
                invoke()

    if operation == "issue" or (operation == "settle" and scope_name != "matching"):
        assert calls["settle"] == calls["receipt"] == 0
        assert ledger.snapshot().state.spent["run"] == Decimal("5")
    else:
        assert calls["settle"] == 1
        assert calls["receipt"] == (
            2 if operation == "reconcile" and scope_name == "matching" else 1
        )
        assert ledger.snapshot().state.spent["run"] == Decimal("7")
    if scope_name != "matching":
        assert calls["owner"] == 0


@pytest.mark.parametrize("invocation", ["job-bound"], indirect=True)
@pytest.mark.parametrize(
    "loss_point", ["after_ledger", "after_receipt", "before_verified_readback"]
)
def test_job_owner_loss_during_real_settlement_cannot_publish_a_proof(
    invocation, monkeypatch: pytest.MonkeyPatch, loss_point: str
) -> None:
    """Loss after an actual write remains ambiguous and cannot return evidence."""
    from threading import Event

    from polisyos.common.job_execution_interrupt import (
        JobExecutionInterrupt,
        JobExecutionInterrupted,
        job_execution_interrupt_scope,
    )

    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    lost = Event()
    signal = JobExecutionInterrupt(
        job_id="fixture-job",
        worker_id="fixture-owner",
        attempt=1,
        lost=lost,
        current_owner_check=lambda: None,
    )
    put_json = ctx.store.put_json
    written_receipts: list[ArtifactRef] = []

    def observe_receipt(obj, opts, canon_spec=None, *, return_selected_profile=False):
        ref = put_json(
            obj,
            opts,
            canon_spec=canon_spec,
            return_selected_profile=return_selected_profile,
        )
        if opts.kind == "scientist.budget_spend_receipt":
            written_receipts.append(ref)
            if loss_point == "after_receipt":
                lost.set()
        return ref

    monkeypatch.setattr(ctx.store, "put_json", observe_receipt)
    with job_execution_interrupt_scope(signal):
        view = _issue_invocation_settlement_view(
            middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
        )
        if loss_point == "before_verified_readback":
            receipt = view.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")
            read_snapshot = ledger._continuation_state

            def interrupted_read():
                result = read_snapshot()
                lost.set()
                return result

            monkeypatch.setattr(ledger, "_continuation_state", interrupted_read)
            with pytest.raises(JobExecutionInterrupted):
                view._verify_acknowledged_settlement()
            assert view._acknowledged_settlement() == (payload, receipt)
        else:
            if loss_point == "after_ledger":
                settle = ledger._settle_spend

                def interrupted_settle(*args, **kwargs):
                    result = settle(*args, **kwargs)
                    lost.set()
                    return result

                monkeypatch.setattr(ledger, "_settle_spend", interrupted_settle)
            with pytest.raises(JobExecutionInterrupted):
                view.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")
            assert view._settlement_uncertain is True
            assert view._acknowledged_settlement() is None

    assert lost.is_set()
    snapshot = ledger.snapshot()
    assert snapshot.state.spent["run"] == Decimal("7")
    assert len(snapshot.spend_receipts) == 1
    assert len(written_receipts) == (0 if loss_point == "after_ledger" else 1)


@pytest.mark.parametrize("invocation", ["job-bound"], indirect=True)
@pytest.mark.parametrize("execution", ["sync", "async"])
@pytest.mark.parametrize("wrong_scope", ["event_only", "foreign"])
def test_retry_does_not_redispatch_a_refused_job_owner(
    invocation, execution: str, wrong_scope: str
) -> None:
    """A producer cannot turn a missing live job owner into a retryable failure."""
    import asyncio
    from dataclasses import replace
    from threading import Event

    from polisyos.common.job_execution_interrupt import (
        JobExecutionInterrupt,
        JobExecutionOwnerNotEstablishedError,
        job_execution_interrupt_scope,
    )
    from polisyos.core.trace.record import TraceRecord
    from polisyos.scientist.orchestration.engine.context import _EngineInvocationBinding
    from polisyos.scientist.orchestration.engine.retry import (
        RetryPolicy,
        execute_with_retry_async,
        execute_with_retry_sync,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    good = JobExecutionInterrupt(
        job_id="fixture-job",
        worker_id="fixture-owner",
        attempt=1,
        lost=Event(),
        current_owner_check=lambda: None,
    )
    invalid = JobExecutionInterrupt(
        job_id="other-job" if wrong_scope == "foreign" else "fixture-job",
        worker_id="fixture-owner",
        attempt=1,
        lost=Event(),
        current_owner_check=(lambda: None) if wrong_scope == "foreign" else None,
    )
    dispatches: list[int] = []
    finalizations: list[tuple[str, object]] = []

    class WrongOwnerNode:
        def execute(self, node_ctx, _attempt_state):
            dispatches.append(1)
            with job_execution_interrupt_scope(invalid):
                return node_ctx._engine_invocation.settlement_view.settle_spend(
                    Decimal("2"), payload_ref=payload, provider="local-fixture"
                )

        async def execute_async(self, node_ctx, attempt_state):
            return self.execute(node_ctx, attempt_state)

    def started(number, _state):
        assert number == 1
        return attempt_id

    def completed(selected_attempt, outcome):
        finalizations.append((selected_attempt, outcome))

    async def started_async(number, state):
        return started(number, state)

    async def completed_async(selected_attempt, outcome):
        completed(selected_attempt, outcome)

    with job_execution_interrupt_scope(good):
        view = _issue_invocation_settlement_view(
            middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
        )
        bound = replace(
            ctx,
            _engine_invocation=_EngineInvocationBinding(
                run_id="run-issued", attempt_id=attempt_id, basis_ref=basis, settlement_view=view
            ),
        )

        def bind(selected_attempt):
            assert selected_attempt == attempt_id
            return bound

        state = ExperimentState(run_id="run-issued", budgets={"run_spent_usd": Decimal("5")})
        policy = RetryPolicy(
            max_retries=1, retry_on=["node.exception"], backoff_base_s=0.1, jitter="none"
        )

        def invoke():
            if execution == "sync":
                return execute_with_retry_sync(
                    WrongOwnerNode(),
                    bound,
                    state,
                    retry_policy=policy,
                    timeout_s=None,
                    alias="effect",
                    attempt_started=started,
                    attempt_completed=completed,
                    attempt_context=bind,
                )
            return asyncio.run(
                execute_with_retry_async(
                    WrongOwnerNode(),
                    bound,
                    state,
                    retry_policy=policy,
                    timeout_s=None,
                    alias="effect",
                    attempt_started=started_async,
                    attempt_completed=completed_async,
                    attempt_context=bind,
                )
            )

        with pytest.raises(Exception) as caught:
            invoke()

    chain: list[BaseException] = []
    error: BaseException | None = caught.value
    while error is not None and error not in chain:
        chain.append(error)
        error = error.__cause__ or error.__context__
    assert any(isinstance(error, JobExecutionOwnerNotEstablishedError) for error in chain)
    assert dispatches == [1]
    assert finalizations == [(attempt_id, None)]
    assert state.budgets["run_spent_usd"] == Decimal("5")
    snapshot = ledger.snapshot()
    assert snapshot.state.spent["run"] == Decimal("5") and not snapshot.spend_receipts
    assert ctx.run.trace_path is not None
    trace = [
        TraceRecord.model_validate_json(line)
        for line in ctx.run.trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert not any(event.event == "NODE_RETRY" for event in trace)


def test_refused_settlement_attempt_cannot_appear_as_no_charge(invocation) -> None:
    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    view = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    unselected = ArtifactRef(
        artifact_id=payload.artifact_id,
        kind=payload.kind,
        media_type=payload.media_type,
    )
    assert view.settlement_attempted is False
    with pytest.raises(ValueError, match="budget_invocation_payload_profile_required"):
        view.settle_spend(Decimal("2"), payload_ref=unselected)
    assert view.settlement_attempted is True
    assert view._settlement_uncertain is True
    with pytest.raises(ValueError, match="budget_invocation_payload_profile_required"):
        view._verify_acknowledged_settlement()
    assert ledger.snapshot().state.spent["run"] == Decimal("5")
    with pytest.raises(AttributeError):
        view.settlement_attempted = False


def test_valid_shaped_forged_receipt_without_ledger_event_is_refused(invocation) -> None:
    ctx, _middleware, ledger, attempt_id, basis, payload = invocation
    event_id, digest = _invocation_spend_identity(
        run_id="run-issued",
        alias="effect",
        attempt_id=attempt_id,
        basis_ref=basis,
        payload_ref=payload,
    )
    snapshot = ledger.snapshot()
    forged = BudgetLedgerSpendReceipt(
        event_id=event_id,
        payload_digest=digest,
        key="run",
        amount=Decimal("2"),
        provider="local-fixture",
        revision=snapshot.revision + 1,
    )
    forged_ref = ctx.store.put_json(
        forged.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind="scientist.budget_spend_receipt",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.budget_ledger.BudgetLedgerSpendReceipt",
                version="1.0",
            ),
            producer=ProducerInfo(component="forged.fixture", version="1.0"),
            inputs=[
                input_ref_from_artifact_ref(basis, role="invocation_basis"),
                input_ref_from_artifact_ref(payload, role="producer_payload"),
            ],
        ),
        return_selected_profile=True,
    )
    assert ledger.resolve_spend(event_id) is None
    with pytest.raises(ValueError, match="budget_invocation_receipt_attempt_mismatch"):
        _verify_invocation_settlement_receipt(
            ctx.store,
            forged_ref,
            [payload, forged_ref],
            run_id="run-issued",
            alias="effect",
            attempt_id=attempt_id,
            basis_ref=basis,
            snapshot=snapshot,
        )


@pytest.mark.parametrize("mode", ["sync", "async", "codec", "falsey"])
def test_issued_settlement_view_refuses_process_transport_before_dispatch(invocation, mode):
    """A local-only owner view cannot disappear into a timed child process."""
    import asyncio
    from dataclasses import replace
    from unittest.mock import MagicMock

    from polisyos.scientist.orchestration.engine.context import _EngineInvocationBinding
    from polisyos.scientist.orchestration.engine.errors import NodeTimeoutError
    from polisyos.scientist.orchestration.engine.retry import (
        _execute_with_timeout_process,
        _execute_with_timeout_process_async,
    )
    from polisyos.scientist.orchestration.engine.runner.serialization import (
        serialize_timeout_context,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    ctx, middleware, _ledger, attempt_id, basis, _payload = invocation
    issued = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    binding = _EngineInvocationBinding(
        run_id="run-issued",
        attempt_id=attempt_id,
        basis_ref=basis,
        settlement_view=False if mode == "falsey" else issued,
    )
    bound = replace(ctx, _engine_invocation=binding)
    node = MagicMock()
    state = ExperimentState(run_id="run-issued")
    if mode == "codec":
        with pytest.raises(ValueError, match="settlement_not_transportable"):
            serialize_timeout_context(bound, expected_run_id=state.run_id)
    elif mode == "async":
        with pytest.raises(NodeTimeoutError, match="settlement_not_transportable"):
            asyncio.run(_execute_with_timeout_process_async(node, bound, state, timeout_s=1.0))
    else:
        with pytest.raises(NodeTimeoutError, match="settlement_not_transportable"):
            _execute_with_timeout_process(node, bound, state, timeout_s=1.0)
    node.execute.assert_not_called()
    assert issued.settlement_attempted is False


@pytest.mark.parametrize("route", ["timed", "unbounded_cancel"])
def test_late_async_settlement_is_revoked_after_timeout_or_cancellation(invocation, route):
    """An actual issued view cannot outlive the dispatched async attempt."""
    import asyncio
    from dataclasses import replace

    from polisyos.scientist.orchestration.engine.context import _EngineInvocationBinding
    from polisyos.scientist.orchestration.engine.errors import NodeTimeoutError
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
    from polisyos.scientist.orchestration.engine.retry import (
        RetryPolicy,
        _AttemptWriteDeniedError,
        _execute_with_timeout_async,
        execute_with_retry_async,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    issued = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    bound = replace(
        ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id="run-issued", attempt_id=attempt_id, basis_ref=basis, settlement_view=issued
        ),
    )
    failures: list[Exception] = []
    writes: list[str] = []

    async def scenario() -> None:
        entered, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()

        class LateNode:
            async def execute_async(self, node_ctx, node_state):
                entered.set()
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    # A producer may suppress cancellation; its old authority must still expire.
                    await release.wait()
                try:
                    node_ctx._engine_invocation.settlement_view.settle_spend(
                        Decimal("2"), payload_ref=payload, provider="local-fixture"
                    )
                    writes.append("settled")
                except Exception as exc:
                    failures.append(exc)
                finally:
                    finished.set()
                return NodeOutcome(status="ok", state=node_state)

        node = LateNode()
        state = ExperimentState(run_id="run-issued")
        if route == "timed":
            dispatched = asyncio.create_task(
                _execute_with_timeout_async(node, bound, state, timeout_s=0.1)
            )
            await asyncio.wait_for(entered.wait(), timeout=2)
            with pytest.raises(NodeTimeoutError):
                await dispatched
            release.set()
        else:
            dispatched = asyncio.create_task(
                execute_with_retry_async(
                    node,
                    bound,
                    state,
                    retry_policy=RetryPolicy(max_retries=0),
                    timeout_s=None,
                    alias="effect",
                )
            )
            await asyncio.wait_for(entered.wait(), timeout=2)
            dispatched.cancel()
            await asyncio.sleep(0)
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await dispatched
        await asyncio.wait_for(finished.wait(), timeout=2)

    asyncio.run(scenario())
    assert writes == []
    assert len(failures) == 1 and isinstance(failures[0], _AttemptWriteDeniedError)
    assert ledger.snapshot().state.spent["run"] == Decimal("5")


@pytest.mark.parametrize("route", ["timed", "unbounded"])
def test_live_async_authority_allows_charge_then_revokes_retained_view(invocation, route):
    """A real live attempt can settle once; its retained capability then expires."""
    import asyncio
    from dataclasses import replace

    from polisyos.scientist.orchestration.engine.context import _EngineInvocationBinding
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
    from polisyos.scientist.orchestration.engine.retry import (
        RetryPolicy,
        _AttemptWriteDeniedError,
        _execute_with_timeout_async,
        execute_with_retry_async,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    issued = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    bound = replace(
        ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id="run-issued", attempt_id=attempt_id, basis_ref=basis, settlement_view=issued
        ),
    )
    retained: list[Any] = []

    class ChargeNode:
        async def execute_async(self, node_ctx, node_state):
            view = node_ctx._engine_invocation.settlement_view
            retained.append(view)
            assert view.spent == Decimal("5")
            receipt_ref = view.settle_spend(
                Decimal("2"), payload_ref=payload, provider="local-fixture"
            )
            assert view.spent == Decimal("7")
            return NodeOutcome(status="ok", state=node_state, artifacts=[payload, receipt_ref])

    async def scenario() -> NodeOutcome:
        state = ExperimentState(run_id="run-issued")
        if route == "timed":
            return await _execute_with_timeout_async(ChargeNode(), bound, state, timeout_s=2)
        return await execute_with_retry_async(
            ChargeNode(),
            bound,
            state,
            retry_policy=RetryPolicy(max_retries=0),
            timeout_s=None,
            alias="effect",
        )

    result = asyncio.run(scenario())
    assert result.status == "ok" and len(result.artifacts) == 2
    assert issued.settlement_attempted is True
    receipt = _verify_invocation_settlement_receipt(
        ctx.store,
        result.artifacts[1],
        result.artifacts,
        run_id="run-issued",
        alias="effect",
        attempt_id=attempt_id,
        basis_ref=basis,
        snapshot=ledger.snapshot(),
    )
    assert ledger.resolve_spend(receipt.event_id) == receipt
    assert len(retained) == 1
    with pytest.raises(_AttemptWriteDeniedError):
        _ = retained[0].spent
    with pytest.raises(_AttemptWriteDeniedError):
        retained[0].settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")
    assert ledger.snapshot().state.spent["run"] == Decimal("7")


@pytest.mark.parametrize("finalization", ["terminal", "cancel"])
def test_completed_async_failure_preserves_real_settled_spend(invocation, finalization):
    """Failure or interrupted finalization must not erase a known actual charge."""
    import asyncio
    from dataclasses import replace

    from polisyos.scientist.orchestration.engine.context import _EngineInvocationBinding
    from polisyos.scientist.orchestration.engine.errors import RetryExhaustedError
    from polisyos.scientist.orchestration.engine.retry import RetryPolicy, execute_with_retry_async
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    issued = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    bound = replace(
        ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id="run-issued", attempt_id=attempt_id, basis_ref=basis, settlement_view=issued
        ),
    )
    state = ExperimentState(
        run_id="run-issued",
        budgets={"run_spent_usd": Decimal("5")},
        params={"stable": "original"},
    )
    receipt_refs: list[ArtifactRef] = []
    finalizations: list[str] = []

    class ChargedFailure:
        async def execute_async(self, node_ctx, attempt_state):
            view = node_ctx._engine_invocation.settlement_view
            receipt_refs.append(
                view.settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")
            )
            attempt_state.budgets["run_spent_usd"] = view.spent
            attempt_state.params["ordinary_failed_write"] = "must-not-leak"
            raise RuntimeError("producer failed after acknowledged charge")

    async def started(number, _state):
        assert number == 1
        return attempt_id

    def bind(selected_attempt):
        assert selected_attempt == attempt_id
        return bound

    async def completed(selected_attempt, outcome):
        assert selected_attempt == attempt_id and outcome is None
        finalizations.append("called")
        if finalization == "cancel":
            raise asyncio.CancelledError()

    async def scenario() -> None:
        await execute_with_retry_async(
            ChargedFailure(),
            bound,
            state,
            retry_policy=RetryPolicy(max_retries=1, retry_on=[]),
            timeout_s=None,
            alias="effect",
            attempt_started=started,
            attempt_completed=completed,
            attempt_context=bind,
        )

    expected_error = asyncio.CancelledError if finalization == "cancel" else RetryExhaustedError
    with pytest.raises(expected_error):
        asyncio.run(scenario())
    assert finalizations == ["called"]
    assert state.budgets["run_spent_usd"] == Decimal("7")
    assert state.params == {"stable": "original"}
    assert len(receipt_refs) == 1
    receipt = _verify_invocation_settlement_receipt(
        ctx.store,
        receipt_refs[0],
        [payload, receipt_refs[0]],
        run_id="run-issued",
        alias="effect",
        attempt_id=attempt_id,
        basis_ref=basis,
        snapshot=ledger.snapshot(),
    )
    assert receipt.amount == Decimal("2")
    assert ledger.resolve_spend(receipt.event_id) == receipt
    assert ledger.snapshot().state.spent["run"] == Decimal("7")


@pytest.mark.parametrize("execution", ["sync", "async"])
@pytest.mark.parametrize("retries", [0, 1])
def test_confirmed_charge_survives_interrupted_attempt_completion(
    invocation, execution: str, retries: int
) -> None:
    """An acknowledged charge is neither lost nor counted twice at finalization."""
    import asyncio
    from dataclasses import replace

    from polisyos.scientist.orchestration.engine.context import _EngineInvocationBinding
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
    from polisyos.scientist.orchestration.engine.retry import (
        RetryPolicy,
        execute_with_retry_async,
        execute_with_retry_sync,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    class CompletionInterrupted(BaseException):
        pass

    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    view = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    bound = replace(
        ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id="run-issued", attempt_id=attempt_id, basis_ref=basis, settlement_view=view
        ),
    )
    state = ExperimentState(run_id="run-issued", budgets={"run_spent_usd": Decimal("5")})
    interrupted = CompletionInterrupted("controlled completion interruption")
    dispatches: list[int] = []
    receipts: list[ArtifactRef] = []
    completions: list[str | None] = []

    class ChargeNode:
        def execute(self, node_ctx, attempt_state):
            dispatches.append(1)
            issued = node_ctx._engine_invocation.settlement_view
            receipt = issued.settle_spend(
                Decimal("2"), payload_ref=payload, provider="local-fixture"
            )
            receipts.append(receipt)
            # The failed completion must project the verified owner value, not
            # trust an unrelated mutable producer-state assertion.
            attempt_state.budgets["run_spent_usd"] = Decimal("999")
            outcome_state = attempt_state.model_copy(deep=True)
            outcome_state.budgets["run_spent_usd"] = issued.spent
            return NodeOutcome(status="ok", state=outcome_state, artifacts=[payload, receipt])

        async def execute_async(self, node_ctx, attempt_state):
            return self.execute(node_ctx, attempt_state)

    def started(number, _state):
        assert number == 1
        return attempt_id

    def completed(selected_attempt, outcome):
        assert selected_attempt == attempt_id
        completions.append(None if outcome is None else outcome.status)
        if outcome is not None:
            raise interrupted

    def bind(selected_attempt):
        assert selected_attempt == attempt_id
        return bound

    async def started_async(number, current_state):
        return started(number, current_state)

    async def completed_async(selected_attempt, outcome):
        completed(selected_attempt, outcome)

    policy = RetryPolicy(max_retries=retries, backoff_base_s=0.1, jitter="none")

    def invoke():
        if execution == "sync":
            return execute_with_retry_sync(
                ChargeNode(),
                bound,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="effect",
                attempt_started=started,
                attempt_completed=completed,
                attempt_context=bind,
            )
        return asyncio.run(
            execute_with_retry_async(
                ChargeNode(),
                bound,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="effect",
                attempt_started=started_async,
                attempt_completed=completed_async,
                attempt_context=bind,
            )
        )

    with pytest.raises(CompletionInterrupted) as caught:
        invoke()
    assert caught.value is interrupted
    assert dispatches == [1] and len(receipts) == 1
    assert completions and completions[0] == "ok"
    assert all(item is None for item in completions[1:])
    receipt = _verify_invocation_settlement_receipt(
        ctx.store,
        receipts[0],
        [payload, receipts[0]],
        run_id="run-issued",
        alias="effect",
        attempt_id=attempt_id,
        basis_ref=basis,
        snapshot=ledger.snapshot(),
    )
    assert receipt.amount == Decimal("2")
    assert ledger.snapshot().state.spent["run"] == Decimal("7")
    assert state.budgets["run_spent_usd"] == Decimal("7")


@pytest.mark.parametrize("execution", ["sync", "async"])
@pytest.mark.parametrize("retries", [0, 1])
@pytest.mark.parametrize("primary_kind", ["producer_base", "child_unknown", "cancel"])
@pytest.mark.parametrize("secondary_kind", ["owner_lost", "base"])
def test_producer_interruption_remains_primary_when_completion_fails(
    invocation, execution: str, retries: int, primary_kind: str, secondary_kind: str
) -> None:
    """A later completion interruption cannot erase the producer's original outcome."""
    import asyncio
    from dataclasses import replace

    from polisyos.common.job_execution_interrupt import JobExecutionInterrupted
    from polisyos.core.run.context import ChildOutcomeUnknownError
    from polisyos.scientist.orchestration.engine.context import _EngineInvocationBinding
    from polisyos.scientist.orchestration.engine.retry import (
        RetryPolicy,
        execute_with_retry_async,
        execute_with_retry_sync,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    class ProducerInterrupted(BaseException):
        pass

    class CompletionInterrupted(BaseException):
        pass

    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    view = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    bound = replace(
        ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id="run-issued", attempt_id=attempt_id, basis_ref=basis, settlement_view=view
        ),
    )
    state = ExperimentState(run_id="run-issued", budgets={"run_spent_usd": Decimal("5")})
    assert ctx.run.trace_path is not None
    primary = {
        "producer_base": ProducerInterrupted("controlled original producer interruption"),
        "child_unknown": ChildOutcomeUnknownError(
            "controlled unknown child outcome",
            run_id="fixture-child",
            run_dir=ctx.run.trace_path.parent / "fixture-child",
        ),
        "cancel": asyncio.CancelledError("controlled producer cancellation"),
    }[primary_kind]
    cleanup = (
        JobExecutionInterrupted("controlled owner loss during completion")
        if secondary_kind == "owner_lost"
        else CompletionInterrupted("controlled completion interruption")
    )
    dispatches: list[int] = []
    receipts: list[ArtifactRef] = []

    class InterruptedNode:
        def execute(self, node_ctx, _state):
            dispatches.append(1)
            receipts.append(
                node_ctx._engine_invocation.settlement_view.settle_spend(
                    Decimal("2"), payload_ref=payload, provider="local-fixture"
                )
            )
            raise primary

        async def execute_async(self, node_ctx, attempt_state):
            return self.execute(node_ctx, attempt_state)

    def started(number, _state):
        assert number == 1
        return attempt_id

    def completed(selected_attempt, outcome):
        assert selected_attempt == attempt_id and outcome is None
        raise cleanup

    def bind(selected_attempt):
        assert selected_attempt == attempt_id
        return bound

    async def started_async(number, current_state):
        return started(number, current_state)

    async def completed_async(selected_attempt, outcome):
        completed(selected_attempt, outcome)

    policy = RetryPolicy(max_retries=retries, backoff_base_s=0.1, jitter="none")

    async def invoke_async():
        try:
            await execute_with_retry_async(
                InterruptedNode(),
                bound,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="effect",
                attempt_started=started_async,
                attempt_completed=completed_async,
                attempt_context=bind,
            )
        except BaseException as error:
            return error
        raise AssertionError("interrupted producer unexpectedly returned")

    if execution == "sync":
        with pytest.raises(type(primary)) as caught:
            execute_with_retry_sync(
                InterruptedNode(),
                bound,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="effect",
                attempt_started=started,
                attempt_completed=completed,
                attempt_context=bind,
            )
        error = caught.value
    else:
        error = asyncio.run(invoke_async())
        assert isinstance(error, type(primary))
    # asyncio may materialize a fresh cancellation at the task boundary.
    if primary_kind != "cancel" or execution == "sync":
        assert error is primary
    assert error.__cause__ is cleanup
    assert dispatches == [1] and len(receipts) == 1
    receipt = _verify_invocation_settlement_receipt(
        ctx.store,
        receipts[0],
        [payload, receipts[0]],
        run_id="run-issued",
        alias="effect",
        attempt_id=attempt_id,
        basis_ref=basis,
        snapshot=ledger.snapshot(),
    )
    assert receipt.amount == Decimal("2")
    assert ledger.snapshot().state.spent["run"] == Decimal("7")
    assert state.budgets["run_spent_usd"] == Decimal("7")


@pytest.mark.parametrize("execution", ["sync", "async"])
@pytest.mark.parametrize("damage", ["missing", "corrupt"])
@pytest.mark.parametrize("failure", ["returned", "raised"])
def test_unverified_receipt_never_projects_failed_attempt_spend(
    invocation, execution: str, damage: str, failure: str
) -> None:
    """Real corrupt CAS evidence cannot become retry, trace or state authority."""
    _assert_strict_failure_does_not_project_unverified_spend(
        invocation, execution=execution, damage=damage, failure=failure
    )


@pytest.mark.parametrize("execution", ["sync", "async"])
@pytest.mark.parametrize("damage", ["decrease", "delete"])
@pytest.mark.parametrize("failure", ["returned", "raised"])
@pytest.mark.parametrize("retry_enabled", [True, False], ids=["retry", "terminal"])
def test_strict_view_cannot_mutate_non_run_spend(
    invocation, execution: str, damage: str, failure: str, retry_enabled: bool
) -> None:
    """A run-scoped receipt never authorizes another budget's removal or decrease."""
    _assert_strict_failure_does_not_project_unverified_spend(
        invocation,
        execution=execution,
        damage=damage,
        failure=failure,
        retry_enabled=retry_enabled,
    )


def _assert_strict_failure_does_not_project_unverified_spend(
    invocation, *, execution: str, damage: str, failure: str, retry_enabled: bool = True
) -> None:
    import asyncio
    from dataclasses import replace

    from polisyos.core.trace.record import TraceRecord
    from polisyos.scientist.orchestration.engine.context import _EngineInvocationBinding
    from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome
    from polisyos.scientist.orchestration.engine.retry import (
        RetryPolicy,
        execute_with_retry_async,
        execute_with_retry_sync,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    issued = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    bound = replace(
        ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id="run-issued", attempt_id=attempt_id, basis_ref=basis, settlement_view=issued
        ),
    )
    other_budget = damage in {"decrease", "delete"}
    initial_budgets = {"run_spent_usd": Decimal("5")}
    if other_budget:
        initial_budgets["other_spent_usd"] = Decimal("3")
    state = ExperimentState(
        run_id="run-issued",
        budgets=initial_budgets,
        params={"stable": "original"},
    )
    dispatches: list[int] = []
    attempt_starts: list[int] = []
    finalizations: list[tuple[str, object]] = []
    damaged: list[ArtifactRef] = []

    class InvalidReceiptNode:
        def execute(self, node_ctx, attempt_state):
            dispatches.append(1)
            receipt = node_ctx._engine_invocation.settlement_view.settle_spend(
                Decimal("2"), payload_ref=payload, provider="local-fixture"
            )
            damaged.append(receipt)
            if other_budget:
                if damage == "delete":
                    del attempt_state.budgets["other_spent_usd"]
                else:
                    attempt_state.budgets["other_spent_usd"] = Decimal("1")
                assert ctx.store.verify(receipt).ok
                attempt_state.budgets["run_spent_usd"] = Decimal("7")
            else:
                blob, _manifest = ctx.store._paths(receipt.artifact_id)
                if damage == "missing":
                    blob.replace(blob.with_name(blob.name + ".held"))
                else:
                    blob.write_bytes(b"deliberately corrupt temporary fixture receipt")
                assert not ctx.store.verify(receipt).ok
                attempt_state.budgets["run_spent_usd"] = Decimal("999")
            attempt_state.params["failed_body"] = "must-not-publish"
            if failure == "raised":
                raise RuntimeError("producer raised after invalid receipt")
            return NodeOutcome(
                status="fail",
                state=attempt_state,
                artifacts=[payload, receipt],
                error=NodeError(code="node.exception", message="producer returned failure"),
            )

        async def execute_async(self, node_ctx, attempt_state):
            return self.execute(node_ctx, attempt_state)

    def started(number, _state):
        attempt_starts.append(number)
        assert number == 1
        return attempt_id

    def completed(selected_attempt, outcome):
        finalizations.append((selected_attempt, outcome))

    def bind(selected_attempt):
        assert selected_attempt == attempt_id
        return bound

    async def started_async(number, current_state):
        return started(number, current_state)

    async def completed_async(selected_attempt, outcome):
        completed(selected_attempt, outcome)

    policy = RetryPolicy(
        max_retries=1,
        retry_on=["node.exception"] if retry_enabled else [],
        backoff_base_s=0.1,
        jitter="none",
    )

    def invoke():
        if execution == "sync":
            return execute_with_retry_sync(
                InvalidReceiptNode(),
                bound,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="effect",
                attempt_started=started,
                attempt_completed=completed,
                attempt_context=bind,
            )
        return asyncio.run(
            execute_with_retry_async(
                InvalidReceiptNode(),
                bound,
                state,
                retry_policy=policy,
                timeout_s=None,
                alias="effect",
                attempt_started=started_async,
                attempt_completed=completed_async,
                attempt_context=bind,
            )
        )

    with pytest.raises(Exception) as caught:
        invoke()

    assert attempt_starts == [1], f"unexpected attempt-start admissions: {attempt_starts}"
    chain: list[BaseException] = []
    error: BaseException | None = caught.value
    while error is not None and error not in chain:
        chain.append(error)
        error = error.__cause__ or error.__context__
    expected_error = (
        "budget_invocation_non_run_spend_not_established"
        if other_budget
        else "budget_invocation_receipt_profile_invalid"
    )
    assert any(expected_error in str(error) for error in chain), [
        (type(error).__name__, str(error)) for error in chain
    ]
    assert dispatches == [1] and len(damaged) == 1
    assert finalizations == [(attempt_id, None)]
    assert state.budgets["run_spent_usd"] == (Decimal("7") if other_budget else Decimal("5"))
    if other_budget:
        assert state.budgets["other_spent_usd"] == Decimal("3")
    assert state.params == {"stable": "original"}
    # The ledger saw the write; only an intact selected proof can establish it.
    assert ledger.snapshot().state.spent["run"] == Decimal("7")
    assert ctx.run.trace_path is not None
    trace = [
        TraceRecord.model_validate_json(line)
        for line in ctx.run.trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    attempt_events = [event for event in trace if event.event in {"NODE_RETRY", "NODE_DEAD_LETTER"}]
    assert not any(event.event == "NODE_RETRY" for event in attempt_events)
    if other_budget:
        assert all(event.metrics.get("failed_cost_usd", 2) == 2 for event in attempt_events)
    else:
        assert not any("failed_cost_usd" in event.metrics for event in attempt_events)


@pytest.mark.parametrize("max_retries", [0, 1])
def test_unbounded_sync_settlement_view_expires_after_return(invocation, max_retries):
    """Fast and retry-enabled sync dispatch use actual attempt-bound authority."""
    from dataclasses import replace

    from polisyos.scientist.orchestration.engine.context import _EngineInvocationBinding
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
    from polisyos.scientist.orchestration.engine.retry import (
        RetryPolicy,
        _AttemptWriteDeniedError,
        execute_with_retry_sync,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    issued = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    bound = replace(
        ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id="run-issued", attempt_id=attempt_id, basis_ref=basis, settlement_view=issued
        ),
    )
    retained: list[Any] = []

    class ChargeNode:
        def execute(self, node_ctx, node_state):
            view = node_ctx._engine_invocation.settlement_view
            retained.append(view)
            assert view.spent == Decimal("5")
            receipt_ref = view.settle_spend(
                Decimal("2"), payload_ref=payload, provider="local-fixture"
            )
            assert view.spent == Decimal("7")
            return NodeOutcome(status="ok", state=node_state, artifacts=[payload, receipt_ref])

    result = execute_with_retry_sync(
        ChargeNode(),
        bound,
        ExperimentState(run_id="run-issued"),
        retry_policy=RetryPolicy(max_retries=max_retries),
        timeout_s=None,
        alias="effect",
    )
    assert result.status == "ok" and len(result.artifacts) == 2
    receipt = _verify_invocation_settlement_receipt(
        ctx.store,
        result.artifacts[1],
        result.artifacts,
        run_id="run-issued",
        alias="effect",
        attempt_id=attempt_id,
        basis_ref=basis,
        snapshot=ledger.snapshot(),
    )
    assert ledger.resolve_spend(receipt.event_id) == receipt
    assert len(retained) == 1
    with pytest.raises(_AttemptWriteDeniedError):
        _ = retained[0].spent
    with pytest.raises(_AttemptWriteDeniedError):
        retained[0].settle_spend(Decimal("2"), payload_ref=payload, provider="local-fixture")
    assert ledger.snapshot().state.spent["run"] == Decimal("7")


@pytest.mark.parametrize(
    "control",
    [
        "intact",
        "remove_strict_merge_guard",
        "terminal_incremental",
        "terminal_cumulative",
        "terminal_missing_receipt",
        "terminal_corrupt_receipt",
    ],
)
def test_actual_retry_cumulative_view_does_not_count_failed_charge_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, control: str
) -> None:
    """A fresh ledger total must not be incremented again by retry bookkeeping."""
    import asyncio
    import sqlite3

    from polisyos.core.run import read_runtime_invocation_attempts
    from polisyos.scientist.orchestration.engine import retry as retry_module
    from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
    from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.retry import RetryPolicy
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
    from tests._helpers.dur02_effects import _CostedRetryEffectNode

    if control == "remove_strict_merge_guard":

        def restore_unconditional_merge(outcome, failed_spend, *, strict):
            retry_module._merge_spend(outcome.state, failed_spend)

        monkeypatch.setattr(
            retry_module, "_merge_failed_spend_for_outcome", restore_unconditional_merge
        )

    class CumulativeCostedNode(_CostedRetryEffectNode):
        def execute(self, node_ctx, state):
            outcome = super().execute(node_ctx, state)
            if outcome.status == "ok":
                if control in {"terminal_missing_receipt", "terminal_corrupt_receipt"}:
                    receipt = next(
                        ref
                        for ref in outcome.artifacts
                        if ref.kind == "scientist.budget_spend_receipt"
                    )
                    blob, _manifest = store._paths(receipt.artifact_id)
                    if control == "terminal_missing_receipt":
                        blob.replace(blob.with_name(blob.name + ".held"))
                    else:
                        blob.write_bytes(b"deliberately corrupt temporary fixture receipt")
                    assert not store.verify(receipt).ok
                    return outcome
                if control != "terminal_incremental":
                    outcome.state.budgets["run_spent_usd"] = (
                        node_ctx._engine_invocation.settlement_view.spent
                    )
                if control.startswith("terminal_"):
                    return NodeOutcome(
                        status="fail",
                        state=outcome.state,
                        artifacts=outcome.artifacts,
                        error=NodeError(
                            code="node.terminal_fixture", message="known final failure"
                        ),
                    )
            return outcome

    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store, return_selected_profile=True)
    run_id, run_dir = "run-cumulative-retry", tmp_path / "run"
    run = RunContext.start(
        store=store, registry_bundle=bundle.bundle_ref, run_id=run_id, run_dir=run_dir
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    ledger_path, database = tmp_path / "budget.json", tmp_path / "effects.sqlite3"
    middleware = BudgetMiddleware(
        BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))},
            spent={"run": Decimal("5")},
        ),
        ledger=FileBudgetLedger(ledger_path),
        invocation_settlement_profile="single_owner_local_v1",
    )
    node = CumulativeCostedNode(database, mode="retry")
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="cumulative_costed_retry",
        nodes=[
            NodeInvocation(
                alias="costed",
                node_id=node.spec.metadata.component_id,
                retry=RetryPolicy(
                    max_retries=1, jitter="none", backoff_base_s=0.1, retry_on=["node.exception"]
                ),
            )
        ],
    )
    try:
        result = asyncio.run(
            AsyncWorkflowExecutor(
                ctx,
                registry,
                max_parallelism=1,
                budget_middleware=middleware,
                strict_budget_attempts=True,
            ).execute(
                workflow, ExperimentState(run_id=run_id, budgets={"run_spent_usd": Decimal("5")})
            )
        )
        snapshot = FileBudgetLedger(ledger_path).snapshot()
        history = read_runtime_invocation_attempts(store, run_dir / "trace.jsonl", run_id=run_id)
        with sqlite3.connect(database) as connection:
            attempts = connection.execute(
                "SELECT attempt_number FROM costed_effects ORDER BY rowid"
            ).fetchall()
        assert result.report.status == ("fail" if control.startswith("terminal_") else "ok")
        assert attempts == [(1,), (2,)]
        receipt_unavailable = control in {
            "terminal_missing_receipt",
            "terminal_corrupt_receipt",
        }
        expected_statuses = [
            "fail",
            "unknown"
            if receipt_unavailable
            else "fail"
            if control.startswith("terminal_")
            else "ok",
        ]
        assert [item.outcome.status for item in history] == expected_statuses
        assert len(snapshot.spend_receipts) == 2
        assert snapshot.state.spent["run"] == Decimal("8")
        expected = (
            Decimal("10")
            if control == "remove_strict_merge_guard"
            else Decimal("7")
            if receipt_unavailable
            else Decimal("8")
        )
        assert result.state.budgets["run_spent_usd"] == expected
        assert "failed_body" not in result.state.params
    finally:
        run.suspend_for_resume()


@pytest.mark.parametrize(
    "projection", ["incremental", "cumulative", "raised_incremental", "raised_cumulative"]
)
def test_sync_retry_two_real_attempts_preserve_exact_settled_spend(
    tmp_path: Path, projection: str
) -> None:
    """The direct sync retry API binds each physical attempt to the real owner."""
    import sqlite3
    from dataclasses import replace

    from polisyos.core.run import read_runtime_invocation_attempts
    from polisyos.scientist.orchestration.engine.context import _EngineInvocationBinding
    from polisyos.scientist.orchestration.engine.errors import RetryExhaustedError
    from polisyos.scientist.orchestration.engine.retry import RetryPolicy, execute_with_retry_sync
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from tests._helpers.dur02_effects import _CostedRetryEffectNode

    produced_artifacts: list[list[ArtifactRef]] = []

    class ProjectingNode(_CostedRetryEffectNode):
        def execute(self, node_ctx, state):
            outcome = super().execute(node_ctx, state)
            produced_artifacts.append(outcome.artifacts)
            if outcome.status == "ok":
                if projection.endswith("cumulative"):
                    outcome.state.budgets["run_spent_usd"] = (
                        node_ctx._engine_invocation.settlement_view.spent
                    )
                if projection.startswith("raised_"):
                    state.budgets["run_spent_usd"] = outcome.state.budgets["run_spent_usd"]
                    state.params["failed_body"] = "must-not-publish"
                    raise RuntimeError("second attempt failed after confirmed settlement")
            return outcome

    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store, return_selected_profile=True)
    run_id, run_dir = "run-sync-retry", tmp_path / "run"
    run = RunContext.start(
        store=store, registry_bundle=bundle.bundle_ref, run_id=run_id, run_dir=run_dir
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    ledger_path, database = tmp_path / "budget.json", tmp_path / "effects.sqlite3"
    middleware = BudgetMiddleware(
        BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))},
            spent={"run": Decimal("5")},
        ),
        ledger=FileBudgetLedger(ledger_path),
        invocation_settlement_profile="single_owner_local_v1",
    )
    node = ProjectingNode(database, mode="retry")
    workflow_ref = store.put_json(
        {"workflow": "sync-retry-fixture"},
        ArtifactWriteOptions(kind="fixture.workflow", media_type="application/json"),
        return_selected_profile=True,
    )
    bases: dict[str, tuple[int, ArtifactRef]] = {}

    def persist_state(state):
        return store.put_json(
            state.model_dump(mode="json"),
            ArtifactWriteOptions(kind="fixture.attempt_state", media_type="application/json"),
            return_selected_profile=True,
        )

    def started(number, state):
        owner, resource, (revision, digest), _snapshot = middleware._continuation_state()
        attempt_id = str(uuid4())
        basis = run._record_runtime_invocation_started(
            attempt_id=attempt_id,
            attempt_number=number,
            workflow_spec_ref=workflow_ref,
            node_alias="costed",
            component_id=str(node.spec.metadata.component_id),
            input_state_ref=persist_state(state),
            execution_budget_contract="admitted_workflow_budget_v1",
            budget_middleware_active=True,
            budget_owner_identity=owner,
            budget_resource_identity=resource,
            budget_start_revision=revision,
            budget_start_snapshot_sha256=digest,
            invocation_settlement_profile=middleware.invocation_settlement_profile,
        )
        bases[attempt_id] = number, basis
        return attempt_id

    def bind(attempt_id):
        _number, basis = bases[attempt_id]
        view = _issue_invocation_settlement_view(
            middleware, ctx, alias="costed", attempt_id=attempt_id, basis_ref=basis
        )
        return replace(
            ctx,
            _engine_invocation=_EngineInvocationBinding(
                run_id=run_id, attempt_id=attempt_id, basis_ref=basis, settlement_view=view
            ),
        )

    def completed(attempt_id, outcome):
        number, basis = bases[attempt_id]
        run._record_runtime_invocation_completed(
            attempt_id=attempt_id,
            attempt_number=number,
            basis_ref=basis,
            status=outcome.status if outcome is not None else "unknown",
            outcome_state_ref=persist_state(outcome.state) if outcome is not None else None,
            output_refs=outcome.artifacts if outcome is not None else [],
        )

    try:
        state = ExperimentState(run_id=run_id, budgets={"run_spent_usd": Decimal("5")})

        def invoke():
            return execute_with_retry_sync(
                node,
                ctx,
                state,
                retry_policy=RetryPolicy(
                    max_retries=1, jitter="none", backoff_base_s=0.1, retry_on=["node.exception"]
                ),
                timeout_s=None,
                alias="costed",
                attempt_started=started,
                attempt_completed=completed,
                attempt_context=bind,
            )

        if projection.startswith("raised_"):
            with pytest.raises(RetryExhaustedError):
                invoke()
            result_state = state
        else:
            result = invoke()
            assert result.status == "ok"
            result_state = result.state
        snapshot = FileBudgetLedger(ledger_path).snapshot()
        history = read_runtime_invocation_attempts(store, run_dir / "trace.jsonl", run_id=run_id)
        with sqlite3.connect(database) as connection:
            attempts = connection.execute(
                "SELECT attempt_number FROM costed_effects ORDER BY rowid"
            ).fetchall()
        assert attempts == [(1,), (2,)]
        expected_statuses = ["fail", "unknown" if projection.startswith("raised_") else "ok"]
        assert [item.outcome.status for item in history] == expected_statuses
        assert len(snapshot.spend_receipts) == 2
        for attempt, artifacts in zip(history, produced_artifacts, strict=True):
            receipt_refs = [
                ref for ref in artifacts if ref.kind == "scientist.budget_spend_receipt"
            ]
            assert len(receipt_refs) == 1
            _verify_invocation_settlement_receipt(
                store,
                receipt_refs[0],
                artifacts,
                run_id=run_id,
                alias="costed",
                attempt_id=attempt.basis.attempt_id,
                basis_ref=attempt.basis_ref,
                snapshot=snapshot,
            )
        assert snapshot.state.spent["run"] == result_state.budgets["run_spent_usd"] == Decimal("8")
        assert "failed_body" not in result_state.params
    finally:
        run.suspend_for_resume()


@pytest.mark.parametrize("control", ["intact", "remove_cache_budget_guard"])
def test_strict_cache_replay_cannot_restore_an_obsolete_run_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, control: str
) -> None:
    """Real A→B→cached A must not roll the current ledger total back to A's old value."""
    import asyncio
    import sqlite3

    from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
    from polisyos.core.trace.record import TraceRecord
    from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

    if control == "remove_cache_budget_guard":
        execute_node = AsyncWorkflowExecutor._execute_node

        async def without_cache_budget_guard(executor, alias, *args, **kwargs):
            if alias != "again":
                return await execute_node(executor, alias, *args, **kwargs)
            executor._strict_budget_attempts = False
            try:
                return await execute_node(executor, alias, *args, **kwargs)
            finally:
                executor._strict_budget_attempts = True

        monkeypatch.setattr(AsyncWorkflowExecutor, "_execute_node", without_cache_budget_guard)

    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store, return_selected_profile=True)
    run_dir, run_id = tmp_path / "run", "strict-cache-budget"
    run = RunContext.start(
        store=store, registry_bundle=bundle.bundle_ref, run_id=run_id, run_dir=run_dir
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    ledger = FileBudgetLedger(tmp_path / "budget.json")
    middleware = BudgetMiddleware(
        BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))},
            spent={"run": Decimal("5")},
        ),
        ledger=ledger,
        invocation_settlement_profile="single_owner_local_v1",
    )
    database = tmp_path / "effects.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE physical_effects (producer TEXT NOT NULL)")

    class CostedNode:
        def __init__(self, name: str, amount: Decimal) -> None:
            self.name, self.amount = name, amount
            self.spec = NodeSpec(
                metadata=ComponentMetadata(
                    component_id=ComponentId.parse(f"scientist.node_cache_{name}@1.0.0"),
                    kind=ComponentKind.SCIENTIST_NODE,
                    abi_targets={"world_abi": "1.x"},
                    display_name=f"Cache budget fixture {name}",
                    capabilities=Capability.SCIENTIST_NODE,
                ),
                # The value comes from the engine-owned view, not from state.
                state_reads=["run_id"],
                state_writes=["budgets.run_spent_usd"],
            )

        def execute(self, node_ctx, state):
            with sqlite3.connect(database) as connection:
                connection.execute("INSERT INTO physical_effects VALUES (?)", (self.name,))
            payload = node_ctx.store.put_json(
                {"producer": self.name},
                ArtifactWriteOptions(
                    kind="fixture.cache_budget_effect", media_type="application/json"
                ),
                return_selected_profile=True,
            )
            view = node_ctx._engine_invocation.settlement_view
            receipt = view.settle_spend(self.amount, payload_ref=payload, provider="fixture")
            state.budgets["run_spent_usd"] = view.spent
            return NodeOutcome(status="ok", state=state, artifacts=[payload, receipt])

        async def execute_async(self, node_ctx, state):
            return self.execute(node_ctx, state)

    first, middle = CostedNode("first", Decimal("2")), CostedNode("middle", Decimal("1"))
    registry = NodeRegistry()
    registry.register(first)
    registry.register(middle)
    workflow = WorkflowSpec(
        workflow_id="strict_cache_budget",
        nodes=[
            NodeInvocation(alias="first", node_id=first.spec.metadata.component_id),
            NodeInvocation(
                alias="middle", node_id=middle.spec.metadata.component_id, depends_on=["first"]
            ),
            NodeInvocation(
                alias="again", node_id=first.spec.metadata.component_id, depends_on=["middle"]
            ),
        ],
    )
    try:
        result = asyncio.run(
            AsyncWorkflowExecutor(
                ctx,
                registry,
                max_parallelism=1,
                budget_middleware=middleware,
                strict_budget_attempts=True,
            ).execute(
                workflow, ExperimentState(run_id=run_id, budgets={"run_spent_usd": Decimal("5")})
            )
        )
        with sqlite3.connect(database) as connection:
            effects = connection.execute(
                "SELECT producer FROM physical_effects ORDER BY rowid"
            ).fetchall()
        trace = [
            TraceRecord.model_validate_json(line)
            for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert effects == [("first",), ("middle",)]
        snapshot = ledger.snapshot()
        assert snapshot.state.spent["run"] == Decimal("8")
        assert sorted(receipt.amount for receipt in snapshot.spend_receipts.values()) == [
            Decimal("1"),
            Decimal("2"),
        ]
        assert result.report.status == "ok"
        assert any(
            event.event == "NODE_CACHE_HIT" and event.phase == "scientist.node.again"
            for event in trace
        )
        if control == "remove_cache_budget_guard":
            # Deliberately removing the consumer guard recovers the old wrong value.
            assert result.state.budgets["run_spent_usd"] == Decimal("7")
        else:
            assert result.state.budgets["run_spent_usd"] == Decimal("8")
    finally:
        run.suspend_for_resume()


@pytest.mark.parametrize("use_breaker", [False, True], ids=["fast", "breaker"])
@pytest.mark.parametrize("corruption", ["none", "first", "second"])
def test_typed_failure_completion_uses_verified_cost_and_clean_baseline(
    invocation, monkeypatch: pytest.MonkeyPatch, use_breaker: bool, corruption: str
) -> None:
    """An actual issued receipt cannot promote failed writes or a corrupt proof."""
    from dataclasses import replace

    from polisyos.scientist.orchestration.engine.circuit_breaker import CircuitBreaker
    from polisyos.scientist.orchestration.engine.context import _EngineInvocationBinding
    from polisyos.scientist.orchestration.engine.errors import ErrorCategory, NodeExecutionError
    from polisyos.scientist.orchestration.engine.retry import RetryPolicy, execute_with_retry_sync
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    view = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    bound = replace(
        ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id="run-issued", attempt_id=attempt_id, basis_ref=basis, settlement_view=view
        ),
    )
    state = ExperimentState(
        run_id="run-issued", params={"clean": "original"}, budgets={"run_spent_usd": Decimal("5")}
    )
    receipt_refs: list[ArtifactRef] = []
    completions = []
    dispatches = []
    error = NodeExecutionError(
        "declared failed effect", code="fixture.typed_failure", category=ErrorCategory.FATAL
    )

    class FailingNode:
        def execute(self, node_ctx, attempt_state):
            dispatches.append(1)
            receipt_refs.append(
                node_ctx._engine_invocation.settlement_view.settle_spend(
                    Decimal("2"), payload_ref=payload, provider="local-fixture"
                )
            )
            attempt_state.params["dirty"] = "must-not-commit"
            attempt_state.budgets["run_spent_usd"] = Decimal("999")
            raise error

    if corruption != "none":
        view_type = type(view)
        original_verify = view_type._verify_acknowledged_settlement
        checks = []

        def corrupt_on_selected_verification(current_view):
            checks.append(1)
            if len(checks) == (1 if corruption == "first" else 2):
                blob, _manifest = ctx.store._paths(receipt_refs[0].artifact_id)
                blob.write_bytes(b"corrupt selected receipt at verification")
            return original_verify(current_view)

        monkeypatch.setattr(
            view_type, "_verify_acknowledged_settlement", corrupt_on_selected_verification
        )

    def started(number, _state):
        assert number == 1
        return attempt_id

    def completed(selected_attempt, outcome):
        assert selected_attempt == attempt_id
        completions.append(outcome)

    with pytest.raises(Exception) as caught:
        execute_with_retry_sync(
            FailingNode(),
            bound,
            state,
            retry_policy=RetryPolicy(max_retries=0),
            timeout_s=None,
            alias="effect",
            circuit_breaker=CircuitBreaker() if use_breaker else None,
            attempt_started=started,
            attempt_completed=completed,
            attempt_context=lambda selected: bound if selected == attempt_id else None,
        )

    assert dispatches == [1] and len(receipt_refs) == 1
    assert ledger.snapshot().state.spent["run"] == Decimal("7")
    if corruption != "none":
        assert len(checks) == (1 if corruption == "first" else 2)
        assert isinstance(caught.value, ValueError)
        assert str(caught.value) == "budget_invocation_receipt_profile_invalid"
        assert completions == [None]
    else:
        assert isinstance(caught.value, NodeExecutionError)
        assert len(completions) == 1 and completions[0] is not None
        completion = completions[0]
        assert completion.status == "fail"
        assert completion.error.code == "fixture.typed_failure"
        assert completion.error.category is ErrorCategory.FATAL
        assert completion.state.params == {"clean": "original"}
        assert completion.state.budgets["run_spent_usd"] == Decimal("7")
        assert completion.artifacts == [payload, receipt_refs[0]]


@pytest.mark.parametrize("execution", ["sync", "async"])
def test_typed_failure_cannot_hide_explicit_unknown_child_after_receipt(
    invocation, execution: str
) -> None:
    """A confirmed charge cannot turn a separate unknown child effect into failure."""
    import asyncio
    from dataclasses import replace

    from polisyos.core.run.context import ChildOutcomeUnknownError
    from polisyos.scientist.orchestration.engine.context import _EngineInvocationBinding
    from polisyos.scientist.orchestration.engine.errors import ErrorCategory, NodeExecutionError
    from polisyos.scientist.orchestration.engine.retry import (
        RetryPolicy,
        execute_with_retry_async,
        execute_with_retry_sync,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    ctx, middleware, ledger, attempt_id, basis, payload = invocation
    view = _issue_invocation_settlement_view(
        middleware, ctx, alias="effect", attempt_id=attempt_id, basis_ref=basis
    )
    bound = replace(
        ctx,
        _engine_invocation=_EngineInvocationBinding(
            run_id="run-issued", attempt_id=attempt_id, basis_ref=basis, settlement_view=view
        ),
    )
    state = ExperimentState(run_id="run-issued", budgets={"run_spent_usd": Decimal("5")})
    assert ctx.run.trace_path is not None
    unknown = ChildOutcomeUnknownError(
        "child effect may have happened",
        run_id="fixture-child",
        run_dir=ctx.run.trace_path.parent / "fixture-child",
    )
    error = NodeExecutionError(
        "declared wrapper", code="node.exception", category=ErrorCategory.TRANSIENT
    )
    dispatches, completions, started_numbers = [], [], []

    class UnknownNode:
        def execute(self, node_ctx, _state):
            dispatches.append(1)
            node_ctx._engine_invocation.settlement_view.settle_spend(
                Decimal("2"), payload_ref=payload, provider="local-fixture"
            )
            raise error from unknown

        async def execute_async(self, node_ctx, attempt_state):
            return self.execute(node_ctx, attempt_state)

    def started(number, _state):
        started_numbers.append(number)
        return attempt_id

    def completed(selected_attempt, outcome):
        assert selected_attempt == attempt_id
        completions.append(outcome)

    async def started_async(number, attempt_state):
        return started(number, attempt_state)

    async def completed_async(selected_attempt, outcome):
        completed(selected_attempt, outcome)

    common = {
        "retry_policy": RetryPolicy(max_retries=1, retry_on=["node.exception"]),
        "timeout_s": None,
        "alias": "effect",
        "attempt_context": lambda selected: bound if selected == attempt_id else None,
    }

    def invoke():
        if execution == "sync":
            return execute_with_retry_sync(
                UnknownNode(),
                bound,
                state,
                attempt_started=started,
                attempt_completed=completed,
                **common,
            )
        return asyncio.run(
            execute_with_retry_async(
                UnknownNode(),
                bound,
                state,
                attempt_started=started_async,
                attempt_completed=completed_async,
                **common,
            )
        )

    with pytest.raises(Exception) as caught:
        invoke()
    chain = []
    current = caught.value
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__
    assert unknown in chain
    assert started_numbers == [1]
    assert dispatches == [1]
    assert completions == [None]
    assert ledger.snapshot().state.spent["run"] == Decimal("7")
