"""File-backed budget ledger for distributed-safe Scientist budget accounting."""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import stat
import tempfile
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, Inexact, localcontext
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import errors as core_errors
from polisyos.core.canon import CanonSpec, content_hash, to_canonical_bytes
from polisyos.core.llm.cache_settlement import CacheSettlementSession
from polisyos.core.llm.settlement import LLMProducerEvent
from polisyos.scientist.orchestration.engine.budget import BudgetState

_CANONICAL_LEDGER_CONTRACT = "scientist.multi_host_budget_ledger.v1"
_COORDINATION_MODE = "shared_posix_file_lock"
_SNAPSHOT_VERSION = "1.8"
_ENGINE_EVENT_PREFIX = "scientist.engine-invocation:"
_LEDGER_THREAD_GATES = tuple(threading.RLock() for _ in range(64))

type _BudgetResourceIdentity = tuple[int, int, str, int, int]
type _BudgetSnapshotAnchor = tuple[int, str]

__all__ = [
    "BudgetLedger",
    "BudgetLedgerMutation",
    "BudgetLedgerMutationResult",
    "BudgetLedgerSnapshot",
    "BudgetLedgerComputeReservation",
    "BudgetInvocationQuotaPolicy",
    "BudgetLedgerInvocationProfile",
    "BudgetLedgerInvocationReservation",
    "BudgetLedgerInvocationQuotaExhaustedError",
    "BudgetLedgerReentryBudgetScope",
    "BudgetLedgerReentryBudgetWindow",
    "BudgetLedgerWriter",
    "BudgetLedgerSpendReceipt",
    "BudgetLedgerProducerRecord",
    "BudgetLedgerCacheReuseAdmission",
    "BudgetLedgerProducerRunBinding",
    "BudgetLedgerSettlementOutcomeUnknownError",
    "FileBudgetLedger",
]


class BudgetLedgerWriter(BaseModel):
    """Identity of the process or host that last mutated the ledger."""

    model_config = ConfigDict(extra="forbid")

    host_id: str = Field(min_length=1)
    writer_id: str = Field(min_length=1)
    pid: int = Field(ge=0)


class BudgetLedgerMutation(BaseModel):
    """Bounded mutation journal entry for the canonical ledger contract."""

    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=0)
    operation: Literal[
        "bootstrap",
        "record_spend",
        "reserve",
        "release",
        "commit_reservation",
        "settle_spend",
        "begin_producer_event",
        "settle_producer_event",
        "reserve_compute",
        "settle_compute",
        "mark_compute_unknown",
        "configure_invocation_quota",
        "select_unconfigured_invocation_quota",
        "open_reentry_budget_window",
        "reserve_invocation",
        "finish_invocation",
    ]
    key: str | None = None
    amount: Decimal | None = None
    applied_amount: Decimal | None = None
    provider: str | None = None
    reserved: bool | None = None
    writer: BudgetLedgerWriter
    committed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BudgetLedgerSpendReceipt(BaseModel):
    """Durable local accounting acknowledgment for one producer settlement event.

    This binds an observed producer payload to one local charge. It does not
    certify external billing authority or supply permission to run new work.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    key: str = Field(min_length=1)
    amount: Decimal = Field(ge=0, allow_inf_nan=False)
    provider: str | None = None
    revision: int = Field(ge=1)
    committed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BudgetLedgerProducerRunBinding(BaseModel):
    """Immutable server-issued run scope used to reconcile producer events."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.scientist.budget_ledger.producer_run_binding.v1"] = (
        "polisyos.scientist.budget_ledger.producer_run_binding.v1"
    )
    run_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    control_job_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _require_established_identity(self) -> BudgetLedgerProducerRunBinding:
        values = (
            self.run_id,
            self.tenant_id,
            self.cell_id,
            self.profile_id,
            self.control_job_id,
        )
        if any(
            not value.strip()
            or value != value.strip()
            or value.casefold() in {"unknown", "none", "null", "anonymous"}
            for value in values
        ):
            raise ValueError("producer_run_binding_identity_not_established")
        return self


class BudgetLedgerCacheReuseAdmission(BaseModel):
    """Frozen local admission of an exact authorized cache edge across runs.

    This is an accounting observation by the ledger, not external permission.
    Only the live Core response verifier can create it at a new write; readers
    recheck its exact source/receiver graph bindings without reissuing the source.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    verifier: Literal["core.cache_settlement.response.v1"] = "core.cache_settlement.response.v1"
    cache_key: str = Field(min_length=1)
    response_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    scope_key: tuple[str, ...] = Field(min_length=10)

    @property
    def issuer(self) -> str:
        """Return the configured authorizer issuer frozen by Core."""
        return self.scope_key[0]

    @property
    def epoch(self) -> str:
        """Return its exact permission epoch at admission."""
        return self.scope_key[1]

    def validate_edge(
        self, receiver: BudgetLedgerProducerRecord, source: BudgetLedgerProducerRecord
    ) -> None:
        """Recompute cache identity and both physical/reuse payload digests."""
        scope = self.scope_key
        if (
            any(
                not scope[index] or scope[index] != scope[index].strip()
                for index in (*range(6), 7, 8)
            )
            or scope[7] != receiver.model
            or scope[8] != receiver.request_digest
        ):
            raise ValueError("producer_reuse_admission_scope_mismatch")
        expected_key = hashlib.sha256(
            json.dumps(
                [receiver.request_digest, scope, receiver.request_digest],
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        if self.cache_key != expected_key:
            raise ValueError("producer_reuse_admission_cache_key_mismatch")
        for record in (source, receiver):
            event = LLMProducerEvent(
                event_id=record.event_id,
                request_digest=record.request_digest,
                response_digest=self.response_digest,
                model=record.model,
                provider=record.provider,
                amount=record.amount,
                cost_origin=record.cost_origin,
                kind="provider" if record is source else "reuse",
                origin_event_id=record.origin_event_id,
            )
            if event.payload_digest != record.payload_digest:
                raise ValueError("producer_reuse_origin_cross_run_payload_mismatch")


def _verified_cache_reuse_admission(
    *,
    session: CacheSettlementSession | None,
    response: object | None,
    event_id: str,
    request_digest: str,
    payload_digest: str,
    origin_event_id: str | None,
    model: str,
    provider: str,
) -> BudgetLedgerCacheReuseAdmission | None:
    """Resolve the opaque Core proof and bind all current event payload fields."""
    if session is None and response is None:
        return None
    if type(session) is not CacheSettlementSession or response is None:
        raise ValueError("producer_reuse_admission_missing_core_response")
    proof = getattr(response, "_polisyos_reuse_provenance", None)
    evidence = session.verify_reuse_attestation(proof, response)
    if evidence is None:
        raise ValueError("producer_reuse_admission_invalid_core_response")
    scope = evidence.scope_key
    if (
        evidence.reuse_event_id != event_id
        or evidence.request_digest != request_digest
        or evidence.origin_event_id != origin_event_id
    ):
        raise ValueError("producer_reuse_admission_event_mismatch")
    event = LLMProducerEvent(
        event_id=event_id,
        request_digest=request_digest,
        response_digest=evidence.response_digest,
        model=model,
        provider=provider,
        amount=Decimal(0),
        cost_origin="reuse",
        kind="reuse",
        origin_event_id=origin_event_id,
    )
    if event.payload_digest != payload_digest:
        raise ValueError("producer_reuse_admission_payload_mismatch")
    # Ordinary same-run cache reuse still uses the original ledger contract.
    # Only a current authorizer decision can widen it across run boundaries.
    if len(scope) < 10 or scope[7] != model or scope[8] != request_digest:
        return None
    return BudgetLedgerCacheReuseAdmission(
        cache_key=evidence.cache_key,
        response_digest=evidence.response_digest,
        scope_key=scope,
    )


class BudgetLedgerProducerRecord(BaseModel):
    """Durable state of one provider outcome, including unresolved attempts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    payload_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    key: str = Field(min_length=1)
    model: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    amount: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    cost_origin: Literal["reported", "estimated", "reuse", "unknown"] = "unknown"
    status: Literal["pending", "committed", "unknown", "unmanaged"] = "pending"
    origin_event_id: str | None = None
    run_binding: BudgetLedgerProducerRunBinding | None = Field(
        default=None,
        json_schema_extra={"introduced_in": "1.3"},
    )
    control_job_attempt: int | None = Field(
        default=None,
        ge=1,
        strict=True,
        json_schema_extra={"introduced_in": "1.4"},
    )
    pre_admission_attempt_id: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{32}$",
        json_schema_extra={"introduced_in": "1.4"},
    )
    reuse_admission: BudgetLedgerCacheReuseAdmission | None = Field(
        default=None, json_schema_extra={"introduced_in": "1.5"}
    )
    revision: int = Field(ge=1)
    committed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def model_post_init(self, __context: Any) -> None:
        if self.status == "pending" and (
            self.payload_digest is not None or self.amount is not None
        ):
            raise ValueError("pending producer event cannot claim a response or amount")
        if self.cost_origin == "unknown" and self.amount is not None:
            raise ValueError("unknown producer cost cannot carry an amount")
        if self.amount is None and self.cost_origin != "unknown":
            raise ValueError("missing producer amount must retain unknown cost origin")
        if self.status == "committed" and self.amount is None:
            raise ValueError("committed producer outcome requires a known amount")
        if self.status in {"unknown", "committed"} and self.payload_digest is None:
            raise ValueError("settled producer outcome requires a response digest")
        if self.cost_origin == "reuse":
            if (
                self.status != "committed"
                or self.amount != Decimal(0)
                or not self.origin_event_id
                or not self.origin_event_id.strip()
            ):
                raise ValueError("producer_reuse_origin_invalid")
        elif self.origin_event_id is not None or self.reuse_admission is not None:
            raise ValueError("producer_reuse_origin_unexpected")
        if self.run_binding is not None and self.key != f"nl-run:{self.run_binding.run_id}":
            raise ValueError("producer_run_binding_budget_key_mismatch")
        if self.control_job_attempt is not None and self.pre_admission_attempt_id is not None:
            raise ValueError("producer_attempt_attribution_is_ambiguous")

    def validate_reuse_origin(self, source: BudgetLedgerProducerRecord | None) -> None:
        """Reconcile the exact physical source under the canonical ledger contract."""
        self._validate_new_settlement_origin(source)

    def _validate_new_settlement_origin(
        self,
        source: BudgetLedgerProducerRecord | None,
    ) -> None:
        """Require a new reuse write to bind an exact committed source in this ledger."""
        if self.cost_origin != "reuse":
            if self.origin_event_id is not None:
                raise ValueError("producer_reuse_origin_unexpected")
            return
        if (
            self.status != "committed"
            or self.amount != Decimal(0)
            or not self.origin_event_id
            or not self.origin_event_id.strip()
        ):
            raise ValueError("producer_reuse_origin_invalid")
        if source is None or source.event_id != self.origin_event_id:
            raise ValueError("producer_reuse_origin_missing")
        source_has_known_physical_cost = (
            source.status == "committed"
            and source.cost_origin in {"reported", "estimated"}
            and source.amount is not None
            and source.amount.is_finite()
            and source.amount >= Decimal(0)
        )
        source_has_terminal_unknown_cost = (
            source.status == "unknown" and source.cost_origin == "unknown" and source.amount is None
        )
        if (
            source.event_id == self.event_id
            or not (source_has_known_physical_cost or source_has_terminal_unknown_cost)
            or source.payload_digest is None
            or source.origin_event_id is not None
            or source.request_digest != self.request_digest
            or source.model != self.model
            or source.provider != self.provider
        ):
            raise ValueError("producer_reuse_origin_mismatch")
        admission = self.reuse_admission
        if admission is not None:
            admission.validate_edge(self, source)
        if source.key == self.key and source.run_binding == self.run_binding:
            return
        source_binding, receiver_binding = source.run_binding, self.run_binding
        if (
            admission is None
            or source_binding is None
            or receiver_binding is None
            or (source_binding.tenant_id, source_binding.cell_id, source_binding.profile_id)
            != (receiver_binding.tenant_id, receiver_binding.cell_id, receiver_binding.profile_id)
            or admission.scope_key[3] != receiver_binding.tenant_id
            or admission.scope_key[4] != f"{receiver_binding.tenant_id}/{receiver_binding.cell_id}"
        ):
            raise ValueError("producer_reuse_origin_cross_run_admission_missing")


def _validate_producer_settlement_origin_graph(
    records: dict[str, BudgetLedgerProducerRecord],
) -> None:
    """Require every reuse edge to resolve to its same-request physical source."""
    for event_id, record in records.items():
        if record.event_id != event_id:
            raise ValueError("producer settlement identity disagrees with snapshot")
        source = records.get(record.origin_event_id) if record.origin_event_id is not None else None
        record._validate_new_settlement_origin(source)


class BudgetLedgerSettlementOutcomeUnknownError(RuntimeError):
    """A filesystem publication failed without establishing charge acknowledgment."""

    # Fatal means a retry dispatcher must not repeat a potentially executed
    # effect. It does not assert that the settlement itself failed.
    default_category = core_errors.ErrorCategory.FATAL
    code = "node.budget_settlement_outcome_unknown"

    def __init__(self, event_id: str, payload_digest: str) -> None:
        self.event_id = event_id
        self.payload_digest = payload_digest
        super().__init__(
            f"budget settlement outcome unknown for event {event_id!r}; "
            "resolve or retry the same event before assuming any charge outcome"
        )


class BudgetLedgerInvocationQuotaExhaustedError(ValueError):
    """The selected physical-invocation allocation has no unit for this purpose."""


