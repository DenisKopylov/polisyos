"""Factory entrypoints for the built-in Scientist governance pass registry."""
from __future__ import annotations

from collections.abc import Callable

from polisyos.core.governance.legal.backends.stub import StubBackend
from polisyos.core.governance.passes.base import ValidatorPass
from polisyos.core.governance.passes.legal_pass import LegalPass
from polisyos.core.governance.passes.safety_pass import SafetyPass

from .passes.budget_pass import BudgetPass
from .passes.checkpoint_pass import CheckpointPass
from .passes.confidence_pass import ConfidencePass
from .passes.cross_graph_evidence_pass import CrossGraphEvidencePass
from .passes.equity_pass import EquityPass
from .passes.freshness_pass import FreshnessPass
from .passes.human_review_pass import HumanReviewRequiredPass
from .passes.literature_gate_pass import LiteratureGatePass
from .passes.normative_arbitration_pass import NormativeArbitrationPass
from .passes.pii_check_pass import PIICheckPass
from .passes.privacy_pass import PrivacyPass
from .passes.quality_gate_pass import QualityGatePass
from .passes.refutation_pass import RefutationPass
from .passes.schema_pass import SchemaPass
from .passes.sutva_check_pass import SutvaCheckPass
from .passes.strategic_response_pass import StrategicResponsePass
from .passes.transportability_required_pass import TransportabilityRequiredPass


def budget_pass_factory() -> ValidatorPass:
    """Create the pass that enforces workflow budget constraints."""
    return BudgetPass()


def checkpoint_pass_factory() -> ValidatorPass:
    """Create the pass that verifies checkpoint availability and consistency."""
    return CheckpointPass()


def schema_pass_factory() -> ValidatorPass:
    """Create the pass that validates required schema-bearing artifacts."""
    return SchemaPass()


def privacy_pass_factory() -> ValidatorPass:
    """Create the pass that enforces privacy policy checks."""
    return PrivacyPass()


def pii_check_pass_factory() -> ValidatorPass:
    """Create the pass that detects personally identifiable information risk."""
    return PIICheckPass()


def freshness_pass_factory() -> ValidatorPass:
    """Create the pass that checks evidence freshness requirements."""
    return FreshnessPass()


def sutva_check_pass_factory() -> ValidatorPass:
    """Create the pass that checks SUTVA-related causal validity assumptions."""
    return SutvaCheckPass()


def transportability_required_pass_factory() -> ValidatorPass:
    """Create the pass that requires transportability evidence when needed."""
    return TransportabilityRequiredPass()


def strategic_response_pass_factory() -> ValidatorPass:
    """Create the pass that reviews strategic-response risk artifacts."""
    return StrategicResponsePass()


def safety_pass_factory() -> ValidatorPass:
    """Create the pass that runs core safety validation checks."""
    return SafetyPass()


def equity_pass_factory() -> ValidatorPass:
    """Create the pass that evaluates equity and fairness evidence."""
    return EquityPass()


def cross_graph_evidence_pass_factory() -> ValidatorPass:
    """Create the pass that verifies cross-graph evidence coverage."""
    return CrossGraphEvidencePass()


def literature_gate_pass_factory() -> ValidatorPass:
    """Create the pass that checks literature-grounding requirements."""
    return LiteratureGatePass()


def normative_arbitration_pass_factory() -> ValidatorPass:
    """Create the pass that arbitrates conflicting normative signals."""
    return NormativeArbitrationPass()


def legal_pass_factory() -> ValidatorPass:
    """Create the legal validation pass with the default stub backend."""
    return LegalPass(backend=StubBackend())


def confidence_pass_factory() -> ValidatorPass:
    """Create the pass that validates confidence and uncertainty posture."""
    return ConfidencePass()


def refutation_pass_factory() -> ValidatorPass:
    """Create the pass that requires refutation evidence for estimates."""
    return RefutationPass()


def human_review_required_pass_factory() -> ValidatorPass:
    """Create the pass that blocks automation until human review is recorded."""
    return HumanReviewRequiredPass()


def quality_gate_pass_factory() -> ValidatorPass:
    """Create the pass that aggregates quality-gate verdicts."""
    return QualityGatePass()


def builtin_governance_pass_factories() -> dict[str, Callable[[], ValidatorPass]]:
    """Return the stable registry of built-in governance pass factories."""
    return {
        "budget": budget_pass_factory,
        "checkpoint": checkpoint_pass_factory,
        "confidence": confidence_pass_factory,
        "cross_graph_evidence": cross_graph_evidence_pass_factory,
        "equity": equity_pass_factory,
        "freshness": freshness_pass_factory,
        "human_review_required": human_review_required_pass_factory,
        "legal": legal_pass_factory,
        "literature_gate": literature_gate_pass_factory,
        "normative_arbitration": normative_arbitration_pass_factory,
        "pii_check": pii_check_pass_factory,
        "privacy": privacy_pass_factory,
        "quality": quality_gate_pass_factory,
        "refutation": refutation_pass_factory,
        "safety": safety_pass_factory,
        "schema": schema_pass_factory,
        "strategic_response": strategic_response_pass_factory,
        "sutva_check": sutva_check_pass_factory,
        "transportability_required": transportability_required_pass_factory,
    }


__all__ = [
    "budget_pass_factory",
    "checkpoint_pass_factory",
    "schema_pass_factory",
    "privacy_pass_factory",
    "pii_check_pass_factory",
    "freshness_pass_factory",
    "strategic_response_pass_factory",
    "sutva_check_pass_factory",
    "transportability_required_pass_factory",
    "safety_pass_factory",
    "equity_pass_factory",
    "literature_gate_pass_factory",
    "normative_arbitration_pass_factory",
    "legal_pass_factory",
    "confidence_pass_factory",
    "cross_graph_evidence_pass_factory",
    "refutation_pass_factory",
    "human_review_required_pass_factory",
    "quality_gate_pass_factory",
    "builtin_governance_pass_factories",
]
