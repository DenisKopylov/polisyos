"""Tests for DatasetVersion and hash utilities (Track E, task E3)."""

from __future__ import annotations

import pandas as pd
import pytest

from polisyos.ir.data.versioning import (
    compute_content_hash,
    compute_schema_hash,
    version_dataset,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_df() -> pd.DataFrame:
    return pd.DataFrame({"X": [1, 2, 3], "Y": [0.1, 0.2, 0.3]})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_version_dataset_deterministic(simple_df: pd.DataFrame) -> None:
    """Same DataFrame produces identical content_hash and schema_hash."""
    v1 = version_dataset(simple_df, dataset_ref="ds_a")
    v2 = version_dataset(simple_df, dataset_ref="ds_a")
    assert v1.content_hash == v2.content_hash
    assert v1.schema_hash == v2.schema_hash


def test_schema_hash_column_order_stable() -> None:
    """schema_hash is identical regardless of column insertion order."""
    df1 = pd.DataFrame({"X": [1], "Y": [2.0]})
    df2 = df1[["Y", "X"]]  # reordered columns
    assert compute_schema_hash(df1) == compute_schema_hash(df2)


def test_content_hash_changes_on_data_mutation() -> None:
    """Changing a cell value produces a different content_hash."""
    df = pd.DataFrame({"X": [1, 2, 3], "Y": [0.1, 0.2, 0.3]})
    h1 = compute_content_hash(df)
    df2 = df.copy()
    df2.loc[0, "X"] = 999
    h2 = compute_content_hash(df2)
    assert h1 != h2


def test_schema_hash_changes_on_dtype_change() -> None:
    """Converting a column dtype produces a different schema_hash."""
    df1 = pd.DataFrame({"X": [1, 2, 3]})  # int64
    df2 = df1.astype({"X": float})  # float64
    assert compute_schema_hash(df1) != compute_schema_hash(df2)


def test_version_tag_optional(simple_df: pd.DataFrame) -> None:
    """version_tag defaults to None and can be set."""
    v_no_tag = version_dataset(simple_df, dataset_ref="ds")
    assert v_no_tag.version_tag is None

    v_tagged = version_dataset(simple_df, dataset_ref="ds", version_tag="v1.0")
    assert v_tagged.version_tag == "v1.0"


def test_version_dataset_fields(simple_df: pd.DataFrame) -> None:
    """Verify all fields are populated correctly."""
    v = version_dataset(simple_df, dataset_ref="my_ds", version_tag="initial")
    assert v.dataset_ref == "my_ds"
    assert v.n_obs == 3
    assert set(v.columns) == {"X", "Y"}
    assert len(v.content_hash) == 16
    assert len(v.schema_hash) == 16
    assert "T" in v.created_at  # ISO 8601 contains "T" between date and time
    assert v.version_tag == "initial"


def test_dataset_version_is_frozen(simple_df: pd.DataFrame) -> None:
    """DatasetVersion is a frozen Pydantic model."""
    v = version_dataset(simple_df, dataset_ref="ds")
    with pytest.raises(Exception):
        v.dataset_ref = "mutated"  # type: ignore[misc]


def test_content_hash_stable_across_column_order() -> None:
    """content_hash is identical regardless of column order."""
    df1 = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    df2 = df1[["B", "A"]]
    assert compute_content_hash(df1) == compute_content_hash(df2)


def test_version_different_refs_same_data(simple_df: pd.DataFrame) -> None:
    """Different dataset_ref values don't affect hashes."""
    v1 = version_dataset(simple_df, dataset_ref="ref_a")
    v2 = version_dataset(simple_df, dataset_ref="ref_b")
    assert v1.content_hash == v2.content_hash
    assert v1.schema_hash == v2.schema_hash
    assert v1.dataset_ref != v2.dataset_ref
