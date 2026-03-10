from __future__ import annotations

from polisyos.academic.knowledge.skg_query import SKGQuery
from polisyos.academic.knowledge.skg_store import EVIDENCE_WEIGHTS
from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.literature import EvidenceParameter, EvidenceStrength, ParameterType
from polisyos.ir.analytics.parameters import ParameterApplicability
from polisyos.ir.analytics.transportability import (
    TransportabilityStatus,
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
        min_transport_confidence: float = 0.3,
    ) -> tuple[EvidenceParameter | None, ParameterApplicability]:
        candidates = self.skg.query_parameters(parameter_name, target_context=target_context)
        if not candidates:
            return None, self._no_evidence(parameter_name, target_context)

        scored: list[
            tuple[
                float,
                float,
                TransportabilityStatus,
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
                status = TransportabilityStatus.NON_TRANSPORTABLE
                distance = 1.0
            else:
                distance = source_context.distance_to(target_context)
                if distance < 0.1:
                    confidence = 0.95
                    status = TransportabilityStatus.DIRECT
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
                        status = TransportabilityStatus.DIRECT
                    else:
                        confidence = max(0.0, 1.0 - distance * 0.5)
                        status = TransportabilityStatus.TRANSPORTABLE

            adjusted_confidence = max(0.0, confidence * (1.0 - candidate.transport_penalty))
            evidence_weight = EVIDENCE_WEIGHTS.get(
                parameter.evidence_strength.value,
                EVIDENCE_WEIGHTS[EvidenceStrength.UNKNOWN.value],
            )
            score = float(adjusted_confidence) * float(evidence_weight)
            notes = list(candidate.transport_notes)
            if candidate.requires_expert_review and "requires_expert_review" not in notes:
                notes.append("requires_expert_review")
            scored.append(
                (
                    score,
                    float(adjusted_confidence),
                    status,
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
            best_notes = next(item[5] for item in sorted(scored, key=lambda item: item[1], reverse=True))
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
            transport_confidence=best_conf,
            context_distance=best_distance,
            is_applicable=True,
            adjustment_required=(
                best_status == TransportabilityStatus.TRANSPORTABLE or best_penalty > 0.0
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
            transport_status=TransportabilityStatus.NON_TRANSPORTABLE,
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
            transport_status=TransportabilityStatus.NON_TRANSPORTABLE,
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


__all__ = ["ParameterSelector"]
