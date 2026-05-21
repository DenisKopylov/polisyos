#!/usr/bin/env python3
"""Audit Wave 0 Honest Diagnostics substrate drift guards."""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.honest_diagnostics_substrate_drift.v1"
TOOL_NAME = "quality.validation.check-substrate-drift"

DEFAULT_SCAN_PATHS = (
    Path("tests/unit/runtime/quality"),
    Path("tests/unit/tools/test_canary_evidence_authority.py"),
    Path("tests/repo_quality/tools/test_honest_diagnostics*.py"),
    Path("tests/repo_quality/tools/test_inventory_legacy_quality_evidence.py"),
    Path("tests/repo_quality/tools/test_runtime_quality_contract_fixtures.py"),
    Path("tests/repo_quality/tools/test_production_invariant_registry.py"),
    Path("src/polisyos/runtime/quality"),
    Path("tools/quality/validation"),
    Path("architecture/production_quality"),
    Path("schemas/runtime_quality"),
    Path("docs/adr/014[7-9]-*.md"),
    Path("docs/adr/015[0-5]-*.md"),
    Path("docs/system-design-decisions/honest-diagnostics-substrate*.md"),
    Path("docs/plans/archive/*policyos-honest-diagnostics-substrate-implementation-plan.md"),
    Path("architecture/production_quality/ci_tiers.toml"),
)
DEFAULT_CI_TIERS = Path("architecture/production_quality/ci_tiers.toml")
DEFAULT_INVARIANT_REGISTRY = Path("architecture/production_quality/invariant_registry.toml")
DEFAULT_DECISION_LOG = Path(
    "docs/system-design-decisions/honest-diagnostics-substrate-decision-log.md"
)
ALLOWED_CI_TIERS = frozenset({"fast-pr", "integration-pr", "nightly", "weekly-closeout"})

