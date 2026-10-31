"""Limited report adapter contracts, refusal, and honest validation projection.

The actual Engine-to-fresh-reader path is qualified separately; synthetic binding
fixtures in this module establish neither source occurrences nor authority.
"""

from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import FileSystemCAS, ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.governance.validation import load_validation_report, persist_validation_report
from polisyos.scientist.nodes.builtins.decide.build_verified_policy_report import (
    BuildVerifiedPolicyReportCompositionNode,
    BuildVerifiedPolicyReportNode,
    _limited_composition_validation,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import InputAwareNodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.policy_verified.models import persist_verified_policy_report
from tests.unit.scientist.validation.test_policy_report_composition import _binding, _report


def test_limited_adapter_preserves_legacy_and_declares_fixed_scope() -> None:
    node = BuildVerifiedPolicyReportCompositionNode()
    spec = node.spec
    assert str(BuildVerifiedPolicyReportNode().spec.metadata.component_id).endswith("@1.0.0")
    assert str(spec.metadata.component_id) == "scientist.node_build_verified_policy_report@1.1.0"
    assert isinstance(spec, InputAwareNodeSpec)
    assert spec.input_contract.contract_id == "policy_verified_completion.v1"
    assert len(spec.state_reads) == 23
    assert len(spec.input_contract.artifact_ref_paths) == 14
    assert tuple(spec.state_writes) == (
        "verified_policy_report_ref",
        "artifacts_index.verified_policy_report_ref",
        "artifacts_index.validation_report_ref",
    )
    assert spec.produces == ["verified_policy_report_ref", "validation_report_ref"]


def test_unscoped_caller_cannot_make_the_actual_adapter_complete(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    run = RunContext.start(store, registry, run_id="not-an-engine-attempt")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    state = ExperimentState(run_id=run.run_manifest.run_id)
    before = state.model_dump(mode="json")
    try:
        outcome = BuildVerifiedPolicyReportCompositionNode().execute(ctx, state)
        assert outcome.status == "fail"
        assert outcome.error is not None
        assert outcome.error.code == "policy_composition_not_established"
        assert outcome.state.model_dump(mode="json") == before
        assert outcome.artifacts == []
        assert outcome.state.verified_policy_report_ref is None
    finally:
        run.suspend_for_resume()


def test_fresh_validation_reader_preserves_blocked_limited_projection(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    binding = _binding(store)
    report_ref = persist_verified_policy_report(store, _report(store, binding))
    report = _limited_composition_validation(report_ref, binding)
    assert report.verdict == report.readiness == "blocked"
    assert report.waivers == []
    assert len(report.phase5_components) == 3
    assert all(item.required and item.status == "blocked" for item in report.phase5_components)
    assert report.normalized_payload["publishable"] is False
    assert report.normalized_payload["requirement_authority"] == "not_established"
    ref = persist_validation_report(
        ensure_ir_artifact_store(store),
        report,
        inputs=[input_ref_from_artifact_ref(report_ref, role="limited_policy_report")],
    )
    fresh = FileSystemCAS(store.root)
    assert load_validation_report(ensure_ir_artifact_store(fresh), ref) == report
    assert fresh.get_manifest(ref).inputs == [
        input_ref_from_artifact_ref(report_ref, role="limited_policy_report")
    ]
    with pytest.raises(ValidationError, match="policy_composition_publishability_invalid"):
        _limited_composition_validation(
            report_ref, binding.model_copy(update={"publishable": True})
        )


def test_actual_engine_composition_reaches_fresh_readers_and_rejects_unowned_report(
    tmp_path, monkeypatch
) -> None:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.run.context import _read_runtime_invocation_attempts
    from polisyos.scientist.orchestration.engine.input_ports import (
        NodeInputPortError,
        read_completed_verified_policy_composition,
    )
    from polisyos.scientist.validation.policy_verified.currentness import (
        resolve_current_verified_policy_report,
    )
    from polisyos.scientist.validation.policy_verified.models import (
        PolicyReportCompositionBinding,
        _compose_limited_policy_report,
        load_verified_policy_body,
        load_verified_policy_report,
    )
    from tests.unit.scientist.orchestration.engine.test_verified_policy_completion import (
        _transition_case,
    )

    ctx, result, _transition, _handle = _transition_case(
        tmp_path, monkeypatch, "none", append_composition=True
    )
    selected = next(item for item in result.report.nodes if item.alias == "completed_report")
    assert selected.status == "ok", selected.error
    report_ref = result.state.verified_policy_report_ref
    assert report_ref is not None
    assert result.state.artifacts_index["verified_policy_report_ref"] == report_ref
    validation_ref = result.state.artifacts_index["validation_report_ref"]
    fresh = FileSystemCAS(ctx.store.root)
    report = load_verified_policy_report(fresh, report_ref)
    binding = report.composition
    assert binding is not None
    assert binding.requirement_authority == "not_established"
    assert binding.publishable is False
    assert binding.result_status == "limited"
    assert report.needs_expert_review
    assert not report.verified_legal_basis and not report.intervention_legal_basis_map
    validation = load_validation_report(ensure_ir_artifact_store(fresh), validation_ref)
    assert validation.verdict == validation.readiness == "blocked"
    assert validation.normalized_payload["composition"] == binding.model_dump(mode="json")
    assert fresh.get_manifest(validation_ref).inputs[0] == input_ref_from_artifact_ref(
        report_ref, role="limited_policy_report"
    )
    assert len(fresh.get_manifest(validation_ref).inputs) == 8

    # This is the existing finalized run owner, with a new CAS/context reader.
    # Independently reopen its persisted invocation history through the canonical
    # Core reader; do not mint a fresh writer or claim a resumed completed run.
    assert ctx.run.trace_path is not None
    attempts = _read_runtime_invocation_attempts(
        fresh, ctx.run.trace_path, run_id=result.state.run_id
    )
    completed = next(item for item in attempts if item.basis_ref == binding.selected_attempt_ref)
    assert completed.basis.input_state_ref == binding.selected_input_ref
    assert completed.outcome is not None and completed.outcome.status == "ok"
    assert {ref.kind for ref in completed.outcome.output_refs} == {
        "scientist.verified_policy_report",
        "scientist.validation_report",
    }
    reader = ExecutionContext(store=fresh, run=ctx.run, logger=logging.getLogger(__name__))
    admitted = resolve_current_verified_policy_report(reader, result.state, report_ref)
    if not admitted.is_current:
        # Keep the real owner exception/facts visible if the outer fail-closed
        # projection has reduced them to its compact reason code. This observes
        # the same input without substituting a source or granting admission.
        actual = read_completed_verified_policy_composition(
            reader,
            current_state=result.state,
            report_ref=report_ref,
            expected_attempt_ref=binding.selected_attempt_ref,
            expected_input_ref=binding.selected_input_ref,
        )
        pytest.fail(
            f"{admitted.reason_code}; fixed_owner_status={actual.status}; "
            f"limitations={actual.limitation_codes}"
        )
    assert admitted.is_current, admitted.reason_code
    assert admitted.report == report

    initial = next(item for item in attempts if item.basis.node_alias == "initial_governance")
    with pytest.raises(
        NodeInputPortError, match="completed_composition_declared_occurrence_mismatch"
    ):
        read_completed_verified_policy_composition(
            reader,
            current_state=result.state,
            report_ref=report_ref,
            expected_attempt_ref=initial.basis_ref,
            expected_input_ref=binding.selected_input_ref,
        )

    for channel in ("advisor_result", "phase5_extra_ref"):
        changed_scope = result.state.model_copy(deep=True)
        changed_scope.params[channel] = {"reported": "new unsupported source"}
        scope_result = resolve_current_verified_policy_report(reader, changed_scope, report_ref)
        assert not scope_result.is_current, channel

    # Keep the complete report/body and all status markers, reissue its exact
    # manifest edges, but remove the genuine report producer occurrence by
    # claiming the real initial-governance attempt instead. The fresh consumer
    # must reject the missing ownership, not merely a malformed payload.
    wrong_binding = PolicyReportCompositionBinding.model_validate(
        {
            **binding.model_dump(mode="python"),
            "selected_attempt_ref": initial.basis_ref,
        }
    )
    unowned = persist_verified_policy_report(
        fresh,
        _compose_limited_policy_report(
            load_verified_policy_body(fresh, binding.body_ref), wrong_binding
        ),
    )
    assert isinstance(unowned, ArtifactRef)
    assert load_verified_policy_report(fresh, unowned).composition == wrong_binding
    wrong_state = result.state.model_copy(deep=True)
    wrong_state.verified_policy_report_ref = unowned
    wrong_state.artifacts_index["verified_policy_report_ref"] = unowned
    refused = resolve_current_verified_policy_report(reader, wrong_state, unowned)
    assert not refused.is_current
    assert refused.reason_code == "producer_artifact_not_owner_linked"
