from __future__ import annotations

import pytest

from polisyos.ir.queries import DataFilter, DataViewRequest, QueryScope, ValidTimeRange


def test_query_scope_aliases() -> None:
    scope = QueryScope(valid_time=ValidTimeRange(from_="2024-01-01", to="2024-12-31"))
    dumped = scope.model_dump(by_alias=True)
    assert dumped["valid_time"]["from"] == "2024-01-01"
    assert dumped["valid_time"]["to"] == "2024-12-31"


def test_data_filter_rejects_float() -> None:
    with pytest.raises(ValueError):
        DataFilter(column="x", op=">", value=0.5)


def test_data_view_request_minimal() -> None:
    request = DataViewRequest(
        request_id="req_1",
        scope=QueryScope(),
        view_type="snapshot",
        metrics=["metric_a"],
    )
    assert request.request_id == "req_1"
