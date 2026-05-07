"""Lazy-loaded governance pass helpers for judge stack flows."""

from __future__ import annotations

from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def load_quality_gate_pass_type() -> type[Any]:
    from polisyos.scientist.governance.passes.quality_gate_pass import QualityGatePass

    return QualityGatePass


@lru_cache(maxsize=1)
def load_robustness_pass_types() -> tuple[type[Any], type[Any]]:
    from polisyos.scientist.governance.passes.refutation_pass import RefutationPass
    from polisyos.scientist.governance.passes.sutva_check_pass import SutvaCheckPass

    return RefutationPass, SutvaCheckPass


@lru_cache(maxsize=1)
def load_transportability_required_pass_type() -> type[Any]:
    from polisyos.scientist.governance.passes.transportability_required_pass import (
        TransportabilityRequiredPass,
    )

    return TransportabilityRequiredPass


@lru_cache(maxsize=1)
def load_governance_pass_factories() -> tuple[Any, ...]:
    from polisyos.scientist.governance.pass_entrypoints import (
        budget_pass_factory,
        equity_pass_factory,
        human_review_required_pass_factory,
        legal_pass_factory,
        pii_check_pass_factory,
        privacy_pass_factory,
    )

    return (
        budget_pass_factory,
        equity_pass_factory,
        privacy_pass_factory,
        pii_check_pass_factory,
        human_review_required_pass_factory,
        legal_pass_factory,
    )


@lru_cache(maxsize=1)
def load_reproducibility_pass_types() -> tuple[type[Any], type[Any], type[Any]]:
    from polisyos.scientist.governance.passes.checkpoint_pass import CheckpointPass
    from polisyos.scientist.governance.passes.citation_validator_pass import (
        CitationValidatorPass,
    )
    from polisyos.scientist.governance.passes.freshness_pass import FreshnessPass

    return CheckpointPass, CitationValidatorPass, FreshnessPass


@lru_cache(maxsize=1)
def load_benchmark_split_enum() -> type[Any]:
    from polisyos.scientist.methods.autotune.models import BenchmarkSplit

    return BenchmarkSplit


__all__ = [
    "load_benchmark_split_enum",
    "load_governance_pass_factories",
    "load_quality_gate_pass_type",
    "load_reproducibility_pass_types",
    "load_robustness_pass_types",
    "load_transportability_required_pass_type",
]
