from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from polisyos.core.contracts.runtime import (
    AgentPipelineResponse,
    AgentPipelineView,
    ApiMeta,
)


def _verified_pipeline() -> AgentPipelineView:
    return AgentPipelineView._from_verified_owner_context(
        owner_control_job_attempt=3,
        run_id="run-r3-cost-projection",
        source_kind="core_run",
        attempts=[
            {
                "attempt": 3,
                "steps": [
                    {
                        "agent": "drafter",
                        "action": "generate",
                        "cost_events": [
                            {
                                "event_id": "provider:r3-cost-projection",
                                "cost_origin": "reported",
                                "amount": Decimal("0.25"),
                                "settlement_status": "committed",
                                "durability": "ledger",
                                "control_job_attempt": 3,
                            }
                        ],
                    }
                ],
            }
        ],
    )


def _response(pipeline: AgentPipelineView) -> AgentPipelineResponse:
    return AgentPipelineResponse(
        meta=ApiMeta(request_id="r3-cost-projection-test"),
        pipeline=pipeline,
    )


def test_fastapi_response_envelope_preserves_verified_owner_projection() -> None:
    pipeline = _verified_pipeline()
    assert pipeline.owner_control_job_attempt == 3
    assert pipeline.cost_origin_counts == {"reported": 1}
    assert pipeline.cost_usd == pytest.approx(0.25)

    response = _response(pipeline)
    wire = response.model_dump(mode="json")
    assert wire["pipeline"]["owner_control_job_attempt"] == 3
    assert wire["pipeline"]["cost_origin_counts"] == {"reported": 1}
    assert wire["pipeline"]["cost_usd"] == pytest.approx(0.25)
    assert "_verified_owner_control_job_attempt" not in wire["pipeline"]
    assert "_verified_cost_event_basis_sha256" not in wire["pipeline"]


def test_wire_report_preserves_observations_without_route_owner_authority() -> None:
    admitted = _response(_verified_pipeline())
    wire = admitted.model_dump(mode="python")
    report = AgentPipelineResponse.model_validate(wire).pipeline

    assert report.owner_control_job_attempt == 3
    assert report.cost_origin_counts == {"reported": 1}
    assert report.settlement_status_counts == {"committed": 1}
    assert report.cost_usd == pytest.approx(0.25)
    assert report.reported_cost_usd == pytest.approx(0.25)
    assert report.attempts[0].cost_usd == pytest.approx(0.25)
    assert report.attempts[0].steps[0].cost_usd == pytest.approx(0.25)
    assert report._verified_owner_control_job_attempt is None
    assert report._verified_cost_event_basis_sha256 is None

    # The admission DTO remains fail-closed when parsed outside the response/report envelope.
    untrusted_admission = AgentPipelineView.model_validate(wire["pipeline"])
    assert untrusted_admission.owner_control_job_attempt is None
    assert untrusted_admission.cost_origin_counts == {}
    assert untrusted_admission.cost_usd is None
    assert untrusted_admission.reported_cost_usd is None

    forged = dict(wire["pipeline"])
    forged["owner_control_job_attempt"] = 9
    forged["cost_usd"] = 999.0
    with pytest.raises(
        ValidationError,
        match="agent_pipeline_owner_context_mismatch",
    ):
        AgentPipelineView.model_validate(
            forged,
            context={"verified_control_job_attempt": 3},
        )


def test_admitted_owner_context_refuses_mutated_cost_event_basis() -> None:
    pipeline = _verified_pipeline()
    attempt = pipeline.attempts[0]
    step = attempt.steps[0]
    event = step.cost_events[0]
    changed_event = event.model_copy(update={"amount": Decimal("0.50"), "cost_usd": 0.5})
    changed_step = step.model_copy(update={"cost_events": [changed_event]})
    changed_attempt = attempt.model_copy(update={"steps": [changed_step]})
    changed_pipeline = pipeline.model_copy(update={"attempts": [changed_attempt]})

    with pytest.raises(
        ValidationError,
        match="agent_pipeline_verified_owner_cost_event_basis_changed",
    ):
        _response(changed_pipeline)
