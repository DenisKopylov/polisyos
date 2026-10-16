"""Shared fail-closed admission for Lex claim-to-source relations.

An exact quotation can bind source text to a provision, but the current Legal
pipeline has no independent verifier that establishes that the complete SPO
claim follows from those bytes. Until such a verifier and receipt are admitted,
the only supported disposition is candidate-only, and authority projections
must carry the typed refusal below.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, NoReturn

from polisyos.data_forge.errors import LexNotReadyError

LegalSourceRelationStatus = Literal["verification_missing"]
LegalSourceRelationRefusalCode = Literal["legal_source_relation_verification_not_established"]
LegalCandidateTrustTier = Literal["search_candidate"]

LEGAL_SOURCE_RELATION_REFUSAL_CODE: LegalSourceRelationRefusalCode = (
    "legal_source_relation_verification_not_established"
)


@dataclass(frozen=True, slots=True)
class LegalSourceRelationRefusal:
    """Typed reason that a Lex SPO claim cannot currently be projected as authority."""

    code: LegalSourceRelationRefusalCode = LEGAL_SOURCE_RELATION_REFUSAL_CODE
    status: LegalSourceRelationStatus = "verification_missing"

    def to_payload(self) -> dict[str, str]:
        """Return the stable, minimal public projection of this refusal."""
        return {"code": self.code, "status": self.status}


@dataclass(frozen=True, slots=True)
class LegalSourceRelationDisposition:
    """Current writer disposition while claim-to-source verification is absent."""

    trust_tier: LegalCandidateTrustTier = "search_candidate"
    refusal: LegalSourceRelationRefusal = LegalSourceRelationRefusal()


LEGAL_SOURCE_RELATION_REFUSAL = LegalSourceRelationRefusal()
CURRENT_LEGAL_SOURCE_RELATION_DISPOSITION = LegalSourceRelationDisposition()


class LegalSourceRelationVerificationMissingError(LexNotReadyError):
    """Typed refusal raised when a consumer requests unverified legal authority."""

    def __init__(self) -> None:
        self.refusal = LEGAL_SOURCE_RELATION_REFUSAL
        super().__init__(
            "Legal claim-to-source relation verification is not established.",
            details=self.refusal.to_payload(),
        )


def current_legal_source_relation_disposition() -> LegalSourceRelationDisposition:
    """Return the current fail-closed SPO disposition without inventing proof."""
    return CURRENT_LEGAL_SOURCE_RELATION_DISPOSITION


def require_legal_source_relation_verification() -> NoReturn:
    """Refuse an authority projection until an independent relation receipt exists."""
    raise LegalSourceRelationVerificationMissingError()


__all__ = [
    "CURRENT_LEGAL_SOURCE_RELATION_DISPOSITION",
    "LEGAL_SOURCE_RELATION_REFUSAL",
    "LEGAL_SOURCE_RELATION_REFUSAL_CODE",
    "LegalCandidateTrustTier",
    "LegalSourceRelationDisposition",
    "LegalSourceRelationRefusal",
    "LegalSourceRelationRefusalCode",
    "LegalSourceRelationStatus",
    "LegalSourceRelationVerificationMissingError",
    "current_legal_source_relation_disposition",
    "require_legal_source_relation_verification",
]
