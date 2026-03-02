"""Configuration for staged academic knowledge pipeline."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from polisyos.batch_common.paths import ensure_dirs, snapshot_component_dir

ALL_STAGES = frozenset(
    {
        "topic_select",
        "harvest",
        "parse",
        "article_extract",
        "extract_llm",
        "merge_dedup",
        "graph_load",
        "graph_index",
        "embed",
        "qc",
        "publish",
    }
)

def _default_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _slugify(value: str, *, max_len: int = 96) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    cleaned = cleaned.strip("_")
    if not cleaned:
        cleaned = "topic"
    return cleaned[:max_len]


@dataclass
class AcademicBatchConfig:
    """Configuration for one academic run under unified snapshot root."""

    snapshot_root: Path
    stages: frozenset[str] = field(default_factory=lambda: ALL_STAGES)
    resume: bool = False

    # Topic source configuration
    topics_dir: Path | None = None
    topic_limit: int | None = None
    target_per_topic: int = 150
    pass_name: str = "pass1_abstract"
    run_id: str = field(default_factory=_default_run_id)

    # OpenAlex retrieval
    openalex_email: str = ""
    openalex_max_rps: int = 10
    openalex_max_concurrent: int = 5
    openalex_timeout_seconds: int = 60
    openalex_max_retries: int = 5
    openalex_backoff_seconds: float = 5.0
    openalex_per_page: int = 200

    # LLM extractor (selective)
    gonka_api_key: str = ""
    gonka_base_url: str = "https://api.gonkagate.com/v1"
    llm_model: str = "qwen/qwen3-235b-a22b-instruct-2507-fp8"
    llm_temperature: float = 0.1
    max_concurrent_llm: int = 12
    llm_rate_limit_rps: float = 5.0
    llm_max_retries: int = 6

    # Article extractor (phase 0a, Gonka-compatible)
    article_screening_model: str = "qwen/qwen3-32b"
    article_extraction_model: str = "qwen/qwen3-235b-a22b-instruct-2507-fp8"
    article_max_concurrent_llm: int = 20
    article_rate_limit_rps: float = 8.0
    article_max_retries: int = 7
    article_fulltext_timeout_seconds: int = 20

    # LLM gate
    llm_gate_enabled: bool = True
    llm_gate_mode: str = "balanced"  # off|balanced|aggressive
    llm_gate_threshold: float = 0.58
    llm_gate_max_share: float = 0.20
    llm_gate_min_score_force_llm: float = 0.80
    llm_gate_audit_sample_rate: float = 0.02
    llm_gate_audit_max_miss_rate_pct: float = 3.0
    llm_gate_auto_conf_threshold: float = 0.85
    llm_gate_circuit_breaker_enabled: bool = True

    # Embedding (local sentence-transformers)
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_dimension: int = 1024
    embedding_batch_size: int = 32
    embedding_device: str = "mps"

    # Thermal/QC
    thermal_profile: str = "m2_air_16gb"
    cooldown_seconds: int = 300
    fail_fast_qc: bool = True

    # DB tunings
    graph_insert_batch: int = 10_000

    @property
    def component_dir(self) -> Path:
        return snapshot_component_dir(self.snapshot_root, "academic")

    @property
    def raw_dir(self) -> Path:
        return self.component_dir / "raw"

    @property
    def parsed_dir(self) -> Path:
        return self.component_dir / "parsed"

    @property
    def extracted_dir(self) -> Path:
        return self.component_dir / "extracted"

    @property
    def merged_dir(self) -> Path:
        return self.component_dir / "merged"

    @property
    def topic_selection_dir(self) -> Path:
        return self.component_dir / "topic_selection"

    @property
    def graph_dir(self) -> Path:
        return self.component_dir / "graph"

    @property
    def db_path(self) -> Path:
        return self.graph_dir / "scholar_knowledge.duckdb"

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
    def topic_links_path(self) -> Path:
        return self.merged_dir / "topic_links.jsonl"

    @property
    def duplicates_report_path(self) -> Path:
        return self.merged_dir / "duplicates_report.csv"

    @property
    def selected_topic_works_path(self) -> Path:
        return self.topic_selection_dir / "selected_topic_works.jsonl"

    @property
    def selected_global_works_path(self) -> Path:
        return self.topic_selection_dir / "selected_global_works.jsonl"

    @property
    def topics_catalog_path(self) -> Path:
        return self.topic_selection_dir / "topics_catalog.jsonl"

    @property
    def llm_gate_audit_path(self) -> Path:
        return self.component_dir / "llm_gate_audit.jsonl"

    @property
    def llm_gate_manifest_path(self) -> Path:
        return self.manifests_dir / "llm_gate.json"

    @property
    def article_extraction_results_path(self) -> Path:
        return self.component_dir / "article_extraction_results.jsonl"

    @property
    def article_extraction_cache_path(self) -> Path:
        return self.component_dir / "article_extract_cache.jsonl"

    @property
    def ingest_errors_path(self) -> Path:
        return self.component_dir / "errors" / "ingest_errors.jsonl"

    @property
    def active_parsed_dir(self) -> Path:
        return self.extracted_dir if any(self.extracted_dir.glob("*.jsonl")) else self.parsed_dir

    def topic_raw_root(self, topic_id: str, topic_name: str = "") -> Path:
        suffix = _slugify(topic_name) if topic_name else topic_id.lower()
        return self.raw_dir / f"{topic_id.lower()}__{suffix}"

    def __post_init__(self) -> None:
        unknown = set(self.stages) - ALL_STAGES
        if unknown:
            raise ValueError(f"Unknown stages: {sorted(unknown)}")

        if self.target_per_topic < 1:
            raise ValueError("target_per_topic must be >= 1")

        if self.llm_gate_mode not in {"off", "balanced", "aggressive"}:
            raise ValueError("llm_gate_mode must be one of: off, balanced, aggressive")
        if not (0.0 <= self.llm_gate_threshold <= 1.0):
            raise ValueError("llm_gate_threshold must be in range [0, 1]")
        if not (0.0 <= self.llm_gate_max_share <= 1.0):
            raise ValueError("llm_gate_max_share must be in range [0, 1]")
        if not (0.0 <= self.llm_gate_min_score_force_llm <= 1.0):
            raise ValueError("llm_gate_min_score_force_llm must be in range [0, 1]")
        if not (0.0 <= self.llm_gate_audit_sample_rate <= 1.0):
            raise ValueError("llm_gate_audit_sample_rate must be in range [0, 1]")
        if self.llm_gate_audit_max_miss_rate_pct < 0.0:
            raise ValueError("llm_gate_audit_max_miss_rate_pct must be >= 0")
        if not (0.0 <= self.llm_gate_auto_conf_threshold <= 1.0):
            raise ValueError("llm_gate_auto_conf_threshold must be in range [0, 1]")

        if self.topics_dir is None:
            self.topics_dir = Path("/Users/deniskopylov/polisyos/relevant_topics_domain_files")

        ensure_dirs(
            self.component_dir,
            self.raw_dir,
            self.parsed_dir,
            self.extracted_dir,
            self.merged_dir,
            self.topic_selection_dir,
            self.graph_dir,
            self.manifests_dir,
            self.publish_manifest_path.parent,
            self.ingest_errors_path.parent,
        )

        if not self.openalex_email:
            self.openalex_email = os.environ.get("OPENALEX_EMAIL", "")
        if not self.gonka_api_key:
            self.gonka_api_key = os.environ.get("GONKA_API_KEY", "")
