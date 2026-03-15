from __future__ import annotations

from polisyos.academic.knowledge.skg_query import SKGQuery
from polisyos.academic.knowledge.skg_store import EVIDENCE_WEIGHTS
from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    EvidenceStatus,
    LegalStatus,
    ObservabilityStatus,
)
from polisyos.ir.analytics.literature import EvidenceParameter, EvidenceStrength, ParameterType
from polisyos.ir.analytics.parameters import ParameterApplicability
from polisyos.ir.analytics.transportability import (
    TransportabilityStatus,
    TransportMode,
    build_selection_diagram,
)


class ParameterSelector:
    """Select literature parameters for a target context with transportability weighting."""

    def __init__(self, skg_query: SKGQuery) -> None:
        self.skg = skg_query

    def select_for_context(
        self,
        parameter_name: str,
        target_context: ContextProfile,
        causal_graph: CausalGraphModel,
        cross_graph_profile: CrossGraphEvidenceProfile | None = None,
        min_transport_confidence: float = 0.3,
    ) -> tuple[EvidenceParameter | None, ParameterApplicability]:
        assessment = _resolve_parameter_assessment(cross_graph_profile, parameter_name)
        if assessment is not None:
            if assessment.legal_status is LegalStatus.PROHIBITED:
                return None, self._low_confidence(
                    parameter_name,
                    target_context,
                    confidence=0.0,
                    notes=["cross_graph_legal_prohibited"],
                )
            if assessment.evidence_status is EvidenceStatus.UNSUPPORTED:
                return None, self._low_confidence(
                    parameter_name,
                    target_context,
                    confidence=0.0,
                    notes=["cross_graph_evidence_unsupported"],
                )

        candidates = self.skg.query_parameters(parameter_name, target_context=target_context)
        if not candidates:
            return None, self._no_evidence(parameter_name, target_context)

        scored: list[
            tuple[
                float,
                float,
                TransportabilityStatus,
                TransportMode,
                float,
                float,
                tuple[str, ...],
                bool,
                EvidenceParameter,
            ]
        ] = []
        for candidate in candidates:
            parameter = candidate.parameter
            source_context = candidate.source_context
            if parameter.parameter_type is not ParameterType.QUANTITATIVE:
                continue

            if source_context is None:
                confidence = 0.3
                status = TransportabilityStatus.UNSUPPORTED
                mode = TransportMode.NONE
                distance = 1.0
            else:
                distance = source_context.distance_to(target_context)
                if distance < 0.1:
                    confidence = 0.95
                    status = TransportabilityStatus.IDENTIFIED
                    mode = TransportMode.DIRECT
                else:
                    selection_diagram = build_selection_diagram(
                        source_context,
                        target_context,
                        causal_graph,
                    )
                    if not selection_diagram.s_nodes:
                        confidence = _compute_final_confidence(
                            base=1.0,
                            distance=distance,
                            target_quantities=[],
                        )
                        status = TransportabilityStatus.IDENTIFIED
                        mode = TransportMode.DIRECT
                    else:
                        confidence = max(0.0, 1.0 - distance * 0.5)
                        status = TransportabilityStatus.IDENTIFIED
                        mode = TransportMode.TRANSPORT_FORMULA

            adjusted_confidence = max(0.0, confidence * (1.0 - candidate.transport_penalty))
            profile_penalty, profile_notes = _cross_graph_penalty(assessment)
            adjusted_confidence = max(0.0, adjusted_confidence * (1.0 - profile_penalty))
            evidence_weight = EVIDENCE_WEIGHTS.get(
                parameter.evidence_strength.value,
                EVIDENCE_WEIGHTS[EvidenceStrength.UNKNOWN.value],
            )
            layer_factor = 1.0 if candidate.source_layer in {"simulation_ready", "simulation"} else 0.72
            uncertainty_factor = 1.0
            if candidate.uncertainty_source == "heuristic":
                uncertainty_factor = 0.8
            elif parameter.confidence_interval is None and parameter.std_error is None:
                uncertainty_factor = 0.9
            score = float(adjusted_confidence) * float(evidence_weight) * layer_factor * uncertainty_factor
            notes = list(candidate.transport_notes)
            notes.extend(profile_notes)
            if candidate.source_layer not in {"simulation_ready", "simulation"}:
                notes.append(f"source_layer:{candidate.source_layer}")
            if candidate.uncertainty_source:
                notes.append(f"uncertainty_source:{candidate.uncertainty_source}")
            for flag in candidate.quality_flags:
                if flag not in notes:
                    notes.append(flag)
            if candidate.requires_expert_review and "requires_expert_review" not in notes:
                notes.append("requires_expert_review")
            scored.append(
                (
                    score,
                    float(adjusted_confidence),
                    status,
                    mode,
                    float(distance),
                    float(candidate.transport_penalty),
                    tuple(notes),
                    bool(candidate.requires_expert_review),
                    parameter,
                )
            )

        if not scored:
            return None, self._low_confidence(
                parameter_name,
                target_context,
                confidence=0.0,
                notes=["no_quantitative_candidates"],
            )

        filtered = [item for item in scored if item[1] >= float(min_transport_confidence)]
        if not filtered:
            best_confidence = max(item[1] for item in scored)
            best_notes = next(item[6] for item in sorted(scored, key=lambda item: item[1], reverse=True))
            return None, self._low_confidence(
                parameter_name,
                target_context,
                confidence=best_confidence,
                notes=list(best_notes),
            )

        filtered.sort(key=lambda item: item[0], reverse=True)
        (
            _,
            best_conf,
            best_status,
            best_mode,
            best_distance,
            best_penalty,
            best_notes,
            _requires_expert_review,
            best_parameter,
        ) = filtered[0]
        uncertainty_multiplier = 1.0 + (1.0 - best_conf) * 2.0 + best_penalty
        applicability = ParameterApplicability(
            parameter_id=best_parameter.name,
            target_context_id=target_context.context_id,
            transport_status=best_status,
            transport_mode=best_mode,
            transport_confidence=best_conf,
            context_distance=best_distance,
            is_applicable=True,
            adjustment_required=(
                best_mode is not TransportMode.DIRECT or best_penalty > 0.0
            ),
            uncertainty_multiplier=uncertainty_multiplier,
            recommended_value=best_parameter.value,
            transport_notes=list(best_notes),
        )
        return best_parameter, applicability

    @staticmethod
    def _no_evidence(
        parameter_name: str,
        target_context: ContextProfile,
    ) -> ParameterApplicability:
        return ParameterApplicability(
            parameter_id=parameter_name,
            target_context_id=target_context.context_id,
            transport_status=TransportabilityStatus.UNSUPPORTED,
            transport_mode=TransportMode.NONE,
            transport_confidence=0.0,
            context_distance=1.0,
            is_applicable=False,
            adjustment_required=True,
            uncertainty_multiplier=3.0,
            recommended_value=None,
            transport_notes=["no_relevant_sources", "requires_expert_review"],
        )

    @staticmethod
    def _low_confidence(
        parameter_name: str,
        target_context: ContextProfile,
        *,
        confidence: float,
        notes: list[str] | None = None,
    ) -> ParameterApplicability:
        bounded = max(0.0, min(1.0, float(confidence)))
        return ParameterApplicability(
            parameter_id=parameter_name,
            target_context_id=target_context.context_id,
            transport_status=TransportabilityStatus.UNSUPPORTED,
            transport_mode=TransportMode.NONE,
            transport_confidence=bounded,
            context_distance=1.0,
            is_applicable=False,
            adjustment_required=True,
            uncertainty_multiplier=1.0 + (1.0 - bounded) * 2.0,
            recommended_value=None,
            transport_notes=list(notes or []),
        )


