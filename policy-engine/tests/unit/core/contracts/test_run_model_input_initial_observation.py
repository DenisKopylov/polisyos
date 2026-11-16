"""DTO compatibility controls for candidate-only initial input observations.

These tests cover Core wire shape and status invariants only. A served
producer-to-RunDetails path is verified separately by its integration owner.
"""

from __future__ import annotations

import hashlib
from typing import Literal

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.runtime import (
    RunDetails,
    RunModelInputInitialObservation,
    RunModelInputInitialObservationsProjection,
)

_PROFILE = "sha256:" + "f" * 64
_RECONCILIATION_KIND = "runtime_quality.generic_model_input_initial_reconciliation"
_CLOSURE_RESIDUALS = (
    "arbitrary_code_read_set_completeness_not_established",
    "same_process_transient_slot_cell_registry_mutations_not_established",
    "opaque_seam_values_not_established",
    "generated_code_provenance_not_established",
    "loaded_code_to_file_bytes_association_not_independently_reconciled",
    "cross_machine_bitwise_reproducibility_not_established",
    "interpreter_os_integrity_not_established",
    "protected_reuse_not_established",
)


def _artifact_ref(kind: str, fill: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + fill * 64,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=_PROFILE,
    )


def _observation() -> RunModelInputInitialObservation:
    return RunModelInputInitialObservation(
        execution_job_id="control-job-source",
        actual_run_id="control-run-17",
        source_run_id="source-run-11",
        frontier_ref="sha256:" + "1" * 64,
        frontier_revision=1,
        basis_ref=_artifact_ref("runtime_quality.acquisition_evaluation_basis", "2"),
        decision_ref=_artifact_ref("runtime_quality.acquisition_evaluation_decision", "3"),
        candidate_content_hash="sha256:" + "4" * 64,
        observation_content_hash="sha256:" + "5" * 64,
        input_ref=_artifact_ref("runtime.quality.generic_cycle_simulation_n5_input", "6"),
        execution_ref=_artifact_ref("runtime.quality.generic_cycle_simulation_n5_execution", "7"),
        result_ref=_artifact_ref("polisyos.runtime.joint_simulation_result", "8"),
        current_method_input_bindings_ref=_artifact_ref("foundry.input_bindings", "9"),
        model_input_obligation_set_ref=_artifact_ref(
            "runtime.quality.model_input_obligation_set", "a"
        ),
        context_job_ref=_artifact_ref("runtime.quality.cycle_substrate_context_job", "b"),
        n4_source_ref=_artifact_ref("runtime.generation_source_handoff", "c"),
        profile_ref=_artifact_ref("runtime.quality.generic_cycle_simulation_profile", "d"),
        limitations=("initial observation is candidate-only",),
        closure_residuals=_CLOSURE_RESIDUALS,
    )


def test_initial_observation_keeps_control_and_core_run_ids_distinct() -> None:
    observation = _observation()
    projection = RunModelInputInitialObservationsProjection(
        source_job_id="control-job-source",
        core_run_id="core-run-29",
        actual_run_id="control-run-17",
        observations=(observation,),
        inventory_status="complete",
        inventory_truncated=False,
    )

    assert projection.core_run_id != projection.actual_run_id
    assert projection.observations[0].actual_run_id == "control-run-17"
    assert projection.observations[0].source_run_id == "source-run-11"
    assert projection.observations[0].observed_admission is False
    assert projection.observations[0].publication_authority is False
    assert projection.observations[0].currentness_status == "not_established"
    assert projection.observations[0].closure_residuals == _CLOSURE_RESIDUALS


def test_ordinary_completion_preserves_legacy_initial_observation_wire_bytes() -> None:
    observation = _observation()
    wire = observation.model_dump_json()

    assert len(wire.encode()) == 4105
    assert hashlib.sha256(wire.encode()).hexdigest() == (
        "a5c6ee5eacf18f1f234817cfeb3837fe2e13638d551e00aece466c86fc7fd65b"
    )
    assert "observation_origin" not in observation.model_dump(mode="json")
    assert "reconciliation_ref" not in observation.model_dump(mode="json")
    assert RunModelInputInitialObservation.model_validate_json(wire) == observation


@pytest.mark.parametrize("mode", ["validation", "serialization"])
def test_initial_observation_schema_preserves_legacy_origin_omission(
    mode: Literal["validation", "serialization"],
) -> None:
    schema = RunModelInputInitialObservation.model_json_schema(mode=mode)
    origin = schema["properties"]["observation_origin"]

    # A schema default makes generated response types require this omitted field.
    assert "default" not in origin
    assert "observation_origin" not in schema["required"]
    assert origin["enum"] == ["ordinary_completion", "historical_reconciliation"]
    assert _observation().observation_origin == "ordinary_completion"


def test_historical_reconciliation_remains_candidate_only_and_serializes_selected_ref() -> None:
    payload = _observation().model_dump(mode="python")
    payload.update(
        observation_origin="historical_reconciliation",
        reconciliation_ref=_artifact_ref(_RECONCILIATION_KIND, "e"),
    )

    observation = RunModelInputInitialObservation.model_validate(payload)
    wire = observation.model_dump(mode="json")

    assert observation.observation_origin == "historical_reconciliation"
    assert wire["observation_origin"] == "historical_reconciliation"
    assert set(wire["reconciliation_ref"]) == {
        "artifact_id",
        "kind",
        "media_type",
        "manifest_profile_sha256",
    }
    assert wire["reconciliation_ref"]["kind"] == _RECONCILIATION_KIND
    assert observation.currentness_status == "not_established"
    assert observation.observed_admission is False
    assert observation.publication_authority is False


