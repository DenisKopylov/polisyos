"""Actual WDI/default executor and native owner chain through same-case re-entry."""

import pytest

from polisyos.core import artifacts, canon
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionActionServiceError,
)
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteClosureError
from polisyos.runtime.quality.generation_cycle import AcquisitionOverlayReentryReceipt
from tests._helpers.acquisition_chain import make_wdi_port_case
from tests._helpers.acquisition_production import (
    install_fixture_wdi_cost_basis,
    persist_wdi_route,
)
from tests.unit.runtime.http.test_control_service_di import _build_control_service


@pytest.mark.asyncio
@pytest.mark.parametrize("guarded_cas", [False, True])
async def test_actual_wdi_admits_delta_and_reenters_same_case(
    tmp_path, monkeypatch, request, guarded_cas
):
    if guarded_cas:
        from polisyos.runtime.http.resilience import guard_runtime_cas
        from tests.unit.runtime.http import test_control_service_di as control_fixture

        def build_guarded_store(path):
            store = guard_runtime_cas(artifacts.FileSystemCAS(path))
            request.addfinalizer(store.close)
            return store

        monkeypatch.setattr(control_fixture, "FileSystemCAS", build_guarded_store)
    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    closure, _ = await persist_wdi_route(control)
    case = make_wdi_port_case(tmp_path / "wdi", monkeypatch, control=control, closure=closure)
    quarantined = case.port.execute(closure)
    assert quarantined.disposition == "quarantined_no_growth"
    assert quarantined.admitted_observation_delta == 0
    assert case.bridge.has_deferred_admission(closure)
    original_bytes = {
        ref: control._artifact_store.get_bytes(ref) for ref in quarantined.owner_receipt_refs
    }
    fetched = tuple(case.transport_calls)
    # A new attempt without appointment remains a known negative, without another fetch.
    repeated = case.port.execute(closure)
    assert repeated.disposition == "quarantined_no_growth"
    assert tuple(case.transport_calls) == fetched
    case.appoint_native_policy()
    case.port.prepare_route_execution(closure)
    result = case.port.execute(closure)
    assert result.disposition == "world_committed"
    assert tuple(case.transport_calls) == fetched
    assert all(control._artifact_store.get_bytes(ref) == raw for ref, raw in original_bytes.items())
    assert result.admitted_observation_delta == 1
    assert len(case.transport_calls) > 0
    assert len(case.appointments) == 1
    before = tuple(case.transport_calls)
    # Lose only the post-activation acknowledgement; recover from native owner bytes.
    case.bridge._growth_pointer(case.selected).unlink()
    assert case.port.recover_owned_result(closure) == result
    assert tuple(case.transport_calls) == before
    assert case.port.project_world_growth(closure).admitted_observation_delta == 1
    ref = case.port.reenter(closure, result)
    receipt = AcquisitionOverlayReentryReceipt.model_validate(
        canon.from_canonical_bytes(control._artifact_store.get_bytes(ref))
    )
    assert receipt.source_run_id == closure.generation_run.run_id
    assert receipt.design_problem_ref == closure.design_problem_ref
    assert receipt.new_cycle.cycle_index == closure.source_cycle.cycle_index + 1
    before = tuple(case.transport_calls)
    assert case.port.resume_reentry(closure, result.owner_receipt_refs) == ref
    assert case.port.recover_owned_result(closure) == result
    assert tuple(case.transport_calls) == before
    with pytest.raises(AcquisitionActionServiceError, match="acquisition_live_attempt_exhausted"):
        case.port.execute(closure)
    # Exercise the real list/detail projection reader with the already verified port.
    service = object.__new__(AcquisitionActionService)
    service._execution_port = case.port
    service._production_execution_port = case.port
    service._authority_provider = None
    assert service._projection(closure).admitted_observation_delta == 1
    blob, _ = control._artifact_store.get_paths(
        artifacts.ArtifactID.model_validate(result.overlay_admission_receipt_ref)
    )
    native = blob.read_bytes()
    blob.unlink()
    try:
        with pytest.raises(
            AcquisitionActionServiceError, match="acquisition_native_admission_unverified"
        ):
            service._projection(closure)
    finally:
        blob.write_bytes(native)


@pytest.mark.asyncio
async def test_both_reentry_paths_keep_empty_selection_refusal(tmp_path, monkeypatch):
    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    closure, _ = await persist_wdi_route(control)
    case = make_wdi_port_case(tmp_path / "wdi", monkeypatch, control=control, closure=closure)
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthConfig

    case.bridge.config = AcquisitionWorldGrowthConfig()
    result = case.port.execute(closure)
    assert result.disposition == "quarantined_no_growth"
    assert result.admitted_observation_delta == 0
    assert case.appointments == []
    for action in (
        lambda: case.port.reenter(closure, result),
        lambda: case.port.resume_reentry(closure, result.owner_receipt_refs),
    ):
        with pytest.raises(
            AcquisitionActionServiceError, match="acquisition_live_evidence_not_admitted"
        ):
            action()


@pytest.mark.asyncio
async def test_default_wdi_cost_selection_is_absent_before_served_execution(tmp_path):
    control = _build_control_service(tmp_path / "control")
    with pytest.raises(AcquisitionRouteClosureError, match="costed_route_not_unique"):
        await persist_wdi_route(control)


@pytest.mark.asyncio
async def test_deferred_admission_refuses_unknown_outcome_and_missing_negative(
    tmp_path, monkeypatch
):
    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    closure, _ = await persist_wdi_route(control)
    case = make_wdi_port_case(tmp_path / "wdi", monkeypatch, control=control, closure=closure)
    negative = case.port.execute(closure)
    assert negative.disposition == "quarantined_no_growth"
    case.appoint_native_policy()
    fetched = tuple(case.transport_calls)
    pointer = case.bridge._growth_pointer(case.selected)
    fence = pointer.with_suffix(".admission.started")
    fence.write_text("unknown outcome; fixture before any deferred effect")
    try:
        assert case.bridge.has_admission_attempt(closure)
        assert not case.bridge.has_deferred_admission(closure)
        with pytest.raises(
            AcquisitionActionServiceError, match="acquisition_live_attempt_exhausted"
        ):
            case.port.execute(closure)
    finally:
        fence.unlink()  # Restore this fixture before any actual deferred effect.
    ref = negative.owner_receipt_refs[-1]
    blob, _ = control._artifact_store.get_paths(artifacts.ArtifactID.model_validate(ref))
    raw = blob.read_bytes()
    blob.unlink()
    try:
        assert case.bridge.has_admission_attempt(closure)
        assert not case.bridge.has_deferred_admission(closure)
        with pytest.raises(
            AcquisitionActionServiceError, match="acquisition_live_attempt_exhausted"
        ):
            case.port.execute(closure)
    finally:
        blob.write_bytes(raw)
    assert tuple(case.transport_calls) == fetched
    assert case.bridge.has_deferred_admission(closure)
