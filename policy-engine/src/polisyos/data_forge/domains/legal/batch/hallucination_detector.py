"""Post-grounding semantic consistency checks for extracted facts."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from polisyos.data_forge.domains.legal.batch.quality_filters import is_synthetic_subject

if TYPE_CHECKING:
    from polisyos.data_forge.domains.legal.contracts import SPOCandidate

_ARTICLE_REF_RE = re.compile(r"(?:статт[іяею]|article)\s+([0-9]+(?:[-.][0-9]+)*)", re.IGNORECASE)
_ARTICLE_EXISTS_RE = re.compile(r"статт[іяею]\s+([0-9]+(?:[-.][0-9]+)*)", re.IGNORECASE)
_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")
_OBLIGATION_RE = re.compile(r"(повинен|повинна|повинні|зобов|необхідно)", re.IGNORECASE)
_PROHIBITION_RE = re.compile(
    r"(забороняється|заборонено|не\s+має\s+права|не\s+допускається)", re.IGNORECASE
)


def detect_hallucination_flags(
    *,
    statement: SPOCandidate,
    provision_text: str,
) -> list[dict[str, str]]:
    """Flag likely grounding errors in one extracted SPO statement."""

    flags: list[dict[str, str]] = []
    cited_articles = _ARTICLE_REF_RE.findall(statement.fact_text_uk or statement.fact_text or "")
    existing_articles = set(_ARTICLE_EXISTS_RE.findall(provision_text))
    for article_ref in cited_articles:
        if existing_articles and article_ref not in existing_articles:
            flags.append(
                {
                    "type": "phantom_article_reference",
                    "severity": "high",
                    "detail": f"Article {article_ref} not found in provision text",
                }
            )

    if statement.subject_uk and statement.source_quote_uk:
        subject = statement.subject_uk.lower()
        if (
            not is_synthetic_subject(statement.subject_uk)
            and subject not in statement.source_quote_uk.lower()
            and subject not in provision_text.lower()
        ):
            flags.append(
                {
                    "type": "ungrounded_subject",
                    "severity": "medium",
                    "detail": f"Subject '{statement.subject_uk}' not grounded in provision text",
                }
            )

    fact_numbers = set(_NUMBER_RE.findall(statement.fact_text_uk or statement.fact_text or ""))
    provision_numbers = set(_NUMBER_RE.findall(provision_text))
    # Normalize comma/dot decimal separators for comparison (UA uses comma, EN uses dot)
    provision_numbers_norm = (
        {n.replace(",", ".") for n in provision_numbers}
        | {n.replace(".", ",") for n in provision_numbers}
        | provision_numbers
    )
    for number in sorted(fact_numbers - provision_numbers_norm):
        flags.append(
            {
                "type": "phantom_number",
                "severity": "high",
                "detail": f"Number {number} not found in provision text",
            }
        )

    norm_type = (statement.norm_type_canon or statement.norm_type or "").strip().lower()
    fact_text = statement.fact_text_uk or statement.fact_text or ""
    if (
        norm_type == "obligation"
        and _OBLIGATION_RE.search(fact_text)
        and not _OBLIGATION_RE.search(provision_text)
        and not is_synthetic_subject(statement.subject_uk)
    ):
        flags.append(
            {
                "type": "norm_type_mismatch",
                "severity": "medium",
                "detail": "Fact classified as obligation but provision lacks obligation markers",
            }
        )
    if (
        norm_type == "prohibition"
        and _PROHIBITION_RE.search(fact_text)
        and not _PROHIBITION_RE.search(provision_text)
        and not is_synthetic_subject(statement.subject_uk)
    ):
        flags.append(
            {
                "type": "norm_type_mismatch",
                "severity": "medium",
                "detail": "Fact classified as prohibition but provision lacks prohibition markers",
            }
        )
    return flags


def encode_hallucination_flags(flags: list[dict[str, str]]) -> str:
    """Serialize hallucination flags for storage in Lex fact tables."""

    return json.dumps(flags, ensure_ascii=False, sort_keys=True)


def has_blocking_hallucination(flags: list[dict[str, Any]] | str | None) -> bool:
    """Return whether the provided flags contain a hard blocking issue."""

    decoded: list[dict[str, Any]]
    if flags is None:
        return False
    if isinstance(flags, str):
        if not flags.strip():
            return False
        try:
            decoded = json.loads(flags)
        except json.JSONDecodeError:
            return False
    else:
        decoded = list(flags)
    blocking = {"phantom_article_reference", "phantom_number"}
    return any(str(flag.get("type") or "") in blocking for flag in decoded)
