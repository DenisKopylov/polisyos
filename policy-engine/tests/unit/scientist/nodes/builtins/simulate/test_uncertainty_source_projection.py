from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store, load_core_json_artifact
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.store import ArtifactWriteOptions, FileSystemCAS
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import MetricsRef, SimulationResult
from polisyos.core.contracts.foundry import ExecPlanRef, SimulationResultRef
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.ir.analytics.uncertainty import (
    IntervalSemantics,
    UncertaintyEnvelope,
    UncertaintySource,
    load_simulation_result_subject_uncertainty_projection,
    load_simulation_result_uncertainty_admission,
    persist_uncertainty_envelope,
)
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.scientist.nodes.builtins.simulate.uncertainty_source_projection import (
    PropagationReportV11,
    _load_validated_uncertainty_source_read,
    load_science_simulation_result_subject_uncertainty_projection,
    load_science_simulation_result_uncertainty_admission,
)


def _put(
    store: FileSystemCAS,
    *,
    kind: str,
    schema_name: str,
    schema_version: str,
    payload: object,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    return store.put_json(
        payload,
        ArtifactWriteOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
            producer=ProducerInfo(
                component="scientist.node_propagate_uncertainty@1.0.0",
                version="1.0.0",
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _source_identity(store: FileSystemCAS, ref: ArtifactRef) -> dict[str, object]:
    return {
        "ref": ref.model_dump(mode="json"),
        "content_sha256": "sha256:" + sha256(store.get_bytes(ref)).hexdigest(),
        "manifest_sha256": "sha256:" + sha256(store.get_manifest_bytes(ref)).hexdigest(),
    }


def _fixture(tmp_path) -> tuple[FileSystemCAS, SimulationResultRef, ArtifactRef]:
    store = FileSystemCAS(tmp_path / "cas")
    plan_ref = _put(
        store,
        kind="foundry.exec_plan",
        schema_name="polisyos.core.ExecPlan",
        schema_version="0.2.0",
        payload={"schema_version": "0.2.0"},
    )
    metrics_ref = _put(
        store,
        kind="foundry.metrics",
        schema_name="polisyos.core.Metrics",
        schema_version="0.1.0",
        payload={"schema_version": "0.1.0", "values": {}},
    )
    base_result = SimulationResult(
        schema_version="1.4",
        exec_plan_ref=ExecPlanRef.model_validate(plan_ref.model_dump(mode="python")),
        metrics_ref=MetricsRef.model_validate(metrics_ref.model_dump(mode="python")),
    )
    base_ref = _put(
        store,
        kind=SimulationResult.ARTIFACT_KIND,
        schema_name=SimulationResult.ARTIFACT_SCHEMA_NAME,
        schema_version=SimulationResult.ARTIFACT_SCHEMA_VERSION,
        payload=base_result.to_artifact_payload(),
    )
    diagnostic_ref = _put(
        store,
        kind="foundry.identifiability_diagnostic",
        schema_name="polisyos.core.IdentifiabilityDiagnosticResult",
        schema_version="1.0",
        payload={"diagnostic": "candidate"},
    )
    matrix_ref = _put(
        store,
        kind="foundry.identifiability_sensitivity_matrix",
        schema_name="polisyos.core.IdentifiabilitySensitivityMatrix",
        schema_version="1.0",
        payload={"matrix": "candidate"},
    )
    calibration_ref = _put(
        store,
        kind="foundry.calibration_report",
        schema_name="polisyos.foundry.CalibrationReport",
        schema_version="2.0",
        payload={"report": "candidate"},
    )
    basis_ref = _put(
        store,
        kind="foundry.calibration_execution_input_basis",
        schema_name="polisyos.foundry.CalibrationExecutionInputBasis",
        schema_version="1.0",
        payload={"basis": "candidate"},
    )
    config = PropagationConfig()
    config_ref = _put(
        store,
        kind="foundry.propagation_config",
        schema_name="polisyos.foundry.PropagationConfig",
        schema_version="1.0",
        payload=config.model_dump(mode="json"),
    )
    state_slot_subject = {
        "kind": "state_slot",
        "id": "population.total",
        "state_path": "world.population.total",
        "unit_id": "people",
    }
    response_basis_refs = [
        ("response_basis.selected_simulation_result", base_ref),
        ("response_basis.source_simulation_result", base_ref),
        ("response_basis.identifiability_diagnostic", diagnostic_ref),
        ("response_basis.sensitivity_matrix", matrix_ref),
        ("response_basis.calibration_report", calibration_ref),
        ("response_basis.propagation_config", config_ref),
        ("response_basis.calibration_execution_input_basis", basis_ref),
    ]
    response_context_refs = [("response_context.selected_result", base_ref)]
    envelope = UncertaintyEnvelope(
        point_estimate=1.0,
        confidence_interval=(0.8, 1.2),
        source=UncertaintySource.CALIBRATION,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=False,
        metadata={"candidate_only": True},
    )
    envelope_ref = persist_uncertainty_envelope(
        ensure_ir_artifact_store(store),
        envelope,
        return_selected_profile=True,
    )
    state_slot_envelope = UncertaintyEnvelope(
        point_estimate=1.0,
        confidence_interval=(0.8, 1.2),
        source=UncertaintySource.CALIBRATION,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=False,
        metadata={"candidate_only": True, "uncertainty_subject": state_slot_subject},
    )
    state_slot_envelope_ref = persist_uncertainty_envelope(
        ensure_ir_artifact_store(store),
        state_slot_envelope,
        inputs=[
            InputRef(
                artifact_id=ref.artifact_id,
                role=role,
                manifest_profile_sha256=ref.manifest_profile_sha256,
            )
            for role, ref in [*response_basis_refs, *response_context_refs]
        ],
        return_selected_profile=True,
    )
    source_identity = _source_identity(store, base_ref)
    report_payload = {
        "schema_version": "1.1",
        "input_envelope_count": 1,
        "output_metric_count": 1,
        "mapped_param_count": 0,
        "mapped_params": [],
        "mapping_status": "unresolved",
        "mapping_source": "not_established",
        "mapping_basis_status": "not_established",
        "unmapped_metric_ids": ["metric-x"],
        "missing_output_metric_ids": [],
        "methods": ["monte_carlo"],
        "diagnostics": [
            {
                "metric_id": "metric-x",
                "method": "monte_carlo",
                "diagnostics": {
                    "output_coverage_complete": True,
                    "n_samples": 0,
                    "n_valid": 0,
                    "n_failed": 0,
                },
            }
        ],
        "incomplete_output_metric_ids": [],
        "response_basis_candidate": {
            "schema_version": "1.0",
            "evidence_grade": "candidate",
            "gate_eligible": False,
            "mapping_status": "candidate_only",
            "mapping_basis_status": "candidate_only",
            "state_slot_to_moment": {"population.total": "mean"},
            "source_inputs": {"selected_result": source_identity},
            "selected_simulation_result_ref": base_ref.model_dump(mode="json"),
            "source_simulation_result_ref": base_ref.model_dump(mode="json"),
            "diagnostic_ref": diagnostic_ref.model_dump(mode="json"),
            "sensitivity_matrix_ref": matrix_ref.model_dump(mode="json"),
            "calibration_report_ref": calibration_ref.model_dump(mode="json"),
            "calibration_execution_input_basis_ref": basis_ref.model_dump(mode="json"),
            "propagation_config_ref": config_ref.model_dump(mode="json"),
            "limitation_codes": ["response_basis_candidate_only"],
            "missing_parameter_envelopes": [],
        },
        "state_slot_outputs": {
            "population.total": {
                "subject_kind": "state_slot",
                "subject_id": "population.total",
                "state_path": "world.population.total",
                "unit_id": "people",
                "response_moment": "mean",
                "envelope_ref": state_slot_envelope_ref.model_dump(mode="json"),
                "evidence_grade": "candidate",
                "gate_eligible": False,
                "input_envelope_sources": {
                    "population": {
                        "source_form": "embedded_in_selected_report",
                        "calibration_report_ref": calibration_ref.model_dump(mode="json"),
                        "calibration_execution_input_basis_ref": basis_ref.model_dump(mode="json"),
                        "content_sha256": sha256(
                            store.get_bytes(state_slot_envelope_ref)
                        ).hexdigest(),
                    }
                },
            }
        },
        "draw_outcome_provenance": {
            "schema_version": "1.0",
            "requested_draw_count": 0,
            "attempted_draw_count": 0,
            "simulation_attempt_count": 0,
            "retry_attempt_count": 0,
            "successful_draw_count": 0,
            "unattempted_draw_count": 0,
            "outcome_denominator_complete": True,
            "sampling_recipe": {
                "config": config.model_dump(mode="json"),
                "input_param_names": [],
                "input_envelope_sha256": {},
                "sample_axis": "draw",
                "joint_sample_id": None,
            },
            "input_identity_status": "not_established",
            "implementation_identity_status": "not_established",
            "draw_identity_basis": "sampling_recipe+draw_index+sampled_input_sha256",
            "failure_records": [],
        },
    }
    report_inputs = [
        InputRef(
            artifact_id=ref.artifact_id,
            role=role,
            manifest_profile_sha256=ref.manifest_profile_sha256,
        )
        for role, ref in [*response_basis_refs, *response_context_refs]
    ] + [
        InputRef(
            artifact_id=envelope_ref.artifact_id,
            role="metric_envelope.metric-x",
            manifest_profile_sha256=envelope_ref.manifest_profile_sha256,
        ),
        InputRef(artifact_id=plan_ref.artifact_id, role="input_envelope.baseline"),
        InputRef(
            artifact_id=state_slot_envelope_ref.artifact_id,
            role="state_slot_envelope.population.total",
            manifest_profile_sha256=state_slot_envelope_ref.manifest_profile_sha256,
        ),
    ]
    report_default_ref = _put(
        store,
        kind="foundry.propagation_report",
        schema_name="polisyos.foundry.PropagationReport",
        schema_version="1.1",
        payload=report_payload,
    )
    report_ref = _put(
        store,
        kind="foundry.propagation_report",
        schema_name="polisyos.foundry.PropagationReport",
        schema_version="1.1",
        payload=report_payload,
        inputs=report_inputs,
    )
    assert report_default_ref.artifact_id == report_ref.artifact_id
    assert report_default_ref.manifest_profile_sha256 != report_ref.manifest_profile_sha256

    result = SimulationResult(
        schema_version="1.4",
        exec_plan_ref=ExecPlanRef.model_validate(plan_ref.model_dump(mode="python")),
        metrics_ref=MetricsRef.model_validate(metrics_ref.model_dump(mode="python")),
        uncertainty_envelopes={
            "metric-x": envelope_ref,
            "population.total": state_slot_envelope_ref,
        },
        propagation_config_ref=config_ref,
        propagation_report_ref=report_ref,
    )
    result_payload = result.to_artifact_payload()
    result_inputs = [
        InputRef(
            artifact_id=base_ref.artifact_id,
            role="base_simulation_result",
            manifest_profile_sha256=base_ref.manifest_profile_sha256,
        ),
        InputRef(
            artifact_id=config_ref.artifact_id,
            role="propagation_config",
            manifest_profile_sha256=config_ref.manifest_profile_sha256,
        ),
        InputRef(
            artifact_id=report_ref.artifact_id,
            role="propagation_report",
            manifest_profile_sha256=report_ref.manifest_profile_sha256,
        ),
        InputRef(
            artifact_id=envelope_ref.artifact_id,
            role="metric_envelope.metric-x",
            manifest_profile_sha256=envelope_ref.manifest_profile_sha256,
        ),
        InputRef(
            artifact_id=state_slot_envelope_ref.artifact_id,
            role="state_slot_envelope.population.total",
            manifest_profile_sha256=state_slot_envelope_ref.manifest_profile_sha256,
        ),
    ]
    sim_default_ref = _put(
        store,
        kind=SimulationResult.ARTIFACT_KIND,
        schema_name=SimulationResult.ARTIFACT_SCHEMA_NAME,
        schema_version=SimulationResult.ARTIFACT_SCHEMA_VERSION,
        payload=result_payload,
        inputs=result_inputs,
    )
    sim_ref = _put(
        store,
        kind=SimulationResult.ARTIFACT_KIND,
        schema_name=SimulationResult.ARTIFACT_SCHEMA_NAME,
        schema_version=SimulationResult.ARTIFACT_SCHEMA_VERSION,
        payload=result_payload,
        inputs=[
            *result_inputs,
            InputRef(artifact_id=plan_ref.artifact_id, role="profile_probe"),
        ],
    )
    assert sim_default_ref.artifact_id == sim_ref.artifact_id
    assert sim_default_ref.manifest_profile_sha256 != sim_ref.manifest_profile_sha256
    return (
        store,
        SimulationResultRef.model_validate(sim_ref.model_dump(mode="python")),
        report_ref,
    )


def test_science_bridge_reads_full_owner_grammar_at_exact_nondefault_profiles(
    tmp_path,
) -> None:
    store, simulation_ref, report_ref = _fixture(tmp_path)

    projection = _load_validated_uncertainty_source_read(store, simulation_ref)

    assert projection.simulation_result_ref.manifest_profile_sha256 == (
        simulation_ref.manifest_profile_sha256
    )
    assert projection.propagation_report_ref.manifest_profile_sha256 == (
        report_ref.manifest_profile_sha256
    )
    assert PropagationReportV11.ARTIFACT_SCHEMA_VERSION == "1.1"
    assert type(projection.propagation_report) is PropagationReportV11
    assert projection.propagation_report.response_basis_candidate is not None
    assert projection.propagation_report.state_slot_outputs is not None
    assert projection.propagation_report.draw_outcome_provenance is not None
    legacy_recipe = projection.propagation_report.draw_outcome_provenance.sampling_recipe
    assert "gaussian_joint_names" not in legacy_recipe.model_dump()
    assert "gaussian_joint_assumption" not in legacy_recipe.model_dump()

    state_slot_id = next(iter(projection.propagation_report.state_slot_outputs))
    state_slot_projection = load_science_simulation_result_subject_uncertainty_projection(
        store,
        simulation_ref,
        subject_kind="state_slot",
        subject_id=state_slot_id,
    )
    assert state_slot_projection.envelope is not None
    assert state_slot_projection.candidate_only is True
    assert state_slot_projection.gate_eligible is False
    assert "source_owner_validation_not_performed" not in state_slot_projection.limitation_codes
    assert "execute_response_basis_revalidation_not_performed_by_ir" in (
        state_slot_projection.limitation_codes
    )
    assert "draw_success_ledger_missing" in state_slot_projection.limitation_codes

    admission = load_science_simulation_result_uncertainty_admission(
        store,
        simulation_ref,
        "metric-x",
    )
    assert not admission.admitted
    assert "source_owner_validation_not_performed" not in admission.limitation_codes
    assert "draw_success_ledger_missing" in admission.limitation_codes
    assert "draw_basis_verifier_missing" in admission.limitation_codes

    # Direct generic IR inspection remains candidate-only even for the same
    # exact selected nondefault refs that the Science bridge just validated.
    generic_admission = load_simulation_result_uncertainty_admission(
        ensure_ir_artifact_store(store),
        simulation_ref,
        "metric-x",
    )
    assert "source_owner_validation_not_performed" in generic_admission.limitation_codes
    generic_state_slot = load_simulation_result_subject_uncertainty_projection(
        ensure_ir_artifact_store(store),
        simulation_ref,
        subject_kind="state_slot",
        subject_id=state_slot_id,
    )
    assert "source_owner_validation_not_performed" in generic_state_slot.limitation_codes


def test_malicious_permissive_carrier_cannot_attest_unknown_live_report_bytes(
    tmp_path,
) -> None:
    store, simulation_ref, report_ref = _fixture(tmp_path)
    raw_report = load_core_json_artifact(store, report_ref)
    raw_report["unowned_authority_marker"] = True
    malformed_report_ref = _put(
        store,
        kind="foundry.propagation_report",
        schema_name="polisyos.foundry.PropagationReport",
        schema_version="1.1",
        payload=raw_report,
    )
    simulation = SimulationResult.model_validate(load_core_json_artifact(store, simulation_ref))
    malformed_simulation = simulation.model_copy(
        update={"propagation_report_ref": malformed_report_ref}
    )
    malformed_simulation_ref = _put(
        store,
        kind=SimulationResult.ARTIFACT_KIND,
        schema_name=SimulationResult.ARTIFACT_SCHEMA_NAME,
        schema_version=SimulationResult.ARTIFACT_SCHEMA_VERSION,
        payload=malformed_simulation.to_artifact_payload(),
    )

    class _PermissivePayload(BaseModel):
        model_config = ConfigDict(extra="allow")

    @dataclass(frozen=True)
    class _ForgedCarrier:
        simulation_result_ref: ArtifactRefModel
        simulation_result: BaseModel
        propagation_report_ref: ArtifactRefModel
        propagation_report: BaseModel

    simulation_payload = load_core_json_artifact(store, malformed_simulation_ref)
    report_payload = load_core_json_artifact(store, malformed_report_ref)
    forged_carrier = _ForgedCarrier(
        simulation_result_ref=ArtifactRefModel.model_validate(
            malformed_simulation_ref.model_dump(mode="python")
        ),
        simulation_result=_PermissivePayload.model_validate(simulation_payload),
        propagation_report_ref=ArtifactRefModel.model_validate(
            malformed_report_ref.model_dump(mode="python")
        ),
        propagation_report=_PermissivePayload.model_validate(report_payload),
    )
    assert forged_carrier.simulation_result.model_dump(mode="json", exclude_unset=True) == (
        simulation_payload
    )
    assert forged_carrier.propagation_report.model_dump(mode="json", exclude_unset=True) == (
        report_payload
    )
    assert forged_carrier.propagation_report.model_config["extra"] == "allow"

    # The real CAS payload is still inspectable by IR but cannot be owner-validated there.
    generic_admission = load_simulation_result_uncertainty_admission(
        ensure_ir_artifact_store(store),
        malformed_simulation_ref,
        "metric-x",
    )
    assert "source_owner_validation_not_performed" in generic_admission.limitation_codes
    generic_state_slot = load_simulation_result_subject_uncertainty_projection(
        ensure_ir_artifact_store(store),
        malformed_simulation_ref,
        subject_kind="state_slot",
        subject_id="population.total",
    )
    assert "source_owner_validation_not_performed" in generic_state_slot.limitation_codes

    # The removed, never-adopted candidate kwarg cannot turn a data carrier into
    # validator provenance, even when its model dumps exactly match the live CAS.
    with pytest.raises(TypeError):
        load_simulation_result_uncertainty_admission(
            ensure_ir_artifact_store(store),
            malformed_simulation_ref,
            "metric-x",
            source_projection=forged_carrier,
        )

    refusal = load_science_simulation_result_uncertainty_admission(
        store,
        malformed_simulation_ref,
        "metric-x",
    )
    assert refusal.envelope is None
    assert refusal.limitation_codes == ("source_owner_validation_refused",)
    subject_refusal = load_science_simulation_result_subject_uncertainty_projection(
        store,
        malformed_simulation_ref,
        subject_kind="state_slot",
        subject_id="population.total",
    )
    assert subject_refusal.envelope is None
    assert subject_refusal.limitation_codes == ("source_owner_validation_refused",)


@pytest.mark.parametrize("malformation", ["unknown_field", "wrong_field_type"])
def test_science_bridge_rejects_unknown_or_malformed_producer_fields(
    tmp_path,
    malformation: str,
) -> None:
    store, simulation_ref, report_ref = _fixture(tmp_path)
    raw = load_core_json_artifact(store, report_ref)
    if malformation == "unknown_field":
        raw["unowned_authority_marker"] = True
    else:
        raw["mapped_params"] = [42]
    malformed_report_ref = _put(
        store,
        kind="foundry.propagation_report",
        schema_name="polisyos.foundry.PropagationReport",
        schema_version="1.1",
        payload=raw,
    )
    simulation = SimulationResult.model_validate(load_core_json_artifact(store, simulation_ref))
    malformed_simulation = simulation.model_copy(
        update={"propagation_report_ref": malformed_report_ref}
    )
    malformed_simulation_ref = _put(
        store,
        kind=SimulationResult.ARTIFACT_KIND,
        schema_name=SimulationResult.ARTIFACT_SCHEMA_NAME,
        schema_version=SimulationResult.ARTIFACT_SCHEMA_VERSION,
        payload=malformed_simulation.to_artifact_payload(),
    )
    with pytest.raises(ValidationError):
        _load_validated_uncertainty_source_read(store, malformed_simulation_ref)
    refusal = load_science_simulation_result_uncertainty_admission(
        store,
        malformed_simulation_ref,
        "metric-x",
    )
    assert refusal.envelope is None
    assert refusal.limitation_codes == ("source_owner_validation_refused",)
