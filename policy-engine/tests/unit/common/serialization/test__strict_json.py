from __future__ import annotations

import pytest

from polisyos.common import serialization


def test_decode_json_object_preserves_valid_null_boolean_and_finite_numbers() -> None:
    assert serialization.decode_json_object(
        b'{"nullable":null,"enabled":false,"nested":[true,1,-0.25,1e12]}',
        source="decoder fixture",
    ) == {
        "nullable": None,
        "enabled": False,
        "nested": [True, 1, -0.25, 1e12],
    }


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(b'{"probe":NaN}', id="nan-token"),
        pytest.param(b'{"probe":Infinity}', id="positive-infinity-token"),
        pytest.param(b'{"probe":-Infinity}', id="negative-infinity-token"),
        pytest.param(b'{"probe":1e999}', id="decimal-overflow"),
        pytest.param(b'{"probe":{"values":[NaN]}}', id="nested-nan-token"),
        pytest.param(b'{"probe":{"values":[1e999]}}', id="nested-decimal-overflow"),
        pytest.param(b'{"probe":1,"probe":2}', id="duplicate-root-key"),
        pytest.param(b'{"probe":{"value":1,"value":2}}', id="duplicate-nested-key"),
        pytest.param(
            b'{"probe":1,"\\u0070robe":2}',
            id="duplicate-decoded-root-key",
        ),
    ],
)
def test_decode_json_object_rejects_nonfinite_numbers_and_ambiguous_keys(
    raw: bytes,
) -> None:
    with pytest.raises(ValueError, match=r"Malformed JSON record at decoder fixture"):
        serialization.decode_json_object(raw, source="decoder fixture")
