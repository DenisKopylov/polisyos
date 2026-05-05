"""EU jurisdiction plugin foundation."""

from __future__ import annotations

import re

from polisyos.data_forge.domains.legal.batch.jurisdictions.protocol import (
    JurisdictionPlugin,
    NormativeSignalPatterns,
    StructurePatterns,
)


class EUJurisdiction(JurisdictionPlugin):
    """EU jurisdiction public type."""

    @property
    def jurisdiction_code(self) -> str:
        return "EU"

    @property
    def language_codes(self) -> list[str]:
        return ["en", "fr", "de"]

    def structure_patterns(self) -> StructurePatterns:
        return StructurePatterns(
            article_re=re.compile(r"^[\s]*Article\s+(\d+[\-\d]*)[\.\s]?", re.IGNORECASE),
            part_re=re.compile(r"^\s*\((\d+)\)\s+"),
            point_res=(
                re.compile(r"^\s*\(([a-z])\)\s+", re.IGNORECASE),
                re.compile(r"^\s*(\d+)\.\s+"),
            ),
            subpoint_re=re.compile(r"^\s*\(([ivxlcdm]+)\)\s+", re.IGNORECASE),
            paragraph_re=None,
            section_heading_re=re.compile(
                r"^[\s]*(?:Chapter|Section|Title)\s+([IVXLCDM]+|\d+)", re.IGNORECASE
            ),
        )

    def normative_signal_patterns(self) -> NormativeSignalPatterns:
        return NormativeSignalPatterns(
            obligation_re=re.compile(r"\bshall\b|\bmust\b|\bis required to\b", re.IGNORECASE),
            prohibition_re=re.compile(
                r"\bshall not\b|\bmust not\b|\bprohibited\b|\bforbidden\b", re.IGNORECASE
            ),
            permission_re=re.compile(
                r"\bmay\b|\bis entitled to\b|\bhas the right to\b", re.IGNORECASE
            ),
            approval_re=re.compile(r"\badopt\b|\bapprove\b|\bestablish\b", re.IGNORECASE),
            amendment_re=re.compile(
                r"\bamend(?:ed|ment)?\b|\breplace(?:d|ment)?\b|\bdelete\b", re.IGNORECASE
            ),
            temporal_re=re.compile(
                r"\benter(?:s)? into force\b|\bwithin \d+ (?:days|months|years)\b", re.IGNORECASE
            ),
            reference_re=re.compile(
                r"\bArticle\s+\d+(?:\(\d+\))?\b|\bRegulation\b|\bDirective\b|\bDecision\b",
                re.IGNORECASE,
            ),
            threshold_re=re.compile(
                r"\b\d+(?:[.,]\d+)?\s*%\b|\bat least\b|\bnot more than\b", re.IGNORECASE
            ),
        )

    def reference_patterns(self) -> tuple[tuple[str, re.Pattern[str], float], ...]:
        return (
            (
                "self_reference",
                re.compile(
                    r"(?P<anchor>Article\s+\d+(?:\(\d+\))?)\s+of\s+this\s+"
                    r"(?P<title>Regulation|Directive|Decision)",
                    re.IGNORECASE,
                ),
                0.98,
            ),
            (
                "article_reference",
                re.compile(
                    r"(?:under|pursuant to|in accordance with)\s+"
                    r"(?P<anchor>Article\s+\d+(?:\(\d+\))?)\s+of\s+"
                    r"(?P<title>(?:this\s+(?:Regulation|Directive|Decision))|(?:Regulation|Directive|Decision)[^,;\.\n]{0,140})",
                    re.IGNORECASE,
                ),
                0.92,
            ),
            (
                "eu_numbered_act",
                re.compile(
                    r"(?P<title>(?:Regulation|Directive|Decision)(?:\s+\(EU\))?[^,;\.\n]{0,120}?)\s+"
                    r"(?:No\.\s*)?(?P<number>[\d/]+)",
                    re.IGNORECASE,
                ),
                0.95,
            ),
        )

    def document_type_hierarchy(self) -> dict[str, int]:
        return {
            "Treaty": 1,
            "Regulation": 2,
            "Directive": 3,
            "Decision": 4,
            "Recommendation": 5,
            "Opinion": 6,
        }
