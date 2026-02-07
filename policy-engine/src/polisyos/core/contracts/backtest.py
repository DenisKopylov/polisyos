from __future__ import annotations

from typing import Literal

from ..artifacts.manifest import ArtifactRef


class BacktestReportRef(ArtifactRef):
    kind: Literal["ir.backtest_report"] = "ir.backtest_report"
    media_type: Literal["application/json"] = "application/json"


__all__ = ["BacktestReportRef"]
