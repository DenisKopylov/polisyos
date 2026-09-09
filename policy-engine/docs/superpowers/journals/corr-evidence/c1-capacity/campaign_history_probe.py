"""Replay actual historical checkpoints without copying their artifacts into evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from polisyos.data_forge.domains.academic.batch.reextraction_campaign import (
    CampaignCheckpoint,
    CampaignPlan,
    _digest,
)


def _projection(root: Path) -> dict[str, dict[str, int | str]]:
    paths = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    independent = {
        (Path(directory) / name).relative_to(root).as_posix()
        for directory, _, names in os.walk(root)
        for name in names
        if (Path(directory) / name).is_file()
    }
    if paths != independent:
        raise RuntimeError("historical_source_identity_enumerations_disagree")
    result = {}
    for relative in sorted(paths):
        digest = hashlib.sha256()
        size = 0
        with (root / relative).open("rb") as stream:
            while chunk := stream.read(1_048_576):
                digest.update(chunk)
                size += len(chunk)
        result[relative] = {"bytes": size, "sha256": "sha256:" + digest.hexdigest()}
    return result


def main() -> None:
    """Require actual old-epoch replay and exact complete source preservation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, nargs="+")
    parser.add_argument("--require-wal", action="store_true")
    args = parser.parse_args()
    results = []
    wal_observed = False
    for root in args.root:
        root = root.resolve()
        before = _projection(root)
        with (root / "plan.json").open("rb") as stream:
            raw = stream.read(1_048_577)
        if len(raw) > 1_048_576:
            raise RuntimeError("historical_plan_exceeds_diagnostic_bound")
        plan = CampaignPlan(**json.loads(raw)["plan"])
        wal_bytes = before.get("checkpoint.sqlite3-wal", {}).get("bytes", 0)
        wal_observed = wal_observed or bool(wal_bytes)
        with CampaignCheckpoint.read_only_history(root, plan) as checkpoint:
            checkpoint.validate_complete_frame()
            summary = checkpoint.summary()
            if summary["works"] != {"complete": plan.input_count}:
                raise RuntimeError("historical_real_source_not_complete")
        after = _projection(root)
        changed = sorted(key for key in before.keys() & after.keys() if before[key] != after[key])
        if before != after:
            raise RuntimeError("historical_real_source_bytes_or_identities_changed")
        results.append({
            "root": str(root), "input_epoch": plan.execution_epoch,
            "source_synthetic": plan.synthetic, "source_plan_hash": _digest(json.loads(raw)),
            "historical_owner_source_hash": plan.owner_source_hash,
            "schema_version": summary["schema_version"], "works": summary["works"],
            "outcomes": summary["outcomes"], "attempts": summary["attempts"],
            "source_files": len(before), "complete_identity_hash": _digest(sorted(before)),
            "before_complete_byte_projection_hash": _digest(before),
            "after_complete_byte_projection_hash": _digest(after),
            "missing": sorted(before.keys() - after.keys()),
            "novel": sorted(after.keys() - before.keys()), "changed": changed,
            "original_wal_bytes": wal_bytes,
            "identity_enumerations": "equal_complete_rglob_and_os_walk",
        })
    if args.require_wal and not wal_observed:
        raise RuntimeError("required_actual_nonempty_wal_not_observed")
    sys.stdout.write(json.dumps({
        "synthetic": True, "authority_status": "candidate_only",
        "purpose": "diagnostic_replay_not_fresh_execution",
        "sources": results,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
