"""Data Plane — orchestration layer for ingestion + snapshot production."""

from .semantic_diff import compare_historical_rows, persist_historical_semantic_diff_report

__all__ = [
    "compare_historical_rows",
    "persist_historical_semantic_diff_report",
]
