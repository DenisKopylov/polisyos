"""Exercise real parameter rejection separately from opaque compile failures."""

from __future__ import annotations

import logging
from decimal import Decimal

import pytest

from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.compiler.report import CompileReport, put_compile_report, put_link_report
from polisyos.core.contracts.execution_plan import ExecutionPlan, ExecutionPlanRef
from polisyos.core.contracts.foundry import CompileRequest
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry.compile import api
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.linker import LinkIssueCode, LinkReport
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.trinity import TrinityBundle


def _request(store: FileSystemCAS, *, profiled_members: bool = True) -> CompileRequest:
    registry = build_default_registry_bundle(store, return_selected_profile=profiled_members)
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="compile_rejection", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="invalid_rate",
            interventions=[
                InterventionSpec(
                    intervention_id="tax",
                    kind="income_tax",
                    target={
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    schedule={"start_step": 0, "duration_steps": 1},
                    params={"rate": Decimal("2")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model",
            data_snapshot_ref="sha256:" + "0" * 64,
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )
    policy_ref = store.put_json(
        bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
        return_selected_profile=True,
    )
    return CompileRequest(
        policy_ref=policy_ref,
        registry_bundle_ref=registry.bundle_ref,
        return_selected_profile=True,
    )


def test_actual_parameter_rejection_is_recomputed_from_selected_sources(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    request = _request(store)
    result = api.compile(store, request)

    assert result.ok is False
    report = validate_core_model_json_artifact(CompileReport, store, result.compile_report_ref)
    link = validate_core_model_json_artifact(LinkReport, store, report.link_report_ref)
    assert {issue.code for issue in link.issues if issue.severity.value == "error"} == {
        LinkIssueCode.PARAM_RANGE
    }
    rejection = getattr(result, "candidate_rejection", None)
    assert rejection is not None
    assert result.schema_version == report.schema_version == "1.1"
    assert rejection.policy_ref == request.policy_ref
    assert rejection.registry_bundle_ref == request.registry_bundle_ref
    assert rejection.link_report_ref == report.link_report_ref
    assert rejection == report.candidate_rejection
    assert result.exec_plan_ref is None
    reopened = FileSystemCAS(tmp_path)
    assert api.verify_expected_candidate_rejection(reopened, request, result) == rejection


@pytest.mark.parametrize("failure", [ValueError, PermissionError, TimeoutError])
def test_backend_error_with_validation_looking_text_stays_unclassified(
    tmp_path, monkeypatch: pytest.MonkeyPatch, failure: type[Exception]
) -> None:
    from polisyos.foundry.compile import trinity_compiler

    store = FileSystemCAS(tmp_path)
    request = _request(store)

    def fail_backend(*args: object, **kwargs: object) -> object:
        raise failure("link_failed: parameter rate outside allowed range")

    monkeypatch.setattr(trinity_compiler, "link_trinity", fail_backend)
    result = api.compile(store, request)
    assert result.ok is False
    assert result.schema_version == "1.0"
    assert getattr(result, "candidate_rejection", None) is None
    assert api.verify_expected_candidate_rejection(store, request, result) is None


def test_legacy_registry_members_do_not_gain_selected_source_proof(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    request = _request(store, profiled_members=False)
    result = api.compile(store, request)
    assert result.ok is False
    assert result.schema_version == "1.0"
    assert result.candidate_rejection is None
    assert api.verify_expected_candidate_rejection(store, request, result) is None


@pytest.mark.parametrize("lost_ack", [False, True])
def test_infrastructure_failure_dominates_completed_validation(
    tmp_path, monkeypatch: pytest.MonkeyPatch, lost_ack: bool
) -> None:
    from polisyos.foundry.compile import trinity_compiler

    store = FileSystemCAS(tmp_path)
    request = _request(store)
    writer = trinity_compiler.put_compile_report
    committed: list[object] = []

    def fail_publication(*args: object, **kwargs: object) -> object:
        if lost_ack:
            committed.append(writer(*args, **kwargs))
        raise TimeoutError("publication outcome is unknown after completed parameter validation")

    monkeypatch.setattr(trinity_compiler, "put_compile_report", fail_publication)
    result = api.compile(store, request)
    assert result.ok is False
    assert result.schema_version == "1.0"
    assert result.candidate_rejection is None
    assert api.verify_expected_candidate_rejection(store, request, result) is None
    if lost_ack:
        assert len(committed) == 1
        stored = validate_core_model_json_artifact(CompileReport, store, committed[0])
        assert stored.candidate_rejection is not None


def test_request_change_cannot_reuse_actual_rejection(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    request = _request(store)
    result = api.compile(store, request)
    changed = request.model_copy(update={"notes": ["another invocation input"]})
    assert api.verify_expected_candidate_rejection(store, changed, result) is None


def test_selected_method_plan_prerequisite_is_replayed(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    request = _request(store)
    plan = ExecutionPlan(plan_id="parameter_rejection_plan")
    plan_ref = store.put_json(
        plan,
        PutOptions(
            kind="scientist.execution_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ExecutionPlan", version="1.0"),
            inputs=[input_ref_from_artifact_ref(request.policy_ref, role="policy_candidate")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    request = request.model_copy(
        update={
            "schema_version": "1.2",
            "method_execution_plan_ref": ExecutionPlanRef.model_validate(
                plan_ref.model_dump(mode="python")
            ),
        }
    )
    result = api.compile(store, request)
    assert result.candidate_rejection is not None
    assert api.verify_expected_candidate_rejection(store, request, result) is not None
    data_path, _ = store._paths(plan_ref.artifact_id)
    data_path.unlink()
    assert api.verify_expected_candidate_rejection(store, request, result) is None


def test_missing_link_diagnostic_does_not_qualify(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    request = _request(store)
    result = api.compile(store, request)
    rejection = result.candidate_rejection
    assert rejection is not None
    data_path, _ = store._paths(rejection.link_report_ref.artifact_id)
    data_path.unlink()
    assert api.verify_expected_candidate_rejection(store, request, result) is None


def test_another_linker_error_is_not_a_parameter_rejection(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    request = _request(store)
    bundle = validate_core_model_json_artifact(TrinityBundle, store, request.policy_ref)
    intervention = bundle.policy_spec.interventions[0].model_copy(update={"kind": "unknown_mech"})
    bundle = bundle.model_copy(
        update={
            "policy_spec": bundle.policy_spec.model_copy(update={"interventions": [intervention]})
        }
    )
    ref = store.put_json(
        bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
        return_selected_profile=True,
    )
    request = request.model_copy(update={"policy_ref": ref})
    result = api.compile(store, request)
    assert result.ok is False
    assert result.candidate_rejection is None
    assert api.verify_expected_candidate_rejection(store, request, result) is None


def test_structured_marker_cannot_replace_recomputed_diagnostic_content(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    request = _request(store)
    result = api.compile(store, request)
    rejection = result.candidate_rejection
    assert rejection is not None
    link = validate_core_model_json_artifact(LinkReport, store, rejection.link_report_ref)
    # Preserve the expected issue code and every source marker, but replace the
    # actual validator's finding. A shape-only or code-only gate would accept it.
    assert link.issues[0].code == LinkIssueCode.PARAM_RANGE
    issue = link.issues[0].model_copy(update={"message": "a caller supplied this finding"})
    forged_link = link.model_copy(update={"issues": [issue]})
    link_ref = put_link_report(
        store,
        forged_link,
        inputs=[
            input_ref_from_artifact_ref(rejection.policy_ref, role="ir"),
            input_ref_from_artifact_ref(rejection.registry_bundle_ref, role="registry_bundle"),
        ],
        return_selected_profile=True,
    )
    forged_rejection = rejection.model_copy(update={"link_report_ref": link_ref})
    report = validate_core_model_json_artifact(CompileReport, store, result.compile_report_ref)
    forged_report = report.model_copy(
        update={"candidate_rejection": forged_rejection, "link_report_ref": link_ref}
    )
    report_ref = put_compile_report(
        store,
        forged_report,
        inputs=[
            input_ref_from_artifact_ref(rejection.policy_ref, role="ir"),
            input_ref_from_artifact_ref(rejection.registry_bundle_ref, role="registry_bundle"),
            input_ref_from_artifact_ref(link_ref, role="link_report"),
        ],
        return_selected_profile=True,
    )
    derived = result.derived_refs[0].model_copy(update={"ref": link_ref})
    forged_result = result.model_copy(
        update={
            "candidate_rejection": forged_rejection,
            "compile_report_ref": report_ref,
            "derived_refs": [derived],
        }
    )
    assert api.verify_expected_candidate_rejection(store, request, forged_result) is None


def test_legacy_serialization_does_not_gain_a_failure_claim() -> None:
    report = CompileReport(ok=False, notes=["compile_exception:ValueError:parameter range"])
    assert report.schema_version == "1.0"
    assert report.candidate_rejection is None
    assert "candidate_rejection" not in report.model_dump(mode="json")


def test_real_compile_node_keeps_failed_status_and_report(tmp_path) -> None:
    from polisyos.core.run.context import RunContext
    from polisyos.core.security import SecuritySettings
    from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
    from polisyos.scientist.nodes.builtins.compile.compile_foundry import CompileFoundryNode
    from polisyos.scientist.nodes.builtins.state_keys import (
        INPUT_REGISTRY_BUNDLE_REF,
        INPUT_TRINITY_BUNDLE_REF,
        REPORT_COMPILE_REPORT_REF,
    )
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    store = FileSystemCAS(tmp_path)
    request = _request(store)
    assert request.registry_bundle_ref is not None
    run = RunContext.start(
        store=store, registry_bundle=request.registry_bundle_ref, run_id="R_compile_rejection"
    )
    state = ExperimentState(
        run_id="R_compile_rejection",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: request.policy_ref,
            INPUT_REGISTRY_BUNDLE_REF: request.registry_bundle_ref,
        },
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(__name__),
        foundry=DefaultFoundryPort(settings=SecuritySettings()),
    )
    outcome = CompileFoundryNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "foundry.compile_failed"
    report_ref = outcome.state.reports_index[REPORT_COMPILE_REPORT_REF]
    report = validate_core_model_json_artifact(CompileReport, store, report_ref)
    assert report.ok is False
    assert report.candidate_rejection is not None
    assert report_ref.manifest_profile_sha256 is not None
