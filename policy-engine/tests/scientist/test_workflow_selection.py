from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_KNOWLEDGE_BUNDLE_REF,
    INPUT_RESEARCH_INTENT_REF,
)
from polisyos.scientist.workflows.selection import resolve_workflow_id


def _artifact_ref(kind: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate("sha256:" + ("1" * 64)),
        kind=kind,
        media_type="application/json",
    )


def test_resolve_workflow_id_defaults_to_scientist_default() -> None:
    state = ExperimentState(run_id="R_workflow_default")

    assert resolve_workflow_id(state) == "scientist_default"


def test_resolve_workflow_id_escalates_when_transport_required() -> None:
    state = ExperimentState(
        run_id="R_workflow_transport_required",
        params={"transport_required": True},
    )

    assert resolve_workflow_id(state) == "scientist_causal_full"


def test_resolve_workflow_id_escalates_for_distinct_contexts() -> None:
    state = ExperimentState(
        run_id="R_workflow_contexts",
        params={
            "source_context": {"context_id": "DE", "publication_year": 2022},
            "target_context": {"context_id": "UA", "publication_year": 2024},
        },
    )

    assert resolve_workflow_id(state) == "scientist_causal_full"


def test_resolve_workflow_id_escalates_for_external_or_knowledge_backed_runs() -> None:
    external_state = ExperimentState(
        run_id="R_workflow_external",
        params={"source_type": "external_literature"},
    )
    knowledge_state = ExperimentState(
        run_id="R_workflow_knowledge",
        inputs={INPUT_KNOWLEDGE_BUNDLE_REF: _artifact_ref("scholar.knowledge_bundle")},
    )

    assert resolve_workflow_id(external_state) == "scientist_causal_full"
    assert resolve_workflow_id(knowledge_state) == "scientist_causal_full"


def test_resolve_workflow_id_forces_serious_workflow_for_serious_profiles() -> None:
    for execution_profile in ("research", "governed", "production"):
        state = ExperimentState(
            run_id=f"R_workflow_{execution_profile}",
            execution_profile=execution_profile,
        )

        assert resolve_workflow_id(state) == "scientist_causal_full"


def test_resolve_workflow_id_uses_policy_verified_for_verified_async_mode() -> None:
    state = ExperimentState(
        run_id="R_workflow_verified_async",
        params={"policy_answer_mode": "verified_async"},
    )

    assert resolve_workflow_id(state) == "scientist_policy_verified"


def test_resolve_workflow_id_uses_policy_verified_for_policy_request_without_trinity() -> None:
    state = ExperimentState(
        run_id="R_workflow_policy_request",
        inputs={INPUT_RESEARCH_INTENT_REF: _artifact_ref("scientist.research_intent")},
        params={"policy_question": "Як змінити ліцензування?"},  # no trinity input
    )

    assert resolve_workflow_id(state) == "scientist_policy_verified"


def test_resolve_workflow_id_uses_discovery_when_discovery_payload_present() -> None:
    state = ExperimentState(
        run_id="R_workflow_discovery",
        params={
            "discovery_data": [[1.0, 2.0], [2.0, 3.0], [3.0, 5.0]],
            "discovery_variable_names": ["x", "y"],
        },
    )

    assert resolve_workflow_id(state) == "scientist_discovery"


def test_resolve_workflow_id_escalates_for_nested_evidence_sources() -> None:
    state = ExperimentState(
        run_id="R_workflow_nested_sources",
        params={"evidence_sources": {"academic_db_path": "/tmp/academic.duckdb"}},
    )

    assert resolve_workflow_id(state) == "scientist_causal_full"
