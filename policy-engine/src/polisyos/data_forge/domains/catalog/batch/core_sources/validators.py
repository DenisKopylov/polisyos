"""Stage 0b: ingest transportability sources into registry/alignment/observation tables."""

from __future__ import annotations

import asyncio
import contextlib
import csv
import gzip
import hashlib
import io
import json
import math
import os
import re
import time
import zipfile
from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import aiohttp
import duckdb
import pandas as pd

from polisyos.common.async_tools import run_coro_sync
from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CatalogTransportDataset,
    CoreSourcesIngestStats,
    ObservationFetchKey,
    ObservationFetchPayload,
    ObservationInsertStats,
    ObservationPlan,
    ObservationShard,
    ObservationShardResult,
    ObservationWriteItem,
    SupportSketch,
    WriterFlushState,
    _ObservationRuntimeMetrics,
    _SourceBudgetWindow,
)
from polisyos.data_forge.domains.catalog.batch.checkpoints import load_json, write_json
from polisyos.data_forge.domains.catalog.knowledge.country_codes import (
    country_scope_members,
    iso2_to_iso3,
    iso2_to_numeric,
    normalize_country_code,
)
from polisyos.data_forge.domains.catalog.knowledge.proxy_penalties import metric_proxy_alignments
from polisyos.data_forge.domains.catalog.knowledge.variable_alignment import (
    AlignmentMethod,
    VariableAlignment,
    align_semantic,
    calibrate_alignment_confidence,
    load_seed_alignments,
)
from polisyos.data_forge.kernel.pipeline.manifests import write_raw_manifest, write_stage_manifest
from polisyos.data_forge.read_api.academic import CANONICAL_VARIABLES
from polisyos.fabric.connectors.base import (
    AsyncFetchLease,
    ConnectionConfig,
    DatasetCapabilitySnapshot,
    FetchRequest,
)
from polisyos.fabric.connectors.profiles.models import SourceExecutionPolicy
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
from polisyos.fabric.connectors.profiles.resolver import (
    resolve_connection_config,
    resolve_execution_policy,
)
from polisyos.fabric.connectors.sources.eurostat import EurostatConnector
from polisyos.fabric.connectors.sources.sdmx_source import SDMXSourceConnector
from polisyos.fabric.connectors.sources.unesco_uis import UNESCOUISConnector
from polisyos.fabric.connectors.sources.unpd import UNPDConnector
from polisyos.fabric.connectors.sources.who import WHOConnector
from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector

if TYPE_CHECKING:
    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig

logger = get_logger(__name__)

_TRANSPORT_SOURCES = frozenset(
    {
        "worldbank",
        "eurostat",
        "oecd",
        "ilo",
        "who",
        "unpd",
        "wvs",
        "unesco_uis",
    }
)
_LEGACY_WGI_INDICATORS: dict[str, str] = {
    "RL.EST": "institutional_quality",
    "CC.EST": "corruption_level",
    "GE.EST": "state_capacity",
}
_LEGACY_WDI_INDICATORS: dict[str, str] = {
    "NY.GDP.PCAP.PP.CD": "gdp_per_capita",
}
_LEGACY_WVS_INDICATORS_STATIC: dict[str, str] = {
    "A165": "social_trust",
    "A173": "cultural_cluster",
}
_CANONICAL_ROOTS = tuple(sorted(CANONICAL_VARIABLES.keys()))
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_WVS_SPECIAL_AGGREGATIONS_STATIC: dict[str, str] = {"A165": "weighted_share_response_1"}
_WVS_WEIGHT_FIELDS: tuple[str, ...] = ("S017", "S018")
_OBSERVATION_INSERT_BATCH_SIZE = 500
_DEFAULT_OBSERVATION_YEAR_WINDOW: tuple[int, int] = (2018, 2022)
_EUROSTAT_SUBANNUAL_TITLE_TOKENS: tuple[str, ...] = (
    "month",
    "monthly",
    "quarter",
    "quarterly",
    "mensuel",
    "mensuelle",
    "monat",
    "monatlich",
    "quartal",
    "viertelj",
    "trimestr",
)
_DEFAULT_SOURCE_CONCURRENCY: dict[str, int] = {
    "eurostat": 3,
    "worldbank": 4,
    "who": 2,
    "unesco_uis": 2,
    "unpd": 1,
    "oecd": 1,
    "ilo": 1,
    "wvs": 1,
}
_SOURCE_LANE_DEFAULTS: dict[str, int] = {
    "eurostat": 1,
    "oecd": 1,
    "worldbank": 2,
    "who": 1,
    "unesco_uis": 1,
    "ilo": 1,
    "unpd": 1,
    "wvs": 1,
}
_SERIAL_HARVEST_FAMILIES: frozenset[str] = frozenset({"ckan"})
_SERIAL_HARVEST_SOURCES: frozenset[str] = frozenset(
    {
        "data_gov_ua_broad",
        "data_gov_ro_broad",
        "data_gov_md_broad",
        "data_gov_pl_broad",
    }
)
_OBSERVATION_PROGRESS_INTERVAL_SECONDS = 60.0
_FETCH_RESULT_CACHE_SIZE = 256
_OBSERVATION_UNSUPPORTED_EMPTY_THRESHOLD = 2
_OBSERVATION_WRITER_FLUSH_ROWS = 8_000
_OBSERVATION_WRITER_FLUSH_BYTES = 8 * 1024 * 1024
_OBSERVATION_WRITER_FLUSH_SECONDS = 5.0
_OBSERVATION_WRITER_IDLE_FLUSH_SECONDS = 0.25
_OBSERVATION_WRITER_CHECKPOINT_EVERY = 10
_OBSERVATION_WRITER_TRANSACTION_ROWS = 2_000
_OBSERVATION_WRITER_TRANSACTION_ITEMS = 8
_OBSERVATION_WRITER_MIN_MEMORY_LIMIT_BYTES = 4 * 1024 * 1024 * 1024
_OBSERVATION_WRITER_MAX_MEMORY_LIMIT_BYTES = 24 * 1024 * 1024 * 1024
_OBSERVATION_WRITER_MEMORY_LIMIT_FRACTION = 0.60
_CAPABILITY_NEGATIVE_STATUS_CODES = frozenset({404, 405})
_RATE_LIMITED_LOG_COUNTS: dict[str, int] = {}
_BULK_MATERIALIZATION_LOCKS: dict[str, asyncio.Lock] = {}
_ILO_INFERRED_DIMENSION_TOKENS: frozenset[str] = frozenset(
    {
        "AGE",
        "CAT",
        "CBR",
        "CCT",
        "CHL",
        "CUR",
        "DSB",
        "DUR",
        "EC2",
        "ECO",
        "EDU",
        "EST",
        "GEO",
        "HHT",
        "HOW",
        "IND",
        "INS",
        "JOB",
        "MJH",
        "MTS",
        "OC2",
        "OCU",
        "SEX",
        "STU",
    }
)




