"""Complete-trace descriptive resource analysis; no long-run memory extrapolation."""

from __future__ import annotations

import argparse
import importlib
import json
import math
import sqlite3
import sys
from collections import defaultdict
from contextlib import closing
from pathlib import Path
from typing import Any

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."
analysis = importlib.import_module(PREFIX + "pilot_analysis")


def _number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _within_active(elapsed: float, last_owner_finish: float) -> bool:
    return elapsed <= last_owner_finish


def _metrics(rows: list[tuple], logical_cpus: int | None, terminal_count: int) -> dict[str, Any]:
    by_time, by_work = analysis._Regression(), analysis._Regression()
    bins = defaultdict(list)
    for _, elapsed, rss, completed, _ in rows:
        by_time.add(elapsed, rss)
        by_work.add(completed, rss)
        bins[completed].append((elapsed, rss))
    values = []
    for completed, points in sorted(bins.items()):
        values.append(
            {
                "completed_work_count": completed,
                "sample_count": len(points),
                "first_elapsed_seconds": points[0][0],
                "last_elapsed_seconds": points[-1][0],
                "rss_first_bytes": points[0][1],
                "rss_last_bytes": points[-1][1],
                "rss_min_bytes": min(rss for _, rss in points),
                "rss_max_bytes": max(rss for _, rss in points),
                "rss_mean_bytes": sum(rss for _, rss in points) / len(points),
            }
        )
    cpu_points = [(row[1], row[4]) for row in rows if row[4] is not None]
    span = cpu_points[-1][0] - cpu_points[0][0] if len(cpu_points) >= 2 else 0
    cpu = cpu_points[-1][1] - cpu_points[0][1] if span > 0 else None
    ratio = cpu / span if cpu is not None else None
    return {
        "sample_count": len(rows),
        "rss_slope_bytes_per_second": by_time.slope(),
        "rss_slope_bytes_per_completed": by_work.slope(),
        "completion_bins": values,
        "first_completion_bin": values[0] if values else None,
        "last_completion_bin": values[-1] if values else None,
        "terminal_completion_bin": next(
            (value for value in values if value["completed_work_count"] == terminal_count), None
        ),
        "observed_cpu_sample_count": len(cpu_points),
        "observed_cpu_seconds": cpu,
        "cpu_per_wall_second": ratio,
        "cpu_share_of_logical_capacity": ratio / logical_cpus
        if ratio is not None and logical_cpus
        else None,
    }


