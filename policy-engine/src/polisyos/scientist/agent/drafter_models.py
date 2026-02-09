"""Shared models/config for drafter implementations."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.scientist.agent.protocols import DraftResult


def _as_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class FindingSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingCategory(str, Enum):
    SIDE_EFFECT = "side_effect"
    MISSING_GROUP = "missing_group"
    BUDGET_VIOLATION = "budget_violation"
    CONSTRAINT_CONFLICT = "constraint_conflict"
    PARAMETER_ERROR = "parameter_error"
    TARGET_OVERLAP = "target_overlap"
    EQUITY_CONCERN = "equity_concern"
    FEASIBILITY_ISSUE = "feasibility_issue"
    OTHER = "other"


_SEVERITY_ORDER: dict[FindingSeverity, int] = {
    FindingSeverity.LOW: 0,
    FindingSeverity.MEDIUM: 1,
    FindingSeverity.HIGH: 2,
    FindingSeverity.CRITICAL: 3,
}


@dataclass(frozen=True, slots=True)
class PassFinding:
    """One issue discovered by a self-critique pass."""

    finding_id: str
    category: FindingCategory
    severity: FindingSeverity
    description: str
    suggested_fix: str = ""
    affected_intervention: str | None = None
    anchor: str = "none"
    source_pass: str = ""

    def as_memory_dict(self) -> dict[str, str]:
        return {
            "category": self.category.value,
            "severity": self.severity.value,
            "description": self.description,
            "suggested_fix": self.suggested_fix,
            "affected_intervention": self.affected_intervention or "",
            "anchor": self.anchor,
        }


@dataclass(slots=True)
class PassExecution:
    """Execution details for one pass in the multipass pipeline."""

    pass_name: str
    pass_number: int
    executed: bool
    draft: DraftResult | None = None
    skip_reason: str = ""
    findings: list[PassFinding] = field(default_factory=list)
    raw_llm_response: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    parse_ok: bool = True
    confidence_adjustment: float | None = None
    verification_code: str | None = None


class MultiPassConfig(BaseModel):
    """Configuration for the multipass self-critique drafter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_passes: int = Field(default=4, ge=1, le=4)
    early_exit_confidence: float = Field(default=0.90, ge=0.0, le=1.0)
    finding_severity_threshold: FindingSeverity = Field(default=FindingSeverity.MEDIUM)
    budget_limit_usd: float = Field(default=0.20, ge=0.0)
    max_extra_llm_calls: int = Field(default=3, ge=0)
    pass_timeout_s: float = Field(default=30.0, gt=0.0, le=300.0)
    pass_retry_count: int = Field(default=1, ge=0, le=3)
    critique_model: str | None = Field(default=None)
    enable_memory_logging: bool = Field(default=True)
    shadow_mode: bool = Field(default=False)
    rag_enabled: bool = Field(default=False)
    rag_top_k: int = Field(default=3, ge=1, le=10)
    rag_similarity_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    rag_domain_filter: bool = Field(default=True)
    rag_max_few_shot_chars: int = Field(default=6000, ge=400, le=20000)
    rag_freeze_snapshot_per_run: bool = Field(default=True)
    code_verification_enabled: bool = Field(default=False)
    code_verification_timeout_s: float = Field(default=5.0, gt=0.0, le=30.0)
    constitution_enabled: bool = Field(default=True)
    constitution_max_total_rules: int = Field(default=50, ge=1, le=120)
    constitution_max_rules_per_section: int = Field(default=20, ge=1, le=50)
    constitution_max_prompt_chars: int = Field(default=9000, ge=500, le=30000)
    constitution_include_domain_rules: bool = Field(default=True)
    constitution_enable_pitfalls: bool = Field(default=True)
    constitution_pitfall_min_occurrences: int = Field(default=3, ge=1, le=20)

    @field_validator("budget_limit_usd")
    @classmethod
    def _validate_budget(cls, value: float) -> float:
        if value < 0.01:
            raise ValueError("budget_limit_usd must be >= 0.01")
        return value

    @classmethod
    def from_env(cls) -> "MultiPassConfig":
        kwargs: dict[str, Any] = {}
        raw_max_passes = os.getenv("POLISYOS_DRAFTER_MAX_PASSES")
        if raw_max_passes:
            kwargs["max_passes"] = int(raw_max_passes)

        raw_early_exit = os.getenv("POLISYOS_DRAFTER_EARLY_EXIT_CONFIDENCE")
        if raw_early_exit:
            kwargs["early_exit_confidence"] = float(raw_early_exit)

        raw_budget = os.getenv("POLISYOS_DRAFTER_BUDGET_LIMIT_USD")
        if raw_budget:
            kwargs["budget_limit_usd"] = float(raw_budget)

        raw_extra_calls = os.getenv("POLISYOS_DRAFTER_MAX_EXTRA_LLM_CALLS")
        if raw_extra_calls:
            kwargs["max_extra_llm_calls"] = int(raw_extra_calls)

        raw_timeout = os.getenv("POLISYOS_DRAFTER_PASS_TIMEOUT_S")
        if raw_timeout:
            kwargs["pass_timeout_s"] = float(raw_timeout)

        raw_retry = os.getenv("POLISYOS_DRAFTER_PASS_RETRY_COUNT")
        if raw_retry:
            kwargs["pass_retry_count"] = int(raw_retry)

        raw_critique_model = os.getenv("POLISYOS_DRAFTER_CRITIQUE_MODEL")
        if raw_critique_model:
            kwargs["critique_model"] = raw_critique_model.strip()

        raw_memory = os.getenv("POLISYOS_DRAFTER_ENABLE_MEMORY_LOGGING")
        if raw_memory is not None:
            kwargs["enable_memory_logging"] = _as_bool(raw_memory, default=True)

        raw_threshold = os.getenv("POLISYOS_DRAFTER_FINDING_SEVERITY_THRESHOLD")
        if raw_threshold:
            kwargs["finding_severity_threshold"] = FindingSeverity(raw_threshold.strip().lower())

        raw_mode = os.getenv("POLISYOS_DRAFTER_MULTIPASS_MODE")
        if raw_mode:
            kwargs["shadow_mode"] = raw_mode.strip().lower() == "shadow"

        raw_rag_enabled = os.getenv("POLISYOS_RAG_ENABLED")
        if raw_rag_enabled is not None:
            kwargs["rag_enabled"] = _as_bool(raw_rag_enabled, default=False)
        raw_rag_top_k = os.getenv("POLISYOS_RAG_TOP_K")
        if raw_rag_top_k:
            kwargs["rag_top_k"] = int(raw_rag_top_k)
        raw_rag_threshold = os.getenv("POLISYOS_RAG_THRESHOLD")
        if raw_rag_threshold:
            kwargs["rag_similarity_threshold"] = float(raw_rag_threshold)
        raw_rag_domain = os.getenv("POLISYOS_RAG_DOMAIN_FILTER")
        if raw_rag_domain is not None:
            kwargs["rag_domain_filter"] = _as_bool(raw_rag_domain, default=True)
        raw_rag_chars = os.getenv("POLISYOS_RAG_MAX_FEW_SHOT_CHARS")
        if raw_rag_chars:
            kwargs["rag_max_few_shot_chars"] = int(raw_rag_chars)
        raw_rag_freeze = os.getenv("POLISYOS_RAG_FREEZE_SNAPSHOT_PER_RUN")
        if raw_rag_freeze is not None:
            kwargs["rag_freeze_snapshot_per_run"] = _as_bool(raw_rag_freeze, default=True)

        raw_code_verif = os.getenv("POLISYOS_CODE_VERIFICATION_ENABLED")
        if raw_code_verif is not None:
            kwargs["code_verification_enabled"] = _as_bool(raw_code_verif, default=False)
        raw_code_timeout = os.getenv("POLISYOS_CODE_VERIFICATION_TIMEOUT")
        if raw_code_timeout:
            kwargs["code_verification_timeout_s"] = float(raw_code_timeout)

        raw_constitution_enabled = os.getenv("POLISYOS_CONSTITUTION_ENABLED")
        if raw_constitution_enabled is not None:
            kwargs["constitution_enabled"] = _as_bool(raw_constitution_enabled, default=True)
        raw_constitution_max_total_rules = os.getenv("POLISYOS_CONSTITUTION_MAX_TOTAL_RULES")
        if raw_constitution_max_total_rules:
            kwargs["constitution_max_total_rules"] = int(raw_constitution_max_total_rules)
        raw_constitution_max_rules_section = os.getenv(
            "POLISYOS_CONSTITUTION_MAX_RULES_PER_SECTION"
        )
        if raw_constitution_max_rules_section:
            kwargs["constitution_max_rules_per_section"] = int(raw_constitution_max_rules_section)
        raw_constitution_chars = os.getenv("POLISYOS_CONSTITUTION_MAX_PROMPT_CHARS")
        if raw_constitution_chars:
            kwargs["constitution_max_prompt_chars"] = int(raw_constitution_chars)
        raw_constitution_domain = os.getenv("POLISYOS_CONSTITUTION_INCLUDE_DOMAIN_RULES")
        if raw_constitution_domain is not None:
            kwargs["constitution_include_domain_rules"] = _as_bool(
                raw_constitution_domain,
                default=True,
            )
        raw_constitution_pitfalls = os.getenv("POLISYOS_CONSTITUTION_ENABLE_PITFALLS")
        if raw_constitution_pitfalls is not None:
            kwargs["constitution_enable_pitfalls"] = _as_bool(
                raw_constitution_pitfalls,
                default=True,
            )
        raw_constitution_pitfall_threshold = os.getenv(
            "POLISYOS_CONSTITUTION_PITFALL_MIN_OCCURRENCES"
        )
        if raw_constitution_pitfall_threshold:
            kwargs["constitution_pitfall_min_occurrences"] = int(
                raw_constitution_pitfall_threshold
            )

        return cls(**kwargs)


class _FindingPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: str = "other"
    severity: str = "medium"
    description: str
    suggested_fix: str = ""
    affected_intervention: str | None = None
    anchor: str = "none"


class _CritiquePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    findings: list[_FindingPayload] = Field(default_factory=list)
    confidence_adjustment: float | None = None
    verification_code: str | None = None


class _ConsolidationPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    narrative: str = ""
    interventions: list[dict[str, Any]] = Field(default_factory=list)
    rationale: str = ""
    alternatives_considered: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


__all__ = [
    "FindingCategory",
    "FindingSeverity",
    "MultiPassConfig",
    "PassExecution",
    "PassFinding",
    "_ConsolidationPayload",
    "_CritiquePayload",
    "_SEVERITY_ORDER",
]
