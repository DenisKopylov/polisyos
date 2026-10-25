import numpy as np
import pandas as pd

from polisyos.fabric.connectors.contracts._inference_validation import _coerce_boolean
from tests._helpers.mirror_contracts import assert_source_stem_has_static_contract


def test__inference_validation_source_modules_have_static_contracts() -> None:
    assert_source_stem_has_static_contract("fabric", "_inference_validation")


def test_coerce_boolean_maps_missing_and_nonscalar_values_to_nullable_missing() -> None:
    values = pd.Series(
        [
            True,
            False,
            1,
            0,
            "YES",
            "no",
            None,
            float("nan"),
            pd.NA,
            [1, 0],
            np.array([1, 0]),
        ],
        dtype=object,
    )

    result = _coerce_boolean(values)

    assert result.dtype == "boolean"
    assert result.iloc[:6].tolist() == [True, False, True, False, True, False]
    assert result.iloc[6:].isna().all()
