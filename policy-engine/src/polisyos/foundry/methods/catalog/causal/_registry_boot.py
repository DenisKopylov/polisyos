from __future__ import annotations

from typing import Sequence

from polisyos.foundry.methods.catalog.causal.did import DifferenceInDifferences
from polisyos.foundry.methods.catalog.causal.rdd import RegressionDiscontinuity
from polisyos.foundry.methods.catalog.causal.scm import SyntheticControlMethod
from polisyos.foundry.methods.catalog.causal.structural_time_series import StructuralTimeSeries


def register_causal_methods() -> Sequence[type]:
    return (
        SyntheticControlMethod,
        DifferenceInDifferences,
        RegressionDiscontinuity,
        StructuralTimeSeries,
    )


__all__ = ["register_causal_methods"]

