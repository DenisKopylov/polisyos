from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts import (
    RunCandidateSimulationAcquisitionHistoryEntry as PublicHistoryEntry,
)
from polisyos.core.contracts.runtime import (
    RunCandidateSimulationAcquisitionHistoryEntry,
    RunCandidateSimulationProjection,
)


def _ref(kind: str, character: str, *, manifest_profile_sha256: str | None = None) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(f"sha256:{character * 64}"),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=manifest_profile_sha256,
    )


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
