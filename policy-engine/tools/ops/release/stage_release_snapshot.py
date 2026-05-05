"""Freeze unreleased fragments into an immutable versioned release snapshot."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from build_release_notes import load_fragments, validate_required_curated_sections

REQUIRED_CURATED_SECTIONS = ["compatibility", "migration", "api", "limitations"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage a versioned release-fragment snapshot")
    parser.add_argument("--version", required=True, help="Release version without the leading v")
    parser.add_argument("--source-dir", default="policy-engine/release-fragments/unreleased")
    parser.add_argument("--release-root", default="policy-engine/_build/release-fragments")
    parser.add_argument(
        "--move",
        action="store_true",
        help="Move fragments out of the source directory instead of copying them.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing versioned snapshot directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_dir = Path(args.source_dir).resolve()
    if not source_dir.exists():
        raise SystemExit(f"Source fragment directory does not exist: {source_dir}")

    fragments = load_fragments(source_dir)
    if not fragments:
        raise SystemExit(f"No unreleased fragments found in {source_dir}")
    validate_required_curated_sections(fragments, REQUIRED_CURATED_SECTIONS)

    target_dir = Path(args.release_root).resolve() / args.version
    if target_dir.exists():
        has_files = any(target_dir.glob("*.toml"))
        if has_files and not args.force:
            raise SystemExit(
                f"Release snapshot already exists for {args.version}: {target_dir}. "
                "Use --force to overwrite it."
            )
        if args.force:
            shutil.rmtree(target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)
    for fragment in fragments:
        source_path = Path(fragment["__path__"]).resolve()
        destination = target_dir / source_path.name
        if args.move:
            shutil.move(str(source_path), destination)
        else:
            shutil.copy2(source_path, destination)

    action = "Moved" if args.move else "Copied"
    print(f"{action} {len(fragments)} release fragment(s) into {target_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