class BudgetLedgerComputeReservation(BaseModel):
    """One durable, identified compute reservation and its eventual actual charge."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    event_id: str = Field(min_length=1)
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    key: str = Field(min_length=1)
    reserved_amount: Decimal
    status: Literal["reserved", "unknown", "settled"]
    actual_amount: Decimal | None = None
    settlement_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    revision: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_status(self) -> BudgetLedgerComputeReservation:
        if not self.reserved_amount.is_finite() or self.reserved_amount <= 0:
            raise ValueError("compute_reservation_amount_must_be_positive_and_finite")
        if self.status in {"reserved", "unknown"} and (
            self.actual_amount is not None or self.settlement_digest is not None
        ):
            raise ValueError("compute_reservation_pending_has_settlement")
        if self.status == "settled" and (
            self.actual_amount is None
            or not self.actual_amount.is_finite()
            or self.actual_amount < 0
            or self.settlement_digest is None
        ):
            raise ValueError("compute_reservation_settlement_incomplete")
        return self


class BudgetInvocationQuotaPolicy(BaseModel):
    """Owner-selected finite allocation of physical N5 invocation units.

    The protected portion is shared by diagnostic and counterevidence work.
    It is a count of physical calls, not a USD price or a calibration claim.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["scientist.n5_invocation_quota.v1"] = "scientist.n5_invocation_quota.v1"
    allocation_id: str = Field(min_length=1, max_length=160)
    total_units: int = Field(ge=0, strict=True)
    protected_units: int = Field(ge=0, strict=True)
    work_unit: Literal["n5_physical_invocation"] = "n5_physical_invocation"
    price_origin: Literal["unknown"] = "unknown"

    @model_validator(mode="after")
    def _validate_allocation(self) -> BudgetInvocationQuotaPolicy:
        if self.allocation_id != self.allocation_id.strip():
            raise ValueError("invocation_quota_allocation_id_invalid")
        if self.protected_units > self.total_units:
            raise ValueError("invocation_quota_protected_exceeds_total")
        return self


class BudgetLedgerInvocationProfile(BudgetInvocationQuotaPolicy):
    """A finite policy bound to the actual server-issued run owner."""

    run_binding: BudgetLedgerProducerRunBinding

    @classmethod
    def from_policy(
        cls, run_binding: BudgetLedgerProducerRunBinding, policy: BudgetInvocationQuotaPolicy
    ) -> BudgetLedgerInvocationProfile:
        """Bind an owner-selected policy to this actual run without inventing scope."""
        if type(policy) is not BudgetInvocationQuotaPolicy:
            raise TypeError("invocation_quota_policy_untyped")
        if type(run_binding) is not BudgetLedgerProducerRunBinding:
            raise TypeError("invocation_quota_run_binding_untyped")
        return cls(**policy.model_dump(mode="python"), run_binding=run_binding)

    @property
    def profile_digest(self) -> str:
        """Hash the complete versioned profile, including owner and unit basis."""
        return content_hash(to_canonical_bytes(self.model_dump(mode="json")))


class BudgetLedgerInvocationReservation(BaseModel):
    """One admitted invocation, counted even if its outcome remains unknown."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    run_id: str = Field(min_length=1)
    profile_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    purpose: Literal["standard", "diagnostic", "counterevidence"]
    units: int = Field(default=1, ge=1, le=1, strict=True)
    status: Literal["reserved", "completed", "failed", "unknown"] = "reserved"
    revision: int = Field(ge=1)


class BudgetLedgerReentryBudgetScope(BaseModel):
    """Owner-selected acquisition action that receives one fresh USD window."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_binding: BudgetLedgerProducerRunBinding
    action_job_id: str = Field(min_length=1)
    route_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    action_generation: int = Field(ge=1, strict=True)
    action_phase_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_payload_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    profile_selection_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_action_id(self) -> BudgetLedgerReentryBudgetScope:
        if not self.action_job_id.strip() or self.action_job_id != self.action_job_id.strip():
            raise ValueError("reentry_budget_action_job_invalid")
        return self

    @property
    def window_id(self) -> str:
        """Keep one identity across phase or attempt changes within this action."""
        return content_hash(
            to_canonical_bytes(
                {
                    "run_binding": self.run_binding.model_dump(mode="json"),
                    "action_job_id": self.action_job_id,
                    "route_id": self.route_id,
                    "action_generation": self.action_generation,
                }
            )
        )


