from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from polisyos.scientist.nodes.builtins.decide.build_verified_policy_report import (
    BuildVerifiedPolicyReportNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_VERIFIED_POLICY_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state as real_branch_state,
)


def _passing_judge_verdict() -> dict[str, object]:
    return {
        "per_judge": {
            name: {"judge_name": name, "passed": True, "is_fatal": True}
            for name in (
                "structural",
                "statistical",
                "robustness",
                "governance",
                "reproducibility",
                "compute",
            )
        },
        "composite_decision": "promote",
        "blocking_failures": [],
        "warnings": [],
    }


def test_report_refuses_unbound_caller_verdict(
    execution_context, minimal_state, artifact_ref_factory
):
    """A caller-provided six-judge marker cannot authorize a report."""
    request_ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    option_ref = artifact_ref_factory(kind="scientist.policy_option_set")
    report_ref = artifact_ref_factory(kind="scientist.source_verification_report")
    payload_ref = artifact_ref_factory(kind="scientist.verified_policy_report")

    mock_frame = MagicMock(request_id="synthetic")
    mock_option_set = MagicMock(request_id="synthetic")
    mock_verification = MagicMock(request_id="synthetic")
    mock_payload = MagicMock()
    mock_payload.verified_findings = [MagicMock()]
    mock_payload.needs_expert_review = False

    state = minimal_state.model_copy(deep=True)
    state.policy_request_ref = request_ref
    state.policy_option_set_ref = option_ref
    state.source_verification_report_ref = report_ref
    state.params["judge_verdict"] = _passing_judge_verdict()

    with (
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.load_policy_request_frame",
            return_value=mock_frame,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.load_policy_option_set",
            return_value=mock_option_set,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.load_source_verification_report",
            return_value=mock_verification,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.require_selected_policy_source_bindings",
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.build_verified_policy_report",
            return_value=mock_payload,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.persist_verified_policy_report",
            return_value=payload_ref,
        ),
    ):
        outcome = BuildVerifiedPolicyReportNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None and outcome.error.code == "phase5_validation_failed"
    assert ARTIFACT_VERIFIED_POLICY_REPORT_REF not in outcome.state.artifacts_index
    assert outcome.state.verified_policy_report_ref is None


def test_report_missing_inputs(execution_context, minimal_state):
    """When required refs are missing, returns skip."""
    outcome = BuildVerifiedPolicyReportNode().execute(execution_context, minimal_state)
    assert outcome.status == "skip"


def test_unbound_cached_report_is_cleared_before_missing_input_skip(
    execution_context, minimal_state, artifact_ref_factory
):
    """An ownerless cached ref cannot bypass report producer currentness."""
    ref = artifact_ref_factory(kind="scientist.verified_policy_report")
    state = minimal_state.model_copy(deep=True)
    state.verified_policy_report_ref = ref
    state.artifacts_index[ARTIFACT_VERIFIED_POLICY_REPORT_REF] = ref
    outcome = BuildVerifiedPolicyReportNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert outcome.state.verified_policy_report_ref is None
    assert ARTIFACT_VERIFIED_POLICY_REPORT_REF not in outcome.state.artifacts_index


