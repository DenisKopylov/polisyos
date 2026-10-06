"""Behavioral witnesses for CAU-04 (B212/B213).

The DoWhy dependency is optional and unavailable in the supported Python 3.14
profile.  These tests therefore replace only the dependency loader with a
small legacy-inprocess recorder; these are not actual-backend witnesses.  The recorder still exercises the normal DoWhy adapter entry
point and makes the constructor, identification, and estimation arguments
observable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal import dowhy_identify_estimate as dowhy_module
from polisyos.foundry.methods.catalog.causal.dowhy_identify_estimate import (
    DoWhyIdentifyEstimate,
)
from polisyos.foundry.methods.catalog.causal.protocols import GraphCausalData
from polisyos.ir.analytics.causal import CausalMethod, EstimationStatus


def _data() -> GraphCausalData:
    return GraphCausalData(
        data=np.asarray(
            [
                [0.0, 1.0],
                [1.0, 3.0],
                [0.0, 2.0],
                [1.0, 4.0],
            ]
        ),
        column_names=["treatment", "outcome"],
        treatment="treatment",
        outcome="outcome",
        graph_dot="digraph { treatment -> outcome; }",
        graph_ref="cas:graph:cau-04",
    )


@dataclass
class _Estimate:
    value: float = 7.0
    interval: tuple[float, float] | None = (5.0, 9.0)
    standard_error: float | None = None

    def get_confidence_intervals(self) -> tuple[float, float] | None:
        return self.interval

    def get_standard_error(self) -> float | None:
        return self.standard_error


class _Identified:
    def __init__(self, label: str, estimand_type: str) -> None:
        self.label = label
        self.estimand_type = estimand_type

    def __str__(self) -> str:
        return self.label


class _RecorderModel:
    instances: ClassVar[list[_RecorderModel]] = []
    estimate = _Estimate()
    identified_type: str | None = None

    def __init__(self, **kwargs: Any) -> None:
        self.constructor_kwargs = kwargs
        self.identify_kwargs: dict[str, Any] | None = None
        self.estimate_kwargs: dict[str, Any] | None = None
        self.identified = _Identified("identified", "nonparametric-ate")
        type(self).instances.append(self)

    def identify_effect(self, **kwargs: Any) -> _Identified:
        self.identify_kwargs = kwargs
        self.identified.estimand_type = type(self).identified_type or kwargs["estimand_type"]
        return self.identified

    def estimate_effect(self, identified: _Identified, **kwargs: Any) -> _Estimate:
        assert identified is self.identified
        self.estimate_kwargs = kwargs
        return type(self).estimate


class _RecorderDoWhy:
    CausalModel = _RecorderModel


class _RecorderPandas:
    @staticmethod
    def DataFrame(data: Any, columns: list[str]) -> dict[str, Any]:  # noqa: N802 -- legacy pandas ABI
        return {"data": data, "columns": columns}


@pytest.fixture(autouse=True)
def _reset_recorder() -> None:
    _RecorderModel.instances.clear()
    _RecorderModel.estimate = _Estimate()
    _RecorderModel.identified_type = None


def _load_recorders() -> tuple[_RecorderDoWhy, _RecorderPandas]:
    return _RecorderDoWhy(), _RecorderPandas()


def test_point_only_dowhy_result_preserves_point_without_epsilon_ci(monkeypatch) -> None:
    _RecorderModel.estimate = _Estimate(value=7.0, interval=None, standard_error=None)
    monkeypatch.setattr(dowhy_module, "_load_dowhy_dependencies", _load_recorders)

    output = DoWhyIdentifyEstimate.pure_step(
        _data(),
        {"method_name": "backdoor.linear_regression", "execution_profile": "legacy-inprocess"},
    )
    report = output["report"]

    assert report.status is EstimationStatus.NUMERICAL_FAILURE
    assert report.point_estimate == pytest.approx(7.0)
    assert report.confidence_interval is None
    assert report.confidence_level is None
    assert report.metadata["inference_status"] == "point_only"
    assert report.to_uncertainty_envelope().gate_eligible is False
    assert report.to_uncertainty_envelope().ci_width > 1.0e6


def test_real_interval_is_preserved_and_remains_success(monkeypatch) -> None:
    _RecorderModel.estimate = _Estimate(value=7.0, interval=(5.0, 9.0), standard_error=1.0)
    monkeypatch.setattr(dowhy_module, "_load_dowhy_dependencies", _load_recorders)

    output = DoWhyIdentifyEstimate.pure_step(
        _data(),
        {"method_name": "backdoor.linear_regression", "execution_profile": "legacy-inprocess"},
    )
    report = output["report"]

    assert report.status is EstimationStatus.SUCCESS
    assert report.point_estimate == pytest.approx(7.0)
    assert report.confidence_interval == pytest.approx((5.0, 9.0))
    assert report.standard_error == pytest.approx(1.0)


def test_requested_estimand_is_bound_to_model_and_identification(monkeypatch) -> None:
    monkeypatch.setattr(dowhy_module, "_load_dowhy_dependencies", _load_recorders)

    output = DoWhyIdentifyEstimate.pure_step(
        _data(),
        {
            "execution_profile": "legacy-inprocess",
            "estimand_type": "nonparametric-nie",
            "method_name": "backdoor.linear_regression",
        },
    )
    report = output["report"]
    model = _RecorderModel.instances[-1]

    assert report.status is EstimationStatus.SUCCESS
    assert report.estimand_type == "nonparametric-nie"
    assert report.identified_estimand == "identified"
    assert model.constructor_kwargs["estimand_type"] == "nonparametric-nie"
    assert model.identify_kwargs == {
        "estimand_type": "nonparametric-nie",
        "proceed_when_unidentifiable": False,
    }
    assert model.estimate_kwargs is not None
    assert model.estimate_kwargs["method_name"] == "backdoor.linear_regression"
    assert model.estimate_kwargs["confidence_intervals"] is True


def test_backend_estimand_mismatch_is_not_relabelled(monkeypatch) -> None:
    _RecorderModel.identified_type = "nonparametric-ate"
    monkeypatch.setattr(dowhy_module, "_load_dowhy_dependencies", _load_recorders)

    output = DoWhyIdentifyEstimate.pure_step(
        _data(),
        {
            "execution_profile": "legacy-inprocess",
            "estimand_type": "nonparametric-nie",
            "method_name": "backdoor.linear_regression",
        },
    )
    report = output["report"]

    assert report.status is EstimationStatus.ASSUMPTION_FAILED
    assert report.point_estimate is None
    assert report.metadata["capability"] == "estimand_binding_mismatch"
    assert report.metadata["identified_estimand_type"] == "nonparametric-ate"


def test_unsupported_estimand_is_an_explicit_capability_result(monkeypatch) -> None:
    def _unexpected_backend_load() -> tuple[Any, Any]:
        pytest.fail("unsupported estimand must be rejected before backend loading")

    monkeypatch.setattr(dowhy_module, "_load_dowhy_dependencies", _unexpected_backend_load)

    output = DoWhyIdentifyEstimate.pure_step(
        _data(),
        {"estimand_type": "unsupported-profile", "execution_profile": "legacy-inprocess"},
    )
    report = output["report"]

    assert report.status is EstimationStatus.INPUT_INVALID
    assert report.point_estimate is None
    assert report.confidence_interval is None
    assert report.metadata["capability"] == "unsupported_estimand_type"
    assert "unsupported-profile" in (report.status_reason or "")
    assert report.method is CausalMethod.DOWHY_BACKDOOR
