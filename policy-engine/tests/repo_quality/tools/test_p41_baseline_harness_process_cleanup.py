"""Behavioral coverage for P41 process-group cleanup failures."""

from __future__ import annotations

import errno
import importlib.util
import json
import signal
import subprocess
import sys
import threading
import time
from functools import lru_cache
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HARNESS_PATH = (
    REPO_ROOT / "docs/plans/active/agent-packages/PolicyOS_E02R2/BASELINE_HARNESS.py"
)


@lru_cache(maxsize=1)
def _harness() -> ModuleType:
    assert HARNESS_PATH.is_file()
    spec = importlib.util.spec_from_file_location("e02r2_baseline_harness_under_test", HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeProcess:
    pid = 48291

    def __init__(self, *, terminate: bool = True) -> None:
        self.returncode: int | None = None
        self.terminate = terminate
        self.wait_calls = 0

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if not self.terminate:
            raise subprocess.TimeoutExpired("pytest", timeout)
        self.returncode = -signal.SIGTERM
        return self.returncode


def _sample(*, live: bool) -> dict[str, object]:
    return {
        "process_group_id": _FakeProcess.pid,
        "process_group_sample_status": "measured",
        "process_group_live_process_count": 1 if live else 0,
        "process_group_cpu_percent_sum": 0.0,
        "process_group_rss_kib_sum": 1024 if live else 0,
        "active_process_group_count": 1 if live else 0,
        "aggregate_process_group_cpu_percent_sum": 0,
        "aggregate_process_group_rss_kib_sum": 1024 if live else 0,
        "aggregate_process_group_rss_by_group_kib": {},
        "system_memory_free_percent": 65,
        "system_memory_total_bytes": 8 * 1024**3,
        "system_swap_used_bytes": 0,
        "scratch_volume_free_bytes": 15 * 1024**3,
    }


def _run_job(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    process: _FakeProcess,
    *,
    registry: dict[int, dict[str, object]] | None = None,
    ready_event: threading.Event | None = None,
    fence_dir: Path | None = None,
    reported_group_live: bool | None = None,
):
    harness = _harness()
    monkeypatch.setattr(harness, "_machine_admission_block_reason", lambda *_: None)
    monkeypatch.setattr(harness, "_stop_requested_reason", lambda: None)
    monkeypatch.setattr(harness, "_safe_environment", lambda *_: {"PATH": "/usr/bin"})
    monkeypatch.setattr(
        harness,
        "_child_resource_snapshot",
        lambda child, _scratch: _sample(live=child.poll() is None),
    )
    if reported_group_live is not None:
        monkeypatch.setattr(
            harness,
            "_child_resource_snapshot",
            lambda _child, _scratch: _sample(live=reported_group_live),
        )
    monkeypatch.setattr(harness.subprocess, "Popen", lambda *_a, **_kw: process)
    monkeypatch.setattr(harness, "_LIVE_PROCESS_GROUPS", registry if registry is not None else {})
    monkeypatch.setattr(
        harness,
        "PROCESS_GROUP_FENCE_DIR",
        fence_dir if fence_dir is not None else tmp_path / "process-group-fences",
    )
    monkeypatch.setattr(
        harness,
        "PROCESS_GROUP_FENCE_FAILURE_DIR",
        tmp_path / "process-group-fence-failures",
    )
    monkeypatch.setattr(
        harness,
        "PROCESS_GROUP_FENCE_LEGACY_FAILURE_PATH",
        tmp_path / "legacy-process-group-fence-failure.flag",
    )
    harness._SCHEDULER_HALT_REASON = None
    job = harness.Job(
        revision_key="fixture",
        test_path="policy-engine/tests/unit/example.py",
        test_blob_oid="0" * 40,
        timeout_seconds=0,
        timeout_basis="test forces the timeout branch",
        exclusive_native=False,
    )
    revision = {
        "key": "fixture",
        "label": "fixture",
        "commit": "1" * 40,
        "checkout": str(tmp_path / "checkout"),
    }
    return harness._run_job(
        job,
        revision,
        tmp_path / "run",
        tmp_path / "home",
        tmp_path,
        0,
        ready_event,
    )


def test_eperm_timeout_is_typed_unrun_and_preserves_process_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness = _harness()
    process = _FakeProcess(terminate=False)
    attempted: list[tuple[int, int]] = []

    def deny_signal(pgid: int, sig: int) -> None:
        attempted.append((pgid, sig))
        raise PermissionError(errno.EPERM, "permission denied by test")

    monkeypatch.setattr(harness.os, "killpg", deny_signal)
    row = _run_job(monkeypatch, tmp_path, process)

    assert attempted == [(process.pid, signal.SIGTERM)]
    assert row["suite_status"] == "UNRUN"
    assert row["timed_out"] is True
    assert isinstance(row["elapsed_seconds"], float)
    assert row["returncode"] is None
    assert row["process_status_at_worker_return"] == "running"
    assert row["resource_guard_code"] == "process_group_termination_unverified"
    assert row["process_group_verification_required"] is True
    assert row["process_group_termination"]["error_number"] == errno.EPERM
    assert row["process_group_termination"]["group_state"] == "unknown_signal_denied"
    assert row["artifacts"]["junit"]["sha256"] is None


def test_esrch_is_recorded_as_absent_group_not_permission_denial(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = _harness()
    process = _FakeProcess()

    def no_group(_pgid: int, _sig: int) -> None:
        raise ProcessLookupError(errno.ESRCH, "no process group")

    monkeypatch.setattr(harness.os, "killpg", no_group)
    outcome = harness._terminate_process_group(process)

    assert outcome["status"] == "group_not_found"
    assert outcome["error_number"] == errno.ESRCH
    assert outcome["group_state"] == "absent_at_signal_attempt"
    assert outcome["status"] != "permission_denied"


def test_normal_timeout_still_sends_term_and_reaps_without_unverified_guard(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness = _harness()
    process = _FakeProcess()
    attempted: list[tuple[int, int]] = []
    monkeypatch.setattr(
        harness.os,
        "killpg",
        lambda pgid, sig: attempted.append((pgid, sig)),
    )

    row = _run_job(monkeypatch, tmp_path, process)

    assert attempted == [(process.pid, signal.SIGTERM)]
    assert row["suite_status"] == "UNRUN"
    assert row["timed_out"] is True
    assert row["returncode"] == -signal.SIGTERM
    assert row["process_status_at_worker_return"] == "exited"
    assert row["resource_guard"] is None
    assert row["process_group_verification_required"] is False
    assert (
        row["process_group_termination"]["group_state"]
        == "no_live_members_observed_at_final_sample"
    )


def test_scheduler_pauses_after_cleanup_requires_owner_verification(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness = _harness()
    harness._SCHEDULER_HALT_REASON = None
    monkeypatch.setattr(harness, "_stop_requested_reason", lambda: None)
    monkeypatch.setattr(harness, "_machine_admission_state", lambda *_: ({}, None))
    calls: list[str] = []

    def cleanup_unverified(job, _revision, _run, _home, _scratch, _swap, ready, _profile):
        ready.set()
        calls.append(job.test_path)
        return {
            "revision_key": job.revision_key,
            "test_path": job.test_path,
            "suite_status": "UNRUN",
            "resource_guard": None,
            "process_group_verification_required": True,
            "worker_error": None,
        }

    monkeypatch.setattr(harness, "_run_job", cleanup_unverified)
    jobs = [
        harness.Job("fixture", f"policy-engine/tests/unit/{name}.py", "0" * 40, 1, "test", False)
        for name in ("first", "second")
    ]
    revision = {
        "key": "fixture",
        "label": "fixture",
        "commit": "1" * 40,
        "checkout": str(tmp_path / "checkout"),
    }

    rows = harness._schedule(
        jobs,
        {"fixture": revision},
        tmp_path / "run",
        tmp_path / "home",
        tmp_path,
        0,
        workers=1,
    )

    assert calls == [jobs[0].test_path]
    assert rows[0]["process_group_verification_required"] is True
    assert rows[1]["suite_status"] == "UNRUN"
    assert "owner must verify" in rows[1]["resource_guard"]


class _RegistrationFails(dict[int, dict[str, object]]):
    def __setitem__(self, _key: int, _value: dict[str, object]) -> None:
        raise MemoryError("injected process registry admission failure")


def _pending_event(harness: ModuleType, *, fence_id: str = "fence-test", pgid: int = 48291) -> None:
    harness._append_process_group_fence_event(
        {
            "event": "pending_verification",
            "fence_id": fence_id,
            "target_pgid": pgid,
            "run_id": "prior-run",
            "revision_key": "main",
            "test_path": "policy-engine/tests/unit/example.py",
            "trigger": "permission_denied",
            "error_number": errno.EPERM,
            "leader_returncode": None,
        }
    )


def test_registration_failure_plus_eperm_returns_unrun_and_persists_fence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness = _harness()
    fence_dir = tmp_path / "fences"
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_DIR", fence_dir)
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_FAILURE_DIR", tmp_path / "fence-failures")
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_LEGACY_FAILURE_PATH", tmp_path / "legacy-fence.flag")
    process = _FakeProcess(terminate=False)
    ready = threading.Event()

    def deny_signal(pgid: int, sig: int) -> None:
        raise PermissionError(errno.EPERM, "injected process-group denial")

    monkeypatch.setattr(harness.os, "killpg", deny_signal)
    row = _run_job(
        monkeypatch,
        tmp_path,
        process,
        registry=_RegistrationFails(),
        ready_event=ready,
        fence_dir=fence_dir,
    )

    assert ready.is_set()
    assert row["suite_status"] == "UNRUN"
    assert row["process_group_registered"] is False
    assert row["process_group_verification_required"] is True
    assert row["resource_guard_code"] == "process_group_termination_unverified"
    events = [json.loads(path.read_text()) for path in fence_dir.glob("pending-*.json")]
    assert len(events) == 1
    assert events[0]["event"] == "pending_verification"
    assert events[0]["target_pgid"] == process.pid


def test_restart_fence_blocks_before_subprocess_and_checkpoint_reuse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness = _harness()
    fence_dir = tmp_path / "fences"
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_DIR", fence_dir)
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_FAILURE_DIR", tmp_path / "fence-failures")
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_LEGACY_FAILURE_PATH", tmp_path / "legacy-fence.flag")

    # First invocation enters its matrix runner and hits an uncertain timeout.
    # The worker must persist its pending group before that invocation releases
    # the admission lock.
    first_process = _FakeProcess(terminate=False)
    first_rows: list[dict[str, object]] = []

    def first_matrix(_args) -> int:
        row = _run_job(
            monkeypatch,
            tmp_path,
            first_process,
            fence_dir=fence_dir,
        )
        first_rows.append(row)
        return 2

    monkeypatch.setattr(harness, "run_matrix", first_matrix)
    monkeypatch.setattr(
        harness.os,
        "killpg",
        lambda _pgid, _sig: (_ for _ in ()).throw(
            PermissionError(errno.EPERM, "injected first-invocation denial")
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(HARNESS_PATH),
            "--run",
            "--test-file",
            "policy-engine/tests/unit/runtime/http/test_control_service_di.py",
            "--scratch-root",
            str(tmp_path / "scratch"),
        ],
    )
    first_exit_code = harness.main()

    assert first_exit_code == 2
    assert len(first_rows) == 1
    assert first_rows[0]["process_group_verification_required"] is True
    first_fence_state = harness._process_group_fence_state()
    assert first_fence_state["verdict"] == "BLOCKED"
    assert len(first_fence_state["pending"]) == 1
    first_fence_id = first_fence_state["pending"][0]["fence_id"]

    # A fresh module instance proves the gate reads the durable journal instead
    # of depending on this process's in-memory scheduler or registry state.
    spec = importlib.util.spec_from_file_location(
        "e02r2_baseline_harness_restart_test", HARNESS_PATH
    )
    assert spec is not None and spec.loader is not None
    restarted = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = restarted
    spec.loader.exec_module(restarted)
    monkeypatch.setattr(restarted, "PROCESS_GROUP_FENCE_DIR", fence_dir)
    monkeypatch.setattr(restarted, "PROCESS_GROUP_FENCE_FAILURE_DIR", tmp_path / "fence-failures")
    monkeypatch.setattr(restarted, "PROCESS_GROUP_FENCE_LEGACY_FAILURE_PATH", tmp_path / "legacy-fence.flag")

    def unexpected_external_process(*_args, **_kwargs):
        raise AssertionError("the restart admission gate reached a subprocess")

    def unexpected_reuse(*_args, **_kwargs):
        raise AssertionError("checkpoint reuse must not clear or bypass a pending fence")

    monkeypatch.setattr(restarted, "_run", unexpected_external_process)
    monkeypatch.setattr(restarted, "_verified_reuse_rows", unexpected_reuse)
    monkeypatch.setattr(restarted.subprocess, "Popen", unexpected_external_process)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(HARNESS_PATH),
            "--run",
            "--test-file",
            "policy-engine/tests/unit/runtime/http/test_control_service_di.py",
            "--resume-run",
            str(tmp_path / "completed-checkpoint"),
            "--scratch-root",
            str(tmp_path / "scratch"),
        ],
    )

    exit_code = restarted.main()

    assert exit_code == 2
    receipts = list((tmp_path / "scratch").glob("p41-admission-unrun-*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text())
    assert receipt["verdict"] == "UNRUN"
    assert receipt["failure_stage"] == "process_group_fence_admission"
    assert receipt["test_process_started"] is False
    assert receipt["pending_process_group_fences"][0]["fence_id"] == first_fence_id
    state = restarted._process_group_fence_state()
    assert state["verdict"] == "BLOCKED"


def test_fallback_fence_marker_can_be_owner_resolved_and_admit_fresh_invocation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness = _harness()
    fence_dir = tmp_path / "fences"
    failure_dir = tmp_path / "fence-failures"
    failure_path = failure_dir / "failure-fallback-write.json"
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_DIR", fence_dir)
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_FAILURE_DIR", failure_dir)
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_LEGACY_FAILURE_PATH", tmp_path / "legacy-fence.flag")
    append_event = harness._append_process_group_fence_event

    def primary_fence_write_failure(_event):
        raise OSError(errno.ENOSPC, "injected primary fence storage failure")

    monkeypatch.setattr(harness, "_append_process_group_fence_event", primary_fence_write_failure)
    persisted = harness._persist_unverified_process_group(
        {
            "event": "pending_verification",
            "fence_id": "fallback-write",
            "target_pgid": 48291,
            "run_id": "first-invocation",
            "revision_key": "main",
            "test_path": "policy-engine/tests/unit/example.py",
            "trigger": "permission_denied",
        }
    )
    assert persisted["persisted"] is True
    assert failure_path.is_file()
    monkeypatch.setattr(harness, "_append_process_group_fence_event", append_event)

    state = harness._process_group_fence_state()
    assert state["verdict"] == "BLOCKED"
    assert state["pending"][0]["fence_id"] == "fallback-write"
    assert state["pending"][0]["target_pgid"] == 48291

    def group_absent(pgid: int, sig: int) -> None:
        assert (pgid, sig) == (48291, 0)
        raise ProcessLookupError(errno.ESRCH, "owner verified exact group absent")

    monkeypatch.setattr(harness.os, "killpg", group_absent)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(HARNESS_PATH),
            "--resolve-process-group-fence",
            "fallback-write",
            "--verified-by",
            "denis",
            "--verification-note",
            "Owner census confirmed the recorded process group is absent.",
        ],
    )
    resolution_exit = harness.main()

    assert resolution_exit == 0
    assert harness._process_group_fence_state()["verdict"] == "CLEAR"

    spec = importlib.util.spec_from_file_location(
        "e02r2_baseline_harness_fallback_restart_test", HARNESS_PATH
    )
    assert spec is not None and spec.loader is not None
    restarted = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = restarted
    spec.loader.exec_module(restarted)
    monkeypatch.setattr(restarted, "PROCESS_GROUP_FENCE_DIR", fence_dir)
    monkeypatch.setattr(restarted, "PROCESS_GROUP_FENCE_FAILURE_DIR", failure_dir)
    monkeypatch.setattr(restarted, "PROCESS_GROUP_FENCE_LEGACY_FAILURE_PATH", tmp_path / "legacy-fence.flag")
    admitted: list[bool] = []
    monkeypatch.setattr(restarted, "run_matrix", lambda _args: admitted.append(True) or 0)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(HARNESS_PATH),
            "--run",
            "--test-file",
            "policy-engine/tests/unit/runtime/http/test_control_service_di.py",
            "--scratch-root",
            str(tmp_path / "fresh-scratch"),
        ],
    )

    fresh_exit = restarted.main()

    assert fresh_exit == 0
    assert admitted == [True]


