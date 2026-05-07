"""Shared contracts for symbolic causal identification engines."""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any

from polisyos.ir.analytics.estimand import DistributionRef, EstimandAST


@dataclasses.dataclass(frozen=True)
class ProofStep:
    """A single deductive step in the ID algorithm proof trace."""

    rule_name: str
    antecedent_vars: tuple[str, ...]
    consequent_vars: tuple[str, ...]
    applied_to_graph_state: str
    depth: int = 0
    graph_state_before: str = ""


@dataclasses.dataclass(frozen=True)
class RequiredDataSpec:
    """Specification of data needed to achieve identification."""

    missing_distributions: tuple[Any, ...]
    suggested_experiment: str | None = None
    alternative_identification: str | None = None


@dataclasses.dataclass(frozen=True)
class HedgeCertificate:
    """Mathematical witness of non-identifiability.

    A hedge (F, F') is a pair of c-forests such that F' is contained in F,
    F' is a c-component of G[An(Y)], F is a c-component of G[V \\ X], and the
    roots of F' are also roots of F inside X.
    """

    treatment: frozenset[str]
    outcome: frozenset[str]
    hedge_forest: frozenset[str]
    hedge_root: frozenset[str]
    c_component_witness: frozenset[str]
    description: str = ""
    required_data: RequiredDataSpec | None = None
    # Minimum S-nodes that, if resolved, can make transport potentially identifiable.
    minimal_required_s_nodes: frozenset[str] = dataclasses.field(default_factory=frozenset)


class IdentificationStatus(str, Enum):
    """Classify whether a causal query is identified, blocked, ambiguous, or oracle-gated."""

    IDENTIFIED = "identified"
    HEDGE_FOUND = "hedge_found"
    PAG_AMBIGUOUS = "pag_ambiguous"
    ORACLE_NEEDED = "oracle_needed"
    NOT_RECOVERABLE = "not_recoverable"


@dataclasses.dataclass(frozen=True)
class IdentificationResult:
    """Result of running an ID-family identification algorithm."""

    status: IdentificationStatus
    estimand_ast: EstimandAST | None
    hedge_certificate: HedgeCertificate | None
    trace: list[str]
    required_distributions: list[DistributionRef]
    algorithm_version: str = "id_v1"
    proof_steps: list[ProofStep] = dataclasses.field(default_factory=list)
    query_str: str = ""
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class CtfQuery:
    """Counterfactual query container for Layer-3 ID* / IDC* requests."""

    outcome: str
    intervention: tuple[tuple[str, float], ...]
    conditioning: tuple[str, ...] = ()
    evidence: tuple[tuple[str, float], ...] = ()
    kind: str = "generic"
    mediators: tuple[str, ...] = ()
    protected_attribute: str | None = None
    reference_intervention: tuple[tuple[str, float], ...] = ()
    outcome_value: float | None = None


@dataclasses.dataclass(frozen=True)
class SourceDomain:
    """Descriptor for a source domain in multi-domain transportability."""

    domain_id: str
    s_nodes: frozenset[str] = dataclasses.field(default_factory=frozenset)
    z_interventions: frozenset[str] = dataclasses.field(default_factory=frozenset)
    dataset_ref: str | None = None
    distribution_domain: Any = "source"


__all__ = [
    "CtfQuery",
    "HedgeCertificate",
    "IdentificationResult",
    "IdentificationStatus",
    "ProofStep",
    "RequiredDataSpec",
    "SourceDomain",
]
