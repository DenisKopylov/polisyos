"""The real non-data bridge refuses ambiguous current planner inputs."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactWriteOptions
from polisyos.runtime.quality import acquisition_planner as planner
from polisyos.runtime.quality import non_data_acquisition as bridge
from tests.unit.fabric.test_non_data_acquisition import candidate_request, make_runtime


@pytest.mark.parametrize("role", ["producer_output", "calibration_feedback"])
def test_non_data_refuses_unclassified_current_input_before_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    module, store, runtime = make_runtime(tmp_path)
    request = candidate_request(module, runtime)
    unrelated = store.put_json(
        {"fixture": "unrelated selected owner output"},
        ArtifactWriteOptions(kind="fixture.unrelated_producer", media_type="application/json"),
        return_selected_profile=True,
    )
    gap = bridge.AcquisitionGap(
        gap_id=request.gap_id,
        claim_ref=request.claim_ref,
        gap_type="legal_competence_authority",
        authority_level="governed",
        **{f"{role}_ref": str(unrelated.artifact_id)},
    )
    effects: list[str] = []
    persist = bridge.persist_acquisition_planner_report
    acquire = runtime.acquire

    def record_persist(*args: object, **kwargs: object):
        effects.append("planner_persist")
        return persist(*args, **kwargs)

    def record_acquire(*args: object, **kwargs: object):
        effects.append("fabric_acquire")
        return acquire(*args, **kwargs)

    monkeypatch.setattr(bridge, "persist_acquisition_planner_report", record_persist)
    monkeypatch.setattr(runtime, "acquire", record_acquire)
    at = datetime(2026, 11, 3, tzinfo=UTC)
    with pytest.raises(
        planner.AcquisitionPlannerBindingError,
        match="n7_legacy_current_input_provenance_not_established",
    ):
        bridge.run_non_data_acquisition(
            runtime=runtime, request=request, gap=gap, run_id="non-data-current", at=at
        )
    assert effects == []
    assert store.get_bytes(unrelated)

    # A non-CAS declaration continues through the actual planner and Fabric
    # producer, while remaining candidate-only evidence.
    declared = gap.model_copy(update={f"{role}_ref": "owner-declaration://result"})
    result = bridge.run_non_data_acquisition(
        runtime=runtime, request=request, gap=declared, run_id="non-data-declared", at=at
    )
    assert effects == ["planner_persist", "fabric_acquire"]
    assert result.receipt.authority_granted is False
    assert runtime.read_receipt(result.receipt.artifact_ref) == result.receipt
