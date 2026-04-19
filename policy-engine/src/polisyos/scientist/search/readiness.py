"""Decision-readiness contracts for promoted policy artifacts."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.ir.analytics.causal import DataReadinessReport, load_data_readiness_report
from polisyos.ir.analytics.cross_graph import CrossGraphEvidenceProfile, EvidenceSourceState
from polisyos.scientist.discovery.priors import PriorKnowledgeBundle
from polisyos.scientist.policy_design.objectives import ConstraintStatus, PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from polisyos.scientist.search.artifact_minimality import (
    ArtifactFunction,
    ArtifactMinimalityMixin,
    artifact_functions_field,
)
from polisyos.scientist.search.uncertainty import UncertaintyEnvelope, UncertaintyType

if TYPE_CHECKING:
    from polisyos.scientist.search.judge_stack import JudgeName, JudgeVerdict

READINESS_CONTRACT_SCHEMA_NAME = "polisyos.scientist.search.DecisionReadinessContract"


class DecisionReadiness(str, Enum):
    """Decision readiness public type."""
    RESEARCH_ARTIFACT = "research_artifact"
    ANALYST_ADVISORY = "analyst_advisory"
    EXTERNAL_BRIEFING = "external_briefing"
    SIMULATION_READY = "simulation_ready"
    RECOMMENDATION_READY = "recommendation_ready"
    DEPLOYMENT_READY = "deployment_ready"


class ReadinessRequirement(BaseModel):
    """Versioned operational requirement for one readiness level."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    readiness_level: DecisionReadiness
    required_judges_passed: list[str]
    required_uncertainty_bounds: dict[UncertaintyType, float]
    mandatory_human_gate: bool
    evidence_depth_required: str
    replicated_evidence_required: bool = False
    senior_human_gate_required: bool = False


