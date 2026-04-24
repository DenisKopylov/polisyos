"""Check release artifact sizes against repo-tracked thresholds."""

from __future__ import annotations

import argparse
import json
import tomllib
from fnmatch import fnmatch
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check release artifact size policy")
    parser.add_argument(
        "--assets-dir", required=True, help="Directory containing release artifacts"
    )
    parser.add_argument("--policy", required=True, help="TOML policy describing size thresholds")
    parser.add_argument("--summary", help="Optional markdown summary output path")
    parser.add_argument("--json-output", help="Optional JSON summary output path")
    return parser.parse_args()


def load_policy(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _format_mib(size_bytes: int) -> str:
    return f"{size_bytes / (1024 * 1024):.2f} MiB"


def evaluate_artifacts(assets_dir: Path, policy: dict[str, object]) -> dict[str, object]:
    artifacts = list(policy.get("artifact", []))
    total_max_bytes = int(policy.get("total_max_bytes", 0) or 0)
    results: list[dict[str, object]] = []
    blockers: list[str] = []

    files = sorted(path for path in assets_dir.iterdir() if path.is_file())
    total_bytes = sum(path.stat().st_size for path in files)

    for artifact_policy in artifacts:
        name = str(artifact_policy["name"])
        pattern = str(artifact_policy["pattern"])
        owner = str(artifact_policy.get("owner", "unknown"))
        max_bytes = int(artifact_policy["max_bytes"])
        matches = [path for path in files if fnmatch(path.name, pattern)]
        if not matches:
            blockers.append(f"{name}: no artifact matched pattern `{pattern}`")
            results.append(
                {
                    "name": name,
                    "pattern": pattern,
                    "owner": owner,
                    "status": "missing",
                    "max_bytes": max_bytes,
                    "matches": [],
                }
            )
            continue

        for path in matches:
            size_bytes = path.stat().st_size
            status = "ok" if size_bytes <= max_bytes else "too_large"
            if status != "ok":
                blockers.append(
                    f"{name}: {path.name} is {_format_mib(size_bytes)} and exceeds "
                    f"{_format_mib(max_bytes)}"
                )
            results.append(
                {
                    "name": name,
                    "file": path.name,
                    "pattern": pattern,
                    "owner": owner,
                    "status": status,
                    "size_bytes": size_bytes,
                    "max_bytes": max_bytes,
                }
            )

    if total_max_bytes and total_bytes > total_max_bytes:
        blockers.append(
            "all release artifacts combined are "
            f"{_format_mib(total_bytes)} and exceed {_format_mib(total_max_bytes)}"
        )

    return {
        "artifacts": results,
        "blockers": blockers,
        "total_bytes": total_bytes,
        "total_max_bytes": total_max_bytes,
    }


def write_summary(path: Path, report: dict[str, object]) -> None:
    lines = ["# Release Artifact Size Policy", ""]
    total_bytes = int(report["total_bytes"])
    total_max_bytes = int(report.get("total_max_bytes", 0) or 0)
    lines.append(f"- Combined release artifact size: {_format_mib(total_bytes)}")
    if total_max_bytes:
        lines.append(f"- Combined threshold: {_format_mib(total_max_bytes)}")
    lines.append("")
    lines.extend(
        [
            "| Artifact | File | Owner | Size | Threshold | Status |",
            "|---|---|---|---:|---:|---|",
        ]
    )
    for artifact in report["artifacts"]:
        file_name = str(artifact.get("file", "n/a"))
        size_bytes = artifact.get("size_bytes")
        max_bytes = int(artifact.get("max_bytes", 0) or 0)
        size_label = _format_mib(int(size_bytes)) if size_bytes is not None else "n/a"
        threshold_label = _format_mib(max_bytes) if max_bytes else "n/a"
        lines.append(
            "| {name} | `{file}` | `{owner}` | {size} | {threshold} | {status} |".format(
                name=artifact["name"],
                file=file_name,
                owner=artifact["owner"],
                size=size_label,
                threshold=threshold_label,
                status=artifact["status"],
            )
        )
    lines.append("")

    blockers = report["blockers"]
    if blockers:
        lines.extend(["## Blocking Findings", ""])
        lines.extend(f"- {message}" for message in blockers)
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    assets_dir = Path(args.assets_dir).resolve()
    policy = load_policy(Path(args.policy).resolve())
    report = evaluate_artifacts(assets_dir, policy)

    if args.summary:
        write_summary(Path(args.summary).resolve(), report)
    if args.json_output:
        Path(args.json_output).resolve().write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if report["blockers"]:
        for message in report["blockers"]:
            print(f"Artifact size policy violation: {message}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