def analyse_trace(level_path: Path) -> dict[str, Any]:
    """Reconcile all Python/SQLite JSON sample identities, retaining ambiguous rows."""
    level = analysis._json(level_path)
    profile = level["profile"]
    synthetic = level["synthetic"]
    root = level_path.parent
    concurrency = level["concurrency"]
    trace = root / f"profile-{concurrency}" / "samples.jsonl"
    checkpoint = root / f"concurrency-{concurrency}" / "checkpoint.sqlite"
    with closing(sqlite3.connect(checkpoint.resolve().as_uri() + "?mode=ro", uri=True)) as con:
        rows = con.execute("SELECT work_id,status,finished_at FROM work_items").fetchall()
        count, maximum = con.execute(

                "SELECT COUNT(*),MAX(finished_at) FROM work_items "
                "WHERE status IN ('succeeded','failed')"

        ).fetchone()
    terminal = [
        (identifier, finished)
        for identifier, status, finished in rows
        if status in ("succeeded", "failed")
    ]
    if (
        len({identifier for identifier, _ in terminal}) != count
        or count != level["terminal_count"]
        or max(finished for _, finished in terminal) != maximum
    ):
        raise ValueError("trace_terminal_identity_value_mismatch")
    if not _number(maximum) or not _number(profile["monotonic_started_seconds"]):
        raise ValueError("trace_active_window_not_established")
    active_end = maximum - profile["monotonic_started_seconds"]
    python_values = []
    ambiguous = []
    sample_count = 0
    with closing(sqlite3.connect(":memory:")) as db:
        db.execute("CREATE TABLE samples(ordinal INTEGER PRIMARY KEY,payload TEXT)")
        with trace.open() as stream:
            for index, line in enumerate(stream):
                sample_count += 1
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    value = None
                db.execute(
                    "INSERT INTO samples VALUES(?,?)", (index, line if value is not None else None)
                )
                if not isinstance(value, dict):
                    ambiguous.append(index)
                    continue
                if value.get("synthetic") is not synthetic:
                    raise ValueError("trace_synthetic_provenance_mismatch")
                elapsed, rss, completed = (
                    value.get(key)
                    for key in ("elapsed_seconds", "summed_rss_bytes", "completed_work_count")
                )
                if (
                    value.get("measurement_status") != "measured"
                    or value.get("completed_work_count_status") != "measured"
                    or not _number(elapsed)
                    or not analysis._integer(rss)
                    or not analysis._integer(completed)
                ):
                    ambiguous.append(index)
                    continue
                user, system = value.get("cpu_user_seconds"), value.get("cpu_system_seconds")
                cpu = user + system if _number(user) and _number(system) else None
                python_values.append((index, elapsed, rss, completed, cpu))
        sql_values = db.execute("""
            SELECT ordinal,json_extract(payload,'$.elapsed_seconds'),
              json_extract(payload,'$.summed_rss_bytes'),json_extract(payload,'$.completed_work_count'),
              CASE WHEN json_type(payload,'$.cpu_user_seconds') IN ('integer','real')
                 AND json_type(payload,'$.cpu_system_seconds') IN ('integer','real')
                 AND json_extract(payload,'$.cpu_user_seconds')>=0
                 AND json_extract(payload,'$.cpu_system_seconds')>=0
              THEN json_extract(payload,'$.cpu_user_seconds')
                +json_extract(payload,'$.cpu_system_seconds')
              ELSE NULL END
            FROM samples WHERE json_valid(payload)
              AND json_extract(payload,'$.measurement_status')='measured'
              AND json_extract(payload,'$.completed_work_count_status')='measured'
              AND json_type(payload,'$.elapsed_seconds') IN ('integer','real')
              AND json_type(payload,'$.summed_rss_bytes')='integer'
              AND json_type(payload,'$.completed_work_count')='integer'
              AND json_extract(payload,'$.elapsed_seconds')>=0
              AND json_extract(payload,'$.summed_rss_bytes')>=0
              AND json_extract(payload,'$.completed_work_count')>=0
            ORDER BY ordinal
        """).fetchall()
        independent_count = db.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
    if (
        python_values != sql_values
        or sample_count != independent_count
        or sample_count != profile["sample_count"]
    ):
        raise ValueError("trace_complete_sample_identity_mismatch")
    warm = [row for row in python_values if row[3] >= 1]
    active = [row for row in warm if _within_active(row[1], active_end)]
    hardware = profile.get("hardware_observation", {})
    cpus = hardware.get("logical_cpu_count")
    if not analysis._integer(cpus) or cpus == 0:
        cpus = None
    return {
        "schema_version": "corr.throughput_complete_trace_analysis.v1",
        "synthetic": synthetic,
        "authority_status": "candidate_measurement",
        "authority_granted": False,
        "level_path": str(level_path),
        "level_sha256": analysis.raw_digest(level_path.read_bytes()),
        "trace_path": str(trace),
        "trace_sha256": analysis.raw_digest(trace.read_bytes()),
        "concurrency": concurrency,
        "terminal_work_count": count,
        "sample_count": sample_count,
        "complete_sample_identity_reconciliation": "equal",
        "ambiguous_sample_count": len(ambiguous),
        "ambiguous_sample_ordinals": ambiguous,
        "startup_measured_sample_count": len(python_values) - len(warm),
        "active_end_elapsed_seconds": active_end,
        "active_end_semantics": (
            "last owner finished_at before outcome persistence; "
            "later completion/shutdown samples separate"
        ),
        "active_warm": _metrics(active, cpus, count),
        "warm_through_process_exit": _metrics(warm, cpus, count),
        "hardware_observation": hardware,
        "long_run_memory_bound_established": False,
        "limitation": (
            "OLS and completion-bin observations on this finite trace only; "
            "startup deallocation and cleanup may dominate; "
            "no week-long or corpus-linear memory claim"
        ),
    }


def main() -> int:
    """Root-owned safe output; read-only source traces and no model requests."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("level", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    common = importlib.import_module(PREFIX + "capacity_common")
    writer = common.SafeJsonWriter(common.load_credential())
    writer(args.output, analyse_trace(args.level))
    sys.stdout.write(writer.encode({"trace_analysis": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
