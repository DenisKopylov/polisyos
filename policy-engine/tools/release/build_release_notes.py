"""Render Keep-a-Changelog style release notes from structured TOML fragments."""

from __future__ import annotations

import argparse
import json
import tomllib
from collections import defaultdict
from datetime import date
from pathlib import Path


CATEGORY_ORDER = ["added", "changed", "deprecated", "removed", "fixed", "security"]
SECTION_TITLES = {
    "added": "Added",
    "changed": "Changed",
    "deprecated": "Deprecated",
    "removed": "Removed",
    "fixed": "Fixed",
    "security": "Security",
}
CURATED_SECTIONS = {
    "compatibility": "Compatibility Notes",
    "surface_classification": "Supported Surface Classification",
    "migration": "Migration Notes",
    "api": "Schema / Runtime / API Changes",
    "limitations": "Known Limitations",
}


def load_fragments(fragments_dir: Path) -> list[dict[str, str]]:
    fragments: list[dict[str, str]] = []
    for path in sorted(fragments_dir.glob("*.toml")):
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
        payload["__path__"] = str(path)
        fragments.append(payload)
    return fragments


def curated_section_counts(fragments: list[dict[str, str]]) -> dict[str, int]:
    counts = {key: 0 for key in CURATED_SECTIONS}
    for fragment in fragments:
        for key in CURATED_SECTIONS:
            value = str(fragment.get(key, "")).strip()
            if value:
                counts[key] += 1
    return counts


def validate_required_curated_sections(
    fragments: list[dict[str, str]],
    required_sections: list[str],
) -> dict[str, int]:
    invalid = sorted(section for section in required_sections if section not in CURATED_SECTIONS)
    if invalid:
        supported = ", ".join(sorted(CURATED_SECTIONS))
        raise ValueError(
            f"Unsupported curated section(s): {', '.join(invalid)}. Supported values: {supported}"
        )

    counts = curated_section_counts(fragments)
    missing = [section for section in required_sections if counts.get(section, 0) == 0]
    if missing:
        missing_labels = ", ".join(CURATED_SECTIONS[section] for section in missing)
        raise ValueError(
            "Release notes are missing required curated section content for: "
            f"{missing_labels}"
        )
    return counts


def render_release_notes(version: str, fragments: list[dict[str, str]], release_date: str) -> str:
    grouped: dict[str, list[str]] = defaultdict(list)
    curated: dict[str, list[str]] = defaultdict(list)

    for fragment in fragments:
        category = fragment["type"].strip().lower()
        if category not in SECTION_TITLES:
            raise ValueError(f"{fragment['__path__']}: unsupported fragment type `{category}`")

        component = fragment.get("component", "").strip()
        summary = fragment["summary"].strip()
        title = fragment.get("title", "").strip()
        bullet = summary
        if title and title.lower() not in summary.lower():
            bullet = f"{title}: {summary}"
        if component:
            bullet = f"`{component}`: {bullet}"
        grouped[category].append(f"- {bullet}")

        for key in CURATED_SECTIONS:
            value = fragment.get(key, "").strip()
            if value:
                curated[key].append(f"- {value}")

    lines = [
        f"## [{version}] - {release_date}",
        "",
    ]

    for category in CATEGORY_ORDER:
        bullets = grouped.get(category)
        if not bullets:
            continue
        lines.append(f"### {SECTION_TITLES[category]}")
        lines.extend(bullets)
        lines.append("")

    for key, heading in CURATED_SECTIONS.items():
        bullets = curated.get(key)
        if not bullets:
            continue
        lines.append(f"## {heading}")
        lines.extend(bullets)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build release notes from structured fragments")
    parser.add_argument("--version", required=True, help="Release version without the leading v")
    parser.add_argument("--fragments-dir", required=True, help="Directory containing TOML fragments")
    parser.add_argument("--output", required=True, help="Output markdown path")
    parser.add_argument("--metadata-output", help="Optional JSON metadata output path")
    parser.add_argument("--date", default=date.today().isoformat(), help="Release date")
    parser.add_argument(
        "--require-curated-sections",
        nargs="*",
        default=[],
        metavar="SECTION",
        help="Require at least one fragment entry for each named curated section.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fragments_dir = Path(args.fragments_dir).resolve()
    fragments = load_fragments(fragments_dir)
    if not fragments:
        raise SystemExit(f"No release fragments found in {fragments_dir}")
    section_counts = validate_required_curated_sections(
        fragments,
        list(args.require_curated_sections),
    )

    notes = render_release_notes(args.version, fragments, args.date)
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(notes, encoding="utf-8")

    if args.metadata_output:
        metadata = {
            "version": args.version,
            "date": args.date,
            "fragment_count": len(fragments),
            "fragments": [fragment["__path__"] for fragment in fragments],
            "curated_section_counts": section_counts,
        }
        Path(args.metadata_output).resolve().write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