class ReadinessAssessment(BaseModel):
    """Per-level assessment result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    readiness_level: DecisionReadiness
    passed: bool
    reasons: list[str] = Field(default_factory=list)


class DecisionReadinessContract(ArtifactMinimalityMixin):
    """Persisted readiness payload attached to promotion metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.PROMOTION_GATING,
            ArtifactFunction.REPLAY_AUDIT,
        )
    )
    readiness_level: DecisionReadiness
    required_judges_passed: list[str]
    required_uncertainty_bounds: dict[UncertaintyType, float]
    mandatory_human_gate: bool
    assumptions_must_be_surfaced: list[str]
    expiry_conditions: list[str]
    evidence_depth_required: str
    assessments: list[ReadinessAssessment] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class DecisionReadinessEvaluator:
    """Top-down readiness evaluator with versioned defaults."""

    def __init__(
        self,
        *,
        requirements: list[ReadinessRequirement] | None = None,
        store: FileSystemCAS | None = None,
    ) -> None:
        self._requirements = requirements or self.default_requirements()
        self._store = store

    @staticmethod
    def default_requirements() -> list[ReadinessRequirement]:
        return [
            ReadinessRequirement(
                readiness_level=DecisionReadiness.DEPLOYMENT_READY,
                required_judges_passed=[
                    "structural",
                    "statistical",
                    "robustness",
                    "governance",
                    "reproducibility",
                    "compute",
                ],
                required_uncertainty_bounds=_uncertainty_bounds(0.1, 0.2),
                mandatory_human_gate=True,
                evidence_depth_required="replicated",
                replicated_evidence_required=True,
                senior_human_gate_required=True,
            ),
            ReadinessRequirement(
                readiness_level=DecisionReadiness.RECOMMENDATION_READY,
                required_judges_passed=[
                    "structural",
                    "statistical",
                    "robustness",
                    "governance",
                    "reproducibility",
                    "compute",
                ],
                required_uncertainty_bounds=_uncertainty_bounds(0.2, 0.3),
                mandatory_human_gate=True,
                evidence_depth_required="meta_analytic",
            ),
            ReadinessRequirement(
                readiness_level=DecisionReadiness.SIMULATION_READY,
                required_judges_passed=[
                    "structural",
                    "statistical",
                    "robustness",
                    "reproducibility",
                ],
                required_uncertainty_bounds=_uncertainty_bounds(0.3, 0.4),
                mandatory_human_gate=False,
                evidence_depth_required="single_study",
            ),
            ReadinessRequirement(
                readiness_level=DecisionReadiness.EXTERNAL_BRIEFING,
                required_judges_passed=[
                    "structural",
                    "statistical",
                    "robustness",
                    "governance",
                    "reproducibility",
                ],
                required_uncertainty_bounds=_uncertainty_bounds(0.3, 0.5),
                mandatory_human_gate=True,
                evidence_depth_required="single_study",
            ),
            ReadinessRequirement(
                readiness_level=DecisionReadiness.ANALYST_ADVISORY,
                required_judges_passed=[
                    "structural",
                    "statistical",
                    "reproducibility",
                ],
                required_uncertainty_bounds=_uncertainty_bounds(0.5, 0.7),
                mandatory_human_gate=False,
                evidence_depth_required="single_study",
            ),
            ReadinessRequirement(
                readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
                required_judges_passed=["structural", "reproducibility"],
                required_uncertainty_bounds=_uncertainty_bounds(1.0, 1.0),
                mandatory_human_gate=False,
                evidence_depth_required="single_study",
            ),
        ]

    def evaluate(
        self,
        *,
        candidate: PolicyCandidateSchema,
        judge_verdict: "JudgeVerdict",
        uncertainty_envelope: UncertaintyEnvelope,
        evaluation_vector: PolicyEvaluationVector | None = None,
        cross_graph_profile: CrossGraphEvidenceProfile | None = None,
        prior_knowledge_bundle: PriorKnowledgeBundle | None = None,
        evidence_support_summary: dict[str, object] | None = None,
        evidence_metadata: dict[str, object] | None = None,
        data_readiness_report: DataReadinessReport | None = None,
        data_readiness_report_ref: ArtifactRef | None = None,
        claim_mode: Literal["proof_only", "bounds", "estimation"] = "estimation",
    ) -> DecisionReadinessContract:
        pending_human_gate = judge_verdict.composite_decision == "defer_to_human"
        support_summary = _resolve_evidence_support_summary(
            prior_knowledge_bundle,
            explicit_summary=evidence_support_summary,
        )
        actual_evidence_depth = _resolve_evidence_depth(
            candidate,
            evaluation_vector,
            prior_knowledge_bundle=prior_knowledge_bundle,
            evidence_support_summary=support_summary,
        )
        runtime_metadata = dict(evidence_metadata or {})
        latent_governance = _resolve_latent_governance(runtime_metadata)
        latent_resolution_error = _resolve_latent_discovery_resolution_error(runtime_metadata)
        resolved_data_readiness = data_readiness_report
        if (
            resolved_data_readiness is None
            and data_readiness_report_ref is not None
            and self._store is not None
        ):
            try:
                resolved_data_readiness = load_data_readiness_report(
                    self._store,
                    data_readiness_report_ref,
                )
            except Exception:
                resolved_data_readiness = None
        resolved_dp_robustness = _resolve_dp_robustness_summary(
            runtime_metadata,
            data_readiness_report=resolved_data_readiness,
        )
        readiness_cap_reason = None
        promotable_source = bool(runtime_metadata.get("promotable_source", True))
        degradation_mode = str(runtime_metadata.get("degradation_mode") or "").strip().lower()
        if latent_resolution_error is not None:
            readiness_cap_reason = "latent_discovery_bundle_unreadable"
        elif latent_governance is not None:
            readiness_cap_reason = "latent_discovery_proof_only"
        elif not promotable_source:
            readiness_cap_reason = "evaluation_source_not_promotable"
        elif degradation_mode in {"research_only", "no_promotion"}:
            readiness_cap_reason = "evaluation_degradation_mode"
        elif claim_mode != "proof_only" and resolved_data_readiness is not None:
            if resolved_data_readiness.decision in {"block", "unknown"}:
                readiness_cap_reason = _dp_readiness_cap_reason(
                    resolved_dp_robustness,
                    default="data_readiness_blocked",
                )
            elif resolved_data_readiness.decision == "warn":
                readiness_cap_reason = _dp_readiness_cap_reason(
                    resolved_dp_robustness,
                    default="data_readiness_warn",
                )
        readiness_cap = _resolve_readiness_cap(
            runtime_metadata,
            data_readiness_report=resolved_data_readiness,
            claim_mode=claim_mode,
        )

        assessments: list[ReadinessAssessment] = []
        selected = self._requirements[-1]
        for requirement in self._requirements:
            reasons = _assessment_failures(
                requirement=requirement,
                judge_verdict=judge_verdict,
                uncertainty_envelope=uncertainty_envelope,
                actual_evidence_depth=actual_evidence_depth,
                pending_human_gate=pending_human_gate,
            )
            if readiness_cap is not None and requirement.readiness_level != readiness_cap:
                reasons = [*reasons, f"readiness_capped:{readiness_cap.value}"]
            passed = not reasons
            assessments.append(
                ReadinessAssessment(
                    readiness_level=requirement.readiness_level,
                    passed=passed,
                    reasons=reasons,
                )
            )
            if passed:
                selected = requirement
                break

        surfaced = _surface_assumptions(
            candidate=candidate,
            evaluation_vector=evaluation_vector,
            judge_verdict=judge_verdict,
            cross_graph_profile=cross_graph_profile,
            prior_knowledge_bundle=prior_knowledge_bundle,
            evidence_support_summary=support_summary,
            actual_evidence_depth=actual_evidence_depth,
        )
        if latent_governance is not None:
            surfaced = _dedupe_strings(
                [
                    *surfaced,
                    *list(latent_governance.get("surfaced_assumptions", [])),
                    *(
                        f"latent_falsification:{value}"
                        for value in latent_governance.get("surfaced_falsification_tests", [])
                    ),
                    *(
                        f"latent_no_promotion:{value}"
                        for value in latent_governance.get("no_promotion_reasons", [])
                    ),
                ]
            )
        expiry = _expiry_conditions(candidate)
        metadata = {
            "pending_human_gate": pending_human_gate,
            "actual_evidence_depth": actual_evidence_depth,
            "prior_evidence_invalidated": any(
                card.failure_type == "platform_meta_evaluation_failed"
                for card in judge_verdict.blocking_failures
            ),
            "evaluation_backend_kind": runtime_metadata.get("backend_kind"),
            "evaluation_fidelity_mode": runtime_metadata.get("fidelity_mode"),
            "evaluation_promotable_source": runtime_metadata.get("promotable_source", True),
            "evaluation_degradation_mode": runtime_metadata.get("degradation_mode"),
            "evaluation_provenance_notes": list(runtime_metadata.get("notes", []) or []),
            "claim_mode": claim_mode,
            "prior_knowledge_status": (
                prior_knowledge_bundle.status if prior_knowledge_bundle is not None else "missing"
            ),
            "evidence_support_summary": support_summary,
            "cross_graph_source_statuses": (
                {
                    key: value.status.value
                    for key, value in (cross_graph_profile.source_statuses.items() if cross_graph_profile is not None else [])
                }
            ),
        }
        if latent_governance is not None:
            metadata["latent_governance"] = dict(latent_governance)
            metadata["latent_falsification_tests"] = list(
                latent_governance.get("surfaced_falsification_tests", [])
            )
            metadata["latent_no_promotion_reasons"] = list(
                latent_governance.get("no_promotion_reasons", [])
            )
            metadata["not_for_decision_support"] = bool(
                latent_governance.get("not_for_decision_support", True)
            )
        if latent_resolution_error is not None:
            metadata["latent_discovery_resolution_error"] = dict(latent_resolution_error)
        if readiness_cap is not None:
            metadata["readiness_cap"] = readiness_cap.value
            metadata["readiness_cap_reason"] = readiness_cap_reason or "unspecified"
        if resolved_data_readiness is not None:
            metadata["data_readiness_decision"] = resolved_data_readiness.decision
            metadata["data_readiness_can_run_estimation"] = (
                resolved_data_readiness.can_run_estimation
            )
        if resolved_dp_robustness is not None:
            metadata["dp_effective_status"] = resolved_dp_robustness["effective_status"]
            metadata["dp_block_reason"] = resolved_dp_robustness.get("block_reason")
            if resolved_dp_robustness.get("distortion_radius") is not None:
                metadata["dp_distortion_radius"] = resolved_dp_robustness["distortion_radius"]
            if resolved_dp_robustness.get("mechanism_family") is not None:
                metadata["dp_mechanism_family"] = resolved_dp_robustness["mechanism_family"]
            if resolved_dp_robustness.get("effect_interval") is not None:
                metadata["dp_effect_interval"] = resolved_dp_robustness["effect_interval"]
            metadata["dp_robustness"] = dict(resolved_dp_robustness)
        if data_readiness_report_ref is not None:
            metadata["data_readiness_report_ref"] = data_readiness_report_ref.model_dump(
                mode="json"
            )

        return DecisionReadinessContract(
            readiness_level=selected.readiness_level,
            required_judges_passed=list(selected.required_judges_passed),
            required_uncertainty_bounds=dict(selected.required_uncertainty_bounds),
            mandatory_human_gate=selected.mandatory_human_gate,
            assumptions_must_be_surfaced=surfaced,
            expiry_conditions=expiry,
            evidence_depth_required=selected.evidence_depth_required,
            assessments=assessments,
            metadata=metadata,
        )


