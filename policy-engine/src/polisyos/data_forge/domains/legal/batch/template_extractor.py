"""Template-based SPO extraction for well-structured document types.

Many Ukrainian НПА follow rigid structural conventions (e.g., КМУ постанови,
presidential decrees, ministerial orders).  For these documents the first few
provisions are almost always: "Затвердити ...", "Міністерству ... забезпечити",
"Контроль ... покласти на", "Набирає чинності ...".

This module detects those templates and produces ``SPOExtractionResult`` objects
**entirely without LLM**, giving them ``extraction_source="template_auto"`` so
the gate/pipeline can track provenance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from polisyos.data_forge.domains.legal.batch.canonicalizers import (
    canonicalize_action,
    canonicalize_norm_type,
    extract_thresholds_from_text,
)
from polisyos.data_forge.domains.legal.contracts import SPOCandidate, SPOExtractionResult


@dataclass(frozen=True)
class TemplateMatch:
    """Result of template matching for an entire document."""

    matched: bool
    template_name: str
    results: list[SPOExtractionResult]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_KMU_PUBLISHERS = frozenset(
    {
        "кабінет міністрів україни",
        "кабінет міністрів",
        "кму",
    }
)

_PRESIDENT_PUBLISHERS = frozenset(
    {
        "президент україни",
    }
)


def _clip(text: str, size: int = 200) -> str:
    text = " ".join(text.split())
    return text[:size] if len(text) <= size else text[: size - 1] + "…"


def _build_candidate(
    *,
    subject_uk: str,
    predicate: str,
    object_uk: str,
    norm_type: str,
    fact_text: str,
    quote: str,
    confidence: float,
) -> SPOCandidate:
    action_canon, _ = canonicalize_action(predicate)
    norm_canon, _ = canonicalize_norm_type(norm_type)
    thresholds = extract_thresholds_from_text(quote, applies_to=object_uk)
    return SPOCandidate.model_validate(
        {
            "subject_en": subject_uk,
            "subject_uk": subject_uk,
            "predicate": predicate,
            "object_en": object_uk,
            "object_uk": object_uk,
            "fact_text": fact_text,
            "confidence": max(0.0, min(1.0, confidence)),
            "norm_type": norm_type,
            "action_raw": predicate,
            "action_canon": action_canon,
            "norm_type_raw": norm_type,
            "norm_type_canon": norm_canon,
            "source_quote_uk": quote[:500],
            "thresholds": [th.model_dump(mode="json") for th in thresholds],
        }
    )


def _make_result(
    doc_id: str,
    anchor: str,
    citation: str,
    candidates: list[SPOCandidate],
    template_name: str,
) -> SPOExtractionResult:
    return SPOExtractionResult(
        doc_id=doc_id,
        provision_anchor=anchor,
        provision_citation=citation,
        statements=candidates,
        prompt_version=f"template_{template_name}_v1",
        extract_passes=0,
        extraction_source="template_auto",
        gate_score=0.0,
        gate_reason_codes=[f"template_{template_name}"],
    )


# ---------------------------------------------------------------------------
# Pattern matchers for provision text
# ---------------------------------------------------------------------------

_RE_APPROVE = re.compile(
    r"(?:затвердити|схвалити|ухвалити|прийняти)\s+(.{10,300})",
    re.IGNORECASE,
)
_RE_DELEGATE = re.compile(
    r"(?:доручити|покласти\s+на|уповноважити)\s+(.{5,250}?)\s+(?:забезпечити|контроль|виконання|здійснення|підготовку|розроб|вжити)",
    re.IGNORECASE,
)
_RE_CONTROL = re.compile(
    r"контроль\s+(?:за\s+виконанням\s+(?:цієї\s+)?(?:постанови|розпорядження|указу)?\s*)?покласти\s+на\s+(.{5,200})",
    re.IGNORECASE,
)
_RE_REPEAL = re.compile(
    r"визнати\s+(?:таки(?:м|ми)\s*,?\s*що\s*втратил(?:и|а|о)\s+чинність|такими\s*що\s*втратили\s+чинність)\s*(.{0,300})",
    re.IGNORECASE,
)
_RE_ENTRY = re.compile(
    r"(?:набирає|набуває)\s+чинності?\s*(.{0,200})",
    re.IGNORECASE,
)
_RE_REGISTER = re.compile(
    r"(?:зареєструвати|опублікувати|оприлюднити)\s+(?:в|у|на)\s+(.{5,200})",
    re.IGNORECASE,
)


def _try_approve(
    text: str, doc_id: str, anchor: str, citation: str, publisher: str
) -> SPOExtractionResult | None:
    m = _RE_APPROVE.search(text)
    if not m or len(text) > 600:
        return None
    obj = m.group(1).strip().rstrip(".")
    return _make_result(
        doc_id,
        anchor,
        citation,
        [
            _build_candidate(
                subject_uk=publisher,
                predicate="approves",
                object_uk=obj,
                norm_type="procedure",
                fact_text=f"Затверджено: {_clip(obj)}",
                quote=_clip(text, 400),
                confidence=0.92,
            ),
        ],
        "kmu_approve",
    )


def _try_delegate(
    text: str, doc_id: str, anchor: str, citation: str, publisher: str
) -> SPOExtractionResult | None:
    m = _RE_DELEGATE.search(text)
    if not m or len(text) > 600:
        return None
    obj = m.group(1).strip().rstrip(".")
    return _make_result(
        doc_id,
        anchor,
        citation,
        [
            _build_candidate(
                subject_uk=publisher,
                predicate="delegates",
                object_uk=obj,
                norm_type="delegation",
                fact_text=f"Доручено: {_clip(obj)}",
                quote=_clip(text, 400),
                confidence=0.88,
            ),
        ],
        "kmu_delegate",
    )


def _try_control(
    text: str, doc_id: str, anchor: str, citation: str, publisher: str
) -> SPOExtractionResult | None:
    m = _RE_CONTROL.search(text)
    if not m or len(text) > 500:
        return None
    obj = m.group(1).strip().rstrip(".")
    return _make_result(
        doc_id,
        anchor,
        citation,
        [
            _build_candidate(
                subject_uk=publisher,
                predicate="delegates",
                object_uk=obj,
                norm_type="delegation",
                fact_text=f"Контроль покладено на: {_clip(obj)}",
                quote=_clip(text, 400),
                confidence=0.90,
            ),
        ],
        "kmu_control",
    )


def _try_repeal(
    text: str, doc_id: str, anchor: str, citation: str, publisher: str
) -> SPOExtractionResult | None:
    m = _RE_REPEAL.search(text)
    if not m or len(text) > 600:
        return None
    obj = (m.group(1) or "").strip().rstrip(".") or "визначені акти"
    return _make_result(
        doc_id,
        anchor,
        citation,
        [
            _build_candidate(
                subject_uk=publisher,
                predicate="repeals",
                object_uk=obj,
                norm_type="repeal",
                fact_text=f"Визнано такими, що втратили чинність: {_clip(obj)}",
                quote=_clip(text, 400),
                confidence=0.92,
            ),
        ],
        "kmu_repeal",
    )


def _try_entry(text: str, doc_id: str, anchor: str, citation: str) -> SPOExtractionResult | None:
    m = _RE_ENTRY.search(text)
    if not m or len(text) > 400:
        return None
    detail = (m.group(1) or "").strip().rstrip(".")
    return _make_result(
        doc_id,
        anchor,
        citation,
        [
            _build_candidate(
                subject_uk="цей акт",
                predicate="enters_into_force",
                object_uk=detail or "з дня офіційного опублікування",
                norm_type="entry_into_force",
                fact_text=f"Акт набирає чинності {detail}".strip(),
                quote=_clip(text, 400),
                confidence=0.93,
            ),
        ],
        "kmu_entry",
    )


def _try_register(
    text: str, doc_id: str, anchor: str, citation: str, publisher: str
) -> SPOExtractionResult | None:
    m = _RE_REGISTER.search(text)
    if not m or len(text) > 400:
        return None
    obj = m.group(1).strip().rstrip(".")
    return _make_result(
        doc_id,
        anchor,
        citation,
        [
            _build_candidate(
                subject_uk=publisher,
                predicate="requires",
                object_uk=obj,
                norm_type="procedure",
                fact_text=f"Зареєструвати/опублікувати в: {_clip(obj)}",
                quote=_clip(text, 400),
                confidence=0.90,
            ),
        ],
        "kmu_register",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def try_template_extraction(
    *,
    doc_id: str,
    doc_type: str,
    publisher: tuple[str, ...] | list[str],
    doc_title: str,
    provisions: list[dict],
) -> TemplateMatch:
    """Attempt template-based extraction for a document.

    Returns a ``TemplateMatch`` with ``matched=True`` if ALL provisions could
    be handled by templates.  If any provision cannot be matched, returns
    ``matched=False`` with an empty results list so the caller falls through
    to the normal pipeline.

    Parameters
    ----------
    provisions : list of dicts with keys ``text``, ``anchor_path``, ``citation_label``
    """
    publisher_lower = " ".join(p.lower() for p in publisher).strip()
    doc_type_lower = (doc_type or "").lower().strip()

    # Only handle known publisher+type combinations
    is_kmu = any(kw in publisher_lower for kw in _KMU_PUBLISHERS)
    is_president = any(kw in publisher_lower for kw in _PRESIDENT_PUBLISHERS)
    is_structured_type = doc_type_lower in (
        "постанова",
        "розпорядження",
        "указ",
        "наказ",
        "рішення",
    )

    if not (is_kmu or is_president) or not is_structured_type:
        return TemplateMatch(matched=False, template_name="none", results=[])

    template_name = "kmu_postanova" if is_kmu else "president_decree"
    publisher_label = "Кабінет Міністрів України" if is_kmu else "Президент України"
    results: list[SPOExtractionResult] = []

    for prov in provisions:
        text = str(prov.get("text", "")).strip()
        anchor = str(prov.get("anchor_path", ""))
        citation = str(prov.get("citation_label", ""))

        if len(text) < 40:
            continue

        # Try each template pattern in order of priority
        result = (
            _try_approve(text, doc_id, anchor, citation, publisher_label)
            or _try_delegate(text, doc_id, anchor, citation, publisher_label)
            or _try_control(text, doc_id, anchor, citation, publisher_label)
            or _try_repeal(text, doc_id, anchor, citation, publisher_label)
            or _try_entry(text, doc_id, anchor, citation)
            or _try_register(text, doc_id, anchor, citation, publisher_label)
        )

        if result is not None:
            results.append(result)
        else:
            # Cannot handle all provisions → bail out
            return TemplateMatch(matched=False, template_name=template_name, results=[])

    return TemplateMatch(matched=bool(results), template_name=template_name, results=results)
