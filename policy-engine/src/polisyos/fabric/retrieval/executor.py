"""FetchPlan preview/execute with quality gate and fallback support."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, cast

from polisyos.common.async_tools import run_coro_sync
from polisyos.common.logger import get_logger
from polisyos.core import artifacts as core_artifacts
from polisyos.core.artifacts import ArtifactStore, ArtifactStoreConfig, build_artifact_store
from polisyos.core.contracts.control import (
    DataContextMetric,
    FetchPlan,
    FetchPlanFallback,
    FetchPreview,
)
from polisyos.fabric._adapters.observability import FABRIC_TRACE_NAMES
from polisyos.fabric.connectors._registry_errors import RegistryError
from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config
from polisyos.ir.connectors import FetchRequest, FetchResult

from .providers import RetrievalProviders, resolve_retrieval_providers

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer
    from polisyos.fabric.connectors._registry_models import _ConnectorRegistrationBinding
    from polisyos.fabric.connectors.base import ConnectionConfig
    from polisyos.fabric.connectors.profiles import SourceProfileRegistry
    from polisyos.fabric.connectors.registry import ConnectorRegistry

logger = get_logger(__name__)


@dataclass(frozen=True)
class ExecutePlanResult:
    """Preview/execute outcome showing the chosen fetch plan, metric payload, and fallback usage."""

    preview: FetchPreview
    metric: DataContextMetric | None
    used_plan: FetchPlan
    fallback_used: bool
    payload_ref: core_artifacts.ArtifactRef | None = None
    fetch_receipt_ref: core_artifacts.ArtifactRef | None = None


@dataclass(frozen=True, slots=True)
class _FetchExecutionBinding:
    """Bind one exact plan to the effective config captured for its execution."""

    owner: object
    plan_fingerprint: str
    connector_id: str
    profile_id: str | None
    connection_config: ConnectionConfig
    config_fingerprint: str
    registration_binding: _ConnectorRegistrationBinding


def _fetch_plan_fingerprint(plan: FetchPlan) -> str:
    canonical = json.dumps(
        plan.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class FetchExecutor:
    """Runs preview gate and full fetch for resolved plans."""

    def __init__(
        self,
        *,
        cas_root: Path | None = None,
        artifact_store: ArtifactStore | None = None,
        artifact_store_config: ArtifactStoreConfig | None = None,
        registry: ConnectorRegistry | None = None,
        profiles: SourceProfileRegistry | None = None,
        tracer: PolicyOSTracer | None = None,
        metrics: MetricsRegistry | None = None,
        providers: RetrievalProviders | None = None,
    ) -> None:
        resolved = providers or resolve_retrieval_providers(
            registry=registry,
            profiles=profiles,
            tracer=tracer,
            metrics=metrics,
        )
        self._registry = resolved.registry
        self._profiles = resolved.profiles
        store_inputs = sum(
            value is not None for value in (cas_root, artifact_store, artifact_store_config)
        )
        if store_inputs > 1:
            raise ValueError("fabric_fetch_store_configuration_conflict")
        self._artifact_store: ArtifactStore | None
        if artifact_store is not None:
            self._artifact_store = artifact_store
        elif artifact_store_config is not None:
            self._artifact_store = build_artifact_store(artifact_store_config)
        elif cas_root is not None:
            # `cas_root` remains a local standalone compatibility spelling. Runtime
            # owners pass their already-scoped ArtifactStore directly.
            self._artifact_store = build_artifact_store(
                ArtifactStoreConfig(backend="filesystem", root=str(cas_root))
            )
        else:
            self._artifact_store = None
        self._tracer = resolved.tracer
        self._metrics = resolved.metrics

    @property
    def artifact_store(self) -> ArtifactStore | None:
        """Return the exact store used for persisted fetch payloads and receipts."""
        return self._artifact_store

    def _bind_execution(
        self,
        plan: FetchPlan,
        *,
        registration_binding: _ConnectorRegistrationBinding | None = None,
    ) -> _FetchExecutionBinding:
        """Capture effective config and exact registry owner for one fetch plan."""
        checked = FetchPlan.model_validate(plan.model_dump(mode="python"))
        selected_registration = registration_binding
        try:
            if selected_registration is None:
                selected_registration = self._registry._capture_registration_binding(
                    checked.connector_id
                )
            selected_registration = self._registry._require_registration_binding(
                checked.connector_id,
                selected_registration,
            )
        except RegistryError as exc:
            raise ValueError("fabric_fetch_execution_registration_mismatch") from exc
        config: ConnectionConfig | None = None
        if checked.profile_id:
            profile = next(
                (
                    candidate
                    for candidate in self._profiles.snapshot_all()
                    if candidate.profile_id == checked.profile_id
                ),
                None,
            )
            if profile is not None:
                config = resolve_connection_config(profile)
        if config is None:
            config = self._registry.get_default_config(checked.connector_id)
        if config is None:
            raise ValueError(f"No connection profile/default config for '{checked.connector_id}'")
        checked_config = config
        try:
            selected_registration = self._registry._require_registration_binding(
                checked.connector_id,
                selected_registration,
            )
        except RegistryError as exc:
            raise ValueError("fabric_fetch_execution_registration_mismatch") from exc
        return _FetchExecutionBinding(
            owner=self,
            plan_fingerprint=_fetch_plan_fingerprint(checked),
            connector_id=checked.connector_id,
            profile_id=checked.profile_id,
            connection_config=checked_config,
            config_fingerprint=checked_config.cache_scope_fingerprint,
            registration_binding=selected_registration,
        )

    def _validate_execution_binding(
        self, plan: FetchPlan, binding: _FetchExecutionBinding
    ) -> ConnectionConfig:
        if (
            not isinstance(binding, _FetchExecutionBinding)
            or binding.owner is not self
            or binding.connector_id != plan.connector_id
            or binding.profile_id != plan.profile_id
            or binding.plan_fingerprint != _fetch_plan_fingerprint(plan)
        ):
            raise ValueError("fabric_fetch_execution_binding_mismatch")
        config = binding.connection_config
        if binding.config_fingerprint != config.cache_scope_fingerprint:
            raise ValueError("fabric_fetch_execution_config_binding_mismatch")
        try:
            self._registry._require_registration_binding(
                binding.connector_id,
                binding.registration_binding,
            )
        except RegistryError as exc:
            raise ValueError("fabric_fetch_execution_registration_mismatch") from exc
        return config

    def preview(self, plan: FetchPlan, *, allow_fallback: bool = True) -> ExecutePlanResult:
        result: ExecutePlanResult = run_coro_sync(
            self._preview_async(plan, allow_fallback=allow_fallback)
        )
        return result

    def replay_fetch(
        self,
        *,
        plan: FetchPlan,
        request: FetchRequest,
        execution_binding: _FetchExecutionBinding | None = None,
    ) -> FetchResult[Any]:
        """Read the exact full request again through the actual connector owner."""
        checked = FetchPlan.model_validate(plan.model_dump(mode="python"))
        if request != _fetch_request(checked, page_size=None):
            raise ValueError("fabric_fetch_request_mismatch")
        if execution_binding is not None:
            self._validate_execution_binding(checked, execution_binding)
        return run_coro_sync(
            self._fetch(
                plan=checked,
                page_size=None,
                execution_binding=execution_binding,
            )
        )

    def execute(
        self,
        plan: FetchPlan,
        *,
        persist_payload: bool = False,
        allow_fallback: bool = True,
        dataset_catalog: object | None = None,
        execution_binding: _FetchExecutionBinding | None = None,
    ) -> ExecutePlanResult:
        result: ExecutePlanResult = run_coro_sync(
            self._execute_async(
                FetchPlan.model_validate(plan.model_dump(mode="python")),
                persist_payload=persist_payload,
                allow_fallback=allow_fallback,
                dataset_catalog=dataset_catalog,
                execution_binding=execution_binding,
            )
        )
        return result

    async def _preview_async(self, plan: FetchPlan, *, allow_fallback: bool) -> ExecutePlanResult:
        preview = await self._fetch_preview(plan)
        if preview.coverage_ok:
            return ExecutePlanResult(
                preview=preview, metric=None, used_plan=plan, fallback_used=False
            )
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
        dataset_catalog: object | None,
        execution_binding: _FetchExecutionBinding | None,
    ) -> ExecutePlanResult:
        if execution_binding is not None:
            self._validate_execution_binding(plan, execution_binding)
        preview = await self._fetch_preview(plan, execution_binding=execution_binding)
        if not preview.coverage_ok and allow_fallback and plan.fallbacks:
            if execution_binding is not None:
                raise ValueError("fabric_fetch_execution_binding_fallback_not_supported")
            fallback_plan = self._fallback_to_plan(plan, plan.fallbacks[0])
            nested = await self._execute_async(
                fallback_plan,
                persist_payload=persist_payload,
                allow_fallback=True,
                dataset_catalog=dataset_catalog,
                execution_binding=None,
            )
            return ExecutePlanResult(
                preview=nested.preview,
                metric=nested.metric,
                used_plan=nested.used_plan,
                fallback_used=True,
                payload_ref=nested.payload_ref,
                fetch_receipt_ref=nested.fetch_receipt_ref,
            )
        if not preview.coverage_ok:
            return ExecutePlanResult(
                preview=preview, metric=None, used_plan=plan, fallback_used=False
            )

        binding = None
        if persist_payload:
            from .custody import FabricFetchCustodyError, _bind_plan

            if self._artifact_store is None:
                raise FabricFetchCustodyError("fabric_fetch_store_missing")
            binding = _bind_plan(dataset_catalog, plan)
        full_result = await self._fetch(
            plan=plan,
            page_size=None,
            execution_binding=execution_binding,
        )
        sample_rows = _extract_rows(full_result.data, max_rows=5)
        payload_ref = fetch_receipt_ref = None
        if persist_payload:
            from .custody import FabricFetchCustodyError, _persist_fetched_result

            if self._artifact_store is None:
                raise FabricFetchCustodyError("fabric_fetch_store_missing")
            if binding is None:
                raise FabricFetchCustodyError("catalog_fetch_target_not_admitted")
            payload_ref, fetch_receipt_ref = _persist_fetched_result(
                store=self._artifact_store,
                plan=plan,
                request=_fetch_request(plan, page_size=None),
                result=full_result,
                catalog=dataset_catalog,
                binding=binding,
            )
        metric = DataContextMetric(
            metric_id=plan.metric_id,
            plan_id=plan.plan_id,
            connector_id=plan.connector_id,
            dataset_id=plan.dataset_id,
            row_count=int(full_result.row_count),
            completeness=float(full_result.completeness),
            source_lane=plan.source_lane,
            sample_rows=sample_rows,
            payload_ref=payload_ref,
            fetch_receipt_ref=fetch_receipt_ref,
        )
        return ExecutePlanResult(
            preview=preview,
            metric=metric,
            used_plan=plan,
            fallback_used=False,
            payload_ref=payload_ref,
            fetch_receipt_ref=fetch_receipt_ref,
        )

    async def _fetch_preview(
        self,
        plan: FetchPlan,
        *,
        execution_binding: _FetchExecutionBinding | None = None,
    ) -> FetchPreview:
        started = datetime.now(UTC)
        try:
            result = await self._fetch(
                plan=plan,
                page_size=max(10, min(plan.max_preview_rows, 50)),
                execution_binding=execution_binding,
            )
        except Exception as exc:
            elapsed_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
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

        elapsed_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
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

    async def _fetch(
        self,
        *,
        plan: FetchPlan,
        page_size: int | None,
        execution_binding: _FetchExecutionBinding | None = None,
    ) -> FetchResult[Any]:
        if execution_binding is None:
            connector = self._registry.get(plan.connector_id, enable_cache=False)
            config = self._resolve_config(plan)
            registration_binding = None
        else:
            config = self._validate_execution_binding(plan, execution_binding)
            registration_binding = execution_binding.registration_binding
            try:
                connector = self._registry.get(
                    plan.connector_id,
                    enable_cache=False,
                    _registration_binding=registration_binding,
                )
            except RegistryError as exc:
                raise ValueError("fabric_fetch_execution_registration_mismatch") from exc
        try:
            if registration_binding is None:
                handle = await self._registry.get_connection(plan.connector_id, config)
            else:
                handle = await self._registry.get_connection(
                    plan.connector_id,
                    config,
                    _registration_binding=registration_binding,
                )
        except RegistryError as exc:
            raise ValueError("fabric_fetch_execution_registration_mismatch") from exc
        started = datetime.now(UTC)
        try:
            request = _fetch_request(plan, page_size=page_size)
            with self._tracer.start_as_current_span(
                FABRIC_TRACE_NAMES["connector_fetch"],
                attributes={
                    "connector.id": plan.connector_id,
                    "dataset.id": plan.dataset_id,
                    "retrieval.plan_id": plan.plan_id,
                },
            ):
                result = await connector.fetch(handle, request)
            duration = max((datetime.now(UTC) - started).total_seconds(), 0.0)
            payload_bytes = None
            try:
                payload_bytes = len(
                    json.dumps(result.data, ensure_ascii=True, sort_keys=True, default=str).encode(
                        "utf-8"
                    )
                )
            except Exception:
                payload_bytes = None
            if getattr(self._metrics, "record_fabric_connector_fetch", None):
                self._metrics.record_fabric_connector_fetch(
                    connector_id=plan.connector_id,
                    status="success",
                    duration_seconds=duration,
                    row_count=int(result.row_count),
                    payload_bytes=payload_bytes,
                )
            return result
        except Exception:
            duration = max((datetime.now(UTC) - started).total_seconds(), 0.0)
            if getattr(self._metrics, "record_fabric_connector_fetch", None):
                self._metrics.record_fabric_connector_fetch(
                    connector_id=plan.connector_id,
                    status="error",
                    duration_seconds=duration,
                    row_count=0,
                    payload_bytes=None,
                )
            raise
        finally:
            await self._registry.release_connection(plan.connector_id, handle)

    def _resolve_config(self, plan: FetchPlan) -> ConnectionConfig | None:
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
        fallback_metric_id = fallback.metric_id or plan.metric_id
        updated_metadata = dict(plan.metadata)
        fallback_metadata = dict(fallback.metadata)
        history = list(updated_metadata.get("fallback_history", []))
        history.append(
            {
                "from_metric_id": plan.metric_id,
                "to_metric_id": fallback_metric_id,
                "from_connector_id": plan.connector_id,
                "to_connector_id": fallback.connector_id,
                "route": fallback_metadata.get("resolution_route")
                or updated_metadata.get("resolution_route", ""),
            }
        )
        updated_metadata.update(fallback_metadata)
        updated_metadata["fallback_applied"] = True
        updated_metadata["fallback_history"] = history
        updated_metadata["fallback_from_metric_id"] = plan.metric_id
        updated_metadata["resolution_route"] = fallback_metadata.get(
            "resolution_route",
            updated_metadata.get("resolution_route", ""),
        )
        return plan.model_copy(
            update={
                "plan_id": f"{plan.plan_id}_fallback_{fallback_metric_id}_{fallback.connector_id}",
                "metric_id": fallback_metric_id,
                "connector_id": fallback.connector_id,
                "dataset_id": fallback.dataset_id,
                "profile_id": fallback.profile_id,
                "filters": fallback.filters or plan.filters,
                "fallbacks": plan.fallbacks[1:],
                "metadata": updated_metadata,
            }
        )


def _filters_to_tuple(filters: dict[str, list[str]]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    return tuple((key, tuple(values)) for key, values in sorted((filters or {}).items()))


def _fetch_request(plan: FetchPlan, *, page_size: int | None) -> FetchRequest:
    return FetchRequest(
        dataset_id=plan.dataset_id,
        filters=_filters_to_tuple(plan.filters),
        date_start=_parse_optional_datetime(plan.date_start),
        date_end=_parse_optional_datetime(plan.date_end),
        include_metadata=True,
        include_schema=True,
        page_size=page_size,
        retryable=True,
    )


def _parse_optional_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    # Common shorthand support for year-only and year-month values.
    if len(raw) == 4 and raw.isdigit():
        return datetime(int(raw), 1, 1, tzinfo=UTC)
    if len(raw) == 7 and raw[4] == "-":
        return datetime.fromisoformat(f"{raw}-01").replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


class _FrameLike(Protocol):
    """Small dataframe-like surface used to extract a bounded row preview."""

    def head(self, count: int) -> _FrameLike: ...

    def to_dict(self, *, orient: str) -> object: ...


def _extract_rows(payload: object, *, max_rows: int) -> list[dict[str, Any]]:
    if max_rows <= 0:
        return []
    if payload is None:
        return []
    # pandas is optional; avoid hard dependency.
    if hasattr(payload, "head") and hasattr(payload, "to_dict"):
        try:
            frame = cast("_FrameLike", payload)
            head = frame.head(max_rows)
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