ALLOW_FALLBACK_RE = re.compile(
    r"(?<![A-Za-z0-9_])[\"']?(?P<flag>allow_[A-Za-z0-9_]*fallback)[\"']?\s*(?:=|:)\s*(?:True|true)\b"
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
    ci_tiers_path: Path | None = DEFAULT_CI_TIERS,
    invariant_registry_path: Path | None = DEFAULT_INVARIANT_REGISTRY,
    decision_log_path: Path | None = DEFAULT_DECISION_LOG,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    paths = list(scan_paths) if scan_paths is not None else list(DEFAULT_SCAN_PATHS)
    ci_tiers, ci_tiers_loaded, config_violations = _load_optional_toml(
        repo_root=repo_root,
        path=ci_tiers_path,
        invalid_code="hds_ci_tiers_registry_invalid",
    )
    invariant_registry, invariant_registry_loaded, invariant_registry_violations = (
        _load_optional_toml(
            repo_root=repo_root,
            path=invariant_registry_path,
            invalid_code="hds_invariant_registry_invalid",
        )
    )
    decision_entries, decision_log_loaded, decision_log_violations = _load_decision_log_entries(
        repo_root=repo_root, path=decision_log_path
    )
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
    scanned_test_files: set[str] = set()
    slow_test_files: set[str] = set()
    strict_xfail_hits: list[dict[str, object]] = []
    fallback_hits: list[dict[str, object]] = []

    for raw_path in paths:
        resolved_paths = _expand_scan_path(repo_root, raw_path)
        if not resolved_paths:
            violations.append(
                DriftViolation(
                    code="hds_scan_path_missing",
                    path=raw_path.as_posix(),
                    line=1,
                    message="HDS anti-drift scan path does not exist.",
                )
            )
            continue
        file_paths: list[Path] = []
        for path in resolved_paths:
            if path.is_dir():
                file_paths.extend(sorted(item for item in path.rglob("*") if item.is_file()))
            else:
                file_paths.append(path)

        for file_path in file_paths:
            if file_path.suffix not in {".py", ".md", ".toml"}:
                continue
            text = file_path.read_text(encoding="utf-8")
            file_rel = _rel(file_path, repo_root)
            scanned.append(file_rel)
            if _is_test_file(file_rel):
                scanned_test_files.add(file_rel)
            if file_path.suffix == ".py":
                _audit_python_source(
                    text=text,
                    path=file_rel,
                    counters=counters,
                    violations=violations,
                    strict_xfail_hits=strict_xfail_hits,
                    slow_test_files=slow_test_files,
                )
            if file_rel not in TEXT_MARKER_EXEMPT_PATHS:
                _audit_text_source(
                    text=text,
                    path=file_rel,
                    counters=counters,
                    fallback_hits=fallback_hits,
                    adr_softening_findings=adr_softening_findings,
                    non_goal_violations=non_goal_violations,
                    violations=violations,
                )

    violations.extend(config_violations)
    if ci_tiers_loaded:
        violations.extend(
            _audit_ci_tiers(
                repo_root=repo_root,
                config=ci_tiers,
                scanned_test_files=scanned_test_files,
                slow_test_files=slow_test_files,
            )
        )
        violations.extend(decision_log_violations)
        violations.extend(invariant_registry_violations)
        violations.extend(
            _audit_temporary_exceptions(
                config=ci_tiers,
                strict_xfail_hits=strict_xfail_hits,
                fallback_hits=fallback_hits,
                decision_entries=decision_entries,
                decision_log_loaded=decision_log_loaded,
                invariant_registry=invariant_registry,
                invariant_registry_loaded=invariant_registry_loaded,
            )
        )
    else:
        violations.extend(_fallback_hits_without_registry(fallback_hits))

    ci_tier_codes = {
        "hds_ci_tiers_registry_invalid",
        "hds_ci_tiers_allowed_tiers_invalid",
        "hds_test_tier_missing",
        "hds_slow_test_tier_missing",
        "hds_test_tier_duplicate",
        "hds_test_tier_invalid",
        "hds_test_tier_row_invalid",
        "hds_test_tier_path_missing",
    }
    temporary_exception_codes = {
        "hds_strict_xfail_unregistered",
        "hds_fallback_allowance_without_registry",
        "hds_fallback_allowance_count_exceeds_registered",
        "hds_temporary_exception_row_invalid",
        "hds_temporary_exception_invariant_permission_missing",
        "hds_decision_log_exception_missing",
        "hds_decision_log_exception_incomplete",
        "hds_decision_log_invalid",
        "hds_invariant_registry_invalid",
    }
    ci_tier_violations = [
        violation.as_dict() for violation in violations if violation.code in ci_tier_codes
    ]
    temporary_exception_violations = [
        violation.as_dict()
        for violation in violations
        if violation.code in temporary_exception_codes
    ]
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
        "ci_tier_violations": ci_tier_violations,
        "temporary_exception_violations": temporary_exception_violations,
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
            "adr_softening={adr_count} non_goals={non_goal_count} "
            "ci_tiers={ci_tier_count} temporary_exceptions={exception_count}"
        ).format(
            **payload,
            adr_count=len(payload["adr_softening_findings"]),
            non_goal_count=len(payload["non_goal_violations"]),
            ci_tier_count=len(payload["ci_tier_violations"]),
            exception_count=len(payload["temporary_exception_violations"]),
        ),
    ]
    for violation in payload.get("violations", []):
        if not isinstance(violation, dict):
            continue
        lines.append("[fail] {path}:{line} {code}: {message}".format(**violation))
    return "\n".join(lines) + "\n"


