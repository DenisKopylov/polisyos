"""Actual WDI/default executor and native owner chain through same-case re-entry."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts, canon
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.services import (
    acquisition_surface_execution as acquisition_surface_execution_module,
)
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionActionServiceError,
)
from polisyos.runtime.quality.acquisition_executor import LiveAcquisitionExecutionError
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteClosureError
from polisyos.runtime.quality.generation_cycle import (
    AcquisitionOverlayReentryReceipt,
    validate_generation_cycle_run,
)
from tests._helpers.acquisition_chain import make_wdi_port_case
from tests._helpers.acquisition_production import (
    install_fixture_wdi_cost_basis,
    persist_wdi_route,
)
from tests.unit.runtime.http.test_control_service_di import _build_control_service
from tests.unit.runtime.quality import test_generation_cycle as cycle_fixtures


def _closure_with_synthetic_revised_basis(closure):
    """Give the real binding seam a typed S/B divergence without forging route closure."""

    basis = closure.design_problem_basis
    revised_basis = basis.model_copy(
        update={
            "jurisdiction_time": basis.jurisdiction_time.model_copy(
                update={"region": "USA", "data_time": "2025"}
            )
        }
    )
    return SimpleNamespace(
        **{
            **closure.__dict__,
            "design_problem_basis": revised_basis,
            "design_problem_basis_ref": gy_content_hash(revised_basis.model_dump(mode="json")),
        }
    )


def _executor_probe_port(case):
    """Stop at the executor boundary and record any attempted authorized fetch."""

    attempted_constraints = []

    def stop_at_executor(**kwargs):
        attempted_constraints.append(kwargs["constraints"])
        raise AssertionError("live acquisition executor boundary was reached")

    port = acquisition_surface_execution_module.WorldBankWDIAcquisitionExecutionPort(
        authority=case.port._authority,
        registry=case.port._registry,
        provision=case.port._provision,
        provision_content_sha256=case.port._provision_content_sha256,
        runtime_state_root=case.port._runtime_state_root,
        artifact_store=case.port._artifact_store,
        executor=stop_at_executor,
    )
    return port, attempted_constraints


def test_wdi_constraints_use_revised_basis_year_with_same_basis_control():
    """The WDI binding owner selects B's year while preserving the S=B control."""

    subject = cycle_fixtures._problem("r13_wdi_basis_year_selector")
    subject = subject.model_copy(
        update={
            "jurisdiction_time": subject.jurisdiction_time.model_copy(
                update={"region": "UKR", "data_time": "2024"}
            )
        }
    )
    revised_basis = subject.model_copy(
        update={
            "jurisdiction_time": subject.jurisdiction_time.model_copy(
                update={"region": "UKR", "data_time": "2023"}
            )
        }
    )
    same_basis_view = SimpleNamespace(
        design_problem=subject,
        design_problem_basis=subject,
    )
    revised_basis_view = SimpleNamespace(
        design_problem=subject,
        design_problem_basis=revised_basis,
    )

    same_constraints = (
        acquisition_surface_execution_module._constraints_from_live_variable_route(
            same_basis_view
        )
    )
    revised_constraints = (
        acquisition_surface_execution_module._constraints_from_live_variable_route(
            revised_basis_view
        )
    )

    assert (same_constraints.country_code, same_constraints.start_year, same_constraints.end_year) == (
        "UKR",
        2024,
        2024,
    )
    assert (
        revised_constraints.country_code,
        revised_constraints.start_year,
        revised_constraints.end_year,
    ) == ("UKR", 2023, 2023)


