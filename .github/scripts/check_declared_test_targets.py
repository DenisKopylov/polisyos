"""Refuse dangling literal Python test-file references in CI declarations.

The source set is every readable file under .github, including composite actions
and scripts. References are relative to the product root, with an optional
policy-engine prefix. This checks file existence, not test coverage or outcomes.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

TEST_PATH = re.compile(r"(?<![\w/])(?:\./)?(?:policy-engine/)?tests/[A-Za-z0-9_./-]+\.py\b")


def check_targets(repo_root: Path) -> int:
    """Enumerate CI references and fail if a file is missing or unreadable."""
    ci_root = repo_root / ".github"
    product_root = (repo_root / "policy-engine").resolve(strict=True)
    if not ci_root.is_dir():
        raise ValueError(f"CI declaration directory is missing: {ci_root}")

    def unreadable(error: OSError) -> None:
        raise error

    references: dict[str, list[str]] = {}
    files = 0
    for directory, directories, names in os.walk(ci_root, onerror=unreadable):
        for name in directories:
            if (Path(directory) / name).is_symlink():
                raise ValueError(f"CI source directory is a symlink: {Path(directory) / name}")
        for name in sorted(names):
            path = Path(directory) / name
            # Interpreter caches are not CI declarations.
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            files += 1
            for number, line in enumerate(text.splitlines(), 1):
                for match in TEST_PATH.finditer(line):
                    target = match.group().removeprefix("./").removeprefix("policy-engine/")
                    references.setdefault(target, []).append(
                        f"{path.relative_to(repo_root)}:{number}"
                    )

    missing = []
    for target, locations in sorted(references.items()):
        resolved = (product_root / target).resolve()
        if not resolved.is_relative_to(product_root / "tests") or not resolved.is_file():
            missing.append(target)
            print(f"missing test target: {target} ({', '.join(locations)})")
    print(
        f"CI declaration files={files}; unique Python test-file references={len(references)}; "
        f"missing={len(missing)}"
    )
    return int(bool(missing))


def main() -> int:
    """Run the declaration gate with errors treated as an undecidable scan."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        return check_targets(args.repo_root.resolve(strict=True))
    except (OSError, UnicodeError, ValueError) as error:
        print(f"Unable to verify declared test targets: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
