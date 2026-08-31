"""Deterministic maintenance scheduling coverage for the embedded control worker."""

from __future__ import annotations

from typing import cast

from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.http.services.control_worker import ControlWorker


def test_control_worker_runs_maintenance_without_a_request_at_a_bounded_interval() -> None:
    """The autonomous worker runs maintenance immediately, then no more than once per interval."""

    invocations: list[float] = []
    now = [0.0]
    worker = ControlWorker(
        store=cast("ControlPlaneStore", object()),
        handler=lambda _job: None,
        maintenance_callback=lambda: invocations.append(now[0]),
        maintenance_interval_s=10.0,
        monotonic_clock=lambda: now[0],
    )

    assert worker.run_maintenance_once() is True
    now[0] = 9.99
    assert worker.run_maintenance_once() is False
    now[0] = 10.0
    assert worker.run_maintenance_once() is True
    assert invocations == [0.0, 10.0]
