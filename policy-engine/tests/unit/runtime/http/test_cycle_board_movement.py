"""The board consumes native row movement and keeps global N13b non-authority."""

from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.http.services.cycle_board_projection import CycleBoardProjectionService
from polisyos.runtime.quality.acquisition_movement import AcquisitionMovementService
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from tests.unit.runtime.http.test_cycle_board_projection_service import REPO_ROOT, _service


def test_installed_movement_consumer_projects_empty_policy_refusal(tmp_path: Path) -> None:
    """An installed empty deployment must be read, not rendered as absent code."""
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    cas = FileSystemCAS(tmp_path / "cas")
    movement = AcquisitionMovementService(
        control_store=store,
        artifact_store=cas,
        event_log=RuntimeDiagnosticEventLog(store=store, artifact_store=cas),
    )
    _, raw, index = _service()
    board = CycleBoardProjectionService(
        projection_service=raw,
        run_index=index,
        repository_root=REPO_ROOT,
        movement_service=movement,
    )

    packet = board.get()

    capstones = [row for row in packet.payload.rows if row.cohort == "n10_capstone"]
    assert len(capstones) == 3
    assert all(row.movement_status.policy_status == "policy_admission_missing" for row in capstones)
    assert all(row.movement_records == () for row in capstones)
    assert packet.payload.movement_gap.capability_state == "verification_missing"
    sources = [row for row in packet.composition_manifest if row.source_kind == "native_movement"]
    assert len(sources) == len(capstones)
    assert all(row.availability == "not_established" for row in sources)
    global_source = next(
        row for row in packet.composition_manifest if row.source_id == "n13b-global-deeper-terminal"
    )
    assert "per_row_movement" in global_source.may_not_use_for
