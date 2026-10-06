"""Trace immutable selector derivation without importing pytest or running gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import traceback
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import FrameType

SELECTOR = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/"
    "final-cohort-selector.py"
)
EQUIVALENTS = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B/"
    "current-adapters-evidence/cohort-selector-equivalents.json"
)


def main() -> None:
    """Execute only the Git-reading static instrument and retain its failure boundary."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    git_executable = shutil.which("git")
    if git_executable is None:
        raise ValueError("Git executable unavailable")

    def git(*argv: str) -> bytes:
        return subprocess.check_output([git_executable, "-C", str(args.repo), *argv])  # noqa: S603 - fixed Git argv, no shell

    source = git("show", f"{args.target}:{SELECTOR}")
    source_copy = args.out / "selector-pinned.py"
    source_copy.write_bytes(source)
    target_output = args.out / "selector-output.json"
    target_argv = [
        str(source_copy),
        "--repo",
        str(args.repo),
        "--sha",
        args.target,
        "--equivalents",
        str(args.repo / EQUIVALENTS),
        "--output",
        str(target_output),
    ]
    before = {
        "head": git("rev-parse", "HEAD").decode().strip(),
        "tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
        "status": git("status", "--porcelain").decode(),
    }
    captured = {}

    def observer(frame: FrameType, event: str, value: object) -> object:
        if (
            frame.f_code.co_filename == str(source_copy)
            and frame.f_code.co_name == "main"
            and event in {"exception", "return"}
        ):
            captured.update(frame.f_locals)
        return observer

    old_argv = sys.argv
    old_trace = sys.gettrace()
    exception = None
    started = datetime.now(UTC).isoformat()
    try:
        sys.argv = target_argv
        sys.settrace(observer)
        namespace = {"__name__": "__main__", "__file__": str(source_copy)}
        exec(compile(source, str(source_copy), "exec"), namespace)  # noqa: S102 - hash-bound actual static driver, no product execution
    except Exception as exc:
        exception = {"type": type(exc).__name__, "message": str(exc)}
        traceback.print_exc()
    finally:
        sys.settrace(old_trace)
        sys.argv = old_argv

    missing = captured.get("missing", [])
    mapping = captured.get("mapping", {})
    planned = captured.get("planned", {})
    cache = captured.get("cache", {})
    roots = [path for path, _ in captured.get("roots", [])]
    references = captured.get("json_references")
    parent = dict.fromkeys(roots)
    pending = deque(roots)
    while pending and references is not None:
        path = pending.popleft()
        if not path.endswith(".json") or path not in cache:
            continue
        try:
            value = json.loads(cache[path])
        except ValueError:
            continue
        for child in sorted(set(references(value))):
            if child not in parent:
                parent[child] = path
                pending.append(child)

    def route(path: str) -> list[str]:
        result = []
        while path is not None:
            result.append(path)
            path = parent.get(path)
        return result[::-1]

    missing_paths = {row["named_selector"] for row in missing}
    commands = []
    for command in captured.get("commands", []):
        absent = sorted(
            selector.split("::")[0].removeprefix("policy-engine/")
            for selector in command["selectors"]
            if selector.split("::")[0].removeprefix("policy-engine/") in missing_paths
        )
        if absent:
            commands.append({**command, "missing_paths": absent})
    origin_paths = set()
    for row in missing:
        row["canonical_planned"] = row["named_selector"] in planned
        row["map_present"] = row["named_selector"] in mapping
        for reference in row["source_refs"]:
            locator = reference["locator"]
            matches = [
                p
                for p in cache
                if locator == p or locator.startswith(p + "/") or locator.startswith(p + "#")
            ]
            if not matches:
                raise ValueError(f"Source locator has no exact pinned source: {locator}")
            path = max(matches, key=len)
            reference["reference_route"] = route(path)
            origin_paths.update(reference["reference_route"])
    identities = [
        {
            "path": path,
            "sha256": hashlib.sha256(cache[path]).hexdigest(),
            "bytes": len(cache[path]),
        }
        for path in sorted(origin_paths)
        if path in cache
    ]
    after = {
        "head": git("rev-parse", "HEAD").decode().strip(),
        "tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
        "status": git("status", "--porcelain").decode(),
    }
    report = {
        "schema": "policyos.e02.independent_static_derivation_trace.v1",
        "target_sha": args.target,
        "target_tree": git("rev-parse", args.target + "^{tree}").decode().strip(),
        "driver_command": sys.argv,
        "selector_argv": target_argv,
        "selector_source": {
            "path": SELECTOR,
            "sha256": hashlib.sha256(source).hexdigest(),
            "bytes": len(source),
        },
        "environment": {
            "python": sys.executable,
            "version": sys.version,
            "cwd": str(Path.cwd()),
            "started_utc": started,
            "ended_utc": datetime.now(UTC).isoformat(),
            "six_numeric_cap_values": {
                key: os.environ.get(key)
                for key in (
                    "OMP_NUM_THREADS",
                    "OPENBLAS_NUM_THREADS",
                    "MKL_NUM_THREADS",
                    "NUMEXPR_NUM_THREADS",
                    "VECLIB_MAXIMUM_THREADS",
                    "XLA_FLAGS",
                )
            },
        },
        "outcome": "FAIL" if exception else "PASS",
        "exception": exception,
        "selector_output_exists": target_output.exists(),
        "root_before": before,
        "root_after": after,
        "root_unchanged": before == after,
        "counts": {
            "existing": len(captured.get("existing", [])),
            "all_missing": len(missing),
            "canonical_planned_missing": sum(row["canonical_planned"] for row in missing),
            "noncanonical_missing": sum(not row["canonical_planned"] for row in missing),
            "unmapped_missing": sum(not row["map_present"] for row in missing),
            "commands": len(captured.get("commands", [])),
            "all_commands": len(captured.get("all_commands", [])),
            "scripts": len(captured.get("driver_records", [])),
            "top_receipts": len(roots),
        },
        "all_missing": missing,
        "commands_contributing_missing": commands,
        "missing_origin_reference_identities": identities,
        "qualification": (
            "Complete actual immutable static main under observational sys.settrace. "
            "No pytest import, collection, cases, gates, product modules, or root mutations. "
            "Missing paths already have explicit UNRUN state before failing the global map guard. "
            "Reference reachability and command shape establish lineage, not execution eligibility."
        ),
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    (args.out / "trace.json").write_text(rendered)
    sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
