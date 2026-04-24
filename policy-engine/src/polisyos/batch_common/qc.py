"""Common QC model and fail-fast evaluator."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class QCCheck:
    """Capture one quality-gate result and its threshold/message metadata."""

    name: str
    passed: bool
    group: str = ""
    severity: str = "critical"  # critical | warning
    value: float | int | str | None = None
    threshold: float | int | str | None = None
    message: str = ""
    status: str = ""  # passed | failed | unstable | skipped


@dataclass
class QCReport:
    """Aggregate quality-gate checks and auxiliary metrics for one pipeline scope."""

    scope: str
    checks: list[QCCheck] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Return `True` when all critical checks passed."""
        return all(c.passed or c.severity != "critical" for c in self.checks)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report into a JSON-compatible payload."""
        return {
            "scope": self.scope,
            "passed": self.passed,
            "metrics": self.metrics,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "group": c.group,
                    "severity": c.severity,
                    "value": c.value,
                    "threshold": c.threshold,
                    "message": c.message,
                    "status": c.status or ("passed" if c.passed else "failed"),
                }
                for c in self.checks
            ],
        }


def write_qc_report(path: Path, report: QCReport) -> Path:
    """Serialize a `QCReport` to JSON and return the written path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report.to_dict(), fh, ensure_ascii=False, indent=2)
    return path


def evaluate_fail_fast(report: QCReport, *, fail_fast: bool) -> None:
    """Raise if critical checks failed and fail_fast is enabled."""
    if not fail_fast:
        return
    failed = [c.name for c in report.checks if (not c.passed and c.severity == "critical")]
    if failed:
        raise RuntimeError(f"QC failed: {', '.join(failed)}")
