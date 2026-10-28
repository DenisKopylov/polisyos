"""Fresh run-budget observations from the existing durable producer owner.

This module reconciles the already-issued USD ledger events with the existing
runtime allocation. It does not price numerical work or issue financial events.
An observation is an audit view; only a fresh owner read can admit another call.
"""

from __future__ import annotations

import hashlib
import json
import threading
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.scientist.orchestration.engine.budget import (
    BudgetExhaustedError,
    BudgetLimit,
    BudgetState,
)
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerProducerRecord,
    BudgetLedgerProducerRunBinding,
    BudgetLedgerSnapshot,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

__all__ = [
    "ProducerBudgetObservation",
    "ProducerBudgetObserver",
    "ProducerBudgetSourceError",
]


class ProducerBudgetSourceError(ValueError):
    """The current selected run's budget basis could not be established."""


class ProducerBudgetObservation(BaseModel):
    """Detached current-basis view, never a reusable execution permission."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["scientist.producer_budget_observation.v1"] = (
        "scientist.producer_budget_observation.v1"
    )
    currency: Literal["USD"] = "USD"
    predicate_basis: Literal["independently_reconciled"] = "independently_reconciled"
    run_binding: BudgetLedgerProducerRunBinding
    producer_key: str
    runtime_key: Literal["run"] = "run"
    settlement_owner: tuple[str, str, str]
    configured_limit_usd: Decimal = Field(ge=0, allow_inf_nan=False)
    configured_soft_limit_usd: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    producer_spent_usd: Decimal = Field(ge=0, allow_inf_nan=False)
    runtime_allocation_usd: Decimal = Field(ge=0, allow_inf_nan=False)
    reserved_usd: Decimal = Field(ge=0, allow_inf_nan=False)
    total_allocated_usd: Decimal = Field(ge=0, allow_inf_nan=False)
    remaining_usd: Decimal = Field(allow_inf_nan=False)
    producer_events: tuple[tuple[str, str, int, str], ...]
    ledger_revision: int = Field(ge=0)
    source_basis_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    limitations: tuple[str, ...] = (
        "runtime_allocation_is_not_measured_n5_cost",
        "n5_usd_price_not_established",
        "remaining_allocation_is_not_a_per_call_cost_reservation",
    )

    @model_validator(mode="after")
    def _recompute_projection(self) -> ProducerBudgetObservation:
        """Recompute audit arithmetic and content binding, without granting authority."""
        if self.total_allocated_usd != self.producer_spent_usd + self.runtime_allocation_usd:
            raise ValueError("producer_budget_total_projection_mismatch")
        if self.remaining_usd != (
            self.configured_limit_usd - self.total_allocated_usd - self.reserved_usd
        ):
            raise ValueError("producer_budget_remaining_projection_mismatch")
        if self.producer_key != f"nl-run:{self.run_binding.run_id}":
            raise ValueError("producer_budget_run_key_mismatch")
        ids = [row[0] for row in self.producer_events]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("producer_budget_event_set_invalid")
        basis = {
            "owner": self.settlement_owner,
            "run_binding": self.run_binding.model_dump(mode="json"),
            "key": self.producer_key,
            "configured_limit_usd": _decimal_ref(self.configured_limit_usd),
            "configured_soft_limit_usd": (
                _decimal_ref(self.configured_soft_limit_usd)
                if self.configured_soft_limit_usd is not None
                else None
            ),
            "runtime_allocation_usd": _decimal_ref(self.runtime_allocation_usd),
            "reserved_usd": _decimal_ref(self.reserved_usd),
            "producer_events": sorted(self.producer_events),
            "producer_spent_usd": _decimal_ref(self.producer_spent_usd),
        }
        digest = hashlib.sha256(
            json.dumps(basis, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
        if digest != self.source_basis_digest:
            raise ValueError("producer_budget_source_basis_mismatch")
        return self


def _decimal_ref(value: Decimal) -> str:
    """Canonicalize the amount, not its incidental trailing-zero representation."""
    if value == 0:
        return "0"
    rendered = format(value, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _amount(value: object, code: str) -> Decimal:
    if type(value) is not Decimal or not value.is_finite() or value < Decimal(0):
        raise ProducerBudgetSourceError(code)
    return value


class ProducerBudgetObserver:
    """Reconcile one existing budget state against one exact durable run owner.

    The caller supplies the admitted run binding and configured run cap. The
    source is re-opened for every admission. A detached or request-supplied view
    cannot be substituted for this observer or renew its source basis.
    """

    def __init__(
        self,
        *,
        settlement_store: BudgetMiddleware,
        producer_run_binding: BudgetLedgerProducerRunBinding,
        budget_state: BudgetState,
    ) -> None:
        if type(settlement_store) is not BudgetMiddleware:
            raise TypeError("control_nl_budget_settlement_store_invalid")
        if type(producer_run_binding) is not BudgetLedgerProducerRunBinding:
            raise TypeError("control_nl_budget_run_binding_invalid")
        if type(budget_state) is not BudgetState:
            raise TypeError("control_nl_budget_state_invalid")
        self._store = settlement_store
        self._binding = producer_run_binding
        self._state = budget_state
        self._limit = self._current_limit().model_copy(deep=True)
        self._owner = settlement_store.settlement_owner_identity
        self._last_reconciled_total = Decimal(0)
        self._last_checked: ProducerBudgetObservation | None = None
        self._lock = threading.RLock()

    @property
    def configured_limit_usd(self) -> Decimal:
        """Return the captured configured allocation, without asserting current spend."""
        return self._limit.max_usd

    @property
    def last_checked(self) -> ProducerBudgetObservation | None:
        """Return the last checked source view without refreshing its identity."""
        with self._lock:
            return self._last_checked

    def require_bound_state(self, current_state: BudgetState) -> None:
        """Check invocation identity/configuration without inventing a spend read."""
        with self._lock:
            if current_state is not self._state or type(current_state) is not BudgetState:
                raise ProducerBudgetSourceError("control_nl_budget_state_binding_mismatch")
            if self._current_limit() != self._limit:
                raise ProducerBudgetSourceError("control_nl_budget_run_limit_changed")

    def __call__(self, current_state: BudgetState) -> None:
        """Preserve the existing scheduler's None-returning callback contract."""
        self.require_bound_state(current_state)
        with self._lock:
            if self._current_limit() != self._limit:
                raise ProducerBudgetSourceError("control_nl_budget_run_limit_changed")
            # The scheduler can independently enforce a configured zero ceiling;
            # no missing event is converted into a known-zero spend projection.
            if self._limit.max_usd <= Decimal(0):
                return
            self.observe()

    def _current_limit(self) -> BudgetLimit:
        if type(self._state.limits) is not dict:
            raise ProducerBudgetSourceError("control_nl_budget_limits_not_established")
        limit = self._state.limits.get("run")
        if type(limit) is not BudgetLimit or limit.key != "run":
            raise ProducerBudgetSourceError("control_nl_budget_run_limit_not_established")
        _amount(limit.max_usd, "control_nl_budget_run_limit_invalid")
        if limit.soft_limit_usd is not None:
            _amount(limit.soft_limit_usd, "control_nl_budget_run_limit_invalid")
        return limit

    def _snapshot(self) -> BudgetLedgerSnapshot:
        try:
            snapshot = self._store.snapshot_safe()
        except Exception as exc:
            raise ProducerBudgetSourceError(
                "control_nl_budget_producer_events_unavailable"
            ) from exc
        if type(snapshot) is not BudgetLedgerSnapshot:
            raise ProducerBudgetSourceError("control_nl_budget_snapshot_untyped")
        owner = (snapshot.ledger_id, snapshot.canonical_contract, snapshot.coordination_mode)
        if owner != self._owner:
            raise ProducerBudgetSourceError("control_nl_budget_source_owner_changed")
        return snapshot

    def observe(self) -> ProducerBudgetObservation:
        """Re-open the current ledger and reconcile its exact selected event set."""
        with self._lock:
            if self._current_limit() != self._limit:
                raise ProducerBudgetSourceError("control_nl_budget_run_limit_changed")
            snapshot = self._snapshot()
            key = f"nl-run:{self._binding.run_id}"
            records = tuple(
                record
                for record in snapshot.producer_settlements.values()
                if record.key == key or record.run_binding == self._binding
            )
            if not records:
                raise ProducerBudgetSourceError("control_nl_budget_producer_events_not_established")
            total = Decimal(0)
            event_ids: set[str] = set()
            event_basis: list[tuple[str, str, int, str]] = []
            for record in records:
                if type(record) is not BudgetLedgerProducerRecord:
                    raise ProducerBudgetSourceError("control_nl_budget_producer_event_untyped")
                if record.key != key or record.run_binding != self._binding:
                    raise ProducerBudgetSourceError(
                        "control_nl_budget_producer_event_binding_mismatch"
                    )
                if record.event_id in event_ids:
                    raise ProducerBudgetSourceError("control_nl_budget_producer_event_duplicate")
                event_ids.add(record.event_id)
                if record.status != "committed":
                    raise ProducerBudgetSourceError("control_nl_budget_producer_event_not_settled")
                amount = _amount(record.amount, "control_nl_budget_producer_amount_not_established")
                if record.cost_origin not in {"reported", "estimated", "reuse"}:
                    raise ProducerBudgetSourceError(
                        "control_nl_budget_producer_cost_origin_not_established"
                    )
                if record.payload_digest is None:
                    raise ProducerBudgetSourceError(
                        "control_nl_budget_producer_payload_not_established"
                    )
                if record.cost_origin == "reuse":
                    origin = snapshot.producer_settlements.get(record.origin_event_id or "")
                    # Unknown physical cost stays unknown even if cache reuse cost is zero.
                    if (
                        type(origin) is not BudgetLedgerProducerRecord
                        or origin.status != "committed"
                        or origin.cost_origin not in {"reported", "estimated"}
                    ):
                        raise ProducerBudgetSourceError(
                            "control_nl_budget_producer_reuse_origin_not_established"
                        )
                    try:
                        record.validate_reuse_origin(origin)
                    except (TypeError, ValueError) as exc:
                        raise ProducerBudgetSourceError(
                            "control_nl_budget_producer_reuse_origin_not_established"
                        ) from exc
                total += amount
                if not total.is_finite():
                    raise ProducerBudgetSourceError("control_nl_budget_producer_total_invalid")
                event_basis.append(
                    (record.event_id, record.payload_digest, record.revision, record.cost_origin)
                )
            if type(self._state.spent) is not dict or type(self._state.reserved) is not dict:
                raise ProducerBudgetSourceError("control_nl_budget_state_spend_not_established")
            spent = _amount(
                self._state.spent.get("run", Decimal(0)),
                "control_nl_budget_state_spend_not_established",
            )
            allocation = spent - self._last_reconciled_total
            _amount(allocation, "control_nl_budget_state_spend_basis_invalid")
            reserved = _amount(
                self._state.reserved.get("run", Decimal(0)),
                "control_nl_budget_state_reserved_not_established",
            )
            total_allocated = allocation + total
            remaining = self._limit.max_usd - total_allocated - reserved
            basis = {
                "owner": self._owner,
                "run_binding": self._binding.model_dump(mode="json"),
                "key": key,
                "configured_limit_usd": _decimal_ref(self._limit.max_usd),
                "configured_soft_limit_usd": (
                    _decimal_ref(self._limit.soft_limit_usd)
                    if self._limit.soft_limit_usd is not None
                    else None
                ),
                "runtime_allocation_usd": _decimal_ref(allocation),
                "reserved_usd": _decimal_ref(reserved),
                "producer_events": sorted(event_basis),
                "producer_spent_usd": _decimal_ref(total),
            }
            digest = hashlib.sha256(
                json.dumps(basis, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            ).hexdigest()
            observation = ProducerBudgetObservation(
                run_binding=self._binding,
                producer_key=key,
                settlement_owner=self._owner,
                configured_limit_usd=self._limit.max_usd,
                configured_soft_limit_usd=self._limit.soft_limit_usd,
                producer_spent_usd=total,
                runtime_allocation_usd=allocation,
                reserved_usd=reserved,
                total_allocated_usd=total_allocated,
                remaining_usd=remaining,
                producer_events=tuple(sorted(event_basis)),
                ledger_revision=snapshot.revision,
                source_basis_digest=digest,
            )
            self._state.spent["run"] = total_allocated
            self._last_reconciled_total = total
            self._last_checked = observation
            return observation

    def admit(self) -> ProducerBudgetObservation:
        """Admit another physical call only after a fresh current-owner read.

        A zero configured cap independently refuses work; it does not impute
        zero cost to an absent ledger event. Unknown positive-cap spend refuses
        owner-bound admission instead of silently becoming a free allocation.
        """
        with self._lock:
            if self._current_limit() != self._limit:
                raise ProducerBudgetSourceError("control_nl_budget_run_limit_changed")
            if self._limit.max_usd <= Decimal(0):
                raise BudgetExhaustedError("configured USD run cap exhausted before N5")
            observation = self.observe()
            if observation.remaining_usd <= Decimal(0):
                raise BudgetExhaustedError("current USD run allocation exhausted before N5")
            return observation
