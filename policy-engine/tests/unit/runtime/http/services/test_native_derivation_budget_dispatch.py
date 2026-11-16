"""Native transport cannot precede the current worker budget preflight.

These are dispatch-boundary controls with explicit owner adapters. They prove
ordering and refusal, not source admission, quote truth or a real action grant.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.runtime.http.services.acquisition_surface_execution import (
    LiveAcquisitionExecutionError,
    WorldBankWDIAcquisitionExecutionPort,
)


class _BeforeTransportError(RuntimeError):
    pass


def _port(tmp_path, *, budget_error=False):
    events = []

    def budget(**_):
        events.append("budget")
        if budget_error:
            raise ValueError("native_reentry_standard_capacity_not_established")

    bridge = SimpleNamespace(
        candidate_source_selection=lambda _: None,
        begin_action=lambda *_: events.append("begin"),
        prepare_native_derivation_reentry_budget=budget,
        has_admission_attempt=lambda _: False,
    )
    port = WorldBankWDIAcquisitionExecutionPort.__new__(WorldBankWDIAcquisitionExecutionPort)
    port._world_growth_bridge = bridge
    port.require_route_ready = lambda _: events.append("readiness")
    port._runtime_artifact_store_root = lambda: tmp_path

    def reserve(_):
        events.append("reserve")
        raise _BeforeTransportError

    port.reserve_route_binding = reserve
    return port, events


def test_native_prepare_leaves_transport_to_the_current_worker(tmp_path):
    port, events = _port(tmp_path)
    port.prepare_route_execution(SimpleNamespace(native_derivation_leaf_scope=object()))
    assert events == ["readiness"]


def test_native_budget_precedes_the_first_transport_reservation(tmp_path):
    port, events = _port(tmp_path)
    with pytest.raises(_BeforeTransportError):
        port.execute(
            SimpleNamespace(native_derivation_leaf_scope=object()), action_phase_ref="phase"
        )
    assert events == ["readiness", "begin", "budget", "reserve"]


def test_native_capacity_refusal_performs_no_transport_reservation(tmp_path):
    port, events = _port(tmp_path, budget_error=True)
    with pytest.raises(ValueError, match="native_reentry_standard_capacity_not_established"):
        port.execute(
            SimpleNamespace(native_derivation_leaf_scope=object()), action_phase_ref="phase"
        )
    assert events == ["readiness", "begin", "budget"]


def test_native_missing_executing_phase_performs_no_transport_reservation(tmp_path):
    port, events = _port(tmp_path)
    with pytest.raises(LiveAcquisitionExecutionError) as caught:
        port.execute(SimpleNamespace(native_derivation_leaf_scope=object()))
    assert caught.value.code == "native_reentry_action_phase_missing"
    assert events == ["readiness"]
