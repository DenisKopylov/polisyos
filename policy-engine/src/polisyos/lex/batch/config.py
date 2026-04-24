"""Configuration for the Lex batch pipeline."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

ALL_STAGES = frozenset(
    {
        "parse",
        "structure",
        "spo",
        "ground_quotes",
        "resolve_refs",
        "graph",
        "export_claims",
        "benchmark",
        # Operational finalize stages are invoked via dedicated CLI commands,
        # but they still need to be accepted by BatchConfig for tests/helpers.
        "qc",
        "publish_bundle",
    }
)


def _default_gonka_api_keys() -> list[str]:
    primary = str(os.environ.get("GONKA_API_KEY", "")).strip()
    keys: list[str] = [primary] if primary else []
    numbered: list[tuple[int, str]] = []
    for key, value in os.environ.items():
        if not key.startswith("GONKA_API_KEY_"):
            continue
        suffix = key.removeprefix("GONKA_API_KEY_")
        if not suffix.isdigit():
            continue
        token = str(value or "").strip()
        if token:
            numbered.append((int(suffix), token))
    for _, token in sorted(numbered):
        if token not in keys:
            keys.append(token)
    return keys


def _default_llm_gap_fill_tail_markers() -> list[str]:
    return [
        "може",
        "не може",
        "має право",
        "крім",
        "за винятком",
        "у цьому разі",
        "при цьому",
        "розмір",
        "мінімальні ставки",
        "максимальні ставки",
        "на умовах та протягом строку дії",
        "порядок",
        "встановлюється",
    ]


def _default_llm_gap_fill_target_families() -> list[str]:
    return ["appendix_heavy", "treaty_protocol", "law"]


def _default_llm_gap_fill_target_subtypes() -> list[str]:
    return [
        "application_requirement",
        "core_normative_clause",
        "temporal_clause",
        "exception_clause",
        "sanction_clause",
        "approval_bundle",
        "tariff_threshold_row",
        "amendment_bundle",
    ]


@dataclass
class BatchConfig:
    """Immutable configuration for a single Lex pipeline run."""

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
    def references_dir(self) -> Path:
        return self.output_dir / "references"

    @property
    def grounded_spo_dir(self) -> Path:
        return self.output_dir / "spo_grounded"

    @property
    def resolved_references_dir(self) -> Path:
        return self.output_dir / "resolved_references"

    @property
    def domains_dir(self) -> Path:
        return self.output_dir / "domains"

    @property
    def claim_exports_dir(self) -> Path:
        return self.output_dir / "claim_exports"

    @property
    def consumer_manifest_path(self) -> Path:
        return self.output_dir / "publish" / "consumer_readiness.json"

    @property
    def benchmark_report_path(self) -> Path:
        return self.output_dir / "benchmark_report.json"

    @property
    def llm_gate_audit_path(self) -> Path:
        return self.output_dir / "llm_gate_audit.jsonl"

    @property
    def llm_gate_manifest_path(self) -> Path:
        return self.output_dir / "manifests" / "llm_gate.json"

    @property
    def pattern_feedback_queue_path(self) -> Path:
        return self.output_dir / "manifests" / "pattern_feedback_queue.jsonl"

    @property
    def telemetry_path(self) -> Path:
        return self.output_dir / "manifests" / "telemetry.json"

    @property
    def llm_request_log_path(self) -> Path:
        return self.output_dir / "manifests" / "llm_requests.jsonl"

    @property
    def pattern_candidates_dir(self) -> Path:
        return self.output_dir / "patterns" / "ua" / "candidates"

    @property
    def openai_batches_dir(self) -> Path:
        # Kept for backward compatibility with older tests/helpers.
        return self.state_dir / "openai_batches"

    # --- LLM (Gonka, OpenAI-compatible) ---
    gonka_api_key: str = ""
    gonka_api_keys: list[str] = field(default_factory=_default_gonka_api_keys)
    gonka_base_url: str = "https://api.gonkagate.com/v1"
    llm_model: str = "qwen/qwen3-235b-a22b-instruct-2507-fp8"
    llm_temperature: float = 0.1
    gonka_disable_json_mode: bool = False
    max_concurrent_llm: int = 40
    rate_limit_rps: float = 9.0
    max_retries: int = 7
    max_concurrent_llm_global: int | None = None
    spo_connect_timeout_seconds: int = 15
    spo_read_timeout_seconds: int = 120
    spo_total_timeout_seconds: int = 180
    spo_provider_watchdog_seconds: int = 0
    spo_retryable_followup_passes: int = 1
    spo_retryable_followup_delay_seconds: float = 5.0
    spo_retryable_followup_worker_scale: float = 0.5
    spo_retryable_followup_dispatch_rps_scale: float = 0.5
    spo_retryable_followup_client_rate_scale: float = 0.5
    spo_retryable_followup_client_concurrency_scale: float = 0.5
    spo_request_log_enabled: bool = True
    spo_rate_warmup_seconds: float = 45.0
    spo_rate_warmup_start_scale: float = 3.0
    spo_adaptive_rate_enabled: bool = True
    spo_adaptive_rate_recovery_factor: float = 0.97
    spo_adaptive_rate_penalty_multiplier: float = 1.35
    spo_adaptive_rate_max_scale: float = 8.0

    # --- Local embeddings (sentence-transformers) ---
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_dimension: int = 1024
    embedding_batch_size: int = 24
    embedding_device: str = "mps"
    embedding_chunk_size: int = 2000
    embedding_pause_seconds: float = 0.5
    embedding_fp16: bool = True
    embedding_incremental: bool = False

    # --- Filtering ---
    status_filter: frozenset[str] | None = None
    type_filter: frozenset[str] | None = None
    doc_id_filter: frozenset[str] | None = None

    # --- Pipeline control ---
    stages: frozenset[str] = field(default_factory=lambda: ALL_STAGES)
    resume: bool = False
    manifest_is_pre_sharded: bool = False

    # --- Pipeline limits ---
    max_docs: int | None = None  # stop after processing this many NEW docs (None = unlimited)

    # --- Hardware tuning (MacBook Air M2, 16 GB) ---
    xml_parse_chunk: int = 5000
    structure_workers: int = 4
    structure_enable_paragraphs: bool = True
    structure_fallback_chunk_chars: int = 1800
    structure_fallback_chunk_overlap: int = 200
    spo_batch_docs: int = 500
    spo_task_batch_size: int = 1000
    spo_request_batch_size: int = 5
    spo_request_batch_chars: int | None = 6000
    spo_adaptive_batch_downshift_enabled: bool = True
    spo_adaptive_batch_soft_chars_share: float = 0.80
    spo_group_timeout_seconds: float | None = None
    spo_timeout_retry_enabled: bool = True
    spo_timeout_retry_batch_size: int = 1
    spo_timeout_retry_chars: int | None = 3000
    spo_max_provisions_per_doc: int | None = None
    spo_extract_mode: str = "light"
    spo_skip_trivial: bool = True
    spo_verify_mode: str = "code"
    graph_insert_batch: int = 10_000
    jurisdiction: str = "UA"
    pattern_feedback_enabled: bool = True

    # --- LLM gating ---
    llm_gate_enabled: bool = True
    llm_gate_mode: str = "balanced"  # off|balanced|aggressive
    llm_gate_threshold: float = 0.55
    llm_gate_max_share: float = 0.35
    llm_gate_min_score_force_llm: float = 0.75
    llm_gate_audit_sample_rate: float = 0.02
    llm_gate_audit_max_miss_rate_pct: float = 3.0
    llm_gate_auto_conf_threshold: float = 0.85
    llm_gate_circuit_breaker_enabled: bool = True
    llm_gap_fill_mode: str = "off"  # off|narrow|wide
    llm_gap_fill_enabled: bool = False
    llm_gap_fill_max_share: float = 0.80
    llm_gap_fill_force_empty_spo: bool = True
    llm_gap_fill_force_single_fact_tails: bool = True
    llm_gap_fill_tail_markers: list[str] = field(default_factory=_default_llm_gap_fill_tail_markers)
    llm_gap_fill_target_families: list[str] = field(
        default_factory=_default_llm_gap_fill_target_families
    )
    llm_gap_fill_target_subtypes: list[str] = field(
        default_factory=_default_llm_gap_fill_target_subtypes
    )

    # --- LLM response cache ---
    spo_cache_enabled: bool = True
    spo_cache_path: Path | None = None  # defaults to output_dir / "spo_cache.sqlite"

    # --- Deterministic enrichments ---
    extract_references_enabled: bool = True
    extract_domains_enabled: bool = True
    publish_require_embeddings: bool = True
    export_claims_to_cas: bool = False
    cas_root: Path | None = None
    fact_log_root: Path | None = None

    # --- Quality gates ---
    quality_gates_enabled: bool = True
    quality_fail_on_critical: bool = False
    quality_structure_gate_enabled: bool = True
    quality_structure_fail_fast: bool = True
    quality_max_full_only_docs_pct: float = 25.0
    quality_max_empty_statement_rows_pct: float = 15.0
    quality_max_oov_action_rate_pct: float = 1.0
    quality_max_missing_quote_rate_pct: float = 5.0
    quality_max_duplicate_anchor_rate_pct: float = 0.1
    quality_max_audit_miss_rate_pct: float = 15.0
    quality_max_hallucination_rate_pct: float = 3.0
    quality_max_unresolved_contradictions: int = 10
    quality_max_low_confidence_normative_pct: float = 15.0
    quality_max_current_like_temporal_unknown_pct: float = 25.0
    quality_max_temporal_interval_inversions: int = 0
    quality_min_reference_resolution_coverage_pct: float = 80.0
    quality_min_amendment_extraction_coverage_pct: float = 60.0
    quality_min_amendment_target_resolution_pct: float = 70.0
    quality_min_llm_saved_pct: float = 30.0
    quality_min_audit_samples_for_rate: int = 10
    quality_min_provision_docs_for_doc_rate: int = 25
    quality_min_spo_rows_for_row_rate: int = 50
    quality_min_statements_for_statement_rate: int = 100
    quality_min_reference_rows_for_rate: int = 10

    def is_doc_in_shard(self, doc_id: str) -> bool:
        """Deterministically assign a document id to one shard."""
        if self.manifest_is_pre_sharded:
            return True
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
        if self.spo_request_batch_size < 1:
            raise ValueError("spo_request_batch_size must be >= 1")
        if self.spo_request_batch_chars is not None and self.spo_request_batch_chars < 500:
            raise ValueError("spo_request_batch_chars must be >= 500 when set")
        if not (0.5 <= self.spo_adaptive_batch_soft_chars_share <= 1.0):
            raise ValueError("spo_adaptive_batch_soft_chars_share must be in range [0.5, 1.0]")
        if self.spo_group_timeout_seconds is not None and self.spo_group_timeout_seconds <= 0:
            raise ValueError("spo_group_timeout_seconds must be > 0 when set")
        if self.spo_connect_timeout_seconds < 1:
            raise ValueError("spo_connect_timeout_seconds must be >= 1")
        if self.spo_read_timeout_seconds < 1:
            raise ValueError("spo_read_timeout_seconds must be >= 1")
        if self.spo_total_timeout_seconds < self.spo_connect_timeout_seconds:
            raise ValueError("spo_total_timeout_seconds must be >= spo_connect_timeout_seconds")
        if self.spo_total_timeout_seconds < self.spo_read_timeout_seconds:
            raise ValueError("spo_total_timeout_seconds must be >= spo_read_timeout_seconds")
        if self.spo_provider_watchdog_seconds < -1:
            raise ValueError("spo_provider_watchdog_seconds must be >= -1")
        if self.spo_timeout_retry_batch_size < 1:
            raise ValueError("spo_timeout_retry_batch_size must be >= 1")
        if self.spo_timeout_retry_chars is not None and self.spo_timeout_retry_chars < 500:
            raise ValueError("spo_timeout_retry_chars must be >= 500 when set")
        if self.spo_retryable_followup_passes < 0:
            raise ValueError("spo_retryable_followup_passes must be >= 0")
        if self.spo_retryable_followup_delay_seconds < 0.0:
            raise ValueError("spo_retryable_followup_delay_seconds must be >= 0")
        if not (0.05 <= self.spo_retryable_followup_worker_scale <= 1.0):
            raise ValueError("spo_retryable_followup_worker_scale must be in range [0.05, 1.0]")
        if not (0.05 <= self.spo_retryable_followup_dispatch_rps_scale <= 1.0):
            raise ValueError(
                "spo_retryable_followup_dispatch_rps_scale must be in range [0.05, 1.0]"
            )
        if not (0.05 <= self.spo_retryable_followup_client_rate_scale <= 1.0):
            raise ValueError(
                "spo_retryable_followup_client_rate_scale must be in range [0.05, 1.0]"
            )
        if not (0.05 <= self.spo_retryable_followup_client_concurrency_scale <= 1.0):
            raise ValueError(
                "spo_retryable_followup_client_concurrency_scale must be in range [0.05, 1.0]"
            )
        if self.spo_rate_warmup_seconds < 0.0:
            raise ValueError("spo_rate_warmup_seconds must be >= 0")
        if self.spo_rate_warmup_start_scale < 1.0:
            raise ValueError("spo_rate_warmup_start_scale must be >= 1")
        if not (0.5 <= self.spo_adaptive_rate_recovery_factor <= 1.0):
            raise ValueError("spo_adaptive_rate_recovery_factor must be in range [0.5, 1.0]")
        if self.spo_adaptive_rate_penalty_multiplier < 1.0:
            raise ValueError("spo_adaptive_rate_penalty_multiplier must be >= 1")
        if self.spo_adaptive_rate_max_scale < 1.0:
            raise ValueError("spo_adaptive_rate_max_scale must be >= 1")
        if self.spo_extract_mode not in {"light", "full"}:
            raise ValueError("spo_extract_mode must be one of: light, full")
        if self.spo_verify_mode not in {"llm", "code"}:
            raise ValueError("spo_verify_mode must be one of: llm, code")
        if self.llm_gate_mode not in {"off", "balanced", "aggressive"}:
            raise ValueError("llm_gate_mode must be one of: off, balanced, aggressive")
        if self.llm_gap_fill_mode not in {"off", "narrow", "wide"}:
            raise ValueError("llm_gap_fill_mode must be one of: off, narrow, wide")
        if not (0.0 <= self.llm_gate_threshold <= 1.0):
            raise ValueError("llm_gate_threshold must be in range [0, 1]")
        if not (0.0 <= self.llm_gate_max_share <= 1.0):
            raise ValueError("llm_gate_max_share must be in range [0, 1]")
        if not (0.0 <= self.llm_gap_fill_max_share <= 1.0):
            raise ValueError("llm_gap_fill_max_share must be in range [0, 1]")
        if not (0.0 <= self.llm_gate_min_score_force_llm <= 1.0):
            raise ValueError("llm_gate_min_score_force_llm must be in range [0, 1]")
        if not (0.0 <= self.llm_gate_audit_sample_rate <= 1.0):
            raise ValueError("llm_gate_audit_sample_rate must be in range [0, 1]")
        if self.llm_gate_audit_max_miss_rate_pct < 0.0:
            raise ValueError("llm_gate_audit_max_miss_rate_pct must be >= 0")
        if (
            self.quality_min_reference_resolution_coverage_pct < 0.0
            or self.quality_min_reference_resolution_coverage_pct > 100.0
        ):
            raise ValueError(
                "quality_min_reference_resolution_coverage_pct must be in range [0, 100]"
            )
        if (
            self.quality_min_amendment_extraction_coverage_pct < 0.0
            or self.quality_min_amendment_extraction_coverage_pct > 100.0
        ):
            raise ValueError(
                "quality_min_amendment_extraction_coverage_pct must be in range [0, 100]"
            )
        if (
            self.quality_min_amendment_target_resolution_pct < 0.0
            or self.quality_min_amendment_target_resolution_pct > 100.0
        ):
            raise ValueError(
                "quality_min_amendment_target_resolution_pct must be in range [0, 100]"
            )
        if (
            self.quality_max_current_like_temporal_unknown_pct < 0.0
            or self.quality_max_current_like_temporal_unknown_pct > 100.0
        ):
            raise ValueError(
                "quality_max_current_like_temporal_unknown_pct must be in range [0, 100]"
            )
        if self.quality_max_temporal_interval_inversions < 0:
            raise ValueError("quality_max_temporal_interval_inversions must be >= 0")
        if self.quality_min_reference_rows_for_rate < 0:
            raise ValueError("quality_min_reference_rows_for_rate must be >= 0")
        if not (0.0 <= self.llm_gate_auto_conf_threshold <= 1.0):
            raise ValueError("llm_gate_auto_conf_threshold must be in range [0, 1]")
        if self.quality_min_provision_docs_for_doc_rate < 0:
            raise ValueError("quality_min_provision_docs_for_doc_rate must be >= 0")
        if self.quality_min_audit_samples_for_rate < 0:
            raise ValueError("quality_min_audit_samples_for_rate must be >= 0")
        if self.quality_min_spo_rows_for_row_rate < 0:
            raise ValueError("quality_min_spo_rows_for_row_rate must be >= 0")
        if self.quality_min_statements_for_statement_rate < 0:
            raise ValueError("quality_min_statements_for_statement_rate must be >= 0")

        if self.sharded and {"graph", "export_claims", "publish_bundle"} & set(self.stages):
            raise ValueError(
                "In sharded mode run only parse/structure/spo/ground_quotes/resolve_refs stages. "
                "Run graph/export_claims/publish_bundle as separate single-process finalize passes."
            )

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.spo_results_dir.mkdir(parents=True, exist_ok=True)
        self.provisions_dir.mkdir(parents=True, exist_ok=True)
        self.references_dir.mkdir(parents=True, exist_ok=True)
        self.grounded_spo_dir.mkdir(parents=True, exist_ok=True)
        self.resolved_references_dir.mkdir(parents=True, exist_ok=True)
        self.domains_dir.mkdir(parents=True, exist_ok=True)
        self.claim_exports_dir.mkdir(parents=True, exist_ok=True)
        self.openai_batches_dir.mkdir(parents=True, exist_ok=True)
        self.pattern_candidates_dir.mkdir(parents=True, exist_ok=True)
        self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        self.llm_request_log_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.gonka_api_keys:
            self.gonka_api_keys = _default_gonka_api_keys()

        explicit_key = str(self.gonka_api_key or "").strip()
        if explicit_key:
            if explicit_key not in self.gonka_api_keys:
                self.gonka_api_keys = [explicit_key, *self.gonka_api_keys]
            else:
                self.gonka_api_keys = [
                    explicit_key,
                    *[k for k in self.gonka_api_keys if k != explicit_key],
                ]
        self.gonka_api_key = explicit_key or (self.gonka_api_keys[0] if self.gonka_api_keys else "")
        self.llm_gap_fill_enabled = bool(
            self.llm_gap_fill_enabled and self.llm_gap_fill_mode != "off"
        )
        self.llm_gap_fill_tail_markers = [
            marker.strip() for marker in self.llm_gap_fill_tail_markers if str(marker).strip()
        ]
        self.llm_gap_fill_target_families = [
            family.strip() for family in self.llm_gap_fill_target_families if str(family).strip()
        ]
        self.llm_gap_fill_target_subtypes = [
            subtype.strip() for subtype in self.llm_gap_fill_target_subtypes if str(subtype).strip()
        ]

        if self.export_claims_to_cas:
            if self.cas_root is None:
                env_root = os.environ.get("POLISYOS_CAS_ROOT")
                if env_root:
                    self.cas_root = Path(env_root)
            if self.fact_log_root is None:
                self.fact_log_root = self.output_dir / "fact_log"
            if self.cas_root is None:
                raise ValueError("export_claims_to_cas requires cas_root or POLISYOS_CAS_ROOT")
            self.cas_root.mkdir(parents=True, exist_ok=True)
            self.fact_log_root.mkdir(parents=True, exist_ok=True)

        unknown = set(self.stages) - ALL_STAGES
        if unknown:
            raise ValueError(f"Unknown stages: {unknown}. Valid: {sorted(ALL_STAGES)}")
