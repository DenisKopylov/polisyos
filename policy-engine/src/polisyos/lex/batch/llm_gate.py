"""Two-stage LLM gate for Lex SPO extraction."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


_NUMERIC_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")
_MODALITY_RE = re.compile(r"(повинен|зобов|має|заборон|уповноваж|доруч)", re.IGNORECASE)
_AMBIGUITY_RE = re.compile(r"(та/або|або|якщо|у разі|може|за потреби|відповідно до)", re.IGNORECASE)


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


@dataclass(frozen=True)
class GateDecision:
    """Routing decision for one provision."""

    route: str  # skip|auto|llm|deferred|audit_llm
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
            self.consecutive_audit_failures = 0
        if self.consecutive_audit_failures < 2:
            return False
        self.safe_pass_active = True
        self.circuit_breaker_hits += 1
        self.consecutive_audit_failures = 0
        return True

    @property
    def effective_threshold(self) -> float:
        if self.safe_pass_active:
            return max(0.0, self.threshold - 0.25)
        if self.mode == "aggressive":
            return min(1.0, self.threshold + 0.10)
        return self.threshold


_LIST_ITEM_RE = re.compile(r"^\s*\d+\)\s+", re.MULTILINE)

_STRUCTURED_PUBLISHERS = frozenset({
    "кабінет міністрів", "кму", "президент",
    "міністерство", "нацбанк", "національний банк",
})


def build_gate_features(
    *,
    text: str,
    deterministic_confidence: float,
    reference_count: int,
    fallback_chunk: bool,
    publisher: str = "",
) -> GateFeatures:
    """Compute routing features from provision text + deterministic signal."""
    words = max(1, len(text.split()))
    numeric_hits = len(_NUMERIC_RE.findall(text))
    modality_hits = len(_MODALITY_RE.findall(text))
    ambiguity_hits = len(_AMBIGUITY_RE.findall(text))
    publisher_lower = publisher.lower()
    is_structured = any(kw in publisher_lower for kw in _STRUCTURED_PUBLISHERS)
    has_list = len(_LIST_ITEM_RE.findall(text)) >= 2
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
    )


def irreducibility_score(features: GateFeatures) -> float:
    """Estimate how likely LLM is irreplaceable for this provision."""
    length_factor = min(1.0, features.length_chars / 2400.0)
    numeric_factor = min(1.0, features.numeric_density * 45.0)
    modality_factor = min(1.0, features.modality_hits / 4.0)
    reference_factor = min(1.0, features.reference_density * 220.0)
    ambiguity_factor = min(1.0, features.ambiguity_hits / 5.0)
    low_det_factor = 1.0 - features.deterministic_confidence

    score = (
        0.23 * low_det_factor
        + 0.20 * ambiguity_factor
        + 0.19 * numeric_factor
        + 0.14 * reference_factor
        + 0.13 * modality_factor
        + 0.11 * length_factor
    )
    if features.fallback_chunk:
        score += 0.05
    # Structured publishers (КМУ, Президент) produce more predictable provisions
    if features.is_structured_publisher:
        score -= 0.08
    # List-structured provisions are typically enumerations of simple items
    if features.has_list_structure:
        score -= 0.05
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
    deterministic_confidence: float,
    auto_conf_threshold: float,
    min_score_force_llm: float,
    features: GateFeatures,
    audit_sample_rate: float,
    audit_seed: str,
) -> GateDecision:
    """Decide routing for one provision."""
    if deterministic_confidence >= auto_conf_threshold:
        if llm_available and _stable_sample(audit_seed, audit_sample_rate):
            return GateDecision(route="audit_llm", score=0.0, reason_codes=["audit_sample"])
        return GateDecision(route="auto", score=0.0, reason_codes=["deterministic_high_conf"])

    if not llm_available:
        return GateDecision(route="deferred", score=0.0, reason_codes=["llm_unavailable"])

    score = irreducibility_score(features)

    if not gate_enabled or runtime.mode == "off":
        return GateDecision(route="llm", score=score, reason_codes=["gate_off"])

    if llm_share >= runtime.max_share and not runtime.safe_pass_active:
        if _stable_sample(audit_seed, audit_sample_rate):
            return GateDecision(route="audit_llm", score=score, reason_codes=["audit_sample_budget_cap"])
        return GateDecision(route="deferred", score=score, reason_codes=["budget_cap"])

    if score >= min_score_force_llm:
        return GateDecision(route="llm", score=score, reason_codes=["force_llm_high_score"])

    if score >= runtime.effective_threshold:
        return GateDecision(route="llm", score=score, reason_codes=["score_above_threshold"])

    if _stable_sample(audit_seed, audit_sample_rate):
        return GateDecision(route="audit_llm", score=score, reason_codes=["audit_sample"])
    return GateDecision(route="deferred", score=score, reason_codes=["score_below_threshold"])

