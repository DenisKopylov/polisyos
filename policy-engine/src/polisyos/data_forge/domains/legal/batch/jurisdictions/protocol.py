"""Protocol for jurisdiction-specific lex processing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import re


@dataclass(frozen=True)
class StructurePatterns:
    """Structure patterns public type."""

    article_re: re.Pattern[str]
    part_re: re.Pattern[str] | None
    point_res: tuple[re.Pattern[str], ...]
    subpoint_re: re.Pattern[str] | None
    paragraph_re: re.Pattern[str] | None
    section_heading_re: re.Pattern[str] | None


@dataclass(frozen=True)
class NormativeSignalPatterns:
    """Normative signal patterns public type."""

    obligation_re: re.Pattern[str]
    prohibition_re: re.Pattern[str]
    permission_re: re.Pattern[str]
    approval_re: re.Pattern[str]
    amendment_re: re.Pattern[str]
    temporal_re: re.Pattern[str]
    reference_re: re.Pattern[str]
    threshold_re: re.Pattern[str]


class JurisdictionPlugin(Protocol):
    """Jurisdiction plugin public type."""

    @property
    def jurisdiction_code(self) -> str: ...

    @property
    def language_codes(self) -> list[str]: ...

    def structure_patterns(self) -> StructurePatterns: ...

    def normative_signal_patterns(self) -> NormativeSignalPatterns: ...

    def reference_patterns(self) -> tuple[tuple[str, re.Pattern[str], float], ...]: ...

    def document_type_hierarchy(self) -> dict[str, int]: ...
