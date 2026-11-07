from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts import (
    RunCandidateSimulationAcquisitionHistoryEntry as PublicHistoryEntry,
)
from polisyos.core.contracts.runtime import (
    RunCandidateEvaluationAttemptProjection,
    RunCandidateSimulationAcquisitionContinuationProjection,
    RunCandidateSimulationAcquisitionHistoryEntry,
    RunCandidateSimulationCurrentOccurrence,
    RunCandidateSimulationModelRevision,
    RunCandidateSimulationProjection,
    RunCandidateSourceCurrentProjection,
)


def _ref(kind: str, character: str, *, manifest_profile_sha256: str | None = None) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(f"sha256:{character * 64}"),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=manifest_profile_sha256,
    )


def _model_revision_continuation() -> dict[str, object]:
    """A display-contract fixture, not a witness of Runtime basis replay."""

    def ref(kind: str, character: str) -> ArtifactRef:
        return _ref(kind, character, manifest_profile_sha256=f"sha256:{'f' * 64}")

    old_input = ref("runtime.quality.candidate_simulation_n5_input", "1")
    new_input = ref("runtime.quality.candidate_simulation_n5_input", "2")
    model_kind = "runtime.quality.candidate_simulation_model_declaration"
    revision = RunCandidateSimulationModelRevision(
        evaluation_decision_ref=ref("runtime_quality.acquisition_evaluation_decision", "3"),
        previous_input_ref=old_input,
        selected_input_ref=new_input,
        previous_declaration_ref=ref(model_kind, "4"),
        selected_declaration_ref=ref(model_kind, "5"),
        previous_ncm_ref=ref("ir.ncm_spec", "6"),
        selected_ncm_ref=ref("ir.ncm_spec", "7"),
        previous_basis_ref=ref("runtime_quality.acquisition_evaluation_basis", "8"),
        selected_basis_ref=ref("runtime_quality.acquisition_evaluation_basis", "9"),
    )
    return {
        "source_generation_run_content_hash": f"sha256:{'a' * 64}",
        "continued_generation_run_content_hash": f"sha256:{'b' * 64}",
        "source_cycle_index": 0,
        "continued_cycle_index": 1,
        "previous_n4_source_ref": ref("runtime.quality.n4_candidate_scenario_source", "a"),
        "selected_n4_source_ref": ref("runtime.quality.n4_candidate_scenario_source", "b"),
        "previous_n5_input_ref": old_input,
        "selected_n5_input_ref": new_input,
        "previous_profile_selection_ref": f"sha256:{'c' * 64}",
        "selected_profile_selection_ref": f"sha256:{'c' * 64}",
        "previous_profile_content_hash": f"sha256:{'d' * 64}",
        "selected_profile_content_hash": f"sha256:{'e' * 64}",
        "selected_target_world_slot": "government.tax_rate",
        "previous_selected_target_baseline_hash": f"sha256:{'1' * 64}",
        "selected_target_baseline_hash": f"sha256:{'1' * 64}",
        "model_revision": revision,
        "source_currentness_status": "not_established",
        "source_currentness_reason": "historical_only",
        "continuation_currentness_status": "not_established",
        "continuation_currentness_reason": "historical_only",
        "n9_status": "not_promoted",
        "n9_reason": "candidate_only",
        "current_candidate_occurrences": (
            {
                "candidate_id": "candidate-same",
                "cycle_index": 1,
                "content_hash": f"sha256:{'2' * 64}",
                "front": "quarantine",
                "certified_by_n9": False,
            },
        ),
        "current_fronts": {
            "decision_candidate_ids": (),
            "research_candidate_ids": (),
            "quarantine_candidate_ids": ("candidate-same",),
            "portfolio_candidate_ids": (),
        },
    }


def test_equal_scalar_display_requires_exact_bound_model_revision() -> None:
    payload = _model_revision_continuation()
    projection = RunCandidateSimulationAcquisitionContinuationProjection.model_validate(payload)
    assert projection.model_revision is not None
    assert projection.current_candidate_occurrences[0].front == "quarantine"
    assert projection.currentness_status == "not_established"
    assert projection.publication_authority is False
    for changed in (
        {"model_revision": None},
        {"previous_n5_input_ref": payload["selected_n5_input_ref"]},
        {"selected_target_baseline_hash": f"sha256:{'2' * 64}"},
    ):
        with pytest.raises(ValidationError, match="continuation_projection_invalid"):
            RunCandidateSimulationAcquisitionContinuationProjection.model_validate(
                {**payload, **changed}
            )
    revision = projection.model_revision.model_dump(mode="json")
    for changed in (
        {"selected_ncm_ref": revision["previous_ncm_ref"]},
        {"predicate_provenance": "consumer_asserted"},
        {"publication_authority": True},
    ):
        with pytest.raises(ValidationError):
            RunCandidateSimulationModelRevision.model_validate({**revision, **changed})


