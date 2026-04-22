#!/usr/bin/env python3
"""Legacy compatibility wrapper for the canonical Foundry Phase 2 closure validator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ASSESSMENT_ID = "scientist_phase2_gate"


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Verify the enrolled Foundry Phase 2 tracks against the canonical "
            "closure manifest and emit a Scientist-compatible wrapper payload."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_default_repo_root(),
        help="Repository root that contains the canonical Phase 2 manifest.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Optional override for the canonical Phase 2 manifest path.",
    )
    parser.add_argument(
        "--junit-xml",
        type=Path,
        required=True,
        help="JUnit XML with enrolled Phase 2 acceptance evidence.",
    )
    parser.add_argument(
        "--benchmark-json",
        type=Path,
        required=True,
        help="JSON benchmark summary with enrolled Phase 2 benchmark statuses.",
    )
    parser.add_argument(
        "--evidence-json",
        type=Path,
        required=True,
        help="JSON evidence report with synthetic-world and judge-verdict statuses.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional file path for the rendered report.",
    )
    parser.add_argument(
        "--output-format",
        choices=("json", "text"),
        default="text",
        help="Render the report as JSON or plain text.",
    )
    return parser


def _resolve_path(path: Path, *, repo_root: Path) -> Path:
    return path.resolve() if path.is_absolute() else (repo_root / path).resolve()


def _render_text(payload: dict[str, Any]) -> str:
    phase2 = payload["phase2_closure"]
    lines = [
        f"{ASSESSMENT_ID}: {'PASS' if payload['passes_all'] else 'FAIL'}",
        f"phase={phase2['phase_id']}",
        f"overall_status={phase2['overall_status']}",
    ]
    for track_id, summary in sorted(phase2["tracks"].items()):
        lines.append(
            f"{track_id}: {summary['status']} ({summary['artifact_family']})"
        )
    if payload["notes"]:
        lines.append("notes:")
        lines.extend(f"- {note}" for note in payload["notes"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    sys.path.insert(0, str(repo_root / "src"))

    from polisyos.foundry.validation import (
        build_foundry_phase2_closure_report,
        default_foundry_phase2_manifest_path,
    )

    report = build_foundry_phase2_closure_report(
        repo_root=repo_root,
        manifest_path=(
            _resolve_path(args.manifest, repo_root=repo_root)
            if args.manifest is not None
            else default_foundry_phase2_manifest_path(repo_root=repo_root)
        ),
        acceptance_junit_xml=_resolve_path(args.junit_xml, repo_root=repo_root),
        benchmark_report=_resolve_path(args.benchmark_json, repo_root=repo_root),
        evidence_report=_resolve_path(args.evidence_json, repo_root=repo_root),
    )

    payload = {
        "assessment_id": ASSESSMENT_ID,
        "phase": "phase_2",
        "passes_all": report.overall_status == "complete",
        "phase2_closure": report.model_dump(mode="json"),
        "notes": list(report.notes),
    }

    rendered = (
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.output_format == "json"
        else _render_text(payload)
    )
    if args.output is not None:
        output_path = _resolve_path(args.output, repo_root=repo_root)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if payload["passes_all"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
