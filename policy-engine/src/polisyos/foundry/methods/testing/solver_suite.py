from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SolverSuiteResult:
    passed: bool
    message: str = ""


class SolverMethodTestSuite:
    """Basic checks for solver backend conventions."""

    def validate_raw_result(self, value: Any) -> SolverSuiteResult:
        if isinstance(value, tuple):
            if len(value) != 2:
                return SolverSuiteResult(False, "solver method tuple must be (output, solver_info)")
            if not isinstance(value[1], dict):
                return SolverSuiteResult(False, "solver_info must be a dictionary")
        return SolverSuiteResult(True)

