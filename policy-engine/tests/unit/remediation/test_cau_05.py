"""Regression witnesses for the CAU-05 dedicated DiD compatibility adapter."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal import did as did_module
from polisyos.foundry.methods.catalog.causal.did import (
    DifferenceInDifferences,
    StaggeredDifferenceInDifferences,
    StandardDifferenceInDifferences,
)
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.ir.analytics.causal import EstimationStatus


def _panel() -> PanelObservationalData:
    return PanelObservationalData(
        outcome=np.array(
            [
                [1.0, 2.5, 7.0, 8.5],
                [2.0, 1.0, 5.5, 7.5],
                [0.0, 1.5, 2.0, 3.0],
                [1.0, 0.5, 3.5, 4.0],
            ]
        ),
        treatment=np.array([1, 1, 0, 0]),
        time_treatment=2,
        unit_ids=np.array(["treated-a", "treated-b", "control-a", "control-b"]),
    )


def _staggered_panel() -> PanelObservationalData:
    timing = np.array([2, 2, 3, 3, -1, -1], dtype=int)
    outcome = np.zeros((timing.size, 5), dtype=float)
    outcome[:2, 2:] = 2.0
    outcome[2:4, 3:] = 10.0
    return PanelObservationalData(
        outcome=outcome,
        treatment=(timing >= 0).astype(int),
        time_treatment=2,
        treatment_timing=timing,
        unit_ids=np.arange(timing.size),
    )


def _report(output: dict[str, object]):
    return output["report"]


def test_cau_05_legacy_staggered_slots_match_dedicated_request() -> None:
    """Historical slots are adapted to the dedicated staggered estimator."""

    data = _staggered_panel()
    legacy_data = DifferenceInDifferences.materialize_input(
        {
            "outcome_panel": data.outcome,
            "treatment_indicator": data.treatment,
            "time_treatment": data.time_treatment,
            "treatment_timing": data.treatment_timing,
            "unit_ids": data.unit_ids,
        },
        {},
    )
    params = {
        "staggered": True,
        "control_group": "not_yet_treated",
        "n_bootstrap": 100,
    }
    legacy = DifferenceInDifferences.pure_step(
        legacy_data,
        {**params, "__rng__": np.random.default_rng(13)},
    )
    dedicated = StaggeredDifferenceInDifferences.pure_step(
        data,
        {**params, "__rng__": np.random.default_rng(13)},
    )

    legacy_report = _report(legacy)
    dedicated_report = _report(dedicated)
    assert legacy_report.status == dedicated_report.status == EstimationStatus.SUCCESS
    assert legacy_report.model_dump(mode="json") == dedicated_report.model_dump(mode="json")
    assert legacy["warnings"] == dedicated["warnings"]
    assert legacy["result"] is legacy["report"]
    assert dedicated["result"] is dedicated["report"]
    assert legacy["uncertainty_envelope"] is legacy["envelope"]
    assert dedicated["uncertainty_envelope"] is dedicated["envelope"]
    assert legacy["envelope"].model_dump(mode="json") == dedicated["envelope"].model_dump(
        mode="json"
    )


@pytest.mark.parametrize("mode", [False, np.bool_(False)])
def test_cau_05_standard_old_slots_and_boolean_mode_preserve_whole_report(mode) -> None:
    data = _panel()
    old = DifferenceInDifferences.materialize_input(
        {
            "outcome_panel": data.outcome,
            "treatment_indicator": data.treatment,
            "time_treatment": data.time_treatment,
            "unit_ids": data.unit_ids,
        },
        {},
    )
    params = {"cov_type": "cluster", "confidence_level": 0.8}
    legacy = DifferenceInDifferences.pure_step(old, {**params, "staggered": mode})
    dedicated = StandardDifferenceInDifferences.pure_step(data, params)
    assert legacy["report"].status is EstimationStatus.SUCCESS
    assert legacy["report"].model_dump(mode="json") == dedicated["report"].model_dump(mode="json")
    assert legacy["warnings"] == dedicated["warnings"]


@pytest.mark.parametrize("mode", [True, np.bool_(True)])
def test_cau_05_staggered_boolean_mode_preserves_whole_report(mode) -> None:
    data = _staggered_panel()
    params = {"n_bootstrap": 399, "control_group": "not_yet_treated", "confidence_level": 0.95}
    legacy = DifferenceInDifferences.pure_step(
        data,
        {
            **params,
            "staggered": mode,
            "__rng__": np.random.default_rng(13),
        },
    )
    dedicated = StaggeredDifferenceInDifferences.pure_step(
        data,
        {
            **params,
            "__rng__": np.random.default_rng(13),
        },
    )
    assert legacy["report"].status is EstimationStatus.SUCCESS
    assert legacy["report"].model_dump(mode="json") == dedicated["report"].model_dump(mode="json")
    assert legacy["warnings"] == dedicated["warnings"]


@pytest.mark.parametrize("mode", ["false", "true", "not-a-bool", 0, 1, None, [], {}])
def test_cau_05_legacy_staggered_flag_rejects_ambiguous_mode(mode) -> None:
    """An invalid legacy mode must not silently select the staggered estimator."""

    report = _report(DifferenceInDifferences.pure_step(_panel(), {"staggered": mode}))

    assert report.status is EstimationStatus.INPUT_INVALID
    assert report.status_reason == "staggered must be a boolean"
    assert report.point_estimate is None


def test_cau_05_staggered_request_rejects_unknown_control_group() -> None:
    """An unsupported control rule must fail closed instead of becoming never-treated."""

    report = _report(
        StaggeredDifferenceInDifferences.pure_step(
            _staggered_panel(),
            {
                "control_group": "all_units",
                "n_bootstrap": 50,
                "__rng__": np.random.default_rng(13),
            },
        )
    )

    assert report.status is EstimationStatus.INPUT_INVALID
    assert report.status_reason == "unsupported control_group: all_units"
    assert report.point_estimate is None


def test_cau_05_legacy_adapter_rejects_conflicting_slot_aliases() -> None:
    """A frozen request cannot provide both legacy and dedicated slot identities."""

    data = _panel()
    with pytest.raises(
        ValueError,
        match="outcome_panel and outcome cannot both be supplied",
    ):
        DifferenceInDifferences.materialize_input(
            {
                "outcome_panel": data.outcome,
                "outcome": data.outcome,
                "treatment_indicator": data.treatment,
                "time_treatment": data.time_treatment,
            },
            {},
        )


def test_cau_05_dedicated_methods_do_not_require_the_legacy_class_binding(monkeypatch) -> None:
    """Removing the deprecated wrapper cannot remove either dedicated numerical owner."""

    standard = StandardDifferenceInDifferences.pure_step(_panel(), {})["report"]
    staggered = StaggeredDifferenceInDifferences.pure_step(
        _staggered_panel(),
        {
            "n_bootstrap": 399,
            "__rng__": np.random.default_rng(17),
        },
    )["report"]
    monkeypatch.delattr(did_module, "DifferenceInDifferences")
    actual_standard = StandardDifferenceInDifferences.pure_step(_panel(), {})["report"]
    actual_staggered = StaggeredDifferenceInDifferences.pure_step(
        _staggered_panel(),
        {
            "n_bootstrap": 399,
            "__rng__": np.random.default_rng(17),
        },
    )["report"]
    assert actual_standard.status is actual_staggered.status is EstimationStatus.SUCCESS
    assert actual_standard.model_dump(mode="json") == standard.model_dump(mode="json")
    assert actual_staggered.model_dump(mode="json") == staggered.model_dump(mode="json")
