"""Stage 3: Async LLM-based 2-pass extraction via Gonka (OpenAI-compatible API).

Pass 1: Extract statements.
Pass 2: Verify + normalize extracted statements against the same provision.

Policy: mark-and-continue for low confidence (no extra LLM passes).
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import aiohttp

from polisyos.common.logger import get_logger
from polisyos.lex.batch.canonicalizers import (
    canonicalize_action,
    canonicalize_norm_type,
    extract_thresholds_from_text,
)
from polisyos.lex.batch.provisions_io import _shard_prefix
from polisyos.lex.batch.spo_prompts import (
    SPO_EXTRACT_BATCH_SYSTEM_PROMPT,
    SPO_EXTRACT_SYSTEM_PROMPT,
    SPO_LIGHT_BATCH_SYSTEM_PROMPT,
    SPO_LIGHT_PROMPT_VERSION,
    SPO_LIGHT_SYSTEM_PROMPT,
    SPO_PROMPT_VERSION,
    SPO_VERIFY_SYSTEM_PROMPT,
    build_spo_extract_batch_user_prompt,
    build_spo_extract_user_prompt,
    build_spo_light_batch_user_prompt,
    build_spo_light_user_prompt,
    build_spo_verify_user_prompt,
)
from polisyos.lex.batch.structurer import ProvisionSpan
from polisyos.lex.batch.xml_parser import NPADocument
from polisyos.lex.knowledge.types import SPOCandidate, SPOExtractionResult

logger = get_logger(__name__)
_MAX_RETRY_AFTER_SECONDS = 30.0


def _retry_delay_seconds(*, attempt: int, retry_after: str | None) -> float:
    """Compute retry delay honoring Retry-After header when present."""
    if retry_after:
        try:
            parsed = float(retry_after.strip())
            if parsed > 0:
                return min(parsed, _MAX_RETRY_AFTER_SECONDS) * random.uniform(0.85, 1.2)
        except ValueError:
            pass
    return min(2 ** (attempt - 1) + 0.5, _MAX_RETRY_AFTER_SECONDS) * random.uniform(0.85, 1.25)


class _SlidingWindowLimiter:
    """Async sliding-window rate limiter with optional jitter and 429 cooldown."""

    __slots__ = ("_max", "_window", "_lock", "_timestamps", "_backoff_until", "_jitter_ratio")

    def __init__(self, max_requests: int, window: float = 1.0, *, jitter_ratio: float = 0.0) -> None:
        self._max = max(1, int(max_requests))
        self._window = max(0.01, float(window))
        self._lock = asyncio.Lock()
        self._timestamps: deque[float] = deque()
        self._backoff_until = 0.0
        self._jitter_ratio = max(0.0, float(jitter_ratio))

    async def acquire(self) -> float:
        waited = 0.0
        while True:
            async with self._lock:
                now = time.monotonic()
                if now < self._backoff_until:
                    wait = self._backoff_until - now
                else:
                    cutoff = now - self._window
                    while self._timestamps and self._timestamps[0] <= cutoff:
                        self._timestamps.popleft()
                    if len(self._timestamps) < self._max:
                        self._timestamps.append(time.monotonic())
                        return waited
                    wait = self._timestamps[0] + self._window - now
            if self._jitter_ratio > 0.0 and wait > 0.05:
                wait *= 1.0 + random.uniform(-self._jitter_ratio, self._jitter_ratio)
            started = time.monotonic()
            await asyncio.sleep(max(0.01, wait))
            waited += time.monotonic() - started

    async def penalise(self, penalty_seconds: float = 5.0) -> None:
        async with self._lock:
            future = time.monotonic() + penalty_seconds - self._window
            self._backoff_until = max(self._backoff_until, time.monotonic() + max(0.1, penalty_seconds))
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
        shared_limiter: _SlidingWindowLimiter | None = None,
        circuit_failures: int = 3,
        circuit_reset_seconds: float = 12.0,
    ) -> None:
        self._api_key = api_key
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._shared_limiter = shared_limiter
        self._circuit_failures = max(1, int(circuit_failures))
        self._circuit_reset_seconds = max(1.0, float(circuit_reset_seconds))
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0
        self._limiter = _SlidingWindowLimiter(
            max_requests=1,
            window=(1.0 / max(0.001, float(rate_limit_rps))),
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

    @property
    def json_mode_disabled(self) -> bool:
        return self._json_mode_disabled

    def disable_json_mode(self) -> None:
        self._json_mode_disabled = True

    def set_cache(self, cache: object | None) -> None:
        """Attach an optional SPOCache instance for response caching."""
        self._cache = cache  # type: ignore[attr-defined]

    def is_available(self) -> bool:
        return time.monotonic() >= self._circuit_open_until

    def backoff_until(self) -> float:
        return self._circuit_open_until

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures < self._circuit_failures:
            return
        jitter = random.uniform(0.85, 1.25)
        self._circuit_open_until = max(
            self._circuit_open_until,
            time.monotonic() + (self._circuit_reset_seconds * jitter),
        )

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
            if self._shared_limiter is not None:
                await self._shared_limiter.acquire()
            await self._limiter.acquire()
            async with self._semaphore:
                payload = dict(payload_base)
                if response_format and not self._json_mode_disabled:
                    payload["response_format"] = response_format
                try:
                    async with self._session.post(self._url, json=payload) as resp:
                        if resp.status == 200:
                            self._record_success()
                            return await resp.json()

                        body = await resp.text()
                        if (
                            "response_format" in payload
                            and _is_json_mode_invalid_request(resp.status, body)
                        ):
                            if not self._json_mode_disabled:
                                logger.warning(
                                    "Gonka 400 invalid_request with response_format; "
                                    "retrying without JSON-mode for subsequent requests."
                                )
                            self.disable_json_mode()
                            payload.pop("response_format", None)
                            # Known compatibility fallback; do not spend retry budget.
                            continue

                        if resp.status < 500 and resp.status not in (429,):
                            logger.warning("Gonka {} (non-retryable): {}", resp.status, body[:200])
                            raise RuntimeError(
                                f"Gonka non-retryable error: HTTP {resp.status}: {body[:500]}"
                            )

                        delay = _retry_delay_seconds(
                            attempt=attempt,
                            retry_after=resp.headers.get("Retry-After"),
                        )
                        if resp.status == 429:
                            self._record_failure()
                            await self._limiter.penalise(delay)
                            if self._shared_limiter is not None:
                                await self._shared_limiter.penalise(min(delay, _MAX_RETRY_AFTER_SECONDS))
                        elif resp.status >= 500:
                            self._record_failure()

                        logger.warning(
                            "Gonka {} (attempt {}/{}), retry in {:.1f}s: {}",
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
                        logger.warning("Gonka client error (non-retryable): {}", exc)
                        raise RuntimeError(f"Gonka non-retryable error: {exc}") from exc

                    last_error = exc
                    self._record_failure()
                    delay = min(2 ** (attempt - 1) + 0.5, 30.0)
                    logger.warning(
                        "Gonka network error (attempt {}/{}), retry in {:.1f}s: {}",
                        attempt,
                        self._max_retries,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)

        raise RuntimeError(f"Gonka request failed after {self._max_retries} attempts") from last_error


class GonkaClientPool:
    """Least-loaded pool of Gonka clients, one per API key."""

    def __init__(
        self,
        *,
        api_keys: list[str],
        base_url: str,
        model: str,
        disable_json_mode: bool = False,
        max_concurrent: int = 50,
        rate_limit_rps: float = 100.0,
        temperature: float = 0.1,
        max_retries: int = 7,
    ) -> None:
        cleaned = [str(key).strip() for key in api_keys if str(key).strip()]
        if not cleaned:
            raise ValueError("GonkaClientPool requires at least one API key")
        total_rps = max(0.001, float(rate_limit_rps) * max(1, len(cleaned)))
        self._shared_limiter = _SlidingWindowLimiter(
            max_requests=1,
            window=(1.0 / total_rps),
            jitter_ratio=0.12,
        )
        self._clients = [
            GonkaClient(
                api_key=key,
                base_url=base_url,
                model=model,
                disable_json_mode=disable_json_mode,
                max_concurrent=max_concurrent,
                rate_limit_rps=rate_limit_rps,
                temperature=temperature,
                max_retries=max_retries,
                shared_limiter=self._shared_limiter,
            )
            for key in cleaned
        ]
        self._in_flight = [0 for _ in self._clients]
        self._selection_lock = asyncio.Lock()
        self._json_mode_disabled = disable_json_mode
        self._rr_cursor = 0

    @property
    def model_id(self) -> str:
        return self._clients[0].model_id

    @property
    def key_count(self) -> int:
        return len(self._clients)

    def set_cache(self, cache: object | None) -> None:
        for client in self._clients:
            client.set_cache(cache)

    def disable_json_mode(self) -> None:
        if self._json_mode_disabled:
            return
        self._json_mode_disabled = True
        for client in self._clients:
            client.disable_json_mode()

    async def __aenter__(self) -> "GonkaClientPool":
        for client in self._clients:
            await client.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        for client in self._clients:
            await client.__aexit__(*exc)

    async def _acquire_client_index(self) -> int:
        while True:
            async with self._selection_lock:
                available = [i for i, client in enumerate(self._clients) if client.is_available()]
                if available:
                    min_load = min(self._in_flight[i] for i in available)
                    tied = [i for i in available if self._in_flight[i] == min_load]
                    tied.sort()
                    offset = self._rr_cursor % len(tied)
                    idx = tied[offset]
                    self._rr_cursor = (self._rr_cursor + 1) % max(1, len(self._clients))
                    self._in_flight[idx] += 1
                    return idx
                earliest = min((client.backoff_until() for client in self._clients), default=time.monotonic() + 0.25)
            wait_for = max(0.05, earliest - time.monotonic())
            await asyncio.sleep(wait_for * random.uniform(0.85, 1.2))

    async def _release_client_index(self, idx: int) -> None:
        async with self._selection_lock:
            self._in_flight[idx] = max(0, self._in_flight[idx] - 1)

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        response_format: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        idx = await self._acquire_client_index()
        try:
            effective_response_format = None if self._json_mode_disabled else response_format
            result = await self._clients[idx].chat_completion(
                messages,
                response_format=effective_response_format,
            )
            if self._clients[idx].json_mode_disabled:
                self.disable_json_mode()
            return result
        finally:
            await self._release_client_index(idx)


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
                logger.warning("Failed to parse extracted codeblock JSON: {}", raw_content[:200])

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

        logger.warning("Failed to parse LLM response as JSON: {}", raw_content[:200])
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
                logger.debug("Skipping invalid SPO statement: {} -- {}", payload, exc)
    return parsed


def _parse_light_statements(raw_data: dict[str, Any] | None) -> list[SPOCandidate]:
    """Parse 7-field light JSON into full SPOCandidate via code enrichment."""
    if not raw_data:
        return []
    statements = raw_data.get("statements", [])
    if not isinstance(statements, list):
        return []

    parsed: list[SPOCandidate] = []
    for stmt in statements:
        if not isinstance(stmt, dict):
            continue

        subject_uk = str(stmt.get("subject_uk") or "").strip()
        predicate = str(stmt.get("predicate") or "requires").strip()
        object_uk = str(stmt.get("object_uk") or "").strip()
        norm_type = str(stmt.get("norm_type") or "obligation").strip()
        fact_text = str(stmt.get("fact_text") or "").strip()
        source_quote_uk = str(stmt.get("source_quote_uk") or "").strip()

        confidence = stmt.get("confidence")
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            confidence_value = 0.7
        confidence_value = min(1.0, max(0.0, confidence_value))

        if not subject_uk and not object_uk:
            continue

        # Code-based canonicalization (no LLM verify pass needed).
        action_canon, action_oov = canonicalize_action(predicate)
        norm_type_canon, norm_oov = canonicalize_norm_type(norm_type)

        # Extract thresholds from text fields.
        threshold_text = "\n".join(part for part in (fact_text, source_quote_uk, object_uk) if part)
        thresholds = extract_thresholds_from_text(threshold_text, applies_to=object_uk)

        payload: dict[str, Any] = {
            "subject_en": subject_uk,
            "subject_uk": subject_uk or "unknown_subject",
            "predicate": predicate,
            "object_en": object_uk,
            "object_uk": object_uk or "unknown_object",
            "fact_text": fact_text or f"{subject_uk} {predicate} {object_uk}".strip(),
            "confidence": confidence_value,
            "norm_type": norm_type,
            "action_raw": predicate,
            "action_canon": action_canon,
            "norm_type_raw": norm_type,
            "norm_type_canon": norm_type_canon,
            "source_quote_uk": source_quote_uk,
            "thresholds": [th.model_dump(mode="json") for th in thresholds],
        }
        try:
            parsed.append(SPOCandidate.model_validate(payload))
        except Exception as exc:
            logger.debug("Skipping invalid light SPO statement: {} -- {}", payload, exc)
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
            "SPO verify returned incompatible schema for {} {}; keeping pass1 statements.",
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


@dataclass(frozen=True, slots=True)
class _BatchProvisionItem:
    item_id: str
    doc: NPADocument
    provision: ProvisionSpan


def _split_int(total: int, parts: int) -> list[int]:
    if parts <= 0:
        return []
    base = total // parts
    remainder = total % parts
    return [base + (1 if idx < remainder else 0) for idx in range(parts)]


def _split_float(total: float, parts: int) -> list[float]:
    if parts <= 0:
        return []
    if parts == 1:
        return [total]
    share = total / parts
    return [share for _ in range(parts)]


def _estimate_request_item_chars(doc: NPADocument, provision: ProvisionSpan) -> int:
    return (
        len(provision.text)
        + len(provision.citation_label or "")
        + len(doc.card.name or "")
        + len(doc.card.doc_type or "")
        + 128
    )


def _group_request_items(
    items: list[tuple[NPADocument, ProvisionSpan]],
    *,
    request_batch_size: int,
    request_batch_chars: int | None,
) -> list[list[tuple[NPADocument, ProvisionSpan]]]:
    groups: list[list[tuple[NPADocument, ProvisionSpan]]] = []
    current: list[tuple[NPADocument, ProvisionSpan]] = []
    current_chars = 0
    max_items = max(1, request_batch_size)
    max_chars = int(request_batch_chars) if request_batch_chars is not None else 0

    for item in items:
        item_chars = _estimate_request_item_chars(item[0], item[1])
        would_overflow_items = len(current) >= max_items
        would_overflow_chars = bool(
            current
            and max_chars > 0
            and current_chars + item_chars > max_chars
        )
        if would_overflow_items or would_overflow_chars:
            groups.append(current)
            current = []
            current_chars = 0
        current.append(item)
        current_chars += item_chars

    if current:
        groups.append(current)
    return groups


def _materialize_fallback_row(
    base_row: dict[str, Any],
    *,
    error_message: str,
    timeout: bool,
) -> dict[str, Any]:
    row = json.loads(json.dumps(base_row, ensure_ascii=False))
    existing_reasons = row.get("low_confidence_reasons")
    reasons = list(existing_reasons) if isinstance(existing_reasons, list) else []
    reason_code = "llm_group_timeout_fallback" if timeout else "llm_group_error_fallback"
    if reason_code not in reasons:
        reasons.append(reason_code)
    row["low_confidence"] = True
    row["low_confidence_reasons"] = reasons
    row["raw_llm_response"] = error_message[:1000]
    row["raw_extract_response"] = error_message[:1000]
    row["extraction_source"] = "llm_timeout_fallback" if timeout else "llm_error_fallback"
    return row


def _coerce_batch_item_payload(item_payload: Any) -> dict[str, Any] | None:
    if isinstance(item_payload, list):
        return {"statements": item_payload}
    if not isinstance(item_payload, dict):
        return None

    statements = item_payload.get("statements")
    payload: dict[str, Any] = {
        "statements": statements if isinstance(statements, list) else [],
    }
    for key in ("low_confidence", "low_confidence_reasons", "verify_report"):
        if key in item_payload:
            payload[key] = item_payload[key]
    return payload


def _parse_batch_extract_payload(raw_data: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not raw_data:
        return {}

    parsed: dict[str, dict[str, Any]] = {}
    raw_items = raw_data.get("items")
    if raw_items is None:
        raw_items = raw_data.get("results")

    if isinstance(raw_items, list):
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            raw_id = raw_item.get("id") or raw_item.get("item_id")
            if not isinstance(raw_id, str):
                continue
            item_id = raw_id.strip()
            if not item_id:
                continue
            payload = _coerce_batch_item_payload(raw_item)
            if payload is not None:
                parsed[item_id] = payload
        return parsed

    if isinstance(raw_items, dict):
        for raw_id, item_payload in raw_items.items():
            if not isinstance(raw_id, str):
                continue
            item_id = raw_id.strip()
            if not item_id:
                continue
            payload = _coerce_batch_item_payload(item_payload)
            if payload is not None:
                parsed[item_id] = payload
        return parsed

    return parsed


def _build_extract_failed_result(
    *,
    client: GonkaClient,
    doc: NPADocument,
    provision: ProvisionSpan,
    error_message: str,
    pass1_latency_ms: int,
) -> SPOExtractionResult:
    return SPOExtractionResult(
        doc_id=doc.card.doc_id,
        provision_anchor=provision.anchor_path,
        provision_citation=provision.citation_label,
        statements=[],
        raw_llm_response=error_message,
        raw_extract_response=error_message,
        model_id=client.model_id,
        prompt_version=SPO_PROMPT_VERSION,
        low_confidence=True,
        low_confidence_reasons=["extract_failed"],
        latency_ms=pass1_latency_ms,
        pass1_latency_ms=pass1_latency_ms,
    )


async def _finalize_provision_from_pass1(
    client: GonkaClient,
    doc: NPADocument,
    provision: ProvisionSpan,
    *,
    statements_pass1: list[SPOCandidate],
    raw_extract: str,
    pass1_latency_ms: int,
    usage1_prompt: int,
    usage1_completion: int,
    cost1_base: float,
    cost1_platform: float,
    cost1_total: float,
    verify_mode: str = "llm",
) -> SPOExtractionResult:
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
            logger.warning("SPO verify failed for {} {}: {}", doc.card.doc_id, provision.anchor_path, exc)

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
        latency_ms=pass1_latency_ms + pass2_latency_ms,
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

    t1 = time.monotonic()
    try:
        resp_extract = await client.chat_completion(
            extract_messages,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.warning("SPO extract failed for {} {}: {}", doc.card.doc_id, provision.anchor_path, exc)
        return _build_extract_failed_result(
            client=client,
            doc=doc,
            provision=provision,
            error_message=str(exc),
            pass1_latency_ms=int((time.monotonic() - t1) * 1000),
        )

    pass1_latency_ms = int((time.monotonic() - t1) * 1000)
    usage1_prompt, usage1_completion, cost1_base, cost1_platform, cost1_total = _usage_counts(resp_extract)
    extract_choice = resp_extract.get("choices", [{}])[0]
    raw_extract = extract_choice.get("message", {}).get("content", "")
    data_extract = _parse_json_object(raw_extract)
    statements_pass1 = _parse_spo_statements(data_extract)

    return await _finalize_provision_from_pass1(
        client,
        doc,
        provision,
        statements_pass1=statements_pass1,
        raw_extract=raw_extract,
        pass1_latency_ms=pass1_latency_ms,
        usage1_prompt=usage1_prompt,
        usage1_completion=usage1_completion,
        cost1_base=cost1_base,
        cost1_platform=cost1_platform,
        cost1_total=cost1_total,
        verify_mode=verify_mode,
    )


async def _extract_one_provision_light(
    client: GonkaClient,
    doc: NPADocument,
    provision: ProvisionSpan,
) -> SPOExtractionResult:
    """Single-provision light extraction: 1-pass, 7-field schema, code canonicalization."""
    # --- Cache lookup ---
    cache = getattr(client, "_cache", None)
    if cache is not None:
        cached = cache.get(provision.text, doc.card.doc_type, client.model_id)
        if cached is not None:
            statements = _parse_light_statements(cached)
            return SPOExtractionResult(
                doc_id=doc.card.doc_id,
                provision_anchor=provision.anchor_path,
                provision_citation=provision.citation_label,
                statements=statements,
                raw_llm_response=json.dumps(cached, ensure_ascii=False),
                raw_extract_response=json.dumps(cached, ensure_ascii=False),
                model_id=client.model_id,
                prompt_version=SPO_LIGHT_PROMPT_VERSION,
                extract_passes=1,
                extraction_source="cache",
                low_confidence=not statements,
                low_confidence_reasons=["no_statements"] if not statements else [],
                latency_ms=0,
                pass1_latency_ms=0,
            )

    user_prompt = build_spo_light_user_prompt(
        provision_text=provision.text,
        doc_title=doc.card.name,
        doc_type=doc.card.doc_type,
        publisher=", ".join(doc.card.publisher) if doc.card.publisher else "",
        date_acc=doc.card.date_acc,
        provision_citation=provision.citation_label,
    )
    messages = [
        {"role": "system", "content": SPO_LIGHT_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    t1 = time.monotonic()
    try:
        resp = await client.chat_completion(
            messages,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.warning("SPO light extract failed for {} {}: {}", doc.card.doc_id, provision.anchor_path, exc)
        return _build_extract_failed_result(
            client=client,
            doc=doc,
            provision=provision,
            error_message=str(exc),
            pass1_latency_ms=int((time.monotonic() - t1) * 1000),
        )

    latency_ms = int((time.monotonic() - t1) * 1000)
    usage_prompt, usage_completion, cost_base, cost_platform, cost_total = _usage_counts(resp)
    choice = resp.get("choices", [{}])[0]
    raw_content = choice.get("message", {}).get("content", "")
    data = _parse_json_object(raw_content)

    # --- Cache store ---
    if cache is not None and data is not None:
        cache.put(provision.text, doc.card.doc_type, client.model_id, data)

    statements = _parse_light_statements(data)

    # Code-based normalization (thresholds already extracted in _parse_light_statements).
    norm_reasons: list[str] = []
    norm_stats = {"oov_action": 0, "oov_norm_type": 0, "missing_quote": 0}
    for stmt in statements:
        _, action_oov = canonicalize_action(stmt.predicate)
        _, norm_oov = canonicalize_norm_type(stmt.norm_type)
        if action_oov:
            norm_stats["oov_action"] += 1
            norm_reasons.append("oov_action")
        if norm_oov:
            norm_stats["oov_norm_type"] += 1
            norm_reasons.append("oov_norm_type")
        if not stmt.source_quote_uk.strip():
            norm_stats["missing_quote"] += 1
            norm_reasons.append("missing_quote")

    low_confidence = not statements
    low_confidence_reasons = sorted(set(norm_reasons))
    if not statements:
        low_confidence_reasons.append("no_statements")

    return SPOExtractionResult(
        doc_id=doc.card.doc_id,
        provision_anchor=provision.anchor_path,
        provision_citation=provision.citation_label,
        statements=statements,
        raw_llm_response=raw_content,
        raw_extract_response=raw_content,
        model_id=client.model_id,
        prompt_version=SPO_LIGHT_PROMPT_VERSION,
        extract_passes=1,
        normalization_report_json=json.dumps(norm_stats, ensure_ascii=False),
        low_confidence=low_confidence,
        low_confidence_reasons=low_confidence_reasons,
        latency_ms=latency_ms,
        pass1_latency_ms=latency_ms,
        token_count_prompt=usage_prompt,
        token_count_completion=usage_completion,
        token_count_prompt_extract=usage_prompt,
        token_count_completion_extract=usage_completion,
        cost_base_usd=cost_base,
        cost_platform_usd=cost_platform,
        cost_total_usd=cost_total,
    )


async def _run_single_extractions(
    client: GonkaClient,
    entries: list[_BatchProvisionItem],
    *,
    verify_mode: str = "llm",
    extract_mode: str = "full",
) -> list[SPOExtractionResult]:
    if extract_mode == "light":
        tasks = [
            asyncio.create_task(
                _extract_one_provision_light(client, entry.doc, entry.provision),
            )
            for entry in entries
        ]
    else:
        tasks = [
            asyncio.create_task(
                _extract_one_provision(
                    client,
                    entry.doc,
                    entry.provision,
                    verify_mode=verify_mode,
                ),
            )
            for entry in entries
        ]
    settled = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[SPOExtractionResult] = []
    for entry, result in zip(entries, settled, strict=True):
        if isinstance(result, Exception):
            logger.warning(
                "Single-request fallback crashed for {} {}: {}",
                entry.doc.card.doc_id,
                entry.provision.anchor_path,
                result,
            )
            results.append(
                _build_extract_failed_result(
                    client=client,
                    doc=entry.doc,
                    provision=entry.provision,
                    error_message=str(result),
                    pass1_latency_ms=0,
                ),
            )
            continue
        results.append(result)
    return results


async def _extract_batch_provisions(
    client: GonkaClient,
    batch_items: list[tuple[NPADocument, ProvisionSpan]],
    *,
    verify_mode: str = "llm",
) -> list[SPOExtractionResult]:
    entries = [
        _BatchProvisionItem(
            item_id=f"item_{idx:04d}",
            doc=doc,
            provision=provision,
        )
        for idx, (doc, provision) in enumerate(batch_items)
    ]
    if not entries:
        return []
    if len(entries) == 1:
        return await _run_single_extractions(client, entries, verify_mode=verify_mode)

    prompt_items = [
        {
            "id": entry.item_id,
            "doc_title": entry.doc.card.name,
            "doc_type": entry.doc.card.doc_type,
            "publisher": ", ".join(entry.doc.card.publisher) if entry.doc.card.publisher else "",
            "date_acc": entry.doc.card.date_acc,
            "provision_citation": entry.provision.citation_label,
            "provision_text": entry.provision.text,
        }
        for entry in entries
    ]
    extract_messages = [
        {"role": "system", "content": SPO_EXTRACT_BATCH_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_spo_extract_batch_user_prompt(items=prompt_items),
        },
    ]

    t1 = time.monotonic()
    try:
        resp_extract = await client.chat_completion(
            extract_messages,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.warning(
            "SPO batched extract failed for {} provisions; fallback to single requests: {}",
            len(entries),
            exc,
        )
        return await _run_single_extractions(client, entries, verify_mode=verify_mode)

    pass1_latency_ms = int((time.monotonic() - t1) * 1000)
    usage1_prompt, usage1_completion, cost1_base, cost1_platform, cost1_total = _usage_counts(resp_extract)
    extract_choice = resp_extract.get("choices", [{}])[0]
    raw_extract = extract_choice.get("message", {}).get("content", "")
    data_extract = _parse_json_object(raw_extract)
    payload_by_id = _parse_batch_extract_payload(data_extract)
    if not payload_by_id:
        logger.warning(
            "SPO batched extract returned incompatible schema for {} provisions; fallback to singles.",
            len(entries),
        )
        return await _run_single_extractions(client, entries, verify_mode=verify_mode)

    prompt_parts = _split_int(usage1_prompt, len(entries))
    completion_parts = _split_int(usage1_completion, len(entries))
    cost_base_parts = _split_float(cost1_base, len(entries))
    cost_platform_parts = _split_float(cost1_platform, len(entries))
    cost_total_parts = _split_float(cost1_total, len(entries))

    entry_by_id = {entry.item_id: entry for entry in entries}
    scheduled_ids: list[str] = []
    scheduled_tasks: list[asyncio.Task[SPOExtractionResult]] = []

    for idx, entry in enumerate(entries):
        item_payload = payload_by_id.get(entry.item_id)
        if item_payload is None:
            continue
        statements_pass1 = _parse_spo_statements(item_payload)
        raw_item_extract = json.dumps(
            {
                "id": entry.item_id,
                "statements": item_payload.get("statements", []),
            },
            ensure_ascii=False,
        )
        scheduled_ids.append(entry.item_id)
        scheduled_tasks.append(
            asyncio.create_task(
                _finalize_provision_from_pass1(
                    client,
                    entry.doc,
                    entry.provision,
                    statements_pass1=statements_pass1,
                    raw_extract=raw_item_extract,
                    pass1_latency_ms=pass1_latency_ms,
                    usage1_prompt=prompt_parts[idx],
                    usage1_completion=completion_parts[idx],
                    cost1_base=cost_base_parts[idx],
                    cost1_platform=cost_platform_parts[idx],
                    cost1_total=cost_total_parts[idx],
                    verify_mode=verify_mode,
                ),
            ),
        )

    settled = await asyncio.gather(*scheduled_tasks, return_exceptions=True)
    results_by_id: dict[str, SPOExtractionResult] = {}
    for item_id, result in zip(scheduled_ids, settled, strict=True):
        if isinstance(result, Exception):
            entry = entry_by_id[item_id]
            logger.warning(
                "Batched finalize failed for {} {}; fallback to single request: {}",
                entry.doc.card.doc_id,
                entry.provision.anchor_path,
                result,
            )
            fallback = await _run_single_extractions(
                client,
                [entry],
                verify_mode=verify_mode,
            )
            results_by_id[item_id] = fallback[0]
            continue
        results_by_id[item_id] = result

    for entry in entries:
        if entry.item_id in results_by_id:
            continue
        logger.warning(
            "Batched extract missing item id={} for {} {}; fallback to single request.",
            entry.item_id,
            entry.doc.card.doc_id,
            entry.provision.anchor_path,
        )
        fallback = await _run_single_extractions(
            client,
            [entry],
            verify_mode=verify_mode,
        )
        results_by_id[entry.item_id] = fallback[0]

    return [results_by_id[entry.item_id] for entry in entries]


async def _extract_batch_provisions_light(
    client: GonkaClient,
    batch_items: list[tuple[NPADocument, ProvisionSpan]],
) -> list[SPOExtractionResult]:
    """Batch light extraction: 1-pass, 7-field schema, code canonicalization.

    Integrates with SPOCache: cached provisions are resolved immediately,
    only uncached provisions are sent to LLM in a single batch request.
    """
    entries = [
        _BatchProvisionItem(
            item_id=f"item_{idx:04d}",
            doc=doc,
            provision=provision,
        )
        for idx, (doc, provision) in enumerate(batch_items)
    ]
    if not entries:
        return []
    if len(entries) == 1:
        return await _run_single_extractions(client, entries, extract_mode="light")

    # --- Cache lookup: resolve cached entries without LLM ---
    cache = getattr(client, "_cache", None)
    results_by_id: dict[str, SPOExtractionResult] = {}
    uncached_entries: list[_BatchProvisionItem] = []

    for entry in entries:
        if cache is not None:
            cached = cache.get(entry.provision.text, entry.doc.card.doc_type, client.model_id)
            if cached is not None:
                statements = _parse_light_statements(cached)
                results_by_id[entry.item_id] = SPOExtractionResult(
                    doc_id=entry.doc.card.doc_id,
                    provision_anchor=entry.provision.anchor_path,
                    provision_citation=entry.provision.citation_label,
                    statements=statements,
                    raw_llm_response=json.dumps(cached, ensure_ascii=False),
                    raw_extract_response=json.dumps(cached, ensure_ascii=False),
                    model_id=client.model_id,
                    prompt_version=SPO_LIGHT_PROMPT_VERSION,
                    extract_passes=1,
                    extraction_source="cache",
                    low_confidence=not statements,
                    low_confidence_reasons=["no_statements"] if not statements else [],
                    latency_ms=0,
                    pass1_latency_ms=0,
                )
                continue
        uncached_entries.append(entry)

    # All entries resolved from cache.
    if not uncached_entries:
        return [results_by_id[e.item_id] for e in entries]

    # Only 1 uncached — use single extraction (has its own cache store).
    if len(uncached_entries) == 1:
        single_results = await _run_single_extractions(client, uncached_entries, extract_mode="light")
        for entry, result in zip(uncached_entries, single_results, strict=True):
            results_by_id[entry.item_id] = result
        return [results_by_id[e.item_id] for e in entries]

    # --- LLM batch request for uncached entries ---
    prompt_items = [
        {
            "id": entry.item_id,
            "doc_title": entry.doc.card.name,
            "doc_type": entry.doc.card.doc_type,
            "publisher": ", ".join(entry.doc.card.publisher) if entry.doc.card.publisher else "",
            "date_acc": entry.doc.card.date_acc,
            "provision_citation": entry.provision.citation_label,
            "provision_text": entry.provision.text,
        }
        for entry in uncached_entries
    ]
    messages = [
        {"role": "system", "content": SPO_LIGHT_BATCH_SYSTEM_PROMPT},
        {"role": "user", "content": build_spo_light_batch_user_prompt(items=prompt_items)},
    ]

    t1 = time.monotonic()
    try:
        resp = await client.chat_completion(
            messages,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.warning(
            "SPO batched light extract failed for {} provisions; fallback to singles: {}",
            len(uncached_entries),
            exc,
        )
        fallback = await _run_single_extractions(client, uncached_entries, extract_mode="light")
        for entry, result in zip(uncached_entries, fallback, strict=True):
            results_by_id[entry.item_id] = result
        return [results_by_id[e.item_id] for e in entries]

    latency_ms = int((time.monotonic() - t1) * 1000)
    usage_prompt, usage_completion, cost_base, cost_platform, cost_total = _usage_counts(resp)
    choice = resp.get("choices", [{}])[0]
    raw_content = choice.get("message", {}).get("content", "")
    data = _parse_json_object(raw_content)
    payload_by_id = _parse_batch_extract_payload(data)

    if not payload_by_id:
        logger.warning(
            "SPO batched light extract returned incompatible schema for {} provisions; fallback to singles.",
            len(uncached_entries),
        )
        fallback = await _run_single_extractions(client, uncached_entries, extract_mode="light")
        for entry, result in zip(uncached_entries, fallback, strict=True):
            results_by_id[entry.item_id] = result
        return [results_by_id[e.item_id] for e in entries]

    prompt_parts = _split_int(usage_prompt, len(uncached_entries))
    completion_parts = _split_int(usage_completion, len(uncached_entries))
    cost_base_parts = _split_float(cost_base, len(uncached_entries))
    cost_platform_parts = _split_float(cost_platform, len(uncached_entries))
    cost_total_parts = _split_float(cost_total, len(uncached_entries))

    for idx, entry in enumerate(uncached_entries):
        item_payload = payload_by_id.get(entry.item_id)
        if item_payload is None:
            logger.warning(
                "Batched light extract missing id={} for {} {}; fallback to single.",
                entry.item_id,
                entry.doc.card.doc_id,
                entry.provision.anchor_path,
            )
            fallback = await _run_single_extractions(client, [entry], extract_mode="light")
            results_by_id[entry.item_id] = fallback[0]
            continue

        # --- Cache store for this item ---
        if cache is not None and item_payload:
            cache.put(entry.provision.text, entry.doc.card.doc_type, client.model_id, item_payload)

        statements = _parse_light_statements(item_payload)
        raw_item = json.dumps(
            {"id": entry.item_id, "statements": item_payload.get("statements", [])},
            ensure_ascii=False,
        )

        low_confidence = not statements
        low_confidence_reasons: list[str] = []
        if not statements:
            low_confidence_reasons.append("no_statements")

        results_by_id[entry.item_id] = SPOExtractionResult(
            doc_id=entry.doc.card.doc_id,
            provision_anchor=entry.provision.anchor_path,
            provision_citation=entry.provision.citation_label,
            statements=statements,
            raw_llm_response=raw_item,
            raw_extract_response=raw_item,
            model_id=client.model_id,
            prompt_version=SPO_LIGHT_PROMPT_VERSION,
            extract_passes=1,
            low_confidence=low_confidence,
            low_confidence_reasons=low_confidence_reasons,
            latency_ms=latency_ms,
            pass1_latency_ms=latency_ms,
            token_count_prompt=prompt_parts[idx],
            token_count_completion=completion_parts[idx],
            token_count_prompt_extract=prompt_parts[idx],
            token_count_completion_extract=completion_parts[idx],
            cost_base_usd=cost_base_parts[idx],
            cost_platform_usd=cost_platform_parts[idx],
            cost_total_usd=cost_total_parts[idx],
        )

    return [results_by_id[e.item_id] for e in entries]


async def _extract_provision_group(
    client: GonkaClient,
    group: list[tuple[NPADocument, ProvisionSpan]],
    *,
    verify_mode: str,
    extract_mode: str = "full",
) -> list[SPOExtractionResult]:
    if not group:
        return []

    if extract_mode == "light":
        if len(group) == 1:
            doc, provision = group[0]
            return [await _extract_one_provision_light(client, doc, provision)]
        return await _extract_batch_provisions_light(client, group)

    if len(group) == 1:
        doc, provision = group[0]
        return [
            await _extract_one_provision(
                client,
                doc,
                provision,
                verify_mode=verify_mode,
            ),
        ]
    return await _extract_batch_provisions(client, group, verify_mode=verify_mode)


async def extract_spo_for_documents(
    client: GonkaClient,
    documents: list[NPADocument],
    provisions_by_doc: dict[str, list[ProvisionSpan]],
    *,
    results_dir: Path,
    task_batch_size: int = 1000,
    request_batch_size: int = 1,
    request_batch_chars: int | None = None,
    group_timeout_seconds: float | None = None,
    verify_mode: str = "llm",
    extract_mode: str = "full",
    overwrite_existing: bool = True,
    extraction_source: str = "llm",
    gate_meta_by_anchor: dict[str, dict[str, dict[str, Any]]] | None = None,
    fallback_rows_by_anchor: dict[str, dict[str, dict[str, Any]]] | None = None,
    result_sink: Callable[[dict[str, Any]], None] | None = None,
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
        if overwrite_existing and out_path.exists():
            out_path.unlink()
        provisions = provisions_by_doc.get(doc.card.doc_id, [])
        for prov in provisions:
            work_items.append((doc, prov))

    if not work_items:
        return 0, set()

    total_statements = 0
    failed_doc_ids: set[str] = set()
    batch_size = max(1, task_batch_size)
    request_size = max(1, request_batch_size)

    for i in range(0, len(work_items), batch_size):
        chunk = work_items[i : i + batch_size]
        request_groups = _group_request_items(
            chunk,
            request_batch_size=request_size,
            request_batch_chars=request_batch_chars,
        )
        tasks = [
            asyncio.create_task(
                asyncio.wait_for(
                    _extract_provision_group(
                        client,
                        group,
                        verify_mode=verify_mode,
                        extract_mode=extract_mode,
                    ),
                    timeout=group_timeout_seconds,
                )
            )
            if group_timeout_seconds is not None
            else asyncio.create_task(
                _extract_provision_group(
                    client,
                    group,
                    verify_mode=verify_mode,
                    extract_mode=extract_mode,
                ),
            )
            for group in request_groups
        ]
        group_results = await asyncio.gather(*tasks, return_exceptions=True)

        doc_buffers: dict[str, list[dict[str, Any]]] = {}
        for group, group_result in zip(request_groups, group_results, strict=True):
            if isinstance(group_result, Exception):
                timeout = isinstance(group_result, asyncio.TimeoutError)
                error_label = "timeout" if timeout else "failure"
                logger.warning(
                    "Provision-group task {} for {} items: {}",
                    error_label,
                    len(group),
                    group_result,
                )
                fallback_rows: list[tuple[str, dict[str, Any]]] = []
                if fallback_rows_by_anchor:
                    for doc, prov in group:
                        base_row = fallback_rows_by_anchor.get(doc.card.doc_id, {}).get(prov.anchor_path)
                        if base_row is None:
                            fallback_rows = []
                            break
                        fallback_rows.append(
                            (
                                doc.card.doc_id,
                                _materialize_fallback_row(
                                    base_row,
                                    error_message=str(group_result),
                                    timeout=timeout,
                                ),
                            )
                        )
                if fallback_rows:
                    for doc_id, row in fallback_rows:
                        if result_sink is not None:
                            result_sink(row)
                        doc_buffers.setdefault(doc_id, []).append(row)
                        statements = row.get("statements")
                        total_statements += len(statements) if isinstance(statements, list) else 0
                    continue
                for doc, _ in group:
                    failed_doc_ids.add(doc.card.doc_id)
                continue

            for result in group_result:
                if not result.statements and "failed" in result.raw_llm_response.lower():
                    failed_doc_ids.add(result.doc_id)

                row = result.model_dump(mode="json")
                row["extraction_source"] = extraction_source
                gate_score = 0.0
                gate_reasons: list[str] = []
                if gate_meta_by_anchor:
                    per_doc = gate_meta_by_anchor.get(result.doc_id, {})
                    meta = per_doc.get(result.provision_anchor)
                    if meta:
                        gate_score = float(meta.get("gate_score", 0.0) or 0.0)
                        gate_reasons = list(meta.get("gate_reason_codes") or [])
                        for key in (
                            "legal_unit_subtype",
                            "route_class",
                            "empty_spo_retry_eligible",
                            "audit_miss_prone",
                            "reference_bearing",
                            "threshold_bearing",
                        ):
                            if key in meta:
                                row[key] = meta.get(key)
                row["gate_score"] = gate_score
                row["gate_reason_codes"] = gate_reasons
                row["extraction_source"] = extraction_source
                if result_sink is not None:
                    result_sink(row)
                doc_buffers.setdefault(result.doc_id, []).append(row)
                total_statements += len(result.statements)

        for doc_id, rows in doc_buffers.items():
            out_path = results_dir / _shard_prefix(doc_id) / f"{doc_id}.jsonl"
            with open(out_path, "a", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    if failed_doc_ids:
        logger.warning(
            "{} documents had failed provisions and will NOT be marked as done: {}",
            len(failed_doc_ids),
            ", ".join(sorted(failed_doc_ids)[:10]) + ("..." if len(failed_doc_ids) > 10 else ""),
        )

    return total_statements, failed_doc_ids
