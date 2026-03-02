"""DOD-137/138/139: Alignment certification policy, outer objective, and bounded search."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.datasets.knowledge.proxy_resolver import compose_confidence_chain


class AlignmentCertificateType(str, Enum):
    EXACT = "exact"
    SCALE_LINK = "scale_link"
    LATENT_LINK_IRT = "latent_link_irt"
    PROXY_BUNDLE = "proxy_bundle"
    TEXT_CONCEPT_MAP = "text_concept_map"


class AlignmentCertificate(BaseModel):
    """Single alignment certificate between a source and target variable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cert_type: AlignmentCertificateType
    source_variable: str
    target_variable: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(default_factory=list)


class CertificationResult(BaseModel):
    """Result of validating a chain of alignment certificates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    passed: bool
    effective_confidence: float = Field(ge=0.0, le=1.0)
    violations: list[str] = Field(default_factory=list)
    long_chain_warning: str | None = None


TAU_MIN_LOWER = 0.55
TAU_MIN_UPPER = 0.95


class AlignmentCertificationPolicy(BaseModel):
    """Policy governing how alignment certificates are validated."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed_types: tuple[AlignmentCertificateType, ...] = Field(
        default=tuple(sorted(AlignmentCertificateType, key=lambda x: x.value))
    )
    tau_min: float = 0.65
    composition_rule: Literal["harmonic", "multiplicative"] = "harmonic"
    max_chain_length: int = Field(default=5, ge=1)

    @field_validator("tau_min")
    @classmethod
    def _validate_tau_min(cls, v: float) -> float:
        if v < TAU_MIN_LOWER or v > TAU_MIN_UPPER:
            raise ValueError(
                f"tau_min must be in [{TAU_MIN_LOWER}, {TAU_MIN_UPPER}], got {v}"
            )
        return v

    def validate_chain(self, chain: list[AlignmentCertificate]) -> CertificationResult:
        """Check types, compose confidence, enforce tau_min."""
        violations: list[str] = []
        warning: str | None = None

        if not chain:
            return CertificationResult(
                passed=False,
                effective_confidence=0.0,
                violations=["empty chain"],
            )

        if len(chain) > self.max_chain_length:
            violations.append(
                f"chain length {len(chain)} exceeds max {self.max_chain_length}"
            )

        allowed = set(self.allowed_types)
        for cert in chain:
            if cert.cert_type not in allowed:
                violations.append(
                    f"certificate type {cert.cert_type.value} not allowed by policy"
                )

        scores = [cert.confidence for cert in chain]
        if self.composition_rule == "harmonic":
            effective = compose_confidence_chain(scores)
        else:
            effective = 1.0
            for s in scores:
                effective *= s

        if len(chain) > self.max_chain_length:
            warning = (
                f"Chain length {len(chain)} exceeds recommended "
                f"maximum {self.max_chain_length}; confidence degradation likely."
            )

        passed = effective >= self.tau_min and not violations
        return CertificationResult(
            passed=passed,
            effective_confidence=effective,
            violations=violations,
            long_chain_warning=warning,
        )


# --- DOD-138: Outer objective formula ---


