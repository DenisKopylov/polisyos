"""The historical measurement is independent of its debt-row status decoration."""

from hashlib import sha256
from pathlib import Path

import pytest

from polisyos.runtime.http.services.cycle_board_sources import load_historical_producer_availability

OWNER = Path("docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md")
MEASUREMENT = (
    "DS3 measured 5 available / 7 `invalid_source` / 1 `artifact_missing` "
    "from a worktree WITHOUT `production_data` — environment-relative fail-closed"
)


def _owner(tmp_path, text):
    path = tmp_path / OWNER
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_historical_measurement_survives_closed_heading_and_recomputes_changed_counts(tmp_path):
    for label in (
        "Producer availability denominator",
        "~~Producer availability denominator~~ **CLOSED, re-owned**",
    ):
        path = _owner(tmp_path, f"| {label} | {MEASUREMENT} | `escaped|owner` | closed |\n")
        result = load_historical_producer_availability(tmp_path)
        assert result.counts == {"available": 5, "invalid_source": 7, "artifact_missing": 1}
        assert result.measurement_scope == "environment_relative"
        assert result.source_content_hash == "sha256:" + sha256(path.read_bytes()).hexdigest()
    _owner(
        tmp_path,
        f"| **CLOSED** | {MEASUREMENT.replace('5 available', '6 available')} | owner | closed |\n",
    )
    assert load_historical_producer_availability(tmp_path).counts["available"] == 6


@pytest.mark.parametrize(
    "text",
    [
        "| old measurement | absent | owner | closed |\n",
        f"| one | {MEASUREMENT} | owner | closed |\n| two | {MEASUREMENT} | owner | closed |\n",
        f"| malformed | {MEASUREMENT.replace('5 available', 'unknown available')} | owner | closed |\n",
        f"| valid | {MEASUREMENT} | owner | closed |\n| malformed | DS3 measured broken | owner | closed |\n",
        f"{MEASUREMENT}\n",
    ],
)
def test_historical_measurement_refuses_absent_ambiguous_or_malformed_owner_rows(tmp_path, text):
    _owner(tmp_path, text)
    with pytest.raises(ValueError):
        load_historical_producer_availability(tmp_path)


def test_historical_read_receipt_tracks_actual_read_hash_and_incomplete_boundaries(tmp_path):
    from polisyos.runtime.http.services.cycle_board_sources import (
        HistoricalProducerAvailabilityError,
    )

    path = _owner(tmp_path, f"| closed | {MEASUREMENT} | owner | closed |\n")
    before = load_historical_producer_availability(tmp_path).read_receipt
    assert before.read_status == "read" and before.status == "COMPLETE"
    assert before.table_row_denominator == 1
    assert before.selected_measurement_cell_count == 1
    path.write_text(path.read_text() + "| unrelated | extra cell | owner | closed |\n")
    after = load_historical_producer_availability(tmp_path).read_receipt
    assert before.source_content_hash != after.source_content_hash
    assert after.table_row_denominator == 2
    assert after.selected_measurement_cell_count == 1
    assert "current_availability_not_measured" in after.unresolved_by_construction
    path.chmod(0)
    try:
        with pytest.raises(HistoricalProducerAvailabilityError) as unreadable:
            load_historical_producer_availability(tmp_path)
        receipt = unreadable.value.read_receipt
        assert receipt.read_status == "failed" and receipt.status == "UNRUN"
        assert receipt.read_error == "PermissionError"
        assert receipt.source_content_hash is None
        assert receipt.selected_measurement_cell_count is None
    finally:
        path.chmod(0o600)
    path.unlink()
    with pytest.raises(HistoricalProducerAvailabilityError) as absent:
        load_historical_producer_availability(tmp_path)
    assert absent.value.read_receipt.read_error == "FileNotFoundError"
    assert absent.value.read_receipt.coverage == "partial"
    assert absent.value.read_receipt.source_ref == OWNER.as_posix()


@pytest.fixture
def historical_runtime_api_env(tmp_path, monkeypatch):
    """Open the actual HTTP runtime over an isolated owner-built Slice0 catalog."""
    from dataclasses import replace

    from polisyos.data_forge.read_api import catalog as catalog_api
    from polisyos.runtime.quality import substrate_registry
    from tests._helpers.runtime_http import build_runtime_api_env, close_runtime_api_env

    catalog_root = tmp_path / "retrieval-catalog"
    catalog_api.build_slice0_fixture_catalog_graph(catalog_root).close()
    original = substrate_registry.default_substrate_catalog_paths
    monkeypatch.setattr(
        substrate_registry,
        "default_substrate_catalog_paths",
        lambda root: replace(original(root), l1_dcat_path=catalog_root / "catalog.duckdb"),
    )
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    try:
        yield env
    finally:
        close_runtime_api_env(env)


def test_historical_source_http_failure_contains_actual_read_receipt(
    historical_runtime_api_env, tmp_path
):
    from polisyos.core.security.identity import PolicyOSRole
    from polisyos.runtime.http.routes.governed_projections import (
        _get_cycle_board_projection_service,
    )
    from polisyos.runtime.http.services.cycle_board_projection import CycleBoardProjectionService
    from tests.unit.runtime.http.test_cycle_board_projection_service import _service
    from tests.unit.runtime.http.test_governed_projection_api import _cycle_board_secure_client

    _, raw, index = _service()
    # Preserve real companion reads so the actual historical loader reaches the missing input.
    from polisyos.runtime.http.services import cycle_board_sources
    from tests.unit.runtime.http.test_cycle_board_projection_service import REPO_ROOT

    for relative in (cycle_board_sources._DS4_SOURCE, cycle_board_sources._N13B_SOURCE):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(REPO_ROOT / relative)
    service = CycleBoardProjectionService(
        projection_service=raw, run_index=index, repository_root=tmp_path
    )
    client, headers = _cycle_board_secure_client(
        historical_runtime_api_env,
        role=PolicyOSRole.ANALYST,
        suffix="historical-measurement-read-receipt",
    )
    client.app.dependency_overrides[_get_cycle_board_projection_service] = lambda: service
    response = client.get(
        "/api/v1/exports/governed-projections/depth-n-cycle-board", headers=headers
    )
    assert response.status_code == 503, response.text
    payload = response.json()
    assert payload["code"] == "cycle_board_historical_source_invalid"
    assert payload["read_receipt"]["source_ref"] == OWNER.as_posix()
    assert payload["read_receipt"]["read_error"] == "FileNotFoundError"
    assert payload["read_receipt"]["source_content_hash"] is None
    assert payload["read_receipt"]["status"] == "UNRUN"
