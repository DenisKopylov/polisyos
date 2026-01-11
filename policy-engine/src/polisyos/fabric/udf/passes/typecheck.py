from __future__ import annotations

from polisyos.ir.data_views import DataViewRequest


def typecheck_pass(request: DataViewRequest) -> DataViewRequest:
    """
    Pass 2: type/unit validation placeholder.
    Ensures metrics are present; real unit compatibility logic will be added later.
    """
    if not request.metrics:
        raise ValueError("DataViewRequest must specify at least one metric")
    return request
