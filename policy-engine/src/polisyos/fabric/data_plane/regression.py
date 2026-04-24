"""Deterministic regression comparison for record/replay CI-hardening.

Compares normalized CAS artifacts (evidence bundle, snapshot) between
a record run and a replay run. Does NOT compare raw HTTP fixtures
(timing and headers vary between runs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from polisyos.fabric.data_plane.orchestrator import IngestionResult


class RegressionIssueCategory(str, Enum):
    """Typed regression issue categories for replay diagnostics."""

    TRANSIENT_IO = "transient_io"
    FIXTURE_MISSING = "fixture_missing"
    COMPARISON_MISMATCH = "comparison_mismatch"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class RegressionResult:
    """Result of comparing a record run with a replay run."""

    match: bool
    mismatches: list[str] = field(default_factory=list)
    issue_categories: tuple[RegressionIssueCategory, ...] = ()


def compare_ingestion_runs(
    record_result: IngestionResult,
    replay_result: IngestionResult,
) -> RegressionResult:
    """Compare two IngestionResult objects for deterministic equivalence.

    Checks:
    1. datasets_fetched matches
    2. evidence_bundle_ref presence matches
    3. data_snapshot_ref presence matches
    4. warnings match (order-independent)
    """
    mismatches: list[str] = []

    # Compare datasets_fetched
    if record_result.datasets_fetched != replay_result.datasets_fetched:
        mismatches.append(
            f"datasets_fetched: record={record_result.datasets_fetched}, "
            f"replay={replay_result.datasets_fetched}"
        )

    # Compare evidence bundle presence
    record_has_evidence = record_result.evidence_bundle_ref is not None
    replay_has_evidence = replay_result.evidence_bundle_ref is not None
    if record_has_evidence != replay_has_evidence:
        mismatches.append(
            f"evidence_bundle_ref: record={'present' if record_has_evidence else 'absent'}, "
            f"replay={'present' if replay_has_evidence else 'absent'}"
        )

    # Compare data snapshot presence
    record_has_snapshot = record_result.data_snapshot_ref is not None
    replay_has_snapshot = replay_result.data_snapshot_ref is not None
    if record_has_snapshot != replay_has_snapshot:
        mismatches.append(
            f"data_snapshot_ref: record={'present' if record_has_snapshot else 'absent'}, "
            f"replay={'present' if replay_has_snapshot else 'absent'}"
        )

    # Compare warnings (order-independent)
    record_warnings = set(record_result.warnings)
    replay_warnings = set(replay_result.warnings)
    if record_warnings != replay_warnings:
        only_record = record_warnings - replay_warnings
        only_replay = replay_warnings - record_warnings
        parts = []
        if only_record:
            parts.append(f"only in record: {sorted(only_record)}")
        if only_replay:
            parts.append(f"only in replay: {sorted(only_replay)}")
        mismatches.append(f"warnings differ: {'; '.join(parts)}")

    return RegressionResult(
        match=len(mismatches) == 0,
        mismatches=mismatches,
        issue_categories=((RegressionIssueCategory.COMPARISON_MISMATCH,) if mismatches else ()),
    )


def compare_artifact_hashes(
    store: Any,
    record_ref: Any,
    replay_ref: Any,
    *,
    label: str = "artifact",
) -> list[str]:
    """Compare content hashes of two CAS artifacts.

    Returns list of mismatch descriptions (empty if identical).
    """
    mismatches: list[str] = []
    try:
        record_manifest = store.get_manifest(record_ref)
        replay_manifest = store.get_manifest(replay_ref)

        if record_manifest.content_hash != replay_manifest.content_hash:
            mismatches.append(
                f"{label} content_hash: record={record_manifest.content_hash}, "
                f"replay={replay_manifest.content_hash}"
            )
    except Exception as exc:
        category = categorize_regression_exception(exc)
        mismatches.append(f"{label} comparison failed [{category.value}]: {exc}")

    return mismatches


def categorize_regression_exception(exc: Exception) -> RegressionIssueCategory:
    """Categorize replay/regression exceptions into stable governance buckets."""
    if isinstance(exc, FileNotFoundError):
        return RegressionIssueCategory.FIXTURE_MISSING
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return RegressionIssueCategory.TRANSIENT_IO
    if isinstance(exc, OSError):
        return RegressionIssueCategory.TRANSIENT_IO
    return RegressionIssueCategory.INTERNAL_ERROR


__all__ = [
    "RegressionIssueCategory",
    "RegressionResult",
    "categorize_regression_exception",
    "compare_artifact_hashes",
    "compare_ingestion_runs",
]
