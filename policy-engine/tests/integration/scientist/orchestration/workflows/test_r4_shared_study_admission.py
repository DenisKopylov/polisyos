"""Exercise configured process admission on concurrent Runtime MethodJobs.

The parent test runs one native child process per profile because the canonical
shared executor is process-scoped and deliberately refuses a second capacity.
It uses the existing internal control-job enqueue path with a typed Scientist
state payload; the served ``WorkflowRunRequest`` does not expose arbitrary HTE
method inputs. The actual ControlWorker, RunLifecycle, ``run_experiment``,
builder, causal node, ``run_job``, MethodBackend, dispatcher, TMLE folds, and CAS
writes remain production implementations.
"""

from __future__ import annotations

import contextvars
import dataclasses
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from polisyos.common import async_tools
from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    artifact_manifest_profile_sha256,
)
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, content_hash, from_canonical_bytes
from polisyos.core.contracts.control import PolicyFlags
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import StateSnapshotRef
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal import HTEObservationalData
from polisyos.foundry.methods.catalog.causal.treatment_effects import TMLEEstimator
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.trinity import TrinityBundle
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.scientist.compute import runner as compute_runner
from polisyos.scientist.nodes.builtins import state_keys

_REPO_ROOT = Path(__file__).resolve().parents[5]
_R4_RAW_ROOT = _REPO_ROOT / "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw"
_R4_SLOW_PAYLOAD_BUDGET_BYTES = 25 * 1024 * 1024
_TENANT_IDS = (
    "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
)
_CELL_IDS = ("cell-a", "cell-b")
_PRINCIPALS = tuple(
    RuntimePrincipal(
        subject=f"r4-native-workload-fixture-{study_index}",
        authenticated=True,
        tenant_id=tenant_id,
        cell_id=_CELL_IDS[study_index],
        roles=frozenset({"analyst"}),
    )
    for study_index, tenant_id in enumerate(_TENANT_IDS)
)
_METHOD_PARAMS: dict[str, Any] = {
    "propensity_backend": "logistic",
    "outcome_backend": "linear",
    "calibration_mode": "none",
    "outcome_scaling": "raw",
    "crossfit_folds": 3,
    "n_repeats": 2,
    "random_seed": 18,
    "random_seed_manifest": [18, 1015],
    "ci_mode": "wald",
    "coverage_guard": "off",
    "inference_profile": "regular_iid",
    "parallel_folds": False,
    "max_parallel_folds": 1,
}
_R4_PROFILE_CASES = (
    {"case_id": "cap-1-configured", "capacity": 1, "bypass": False},
    {"case_id": "cap-2-configured", "capacity": 2, "bypass": False},
    {"case_id": "cap-1-bridge-removal", "capacity": 1, "bypass": True},
)


def _json_safe_metadata(value: Any) -> Any:
    """Convert write options to JSON without copying canonical payload bytes."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return _json_safe_metadata(value.value)
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "model_dump"):
        return _json_safe_metadata(value.model_dump(mode="json"))
    if dataclasses.is_dataclass(value):
        return {
            field.name: _json_safe_metadata(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _json_safe_metadata(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe_metadata(item) for item in value]
    return str(value)


def _attempt_all_r4_profiles(invoke_case: Any) -> list[dict[str, Any]]:
    """Attempt every fresh-process profile before a caller decides pass/fail."""
    attempts: list[dict[str, Any]] = []
    for profile_case in _R4_PROFILE_CASES:
        try:
            outcome = invoke_case(dict(profile_case))
        except Exception as exc:
            outcome = {
                "status": "parent_runner_exception",
                "exception_type": type(exc).__name__,
            }
        if not isinstance(outcome, Mapping):
            outcome = {
                "status": "invalid_parent_runner_outcome",
                "outcome_type": type(outcome).__name__,
            }
        attempts.append({**profile_case, **outcome})
    return attempts


def _require_all_r4_profiles_passed(attempts: list[dict[str, Any]]) -> None:
    """Fail once after the complete configured/removal case set was attempted."""
    expected_case_ids = [str(case["case_id"]) for case in _R4_PROFILE_CASES]
    observed_case_ids = [str(attempt.get("case_id")) for attempt in attempts]
    failures = [
        attempt
        for attempt in attempts
        if attempt.get("status") != "passed"
        or attempt.get("child_returncode") != 0
        or not isinstance(attempt.get("profile_result"), dict)
    ]
    if observed_case_ids != expected_case_ids or failures:
        summaries = [
            {
                "case_id": attempt.get("case_id"),
                "status": attempt.get("status"),
                "child_returncode": attempt.get("child_returncode"),
                "output_receipts": attempt.get("output_receipts", {}),
            }
            for attempt in attempts
        ]
        raise AssertionError(
            "R4 profile driver attempted all three fresh children before aggregate failure; "
            f"expected={expected_case_ids}, observed={observed_case_ids}, outcomes={summaries}"
        )


def _r4_profile_receipt_root() -> Path:
    """Choose a unique ignored-RAW destination for complete child receipts."""
    configured_root = os.environ.get("POLISYOS_R4_RECEIPT_ROOT")
    if configured_root is None:
        configured_root = os.environ.get("POLISYOS_R4_RECEIPT_DIR")
    root = (
        Path(configured_root).expanduser()
        if configured_root
        else _R4_RAW_ROOT / f"r4-shared-admission-{uuid.uuid4().hex}"
    )
    if not root.resolve().is_relative_to(_R4_RAW_ROOT.resolve()):
        raise ValueError("R4 profile receipts must be written under ignored LOCAL/raw")
    return root


class _ObservedWorkQueue:
    """Measure queue residence for every shared-executor work item."""

    def __init__(
        self,
        delegate: Any,
        *,
        executor: Any,
        submission_context: threading.local,
        observations: list[dict[str, Any]],
        guard_observations: list[dict[str, Any]],
        other_observations: list[dict[str, Any]],
        lock: Any,
    ) -> None:
        self._delegate = delegate
        self._executor = executor
        self._submission_context = submission_context
        self._observations = observations
        self._guard_observations = guard_observations
        self._other_observations = other_observations
        self._lock = lock
        self._queued_at_ns: dict[int, tuple[int, dict[str, Any]]] = {}

    def put(self, item: Any, block: bool = True, timeout: float | None = None) -> None:
        context = getattr(self._submission_context, "current", None)
        identity = id(item)
        if item is None:
            if timeout is None:
                self._delegate.put(item, block=block)
            else:
                self._delegate.put(item, block=block, timeout=timeout)
            return

        observed_context = dict(context or {})
        observed_context.setdefault("observer_kind", "unclassified_executor_submission")
        observed_context.setdefault("submission_context_missing", context is None)

        # Hold the existing admission lock across the real unbounded put, so
        # the active-worker snapshot cannot go stale before queue insertion.
        with self._executor._admission_lock:
            physical_workers = int(self._executor._physical_workers)
            queue_depth = int(self._delegate.qsize())
            queued_at_ns = time.perf_counter_ns()
            observed_context = {
                **observed_context,
                "physical_workers_active_at_put": physical_workers,
                "queue_depth_before_put": queue_depth,
                "outstanding_jobs_at_put": int(self._executor._outstanding_jobs),
                "queue_submitted_at_ns": queued_at_ns,
                "queue_submit_thread_id": threading.get_ident(),
            }
            with self._lock:
                self._queued_at_ns[identity] = (queued_at_ns, observed_context)
            try:
                if timeout is None:
                    self._delegate.put(item, block=block)
                else:
                    self._delegate.put(item, block=block, timeout=timeout)
            except BaseException:
                with self._lock:
                    self._queued_at_ns.pop(identity, None)
                raise

    def get(self, block: bool = True, timeout: float | None = None) -> Any:
        if timeout is None:
            item = self._delegate.get(block=block)
        else:
            item = self._delegate.get(block=block, timeout=timeout)
        self._record_dequeue(item)
        return item

    def get_nowait(self) -> Any:
        item = self._delegate.get_nowait()
        self._record_dequeue(item)
        return item

    def _record_dequeue(self, item: Any) -> None:
        dequeued_at_ns = time.perf_counter_ns()
        with self._lock:
            queued = self._queued_at_ns.pop(id(item), None)
            if queued is None:
                return
            queued_at_ns, context = queued
            observer_kind = context.get("observer_kind")
            if observer_kind == "method_dispatch":
                target = self._observations
            elif observer_kind in {
                "runtime_cas_guard",
                "runtime_control_store_guard",
                "runtime_blocking_guard",
            }:
                target = self._guard_observations
            else:
                target = self._other_observations
            target.append(
                {
                    **context,
                    "queue_dequeued_at_ns": dequeued_at_ns,
                    "queue_worker_thread_id": threading.get_ident(),
                    "queue_wait_ns": dequeued_at_ns - queued_at_ns,
                }
            )

    def pending_observations(self) -> list[dict[str, Any]]:
        """Return all submissions that have not reached a worker yet."""
        observed_at_ns = time.perf_counter_ns()
        with self._lock:
            return [
                {
                    **context,
                    "queue_submitted_at_ns": queued_at_ns,
                    "queue_pending_observed_at_ns": observed_at_ns,
                    "queue_pending_wait_ns": observed_at_ns - queued_at_ns,
                }
                for queued_at_ns, context in self._queued_at_ns.values()
            ]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)


def _process_peak_rss_observation() -> dict[str, Any]:
    """Read the isolated pytest child's kernel-reported process high-water mark."""
    import platform

    try:
        import resource
    except ImportError:
        return {"available": False, "reason": "resource_module_unavailable"}

    units = {"Linux": "KiB", "Darwin": "bytes"}.get(platform.system())
    if units is None:
        return {"available": False, "reason": "ru_maxrss_units_not_qualified"}
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "available": True,
        "value": int(peak),
        "units": units,
        "normalized_bytes": int(peak) * 1024 if units == "KiB" else int(peak),
        "source": "resource.getrusage(RUSAGE_SELF).ru_maxrss",
        "window": "RUSAGE_SELF high-water from fresh pytest child process start through profile result preparation; includes interpreter/plugins, fixture setup, both local Runtime environments and CAS; excludes parent and sibling children",
    }


