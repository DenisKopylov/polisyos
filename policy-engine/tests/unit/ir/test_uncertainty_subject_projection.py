from __future__ import annotations

from hashlib import sha256

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.store import ArtifactWriteOptions, FileSystemCAS
from polisyos.core.canon import CanonSpec
from polisyos.ir.analytics.uncertainty import (
    IntervalSemantics,
    UncertaintyEnvelope,
    UncertaintySource,
    load_simulation_result_subject_uncertainty_projection,
    persist_uncertainty_envelope,
)


def test_subject_projection_is_exported_from_the_ir_root() -> None:
    from polisyos.ir import (
        load_simulation_result_subject_uncertainty_projection as root_projection,
    )

    assert root_projection is load_simulation_result_subject_uncertainty_projection


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
                component="scientist.node_propagate_uncertainty@1.0.0", version="1.0.0"
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


def _lineage_fixture(
    tmp_path,
    *,
    keep_output_edge: bool = True,
    source_roster_case: str = "valid",
    report_schema_version: str = "1.1",
    report_payload_version: str = "1.1",
) -> tuple[FileSystemCAS, ArtifactRef, UncertaintyEnvelope, str]:
    store = FileSystemCAS(tmp_path / "cas")
    slot_id = "population.total"
    subject = {
        "kind": "state_slot",
        "id": slot_id,
        "state_path": "world.population.total",
        "unit_id": "people",
    }
    envelope = UncertaintyEnvelope(
        point_estimate=10.0,
        confidence_interval=(8.0, 12.0),
        source=UncertaintySource.CALIBRATION,
        confidence_level=0.95,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=False,
        metadata={"candidate_only": True, "uncertainty_subject": subject},
    )

    source_sim_ref = _put(
        store,
        kind="foundry.simulation_result",
        schema_name="polisyos.core.SimulationResult",
        schema_version="1.4",
        payload={"source": "selected response context"},
    )
    diagnostic_ref = _put(
        store,
        kind="foundry.identifiability_diagnostic",
        schema_name="polisyos.core.IdentifiabilityDiagnosticResult",
        schema_version="1.0",
        payload={"diagnostic": "fixture"},
    )
    matrix_ref = _put(
        store,
        kind="foundry.identifiability_sensitivity_matrix",
        schema_name="polisyos.core.IdentifiabilitySensitivityMatrix",
        schema_version="1.0",
        payload={"matrix": "fixture"},
    )
    calibration_ref = _put(
        store,
        kind="foundry.calibration_report",
        schema_name="polisyos.foundry.CalibrationReport",
        schema_version="2.0",
        payload={"report": "fixture"},
    )
    basis_ref = _put(
        store,
        kind="foundry.calibration_execution_input_basis",
        schema_name="polisyos.foundry.CalibrationExecutionInputBasis",
        schema_version="1.0",
        payload={"basis": "fixture"},
    )
    config_ref = _put(
        store,
        kind="foundry.propagation_config",
        schema_name="polisyos.foundry.PropagationConfig",
        schema_version="1.0",
        payload={"config": "fixture"},
    )
    source_context_refs = {
        "source": source_sim_ref,
        "diagnostic": diagnostic_ref,
    }
    source_inputs = {
        role: _source_identity(store, ref) for role, ref in source_context_refs.items()
    }
    report_context_refs = dict(source_context_refs)
    envelope_context_refs = dict(source_context_refs)
    if source_roster_case in {
        "orphan_edge",
        "foreign_reference",
        "foreign_candidate_source",
        "envelope_orphan_edge",
    }:
        foreign_ref = _put(
            store,
            kind="foundry.foreign_response_source",
            schema_name="polisyos.test.ForeignResponseSource",
            schema_version="1.0",
            payload={"source": "different selected CAS object"},
        )
        if source_roster_case == "orphan_edge":
            report_context_refs["orphan"] = foreign_ref
        elif source_roster_case == "foreign_reference":
            first_role = next(iter(report_context_refs))
            report_context_refs[first_role] = foreign_ref
        elif source_roster_case == "foreign_candidate_source":
            first_role = next(iter(source_inputs))
            source_inputs[first_role] = _source_identity(store, foreign_ref)
        else:
            envelope_context_refs["orphan"] = foreign_ref
    elif source_roster_case == "malformed_content_digest":
        first_role = next(iter(source_inputs))
        source_inputs[first_role]["content_sha256"] = "sha256:" + "0" * 64
    elif source_roster_case == "malformed_manifest_digest":
        first_role = next(iter(source_inputs))
        source_inputs[first_role]["manifest_sha256"] = "sha256:" + "0" * 64
    elif source_roster_case in {"malformed_profile", "missing_profile"}:
        first_role = next(iter(source_inputs))
        source_ref_payload = dict(source_inputs[first_role]["ref"])
        source_ref_payload["manifest_profile_sha256"] = (
            None if source_roster_case == "missing_profile" else "sha256:" + "0" * 64
        )
        source_inputs[first_role]["ref"] = source_ref_payload
    elif source_roster_case not in {"valid", "omitted_roster"}:
        raise ValueError(f"unsupported source roster case: {source_roster_case}")

    envelope_ref = persist_uncertainty_envelope(
        ensure_ir_artifact_store(store),
        envelope,
        inputs=[
            InputRef(
                artifact_id=ref.artifact_id,
                role=role,
                manifest_profile_sha256=ref.manifest_profile_sha256,
            )
            for role, ref in (
                ("response_basis.selected_simulation_result", source_sim_ref),
                ("response_basis.source_simulation_result", source_sim_ref),
                ("response_basis.identifiability_diagnostic", diagnostic_ref),
                ("response_basis.sensitivity_matrix", matrix_ref),
                ("response_basis.calibration_report", calibration_ref),
                ("response_basis.propagation_config", config_ref),
                ("response_basis.calibration_execution_input_basis", basis_ref),
            )
        ]
        + [
            InputRef(
                artifact_id=ref.artifact_id,
                role=f"response_context.{role}",
                manifest_profile_sha256=ref.manifest_profile_sha256,
            )
            for role, ref in envelope_context_refs.items()
        ],
        return_selected_profile=True,
    )
    refs = {
        "selected_simulation_result_ref": source_sim_ref,
        "source_simulation_result_ref": source_sim_ref,
        "diagnostic_ref": diagnostic_ref,
        "sensitivity_matrix_ref": matrix_ref,
        "calibration_report_ref": calibration_ref,
        "propagation_config_ref": config_ref,
        "calibration_execution_input_basis_ref": basis_ref,
    }
    report_inputs = [
        InputRef(
            artifact_id=ref.artifact_id,
            role=role,
            manifest_profile_sha256=ref.manifest_profile_sha256,
        )
        for role, ref in (
            ("response_basis.selected_simulation_result", source_sim_ref),
            ("response_basis.source_simulation_result", source_sim_ref),
            ("response_basis.identifiability_diagnostic", diagnostic_ref),
            ("response_basis.sensitivity_matrix", matrix_ref),
            ("response_basis.calibration_report", calibration_ref),
            ("response_basis.propagation_config", config_ref),
            ("response_basis.calibration_execution_input_basis", basis_ref),
            (f"state_slot_envelope.{slot_id}", envelope_ref),
        )
    ] + [
        InputRef(
            artifact_id=ref.artifact_id,
            role=f"response_context.{role}",
            manifest_profile_sha256=ref.manifest_profile_sha256,
        )
        for role, ref in report_context_refs.items()
    ]
    candidate_payload = {
        **{name: ref.model_dump(mode="json") for name, ref in refs.items()},
        "evidence_grade": "candidate",
        "gate_eligible": False,
    }
    if source_roster_case != "omitted_roster":
        candidate_payload["source_inputs"] = source_inputs
    report_ref = _put(
        store,
        kind="foundry.propagation_report",
        schema_name="polisyos.foundry.PropagationReport",
        schema_version=report_schema_version,
        payload={
            "schema_version": report_payload_version,
            "response_basis_candidate": candidate_payload,
            "state_slot_outputs": {
                slot_id: {
                    "subject_kind": "state_slot",
                    "subject_id": slot_id,
                    "state_path": subject["state_path"],
                    "unit_id": subject["unit_id"],
                    "envelope_ref": envelope_ref.model_dump(mode="json"),
                }
            },
        },
        inputs=report_inputs,
    )
    metrics_ref = _put(
        store,
        kind="foundry.metrics",
        schema_name="polisyos.core.Metrics",
        schema_version="1.0",
        payload={"values": {}},
    )
    sim_inputs = [
        InputRef(
            artifact_id=source_sim_ref.artifact_id,
            role="base_simulation_result",
            manifest_profile_sha256=source_sim_ref.manifest_profile_sha256,
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
    ]
    if keep_output_edge:
        sim_inputs.append(
            InputRef(
                artifact_id=envelope_ref.artifact_id,
                role=f"state_slot_envelope.{slot_id}",
                manifest_profile_sha256=envelope_ref.manifest_profile_sha256,
            )
        )
    output_sim_ref = _put(
        store,
        kind="foundry.simulation_result",
        schema_name="polisyos.core.SimulationResult",
        schema_version="1.4",
        payload={
            "schema_version": "1.4",
            "exec_plan_ref": {
                "artifact_id": str(source_sim_ref.artifact_id),
                "kind": "foundry.exec_plan",
                "media_type": "application/json",
            },
            "metrics_ref": metrics_ref.model_dump(mode="json"),
            "uncertainty_envelopes": {slot_id: envelope_ref.model_dump(mode="json")},
            "propagation_config_ref": config_ref.model_dump(mode="json"),
            "propagation_report_ref": report_ref.model_dump(mode="json"),
        },
        inputs=sim_inputs,
    )
    return store, output_sim_ref, envelope, slot_id


@pytest.mark.parametrize("report_version", ["1.1", "1.2"])
def test_state_slot_projection_resolves_exact_candidate_lineage(
    tmp_path, report_version: str
) -> None:
    store, simulation_ref, expected_envelope, slot_id = _lineage_fixture(
        tmp_path, report_schema_version=report_version, report_payload_version=report_version
    )

    projection = load_simulation_result_subject_uncertainty_projection(
        ensure_ir_artifact_store(store),
        simulation_ref,
        subject_kind="state_slot",
        subject_id=slot_id,
    )

    assert projection.envelope == expected_envelope
    assert projection.envelope_ref is not None
    assert projection.candidate_only is True
    assert projection.gate_eligible is False
    assert "execute_response_basis_revalidation_not_performed_by_ir" in projection.limitation_codes
    assert "draw_success_ledger_missing" in projection.limitation_codes
    assert "propagation_report_schema_version_mismatch" not in projection.limitation_codes
    assert "propagation_report_payload_version_mismatch" not in projection.limitation_codes


@pytest.mark.parametrize(
    ("manifest_version", "payload_version", "expected_limitation"),
    [
        ("1.1", "1.2", "propagation_report_payload_version_mismatch"),
        ("1.2", "1.1", "propagation_report_payload_version_mismatch"),
        ("1.9", "1.9", "propagation_report_schema_version_mismatch"),
    ],
)
def test_state_slot_projection_keeps_mismatched_report_versions_non_authoritative(
    tmp_path, manifest_version: str, payload_version: str, expected_limitation: str
) -> None:
    store, simulation_ref, _, slot_id = _lineage_fixture(
        tmp_path,
        report_schema_version=manifest_version,
        report_payload_version=payload_version,
    )
    projection = load_simulation_result_subject_uncertainty_projection(
        ensure_ir_artifact_store(store),
        simulation_ref,
        subject_kind="state_slot",
        subject_id=slot_id,
    )
    assert projection.gate_eligible is False
    assert expected_limitation in projection.limitation_codes


def test_state_slot_projection_rejects_missing_exact_edge_with_markers_retained(
    tmp_path,
) -> None:
    store, simulation_ref, _, slot_id = _lineage_fixture(tmp_path, keep_output_edge=False)

    projection = load_simulation_result_subject_uncertainty_projection(
        ensure_ir_artifact_store(store),
        simulation_ref,
        subject_kind="state_slot",
        subject_id=slot_id,
    )

    assert projection.envelope is None
    assert projection.gate_eligible is False
    assert f"state_slot_projection_chain_invalid:simulation:state_slot_envelope.{slot_id}" in (
        projection.limitation_codes
    )


@pytest.mark.parametrize(
    ("source_roster_case", "expected_limitation"),
    [
        (
            "orphan_edge",
            "state_slot_projection_chain_invalid:report:response_context_roster",
        ),
        (
            "foreign_reference",
            "state_slot_projection_chain_invalid:report:response_context_roster",
        ),
        (
            "foreign_candidate_source",
            "state_slot_projection_chain_invalid:report:response_context_roster",
        ),
        (
            "envelope_orphan_edge",
            "state_slot_projection_chain_invalid:envelope:response_context_roster",
        ),
        (
            "malformed_content_digest",
            "state_slot_projection_chain_invalid:report:response_context_source_identity",
        ),
        (
            "malformed_manifest_digest",
            "state_slot_projection_chain_invalid:report:response_context_source_identity",
        ),
        (
            "malformed_profile",
            "state_slot_projection_chain_invalid:report:response_context_source_identity",
        ),
        (
            "missing_profile",
            "state_slot_projection_chain_invalid:report:response_context_source_identity",
        ),
    ],
)
def test_state_slot_projection_rejects_unbound_response_context_with_markers_retained(
    tmp_path,
    source_roster_case: str,
    expected_limitation: str,
) -> None:
    from polisyos.ir.artifacts import get_json_artifact

    store, simulation_ref, _, slot_id = _lineage_fixture(
        tmp_path, source_roster_case=source_roster_case
    )
    simulation_payload = get_json_artifact(store, simulation_ref)
    report_payload = get_json_artifact(store, simulation_payload["propagation_report_ref"])
    candidate = report_payload["response_basis_candidate"]
    assert candidate["evidence_grade"] == "candidate"
    assert candidate["gate_eligible"] is False

    projection = load_simulation_result_subject_uncertainty_projection(
        ensure_ir_artifact_store(store),
        simulation_ref,
        subject_kind="state_slot",
        subject_id=slot_id,
    )

    assert projection.envelope is None
    assert projection.gate_eligible is False
    assert expected_limitation in projection.limitation_codes


def test_state_slot_projection_keeps_legacy_candidate_without_source_roster_limited(
    tmp_path,
) -> None:
    store, simulation_ref, expected_envelope, slot_id = _lineage_fixture(
        tmp_path, source_roster_case="omitted_roster"
    )

    projection = load_simulation_result_subject_uncertainty_projection(
        ensure_ir_artifact_store(store),
        simulation_ref,
        subject_kind="state_slot",
        subject_id=slot_id,
    )

    assert projection.envelope == expected_envelope
    assert projection.candidate_only is True
    assert projection.gate_eligible is False
    assert "execute_response_source_roster_not_established" in projection.limitation_codes
