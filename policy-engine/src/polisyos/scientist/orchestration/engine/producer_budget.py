"""Fresh run-budget observations from the existing durable producer owner.

This module reconciles the already-issued USD ledger events with the existing
runtime allocation. It does not price numerical work or issue financial events.
An observation is an audit view; only a fresh owner read can admit another call.
"""

from __future__ import annotations

import hashlib
import json
import threading
import weakref
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.scientist.orchestration.engine.budget import (
    BudgetExhaustedError,
    BudgetLimit,
    BudgetState,
)
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetInvocationQuotaPolicy,
    BudgetLedgerInvocationProfile,
    BudgetLedgerInvocationQuotaExhaustedError,
    BudgetLedgerInvocationReservation,
    BudgetLedgerProducerRecord,
    BudgetLedgerProducerRunBinding,
    BudgetLedgerReentryBudgetScope,
    BudgetLedgerReentryBudgetWindow,
    BudgetLedgerSnapshot,
    FileBudgetLedger,
    _reentry_add,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

__all__ = [
    "BudgetInvocationCapacityObservation",
    "BudgetInvocationExhaustionWitness",
    "ProducerBudgetObservation",
    "ProducerBudgetObserver",
    "ProducerBudgetSourceError",
    "verify_standard_invocation_exhaustion_historical",
]


class ProducerBudgetSourceError(ValueError):
    """The current selected run's budget basis could not be established."""