def test_engine_owned_verified_report_cache_replays_sources(tmp_path, monkeypatch) -> None:
    """The report cache reuses only its selected source-bound producer output."""
    import logging

    import polisyos.scientist.nodes.builtins.decide.build_verified_policy_report as report_module
    from polisyos.core.artifacts import PutOptions, SchemaInfo, input_ref_from_artifact_ref
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.components import ComponentId
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.run.context import RunContext
    from polisyos.scientist.nodes.builtins import state_keys
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
    from polisyos.scientist.validation.phase5_preflight import Phase5PublicationResult
    from polisyos.scientist.validation.policy_verified.models import (
        PolicyOption,
        PolicyOptionSet,
        PolicyRequestFrame,
        SourceVerificationReport,
        VerifiedPolicyReportRef,
        load_verified_policy_report,
        persist_policy_option_set,
        persist_policy_request_frame,
        persist_source_verification_report,
    )

    store = FileSystemCAS(tmp_path / "cas")
    bundle_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run_id = "R_verified_policy_report_source_cache"
    run = RunContext.start(store=store, registry_bundle=bundle_ref, run_id=run_id)
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.nodes.verified_report_currentness"),
    )
    frame = PolicyRequestFrame(
        request_id="verified-report-cache",
        policy_question="How should the transport policy change?",
    )
    original_options = PolicyOptionSet(
        request_id=frame.request_id,
        hypothesis_options=[
            PolicyOption(
                option_id="hypothesis-a",
                title="Original hypothesis",
                summary="Original candidate only.",
                hypothesis_basis=True,
            )
        ],
    )
    frame_ref = persist_policy_request_frame(store, frame)
    verification_ref = persist_source_verification_report(
        store,
        SourceVerificationReport(request_id=frame.request_id, needs_expert_review=True),
        inputs=[input_ref_from_artifact_ref(frame_ref, role="policy_request_frame")],
    )
    option_ref = persist_policy_option_set(
        store,
        original_options,
        inputs=[
            input_ref_from_artifact_ref(frame_ref, role="policy_request_frame"),
            input_ref_from_artifact_ref(verification_ref, role="source_verification_report"),
        ],
    )
    validation_ref = store.put_json(
        {"verdict": "pass"},
        PutOptions(
            kind="scientist.validation_report",
            media_type="application/json",
            schema=SchemaInfo(name="test.ValidationReport", version="1.0"),
        ),
    )
    monkeypatch.setattr(
        report_module,
        "run_phase5_artifact_preflight",
        lambda *_args, **_kwargs: Phase5PublicationResult(
            validation_report=MagicMock(),
            validation_ref=validation_ref,
            publishable=True,
            readiness="ready",
        ),
    )

    node = BuildVerifiedPolicyReportNode()
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="verified_report_currentness",
        nodes=[
            NodeInvocation(
                alias="verified_report",
                node_id=ComponentId.parse(str(node.spec.metadata.component_id)),
            )
        ],
    )
    initial = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": bundle_ref},
        policy_request_ref=frame_ref,
        policy_option_set_ref=option_ref,
        source_verification_report_ref=verification_ref,
        artifacts_index={
            state_keys.ARTIFACT_POLICY_REQUEST_FRAME_REF: frame_ref,
            state_keys.ARTIFACT_POLICY_OPTION_SET_REF: option_ref,
            state_keys.ARTIFACT_SOURCE_VERIFICATION_REPORT_REF: verification_ref,
        },
    )
    result = WorkflowExecutor(ctx, registry).execute(workflow, initial)
    assert result.state.verified_policy_report_ref is not None
    original_report_ref = result.state.verified_policy_report_ref
    original_report = load_verified_policy_report(
        store,
        VerifiedPolicyReportRef.model_validate(original_report_ref.model_dump(mode="json")),
    )
    assert original_report.hypotheses == ["Original candidate only."]

    with (
        patch.object(report_module, "load_policy_request_frame", side_effect=AssertionError),
        patch.object(report_module, "load_policy_option_set", side_effect=AssertionError),
        patch.object(report_module, "load_source_verification_report", side_effect=AssertionError),
        patch.object(report_module, "build_verified_policy_report", side_effect=AssertionError),
        patch.object(report_module, "persist_verified_policy_report", side_effect=AssertionError),
    ):
        cached = node.execute(ctx, result.state)
    assert cached.status == "ok"
    assert cached.state.verified_policy_report_ref == original_report_ref

    revised_options = PolicyOptionSet(
        request_id=frame.request_id,
        hypothesis_options=[
            PolicyOption(
                option_id="hypothesis-b",
                title="Revised hypothesis",
                summary="Revised candidate only.",
                hypothesis_basis=True,
            )
        ],
    )
    revised_option_ref = persist_policy_option_set(
        store,
        revised_options,
        inputs=[
            input_ref_from_artifact_ref(frame_ref, role="policy_request_frame"),
            input_ref_from_artifact_ref(verification_ref, role="source_verification_report"),
        ],
    )
    changed = result.state.model_copy(deep=True)
    changed.policy_option_set_ref = revised_option_ref
    changed.artifacts_index[state_keys.ARTIFACT_POLICY_OPTION_SET_REF] = revised_option_ref
    loaded_option_refs = []
    original_loader = report_module.load_policy_option_set

    def capture_option_load(loader_store, selected_ref):
        loaded_option_refs.append(selected_ref)
        return original_loader(loader_store, selected_ref)

    with patch.object(report_module, "load_policy_option_set", side_effect=capture_option_load):
        rebuilt = node.execute(ctx, changed)
    assert rebuilt.status == "ok"
    assert loaded_option_refs == [revised_option_ref]
    assert rebuilt.state.verified_policy_report_ref != original_report_ref
    rebuilt_report = load_verified_policy_report(
        store,
        VerifiedPolicyReportRef.model_validate(
            rebuilt.state.verified_policy_report_ref.model_dump(mode="json")
        ),
    )
    assert rebuilt_report.hypotheses == ["Revised candidate only."]

    # A present option-set ref with correctly declared artifact identity but malformed
    # model bytes must be loaded and refused; it cannot be treated as absent or served
    # from the prior current cache.
    malformed_option_ref = store.put_json(
        {"schema_version": "1.0", "request_id": frame.request_id, "unknown": "present"},
        PutOptions(
            kind="scientist.policy_option_set",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.scientist.PolicyOptionSet", version="1.0"),
        ),
    )
    malformed = result.state.model_copy(deep=True)
    malformed.policy_option_set_ref = malformed_option_ref
    malformed.artifacts_index[state_keys.ARTIFACT_POLICY_OPTION_SET_REF] = malformed_option_ref
    with pytest.raises(ValidationError):
        node.execute(ctx, malformed)

    removed = result.state.model_copy(deep=True)
    removed.policy_option_set_ref = None
    removed.artifacts_index.pop(state_keys.ARTIFACT_POLICY_OPTION_SET_REF)
    skipped = node.execute(ctx, removed)
    assert skipped.status == "skip"
    assert skipped.state.verified_policy_report_ref is None
    assert state_keys.ARTIFACT_VERIFIED_POLICY_REPORT_REF not in skipped.state.artifacts_index


