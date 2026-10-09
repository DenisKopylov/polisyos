from __future__ import annotations

import concurrent.futures
import threading
import time
from typing import Any, ClassVar

import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.methods import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodRegistry,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.scientist.compute.job_spec import JobKey, JobSpec
from polisyos.scientist.compute.runner import run_job


@pytest.fixture(autouse=True)
def _reset_registry():
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


class _MethodJobIncrement:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="method_job_increment",
        namespace="tests.scientist",
        version="1.0.0",
        input_slots=frozenset({SlotSpec("state", SlotType.VECTOR, Unit("dimensionless", "array"))}),
        output_slots=frozenset(
            {SlotSpec("values", SlotType.VECTOR, Unit("dimensionless", "array"))}
        ),
        parameters=(ParameterSpec(name="delta", default=1.0),),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="method job increment")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> dict[str, Any]:
        values = np.asarray(state["state"])
        return {"values": values + float(params["delta"])}


class _ArtifactStoreProxy:
    def __init__(self, store: FileSystemCAS) -> None:
        self._store = store

    def __getattr__(self, name: str):
        return getattr(self._store, name)


def test_job_spec_kind_validation():
    with pytest.raises(ValueError, match="job_kind"):
        JobSpec(job_kind="unknown")


def test_job_key_legacy_ignores_polyglot_fields():
    spec_a = JobSpec(
        job_kind="legacy_program",
        program_ref={
            "artifact_id": "sha256:" + ("a" * 64),
            "kind": "x",
            "media_type": "application/json",
        },
    )
    spec_b = JobSpec(
        job_kind="legacy_program",
        program_ref={
            "artifact_id": "sha256:" + ("a" * 64),
            "kind": "x",
            "media_type": "application/json",
        },
        method_fqn="tests.unit.scientist.method_job_increment@1.0.0",
    )
    assert JobKey.from_spec(spec_a) == JobKey.from_spec(spec_a)
    assert JobKey.from_spec(spec_a) != JobKey.from_spec(spec_b)


def test_run_job_method_flow(tmp_path):
    registry = MethodRegistry.get_instance()
    registry.register(_MethodJobIncrement, override=True)

    cas = FileSystemCAS(tmp_path)
    input_ref = cas.put_json(
        [1, 2],
        PutOptions(
            kind="tests.input",
            media_type="application/json",
            schema=SchemaInfo(name="tests.Input", version="0.1.0"),
        ),
    )

    spec = JobSpec(
        job_kind="method",
        method_fqn=_MethodJobIncrement.signature.fqn,
        input_refs={"state": input_ref},
        method_params={"delta": 3},
    )
    result = run_job(spec, cas_root=tmp_path)

    assert not result.issues
    assert result.simulation_results_ref is not None
    assert result.method_result_ref is not None
    assert result.method_evidence_ref is not None
    assert result.final_state is not None
    assert np.allclose(np.asarray(result.final_state["values"]), np.array([4.0, 5.0]))
    evidence = from_canonical_bytes(cas.get_bytes(result.method_evidence_ref.artifact_id))
    assert evidence["authority_purpose"] == "method_execution"
    assert evidence["authoritative_for"] == ["execution_reproducibility"]
    assert evidence["may_not_use_for"] == [
        "governance_admissibility",
        "method_validity",
    ]


def test_method_job_results_follow_ambient_tenant_ownership(tmp_path) -> None:
    registry = MethodRegistry.get_instance()
    registry.register(_MethodJobIncrement, override=True)

    cas = FileSystemCAS(tmp_path).with_ambient_ownership_enforcement()
    tenant_id = "tenant-r4-method-owner"
    cell_id = "cell-r4-method-owner"
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        input_ref = cas.put_json(
            [1, 2],
            PutOptions(
                kind="tests.input",
                media_type="application/json",
                schema=SchemaInfo(name="tests.Input", version="0.1.0"),
            ),
        )
        result = run_job(
            JobSpec(
                job_kind="method",
                method_fqn=_MethodJobIncrement.signature.fqn,
                input_refs={"state": input_ref},
                method_params={"delta": 3},
            ),
            cas_root=tmp_path,
        )

        assert not result.issues
        assert result.method_result_ref is not None
        assert result.method_evidence_ref is not None
        assert cas.get_bytes(result.method_result_ref)
        assert cas.get_bytes(result.method_evidence_ref)

    with tenant_scope(None, tenant_id="tenant-r4-other", cell_id="cell-r4-other"):
        with pytest.raises(ArtifactOwnershipError, match="not readable by tenant"):
            cas.get_bytes(result.method_result_ref)
        with pytest.raises(ArtifactOwnershipError, match="not readable by tenant"):
            cas.get_bytes(result.method_evidence_ref)


def test_run_job_method_without_fqn_returns_issue(tmp_path):
    spec = JobSpec(job_kind="method")
    result = run_job(spec, cas_root=tmp_path)
    assert result.issues


