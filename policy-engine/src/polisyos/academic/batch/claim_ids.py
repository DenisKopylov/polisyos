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
) -> str:
    payload = "|".join(
        [
            str(work_id).strip().lower(),
            str(cause).strip().lower(),
            str(effect).strip().lower(),
            str(direction).strip().lower(),
            str(claim_text).strip().lower(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


__all__ = ["stable_claim_id"]
