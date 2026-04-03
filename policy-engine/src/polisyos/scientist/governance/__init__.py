"""Stable governance facade for runtime validation, calibration review, and replay reports.

This package exposes the orchestration-level contracts consumed by Scientist
nodes and calibration jobs: pre/postflight helpers, validation profiles,
backtest/stress runners, leaderboard rollups, and persisted governance reports.
Concrete validator passes live under `polisyos.scientist.governance.passes` and
are usually loaded through `pass_registry`.
"""

from polisyos.core.governance.profiles import ValidationProfile  # noqa: F401

from .backtest_matrix import (  # noqa: F401
    BacktestKind,
    BacktestKindResult,
    BacktestMatrixResult,
    BacktestMatrixRunner,
)
from .calibration import (  # noqa: F401
    CalibrationAdversarialResult,
    CalibrationAdversarialSuiteRegistry,
    CalibrationGovernanceInput,
    CalibrationGovernanceReport,
    CalibrationGovernanceRunner,
)
from .calibration_leaderboard import (  # noqa: F401
    CalibrationLeaderboard,
    CalibrationLeaderboardEntry,
    CalibrationLeaderboardMetrics,
)
from .calibration_validation import (  # noqa: F401
    CalibrationValidationBundle,
    CalibrationValidationRunner,
    CalibrationValidationRunnerInput,
    CalibrationValidationRunnerResult,
    load_calibration_validation_bundle,
    persist_calibration_validation_bundle,
)
from .postflight import postflight_checks  # noqa: F401
from .preflight import preflight_checks  # noqa: F401
from .report import GovernanceReport, GovernanceReportLinks  # noqa: F401
from .stress_scenarios import (  # noqa: F401
    StressScenarioComparison,
    StressScenarioKind,
    StressScenarioResult,
    StressScenarioRunner,
)

__all__ = [
    "preflight_checks",
    "postflight_checks",
    "ValidationProfile",
    "BacktestKind",
    "BacktestKindResult",
    "BacktestMatrixResult",
    "BacktestMatrixRunner",
    "CalibrationAdversarialResult",
    "CalibrationAdversarialSuiteRegistry",
    "CalibrationGovernanceInput",
    "CalibrationGovernanceReport",
    "CalibrationGovernanceRunner",
    "StressScenarioComparison",
    "StressScenarioKind",
    "StressScenarioResult",
    "StressScenarioRunner",
    "CalibrationLeaderboard",
    "CalibrationLeaderboardEntry",
    "CalibrationLeaderboardMetrics",
    "CalibrationValidationBundle",
    "CalibrationValidationRunner",
    "CalibrationValidationRunnerInput",
    "CalibrationValidationRunnerResult",
    "persist_calibration_validation_bundle",
    "load_calibration_validation_bundle",
    "GovernanceReport",
    "GovernanceReportLinks",
]
