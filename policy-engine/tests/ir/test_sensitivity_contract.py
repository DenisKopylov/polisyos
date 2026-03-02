from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.sensitivity import (
    EValueResult,
    SensitivityResult,
    load_sensitivity_result,
    persist_sensitivity_result,
)


def test_sensitivity_result_rejects_invalid_e_value() -> None:
    with pytest.raises(ValueError, match="E-value must be >= 1.0"):
        SensitivityResult(e_value=0.99)


def test_sensitivity_result_persist_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    result = SensitivityResult(
        e_value=2.12,
        e_value_ci_lower=1.45,
        conversion_method="ate_to_rr_log",
        e_value_result=EValueResult(
            raw_effect=0.42,
            rr_equivalent=1.52,
            method="ate_to_rr_log",
            ci_rr=(1.1, 1.9),
            ci_crosses_null=False,
        ),
        robustness_value=0.12,
        partial_r2_treatment=0.08,
        rosenbaum_gamma=1.4,
        rosenbaum_p_value=0.08,
        interpretation="E-value=2.120; RV=0.120; Rosenbaum_Gamma=1.400; combined_assessment=robust.",
        is_robust=True,
    )

    ref = persist_sensitivity_result(store, result)
    loaded = load_sensitivity_result(store, ref)

    assert ref.kind == "ir.sensitivity_result"
    assert loaded == result