def test_reentry_history_retains_typed_observed_lineage_as_candidate_only() -> None:
    assert PublicHistoryEntry is RunCandidateSimulationAcquisitionHistoryEntry
    row = RunCandidateSimulationAcquisitionHistoryEntry(
        route_receipt_ref=_ref("runtime_quality.acquisition_route_loop_receipt", "a"),
        reentry_receipt_ref=_ref("runtime_quality.acquisition_overlay_reentry_receipt", "b"),
        route_id=f"sha256:{'c' * 64}",
        action_generation=2,
        terminal_outcome="reentry_completed",
        old_candidate_id="candidate-old",
        new_candidate_id="candidate-new",
        new_candidate_source_ref=_ref("runtime.quality.n4_candidate_scenario_source", "d"),
        origin_source_ref=None,
    )

    projection = RunCandidateSimulationProjection(
        run_id="run-a",
        artifact_status="resolved",
        source_ref=_ref("runtime.compiled_recursive_generation_cycle", "e"),
        source_content_hash=f"sha256:{'e' * 64}",
        acquisition_history=(row,),
    )

    assert projection.acquisition_history[0].old_candidate_id == "candidate-old"
    assert projection.acquisition_history[0].new_candidate_id == "candidate-new"
    assert projection.acquisition_history[0].origin_source_ref is None
    assert projection.acquisition_history[0].currentness_status == "not_established"
    assert projection.acquisition_history[0].authority_purpose == ("candidate_observation_only")
    assert projection.publication_authority is False


def test_history_refusal_cannot_be_mixed_with_resolved_rows_or_claim_authority() -> None:
    quarantine = RunCandidateSimulationAcquisitionHistoryEntry(
        route_receipt_ref=_ref("runtime_quality.acquisition_route_loop_receipt", "a"),
        route_id=f"sha256:{'c' * 64}",
        action_generation=1,
        terminal_outcome="quarantined_no_growth",
    )
    with pytest.raises(
        ValidationError, match="candidate_projection_acquisition_history_mixed_refusal"
    ):
        RunCandidateSimulationProjection(
            run_id="run-a",
            artifact_status="resolved",
            source_ref=_ref("runtime.compiled_recursive_generation_cycle", "e"),
            source_content_hash=f"sha256:{'e' * 64}",
            acquisition_history=(quarantine,),
            acquisition_history_limitation_code="acquisition_action_history_not_observed",
        )
    with pytest.raises(ValidationError):
        RunCandidateSimulationAcquisitionHistoryEntry.model_validate(
            {
                **quarantine.model_dump(mode="json"),
                "publication_authority": True,
            }
        )

    observed_quarantine = RunCandidateSimulationAcquisitionHistoryEntry(
        route_receipt_ref=_ref("runtime_quality.acquisition_route_loop_receipt", "a"),
        route_id=f"sha256:{'c' * 64}",
        action_generation=1,
        terminal_outcome="quarantined_no_growth",
        origin_source_ref=_ref("runtime.quality.n4_candidate_scenario_source", "d"),
        schema_version="policyos.runtime.run_candidate_simulation_acquisition_history.v2",
        reentry_receipt_schema_version=None,
        continuation_join_status="not_applicable",
        origin_source_binding_status="observed_only",
    )
    assert observed_quarantine.origin_source_ref is not None
    assert observed_quarantine.expected_origin_source_ref is None
    assert observed_quarantine.continuation is None


