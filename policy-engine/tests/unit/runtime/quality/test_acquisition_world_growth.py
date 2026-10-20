"""Behavioral witnesses for native membership growth and empty deployment slots."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core import artifacts, canon
from polisyos.runtime.quality import acquisition_world_growth as growth
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRoutePhaseReceipt


def _epoch(*, count=3, active="active", passport="passport"):
    return SimpleNamespace(
        epoch_id=7,
        passport_id=passport,
        epoch_activation_state=active,
        admitted_observation_count=count,
    )


@pytest.mark.parametrize(
    ("before", "expected"),
    [
        ((), 3),
        ((_epoch(),), 0),
        ((_epoch(active="pending_semantic_epoch"),), 3),
    ],
)
def test_membership_delta_counts_only_new_active_native_membership(before, expected):
    assert (
        growth.admitted_membership_delta(
            before=before, after=(_epoch(),), epoch_id=7, passport_id="passport"
        )
        == expected
    )


@pytest.mark.parametrize(
    "after",
    [
        (),
        (_epoch(active="pending_semantic_epoch"),),
        (_epoch(), _epoch()),
        (_epoch(passport="other"),),
    ],
)
def test_membership_delta_refuses_absent_ambiguous_or_other_passport(after):
    with pytest.raises(ValueError, match="acquisition_active_membership_unresolved"):
        growth.admitted_membership_delta(before=(), after=after, epoch_id=7, passport_id="passport")


def test_membership_delta_refuses_prior_epoch_replacement():
    with pytest.raises(ValueError, match="acquisition_prior_membership_changed"):
        growth.admitted_membership_delta(
            before=(_epoch(passport="other"),),
            after=(_epoch(),),
            epoch_id=7,
            passport_id="passport",
        )


def test_action_phase_refuses_extra_manifest_input_before_payload_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The action-phase writer's ``inputs=[]`` contract is checked at admission."""
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    source_ref = store.put_bytes(
        b"unexpected parent",
        artifacts.ArtifactWriteOptions(
            kind="fixture.unexpected-parent",
            media_type="application/octet-stream",
        ),
    )
    extra_input = artifacts.input_ref_from_artifact_ref(
        source_ref,
        role="unexpected_parent",
    )
    phase = AcquisitionRoutePhaseReceipt(
        receipt_id="phase-requested",
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="job-source",
        route_id="sha256:" + "a" * 64,
        action_generation=1,
        job_id="job-acquisition",
        compiled_ref="sha256:" + "b" * 64,
        planner_report_hash="sha256:" + "c" * 64,
        cost_basis_hash="sha256:" + "d" * 64,
        decision_ref="sha256:" + "e" * 64,
        coarse_phase="requested",
        receipt_phase="requested",
        recovery_state="none",
        generated_at=datetime(2026, 10, 20, tzinfo=UTC),
    )
    canon_spec = canon.CanonSpec(forbid_floats=False)
    payload = canon.to_canonical_bytes(phase.model_dump(mode="json"), canon_spec)
    selected_ref = store.put_bytes(
        payload,
        artifacts.ArtifactWriteOptions(
            kind="runtime_quality.acquisition_route_phase_receipt",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="polisyos.runtime.AcquisitionRoutePhaseReceipt",
                version="1.0",
            ),
            producer=artifacts.ProducerInfo(
                component="polisyos.runtime.acquisition_route_loop",
                version="2026.08.28+ds15-c02",
            ),
            governance=artifacts.ArtifactGovernanceInfo(classification="internal"),
            canon=artifacts.CanonInfo.from_spec(canon_spec),
            inputs=[extra_input],
        ),
    )
    assert store.get_bytes(selected_ref) == payload  # noqa: S101
    assert store.get_manifest(selected_ref).inputs == [extra_input]  # noqa: S101

    reads: list[str] = []
    original_get_bytes = type(store).get_bytes
    original_verify = type(store).verify

    def record_get_bytes(owner: object, ref: object) -> bytes:
        if getattr(ref, "artifact_id", ref) == selected_ref.artifact_id:
            reads.append("get_bytes")
        return original_get_bytes(owner, ref)

    def record_verify(owner: object, ref: object) -> object:
        if getattr(ref, "artifact_id", ref) == selected_ref.artifact_id:
            reads.append("verify")
        return original_verify(owner, ref)

    monkeypatch.setattr(type(store), "get_bytes", record_get_bytes)
    monkeypatch.setattr(type(store), "verify", record_verify)
    bridge = growth.AcquisitionWorldGrowthBridge.__new__(growth.AcquisitionWorldGrowthBridge)
    bridge.artifact_store = store

    with pytest.raises(CanonicalProfileRefusalError) as refused:
        bridge._validate_action_phase(None, None, str(selected_ref.artifact_id))

    assert refused.value.code == "canon_profile_typed_artifact_profile_mismatch"  # noqa: S101
    assert reads == []  # noqa: S101
