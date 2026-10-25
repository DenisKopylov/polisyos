from __future__ import annotations

import pandas as pd

from polisyos.fabric.data_plane.tabular import payload_to_dataframe


class _FrameConverter:
    def __init__(self, frame: pd.DataFrame) -> None:
        self._frame = frame

    def to_pandas(self) -> pd.DataFrame:
        return self._frame


class _RowsConverter:
    def to_pandas(self) -> list[dict[str, int]]:
        return [{"value": 1}]


def test_payload_to_dataframe_preserves_a_pandas_converter_frame() -> None:
    frame = pd.DataFrame({"value": [1]})

    assert payload_to_dataframe(_FrameConverter(frame)) is frame


def test_payload_to_dataframe_retains_coercion_for_legacy_converter_output() -> None:
    frame = payload_to_dataframe(_RowsConverter())

    assert frame is not None
    assert frame.to_dict(orient="records") == [{"value": 1}]
