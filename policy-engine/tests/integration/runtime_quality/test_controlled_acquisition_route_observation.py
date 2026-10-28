"""Transparent witnesses for the actual guarded predictive HTTP acquisition route.

The guard remains the decision owner. Its four actual input premises are
retained before it succeeds or raises; no fixture field is repaired by this
observer. The synthetic observer control is not an ordinary N4/N7 proof.
"""

from __future__ import annotations

import json
from typing import Any

import pytest


def _observe_live_route_guard(
    monkeypatch: pytest.MonkeyPatch,
    *,
    record_property: Any,
    observations: list[dict[str, Any]],
) -> None:
    from polisyos.runtime.http.services import acquisition_surface_execution as owner

    original = owner._require_live_variable_route

    def observe(closure: Any) -> str:
        record = closure.planner_record
        routing_ref = closure.source_cycle.acquisition_routing_report_ref
        observation = {
            "schema": "policyos.e02.live_variable_route_observation.v1",
            "gap_type": getattr(record.gap_type, "value", record.gap_type),
            "requirement_family": record.requirement_family,
            "requirement_schema_version": record.requirement_schema_version,
            "recommended_strategy": getattr(
                record.recommended_strategy, "value", record.recommended_strategy
            ),
            "missing_requirement_fields": list(record.missing_requirement_fields),
            "run_id": closure.run_id,
            "tenant_id": closure.tenant_id,
            "cell_id": closure.cell_id,
            "source_job_id": closure.source_job_id,
            "source_payload_ref": closure.source_payload_ref,
            "capability_manifest_ref": closure.capability_manifest_ref,
            "compiled_ref": closure.compiled_ref,
            "compiled_content_hash": closure.compiled_content_hash,
            "terminal_event_id": closure.terminal_event_id,
            "route_id": closure.route_id,
            "source_cycle_index": closure.route_source_cycle_index,
            "design_problem_ref": closure.design_problem_ref,
            "planner_report_run_id": closure.planner_report.run_id,
            "planning_context_hash": closure.planner_report.planning_context_hash,
            "planning_binding_hash": closure.planner_report.planning_binding_hash,
            "planner_acquisition_id": record.acquisition_id,
            "planner_gap_id": record.gap_id,
            "compiled_requirement_ref": record.compiled_requirement_ref,
            "routing_report_ref": (
                routing_ref.model_dump(mode="json", exclude_none=True)
                if routing_ref is not None
                else None
            ),
        }
        observations.append(observation)
        encoded = json.dumps(observation, sort_keys=True, separators=(",", ":"))
        record_property("live_variable_route_observation", encoded)
        print("live_variable_route_observation=" + encoded, flush=True)
        return original(closure)

    monkeypatch.setattr(owner, "_require_live_variable_route", observe)


def test_live_route_observer_preserves_actual_guard_result_and_refusal(
    monkeypatch: pytest.MonkeyPatch,
    record_property: Any,
) -> None:
    """Real guard execution stays unchanged with both matching and divergent input."""
    from types import SimpleNamespace

    from polisyos.runtime.http.services import acquisition_surface_execution as owner

    observations: list[dict[str, Any]] = []
    _observe_live_route_guard(
        monkeypatch, record_property=record_property, observations=observations
    )
    record = SimpleNamespace(
        gap_type="data_snapshot_release",
        requirement_family="data_requirement",
        requirement_schema_version="policyos.runtime.l1_variable_availability_gap.v1",
        recommended_strategy="production_snapshot_build",
        missing_requirement_fields=("canonical_variable_observations:government.balance",),
        acquisition_id="observer-control-only",
        gap_id="observer-control-only",
        compiled_requirement_ref=None,
    )
    closure = SimpleNamespace(
        planner_record=record,
        run_id="observer-control-only",
        tenant_id="observer-control-only",
        cell_id="observer-control-only",
        source_job_id="observer-control-only",
        source_payload_ref="observer-control-only",
        capability_manifest_ref="observer-control-only",
        compiled_ref="observer-control-only",
        compiled_content_hash="observer-control-only",
        terminal_event_id="observer-control-only",
        route_id="observer-control-only",
        route_source_cycle_index=0,
        design_problem_ref="observer-control-only",
        planner_report=SimpleNamespace(
            run_id="observer-control-only", planning_context_hash=None, planning_binding_hash=None
        ),
        source_cycle=SimpleNamespace(acquisition_routing_report_ref=None),
    )
    assert owner._require_live_variable_route(closure) == "government.balance"
    record.requirement_schema_version = "observer-control:divergent-schema"
    with pytest.raises(owner.LiveAcquisitionExecutionError) as refused:
        owner._require_live_variable_route(closure)
    assert refused.value.code == "live_route_requirement_shape_invalid"
    assert len(observations) == 2
    assert observations[0]["requirement_schema_version"] == (
        "policyos.runtime.l1_variable_availability_gap.v1"
    )
    assert observations[1]["requirement_schema_version"] == "observer-control:divergent-schema"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_predictive_http_retains_actual_live_route_premises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    request: pytest.FixtureRequest,
    record_property: Any,
) -> None:
    """Run the existing complete HTTP witness under an unchanged observing guard."""
    pytest.importorskip("fastapi.testclient")
    from tests.unit.runtime.http.test_control_service_di import (
        test_predictive_calibration_post_event_reopen_get_and_exact_intent_retry,
    )

    observations: list[dict[str, Any]] = []
    _observe_live_route_guard(
        monkeypatch, record_property=record_property, observations=observations
    )
    await test_predictive_calibration_post_event_reopen_get_and_exact_intent_retry(
        monkeypatch=monkeypatch, tmp_path=tmp_path, request=request
    )
    assert observations, "actual_live_route_guard_not_reached"
