"""Validate that a release tag matches packaged versions and fragment state."""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate PolicyOS release version alignment")
    parser.add_argument("--tag", required=True, help="Git tag in vX.Y.Z form")
    parser.add_argument("--pyproject", default="policy-engine/pyproject.toml")
    parser.add_argument(
        "--package-json", default="policy-engine/apps/runtime-dashboard/package.json"
    )
    parser.add_argument(
        "--release-fragments-root", default="policy-engine/_build/release-fragments"
    )
    parser.add_argument("--github-output", help="Optional GitHub output file path")
    return parser.parse_args()


def resolve_release_fragments_dir(version: str, release_root: Path) -> Path:
    fragments_dir = release_root / version
    if not fragments_dir.exists():
        raise SystemExit(
            f"Release fragment snapshot is missing for {version}: {fragments_dir}. "
            "Stage a versioned snapshot before cutting the tag."
        )
    return fragments_dir


def main() -> int:
    args = parse_args()
    tag = args.tag.strip()
    if not tag.startswith("v") or len(tag) == 1:
        raise SystemExit("Release tag must be in vX.Y.Z form")
    version = tag[1:]

    pyproject = tomllib.loads(Path(args.pyproject).read_text(encoding="utf-8"))
    python_version = pyproject["project"]["version"]
    frontend_version = json.loads(Path(args.package_json).read_text(encoding="utf-8"))["version"]

    if python_version != version:
        raise SystemExit(f"pyproject version mismatch: expected {version}, found {python_version}")
    if frontend_version != version:
        raise SystemExit(
            f"frontend package version mismatch: expected {version}, found {frontend_version}"
        )

    fragments_dir = resolve_release_fragments_dir(
        version,
        Path(args.release_fragments_root),
    )
    fragment_count = len(list(fragments_dir.glob("*.toml")))
    if fragment_count == 0:
        raise SystemExit(f"No release fragments found in {fragments_dir}")

    if args.github_output:
        output_path = Path(args.github_output)
        with output_path.open("a", encoding="utf-8") as fh:
            fh.write(f"version={version}\n")
            fh.write(f"fragments_dir={fragments_dir.resolve()}\n")
            fh.write(f"fragment_count={fragment_count}\n")

    print(f"Release version {version} validated against Python/frontend package metadata.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
