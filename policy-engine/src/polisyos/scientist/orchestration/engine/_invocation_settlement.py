"""Private, engine-issued settlement binding for one selected invocation."""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from polisyos.common.job_execution_interrupt import (
    JobExecutionOwnerNotEstablishedError,
    raise_if_job_execution_interrupted,
    require_current_job_execution_owner,
)
from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    ProducerInfo,
    SchemaInfo,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
)
from polisyos.core.canon import CanonSpec, content_hash, to_canonical_bytes
from polisyos.scientist.orchestration.engine.budget_ledger import (
    _ENGINE_EVENT_PREFIX,
    BudgetLedgerSettlementOutcomeUnknownError,
    BudgetLedgerSnapshot,
    BudgetLedgerSpendReceipt,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore
    from polisyos.core.run.manifest import RunInvocationStarted
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

_RECEIPT_KIND = "scientist.budget_spend_receipt"
_RECEIPT_SCHEMA = "polisyos.scientist.orchestration.engine.budget_ledger.BudgetLedgerSpendReceipt"
_Settle = Callable[[str, Decimal, str, str | None], BudgetLedgerSpendReceipt]


def _require_settlement_owner(ctx: ExecutionContext, *, check_unbound: bool = True) -> None:
    """Check the persisted run's job restriction before consuming its capability."""
    ctx.run._validate_run_owner_binding()
    job_id = ctx.run.run_manifest.control_job_id
    if job_id is not None:
        require_current_job_execution_owner(job_id)
    elif check_unbound:
        raise_if_job_execution_interrupted(check_current_owner=True)


@dataclass(frozen=True)
class _VerifiedInvocationSettlement:
    """One acknowledged local charge, independently reconciled with its owner."""

    amount: Decimal
    total: Decimal
    payload_ref: ArtifactRef
    receipt_ref: ArtifactRef


@dataclass(frozen=True)
class _PendingInvocationSettlement:
    event_id: str
    payload_digest: str
    amount: Decimal
    provider: str | None
    payload_ref: ArtifactRef


def _invocation_spend_identity(
    *,
    run_id: str,
    alias: str,
    attempt_id: str,
    basis_ref: ArtifactRef,
    payload_ref: ArtifactRef,
) -> tuple[str, str]:
    """Derive one stable event per physical attempt and its exact effect binding."""
    event_id = _ENGINE_EVENT_PREFIX + content_hash(
        to_canonical_bytes(
            {
                "contract": "scientist.engine_invocation_event.v1",
                "run_id": run_id,
                "alias": alias,
                "attempt_id": attempt_id,
                "basis_ref": basis_ref.model_dump(mode="json"),
            },
            CanonSpec(forbid_floats=False),
        )
    )
    digest = content_hash(
        to_canonical_bytes(
            {
                "contract": "scientist.engine_invocation_settlement.v1",
                "run_id": run_id,
                "alias": alias,
                "attempt_id": attempt_id,
                "basis_ref": basis_ref.model_dump(mode="json"),
                "payload_ref": payload_ref.model_dump(mode="json"),
            },
            CanonSpec(forbid_floats=False),
        )
    )
    return event_id, digest


class _InvocationSettlementView:
    """An invocation's narrow settlement capability; it exposes no ledger owner."""

    __slots__ = (
        "__acknowledged",
        "__alias",
        "__attempt_id",
        "__attempted",
        "__basis_ref",
        "__ctx",
        "__last_error",
        "__lock",
        "__pending",
        "__settle",
        "__snapshot",
        "__spent",
        "__uncertain",
    )

    def __init__(
        self,
        *,
        ctx: ExecutionContext,
        alias: str,
        attempt_id: str,
        basis_ref: ArtifactRef,
        settle: _Settle,
        snapshot: Callable[[], BudgetLedgerSnapshot],
        spent: Callable[[], Decimal],
    ) -> None:
        self.__ctx = ctx
        self.__lock = threading.RLock()
        self.__alias = alias
        self.__attempt_id = attempt_id
        self.__attempted = False
        self.__uncertain = False
        self.__acknowledged: tuple[ArtifactRef, ArtifactRef] | None = None
        self.__pending: _PendingInvocationSettlement | None = None
        self.__last_error: Exception | None = None
        self.__basis_ref = basis_ref.model_copy(deep=True)
        self.__settle = settle
        self.__snapshot = snapshot
        self.__spent = spent

    @property
    def settlement_attempted(self) -> bool:
        """Indicate whether this invocation entered the settlement boundary."""
        with self.__lock:
            return self.__attempted

    @property
    def _settlement_uncertain(self) -> bool:
        """Retain uncertainty after a failed call until an exact successful retry."""
        with self.__lock:
            return self.__uncertain

    def _acknowledged_settlement(self) -> tuple[ArtifactRef, ArtifactRef] | None:
        """Return detached selectors; a later call may still be uncertain."""
        with self.__lock:
            if self.__acknowledged is None:
                return None
            payload_ref, receipt_ref = self.__acknowledged
            return payload_ref.model_copy(deep=True), receipt_ref.model_copy(deep=True)

    def _verify_acknowledged_settlement(self) -> _VerifiedInvocationSettlement | None:
        """Reconcile a successful selected receipt with the actual current owner."""
        with self.__lock:
            if self.__uncertain:
                if self.__last_error is not None:
                    raise self.__last_error
                if self.__pending is not None:
                    raise BudgetLedgerSettlementOutcomeUnknownError(
                        self.__pending.event_id, self.__pending.payload_digest
                    )
                raise ValueError("budget_invocation_settlement_identity_not_established")
            return self._verify_prior_acknowledged_settlement()

    def _verify_prior_acknowledged_settlement(self) -> _VerifiedInvocationSettlement | None:
        """Verify the last known receipt without resolving a later uncertain call."""
        with self.__lock:
            acknowledged = self._acknowledged_settlement()
            if acknowledged is None:
                return None
            _require_live_invocation(self.__ctx, self.__alias, self.__attempt_id, self.__basis_ref)
            payload_ref, receipt_ref = acknowledged
            snapshot = self.__snapshot()
            verified = self.__verify_receipt(payload_ref, receipt_ref, snapshot)
            _require_settlement_owner(self.__ctx)
            return verified

    def __verify_receipt(
        self, payload_ref: ArtifactRef, receipt_ref: ArtifactRef, snapshot: BudgetLedgerSnapshot
    ) -> _VerifiedInvocationSettlement:
        receipt = _verify_invocation_settlement_receipt(
            self.__ctx.store,
            receipt_ref,
            [payload_ref, receipt_ref],
            run_id=self.__ctx.run.run_manifest.run_id,
            alias=self.__alias,
            attempt_id=self.__attempt_id,
            basis_ref=self.__basis_ref,
            snapshot=snapshot,
        )
        total = snapshot.state.spent.get("run", Decimal(0))
        if type(total) is not Decimal or not total.is_finite() or total < receipt.amount:
            raise ValueError("budget_invocation_confirmed_spend_invalid")
        return _VerifiedInvocationSettlement(
            amount=receipt.amount,
            total=total,
            payload_ref=payload_ref,
            receipt_ref=receipt_ref,
        )

    def __put_receipt(
        self, receipt: BudgetLedgerSpendReceipt, payload_ref: ArtifactRef
    ) -> ArtifactRef:
        receipt_ref = self.__ctx.store.put_json(
            receipt.model_dump(mode="json"),
            ArtifactWriteOptions(
                kind=_RECEIPT_KIND,
                media_type="application/json",
                schema=SchemaInfo(name=_RECEIPT_SCHEMA, version="1.0"),
                producer=ProducerInfo(component=__name__, version="1.0"),
                inputs=[
                    input_ref_from_artifact_ref(self.__basis_ref, role="invocation_basis"),
                    input_ref_from_artifact_ref(payload_ref, role="producer_payload"),
                ],
            ),
            return_selected_profile=True,
        )
        if (
            type(receipt_ref) is not ArtifactRef
            or receipt_ref.kind != _RECEIPT_KIND
            or receipt_ref.media_type != "application/json"
            or receipt_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("budget_invocation_receipt_profile_invalid")
        return receipt_ref

    def _reconcile_pending_settlement(self) -> _VerifiedInvocationSettlement | None:
        """Reconfirm an existing exact event without dispatching or charging again."""
        with self.__lock:
            return self.__reconcile_pending_settlement()

    def __reconcile_pending_settlement(self) -> _VerifiedInvocationSettlement | None:
        if not self.__uncertain:
            return self._verify_acknowledged_settlement()
        pending = self.__pending
        if pending is None:
            if self.__last_error is not None:
                raise self.__last_error
            raise ValueError("budget_invocation_settlement_identity_not_established")
        try:
            _require_live_invocation(self.__ctx, self.__alias, self.__attempt_id, self.__basis_ref)
            snapshot = self.__snapshot()
            receipt = snapshot.spend_receipts.get(pending.event_id)
            if (
                receipt is None
                or receipt.payload_digest != pending.payload_digest
                or receipt.key != "run"
                or receipt.amount != pending.amount
                or receipt.provider != pending.provider
            ):
                raise ValueError("budget_invocation_pending_event_not_reconciled")
            if not self.__ctx.store.verify(pending.payload_ref).ok:
                raise ValueError("budget_invocation_payload_invalid")
            self.__ctx.store.get_bytes(pending.payload_ref)
            _require_settlement_owner(self.__ctx)
            receipt_ref = self.__put_receipt(receipt, pending.payload_ref)
            confirmed = self.__snapshot()
            if confirmed != snapshot:
                raise ValueError("budget_invocation_snapshot_changed")
            verified = self.__verify_receipt(pending.payload_ref, receipt_ref, confirmed)
            _require_settlement_owner(self.__ctx)
        except BudgetLedgerSettlementOutcomeUnknownError as exc:
            if (exc.event_id, exc.payload_digest) == (pending.event_id, pending.payload_digest):
                self.__last_error = exc
                raise
            error = BudgetLedgerSettlementOutcomeUnknownError(
                pending.event_id, pending.payload_digest
            )
            error.add_note("ledger reconciliation reported another unresolved outcome")
            self.__last_error = error
            raise error from exc
        except Exception as exc:
            error = BudgetLedgerSettlementOutcomeUnknownError(
                pending.event_id, pending.payload_digest
            )
            error.add_note(f"exact settlement reconciliation failed: {type(exc).__name__}")
            self.__last_error = error
            raise error from exc
        self.__acknowledged = (
            pending.payload_ref.model_copy(deep=True),
            receipt_ref.model_copy(deep=True),
        )
        self.__uncertain = False
        self.__pending = None
        self.__last_error = None
        return verified

    @property
    def spent(self) -> Decimal:
        """Return this owner's current confirmed `run` spend only."""
        with self.__lock:
            _require_live_invocation(self.__ctx, self.__alias, self.__attempt_id, self.__basis_ref)
            return self.__spent()

    def settle_spend(
        self, amount: Decimal, *, payload_ref: ArtifactRef, provider: str | None = None
    ) -> ArtifactRef:
        """Persist the exact event and return its selected receipt artifact."""
        with self.__lock:
            return self.__settle_spend(amount, payload_ref=payload_ref, provider=provider)

    def __settle_spend(
        self, amount: Decimal, *, payload_ref: ArtifactRef, provider: str | None
    ) -> ArtifactRef:
        self.__attempted = True
        self.__uncertain = True
        self.__pending = None
        self.__last_error = None
        if type(payload_ref) is not ArtifactRef or payload_ref.manifest_profile_sha256 is None:
            error = ValueError("budget_invocation_payload_profile_required")
            self.__last_error = error
            raise error
        payload_ref = payload_ref.model_copy(deep=True)
        event_id, digest = _invocation_spend_identity(
            run_id=self.__ctx.run.run_manifest.run_id,
            alias=self.__alias,
            attempt_id=self.__attempt_id,
            basis_ref=self.__basis_ref,
            payload_ref=payload_ref,
        )
        try:
            candidate = BudgetLedgerSpendReceipt(
                event_id=event_id,
                payload_digest=digest,
                key="run",
                amount=amount,
                provider=provider,
                revision=1,
            )
        except Exception as exc:
            self.__last_error = exc
            raise
        self.__pending = _PendingInvocationSettlement(
            event_id,
            digest,
            candidate.amount,
            candidate.provider,
            payload_ref.model_copy(deep=True),
        )
        try:
            _require_live_invocation(self.__ctx, self.__alias, self.__attempt_id, self.__basis_ref)
        except (
            JobExecutionOwnerNotEstablishedError,
            ValueError,
            TypeError,
            MemoryError,
            NotImplementedError,
        ) as exc:
            self.__last_error = exc
            raise
        except Exception as exc:
            error = BudgetLedgerSettlementOutcomeUnknownError(event_id, digest)
            self.__last_error = error
            raise error from exc
        write_dispatched = False
        try:
            if not self.__ctx.store.verify(payload_ref).ok:
                raise ValueError("budget_invocation_payload_invalid")
            self.__ctx.store.get_bytes(payload_ref)
            _require_settlement_owner(self.__ctx)
            write_dispatched = True
            receipt = self.__settle(event_id, candidate.amount, digest, candidate.provider)
            _require_settlement_owner(self.__ctx)
            receipt_ref = self.__put_receipt(receipt, payload_ref)
            _require_settlement_owner(self.__ctx)
            self.__acknowledged = (
                payload_ref.model_copy(deep=True),
                receipt_ref.model_copy(deep=True),
            )
            self.__uncertain = False
            self.__pending = None
            self.__last_error = None
            return receipt_ref
        except JobExecutionOwnerNotEstablishedError as exc:
            if not write_dispatched:
                self.__last_error = exc
                raise
            error = BudgetLedgerSettlementOutcomeUnknownError(event_id, digest)
            self.__last_error = error
            raise error from exc
        except BudgetLedgerSettlementOutcomeUnknownError as exc:
            self.__last_error = exc
            raise
        except Exception as exc:
            error = BudgetLedgerSettlementOutcomeUnknownError(event_id, digest)
            self.__last_error = error
            raise error from exc


def _require_live_invocation(
    ctx: ExecutionContext, alias: str, attempt_id: str, basis_ref: ArtifactRef
) -> RunInvocationStarted:
    _require_settlement_owner(ctx, check_unbound=False)
    if type(basis_ref) is not ArtifactRef or basis_ref.manifest_profile_sha256 is None:
        raise ValueError("budget_invocation_basis_profile_required")
    matches = [
        item
        for item in ctx.run.read_runtime_invocation_attempts()
        if item.basis_ref == basis_ref and item.basis.attempt_id == attempt_id
    ]
    if len(matches) != 1:
        raise ValueError("budget_invocation_basis_not_owner_linked")
    attempt = matches[0]
    if (
        attempt.outcome is not None
        or attempt.basis.run_id != ctx.run.run_manifest.run_id
        or attempt.basis.node_alias != alias
        or attempt.basis.budget_middleware_active is not True
    ):
        raise ValueError("budget_invocation_not_active")
    return attempt.basis


def _issue_invocation_settlement_view(
    middleware: BudgetMiddleware,
    ctx: ExecutionContext,
    *,
    alias: str,
    attempt_id: str,
    basis_ref: ArtifactRef,
) -> _InvocationSettlementView:
    """Issue a private view only for the actual active Core-owned attempt."""
    if type(middleware) is not BudgetMiddleware:
        raise ValueError("budget_ledger_engine_owner_not_supported")
    basis = _require_live_invocation(ctx, alias, attempt_id, basis_ref)
    owner = basis.budget_owner_identity
    resource = basis.budget_resource_identity
    revision = basis.budget_start_revision
    digest = basis.budget_start_snapshot_sha256
    if (
        owner is None
        or resource is None
        or revision is None
        or digest is None
        or basis.invocation_settlement_profile != "single_owner_local_v1"
        or middleware.invocation_settlement_profile != basis.invocation_settlement_profile
    ):
        raise ValueError("budget_invocation_start_binding_not_established")
    middleware._arm_engine_guard(owner, resource, (revision, digest))
    return _InvocationSettlementView(
        ctx=ctx,
        alias=alias,
        attempt_id=attempt_id,
        basis_ref=basis_ref,
        settle=middleware._issue_engine_settlement_writer(),
        snapshot=lambda: middleware._continuation_state()[3],
        spent=middleware._read_engine_spent,
    )


def _verify_invocation_settlement_receipt(
    store: ArtifactStore,
    receipt_ref: ArtifactRef,
    output_refs: Sequence[ArtifactRef],
    *,
    run_id: str,
    alias: str,
    attempt_id: str,
    basis_ref: ArtifactRef,
    snapshot: BudgetLedgerSnapshot,
) -> BudgetLedgerSpendReceipt:
    """Verify one selected receipt against its protected attempt and actual output."""
    if (
        type(receipt_ref) is not ArtifactRef
        or type(basis_ref) is not ArtifactRef
        or basis_ref.manifest_profile_sha256 is None
        or receipt_ref not in output_refs
        or receipt_ref.kind != _RECEIPT_KIND
        or receipt_ref.media_type != "application/json"
        or receipt_ref.manifest_profile_sha256 is None
        or not store.verify(receipt_ref).ok
    ):
        raise ValueError("budget_invocation_receipt_profile_invalid")
    manifest = store.get_manifest(receipt_ref)
    if (
        manifest.artifact_schema is None
        or manifest.artifact_schema.name != _RECEIPT_SCHEMA
        or manifest.artifact_schema.version != "1.0"
    ):
        raise ValueError("budget_invocation_receipt_schema_invalid")
    bases = [item for item in manifest.inputs if item.role == "invocation_basis"]
    payloads = [item for item in manifest.inputs if item.role == "producer_payload"]
    if (
        len(bases) != 1
        or bases[0].artifact_id != basis_ref.artifact_id
        or bases[0].manifest_profile_sha256 != basis_ref.manifest_profile_sha256
        or len(payloads) != 1
    ):
        raise ValueError("budget_invocation_receipt_lineage_invalid")
    payload_matches = [
        ref
        for ref in output_refs
        if ref != receipt_ref
        and ref.artifact_id == payloads[0].artifact_id
        and ref.manifest_profile_sha256 == payloads[0].manifest_profile_sha256
    ]
    if (
        len(payload_matches) != 1
        or payload_matches[0].manifest_profile_sha256 is None
        or not store.verify(payload_matches[0]).ok
    ):
        raise ValueError("budget_invocation_payload_not_owned")
    store.get_bytes(payload_matches[0])
    receipt = BudgetLedgerSpendReceipt.model_validate(load_core_json_artifact(store, receipt_ref))
    expected_event, expected_digest = _invocation_spend_identity(
        run_id=run_id,
        alias=alias,
        attempt_id=attempt_id,
        basis_ref=basis_ref,
        payload_ref=payload_matches[0],
    )
    if (
        receipt.event_id != expected_event
        or receipt.payload_digest != expected_digest
        or receipt.key != "run"
        or type(snapshot) is not BudgetLedgerSnapshot
        or snapshot.spend_receipts.get(expected_event) != receipt
    ):
        raise ValueError("budget_invocation_receipt_attempt_mismatch")
    return receipt
