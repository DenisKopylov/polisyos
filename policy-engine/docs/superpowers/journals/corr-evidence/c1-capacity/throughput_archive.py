"""Archive completed throughput primary bytes with existing owner reconciliation.

Outcomes carry primary parsed responses. Provider observations and profile samples
carry nonrecomputable measurement values. The scalar checkpoint retains individual
admission/completion times needed to recompute latency and active resource windows;
its WAL is a physical companion, while SHM is a rebuildable index and is excluded.
No held source rows, derived extracted DTOs or alternate sorted views are copied.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Protocol

PREFIX = "docs.superpowers.journals.corr-evidence.c1-capacity."
analysis = importlib.import_module(PREFIX + "pilot_analysis")
runner = importlib.import_module(PREFIX + "throughput_runner")


class _Writer(Protocol):
    def check_payload(self, payload: object) -> None: ...
    def __call__(self, path: Path, payload: object) -> None: ...


def _scan(writer: _Writer, payload: object) -> None:
    writer.check_payload(payload)


def _equal(actual: object, expected: object, reason: str) -> None:
    if actual != expected:
        raise ValueError(reason)


def archive_throughput(
    source: Path, declaration: Path, destination: Path, *, writer: _Writer
) -> dict[str, Any]:
    """Preflight every complete primary before any new output; preserve exact bytes."""
    report = analysis._json(source)
    plan = runner.load_plan(declaration)
    synthetic = plan["synthetic"]
    if (
        type(synthetic) is not bool
        or report.get("synthetic") is not synthetic
        or report.get("declaration_hash") != plan["content_hash"]
        or report.get("authority_granted") is not False
        or report.get("full_pass_executed") is not False
    ):
        raise ValueError("throughput_archive_run_binding_mismatch")
    files = {"throughput-report.json": source}
    expected_levels = [row["concurrency"] for row in plan["levels"]]
    observed_levels = [row["concurrency"] for row in report["levels"]]
    _equal(
        observed_levels,
        expected_levels[: len(observed_levels)],
        "throughput_archive_level_identity_mismatch",
    )
    _equal(
        report["unrun_concurrencies"],
        expected_levels[len(observed_levels) :],
        "throughput_archive_unrun_identity_mismatch",
    )
    _equal(
        {Path(row["report_path"]).resolve() for row in report["levels"]},
        {path.resolve() for path in source.parent.glob("concurrency-*-report.json")},
        "throughput_archive_level_identity_mismatch",
    )
    denominators = []
    excluded = []
    trace_counts = {}
    for index, entry in enumerate(report["levels"]):
        concurrency = entry["concurrency"]
        prefix = "concurrency-" + str(concurrency)
        root = source.parent / prefix
        level_path = Path(entry["report_path"])
        level = analysis._json(level_path)
        if (
            analysis.digest(level) != entry["report_hash"]
            or level["declaration_hash"] != plan["content_hash"]
        ):
            raise ValueError("throughput_archive_level_hash_mismatch")
        files[prefix + "-report.json"] = level_path
        members = runner.level_members(plan, index)
        rows = runner.read_level_rows(root, members)
        # Same existing owner proves full work/outcome sets; no second outcome parser.
        outcomes = analysis._family(root, "outcomes")
        providers = analysis._family(root, "provider_attempts")
        expected_attempts = set()
        member_map = {member["work_id"]: member for member in members}
        for name, path in outcomes.items():
            packet = analysis._json(path)
            identifier = packet["work_id"]
            member = member_map[identifier]
            if (
                packet.get("synthetic") is not synthetic
                or packet.get("authority_granted") is not False
                or packet.get("declaration_hash") != plan["content_hash"]
                or packet.get("input_hash") != member["abstract_content_hash"]
                or packet.get("requested_model_id") != plan["model_id"]
            ):
                raise ValueError("throughput_archive_outcome_provenance_mismatch")
            attempt_id = packet["attempt_id"]
            if attempt_id in expected_attempts:
                raise ValueError("throughput_archive_duplicate_attempt")
            expected_attempts.add(attempt_id)
            if attempt_id not in providers:
                raise ValueError("throughput_archive_provider_identity_mismatch")
            provider_path = providers[attempt_id]
            observation = analysis._json(provider_path)
            if (
                Path(packet["provider_observation_path"]).resolve() != provider_path.resolve()
                or packet["provider_observation_hash"] != analysis.digest(observation)
                or observation.get("synthetic") is not synthetic
                or observation.get("model_id") != plan["model_id"]
                or observation.get("reported_model_id") not in (None, plan["model_id"])
            ):
                raise ValueError("throughput_archive_provider_binding_mismatch")
            context = observation["context"]
            for key, value in {
                "attempt_id": attempt_id,
                "work_id": identifier,
                "phase": "extraction",
                "campaign_id": plan["content_hash"],
                "input_hash": member["abstract_content_hash"],
                "synthetic": synthetic,
            }.items():
                if context.get(key) != value:
                    raise ValueError("throughput_archive_provider_context_mismatch")
            files[prefix + "/outcomes/" + name + ".json"] = path
            files[prefix + "/provider_attempts/" + attempt_id + ".json"] = provider_path
        _equal(set(providers), expected_attempts, "throughput_archive_provider_identity_mismatch")
        checkpoint = root / "checkpoint.sqlite"
        with sqlite3.connect(checkpoint.resolve().as_uri() + "?mode=ro", uri=True) as con:
            provenance = con.execute(
                "SELECT synthetic,authority_status FROM artifact_provenance"
            ).fetchall()
        _equal(
            provenance,
            [(int(synthetic), "candidate_only")],
            "throughput_archive_checkpoint_provenance_mismatch",
        )
        files[prefix + "/checkpoint.sqlite"] = checkpoint
        wal = checkpoint.with_name(checkpoint.name + "-wal")
        if wal.exists():
            files[prefix + "/checkpoint.sqlite-wal"] = wal
        shm = checkpoint.with_name(checkpoint.name + "-shm")
        if shm.exists():
            excluded.append({"path": str(shm), "reason": "rebuildable SQLite shared-memory index"})
        trace_name = "profile-" + str(concurrency) + "/samples.jsonl"
        trace = source.parent / trace_name
        files[trace_name] = trace
        trace_counts[trace_name] = level["profile"]["sample_count"]
        denominators.append(
            {
                "concurrency": concurrency,
                "work_count": len(rows),
                "terminal_count": sum(row["status"] in ("succeeded", "failed") for row in rows),
                "provider_observation_count": len(providers),
                "outcome_count": len(outcomes),
                "profile_sample_count": trace_counts[trace_name],
            }
        )
    bound_files = []
    # Scan raw bytes too, and decode every JSON/JSONL payload to catch escaped echoes.
    for relative, path in sorted(files.items()):
        data = path.read_bytes()
        _scan(writer, data.decode("latin1"))
        if path.suffix == ".json":
            packet = json.loads(data)
            _scan(writer, packet)
            if packet.get("synthetic") is not synthetic:
                raise ValueError("throughput_archive_primary_synthetic_mismatch")
        elif path.suffix == ".jsonl":
            count = 0
            for line in data.splitlines():
                value = json.loads(line)
                _scan(writer, value)
                if value.get("synthetic") is not synthetic:
                    raise ValueError("throughput_archive_trace_synthetic_mismatch")
                count += 1
            with path.open("rb") as stream:
                independent_count = sum(1 for _ in stream)
            _equal(
                (count, independent_count),
                (trace_counts[relative], trace_counts[relative]),
                "throughput_archive_trace_denominator_mismatch",
            )
        bound_files.append((relative, path, analysis.raw_digest(data), len(data)))
    destination.mkdir(parents=True, exist_ok=False)
    refs = []
    for relative, path, expected_hash, size in bound_files:
        data = path.read_bytes()
        if analysis.raw_digest(data) != expected_hash:
            raise ValueError("throughput_archive_source_changed")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if analysis.raw_digest(target.read_bytes()) != expected_hash:
            raise ValueError("throughput_archive_byte_readback_mismatch")
        refs.append(
            {
                "source_path": str(path),
                "archive_path": str(target),
                "sha256": expected_hash,
                "bytes": size,
            }
        )
    for _, path, expected_hash, _ in bound_files:
        if analysis.raw_digest(path.read_bytes()) != expected_hash:
            raise ValueError("throughput_archive_source_changed")
    return {
        "schema_version": "corr.throughput_primary_archive.v1",
        "synthetic": synthetic,
        "authority_status": "candidate_measurement",
        "authority_granted": False,
        "declaration_path": str(declaration),
        "declaration_hash": plan["content_hash"],
        "primary_files": refs,
        "level_denominators": denominators,
        "unrun_concurrencies": report["unrun_concurrencies"],
        "excluded_rebuildable_files": excluded,
        "corrected_interpretation": (
            "separate v2 artifact; original reports preserved byte-identically"
        ),
        "full_pass_executed": False,
    }


def main() -> int:
    """Root-owned scanner and immutable local archive; no provider calls."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("declaration", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    common = importlib.import_module(PREFIX + "capacity_common")
    writer = common.SafeJsonWriter(common.load_credential())
    manifest = archive_throughput(args.source, args.declaration, args.destination, writer=writer)
    writer(args.destination / "archive-manifest.json", manifest)
    sys.stdout.write(
        writer.encode({"archive_manifest": str(args.destination / "archive-manifest.json")})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