def _migrate_legacy_support_cache(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    unsupported: dict[str, Any] = {}
    empty: dict[str, Any] = {}
    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        if bool(value.get("unsupported")):
            unsupported[key] = dict(value)
            continue
        if int(value.get("empty_hits", 0) or 0) > 0:
            empty[key] = {
                "updated_at": value.get("updated_at", ""),
                "expires_at": value.get("expires_at", ""),
            }
    return unsupported, empty


def _migrate_deferred_unsupported_results(
    completed: dict[str, Any],
    deferred: dict[str, Any],
) -> int:
    migrated = 0
    for shard_id, payload in list(deferred.items()):
        if not isinstance(payload, dict):
            continue
        error_text = str(payload.get("error") or payload.get("last_error") or "").strip()
        if not error_text or not _is_explicit_unsupported_error(RuntimeError(error_text)):
            continue
        completed[shard_id] = {
            **payload,
            "status": "complete_empty",
            "row_count": int(payload.get("row_count", 0) or 0),
            "error": error_text,
        }
        deferred.pop(shard_id, None)
        migrated += 1
    return migrated


def _migrate_dimensionless_ilo_capability_snapshots(
    capability_snapshots: dict[str, Any],
) -> int:
    migrated = 0
    for cache_key, payload in list(capability_snapshots.items()):
        if not isinstance(payload, dict):
            continue
        source = str(payload.get("source") or "").strip().lower()
        if source != "ilo":
            continue
        if tuple(
            str(value).strip()
            for value in list(payload.get("dimension_order") or [])
            if str(value).strip()
        ):
            continue
        capability_snapshots.pop(cache_key, None)
        migrated += 1
    return migrated


def _reactivate_retryable_deferred_results(
    work_packages: dict[str, Any],
    deferred: dict[str, Any],
    async_fetch_leases: dict[str, Any],
) -> int:
    migrated = 0
    for shard_id, payload in list(deferred.items()):
        if not isinstance(payload, dict):
            continue
        work_package = work_packages.get(shard_id)
        if not isinstance(work_package, dict):
            continue
        plan = work_package.get("plan")
        if not isinstance(plan, dict):
            plan = {}
        source = str(payload.get("source") or plan.get("source") or "").strip().lower()
        error_text = str(payload.get("error") or payload.get("last_error") or "").strip()
        if not error_text:
            continue
        status_code = _planner_error_status_code(RuntimeError(error_text))
        if source == "ilo" and status_code == 422:
            deferred.pop(shard_id, None)
            async_fetch_leases.pop(shard_id, None)
            migrated += 1
            continue
        if (
            source == "eurostat"
            and status_code == 405
            and str(work_package.get("acquisition_method") or "").strip().lower() == "api_async"
        ):
            work_package["acquisition_method"] = "bulk_file"
            deferred.pop(shard_id, None)
            async_fetch_leases.pop(shard_id, None)
            migrated += 1
    return migrated


def _load_observation_checkpoint_state(config: DatasetBatchConfig) -> dict[str, Any]:
    payload = load_json(config.observation_ingest_checkpoint_path, default={})
    if not isinstance(payload, dict):
        payload = {}
    completed = payload.get("completed", {})
    failed = payload.get("failed", {})
    deferred = payload.get("deferred", {})
    legacy_support_cache = payload.get("support_cache", {})
    unsupported_signatures = payload.get("unsupported_signatures", {})
    empty_signatures = payload.get("empty_signatures", {})
    if not isinstance(unsupported_signatures, dict):
        unsupported_signatures = {}
    if not isinstance(empty_signatures, dict):
        empty_signatures = {}
    if (not unsupported_signatures and not empty_signatures) and isinstance(
        legacy_support_cache, dict
    ):
        migrated_unsupported, migrated_empty = _migrate_legacy_support_cache(legacy_support_cache)
        unsupported_signatures = migrated_unsupported
        empty_signatures = migrated_empty
    inflight_leases = payload.get("inflight_leases", {})
    async_fetch_leases = payload.get("async_fetch_leases", {})
    capability_snapshots = payload.get("capability_snapshots", {})
    capability_failures = payload.get("capability_failures", {})
    source_budgets = payload.get("source_budgets", {})
    writer_state = payload.get("writer_state", {})
    support_sketches = payload.get("support_sketches", {})
    work_packages = payload.get("work_packages", {})
    planner_phase = payload.get("planner_phase", "support_sketch")
    publishable_core_complete = payload.get("publishable_core_complete", False)
    negative_cache_version = payload.get("negative_cache_version", 1)
    planner_signature = payload.get("planner_signature", "")
    completed = completed if isinstance(completed, dict) else {}
    failed = failed if isinstance(failed, dict) else {}
    deferred = deferred if isinstance(deferred, dict) else {}
    async_fetch_leases = async_fetch_leases if isinstance(async_fetch_leases, dict) else {}
    capability_snapshots = capability_snapshots if isinstance(capability_snapshots, dict) else {}
    work_packages = work_packages if isinstance(work_packages, dict) else {}
    migrated_deferred = _migrate_deferred_unsupported_results(completed, deferred)
    migrated_retryable = _reactivate_retryable_deferred_results(
        work_packages,
        deferred,
        async_fetch_leases,
    )
    migrated_capability_snapshots = _migrate_dimensionless_ilo_capability_snapshots(
        capability_snapshots
    )
    if migrated_deferred > 0 or migrated_retryable > 0 or migrated_capability_snapshots > 0:
        _write_observation_checkpoint_state(
            config,
            completed=completed,
            failed=failed,
            deferred=deferred,
            unsupported_signatures=unsupported_signatures,
            empty_signatures=empty_signatures,
            inflight_leases=inflight_leases if isinstance(inflight_leases, dict) else {},
            async_fetch_leases=async_fetch_leases,
            capability_snapshots=capability_snapshots,
            capability_failures=capability_failures
            if isinstance(capability_failures, dict)
            else {},
            source_budgets=source_budgets if isinstance(source_budgets, dict) else {},
            writer_state=writer_state if isinstance(writer_state, dict) else {},
            support_sketches=support_sketches if isinstance(support_sketches, dict) else {},
            work_packages=work_packages,
            planner_phase=str(planner_phase or "support_sketch"),
            publishable_core_complete=bool(publishable_core_complete),
            negative_cache_version=max(1, int(negative_cache_version or 1)),
            planner_signature=str(planner_signature or ""),
        )
    return {
        "completed": completed,
        "failed": failed,
        "deferred": deferred,
        "unsupported_signatures": unsupported_signatures,
        "empty_signatures": empty_signatures,
        "inflight_leases": inflight_leases if isinstance(inflight_leases, dict) else {},
        "async_fetch_leases": async_fetch_leases,
        "capability_snapshots": capability_snapshots,
        "capability_failures": capability_failures if isinstance(capability_failures, dict) else {},
        "source_budgets": source_budgets if isinstance(source_budgets, dict) else {},
        "writer_state": writer_state if isinstance(writer_state, dict) else {},
        "support_sketches": support_sketches if isinstance(support_sketches, dict) else {},
        "work_packages": work_packages,
        "planner_phase": str(planner_phase or "support_sketch"),
        "publishable_core_complete": bool(publishable_core_complete),
        "negative_cache_version": max(1, int(negative_cache_version or 1)),
        "planner_signature": str(planner_signature or ""),
    }


def _write_observation_checkpoint_state(
    config: DatasetBatchConfig,
    *,
    completed: dict[str, Any],
    failed: dict[str, Any],
    deferred: dict[str, Any],
    unsupported_signatures: dict[str, Any],
    empty_signatures: dict[str, Any],
    inflight_leases: dict[str, Any],
    async_fetch_leases: dict[str, Any],
    capability_snapshots: dict[str, Any],
    capability_failures: dict[str, Any],
    source_budgets: dict[str, Any],
    writer_state: dict[str, Any],
    support_sketches: dict[str, Any] | None = None,
    work_packages: dict[str, Any] | None = None,
    planner_phase: str = "support_sketch",
    publishable_core_complete: bool = False,
    negative_cache_version: int = 2,
    planner_signature: str = "",
) -> None:
    write_json(
        config.observation_ingest_checkpoint_path,
        {
            "completed": completed,
            "failed": failed,
            "deferred": deferred,
            "unsupported_signatures": unsupported_signatures,
            "empty_signatures": empty_signatures,
            "support_cache": unsupported_signatures,
            "inflight_leases": inflight_leases,
            "async_fetch_leases": async_fetch_leases,
            "capability_snapshots": capability_snapshots,
            "capability_failures": capability_failures,
            "source_budgets": source_budgets,
            "writer_state": writer_state,
            "support_sketches": support_sketches or {},
            "work_packages": work_packages or {},
            "planner_phase": planner_phase,
            "publishable_core_complete": bool(publishable_core_complete),
            "negative_cache_version": max(1, int(negative_cache_version)),
            "planner_signature": planner_signature,
        },
    )


def _support_cache_key(
    shard: ObservationShard,
    *,
    capability: DatasetCapabilitySnapshot | None = None,
) -> str:
    filters_json = json.dumps(
        shard.filters, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    country_codes = tuple(
        code
        for code in (shard.country_codes or ((shard.country_code,) if shard.country_code else ()))
        if str(code).strip()
    )
    countries_json = json.dumps(country_codes, ensure_ascii=False, separators=(",", ":"))
    dataset_version = (
        str(capability.version_hint or "").strip()
        if capability is not None and getattr(capability, "version_hint", None)
        else str(shard.dataset_version or shard.plan.dataset_version or "")
    )
    transport = str(
        shard.acquisition_method
        or (
            capability.preferred_transport
            if capability is not None and getattr(capability, "preferred_transport", None)
            else ""
        )
    ).strip()
    return "|".join(
        [
            str(shard.plan.source or ""),
            str(
                capability.resolved_dataset_id
                if capability is not None and capability.resolved_dataset_id
                else shard.plan.request_dataset_id or ""
            ),
            dataset_version,
            transport,
            str(shard.country_code or ""),
            countries_json,
            filters_json,
            str(capability.constraint_hash if capability is not None else ""),
        ]
    )


def _support_cache_entry_active(entry: dict[str, Any], *, now: datetime) -> bool:
    expires_at = str(entry.get("expires_at") or "").strip()
    if not expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(expires_at)
    except ValueError:
        return True
    return expiry >= now


def _support_cache_proves_unsupported(entry: dict[str, Any], *, now: datetime) -> bool:
    if not _support_cache_entry_active(entry, now=now):
        return False
    return bool(entry.get("unsupported"))


def _empty_signature_cache_hit(entry: dict[str, Any], *, now: datetime) -> bool:
    if not entry:
        return False
    if "updated_at" not in entry and "expires_at" not in entry:
        return False
    return _support_cache_entry_active(entry, now=now)


def _update_unsupported_signature_cache(
    support_cache: dict[str, Any],
    *,
    key: str,
    policy: SourceExecutionPolicy,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    ttl = timedelta(hours=max(1, _policy_int_attr(policy, "negative_cache_ttl_hours", 24)))
    payload = {
        "unsupported": True,
        "updated_at": now.isoformat(),
        "expires_at": (now + ttl).isoformat(),
    }
    support_cache[key] = payload
    return payload


def _update_empty_signature_cache(
    empty_signatures: dict[str, Any],
    *,
    key: str,
    policy: SourceExecutionPolicy,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    ttl = timedelta(hours=max(1, _policy_int_attr(policy, "soft_negative_cache_ttl_hours", 24)))
    payload = {
        "updated_at": now.isoformat(),
        "expires_at": (now + ttl).isoformat(),
    }
    empty_signatures[key] = payload
    return payload


def _update_support_cache(
    unsupported_signatures: dict[str, Any],
    empty_signatures: dict[str, Any],
    *,
    key: str,
    policy: SourceExecutionPolicy,
    unsupported: bool = False,
    empty_result: bool = False,
    promote_empty_to_unsupported: bool = False,
) -> dict[str, Any] | None:
    if unsupported:
        empty_signatures.pop(key, None)
        return _update_unsupported_signature_cache(
            unsupported_signatures,
            key=key,
            policy=policy,
        )
    if empty_result:
        if promote_empty_to_unsupported:
            return _update_unsupported_signature_cache(
                unsupported_signatures,
                key=key,
                policy=policy,
            )
        unsupported_signatures.pop(key, None)
        return _update_empty_signature_cache(
            empty_signatures,
            key=key,
            policy=policy,
        )
    return None


def _prune_expired_support_cache(support_cache: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        key: value
        for key, value in support_cache.items()
        if isinstance(value, dict) and _support_cache_entry_active(value, now=now)
    }


def _source_completion_pct_by_phase(
    work_packages: dict[str, ObservationShard],
    *,
    completed: dict[str, Any],
    selected_phases: set[str],
) -> tuple[dict[str, float], dict[str, float]]:
    completed_ids = {str(shard_id) for shard_id in completed if str(shard_id).strip()}
    core_totals: dict[str, int] = {}
    core_done: dict[str, int] = {}
    full_totals: dict[str, int] = {}
    full_done: dict[str, int] = {}
    for shard_id, shard in work_packages.items():
        if shard.phase not in selected_phases:
            continue
        source = str(shard.plan.source or "")
        full_totals[source] = full_totals.get(source, 0) + 1
        if shard.phase == "publishable_core":
            core_totals[source] = core_totals.get(source, 0) + 1
        if shard_id in completed_ids:
            full_done[source] = full_done.get(source, 0) + 1
            if shard.phase == "publishable_core":
                core_done[source] = core_done.get(source, 0) + 1

    sources = sorted(set(full_totals) | set(core_totals))
    core_pct = {
        source: round(
            100.0 * float(core_done.get(source, 0)) / max(float(core_totals.get(source, 0)), 1.0),
            2,
        )
        for source in sources
    }
    full_pct = {
        source: round(
            100.0 * float(full_done.get(source, 0)) / max(float(full_totals.get(source, 0)), 1.0),
            2,
        )
        for source in sources
    }
    return core_pct, full_pct


def _capability_dimension_values(
    snapshot: DatasetCapabilitySnapshot | None,
    *names: str,
) -> tuple[str, ...]:
    if snapshot is None:
        return ()
    allowed = snapshot.allowed_positions or {}
    for name in names:
        values = allowed.get(name)
        if values:
            return tuple(str(value) for value in values if str(value).strip())
    lowered = {str(key).lower(): value for key, value in allowed.items()}
    for name in names:
        values = lowered.get(name.lower())
        if values:
            return tuple(str(value) for value in values if str(value).strip())
    return ()


def _shard_supported_by_capability(
    shard: ObservationShard,
    *,
    snapshot: DatasetCapabilitySnapshot | None,
) -> bool:
    if snapshot is None:
        return True
    allowed_geo = _capability_dimension_values(snapshot, "geo", "country", "ref_area")
    if allowed_geo:
        requested_countries = shard.country_codes or (
            (shard.country_code,) if shard.country_code else ()
        )
        for country_code in requested_countries:
            iso2 = str(country_code or "").strip().upper()
            iso3 = _to_iso3(iso2)
            numeric = iso2_to_numeric(iso2) or ""
            allowed = {str(value).strip().upper() for value in allowed_geo if str(value).strip()}
            if iso2 not in allowed and iso3 not in allowed and numeric not in allowed:
                return False
    return not (
        shard.country_code
        and not shard.country_codes
        and allowed_geo
        and shard.country_code not in allowed_geo
    )


def _split_shard_by_filter_values(
    shard: ObservationShard,
    *,
    split_key: str,
    values: list[str],
) -> list[ObservationShard]:
    if len(values) <= 1:
        return []
    midpoint = max(len(values) // 2, 1)
    left_filters = {key: list(current) for key, current in shard.filters.items()}
    right_filters = {key: list(current) for key, current in shard.filters.items()}
    left_filters[split_key] = values[:midpoint]
    right_filters[split_key] = values[midpoint:]
    return [
        ObservationShard(
            shard_id=_observation_shard_id(
                plan=shard.plan,
                country_code=shard.country_code,
                country_codes=shard.country_codes,
                start_year=shard.start_year,
                end_year=shard.end_year,
                filters=current_filters,
                split_depth=shard.split_depth + 1,
            ),
            plan=shard.plan,
            country_code=shard.country_code,
            country_codes=shard.country_codes,
            start_year=shard.start_year,
            end_year=shard.end_year,
            filters=current_filters,
            split_depth=shard.split_depth + 1,
            phase=shard.phase,
            acquisition_method=shard.acquisition_method,
            source_watermark=shard.source_watermark,
            dataset_version=shard.dataset_version,
            dimension_order=shard.dimension_order,
        )
        for current_filters in (left_filters, right_filters)
        if current_filters.get(split_key)
    ]


def _split_shard_by_country_group(shard: ObservationShard) -> list[ObservationShard]:
    countries = list(shard.country_codes)
    if len(countries) <= 1:
        return []
    midpoint = max(len(countries) // 2, 1)
    groups = [tuple(countries[:midpoint]), tuple(countries[midpoint:])]
    out: list[ObservationShard] = []
    for group in groups:
        if not group:
            continue
        filters = dict(shard.filters)
        if shard.plan.source == "eurostat":
            filters = _eurostat_filters_for_countries(
                group, base_filters=_strip_geo_filters(filters)
            )
        elif shard.plan.source in {"oecd", "ilo"}:
            filters = _sdmx_filters_for_countries(group, base_filters=_strip_geo_filters(filters))
        country_code = group[0] if len(group) == 1 else None
        out.append(
            ObservationShard(
                shard_id=_observation_shard_id(
                    plan=shard.plan,
                    country_code=country_code,
                    country_codes=group,
                    start_year=shard.start_year,
                    end_year=shard.end_year,
                    filters=filters,
                    split_depth=shard.split_depth + 1,
                ),
                plan=shard.plan,
                country_code=country_code,
                country_codes=group,
                start_year=shard.start_year,
                end_year=shard.end_year,
                filters=filters,
                split_depth=shard.split_depth + 1,
                phase=shard.phase,
                acquisition_method=shard.acquisition_method,
                source_watermark=shard.source_watermark,
                dataset_version=shard.dataset_version,
                dimension_order=shard.dimension_order,
            )
        )
    return out


def _time_dimension_cardinality(shard: ObservationShard) -> int:
    span_years = max(int(shard.end_year) - int(shard.start_year) + 1, 1)
    frequency_rank = _observation_frequency_rank(shard.plan.update_frequency)
    if frequency_rank >= 2:
        return span_years * 12
    if frequency_rank >= 1:
        return span_years * 4
    return span_years


def _estimate_shard_cardinality(
    shard: ObservationShard,
    *,
    snapshot: DatasetCapabilitySnapshot | None,
) -> int:
    if snapshot is None:
        return 0
    filter_map = {
        str(key): [str(value) for value in values if str(value).strip()]
        for key, values in shard.filters.items()
    }
    dimensions = tuple(snapshot.dimension_order or tuple(filter_map.keys()))
    estimate = 1
    has_signal = False
    for dimension in dimensions:
        normalized = str(dimension).strip()
        lowered = normalized.lower()
        count = 0
        if lowered in {"geo", "country", "ref_area"}:
            if shard.country_codes:
                count = len(shard.country_codes)
            elif shard.country_code:
                count = 1
            else:
                allowed = _capability_dimension_values(
                    snapshot, normalized, "geo", "country", "ref_area"
                )
                count = len(allowed)
        elif lowered in {"time", "time_period"}:
            filter_values = filter_map.get(normalized) or filter_map.get(lowered) or []
            count = len(filter_values) if filter_values else _time_dimension_cardinality(shard)
        else:
            filter_values = (
                filter_map.get(normalized)
                or filter_map.get(lowered)
                or filter_map.get(normalized.upper())
                or []
            )
            if filter_values:
                count = len(filter_values)
            else:
                allowed = _capability_dimension_values(snapshot, normalized)
                count = len(allowed)
        if count <= 0:
            continue
        has_signal = True
        estimate *= count
    if has_signal:
        return estimate
    return int(snapshot.estimated_cardinality or 0)


def _shard_prefers_async_fetch(
    shard: ObservationShard,
    *,
    snapshot: DatasetCapabilitySnapshot | None,
    policy: SourceExecutionPolicy,
    config: DatasetBatchConfig,
) -> bool:
    if shard.plan.source != "eurostat":
        return False
    if not _policy_bool_attr(policy, "supports_async_fetch", False):
        return False
    if config.is_sampled_run or config.preflight_only or config.run_profile == "preflight_core":
        return False
    estimated = _estimate_shard_cardinality(shard, snapshot=snapshot)
    max_sync = _policy_int_attr(policy, "max_sync_cells", 0)
    max_async = _policy_int_attr(policy, "max_async_cells", 0)
    if estimated <= 0 or max_sync <= 0 or max_async <= 0:
        return False
    return max_sync < estimated <= max_async


def _planner_split_shard_from_capability(
    shard: ObservationShard,
    *,
    snapshot: DatasetCapabilitySnapshot | None,
    policy: SourceExecutionPolicy,
) -> list[ObservationShard]:
    max_cells = _policy_int_attr(policy, "max_sync_cells", 0)
    if snapshot is None or max_cells <= 0:
        return [shard]
    estimated = _estimate_shard_cardinality(shard, snapshot=snapshot)
    if estimated <= 0 or estimated <= max_cells:
        return [shard]
    max_async = _policy_int_attr(policy, "max_async_cells", 0)
    if (
        _policy_bool_attr(policy, "supports_async_fetch", False)
        and max_async > 0
        and estimated <= max_async
    ):
        return [shard]
    if shard.start_year < shard.end_year:
        synthetic_413 = RuntimeError(f"payload cardinality split {estimated}>{max_cells}")
        return _split_shard_for_retry(shard, synthetic_413) or [shard]
    if len(shard.country_codes) > 1:
        split = _split_shard_by_country_group(shard)
        if split:
            return split
    preferred_dims = tuple(snapshot.dimension_order or ())
    for key in preferred_dims:
        normalized_key = str(key).strip()
        if not normalized_key or normalized_key.lower() in {
            "geo",
            "country",
            "ref_area",
            "time",
            "time_period",
        }:
            continue
        allowed = _capability_dimension_values(snapshot, normalized_key)
        if len(allowed) > 1:
            split_values = list(shard.filters.get(normalized_key) or allowed)
            split_values = [str(value) for value in split_values if str(value).strip()]
            if len(split_values) > 1:
                split = _split_shard_by_filter_values(
                    shard, split_key=normalized_key, values=split_values
                )
                if split:
                    return split
    return [shard]


def _empty_result_proves_unsupported(
    *,
    shard: ObservationShard,
    snapshot: DatasetCapabilitySnapshot | None,
) -> bool:
    del shard, snapshot
    return False


def _load_source_budget_windows(state: dict[str, Any]) -> dict[str, _SourceBudgetWindow]:
    out: dict[str, _SourceBudgetWindow] = {}
    for source, payload in state.items():
        if not isinstance(payload, dict):
            continue
        started_at = str(payload.get("window_started_at") or "").strip()
        try:
            window_started_at = (
                datetime.fromisoformat(started_at) if started_at else datetime.now(UTC)
            )
        except ValueError:
            window_started_at = datetime.now(UTC)
        out[str(source)] = _SourceBudgetWindow(
            window_started_at=window_started_at,
            requests_used=max(0, int(payload.get("requests_used", 0))),
        )
    return out


def _serialize_source_budget_windows(
    state: dict[str, _SourceBudgetWindow],
) -> dict[str, dict[str, Any]]:
    return {
        source: {
            "window_started_at": bucket.window_started_at.isoformat(),
            "requests_used": int(bucket.requests_used),
        }
        for source, bucket in state.items()
    }


def _serialize_writer_state(state: WriterFlushState) -> dict[str, Any]:
    return {
        "buffered_rows": int(state.buffered_rows),
        "buffered_bytes": int(state.buffered_bytes),
        "flush_count": int(state.flush_count),
        "last_flush_at": float(state.last_flush_at),
        "last_flush_latency_ms": float(state.last_flush_latency_ms),
    }


def _deserialize_writer_state(payload: Any) -> WriterFlushState:
    if not isinstance(payload, dict):
        return WriterFlushState(last_flush_at=time.monotonic())
    return WriterFlushState(
        buffered_rows=max(0, int(payload.get("buffered_rows", 0) or 0)),
        buffered_bytes=max(0, int(payload.get("buffered_bytes", 0) or 0)),
        flush_count=max(0, int(payload.get("flush_count", 0) or 0)),
        last_flush_at=float(payload.get("last_flush_at", 0.0) or 0.0) or time.monotonic(),
        last_flush_latency_ms=max(0.0, float(payload.get("last_flush_latency_ms", 0.0) or 0.0)),
    )


def _capability_failure_entry_active(
    entry: dict[str, Any],
    *,
    now: datetime,
) -> bool:
    expires_at = str(entry.get("expires_at") or "").strip()
    if not expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(expires_at)
    except ValueError:
        return True
    return expiry >= now


def _prune_expired_capability_failures(capability_failures: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        key: value
        for key, value in capability_failures.items()
        if isinstance(value, dict) and _capability_failure_entry_active(value, now=now)
    }


def _serialize_capability_failure(
    *,
    plan: ObservationPlan,
    policy: SourceExecutionPolicy,
    exc: Exception,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    ttl = timedelta(hours=max(1, int(policy.capability_cache_ttl_hours or 24)))
    status_code = _planner_error_status_code(exc)
    return {
        "source": str(plan.source or ""),
        "dataset_id": str(plan.request_dataset_id or ""),
        "status_code": int(status_code) if status_code is not None else None,
        "error": str(exc),
        "updated_at": now.isoformat(),
        "expires_at": (now + ttl).isoformat(),
    }


def _capability_failure_supports_fallback(
    entry: dict[str, Any],
    *,
    now: datetime,
) -> bool:
    if not _capability_failure_entry_active(entry, now=now):
        return False
    status_code = entry.get("status_code")
    try:
        normalized = int(status_code)
    except (TypeError, ValueError):
        normalized = None
    return normalized in _CAPABILITY_NEGATIVE_STATUS_CODES


def _capability_failures_by_source(capability_failures: dict[str, Any]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for value in capability_failures.values():
        if not isinstance(value, dict):
            continue
        source = str(value.get("source") or "").strip()
        if not source:
            continue
        summary[source] = summary.get(source, 0) + 1
    return summary


def _write_core_ingest_stage_progress(
    config: DatasetBatchConfig,
    *,
    metadata: dict[str, Any],
) -> None:
    state = load_json(config.stage_state_path, default={})
    if not isinstance(state, dict):
        state = {}
    current = state.get("core_sources_ingest", {})
    if not isinstance(current, dict):
        current = {}
    state["core_sources_ingest"] = {
        "status": "running",
        "input_fingerprint": str(current.get("input_fingerprint", "")),
        "outputs": [str(config.db_path)],
        "metadata": metadata,
    }
    write_json(config.stage_state_path, state)
def _chunked_observation_requests(
    *,
    plan: ObservationPlan,
    filters: tuple[tuple[str, tuple[str, ...]], ...],
    source: str,
    start_year: int | None = None,
    end_year: int | None = None,
) -> list[FetchRequest]:
    window_start = start_year if start_year is not None else _DEFAULT_OBSERVATION_YEAR_WINDOW[0]
    window_end = end_year if end_year is not None else _DEFAULT_OBSERVATION_YEAR_WINDOW[1]
    window_years = _observation_time_window_years(
        source=source, update_frequency=plan.update_frequency
    )
    requests: list[FetchRequest] = []
    for window_start, window_end in _year_windows(window_start, window_end, window_years):
        requests.append(
            FetchRequest(
                dataset_id=plan.request_dataset_id,
                filters=filters,
                date_start=datetime(window_start, 1, 1, tzinfo=UTC),
                date_end=datetime(window_end, 12, 31, tzinfo=UTC),
                page_size=200,
            )
        )
    return requests


def _observation_time_window_years(*, source: str, update_frequency: str) -> int:
    normalized = str(source or "").strip().lower()
    if normalized != "eurostat":
        start_year, end_year = _DEFAULT_OBSERVATION_YEAR_WINDOW
        return max((end_year - start_year) + 1, 1)
    frequency_rank = _observation_frequency_rank(update_frequency)
    if frequency_rank >= 1:
        return 1
    return 2


def _year_windows(start_year: int, end_year: int, window_years: int) -> list[tuple[int, int]]:
    if end_year < start_year:
        return []
    width = max(int(window_years), 1)
    windows: list[tuple[int, int]] = []
    current = int(start_year)
    while current <= int(end_year):
        upper = min(current + width - 1, int(end_year))
        windows.append((current, upper))
        current = upper + 1
    return windows


def _build_observation_shards(
    plans: list[ObservationPlan],
    *,
    config: DatasetBatchConfig,
) -> list[ObservationShard]:
    source_policies = {
        plan.source: _resolve_source_execution_policy(
            source=plan.source, profile_id=plan.profile_id
        )
        for plan in plans
    }
    sketches = _build_support_sketches(
        plans,
        config=config,
        plan_capabilities={},
        source_policies=source_policies,
    )
    return _build_observation_shards_from_sketches(
        sketches,
        config=config,
        source_policies=source_policies,
    )


def _observation_shard_id(
    *,
    plan: ObservationPlan,
    country_code: str | None,
    country_codes: tuple[str, ...] = (),
    start_year: int,
    end_year: int,
    filters: dict[str, list[str]],
    split_depth: int,
) -> str:
    payload = {
        "dataset_id": plan.dataset_id,
        "source": plan.source,
        "raw_variable": plan.raw_variable,
        "canonical_var": plan.canonical_var,
        "request_dataset_id": plan.request_dataset_id,
        "country_code": country_code,
        "country_codes": list(country_codes),
        "start_year": start_year,
        "end_year": end_year,
        "filters": filters,
        "split_depth": split_depth,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def _split_shard_for_retry(shard: ObservationShard, exc: Exception) -> list[ObservationShard]:
    lowered = str(exc or "").lower()
    if "http 413" not in lowered and "payload" not in lowered:
        return []
    if shard.start_year < shard.end_year:
        mid = (shard.start_year + shard.end_year) // 2
        windows = ((shard.start_year, mid), (mid + 1, shard.end_year))
        return [
            ObservationShard(
                shard_id=_observation_shard_id(
                    plan=shard.plan,
                    country_code=shard.country_code,
                    country_codes=shard.country_codes,
                    start_year=window_start,
                    end_year=window_end,
                    filters=shard.filters,
                    split_depth=shard.split_depth + 1,
                ),
                plan=shard.plan,
                country_code=shard.country_code,
                country_codes=shard.country_codes,
                start_year=window_start,
                end_year=window_end,
                filters=dict(shard.filters),
                split_depth=shard.split_depth + 1,
                phase=shard.phase,
                acquisition_method=shard.acquisition_method,
                source_watermark=shard.source_watermark,
                dataset_version=shard.dataset_version,
                dimension_order=shard.dimension_order,
            )
            for window_start, window_end in windows
            if window_start <= window_end
        ]
    split_key = _largest_filter_key(shard.filters)
    if not split_key:
        return []
    values = list(shard.filters.get(split_key, ()))
    if len(values) <= 1:
        return []
    midpoint = max(len(values) // 2, 1)
    left = dict(shard.filters)
    right = dict(shard.filters)
    left[split_key] = values[:midpoint]
    right[split_key] = values[midpoint:]
    return [
        ObservationShard(
            shard_id=_observation_shard_id(
                plan=shard.plan,
                country_code=shard.country_code,
                country_codes=shard.country_codes,
                start_year=shard.start_year,
                end_year=shard.end_year,
                filters=current_filters,
                split_depth=shard.split_depth + 1,
            ),
            plan=shard.plan,
            country_code=shard.country_code,
            country_codes=shard.country_codes,
            start_year=shard.start_year,
            end_year=shard.end_year,
            filters=current_filters,
            split_depth=shard.split_depth + 1,
            phase=shard.phase,
            acquisition_method=shard.acquisition_method,
            source_watermark=shard.source_watermark,
            dataset_version=shard.dataset_version,
            dimension_order=shard.dimension_order,
        )
        for current_filters in (left, right)
        if current_filters.get(split_key)
    ]


async def _split_shard_for_retry_async(
    shard: ObservationShard,
    exc: Exception,
    *,
    cache: _ConnectorSessionCache,
    config: DatasetBatchConfig,
    policy: SourceExecutionPolicy,
    budget_windows: dict[str, _SourceBudgetWindow],
    state_lock: asyncio.Lock,
    budget_wait_observer: Any | None = None,
) -> list[ObservationShard]:
    status_code = _planner_error_status_code(exc)
    if (
        shard.plan.source == "eurostat"
        and status_code in {405, 413}
        and not (
            config.is_sampled_run or config.preflight_only or config.run_profile == "preflight_core"
        )
    ):
        current_transport = str(shard.acquisition_method or "").strip().lower()
        next_transport = ""
        if (
            status_code == 413
            and current_transport != "api_async"
            and _policy_bool_attr(policy, "supports_async_fetch", False)
        ):
            next_transport = "api_async"
        elif current_transport == "api_async" and _policy_attr(policy, "bulk_download_url", None):
            next_transport = "bulk_file"
        if next_transport:
            return [
                ObservationShard(
                    shard_id=shard.shard_id,
                    plan=shard.plan,
                    country_code=shard.country_code,
                    country_codes=shard.country_codes,
                    start_year=shard.start_year,
                    end_year=shard.end_year,
                    filters=dict(shard.filters),
                    split_depth=shard.split_depth,
                    phase=shard.phase,
                    acquisition_method=next_transport,
                    source_watermark=shard.source_watermark,
                    dataset_version=shard.dataset_version,
                    dimension_order=shard.dimension_order,
                )
            ]
    split_shards = _split_shard_for_retry(shard, exc)
    if split_shards:
        return split_shards
    if _planner_error_status_code(exc) != 413 or not policy.schema_preflight:
        return []
    return await _probe_shard_split_dimensions(
        shard,
        cache=cache,
        config=config,
        policy=policy,
        budget_windows=budget_windows,
        state_lock=state_lock,
        budget_wait_observer=budget_wait_observer,
    )


async def _probe_shard_split_dimensions(
    shard: ObservationShard,
    *,
    cache: _ConnectorSessionCache,
    config: DatasetBatchConfig,
    policy: SourceExecutionPolicy,
    budget_windows: dict[str, _SourceBudgetWindow],
    state_lock: asyncio.Lock,
    budget_wait_observer: Any | None = None,
) -> list[ObservationShard]:
    request = _build_probe_request(shard)
    if request is None:
        return []
    try:
        if shard.plan.source == "eurostat":
            connector, handle = await cache.get_eurostat()
        elif shard.plan.source in {"oecd", "ilo"}:
            profile_id = shard.plan.profile_id or (
                "oecd_sdmx" if shard.plan.source == "oecd" else "ilo_sdmx"
            )
            connector, handle = await cache.get_sdmx(profile_id)
        else:
            return []
        result = await _execute_source_fetch(
            connector,
            handle,
            request,
            source=shard.plan.source,
            policy=policy,
            budget_windows=budget_windows,
            state_lock=state_lock,
            budget_wait_observer=budget_wait_observer,
        )
    except Exception:
        return []
    rows = _records_from_payload(result.data)
    split_key, values = _probe_dimension_split_key(rows, shard=shard)
    if not split_key or len(values) <= 1:
        return []
    midpoint = max(len(values) // 2, 1)
    left_filters = {key: list(current) for key, current in shard.filters.items()}
    right_filters = {key: list(current) for key, current in shard.filters.items()}
    left_filters[split_key] = values[:midpoint]
    right_filters[split_key] = values[midpoint:]
    return [
        ObservationShard(
            shard_id=_observation_shard_id(
                plan=shard.plan,
                country_code=shard.country_code,
                start_year=shard.start_year,
                end_year=shard.end_year,
                filters=current_filters,
                split_depth=shard.split_depth + 1,
            ),
            plan=shard.plan,
            country_code=shard.country_code,
            start_year=shard.start_year,
            end_year=shard.end_year,
            filters=current_filters,
            split_depth=shard.split_depth + 1,
            phase=shard.phase,
            acquisition_method=shard.acquisition_method,
            source_watermark=shard.source_watermark,
            dataset_version=shard.dataset_version,
            dimension_order=shard.dimension_order,
        )
        for current_filters in (left_filters, right_filters)
        if current_filters.get(split_key)
    ]


def _build_probe_request(shard: ObservationShard) -> FetchRequest | None:
    filters = _canonicalize_observation_request_filters(
        source=shard.plan.source,
        filters={key: list(values) for key, values in shard.filters.items()},
    )
    if shard.plan.source == "eurostat":
        probe_time = _eurostat_probe_time_value(shard)
        if not probe_time:
            return None
        filters["time"] = [probe_time]
        return FetchRequest(
            dataset_id=shard.plan.request_dataset_id,
            filters=_filters_to_tuple(filters),
            page_size=50,
        )
    probe_start = datetime(shard.start_year, 1, 1, tzinfo=UTC)
    probe_end = probe_start
    return FetchRequest(
        dataset_id=shard.plan.request_dataset_id,
        filters=_filters_to_tuple(filters),
        date_start=probe_start,
        date_end=probe_end,
        page_size=50,
    )


def _eurostat_probe_time_value(shard: ObservationShard) -> str:
    rank = _observation_frequency_rank(shard.plan.update_frequency)
    if rank == 0:
        return str(shard.start_year)
    if rank == 1:
        return f"{shard.start_year}-Q1"
    return f"{shard.start_year}-01"


def _probe_dimension_split_key(
    rows: list[dict[str, Any]],
    *,
    shard: ObservationShard,
) -> tuple[str, list[str]]:
    candidates: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if shard.plan.source == "eurostat":
            dimensions = _load_json_dict(row.get("dimensions_json"))
            for key, value in dimensions.items():
                normalized_key = str(key or "").strip()
                normalized_value = str(value or "").strip()
                if not normalized_key or not normalized_value:
                    continue
                if normalized_key.lower() in {"time", "geo", "country", "ref_area"}:
                    continue
                candidates[normalized_key].add(normalized_value)
            continue
        for key, value in row.items():
            normalized_key = str(key or "").strip()
            if normalized_key.lower() in {
                "value",
                "time",
                "time_period",
                "geo",
                "country",
                "ref_area",
            }:
                continue
            normalized_value = str(value or "").strip()
            if not normalized_value:
                continue
            candidates[normalized_key].add(normalized_value)
    ranked = sorted(
        (
            (len(values), key, sorted(values))
            for key, values in candidates.items()
            if len(values) > 1 and len(shard.filters.get(key, [])) <= 1
        ),
        reverse=True,
    )
    if not ranked:
        return "", []
    _, key, values = ranked[0]
    return key, values


def _largest_filter_key(filters: dict[str, list[str]]) -> str:
    ranked = sorted(
        (
            (len(values), key)
            for key, values in (filters or {}).items()
            if isinstance(values, list) and len(values) > 1
        ),
        reverse=True,
    )
    return ranked[0][1] if ranked else ""


def _shard_completed(
    config: DatasetBatchConfig,
    shard: ObservationShard,
    *,
    completed: dict[str, Any],
    failed: dict[str, Any],
    deferred: dict[str, Any],
) -> bool:
    if not config.resume or config.resume_mode == "off":
        return False
    if shard.shard_id in completed:
        return True
    return bool(
        config.resume_mode == "smart" and (shard.shard_id in failed or shard.shard_id in deferred)
    )


def _record_shard_result(
    config: DatasetBatchConfig,
    *,
    result: ObservationShardResult,
    completed: dict[str, Any],
    failed: dict[str, Any],
    deferred: dict[str, Any],
) -> None:
    _store_shard_result(
        result=result,
        completed=completed,
        failed=failed,
        deferred=deferred,
    )
    checkpoint_state = _load_observation_checkpoint_state(config)
    _write_observation_checkpoint_state(
        config,
        completed=completed,
        failed=failed,
        deferred=deferred,
        unsupported_signatures=checkpoint_state["unsupported_signatures"],
        empty_signatures=checkpoint_state["empty_signatures"],
        inflight_leases=checkpoint_state["inflight_leases"],
        async_fetch_leases=checkpoint_state["async_fetch_leases"],
        capability_snapshots=checkpoint_state["capability_snapshots"],
        capability_failures=checkpoint_state["capability_failures"],
        source_budgets=checkpoint_state["source_budgets"],
        writer_state=checkpoint_state["writer_state"],
        support_sketches=checkpoint_state["support_sketches"],
        work_packages=checkpoint_state["work_packages"],
        planner_phase=checkpoint_state["planner_phase"],
        publishable_core_complete=checkpoint_state["publishable_core_complete"],
        negative_cache_version=checkpoint_state["negative_cache_version"],
        planner_signature=checkpoint_state["planner_signature"],
    )


def _store_shard_result(
    *,
    result: ObservationShardResult,
    completed: dict[str, Any],
    failed: dict[str, Any],
    deferred: dict[str, Any],
) -> None:
    completed.pop(result.shard_id, None)
    failed.pop(result.shard_id, None)
    deferred.pop(result.shard_id, None)
    target = completed
    if result.status == "failed":
        target = failed
    elif result.status == "deferred":
        target = deferred
    target[result.shard_id] = {
        "status": result.status,
        "source": result.source,
        "dataset_id": result.dataset_id,
        "raw_variable": result.raw_variable,
        "canonical_var": result.canonical_var,
        "country_code": result.country_code,
        "start_year": result.start_year,
        "end_year": result.end_year,
        "row_count": result.row_count,
        "error": result.error,
        "updated_at": datetime.now(UTC).isoformat(),
    }


def _append_shard_result(
    *,
    result: ObservationShardResult,
    completed_results: list[dict[str, Any]],
    failed_results: list[dict[str, Any]],
    deferred_results: list[dict[str, Any]],
    source_summary: dict[str, dict[str, int]],
) -> None:
    payload = {
        "shard_id": result.shard_id,
        "status": result.status,
        "source": result.source,
        "dataset_id": result.dataset_id,
        "raw_variable": result.raw_variable,
        "canonical_var": result.canonical_var,
        "country_code": result.country_code,
        "start_year": result.start_year,
        "end_year": result.end_year,
        "row_count": result.row_count,
        "error": result.error,
    }
    if result.status.startswith("complete"):
        completed_results.append(payload)
    elif result.status == "failed":
        failed_results.append(payload)
    else:
        deferred_results.append(payload)
    summary = source_summary.setdefault(
        result.source,
        {
            "complete": 0,
            "complete_with_rows": 0,
            "complete_empty": 0,
            "failed": 0,
            "deferred": 0,
            "rows": 0,
        },
    )
    if result.status.startswith("complete"):
        summary["complete"] = int(summary.get("complete", 0)) + 1
    summary[result.status] = int(summary.get(result.status, 0)) + 1
    summary["rows"] = int(summary.get("rows", 0)) + int(result.row_count)
