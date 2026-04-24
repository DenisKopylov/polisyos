#!/usr/bin/env python3
"""Validate the repo-tracked Scientist Phase 1 acceptance barrier."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from pathlib import Path

from tools._lib.fs import atomic_write_text
from tools._lib.imports import ensure_repo_import_roots
from tools._lib.output import ToolMessage, ToolResult, format_tool_result

_REPO_ROOT_LIB, _SRC_ROOT = ensure_repo_import_roots(__file__, include_src_root=True)

from polisyos.scientist.reliability_scorecard import (  # noqa: E402
    build_scientist_reliability_scorecard_from_evidence,
)

ASSESSMENT_ID = "scientist_phase1_gate"
PHASE1_TEST_CASES: dict[str, tuple[str, ...]] = {
    "machine_readable_status": (
        "test_scientist_remediation_status_report_covers_all_workstreams",
        "test_scientist_remediation_status_report_is_machine_readable",
        "test_scientist_remediation_status_report_marks_all_workstreams_done",
    ),
    "error_semantics_tranche": (
        "test_extract_data_needs_json_parse_assertion_is_not_swallowed",
        "test_catalog_lookup_assertion_is_not_swallowed",
        "test_cas_norm_loader_assertion_is_not_swallowed",
        "test_create_drafter_agent_rag_assertion_is_not_swallowed",
        "TestBuildConstitution::test_assertion_is_not_swallowed",
        "TestAgentFallbackChain::test_assertion_is_not_swallowed",
        "test_parallel_assertion_is_not_swallowed",
        "test_load_allowed_modules_assertion_is_not_swallowed",
        "test_supervisor_provenance_export_assertion_is_not_swallowed",
        "test_rag_build_from_cas_manifest_assertion_is_not_swallowed",
        "test_cross_graph_compiler_legal_assertion_is_not_swallowed",
        "test_serialize_value_assertion_is_not_swallowed",
        "test_with_topology_mutation_does_not_swallow_registry_assertion",
        "test_coerce_context_data_does_not_swallow_assertion",
    ),
    "branch_state_tranche": (
        "test_apply_to_config_uses_branch_local_nested_model_clones",
        "test_policy_translation_uses_branch_state_for_declared_outputs",
        "test_translator_compliance_uses_branch_state_for_declared_outputs",
        "test_workflow_runners_use_branch_local_snapshot_state",
        "test_ledger_mutation_uses_copy_on_write_budget_state",
    ),
}
DEFAULT_BROAD_EXCEPTION_TARGETS = (
    "src/polisyos/scientist/agent/code_verifier.py",
    "src/polisyos/scientist/agent/data_need_extractor.py",
    "src/polisyos/scientist/agent/drafter_factory.py",
    "src/polisyos/scientist/agent/_drafter_formatting.py",
    "src/polisyos/scientist/agent/router.py",
    "src/polisyos/scientist/agent/supervisor.py",
    "src/polisyos/scientist/agent/rag.py",
    "src/polisyos/scientist/agent/norm_loader.py",
    "src/polisyos/scientist/autotune/execution_plan.py",
    "src/polisyos/scientist/autotune/calibration.py",
    "src/polisyos/scientist/cross_graph/compiler.py",
    "src/polisyos/scientist/cross_graph/gatherers/academic.py",
    "src/polisyos/scientist/search/funnel/level2_causal.py",
    "src/polisyos/scientist/nodes/builtins/decide/run_policy_translation.py",
    "src/polisyos/scientist/nodes/builtins/decide/run_translator_compliance.py",
    "src/polisyos/scientist/workflows/builder.py",
)
DEFAULT_DEEP_COPY_ALLOWLIST = (
    "src/polisyos/scientist/engine/state_branching.py",
    "src/polisyos/scientist/remediation_status.py",
)


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


def _scan_for_broad_handlers(repo_root: Path, targets: Sequence[str]) -> list[str]:
    findings: list[str] = []
    pattern = re.compile(r"except\s+Exception\b")
    for relative_path in targets:
        source_path = (repo_root / relative_path).resolve()
        if not source_path.exists():
            findings.append(f"missing_target:{relative_path}")
            continue
        for line_number, line in enumerate(
            source_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if pattern.search(line):
                findings.append(f"{relative_path}:{line_number}")
    return findings


def _scan_for_live_deep_copy_calls(repo_root: Path, allowlist: set[str]) -> list[str]:
    findings: list[str] = []
    for source_path in (repo_root / "src/polisyos/scientist").rglob("*.py"):
        relative_path = str(source_path.relative_to(repo_root))
        if relative_path in allowlist:
            continue
        for line_number, line in enumerate(
            source_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if "model_copy(deep=True)" in line:
                findings.append(f"{relative_path}:{line_number}")
    return findings


def _build_payload(
    *,
    benchmark_json: Path,
    junit_xml: Sequence[Path],
    repo_root: Path,
    broad_exception_targets: Sequence[str],
    deep_copy_allowlist: set[str],
) -> dict[str, object]:
    benchmark_names = _load_benchmark_names(benchmark_json)
    passed_cases: set[str] = set()
    for path in junit_xml:
        passed_cases.update(_load_passed_test_cases(path))

    reliability = build_scientist_reliability_scorecard_from_evidence(
        passed_test_cases=passed_cases,
        benchmark_names=benchmark_names,
    )
    test_results = {
        category: all(_has_case(passed_cases, case) for case in cases)
        for category, cases in PHASE1_TEST_CASES.items()
    }
    broad_handler_findings = _scan_for_broad_handlers(repo_root, broad_exception_targets)
    deep_copy_findings = _scan_for_live_deep_copy_calls(repo_root, deep_copy_allowlist)
    ratchet_results = {
        "critical_broad_exception_targets_clean": not broad_handler_findings,
        "no_live_model_copy_deep_true_hot_paths": not deep_copy_findings,
    }

    notes = [
        *[
            f"{category}:{case}"
            for category, cases in PHASE1_TEST_CASES.items()
            for case in cases
            if not _has_case(passed_cases, case)
        ],
        *[f"reliability:{note}" for note in reliability.notes],
        *[f"broad_exception:{item}" for item in broad_handler_findings],
        *[f"deep_copy:{item}" for item in deep_copy_findings],
    ]

    return {
        "assessment_id": ASSESSMENT_ID,
        "passes_all": reliability.passes_all
        and all(test_results.values())
        and all(ratchet_results.values()),
        "reliability_scorecard": reliability.to_dict(),
        "phase1_test_results": test_results,
        "required_cases": {key: list(value) for key, value in PHASE1_TEST_CASES.items()},
        "ratchet_results": ratchet_results,
        "broad_exception_findings": broad_handler_findings,
        "deep_copy_findings": deep_copy_findings,
        "benchmark_source": str(benchmark_json),
        "junit_sources": [str(path) for path in junit_xml],
        "notes": notes,
    }


def _has_case(passed_cases: set[str], required_case: str) -> bool:
    return any(_matches_required_case(item, required_case) for item in passed_cases)


def _matches_required_case(observed_case: str, required_case: str) -> bool:
    if observed_case == required_case or observed_case.startswith(f"{required_case}["):
        return True
    if "::" in required_case:
        return observed_case.endswith(required_case) or f"{required_case}[" in observed_case
    class_scoped_required = f"::{required_case}"
    return (
        observed_case.endswith(class_scoped_required)
        or f"{class_scoped_required}[" in observed_case
    )


def _phase1_result(payload: dict[str, object]) -> ToolResult:
    notes = payload.get("notes")
    missing = list(notes) if isinstance(notes, list) else []
    status = "ok" if payload.get("passes_all") else "failed"
    summary = (
        "Scientist Phase 1 acceptance barrier has complete repo-tracked evidence"
        if status == "ok"
        else "Scientist Phase 1 acceptance barrier is missing required evidence"
    )
    messages = tuple(
        ToolMessage(
            level="error",
            message=str(item),
            rule_id="SCIENTIST_PHASE1_GATE",
        )
        for item in missing
    )
    return ToolResult(
        tool="ci.check-scientist-phase1-gate",
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
        description="Build the Scientist Phase 1 acceptance barrier from CI evidence.",
    )
    parser.add_argument("--benchmark-json", type=Path, required=True)
    parser.add_argument(
        "--junit-xml",
        type=Path,
        action="append",
        required=True,
        help="One or more JUnit XML reports covering the required Phase 1 regressions.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root used for source ratchet scans.",
    )
    parser.add_argument(
        "--broad-exception-target",
        action="append",
        dest="broad_exception_targets",
        default=None,
        help="Optional override for the critical source files that must remain free of broad handlers.",
    )
    parser.add_argument(
        "--deep-copy-allowlist",
        action="append",
        default=None,
        help="Optional override for source files allowed to mention model_copy(deep=True).",
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

    broad_exception_targets = tuple(args.broad_exception_targets or DEFAULT_BROAD_EXCEPTION_TARGETS)
    deep_copy_allowlist = set(args.deep_copy_allowlist or DEFAULT_DEEP_COPY_ALLOWLIST)

    try:
        payload = _build_payload(
            benchmark_json=args.benchmark_json,
            junit_xml=args.junit_xml,
            repo_root=args.repo_root.resolve(),
            broad_exception_targets=broad_exception_targets,
            deep_copy_allowlist=deep_copy_allowlist,
        )
    except ValueError as exc:
        result = ToolResult.failed(
            "ci.check-scientist-phase1-gate",
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
            format_tool_result(_phase1_result(payload), output_format=args.output_format),
            output=args.output,
        )

    if args.require_passing and not bool(payload.get("passes_all")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
