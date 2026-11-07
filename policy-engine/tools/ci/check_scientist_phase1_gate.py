#!/usr/bin/env python3
"""Validate the repo-tracked Scientist Phase 1 acceptance barrier."""

from __future__ import annotations

import argparse
import ast
import json
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal, TypedDict

from tools.lib.fs import (
    FileReadMeasurement,
    atomic_write_text,
    measure_file_reads,
    measured_is_dir,
    measured_read_bytes,
    measured_read_text,
)
from tools.lib.imports import ensure_repo_import_roots
from tools.lib.output import ToolMessage, ToolResult, format_tool_result

_REPO_ROOT_LIB, _SRC_ROOT = ensure_repo_import_roots(__file__, include_src_root=True)

from polisyos.scientist.validation.reliability_scorecard import (  # noqa: E402
    build_scientist_reliability_scorecard_from_evidence,
)

ASSESSMENT_ID = "scientist_phase1_gate"
MEASUREMENT_SCOPE = (
    "Partial coverage: supplied JUnit pass names and benchmark names, plus Python AST "
    "bare or unqualified Exception/BaseException handler syntax (including tuples) "
    "excluding structurally verified same-primary cleanup/reraise paths, and explicit "
    ".model_copy(deep=True) syntax. Cleanup recognition checks source control flow, "
    "not the behavior of opaque runtime callables. Unmeasured: execution "
    "provenance of those reports, benchmark performance, runtime receiver types, call "
    "reachability/hotness, copy necessity/cost, opaque aliases and dynamic arguments, "
    "qualified/aliased exception types, and allowlisted/excluded source."
)
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
    "src/polisyos/scientist/methods/autotune/execution_plan.py",
    "src/polisyos/scientist/methods/autotune/calibration.py",
    "src/polisyos/scientist/cross_graph/compiler.py",
    "src/polisyos/scientist/cross_graph/gatherers/academic.py",
    "src/polisyos/scientist/methods/search/funnel/level2_causal.py",
    "src/polisyos/scientist/nodes/builtins/decide/run_policy_translation.py",
    "src/polisyos/scientist/nodes/builtins/decide/run_translator_compliance.py",
    "src/polisyos/scientist/orchestration/workflows/builder.py",
)
DEFAULT_DEEP_COPY_ALLOWLIST = (
    "src/polisyos/scientist/orchestration/engine/state_branching.py",
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
        root = ET.fromstring(measured_read_bytes(path))
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
        payload = json.loads(measured_read_text(path))
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


def _is_broad_handler(handler: ast.ExceptHandler) -> bool:
    names = ast.walk(handler.type) if handler.type is not None else ()
    return handler.type is None or any(
        isinstance(item, ast.Name) and item.id in {"Exception", "BaseException"} for item in names
    )


def _is_same_primary_raise(node: ast.Raise, primary: str | None) -> bool:
    return node.cause is None and (
        node.exc is None
        or (primary is not None and isinstance(node.exc, ast.Name) and node.exc.id == primary)
    )


def _is_cleanup_note(statement: ast.stmt, primary: str, secondary: str | None) -> bool:
    if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
        return False
    call = statement.value
    if not (
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == primary
        and call.func.attr == "add_note"
        and len(call.args) == 1
        and not call.keywords
    ):
        return False
    note = call.args[0]
    if secondary is None or not isinstance(note, ast.JoinedStr):
        return False
    records_secondary_class = False
    for item in note.values:
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            continue
        if not (
            isinstance(item, ast.FormattedValue)
            and item.conversion == -1
            and item.format_spec is None
            and isinstance(item.value, ast.Attribute)
            and item.value.attr == "__name__"
            and isinstance(item.value.value, ast.Call)
            and isinstance(item.value.value.func, ast.Name)
            and item.value.value.func.id == "type"
            and not item.value.value.keywords
            and len(item.value.value.args) == 1
            and isinstance(item.value.value.args[0], ast.Name)
            and item.value.value.args[0].id == secondary
        ):
            return False
        records_secondary_class = True
    return records_secondary_class


def _cleanup_reraise_handlers(handler: ast.ExceptHandler) -> set[ast.ExceptHandler]:
    """Recognize a constrained no-recovery path without judging cleanup effects."""
    primary = handler.name
    for statement in handler.body:
        for node in ast.walk(statement):
            if isinstance(
                node,
                (
                    ast.Return,
                    ast.Break,
                    ast.Continue,
                    ast.Yield,
                    ast.YieldFrom,
                    ast.For,
                    ast.AsyncFor,
                    ast.While,
                    ast.comprehension,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                ),
            ):
                return set()
            if primary is not None and (
                (
                    isinstance(node, ast.Name)
                    and node.id == primary
                    and not isinstance(node.ctx, ast.Load)
                )
                or (isinstance(node, ast.ExceptHandler) and node.name == primary)
                or (
                    isinstance(node, (ast.Attribute, ast.Subscript))
                    and not isinstance(node.ctx, ast.Load)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == primary
                )
            ):
                return set()

    recognized: set[ast.ExceptHandler] = {handler}

    def preserves_primary(statements: Sequence[ast.stmt]) -> bool:
        if not statements:
            return False
        first, *rest = statements
        if isinstance(first, ast.Raise):
            return _is_same_primary_raise(first, primary)
        if isinstance(first, ast.Pass):
            return preserves_primary(rest)
        if not (
            primary is not None
            and isinstance(first, ast.Try)
            and len(first.handlers) == 1
            and all(
                isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)
                for statement in first.body
            )
            and not first.orelse
            and not first.finalbody
        ):
            return False
        cleanup = first.handlers[0]
        if cleanup.type is not None and not (
            isinstance(cleanup.type, ast.Name) and cleanup.type.id == "BaseException"
        ):
            return False
        if not cleanup.body or not all(
            _is_cleanup_note(statement, primary, cleanup.name) for statement in cleanup.body
        ):
            return False
        recognized.add(cleanup)
        return preserves_primary(rest)

    return recognized if preserves_primary(handler.body) else set()


