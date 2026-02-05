"""Acquisition helper utilities."""

from __future__ import annotations

from polisyos.scientist.search.strategies.types import AcquisitionType


def is_batch_acquisition(acquisition: AcquisitionType) -> bool:
    """Return True when acquisition function is batch-oriented."""
    return acquisition in {
        AcquisitionType.QEI,
        AcquisitionType.QEHVI,
    }


def is_multi_objective_acquisition(acquisition: AcquisitionType) -> bool:
    """Return True when acquisition function is multi-objective."""
    return acquisition in {
        AcquisitionType.EHVI,
        AcquisitionType.QEHVI,
    }

