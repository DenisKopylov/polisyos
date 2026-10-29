"""Explicit candidate capture scope; product N4 CAS call models stay unchanged."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.common.producer_request import parse_producer_request_context as _parse_context
from polisyos.core.llm import LLMProducerEvent
from polisyos.core.llm import (
    capture_llm_usage_observation as _capture_usage_observation,
)
from polisyos.core.llm import (
    parse_llm_usage_quantity as _usage_quantity,
)
from polisyos.pdc import gy_content_hash

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from polisyos.core.llm.cache_settlement import CacheSettlementSession


class _BillableUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    usage_status: Literal["known", "missing", "invalid"]


class _NormalizedOriginUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    prompt_tokens: int | None = Field(ge=0)
    completion_tokens: int | None = Field(ge=0)
    usage_status: Literal["known", "missing", "invalid"]


class _SettlementObservation(BaseModel):
    """Consistent captured owner-event bytes; not an external execution signature."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    event_id: str
    request_digest: str
    response_utf8_sha256: str
    model: str
    provider: str
    kind: Literal["provider", "reuse"]
    cost_origin: Literal["reported", "estimated", "reuse", "unknown"]
    origin_event_id: str | None
    payload_digest: str
    amount: str | None
    ack_status: Literal["committed", "unknown", "unmanaged"] | None

    @model_validator(mode="after")
    def _event_bytes_bind(self) -> Self:
        try:
            amount = Decimal(self.amount) if self.amount is not None else None
        except InvalidOperation as error:
            raise ValueError("captured_usage_event_amount_invalid") from error
        event = LLMProducerEvent(
            event_id=self.event_id,
            request_digest=self.request_digest,
            response_digest=self.response_utf8_sha256,
            model=self.model,
            provider=self.provider,
            kind=self.kind,
            cost_origin=self.cost_origin,
            origin_event_id=self.origin_event_id,
            amount=amount,
        )
        if event.payload_digest != self.payload_digest:
            raise ValueError("captured_usage_event_content_mismatch")
        return self


class _UsageObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    usage_source: Literal["response_payload", "normalized_object_only"]
    provider_usage: Any
    provider_usage_present: bool
    provider_top_usage: dict[str, Any]
    provider_usage_status: Literal["known", "missing", "invalid"]
    provider_total_basis: Literal["reported", "derived", "unavailable"]
    normalized_origin_usage: _NormalizedOriginUsage | None
    billable_usage: _BillableUsage
    source_cost_origin: Literal["reported", "estimated", "reuse", "unknown"] | None
    source_was_reuse: bool
    reuse_verification: Literal["verified_live_core_session", "not_established"]
    settlement: _SettlementObservation | None

    @model_validator(mode="after")
    def _availability_is_recomputed(self) -> Self:
        quantity = _usage_quantity(
            self.provider_usage,
            self.provider_top_usage,
            nested_usage_present=self.provider_usage_present,
        )
        if (quantity.status, quantity.total_basis) != (
            self.provider_usage_status,
            self.provider_total_basis,
        ):
            raise ValueError("captured_usage_observation_mismatch")
        if self.settlement is not None:
            if self.source_cost_origin != self.settlement.cost_origin:
                raise ValueError("captured_usage_cost_origin_mismatch")
            if self.settlement.kind == "reuse" and not self.source_was_reuse:
                raise ValueError("captured_usage_reuse_downgraded_to_provider")
        return self


class CallUsageEvidenceV2(BaseModel):
    """Content-bound capture input facts, not historical billing authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["policyos.testing.n4_call_usage.v2"] = (
        "policyos.testing.n4_call_usage.v2"
    )
    call_index: int = Field(ge=0)
    call_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    prompt_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    response_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    response_utf8_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_id: str = Field(min_length=1)
    producer_context: dict[str, Any] | None
    observation: _UsageObservation
    quantity_verification: Literal["recomputed_from_bound_usage_payload"] = (
        "recomputed_from_bound_usage_payload"
    )
    capture_execution_provenance: Literal["not_established_by_this_artifact"] = (
        "not_established_by_this_artifact"
    )
    authority_scope: Literal["candidate_capture_input_not_billing_authority"] = (
        "candidate_capture_input_not_billing_authority"
    )

    @model_validator(mode="after")
    def _context_shape_is_bound(self) -> Self:
        if self.producer_context is not None:
            from polisyos.scientist import validate_n4_producer_context as _check_n4_context

            context = _check_n4_context(_parse_context(self.producer_context, sealed=False))
            if context["model_id"] != self.model_id:
                raise ValueError("captured_usage_context_model_mismatch")
        return self


@dataclass
class _UsageCapture:
    calls: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[CallUsageEvidenceV2] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)


_CAPTURE: ContextVar[_UsageCapture | None] = ContextVar("n4_usage_capture", default=None)


@contextmanager
def capture_call_usage() -> Iterator[_UsageCapture]:
    """Collect only inside an explicitly selected capture task; reset on every exit."""
    capture = _UsageCapture()
    token = _CAPTURE.set(capture)
    try:
        yield capture
    finally:
        _CAPTURE.reset(token)


def _observe_call(
    call: Mapping[str, Any],
    response: object,
    *,
    producer_context: Mapping[str, Any] | None,
    cache_settlement_session: CacheSettlementSession | None,
) -> None:
    capture = _CAPTURE.get()
    if capture is None:
        return
    payload = dict(call)
    raw = str(payload["raw_llm_response"])
    capture.calls.append(payload)
    observation = _capture_usage_observation(
        response, cache_settlement_session=cache_settlement_session
    )
    try:
        evidence = CallUsageEvidenceV2(
            call_index=payload["call_index"],
            call_content_hash=gy_content_hash(payload),
            prompt_hash=payload["prompt_hash"],
            response_content_hash=gy_content_hash(raw),
            response_utf8_sha256=hashlib.sha256(raw.encode()).hexdigest(),
            model_id=payload["model_id"],
            producer_context=dict(producer_context) if producer_context is not None else None,
            observation=observation,
        )
    except Exception:
        capture.failures.append(
            {"call_content_hash": gy_content_hash(payload), "observation": observation}
        )
        raise
    capture.evidence.append(evidence)
