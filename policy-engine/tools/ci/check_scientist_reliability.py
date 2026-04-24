#!/usr/bin/env python3
"""Assemble the Scientist Gate 2 reliability scorecard from CI evidence."""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools._lib.fs import atomic_write_text
from tools._lib.imports import ensure_repo_import_roots
from tools._lib.output import ToolMessage, ToolResult, format_tool_result

_REPO_ROOT_LIB, _SRC_ROOT = ensure_repo_import_roots(__file__, include_src_root=True)

from polisyos.scientist.reliability_scorecard import (  # noqa: E402
    build_scientist_reliability_scorecard_from_evidence,
)


def _load_benchmark_names(path: Path) -> set[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid pytest-benchmark JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"pytest-benchmark payload must be an object: {path}")
    benchmarks = payload.get("benchmarks")
    if not isinstance(benchmarks, list):
        raise ValueError(f"pytest-benchmark payload 'benchmarks' must be a list: {path}")

    names: set[str] = set()
    for index, item in enumerate(benchmarks):
        if not isinstance(item, dict):
            raise ValueError(f"benchmark entry {index} in {path} must be an object")
        name = str(item.get("name") or "").strip()
        if not name:
            raise ValueError(f"benchmark entry {index} in {path} is missing name")
        names.add(name)
    return names


def _iter_suites(root: ET.Element) -> Iterable[ET.Element]:
    if root.tag == "testsuite":
        yield root
        return
    if root.tag == "testsuites":
        yield from root.findall("testsuite")
        return
    raise ValueError(f"unsupported JUnit root element: {root.tag}")


def _load_passed_test_cases(path: Path) -> set[str]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"invalid JUnit XML: {path}") from exc

    passed: set[str] = set()
    for suite in _iter_suites(root):
        for testcase in suite.findall("testcase"):
            if testcase.find("failure") is not None or testcase.find("error") is not None:
                continue
            if testcase.find("skipped") is not None:
                continue
            name = testcase.attrib.get("name", "").strip()
            classname = testcase.attrib.get("classname", "").strip()
            if name:
                passed.add(name)
            if classname and name:
                passed.add(f"{classname}::{name}")
    return passed


def _scorecard_payload(
    benchmark_json: Path,
    junit_xml: Sequence[Path],
) -> dict[str, object]:
    benchmark_names = _load_benchmark_names(benchmark_json)
    passed_cases: set[str] = set()
    for path in junit_xml:
        passed_cases.update(_load_passed_test_cases(path))

    scorecard = build_scientist_reliability_scorecard_from_evidence(
        passed_test_cases=passed_cases,
        benchmark_names=benchmark_names,
    )
    payload = scorecard.to_dict()
    payload["assessment_id"] = "scientist_gate2_reliability"
    payload["benchmark_sources"] = [str(benchmark_json)]
    payload["junit_sources"] = [str(path) for path in junit_xml]
    return payload


def _scorecard_result(payload: dict[str, object]) -> ToolResult:
    notes = payload.get("notes")
    failures = list(notes) if isinstance(notes, list) else []
    status = "ok" if payload.get("passes_all") else "failed"
    summary = (
        "Scientist reliability scorecard passes all Gate 2 requirements"
        if status == "ok"
        else "Scientist reliability scorecard is missing required Gate 2 evidence"
    )
    messages = tuple(
        ToolMessage(
            level="error"
            if failure.startswith(("scenario_missing", "benchmark_missing", "operational_gap"))
            else "warning",
            message=str(failure),
            rule_id="SCIENTIST_RELIABILITY_GATE",
        )
        for failure in failures
    )
    return ToolResult(
        tool="ci.check-scientist-reliability",
        status=status,
        summary=summary,
        exit_code=0 if status == "ok" else 1,
        messages=messages,
        data=payload,
    )


def _emit(content: str, *, output: Path | None) -> None:
    if output is not None:
        atomic_write_text(output, content if content.endswith("\n") else content + "\n")
        return
    sys.stdout.write(content)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the Scientist Gate 2 reliability scorecard from CI evidence.",
    )
    parser.add_argument("--benchmark-json", type=Path, required=True)
    parser.add_argument(
        "--junit-xml",
        type=Path,
        action="append",
        required=True,
        help="One or more JUnit XML reports covering scenario and operational evidence.",
    )
    parser.add_argument("--output", type=Path, help="Optional output file path.")
    parser.add_argument(
        "--output-format",
        choices=("text", "json", "junit"),
        default="json",
    )
    parser.add_argument(
        "--require-passing",
        action="store_true",
        help="Exit non-zero when the scorecard does not pass all required gates.",
    )
    args = parser.parse_args(argv)

    try:
        payload = _scorecard_payload(args.benchmark_json, args.junit_xml)
    except ValueError as exc:
        result = ToolResult.failed(
            "ci.check-scientist-reliability",
            str(exc),
            exit_code=2,
        )
        if args.output_format == "json":
            _emit(
                json.dumps(
                    {
                        "assessment_id": "scientist_gate2_reliability",
                        "error": str(exc),
                    },
                    indent=2,
                    sort_keys=True,
                ),
                output=args.output,
            )
        else:
            _emit(format_tool_result(result, output_format=args.output_format), output=args.output)
        return 2

    if args.output_format == "json":
        _emit(json.dumps(payload, indent=2, sort_keys=True), output=args.output)
    else:
        _emit(
            format_tool_result(_scorecard_result(payload), output_format=args.output_format),
            output=args.output,
        )

    if args.require_passing and not bool(payload.get("passes_all")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
