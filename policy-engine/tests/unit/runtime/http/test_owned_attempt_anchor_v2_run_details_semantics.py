from __future__ import annotations

import json
import math
from typing import Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactGovernanceInfo, ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.owned_attempt_anchor import (
    OwnedAttemptAnchorRefusalAssociation,
    OwnedAttemptLifecycleEvent,
)
from polisyos.core.security.tenant_context import tenant_scope


def _put_v2_hte_source(
    service: Any,
    *,
    tenant_id: str,
    cell_id: str,
    wrong_target: bool = False,
) -> ArtifactRef:
    """Persist one profile-qualified, bounded synthetic HTE input."""
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
                    "contract_id": (
                        "foundry.causal.hte_observational_data.v0"
                        if wrong_target
                        else "foundry.causal.hte_observational_data.v1"
                    ),
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


def _submit_and_dispatch_v2_request(
    runtime_api_env: dict[str, Any],
    *,
    source_ref: ArtifactRef,
    method_fqn: str,
    target_scope: str,
    requested_guarantee: str,
) -> tuple[Any, dict[str, Any], Any]:
    """Create and dispatch one real control job through its ordinary worker."""
    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker

    service = runtime_api_env["app"].state._control_service
    stop_embedded_control_worker(service)
    response = runtime_api_env["client"].post(
        "/api/v1/control/runs",
        json={
            "observational_input": {
                "protocol": "method_input_envelope_v1",
                "source_ref": source_ref.model_dump(mode="json"),
                "method": {"fqn": method_fqn},
                "hte_request": {
                    "schema_version": "polisyos.runtime.observational_hte_request.v2",
                    "estimand": "mean_effect_over_selected_x",
                    "target_scope": target_scope,
                    "outcome_variable_id": "outcome.effect",
                    "treatment_variable_id": "treatment.policy",
                    "control_value": 0.0,
                    "treated_value": 1.0,
                    "alpha": 0.05,
                    "requested_guarantee": requested_guarantee,
                },
            }
        },
    )
    assert response.status_code == 200, response.text
    accepted = response.json()
    job_id = accepted["job_id"]
    assert (
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=job_id,
        )
        == job_id
    )
    record = service._control_store.get_job(job_id)
    assert record is not None
    return service, accepted, record


