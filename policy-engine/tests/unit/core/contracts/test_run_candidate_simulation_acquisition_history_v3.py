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


def _cheap_consequences() -> dict[str, Any]:
    """A typed display sample; the served test binds the real continuation."""
    return {
        "source_cycle_index": 1,
        "candidate_id": "candidate-prior",
        "candidate_content_hash": f"sha256:{'6' * 64}",
        "grounding_status": "grounding_gap",
        "grounding_current_valid": False,
        "value_status": "value_blocked",
        "value_decision_grade": "blocked",
        "value_authority_blockers": ["current_grounding_gap"],
        "value_ref": None,
        "voi_next_action": "stop",
        "voi_reason": "resource_budget_exhausted",
        "terminal_kind": "budget_exhausted",
        "refinement_decision": "stop",
        "search_iteration_status": "stopped",
        "current_planner_report_ref": _ref("runtime.acquisition_planner_report", "a"),
        "scope": "current_cheap_consequences_at_recorded_action",
        "numerical_provenance": "retained_prior",
    }


def test_v3_current_cheap_worsening_preserves_the_separate_original_numerical_occurrence() -> None:
    wire = _wire_row()
    prior = deepcopy(wire["retained_evaluation"])
    wire["current_cheap_consequences"] = _cheap_consequences()
    row = RunCandidateSimulationAcquisitionHistoryEntryV3.model_validate(wire)
    fresh = RunCandidateSimulationAcquisitionHistoryEntryV3.model_validate_json(
        row.model_dump_json()
    )
    assert fresh.retained_evaluation.model_dump(mode="json") == prior
    current = fresh.current_cheap_consequences
    assert current is not None
    assert current.value_status == "value_blocked"
    assert current.value_authority_blockers == ("current_grounding_gap",)
    assert current.numerical_provenance == "retained_prior"
    assert current.scope == "current_cheap_consequences_at_recorded_action"
    assert fresh.continuation is None
    assert fresh.new_candidate_id is None
    assert fresh.publication_authority is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_cycle_index", 2),
        ("candidate_id", "candidate-foreign"),
        ("candidate_content_hash", f"sha256:{'1' * 64}"),
        ("numerical_provenance", "new_execution"),
        ("scope", "current_numerical_occurrence"),
        ("current_planner_report_ref", _ref("foreign.artifact", "a")),
        ("refinement_decision", "abstain"),
        ("search_iteration_status", "abstained"),
        ("terminal_kind", "grounded_abstention"),
        ("voi_next_action", "advance"),
    ],
)
def test_v3_current_cheap_reaction_cannot_change_subject_or_claim_a_new_execution(
    field: str, value: Any
) -> None:
    wire = _wire_row()
    wire["current_cheap_consequences"] = {**_cheap_consequences(), field: value}
    with pytest.raises(ValidationError):
        RunCandidateSimulationAcquisitionHistoryEntryV3.model_validate(wire)


def test_candidate_v4_history_preserves_candidate_only_and_blocked_n5() -> None:
    from polisyos.core.contracts.runtime import RunCandidateSimulationAcquisitionHistoryEntryV4

    kinds = {
        "route_receipt_ref": "runtime_quality.acquisition_route_loop_receipt",
        "reentry_receipt_ref": "runtime_quality.candidate_source_reentry_receipt",
        "candidate_action_ref": "runtime_quality.acquisition_candidate_action_receipt",
        "candidate_source_ref": "runtime.quality.candidate_acquisition_source",
        "data_snapshot_ref": "fabric.data_snapshot",
        "world_model_ref": "runtime.quality.world_model_record",
        "context_job_ref": "runtime.quality.cycle_substrate_context_job",
        "model_declaration_ref": "runtime.quality.candidate_simulation_model_declaration",
        "ncm_ref": "ir.ncm_spec",
    }
    wire: dict[str, Any] = {name: _ref(kind, "1") for name, kind in kinds.items()}
    wire.update(
        route_id=f"sha256:{'2' * 64}",
        action_generation=1,
        simulation_status="simulation_blocked",
        simulation_authority_blockers=["n5_blocked"],
        source_cycle_index=0,
        continued_cycle_index=1,
        source_generation_run_content_hash=f"sha256:{'3' * 64}",
        continued_generation_run_content_hash=f"sha256:{'4' * 64}",
        basis_transition_content_hash=f"sha256:{'5' * 64}",
        limitations=["candidate_only"],
    )
    row = RunCandidateSimulationAcquisitionHistoryEntryV4.model_validate(wire)
    assert row.simulation_status == "simulation_blocked"
    assert row.observed_admission is False and row.publication_authority is False
    for field, value in (
        ("observed_admission", True),
        ("publication_authority", True),
        ("terminal_outcome", "candidate_evaluation_retained"),
        ("candidate_source_ref", _ref("fabric.data_snapshot", "1")),
        ("continued_cycle_index", 0),
    ):
        with pytest.raises(ValidationError):
            RunCandidateSimulationAcquisitionHistoryEntryV4.model_validate({**wire, field: value})


