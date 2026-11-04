"""Owner-bound input controls for candidate-experiment terminal replay."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.http.services.control_plane_store import AcquisitionActionHeadRecord
from polisyos.runtime.quality.acquisition_evaluation_history import (
    verify_candidate_experiment_terminal_history,
)
from tests._helpers.runtime_http import _build_control_service


def test_terminal_history_rejects_unselected_terminal_reference(tmp_path: Path) -> None:
    """An artifact ID without its selected manifest profile is not a history input."""
    service = _build_control_service(tmp_path / "control")
    head = AcquisitionActionHeadRecord(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="source-a",
        route_id="sha256:" + "1" * 64,
        action_generation=1,
        head_generation=1,
        receipt_ref="sha256:" + "2" * 64,
        receipt_sha256="sha256:" + "2" * 64,
        durable_event_id="event-a",
        coarse_phase="candidate_input_prepared",
        receipt_phase="candidate_input_reentry_pending",
        recovery_state="reentry_recovery_required",
        job_id="action-a",
        predecessor_receipt_ref="sha256:" + "3" * 64,
        created_at=datetime.now(UTC),
    )
    terminal_ref = ArtifactRef(
        artifact_id="sha256:" + "4" * 64,
        kind="runtime_quality.acquisition_route_loop_receipt",
        media_type="application/json",
    )
    try:
        with pytest.raises(
            ValueError,
            match="candidate_experiment_terminal_history_owner_not_established",
        ):
            verify_candidate_experiment_terminal_history(
                control_service=service,
                head=head,
                terminal_ref=terminal_ref,
            )
    finally:
        service._control_store.close()
