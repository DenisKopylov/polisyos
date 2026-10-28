"""C96 test-owned HTTP/worker witness; never a production authority or scheduler."""

from __future__ import annotations

import gzip
import hashlib
import importlib.metadata
import inspect
import json
import os
import resource
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
from importlib.machinery import ModuleSpec
from importlib.util import module_from_spec
from pathlib import Path
from typing import Any


def _bootstrap_checkout_imports() -> dict[str, Any]:
    """Bind this checkout before pytest import and spawn target resolution.

    The repository tests root is a namespace directory. Merely prepending its
    parent to sys.path still lets a later installed regular ``tests`` package
    win. Bind one explicit local namespace, without executing another package
    or replacing any already-loaded foreign test module.
    """
    product = Path(__file__).resolve().parents[2]
    owned_tests = product / "tests"
    roots = (product, product / "src", owned_tests)
    if not (
        (product / "pytest.ini").is_file()
        and (product / "src/polisyos").is_dir()
        and (owned_tests / "conftest.py").is_file()
        and (owned_tests / "_helpers/__init__.py").is_file()
    ):
        raise RuntimeError(f"C96 bootstrap layout is not a PolicyOS product root: {product}")
    if (owned_tests / "__init__.py").exists():
        raise RuntimeError("C96 namespace contract changed: review the actual tests package owner")
    for name, module in tuple(sys.modules.items()):
        if name != "tests" and not name.startswith("tests."):
            continue
        locations = []
        origin = getattr(module, "__file__", None)
        if isinstance(origin, str):
            locations.append(Path(origin).resolve())
        locations.extend(Path(item).resolve() for item in getattr(module, "__path__", ()))
        if not locations or any(not item.is_relative_to(owned_tests) for item in locations):
            raise RuntimeError(
                f"C96 refuses already-loaded foreign tests module: {name} {locations}"
            )
    explicit = [str(item) for item in roots]
    # Keep the ordinary interpreter/dependency paths; no environment-variable
    # edit, plugin disable, import-mode change or incidental PYTHONPATH is needed.
    sys.path[:] = explicit + [item for item in sys.path if item not in explicit]
    created_namespace = "tests" not in sys.modules
    if created_namespace:
        spec = ModuleSpec("tests", loader=None, is_package=True)
        spec.submodule_search_locations = [str(owned_tests)]
        sys.modules["tests"] = module_from_spec(spec)
    namespace_paths = [str(Path(item).resolve()) for item in sys.modules["tests"].__path__]
    if namespace_paths != [str(owned_tests)]:
        raise RuntimeError(f"C96 tests namespace is not exclusively local: {namespace_paths}")
    return {
        "strategy": "explicit_checkout_namespace_before_pytest_and_spawn_target",
        "product_root": str(product),
        "src_root": str(product / "src"),
        "tests_root": str(owned_tests),
        "tests_namespace_paths": namespace_paths,
        "created_tests_namespace": created_namespace,
        "sys_path_prefix": sys.path[:3],
        "pythonpath_was_present": bool(os.getenv("PYTHONPATH")),
        "depends_on_pythonpath": False,
        "entry_module_name": __name__,
    }


# A spawned process reconstructs the file entrypoint as __mp_main__ before
# unpickling the canonical tests._helpers target; this same bootstrap runs there.
_IMPORT_BOOTSTRAP = _bootstrap_checkout_imports()


def _event(observed: dict[str, Any], name: str, **values: Any) -> None:
    observed["trace"].append(
        {
            "event": name,
            "pid": os.getpid(),
            "thread_id": threading.get_ident(),
            "native_thread_id": threading.get_native_id(),
            "monotonic_ns": time.monotonic_ns(),
            **values,
        }
    )


def _owner_identity(call: Any) -> dict[str, Any]:
    file = Path(inspect.getsourcefile(call) or "").resolve()
    return {
        "module": call.__module__,
        "qualname": call.__qualname__,
        "path": str(file),
        "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
    }