class OuterObjectiveResult(BaseModel):
    """Result of evaluating the outer objective for one policy configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    score: float
    coverage: float = Field(ge=0.0, le=1.0)
    conflict_norm: float = Field(ge=0.0, le=1.0)
    lambda_conflict: float
    config: AlignmentCertificationPolicy
    is_feasible: bool


def compute_outer_objective(
    coverage_queries: float,
    irreducible_conflict_norm: float,
    lambda_conflict: float = 1.0,
) -> float:
    """score(N) = coverage - lambda_conflict * irreducible_conflict_norm"""
    return coverage_queries - lambda_conflict * irreducible_conflict_norm


# --- DOD-139: Bounded knobs + grid search ---

TAU_GRID: tuple[float, ...] = (0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90)
LAMBDA_GRID: tuple[float, ...] = (0.5, 1.0, 2.0)

def _sorted_types(*items: AlignmentCertificateType) -> tuple[AlignmentCertificateType, ...]:
    return tuple(sorted(items, key=lambda x: x.value))


_ALL_TYPES = _sorted_types(*AlignmentCertificateType)
_NO_TEXT = _sorted_types(*(t for t in AlignmentCertificateType if t != AlignmentCertificateType.TEXT_CONCEPT_MAP))
_EXACT_SCALE = _sorted_types(AlignmentCertificateType.EXACT, AlignmentCertificateType.SCALE_LINK)
_EXACT_ONLY = _sorted_types(AlignmentCertificateType.EXACT)
_PROXY_IRT = _sorted_types(
    AlignmentCertificateType.PROXY_BUNDLE,
    AlignmentCertificateType.LATENT_LINK_IRT,
)
_EXACT_PROXY = _sorted_types(AlignmentCertificateType.EXACT, AlignmentCertificateType.PROXY_BUNDLE)

TYPE_CONFIGS: tuple[tuple[AlignmentCertificateType, ...], ...] = (
    _ALL_TYPES,
    _NO_TEXT,
    _EXACT_SCALE,
    _EXACT_ONLY,
    _PROXY_IRT,
    _EXACT_PROXY,
)

MAX_OUTER_SOLVES = 48
MAX_OUTER_WALLTIME_SEC = 3.0


class OuterSearchResult(BaseModel):
    """Result of bounded grid search over alignment policy knobs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    best_config: AlignmentCertificationPolicy
    best_score: float
    configs_evaluated: int
    truncated: bool
    all_scores: list[OuterObjectiveResult] = Field(default_factory=list)


def run_outer_search(
    evaluator: Callable[[AlignmentCertificationPolicy], OuterObjectiveResult],
    type_configs: Sequence[tuple[AlignmentCertificateType, ...]] | None = None,
) -> OuterSearchResult:
    """Bounded grid search over (tau, lambda, type_config) space."""
    configs = type_configs if type_configs is not None else TYPE_CONFIGS
    best_score = float("-inf")
    best_config: AlignmentCertificationPolicy | None = None
    all_scores: list[OuterObjectiveResult] = []
    evaluated = 0
    start = time.monotonic()

    for type_set in configs:
        for tau in TAU_GRID:
            for _lambda in LAMBDA_GRID:
                if evaluated >= MAX_OUTER_SOLVES:
                    return OuterSearchResult(
                        best_config=best_config or _default_policy(),
                        best_score=best_score if best_config else 0.0,
                        configs_evaluated=evaluated,
                        truncated=True,
                        all_scores=all_scores,
                    )
                elapsed = time.monotonic() - start
                if elapsed > MAX_OUTER_WALLTIME_SEC:
                    return OuterSearchResult(
                        best_config=best_config or _default_policy(),
                        best_score=best_score if best_config else 0.0,
                        configs_evaluated=evaluated,
                        truncated=True,
                        all_scores=all_scores,
                    )

                policy = AlignmentCertificationPolicy(
                    allowed_types=type_set,
                    tau_min=tau,
                )
                result = evaluator(policy)
                all_scores.append(result)
                evaluated += 1
                if result.score > best_score:
                    best_score = result.score
                    best_config = policy

    return OuterSearchResult(
        best_config=best_config or _default_policy(),
        best_score=best_score if best_config else 0.0,
        configs_evaluated=evaluated,
        truncated=False,
        all_scores=all_scores,
    )


def _default_policy() -> AlignmentCertificationPolicy:
    return AlignmentCertificationPolicy()


__all__ = [
    "AlignmentCertificateType",
    "AlignmentCertificate",
    "AlignmentCertificationPolicy",
    "CertificationResult",
    "OuterObjectiveResult",
    "OuterSearchResult",
    "TAU_GRID",
    "TAU_MIN_LOWER",
    "TAU_MIN_UPPER",
    "LAMBDA_GRID",
    "MAX_OUTER_SOLVES",
    "MAX_OUTER_WALLTIME_SEC",
    "TYPE_CONFIGS",
    "compute_outer_objective",
    "run_outer_search",
]