@pytest.mark.asyncio
async def test_bridge_resume_reenters_after_current_source_passport_and_epoch(
    tmp_path, monkeypatch
):
    """A current source-bound route reaches native admission and direct bridge re-entry."""

    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    source_root = Path(__file__).resolve().parents[3]
    closure, _ = await persist_wdi_route(
        control,
        generation_cycle_repo_root=source_root,
    )
    assert validate_generation_cycle_run(closure.generation_run, repo_root=source_root) == ()
    case = make_wdi_port_case(tmp_path / "wdi", monkeypatch, control=control, closure=closure)

    quarantined = case.port.execute(closure)
    assert quarantined.disposition == "quarantined_no_growth"
    assert quarantined.admitted_observation_delta == 0
    case.appoint_native_policy()
    case.port.prepare_route_execution(closure)
    committed = case.port.execute(closure)
    assert committed.disposition == "world_committed"
    assert committed.admitted_observation_delta == 1
    assert case.bridge.artifact_store is control._artifact_store

    reentry_ref = case.bridge.resume(closure, committed.owner_receipt_refs)
    reentry = AcquisitionOverlayReentryReceipt.model_validate(
        canon.from_canonical_bytes(control._artifact_store.get_bytes(reentry_ref))
    )
    growth = case.bridge.project_growth(closure)
    assert growth is not None
    assert reentry.source_run_id == closure.generation_run.run_id
    assert reentry.design_problem_ref == closure.design_problem_ref
    assert reentry.source_cycle_index == closure.source_cycle.cycle_index
    assert reentry.new_cycle.cycle_index == closure.source_cycle.cycle_index + 1
    assert reentry.passport_id == growth.passport_id
    assert reentry.epoch_id == growth.selection.epoch_id
    assert reentry.overlay_receipt_ref == committed.overlay_admission_receipt_ref
    assert reentry.admitted_observation_count == (
        growth.previously_active_observations + growth.admitted_observation_delta
    )
    assert reentry.admitted_observation_count > 0
    assert reentry.semantic_epoch_ref == str(growth.activation.semantic_epoch_stamp.epoch_ref)
    assert reentry.semantic_epoch_production_receipt_content_hash


@pytest.mark.asyncio
async def test_revised_cycle_basis_survives_served_native_admission_and_reentry(
    tmp_path, monkeypatch
):
    """A costed cycle N>0 re-enters on its exact revision basis, under stable subject S."""

    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    source_root = Path(__file__).resolve().parents[3]
    closure, _ = await persist_wdi_route(
        control,
        generation_cycle_repo_root=source_root,
        revised_source=True,
    )
    subject = closure.design_problem_ref
    basis = closure.design_problem_basis_ref
    assert closure.source_cycle.cycle_index == 1
    assert subject == closure.generation_run.design_problem_ref
    assert subject == closure.source_cycle.design_problem_ref
    assert subject != basis
    assert closure.design_problem_basis == closure.generation_run.cycles[0].revision_request.revised_problem
    assert closure.generation_run.cycles[1].design_problem_basis_ref == basis

    case = make_wdi_port_case(tmp_path / "wdi", monkeypatch, control=control, closure=closure)
    quarantined = case.port.execute(closure)
    assert quarantined.disposition == "quarantined_no_growth"
    case.appoint_native_policy()
    case.port.prepare_route_execution(closure)
    committed = case.port.execute(closure)
    assert committed.disposition == "world_committed"
    assert committed.admitted_observation_delta == 1
    assert case.bridge.artifact_store is control._artifact_store

    reentry_ref = case.bridge.resume(closure, committed.owner_receipt_refs)
    reentry = AcquisitionOverlayReentryReceipt.model_validate(
        canon.from_canonical_bytes(control._artifact_store.get_bytes(reentry_ref))
    )
    growth = case.bridge.project_growth(closure)
    assert growth is not None
    assert reentry.source_run_id == closure.generation_run.run_id
    assert reentry.design_problem_ref == subject
    assert reentry.source_cycle_index == 1
    assert reentry.new_cycle.cycle_index == 2
    assert reentry.new_cycle.design_problem_ref == subject
    assert reentry.new_cycle.design_problem_basis_ref == basis
    assert reentry.passport_id == growth.passport_id
    assert reentry.epoch_id == growth.selection.epoch_id
    assert reentry.overlay_receipt_ref == committed.overlay_admission_receipt_ref
    assert reentry.admitted_observation_count == (
        growth.previously_active_observations + growth.admitted_observation_delta
    )
    assert reentry.semantic_epoch_ref == str(growth.activation.semantic_epoch_stamp.epoch_ref)

    prior = closure.generation_run.cycles[0]
    revised = prior.revision_request.revised_problem
    changed_basis = revised.model_copy(
        update={
            "runtime_hints": {
                **revised.runtime_hints,
                "r13_basis_removal_probe": "changed-with-subject-and-receipt-markers-retained",
            }
        }
    )
    changed_request = prior.revision_request.model_copy(update={"revised_problem": changed_basis})
    changed_prior = prior.model_copy(update={"revision_request": changed_request})
    changed_run = closure.generation_run.model_copy(
        update={"cycles": (changed_prior, *closure.generation_run.cycles[1:])}
    )
    changed_closure = closure.model_copy(update={"generation_run": changed_run})
    assert changed_closure.design_problem_ref == subject
    assert changed_closure.route_id == closure.route_id
    assert changed_closure.source_cycle.design_problem_basis_ref == basis
    with pytest.raises(AcquisitionRouteClosureError, match="source_cycle_basis_chain_invalid"):
        case.bridge._validate_reentry(changed_closure, growth, reentry)


