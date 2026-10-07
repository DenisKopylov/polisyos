"""Maintained request FQN reaches the dedicated method and actual output consumer."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal.did import (
    DifferenceInDifferences,
    StandardDifferenceInDifferences,
)
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.foundry.methods.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.components.io import dematerialize_method_output
from polisyos.foundry.methods.exceptions import MethodNotFoundError
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import (
    EstimationStatus,
    load_causal_effect_report,
    persist_causal_effect_report,
)
from polisyos.runtime.quality.proving_ground import causal_forecast_search


@pytest.fixture(autouse=True)
def _isolate_registry():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def test_maintained_default_request_uses_real_dedicated_registry_dispatch_and_fresh_reader(
    monkeypatch, tmp_path
):
    request = causal_forecast_search._default_g2_runtime_method_candidate()
    assert request["truthfulness_status"] == "synthetic_fixture"
    assert request["source_request_kind"] == "synthetic_fixture"
    assert request["specification_space"]["primary"] == "standard_2x2_did"
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    method = registry.get(request["method_fqn"])
    assert method is StandardDifferenceInDifferences
    assert "staggered" not in {parameter.name for parameter in method.signature.parameters}
    assert {slot.name for slot in method.signature.input_slots} == {
        "outcome",
        "treatment",
        "time_treatment",
    }
    for old_fqn in (
        "causal.did.difference_in_differences@1.0.0",
        DifferenceInDifferences.signature.fqn,
    ):
        with pytest.raises(MethodNotFoundError):
            registry.get(old_fqn)

    def legacy_poison(*args, **kwargs):
        raise AssertionError("maintained request invoked the historical umbrella")

    monkeypatch.setattr(DifferenceInDifferences, "pure_step", legacy_poison)
    outcome = np.tile(np.arange(5, dtype=float), (8, 1))
    outcome[:3, 3:] += 3
    panel = PanelObservationalData(
        outcome=outcome,
        treatment=np.array([1, 1, 1, 0, 0, 0, 0, 0]),
        time_treatment=3,
        unit_ids=np.arange(8),
    )
    result = MethodDispatcher.get_instance().dispatch(
        method_class=method,
        signature=method.signature,
        state=panel,
        params={},
        seed=7,
    )
    report = result.output["report"]
    assert report.status is EstimationStatus.SUCCESS
    assert report.point_estimate == pytest.approx(3)
    assert report.confidence_level == 0.95
    assert report.method_params["covariance_procedure"] == "hc1"
    assert report.method_params["parallel_trends_identified"] is False
    slots = dematerialize_method_output(
        method_class=method, signature=method.signature, output=result.output
    )
    assert slots["report"] is report and slots["result"] is report
    ref = persist_causal_effect_report(FileSystemCAS(tmp_path), report)
    fresh = load_causal_effect_report(FileSystemCAS(tmp_path), ref)
    assert fresh.model_dump(mode="json") == report.model_dump(mode="json")
    # Synthetic planner refs/pass labels above did not provide Runtime authority;
    # this witness measures supported route/defaults/ABI and an actual synthetic job only.
