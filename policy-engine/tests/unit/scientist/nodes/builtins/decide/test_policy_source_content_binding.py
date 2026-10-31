"""Selected policy sources must actually belong to the selected request and report."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions, input_ref_from_artifact_ref
from polisyos.scientist.nodes.builtins.decide.build_verified_policy_body import (
    _build_candidate_body,
)
from polisyos.scientist.nodes.builtins.decide.build_verified_policy_report import (
    BuildVerifiedPolicyReportNode,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_VERIFIED_POLICY_BODY_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.policy_verified import (
    PolicyOptionSet,
    SourceVerificationReport,
    persist_policy_option_set,
    persist_policy_request_frame,
    persist_source_verification_report,
)
from polisyos.scientist.validation.policy_verified.service import build_policy_request_frame


@pytest.mark.parametrize(
    "variant",
    [
        "current",
        "old_source_request",
        "old_option_request",
        "foreign_report",
        "unbound",
        "duplicate_source",
        "duplicate_option",
    ],
)
def test_body_reconciles_actual_selected_source_edges(tmp_path, variant: str) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ctx = cast("ExecutionContext", SimpleNamespace(store=store))
    params = {"policy_question": "Synthetic?", "policy_request_jurisdiction": "synthetic"}
    current_frame = build_policy_request_frame(
        ctx,
        ExperimentState(
            run_id="synthetic-selected-source-join", params={**params, "goals": ["new goal"]}
        ),
    )
    old_frame = build_policy_request_frame(
        ctx,
        ExperimentState(
            run_id="synthetic-selected-source-join", params={**params, "goals": ["old goal"]}
        ),
    )
    assert current_frame.request_id == old_frame.request_id
    current = persist_policy_request_frame(store, current_frame)
    old = persist_policy_request_frame(store, old_frame)
    assert current.artifact_id != old.artifact_id
    report = SourceVerificationReport(request_id=current_frame.request_id, needs_expert_review=True)
    report_request = old if variant == "old_source_request" else current
    source_inputs = [input_ref_from_artifact_ref(report_request, role="policy_request_frame")]
    if variant == "duplicate_source":
        source_inputs.append(source_inputs[0])
    source = persist_source_verification_report(store, report, inputs=source_inputs)
    other_input = store.put_json(
        {"synthetic": True},
        PutOptions(kind="test.other_source", media_type="application/json"),
        return_selected_profile=True,
    )
    other_source = persist_source_verification_report(
        store,
        report,
        inputs=[
            input_ref_from_artifact_ref(current, role="policy_request_frame"),
            input_ref_from_artifact_ref(other_input, role="other_source"),
        ],
    )
    if variant == "foreign_report":
        assert other_source.artifact_id == source.artifact_id
        assert other_source.manifest_profile_sha256 != source.manifest_profile_sha256
    option_request = old if variant == "old_option_request" else current
    option_source = other_source if variant == "foreign_report" else source
    option_inputs = (
        []
        if variant == "unbound"
        else [
            input_ref_from_artifact_ref(option_request, role="policy_request_frame"),
            input_ref_from_artifact_ref(option_source, role="source_verification_report"),
        ]
    )
    if variant == "duplicate_option":
        option_inputs.append(option_inputs[0])
    options = persist_policy_option_set(
        store, PolicyOptionSet(request_id=current_frame.request_id), inputs=option_inputs
    )
    state = ExperimentState(
        run_id="synthetic-selected-source-join",
        policy_request_ref=current,
        policy_option_set_ref=options,
        source_verification_report_ref=source,
    )
    result = _build_candidate_body(ctx, state)
    if variant == "current":
        assert result.status == "ok"
        assert ARTIFACT_VERIFIED_POLICY_BODY_REF in result.state.artifacts_index
    else:
        assert result.status == "fail"
        assert (
            result.error is not None
            and result.error.code == "policy_source_binding_not_established"
        )
        assert ARTIFACT_VERIFIED_POLICY_BODY_REF not in result.state.artifacts_index
        report_result = BuildVerifiedPolicyReportNode().execute(ctx, state)
        assert report_result.status == "fail"
        assert (
            report_result.error is not None
            and report_result.error.code == "policy_source_binding_not_established"
        )
