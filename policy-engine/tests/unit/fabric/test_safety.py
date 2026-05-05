from __future__ import annotations

import pytest
from polisyos.fabric.safety import (
    UnsafeDataPathError,
    UnsafeIdentifierError,
    UnsafePathSegmentError,
    quote_sql_identifier,
    safe_path_segment,
    validate_data_path,
    validate_sql_identifier,
)


def test_validate_sql_identifier_accepts_world_query_policy() -> None:
    assert validate_sql_identifier("claims") == "claims"
    assert quote_sql_identifier("world.claims", allow_dotted=True) == '"world"."claims"'


def test_validate_sql_identifier_rejects_unsafe_input() -> None:
    with pytest.raises(UnsafeIdentifierError, match="Unsafe identifier"):
        validate_sql_identifier("claims; DROP TABLE world.claims")


def test_safe_path_segment_percent_encodes_spaces() -> None:
    assert safe_path_segment("GDP per capita") == "GDP%20per%20capita"


def test_safe_path_segment_rejects_traversal() -> None:
    with pytest.raises(UnsafePathSegmentError, match="traversal"):
        safe_path_segment("..")


def test_validate_data_path_rejects_invalid_tokens() -> None:
    with pytest.raises(UnsafeDataPathError, match="Unsafe data_path token"):
        validate_data_path("data.__private")


def test_validate_data_path_rejects_excessive_depth() -> None:
    with pytest.raises(UnsafeDataPathError, match="depth"):
        validate_data_path("a.b.c.d.e.f.g.h.i")