def _owner_scope_observation(
    store: FileSystemCAS,
    artifact_id: Any,
    *,
    tenant_id: str,
    cell_id: str,
) -> dict[str, Any]:
    """Summarize owner claims without copying tenant or cell identifiers."""
    owner_rows = store._ownership_index.owners_for(artifact_id)
    admitted_owner = any(
        row.get("tenant_id") == tenant_id and row.get("cell_id") == cell_id for row in owner_rows
    )
    return {
        "claim_count": len(owner_rows),
        "matches_admitted_scope": admitted_owner,
        "scope_class": (
            "admitted_scope" if admitted_owner else "other_scope" if owner_rows else "unowned"
        ),
    }


def _run_child(
    capacity: int,
    *,
    temp_root: Path,
    bypass: bool = False,
) -> dict[str, Any]:
    """Run the two-study native witness in one isolated Runtime process."""
    import importlib

    from polisyos.runtime.http.resilience import (
        BlockingDependencyGuard,
        GuardedDependencyProxy,
    )
    from polisyos.runtime.quality.workspace.foundry_consumption import (
        _method_evidence_semantics,
    )
    from tests._helpers.runtime_http import build_runtime_api_env, close_runtime_api_env

    revision = f"r4-native-method-cap-{capacity}-v1"
    expected_profile = async_tools.SharedExecutorProfile(
        capacity=capacity,
        revision=revision,
    )
    # Runtime composition may use the shared executor while constructing its
    # guarded promotion services. Configure and instrument that exact process
    # owner first, before any Runtime/TestClient producer can start a worker.
    async_tools.configure_shared_executor_profile(expected_profile)
    physical_executor = async_tools.get_shared_executor()
    assert physical_executor._max_workers == capacity
    queue_wait_rows: list[dict[str, Any]] = []
    guard_queue_wait_rows: list[dict[str, Any]] = []
    other_queue_wait_rows: list[dict[str, Any]] = []
    cas_guard_rows: list[dict[str, Any]] = []
    slow_cas_payloads: list[dict[str, Any]] = []
    cas_payload_inputs_by_operation: dict[str, list[dict[str, Any]]] = {}
    cas_guard_call_sequence = 0
    cas_diagnostic_printed = False
    cas_guard_lock = threading.Lock()
    cas_payload_lock = threading.Lock()
    active_guard_operations = 0
    cas_instrumentation_errors: list[str] = []
    guard_operations_idle = threading.Event()
    guard_operations_idle.set()
    queue_observation_lock = threading.Lock()
    queue_observation_context = threading.local()
    active_guard_operation: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
        "r4_active_guard_operation", default=None
    )
    launch_context_by_study: dict[int, dict[str, str]] = {}
    original_put_blob_and_manifest_once = FileSystemCAS._put_blob_and_manifest_once

    def observed_put_blob_and_manifest_once(
        store: FileSystemCAS,
        *,
        data: bytes,
        opts: PutOptions,
        aid: Any,
        sha: str,
        return_selected_profile: bool,
    ) -> Any:
        active_operation = active_guard_operation.get()
        captured: dict[str, Any] | None = None
        if active_operation is not None and active_operation.get("is_put_json"):
            try:
                options = _json_safe_metadata(opts)
                json.dumps(options, sort_keys=True, allow_nan=False)
                schema = _json_safe_metadata(opts.schema)
                json.dumps(schema, sort_keys=True, allow_nan=False)
            except Exception as exc:  # instrumentation must not change CAS behavior
                options = None
                schema = None
                options_error = type(exc).__name__
            else:
                options_error = None
            try:
                captured = {
                    "operation_id": active_operation["operation_id"],
                    "dependency_name": active_operation["dependency_name"],
                    "study_index": active_operation["study_index"],
                    "run_id": active_operation["run_id"],
                    "job_id": active_operation["job_id"],
                    "artifact_id": str(aid),
                    "content_sha256": sha,
                    "canonical_payload_bytes": len(data),
                    "artifact_kind": opts.kind,
                    "media_type": opts.media_type,
                    "schema": schema,
                    "return_selected_profile": return_selected_profile,
                    "options": options,
                    "options_capture_error": options_error,
                    "canonical_bytes": data,
                }
            except Exception as exc:  # instrumentation must not change CAS behavior
                with cas_payload_lock:
                    cas_instrumentation_errors.append(
                        f"payload input capture: {type(exc).__name__}"
                    )
        try:
            result = original_put_blob_and_manifest_once(
                store,
                data=data,
                opts=opts,
                aid=aid,
                sha=sha,
                return_selected_profile=return_selected_profile,
            )
        except BaseException as exc:
            if captured is not None:
                captured["publication_outcome"] = type(exc).__name__
                with cas_payload_lock:
                    cas_payload_inputs_by_operation.setdefault(captured["operation_id"], []).append(
                        captured
                    )
            raise
        if captured is not None:
            captured["publication_outcome"] = "ok"
            try:
                captured["selected_manifest_profile_sha256"] = result[2]
            except Exception as exc:  # instrumentation must not change CAS behavior
                captured["selected_profile_capture_error"] = type(exc).__name__
            with cas_payload_lock:
                cas_payload_inputs_by_operation.setdefault(captured["operation_id"], []).append(
                    captured
                )
        return result

    FileSystemCAS._put_blob_and_manifest_once = observed_put_blob_and_manifest_once
    assert not physical_executor._threads, (
        "actual queue residence must be instrumented before Runtime producers start"
    )
    observed_work_queue = _ObservedWorkQueue(
        physical_executor._work_queue,
        executor=physical_executor,
        submission_context=queue_observation_context,
        observations=queue_wait_rows,
        guard_observations=guard_queue_wait_rows,
        other_observations=other_queue_wait_rows,
        lock=queue_observation_lock,
    )
    physical_executor._work_queue = observed_work_queue
    envs = [
        build_runtime_api_env(
            temp_root / f"runtime-{study_index}",
            include_test_client=True,
            app_kwargs={
                "process_worker_capacity": capacity,
                "process_worker_profile_revision": revision,
            },
        )
        for study_index in range(2)
    ]
    try:
        apps = [env["app"] for env in envs]
        clients = [env["client"] for env in envs]
        assert all(client is not None for client in clients)
        with ExitStack() as runtime_context:
            for client in clients:
                runtime_context.enter_context(client)
            services = [app.state._control_service for app in apps]
            containers = [app.state.runtime_container for app in apps]
            guard_owner_by_id: dict[int, dict[str, Any]] = {}
            assert all(
                container.config.shared_executor_profile() == expected_profile
                for container in containers
            )
            assert async_tools.get_shared_executor_profile() == expected_profile
            for runtime_index, (service, container) in enumerate(
                zip(services, containers, strict=True)
            ):
                guarded_stores = (
                    ("content_addressed_storage", container.runtime_api_context.store),
                    ("control_plane_store", service._control_store),
                )
                for dependency_name, guarded_store in guarded_stores:
                    assert isinstance(guarded_store, GuardedDependencyProxy)
                    guard = guarded_store._guard
                    assert isinstance(guard, BlockingDependencyGuard)
                    assert guard._dependency_name == dependency_name
                    assert guard._executor is physical_executor
                    guard_owner_by_id[id(guard)] = {
                        "runtime_index": runtime_index,
                        "dependency_name": dependency_name,
                        "guard_object_id": id(guard),
                        "executor_object_id": id(guard._executor),
                        "proxy_object_id": id(guarded_store),
                    }
                assert service._artifact_store is container.runtime_api_context.store
            workers = [service._worker for service in services]
            assert all(worker is not None for worker in workers)
            assert all(
                worker._store is service._control_store
                for worker, service in zip(workers, services, strict=True)
            ), "ControlWorker does not consume the guarded control-store proxy"
            for worker in workers:
                worker.stop()

            assert async_tools.get_shared_executor() is physical_executor
            assert physical_executor._work_queue is observed_work_queue
            worker_ids: set[int] = set()
            worker_ids_lock = threading.Lock()
            ready = threading.Barrier(capacity)

            def identify_shared_worker() -> int:
                thread_id = threading.get_ident()
                with worker_ids_lock:
                    worker_ids.add(thread_id)
                ready.wait(timeout=10)
                return thread_id

            previous_queue_context = getattr(queue_observation_context, "current", None)
            queue_observation_context.current = {
                "observer_kind": "executor_calibration",
                "purpose": "identify_actual_shared_executor_workers",
            }
            try:
                calibration = [
                    physical_executor.submit(identify_shared_worker) for _ in range(capacity)
                ]
            finally:
                queue_observation_context.current = previous_queue_context
            [future.result(timeout=10) for future in calibration]
            assert len(worker_ids) == capacity

            runtime_inputs: dict[int, dict[str, Any]] = {}
            for study_index, service in enumerate(services):
                with tenant_scope(
                    None,
                    tenant_id=_TENANT_IDS[study_index],
                    cell_id=_CELL_IDS[study_index],
                ):
                    registry_bundle = build_default_registry_bundle(service._artifact_store)
                    state_snapshot = put_state_snapshot(
                        service._artifact_store,
                        state=GlobalState.empty(n_agents=5, n_firms=2),
                        step=0,
                    )
                    snapshot_ref = service._artifact_store.put_json(
                        DataSnapshot(
                            data_ref=StateSnapshotRef(artifact_id=state_snapshot.artifact_id)
                        ),
                        PutOptions(
                            kind="fabric.data_snapshot",
                            media_type="application/json",
                            schema=SchemaInfo(
                                name="polisyos.core.DataSnapshot",
                                version="0.1.0",
                            ),
                        ),
                    )
                    data_snapshot_ref = DataSnapshotRef(artifact_id=snapshot_ref.artifact_id)
                    trinity_bundle = TrinityBundle(
                        problem_frame=ProblemFrame(
                            problem_id="r4_native_workload",
                            domain=ProblemDomain.FISCAL,
                        ),
                        policy_spec=PolicySpec(
                            policy_id="r4_native_workload",
                            interventions=[
                                InterventionSpec(
                                    intervention_id="r4_tax_change",
                                    kind="income_tax",
                                    target={
                                        "kind": "predicate",
                                        "field": "id",
                                        "operator": SelectorOperator.EQUALS,
                                        "value": "all",
                                    },
                                    schedule={"start_step": 0, "duration_steps": 1},
                                    params={"rate": Decimal("0.1")},
                                )
                            ],
                        ),
                        model_spec=ModelSpec(
                            model_id="r4_native_workload",
                            data_snapshot_ref=str(data_snapshot_ref.artifact_id),
                            registry_bundle_ref=str(registry_bundle.bundle_ref.artifact_id),
                        ),
                    )
                    trinity_ref = service._artifact_store.put_json(
                        trinity_bundle,
                        PutOptions(
                            kind="ir.trinity_bundle",
                            media_type="application/json",
                            schema=SchemaInfo(
                                name="polisyos.ir.TrinityBundle",
                                version=trinity_bundle.schema_version,
                            ),
                        ),
                    )
                    rng = np.random.default_rng(811 + study_index)
                    n_obs = 240
                    covariates = rng.normal(size=(n_obs, 2))
                    treatment = rng.binomial(1, 0.5, size=n_obs).astype(float)
                    outcome = (
                        0.45 * treatment
                        + 0.25 * covariates[:, 0]
                        - 0.15 * covariates[:, 1]
                        + rng.normal(0.0, 0.7, size=n_obs)
                    )
                    observations = HTEObservationalData(
                        outcome=outcome,
                        treatment=treatment,
                        covariates=covariates,
                        feature_names=["x0", "x1"],
                        sample_ids=np.arange(n_obs),
                    )
                    data_ref = service._artifact_store.put_json(
                        observations.model_dump(mode="json"),
                        ArtifactWriteOptions(
                            kind="ir.observational_data",
                            media_type="application/json",
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                    )
                    runtime_inputs[study_index] = {
                        "registry_bundle": registry_bundle,
                        "snapshot_ref": snapshot_ref,
                        "trinity_ref": trinity_ref,
                        "data_ref": data_ref,
                    }

            from polisyos.foundry.methods.catalog.causal import tmle_core
            from polisyos.scientist import api as scientist_api

            causal_node = importlib.import_module(
                "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation"
            )
            # The Runtime endpoint in this slice accepts generic workflow data
            # bindings, while evaluation admission is an independently owned
            # gate. Bypass only that gate so this integration test isolates
            # aggregate MethodJob admission; the result stays legacy-shadow and
            # candidate-only. No safety or promotion claim is tested here.
            causal_gate = causal_node._causal_evaluation_safety_blockers
            causal_node._causal_evaluation_safety_blockers = lambda *_a, **_k: ()

            original_run_experiment = scientist_api.run_experiment
            from polisyos.scientist.orchestration.engine.state import ExperimentState

            active_study: contextvars.ContextVar[int | None] = contextvars.ContextVar(
                "r4_active_native_study",
                default=None,
            )
            active_method_fqn: contextvars.ContextVar[str | None] = contextvars.ContextVar(
                "r4_active_native_method_fqn",
                default=None,
            )
            final_states: dict[int, dict[str, Any]] = {}
            causal_node_outcomes: dict[int, Any] = {}
            method_results: dict[int, dict[str, Any]] = {}
            producer_lock = threading.Lock()
            producer_entries = 0
            producer_active = 0
            producer_peak = 0
            method_backend_entries = 0
            original_method_backend_run = compute_runner.MethodBackend.run

            def target_method(kwargs: Mapping[str, Any]) -> bool:
                method_class = kwargs.get("method_class")
                signature = getattr(method_class, "signature", None)
                fqn = str(getattr(signature, "fqn", "")).split("@", 1)[0]
                return fqn == TMLEEstimator.signature.fqn.split("@", 1)[0]

            original_causal_execute = causal_node.RunCausalEvaluationNode.execute

            def observed_causal_execute(node: Any, ctx: Any, state: Any) -> Any:
                outcome = original_causal_execute(node, ctx, state)
                study_index = int(state.params["r4_study_index"])
                causal_node_outcomes[study_index] = outcome
                return outcome

            causal_node.RunCausalEvaluationNode.execute = observed_causal_execute

            def observed_method_backend_run(
                backend: compute_runner.MethodBackend,
                **kwargs: Any,
            ) -> Any:
                nonlocal method_backend_entries
                normalized_method_fqn = str(kwargs.get("method_fqn") or "").split("@", 1)[0]
                is_tmle = normalized_method_fqn == TMLEEstimator.signature.fqn.split("@", 1)[0]
                if is_tmle:
                    with producer_lock:
                        method_backend_entries += 1
                method_token = active_method_fqn.set(normalized_method_fqn)
                try:
                    result = original_method_backend_run(backend, **kwargs)
                finally:
                    active_method_fqn.reset(method_token)
                if is_tmle:
                    study_index = active_study.get()
                    assert study_index is not None
                    artifacts = result.exec_artifacts
                    method_results[study_index] = {
                        "result_ref": artifacts.result_ref,
                        "evidence_ref": artifacts.evidence_ref,
                        "result": result.final_state,
                    }
                return result

            compute_runner.MethodBackend.run = observed_method_backend_run

            def observed_run_experiment(
                state: Mapping[str, Any] | ExperimentState,
                **kwargs: Any,
            ) -> dict[str, Any]:
                nonlocal producer_entries, producer_active, producer_peak
                payload = (
                    state.model_dump(mode="json")
                    if isinstance(state, ExperimentState)
                    else dict(state)
                )
                typed_state = ExperimentState.model_validate(payload)
                study_index = int(typed_state.params["r4_study_index"])
                with producer_lock:
                    producer_entries += 1
                    producer_active += 1
                    producer_peak = max(producer_peak, producer_active)
                token = active_study.set(study_index)
                try:
                    result = original_run_experiment(state, **kwargs)
                finally:
                    active_study.reset(token)
                    with producer_lock:
                        producer_active -= 1
                final_states[study_index] = result
                return result

            scientist_api.run_experiment = observed_run_experiment

            dispatcher = MethodDispatcher.get_instance()
            original_dispatch = dispatcher.dispatch
            submission_lock = threading.Lock()
            submit_count = 0
            both_submitted = threading.Event()
            both_dispatches_waiting = threading.Event()
            release_dispatches = threading.Event()
            active_lock = threading.Lock()
            dispatch_active = 0
            dispatch_peak = 0
            physical_active_thread_depths: Counter[int] = Counter()
            physical_active_workers_peak = 0
            dispatch_rows: list[dict[str, int | bool]] = []
            fold_rows: list[tuple[int, int, int]] = []
            submit_active = 0
            submit_peak = 0

            def observed_dispatch(**kwargs: Any) -> Any:
                nonlocal dispatch_active, dispatch_peak, physical_active_workers_peak
                if not target_method(kwargs):
                    return original_dispatch(**kwargs)
                study_index = active_study.get()
                assert study_index is not None, "TMLE dispatch lost its submitted context"
                thread_id = threading.get_ident()
                on_shared_worker = async_tools.is_current_shared_executor_worker()
                if not bypass:
                    assert on_shared_worker, "admitted TMLE dispatch did not run on a shared worker"
                else:
                    assert not on_shared_worker, (
                        "bridge-removal body unexpectedly used a shared worker"
                    )
                with active_lock:
                    dispatch_active += 1
                    dispatch_peak = max(dispatch_peak, dispatch_active)
                    if on_shared_worker:
                        physical_active_thread_depths[thread_id] += 1
                        physical_active_workers_peak = max(
                            physical_active_workers_peak,
                            len(physical_active_thread_depths),
                        )
                    dispatch_rows.append(
                        {
                            "study": study_index,
                            "thread_id": thread_id,
                            "shared_executor_worker": on_shared_worker,
                        }
                    )
                    if dispatch_active == 2:
                        both_dispatches_waiting.set()
                try:
                    if capacity == 1 and not bypass:
                        # Do not make the only worker wait for a second call.
                        # The call-level counter below records whether another
                        # producer reached the shared executor while this one ran.
                        pass
                    else:
                        assert release_dispatches.wait(timeout=60), (
                            "dispatch release was not signaled after observing both producers"
                        )
                    return original_dispatch(**kwargs)
                finally:
                    with active_lock:
                        dispatch_active -= 1
                        if on_shared_worker:
                            physical_active_thread_depths[thread_id] -= 1
                            if physical_active_thread_depths[thread_id] == 0:
                                del physical_active_thread_depths[thread_id]

            dispatcher.dispatch = observed_dispatch

            # MethodBackend calls through the shared owner module imported by
            # the production runner. Instrument that actual binding rather
            # than assuming the helper is re-exported from compute.runner.
            submit_owner = compute_runner.common_async_tools
            assert submit_owner is async_tools
            original_submit = submit_owner.run_shared_executor_sync

            def observed_submit(func: Any, /, *args: Any, **kwargs: Any) -> Any:
                nonlocal submit_count, submit_active, submit_peak
                # The bridge receives a callable, not the MethodDispatcher kwargs.
                # Read identity from the active MethodBackend invocation context.
                is_tmle = active_method_fqn.get() == TMLEEstimator.signature.fqn.split("@", 1)[0]
                if is_tmle:
                    assert active_study.get() is not None
                    with submission_lock:
                        submit_count += 1
                        submit_active += 1
                        submit_peak = max(submit_peak, submit_active)
                        if submit_count == 2:
                            both_submitted.set()
                    if bypass:
                        # Mirror the real SharedExecutor.submit context capture
                        # while removing only its shared worker/admission boundary.
                        bypass_context = contextvars.copy_context()
                        try:
                            return bypass_context.run(func, *args, **kwargs)
                        finally:
                            with submission_lock:
                                submit_active -= 1
                previous_queue_context = getattr(queue_observation_context, "current", None)
                queue_observation_context.current = (
                    {
                        "observer_kind": "method_dispatch",
                        "study_index": int(active_study.get()),
                        "method_fqn": TMLEEstimator.signature.fqn.split("@", 1)[0],
                    }
                    if is_tmle
                    else None
                )
                try:
                    return original_submit(func, *args, **kwargs)
                finally:
                    queue_observation_context.current = previous_queue_context
                    if is_tmle:
                        with submission_lock:
                            submit_active -= 1

            submit_owner.run_shared_executor_sync = observed_submit
            original_fold = tmle_core._fit_crossfit_fold

            def observed_fold(**kwargs: Any) -> dict[str, Any]:
                study_index = active_study.get()
                assert study_index is not None, "TMLE fold lost its submitted context"
                fold_rows.append(
                    (
                        study_index,
                        int(kwargs["rep_seed"]),
                        int(kwargs["fold_id"]),
                    )
                )
                return original_fold(**kwargs)

            tmle_core._fit_crossfit_fold = observed_fold

            original_guard_run = BlockingDependencyGuard.run
            guard_operation_contexts: dict[int, threading.local] = {}

            def executor_state() -> dict[str, int]:
                with physical_executor._admission_lock:
                    return {
                        "capacity": int(physical_executor._max_workers),
                        "physical_workers_active": int(physical_executor._physical_workers),
                        "outstanding_jobs": int(physical_executor._outstanding_jobs),
                        "queue_depth": int(observed_work_queue.qsize()),
                    }

            def update_guard_row(row: dict[str, Any], **values: Any) -> None:
                with cas_guard_lock:
                    row.update(values)

            def consider_slow_cas_payloads(
                operation_id: str,
                row: dict[str, Any],
                *,
                elapsed_ns: int,
                outcome: str,
                result: Any,
            ) -> None:
                with cas_payload_lock:
                    captured = cas_payload_inputs_by_operation.pop(operation_id, [])
                if not captured:
                    return
                result_ref = str(getattr(result, "artifact_id", "")) or None
                for payload in captured:
                    payload["guard_operation_elapsed_ns"] = elapsed_ns
                    payload["guard_operation_outcome"] = outcome
                    payload["result_artifact_id"] = result_ref
                    payload["result_manifest_profile_sha256"] = getattr(
                        result,
                        "manifest_profile_sha256",
                        None,
                    )
                    payload["operation_name"] = row["operation_name"]
                    payload["call_outcome"] = row.get("call_outcome")
                    with cas_payload_lock:
                        slow_cas_payloads.append(payload)
                        slow_cas_payloads.sort(
                            key=lambda candidate: (
                                int(candidate["guard_operation_elapsed_ns"]),
                                str(candidate["operation_id"]),
                            ),
                            reverse=True,
                        )
                        del slow_cas_payloads[2:]

            slow_payload_receipts: list[dict[str, Any]] = []

            def persist_slowest_cas_payloads() -> list[dict[str, Any]]:
                if slow_payload_receipts:
                    return [dict(receipt) for receipt in slow_payload_receipts]
                receipt_directory_raw = os.environ.get("POLISYOS_R4_RECEIPT_DIR")
                if not receipt_directory_raw:
                    return [
                        {
                            "payload_retention_status": "receipt_directory_not_configured",
                            "operation_id": payload["operation_id"],
                            "artifact_id": payload["artifact_id"],
                            "content_sha256": payload["content_sha256"],
                            "canonical_payload_bytes": payload["canonical_payload_bytes"],
                            "guard_operation_elapsed_ns": payload["guard_operation_elapsed_ns"],
                        }
                        for payload in slow_cas_payloads
                    ]
                receipt_directory = Path(receipt_directory_raw).resolve()
                raw_root = _R4_RAW_ROOT.resolve()
                if not receipt_directory.is_relative_to(raw_root):
                    return [
                        {
                            "payload_retention_status": "receipt_directory_outside_ignored_raw",
                            "operation_id": payload["operation_id"],
                            "artifact_id": payload["artifact_id"],
                            "content_sha256": payload["content_sha256"],
                            "canonical_payload_bytes": payload["canonical_payload_bytes"],
                            "guard_operation_elapsed_ns": payload["guard_operation_elapsed_ns"],
                        }
                        for payload in slow_cas_payloads
                    ]

                receipt_directory.mkdir(parents=True, exist_ok=True)
                retained_bytes = 0
                with cas_payload_lock:
                    candidates = [dict(payload) for payload in slow_cas_payloads]
                for rank, payload in enumerate(candidates, start=1):
                    payload_bytes = payload.pop("canonical_bytes")
                    byte_count = len(payload_bytes)
                    receipt: dict[str, Any] = {
                        "operation_id": payload["operation_id"],
                        "artifact_id": payload["artifact_id"],
                        "content_sha256": payload["content_sha256"],
                        "canonical_payload_bytes": byte_count,
                        "guard_operation_elapsed_ns": payload["guard_operation_elapsed_ns"],
                    }
                    if retained_bytes + byte_count > _R4_SLOW_PAYLOAD_BUDGET_BYTES:
                        receipt["payload_retention_status"] = "per_child_raw_budget_exceeded"
                        slow_payload_receipts.append(receipt)
                        continue
                    payload_stem = (
                        f"slow-put-json-{rank:02d}-{payload['operation_id']}-"
                        f"{payload['content_sha256'][:12]}"
                    )
                    payload_path = receipt_directory / f"{payload_stem}.canonical.json"
                    metadata_path = receipt_directory / f"{payload_stem}.metadata.json"
                    try:
                        payload_path.write_bytes(payload_bytes)
                        metadata_path.write_text(
                            json.dumps(payload, sort_keys=True, allow_nan=False, indent=2) + "\n",
                            encoding="utf-8",
                        )
                    except Exception as exc:  # retain runtime behavior if disk is unavailable
                        receipt["payload_retention_status"] = (
                            f"receipt_write_failed:{type(exc).__name__}"
                        )
                    else:
                        retained_bytes += byte_count
                        receipt.update(
                            {
                                "payload_retention_status": "retained",
                                "payload_path": str(payload_path),
                                "metadata_path": str(metadata_path),
                            }
                        )
                    slow_payload_receipts.append(receipt)
                return [dict(receipt) for receipt in slow_payload_receipts]

            def cas_diagnostic_snapshot() -> dict[str, Any]:
                with cas_guard_lock:
                    guard_calls = [dict(row) for row in cas_guard_rows]
                with queue_observation_lock:
                    guard_queue_submissions = [dict(row) for row in guard_queue_wait_rows]
                    other_queue_submissions = [dict(row) for row in other_queue_wait_rows]
                    method_queue_submissions = [dict(row) for row in queue_wait_rows]
                with cas_guard_lock:
                    pending_guard_operations = active_guard_operations
                return {
                    "capacity": capacity,
                    "bypass": bypass,
                    "shared_executor_object_id": id(physical_executor),
                    "guard_bindings": sorted(
                        [dict(binding) for binding in guard_owner_by_id.values()],
                        key=lambda binding: (
                            int(binding["runtime_index"]),
                            str(binding["dependency_name"]),
                        ),
                    ),
                    "active_guard_operations_at_snapshot": pending_guard_operations,
                    "guard_count_by_dependency": dict(
                        Counter(str(row["dependency_name"]) for row in guard_calls)
                    ),
                    "guard_calls": guard_calls,
                    "executor_queue_submissions": sorted(
                        [
                            *guard_queue_submissions,
                            *other_queue_submissions,
                            *method_queue_submissions,
                        ],
                        key=lambda row: int(row["queue_submitted_at_ns"]),
                    ),
                    "guard_executor_queue_submissions": guard_queue_submissions,
                    "other_executor_queue_submissions": other_queue_submissions,
                    "method_executor_queue_submissions": method_queue_submissions,
                    "pending_executor_queue_submissions": (
                        observed_work_queue.pending_observations()
                    ),
                    "slow_canonical_put_json_payloads": persist_slowest_cas_payloads(),
                    "instrumentation_errors": list(cas_instrumentation_errors),
                }

            def emit_cas_diagnostic() -> None:
                nonlocal cas_diagnostic_printed
                if cas_diagnostic_printed:
                    return
                drain_started_ns = time.perf_counter_ns()
                drain_completed = guard_operations_idle.wait(timeout=5.0)
                drain_elapsed_ns = time.perf_counter_ns() - drain_started_ns
                if not drain_completed:
                    with cas_guard_lock:
                        outstanding = active_guard_operations
                    print(
                        "R4_GUARD_OPERATION_DRAIN="
                        + json.dumps(
                            {
                                "completed": False,
                                "timeout_seconds": 5.0,
                                "elapsed_ns": drain_elapsed_ns,
                                "active_operations": outstanding,
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
                print(
                    "R4_CAS_GUARD_DIAGNOSTIC="
                    + json.dumps(
                        cas_diagnostic_snapshot(),
                        sort_keys=True,
                        allow_nan=False,
                    ),
                    flush=True,
                )
                cas_diagnostic_printed = True

            def observed_guard_run(
                guard: BlockingDependencyGuard,
                func: Any,
                *args: Any,
                **kwargs: Any,
            ) -> Any:
                nonlocal cas_guard_call_sequence
                owner_binding = guard_owner_by_id.get(id(guard))
                if owner_binding is None:
                    return original_guard_run(guard, func, *args, **kwargs)

                with cas_guard_lock:
                    cas_guard_call_sequence += 1
                    operation_id = f"guard-{cas_guard_call_sequence:04d}"
                    execution_context = guard_operation_contexts.setdefault(
                        id(guard), threading.local()
                    )
                    parent_operation_id = getattr(execution_context, "current_operation_id", None)

                active_study_index = active_study.get()
                runtime_index = int(owner_binding["runtime_index"])
                study_index = (
                    active_study_index if active_study_index is not None else runtime_index
                )
                launch_context = launch_context_by_study.get(study_index, {})
                nested_attempt = getattr(guard._execution, "attempt", None) is not None
                operation_name = str(getattr(func, "__qualname__", type(func).__name__))
                dependency_name = str(owner_binding["dependency_name"])
                observer_kind = (
                    "runtime_cas_guard"
                    if dependency_name == "content_addressed_storage"
                    else "runtime_control_store_guard"
                )
                observed_at_ns = time.perf_counter_ns()
                state_at_call = executor_state()
                row: dict[str, Any] = {
                    "operation_id": operation_id,
                    "parent_guard_operation_id": parent_operation_id,
                    "guard_owner_index": runtime_index,
                    "guard_object_id": id(guard),
                    "executor_object_id": id(guard._executor),
                    "dependency_name": guard._dependency_name,
                    "guard_proxy_object_id": owner_binding["proxy_object_id"],
                    "operation_name": operation_name,
                    "study_index": study_index,
                    "active_study_context": active_study_index,
                    "identity_binding_basis": (
                        "active_study_context"
                        if active_study_index is not None
                        else "runtime_guard_owner_mapping"
                    ),
                    "run_id": launch_context.get("run_id"),
                    "job_id": launch_context.get("job_id"),
                    "active_method_fqn": active_method_fqn.get(),
                    "nested_guard_attempt": nested_attempt,
                    "call_thread_id": threading.get_ident(),
                    "call_is_shared_executor_worker": (
                        async_tools.is_current_shared_executor_worker()
                    ),
                    "call_observed_at_ns": observed_at_ns,
                    "executor_state_at_call": state_at_call,
                }
                with cas_guard_lock:
                    cas_guard_rows.append(row)

                def observed_operation(*call_args: Any, **call_kwargs: Any) -> Any:
                    nonlocal active_guard_operations
                    previous_operation_id = getattr(execution_context, "current_operation_id", None)
                    execution_context.current_operation_id = operation_id
                    state_at_operation_start = executor_state()
                    operation_started_at_ns = time.perf_counter_ns()
                    with cas_guard_lock:
                        active_guard_operations += 1
                        guard_operations_idle.clear()
                    update_guard_row(
                        row,
                        operation_started_at_ns=operation_started_at_ns,
                        operation_thread_id=threading.get_ident(),
                        operation_is_shared_executor_worker=(
                            async_tools.is_current_shared_executor_worker()
                        ),
                        executor_state_at_operation_start=state_at_operation_start,
                    )
                    active_context_token = active_guard_operation.set(
                        {
                            "operation_id": operation_id,
                            "parent_guard_operation_id": parent_operation_id,
                            "guard_object_id": id(guard),
                            "executor_object_id": id(guard._executor),
                            "dependency_name": dependency_name,
                            "study_index": study_index,
                            "run_id": launch_context.get("run_id"),
                            "job_id": launch_context.get("job_id"),
                            "is_put_json": operation_name.endswith(".put_json")
                            or operation_name == "put_json",
                        }
                    )
                    operation_result: Any = None
                    operation_outcome = "unknown"
                    try:
                        operation_result = func(*call_args, **call_kwargs)
                    except BaseException as exc:
                        operation_outcome = type(exc).__name__
                        update_guard_row(row, operation_outcome=operation_outcome)
                        raise
                    else:
                        operation_outcome = "ok"
                        update_guard_row(row, operation_outcome="ok")
                        return operation_result
                    finally:
                        finished_at_ns = time.perf_counter_ns()
                        elapsed_ns = finished_at_ns - operation_started_at_ns
                        update_guard_row(
                            row,
                            operation_finished_at_ns=finished_at_ns,
                            operation_elapsed_ns=elapsed_ns,
                            executor_state_at_operation_end=executor_state(),
                        )
                        active_guard_operation.reset(active_context_token)
                        execution_context.current_operation_id = previous_operation_id
                        try:
                            consider_slow_cas_payloads(
                                operation_id,
                                row,
                                elapsed_ns=elapsed_ns,
                                outcome=operation_outcome,
                                result=operation_result,
                            )
                        except Exception as exc:  # instrumentation must not change CAS behavior
                            with cas_payload_lock:
                                cas_instrumentation_errors.append(
                                    f"slow payload selection: {type(exc).__name__}"
                                )
                        finally:
                            with cas_guard_lock:
                                active_guard_operations -= 1
                                if active_guard_operations == 0:
                                    guard_operations_idle.set()

                previous_queue_context = getattr(queue_observation_context, "current", None)
                if nested_attempt:
                    queue_observation_context.current = previous_queue_context
                else:
                    queue_observation_context.current = {
                        "observer_kind": observer_kind,
                        "operation_id": operation_id,
                        "parent_guard_operation_id": parent_operation_id,
                        "guard_owner_index": runtime_index,
                        "dependency_name": dependency_name,
                        "study_index": study_index,
                        "run_id": launch_context.get("run_id"),
                        "job_id": launch_context.get("job_id"),
                        "operation_name": operation_name,
                    }
                call_started_at_ns = time.perf_counter_ns()
                update_guard_row(row, call_started_at_ns=call_started_at_ns)
                try:
                    result = original_guard_run(
                        guard,
                        observed_operation,
                        *args,
                        **kwargs,
                    )
                except BaseException as exc:
                    update_guard_row(row, call_outcome=type(exc).__name__)
                    raise
                else:
                    update_guard_row(row, call_outcome="ok")
                    return result
                finally:
                    finished_at_ns = time.perf_counter_ns()
                    update_guard_row(
                        row,
                        call_finished_at_ns=finished_at_ns,
                        call_elapsed_ns=finished_at_ns - call_started_at_ns,
                        executor_state_at_call_end=executor_state(),
                    )
                    queue_observation_context.current = previous_queue_context

            BlockingDependencyGuard.run = observed_guard_run

            try:
                launches: dict[int, Any] = {}
                study_profiles: dict[int, dict[str, Any]] = {}
                from polisyos.core.run.context import new_run_id

                for study_index in range(2):
                    with tenant_scope(
                        None,
                        tenant_id=_TENANT_IDS[study_index],
                        cell_id=_CELL_IDS[study_index],
                    ):
                        service = services[study_index]
                        inputs = runtime_inputs[study_index]
                        seed = 18 + study_index
                        method_params = dict(_METHOD_PARAMS)
                        method_params["random_seed"] = seed
                        method_params["random_seed_manifest"] = [seed, seed + 997]
                        study_profiles[study_index] = method_params
                        run_id = new_run_id()
                        job_id = uuid.uuid4().hex
                        launch_context_by_study[study_index] = {
                            "run_id": run_id,
                            "job_id": job_id,
                        }
                        policy = service._resolve_execution_policy(
                            requested_profile="dev",
                            policy_flags=PolicyFlags(),
                            principal=_PRINCIPALS[study_index],
                        )
                        state_payload = {
                            "run_id": run_id,
                            "inputs": {
                                "data_snapshot_ref": inputs["snapshot_ref"].model_dump(mode="json"),
                                "registry_bundle_ref": inputs[
                                    "registry_bundle"
                                ].bundle_ref.model_dump(mode="json"),
                                "trinity_bundle_ref": inputs["trinity_ref"].model_dump(mode="json"),
                            },
                            "params": {
                                "control_plane_transition": "legacy_shadow",
                                "workflow_id": "scientist_default",
                                "r4_study_index": study_index,
                                "random_seed": seed,
                                "causal_method_params": method_params,
                            },
                            "observational_data_ref": inputs["data_ref"].model_dump(mode="json"),
                            "causal_method_fqn": TMLEEstimator.signature.fqn,
                            "causal_method_params": method_params,
                        }
                        launches[study_index] = service._enqueue_job(
                            job_id=job_id,
                            job_kind="workflow_run",
                            run_id=run_id,
                            pipeline_id=None,
                            payload={
                                "run_id": run_id,
                                "state_payload": state_payload,
                                "checkpoint_policy": "strict",
                            },
                            policy=policy,
                        )
                futures_by_study: dict[int, Any] = {}
                barrier_timeout_seconds = 60.0

                def capture_barrier_receipt() -> dict[str, Any]:
                    job_rows: list[dict[str, Any]] = []
                    for study_index, launch in sorted(launches.items()):
                        future = futures_by_study.get(study_index)
                        future_done = future is not None and future.done()
                        dispatch_result: Any = None
                        future_error_type: str | None = None
                        if future_done and future is not None:
                            try:
                                dispatch_result = future.result()
                            except Exception as exc:
                                future_error_type = type(exc).__name__
                        launch_context = launch_context_by_study[study_index]
                        with tenant_scope(
                            None,
                            tenant_id=_TENANT_IDS[study_index],
                            cell_id=_CELL_IDS[study_index],
                        ):
                            terminal_job = services[study_index]._control_store.get_job(
                                launch.job_id
                            )
                        progress = None if terminal_job is None else terminal_job.progress
                        job_rows.append(
                            {
                                "study_index": study_index,
                                "run_id": launch_context["run_id"],
                                "job_id": launch.job_id,
                                "future_done": future_done,
                                "dispatch_result": dispatch_result,
                                "future_error_type": future_error_type,
                                "job_state": None if terminal_job is None else terminal_job.state,
                                "job_error": (
                                    None if terminal_job is None else terminal_job.error_message
                                ),
                                "terminal_phase": (
                                    progress.get("phase") if isinstance(progress, Mapping) else None
                                ),
                            }
                        )
                    with producer_lock:
                        producer_count = producer_entries
                        method_count = method_backend_entries
                    with submission_lock:
                        submissions = submit_count
                        active_submissions = submit_active
                        peak_submissions = submit_peak
                    with active_lock:
                        observed_dispatches = [dict(row) for row in dispatch_rows]
                        active_dispatches = dispatch_active
                        peak_dispatches = dispatch_peak
                    return {
                        "capacity": capacity,
                        "bypass": bypass,
                        "jobs": job_rows,
                        "run_experiment_entries": producer_count,
                        "method_backend_entries": method_count,
                        "submit_count": submissions,
                        "submit_active": active_submissions,
                        "submit_peak": peak_submissions,
                        "dispatch_entries": len(observed_dispatches),
                        "dispatch_active": active_dispatches,
                        "dispatch_peak": peak_dispatches,
                        "dispatches": observed_dispatches,
                    }

                def fail_r4_barrier(boundary_name: str, reason: str) -> None:
                    receipt = capture_barrier_receipt()
                    emit_cas_diagnostic()
                    raise AssertionError(
                        f"R4 barrier {boundary_name!r} did not reach its held state: "
                        f"{reason}; boundary_receipt={receipt}"
                    )

                def wait_for_r4_barrier(
                    event: threading.Event,
                    *,
                    boundary_name: str,
                ) -> None:
                    deadline = time.monotonic() + barrier_timeout_seconds
                    while True:
                        if event.is_set():
                            completed_indices = [
                                study_index
                                for study_index, future in futures_by_study.items()
                                if future.done()
                            ]
                            if completed_indices:
                                fail_r4_barrier(
                                    boundary_name,
                                    "a control future completed before the paired witness was released; "
                                    f"completed_studies={completed_indices}",
                                )
                            return
                        completed_indices = [
                            study_index
                            for study_index, future in futures_by_study.items()
                            if future.done()
                        ]
                        if completed_indices:
                            fail_r4_barrier(
                                boundary_name,
                                "a control future completed before this barrier; "
                                f"completed_studies={completed_indices}",
                            )
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            fail_r4_barrier(
                                boundary_name,
                                f"bounded wait expired after {barrier_timeout_seconds:.1f}s",
                            )
                        event.wait(timeout=min(0.05, remaining))

                with ThreadPoolExecutor(max_workers=2) as control_threads:
                    pre_dispatch_release: dict[str, Any] | None = None
                    try:
                        futures_by_study = {
                            study_index: control_threads.submit(workers[study_index].dispatch_once)
                            for study_index in range(2)
                        }
                        if capacity > 1 or bypass:
                            wait_for_r4_barrier(
                                both_submitted,
                                boundary_name="both MethodBackend submissions",
                            )
                            with producer_lock:
                                observed_producers = producer_entries
                                observed_methods = method_backend_entries
                            with submission_lock:
                                observed_submissions = submit_count
                            assert (
                                observed_producers == observed_methods == observed_submissions == 2
                            )
                            wait_for_r4_barrier(
                                both_dispatches_waiting,
                                boundary_name="both real MethodDispatcher calls",
                            )
                            with active_lock:
                                observed_dispatches = len(dispatch_rows)
                                observed_dispatch_active = dispatch_active
                            pre_dispatch_release = {
                                "run_experiment_entries": observed_producers,
                                "method_backend_entries": observed_methods,
                                "submit_count": observed_submissions,
                                "dispatch_entries": observed_dispatches,
                                "dispatch_active": observed_dispatch_active,
                                "control_futures_done": [
                                    futures_by_study[study_index].done() for study_index in range(2)
                                ],
                            }
                            assert observed_dispatches == observed_dispatch_active == 2
                            assert pre_dispatch_release["control_futures_done"] == [
                                False,
                                False,
                            ]
                            release_dispatches.set()
                        dispatched = [
                            futures_by_study[study_index].result(timeout=120)
                            for study_index in range(2)
                        ]
                    finally:
                        # One cleanup boundary releases a sibling after either
                        # wait, any post-wait assertion, or partial submission.
                        release_dispatches.set()
                assert dispatched == [True, True]

                terminal_jobs = []
                for study_index, launch in launches.items():
                    with tenant_scope(
                        None,
                        tenant_id=_TENANT_IDS[study_index],
                        cell_id=_CELL_IDS[study_index],
                    ):
                        terminal_jobs.append(
                            services[study_index]._control_store.get_job(launch.job_id)
                        )
                jobs_completed = all(
                    job is not None and job.state == "completed" for job in terminal_jobs
                )
                if not jobs_completed:
                    emit_cas_diagnostic()
                assert jobs_completed, (
                    "control jobs failed before complete result readback; "
                    f"jobs={[None if job is None else (job.job_id, job.state, job.error_message) for job in terminal_jobs]}, "
                    f"producer_entries={producer_entries}, "
                    f"method_backend_entries={method_backend_entries}, "
                    f"submissions={submit_count}, causal_nodes="
                    f"{[(study, outcome.status, getattr(outcome.error, 'message', None)) for study, outcome in causal_node_outcomes.items()]}"
                )

                study_outputs: dict[str, Any] = {}
                input_receipts: dict[str, dict[str, Any]] = {}
                input_run_bindings: dict[str, dict[str, Any]] = {}
                for study_index, state in final_states.items():
                    with tenant_scope(
                        None,
                        tenant_id=_TENANT_IDS[study_index],
                        cell_id=_CELL_IDS[study_index],
                    ):
                        fresh_store = FileSystemCAS(
                            Path(envs[study_index]["cas_root"])
                        ).with_ambient_ownership_enforcement()
                        node_outcome = causal_node_outcomes[study_index]
                        artifacts_index = state["artifacts_index"]
                        ref_payload = artifacts_index.get(
                            state_keys.ARTIFACT_CAUSAL_METHOD_RESULT_REF
                        )
                        state_linked = ref_payload is not None
                        if ref_payload is None:
                            assert study_index in method_results, (
                                f"causal result missing from final state and MethodBackend "
                                f"receipt; artifacts={sorted(artifacts_index)}, "
                                f"params={sorted(state.get('params', {}))}"
                            )
                            ref_payload = method_results[study_index]["result_ref"]
                        ref = ArtifactRef.model_validate(ref_payload)
                        saved = from_canonical_bytes(fresh_store.get_bytes(ref))
                        assert isinstance(saved, dict)
                        result_manifest = fresh_store.get_manifest(ref)
                        input_data_ref = runtime_inputs[study_index]["data_ref"]
                        assert any(
                            str(source.artifact_id) == str(input_data_ref.artifact_id)
                            and source.role == "input:causal_observational_data"
                            for source in result_manifest.inputs
                        )
                        input_manifest = fresh_store.get_manifest(input_data_ref)
                        input_bytes = fresh_store.get_bytes(input_data_ref)
                        input_content_sha256 = content_hash(input_bytes, prefix=True)
                        input_manifest_profile_sha256 = artifact_manifest_profile_sha256(
                            input_manifest
                        )
                        evidence_ref = method_results[study_index]["evidence_ref"]
                        evidence_raw = fresh_store.get_bytes(evidence_ref)
                        evidence = from_canonical_bytes(evidence_raw)
                        assert isinstance(evidence, dict)
                        assert (
                            evidence.get("method_fqn", "").split("@", 1)[0]
                            == (TMLEEstimator.signature.fqn.split("@", 1)[0])
                        )
                        evidence_manifest = fresh_store.get_manifest(evidence_ref)
                        assert any(
                            str(source.artifact_id) == str(ref.artifact_id)
                            and source.role == "method_result"
                            for source in evidence_manifest.inputs
                        )
                        evidence_manifest_profile_sha256 = artifact_manifest_profile_sha256(
                            evidence_manifest
                        )
                        assert (
                            evidence_ref.manifest_profile_sha256 == evidence_manifest_profile_sha256
                        )
                        # Reuse the consumer's validated semantic projection. The raw CAS
                        # evidence remains attempt-specific and retains measured cost below.
                        semantic_evidence = _method_evidence_semantics(evidence_raw)
                        cost_attribution = evidence["artifacts"]["cost_attribution"]
                        assert isinstance(cost_attribution, dict)

                        input_owner_scope = _owner_scope_observation(
                            fresh_store,
                            input_data_ref.artifact_id,
                            tenant_id=_TENANT_IDS[study_index],
                            cell_id=_CELL_IDS[study_index],
                        )
                        launch_context = launch_context_by_study[study_index]
                        input_receipts[str(study_index)] = {
                            "study_index": study_index,
                            "tenant_id": _TENANT_IDS[study_index],
                            "cell_id": _CELL_IDS[study_index],
                            "input_ref": input_data_ref.model_dump(mode="json", exclude_none=False),
                            "manifest": input_manifest.model_dump(mode="json", exclude_none=False),
                            "manifest_profile_sha256": input_manifest_profile_sha256,
                            "content_sha256": input_content_sha256,
                            "owner_scope": input_owner_scope,
                        }
                        input_run_bindings[str(study_index)] = {
                            "study_index": study_index,
                            "run_id": str(launch_context["run_id"]),
                            "job_id": str(launch_context["job_id"]),
                            "input_ref": input_data_ref.model_dump(mode="json", exclude_none=False),
                            "tenant_id": _TENANT_IDS[study_index],
                            "cell_id": _CELL_IDS[study_index],
                        }
                        result_owner_scope = _owner_scope_observation(
                            fresh_store,
                            ref.artifact_id,
                            tenant_id=_TENANT_IDS[study_index],
                            cell_id=_CELL_IDS[study_index],
                        )
                        evidence_owner_scope = _owner_scope_observation(
                            fresh_store,
                            evidence_ref.artifact_id,
                            tenant_id=_TENANT_IDS[study_index],
                            cell_id=_CELL_IDS[study_index],
                        )
                        result = saved["result"]
                        declared_profile = study_profiles[study_index]
                        repeat_seeds = declared_profile["random_seed_manifest"]
                        fold_count = declared_profile["crossfit_folds"]
                        repeat_count = declared_profile["n_repeats"]
                        expected_study_folds = {
                            (int(repeat_seeds[repeat]), fold)
                            for repeat in range(repeat_count)
                            for fold in range(fold_count)
                        }
                        observed_study_folds = [
                            (fold_seed, fold)
                            for study, fold_seed, fold in fold_rows
                            if study == study_index
                        ]
                        assert set(observed_study_folds) == expected_study_folds
                        assert len(observed_study_folds) == len(expected_study_folds)
                        numerical = {
                            "result": result,
                            "report": saved["report"],
                            "envelope": saved["envelope"],
                            "executed_folds": [
                                {"seed": fold_seed, "fold": fold}
                                for fold_seed, fold in sorted(observed_study_folds)
                            ],
                        }
                        evidence_state_payload = artifacts_index.get(
                            state_keys.ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF
                        )
                        study_outputs[str(study_index)] = {
                            "result_ref": str(ref.artifact_id),
                            "evidence_ref": str(evidence_ref.artifact_id),
                            "evidence_manifest_profile_sha256": evidence_manifest_profile_sha256,
                            "semantic_evidence_sha256": hashlib.sha256(
                                semantic_evidence
                            ).hexdigest(),
                            "attempt_cost_attribution": dict(cost_attribution),
                            "input_owner_scope": input_owner_scope,
                            "result_owner_scope": result_owner_scope,
                            "evidence_owner_scope": evidence_owner_scope,
                            "state_linked": state_linked,
                            "evidence_state_linked": (
                                evidence_state_payload is not None
                                and ArtifactRef.model_validate(evidence_state_payload)
                                == evidence_ref
                            ),
                            "causal_node_status": node_outcome.status,
                            "causal_node_error": (
                                node_outcome.error.message
                                if node_outcome.error is not None
                                else None
                            ),
                            "numerical": numerical,
                        }

                expected_folds = {
                    (
                        study_index,
                        int(study_profiles[study_index]["random_seed_manifest"][repeat]),
                        fold,
                    )
                    for study_index in range(2)
                    for repeat in range(study_profiles[study_index]["n_repeats"])
                    for fold in range(study_profiles[study_index]["crossfit_folds"])
                }
                observed_counts = Counter(fold_rows)
                assert set(observed_counts) == expected_folds
                assert set(observed_counts.values()) == {1}
                assert len(dispatch_rows) == 2
                owner_dispatch_count = sum(row["thread_id"] in worker_ids for row in dispatch_rows)
                if bypass:
                    assert dispatch_peak == 2
                    assert owner_dispatch_count == 0
                else:
                    assert dispatch_peak == capacity
                    assert owner_dispatch_count == 2

                queue_wait_observations = sorted(
                    queue_wait_rows,
                    key=lambda row: int(row["study_index"]),
                )
                if bypass:
                    assert queue_wait_observations == []
                    assert physical_active_workers_peak == 0
                else:
                    assert len(queue_wait_observations) == 2
                    assert {row["study_index"] for row in queue_wait_observations} == {
                        0,
                        1,
                    }
                    assert all(row["queue_wait_ns"] >= 0 for row in queue_wait_observations)
                    assert all(
                        row["method_fqn"] == TMLEEstimator.signature.fqn.split("@", 1)[0]
                        for row in queue_wait_observations
                    )
                    if capacity == 1:
                        actual_cap_waits = [
                            row
                            for row in queue_wait_observations
                            if row["queue_wait_ns"] > 0
                            and (
                                row["physical_workers_active_at_put"] >= capacity
                                or row["queue_depth_before_put"] > 0
                            )
                        ]
                        assert actual_cap_waits, (
                            "cap one recorded no positive queue residence while the shared "
                            "executor had an active worker or an earlier queued item; "
                            f"observations={queue_wait_observations}"
                        )
                    assert physical_active_workers_peak == capacity

                results = {
                    "capacity": capacity,
                    "profile_revision": revision,
                    "source": "candidate_configured_runtime_profile",
                    "dispatch_peak": dispatch_peak,
                    "physical_active_workers_peak": physical_active_workers_peak,
                    "physical_active_workers_basis": (
                        "maximum distinct SharedExecutor worker threads simultaneously inside the real TMLE MethodDispatcher body; excludes ControlWorker threads and idle executor capacity"
                    ),
                    "executor_queue_wait_observations": queue_wait_observations,
                    "executor_queue_wait_basis": (
                        "perf_counter_ns from immediately before actual work-queue delegate.put() to immediately after get()/get_nowait(); rows also retain the admission-lock-stable active-worker count and pre-insertion queue depth; state qualifies but never replaces measured residence"
                    ),
                    "cas_guard_diagnostic": {
                        **cas_diagnostic_snapshot(),
                        "basis": (
                            "test-only observation of the actual Runtime CAS BlockingDependencyGuard, its configured SharedExecutor submission, queue residence, callable service interval, calling/worker thread IDs, and observed run/job context; callable arguments, payloads, and exception messages are intentionally omitted"
                        ),
                    },
                    "dispatches_on_shared_workers": owner_dispatch_count,
                    "dispatch_count": len(dispatch_rows),
                    "run_experiment_entries": producer_entries,
                    "run_experiment_peak_active": producer_peak,
                    "method_backend_entries": method_backend_entries,
                    "submit_count": submit_count,
                    "submit_peak_active": submit_peak,
                    "expected_fold_count": len(expected_folds),
                    "observed_fold_count": len(fold_rows),
                    "completed_jobs": len(terminal_jobs),
                    "control_worker_results": dispatched,
                    "pre_dispatch_release": pre_dispatch_release,
                    "study_outputs": study_outputs,
                    "input_receipts": input_receipts,
                    "input_run_bindings": input_run_bindings,
                    "bypass": bypass,
                }
            finally:
                emit_cas_diagnostic()
                BlockingDependencyGuard.run = original_guard_run
                submit_owner.run_shared_executor_sync = original_submit
                compute_runner.MethodBackend.run = original_method_backend_run
                dispatcher.dispatch = original_dispatch
                tmle_core._fit_crossfit_fold = original_fold
                scientist_api.run_experiment = original_run_experiment
                causal_node.RunCausalEvaluationNode.execute = original_causal_execute
                causal_node._causal_evaluation_safety_blockers = causal_gate

        return results
    finally:
        FileSystemCAS._put_blob_and_manifest_once = original_put_blob_and_manifest_once
        for env in reversed(envs):
            close_runtime_api_env(env)


def test_r4_native_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run one profile child and emit its complete machine-readable receipt."""
    if os.environ.get("POLISYOS_R4_CHILD") != "1":
        pytest.skip("invoked only by the R4 profile parent")
    capacity = int(os.environ["POLISYOS_R4_CAPACITY"])
    bypass = os.environ.get("POLISYOS_R4_BYPASS") == "1"
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", "local")
    profile_started_ns = time.perf_counter_ns()
    result = _run_child(capacity, temp_root=tmp_path, bypass=bypass)
    result["profile_elapsed_ns"] = time.perf_counter_ns() - profile_started_ns
    result["profile_elapsed_basis"] = (
        "monotonic_ns from _run_child entry through its return after CAS readback and Runtime environment teardown; excludes interpreter/pytest startup"
    )
    result["process_peak_rss"] = _process_peak_rss_observation()
    assert result["process_peak_rss"]["available"], result["process_peak_rss"]
    print(
        "R4_NATIVE_RESULT=" + json.dumps(result, sort_keys=True, allow_nan=False),
        flush=True,
    )


def _decode_child_stream(output: str | bytes | None) -> str:
    return output.decode("utf-8", errors="replace") if isinstance(output, bytes) else output or ""


def _parse_json_markers(output: str, marker: str) -> tuple[list[dict[str, Any]], list[str]]:
    payloads: list[dict[str, Any]] = []
    errors: list[str] = []
    for line in output.splitlines():
        if not line.startswith(marker):
            continue
        try:
            payload = json.loads(line[len(marker) :])
        except json.JSONDecodeError as exc:
            errors.append(type(exc).__name__)
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
        else:
            errors.append("marker_payload_not_object")
    return payloads, errors


def _invoke_child(
    *,
    capacity: int,
    bypass: bool = False,
    case_id: str | None = None,
    receipt_directory: Path | None = None,
) -> dict[str, Any]:
    profile = "removal" if bypass else "configured"
    case_id = case_id or f"cap-{capacity}-{profile}"
    receipt_directory = receipt_directory or (_r4_profile_receipt_root() / case_id)
    if not receipt_directory.resolve().is_relative_to(_R4_RAW_ROOT.resolve()):
        raise ValueError("R4 profile child outputs must be retained under ignored LOCAL/raw")
    receipt_directory.mkdir(parents=True, exist_ok=True)
    child_env = dict(os.environ)
    child_env.update(
        {
            "POLISYOS_R4_CHILD": "1",
            "POLISYOS_R4_CAPACITY": str(capacity),
            "POLISYOS_R4_BYPASS": "1" if bypass else "0",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "POLISYOS_EXECUTION_PROFILE": "dev",
            "POLISYOS_RUNNER_BACKEND": "local",
            "LOG_LEVEL": "WARNING",
            "POLISYOS_R4_RECEIPT_DIR": str(receipt_directory),
        }
    )
    child_benchmark_storage = receipt_directory / "benchmark-storage"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-o",
        f"cache_dir={receipt_directory / 'pytest-cache'}",
        "-o",
        f"log_file={receipt_directory / 'pytest.log'}",
        "-o",
        "tmp_path_retention_policy=all",
        "-o",
        "tmp_path_retention_count=1",
        f"--benchmark-storage={child_benchmark_storage.as_uri()}",
        "--basetemp",
        str(receipt_directory / "pytest-tmp"),
        "-q",
        "-s",
        "tests/integration/scientist/orchestration/workflows/"
        "test_r4_shared_study_admission.py::test_r4_native_child",
    ]
    child_started_ns = time.perf_counter_ns()
    try:
        completed = subprocess.run(
            command,
            cwd=_REPO_ROOT,
            env=child_env,
            capture_output=True,
            text=False,
            timeout=180,
            check=False,
        )
        child_process_elapsed_ns = time.perf_counter_ns() - child_started_ns
    except subprocess.TimeoutExpired as exc:
        output_receipts = _retain_child_output(
            capacity=capacity,
            bypass=bypass,
            stdout=exc.stdout,
            stderr=exc.stderr,
            receipt_directory=receipt_directory,
        )
        stdout = _decode_child_stream(exc.stdout)
        stderr = _decode_child_stream(exc.stderr)
        guard_payloads, guard_parse_errors = _parse_json_markers(
            stdout,
            "R4_CAS_GUARD_DIAGNOSTIC=",
        )
        return {
            "case_id": case_id,
            "capacity": capacity,
            "bypass": bypass,
            "status": "child_timeout",
            "child_returncode": None,
            "profile_result": None,
            "guard_diagnostic": guard_payloads[-1] if guard_payloads else None,
            "guard_diagnostic_parse_errors": guard_parse_errors,
            "timeout_seconds": 180,
            "output_receipts": output_receipts,
            "stdout_tail": _diagnostic_tail(stdout),
            "stderr_tail": _diagnostic_tail(stderr),
            "child_elapsed_ns": time.perf_counter_ns() - child_started_ns,
            "command": command,
        }
    output_receipts = _retain_child_output(
        capacity=capacity,
        bypass=bypass,
        stdout=completed.stdout,
        stderr=completed.stderr,
        receipt_directory=receipt_directory,
    )
    stdout = _decode_child_stream(completed.stdout)
    stderr = _decode_child_stream(completed.stderr)
    native_results, native_parse_errors = _parse_json_markers(stdout, "R4_NATIVE_RESULT=")
    guard_payloads, guard_parse_errors = _parse_json_markers(
        stdout,
        "R4_CAS_GUARD_DIAGNOSTIC=",
    )
    profile_result = native_results[0] if len(native_results) == 1 else None
    if profile_result is not None:
        profile_result["child_process_elapsed_ns"] = child_process_elapsed_ns
        profile_result["child_process_elapsed_basis"] = (
            "parent monotonic_ns around subprocess.run; includes isolated Python/pytest startup, the full controlled profile, CAS readback, shutdown, and child exit"
        )
    status = (
        "passed"
        if completed.returncode == 0 and profile_result is not None and not native_parse_errors
        else "child_failed"
        if completed.returncode != 0
        else "native_result_missing_or_malformed"
    )
    return {
        "case_id": case_id,
        "capacity": capacity,
        "bypass": bypass,
        "status": status,
        "child_returncode": completed.returncode,
        "profile_result": profile_result,
        "guard_diagnostic": guard_payloads[-1] if guard_payloads else None,
        "native_result_count": len(native_results),
        "native_result_parse_errors": native_parse_errors,
        "guard_diagnostic_count": len(guard_payloads),
        "guard_diagnostic_parse_errors": guard_parse_errors,
        "output_receipts": output_receipts,
        "stdout_tail": _diagnostic_tail(stdout),
        "stderr_tail": _diagnostic_tail(stderr),
        "child_elapsed_ns": child_process_elapsed_ns,
        "command": command,
    }


def _retain_child_output(
    *,
    capacity: int,
    bypass: bool,
    stdout: str | bytes | None,
    stderr: str | bytes | None,
    receipt_directory: Path | None = None,
) -> dict[str, Any]:
    """Persist complete native child output before any parent assertion."""
    configured_directory = receipt_directory or (
        Path(os.environ["POLISYOS_R4_RECEIPT_DIR"])
        if os.environ.get("POLISYOS_R4_RECEIPT_DIR")
        else None
    )
    if configured_directory is None:
        return {}
    directory = Path(configured_directory)
    directory.mkdir(parents=True, exist_ok=True)
    profile = "removal" if bypass else "configured"
    stem = f"cap-{capacity}-{profile}"
    receipts: dict[str, Any] = {}
    for stream_name, output in (("stdout", stdout), ("stderr", stderr)):
        content = output if isinstance(output, bytes) else (output or "").encode("utf-8")
        path = directory / f"{stem}.{stream_name}.txt"
        path.write_bytes(content)
        receipts[stream_name] = {
            "path": str(path),
            "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content),
        }
    return receipts


def _diagnostic_tail(output: str, *, limit: int = 80) -> str:
    """Keep failure reports readable while preserving route diagnostics."""
    lines = output.splitlines()
    relevant = [
        line
        for line in lines
        if any(
            marker in line
            for marker in (
                "R4_NATIVE_RESULT=",
                "Traceback",
                "AssertionError",
                "Error:",
                "error:",
                "FAILED",
                "Control worker",
                "control job",
                "legacy_workflow",
            )
        )
    ]
    return "\n".join(relevant[-limit:] if relevant else lines[-limit:])


def test_r4_child_output_retention_writes_full_timeout_streams(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt_directory = tmp_path / "receipts"
    monkeypatch.setenv("POLISYOS_R4_RECEIPT_DIR", str(receipt_directory))

    _retain_child_output(
        capacity=2,
        bypass=True,
        stdout=b"full partial child stdout\n",
        stderr=b"full partial child stderr\n",
    )

    assert (receipt_directory / "cap-2-removal.stdout.txt").read_text() == (
        "full partial child stdout\n"
    )
    assert (receipt_directory / "cap-2-removal.stderr.txt").read_text() == (
        "full partial child stderr\n"
    )


def test_r4_profile_driver_attempts_all_cases_before_aggregate_failure() -> None:
    """Exercise continuation with three tiny controlled child processes."""
    controlled_child = (
        "import json, sys; "
        "case_id = sys.argv[1]; "
        "status = 'controlled_failure' if case_id == 'cap-1-configured' else 'passed'; "
        "print('R4_DRIVER_CONTROLLED=' + json.dumps({'case_id': case_id, 'status': status})); "
        "sys.exit(7 if status == 'controlled_failure' else 0)"
    )
    attempted_case_ids: list[str] = []

    def invoke_controlled_case(profile_case: dict[str, Any]) -> dict[str, Any]:
        case_id = str(profile_case["case_id"])
        attempted_case_ids.append(case_id)
        completed = subprocess.run(
            [sys.executable, "-c", controlled_child, case_id],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        markers, parse_errors = _parse_json_markers(
            completed.stdout,
            "R4_DRIVER_CONTROLLED=",
        )
        child_result = markers[0] if len(markers) == 1 else None
        return {
            "status": (
                "passed"
                if completed.returncode == 0
                and child_result is not None
                and child_result.get("status") == "passed"
                else "child_failed"
            ),
            "child_returncode": completed.returncode,
            "profile_result": child_result,
            "controlled_stdout": completed.stdout,
            "controlled_stderr": completed.stderr,
            "controlled_parse_errors": parse_errors,
        }

    attempts = _attempt_all_r4_profiles(invoke_controlled_case)
    assert attempted_case_ids == [str(case["case_id"]) for case in _R4_PROFILE_CASES]
    assert [attempt["status"] for attempt in attempts] == [
        "child_failed",
        "passed",
        "passed",
    ]
    with pytest.raises(AssertionError, match="attempted all three fresh children"):
        _require_all_r4_profiles_passed(attempts)


def test_runtime_control_worker_shared_method_admission_and_removal_probe() -> None:
    """Measure cap 1/2, preserve results, and prove bridge removal escapes the cap."""
    receipt_root = _r4_profile_receipt_root()

    def invoke_profile(profile_case: dict[str, Any]) -> dict[str, Any]:
        case_id = str(profile_case["case_id"])
        return _invoke_child(
            capacity=int(profile_case["capacity"]),
            bypass=bool(profile_case["bypass"]),
            case_id=case_id,
            receipt_directory=receipt_root / case_id,
        )

    attempts = _attempt_all_r4_profiles(invoke_profile)
    print(
        "R4_NATIVE_PROFILE_ATTEMPTS="
        + json.dumps(
            [
                {
                    "case_id": attempt["case_id"],
                    "status": attempt["status"],
                    "child_returncode": attempt.get("child_returncode"),
                    "output_receipts": attempt.get("output_receipts", {}),
                    "guard_diagnostic_present": attempt.get("guard_diagnostic") is not None,
                }
                for attempt in attempts
            ],
            sort_keys=True,
            allow_nan=False,
        ),
        flush=True,
    )
    _require_all_r4_profiles_passed(attempts)
    profile_results = {str(attempt["case_id"]): attempt["profile_result"] for attempt in attempts}
    cap_one = profile_results["cap-1-configured"]
    cap_two = profile_results["cap-2-configured"]
    no_bridge = profile_results["cap-1-bridge-removal"]
    for profile in (cap_one, cap_two, no_bridge):
        assert profile["profile_elapsed_ns"] >= 0
        assert profile["child_process_elapsed_ns"] > 0
        rss = profile["process_peak_rss"]
        assert rss["available"] and type(rss["value"]) is int
        assert rss["units"] in {"KiB", "bytes"}
    print(
        "R4_NATIVE_PROFILES="
        + json.dumps(
            {"cap_one": cap_one, "cap_two": cap_two, "no_bridge": no_bridge},
            sort_keys=True,
            allow_nan=False,
        ),
        flush=True,
    )

    assert cap_one["capacity"] == 1
    assert cap_one["source"] == "candidate_configured_runtime_profile"
    assert cap_one["profile_revision"] == "r4-native-method-cap-1-v1"
    assert cap_one["control_worker_results"] == [True, True]
    assert cap_one["run_experiment_peak_active"] == 2
    assert cap_one["submit_peak_active"] == 2
    assert cap_one["dispatch_count"] == 2
    assert cap_one["dispatches_on_shared_workers"] == 2
    assert set(cap_one["study_outputs"]) == {"0", "1"}

    assert cap_one["dispatch_peak"] == 1
    assert cap_two["dispatch_peak"] == 2
    for profile in (cap_one, cap_two, no_bridge):
        assert profile["run_experiment_entries"] == 2
        assert profile["method_backend_entries"] == profile["submit_count"] == 2
    assert cap_one["expected_fold_count"] == cap_one["observed_fold_count"] == 12
    assert cap_two["expected_fold_count"] == cap_two["observed_fold_count"] == 12
    for profile in (cap_one, cap_two):
        assert profile["physical_active_workers_peak"] == profile["capacity"]
        assert len(profile["executor_queue_wait_observations"]) == 2
    for profile in (cap_one, cap_two, no_bridge):
        diagnostic = profile["cas_guard_diagnostic"]
        assert diagnostic["shared_executor_object_id"]
        assert len(diagnostic["guard_bindings"]) == 4
        assert set(diagnostic["guard_count_by_dependency"]) == {
            "content_addressed_storage",
            "control_plane_store",
        }
        assert diagnostic["executor_queue_submissions"]
    assert cap_one["completed_jobs"] == cap_two["completed_jobs"] == 2
    for profile in (cap_one, cap_two):
        for study_index, output in profile["study_outputs"].items():
            assert output["causal_node_status"] == "ok", (
                f"study {study_index} causal node failed: {output['causal_node_error']}"
            )
            assert output["causal_node_error"] is None
            assert output["input_owner_scope"]["scope_class"] == "admitted_scope"
            assert output["result_owner_scope"]["scope_class"] == "admitted_scope"
            assert output["evidence_owner_scope"]["scope_class"] == "admitted_scope"
            assert output["state_linked"]
            assert output["evidence_state_linked"]
    assert all(output["state_linked"] for output in cap_one["study_outputs"].values()), (
        "cap-1 MethodBackend CAS results were not projected into final Scientist state: "
        + json.dumps(cap_one["study_outputs"], sort_keys=True)
    )
    assert all(output["state_linked"] for output in cap_two["study_outputs"].values()), (
        "cap-2 MethodBackend CAS results were not projected into final Scientist state: "
        + json.dumps(cap_two["study_outputs"], sort_keys=True)
    )
    for study_index in ("0", "1"):
        cap_one_output = cap_one["study_outputs"][study_index]
        cap_two_output = cap_two["study_outputs"][study_index]
        assert cap_one_output["result_ref"] == cap_two_output["result_ref"]
        assert (
            cap_one_output["semantic_evidence_sha256"] == cap_two_output["semantic_evidence_sha256"]
        )
        assert (
            cap_one_output["evidence_manifest_profile_sha256"]
            == cap_two_output["evidence_manifest_profile_sha256"]
        )
        attempt_specific_fields = {"evidence_ref", "attempt_cost_attribution"}
        cap_one_semantic_output = {
            key: value
            for key, value in cap_one_output.items()
            if key not in attempt_specific_fields
        }
        cap_two_semantic_output = {
            key: value
            for key, value in cap_two_output.items()
            if key not in attempt_specific_fields
        }
        # Compare the consumer-validated semantic projection, not a raw evidence ID
        # that commits the legitimately different timing/cost of each attempt.
        assert cap_one_semantic_output == cap_two_semantic_output
        for output in (cap_one_output, cap_two_output):
            cost = output["attempt_cost_attribution"]
            assert output["evidence_ref"]
            assert output["evidence_manifest_profile_sha256"]
            assert cost["method_fqn"] == TMLEEstimator.signature.fqn
            assert cost["backend"]
            assert cost["wall_time_ms"] >= 0.0
            assert cost["estimated_cost_usd"] >= 0.0
            assert cost["usd_per_ms"] > 0.0

    assert no_bridge["capacity"] == 1
    assert no_bridge["dispatch_peak"] == 2
    assert no_bridge["dispatches_on_shared_workers"] == 0
    assert no_bridge["physical_active_workers_peak"] == 0
    assert no_bridge["executor_queue_wait_observations"] == []
    assert no_bridge["expected_fold_count"] == no_bridge["observed_fold_count"] == 12
    assert no_bridge["completed_jobs"] == 2
