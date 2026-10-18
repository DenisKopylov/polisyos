"""Typed read contract for durable pre-admission provider attempts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .control import ExecutionProfile
from .runtime import ApiMeta

CONTROL_PRE_ADMISSION_SETTLEMENT_REQUIRED_PROFILES: frozenset[str] = frozenset(
    {"research", "governed", "production"}
)

ControlPreAdmissionAttemptStatus = Literal[
    "started", "settled", "admitted", "refused", "cancelled", "failed"
]
ProducerCallState = Literal["not_applicable", "no_call", "complete", "unavailable"]
ControlPreAdmissionEventObservation = ProducerCallState
NoCallReason = Literal["producer_run_binding_not_established", "provider_preflight_not_started"]

PRODUCER_CALL_STATE_VALUES = frozenset(get_args(ProducerCallState))
NO_CALL_REASON_VALUES = frozenset(get_args(NoCallReason))


def validate_producer_call_observation(state: object, reason: object) -> None:
    """Require the one canonical producer-call state/reason combination."""
    if not isinstance(state, str) or state not in PRODUCER_CALL_STATE_VALUES:
        raise ValueError("control_pre_admission_observation_invalid")
    if state == "no_call":
        if not isinstance(reason, str) or reason not in NO_CALL_REASON_VALUES:
            raise ValueError("control_pre_admission_no_call_reason_invalid")
    elif reason is not None:
        raise ValueError("control_pre_admission_no_call_reason_unexpected")


class ControlPreAdmissionAttemptEventInfo(BaseModel):
    """Describe one append-only observation of a billable launch attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    event_type: ControlPreAdmissionAttemptStatus
    observed_at: datetime
    producer_event_ids: list[str] = Field(default_factory=list)
    producer_event_observation: ControlPreAdmissionEventObservation = "not_applicable"
    producer_no_call_reason: NoCallReason | None = None
    failure_code: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._-]{1,96}$")
    job_id: str | None = None

    @model_validator(mode="after")
    def require_bound_no_call_reason(self) -> Self:
        validate_producer_call_observation(
            self.producer_event_observation, self.producer_no_call_reason
        )
        if (
            self.producer_no_call_reason is not None
            and self.failure_code != self.producer_no_call_reason
        ):
            raise ValueError("control_pre_admission_no_call_reason_failure_code_mismatch")
        return self


class ControlPreAdmissionOwnerBinding(BaseModel):
    """Expose the durable shared-owner identity used to authorize recovery."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    purpose: Literal["control.nl_pre_admission.v1"]
    scope_kind: Literal["route"]
    scope_id: Literal["control.runs.nl"]
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    actor_subject_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    run_id: str = Field(min_length=1)
    intent_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    body_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_content_sha256: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    effective_execution_profile: ExecutionProfile


class ControlPreAdmissionAttemptResponse(BaseModel):
    """Return the current attempt owner and its durable observation history."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: ApiMeta
    owner_binding: ControlPreAdmissionOwnerBinding
    attempt_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    intent_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: ControlPreAdmissionAttemptStatus
    run_id: str = Field(min_length=1)
    job_id: str | None = None
    effective_execution_profile: ExecutionProfile
    producer_event_ids: list[str] = Field(default_factory=list)
    producer_event_observation: ControlPreAdmissionEventObservation = "not_applicable"
    producer_no_call_reason: NoCallReason | None = None
    failure_code: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._-]{1,96}$")
    created_at: datetime
    updated_at: datetime
    history: list[ControlPreAdmissionAttemptEventInfo] = Field(min_length=1)

    @model_validator(mode="after")
    def require_current_no_call_reason(self) -> Self:
        validate_producer_call_observation(
            self.producer_event_observation, self.producer_no_call_reason
        )
        if (
            self.producer_no_call_reason is not None
            and self.failure_code != self.producer_no_call_reason
        ):
            raise ValueError("control_pre_admission_no_call_reason_failure_code_mismatch")
        if self.history[-1].producer_no_call_reason != self.producer_no_call_reason:
            raise ValueError("control_pre_admission_current_no_call_reason_history_mismatch")
        return self
