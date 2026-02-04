from __future__ import annotations

from dataclasses import dataclass, field

from polisyos.fabric.claims import ClaimExtractOptions, ClaimNormalizeOptions, ConflictResolveOptions
from polisyos.fabric.docs import DocChunkOptions, DocNormalizeOptions, DocStructureOptions
from polisyos.ir.world.trust import TrustTier


@dataclass(frozen=True)
class ScholarBudgetsDefaults:
    max_docs: int = 16
    max_bytes_total: int = 20_000_000
    max_claims_total: int = 2_000
    max_bytes_per_doc: int | None = None


@dataclass(frozen=True)
class ScholarThresholdsDefaults:
    min_doc_trust_tier: TrustTier = TrustTier.MEDIUM


@dataclass(frozen=True)
class ScholarDocsDefaults:
    normalize_options: DocNormalizeOptions = field(default_factory=DocNormalizeOptions)
    structure_options: DocStructureOptions = field(default_factory=DocStructureOptions)
    chunk_options: DocChunkOptions = field(
        default_factory=lambda: DocChunkOptions(min_chunk_chars=1)
    )


@dataclass(frozen=True)
class ScholarClaimsDefaults:
    extractor_id: str = "explicit_lines_v1"
    extract_options: ClaimExtractOptions = field(default_factory=ClaimExtractOptions)
    normalize_options: ClaimNormalizeOptions = field(default_factory=ClaimNormalizeOptions)
    resolve_options: ConflictResolveOptions = field(default_factory=ConflictResolveOptions)


@dataclass(frozen=True)
class ScholarConflictPolicyDefaults:
    policy_id: str = "policy.conflicts.default_v1"


@dataclass(frozen=True)
class ScholarAcquireDefaults:
    timeout_s: float = 10.0
    user_agent: str = "polisyos-scholar/1.0"


@dataclass(frozen=True)
class ScholarPolicy:
    budgets: ScholarBudgetsDefaults = field(default_factory=ScholarBudgetsDefaults)
    thresholds: ScholarThresholdsDefaults = field(default_factory=ScholarThresholdsDefaults)
    docs: ScholarDocsDefaults = field(default_factory=ScholarDocsDefaults)
    claims: ScholarClaimsDefaults = field(default_factory=ScholarClaimsDefaults)
    conflict: ScholarConflictPolicyDefaults = field(default_factory=ScholarConflictPolicyDefaults)
    acquire: ScholarAcquireDefaults = field(default_factory=ScholarAcquireDefaults)
    persist_report: bool = True


__all__ = [
    "ScholarAcquireDefaults",
    "ScholarBudgetsDefaults",
    "ScholarClaimsDefaults",
    "ScholarConflictPolicyDefaults",
    "ScholarDocsDefaults",
    "ScholarPolicy",
    "ScholarThresholdsDefaults",
]