@pytest.mark.parametrize("blocked_store", ["primary", "fallback"])
def test_scandir_error_returns_unrun_instead_of_false_clear(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, blocked_store: str
) -> None:
    harness = _harness()
    fence_dir = tmp_path / "fences"
    failure_dir = tmp_path / "fence-failures"
    legacy_path = tmp_path / "legacy-fence.flag"
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_DIR", fence_dir)
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_FAILURE_DIR", failure_dir)
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_LEGACY_FAILURE_PATH", legacy_path)

    if blocked_store == "primary":
        _pending_event(harness, fence_id="unreadable-primary")
        denied_dir = fence_dir
    else:
        monkeypatch.setattr(
            harness,
            "_append_process_group_fence_event",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                OSError(errno.ENOSPC, "injected primary journal write failure")
            ),
        )
        fallback = harness._persist_unverified_process_group(
            {
                "event": "pending_verification",
                "fence_id": "unreadable-fallback",
                "target_pgid": 48291,
                "run_id": "prior-run",
                "revision_key": "main",
                "test_path": "policy-engine/tests/unit/example.py",
                "trigger": "permission_denied",
            }
        )
        assert fallback["persisted"] is True
        denied_dir = failure_dir

    real_scandir = harness.os.scandir

    def deny_target_directory(path="."):
        if not isinstance(path, int) and Path(path) == denied_dir:
            raise PermissionError(errno.EACCES, "injected journal enumeration denial", str(path))
        return real_scandir(path)

    monkeypatch.setattr(harness.os, "scandir", deny_target_directory)
    state = harness._process_group_fence_state()

    assert state["verdict"] == "UNRUN"
    assert state["pending"] == []
    assert state["sha256"] is None
    assert state["inspection_error"].startswith("PermissionError:")


