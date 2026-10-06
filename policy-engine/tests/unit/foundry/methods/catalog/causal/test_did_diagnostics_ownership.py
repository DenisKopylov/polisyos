"""Real diagnostic, registry/dispatcher, and fresh CAS consumer witnesses."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from statsmodels.api import OLS
from statsmodels.stats.sandwich_covariance import cov_cluster

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal.did import (
    DifferenceInDifferences,
    StandardDifferenceInDifferences,
)
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.foundry.methods.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.exceptions import MethodNotFoundError
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import load_causal_effect_report, persist_causal_effect_report


@pytest.fixture(autouse=True)
def _registry_isolation():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _standard(pre=3):
    outcome = np.tile(np.arange(pre + 2, dtype=float), (8, 1))
    outcome[:3, pre:] += 3.0
    return PanelObservationalData(
        outcome=outcome,
        treatment=np.array([1, 1, 1, 0, 0, 0, 0, 0]),
        time_treatment=pre,
        unit_ids=np.arange(8),
    )


@pytest.mark.parametrize("pre", [1, 2])
def test_insufficient_pretrend_is_not_testable_never_passed(pre):
    report = StandardDifferenceInDifferences.pure_step(_standard(pre), {})["report"]
    diagnostic = report.diagnostics[0]
    assert diagnostic.passed is False
    assert diagnostic.statistic is None and diagnostic.p_value is None
    assert diagnostic.details["status"] == "not_testable"
    assert diagnostic.details["identification_authority"] is False


def test_zero_pretrend_nonrejection_does_not_identify_parallel_trends():
    report = StandardDifferenceInDifferences.pure_step(_standard(), {})["report"]
    assert report.point_estimate == pytest.approx(3.0)
    assert report.diagnostics[0].details["status"] == "no_detected_pretrend"
    assert report.diagnostics[0].details["identification_authority"] is False


def test_differential_pretrend_is_evidence_of_violation():
    data = _standard(pre=4)
    outcome = data.outcome.copy()
    outcome[:3] += np.arange(6)
    report = StandardDifferenceInDifferences.pure_step(
        data.model_copy(update={"outcome": outcome}), {}
    )["report"]
    assert report.diagnostics[0].details["status"] == "evidence_of_violation"
    assert report.diagnostics[0].passed is False


@pytest.mark.parametrize("profile", ["HC1", "cluster"])
def test_independent_statsmodels_covariance_on_group_labelled_design(profile):
    data = _standard(pre=3)
    rng = np.random.default_rng(173)
    outcome = data.outcome + rng.normal(size=data.outcome.shape)
    data = data.model_copy(update={"outcome": outcome})
    # Construct the reference by labelled observation tuples, independent of owner flattening.
    rows = [(i, t, float(outcome[i, t])) for i in range(8) for t in range(5)]
    design = np.array([[1, int(t >= 3), int(i < 3), int(t >= 3 and i < 3)] for i, t, _ in rows])
    reference = OLS(np.array([y for _, _, y in rows]), design).fit()
    covariance = (
        reference.get_robustcov_results(cov_type="HC1").cov_params()
        if profile == "HC1"
        else cov_cluster(reference, [i for i, _, _ in rows], use_correction=False)
    )
    report = StandardDifferenceInDifferences.pure_step(data, {"cov_type": profile})["report"]
    assert report.point_estimate == pytest.approx(reference.params[3])
    assert report.standard_error == pytest.approx(np.sqrt(covariance[3, 3]))
    assert (
        report.method_params["inference_scope"] == "large_independent_units"
        if profile == "cluster"
        else report.method_params["inference_scope"] == "iid_rows"
    )


def test_actual_registry_retirement_old_slots_dispatch_and_fresh_cas(tmp_path):
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    with pytest.raises(MethodNotFoundError):
        registry.get("causal.inference.difference_in_differences@1.0.0")
    canonical = registry.get("causal.inference.did.standard@1.0.0")
    data = _standard()
    old_data = DifferenceInDifferences.materialize_input(
        {
            "outcome_panel": data.outcome,
            "treatment_indicator": data.treatment,
            "time_treatment": data.time_treatment,
            "unit_ids": data.unit_ids,
        },
        {},
    )
    dispatch = MethodDispatcher.get_instance()
    old = dispatch.dispatch(
        method_class=DifferenceInDifferences,
        signature=DifferenceInDifferences.signature,
        state=old_data,
        params={"staggered": False, "confidence_level": 0.8},
        seed=3,
    )
    new = dispatch.dispatch(
        method_class=canonical,
        signature=canonical.signature,
        state=data,
        params={"confidence_level": 0.8},
        seed=3,
    )
    for output in (old.output, new.output):
        assert {slot.name for slot in canonical.signature.output_slots} <= output.keys()
        assert output["result"] is output["report"]
        assert output["uncertainty_envelope"] is output["envelope"]
        assert output["report"].point_estimate == pytest.approx(3.0)
    assert old.output["report"].method_params == new.output["report"].method_params
    ref = persist_causal_effect_report(FileSystemCAS(tmp_path), new.output["report"])
    reader = load_causal_effect_report(FileSystemCAS(tmp_path), ref)
    assert reader.point_estimate == pytest.approx(3.0)
    assert reader.confidence_level == 0.8
    assert reader.method_params["covariance_procedure"] == "hc1"
    # A real stale planner route fails resolution after retirement.
    with pytest.raises(MethodNotFoundError):
        registry.get(DifferenceInDifferences.signature.fqn)


def test_dedicated_metadata_and_estimator_survive_legacy_metadata_replacement(monkeypatch):
    before = StandardDifferenceInDifferences.pure_step(_standard(), {})["report"]
    monkeypatch.setattr(
        DifferenceInDifferences,
        "metadata",
        replace(
            DifferenceInDifferences.metadata,
            assumptions={"legacy_poison": "not canonical"},
            equations={"legacy_poison": "wrong"},
            citations=("legacy_poison",),
        ),
    )
    after = StandardDifferenceInDifferences.pure_step(_standard(), {})["report"]
    assert after.point_estimate == before.point_estimate
    assert after.assumptions == before.assumptions
    assert "legacy_poison" not in StandardDifferenceInDifferences.metadata.assumptions
