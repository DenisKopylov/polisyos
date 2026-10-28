"""Hybrid retrieval service (FastLane + ExploreLane + PromotionLane)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast
from urllib.parse import urlparse

from polisyos.common.logger import get_logger
from polisyos.core import canon
from polisyos.core.contracts.control import (
    DataContext,
    DataNeed,
    DataResolveRequest,
    DiscoveryCandidate,
    FetchPlan,
    FetchPlanFallback,
    IndexStats,
    MetricCandidate,
    PromotionCandidate,
)
from polisyos.data_forge.read_api import catalog as catalog_read_api
from polisyos.fabric._adapters.observability import FABRIC_TRACE_NAMES
from polisyos.fabric.catalog.resolver_fast_lane import FastLaneResolver
from polisyos.fabric.catalog.source_bindings import SourceBinding
from polisyos.fabric.connectors.base import _safe_local_path

from .executor import ExecutePlanResult, FetchExecutor
from .explore_lane import (
    ExploreLaneDiscoverResult,
    ExploreLaneDiscovery,
    ExploreLaneLimits,
)
from .providers import RetrievalProviders, resolve_retrieval_providers

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactStore, ArtifactStoreConfig
    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer
    from polisyos.data_forge.read_api.catalog import (
        CatalogRunProfile,
        CatalogSourceRegistryEntry,
        CatalogSourceRegistrySpec,
    )
    from polisyos.fabric.connectors._registry_models import _ConnectorRegistrationBinding
    from polisyos.fabric.connectors.profiles import SourceProfileRegistry
    from polisyos.fabric.connectors.registry import ConnectorRegistry

    from .executor import _FetchExecutionBinding

logger = get_logger(__name__)

_EXECUTABLE_CATALOG_TIERS = frozenset({"fetchable", "transport_ready"})
_CatalogCandidateT = TypeVar("_CatalogCandidateT", MetricCandidate, DiscoveryCandidate)


@dataclass(frozen=True)
class ResolveOutcome:
    """Resolve outcome public type."""

    mode: str
    fetch_plans: list[FetchPlan]
    candidates: list[MetricCandidate]
    warnings: list[str]
    telemetry: dict[str, object]


@dataclass(frozen=True)
class DiscoverOutcome:
    """Discover outcome public type."""

    candidates: list[DiscoveryCandidate]
    docs_fetched_total: int
    warnings: list[str]


@dataclass(frozen=True)
class ExecuteOutcome:
    """Execute outcome public type."""

    data_context: DataContext
    previews: list[ExecutePlanResult]
    promoted_count: int
    fallback_triggered_count: int


@dataclass(frozen=True, slots=True)
class FetchCaptureLocatorView:
    """Transient locator classification for the bounded local capture policy.

    Local paths are exposed only to the callback for root checks and are omitted
    from ``repr``. Remote authorities, query strings, fragments, and raw config
    values are never copied into this view.
    """

    present: bool
    is_text: bool
    classification: Literal["missing", "malformed", "local", "remote", "nonlocal"]
    local_path: str | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class FetchCapturePreflightView:
    """Minimal owner snapshot supplied to one persisted-capture preflight.

    The view contains plan, catalog-binding, and captured config digests,
    connector types, and classified locator inputs. ``local_path`` fields
    are transient inputs for a root-bound policy check; callbacks must not
    persist or log them. Captured fingerprints describe the immutable config
    used for this operation, not the live profile registry or source
    currentness.
    """

    plan_id: str
    metric_id: str
    connector_id: str
    profile_id: str | None
    plan_fingerprint: str
    catalog_binding_fingerprint: str
    effective_config_fingerprint: str
    source_profile_fingerprint: str | None
    target_distribution_id: str
    target_connector_id: str
    target_profile_id: str | None
    connector_params_mappable: bool
    connector_param_locators: tuple[tuple[str, FetchCaptureLocatorView], ...]
    effective_locator: FetchCaptureLocatorView
    connector_class: type[object] | None
    connector_instance_class: type[object] | None


@dataclass(frozen=True, slots=True)
class FetchCaptureArtifactReferenceView:
    """Scalar artifact-reference identity without a mutable CAS model object."""

    artifact_id: str
    kind: str
    media_type: str
    manifest_profile_sha256: str | None


@dataclass(frozen=True, slots=True)
class FetchCaptureMetricView:
    """Metric summary and CAS references for one actual persisted fetch."""

    plan_id: str
    metric_id: str
    row_count: int
    completeness: float
    source_lane: str
    payload_ref: FetchCaptureArtifactReferenceView | None
    fetch_receipt_ref: FetchCaptureArtifactReferenceView | None


@dataclass(frozen=True, slots=True)
class FetchCapturePostflightView:
    """Postflight projection with captured config digests and artifact refs.

    Sample rows and payload content are excluded. The config fingerprints let
    callbacks compare the operation's preflight and postflight snapshots; they
    do not establish live profile currentness.
    """

    plan_fingerprint: str
    effective_config_fingerprint: str
    source_profile_fingerprint: str | None
    metrics: tuple[FetchCaptureMetricView, ...]


def _capture_locator_view(value: object, *, present: bool = True) -> FetchCaptureLocatorView:
    """Classify a locator without retaining remote authority or raw config text."""
    if not present:
        return FetchCaptureLocatorView(
            present=False,
            is_text=False,
            classification="missing",
        )
    if not isinstance(value, str):
        return FetchCaptureLocatorView(
            present=True,
            is_text=False,
            classification="malformed",
        )
    if not value:
        return FetchCaptureLocatorView(
            present=True,
            is_text=True,
            classification="malformed",
        )
    try:
        parsed = urlparse(value)
    except ValueError:
        return FetchCaptureLocatorView(
            present=True,
            is_text=True,
            classification="malformed",
        )
    scheme = parsed.scheme.lower()
    if scheme in {"http", "https"}:
        return FetchCaptureLocatorView(
            present=True,
            is_text=True,
            classification="remote",
        )
    if (scheme and scheme != "file") or parsed.netloc:
        return FetchCaptureLocatorView(
            present=True,
            is_text=True,
            classification="nonlocal",
        )
    try:
        # Use the exact lexical path projection consumed by the registered
        # file connector; do not trim or expand shell-home syntax here.
        local_path = str(_safe_local_path(value, scheme=scheme))
    except ValueError:
        return FetchCaptureLocatorView(
            present=True,
            is_text=True,
            classification="malformed",
        )
    return FetchCaptureLocatorView(
        present=True,
        is_text=True,
        classification="local",
        local_path=local_path,
    )


def _capture_binding_fingerprint(binding: object) -> str:
    """Return a non-reversible identity digest for one typed catalog binding."""
    model_dump = getattr(binding, "model_dump", None)
    if not callable(model_dump):
        raise ValueError("fabric_fetch_capture_catalog_binding_missing")
    return canon.fingerprint(
        model_dump(mode="json"),
        prefix=True,
        canon_spec=canon.CanonSpec(forbid_floats=False, exclude_none=False),
    )


def _capture_artifact_reference_view(
    value: object | None,
) -> FetchCaptureArtifactReferenceView | None:
    """Copy only typed CAS reference scalars into a callback view."""
    if value is None:
        return None
    artifact_id = getattr(value, "artifact_id", None)
    kind = getattr(value, "kind", None)
    media_type = getattr(value, "media_type", None)
    profile = getattr(value, "manifest_profile_sha256", None)
    if artifact_id is None:
        raise ValueError("fabric_fetch_capture_ref_metadata_mismatch")
    if (
        not isinstance(kind, str)
        or not isinstance(media_type, str)
        or (profile is not None and not isinstance(profile, str))
    ):
        raise ValueError("fabric_fetch_capture_ref_metadata_mismatch")
    return FetchCaptureArtifactReferenceView(
        artifact_id=str(artifact_id),
        kind=kind,
        media_type=media_type,
        manifest_profile_sha256=profile,
    )


def _flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {"none", "null"}:
        return None
    return text


def _coerce_int(value: object, *, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            return int(value)
    except TypeError, ValueError:
        pass
    return default


def _coerce_float(value: object, *, default: float = 0.0) -> float:
    try:
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return float(value)
    except TypeError, ValueError:
        pass
    return default


def _coerce_filter_map(value: object) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for key, raw_values in value.items():
        if not isinstance(key, str):
            continue
        if isinstance(raw_values, list):
            normalized[key] = [str(item) for item in raw_values]
        elif raw_values is not None:
            normalized[key] = [str(raw_values)]
    return normalized


def _scope_date(value: object, *, upper_bound: bool) -> date | None:
    """Parse year, date, or ISO datetime scope bounds without guessing."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if re.fullmatch(r"\d{4}", text):
        year = int(text)
        try:
            return date(year, 12 if upper_bound else 1, 31 if upper_bound else 1)
        except ValueError:
            return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None


