from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from pathlib import Path

    from polisyos.core.artifacts import ArtifactStore
    from polisyos.runtime.http.services.run_index import IndexedRunRecord
from _helpers.runtime_http import (
    _runtime_api_request,
    build_runtime_api_env,
    close_runtime_api_env,
)

from polisyos.core.contracts import (
    RunConditionalTransportCandidateProjection,
    RunDetails,
)
from polisyos.runtime.http.authorization import OptionalActionPermissionResult
from polisyos.runtime.http.routes import runs as runs_routes


@pytest.fixture
def runtime_api_env(tmp_path: Path) -> Iterator[Mapping[str, object]]:
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    try:
        yield env
    finally:
        close_runtime_api_env(env)


def _projection_payload(**overrides: object) -> dict[str, object]:
    return {
        "candidate_scope": "candidate_only",
        "candidate_disposition": "completed",
        "requested_profile_id": "profile.transport.pag",
        "requested_profile_revision": "r1",
        "selection_identity": "transport-selection-1",
        "reason_code": None,
        "proposal_count": 0,
        "member_evaluation_count": 2,
        "completed_valid_member_count": 2,
        "identified_member_fraction": 0.5,
        "identified_member_fraction_basis": "selected_completed_valid_members",
        "source_currentness": "unknown",
        "interpretation_limit": (
            "selected_family_member_outcomes_do_not_establish_whole_pag_class_probability_calibration_legal_applicability_or_protected_eligibility"
        ),
        **overrides,
    }


def test_public_projection_schema_is_strict_and_fraction_denominator_is_explicit() -> None:
    schema = RunConditionalTransportCandidateProjection.model_json_schema()
    assert schema["additionalProperties"] is False
    assert "$ref" not in str(schema)
    assert set(schema["properties"]) == set(_projection_payload())

    run_details_schema = RunDetails.model_json_schema()
    assert "conditional_transport_candidate" in run_details_schema["properties"]
    assert "conditional_transport_candidate" not in run_details_schema.get("required", ())
    projection_schema = run_details_schema["$defs"]["RunConditionalTransportCandidateProjection"]
    assert set(projection_schema["properties"]) == set(_projection_payload())
    assert "RunConditionalTransportCandidateProjection" in str(
        run_details_schema["properties"]["conditional_transport_candidate"]
    )

    projection = RunConditionalTransportCandidateProjection.model_validate(_projection_payload())
    assert projection.proposal_count == 0
    assert projection.member_evaluation_count == 2
    assert projection.completed_valid_member_count == 2
    assert projection.identified_member_fraction == 0.5

    empty = RunConditionalTransportCandidateProjection.model_validate(
        _projection_payload(
            member_evaluation_count=0,
            completed_valid_member_count=0,
            identified_member_fraction=None,
        )
    )
    assert empty.identified_member_fraction is None

    for bad in (
        _projection_payload(completed_valid_member_count=3),
        _projection_payload(
            member_evaluation_count=0,
            completed_valid_member_count=0,
            identified_member_fraction=0.0,
        ),
        _projection_payload(completed_valid_member_count=1, identified_member_fraction=None),
        _projection_payload(identified_member_fraction=1.01),
        _projection_payload(extra_artifact_ref={"kind": "ir.causal_graph_model"}),
    ):
        with pytest.raises(ValidationError):
            RunConditionalTransportCandidateProjection.model_validate(bad)


