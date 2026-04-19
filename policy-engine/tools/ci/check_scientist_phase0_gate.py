#!/usr/bin/env python3
"""Validate the repo-tracked Scientist Phase 0 acceptance barrier."""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from pathlib import Path

from tools._lib.fs import atomic_write_text
from tools._lib.output import ToolMessage, ToolResult, format_tool_result

ASSESSMENT_ID = "scientist_phase0_gate"
REQUIRED_PHASE0_CASES: dict[str, tuple[str, ...]] = {
    "async_lifecycle": (
        "test_timeout_worker_does_not_swallow_system_exit",
        "test_worker_runtime_error_surfaces_on_future",
        "test_measure_acquire_does_not_swallow_assertion_errors",
        "test_detect_stale_runtime_probe_error_returns_false",
        "test_detect_stale_returns_false_on_runtime_probe_error",
    ),
    "idempotency": (
        "test_retry_after_header_and_idempotency_key_are_reused",
        "test_idempotency_key_is_added_even_without_retry_budget",
        "test_compute_idempotency_key_stable_for_same_inputs",
        "test_compute_idempotency_key_changes_on_artifact_change",
    ),
    "budget_accounting": (
        "test_post_record_falls_back_to_reserved_cost_when_accounting_breaks",
        "test_parallel_calls_do_not_overspend_reserved_budget",
        "test_releases_reservation_when_generate_raises",
        "test_releases_reservation_when_task_is_cancelled",
        "test_actual_cost_commit_reconciles_estimate_delta",
    ),
    "masking_fail_closed": (
        "test_masking_raises_when_target_metric_is_missing",
        "test_masking_raises_when_intervention_step_exceeds_metric_horizon",
    ),
    "foundry_env_hardening": (
        "test_rejects_control_characters_in_env_values",
        "test_sets_and_restores_sanitized_env_values",
    ),
    "statistical_hotfixes": (
        "test_rmse_ci_bootstraps_rmse_directly",
        "test_equal_propensity",
        "test_iid_data",
        "test_spearman_uses_average_ranks_for_ties",
    ),
}


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


def _build_payload(junit_xml: Sequence[Path]) -> dict[str, object]:
    passed_cases: set[str] = set()
    for path in junit_xml:
        passed_cases.update(_load_passed_test_cases(path))

    category_results = {
        category: all(case in passed_cases for case in cases)
        for category, cases in REQUIRED_PHASE0_CASES.items()
    }
    missing_cases = [
        f"{category}:{case}"
        for category, cases in REQUIRED_PHASE0_CASES.items()
        for case in cases
        if case not in passed_cases
    ]
    return {
        "assessment_id": ASSESSMENT_ID,
        "passes_all": all(category_results.values()),
        "category_results": category_results,
        "required_cases": {key: list(value) for key, value in REQUIRED_PHASE0_CASES.items()},
        "junit_sources": [str(path) for path in junit_xml],
        "notes": missing_cases,
    }


def _phase0_result(payload: dict[str, object]) -> ToolResult:
    notes = payload.get("notes")
    missing = list(notes) if isinstance(notes, list) else []
    status = "ok" if payload.get("passes_all") else "failed"
    summary = (
        "Scientist Phase 0 acceptance barrier has complete repo-tracked evidence"
        if status == "ok"
        else "Scientist Phase 0 acceptance barrier is missing required evidence"
    )
    messages = tuple(
        ToolMessage(
            level="error",
            message=str(item),
            rule_id="SCIENTIST_PHASE0_GATE",
        )
        for item in missing
    )
    return ToolResult(
        tool="ci.check-scientist-phase0-gate",
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
        description="Build the Scientist Phase 0 acceptance barrier from JUnit evidence.",
    )
    parser.add_argument(
        "--junit-xml",
        type=Path,
        action="append",
        required=True,
        help="One or more JUnit XML reports covering the required Phase 0 regressions.",
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
        help="Exit non-zero when the acceptance barrier is incomplete.",
    )
    args = parser.parse_args(argv)

    try:
        payload = _build_payload(args.junit_xml)
    except ValueError as exc:
        result = ToolResult.failed(
            "ci.check-scientist-phase0-gate",
            str(exc),
            exit_code=2,
        )
        if args.output_format == "json":
            _emit(
                json.dumps(
                    {"assessment_id": ASSESSMENT_ID, "error": str(exc)},
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
            format_tool_result(_phase0_result(payload), output_format=args.output_format),
            output=args.output,
        )

    if args.require_passing and not bool(payload.get("passes_all")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
