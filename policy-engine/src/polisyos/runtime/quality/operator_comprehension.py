"""Candidate operator instrument over canonical honest-diagnostic event/CAS owners.

RuntimeDiagnosticEventLog owns persistence, event admission and duplicate custody.
This module adds only sealed behavioral trial orchestration. W5-K02 comprehension
is never produced by synthetic trials or conformance; WP-09 withholds public bounds.
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.canon import (
    CanonSpec,
    from_canonical_bytes,
    from_canonical_obj,
    to_canonical_bytes,
)
from polisyos.runtime.quality.diagnostic_events import DiagnosticEvent
from polisyos.runtime.quality.event_log import (
    DiagnosticEventPayloadPolicy,
    RuntimeDiagnosticEventLog,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


class InstrumentModel(BaseModel):
    """Strict immutable candidate instrument data; no promotion authority."""

    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")


class ScenarioItem(InstrumentModel):
    """One sealed synthetic scenario and its candidate action ground truth."""

    item_id: str
    partition: Literal["training", "sealed"]
    construct: str
    modality: str
    stimulus_text: str = Field(min_length=1)
    stimulus_family: tuple[str, ...] = Field(min_length=1)
    blockers: tuple[str, ...]
    admissible_actions: tuple[str, ...] = Field(min_length=1)
    forbidden_actions: tuple[str, ...]
    target_role: str
    authority_level: Literal["candidate_only"]  # Evidence authority, not participant competence.
    target_authority_level: str = Field(min_length=1)
    tenure_band: str
    environment: str
    deadline_seconds: int = Field(gt=0)

    @model_validator(mode="after")
    def _source_family_binding(self) -> ScenarioItem:
        if self.stimulus_text not in self.stimulus_family:
            raise ValueError("stimulus_family_unbound")
        if len(set(self.stimulus_family)) != len(self.stimulus_family):
            raise ValueError("duplicate_stimulus_family_member")
        return self

    @property
    def source_identity(self) -> str:
        """Derive exact undecorated source identity independently of display and partition."""
        return hashlib.sha256(self.stimulus_text.encode("utf-8")).hexdigest()

    @property
    def family_id(self) -> str:
        """Derive the declared source-family identity from actual member bytes."""
        return _digest(sorted(self.stimulus_family))

    @property
    def content(self) -> str:
        """Render controlled presentation wrappers from the bound source stimulus."""
        prefix = "Practice demonstration: " if self.partition == "training" else ""
        return f"{prefix}{self.stimulus_text} Modality: {self.modality}."


class ComprehensionCorpus(InstrumentModel):
    """Complete candidate item denominator and its predeclared stop policy."""

    schema_version: Literal["2"]
    corpus_id: str
    build_ref: str
    rule_refs: tuple[str, ...]
    mandatory_constructs: tuple[str, ...]
    modalities: tuple[str, ...]
    items: tuple[ScenarioItem, ...]
    seal: str

    @model_validator(mode="after")
    def _validate_partition(self) -> ComprehensionCorpus:
        if len({i.item_id for i in self.items}) != len(self.items):
            raise ValueError("duplicate_item_identity")
        training_members = {
            member
            for item in self.items
            if item.partition == "training"
            for member in item.stimulus_family
        }
        sealed_members = {
            member
            for item in self.items
            if item.partition == "sealed"
            for member in item.stimulus_family
        }
        # Each stimulus must belong to its family: this also binds all displayed sources.
        if training_members & sealed_members:
            raise ValueError("partition_leakage:source_family_member")
        expected = {(c, m) for c in self.mandatory_constructs for m in self.modalities}
        observed = {(i.construct, i.modality) for i in self.items if i.partition == "sealed"}
        if not expected or observed != expected:
            raise ValueError("partition_coverage_incomplete")
        if any(set(i.admissible_actions) & set(i.forbidden_actions) for i in self.items):
            raise ValueError("ambiguous_action_ground_truth")
        payload = self.model_dump(mode="json", exclude={"seal"})
        if self.seal != _digest(payload):
            raise ValueError("corpus_seal_mismatch")
        return self


class CandidateDesign(InstrumentModel):
    """Explicit candidate statistical design, never a governance threshold."""

    alpha: float = Field(gt=0, lt=1)
    population: str = Field(min_length=1)
    horizon: str = Field(min_length=1)
    assumptions: str = Field(min_length=1)
    authority_source: None = None


class TrialEvent(InstrumentModel):
    """Pseudonymous synthetic event with an ordered within-item event clock."""

    event_id: str
    item_id: str
    sequence: int = Field(ge=0)
    kind: Literal[
        "selected_blocker",
        "retrospective_blocker",
        "confidence",
        "action_attempt",
        "action_commit",
        "timeout",
        "environment_failure",
        "feedback",
    ]
    value: str
    participant_pseudonym: str = "synthetic"
    elapsed_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class SafetyCell(InstrumentModel):
    """Eligible-opportunity counts and an internal candidate estimate for one item."""

    item_id: str
    construct: str
    modality: str
    eligible_opportunities: int
    participant_count: int = 1
    false_action: int
    false_pass: int
    missed_blocker: int
    unsafe_attempts: int
    unsafe_commits: int
    unsafe_override: int
    high_confidence_wrong: None = None
    reported_confidence: float | None = None
    incorrect_with_confidence: int = 0
    confidence_squared_error: float | None
    time_to_correct: float | None
    terminal: str
    candidate_upper_bound: float | None


class ComprehensionResult(InstrumentModel):
    """Recomputed instrument result whose human-comprehension claim cannot be set."""

    corpus_seal: str
    result: Literal["instrument_demonstrated", "not_established"]
    stop_reason: str | None
    safety_cells: tuple[SafetyCell, ...]
    evidence_kind: Literal["synthetic_candidate"] = "synthetic_candidate"

    @property
    def human_comprehension_established(self) -> Literal[False]:
        """Refuse W5-K02 promotion on every construction and projection path."""
        return False

    def projection(self) -> dict[str, Any]:
        """Expose research diagnostics while withholding WP-09 numerical bounds."""
        cells = []
        for cell in self.safety_cells:
            row = cell.model_dump(exclude={"candidate_upper_bound"})
            row.update(upper_bound=None, upper_bound_withheld_by="WP-09")
            cells.append(row)
        return {
            "result": self.result,
            "stop_reason": self.stop_reason,
            "score": None,
            "human_comprehension_established": False,
            "semantic_independence": "not_established",
            "partition_independence": "exact_source_and_declared_family_only",
            "population_scope_provenance": "consumer_asserted",
            "limitations": [
                "semantic_family_independence_not_established",
                "W5-R3-Q06_item_adjudicator_absent",
            ],
            "safety_cells": cells,
            "authoritative_for": ["synthetic_instrument_diagnostics"],
            "may_not_use_for": [
                "human_comprehension",
                "operator_authority",
                "governance_threshold",
                "publication_authority",
            ],
        }


class InstrumentReceipt(InstrumentModel):
    """Persisted producer event address for consumer-side recomputation."""

    event_id: str
    payload_ref: str


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def seal_corpus(payload: Mapping[str, Any]) -> ComprehensionCorpus:
    """Freeze complete scenario bytes before any response can be collected."""
    candidate = dict(payload)
    candidate.pop("seal", None)
    # Canonical JSON arrays give identical identity for lists and validated tuples.
    return ComprehensionCorpus.model_validate({**candidate, "seal": _digest(candidate)})


def binomial_upper_bound(failures: int, opportunities: int, *, alpha: float) -> float | None:
    """Invert a binomial CDF for a one-sided exact candidate upper bound.

    Args:
        failures: Observed failures in the declared eligible denominator.
        opportunities: Complete number of eligible trials.
        alpha: Explicit candidate tail probability; there is no default or pass threshold.

    Returns:
        Exact-binomial upper endpoint to floating precision, or no estimate for zero trials.
    """
    if not 0 < alpha < 1 or not 0 <= failures <= opportunities:
        raise ValueError("invalid_binomial_design")
    if opportunities == 0:
        return None
    if failures == opportunities:
        return 1.0
    if failures == 0:
        return -math.expm1(math.log(alpha) / opportunities)
    lower, upper = 0.0, 1.0
    for _ in range(80):
        probability = (lower + upper) / 2
        terms = [
            math.lgamma(opportunities + 1)
            - math.lgamma(k + 1)
            - math.lgamma(opportunities - k + 1)
            + k * math.log(probability)
            + (opportunities - k) * math.log1p(-probability)
            for k in range(failures + 1)
        ]
        pivot = max(terms)
        cdf = math.exp(pivot) * sum(math.exp(term - pivot) for term in terms)
        if cdf > alpha:
            lower = probability
        else:
            upper = probability
    return (lower + upper) / 2


def score_trials(
    corpus: ComprehensionCorpus,
    events: Sequence[Mapping[str, Any] | TrialEvent],
    *,
    design: Mapping[str, Any] | CandidateDesign,
    conformance_evidence: Sequence[str] = (),
) -> ComprehensionResult:
    """Execute sealed scoring without treating conformance as behavioral evidence."""
    corpus = ComprehensionCorpus.model_validate(corpus)
    candidate_design = CandidateDesign.model_validate(design)
    del conformance_evidence  # Not an input to a behavioral result or authority claim.
    unique: dict[str, TrialEvent] = {}
    grouped: dict[tuple[str, str], list[TrialEvent]] = defaultdict(list)
    integrity_failure = False
    sealed = {i.item_id: i for i in corpus.items if i.partition == "sealed"}
    for raw in events:
        event = TrialEvent.model_validate(raw)
        if event.event_id in unique:
            integrity_failure |= unique[event.event_id] != event
            continue
        unique[event.event_id] = event
        if event.item_id not in sealed:
            integrity_failure = True
            continue
        grouped[(event.item_id, event.participant_pseudonym)].append(event)
    participants = {e.participant_pseudonym for e in unique.values()} or {"synthetic"}
    trial_cells: list[SafetyCell] = []
    for item_id, participant in (
        (item, person) for item in sealed for person in sorted(participants)
    ):
        item = sealed[item_id]
        trial = sorted(grouped[(item_id, participant)], key=lambda e: e.sequence)
        elapsed = [e.elapsed_seconds for e in trial if e.elapsed_seconds is not None]
        if elapsed != sorted(elapsed) or any(t > item.deadline_seconds for t in elapsed):
            integrity_failure = True
        if len({e.sequence for e in trial}) != len(trial):
            integrity_failure = True
        terminal_events = [
            e for e in trial if e.kind in ("action_commit", "timeout", "environment_failure")
        ]
        integrity_failure |= len(terminal_events) > 1
        terminal = terminal_events[0] if terminal_events else None
        cutoff = terminal.sequence if terminal else math.inf
        confidences = [e for e in trial if e.kind == "confidence" and e.sequence < cutoff]
        attempts = [e for e in trial if e.kind == "action_attempt" and e.sequence < cutoff]
        feedback = [e for e in trial if e.kind == "feedback"]
        if feedback or len(confidences) > 1:
            integrity_failure = True
        confidence = None
        if confidences:
            try:
                confidence = float(confidences[0].value)
                if not 0 <= confidence <= 1:
                    raise ValueError("invalid_confidence")
            except ValueError:
                integrity_failure = True
        if attempts and (not confidences or confidences[0].sequence > attempts[0].sequence):
            integrity_failure = True
        if (
            terminal
            and terminal.kind == "action_commit"
            and not any(a.value == terminal.value for a in attempts)
        ):
            integrity_failure = True
        correct = bool(
            terminal
            and terminal.kind == "action_commit"
            and terminal.value in item.admissible_actions
        )
        eligible = int(terminal is not None and terminal.kind != "environment_failure")
        selected = {e.value for e in trial if e.kind == "selected_blocker" and e.sequence < cutoff}
        unsafe_commits = int(bool(terminal and terminal.kind == "action_commit" and not correct))
        failure = int(bool(eligible and not correct))
        trial_cells.append(
            SafetyCell(
                item_id=item_id,
                construct=item.construct,
                modality=item.modality,
                eligible_opportunities=eligible,
                false_action=unsafe_commits,
                false_pass=int(bool(unsafe_commits and terminal and terminal.value == "pass")),
                missed_blocker=int(bool(eligible and not set(item.blockers) <= selected)),
                unsafe_attempts=sum(a.value not in item.admissible_actions for a in attempts),
                unsafe_commits=unsafe_commits,
                unsafe_override=int(
                    bool(unsafe_commits and terminal and terminal.value == "override")
                ),
                # No confidence cut point is appointed: retain the direct confidence/error pair.
                high_confidence_wrong=None,
                reported_confidence=confidence,
                incorrect_with_confidence=int(bool(failure and confidence is not None)),
                confidence_squared_error=(confidence - int(correct)) ** 2
                if confidence is not None
                else None,
                time_to_correct=terminal.elapsed_seconds if correct and terminal else None,
                terminal=terminal.kind if terminal else "missing",
                candidate_upper_bound=binomial_upper_bound(
                    failure, eligible, alpha=candidate_design.alpha
                ),
            )
        )
    cells: list[SafetyCell] = []
    count_fields = (
        "eligible_opportunities",
        "false_action",
        "false_pass",
        "missed_blocker",
        "unsafe_attempts",
        "unsafe_commits",
        "unsafe_override",
        "incorrect_with_confidence",
    )
    for item_id, item in sealed.items():
        members = [cell for cell in trial_cells if cell.item_id == item_id]
        counts = {field: sum(getattr(cell, field) for cell in members) for field in count_fields}
        times = [cell.time_to_correct for cell in members if cell.time_to_correct is not None]
        errors = [
            cell.confidence_squared_error
            for cell in members
            if cell.confidence_squared_error is not None
        ]
        failures = sum(
            cell.eligible_opportunities and (cell.terminal != "action_commit" or cell.false_action)
            for cell in members
        )
        terminal = (
            "missing"
            if any(c.terminal == "missing" for c in members)
            else "timeout"
            if any(c.terminal == "timeout" for c in members)
            else "environment_failure"
            if any(c.terminal == "environment_failure" for c in members)
            else "action_commit"
        )
        cells.append(
            SafetyCell(
                item_id=item_id,
                construct=item.construct,
                modality=item.modality,
                **counts,
                participant_count=len(participants),
                high_confidence_wrong=None,
                reported_confidence=members[0].reported_confidence if len(members) == 1 else None,
                confidence_squared_error=sum(errors) / len(errors) if errors else None,
                time_to_correct=sum(times) / len(times) if times else None,
                terminal=terminal,
                candidate_upper_bound=binomial_upper_bound(
                    failures, counts["eligible_opportunities"], alpha=candidate_design.alpha
                ),
            )
        )
    if integrity_failure:
        stop_reason = "event_integrity_failure"
    elif not any(c.eligible_opportunities for c in cells):
        stop_reason = "no_eligible_opportunities"
    elif any(c.eligible_opportunities != c.participant_count for c in cells):
        stop_reason = "coverage_insufficient"
    elif any(c.terminal != "action_commit" for c in cells):
        stop_reason = "demonstrability_stop_triggered"
    elif any(c.false_action or c.missed_blocker for c in cells):
        stop_reason = "safety_cell_failure"
    else:
        stop_reason = None
    return ComprehensionResult(
        corpus_seal=corpus.seal,
        result="not_established" if stop_reason else "instrument_demonstrated",
        stop_reason=stop_reason,
        safety_cells=tuple(cells),
    )


def run_instrument(
    corpus: ComprehensionCorpus,
    events: Sequence[Mapping[str, Any]],
    *,
    design: Mapping[str, Any],
    event_log: RuntimeDiagnosticEventLog,
) -> InstrumentReceipt:
    """Produce and persist one synthetic run through the existing diagnostic owner."""
    result = score_trials(corpus, events, design=design)
    run_id = uuid.uuid4().hex
    event = DiagnosticEvent(
        event_id=f"comprehension:{run_id}",
        event_source="polisyos.runtime.operator_comprehension",
        event_type="polisyos.runtime.diagnostic.producer_execution.v1",
        event_time=datetime.now(UTC),
        event_subject=f"instrument/{run_id}",
        schema_name="polisyos.runtime.quality.diagnostic_event",
        schema_version="1.0",
        trace_id=run_id,
        span_id=run_id,
        parent_span_id=None,
        run_id=run_id,
        job_id=run_id,
        tenant_id="synthetic-instrument",
        cell_id="research",
        producer_component=__name__,
        producer_version="2",
        execution_profile="research",
        phase="operator_comprehension",
        state_before="sealed",
        state_after=result.result,
        payload_ref=None,
        artifact_refs=(),
        input_refs=(corpus.seal,),
        blocking_status="blocking",
        redaction_policy_ref="research-synthetic-only",
        duplicate_of=None,
        dedupe_key=f"comprehension:{run_id}",
    )
    row = event_log.append(
        event,
        payload={
            "corpus": corpus.model_dump(mode="json"),
            "events": list(events),
            "design": dict(design),
            "result": result.model_dump(mode="json"),
        },
        payload_policy=DiagnosticEventPayloadPolicy(sensitive=True),
    )
    return InstrumentReceipt(event_id=event.event_id, payload_ref=row.payload_ref)


def recompute_instrument_payload(payload: Mapping[str, Any]) -> ComprehensionResult:
    """Recompute decisive result fields from the frozen corpus and raw events."""
    payload = from_canonical_obj(payload)
    corpus = ComprehensionCorpus.model_validate(payload["corpus"])
    result = score_trials(corpus, payload["events"], design=payload["design"])
    canon = CanonSpec(forbid_floats=False)
    if to_canonical_bytes(result.model_dump(mode="json"), canon) != to_canonical_bytes(
        payload["result"], canon
    ):
        raise ValueError("instrument_result_recompute_mismatch")
    return result


def read_instrument_result(
    event_log: RuntimeDiagnosticEventLog,
    event_id: str,
) -> ComprehensionResult:
    """Resolve the persisted event and content before returning its candidate projection."""
    rows = event_log.list_events(event_id=event_id)
    if len(rows) != 1 or not rows[0].payload_ref:
        raise ValueError("instrument_event_unresolved")
    record = rows[0]
    payload = from_canonical_bytes(event_log.artifact_store.get_bytes(record.payload_ref))
    result = recompute_instrument_payload(payload)
    if record.event.state_after != result.result:
        raise ValueError("instrument_event_recompute_mismatch")
    return result
