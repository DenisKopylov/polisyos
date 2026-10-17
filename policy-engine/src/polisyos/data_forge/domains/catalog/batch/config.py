"""Configuration for staged dataset catalog pipeline."""

from __future__ import annotations

import json
import os
import platform
import types
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import TYPE_CHECKING, Union, cast, get_args, get_origin, get_type_hints

if TYPE_CHECKING:
    from collections.abc import Callable

from polisyos.data_forge.domains.catalog._resources import catalog_default_resource_path
from polisyos.data_forge.domains.catalog.batch.checkpoints import hash_payload
from polisyos.data_forge.domains.catalog.batch.material_inputs import (
    _material_file_snapshot,
)
from polisyos.data_forge.domains.catalog.batch.source_registry import (
    SourceRegistry,
    load_source_registry,
)
from polisyos.data_forge.domains.catalog.knowledge.country_codes import (
    COUNTRY_SCOPES,
    country_scope_members,
)
from polisyos.data_forge.domains.catalog.registry import (
    default_catalog_source_registry_path,
)
from polisyos.data_forge.domains.catalog.selection import validate_catalog_run_profile
from polisyos.data_forge.kernel.io import ensure_dirs
from polisyos.data_forge.kernel.io.generation_basis import build_generation_basis

_PROFILE_INPUT_COVERAGE_SCHEMA_VERSION = "policyos.catalog.profile_input_coverage.v1"
_PROFILE_INPUT_COVERAGE_STATES = frozenset({"none", "excluded_present"})


@dataclass(frozen=True, slots=True)
class _RuntimeSourceProfileSnapshot:
    """One immutable in-memory view of profile inputs consumed by a catalog run.

    Connection configs may carry secrets and are deliberately excluded from the
    representation and from every persisted signature. Only their excluded-input
    presence classification is persisted.
    """

    connection_configs: Mapping[str, object] = field(repr=False)
    execution_policies: Mapping[str, object] = field(repr=False)
    coverage: Mapping[str, object] = field(repr=False)
    profile_payload: bytes = field(repr=False)
    legacy_serial_mode: bool


_RUNTIME_SOURCE_PROFILE_SNAPSHOT: ContextVar[_RuntimeSourceProfileSnapshot | None] = ContextVar(
    "polisyos_catalog_runtime_source_profile_snapshot", default=None
)

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

    @classmethod
    def from_producer_config_snapshot(
        cls, snapshot: Mapping[str, object]
    ) -> DatasetBatchConfig | None:
        """Rehydrate complete saved producer intent without producer side effects."""
        coverage_state, _profile_coverage = parse_profile_input_coverage(
            snapshot.get("resolved_profile_input_coverage"),
            missing="resolved_profile_input_coverage" not in snapshot,
        )
        if coverage_state != "established":
            return None
        raw = {item.name for item in fields(cls)} - {"resume", "stages"}
        derived = {
            "resolved_embedding_device",
            "resolved_active_countries",
            "resolved_year_window",
            "resolved_metrics_map_path",
            "resolved_registry_path",
            "uses_custom_registry",
            "is_sampled_run",
            "producer_material_input_basis",
            "resolved_profile_input_coverage",
        }
        if set(snapshot) != raw | derived:
            return None
        try:
            annotations = get_type_hints(cls)
            values = {
                name: _decode_config_snapshot_value(snapshot[name], annotations[name])
                for name in raw
            }
            if values.get("metrics_map_path") is None:
                return None
            values = _validate_dataset_batch_config_values(values, allow_default_metrics_map=False)
            # Allocate only after strict decoding and the complete shared validator.
            config = object.__new__(cls)
            object.__setattr__(config, "stages", ALL_STAGES)
            object.__setattr__(config, "resume", False)
            for name, value in values.items():
                object.__setattr__(config, name, value)
            if set(_producer_config_snapshot(config)) != set(snapshot):
                return None
        except AttributeError, KeyError, OSError, TypeError, ValueError:
            return None
        return config

    @property
    def component_dir(self) -> Path:
        """Return the component path without creating producer directories."""
        return Path(self.snapshot_root) / "datasets"

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
        return catalog_default_resource_path("metrics_map.yaml")

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
            return selected_path not in {
                self.default_registry_path.resolve(),
                legacy_path,
            }
        except FileNotFoundError:
            return True

    @property
    def is_sampled_run(self) -> bool:
        return int(self.max_datasets_per_source) > 0 and int(self.max_datasets_per_source) < 100_000

    def __post_init__(self) -> None:
        unknown = set(self.stages) - ALL_STAGES
        if unknown:
            raise ValueError(f"Unknown stages: {sorted(unknown)}")
        values = {
            item.name: getattr(self, item.name)
            for item in fields(self)
            if item.name not in {"resume", "stages"}
        }
        for name, value in _validate_dataset_batch_config_values(
            values, allow_default_metrics_map=True
        ).items():
            setattr(self, name, value)
        self._ensure_output_directories()

    def _ensure_output_directories(self) -> None:
        """Create producer output directories after read-only validation."""
        ensure_dirs(
            self.component_dir,
            self.raw_dir,
            self.normalized_dir,
            self.merged_dir,
            self.graph_dir,
            self.manifests_dir,
            self.publish_manifest_path.parent,
        )


