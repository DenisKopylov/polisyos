"""Installed Runtime guard/C105 storage controls; issuer fixture is synthetic."""

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.errors import RuntimeDependencyUnavailableError
from polisyos.scientist.validation.source_admission_port import _bind_source_admission_authority


def _configured_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    app = create_runtime_api_app(cas_root=tmp_path / "cas", core_runs_root=tmp_path / "runs")
    container = app.state.runtime_container
    store = container.runtime_api_context.store
    owner = container.decision_validity_service
    assert owner._store is store
    assert container.runtime_api_context.debug._decision_validity_service is owner
    tenant = store.for_tenant("tenant-a", "cell-a")

    def contract(kind):
        return tenant.put_json(
            {"fixture": kind},
            ArtifactWriteOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(name=kind, version="1.0"),
            ),
            return_selected_profile=True,
        )

    view, use = contract("test.view"), contract("test.use")
    # This unit exercises storage/guard composition only. It does not prove the
    # real installed deployment/route/job authority that the feature requires.
    authority = _bind_source_admission_authority(
        issuer_key="storage-test-only",
        tenant_id="tenant-a",
        cell_id="cell-a",
        provider_id="test-provider",
        registration_key="test-source",
        effective_view_contract_ref=view,
        use_contract_ref=use,
        permitted_operations=frozenset({"genesis", "read_event", "admit"}),
        validate_issuer=lambda: None,
    )
    return store, owner, authority, view, use


def test_installed_c105_owner_uses_real_tenant_cas_and_runtime_guard(tmp_path, monkeypatch):
    store, owner, authority, view, use = _configured_owner(tmp_path, monkeypatch)
    # A storage fixture callback is not an installed issuer grant.
    with pytest.raises(ValueError, match="source_admission_owner_not_established"):
        owner.register_materialization_source(
            authority,
            event_id="genesis",
            registration_key="test-source",
            effective_view_contract_ref=view,
            use_contract_ref=use,
        )
    assert owner.read_source_current_use(()).status == "unknown"
    store.close()
    with pytest.raises(RuntimeDependencyUnavailableError):
        owner.read_source_current_use(())


def test_changed_runtime_guard_target_is_refused(tmp_path, monkeypatch):
    from polisyos.core.artifacts.store import FileSystemCAS

    store, owner, authority, view, use = _configured_owner(tmp_path, monkeypatch)
    replacement = FileSystemCAS(tmp_path / "replacement")
    store._target = replacement  # adversarial mutation of the actual installed proxy
    with pytest.raises(ValueError, match="registered_sql_guard_binding_changed"):
        owner.register_materialization_source(
            authority,
            event_id="genesis",
            registration_key="test-source",
            effective_view_contract_ref=view,
            use_contract_ref=use,
        )


def test_nonfactory_guard_and_different_same_root_backend_are_refused(tmp_path):
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.http.resilience import (
        GuardedDependencyProxy,
        _bind_registered_source_owner,
        build_runtime_cas_guard,
        guard_runtime_cas,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService

    backend = FileSystemCAS(tmp_path / "cas").with_ambient_ownership_enforcement()
    lookalike = GuardedDependencyProxy(target=backend, guard=build_runtime_cas_guard())
    owner = ControlPlaneService.build_decision_validity_owner(lookalike)
    with pytest.raises(ValueError, match="registered_sql_guard_binding_not_established"):
        _bind_registered_source_owner(owner=owner, guarded_store=lookalike)

    guarded = guard_runtime_cas(backend)
    owner = ControlPlaneService.build_decision_validity_owner(guarded)
    different_handle = FileSystemCAS(tmp_path / "cas").with_ambient_ownership_enforcement()
    guarded._target = different_handle  # same root, different factory target identity
    with pytest.raises(ValueError, match="registered_sql_guard_binding_changed"):
        _bind_registered_source_owner(owner=owner, guarded_store=guarded)


def test_changed_runtime_guard_is_refused(tmp_path, monkeypatch):
    from polisyos.runtime.http.resilience import build_runtime_cas_guard

    store, owner, authority, view, use = _configured_owner(tmp_path, monkeypatch)
    store._guard = build_runtime_cas_guard()  # real guard, wrong factory incarnation
    with pytest.raises(ValueError, match="registered_sql_guard_binding_changed"):
        owner.register_materialization_source(
            authority,
            event_id="genesis",
            registration_key="test-source",
            effective_view_contract_ref=view,
            use_contract_ref=use,
        )


def test_guard_breaker_replacement_is_refused(tmp_path, monkeypatch):
    store, owner, authority, view, use = _configured_owner(tmp_path, monkeypatch)
    store._guard._breaker = object()  # cannot substitute a no-op guard component
    with pytest.raises(ValueError, match="registered_sql_guard_binding_changed"):
        owner.register_materialization_source(
            authority,
            event_id="genesis",
            registration_key="test-source",
            effective_view_contract_ref=view,
            use_contract_ref=use,
        )


def test_mutated_guard_code_cannot_bypass_the_closed_owner_guard(tmp_path, monkeypatch):
    """A saved function identity cannot authorize replacement guard code."""
    from polisyos.runtime.http.resilience import BlockingDependencyGuard

    store, owner, authority, _, _ = _configured_owner(tmp_path, monkeypatch)
    store.close()

    def bypass(self, snapshot, func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(BlockingDependencyGuard._run_snapshot, "__code__", bypass.__code__)
    with pytest.raises(RuntimeDependencyUnavailableError):
        owner.resolve_source_admission_event(authority, event_id="not-committed")


def test_mutated_guard_factory_code_cannot_register_a_lookalike(tmp_path, monkeypatch):
    """The source backend is attached only to the captured factory execution."""
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.http.resilience import (
        BlockingDependencyGuard,
        _bind_registered_source_owner,
        build_runtime_cas_guard,
        guard_runtime_cas,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService

    def bypass_factory():
        return object()

    monkeypatch.setattr(build_runtime_cas_guard, "__code__", bypass_factory.__code__)
    guarded = guard_runtime_cas(FileSystemCAS(tmp_path / "cas"))
    assert type(guarded._guard) is BlockingDependencyGuard
    owner = ControlPlaneService.build_decision_validity_owner(guarded)
    _bind_registered_source_owner(owner=owner, guarded_store=guarded)


def test_source_guard_uses_the_captured_timeout_during_aba(tmp_path, monkeypatch):
    """The actual wait uses its factory timeout even when the live guard changes."""
    import threading

    from polisyos.runtime.http.errors import RuntimeDependencyTimeoutError

    monkeypatch.setenv("POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS", "0.2")
    store, owner, authority, _, _ = _configured_owner(tmp_path, monkeypatch)
    guard = store._guard
    source = owner._source_admission
    entered = threading.Event()
    release = threading.Event()
    original_submit = guard._executor.submit
    original_timeout = guard._timeout_seconds

    def held_owner_read(*_args, **_kwargs):
        entered.set()
        if not release.wait(5):
            raise AssertionError("test did not release owner read")
        return None

    source._methods["event_receipt"] = held_owner_read

    def mutate_after_submit(*args, **kwargs):
        future = original_submit(*args, **kwargs)
        if not entered.wait(5):
            raise AssertionError("owner read did not enter the worker")
        guard._timeout_seconds = 30.0
        return future

    monkeypatch.setattr(guard._executor, "submit", mutate_after_submit)
    try:
        with pytest.raises(RuntimeDependencyTimeoutError):
            owner.resolve_source_admission_event(authority, event_id="held")
    finally:
        guard._timeout_seconds = original_timeout
        release.set()
