"""Parameter evidence contribution at the cross-graph assessment boundary."""

from types import SimpleNamespace
from typing import cast

import pytest

from polisyos.data_forge.read_api.academic import ParameterCandidate
from polisyos.ir.analytics.cross_graph import EvidenceNeed, EvidenceNeedType, EvidenceStatus
from polisyos.ir.analytics.literature import EvidenceParameter, EvidenceStrength
from polisyos.scientist.cross_graph import compiler


def _candidate(strength: object) -> ParameterCandidate:
    parameter = EvidenceParameter(name="p", value=1.0, confidence_interval=(0.0, 2.0))
    if isinstance(strength, EvidenceStrength):
        parameter = parameter.model_copy(update={"evidence_strength": strength})
    else:
        # Boundary/adaptor negative: the validated DTO does not admit None or alien enums.
        parameter = cast(
            "EvidenceParameter",
            SimpleNamespace(**{**parameter.model_dump(), "evidence_strength": strength}),
        )
    return ParameterCandidate(
        parameter=parameter, source_context=None, source_layer="simulation_ready"
    )


def test_parameter_candidate_mixed_batch_preserves_classes_without_contribution() -> None:
    """Catch unknown, absent or unrecognized inputs receiving a positive evidence score."""
    strengths = [*EvidenceStrength, None, SimpleNamespace(value="alien"), "rct"]
    candidates = [_candidate(strength) for strength in strengths]
    expected = {
        "rct": 1.0,
        "meta_analysis": 0.95,
        "quasi_natural": 0.8,
        "quasi_natural_event": 0.75,
        "panel_fe": 0.65,
        "structural": 0.55,
        "observational": 0.45,
        "cross_sectional": 0.35,
        "theoretical": 0.15,
        "unknown": 0.0,
    }
    assert [compiler._parameter_candidate_score(candidate) for candidate in candidates] == (
        pytest.approx([expected[strength.value] for strength in EvidenceStrength] + [0.0] * 3)
    )
    assert [candidate.parameter.evidence_strength for candidate in candidates] == strengths


def test_none_candidate_is_not_scored_as_unknown(monkeypatch) -> None:
    """Distinguish None from unknown even when a hypothetical unknown rule is positive."""
    monkeypatch.setattr(compiler, "_PARAMETER_EVIDENCE_WEIGHTS", {"unknown": 0.25}, raising=False)
    assert compiler._parameter_candidate_score(_candidate(EvidenceStrength.UNKNOWN)) == 0.25
    assert compiler._parameter_candidate_score(_candidate(None)) == 0.0
    assert compiler._parameter_candidate_score(_candidate(SimpleNamespace(value="alien"))) == 0.0


def test_academic_assessment_consumes_mixed_and_noncontributing_batches() -> None:
    """Catch a zero-score result being replaced by unknown weight at its assessment consumer."""
    need = EvidenceNeed(need_id="p", need_type=EvidenceNeedType.PARAMETER_NEED, parameter_name="p")
    batches = [
        [_candidate(EvidenceStrength.UNKNOWN), _candidate(None)],
        [_candidate(EvidenceStrength.UNKNOWN), _candidate(None), _candidate(EvidenceStrength.RCT)],
    ]
    results = []
    for candidates in batches:
        query = SimpleNamespace(query_parameters=lambda *args, rows=candidates, **kwargs: rows)
        results.append(
            compiler._assess_academic_need(
                need, concepts=[], academic_query=query, target_context=None
            )
        )
    assert [result.confidence for result in results] == [0.0, 1.0]
    assert [result.status for result in results] == [
        EvidenceStatus.INSUFFICIENT,
        EvidenceStatus.SUPPORTED,
    ]


def test_parameter_candidate_keeps_established_quality_factors() -> None:
    """Catch unrelated transport/review/uncertainty weighting being changed by the repair."""
    candidate = ParameterCandidate(
        parameter=EvidenceParameter(name="p", value=1.0, evidence_strength=EvidenceStrength.RCT),
        source_context=None,
        transport_penalty=0.2,
        requires_expert_review=True,
        source_layer="raw_parameter",
        transport_notes=("context_mismatch",),
        quality_flags=("canonical_gap_resolved",),
    )
    assert compiler._parameter_candidate_score(candidate) == pytest.approx(0.205632)
