"""Pure policy-runtime metric projections and input parsing."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.foundry.methods.catalog.optimization.protocols import AmbiguityCertificate
from polisyos.ir.analytics import CausalEffectReport, DistributionalReport
from polisyos.ir.analytics.cross_graph import CrossGraphEvidenceProfile, TransportStatus
from polisyos.scientist.methods.search.uncertainty import UncertaintyEnvelope, UncertaintyType
from polisyos.scientist.policy_design.objectives import _normalize_policy_evaluation_vector

if TYPE_CHECKING:
    from polisyos.scientist.governance.report import GovernanceReport
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
        PolicyRuntimeProvenance,
    )
    from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

_POLICY_RUNTIME_VALIDATION_ERRORS = (TypeError, ValidationError, ValueError)
_POLICY_RUNTIME_LOAD_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)


def _build_runtime_simulation_metrics(
    candidate: PolicyCandidateSchema,
    *,
    fidelity: str,
    governance_report: GovernanceReport | None,
    distributional_report: DistributionalReport | None,
) -> dict[str, float]:
    payload = candidate.model_dump(mode="json")
    canon = to_canonical_bytes(payload, CanonSpec(forbid_floats=False))
    digest = hashlib.sha256(canon).digest()
    basis = int.from_bytes(digest[:8], byteorder="big") / float(2**64 - 1)

    interventions = list(candidate.trinity_bundle.policy_spec.interventions)
    parameters = list(candidate.trinity_bundle.policy_spec.parameters)
    objectives = list(candidate.trinity_bundle.problem_frame.objectives)
    fidelity_scale = {
        "selection": 0.78,
        "medium": 0.88,
        "full": 1.0,
    }.get(fidelity, 1.0)
    governance_issue_count = float(len(getattr(governance_report, "issues", None) or []))
    subgroup_count = float(len(getattr(distributional_report, "subgroup_reports", None) or []))

    policy_value = max(
        -1.0,
        min(
            1.5,
            (0.35 + basis)
            + (0.08 * len(interventions))
            + (0.03 * len(parameters))
            - (0.04 * governance_issue_count),
        ),
    )
    employment = max(
        -1.0,
        min(
            1.5,
            (0.25 + basis * 0.8) + (0.02 * len(objectives)) - (0.015 * subgroup_count),
        ),
    )
    welfare = (policy_value * 0.65) + (employment * 0.35)
    budget_penalty = max(0.0, (len(parameters) * 0.05) + (len(interventions) * 0.08))

    return {
        "policy_value": policy_value * fidelity_scale,
        "employment": employment * fidelity_scale,
        "welfare": welfare * fidelity_scale,
        "net_social_welfare": welfare * fidelity_scale,
        "gdp_change": welfare * fidelity_scale,
        "gov_balance": -budget_penalty * fidelity_scale,
        "budget_penalty": budget_penalty,
    }


def _build_evidence_driven_simulation_metrics(
    candidate: PolicyCandidateSchema,
    *,
    fidelity: str,
    simulation_metrics: dict[str, float] | None,
    uncertainty: UncertaintyEnvelope | None,
    distributional_report: DistributionalReport | None,
    causal_effect_report: CausalEffectReport | None,
    cross_graph_profile: CrossGraphEvidenceProfile | None,
    governance_report: GovernanceReport | None,
) -> tuple[dict[str, float], tuple[str, ...], tuple[str, ...]]:
    metrics = {
        key: float(value)
        for key, value in dict(simulation_metrics or {}).items()
        if isinstance(value, (int, float))
    }
    source_components: list[str] = []
    notes: list[str] = []

    if metrics:
        source_components.append("metrics_artifact")

    fidelity_scale = {
        "selection": 0.78,
        "medium": 0.86,
        "full": 1.0,
    }.get(fidelity, 1.0)

    point_estimate = _apply_policy_value_metrics(
        metrics,
        causal_effect_report=causal_effect_report,
        source_components=source_components,
        notes=notes,
    )
    _apply_distributional_and_budget_metrics(
        metrics,
        candidate=candidate,
        point_estimate=point_estimate,
        distributional_report=distributional_report,
        cross_graph_profile=cross_graph_profile,
        governance_report=governance_report,
        source_components=source_components,
    )
    _apply_uncertainty_metrics(
        metrics,
        causal_effect_report=causal_effect_report,
        uncertainty=uncertainty,
        governance_report=governance_report,
        source_components=source_components,
    )

    scaled = {
        key: (
            float(value) * fidelity_scale
            if key not in {"budget_penalty", "ci_width"}
            else float(value)
        )
        for key, value in metrics.items()
    }
    return scaled, tuple(dict.fromkeys(source_components)), tuple(notes)


def _apply_policy_value_metrics(
    metrics: dict[str, float],
    *,
    causal_effect_report: CausalEffectReport | None,
    source_components: list[str],
    notes: list[str],
) -> float:
    """Fill the policy value from its causal or metric evidence."""
    point_estimate = None
    if (
        causal_effect_report is not None
        and getattr(causal_effect_report, "point_estimate", None) is not None
    ):
        point_estimate = float(causal_effect_report.point_estimate)
        source_components.append("causal_effect_report")
    elif "ate" in metrics:
        point_estimate = float(metrics["ate"])

    if point_estimate is None:
        point_estimate = 0.0
        notes.append("Missing causal effect report; using conservative zero-effect baseline.")

    if "policy_value" not in metrics:
        metrics["policy_value"] = point_estimate
    return point_estimate


def _apply_distributional_and_budget_metrics(
    metrics: dict[str, float],
    *,
    candidate: PolicyCandidateSchema,
    point_estimate: float,
    distributional_report: DistributionalReport | None,
    cross_graph_profile: CrossGraphEvidenceProfile | None,
    governance_report: GovernanceReport | None,
    source_components: list[str],
) -> None:
    """Fill employment, welfare, budget, and related output metrics."""
    if "employment" not in metrics:
        metrics["employment"] = _employment_signal_from_distribution(
            distributional_report,
            fallback=point_estimate * 0.6,
        )
        if distributional_report is not None:
            source_components.append("distributional_report")

    if cross_graph_profile is not None:
        source_components.append("cross_graph_profile")

    if "welfare" not in metrics:
        inequality_penalty = _distributional_shift_penalty(distributional_report)
        governance_penalty = 0.05 * float(len(getattr(governance_report, "issues", None) or []))
        transport_penalty = _transport_penalty(cross_graph_profile)
        metrics["welfare"] = (
            metrics["policy_value"] * 0.65
            + metrics["employment"] * 0.35
            - inequality_penalty
            - governance_penalty
            - transport_penalty
        )

    budget_total = _policy_budget_total(candidate)
    budget_penalty = float(metrics.get("budget_penalty", min(1.0, budget_total / 1000.0)))
    metrics["budget_penalty"] = budget_penalty
    metrics.setdefault("gov_balance", -abs(budget_penalty))
    metrics.setdefault("net_social_welfare", metrics["welfare"])
    metrics.setdefault("gdp_change", metrics["welfare"])
    metrics.setdefault("ate", point_estimate)


def _apply_uncertainty_metrics(
    metrics: dict[str, float],
    *,
    causal_effect_report: CausalEffectReport | None,
    uncertainty: UncertaintyEnvelope | None,
    governance_report: GovernanceReport | None,
    source_components: list[str],
) -> None:
    """Project interval and source-component details onto the metric result."""
    ci_width = None
    if causal_effect_report is not None and getattr(
        causal_effect_report, "confidence_interval", None
    ):
        low, high = causal_effect_report.confidence_interval
        try:
            ci_width = abs(float(high) - float(low))
        except (TypeError, ValueError):
            ci_width = None
    if ci_width is None and isinstance(uncertainty, UncertaintyEnvelope):
        ci_width = max(
            0.08,
            float(uncertainty.uncertainties[UncertaintyType.STATISTICAL].level) * 0.25,
        )
    if ci_width is not None:
        metrics["ci_width"] = float(ci_width)
    if isinstance(uncertainty, UncertaintyEnvelope):
        source_components.append("uncertainty_envelope")
    if governance_report is not None:
        source_components.append("governance_report")

    return


def _parse_policy_evaluation(value: Any) -> PolicyEvaluationVector | None:
    try:
        return _normalize_policy_evaluation_vector(value, allow_mapping=isinstance(value, Mapping))
    except _POLICY_RUNTIME_VALIDATION_ERRORS:
        return None


def _parse_ambiguity_certificate(value: Any) -> AmbiguityCertificate | None:
    if isinstance(value, AmbiguityCertificate):
        return value
    if isinstance(value, Mapping):
        payload: Mapping[str, Any] = value
        nested = payload.get("ambiguity_certificate")
        if isinstance(nested, Mapping) or isinstance(nested, AmbiguityCertificate):
            nested_certificate = _parse_ambiguity_certificate(nested)
            if nested_certificate is not None:
                return nested_certificate
        try:
            return AmbiguityCertificate.from_mapping(payload)
        except _POLICY_RUNTIME_VALIDATION_ERRORS:
            return None
    return None


def _ambiguity_certificate_payload(
    value: AmbiguityCertificate | dict[str, Any] | None,
) -> dict[str, Any] | None:
    certificate = _parse_ambiguity_certificate(value)
    if certificate is not None:
        return certificate.to_payload()
    if isinstance(value, dict):
        return dict(value)
    return None


def _channel_higher_is_better(
    evaluation: PolicyEvaluationVector,
    name: str,
    *,
    fallback: float = 0.0,
) -> float:
    channel = evaluation.primary.get(name) or evaluation.secondary.get(name)
    if channel is None:
        return float(fallback)
    return float(channel.higher_is_better)


def _budget_pressure(evaluation: PolicyEvaluationVector) -> float:
    budget_channel = evaluation.hard_constraints.get("policy_budget_constraint")
    if budget_channel is None and evaluation.hard_constraints:
        budget_channel = next(iter(evaluation.hard_constraints.values()))
    if budget_channel is None:
        return 0.0
    return float(budget_channel.value)


def _employment_signal_from_distribution(
    distributional_report: DistributionalReport | None,
    *,
    fallback: float,
) -> float:
    if distributional_report is None:
        return float(fallback)
    winners_losers = getattr(distributional_report, "winners_losers", None)
    winners = list(getattr(winners_losers, "winners", None) or [])
    if not winners:
        return float(fallback)
    deltas = [float(getattr(item, "key_metric_delta", 0.0) or 0.0) for item in winners]
    if not deltas:
        return float(fallback)
    return float(sum(deltas) / max(len(deltas), 1))


def _distributional_shift_penalty(distributional_report: DistributionalReport | None) -> float:
    if distributional_report is None:
        return 0.0
    before = getattr(distributional_report, "overall_gini_before", None)
    after = getattr(distributional_report, "overall_gini_after", None)
    if before is None or after is None:
        return 0.0
    try:
        return max(0.0, float(after) - float(before))
    except (TypeError, ValueError):
        return 0.0


def _transport_penalty(cross_graph_profile: CrossGraphEvidenceProfile | None) -> float:
    if cross_graph_profile is None:
        return 0.0
    unsupported = sum(
        1
        for assessment in getattr(cross_graph_profile, "needs", None) or []
        if getattr(assessment, "transport_status", None) is TransportStatus.UNSUPPORTED
    )
    return min(0.25, unsupported * 0.05)


def _policy_budget_total(candidate: PolicyCandidateSchema) -> float:
    total = 0.0
    for allocation in candidate.budget_allocation:
        amount = getattr(allocation.amount, "amount", allocation.amount)
        try:
            total += float(amount)
        except (TypeError, ValueError):
            continue
    return total


def _selection_score_impl(evaluation_vector: PolicyEvaluationVector) -> float:
    """Return the primary policy-value score, preserving the support fallback order."""
    if "policy_value" in evaluation_vector.primary:
        return float(evaluation_vector.primary["policy_value"].value)
    if evaluation_vector.primary:
        return float(next(iter(evaluation_vector.primary.values())).value)
    return 0.0


def _build_policy_simulation_results_impl(
    evaluation: PolicyEvaluationVector,
    *,
    fidelity: str,
    uncertainty: UncertaintyEnvelope | None,
    base_metrics: dict[str, float] | None = None,
    provenance: PolicyRuntimeProvenance | None = None,
    ambiguity_certificate: AmbiguityCertificate | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build policy simulation results."""
    metrics = dict(base_metrics or {})
    policy_value = float(
        metrics.get("policy_value", _channel_higher_is_better(evaluation, "policy_value"))
    )
    employment = float(
        metrics.get("employment", _channel_higher_is_better(evaluation, "employment"))
    )
    welfare = float(
        metrics.get(
            "welfare", _channel_higher_is_better(evaluation, "welfare", fallback=policy_value)
        )
    )
    budget_pressure = float(metrics.get("budget_penalty", _budget_pressure(evaluation)))
    gov_balance = float(metrics.get("gov_balance", -abs(budget_pressure)))
    ate = float(metrics.get("ate", policy_value))
    statistical = (
        uncertainty.uncertainties.get(UncertaintyType.STATISTICAL)
        if isinstance(uncertainty, UncertaintyEnvelope)
        else None
    )
    ci_width = 0.12 if fidelity == "selection" else 0.1
    if statistical is not None:
        ci_width = max(
            ci_width,
            float(statistical.level) * (0.22 if fidelity == "full" else 0.34),
        )
    if not evaluation.feasible:
        ci_width = max(ci_width, 0.35)
    ambiguity_payload = _ambiguity_certificate_payload(ambiguity_certificate)
    return {
        "policy_value": policy_value,
        "employment": employment,
        "welfare": welfare,
        "net_social_welfare": float(metrics.get("net_social_welfare", welfare)),
        "gdp_change": float(metrics.get("gdp_change", welfare)),
        "gov_balance": gov_balance,
        "ate": ate,
        "bootstrap": {
            "ci_width": ci_width,
            "requested_draw_count": (
                500 if fidelity == "full" else (64 if fidelity == "medium" else 32)
            ),
            "requested_draw_source": "fidelity_default",
            "draw_execution_status": "not_instrumented",
            "attempted_draw_count": None,
            "successful_draw_count": None,
            "failed_draw_count": None,
            "unattempted_draw_count": None,
            "fidelity": fidelity,
        },
        "objective_channels": {
            name: channel.value for name, channel in evaluation.all_channels().items()
        },
        "blocking_reasons": list(evaluation.blocking_reasons),
        "fidelity": fidelity,
        "evaluation_backend_kind": provenance.backend_kind if provenance is not None else "unknown",
        "promotable_source": provenance.promotable_source if provenance is not None else None,
        "evaluation_degradation_mode": (
            provenance.degradation_mode if provenance is not None else None
        ),
        "evaluation_source_components": list(provenance.source_components)
        if provenance is not None
        else [],
        "ambiguity_certificate": ambiguity_payload,
        "ambiguity_certificate_status": (
            ambiguity_payload.get("overall_status") if isinstance(ambiguity_payload, dict) else None
        ),
    }
