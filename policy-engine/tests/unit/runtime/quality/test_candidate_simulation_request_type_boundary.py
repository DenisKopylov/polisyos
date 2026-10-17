from __future__ import annotations

import pytest

from polisyos.runtime.quality.candidate_simulation import (
    CandidateSimulationN5InputV2,
    CandidateSimulationN5InputV3,
    CandidateSimulationN5InputV4,
    CandidateSimulationN5InputV5,
)
from polisyos.runtime.quality.design_generation import (
    N4CandidateScenarioProposalCandidate,
    ShadowGeneratedCandidate,
)
from polisyos.runtime.quality.generation_cycle import JointSimulationPort
from polisyos.runtime.quality.world_model_record import WorldModelRecordError
from tests._helpers.controlled_candidate_profile import _problem


@pytest.mark.parametrize(
    ("input_type", "accepted_candidate_type", "rejected_candidate_type"),
    [
        (
            CandidateSimulationN5InputV2,
            ShadowGeneratedCandidate,
            N4CandidateScenarioProposalCandidate,
        ),
        (
            CandidateSimulationN5InputV3,
            ShadowGeneratedCandidate,
            N4CandidateScenarioProposalCandidate,
        ),
        (
            CandidateSimulationN5InputV4,
            N4CandidateScenarioProposalCandidate,
            ShadowGeneratedCandidate,
        ),
        (
            CandidateSimulationN5InputV5,
            N4CandidateScenarioProposalCandidate,
            ShadowGeneratedCandidate,
        ),
    ],
)
def test_candidate_request_keeps_versioned_n4_candidate_boundary(
    input_type: type[
        CandidateSimulationN5InputV2
        | CandidateSimulationN5InputV3
        | CandidateSimulationN5InputV4
        | CandidateSimulationN5InputV5
    ],
    accepted_candidate_type: type[N4CandidateScenarioProposalCandidate | ShadowGeneratedCandidate],
    rejected_candidate_type: type[N4CandidateScenarioProposalCandidate | ShadowGeneratedCandidate],
) -> None:
    """Exact N5 input versions keep their existing N4 source class pairing."""

    input_record = input_type.model_construct()
    problem = _problem("candidate_request_type_boundary")
    port = JointSimulationPort()

    with pytest.raises(
        WorldModelRecordError,
        match="candidate_simulation_n4_source_untyped",
    ):
        port._build_candidate_simulation_request(
            candidate=rejected_candidate_type.model_construct(),
            problem=problem,
            input_record=input_record,
        )

    with pytest.raises(
        WorldModelRecordError,
        match="candidate_simulation_context_missing",
    ):
        port._build_candidate_simulation_request(
            candidate=accepted_candidate_type.model_construct(),
            problem=problem,
            input_record=input_record,
        )
