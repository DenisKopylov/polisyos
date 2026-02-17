"""Stage 3: Async LLM-based 2-pass extraction via Gonka (OpenAI-compatible API).

Pass 1: Extract statements.
Pass 2: Verify + normalize extracted statements against the same provision.

Policy: mark-and-continue for low confidence (no extra LLM passes).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from pathlib import Path
from typing import Any

import aiohttp

from polisyos.lex.batch.canonicalizers import (
    canonicalize_action,
    canonicalize_norm_type,
    extract_thresholds_from_text,
)
from polisyos.lex.batch.provisions_io import _shard_prefix
from polisyos.lex.batch.spo_prompts import (
    SPO_EXTRACT_SYSTEM_PROMPT,
    SPO_PROMPT_VERSION,
    SPO_VERIFY_SYSTEM_PROMPT,
    build_spo_extract_user_prompt,
    build_spo_verify_user_prompt,
)
from polisyos.lex.batch.structurer import ProvisionSpan
from polisyos.lex.batch.xml_parser import NPADocument
from polisyos.lex.knowledge.types import SPOCandidate, SPOExtractionResult

logger = logging.getLogger(__name__)


def _retry_delay_seconds(*, attempt: int, retry_after: str | None) -> float:
    """Compute retry delay honoring Retry-After header when present."""
    if retry_after:
        try:
            parsed = float(retry_after.strip())
            if parsed > 0:
                return min(parsed, 120.0)
        except ValueError:
            pass
    return min(2 ** (attempt - 1) + 0.5, 30.0)


class _SlidingWindowLimiter:
    """Async sliding-window rate limiter with 429-cooldown support."""

    __slots__ = ("_max", "_window", "_lock", "_timestamps")

    def __init__(self, max_requests: int, window: float = 1.0) -> None:
        self._max = max(1, max_requests)
        self._window = window
        self._lock = asyncio.Lock()
        self._timestamps: deque[float] = deque()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                cutoff = now - self._window
                while self._timestamps and self._timestamps[0] <= cutoff:
                    self._timestamps.popleft()
                if len(self._timestamps) < self._max:
                    self._timestamps.append(time.monotonic())
                    return
                wait = self._timestamps[0] + self._window - now
            await asyncio.sleep(max(0.01, wait))

    async def penalise(self, penalty_seconds: float = 5.0) -> None:
        async with self._lock:
            future = time.monotonic() + penalty_seconds - self._window
            for _ in range(self._max):
                self._timestamps.append(future)


class GonkaClient:
    """Async OpenAI-compatible chat completion client with rate limiting."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        disable_json_mode: bool = False,
        max_concurrent: int = 50,
        rate_limit_rps: float = 100.0,
        temperature: float = 0.1,
        max_retries: int = 7,
    ) -> None:
        self._api_key = api_key
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._limiter = _SlidingWindowLimiter(
            max_requests=max(1, int(rate_limit_rps)),
            window=1.0,
        )
        self._session: aiohttp.ClientSession | None = None
        # Some deployments reject OpenAI JSON-mode ("response_format") even though
        # the rest of the Chat Completions surface is compatible. When we detect
        # that pattern once, disable JSON-mode for the rest of the run to avoid
        # doubling request volume.
        self._json_mode_disabled = disable_json_mode
        if disable_json_mode:
            logger.info("Gonka JSON-mode disabled by configuration; sending plain chat completions.")

    @property
    def model_id(self) -> str:
        return self._model

    async def __aenter__(self) -> GonkaClient:
        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=aiohttp.ClientTimeout(total=180),
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request with retry + rate limiting."""
        assert self._session is not None, "Use 'async with GonkaClient(...)'"

        payload_base: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
        }

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            async with self._semaphore:
                await self._limiter.acquire()
                payload = dict(payload_base)
                if response_format and not self._json_mode_disabled:
                    payload["response_format"] = response_format
                try:
                    async with self._session.post(self._url, json=payload) as resp:
                        if resp.status == 200:
                            return await resp.json()

                        body = await resp.text()
                        if (
                            "response_format" in payload
                            and _is_json_mode_invalid_request(resp.status, body)
                        ):
                            logger.warning(
                                "Gonka 400 invalid_request with response_format; "
                                "retrying without JSON-mode for this request."
                            )
                            self._json_mode_disabled = True
                            payload.pop("response_format", None)
                            # Known compatibility fallback; do not spend retry budget.
                            continue

                        if resp.status < 500 and resp.status not in (429,):
                            logger.warning("Gonka %d (non-retryable): %s", resp.status, body[:200])
                            raise RuntimeError(
                                f"Gonka non-retryable error: HTTP {resp.status}: {body[:500]}"
                            )

                        if resp.status == 429:
                            await self._limiter.penalise(5.0)

                        delay = _retry_delay_seconds(
                            attempt=attempt,
                            retry_after=resp.headers.get("Retry-After"),
                        )
                        logger.warning(
                            "Gonka %d (attempt %d/%d), retry in %.1fs: %s",
                            resp.status,
                            attempt,
                            self._max_retries,
                            delay,
                            body[:200],
                        )
                        last_error = RuntimeError(
                            f"Gonka retryable HTTP {resp.status}: {body[:200]}"
                        )
                        await asyncio.sleep(delay)
                        continue

                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    exc_str = str(exc)
                    if "413" in exc_str:
                        logger.warning("Gonka client error (non-retryable): %s", exc)
                        raise RuntimeError(f"Gonka non-retryable error: {exc}") from exc

                    last_error = exc
                    delay = min(2 ** (attempt - 1) + 0.5, 30.0)
                    logger.warning(
                        "Gonka network error (attempt %d/%d), retry in %.1fs: %s",
                        attempt,
                        self._max_retries,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)

        raise RuntimeError(f"Gonka request failed after {self._max_retries} attempts") from last_error


def _parse_json_object(raw_content: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw_content)
        if isinstance(data, dict):
            return data
        return None
    except json.JSONDecodeError:
        import re

        # Robust fallback for responses with trailing junk (common in non-JSON-mode).
        start = raw_content.find("{")
        if start != -1:
            try:
                parsed, _ = json.JSONDecoder().raw_decode(raw_content[start:])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_content, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(1))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                logger.warning("Failed to parse extracted codeblock JSON: %.200s", raw_content)

        # Non-JSON-mode fallback: extract outermost object from mixed text.
        start = raw_content.find("{")
        end = raw_content.rfind("}")
        if start != -1 and end > start:
            candidate = raw_content[start : end + 1]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        logger.warning("Failed to parse LLM response as JSON: %.200s", raw_content)
        return None


def _is_json_mode_invalid_request(status: int, body: str) -> bool:
    """Return True when provider rejects JSON-mode with generic 400 invalid_request."""
    if status != 400:
        return False
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    err = payload.get("error")
    if not isinstance(err, dict):
        return False
    err_type = str(err.get("type") or "").strip().lower()
    err_code = str(err.get("code") or "").strip().lower()
    return err_type == "invalid_request_error" and err_code == "invalid_request"


def _parse_spo_statements(raw_data: dict[str, Any] | None) -> list[SPOCandidate]:
    if not raw_data:
        return []
    statements = raw_data.get("statements", [])
    if not isinstance(statements, list):
        return []

    parsed: list[SPOCandidate] = []
    for stmt in statements:
        if not isinstance(stmt, dict):
            continue
        payload = _normalize_provider_statement(stmt)
        try:
            parsed.append(SPOCandidate.model_validate(payload))
        except Exception as exc:
            # Last-resort salvage: keep statement even when threshold objects are malformed.
            payload_no_thresholds = dict(payload)
            payload_no_thresholds["thresholds"] = []
            try:
                parsed.append(SPOCandidate.model_validate(payload_no_thresholds))
            except Exception:
                logger.debug("Skipping invalid SPO statement: %s -- %s", payload, exc)
    return parsed


def _normalize_provider_statement(stmt: dict[str, Any]) -> dict[str, Any]:
    """Loose schema mapper from provider payload to strict SPOCandidate fields."""
    payload = dict(stmt)

    alias_map = {
        "quote_start": "source_quote_start",
        "quote_end": "source_quote_end",
        "start": "source_quote_start",
        "end": "source_quote_end",
        "source_quote": "source_quote_uk",
        "subject": "subject_uk",
        "subject_name": "subject_uk",
        "subject_role": "subject_uk",
        "object": "object_uk",
        "object_name": "object_uk",
        "object_role": "object_uk",
        "condition": "condition_text_uk",
        "exception": "exception_text_uk",
        "procedure": "procedure_text_uk",
        "temporal": "temporal_text_uk",
        "sanction": "sanction_text_uk",
    }
    for src, dst in alias_map.items():
        src_val = payload.get(src)
        dst_val = payload.get(dst)
        if src_val not in (None, "") and dst_val in (None, ""):
            payload[dst] = src_val

    if "thresholds" not in payload and isinstance(payload.get("threshold"), dict):
        payload["thresholds"] = [payload["threshold"]]
    thresholds = payload.get("thresholds")
    if not isinstance(thresholds, list):
        thresholds = []
    payload["thresholds"] = [_normalize_threshold_item(item) for item in thresholds if isinstance(item, dict)]

    if not isinstance(payload.get("links"), list):
        payload["links"] = []

    subject_uk = str(payload.get("subject_uk") or "").strip()
    object_uk = str(payload.get("object_uk") or "").strip()
    payload["subject_en"] = str(payload.get("subject_en") or payload.get("actor_en") or subject_uk or "unknown_subject")
    payload["subject_uk"] = subject_uk or payload["subject_en"]
    payload["object_en"] = str(payload.get("object_en") or payload.get("target_en") or object_uk or "unknown_object")
    payload["object_uk"] = object_uk or payload["object_en"]

    payload["predicate"] = str(payload.get("predicate") or payload.get("action_canon") or payload.get("action_raw") or "requires")
    payload["norm_type"] = str(payload.get("norm_type") or payload.get("norm_type_canon") or payload.get("norm_type_raw") or "obligation")

    fact_text = payload.get("fact_text")
    if not isinstance(fact_text, str) or not fact_text.strip():
        fact_text = payload.get("fact_text_en") or payload.get("fact_text_uk") or payload.get("source_quote_uk")
    if not isinstance(fact_text, str) or not fact_text.strip():
        fact_text = f"{payload['subject_uk']} {payload['predicate']} {payload['object_uk']}".strip()
    payload["fact_text"] = fact_text

    confidence = payload.get("confidence")
    if confidence is None:
        confidence = (
            payload.get("confidence_final")
            or payload.get("confidence_extract")
            or payload.get("confidence_verify")
            or 0.7
        )
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0.7
    payload["confidence"] = min(1.0, max(0.0, confidence_value))

    for key in ("source_quote_start", "source_quote_end"):
        value = payload.get(key)
        if value in ("", None):
            payload[key] = None
            continue
        try:
            payload[key] = int(value)
        except (TypeError, ValueError):
            payload[key] = None

    for key in (
        "statement_id",
        "actor_en",
        "actor_uk",
        "target_en",
        "target_uk",
        "beneficiary_en",
        "beneficiary_uk",
        "action_raw",
        "action_canon",
        "norm_type_raw",
        "norm_type_canon",
        "fact_text_en",
        "fact_text_uk",
        "condition_text_uk",
        "exception_text_uk",
        "procedure_text_uk",
        "temporal_text_uk",
        "sanction_text_uk",
        "source_quote_uk",
    ):
        if key in payload and payload[key] is not None and not isinstance(payload[key], str):
            payload[key] = str(payload[key])

    # Drop provider-side alias keys to satisfy SPOCandidate(extra="forbid").
    for key in (
        "subject",
        "subject_name",
        "subject_role",
        "object",
        "object_name",
        "object_role",
        "quote_start",
        "quote_end",
        "start",
        "end",
        "source_quote",
        "condition",
        "exception",
        "procedure",
        "temporal",
        "sanction",
        "threshold",
    ):
        payload.pop(key, None)

    return payload


def _normalize_threshold_item(raw: dict[str, Any]) -> dict[str, Any]:
    metric = raw.get("metric")
    if metric in (None, ""):
        metric = raw.get("type") or ""

    operator = raw.get("operator")
    if operator in (None, ""):
        operator = raw.get("comparator") or ""

    value_decimal = raw.get("value_decimal")
    if value_decimal in (None, ""):
        value_decimal = raw.get("value")
    if value_decimal in (None, ""):
        value_decimal = raw.get("amount")
    if value_decimal not in (None, "") and not isinstance(value_decimal, str):
        value_decimal = str(value_decimal)

    value_text = raw.get("value_text")
    if value_text in (None, "") and value_decimal not in (None, ""):
        value_text = str(value_decimal)
    if value_text not in (None, "") and not isinstance(value_text, str):
        value_text = str(value_text)

    unit = raw.get("unit")
    if unit not in (None, "") and not isinstance(unit, str):
        unit = str(unit)

    applies_to = raw.get("applies_to")
    if applies_to in (None, ""):
        applies_to = raw.get("applicable_to")
    if applies_to not in (None, "") and not isinstance(applies_to, str):
        applies_to = str(applies_to)

    return {
        "metric": str(metric or ""),
        "operator": str(operator or ""),
        "value_decimal": value_decimal if value_decimal not in (None, "") else None,
        "value_text": value_text if value_text not in (None, "") else None,
        "unit": unit if unit not in (None, "") else None,
        "applies_to": applies_to if applies_to not in (None, "") else None,
    }


def _choose_verify_statements(
    *,
    doc_id: str,
    provision_anchor: str,
    statements_pass1: list[SPOCandidate],
    data_verify: dict[str, Any] | None,
) -> tuple[list[SPOCandidate], bool]:
    """Choose pass2 statements; fallback to pass1 on verify schema mismatch."""
    if data_verify is None:
        return statements_pass1, False

    statements_pass2 = _parse_spo_statements(data_verify)
    if statements_pass2:
        return statements_pass2, False

    if statements_pass1:
        logger.warning(
            "SPO verify returned incompatible schema for %s %s; keeping pass1 statements.",
            doc_id,
            provision_anchor,
        )
        return statements_pass1, True
    return statements_pass2, False


def _usage_counts(resp: dict[str, Any]) -> tuple[int, int, float, float, float]:
    usage = resp.get("usage", {})
    if not isinstance(usage, dict):
        usage = {}
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)

    cost_base = float(
        usage.get("base_cost_usd")
        or usage.get("cost_base_usd")
        or usage.get("prompt_cost_usd")
        or 0.0
    )
    cost_platform = float(
        usage.get("platform_cost_usd")
        or usage.get("cost_platform_usd")
        or usage.get("service_cost_usd")
        or 0.0
    )
    total_candidates = [
        usage.get("total_cost_usd"),
        usage.get("cost_total_usd"),
        usage.get("total_cost"),
    ]
    total = 0.0
    for value in total_candidates:
        if value is None:
            continue
        try:
            total = float(value)
            break
        except (TypeError, ValueError):
            continue
    if total <= 0.0:
        total = max(0.0, cost_base + cost_platform)

    return prompt, completion, cost_base, cost_platform, total


def _normalize_statements(statements: list[SPOCandidate]) -> tuple[list[SPOCandidate], list[str], dict[str, int]]:
    normalized: list[SPOCandidate] = []
    reasons: list[str] = []
    stats = {
        "oov_action": 0,
        "oov_norm_type": 0,
        "missing_quote": 0,
        "added_thresholds": 0,
    }

    for stmt in statements:
        # Verify pass may already provide canonical values, but on noisy outputs
        # we fallback to predicate/norm_type when canon/raw are out-of-vocab.
        action_candidates = [
            stmt.action_canon,
            stmt.predicate,
            stmt.action_raw,
        ]
        norm_candidates = [
            stmt.norm_type_canon,
            stmt.norm_type,
            stmt.norm_type_raw,
        ]

        action_canon = "requires"
        action_oov = True
        for candidate in action_candidates:
            if not candidate:
                continue
            c_canon, c_oov = canonicalize_action(candidate)
            action_canon = c_canon
            action_oov = c_oov
            if not c_oov:
                break

        norm_canon = "obligation"
        norm_oov = True
        for candidate in norm_candidates:
            if not candidate:
                continue
            c_canon, c_oov = canonicalize_norm_type(candidate)
            norm_canon = c_canon
            norm_oov = c_oov
            if not c_oov:
                break

        thresholds = list(stmt.thresholds)
        if not thresholds:
            derived = extract_thresholds_from_text(
                "\n".join(
                    part
                    for part in (
                        stmt.condition_text_uk,
                        stmt.fact_text_uk,
                        stmt.source_quote_uk,
                        stmt.object_uk,
                    )
                    if part
                ),
                applies_to=stmt.target_en or stmt.object_en,
            )
            if derived:
                thresholds = derived
                stats["added_thresholds"] += len(derived)

        if action_oov:
            stats["oov_action"] += 1
            reasons.append("oov_action")
        if norm_oov:
            stats["oov_norm_type"] += 1
            reasons.append("oov_norm_type")

        if not stmt.source_quote_uk.strip() or stmt.source_quote_start is None or stmt.source_quote_end is None:
            stats["missing_quote"] += 1
            reasons.append("missing_quote")

        payload = stmt.model_dump(mode="json")
        payload["action_raw"] = stmt.action_raw or stmt.predicate
        payload["action_canon"] = action_canon
        payload["norm_type_raw"] = stmt.norm_type_raw or stmt.norm_type
        payload["norm_type_canon"] = norm_canon
        payload["thresholds"] = [th.model_dump(mode="json") for th in thresholds]

        normalized.append(SPOCandidate.model_validate(payload))

    dedup_reasons = sorted(set(reasons))
    return normalized, dedup_reasons, stats


async def _extract_one_provision(
    client: GonkaClient,
    doc: NPADocument,
    provision: ProvisionSpan,
    *,
    verify_mode: str = "llm",
) -> SPOExtractionResult:
    """Run extraction for one provision (llm or code verify mode)."""

    # -------------------- Pass 1: Extract --------------------
    extract_prompt = build_spo_extract_user_prompt(
        provision_text=provision.text,
        doc_title=doc.card.name,
        doc_type=doc.card.doc_type,
        publisher=", ".join(doc.card.publisher) if doc.card.publisher else "",
        date_acc=doc.card.date_acc,
        provision_citation=provision.citation_label,
    )
    extract_messages = [
        {"role": "system", "content": SPO_EXTRACT_SYSTEM_PROMPT},
        {"role": "user", "content": extract_prompt},
    ]

    t_total = time.monotonic()
    t1 = time.monotonic()
    try:
        resp_extract = await client.chat_completion(
            extract_messages,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.warning("SPO extract failed for %s %s: %s", doc.card.doc_id, provision.anchor_path, exc)
        return SPOExtractionResult(
            doc_id=doc.card.doc_id,
            provision_anchor=provision.anchor_path,
            provision_citation=provision.citation_label,
            statements=[],
            raw_llm_response=str(exc),
            raw_extract_response=str(exc),
            model_id=client.model_id,
            prompt_version=SPO_PROMPT_VERSION,
            low_confidence=True,
            low_confidence_reasons=["extract_failed"],
            latency_ms=int((time.monotonic() - t_total) * 1000),
            pass1_latency_ms=int((time.monotonic() - t1) * 1000),
        )

    pass1_latency_ms = int((time.monotonic() - t1) * 1000)
    usage1_prompt, usage1_completion, cost1_base, cost1_platform, cost1_total = _usage_counts(resp_extract)
    extract_choice = resp_extract.get("choices", [{}])[0]
    raw_extract = extract_choice.get("message", {}).get("content", "")
    data_extract = _parse_json_object(raw_extract)
    statements_pass1 = _parse_spo_statements(data_extract)

    raw_verify = ""
    data_verify: dict[str, Any] | None = None
    usage2_prompt = usage2_completion = 0
    cost2_base = cost2_platform = cost2_total = 0.0
    verify_failed = False
    pass2_latency_ms = 0
    verify_schema_fallback = False
    statements_pass2 = statements_pass1
    verify_report = {
        "input_count": len(statements_pass1),
        "output_count": len(statements_pass1),
        "dropped_count": 0,
    }

    if verify_mode == "llm":
        # -------------------- Pass 2: Verify + normalize --------------------
        verify_input_json = json.dumps(
            {"statements": [s.model_dump(mode="json") for s in statements_pass1]},
            ensure_ascii=False,
        )
        verify_prompt = build_spo_verify_user_prompt(
            provision_text=provision.text,
            extracted_json=verify_input_json,
            provision_citation=provision.citation_label,
        )
        verify_messages = [
            {"role": "system", "content": SPO_VERIFY_SYSTEM_PROMPT},
            {"role": "user", "content": verify_prompt},
        ]

        t2 = time.monotonic()
        try:
            resp_verify = await client.chat_completion(
                verify_messages,
                response_format={"type": "json_object"},
            )
            pass2_latency_ms = int((time.monotonic() - t2) * 1000)
            usage2_prompt, usage2_completion, cost2_base, cost2_platform, cost2_total = _usage_counts(resp_verify)
            verify_choice = resp_verify.get("choices", [{}])[0]
            raw_verify = verify_choice.get("message", {}).get("content", "")
            data_verify = _parse_json_object(raw_verify)
        except Exception as exc:
            pass2_latency_ms = int((time.monotonic() - t2) * 1000)
            verify_failed = True
            raw_verify = str(exc)
            logger.warning("SPO verify failed for %s %s: %s", doc.card.doc_id, provision.anchor_path, exc)

        statements_pass2, verify_schema_fallback = _choose_verify_statements(
            doc_id=doc.card.doc_id,
            provision_anchor=provision.anchor_path,
            statements_pass1=statements_pass1,
            data_verify=data_verify,
        )

        verify_report = {}
        if isinstance(data_verify, dict):
            raw_report = data_verify.get("verify_report")
            if isinstance(raw_report, dict):
                verify_report = raw_report
        if not verify_report:
            verify_report = {
                "input_count": len(statements_pass1),
                "output_count": len(statements_pass2),
                "dropped_count": max(0, len(statements_pass1) - len(statements_pass2)),
            }
    else:
        verify_report["mode"] = "code"

    normalized, norm_reasons, norm_stats = _normalize_statements(statements_pass2)

    low_confidence_reasons: list[str] = []
    low_confidence = False
    if verify_failed:
        low_confidence = True
        low_confidence_reasons.append("verify_failed")
    if verify_schema_fallback:
        low_confidence = True
        low_confidence_reasons.append("verify_schema_fallback")
    if not normalized:
        low_confidence = True
        low_confidence_reasons.append("no_statements")
    if norm_stats["missing_quote"] > 0:
        low_confidence = True
        low_confidence_reasons.append("missing_quote")

    if isinstance(data_verify, dict):
        verify_low_conf = bool(data_verify.get("low_confidence", False))
        if verify_low_conf:
            low_confidence = True
        verify_reasons = data_verify.get("low_confidence_reasons", [])
        if isinstance(verify_reasons, list):
            for reason in verify_reasons:
                if isinstance(reason, str) and reason.strip():
                    low_confidence_reasons.append(reason.strip())

    low_confidence_reasons.extend(norm_reasons)
    low_confidence_reasons = sorted(set(low_confidence_reasons))

    total_latency_ms = int((time.monotonic() - t_total) * 1000)
    total_prompt_tokens = usage1_prompt + usage2_prompt
    total_completion_tokens = usage1_completion + usage2_completion
    total_cost_base = cost1_base + cost2_base
    total_cost_platform = cost1_platform + cost2_platform
    total_cost = cost1_total + cost2_total
    if total_cost <= 0.0:
        total_cost = max(0.0, total_cost_base + total_cost_platform)

    normalization_report = {
        "oov_action": norm_stats["oov_action"],
        "oov_norm_type": norm_stats["oov_norm_type"],
        "missing_quote": norm_stats["missing_quote"],
        "added_thresholds": norm_stats["added_thresholds"],
    }

    return SPOExtractionResult(
        doc_id=doc.card.doc_id,
        provision_anchor=provision.anchor_path,
        provision_citation=provision.citation_label,
        statements=normalized,
        raw_llm_response=raw_verify or raw_extract,
        raw_extract_response=raw_extract,
        raw_verify_response=raw_verify,
        model_id=client.model_id,
        prompt_version=SPO_PROMPT_VERSION,
        extract_passes=2 if verify_mode == "llm" else 1,
        verify_report_json=json.dumps(verify_report, ensure_ascii=False),
        normalization_report_json=json.dumps(normalization_report, ensure_ascii=False),
        low_confidence=low_confidence,
        low_confidence_reasons=low_confidence_reasons,
        latency_ms=total_latency_ms,
        pass1_latency_ms=pass1_latency_ms,
        pass2_latency_ms=pass2_latency_ms,
        token_count_prompt=total_prompt_tokens,
        token_count_completion=total_completion_tokens,
        token_count_prompt_extract=usage1_prompt,
        token_count_completion_extract=usage1_completion,
        token_count_prompt_verify=usage2_prompt,
        token_count_completion_verify=usage2_completion,
        cost_base_usd=total_cost_base,
        cost_platform_usd=total_cost_platform,
        cost_total_usd=total_cost,
    )


async def extract_spo_for_documents(
    client: GonkaClient,
    documents: list[NPADocument],
    provisions_by_doc: dict[str, list[ProvisionSpan]],
    *,
    results_dir: Path,
    task_batch_size: int = 1000,
    verify_mode: str = "llm",
) -> tuple[int, set[str]]:
    """Extract SPO for all provisions across documents.

    Results are written to ``results_dir/{doc_id}.jsonl`` with one JSON line per provision.
    Returns ``(total_statement_count, failed_doc_ids)``.
    """
    work_items: list[tuple[NPADocument, ProvisionSpan]] = []
    for doc in documents:
        shard_dir = results_dir / _shard_prefix(doc.card.doc_id)
        shard_dir.mkdir(parents=True, exist_ok=True)
        out_path = shard_dir / f"{doc.card.doc_id}.jsonl"
        if out_path.exists():
            out_path.unlink()
        provisions = provisions_by_doc.get(doc.card.doc_id, [])
        for prov in provisions:
            work_items.append((doc, prov))

    if not work_items:
        return 0, set()

    total_statements = 0
    failed_doc_ids: set[str] = set()
    batch_size = max(1, task_batch_size)

    for i in range(0, len(work_items), batch_size):
        chunk = work_items[i : i + batch_size]
        tasks = [
            asyncio.create_task(
                _extract_one_provision(client, doc, prov, verify_mode=verify_mode),
            )
            for doc, prov in chunk
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        doc_buffers: dict[str, list[dict[str, Any]]] = {}
        for (doc, prov), result in zip(chunk, results, strict=True):
            if isinstance(result, Exception):
                logger.warning("Task failed for %s %s: %s", doc.card.doc_id, prov.anchor_path, result)
                failed_doc_ids.add(doc.card.doc_id)
                continue

            if not result.statements and "failed" in result.raw_llm_response.lower():
                failed_doc_ids.add(result.doc_id)

            row = result.model_dump(mode="json")
            doc_buffers.setdefault(result.doc_id, []).append(row)
            total_statements += len(result.statements)

        for doc_id, rows in doc_buffers.items():
            out_path = results_dir / _shard_prefix(doc_id) / f"{doc_id}.jsonl"
            with open(out_path, "a", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    if failed_doc_ids:
        logger.warning(
            "%d documents had failed provisions and will NOT be marked as done: %s",
            len(failed_doc_ids),
            ", ".join(sorted(failed_doc_ids)[:10]) + ("..." if len(failed_doc_ids) > 10 else ""),
        )

    return total_statements, failed_doc_ids
