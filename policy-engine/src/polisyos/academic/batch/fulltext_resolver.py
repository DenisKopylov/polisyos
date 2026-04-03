"""Stage: resolve accessible paper text before LLM extraction."""

from __future__ import annotations

import asyncio
import json
import re
import socket
import time
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import aiohttp

from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.common.logger import get_logger
from polisyos.ir.analytics.literature import SourceBasis, TextQuality

logger = get_logger(__name__)

_SECTION_CUE_RE = re.compile(
    r"\b(abstract|introduction|background|methods?|results?|discussion|conclusion|references)\b",
    re.IGNORECASE,
)
_PLACEHOLDER_RE = re.compile(
    r"\b(redirecting|loading|just a moment|access denied|captcha|checking your browser|enable javascript)\b",
    re.IGNORECASE,
)
_FULLTEXT_HEADER_TRIM_RE = re.compile(r"(?is)\A.{0,4000}?\b(abstract|introduction|background)\b[:\s]")
_FULLTEXT_REFERENCE_TAIL_RE = re.compile(r"(?is)\b(references|bibliography|works cited)\b.{1200,}\Z")
_FULLTEXT_BOILERPLATE_RE = re.compile(
    r"(?is)"
    r"(cookie policy|cookie settings|cookie preferences|cookie consent|accept cookies|manage cookies|we use cookies|"
    r"all rights reserved|copyright \d{4}|download pdf|view abstract|view pdf|"
    r"sign in to access|institutional login|research output|explore all metrics|accesses|citations|altmetric|"
    r"doi:\s*\S+|doi\.org/\S+|https?://\S{20,}|"
    r"export citation|download citation|cite this article|"
    r"published by \w[\w\s]{2,30}press|elsevier|springer|wiley|taylor & francis|sage publications|"
    r"supplementary (?:materials?|data|information|files?)|"
    r"orcid\.org/\S+|"
    r"funding[:\s]+this (?:work|research|study) was (?:supported|funded)[\s\S]{0,200}?\.|"
    r"journal contributions|prodotti della ricerca|retrieved from https?://\S+|"
    r"prev\s+next|skip to main content|toggle navigation)"
)
_REPOSITORY_SHELL_CUE_RE = re.compile(
    r"(?i)\b("
    r"institutional research information system|catalogo dei prodotti della ricerca|"
    r"scheda breve|scheda completa|file in questo prodotto|visualizza/apri|"
    r"pubblicazioni consigliate|recommended publications|"
    r"utilizza questo identificativo|social impact|focus group iris|"
    r"home sfoglia|client feedback faq|all open access proceedings journals|"
    r"simulazione asn|prodotti della ricerca"
    r")\b"
)
_HTMLISH_PREFIXES = (
    b"<!doctype",
    b"<html",
    b"<head",
    b"<?xml",
    b"<!doc",
    b"\n\n\n\n<",
)
_NON_PDF_BINARY_PREFIXES = (
    b"\xff\xd8\xff",
    b"\x89png\r\n\x1a\n",
    b"gif87a",
    b"gif89a",
)


@dataclass(frozen=True)
class FullTextFetchAttempt:
    """Full text fetch attempt public type."""
    work_id: str
    attempt_kind: str
    candidate_priority: int
    candidate_url: str
    source_kind: str
    http_status: int
    fetch_error_class: str
    latency_ms: float
    redirected_to: str = ""
    discovered_pdf_count: int = 0
    discovered_canonical_count: int = 0
    text_chars: int = 0
    usable_text: bool = False
    final_for_work: bool = False


@dataclass(frozen=True)
class FullTextFetchResult:
    """Full text fetch result data model."""
    text: str
    source_kind: str
    source_url: str
    fetch_error_class: str = ""
    final_state: str = "abstract_fallback"
    attempts: tuple[FullTextFetchAttempt, ...] = ()
    metadata_cache_rows: tuple[dict[str, Any], ...] = ()
    resolved_cache_row: dict[str, Any] | None = None
    cache_hit: bool = False
    cache_key: str = ""


@dataclass(frozen=True)
class _URLCandidate:
    url: str
    priority: int
    expect_pdf: bool = False
    attempt_kind: str = "seed"
    source_kind: str = "seed_candidate"


def reconstruct_abstract(work: dict[str, Any]) -> str:
    """Reconstruct abstract helper."""
    direct = str(work.get("abstract") or "").strip()
    if direct:
        return direct
    index = work.get("abstract_inverted_index")
    if not isinstance(index, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for word, pos_list in index.items():
        if not isinstance(word, str) or not isinstance(pos_list, list):
            continue
        for pos in pos_list:
            if isinstance(pos, int):
                positions.append((pos, word))
    positions.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positions)


def _extract_html_tables(html: str) -> list[dict[str, Any]]:
    """Extract structured tables from HTML using lxml or BeautifulSoup."""
    tables: list[dict[str, Any]] = []
    try:
        from lxml.html import fromstring as _lxml_parse_html  # type: ignore[import-untyped]

        doc = _lxml_parse_html(html)
        for idx, table_elem in enumerate(doc.xpath("//table"), start=1):
            rows: list[list[str]] = []
            for tr in table_elem.xpath(".//tr"):
                cells = []
                for td in tr.xpath(".//td|.//th"):
                    cells.append(
                        re.sub(r"\s+", " ", (td.text_content() or "").strip())
                    )
                if cells:
                    rows.append(cells)
            if len(rows) < 2:
                continue
            headers = rows[0]
            md_lines = ["| " + " | ".join(headers) + " |"]
            md_lines.append("| " + " | ".join("---" for _ in headers) + " |")
            for row in rows[1:]:
                padded = row + [""] * max(0, len(headers) - len(row))
                md_lines.append("| " + " | ".join(padded[: len(headers)]) + " |")
            tables.append({
                "table_id": f"html_tbl_{idx:03d}",
                "label": f"table_{idx}",
                "text": "\n".join(md_lines),
                "headers": headers,
                "rows": rows[1:],
                "score": 0.7,
                "structure_source": "html_table",
            })
    except ImportError:
        try:
            from bs4 import BeautifulSoup  # type: ignore[import-untyped]

            soup = BeautifulSoup(html, "html.parser")
            for idx, table_elem in enumerate(soup.find_all("table"), start=1):
                rows: list[list[str]] = []  # type: ignore[no-redef]
                for tr in table_elem.find_all("tr"):
                    cells = [
                        re.sub(r"\s+", " ", (td.get_text() or "").strip())
                        for td in tr.find_all(["td", "th"])
                    ]
                    if cells:
                        rows.append(cells)
                if len(rows) < 2:
                    continue
                headers = rows[0]
                md_lines = ["| " + " | ".join(headers) + " |"]
                md_lines.append("| " + " | ".join("---" for _ in headers) + " |")
                for row in rows[1:]:
                    padded = row + [""] * max(0, len(headers) - len(row))
                    md_lines.append("| " + " | ".join(padded[: len(headers)]) + " |")
                tables.append({
                    "table_id": f"html_tbl_{idx:03d}",
                    "label": f"table_{idx}",
                    "text": "\n".join(md_lines),
                    "headers": headers,
                    "rows": rows[1:],
                    "score": 0.7,
                    "structure_source": "html_table",
                })
        except ImportError:
            pass
    except Exception as exc:
        logger.debug("HTML table extraction failed: {}", exc)
    return tables


def _extract_html_text(html: str) -> str:
    try:
        import html2text  # type: ignore[import-untyped]

        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        h.body_width = 0
        return h.handle(html).strip()
    except ImportError:
        pass
    cleaned = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    cleaned = re.sub(r"(?is)<style.*?>.*?</style>", " ", cleaned)
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


