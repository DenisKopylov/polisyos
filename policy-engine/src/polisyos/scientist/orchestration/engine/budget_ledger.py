"""File-backed budget ledger for distributed-safe Scientist budget accounting."""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import tempfile
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.llm.cache_settlement import CacheSettlementSession
from polisyos.core.llm.settlement import LLMProducerEvent
from polisyos.scientist.orchestration.engine.budget import BudgetState

_CANONICAL_LEDGER_CONTRACT = "scientist.multi_host_budget_ledger.v1"
_COORDINATION_MODE = "shared_posix_file_lock"
_SNAPSHOT_VERSION = "1.6"

__all__ = [
    "BudgetLedger",
    "BudgetLedgerMutation",
    "BudgetLedgerMutationResult",
    "BudgetLedgerSnapshot",
    "BudgetLedgerComputeReservation",
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

    def __init__(self, event_id: str, payload_digest: str) -> None:
        self.event_id = event_id
        self.payload_digest = payload_digest
        super().__init__(
            f"budget settlement outcome unknown for event {event_id!r}; "
            "resolve or retry the same event before assuming any charge outcome"
        )


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
        _SNAPSHOT_VERSION,
    }:
        raise ValueError("budget ledger schema_version is missing or unsupported")
    if (
        value.get("canonical_contract") != _CANONICAL_LEDGER_CONTRACT
        or value.get("coordination_mode") != _COORDINATION_MODE
    ):
        raise ValueError("budget ledger contract or coordination mode is unsupported")
    _require_wire_fields(
        value,
        _PERSISTED_SNAPSHOT_SCHEMA,
        _PERSISTED_SNAPSHOT_SCHEMA.get("$defs", {}),
        version=version,
    )
    snapshot = BudgetLedgerSnapshot.model_validate_json(raw, strict=True)
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
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        self._thread_lock = threading.Lock()
        self._ledger_id = str(ledger_id or _default_ledger_id(self._path))
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
        with self._file_lock(exclusive=False):
            snapshot = self._load_snapshot()
        if snapshot is None:
            raise FileNotFoundError("budget ledger requires explicit load_or_bootstrap before use")
        return snapshot.state

    @property
    def settlement_owner_identity(self) -> tuple[str, str, str]:
        """Return the persisted owner/contract identity for producer cache isolation."""
        with self._file_lock(exclusive=False):
            snapshot = self._load_snapshot()
        if snapshot is None:
            raise FileNotFoundError("budget ledger requires explicit load_or_bootstrap before use")
        if snapshot.ledger_id is None:
            raise ValueError("durable settlement owner requires a persisted ledger identity")
        return snapshot.ledger_id, snapshot.canonical_contract, snapshot.coordination_mode

    def snapshot(self) -> BudgetLedgerSnapshot:
        with self._file_lock(exclusive=False):
            snapshot = self._load_snapshot()
        if snapshot is None:
            raise FileNotFoundError("budget ledger requires explicit load_or_bootstrap before use")
        return self._normalize_snapshot(snapshot)

    def load_or_bootstrap(self, initial_state: BudgetState) -> BudgetState:
        with self._thread_lock:
            with self._file_lock(exclusive=True):
                snapshot = self._load_snapshot()
                if snapshot is None:
                    snapshot = self._persist_snapshot(
                        self._build_snapshot(
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
        candidate = BudgetLedgerComputeReservation(
            event_id=event_id,
            request_digest=request_digest,
            key=key,
            reserved_amount=amount,
            status="reserved",
            revision=0,
        )
        with self._thread_lock, self._file_lock(exclusive=True):
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
                self._confirm_compute_durability(event_id, snapshot)
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
        if type(amount) is not Decimal or not amount.is_finite() or amount < 0:
            raise ValueError("compute_actual_cost_must_be_finite_and_nonnegative")
        if re.fullmatch(r"[0-9a-f]{64}", settlement_digest) is None:
            raise ValueError("compute_settlement_digest_invalid")
        with self._thread_lock, self._file_lock(exclusive=True):
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
                self._confirm_compute_durability(event_id, snapshot)
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
        with self._thread_lock, self._file_lock(exclusive=True):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError("budget ledger requires explicit bootstrap")
            existing = snapshot.compute_reservations.get(event_id)
            if existing is None or existing.request_digest != request_digest:
                raise ValueError("compute_reservation_missing_or_conflicting")
            if existing.status == "settled":
                raise ValueError("compute_settlement_already_known")
            if existing.status == "unknown":
                self._confirm_compute_durability(event_id, snapshot)
                return existing
            revision = snapshot.revision + 1
            record = existing.model_copy(update={"status": "unknown", "revision": revision})
            records = dict(snapshot.compute_reservations)
            records[event_id] = record
            try:
                written = self._persist_snapshot(
                    self._build_snapshot(
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

    def _confirm_compute_durability(self, event_id: str, snapshot: BudgetLedgerSnapshot) -> None:
        try:
            _fsync_dir(self._path.parent)
            confirmed = self._load_snapshot()
        except OSError as exc:
            raise BudgetLedgerSettlementOutcomeUnknownError(event_id, "readback") from exc
        if confirmed != snapshot:
            raise BudgetLedgerSettlementOutcomeUnknownError(event_id, "readback")

    def resolve_compute(self, event_id: str) -> BudgetLedgerComputeReservation | None:
        """Reread this owner's durable record; absent does not prove zero work."""
        with self._thread_lock, self._file_lock(exclusive=True):
            snapshot = self._load_snapshot()
            if snapshot is None:
                raise FileNotFoundError("budget ledger requires explicit bootstrap")
            if event_id not in snapshot.compute_reservations and (
                event_id in snapshot.spend_receipts or event_id in snapshot.producer_settlements
            ):
                raise ValueError("budget_event_kind_conflict")
            self._confirm_compute_durability(event_id, snapshot)
            return snapshot.compute_reservations.get(event_id)

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
        candidate = BudgetLedgerSpendReceipt(
            event_id=event_id,
            payload_digest=payload_digest,
            key=key,
            amount=amount,
            provider=provider,
            revision=1,
        )
        with self._thread_lock:
            with self._file_lock(exclusive=True):
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
                            state=state,
                            revision=revision,
                            recent_mutations=mutations,
                            spend_receipts=receipts,
                            producer_settlements=snapshot.producer_settlements,
                            compute_reservations=snapshot.compute_reservations,
                        )
                    )
                except OSError as exc:
                    raise BudgetLedgerSettlementOutcomeUnknownError(
                        event_id, payload_digest
                    ) from exc
                return written.spend_receipts[event_id]

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
        with self._thread_lock:
            with self._file_lock(exclusive=True):
                snapshot = self._load_snapshot()
                if snapshot is None:
                    raise FileNotFoundError(
                        "budget ledger requires explicit load_or_bootstrap before use"
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
            with self._file_lock(exclusive=True):
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
        with self._file_lock(exclusive=False):
            snapshot = self._load_snapshot()
        if snapshot is None:
            raise FileNotFoundError("budget ledger requires explicit load_or_bootstrap before use")
        if event_id in snapshot.compute_reservations:
            raise ValueError("budget_event_kind_conflict")
        return snapshot.producer_settlements.get(event_id)

    def list_producer_events_for_run(
        self,
        run_binding: BudgetLedgerProducerRunBinding,
    ) -> tuple[BudgetLedgerProducerRecord, ...]:
        """Read only producer records whose immutable run binding exactly matches."""
        if type(run_binding) is not BudgetLedgerProducerRunBinding:
            raise TypeError("producer_run_binding_must_be_typed")
        with self._file_lock(exclusive=False):
            snapshot = self._load_snapshot()
        if snapshot is None:
            raise FileNotFoundError("budget ledger requires explicit load_or_bootstrap before use")
        records = (
            record
            for record in snapshot.producer_settlements.values()
            if record.run_binding == run_binding
        )
        return tuple(sorted(records, key=lambda record: (record.revision, record.event_id)))

    def resolve_spend(self, event_id: str) -> BudgetLedgerSpendReceipt | None:
        """Resolve a durable local receipt; absence is not an assertion of zero cost."""
        with self._file_lock(exclusive=False):
            snapshot = self._load_snapshot()
        if snapshot is None:
            raise FileNotFoundError("budget ledger requires explicit load_or_bootstrap before use")
        if event_id in snapshot.compute_reservations:
            raise ValueError("budget_event_kind_conflict")
        return snapshot.spend_receipts.get(event_id)

    @contextmanager
    def _file_lock(self, *, exclusive: bool) -> Iterator[None]:
        """Hold the stable lockfile for one complete read or publication."""
        try:
            import fcntl
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("fcntl is required for file budget ledger locking") from exc

        fd = os.open(str(self._lock_path), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

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

    def _load_snapshot(self) -> BudgetLedgerSnapshot | None:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        return _decode_snapshot(raw)

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
            _fsync_dir(self._path.parent)
            return normalized
        finally:
            if temp_fd >= 0:
                os.close(temp_fd)
            Path(temp_name).unlink(missing_ok=True)

    def _build_snapshot(
        self,
        *,
        state: BudgetState,
        revision: int = 0,
        recent_mutations: tuple[BudgetLedgerMutation, ...] | list[BudgetLedgerMutation] = (),
        spend_receipts: dict[str, BudgetLedgerSpendReceipt] | None = None,
        producer_settlements: dict[str, BudgetLedgerProducerRecord] | None = None,
        compute_reservations: dict[str, BudgetLedgerComputeReservation] | None = None,
    ) -> BudgetLedgerSnapshot:
        return BudgetLedgerSnapshot(
            canonical_contract=_CANONICAL_LEDGER_CONTRACT,
            coordination_mode=_COORDINATION_MODE,
            ledger_id=self._ledger_id,
            revision=revision,
            updated_at=datetime.now(UTC),
            last_writer=self._writer,
            recent_mutations=list(recent_mutations)[-self._mutation_history_limit :],
            state=state,
            spend_receipts=dict(spend_receipts or {}),
            producer_settlements=dict(producer_settlements or {}),
            compute_reservations=dict(compute_reservations or {}),
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
