from __future__ import annotations

import numpy as np
from polisyos.foundry.calibration.hessian import HessianResult
from polisyos.foundry.calibration.identifiability import (
    IdentifiabilityReport,
    IdentifiabilityStatus,
    ParamIdentifiability,
)
from polisyos.foundry.calibration.multi_start import (
    SingleRunResult,
    select_best,
)
from polisyos.ir.analytics.calibration import MultiStartConfig


def _hr(condition: float) -> HessianResult:
    """Build a minimal HessianResult with a given condition number."""
    return HessianResult(
        hessian=np.eye(1),
        covariance=np.eye(1),
        std=np.ones(1),
        eigenvalues=np.array([1.0]),
        condition_number=condition,
        n_repaired=0,
        param_names=["p0"],
        strategy="exact",
    )


def _id_report(n_identified: int) -> IdentifiabilityReport:
    params = [
        ParamIdentifiability(
            name=f"p{i}",
            status=IdentifiabilityStatus.IDENTIFIED,
            eigenvalue=1.0,
            std=0.1,
        )
        for i in range(n_identified)
    ]
    return IdentifiabilityReport(
        params=params,
        n_identified=n_identified,
        n_sloppy=0,
        n_non_identified=0,
        effective_dimension=n_identified,
    )


def test_multi_start_finds_global_minimum() -> None:
    """best_loss selection should pick the run with lowest loss among acceptable condition."""
    runs = [
        SingleRunResult(loss=0.5, params=[], hessian_result=_hr(10.0)),
        SingleRunResult(loss=0.1, params=[], hessian_result=_hr(100.0)),
        SingleRunResult(loss=0.3, params=[], hessian_result=_hr(50.0)),
    ]
    cfg = MultiStartConfig(n_starts=3, selection="best_loss", condition_threshold=1e8)
    idx, reason = select_best(runs, cfg)
    assert idx == 1  # lowest loss
    assert "0.1" in reason


def test_multi_start_identifiability_selection() -> None:
    """best_identifiability should pick the run with most identified params."""
    runs = [
        SingleRunResult(loss=0.1, params=[], identifiability=_id_report(1)),
        SingleRunResult(loss=0.5, params=[], identifiability=_id_report(3)),
        SingleRunResult(loss=0.3, params=[], identifiability=_id_report(2)),
    ]
    cfg = MultiStartConfig(n_starts=3, selection="best_identifiability")
    idx, reason = select_best(runs, cfg)
    assert idx == 1  # most identified params
    assert "3 identified" in reason


def test_multi_start_identifiability_tiebreaks_on_condition_then_loss() -> None:
    runs = [
        SingleRunResult(
            loss=0.05, params=[], identifiability=_id_report(2), hessian_result=_hr(100.0)
        ),
        SingleRunResult(
            loss=0.10, params=[], identifiability=_id_report(2), hessian_result=_hr(10.0)
        ),
    ]
    cfg = MultiStartConfig(n_starts=2, selection="best_identifiability")
    idx, reason = select_best(runs, cfg)
    assert idx == 1
    assert "condition=10" in reason


def test_condition_threshold_filtering() -> None:
    """Runs with bad condition numbers should be deprioritized in best_loss."""
    runs = [
        SingleRunResult(loss=0.1, params=[], hessian_result=_hr(1e12)),  # bad condition
        SingleRunResult(loss=0.5, params=[], hessian_result=_hr(10.0)),  # good condition
    ]
    cfg = MultiStartConfig(n_starts=2, selection="best_loss", condition_threshold=1e8)
    idx, reason = select_best(runs, cfg)
    assert idx == 1  # good condition, even though higher loss


def test_single_run_returns_zero() -> None:
    """A single run should return index 0."""
    runs = [SingleRunResult(loss=0.5, params=[])]
    cfg = MultiStartConfig(n_starts=1)
    idx, reason = select_best(runs, cfg)
    assert idx == 0
    assert reason == "single_run"