def test_pending_record_read_error_is_unrun_even_with_fallback_marker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness = _harness()
    fence_dir = tmp_path / "fences"
    failure_dir = tmp_path / "fence-failures"
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_DIR", fence_dir)
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_FAILURE_DIR", failure_dir)
    monkeypatch.setattr(
        harness,
        "PROCESS_GROUP_FENCE_LEGACY_FAILURE_PATH",
        tmp_path / "legacy-fence.flag",
    )
    append_event = harness._append_process_group_fence_event
    monkeypatch.setattr(
        harness,
        "_append_process_group_fence_event",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError(errno.ENOSPC, "injected primary journal write failure")
        ),
    )
    fallback = harness._persist_unverified_process_group(
        {
            "event": "pending_verification",
            "fence_id": "read-failure",
            "target_pgid": 48291,
            "run_id": "prior-run",
            "revision_key": "main",
            "test_path": "policy-engine/tests/unit/example.py",
            "trigger": "permission_denied",
        }
    )
    assert fallback["persisted"] is True
    monkeypatch.setattr(harness, "_append_process_group_fence_event", append_event)
    pending_path = fence_dir / "pending-read-failure.json"
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    pending_path.write_text("partial record", encoding="utf-8")

    real_read_text = Path.read_text

    def deny_pending_read(path: Path, *args, **kwargs):
        if path == pending_path:
            raise PermissionError(errno.EACCES, "injected journal read denial", str(path))
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", deny_pending_read)
    state = harness._process_group_fence_state()

    assert state["verdict"] == "UNRUN"
    assert state["pending"] == []
    assert state["sha256"] is None
    assert state["inspection_error"].startswith("PermissionError:")