class BudgetInvocationExhaustionWitness(BaseModel):
    """Terminal unit facts sufficient to replay standard-quota exhaustion.

    The producing partial artifact must bind this witness to the actual stop.
    This proves no protected balance, past snapshot hash, or future permit.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["scientist.n5_standard_invocation_exhaustion.v1"] = (
        "scientist.n5_standard_invocation_exhaustion.v1"
    )
    run_binding: BudgetLedgerProducerRunBinding
    settlement_owner: tuple[str, str, str]
    resource_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    profile_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    standard_limit_units: int = Field(gt=0, strict=True)
    source_revision: int = Field(ge=1, strict=True)
    terminal_witnesses: tuple[tuple[str, int], ...] = Field(min_length=1)
    not_a_permit: Literal[True] = True

    @model_validator(mode="after")
    def _validate_terminal_witnesses(self) -> BudgetInvocationExhaustionWitness:
        ids = tuple(item[0] for item in self.terminal_witnesses)
        if (
            len(self.terminal_witnesses) != self.standard_limit_units
            or ids != tuple(sorted(set(ids)))
            or any(
                len(event_id) != 64
                or any(char not in "0123456789abcdef" for char in event_id)
                or type(event_revision) is not int
                or event_revision < 1
                or event_revision > self.source_revision
                for event_id, event_revision in self.terminal_witnesses
            )
        ):
            raise ValueError("invocation_exhaustion_witness_invalid")
        return self


class BudgetInvocationCapacityObservation(BaseModel):
    """A current quota view, never a reservation or a general N5 permit.

    Only terminal-witness exhaustion is replayable against the same durable
    owner. An available result is advisory for the captured snapshot only.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["scientist.n5_standard_invocation_capacity.v1"] = (
        "scientist.n5_standard_invocation_capacity.v1"
    )
    status: Literal["available", "exhausted", "not_established"]
    predicate_basis: Literal["independently_reconciled", "not_established"]
    reason_code: str | None = None
    run_binding: BudgetLedgerProducerRunBinding
    settlement_owner: tuple[str, str, str]
    resource_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    profile_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    standard_limit_units: int | None = Field(default=None, ge=0, strict=True)
    standard_remaining_units: int | None = Field(default=None, ge=0, strict=True)
    protected_limit_units: int | None = Field(default=None, ge=0, strict=True)
    protected_remaining_units: int | None = Field(default=None, ge=0, strict=True)
    source_revision: int | None = Field(default=None, ge=0, strict=True)
    source_anchor: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    terminal_witnesses: tuple[tuple[str, int], ...] = ()
    not_a_permit: Literal[True] = True

    @property
    def exhaustion_witness(self) -> BudgetInvocationExhaustionWitness | None:
        """Select only the replayable exhausted facts; other fields remain advisory."""
        if self.status != "exhausted":
            return None
        if (
            self.profile_digest is None
            or self.standard_limit_units is None
            or self.source_revision is None
        ):
            raise ValueError("invocation_exhaustion_observation_incomplete")
        return BudgetInvocationExhaustionWitness(
            run_binding=self.run_binding,
            settlement_owner=self.settlement_owner,
            resource_digest=self.resource_digest,
            profile_digest=self.profile_digest,
            standard_limit_units=self.standard_limit_units,
            source_revision=self.source_revision,
            terminal_witnesses=self.terminal_witnesses,
        )

    @model_validator(mode="after")
    def _validate_capacity_projection(self) -> BudgetInvocationCapacityObservation:
        measurements = (
            self.profile_digest,
            self.standard_limit_units,
            self.standard_remaining_units,
            self.protected_limit_units,
            self.protected_remaining_units,
            self.source_revision,
            self.source_anchor,
        )
        if self.status == "not_established":
            if (
                self.predicate_basis != "not_established"
                or not self.reason_code
                or any(value is not None for value in measurements)
                or self.terminal_witnesses
            ):
                raise ValueError("invocation_capacity_unknown_projection_invalid")
            return self
        if (
            self.predicate_basis != "independently_reconciled"
            or self.reason_code is not None
            or any(value is None for value in measurements)
        ):
            raise ValueError("invocation_capacity_projection_incomplete")
        limit = self.standard_limit_units
        remaining = self.standard_remaining_units
        protected_limit = self.protected_limit_units
        protected_remaining = self.protected_remaining_units
        revision = self.source_revision
        if (
            limit is None
            or remaining is None
            or revision is None
            or protected_limit is None
            or protected_remaining is None
        ):
            raise ValueError("invocation_capacity_projection_incomplete")
        witnesses = self.terminal_witnesses
        ids = tuple(item[0] for item in witnesses)
        if (
            limit <= 0
            or protected_remaining > protected_limit
            or remaining > limit
            or len(witnesses) != limit - remaining
            or ids != tuple(sorted(set(ids)))
            or any(
                len(event_id) != 64
                or any(char not in "0123456789abcdef" for char in event_id)
                or type(event_revision) is not int
                or event_revision < 1
                or event_revision > revision
                for event_id, event_revision in witnesses
            )
            or (self.status == "exhausted") != (remaining == 0)
        ):
            raise ValueError("invocation_capacity_projection_invalid")
        return self


