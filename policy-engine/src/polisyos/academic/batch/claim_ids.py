"""Stable claim id helpers shared across extraction, adjudication, and graph load."""

from __future__ import annotations

import hashlib


def stable_claim_id(
    *,
    work_id: str,
    cause: str,
    effect: str,
    claim_text: str = "",
    direction: str = "",
    supporting_span_ids: tuple[str, ...] | list[str] | None = None,
) -> str:
    """Stable claim ID helper."""
    span_signature = tuple(sorted({str(item).strip().lower() for item in (supporting_span_ids or []) if str(item).strip()}))
    legacy_text_alias = str(claim_text).strip().lower()[:64] if not span_signature else ""
    payload = "|".join(
        [
            str(work_id).strip().lower(),
            str(cause).strip().lower(),
            str(effect).strip().lower(),
            str(direction).strip().lower(),
            ",".join(span_signature),
            legacy_text_alias,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


__all__ = ["stable_claim_id"]
