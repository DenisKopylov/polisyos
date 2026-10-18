"""Typed result and inspection-error contracts for the trust-posture checker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.scientist.evidence.claims.posture import (
        ClaimPostureState,
        CustodyAppointmentStatus,
        EstablishmentClass,
    )


class _PosturePredicateError(ValueError):
    """A declared trust-posture predicate was measured and failed."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        stage: str,
        finding_coverage: str,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.finding_coverage = finding_coverage


class _PostureInspectionError(ValueError):
    """A required inspection stage did not complete, so no property verdict exists."""

    def __init__(self, message: str, *, stage: str) -> None:
        super().__init__(message)
        self.stage = stage


@dataclass(frozen=True)
class AccessibilityEvaluation:
    """Bounded accessibility-purpose evaluation."""

    state: ClaimPostureState
    issue_codes: tuple[str, ...]


@dataclass(frozen=True)
class ScopeEvaluation:
    """Fail-closed result for a declared scope assumption."""

    state: ClaimPostureState
    establishment_class: EstablishmentClass
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class CustodyAppointment:
    """One accepted owner/closure appointment derived from the debt register."""

    debt_id: str
    owner: str
    status: CustodyAppointmentStatus
    closure_signal: str
    source_ref: str
    line: int
    source_content: str
