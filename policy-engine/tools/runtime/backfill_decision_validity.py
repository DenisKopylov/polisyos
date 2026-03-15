from __future__ import annotations

import argparse
import json
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.runtime.http.services.adapters.core_run import load_core_run
from polisyos.scientist.decision_validity import DecisionValidityService


def _iter_run_dirs(root: Path):
    if not root.exists():
        return
    for item in sorted(root.iterdir()):
        if item.is_dir():
            yield item


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill decision validity state for existing runs.")
    parser.add_argument("--cas-root", type=Path, default=Path(".polisyos/cas"))
    parser.add_argument("--runs-root", type=Path, default=Path(".polisyos/runs"))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    store = FileSystemCAS(args.cas_root)
    service = DecisionValidityService(store)

    processed = 0
    skipped = 0
    run_ids: list[str] = []

    for run_dir in _iter_run_dirs(args.runs_root):
        result = load_core_run(store=store, run_dir=run_dir)
        if result is None or result.decision_packet_ref is None:
            skipped += 1
            continue
        service.backfill_packet(str(result.decision_packet_ref.artifact_id))
        processed += 1
        run_ids.append(result.run_id)

    report = {
        "processed": processed,
        "skipped": skipped,
        "cas_root": str(args.cas_root),
        "runs_root": str(args.runs_root),
        "run_ids": run_ids,
    }

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