def test_v5_candidate_frontier_preserves_blocked_and_fresh_uncompared_outcomes() -> None:
    from polisyos.core.contracts.runtime import RunCandidateSimulationAcquisitionHistoryEntryV5

    route = _ref("runtime_quality.acquisition_route_loop_receipt", "1")
    action = _ref("runtime_quality.acquisition_candidate_action_receipt", "2")
    source = _ref("runtime.quality.candidate_acquisition_source", "3")
    failure = _ref("runtime_quality.candidate_source_reentry_receipt", "4")
    reentry = {
        "route_receipt_ref": route,
        "reentry_receipt_ref": failure,
        "route_id": f"sha256:{'5' * 64}",
        "action_generation": 2,
        "candidate_action_ref": action,
        "candidate_source_ref": source,
        "data_snapshot_ref": _ref("fabric.data_snapshot", "6"),
        "world_model_ref": _ref("runtime.quality.world_model_record", "7"),
        "context_job_ref": _ref("runtime.quality.cycle_substrate_context_job", "8"),
        "model_declaration_ref": _ref(
            "runtime.quality.candidate_simulation_model_declaration", "9"
        ),
        "ncm_ref": _ref("ir.ncm_spec", "a"),
        "simulation_status": "simulation_blocked",
        "simulation_authority_blockers": ["n5_blocked"],
        "source_cycle_index": 0,
        "continued_cycle_index": 1,
        "source_generation_run_content_hash": f"sha256:{'b' * 64}",
        "continued_generation_run_content_hash": f"sha256:{'c' * 64}",
        "basis_transition_content_hash": f"sha256:{'d' * 64}",
        "limitations": ["candidate_only"],
    }
    row = {
        "route_receipt_ref": route,
        "route_id": reentry["route_id"],
        "action_generation": 2,
        "terminal_outcome": "candidate_reentry_completed",
        "candidate_action_ref": action,
        "candidate_source_ref": source,
        "evaluation_decision_ref": _ref("runtime_quality.acquisition_evaluation_decision", "e"),
        "current_basis_ref": _ref("runtime_quality.acquisition_evaluation_basis", "f"),
        "selected_basis_ref": _ref("runtime_quality.acquisition_evaluation_basis", "0"),
        "selected_evaluation_witness_ref": failure,
        "comparison_result": "not_established",
        "predicate_provenance": "not_established",
        "comparison_reason_codes": ["prior_unavailable"],
        "selected_basis_role": "blocked",
        "current_basis_provenance": "not_established",
        "selected_basis_provenance": "not_established",
        "current_basis_limitations": ["candidate_only"],
        "selected_basis_limitations": ["candidate_only"],
        "frontier_ref": f"sha256:{'1' * 64}",
        "frontier_revision": 2,
        "frontier_selection": "selected",
        "reentry": reentry,
        "evaluation_provenance": "not_established",
    }
    blocked = RunCandidateSimulationAcquisitionHistoryEntryV5.model_validate(row)
    assert blocked.selected_evaluation is None and blocked.selected_n5_observation is None
    for field in (
        "route_receipt_ref",
        "candidate_action_ref",
        "candidate_source_ref",
        "reentry_receipt_ref",
    ):
        altered = deepcopy(reentry)
        altered[field]["manifest_profile_sha256"] = f"sha256:{'e' * 64}"
        with pytest.raises(ValidationError):
            RunCandidateSimulationAcquisitionHistoryEntryV5.model_validate(
                {**row, "reentry": altered}
            )
    for change in (
        {
            "selected_evaluation_witness_ref": _ref(
                "runtime_quality.candidate_source_reentry_receipt", "9"
            )
        },
        {"route_id": f"sha256:{'9' * 64}"},
        {"publication_authority": True},
        {"selected_basis_provenance": "recomputed"},
        {"comparison_reason_codes": []},
        {
            "comparison_result": "equivalent",
            "predicate_provenance": "recomputed",
            "comparison_reason_codes": [],
        },
    ):
        with pytest.raises(ValidationError):
            RunCandidateSimulationAcquisitionHistoryEntryV5.model_validate({**row, **change})
    prior = _wire_row()["retained_evaluation"]
    fresh_reentry = {
        **reentry,
        "simulation_status": "joint_simulated",
        **{
            field: prior[field]
            for field in (
                "n4_source_ref",
                "context_job_ref",
                "n5_input_ref",
                "n5_execution_ref",
                "n5_result_ref",
            )
        },
    }
    fresh = RunCandidateSimulationAcquisitionHistoryEntryV5.model_validate(
        {
            **row,
            "selected_basis_ref": prior["basis_ref"],
            "selected_basis_role": "evaluated",
            "selected_basis_provenance": "recomputed",
            "selected_evaluation": prior,
            "selected_evaluation_witness_ref": prior["n5_execution_ref"],
            "reentry": fresh_reentry,
            "evaluation_provenance": "new_execution",
        }
    )
    assert fresh.comparison_result == "not_established"
    assert fresh.evaluation_provenance == "new_execution"


