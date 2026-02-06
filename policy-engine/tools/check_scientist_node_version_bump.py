#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_VERSION_RE = re.compile(
    r'component_id\s*=\s*ComponentId\.parse\("(?P<node_id>[^"]+?)@(?P<version>\d+\.\d+\.\d+)"\)'
)

_SKIP_FILENAMES = {"__init__.py", "errors.py", "state_keys.py"}


def _run_git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.stdout.strip()


def _try_git(args: list[str]) -> str | None:
    try:
        return _run_git(args)
    except subprocess.CalledProcessError:
        return None


def _resolve_merge_base(base_ref: str) -> str:
    direct = _try_git(["merge-base", "HEAD", base_ref])
    if direct:
        return direct
    fallback = _try_git(["rev-parse", "HEAD~1"])
    if fallback:
        return fallback
    return _run_git(["rev-parse", "HEAD"])


def _changed_builtin_files(merge_base: str) -> list[Path]:
    output = _run_git(
        [
            "diff",
            "--name-only",
            f"{merge_base}..HEAD",
            "--",
            "src/polisyos/scientist/nodes/builtins",
            "src/polisyos/scientist/engine/builtins",
        ]
    )
    paths: list[Path] = []
    for raw in output.splitlines():
        if not raw.endswith(".py"):
            continue
        path = Path(raw)
        if path.name in _SKIP_FILENAMES:
            continue
        paths.append(path)
    return paths


def _extract_version(source: str) -> str | None:
    match = _VERSION_RE.search(source)
    if match is None:
        return None
    return match.group("version")


def _load_old_file(merge_base: str, path: Path) -> str | None:
    return _try_git(["show", f"{merge_base}:{path.as_posix()}"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Require SemVer bump for changed Scientist builtin nodes"
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Git ref for merge-base comparison",
    )
    args = parser.parse_args()

    merge_base = _resolve_merge_base(args.base_ref)
    changed_files = _changed_builtin_files(merge_base)
    if not changed_files:
        print("no Scientist builtin node file changes detected")
        return 0

    failures: list[str] = []
    for path in changed_files:
        old_source = _load_old_file(merge_base, path)
        if old_source is None:
            # New file, no version bump requirement.
            continue
        if not path.exists():
            # File deleted/renamed.
            continue
        new_source = path.read_text(encoding="utf-8")
        old_version = _extract_version(old_source)
        new_version = _extract_version(new_source)
        if old_version is None or new_version is None:
            continue
        if old_version == new_version:
            failures.append(
                (
                    f"{path.as_posix()}: component_id version unchanged ({new_version}); "
                    "bump SemVer on code changes"
                )
            )

    if failures:
        for issue in failures:
            print(issue)
        return 1
    print("Scientist builtin version bump check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
