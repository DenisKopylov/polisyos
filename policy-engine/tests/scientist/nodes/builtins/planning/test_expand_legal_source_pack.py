from __future__ import annotations

from unittest.mock import MagicMock, patch

from polisyos.scientist.nodes.builtins.planning.expand_legal_source_pack import (
    ExpandLegalSourcePackNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_LEGAL_CANDIDATE_PACK_REF,
    ARTIFACT_LEGAL_SOURCE_PACK_REF,
)


def test_expansion_success(execution_context, minimal_state, artifact_ref_factory):
    """Expands legal candidate pack into source pack."""
    candidate_ref = artifact_ref_factory(kind="scientist.legal_candidate_pack")
    source_ref = artifact_ref_factory(kind="scientist.legal_source_pack")
    mock_pack = MagicMock()
    mock_source_pack = MagicMock()
    mock_source_pack.source_bundles = [MagicMock()]
    state = minimal_state.model_copy(deep=True)
    state.legal_candidate_pack_ref = candidate_ref
    state.artifacts_index[ARTIFACT_LEGAL_CANDIDATE_PACK_REF] = candidate_ref
    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.expand_legal_source_pack.load_legal_candidate_pack",
            return_value=mock_pack,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.expand_legal_source_pack.expand_legal_source_pack",
            return_value=mock_source_pack,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.expand_legal_source_pack.persist_legal_source_pack",
            return_value=source_ref,
        ),
    ):
        outcome = ExpandLegalSourcePackNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert ARTIFACT_LEGAL_SOURCE_PACK_REF in outcome.state.artifacts_index
    assert outcome.state.legal_source_pack_ref == source_ref


def test_expansion_empty_no_candidate(execution_context, minimal_state):
    """Without candidate pack ref, returns skip."""
    outcome = ExpandLegalSourcePackNode().execute(execution_context, minimal_state)
    assert outcome.status == "skip"


def test_expansion_already_exists(execution_context, minimal_state, artifact_ref_factory):
    """When legal_source_pack_ref is already set, no-op."""
    ref = artifact_ref_factory(kind="scientist.legal_source_pack")
    state = minimal_state.model_copy(deep=True)
    state.legal_source_pack_ref = ref
    state.artifacts_index[ARTIFACT_LEGAL_SOURCE_PACK_REF] = ref
    outcome = ExpandLegalSourcePackNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert outcome.state is state
