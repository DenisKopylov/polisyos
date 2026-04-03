"""Audit pinned third-party GitHub Actions against latest upstream releases."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path


USES_PATTERN = re.compile(
    r"uses:\s*(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:/[A-Za-z0-9_.-]+)*@(?P<sha>[0-9a-f]{40})(?:\s+#\s*(?P<tag>[^\s]+))?"
)
SEMVER_PATTERN = re.compile(r"^v?(?P<major>\d+)(?:\.(?P<minor>\d+))?(?:\.(?P<patch>\d+))?")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check pinned GitHub Action freshness")
    parser.add_argument("--workflows-root", default=".github/workflows")
    parser.add_argument("--summary", help="Optional markdown summary output path")
    parser.add_argument("--json-output", help="Optional JSON output path")
    return parser.parse_args()


def parse_semver(tag: str | None) -> tuple[int, int, int] | None:
    if not tag:
        return None
    match = SEMVER_PATTERN.match(tag.strip())
    if not match:
        return None
    return (
        int(match.group("major") or 0),
        int(match.group("minor") or 0),
        int(match.group("patch") or 0),
    )


def discover_pinned_actions(workflows_root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for workflow in sorted(workflows_root.glob("*.yml")):
        for line_number, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), start=1):
            match = USES_PATTERN.search(line)
            if not match:
                continue
            entries.append(
                {
                    "workflow": str(workflow),
                    "line": line_number,
                    "repo": match.group("repo"),
                    "sha": match.group("sha"),
                    "tag": match.group("tag"),
                }
            )
    return entries


def fetch_latest_tag(repo: str) -> str | None:
    token = os.environ.get("GH_TOKEN", "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "polisyos-action-freshness-audit",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/repos/{repo}/releases/latest"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        tags_url = f"https://api.github.com/repos/{repo}/tags?per_page=1"
        fallback_request = urllib.request.Request(tags_url, headers=headers)
        try:
            with urllib.request.urlopen(fallback_request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if payload:
                    return str(payload[0].get("name", ""))
        except Exception:
            return None
        return None
    return str(payload.get("tag_name", ""))


def evaluate(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    latest_cache: dict[str, str | None] = {}
    results: list[dict[str, object]] = []
    for entry in entries:
        repo = str(entry["repo"])
        latest_tag = latest_cache.setdefault(repo, fetch_latest_tag(repo))
        current_tag = str(entry.get("tag") or "")
        current_version = parse_semver(current_tag)
        latest_version = parse_semver(latest_tag)

        if not current_tag:
            status = "missing-comment"
        elif latest_version is None or current_version is None:
            status = "unknown"
        elif current_version == latest_version:
            status = "current"
        elif current_version[0] < latest_version[0]:
            status = "major-lag"
        else:
            status = "update-available"

        results.append(
            {
                **entry,
                "latest_tag": latest_tag,
                "status": status,
            }
        )
    return results


def write_summary(path: Path, results: list[dict[str, object]]) -> None:
    lines = ["# GitHub Action Freshness Audit", ""]
    lines.extend(
        [
            "| Workflow | Line | Action | Pinned comment | Latest upstream | Status |",
            "|---|---:|---|---|---|---|",
        ]
    )
    for result in results:
        lines.append(
            "| `{workflow}` | {line} | `{repo}` | `{tag}` | `{latest}` | {status} |".format(
                workflow=Path(str(result["workflow"])).name,
                line=result["line"],
                repo=result["repo"],
                tag=result.get("tag") or "missing",
                latest=result.get("latest_tag") or "unknown",
                status=result["status"],
            )
        )
    lines.append("")

    lagged = [result for result in results if result["status"] not in {"current"}]
    if lagged:
        lines.extend(["## Follow-up", ""])
        lines.extend(
            f"- `{result['repo']}` in `{Path(str(result['workflow'])).name}` is `{result['status']}`."
            for result in lagged
        )
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    workflows_root = Path(args.workflows_root).resolve()
    entries = discover_pinned_actions(workflows_root)
    results = evaluate(entries)

    if args.summary:
        write_summary(Path(args.summary).resolve(), results)
    if args.json_output:
        Path(args.json_output).resolve().write_text(
            json.dumps({"results": results}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
