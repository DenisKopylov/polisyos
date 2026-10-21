from __future__ import annotations

from typing import Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactGovernanceInfo, ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.security.tenant_context import tenant_scope


def _put_v2_hte_source(
    service: Any,
    *,
    tenant_id: str,
    cell_id: str,
) -> ArtifactRef:
    """Persist the same bounded 40-row synthetic HTE input used by the owner path."""
    row_count = 40
    payload = {
        "outcome": [float(index) / 10 + (index % 2) * 0.5 for index in range(row_count)],
        "treatment": [index % 2 for index in range(row_count)],
        "covariates": [[float(index), float(index % 5)] for index in range(row_count)],
        "confounders": [[float(index % 7)] for index in range(row_count)],
        "feature_names": ["age", "baseline"],
        "confounder_names": ["risk"],
        "sample_ids": [f"candidate-{index}" for index in range(row_count)],
        "metadata": {"source": "synthetic_candidate"},
    }
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        ref = service._artifact_store.put_json(
            {
                "schema_version": "policyos.ir.observation.method_input_envelope.v1",
                "contract_target": {
                    "contract_id": "foundry.causal.hte_observational_data.v1",
                    "contract_fqn": (
                        "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
                    ),
                },
                "contract_payload": payload,
            },
            PutOptions(
                kind="ir.observation_method_input",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.ir.ObservationMethodInputEnvelope",
                    version="1.0",
                ),
                inputs=[],
                governance=ArtifactGovernanceInfo(classification="public"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    return ArtifactRef.model_validate(ref, strict=True)


def test_v2_completed_hte_is_served_by_fresh_run_details_get(
    runtime_api_env: dict[str, Any],
) -> None:
    """The ordinary Run Details GET serves the persisted v2 HTE selection to its owner."""
    pytest.importorskip("econml")
    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker
    from pydantic import TypeAdapter

    from polisyos.core.contracts.runtime import (
        DirectMethodExecutionSelection,
        MethodExecutionSelection,
    )

    service = runtime_api_env["app"].state._control_service
    stop_embedded_control_worker(service)
    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    source_ref = _put_v2_hte_source(service, tenant_id=tenant_id, cell_id=cell_id)
    accepted_response = runtime_api_env["client"].post(
        "/api/v1/control/runs",
        json={
            "observational_input": {
                "protocol": "method_input_envelope_v1",
                "source_ref": source_ref.model_dump(mode="json"),
                "method": {"fqn": "causal.hte.double_ml@2.0.0"},
                "hte_request": {
                    "schema_version": "polisyos.runtime.observational_hte_request.v2",
                    "estimand": "mean_effect_over_selected_x",
                    "target_scope": "selected_evaluation_rows",
                    "outcome_variable_id": "outcome.effect",
                    "treatment_variable_id": "treatment.policy",
                    "control_value": 0.0,
                    "treated_value": 1.0,
                    "alpha": 0.05,
                    "requested_guarantee": "candidate_point",
                },
            }
        },
    )
    assert accepted_response.status_code == 200, accepted_response.text
    accepted = accepted_response.json()
    job_id = accepted["job_id"]
    run_id = accepted["run_id"]

    assert (
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=job_id,
        )
        == job_id
    )
    completed = service._control_store.get_job(job_id)
    assert completed is not None and completed.state == "completed"
    assert completed.method_execution_selection is not None
    persisted_selection = TypeAdapter(MethodExecutionSelection).validate_python(
        completed.method_execution_selection,
        strict=True,
    )
    assert type(persisted_selection) is DirectMethodExecutionSelection
    assert persisted_selection.hte is not None
    assert persisted_selection.hte.kind == "point_estimate"
    assert persisted_selection.attempt == completed.attempt

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        fresh = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}")
    assert fresh.status_code == 200, fresh.text
    body = fresh.json()
    assert body["run"]["run_id"] == run_id
    projection = body["run"]["method_execution_selection"]
    assert projection["status"] == "selected"
    served_selection = projection["selection"]
    assert served_selection["job_id"] == job_id
    assert served_selection["run_id"] == run_id
    assert served_selection["attempt"] == completed.attempt
    expected_anchor_ref = persisted_selection.owned_attempt_anchor_ref.model_dump(mode="json")
    assert served_selection["owned_attempt_anchor_ref"] == expected_anchor_ref

    served_hte = served_selection["hte"]
    expected_hte = persisted_selection.hte
    assert served_hte["schema_version"] == "1.0"
    assert served_hte["kind"] == "point_estimate"
    assert served_hte["method_fqn"] == "causal.hte.double_ml@2.0.0"
    assert served_hte["method_abi_digest"] == expected_hte.method_abi_digest
    expected_hte_anchor_ref = expected_hte.owned_attempt_anchor_ref.model_dump(mode="json")
    assert served_hte["owned_attempt_anchor_ref"] == expected_hte_anchor_ref
    assert expected_hte.point_result_ref is not None
    assert served_hte["hte_outcome_ref"] == expected_hte.hte_outcome_ref.model_dump(mode="json")
    assert served_hte["point_result_ref"] == expected_hte.point_result_ref.model_dump(mode="json")
    assert served_hte["point_estimate"] == expected_hte.point_estimate
    assert served_hte["hte_result_ref"] is None
    assert served_hte["refusal_diagnostic_ref"] is None
    assert served_hte["resource_evidence"]["owner_policy_revision"] == "r5"
    assert "observational_data" not in fresh.text
    assert "covariates" not in fresh.text
    assert "sample_ids" not in fresh.text
    assert "cate_values" not in fresh.text

    # The same GET endpoint must withhold the v2 association from another cell.
    with tenant_scope(None, tenant_id=tenant_id, cell_id="cell-not-owned-by-run"):
        wrong_cell = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}")
    assert wrong_cell.status_code == 200, wrong_cell.text
    withheld = wrong_cell.json()["run"]["method_execution_selection"]
    assert withheld["status"] == "withheld"
    assert withheld["limitations"] == ["owned_run_cell_scope_required"]
    assert withheld["selection"] is None
