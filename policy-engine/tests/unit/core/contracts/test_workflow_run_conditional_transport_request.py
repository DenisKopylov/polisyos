from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.contracts.control import WorkflowRunRequest
from polisyos.ir.analytics.transportability import TransportabilityCandidateRequestV1


def _workflow_payload(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "data_source": {"data_snapshot_ref": "sha256:" + "1" * 64},
        "params": params,
    }


def test_workflow_params_schema_inlines_canonical_conditional_request() -> None:
    params_schema = WorkflowRunRequest.model_json_schema()["properties"]["params"]
    assert params_schema["type"] == "object"
    assert params_schema["additionalProperties"] is True
    request_schema = params_schema["properties"]["conditional_transport_request"]
    assert request_schema == TransportabilityCandidateRequestV1.model_json_schema()
    assert "$ref" not in str(request_schema)


def test_workflow_run_request_keeps_omitted_and_unrelated_params_open() -> None:
    original_params = {"existing_option": {"preserved": True}}
    payload = _workflow_payload(original_params)

    request = WorkflowRunRequest.model_validate(payload)

    assert "conditional_transport_request" not in request.params
    assert request.params == original_params
    assert payload["params"] == original_params


def test_workflow_run_request_strictly_validates_and_copies_conditional_request() -> None:
    original_params = {
        "conditional_transport_request": {
            "profile_id": "profile.transport.pag",
            "profile_revision": "r1",
            "selection_identity": "selected-profile-1",
        },
        "existing_option": {"preserved": True},
    }
    payload = _workflow_payload(original_params)

    request = WorkflowRunRequest.model_validate(payload)

    typed_request = TransportabilityCandidateRequestV1.model_validate(
        request.params["conditional_transport_request"],
        strict=True,
    )
    assert typed_request.schema_version == "1.0"
    assert request.params["conditional_transport_request"]["schema_version"] == "1.0"
    assert request.params["existing_option"] == {"preserved": True}
    assert payload["params"] == original_params


@pytest.mark.parametrize(
    ("value", "error_code"),
    [
        (None, "workflow_conditional_transport_request_explicit_null"),
        (
            {
                "profile_id": "profile.transport.pag",
                "profile_revision": "r1",
                "selection_identity": "selected-profile-1",
                "unexpected": True,
            },
            "workflow_conditional_transport_request_invalid",
        ),
        (
            {
                "profile_id": 7,
                "profile_revision": "r1",
                "selection_identity": "selected-profile-1",
            },
            "workflow_conditional_transport_request_invalid",
        ),
    ],
)
def test_workflow_run_request_refuses_null_or_malformed_conditional_request(
    value: object,
    error_code: str,
) -> None:
    params = {"conditional_transport_request": value}
    original_params = deepcopy(params)

    with pytest.raises(ValidationError, match=error_code):
        WorkflowRunRequest.model_validate(_workflow_payload(params))

    assert params == original_params
