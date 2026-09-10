"""Constrained candidate E/X/V/C transitions composed through CR1 durable custody.

GY-CR2 consumes the VC1 vocabulary and CR1 public submit/process/snapshot APIs.
One documented intra-Runtime exact-key discovery seam calls CR1's existing private
lookup; it discovers tickets only. Substantive state always comes from snapshot.
No external action, equivalence, restart or institutional appointment is admitted.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from polisyos.fabric import file_lock
from polisyos.runtime.quality.adaptation_transition import (
    REQUEST_TOPIC,
    AdaptationTransitionRequest,
    AdaptationTransitionRuntime,
    CandidateOperationCharter,
)
from polisyos.runtime.quality.vocabulary_crosswalk import (
    ClaimFactor,
    EpistemicFactor,
    ExposureFactor,
    InterventionFactor,
    MovementClass,
    require_canonical_movement,
)

if TYPE_CHECKING:
    from pathlib import Path

type _Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
type Operation = Literal[
    "observe",
    "early_warning",
    "diagnose",
    "refresh",
    "recompute",
    "recalibrate",
    "adjust_implementation",
    "narrow_scope",
    "partial_reissue",
    "pause",
    "rollback",
    "redesign",
    "terminate",
    "restart",
]
SCHEMA_VERSION = "response-state.v1"


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")


class ResponseFactors(_Record):
    """Candidate coordinates from the single source-owned vocabulary."""

    E: EpistemicFactor
    X: ExposureFactor
    V: InterventionFactor
    C: ClaimFactor


class ResponseObservation(_Record):
    """Candidate observation discriminators, never certified empirical evidence."""

    movement: float = Field(allow_inf_nan=False)
    maturity: Literal["mature", "immature", "unknown"]
    health: Literal["valid", "invalid", "unknown"]
    expected_denominator: int = Field(ge=0)
    observed_denominator: int = Field(ge=0)
    subgroup_blocked: bool = False


class ResponseEvent(_Record):
    """Exact candidate event and claim identity crossing the custody boundary."""

    event_id: _Text
    aggregate_id: _Text
    sequence: int = Field(ge=0)
    previous_ticket: _Text | None = None
    observed_at: AwareDatetime
    valid_at: AwareDatetime
    contract_ref: _Text
    claim_ref: _Text
    population_ref: _Text
    intervention_version: _Text
    measurement_epoch: _Text
    current: ResponseFactors
    requested: ResponseFactors
    operation: Operation
    movement_vocabulary: _Text = "SMDV-1@1"
    movement: MovementClass
    observation: ResponseObservation
    charter_ref: _Text | None = None
    waiting_harm: Literal["high", "low", "unknown"] = "unknown"
    premature_loss: Literal["high", "low", "unknown"] = "unknown"
    reversibility: Literal["reversible", "limited", "irreversible", "unknown"] = "unknown"
    blast_radius: Literal["bounded", "wide", "unknown"] = "unknown"
    declared_owner: _Text | None = None
    appointed_signer: None = None
    after_hours_substitute: None = None
    equivalence_evidence: None = None
    restart_evidence: None = None
    external_continuation_ref: _Text | None = None
    restart_candidate_ref: _Text | None = None
    execution_candidate_ref: _Text | None = None
    requested_version: _Text | None = None
    requested_measurement_epoch: _Text | None = None
    legal_deadline: AwareDatetime | None = None
    learning_requested: bool = False
    world_write_requested: bool = False


class ResponseAssessment(_Record):
    """Recomputed candidate conformance; no field carries external permission."""

    product_violations: tuple[str, ...]
    reasons: tuple[str, ...]
    candidate_admissible: bool
    custody_factors: ResponseFactors
    protective_containment_required: bool
    conservative_posture: Literal["no_authority_expansion"] = "no_authority_expansion"
    execution_authorized: Literal[False] = False
    external_executed: Literal[False] = False
    posterior_learning_allowed: Literal[False] = False
    world_write_allowed: Literal[False] = False
    claim_dependent_continuation: Literal[False] = False
    external_continuation_observed: bool


class ResponseReceipt(_Record):
    """Persisted CR1 readback with coordinates beside the unchanged status."""

    ticket: str
    request_ref: str
    decision_ref: str | None
    status: Literal["pending", "failed_safe"]
    event: ResponseEvent
    assessment: ResponseAssessment
    previous_ticket: str | None
    reaction: Literal["initial", "appended", "correction_opened"]
    execution_authorized: Literal[False] = False


class ResponsePacket(_Record):
    """Immutable multi-event corpus input, with no expected outputs attached."""

    scenario_id: str
    family: str
    proxy_dimension: str | None
    description: str
    events: tuple[ResponseEvent, ...] = Field(min_length=2)


class ResponseCorpus(_Record):
    """Versioned corpus carrier decoded independently of the oracle."""

    version: Literal["response-corpus.v1"]
    packets: tuple[ResponsePacket, ...]


def decode_packet(raw: bytes) -> ResponseCorpus:
    """Decode raw corpus through Pydantic-core, without the oracle JSON decoder."""
    return ResponseCorpus.model_validate_json(raw)


def assess_response(event: ResponseEvent) -> ResponseAssessment:
    """Recompute every candidate predicate; missing authority always stays missing."""
    event = ResponseEvent.model_validate(event.model_dump(mode="json"))
    require_canonical_movement(event.movement_vocabulary, event.movement)
    target = event.requested
    violations: list[str] = []
    if target.V == "V2" and target.C == "C0":
        violations.append("FCT-01")
    if target.E == "E4" and target.X == "X4" and target.C == "C0":
        violations.append("FCT-02")
    if target.V == "V4" and target.X == "X0":
        violations.append("FCT-03")
    if target.V == "V3" and target.C == "C0":
        violations.append("redesign_claim_inheritance")
    reasons = list(violations)
    obs = event.observation
    if obs.maturity != "mature":
        reasons.append("observation_not_mature")
    if obs.health != "valid":
        reasons.append("measurement_not_valid")
    if obs.expected_denominator != obs.observed_denominator:
        reasons.append("denominator_changed")
    if obs.subgroup_blocked:
        reasons.append("subgroup_guardrail_block")
    if event.charter_ref is None:
        reasons.append("transition_charter_missing")
    high_harm = event.waiting_harm == "high"
    reasons.append("protective_containment_required" if high_harm else "investigation_only")
    if event.premature_loss == "high":
        reasons.append("premature_action_loss_unresolved")
    if event.reversibility == "irreversible":
        reasons.append("irreversible_response_review")
    if event.blast_radius == "wide":
        reasons.append("wide_blast_radius_review")
    if event.learning_requested:
        reasons.append("posterior_learning_not_admitted")
    if event.world_write_requested:
        reasons.append("world_write_not_admitted")
    if (
        event.operation in {"adjust_implementation", "partial_reissue", "redesign", "terminate"}
        and event.movement == "diagnosis_unresolved"
    ):
        reasons.append("diagnosis_unresolved_for_action")
    reasons.append(
        "owner_label_not_appointment"
        if event.declared_owner
        else "institutional_signer_not_established"
    )
    if event.operation == "restart":
        reasons.append(
            "restart_candidate_unverified"
            if event.restart_candidate_ref
            else "alert_disappearance_not_restart"
        )
    version_changed = (
        event.requested_version is not None
        and event.requested_version != event.intervention_version
    )
    epoch_changed = (
        event.requested_measurement_epoch is not None
        and event.requested_measurement_epoch != event.measurement_epoch
    )
    version_reuse = (version_changed or epoch_changed) and target.C == "C0"
    if version_reuse:
        reasons.append("version_identity_reused")
    if target.C == "C3" and target.X != "X4":
        reasons.append(
            "external_continuation_basis_unverified"
            if event.external_continuation_ref
            else "external_continuation_basis_not_established"
        )
    if event.legal_deadline is not None and event.valid_at >= event.legal_deadline:
        reasons.append("legal_review_clock_elapsed")
    if event.execution_candidate_ref:
        reasons.append("execution_receipt_unverified")
    exposure_order = tuple(ExposureFactor)
    expansion = exposure_order.index(target.X) < exposure_order.index(event.current.X)
    if expansion:
        reasons.append("exposure_expansion_without_restart")
    admissible = (
        not violations and not version_reuse and not expansion and event.operation != "restart"
    )
    return ResponseAssessment(
        product_violations=tuple(violations),
        reasons=tuple(reasons),
        candidate_admissible=admissible,
        custody_factors=target if admissible else event.current,
        protective_containment_required=high_harm,
        external_continuation_observed=event.external_continuation_ref is not None,
    )


class ConstrainedResponseRuntime:
    """Append one aggregate's candidate states through the existing CR1 machine.

    Args:
        custody: Existing CR1 runtime with its own persistence/identity owners.
        root: Local lock root shared by all cooperating writers of this aggregate.
        tenant_id: Exact tenant bound to the underlying CR1 runtime.
        cell_id: Exact cell bound to the underlying CR1 runtime.
    """

    def __init__(
        self, *, custody: AdaptationTransitionRuntime, root: Path, tenant_id: str, cell_id: str
    ) -> None:
        self.custody = custody
        self.root = root
        self.tenant_id = tenant_id
        self.cell_id = cell_id

    @classmethod
    def open(cls, *, root: Path, tenant_id: str, cell_id: str) -> Self:
        """Open CR1's real local owner composition, without another state store."""
        return cls(
            custody=AdaptationTransitionRuntime.open(
                root=root, tenant_id=tenant_id, cell_id=cell_id
            ),
            root=root,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )

    def _request(self, event: ResponseEvent) -> AdaptationTransitionRequest:
        return AdaptationTransitionRequest(
            request_id=f"{SCHEMA_VERSION}:{event.aggregate_id}:{event.sequence}",
            tenant_id=self.tenant_id,
            cell_id=self.cell_id,
            contract_ref=event.contract_ref,
            signal_refs=(event.event_id,),
            diagnosis_refs=(event.movement.value,),
            observed_at=event.observed_at,
            current_context={"schema": SCHEMA_VERSION, "factors": event.current.model_dump_json()},
            requested_context={"schema": SCHEMA_VERSION, "event": event.model_dump_json()},
            charter=CandidateOperationCharter(
                action_description=f"Candidate {event.operation}",
                required_signer_role="appointed_response_authority",
                escalation_after_seconds=60,
                provenance_refs=("AUD-F06", "AUD-F08", "WP-08"),
            ),
            intended_claim_consequence="candidate conformance only; protected response withheld",
            provenance_refs=(SCHEMA_VERSION, event.claim_ref),
        )

    def _slot(self, event: ResponseEvent, sequence: int) -> str | None:
        # CR1-internal discovery only; fail on API absence, never guess an empty head.
        request = self._request(event.model_copy(update={"sequence": sequence}))
        row = self.custody._by_key(REQUEST_TOPIC, self.custody._request_key(request))
        return None if row is None else row.event_id

    def append(self, event: ResponseEvent) -> ResponseReceipt:
        """Admit one contiguous append or reconcile an exact duplicate, under lock."""
        event = ResponseEvent.model_validate(event.model_dump(mode="json"))
        assess_response(event)
        key = hashlib.sha256(
            f"{self.tenant_id}:{self.cell_id}:{event.aggregate_id}".encode()
        ).hexdigest()
        with file_lock(self.root / "response-locks" / f"{key}.lock"):
            history: list[ResponseReceipt] = []
            while (ticket := self._slot(event, len(history))) is not None:
                prior = self.read(ticket)
                if (
                    prior.event.sequence != len(history)
                    or prior.event.aggregate_id != event.aggregate_id
                ):
                    raise ValueError("response_history_identity_invalid")
                if prior.previous_ticket != (history[-1].ticket if history else None):
                    raise ValueError("response_history_chain_invalid")
                history.append(prior)
            if event.sequence < len(history):
                prior = history[event.sequence]
                if prior.event != event:
                    raise ValueError("response_identity_conflict")
                self.custody.process(prior.ticket)
                return self.read(prior.ticket)
            if event.sequence != len(history):
                raise ValueError("response_sequence_gap")
            predecessor = history[-1] if history else None
            self._check_predecessor(event, predecessor)
            ticket = self.custody.submit(self._request(event))
            self.custody.process(ticket)
            return self.read(ticket)

    @staticmethod
    def _check_predecessor(event: ResponseEvent, prior: ResponseReceipt | None) -> None:
        if event.previous_ticket != (prior.ticket if prior else None):
            raise ValueError("response_predecessor_mismatch")
        if prior is None:
            check = assess_response(event.model_copy(update={"requested": event.current}))
            if check.product_violations:
                raise ValueError("response_initial_state_forbidden")
            return
        for name in ("contract_ref", "claim_ref", "population_ref"):
            if getattr(event, name) != getattr(prior.event, name):
                raise ValueError("response_claim_identity_fork")
        if (
            event.aggregate_id != prior.event.aggregate_id
            or event.sequence != prior.event.sequence + 1
        ):
            raise ValueError("response_history_identity_invalid")
        if event.current != prior.assessment.custody_factors:
            raise ValueError("response_current_state_mismatch")
        version = prior.event.requested_version or prior.event.intervention_version
        epoch = prior.event.requested_measurement_epoch or prior.event.measurement_epoch
        if not prior.assessment.candidate_admissible:
            version, epoch = prior.event.intervention_version, prior.event.measurement_epoch
        if event.intervention_version != version or event.measurement_epoch != epoch:
            raise ValueError("response_version_identity_fork")

    def read(self, ticket: str) -> ResponseReceipt:
        """Recompute factor state from CR1's content-checked public audit readback."""
        snapshot = self.custody.snapshot(ticket, as_of=datetime.now(UTC))
        if snapshot.requested_context.get("schema") != SCHEMA_VERSION:
            raise ValueError("response_context_schema_invalid")
        event = ResponseEvent.model_validate_json(snapshot.requested_context["event"])
        assessment = assess_response(event)
        if self._slot(event, event.sequence) != ticket:
            raise ValueError("response_ticket_identity_invalid")
        if (event.sequence == 0) != (event.previous_ticket is None):
            raise ValueError("response_predecessor_mismatch")
        if snapshot.contract_ref != event.contract_ref:
            raise ValueError("response_contract_binding_invalid")
        if snapshot.current_context != {
            "schema": SCHEMA_VERSION,
            "factors": event.current.model_dump_json(),
        }:
            raise ValueError("response_context_binding_invalid")
        reaction = "initial" if event.previous_ticket is None else "appended"
        prior = None
        if event.previous_ticket is not None:
            expected_previous = self._slot(event, event.sequence - 1)
            if expected_previous != event.previous_ticket:
                raise ValueError("response_predecessor_mismatch")
            prior = self.read(event.previous_ticket)
            if event.observed_at < prior.event.observed_at:
                reaction = "correction_opened"
        self._check_predecessor(event, prior)
        return ResponseReceipt(
            ticket=ticket,
            request_ref=snapshot.request_ref,
            decision_ref=snapshot.decision_ref,
            status=snapshot.status,
            event=event,
            assessment=assessment,
            previous_ticket=event.previous_ticket,
            reaction=reaction,
        )
