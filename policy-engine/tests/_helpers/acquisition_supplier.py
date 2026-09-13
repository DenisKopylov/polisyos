"""Native supplier terminal fixture; live HTTP authority has its separate served witness."""

from types import SimpleNamespace

from polisyos.runtime.http.services.acquisition_action_service import AcquisitionActionService
from polisyos.runtime.quality.acquisition_route_loop import persist_world_commit_and_reenter
from tests._helpers.acquisition_chain import make_wdi_port_case
from tests._helpers.acquisition_production import (
    install_fixture_wdi_cost_basis,
    persist_wdi_route,
)
from tests.unit.runtime.http.test_control_service_di import _build_control_service


async def build_supplier_terminal_case(tmp_path, monkeypatch):
    """Run actual live/epoch/N6/sink owners with an explicitly synthetic decision input."""
    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    closure, _ = await persist_wdi_route(control)
    case = make_wdi_port_case(tmp_path / "wdi", monkeypatch, control=control, closure=closure)
    quarantined = case.port.execute(closure)
    assert quarantined.disposition == "quarantined_no_growth"
    assert quarantined.admitted_observation_delta == 0
    retained_negative = {
        ref: control._artifact_store.get_bytes(ref) for ref in quarantined.owner_receipt_refs
    }
    before = tuple(case.transport_calls)
    case.appoint_native_policy()
    decision_ref = control._put_json_artifact(
        {"scope": "fixture-only-supplier-custody", "synthetic": True},
        kind="fixture.acquisition_decision",
        schema_name="FixtureAcquisitionDecision",
    )
    sink = control.acquisition_route_sink
    predecessor = None
    for phase in ("requested", "executing"):
        receipt = AcquisitionActionService._phase_receipt(
            closure=closure,
            job_id="fixture-acquisition",
            decision_ref=decision_ref,
            receipt_phase=phase,
            predecessor_receipt_ref=predecessor,
            owner_receipt_refs=(),
        )
        predecessor = sink.persist_phase(receipt).receipt_ref
    result = case.port.execute(closure)
    assert tuple(case.transport_calls) == before
    assert all(
        control._artifact_store.get_bytes(ref) == blob for ref, blob in retained_negative.items()
    )
    if result.disposition != "world_committed":
        raise AssertionError("native supplier fixture did not commit observations")
    pending = AcquisitionActionService._phase_receipt(
        closure=closure,
        job_id="fixture-acquisition",
        decision_ref=decision_ref,
        receipt_phase="world_committed_reentry_pending",
        predecessor_receipt_ref=predecessor,
        owner_receipt_refs=result.owner_receipt_refs,
    )
    terminal = persist_world_commit_and_reenter(
        sink=sink, pending_receipt=pending, reentry=lambda: case.port.reenter(closure, result)
    )
    return SimpleNamespace(
        control=control,
        closure=closure,
        result=result,
        supplier_receipt_ref=terminal.receipt_ref,
        case=case,
    )
