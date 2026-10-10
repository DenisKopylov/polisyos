"""Characterize control-job dispatch boundaries while lifecycle helpers are composed."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from polisyos.core.security.tenant_context import (
    get_current_access_scope_or_none,
    get_current_cell_id,
    get_current_tenant_id_or_none,
    tenant_scope,
)
from polisyos.runtime.http.services.control import run_lifecycle
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobExecutionScope,
    ControlJobLeaseLostError,
)


def _bare_control_service(store: object) -> run_lifecycle.ControlPlaneService:
    service = run_lifecycle.ControlPlaneService.__new__(run_lifecycle.ControlPlaneService)
    object.__setattr__(service, "_control_store", store)
    return service


def test_worker_dispatch_clears_ambient_identity_and_preserves_admission_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The live lease owns job identity before the admitted handler is entered."""
    events: list[tuple[object, ...]] = []
    scope = ControlJobExecutionScope(
        status="established",
        tenant_id="tenant-job",
        cell_id="cell-job",
        actor_subject="worker-subject",
        actor_authenticated=True,
        actor_roles=("worker",),
    )
    job = SimpleNamespace(job_id="job-admitted", run_id="run-admitted")
    admission = SimpleNamespace(job=job, scope=scope)

    class Store:
        def current_execution_job_admission(self) -> object:
            identity = (
                get_current_tenant_id_or_none(),
                get_current_cell_id(),
                get_current_access_scope_or_none(),
            )
            events.append(("admit", identity))
            return admission

    service = _bare_control_service(Store())

    @contextmanager
    def install_scope(received_scope: object):
        events.append(("scope_enter", received_scope))
        yield
        events.append(("scope_exit", received_scope))

    def process_admitted(*, job: object, admission: object, execution_scope: object) -> None:
        identity = (
            get_current_tenant_id_or_none(),
            get_current_cell_id(),
            get_current_access_scope_or_none(),
        )
        events.append(("process", job, admission, execution_scope, identity))

    monkeypatch.setattr(service, "_install_execution_scope", install_scope)
    monkeypatch.setattr(service, "_process_control_job_admitted", process_admitted)

    with tenant_scope(None, tenant_id="ambient-tenant", cell_id="ambient-cell"):
        service._process_control_job(SimpleNamespace(job_id="dispatch-snapshot"))
        assert get_current_tenant_id_or_none() == "ambient-tenant"
        assert get_current_cell_id() == "ambient-cell"

    assert [event[0] for event in events] == [
        "admit",
        "scope_enter",
        "process",
        "scope_exit",
    ]
    assert events[0][1] == (None, None, None)
    assert events[1] == ("scope_enter", scope)
    assert events[2] == ("process", job, admission, scope, (None, None, None))
    assert events[3] == ("scope_exit", scope)


def test_worker_dispatch_propagates_lease_loss_before_scope_or_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    failure = ControlJobLeaseLostError("lease_lost")

    class Store:
        def current_execution_job_admission(self) -> object:
            events.append("admission")
            raise failure

    service = _bare_control_service(Store())
    monkeypatch.setattr(
        service,
        "_install_execution_scope",
        lambda _scope: pytest.fail("lease loss reached scope installation"),
    )
    monkeypatch.setattr(
        service,
        "_process_control_job_admitted",
        lambda **_kwargs: pytest.fail("lease loss reached admitted processing"),
    )

    with pytest.raises(ControlJobLeaseLostError) as raised:
        service._process_control_job(SimpleNamespace(job_id="dispatch-snapshot"))

    assert raised.value is failure
    assert events == ["admission"]


def test_control_service_and_worker_entrypoints_keep_canonical_fqns() -> None:
    service_type = run_lifecycle.ControlPlaneService

    assert service_type.__module__ == run_lifecycle.__name__
    assert service_type._process_control_job.__module__ == run_lifecycle.__name__
    assert service_type._process_control_job_admitted.__module__ == run_lifecycle.__name__
