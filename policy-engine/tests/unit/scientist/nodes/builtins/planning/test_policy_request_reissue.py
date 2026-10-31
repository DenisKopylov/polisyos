from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from polisyos.core.artifacts import (
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.contracts.scholar import ResearchIntent
from polisyos.scientist.nodes.builtins.planning.plan_policy_request import PlanPolicyRequestNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_POLICY_REQUEST_FRAME_REF,
    INPUT_RESEARCH_INTENT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.policy_verified import (
    PolicyRequestFrame,
    load_policy_request_frame,
    persist_policy_request_frame,
)


def test_request_producer_reissues_when_actual_question_changes(tmp_path) -> None:
    """An old selected frame cannot bypass the current request input."""
    store = FileSystemCAS(tmp_path / "cas")
    old = persist_policy_request_frame(
        store,
        PolicyRequestFrame(
            request_id="synthetic-old", policy_question="Old?", jurisdiction="synthetic"
        ),
    )
    state = ExperimentState(
        run_id="synthetic-request-reissue",
        policy_request_ref=old,
        artifacts_index={ARTIFACT_POLICY_REQUEST_FRAME_REF: old},
        params={"policy_question": "New?", "policy_request_jurisdiction": "synthetic"},
    )
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    result = PlanPolicyRequestNode().execute(ctx, state)
    assert result.status == "ok"
    selected = result.state.policy_request_ref
    assert selected is not None and selected != old
    assert selected.manifest_profile_sha256 is not None
    assert load_policy_request_frame(store, selected).policy_question == "New?"
    assert load_policy_request_frame(store, old).policy_question == "Old?"


def test_request_producer_preserves_selected_research_intent_edge(tmp_path) -> None:
    """The selected input profile that supplied the question is in the real output lineage."""
    store = FileSystemCAS(tmp_path / "cas")
    intent = store.put_json(
        ResearchIntent(topic="A synthetic research topic", jurisdiction="synthetic"),
        PutOptions(
            kind="scholar.research_intent",
            media_type="application/json",
            schema=SchemaInfo(name="test.ResearchIntent", version="1.0"),
        ),
        return_selected_profile=True,
    )
    state = ExperimentState(
        run_id="synthetic-intent",
        inputs={INPUT_RESEARCH_INTENT_REF: intent},
        params={"policy_request_jurisdiction": "synthetic"},
    )
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    result = PlanPolicyRequestNode().execute(ctx, state)
    assert result.status == "ok"
    selected = result.state.policy_request_ref
    assert selected is not None
    assert (
        load_policy_request_frame(store, selected).policy_question == "A synthetic research topic"
    )
    assert store.get_manifest(selected).inputs == [
        input_ref_from_artifact_ref(intent, role="research_intent")
    ]
