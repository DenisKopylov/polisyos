"""Observe candidate drafter assessments on the existing traced LLM producer.

These are content-bound candidate observations, never calibration, scientific
convergence or publication authority. Missing provider versions stay unknown.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import TYPE_CHECKING, Any

from polisyos.core.llm.settlement import LLMSettledResponse
from polisyos.scientist.orchestration.engine.convergence import ConvergenceObservation

if TYPE_CHECKING:
    from polisyos.scientist.agent.protocols import ProblemFrame


def confidence_subject_ref(problem_frame: ProblemFrame) -> str | None:
    """Bind a serializable semantic problem; missing identity stays unavailable."""
    payload = {
        "frame_id": problem_frame.frame_id,
        "domain": problem_frame.domain,
        "problem_statement": problem_frame.problem_statement,
        "actors": problem_frame.actors,
        "goals": problem_frame.goals,
        "constraints": problem_frame.constraints,
        "success_criteria": problem_frame.success_criteria,
        "assumptions": problem_frame.assumptions,
    }
    try:
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    except (TypeError, ValueError, OverflowError):
        return None
    return hashlib.sha256(encoded).hexdigest()


def confidence_request_ref(*, system: str, user: str) -> str:
    """Bind the actual caller input, separately from Core's scoped/sanitized request."""
    return hashlib.sha256(
        json.dumps(
            {"system": system, "user": user, "response_format": {"type": "json_object"}},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def finite_candidate_confidence(value: object) -> float | None:
    """Refuse bools, coercible strings and nonfinite or out-of-range self-grades."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) and 0.0 <= result <= 1.0 else None


def observe_candidate_confidence(
    *,
    response: object,
    source_text: str,
    subject_ref: str | None,
    request_ref: str,
    pass_number: int,
    value: float,
) -> ConvergenceObservation | None:
    """Use the real Core producer event and recompute its response binding.

    Monetary settlement status is deliberately separate: missing cost does not
    erase an observed response, and content does not establish a USD charge.
    Core hashes the producer response before restoration. When the consumed
    bytes differ, this view retains both identities but does not invent a
    cross-layer attestation; the current grade remains a limited candidate.
    """
    if type(response) is not LLMSettledResponse or subject_ref is None:
        return None
    event = response.settlement.event
    source_ref = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    if any(
        type(value) is not str or re.fullmatch(r"[a-f0-9]{64}", value) is None
        for value in (event.request_digest, event.response_digest)
    ):
        return None
    raw = response.response
    version: Any = (
        raw.get("model_version") if isinstance(raw, dict) else getattr(raw, "model_version", None)
    )
    if type(version) is not str or not version.strip():
        version = None
    else:
        version = version.strip()
    return ConvergenceObservation(
        subject_ref=subject_ref,
        request_ref=request_ref,
        producer_request_ref=event.request_digest,
        source_ref=source_ref,
        producer_response_ref=event.response_digest,
        response_binding_status=(
            "same_bytes" if event.response_digest == source_ref else "not_established"
        ),
        producer_event_id=event.event_id,
        producer_kind=event.kind,
        model_ref=event.model,
        model_version=version,
        pass_number=pass_number,
        value=value,
    )
