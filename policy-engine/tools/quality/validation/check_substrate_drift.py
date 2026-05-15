#!/usr/bin/env python3
"""Audit Wave 0 Honest Diagnostics substrate drift guards."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.honest_diagnostics_substrate_drift.v1"
TOOL_NAME = "quality.validation.check-substrate-drift"

DEFAULT_SCAN_PATHS = (
    Path("tests/unit/runtime/quality/test_authority_envelope_contract.py"),
    Path("tests/unit/runtime/quality/test_diagnostic_event_contract.py"),
    Path("tests/unit/tools/test_canary_evidence_authority.py"),
    Path("tests/repo_quality/tools/test_honest_diagnostics_substrate_red_controls.py"),
    Path("tests/repo_quality/tools/test_runtime_quality_contract_fixtures.py"),
    Path("tests/repo_quality/tools/test_production_invariant_registry.py"),
    Path("tests/repo_quality/tools/test_honest_diagnostics_decision_log.py"),
    Path("tests/repo_quality/tools/test_honest_diagnostics_coverage.py"),
    Path("tests/repo_quality/tools/test_honest_diagnostics_substrate_drift.py"),
    Path("tools/quality/validation/build_honest_diagnostics_coverage.py"),
    Path("tools/quality/validation/compare_honest_diagnostics_rebaseline.py"),
    Path("tools/quality/validation/check_substrate_drift.py"),
    Path("architecture/production_quality/invariant_registry.toml"),
    Path("docs/system-design-decisions/honest-diagnostics-substrate-decision-log.md"),
)

ALLOW_FALLBACK_RE = re.compile(
    r"\ballow_[A-Za-z0-9_]*fallback\b\s*(?:=|:)\s*(?:True|true)\b"
)
FIXTURE_SERIOUS_MARKERS = (
    "fixture_serious_consumption_allowed",
    "fixture_satisfies_serious_closeout",
    "fixture serious consumption allowed",
)
WARN_CLOSEOUT_MARKERS = (
    "warn_closeout_acceptance_allowed",
    "warn_satisfies_serious_closeout",
    "warn closeout acceptance allowed",
)
ADR_SOFTENING_MARKERS = (
    "adr_softening_allowed",
    "adr_0147_decision_softened",
    "adr-0147 decision softened",
    "adr-0148 decision softened",
    "adr-0149 decision softened",
    "adr-0150 decision softened",
    "adr-0151 decision softened",
    "adr-0152 decision softened",
    "adr-0153 decision softened",
    "adr-0154 decision softened",
    "adr-0155 decision softened",
)
NON_GOAL_MARKERS = (
    "hds_non_goal_violation",
    "non_goal_violation_allowed",
    "non-goal violation allowed",
)
TEXT_MARKER_EXEMPT_PATHS = {
    "tools/quality/validation/check_substrate_drift.py",
    "tests/repo_quality/tools/test_honest_diagnostics_substrate_drift.py",
}


@dataclass(frozen=True)
class DriftViolation:
    code: str
    path: str
    line: int
    message: str

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "path": self.path,
            "line": self.line,
            "message": self.message,
        }


def build_substrate_drift_payload(
    *,
    repo_root: Path = REPO_ROOT,
    scan_paths: Sequence[Path] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    paths = list(scan_paths) if scan_paths is not None else list(DEFAULT_SCAN_PATHS)
    counters = {
        "xfail_strict_count": 0,
        "xfail_non_strict_count": 0,
        "skip_count_substrate_tests": 0,
        "allow_fallback_count": 0,
        "fixture_serious_consumption_count": 0,
        "warn_closeout_acceptance_count": 0,
    }
    adr_softening_findings: list[dict[str, object]] = []
    non_goal_violations: list[dict[str, object]] = []
    violations: list[DriftViolation] = []
    scanned: list[str] = []

    for raw_path in paths:
        path = _resolve(repo_root, raw_path)
        rel = _rel(path, repo_root)
        if not path.exists():
            violations.append(
                DriftViolation(
                    code="hds_scan_path_missing",
                    path=rel,
                    line=1,
                    message="HDS anti-drift scan path does not exist.",
                )
            )
            continue
        if path.is_dir():
            file_paths = sorted(item for item in path.rglob("*") if item.is_file())
        else:
            file_paths = [path]

        for file_path in file_paths:
            if file_path.suffix not in {".py", ".md", ".toml"}:
                continue
            text = file_path.read_text(encoding="utf-8")
            file_rel = _rel(file_path, repo_root)
            scanned.append(file_rel)
            if file_path.suffix == ".py":
                _audit_python_source(
                    text=text,
                    path=file_rel,
                    counters=counters,
                    violations=violations,
                )
            if file_rel not in TEXT_MARKER_EXEMPT_PATHS:
                _audit_text_source(
                    text=text,
                    path=file_rel,
                    counters=counters,
                    adr_softening_findings=adr_softening_findings,
                    non_goal_violations=non_goal_violations,
                    violations=violations,
                )

    status = "fail" if violations or adr_softening_findings or non_goal_violations else "pass"
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "status": status,
        "repo_root": str(repo_root),
        "scan_paths": scanned,
        **counters,
        "adr_softening_findings": adr_softening_findings,
        "non_goal_violations": non_goal_violations,
        "violations": [violation.as_dict() for violation in violations],
    }


def dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"{TOOL_NAME}: {payload['status']}",
        (
            "strict_xfail={xfail_strict_count} non_strict_xfail={xfail_non_strict_count} "
            "skips={skip_count_substrate_tests} allow_fallback={allow_fallback_count} "
            "fixture_serious={fixture_serious_consumption_count} "
            "warn_closeout={warn_closeout_acceptance_count} "
            "adr_softening={adr_count} non_goals={non_goal_count}"
        ).format(
            **payload,
            adr_count=len(payload["adr_softening_findings"]),
            non_goal_count=len(payload["non_goal_violations"]),
        ),
    ]
    for violation in payload.get("violations", []):
        if not isinstance(violation, dict):
            continue
        lines.append(
            "[fail] {path}:{line} {code}: {message}".format(**violation)
        )
    return "\n".join(lines) + "\n"


def _audit_python_source(
    *,
    text: str,
    path: str,
    counters: dict[str, int],
    violations: list[DriftViolation],
) -> None:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        violations.append(
            DriftViolation(
                code="hds_scan_python_syntax_error",
                path=path,
                line=exc.lineno or 1,
                message=f"Could not parse HDS Python source: {exc.msg}",
            )
        )
        return

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        mark_name = _pytest_mark_name(node)
        if mark_name == "xfail":
            if _call_has_strict_true(node):
                counters["xfail_strict_count"] += 1
            else:
                counters["xfail_non_strict_count"] += 1
                violations.append(
                    DriftViolation(
                        code="hds_non_strict_xfail",
                        path=path,
                        line=getattr(node, "lineno", 1),
                        message="HDS red controls must use strict xfail markers.",
                    )
                )
        if mark_name in {"skip", "skipif"}:
            counters["skip_count_substrate_tests"] += 1
            violations.append(
                DriftViolation(
                    code="hds_permanent_skip",
                    path=path,
                    line=getattr(node, "lineno", 1),
                    message="HDS substrate tests must not use skip or broad module skips.",
                )
            )


def _audit_text_source(
    *,
    text: str,
    path: str,
    counters: dict[str, int],
    adr_softening_findings: list[dict[str, object]],
    non_goal_violations: list[dict[str, object]],
    violations: list[DriftViolation],
) -> None:
    for match in ALLOW_FALLBACK_RE.finditer(text):
        counters["allow_fallback_count"] += 1
        violations.append(
            DriftViolation(
                code="hds_fallback_allowance_without_registry",
                path=path,
                line=_line_number(text, match.start()),
                message="New HDS fallback allowance requires registry and decision-log permission.",
            )
        )

    for line, marker in _marker_hits(text, FIXTURE_SERIOUS_MARKERS):
        counters["fixture_serious_consumption_count"] += 1
        violations.append(
            DriftViolation(
                code="hds_fixture_serious_consumption",
                path=path,
                line=line,
                message=f"Fixture serious closeout marker is forbidden: {marker}.",
            )
        )
    for line, marker in _marker_hits(text, WARN_CLOSEOUT_MARKERS):
        counters["warn_closeout_acceptance_count"] += 1
        violations.append(
            DriftViolation(
                code="hds_warn_closeout_acceptance",
                path=path,
                line=line,
                message=f"Warn closeout acceptance marker is forbidden: {marker}.",
            )
        )
    for line, marker in _marker_hits(text, ADR_SOFTENING_MARKERS):
        finding = {
            "code": "hds_adr_softening",
            "path": path,
            "line": line,
            "message": f"ADR softening marker is forbidden without superseding ADR: {marker}.",
        }
        adr_softening_findings.append(finding)
        violations.append(
            DriftViolation(
                code=str(finding["code"]),
                path=path,
                line=line,
                message=str(finding["message"]),
            )
        )
    for line, marker in _marker_hits(text, NON_GOAL_MARKERS):
        finding = {
            "code": "hds_non_goal_violation",
            "path": path,
            "line": line,
            "message": f"HDS non-goal violation marker is forbidden: {marker}.",
        }
        non_goal_violations.append(finding)
        violations.append(
            DriftViolation(
                code=str(finding["code"]),
                path=path,
                line=line,
                message=str(finding["message"]),
            )
        )


def _pytest_mark_name(call: ast.Call) -> str | None:
    func = call.func
    if not isinstance(func, ast.Attribute):
        return None
    name = func.attr
    if name not in {"xfail", "skip", "skipif"}:
        return None
    return name


def _call_has_strict_true(call: ast.Call) -> bool:
    for keyword in call.keywords:
        if keyword.arg != "strict":
            continue
        return isinstance(keyword.value, ast.Constant) and keyword.value.value is True
    return False


def _marker_hits(text: str, markers: Iterable[str]) -> list[tuple[int, str]]:
    lowered = text.casefold()
    hits: list[tuple[int, str]] = []
    for marker in markers:
        start = 0
        marker_lower = marker.casefold()
        while True:
            index = lowered.find(marker_lower, start)
            if index < 0:
                break
            hits.append((_line_number(text, index), marker))
            start = index + len(marker_lower)
    return hits


def _line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    parser.add_argument("--require-passing", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    payload = build_substrate_drift_payload(repo_root=repo_root)
    rendered = dump_json(payload) if args.output_format == "json" else render_text(payload)
    if args.json_output is not None:
        atomic_write_text(_resolve(repo_root, args.json_output), dump_json(payload))
    else:
        sys.stdout.write(rendered)
    if args.require_passing and payload["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
