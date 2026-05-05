"""Shared QC report contracts for Data Forge shadow kernel."""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class QCCheck:
    """Capture one quality-gate result and its threshold/message metadata."""

    name: str
    passed: bool
    group: str = ""
    severity: str = "critical"
    value: float | int | str | None = None
    threshold: float | int | str | None = None
    message: str = ""
    status: str = ""


@dataclass
class QCReport:
    """Aggregate quality-gate checks and auxiliary metrics for one pipeline scope."""

    scope: str
    checks: list[QCCheck] | tuple[QCCheck, ...] = field(default_factory=list)
    metrics: dict[str, object] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Return True when all critical checks passed."""
        return all(check.passed or check.severity != "critical" for check in self.checks)

    def to_dict(self) -> dict[str, object]:
        """Serialize the report into the legacy-compatible JSON shape."""
        return {
            "scope": self.scope,
            "passed": self.passed,
            "metrics": self.metrics,
            "checks": [
                {
                    "name": check.name,
                    "passed": check.passed,
                    "group": check.group,
                    "severity": check.severity,
                    "value": check.value,
                    "threshold": check.threshold,
                    "message": check.message,
                    "status": check.status or ("passed" if check.passed else "failed"),
                }
                for check in self.checks
            ],
        }


def write_qc_report(path: str | pathlib.Path, report: QCReport) -> pathlib.Path:
    """Serialize a QC report to JSON and return the written path."""
    out_path = pathlib.Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def evaluate_fail_fast(report: QCReport, *, fail_fast: bool) -> None:
    """Raise if critical checks failed and fail_fast is enabled."""
    if not fail_fast:
        return
    failed = [
        check.name for check in report.checks if not check.passed and check.severity == "critical"
    ]
    if failed:
        raise RuntimeError(f"QC failed: {', '.join(failed)}")


__all__ = ["QCCheck", "QCReport", "evaluate_fail_fast", "write_qc_report"]