def _capacity_resource_digest(resource: tuple[int, int, str, int, int]) -> str:
    encoded = json.dumps(resource, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _capacity_store_snapshot(
    store: BudgetMiddleware, *, require_existing_lock: bool = False
) -> tuple[
    tuple[str, str, str], tuple[int, int, str, int, int], tuple[int, str], BudgetLedgerSnapshot
]:
    """Read the exact file owner, refusing shadowed source-boundary methods."""
    if type(store) is not BudgetMiddleware or "_continuation_state" in vars(store):
        raise ValueError("invocation_capacity_source_shadowed")
    with store._lock:
        ledger = store._ledger
        if type(ledger) is not FileBudgetLedger or any(
            name in vars(ledger)
            for name in (
                "_continuation_state",
                "_file_lock",
                "_load_snapshot",
                "_read_snapshot",
                "_resource_identity",
                "_confirm_snapshot_durability",
                "_normalize_snapshot",
            )
        ):
            raise ValueError("invocation_capacity_source_shadowed")
        if require_existing_lock:
            return FileBudgetLedger._continuation_state(ledger, require_existing_lock=True)
        return FileBudgetLedger._continuation_state(ledger)


def _validate_exhaustion_witness(witness: object) -> BudgetInvocationExhaustionWitness:
    if type(witness) is not BudgetInvocationExhaustionWitness:
        raise ProducerBudgetSourceError("invocation_exhaustion_witness_untyped")
    try:
        return BudgetInvocationExhaustionWitness.model_validate_json(
            witness.model_dump_json(), strict=True
        )
    except (TypeError, ValueError) as exc:
        raise ProducerBudgetSourceError("invocation_exhaustion_witness_invalid") from exc


def _verify_exhaustion_terminal_records(
    snapshot: BudgetLedgerSnapshot,
    profile: BudgetLedgerInvocationProfile,
    witness: BudgetInvocationExhaustionWitness,
) -> None:
    for operation_id, revision in witness.terminal_witnesses:
        record = snapshot.invocation_reservations.get(operation_id)
        if (
            type(record) is not BudgetLedgerInvocationReservation
            or record.run_id != profile.run_binding.run_id
            or record.profile_digest != profile.profile_digest
            or record.purpose != "standard"
            or record.units != 1
            or record.status not in {"completed", "failed"}
            or record.revision != revision
            or revision > witness.source_revision
        ):
            raise ProducerBudgetSourceError("invocation_exhaustion_witness_mismatch")


def verify_standard_invocation_exhaustion_historical(
    *,
    settlement_store: BudgetMiddleware,
    expected_run_binding: BudgetLedgerProducerRunBinding,
    expected_policy: BudgetInvocationQuotaPolicy,
    witness: BudgetInvocationExhaustionWitness,
) -> bool:
    """Replay an issued stop against its existing owner without configuring a budget.

    The completed-run caller must independently reopen its selected policy and
    original run binding, and authenticate the stop artifact carrying witness.
    This verifies standard terminal units, not physical need or a future permit.

    Args:
        settlement_store: The completed run's already selected durable owner.
        expected_run_binding: Original binding established by the run owner.
        expected_policy: Policy independently reopened from selected input.
        witness: Terminal-only evidence from the persisted stop artifact.

    Returns:
        True when the exact historical terminal units remain reconciled.

    Raises:
        ProducerBudgetSourceError: If selection, owner, or evidence cannot be established.
    """
    if (
        type(expected_run_binding) is not BudgetLedgerProducerRunBinding
        or type(expected_policy) is not BudgetInvocationQuotaPolicy
    ):
        raise ProducerBudgetSourceError("invocation_exhaustion_selection_untyped")
    checked = _validate_exhaustion_witness(witness)
    try:
        binding = BudgetLedgerProducerRunBinding.model_validate_json(
            expected_run_binding.model_dump_json(), strict=True
        )
        policy = BudgetInvocationQuotaPolicy.model_validate_json(
            expected_policy.model_dump_json(), strict=True
        )
        profile = BudgetLedgerInvocationProfile.from_policy(binding, policy)
        owner, resource, anchor, snapshot = _capacity_store_snapshot(
            settlement_store, require_existing_lock=True
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ProducerBudgetSourceError("invocation_exhaustion_source_unavailable") from exc
    if (
        checked.run_binding != binding
        or checked.settlement_owner != owner
        or checked.resource_digest != _capacity_resource_digest(resource)
        or checked.profile_digest != profile.profile_digest
        or checked.standard_limit_units != profile.total_units - profile.protected_units
        or type(snapshot) is not BudgetLedgerSnapshot
        or snapshot.revision != anchor[0]
        or snapshot.invocation_profiles.get(binding.run_id) != profile
        or anchor[0] < checked.source_revision
    ):
        raise ProducerBudgetSourceError("invocation_exhaustion_owner_mismatch")
    _verify_exhaustion_terminal_records(snapshot, profile, checked)
    return True


class _LiveProducerReconciliation:
    """One live state's shared producer projection and serialization lock."""

    def __init__(
        self,
        owner: tuple[str, str, str],
        resource: tuple[int, int, str, int, int],
        binding: BudgetLedgerProducerRunBinding,
        window_id: str | None,
    ) -> None:
        self.owner = owner
        self.resource = resource
        self.binding = binding
        self.window_id = window_id
        self.lock = threading.RLock()
        self.last_reconciled_total = Decimal(0)


_LIVE_RECONCILIATIONS_LOCK = threading.RLock()
_LIVE_RECONCILIATIONS: dict[
    int, tuple[weakref.ReferenceType[BudgetState], _LiveProducerReconciliation]
] = {}


def _live_reconciliation(
    state: BudgetState,
    owner: tuple[str, str, str],
    resource: tuple[int, int, str, int, int],
    binding: BudgetLedgerProducerRunBinding,
    window_id: str | None,
) -> _LiveProducerReconciliation:
    """Share reconciliation by object identity without retaining the budget state."""
    key = id(state)
    with _LIVE_RECONCILIATIONS_LOCK:
        existing = _LIVE_RECONCILIATIONS.get(key)
        if existing is not None and existing[0]() is state:
            shared = existing[1]
            if (shared.owner, shared.resource, shared.binding, shared.window_id) != (
                owner,
                resource,
                binding,
                window_id,
            ):
                raise ProducerBudgetSourceError("control_nl_budget_state_owner_binding_mismatch")
            return shared

        if type(state.spent) is not dict:
            raise ProducerBudgetSourceError("control_nl_budget_state_spend_not_established")
        prior_spend = _amount(
            state.spent.get("run", Decimal(0)), "control_nl_budget_state_spend_not_established"
        )
        if prior_spend:
            raise ProducerBudgetSourceError(
                "control_nl_budget_state_projection_basis_not_established"
            )

        def forget(ref: weakref.ReferenceType[BudgetState]) -> None:
            with _LIVE_RECONCILIATIONS_LOCK:
                current = _LIVE_RECONCILIATIONS.get(key)
                if current is not None and current[0] is ref:
                    del _LIVE_RECONCILIATIONS[key]

        shared = _LiveProducerReconciliation(owner, resource, binding, window_id)
        _LIVE_RECONCILIATIONS[key] = (weakref.ref(state, forget), shared)
        return shared


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


def _add_budget_amount(left: Decimal, right: Decimal, *, exact: bool) -> Decimal:
    if not exact:
        return left + right
    try:
        return _reentry_add(left, right)
    except ValueError as exc:
        raise ProducerBudgetSourceError("reentry_budget_arithmetic_not_established") from exc


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
        invocation_quota_profile: BudgetLedgerInvocationProfile | None = None,
        invocation_purpose: Literal["standard", "diagnostic", "counterevidence"] = "standard",
        invocation_selection_pending: bool = False,
        reentry_budget_scope: BudgetLedgerReentryBudgetScope | None = None,
        invocation_guard_binding: object | None = None,
    ) -> None:
        if type(settlement_store) is not BudgetMiddleware:
            raise TypeError("control_nl_budget_settlement_store_invalid")
        if type(producer_run_binding) is not BudgetLedgerProducerRunBinding:
            raise TypeError("control_nl_budget_run_binding_invalid")
        if type(budget_state) is not BudgetState:
            raise TypeError("control_nl_budget_state_invalid")
        if reentry_budget_scope is not None and (
            type(reentry_budget_scope) is not BudgetLedgerReentryBudgetScope
            or reentry_budget_scope.run_binding != producer_run_binding
        ):
            raise ValueError("reentry_budget_scope_binding_mismatch")
        if invocation_purpose not in {"standard", "diagnostic", "counterevidence"}:
            raise ValueError("invocation_quota_purpose_invalid")
        if type(invocation_selection_pending) is not bool or (
            invocation_selection_pending and invocation_quota_profile is not None
        ):
            raise ValueError("invocation_quota_selection_invalid")
        if invocation_quota_profile is not None and (
            type(invocation_quota_profile) is not BudgetLedgerInvocationProfile
            or invocation_quota_profile.run_binding != producer_run_binding
        ):
            raise ValueError("invocation_quota_owner_binding_mismatch")
        if (
            invocation_quota_profile is None
            and not invocation_selection_pending
            and invocation_purpose != "standard"
        ):
            raise ValueError("invocation_quota_protected_purpose_not_established")
        self._store = settlement_store
        self._binding = producer_run_binding
        self._state = budget_state
        # This opaque composition binding is not a permit. A higher-layer
        # consumer must independently validate the owner and current scope.
        self._invocation_guard_binding = invocation_guard_binding
        self._invocation_guard_binding_id = (
            id(invocation_guard_binding) if invocation_guard_binding is not None else None
        )
        self._limit = self._current_limit().model_copy(deep=True)
        self._owner, resource = settlement_store._bind_live_producer_resource()
        self._reentry_window: BudgetLedgerReentryBudgetWindow | None = None
        if reentry_budget_scope is not None:
            try:
                window = settlement_store.resolve_reentry_budget_window_safe(reentry_budget_scope)
            except (OSError, ValueError, RuntimeError) as exc:
                raise ProducerBudgetSourceError("reentry_budget_window_not_established") from exc
            if (
                window is None
                or window.ledger_id != self._owner[0]
                or window.resource_identity != resource
                or self._limit.max_usd != window.effective_limit_usd
            ):
                raise ProducerBudgetSourceError("reentry_budget_window_not_established")
            self._reentry_window = window
        self._reconciliation = _live_reconciliation(
            budget_state,
            self._owner,
            resource,
            producer_run_binding,
            self._reentry_window.window_id if self._reentry_window is not None else None,
        )
        self._last_checked: ProducerBudgetObservation | None = None
        self._lock = self._reconciliation.lock
        self._invocation_profile = (
            settlement_store.configure_invocation_profile_safe(invocation_quota_profile)
            if invocation_quota_profile is not None
            else None
        )
        self._invocation_purpose = invocation_purpose
        self._invocation_purpose_context: ContextVar[
            Literal["standard", "diagnostic", "counterevidence"] | None
        ] = ContextVar("n5_invocation_purpose", default=None)
        self._invocation_selection_pending = invocation_selection_pending
        self._invocation_selection_bound = invocation_quota_profile is not None

    @property
    def invocation_guard_binding(self) -> object | None:
        """Return the original opaque physical-invocation composition binding."""
        binding = self._invocation_guard_binding
        if (id(binding) if binding is not None else None) != self._invocation_guard_binding_id:
            raise ProducerBudgetSourceError("invocation_guard_binding_changed")
        return binding

    @property
    def reentry_budget_window(self) -> BudgetLedgerReentryBudgetWindow | None:
        """Return the reopened owner-issued action window, if one was selected."""
        return self._reentry_window

    @property
    def invocation_quota_profile(self) -> BudgetLedgerInvocationProfile | None:
        """Return the selected finite profile, or None when no quota is guaranteed."""
        return self._invocation_profile

    @property
    def invocation_purpose(self) -> Literal["standard", "diagnostic", "counterevidence"]:
        """Return the current owner-selected purpose for this execution context."""
        return self._invocation_purpose_context.get() or self._invocation_purpose

    @property
    def invocation_guarantee(self) -> Literal["no_guarantee", "protected_invocations"]:
        """Disclose whether a protected invocation partition is configured."""
        profile = self._invocation_profile
        return (
            "protected_invocations"
            if profile is not None and profile.protected_units
            else "no_guarantee"
        )

    def _unknown_standard_capacity(self, reason: str) -> BudgetInvocationCapacityObservation:
        return BudgetInvocationCapacityObservation(
            status="not_established",
            predicate_basis="not_established",
            reason_code=reason,
            run_binding=self._binding,
            settlement_owner=self._owner,
            resource_digest=_capacity_resource_digest(self._reconciliation.resource),
        )

    def _capacity_owner_snapshot(
        self,
    ) -> tuple[
        tuple[str, str, str], tuple[int, int, str, int, int], tuple[int, str], BudgetLedgerSnapshot
    ]:
        """Read the exact file owner, refusing shadowed source-boundary methods."""
        return _capacity_store_snapshot(self._store)

    def observe_standard_invocation_capacity(self) -> BudgetInvocationCapacityObservation:
        """Read current standard quota without consuming a unit or granting a permit.

        A zero partition, unavailable profile, or unresolved invocation is not
        promoted to a historical stop. USD and the need for N5 remain separate.
        """
        with self._lock:
            try:
                ProducerBudgetObserver.require_bound_state(self, self._state)
            except ProducerBudgetSourceError:
                return ProducerBudgetObserver._unknown_standard_capacity(
                    self, "budget_state_not_established"
                )
            profile = self._invocation_profile
            if self._invocation_selection_pending or profile is None:
                return ProducerBudgetObserver._unknown_standard_capacity(
                    self, "quota_profile_not_established"
                )
            if self.invocation_purpose != "standard":
                return ProducerBudgetObserver._unknown_standard_capacity(
                    self, "standard_purpose_not_selected"
                )
            standard_limit = profile.total_units - profile.protected_units
            if standard_limit <= 0:
                return ProducerBudgetObserver._unknown_standard_capacity(
                    self, "zero_standard_partition_not_established"
                )
            try:
                if "_capacity_owner_snapshot" in vars(self):
                    raise ValueError("invocation_capacity_source_shadowed")
                owner, resource, anchor, snapshot = ProducerBudgetObserver._capacity_owner_snapshot(
                    self
                )
            except (OSError, RuntimeError, TypeError, ValueError):
                return ProducerBudgetObserver._unknown_standard_capacity(
                    self, "quota_source_not_established"
                )
            if (
                owner != self._owner
                or resource != self._reconciliation.resource
                or type(snapshot) is not BudgetLedgerSnapshot
                or snapshot.revision != anchor[0]
                or snapshot.invocation_profiles.get(self._binding.run_id) != profile
                or (
                    self._reentry_window is not None
                    and snapshot.reentry_budget_windows.get(self._reentry_window.window_id)
                    != self._reentry_window
                )
            ):
                return ProducerBudgetObserver._unknown_standard_capacity(
                    self, "quota_owner_basis_not_established"
                )
            records = tuple(
                record
                for record in snapshot.invocation_reservations.values()
                if record.run_id == self._binding.run_id
            )
            if any(record.status not in {"completed", "failed"} for record in records):
                return ProducerBudgetObserver._unknown_standard_capacity(
                    self, "quota_invocation_unresolved"
                )
            standard = tuple(record for record in records if record.purpose == "standard")
            protected = tuple(record for record in records if record.purpose != "standard")
            remaining = standard_limit - sum(record.units for record in standard)
            protected_remaining = profile.protected_units - sum(
                record.units for record in protected
            )
            if remaining < 0 or protected_remaining < 0:
                return ProducerBudgetObserver._unknown_standard_capacity(
                    self, "quota_capacity_inconsistent"
                )
            return BudgetInvocationCapacityObservation(
                status="exhausted" if remaining == 0 else "available",
                predicate_basis="independently_reconciled",
                run_binding=self._binding,
                settlement_owner=owner,
                resource_digest=_capacity_resource_digest(resource),
                profile_digest=profile.profile_digest,
                standard_limit_units=standard_limit,
                standard_remaining_units=remaining,
                protected_limit_units=profile.protected_units,
                protected_remaining_units=protected_remaining,
                source_revision=anchor[0],
                source_anchor=anchor[1],
                terminal_witnesses=tuple(
                    sorted((record.operation_id, record.revision) for record in standard)
                ),
            )

    def verify_standard_invocation_exhaustion(
        self, witness: BudgetInvocationExhaustionWitness
    ) -> bool:
        """Replay immutable terminal units; no current or future permit is issued.

        The caller must independently bind this witness to its actual
        owner-produced stop artifact. A snapshot hash alone is not provenance.
        """
        checked = _validate_exhaustion_witness(witness)
        with self._lock:
            profile = self._invocation_profile
            if (
                checked.run_binding != self._binding
                or checked.settlement_owner != self._owner
                or checked.resource_digest
                != _capacity_resource_digest(self._reconciliation.resource)
                or self._invocation_selection_pending
                or profile is None
                or self.invocation_purpose != "standard"
                or checked.profile_digest != profile.profile_digest
                or checked.standard_limit_units != profile.total_units - profile.protected_units
            ):
                raise ProducerBudgetSourceError("invocation_exhaustion_basis_mismatch")
            try:
                if "_capacity_owner_snapshot" in vars(self):
                    raise ValueError("invocation_capacity_source_shadowed")
                owner, resource, anchor, snapshot = ProducerBudgetObserver._capacity_owner_snapshot(
                    self
                )
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                raise ProducerBudgetSourceError("invocation_exhaustion_source_unavailable") from exc
            if (
                owner != self._owner
                or resource != self._reconciliation.resource
                or type(snapshot) is not BudgetLedgerSnapshot
                or snapshot.invocation_profiles.get(self._binding.run_id) != profile
                or anchor[0] < checked.source_revision
                or (
                    self._reentry_window is not None
                    and snapshot.reentry_budget_windows.get(self._reentry_window.window_id)
                    != self._reentry_window
                )
            ):
                raise ProducerBudgetSourceError("invocation_exhaustion_owner_mismatch")
            _verify_exhaustion_terminal_records(snapshot, profile, checked)
            return True

    def bind_invocation_policy_from_selected_owner(
        self,
        policy: BudgetInvocationQuotaPolicy | None,
        *,
        purpose: Literal["standard", "diagnostic", "counterevidence"] = "standard",
    ) -> BudgetLedgerInvocationProfile | None:
        """Bind the actual resolved owner's policy before any physical admission.

        None declares that this owner selected no finite allocation; it cannot
        replace a profile already adopted for the run. Repeating an identical
        selection is idempotent; selecting a different policy or purpose fails.
        """
        if policy is not None and type(policy) is not BudgetInvocationQuotaPolicy:
            raise TypeError("invocation_quota_policy_untyped")
        if purpose not in {"standard", "diagnostic", "counterevidence"}:
            raise ValueError("invocation_quota_purpose_invalid")
        if policy is None and purpose != "standard":
            raise ProducerBudgetSourceError("n5_protected_purpose_not_established")
        profile = (
            BudgetLedgerInvocationProfile.from_policy(self._binding, policy)
            if policy is not None
            else None
        )
        with self._lock:
            if self._invocation_selection_bound:
                if profile != self._invocation_profile or purpose != self._invocation_purpose:
                    raise ProducerBudgetSourceError("n5_invocation_selection_conflict")
                return self._invocation_profile
            try:
                if profile is None:
                    self._store.select_unconfigured_invocations_safe(self._binding)
                else:
                    profile = self._store.configure_invocation_profile_safe(profile)
            except (OSError, ValueError, RuntimeError) as exc:
                raise ProducerBudgetSourceError("n5_invocation_selection_failed") from exc
            self._invocation_profile = profile
            self._invocation_purpose = purpose
            self._invocation_selection_bound = True
            self._invocation_selection_pending = False
            return profile

    @contextmanager
    def invocation_purpose_scope_from_selected_owner(
        self,
        policy: BudgetInvocationQuotaPolicy | None,
        *,
        purpose: Literal["standard", "diagnostic", "counterevidence"],
    ) -> Iterator[None]:
        """Scope the owner's purpose to one execution context and selected policy.

        The lifecycle owner must verify the selected policy and purpose before
        entering. This scope is not evidence of external authorization.
        """
        if policy is not None and type(policy) is not BudgetInvocationQuotaPolicy:
            raise TypeError("invocation_quota_policy_untyped")
        if purpose not in {"standard", "diagnostic", "counterevidence"}:
            raise ValueError("invocation_quota_purpose_invalid")
        with self._lock:
            if self._invocation_selection_pending or not self._invocation_selection_bound:
                raise ProducerBudgetSourceError("n5_invocation_selection_not_established")
            selected = (
                BudgetLedgerInvocationProfile.from_policy(self._binding, policy)
                if policy is not None
                else None
            )
            if selected != self._invocation_profile:
                raise ProducerBudgetSourceError("n5_invocation_selection_conflict")
            if selected is None and purpose != "standard":
                raise ProducerBudgetSourceError("n5_protected_purpose_not_established")
        token = self._invocation_purpose_context.set(purpose)
        try:
            yield
        finally:
            self._invocation_purpose_context.reset(token)

    def reserve_invocation(
        self, operation_id: str, request_digest: str
    ) -> BudgetLedgerInvocationReservation | None:
        """Reserve one unique physical call; duplicate IDs never grant re-execution."""
        with self._lock:
            self.require_bound_state(self._state)
            if self._invocation_selection_pending:
                raise ProducerBudgetSourceError("n5_invocation_selection_pending")
            profile = self._invocation_profile
            try:
                if profile is None:
                    if self.invocation_purpose != "standard":
                        raise ProducerBudgetSourceError("n5_protected_purpose_not_established")
                    self._store.select_unconfigured_invocations_safe(self._binding)
                    self._invocation_selection_bound = True
                    return None
                record, created = self._store.reserve_invocation_safe(
                    operation_id,
                    request_digest,
                    profile=profile,
                    purpose=self.invocation_purpose,
                )
            except BudgetLedgerInvocationQuotaExhaustedError as exc:
                raise BudgetExhaustedError("configured N5 invocation allocation exhausted") from exc
            except (OSError, ValueError, RuntimeError) as exc:
                raise ProducerBudgetSourceError("n5_invocation_quota_admission_failed") from exc
            if not created:
                raise ProducerBudgetSourceError("n5_invocation_already_issued")
            return record

    def finish_invocation(
        self,
        operation_id: str,
        request_digest: str,
        outcome: Literal["completed", "failed", "unknown"],
    ) -> None:
        """Retain a terminal outcome; failed or uncertain calls remain counted."""
        profile = self._invocation_profile
        if profile is None:
            return
        with self._lock:
            try:
                self._store.finish_invocation_safe(
                    operation_id, request_digest, profile=profile, outcome=outcome
                )
            except (OSError, ValueError, RuntimeError) as exc:
                raise ProducerBudgetSourceError("n5_invocation_outcome_unresolved") from exc

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
            if (
                self._reentry_window is not None
                and snapshot.reentry_budget_windows.get(self._reentry_window.window_id)
                != self._reentry_window
            ):
                raise ProducerBudgetSourceError("reentry_budget_window_changed")
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
                total = _add_budget_amount(total, amount, exact=self._reentry_window is not None)
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
            exact_window = self._reentry_window is not None
            allocation = _add_budget_amount(
                spent, self._reconciliation.last_reconciled_total.copy_negate(), exact=exact_window
            )
            _amount(allocation, "control_nl_budget_state_spend_basis_invalid")
            reserved = _amount(
                self._state.reserved.get("run", Decimal(0)),
                "control_nl_budget_state_reserved_not_established",
            )
            total_allocated = _add_budget_amount(allocation, total, exact=exact_window)
            remaining = _add_budget_amount(
                _add_budget_amount(
                    self._limit.max_usd, total_allocated.copy_negate(), exact=exact_window
                ),
                reserved.copy_negate(),
                exact=exact_window,
            )
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
            self._reconciliation.last_reconciled_total = total
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
