"""FetchPlan preview/execute with quality gate and fallback support."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from polisyos.common.async_tools import run_coro_sync
from polisyos.common.logger import get_logger
from polisyos.core.contracts.control import (
    DataContextMetric,
    FetchPlan,
    FetchPlanFallback,
    FetchPreview,
)
from polisyos.fabric.connectors.profiles import SourceProfileRegistry
from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.ir.connectors import FetchRequest, FetchResult

logger = get_logger(__name__)


@dataclass(frozen=True)
class ExecutePlanResult:
    preview: FetchPreview
    metric: DataContextMetric | None
    used_plan: FetchPlan
    fallback_used: bool


class FetchExecutor:
    """Runs preview gate and full fetch for resolved plans."""

    def __init__(
        self,
        *,
        cas_root: Path | None = None,
    ) -> None:
        self._registry = ConnectorRegistry.get_instance()
        self._profiles = SourceProfileRegistry.get_instance()
        self._cas_root = cas_root

    def preview(self, plan: FetchPlan, *, allow_fallback: bool = True) -> ExecutePlanResult:
        return run_coro_sync(self._preview_async(plan, allow_fallback=allow_fallback))

    def execute(
        self,
        plan: FetchPlan,
        *,
        persist_payload: bool = False,
        allow_fallback: bool = True,
    ) -> ExecutePlanResult:
        return run_coro_sync(
            self._execute_async(
                plan,
                persist_payload=persist_payload,
                allow_fallback=allow_fallback,
            )
        )

    async def _preview_async(self, plan: FetchPlan, *, allow_fallback: bool) -> ExecutePlanResult:
        preview = await self._fetch_preview(plan)
        if preview.coverage_ok:
            return ExecutePlanResult(preview=preview, metric=None, used_plan=plan, fallback_used=False)
        if allow_fallback and plan.fallbacks:
            fallback_plan = self._fallback_to_plan(plan, plan.fallbacks[0])
            nested = await self._preview_async(fallback_plan, allow_fallback=True)
            return ExecutePlanResult(
                preview=nested.preview,
                metric=None,
                used_plan=nested.used_plan,
                fallback_used=True,
            )
        return ExecutePlanResult(preview=preview, metric=None, used_plan=plan, fallback_used=False)

    async def _execute_async(
        self,
        plan: FetchPlan,
        *,
        persist_payload: bool,
        allow_fallback: bool,
    ) -> ExecutePlanResult:
        preview = await self._fetch_preview(plan)
        if not preview.coverage_ok and allow_fallback and plan.fallbacks:
            fallback_plan = self._fallback_to_plan(plan, plan.fallbacks[0])
            nested = await self._execute_async(
                fallback_plan,
                persist_payload=persist_payload,
                allow_fallback=True,
            )
            return ExecutePlanResult(
                preview=nested.preview,
                metric=nested.metric,
                used_plan=nested.used_plan,
                fallback_used=True,
            )
        if not preview.coverage_ok:
            return ExecutePlanResult(preview=preview, metric=None, used_plan=plan, fallback_used=False)

        full_result = await self._fetch(
            plan=plan,
            page_size=None,
        )
        sample_rows = _extract_rows(full_result.data, max_rows=5)
        if persist_payload and self._cas_root is not None:
            # Retrieval mode defaults to in-memory payload usage. Persisting large payloads
            # is intentionally deferred to the ingestion pipeline.
            _ = self._cas_root
        metric = DataContextMetric(
            metric_id=plan.metric_id,
            plan_id=plan.plan_id,
            connector_id=plan.connector_id,
            dataset_id=plan.dataset_id,
            row_count=int(full_result.row_count),
            completeness=float(full_result.completeness),
            source_lane=plan.source_lane,
            sample_rows=sample_rows,
        )
        return ExecutePlanResult(preview=preview, metric=metric, used_plan=plan, fallback_used=False)

    async def _fetch_preview(self, plan: FetchPlan) -> FetchPreview:
        started = datetime.now(timezone.utc)
        try:
            result = await self._fetch(
                plan=plan,
                page_size=max(10, min(plan.max_preview_rows, 50)),
            )
        except Exception as exc:
            elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            return FetchPreview(
                status="error",
                connector_id=plan.connector_id,
                dataset_id=plan.dataset_id,
                row_count=0,
                completeness=0.0,
                coverage_ok=False,
                quality_min=plan.quality_min,
                sample_rows=[],
                schema_payload={},
                quality_flags=[],
                message=str(exc),
                latency_ms=max(0, elapsed_ms),
            )

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        completeness = float(result.completeness)
        coverage_ok = completeness >= float(plan.quality_min)
        status = "ok" if coverage_ok else "insufficient_coverage"
        return FetchPreview(
            status=status,
            connector_id=plan.connector_id,
            dataset_id=plan.dataset_id,
            row_count=int(result.row_count),
            completeness=completeness,
            coverage_ok=coverage_ok,
            quality_min=plan.quality_min,
            sample_rows=_extract_rows(result.data, max_rows=max(1, min(plan.max_preview_rows, 25))),
            schema_payload={
                "schema_id": result.schema_id,
                "schema_version": result.schema_version,
            },
            quality_flags=sorted(str(flag) for flag in result.quality_flags),
            message=None if coverage_ok else "Preview gate rejected by quality_min",
            latency_ms=max(0, elapsed_ms),
        )

    async def _fetch(self, *, plan: FetchPlan, page_size: int | None) -> FetchResult[Any]:
        connector = self._registry.get(plan.connector_id, enable_cache=False)
        config = self._resolve_config(plan)
        handle = await self._registry.get_connection(plan.connector_id, config)
        try:
            request = FetchRequest(
                dataset_id=plan.dataset_id,
                filters=_filters_to_tuple(plan.filters),
                date_start=_parse_optional_datetime(plan.date_start),
                date_end=_parse_optional_datetime(plan.date_end),
                include_metadata=True,
                include_schema=True,
                page_size=page_size,
                retryable=True,
            )
            return await connector.fetch(handle, request)
        finally:
            await self._registry.release_connection(plan.connector_id, handle)

    def _resolve_config(self, plan: FetchPlan):
        if plan.profile_id:
            profile = self._profiles.get(plan.profile_id)
            if profile is not None:
                return resolve_connection_config(profile)
        config = self._registry.get_default_config(plan.connector_id)
        if config is None:
            raise ValueError(f"No connection profile/default config for '{plan.connector_id}'")
        return config

    @staticmethod
    def _fallback_to_plan(plan: FetchPlan, fallback: FetchPlanFallback) -> FetchPlan:
        return plan.model_copy(
            update={
                "plan_id": f"{plan.plan_id}_fallback_{fallback.connector_id}",
                "connector_id": fallback.connector_id,
                "dataset_id": fallback.dataset_id,
                "profile_id": fallback.profile_id,
                "filters": fallback.filters or plan.filters,
                "fallbacks": plan.fallbacks[1:],
            }
        )


def _filters_to_tuple(filters: dict[str, list[str]]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple((key, tuple(values)) for key, values in sorted((filters or {}).items()))


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    # Common shorthand support for year-only and year-month values.
    if len(raw) == 4 and raw.isdigit():
        return datetime(int(raw), 1, 1, tzinfo=timezone.utc)
    if len(raw) == 7 and raw[4] == "-":
        return datetime.fromisoformat(f"{raw}-01").replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _extract_rows(payload: Any, *, max_rows: int) -> list[dict[str, Any]]:
    if max_rows <= 0:
        return []
    if payload is None:
        return []
    # pandas is optional; avoid hard dependency.
    if hasattr(payload, "head") and hasattr(payload, "to_dict"):
        try:
            head = payload.head(max_rows)
            rows = head.to_dict(orient="records")
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        except Exception as exc:
            logger.debug("Ignored exception: %s", exc)
    if isinstance(payload, list):
        rows = payload[:max_rows]
        return [row for row in rows if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "data", "items"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                rows = candidate[:max_rows]
                return [row for row in rows if isinstance(row, dict)]
    return []
