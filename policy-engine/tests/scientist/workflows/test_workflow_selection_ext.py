"""Extended workflow selection heuristic tests."""
from __future__ import annotations

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_TRINITY_BUNDLE_REF,
    INPUT_RESEARCH_INTENT_REF,
)
from polisyos.scientist.workflows.selection import resolve_workflow_id


def _ref(kind: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate("sha256:" + ("a" * 64)),
        kind=kind,
        media_type="application/json",
    )


def test_policy_verified_for_policy_verified_async_profile():
    state = ExperimentState(
        run_id="R_pv_profile",
        execution_profile="policy_verified_async",
    )
    assert resolve_workflow_id(state) == "scientist_policy_verified"


def test_default_when_trinity_present_with_policy_question():
    """If trinity bundle IS present alongside a policy question, don't escalate to policy_verified."""
    state = ExperimentState(
        run_id="R_trinity_with_question",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: _ref("ir.trinity_bundle"),
            INPUT_RESEARCH_INTENT_REF: _ref("scientist.research_intent"),
        },
        params={"policy_question": "What if we change tax rates?"},
    )
    # Trinity present → _should_use_policy_verified returns False
    result = resolve_workflow_id(state)
    assert result != "scientist_policy_verified"


def test_causal_full_for_cross_graph_evidence_expected():
    state = ExperimentState(
        run_id="R_cross_graph",
        params={"cross_graph_evidence_expected": True},
    )
    assert resolve_workflow_id(state) == "scientist_causal_full"


def test_causal_full_for_cross_context_reuse():
    state = ExperimentState(
        run_id="R_cross_context",
        params={"cross_context_causal_reuse": True},
    )
    assert resolve_workflow_id(state) == "scientist_causal_full"


def test_explicit_workflow_id_scientist_causal_full():
    state = ExperimentState(
        run_id="R_explicit",
        params={"workflow_id": "scientist_causal_full"},
    )
    assert resolve_workflow_id(state) == "scientist_causal_full"


def test_explicit_policy_verified_takes_precedence_over_serious_profile():
    state = ExperimentState(
        run_id="R_precedence",
        params={"workflow_id": "scientist_policy_verified"},
        execution_profile="production",
    )
    assert resolve_workflow_id(state) == "scientist_policy_verified"


def test_default_for_empty_state():
    state = ExperimentState(run_id="R_empty")
    assert resolve_workflow_id(state) == "scientist_default"


def test_causal_full_for_cross_graph_evidence_config_enabled():
    state = ExperimentState(
        run_id="R_config",
        params={"cross_graph_evidence_config": {"enabled": True}},
    )
    assert resolve_workflow_id(state) == "scientist_causal_full"


def test_causal_full_for_nested_evidence_sources():
    state = ExperimentState(
        run_id="R_nested_sources",
        params={"evidence_sources": {"legal_db_path": "/tmp/legal.duckdb"}},
    )
    assert resolve_workflow_id(state) == "scientist_causal_full"