_DEFAULT_MAX_PDF_PAGES: int = 50


def _extract_pdf_text(raw_bytes: bytes, *, max_pages: int = 0) -> str:
    if max_pages <= 0:
        max_pages = _DEFAULT_MAX_PDF_PAGES

    # Try PyMuPDF first (better text extraction quality)
    try:
        import fitz  # type: ignore[import-untyped]  # pymupdf

        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        total_pages = len(doc)
        texts: list[str] = []
        for page_num in range(min(total_pages, max_pages)):
            page = doc[page_num]
            texts.append(page.get_text("text") or "")
        doc.close()
        if total_pages > max_pages:
            logger.warning(
                "PDF has {} pages, truncated to {} — data loss possible",
                total_pages, max_pages,
            )
        result = "\n".join(texts).strip()
        if result:
            return result
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("PyMuPDF extraction failed, falling back to pypdf: {}", exc)

    # Fallback to pypdf
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except (ImportError, ModuleNotFoundError):
        return ""
    try:
        import io

        reader = PdfReader(io.BytesIO(raw_bytes))
        total_pages = len(reader.pages)
        texts_fallback: list[str] = []
        for page in reader.pages[:max_pages]:
            texts_fallback.append(str(page.extract_text() or ""))
        if total_pages > max_pages:
            logger.warning(
                "PDF has {} pages, truncated to {} — data loss possible",
                total_pages, max_pages,
            )
        return "\n".join(texts_fallback).strip()
    except (OSError, TypeError, ValueError) as exc:
        logger.debug("PDF text extraction failed: {}", exc)
        return ""


def _sniff_pdf_payload(raw_bytes: bytes, *, content_type: str) -> tuple[bool, str]:
    head = bytes(raw_bytes[:64]).lstrip()
    lower_head = head.lower()
    lowered_type = str(content_type or "").lower()
    if head.startswith(b"%PDF-"):
        return True, "pdf"
    if any(lower_head.startswith(prefix) for prefix in _HTMLISH_PREFIXES):
        return False, "html_disguised_as_pdf"
    if any(lower_head.startswith(prefix) for prefix in _NON_PDF_BINARY_PREFIXES):
        return False, "binary_disguised_as_pdf"
    if any(token in lowered_type for token in ("text/html", "xml", "application/json")):
        return False, "html_disguised_as_pdf"
    if lowered_type.startswith("image/"):
        return False, "binary_disguised_as_pdf"
    return True, "unknown_pdf_payload"


def _sanitize_fulltext_text(text: str) -> tuple[str, bool]:
    normalized = str(text or "").strip()
    if not normalized:
        return "", False

    cleaned = normalized
    changed = False

    header_match = _FULLTEXT_HEADER_TRIM_RE.search(cleaned)
    if header_match and header_match.start() > 0:
        cleaned = cleaned[header_match.start():]
        changed = True

    tail_match = _FULLTEXT_REFERENCE_TAIL_RE.search(cleaned)
    if tail_match:
        cleaned = cleaned[: tail_match.start()].strip()
        changed = True

    stripped = _FULLTEXT_BOILERPLATE_RE.sub(" ", cleaned)
    if stripped != cleaned:
        cleaned = stripped
        changed = True

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, changed


def _text_quality_for(source_kind: str, text: str) -> TextQuality:
    if source_kind == "abstract_fallback":
        return TextQuality.ABSTRACT_ONLY
    if len(text) < 800:
        return TextQuality.DEGRADED
    return TextQuality.EXTRACTED_FULLTEXT


def _is_fetchable_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def _is_probable_pdf_url(url: str) -> bool:
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    return path.endswith(".pdf") or "/pdf" in path


def _looks_like_redirect_placeholder(text: str) -> bool:
    normalized = (text or "").strip().lower()
    return normalized in {
        "redirecting",
        "redirecting...",
        "loading",
        "loading...",
        "access denied",
        "just a moment",
    } or normalized.startswith("redirecting ")


def _looks_like_fake_fulltext(text: str) -> bool:
    normalized = (text or "").strip()
    if not normalized:
        return False
    if _looks_like_redirect_placeholder(normalized):
        return True
    if _PLACEHOLDER_RE.search(normalized):
        return True
    return False


def _looks_like_repository_shell(text: str) -> bool:
    normalized = (text or "").strip()
    if not normalized:
        return False
    cues = {match.group(0).lower() for match in _REPOSITORY_SHELL_CUE_RE.finditer(normalized)}
    return len(cues) >= 2


def _looks_like_usable_fulltext(
    text: str,
    *,
    min_usable_chars: int = 1500,
    min_soft_usable_chars: int = 700,
    soft_usable_requires_section_cues: bool = True,
) -> bool:
    normalized = (text or "").strip()
    if not normalized or _looks_like_fake_fulltext(normalized):
        return False
    if len(normalized) >= min_usable_chars:
        return True
    sentence_count = len(re.findall(r"[.!?](?:\s|$)", normalized))
    has_section_cues = bool(_SECTION_CUE_RE.search(normalized))
    if len(normalized) < min_soft_usable_chars:
        return False
    if sentence_count < 6:
        return False
    if soft_usable_requires_section_cues:
        return has_section_cues
    return has_section_cues or sentence_count >= 10


def _classify_text_state(
    text: str,
    *,
    min_usable_chars: int,
    min_soft_usable_chars: int,
    soft_usable_requires_section_cues: bool,
) -> tuple[bool, str]:
    normalized = (text or "").strip()
    if not normalized:
        return False, "degraded_text"
    if _looks_like_fake_fulltext(normalized):
        return False, "fake_fulltext"
    if len(normalized) >= min_usable_chars:
        return True, "usable_fulltext_strong"
    if _looks_like_usable_fulltext(
        normalized,
        min_usable_chars=min_usable_chars,
        min_soft_usable_chars=min_soft_usable_chars,
        soft_usable_requires_section_cues=soft_usable_requires_section_cues,
    ):
        return True, "usable_fulltext_soft"
    return False, "degraded_text"


def _extract_redirect_targets(html: str, base_url: str) -> list[str]:
    patterns = (
        re.compile(r'''<meta[^>]+http-equiv=["']?refresh["']?[^>]+content=["'][^"'>]*url=([^"'>\s]+)''', re.IGNORECASE),
        re.compile(r'''window\.location(?:\.href)?\s*=\s*["']([^"']+)["']''', re.IGNORECASE),
        re.compile(r'''location\.replace\(\s*["']([^"']+)["']\s*\)''', re.IGNORECASE),
        re.compile(r'''location\.assign\(\s*["']([^"']+)["']\s*\)''', re.IGNORECASE),
        re.compile(r'''<a[^>]+href=["']([^"']+)["'][^>]*>\s*(?:continue|here|full text|article)\s*</a>''', re.IGNORECASE),
    )
    targets: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(html or ""):
            target = urljoin(base_url, match.group(1).strip())
            if _is_fetchable_url(target) and target not in targets:
                targets.append(target)
    return targets


def _extract_pdf_targets(html: str, base_url: str) -> list[str]:
    patterns = (
        re.compile(r'''<meta[^>]+name=["']citation_pdf_url["'][^>]+content=["']([^"']+)["']''', re.IGNORECASE),
        re.compile(r'''<meta[^>]+property=["']og:pdf["'][^>]+content=["']([^"']+)["']''', re.IGNORECASE),
        re.compile(r'''<link[^>]+type=["']application/pdf["'][^>]+href=["']([^"']+)["']''', re.IGNORECASE),
        re.compile(r'''<a[^>]+href=["']([^"']+\.pdf(?:\?[^"']*)?)["']''', re.IGNORECASE),
        re.compile(r'''<a[^>]+href=["']([^"']+)["'][^>]*>\s*(?:pdf|download pdf|view pdf|full text pdf)\s*</a>''', re.IGNORECASE),
    )
    targets: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(html or ""):
            target = urljoin(base_url, match.group(1).strip())
            if _is_fetchable_url(target) and target not in targets:
                targets.append(target)
    return targets


