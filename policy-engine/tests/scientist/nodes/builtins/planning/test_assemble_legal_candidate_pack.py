from __future__ import annotations

from unittest.mock import MagicMock, patch

from polisyos.scientist.nodes.builtins.planning.assemble_legal_candidate_pack import (
    AssembleLegalCandidatePackNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_LEGAL_CANDIDATE_PACK_REF,
    ARTIFACT_POLICY_REQUEST_FRAME_REF,
)


def test_assemble_with_sources(execution_context, minimal_state, artifact_ref_factory):
    """With a policy_request_ref, assembles the legal candidate pack."""
    request_ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    pack_ref = artifact_ref_factory(kind="scientist.legal_candidate_pack")
    mock_frame = MagicMock()
    mock_pack = MagicMock()
    mock_pack.fact_hits = [MagicMock()]
    mock_pack.provision_hits = [MagicMock(), MagicMock()]
    state = minimal_state.model_copy(deep=True)
    state.policy_request_ref = request_ref
    state.artifacts_index[ARTIFACT_POLICY_REQUEST_FRAME_REF] = request_ref
    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.assemble_legal_candidate_pack.load_policy_request_frame",
            return_value=mock_frame,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.assemble_legal_candidate_pack.assemble_legal_candidate_pack",
            return_value=mock_pack,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.assemble_legal_candidate_pack.persist_legal_candidate_pack",
            return_value=pack_ref,
        ),
    ):
        outcome = AssembleLegalCandidatePackNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert ARTIFACT_LEGAL_CANDIDATE_PACK_REF in outcome.state.artifacts_index
    assert outcome.state.legal_candidate_pack_ref == pack_ref


def test_assemble_no_sources(execution_context, minimal_state):
    """Without policy_request_ref, returns skip."""
    outcome = AssembleLegalCandidatePackNode().execute(execution_context, minimal_state)
    assert outcome.status == "skip"


def test_assemble_already_exists(execution_context, minimal_state, artifact_ref_factory):
    """When legal_candidate_pack_ref is already set, no-op."""
    ref = artifact_ref_factory(kind="scientist.legal_candidate_pack")
    state = minimal_state.model_copy(deep=True)
    state.legal_candidate_pack_ref = ref
    state.artifacts_index[ARTIFACT_LEGAL_CANDIDATE_PACK_REF] = ref
    outcome = AssembleLegalCandidatePackNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert outcome.state is state
