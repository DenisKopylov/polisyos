"""Configuration for staged academic knowledge pipeline."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from polisyos.data_forge.kernel.io import ensure_dirs, snapshot_component_dir

ALL_STAGES = frozenset(
    {
        "topic_select",
        "demand_harvest",
        "doc_normalize",
        "harvest",
        "parse",
        "resolve_extract",
        "claim_extract",
        "context_extract",
        "mechanism_extract",
        "resolve_finalize",
        "numeric_extract",
        "merge_dedup",
        "claim_adjudicate",
        "conflict_resolve",
        "graph_load",
        "edge_synthesize",
        "graph_index",
        "transport_score",
        "benchmark",
        "embed",
        "qc",
        "publish",
    }
)

RUN2_PRIORITY_DOMAIN_SUBBLOCKS: tuple[str, ...] = (
    "economy/finance/business",
    "health/healthcare",
    "climate/energy/environment",
    "agriculture/food/rural",
    "urban/housing/transport",
    "governance/law/regulation",
    "labor/social development",
    "education/human capital",
    "technology/industry/digital",
)

RUN2_PRIORITY_CONTEXT_SUBBLOCKS: tuple[str, ...] = (
    "country/region profiles",
    "comparative area studies",
    "historical/political context",
)

DEFAULT_TOPICS_DIR = (
    Path(__file__).resolve().parents[2] / "catalog" / "fixtures" / "relevant_topics_domain_files"
)


def _default_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


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
    target_per_topic: int = 500
    selected_unique_budget: int = 330_000
    usable_fulltext_target: int = 180_000
    policy_core_quota_share: float = 0.25
    priority_domain_quota_share: float = 0.55
    priority_context_quota_share: float = 0.15
    adaptive_reserve_quota_share: float = 0.05
    priority_domain_subblocks: tuple[str, ...] = RUN2_PRIORITY_DOMAIN_SUBBLOCKS
    priority_context_subblocks: tuple[str, ...] = RUN2_PRIORITY_CONTEXT_SUBBLOCKS
    demand_backlog_path: Path | None = None
    demand_backlog_boost: float = 0.20
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
    gonka_api_keys: list[str] = field(default_factory=_default_gonka_api_keys)
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
    article_target_fulltext_per_topic: int = 50
    article_prefetch_candidates_per_topic: int = 150
    article_max_completion_tokens: int = 8192
    article_evidence_bundle_sentence_budget: int = 28
    article_connect_timeout_seconds: int = 15
    article_read_timeout_seconds: int = 120
    article_total_timeout_seconds: int = 150
    article_provider_watchdog_seconds: int = 0
    article_retryable_followup_passes: int = 1
    article_retryable_followup_delay_seconds: float = 5.0
    fulltext_max_concurrent_fetches: int = 24
    fulltext_acquisition_mode: str = "v7_http_metadata"
    fulltext_metadata_resolvers_enabled: bool = True
    fulltext_metadata_resolver_order: tuple[str, ...] = ("unpaywall", "crossref", "semanticscholar")
    fulltext_unpaywall_email: str = ""
    fulltext_semantic_scholar_api_key: str = ""
    fulltext_metadata_timeout_seconds: int = 20
    fulltext_max_candidate_urls_per_work: int = 20
    fulltext_min_usable_chars: int = 1500
    fulltext_min_soft_usable_chars: int = 700
    fulltext_soft_usable_requires_section_cues: bool = True
    fulltext_shared_cache_dir: Path | None = None
    fulltext_cache_ttl_days: int = 30
    fulltext_max_pdf_pages: int = 50
    fulltext_extract_html_tables: bool = True
    doc_infra_enable_pub2tei: bool = True
    doc_infra_enable_grobid: bool = True
    doc_pub2tei_base_url: str = "http://localhost:8074"
    doc_grobid_base_url: str = "http://localhost:8070"
    doc_infra_timeout_seconds: int = 45
    doc_infra_precedence: tuple[str, ...] = ("publisher_xml", "pdf", "text")
    stream_doc_normalize_to_resolve_extract: bool = False
    stream_doc_ready_poll_seconds: float = 2.0
    provider_circuit_breaker_failures: int = 5
    provider_circuit_breaker_reset_seconds: int = 60

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

    # Track B/C extraction (opt-in)
    track_b_enabled: bool = False
    track_c_enabled: bool = False
    paper_classification_model: str = ""
    track_b_extraction_model: str = ""
    track_c_extraction_model: str = ""
    numeric_precision_mode: str = "high_precision"
    claim_adjudication_passes: int = 3
    extraction_lane: str = "all"
    transport_target_context_id: str = ""
    transport_target_country_codes: tuple[str, ...] = ("UA",)
    transport_target_time_period: str = ""
    benchmark_suite_path_override: Path | None = None

    # Cross-run timeout retry
    retry_timeout_articles: bool = True
    retry_max_attempts: int = 2
    retry_timeout_seconds: int = 30
    retry_max_concurrent_llm: int = 10

    # Demand-first harvesting
    demand_harvest_enabled: bool = False
    demand_harvest_max_works_per_need: int = 50
    demand_harvest_min_priority_weight: float = 0.5

    # Targeted multi-pass extraction
    targeted_extraction_enabled: bool = False
    targeted_extraction_max_papers: int = 200

    # Table extraction (optional dependency — marker-pdf)
    table_extraction_enabled: bool = False
    table_extraction_backend: str = "auto"  # "auto" | "marker" | "off"

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
    def fulltext_resolved_path(self) -> Path:
        return self.component_dir / "fulltext_resolved.jsonl"

    @property
    def doc_tei_dir(self) -> Path:
        return self.component_dir / "doc_tei"

    @property
    def doc_json_path(self) -> Path:
        return self.component_dir / "doc_json.json"

    @property
    def doc_substrate_path(self) -> Path:
        return self.component_dir / "doc_substrate.jsonl"

    @property
    def doc_sentences_path(self) -> Path:
        return self.component_dir / "sentences.jsonl"

    @property
    def doc_sections_path(self) -> Path:
        return self.component_dir / "sections.jsonl"

    @property
    def doc_references_path(self) -> Path:
        return self.component_dir / "references.jsonl"

    @property
    def doc_tables_path(self) -> Path:
        return self.component_dir / "tables.jsonl"

    @property
    def doc_figures_path(self) -> Path:
        return self.component_dir / "figures.jsonl"

    @property
    def doc_appendix_blocks_path(self) -> Path:
        return self.component_dir / "appendix_blocks.jsonl"

    @property
    def doc_routing_path(self) -> Path:
        return self.component_dir / "doc_routing.jsonl"

    @property
    def doc_ready_queue_path(self) -> Path:
        return self.component_dir / "doc_ready_queue.jsonl"

    @property
    def resolve_extract_progress_path(self) -> Path:
        return self.component_dir / "resolve_extract_progress.json"

    @property
    def resolve_extract_results_path(self) -> Path:
        return self.component_dir / "resolve_extract_results.jsonl"

    @property
    def resolve_extract_attempts_path(self) -> Path:
        return self.resolve_extract_results_path

    @property
    def resolve_extract_final_results_path(self) -> Path:
        return self.component_dir / "resolve_extract_final_results.jsonl"

    @property
    def resolve_extract_final_works_path(self) -> Path:
        return self.extracted_dir / "resolve_finalize.jsonl"

    @property
    def resolve_extract_errors_path(self) -> Path:
        return self.component_dir / "resolve_extract_errors.jsonl"

    @property
    def fulltext_fetch_log_path(self) -> Path:
        return self.component_dir / "fulltext_fetch_log.jsonl"

    @property
    def fulltext_metadata_cache_path(self) -> Path:
        return self.component_dir / "fulltext_metadata_cache.jsonl"

    @property
    def llm_request_log_path(self) -> Path:
        return self.component_dir / "llm_request_log.jsonl"

    @property
    def raw_claim_candidates_path(self) -> Path:
        return self.component_dir / "raw_claim_candidates.jsonl"

    @property
    def published_claims_path(self) -> Path:
        return self.component_dir / "published_claims.jsonl"

    @property
    def raw_claim_candidates_final_path(self) -> Path:
        return self.component_dir / "raw_claim_candidates_final.jsonl"

    @property
    def published_claims_final_path(self) -> Path:
        return self.component_dir / "published_claims_final.jsonl"

    @property
    def context_attributes_path(self) -> Path:
        return self.component_dir / "context_attributes.jsonl"

    @property
    def moderation_edges_path(self) -> Path:
        return self.component_dir / "moderation_edges.jsonl"

    @property
    def context_attributes_clean_path(self) -> Path:
        return self.component_dir / "context_attributes_clean.jsonl"

    @property
    def moderation_edges_clean_path(self) -> Path:
        return self.component_dir / "moderation_edges_clean.jsonl"

    @property
    def simulation_ready_numeric_path(self) -> Path:
        return self.component_dir / "simulation_ready_numeric_estimates.jsonl"

    @property
    def numeric_estimates_raw_path(self) -> Path:
        return self.component_dir / "numeric_estimates_raw.jsonl"

    @property
    def numeric_estimates_curated_path(self) -> Path:
        return self.component_dir / "numeric_estimates_curated.jsonl"

    @property
    def claim_adjudication_passes_path(self) -> Path:
        return self.component_dir / "claim_adjudication_passes.jsonl"

    @property
    def claim_adjudications_path(self) -> Path:
        return self.component_dir / "claim_adjudications.jsonl"

    @property
    def claim_consensus_report_path(self) -> Path:
        return self.component_dir / "claim_consensus_report.json"

    @property
    def claim_sets_path(self) -> Path:
        return self.component_dir / "claim_sets.jsonl"

    @property
    def conflict_sets_path(self) -> Path:
        return self.component_dir / "conflict_sets.jsonl"

    @property
    def conflict_resolutions_path(self) -> Path:
        return self.component_dir / "conflict_resolutions.jsonl"

    @property
    def canonical_review_queue_path(self) -> Path:
        return self.component_dir / "canonical_review_queue.jsonl"

    @property
    def edge_synthesis_report_path(self) -> Path:
        return self.component_dir / "edge_synthesis_report.json"

    @property
    def benchmark_suite_path(self) -> Path:
        return self.benchmark_suite_path_override or (self.component_dir / "benchmark_suite.json")

    @property
    def benchmark_report_path(self) -> Path:
        return self.component_dir / "benchmark_report.json"

    @property
    def runtime_demand_backlog_path(self) -> Path:
        return self.component_dir / "runtime_demand_backlog.jsonl"

    @property
    def timeout_retry_queue_path(self) -> Path:
        return self.component_dir / "timeout_retry_queue.jsonl"

    @property
    def demand_harvest_works_path(self) -> Path:
        return self.component_dir / "demand_harvest_works.jsonl"

    @property
    def readiness_report_path(self) -> Path:
        return self.component_dir / "publish" / "academic_pipeline_readiness.json"

    @property
    def transport_scores_path(self) -> Path:
        return self.component_dir / "transport_scores.jsonl"

    @property
    def resolved_fulltext_cache_path(self) -> Path:
        if self.fulltext_shared_cache_dir is not None:
            return self.fulltext_shared_cache_dir / "resolved_fulltext_cache.jsonl"
        return self.component_dir / "resolved_fulltext_cache.jsonl"

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

        unknown = set(self.stages) - ALL_STAGES
        if unknown:
            raise ValueError(f"Unknown stages: {sorted(unknown)}")

        if self.target_per_topic < 1:
            raise ValueError("target_per_topic must be >= 1")
        if self.selected_unique_budget < 1:
            raise ValueError("selected_unique_budget must be >= 1")
        if self.usable_fulltext_target < 1:
            raise ValueError("usable_fulltext_target must be >= 1")
        if not (0.0 <= float(self.demand_backlog_boost) <= 1.0):
            raise ValueError("demand_backlog_boost must be in range [0, 1]")
        if self.claim_adjudication_passes < 1:
            raise ValueError("claim_adjudication_passes must be >= 1")
        if self.extraction_lane not in {"all", "claim", "context", "mechanism"}:
            raise ValueError("extraction_lane must be one of: all, claim, context, mechanism")
        if self.fulltext_acquisition_mode not in {"v3_legacy", "v7_http_metadata"}:
            raise ValueError(
                "fulltext_acquisition_mode must be one of: v3_legacy, v7_http_metadata"
            )
        if self.numeric_precision_mode not in {"off", "balanced", "high_precision"}:
            raise ValueError("numeric_precision_mode must be one of: off, balanced, high_precision")
        if self.fulltext_metadata_timeout_seconds < 1:
            raise ValueError("fulltext_metadata_timeout_seconds must be >= 1")
        if self.article_retryable_followup_passes < 0:
            raise ValueError("article_retryable_followup_passes must be >= 0")
        if self.article_retryable_followup_delay_seconds < 0:
            raise ValueError("article_retryable_followup_delay_seconds must be >= 0")
        if self.article_provider_watchdog_seconds < -1:
            raise ValueError("article_provider_watchdog_seconds must be >= -1")
        if not self.fulltext_metadata_resolver_order:
            raise ValueError("fulltext_metadata_resolver_order must not be empty")
        if self.fulltext_max_candidate_urls_per_work < 1:
            raise ValueError("fulltext_max_candidate_urls_per_work must be >= 1")
        if self.fulltext_min_usable_chars < 1:
            raise ValueError("fulltext_min_usable_chars must be >= 1")
        if self.fulltext_min_soft_usable_chars < 1:
            raise ValueError("fulltext_min_soft_usable_chars must be >= 1")
        if self.fulltext_min_soft_usable_chars > self.fulltext_min_usable_chars:
            raise ValueError("fulltext_min_soft_usable_chars must be <= fulltext_min_usable_chars")
        if self.fulltext_cache_ttl_days < 1:
            raise ValueError("fulltext_cache_ttl_days must be >= 1")
        if self.doc_infra_timeout_seconds < 1:
            raise ValueError("doc_infra_timeout_seconds must be >= 1")
        if not self.doc_infra_precedence:
            raise ValueError("doc_infra_precedence must not be empty")
        if self.stream_doc_ready_poll_seconds <= 0:
            raise ValueError("stream_doc_ready_poll_seconds must be > 0")

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
        quota_sum = (
            float(self.policy_core_quota_share)
            + float(self.priority_domain_quota_share)
            + float(self.priority_context_quota_share)
            + float(self.adaptive_reserve_quota_share)
        )
        if abs(quota_sum - 1.0) > 0.001:
            raise ValueError("selection quota shares must sum to 1.0")

        if self.topics_dir is None:
            self.topics_dir = Path(
                os.environ.get(
                    "POLISYOS_TOPICS_DIR",
                    str(DEFAULT_TOPICS_DIR),
                )
            )
        if self.fulltext_shared_cache_dir is not None:
            self.fulltext_shared_cache_dir = Path(self.fulltext_shared_cache_dir)
        else:
            self.fulltext_shared_cache_dir = self.snapshot_root / "_shared_fulltext_cache"
        if self.demand_backlog_path is not None:
            self.demand_backlog_path = Path(self.demand_backlog_path)
        if self.benchmark_suite_path_override is not None:
            self.benchmark_suite_path_override = Path(self.benchmark_suite_path_override)

        ensure_dirs(
            self.component_dir,
            self.raw_dir,
            self.parsed_dir,
            self.extracted_dir,
            self.merged_dir,
            self.topic_selection_dir,
            self.graph_dir,
            self.manifests_dir,
            self.doc_tei_dir,
            self.publish_manifest_path.parent,
            self.ingest_errors_path.parent,
        )
        if self.fulltext_shared_cache_dir is not None:
            ensure_dirs(self.fulltext_shared_cache_dir)

        if not self.openalex_email:
            self.openalex_email = os.environ.get("OPENALEX_EMAIL", "")
        if not self.gonka_api_key:
            self.gonka_api_key = os.environ.get("GONKA_API_KEY", "")
        if not self.fulltext_unpaywall_email:
            self.fulltext_unpaywall_email = (
                os.environ.get("UNPAYWALL_EMAIL", "") or self.openalex_email
            )
        if not self.fulltext_semantic_scholar_api_key:
            self.fulltext_semantic_scholar_api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
        if not self.doc_pub2tei_base_url:
            self.doc_pub2tei_base_url = (
                os.environ.get("POLISYOS_PUB2TEI_BASE_URL", "")
                or os.environ.get("PUB2TEI_BASE_URL", "")
                or "http://localhost:8074"
            )
        if not self.doc_grobid_base_url:
            self.doc_grobid_base_url = (
                os.environ.get("POLISYOS_GROBID_BASE_URL", "")
                or os.environ.get("GROBID_BASE_URL", "")
                or "http://localhost:8070"
            )
