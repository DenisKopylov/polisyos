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


def _ref(kind: str, character: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(f"sha256:{character * 64}"),
        kind=kind,
        media_type="application/json",
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
