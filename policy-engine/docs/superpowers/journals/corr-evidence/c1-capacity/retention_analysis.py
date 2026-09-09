"""Describe complete marked campaign memory traces without long-run extrapolation."""

from __future__ import annotations

import argparse
import importlib
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."
trace_owner = importlib.import_module(PREFIX + "throughput_trace_analysis")
analysis = importlib.import_module(PREFIX + "pilot_analysis")


def _work_progress(completed: int, count: int) -> bool:
    return 1 <= completed < count


def windows(
    rows: list[tuple], *, input_count: int, campaign_end: float, logical_cpus: int | None
) -> dict[str, Any]:
    """Reuse the existing complete-bin/OLS owner, separating replay and exit."""
    warm = [row for row in rows if row[3] >= 1]
    progress = [row for row in warm if _work_progress(row[3], input_count)]
    active = [row for row in warm if row[1] <= campaign_end]
    return {
        "startup_sample_count": len(rows) - len(warm),
        "work_progress_warm": trace_owner._metrics(progress, logical_cpus, input_count),
        "campaign_warm_including_replay": trace_owner._metrics(active, logical_cpus, input_count),
        "warm_through_exit": trace_owner._metrics(warm, logical_cpus, input_count),
        "work_window_semantics": (
            "sampled durable completion count >=1 and < declared frame size; "
            "final completion/replay excluded, unsampled bins are not zeros"
        ),
        "campaign_window_semantics": (
            "after first durable completion through real run_campaign return; "
            "includes mandatory complete-artifact replay"
        ),
    }


def analyse(path: Path) -> dict[str, Any]:
    """Reconcile every recorded sample and work identity before descriptive analysis."""
    outer = analysis._json(path)
    profile = outer["profile"]
    if outer["synthetic"] is not True or profile["synthetic"] is not True:
        raise ValueError("retention_analysis_requires_marked_synthetic")
    root = path.parent
    summary_path = Path(outer["worker_summary_path"])
    worker = analysis._json(summary_path)
    count = outer["declared_input_count"]
    if (
        worker["synthetic"] is not True
        or worker["authority_granted"] is not False
        or worker["declaration_hash"] != outer["declaration_hash"]
        or worker["completed_work_count"] != count
    ):
        raise ValueError("retention_completed_frame_not_established")
    campaign = summary_path.parent / "campaign"
    with closing(
        sqlite3.connect((campaign / "checkpoint.sqlite3").resolve().as_uri() + "?mode=ro", uri=True)
    ) as db:
        work_ids = {
            row[0][7:] for row in db.execute("SELECT work_key FROM works WHERE state='complete'")
        }
        independent = db.execute("SELECT COUNT(*) FROM works WHERE state='complete'").fetchone()[0]
    file_ids = {file.stem for file in (campaign / "works").glob("*.json")}
    if work_ids != file_ids or len(work_ids) != independent or independent != count:
        raise ValueError("retention_work_identity_mismatch")
    trace = root / "profile" / "samples.jsonl"
    qualified = []
    ambiguous = []
    total = 0
    with closing(sqlite3.connect(":memory:")) as db:
        db.execute("CREATE TABLE samples(ordinal INTEGER PRIMARY KEY,payload TEXT)")
        with trace.open() as stream:
            for ordinal, line in enumerate(stream):
                total += 1
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    value = None
                db.execute("INSERT INTO samples VALUES(?,?)", (ordinal, line if value else None))
                if not isinstance(value, dict):
                    ambiguous.append(ordinal)
                    continue
                if value.get("synthetic") is not True:
                    raise ValueError("retention_trace_unmarked_sample")
                elapsed, rss, completed = (
                    value.get(key)
                    for key in (
                        "elapsed_seconds",
                        "summed_rss_bytes",
                        "completed_work_count",
                    )
                )
                if (
                    value.get("measurement_status") != "measured"
                    or value.get("completed_work_count_status") != "measured"
                    or not trace_owner._number(elapsed)
                    or not analysis._integer(rss)
                    or not analysis._integer(completed)
                ):
                    ambiguous.append(ordinal)
                    continue
                user, system = value.get("cpu_user_seconds"), value.get("cpu_system_seconds")
                cpu = (
                    user + system
                    if trace_owner._number(user) and trace_owner._number(system)
                    else None
                )
                qualified.append((ordinal, elapsed, rss, completed, cpu))
        sql_values = db.execute("""
            SELECT ordinal,json_extract(payload,'$.elapsed_seconds'),
              json_extract(payload,'$.summed_rss_bytes'),json_extract(payload,'$.completed_work_count'),
              CASE WHEN json_type(payload,'$.cpu_user_seconds') IN ('integer','real')
                 AND json_type(payload,'$.cpu_system_seconds') IN ('integer','real')
                 AND json_extract(payload,'$.cpu_user_seconds')>=0
                 AND json_extract(payload,'$.cpu_system_seconds')>=0
              THEN json_extract(payload,'$.cpu_user_seconds')
                +json_extract(payload,'$.cpu_system_seconds') ELSE NULL END
            FROM samples WHERE json_valid(payload)
              AND json_extract(payload,'$.measurement_status')='measured'
              AND json_extract(payload,'$.completed_work_count_status')='measured'
              AND json_type(payload,'$.elapsed_seconds') IN ('integer','real')
              AND json_type(payload,'$.summed_rss_bytes')='integer'
              AND json_type(payload,'$.completed_work_count')='integer'
              AND json_extract(payload,'$.elapsed_seconds')>=0
              AND json_extract(payload,'$.summed_rss_bytes')>=0
              AND json_extract(payload,'$.completed_work_count')>=0 ORDER BY ordinal
        """).fetchall()
        sql_count = db.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
    if qualified != sql_values or total != sql_count or total != profile["sample_count"]:
        raise ValueError("retention_complete_sample_identity_mismatch")
    end = worker["campaign_finished_monotonic_seconds"] - profile["monotonic_started_seconds"]
    hardware = profile["hardware_observation"]
    cpus = hardware["logical_cpu_count"]
    return {
        "schema_version": "corr.synthetic_retention_analysis.v1",
        "synthetic": True,
        "authority_granted": False,
        "authority_status": "candidate_measurement",
        "declaration_hash": outer["declaration_hash"],
        "profile_path": str(path),
        "profile_sha256": analysis.raw_digest(path.read_bytes()),
        "trace_path": str(trace),
        "trace_sha256": analysis.raw_digest(trace.read_bytes()),
        "input_count": count,
        "sample_count": total,
        "ambiguous_sample_ordinals": ambiguous,
        "ambiguous_sample_count": len(ambiguous),
        "complete_identity_reconciliation": "equal",
        "hardware_observation": hardware,
        **windows(qualified, input_count=count, campaign_end=end, logical_cpus=cpus),
        "storage": analysis.storage_inventory(
            root, completed=count, wall_seconds=profile["wall_seconds"]
        ),
        "long_run_memory_bound_established": False,
        "limitation": (
            "Constructed bounded response vocabulary and finite input counts; "
            "allocator warm-up and retained state are not causally separated by an OLS slope. "
            "No provider throughput, correctness, calibration or week-long resource claim."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    owner = importlib.import_module(PREFIX + "synthetic_retention")
    result = analyse(args.profile)
    owner.write_json(args.output, result)
    sys.stdout.write(json.dumps({"synthetic": True, "analysis": str(args.output)}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
