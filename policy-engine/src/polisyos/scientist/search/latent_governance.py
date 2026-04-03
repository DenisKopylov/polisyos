"""Governance adapter for research-only latent discovery artifacts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.causal_discovery import LatentDiscoveryBundle


class LatentGovernanceAssessment(BaseModel):
    """Normalized latent-governance decision used by search runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    active: bool = True
    valid: bool
    claim_mode: Literal["proof_only"] = "proof_only"
    degradation_mode: Literal["research_only"] = "research_only"
    promotion_allowed: bool = False
    human_gate_required: bool = True
    not_for_decision_support: bool = True
    missing_requirements: list[str] = Field(default_factory=list)
    surfaced_assumptions: list[str] = Field(default_factory=list)
    surfaced_falsification_tests: list[str] = Field(default_factory=list)
    no_promotion_reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def assess_latent_governance(
    bundle: LatentDiscoveryBundle | None,
) -> LatentGovernanceAssessment | None:
    """Assess latent governance helper."""
    if bundle is None:
        return None

    missing_requirements: list[str] = []
    if not bundle.proposed_latent_nodes:
        missing_requirements.append("proposed_latent_nodes_missing")
    if not bundle.inducing_environments:
        missing_requirements.append("inducing_environments_missing")
    if not bundle.identification_conditions:
        missing_requirements.append("identification_conditions_missing")
    if not bundle.assumption_cards:
        missing_requirements.append("assumption_cards_missing")
    if not bundle.falsification_tests:
        missing_requirements.append("falsification_tests_missing")
    if bundle.readiness_cap != "proof_only":
        missing_requirements.append("readiness_cap_not_proof_only")
    if not bundle.human_gate_required:
        missing_requirements.append("human_gate_required_false")
    if bundle.promotion_allowed:
        missing_requirements.append("promotion_allowed_true")
    if not bundle.not_for_decision_support:
        missing_requirements.append("not_for_decision_support_false")

    surfaced_assumptions = _dedupe_strings(
        [
            *(card.description for card in bundle.assumption_cards),
            *(f"latent_environment_assumption:{value}" for value in bundle.inducing_environments),
            *(
                f"latent_identification_condition:{value}"
                for value in bundle.identification_conditions
            ),
            *_proxy_boundary_notes(bundle.metadata),
        ]
    )
    surfaced_falsification_tests = _dedupe_strings(list(bundle.falsification_tests))
    no_promotion_reasons = _dedupe_strings(
        [
            *list(bundle.no_promotion_reasons),
            *_proxy_boundary_no_promotion_reasons(bundle.metadata),
            "latent_discovery_proof_only",
        ]
    )

    return LatentGovernanceAssessment(
        valid=not missing_requirements,
        human_gate_required=bool(bundle.human_gate_required),
        not_for_decision_support=bool(bundle.not_for_decision_support),
        missing_requirements=missing_requirements,
        surfaced_assumptions=surfaced_assumptions,
        surfaced_falsification_tests=surfaced_falsification_tests,
        no_promotion_reasons=no_promotion_reasons,
        metadata={
            "trust_level": bundle.trust_level.value,
            "readiness_cap": bundle.readiness_cap,
            "proposed_latent_nodes": list(bundle.proposed_latent_nodes),
            "inducing_environments": list(bundle.inducing_environments),
            "identification_conditions": list(bundle.identification_conditions),
        },
    )


def latent_governance_metadata(
    bundle: LatentDiscoveryBundle | None,
) -> dict[str, Any] | None:
    """Latent governance metadata helper."""
    assessment = assess_latent_governance(bundle)
    if assessment is None:
        return None
    return assessment.model_dump(mode="json")


def _proxy_boundary_notes(metadata: dict[str, Any]) -> list[str]:
    payload = metadata.get("proxy_boundary")
    if not isinstance(payload, dict):
        return []
    notes = payload.get("boundary_notes", [])
    if not isinstance(notes, list):
        return []
    return [str(item) for item in notes if str(item).strip()]


def _proxy_boundary_no_promotion_reasons(metadata: dict[str, Any]) -> list[str]:
    payload = metadata.get("proxy_boundary")
    if not isinstance(payload, dict):
        return []
    reasons = payload.get("no_promotion_reasons", [])
    if not isinstance(reasons, list):
        return []
    return [str(item) for item in reasons if str(item).strip()]


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


__all__ = [
    "LatentGovernanceAssessment",
    "assess_latent_governance",
    "latent_governance_metadata",
]