def test_distinct_fallback_write_failures_keep_distinct_pending_pgids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness = _harness()
    fence_dir = tmp_path / "fences"
    failure_dir = tmp_path / "fence-failures"
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_DIR", fence_dir)
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_FAILURE_DIR", failure_dir)
    monkeypatch.setattr(
        harness,
        "PROCESS_GROUP_FENCE_LEGACY_FAILURE_PATH",
        tmp_path / "legacy-fence.flag",
    )
    monkeypatch.setattr(
        harness,
        "_append_process_group_fence_event",
        lambda _event: (_ for _ in ()).throw(OSError(errno.ENOSPC, "injected write failure")),
    )

    for fence_id, pgid in (("fallback-a", 48291), ("fallback-b", 48292)):
        persisted = harness._persist_unverified_process_group(
            {
                "event": "pending_verification",
                "fence_id": fence_id,
                "target_pgid": pgid,
                "run_id": f"run-{fence_id}",
                "trigger": "permission_denied",
            }
        )
        assert persisted["persisted"] is True

    state = harness._process_group_fence_state()

    assert state["verdict"] == "BLOCKED"
    assert {(item["fence_id"], item["target_pgid"]) for item in state["pending"]} == {
        ("fallback-a", 48291),
        ("fallback-b", 48292),
    }
    assert len(list(failure_dir.glob("failure-*.json"))) == 2