def _audit_python_source(
    *,
    text: str,
    path: str,
    counters: dict[str, int],
    violations: list[DriftViolation],
    strict_xfail_hits: list[dict[str, object]],
    slow_test_files: set[str],
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

    if _is_test_file(path) and "@pytest.mark.slow" in text:
        slow_test_files.add(path)

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if any(
            _pytest_mark_name_from_expr(decorator) == "slow" for decorator in node.decorator_list
        ):
            slow_test_files.add(path)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        mark_name = _pytest_mark_name(node)
        if mark_name == "xfail":
            if _call_has_strict_true(node):
                counters["xfail_strict_count"] += 1
                strict_xfail_hits.append({"path": path, "line": getattr(node, "lineno", 1)})
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
        if mark_name == "slow":
            slow_test_files.add(path)


def _audit_text_source(
    *,
    text: str,
    path: str,
    counters: dict[str, int],
    fallback_hits: list[dict[str, object]],
    adr_softening_findings: list[dict[str, object]],
    non_goal_violations: list[dict[str, object]],
    violations: list[DriftViolation],
) -> None:
    for match in ALLOW_FALLBACK_RE.finditer(text):
        counters["allow_fallback_count"] += 1
        fallback_hits.append(
            {
                "path": path,
                "line": _line_number(text, match.start()),
                "flag": match.group("flag"),
            }
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
    return _pytest_mark_name_from_expr(call.func)


def _pytest_mark_name_from_expr(expr: ast.expr) -> str | None:
    if not isinstance(expr, ast.Attribute):
        return None
    name = expr.attr
    if name not in {"xfail", "skip", "skipif", "slow"}:
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


def _expand_scan_path(repo_root: Path, path: Path) -> list[Path]:
    raw = path.as_posix()
    if any(char in raw for char in "*?[]"):
        return sorted(repo_root.glob(raw))
    resolved = _resolve(repo_root, path)
    return [resolved] if resolved.exists() else []


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _load_optional_toml(
    *,
    repo_root: Path,
    path: Path | None,
    invalid_code: str,
) -> tuple[dict[str, Any], bool, list[DriftViolation]]:
    if path is None:
        return {}, False, []
    resolved = _resolve(repo_root, path)
    if not resolved.exists():
        return {}, False, []
    try:
        with resolved.open("rb") as stream:
            payload = tomllib.load(stream)
    except tomllib.TOMLDecodeError as exc:
        return (
            {},
            False,
            [
                DriftViolation(
                    code=invalid_code,
                    path=_rel(resolved, repo_root),
                    line=exc.lineno or 1,
                    message=f"HDS TOML registry is invalid: {exc}",
                )
            ],
        )
    if not isinstance(payload, dict):
        return (
            {},
            False,
            [
                DriftViolation(
                    code=invalid_code,
                    path=_rel(resolved, repo_root),
                    line=1,
                    message="HDS TOML registry must load as a table.",
                )
            ],
        )
    return payload, True, []


def _load_decision_log_entries(
    *,
    repo_root: Path,
    path: Path | None,
) -> tuple[dict[str, dict[str, str]], bool, list[DriftViolation]]:
    if path is None:
        return {}, False, []
    resolved = _resolve(repo_root, path)
    if not resolved.exists():
        return {}, False, []
    text = resolved.read_text(encoding="utf-8")
    entries: dict[str, dict[str, str]] = {}
    current_id: str | None = None
    current: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("### "):
            if current_id is not None:
                entries[current_id] = current
            current_id = line.removeprefix("### ").split(" - ", 1)[0].strip()
            current = {"decision_id": current_id}
            continue
        if current_id is None or not line.startswith("- **"):
            continue
        label, separator, value = line.removeprefix("- **").partition("**:")
        if separator:
            current[_decision_log_field_key(label)] = value.strip()
    if current_id is not None:
        entries[current_id] = current
    return entries, True, []


def _decision_log_field_key(label: str) -> str:
    return label.strip().casefold().replace(" ", "_").replace("-", "_").replace("/", "_")


def _is_test_file(path: str) -> bool:
    return path.startswith("tests/") and path.endswith(".py")


def _audit_ci_tiers(
    *,
    repo_root: Path,
    config: dict[str, Any],
    scanned_test_files: set[str],
    slow_test_files: set[str],
) -> list[DriftViolation]:
    violations: list[DriftViolation] = []
    allowed = config.get("allowed_tiers")
    if not isinstance(allowed, list) or {str(item) for item in allowed} != ALLOWED_CI_TIERS:
        violations.append(
            DriftViolation(
                code="hds_ci_tiers_allowed_tiers_invalid",
                path=_rel(DEFAULT_CI_TIERS, repo_root),
                line=1,
                message="HDS CI tier registry must declare the allowed tier set.",
            )
        )
    rows = config.get("tests")
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        return [
            DriftViolation(
                code="hds_test_tier_row_invalid",
                path=_rel(DEFAULT_CI_TIERS, repo_root),
                line=1,
                message="HDS CI tier registry tests must be a list.",
            )
        ]

    tier_by_path: dict[str, str] = {}
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            violations.append(
                DriftViolation(
                    code="hds_test_tier_row_invalid",
                    path=_rel(DEFAULT_CI_TIERS, repo_root),
                    line=1,
                    message="Every HDS CI tier test row must be a table.",
                )
            )
            continue
        test_path = str(row.get("path") or "").strip()
        tier = str(row.get("tier") or "").strip()
        if not test_path or tier not in ALLOWED_CI_TIERS:
            violations.append(
                DriftViolation(
                    code="hds_test_tier_invalid",
                    path=test_path or _rel(DEFAULT_CI_TIERS, repo_root),
                    line=1,
                    message="Every HDS test tier row must declare a valid path and tier.",
                )
            )
            continue
        if test_path in seen:
            duplicates.add(test_path)
        seen.add(test_path)
        tier_by_path[test_path] = tier
        if not (repo_root / test_path).exists():
            violations.append(
                DriftViolation(
                    code="hds_test_tier_path_missing",
                    path=test_path,
                    line=1,
                    message="HDS CI tier registry references a missing test path.",
                )
            )
    for test_path in sorted(duplicates):
        violations.append(
            DriftViolation(
                code="hds_test_tier_duplicate",
                path=test_path,
                line=1,
                message="HDS test file is declared in more than one CI tier row.",
            )
        )
    for test_path in sorted(scanned_test_files - set(tier_by_path)):
        violations.append(
            DriftViolation(
                code="hds_test_tier_missing",
                path=test_path,
                line=1,
                message="HDS scanned test file must have a CI tier declaration.",
            )
        )
    for test_path in sorted(slow_test_files):
        if test_path not in tier_by_path:
            violations.append(
                DriftViolation(
                    code="hds_slow_test_tier_missing",
                    path=test_path,
                    line=1,
                    message="HDS slow test must declare an explicit non-fast CI tier.",
                )
            )
    return violations


def _audit_temporary_exceptions(
    *,
    config: dict[str, Any],
    strict_xfail_hits: list[dict[str, object]],
    fallback_hits: list[dict[str, object]],
    decision_entries: dict[str, dict[str, str]],
    decision_log_loaded: bool,
    invariant_registry: dict[str, Any],
    invariant_registry_loaded: bool,
) -> list[DriftViolation]:
    violations: list[DriftViolation] = []
    exceptions = _temporary_exception_rows(config)
    baseline = _anti_drift_baseline(config)
    allowed_xfails = int(baseline.get("xfail_strict_count", 0))
    strict_xfail_exceptions = [
        exception for exception in exceptions if exception.get("kind") == "strict_xfail"
    ]
    for hit in strict_xfail_hits:
        if not any(_exception_matches_hit(exception, hit) for exception in strict_xfail_exceptions):
            violations.append(
                DriftViolation(
                    code="hds_strict_xfail_unregistered",
                    path=str(hit.get("path") or ""),
                    line=int(hit.get("line") or 1),
                    message="Strict HDS xfail is outside registered exception paths.",
                )
            )
    if len(strict_xfail_hits) > allowed_xfails:
        for hit in strict_xfail_hits[allowed_xfails:]:
            violations.append(
                DriftViolation(
                    code="hds_strict_xfail_unregistered",
                    path=str(hit.get("path") or ""),
                    line=int(hit.get("line") or 1),
                    message="Strict HDS xfail exceeds the registered anti-drift baseline.",
                )
            )

    exception_ids_by_invariant = _temporary_exception_ids_by_invariant(
        invariant_registry if invariant_registry_loaded else {}
    )
    for exception in exceptions:
        violations.extend(
            _temporary_exception_metadata_violations(
                exception=exception,
                decision_entries=decision_entries,
                decision_log_loaded=decision_log_loaded,
                exception_ids_by_invariant=exception_ids_by_invariant,
                invariant_registry_loaded=invariant_registry_loaded,
            )
        )

    fallback_exceptions = [
        exception for exception in exceptions if exception.get("kind") == "fallback_allowance"
    ]
    for hit in fallback_hits:
        matches = [
            exception for exception in fallback_exceptions if _exception_matches_hit(exception, hit)
        ]
        if not matches:
            violations.append(
                DriftViolation(
                    code="hds_fallback_allowance_without_registry",
                    path=str(hit.get("path") or ""),
                    line=int(hit.get("line") or 1),
                    message="HDS fallback allowance requires a registered temporary exception.",
                )
            )
            continue
        for exception in matches:
            max_count = int(exception.get("max_count") or 1)
            count = sum(
                1 for candidate in fallback_hits if _exception_matches_hit(exception, candidate)
            )
            if count > max_count:
                violations.append(
                    DriftViolation(
                        code="hds_fallback_allowance_count_exceeds_registered",
                        path=str(hit.get("path") or ""),
                        line=int(hit.get("line") or 1),
                        message="HDS fallback allowance count exceeds registered maximum.",
                    )
                )
    return violations


def _temporary_exception_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
    rows = config.get("temporary_exceptions")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _anti_drift_baseline(config: dict[str, Any]) -> dict[str, Any]:
    baseline = config.get("anti_drift_baseline")
    return dict(baseline) if isinstance(baseline, dict) else {}


def _temporary_exception_metadata_violations(
    *,
    exception: dict[str, Any],
    decision_entries: dict[str, dict[str, str]],
    decision_log_loaded: bool,
    exception_ids_by_invariant: dict[str, set[str]],
    invariant_registry_loaded: bool,
) -> list[DriftViolation]:
    violations: list[DriftViolation] = []
    exception_id = str(exception.get("exception_id") or "").strip()
    invariant_id = str(exception.get("invariant_id") or "").strip()
    decision_id = str(exception.get("decision_id") or "").strip()
    path_globs = exception.get("path_globs")
    if not exception_id or not invariant_id or not decision_id or not isinstance(path_globs, list):
        return [
            DriftViolation(
                code="hds_temporary_exception_row_invalid",
                path=exception_id or "temporary_exceptions",
                line=1,
                message="Temporary exception rows require id, invariant, decision, and path globs.",
            )
        ]

    if not invariant_registry_loaded or exception_id not in exception_ids_by_invariant.get(
        invariant_id, set()
    ):
        violations.append(
            DriftViolation(
                code="hds_temporary_exception_invariant_permission_missing",
                path=invariant_id,
                line=1,
                message="Temporary exception is not permitted by the invariant registry.",
            )
        )
    if not decision_log_loaded or decision_id not in decision_entries:
        violations.append(
            DriftViolation(
                code="hds_decision_log_exception_missing",
                path=decision_id,
                line=1,
                message="Temporary exception must have a decision-log entry.",
            )
        )
        return violations
    entry = decision_entries[decision_id]
    required = {
        "owner": entry.get("owner", ""),
        "affected_invariant_id_or_phase_id": entry.get("affected_invariant_id_or_phase_id", ""),
        "revisit_wave": entry.get("revisit_wave", ""),
    }
    if (
        any(not value.strip() for value in required.values())
        or invariant_id not in required["affected_invariant_id_or_phase_id"]
    ):
        violations.append(
            DriftViolation(
                code="hds_decision_log_exception_incomplete",
                path=decision_id,
                line=1,
                message="Decision-log temporary exception entry is incomplete.",
            )
        )
    return violations


def _temporary_exception_ids_by_invariant(
    invariant_registry: dict[str, Any],
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    rows = invariant_registry.get("invariants")
    if not isinstance(rows, list):
        return result
    for row in rows:
        if not isinstance(row, dict):
            continue
        invariant_id = str(row.get("invariant_id") or "").strip()
        ids = row.get("temporary_exception_ids")
        if not invariant_id or not isinstance(ids, list):
            continue
        result[invariant_id] = {str(item).strip() for item in ids if str(item).strip()}
    return result


def _exception_matches_hit(exception: dict[str, Any], hit: dict[str, object]) -> bool:
    path = str(hit.get("path") or "")
    flag = str(hit.get("flag") or "")
    path_globs = exception.get("path_globs")
    flags = exception.get("fallback_flags")
    if isinstance(flags, list) and flags and flag not in {str(item) for item in flags}:
        return False
    if not isinstance(path_globs, list):
        return False
    return any(fnmatch.fnmatch(path, str(pattern)) for pattern in path_globs)


def _fallback_hits_without_registry(
    fallback_hits: list[dict[str, object]],
) -> list[DriftViolation]:
    return [
        DriftViolation(
            code="hds_fallback_allowance_without_registry",
            path=str(hit.get("path") or ""),
            line=int(hit.get("line") or 1),
            message="HDS fallback allowance requires registry and decision-log permission.",
        )
        for hit in fallback_hits
    ]


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--ci-tiers", type=Path, default=DEFAULT_CI_TIERS)
    parser.add_argument("--invariant-registry", type=Path, default=DEFAULT_INVARIANT_REGISTRY)
    parser.add_argument("--decision-log", type=Path, default=DEFAULT_DECISION_LOG)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    parser.add_argument("--require-passing", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    payload = build_substrate_drift_payload(
        repo_root=repo_root,
        ci_tiers_path=args.ci_tiers,
        invariant_registry_path=args.invariant_registry,
        decision_log_path=args.decision_log,
    )
    rendered = dump_json(payload) if args.output_format == "json" else render_text(payload)
    if args.json_output is not None:
        atomic_write_text(_resolve(repo_root, args.json_output), dump_json(payload))
    else:
        sys.stdout.write(rendered)
    if payload["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