def _decode_config_snapshot_value(value: object, annotation: object) -> object:
    """Decode JSON-safe persisted values strictly using declared dataclass types."""
    origin, args = get_origin(annotation), get_args(annotation)
    if origin in {types.UnionType, Union}:
        if value is None and type(None) in args:
            return None
        for member in args:
            if member is type(None):
                continue
            try:
                return _decode_config_snapshot_value(value, member)
            except TypeError, ValueError:
                pass
        raise TypeError("persisted config union type mismatch")
    if annotation is Path:
        if not isinstance(value, str) or not value:
            raise TypeError("persisted path must be a non-empty string")
        return Path(value)
    if origin is tuple:
        if not isinstance(value, (list, tuple)) or isinstance(value, (str, bytes)):
            raise TypeError("persisted tuple must be an array")
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_decode_config_snapshot_value(x, args[0]) for x in value)
        if len(value) != len(args):
            raise TypeError("persisted tuple length mismatch")
        return tuple(
            _decode_config_snapshot_value(x, typ) for x, typ in zip(value, args, strict=True)
        )
    if origin is frozenset:
        if not isinstance(value, (list, tuple, set, frozenset)) or isinstance(value, str):
            raise TypeError("persisted frozenset must be an array")
        return frozenset(_decode_config_snapshot_value(x, args[0]) for x in value)
    if annotation is bool:
        if type(value) is not bool:
            raise TypeError("persisted bool mismatch")
        return value
    if annotation is int:
        if type(value) is not int:
            raise TypeError("persisted int mismatch")
        return value
    if annotation is str:
        if not isinstance(value, str):
            raise TypeError("persisted str mismatch")
        return value
    if isinstance(annotation, type) and isinstance(value, annotation):
        return value
    raise TypeError("unsupported persisted config field type")


def _validate_dataset_batch_config_values(
    values: Mapping[str, object], *, allow_default_metrics_map: bool
) -> dict[str, object]:
    """Canonical read-only semantic validation shared by constructor and rehydration."""
    normalized = dict(values)
    run_profile = normalized.get("run_profile")
    if not isinstance(run_profile, str):
        raise TypeError("run_profile must be text")
    validate_catalog_run_profile(run_profile)
    metrics_path = normalized.get("metrics_map_path")
    if metrics_path is None and allow_default_metrics_map:
        metrics_path = catalog_default_resource_path("metrics_map.yaml")
    if not isinstance(metrics_path, Path):
        raise ValueError("persisted metrics_map_path is required")
    if not metrics_path.exists():
        raise ValueError(f"metrics_map.yaml not found: {metrics_path}")
    from polisyos.data_forge.domains.catalog.metrics_map import load_metrics_map

    load_metrics_map(metrics_path)
    normalized["metrics_map_path"] = metrics_path
    registry_path = normalized.get("registry_path")
    if registry_path is not None and not isinstance(registry_path, Path):
        raise TypeError("registry_path must be a path or null")
    registry = load_source_registry(registry_path or default_catalog_source_registry_path())
    if (
        normalized.get("date_start") or normalized.get("date_end")
    ) and run_profile != "rest_backfill":
        raise ValueError(
            "date_start/date_end overrides are only supported for run_profile='rest_backfill'"
        )
    if run_profile == "rest_backfill" and not any(
        x.allow_manual_backfill and x.enabled for x in registry.sources
    ):
        raise ValueError(
            "rest_backfill profile requires at least one enabled rolling-window source"
        )
    if normalized.get("observation_mode") not in {"all", "core", "backfill"}:
        raise ValueError("observation_mode must be one of: all, core, backfill")
    if normalized.get("resume_mode") not in {"smart", "force", "off"}:
        raise ValueError("resume_mode must be one of: smart, force, off")
    if normalized.get("country_scope") not in COUNTRY_SCOPES and not normalized.get(
        "active_countries"
    ):
        raise ValueError(f"Unknown country scope: {normalized.get('country_scope')}")
    return normalized


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
    profile_snapshot = _current_runtime_source_profile_snapshot()
    if profile_snapshot is None:
        profile_snapshot = _capture_runtime_source_profile_snapshot()
    profile_input_coverage = _runtime_profile_input_coverage(profile_snapshot)
    values.update(
        {
            "resolved_embedding_device": config.resolved_embedding_device,
            "resolved_active_countries": config.resolved_active_countries,
            "resolved_year_window": config.resolved_year_window,
            "resolved_metrics_map_path": config.resolved_metrics_map_path,
            "resolved_registry_path": config.registry_path or config.default_registry_path,
            "uses_custom_registry": config.uses_custom_registry,
            "is_sampled_run": config.is_sampled_run,
            "producer_material_input_basis": _producer_material_input_basis(
                config,
                profile_input_coverage=profile_input_coverage,
                profile_snapshot=profile_snapshot,
            ),
            "resolved_profile_input_coverage": profile_input_coverage,
        }
    )
    return {key: _signature_safe(value) for key, value in values.items()}