def persist_decision_readiness_contract(
    store: FileSystemCAS,
    contract: DecisionReadinessContract,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist decision readiness contract helper."""
    return store.put_json(
        contract,
        PutOptions(
            kind="scientist.decision_readiness_contract",
            media_type="application/json",
            schema=SchemaInfo(
                name=READINESS_CONTRACT_SCHEMA_NAME,
                version=contract.schema_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_decision_readiness_contract(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> DecisionReadinessContract:
    """Load decision readiness contract."""
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return DecisionReadinessContract.model_validate(payload)


def _uncertainty_bounds(
    statistical: float,
    structural: float,
) -> dict[UncertaintyType, float]:
    return {
        UncertaintyType.STATISTICAL: statistical,
        UncertaintyType.STRUCTURAL: structural,
        UncertaintyType.TRANSPORT: structural,
        UncertaintyType.MEASUREMENT: statistical,
        UncertaintyType.MODEL: structural,
        UncertaintyType.OPTIMIZATION: structural,
    }


def _assessment_failures(
    *,
    requirement: ReadinessRequirement,
    judge_verdict: "JudgeVerdict",
    uncertainty_envelope: UncertaintyEnvelope,
    actual_evidence_depth: str,
    pending_human_gate: bool,
) -> list[str]:
    reasons: list[str] = []
    for judge_name in requirement.required_judges_passed:
        judge = judge_verdict.per_judge.get(judge_name)
        if judge is None or not judge.passed:
            reasons.append(f"judge_failed:{judge_name}")

    for uncertainty_type, threshold in requirement.required_uncertainty_bounds.items():
        observed = uncertainty_envelope.uncertainties[uncertainty_type].level
        if observed > threshold:
            reasons.append(
                f"uncertainty_exceeded:{uncertainty_type.value}:{observed:.3f}>{threshold:.3f}"
            )

    if requirement.mandatory_human_gate and pending_human_gate:
        reasons.append("mandatory_human_gate_pending")

    depth_rank = {"single_study": 1, "meta_analytic": 2, "replicated": 3}
    if depth_rank.get(actual_evidence_depth, 0) < depth_rank.get(
        requirement.evidence_depth_required,
        0,
    ):
        reasons.append(
            f"evidence_depth:{actual_evidence_depth}<{requirement.evidence_depth_required}"
        )

    if requirement.replicated_evidence_required and actual_evidence_depth != "replicated":
        reasons.append("replicated_evidence_required")

    return reasons


def _resolve_readiness_cap(
    evidence_metadata: dict[str, object],
    *,
    data_readiness_report: DataReadinessReport | None = None,
    claim_mode: Literal["proof_only", "bounds", "estimation"] = "estimation",
) -> DecisionReadiness | None:
    if _resolve_latent_discovery_resolution_error(evidence_metadata) is not None:
        return DecisionReadiness.RESEARCH_ARTIFACT
    if _resolve_latent_governance(evidence_metadata) is not None:
        return DecisionReadiness.RESEARCH_ARTIFACT
    promotable_source = bool(evidence_metadata.get("promotable_source", True))
    degradation_mode = str(evidence_metadata.get("degradation_mode") or "").strip().lower()
    if not promotable_source:
        return DecisionReadiness.RESEARCH_ARTIFACT
    if degradation_mode in {"research_only", "no_promotion"}:
        return DecisionReadiness.RESEARCH_ARTIFACT
    if claim_mode == "proof_only":
        return None
    if data_readiness_report is not None:
        if data_readiness_report.decision in {"block", "unknown"}:
            return DecisionReadiness.RESEARCH_ARTIFACT
        if data_readiness_report.decision == "warn":
            return DecisionReadiness.ANALYST_ADVISORY
    return None


def _resolve_latent_governance(
    evidence_metadata: dict[str, object],
) -> dict[str, object] | None:
    payload = evidence_metadata.get("latent_governance")
    if not isinstance(payload, dict) or not payload.get("active", False):
        return None
    return payload


def _resolve_latent_discovery_resolution_error(
    evidence_metadata: dict[str, object],
) -> dict[str, object] | None:
    payload = evidence_metadata.get("latent_discovery_resolution_error")
    if not isinstance(payload, dict):
        return None
    return payload


def _resolve_dp_robustness_summary(
    evidence_metadata: dict[str, object],
    *,
    data_readiness_report: DataReadinessReport | None = None,
) -> dict[str, object] | None:
    if isinstance(getattr(data_readiness_report, "dp_distortion", None), dict):
        return dict(data_readiness_report.dp_distortion)
    payload = evidence_metadata.get("dp_robustness")
    if not isinstance(payload, dict):
        return None
    effective_status = payload.get("effective_status") or payload.get("dp_effective_status")
    if effective_status is None:
        return None
    return dict(payload)


def _dp_readiness_cap_reason(
    dp_robustness: dict[str, object] | None,
    *,
    default: str,
) -> str:
    if not isinstance(dp_robustness, dict):
        return default
    status = str(dp_robustness.get("effective_status") or "").strip().lower()
    if status == "bounded":
        return "dp_bounds_only"
    if status == "unidentifiable":
        return "dp_release_unidentifiable"
    if status == "blocked":
        block_reason = dp_robustness.get("block_reason")
        if block_reason is not None:
            return f"dp_release_blocked:{block_reason}"
        return "dp_release_blocked"
    return default


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


def _resolve_evidence_depth(
    candidate: PolicyCandidateSchema,
    evaluation_vector: PolicyEvaluationVector | None,
    *,
    prior_knowledge_bundle: PriorKnowledgeBundle | None,
    evidence_support_summary: dict[str, object],
) -> str:
    raw = str(candidate.metadata.get("evidence_depth", "")).strip().lower()
    if raw in {"single_study", "meta_analytic", "replicated"}:
        requested = raw
    elif bool(candidate.metadata.get("replicated_evidence")):
        requested = "replicated"
    else:
        requested = ""
    if evaluation_vector is not None:
        score = evaluation_vector.secondary.get("evidence_depth")
        if not requested and score is not None and score.value >= 0.8:
            requested = "meta_analytic"
    if requested in {"meta_analytic", "replicated"} and not _supports_advanced_evidence_depth(
        prior_knowledge_bundle,
        evidence_support_summary=evidence_support_summary,
    ):
        return "single_study"
    return requested or "single_study"


def _surface_assumptions(
    *,
    candidate: PolicyCandidateSchema,
    evaluation_vector: PolicyEvaluationVector | None,
    judge_verdict: "JudgeVerdict",
    cross_graph_profile: CrossGraphEvidenceProfile | None,
    prior_knowledge_bundle: PriorKnowledgeBundle | None,
    evidence_support_summary: dict[str, object],
    actual_evidence_depth: str,
) -> list[str]:
    surfaced: list[str] = []
    for assumption in candidate.evidence_assumptions:
        surfaced.append(assumption.description)
    for assumption in candidate.transport_assumptions:
        surfaced.append(assumption.description)
        surfaced.extend(assumption.caveats)
    for assumption in candidate.trinity_bundle.model_spec.assumptions:
        surfaced.append(assumption.description)
    if evaluation_vector is not None:
        for name, status in evaluation_vector.constraint_statuses.items():
            if status is ConstraintStatus.NEAR_BINDING:
                surfaced.append(f"Hard constraint near binding: {name}")
    surfaced.extend(_evidence_channel_notes(cross_graph_profile, prior_knowledge_bundle))
    requested_depth = str(candidate.metadata.get("evidence_depth", "")).strip().lower()
    if requested_depth in {"meta_analytic", "replicated"} and actual_evidence_depth == "single_study":
        surfaced.append(
            "Evidence depth remains single_study because academic prior support coverage is unavailable or incomplete."
        )
    if not evidence_support_summary.get("available", False):
        surfaced.append("Academic prior support channel is unavailable for this run.")
    surfaced.extend(card.description for card in judge_verdict.blocking_failures)
    surfaced.extend(card.description for card in judge_verdict.warnings if card.is_blocker)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in surfaced:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _resolve_evidence_support_summary(
    prior_knowledge_bundle: PriorKnowledgeBundle | None,
    *,
    explicit_summary: dict[str, object] | None,
) -> dict[str, object]:
    if explicit_summary:
        return dict(explicit_summary)
    if prior_knowledge_bundle is None:
        return {
            "available": False,
            "status": "missing",
            "resolved_edges": 0,
            "total_edges": 0,
            "coverage_ratio": 0.0,
        }
    total_edges = len(prior_knowledge_bundle.query_edge_keys)
    unresolved_edges = len(prior_knowledge_bundle.unresolved_edges)
    resolved_edges = max(total_edges - unresolved_edges, 0)
    coverage_ratio = (
        float(resolved_edges / total_edges)
        if total_edges > 0
        else (1.0 if prior_knowledge_bundle.status == "ok" else 0.0)
    )
    return {
        "available": prior_knowledge_bundle.status == "ok",
        "status": prior_knowledge_bundle.status,
        "resolved_edges": resolved_edges,
        "total_edges": total_edges,
        "coverage_ratio": coverage_ratio,
    }


def _supports_advanced_evidence_depth(
    prior_knowledge_bundle: PriorKnowledgeBundle | None,
    *,
    evidence_support_summary: dict[str, object],
) -> bool:
    if prior_knowledge_bundle is None or prior_knowledge_bundle.status != "ok":
        return False
    return bool(evidence_support_summary.get("available", False)) and float(
        evidence_support_summary.get("coverage_ratio", 0.0) or 0.0
    ) >= 0.8


def _evidence_channel_notes(
    cross_graph_profile: CrossGraphEvidenceProfile | None,
    prior_knowledge_bundle: PriorKnowledgeBundle | None,
) -> list[str]:
    notes: list[str] = []
    if cross_graph_profile is not None:
        for source_name, status in cross_graph_profile.source_statuses.items():
            if status.status is EvidenceSourceState.AVAILABLE:
                continue
            notes.append(
                f"Evidence channel unavailable: {source_name} ({status.status.value})."
            )
    if prior_knowledge_bundle is not None:
        for source_name, status in prior_knowledge_bundle.source_statuses.items():
            if status.status is EvidenceSourceState.AVAILABLE:
                continue
            notes.append(
                f"Prior knowledge source unavailable: {source_name} ({status.status.value})."
            )
    return notes


def _expiry_conditions(candidate: PolicyCandidateSchema) -> list[str]:
    return [
        "upstream_CAS_inputs_changed",
        "freshness_violation_detected",
        "hidden_holdout_or_calibration_rotation_invalidated_prior_evidence",
        "governance_or_legal_regime_changed",
        f"trinity_bundle_changed:{candidate.trinity_bundle.problem_frame.problem_id}",
    ]


__all__ = [
    "DecisionReadiness",
    "DecisionReadinessContract",
    "DecisionReadinessEvaluator",
    "ReadinessAssessment",
    "ReadinessRequirement",
    "load_decision_readiness_contract",
    "persist_decision_readiness_contract",
]
