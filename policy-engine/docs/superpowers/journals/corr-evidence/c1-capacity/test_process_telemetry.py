"""Real process/child telemetry and removal witnesses for the bounded C1 observer."""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE = "docs.superpowers.journals.corr-evidence.c1-capacity"
MODULE = PACKAGE + ".process_telemetry"
FIXTURE = PACKAGE + ".telemetry_fixture"
ROOT = Path(__file__).resolve().parents[5]


def _check(value: object, message: str = "semantic_condition_failed") -> None:
    if not value:
        raise AssertionError(message)


class ProcessTelemetryTests(unittest.TestCase):
    """Deleting real counters or descendant aggregation must break these assertions."""

    def setUp(self) -> None:
        _check(importlib.util.find_spec(MODULE) is not None, "process_telemetry_owner_missing")
        self.owner = importlib.import_module(MODULE)
        scratch = ROOT / ".tmp"
        scratch.mkdir(exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix="corr-telemetry-test-", dir=scratch)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_real_descendant_cpu_disk_memory_and_checkpoint(self) -> None:
        """Child-only real work is visible in aggregate and independently measured."""
        checkpoint = self.root / "work.sqlite"
        with sqlite3.connect(checkpoint) as con:
            con.execute(
                "CREATE TABLE work_items (id TEXT PRIMARY KEY, status TEXT, "
                "synthetic BOOLEAN DEFAULT TRUE)"
            )
        summary = self.owner.profile_module(
            FIXTURE,
            ["--root", str(self.root), "--private-note", "SYNTHETIC_SECRET_SENTINEL"],
            cwd=ROOT,
            output_root=self.root / "observed",
            limits=self.owner.ProfileLimits(max_wall_seconds=20),
            completion_reader=self.owner.sqlite_completion_reader(
                checkpoint, terminal_statuses=("completed",)
            ),
            synthetic=True,
        )
        independent = json.loads((self.root / "child-observed.json").read_text())
        sys.stdout.write(
            json.dumps({"synthetic": True, "observed": summary, "independent_child": independent})
            + "\n"
        )
        _check(summary["status"] == "completed", "summary['status'] == 'completed'")
        _check(summary["returncode"] == 0, "summary['returncode'] == 0")
        _check(summary["monotonic_started_seconds"] > 0, "monotonic origin absent")
        hardware = summary["hardware_observation"]
        _check(hardware["logical_cpu_count"] > 0, "logical CPU denominator absent")
        _check(hardware["physical_memory_bytes"] > 0, "physical RAM denominator absent")
        _check(summary["worker_cpu_capacity_fraction"] > 0, "CPU capacity fraction absent")
        _check(summary["peak_worker_rss_physical_memory_fraction"] > 0,
               "observed RSS fraction absent")
        _check(
            independent["native_user_seconds_delta"] > 0.2,
            "independent['native_user_seconds_delta'] > 0.2",
        )
        _check(
            independent["resource_user_seconds_delta"] > 0.2,
            "independent['resource_user_seconds_delta'] > 0.2",
        )
        _check(
            abs(
                independent["native_user_seconds_delta"]
                - independent["resource_user_seconds_delta"]
            )
            <= 0.06
        )
        _check(
            independent["disk_write_bytes_delta"] > 0, "independent['disk_write_bytes_delta'] > 0"
        )
        _check(independent["disk_read_bytes_delta"] > 0, "independent['disk_read_bytes_delta'] > 0")
        _check(independent["file_hash_equal"], "independent['file_hash_equal']")
        _check(
            independent["file_bytes"] == 32 * 1024 * 1024,
            "independent['file_bytes'] == 32 * 1024 * 1024",
        )
        _check(summary["cpu_user_seconds"] >= independent["native_user_seconds_delta"])
        _check(
            summary["disk_write_bytes"] >= independent["disk_write_bytes_delta"],
            "summary['disk_write_bytes'] >= independent['disk_write_bytes_delta']",
        )
        _check(
            summary["disk_read_bytes"] >= independent["disk_read_bytes_delta"],
            "summary['disk_read_bytes'] >= independent['disk_read_bytes_delta']",
        )
        _check(
            summary["peak_summed_rss_bytes"] >= 32 * 1024 * 1024,
            "summary['peak_summed_rss_bytes'] >= 32 * 1024 * 1024",
        )
        _check(summary["max_descendant_count"] >= 1, "summary['max_descendant_count'] >= 1")
        _check(summary["completed_work_count"] == 3, "summary['completed_work_count'] == 3")
        _check(
            summary["completed_work_count_status"] == "measured",
            "summary['completed_work_count_status'] == 'measured'",
        )
        _check(summary["observer_cpu_seconds"] > 0, "summary['observer_cpu_seconds'] > 0")
        _check(
            summary["observer_scope"] == "excluded_from_worker_tree",
            "summary['observer_scope'] == 'excluded_from_worker_tree'",
        )
        samples_text = (self.root / "observed" / "samples.jsonl").read_text()
        _check(
            "SYNTHETIC_SECRET_SENTINEL" not in samples_text + json.dumps(summary),
            "'SYNTHETIC_SECRET_SENTINEL' not in samples_text + json.dumps(summary)",
        )
        samples = [json.loads(line) for line in samples_text.splitlines()]
        _check(
            all(row["synthetic"] is True for row in samples),
            "all((row['synthetic'] is True for row in samples))",
        )
        _check(
            any(row["descendant_count"] > 0 for row in samples),
            "any((row['descendant_count'] > 0 for row in samples))",
        )
        _check(
            any(row["completed_work_count"] == 3 for row in samples),
            "any((row['completed_work_count'] == 3 for row in samples))",
        )
        _check(
            all("argv" not in row and "environ" not in row for row in samples),
            "all(('argv' not in row and 'environ' not in row for row in samples))",
        )

    def test_wall_rss_disk_and_requested_interrupt_stop_owned_group(self) -> None:
        """Caps and interruption act on the launched workload, preserving final samples."""
        cases = (
            ("max_wall_seconds", {"max_wall_seconds": 0.35}, None, "sleep"),
            ("max_rss_bytes", {"max_wall_seconds": 10, "max_rss_bytes": 1}, None, "sleep"),
            (
                "max_disk_write_bytes",
                {"max_wall_seconds": 20, "max_disk_write_bytes": 1},
                None,
                "write",
            ),
            ("interrupted", {"max_wall_seconds": 10}, lambda: True, "sleep"),
        )
        for name, values, callback, mode in cases:
            with self.subTest(name=name):
                output = self.root / name
                started = time.monotonic()
                summary = self.owner.profile_module(
                    FIXTURE,
                    ["--root", str(self.root), "--mode", mode],
                    cwd=ROOT,
                    output_root=output,
                    limits=self.owner.ProfileLimits(**values, shutdown_grace_seconds=0.3),
                    interrupt_requested=callback,
                    synthetic=True,
                )
                _check(summary["status"] == "stopped", "summary['status'] == 'stopped'")
                _check(summary["stop_reason"] == name, "summary['stop_reason'] == name")
                _check(time.monotonic() - started < 8, "time.monotonic() - started < 8")
                _check(summary["returncode"] is not None, "summary['returncode'] is not None")
                _check((output / "samples.jsonl").is_file(), "(output / 'samples.jsonl').is_file()")

    def test_missing_native_process_and_checkpoint_are_ambiguous(self) -> None:
        """Unavailable observations never turn into measured zeros."""
        snapshot = self.owner.read_process_usage(2147483647)
        _check(snapshot["status"] == "ambiguous", "snapshot['status'] == 'ambiguous'")
        _check(snapshot["cpu_user_seconds"] is None, "snapshot['cpu_user_seconds'] is None")
        _check(snapshot["disk_write_bytes"] is None, "snapshot['disk_write_bytes'] is None")
        reader = self.owner.sqlite_completion_reader(self.root / "absent.sqlite")
        summary = self.owner.profile_module(
            FIXTURE,
            ["--root", str(self.root), "--mode", "brief"],
            cwd=ROOT,
            output_root=self.root / "missing-checkpoint",
            limits=self.owner.ProfileLimits(max_wall_seconds=10),
            completion_reader=reader,
            synthetic=True,
        )
        _check(summary["completed_work_count"] is None, "summary['completed_work_count'] is None")
        _check(
            summary["completed_work_count_status"] == "ambiguous",
            "summary['completed_work_count_status'] == 'ambiguous'",
        )

    def test_observer_failure_terminates_child_and_sanitizes_error(self) -> None:
        """A failed observation cannot leave an unmonitored, potentially paid worker."""
        actual = subprocess.Popen
        processes = []

        def launch(*args: object, **kwargs: object) -> subprocess.Popen:
            process = actual(*args, **kwargs)
            processes.append(process)
            return process

        def cleanup() -> None:
            if processes and processes[0].poll() is None:
                os.killpg(processes[0].pid, signal.SIGKILL)
                processes[0].wait(timeout=3)

        self.addCleanup(cleanup)
        error: Exception | None = None
        with (
            patch.object(self.owner.subprocess, "Popen", launch),
            patch.object(
                self.owner, "_completion", side_effect=OSError("SYNTHETIC_SECRET_SENTINEL")
            ),
        ):
            try:
                self.owner.profile_module(
                    FIXTURE,
                    ["--root", str(self.root), "--mode", "sleep"],
                    cwd=ROOT,
                    output_root=self.root / "broken-observer",
                    limits=self.owner.ProfileLimits(max_wall_seconds=10),
                    synthetic=True,
                )
            except Exception as exc:
                error = exc
        _check(isinstance(error, RuntimeError), "sanitized_exception_class")
        _check(str(error) == "telemetry_observer_failed:OSError", "sanitized_exception_message")
        _check(processes[0].poll() is not None, "processes[0].poll() is not None")


if __name__ == "__main__":
    unittest.main()
