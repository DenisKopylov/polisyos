"""Public scholar policies module API."""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from polisyos.fabric.claims import (
    ClaimExtractOptions,
    ClaimNormalizeOptions,
    ConflictResolveOptions,
)
from polisyos.fabric.docs import DocChunkOptions, DocNormalizeOptions, DocStructureOptions
from polisyos.ir.world.trust import TrustTier


@dataclass(frozen=True)
class ScholarBudgetsDefaults:
    """Scholar budgets defaults public type."""
    max_docs: int = 16
    max_bytes_total: int = 20_000_000
    max_claims_total: int = 2_000
    max_bytes_per_doc: int | None = None


@dataclass(frozen=True)
class ScholarThresholdsDefaults:
    """Scholar thresholds defaults public type."""
    min_doc_trust_tier: TrustTier = TrustTier.MEDIUM


@dataclass(frozen=True)
class ScholarDocsDefaults:
    """Scholar docs defaults public type."""
    normalize_options: DocNormalizeOptions = field(default_factory=DocNormalizeOptions)
    structure_options: DocStructureOptions = field(default_factory=DocStructureOptions)
    chunk_options: DocChunkOptions = field(
        default_factory=lambda: DocChunkOptions(min_chunk_chars=1)
    )


@dataclass(frozen=True)
class ScholarClaimsDefaults:
    """Scholar claims defaults public type."""
    extractor_id: str = "explicit_lines_v1"
    extract_options: ClaimExtractOptions = field(default_factory=ClaimExtractOptions)
    normalize_options: ClaimNormalizeOptions = field(default_factory=ClaimNormalizeOptions)
    resolve_options: ConflictResolveOptions = field(default_factory=ConflictResolveOptions)


@dataclass(frozen=True)
class ScholarConflictPolicyDefaults:
    """Scholar conflict policy defaults public type."""
    policy_id: str = "policy.conflicts.default_v1"


@dataclass(frozen=True)
class ScholarAcquireDefaults:
    """Scholar acquire defaults public type."""
    timeout_s: float = 10.0
    user_agent: str = "polisyos-scholar/1.0"


@dataclass(frozen=True)
class ScholarFreshnessThreshold:
    """Scholar freshness threshold public type."""
    staleness_days: int = 30
    expiry_days: int = 90
    cooldown_seconds: int = 3600

    def __post_init__(self) -> None:
        if self.staleness_days <= 0:
            raise ValueError("staleness_days must be > 0")
        if self.expiry_days < self.staleness_days:
            raise ValueError("expiry_days must be >= staleness_days")
        if self.cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be >= 0")


_DEFAULT_DOMAIN_THRESHOLDS: Mapping[str, ScholarFreshnessThreshold] = MappingProxyType(
    {
        "fiscal": ScholarFreshnessThreshold(
            staleness_days=90,
            expiry_days=365,
            cooldown_seconds=3600,
        ),
        "labor": ScholarFreshnessThreshold(
            staleness_days=30,
            expiry_days=90,
            cooldown_seconds=3600,
        ),
        "health": ScholarFreshnessThreshold(
            staleness_days=14,
            expiry_days=60,
            cooldown_seconds=1800,
        ),
        "infrastructure": ScholarFreshnessThreshold(
            staleness_days=180,
            expiry_days=730,
            cooldown_seconds=7200,
        ),
        "education": ScholarFreshnessThreshold(
            staleness_days=60,
            expiry_days=365,
            cooldown_seconds=3600,
        ),
    }
)


@dataclass(frozen=True)
class ScholarFreshnessDefaults:
    """Scholar freshness defaults public type."""
    default: ScholarFreshnessThreshold = field(default_factory=ScholarFreshnessThreshold)
    domains: Mapping[str, ScholarFreshnessThreshold] = field(
        default_factory=lambda: _DEFAULT_DOMAIN_THRESHOLDS
    )

    def resolve(self, domain: str | None) -> ScholarFreshnessThreshold:
        key = (domain or "").strip().lower()
        if key and key in self.domains:
            return self.domains[key]
        return self.default


@dataclass(frozen=True)
class ScholarPolicy:
    """Scholar policy data model."""
    budgets: ScholarBudgetsDefaults = field(default_factory=ScholarBudgetsDefaults)
    thresholds: ScholarThresholdsDefaults = field(default_factory=ScholarThresholdsDefaults)
    docs: ScholarDocsDefaults = field(default_factory=ScholarDocsDefaults)
    claims: ScholarClaimsDefaults = field(default_factory=ScholarClaimsDefaults)
    conflict: ScholarConflictPolicyDefaults = field(default_factory=ScholarConflictPolicyDefaults)
    acquire: ScholarAcquireDefaults = field(default_factory=ScholarAcquireDefaults)
    freshness: ScholarFreshnessDefaults = field(default_factory=ScholarFreshnessDefaults)
    persist_report: bool = True


__all__ = [
    "ScholarAcquireDefaults",
    "ScholarBudgetsDefaults",
    "ScholarClaimsDefaults",
    "ScholarConflictPolicyDefaults",
    "ScholarDocsDefaults",
    "ScholarFreshnessDefaults",
    "ScholarFreshnessThreshold",
    "ScholarPolicy",
    "ScholarThresholdsDefaults",
]