def _classify_broad_handlers(
    repo_root: Path, targets: Sequence[str]
) -> tuple[list[str], list[str]]:
    findings: list[str] = []
    cleanup_reraises: list[str] = []
    for relative_path in targets:
        source_path = repo_root / relative_path
        tree = ast.parse(measured_read_text(source_path), filename=str(source_path))
        handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
        recognized = set().union(*(_cleanup_reraise_handlers(node) for node in handlers))
        for node in handlers:
            if _is_broad_handler(node):
                if node in recognized:
                    cleanup_reraises.append(f"{relative_path}:{node.lineno}")
                    continue
                findings.append(f"{relative_path}:{node.lineno}")
    return sorted(findings), sorted(cleanup_reraises)


def _scan_for_broad_handlers(repo_root: Path, targets: Sequence[str]) -> list[str]:
    return _classify_broad_handlers(repo_root, targets)[0]


class _DeepCopyScan(TypedDict):
    findings: list[str]
    unresolved_by_construction: list[dict[str, str | int]]
    source_files: list[str]
    excluded_paths: list[str]
    unmeasured: str


def _scan_for_explicit_deep_copy_calls(repo_root: Path, allowlist: set[str]) -> _DeepCopyScan:
    findings: list[str] = []
    unresolved: list[dict[str, str | int]] = []
    source_files: list[str] = []
    source_root = repo_root / "src/polisyos/scientist"
    if not measured_is_dir(source_root):
        raise ValueError(f"source root is unavailable: {source_root}")
    for source_path in sorted(source_root.rglob("*.py")):
        relative_path = str(source_path.relative_to(repo_root))
        if relative_path in allowlist:
            continue
        source_files.append(relative_path)
        tree = ast.parse(measured_read_text(source_path), filename=str(source_path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            is_model_copy = isinstance(node.func, ast.Attribute) and node.func.attr == "model_copy"
            deep = next((kw.value for kw in node.keywords if kw.arg == "deep"), None)
            literal_deep = isinstance(deep, ast.Constant) and deep.value is True
            if is_model_copy and literal_deep:
                findings.append(f"{relative_path}:{node.lineno}")
            elif (
                is_model_copy
                and (
                    (
                        deep is not None
                        and not (isinstance(deep, ast.Constant) and deep.value is False)
                    )
                    or any(kw.arg is None for kw in node.keywords)
                )
            ) or (not is_model_copy and literal_deep):
                unresolved.append(
                    {
                        "path": relative_path,
                        "line": node.lineno,
                        "class": "unresolved_by_construction",
                        "reason": "dynamic_deep_argument"
                        if is_model_copy
                        else "callable_target_unknown",
                    }
                )
    if not source_files:
        raise ValueError(f"no non-allowlisted Python source files: {source_root}")
    return {
        "findings": sorted(findings),
        "unresolved_by_construction": unresolved,
        "source_files": source_files,
        "excluded_paths": sorted(allowlist),
        "unmeasured": MEASUREMENT_SCOPE,
    }


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
    broad_handler_findings, cleanup_reraise_handlers = _classify_broad_handlers(
        repo_root, broad_exception_targets
    )
    deep_copy_scan = _scan_for_explicit_deep_copy_calls(repo_root, deep_copy_allowlist)
    deep_copy_findings = deep_copy_scan["findings"]
    ratchet_results = {
        "critical_broad_exception_targets_clean": not broad_handler_findings,
        "no_explicit_model_copy_deep_true": not deep_copy_findings,
        "no_unresolved_deep_copy_candidates": not deep_copy_scan["unresolved_by_construction"],
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
        *[
            f"unresolved_by_construction:{item}"
            for item in deep_copy_scan["unresolved_by_construction"]
        ],
    ]
    passes_all = (
        reliability.passes_all and all(test_results.values()) and all(ratchet_results.values())
    )
    return {
        "assessment_id": ASSESSMENT_ID,
        "status": "passed" if passes_all else "FAILED",
        "complete_verdict": True,
        "measurement_scope": MEASUREMENT_SCOPE,
        "passes_all": passes_all,
        "reliability_scorecard": reliability.to_dict(),
        "phase1_test_results": test_results,
        "required_cases": {key: list(value) for key, value in PHASE1_TEST_CASES.items()},
        "ratchet_results": ratchet_results,
        "broad_exception_findings": broad_handler_findings,
        "recognized_cleanup_reraise_handlers": cleanup_reraise_handlers,
        "deep_copy_findings": deep_copy_findings,
        "deep_copy_scan": deep_copy_scan,
        "broad_exception_targets": list(broad_exception_targets),
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


def _measurement_receipt(
    reads: FileReadMeasurement,
    payload: dict[str, object],
    *,
    broad_exception_targets: Sequence[str],
    deep_copy_allowlist: set[str],
) -> dict[str, object]:
    complete = payload.get("complete_verdict") is True
    receipt = reads.snapshot(complete_verdict=complete)
    scan = payload.get("deep_copy_scan")
    source_files = scan.get("source_files", []) if isinstance(scan, dict) else []
    receipt["selector"] = {
        "broad_exception_targets": list(broad_exception_targets),
        "deep_copy_source_root": "src/polisyos/scientist",
        "deep_copy_glob": "**/*.py",
        "excluded_paths": sorted(deep_copy_allowlist),
    }
    receipt["denominator"] = {
        "broad_exception_targets": list(broad_exception_targets),
        "deep_copy_source_files": source_files,
        "deep_copy_enumeration_completed": isinstance(scan, dict),
    }
    receipt["unresolved_by_construction"].extend(
        [
            "supplied_report_provenance: JUnit/benchmark names do not establish which "
            "source, inputs or backend executed, nor benchmark performance.",
            "unselected_or_qualified_handlers: only the selected files and bare or "
            "unqualified broad exception syntax are classified.",
            "opaque_cleanup_effects: source flow does not establish termination or "
            "exception-object effects of called cleanup, note or type implementations.",
            "runtime_copy_contract: receiver types, call reachability/hotness, copy "
            "necessity/cost, aliases and excluded paths are not decided by syntax.",
            "filesystem_visibility: selected glob members do not establish absence "
            "in inaccessible or unselected source trees.",
        ]
    )
    if not complete:
        receipt["unresolved_by_construction"].append(
            "input_scan_incomplete: failed reads/parses prevent a complete source/evidence verdict."
        )
    return receipt


def _phase1_result(payload: dict[str, object]) -> ToolResult:
    if payload.get("status") == "UNRUN":
        return ToolResult(
            tool="ci.check-scientist-phase1-gate",
            status="UNRUN",
            summary=f"No complete verdict: {payload.get('error')}. {MEASUREMENT_SCOPE}",
            exit_code=2,
            messages=(
                ToolMessage(
                    level="error",
                    message=str(payload.get("error")),
                    rule_id="SCIENTIST_PHASE1_INPUT",
                ),
            ),
            data=payload,
        )
    notes = payload.get("notes")
    missing = list(notes) if isinstance(notes, list) else []
    status = "ok" if payload.get("passes_all") else "failed"
    summary = (
        "Scientist Phase 1 supplied-evidence and source-syntax checks passed. "
        if status == "ok"
        else "Scientist Phase 1 supplied-evidence or source-syntax checks FAILED. "
    ) + MEASUREMENT_SCOPE
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


def _render_payload(
    payload: dict[str, object], output_format: Literal["text", "json", "junit"]
) -> str:
    if output_format == "json":
        return json.dumps(payload, indent=2, sort_keys=True)
    rendered = format_tool_result(_phase1_result(payload), output_format=output_format)
    measurement = json.dumps(payload["measurement"], sort_keys=True)
    if output_format == "text":
        return f"{rendered}measurement: {measurement}\n"
    suite = ET.fromstring(rendered)
    if payload.get("status") == "UNRUN":
        for failure in suite.iter("failure"):
            failure.tag = "error"
        suite.set("errors", suite.get("failures", "0"))
        suite.set("failures", "0")
    ET.SubElement(suite, "system-out").text = measurement
    return ET.tostring(suite, encoding="unicode") + "\n"


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
        help="Optional override for Python paths excluded from the deep-copy syntax scan.",
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

    with measure_file_reads(args.repo_root.resolve()) as reads:
        try:
            payload = _build_payload(
                benchmark_json=args.benchmark_json,
                junit_xml=args.junit_xml,
                repo_root=args.repo_root.resolve(),
                broad_exception_targets=broad_exception_targets,
                deep_copy_allowlist=deep_copy_allowlist,
            )
        except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
            payload = {
                "assessment_id": ASSESSMENT_ID,
                "status": "UNRUN",
                "complete_verdict": False,
                "passes_all": False,
                "error": str(exc),
                "measurement_scope": MEASUREMENT_SCOPE,
            }
        payload["measurement"] = _measurement_receipt(
            reads,
            payload,
            broad_exception_targets=broad_exception_targets,
            deep_copy_allowlist=deep_copy_allowlist,
        )

    _emit(_render_payload(payload, args.output_format), output=args.output)
    if args.output is not None:
        print(_phase1_result(payload).summary)

    if payload.get("status") == "UNRUN":
        return 2
    if args.require_passing and not bool(payload.get("passes_all")):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
