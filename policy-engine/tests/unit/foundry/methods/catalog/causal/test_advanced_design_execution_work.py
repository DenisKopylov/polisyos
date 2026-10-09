from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal import advanced_designs
from polisyos.foundry.methods.catalog.causal.nuisance_layer import TauFitResult


@pytest.mark.parametrize(
    ("estimator", "fit_name"),
    [
        (advanced_designs.DRLearnerEstimator, "fit_dr_tau_model"),
        (advanced_designs.RLearnerEstimator, "fit_r_tau_model"),
    ],
)
def test_estimators_expose_opt_in_actual_bootstrap_counts_without_changing_results(
    monkeypatch: pytest.MonkeyPatch,
    estimator: Any,
    fit_name: str,
) -> None:
    n = 24
    x = np.linspace(-1.0, 1.0, n).reshape(-1, 1)
    treatment = np.asarray([0, 1] * (n // 2), dtype=float)
    outcome = 1.0 + x[:, 0] + 0.4 * treatment
    nuisance = SimpleNamespace(
        propensity=np.full(n, 0.5),
        mu1=outcome + 0.2,
        mu0=outcome - 0.2,
        trim_mask=np.ones(n, dtype=bool),
        diagnostics=lambda: {"fixture": "controlled-nuisance-only"},
        aipw_scores=lambda y, t: np.asarray(y) + np.asarray(t) + 0.1,
    )
    monkeypatch.setattr(advanced_designs, "_resolve_nuisance_outputs", lambda *a, **k: nuisance)
    monkeypatch.setattr(
        advanced_designs,
        fit_name,
        lambda *args, **kwargs: TauFitResult(
            cate_predictions=np.linspace(0.5, 1.5, n),
            feature_importances=np.asarray([1.0]),
        ),
    )
    state = {"X": x, "treatment": treatment, "outcome": outcome}
    # NuisanceConfig enforces the estimator's existing 40-draw minimum.
    params = {"bootstrap_draws": 40, "random_seed": 13}

    baseline = estimator.pure_step(state, params)["result"]
    measured = estimator.pure_step(state, {**params, "capture_execution_work": True})["result"]

    assert "bootstrap_execution" not in baseline
    assert measured["bootstrap_execution"] == {
        "schema_version": "1.0",
        "work_unit": "bootstrap_replicate",
        "requested_draw_count": 40,
        "attempted_draw_count": 40,
        "completed_draw_count": 40,
        "failed_draw_count": 0,
        "unattempted_draw_count": 0,
        "draw_execution_status": "complete",
    }
    assert measured["ci_lower"] == baseline["ci_lower"]
    assert measured["ci_upper"] == baseline["ci_upper"]
    assert measured["ate"] == baseline["ate"]
