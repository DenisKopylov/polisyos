"""Configuration for staged dataset catalog pipeline."""

from __future__ import annotations

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
        "qc",
        "publish",
    }
)
DEFAULT_RUN_STAGES = frozenset(stage for stage in ALL_STAGES if stage != "core_sources_ingest")


@dataclass
class DatasetBatchConfig:
    """Configuration for one dataset batch run under a snapshot root."""

    snapshot_root: Path
    stages: frozenset[str] = field(default_factory=lambda: ALL_STAGES)
    resume: bool = False

    # Source registry and staged harvest
    registry_path: Path | None = None
    wave: str | None = None
    max_datasets_per_source: int = 100_000

    # Embedding
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_dimension: int = 1024
    embedding_batch_size: int = 32
    embedding_device: str = "mps"

    # Thermal
    thermal_profile: str = "m2_air_16gb"
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
    def publish_manifest_path(self) -> Path:
        return self.component_dir / "publish" / "manifest.json"

    @property
    def merged_records_path(self) -> Path:
        return self.merged_dir / "all_records.jsonl"

    @property
    def duplicates_report_path(self) -> Path:
        return self.merged_dir / "duplicates_report.csv"

    def load_registry(self) -> SourceRegistry:
        path = self.registry_path or (Path(__file__).resolve().parent / "source_registry.yaml")
        return load_source_registry(path)

    def __post_init__(self) -> None:
        unknown = set(self.stages) - ALL_STAGES
        if unknown:
            raise ValueError(f"Unknown stages: {sorted(unknown)}")
        ensure_dirs(
            self.component_dir,
            self.raw_dir,
            self.normalized_dir,
            self.merged_dir,
            self.graph_dir,
            self.manifests_dir,
            self.publish_manifest_path.parent,
        )
