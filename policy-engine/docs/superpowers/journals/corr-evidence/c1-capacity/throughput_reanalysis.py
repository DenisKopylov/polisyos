"""Reissue only the interpretation of completed throughput runs under epoch v2.

The original owner still computes the exact stop rule. This post-run reader adds
its missing measured-concurrency-comparison condition; it cannot dispatch calls,
change selection, resume a run or alter an original receipt.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."
_owner = importlib.import_module(PREFIX + "throughput_analysis")


def _comparison_established(current: dict[str, Any], previous: dict[str, Any] | None) -> bool:
    if previous is None or current["status"] != "measured" or previous["status"] != "measured":
        return False
    before, after = (
        previous.get("typed_success_per_second"),
        current.get("typed_success_per_second"),
    )
    lower, upper = previous.get("concurrency"), current.get("concurrency")
    return (
        type(lower) is int
        and type(upper) is int
        and 0 < lower < upper
        and type(before) in (float, int)
        and math.isfinite(before)
        and before > 0
        and type(after) in (float, int)
        and math.isfinite(after)
        and after >= 0
    )


def corrected_decision(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    """Preserve the stop and credit a knee only after an actual level comparison."""
    original = _owner.stop_decision(current, previous)
    comparable = _comparison_established(current, previous)
    return {
        **original,
        "schema_version": "corr.direct_extraction_stop_interpretation.v2",
        "knee_established": original["knee_established"] and comparable,
        "actual_concurrency_comparison_established": comparable,
        "knee_status": "established"
        if original["knee_established"] and comparable
        else "not_established",
        "observed_relative_throughput_gain": (
            current["typed_success_per_second"] / previous["typed_success_per_second"] - 1
            if comparable and previous is not None
            else None
        ),
        "error_origin": (
            "not_established; HTTP status and adapter labels do not locate the limiting service"
        ),
    }


def reanalyse(path: Path) -> dict[str, Any]:
    """Consume every emitted level and preserve every unrun declaration member."""
    analysis = importlib.import_module(PREFIX + "pilot_analysis")
    source = json.loads(path.read_text())
    before = analysis.raw_digest(path.read_bytes())
    if source["schema_version"] != "corr.direct_extraction_throughput_report.v1":
        raise ValueError("throughput_reanalysis_source_epoch_invalid")
    entries = source["levels"]
    expected = {Path(row["report_path"]).resolve() for row in entries}
    actual = {item.resolve() for item in path.parent.glob("concurrency-*-report.json")}
    if expected != actual or len(expected) != len(entries):
        raise ValueError("throughput_reanalysis_level_identity_mismatch")
    revised = []
    previous = None
    for entry in entries:
        level_path = Path(entry["report_path"])
        level = json.loads(level_path.read_text())
        if (
            analysis.digest(level) != entry["report_hash"]
            or level["concurrency"] != entry["concurrency"]
            or level["declaration_hash"] != source["declaration_hash"]
        ):
            raise ValueError("throughput_reanalysis_level_binding_mismatch")
        original = _owner.stop_decision(level, previous)
        if original != level["stop_decision"] or original != entry["stop_decision"]:
            raise ValueError("throughput_original_decision_not_recomputed")
        decision = corrected_decision(level, previous)
        if (
            decision["stop_higher_levels"] != original["stop_higher_levels"]
            or decision["reason"] != original["reason"]
        ):
            raise ValueError("throughput_reanalysis_changed_execution_rule")
        revised.append(
            {
                "concurrency": level["concurrency"],
                "source_path": str(level_path),
                "source_sha256": analysis.raw_digest(level_path.read_bytes()),
                "original_decision": original,
                "decision": decision,
                "storage": analysis.storage_inventory(
                    path.parent / ("concurrency-" + str(level["concurrency"])),
                    completed=level["terminal_count"] or 0,
                    wall_seconds=level["profile"]["wall_seconds"],
                ),
            }
        )
        previous = level
    if analysis.raw_digest(path.read_bytes()) != before:
        raise ValueError("throughput_reanalysis_source_changed")
    return {
        "schema_version": "corr.direct_extraction_throughput_interpretation.v2",
        "synthetic": source["synthetic"],
        "authority_status": "candidate_measurement",
        "authority_granted": False,
        "analysis_declared_at": datetime.now(UTC).isoformat(),
        "purpose": "post-run interpretation correction; not a pre-outcome selection declaration",
        "source_path": str(path),
        "source_sha256": before,
        "declaration_hash": source["declaration_hash"],
        "levels": revised,
        "unrun_concurrencies": source["unrun_concurrencies"],
        "full_pass_executed": False,
        "original_receipt_changed": False,
        "stop_rule_changed": False,
        "source_projection": {
            str(Path(__file__)): analysis.raw_digest(Path(__file__).read_bytes()),
            str(Path(_owner.__file__)): analysis.raw_digest(Path(_owner.__file__).read_bytes()),
            str(Path(analysis.__file__)): analysis.raw_digest(Path(analysis.__file__).read_bytes()),
        },
    }


def main() -> int:
    """Root-only secret-scanned append; never overwrite the historical v1 report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    common = importlib.import_module(PREFIX + "capacity_common")
    writer = common.SafeJsonWriter(common.load_credential())
    writer(args.output, reanalyse(args.source))
    sys.stdout.write(writer.encode({"interpretation_path": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
