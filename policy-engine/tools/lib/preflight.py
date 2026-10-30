"""Preflight checks shared by repository tools."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .runner import ToolSpec, ToolStatus


class PreflightStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"
    QUARANTINED = "quarantined"


@dataclass(frozen=True)
class PreflightIssue:
    status: PreflightStatus
    message: str


@dataclass(frozen=True)
class PreflightResult:
    status: PreflightStatus
    issues: tuple[PreflightIssue, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status == PreflightStatus.OK


def run_preflight(spec: ToolSpec) -> PreflightResult:
    """Validate optional imports, external executables, and lifecycle gates."""

    repo_root = Path(__file__).resolve().parents[2]
    src_root = repo_root / "src"
    for import_root in (repo_root, src_root):
        rendered_root = str(import_root)
        if import_root.exists() and rendered_root not in sys.path:
            sys.path.insert(0, rendered_root)

    issues: list[PreflightIssue] = []
    if spec.status == ToolStatus.QUARANTINED:
        reason = spec.reason or "tool is quarantined until its compatibility contract is repaired"
        issues.append(PreflightIssue(PreflightStatus.QUARANTINED, reason))
    elif spec.status == ToolStatus.DEPRECATED:
        reason = spec.reason or "tool is deprecated"
        replacement = f"; use {spec.replacement}" if spec.replacement else ""
        issues.append(PreflightIssue(PreflightStatus.DEGRADED, f"{reason}{replacement}"))

    for module_name in spec.required_imports:
        try:
            spec_found = importlib.util.find_spec(module_name)
        except ModuleNotFoundError:
            spec_found = None
        if spec_found is None:
            issues.append(
                PreflightIssue(
                    PreflightStatus.FAILED,
                    f"missing Python dependency import: {module_name}",
                )
            )

    for executable in spec.external_dependencies:
        if shutil.which(executable) is None:
            issues.append(
                PreflightIssue(
                    PreflightStatus.FAILED,
                    f"missing external executable: {executable}",
                )
            )

    if any(issue.status == PreflightStatus.QUARANTINED for issue in issues):
        return PreflightResult(PreflightStatus.QUARANTINED, tuple(issues))
    if any(issue.status == PreflightStatus.FAILED for issue in issues):
        return PreflightResult(PreflightStatus.FAILED, tuple(issues))
    if issues:
        return PreflightResult(PreflightStatus.DEGRADED, tuple(issues))
    return PreflightResult(PreflightStatus.OK)