def test_v2_interval_semantics_and_limitations_survive_fresh_run_details_get(
    runtime_api_env: dict[str, Any],
) -> None:
    """The ordinary GET preserves native interval semantics and candidate limits."""
    pytest.importorskip("econml")
    from pydantic import TypeAdapter

    from polisyos.core.contracts.runtime import (
        DirectMethodExecutionSelection,
        MethodExecutionSelection,
    )

    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    service = runtime_api_env["app"].state._control_service
    source_ref = _put_v2_hte_source(service, tenant_id=tenant_id, cell_id=cell_id)
    service, accepted, record = _submit_and_dispatch_v2_request(
        runtime_api_env,
        source_ref=source_ref,
        method_fqn="causal.hte.causal_forest@2.0.0",
        target_scope="population",
        requested_guarantee="backend_conditional_interval",
    )
    assert record.state == "completed"
    assert record.method_execution_selection is not None
    persisted = TypeAdapter(MethodExecutionSelection).validate_python(
        record.method_execution_selection,
        strict=True,
    )
    assert type(persisted) is DirectMethodExecutionSelection
    assert persisted.hte is not None
    assert persisted.hte.kind == "interval_estimate"
    assert persisted.hte.inference_status == "native_ate_inference_validated"
    assert persisted.owned_attempt_anchor_ref is not None

    run_id = accepted["run_id"]
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        fresh = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}")
    assert fresh.status_code == 200, fresh.text
    run = fresh.json()["run"]
    projection = run["method_execution_selection"]
    assert projection["status"] == "selected"
    assert projection["candidate_only"] is True
    assert projection["request"]["method_fqn"] == "causal.hte.causal_forest@2.0.0"
    selection = projection["selection"]
    assert selection["job_id"] == accepted["job_id"]
    assert selection["run_id"] == run_id
    assert selection["attempt"] == record.attempt
    assert selection["owned_attempt_anchor_ref"] == persisted.owned_attempt_anchor_ref.model_dump(
        mode="json"
    )

    hte = selection["hte"]
    expected = persisted.hte
    assert expected is not None
    assert hte["kind"] == "interval_estimate"
    assert hte["method_profile_id"] == "econml.causal_forest_dml.native_mean@2.0"
    assert hte["method_abi_digest"] == expected.method_abi_digest
    assert hte["inference_status"] == "native_ate_inference_validated"
    assert hte["inference_reason"] is None
    assert hte["requested_alpha"] == 0.05
    assert hte["confidence_level"] == pytest.approx(0.95)
    assert hte["requested_guarantee"] == "backend_conditional_interval"
    assert hte["computed_guarantee"] == "backend_conditional_interval"
    assert hte["lower_bound"] <= hte["point_estimate"] <= hte["upper_bound"]
    assert math.isfinite(hte["lower_bound"])
    assert math.isfinite(hte["point_estimate"])
    assert math.isfinite(hte["upper_bound"])
    assert hte["point_result_ref"] is None
    assert expected.hte_result_ref is not None
    assert expected.inference_basis_ref is not None
    assert hte["hte_result_ref"] == expected.hte_result_ref.model_dump(mode="json")
    assert hte["inference_basis_ref"] == expected.inference_basis_ref.model_dump(mode="json")
    assert hte["hte_result_ref"]["kind"] == "ir.hte_result"
    assert hte["hte_result_ref"]["manifest_profile_sha256"] is not None

    relation = hte["target_relation"]
    assert relation["requested_scope"] == "population"
    assert relation["computed_scope"] == "selected_evaluation_rows"
    assert relation["scope_disposition"] == "requested_claim_not_satisfied"
    assert relation["requested_guarantee"] == "backend_conditional_interval"
    assert relation["computed_guarantee"] == "backend_conditional_interval"
    assert relation["alpha_status"] == "recomputed"
    assert relation["profile_status"] == "qualified"
    assert relation["guarantee_disposition"] == "satisfied"
    assert relation["estimand_status"] == "not_established"
    assert relation["overall_disposition"] == "requested_claim_not_satisfied"
    assert hte["measure_unit_status"] == "not_established"
    assert hte["measure_unit"] is None
    assert {
        "target_population_not_established_by_this_fit",
        "outcome_measure_unit_not_established",
        "causal_interpretation_is_conditional_on_declared_assumptions",
        "source_variable_identity_not_established",
    }.issubset(set(hte["limitations"]))
    assert set(projection["limitations"]) == {
        "candidate_input_not_external_truth",
        "scientific_validity_not_established",
        "units_and_context_not_established",
        "source_access_revalidation_not_established",
    }
    assert "covariates" not in fresh.text
    assert "cate_values" not in fresh.text