def test_run_job_method_flow_accepts_injected_store_and_method_providers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    registry = MethodRegistry()
    registry.register(_MethodJobIncrement, override=True)
    dispatcher = MethodDispatcher()
    store_paths: list[object] = []

    def _store_factory(path):
        store_paths.append(path)
        return FileSystemCAS(path)

    def _unexpected(cls, *args, **kwargs):
        del cls, args, kwargs
        raise AssertionError("global singleton lookup should not be used")

    monkeypatch.setattr(MethodRegistry, "get_instance", classmethod(_unexpected))
    monkeypatch.setattr(MethodDispatcher, "get_instance", classmethod(_unexpected))

    cas = FileSystemCAS(tmp_path)
    input_ref = cas.put_json(
        [5, 6],
        PutOptions(
            kind="tests.input",
            media_type="application/json",
            schema=SchemaInfo(name="tests.Input", version="0.1.0"),
        ),
    )
    spec = JobSpec(
        job_kind="method",
        method_fqn=_MethodJobIncrement.signature.fqn,
        input_refs={"state": input_ref},
        method_params={"delta": 2},
    )

    result = run_job(
        spec,
        cas_root=tmp_path,
        store_factory=_store_factory,
        method_registry_provider=lambda: registry,
        method_dispatcher_provider=lambda: dispatcher,
    )

    assert not result.issues
    assert result.method_result_ref is not None
    assert result.method_evidence_ref is not None
    assert np.allclose(np.asarray(result.final_state["values"]), np.array([7.0, 8.0]))
    assert store_paths
    assert all(path == tmp_path for path in store_paths)


def test_run_job_method_flow_accepts_protocol_store_factory(tmp_path) -> None:
    registry = MethodRegistry.get_instance()
    registry.register(_MethodJobIncrement, override=True)

    def _store_factory(path):
        return _ArtifactStoreProxy(FileSystemCAS(path))

    cas = FileSystemCAS(tmp_path)
    input_ref = cas.put_json(
        [10, 11],
        PutOptions(
            kind="tests.input",
            media_type="application/json",
            schema=SchemaInfo(name="tests.Input", version="0.1.0"),
        ),
    )
    spec = JobSpec(
        job_kind="method",
        method_fqn=_MethodJobIncrement.signature.fqn,
        input_refs={"state": input_ref},
        method_params={"delta": 4},
    )

    result = run_job(spec, cas_root=tmp_path, store_factory=_store_factory)

    assert not result.issues
    assert result.method_result_ref is not None
    assert result.method_evidence_ref is not None
    assert np.allclose(np.asarray(result.final_state["values"]), np.array([14.0, 15.0]))


@pytest.mark.parametrize("capacity", [1, 2])
def test_competing_method_jobs_share_the_configured_physical_executor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capacity: int,
) -> None:
    from polisyos.common import async_tools

    monkeypatch.setattr(async_tools, "_RUN_CORO_SYNC_EXECUTOR", None)
    monkeypatch.setattr(async_tools, "_SHARED_EXECUTOR_PROFILE", None, raising=False)
    profile = async_tools.SharedExecutorProfile(
        capacity=capacity,
        revision=f"method-jobs-cap-{capacity}-test-v1",
    )
    async_tools.configure_shared_executor_profile(profile)
    executor = async_tools.get_shared_executor()
    owner_barrier = threading.Barrier(capacity)
    owner_threads: set[int] = set()
    owner_lock = threading.Lock()

    def _identify_owner_worker() -> int:
        thread_id = threading.get_ident()
        with owner_lock:
            owner_threads.add(thread_id)
        owner_barrier.wait(timeout=2)
        return thread_id

    owner_futures = [executor.submit(_identify_owner_worker) for _ in range(capacity)]
    [future.result(timeout=2) for future in owner_futures]

    registry = MethodRegistry.get_instance()
    registry.register(_MethodJobIncrement, override=True)
    delegate = MethodDispatcher()
    lock = threading.Lock()
    first_started = threading.Event()
    both_started = threading.Event()
    release_first = threading.Event()
    calls = 0
    active = 0
    peak = 0
    dispatched_threads: list[int] = []

    class ObservedDispatcher:
        def dispatch(self, **kwargs: Any) -> Any:
            nonlocal calls, active, peak
            with lock:
                calls += 1
                call_number = calls
                active += 1
                peak = max(peak, active)
                dispatched_threads.append(threading.get_ident())
            if call_number == 1:
                first_started.set()
            if call_number == 2:
                both_started.set()
            try:
                if capacity == 1 and call_number == 1:
                    assert release_first.wait(timeout=3)
                elif capacity == 2:
                    assert both_started.wait(timeout=3)
                return delegate.dispatch(**kwargs)
            finally:
                with lock:
                    active -= 1

    dispatcher = ObservedDispatcher()
    specs = [
        JobSpec(
            job_kind="method",
            method_fqn=_MethodJobIncrement.signature.fqn,
            method_params={"delta": delta},
            seed=seed,
        )
        for delta, seed in ((2.0, 71), (3.0, 72))
    ]
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as callers:
            futures = [
                callers.submit(
                    run_job,
                    spec,
                    cas_root=tmp_path,
                    method_state={"state": np.array([1.0, 2.0])},
                    method_registry_provider=lambda: registry,
                    method_dispatcher_provider=lambda: dispatcher,  # type: ignore[arg-type]
                )
                for spec in specs
            ]
            assert first_started.wait(timeout=2)
            if capacity == 1:
                time.sleep(0.05)
                with lock:
                    assert calls == 1
                release_first.set()
            else:
                assert both_started.wait(timeout=2)
            results = [future.result(timeout=3) for future in futures]

        assert all(not result.issues for result in results)
        assert all(result.method_result_ref is not None for result in results)
        assert all(result.method_evidence_ref is not None for result in results)
        assert peak == capacity
        assert dispatched_threads and set(dispatched_threads) <= owner_threads
        cas = FileSystemCAS(tmp_path)
        assert all(cas.get_bytes(result.method_result_ref.artifact_id) for result in results)
    finally:
        release_first.set()
        executor.shutdown(wait=True, cancel_futures=True)
