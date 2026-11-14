"""Bounded SQL job discovery preserves its exact run/kind denominator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from tests.unit.runtime.http.test_control_plane_store_evaluation_frontier import _create_job

if TYPE_CHECKING:
    from pathlib import Path


def test_job_inventory_is_stable_bounded_and_exactly_scoped(tmp_path: Path) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    for job_id in ("action-c", "action-a", "action-b"):
        _create_job(store, job_id=job_id, kind="acquisition", run_id="run-a")
    _create_job(store, job_id="foreign-run", kind="acquisition", run_id="run-b")
    _create_job(store, job_id="other-kind", kind="natural_language_run", run_id="run-a")

    bounded = store.list_jobs_by_run_and_kind(run_id="run-a", kind="acquisition", limit=2)
    full = store.list_jobs_by_run_and_kind(run_id="run-a", kind="acquisition", limit=3)

    assert tuple(job.job_id for job in bounded) == ("action-a", "action-b")
    assert tuple(job.job_id for job in full) == ("action-a", "action-b", "action-c")
    assert all(job.run_id == "run-a" and job.kind == "acquisition" for job in full)


@pytest.mark.parametrize("limit", [0, 1001, True])
def test_job_inventory_rejects_an_invalid_bound(tmp_path: Path, limit: int) -> None:
    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    with pytest.raises(ValueError, match="control_job_inventory_limit_invalid"):
        store.list_jobs_by_run_and_kind(run_id="run-a", kind="acquisition", limit=limit)
