"""Wire-contract negatives for the distinct retained-evaluation history epoch.

These DTO samples are not producer, source admission, or Runtime success evidence.
The integrated served oracle must separately prove the owner/CAS/action/GET chain.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.contracts import (
    RunCandidateSimulationAcquisitionHistoryEntryV3 as PublicHistoryEntryV3,
)
from polisyos.core.contracts.runtime import (
    RunCandidateSimulationAcquisitionHistoryEntry,
    RunCandidateSimulationAcquisitionHistoryEntryV3,
    RunCandidateSimulationProjection,
)


def _ref(kind: str, digit: str) -> dict[str, str]:
    return {
        "artifact_id": f"sha256:{digit * 64}",
        "manifest_profile_sha256": f"sha256:{'f' * 64}",
        "kind": kind,
        "media_type": "application/json",
    }


def _wire_row() -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.run_candidate_simulation_acquisition_history.v3",
        "route_receipt_ref": _ref("runtime_quality.acquisition_route_loop_receipt", "1"),
        "route_id": f"sha256:{'2' * 64}",
        "action_generation": 3,
        "terminal_outcome": "source_admitted_evaluation_retained",
        "admitted_source_ref": _ref("data.snapshot", "3"),
        "growth_receipt_ref": _ref("runtime_quality.acquisition_world_growth_receipt", "4"),
        "evaluation_decision_ref": _ref("runtime_quality.acquisition_evaluation_decision", "5"),
        "current_continuation_ref": _ref("runtime_quality.acquisition_retained_continuation", "0"),
        "retained_evaluation": {
            "candidate_id": "candidate-prior",
            "candidate_content_hash": f"sha256:{'6' * 64}",
            "design_problem_ref": f"sha256:{'7' * 64}",
            "world_model_record_hash": f"sha256:{'8' * 64}",
            "evaluation_job_id": "job-original",
            "evaluation_run_id": "run-original",
            "generation_run_id": "generation-original",
            "cycle_index": 1,
            "n4_source_ref": _ref("runtime.quality.n4_candidate_scenario_source", "9"),
            "context_job_ref": _ref("runtime.quality.cycle_substrate_context_job", "a"),
            "n5_input_ref": _ref("runtime.quality.candidate_simulation_n5_input", "b"),
            "n5_execution_ref": _ref("runtime.quality.candidate_simulation_execution", "c"),
            "n5_result_ref": _ref("polisyos.runtime.joint_simulation_result", "d"),
            "basis_ref": _ref("runtime_quality.acquisition_evaluation_basis", "e"),
        },
    }


def test_v3_union_preserves_original_occurrence_without_new_evaluation_claim() -> None:
    assert PublicHistoryEntryV3 is RunCandidateSimulationAcquisitionHistoryEntryV3
    row = RunCandidateSimulationAcquisitionHistoryEntryV3.model_validate(_wire_row())
    projection = RunCandidateSimulationProjection.model_validate(
        {
            "run_id": "source-core-run",
            "artifact_status": "resolved",
            "source_ref": _ref("runtime.compiled_recursive_generation_cycle", "a"),
            "source_content_hash": f"sha256:{'a' * 64}",
            "acquisition_history": [row.model_dump(mode="json")],
        }
    )
    restored = RunCandidateSimulationProjection.model_validate_json(projection.model_dump_json())
    selected = restored.acquisition_history[0]
    assert isinstance(selected, RunCandidateSimulationAcquisitionHistoryEntryV3)
    assert selected.retained_evaluation.evaluation_job_id == "job-original"
    assert selected.retained_evaluation.cycle_index == 1
    assert selected.admitted_source_ref != selected.retained_evaluation.n4_source_ref
    assert selected.new_candidate_id is None
    assert selected.new_candidate_source_ref is None
    assert selected.reentry_receipt_ref is None
    assert selected.continuation is None
    assert selected.currentness_status == "not_established"
    assert selected.authority_purpose == "candidate_observation_only"
    assert selected.publication_authority is False
    with pytest.raises(ValidationError):
        RunCandidateSimulationAcquisitionHistoryEntry.model_validate(_wire_row())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "policyos.runtime.run_candidate_simulation_acquisition_history.v4"),
        ("terminal_outcome", "reentry_completed"),
        ("new_candidate_id", "candidate-new"),
        ("new_candidate_source_ref", _ref("runtime.quality.n4_candidate_scenario_source", "e")),
        ("reentry_receipt_ref", _ref("runtime_quality.acquisition_overlay_reentry_receipt", "d")),
        ("continuation", {}),
        ("retained_evaluation", None),
        ("evaluation_decision_ref", None),
        ("current_continuation_ref", None),
        ("currentness_status", "current"),
        ("publication_authority", True),
        ("authority_purpose", "publication"),
    ],
)
def test_v3_cannot_launder_retention_into_reentry_or_authority(field: str, value: Any) -> None:
    wire = _wire_row()
    wire[field] = value
    with pytest.raises(ValidationError):
        RunCandidateSimulationAcquisitionHistoryEntryV3.model_validate(wire)


@pytest.mark.parametrize(
    "field",
    [
        "n4_source_ref",
        "context_job_ref",
        "n5_input_ref",
        "n5_execution_ref",
        "n5_result_ref",
        "basis_ref",
    ],
)
def test_v3_requires_each_exact_selected_prior_evaluation_ref(field: str) -> None:
    wire = _wire_row()
    prior = wire["retained_evaluation"]
    for corrupt in (
        None,
        {**prior[field], "kind": "foreign.artifact"},
        {**prior[field], "manifest_profile_sha256": None},
    ):
        changed = deepcopy(wire)
        changed["retained_evaluation"][field] = corrupt
        with pytest.raises(ValidationError):
            RunCandidateSimulationAcquisitionHistoryEntryV3.model_validate(changed)


@pytest.mark.parametrize("corruption", ["missing", "wrong_kind", "unselected"])
def test_v3_requires_actual_source_reaction_ref(corruption: str) -> None:
    wire = _wire_row()
    if corruption == "missing":
        wire.pop("current_continuation_ref")
    elif corruption == "wrong_kind":
        wire["current_continuation_ref"]["kind"] = "foreign.artifact"
    else:
        wire["current_continuation_ref"]["manifest_profile_sha256"] = None
    with pytest.raises(ValidationError):
        RunCandidateSimulationAcquisitionHistoryEntryV3.model_validate(wire)
