#!/usr/bin/env python3
"""Generate Phase 2 synthetic-world and judge evidence from enrolled JUnit reports."""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="Phase 2 manifest path.")
    parser.add_argument(
        "--acceptance-junit-xml",
        type=Path,
        required=True,
        help="JUnit XML for the enrolled synthetic-world-backed acceptance tests.",
    )
    parser.add_argument(
        "--judge-junit-xml",
        type=Path,
        required=True,
        help="JUnit XML for the enrolled family-level judge verdict tests.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output JSON evidence report path.",
    )
    return parser


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_junit_xml(path: Path) -> tuple[set[str], set[str]]:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    all_tests: set[str] = set()
    passing: set[str] = set()
    for testcase in root.iter("testcase"):
        name = str(testcase.attrib.get("name", "")).strip()
        classname = str(testcase.attrib.get("classname", "")).strip()
        file_attr = str(testcase.attrib.get("file", "")).strip()
        base_name = name.split("[", 1)[0].strip() if name else ""
        variants = {value for value in (name, base_name) if value}
        name_variants = tuple(value for value in (name, base_name) if value)

        if classname and name_variants:
            for variant_name in name_variants:
                variants.add(f"{classname}::{variant_name}")

        if file_attr and name_variants:
            class_tail = classname.rsplit(".", 1)[-1] if classname else ""
            for variant_name in name_variants:
                variants.add(f"{file_attr}::{variant_name}")
                if class_tail and class_tail != Path(file_attr).stem:
                    variants.add(f"{file_attr}::{class_tail}::{variant_name}")

        if classname and name_variants:
            parts = [part for part in classname.split(".") if part]
            for index in range(len(parts), 0, -1):
                module_path = "/".join(parts[:index]) + ".py"
                remainder = parts[index:]
                for variant_name in name_variants:
                    variants.add(f"{module_path}::{variant_name}")
                    if remainder:
                        variants.add(f"{module_path}::{'::'.join(remainder)}::{variant_name}")
        failed = any(child.tag in {"failure", "error"} for child in testcase)
        skipped = any(child.tag == "skipped" for child in testcase)
        for variant in variants:
            if not variant:
                continue
            all_tests.add(variant)
            if not failed and not skipped:
                passing.add(variant)
    return all_tests, passing


def _status(name: str, *, all_tests: set[str], passing: set[str]) -> str | None:
    if name not in all_tests:
        return None
    return "pass" if name in passing else "fail"


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    manifest = _load_json(args.manifest.resolve())
    acceptance_all, acceptance_passing = _parse_junit_xml(args.acceptance_junit_xml.resolve())
    judge_all, judge_passing = _parse_junit_xml(args.judge_junit_xml.resolve())

    evidence_tracks: dict[str, Any] = {}
    for track in manifest.get("tracks", []):
        if not isinstance(track, dict):
            continue
        track_id = str(track.get("track_id") or "").strip()
        if not track_id:
            continue
        synthetic_statuses: dict[str, str] = {}
        for check_id in track.get("required_synthetic_world_checks", []):
            status = _status(str(check_id), all_tests=acceptance_all, passing=acceptance_passing)
            if status is not None:
                synthetic_statuses[str(check_id)] = status
        judge_statuses: dict[str, Any] = {}
        for verdict_id in track.get("required_judge_verdicts", []):
            status = _status(str(verdict_id), all_tests=judge_all, passing=judge_passing)
            if status is None:
                continue
            judge_statuses[str(verdict_id)] = (
                {"composite_decision": "promote"} if status == "pass" else {"composite_decision": "reject"}
            )
        evidence_tracks[track_id] = {
            "synthetic_world_checks": synthetic_statuses,
            "judge_verdicts": judge_statuses,
        }

    payload = {
        "phase_id": str(manifest.get("phase_id") or "foundry.phase2"),
        "tracks": evidence_tracks,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
