"""Bind omitted and explicit-null predecessor pins through the real HTTP binder."""

from __future__ import annotations

import json

import pytest
from fastapi import Request

from polisyos.core.security import AccessScope, PIIAccessLevel
from polisyos.runtime.http.resource_binding import bind_authorization_resource
from polisyos.runtime.http.routes.acquisitions import _CANDIDATE_EXPERIMENT_MUTATION_AUTHZ
from polisyos.runtime.http.services.acquisition_action_service import (
    CandidateExperimentRouteMutationRequest,
    CandidateExperimentRouteReplayPins,
)
from polisyos.runtime.http.services.acquisition_admission_bundle import (
    candidate_experiment_request_resource_digest,
    require_candidate_experiment_bound_permission,
)
from tests.integration.core_runtime.test_acquisition_admission_bundle import _proof
from tests.unit.runtime.http.services.test_acquisition_action_service import (
    _candidate_experiment_action_fixture,
)


@pytest.mark.parametrize("explicit_null", [False, True])
def test_raw_predecessor_pin_binding_survives_dto_and_historical_replay(
    explicit_null: bool,
) -> None:
    """A nullable raw selector retains its exact presence and original body hash."""
    _, mutation = _candidate_experiment_action_fixture()
    body = mutation.model_dump(mode="json")
    if explicit_null:
        body["replay_pins"]["predecessor_terminal_ref"] = None
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    requirement = _CANDIDATE_EXPERIMENT_MUTATION_AUTHZ.requirement
    verification = _proof(requirement=requirement).verification
    scope = AccessScope(
        tenant_id=verification.tenant_id,
        cell_id="cell-acquisition",
        principal_type="user",
        user_sub=verification.subject,
        roles=verification.roles,
        max_pii_tier=PIIAccessLevel.HIGH,
        mfa_verified=True,
        jwt_jti=verification.jwt_id,
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/candidate-experiment-component-probe",
            "query_string": b"",
            "headers": [],
        }
    )
    request.state.authz_effective_scope = scope
    request.state.action_permission_verification = verification
    bound = bind_authorization_resource(request, requirement, raw)
    proof = _proof(
        requirement=requirement,
        resource_digest=bound.resource_digest,
        canonical_selectors=bound.canonical_selectors,
        body_sha256=bound.body_sha256,
        query_sha256=bound.query_sha256,
    )
    parsed = CandidateExperimentRouteMutationRequest.model_validate_json(raw)

    assert require_candidate_experiment_bound_permission(proof, parsed) == bound.resource_digest
    assert (
        candidate_experiment_request_resource_digest(
            parsed,
            body_sha256=bound.body_sha256,
            query_sha256=bound.query_sha256,
        )
        == bound.resource_digest
    )
    assert parsed.model_dump(mode="json") == body
    assert json.loads(parsed.model_dump_json()) == body


def test_presence_serializer_preserves_typed_predecessor_output_schema() -> None:
    """The presence-preserving hook must not replace the DTO schema with an opaque map."""
    schema = CandidateExperimentRouteReplayPins.model_json_schema(mode="serialization")
    assert set(schema["properties"]) == set(CandidateExperimentRouteReplayPins.model_fields)
    assert "predecessor_terminal_ref" not in schema["required"]
    assert {
        item.get("type") for item in schema["properties"]["predecessor_terminal_ref"]["anyOf"]
    } == {None, "null"}
