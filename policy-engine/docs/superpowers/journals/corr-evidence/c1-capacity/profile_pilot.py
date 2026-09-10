"""Measure one declared six-input pilot and retain its complete resource trace."""

from __future__ import annotations

import argparse
import importlib
import sqlite3
import sys
from pathlib import Path

common = importlib.import_module(
    "docs.superpowers.journals.corr-evidence.c1-capacity.capacity_common"
)
telemetry = importlib.import_module(
    "docs.superpowers.journals.corr-evidence.c1-capacity.process_telemetry"
)


def main() -> int:
    """Run a committed pilot under its predeclared local operational caps."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binding", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    binding = common.read_sealed(args.binding)
    if binding["campaign_plan"]["input_count"] != 6:
        raise ValueError("profile_is_frozen_six_only")
    limits = binding["resource_profile_limits"]
    checkpoint = Path(binding["output_root"]) / "checkpoint.sqlite3"

    def completed() -> int:
        with sqlite3.connect(f"file:{checkpoint}?mode=ro", uri=True, timeout=0.1) as con:
            count = con.execute("SELECT COUNT(*) FROM works WHERE state='complete'").fetchone()[0]
            # This diagnostic's fixed six rows are reconciled completely.
            rows = con.execute("SELECT work_key,state FROM works").fetchall()
        identities = {key for key, state in rows if state == "complete"}
        if count != len(identities) or len(rows) != 6:
            raise ValueError("pilot_completion_identity_mismatch")
        return count

    summary = telemetry.profile_module(
        "docs.superpowers.journals.corr-evidence.c1-capacity.pilot_campaign",
        ["run", str(args.binding)], cwd=Path.cwd(), output_root=args.output,
        limits=telemetry.ProfileLimits(**limits), completion_reader=completed, synthetic=False,
    )
    cpu_parts = (summary["cpu_user_seconds"], summary["cpu_system_seconds"])
    cpu = sum(cpu_parts) if all(value is not None for value in cpu_parts) else None
    packet = {
        **summary, "binding_path": str(args.binding), "binding_hash": binding["content_hash"],
        "cpu_to_wall_ratio": cpu / summary["wall_seconds"] if cpu is not None else None,
        "native_disk_write_bytes_per_wall_second": (
            summary["disk_write_bytes"] / summary["wall_seconds"]
            if summary["disk_write_bytes"] is not None else None
        ),
        "sample_trace": str(args.output / "samples.jsonl"),
        "memory_trend": "requires complete warm-window analysis; six-input bound only",
    }
    writer = common.SafeJsonWriter(common.load_credential())
    writer(args.output / "summary.json", packet)
    sys.stdout.write(writer.encode(packet))
    return 0 if packet["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