def test_verified_policy_report_uses_branch_state_for_declared_outputs(
    execution_context, minimal_state, artifact_ref_factory
):
    request_ref = artifact_ref_factory(kind="scientist.policy_request_frame")
    option_ref = artifact_ref_factory(kind="scientist.policy_option_set")
    report_ref = artifact_ref_factory(kind="scientist.source_verification_report")
    payload_ref = artifact_ref_factory(kind="scientist.verified_policy_report")

    mock_payload = MagicMock()
    mock_payload.verified_findings = []
    mock_payload.needs_expert_review = False

    state = minimal_state.model_copy(deep=True)
    state.policy_request_ref = request_ref
    state.policy_option_set_ref = option_ref
    state.source_verification_report_ref = report_ref
    state.params["nested"] = {"baseline": True}
    state.params["judge_verdict"] = _passing_judge_verdict()
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.load_policy_request_frame",
            return_value=MagicMock(request_id="synthetic"),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.load_policy_option_set",
            return_value=MagicMock(request_id="synthetic"),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.load_source_verification_report",
            return_value=MagicMock(request_id="synthetic"),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.require_selected_policy_source_bindings",
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.build_verified_policy_report",
            return_value=mock_payload,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.decide.build_verified_policy_report.persist_verified_policy_report",
            return_value=payload_ref,
        ),
    ):
        outcome = BuildVerifiedPolicyReportNode().execute(execution_context, state)

    assert outcome.status == "fail"
    assert outcome.error is not None and outcome.error.code == "phase5_validation_failed"
    assert observed["write_paths"] == (
        "artifacts_index.validation_report_ref",
        "artifacts_index.judge_verdict_ref",
    )
    assert state.params["nested"] == {"baseline": True}
    assert ARTIFACT_VERIFIED_POLICY_REPORT_REF not in state.artifacts_index
    assert outcome.state.verified_policy_report_ref is None
