from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.econometrics.protocols import (
    EconometricResult,
    PanelData,
    TimeSeriesData,
)


def test_panel_data_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="exog row count"):
        PanelData(
            dependent=np.ones(10),
            exog=np.ones((9, 2)),
            entity_ids=np.repeat(np.arange(5), 2),
            time_ids=np.tile(np.arange(2), 5),
        )


def test_time_series_data_rejects_short_series() -> None:
    with pytest.raises(ValueError, match="at least 8"):
        TimeSeriesData(endog=np.arange(4, dtype=float))


def test_econometric_result_to_uncertainty_envelope() -> None:
    result = EconometricResult(
        method_name="test",
        params={"beta": 1.2},
        std_errors={"beta": 0.1},
        confidence_intervals={"beta": (1.0, 1.4)},
        p_values={"beta": 0.01},
        n_obs=100,
    )

    envelope = result.to_uncertainty_envelope("beta")
    assert envelope is not None
    assert envelope.point_estimate == 1.2
    assert envelope.confidence_interval == (1.0, 1.4)