def _extract_canonical_targets(html: str, base_url: str) -> list[str]:
    patterns = (
        re.compile(r'''<link[^>]+rel=["']canonical["'][^>]+href=["']([^"']+)["']''', re.IGNORECASE),
        re.compile(r'''<meta[^>]+property=["']og:url["'][^>]+content=["']([^"']+)["']''', re.IGNORECASE),
    )
    targets: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(html or ""):
            target = urljoin(base_url, match.group(1).strip())
            if _is_fetchable_url(target) and target not in targets:
                targets.append(target)
    return targets


def _insert_candidate(
    pending: list[_URLCandidate],
    queued_urls: set[str],
    *,
    url: str,
    priority: int,
    expect_pdf: bool,
    attempt_kind: str,
    source_kind: str,
    max_candidates: int,
) -> None:
    if not _is_fetchable_url(url) or url in queued_urls:
        return
    if max_candidates > 0 and len(queued_urls) >= max_candidates:
        worst_priority = max((candidate.priority for candidate in pending), default=priority)
        if priority >= worst_priority:
            return
    queued_urls.add(url)
    candidate = _URLCandidate(
        url=url,
        priority=priority,
        expect_pdf=expect_pdf,
        attempt_kind=attempt_kind,
        source_kind=source_kind,
    )
    insert_at = len(pending)
    for idx, existing in enumerate(pending):
        if priority < existing.priority:
            insert_at = idx
            break
    pending.insert(insert_at, candidate)
    if max_candidates > 0 and len(pending) > max_candidates:
        dropped = pending.pop()
        queued_urls.discard(dropped.url)


