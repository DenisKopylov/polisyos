from __future__ import annotations

from unittest.mock import MagicMock, patch

from polisyos.scientist.nodes.builtins.compile.link_trinity import LinkTrinityNode
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_LINK_REPORT_REF,
)


def test_link_success(execution_context, minimal_state, artifact_ref_factory):
    """Successful link produces a link report."""
    trinity_ref = artifact_ref_factory(kind="ir.trinity_bundle")

    state = minimal_state.model_copy(deep=True)
    state.inputs[INPUT_TRINITY_BUNDLE_REF] = trinity_ref

    mock_link_report = MagicMock()
    mock_link_report.ok = True
    link_report_ref = artifact_ref_factory(kind="compiler.link_report")

    _mod = "polisyos.scientist.nodes.builtins.compile.link_trinity"
    with (
        patch(f"{_mod}.from_canonical_bytes", return_value={}),
        patch(f"{_mod}.TrinityBundle.model_validate", return_value=MagicMock()),
        patch(f"{_mod}.load_registry_bundle_content", return_value=MagicMock()),
        patch(f"{_mod}.RegistryBundle", return_value=MagicMock()),
        patch(f"{_mod}.link_trinity", return_value=(MagicMock(), mock_link_report)),
        patch(f"{_mod}.put_link_report", return_value=link_report_ref),
    ):
        outcome = LinkTrinityNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert REPORT_LINK_REPORT_REF in outcome.state.reports_index


def test_link_missing_refs(execution_context, minimal_state):
    """Missing trinity or registry ref causes fail."""
    outcome = LinkTrinityNode().execute(execution_context, minimal_state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "node.missing_input"


def test_link_missing_trinity_only(execution_context, minimal_state):
    """With registry but no trinity ref, also fails."""
    # minimal_state already has registry_bundle_ref but no trinity_bundle_ref
    outcome = LinkTrinityNode().execute(execution_context, minimal_state)
    assert outcome.status == "fail"
    assert outcome.error.code == "node.missing_input"
