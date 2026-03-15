"""Configuration for staged dataset catalog pipeline."""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from pathlib import Path

from polisyos.batch_common.paths import ensure_dirs, snapshot_component_dir
from polisyos.datasets.batch.source_registry import SourceRegistry, load_source_registry

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

    def load_registry(self) -> SourceRegistry:
        path = self.registry_path or (Path(__file__).resolve().parent / "source_registry.yaml")
        return load_source_registry(path)

    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[4]

    @property
    def default_registry_path(self) -> Path:
        return Path(__file__).resolve().parent / "source_registry.yaml"

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
    def uses_custom_registry(self) -> bool:
        if self.registry_path is None:
            return False
        try:
            return self.registry_path.resolve() != self.default_registry_path.resolve()
        except FileNotFoundError:
            return True

    @property
    def is_sampled_run(self) -> bool:
        return int(self.max_datasets_per_source) > 0 and int(self.max_datasets_per_source) < 100_000

    def __post_init__(self) -> None:
        unknown = set(self.stages) - ALL_STAGES
        if unknown:
            raise ValueError(f"Unknown stages: {sorted(unknown)}")
        if self.metrics_map_path is None:
            self.metrics_map_path = self.default_metrics_map_path
        if not self.resolved_metrics_map_path.exists():
            raise ValueError(f"metrics_map.yaml not found: {self.resolved_metrics_map_path}")
        from polisyos.datasets.metrics_map import load_metrics_map

        load_metrics_map(self.resolved_metrics_map_path)
        registry = self.load_registry()
        if (self.date_start or self.date_end) and self.run_profile != "rest_backfill":
            raise ValueError("date_start/date_end overrides are only supported for run_profile='rest_backfill'")
        if self.run_profile == "rest_backfill":
            if not any(spec.allow_manual_backfill and spec.enabled for spec in registry.sources):
                raise ValueError("rest_backfill profile requires at least one enabled rolling-window source")
        ensure_dirs(
            self.component_dir,
            self.raw_dir,
            self.normalized_dir,
            self.merged_dir,
            self.graph_dir,
            self.manifests_dir,
            self.publish_manifest_path.parent,
        )
