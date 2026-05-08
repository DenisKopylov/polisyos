#!/usr/bin/env python3
"""Clean stale local reports and optional source-adjacent residue."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SOURCE_ADJACENT_ROOTS = (
    "apps",
    "architecture",
    "benchmarks",
    "data",
    "docs",
    "examples",
    "frontend",
    "ops",
    "packages",
    "release",
    "release-fragments",
    "schemas",
    "src",
    "tests",
    "tools",
)
SKIP_DIR_NAMES = {".git", ".hg", ".venv", ".venv_codex", "node_modules", ".next", ".turbo"}
AMBIGUOUS_FIXTURE_DIR_NAMES = {"cache", "errors", "raw"}
PHASE_LOCAL_JUNK_PATTERN = "phase*-local-junk-*"
PHASE_LOCAL_JUNK_KIND = "phase_local_junk_residue"


@dataclass(frozen=True)
class CleanupCandidate:
    path: Path
    kind: str
    reason: str
    owner_approval_required: bool = False

    def as_dict(self, repo_root: Path) -> dict[str, Any]:
        return {
            "path": _rel(self.path, repo_root),
            "kind": self.kind,
            "reason": self.reason,
            "owner_approval_required": self.owner_approval_required,
        }


def build_cleanup_plan(
    repo_root: Path = REPO_ROOT,
    *,
    stale_days: int = 30,
    include_residue: bool = False,
    include_audits: bool = False,
) -> dict[str, Any]:
    cutoff = time.time() - (stale_days * 24 * 60 * 60)
    candidates: list[CleanupCandidate] = []
    manual: list[CleanupCandidate] = []
    candidates.extend(_stale_children(repo_root / ".polisyos" / "reports", cutoff, "local_report"))
    candidates.extend(_stale_children(repo_root / "benchmarks" / "_reports", cutoff, "benchmark_report"))
    candidates.extend(_stale_build_audit_children(repo_root / "_build", cutoff))
    phase_junk_candidates, phase_junk_manual = _phase_local_junk_roots(repo_root)
    candidates.extend(phase_junk_candidates)
    manual.extend(phase_junk_manual)

    audit_candidates = _stale_children(
        repo_root / ".polisyos" / "audits",
        cutoff,
        "local_audit",
        owner_approval_required=True,
    )
    if include_audits:
        manual.extend(audit_candidates)
    else:
        manual.extend(audit_candidates)

    if include_residue:
        candidates.extend(_source_adjacent_residue(repo_root))
        candidates.extend(_empty_fixture_dirs(repo_root))

    unique_candidates = _dedupe_candidates(candidates)
    unique_manual = _dedupe_candidates(manual)
    return {
        "repo_root": str(repo_root),
        "stale_days": stale_days,
        "candidates": [candidate.as_dict(repo_root) for candidate in unique_candidates],
        "manual_review": [candidate.as_dict(repo_root) for candidate in unique_manual],
        "candidate_count": len(unique_candidates),
        "manual_review_count": len(unique_manual),
    }


def apply_cleanup(repo_root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    deleted: list[str] = []
    skipped: list[dict[str, str]] = []
    for item in plan["candidates"]:
        path = (repo_root / item["path"]).resolve()
        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
            else:
                skipped.append({"path": item["path"], "reason": "missing"})
                continue
        except OSError as exc:
            skipped.append({"path": item["path"], "reason": str(exc)})
            continue
        deleted.append(item["path"])
    return {
        **plan,
        "deleted": deleted,
        "deleted_count": len(deleted),
        "skipped": skipped,
        "skipped_count": len(skipped),
    }


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--stale-days", type=int, default=30)
    parser.add_argument("--include-residue", action="store_true")
    parser.add_argument("--include-audits", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    plan = build_cleanup_plan(
        repo_root,
        stale_days=args.stale_days,
        include_residue=args.include_residue,
        include_audits=args.include_audits,
    )
    payload = apply_cleanup(repo_root, plan) if args.apply else {**plan, "deleted_count": 0}
    payload["mode"] = "apply" if args.apply else "dry_run"

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        "clean-local-reports: "
        f"{payload['mode']} "
        f"candidates={payload['candidate_count']} "
        f"manual_review={payload['manual_review_count']} "
        f"deleted={payload['deleted_count']}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    return run_cli(argv)


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _dedupe_candidates(candidates: list[CleanupCandidate]) -> list[CleanupCandidate]:
    seen: set[Path] = set()
    unique: list[CleanupCandidate] = []
    for candidate in sorted(candidates, key=lambda item: item.path.as_posix()):
        resolved = candidate.path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(candidate)
    return unique


def _older_than(path: Path, cutoff: float) -> bool:
    try:
        return path.stat().st_mtime < cutoff
    except OSError:
        return False


def _stale_children(
    root: Path,
    cutoff: float,
    kind: str,
    *,
    owner_approval_required: bool = False,
) -> list[CleanupCandidate]:
    if not root.exists():
        return []
    candidates: list[CleanupCandidate] = []
    for child in sorted(root.iterdir()):
        if _older_than(child, cutoff):
            candidates.append(
                CleanupCandidate(
                    child,
                    kind,
                    "stale local report output",
                    owner_approval_required=owner_approval_required,
                )
            )
    return candidates


def _stale_build_audit_children(root: Path, cutoff: float) -> list[CleanupCandidate]:
    if not root.exists():
        return []
    candidates: list[CleanupCandidate] = []
    for current, dirnames, _filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
        current_path = Path(current)
        if current_path.name != "audit":
            continue
        for child in sorted(current_path.iterdir()):
            if _older_than(child, cutoff):
                candidates.append(CleanupCandidate(child, "build_audit", "stale build audit output"))
    return candidates


def _phase_local_junk_roots(
    repo_root: Path,
) -> tuple[list[CleanupCandidate], list[CleanupCandidate]]:
    build_root = repo_root / "_build"
    if not build_root.exists():
        return [], []
    candidates: list[CleanupCandidate] = []
    manual: list[CleanupCandidate] = []
    phase_junk_roots = (
        path for path in build_root.glob(PHASE_LOCAL_JUNK_PATTERN) if path.is_dir()
    )
    for child in sorted(phase_junk_roots):
        if _contains_tracked_file(repo_root, child):
            manual.append(
                CleanupCandidate(
                    child,
                    PHASE_LOCAL_JUNK_KIND,
                    "phase-local-junk root contains tracked evidence; review before cleanup",
                    owner_approval_required=True,
                )
            )
            continue
        candidates.append(
            CleanupCandidate(
                child,
                PHASE_LOCAL_JUNK_KIND,
                "ignored phase-local-junk build residue",
            )
        )
    return candidates, manual


def _contains_tracked_file(repo_root: Path, path: Path) -> bool:
    relative = _rel(path, repo_root)
    try:
        completed = subprocess.run(  # noqa: S603
            ["git", "ls-files", "--", relative],  # noqa: S607
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return any(line.strip() for line in completed.stdout.splitlines())


def _source_adjacent_residue(repo_root: Path) -> list[CleanupCandidate]:
    candidates: list[CleanupCandidate] = []
    for root_name in SOURCE_ADJACENT_ROOTS:
        root = repo_root / root_name
        if not root.exists():
            continue
        for current, dirnames, filenames in os.walk(root, topdown=True):
            dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
            current_path = Path(current)
            if current_path.name == "__pycache__":
                candidates.append(CleanupCandidate(current_path, "pycache", "Python bytecode cache"))
                dirnames[:] = []
                continue
            if current_path.name.endswith(".egg-info"):
                candidates.append(CleanupCandidate(current_path, "egg_info", "local package metadata"))
                dirnames[:] = []
                continue
            for filename in filenames:
                if filename == ".DS_Store":
                    candidates.append(
                        CleanupCandidate(current_path / filename, "ds_store", "macOS Finder residue")
                    )
    return candidates


def _empty_fixture_dirs(repo_root: Path) -> list[CleanupCandidate]:
    candidates: list[CleanupCandidate] = []
    for root_name in ("src", "tests", "benchmarks"):
        root = repo_root / root_name
        if not root.exists():
            continue
        for current, dirnames, _filenames in os.walk(root, topdown=False):
            dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
            path = Path(current)
            parts = {part.lower() for part in path.parts}
            if "fixtures" not in parts:
                continue
            if not _is_empty(path):
                continue
            reason = "empty fixture directory"
            if path.name.lower() in AMBIGUOUS_FIXTURE_DIR_NAMES:
                reason = "empty ambiguous cache/raw/errors fixture directory"
            candidates.append(CleanupCandidate(path, "empty_fixture_dir", reason))
    return candidates


def _is_empty(path: Path) -> bool:
    try:
        return path.is_dir() and not any(path.iterdir())
    except OSError:
        return False


if __name__ == "__main__":
    sys.exit(main())
