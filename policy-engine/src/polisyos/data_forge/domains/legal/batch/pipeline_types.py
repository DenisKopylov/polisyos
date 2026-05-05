"""Shared dataclasses for the Lex batch pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PipelineStats:
    """Pipeline stats public type."""

    total_docs: int = 0
    total_provisions: int = 0
    total_spo: int = 0
    entities: int = 0
    facts: int = 0
    provisions_embedded: int = 0
    elapsed_seconds: float = 0.0
    stage_times: dict[str, float] = field(default_factory=dict)
    quality_passed: bool | None = None
    quality_gate_passed: bool | None = None
    qc_passed: bool | None = None
    release_passed: bool | None = None
    quality_report: dict[str, float] = field(default_factory=dict)
    quality_failed_checks: list[str] = field(default_factory=list)
    quality_gate_failed_checks: list[str] = field(default_factory=list)
    quality_hotspot_failed_checks: list[str] = field(default_factory=list)
    quality_warning_failed_checks: list[str] = field(default_factory=list)
    quality_skipped_checks: list[str] = field(default_factory=list)
    qc_failed_checks: list[str] = field(default_factory=list)
    release_failed_checks: list[str] = field(default_factory=list)
    llm_gate_metrics: dict[str, float | int] = field(default_factory=dict)
    grounded_statements: int = 0
    normative_statements: int = 0
    candidate_facts: int = 0
    grounded_facts: int = 0
    normative_facts: int = 0
    reference_edges: int = 0
    exported_claims: int = 0
    exported_claim_sets: int = 0
    benchmark_passed: bool | None = None
    benchmark_metrics: dict[str, float | int] = field(default_factory=dict)
    benchmark_failed_checks: list[str] = field(default_factory=list)
    published_bundle: bool = False


@dataclass
class LLMGateStats:
    """Runtime counters for LLM gating decisions."""

    provisions_seen: int = 0
    skipped_total: int = 0
    auto_by_code_total: int = 0
    llm_candidate_total: int = 0
    llm_sent_total: int = 0
    llm_primary_sent_total: int = 0
    llm_gap_fill_sent_total: int = 0
    llm_gap_fill_added_statements_total: int = 0
    llm_gap_fill_timeout_fallback_total: int = 0
    llm_gap_fill_empty_responses_total: int = 0
    llm_gap_fill_null_yield_total: int = 0
    llm_gap_fill_null_yield_persisted_empty_total: int = 0
    llm_gap_fill_null_yield_preserved_baseline_total: int = 0
    auto_empty_skipped_total: int = 0
    deferred_total: int = 0
    audit_sample_total: int = 0
    audit_miss_total: int = 0
    circuit_breaker_hits: int = 0
    dedup_reused_total: int = 0
    timeout_retry_groups_total: int = 0
    timeout_retry_success_total: int = 0
    timeout_retry_failure_total: int = 0
    retry_followup_passes_run: int = 0
    retry_followup_pending_items_total: int = 0
    retry_followup_recovered_items_total: int = 0
    retry_followup_items_exhausted_total: int = 0
    llm_gap_fill_family_counts: dict[str, int] = field(default_factory=dict)
    llm_gap_fill_subtype_counts: dict[str, int] = field(default_factory=dict)
    llm_gap_fill_timeout_family_counts: dict[str, int] = field(default_factory=dict)
    llm_gap_fill_trigger_counts: dict[str, int] = field(default_factory=dict)
    deferred_reason_counts: dict[str, int] = field(default_factory=dict)
    audit_miss_category_counts: dict[str, int] = field(default_factory=dict)

    @property
    def llm_saved_pct(self) -> float:
        if self.llm_candidate_total <= 0:
            return 100.0
        saved = max(0, self.llm_candidate_total - self.llm_sent_total)
        return (saved * 100.0) / self.llm_candidate_total

    @property
    def primary_llm_saved_pct(self) -> float:
        if self.llm_candidate_total <= 0:
            return 100.0
        saved = max(0, self.llm_candidate_total - self.llm_primary_sent_total)
        return (saved * 100.0) / self.llm_candidate_total

    @property
    def audit_miss_rate_pct(self) -> float:
        if self.audit_sample_total <= 0:
            return 0.0
        return (self.audit_miss_total * 100.0) / self.audit_sample_total

    @property
    def gap_fill_gain_rate_pct(self) -> float:
        if self.llm_gap_fill_sent_total <= 0:
            return 0.0
        return (self.llm_gap_fill_added_statements_total * 100.0) / self.llm_gap_fill_sent_total

    @property
    def gap_fill_null_yield_pct(self) -> float:
        if self.llm_gap_fill_sent_total <= 0:
            return 0.0
        return (self.llm_gap_fill_null_yield_total * 100.0) / self.llm_gap_fill_sent_total


@dataclass
class StructureQualityStats:
    """Structure quality stats public type."""

    provision_docs_total: int = 0
    full_only_docs: int = 0
    duplicate_anchor_docs: int = 0


@dataclass(frozen=True)
class SPOLLMSettings:
    """SPOLLM settings public type."""

    task_batch_size: int
    request_batch_size: int
    request_batch_chars: int | None
    group_timeout_seconds: float | None


@dataclass
class SPODocRoutingPlan:
    """SPO doc routing plan data model."""

    reasoning_spans: list
    llm_allowed: bool
    llm_settings: SPOLLMSettings
    flags: tuple[str, ...] = ()


@dataclass
class StratifiedAuditSampler:
    """Stratified audit sampler implementation."""

    base_rate: float
    max_forced_samples: int = 32
    sampled_counts: dict[str, int] = field(default_factory=dict)
    forced_samples_used: int = 0

    @staticmethod
    def _key(*, family: str, subtype: str, route_class: str) -> str:
        return f"{family or 'other'}|{subtype or 'unknown'}|{route_class or 'unknown'}"

    def should_force_sample(
        self,
        *,
        family: str,
        subtype: str,
        route_class: str,
        llm_available: bool,
    ) -> bool:
        if not llm_available or self.base_rate <= 0.0:
            return False
        if family not in {"appendix_heavy", "law", "treaty_protocol", "decree_resolution"}:
            return False
        if self.forced_samples_used >= self.max_forced_samples:
            return False
        key = self._key(family=family, subtype=subtype, route_class=route_class)
        return self.sampled_counts.get(key, 0) < 1

    def register_sample(
        self,
        *,
        family: str,
        subtype: str,
        route_class: str,
        forced: bool,
    ) -> None:
        key = self._key(family=family, subtype=subtype, route_class=route_class)
        self.sampled_counts[key] = self.sampled_counts.get(key, 0) + 1
        if forced:
            self.forced_samples_used += 1


__all__ = [
    "LLMGateStats",
    "PipelineStats",
    "SPODocRoutingPlan",
    "SPOLLMSettings",
    "StratifiedAuditSampler",
    "StructureQualityStats",
]
