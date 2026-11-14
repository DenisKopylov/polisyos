"""DTO compatibility controls for candidate-only initial input observations.

These tests cover Core wire shape and status invariants only. A served
producer-to-RunDetails path is verified separately by its integration owner.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.runtime import (
    RunDetails,
    RunModelInputInitialObservation,
    RunModelInputInitialObservationsProjection,
)

_PROFILE = "sha256:" + "f" * 64
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
