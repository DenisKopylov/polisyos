from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import pytest

from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.identity import PIIAccessLevel, PolicyOSRole
from polisyos.core.security.tenant_context import (
    get_current_access_scope_or_none,
    get_current_cell_id,
    get_current_tenant_id_or_none,
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)
from polisyos.runtime.http.services.control_plane_store import ControlJobRecord, ControlPlaneStore
from polisyos.runtime.http.services.control_worker import ControlWorker, _worker_tenant_context

if TYPE_CHECKING:
    from collections.abc import Iterator


class _WorkerStore:
    def heartbeat_worker(self, **_kwargs: object) -> None:
        return None

    def renew_job_lease(self, **_kwargs: object) -> bool:
        return True


class _FencedWorkerStore(_WorkerStore):
    @contextmanager
    def job_execution_fence(self, **_kwargs: object) -> Iterator[None]:
        yield


@pytest.fixture
def job() -> ControlJobRecord:
    now = datetime.now(UTC)
    return ControlJobRecord(
        job_id="job-worker-custody",
        kind="workflow_run",
        state="running",
        run_id="run-worker-custody",
        pipeline_id=None,
        requested_execution_profile=None,
        effective_execution_profile="dev",
        policy_flags={},
        capability_manifest_ref=None,
        payload_ref=None,
        submitted_by="test",
        created_at=now,
        started_at=now,
        finished_at=None,
        lease_owner="worker-custody",
        lease_expires_at=None,
        attempt=1,
        error_message=None,
        progress={"details": {"tenant_id": "progress-tenant", "cell_id": "progress-cell"}},
    )


def test_worker_clears_ambient_identity_for_fenced_and_generic_handlers(
    job: ControlJobRecord,
) -> None:
    scope = AccessScope(
        tenant_id="tenant-caller",
        cell_id="cell-caller",
        principal_type="user",
        user_sub="caller",
        roles=frozenset({PolicyOSRole.ANALYST}),
        max_pii_tier=PIIAccessLevel.HIGH,
        mfa_verified=True,
    )
    for store_type in (_FencedWorkerStore, _WorkerStore):
        observed: list[tuple[str | None, str | None, AccessScope | None]] = []

        def handle(
            _job: ControlJobRecord,
            *,
            observations: list[tuple[str | None, str | None, AccessScope | None]] = observed,
        ) -> None:
            observations.append(
                (
                    get_current_tenant_id_or_none(),
                    get_current_cell_id(),
                    get_current_access_scope_or_none(),
                )
            )

        worker = ControlWorker(
            store=cast("ControlPlaneStore", store_type()),
            handler=handle,
            worker_id="worker-custody",
        )
        with tenant_scope(None, tenant_id="tenant-caller", cell_id="cell-caller"):
            token = set_current_access_scope(scope)
            try:
                worker._run_with_lease_heartbeat(job)
                assert get_current_tenant_id_or_none() == "tenant-caller"
                assert get_current_cell_id() == "cell-caller"
                assert get_current_access_scope_or_none() == scope
            finally:
                reset_current_access_scope(token)
        assert observed == [(None, None, None)]


def test_worker_diagnostic_scope_ignores_progress_identity(job: ControlJobRecord) -> None:
    assert _worker_tenant_context(job) == ("tenant-unknown", "cell-unknown")