def _scope_year_range(value: object) -> tuple[date, date] | None:
    """Parse the catalog's existing inclusive YYYY-YYYY range representation."""
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(\d{4})\s*[-–—]\s*(\d{4})\s*", value)
    if match is None:
        return None
    start_year, end_year = (int(part) for part in match.groups())
    try:
        return date(start_year, 1, 1), date(end_year, 12, 31)
    except ValueError:
        return None


def _catalog_selection_error(code: str, detail: str | None = None) -> RuntimeError:
    """Construct the canonical error through the existing lazy read API."""
    error_type = cast(
        "Callable[[str, str | None], RuntimeError]",
        catalog_read_api.CatalogSelectionError,
    )
    return error_type(code, detail)


class RetrievalService:
    """High-level retrieval orchestrator for control API and NL pipeline."""

    def __init__(
        self,
        *,
        curated_dir: Path,
        cas_root: Path | None = None,
        artifact_store: ArtifactStore | None = None,
        artifact_store_config: ArtifactStoreConfig | None = None,
        dataset_catalog: object | None = None,
        max_local_index_docs: int = 2_048,
        max_promotion_candidates: int = 512,
        registry: ConnectorRegistry | None = None,
        profiles: SourceProfileRegistry | None = None,
        tracer: PolicyOSTracer | None = None,
        metrics: MetricsRegistry | None = None,
        fastlane: FastLaneResolver | None = None,
        executor: FetchExecutor | None = None,
        explore: ExploreLaneDiscovery | None = None,
        providers: RetrievalProviders | None = None,
    ) -> None:
        resolved = providers or resolve_retrieval_providers(
            registry=registry,
            profiles=profiles,
            tracer=tracer,
            metrics=metrics,
        )
        resolved_registry = resolved.registry
        resolved_profiles = resolved.profiles
        resolved_tracer = resolved.tracer
        resolved_metrics = resolved.metrics
        self._fastlane = fastlane or FastLaneResolver(
            curated_dir=curated_dir,
            connector_registry=resolved_registry,
        )
        self._explore = explore or ExploreLaneDiscovery(
            providers=resolved,
        )
        if executor is not None and (cas_root is not None or artifact_store_config is not None):
            raise ValueError("retrieval_service_executor_store_configuration_conflict")
        if (
            executor is not None
            and artifact_store is not None
            and executor.artifact_store is not artifact_store
        ):
            raise ValueError("retrieval_service_executor_store_identity_mismatch")
        self._executor = executor or FetchExecutor(
            cas_root=cas_root,
            artifact_store=artifact_store,
            artifact_store_config=artifact_store_config,
            providers=resolved,
        )
        self._artifact_store = self._executor.artifact_store
        self._dataset_catalog = dataset_catalog  # DatasetCatalogGraph (optional)
        self._registry = resolved_registry
        self._profiles = resolved_profiles
        self._tracer = resolved_tracer
        self._metrics = resolved_metrics
        self._promotion_queue: OrderedDict[str, PromotionCandidate] = OrderedDict()
        self._local_index_docs: OrderedDict[str, dict[str, object]] = OrderedDict()
        self._index_size_bytes = 0
        self._docs_added_last_run = 0
        self._last_updated: datetime | None = None
        self._catalog_source_registry: CatalogSourceRegistrySpec | None = None
        self._catalog_source_selections: dict[str, frozenset[str]] = {}
        self._max_local_index_docs = max(1, max_local_index_docs)
        self._max_promotion_candidates = max(1, max_promotion_candidates)
        self._state_lock = threading.RLock()
        self._capture_deferred_promotions: ContextVar[list[tuple[FetchPlan, float]] | None] = (
            ContextVar(f"fabric-capture-promotions-{id(self)}", default=None)
        )

    @property
    def artifact_store(self) -> ArtifactStore | None:
        """Return the exact artifact store owned by the fetch executor."""
        return self._artifact_store

    def _catalog_registry(self) -> CatalogSourceRegistrySpec:
        """Refresh cached selection from the complete canonical effective registry."""
        with self._state_lock:
            load_registry = cast(
                "Callable[[], CatalogSourceRegistrySpec]",
                catalog_read_api.load_catalog_source_registry,
            )
            registry = load_registry()
            cached_registry = self._catalog_source_registry
            if cached_registry is None or cached_registry != registry:
                cached_registry = registry
                self._catalog_source_registry = cached_registry
                self._catalog_source_selections.clear()
            return cached_registry

    def _source_policy(self, source_name: str) -> CatalogSourceRegistryEntry | None:
        normalized = (source_name or "").strip()
        if not normalized:
            return None
        return self._catalog_registry().source_by_id(normalized)

    def _selected_catalog_source_ids(self, run_profile: CatalogRunProfile | None) -> frozenset[str]:
        if run_profile is None:
            raise _catalog_selection_error("catalog_run_profile_unresolved")
        with self._state_lock:
            registry = self._catalog_registry()
            cached = self._catalog_source_selections.get(run_profile)
            if cached is not None:
                return cached
            selected = registry.enabled_sources(run_profile=run_profile)
            selected_ids = frozenset(source.source_id for source in selected)
            self._catalog_source_selections[run_profile] = selected_ids
            return selected_ids

    def _catalog_source_is_enabled(
        self,
        source_name: str,
        *,
        connector_id: str,
        run_profile: CatalogRunProfile | None,
    ) -> bool:
        """Join a supplied source identity to its registered connector and run profile."""
        normalized = source_name.strip()
        if not normalized:
            raise _catalog_selection_error("catalog_source_identity_unresolved")
        policy = self._source_policy(normalized)
        if policy is None:
            raise _catalog_selection_error(
                "catalog_source_unregistered",
                normalized,
            )
        if not policy.enabled:
            return False
        supplied_connector = connector_id.strip()
        registered_connector = policy.connector_id.strip()
        if not supplied_connector or supplied_connector != registered_connector:
            raise _catalog_selection_error(
                "catalog_source_connector_mismatch",
                f"source={normalized}/registered={registered_connector}/supplied={supplied_connector}",
            )
        return normalized in self._selected_catalog_source_ids(run_profile)

    def _catalog_date_window(
        self,
        *,
        source_name: str,
        need: DataNeed,
    ) -> tuple[str | None, str | None, CatalogSourceRegistryEntry | None]:
        policy = self._source_policy(source_name)
        if need.time_start or need.time_end or policy is None:
            return need.time_start, need.time_end, policy
        if policy.history_policy != "rolling_window" or policy.default_lookback_days is None:
            return None, None, policy
        date_end = datetime.now(UTC)
        date_start = date_end - timedelta(days=int(policy.default_lookback_days))
        return date_start.isoformat(), date_end.isoformat(), policy

    @staticmethod
    def _has_explicit_scope(need: DataNeed) -> bool:
        return (
            need.geography is not None or need.time_start is not None or need.time_end is not None
        )

    def _catalog_scope_status(
        self,
        need: DataNeed,
        catalog_dataset_id: str,
    ) -> tuple[str, str]:
        """Compare an explicit request scope with one exact catalog dataset row."""
        if not self._has_explicit_scope(need):
            return "compatible", ""
        catalog = self._dataset_catalog
        get_dataset = getattr(catalog, "get_dataset", None)
        if not callable(get_dataset) or not catalog_dataset_id:
            return "unknown", "catalog_metadata_unavailable"
        dataset = get_dataset(catalog_dataset_id)
        if dataset is None or str(getattr(dataset, "id", "")) != catalog_dataset_id:
            raise _catalog_selection_error(
                "catalog_dataset_identity_unresolved",
                catalog_dataset_id,
            )
        coverage = getattr(dataset, "coverage", None)
        if coverage is None:
            return "unknown", "catalog_coverage_unavailable"

        dimensions: list[tuple[str, str]] = []
        if need.geography is not None:
            normalize_country = cast(
                "Callable[[object], str]", catalog_read_api.normalize_country_code
            )
            country = normalize_country(need.geography.strip())
            if not country:
                dimensions.append(("unknown", "geography_scope_unrecognized"))
            else:
                raw_countries = getattr(coverage, "countries", None)
                raw_regions = getattr(coverage, "regions", None)
                if not isinstance(raw_countries, (list, tuple)):
                    dimensions.append(("unknown", "geography_coverage_unavailable"))
                else:
                    normalized = [normalize_country(value) for value in raw_countries]
                    if country in normalized:
                        dimensions.append(("compatible", ""))
                    elif raw_countries and all(normalized) and not raw_regions:
                        dimensions.append(("incompatible", "geography_outside_coverage"))
                    else:
                        dimensions.append(("unknown", "geography_coverage_unverified"))

        if need.time_start is not None or need.time_end is not None:
            requested_start = (
                _scope_date(need.time_start, upper_bound=False)
                if need.time_start is not None
                else None
            )
            requested_end = (
                _scope_date(need.time_end, upper_bound=True) if need.time_end is not None else None
            )
            if (
                (need.time_start is not None and requested_start is None)
                or (need.time_end is not None and requested_end is None)
                or (
                    requested_start is not None
                    and requested_end is not None
                    and requested_start > requested_end
                )
            ):
                dimensions.append(("unknown", "time_scope_unverified"))
            else:
                raw_start = getattr(coverage, "time_start", None)
                raw_end = getattr(coverage, "time_end", None)
                if raw_start is None:
                    raw_start = getattr(dataset, "temporal_start", None)
                if raw_end is None:
                    raw_end = getattr(dataset, "temporal_end", None)
                parsed_range = _scope_year_range(getattr(coverage, "time_range", ""))
                coverage_start = (
                    _scope_date(raw_start, upper_bound=False)
                    if raw_start is not None
                    else parsed_range[0]
                    if parsed_range is not None
                    else None
                )
                coverage_end = (
                    _scope_date(raw_end, upper_bound=True)
                    if raw_end is not None
                    else parsed_range[1]
                    if parsed_range is not None
                    else None
                )
                if (
                    (raw_start is not None and coverage_start is None)
                    or (raw_end is not None and coverage_end is None)
                    or (
                        coverage_start is not None
                        and coverage_end is not None
                        and coverage_start > coverage_end
                    )
                ):
                    dimensions.append(("unknown", "time_coverage_unverified"))
                elif (
                    requested_start is not None
                    and requested_end is not None
                    and coverage_start is not None
                    and coverage_end is not None
                ):
                    if requested_start > coverage_end or requested_end < coverage_start:
                        dimensions.append(("incompatible", "time_outside_coverage"))
                    elif requested_start >= coverage_start and requested_end <= coverage_end:
                        dimensions.append(("compatible", ""))
                    else:
                        dimensions.append(("unknown", "time_coverage_partial_overlap"))
                elif requested_start is not None and coverage_end is not None:
                    dimensions.append(
                        ("incompatible", "time_outside_coverage")
                        if requested_start > coverage_end
                        else ("unknown", "time_coverage_unverified")
                    )
                elif requested_end is not None and coverage_start is not None:
                    dimensions.append(
                        ("incompatible", "time_outside_coverage")
                        if requested_end < coverage_start
                        else ("unknown", "time_coverage_unverified")
                    )
                else:
                    dimensions.append(("unknown", "time_coverage_unverified"))

        if any(status == "incompatible" for status, _ in dimensions):
            reason = next(reason for status, reason in dimensions if status == "incompatible")
            return "incompatible", reason
        if any(status == "unknown" for status, _ in dimensions):
            reason = next(reason for status, reason in dimensions if status == "unknown")
            return "unknown", reason
        return "compatible", ""

    def _catalog_dataset_id_for_target(
        self,
        *,
        metric_id: str,
        connector_id: str,
        request_dataset_id: str,
        profile_id: str | None,
        run_profile: CatalogRunProfile | None,
        source_name: str | None = None,
    ) -> str | None:
        """Join a selected target to one reconciled, profile-admitted catalog row.

        Plan metadata and identifier spelling are not identity evidence. The
        complete C05 binding population is the sole relation used here; its
        refusals intentionally propagate to the retrieval caller.
        """
        catalog = self._dataset_catalog
        population_reader = getattr(catalog, "reconciled_metric_binding_population", None)
        if not callable(population_reader):
            return None

        bindings = population_reader(metric_id)
        exact: set[tuple[str, str]] = set()
        requested_profile = _optional_text(profile_id)
        for binding in bindings:
            if str(getattr(binding, "metric_id", "") or "").strip() != metric_id:
                continue
            if str(getattr(binding, "connector_id", "") or "").strip() != connector_id:
                continue
            if str(getattr(binding, "request_dataset_id", "") or "").strip() != request_dataset_id:
                continue
            if _optional_text(getattr(binding, "profile_id", None)) != requested_profile:
                continue

            binding_source = str(getattr(binding, "source", "") or "").strip()
            if source_name is not None and binding_source != source_name:
                continue
            if not self._catalog_source_is_enabled(
                binding_source,
                connector_id=connector_id,
                run_profile=run_profile,
            ):
                continue
            catalog_dataset_id = str(getattr(binding, "catalog_dataset_id", "") or "").strip()
            if catalog_dataset_id:
                exact.add((catalog_dataset_id, binding_source))

        if len(exact) != 1:
            return None
        return next(iter(exact))[0]

    def _filter_known_incompatible_catalog_outputs(
        self,
        plans: list[FetchPlan],
        candidates: Sequence[_CatalogCandidateT],
        data_needs: list[DataNeed],
        *,
        run_profile: CatalogRunProfile | None = None,
    ) -> tuple[list[FetchPlan], list[_CatalogCandidateT], list[str]]:
        """Filter known-incompatible outputs at the selected resolve boundary.

        The same target predicate covers executable plans, public candidates,
        and fallbacks. DataNeed is an occurrence list, not a metric-keyed map;
        without an occurrence ID, ambiguous mixed scopes remain unverified.
        """
        needs_by_metric: dict[str, list[DataNeed]] = {}
        for need in data_needs:
            needs_by_metric.setdefault(need.metric, []).append(need)
        warnings: list[str] = []

        def record(
            *,
            need: DataNeed,
            dataset_id: str | None,
            status: str,
            reason: str,
        ) -> None:
            if status == "incompatible":
                warnings.append(
                    f"catalog_scope_incompatible:{need.metric}:{dataset_id or 'unknown'}"
                )
            elif status == "unknown":
                warnings.append(
                    f"catalog_scope_unverified:{need.metric}:{reason or 'identity_unresolved'}"
                )

        def target_status(
            *,
            catalog_metric_id: str,
            request_metric_id: str,
            connector_id: str,
            request_dataset_id: str,
            profile_id: str | None,
        ) -> str:
            matching_needs = needs_by_metric.get(request_metric_id, [])
            if not matching_needs:
                warnings.append(
                    f"catalog_scope_unverified:{request_metric_id}:request_scope_unmatched"
                )
                return "unknown"
            scoped_needs = [need for need in matching_needs if self._has_explicit_scope(need)]
            if not scoped_needs:
                return "compatible"

            catalog_dataset_id = self._catalog_dataset_id_for_target(
                metric_id=catalog_metric_id,
                connector_id=connector_id,
                request_dataset_id=request_dataset_id,
                profile_id=profile_id,
                run_profile=run_profile,
            )
            if catalog_dataset_id is None:
                for need in scoped_needs:
                    record(
                        need=need,
                        dataset_id=None,
                        status="unknown",
                        reason="catalog_identity_unresolved",
                    )
                return "unknown"

            statuses: list[str] = []
            for need in scoped_needs:
                status, reason = self._catalog_scope_status(need, catalog_dataset_id)
                statuses.append(status)
                record(
                    need=need,
                    dataset_id=catalog_dataset_id,
                    status=status,
                    reason=reason,
                )

            has_unscoped_occurrence = len(scoped_needs) != len(matching_needs)
            if (
                not has_unscoped_occurrence
                and statuses
                and all(status == "incompatible" for status in statuses)
            ):
                return "incompatible"
            if (
                not has_unscoped_occurrence
                and statuses
                and all(status == "compatible" for status in statuses)
            ):
                return "compatible"
            if len(set(statuses)) > 1 or has_unscoped_occurrence:
                warnings.append(
                    f"catalog_scope_unverified:{request_metric_id}:duplicate_need_scope_ambiguous"
                )
            return "unknown"

        retained_plans: list[FetchPlan] = []
        for plan in plans:
            status = target_status(
                catalog_metric_id=plan.metric_id,
                request_metric_id=plan.metric_id,
                connector_id=plan.connector_id,
                request_dataset_id=plan.dataset_id,
                profile_id=plan.profile_id,
            )
            if status == "incompatible":
                continue

            fallbacks = []
            for fallback in plan.fallbacks:
                fallback_metric = fallback.metric_id or plan.metric_id
                fallback_status = target_status(
                    catalog_metric_id=fallback_metric,
                    request_metric_id=plan.metric_id,
                    connector_id=fallback.connector_id,
                    request_dataset_id=fallback.dataset_id,
                    profile_id=fallback.profile_id,
                )
                if fallback_status != "incompatible":
                    fallbacks.append(fallback)
            retained_plans.append(
                plan
                if fallbacks == plan.fallbacks
                else plan.model_copy(update={"fallbacks": fallbacks})
            )

        retained_candidates = [
            candidate
            for candidate in candidates
            if target_status(
                catalog_metric_id=candidate.metric_id,
                request_metric_id=candidate.metric_id,
                connector_id=candidate.connector_id,
                request_dataset_id=candidate.dataset_id,
                profile_id=candidate.profile_id,
            )
            != "incompatible"
        ]
        return retained_plans, retained_candidates, list(dict.fromkeys(warnings))

    def _filter_known_incompatible_catalog_targets(
        self,
        plans: list[FetchPlan],
        data_needs: list[DataNeed],
        *,
        run_profile: CatalogRunProfile | None = None,
    ) -> tuple[list[FetchPlan], list[str]]:
        """Keep the existing plan-only helper contract for focused callers."""
        retained, _, warnings = self._filter_known_incompatible_catalog_outputs(
            plans,
            [],
            data_needs,
            run_profile=run_profile,
        )
        return retained, warnings

    def resolve(
        self,
        request: DataResolveRequest,
        *,
        run_profile: CatalogRunProfile | None = None,
    ) -> ResolveOutcome:
        if run_profile is not None and request.catalog_run_profile is not None:
            if run_profile != request.catalog_run_profile:
                raise _catalog_selection_error("catalog_run_profile_conflict")
        elif run_profile is None:
            run_profile = request.catalog_run_profile
        started = time.perf_counter()
        warnings: list[str] = []
        candidates: list[MetricCandidate] = []
        fetch_plans: list[FetchPlan] = []
        phase_metrics: list[dict[str, object]] = []
        with self._tracer.start_as_current_span(
            FABRIC_TRACE_NAMES["retrieval_resolve"],
            attributes={
                "retrieval.mode": request.mode,
                "retrieval.need_count": len(request.data_needs),
            },
        ):
            fastlane_enabled = _flag("POLISYOS_RETRIEVAL_FASTLANE_ENABLED", default=True)
            explore_enabled = _flag("POLISYOS_RETRIEVAL_EXPLORE_ENABLED", default=True)

            unresolved: list[DataNeed] = list(request.data_needs)
            if request.mode in {"fastlane", "hybrid"} and fastlane_enabled:
                phase_start = time.perf_counter()
                fast = self._fastlane.resolve(request.data_needs)
                fast_plans, scoped_fast_candidates, scope_warnings = (
                    self._filter_known_incompatible_catalog_outputs(
                        list(fast.fetch_plans),
                        list(fast.candidates),
                        request.data_needs,
                        run_profile=run_profile,
                    )
                )
                fast_candidates = scoped_fast_candidates
                candidates.extend(fast_candidates)
                fetch_plans.extend(fast_plans)
                warnings.extend(scope_warnings)
                warnings.extend(fast.warnings)
                resolved_metrics = {plan.metric_id for plan in fast_plans}
                unresolved = [
                    need for need in request.data_needs if need.metric not in resolved_metrics
                ]
                phase_metrics.append(
                    {
                        "phase": "resolve_fast_lane",
                        "lane": "fastlane",
                        "duration_ms": int((time.perf_counter() - phase_start) * 1000),
                        "candidates_total": len(fast_candidates),
                        "candidates_selected": len(fast_plans),
                        "docs_fetched": 0,
                        "route_breakdown": self._route_breakdown(fast_candidates),
                    }
                )
            elif request.mode in {"fastlane", "hybrid"} and not fastlane_enabled:
                warnings.append("fastlane_disabled_by_feature_flag")

            if unresolved and self._dataset_catalog is not None:
                phase_start = time.perf_counter()
                catalog_scope_warnings: list[str] = []
                catalog_plans, catalog_candidates = self._resolve_via_catalog(
                    unresolved,
                    run_profile=run_profile,
                    warnings=catalog_scope_warnings,
                )
                scoped_catalog_plans, scoped_catalog_candidates, scope_warnings = (
                    self._filter_known_incompatible_catalog_outputs(
                        catalog_plans,
                        catalog_candidates,
                        unresolved,
                        run_profile=run_profile,
                    )
                )
                warnings.extend(catalog_scope_warnings)
                warnings.extend(scope_warnings)
                fetch_plans.extend(scoped_catalog_plans)
                candidates.extend(scoped_catalog_candidates)
                resolved_metrics = {plan.metric_id for plan in fetch_plans}
                unresolved = [need for need in unresolved if need.metric not in resolved_metrics]
                phase_metrics.append(
                    {
                        "phase": "resolve_dataset_catalog",
                        "lane": "catalog",
                        "duration_ms": int((time.perf_counter() - phase_start) * 1000),
                        "candidates_total": len(scoped_catalog_candidates),
                        "candidates_selected": len(scoped_catalog_plans),
                        "docs_fetched": 0,
                        "route_breakdown": self._route_breakdown(scoped_catalog_candidates),
                    }
                )

            should_explore = request.mode == "explorelane" or (
                request.mode == "hybrid" and request.allow_explore_fallback and bool(unresolved)
            )
            if should_explore:
                if not explore_enabled:
                    warnings.append("explorelane_disabled_by_feature_flag")
                else:
                    phase_start = time.perf_counter()
                    discover_outcome = self.discover(
                        data_needs=request.data_needs
                        if request.mode == "explorelane"
                        else unresolved
                    )
                    warnings.extend(discover_outcome.warnings)
                    # The local index remains a raw discovery cache. Bind each
                    # request's selected scope before candidate/plan emission.
                    self._update_local_index(discover_outcome.candidates)
                    _, scoped_discovery_candidates, scope_warnings = (
                        self._filter_known_incompatible_catalog_outputs(
                            [],
                            list(discover_outcome.candidates),
                            request.data_needs,
                            run_profile=run_profile,
                        )
                    )
                    warnings.extend(scope_warnings)
                    explore_candidates = scoped_discovery_candidates
                    explore_plans = self._build_plans_from_discovery(
                        candidates=explore_candidates,
                        existing_metric_ids={plan.metric_id for plan in fetch_plans},
                        data_needs=request.data_needs,
                    )
                    explore_plans, _, scope_warnings = (
                        self._filter_known_incompatible_catalog_outputs(
                            explore_plans,
                            [],
                            request.data_needs,
                            run_profile=run_profile,
                        )
                    )
                    warnings.extend(scope_warnings)
                    fetch_plans.extend(explore_plans)
                    candidates.extend(
                        [
                            MetricCandidate(
                                candidate_id=item.candidate_id,
                                metric_id=item.metric_id,
                                connector_id=item.connector_id,
                                dataset_id=item.dataset_id,
                                profile_id=item.profile_id,
                                source_lane="explorelane",
                                confidence=item.confidence,
                                rank=index + 1,
                                trust_score=0.5,
                                freshness_score=0.5,
                                coverage_estimate=item.coverage_estimate,
                                latency_estimate_ms=item.latency_estimate_ms,
                                filters_template={},
                                match_reason="explore_lane_discovery",
                                metadata=item.metadata,
                            )
                            for index, item in enumerate(explore_candidates)
                        ]
                    )
                    phase_metrics.append(
                        {
                            "phase": "discover_explore_lane",
                            "lane": "explorelane",
                            "duration_ms": int((time.perf_counter() - phase_start) * 1000),
                            "candidates_total": len(explore_candidates),
                            "candidates_selected": len(explore_plans),
                            "docs_fetched": discover_outcome.docs_fetched_total,
                            "route_breakdown": self._route_breakdown(explore_candidates),
                        }
                    )

            warnings = list(dict.fromkeys(warnings))
            if not fetch_plans:
                warnings.append("no_fetch_plans_resolved")

            total_duration_ms = int((time.perf_counter() - started) * 1000)
            with self._state_lock:
                local_index_docs_total = len(self._local_index_docs)
                local_index_size_bytes = self._index_size_bytes
            telemetry = {
                "mode": request.mode,
                "lane_used": self._lane_used(fetch_plans),
                "metadata_docs_fetched": sum(
                    _coerce_int(item.get("docs_fetched", 0))
                    for item in phase_metrics
                    if isinstance(item, dict)
                ),
                "local_index_size_bytes": local_index_size_bytes,
                "local_index_docs_total": local_index_docs_total,
                "candidates_filtered": max(0, len(candidates) - len(fetch_plans)),
                "candidates_promoted": 0,
                "duration_ms": total_duration_ms,
                "phases": phase_metrics,
                "warnings": list(warnings),
                "resolution_routes": {
                    "candidates": self._route_breakdown(candidates),
                    "selected": self._route_breakdown(fetch_plans),
                },
            }
            if getattr(self._metrics, "record_fabric_query", None):
                self._metrics.record_fabric_query(
                    operation="resolve",
                    duration_seconds=max(total_duration_ms / 1000.0, 0.0),
                    row_count=len(fetch_plans),
                    status="success" if fetch_plans else "empty",
                )
            return ResolveOutcome(
                mode=request.mode,
                fetch_plans=fetch_plans,
                candidates=candidates,
                warnings=warnings,
                telemetry=telemetry,
            )

    def discover(
        self,
        *,
        data_needs: list[DataNeed],
        max_sources_per_query: int = 5,
        max_discovery_calls_per_source: int = 25,
        max_candidates_total: int = 50,
        time_budget_ms: int = 5_000,
        cost_budget_usd: float = 0.0,
    ) -> DiscoverOutcome:
        started = time.perf_counter()
        limits = ExploreLaneLimits(
            max_sources_per_query=max_sources_per_query,
            max_discovery_calls_per_source=max_discovery_calls_per_source,
            max_candidates_total=max_candidates_total,
            time_budget_ms=time_budget_ms,
            cost_budget_usd=cost_budget_usd,
        )
        with self._tracer.start_as_current_span(
            FABRIC_TRACE_NAMES["retrieval_discover"],
            attributes={"retrieval.need_count": len(data_needs)},
        ):
            result: ExploreLaneDiscoverResult = self._explore.discover(data_needs, limits=limits)
        if getattr(self._metrics, "record_fabric_query", None):
            self._metrics.record_fabric_query(
                operation="discover",
                duration_seconds=max(time.perf_counter() - started, 0.0),
                row_count=len(result.candidates),
                status="success",
            )
        return DiscoverOutcome(
            candidates=result.candidates,
            docs_fetched_total=result.docs_fetched_total,
            warnings=result.warnings,
        )

    def _bind_execution(
        self,
        plan: FetchPlan,
        *,
        registration_binding: _ConnectorRegistrationBinding | None = None,
    ) -> _FetchExecutionBinding:
        """Capture the executor-owned config and registry snapshot for one fetch plan."""
        return self._executor._bind_execution(
            plan,
            registration_binding=registration_binding,
        )

    def preview(self, plan: FetchPlan, *, allow_fallback: bool = True) -> ExecutePlanResult:
        return self._executor.preview(plan, allow_fallback=allow_fallback)

    def execute_fetch_plans(
        self,
        plans: list[FetchPlan],
        *,
        persist_payload: bool = False,
        allow_fallback: bool = True,
        execution_binding: _FetchExecutionBinding | None = None,
    ) -> ExecuteOutcome:
        if execution_binding is not None and len(plans) != 1:
            raise ValueError("fabric_fetch_execution_binding_requires_one_plan")
        started = time.perf_counter()
        data_metrics: list[Any] = []
        previews: list[ExecutePlanResult] = []
        promoted_count = 0
        fallback_triggered_count = 0
        with self._tracer.start_as_current_span(
            FABRIC_TRACE_NAMES["retrieval_execute"],
            attributes={"retrieval.plan_count": len(plans)},
        ):
            for plan in plans:
                outcome = self._executor.execute(
                    plan,
                    persist_payload=persist_payload,
                    allow_fallback=allow_fallback,
                    dataset_catalog=self._dataset_catalog if persist_payload else None,
                    execution_binding=execution_binding,
                )
                previews.append(outcome)
                if outcome.fallback_used:
                    fallback_triggered_count += 1
                if outcome.metric is not None:
                    data_metrics.append(outcome.metric)
                    deferred_promotions = self._capture_deferred_promotions.get()
                    if deferred_promotions is None:
                        promoted_count += self._emit_promotion_candidate(
                            plan=outcome.used_plan,
                            completeness=outcome.metric.completeness,
                        )
                    else:
                        deferred_promotions.append((outcome.used_plan, outcome.metric.completeness))

        with self._state_lock:
            index_docs_total = len(self._local_index_docs)
            index_size_bytes = self._index_size_bytes
        data_context = DataContext(
            metrics=data_metrics,
            metadata_docs_fetched=0,
            index_docs_total=index_docs_total,
            index_size_bytes=index_size_bytes,
        )
        execute_outcome = ExecuteOutcome(
            data_context=data_context,
            previews=previews,
            promoted_count=promoted_count,
            fallback_triggered_count=fallback_triggered_count,
        )
        if getattr(self._metrics, "record_fabric_query", None):
            self._metrics.record_fabric_query(
                operation="execute_fetch_plans",
                duration_seconds=max(time.perf_counter() - started, 0.0),
                row_count=sum(metric.row_count for metric in data_metrics),
                status="success" if previews else "empty",
            )
        return execute_outcome

    def execute_persisted_fetch_capture(
        self,
        plans: Sequence[FetchPlan],
        *,
        preflight: Callable[[FetchCapturePreflightView], object],
        postflight: Callable[[FetchCapturePostflightView], object],
    ) -> ExecuteOutcome:
        """Execute one persisted fetch under owner-managed source and registry binding.

        The callbacks receive scalar projections, not the raw catalog binding,
        connector configuration, or mutable metric/ref objects. Config
        fingerprints identify the one immutable effective config captured for
        this operation; profile-registry updates do not reroute it or establish
        live profile currentness. Callbacks may refuse by raising. A callback
        return value is never accepted as an authorization result: callbacks
        must return ``None``, after which this owner rechecks the original
        plan, catalog bytes, captured config, store identity, and registration.

        Args:
            plans: The single resolved plan to execute and persist.
            preflight: Runtime-owned route validation; raise to refuse before fetch.
            postflight: Runtime-owned persisted-result validation; raise to refuse
                returning the outcome.

        Returns:
            The existing execution outcome after both callbacks and owner rechecks.

        Raises:
            ValueError: If the plan, owner snapshots, callback result, execution
                shape, or persisted references fail their checks.
        """
        if len(plans) != 1:
            raise ValueError("fabric_fetch_capture_requires_one_plan")
        if not callable(preflight) or not callable(postflight):
            raise ValueError("fabric_fetch_capture_callback_missing")
        try:
            checked = FetchPlan.model_validate(plans[0].model_dump(mode="python"))
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("fabric_fetch_capture_plan_invalid") from exc

        executor = self._executor
        catalog = self._dataset_catalog
        store = self._artifact_store
        if not isinstance(catalog, catalog_read_api.DatasetCatalogGraph):
            raise ValueError("fabric_fetch_capture_catalog_owner_missing")
        if store is None:
            raise ValueError("fabric_fetch_capture_store_missing")
        if executor.artifact_store is not store:
            raise ValueError("fabric_fetch_capture_store_identity_mismatch")

        binding = catalog.bind_fetch_target(
            metric_id=checked.metric_id,
            connector_id=checked.connector_id,
            request_dataset_id=checked.dataset_id,
            profile_id=checked.profile_id,
            filters=checked.filters,
        )
        if binding is None:
            raise ValueError("fabric_fetch_capture_catalog_binding_missing")
        target = binding.target
        if (
            binding.metric_id != checked.metric_id
            or binding.connector_id != checked.connector_id
            or binding.request_dataset_id != checked.dataset_id
            or binding.profile_id != checked.profile_id
            or binding.requested_filters != checked.filters
            or target.connector_id != checked.connector_id
            or target.request_dataset_id != checked.dataset_id
            or (target.profile_id or None) != checked.profile_id
        ):
            raise ValueError("fabric_fetch_capture_binding_plan_mismatch")
        binding_fingerprint = _capture_binding_fingerprint(binding)
        execution_binding = executor._bind_execution(checked)
        executor._validate_execution_binding(checked, execution_binding)
        registration = execution_binding.registration_binding
        connector_params = target.connector_params
        connector_params_mappable = isinstance(connector_params, Mapping)
        connector_param_locators = tuple(
            (name, _capture_locator_view(connector_params[name]))
            for name in ("url", "path")
            if connector_params_mappable and name in connector_params
        )
        instance = getattr(registration, "instance", None)
        view = FetchCapturePreflightView(
            plan_id=checked.plan_id,
            metric_id=checked.metric_id,
            connector_id=checked.connector_id,
            profile_id=checked.profile_id,
            plan_fingerprint=execution_binding.plan_fingerprint,
            catalog_binding_fingerprint=binding_fingerprint,
            effective_config_fingerprint=execution_binding.config_fingerprint,
            source_profile_fingerprint=(
                execution_binding.connection_config.source_profile_fingerprint
            ),
            target_distribution_id=target.distribution_id,
            target_connector_id=target.connector_id,
            target_profile_id=target.profile_id or None,
            connector_params_mappable=connector_params_mappable,
            connector_param_locators=connector_param_locators,
            effective_locator=_capture_locator_view(execution_binding.connection_config.url),
            connector_class=getattr(registration, "connector_class", None),
            connector_instance_class=type(instance) if instance is not None else None,
        )

        def validate_captured_owner_state() -> None:
            if (
                self._executor is not executor
                or self._dataset_catalog is not catalog
                or self._artifact_store is not store
                or executor.artifact_store is not store
            ):
                raise ValueError("fabric_fetch_capture_owner_identity_changed")
            executor._validate_execution_binding(checked, execution_binding)
            verified_binding = catalog.verify_fetch_binding(binding)
            current_binding = catalog.bind_fetch_target(
                metric_id=checked.metric_id,
                connector_id=checked.connector_id,
                request_dataset_id=checked.dataset_id,
                profile_id=checked.profile_id,
                filters=checked.filters,
            )
            if (
                _capture_binding_fingerprint(verified_binding) != binding_fingerprint
                or _capture_binding_fingerprint(current_binding) != binding_fingerprint
            ):
                raise ValueError("fabric_fetch_capture_catalog_binding_changed")

        if preflight(view) is not None:
            raise ValueError("fabric_fetch_capture_preflight_must_return_none")
        validate_captured_owner_state()
        deferred_promotions: list[tuple[FetchPlan, float]] = []
        promotion_token = self._capture_deferred_promotions.set(deferred_promotions)
        try:
            outcome = self.execute_fetch_plans(
                [checked.model_copy(deep=True)],
                persist_payload=True,
                allow_fallback=False,
                execution_binding=execution_binding,
            )
        finally:
            self._capture_deferred_promotions.reset(promotion_token)
        if (
            len(outcome.previews) != 1
            or outcome.fallback_triggered_count != 0
            or outcome.previews[0].fallback_used
            or outcome.previews[0].used_plan != checked
        ):
            raise ValueError("fabric_fetch_capture_execution_shape_mismatch")
        metrics = tuple(outcome.data_context.metrics)
        if len(metrics) != 1:
            raise ValueError("fabric_fetch_capture_plan_metric_cardinality_mismatch")
        metric = metrics[0]
        if (
            metric.plan_id != checked.plan_id
            or metric.metric_id != checked.metric_id
            or metric.connector_id != checked.connector_id
            or metric.dataset_id != checked.dataset_id
        ):
            raise ValueError("fabric_fetch_capture_plan_metric_identity_mismatch")
        payload_ref = _capture_artifact_reference_view(metric.payload_ref)
        receipt_ref = _capture_artifact_reference_view(metric.fetch_receipt_ref)
        if payload_ref is None or receipt_ref is None:
            raise ValueError("fabric_fetch_capture_refs_missing")
        postflight_view = FetchCapturePostflightView(
            plan_fingerprint=execution_binding.plan_fingerprint,
            effective_config_fingerprint=execution_binding.config_fingerprint,
            source_profile_fingerprint=(
                execution_binding.connection_config.source_profile_fingerprint
            ),
            metrics=(
                FetchCaptureMetricView(
                    plan_id=metric.plan_id,
                    metric_id=metric.metric_id,
                    row_count=metric.row_count,
                    completeness=metric.completeness,
                    source_lane=str(metric.source_lane),
                    payload_ref=payload_ref,
                    fetch_receipt_ref=receipt_ref,
                ),
            ),
        )
        if postflight(postflight_view) is not None:
            raise ValueError("fabric_fetch_capture_postflight_must_return_none")
        validate_captured_owner_state()
        promoted_count = sum(
            self._emit_promotion_candidate(plan=plan, completeness=completeness)
            for plan, completeness in deferred_promotions
        )
        if promoted_count:
            outcome = replace(outcome, promoted_count=promoted_count)
        return outcome

    def search_catalog(
        self,
        *,
        metric_query: str,
        geography: str | None = None,
        limit: int = 25,
    ) -> list[MetricCandidate]:
        result: list[MetricCandidate] = self._fastlane.search_catalog(
            metric_query=metric_query,
            geography=geography,
            limit=limit,
        )
        return result

    def get_index_stats(self) -> IndexStats:
        with self._state_lock:
            source_coverage: dict[str, int] = {}
            for row in self._local_index_docs.values():
                source = str(row.get("connector_id") or "unknown")
                source_coverage[source] = source_coverage.get(source, 0) + 1
            return IndexStats(
                index_docs_total=len(self._local_index_docs),
                index_size_bytes=self._index_size_bytes,
                indexed_sources=len(source_coverage),
                docs_added_last_run=self._docs_added_last_run,
                source_coverage=source_coverage,
                last_updated=self._last_updated,
            )

    def list_promotion_candidates(self) -> list[PromotionCandidate]:
        with self._state_lock:
            values = list(self._promotion_queue.values())
        values.sort(
            key=lambda item: item.created_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return values

    def approve_promotion(self, promotion_id: str, *, reason: str | None = None) -> bool:
        with self._state_lock:
            candidate = self._promotion_queue.get(promotion_id)
            if candidate is None:
                return False
            if candidate.status == "approved":
                return True
            updated = candidate.model_copy(
                update={
                    "status": "approved",
                    "metadata": {
                        **candidate.metadata,
                        "approval_reason": reason or "",
                        "approved_at": datetime.now(UTC).isoformat(),
                    },
                }
            )
            self._store_promotion_candidate_locked(updated)
        self._promote_binding(updated)
        return True

    def reject_promotion(self, promotion_id: str, *, reason: str | None = None) -> bool:
        with self._state_lock:
            candidate = self._promotion_queue.get(promotion_id)
            if candidate is None:
                return False
            self._store_promotion_candidate_locked(
                candidate.model_copy(
                    update={
                        "status": "rejected",
                        "metadata": {
                            **candidate.metadata,
                            "rejection_reason": reason or "",
                            "rejected_at": datetime.now(UTC).isoformat(),
                        },
                    }
                )
            )
        return True

    def _build_plans_from_discovery(
        self,
        *,
        candidates: list[DiscoveryCandidate],
        existing_metric_ids: set[str],
        data_needs: list[DataNeed],
    ) -> list[FetchPlan]:
        by_metric: dict[str, list[DiscoveryCandidate]] = {}
        for candidate in candidates:
            by_metric.setdefault(candidate.metric_id, []).append(candidate)
        need_map = {need.metric: need for need in data_needs}
        plans: list[FetchPlan] = []
        for metric_id, rows in by_metric.items():
            if metric_id in existing_metric_ids:
                continue
            rows.sort(key=lambda item: (-item.confidence, item.connector_id, item.dataset_id))
            primary = rows[0]
            need = need_map.get(metric_id, DataNeed(metric=metric_id))
            fallbacks = [
                FetchPlanFallback(
                    connector_id=item.connector_id,
                    dataset_id=item.dataset_id,
                    metric_id=item.metric_id,
                    profile_id=item.profile_id,
                    filters={},
                    metadata={
                        "resolution_route": item.metadata.get("resolution_route", item.source_lane),
                        "confidence": item.confidence,
                    },
                )
                for item in rows[1:3]
            ]
            plans.append(
                FetchPlan(
                    plan_id=_stable_id("plan", metric_id, primary.connector_id, primary.dataset_id),
                    metric_id=metric_id,
                    connector_id=primary.connector_id,
                    dataset_id=primary.dataset_id,
                    profile_id=primary.profile_id,
                    filters={},
                    date_start=need.time_start,
                    date_end=need.time_end,
                    granularity=need.granularity,
                    quality_min=need.quality_min,
                    source_lane="explorelane",
                    fallbacks=fallbacks,
                    metadata={
                        "discovered": True,
                        "confidence": primary.confidence,
                        "resolution_route": primary.metadata.get("resolution_route", "explorelane"),
                    },
                )
            )
        return plans

    def _update_local_index(self, candidates: list[DiscoveryCandidate]) -> None:
        added = 0
        now_iso = datetime.now(UTC).isoformat()
        with self._state_lock:
            for candidate in candidates:
                key = f"{candidate.connector_id}:{candidate.dataset_id}"
                if key not in self._local_index_docs:
                    added += 1
                else:
                    self._local_index_docs.pop(key, None)
                self._local_index_docs[key] = {
                    "connector_id": candidate.connector_id,
                    "dataset_id": candidate.dataset_id,
                    "metric_id": candidate.metric_id,
                    "confidence": candidate.confidence,
                    "profile_id": candidate.profile_id,
                    "updated_at": now_iso,
                }
            self._trim_ordered_dict_locked(self._local_index_docs, self._max_local_index_docs)
            self._docs_added_last_run = added
            self._recompute_index_size_locked()
            self._last_updated = datetime.now(UTC)

    def _emit_promotion_candidate(self, *, plan: FetchPlan, completeness: float) -> int:
        if not _flag("POLISYOS_RETRIEVAL_PROMOTION_ENABLED", default=True):
            return 0
        if completeness < plan.quality_min:
            return 0
        if plan.source_lane != "explorelane":
            return 0
        promotion_id = _stable_id("promo", plan.metric_id, plan.connector_id, plan.dataset_id)
        with self._state_lock:
            if promotion_id in self._promotion_queue:
                return 0
            candidate = PromotionCandidate(
                promotion_id=promotion_id,
                metric_id=plan.metric_id,
                connector_id=plan.connector_id,
                dataset_id=plan.dataset_id,
                profile_id=plan.profile_id,
                source_lane="explorelane",
                confidence=(
                    _coerce_float(plan.metadata.get("confidence", 0.8), default=0.8)
                    if isinstance(plan.metadata, dict)
                    else 0.8
                ),
                signals=[
                    "resolved_successfully",
                    "fetch_successfully",
                    "quality_pass",
                ],
                status="pending",
                created_at=datetime.now(UTC),
                metadata={
                    "quality_min": plan.quality_min,
                    "completeness": completeness,
                },
            )
            self._store_promotion_candidate_locked(candidate)
        return 1

    def _promote_binding(self, candidate: PromotionCandidate) -> None:
        binding = SourceBinding(
            metric_id=candidate.metric_id,
            connector_id=candidate.connector_id,
            dataset_id=candidate.dataset_id,
            profile_id=candidate.profile_id,
            geography_patterns=["*"],
            granularity=[],
            priority=25,
            trust=max(0.5, min(1.0, candidate.confidence)),
            filters_template={},
            tags=["promoted"],
            aliases=[],
            metadata={"promotion_id": candidate.promotion_id},
        )
        self._fastlane.binding_registry.upsert(binding)
        self._fastlane.refresh_search_index()
        if _flag("POLISYOS_RETRIEVAL_PROMOTION_PERSIST", default=False):
            self._fastlane.binding_registry.persist()

    def _recompute_index_size_locked(self) -> None:
        self._index_size_bytes = len(
            json.dumps(dict(self._local_index_docs), ensure_ascii=True, sort_keys=True).encode(
                "utf-8"
            )
        )

    @staticmethod
    def _trim_ordered_dict_locked(mapping: OrderedDict[str, Any], max_items: int) -> None:
        while len(mapping) > max_items:
            mapping.popitem(last=False)

    def _store_promotion_candidate_locked(self, candidate: PromotionCandidate) -> None:
        self._promotion_queue.pop(candidate.promotion_id, None)
        self._promotion_queue[candidate.promotion_id] = candidate
        self._trim_ordered_dict_locked(self._promotion_queue, self._max_promotion_candidates)

    def _catalog_publish_admission(
        self, catalog: object, run_profile: CatalogRunProfile | None
    ) -> tuple[str, str, dict[str, object] | None]:
        """Join recomputed local publish currentness to the exact open DB session."""
        if run_profile is None:
            return "not_established", "catalog_run_profile_unresolved", None
        path = getattr(catalog, "database_path", None)
        identity_reader = getattr(catalog, "source_content_identities", None)
        if not isinstance(path, Path) or not callable(identity_reader):
            return "not_established", "catalog_open_session_identity_unavailable", None
        try:
            baseline, _overlay_path, overlay = identity_reader()
            if overlay is not None:
                return (
                    "not_established",
                    "catalog_overlay_not_bound_by_publish_receipt",
                    None,
                )
            resolver = cast(
                "Callable[..., dict[str, object]]",
                catalog_read_api._current_catalog_publish_receipt,
            )
            receipt = resolver(path, run_profile=run_profile)
        except Exception as exc:
            if isinstance(exc, catalog_read_api.CatalogReadSourceError):
                raise
            return "not_established", "catalog_publish_receipt_unavailable", None
        state = str(receipt.get("state") or "not_established")
        if state != "current":
            return state, str(receipt.get("reason") or "receipt_not_current"), None
        expected = {
            "source_path": baseline.source_path,
            "content_sha256": baseline.content_sha256,
            "byte_size": baseline.byte_size,
        }
        if receipt.get("database_identity") != expected:
            return "stale", "publish_database_identity_differs_from_open_session", None
        profile_coverage = receipt.get("profile_input_coverage")
        if receipt.get("profile_input_coverage_state") != "established" or not isinstance(
            profile_coverage, dict
        ):
            return "not_established", "catalog_profile_input_coverage_unknown", None
        return "current", "publish_receipt_matches_open_session", profile_coverage

    def _catalog_profile_plan_admission(
        self, profile_id: str | None, profile_coverage: object
    ) -> tuple[bool, str]:
        """Admit only rows whose producer-time excluded-input scope is established."""
        if not profile_id:
            return False, "catalog_profile_id_unresolved"
        from polisyos.data_forge.read_api.catalog import (
            profile_input_coverage_currentness,
        )

        coverage_state, profiles = profile_input_coverage_currentness(
            profile_coverage,
            missing=profile_coverage is None,
        )
        if coverage_state == "legacy_unknown":
            return False, "catalog_profile_input_coverage_unknown"
        if coverage_state == "malformed" or profiles is None:
            return False, "catalog_profile_input_coverage_malformed"
        if coverage_state != "established":
            return False, "catalog_profile_inputs_not_established"
        if profile_id not in profiles:
            return False, "catalog_profile_input_coverage_unmatched"
        return True, "catalog_profile_inputs_covered"

    def _resolve_via_catalog(
        self,
        unresolved: list[DataNeed],
        *,
        run_profile: CatalogRunProfile | None = None,
        warnings: list[str] | None = None,
    ) -> tuple[list[FetchPlan], list[MetricCandidate]]:
        """Resolve through the catalog only after local receipt admission."""
        catalog = self._dataset_catalog
        if catalog is None:
            return [], []
        state, reason, profile_coverage = self._catalog_publish_admission(catalog, run_profile)
        if state != "current" and warnings is not None:
            warnings.append(f"catalog_source_{state}:{reason}")

        def admit(row: dict[str, object]) -> tuple[bool, str]:
            if state != "current":
                return False, reason
            return self._catalog_profile_plan_admission(
                _optional_text(row.get("profile_id")), profile_coverage
            )

        return self._resolve_via_catalog_rows(
            unresolved,
            run_profile=run_profile,
            warnings=warnings,
            source_currentness=state,
            source_reason=reason,
            plan_admission=admit,
        )

    def _resolve_via_catalog_rows(
        self,
        unresolved: list[DataNeed],
        *,
        run_profile: CatalogRunProfile | None = None,
        warnings: list[str] | None = None,
        source_currentness: str = "not_established",
        source_reason: str = "logic_only_mapper",
        plan_admission: Callable[[dict[str, object]], tuple[bool, str]],
    ) -> tuple[list[FetchPlan], list[MetricCandidate]]:
        """Map catalog rows; the caller supplies its plan-admission predicate."""
        plans: list[FetchPlan] = []
        candidates: list[MetricCandidate] = []
        catalog = self._dataset_catalog
        if catalog is None:
            return plans, candidates

        for need in unresolved:
            resolved_rows: list[dict[str, object]] = []

            binding_fn = getattr(catalog, "resolve_metric_bindings", None)
            if binding_fn is not None:
                try:
                    bindings = binding_fn(need.metric, top_k=3)
                except Exception as exc:
                    if isinstance(exc, catalog_read_api.CatalogReadSourceError):
                        raise
                    logger.debug(
                        "Catalog binding lookup failed for metric %s",
                        need.metric,
                        exc_info=True,
                    )
                    bindings = []
                for binding in bindings:
                    execution_tier = str(getattr(binding, "execution_tier", "catalog") or "catalog")
                    if execution_tier not in _EXECUTABLE_CATALOG_TIERS:
                        continue
                    connector_id = str(getattr(binding, "connector_id", "") or "").strip()
                    request_dataset_id = str(
                        getattr(binding, "request_dataset_id", "") or ""
                    ).strip()
                    if not connector_id or not request_dataset_id:
                        continue
                    source_name = str(getattr(binding, "source", "") or "")
                    if not self._catalog_source_is_enabled(
                        source_name,
                        connector_id=connector_id,
                        run_profile=run_profile,
                    ):
                        continue
                    resolved_rows.append(
                        {
                            "catalog_dataset_id": str(
                                getattr(binding, "catalog_dataset_id", "") or ""
                            ),
                            "distribution_id": str(getattr(binding, "distribution_id", "") or ""),
                            "connector_id": connector_id,
                            "profile_id": _optional_text(getattr(binding, "profile_id", None)),
                            "request_dataset_id": request_dataset_id,
                            "default_filters": _coerce_filter_map(
                                getattr(binding, "default_filters", {}) or {}
                            ),
                            "confidence": _coerce_float(getattr(binding, "confidence", 0.0) or 0.0),
                            "catalog_title": str(getattr(binding, "title", "") or ""),
                            "execution_tier": execution_tier,
                            "source": source_name,
                        }
                    )

            if not resolved_rows:
                find_fn = getattr(catalog, "find_by_polisyos_metric", None)
                resolve_target_fn = getattr(catalog, "resolve_fetch_target", None)
                if find_fn is None or resolve_target_fn is None:
                    continue
                try:
                    results = find_fn(need.metric, top_k=3)
                except Exception as exc:
                    if isinstance(exc, catalog_read_api.CatalogReadSourceError):
                        raise
                    logger.debug(
                        "Catalog lookup failed for metric %s",
                        need.metric,
                        exc_info=True,
                    )
                    continue
                for result in results:
                    execution_tier = str(getattr(result, "execution_tier", "catalog") or "catalog")
                    if execution_tier not in _EXECUTABLE_CATALOG_TIERS:
                        continue
                    try:
                        target = resolve_target_fn(result.id)
                    except Exception as exc:
                        if isinstance(exc, catalog_read_api.CatalogReadSourceError):
                            raise
                        logger.debug(
                            "Catalog fetch target resolution failed for %s",
                            result.id,
                            exc_info=True,
                        )
                        continue
                    if (
                        target is None
                        or not target.connector_id
                        or not target.request_dataset_id
                        or not target.parser_supported
                    ):
                        continue
                    source_name = str(getattr(result, "source", "") or "")
                    if not self._catalog_source_is_enabled(
                        source_name,
                        connector_id=target.connector_id,
                        run_profile=run_profile,
                    ):
                        continue
                    resolved_rows.append(
                        {
                            "catalog_dataset_id": target.catalog_dataset_id,
                            "distribution_id": target.distribution_id,
                            "connector_id": target.connector_id,
                            "profile_id": _optional_text(target.profile_id),
                            "request_dataset_id": target.request_dataset_id,
                            "default_filters": _coerce_filter_map(target.default_filters),
                            "confidence": max(0.05, _coerce_float(result.similarity) * 0.8),
                            "catalog_title": result.title,
                            "execution_tier": execution_tier,
                            "source": source_name,
                        }
                    )

            if not resolved_rows:
                continue

            deduped_rows: list[dict[str, object]] = []
            seen: set[tuple[str, str]] = set()
            for row in resolved_rows:
                dedupe_key = (str(row["connector_id"]), str(row["request_dataset_id"]))
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                deduped_rows.append(row)

            selectable_rows: list[dict[str, object]] = []
            for row in deduped_rows:
                plan_allowed, plan_reason = plan_admission(row)
                row["_plan_admitted"] = plan_allowed
                row["_plan_admission_reason"] = plan_reason
                if not plan_allowed and warnings is not None and source_currentness == "current":
                    warnings.append(
                        f"catalog_profile_not_admitted:{row.get('profile_id') or 'unknown'!s}:"
                        f"{plan_reason}"
                    )
                if not self._has_explicit_scope(need):
                    selectable_rows.append(row)
                    continue
                row_catalog_dataset_id = str(row["catalog_dataset_id"] or "").strip()
                exact_catalog_dataset_id = self._catalog_dataset_id_for_target(
                    metric_id=need.metric,
                    connector_id=str(row["connector_id"]),
                    request_dataset_id=str(row["request_dataset_id"]),
                    profile_id=_optional_text(row["profile_id"]),
                    run_profile=run_profile,
                    source_name=str(row.get("source") or "").strip(),
                )
                if (
                    exact_catalog_dataset_id is None
                    or exact_catalog_dataset_id != row_catalog_dataset_id
                ):
                    status, reason = "unknown", "catalog_identity_unresolved"
                else:
                    status, reason = self._catalog_scope_status(
                        need,
                        exact_catalog_dataset_id,
                    )
                if status == "incompatible":
                    if warnings is not None:
                        warnings.append(
                            f"catalog_scope_incompatible:{need.metric}:"
                            f"{exact_catalog_dataset_id or 'unknown'}"
                        )
                elif status == "unknown":
                    if warnings is not None:
                        warnings.append(f"catalog_scope_unverified:{need.metric}:{reason}")
                    selectable_rows.append(row)
                else:
                    selectable_rows.append(row)

            selectable_target_keys = {
                (str(row["connector_id"]), str(row["request_dataset_id"]))
                for row in selectable_rows
            }
            for rank, row in enumerate(deduped_rows, start=1):
                target_key = (str(row["connector_id"]), str(row["request_dataset_id"]))
                if target_key not in selectable_target_keys:
                    continue
                candidate = MetricCandidate(
                    candidate_id=_stable_id(
                        "cat",
                        need.metric,
                        str(row["connector_id"]),
                        str(row["request_dataset_id"]),
                    ),
                    metric_id=need.metric,
                    connector_id=str(row["connector_id"]),
                    dataset_id=str(row["request_dataset_id"]),
                    profile_id=_optional_text(row["profile_id"]),
                    source_lane="catalog",
                    confidence=max(0.05, min(1.0, _coerce_float(row["confidence"]))),
                    rank=rank,
                    trust_score=0.7,
                    freshness_score=0.6,
                    coverage_estimate=0.75,
                    latency_estimate_ms=1500,
                    filters_template=_coerce_filter_map(row["default_filters"]),
                    match_reason="dataset_catalog_metric_binding",
                    metadata={
                        "catalog_dataset_id": row["catalog_dataset_id"],
                        "distribution_id": row["distribution_id"],
                        "catalog_title": row["catalog_title"],
                        "execution_tier": row["execution_tier"],
                        "resolution_route": "catalog",
                        "source_currentness": source_currentness,
                        "source_currentness_reason": source_reason,
                        "plan_admission_reason": row.get("_plan_admission_reason", ""),
                    },
                )
                candidates.append(candidate)

            plan_rows = [row for row in selectable_rows if row.get("_plan_admitted") is True]
            if not plan_rows:
                continue
            fallbacks = [
                FetchPlanFallback(
                    connector_id=str(row["connector_id"]),
                    dataset_id=str(row["request_dataset_id"]),
                    metric_id=need.metric,
                    profile_id=_optional_text(row["profile_id"]),
                    filters=_coerce_filter_map(row["default_filters"]),
                    metadata={
                        "resolution_route": "catalog",
                        "catalog_dataset_id": row["catalog_dataset_id"],
                        "distribution_id": row["distribution_id"],
                    },
                )
                for row in plan_rows[1:3]
            ]
            primary = plan_rows[0]
            date_start, date_end, policy = self._catalog_date_window(
                source_name=str(primary.get("source") or ""),
                need=need,
            )
            plans.append(
                FetchPlan(
                    plan_id=_stable_id(
                        "plan",
                        need.metric,
                        str(primary["connector_id"]),
                        str(primary["request_dataset_id"]),
                    ),
                    metric_id=need.metric,
                    connector_id=str(primary["connector_id"]),
                    dataset_id=str(primary["request_dataset_id"]),
                    profile_id=_optional_text(primary["profile_id"]),
                    filters=_coerce_filter_map(primary["default_filters"]),
                    date_start=date_start,
                    date_end=date_end,
                    granularity=need.granularity,
                    quality_min=need.quality_min,
                    source_lane="catalog",
                    fallbacks=fallbacks[:2],
                    metadata={
                        "catalog_discovered": True,
                        "catalog_dataset_id": primary["catalog_dataset_id"],
                        "distribution_id": primary["distribution_id"],
                        "catalog_title": primary["catalog_title"],
                        "execution_tier": primary["execution_tier"],
                        "source": primary.get("source", ""),
                        "history_policy": policy.history_policy if policy else "",
                        "default_lookback_days": policy.default_lookback_days if policy else None,
                        "manual_backfill_allowed": bool(policy.allow_manual_backfill)
                        if policy
                        else False,
                        "resolution_route": "catalog",
                    },
                )
            )
        return plans, candidates

    @staticmethod
    def _lane_used(plans: list[FetchPlan]) -> str:
        if not plans:
            return "none"
        lanes = {plan.source_lane for plan in plans}
        if len(lanes) == 1:
            return str(next(iter(lanes)))
        return "hybrid"

    @staticmethod
    def _route_breakdown(items: Sequence[object]) -> dict[str, int]:
        breakdown: dict[str, int] = {}
        for item in items:
            metadata = getattr(item, "metadata", None)
            route = None
            if isinstance(metadata, dict):
                route = metadata.get("resolution_route")
            if not route:
                route = getattr(item, "source_lane", None) or "unknown"
            route_name = str(route)
            breakdown[route_name] = breakdown.get(route_name, 0) + 1
        return dict(sorted(breakdown.items()))
