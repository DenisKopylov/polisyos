"""Marked complete traces distinguish active memory growth from later deallocation."""

from __future__ import annotations

import importlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."
fixture = importlib.import_module(PREFIX + "test_pilot_analysis")


class ThroughputTraceTests(unittest.TestCase):
    def test_complete_active_window_bins_and_cleanup_are_distinct(self) -> None:
        owner = importlib.import_module(PREFIX + "throughput_trace_analysis")
        scratch = Path.cwd() / ".tmp"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="throughput-trace-", dir=scratch) as name:
            root = Path(name)
            data = root / "concurrency-1"
            data.mkdir()
            con = sqlite3.connect(data / "checkpoint.sqlite")
            con.executescript("""CREATE TABLE work_items(work_id TEXT,status TEXT,finished_at REAL);
                INSERT INTO work_items VALUES('synthetic:one','succeeded',101);
                INSERT INTO work_items VALUES('synthetic:two','succeeded',103);
                INSERT INTO work_items VALUES('synthetic:three','succeeded',104.5);
                CREATE TABLE artifact_provenance(synthetic INTEGER,authority_status TEXT);
                INSERT INTO artifact_provenance VALUES(1,'candidate_only');""")
            con.commit()
            con.close()
            profile = root / "profile-1"
            profile.mkdir()
            rows = [
                {
                    "synthetic": True,
                    "measurement_status": "measured",
                    "completed_work_count_status": "measured",
                    "elapsed_seconds": n,
                    "completed_work_count": [0, 1, 1, 2, 2, 3][n],
                    "summed_rss_bytes": [100, 120, 130, 140, 150, 30][n],
                    "cpu_user_seconds": n,
                    "cpu_system_seconds": 0,
                }
                for n in range(6)
            ]
            (profile / "samples.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
            level_path = root / "concurrency-1-report.json"
            fixture.write(
                level_path,
                {
                    "synthetic": True,
                    "concurrency": 1,
                    "terminal_count": 3,
                    "profile": {
                        "synthetic": True,
                        "sample_count": 6,
                        "monotonic_started_seconds": 100,
                        "hardware_observation": {"logical_cpu_count": 2},
                    },
                },
            )
            result = owner.analyse_trace(level_path)
            fixture._equal(result["sample_count"], 6)
            fixture._equal(result["complete_sample_identity_reconciliation"], "equal")
            fixture._equal(result["active_warm"]["sample_count"], 4)
            fixture._equal(result["active_warm"]["rss_slope_bytes_per_second"], 10.0)
            fixture._equal(result["active_warm"]["first_completion_bin"]["rss_mean_bytes"], 125.0)
            fixture._equal(result["active_warm"]["last_completion_bin"]["rss_mean_bytes"], 145.0)
            if result["warm_through_process_exit"]["rss_slope_bytes_per_second"] >= 0:
                raise AssertionError("synthetic late deallocation was not retained separately")
            fixture._equal(result["long_run_memory_bound_established"], False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
