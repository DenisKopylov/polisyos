"""Expose the frozen paper packet as the case-inspection projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.runtime.http.services.case_inspection_contracts import (
        CaseInspectionReplayQuery,
        CaseInspectionResponse,
    )
    from polisyos.runtime.http.services.run_paper_projection import RunPaperProjectionService


@dataclass(frozen=True, slots=True)
class CaseInspectionService:
    """Delegate case inspection to the one verified run-paper producer.

    This service does not construct the available case arm.  Until the runtime/GY
    owner closes ``case-record-not-run-bound``, the delegated producer returns the
    frozen typed-unavailable arm.
    """

    run_paper: RunPaperProjectionService

    def get(
        self,
        run_id: str,
        *,
        replay_query: CaseInspectionReplayQuery | None = None,
    ) -> CaseInspectionResponse:
        """Return the exact verified packet selected by the replay tuple."""

        return self.run_paper.get(run_id, replay_query=replay_query)


__all__ = ["CaseInspectionService"]
