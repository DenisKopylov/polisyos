"""Async OpenAlex client for topic-based literature harvesting."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp

from polisyos.academic.openalex.rate_limiter import OpenAlexRateLimiter
from polisyos.common.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class OpenAlexRequest:
    """Request envelope for /works list endpoint."""

    filter_expr: str
    sort: str
    per_page: int = 200
    cursor: str = "*"
    select: str = (
        "id,doi,title,abstract_inverted_index,cited_by_count,fwci,"
        "citation_normalized_percentile,publication_year,publication_date,language,type,is_retracted,"
        "has_fulltext,open_access,best_oa_location,authorships,primary_location,topics"
    )


class OpenAlexClient:
    """Rate-limited OpenAlex API client with retry/backoff."""

    def __init__(
        self,
        *,
        email: str = "",
        max_rps: int = 10,
        max_concurrent: int = 5,
        timeout_seconds: int = 60,
        max_retries: int = 5,
        backoff_seconds: float = 5.0,
    ) -> None:
        self._email = email.strip()
        self._timeout = aiohttp.ClientTimeout(total=max(5, int(timeout_seconds)))
        self._max_retries = max(1, int(max_retries))
        self._backoff_seconds = float(backoff_seconds)
        self._limiter = OpenAlexRateLimiter(max_rps=max_rps, max_concurrent=max_concurrent)
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> OpenAlexClient:
        headers: dict[str, str] = {}
        if self._email:
            headers["User-Agent"] = f"PolicyOS/1.0 (mailto:{self._email})"
        self._session = aiohttp.ClientSession(timeout=self._timeout, headers=headers)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def list_works(self, req: OpenAlexRequest) -> dict[str, Any]:
        """Call OpenAlex /works with retry handling."""
        assert self._session is not None, "Use `async with OpenAlexClient(...)`"

        params = {
            "filter": req.filter_expr,
            "sort": req.sort,
            "per-page": max(1, int(req.per_page)),
            "cursor": req.cursor,
            "select": req.select,
        }
        if self._email:
            params["mailto"] = self._email

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            async with self._limiter.semaphore:
                await self._limiter.acquire()
                try:
                    async with self._session.get("https://api.openalex.org/works", params=params) as resp:
                        if resp.status == 200:
                            payload = await resp.json(content_type=None)
                            if isinstance(payload, dict):
                                return payload
                            return {"results": [], "meta": {}}

                        body = await resp.text()
                        if resp.status == 429:
                            await self._limiter.report_429(self._backoff_seconds)
                            wait = self._retry_delay(attempt, resp.headers.get("Retry-After"))
                            logger.warning(
                                "OpenAlex 429, retrying in %.1fs (%d/%d)",
                                wait,
                                attempt,
                                self._max_retries,
                            )
                            await asyncio.sleep(wait)
                            continue

                        if 500 <= resp.status < 600:
                            wait = self._retry_delay(attempt, resp.headers.get("Retry-After"))
                            logger.warning(
                                "OpenAlex %d, retrying in %.1fs (%d/%d): %s",
                                resp.status,
                                wait,
                                attempt,
                                self._max_retries,
                                body[:160],
                            )
                            await asyncio.sleep(wait)
                            continue

                        raise RuntimeError(f"OpenAlex non-retryable error HTTP {resp.status}: {body[:500]}")

                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    last_error = exc
                    wait = min(0.5 * (2 ** (attempt - 1)), 20.0)
                    logger.warning(
                        "OpenAlex network error, retrying in %.1fs (%d/%d): %s",
                        wait,
                        attempt,
                        self._max_retries,
                        exc,
                    )
                    await asyncio.sleep(wait)

        raise RuntimeError("OpenAlex request failed after retries") from last_error

    @staticmethod
    def _retry_delay(attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                parsed = float(retry_after.strip())
                if parsed > 0:
                    return min(parsed, 120.0)
            except ValueError:
                pass
        return min(0.5 * (2 ** (attempt - 1)), 30.0)
