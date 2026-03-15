"""Stage 1: Stream-parse ЄДРНПА XML dumps (cards + texts) into NPADocument objects.

Design for memory:
- Cards XML (161 MB) — parsed fully into a dict (fits in ~500 MB RAM as Python objects).
- Texts XML (3 GB)  — streamed via iterparse, one <document> at a time, joined with
  the in-memory cards index by reestr_code/reestr_kod.
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from polisyos.common.logger import get_logger

logger = get_logger(__name__)

_WS_RE = re.compile(r"\s+")


def _collapse_ws(text: str) -> str:
    return _WS_RE.sub(" ", text.strip())


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NPACard:
    """Metadata card for a single НПА."""

    doc_id: str
    reestr_code: str
    date_acc: str
    reestr_date: str
    status: str
    doc_type: str
    name: str
    publisher: tuple[str, ...]
    number: str
    publication: tuple[str, ...]
    keywords: tuple[str, ...]
    reg_date: str
    reg_number: str


@dataclass
class NPADocument:
    """A joined НПА: metadata card + full text."""

    card: NPACard
    text: str


# ---------------------------------------------------------------------------
# Stable doc_id generation
# ---------------------------------------------------------------------------

def _stable_doc_id(
    reestr_code: str,
    date_acc: str,
    doc_type: str,
    number: str,
    name: str,
) -> str:
    """Generate a deterministic 16-char hex doc_id from key fields."""
    canon = "|".join(
        _collapse_ws(v) for v in (reestr_code, date_acc, doc_type, number, name)
    )
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _item_text(document_elem: ET.Element, item_name: str) -> str:
    """Extract single-value <item name="X"><text>...</text></item>."""
    for item in document_elem.findall("item"):
        if item.get("name") == item_name:
            text_elem = item.find("text")
            if text_elem is not None and text_elem.text:
                return _collapse_ws(text_elem.text)
            # Might be inside textlist — take first
            tl = item.find("textlist")
            if tl is not None:
                first = tl.find("text")
                if first is not None and first.text:
                    return _collapse_ws(first.text)
    return ""


def _item_text_list(document_elem: ET.Element, item_name: str) -> tuple[str, ...]:
    """Extract multi-value <item name="X"><textlist><text>...</text>...</textlist></item>."""
    for item in document_elem.findall("item"):
        if item.get("name") == item_name:
            tl = item.find("textlist")
            if tl is not None:
                return tuple(
                    _collapse_ws(t.text)
                    for t in tl.findall("text")
                    if t.text and t.text.strip()
                )
            # Single text fallback
            text_elem = item.find("text")
            if text_elem is not None and text_elem.text and text_elem.text.strip():
                return (_collapse_ws(text_elem.text),)
    return ()


def _extract_text_from_richtext(document_elem: ET.Element) -> str:
    """Extract plain text from <item name="TEXT_ED"><richtext><par>...</par></richtext>."""
    for item in document_elem.findall("item"):
        if item.get("name") == "TEXT_ED":
            parts: list[str] = []
            for par in item.iter("par"):
                text = "".join(par.itertext()).strip()
                if text:
                    parts.append(text)
            return "\n".join(parts)
    return ""


# ---------------------------------------------------------------------------
# Stage 1a: Parse cards XML
# ---------------------------------------------------------------------------

def parse_cards(cards_path: Path) -> dict[str, list[NPACard]]:
    """Stream-parse cards XML into ``{reestr_code: [NPACard, ...]}``.

    Returns a dict because reestr_code is NOT unique (133K unique / 140K cards).
    Multiple cards with the same code form a "package" (decree + appendices).
    """
    index: dict[str, list[NPACard]] = {}
    count = 0

    context = ET.iterparse(str(cards_path), events=("end",))
    try:
        for _event, elem in context:
            if elem.tag != "document":
                continue

            reestr_code = _item_text(elem, "reestr_code")
            date_acc = _item_text(elem, "date_acc")
            doc_type = _item_text(elem, "type")
            number = _item_text(elem, "number")
            name = _item_text(elem, "name")

            doc_id = _stable_doc_id(reestr_code, date_acc, doc_type, number, name)

            card = NPACard(
                doc_id=doc_id,
                reestr_code=reestr_code,
                date_acc=date_acc,
                reestr_date=_item_text(elem, "reestr_date"),
                status=_item_text(elem, "status"),
                doc_type=doc_type,
                name=name,
                publisher=_item_text_list(elem, "publisher"),
                number=number,
                publication=_item_text_list(elem, "publication"),
                keywords=_item_text_list(elem, "keywords"),
                reg_date=_item_text(elem, "reg_date") or "",
                reg_number=_item_text(elem, "reg_number") or "",
            )
            index.setdefault(reestr_code, []).append(card)
            count += 1

            # Free memory for parsed elements
            elem.clear()

            if count % 20_000 == 0:
                logger.info("Parsed {} cards...", count)
    except ET.ParseError as exc:
        # ЄДРНПА XML dumps may contain trailing junk bytes (e.g. \x1a DOS EOF)
        # after the closing root tag.  If we already parsed documents, treat
        # this as a non-fatal end-of-stream.
        if count > 0:
            logger.warning("XML parse error after {} cards (ignored): {}", count, exc)
        else:
            raise

    logger.info("Parsed {} cards total, {} unique reestr_codes", count, len(index))
    return index


# ---------------------------------------------------------------------------
# Stage 1b: Stream texts + join with cards
# ---------------------------------------------------------------------------

def iter_documents(
    cards_path: Path,
    texts_path: Path,
    *,
    status_filter: frozenset[str] | None = None,
    type_filter: frozenset[str] | None = None,
    doc_id_filter: frozenset[str] | None = None,
) -> Iterator[NPADocument]:
    """Stream-parse texts XML, join with cards, yield NPADocument objects.

    Memory: only one <document> from texts in RAM at a time (+ all cards index).
    """
    logger.info("Loading cards index from {} ...", cards_path)
    cards_index = parse_cards(cards_path)
    logger.info("Cards index loaded. Streaming texts from {} ...", texts_path)

    matched = 0
    skipped_no_card = 0
    skipped_filter = 0
    skipped_empty = 0
    remaining_doc_ids = set(doc_id_filter) if doc_id_filter else None

    context = ET.iterparse(str(texts_path), events=("end",))
    try:
        for _event, elem in context:
            if elem.tag != "document":
                continue

            reestr_kod = _item_text(elem, "reestr_kod")
            text = _extract_text_from_richtext(elem)
            elem.clear()

            if not text.strip():
                skipped_empty += 1
                continue

            cards = cards_index.get(reestr_kod)
            if not cards:
                skipped_no_card += 1
                continue

            # Take the first card (primary document in the package).
            # Others in the package share the same text but are appendices/forms.
            card = cards[0]

            if status_filter and card.status not in status_filter:
                skipped_filter += 1
                continue
            if type_filter and card.doc_type not in type_filter:
                skipped_filter += 1
                continue
            if remaining_doc_ids is not None and card.doc_id not in remaining_doc_ids:
                skipped_filter += 1
                continue

            yield NPADocument(card=card, text=text)
            matched += 1
            if remaining_doc_ids is not None:
                remaining_doc_ids.discard(card.doc_id)
                if not remaining_doc_ids:
                    break

            if matched % 10_000 == 0:
                logger.info(
                    "Yielded {} documents (skipped: {} no card, {} filter, {} empty)",
                    matched,
                    skipped_no_card,
                    skipped_filter,
                    skipped_empty,
                )
    except ET.ParseError as exc:
        if matched > 0:
            logger.warning("XML parse error after {} texts (ignored): {}", matched, exc)
        else:
            raise

    logger.info(
        "Done. Total yielded: {}, skipped: {} no card, {} filter, {} empty",
        matched,
        skipped_no_card,
        skipped_filter,
        skipped_empty,
    )


# ---------------------------------------------------------------------------
# Manifest builder (optional: persist doc list to JSONL for inspection)
# ---------------------------------------------------------------------------

def build_manifest(
    cards_path: Path,
    texts_path: Path,
    output_path: Path,
    *,
    status_filter: frozenset[str] | None = None,
    type_filter: frozenset[str] | None = None,
    doc_id_filter: frozenset[str] | None = None,
) -> int:
    """Write manifest.jsonl with all document metadata. Returns count."""
    count = 0
    with open(output_path, "w", encoding="utf-8") as fh:
        for doc in iter_documents(
            cards_path, texts_path,
            status_filter=status_filter,
            type_filter=type_filter,
            doc_id_filter=doc_id_filter,
        ):
            entry = {
                "doc_id": doc.card.doc_id,
                "reestr_code": doc.card.reestr_code,
                "date_acc": doc.card.date_acc,
                "status": doc.card.status,
                "doc_type": doc.card.doc_type,
                "name": doc.card.name,
                "publisher": list(doc.card.publisher),
                "number": doc.card.number,
                "keywords": list(doc.card.keywords),
                "text_length": len(doc.text),
            }
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            count += 1
    logger.info("Manifest written: {} entries -> {}", count, output_path)
    return count