@pytest.mark.parametrize(
    "invalid_case",
    [
        "missing_ref",
        "null_ref",
        "ordinary_with_ref",
        "wrong_origin",
        "wrong_kind",
        "wrong_media_type",
        "missing_profile",
        "null_profile",
        "malformed_profile",
        "extra_ref_field",
        "ref_subclass_field",
    ],
)
def test_initial_observation_rejects_invalid_reconciliation_ref(invalid_case: str) -> None:
    payload = _observation().model_dump(mode="python")
    reconciliation_ref = {
        "artifact_id": "sha256:" + "e" * 64,
        "kind": _RECONCILIATION_KIND,
        "media_type": "application/json",
        "manifest_profile_sha256": _PROFILE,
    }
    payload["observation_origin"] = "historical_reconciliation"
    payload["reconciliation_ref"] = reconciliation_ref

    if invalid_case == "missing_ref":
        payload.pop("reconciliation_ref")
    elif invalid_case == "null_ref":
        payload["reconciliation_ref"] = None
    elif invalid_case == "ordinary_with_ref":
        payload["observation_origin"] = "ordinary_completion"
    elif invalid_case == "wrong_origin":
        payload["observation_origin"] = "unspecified"
    elif invalid_case == "wrong_kind":
        reconciliation_ref["kind"] = "polisyos.pdc.generic_model_input_initial_reconciliation"
    elif invalid_case == "wrong_media_type":
        reconciliation_ref["media_type"] = "application/octet-stream"
    elif invalid_case == "missing_profile":
        reconciliation_ref.pop("manifest_profile_sha256")
    elif invalid_case == "null_profile":
        reconciliation_ref["manifest_profile_sha256"] = None
    elif invalid_case == "malformed_profile":
        reconciliation_ref["manifest_profile_sha256"] = "not-a-selected-profile"
    elif invalid_case == "extra_ref_field":
        reconciliation_ref["selection_note"] = "untyped extra field"
    elif invalid_case == "ref_subclass_field":

        class ExtendedArtifactRef(ArtifactRef):
            selection_note: str

        payload["reconciliation_ref"] = ExtendedArtifactRef(
            **reconciliation_ref,
            selection_note="subclass-only field",
        )

    with pytest.raises(ValidationError):
        RunModelInputInitialObservation.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("observed_admission", True),
        ("publication_authority", True),
        ("currentness_status", "current"),
        ("historical_replay_status", "asserted"),
        ("authority_purpose", "current_use_authority"),
        ("unexpected", "value"),
    ],
)
def test_initial_observation_rejects_authority_or_status_grafts(field: str, value: object) -> None:
    payload = _observation().model_dump(mode="python")
    payload[field] = value

    with pytest.raises(ValidationError):
        RunModelInputInitialObservation.model_validate(payload)


def test_initial_observation_rejects_missing_closure_residual_scope() -> None:
    payload = _observation().model_dump(mode="python")
    payload["closure_residuals"] = ()

    with pytest.raises(ValidationError):
        RunModelInputInitialObservation.model_validate(payload)


def test_legacy_run_details_omits_unset_initial_observations() -> None:
    run = RunDetails(run_id="core-run-29", source_kind="core_run", status="completed")

    assert "model_input_initial_observations" not in run.model_dump(mode="json")


def test_limited_empty_and_truncated_inventory_states_remain_explicit() -> None:
    unavailable = RunModelInputInitialObservationsProjection(
        source_job_id="control-job-source",
        core_run_id="core-run-29",
        actual_run_id=None,
        observations=(),
        inventory_status="limited",
        inventory_truncated=False,
        limitation_codes=("initial_observation_history_unavailable",),
    )
    truncated = RunModelInputInitialObservationsProjection(
        source_job_id="control-job-source",
        core_run_id="core-run-29",
        actual_run_id="control-run-17",
        observations=(),
        inventory_status="limited",
        inventory_truncated=True,
        limitation_codes=("initial_observation_frontier_inventory_truncated",),
    )

    assert unavailable.actual_run_id is None
    assert unavailable.inventory_status == "limited"
    assert not unavailable.observations
    assert truncated.inventory_truncated
    assert truncated.limitation_codes == ("initial_observation_frontier_inventory_truncated",)

    with pytest.raises(ValidationError, match="model_input_initial_observation_inventory_mismatch"):
        RunModelInputInitialObservationsProjection(
            source_job_id="control-job-source",
            core_run_id="core-run-29",
            actual_run_id=None,
            observations=(),
            inventory_status="complete",
            inventory_truncated=False,
        )

    with pytest.raises(ValidationError, match="model_input_initial_observation_inventory_mismatch"):
        RunModelInputInitialObservationsProjection(
            source_job_id="control-job-source",
            core_run_id="core-run-29",
            actual_run_id=None,
            observations=(),
            inventory_status="limited",
            inventory_truncated=True,
            limitation_codes=("initial_observation_history_unavailable",),
        )
