"""Production-boundary regressions for the badged acquisition fixture path."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionServiceError,
    AcquisitionRouteMutationRequest,
)
from tests.unit.runtime.http.test_acquisition_control_worker import _worker_harness


@pytest.mark.asyncio
async def test_badged_dependencies_cannot_project_ready(tmp_path: Path) -> None:
    """Injected behavioral collaborators must not project production readiness."""

    control, service, _calls, _requested = await _worker_harness(
        tmp_path,
        decision_missing=False,
    )
    try:
        closure = service._resolve(
            tenant_id="tenant-a",
            cell_id="cell-a",
            run_id="run-ds15",
        )

        projection = service._projection(closure)

        assert projection.authority_badge == "behavioral_fixture_not_production"
        assert projection.authority_capability == "producer_missing"
        assert projection.execution_capability == "producer_missing"
    finally:
        control.close()


@pytest.mark.asyncio
async def test_badged_dependencies_fail_before_reservation_or_job_creation(
    tmp_path: Path,
) -> None:
    """The fixture path must stop before authority use or durable enqueueing."""

    control, service, calls, _requested = await _worker_harness(
        tmp_path,
        decision_missing=False,
    )
    try:
        closure = service._resolve(
            tenant_id="tenant-a",
            cell_id="cell-a",
            run_id="run-ds15",
        )
        projection = service._projection(closure)
        request = AcquisitionRouteMutationRequest(
            route_projection_hash=projection.route_projection_hash,
            planner_report_hash=projection.planner_report_hash,
            replay_pins=projection.replay_pins,
            idempotency_key="production-boundary",
            human_decision_record_ref="sha256:" + "8" * 64,
        )
        job_id = service._job_id(closure, request)
        assert control._control_store.get_job(job_id) is None

        with pytest.raises(
            AcquisitionActionServiceError,
            match="acquisition_execution_bridge_missing",
        ):
            service.execute(
                tenant_id="tenant-a",
                cell_id="cell-a",
                run_id="run-ds15",
                route_id=closure.route_id,
                request=request,
                bound_permission=cast("Any", object()),
                request_id="request-production-boundary",
                principal=None,
            )

        assert calls == []
        assert control._control_store.get_job(job_id) is None
    finally:
        control.close()
