"""Verify the five source/cancellation/comparison documentation examples."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from polisyos.runtime.http.app import export_runtime_openapi_schema
from polisyos.runtime.http.openapi_contract import (
    _success_example_response_adapters,
    _success_example_response_models,
    validate_runtime_openapi_contract,
)

# This is the exact five-route slice supplied by the Runtime owners, not a
# claim that other Runtime routes or authority checks have been exercised.
_TARGETS = (
    (
        "/api/v1/control/jobs/{job_id}/cancel",
        "post",
        "cancel_control_job",
        "jobs.cancel",
    ),
    (
        "/api/v1/control/registered-sql/registrations",
        "post",
        "register_sql_source",
        "sources.registered_sql.register",
    ),
    (
        "/api/v1/control/registered-sql/materializations",
        "post",
        "admit_registered_sql_materialization",
        "sources.registered_sql.admit",
    ),
    (
        "/api/v1/control/registered-sql/withdrawals",
        "post",
        "withdraw_registered_sql_materialization",
        "sources.registered_sql.withdraw",
    ),
    (
        "/api/v1/runs/{run_id}/method-metric-comparison",
        "get",
        "get_run_method_metric_comparison",
        "runs.review",
    ),
)


def _success_example(schema: dict, path: str, method: str) -> dict:
    return schema["paths"][path][method]["responses"]["200"]["content"]["application/json"][
        "examples"
    ]["synthetic_documentation"]


def test_source_and_comparison_examples_are_typed_limited_and_validator_bound(
    runtime_openapi_app,
) -> None:
    """Actual exported metadata, DTOs, limit semantics and validator agree."""
    app = runtime_openapi_app
    schema = export_runtime_openapi_schema(app=app)
    assert validate_runtime_openapi_contract(schema) == []
    models = _success_example_response_models()
    adapters = _success_example_response_adapters()
    route_models = {
        route.operation_id: route.response_model
        for route in app.routes
        if isinstance(getattr(route, "operation_id", None), str)
        and getattr(route, "response_model", None) is not None
    }
    payloads = {}
    for path, method, operation_id, permission in _TARGETS:
        operation = schema["paths"][path][method]
        assert operation["operationId"] == operation_id
        assert operation["x-polisyos-action-permission"] == permission
        assert models[operation_id] is route_models[operation_id]
        example = _success_example(schema, path, method)
        assert "synthetic" in example["description"].lower()
        payload = example["value"]
        admitted = adapters[operation_id].validate_json(
            json.dumps(payload, ensure_ascii=False, allow_nan=False), strict=True
        )
        assert admitted.model_dump(mode="json") == payload
        payloads[operation_id] = payload

    cancellation = payloads["cancel_control_job"]
    assert cancellation["state"] == "cancelled"
    assert cancellation["cancellation_disposition"] == "publication_fenced"
    assert cancellation["physical_stop_status"] == "not_established"

    registration = payloads["register_sql_source"]["registration"]
    assert registration["issuer_key"] == "documentation-fixture-not-an-issuer"
    assert registration["source_incarnation_id"].startswith("fixture-")
    materialization = payloads["admit_registered_sql_materialization"]
    assert materialization["receipt"]["operation"] == "admit"
    assert materialization["receipt"]["carrier"] is not None
    assert materialization["binding_ref"]["kind"] == "fabric.registered_sql_admission_binding"
    assert materialization["binding_ref"]["manifest_profile_sha256"] is not None
    assert materialization["current_use"] == "not_checked"
    assert materialization["external_database_currentness"] == "not_established"
    assert payloads["withdraw_registered_sql_materialization"]["receipt"]["operation"] == (
        "withdraw"
    )
    comparison = payloads["get_run_method_metric_comparison"]["candidate_comparison"]
    assert comparison["status"] == "verification_missing"
    assert comparison["authority_status"] == "candidate_only"
    assert comparison["revalidation_required"] is True
    assert comparison["observations"] == []
    assert comparison["frontier_candidate_hashes"] == []
    assert comparison["limitations"] == ["current_candidate_comparison_owner_unavailable"]

    # Exercise the actual hardening gate with present examples whose DTO-level
    # content is wrong, including three mutations JSON Schema alone may permit.
    corrupted = deepcopy(schema)
    bad_values = {
        operation_id: _success_example(corrupted, path, method)["value"]
        for path, method, operation_id, _permission in _TARGETS
    }
    bad_values["cancel_control_job"]["physical_stop_status"] = "confirmed"
    bad_values["register_sql_source"]["registration"]["issuer_key"] = ""
    bad_values["admit_registered_sql_materialization"]["binding_ref"]["manifest_profile_sha256"] = (
        None
    )
    bad_values["withdraw_registered_sql_materialization"]["receipt"]["operation"] = "admit"
    bad_values["get_run_method_metric_comparison"]["candidate_comparison"]["status"] = "complete"
    for operation_id, value in bad_values.items():
        with pytest.raises(ValidationError):
            adapters[operation_id].validate_json(
                json.dumps(value, ensure_ascii=False, allow_nan=False), strict=True
            )
    violations = validate_runtime_openapi_contract(corrupted)
    for path, method, _operation_id, _permission in _TARGETS:
        assert (
            f"{method.upper()} {path}: 200 success example synthetic_documentation "
            "does not match registered response model"
        ) in violations

    # Removing examples while keeping all route/model metadata must be red.
    missing = deepcopy(schema)
    for path, method, _operation_id, _permission in _TARGETS:
        del missing["paths"][path][method]["responses"]["200"]["content"]["application/json"][
            "examples"
        ]
    missing_violations = validate_runtime_openapi_contract(missing)
    for path, method, _operation_id, _permission in _TARGETS:
        assert (
            f"{method.upper()} {path}: missing 2xx success response example"
        ) in missing_violations
