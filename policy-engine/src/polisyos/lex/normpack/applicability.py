"""Public normpack applicability module API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from polisyos.core.canon import content_hash
from polisyos.ir.analytics.applicability import IdSelector, NormApplicability, TimeWindow
from polisyos.ir.canon import to_canonical_bytes

if TYPE_CHECKING:
    from polisyos.ir.world.claim import Claim


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def build_norm_applicability(*, claim: Claim, jurisdiction_norm: str) -> NormApplicability:
    """Build norm applicability."""
    valid_from = _iso_utc(claim.valid_from)
    valid_to = _iso_utc(claim.valid_to)
    return NormApplicability(
        jurisdiction=IdSelector(any_of=[jurisdiction_norm]),
        time=TimeWindow(valid_from=valid_from, valid_to=valid_to),
    )


def applicability_key(applicability: NormApplicability) -> str:
    """Applicability key helper."""
    payload = applicability.model_dump(mode="python")
    digest = content_hash(to_canonical_bytes(payload))
    return digest[:32]


def applies_to_context(
    *,
    applicability: NormApplicability,
    jurisdiction_norm: str,
    as_of_iso: str,
) -> bool:
    """Applies to context helper."""
    jurisdiction_any = applicability.jurisdiction.any_of
    if jurisdiction_any and jurisdiction_norm not in jurisdiction_any:
        return False

    as_of = datetime.fromisoformat(f"{as_of_iso}T00:00:00+00:00")
    valid_from = applicability.time.valid_from
    valid_to = applicability.time.valid_to
    if valid_from is not None and as_of < datetime.fromisoformat(valid_from.replace("Z", "+00:00")):
        return False
    return not (
        valid_to is not None and as_of > datetime.fromisoformat(valid_to.replace("Z", "+00:00"))
    )


__all__ = [
    "applicability_key",
    "applies_to_context",
    "build_norm_applicability",
]