class BudgetLedgerReentryBudgetWindow(BaseModel):
    """Immutable owner-observed starting point for a bounded reentry allocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["scientist.reentry_budget_window.v1"] = (
        "scientist.reentry_budget_window.v1"
    )
    scope: BudgetLedgerReentryBudgetScope
    ledger_id: str = Field(min_length=1)
    resource_identity: tuple[int, int, str, int, int]
    fresh_limit_usd: Decimal = Field(gt=0, allow_inf_nan=False)
    global_limit_usd: Decimal = Field(ge=0, allow_inf_nan=False)
    baseline_total_usd: Decimal = Field(ge=0, allow_inf_nan=False)
    baseline_revision: int = Field(ge=0)
    baseline_prefix_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision: int = Field(ge=1)

    @property
    def window_id(self) -> str:
        """Return the stable action identity, independent of retry attempt."""
        return self.scope.window_id

    @property
    def record_digest(self) -> str:
        """Identify the complete original owner-issued record for action custody."""
        return content_hash(to_canonical_bytes(self.model_dump(mode="json")))

    @property
    def effective_limit_usd(self) -> Decimal:
        """Bound the full-run total by both global and fresh-window limits."""
        if self.global_limit_usd <= self.baseline_total_usd:
            return self.global_limit_usd
        return min(
            self.global_limit_usd, _reentry_add(self.baseline_total_usd, self.fresh_limit_usd)
        )


class BudgetLedgerSnapshot(BaseModel):
    """Persisted budget ledger state."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=_SNAPSHOT_VERSION, pattern=r"^\d+\.\d+$")
    canonical_contract: str = Field(default=_CANONICAL_LEDGER_CONTRACT, min_length=1)
    coordination_mode: str = Field(default=_COORDINATION_MODE, min_length=1)
    ledger_id: str | None = None
    revision: int = Field(default=0, ge=0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_writer: BudgetLedgerWriter | None = None
    recent_mutations: list[BudgetLedgerMutation] = Field(default_factory=list)
    state: BudgetState = Field(default_factory=BudgetState)
    spend_receipts: dict[str, BudgetLedgerSpendReceipt] = Field(
        default_factory=dict, json_schema_extra={"introduced_in": "1.1"}
    )
    producer_settlements: dict[str, BudgetLedgerProducerRecord] = Field(
        default_factory=dict, json_schema_extra={"introduced_in": "1.2"}
    )
    # Legacy pre-1.6 snapshots have no identified compute reservation records.
    compute_reservations: dict[str, BudgetLedgerComputeReservation] = Field(
        default_factory=dict, json_schema_extra={"introduced_in": "1.6"}
    )
    invocation_profiles: dict[str, BudgetLedgerInvocationProfile] = Field(
        default_factory=dict, json_schema_extra={"introduced_in": "1.7"}
    )
    invocation_unconfigured_runs: dict[str, BudgetLedgerProducerRunBinding] = Field(
        default_factory=dict, json_schema_extra={"introduced_in": "1.7"}
    )
    invocation_reservations: dict[str, BudgetLedgerInvocationReservation] = Field(
        default_factory=dict, json_schema_extra={"introduced_in": "1.7"}
    )
    reentry_budget_windows: dict[str, BudgetLedgerReentryBudgetWindow] = Field(
        default_factory=dict, json_schema_extra={"introduced_in": "1.8"}
    )


def _reentry_add(left: Decimal, right: Decimal) -> Decimal:
    """Refuse rather than silently round a USD admission calculation."""
    try:
        with localcontext() as context:
            context.traps[Inexact] = True
            return left + right
    except ArithmeticError as exc:
        raise ValueError("reentry_budget_arithmetic_not_established") from exc


def _reentry_prefix(
    snapshot: BudgetLedgerSnapshot,
    binding: BudgetLedgerProducerRunBinding,
    *,
    cutoff: int | None,
) -> tuple[Decimal, str]:
    """Recompute one exact known-cost run prefix from the durable producer owner."""
    key = f"nl-run:{binding.run_id}"
    records = sorted(
        (
            record
            for record in snapshot.producer_settlements.values()
            if (record.key == key or record.run_binding == binding)
            and (cutoff is None or record.revision <= cutoff)
        ),
        key=lambda record: record.event_id,
    )
    if not records:
        raise ValueError("reentry_budget_producer_prefix_not_established")
    total = Decimal(0)
    for record in records:
        if record.key != key or record.run_binding != binding:
            raise ValueError("reentry_budget_producer_binding_mismatch")
        if (
            record.status != "committed"
            or record.amount is None
            or not record.amount.is_finite()
            or record.amount < 0
            or record.payload_digest is None
            or record.cost_origin not in {"reported", "estimated", "reuse"}
        ):
            raise ValueError("reentry_budget_producer_outcome_not_established")
        if record.cost_origin == "reuse":
            record.validate_reuse_origin(
                snapshot.producer_settlements.get(record.origin_event_id or "")
            )
        total = _reentry_add(total, record.amount)
        if not total.is_finite():
            raise ValueError("reentry_budget_producer_total_invalid")
    digest = content_hash(
        to_canonical_bytes([record.model_dump(mode="json") for record in records])
    )
    return total, digest


def _same_reentry_action_basis(
    first: BudgetLedgerReentryBudgetScope, current: BudgetLedgerReentryBudgetScope
) -> bool:
    """The action owner separately verifies phase ancestry across attempts."""
    return (
        first.window_id == current.window_id
        and first.source_payload_ref == current.source_payload_ref
        and first.profile_selection_ref == current.profile_selection_ref
    )


def _reentry_limit_identity(value: Decimal) -> str:
    """Canonicalize a finite Decimal without context-dependent rounding."""
    sign, digits, exponent = value.as_tuple()
    significant = list(digits)
    if not any(significant):
        return "0"
    while significant[-1] == 0:
        significant.pop()
        exponent += 1
    return f"{sign}:{''.join(str(digit) for digit in significant)}:{exponent}"


@dataclass
class _LockedEventOutcome:
    """Track only the event whose acknowledgment depends on this lock."""

    event_id: str
    payload_digest: str
    published_snapshot: BudgetLedgerSnapshot | None = None
    acknowledged: bool = False


_PERSISTED_SNAPSHOT_SCHEMA = BudgetLedgerSnapshot.model_json_schema(mode="serialization")


def _require_wire_fields(
    value: object,
    schema: dict[str, Any],
    definitions: dict[str, Any],
    *,
    location: str = "snapshot",
    version: str = _SNAPSHOT_VERSION,
) -> None:
    """Require non-nullable writer fields before constructor defaults can apply."""
    if "$ref" in schema:
        schema = definitions[schema["$ref"].rsplit("/", 1)[1]]
    alternatives = schema.get("anyOf", [])
    if alternatives:
        schema = next((item for item in alternatives if item.get("type") != "null"), schema)
        if "$ref" in schema:
            schema = definitions[schema["$ref"].rsplit("/", 1)[1]]
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for name, field_schema in properties.items():
            nullable = any(item.get("type") == "null" for item in field_schema.get("anyOf", []))
            introduced = field_schema.get("introduced_in", "1.0")
            required_in_version = tuple(map(int, introduced.split("."))) <= tuple(
                map(int, version.split("."))
            )
            if name not in value and not nullable and required_in_version:
                raise ValueError(f"incomplete budget ledger: missing {location}.{name}")
        for name, item in value.items():
            field_schema = properties.get(name, schema.get("additionalProperties", {}))
            if isinstance(field_schema, dict):
                _require_wire_fields(
                    item, field_schema, definitions, location=f"{location}.{name}", version=version
                )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _require_wire_fields(
                item,
                schema.get("items", {}),
                definitions,
                location=f"{location}[{index}]",
                version=version,
            )


def _require_nonnegative_amounts(value: object) -> None:
    """Reject nonfinite or negative accounting amounts in a persisted snapshot."""
    if isinstance(value, Decimal):
        if not value.is_finite() or value < 0:
            raise ValueError("budget ledger accounting amounts must be finite and nonnegative")
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            _require_nonnegative_amounts(getattr(value, name))
    elif isinstance(value, dict):
        for item in value.values():
            _require_nonnegative_amounts(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _require_nonnegative_amounts(item)


def decode_budget_ledger_snapshot(raw: bytes) -> BudgetLedgerSnapshot:
    """Decode and validate the exact persisted ledger bytes.

    Args:
        raw: Complete UTF-8 ledger snapshot bytes.

    Returns:
        The validated persisted snapshot.
    """
    return _decode_snapshot(raw.decode("utf-8"))


def _decode_snapshot(raw: str) -> BudgetLedgerSnapshot:
    """Decode complete persisted wire data without treating corruption as defaults."""
    if not raw.strip():
        raise ValueError("existing budget ledger is empty")
    value = json.loads(raw)
    version = value.get("schema_version") if isinstance(value, dict) else None
    if not isinstance(version, str) or version not in {
        "1.0",
        "1.1",
        "1.2",
        "1.3",
        "1.4",
        "1.5",
        "1.6",
        "1.7",
        _SNAPSHOT_VERSION,
    }:
        raise ValueError("budget ledger schema_version is missing or unsupported")
    if (
        value.get("canonical_contract") != _CANONICAL_LEDGER_CONTRACT
        or value.get("coordination_mode") != _COORDINATION_MODE
    ):
        raise ValueError("budget ledger contract or coordination mode is unsupported")
    if version not in {"1.7", _SNAPSHOT_VERSION} and (
        value.get("invocation_profiles")
        or value.get("invocation_unconfigured_runs")
        or value.get("invocation_reservations")
    ):
        raise ValueError("budget_ledger_invocation_fields_require_version_1_7")
    if version != _SNAPSHOT_VERSION and value.get("reentry_budget_windows"):
        raise ValueError("budget_ledger_reentry_windows_require_version_1_8")
    _require_wire_fields(
        value,
        _PERSISTED_SNAPSHOT_SCHEMA,
        _PERSISTED_SNAPSHOT_SCHEMA.get("$defs", {}),
        version=version,
    )
    snapshot = BudgetLedgerSnapshot.model_validate_json(raw, strict=True)
    if snapshot.ledger_id is not None and not snapshot.ledger_id.strip():
        raise ValueError("budget_ledger_identity_invalid")
    _require_nonnegative_amounts(snapshot)
    amounts: dict[str, Decimal] = {}
    provider_amounts: dict[str, Decimal] = {}
    for event_id, receipt in snapshot.spend_receipts.items():
        if receipt.event_id != event_id or receipt.revision > snapshot.revision:
            raise ValueError("budget settlement receipt identity/revision disagrees with snapshot")
        amounts[receipt.key] = amounts.get(receipt.key, Decimal("0")) + receipt.amount
        if receipt.provider is not None:
            provider_amounts[receipt.provider] = (
                provider_amounts.get(receipt.provider, Decimal("0")) + receipt.amount
            )
    for event_id, record in snapshot.producer_settlements.items():
        if record.event_id != event_id or record.revision > snapshot.revision:
            raise ValueError("producer settlement identity/revision disagrees with snapshot")
        receipt = snapshot.spend_receipts.get(event_id)
        if record.status == "committed":
            if (
                receipt is None
                or receipt.amount != record.amount
                or receipt.key != record.key
                or receipt.provider != record.provider
            ):
                raise ValueError("committed producer outcome requires its exact spend receipt")
            if receipt.payload_digest != record.payload_digest:
                raise ValueError("producer settlement and spend receipt digest disagree")
    identified_reserved: dict[str, Decimal] = {}
    for event_id, record in (snapshot.compute_reservations or {}).items():
        if record.event_id != event_id or record.revision > snapshot.revision:
            raise ValueError("compute reservation identity/revision disagrees with snapshot")
        if event_id in snapshot.producer_settlements:
            raise ValueError("compute reservation conflicts with producer event")
        receipt = snapshot.spend_receipts.get(event_id)
        if record.status in {"reserved", "unknown"}:
            if receipt is not None:
                raise ValueError("pending compute reservation already has spend receipt")
            identified_reserved[record.key] = (
                identified_reserved.get(record.key, Decimal(0)) + record.reserved_amount
            )
        elif (
            receipt is None
            or receipt.key != record.key
            or receipt.amount != record.actual_amount
            or receipt.payload_digest != record.settlement_digest
        ):
            raise ValueError("settled compute reservation requires exact spend receipt")
    for key, amount in identified_reserved.items():
        if snapshot.state.reserved.get(key, Decimal(0)) < amount:
            raise ValueError("identified reservations exceed aggregate reserved amount")
    invocation_usage: dict[str, tuple[int, int]] = {}
    for run_id, profile in snapshot.invocation_profiles.items():
        if run_id != profile.run_binding.run_id:
            raise ValueError("invocation_quota_run_binding_mismatch")
        if run_id in snapshot.invocation_unconfigured_runs:
            raise ValueError("invocation_quota_mode_conflict")
    for run_id, binding in snapshot.invocation_unconfigured_runs.items():
        if run_id != binding.run_id:
            raise ValueError("invocation_quota_run_binding_mismatch")
    for operation_id, record in snapshot.invocation_reservations.items():
        profile = snapshot.invocation_profiles.get(record.run_id)
        if (
            operation_id != record.operation_id
            or record.revision > snapshot.revision
            or profile is None
            or record.profile_digest != profile.profile_digest
        ):
            raise ValueError("invocation_reservation_identity_mismatch")
        standard, protected = invocation_usage.get(record.run_id, (0, 0))
        if record.purpose == "standard":
            standard += record.units
        else:
            protected += record.units
        if standard > profile.total_units - profile.protected_units:
            raise ValueError("invocation_quota_standard_exceeded")
        if protected > profile.protected_units:
            raise ValueError("invocation_quota_protected_exceeded")
        invocation_usage[record.run_id] = (standard, protected)
    for window_id, window in snapshot.reentry_budget_windows.items():
        if (
            window_id != window.window_id
            or window.ledger_id != snapshot.ledger_id
            or window.revision > snapshot.revision
            or window.baseline_revision >= window.revision
        ):
            raise ValueError("reentry_budget_window_identity_mismatch")
        total, digest = _reentry_prefix(
            snapshot, window.scope.run_binding, cutoff=window.baseline_revision
        )
        if total != window.baseline_total_usd or digest != window.baseline_prefix_digest:
            raise ValueError("reentry_budget_window_prefix_mismatch")
    _validate_producer_settlement_origin_graph(snapshot.producer_settlements)
    for key, amount in amounts.items():
        if snapshot.state.spent.get(key, Decimal("0")) < amount:
            raise ValueError("budget settlement receipts exceed the recorded spend")
    for provider, amount in provider_amounts.items():
        if snapshot.state.provider_spent.get(provider, Decimal("0")) < amount:
            raise ValueError("budget settlement receipts exceed the recorded provider spend")
    return snapshot


@dataclass(frozen=True)
class BudgetLedgerMutationResult:
    """Result of a ledger mutation."""

    state: BudgetState
    revision: int
    applied_amount: Decimal = Decimal("0")
    reserved: bool | None = None


class BudgetLedger(Protocol):
    """Protocol for distributed-safe budget ledgers."""

    @property
    def settlement_owner_identity(self) -> tuple[str, str, str]: ...

    def load(self) -> BudgetState: ...
    def load_for_admission(self, budget_key: str) -> tuple[BudgetState, Decimal | None]: ...
    def load_existing(
        self,
        expected_owner_identity: tuple[str, str, str],
        *,
        expected_resource_identity: _BudgetResourceIdentity | None = None,
        expected_snapshot_anchor: _BudgetSnapshotAnchor | None = None,
    ) -> BudgetState: ...
    def continuation_binding(
        self,
    ) -> tuple[tuple[str, str, str], _BudgetResourceIdentity, _BudgetSnapshotAnchor]: ...
    def snapshot(self) -> BudgetLedgerSnapshot: ...
    def load_or_bootstrap(self, initial_state: BudgetState) -> BudgetState: ...
    def record_spend(
        self,
        key: str,
        amount: Decimal,
        *,
        provider: str | None = None,
    ) -> BudgetLedgerMutationResult: ...
    def reserve(self, key: str, amount: Decimal) -> BudgetLedgerMutationResult: ...
    def release(self, key: str, amount: Decimal) -> BudgetLedgerMutationResult: ...
    def commit_reservation(
        self,
        key: str,
        amount: Decimal,
        *,
        provider: str | None = None,
    ) -> BudgetLedgerMutationResult: ...
    def settle_spend(
        self,
        event_id: str,
        key: str,
        amount: Decimal,
        *,
        payload_digest: str,
        provider: str | None = None,
    ) -> BudgetLedgerSpendReceipt: ...
    def resolve_spend(self, event_id: str) -> BudgetLedgerSpendReceipt | None: ...

    def reserve_compute(
        self, event_id: str, request_digest: str, key: str, amount: Decimal
    ) -> BudgetLedgerComputeReservation: ...

    def settle_compute(
        self, event_id: str, request_digest: str, settlement_digest: str, amount: Decimal
    ) -> BudgetLedgerComputeReservation: ...

    def mark_compute_unknown(
        self, event_id: str, request_digest: str
    ) -> BudgetLedgerComputeReservation: ...

    def resolve_compute(self, event_id: str) -> BudgetLedgerComputeReservation | None: ...
    def configure_invocation_profile(
        self, profile: BudgetLedgerInvocationProfile
    ) -> BudgetLedgerInvocationProfile: ...
    def select_unconfigured_invocations(self, binding: BudgetLedgerProducerRunBinding) -> None: ...
    def reserve_invocation(
        self,
        operation_id: str,
        request_digest: str,
        *,
        profile: BudgetLedgerInvocationProfile,
        purpose: Literal["standard", "diagnostic", "counterevidence"],
    ) -> tuple[BudgetLedgerInvocationReservation, bool]: ...
    def finish_invocation(
        self,
        operation_id: str,
        request_digest: str,
        *,
        profile: BudgetLedgerInvocationProfile,
        outcome: Literal["completed", "failed", "unknown"],
    ) -> BudgetLedgerInvocationReservation: ...
    def resolve_invocation(
        self, operation_id: str, *, profile: BudgetLedgerInvocationProfile
    ) -> BudgetLedgerInvocationReservation | None: ...
    def open_reentry_budget_window(
        self,
        scope: BudgetLedgerReentryBudgetScope,
        *,
        fresh_limit_usd: Decimal,
        global_limit_usd: Decimal,
    ) -> BudgetLedgerReentryBudgetWindow: ...
    def resolve_reentry_budget_window(
        self, scope: BudgetLedgerReentryBudgetScope
    ) -> BudgetLedgerReentryBudgetWindow | None: ...
    def begin_producer_event(
        self,
        event_id: str,
        request_digest: str,
        key: str,
        model: str,
        provider: str,
        *,
        run_binding: BudgetLedgerProducerRunBinding | None = None,
        control_job_attempt: int | None = None,
        pre_admission_attempt_id: str | None = None,
    ) -> BudgetLedgerProducerRecord: ...
    def settle_producer_event(
        self,
        event_id: str,
        request_digest: str,
        payload_digest: str,
        key: str,
        model: str,
        provider: str,
        amount: Decimal | None,
        cost_origin: Literal["reported", "estimated", "reuse", "unknown"],
        origin_event_id: str | None = None,
        run_binding: BudgetLedgerProducerRunBinding | None = None,
        control_job_attempt: int | None = None,
        pre_admission_attempt_id: str | None = None,
        cache_reuse_session: CacheSettlementSession | None = None,
        cache_reuse_response: object | None = None,
    ) -> BudgetLedgerProducerRecord: ...
    def resolve_producer_event(self, event_id: str) -> BudgetLedgerProducerRecord | None: ...
    def list_producer_events_for_run(
        self, run_binding: BudgetLedgerProducerRunBinding
    ) -> tuple[BudgetLedgerProducerRecord, ...]: ...


def _fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _snapshot_anchor(snapshot: BudgetLedgerSnapshot) -> _BudgetSnapshotAnchor:
    return snapshot.revision, content_hash(
        to_canonical_bytes(snapshot, CanonSpec(forbid_floats=False))
    )


def _legacy_snapshot_anchor_v16(snapshot: BudgetLedgerSnapshot) -> _BudgetSnapshotAnchor:
    """Reproduce the predecessor owner's exact normalized 1.6 anchor."""
    projection = snapshot.model_dump(
        mode="python",
        by_alias=True,
        exclude_none=True,
        exclude={
            "invocation_profiles",
            "invocation_unconfigured_runs",
            "invocation_reservations",
            "reentry_budget_windows",
        },
    )
    projection["schema_version"] = "1.6"
    return snapshot.revision, content_hash(
        to_canonical_bytes(projection, CanonSpec(forbid_floats=False))
    )


def _legacy_snapshot_anchor_v17(snapshot: BudgetLedgerSnapshot) -> _BudgetSnapshotAnchor:
    """Reproduce the actual previous owner's normalized 1.7 anchor."""
    projection = snapshot.model_dump(
        mode="python", by_alias=True, exclude_none=True, exclude={"reentry_budget_windows"}
    )
    projection["schema_version"] = "1.7"
    return snapshot.revision, content_hash(
        to_canonical_bytes(projection, CanonSpec(forbid_floats=False))
    )


def _normalize_public_event_id(event_id: str, *, allow_engine_event: bool = False) -> str:
    """Normalize one typed public event identity before checking or using it."""
    if not isinstance(event_id, str):
        raise TypeError("budget_ledger_event_id_invalid")
    normalized = str.__str__(event_id)
    if not allow_engine_event and str.startswith(normalized, _ENGINE_EVENT_PREFIX):
        raise ValueError("budget_ledger_engine_event_reserved")
    return normalized


class FileBudgetLedger:
    """Atomic JSON budget ledger shared across threads/processes."""

    def __init__(
        self,
        path: Path,
        *,
        ledger_id: str | None = None,
        host_id: str | None = None,
        writer_id: str | None = None,
        mutation_history_limit: int = 32,
    ) -> None:
        if ledger_id is not None and (not isinstance(ledger_id, str) or not ledger_id.strip()):
            raise ValueError("budget_ledger_identity_invalid")
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        self._thread_lock = threading.Lock()
        self._producer_admission: ContextVar[
            Callable[[BudgetLedgerProducerRecord], bool] | None
        ] = ContextVar(f"budget_ledger_producer_admission_{id(self)}", default=None)
        self._expected_ledger_id = ledger_id
        self._require_existing = False
        self._expected_resource_identity: _BudgetResourceIdentity | None = None
        self._strict_snapshot_anchor: _BudgetSnapshotAnchor | None = None
        self._pending_owned_snapshot: BudgetLedgerSnapshot | None = None
        self._pending_owned_identity: tuple[str, str] | None = None
        self._locked_event_outcome: _LockedEventOutcome | None = None
        self.__engine_settlement_capability = object()
        self._ledger_id = ledger_id if ledger_id is not None else _default_ledger_id(self._path)
        resolved_host_id = str(
            host_id or os.getenv("POLISYOS_LEDGER_HOST_ID") or socket.gethostname()
        )
        self._host_id = resolved_host_id.strip() or "localhost"
        resolved_writer_id = str(writer_id or f"{self._host_id}:{os.getpid()}:{self._path.name}")
        self._writer = BudgetLedgerWriter(
            host_id=self._host_id,
            writer_id=resolved_writer_id.strip() or f"{self._host_id}:{os.getpid()}",
            pid=os.getpid(),
        )
        self._mutation_history_limit = max(int(mutation_history_limit), 1)

    def load(self) -> BudgetState:
        with self._thread_lock, self._file_lock(exclusive=True):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError(
                    "budget ledger requires explicit load_or_bootstrap before use"
                )
            self._confirm_snapshot_durability("ledger-snapshot", snapshot)
            return snapshot.state

    def load_for_admission(self, budget_key: str) -> tuple[BudgetState, Decimal | None]:
        """Reconcile the selected budget and evaluate its remaining amount under the lock."""
        with self._thread_lock, self._file_lock(exclusive=True):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError("budget ledger requires an existing snapshot")
            self._confirm_snapshot_durability("ledger-snapshot", snapshot)
            return snapshot.state, snapshot.state.remaining(budget_key)

    def load_existing(
        self,
        expected_owner_identity: tuple[str, str, str],
        *,
        expected_resource_identity: _BudgetResourceIdentity | None = None,
        expected_snapshot_anchor: _BudgetSnapshotAnchor | None = None,
    ) -> BudgetState:
        """Bind a continuing owner to an existing, confirmed ledger without bootstrap.

        The supplied identity must come from the original admitted execution.
        Once continuation is requested, this instance never bootstraps a
        missing ledger or adopts an ID-less snapshot.
        """
        if (
            type(expected_owner_identity) is not tuple
            or len(expected_owner_identity) != 3
            or any(
                not isinstance(value, str) or not value.strip() for value in expected_owner_identity
            )
            or expected_owner_identity[1:] != (_CANONICAL_LEDGER_CONTRACT, _COORDINATION_MODE)
        ):
            raise ValueError("budget_ledger_identity_invalid")
        if (expected_resource_identity is None) != (expected_snapshot_anchor is None):
            raise ValueError("budget_ledger_continuation_binding_incomplete")
        if expected_resource_identity is not None and (
            type(expected_resource_identity) is not tuple
            or len(expected_resource_identity) != 5
            or any(type(expected_resource_identity[index]) is not int for index in (0, 1, 3, 4))
            or not isinstance(expected_resource_identity[2], str)
            or not expected_resource_identity[2]
        ):
            raise ValueError("budget_ledger_resource_identity_invalid")
        if expected_snapshot_anchor is not None and (
            type(expected_snapshot_anchor) is not tuple
            or len(expected_snapshot_anchor) != 2
            or type(expected_snapshot_anchor[0]) is not int
            or expected_snapshot_anchor[0] < 0
            or not isinstance(expected_snapshot_anchor[1], str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_snapshot_anchor[1]) is None
        ):
            raise ValueError("budget_ledger_snapshot_anchor_invalid")
        expected_id = expected_owner_identity[0]
        with (
            self._thread_lock,
            self._file_lock(
                exclusive=True, require_concrete=expected_resource_identity is not None
            ) as lock_fd,
        ):
            self._require_existing = True
            if self._expected_ledger_id is not None and self._expected_ledger_id != expected_id:
                raise ValueError("budget_ledger_identity_mismatch")
            self._expected_ledger_id = expected_id
            if expected_resource_identity is not None:
                if (
                    self._expected_resource_identity is not None
                    and self._expected_resource_identity != expected_resource_identity
                ):
                    raise ValueError("budget_ledger_resource_identity_mismatch")
                self._expected_resource_identity = expected_resource_identity
                if self._resource_identity(lock_fd) != expected_resource_identity:
                    raise ValueError("budget_ledger_resource_identity_mismatch")
                if (
                    self._strict_snapshot_anchor is not None
                    and self._strict_snapshot_anchor != expected_snapshot_anchor
                ):
                    raise ValueError("budget_ledger_snapshot_anchor_mismatch")
                self._strict_snapshot_anchor = expected_snapshot_anchor
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError("budget ledger continuation requires an existing snapshot")
            if self._needs_contract_upgrade(snapshot):
                snapshot = self._persist_snapshot(self._normalize_snapshot(snapshot))
            else:
                self._confirm_snapshot_durability("ledger-snapshot", snapshot)
            return snapshot.state

    def continuation_binding(
        self,
    ) -> tuple[tuple[str, str, str], _BudgetResourceIdentity, _BudgetSnapshotAnchor]:
        """Read the confirmed local owner, actual lock resource, and snapshot together."""
        owner, resource, anchor, _snapshot = self._continuation_state()
        return owner, resource, anchor

    def _bind_live_producer_resource(
        self,
    ) -> tuple[tuple[str, str, str], _BudgetResourceIdentity]:
        """Pin a live producer to this existing owner and concrete lock resource."""
        with self._thread_lock, self._file_lock(exclusive=True, require_concrete=True) as lock_fd:
            snapshot = self._load_snapshot()
            if snapshot is None or snapshot.ledger_id is None:
                raise ValueError("budget_ledger_identity_not_established")
            owner = (snapshot.ledger_id, snapshot.canonical_contract, snapshot.coordination_mode)
            resource = self._resource_identity(lock_fd)
            if self._expected_ledger_id is not None and self._expected_ledger_id != owner[0]:
                raise ValueError("budget_ledger_identity_mismatch")
            if (
                self._expected_resource_identity is not None
                and self._expected_resource_identity != resource
            ):
                raise ValueError("budget_ledger_resource_identity_mismatch")
            self._confirm_snapshot_durability("ledger-snapshot", snapshot)
            self._expected_ledger_id = owner[0]
            self._expected_resource_identity = resource
            self._require_existing = True
            return owner, resource

    def _continuation_state(
        self, *, require_existing_lock: bool = False
    ) -> tuple[
        tuple[str, str, str], _BudgetResourceIdentity, _BudgetSnapshotAnchor, BudgetLedgerSnapshot
    ]:
        """Read one confirmed owner, physical resource, and detached normalized snapshot."""
        file_lock = (
            self._file_lock(exclusive=True, require_concrete=True, create_if_missing=False)
            if require_existing_lock
            else self._file_lock(exclusive=True, require_concrete=True)
        )
        with self._thread_lock, file_lock as lock_fd:
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError("budget ledger requires an existing snapshot")
            if snapshot.ledger_id is None:
                raise ValueError("budget_ledger_identity_not_established")
            self._confirm_snapshot_durability("ledger-snapshot", snapshot)
            normalized = self._normalize_snapshot(snapshot)
            return (
                (snapshot.ledger_id, snapshot.canonical_contract, snapshot.coordination_mode),
                self._resource_identity(lock_fd),
                _snapshot_anchor(normalized),
                normalized.model_copy(deep=True),
            )

    @property
    def settlement_owner_identity(self) -> tuple[str, str, str]:
        """Return the persisted owner/contract identity for producer cache isolation."""
        with self._thread_lock, self._file_lock(exclusive=True):
            snapshot = self._load_snapshot()
        if snapshot is None:
            raise FileNotFoundError("budget ledger requires explicit load_or_bootstrap before use")
        if snapshot.ledger_id is None:
            raise ValueError("durable settlement owner requires a persisted ledger identity")
        return snapshot.ledger_id, snapshot.canonical_contract, snapshot.coordination_mode

    def snapshot(self) -> BudgetLedgerSnapshot:
        with self._thread_lock, self._file_lock(exclusive=True):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError(
                    "budget ledger requires explicit load_or_bootstrap before use"
                )
            self._confirm_snapshot_durability("ledger-snapshot", snapshot)
            return self._normalize_snapshot(snapshot)

    def snapshot_with_raw_bytes(self) -> tuple[BudgetLedgerSnapshot, bytes]:
        """Read and reconcile a concrete snapshot and its bytes under the owner lock."""
        if self._path.is_symlink():
            raise ValueError("budget_ledger_path_is_symlink")
        with (
            self._thread_lock,
            self._file_lock(exclusive=True, require_concrete=True, create_if_missing=False),
        ):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError("budget ledger snapshot is unavailable")
            raw = self._path.read_bytes()
            if decode_budget_ledger_snapshot(raw) != snapshot:
                raise ValueError("budget ledger bytes changed during snapshot")
            return snapshot, raw

    def load_or_bootstrap(self, initial_state: BudgetState) -> BudgetState:
        with self._thread_lock:
            with self._file_lock(exclusive=True):
                snapshot = self._load_snapshot()
                if snapshot is None:
                    if self._require_existing:
                        raise FileNotFoundError(
                            "budget ledger continuation requires an existing snapshot"
                        )
                    snapshot = self._persist_snapshot(
                        self._build_snapshot(
                            prior_snapshot=None,
                            state=initial_state,
                            recent_mutations=(
                                self._build_mutation(
                                    revision=0,
                                    operation="bootstrap",
                                ),
                            ),
                        )
                    )
                else:
                    needs_upgrade = self._needs_contract_upgrade(snapshot)
                    if not needs_upgrade:
                        self._confirm_snapshot_durability("ledger-snapshot", snapshot)
                    snapshot = self._normalize_snapshot(snapshot)
                    if needs_upgrade:
                        snapshot = self._persist_snapshot(snapshot)
                return snapshot.state

    def record_spend(
        self,
        key: str,
        amount: Decimal,
        *,
        provider: str | None = None,
    ) -> BudgetLedgerMutationResult:
        def apply(state: BudgetState) -> BudgetLedgerMutationResult:
            state.record_spend(key, amount, provider=provider)
            return BudgetLedgerMutationResult(
                state=state,
                revision=0,
                applied_amount=amount,
            )

        return self._mutate(
            "record_spend",
            key,
            amount,
            provider=provider,
            operation=apply,
        )

    def reserve(self, key: str, amount: Decimal) -> BudgetLedgerMutationResult:
        def apply(state: BudgetState) -> BudgetLedgerMutationResult:
            reserved = state.reserve(key, amount)
            return BudgetLedgerMutationResult(
                state=state,
                revision=0,
                applied_amount=amount if reserved else Decimal("0"),
                reserved=reserved,
            )

        return self._mutate("reserve", key, amount, operation=apply)

    def release(self, key: str, amount: Decimal) -> BudgetLedgerMutationResult:
        def apply(state: BudgetState) -> BudgetLedgerMutationResult:
            released = state.release(key, amount)
            return BudgetLedgerMutationResult(
                state=state,
                revision=0,
                applied_amount=released,
            )

        return self._mutate("release", key, amount, operation=apply)

    def commit_reservation(
        self,
        key: str,
        amount: Decimal,
        *,
        provider: str | None = None,
    ) -> BudgetLedgerMutationResult:
        def apply(state: BudgetState) -> BudgetLedgerMutationResult:
            committed = state.commit_reservation(key, amount, provider=provider)
            return BudgetLedgerMutationResult(
                state=state,
                revision=0,
                applied_amount=committed,
            )

        return self._mutate(
            "commit_reservation",
            key,
            amount,
            provider=provider,
            operation=apply,
        )

    def reserve_compute(
        self, event_id: str, request_digest: str, key: str, amount: Decimal
    ) -> BudgetLedgerComputeReservation:
        """Reserve a priced upper budget once under the durable ledger lock."""
        event_id = _normalize_public_event_id(event_id)
        candidate = BudgetLedgerComputeReservation(
            event_id=event_id,
            request_digest=request_digest,
            key=key,
            reserved_amount=amount,
            status="reserved",
            revision=0,
        )
        with (
            self._thread_lock,
            self._file_lock(exclusive=True, outcome_identity=(event_id, request_digest)),
        ):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError("budget ledger requires explicit bootstrap")
            existing = snapshot.compute_reservations.get(event_id)
            if existing is not None:
                if (
                    existing.request_digest != request_digest
                    or existing.key != key
                    or existing.reserved_amount != amount
                ):
                    raise ValueError("compute_reservation_event_conflict")
                self._confirm_snapshot_durability(event_id, snapshot)
                return existing
            if event_id in snapshot.spend_receipts or event_id in snapshot.producer_settlements:
                raise ValueError("compute_reservation_event_conflict")
            if any(
                item.key == key and item.status in {"reserved", "unknown"}
                for item in snapshot.compute_reservations.values()
            ):
                raise ValueError("compute_budget_unresolved_reservation")
            state = _branch_budget_state(snapshot.state)
            if state.remaining(key) is None:
                raise ValueError("compute_budget_limit_not_configured")
            if not state.reserve(key, amount):
                raise ValueError("compute_budget_exhausted")
            record = candidate.model_copy(update={"revision": snapshot.revision + 1})
            records = dict(snapshot.compute_reservations)
            records[event_id] = record
            try:
                written = self._persist_snapshot(
                    self._build_snapshot(
                        prior_snapshot=snapshot,
                        state=state,
                        revision=record.revision,
                        recent_mutations=[
                            *snapshot.recent_mutations,
                            self._build_mutation(
                                revision=record.revision,
                                operation="reserve_compute",
                                key=key,
                                amount=amount,
                                applied_amount=amount,
                                reserved=True,
                            ),
                        ],
                        spend_receipts=snapshot.spend_receipts,
                        producer_settlements=snapshot.producer_settlements,
                        compute_reservations=records,
                    )
                )
            except OSError as exc:
                raise BudgetLedgerSettlementOutcomeUnknownError(event_id, request_digest) from exc
            return written.compute_reservations[event_id]

    def settle_compute(
        self, event_id: str, request_digest: str, settlement_digest: str, amount: Decimal
    ) -> BudgetLedgerComputeReservation:
        """Atomically consume one identified reservation and charge actual work once."""
        event_id = _normalize_public_event_id(event_id)
        if type(amount) is not Decimal or not amount.is_finite() or amount < 0:
            raise ValueError("compute_actual_cost_must_be_finite_and_nonnegative")
        if re.fullmatch(r"[0-9a-f]{64}", settlement_digest) is None:
            raise ValueError("compute_settlement_digest_invalid")
        with (
            self._thread_lock,
            self._file_lock(exclusive=True, outcome_identity=(event_id, settlement_digest)),
        ):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError("budget ledger requires explicit bootstrap")
            existing = snapshot.compute_reservations.get(event_id)
            if existing is None or existing.request_digest != request_digest:
                raise ValueError("compute_reservation_missing_or_conflicting")
            if existing.status == "settled":
                if (
                    existing.actual_amount != amount
                    or existing.settlement_digest != settlement_digest
                ):
                    raise ValueError("compute_settlement_event_conflict")
                self._confirm_snapshot_durability(event_id, snapshot)
                return existing
            if event_id in snapshot.spend_receipts:
                raise ValueError("compute_settlement_receipt_conflict")
            state = _branch_budget_state(snapshot.state)
            if state.release(existing.key, existing.reserved_amount) != existing.reserved_amount:
                raise ValueError("compute_reservation_balance_invalid")
            state.record_spend(existing.key, amount)
            revision = snapshot.revision + 1
            record = existing.model_copy(
                update={
                    "status": "settled",
                    "actual_amount": amount,
                    "settlement_digest": settlement_digest,
                    "revision": revision,
                }
            )
            records = dict(snapshot.compute_reservations)
            records[event_id] = record
            receipts = dict(snapshot.spend_receipts)
            receipts[event_id] = BudgetLedgerSpendReceipt(
                event_id=event_id,
                payload_digest=settlement_digest,
                key=existing.key,
                amount=amount,
                revision=revision,
            )
            try:
                written = self._persist_snapshot(
                    self._build_snapshot(
                        prior_snapshot=snapshot,
                        state=state,
                        revision=revision,
                        recent_mutations=[
                            *snapshot.recent_mutations,
                            self._build_mutation(
                                revision=revision,
                                operation="settle_compute",
                                key=existing.key,
                                amount=amount,
                                applied_amount=amount,
                            ),
                        ],
                        spend_receipts=receipts,
                        producer_settlements=snapshot.producer_settlements,
                        compute_reservations=records,
                    )
                )
            except OSError as exc:
                raise BudgetLedgerSettlementOutcomeUnknownError(
                    event_id, settlement_digest
                ) from exc
            return written.compute_reservations[event_id]

    def mark_compute_unknown(
        self, event_id: str, request_digest: str
    ) -> BudgetLedgerComputeReservation:
        """Retain the reservation when actual work cost cannot be established."""
        event_id = _normalize_public_event_id(event_id)
        with (
            self._thread_lock,
            self._file_lock(exclusive=True, outcome_identity=(event_id, request_digest)),
        ):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError("budget ledger requires explicit bootstrap")
            existing = snapshot.compute_reservations.get(event_id)
            if existing is None or existing.request_digest != request_digest:
                raise ValueError("compute_reservation_missing_or_conflicting")
            if existing.status == "settled":
                raise ValueError("compute_settlement_already_known")
            if existing.status == "unknown":
                self._confirm_snapshot_durability(event_id, snapshot)
                return existing
            revision = snapshot.revision + 1
            record = existing.model_copy(update={"status": "unknown", "revision": revision})
            records = dict(snapshot.compute_reservations)
            records[event_id] = record
            try:
                written = self._persist_snapshot(
                    self._build_snapshot(
                        prior_snapshot=snapshot,
                        state=snapshot.state,
                        revision=revision,
                        recent_mutations=[
                            *snapshot.recent_mutations,
                            self._build_mutation(
                                revision=revision,
                                operation="mark_compute_unknown",
                                key=existing.key,
                            ),
                        ],
                        spend_receipts=snapshot.spend_receipts,
                        producer_settlements=snapshot.producer_settlements,
                        compute_reservations=records,
                    )
                )
            except OSError as exc:
                raise BudgetLedgerSettlementOutcomeUnknownError(event_id, request_digest) from exc
            return written.compute_reservations[event_id]

    def _confirm_snapshot_durability(
        self, event_id: str, snapshot: BudgetLedgerSnapshot, *, payload_digest: str = "readback"
    ) -> None:
        """Confirm the selected snapshot under the caller's stable exclusive lock."""
        try:
            _fsync_dir(self._path.parent)
            confirmed = self._load_snapshot()
        except (OSError, ValueError) as exc:
            raise BudgetLedgerSettlementOutcomeUnknownError(event_id, payload_digest) from exc
        if confirmed != snapshot:
            raise BudgetLedgerSettlementOutcomeUnknownError(event_id, payload_digest)
        outcome = self._locked_event_outcome
        if outcome is not None and outcome.event_id == event_id:
            if payload_digest != "readback":
                outcome.payload_digest = payload_digest
            outcome.acknowledged = True

    def resolve_compute(self, event_id: str) -> BudgetLedgerComputeReservation | None:
        """Reread this owner's durable record; absent does not prove zero work."""
        event_id = _normalize_public_event_id(event_id, allow_engine_event=True)
        with (
            self._thread_lock,
            self._file_lock(exclusive=True, outcome_identity=(event_id, "readback")),
        ):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError("budget ledger requires explicit bootstrap")
            if event_id not in snapshot.compute_reservations and (
                event_id in snapshot.spend_receipts or event_id in snapshot.producer_settlements
            ):
                raise ValueError("budget_event_kind_conflict")
            self._confirm_snapshot_durability(event_id, snapshot)
            return snapshot.compute_reservations.get(event_id)

    def _persist_invocation_update(
        self,
        snapshot: BudgetLedgerSnapshot,
        *,
        mutation: BudgetLedgerMutation,
        profiles: dict[str, BudgetLedgerInvocationProfile] | None = None,
        unconfigured_runs: dict[str, BudgetLedgerProducerRunBinding] | None = None,
        reservations: dict[str, BudgetLedgerInvocationReservation] | None = None,
    ) -> BudgetLedgerSnapshot:
        """Persist invocation-unit changes in the existing locked budget snapshot."""
        return self._persist_snapshot(
            self._build_snapshot(
                prior_snapshot=snapshot,
                state=snapshot.state,
                revision=mutation.revision,
                recent_mutations=[*snapshot.recent_mutations, mutation],
                spend_receipts=snapshot.spend_receipts,
                producer_settlements=snapshot.producer_settlements,
                compute_reservations=snapshot.compute_reservations,
                invocation_profiles=profiles,
                invocation_unconfigured_runs=unconfigured_runs,
                invocation_reservations=reservations,
            )
        )

    def configure_invocation_profile(
        self, profile: BudgetLedgerInvocationProfile
    ) -> BudgetLedgerInvocationProfile:
        """Persist one immutable, owner-selected unit allocation for this run."""
        if type(profile) is not BudgetLedgerInvocationProfile:
            raise TypeError("invocation_quota_profile_untyped")
        run_id = profile.run_binding.run_id
        event_id = f"n5-invocation-profile:{profile.profile_digest}"
        with (
            self._thread_lock,
            self._file_lock(exclusive=True, outcome_identity=(event_id, profile.profile_digest)),
        ):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError("budget ledger requires explicit bootstrap")
            if run_id in snapshot.invocation_unconfigured_runs:
                raise ValueError("invocation_quota_run_already_unconfigured")
            existing = snapshot.invocation_profiles.get(run_id)
            if existing is not None:
                if existing != profile:
                    raise ValueError("invocation_quota_profile_conflict")
                self._confirm_snapshot_durability(event_id, snapshot)
                return existing
            profiles = dict(snapshot.invocation_profiles)
            profiles[run_id] = profile
            revision = snapshot.revision + 1
            written = self._persist_invocation_update(
                snapshot,
                profiles=profiles,
                mutation=self._build_mutation(
                    revision=revision,
                    operation="configure_invocation_quota",
                    key=f"nl-run:{run_id}",
                ),
            )
            self._confirm_snapshot_durability(
                event_id, written, payload_digest=profile.profile_digest
            )
            return written.invocation_profiles[run_id]

    def select_unconfigured_invocations(self, binding: BudgetLedgerProducerRunBinding) -> None:
        """Atomically select no guarantee for this exact run, before physical work.

        Once selected, finite quota cannot be introduced for the run: earlier
        unmetered work cannot truthfully be counted towards a new allocation.
        """
        if type(binding) is not BudgetLedgerProducerRunBinding:
            raise TypeError("invocation_quota_run_binding_untyped")
        binding_digest = content_hash(to_canonical_bytes(binding.model_dump(mode="json")))
        event_id = f"n5-invocation-unconfigured:{binding_digest}"
        with (
            self._thread_lock,
            self._file_lock(exclusive=True, outcome_identity=(event_id, binding_digest)),
        ):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError("budget ledger requires explicit bootstrap")
            if binding.run_id in snapshot.invocation_profiles:
                raise ValueError("invocation_quota_profile_required")
            existing = snapshot.invocation_unconfigured_runs.get(binding.run_id)
            if existing is not None:
                if existing != binding:
                    raise ValueError("invocation_quota_run_binding_mismatch")
                self._confirm_snapshot_durability(event_id, snapshot)
                return
            runs = dict(snapshot.invocation_unconfigured_runs)
            runs[binding.run_id] = binding
            written = self._persist_invocation_update(
                snapshot,
                unconfigured_runs=runs,
                mutation=self._build_mutation(
                    revision=snapshot.revision + 1,
                    operation="select_unconfigured_invocation_quota",
                    key=f"nl-run:{binding.run_id}",
                ),
            )
            self._confirm_snapshot_durability(event_id, written, payload_digest=binding_digest)

    def open_reentry_budget_window(
        self,
        scope: BudgetLedgerReentryBudgetScope,
        *,
        fresh_limit_usd: Decimal,
        global_limit_usd: Decimal,
    ) -> BudgetLedgerReentryBudgetWindow:
        """Issue or reopen one owner-observed window before the action fetches.

        The caller is the action owner: it verifies the current action phase,
        its ancestry, and the selected source/profile and limits. The ledger
        fixes the actual producer prefix once for this stable action identity.
        """
        if type(scope) is not BudgetLedgerReentryBudgetScope:
            raise TypeError("reentry_budget_scope_untyped")
        if (
            type(fresh_limit_usd) is not Decimal
            or not fresh_limit_usd.is_finite()
            or fresh_limit_usd <= 0
            or type(global_limit_usd) is not Decimal
            or not global_limit_usd.is_finite()
            or global_limit_usd < 0
        ):
            raise ValueError("reentry_budget_limit_invalid")
        event_id = f"reentry-budget:{scope.window_id}"
        request_digest = content_hash(
            to_canonical_bytes(
                {
                    "window_id": scope.window_id,
                    "source_payload_ref": scope.source_payload_ref,
                    "profile_selection_ref": scope.profile_selection_ref,
                    "fresh_limit_usd": _reentry_limit_identity(fresh_limit_usd),
                    "global_limit_usd": _reentry_limit_identity(global_limit_usd),
                }
            )
        )
        with (
            self._thread_lock,
            self._file_lock(
                exclusive=True, require_concrete=True, outcome_identity=(event_id, request_digest)
            ) as lock_fd,
        ):
            snapshot = self._load_snapshot()
            if snapshot is None or snapshot.ledger_id is None:
                raise ValueError("budget_ledger_identity_not_established")
            resource = self._resource_identity(lock_fd)
            existing = snapshot.reentry_budget_windows.get(scope.window_id)
            if existing is not None:
                if (
                    not _same_reentry_action_basis(existing.scope, scope)
                    or existing.fresh_limit_usd != fresh_limit_usd
                    or existing.global_limit_usd != global_limit_usd
                    or existing.resource_identity != resource
                ):
                    raise ValueError("reentry_budget_window_conflict")
                _reentry_prefix(snapshot, scope.run_binding, cutoff=None)
                self._confirm_snapshot_durability(event_id, snapshot, payload_digest=request_digest)
                return existing
            baseline_total, prefix_digest = _reentry_prefix(
                snapshot, scope.run_binding, cutoff=None
            )
            revision = snapshot.revision + 1
            window = BudgetLedgerReentryBudgetWindow(
                scope=scope,
                ledger_id=snapshot.ledger_id,
                resource_identity=resource,
                fresh_limit_usd=fresh_limit_usd,
                global_limit_usd=global_limit_usd,
                baseline_total_usd=baseline_total,
                baseline_revision=snapshot.revision,
                baseline_prefix_digest=prefix_digest,
                revision=revision,
            )
            # Validate arithmetic before persisting an unusable or rounded allowance.
            if not window.effective_limit_usd.is_finite():
                raise ValueError("reentry_budget_arithmetic_not_established")
            windows = dict(snapshot.reentry_budget_windows)
            windows[scope.window_id] = window
            written = self._persist_snapshot(
                self._build_snapshot(
                    prior_snapshot=snapshot,
                    state=snapshot.state,
                    revision=revision,
                    recent_mutations=[
                        *snapshot.recent_mutations,
                        self._build_mutation(
                            revision=revision,
                            operation="open_reentry_budget_window",
                            key=f"nl-run:{scope.run_binding.run_id}",
                        ),
                    ],
                    spend_receipts=snapshot.spend_receipts,
                    producer_settlements=snapshot.producer_settlements,
                    compute_reservations=snapshot.compute_reservations,
                    reentry_budget_windows=windows,
                )
            )
            self._confirm_snapshot_durability(event_id, written, payload_digest=request_digest)
            return written.reentry_budget_windows[scope.window_id]

    def resolve_reentry_budget_window(
        self, scope: BudgetLedgerReentryBudgetScope
    ) -> BudgetLedgerReentryBudgetWindow | None:
        """Read the same durable action window; never select a new baseline."""
        if type(scope) is not BudgetLedgerReentryBudgetScope:
            raise TypeError("reentry_budget_scope_untyped")
        event_id = f"reentry-budget:{scope.window_id}"
        with (
            self._thread_lock,
            self._file_lock(exclusive=True, require_concrete=True) as lock_fd,
        ):
            snapshot = self._load_snapshot()
            if snapshot is None or snapshot.ledger_id is None:
                raise ValueError("budget_ledger_identity_not_established")
            window = snapshot.reentry_budget_windows.get(scope.window_id)
            if window is not None and (
                not _same_reentry_action_basis(window.scope, scope)
                or window.resource_identity != self._resource_identity(lock_fd)
            ):
                raise ValueError("reentry_budget_window_conflict")
            self._confirm_snapshot_durability(event_id, snapshot)
            return window

    def reserve_invocation(
        self,
        operation_id: str,
        request_digest: str,
        *,
        profile: BudgetLedgerInvocationProfile,
        purpose: Literal["standard", "diagnostic", "counterevidence"],
    ) -> tuple[BudgetLedgerInvocationReservation, bool]:
        """Reserve one physical call; an existing operation is never a new permit."""
        if type(profile) is not BudgetLedgerInvocationProfile:
            raise TypeError("invocation_quota_profile_untyped")
        candidate = BudgetLedgerInvocationReservation(
            operation_id=operation_id,
            request_digest=request_digest,
            run_id=profile.run_binding.run_id,
            profile_digest=profile.profile_digest,
            purpose=purpose,
            revision=1,
        )
        with (
            self._thread_lock,
            self._file_lock(exclusive=True, outcome_identity=(operation_id, request_digest)),
        ):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError("budget ledger requires explicit bootstrap")
            if snapshot.invocation_profiles.get(candidate.run_id) != profile:
                raise ValueError("invocation_quota_profile_not_current")
            existing = snapshot.invocation_reservations.get(operation_id)
            if existing is not None:
                if any(
                    getattr(existing, field) != getattr(candidate, field)
                    for field in ("request_digest", "run_id", "profile_digest", "purpose")
                ):
                    raise ValueError("invocation_reservation_identity_conflict")
                self._confirm_snapshot_durability(operation_id, snapshot)
                return existing, False
            protected = purpose != "standard"
            consumed = sum(
                item.units
                for item in snapshot.invocation_reservations.values()
                if item.run_id == candidate.run_id and (item.purpose != "standard") == protected
            )
            limit = (
                profile.protected_units
                if protected
                else profile.total_units - profile.protected_units
            )
            if consumed >= limit:
                raise BudgetLedgerInvocationQuotaExhaustedError("invocation_quota_exhausted")
            revision = snapshot.revision + 1
            record = candidate.model_copy(update={"revision": revision})
            reservations = dict(snapshot.invocation_reservations)
            reservations[operation_id] = record
            written = self._persist_invocation_update(
                snapshot,
                reservations=reservations,
                mutation=self._build_mutation(
                    revision=revision, operation="reserve_invocation", key=f"nl-run:{record.run_id}"
                ),
            )
            self._confirm_snapshot_durability(operation_id, written, payload_digest=request_digest)
            return written.invocation_reservations[operation_id], True

    def finish_invocation(
        self,
        operation_id: str,
        request_digest: str,
        *,
        profile: BudgetLedgerInvocationProfile,
        outcome: Literal["completed", "failed", "unknown"],
    ) -> BudgetLedgerInvocationReservation:
        """Record the real terminal outcome without returning a used unit."""
        if type(profile) is not BudgetLedgerInvocationProfile:
            raise TypeError("invocation_quota_profile_untyped")
        if outcome not in {"completed", "failed", "unknown"}:
            raise ValueError("invocation_outcome_invalid")
        with (
            self._thread_lock,
            self._file_lock(exclusive=True, outcome_identity=(operation_id, request_digest)),
        ):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError("budget ledger requires explicit bootstrap")
            existing = snapshot.invocation_reservations.get(operation_id)
            if (
                snapshot.invocation_profiles.get(profile.run_binding.run_id) != profile
                or existing is None
                or existing.run_id != profile.run_binding.run_id
                or existing.profile_digest != profile.profile_digest
                or existing.request_digest != request_digest
            ):
                raise ValueError("invocation_reservation_missing_or_conflicting")
            if existing.status != "reserved":
                if existing.status != outcome:
                    raise ValueError("invocation_outcome_conflict")
                self._confirm_snapshot_durability(operation_id, snapshot)
                return existing
            revision = snapshot.revision + 1
            record = existing.model_copy(update={"status": outcome, "revision": revision})
            reservations = dict(snapshot.invocation_reservations)
            reservations[operation_id] = record
            written = self._persist_invocation_update(
                snapshot,
                reservations=reservations,
                mutation=self._build_mutation(
                    revision=revision, operation="finish_invocation", key=f"nl-run:{record.run_id}"
                ),
            )
            self._confirm_snapshot_durability(operation_id, written, payload_digest=request_digest)
            return written.invocation_reservations[operation_id]

    def resolve_invocation(
        self, operation_id: str, *, profile: BudgetLedgerInvocationProfile
    ) -> BudgetLedgerInvocationReservation | None:
        """Read an exact invocation record; absence never proves that work was free."""
        if type(profile) is not BudgetLedgerInvocationProfile:
            raise TypeError("invocation_quota_profile_untyped")
        if re.fullmatch(r"[0-9a-f]{64}", operation_id) is None:
            raise ValueError("invocation_operation_id_invalid")
        with (
            self._thread_lock,
            self._file_lock(exclusive=True, outcome_identity=(operation_id, "readback")),
        ):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError("budget ledger requires explicit bootstrap")
            if snapshot.invocation_profiles.get(profile.run_binding.run_id) != profile:
                raise ValueError("invocation_quota_profile_not_current")
            record = snapshot.invocation_reservations.get(operation_id)
            if record is not None and record.run_id != profile.run_binding.run_id:
                raise ValueError("invocation_reservation_owner_mismatch")
            self._confirm_snapshot_durability(operation_id, snapshot)
            return record

    def settle_spend(
        self,
        event_id: str,
        key: str,
        amount: Decimal,
        *,
        payload_digest: str,
        provider: str | None = None,
    ) -> BudgetLedgerSpendReceipt:
        """Atomically charge one exact event once and return its durable receipt.

        Exact retries return the original receipt, including after journal
        eviction or process restart. A reused ID with different payload or
        charge refuses. Filesystem failure is an unknown acknowledgment;
        resolve or retry this same ID instead of inventing a second event.
        """
        event_id = _normalize_public_event_id(event_id)
        return self._settle_spend(
            event_id, key, amount, payload_digest=payload_digest, provider=provider
        )

    def _issue_engine_settlement_writer(
        self,
    ) -> Callable[[str, Decimal, str, str | None], BudgetLedgerSpendReceipt]:
        """Issue one private writer only from an armed, current ledger owner."""
        with self._thread_lock, self._file_lock(exclusive=True):
            if self._expected_resource_identity is None or self._strict_snapshot_anchor is None:
                raise ValueError("budget_ledger_engine_guard_not_armed")
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError("budget ledger continuation requires an existing snapshot")
            self._confirm_snapshot_durability("ledger-snapshot", snapshot)
            capability = self.__engine_settlement_capability

        def write(
            event_id: str, amount: Decimal, payload_digest: str, provider: str | None
        ) -> BudgetLedgerSpendReceipt:
            if (
                capability is not self.__engine_settlement_capability
                or type(event_id) is not str
                or not str.startswith(event_id, _ENGINE_EVENT_PREFIX)
            ):
                raise ValueError("budget_ledger_engine_capability_invalid")
            return self._settle_spend(
                event_id, "run", amount, payload_digest=payload_digest, provider=provider
            )

        return write

    def _settle_spend(
        self,
        event_id: str,
        key: str,
        amount: Decimal,
        *,
        payload_digest: str,
        provider: str | None,
    ) -> BudgetLedgerSpendReceipt:
        candidate = BudgetLedgerSpendReceipt(
            event_id=event_id,
            payload_digest=payload_digest,
            key=key,
            amount=amount,
            provider=provider,
            revision=1,
        )
        with self._thread_lock:
            with self._file_lock(exclusive=True, outcome_identity=(event_id, payload_digest)):
                snapshot = self._load_snapshot()
                if snapshot is None:
                    raise FileNotFoundError(
                        "budget ledger requires explicit load_or_bootstrap before use"
                    )
                if event_id in snapshot.compute_reservations:
                    raise ValueError("budget_event_kind_conflict")
                existing = snapshot.spend_receipts.get(event_id)
                if existing is not None:
                    identity = ("event_id", "payload_digest", "key", "amount", "provider")
                    if any(
                        getattr(existing, field) != getattr(candidate, field) for field in identity
                    ):
                        raise ValueError("settlement event ID conflicts with an existing charge")
                    self._confirm_snapshot_durability(
                        event_id, snapshot, payload_digest=payload_digest
                    )
                    return existing
                state = _branch_budget_state(snapshot.state)
                state.record_spend(key, candidate.amount, provider=provider)
                revision = snapshot.revision + 1
                receipt = candidate.model_copy(update={"revision": revision})
                receipts = dict(snapshot.spend_receipts)
                receipts[event_id] = receipt
                mutations = list(snapshot.recent_mutations)
                mutations.append(
                    self._build_mutation(
                        revision=revision,
                        operation="settle_spend",
                        key=key,
                        amount=candidate.amount,
                        applied_amount=candidate.amount,
                        provider=provider,
                    )
                )
                try:
                    written = self._persist_snapshot(
                        self._build_snapshot(
                            prior_snapshot=snapshot,
                            state=state,
                            revision=revision,
                            recent_mutations=mutations,
                            spend_receipts=receipts,
                            producer_settlements=snapshot.producer_settlements,
                            compute_reservations=snapshot.compute_reservations,
                        )
                    )
                except (OSError, BudgetLedgerSettlementOutcomeUnknownError) as exc:
                    if self._pending_owned_snapshot is not None:
                        self._pending_owned_identity = (event_id, payload_digest)
                    raise BudgetLedgerSettlementOutcomeUnknownError(
                        event_id, payload_digest
                    ) from exc
                return written.spend_receipts[event_id]

    @contextmanager
    def _guarded_producer_begin(
        self, is_live_attempt: Callable[[BudgetLedgerProducerRecord], bool]
    ) -> Iterator[None]:
        """Bind an owner check to one call without replacing the normal begin seam."""
        token = self._producer_admission.set(is_live_attempt)
        try:
            yield
        finally:
            self._producer_admission.reset(token)

    def begin_producer_event(
        self,
        event_id: str,
        request_digest: str,
        key: str,
        model: str,
        provider: str,
        *,
        run_binding: BudgetLedgerProducerRunBinding | None = None,
        control_job_attempt: int | None = None,
        pre_admission_attempt_id: str | None = None,
    ) -> BudgetLedgerProducerRecord:
        """Persist the provider intent before dispatch; pending is never zero."""
        return self._begin_producer_event(
            event_id,
            request_digest,
            key,
            model,
            provider,
            run_binding=run_binding,
            control_job_attempt=control_job_attempt,
            pre_admission_attempt_id=pre_admission_attempt_id,
            is_live_attempt=self._producer_admission.get(),
        )

    def _begin_producer_event(
        self,
        event_id: str,
        request_digest: str,
        key: str,
        model: str,
        provider: str,
        *,
        run_binding: BudgetLedgerProducerRunBinding | None = None,
        control_job_attempt: int | None = None,
        pre_admission_attempt_id: str | None = None,
        is_live_attempt: Callable[[BudgetLedgerProducerRecord], bool] | None = None,
    ) -> BudgetLedgerProducerRecord:
        """Check the current run and issue one intent in a single ledger transaction.

        The predicate is owned by the middleware and reads its live registry at
        admission time. A different process cannot assert that its pending row
        is active: absent local ownership, the outcome stays unresolved.
        """
        event_id = _normalize_public_event_id(event_id)
        with self._thread_lock:
            with self._file_lock(exclusive=True, outcome_identity=(event_id, request_digest)):
                snapshot = self._load_snapshot()
                if snapshot is None:
                    raise FileNotFoundError(
                        "budget ledger requires explicit load_or_bootstrap before use"
                    )
                if is_live_attempt is not None:
                    if run_binding is None or key != f"nl-run:{run_binding.run_id}":
                        raise ValueError("producer_spend_owner_not_established")
                    for prior in snapshot.producer_settlements.values():
                        if prior.key != key:
                            continue
                        if prior.run_binding != run_binding:
                            raise ValueError("producer_spend_owner_binding_conflict")
                        if prior.status == "committed":
                            continue
                        if (
                            prior.status == "pending"
                            and is_live_attempt(prior)
                            and prior.control_job_attempt == control_job_attempt
                            and prior.pre_admission_attempt_id == pre_admission_attempt_id
                        ):
                            continue
                        raise BudgetLedgerSettlementOutcomeUnknownError(
                            prior.event_id, prior.payload_digest or prior.request_digest
                        )
                if event_id in snapshot.compute_reservations:
                    raise ValueError("budget_event_kind_conflict")
                existing = snapshot.producer_settlements.get(event_id)
                if existing is not None:
                    if (
                        existing.request_digest != request_digest
                        or existing.key != key
                        or existing.model != model
                        or existing.provider != provider
                        or existing.run_binding != run_binding
                        or existing.control_job_attempt != control_job_attempt
                        or existing.pre_admission_attempt_id != pre_admission_attempt_id
                    ):
                        raise ValueError("producer event ID conflicts with an existing intent")
                    self._confirm_snapshot_durability(
                        event_id, snapshot, payload_digest=request_digest
                    )
                    return existing
                revision = snapshot.revision + 1
                record = BudgetLedgerProducerRecord(
                    event_id=event_id,
                    request_digest=request_digest,
                    key=key,
                    model=model,
                    provider=provider,
                    run_binding=run_binding,
                    control_job_attempt=control_job_attempt,
                    pre_admission_attempt_id=pre_admission_attempt_id,
                    amount=None,
                    cost_origin="unknown",
                    status="pending",
                    revision=revision,
                )
                settlements = dict(snapshot.producer_settlements)
                settlements[event_id] = record
                mutations = list(snapshot.recent_mutations)
                mutations.append(
                    self._build_mutation(
                        revision=revision,
                        operation="begin_producer_event",
                        key=key,
                        provider=provider,
                    )
                )
                try:
                    written = self._persist_snapshot(
                        self._build_snapshot(
                            prior_snapshot=snapshot,
                            state=snapshot.state,
                            revision=revision,
                            recent_mutations=mutations,
                            spend_receipts=snapshot.spend_receipts,
                            producer_settlements=settlements,
                            compute_reservations=snapshot.compute_reservations,
                        )
                    )
                except OSError as exc:
                    raise BudgetLedgerSettlementOutcomeUnknownError(
                        event_id, request_digest
                    ) from exc
                return written.producer_settlements[event_id]

    def settle_producer_event(
        self,
        event_id: str,
        request_digest: str,
        payload_digest: str,
        key: str,
        model: str,
        provider: str,
        amount: Decimal | None,
        cost_origin: Literal["reported", "estimated", "reuse", "unknown"],
        origin_event_id: str | None = None,
        run_binding: BudgetLedgerProducerRunBinding | None = None,
        control_job_attempt: int | None = None,
        pre_admission_attempt_id: str | None = None,
        cache_reuse_session: CacheSettlementSession | None = None,
        cache_reuse_response: object | None = None,
    ) -> BudgetLedgerProducerRecord:
        """Atomically publish one terminal producer status and any known charge."""
        event_id = _normalize_public_event_id(event_id)
        status: Literal["committed", "unknown"] = "unknown" if amount is None else "committed"
        if cost_origin != "reuse" and (
            cache_reuse_session is not None or cache_reuse_response is not None
        ):
            raise ValueError("producer_reuse_admission_unexpected")
        admission = (
            _verified_cache_reuse_admission(
                session=cache_reuse_session,
                response=cache_reuse_response,
                event_id=event_id,
                request_digest=request_digest,
                payload_digest=payload_digest,
                origin_event_id=origin_event_id,
                model=model,
                provider=provider,
            )
            if cost_origin == "reuse"
            else None
        )
        candidate = BudgetLedgerProducerRecord(
            event_id=event_id,
            request_digest=request_digest,
            payload_digest=payload_digest,
            key=key,
            model=model,
            provider=provider,
            amount=amount,
            cost_origin=cost_origin,
            reuse_admission=admission,
            status=status,
            origin_event_id=origin_event_id,
            run_binding=run_binding,
            control_job_attempt=control_job_attempt,
            pre_admission_attempt_id=pre_admission_attempt_id,
            revision=1,
        )
        with self._thread_lock:
            with self._file_lock(exclusive=True, outcome_identity=(event_id, payload_digest)):
                snapshot = self._load_snapshot()
                if snapshot is None:
                    raise FileNotFoundError(
                        "budget ledger requires explicit load_or_bootstrap before use"
                    )
                if event_id in snapshot.compute_reservations:
                    raise ValueError("budget_event_kind_conflict")
                _validate_producer_settlement_origin_graph(snapshot.producer_settlements)
                existing_record = snapshot.producer_settlements.get(event_id)
                if existing_record is not None:
                    intent_identity = (
                        "request_digest",
                        "key",
                        "model",
                        "provider",
                        "run_binding",
                    )
                    if any(
                        getattr(existing_record, field) != getattr(candidate, field)
                        for field in intent_identity
                    ):
                        raise ValueError(
                            "producer event run binding conflicts with existing intent"
                        )
                    for field in ("control_job_attempt", "pre_admission_attempt_id"):
                        incoming = getattr(candidate, field)
                        persisted = getattr(existing_record, field)
                        if incoming is not None and incoming != persisted:
                            raise ValueError(
                                "producer event attempt attribution conflicts with existing intent"
                            )
                        if incoming is None:
                            candidate = candidate.model_copy(update={field: persisted})
                    if existing_record.status != "pending":
                        identity = (
                            "payload_digest",
                            "key",
                            "model",
                            "provider",
                            "amount",
                            "cost_origin",
                            "status",
                            "origin_event_id",
                            "reuse_admission",
                            "control_job_attempt",
                            "pre_admission_attempt_id",
                        )
                        if any(
                            getattr(existing_record, field) != getattr(candidate, field)
                            for field in identity
                        ):
                            raise ValueError("producer event retry conflicts with prior outcome")
                        self._confirm_snapshot_durability(
                            event_id, snapshot, payload_digest=payload_digest
                        )
                        return existing_record

                origin_source = (
                    snapshot.producer_settlements.get(candidate.origin_event_id)
                    if candidate.origin_event_id is not None
                    else None
                )
                candidate._validate_new_settlement_origin(origin_source)

                state = _branch_budget_state(snapshot.state)
                receipts = dict(snapshot.spend_receipts)
                if amount is not None:
                    existing_receipt = receipts.get(event_id)
                    if existing_receipt is not None:
                        identity = ("payload_digest", "key", "amount", "provider")
                        if any(
                            getattr(existing_receipt, field)
                            != getattr(
                                BudgetLedgerSpendReceipt(
                                    event_id=event_id,
                                    payload_digest=payload_digest,
                                    key=key,
                                    amount=amount,
                                    provider=provider,
                                    revision=existing_receipt.revision,
                                ),
                                field,
                            )
                            for field in identity
                        ):
                            raise ValueError("producer charge conflicts with existing receipt")
                    else:
                        state.record_spend(key, amount, provider=provider)
                        revision = snapshot.revision + 1
                        receipts[event_id] = BudgetLedgerSpendReceipt(
                            event_id=event_id,
                            payload_digest=payload_digest,
                            key=key,
                            amount=amount,
                            provider=provider,
                            revision=revision,
                        )
                revision = snapshot.revision + 1
                record = candidate.model_copy(update={"revision": revision})
                settlements = dict(snapshot.producer_settlements)
                settlements[event_id] = record
                mutations = list(snapshot.recent_mutations)
                mutations.append(
                    self._build_mutation(
                        revision=revision,
                        operation="settle_producer_event",
                        key=key,
                        amount=amount,
                        applied_amount=amount,
                        provider=provider,
                    )
                )
                try:
                    written = self._persist_snapshot(
                        self._build_snapshot(
                            prior_snapshot=snapshot,
                            state=state,
                            revision=revision,
                            recent_mutations=mutations,
                            spend_receipts=receipts,
                            producer_settlements=settlements,
                            compute_reservations=snapshot.compute_reservations,
                        )
                    )
                except OSError as exc:
                    raise BudgetLedgerSettlementOutcomeUnknownError(
                        event_id, payload_digest
                    ) from exc
                return written.producer_settlements[event_id]

    def resolve_producer_event(self, event_id: str) -> BudgetLedgerProducerRecord | None:
        """Read exact pending, unknown, or committed producer status."""
        event_id = _normalize_public_event_id(event_id, allow_engine_event=True)
        with (
            self._thread_lock,
            self._file_lock(exclusive=True, outcome_identity=(event_id, "readback")),
        ):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError(
                    "budget ledger requires explicit load_or_bootstrap before use"
                )
            if event_id in snapshot.compute_reservations:
                raise ValueError("budget_event_kind_conflict")
            record = snapshot.producer_settlements.get(event_id)
            digest = (
                (record.payload_digest or record.request_digest)
                if record is not None
                else "readback"
            )
            self._confirm_snapshot_durability(event_id, snapshot, payload_digest=digest)
            return record

    def list_producer_events_for_run(
        self,
        run_binding: BudgetLedgerProducerRunBinding,
    ) -> tuple[BudgetLedgerProducerRecord, ...]:
        """Read only producer records whose immutable run binding exactly matches."""
        if type(run_binding) is not BudgetLedgerProducerRunBinding:
            raise TypeError("producer_run_binding_must_be_typed")
        with self._thread_lock, self._file_lock(exclusive=True):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError(
                    "budget ledger requires explicit load_or_bootstrap before use"
                )
            self._confirm_snapshot_durability("ledger-snapshot", snapshot)
            records = (
                record
                for record in snapshot.producer_settlements.values()
                if record.run_binding == run_binding
            )
            return tuple(sorted(records, key=lambda record: (record.revision, record.event_id)))

    def resolve_spend(self, event_id: str) -> BudgetLedgerSpendReceipt | None:
        """Resolve a durable local receipt; absence is not an assertion of zero cost."""
        event_id = _normalize_public_event_id(event_id, allow_engine_event=True)
        with (
            self._thread_lock,
            self._file_lock(exclusive=True, outcome_identity=(event_id, "readback")),
        ):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError(
                    "budget ledger requires explicit load_or_bootstrap before use"
                )
            if event_id in snapshot.compute_reservations:
                raise ValueError("budget_event_kind_conflict")
            receipt = snapshot.spend_receipts.get(event_id)
            digest = receipt.payload_digest if receipt is not None else "readback"
            self._confirm_snapshot_durability(event_id, snapshot, payload_digest=digest)
            return receipt

    def _resource_identity(self, lock_fd: int) -> _BudgetResourceIdentity:
        """Measure the local directory entry and its actually locked inode."""
        try:
            directory = self._path.parent.stat()
            linked_lock = os.stat(self._lock_path, follow_symlinks=False)
            opened_lock = os.fstat(lock_fd)
            ledger_file = os.stat(self._path, follow_symlinks=False)
        except OSError as exc:
            if self._pending_owned_snapshot is not None:
                raise self._pending_outcome_unknown() from exc
            raise
        if (
            not stat.S_ISREG(linked_lock.st_mode)
            or not stat.S_ISREG(opened_lock.st_mode)
            or (linked_lock.st_dev, linked_lock.st_ino) != (opened_lock.st_dev, opened_lock.st_ino)
            or not stat.S_ISREG(ledger_file.st_mode)
        ):
            raise ValueError("budget_ledger_resource_identity_mismatch")
        return (
            directory.st_dev,
            directory.st_ino,
            self._path.name,
            opened_lock.st_dev,
            opened_lock.st_ino,
        )

    @contextmanager
    def _file_lock(
        self,
        *,
        exclusive: bool,
        require_concrete: bool = False,
        create_if_missing: bool = True,
        outcome_identity: tuple[str, str] | None = None,
    ) -> Iterator[int]:
        """Hold the stable lockfile for one complete read or publication."""
        try:
            import fcntl
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("fcntl is required for file budget ledger locking") from exc

        try:
            parent = self._path.parent.stat()
        except OSError as exc:
            if self._pending_owned_snapshot is not None:
                raise self._pending_outcome_unknown() from exc
            raise
        gate = _LEDGER_THREAD_GATES[
            hash((parent.st_dev, parent.st_ino, self._path.name)) % len(_LEDGER_THREAD_GATES)
        ]
        concrete = require_concrete or self._expected_resource_identity is not None
        flags = os.O_RDWR | getattr(os, "O_CLOEXEC", 0)
        if create_if_missing:
            flags |= os.O_CREAT
        if concrete:
            nofollow = getattr(os, "O_NOFOLLOW", 0)
            if not nofollow:
                raise RuntimeError("budget_ledger_no_follow_unavailable")
            flags |= nofollow
        with gate:
            try:
                fd = os.open(str(self._lock_path), flags, 0o644)
            except OSError as exc:
                if self._pending_owned_snapshot is not None:
                    raise self._pending_outcome_unknown() from exc
                raise
            outcome = (
                _LockedEventOutcome(*outcome_identity) if outcome_identity is not None else None
            )
            self._locked_event_outcome = outcome
            failure: BaseException | None = None
            try:
                fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
                if (
                    self._expected_resource_identity is not None
                    and self._resource_identity(fd) != self._expected_resource_identity
                ):
                    raise ValueError("budget_ledger_resource_identity_mismatch")
                yield fd
                if concrete:
                    identity = self._resource_identity(fd)
                    if (
                        self._expected_resource_identity is not None
                        and identity != self._expected_resource_identity
                    ):
                        raise ValueError("budget_ledger_resource_identity_mismatch")
            except BaseException as exc:
                failure = exc
            finally:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except BaseException as exc:
                    if failure is None:
                        failure = exc
                    else:
                        failure.add_note(f"budget lock release also failed: {exc!r}")
                try:
                    os.close(fd)
                except BaseException as exc:
                    if failure is None:
                        failure = exc
                    else:
                        failure.add_note(f"budget lock close also failed: {exc!r}")
                self._locked_event_outcome = None
            if failure is not None:
                if outcome is not None and (
                    outcome.published_snapshot is not None or outcome.acknowledged
                ):
                    if (
                        outcome.published_snapshot is not None
                        and self._strict_snapshot_anchor is not None
                    ):
                        self._pending_owned_snapshot = outcome.published_snapshot
                        self._pending_owned_identity = (outcome.event_id, outcome.payload_digest)
                    if isinstance(failure, BudgetLedgerSettlementOutcomeUnknownError):
                        if (failure.event_id, failure.payload_digest) == (
                            outcome.event_id,
                            outcome.payload_digest,
                        ):
                            raise failure
                        raise BudgetLedgerSettlementOutcomeUnknownError(
                            outcome.event_id, outcome.payload_digest
                        ) from failure
                    if isinstance(failure, Exception):
                        raise BudgetLedgerSettlementOutcomeUnknownError(
                            outcome.event_id, outcome.payload_digest
                        ) from failure
                    failure.add_note(
                        "budget settlement acknowledgment is unknown for event "
                        f"{outcome.event_id!r} with digest {outcome.payload_digest!r}"
                    )
                raise failure

    def _mutate(
        self,
        mutation_kind: Literal[
            "record_spend",
            "reserve",
            "release",
            "commit_reservation",
        ],
        key: str,
        amount: Decimal,
        *,
        provider: str | None = None,
        operation: Callable[[BudgetState], BudgetLedgerMutationResult],
    ) -> BudgetLedgerMutationResult:
        with self._thread_lock:
            with self._file_lock(exclusive=True):
                if self._strict_snapshot_anchor is not None:
                    raise ValueError("budget_ledger_unattributed_mutation_forbidden")
                snapshot = self._load_snapshot()
                if snapshot is None:
                    raise FileNotFoundError(
                        "budget ledger requires explicit load_or_bootstrap before use"
                    )
                snapshot = self._normalize_snapshot(snapshot)
                if mutation_kind in {"release", "commit_reservation"}:
                    identified_floor = sum(
                        (
                            record.reserved_amount
                            for record in snapshot.compute_reservations.values()
                            if record.status in {"reserved", "unknown"} and record.key == key
                        ),
                        Decimal(0),
                    )
                    available = snapshot.state.reserved.get(key, Decimal(0)) - identified_floor
                    if amount > available and identified_floor > 0:
                        raise ValueError("legacy_mutation_cannot_consume_identified_reservation")
                state = _branch_budget_state(snapshot.state)
                result = operation(state)
                revision = snapshot.revision + 1
                mutations = list(snapshot.recent_mutations)
                mutations.append(
                    self._build_mutation(
                        revision=revision,
                        operation=mutation_kind,
                        key=key,
                        amount=amount,
                        applied_amount=result.applied_amount,
                        provider=provider,
                        reserved=result.reserved,
                    )
                )
                written = self._persist_snapshot(
                    self._build_snapshot(
                        prior_snapshot=snapshot,
                        revision=revision,
                        state=state,
                        recent_mutations=tuple(mutations[-self._mutation_history_limit :]),
                        spend_receipts=snapshot.spend_receipts,
                        producer_settlements=snapshot.producer_settlements,
                        compute_reservations=snapshot.compute_reservations,
                    )
                )
                return BudgetLedgerMutationResult(
                    state=written.state,
                    revision=written.revision,
                    applied_amount=result.applied_amount,
                    reserved=result.reserved,
                )

    def _read_snapshot(self) -> BudgetLedgerSnapshot | None:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        return _decode_snapshot(raw)

    def _pending_outcome_unknown(self) -> BudgetLedgerSettlementOutcomeUnknownError:
        event_id, digest = self._pending_owned_identity or ("ledger-snapshot", "readback")
        return BudgetLedgerSettlementOutcomeUnknownError(event_id, digest)

    def _load_snapshot(self) -> BudgetLedgerSnapshot | None:
        try:
            snapshot = self._read_snapshot()
        except (OSError, ValueError) as exc:
            if self._pending_owned_snapshot is not None:
                raise self._pending_outcome_unknown() from exc
            raise
        if self._pending_owned_snapshot is not None:
            if snapshot != self._pending_owned_snapshot:
                raise self._pending_outcome_unknown()
            try:
                _fsync_dir(self._path.parent)
                confirmed = self._read_snapshot()
            except (OSError, ValueError) as exc:
                raise self._pending_outcome_unknown() from exc
            if confirmed != snapshot:
                raise self._pending_outcome_unknown()
            self._strict_snapshot_anchor = _snapshot_anchor(self._normalize_snapshot(snapshot))
            self._pending_owned_snapshot = None
            self._pending_owned_identity = None
        if snapshot is None:
            return None
        if self._require_existing and snapshot.ledger_id is None:
            raise ValueError("budget_ledger_identity_not_established")
        if (
            self._expected_ledger_id is not None
            and snapshot.ledger_id is not None
            and snapshot.ledger_id != self._expected_ledger_id
        ):
            raise ValueError("budget_ledger_identity_mismatch")
        if self._strict_snapshot_anchor is not None:
            normalized = self._normalize_snapshot(snapshot)
            current_anchor = _snapshot_anchor(normalized)
            legacy_16_match = (
                snapshot.schema_version not in {"1.7", _SNAPSHOT_VERSION}
                and not snapshot.invocation_profiles
                and not snapshot.invocation_unconfigured_runs
                and not snapshot.invocation_reservations
                and not snapshot.reentry_budget_windows
                and _legacy_snapshot_anchor_v16(normalized) == self._strict_snapshot_anchor
            )
            legacy_17_match = (
                snapshot.schema_version == "1.7"
                and not snapshot.reentry_budget_windows
                and _legacy_snapshot_anchor_v17(normalized) == self._strict_snapshot_anchor
            )
            if current_anchor != self._strict_snapshot_anchor and not (
                legacy_16_match or legacy_17_match
            ):
                raise ValueError("budget_ledger_snapshot_anchor_mismatch")
        return snapshot

    def _persist_snapshot(self, snapshot: BudgetLedgerSnapshot) -> BudgetLedgerSnapshot:
        normalized = self._normalize_snapshot(snapshot)
        payload = normalized.model_dump_json(by_alias=True, exclude_none=True, indent=2).encode(
            "utf-8"
        )
        # Constructor defaults are permitted for an explicit bootstrap only.
        # Every published byte record must also pass the strict persisted inlet.
        normalized = _decode_snapshot(payload.decode("utf-8"))
        temp_fd, temp_name = tempfile.mkstemp(
            prefix=f".{self._path.name}.tmp-",
            dir=self._path.parent,
        )
        replaced = False
        try:
            offset = 0
            while offset < len(payload):
                written = os.write(temp_fd, payload[offset:])
                if written <= 0:
                    raise OSError("budget ledger temporary write made no progress")
                offset += written
            os.fsync(temp_fd)
            os.close(temp_fd)
            temp_fd = -1
            os.replace(temp_name, self._path)
            replaced = True
            if self._locked_event_outcome is not None:
                self._locked_event_outcome.published_snapshot = normalized
            _fsync_dir(self._path.parent)
            if self._strict_snapshot_anchor is not None:
                try:
                    confirmed = self._read_snapshot()
                except (OSError, ValueError) as exc:
                    raise BudgetLedgerSettlementOutcomeUnknownError(
                        "ledger-snapshot", "readback"
                    ) from exc
                if confirmed != normalized:
                    raise BudgetLedgerSettlementOutcomeUnknownError("ledger-snapshot", "readback")
                self._strict_snapshot_anchor = _snapshot_anchor(normalized)
                self._pending_owned_snapshot = None
                self._pending_owned_identity = None
            return normalized
        except (OSError, BudgetLedgerSettlementOutcomeUnknownError):
            if replaced and self._strict_snapshot_anchor is not None:
                self._pending_owned_snapshot = normalized
                if self._locked_event_outcome is not None:
                    self._pending_owned_identity = (
                        self._locked_event_outcome.event_id,
                        self._locked_event_outcome.payload_digest,
                    )
            raise
        finally:
            if temp_fd >= 0:
                os.close(temp_fd)
            Path(temp_name).unlink(missing_ok=True)

    def _build_snapshot(
        self,
        *,
        prior_snapshot: BudgetLedgerSnapshot | None,
        state: BudgetState,
        revision: int = 0,
        recent_mutations: tuple[BudgetLedgerMutation, ...] | list[BudgetLedgerMutation] = (),
        spend_receipts: dict[str, BudgetLedgerSpendReceipt] | None = None,
        producer_settlements: dict[str, BudgetLedgerProducerRecord] | None = None,
        compute_reservations: dict[str, BudgetLedgerComputeReservation] | None = None,
        invocation_profiles: dict[str, BudgetLedgerInvocationProfile] | None = None,
        invocation_unconfigured_runs: dict[str, BudgetLedgerProducerRunBinding] | None = None,
        invocation_reservations: dict[str, BudgetLedgerInvocationReservation] | None = None,
        reentry_budget_windows: dict[str, BudgetLedgerReentryBudgetWindow] | None = None,
    ) -> BudgetLedgerSnapshot:
        return BudgetLedgerSnapshot(
            canonical_contract=_CANONICAL_LEDGER_CONTRACT,
            coordination_mode=_COORDINATION_MODE,
            ledger_id=(prior_snapshot.ledger_id if prior_snapshot is not None else None)
            or self._ledger_id,
            revision=revision,
            updated_at=datetime.now(UTC),
            last_writer=self._writer,
            recent_mutations=list(recent_mutations)[-self._mutation_history_limit :],
            state=state,
            spend_receipts=dict(spend_receipts or {}),
            producer_settlements=dict(producer_settlements or {}),
            compute_reservations=dict(compute_reservations or {}),
            invocation_profiles=dict(
                invocation_profiles
                if invocation_profiles is not None
                else prior_snapshot.invocation_profiles
                if prior_snapshot is not None
                else {}
            ),
            invocation_unconfigured_runs=dict(
                invocation_unconfigured_runs
                if invocation_unconfigured_runs is not None
                else prior_snapshot.invocation_unconfigured_runs
                if prior_snapshot is not None
                else {}
            ),
            invocation_reservations=dict(
                invocation_reservations
                if invocation_reservations is not None
                else prior_snapshot.invocation_reservations
                if prior_snapshot is not None
                else {}
            ),
            reentry_budget_windows=dict(
                reentry_budget_windows
                if reentry_budget_windows is not None
                else prior_snapshot.reentry_budget_windows
                if prior_snapshot is not None
                else {}
            ),
        )

    def _build_mutation(
        self,
        *,
        revision: int,
        operation: Literal[
            "bootstrap",
            "record_spend",
            "reserve",
            "release",
            "commit_reservation",
            "settle_spend",
            "begin_producer_event",
            "settle_producer_event",
            "reserve_compute",
            "settle_compute",
            "mark_compute_unknown",
            "configure_invocation_quota",
            "select_unconfigured_invocation_quota",
            "open_reentry_budget_window",
            "reserve_invocation",
            "finish_invocation",
        ],
        key: str | None = None,
        amount: Decimal | None = None,
        applied_amount: Decimal | None = None,
        provider: str | None = None,
        reserved: bool | None = None,
    ) -> BudgetLedgerMutation:
        return BudgetLedgerMutation(
            revision=revision,
            operation=operation,
            key=key,
            amount=amount,
            applied_amount=applied_amount,
            provider=provider,
            reserved=reserved,
            writer=self._writer,
        )

    def _normalize_snapshot(self, snapshot: BudgetLedgerSnapshot) -> BudgetLedgerSnapshot:
        return snapshot.model_copy(
            update={
                "canonical_contract": snapshot.canonical_contract or _CANONICAL_LEDGER_CONTRACT,
                "coordination_mode": snapshot.coordination_mode or _COORDINATION_MODE,
                "ledger_id": snapshot.ledger_id or self._ledger_id,
                "schema_version": _SNAPSHOT_VERSION,
            }
        )

    def _needs_contract_upgrade(self, snapshot: BudgetLedgerSnapshot) -> bool:
        return bool(
            snapshot.ledger_id is None
            or tuple(map(int, snapshot.schema_version.split("."))) < (1, 3)
            or snapshot.canonical_contract != _CANONICAL_LEDGER_CONTRACT
            or snapshot.coordination_mode != _COORDINATION_MODE
        )


def _branch_budget_state(state: BudgetState) -> BudgetState:
    """Copy only the mutable budget maps before one ledger mutation."""

    branched = state.model_copy(deep=False)
    branched.limits = dict(state.limits)
    branched.spent = dict(state.spent)
    branched.provider_spent = dict(state.provider_spent)
    branched.reserved = dict(state.reserved)
    return branched


def _default_ledger_id(path: Path) -> str:
    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()
    return f"ledger:{digest[:16]}"
