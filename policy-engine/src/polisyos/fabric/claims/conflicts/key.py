"""Public conflicts key module API."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from polisyos.core.canon import content_hash
from polisyos.ir.canon import to_canonical_bytes
from polisyos.ir.world.claim import Claim
from polisyos.ir.world.conflict import ConflictKind

_WS_RE = re.compile(r"\s+")


def normalize_text_v1(value: str) -> str:
    """Normalize text v 1 helper."""
    return _WS_RE.sub(" ", value.strip()).casefold()


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def conflict_key_payload_v1(claim: Claim) -> dict[str, Any]:
    """Conflict key payload v 1 helper."""
    if claim.subject_id is not None:
        subject_key: dict[str, str] = {"subject_id": claim.subject_id}
    else:
        subject_key = {"subject_text_norm": normalize_text_v1(claim.subject_text or "")}

    scope_key = {
        "jurisdiction": claim.jurisdiction,
        "domain": claim.domain,
        "qualifiers": claim.qualifiers,
    }
    validity_bucket: dict[str, str | None] | None
    if claim.valid_from is None and claim.valid_to is None:
        validity_bucket = None
    else:
        validity_bucket = {
            "valid_from": _iso_utc(claim.valid_from),
            "valid_to": _iso_utc(claim.valid_to),
        }

    return {
        "predicate_id": claim.predicate_id,
        "subject_key": subject_key,
        "scope_key": scope_key,
        "validity_bucket": validity_bucket,
    }


def conflict_key_v1(claim: Claim) -> str:
    """Conflict key v 1 helper."""
    canonical = to_canonical_bytes(conflict_key_payload_v1(claim))
    return content_hash(canonical)


def value_signature_v1(claim: Claim) -> str:
    """Value signature v 1 helper."""
    if claim.value_decimal is not None:
        unit = claim.unit_id or "none"
        return f"num:{str(claim.value_decimal)}:{unit}"
    return f"text:{normalize_text_v1(claim.value_text)}"


def _interval_disjoint(
    a_from: datetime | None,
    a_to: datetime | None,
    b_from: datetime | None,
    b_to: datetime | None,
) -> bool:
    left_from = a_from or datetime.min.replace(tzinfo=timezone.utc)
    left_to = a_to or datetime.max.replace(tzinfo=timezone.utc)
    right_from = b_from or datetime.min.replace(tzinfo=timezone.utc)
    right_to = b_to or datetime.max.replace(tzinfo=timezone.utc)

    if left_from.tzinfo is None:
        left_from = left_from.replace(tzinfo=timezone.utc)
    if left_to.tzinfo is None:
        left_to = left_to.replace(tzinfo=timezone.utc)
    if right_from.tzinfo is None:
        right_from = right_from.replace(tzinfo=timezone.utc)
    if right_to.tzinfo is None:
        right_to = right_to.replace(tzinfo=timezone.utc)
    return left_to < right_from or right_to < left_from


def compare_v1(a: Claim, b: Claim, *, tolerance: Decimal) -> ConflictKind:
    """Compare v 1 helper."""
    tol = tolerance if tolerance >= Decimal("0") else Decimal("0")

    if _interval_disjoint(a.valid_from, a.valid_to, b.valid_from, b.valid_to):
        return ConflictKind.TEMPORAL_MISMATCH

    if a.value_decimal is not None and b.value_decimal is not None:
        if a.unit_id and b.unit_id and a.unit_id != b.unit_id:
            return ConflictKind.UNIT_MISMATCH
        if a.unit_id != b.unit_id and (a.unit_id is not None or b.unit_id is not None):
            return ConflictKind.UNIT_MISMATCH
        delta = abs(a.value_decimal - b.value_decimal)
        if delta <= tol:
            return ConflictKind.DUPLICATE
        return ConflictKind.VALUE_MISMATCH

    if normalize_text_v1(a.value_text) == normalize_text_v1(b.value_text):
        return ConflictKind.DUPLICATE
    return ConflictKind.DEFINITION_MISMATCH


__all__ = [
    "compare_v1",
    "conflict_key_payload_v1",
    "conflict_key_v1",
    "normalize_text_v1",
    "value_signature_v1",
]
