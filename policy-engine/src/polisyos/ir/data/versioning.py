"""DatasetVersion — reproducibility tracking for DataFrames in the causal engine.

A :class:`DatasetVersion` is a compact, hashable snapshot of a DataFrame's
identity: schema (column names + dtypes) and content (row data).  It enables
downstream components to detect dataset mutations between pipeline runs.

Usage example::

    import pandas as pd
    from polisyos.ir.data.versioning import version_dataset

    df = pd.DataFrame({"X": [1, 2, 3], "Y": [0.1, 0.2, 0.3]})
    ver = version_dataset(df, dataset_ref="rct_2024")
    print(ver.content_hash)   # e.g. "3a8f2c1d4e7b9f0a"

Design
------
- Frozen Pydantic model (``extra="forbid"``) — project standard.
- Hashes are 16-char hex (64-bit prefix of SHA-256) — readable, collision-resistant.
- pandas imported lazily inside helper functions.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    import pandas as pd


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class DatasetVersion(BaseModel):
    """Reproducibility snapshot for a single dataset / DataFrame.

    Attributes
    ----------
    dataset_ref:
        Logical identifier matching :attr:`DatasetEntry.dataset_ref` in the
        knowledge base.
    content_hash:
        16-char hex prefix of SHA-256 computed over the CSV representation of
        the DataFrame (columns sorted for stability).  Changes whenever any
        cell value changes.
    schema_hash:
        16-char hex prefix of SHA-256 computed over a JSON dict of
        ``{column_name: dtype_string}`` (sorted keys).  Changes only when the
        schema changes.
    n_obs:
        Number of rows at version time.
    columns:
        Ordered tuple of column names at version time.
    created_at:
        ISO 8601 UTC timestamp of when the version was created.
    version_tag:
        Optional user-supplied label (e.g. ``"v1.2"``, ``"pre-cleaning"``).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_ref: str
    content_hash: str
    schema_hash: str
    n_obs: int
    columns: tuple[str, ...]
    created_at: str
    version_tag: str | None = None


# ---------------------------------------------------------------------------
# Hash utilities
# ---------------------------------------------------------------------------


def compute_schema_hash(df: pd.DataFrame) -> str:
    """Return a 16-char hex hash of *df*'s schema (column names + dtypes).

    The hash is stable regardless of column order in *df*.
    """
    schema_repr = json.dumps(
        {col: str(dtype) for col, dtype in df.dtypes.items()},
        sort_keys=True,
    )
    return hashlib.sha256(schema_repr.encode()).hexdigest()[:16]


def compute_content_hash(df: pd.DataFrame) -> str:
    """Return a 16-char hex hash of *df*'s content.

    Columns are sorted before serialisation so that the hash is stable
    regardless of column order.

    Note
    ----
    Uses ``DataFrame.to_csv()`` which is deterministic for the same data.
    For DataFrames with >100 k rows this may be slow; a future optimisation
    can use ``pandas.util.hash_dataframe`` or row sampling.
    """
    sorted_cols = sorted(df.columns)
    content_repr = df[sorted_cols].to_csv(index=False)
    return hashlib.sha256(content_repr.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def version_dataset(
    df: pd.DataFrame,
    dataset_ref: str,
    *,
    version_tag: str | None = None,
) -> DatasetVersion:
    """Create a :class:`DatasetVersion` snapshot for *df*.

    Parameters
    ----------
    df:
        The DataFrame to snapshot.
    dataset_ref:
        Logical identifier for this dataset.
    version_tag:
        Optional label (free-form string).

    Returns
    -------
    DatasetVersion
        Frozen version record.
    """
    from datetime import datetime

    return DatasetVersion(
        dataset_ref=dataset_ref,
        content_hash=compute_content_hash(df),
        schema_hash=compute_schema_hash(df),
        n_obs=len(df),
        columns=tuple(df.columns),
        created_at=datetime.now(UTC).isoformat(),
        version_tag=version_tag,
    )


__all__ = [
    "DatasetVersion",
    "compute_content_hash",
    "compute_schema_hash",
    "version_dataset",
]
