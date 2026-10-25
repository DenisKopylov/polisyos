from __future__ import annotations

from typing import Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactGovernanceInfo, ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.security.tenant_context import tenant_scope


def _v2_hte_source_payload(*, source_only_sample_id: str) -> dict[str, object]:
    """Build the actual producer DTO fields with one source-only privacy canary."""
    row_count = 40
    sample_ids = [f"candidate-{index}" for index in range(row_count)]
    sample_ids[0] = source_only_sample_id
    payload: dict[str, object] = {
        "outcome": [float(index) / 10 + (index % 2) * 0.5 for index in range(row_count)],
        "treatment": [index % 2 for index in range(row_count)],
        "covariates": [[float(index), float(index % 5)] for index in range(row_count)],
        "confounders": [[float(index % 7)] for index in range(row_count)],
        "feature_names": ["age", "baseline"],
        "confounder_names": ["risk"],
        "sample_ids": sample_ids,
        "metadata": {"source": "synthetic_candidate"},
    }
    from _helpers.hte_privacy import hte_source_data_field_names

    if set(payload) != hte_source_data_field_names():
        raise AssertionError("test_hte_source_fixture_does_not_match_producer_dto")
    return payload


def _put_v2_hte_source(
    service: Any,
    *,
    tenant_id: str,
    cell_id: str,
    payload: dict[str, object],
) -> ArtifactRef:
    """Persist the same bounded 40-row synthetic HTE input used by the owner path."""
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


def test_hte_source_privacy_falsifier_rejects_renamed_copied_payload_with_canary() -> None:
    from _helpers.hte_privacy import hte_source_privacy_violations

    source_only_sample_id = "hte-source-only::renamed-copy-falsifier::row-0"
    source_payload = _v2_hte_source_payload(source_only_sample_id=source_only_sample_id)
    response_wire = {
        "run": {
            "method_execution_selection": {
                "status": "withheld",
                "selection": None,
            }
        },
        "diagnostics": {
            "source_echo": {
                "candidate_payload_alias": {
                    "covariate_matrix": source_payload["covariates"],
                    "row_identifiers": source_payload["sample_ids"],
                },
                "unit_key": source_only_sample_id,
            }
        },
    }

    violations = hte_source_privacy_violations(
        response_wire,
        source_payload=source_payload,
        source_only_sample_id=source_only_sample_id,
    )

    assert "source_only_sample_id_present" in violations
    assert "source_array_value_present:covariates" in violations
    assert "source_array_value_present:sample_ids" in violations
    assert not any(item.startswith("private_array_field_present:") for item in violations)


def test_hte_source_privacy_falsifier_rejects_each_serialized_array_as_renamed_copy() -> None:
    from _helpers.hte_privacy import (
        hte_source_array_field_names,
        hte_source_privacy_violations,
    )

    source_only_sample_id = "hte-source-only::array-copy-falsifier::row-0"
    source_payload = _v2_hte_source_payload(source_only_sample_id=source_only_sample_id)
    for field_name in sorted(hte_source_array_field_names()):
        response_wire = {
            "run": {"method_execution_selection": {"status": "withheld", "selection": None}},
            "diagnostics": {
                "renamed_value": {f"unrelated_{field_name}": source_payload[field_name]}
            },
        }
        violations = hte_source_privacy_violations(
            response_wire,
            source_payload=source_payload,
            source_only_sample_id=source_only_sample_id,
        )
        assert f"source_array_value_present:{field_name}" in violations, field_name


@pytest.mark.parametrize("field_name", ["covariates", "sample_ids", "cate_values"])
def test_hte_source_privacy_falsifier_rejects_private_array_fields_outside_selection(
    field_name: str,
) -> None:
    from _helpers.hte_privacy import hte_source_privacy_violations

    source_only_sample_id = f"hte-source-only::private-field-falsifier::{field_name}"
    source_payload = _v2_hte_source_payload(source_only_sample_id=source_only_sample_id)
    response_wire = {
        "run": {"method_execution_selection": {"status": "withheld", "selection": None}},
        "diagnostics": {"unrelated_consumer": {field_name: ["redacted-shape"]}},
        "metadata": {"contract_id": "foundry.causal.hte_observational_data.v1"},
    }

    violations = hte_source_privacy_violations(
        response_wire,
        source_payload=source_payload,
        source_only_sample_id=source_only_sample_id,
    )

    assert f"private_array_field_present:{field_name}" in violations
    assert "source_only_sample_id_present" not in violations