def test_same_candidate_history_binds_the_expected_root_origin_by_full_identity() -> None:
    base = {
        "route_receipt_ref": _ref("runtime_quality.acquisition_route_loop_receipt", "a"),
        "reentry_receipt_ref": _ref("runtime_quality.acquisition_overlay_reentry_receipt", "b"),
        "route_id": f"sha256:{'c' * 64}",
        "action_generation": 2,
        "terminal_outcome": "reentry_completed",
        "old_candidate_id": "candidate-same",
        "new_candidate_id": "candidate-same",
        "new_candidate_source_ref": _ref(
            "runtime.quality.n4_candidate_scenario_source",
            "d",
            manifest_profile_sha256=f"sha256:{'1' * 64}",
        ),
        "origin_source_ref": _ref(
            "runtime.quality.n4_candidate_scenario_source",
            "e",
            manifest_profile_sha256=f"sha256:{'2' * 64}",
        ),
        "expected_origin_source_ref": _ref(
            "runtime.quality.n4_candidate_scenario_source",
            "e",
            manifest_profile_sha256=f"sha256:{'2' * 64}",
        ),
        "schema_version": ("policyos.runtime.run_candidate_simulation_acquisition_history.v2"),
        "reentry_receipt_schema_version": ("policyos.runtime.acquisition_overlay_reentry.v2"),
        "continuation_join_status": "legacy_occurrence_unbound",
        "origin_source_binding_status": "verified_same_candidate_root",
    }
    row = RunCandidateSimulationAcquisitionHistoryEntry.model_validate(base)
    assert row.old_candidate_id == row.new_candidate_id
    assert row.origin_source_ref is not None
    assert row.expected_origin_source_ref is not None
    missing_expected = dict(base)
    missing_expected.pop("expected_origin_source_ref")
    with pytest.raises(
        ValidationError,
        match="candidate_acquisition_same_candidate_origin_binding_invalid",
    ):
        RunCandidateSimulationAcquisitionHistoryEntry.model_validate(missing_expected)
    expected_root_without_metadata = {
        key: value
        for key, value in base.items()
        if key
        not in {
            "schema_version",
            "reentry_receipt_schema_version",
            "continuation_join_status",
            "origin_source_binding_status",
        }
    }
    with pytest.raises(
        ValidationError,
        match="candidate_acquisition_expected_origin_without_metadata",
    ):
        RunCandidateSimulationAcquisitionHistoryEntry.model_validate(expected_root_without_metadata)
    wrong_profile_same_artifact = dict(base)
    wrong_profile_same_artifact["expected_origin_source_ref"] = _ref(
        "runtime.quality.n4_candidate_scenario_source",
        "e",
        manifest_profile_sha256=f"sha256:{'3' * 64}",
    )
    with pytest.raises(
        ValidationError,
        match="candidate_acquisition_same_candidate_origin_binding_invalid",
    ):
        RunCandidateSimulationAcquisitionHistoryEntry.model_validate(wrong_profile_same_artifact)

    legacy_without_metadata = {
        key: value
        for key, value in base.items()
        if key
        not in {
            "expected_origin_source_ref",
            "schema_version",
            "reentry_receipt_schema_version",
            "continuation_join_status",
            "origin_source_binding_status",
        }
    }
    legacy_row = RunCandidateSimulationAcquisitionHistoryEntry.model_validate(
        legacy_without_metadata
    )
    assert legacy_row.schema_version is None
    assert legacy_row.origin_source_binding_status is None

    malformed_metadata = {**base, "continuation_join_status": "self_attested"}
    with pytest.raises(ValidationError):
        RunCandidateSimulationAcquisitionHistoryEntry.model_validate(malformed_metadata)

    caller_labeled_origin = {
        **base,
        "origin_source_binding_status": "observed_only",
    }
    with pytest.raises(
        ValidationError,
        match="candidate_acquisition_origin_status_invalid",
    ):
        RunCandidateSimulationAcquisitionHistoryEntry.model_validate(caller_labeled_origin)

    unpersisted_v3_join = {
        **base,
        "reentry_receipt_schema_version": ("policyos.runtime.acquisition_overlay_reentry.v3"),
        "continuation_join_status": "v3_occurrence_joined",
    }
    with pytest.raises(
        ValidationError,
        match="candidate_acquisition_receipt_join_status_invalid",
    ):
        RunCandidateSimulationAcquisitionHistoryEntry.model_validate(unpersisted_v3_join)


def _recorded_attempt() -> dict[str, object]:
    """A wire sample; canonical owner-history replay is qualified separately."""
    return {
        "node_ref": "design-problem://attempt",
        "candidate_id": "candidate-refused",
        "candidate_content_hash": f"sha256:{'a' * 64}",
        "cycle_index": 2,
        "problem_ref": f"sha256:{'b' * 64}",
        "attempt_ref": f"sha256:{'c' * 64}",
        "failure_stage": "n8",
        "simulation_status": "joint_simulated",
        "simulation_authority_blockers": ("simulation_only_k_sim_not_world_evidence",),
        "value_status": "value_blocked",
        "value_decision_grade": "blocked",
        "value_authority_blockers": ("candidate_value_unavailable",),
        "simulation_result_ref": _ref("polisyos.runtime.joint_simulation_result", "d"),
        "n5_input_ref": _ref("runtime.quality.candidate_simulation_n5_input", "e"),
    }


