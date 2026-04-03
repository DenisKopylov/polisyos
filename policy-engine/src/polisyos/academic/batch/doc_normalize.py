"""Normalize academic full text into structured substrate artifacts."""

from __future__ import annotations

import asyncio
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiohttp

from polisyos.academic.batch.article_extractor import (
    _build_evidence_bundle,
    _normalized_text,
    _select_numeric_result_blocks,
    _split_sentences,
)
from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.batch.fulltext_resolver import (
    FullTextFetchResult,
    _extract_html_tables,
    fetch_full_text_result_for_work,
    load_resolved_fulltext_cache,
    reconstruct_abstract,
)
from polisyos.batch_common.manifest import write_stage_manifest

try:
    from polisyos.academic.batch.table_extractor import extract_tables_from_pdf
    _HAS_TABLE_EXTRACTOR = True
except ImportError:
    _HAS_TABLE_EXTRACTOR = False

_JATS_ROOT_RE = re.compile(r"<article\b", re.IGNORECASE)
_JATS_NS = "{http://jats.nlm.nih.gov/ns/archiving/1.0/}"

_SECTION_HEADING_RE = re.compile(
    r"^\s*(abstract|introduction|background|methods?|materials?(?:\s+and\s+methods?)?|"
    r"results?|discussion|conclusion|limitations|references|bibliography|appendix|supplementary(?: materials?)?)\s*:?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_TABLE_RE = re.compile(r"\b(table\s+\d+|panel\s+[a-z]|regression results?)\b", re.IGNORECASE)
_FIGURE_RE = re.compile(r"\b(fig(?:ure)?\s+\d+)\b", re.IGNORECASE)
_APPENDIX_RE = re.compile(r"\b(appendix|supplementary(?: materials?)?|online appendix)\b", re.IGNORECASE)
_REFERENCE_RE = re.compile(
    r"(\bdoi:\s*\S+|\bhttps?://\S+|\[[0-9]{1,3}\]|\([A-Z][A-Za-z\-]+(?:\s+et al\.)?,\s*\d{4}\))"
)
_RCT_RE = re.compile(r"\b(randomi[sz]ed|random assignment|rct|encouragement design|field experiment)\b", re.IGNORECASE)
_QUASI_RE = re.compile(
    r"\b(difference.?in.?differences?|instrumental variable|2sls|tsls|regression discontinuity|rdd\b|"
    r"synthetic control|natural experiment|quasi[- ]experimental|event study)\b",
    re.IGNORECASE,
)
_OBSERVATIONAL_RE = re.compile(
    r"\b(observational|cohort|case-control|cross-sectional|panel data|fixed effects|ols\b)\b",
    re.IGNORECASE,
)
_REVIEW_RE = re.compile(r"\b(systematic review|meta-analysis|review article|literature review)\b", re.IGNORECASE)
_THEORETICAL_RE = re.compile(r"\b(theoretical|conceptual framework|simulation model|proof)\b", re.IGNORECASE)
_METHODS_RE = re.compile(r"\b(methodological|benchmark dataset|algorithm|architecture|estimation method)\b", re.IGNORECASE)
_CONTEXT_RE = re.compile(
    r"\b(country|countries|regional|jurisdiction|institutional|historical|comparative|governance|socioeconomic|policy context)\b",
    re.IGNORECASE,
)
_MECHANISM_RE = re.compile(r"\b(mechanism|channel|pathway|mediat(?:e|es|ion)|through which)\b", re.IGNORECASE)
_XML_SIGNAL_RE = re.compile(r"<(?:article|article-meta|body|sec|front|back)\b", re.IGNORECASE)
_TEI_SIGNAL_RE = re.compile(r"<TEI\b", re.IGNORECASE)
_PDF_MAGIC = b"%PDF"


def _jsonl_write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _jsonl_append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _iter_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _reset_doc_normalize_paths(config: AcademicBatchConfig) -> None:
    reset_paths = [
        config.fulltext_resolved_path,
        config.doc_substrate_path,
        config.doc_sentences_path,
        config.doc_sections_path,
        config.doc_references_path,
        config.doc_tables_path,
        config.doc_figures_path,
        config.doc_appendix_blocks_path,
        config.doc_routing_path,
        config.doc_ready_queue_path,
        config.doc_json_path,
        config.manifests_dir / "doc_normalize.json",
    ]
    for path in reset_paths:
        if path.exists():
            path.unlink()
    if config.doc_tei_dir.exists():
        for child in config.doc_tei_dir.iterdir():
            if child.is_file():
                child.unlink()


def _load_selected_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _fetch_result_to_row(
    *,
    work_id: str,
    result: FullTextFetchResult,
) -> dict[str, Any]:
    text = _normalized_text(result.text)
    return {
        "work_id": work_id,
        "source_kind": result.source_kind,
        "source_basis": "abstract_only" if result.source_kind == "abstract_fallback" else "fulltext",
        "text_quality": (
            "abstract_only"
            if result.source_kind == "abstract_fallback"
            else "degraded"
            if len(text) < 800
            else "extracted_fulltext"
        ),
        "source_url": result.source_url,
        "fetch_error_class": result.fetch_error_class,
        "final_state": result.final_state,
        "text": text,
    }


def _extract_sections(text: str, *, title: str, abstract: str, bundle: dict[str, Any]) -> list[dict[str, Any]]:
    raw_text = str(text or "")
    sections: list[dict[str, Any]] = []
    matches = list(_SECTION_HEADING_RE.finditer(raw_text))
    if matches:
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(raw_text)
            body = _normalized_text(raw_text[start:end])
            if not body:
                continue
            heading = _normalized_text(match.group(1)).lower()
            sections.append(
                {
                    "section_id": f"sec_{index + 1:03d}",
                    "section_name": heading,
                    "text": body,
                    "char_count": len(body),
                }
            )
    if sections:
        return sections

    synthesized: list[tuple[str, str]] = []
    if abstract.strip():
        synthesized.append(("abstract", abstract))
    for bucket, label in (
        ("method_sentences", "methods"),
        ("result_sentences", "results"),
        ("claim_sentences", "claims"),
    ):
        texts = [
            _normalized_text(item.get("text"))
            for item in bundle.get(bucket, [])
            if isinstance(item, dict) and _normalized_text(item.get("text"))
        ]
        if texts:
            synthesized.append((label, " ".join(texts)))
    if not synthesized and raw_text.strip():
        synthesized.append(("body", _normalized_text(raw_text[:8000])))
    for index, (label, body) in enumerate(synthesized, start=1):
        sections.append(
            {
                "section_id": f"sec_{index:03d}",
                "section_name": label,
                "text": body,
                "char_count": len(body),
            }
        )
    return sections


def _extract_tables(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, block in enumerate(_select_numeric_result_blocks(text, limit=24), start=1):
        match = _TABLE_RE.search(str(block.get("text") or ""))
        rows.append(
            {
                "table_id": f"tbl_{index:03d}",
                "label": match.group(1) if match else f"table_{index}",
                "text": str(block.get("text") or ""),
                "score": float(block.get("score") or 0.0),
            }
        )
    return rows


def _extract_figures(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    normalized = _normalized_text(text)
    seen: set[str] = set()
    for index, match in enumerate(_FIGURE_RE.finditer(normalized), start=1):
        label = _normalized_text(match.group(1)).lower()
        if label in seen:
            continue
        seen.add(label)
        start = max(0, match.start() - 120)
        end = min(len(normalized), match.end() + 220)
        rows.append(
            {
                "figure_id": f"fig_{index:03d}",
                "label": label,
                "text": normalized[start:end].strip(" ;,"),
            }
        )
    return rows


def _extract_appendix_blocks(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    raw_text = str(text or "")
    matches = list(_APPENDIX_RE.finditer(raw_text))
    for index, match in enumerate(matches[:16], start=1):
        start = max(0, match.start() - 120)
        end = min(len(raw_text), match.end() + 900)
        block = _normalized_text(raw_text[start:end])
        if len(block) < 40:
            continue
        rows.append(
            {
                "appendix_id": f"app_{index:03d}",
                "label": _normalized_text(match.group(1)).lower(),
                "text": block,
            }
        )
    return rows


def _extract_references(text: str, work: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    doi = _normalized_text(work.get("doi"))
    if doi:
        rows.append({"reference_id": "ref_001", "reference_text": f"doi:{doi}", "kind": "doi"})
        seen.add(f"doi:{doi}")
    normalized = _normalized_text(text)
    for index, match in enumerate(_REFERENCE_RE.finditer(normalized), start=2):
        snippet = _normalized_text(match.group(1))
        if not snippet or snippet in seen:
            continue
        seen.add(snippet)
        rows.append(
            {
                "reference_id": f"ref_{index:03d}",
                "reference_text": snippet,
                "kind": "inline_citation" if snippet.startswith("[") or snippet.startswith("(") else "link",
            }
        )
        if len(rows) >= 32:
            break
    return rows


def _infer_source_hint(source_kind: str, source_url: str, content_type: str, payload: bytes) -> str:
    kind = str(source_kind or "").strip().lower()
    url = str(source_url or "").strip().lower()
    ctype = str(content_type or "").strip().lower()
    prefix = payload[:256].decode("utf-8", errors="ignore")
    if "xml" in ctype or kind == "publisher_xml" or _XML_SIGNAL_RE.search(prefix):
        return "publisher_xml"
    if "pdf" in ctype or payload.startswith(_PDF_MAGIC) or url.endswith(".pdf") or "pdf" in kind:
        return "pdf"
    return "text"


def _tei_endpoint(base_url: str, default_path: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    if not base:
        return ""
    if base.endswith(default_path):
        return base
    return f"{base}{default_path}"


async def _fetch_source_document(
    session: aiohttp.ClientSession,
    *,
    source_url: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    if not str(source_url or "").strip():
        return {"ok": False, "error_class": "missing_source_url"}
    timeout = aiohttp.ClientTimeout(total=max(3, int(timeout_seconds)))
    try:
        async with session.get(source_url, timeout=timeout, allow_redirects=True) as response:
            payload = await response.read()
            content_type = str(response.headers.get("Content-Type") or "").strip().lower()
            return {
                "ok": 200 <= int(response.status) < 300,
                "status": int(response.status),
                "content_type": content_type,
                "bytes": payload,
                "text": payload.decode("utf-8", errors="ignore"),
            }
    except asyncio.TimeoutError:
        return {"ok": False, "error_class": "source_fetch_timeout"}
    except aiohttp.ClientError as exc:
        return {"ok": False, "error_class": exc.__class__.__name__.lower()}


async def _call_pub2tei(
    session: aiohttp.ClientSession,
    *,
    base_url: str,
    xml_text: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    endpoint = _tei_endpoint(base_url, "/service/processXML")
    if not endpoint:
        return {"ok": False, "error_class": "pub2tei_disabled"}
    timeout = aiohttp.ClientTimeout(total=max(5, int(timeout_seconds)))
    form = aiohttp.FormData()
    form.add_field("input", xml_text.encode("utf-8"), filename="document.xml", content_type="application/xml")
    form.add_field("segmentSentences", "1")
    form.add_field("generateIDs", "1")
    try:
        async with session.post(endpoint, data=form, timeout=timeout) as response:
            tei_text = await response.text()
            ok = 200 <= int(response.status) < 300 and bool(_TEI_SIGNAL_RE.search(tei_text))
            return {
                "ok": ok,
                "status": int(response.status),
                "tei_text": tei_text,
                "error_class": "" if ok else "pub2tei_invalid_response",
            }
    except asyncio.TimeoutError:
        return {"ok": False, "error_class": "pub2tei_timeout"}
    except aiohttp.ClientError as exc:
        return {"ok": False, "error_class": exc.__class__.__name__.lower()}


async def _call_grobid(
    session: aiohttp.ClientSession,
    *,
    base_url: str,
    pdf_bytes: bytes,
    timeout_seconds: int,
) -> dict[str, Any]:
    endpoint = _tei_endpoint(base_url, "/api/processFulltextDocument")
    if not endpoint:
        return {"ok": False, "error_class": "grobid_disabled"}
    timeout = aiohttp.ClientTimeout(total=max(5, int(timeout_seconds)))
    form = aiohttp.FormData()
    form.add_field("input", pdf_bytes, filename="document.pdf", content_type="application/pdf")
    try:
        async with session.post(endpoint, data=form, timeout=timeout) as response:
            tei_text = await response.text()
            ok = 200 <= int(response.status) < 300 and bool(_TEI_SIGNAL_RE.search(tei_text))
            return {
                "ok": ok,
                "status": int(response.status),
                "tei_text": tei_text,
                "error_class": "" if ok else "grobid_invalid_response",
            }
    except asyncio.TimeoutError:
        return {"ok": False, "error_class": "grobid_timeout"}
    except aiohttp.ClientError as exc:
        return {"ok": False, "error_class": exc.__class__.__name__.lower()}


def _tei_tag_name(tag: str) -> str:
    return str(tag or "").split("}", 1)[-1]


def _tei_text(elem: ET.Element | None) -> str:
    if elem is None:
        return ""
    return _normalized_text(" ".join(chunk for chunk in elem.itertext()))


def _tei_child_text(elem: ET.Element, names: tuple[str, ...]) -> str:
    wanted = set(names)
    for child in list(elem):
        if _tei_tag_name(child.tag) in wanted:
            text = _tei_text(child)
            if text:
                return text
    return ""


def _parse_tei_artifacts(tei_text: str) -> dict[str, Any]:
    root = ET.fromstring(tei_text)
    title = ""
    for elem in root.iter():
        if _tei_tag_name(elem.tag) == "title":
            title = _tei_text(elem)
            if title:
                break

    sections: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    figures: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    appendix_blocks: list[dict[str, Any]] = []

    section_index = 0
    fallback_paragraphs: list[str] = []
    for elem in root.iter():
        tag = _tei_tag_name(elem.tag)
        if tag in {"div", "div1", "div2", "div3", "section"}:
            body = _tei_text(elem)
            if not body:
                continue
            heading = _tei_child_text(elem, ("head", "title")) or _normalized_text(elem.attrib.get("type"))
            if heading and body.lower().startswith(heading.lower()):
                body = _normalized_text(body[len(heading) :])
            section_index += 1
            payload = {
                "section_id": f"sec_{section_index:03d}",
                "section_name": heading.lower() if heading else f"section_{section_index}",
                "text": body,
                "char_count": len(body),
            }
            sections.append(payload)
            if _APPENDIX_RE.search(heading) or _APPENDIX_RE.search(body[:200]):
                appendix_blocks.append(
                    {
                        "appendix_id": f"app_{len(appendix_blocks) + 1:03d}",
                        "label": heading.lower() if heading else "appendix",
                        "text": body[:2400],
                    }
                )
        elif tag == "p":
            text = _tei_text(elem)
            if text:
                fallback_paragraphs.append(text)
        elif tag == "table":
            text = _tei_text(elem)
            if text:
                tables.append(
                    {
                        "table_id": f"tbl_{len(tables) + 1:03d}",
                        "label": _tei_child_text(elem, ("head", "label")) or f"table_{len(tables) + 1}",
                        "text": text,
                        "score": 1.0,
                        "structure_source": "tei_table",
                    }
                )
        elif tag == "figure":
            text = _tei_text(elem)
            if not text:
                continue
            figure_type = _normalized_text(elem.attrib.get("type")).lower()
            label = _tei_child_text(elem, ("head", "label")) or _normalized_text(elem.attrib.get("{http://www.w3.org/XML/1998/namespace}id"))
            if figure_type == "table" or _TABLE_RE.search(text):
                tables.append(
                    {
                        "table_id": f"tbl_{len(tables) + 1:03d}",
                        "label": label or f"table_{len(tables) + 1}",
                        "text": text,
                        "score": 1.0,
                        "structure_source": "tei_figure_table",
                    }
                )
            else:
                figures.append(
                    {
                        "figure_id": f"fig_{len(figures) + 1:03d}",
                        "label": (label or f"figure_{len(figures) + 1}").lower(),
                        "text": text[:3200],
                    }
                )
        elif tag in {"biblStruct", "bibl"}:
            text = _tei_text(elem)
            if text:
                references.append(
                    {
                        "reference_id": f"ref_{len(references) + 1:03d}",
                        "reference_text": text[:1000],
                        "kind": "tei_reference",
                    }
                )

    if not sections and fallback_paragraphs:
        for index, paragraph in enumerate(fallback_paragraphs[:24], start=1):
            sections.append(
                {
                    "section_id": f"sec_{index:03d}",
                    "section_name": "body",
                    "text": paragraph,
                    "char_count": len(paragraph),
                }
            )

    return {
        "title": title,
        "sections": sections,
        "tables": tables,
        "figures": figures,
        "references": references[:64],
        "appendix_blocks": appendix_blocks[:24],
    }


def _safe_parse_tei_artifacts(tei_text: str) -> dict[str, Any] | None:
    try:
        return _parse_tei_artifacts(tei_text)
    except ET.ParseError:
        return None


def _parse_jats_xml(xml_text: str) -> dict[str, Any] | None:
    """Parse JATS/NLM XML directly into structured artifacts."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    # Detect JATS root (with or without namespace)
    root_tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
    if root_tag != "article":
        return None

    ns = ""
    if "}" in root.tag:
        ns = root.tag.split("}")[0] + "}"

    def _find(parent: ET.Element, tag: str) -> ET.Element | None:
        return parent.find(f"{ns}{tag}") or parent.find(tag)

    def _findall(parent: ET.Element, tag: str) -> list[ET.Element]:
        return list(parent.findall(f".//{ns}{tag}") or parent.findall(f".//{tag}"))

    def _text_of(elem: ET.Element | None) -> str:
        if elem is None:
            return ""
        return _normalized_text(" ".join(chunk for chunk in elem.itertext()))

    title = ""
    title_group = _find(root, ".//article-meta/title-group/article-title")
    if title_group is None:
        for path in [".//front/article-meta/title-group/article-title", ".//article-title"]:
            candidate = root.find(f".//{ns}{path.lstrip('./')}") or root.find(path)
            if candidate is not None:
                title_group = candidate
                break
    title = _text_of(title_group)

    sections: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    figures: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []

    # Extract sections from <body><sec>
    sec_idx = 0
    for sec in _findall(root, "sec"):
        heading_elem = _find(sec, "title")
        heading = _text_of(heading_elem).lower() if heading_elem is not None else ""
        body = _text_of(sec)
        if heading and body.lower().startswith(heading):
            body = _normalized_text(body[len(heading):])
        if not body:
            continue
        sec_idx += 1
        sections.append({
            "section_id": f"sec_{sec_idx:03d}",
            "section_name": heading or f"section_{sec_idx}",
            "text": body,
            "char_count": len(body),
        })

    # Extract tables from <table-wrap>
    for tw in _findall(root, "table-wrap"):
        label_elem = _find(tw, "label")
        caption_elem = _find(tw, "caption")
        table_elem = _find(tw, "table")
        label = _text_of(label_elem) or f"table_{len(tables) + 1}"
        caption = _text_of(caption_elem)

        # Try to extract structured table
        rows_data: list[list[str]] = []
        if table_elem is not None:
            for tr in _findall(table_elem, "tr"):
                cells = []
                for cell_tag in ("th", "td"):
                    for cell in (tr.findall(f"{ns}{cell_tag}") or tr.findall(cell_tag)):
                        cells.append(_text_of(cell))
                if cells:
                    rows_data.append(cells)

        if rows_data and len(rows_data) >= 2:
            headers = rows_data[0]
            md_lines = ["| " + " | ".join(headers) + " |"]
            md_lines.append("| " + " | ".join("---" for _ in headers) + " |")
            for row in rows_data[1:]:
                padded = row + [""] * max(0, len(headers) - len(row))
                md_lines.append("| " + " | ".join(padded[:len(headers)]) + " |")
            text = "\n".join(md_lines)
            if caption:
                text = f"{label}: {caption}\n{text}"
        else:
            text = _text_of(tw)

        if text:
            tables.append({
                "table_id": f"tbl_{len(tables) + 1:03d}",
                "label": label,
                "text": text,
                "score": 1.0,
                "structure_source": "jats_table",
            })

    # Extract figures from <fig>
    for fig in _findall(root, "fig"):
        label_elem = _find(fig, "label")
        caption_elem = _find(fig, "caption")
        label = (_text_of(label_elem) or f"figure_{len(figures) + 1}").lower()
        caption = _text_of(caption_elem)
        if caption:
            figures.append({
                "figure_id": f"fig_{len(figures) + 1:03d}",
                "label": label,
                "text": f"{label}: {caption}"[:3200],
            })

    # Extract references from <ref-list><ref>
    for ref in _findall(root, "ref"):
        text = _text_of(ref)
        if text:
            references.append({
                "reference_id": f"ref_{len(references) + 1:03d}",
                "reference_text": text[:1000],
                "kind": "jats_reference",
            })

    if not sections and not tables:
        return None

    return {
        "title": title,
        "sections": sections,
        "tables": tables,
        "figures": figures,
        "references": references[:64],
        "appendix_blocks": [],
    }


def _extract_tables_from_pdf_bytes(pdf_bytes: bytes, work_id: str) -> list[dict[str, Any]]:
    """Use table_extractor (marker-pdf) to get structured tables from PDF bytes."""
    if not _HAS_TABLE_EXTRACTOR:
        return []
    import tempfile
    from pathlib import Path as _Path
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = _Path(tmp.name)
        raw_tables = extract_tables_from_pdf(tmp_path)
        tmp_path.unlink(missing_ok=True)
    except Exception:
        from polisyos.common.logger import get_logger as _gl
        _gl(__name__).debug("table_extractor failed for {}", work_id, exc_info=True)
        return []

    structured: list[dict[str, Any]] = []
    for tbl in raw_tables:
        headers = tbl.get("headers", [])
        rows = tbl.get("rows", [])
        if not headers or not rows:
            continue
        md_lines = ["| " + " | ".join(str(h) for h in headers) + " |"]
        md_lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for row in rows[:50]:
            padded = [str(c) for c in row] + [""] * max(0, len(headers) - len(row))
            md_lines.append("| " + " | ".join(padded[:len(headers)]) + " |")
        structured.append({
            "table_id": f"tbl_marker_{tbl.get('table_index', len(structured)) + 1:03d}",
            "label": f"table_{tbl.get('table_index', len(structured)) + 1}",
            "text": "\n".join(md_lines),
            "headers": headers,
            "rows": rows[:50],
            "numeric_cells": tbl.get("numeric_cells", []),
            "score": 0.9,
            "structure_source": "marker_pdf",
        })
    return structured


async def _build_document_substrate(
    *,
    session: aiohttp.ClientSession,
    config: AcademicBatchConfig,
    fetch_result: FullTextFetchResult,
    title: str,
    abstract: str,
    work: dict[str, Any],
) -> dict[str, Any]:
    text = _normalized_text(fetch_result.text or abstract)
    bundle = _build_evidence_bundle(
        title=title,
        abstract=abstract,
        text=text,
        source_kind=fetch_result.source_kind,
    )
    fallback_sections = _extract_sections(text, title=title, abstract=abstract, bundle=bundle)
    fallback_tables = _extract_tables(text)
    fallback_figures = _extract_figures(text)
    fallback_appendix = _extract_appendix_blocks(text)
    fallback_references = _extract_references(text, work)
    fallback_tei = _pseudo_tei_xml(title=title, sections=fallback_sections)

    work_id = str(work.get("id") or work.get("work_id") or "")

    if fetch_result.source_kind == "abstract_fallback":
        return {
            "text": text,
            "bundle": bundle,
            "sections": fallback_sections,
            "tables": fallback_tables,
            "figures": fallback_figures,
            "appendix_blocks": fallback_appendix,
            "references": fallback_references,
            "tei_text": fallback_tei,
            "tei_source": "heuristic",
            "tei_status": "fallback",
            "infra_error_class": "",
            "source_content_type": "",
            "source_fetch_status": 0,
        }

    source_doc = await _fetch_source_document(
        session,
        source_url=str(fetch_result.source_url or ""),
        timeout_seconds=config.doc_infra_timeout_seconds,
    )
    payload = bytes(source_doc.get("bytes") or b"")
    source_text = str(source_doc.get("text") or "")
    content_type = str(source_doc.get("content_type") or "")
    source_hint = _infer_source_hint(fetch_result.source_kind, str(fetch_result.source_url or ""), content_type, payload)

    # --- Try native JATS XML parsing (before Pub2TEI) ---
    if source_doc.get("ok") and source_hint == "publisher_xml":
        xml_payload = source_text if source_text.strip() else payload.decode("utf-8", errors="ignore")
        if _JATS_ROOT_RE.search(xml_payload[:2000]):
            jats_parsed = _parse_jats_xml(xml_payload)
            if jats_parsed is not None and (jats_parsed.get("sections") or jats_parsed.get("tables")):
                return {
                    "text": text,
                    "bundle": bundle,
                    "sections": jats_parsed["sections"] or fallback_sections,
                    "tables": jats_parsed["tables"] or fallback_tables,
                    "figures": jats_parsed["figures"] or fallback_figures,
                    "appendix_blocks": jats_parsed.get("appendix_blocks") or fallback_appendix,
                    "references": jats_parsed["references"] or fallback_references,
                    "tei_text": fallback_tei,
                    "tei_source": "jats_native",
                    "tei_status": "ok",
                    "infra_error_class": "",
                    "source_content_type": content_type,
                    "source_fetch_status": int(source_doc.get("status") or 0),
                }

    # --- Try HTML table extraction ---
    if source_doc.get("ok") and source_hint not in ("pdf", "publisher_xml") and config.fulltext_extract_html_tables:
        html_content = source_text if source_text.strip() else payload.decode("utf-8", errors="ignore")
        html_tables = _extract_html_tables(html_content)
        if html_tables:
            merged_tables = html_tables + fallback_tables
            return {
                "text": text,
                "bundle": bundle,
                "sections": fallback_sections,
                "tables": merged_tables,
                "figures": fallback_figures,
                "appendix_blocks": fallback_appendix,
                "references": fallback_references,
                "tei_text": fallback_tei,
                "tei_source": "html_tables",
                "tei_status": "fallback",
                "infra_error_class": "",
                "source_content_type": content_type,
                "source_fetch_status": int(source_doc.get("status") or 0),
            }

    # --- Try marker-pdf structured table extraction for PDFs ---
    if source_doc.get("ok") and source_hint == "pdf" and payload.startswith(_PDF_MAGIC) and _HAS_TABLE_EXTRACTOR:
        marker_tables = _extract_tables_from_pdf_bytes(payload, work_id)
        if marker_tables:
            merged_tables = marker_tables + fallback_tables
            fallback_tables = merged_tables

    if not config.doc_infra_enable_pub2tei and not config.doc_infra_enable_grobid:
        return {
            "text": text,
            "bundle": bundle,
            "sections": fallback_sections,
            "tables": fallback_tables,
            "figures": fallback_figures,
            "appendix_blocks": fallback_appendix,
            "references": fallback_references,
            "tei_text": fallback_tei,
            "tei_source": "heuristic",
            "tei_status": "fallback",
            "infra_error_class": "",
            "source_content_type": content_type if source_doc.get("ok") else "",
            "source_fetch_status": int(source_doc.get("status") or 0) if source_doc.get("ok") else 0,
        }

    if source_doc.get("ok"):
        precedence = tuple(str(item).strip().lower() for item in config.doc_infra_precedence if str(item).strip())
        attempted = False
        for lane in precedence:
            if lane == "publisher_xml" and config.doc_infra_enable_pub2tei and source_hint == "publisher_xml":
                attempted = True
                xml_payload = source_text if source_text.strip() else payload.decode("utf-8", errors="ignore")
                if _TEI_SIGNAL_RE.search(xml_payload):
                    tei_payload = {"ok": True, "tei_text": xml_payload, "status": 200, "error_class": ""}
                else:
                    tei_payload = await _call_pub2tei(
                        session,
                        base_url=config.doc_pub2tei_base_url,
                        xml_text=xml_payload,
                        timeout_seconds=config.doc_infra_timeout_seconds,
                    )
                if tei_payload.get("ok") and str(tei_payload.get("tei_text") or "").strip():
                    parsed = _safe_parse_tei_artifacts(str(tei_payload["tei_text"]))
                    if parsed is not None:
                        return {
                            "text": text,
                            "bundle": bundle,
                            "sections": parsed["sections"] or fallback_sections,
                            "tables": parsed["tables"] or fallback_tables,
                            "figures": parsed["figures"] or fallback_figures,
                            "appendix_blocks": parsed["appendix_blocks"] or fallback_appendix,
                            "references": parsed["references"] or fallback_references,
                            "tei_text": str(tei_payload["tei_text"]),
                            "tei_source": "pub2tei",
                            "tei_status": "ok",
                            "infra_error_class": "",
                            "source_content_type": content_type,
                            "source_fetch_status": int(source_doc.get("status") or 0),
                        }
                    infra_error_class = "pub2tei_malformed_tei"
                else:
                    infra_error_class = str(tei_payload.get("error_class") or "pub2tei_failed")
            elif lane == "pdf" and config.doc_infra_enable_grobid and source_hint == "pdf":
                attempted = True
                if not payload.startswith(_PDF_MAGIC):
                    infra_error_class = "fake_pdf_source"
                else:
                    tei_payload = await _call_grobid(
                        session,
                        base_url=config.doc_grobid_base_url,
                        pdf_bytes=payload,
                        timeout_seconds=config.doc_infra_timeout_seconds,
                    )
                    if tei_payload.get("ok") and str(tei_payload.get("tei_text") or "").strip():
                        parsed = _safe_parse_tei_artifacts(str(tei_payload["tei_text"]))
                        if parsed is not None:
                            return {
                                "text": text,
                                "bundle": bundle,
                                "sections": parsed["sections"] or fallback_sections,
                                "tables": parsed["tables"] or fallback_tables,
                                "figures": parsed["figures"] or fallback_figures,
                                "appendix_blocks": parsed["appendix_blocks"] or fallback_appendix,
                                "references": parsed["references"] or fallback_references,
                                "tei_text": str(tei_payload["tei_text"]),
                                "tei_source": "grobid",
                                "tei_status": "ok",
                                "infra_error_class": "",
                                "source_content_type": content_type,
                                "source_fetch_status": int(source_doc.get("status") or 0),
                            }
                        infra_error_class = "grobid_malformed_tei"
                    else:
                        infra_error_class = str(tei_payload.get("error_class") or "grobid_failed")
            if lane == "text":
                break
        if not attempted:
            infra_error_class = ""
    else:
        infra_error_class = str(source_doc.get("error_class") or "source_fetch_failed")

    return {
        "text": text,
        "bundle": bundle,
        "sections": fallback_sections,
        "tables": fallback_tables,
        "figures": fallback_figures,
        "appendix_blocks": fallback_appendix,
        "references": fallback_references,
        "tei_text": fallback_tei,
        "tei_source": "heuristic",
        "tei_status": "fallback",
        "infra_error_class": infra_error_class,
        "source_content_type": content_type,
        "source_fetch_status": int(source_doc.get("status") or 0) if isinstance(source_doc, dict) else 0,
    }


def _classify_doc_family(*, title: str, abstract: str, text: str, tables: list[dict[str, Any]], appendix_blocks: list[dict[str, Any]]) -> str:
    haystack = "\n".join(part for part in (title, abstract, text[:12000]) if part)
    if _REVIEW_RE.search(haystack):
        return "review_meta_analysis"
    if _RCT_RE.search(haystack):
        return "empirical_rct"
    if _QUASI_RE.search(haystack):
        return "empirical_quasi"
    if _OBSERVATIONAL_RE.search(haystack):
        return "observational"
    if _METHODS_RE.search(haystack):
        return "methods"
    if _THEORETICAL_RE.search(haystack):
        return "theoretical"
    if len(appendix_blocks) >= 2:
        return "appendix_heavy"
    if len(tables) >= 2:
        return "table_heavy"
    return "observational" if _CONTEXT_RE.search(haystack) else "methods"


def _route_document(*, family: str, bundle: dict[str, Any], tables: list[dict[str, Any]], appendix_blocks: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
    normalized = _normalized_text(text)
    route_rows: list[dict[str, Any]] = []
    claim_score = 0.0
    if family in {"empirical_rct", "empirical_quasi", "observational", "review_meta_analysis"}:
        claim_score += 0.45
    claim_score += min(0.35, 0.05 * len(bundle.get("claim_sentences", [])))
    if len(bundle.get("result_sentences", [])) >= 2:
        claim_score += 0.1
    route_rows.append(
        {
            "lane": "claim",
            "eligible": claim_score >= 0.45,
            "route": "llm" if claim_score >= 0.45 else "skip",
            "score": round(min(1.0, claim_score), 4),
            "reasons": ["family_signal", "claim_sentences"] if claim_score >= 0.45 else ["low_claim_signal"],
        }
    )

    numeric_score = 0.0
    if family in {"empirical_rct", "empirical_quasi", "observational", "table_heavy"}:
        numeric_score += 0.35
    numeric_score += min(0.35, 0.08 * len(tables))
    numeric_score += min(0.2, 0.03 * len(bundle.get("numeric_result_blocks", [])))
    numeric_score += 0.1 if re.search(r"\b(95%\s*ci|std\.?\s*err(?:or)?|odds ratio|hazard ratio|coefficient|beta)\b", normalized, re.IGNORECASE) else 0.0
    route_rows.append(
        {
            "lane": "numeric",
            "eligible": numeric_score >= 0.45,
            "route": "llm" if numeric_score >= 0.45 else "skip",
            "score": round(min(1.0, numeric_score), 4),
            "reasons": ["table_or_result_signal"] if numeric_score >= 0.45 else ["low_numeric_signal"],
        }
    )

    context_score = 0.0
    if family in {"review_meta_analysis", "observational"}:
        context_score += 0.25
    if _CONTEXT_RE.search(normalized):
        context_score += 0.35
    if appendix_blocks:
        context_score += 0.05
    if re.search(r"\b(country|countries|region|regional|institutional|historical|governance)\b", normalized, re.IGNORECASE):
        context_score += 0.2
    route_rows.append(
        {
            "lane": "context",
            "eligible": context_score >= 0.35,
            "route": "llm" if context_score >= 0.35 else "skip",
            "score": round(min(1.0, context_score), 4),
            "reasons": ["context_signal"] if context_score >= 0.35 else ["low_context_signal"],
        }
    )

    mechanism_score = 0.0
    if any(row["eligible"] for row in route_rows if row["lane"] == "claim"):
        mechanism_score += 0.2
    if _MECHANISM_RE.search(normalized):
        mechanism_score += 0.45
    mechanism_score += min(0.15, 0.03 * len(bundle.get("claim_sentences", [])))
    route_rows.append(
        {
            "lane": "mechanism",
            "eligible": mechanism_score >= 0.35,
            "route": "llm" if mechanism_score >= 0.35 else "skip",
            "score": round(min(1.0, mechanism_score), 4),
            "reasons": ["mechanism_signal"] if mechanism_score >= 0.35 else ["low_mechanism_signal"],
        }
    )
    return route_rows


def _pseudo_tei_xml(*, title: str, sections: list[dict[str, Any]]) -> str:
    section_xml = "\n".join(
        (
            f'<div type="{_normalized_text(section.get("section_name")) or "section"}">'
            f"<head>{_normalized_text(section.get('section_name'))}</head>"
            f"<p>{_normalized_text(section.get('text'))}</p>"
            "</div>"
        )
        for section in sections
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<TEI>\n"
        "  <text>\n"
        "    <front>\n"
        f"      <title>{_normalized_text(title)}</title>\n"
        "    </front>\n"
        "    <body>\n"
        f"{section_xml}\n"
        "    </body>\n"
        "  </text>\n"
        "</TEI>\n"
    )


async def run_doc_normalize(config: AcademicBatchConfig) -> dict[str, int]:
    """Run doc normalize."""
    started_at = datetime.now(UTC).isoformat()
    selected_rows = _load_selected_rows(config.selected_global_works_path)
    if not selected_rows:
        write_stage_manifest(
            manifest_path=config.manifests_dir / "doc_normalize.json",
            stage="doc_normalize",
            status="ok",
            metrics={"docs_total": 0, "usable_docs": 0, "sectioned_docs": 0, "table_heavy_docs": 0},
            artifacts=[],
            started_at=started_at,
        )
        return {"docs_total": 0, "usable_docs": 0, "sectioned_docs": 0, "table_heavy_docs": 0}

    if not config.resume:
        _reset_doc_normalize_paths(config)

    processed_work_ids = {
        str(row.get("work_id") or "").strip()
        for row in _iter_jsonl_rows(config.doc_substrate_path)
        if str(row.get("work_id") or "").strip()
    }

    connector_timeout = aiohttp.ClientTimeout(
        total=max(3, int(config.article_total_timeout_seconds)),
        connect=max(1, int(config.article_connect_timeout_seconds)),
        sock_read=max(1, int(config.article_read_timeout_seconds)),
    )
    headers = {"User-Agent": "PolicyOS/1.0 (+academic doc_normalize)"}
    metadata_cache: dict[str, dict[str, Any]] = {}
    resolved_cache = load_resolved_fulltext_cache(
        config.resolved_fulltext_cache_path,
        ttl_days=config.fulltext_cache_ttl_days,
    )
    tei_source_counter: Counter[str] = Counter()
    infra_error_counter: Counter[str] = Counter()
    family_counter: Counter[str] = Counter()

    async with aiohttp.ClientSession(timeout=connector_timeout, headers=headers) as session:
        for selected_row in selected_rows:
            work = selected_row.get("work") if isinstance(selected_row.get("work"), dict) else {}
            work_id = str(selected_row.get("work_id") or work.get("id") or "").strip()
            if not work_id:
                continue
            if work_id in processed_work_ids:
                continue
            abstract = reconstruct_abstract(work)
            try:
                fetch_result = await fetch_full_text_result_for_work(
                    work,
                    timeout_seconds=config.article_fulltext_timeout_seconds,
                    connect_timeout_seconds=config.article_connect_timeout_seconds,
                    read_timeout_seconds=config.article_read_timeout_seconds,
                    total_timeout_seconds=config.article_total_timeout_seconds,
                    session=session,
                    acquisition_mode=config.fulltext_acquisition_mode,
                    metadata_resolvers_enabled=config.fulltext_metadata_resolvers_enabled,
                    metadata_resolver_order=config.fulltext_metadata_resolver_order,
                    unpaywall_email=config.fulltext_unpaywall_email,
                    semantic_scholar_api_key=config.fulltext_semantic_scholar_api_key,
                    metadata_timeout_seconds=config.fulltext_metadata_timeout_seconds,
                    max_candidate_urls_per_work=config.fulltext_max_candidate_urls_per_work,
                    min_usable_chars=config.fulltext_min_usable_chars,
                    min_soft_usable_chars=config.fulltext_min_soft_usable_chars,
                    soft_usable_requires_section_cues=config.fulltext_soft_usable_requires_section_cues,
                    metadata_cache=metadata_cache,
                    resolved_cache=resolved_cache,
                    cache_ttl_days=config.fulltext_cache_ttl_days,
                )
            except Exception:
                fetch_result = FullTextFetchResult(
                    text=abstract,
                    source_kind="abstract_fallback",
                    source_url="",
                    fetch_error_class="fetch_error",
                    final_state="abstract_fallback",
                )
            fulltext_row = _fetch_result_to_row(work_id=work_id, result=fetch_result)
            _jsonl_append(config.fulltext_resolved_path, fulltext_row)
            title = str(work.get("title") or "")
            substrate = await _build_document_substrate(
                session=session,
                config=config,
                fetch_result=fetch_result,
                title=title,
                abstract=abstract,
                work=work,
            )
            text = str(substrate["text"])
            bundle = dict(substrate["bundle"])
            sections = list(substrate["sections"])
            tables = list(substrate["tables"])
            figures = list(substrate["figures"])
            appendix_blocks = list(substrate["appendix_blocks"])
            references = list(substrate["references"])
            tei_source = str(substrate.get("tei_source") or "heuristic")
            tei_status = str(substrate.get("tei_status") or "fallback")
            infra_error_class = str(substrate.get("infra_error_class") or "")
            tei_source_counter[tei_source] += 1
            if infra_error_class:
                infra_error_counter[infra_error_class] += 1
            family = _classify_doc_family(
                title=title,
                abstract=abstract,
                text=text,
                tables=tables,
                appendix_blocks=appendix_blocks,
            )
            family_counter[family] += 1
            routing = _route_document(
                family=family,
                bundle=bundle,
                tables=tables,
                appendix_blocks=appendix_blocks,
                text=text,
            )
            tei_path = config.doc_tei_dir / f"{work_id.replace('/', '_')}.xml"
            tei_path.write_text(
                str(substrate["tei_text"]),
                encoding="utf-8",
            )
            substrate_row = {
                "work_id": work_id,
                "title": title,
                "source_kind": fetch_result.source_kind,
                "source_basis": "abstract_only" if fetch_result.source_kind == "abstract_fallback" else "fulltext",
                "text_quality": "abstract_only" if fetch_result.source_kind == "abstract_fallback" else ("degraded" if len(text) < 800 else "extracted_fulltext"),
                "text_chars": len(text),
                "abstract_chars": len(abstract),
                "doc_family": family,
                "section_count": len(sections),
                "sentence_count": len(_split_sentences(text or abstract)),
                "table_count": len(tables),
                "figure_count": len(figures),
                "reference_count": len(references),
                "appendix_block_count": len(appendix_blocks),
                "routing": routing,
                "tei_source": tei_source,
                "tei_status": tei_status,
                "infra_error_class": infra_error_class,
                "source_content_type": str(substrate.get("source_content_type") or ""),
                "source_fetch_status": int(substrate.get("source_fetch_status") or 0),
                "tei_path": str(tei_path),
            }
            _jsonl_append(config.doc_substrate_path, substrate_row)
            for index, sentence in enumerate(_split_sentences(text or abstract), start=1):
                _jsonl_append(
                    config.doc_sentences_path,
                    {
                        "work_id": work_id,
                        "sentence_id": f"s_{index:04d}",
                        "section_name": "body",
                        "text": sentence,
                    },
                )
            for section in sections:
                _jsonl_append(config.doc_sections_path, {"work_id": work_id, **section})
            for row in references:
                _jsonl_append(config.doc_references_path, {"work_id": work_id, **row})
            for row in tables:
                _jsonl_append(config.doc_tables_path, {"work_id": work_id, **row})
            for row in figures:
                _jsonl_append(config.doc_figures_path, {"work_id": work_id, **row})
            for row in appendix_blocks:
                _jsonl_append(config.doc_appendix_blocks_path, {"work_id": work_id, **row})
            routing_row = {
                "work_id": work_id,
                "doc_family": family,
                "routing": routing,
            }
            _jsonl_append(config.doc_routing_path, routing_row)
            _jsonl_append(
                config.doc_ready_queue_path,
                {
                    "work_id": work_id,
                    "fulltext": fulltext_row,
                    "substrate": substrate_row,
                    "sections": sections,
                    "references": references,
                    "tables": tables,
                    "figures": figures,
                    "appendix_blocks": appendix_blocks,
                    "routing": routing_row,
                    "ready_at": datetime.now(UTC).isoformat(),
                },
            )
            processed_work_ids.add(work_id)

    substrate_rows = _iter_jsonl_rows(config.doc_substrate_path)
    table_rows = _iter_jsonl_rows(config.doc_tables_path)
    family_counter: Counter[str] = Counter(
        str(row.get("doc_family") or "unknown")
        for row in substrate_rows
        if isinstance(row, dict)
    )
    tei_source_counter: Counter[str] = Counter(
        str(row.get("tei_source") or "heuristic")
        for row in substrate_rows
        if isinstance(row, dict)
    )
    infra_error_counter: Counter[str] = Counter(
        str(row.get("infra_error_class") or "")
        for row in substrate_rows
        if isinstance(row, dict) and str(row.get("infra_error_class") or "")
    )
    usable_docs = sum(
        1
        for row in substrate_rows
        if isinstance(row, dict) and str(row.get("source_kind") or "") != "abstract_fallback"
    )
    sectioned_docs = sum(
        1
        for row in substrate_rows
        if isinstance(row, dict) and int(row.get("section_count") or 0) > 0
    )
    table_structured_docs = len(
        {
            str(row.get("work_id") or "").strip()
            for row in table_rows
            if isinstance(row, dict)
            and str(row.get("work_id") or "").strip()
            and str(row.get("structure_source") or "").startswith("tei_")
        }
    )
    config.doc_json_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "doc_count": len(substrate_rows),
                "artifacts": {
                    "doc_substrate": str(config.doc_substrate_path),
                    "sentences": str(config.doc_sentences_path),
                    "sections": str(config.doc_sections_path),
                    "references": str(config.doc_references_path),
                    "tables": str(config.doc_tables_path),
                    "figures": str(config.doc_figures_path),
                    "appendix_blocks": str(config.doc_appendix_blocks_path),
                    "routing": str(config.doc_routing_path),
                    "ready_queue": str(config.doc_ready_queue_path),
                    "tei_dir": str(config.doc_tei_dir),
                },
                "doc_family_breakdown": dict(sorted(family_counter.items())),
                "tei_source_breakdown": dict(sorted(tei_source_counter.items())),
                "infra_error_breakdown": dict(sorted(infra_error_counter.items())),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    metrics = {
        "docs_total": len(substrate_rows),
        "usable_docs": usable_docs,
        "sectioned_docs": sectioned_docs,
        "table_heavy_docs": int(family_counter.get("table_heavy", 0)),
        "appendix_heavy_docs": int(family_counter.get("appendix_heavy", 0)),
        "table_structured_docs": table_structured_docs,
        "pub2tei_docs": int(tei_source_counter.get("pub2tei", 0)),
        "grobid_docs": int(tei_source_counter.get("grobid", 0)),
        "heuristic_docs": int(tei_source_counter.get("heuristic", 0)),
        "infra_errors": int(sum(infra_error_counter.values())),
    }
    write_stage_manifest(
        manifest_path=config.manifests_dir / "doc_normalize.json",
        stage="doc_normalize",
        status="ok",
        metrics=metrics,
        artifacts=[
            config.doc_json_path,
            config.doc_substrate_path,
            config.doc_sentences_path,
            config.doc_sections_path,
            config.doc_references_path,
            config.doc_tables_path,
            config.doc_figures_path,
            config.doc_appendix_blocks_path,
            config.doc_routing_path,
            config.doc_ready_queue_path,
        ],
        started_at=started_at,
    )
    return metrics


__all__ = ["run_doc_normalize"]
