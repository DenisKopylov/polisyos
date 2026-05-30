"""Compatibility metadata for the Scientist feedback/evidence/replay lane."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass(frozen=True)
class ScientistEvidenceShim:
    """Governed temporary import bridge for Phase 4.4 module consolidation."""

    id: str
    legacy_module: str
    canonical_module: str
    owner: str
    reason: str
    sunset_date: date
    migration_hint: str
    status: Literal["active", "sunsetting"] = "active"


PHASE44_SHIM_SUNSET_DATE = date(2026, 11, 30)

SCIENTIST_EVIDENCE_SHIMS: tuple[ScientistEvidenceShim, ...] = ()


def shim_metadata_for(legacy_module: str) -> ScientistEvidenceShim:
    """Return the governed shim record for a legacy module."""

    for shim in SCIENTIST_EVIDENCE_SHIMS:
        if shim.legacy_module == legacy_module:
            return shim
    raise KeyError(legacy_module)


def validate_scientist_evidence_shims(
    shims: tuple[ScientistEvidenceShim, ...] = SCIENTIST_EVIDENCE_SHIMS,
    *,
    today: date = date(2026, 5, 5),
) -> list[str]:
    """Return local shim-governance errors without importing legacy modules."""

    errors: list[str] = []
    seen: set[str] = set()
    for shim in shims:
        if shim.id in seen:
            errors.append(f"{shim.id}: duplicate shim id")
        seen.add(shim.id)
        if not shim.owner.startswith("team-"):
            errors.append(f"{shim.id}: owner must be a team handle")
        if shim.legacy_module == shim.canonical_module:
            errors.append(f"{shim.id}: legacy and canonical modules must differ")
        if shim.sunset_date <= today:
            errors.append(f"{shim.id}: sunset date must be in the future")
        if not shim.migration_hint.strip():
            errors.append(f"{shim.id}: migration hint is required")
    return errors


__all__ = [
    "PHASE44_SHIM_SUNSET_DATE",
    "SCIENTIST_EVIDENCE_SHIMS",
    "ScientistEvidenceShim",
    "shim_metadata_for",
    "validate_scientist_evidence_shims",
]