def _producer_material_input_basis(
    config: DatasetBatchConfig,
    *,
    profile_input_coverage: dict[str, object],
    profile_snapshot: _RuntimeSourceProfileSnapshot,
) -> dict[str, object]:
    """Bind canonical policy file bytes and covered live profile settings.

    File members use the exact locators consumed by the canonical owners,
    including both WVS readers and the conditional local metadata fallback.
    Required absence refuses recomputation; optional absence is content-bound.
    Profile settings have the explicit header/credential exclusions below.
    """
    from polisyos.data_forge.domains.catalog.batch import harvester
    from polisyos.data_forge.domains.catalog.batch.core_sources import api as core_api
    from polisyos.data_forge.domains.catalog.batch.core_sources import loaders
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
        "source_registry": (
            config.registry_path or config.default_registry_path,
            True,
            True,
        ),
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
    members.append(("resolved_profile_registry", profile_snapshot.profile_payload))
    members.append(
        (
            "resolved_profile_input_coverage",
            json.dumps(
                profile_input_coverage,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
    )
    members.append(
        (
            "resolved_producer_runtime_policy",
            json.dumps(
                {"legacy_serial_mode_enabled": profile_snapshot.legacy_serial_mode},
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


def _runtime_profile_input_coverage(
    snapshot: _RuntimeSourceProfileSnapshot | None = None,
) -> dict[str, object]:
    """Classify one complete immutable profile snapshot without input values."""
    profile_snapshot = snapshot or _current_runtime_source_profile_snapshot()
    if profile_snapshot is None:
        profile_snapshot = _capture_runtime_source_profile_snapshot()
    profiles = cast("Mapping[str, str]", profile_snapshot.coverage["profiles"])
    return {
        "schema_version": _PROFILE_INPUT_COVERAGE_SCHEMA_VERSION,
        "profiles": dict(sorted(profiles.items())),
    }


def _capture_runtime_source_profile_snapshot() -> _RuntimeSourceProfileSnapshot:
    """Copy profiles once, then resolve every runtime input from those copies."""
    from polisyos.fabric.connectors.base import ConnectionConfig
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
    from polisyos.fabric.connectors.profiles.resolver import (
        resolve_connection_config,
        resolve_execution_policy,
    )

    # snapshot_all copies while holding the registry lock. Re-copying these
    # detached models outside that lock would add work without improving the
    # supported register/override consistency guarantee.
    profiles = tuple(SourceProfileRegistry.get_instance().snapshot_all())
    token = str(os.getenv("POLISYOS_UNPD_API_TOKEN") or "").strip()
    legacy_serial_mode_value = (
        str(os.getenv("POLISYOS_DATASET_LEGACY_SERIAL") or "").strip().lower()
    )
    connections: dict[str, ConnectionConfig] = {}
    policies: dict[str, object] = {}
    coverage: dict[str, str] = {}
    payload: list[dict[str, object]] = []
    for profile in profiles:
        connection = resolve_connection_config(profile)
        if (
            profile.profile_id == "unpd_dataportal"
            and token
            and not connection.auth_credentials.get("token")
        ):
            credentials = dict(connection.auth_credentials)
            credentials["token"] = token
            connection = ConnectionConfig(
                url=connection.url,
                headers=dict(connection.headers),
                auth_method=connection.auth_method or "bearer",
                auth_credentials=credentials,
                timeout_seconds=connection.timeout_seconds,
                max_retries=connection.max_retries,
                retry_delay_seconds=connection.retry_delay_seconds,
                rate_limit_rps=connection.rate_limit_rps,
                max_connections=connection.max_connections,
                keepalive_seconds=connection.keepalive_seconds,
                verify_ssl=connection.verify_ssl,
                ca_bundle_path=connection.ca_bundle_path,
            )
        connections[profile.profile_id] = connection
        policies[profile.profile_id] = resolve_execution_policy(profile)
        coverage[profile.profile_id] = (
            "excluded_present"
            if connection.headers or connection.auth_method or connection.auth_credentials
            else "none"
        )
        payload.append(
            {
                "profile": profile.model_dump(mode="json", exclude={"headers"}),
                "connection": {
                    item.name: _signature_safe(getattr(connection, item.name))
                    for item in fields(connection)
                    if item.name
                    not in {"headers", "auth_credentials", "source_profile_fingerprint"}
                },
                "execution_policy": policies[profile.profile_id].model_dump(mode="json"),
            }
        )
    frozen_coverage = types.MappingProxyType(
        {
            "schema_version": _PROFILE_INPUT_COVERAGE_SCHEMA_VERSION,
            "profiles": types.MappingProxyType(dict(sorted(coverage.items()))),
        }
    )
    return _RuntimeSourceProfileSnapshot(
        connection_configs=types.MappingProxyType(connections),
        execution_policies=types.MappingProxyType(policies),
        coverage=frozen_coverage,
        profile_payload=json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8"),
        legacy_serial_mode=legacy_serial_mode_value in {"1", "true", "yes", "on"},
    )


@contextmanager
def _runtime_source_profile_snapshot_scope() -> Iterator[_RuntimeSourceProfileSnapshot]:
    """Keep profile resolution stable across one catalog pipeline operation."""
    current = _current_runtime_source_profile_snapshot()
    if current is not None:
        yield current
        return
    snapshot = _capture_runtime_source_profile_snapshot()
    token: Token[_RuntimeSourceProfileSnapshot | None] = _RUNTIME_SOURCE_PROFILE_SNAPSHOT.set(
        snapshot
    )
    try:
        yield snapshot
    finally:
        _RUNTIME_SOURCE_PROFILE_SNAPSHOT.reset(token)


def _current_runtime_source_profile_snapshot() -> _RuntimeSourceProfileSnapshot | None:
    """Return the profile snapshot active for the current run, if any."""
    return _RUNTIME_SOURCE_PROFILE_SNAPSHOT.get()


def parse_profile_input_coverage(
    value: object, *, missing: bool = False
) -> tuple[str, dict[str, str] | None]:
    """Validate persisted coverage classifications; absent legacy data stays unknown."""
    if missing:
        return "legacy_unknown", None
    if not isinstance(value, Mapping) or set(value) != {"schema_version", "profiles"}:
        return "malformed", None
    if value.get("schema_version") != _PROFILE_INPUT_COVERAGE_SCHEMA_VERSION:
        return "malformed", None
    profiles = value.get("profiles")
    if not isinstance(profiles, Mapping) or not profiles:
        return "malformed", None
    normalized: dict[str, str] = {}
    for profile_id, state in profiles.items():
        if (
            not isinstance(profile_id, str)
            or not profile_id.strip()
            or not isinstance(state, str)
            or state not in _PROFILE_INPUT_COVERAGE_STATES
        ):
            return "malformed", None
        normalized[profile_id] = state
    return "established", dict(sorted(normalized.items()))


def profile_input_coverage_currentness(
    value: object, *, missing: bool = False
) -> tuple[str, dict[str, str] | None]:
    """Classify whether excluded profile inputs are safe to call current.

    Header and credential values are deliberately never persisted. Their mere
    presence is therefore insufficient to prove two effective profiles equal.
    """
    state, profiles = parse_profile_input_coverage(value, missing=missing)
    if state != "established" or profiles is None:
        return state, profiles
    if any(value == "excluded_present" for value in profiles.values()):
        return "not_established", profiles
    return "established", profiles


def _runtime_profile_input_currentness() -> tuple[str, dict[str, str] | None]:
    """Recompute profile currentness from one immutable effective snapshot."""
    try:
        coverage = _runtime_profile_input_coverage()
        return profile_input_coverage_currentness(coverage)
    except Exception:
        return "malformed", None


def _runtime_source_profile_payload() -> bytes:
    """Bind profile settings while retaining only coverage of excluded inputs.

    Core ingest may select profile IDs from persisted catalog bindings as well
    as source YAML. The complete registry is a conservative finite denominator.
    Header and credential contents remain excluded; their presence classification
    is separately content-bound in the producer basis. No values or digests of
    headers, credentials, or environment tokens are persisted.
    """
    snapshot = _current_runtime_source_profile_snapshot()
    if snapshot is None:
        snapshot = _capture_runtime_source_profile_snapshot()
    return snapshot.profile_payload


def _signature_safe(value: object) -> object:
    if isinstance(value, Path):
        return str(value.resolve())
    if isinstance(value, Mapping):
        return {str(key): _signature_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_signature_safe(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(
            (_signature_safe(item) for item in value),
            key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True),
        )
    return value
