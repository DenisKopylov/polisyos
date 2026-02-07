from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal import (
    PanelObservationalData,
    ensure_causal_methods_registered,
)
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.causal import EstimationStatus


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def test_scm_perfect_donor_match_att_estimate():
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("causal.inference.synthetic_control@1.0.0")

    t0 = 6
    true_att = 5.0
    donor_1 = np.array([10, 11, 12, 13, 14, 15, 16, 17, 18, 19], dtype=float)
    donor_2 = np.array([5, 5, 5, 5, 5, 5, 5, 5, 5, 5], dtype=float)
    treated = donor_1.copy()
    treated[t0:] += true_att

    data = PanelObservationalData(
        outcome=np.vstack([treated, donor_1, donor_2]),
        treatment=np.array([1, 0, 0]),
        time_treatment=t0,
    )

    dispatcher = MethodDispatcher.get_instance()
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params={"n_placebo_runs": "all"},
        seed=42,
    )

    report = result.output["report"]
    weights = np.asarray(result.output["weights"])
    assert report.status == EstimationStatus.SUCCESS
    assert abs(report.point_estimate - true_att) < 1.0
    assert abs(weights[0] - 1.0) < 1e-2
    assert result.reproducibility.determinism_tier == DeterminismTier.STATISTICAL


def test_scm_fails_with_multiple_treated_units():
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("causal.inference.synthetic_control@1.0.0")
    data = PanelObservationalData(
        outcome=np.arange(20, dtype=float).reshape(4, 5),
        treatment=np.array([1, 1, 0, 0]),
        time_treatment=2,
    )
    dispatcher = MethodDispatcher.get_instance()
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params={},
        seed=0,
    )
    report = result.output["report"]
    assert report.status == EstimationStatus.INPUT_INVALID
    envelope = result.output["envelope"]
    assert envelope is not None
    assert envelope.gate_eligible is False
