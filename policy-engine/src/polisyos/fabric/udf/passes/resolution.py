from __future__ import annotations

from polisyos.ir.data_views import DataViewRequest


def resolution_pass(request: DataViewRequest) -> DataViewRequest:
    """
    Pass 1: resolve human-friendly fields (placeholder for predicate/slot resolution).
    Currently returns the request unchanged but serves as the hook for predicate/slot
    normalization once PredicateRegistry is populated.
    """
    return request
