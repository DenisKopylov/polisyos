"""Resolution policies that score competing claims after conflict detection."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from polisyos.fabric.claims.errors import ClaimValidationError


@dataclass(frozen=True)
class ConflictPolicy:
    """Weights and tolerances used to rank competing claims inside one conflict set."""
    policy_id: str
    policy_version: str
    tolerance: Decimal
    score_weights: dict[str, Decimal] = field(default_factory=dict)
    source_type_weights: dict[str, Decimal] = field(default_factory=dict)
    host_suffix_weights: dict[str, Decimal] = field(default_factory=dict)
    license_weights: dict[str, Decimal] = field(default_factory=dict)
    extractor_reliability: dict[str, Decimal] = field(default_factory=dict)
    agent_reliability: dict[str, Decimal] = field(default_factory=dict)
    evidence_density_divisor: Decimal = Decimal("4")
    default_doc_trust: Decimal = Decimal("0.50")
    default_claim_trust: Decimal = Decimal("0.50")


DEFAULT_POLICY = ConflictPolicy(
    policy_id="policy.conflicts.default_v1",
    policy_version="1.0",
    tolerance=Decimal("0"),
    score_weights={
        "doc_trust": Decimal("0.45"),
        "evidence_density": Decimal("0.20"),
        "extractor_reliability": Decimal("0.20"),
        "consensus": Decimal("0.15"),
    },
    source_type_weights={
        "official": Decimal("0.90"),
        "government": Decimal("0.88"),
        "law": Decimal("0.86"),
        "regulator": Decimal("0.84"),
        "news": Decimal("0.65"),
        "research": Decimal("0.78"),
        "test": Decimal("0.55"),
    },
    host_suffix_weights={
        ".gov": Decimal("0.88"),
        ".edu": Decimal("0.78"),
        ".org": Decimal("0.66"),
        ".com": Decimal("0.60"),
    },
    license_weights={
        "public": Decimal("0.75"),
        "cc0": Decimal("0.78"),
        "cc-by": Decimal("0.74"),
        "proprietary": Decimal("0.55"),
    },
    extractor_reliability={
        "explicit_lines_v1": Decimal("0.70"),
        "lex.norm_extractor.regex_v1": Decimal("0.80"),
        "regex_numeric_v1": Decimal("0.55"),
    },
    agent_reliability={
        "prov.agent.fabric_claims": Decimal("0.60"),
    },
)


_POLICIES: dict[str, ConflictPolicy] = {
    DEFAULT_POLICY.policy_id: DEFAULT_POLICY,
}


def get_conflict_policy(policy_id: str) -> ConflictPolicy:
    """Return conflict policy."""
    policy = _POLICIES.get(policy_id)
    if policy is None:
        supported = ", ".join(sorted(_POLICIES))
        raise ClaimValidationError(
            f"unknown conflict policy_id '{policy_id}', supported: {supported}"
        )
    return policy


__all__ = [
    "ConflictPolicy",
    "DEFAULT_POLICY",
    "get_conflict_policy",
]
