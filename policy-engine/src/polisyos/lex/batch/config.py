"""Configuration for the Lex batch pipeline."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

ALL_STAGES = frozenset({"parse", "structure", "spo", "graph", "embed"})


@dataclass
class BatchConfig:
    """Immutable configuration for a single batch pipeline run."""

    # --- Input paths ---
    cards_path: Path
    texts_path: Path
    output_dir: Path
    shard_count: int = 1
    shard_index: int = 0

    # --- Derived path (always output_dir / filename) ---
    @property
    def sharded(self) -> bool:
        return self.shard_count > 1

    @property
    def shard_slug(self) -> str:
        return f"shard_{self.shard_index:02d}_of_{self.shard_count:02d}"

    @property
    def state_dir(self) -> Path:
        if self.sharded:
            return self.output_dir / "_shards" / self.shard_slug
        return self.output_dir

    @property
    def db_path(self) -> Path:
        return self.state_dir / "lex_knowledge_graph.duckdb"

    @property
    def progress_path(self) -> Path:
        return self.state_dir / "progress.jsonl"

    @property
    def manifest_path(self) -> Path:
        return self.state_dir / "manifest.jsonl"

    @property
    def spo_results_dir(self) -> Path:
        return self.output_dir / "spo_results"

    @property
    def provisions_dir(self) -> Path:
        return self.output_dir / "provisions"

    @property
    def openai_batches_dir(self) -> Path:
        return self.state_dir / "openai_batches"

    # --- LLM (Gonka, OpenAI-compatible) ---
    gonka_api_key: str = ""
    gonka_base_url: str = "https://api.gonkagate.com/v1"
    llm_model: str = "qwen/qwen3-235b-a22b-instruct-2507-fp8"
    llm_temperature: float = 0.1
    gonka_disable_json_mode: bool = False
    max_concurrent_llm: int = 20
    rate_limit_rps: float = 5.0
    max_retries: int = 7

    # --- Embedding (OpenAI API) ---
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-large"
    embedding_dimension: int = 3072
    embedding_max_concurrent: int = 10  # gentle on M2 16 GB
    embedding_chunk_size: int = 5000  # vectors per disk flush

    # --- Filtering ---
    status_filter: frozenset[str] | None = None
    type_filter: frozenset[str] | None = None

    # --- Pipeline control ---
    stages: frozenset[str] = field(default_factory=lambda: ALL_STAGES)
    resume: bool = False

    # --- Pipeline limits ---
    max_docs: int | None = None  # stop after processing this many NEW docs (None = unlimited)

    # --- Hardware tuning (MacBook Air M2, 16 GB) ---
    xml_parse_chunk: int = 5000  # docs buffered in RAM during XML parse
    structure_workers: int = 4  # multiprocessing workers
    structure_enable_paragraphs: bool = True
    structure_fallback_chunk_chars: int = 1800
    structure_fallback_chunk_overlap: int = 200
    spo_batch_docs: int = 500  # docs per SPO batch (checkpoint granularity)
    spo_task_batch_size: int = 1000  # max asyncio tasks created per gather() cycle
    spo_max_provisions_per_doc: int | None = None  # cap spans per doc for SPO (debug/smoke)
    spo_verify_mode: str = "llm"  # llm | code
    graph_insert_batch: int = 10_000  # DuckDB INSERT batch size

    # --- Quality gates ---
    quality_gates_enabled: bool = True
    quality_fail_on_critical: bool = False
    quality_max_full_only_docs_pct: float = 30.0
    quality_max_empty_statement_rows_pct: float = 12.0
    quality_max_oov_action_rate_pct: float = 1.0
    quality_max_missing_quote_rate_pct: float = 5.0
    quality_max_duplicate_anchor_rate_pct: float = 0.1
    quality_min_provision_docs_for_doc_rate: int = 25
    quality_min_spo_rows_for_row_rate: int = 50
    quality_min_statements_for_statement_rate: int = 100

    def is_doc_in_shard(self, doc_id: str) -> bool:
        """Deterministically assign a document id to one shard."""
        if not self.sharded:
            return True
        digest = hashlib.sha1(doc_id.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:8], "big") % self.shard_count
        return bucket == self.shard_index

    def __post_init__(self) -> None:
        if self.shard_count < 1:
            raise ValueError("shard_count must be >= 1")
        if self.shard_index < 0 or self.shard_index >= self.shard_count:
            raise ValueError("shard_index must satisfy 0 <= shard_index < shard_count")

        if self.spo_max_provisions_per_doc is not None and self.spo_max_provisions_per_doc < 1:
            raise ValueError("spo_max_provisions_per_doc must be >= 1 when set")
        if self.spo_verify_mode not in {"llm", "code"}:
            raise ValueError("spo_verify_mode must be one of: llm, code")
        if self.quality_min_provision_docs_for_doc_rate < 0:
            raise ValueError("quality_min_provision_docs_for_doc_rate must be >= 0")
        if self.quality_min_spo_rows_for_row_rate < 0:
            raise ValueError("quality_min_spo_rows_for_row_rate must be >= 0")
        if self.quality_min_statements_for_statement_rate < 0:
            raise ValueError("quality_min_statements_for_statement_rate must be >= 0")

        if self.sharded and {"graph", "embed"} & set(self.stages):
            raise ValueError(
                "In sharded mode run only parse/structure/spo stages. "
                "Run graph/embed as a separate single-process finalize pass."
            )

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.spo_results_dir.mkdir(parents=True, exist_ok=True)
        self.provisions_dir.mkdir(parents=True, exist_ok=True)
        self.openai_batches_dir.mkdir(parents=True, exist_ok=True)

        if not self.gonka_api_key:
            self.gonka_api_key = os.environ.get("GONKA_API_KEY", "")
        if not self.openai_api_key:
            self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")

        unknown = set(self.stages) - ALL_STAGES
        if unknown:
            raise ValueError(f"Unknown stages: {unknown}. Valid: {sorted(ALL_STAGES)}")