def test_recorded_local_attempt_preserves_status_and_prior_n5_without_new_verification() -> None:
    row = RunCandidateEvaluationAttemptProjection.model_validate(_recorded_attempt())
    source = _ref("runtime.compiled_recursive_generation_cycle", "f")
    projection = RunCandidateSimulationProjection(
        run_id="run-a",
        artifact_status="resolved",
        source_ref=source,
        source_content_hash=str(source.artifact_id),
        candidate_evaluation_attempts=(row,),
    )
    fresh = RunCandidateSimulationProjection.model_validate_json(projection.model_dump_json())
    assert fresh.candidate_evaluation_attempts == (row,)
    assert row.simulation_status == "joint_simulated"
    assert row.value_status == "value_blocked"
    assert row.simulation_result_ref == _recorded_attempt()["simulation_result_ref"]
    assert row.numerical_result_verification == "not_established"
    assert row.publication_authority is False
    with pytest.raises(ValidationError, match="candidate_attempt_source_not_resolved"):
        RunCandidateSimulationProjection(
            run_id="run-a", artifact_status="not_established", candidate_evaluation_attempts=(row,)
        )
    empty = RunCandidateSimulationProjection(
        run_id="run-a",
        artifact_status="not_established",
        limitation_code="compiled_cycle_artifact_integrity_not_established",
    )
    assert "candidate_evaluation_attempts" not in empty.model_dump(mode="json")