@pytest.mark.asyncio
async def test_revised_basis_scope_refuses_before_egress_and_selector_removal_is_red(
    tmp_path, monkeypatch
):
    """B=USA/2025 cannot inherit S=UKR/2024's otherwise-valid WDI authority."""

    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    source_root = Path(__file__).resolve().parents[3]
    served_closure, _ = await persist_wdi_route(
        control,
        generation_cycle_repo_root=source_root,
    )
    assert served_closure.source_cycle.cycle_index == 0
    assert served_closure.design_problem_basis_ref == served_closure.design_problem_ref
    # A revised-source route does not currently resolve to one costed route. Isolate
    # the live binding owner with a typed S/B view; this is not a served N6 producer.
    closure = _closure_with_synthetic_revised_basis(served_closure)
    subject = closure.design_problem_ref
    basis = closure.design_problem_basis_ref
    assert closure.design_problem.jurisdiction_time.region == "UKR"
    assert closure.design_problem.jurisdiction_time.data_time == "2024"
    assert closure.design_problem_basis.jurisdiction_time.region == "USA"
    assert closure.design_problem_basis.jurisdiction_time.data_time == "2025"
    assert served_closure.source_cycle.design_problem_ref == subject
    assert served_closure.design_problem_basis_ref != basis
    assert subject == closure.generation_run.design_problem_ref
    assert subject != basis

    case = make_wdi_port_case(
        tmp_path / "wdi", monkeypatch, control=control, closure=served_closure
    )
    probe_port, attempted_constraints = _executor_probe_port(case)
    with pytest.raises(LiveAcquisitionExecutionError) as refused:
        probe_port.execute(closure)
    assert refused.value.code == "live_request_outside_authority_countries"
    assert attempted_constraints == [], "out-of-authority basis reached the executor boundary"
    assert case.transport_calls == [], "out-of-authority revised basis reached WDI egress"

    # Marker-retaining removal probe: restore the old subject selector while the
    # stable subject, revised-basis ref, and route identity remain unchanged.
    subject_only = SimpleNamespace(
        design_problem=closure.design_problem,
        design_problem_basis=closure.design_problem,
    )
    old_subject_constraints = (
        acquisition_surface_execution_module._constraints_from_live_variable_route(subject_only)
    )
    with monkeypatch.context() as removal:
        removal.setattr(
            acquisition_surface_execution_module,
            "_constraints_from_live_variable_route",
            lambda _closure: old_subject_constraints,
        )
        assert closure.design_problem_ref == subject
        assert closure.design_problem_basis_ref == basis
        with pytest.raises(AssertionError, match="executor boundary was reached"):
            probe_port.execute(closure)
    assert closure.route_id == served_closure.route_id
    assert len(attempted_constraints) == 1
    assert attempted_constraints[0].country_code == "UKR"
    assert attempted_constraints[0].start_year == 2024
    assert attempted_constraints[0].end_year == 2024
    assert case.transport_calls == []  # the injected boundary records but never sends requests


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