def _normalize_doi(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/", "doi:"):
        if lowered.startswith(prefix):
            raw = raw[len(prefix):].strip()
            break
    return raw.strip().strip("/")


def _doi_url(doi: str) -> str:
    return f"https://doi.org/{quote(doi, safe='')}"


def _cache_keys_for_work(work: dict[str, Any]) -> list[str]:
    ids = work.get("ids") if isinstance(work.get("ids"), dict) else {}
    doi = _normalize_doi(str(work.get("doi") or ids.get("doi") or ""))
    work_id = str(work.get("id") or "").strip()
    keys: list[str] = []
    if doi:
        keys.append(f"doi:{doi.lower()}")
    if work_id:
        keys.append(f"work:{work_id}")
    return keys


def _is_cache_row_fresh(row: dict[str, Any], *, ttl_days: int) -> bool:
    resolved_at = str(row.get("resolved_at") or "").strip()
    if not resolved_at:
        return False
    try:
        parsed = datetime.fromisoformat(resolved_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed >= datetime.now(UTC) - timedelta(days=max(1, int(ttl_days)))


def _store_resolved_cache_row(cache: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
    for key in row.get("lookup_keys", []):
        if isinstance(key, str) and key:
            cache[key] = row
    cache_key = str(row.get("cache_key") or "").strip()
    if cache_key:
        cache[cache_key] = row


def _cache_attempt(work_id: str, row: dict[str, Any]) -> FullTextFetchAttempt:
    return FullTextFetchAttempt(
        work_id=work_id,
        attempt_kind="shared_cache",
        candidate_priority=-1,
        candidate_url=str(row.get("source_url") or ""),
        source_kind=f"{str(row.get('source_kind') or 'unknown')}_cache_hit",
        http_status=200,
        fetch_error_class="",
        latency_ms=0.0,
        text_chars=len(str(row.get("text") or "").strip()),
        usable_text=str(row.get("source_kind") or "") != "abstract_fallback",
        final_for_work=True,
    )


def _build_resolved_cache_row(work: dict[str, Any], result: FullTextFetchResult) -> dict[str, Any]:
    lookup_keys = _cache_keys_for_work(work)
    cache_key = lookup_keys[0] if lookup_keys else ""
    ids = work.get("ids") if isinstance(work.get("ids"), dict) else {}
    return {
        "cache_key": cache_key,
        "lookup_keys": lookup_keys,
        "work_id": str(work.get("id") or ""),
        "doi": _normalize_doi(str(work.get("doi") or ids.get("doi") or "")),
        "resolved_at": datetime.now(UTC).isoformat(),
        "source_kind": result.source_kind,
        "source_url": result.source_url,
        "fetch_error_class": result.fetch_error_class,
        "final_state": result.final_state,
        "text_quality": _text_quality_for(result.source_kind, result.text).value,
        "text": result.text,
    }


def load_resolved_fulltext_cache(
    path: Path,
    *,
    ttl_days: int,
) -> dict[str, dict[str, Any]]:
    """Load resolved fulltext cache."""
    cache: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return cache
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            if not _is_cache_row_fresh(row, ttl_days=ttl_days):
                continue
            _store_resolved_cache_row(cache, row)
    return cache


def _candidate_urls(work: dict[str, Any], *, max_candidates: int) -> list[_URLCandidate]:
    open_access = work.get("open_access") if isinstance(work.get("open_access"), dict) else {}
    best_oa = work.get("best_oa_location") if isinstance(work.get("best_oa_location"), dict) else {}
    primary_location = work.get("primary_location") if isinstance(work.get("primary_location"), dict) else {}
    locations = work.get("locations") if isinstance(work.get("locations"), list) else []
    ids = work.get("ids") if isinstance(work.get("ids"), dict) else {}

    pending: list[_URLCandidate] = []
    queued_urls: set[str] = set()

    def add(
        url: str | None,
        *,
        priority: int,
        source_kind: str,
        attempt_kind: str = "seed",
        expect_pdf: bool | None = None,
    ) -> None:
        text = str(url or "").strip()
        if not text:
            return
        pdfish = _is_probable_pdf_url(text)
        _insert_candidate(
            pending,
            queued_urls,
            url=text,
            priority=priority,
            expect_pdf=pdfish if expect_pdf is None else expect_pdf,
            attempt_kind=attempt_kind,
            source_kind=source_kind,
            max_candidates=max_candidates,
        )

    add(best_oa.get("pdf_url"), priority=0, source_kind="openalex_pdf", expect_pdf=True)
    add(open_access.get("oa_url"), priority=1, source_kind="openalex_oa_url")
    add(best_oa.get("landing_page_url"), priority=2, source_kind="openalex_landing_page")
    add(primary_location.get("pdf_url"), priority=3, source_kind="openalex_primary_pdf", expect_pdf=True)
    add(primary_location.get("landing_page_url"), priority=4, source_kind="openalex_primary_landing")

    for idx, location in enumerate(locations):
        if not isinstance(location, dict):
            continue
        add(location.get("pdf_url"), priority=10 + idx, source_kind="openalex_location_pdf", expect_pdf=True)
        add(location.get("landing_page_url"), priority=40 + idx, source_kind="openalex_location_landing")

    doi = _normalize_doi(str(work.get("doi") or ids.get("doi") or ""))
    if doi:
        add(_doi_url(doi), priority=90, source_kind="doi_redirect")
    return pending


def _has_any_candidate_url_text(work: dict[str, Any]) -> bool:
    open_access = work.get("open_access") if isinstance(work.get("open_access"), dict) else {}
    best_oa = work.get("best_oa_location") if isinstance(work.get("best_oa_location"), dict) else {}
    primary_location = work.get("primary_location") if isinstance(work.get("primary_location"), dict) else {}
    locations = work.get("locations") if isinstance(work.get("locations"), list) else []
    ids = work.get("ids") if isinstance(work.get("ids"), dict) else {}
    direct_candidates = [
        open_access.get("oa_url"),
        best_oa.get("pdf_url"),
        best_oa.get("landing_page_url"),
        primary_location.get("pdf_url"),
        primary_location.get("landing_page_url"),
        work.get("doi"),
        ids.get("doi"),
    ]
    if any(str(candidate or "").strip() for candidate in direct_candidates):
        return True
    for location in locations:
        if not isinstance(location, dict):
            continue
        if any(str(location.get(key) or "").strip() for key in ("pdf_url", "landing_page_url")):
            return True
    return False


def _classify_fetch_error(exc: Exception) -> str:
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"
    if isinstance(exc, aiohttp.InvalidURL):
        return "invalid_url"
    if isinstance(exc, socket.gaierror):
        return "dns_error"
    if isinstance(exc, aiohttp.ClientConnectorError):
        os_error = getattr(exc, "os_error", None)
        if isinstance(os_error, socket.gaierror):
            return "dns_error"
        return "client_connector_error"
    return "fetch_error"


def _metadata_cache_row_to_candidates(row: dict[str, Any]) -> list[_URLCandidate]:
    candidates: list[_URLCandidate] = []
    for item in row.get("candidates", []):
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        candidates.append(
            _URLCandidate(
                url=url,
                priority=int(item.get("priority", 999)),
                expect_pdf=bool(item.get("expect_pdf", False)),
                attempt_kind="metadata",
                source_kind=str(item.get("source_kind") or f"metadata_{row.get('resolver', 'unknown')}") or "metadata_candidate",
            )
        )
    return candidates


def _metadata_cache_row_to_attempt(work_id: str, row: dict[str, Any], *, cache_hit: bool) -> FullTextFetchAttempt:
    candidates = row.get("candidates", []) if isinstance(row.get("candidates"), list) else []
    return FullTextFetchAttempt(
        work_id=work_id,
        attempt_kind="metadata",
        candidate_priority=min((int(item.get("priority", 999)) for item in candidates if isinstance(item, dict)), default=999),
        candidate_url=str(row.get("resolver_url") or ""),
        source_kind=f"metadata_{row.get('resolver', 'unknown')}{'_cache_hit' if cache_hit else ''}",
        http_status=int(row.get("http_status") or 0),
        fetch_error_class=str(row.get("fetch_error_class") or ""),
        latency_ms=float(row.get("latency_ms") or 0.0),
        discovered_pdf_count=int(row.get("discovered_pdf_count") or 0),
        discovered_canonical_count=int(row.get("discovered_canonical_count") or 0),
        text_chars=0,
        usable_text=False,
        final_for_work=False,
    )


async def _query_unpaywall(
    doi: str,
    *,
    work_id: str,
    email: str,
    timeout_seconds: int,
    session: aiohttp.ClientSession,
) -> dict[str, Any]:
    endpoint = f"https://api.unpaywall.org/v2/{quote(doi, safe='')}?email={quote(email, safe='@._+-')}"
    started = time.monotonic()
    status = 0
    error_class = ""
    candidates: list[dict[str, Any]] = []
    try:
        async with asyncio.timeout(timeout_seconds):
            async with session.get(endpoint) as resp:
                status = int(resp.status)
                if status == 200:
                    payload = await resp.json(content_type=None)
                    best = payload.get("best_oa_location") if isinstance(payload, dict) and isinstance(payload.get("best_oa_location"), dict) else {}
                    locations = payload.get("oa_locations") if isinstance(payload, dict) and isinstance(payload.get("oa_locations"), list) else []

                    def add(url: str | None, *, priority: int, source_kind: str, expect_pdf: bool) -> None:
                        text = str(url or "").strip()
                        if not text:
                            return
                        candidates.append(
                            {
                                "url": text,
                                "priority": priority,
                                "expect_pdf": expect_pdf,
                                "source_kind": source_kind,
                            }
                        )

                    add(best.get("url_for_pdf"), priority=5, source_kind="metadata_unpaywall_pdf", expect_pdf=True)
                    add(best.get("url_for_landing_page") or best.get("url"), priority=6, source_kind="metadata_unpaywall_landing", expect_pdf=False)
                    for idx, location in enumerate(locations[:10]):
                        if not isinstance(location, dict):
                            continue
                        add(location.get("url_for_pdf"), priority=20 + idx, source_kind="metadata_unpaywall_pdf", expect_pdf=True)
                        add(
                            location.get("url_for_landing_page") or location.get("url"),
                            priority=30 + idx,
                            source_kind="metadata_unpaywall_landing",
                            expect_pdf=False,
                        )
                    if not candidates:
                        error_class = "metadata_no_result"
                elif status == 404:
                    error_class = "metadata_no_result"
                else:
                    error_class = f"http_{status}"
    except asyncio.TimeoutError:
        error_class = "metadata_timeout"
    except Exception as exc:
        error_class = _classify_fetch_error(exc)

    return {
        "cache_key": f"unpaywall:{doi.lower()}",
        "resolver": "unpaywall",
        "resolver_url": endpoint,
        "doi": doi,
        "work_id": work_id,
        "queried_at": datetime.now(UTC).isoformat(),
        "http_status": status,
        "fetch_error_class": error_class,
        "latency_ms": round((time.monotonic() - started) * 1000.0, 3),
        "discovered_pdf_count": sum(1 for item in candidates if bool(item.get("expect_pdf"))),
        "discovered_canonical_count": sum(1 for item in candidates if not bool(item.get("expect_pdf"))),
        "candidates": candidates,
    }


async def _query_crossref(
    doi: str,
    *,
    work_id: str,
    timeout_seconds: int,
    session: aiohttp.ClientSession,
) -> dict[str, Any]:
    endpoint = f"https://api.crossref.org/works/{quote(doi, safe='')}"
    started = time.monotonic()
    status = 0
    error_class = ""
    candidates: list[dict[str, Any]] = []
    try:
        async with asyncio.timeout(timeout_seconds):
            async with session.get(endpoint) as resp:
                status = int(resp.status)
                if status == 200:
                    payload = await resp.json(content_type=None)
                    message = payload.get("message") if isinstance(payload, dict) and isinstance(payload.get("message"), dict) else {}
                    link_items = message.get("link") if isinstance(message.get("link"), list) else []
                    landing_candidates = [message.get("URL")]
                    resource = message.get("resource") if isinstance(message.get("resource"), dict) else {}
                    primary = resource.get("primary") if isinstance(resource.get("primary"), dict) else {}
                    landing_candidates.append(primary.get("URL"))
                    for idx, url in enumerate(landing_candidates):
                        text = str(url or "").strip()
                        if text:
                            candidates.append(
                                {
                                    "url": text,
                                    "priority": 7 + idx,
                                    "expect_pdf": _is_probable_pdf_url(text),
                                    "source_kind": "metadata_crossref_landing" if not _is_probable_pdf_url(text) else "metadata_crossref_pdf",
                                }
                            )
                    for idx, item in enumerate(link_items[:10]):
                        if not isinstance(item, dict):
                            continue
                        text = str(item.get("URL") or item.get("url") or "").strip()
                        if not text:
                            continue
                        content_type = str(item.get("content-type") or item.get("content_type") or "").lower()
                        expect_pdf = "pdf" in content_type or _is_probable_pdf_url(text)
                        candidates.append(
                            {
                                "url": text,
                                "priority": 12 + idx,
                                "expect_pdf": expect_pdf,
                                "source_kind": "metadata_crossref_pdf" if expect_pdf else "metadata_crossref_landing",
                            }
                        )
                    if not candidates:
                        error_class = "metadata_no_result"
                elif status == 404:
                    error_class = "metadata_no_result"
                else:
                    error_class = f"http_{status}"
    except asyncio.TimeoutError:
        error_class = "metadata_timeout"
    except Exception as exc:
        error_class = _classify_fetch_error(exc)

    return {
        "cache_key": f"crossref:{doi.lower()}",
        "resolver": "crossref",
        "resolver_url": endpoint,
        "doi": doi,
        "work_id": work_id,
        "queried_at": datetime.now(UTC).isoformat(),
        "http_status": status,
        "fetch_error_class": error_class,
        "latency_ms": round((time.monotonic() - started) * 1000.0, 3),
        "discovered_pdf_count": sum(1 for item in candidates if bool(item.get("expect_pdf"))),
        "discovered_canonical_count": sum(1 for item in candidates if not bool(item.get("expect_pdf"))),
        "candidates": candidates,
    }


async def _query_semantic_scholar(
    doi: str,
    *,
    work_id: str,
    timeout_seconds: int,
    api_key: str,
    session: aiohttp.ClientSession,
) -> dict[str, Any]:
    endpoint = (
        "https://api.semanticscholar.org/graph/v1/paper/"
        f"DOI:{quote(doi, safe='')}?fields=openAccessPdf,url,externalIds"
    )
    started = time.monotonic()
    status = 0
    error_class = ""
    candidates: list[dict[str, Any]] = []
    headers = {"x-api-key": api_key} if api_key else {}
    try:
        async with asyncio.timeout(timeout_seconds):
            async with session.get(endpoint, headers=headers) as resp:
                status = int(resp.status)
                if status == 200:
                    payload = await resp.json(content_type=None)
                    open_access_pdf = payload.get("openAccessPdf") if isinstance(payload, dict) and isinstance(payload.get("openAccessPdf"), dict) else {}
                    pdf_url = str(open_access_pdf.get("url") or "").strip()
                    paper_url = str(payload.get("url") or "").strip() if isinstance(payload, dict) else ""
                    if pdf_url:
                        candidates.append(
                            {
                                "url": pdf_url,
                                "priority": 8,
                                "expect_pdf": True,
                                "source_kind": "metadata_semanticscholar_pdf",
                            }
                        )
                    if paper_url:
                        candidates.append(
                            {
                                "url": paper_url,
                                "priority": 9,
                                "expect_pdf": _is_probable_pdf_url(paper_url),
                                "source_kind": "metadata_semanticscholar_landing",
                            }
                        )
                    if not candidates:
                        error_class = "metadata_no_result"
                elif status == 404:
                    error_class = "metadata_no_result"
                else:
                    error_class = f"http_{status}"
    except asyncio.TimeoutError:
        error_class = "metadata_timeout"
    except Exception as exc:
        error_class = _classify_fetch_error(exc)

    return {
        "cache_key": f"semanticscholar:{doi.lower()}",
        "resolver": "semanticscholar",
        "resolver_url": endpoint,
        "doi": doi,
        "work_id": work_id,
        "queried_at": datetime.now(UTC).isoformat(),
        "http_status": status,
        "fetch_error_class": error_class,
        "latency_ms": round((time.monotonic() - started) * 1000.0, 3),
        "discovered_pdf_count": sum(1 for item in candidates if bool(item.get("expect_pdf"))),
        "discovered_canonical_count": sum(1 for item in candidates if not bool(item.get("expect_pdf"))),
        "candidates": candidates,
    }


async def _resolve_metadata_candidates(
    work: dict[str, Any],
    *,
    metadata_enabled: bool,
    resolver_order: tuple[str, ...],
    unpaywall_email: str,
    semantic_scholar_api_key: str,
    timeout_seconds: int,
    session: aiohttp.ClientSession,
    metadata_cache: dict[str, dict[str, Any]] | None,
) -> tuple[list[_URLCandidate], list[FullTextFetchAttempt], list[dict[str, Any]]]:
    if not metadata_enabled:
        return [], [], []
    ids = work.get("ids") if isinstance(work.get("ids"), dict) else {}
    doi = _normalize_doi(str(work.get("doi") or ids.get("doi") or ""))
    if not doi:
        return [], [], []

    cache = metadata_cache if metadata_cache is not None else {}
    attempts: list[FullTextFetchAttempt] = []
    candidates: list[_URLCandidate] = []
    rows_to_append: list[dict[str, Any]] = []
    work_id = str(work.get("id") or "")

    async def resolve_row(resolver_name: str) -> dict[str, Any]:
        cache_key = f"{resolver_name}:{doi.lower()}"
        if cache_key in cache:
            row = cache[cache_key]
            attempts.append(_metadata_cache_row_to_attempt(work_id, row, cache_hit=True))
            candidates.extend(_metadata_cache_row_to_candidates(row))
            return row
        if resolver_name == "unpaywall":
            row = await _query_unpaywall(
                doi,
                work_id=work_id,
                email=unpaywall_email,
                timeout_seconds=timeout_seconds,
                session=session,
            )
        elif resolver_name == "semanticscholar":
            row = await _query_semantic_scholar(
                doi,
                work_id=work_id,
                timeout_seconds=timeout_seconds,
                api_key=semantic_scholar_api_key,
                session=session,
            )
        else:
            row = await _query_crossref(
                doi,
                work_id=work_id,
                timeout_seconds=timeout_seconds,
                session=session,
            )
        cache[cache_key] = row
        rows_to_append.append(row)
        attempts.append(_metadata_cache_row_to_attempt(work_id, row, cache_hit=False))
        candidates.extend(_metadata_cache_row_to_candidates(row))
        return row

    for resolver_name in resolver_order:
        normalized = str(resolver_name or "").strip().lower()
        if normalized not in {"unpaywall", "crossref", "semanticscholar"}:
            continue
        if normalized == "unpaywall" and not unpaywall_email:
            continue
        if normalized == "semanticscholar" and not semantic_scholar_api_key:
            continue
        await resolve_row(normalized)
    return candidates, attempts, rows_to_append


async def _fetch_v3_legacy(
    work: dict[str, Any],
    *,
    timeout_seconds: int | None,
    connect_timeout_seconds: int | None,
    read_timeout_seconds: int | None,
    total_timeout_seconds: int | None,
    session: aiohttp.ClientSession | None,
) -> FullTextFetchResult:
    pending_urls = _candidate_urls(work, max_candidates=20)
    if not pending_urls:
        return FullTextFetchResult(
            text=reconstruct_abstract(work),
            source_kind="abstract_fallback",
            source_url="",
            fetch_error_class="invalid_url" if _has_any_candidate_url_text(work) else "no_url_candidates",
            final_state="abstract_fallback",
        )

    total_timeout = total_timeout_seconds if total_timeout_seconds is not None else timeout_seconds
    timeout = aiohttp.ClientTimeout(
        total=max(3, int(total_timeout or 20)),
        connect=max(1, int(connect_timeout_seconds or 10)),
        sock_read=max(1, int(read_timeout_seconds or max(3, int((total_timeout or timeout_seconds or 20))))),
    )
    headers = {"User-Agent": "PolicyOS/1.0 (+academic extraction)"}
    owns_session = session is None
    local_session = session or aiohttp.ClientSession(timeout=timeout, headers=headers)
    last_error_class = ""
    seen_urls: set[str] = set()
    queued_urls: set[str] = {candidate.url for candidate in pending_urls}
    try:
        while pending_urls:
            candidate = pending_urls.pop(0)
            url = candidate.url
            if url in seen_urls:
                continue
            seen_urls.add(url)
            if not _is_fetchable_url(url):
                last_error_class = "invalid_url"
                continue
            try:
                async with local_session.get(url) as resp:
                    if resp.status != 200:
                        last_error_class = f"http_{resp.status}"
                        continue
                    content_type = str(resp.headers.get("Content-Type") or "").lower()
                    raw_bytes = await resp.read()
                    final_url = str(getattr(resp, "url", url) or url)
                    if "pdf" in content_type or candidate.expect_pdf or url.lower().endswith(".pdf"):
                        looks_pdf, sniff_state = _sniff_pdf_payload(raw_bytes, content_type=content_type)
                        if not looks_pdf:
                            last_error_class = sniff_state
                            continue
                        text, _ = _sanitize_fulltext_text(_extract_pdf_text(raw_bytes))
                        if text.strip():
                            return FullTextFetchResult(
                                text=text,
                                source_kind="fulltext_pdf",
                                source_url=final_url,
                                fetch_error_class="",
                                final_state="usable_fulltext",
                            )
                        last_error_class = "pdf_parse_failed"
                        continue
                    html = raw_bytes.decode("utf-8", errors="ignore")
                    pdf_targets = _extract_pdf_targets(html, final_url)
                    repository_shell = False
                    for target in pdf_targets:
                        _insert_candidate(
                            pending_urls,
                            queued_urls,
                            url=target,
                            priority=max(0, candidate.priority - 5),
                            expect_pdf=True,
                            attempt_kind="discovered",
                            source_kind="publisher_pdf",
                            max_candidates=20,
                        )
                    for target in _extract_redirect_targets(html, final_url):
                        _insert_candidate(
                            pending_urls,
                            queued_urls,
                            url=target,
                            priority=candidate.priority + 1,
                            expect_pdf=_is_probable_pdf_url(target),
                            attempt_kind="discovered",
                            source_kind="publisher_redirect",
                            max_candidates=20,
                        )
                    for target in _extract_canonical_targets(html, final_url):
                        if target == final_url:
                            continue
                        _insert_candidate(
                            pending_urls,
                            queued_urls,
                            url=target,
                            priority=candidate.priority + 2,
                            expect_pdf=_is_probable_pdf_url(target),
                            attempt_kind="discovered",
                            source_kind="publisher_canonical",
                            max_candidates=20,
                        )
                    text, _ = _sanitize_fulltext_text(_extract_html_text(html))
                    repository_shell = bool(pdf_targets) and _looks_like_repository_shell(text)
                    if _looks_like_redirect_placeholder(text):
                        last_error_class = "redirect_placeholder"
                        continue
                    if repository_shell:
                        last_error_class = "repository_shell_with_pdf"
                        continue
                    if text.strip():
                        if pdf_targets and not _looks_like_usable_fulltext(text):
                            last_error_class = "landing_page_without_pdf"
                            continue
                        return FullTextFetchResult(
                            text=text,
                            source_kind="fulltext_html",
                            source_url=final_url,
                            fetch_error_class="",
                            final_state="usable_fulltext",
                        )
                    last_error_class = "landing_page_without_pdf"
            except Exception as exc:
                last_error_class = _classify_fetch_error(exc)
                continue
    finally:
        if owns_session:
            await local_session.close()

    return FullTextFetchResult(
        text=reconstruct_abstract(work),
        source_kind="abstract_fallback",
        source_url="",
        fetch_error_class=last_error_class,
        final_state="abstract_fallback",
    )


async def _fetch_v7_http_metadata(
    work: dict[str, Any],
    *,
    timeout_seconds: int | None,
    connect_timeout_seconds: int | None,
    read_timeout_seconds: int | None,
    total_timeout_seconds: int | None,
    session: aiohttp.ClientSession | None,
    metadata_enabled: bool,
    metadata_resolver_order: tuple[str, ...],
    unpaywall_email: str,
    semantic_scholar_api_key: str,
    metadata_timeout_seconds: int,
    max_candidate_urls_per_work: int,
    min_usable_chars: int,
    min_soft_usable_chars: int,
    soft_usable_requires_section_cues: bool,
    metadata_cache: dict[str, dict[str, Any]] | None,
) -> FullTextFetchResult:
    work_id = str(work.get("id") or "")
    pending_urls = _candidate_urls(work, max_candidates=max_candidate_urls_per_work)
    total_timeout = total_timeout_seconds if total_timeout_seconds is not None else timeout_seconds
    timeout = aiohttp.ClientTimeout(
        total=max(3, int(total_timeout or 20)),
        connect=max(1, int(connect_timeout_seconds or 10)),
        sock_read=max(1, int(read_timeout_seconds or max(3, int((total_timeout or timeout_seconds or 20))))),
    )
    headers = {"User-Agent": "PolicyOS/1.0 (+academic extraction)"}
    owns_session = session is None
    local_session = session or aiohttp.ClientSession(timeout=timeout, headers=headers)
    attempts: list[FullTextFetchAttempt] = []
    last_error_class = ""
    seen_urls: set[str] = set()
    queued_urls: set[str] = {candidate.url for candidate in pending_urls}
    metadata_cache_rows: list[dict[str, Any]] = []

    try:
        metadata_candidates, metadata_attempts, new_cache_rows = await _resolve_metadata_candidates(
            work,
            metadata_enabled=metadata_enabled,
            resolver_order=metadata_resolver_order,
            unpaywall_email=unpaywall_email,
            semantic_scholar_api_key=semantic_scholar_api_key,
            timeout_seconds=metadata_timeout_seconds,
            session=local_session,
            metadata_cache=metadata_cache,
        )
        attempts.extend(metadata_attempts)
        metadata_cache_rows.extend(new_cache_rows)
        for candidate in metadata_candidates:
            _insert_candidate(
                pending_urls,
                queued_urls,
                url=candidate.url,
                priority=candidate.priority,
                expect_pdf=candidate.expect_pdf,
                attempt_kind=candidate.attempt_kind,
                source_kind=candidate.source_kind,
                max_candidates=max_candidate_urls_per_work,
            )

        if not pending_urls:
            fetch_error = "invalid_url" if _has_any_candidate_url_text(work) else "no_url_candidates"
            return FullTextFetchResult(
                text=reconstruct_abstract(work),
                source_kind="abstract_fallback",
                source_url="",
                fetch_error_class=fetch_error,
                final_state="abstract_fallback",
                attempts=tuple(attempts),
                metadata_cache_rows=tuple(metadata_cache_rows),
            )

        while pending_urls:
            candidate = pending_urls.pop(0)
            url = candidate.url
            if url in seen_urls:
                continue
            seen_urls.add(url)
            if not _is_fetchable_url(url):
                last_error_class = "invalid_url"
                attempts.append(
                    FullTextFetchAttempt(
                        work_id=work_id,
                        attempt_kind=candidate.attempt_kind,
                        candidate_priority=candidate.priority,
                        candidate_url=url,
                        source_kind=candidate.source_kind,
                        http_status=0,
                        fetch_error_class="invalid_url",
                        latency_ms=0.0,
                    )
                )
                continue
            started = time.monotonic()
            try:
                async with local_session.get(url) as resp:
                    http_status = int(resp.status)
                    final_url = str(getattr(resp, "url", url) or url)
                    redirected_to = final_url if final_url != url else ""
                    if http_status != 200:
                        fetch_error_class = "publisher_blocked_403" if http_status == 403 else f"http_{http_status}"
                        last_error_class = fetch_error_class
                        attempts.append(
                            FullTextFetchAttempt(
                                work_id=work_id,
                                attempt_kind=candidate.attempt_kind,
                                candidate_priority=candidate.priority,
                                candidate_url=url,
                                source_kind=candidate.source_kind,
                                http_status=http_status,
                                fetch_error_class=fetch_error_class,
                                latency_ms=round((time.monotonic() - started) * 1000.0, 3),
                                redirected_to=redirected_to,
                            )
                        )
                        continue
                    content_type = str(resp.headers.get("Content-Type") or "").lower()
                    raw_bytes = await resp.read()
                    latency_ms = round((time.monotonic() - started) * 1000.0, 3)
                    if "pdf" in content_type or candidate.expect_pdf or url.lower().endswith(".pdf"):
                        looks_pdf, sniff_state = _sniff_pdf_payload(raw_bytes, content_type=content_type)
                        if not looks_pdf:
                            attempts.append(
                                FullTextFetchAttempt(
                                    work_id=work_id,
                                    attempt_kind=candidate.attempt_kind,
                                    candidate_priority=candidate.priority,
                                    candidate_url=url,
                                    source_kind=candidate.source_kind or "publisher_pdf",
                                    http_status=http_status,
                                    fetch_error_class=sniff_state,
                                    latency_ms=latency_ms,
                                    redirected_to=redirected_to,
                                    text_chars=0,
                                    usable_text=False,
                                    final_for_work=False,
                                )
                            )
                            last_error_class = sniff_state
                            continue
                        text, _ = _sanitize_fulltext_text(_extract_pdf_text(raw_bytes))
                        usable, text_state = _classify_text_state(
                            text,
                            min_usable_chars=min_usable_chars,
                            min_soft_usable_chars=min_soft_usable_chars,
                            soft_usable_requires_section_cues=soft_usable_requires_section_cues,
                        )
                        attempts.append(
                            FullTextFetchAttempt(
                                work_id=work_id,
                                attempt_kind=candidate.attempt_kind,
                                candidate_priority=candidate.priority,
                                candidate_url=url,
                                source_kind=candidate.source_kind or "publisher_pdf",
                                http_status=http_status,
                                fetch_error_class="" if usable else "pdf_parse_failed" if not text.strip() else text_state,
                                latency_ms=latency_ms,
                                redirected_to=redirected_to,
                                text_chars=len(text.strip()),
                                usable_text=usable,
                                final_for_work=usable,
                            )
                        )
                        if usable:
                            return FullTextFetchResult(
                                text=text,
                                source_kind="fulltext_pdf",
                                source_url=final_url,
                                fetch_error_class="",
                                final_state="usable_fulltext",
                                attempts=tuple(attempts),
                                metadata_cache_rows=tuple(metadata_cache_rows),
                            )
                        last_error_class = "pdf_parse_failed" if not text.strip() else text_state
                        continue

                    html = raw_bytes.decode("utf-8", errors="ignore")
                    pdf_targets = _extract_pdf_targets(html, final_url)
                    redirect_targets = _extract_redirect_targets(html, final_url)
                    canonical_targets = _extract_canonical_targets(html, final_url)
                    for target in pdf_targets:
                        _insert_candidate(
                            pending_urls,
                            queued_urls,
                            url=target,
                            priority=max(0, candidate.priority - 5),
                            expect_pdf=True,
                            attempt_kind="discovered",
                            source_kind="publisher_pdf",
                            max_candidates=max_candidate_urls_per_work,
                        )
                    for target in redirect_targets:
                        _insert_candidate(
                            pending_urls,
                            queued_urls,
                            url=target,
                            priority=candidate.priority + 1,
                            expect_pdf=_is_probable_pdf_url(target),
                            attempt_kind="discovered",
                            source_kind="publisher_redirect",
                            max_candidates=max_candidate_urls_per_work,
                        )
                    for target in canonical_targets:
                        if target == final_url:
                            continue
                        _insert_candidate(
                            pending_urls,
                            queued_urls,
                            url=target,
                            priority=candidate.priority + 2,
                            expect_pdf=_is_probable_pdf_url(target),
                            attempt_kind="discovered",
                            source_kind="publisher_canonical",
                            max_candidates=max_candidate_urls_per_work,
                        )

                    text, _ = _sanitize_fulltext_text(_extract_html_text(html))
                    usable, text_state = _classify_text_state(
                        text,
                        min_usable_chars=min_usable_chars,
                        min_soft_usable_chars=min_soft_usable_chars,
                        soft_usable_requires_section_cues=soft_usable_requires_section_cues,
                    )
                    repository_shell = bool(pdf_targets) and _looks_like_repository_shell(text)
                    if _looks_like_redirect_placeholder(text):
                        fetch_error_class = "redirect_placeholder"
                    elif repository_shell:
                        fetch_error_class = "repository_shell_with_pdf"
                    elif pdf_targets and not usable:
                        fetch_error_class = "landing_page_without_pdf"
                    elif not usable and len(text.strip()) < min_soft_usable_chars:
                        fetch_error_class = "short_html_shell"
                    elif not usable:
                        fetch_error_class = text_state
                    else:
                        fetch_error_class = ""

                    attempts.append(
                        FullTextFetchAttempt(
                            work_id=work_id,
                            attempt_kind=candidate.attempt_kind,
                            candidate_priority=candidate.priority,
                            candidate_url=url,
                            source_kind=candidate.source_kind or "publisher_html",
                            http_status=http_status,
                            fetch_error_class=fetch_error_class,
                            latency_ms=latency_ms,
                            redirected_to=redirected_to,
                            discovered_pdf_count=len(pdf_targets),
                            discovered_canonical_count=len(canonical_targets),
                            text_chars=len(text.strip()),
                            usable_text=usable and not repository_shell,
                            final_for_work=usable and not repository_shell,
                        )
                    )
                    if usable and not repository_shell:
                        return FullTextFetchResult(
                            text=text,
                            source_kind="fulltext_html",
                            source_url=final_url,
                            fetch_error_class="",
                            final_state="usable_fulltext",
                            attempts=tuple(attempts),
                            metadata_cache_rows=tuple(metadata_cache_rows),
                        )
                    last_error_class = fetch_error_class or text_state
                    continue
            except Exception as exc:
                error_class = _classify_fetch_error(exc)
                last_error_class = error_class
                attempts.append(
                    FullTextFetchAttempt(
                        work_id=work_id,
                        attempt_kind=candidate.attempt_kind,
                        candidate_priority=candidate.priority,
                        candidate_url=url,
                        source_kind=candidate.source_kind,
                        http_status=0,
                        fetch_error_class=error_class,
                        latency_ms=round((time.monotonic() - started) * 1000.0, 3),
                    )
                )
                continue
    finally:
        if owns_session:
            await local_session.close()

    return FullTextFetchResult(
        text=reconstruct_abstract(work),
        source_kind="abstract_fallback",
        source_url="",
        fetch_error_class=last_error_class,
        final_state="abstract_fallback",
        attempts=tuple(attempts),
        metadata_cache_rows=tuple(metadata_cache_rows),
    )


async def fetch_full_text_result_for_work(
    work: dict[str, Any],
    *,
    timeout_seconds: int | None = None,
    connect_timeout_seconds: int | None = None,
    read_timeout_seconds: int | None = None,
    total_timeout_seconds: int | None = None,
    session: aiohttp.ClientSession | None = None,
    acquisition_mode: str = "v3_legacy",
    metadata_resolvers_enabled: bool = True,
    metadata_resolver_order: tuple[str, ...] = ("unpaywall", "crossref", "semanticscholar"),
    unpaywall_email: str = "",
    semantic_scholar_api_key: str = "",
    metadata_timeout_seconds: int = 20,
    max_candidate_urls_per_work: int = 20,
    min_usable_chars: int = 1500,
    min_soft_usable_chars: int = 700,
    soft_usable_requires_section_cues: bool = True,
    metadata_cache: dict[str, dict[str, Any]] | None = None,
    resolved_cache: dict[str, dict[str, Any]] | None = None,
    cache_ttl_days: int = 30,
) -> FullTextFetchResult:
    """Return text/source metadata plus detailed attempt telemetry."""
    work_id = str(work.get("id") or "")
    if resolved_cache is not None:
        for key in _cache_keys_for_work(work):
            cached_row = resolved_cache.get(key)
            if cached_row and _is_cache_row_fresh(cached_row, ttl_days=cache_ttl_days):
                return FullTextFetchResult(
                    text=str(cached_row.get("text") or ""),
                    source_kind=str(cached_row.get("source_kind") or "abstract_fallback"),
                    source_url=str(cached_row.get("source_url") or ""),
                    fetch_error_class=str(cached_row.get("fetch_error_class") or ""),
                    final_state=str(cached_row.get("final_state") or "abstract_fallback"),
                    attempts=(_cache_attempt(work_id, cached_row),),
                    cache_hit=True,
                    cache_key=str(cached_row.get("cache_key") or key),
                )

    if acquisition_mode == "v7_http_metadata":
        result = await _fetch_v7_http_metadata(
            work,
            timeout_seconds=timeout_seconds,
            connect_timeout_seconds=connect_timeout_seconds,
            read_timeout_seconds=read_timeout_seconds,
            total_timeout_seconds=total_timeout_seconds,
            session=session,
            metadata_enabled=metadata_resolvers_enabled,
            metadata_resolver_order=metadata_resolver_order,
            unpaywall_email=unpaywall_email,
            semantic_scholar_api_key=semantic_scholar_api_key,
            metadata_timeout_seconds=metadata_timeout_seconds,
            max_candidate_urls_per_work=max_candidate_urls_per_work,
            min_usable_chars=min_usable_chars,
            min_soft_usable_chars=min_soft_usable_chars,
            soft_usable_requires_section_cues=soft_usable_requires_section_cues,
            metadata_cache=metadata_cache,
        )
    else:
        result = await _fetch_v3_legacy(
            work,
            timeout_seconds=timeout_seconds,
            connect_timeout_seconds=connect_timeout_seconds,
            read_timeout_seconds=read_timeout_seconds,
            total_timeout_seconds=total_timeout_seconds,
            session=session,
        )

    cache_row = _build_resolved_cache_row(work, result)
    if resolved_cache is not None:
        _store_resolved_cache_row(resolved_cache, cache_row)
    return replace(result, resolved_cache_row=cache_row, cache_key=str(cache_row.get("cache_key") or ""))


async def fetch_full_text_for_work(
    work: dict[str, Any],
    *,
    timeout_seconds: int | None = None,
    connect_timeout_seconds: int | None = None,
    read_timeout_seconds: int | None = None,
    total_timeout_seconds: int | None = None,
    session: aiohttp.ClientSession | None = None,
) -> tuple[str, str, str]:
    """Return (text, source_kind, source_url)."""
    result = await fetch_full_text_result_for_work(
        work,
        timeout_seconds=timeout_seconds,
        connect_timeout_seconds=connect_timeout_seconds,
        read_timeout_seconds=read_timeout_seconds,
        total_timeout_seconds=total_timeout_seconds,
        session=session,
    )
    return result.text, result.source_kind, result.source_url


def _load_selected_works(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


async def run_fulltext_resolve(config: AcademicBatchConfig) -> dict[str, int]:
    """Run fulltext resolve."""
    started_at = datetime.now(UTC).isoformat()
    rows = _load_selected_works(config.selected_global_works_path)
    if not rows:
        write_stage_manifest(
            manifest_path=config.manifests_dir / "fulltext_resolve.json",
            stage="fulltext_resolve",
            status="ok",
            metrics={"records": 0, "resolved": 0, "fulltext_cache_hits": 0},
            artifacts=[],
            started_at=started_at,
        )
        return {"records": 0, "resolved": 0, "fulltext_cache_hits": 0}

    output_rows: list[dict[str, Any]] = []
    resolved = 0
    abstract_only = 0
    fulltext_cache_hits = 0
    metadata_cache_rows: list[dict[str, Any]] = []
    resolved_cache_rows: list[dict[str, Any]] = []
    metadata_cache: dict[str, dict[str, Any]] = {}
    resolved_cache = load_resolved_fulltext_cache(
        config.resolved_fulltext_cache_path,
        ttl_days=config.fulltext_cache_ttl_days,
    )
    if config.fulltext_metadata_cache_path.exists():
        with open(config.fulltext_metadata_cache_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    key = str(row.get("cache_key") or "")
                    if key:
                        metadata_cache[key] = row

    for row in rows:
        work = row.get("work")
        if not isinstance(work, dict):
            continue
        work_id = str(work.get("id") or row.get("work_id") or "")
        if not work_id:
            continue
        result = await fetch_full_text_result_for_work(
            work,
            timeout_seconds=config.article_fulltext_timeout_seconds,
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
        if result.cache_hit:
            fulltext_cache_hits += 1
        metadata_cache_rows.extend(result.metadata_cache_rows)
        if result.resolved_cache_row is not None:
            resolved_cache_rows.append(result.resolved_cache_row)
        source_basis = (
            SourceBasis.ABSTRACT_ONLY.value
            if result.source_kind == "abstract_fallback"
            else SourceBasis.FULLTEXT.value
        )
        if source_basis == SourceBasis.ABSTRACT_ONLY.value:
            abstract_only += 1
        else:
            resolved += 1
        output_rows.append(
            {
                "work_id": work_id,
                "source_kind": result.source_kind,
                "source_basis": source_basis,
                "text_quality": _text_quality_for(result.source_kind, result.text).value,
                "source_url": result.source_url,
                "fetch_error_class": result.fetch_error_class,
                "final_state": result.final_state,
                "text": result.text,
            }
        )

    with open(config.fulltext_resolved_path, "w", encoding="utf-8") as fh:
        for row in output_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    if metadata_cache_rows:
        with open(config.fulltext_metadata_cache_path, "a", encoding="utf-8") as fh:
            for row in metadata_cache_rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    if resolved_cache_rows:
        with open(config.resolved_fulltext_cache_path, "a", encoding="utf-8") as fh:
            for row in resolved_cache_rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    metrics = {
        "records": len(output_rows),
        "resolved": resolved,
        "abstract_only": abstract_only,
        "fulltext_cache_hits": fulltext_cache_hits,
    }
    artifacts = [config.fulltext_resolved_path]
    if metadata_cache_rows:
        artifacts.append(config.fulltext_metadata_cache_path)
    if resolved_cache_rows:
        artifacts.append(config.resolved_fulltext_cache_path)
    write_stage_manifest(
        manifest_path=config.manifests_dir / "fulltext_resolve.json",
        stage="fulltext_resolve",
        status="ok",
        metrics=metrics,
        artifacts=artifacts,
        started_at=started_at,
    )
    return metrics


__all__ = [
    "FullTextFetchAttempt",
    "FullTextFetchResult",
    "fetch_full_text_for_work",
    "fetch_full_text_result_for_work",
    "load_resolved_fulltext_cache",
    "reconstruct_abstract",
    "run_fulltext_resolve",
]
