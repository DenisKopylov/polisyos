"""Audit pinned third-party GitHub Actions against latest upstream releases."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from tools._lib.fs import atomic_write_text
from tools._lib.http import fetch_json
from tools._lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__, include_src_root=False)


USES_PATTERN = re.compile(
    r"uses:\s*(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)(?:/[A-Za-z0-9_.-]+)*@(?P<sha>[0-9a-f]{40})(?:\s+#\s*(?P<tag>[^\s]+))?"
)
SEMVER_PATTERN = re.compile(r"^v?(?P<major>\d+)(?:\.(?P<minor>\d+))?(?:\.(?P<patch>\d+))?")


@dataclass(frozen=True)
class LatestTagResult:
    tag: str | None
    degraded_reason: str | None = None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check pinned GitHub Action freshness")
    parser.add_argument("--workflows-root", default=".github/workflows")
    parser.add_argument("--summary", help="Optional markdown summary output path")
    parser.add_argument("--json-output", help="Optional JSON output path")
    return parser.parse_args(argv)


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


def _fetch_latest_release_tag(repo: str, headers: dict[str, str]) -> str | None:
    payload = fetch_json(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers=headers,
        timeout_seconds=20,
        max_bytes=512 * 1024,
    )
    if not isinstance(payload, dict):
        raise ValueError(f"unexpected latest release payload for {repo}")
    tag = payload.get("tag_name")
    return str(tag) if tag else None


def _fetch_latest_tag(repo: str, headers: dict[str, str]) -> str | None:
    payload = fetch_json(
        f"https://api.github.com/repos/{repo}/tags?per_page=1",
        headers=headers,
        timeout_seconds=20,
        max_bytes=512 * 1024,
    )
    if not isinstance(payload, list):
        raise ValueError(f"unexpected tags payload for {repo}")
    if not payload:
        return None
    first = payload[0]
    if not isinstance(first, dict):
        raise ValueError(f"unexpected tag entry for {repo}")
    name = first.get("name")
    return str(name) if name else None


def fetch_latest_tag(repo: str) -> LatestTagResult:
    token = os.environ.get("GH_TOKEN", "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "polisyos-action-freshness-audit",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        tag = _fetch_latest_release_tag(repo, headers)
        return LatestTagResult(tag)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as release_exc:
        try:
            tag = _fetch_latest_tag(repo, headers)
            return LatestTagResult(tag, degraded_reason=f"latest release lookup failed: {release_exc}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as tag_exc:
            return LatestTagResult(
                None,
                degraded_reason=f"GitHub lookup degraded: release={release_exc}; tags={tag_exc}",
            )


def evaluate(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    latest_cache: dict[str, LatestTagResult | str | None] = {}
    results: list[dict[str, object]] = []
    for entry in entries:
        repo = str(entry["repo"])
        latest_raw = latest_cache.setdefault(repo, fetch_latest_tag(repo))
        latest = latest_raw if isinstance(latest_raw, LatestTagResult) else LatestTagResult(latest_raw)
        latest_tag = latest.tag
        current_tag = str(entry.get("tag") or "")
        current_version = parse_semver(current_tag)
        latest_version = parse_semver(latest_tag)

        if latest.degraded_reason and latest_tag is None:
            status = "degraded"
        elif not current_tag:
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
                "degraded_reason": latest.degraded_reason,
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
    atomic_write_text(path, "\n".join(lines) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    workflows_root = Path(args.workflows_root).resolve()
    entries = discover_pinned_actions(workflows_root)
    results = evaluate(entries)

    if args.summary:
        write_summary(Path(args.summary).resolve(), results)
    if args.json_output:
        atomic_write_text(
            Path(args.json_output).resolve(),
            json.dumps({"results": results}, indent=2, sort_keys=True) + "\n",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
