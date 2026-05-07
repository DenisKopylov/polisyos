"""Contracts for the causal engine orchestrator."""

from __future__ import annotations

from polisyos.ir.analytics.causal import DataReadinessReport


class DataReadinessBlockedError(RuntimeError):
    """Typed pre-execution failure raised when an estimation path is not ready."""

    def __init__(self, report: DataReadinessReport, *, reason: str) -> None:
        self.report = report
        self.reason = reason
        super().__init__(reason)


__all__ = ["DataReadinessBlockedError"]