def test_run_details_projects_only_reviewed_candidate_and_records_access_audit(
    runtime_api_env: Mapping[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]
    assert client is not None
    projection = RunConditionalTransportCandidateProjection.model_validate(
        _projection_payload(
            candidate_disposition="unsupported",
            reason_code="owner_profile_refused",
            proposal_count=0,
            member_evaluation_count=0,
            completed_valid_member_count=0,
            identified_member_fraction=None,
        )
    )
    helper_calls: list[tuple[str, object]] = []

    def project(
        run: IndexedRunRecord, *, store: ArtifactStore
    ) -> RunConditionalTransportCandidateProjection:
        helper_calls.append((run.run_id, store))
        return projection

    monkeypatch.setattr(
        runs_routes,
        "_conditional_transport_candidate_for_indexed_run",
        project,
    )
    audit = client.app.state.runtime_container.runtime_access_audit
    before = len(audit.scan_read_only().entries)

    response = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/runs/{run_id}",
        headers={"X-Request-ID": "conditional-transport-candidate-projection"},
    )

    assert response.status_code == 200, response.text
    run_payload = response.json()["run"]
    candidate = run_payload["conditional_transport_candidate"]
    assert candidate == projection.model_dump(mode="json")
    assert set(candidate) == set(_projection_payload())
    assert not {
        "artifact_ref",
        "graph_ref",
        "candidate_diagnostics",
        "outer_status",
        "authority",
    }.intersection(candidate)
    assert len(helper_calls) == 1
    assert helper_calls[0][0] == run_id
    events = audit.scan_read_only().entries[before:]
    assert any(
        event.get("resource_kind") == "runtime.run.conditional_transport_candidate"
        and event.get("outcome") == "conditional_transport_candidate_projected"
        for event in events
    )

    monkeypatch.setattr(
        runs_routes,
        "_conditional_transport_candidate_for_indexed_run",
        lambda run, *, store: None,
    )
    unavailable_response = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/runs/{run_id}",
        headers={"X-Request-ID": "conditional-transport-candidate-unavailable"},
    )
    assert unavailable_response.status_code == 200, unavailable_response.text
    assert "conditional_transport_candidate" not in unavailable_response.json()["run"]

    gate = runs_routes._GET_RUN_METHOD_SELECTION_AUTHZ
    denied = OptionalActionPermissionResult(
        requirement=gate.requirement,
        allowed=False,
        denial_class="permission_denied",
    )
    client.app.dependency_overrides[gate] = lambda: denied
    before_denied = len(audit.scan_read_only().entries)
    denied_response = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/runs/{run_id}",
        headers={"X-Request-ID": "conditional-transport-candidate-denied"},
    )
    client.app.dependency_overrides.pop(gate, None)

    assert denied_response.status_code == 200, denied_response.text
    assert "conditional_transport_candidate" not in denied_response.json()["run"]
    assert len(helper_calls) == 1
    denied_events = audit.scan_read_only().entries[before_denied:]
    assert any(
        event.get("resource_kind") == "runtime.run.conditional_transport_candidate"
        and event.get("outcome") == "denied"
        for event in denied_events
    )


def test_explicit_temporal_scope_suppresses_current_enrichments_and_audits(
    runtime_api_env: Mapping[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = runtime_api_env["client"]
    run_id = runtime_api_env["core_run_id"]
    assert client is not None

    current_response = _runtime_api_request(
        runtime_api_env,
        client.get,
        f"/api/v1/runs/{run_id}",
        headers={"X-Request-ID": "conditional-transport-temporal-current"},
    )
    assert current_response.status_code == 200, current_response.text
    current_run = current_response.json()["run"]
    started_at = current_run["started_at"]
    finished_at = current_run["finished_at"]
    assert isinstance(started_at, str)
    assert isinstance(finished_at, str)

    def unexpected_current_enrichment(*args: object, **kwargs: object) -> None:
        raise AssertionError("current-view enrichment ran for an explicit temporal scope")

    for helper_name in (
        "_control_service_from_request",
        "_conditional_transport_candidate_for_indexed_run",
        "_latest_control_operator_diagnostic",
        "_latest_control_policy_projection",
        "_candidate_simulation_for_indexed_run",
        "_generic_cycle_simulation_projection",
    ):
        monkeypatch.setattr(runs_routes, helper_name, unexpected_current_enrichment)

    audit = client.app.state.runtime_container.runtime_access_audit
    for request_id, valid_at in (
        ("conditional-transport-temporal-before-finish", started_at),
        ("conditional-transport-temporal-at-finish", finished_at),
    ):
        before = len(audit.scan_read_only().entries)
        scoped_response = _runtime_api_request(
            runtime_api_env,
            client.get,
            f"/api/v1/runs/{run_id}",
            params={"valid_at": valid_at},
            headers={"X-Request-ID": request_id},
        )
        assert scoped_response.status_code == 200, scoped_response.text
        payload = scoped_response.json()
        assert payload["temporal_scope"]["valid_at"] == valid_at
        scoped_run = payload["run"]
        for current_field in (
            "method_execution_selection",
            "conditional_transport_candidate",
            "method_execution_producer_diagnostic",
            "candidate_simulation",
            "generic_cycle_simulation",
            "operator_diagnostic",
            "policy_design_case_projection",
        ):
            assert current_field not in scoped_run or scoped_run[current_field] is None

        scoped_events = audit.scan_read_only().entries[before:]
        assert not any(
            event.get("resource_kind")
            in {
                "runtime.run.method_execution_selection",
                "runtime.run.conditional_transport_candidate",
            }
            for event in scoped_events
        )
