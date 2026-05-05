from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st
from polisyos.common.serialization import fast_json_dumps, fast_json_loads

_JSON_SCALARS = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**63), max_value=(2**63) - 1),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(),
)
_JSON_VALUES = st.recursive(
    _JSON_SCALARS,
    lambda children: st.one_of(
        st.lists(children, max_size=8),
        st.dictionaries(st.text(min_size=1, max_size=12), children, max_size=8),
    ),
    max_leaves=24,
)


@pytest.mark.property
@given(payload=_JSON_VALUES)
def test_fast_json_roundtrip_property(payload: object) -> None:
    encoded = fast_json_dumps(payload, sort_keys=True)
    decoded = fast_json_loads(encoded)

    assert decoded == payload


@pytest.mark.property
@given(
    malformed=st.binary(min_size=1, max_size=128).filter(
        lambda value: not _looks_like_valid_json(value)
    )
)
def test_fast_json_loads_rejects_malformed_bytes(malformed: bytes) -> None:
    with pytest.raises((ValueError, json.JSONDecodeError, TypeError)):
        fast_json_loads(malformed)


def _looks_like_valid_json(raw: bytes) -> bool:
    try:
        fast_json_loads(raw)
    except (ValueError, json.JSONDecodeError, TypeError):
        return False
    return True
