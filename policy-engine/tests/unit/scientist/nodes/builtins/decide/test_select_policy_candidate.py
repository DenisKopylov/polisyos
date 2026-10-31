"""Selected candidate intake is distinct from any publication authority."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    ensure_ir_artifact_store,
)
from polisyos.ir.trinity import persist_trinity_bundle_artifact
from polisyos.scientist.nodes.builtins.decide.select_policy_candidate import (
    SelectPolicyCandidateNode,
    _selected_candidate,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.schema import persist_policy_candidate_schema
from tests.unit.scientist.search.test_phase_b_policy_runtime import _candidate


def test_selected_candidate_accepts_matching_typed_values_and_owner_profiles(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _candidate()
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    trinity_ref = ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(store), candidate.trinity_bundle
        ).model_dump(mode="json")
    )
    selected, inputs = _selected_candidate(
        store, candidate.model_dump(mode="json"), candidate_ref.model_dump(mode="json"), trinity_ref
    )
    assert selected.model_dump(mode="json") == candidate.model_dump(mode="json")
    assert inputs == [("candidate_source", candidate_ref), ("candidate_trinity", trinity_ref)]


def test_missing_or_disagreeing_candidate_never_becomes_selected(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _candidate()
    selected = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    with pytest.raises(ValueError, match="policy_candidate_not_established"):
        _selected_candidate(store, None, None, None)
    with pytest.raises(ValueError, match="policy_candidate_version_not_established"):
        _selected_candidate(
            store, candidate.model_copy(update={"schema_version": "2.0"}), None, None
        )
    with pytest.raises(ValueError, match="policy_candidate_source_not_established"):
        _selected_candidate(
            store,
            candidate,
            selected.model_copy(update={"manifest_profile_sha256": None}),
            None,
        )
    with pytest.raises(ValueError, match="policy_candidate_selection_conflict"):
        _selected_candidate(
            store, candidate.model_copy(update={"candidate_id": "different"}), selected, None
        )


def test_same_bytes_foreign_candidate_profile_is_not_an_owner_occurrence(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _candidate()
    selected = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    manifest = store.get_manifest(selected)
    foreign = store.put_bytes(
        store.get_bytes(selected),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=SchemaInfo(name="test.ForeignCandidate", version="1.0"),
            canon=manifest.canon,
        ),
        return_selected_profile=True,
    )
    assert foreign.artifact_id == selected.artifact_id
    assert foreign.manifest_profile_sha256 != selected.manifest_profile_sha256
    with pytest.raises(ValueError):
        _selected_candidate(store, candidate, foreign, None)


def test_selected_trinity_must_match_candidate(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _candidate()
    foreign_bundle = candidate.trinity_bundle.model_copy(
        update={
            "problem_frame": candidate.trinity_bundle.problem_frame.model_copy(
                update={"problem_id": "foreign_problem"}
            )
        }
    )
    trinity_ref = ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(ensure_ir_artifact_store(store), foreign_bundle).model_dump(
            mode="json"
        )
    )
    with pytest.raises(ValueError, match="policy_candidate_trinity_mismatch"):
        _selected_candidate(store, candidate, None, trinity_ref)


def test_typed_caller_candidate_without_engine_attempt_is_blocked(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _candidate()
    state = ExperimentState(
        run_id="synthetic-unappointed", params={"policy_candidate_schema": candidate.model_dump()}
    )
    ctx = cast("ExecutionContext", SimpleNamespace(store=store, _node_input_selection=None))
    outcome = SelectPolicyCandidateNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None and outcome.error.code == "policy_candidate_not_established"
    assert "verified_policy_candidate_ref" not in outcome.state.artifacts_index


def test_real_engine_binds_candidate_to_selected_attempt_and_profile(tmp_path, monkeypatch) -> None:
    """An actual selected producer has no access to unrelated workflow history."""
    import logging

    import polisyos.scientist.nodes.builtins.decide.select_policy_candidate as candidate_owner
    from polisyos.core.artifacts import input_ref_from_artifact_ref
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
    from polisyos.scientist.orchestration.engine.producer_currentness import (
        resolve_engine_produced_artifact,
    )
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
    from polisyos.scientist.policy_design.schema import load_policy_candidate_schema

    store = FileSystemCAS(tmp_path / "cas")
    candidate = _candidate()
    source = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    trinity = ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(store), candidate.trinity_bundle
        ).model_dump(mode="json")
    )
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id="synthetic-select")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    state = ExperimentState(
        run_id="synthetic-select",
        params={
            "policy_candidate_schema": candidate.model_dump(mode="json"),
            "policy_candidate_ref": source.model_dump(mode="json"),
            "old_promotion_verdict": "untrusted-history",
        },
        inputs={"trinity_bundle_ref": trinity},
        reports_index={"unrelated": source},
    )
    node = SelectPolicyCandidateNode()
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="synthetic_candidate_selection",
        nodes=[NodeInvocation(alias="select_candidate", node_id=node.spec.metadata.component_id)],
    )
    result = WorkflowExecutor(ctx, registry).execute(workflow, state)
    assert result.report.nodes[0].status == "ok"
    assert result.state.params["old_promotion_verdict"] == "untrusted-history"
    assert result.state.reports_index["unrelated"] == source
    ref = result.state.artifacts_index["verified_policy_candidate_ref"]
    assert load_policy_candidate_schema(store, ref).model_dump(mode="json") == candidate.model_dump(
        mode="json"
    )
    attempts = run.read_runtime_invocation_attempts()
    assert len(attempts) == 1
    edges = {edge.role: edge for edge in store.get_manifest(ref).inputs}
    assert edges["selected_input"] == input_ref_from_artifact_ref(
        attempts[0].basis.input_state_ref, role="selected_input"
    )
    assert edges["candidate_source"] == input_ref_from_artifact_ref(source, role="candidate_source")
    assert edges["candidate_trinity"] == input_ref_from_artifact_ref(
        trinity, role="candidate_trinity"
    )
    assert edges["selected_attempt"].manifest_profile_sha256 is not None

    def admission(current: ExperimentState):
        return resolve_engine_produced_artifact(
            ctx,
            current,
            ref,
            expected_component_id=str(node.spec.metadata.component_id),
            expected_node_spec=node.spec,
            source_read_paths=tuple(node.spec.state_reads),
        )

    assert admission(result.state).is_current
    manifest = store.get_manifest(source)
    alias = store.put_bytes(
        store.get_bytes(source),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            canon=manifest.canon,
            inputs=[input_ref_from_artifact_ref(trinity, role="different_selection")],
        ),
        return_selected_profile=True,
    )
    assert alias.artifact_id == source.artifact_id
    assert alias.manifest_profile_sha256 != source.manifest_profile_sha256
    changed = result.state.model_copy(deep=True)
    changed.params["policy_candidate_ref"] = alias.model_dump(mode="json")
    assert admission(changed).status == "stale"
    actual_selector = candidate_owner._selected_candidate
    monkeypatch.setattr(candidate_owner, "_selected_candidate", lambda *_args: None)
    assert admission(result.state).status == "not_established"
    monkeypatch.setattr(candidate_owner, "_selected_candidate", actual_selector)
    monkeypatch.setattr(SelectPolicyCandidateNode, "execute", lambda *_args: None)
    assert admission(result.state).status == "not_established"