@pytest.mark.parametrize(
    "change",
    [
        {"failure_stage": "n5"},
        {"simulation_status": "simulation_pending_n5"},
        {"value_status": "value_ready"},
        {"failure_scope": "shared"},
        {"scope": "execution_reservation"},
        {"numerical_result_verification": "recomputed"},
        {"publication_authority": True},
        {"simulation_result_ref": _ref("foreign.artifact", "d")},
    ],
)
def test_recorded_attempt_refuses_changed_failure_or_borrowed_authority(
    change: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        RunCandidateEvaluationAttemptProjection.model_validate({**_recorded_attempt(), **change})


def _candidate_basis_occurrence() -> dict[str, object]:
    """Display of an old accepted occurrence on a later candidate-only basis."""
    limitation = "candidate_source_basis_prior_occurrence_not_revalidated"
    return {
        "candidate_id": "candidate-historically-accepted",
        "cycle_index": 1,
        "content_hash": f"sha256:{'a' * 64}",
        "front": "research",
        "certified_by_n9": False,
        "candidate_basis_cycle_index": 2,
        "candidate_basis_content_hash": f"sha256:{'b' * 64}",
        "candidate_basis_status": "prior_basis_not_revalidated",
        "candidate_basis_limitation_code": limitation,
        "historical_front": "decision",
        "historical_certified_by_n9": True,
        "historical_value_status": "value_ready",
        "historical_value_decision_grade": "high",
        "historical_value_ref": "value://historically-accepted",
        "historical_value_blockers": (),
        "value_status": "value_pending_n8",
        "value_blockers": (limitation,),
    }


def test_candidate_basis_projection_preserves_historical_acceptance_without_current_promotion() -> (
    None
):
    row = RunCandidateSimulationCurrentOccurrence.model_validate(_candidate_basis_occurrence())
    assert row.front == "research" and row.certified_by_n9 is False
    assert row.value_status == "value_pending_n8" and row.value_ref is None
    assert row.historical_front == "decision" and row.historical_certified_by_n9 is True
    assert row.historical_value_status == "value_ready"
    assert row.historical_value_ref == "value://historically-accepted"
    assert RunCandidateSimulationCurrentOccurrence.model_validate_json(row.model_dump_json()) == row
    legacy = RunCandidateSimulationCurrentOccurrence(
        candidate_id="legacy",
        cycle_index=0,
        content_hash=f"sha256:{'c' * 64}",
        front="decision",
        certified_by_n9=True,
    )
    assert not any("basis" in key or "historical" in key for key in legacy.model_dump(mode="json"))
    assert legacy.certified_by_n9 is True


@pytest.mark.parametrize(
    "change",
    [
        {"front": "decision"},
        {"certified_by_n9": True},
        {"value_status": "value_ready"},
        {"value_ref": "value://historically-accepted"},
        {"value_decision_grade": "high"},
        {"candidate_basis_status": "recorded_on_selected_basis"},
        {"candidate_basis_content_hash": None},
        {"candidate_basis_limitation_code": None},
        {"historical_certified_by_n9": None},
        {"historical_front": "quarantine"},
        {"cycle_index": 2},
        {"value_blockers": ()},
    ],
)
def test_candidate_basis_view_refuses_old_certification_value_or_an_unbound_anchor(
    change: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="run_candidate_occurrence_basis_projection"):
        RunCandidateSimulationCurrentOccurrence.model_validate(
            {**_candidate_basis_occurrence(), **change}
        )


def _candidate_current_view() -> dict[str, object]:
    return {
        "status": "resolved",
        "generation_run_content_hash": f"sha256:{'c' * 64}",
        "basis_cycle_index": 2,
        "basis_transition_content_hash": f"sha256:{'b' * 64}",
        "occurrences": (_candidate_basis_occurrence(),),
        "fronts": {
            "decision_candidate_ids": (),
            "research_candidate_ids": ("candidate-historically-accepted",),
            "quarantine_candidate_ids": (),
            "portfolio_candidate_ids": (),
        },
    }


def test_resolved_current_view_requires_one_complete_shared_basis_and_front_denominator() -> None:
    view = RunCandidateSourceCurrentProjection.model_validate(_candidate_current_view())
    assert view.occurrences[0].historical_certified_by_n9 is True
    assert view.certified_candidate_ids == ()
    assert view.currentness_status == "not_established" and view.publication_authority is False
    legacy_row = {
        "candidate_id": "candidate-historically-accepted",
        "cycle_index": 1,
        "content_hash": f"sha256:{'a' * 64}",
        "front": "research",
        "certified_by_n9": False,
    }
    for change in (
        {"basis_transition_content_hash": f"sha256:{'d' * 64}"},
        {"generation_run_content_hash": None},
        {"certified_candidate_ids": ("candidate-historically-accepted",)},
        {"occurrences": (legacy_row,)},
        {"occurrences": (_candidate_basis_occurrence(), _candidate_basis_occurrence())},
        {
            "fronts": {
                **_candidate_current_view()["fronts"],
                "quarantine_candidate_ids": ("foreign",),
            }
        },
    ):
        with pytest.raises(ValidationError):
            RunCandidateSourceCurrentProjection.model_validate(
                {**_candidate_current_view(), **change}
            )
    unresolved = RunCandidateSourceCurrentProjection(
        status="not_established", issues=("candidate_source_current_owner_refused",)
    )
    assert unresolved.occurrences == () and unresolved.fronts is None
    with pytest.raises(ValidationError):
        RunCandidateSourceCurrentProjection.model_validate(
            {**_candidate_current_view(), "status": "not_established"}
        )
    with pytest.raises(ValidationError, match="candidate_current_projection_source_not_resolved"):
        RunCandidateSimulationProjection(
            run_id="run-a",
            artifact_status="not_established",
            candidate_source_current_projection=unresolved,
        )


def test_current_candidate_basis_preserves_quarantine_and_recorded_new_candidate_values() -> None:
    prior = RunCandidateSimulationCurrentOccurrence.model_validate(
        {
            **_candidate_basis_occurrence(),
            "front": "quarantine",
            "historical_front": "quarantine",
            "historical_certified_by_n9": False,
            "historical_value_status": "value_blocked",
            "historical_value_decision_grade": "blocked",
            "historical_value_ref": None,
        }
    )
    assert prior.front == "quarantine"
    current = RunCandidateSimulationCurrentOccurrence.model_validate(
        {
            **_candidate_basis_occurrence(),
            "cycle_index": 2,
            "candidate_basis_status": "recorded_on_selected_basis",
            "candidate_basis_limitation_code": None,
            "historical_front": "research",
            "historical_certified_by_n9": False,
            "historical_value_status": "value_conditional",
            "historical_value_decision_grade": "low",
            "historical_value_ref": "value://new-candidate",
            "historical_value_blockers": ("candidate_only",),
            "value_status": "value_conditional",
            "value_decision_grade": "low",
            "value_ref": "value://new-candidate",
            "value_blockers": ("candidate_only",),
        }
    )
    assert current.value_ref == current.historical_value_ref == "value://new-candidate"
    assert current.certified_by_n9 is False
