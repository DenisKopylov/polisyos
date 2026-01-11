from __future__ import annotations

from polisyos.ir.data_views import DataViewRequest


def merge_pass(request: DataViewRequest) -> DataViewRequest:
    """
    Pass 3: merge/conflict policy placeholder.
    Currently a no-op; intended to enforce MergeRuleRegistry once registry is wired.
    """
    return request
