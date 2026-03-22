"""Two-stage LLM gate for Lex SPO extraction."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from polisyos.lex.batch.patterns import (
    AMENDMENT_CORE_RE,
    AMBIGUITY_CORE_RE,
    ANNEX_REFERENCE_RE,
    ARTICLE_LABEL_RE,
    BULLET_PREFIX_RE,
    LEGAL_SIGNAL_CORE_RE,
    LIST_ITEM_RE,
    MODALITY_CORE_RE,
    NUMERIC_TOKEN_RE,
    TEMPORAL_CORE_RE,
    TITLE_ACTION_RE,
    TREATY_SIGNAL_RE,
)

if TYPE_CHECKING:
    from polisyos.lex.batch.jurisdictions.protocol import JurisdictionPlugin, NormativeSignalPatterns

_NUMERIC_RE = NUMERIC_TOKEN_RE
_MODALITY_RE = MODALITY_CORE_RE
_AMBIGUITY_RE = AMBIGUITY_CORE_RE
_LEGAL_SIGNAL_RE = LEGAL_SIGNAL_CORE_RE
_AMENDMENT_RE = AMENDMENT_CORE_RE
_TEMPORAL_RE = TEMPORAL_CORE_RE
_TREATY_RE = TREATY_SIGNAL_RE
_TITLE_ACTION_RE = TITLE_ACTION_RE
_ANNEX_REF_RE = ANNEX_REFERENCE_RE
_ARTICLE_LABEL_RE = ARTICLE_LABEL_RE
_BULLET_PREFIX_RE = BULLET_PREFIX_RE


@dataclass(frozen=True)
class GateFeatures:
    """Feature set used by irreducibility scoring."""

    length_chars: int
    numeric_density: float
    modality_hits: int
    reference_density: float
    fallback_chunk: bool
    deterministic_confidence: float
    ambiguity_hits: int
    is_structured_publisher: bool = False
    has_list_structure: bool = False
    legal_signal_hits: int = 0
    amendment_hits: int = 0
    temporal_hits: int = 0
    treaty_hits: int = 0
    annex_reference_hits: int = 0
    approval_context_hits: int = 0
    structural_priority: float = 0.0
    high_value_legal_span: bool = False
    is_fragment_like: bool = False
    law_like_doc: bool = False
    treaty_like_doc: bool = False
    appendix_heavy_doc: bool = False
    legal_unit_subtype: str = ""
    route_class: str = ""
    empty_spo_retry_eligible: bool = False
    audit_miss_prone: bool = False
    reference_bearing: bool = False
    threshold_bearing: bool = False


@dataclass(frozen=True)
class GateDecision:
    """Routing decision for one provision."""

    route: str  # skip|auto|llm|llm_gap_fill|deferred|audit_llm
    score: float
    reason_codes: list[str]


@dataclass
class GateRuntime:
    """Mutable runtime state for circuit breaker."""

    threshold: float
    mode: str
    max_share: float
    audit_max_miss_rate_pct: float
    circuit_breaker_enabled: bool = True
    safe_pass_active: bool = False
    consecutive_audit_failures: int = 0
    circuit_breaker_hits: int = 0

    def register_audit_miss_rate(self, miss_rate_pct: float) -> bool:
        """Update circuit breaker state. Returns True when breaker trips."""
        if not self.circuit_breaker_enabled:
            return False
        if miss_rate_pct > self.audit_max_miss_rate_pct:
            self.consecutive_audit_failures += 1
        else:
            self.consecutive_audit_failures = max(0, self.consecutive_audit_failures - 1)
        # Trip on first failure if miss rate is severely above threshold (>2x),
        # otherwise require 2 consecutive failures.
        trip_threshold = 1 if miss_rate_pct > self.audit_max_miss_rate_pct * 2 else 2
        if self.consecutive_audit_failures < trip_threshold:
            return False
        self.safe_pass_active = True
        self.circuit_breaker_hits += 1
        self.consecutive_audit_failures = 0
        return True

    @property
    def effective_threshold(self) -> float:
        if self.safe_pass_active:
            return max(0.0, self.threshold - 0.35)
        if self.mode == "aggressive":
            return min(1.0, self.threshold + 0.10)
        return self.threshold


_LIST_ITEM_RE = LIST_ITEM_RE

_STRUCTURED_PUBLISHERS = frozenset({
    "кабінет міністрів", "кму", "президент",
    "міністерство", "нацбанк", "національний банк",
})


def _signal_patterns(jurisdiction_plugin: JurisdictionPlugin | None) -> NormativeSignalPatterns | None:
    if jurisdiction_plugin is None:
        return None
    cached = getattr(jurisdiction_plugin, "_cached_normative_signal_patterns", None)
    if cached is None:
        cached = jurisdiction_plugin.normative_signal_patterns()
        try:
            setattr(jurisdiction_plugin, "_cached_normative_signal_patterns", cached)
        except Exception:  # pragma: no cover - defensive for exotic plugin objects
            pass
    return cached


def _count_hits(text: str, *patterns: re.Pattern[str] | None) -> int:
    total = 0
    for pattern in patterns:
        if pattern is None:
            continue
        total += len(pattern.findall(text))
    return total


def build_gate_features(
    *,
    text: str,
    deterministic_confidence: float,
    reference_count: int,
    fallback_chunk: bool,
    publisher: str = "",
    doc_title: str = "",
    citation_label: str = "",
    struct_kind: str = "",
    section_role: str = "",
    doc_type_category: str = "",
    legal_unit_subtype: str = "",
    route_class: str = "",
    empty_spo_retry_eligible: bool = False,
    audit_miss_prone: bool = False,
    reference_bearing: bool = False,
    threshold_bearing: bool = False,
    jurisdiction_plugin: JurisdictionPlugin | None = None,
) -> GateFeatures:
    """Compute routing features from provision text + deterministic signal."""
    stripped_text = text.strip()
    words = max(1, len(text.split()))
    numeric_hits = len(_NUMERIC_RE.findall(text))
    signal_patterns = _signal_patterns(jurisdiction_plugin)
    if signal_patterns is None:
        modality_hits = len(_MODALITY_RE.findall(text))
        legal_signal_hits = len(_LEGAL_SIGNAL_RE.findall(text))
        amendment_hits = len(_AMENDMENT_RE.findall(text))
        temporal_hits = len(_TEMPORAL_RE.findall(text))
    else:
        modality_hits = _count_hits(
            text,
            signal_patterns.obligation_re,
            signal_patterns.prohibition_re,
            signal_patterns.permission_re,
        )
        legal_signal_hits = _count_hits(
            text,
            signal_patterns.approval_re,
            signal_patterns.reference_re,
            signal_patterns.threshold_re,
        )
        amendment_hits = _count_hits(text, signal_patterns.amendment_re)
        temporal_hits = _count_hits(text, signal_patterns.temporal_re)
    ambiguity_hits = len(_AMBIGUITY_RE.findall(text))
    treaty_hits = len(_TREATY_RE.findall(f"{doc_title}\n{text}"))
    annex_reference_hits = len(_ANNEX_REF_RE.findall(text))
    approval_context_hits = len(_TITLE_ACTION_RE.findall(doc_title))
    publisher_lower = publisher.lower()
    is_structured = any(kw in publisher_lower for kw in _STRUCTURED_PUBLISHERS)
    has_list = bool(_LIST_ITEM_RE.search(text))
    is_article_like = struct_kind in {"article", "part"} or bool(_ARTICLE_LABEL_RE.match(citation_label))
    is_clause_like = struct_kind in {"point", "subpoint", "enumeration_item"}
    category = (doc_type_category or "").strip().lower()
    law_like_doc = category in {"constitution", "law", "code"}
    treaty_like_doc = category in {"treaty", "protocol"}
    appendix_heavy_doc = category in {"order", "regulation", "cabinet_resolution", "resolution", "decision", "directive", "decree"}
    structural_priority = 0.0
    if is_article_like:
        structural_priority += 0.70
    elif is_clause_like:
        structural_priority += 0.55
    if law_like_doc and is_article_like:
        structural_priority += 0.15
    if treaty_like_doc and (is_article_like or is_clause_like):
        structural_priority += 0.12
    if appendix_heavy_doc and is_clause_like:
        structural_priority += 0.08
    if section_role in {"normative_unit", "procedure", "entry_into_force"}:
        structural_priority += 0.15
    if approval_context_hits > 0 and (annex_reference_hits > 0 or legal_signal_hits > 0):
        structural_priority += 0.15
    if legal_unit_subtype in {"amendment_bundle", "approval_bundle", "tariff_threshold_row", "application_requirement"}:
        structural_priority += 0.20
    elif legal_unit_subtype in {"core_normative_clause", "temporal_clause", "sanction_clause", "exception_clause"}:
        structural_priority += 0.10
    structural_priority = max(0.0, min(1.0, structural_priority))

    short_fragment = len(stripped_text.split()) <= 12
    trailing_marker = stripped_text.endswith("*")
    bullet_fragment = bool(_BULLET_PREFIX_RE.match(stripped_text))
    is_fragment_like = (
        short_fragment
        and (bullet_fragment or trailing_marker)
        and amendment_hits == 0
        and temporal_hits == 0
        and treaty_hits == 0
        and annex_reference_hits == 0
    )
    total_legal_hits = modality_hits + legal_signal_hits + amendment_hits + temporal_hits + treaty_hits
    if approval_context_hits > 0 and (annex_reference_hits > 0 or legal_signal_hits > 0):
        total_legal_hits += 1
    high_value_legal_span = (
        amendment_hits > 0
        or legal_unit_subtype in {
            "amendment_bundle",
            "approval_bundle",
            "tariff_threshold_row",
            "application_requirement",
            "core_normative_clause",
            "temporal_clause",
            "sanction_clause",
            "exception_clause",
        }
        or temporal_hits > 0
        or treaty_hits > 0
        or (law_like_doc and is_article_like and (modality_hits > 0 or legal_signal_hits > 0))
        or (treaty_like_doc and (is_article_like or is_clause_like))
        or (is_article_like and (total_legal_hits > 0 or reference_count > 0))
        or (is_clause_like and approval_context_hits > 0 and (annex_reference_hits > 0 or legal_signal_hits > 0))
        or (is_clause_like and (total_legal_hits > 0 or reference_count > 0))
    ) and not is_fragment_like
    return GateFeatures(
        length_chars=len(text),
        numeric_density=numeric_hits / words,
        modality_hits=modality_hits,
        reference_density=reference_count / words,
        fallback_chunk=fallback_chunk,
        deterministic_confidence=max(0.0, min(1.0, deterministic_confidence)),
        ambiguity_hits=ambiguity_hits,
        is_structured_publisher=is_structured,
        has_list_structure=has_list,
        legal_signal_hits=total_legal_hits,
        amendment_hits=amendment_hits,
        temporal_hits=temporal_hits,
        treaty_hits=treaty_hits,
        annex_reference_hits=annex_reference_hits,
        approval_context_hits=approval_context_hits,
        structural_priority=structural_priority,
        high_value_legal_span=high_value_legal_span,
        is_fragment_like=is_fragment_like,
        law_like_doc=law_like_doc,
        treaty_like_doc=treaty_like_doc,
        appendix_heavy_doc=appendix_heavy_doc,
        legal_unit_subtype=legal_unit_subtype,
        route_class=route_class,
        empty_spo_retry_eligible=empty_spo_retry_eligible,
        audit_miss_prone=audit_miss_prone,
        reference_bearing=reference_bearing,
        threshold_bearing=threshold_bearing,
    )


def irreducibility_score(features: GateFeatures) -> float:
    """Estimate how likely LLM is irreplaceable for this provision."""
    length_factor = min(1.0, features.length_chars / 2400.0)
    numeric_factor = min(1.0, features.numeric_density * 45.0)
    modality_factor = min(1.0, features.modality_hits / 4.0)
    reference_factor = min(1.0, features.reference_density * 220.0)
    ambiguity_factor = min(1.0, features.ambiguity_hits / 5.0)
    legal_factor = min(1.0, features.legal_signal_hits / 3.0)
    low_det_factor = 1.0 - features.deterministic_confidence

    score = (
        0.19 * low_det_factor
        + 0.16 * ambiguity_factor
        + 0.14 * numeric_factor
        + 0.13 * reference_factor
        + 0.12 * modality_factor
        + 0.10 * legal_factor
        + 0.08 * length_factor
        + 0.08 * features.structural_priority
    )
    if features.fallback_chunk:
        score += 0.03
    if features.amendment_hits > 0:
        score += 0.08
    if features.temporal_hits > 0:
        score += 0.06
    if features.treaty_hits > 0:
        score += 0.05
    if features.reference_bearing:
        score += 0.06
    if features.threshold_bearing:
        score += 0.06
    if features.audit_miss_prone:
        score += 0.08
    if features.empty_spo_retry_eligible:
        score += 0.04
    # Subtypes known to produce audit misses under deterministic routing
    if features.legal_unit_subtype in {
        "core_normative_clause", "sanction_clause", "temporal_clause",
        "exception_clause", "amendment_bundle",
    }:
        score += 0.06
    if features.law_like_doc and features.high_value_legal_span:
        score += 0.07
    if features.treaty_like_doc and features.high_value_legal_span:
        score += 0.05
    if features.appendix_heavy_doc and features.high_value_legal_span and not features.is_fragment_like:
        score += 0.04
    if features.approval_context_hits > 0 and (features.annex_reference_hits > 0 or features.legal_signal_hits > 0):
        score += 0.07
    if features.is_structured_publisher and not features.high_value_legal_span and features.deterministic_confidence >= 0.5:
        score -= 0.03
    if features.has_list_structure:
        if features.high_value_legal_span:
            score += 0.04
        elif features.is_fragment_like:
            score -= 0.10
    if features.is_fragment_like:
        score -= 0.10
    if features.route_class == "deterministic_only":
        score -= 0.08
    elif features.route_class == "deterministic_then_llm_retry":
        score += 0.05
    return max(0.0, min(1.0, score))


def _stable_sample(seed: str, sample_rate: float) -> bool:
    if sample_rate <= 0.0:
        return False
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    value = int(digest, 16) / 0xFFFFFFFF
    return value < sample_rate


def decide_route(
    *,
    gate_enabled: bool,
    runtime: GateRuntime,
    llm_available: bool,
    llm_share: float,
    gap_fill_enabled: bool,
    gap_fill_eligible: bool,
    gap_fill_share: float,
    gap_fill_max_share: float,
    gap_fill_priority: int = 99,
    deterministic_confidence: float,
    auto_conf_threshold: float,
    min_score_force_llm: float,
    features: GateFeatures,
    audit_sample_rate: float,
    audit_seed: str,
) -> GateDecision:
    """Decide routing for one provision."""
    if features.route_class == "search_only":
        return GateDecision(route="deferred", score=0.0, reason_codes=["search_only_route"])

    score = irreducibility_score(features)
    gap_fill_priority_extra = 0.0
    if gap_fill_priority <= 2:
        gap_fill_priority_extra = 0.10
    elif gap_fill_priority <= 5:
        gap_fill_priority_extra = 0.05

    if gap_fill_enabled and gap_fill_eligible:
        if not llm_available:
            if deterministic_confidence > 0.0:
                return GateDecision(route="auto", score=score, reason_codes=["llm_gap_fill_unavailable"])
            return GateDecision(route="deferred", score=score, reason_codes=["llm_gap_fill_unavailable"])
        if runtime.safe_pass_active or gap_fill_share < (gap_fill_max_share + gap_fill_priority_extra):
            reason_codes = ["gap_fill_eligible"]
            if gap_fill_priority_extra > 0.0:
                reason_codes.append("gap_fill_priority")
            return GateDecision(route="llm_gap_fill", score=score, reason_codes=reason_codes)

    if deterministic_confidence >= auto_conf_threshold:
        if llm_available and _stable_sample(audit_seed, audit_sample_rate):
            return GateDecision(route="audit_llm", score=score, reason_codes=["audit_sample"])
        return GateDecision(route="auto", score=score, reason_codes=["deterministic_high_conf"])

    if features.route_class == "deterministic_only":
        if deterministic_confidence > 0.0:
            return GateDecision(route="auto", score=score, reason_codes=["deterministic_only_route"])
        return GateDecision(route="deferred", score=score, reason_codes=["deterministic_only_route"])

    if not llm_available:
        return GateDecision(route="deferred", score=score, reason_codes=["llm_unavailable"])

    if not gate_enabled or runtime.mode == "off":
        return GateDecision(route="llm", score=score, reason_codes=["gate_off"])

    priority_max_share = runtime.max_share + (0.10 if features.high_value_legal_span else 0.0)
    if llm_share >= priority_max_share and not runtime.safe_pass_active:
        if _stable_sample(audit_seed, audit_sample_rate):
            return GateDecision(route="audit_llm", score=score, reason_codes=["audit_sample_budget_cap"])
        return GateDecision(route="deferred", score=score, reason_codes=["budget_cap"])

    if score >= min_score_force_llm:
        return GateDecision(route="llm", score=score, reason_codes=["force_llm_high_score"])

    if score >= runtime.effective_threshold:
        return GateDecision(route="llm", score=score, reason_codes=["score_above_threshold"])

    if (
        features.route_class == "deterministic_then_llm_retry"
        and features.empty_spo_retry_eligible
        and deterministic_confidence <= 0.2
        and score >= max(0.0, runtime.effective_threshold - 0.18)
    ):
        return GateDecision(route="llm", score=score, reason_codes=["retry_route_priority"])

    if features.high_value_legal_span and score >= max(0.0, runtime.effective_threshold - 0.12):
        return GateDecision(route="llm", score=score, reason_codes=["near_threshold_legal_priority"])

    if _stable_sample(audit_seed, audit_sample_rate):
        return GateDecision(route="audit_llm", score=score, reason_codes=["audit_sample"])
    return GateDecision(route="deferred", score=score, reason_codes=["score_below_threshold"])
