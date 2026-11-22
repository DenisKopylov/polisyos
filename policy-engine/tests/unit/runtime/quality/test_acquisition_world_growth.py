"""Behavioral witnesses for native membership growth and empty deployment slots."""

import asyncio
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from polisyos.common import async_tools
from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core import artifacts, canon
from polisyos.runtime.quality import acquisition_world_growth as growth
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRoutePhaseReceipt,
    VerifiedAcquisitionRouteClosure,
)


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

    closure = VerifiedAcquisitionRouteClosure.model_construct(
        tenant_id=phase.tenant_id,
        cell_id=phase.cell_id,
        run_id=phase.run_id,
        source_job_id=phase.source_job_id,
        route_id=phase.route_id,
        compiled_ref=phase.compiled_ref,
        cost_basis_hash=phase.cost_basis_hash,
    )
    selected = growth.AcquisitionWorldGrowthRoute.model_construct(route_id=phase.route_id)
    with pytest.raises(CanonicalProfileRefusalError) as refused:
        bridge._validate_action_phase(closure, selected, str(selected_ref.artifact_id))

    assert refused.value.code == "canon_profile_typed_artifact_profile_mismatch"  # noqa: S101
    assert reads == []  # noqa: S101


@pytest.fixture
def native_route() -> growth.NativeDerivationRouteConfiguration:
    return growth.NativeDerivationRouteConfiguration(
        tenant_id="tenant",
        cell_id="cell",
        run_id="run",
        source_job_id="source",
        configured_port_source_ref=artifacts.ArtifactRef(
            artifact_id="sha256:" + "1" * 64,
            kind="runtime.quality.n7_configured_candidate_port_source",
            media_type="application/json",
            manifest_profile_sha256="sha256:" + "2" * 64,
        ),
    )


def test_native_reentry_timeout_preserves_legacy_configuration_serialization(
    native_route: growth.NativeDerivationRouteConfiguration,
) -> None:
    legacy = native_route.model_dump(mode="json")
    assert native_route.reentry_timeout_seconds is None  # noqa: S101
    assert "reentry_timeout_seconds" not in legacy  # noqa: S101
    assert (
        growth.NativeDerivationRouteConfiguration.model_validate(  # noqa: S101
            {**legacy, "reentry_timeout_seconds": None}
        ).model_dump(mode="json")
        == legacy
    )
    assert growth.NativeDerivationRouteConfiguration.model_validate(  # noqa: S101
        {**legacy, "reentry_timeout_seconds": 3600}
    ).model_dump(mode="json") == {**legacy, "reentry_timeout_seconds": 3600.0}


@pytest.mark.parametrize("invalid_timeout", [0, -1, float("inf"), float("nan"), True, "120"])
def test_native_reentry_timeout_requires_finite_positive_number(
    native_route: growth.NativeDerivationRouteConfiguration, invalid_timeout: object
) -> None:
    with pytest.raises(ValidationError, match="reentry_timeout_seconds"):
        growth.NativeDerivationRouteConfiguration.model_validate(
            {**native_route.model_dump(mode="json"), "reentry_timeout_seconds": invalid_timeout}
        )


@pytest.mark.parametrize(
    ("native", "selected_timeout", "default_timeout", "expected_timeout"),
    [
        pytest.param(False, None, 0.01, 0.01, id="ordinary-default"),
        pytest.param(True, None, 0.01, 0.01, id="native-default"),
        pytest.param(True, 2.0, 0.01, None, id="selected-completes"),
        pytest.param(True, 0.01, 2.0, 0.01, id="selected-expires"),
    ],
)
def test_active_overlay_native_reentry_uses_selected_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    native_route: growth.NativeDerivationRouteConfiguration,
    native: bool,
    selected_timeout: float | None,
    default_timeout: float,
    expected_timeout: float | None,
) -> None:
    monkeypatch.setattr(async_tools, "_DEFAULT_TIMEOUT_SECONDS", default_timeout)
    configuration = (
        growth.NativeDerivationRouteConfiguration.model_validate(
            {**native_route.model_dump(mode="json"), "reentry_timeout_seconds": selected_timeout}
        )
        if native
        else None
    )
    fence = tmp_path / "world.reentry.started"
    growth_ref = "sha256:" + "3" * 64
    receipt = growth.AcquisitionOverlayReentryReceipt.model_construct()
    milestones = []

    async def reenter() -> growth.AcquisitionOverlayReentryReceipt:
        assert fence.read_text() == growth_ref  # noqa: S101
        # Start the adapter timer before modeling a synchronous route proof.
        await asyncio.sleep(0)
        time.sleep(0.04)
        milestones.append("proof_complete")
        await asyncio.sleep(0.005)
        milestones.append("async_work_complete")
        return receipt

    def run() -> growth.AcquisitionOverlayReentryReceipt:
        return growth.AcquisitionWorldGrowthBridge._run_active_overlay_reentry(
            fence=fence,
            growth_ref=growth_ref,
            started=False,
            native_configuration=configuration,
            reenter=reenter,
        )

    if expected_timeout is None:
        assert run() is receipt  # noqa: S101
        assert milestones == ["proof_complete", "async_work_complete"]  # noqa: S101
    else:
        with pytest.raises(
            TimeoutError, match=f"did not complete within {expected_timeout:.3f}s"
        ) as refused:
            run()
        assert isinstance(refused.value.__cause__, TimeoutError)  # noqa: S101
        assert isinstance(refused.value.__cause__.__cause__, asyncio.CancelledError)  # noqa: S101
        assert milestones == ["proof_complete"]  # noqa: S101
    assert fence.read_text() == growth_ref  # noqa: S101


def test_settled_draft_reentry_writes_one_new_marker_and_keeps_original(
    tmp_path: Path, native_route: growth.NativeDerivationRouteConfiguration
) -> None:
    original = tmp_path / "world.reentry.started"
    retry = original.with_suffix(".settled-draft-resume")
    growth_ref = "sha256:" + "3" * 64
    original.write_text(growth_ref)
    config = native_route.model_copy(update={"reentry_timeout_seconds": 2.0})
    observed = []

    async def stop() -> growth.AcquisitionOverlayReentryReceipt:
        observed.append(retry.read_text())
        assert original.read_text() == growth_ref  # noqa: S101
        raise ValueError("short stop after new marker")

    with pytest.raises(ValueError, match="short stop"):
        growth.AcquisitionWorldGrowthBridge._run_active_overlay_reentry(
            fence=original,
            growth_ref=growth_ref,
            started=True,
            native_configuration=config,
            reenter=stop,
            draft_recovery_fence=(retry, "event-1"),
        )
    with pytest.raises(FileExistsError):
        growth.AcquisitionWorldGrowthBridge._run_active_overlay_reentry(
            fence=original,
            growth_ref=growth_ref,
            started=True,
            native_configuration=config,
            reenter=stop,
            draft_recovery_fence=(retry, "event-2"),
        )
    assert observed == ["event-1"]  # noqa: S101
    assert original.read_text() == growth_ref  # noqa: S101
    assert retry.read_text() == "event-1"  # noqa: S101