def test_hte_source_privacy_falsifier_rejects_identifier_canary_outside_selection() -> None:
    from _helpers.hte_privacy import hte_source_privacy_violations

    source_only_sample_id = "hte-source-only::identifier-outside-selection::row-0"
    source_payload = _v2_hte_source_payload(source_only_sample_id=source_only_sample_id)
    response_wire = {
        "run": {"method_execution_selection": {"status": "withheld", "selection": None}},
        "diagnostics": {"unrelated_record_key": source_only_sample_id},
    }

    violations = hte_source_privacy_violations(
        response_wire,
        source_payload=source_payload,
        source_only_sample_id=source_only_sample_id,
    )

    assert violations == ("source_only_sample_id_present",)


def test_hte_source_privacy_allows_contract_ids_and_generic_metadata() -> None:
    from _helpers.hte_privacy import hte_source_privacy_violations

    from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData

    source_only_sample_id = "hte-source-only::allowed-metadata::row-0"
    source_payload = _v2_hte_source_payload(source_only_sample_id=source_only_sample_id)
    response_wire = {
        "run": {
            "method_execution_selection": {
                "contract_id": HTEObservationalData.contract_id,
                "contract_target_id": HTEObservationalData.contract_id,
                "contract_target": (
                    f"{HTEObservationalData.__module__}.{HTEObservationalData.__qualname__}"
                ),
            }
        },
        "metadata": {
            "source": "runtime_projection",
            "trace_id": "trace-allowed",
            "feature_labels": source_payload["feature_names"],
            "confounder_labels": source_payload["confounder_names"],
            "artifact_ref": {
                "kind": "ir.observation_method_input",
                "media_type": "application/json",
            },
        },
    }

    violations = hte_source_privacy_violations(
        response_wire,
        source_payload=source_payload,
        source_only_sample_id=source_only_sample_id,
    )

    assert violations == ()


def test_v2_completed_hte_is_served_by_fresh_run_details_get(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ordinary Run Details GET serves the persisted v2 HTE selection to its owner."""
    pytest.importorskip("econml")
    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker
    from _helpers.hte_privacy import hte_source_privacy_violations
    from _helpers.runtime_test_identity import fixture_identity_cell

    from polisyos.core.contracts.runtime import (
        DirectMethodExecutionSelection,
        _validate_method_execution_selection_wire_payload,
    )

    service = runtime_api_env["app"].state._control_service
    stop_embedded_control_worker(service)
    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    source_only_sample_id = "hte-source-only::v2-completed-get::row-0"
    source_payload = _v2_hte_source_payload(source_only_sample_id=source_only_sample_id)
    source_ref = _put_v2_hte_source(
        service,
        tenant_id=tenant_id,
        cell_id=cell_id,
        payload=source_payload,
    )
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
    persisted_selection = _validate_method_execution_selection_wire_payload(
        completed.method_execution_selection
    )
    assert type(persisted_selection) is DirectMethodExecutionSelection
    assert persisted_selection.hte is not None
    assert persisted_selection.hte.kind == "point_estimate"
    assert persisted_selection.attempt == completed.attempt

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        fresh = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}")
    assert fresh.status_code == 200, fresh.text
    body = fresh.json()
    assert body["run"]["run_id"] == completed.progress["core_run_id"]
    assert body["run"]["source_kind"] == "core_run"
    projection = body["run"]["method_execution_selection"]
    assert projection["status"] == "selected"
    served_selection = projection["selection"]
    from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData

    assert served_selection["contract_target_id"] == HTEObservationalData.contract_id
    assert served_selection["contract_target"] == (
        f"{HTEObservationalData.__module__}.{HTEObservationalData.__qualname__}"
    )
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
    assert served_hte == expected_hte.model_dump(mode="json")
    privacy_violations = hte_source_privacy_violations(
        body,
        source_payload=source_payload,
        source_only_sample_id=source_only_sample_id,
    )
    assert privacy_violations == (), privacy_violations

    # Same-tenant Run Details stays visible while the owner-only selection is withheld.
    with fixture_identity_cell(monkeypatch, cell_id="cell-not-owned-by-run"):
        wrong_cell = runtime_api_env["client"].get(f"/api/v1/runs/{body['run']['run_id']}")
    assert wrong_cell.status_code == 200, wrong_cell.text
    wrong_body = wrong_cell.json()
    withheld = wrong_body["run"]["method_execution_selection"]
    assert withheld["status"] == "withheld"
    assert withheld["limitations"] == ["owned_run_cell_scope_required"]
    assert withheld["selection"] is None
    wrong_cell_privacy_violations = hte_source_privacy_violations(
        wrong_body,
        source_payload=source_payload,
        source_only_sample_id=source_only_sample_id,
    )
    assert wrong_cell_privacy_violations == (), wrong_cell_privacy_violations
