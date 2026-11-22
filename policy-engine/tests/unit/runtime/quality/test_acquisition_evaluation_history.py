"""Exercise retained ordinary reentry through its actual CAS and event owner."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from polisyos.core import artifacts, canon
from polisyos.runtime.http.services.control_plane_store import AcquisitionActionHeadRecord
from polisyos.runtime.quality.acquisition_evaluation import AcquisitionEvaluationDecisionV2
from polisyos.runtime.quality.acquisition_evaluation_history import _ordinary_checkpoint_reentry
from polisyos.runtime.quality.acquisition_executor import ActivatedSemanticEpochAdmissionReceipt
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionWorldGrowthBridge,
    AcquisitionWorldGrowthReceipt,
    AcquisitionWorldGrowthRoute,
)
from polisyos.runtime.quality.generation_cycle import (
    AcquisitionOverlayReentryReceipt,
    GenerationCycleRun,
    generation_cycle_run_content_hash,
)
from tests._helpers.runtime_http import _build_control_service
from tests.unit.runtime.quality.test_generation_cycle_model_input_wire import _v3_fixture

if TYPE_CHECKING:
    from pathlib import Path


def _hash(digit: str) -> str:
    return "sha256:" + digit * 64


@pytest.fixture
def retained_checkpoint(tmp_path: Path) -> SimpleNamespace:
    service = _build_control_service(tmp_path)
    head = AcquisitionActionHeadRecord(
        tenant_id="tenant",
        cell_id="cell",
        run_id="run",
        source_job_id="source",
        route_id=_hash("a"),
        action_generation=4,
        head_generation=4,
        receipt_ref=_hash("b"),
        receipt_sha256=_hash("b"),
        durable_event_id="pending",
        coarse_phase="world_committed",
        receipt_phase="world_committed_reentry_pending",
        recovery_state="reentry_recovery_required",
        job_id="ordinary-acquisition",
        predecessor_receipt_ref=_hash("c"),
        created_at=datetime.now(UTC),
    )
    growth_ref = artifacts.ArtifactRef(
        artifact_id=artifacts.ArtifactID(_hash("d")),
        kind="runtime_quality.acquisition_world_growth_receipt",
        media_type="application/json",
    )
    decision = AcquisitionEvaluationDecisionV2.model_construct(
        compiled_ref=_hash("e"), growth_receipt_ref=growth_ref
    )
    scope = {"tenant_id": head.tenant_id, "cell_id": head.cell_id, "run_id": head.run_id}
    semantic_ref = artifacts.ArtifactRef(
        artifact_id=artifacts.ArtifactID(_hash("f")),
        kind="epoch.production_receipt",
        media_type="application/json",
    )
    growth = AcquisitionWorldGrowthReceipt.model_construct(
        selection=AcquisitionWorldGrowthRoute.model_construct(
            **scope, route_id=head.route_id, epoch_id=2
        ),
        passport_id="passport",
        activation=ActivatedSemanticEpochAdmissionReceipt.model_construct(
            semantic_epoch_stamp=SimpleNamespace(epoch_ref=_hash("1")),
            semantic_epoch_production_receipt_ref=semantic_ref,
        ),
    )
    _, wire = _v3_fixture()
    run = GenerationCycleRun.model_validate(wire)
    cycle = run.cycles[-1]
    receipt = AcquisitionOverlayReentryReceipt.issue(
        source_run_id=run.run_id,
        design_problem_ref=run.design_problem_ref,
        source_cycle_index=0,
        source_candidate_ref=cycle.selected_candidate_ref,
        overlay_receipt_ref=_hash("2"),
        overlay_receipt_content_hash=_hash("3"),
        baseline_content_hash=_hash("4"),
        overlay_path="fixture-overlay",
        epoch_id=2,
        passport_id="passport",
        passport_variable_id="variable",
        admitted_observation_count=1,
        semantic_epoch_ref=_hash("1"),
        semantic_epoch_production_receipt_ref=str(semantic_ref.artifact_id),
        semantic_epoch_production_receipt_content_hash=_hash("5"),
        new_cycle=cycle,
        candidate_summaries=run.candidate_summaries,
        source_generation_run_content_hash=_hash("6"),
        continued_generation_run_content_hash=generation_cycle_run_content_hash(run),
        continued_generation_run=run,
    )
    bridge = object.__new__(AcquisitionWorldGrowthBridge)
    object.__setattr__(bridge, "artifact_store", service._artifact_store)
    object.__setattr__(bridge, "event_log", service._diagnostic_event_log)
    closure = SimpleNamespace(
        **scope,
        source_job_id=head.source_job_id,
        compiled_ref=decision.compiled_ref,
        route_id=head.route_id,
        cost_basis_hash=_hash("7"),
    )
    kind = "runtime_quality.acquisition_overlay_reentry_receipt"
    schema = "polisyos.runtime.AcquisitionOverlayReentryReceipt"
    growth_key = str(growth_ref.artifact_id).removeprefix("sha256:")
    ref = bridge._persist(
        closure,
        receipt.model_dump(mode="json"),
        kind,
        schema,
        "reentry_terminal",
        event_id="evt_acquisition_reentry_" + growth_key,
        return_selected_profile=True,
    )
    paths = canon.to_canonical_bytes([head.tenant_id, head.cell_id])
    relative = sha256(paths).hexdigest()
    pointer = (
        service._cas_root
        / "runtime/acquisition/world-growth"
        / relative
        / (growth_key + ".reentry.json")
    )
    return SimpleNamespace(
        kwargs={
            "control_service": service,
            "head": head,
            "decision": decision,
            "growth": growth,
            "reentry_ref": ref,
        },
        receipt=receipt,
        pointer=pointer,
        kind=kind,
        schema=schema,
        bridge=bridge,
        closure=closure,
    )


def test_retained_reentry_uses_its_real_growth_event_without_repair(retained_checkpoint) -> None:
    case = retained_checkpoint
    assert not case.pointer.exists()
    assert _ordinary_checkpoint_reentry(**case.kwargs) == case.receipt
    assert not case.pointer.exists()

    payload = dict(case.receipt)
    del payload["content_hash"]
    other = AcquisitionOverlayReentryReceipt.issue(
        **{**payload, "baseline_content_hash": _hash("8")}
    )
    foreign = case.bridge._persist(
        case.closure,
        other.model_dump(mode="json"),
        case.kind,
        case.schema,
        "reentry_terminal",
        event_id="evt_acquisition_other_growth",
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="ordinary_acquisition_checkpoint_reentry_event_mismatch"):
        _ordinary_checkpoint_reentry(**{**case.kwargs, "reentry_ref": foreign})


def test_retained_reentry_refuses_conflicting_pointer_and_removed_blob(retained_checkpoint) -> None:
    case = retained_checkpoint
    case.pointer.parent.mkdir(parents=True)
    case.pointer.write_text('{"receipt_ref":"' + _hash("9") + '"}', encoding="utf-8")
    with pytest.raises(
        ValueError, match="ordinary_acquisition_checkpoint_reentry_pointer_mismatch"
    ):
        _ordinary_checkpoint_reentry(**case.kwargs)

    ref = case.kwargs["reentry_ref"]
    case.pointer.write_text('{"receipt_ref":"' + str(ref.artifact_id) + '"}', encoding="utf-8")
    assert _ordinary_checkpoint_reentry(**case.kwargs) == case.receipt
    store = case.kwargs["control_service"]._artifact_store
    blob, _manifest = store._paths(ref.artifact_id)
    evidence = blob.read_bytes()
    blob.unlink()
    pointer_before = case.pointer.read_bytes()
    try:
        with pytest.raises((FileNotFoundError, ValueError, artifacts.ArtifactIntegrityError)):
            _ordinary_checkpoint_reentry(**case.kwargs)
        assert not blob.exists()
        assert case.pointer.read_bytes() == pointer_before
    finally:
        blob.write_bytes(evidence)
    assert _ordinary_checkpoint_reentry(**case.kwargs) == case.receipt
