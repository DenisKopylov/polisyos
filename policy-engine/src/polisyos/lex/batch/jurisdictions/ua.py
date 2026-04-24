"""UA jurisdiction plugin."""

from __future__ import annotations

import re

from polisyos.lex.batch.jurisdictions.protocol import (
    JurisdictionPlugin,
    NormativeSignalPatterns,
    StructurePatterns,
)
from polisyos.lex.batch.patterns import (
    AMENDMENT_CORE_RE,
    APPROVAL_CORE_RE,
    DOC_TYPE_HIERARCHY_UA,
    OBLIGATION_CORE_RE,
    PERMISSION_CORE_RE,
    PROHIBITION_CORE_RE,
    REFERENCE_CORE_RE,
    REFERENCE_PATTERNS_UA,
    TEMPORAL_CORE_RE,
    THRESHOLD_CORE_RE,
)


class UkrainianJurisdiction(JurisdictionPlugin):
    """Ukrainian jurisdiction public type."""

    @property
    def jurisdiction_code(self) -> str:
        return "UA"

    @property
    def language_codes(self) -> list[str]:
        return ["uk"]

    def structure_patterns(self) -> StructurePatterns:
        return StructurePatterns(
            article_re=re.compile(r"^[\s]*Стаття\s+(\d+[\-\d]*)[\.\s]"),
            part_re=re.compile(r"^\s*(\d+)\.\s+"),
            point_res=(
                re.compile(r"^\s*(\d+)\)\s+\S"),
                re.compile(r"^\s*(\d+)\.\s+\S"),
            ),
            subpoint_re=re.compile(r"^\s*([а-яА-Яa-zA-Z])\)\s+\S"),
            paragraph_re=None,
            section_heading_re=re.compile(r"^[\s]*Розділ\s+([IVXLCDM]+|[0-9]+)"),
        )

    def normative_signal_patterns(self) -> NormativeSignalPatterns:
        return NormativeSignalPatterns(
            obligation_re=OBLIGATION_CORE_RE,
            prohibition_re=PROHIBITION_CORE_RE,
            permission_re=PERMISSION_CORE_RE,
            approval_re=APPROVAL_CORE_RE,
            amendment_re=AMENDMENT_CORE_RE,
            temporal_re=TEMPORAL_CORE_RE,
            reference_re=REFERENCE_CORE_RE,
            threshold_re=THRESHOLD_CORE_RE,
        )

    def reference_patterns(self) -> tuple[tuple[str, re.Pattern[str], float], ...]:
        return REFERENCE_PATTERNS_UA

    def document_type_hierarchy(self) -> dict[str, int]:
        return dict(DOC_TYPE_HIERARCHY_UA)
