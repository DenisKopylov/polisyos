"""Distinguish selected identity membership from order without fitting a model."""

from __future__ import annotations

import hashlib
import json

import numpy as np

from polisyos.foundry.methods.catalog.causal.hte_v2 import _row_identity_hashes
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData


def test_row_identity_membership_and_order_are_independent_quantities() -> None:
    """Canonical order can coincide; a coordinated permutation separates them."""
    ids = [f"row-{index:03d}" for index in range(40)]
    data = HTEObservationalData(
        outcome=np.arange(40, dtype=float),
        treatment=np.tile(np.asarray([0, 1], dtype=int), 20),
        covariates=np.arange(80, dtype=float).reshape(40, 2),
        sample_ids=np.asarray(ids),
    )

    def digest(values: object) -> str:
        return hashlib.sha256(
            json.dumps(
                values, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()

    membership, ordered, sample_ids, status = _row_identity_hashes(data)
    assert membership == ordered == sample_ids == digest(ids)
    assert status == "provided"

    reversed_data = HTEObservationalData(
        outcome=data.outcome[::-1],
        treatment=data.treatment[::-1],
        covariates=data.covariates[::-1],
        sample_ids=data.sample_ids[::-1],
    )
    reversed_membership, reversed_order, reversed_ids, reversed_status = _row_identity_hashes(
        reversed_data
    )
    assert reversed_membership == membership
    assert reversed_order == reversed_ids == digest(list(reversed(ids)))
    assert reversed_order != ordered
    assert reversed_status == status
