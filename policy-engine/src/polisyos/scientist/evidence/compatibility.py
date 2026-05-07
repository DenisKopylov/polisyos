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

SCIENTIST_EVIDENCE_SHIMS: tuple[ScientistEvidenceShim, ...] = (
    ScientistEvidenceShim(
        id="scientist.feedback_utils-to-feedback.utils",
        legacy_module="polisyos.scientist.feedback_utils",
        canonical_module="polisyos.scientist.feedback.utils",
        owner="team-scientist",
        reason="Feedback helpers now live inside the Feedback hub.",
        sunset_date=PHASE44_SHIM_SUNSET_DATE,
        migration_hint="Use polisyos.scientist.feedback.utils for new imports.",
    ),
    ScientistEvidenceShim(
        id="scientist.replay_backend-to-replay.backend",
        legacy_module="polisyos.scientist.replay_backend",
        canonical_module="polisyos.scientist.replay.backend",
        owner="team-scientist",
        reason="Replay backend helpers now live inside the Replay hub.",
        sunset_date=PHASE44_SHIM_SUNSET_DATE,
        migration_hint="Use polisyos.scientist.replay.backend for new imports.",
    ),
    ScientistEvidenceShim(
        id="scientist.evidence_sources-to-evidence.sources",
        legacy_module="polisyos.scientist.evidence_sources",
        canonical_module="polisyos.scientist.evidence.sources",
        owner="team-scientist",
        reason="Evidence source configuration now lives inside the Evidence hub.",
        sunset_date=PHASE44_SHIM_SUNSET_DATE,
        migration_hint="Use polisyos.scientist.evidence.sources for new imports.",
    ),
    ScientistEvidenceShim(
        id="scientist.claims-to-evidence.claims",
        legacy_module="polisyos.scientist.claims",
        canonical_module="polisyos.scientist.evidence.claims",
        owner="team-scientist",
        reason="Claim ledgers are evidence artifacts and now live under the Evidence hub.",
        sunset_date=PHASE44_SHIM_SUNSET_DATE,
        migration_hint="Use polisyos.scientist.evidence.claims for new imports.",
    ),
    ScientistEvidenceShim(
        id="scientist.provenance-to-evidence.provenance",
        legacy_module="polisyos.scientist.provenance",
        canonical_module="polisyos.scientist.evidence.provenance",
        owner="team-scientist",
        reason="Run provenance helpers are evidence artifacts and now live under the Evidence hub.",
        sunset_date=PHASE44_SHIM_SUNSET_DATE,
        migration_hint="Use polisyos.scientist.evidence.provenance for new imports.",
    ),
)


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