def test_v2_input_refusal_is_visible_through_fresh_run_details_get(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A worker refusal is served as a typed refusal, never a selected result."""
    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    service = runtime_api_env["app"].state._control_service
    source_ref = _put_v2_hte_source(
        service,
        tenant_id=tenant_id,
        cell_id=cell_id,
        wrong_target=True,
    )
    service, accepted, record = _submit_and_dispatch_v2_request(
        runtime_api_env,
        source_ref=source_ref,
        method_fqn="causal.hte.forest_dr@2.0.0",
        target_scope="selected_evaluation_rows",
        requested_guarantee="candidate_point",
    )
    assert record.state == "failed"
    assert record.method_execution_selection is None
    terminal_event = service._control_store.get_job_terminal_source_event_record(accepted["job_id"])
    assert terminal_event.event_type == "job_failed"
    assert terminal_event.payload["owned_attempt_failure_disposition"] == "input_refused"

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        fresh = runtime_api_env["client"].get(f"/api/v1/runs/{accepted['run_id']}")
    assert fresh.status_code == 200, fresh.text
    projection = fresh.json()["run"]["method_execution_selection"]
    assert projection["status"] == "input_refused"
    assert projection["candidate_only"] is True
    assert projection["refusal_code"] == "observational_input_refused"
    assert projection["limitations"] == ["input_refused_before_dispatch"]
    assert projection["selection"] is None
    refusal = projection["input_refusal"]
    assert refusal["schema_version"] == "1.0"
    assert refusal["status"] == "input_refusal_reconciled"
    assert refusal["job_id"] == accepted["job_id"]
    assert refusal["run_id"] == accepted["run_id"]
    typed_refusal = OwnedAttemptAnchorRefusalAssociation.model_validate_json(
        json.dumps(refusal), strict=True
    )
    expected_failed_event = OwnedAttemptLifecycleEvent(
        event_id=terminal_event.event_id,
        job_id=terminal_event.job_id,
        event_type=terminal_event.event_type,
        payload_sha256=terminal_event.payload_sha256,
        created_at=terminal_event.created_at,
    )
    assert typed_refusal.job_failed_event == expected_failed_event
    assert (typed_refusal.job_id, typed_refusal.run_id, typed_refusal.attempt) == (
        accepted["job_id"],
        accepted["run_id"],
        record.attempt,
    )
    assert typed_refusal.refusal.refusal_code == "hte_contract_target_mismatch"
    assert not any(
        key in refusal for key in ("method_result_ref", "method_evidence_ref", "outcome_ref")
    )
    assert "contract_payload" not in fresh.text
    assert "covariates" not in fresh.text

    # Change only the persisted JSON encoding after the route's first terminal-event
    # read. The owner resolver remains real; it sees the same event id and payload
    # value under different bytes, so the fresh GET must fail closed on digest drift.
    control_store = service._control_store._target
    original_resolver = service.resolve_owned_attempt_anchor_refusal_association
    tampered_event: dict[str, str | int] = {}

    def tamper_persisted_event_before_real_resolution(*, anchor_ref: Any) -> Any:
        with control_store._sqlite_connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM control_job_events "
                "WHERE event_id = ? AND job_id = ? AND event_type = 'job_failed'",
                (terminal_event.event_id, accepted["job_id"]),
            ).fetchone()
            assert row is not None
            original_payload_json = str(row[0])
            compact_payload_json = json.dumps(
                json.loads(original_payload_json),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            if compact_payload_json == original_payload_json:
                compact_payload_json = original_payload_json + " "
            updated = connection.execute(
                "UPDATE control_job_events SET payload_json = ? "
                "WHERE event_id = ? AND job_id = ? AND event_type = 'job_failed'",
                (compact_payload_json, terminal_event.event_id, accepted["job_id"]),
            )
            assert updated.rowcount == 1
            connection.commit()
        changed_event = control_store.get_job_terminal_source_event_record(accepted["job_id"])
        tampered_event.update(
            event_id=changed_event.event_id,
            payload_sha256=changed_event.payload_sha256,
        )
        return original_resolver(anchor_ref=anchor_ref)

    monkeypatch.setattr(
        service,
        "resolve_owned_attempt_anchor_refusal_association",
        tamper_persisted_event_before_real_resolution,
    )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        drifted = runtime_api_env["client"].get(f"/api/v1/runs/{accepted['run_id']}")
    assert drifted.status_code == 200, drifted.text
    drifted_projection = drifted.json()["run"]["method_execution_selection"]
    assert tampered_event["event_id"] == terminal_event.event_id
    assert tampered_event["payload_sha256"] != terminal_event.payload_sha256
    assert drifted_projection["status"] == "unavailable"
    assert drifted_projection["limitations"] == ["execution_outcome_not_established"]
    assert drifted_projection.get("input_refusal") is None
