"""Focused architecture report validator owner."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.quality.validation.architecture_package_contracts import (
        ArchitectureReportServices,
        FindingLike,
    )

import fnmatch
from pathlib import Path
from typing import Any

from tools.quality.validation.package_import_size_ratchet import count_lines


def _validate_module_size_budget(
    repo_root: Path, *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    findings: list[FindingLike] = []
    data = _services.read_toml(repo_root / "architecture" / "module_size_budget.toml")
    header = data.get("module_size_budget", {})
    validation_header = data.get("validation_tooling_size_budget", {})
    if int(header.get("default_warning_lines", 0)) != 1000:
        findings.append(
            _services.finding(
                "module-size",
                "error",
                "architecture/module_size_budget.toml",
                "default warning line budget is not 1000",
                str(header.get("default_warning_lines")),
            )
        )
    if int(header.get("default_fail_closed_target_lines", 0)) != 2500:
        findings.append(
            _services.finding(
                "module-size",
                "report_only",
                "architecture/module_size_budget.toml",
                "default fail-closed target is not 2500",
                str(header.get("default_fail_closed_target_lines")),
            )
        )
    if not validation_header:
        findings.append(
            _services.finding(
                "module-size",
                "error",
                "architecture/module_size_budget.toml",
                "validation tooling size budget is missing",
            )
        )
    else:
        findings.extend(
            _services.dispatch("_validate_validation_tooling_defaults", validation_header)
        )

    budgets = data.get("budget", [])
    validation_scope = [
        str(item) for item in validation_header.get("scope", []) if str(item).strip()
    ]
    budget_by_path = {
        str(budget.get("path", "")): budget
        for budget in budgets
        if str(budget.get("path", "")).strip()
    }
    if validation_header:
        findings.extend(
            _services.dispatch(
                "_validate_validation_tooling_budget_coverage",
                repo_root,
                budget_by_path=budget_by_path,
                validation_header=validation_header,
                validation_scope=validation_scope,
            )
        )

    for budget in budgets:
        relative = str(budget.get("path", ""))
        if _services.dispatch("_matches_any_validation_scope", relative, validation_scope):
            findings.extend(
                _services.dispatch(
                    "_validate_validation_tooling_budget_entry",
                    repo_root,
                    budget,
                    validation_header=validation_header,
                    validation_scope=validation_scope,
                )
            )
            continue
        path = repo_root / relative
        subject = relative or "architecture/module_size_budget.toml"
        for field in (
            "owner",
            "current_lines",
            "target_lines",
            "shrink_plan",
            "extraction_sequence",
            "risk_notes",
        ):
            if field not in budget or budget[field] in ("", [], None):
                findings.append(
                    _services.finding(
                        "module-size",
                        "report_only",
                        subject,
                        "budget is missing Phase 4.3 shrink metadata",
                        field,
                    )
                )
        extraction_sequence = budget.get("extraction_sequence", [])
        if extraction_sequence and (
            not isinstance(extraction_sequence, list)
            or any(not str(item).strip() for item in extraction_sequence)
        ):
            findings.append(
                _services.finding(
                    "module-size",
                    "report_only",
                    subject,
                    "extraction sequence must be a non-empty list of responsibility names",
                )
            )
        if not path.exists():
            findings.append(
                _services.finding(
                    "module-size", "report_only", relative, "budgeted module is missing"
                )
            )
            continue
        current_lines = count_lines(path)
        current_budget = int(budget.get("current_lines", 0))
        limit = int(budget.get("report_only_limit_lines", 0))
        target = int(budget.get("target_lines", 0))
        baseline = int(budget.get("baseline_lines", 0))
        if current_budget and current_lines > current_budget:
            findings.append(
                _services.finding(
                    "module-size",
                    "report_only",
                    relative,
                    "module grew above Phase 4.3 current-line budget",
                    f"current={current_lines} current_budget={current_budget}",
                )
            )
        if current_lines > limit:
            findings.append(
                _services.finding(
                    "module-size",
                    "report_only",
                    relative,
                    "module exceeds report-only limit",
                    f"current={current_lines} limit={limit}",
                )
            )
        if target > int(header.get("default_fail_closed_target_lines", 2500)):
            findings.append(
                _services.finding(
                    "module-size",
                    "report_only",
                    relative,
                    "target is above default fail-closed target",
                    str(target),
                )
            )
        if baseline < target:
            findings.append(
                _services.finding(
                    "module-size",
                    "report_only",
                    relative,
                    "baseline is already below target; budget should be removed or tightened",
                    f"baseline={baseline} target={target}",
                )
            )
    return findings


def _validate_validation_tooling_defaults(
    header: dict[str, Any], *, _services: ArchitectureReportServices
) -> list[FindingLike]:
    findings: list[FindingLike] = []
    subject = "architecture/module_size_budget.toml"
    scope = header.get("scope", [])
    if scope != ["tools/quality/validation/**/*.py"]:
        findings.append(
            _services.finding(
                "module-size",
                "error",
                subject,
                "validation tooling size budget must cover tools/quality/validation/**/*.py",
                str(scope),
            )
        )
    if int(header.get("warning_lines", 0)) != 1000:
        findings.append(
            _services.finding(
                "module-size",
                "error",
                subject,
                "validation tooling warning line budget is not 1000",
                str(header.get("warning_lines")),
            )
        )
    if int(header.get("fail_closed_lines", 0)) != 2000:
        findings.append(
            _services.finding(
                "module-size",
                "error",
                subject,
                "validation tooling fail-closed line budget is not 2000",
                str(header.get("fail_closed_lines")),
            )
        )
    return findings


def _validate_validation_tooling_budget_coverage(
    repo_root: Path,
    *,
    budget_by_path: dict[str, dict[str, Any]],
    validation_header: dict[str, Any],
    validation_scope: list[str],
    _services: ArchitectureReportServices,
) -> list[FindingLike]:
    findings: list[FindingLike] = []
    warning = int(validation_header.get("require_budget_above_lines", 0)) or int(
        validation_header.get("warning_lines", 1000)
    )
    for path in _services.dispatch("_validation_tooling_paths", repo_root, validation_scope):
        relative = _services.dispatch("_relative", path, repo_root)
        logical_lines = count_lines(path)
        if logical_lines <= warning or relative in budget_by_path:
            continue
        findings.append(
            _services.finding(
                "module-size",
                "error",
                relative,
                "validation tooling above warning threshold lacks a module-size budget",
                f"logical_lines={logical_lines} warning={warning}",
            )
        )
    return findings


def _validate_validation_tooling_budget_entry(
    repo_root: Path,
    budget: dict[str, Any],
    *,
    validation_header: dict[str, Any],
    validation_scope: list[str],
    _services: ArchitectureReportServices,
) -> list[FindingLike]:
    findings: list[FindingLike] = []
    relative = str(budget.get("path", ""))
    path = repo_root / relative
    subject = relative or "architecture/module_size_budget.toml"
    if not _services.dispatch("_matches_any_validation_scope", relative, validation_scope):
        return findings
    warning = int(validation_header.get("warning_lines", 1000))
    fail_closed = int(validation_header.get("fail_closed_lines", 2000))
    if int(budget.get("warning_lines", 0)) != warning:
        findings.append(
            _services.finding(
                "module-size",
                "error",
                subject,
                "validation tooling budget warning_lines must match validation default",
                str(budget.get("warning_lines")),
            )
        )
    if int(budget.get("fail_closed_lines", 0)) != fail_closed:
        findings.append(
            _services.finding(
                "module-size",
                "error",
                subject,
                "validation tooling budget fail_closed_lines must match validation default",
                str(budget.get("fail_closed_lines")),
            )
        )
    if not path.exists():
        findings.append(
            _services.finding("module-size", "error", subject, "budgeted module is missing")
        )
        return findings

    current_lines = count_lines(path)
    current_budget = int(budget.get("current_lines", 0))
    baseline = int(budget.get("baseline_lines", 0))
    limit = int(budget.get("report_only_limit_lines", 0))
    if current_budget and current_lines > current_budget:
        findings.append(
            _services.finding(
                "module-size",
                "error",
                subject,
                "validation tooling grew above its ratcheted current_lines budget",
                f"current={current_lines} budget={current_budget}",
            )
        )
    if limit and current_lines > limit:
        findings.append(
            _services.finding(
                "module-size",
                "error",
                subject,
                "validation tooling grew above its report_only_limit_lines ratchet",
                f"current={current_lines} limit={limit}",
            )
        )
    if current_lines <= warning:
        return findings

    if not str(budget.get("owner", "")).startswith("team-"):
        findings.append(
            _services.finding(
                "module-size",
                "error",
                subject,
                "validation tooling above warning threshold must declare a team owner",
                str(budget.get("owner", "")),
            )
        )
    if not baseline:
        findings.append(
            _services.finding(
                "module-size",
                "error",
                subject,
                "validation tooling above warning threshold must pin baseline_lines",
            )
        )
    elif current_lines > baseline:
        findings.append(
            _services.finding(
                "module-size",
                "error",
                subject,
                "validation tooling grew above its pinned baseline",
                f"current={current_lines} baseline={baseline}",
            )
        )
    if limit != baseline:
        findings.append(
            _services.finding(
                "module-size",
                "error",
                subject,
                "validation tooling above warning threshold must use a no-growth ratchet",
                f"baseline={baseline} report_only_limit_lines={limit}",
            )
        )
    extraction_sequence = budget.get("extraction_sequence", [])
    if (
        not isinstance(extraction_sequence, list)
        or not extraction_sequence
        or any(not str(item).strip() for item in extraction_sequence)
    ):
        findings.append(
            _services.finding(
                "module-size",
                "error",
                subject,
                "validation tooling above warning threshold must declare extraction sequence",
            )
        )
    target_date = str(budget.get("target_date", ""))
    if not target_date:
        findings.append(
            _services.finding(
                "module-size",
                "error",
                subject,
                "validation tooling above warning threshold must declare extraction target date",
            )
        )
    elif not _services.dispatch("_valid_future_or_today", target_date):
        findings.append(
            _services.finding(
                "module-size",
                "error",
                subject,
                "validation tooling extraction target date must be today or future",
                target_date,
            )
        )
    target = int(budget.get("target_lines", 0))
    if target and target > warning:
        findings.append(
            _services.finding(
                "module-size",
                "error",
                subject,
                "validation tooling extraction target must be at or below warning threshold",
                str(target),
            )
        )
    return findings


def _validation_tooling_paths(
    repo_root: Path, validation_scope: list[str], *, _services: ArchitectureReportServices
) -> list[Path]:
    paths: set[Path] = set()
    for pattern in validation_scope:
        paths.update(path for path in repo_root.glob(pattern) if path.is_file())
    return sorted(paths)


def _matches_any_validation_scope(
    relative: str, validation_scope: list[str], *, _services: ArchitectureReportServices
) -> bool:
    return any(
        _services.dispatch("_matches_validation_scope", relative, pattern)
        for pattern in validation_scope
    )


def _matches_validation_scope(
    relative: str, pattern: str, *, _services: ArchitectureReportServices
) -> bool:
    if fnmatch.fnmatch(relative, pattern):
        return True
    if pattern == "tools/quality/validation/**/*.py":
        return relative.startswith("tools/quality/validation/") and relative.endswith(".py")
    return False
