"""Configuration for staged dataset catalog pipeline."""

from __future__ import annotations

import json
import platform
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable

from polisyos.data_forge.domains.catalog.batch.checkpoints import hash_payload
from polisyos.data_forge.domains.catalog.batch.material_inputs import _material_file_snapshot
from polisyos.data_forge.domains.catalog.batch.source_registry import (
    SourceRegistry,
    load_source_registry,
)
from polisyos.data_forge.domains.catalog.knowledge.country_codes import (
    COUNTRY_SCOPES,
    country_scope_members,
)
from polisyos.data_forge.domains.catalog.registry import default_catalog_source_registry_path
from polisyos.data_forge.domains.catalog.selection import validate_catalog_run_profile
from polisyos.data_forge.kernel.io import ensure_dirs, snapshot_component_dir
from polisyos.data_forge.kernel.io.generation_basis import build_generation_basis

ALL_STAGES = frozenset(
    {
        "harvest",
        "normalize",
        "merge_dedup",
        "graph_load",
        "graph_index",
        "core_sources_ingest",
        "embed",
        "benchmark",
        "qc",
        "publish",
    }
)
DEFAULT_RUN_STAGES = ALL_STAGES


@dataclass
class DatasetBatchConfig:
    """Configuration for one dataset batch run under a snapshot root."""

    snapshot_root: Path
    stages: frozenset[str] = field(default_factory=lambda: ALL_STAGES)
    resume: bool = False

    # Source registry and staged harvest
    registry_path: Path | None = None
    metrics_map_path: Path | None = None
    wave: str | None = None
    run_profile: str = "prod_full"
    max_datasets_per_source: int = 100_000
    promoted_sources: tuple[str, ...] = ()
    date_start: str | None = None
    date_end: str | None = None
    country_scope: str = "core_blocking"
    active_countries: tuple[str, ...] = ()
    active_year_window: tuple[int, int] = (2018, 2022)
    observation_mode: str = "all"
    resume_mode: str = "smart"
    preflight_sources: tuple[str, ...] = ()
    preflight_only: bool = False
    defer_unsupported_observation_plans: bool = True

    # Embedding
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_dimension: int = 1024
    embedding_batch_size: int = 32
    embedding_device: str = "auto"

    # Thermal
    thermal_profile: str = "server_cpx42"
    cooldown_seconds: int = 300

    # QC
    fail_fast_qc: bool = True

    # HTTP
    harvest_timeout: int = 60

    @property
    def component_dir(self) -> Path:
        return snapshot_component_dir(self.snapshot_root, "datasets")

    @property
    def raw_dir(self) -> Path:
        return self.component_dir / "raw"

    @property
    def normalized_dir(self) -> Path:
        return self.component_dir / "normalized"

    @property
    def merged_dir(self) -> Path:
        return self.component_dir / "merged"

    @property
    def graph_dir(self) -> Path:
        return self.component_dir / "graph"

    @property
    def db_path(self) -> Path:
        return self.graph_dir / "dataset_catalog.duckdb"

    @property
    def index_dir(self) -> Path:
        return self.component_dir

    @property
    def manifests_dir(self) -> Path:
        return self.component_dir / "manifests"

    @property
    def qc_report_path(self) -> Path:
        return self.component_dir / "qc_report.json"

    @property
    def benchmark_report_path(self) -> Path:
        return self.component_dir / "benchmark_report.json"

    @property
    def publish_manifest_path(self) -> Path:
        return self.component_dir / "publish" / "manifest.json"

    @property
    def consumer_readiness_path(self) -> Path:
        return self.component_dir / "publish" / "consumer_readiness.json"

    @property
    def merged_records_path(self) -> Path:
        return self.merged_dir / "all_records.jsonl"

    @property
    def duplicates_report_path(self) -> Path:
        return self.merged_dir / "duplicates_report.csv"

    @property
    def stage_state_path(self) -> Path:
        return self.manifests_dir / "stage_state.json"

    @property
    def harvest_checkpoint_path(self) -> Path:
        return self.manifests_dir / "harvest_checkpoint.json"

    @property
    def normalize_checkpoint_path(self) -> Path:
        return self.manifests_dir / "normalize_checkpoint.json"

    @property
    def observation_ingest_checkpoint_path(self) -> Path:
        return self.manifests_dir / "observation_ingest_checkpoint.json"

    @property
    def telemetry_path(self) -> Path:
        return self.manifests_dir / "telemetry.json"

    def load_registry(self) -> SourceRegistry:
        path = self.registry_path or self.default_registry_path
        return load_source_registry(path)

    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[6]

    @property
    def default_registry_path(self) -> Path:
        return default_catalog_source_registry_path()

    @property
    def default_metrics_map_path(self) -> Path:
        return self.repo_root / "data" / "dataset_catalog" / "metrics_map.yaml"

    @property
    def resolved_metrics_map_path(self) -> Path:
        return self.metrics_map_path or self.default_metrics_map_path

    @property
    def resolved_embedding_device(self) -> str:
        if self.embedding_device and self.embedding_device != "auto":
            return self.embedding_device
        return "mps" if platform.system() == "Darwin" else "cpu"

    @property
    def resolved_active_countries(self) -> tuple[str, ...]:
        if self.active_countries:
            return tuple(
                sorted({item.strip().upper() for item in self.active_countries if item.strip()})
            )
        return tuple(country_scope_members(self.country_scope))

    @property
    def resolved_year_window(self) -> tuple[int, int]:
        start_year, end_year = self.active_year_window
        start_value = int(start_year)
        end_value = int(end_year)
        if end_value < start_value:
            raise ValueError("active_year_window must be ordered as (start_year, end_year)")
        return start_value, end_value

    @property
    def run_signature(self) -> str:
        return hash_payload({"producer_config": _producer_config_snapshot(self)})

    @property
    def uses_custom_registry(self) -> bool:
        if self.registry_path is None:
            return False
        try:
            selected_path = self.registry_path.resolve()
            legacy_path = (Path(__file__).resolve().parent / "source_registry.yaml").resolve()
            return selected_path not in {self.default_registry_path.resolve(), legacy_path}
        except FileNotFoundError:
            return True

    @property
    def is_sampled_run(self) -> bool:
        return int(self.max_datasets_per_source) > 0 and int(self.max_datasets_per_source) < 100_000

    def __post_init__(self) -> None:
        unknown = set(self.stages) - ALL_STAGES
        if unknown:
            raise ValueError(f"Unknown stages: {sorted(unknown)}")
        validate_catalog_run_profile(self.run_profile)
        if self.metrics_map_path is None:
            self.metrics_map_path = self.default_metrics_map_path
        if not self.resolved_metrics_map_path.exists():
            raise ValueError(f"metrics_map.yaml not found: {self.resolved_metrics_map_path}")
        from polisyos.data_forge.domains.catalog.metrics_map import load_metrics_map

        load_metrics_map(self.resolved_metrics_map_path)
        registry = self.load_registry()
        if (self.date_start or self.date_end) and self.run_profile != "rest_backfill":
            raise ValueError(
                "date_start/date_end overrides are only supported for run_profile='rest_backfill'"
            )
        if self.run_profile == "rest_backfill":
            if not any(spec.allow_manual_backfill and spec.enabled for spec in registry.sources):
                raise ValueError(
                    "rest_backfill profile requires at least one enabled rolling-window source"
                )
        if self.observation_mode not in {"all", "core", "backfill"}:
            raise ValueError("observation_mode must be one of: all, core, backfill")
        if self.resume_mode not in {"smart", "force", "off"}:
            raise ValueError("resume_mode must be one of: smart, force, off")
        if self.country_scope not in COUNTRY_SCOPES and not self.active_countries:
            raise ValueError(f"Unknown country scope: {self.country_scope}")
        ensure_dirs(
            self.component_dir,
            self.raw_dir,
            self.normalized_dir,
            self.merged_dir,
            self.graph_dir,
            self.manifests_dir,
            self.publish_manifest_path.parent,
        )


