"""Shared payloads for world templates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class MaterializedWorldPayload:
    """One fully materialized synthetic world."""

    latent_table: dict[str, np.ndarray]
    observed_table: dict[str, np.ndarray]
    truth_registry: dict[str, dict[str, Any]]
    metadata: dict[str, Any]
    splits: dict[str, np.ndarray]


def default_splits(n_rows: int) -> dict[str, np.ndarray]:
    """Deterministic train/validation/test split helper."""
    index = np.arange(n_rows, dtype=int)
    bucket = index % 10
    return {
        "train": index[bucket < 6],
        "validation": index[(bucket >= 6) & (bucket < 8)],
        "test": index[bucket >= 8],
        "all": index,
    }


__all__ = ["MaterializedWorldPayload", "default_splits"]