def _prelude(root: Path) -> dict[str, Any]:
    product = Path(__file__).resolve().parents[2]
    checkout = product.parent
    source = subprocess.check_output(
        ["git", "rev-parse", "HEAD", "HEAD^{tree}"], cwd=checkout, text=True
    ).splitlines()
    expected = os.getenv("POLISYOS_C96_EXPECTED_HEAD")
    expected_tree = os.getenv("POLISYOS_C96_EXPECTED_TREE")
    if (expected is not None and source[0] != expected) or (
        expected_tree is not None and source[1] != expected_tree
    ):
        raise ValueError(f"C96 source mismatch: actual {source}; do not repair checkout")
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=checkout, text=True
    )
    if dirty:
        raise ValueError("C96 deciding source must be committed before its execution")
    versions = {}
    for package in ("pytest", "psutil", "numpy", "scikit-learn", "duckdb"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "unavailable"
    return {
        "schema": "policyos.e02.c96.process_observation.v1",
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "executable": sys.executable,
        "flags": repr(sys.flags),
        "argv": sys.argv,
        "source": source,
        "product_root": str(product),
        "import_bootstrap": {
            "active_module": _IMPORT_BOOTSTRAP,
            "reconstructed_main": getattr(sys.modules.get("__main__"), "_IMPORT_BOOTSTRAP", None),
        },
        "environment": {
            key: os.getenv(key)
            for key in (
                "PYTHONDONTWRITEBYTECODE",
                "PYTHONPYCACHEPREFIX",
                "PYTEST_ADDOPTS",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
        "versions": versions,
        "disk_free_before": shutil.disk_usage(root).free,
        "cpu_count": os.cpu_count(),
        "stage": "setup",
        "trace": [],
        "thread_errors": [],
    }


def _readset(
    observed: dict[str, Any], evidence: Path, *, filename: str = "child-readset.json.gz"
) -> None:
    product = Path(observed.get("product_root", Path(__file__).resolve().parents[2]))
    selected = set()
    foreign = []
    for module_name, module in tuple(sys.modules.items()):
        name = getattr(module, "__file__", None)
        if not isinstance(name, str) or not name.endswith(".py"):
            continue
        file = Path(name).resolve()
        if any(file.is_relative_to(product / part) for part in ("src/polisyos", "tests", "tools")):
            selected.add(file)
        elif module_name.startswith(("polisyos.", "tests.", "tools.", "_helpers.")):
            foreign.append({"module": module_name, "path": str(file)})
    checkout = product.parent
    tracked = subprocess.check_output(
        [
            "git",
            "ls-tree",
            "-r",
            "-z",
            "HEAD",
            "--",
            *[
                str((product / part).relative_to(checkout))
                for part in ("src/polisyos", "tests", "tools")
            ],
        ],
        cwd=checkout,
    )
    git_blobs = {}
    for item in tracked.split(b"\0"):
        if item:
            header, name = item.split(b"\t", 1)
            git_blobs[name.decode()] = header.split()[2].decode()
    rows = []
    for file in sorted(selected):
        if not file.is_file():
            rows.append({"path": str(file), "missing": True})
            continue
        source = file.read_bytes()
        blob = hashlib.sha1(
            b"blob " + str(len(source)).encode() + b"\0" + source, usedforsecurity=False
        ).hexdigest()
        expected = git_blobs.get(str(file.relative_to(checkout)))
        rows.append(
            {
                "path": str(file.relative_to(product)),
                "sha256": hashlib.sha256(source).hexdigest(),
                "git_blob": expected,
                "actual_blob": blob,
                "git_match": blob == expected,
            }
        )
    qualified = not foreign and all(row.get("git_match") is True for row in rows)
    data = json.dumps(
        {
            "pid": os.getpid(),
            "scope": "finite loaded Python .py files only",
            "unresolved": ["native libraries", "data outside fixtures", "unloaded code"],
            "foreign_source_modules": foreign,
            "source_qualified": qualified,
            "files": rows,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    target = evidence / filename
    target.write_bytes(gzip.compress(data, mtime=0))
    observed["readset"] = {
        "path": target.name,
        "bytes": target.stat().st_size,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "uncompressed_bytes": len(data),
        "python_paths": len(rows),
        "source_qualified": qualified,
    }


def _snapshot(reader: Any, job_id: str, before_progress: dict[str, Any]) -> dict[str, Any]:
    from polisyos.runtime.http.services.control_plane_store import ControlJobLeaseLostError

    record = reader.get_job(job_id)
    assert record is not None
    verified = False
    verification_error = None
    try:
        established = reader.get_cancelled_job_verified_record(job_id)
        verified = established.state == "cancelled" and established.progress == record.progress
    except ControlJobLeaseLostError as exc:
        verification_error = str(exc)
    with sqlite3.connect(reader._sqlite_path) as db:
        events = db.execute(
            "SELECT event_type FROM control_job_events WHERE job_id = ?", (job_id,)
        ).fetchall()
        outbox = db.execute(
            "SELECT topic FROM control_outbox_events WHERE job_id = ?", (job_id,)
        ).fetchall()
    progress = dict(record.progress)
    cancellation = progress.pop("cancellation", {})
    return {
        "state": record.state,
        "attempt": record.attempt,
        "lease_owner": record.lease_owner,
        "manifest_ref": record.capability_manifest_ref,
        "verified": verified,
        "verification_error": verification_error,
        "cancellation_event_count": sum(name == "job_cancelled" for (name,) in events),
        "cancellation_outbox_count": sum(name == "control.job.cancelled" for (name,) in outbox),
        "other_terminal_count": sum(name in {"job_completed", "job_failed"} for (name,) in events),
        "progress_preserved": progress == before_progress,
        "physical_stop_status": cancellation.get("physical_stop_status"),
    }


def _response(response: Any) -> dict[str, Any]:
    try:
        value = response.json()
    except ValueError:
        value = {"non_json": response.text[:1000]}
    return {"status": response.status_code, **value}


def _queue_snapshot(executor: Any, running: Any, queued: Any, queued_calls: list) -> dict:
    with executor._admission_lock:
        return {
            "physical_workers": executor._physical_workers,
            "queued_jobs": executor._queued_jobs,
            "outstanding_jobs": executor._outstanding_jobs,
            "capacity": executor._max_workers,
            "queue_capacity": executor._max_queued,
            "running_physical": running.running() and not running.done(),
            "queued_body_calls": len(queued_calls),
            "cancelled_queued": queued.cancelled(),
        }


def _exercise(
    root: Path, observed: dict[str, Any], *, cancel_queued: bool, remove_write_capacity: bool
) -> None:
    import pytest

    from polisyos.common import async_tools
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.security.identity import PolicyOSRole, UserIdentityClaims
    from polisyos.runtime.http import deployment_security, resilience
    from polisyos.runtime.http.app import create_runtime_api_app
    from polisyos.runtime.http.cancellation_admission import is_current_cancellation_authority
    from polisyos.runtime.http.services.control_plane_store import (
        ControlJobLeaseLostError,
        ControlPlaneStore,
    )
    from polisyos.runtime.http.services.control_worker import ControlWorker
    from polisyos.runtime.quality.data_state_substrate import l1_dcat_variable_availability
    from polisyos.runtime.quality.substrate_registry import (
        CatalogServingSourceSelection,
        catalog_serving_source_scope,
        resolve_catalog_serving_source,
    )
    from tests._helpers.runtime_http import (
        build_runtime_api_env,
        close_runtime_api_env,
        deployment_security_config_mapping,
    )
    from tests.unit.runtime.http import test_runtime_api_authz as authz
    from tests.unit.runtime.http.test_control_plane_store import (
        _job_creation_event,
        _job_execution_scope,
    )
    from tests.unit.runtime.quality.test_catalog_source_identity import _selected_fixture

    revision = "c96-real-saturation-r1"
    profile = async_tools.SharedExecutorProfile(capacity=1, queue_capacity=1, revision=revision)
    async_tools.configure_shared_executor_profile(profile)
    executor = async_tools.get_shared_executor()
    code, owner, expected_source = _selected_fixture(root / "catalog")
    selection = CatalogServingSourceSelection(
        snapshot_root=owner / "snapshot", source_owner_root=owner, catalog_run_profile="prod_full"
    )
    env = build_runtime_api_env(
        root / "runtime-env",
        include_test_client=False,
        app_kwargs={
            "repo_root": code,
            "catalog_source_selection": selection,
            "process_worker_capacity": 1,
            "process_worker_profile_revision": revision,
        },
    )
    patch = pytest.MonkeyPatch()

    def app_factory(**kwargs: Any) -> Any:
        kwargs.setdefault("repo_root", code)
        kwargs.setdefault("catalog_source_selection", selection)
        kwargs["process_worker_capacity"] = 1
        kwargs["process_worker_profile_revision"] = revision
        return create_runtime_api_app(**kwargs)

    patch.setattr(authz, "create_runtime_api_app", app_factory)
    client, cell, provider = authz._build_secure_client(
        env,
        opa_client=authz._AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
        repo_root=code,
        catalog_source_selection=selection,
    )
    tenant = env["tenant_a"]
    bearer = authz._fixture_bearer("c96-real-saturation-authorized")
    foreign = authz._fixture_bearer("c96-real-saturation-foreign")
    for token, selected_tenant in [(bearer, tenant), (foreign, env["tenant_b"])]:
        provider.put_claim(
            token,
            UserIdentityClaims(
                sub="runtime-canary",
                tenant_id=selected_tenant,
                cell_id=cell.cell_id,
                roles=frozenset({PolicyOSRole.ADMIN}),
                mfa_verified=True,
                iss="https://idp.example",
                aud="polisyos-runtime",
                exp=9_999_999_999,
                iat=1,
                jti="c96-" + selected_tenant,
            ),
        )
    config = deployment_security_config_mapping(root)
    registry = root / "cells.json"
    registry.write_text(
        json.dumps(
            {
                "cells": [cell.model_dump(mode="json")],
                "tenants": [
                    {
                        "tenant_id": item,
                        "name": "C96 synthetic tenant",
                        "tier": cell.tier.value,
                        "region": cell.region,
                        "cell_id": cell.cell_id,
                    }
                    for item in (tenant, env["tenant_b"])
                ],
            }
        )
    )
    config["cell_registry_path"] = str(registry)
    config["service_principals"][0].update(
        tenant_id=tenant, cell_id=cell.cell_id, permissions=["runs.view", "jobs.cancel"]
    )

    def grants(allowed: bool) -> Any:
        config["service_principals"][0]["permissions"] = (
            ["runs.view", "jobs.cancel"] if allowed else ["runs.view"]
        )
        return deployment_security.build_deployment_security(
            deployment_security.DeploymentSecurityConfig.from_mapping(config)
        ).principal_grants

    allowed_grants = grants(True)
    denied_grants = grants(False)
    client.app.state.runtime_deployment_principal_grants = allowed_grants
    authz._install_authorization_audit_capture(client)
    headers = {"Authorization": f"Bearer {bearer}", "X-Tenant-ID": tenant}
    compute_entered = threading.Event()
    release_compute = threading.Event()
    handler_entered = threading.Event()
    continue_handler = threading.Event()
    late_finished = threading.Event()
    do_late = threading.Event()
    queued_calls: list[int] = []
    late_refused: dict[str, bool] = {}
    renewal_calls: list[int] = []
    control_calls: list[dict] = []
    running_future = queued_future = worker = dispatch_thread = reader = removed_guard = None
    try:
        with client:
            service = client.app.state.runtime_container.control_service
            assert service is not None
            if service._worker is not None:
                service._worker.stop()
            store = service._control_store
            raw = store._target
            reader = ControlPlaneStore(backend="sqlite", sqlite_path=raw._sqlite_path)
            actual_source = service.catalog_serving_source
            fresh_source = resolve_catalog_serving_source(
                code, selection=selection, requested_profile="prod_full"
            )
            assert (
                actual_source.database_path
                == expected_source.database_path
                == fresh_source.database_path
            )
            assert (
                actual_source.read_source_identity
                == expected_source.read_source_identity
                == fresh_source.read_source_identity
            )
            with catalog_serving_source_scope(actual_source):
                availability = l1_dcat_variable_availability(code, "government.balance")
            assert availability.status == "unavailable"
            observed["catalog"] = {
                "real_reader_identity_matches": True,
                "read_source_identity": repr(fresh_source.read_source_identity),
                "actual_database_path": str(actual_source.database_path),
                "availability_ref": availability.coverage_ref,
            }
            cas = FileSystemCAS(env["cas_root"])
            options = ArtifactWriteOptions(
                kind="runtime.capability_manifest",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.test.C96Manifest", version="1.0"),
            )
            initial = cas.put_json({"fixture": "c96-control-initial"}, options)
            late = cas.put_json({"fixture": "c96-control-late"}, options)
            payload = cas.put_json({"fixture": "c96-control-input"}, options)
            scope = _job_execution_scope()
            scope.update(tenant_id=tenant, cell_id=cell.cell_id)
            creation = _job_creation_event(execution_scope=scope)
            creation.update(
                capability_manifest_ref=str(initial.artifact_id),
                payload_ref=str(payload.artifact_id),
            )
            job = store.create_job(
                job_id="job_execution_admission",
                kind="workflow_run",
                run_id="run_execution_admission",
                pipeline_id=None,
                requested_execution_profile=None,
                effective_execution_profile="dev",
                policy_flags={"candidate": True},
                capability_manifest_ref=str(initial.artifact_id),
                payload_ref=str(payload.artifact_id),
                submitted_by="c96-configured-test",
                creation_event_payload=creation,
            )
            original_renew = raw.renew_job_lease

            def observe_renew(**kwargs: Any) -> bool:
                answer = original_renew(**kwargs)
                if compute_entered.is_set() and not release_compute.is_set():
                    renewal_calls.append(time.monotonic_ns())
                    _event(observed, "actual_renewal", result=answer)
                return answer

            patch.setattr(raw, "renew_job_lease", observe_renew)
            original_cancel = raw.cancel_job
            if remove_write_capacity:
                guard = store._guard
                removed_guard = resilience.BlockingDependencyGuard(
                    dependency_name=guard._dependency_name,
                    timeout_seconds=guard._timeout_seconds,
                    breaker=guard._breaker,
                    executor=executor,
                    unavailable_exception_types=guard._unavailable_exception_types,
                    unavailable_exception_predicate=guard._unavailable_exception_predicate,
                )
            tamper = threading.Event()

            def observe_cancel(**kwargs: Any) -> Any:
                current = is_current_cancellation_authority(kwargs.get("authorization_proof"))
                call = {
                    "current_authority": current,
                    "body_called": False,
                    "operation_id": kwargs.get("operation_id"),
                    "tampered": tamper.is_set(),
                }
                control_calls.append(call)
                _event(observed, "actual_cancel_entry", **call)

                def write() -> Any:
                    call["body_called"] = True
                    _event(observed, "actual_cancel_body", owner=_owner_identity(original_cancel))
                    values = dict(kwargs)
                    if tamper.is_set():
                        values["operation_id"] += "-substituted-after-proof"
                    return original_cancel(**values)

                if removed_guard is not None and not tamper.is_set():
                    return removed_guard.run(write)
                return write()

            patch.setattr(raw, "cancel_job", observe_cancel)

            def handler(_job: Any) -> None:
                handler_entered.set()
                _event(observed, "real_handler_entered", attempt=_job.attempt)
                assert continue_handler.wait(timeout=120), "C96 handler action was never released"
                if do_late.is_set():
                    for name, operation in [
                        (
                            "progress",
                            lambda: store.upsert_progress(
                                job_id=job.job_id, progress={"late": True}
                            ),
                        ),
                        (
                            "manifest",
                            lambda: store.update_manifest_ref(
                                job_id=job.job_id, capability_manifest_ref=str(late.artifact_id)
                            ),
                        ),
                        (
                            "terminal",
                            lambda: store.complete_job(
                                job_id=job.job_id,
                                expected_lease_owner=_job.lease_owner,
                                expected_attempt=_job.attempt,
                            ),
                        ),
                    ]:
                        try:
                            operation()
                        except ControlJobLeaseLostError:
                            late_refused[name] = True
                        else:
                            late_refused[name] = False
                        _event(
                            observed, "actual_stale_write", kind=name, refused=late_refused[name]
                        )
                late_finished.set()

            worker = ControlWorker(
                store=store, handler=handler, worker_id="c96-actual-worker", lease_seconds=2
            )
            worker._heartbeat_interval_s = 0.05

            def dispatch() -> None:
                try:
                    worker.dispatch_once()
                except BaseException as exc:
                    observed["thread_errors"].append(
                        {"type": type(exc).__name__, "message": str(exc)}
                    )

            dispatch_thread = threading.Thread(
                target=dispatch, name="c96-actual-dispatch", daemon=True
            )
            dispatch_thread.start()
            assert handler_entered.wait(timeout=30)
            running = reader.get_job(job.job_id)
            assert (
                running is not None
                and running.state == "running"
                and running.lease_expires_at is not None
            )
            observed["running"] = {
                "attempt": running.attempt,
                "owner": running.lease_owner,
                "manifest_ref": running.capability_manifest_ref,
            }

            def compute() -> str:
                _event(observed, "compute_body_entered")
                compute_entered.set()
                assert release_compute.wait(timeout=120), "C96 held compute was never released"
                _event(observed, "compute_body_returned")
                return "event-held; not a native fit"

            running_future = executor.submit(compute)
            assert compute_entered.wait(timeout=30)

            def queued_body() -> None:
                queued_calls.append(time.monotonic_ns())
                _event(observed, "actual_queued_body_entered")

            queued_future = executor.submit(queued_body)
            accepted_pending = not queued_future.done() and not queued_future.running()
            assert accepted_pending, "The required second future was not accepted pending."
            if cancel_queued:
                assert queued_future.cancel()
            queue = _queue_snapshot(executor, running_future, queued_future, queued_calls)
            queue["accepted_pending"] = accepted_pending
            queue["queued_future_id"] = id(queued_future)
            queue["queued_future_type"] = (
                type(queued_future).__module__ + "." + type(queued_future).__qualname__
            )
            queue["submit_owner"] = _owner_identity(executor.submit)
            with pytest.raises(async_tools.SharedExecutorBackpressureError) as full:
                executor.submit(lambda: queued_calls.append(-1))
            queue["overflow_code"] = full.value.code
            assert (full.value.capacity, full.value.queue_capacity, full.value.queue_depth) == (
                1,
                1,
                1,
            )
            observed["queue"] = queue
            _event(observed, "actual_queue_full", **queue)
            deadline = time.monotonic() + 20
            renewed = reader.get_job(job.job_id)
            while time.monotonic() < deadline:
                renewed = reader.get_job(job.job_id)
                if renewed is not None and renewed.lease_expires_at > running.lease_expires_at:
                    break
                threading.Event().wait(0.01)
            assert renewed is not None and renewed.lease_expires_at > running.lease_expires_at
            observed["renewal"] = {
                "before": running.lease_expires_at.isoformat(),
                "after": renewed.lease_expires_at.isoformat(),
                "calls_under_held_compute": len(renewal_calls),
            }
            url = f"/api/v1/control/jobs/{job.job_id}/cancel"
            body = {
                "operation_id": "c96-cancel-positive",
                "expected_lease_owner": running.lease_owner,
                "expected_attempt": running.attempt,
            }
            client.app.state.control_job_cancellation_rollout_enabled = True
            observed["adversarial"] = []
            for kind in (
                "disabled-rollout",
                "denied-permission",
                "wrong-tenant",
                "stale-attempt",
                "body-proof-substitution",
            ):
                client.app.state.runtime_deployment_principal_grants = (
                    denied_grants if kind == "denied-permission" else allowed_grants
                )
                client.app.state.control_job_cancellation_rollout_enabled = (
                    kind != "disabled-rollout"
                )
                if kind == "body-proof-substitution":
                    tamper.set()
                negative_body = {**body, "operation_id": "c96-negative-" + kind}
                if kind == "stale-attempt":
                    negative_body["expected_attempt"] = running.attempt + 1
                selected_headers = (
                    {"Authorization": f"Bearer {foreign}", "X-Tenant-ID": env["tenant_b"]}
                    if kind == "wrong-tenant"
                    else headers
                )
                response = client.post(url, headers=selected_headers, json=negative_body)
                tamper.clear()
                current = _snapshot(reader, job.job_id, renewed.progress)
                zero = (
                    current["state"] == "running"
                    and current["cancellation_event_count"] == 0
                    and current["cancellation_outbox_count"] == 0
                    and current["other_terminal_count"] == 0
                    and current["manifest_ref"] == running.capability_manifest_ref
                    and current["progress_preserved"]
                )
                observed["adversarial"].append(
                    {"kind": kind, "status": response.status_code, "zero_protected_effects": zero}
                )
                assert response.status_code >= 400 and zero
            client.app.state.runtime_deployment_principal_grants = allowed_grants
            client.app.state.control_job_cancellation_rollout_enabled = True
            before = reader.get_job(job.job_id)
            assert before is not None
            positive_at = len(control_calls)
            observed["stage"] = "actual_http_cancellation"
            observed["post"] = _response(client.post(url, headers=headers, json=body))
            # Always collect the actual durable state before interpreting the status code.
            observed["persisted"] = _snapshot(reader, job.job_id, before.progress)
            observed["fresh_http"] = _response(
                client.get(f"/api/v1/control/jobs/{job.job_id}", headers=headers)
            )
            observed["retry"] = {"status": None}
            if observed["persisted"]["verified"]:
                observed["retry"] = _response(client.post(url, headers=headers, json=body))
                do_late.set()
            continue_handler.set()
            assert late_finished.wait(timeout=30)
            assert dispatch_thread is not None
            dispatch_thread.join(timeout=30)
            assert not dispatch_thread.is_alive(), "C96 dispatch did not finish before app close"
            observed["late_refused"] = late_refused
            observed["persisted"] = _snapshot(reader, job.job_id, before.progress)
            observed["held_until_readback"] = (
                not running_future.done() and not release_compute.is_set() and not queued_calls
            )
            selected_calls = control_calls[positive_at:]
            observed["positive_current_authority_calls"] = sum(
                c["current_authority"] for c in selected_calls
            )
            observed["positive_control_entry_calls"] = len(selected_calls)
            observed["positive_control_body_calls"] = sum(c["body_called"] for c in selected_calls)
            observed["control_owner"] = _owner_identity(original_cancel)
            observed["guard_identity"] = {
                "constructor": _owner_identity(resilience.build_runtime_control_store_guard),
                "control_guard_type": type(store._guard).__module__
                + "."
                + type(store._guard).__qualname__,
                "compute_executor_type": type(executor).__module__
                + "."
                + type(executor).__qualname__,
                "control_timeout_seconds": store._guard._timeout_seconds,
                "control_executor_id": id(store._guard._executor),
                "compute_executor_id": id(executor),
                "removal_executor_id": id(removed_guard._executor) if removed_guard else None,
                "same_breaker_and_policy": removed_guard is None
                or (
                    removed_guard._breaker is store._guard._breaker
                    and removed_guard._timeout_seconds == store._guard._timeout_seconds
                    and removed_guard._unavailable_exception_types
                    == store._guard._unavailable_exception_types
                    and removed_guard._unavailable_exception_predicate
                    is store._guard._unavailable_exception_predicate
                ),
            }
            observed["stage"] = "complete"
    finally:
        continue_handler.set()
        if worker is not None:
            worker.stop()
        if dispatch_thread is not None:
            dispatch_thread.join(timeout=30)
            assert not dispatch_thread.is_alive(), "C96 dispatch did not stop"
        release_compute.set()
        if running_future is not None:
            running_future.result(timeout=30)
        if queued_future is not None and not queued_future.cancelled():
            queued_future.result(timeout=30)
        if removed_guard is not None:
            removed_guard.close()
        if reader is not None:
            reader.close()
        patch.undo()
        close_runtime_api_env(env)
        executor.shutdown(wait=True, cancel_futures=True)
        if running_future is not None and queued_future is not None:
            observed["queue_after_release"] = _queue_snapshot(
                executor, running_future, queued_future, queued_calls
            )


def run_capacity_case(
    case_dir: str, evidence_dir: str, *, cancel_queued: bool, remove_write_capacity: bool
) -> None:
    """Record fresh-process source/environment and all deciding observations."""
    root = Path(case_dir)
    root.mkdir(parents=True, exist_ok=False)
    evidence = Path(evidence_dir)
    observed: dict[str, Any] = {"pid": os.getpid(), "stage": "prelude", "trace": []}
    started = time.monotonic_ns()
    failed = False
    try:
        observed = _prelude(root)
        observed["case"] = {
            "cancel_queued": cancel_queued,
            "remove_write_capacity": remove_write_capacity,
            "authority": "configured synthetic test identity/permission only",
            "compute": "event-held A only; no native fit/G acceptance",
        }
        _exercise(
            root, observed, cancel_queued=cancel_queued, remove_write_capacity=remove_write_capacity
        )
    except BaseException as exc:
        failed = True
        observed["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
    finally:
        observed["wall_ns"] = time.monotonic_ns() - started
        observed["self_maxrss"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        observed["self_maxrss_unit"] = "bytes" if sys.platform == "darwin" else "KiB"
        observed["disk_free_after"] = shutil.disk_usage(root).free
        _readset(observed, evidence)
        (evidence / "observation.json").write_text(
            json.dumps(observed, sort_keys=True, indent=2, default=str) + "\n"
        )
    if failed or not observed["readset"]["source_qualified"]:
        raise SystemExit(1)


class _PytestObserver:
    """Observe the actual pytest process without changing plugins or selection."""

    def __init__(self, observed: dict[str, Any]) -> None:
        self.observed = observed

    def pytest_configure(self, config: Any) -> None:
        self.observed["pytest"] = {
            "pid": os.getpid(),
            "rootpath": str(config.rootpath),
            "inipath": str(config.inipath),
            "importmode": config.getoption("importmode"),
            "ini_addopts": config.getini("addopts"),
            "plugins": sorted(
                [
                    {"name": name, "module": getattr(plugin, "__name__", type(plugin).__module__)}
                    for name, plugin in config.pluginmanager.list_name_plugin()
                    if plugin is not None
                ],
                key=lambda value: value["name"],
            ),
        }

    def pytest_collection_finish(self, session: Any) -> None:
        self.observed["collected_node_ids_after_deselection"] = [
            item.nodeid for item in session.items
        ]

    def pytest_sessionfinish(self, session: Any, exitstatus: Any) -> None:
        self.observed["pytest_exitstatus"] = int(exitstatus)
        self.observed["junit_path"] = session.config.getoption("xmlpath")


def _observe_pytest() -> int:
    """Run normal pytest and save compact same-PID input/output custody."""
    evidence = Path(os.environ["POLISYOS_C96_EVIDENCE_DIR"]) / "parent"
    evidence.mkdir(parents=True, exist_ok=True)
    target = evidence / "parent-process.json"
    assert not target.exists(), "Every deciding phase needs a fresh evidence directory."
    observed = _prelude(evidence)
    observed["stage"] = "before_pytest_import"
    observed["pytest_not_yet_imported"] = "pytest" not in sys.modules
    prefix = os.getenv("PYTHONPYCACHEPREFIX")
    assert prefix is not None, "Declare an initially empty private PYTHONPYCACHEPREFIX."
    private = Path(prefix)
    assert private.is_dir() and not any(private.iterdir())
    assert sys.dont_write_bytecode is True
    assert os.getenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD") is None
    assert not os.getenv("PYTEST_ADDOPTS"), "Do not inject an unrecorded pytest profile."
    observed["initial_private_pycache_empty"] = True
    observed["sys_pycache_prefix"] = sys.pycache_prefix
    target.write_text(json.dumps(observed, sort_keys=True, indent=2, default=str) + "\n")
    started = time.monotonic_ns()
    try:
        import pytest

        code = int(pytest.main(sys.argv[2:], plugins=[_PytestObserver(observed)]))
        observed["stage"] = "pytest_finished"
        return code
    except BaseException:
        observed["error"] = traceback.format_exc()
        raise
    finally:
        observed["wall_ns"] = time.monotonic_ns() - started
        checkout = Path(observed["product_root"]).parent
        observed["source_after"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD", "HEAD^{tree}"], cwd=checkout, text=True
        ).splitlines()
        _readset(observed, evidence, filename="parent-readset.json.gz")
        target.write_text(json.dumps(observed, sort_keys=True, indent=2, default=str) + "\n")
        if (
            not observed["readset"]["source_qualified"]
            or observed["source_after"] != observed["source"]
        ):
            raise RuntimeError("C96 actual loaded source is not qualified; retain all outputs")


if __name__ == "__main__":
    if sys.argv[1:2] != ["--observe-pytest"]:
        raise SystemExit("Use --observe-pytest followed by ordinary pytest arguments.")
    raise SystemExit(_observe_pytest())
