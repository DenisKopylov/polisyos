"""Case-inspection names for the frozen run-paper ABI.

The case workspace deliberately does not define a second DTO.  Its response is
the already-frozen run-paper packet, including the discriminated available and
typed-unavailable case arms.
"""

from polisyos.runtime.http.services.run_paper_contracts import (
    RunPaperPacket,
    RunPaperReplayQuery,
)

CaseInspectionResponse = RunPaperPacket
CaseInspectionReplayQuery = RunPaperReplayQuery

__all__ = ["CaseInspectionReplayQuery", "CaseInspectionResponse"]