def test_v5_retention_requires_equivalence_and_original_occurrence() -> None:
    from polisyos.core.contracts.runtime import RunCandidateSimulationAcquisitionHistoryEntryV5

    prior = _wire_row()["retained_evaluation"]
    row = {
        "route_receipt_ref": _ref("runtime_quality.acquisition_route_loop_receipt", "1"),
        "route_id": f"sha256:{'2' * 64}",
        "action_generation": 2,
        "terminal_outcome": "candidate_evaluation_retained",
        "candidate_action_ref": _ref("runtime_quality.acquisition_candidate_action_receipt", "3"),
        "candidate_source_ref": _ref("runtime.quality.candidate_acquisition_source", "4"),
        "evaluation_decision_ref": _ref("runtime_quality.acquisition_evaluation_decision", "5"),
        "current_basis_ref": _ref("runtime_quality.acquisition_evaluation_basis", "6"),
        "selected_basis_ref": prior["basis_ref"],
        "selected_evaluation_witness_ref": prior["n5_execution_ref"],
        "comparison_result": "equivalent",
        "predicate_provenance": "recomputed",
        "selected_basis_role": "evaluated",
        "current_basis_provenance": "recomputed",
        "selected_basis_provenance": "recomputed",
        "current_basis_limitations": ["candidate_only"],
        "selected_basis_limitations": ["candidate_only"],
        "frontier_ref": f"sha256:{'7' * 64}",
        "frontier_revision": 1,
        "frontier_selection": "selected",
        "selected_evaluation": prior,
        "current_continuation_ref": _ref(
            "runtime_quality.candidate_acquisition_retained_continuation", "8"
        ),
        "current_cheap_consequences": _cheap_consequences(),
        "evaluation_provenance": "retained_prior",
    }
    retained = RunCandidateSimulationAcquisitionHistoryEntryV5.model_validate(row)
    assert retained.selected_evaluation is not None
    assert retained.selected_evaluation.evaluation_job_id == "job-original"
    assert retained.current_cheap_consequences is not None
    assert retained.current_cheap_consequences.value_status == "value_blocked"
    for change in (
        {"comparison_result": "not_established", "predicate_provenance": "not_established"},
        {"current_continuation_ref": None},
        {"comparison_reason_codes": ["invented"]},
        {
            "selected_evaluation_witness_ref": _ref(
                "runtime.quality.candidate_simulation_execution", "9"
            )
        },
        {"current_cheap_consequences": {**_cheap_consequences(), "candidate_id": "foreign"}},
    ):
        with pytest.raises(ValidationError):
            RunCandidateSimulationAcquisitionHistoryEntryV5.model_validate({**row, **change})


@pytest.mark.parametrize("include_history", [False, True])
def test_run_details_preserves_explicit_terminal_projection_gap(include_history: bool) -> None:
    """A verified blocked terminal limits coverage without erasing earlier verified rows."""
    from polisyos.core.contracts.runtime import RunDetails

    code = "acquisition_action_history_terminal_projection_unavailable"
    projection = RunCandidateSimulationProjection.model_validate(
        {
            "run_id": "source-core-run",
            "artifact_status": "resolved",
            "source_ref": _ref("runtime.compiled_recursive_generation_cycle", "a"),
            "source_content_hash": f"sha256:{'a' * 64}",
            "acquisition_history": [_wire_row()] if include_history else [],
            "acquisition_history_limitation_code": code,
        }
    )
    run = RunDetails(
        run_id="source-core-run",
        source_kind="core_run",
        status="completed",
        candidate_simulation=projection,
    )
    restored = RunDetails.model_validate_json(run.model_dump_json()).candidate_simulation
    assert restored.acquisition_history_limitation_code == code
    assert bool(restored.acquisition_history) is include_history
    assert restored.publication_authority is False
    assert all(row.publication_authority is False for row in restored.acquisition_history)


@pytest.mark.parametrize(
    "code",
    [
        "acquisition_n4_source_not_established",
        "acquisition_action_history_not_observed",
        "acquisition_action_history_incomplete",
        "acquisition_action_history_integrity_not_established",
        "acquisition_reentry_source_not_established",
    ],
)
def test_other_history_refusals_still_prohibit_projected_rows(code: str) -> None:
    """The partial-surface exception never admits rows alongside integrity/source refusals."""
    with pytest.raises(
        ValidationError, match="candidate_projection_acquisition_history_mixed_refusal"
    ):
        RunCandidateSimulationProjection.model_validate(
            {
                "run_id": "source-core-run",
                "artifact_status": "resolved",
                "source_ref": _ref("runtime.compiled_recursive_generation_cycle", "a"),
                "source_content_hash": f"sha256:{'a' * 64}",
                "acquisition_history": [_wire_row()],
                "acquisition_history_limitation_code": code,
            }
        )
