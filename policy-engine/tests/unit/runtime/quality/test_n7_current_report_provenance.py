"""Current N7 use must not infer producer authority from a digest-shaped value."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactWriteOptions, FileSystemCAS
from polisyos.runtime.quality import acquisition_planner as owner

AT = datetime(2026, 11, 3, tzinfo=UTC)


class _CountingGateway:
    def __init__(self) -> None:
        self.calls = 0

    def acquire(self, **_kwargs: object) -> None:
        self.calls += 1
        return None


@pytest.mark.parametrize("role", ["voi_ranking", "producer_output", "calibration_feedback"])
def test_current_legacy_report_cannot_promote_unclassified_owned_cas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    unrelated = store.put_json(
        {"fixture": "same ID does not establish the report's producer role"},
        ArtifactWriteOptions(kind="fixture.unrelated_producer", media_type="application/json"),
        return_selected_profile=True,
    )
    value = str(unrelated.artifact_id)
    gap = owner.value_input_world_knowledge_requirement_gap(claim_ref="claim:current-use")
    if role != "voi_ranking":
        gap = gap.model_copy(update={f"{role}_ref": value})
    request = {"cycle_index": 0}
    world = owner.AcquisitionWorldSnapshot(world_ref="world://current")
    run_id = f"current-role-{role}"
    context_hash = owner.n7_planner_input_content_hash(
        run_id=run_id,
        acquisition_request=request,
        compiled_requirement_specs=(gap,),
        world_snapshot=world,
        capability_requirement_resolutions=None,
        design_problem=None,
        generated_at=AT,
    )
    report = owner.plan_requirement_gap_acquisition(
        run_id=run_id,
        requirement_gaps=(gap,),
        voi_report={"artifact_ref": value} if role == "voi_ranking" else None,
        generated_at=AT,
        planning_context_hash=context_hash,
    )
    assert getattr(report.acquisition_records[0], f"{role}_ref") == value
    # V1 historical storage and readback remain available; possession of this
    # unrelated selected object does not establish its semantic role today.
    report_ref = owner.persist_and_verify_acquisition_planner_report(store, report)
    assert owner.load_acquisition_planner_report(store, report_ref) == report
    gateway = _CountingGateway()
    inputs = {
        "run_id": run_id,
        "acquisition_request": request,
        "data_requirement_specs": (gap,),
        "world_snapshot": world,
        "owner_gateway": gateway,
        "generated_at": AT,
        "planner_report": report,
        "planner_report_ref": report_ref,
        "artifact_store": store,
    }
    with pytest.raises(
        owner.AcquisitionPlannerBindingError,
        match="n7_legacy_current_input_provenance_not_established",
    ):
        owner.run_acquisition_closed_loop(**inputs)
    assert gateway.calls == 0
    assert store.get_bytes(unrelated)

    # Distinguishing removal control: without the current-use check the same
    # persisted, context-bound report reaches the owner despite wrong origin.
    with monkeypatch.context() as disabled:
        disabled.setattr(owner, "_n7_require_current_report_input_provenance", lambda _report: None)
        owner.run_acquisition_closed_loop(**inputs)
    assert gateway.calls == 1


@pytest.mark.parametrize("role", ["producer_output", "calibration_feedback"])
def test_automatic_current_plan_refuses_before_report_persistence_or_gateway(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    unrelated = store.put_json(
        {"fixture": "owned but unrelated"},
        ArtifactWriteOptions(kind="fixture.unrelated_producer", media_type="application/json"),
        return_selected_profile=True,
    )
    gap = owner.value_input_world_knowledge_requirement_gap(claim_ref="claim:automatic")
    gap = gap.model_copy(update={f"{role}_ref": f"cas://{unrelated.artifact_id}"})
    gateway = _CountingGateway()
    writes: list[object] = []
    persist = owner.persist_and_verify_acquisition_planner_report

    def record_persist(*args: object, **kwargs: object):
        writes.append(args)
        return persist(*args, **kwargs)

    monkeypatch.setattr(owner, "persist_and_verify_acquisition_planner_report", record_persist)
    with pytest.raises(
        owner.AcquisitionPlannerBindingError,
        match="n7_legacy_current_input_provenance_not_established",
    ):
        owner.run_acquisition_closed_loop(
            run_id=f"automatic-{role}",
            acquisition_request={"cycle_index": 0},
            data_requirement_specs=(gap,),
            world_snapshot=owner.AcquisitionWorldSnapshot(world_ref="world://current"),
            owner_gateway=gateway,
            generated_at=AT,
            artifact_store=store,
        )
    assert writes == []
    assert gateway.calls == 0


def test_current_legacy_non_cas_locator_remains_a_declaration() -> None:
    gap = owner.value_input_world_knowledge_requirement_gap(claim_ref="claim:declared")
    gap = gap.model_copy(update={"producer_output_ref": "owner-declaration://producer/result"})
    report = owner.plan_requirement_gap_acquisition(
        run_id="current-declared-locator", requirement_gaps=(gap,), generated_at=AT
    )
    owner._n7_require_current_report_input_provenance(report)
    assert (
        report.acquisition_records[0].producer_output_ref == "owner-declaration://producer/result"
    )