def _producer_config_snapshot(config: DatasetBatchConfig) -> dict[str, object]:
    """Return producer configuration and one content-bound material input basis.

    ``resume`` and ``stages`` select orchestration behavior; they do not change
    what an individual stage produces. All other config fields are included,
    along with derived values that resolve platform- or policy-dependent
    defaults before producers read them.
    """
    values = {
        item.name: getattr(config, item.name)
        for item in fields(config)
        if item.name not in {"resume", "stages"}
    }
    values.update(
        {
            "resolved_embedding_device": config.resolved_embedding_device,
            "resolved_active_countries": config.resolved_active_countries,
            "resolved_year_window": config.resolved_year_window,
            "resolved_metrics_map_path": config.resolved_metrics_map_path,
            "resolved_registry_path": config.registry_path or config.default_registry_path,
            "uses_custom_registry": config.uses_custom_registry,
            "is_sampled_run": config.is_sampled_run,
            "producer_material_input_basis": _producer_material_input_basis(config),
        }
    )
    return {key: _signature_safe(value) for key, value in values.items()}


def _producer_material_input_basis(config: DatasetBatchConfig) -> dict[str, object]:
    """Bind canonical policy file bytes and covered live profile settings.

    File members use the exact locators consumed by the canonical owners,
    including both WVS readers and the conditional local metadata fallback.
    Required absence refuses recomputation; optional absence is content-bound.
    Profile settings have the explicit header/credential exclusions below.
    """
    from polisyos.data_forge.domains.catalog.batch import harvester
    from polisyos.data_forge.domains.catalog.batch.core_sources import api as core_api
    from polisyos.data_forge.domains.catalog.batch.core_sources import loaders
    from polisyos.data_forge.domains.catalog.batch.core_sources.api import (
        _legacy_serial_mode_enabled,
    )
    from polisyos.data_forge.domains.catalog.knowledge import proxy_penalties

    harvest_wvs_snapshot = _material_file_snapshot(harvester._wvs_registry_path())
    wvs_fallback_selected = not harvester._load_wvs_indicator_registry_snapshot(
        harvest_wvs_snapshot
    )
    # API resolves this canonical locator through its existing dependency map.
    seed_alignments_path = cast(
        "Callable[[], Path]", getattr(core_api, "_seed_alignments_path", None)
    )()
    paths = {
        "source_registry": (config.registry_path or config.default_registry_path, True, True),
        "metrics_map": (config.resolved_metrics_map_path, True, True),
        "seed_variable_alignments": (seed_alignments_path, True, True),
        "proxy_metric_alignments": (
            proxy_penalties.default_proxy_metric_alignments_path(),
            False,
            True,
        ),
        "wvs_indicator_registry_core": (loaders._wvs_registry_path(), False, True),
        "wvs_indicator_registry_harvest": (harvester._wvs_registry_path(), False, True),
        "wvs_variable_catalog": (
            harvester._wvs_variable_catalog_path(),
            False,
            wvs_fallback_selected,
        ),
    }
    snapshots = {
        role: (
            harvest_wvs_snapshot
            if role == "wvs_indicator_registry_harvest"
            else _material_file_snapshot(path, required=required, selected=selected)
        )
        for role, (path, required, selected) in sorted(paths.items())
    }
    members = [snapshot.generation_member(role) for role, snapshot in snapshots.items()]
    members.append(("resolved_profile_registry", _runtime_source_profile_payload()))
    members.append(
        (
            "resolved_producer_runtime_policy",
            json.dumps(
                {"legacy_serial_mode_enabled": _legacy_serial_mode_enabled()},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
    )
    return build_generation_basis(
        basis_kind="catalog_producer_material_inputs",
        generator_rule_version="policyos.catalog.producer_material_inputs.v1",
        members=members,
    ).to_dict()


def _runtime_source_profile_payload() -> bytes:
    """Bind live profile settings and resolved contracts with declared exclusions.

    Core ingest may select profile IDs from persisted catalog bindings as well
    as source YAML. The complete registry is a conservative finite denominator.
    Presentation-only profile edits also invalidate reuse. ALL header policy
    (including non-secret content negotiation), credentials and environment
    auth overlays are omitted. No header revision or classifier is established;
    complete effective-policy currentness remains limited until the owner
    supplies a non-secret revision or enforces explicit invalidation.
    Only member digests are persisted.
    """
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
    from polisyos.fabric.connectors.profiles.resolver import (
        resolve_connection_config,
        resolve_execution_policy,
    )

    profiles = [
        profile.model_copy(deep=True) for profile in SourceProfileRegistry.get_instance().list_all()
    ]
    payload: list[dict[str, object]] = []
    for profile in profiles:
        connection = resolve_connection_config(profile)
        payload.append(
            {
                "profile": profile.model_dump(mode="json", exclude={"headers"}),
                "connection": {
                    item.name: _signature_safe(getattr(connection, item.name))
                    for item in fields(connection)
                    if item.name not in {"headers", "auth_credentials"}
                },
                "execution_policy": resolve_execution_policy(profile).model_dump(mode="json"),
            }
        )
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _signature_safe(value: object) -> object:
    if isinstance(value, Path):
        return str(value.resolve())
    if isinstance(value, Mapping):
        return {str(key): _signature_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_signature_safe(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_signature_safe(item) for item in value)
    return value
