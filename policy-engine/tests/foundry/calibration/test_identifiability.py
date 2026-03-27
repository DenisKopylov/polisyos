from __future__ import annotations

import numpy as np

from polisyos.foundry.calibration.hessian import HessianResult
from polisyos.foundry.calibration.identifiability import (
    IdentifiabilityStatus,
    diagnose_identifiability,
)


def _make_hessian_result(
    diag: list[float],
    param_names: list[str] | None = None,
) -> HessianResult:
    """Helper: build a HessianResult from diagonal Hessian values."""
    n = len(diag)
    H = np.diag(diag)
    cov = np.diag([1.0 / d for d in diag])
    std = np.array([1.0 / d**0.5 for d in diag])
    eigvals = np.array(sorted(diag))
    if param_names is None:
        param_names = [f"p{i}" for i in range(n)]
    cond = max(diag) / min(diag) if min(diag) > 0 else float("inf")
    return HessianResult(
        hessian=H,
        covariance=cov,
        std=std,
        eigenvalues=eigvals,
        condition_number=cond,
        n_repaired=0,
        param_names=param_names,
        strategy="exact",
    )


def test_identified_parameter() -> None:
    """Parameters with large Hessian diagonal should be IDENTIFIED."""
    hr = _make_hessian_result([1.0, 5.0], ["alpha", "beta"])
    report = diagnose_identifiability(hr)

    assert report.n_identified == 2
    assert report.n_sloppy == 0
    assert report.n_non_identified == 0
    for p in report.params:
        assert p.status == IdentifiabilityStatus.IDENTIFIED


def test_sloppy_parameter_flagged() -> None:
    """A parameter with eigenvalue in (1e-8, 1e-3) should be SLOPPY."""
    hr = _make_hessian_result([1.0, 1e-5], ["good", "sloppy"])
    report = diagnose_identifiability(hr)

    assert report.n_identified == 1
    assert report.n_sloppy == 1
    statuses = {p.name: p.status for p in report.params}
    assert statuses["good"] == IdentifiabilityStatus.IDENTIFIED
    assert statuses["sloppy"] == IdentifiabilityStatus.SLOPPY


def test_non_identified_parameter_flagged() -> None:
    """A parameter with eigenvalue <= 1e-8 should be NON_IDENTIFIED."""
    hr = _make_hessian_result([2.0, 1e-10], ["strong", "flat"])
    report = diagnose_identifiability(hr)

    assert report.n_identified == 1
    assert report.n_non_identified == 1
    statuses = {p.name: p.status for p in report.params}
    assert statuses["strong"] == IdentifiabilityStatus.IDENTIFIED
    assert statuses["flat"] == IdentifiabilityStatus.NON_IDENTIFIED
    assert report.effective_dimension == 1
