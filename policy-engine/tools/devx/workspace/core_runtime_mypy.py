#!/usr/bin/env python3
"""Run strict mypy over every Python file in the core runtime surface."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from ._common import PRODUCT_ROOT

DEFAULT_SCOPE = (
    "src/polisyos/common",
    "src/polisyos/core",
    "src/polisyos/runtime",
)
DEFAULT_MYPY_ARGS = ("--strict",)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run strict mypy over every file in the core-runtime typing surface. "
            "Files are checked one-by-one to avoid bulk-run false positives while "
            "still covering the complete surface."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help=(
            "Optional files or directories to check. "
            "Defaults to src/polisyos/common, src/polisyos/core, src/polisyos/runtime."
        ),
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first failing file.",
    )
    return parser


def _resolve_scope(raw_paths: list[str]) -> list[Path]:
    if raw_paths:
        candidates = raw_paths
    else:
        candidates = list(DEFAULT_SCOPE)
    resolved: list[Path] = []
    for raw in candidates:
        path = Path(raw)
        if not path.is_absolute():
            path = PRODUCT_ROOT / path
        resolved.append(path.resolve())
    return resolved


def _iter_python_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if not path.exists():
            raise SystemExit(f"Path does not exist: {path}")
        candidates: list[Path]
        if path.is_file():
            candidates = [path] if path.suffix == ".py" else []
        else:
            candidates = sorted(
                file_path
                for file_path in path.rglob("*.py")
                if "__pycache__" not in file_path.parts
            )
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            files.append(candidate)
    files.sort()
    if not files:
        raise SystemExit("No Python files discovered for the requested scope.")
    return files


def _run_mypy_for_file(path: Path) -> tuple[int, str]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            *DEFAULT_MYPY_ARGS,
            str(path.relative_to(PRODUCT_ROOT)),
        ],
        cwd=PRODUCT_ROOT,
        capture_output=True,
        text=True,
    )
    combined = "\n".join(
        part for part in (completed.stdout.strip(), completed.stderr.strip()) if part
    )
    return completed.returncode, combined


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    scope = _resolve_scope(args.paths)
    files = _iter_python_files(scope)
    print(f"Running strict mypy over {len(files)} files...")

    failures = 0
    for index, path in enumerate(files, start=1):
        if index == 1 or index == len(files) or index % 25 == 0:
            print(f"[mypy] {index}/{len(files)}")
        returncode, output = _run_mypy_for_file(path)
        if returncode == 0:
            continue
        failures += 1
        print()
        print(f"==> {path.relative_to(PRODUCT_ROOT)}")
        if output:
            print(output)
        if args.fail_fast:
            break

    if failures:
        print(f"\nStrict mypy failed for {failures} file(s).")
        return 1

    print("Strict mypy passed for the full core-runtime surface.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
