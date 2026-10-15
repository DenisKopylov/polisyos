from __future__ import annotations

import concurrent.futures
import threading
import time
from typing import Any, ClassVar

import numpy as np
import pytest

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, fingerprint, from_canonical_bytes
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
from polisyos.scientist.methods.autotune import execution_work


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
        parameters=(
            ParameterSpec(name="delta", default=1.0),
            ParameterSpec(name="capture_execution_work", default=False),
        ),
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
    assert result.method_result_ref.manifest_profile_sha256 is not None
    assert result.method_evidence_ref.manifest_profile_sha256 is not None
    assert result.final_state is not None
    assert np.allclose(np.asarray(result.final_state["values"]), np.array([4.0, 5.0]))
    evidence = from_canonical_bytes(cas.get_bytes(result.method_evidence_ref.artifact_id))
    assert evidence["authority_purpose"] == "method_execution"
    assert evidence["authoritative_for"] == ["execution_reproducibility"]
    assert evidence["may_not_use_for"] == [
        "governance_admissibility",
        "method_validity",
    ]
    fresh_reader = FileSystemCAS(tmp_path)
    result_manifest = fresh_reader.get_manifest(result.method_result_ref)
    evidence_manifest = fresh_reader.get_manifest(result.method_evidence_ref)
    assert (
        artifact_manifest_profile_sha256(result_manifest)
        == result.method_result_ref.manifest_profile_sha256
    )
    assert (
        artifact_manifest_profile_sha256(evidence_manifest)
        == result.method_evidence_ref.manifest_profile_sha256
    )
    assert evidence_manifest.inputs == [
        input_ref_from_artifact_ref(result.method_result_ref, role="method_result")
    ]


@pytest.mark.parametrize(
    ("use_finite_request_profile", "expected_binding_status"),
    [
        pytest.param(True, "recomputed", id="finite-request-profile"),
        pytest.param(False, "not_established", id="strict-default-mutation"),
    ],
)
def test_run_job_method_flow_records_finite_float_dispatch_and_adapter(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    use_finite_request_profile: bool,
    expected_binding_status: str,
) -> None:
    registry = MethodRegistry.get_instance()
    registry.register(_MethodJobIncrement, override=True)
    if not use_finite_request_profile:
        # Simulate restoring the strict default at the production call site while
        # leaving the helper/profile marker present. Actual dispatch must go unbound.
        monkeypatch.setattr(execution_work, "_fingerprint_method_request_material", fingerprint)

    cas = FileSystemCAS(tmp_path)
    input_ref = cas.put_json(
        [1, 2],
        PutOptions(
            kind="tests.input",
            media_type="application/json",
            schema=SchemaInfo(name="tests.Input", version="0.1.0"),
        ),
    )
    method_params = {"delta": 2.5, "capture_execution_work": True}
    spec = JobSpec(
        job_kind="method",
        method_fqn=_MethodJobIncrement.signature.fqn,
        input_refs={"state": input_ref},
        method_params=method_params,
    )

    result = run_job(spec, cas_root=tmp_path)

    assert not result.issues
    assert result.method_result_ref is not None
    assert result.method_evidence_ref is not None
    assert np.allclose(np.asarray(result.final_state["values"]), np.array([3.5, 4.5]))
    evidence = from_canonical_bytes(cas.get_bytes(result.method_evidence_ref.artifact_id))
    assert evidence["method_dispatch_binding_status"] == expected_binding_status
    if use_finite_request_profile:
        dispatch = evidence["method_dispatch_binding"]
        assert dispatch["method_params_fingerprint"] == fingerprint(
            method_params,
            canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=True),
        )
    else:
        assert "method_dispatch_binding" not in evidence

    adapter_warning = next(
        item for item in result.warnings if item.startswith("legacy_method_adapter_ref:")
    )
    adapter_id = adapter_warning.split(":", 1)[1]
    adapter = from_canonical_bytes(cas.get_bytes(adapter_id))
    assert adapter["method_params"] == method_params


def test_dispatch_capture_is_separate_from_scientific_method_params(tmp_path) -> None:
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
        method_params={"delta": 2},
    )

    uncaptured = run_job(spec, cas_root=tmp_path)
    captured = run_job(spec, cas_root=tmp_path, capture_dispatch_binding=True)

    assert uncaptured.method_evidence_ref is not None
    assert captured.method_evidence_ref is not None
    assert uncaptured.job_key == captured.job_key == JobKey.from_spec(spec)
    ordinary_evidence = from_canonical_bytes(
        cas.get_bytes(uncaptured.method_evidence_ref.artifact_id)
    )
    captured_evidence = from_canonical_bytes(
        cas.get_bytes(captured.method_evidence_ref.artifact_id)
    )
    assert "method_dispatch_binding_status" not in ordinary_evidence
    assert captured_evidence["method_dispatch_binding_status"] == "recomputed"
    binding = captured_evidence["method_dispatch_binding"]
    assert binding["method_params_fingerprint"] == fingerprint(
        {"delta": 2}, canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=True)
    )
    assert "capture_dispatch_binding" not in binding
    assert "capture_execution_work" not in spec.method_params


@pytest.mark.parametrize(
    "non_finite",
    [
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="positive-infinity"),
        pytest.param(float("-inf"), id="negative-infinity"),
    ],
)
def test_run_job_nonfinite_method_params_leave_dispatch_unbound(
    tmp_path,
    non_finite: float,
) -> None:
    registry = MethodRegistry.get_instance()
    registry.register(_MethodJobIncrement, override=True)

    cas = FileSystemCAS(tmp_path)
    # Empty vector keeps the fixture output finite while the supplied request still
    # crosses the actual JobSpec, dispatch observer, and adapter persistence path.
    input_ref = cas.put_json(
        [],
        PutOptions(
            kind="tests.input",
            media_type="application/json",
            schema=SchemaInfo(name="tests.Input", version="0.1.0"),
        ),
    )
    method_params = {"delta": non_finite, "capture_execution_work": True}
    spec = JobSpec(
        job_kind="method",
        method_fqn=_MethodJobIncrement.signature.fqn,
        input_refs={"state": input_ref},
        method_params=method_params,
    )

    result = run_job(spec, cas_root=tmp_path)

    if result.method_evidence_ref is None:
        assert result.issues
        assert any(
            issue["loc"] == ["method_runner"] and issue["error_type"] == "runtime"
            for issue in result.issues
        )
        assert result.method_result_ref is None
        return

    evidence = from_canonical_bytes(cas.get_bytes(result.method_evidence_ref.artifact_id))
    assert evidence["method_dispatch_binding_status"] == "not_established"
    assert "method_dispatch_binding" not in evidence
    assert result.method_result_ref is not None
    adapter_failures = [
        warning
        for warning in result.warnings
        if warning.startswith("legacy_method_adapter_failed:")
    ]
    assert len(adapter_failures) == 1
    assert "NaN/Inf forbidden" in adapter_failures[0]


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