def test_legacy_singleton_fallback_marker_can_be_owner_resolved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness = _harness()
    fence_id = "legacy-fallback"
    legacy_path = tmp_path / "legacy-fence.flag"
    failure_dir = tmp_path / "fence-failures"
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_DIR", tmp_path / "fences")
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_FAILURE_DIR", failure_dir)
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_LEGACY_FAILURE_PATH", legacy_path)
    legacy_path.write_text(
        json.dumps(
            {
                "schema": harness.PROCESS_GROUP_FENCE_EVENT_SCHEMA,
                "state": "unidentified_unverified_process_group",
                "fence_id": fence_id,
                "target_pgid": 48293,
                "run_id": "legacy-run",
                "record_error": "primary pending event failed",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def group_absent(pgid: int, sig: int) -> None:
        assert (pgid, sig) == (48293, 0)
        raise ProcessLookupError(errno.ESRCH, "owner verified legacy group absent")

    monkeypatch.setattr(harness.os, "killpg", group_absent)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(HARNESS_PATH),
            "--resolve-process-group-fence",
            fence_id,
            "--verified-by",
            "denis",
            "--verification-note",
            "Owner census confirmed the legacy process group is absent.",
        ],
    )

    exit_code = harness.main()

    assert exit_code == 0
    assert legacy_path.is_file()
    assert harness._process_group_fence_state()["verdict"] == "CLEAR"
    assert (failure_dir / f"verified-{fence_id}.json").is_file()


def test_malformed_fallback_marker_returns_typed_unrun(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness = _harness()
    failure_dir = tmp_path / "fence-failures"
    failure_dir.mkdir()
    (failure_dir / "failure-corrupt.json").write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_FAILURE_DIR", failure_dir)
    monkeypatch.setattr(
        harness,
        "PROCESS_GROUP_FENCE_DIR",
        tmp_path / "fences",
    )
    monkeypatch.setattr(
        harness,
        "PROCESS_GROUP_FENCE_LEGACY_FAILURE_PATH",
        tmp_path / "legacy-fence.flag",
    )

    state = harness._process_group_fence_state()

    assert state["verdict"] == "UNRUN"
    assert "not an object" in state["inspection_error"]


def test_removing_startup_gate_reaches_subprocess_with_pending_marker_retained(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness = _harness()
    fence_dir = tmp_path / "fences"
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_DIR", fence_dir)
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_FAILURE_DIR", tmp_path / "fence-failures")
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_LEGACY_FAILURE_PATH", tmp_path / "legacy-fence.flag")
    _pending_event(harness)

    class RemovalProbeReachedProcessBoundaryError(RuntimeError):
        pass

    # Simulate removal of the admission property while keeping the durable marker.
    monkeypatch.setattr(
        harness,
        "_process_group_fence_state",
        lambda *_args, **_kwargs: {"verdict": "CLEAR", "pending": [], "sha256": None},
    )
    monkeypatch.setattr(
        harness,
        "_run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RemovalProbeReachedProcessBoundaryError()),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(HARNESS_PATH),
            "--run",
            "--test-file",
            "policy-engine/tests/unit/runtime/http/test_control_service_di.py",
            "--scratch-root",
            str(tmp_path / "scratch"),
        ],
    )

    with pytest.raises(RemovalProbeReachedProcessBoundaryError):
        harness.main()
    pending_paths = list(fence_dir.glob("pending-*.json"))
    assert len(pending_paths) == 1
    assert json.loads(pending_paths[0].read_text())["fence_id"] == "fence-test"


def test_owner_resolution_requires_exact_fence_and_observed_absent_group(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness = _harness()
    fence_dir = tmp_path / "fences"
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_DIR", fence_dir)
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_FAILURE_DIR", tmp_path / "fence-failures")
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_LEGACY_FAILURE_PATH", tmp_path / "legacy-fence.flag")
    _pending_event(harness)
    attempted: list[tuple[int, int]] = []

    def absent_group(pgid: int, sig: int) -> None:
        attempted.append((pgid, sig))
        raise ProcessLookupError(errno.ESRCH, "the recorded process group is absent")

    monkeypatch.setattr(harness.os, "killpg", absent_group)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(HARNESS_PATH),
            "--resolve-process-group-fence",
            "fence-test",
            "--verified-by",
            "denis",
            "--verification-note",
            "Independent process-group absence check completed.",
        ],
    )
    exit_code = harness.main()

    assert attempted == [(48291, 0)]
    assert exit_code == 0
    state = harness._process_group_fence_state()
    assert state["verdict"] == "CLEAR"
    events = [json.loads(path.read_text()) for path in sorted(fence_dir.glob("*.json"))]
    assert [event["event"] for event in events] == [
        "pending_verification",
        "owner_verified_absent",
    ]


@pytest.mark.parametrize(
    "probe",
    [
        pytest.param(lambda _pgid, _sig: None, id="still-live"),
        pytest.param(
            lambda _pgid, _sig: (_ for _ in ()).throw(
                PermissionError(errno.EPERM, "group visibility denied")
            ),
            id="permission-denied",
        ),
    ],
)
def test_owner_resolution_does_not_clear_live_or_inaccessible_group(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, probe
) -> None:
    harness = _harness()
    fence_dir = tmp_path / "fences"
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_DIR", fence_dir)
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_FAILURE_DIR", tmp_path / "fence-failures")
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_LEGACY_FAILURE_PATH", tmp_path / "legacy-fence.flag")
    _pending_event(harness)
    monkeypatch.setattr(harness.os, "killpg", probe)

    blocked = harness._resolve_process_group_fence(
        "fence-test",
        verified_by="denis",
        verification_note="Attempted verification.",
    )

    assert blocked["status"] == "still_present_or_unknown"
    assert harness._process_group_fence_state()["verdict"] == "BLOCKED"
    assert len(list(fence_dir.glob("pending-*.json"))) == 1
    assert not list(fence_dir.glob("verified-*.json"))


def test_observed_orphan_after_reaped_leader_persists_next_invocation_fence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness = _harness()
    fence_dir = tmp_path / "process-group-fences"
    process = _FakeProcess()
    attempted: list[tuple[int, int]] = []
    monkeypatch.setattr(
        harness.os,
        "killpg",
        lambda pgid, sig: attempted.append((pgid, sig)),
    )
    monkeypatch.setattr(
        harness,
        "_observe_orphaned_group",
        lambda *_args, **_kwargs: _sample(live=True),
    )
    monkeypatch.setattr(harness, "PROCESS_GROUP_FENCE_DIR", fence_dir)
    monkeypatch.setattr(
        harness,
        "PROCESS_GROUP_FENCE_FAILURE_DIR",
        tmp_path / "process-group-fence-failures",
    )

    row = _run_job(
        monkeypatch,
        tmp_path,
        process,
        fence_dir=fence_dir,
        reported_group_live=True,
    )

    assert process.poll() is not None
    assert attempted == [(process.pid, signal.SIGTERM)]
    assert row["suite_status"] == "UNRUN"
    assert row["process_group_verification_required"] is True
    assert row["process_group_fence_persisted"] is True
    assert row["process_group_fence_record"]["event"]["trigger"] == (
        "live_members_observed_after_leader_exit"
    )
    assert harness._process_group_fence_state()["verdict"] == "BLOCKED"


def test_reaped_leader_is_never_signaled_by_numeric_pgid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness()
    process = _FakeProcess()
    process.returncode = 0
    attempted: list[tuple[int, int]] = []

    def forbidden_signal(pgid: int, sig: int) -> None:
        attempted.append((pgid, sig))
        raise AssertionError("a reaped leader's potentially reused PGID was signaled")

    monkeypatch.setattr(harness.os, "killpg", forbidden_signal)
    outcome = harness._terminate_process_group(process)

    assert attempted == []
    assert outcome["status"] == "leader_already_exited"
    assert outcome["group_state"] == "unknown_after_leader_exit"


def _pilot_snapshot(
    *,
    active_count: int = 0,
    aggregate_rss_kib: int = 0,
    aggregate_cpu_percent: float = 0,
    group_rss: dict[str, int] | None = None,
    free_memory_percent: int = 75,
    total_memory_bytes: int = 64 * 1024**3,
    disk_free_bytes: int = 16 * 1024**3,
) -> dict[str, object]:
    return {
        "active_process_group_count": active_count,
        "aggregate_process_group_rss_kib_sum": aggregate_rss_kib,
        "aggregate_process_group_cpu_percent_sum": aggregate_cpu_percent,
        "aggregate_process_group_rss_by_group_kib": group_rss or {},
        "system_memory_free_percent": free_memory_percent,
        "system_memory_total_bytes": total_memory_bytes,
        "scratch_volume_free_bytes": disk_free_bytes,
    }


def _pilot_job(
    harness: ModuleType,
    *,
    path: str = "policy-engine/tests/unit/example.py",
    native: bool = False,
):
    return harness.Job("fixture", path, "0" * 40, 10, "synthetic", native)


def test_unprofiled_pilot_admission_projects_rss_and_cpu_without_profile_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _harness()
    reason, hard_block = harness._unprofiled_pilot_admission_reason(
        _pilot_job(harness), _pilot_snapshot(), {}
    )
    assert reason is None
    assert hard_block is False

    pilot_group = {
        "unprofiled_pilot_rss_cap_kib": 2 * 1024**2,
        "unprofiled_pilot_cpu_projection_percent": 200.0,
        "expected_profile": None,
    }
    monkeypatch.setattr(harness, "ADAPTIVE_MAX_BATCH_RSS_KIB", 4_000_000)
    tight_rss = _pilot_snapshot(
        active_count=1,
        aggregate_rss_kib=1_800_000,
        aggregate_cpu_percent=0,
        group_rss={"7001": 1_800_000},
    )
    reason, _ = harness._unprofiled_pilot_admission_reason(
        _pilot_job(harness), tight_rss, {7001: pilot_group}
    )
    assert reason is not None and "projected active pytest RSS" in reason

    tight_cpu = _pilot_snapshot(aggregate_cpu_percent=501)
    reason, _ = harness._unprofiled_pilot_admission_reason(
        _pilot_job(harness), tight_cpu, {}
    )
    assert reason is not None and "projected active pytest CPU" in reason

    tight_memory = _pilot_snapshot(
        free_memory_percent=35,
        total_memory_bytes=32 * 1024**3,
    )
    reason, _ = harness._unprofiled_pilot_admission_reason(
        _pilot_job(harness), tight_memory, {}
    )
    assert reason is not None and "hard memory reserve" in reason

    tight_disk = _pilot_snapshot(disk_free_bytes=8 * 1024**3 - 1)
    reason, _ = harness._unprofiled_pilot_admission_reason(
        _pilot_job(harness), tight_disk, {}
    )
    assert reason is not None and "scratch free-space floor" in reason

    two_active_pilots = {7001: pilot_group, 7002: pilot_group}
    reason, _ = harness._unprofiled_pilot_admission_reason(
        _pilot_job(harness),
        _pilot_snapshot(
            active_count=2,
            aggregate_rss_kib=2_000_000,
            aggregate_cpu_percent=100,
            group_rss={"7001": 1_000_000, "7002": 1_000_000},
        ),
        two_active_pilots,
    )
    assert reason is not None and "two-group pilot limit" in reason

    assert harness._measured_light_profiles([]) == {}


def test_unprofiled_pilot_never_admits_native_or_resource_exclusive_jobs() -> None:
    harness = _harness()
    ordinary_snapshot = _pilot_snapshot()
    reason, _ = harness._unprofiled_pilot_admission_reason(
        _pilot_job(harness, native=True), ordinary_snapshot, {}
    )
    assert reason is not None and "native or resource-exclusive" in reason

    for resource_exclusive in harness.RESOURCE_EXCLUSIVE_TEST_PATHS:
        reason, _ = harness._unprofiled_pilot_admission_reason(
            _pilot_job(harness, path=resource_exclusive), ordinary_snapshot, {}
        )
        assert reason is not None and "native or resource-exclusive" in reason


def test_scheduler_default_keeps_unknown_jobs_serial_and_opt_in_caps_at_two(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    harness = _harness()
    harness._SCHEDULER_HALT_REASON = None
    monkeypatch.setattr(harness, "_stop_requested_reason", lambda: None)
    monkeypatch.setattr(
        harness,
        "_machine_admission_state",
        lambda *_: (_pilot_snapshot(), None),
    )
    monkeypatch.setattr(
        harness,
        "_can_admit_unprofiled_pilot_job",
        lambda *_: (True, None, False),
    )
    jobs = [
        _pilot_job(harness, path=f"policy-engine/tests/unit/item_{index}.py")
        for index in range(3)
    ]
    revision = {
        "key": "fixture",
        "label": "fixture",
        "commit": "1" * 40,
        "checkout": str(tmp_path / "checkout"),
    }

    def measure_max_active(
        unprofiled_pilot_groups: int,
        *,
        measured_heavy: bool = False,
    ) -> tuple[int, dict[tuple[str, str, str], dict[str, object]]]:
        lock = threading.Lock()
        active = 0
        max_active = 0

        def fake_run(
            job,
            _revision,
            _run,
            _home,
            _scratch,
            _swap,
            ready,
            _profile,
            *,
            unprofiled_pilot_rss_cap_kib=None,
        ):
            nonlocal active, max_active
            ready.set()
            with lock:
                active += 1
                max_active = max(max_active, active)
            if unprofiled_pilot_rss_cap_kib is not None:
                time.sleep(0.65)
            else:
                time.sleep(0.01)
            with lock:
                active -= 1
            return {
                "revision_key": job.revision_key,
                "test_path": job.test_path,
                "suite_status": "passed",
                "resource_guard": None,
                "worker_error": None,
                "process_group_verification_required": False,
                "resource_group_live_after_exit": False,
            }

        monkeypatch.setattr(harness, "_run_job", fake_run)
        profiles: dict[tuple[str, str, str], dict[str, object]] = (
            {
                harness._profile_key(job): {
                    "elapsed_seconds": 61,
                    "peak_process_group_rss_kib": 3 * 1024**2,
                    "peak_process_group_cpu_percent_sum": 250.0,
                    "swap_growth_bytes": 0,
                }
                for job in jobs
            }
            if measured_heavy
            else {}
        )
        harness._schedule(
            jobs,
            {"fixture": revision},
            tmp_path / "run",
            tmp_path / "home",
            tmp_path,
            0,
            workers=5 if unprofiled_pilot_groups == 2 else 2,
            light_profiles=profiles,
            unprofiled_pilot_groups=unprofiled_pilot_groups,
        )
        return max_active, profiles

    default_max, default_profiles = measure_max_active(0)
    assert default_max == 1
    assert default_profiles == {}

    pilot_max, pilot_profiles = measure_max_active(2)
    assert pilot_max == 2
    assert pilot_profiles == {}

    heavy_max, _ = measure_max_active(2, measured_heavy=True)
    assert heavy_max == 1
