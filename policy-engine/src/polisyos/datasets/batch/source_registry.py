"""Load and validate dataset source registry for staged harvest waves."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_VALID_TIERS = frozenset({"catalog", "fetchable", "transport_ready"})
_VALID_RUN_LANES = frozenset({"catalog", "empirical", "enrichment"})
_VALID_HISTORY_POLICIES = frozenset({"full_snapshot", "rolling_window"})
_VALID_RUN_PROFILES = frozenset(
    {
        "prod_full",
        "prod_core_blocking",
        "rest_backfill",
        "catalog_refresh",
        "preflight_core",
        "observations_backfill",
    }
)


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """One declarative dataset source definition from ``source_registry.yaml``.

    ``execution_tier`` and ``run_lane`` determine whether the source participates only in catalog
    discovery or also in empirical transport/backfill stages; ``seed_from`` models dependency
    expansion between catalog and derived sources.
    """
    name: str
    family: str
    wave: str
    endpoint: str
    enabled: bool = True
    connector_id: str = ""
    profile_id: str = ""
    execution_tier: str = "catalog"
    run_lane: str = "catalog"
    publish_blocking: bool = False
    update_frequency: str = ""
    metrics_required: bool = False
    history_policy: str = "full_snapshot"
    default_lookback_days: int | None = None
    max_rows_per_snapshot: int | None = None
    max_bytes_per_snapshot: int | None = None
    allow_manual_backfill: bool = False
    agency_prefix: str = ""
    agency_allowlist: tuple[str, ...] = ()
    exclude_agencies: tuple[str, ...] = ()
    seed_from: str = ""
    format_allowlist: tuple[str, ...] = ()
    format_denylist: tuple[str, ...] = ()
    keyword_allowlist: tuple[str, ...] = ()
    keyword_denylist: tuple[str, ...] = ()
    require_curated_resources: bool = False

    def included_in_run_profile(self, profile: str) -> bool:
        profile_name = (profile or "prod_full").strip() or "prod_full"
        if profile_name == "prod_full":
            return self.enabled
        if profile_name == "prod_core_blocking":
            return self.enabled and self.publish_blocking
        if profile_name == "rest_backfill":
            return self.enabled and self.allow_manual_backfill
        if profile_name == "catalog_refresh":
            return self.enabled and self.run_lane in {"catalog", "enrichment"}
        if profile_name == "preflight_core":
            return self.enabled and self.publish_blocking and self.run_lane == "empirical"
        if profile_name == "observations_backfill":
            return self.enabled and self.execution_tier == "transport_ready" and self.run_lane == "empirical"
        raise ValueError(f"Unsupported dataset run profile: {profile_name}")


@dataclass(frozen=True, slots=True)
class SourceRegistry:
    """Validated in-memory source registry used by staged dataset harvest waves."""
    version: int
    sources: tuple[SourceSpec, ...] = field(default_factory=tuple)

    def enabled_sources(
        self,
        *,
        wave: str | None = None,
        run_profile: str = "prod_full",
    ) -> list[SourceSpec]:
        """Return sources selected by wave/run profile and expanded seed dependencies."""
        if run_profile not in _VALID_RUN_PROFILES:
            raise ValueError(f"Unsupported dataset run profile: {run_profile}")
        out = [s for s in self.sources if s.enabled]
        if wave:
            out = [s for s in out if s.wave.upper() == wave.upper()]
        out = [s for s in out if s.included_in_run_profile(run_profile)]
        return self._expand_seed_dependencies(out)

    def _expand_seed_dependencies(self, selected: list[SourceSpec]) -> list[SourceSpec]:
        if not selected:
            return []
        enabled_by_name = {spec.name: spec for spec in self.sources if spec.enabled}
        selected_names = {spec.name for spec in selected}
        queue = list(selected)
        while queue:
            spec = queue.pop()
            seed_name = str(spec.seed_from or "").strip()
            if not seed_name:
                continue
            seed_spec = enabled_by_name.get(seed_name)
            if seed_spec is None or seed_spec.name in selected_names:
                continue
            selected_names.add(seed_spec.name)
            queue.append(seed_spec)
        return [spec for spec in self.sources if spec.enabled and spec.name in selected_names]


def load_source_registry(path: Path) -> SourceRegistry:
    """Load YAML source registry from disk."""
    import yaml

    with open(path, "r", encoding="utf-8") as fh:
        payload = yaml.safe_load(fh) or {}

    if not isinstance(payload, dict):
        raise ValueError("source_registry.yaml must be a mapping")

    version = int(payload.get("version", 1))
    raw_sources = payload.get("sources", [])
    if not isinstance(raw_sources, list):
        raise ValueError("source_registry.yaml 'sources' must be a list")

    parsed: list[SourceSpec] = []
    for row in raw_sources:
        if not isinstance(row, dict):
            continue
        execution_tier = str(row.get("execution_tier", "catalog")).strip() or "catalog"
        run_lane = str(
            row.get("run_lane", "catalog" if execution_tier == "catalog" else "empirical")
        ).strip() or ("catalog" if execution_tier == "catalog" else "empirical")
        parsed.append(
            SourceSpec(
                name=str(row.get("name", "")).strip(),
                family=str(row.get("family", "")).strip(),
                wave=str(row.get("wave", "")).strip().upper(),
                endpoint=str(row.get("endpoint", "")).strip(),
                enabled=bool(row.get("enabled", True)),
                connector_id=str(row.get("connector_id", "")).strip(),
                profile_id=str(row.get("profile_id", "")).strip(),
                execution_tier=execution_tier,
                run_lane=run_lane,
                publish_blocking=bool(row.get("publish_blocking", execution_tier != "catalog")),
                update_frequency=str(row.get("update_frequency", "")).strip(),
                metrics_required=bool(row.get("metrics_required", False)),
                history_policy=str(row.get("history_policy", "full_snapshot")).strip() or "full_snapshot",
                default_lookback_days=_int_or_none(row.get("default_lookback_days")),
                max_rows_per_snapshot=_int_or_none(row.get("max_rows_per_snapshot")),
                max_bytes_per_snapshot=_int_or_none(row.get("max_bytes_per_snapshot")),
                allow_manual_backfill=bool(row.get("allow_manual_backfill", False)),
                agency_prefix=str(row.get("agency_prefix", "")).strip(),
                agency_allowlist=tuple(str(v) for v in (row.get("agency_allowlist") or [])),
                exclude_agencies=tuple(str(v) for v in (row.get("exclude_agencies") or [])),
                seed_from=str(row.get("seed_from", "")).strip(),
                format_allowlist=tuple(str(v).strip().upper() for v in (row.get("format_allowlist") or []) if str(v).strip()),
                format_denylist=tuple(str(v).strip().upper() for v in (row.get("format_denylist") or []) if str(v).strip()),
                keyword_allowlist=tuple(str(v).strip().lower() for v in (row.get("keyword_allowlist") or []) if str(v).strip()),
                keyword_denylist=tuple(str(v).strip().lower() for v in (row.get("keyword_denylist") or []) if str(v).strip()),
                require_curated_resources=bool(row.get("require_curated_resources", False)),
            )
        )

    for spec in parsed:
        if not spec.name or not spec.family or not spec.wave or not spec.endpoint:
            raise ValueError(f"Invalid source spec: {spec}")
        if spec.execution_tier not in _VALID_TIERS:
            raise ValueError(f"Invalid execution_tier for {spec.name}: {spec.execution_tier}")
        if spec.run_lane not in _VALID_RUN_LANES:
            raise ValueError(f"Invalid run_lane for {spec.name}: {spec.run_lane}")
        if spec.history_policy not in _VALID_HISTORY_POLICIES:
            raise ValueError(f"Invalid history_policy for {spec.name}: {spec.history_policy}")
        for label, value in (
            ("default_lookback_days", spec.default_lookback_days),
            ("max_rows_per_snapshot", spec.max_rows_per_snapshot),
            ("max_bytes_per_snapshot", spec.max_bytes_per_snapshot),
        ):
            if value is not None and int(value) < 0:
                raise ValueError(f"{label} must be >= 0 for {spec.name}")
        if spec.run_lane == "enrichment" and spec.publish_blocking:
            raise ValueError(f"Enrichment source cannot be publish-blocking: {spec.name}")
        if spec.allow_manual_backfill and spec.history_policy != "rolling_window":
            raise ValueError(
                f"Manual backfill is only supported for rolling_window sources: {spec.name}"
            )
        if spec.default_lookback_days is not None and spec.history_policy != "rolling_window":
            raise ValueError(
                f"default_lookback_days requires rolling_window history_policy: {spec.name}"
            )

    return SourceRegistry(version=version, sources=tuple(parsed))


def _int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)