def _compute_final_confidence(
    *,
    base: float,
    distance: float,
    target_quantities: list[str],
) -> float:
    distance_factor = 1.0 - min(max(distance, 0.0) * 0.3, 0.5)
    data_factor = 0.95 ** max(0, len(target_quantities))
    confidence = float(base) * distance_factor * data_factor
    if confidence < 0.0:
        return 0.0
    if confidence > 1.0:
        return 1.0
    return confidence


def _resolve_parameter_assessment(
    cross_graph_profile: CrossGraphEvidenceProfile | None,
    parameter_name: str,
):
    if cross_graph_profile is None:
        return None
    clean_name = str(parameter_name).strip()
    if not clean_name:
        return None
    for assessment in cross_graph_profile.needs:
        need = assessment.need
        if need.parameter_name == clean_name or need.param_path == clean_name:
            return assessment
    return None


def _cross_graph_penalty(assessment) -> tuple[float, list[str]]:
    if assessment is None:
        return 0.0, []
    penalty = 0.0
    notes: list[str] = []
    if assessment.legal_status is LegalStatus.CONSTRAINED:
        penalty += 0.10
        notes.append("cross_graph_legal_constrained")
    if assessment.observability_status is ObservabilityStatus.PROXY_ONLY:
        penalty += 0.10
        notes.append("cross_graph_proxy_only")
    if assessment.evidence_status is EvidenceStatus.INSUFFICIENT:
        penalty += 0.15
        notes.append("cross_graph_evidence_insufficient")
    elif assessment.evidence_status is EvidenceStatus.MIXED:
        penalty += 0.05
        notes.append("cross_graph_evidence_mixed")
    return min(0.35, penalty), notes


__all__ = ["ParameterSelector"]
