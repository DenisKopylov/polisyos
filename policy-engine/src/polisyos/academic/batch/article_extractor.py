"""Phase 0a article extraction pipeline (screening + full extraction)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiohttp

from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.batch.context_classifier import infer_context_from_article
from polisyos.academic.batch.prompts import (
    BOUNDARY_CONDITIONS_SCHEMA_HINT,
    CAUSAL_CLAIMS_SCHEMA_HINT,
    MECHANISMS_SCHEMA_HINT,
    SCREENING_PROMPT,
)
from polisyos.academic.knowledge.types import EstimateCandidate, SourceTopicRef, WorkRecord
from polisyos.academic.knowledge.variable_canonizer import VariableCanonizer
from polisyos.academic.openalex.priority_filter import should_process
from polisyos.core.canon.hashing import content_hash
from polisyos.ir.analytics.literature import ArticleExtractionResult

logger = logging.getLogger(__name__)


def _parse_json_object(raw_content: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw_content)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    start = raw_content.find("{")
    end = raw_content.rfind("}")
    if start != -1 and end > start:
        candidate = raw_content[start : end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None
    return None


class _SlidingWindowLimiter:
    def __init__(self, max_requests: int, window: float = 1.0) -> None:
        self._max = max(1, int(max_requests))
        self._window = float(window)
        self._lock = asyncio.Lock()
        self._timestamps: deque[float] = deque()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._timestamps and self._timestamps[0] <= now - self._window:
                    self._timestamps.popleft()
                if len(self._timestamps) < self._max:
                    self._timestamps.append(now)
                    return
                wait = self._timestamps[0] + self._window - now
            await asyncio.sleep(max(0.01, wait))


class GonkaChatClient:
    """OpenAI-compatible client using Gonka API pattern from lex batch."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        max_concurrent: int,
        rate_limit_rps: float,
        max_retries: int,
        disable_json_mode: bool = False,
        timeout_seconds: int = 120,
    ) -> None:
        self._api_key = api_key
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._session: aiohttp.ClientSession | None = None
        self._sem = asyncio.Semaphore(max(1, int(max_concurrent)))
        self._limiter = _SlidingWindowLimiter(max(1, int(rate_limit_rps)), window=1.0)
        self._max_retries = max(1, int(max_retries))
        self._disable_json_mode = disable_json_mode
        self._timeout = aiohttp.ClientTimeout(total=max(10, int(timeout_seconds)))

    async def __aenter__(self) -> "GonkaChatClient":
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def chat(
        self,
        *,
        model: str,
        temperature: float,
        prompt: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        assert self._session is not None, "Use async context manager"

        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if not self._disable_json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            async with self._sem:
                await self._limiter.acquire()
                try:
                    async with self._session.post(self._url, json=payload) as resp:
                        body = await resp.text()
                        if resp.status == 200:
                            data = json.loads(body)
                            if not isinstance(data, dict):
                                data = {}
                            content = ""
                            choices = data.get("choices")
                            if isinstance(choices, list) and choices:
                                first = choices[0]
                                if isinstance(first, dict):
                                    msg = first.get("message")
                                    if isinstance(msg, dict):
                                        content = str(msg.get("content") or "")
                            parsed = _parse_json_object(content) or {}
                            usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
                            return parsed, usage

                        if resp.status in {429, 500, 502, 503, 504}:
                            await asyncio.sleep(min(0.5 * (2 ** (attempt - 1)), 20.0))
                            continue

                        # Retry once without JSON mode for compatibility.
                        if resp.status == 400 and "response_format" in payload:
                            payload.pop("response_format", None)
                            await asyncio.sleep(0.05)
                            continue

                        raise RuntimeError(f"Gonka HTTP {resp.status}: {body[:300]}")
                except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as exc:
                    last_error = exc
                    await asyncio.sleep(min(0.5 * (2 ** (attempt - 1)), 20.0))

        raise RuntimeError("Gonka request failed after retries") from last_error


@dataclass
class ExtractorStats:
    total_seen: int = 0
    skipped: int = 0
    screening_rejected: int = 0
    no_fulltext: int = 0
    extracted: int = 0
    extraction_errors: int = 0
    cached_skipped: int = 0
    total_screening_cost_usd: float = 0.0
    total_extraction_cost_usd: float = 0.0
    total_tokens_prompt: int = 0
    total_tokens_completion: int = 0
    new_canonical_names: int = 0
    elapsed_seconds: float = 0.0


class PolicyArticleExtractor:
    def __init__(
        self,
        *,
        screening_model: str,
        extraction_model: str,
        max_concurrent: int,
        canonizer: VariableCanonizer,
        gonka_client: GonkaChatClient,
        fulltext_timeout_seconds: int,
        cache_path: Path,
    ) -> None:
        self.screening_model = screening_model
        self.extraction_model = extraction_model
        self._semaphore = asyncio.Semaphore(max(1, int(max_concurrent)))
        self._canonizer = canonizer
        self._gonka = gonka_client
        self._fulltext_timeout_seconds = max(3, int(fulltext_timeout_seconds))
        self._cache_path = cache_path
        self._processed_cache = self._load_processed_cache(cache_path)

    @staticmethod
    def _load_processed_cache(cache_path: Path) -> set[str]:
        if not cache_path.exists():
            return set()
        cache: set[str] = set()
        with open(cache_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = row.get("cache_key")
                if isinstance(key, str) and key:
                    cache.add(key)
        return cache

    def _append_cache_key(self, cache_key: str, openalex_id: str) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._cache_path, "a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "cache_key": cache_key,
                        "openalex_id": openalex_id,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        self._processed_cache.add(cache_key)

    @staticmethod
    def _cache_key_for_work(work: dict[str, Any]) -> str:
        openalex_id = str(work.get("id") or "")
        doi = str(work.get("doi") or "")
        payload = f"{doi.strip().lower()}|{openalex_id.strip().lower()}"
        if payload == "|":
            payload = json.dumps(work, sort_keys=True, ensure_ascii=False)
        return content_hash(payload, prefix=True)

    @staticmethod
    def _reconstruct_abstract(work: dict[str, Any]) -> str:
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

    async def _screen(self, abstract: str, stats: ExtractorStats) -> bool:
        prompt = SCREENING_PROMPT.format(abstract=abstract[:6000])
        parsed, usage = await self._gonka.chat(
            model=self.screening_model,
            temperature=0.0,
            prompt=prompt,
        )
        stats.total_tokens_prompt += int(usage.get("prompt_tokens") or 0)
        stats.total_tokens_completion += int(usage.get("completion_tokens") or 0)
        stats.total_screening_cost_usd += float(usage.get("total_cost_usd") or 0.0)
        return bool(parsed.get("relevant", False))

    async def _fetch_full_text(self, work: dict[str, Any]) -> tuple[str, str]:
        """Return (text, source_kind). source_kind in {fulltext_html, fulltext_pdf, abstract_fallback}."""
        open_access = work.get("open_access") if isinstance(work.get("open_access"), dict) else {}
        best_oa = work.get("best_oa_location") if isinstance(work.get("best_oa_location"), dict) else {}
        url = str(open_access.get("oa_url") or best_oa.get("pdf_url") or "").strip()

        if not url:
            abstract = self._reconstruct_abstract(work)
            return abstract, "abstract_fallback"

        timeout = aiohttp.ClientTimeout(total=self._fulltext_timeout_seconds)
        headers = {"User-Agent": "PolicyOS/1.0 (+academic extraction)"}
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        abstract = self._reconstruct_abstract(work)
                        return abstract, "abstract_fallback"

                    content_type = str(resp.headers.get("Content-Type") or "").lower()
                    raw_bytes = await resp.read()

                    if "pdf" in content_type or url.lower().endswith(".pdf"):
                        text = self._extract_pdf_text(raw_bytes)
                        if text.strip():
                            return text, "fulltext_pdf"
                        abstract = self._reconstruct_abstract(work)
                        return abstract, "abstract_fallback"

                    text = self._extract_html_text(raw_bytes.decode("utf-8", errors="ignore"))
                    if text.strip():
                        return text, "fulltext_html"
        except Exception:
            pass

        abstract = self._reconstruct_abstract(work)
        return abstract, "abstract_fallback"

    @staticmethod
    def _extract_html_text(html: str) -> str:
        cleaned = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
        cleaned = re.sub(r"(?is)<style.*?>.*?</style>", " ", cleaned)
        cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    @staticmethod
    def _extract_pdf_text(raw_bytes: bytes) -> str:
        try:
            from pypdf import PdfReader  # type: ignore[import-not-found]
        except Exception:
            return ""

        try:
            import io

            reader = PdfReader(io.BytesIO(raw_bytes))
            texts: list[str] = []
            for page in reader.pages[:30]:
                texts.append(str(page.extract_text() or ""))
            return "\n".join(texts).strip()
        except Exception:
            return ""

    async def _extract(self, work: dict[str, Any], text: str, stats: ExtractorStats) -> ArticleExtractionResult | None:
        extraction_prompt = f"""
Extract policy-relevant empirical evidence from the paper text.
Return strict JSON with keys:
- empirical_parameters
- causal_claims
- mechanisms
- boundary_conditions
- methodology
- sample_size
- citation_summary
- extraction_confidence

{CAUSAL_CLAIMS_SCHEMA_HINT}
{MECHANISMS_SCHEMA_HINT}
{BOUNDARY_CONDITIONS_SCHEMA_HINT}

Text:
{text[:14000]}
""".strip()

        parsed, usage = await self._gonka.chat(
            model=self.extraction_model,
            temperature=0.0,
            prompt=extraction_prompt,
        )

        stats.total_tokens_prompt += int(usage.get("prompt_tokens") or 0)
        stats.total_tokens_completion += int(usage.get("completion_tokens") or 0)
        stats.total_extraction_cost_usd += float(usage.get("total_cost_usd") or 0.0)

        try:
            result = ArticleExtractionResult(
                openalex_id=str(work.get("id") or ""),
                doi=str(work.get("doi") or ""),
                title=str(work.get("title") or ""),
                year=int(work.get("publication_year") or 0) or None,
                cited_by_count=int(work.get("cited_by_count") or 0),
                empirical_parameters=parsed.get("empirical_parameters") or [],
                causal_claims=parsed.get("causal_claims") or [],
                mechanisms=parsed.get("mechanisms") or [],
                boundary_conditions=parsed.get("boundary_conditions") or [],
                methodology=str(parsed.get("methodology") or ""),
                sample_size=int(parsed.get("sample_size")) if parsed.get("sample_size") is not None else None,
                citation_summary=str(parsed.get("citation_summary") or ""),
                extraction_model=self.extraction_model,
                extraction_timestamp=datetime.now(UTC).isoformat(),
                extraction_confidence=float(parsed.get("extraction_confidence") or 0.7),
                screening_cost_usd=0.0,
                extraction_cost_usd=float(usage.get("total_cost_usd") or 0.0),
                token_count_prompt=int(usage.get("prompt_tokens") or 0),
                token_count_completion=int(usage.get("completion_tokens") or 0),
            )
            return result
        except Exception as exc:
            logger.warning("article extraction parse failed for %s: %s", work.get("id"), exc)
            stats.extraction_errors += 1
            return None

    def _canonize_variables(self, result: ArticleExtractionResult, stats: ExtractorStats) -> ArticleExtractionResult:
        canonized_claims = []
        for claim in result.causal_claims:
            cause, cause_new = self._canonizer.canonize(claim.cause_variable)
            effect, effect_new = self._canonizer.canonize(claim.effect_variable)
            stats.new_canonical_names += int(cause_new) + int(effect_new)
            canonized_claims.append(
                claim.model_copy(update={"cause_variable": cause, "effect_variable": effect})
            )

        canonized_params = []
        for parameter in result.empirical_parameters:
            name, is_new = self._canonizer.canonize(parameter.name)
            stats.new_canonical_names += int(is_new)
            canonized_params.append(parameter.model_copy(update={"name": name}))

        canonized_mechanisms = []
        for mechanism in result.mechanisms:
            mediators: list[str] = []
            for mediator in mechanism.mediating_variables:
                canonical_mediator, is_new = self._canonizer.canonize(mediator)
                stats.new_canonical_names += int(is_new)
                mediators.append(canonical_mediator)
            canonized_mechanisms.append(
                mechanism.model_copy(update={"mediating_variables": mediators})
            )

        canonized_boundaries = []
        for boundary in result.boundary_conditions:
            if boundary.variable:
                canonical_var, is_new = self._canonizer.canonize(boundary.variable)
                stats.new_canonical_names += int(is_new)
                canonized_boundaries.append(boundary.model_copy(update={"variable": canonical_var}))
            else:
                canonized_boundaries.append(boundary)

        return result.model_copy(
            update={
                "causal_claims": canonized_claims,
                "empirical_parameters": canonized_params,
                "mechanisms": canonized_mechanisms,
                "boundary_conditions": canonized_boundaries,
            }
        )

    async def _process_one(self, work: dict[str, Any], stats: ExtractorStats) -> ArticleExtractionResult | None:
        async with self._semaphore:
            cache_key = self._cache_key_for_work(work)
            if cache_key in self._processed_cache:
                stats.cached_skipped += 1
                return None

            abstract = self._reconstruct_abstract(work)
            if abstract:
                relevant = await self._screen(abstract, stats)
                if not relevant:
                    stats.screening_rejected += 1
                    return None

            full_text, source_kind = await self._fetch_full_text(work)
            if not full_text.strip():
                stats.no_fulltext += 1
                return None

            result = await self._extract(work, full_text, stats)
            if result is None:
                return None

            if source_kind == "abstract_fallback":
                result = result.model_copy(
                    update={
                        "extraction_confidence": max(0.1, result.extraction_confidence * 0.8),
                        "citation_summary": (
                            (result.citation_summary + " ").strip()
                            + "[fallback:abstract_only]"
                        ).strip(),
                    }
                )

            result = self._canonize_variables(result, stats)
            result = result.model_copy(update={"source_context": infer_context_from_article(work, result)})
            self._append_cache_key(cache_key, result.openalex_id)

            stats.extracted += 1
            return result

    async def process_batch(
        self,
        works: list[dict[str, Any]],
        *,
        domain_filter: list[str] | None = None,
        min_citations: int = 10,
    ) -> tuple[list[ArticleExtractionResult], ExtractorStats]:
        started = time.monotonic()
        stats = ExtractorStats()
        accepted: list[tuple[int, dict[str, Any]]] = []

        for index, work in enumerate(works):
            stats.total_seen += 1
            keep, _ = should_process(work, domain_filter=domain_filter, min_citations=min_citations)
            if not keep:
                stats.skipped += 1
                continue
            accepted.append((index, work))

        async def _run_one(index: int, work: dict[str, Any]) -> tuple[int, ArticleExtractionResult | None]:
            return index, await self._process_one(work, stats)

        indexed_results: list[tuple[int, ArticleExtractionResult]] = []
        tasks = [asyncio.create_task(_run_one(index, work)) for index, work in accepted]
        for task in asyncio.as_completed(tasks):
            index, result = await task
            if result is not None:
                indexed_results.append((index, result))

        indexed_results.sort(key=lambda item: item[0])
        results = [result for _, result in indexed_results]

        stats.elapsed_seconds = time.monotonic() - started
        return results, stats


def _safe_float(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_work_record(
    *,
    result: ArticleExtractionResult,
    raw_work: dict[str, Any],
    topic_ids: list[str],
    topic_display_names: list[str],
    run_id: str,
    pass_name: str,
) -> WorkRecord:
    estimates: list[EstimateCandidate] = []
    for parameter in result.empirical_parameters:
        value = parameter.value
        if value is None and parameter.value_range is not None:
            lo, hi = parameter.value_range
            value = (float(lo) + float(hi)) / 2.0
        if value is None:
            continue
        estimates.append(
            EstimateCandidate(
                value=float(value),
                ci_low=(
                    _safe_float(parameter.confidence_interval[0])
                    if parameter.confidence_interval is not None
                    else None
                ),
                ci_high=(
                    _safe_float(parameter.confidence_interval[1])
                    if parameter.confidence_interval is not None
                    else None
                ),
                std_error=_safe_float(parameter.std_error),
                unit=str(parameter.unit or ""),
                context_snippet=str(parameter.heterogeneity_note or ""),
                pattern_name="article_extract",
                confidence=float(result.extraction_confidence),
                variable_hint=parameter.name,
            )
        )

    causal_claims = [
        {
            "cause": claim.cause_variable,
            "effect": claim.effect_variable,
            "direction": claim.direction.value,
            "strength": claim.evidence_strength.value,
            "mechanism": claim.counterevidence_notes,
            "effect_size": claim.effect_size,
        }
        for claim in result.causal_claims
    ]

    boundary_conditions = [
        {
            "variable": boundary.variable,
            "operator": boundary.operator,
            "threshold_value": str(boundary.required_value or boundary.threshold_value or ""),
            "scope_text": boundary.scope_text,
            "confidence": boundary.confidence,
            "condition_type": boundary.condition_type,
            "consequence_if_violated": boundary.consequence_if_violated,
        }
        for boundary in result.boundary_conditions
    ]

    topic_refs: list[SourceTopicRef] = []
    for index, topic_id in enumerate(topic_ids):
        topic_refs.append(
            SourceTopicRef(
                topic_id=str(topic_id),
                topic_display_name=(
                    topic_display_names[index]
                    if index < len(topic_display_names)
                    else str(topic_id)
                ),
                rank=0,
                selection_score=0.0,
                batch_origin="article_extract",
                selected_at=datetime.now(UTC).isoformat(),
            )
        )

    abstract = PolicyArticleExtractor._reconstruct_abstract(raw_work)

    return WorkRecord(
        id=result.openalex_id,
        title=result.title,
        doi=result.doi,
        abstract=abstract,
        year=result.year,
        publication_date=str(raw_work.get("publication_date") or ""),
        language=str(raw_work.get("language") or ""),
        work_type=str(raw_work.get("type") or ""),
        is_retracted=bool(raw_work.get("is_retracted") or False),
        cited_by_count=result.cited_by_count,
        fwci=float(raw_work.get("fwci")) if isinstance(raw_work.get("fwci"), (int, float)) else None,
        citation_normalized_percentile=None,
        citation_is_top_1_percent=False,
        citation_is_top_10_percent=False,
        journal="",
        source_id="",
        is_oa=bool((raw_work.get("open_access") or {}).get("is_oa") if isinstance(raw_work.get("open_access"), dict) else False),
        has_fulltext=bool(raw_work.get("has_fulltext") or False),
        full_text_url=str(((raw_work.get("open_access") or {}).get("oa_url") if isinstance(raw_work.get("open_access"), dict) else "") or ""),
        concepts=list(raw_work.get("topics") or []),
        source_topics=topic_refs,
        study_design=str(result.methodology or ""),
        trust_score=float(result.extraction_confidence),
        estimates=estimates,
        causal_claims=causal_claims,
        boundary_conditions=boundary_conditions,
        context_profile=result.source_context.model_dump(mode="json") if result.source_context else {},
        extraction_mode="article_extract",
        extraction_confidence=float(result.extraction_confidence),
        method_signal_score=float(result.extraction_confidence),
        token_count_prompt=int(result.token_count_prompt),
        token_count_completion=int(result.token_count_completion),
        screening_cost_usd=float(result.screening_cost_usd),
        extraction_cost_usd=float(result.extraction_cost_usd),
        metadata={
            "sample_size": result.sample_size,
            "run_id": run_id,
            "pass_name": pass_name,
            "article_extract": True,
        },
    )


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


async def run_article_extract(config: AcademicBatchConfig) -> dict[str, float | int]:
    """Run phase-0a article extraction and emit WorkRecord payload for merge stage."""
    started_at = datetime.now(UTC).isoformat()

    selected_rows = _load_selected_works(config.selected_global_works_path)
    if not selected_rows:
        write_stage_manifest(
            manifest_path=config.manifests_dir / "article_extract.json",
            stage="article_extract",
            status="ok",
            metrics={"records": 0, "extracted": 0},
            artifacts=[],
            started_at=started_at,
        )
        return {"records": 0, "extracted": 0}

    if not config.gonka_api_key:
        # Keep pipeline robust when optional deps/API are absent.
        write_stage_manifest(
            manifest_path=config.manifests_dir / "article_extract.json",
            stage="article_extract",
            status="ok",
            metrics={"records": len(selected_rows), "extracted": 0, "skipped_reason": "no_api_key"},
            artifacts=[],
            started_at=started_at,
        )
        return {"records": len(selected_rows), "extracted": 0, "skipped_reason": "no_api_key"}

    canonizer = VariableCanonizer(db_path=config.db_path)
    client = GonkaChatClient(
        api_key=config.gonka_api_key,
        base_url=config.gonka_base_url,
        max_concurrent=config.article_max_concurrent_llm,
        rate_limit_rps=config.article_rate_limit_rps,
        max_retries=config.article_max_retries,
        timeout_seconds=120,
    )

    works: list[dict[str, Any]] = []
    topic_meta: dict[str, tuple[list[str], list[str]]] = {}
    for row in selected_rows:
        work = row.get("work")
        if not isinstance(work, dict):
            continue
        work_id = str(row.get("work_id") or work.get("id") or "")
        if not work_id:
            continue
        works.append(work)
        topic_meta[work_id] = (
            [str(t) for t in row.get("topic_ids") or []],
            [str(t) for t in row.get("topic_display_names") or []],
        )

    async with client:
        extractor = PolicyArticleExtractor(
            screening_model=config.article_screening_model,
            extraction_model=config.article_extraction_model,
            max_concurrent=config.article_max_concurrent_llm,
            canonizer=canonizer,
            gonka_client=client,
            fulltext_timeout_seconds=config.article_fulltext_timeout_seconds,
            cache_path=config.article_extraction_cache_path,
        )
        results, stats = await extractor.process_batch(works)

    config.extracted_dir.mkdir(parents=True, exist_ok=True)
    output_records_path = config.extracted_dir / "article_extract.jsonl"

    with open(config.article_extraction_results_path, "w", encoding="utf-8") as fh:
        for result in results:
            fh.write(result.model_dump_json() + "\n")

    with open(output_records_path, "w", encoding="utf-8") as fh:
        for result in results:
            topic_ids, topic_display_names = topic_meta.get(result.openalex_id, ([], []))
            work_row = next((w for w in works if str(w.get("id") or "") == result.openalex_id), {})
            record = _to_work_record(
                result=result,
                raw_work=work_row,
                topic_ids=topic_ids,
                topic_display_names=topic_display_names,
                run_id=config.run_id,
                pass_name=config.pass_name,
            )
            fh.write(record.model_dump_json() + "\n")

    metrics = {
        "records": stats.total_seen,
        "skipped": stats.skipped,
        "screening_rejected": stats.screening_rejected,
        "no_fulltext": stats.no_fulltext,
        "extracted": stats.extracted,
        "extraction_errors": stats.extraction_errors,
        "cached_skipped": stats.cached_skipped,
        "new_canonical_names": stats.new_canonical_names,
        "total_screening_cost_usd": round(stats.total_screening_cost_usd, 6),
        "total_extraction_cost_usd": round(stats.total_extraction_cost_usd, 6),
        "total_tokens_prompt": stats.total_tokens_prompt,
        "total_tokens_completion": stats.total_tokens_completion,
        "elapsed_seconds": round(stats.elapsed_seconds, 3),
    }

    write_stage_manifest(
        manifest_path=config.manifests_dir / "article_extract.json",
        stage="article_extract",
        status="ok",
        metrics=metrics,
        artifacts=[config.article_extraction_results_path, output_records_path],
        started_at=started_at,
    )

    return metrics


__all__ = ["ExtractorStats", "PolicyArticleExtractor", "run_article_extract"]
