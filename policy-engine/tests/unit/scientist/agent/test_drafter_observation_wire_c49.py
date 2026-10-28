"""Historical wire and current typed worker transport, with no authority inflation."""

from __future__ import annotations

import copy
import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from polisyos.scientist.agent.protocols import DraftResult
from polisyos.scientist.agent.workers import _draft_to_payload, draft_from_payload
from polisyos.scientist.orchestration.engine.convergence import (
    ConvergenceConfig,
    ConvergenceDetector,
    ConvergenceObservation,
)


def test_historical_draft_projection_omits_unproduced_new_fields():
    draft = DraftResult(
        draft_id="legacy-draft",
        problem_frame_ref="legacy-problem",
        narrative="Useful candidate",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        confidence=0.5,
    )
    projected = TypeAdapter(DraftResult).dump_python(draft, mode="json")
    assert set(projected) == {
        "draft_id",
        "problem_frame_ref",
        "narrative",
        "interventions",
        "rationale",
        "domain_references",
        "citations",
        "claim_supports",
        "grounding_notes",
        "confidence",
        "alternatives_considered",
        "raw_llm_response",
        "created_at",
    }
    assert _draft_to_payload(draft)["created_at"] == draft.created_at
    assert draft_from_payload(_draft_to_payload(draft)) == draft


def test_actual_worker_bridge_round_trips_typed_current_observation_and_rejects_authority():
    raw = "actual-current-response"

    def digest(text):
        return hashlib.sha256(text.encode()).hexdigest()

    observation = ConvergenceObservation(
        subject_ref=digest("problem"),
        request_ref=digest("request"),
        source_ref=digest(raw),
        producer_response_ref=digest(raw),
        producer_request_ref=digest("core-scoped-request"),
        producer_event_id="real-call-id",
        model_ref="fixture-model",
        model_version="fixture-v1",
        pass_number=1,
        value=0.2,
    )
    state = ConvergenceDetector(ConvergenceConfig()).check_candidate_observation(
        observation,
        subject_ref=observation.subject_ref,
        request_ref=observation.request_ref,
        source_text=raw,
        value=0.2,
        pass_number=1,
    )
    draft = DraftResult(
        draft_id="current-draft",
        problem_frame_ref="problem",
        narrative="Useful candidate",
        citations=[{"ref": "existing-citation"}],
        claim_supports=[{"id": "existing-claim"}],
        grounding_notes=["candidate-only"],
        confidence=0.2,
        confidence_status="candidate_self_assessment",
        confidence_request_ref=observation.request_ref,
        confidence_observation=observation,
        convergence_state=state,
    )
    payload = _draft_to_payload(draft)
    assert type(payload["confidence_observation"]) is dict
    assert type(payload["convergence_state"]) is dict
    reopened = draft_from_payload(payload)
    assert type(reopened.confidence_observation) is ConvergenceObservation
    assert reopened.convergence_state == state
    assert reopened.citations == draft.citations and reopened.claim_supports == draft.claim_supports
    forged = copy.deepcopy(payload)
    forged["convergence_state"]["scientific_converged"] = True
    with pytest.raises(ValidationError):
        draft_from_payload(forged)
    with pytest.raises(TypeError):
        draft_from_payload({**payload, "authority": "publication"})
