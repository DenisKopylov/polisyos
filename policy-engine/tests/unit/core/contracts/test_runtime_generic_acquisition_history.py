"""Wire-shape controls for optional generic acquisition history."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.contracts.runtime import RunGenericCycleSimulationProjection


def _ref(kind: str, digit: str, *, selected: bool = True) -> dict[str, str | None]:
    return {
        "artifact_id": f"sha256:{digit * 64}",
        "manifest_profile_sha256": f"sha256:{'f' * 64}" if selected else None,
        "kind": kind,
        "media_type": "application/json",
    }


def _v3_history_row() -> dict[str, Any]:
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


def _resolved_projection_payload() -> dict[str, Any]:
    return {
        "run_id": "generic-run",
        "artifact_status": "resolved",
        "source_ref": _ref("runtime.compiled_recursive_generation_cycle", "a"),
        "source_content_hash": f"sha256:{'b' * 64}",
        "child_profile_status": "not_established",
        "child_profile_limitation_code": "generic_n4_source_not_established",
    }


def test_history_omission_and_explicit_none_preserve_legacy_projection_bytes() -> None:
    payload = _resolved_projection_payload()
    legacy = RunGenericCycleSimulationProjection.model_validate(payload)
    explicit_none = RunGenericCycleSimulationProjection.model_validate(
        {
            **payload,
            "acquisition_history": None,
            "acquisition_history_limitation_code": None,
        }
    )

    assert legacy.model_dump_json() == explicit_none.model_dump_json()
    assert "acquisition_history" not in legacy.model_dump(mode="json")
    assert "acquisition_history_limitation_code" not in legacy.model_dump(mode="json")


def test_history_accepts_selected_v3_rows_and_a_partial_history_limitation() -> None:
    payload = _resolved_projection_payload()
    payload.update(
        acquisition_history=[_v3_history_row()],
        acquisition_history_limitation_code="acquisition_action_history_incomplete",
    )

    projection = RunGenericCycleSimulationProjection.model_validate(payload)
    row = projection.acquisition_history[0]  # type: ignore[index]
    assert row.schema_version == "policyos.runtime.run_candidate_simulation_acquisition_history.v3"
    assert row.evaluation_decision_ref.manifest_profile_sha256 == f"sha256:{'f' * 64}"
    assert projection.acquisition_history_limitation_code == "acquisition_action_history_incomplete"
    assert projection.publication_authority is False
    assert projection.currentness_status == "not_established"


def test_history_refuses_foreign_selected_reference_kind() -> None:
    row = _v3_history_row()
    row["evaluation_decision_ref"] = _ref("foreign.artifact", "5")
    payload = _resolved_projection_payload()
    payload["acquisition_history"] = [row]

    with pytest.raises(ValidationError, match="candidate_acquisition_retention_ref_invalid"):
        RunGenericCycleSimulationProjection.model_validate(payload)


def test_history_distinguishes_unavailable_known_empty_and_unresolved_source() -> None:
    unavailable = RunGenericCycleSimulationProjection.model_validate(
        {
            "run_id": "generic-run-unavailable",
            "artifact_status": "not_established",
            "child_profile_status": "not_established",
            "child_profile_limitation_code": "generic_n4_source_not_established",
            "limitation_code": "compiled_cycle_artifact_ambiguous",
            "acquisition_history_limitation_code": "acquisition_action_history_not_observed",
        }
    )
    known_empty_payload = _resolved_projection_payload()
    known_empty_payload["acquisition_history"] = []
    known_empty = RunGenericCycleSimulationProjection.model_validate(known_empty_payload)

    assert unavailable.acquisition_history is None
    assert (
        unavailable.acquisition_history_limitation_code == "acquisition_action_history_not_observed"
    )
    assert known_empty.acquisition_history == ()
    assert known_empty.acquisition_history_limitation_code is None

    unresolved_empty = deepcopy(known_empty_payload)
    unresolved_empty.update(
        artifact_status="not_established",
        source_ref=None,
        source_content_hash=None,
        limitation_code="compiled_cycle_artifact_ambiguous",
    )
    with pytest.raises(
        ValidationError,
        match="run_generic_projection_acquisition_history_source_not_resolved",
    ):
        RunGenericCycleSimulationProjection.model_validate(unresolved_empty)
