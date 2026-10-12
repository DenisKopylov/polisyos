"""Source-bound, multiplicity-preserving E02 occurrence identity comparison.

This is an immutable raw counterpart to the local author-report map helper. It
reuses the registered emitter's source loader and canonical coverage document.
It does not assign property outcomes or formal closures.
"""
from __future__ import annotations

from collections import Counter
from typing import Any


def coverage_occurrence_keys(coverage: dict[str, Any], coverage_path: str) -> list[tuple[str, str, str]]:
    """Return every exact canonical occurrence identity without collapsing repeats."""
    rows: list[tuple[str, str, str]] = []
    for finding_index, finding in enumerate(coverage.get("findings", [])):
        finding_id = finding.get("id")
        if not isinstance(finding_id, str) or not isinstance(finding.get("criterion_refs"), list):
            raise ValueError(f"invalid coverage row at index {finding_index}")
        for criterion_index, criterion in enumerate(finding["criterion_refs"]):
            digest = criterion.get("sha256")
            if not isinstance(digest, str) or len(digest) != 64:
                raise ValueError(f"invalid criterion digest: {finding_id}/{criterion_index}")
            pointer = f"{coverage_path}#/findings/{finding_index}/criterion_refs/{criterion_index}"
            rows.append((finding_id, pointer, digest))
    return rows


def ledger_occurrence_keys(ledger: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return all ledger occurrence identities, preserving duplicate rows."""
    rows: list[tuple[str, str, str]] = []
    for finding in ledger.get("findings", []):
        finding_id = finding.get("finding_id")
        if not isinstance(finding_id, str):
            raise ValueError("invalid finding ID in ledger")
        for occurrence in finding.get("occurrences", []):
            original = occurrence.get("original", {})
            pointer = original.get("occurrence_pointer")
            digest = original.get("sha256")
            if not isinstance(pointer, str) or not isinstance(digest, str) or len(digest) != 64:
                raise ValueError(f"invalid ledger occurrence identity: {finding_id}")
            rows.append((finding_id, pointer, digest))
    return rows


def draft_occurrence_keys(draft: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return all preparation-draft occurrence identities, preserving duplicate rows."""
    rows: list[tuple[str, str, str]] = []
    for index, occurrence in enumerate(draft.get("occurrences", [])):
        identity = occurrence.get("key", {})
        finding_id = identity.get("finding_id")
        pointer = identity.get("coverage_pointer")
        digest = identity.get("criterion_sha256")
        if not all(isinstance(value, str) and value for value in (finding_id, pointer, digest)) or len(digest) != 64:
            raise ValueError(f"invalid draft occurrence identity at index {index}")
        rows.append((finding_id, pointer, digest))
    return rows


def require_same_occurrence_multiset(
    expected: list[tuple[str, str, str]], actual: list[tuple[str, str, str]], *, label: str
) -> None:
    """Reject missing, duplicate, substituted, or extra canonical occurrence keys."""
    expected_counts = Counter(expected)
    actual_counts = Counter(actual)
    if expected_counts != actual_counts:
        missing = list((expected_counts - actual_counts).items())
        extra = list((actual_counts - expected_counts).items())
        raise ValueError(
            f"{label} occurrence multiset differs: expected={len(expected)}, actual={len(actual)}, "
            f"missing={missing[:2]}, extra={extra[:2]}"
        )
