"""Standard-library behavioral checks for P41 checkout-root leases."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import pytest

POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]
HARNESS_PATH = (
    POLICY_ENGINE_ROOT
    / "docs/plans/active/agent-packages/PolicyOS_E02R2/BASELINE_HARNESS.py"
)
SPEC = importlib.util.spec_from_file_location("checkout_lease_harness", HARNESS_PATH)
assert SPEC is not None and SPEC.loader is not None
HARNESS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = HARNESS
SPEC.loader.exec_module(HARNESS)


def _root(path: Path) -> str:
    return str((path / "policy-engine").resolve())


def _job(revision_key: str, path: str = "policy-engine/tests/unit/example.py"):
    return HARNESS.Job(revision_key, path, "0" * 40, 10, "synthetic", False)


def _profile() -> dict[str, object]:
    return {
        "elapsed_seconds": 30,
        "peak_process_group_rss_kib": 100_000,
        "peak_process_group_cpu_percent_sum": 50.0,
        "swap_growth_bytes": 0,
    }


def _snapshot(active: dict[int, dict[str, object]]) -> dict[str, object]:
    rss = {str(pid): 100_000 for pid in active}
    return {
        "active_process_group_count": len(active),
        "aggregate_process_group_rss_kib_sum": 100_000 * len(active),
        "aggregate_process_group_cpu_percent_sum": 50.0 * len(active),
        "aggregate_process_group_rss_by_group_kib": rss,
        "system_memory_free_percent": 65,
        "system_memory_total_bytes": 64 * 1024**3,
        "scratch_volume_free_bytes": 16 * 1024**3,
    }


class CheckoutRootAdmissionTests(unittest.TestCase):
    def test_worker_registers_its_actual_canonical_product_cwd(self) -> None:
        class ImmediateChild:
            pid = 9901
            returncode = 0

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                return self.returncode

        class CapturingRegistry(dict):
            inserted: dict[str, object] | None = None

            def __setitem__(self, key, value):
                self.inserted = dict(value)
                super().__setitem__(key, value)

        with tempfile.TemporaryDirectory() as tempdir:
            tmp = Path(tempdir)
            checkout = tmp / "checkout"
            revision = {
                "key": "fixture",
                "label": "fixture",
                "commit": "1" * 40,
                "checkout": str(checkout),
            }
            registry = CapturingRegistry()
            child = ImmediateChild()
            sample = {
                "process_group_id": child.pid,
                "process_group_sample_status": "measured",
                "process_group_live_process_count": 0,
                "process_group_cpu_percent_sum": 0.0,
                "process_group_rss_kib_sum": 0,
                "active_process_group_count": 0,
                "aggregate_process_group_cpu_percent_sum": 0.0,
                "aggregate_process_group_rss_kib_sum": 0,
                "aggregate_process_group_rss_by_group_kib": {},
                "system_memory_free_percent": 65,
                "system_memory_total_bytes": 8 * 1024**3,
                "system_swap_used_bytes": 0,
                "scratch_volume_free_bytes": 16 * 1024**3,
            }
            ready = threading.Event()
            job = _job("fixture")
            with (
                mock.patch.object(HARNESS, "_LIVE_PROCESS_GROUPS", registry),
                mock.patch.object(HARNESS, "_machine_admission_block_reason", return_value=None),
                mock.patch.object(HARNESS, "_process_group_fence_state", return_value={"verdict": "CLEAR"}),
                mock.patch.object(HARNESS, "_stop_requested_reason", return_value=None),
                mock.patch.object(HARNESS, "_safe_environment", return_value={"PATH": "/usr/bin"}),
                mock.patch.object(HARNESS, "_child_resource_snapshot", return_value=sample),
                mock.patch.object(HARNESS.subprocess, "Popen", return_value=child),
            ):
                HARNESS._run_job(
                    job,
                    revision,
                    tmp / "run",
                    tmp / "home",
                    tmp,
                    0,
                    ready,
                )
            assert ready.is_set()
            assert registry.inserted is not None
            assert registry.inserted['checkout_root'] == str((checkout / 'policy-engine').resolve())

    def test_profiled_and_unprofiled_helpers_block_same_root_and_allow_other_root(self) -> None:
        root_a = _root(Path("/tmp/p41-checkout-a"))
        root_b = _root(Path("/tmp/p41-checkout-b"))
        job = _job("candidate")
        pilot_group = {
            "checkout_root": root_a,
            "unprofiled_pilot_rss_cap_kib": HARNESS.UNPROFILED_PILOT_MAX_GROUP_RSS_KIB,
            "unprofiled_pilot_cpu_projection_percent": 100.0,
        }
        pilot_active = {7001: pilot_group}
        pilot_snapshot = _snapshot(pilot_active)

        same_reason, same_hard = HARNESS._unprofiled_pilot_admission_reason(
            job, pilot_snapshot, pilot_active, checkout_root=root_a
        )
        assert not same_hard
        assert 'same checkout root' in (same_reason or '')

        other_reason, other_hard = HARNESS._unprofiled_pilot_admission_reason(
            job, pilot_snapshot, pilot_active, checkout_root=root_b
        )
        assert other_reason is None
        assert not other_hard

        reserved_reason, _ = HARNESS._unprofiled_pilot_admission_reason(
            job,
            _snapshot({}),
            {},
            checkout_root=root_b,
            reserved_checkout_roots={root_b},
        )
        assert 'reserved' in (reserved_reason or '')

        active_profile = _profile()
        profiled_active = {
            7002: {
                "checkout_root": root_a,
                "expected_profile": active_profile,
                "exclusive_native": False,
                "resource_exclusive": False,
            }
        }
        profiles = {HARNESS._profile_key(job): _profile()}
        with (
            mock.patch.object(HARNESS, "_LIVE_PROCESS_GROUPS", profiled_active),
            mock.patch.object(HARNESS, "_machine_admission_state", return_value=(_snapshot(profiled_active), None)),
        ):
            blocked = HARNESS._can_admit_profiled_job(
                job,
                profiles,
                Path("/tmp"),
                0,
                checkout_root=root_a,
                reserved_checkout_roots=set(),
            )
            admitted = HARNESS._can_admit_profiled_job(
                job,
                profiles,
                Path("/tmp"),
                0,
                checkout_root=root_b,
                reserved_checkout_roots=set(),
            )
            reserved = HARNESS._can_admit_profiled_job(
                job,
                profiles,
                Path("/tmp"),
                0,
                checkout_root=root_b,
                reserved_checkout_roots={root_b},
            )
        assert not blocked[0]
        assert 'same checkout root' in (blocked[1] or '')
        assert admitted[0], admitted[1]
        assert not reserved[0]
        assert 'reserved' in (reserved[1] or '')

    def test_active_group_without_root_lease_fails_closed(self) -> None:
        reason, hard_block = HARNESS._unprofiled_pilot_admission_reason(
            _job("candidate"), _snapshot({7003: {}}), {7003: {}}, checkout_root="/root/a"
        )
        assert hard_block
        assert 'checkout-root lease' in (reason or '')

        job = _job("candidate")
        active = {
            7004: {
                "expected_profile": _profile(),
                "exclusive_native": False,
                "resource_exclusive": False,
            }
        }
        with (
            mock.patch.object(HARNESS, "_LIVE_PROCESS_GROUPS", active),
            mock.patch.object(HARNESS, "_machine_admission_state", return_value=(_snapshot(active), None)),
        ):
            profiled_reason = HARNESS._can_admit_profiled_job(
                job,
                {HARNESS._profile_key(job): _profile()},
                Path("/tmp"),
                0,
                checkout_root="/root/a",
                reserved_checkout_roots=set(),
            )
        assert not profiled_reason[0]
        assert profiled_reason[2]
        assert 'checkout-root lease' in (profiled_reason[1] or '')


class CheckoutRootSchedulerTests(unittest.TestCase):
    def _measure(
        self,
        tmp: Path,
        checkouts: tuple[Path, ...],
        jobs: list[object],
        *,
        workers: int = 5,
        unprofiled_pilot_groups: int = 0,
    ) -> int:
        active: dict[int, dict[str, object]] = {}
        state_lock = threading.Lock()
        max_active = 0
        next_pid = 9000
        revisions = {
            f"ref{index}": {
                "key": f"ref{index}",
                "label": f"ref{index}",
                "commit": str(index) * 40,
                "checkout": str(checkout),
            }
            for index, checkout in enumerate(checkouts)
        }
        profiles = (
            {}
            if unprofiled_pilot_groups
            else {HARNESS._profile_key(job): _profile() for job in jobs}
        )

        def machine_state(*_args):
            with state_lock:
                return _snapshot(dict(active)), None

        def fake_run(
            job,
            revision,
            _run_dir,
            _home,
            _scratch,
            _swap,
            ready,
            expected_profile,
            *,
            unprofiled_pilot_rss_cap_kib=None,
        ):
            nonlocal max_active, next_pid
            root = str((Path(revision["checkout"]) / "policy-engine").resolve())
            with state_lock:
                pid = next_pid
                next_pid += 1
                active[pid] = {
                    "checkout_root": root,
                    "expected_profile": expected_profile or _profile(),
                    "exclusive_native": job.exclusive_native,
                    "resource_exclusive": job.test_path in HARNESS.RESOURCE_EXCLUSIVE_TEST_PATHS,
                    "unprofiled_pilot_rss_cap_kib": unprofiled_pilot_rss_cap_kib,
                    "unprofiled_pilot_cpu_projection_percent": (
                        100.0 if unprofiled_pilot_rss_cap_kib is not None else None
                    ),
                }
                max_active = max(max_active, len(active))
                ready.set()
            time.sleep(0.08)
            with state_lock:
                active.pop(pid)
            return {
                "revision_key": job.revision_key,
                "test_path": job.test_path,
                "test_blob_oid": job.test_blob_oid,
                "cell_presence": "PRESENT",
                "suite_status": "passed",
                "elapsed_seconds": 30,
                "exclusive_native": job.exclusive_native,
                "resource_exclusive": job.test_path in HARNESS.RESOURCE_EXCLUSIVE_TEST_PATHS,
                "resource_guard": None,
                "worker_error": None,
                "process_group_verification_required": False,
                "resource_group_live_after_exit": False,
                "resource_metrics": (
                    None
                    if unprofiled_pilot_rss_cap_kib is not None
                    else {
                        "peak_process_group_rss_kib_sum": 100_000,
                        "peak_process_group_cpu_percent_sum": 50.0,
                        "swap_growth_bytes": 0,
                        "initial_process_group_sample_measured": True,
                    }
                ),
            }

        with (
            mock.patch.object(HARNESS, "_LIVE_PROCESS_GROUPS", active),
            mock.patch.object(HARNESS, "_PROCESS_GROUPS_LOCK", state_lock),
            mock.patch.object(HARNESS, "_machine_admission_state", side_effect=machine_state),
            mock.patch.object(HARNESS, "_run_job", side_effect=fake_run),
            mock.patch.object(HARNESS, "_stop_requested_reason", return_value=None),
            mock.patch.object(HARNESS, "PROCESS_GROUP_LAUNCH_STAGGER_SECONDS", 0.0),
        ):
            HARNESS._SCHEDULER_HALT_REASON = None
            HARNESS._schedule(
                jobs,
                revisions,
                tmp / "run",
                tmp / "home",
                tmp,
                0,
                workers=workers,
                light_profiles=profiles,
                unprofiled_pilot_groups=unprofiled_pilot_groups,
            )
        return max_active

    def test_five_worker_scheduler_serializes_same_root_and_runs_distinct_roots_in_parallel(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            tmp = Path(tempdir)
            same_root = tmp / "shared"
            same_jobs = [_job("ref0", "policy-engine/tests/unit/one.py"), _job("ref0", "policy-engine/tests/unit/two.py")]
            assert self._measure(tmp, (same_root,), same_jobs) == 1

            distinct_jobs = [_job("ref0"), _job("ref1")]
            assert self._measure(tmp, (tmp / 'one', tmp / 'two'), distinct_jobs) == 2

            same_pilot_jobs = [_job("ref0", "policy-engine/tests/unit/three.py"), _job("ref0", "policy-engine/tests/unit/four.py")]
            assert self._measure(tmp, (same_root,), same_pilot_jobs, unprofiled_pilot_groups=HARNESS.UNPROFILED_PILOT_MAX_GROUPS) == 1
            distinct_pilot_jobs = [_job("ref0"), _job("ref1")]
            assert self._measure(tmp, (tmp / 'pilot-one', tmp / 'pilot-two'), distinct_pilot_jobs, unprofiled_pilot_groups=HARNESS.UNPROFILED_PILOT_MAX_GROUPS) == 2

            exclusive_job = _job("ref0", next(iter(HARNESS.RESOURCE_EXCLUSIVE_TEST_PATHS)))
            ordinary_job = _job("ref1", "policy-engine/tests/unit/ordinary.py")
            assert self._measure(tmp, (tmp / 'heavy', tmp / 'ordinary'), [exclusive_job, ordinary_job]) == 1


class ByproductRetirementTests(unittest.TestCase):
    def _fake_move_command(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        if argv[0] == "du":
            return subprocess.CompletedProcess(argv, 0, "1\tfixture\n", "")
        if argv[0] == "find":
            return subprocess.CompletedProcess(argv, 0, f"{argv[-1]}/sentinel\n", "")
        if argv[0] == "mv":
            shutil.move(argv[1], argv[2])
            return subprocess.CompletedProcess(argv, 0, "", "")
        self.fail(f"unexpected command in mocked mover: {argv[0]}")

    def test_both_movers_block_live_groups_blocked_fences_and_unrun_inspection(self) -> None:
        states = (
            ("active", {7701: {"checkout_root": "/fixture/policy-engine"}}, {"verdict": "CLEAR"}),
            ("pending", {}, {"verdict": "BLOCKED", "pending": [{"target_pgid": 7701}]}),
            ("unrun", {}, {"verdict": "UNRUN", "inspection_error": "fixture failure"}),
            ("inspection_exception", {}, OSError("fixture failure")),
        )
        for mover_name in ("_move_test_byproducts", "_move_completed_byproducts_to_trash"):
            mover = getattr(HARNESS, mover_name)
            for label, active, fence in states:
                with self.subTest(mover=mover_name, state=label), tempfile.TemporaryDirectory() as tempdir:
                    tmp = Path(tempdir)
                    run_dir = tmp / "run"
                    source = run_dir / "cells" / "ref" / "case.tmp"
                    source.mkdir(parents=True)
                    (source / "sentinel").write_text("fixture\n", encoding="utf-8")
                    byproduct_root = tmp / "byproducts" / "run-id"
                    byproduct = byproduct_root / "ref" / "case.tmp"
                    byproduct.mkdir(parents=True)
                    (byproduct / "sentinel").write_text("fixture\n", encoding="utf-8")
                    package_raw = tmp / "package-raw"
                    package_raw.mkdir()
                    fake_home = tmp / "home"
                    fence_patch = (
                        mock.patch.object(HARNESS, "_process_group_fence_state", side_effect=fence)
                        if isinstance(fence, BaseException)
                        else mock.patch.object(HARNESS, "_process_group_fence_state", return_value=fence)
                    )
                    if mover_name == '_move_test_byproducts':
                        mover_args = (run_dir, tmp / 'scratch', 'run-id')
                    else:
                        mover_args = (byproduct_root, 'run-id', package_raw)
                    with mock.patch.object(HARNESS, '_LIVE_PROCESS_GROUPS', active), mock.patch.object(HARNESS, '_PROCESS_GROUPS_LOCK', threading.Lock()), fence_patch, mock.patch.object(HARNESS, '_run', side_effect=self._fake_move_command), mock.patch.object(HARNESS.Path, 'home', return_value=fake_home), pytest.raises(RuntimeError, match='retirement'):
                        mover(*mover_args)
                    if mover_name == "_move_test_byproducts":
                        assert source.exists(), 'source byproduct moved despite blocked retirement'
                        assert not (tmp / 'scratch' / 'byproducts' / 'run-id').exists()
                    else:
                        assert byproduct.exists(), 'byproduct root moved despite blocked retirement'
                        assert not (fake_home / '.Trash' / 'e02-r2-run-id-byproducts').exists()
                        assert list(package_raw.iterdir()) == []

    def test_clear_fence_allows_safe_scratch_move_and_mocked_trash_mv(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            tmp = Path(tempdir)
            run_dir = tmp / "run"
            source = run_dir / "cells" / "ref" / "case.tmp"
            source.mkdir(parents=True)
            (source / "sentinel").write_text("fixture\n", encoding="utf-8")
            scratch_root = tmp / "scratch"
            package_raw = tmp / "package-raw"
            package_raw.mkdir()
            fake_home = tmp / "home"
            with (
                mock.patch.object(HARNESS, "_LIVE_PROCESS_GROUPS", {}),
                mock.patch.object(HARNESS, "_PROCESS_GROUPS_LOCK", threading.Lock()),
                mock.patch.object(HARNESS, "_process_group_fence_state", return_value={"verdict": "CLEAR"}),
                mock.patch.object(HARNESS, "_run", side_effect=self._fake_move_command),
                mock.patch.object(HARNESS.Path, "home", return_value=fake_home),
            ):
                moved_root = HARNESS._move_test_byproducts(run_dir, scratch_root, "run-id")
                result = HARNESS._move_completed_byproducts_to_trash(
                    moved_root,
                    "run-id",
                    package_raw,
                )
            trash_root = fake_home / ".Trash" / "e02-r2-run-id-byproducts"
            assert not source.exists()
            assert trash_root.exists()
            assert result['directory_count'] == 1
            assert result['path'] == str(trash_root)
            assert (package_raw / 'p41-trash-moves-run-id.json').is_file()


if __name__ == "__main__":
    unittest.main()
