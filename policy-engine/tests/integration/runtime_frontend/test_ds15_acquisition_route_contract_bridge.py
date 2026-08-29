from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.runtime.http.app import export_runtime_openapi_schema
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionRouteMutationRequest,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_ds15_backend_contract_and_generated_client_expose_all_four_operations() -> None:
    schema = export_runtime_openapi_schema()
    paths = schema["paths"]
    expected = {
        "/api/v1/runs/{run_id}/acquisition-routes": ("get",),
        "/api/v1/runs/{run_id}/acquisition-routes/{route_id}": ("get",),
        "/api/v1/runs/{run_id}/acquisition-routes/{route_id}/decision-request": ("post",),
        "/api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute": ("post",),
    }
    for path, methods in expected.items():
        assert tuple(method for method in methods if method in paths[path]) == methods
    assert (
        paths["/api/v1/runs/{run_id}/acquisition-routes/{route_id}/execute"]["post"][
            "x-polisyos-step-up-class"
        ]
        == "acquisition_approval"
    )

    generated_client = REPO_ROOT / "packages/runtime-api-client/runtimeApiClient.ts"
    source = generated_client.read_text(encoding="utf-8")
    expected_signatures = {
        "async listRunAcquisitionRoutes(",
        "async getRunAcquisitionRoute(",
        "async requestRunAcquisitionDecision(",
        "async executeRunAcquisitionRoute(",
    }
    assert all(signature in source for signature in expected_signatures)


@pytest.mark.parametrize(
    "forged_field",
    [
        "gap_class",
        "decision_status",
        "passport",
        "epoch",
        "world_growth",
        "reentry_receipt_ref",
    ],
)
def test_ds15_frontend_payload_cannot_author_client_owned_status(
    forged_field: str,
) -> None:
    payload = {
        "route_projection_hash": "sha256:" + "1" * 64,
        "planner_report_hash": "sha256:" + "2" * 64,
        "replay_pins": {
            "source_job_id": "job-natural-language",
            "compiled_ref": "sha256:" + "3" * 64,
            "compiled_content_hash": "sha256:" + "4" * 64,
            "terminal_event_id": "evt-terminal",
            "design_problem_ref": "sha256:" + "5" * 64,
            "cost_basis_hash": "sha256:" + "6" * 64,
        },
        "idempotency_key": "frontend-ds15",
        forged_field: "active",
    }
    with pytest.raises(ValidationError, match=forged_field):
        AcquisitionRouteMutationRequest.model_validate(payload)
