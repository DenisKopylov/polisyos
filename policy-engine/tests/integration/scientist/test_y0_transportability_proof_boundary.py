from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.lex import IssueSeverity
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.foundry.methods.catalog.causal.transport_check import CheckTransportability
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
    ProofBundle,
    load_causal_effect_report,
    load_proof_bundle,
    persist_causal_effect_report,
    persist_proof_bundle,
    proof_bundle_from_transportability_result,
    transportability_proof_review_grade,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.context import ContextProfile, IncomeLevel
from polisyos.ir.analytics.transportability import (
    TransportabilityResult,
    TransportabilityStatus,
    build_selection_diagram,
    persist_transportability_result,
)
from polisyos.scientist.governance.passes.transportability_required_pass import (
    TransportabilityRequiredPass,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.causal_sections import (
    _build_transportability_summary,
)


def _external_report(result: TransportabilityResult) -> CausalEffectReport:
    return CausalEffectReport(
        method=CausalMethod.DOWHY_BACKDOOR,
        status=EstimationStatus.SUCCESS,
        estimand="ATE",
        point_estimate=1.0,
        confidence_interval=(0.8, 1.2),
        inference_method="backdoor.linear_regression",
        sample_size=100,
        n_treated=50,
        n_control=50,
        pre_periods=0,
        post_periods=0,
        method_params={"source_type": "external_literature"},
        transport_result=result,
    )


def test_real_y0_transport_proof_scope_survives_cas_pass_export_and_grade_removal(
    tmp_path,
) -> None:
    pytest.importorskip("y0")
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    context = ContextProfile(context_id="source", income_level=IncomeLevel.HIGH)
    diagram = build_selection_diagram(context, context.model_copy(deep=True), graph)

    payload = CheckTransportability.pure_step(
        {
            "selection_diagram": diagram.model_dump(mode="json"),
            "query_treatment": "X",
            "query_outcome": "Y",
        },
        {"transport_solver_mode": "symbolic_y0"},
    )
    result = TransportabilityResult.model_validate(payload["transport_result"])
    proof = ProofBundle.model_validate(payload["proof_bundle"])
    assert result.status is TransportabilityStatus.IDENTIFIED
    assert proof.proof_status == "identified"
    assert proof.proof_stratum == "A2_oracle_backed"
    assert proof.completeness_regime == "sound_incomplete"
    assert proof.metadata["transport_review_grade"] == "review_required"

    store = FileSystemCAS(tmp_path)
    ir_store = ensure_ir_artifact_store(store)
    result_ref = persist_transportability_result(ir_store, result)
    proof_ref = persist_proof_bundle(ir_store, proof)
    report_ref = persist_causal_effect_report(ir_store, _external_report(result))
    loaded_proof = load_proof_bundle(ir_store, proof_ref)
    loaded_report = load_causal_effect_report(ir_store, report_ref)
    assert loaded_proof.proof_status == "identified"
    assert loaded_proof.proof_stratum == "A2_oracle_backed"
    assert loaded_report.transport_result is not None
    assert loaded_report.transport_result.metadata["backend_operation"] == "identify_outcomes"

    direct_ctx = PassContext(
        ir=None,
        state={
            "artifacts_index": {"transportability_result_ref": result_ref},
            "params": {"transport_required": True},
            "_store": store,
        },
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_y0_transport_proof_cas",
    )
    report_ctx = PassContext(
        ir=None,
        state={"artifacts_index": {"causal_report_ref": report_ref}, "_store": store},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_y0_transport_proof_report",
    )
    direct_issues = TransportabilityRequiredPass().validate(direct_ctx)
    report_issues = TransportabilityRequiredPass().validate(report_ctx)
    assert [issue.code for issue in direct_issues] == ["TRANSPORT_REVIEW_REQUIRED"]
    assert [issue.code for issue in report_issues] == ["TRANSPORT_REVIEW_REQUIRED"]
    assert direct_issues[0].severity is IssueSeverity.BLOCKER
    summary = _build_transportability_summary(loaded_report, SimpleNamespace(params={}))
    assert summary is not None
    assert summary["proof_review_grade"] == "review_required"
    assert summary["proof_purpose"] == "conditional_graph_mathematics"
    assert summary["proof_status"] == "identified"
    assert summary["proof_stratum"] == "A2_oracle_backed"
    assert summary["proof_completeness"] == "sound_incomplete"
    assert summary["source_data_authority"] == "not_established"

    # Remove the grade-bearing review fields but keep the actual backend operation,
    # returned formula AST, graph/query scope, and gate predicates. The consumer
    # must recompute a review-required grade instead of trusting the Boolean.
    stripped = result.model_copy(
        update={"requires_expert_review": False, "expert_review_reasons": []}
    )
    stripped_proof = proof_bundle_from_transportability_result(stripped)
    stripped_metadata = dict(stripped_proof.metadata)
    stripped_metadata.pop("transport_review_grade")
    bundle_without_grade = stripped_proof.model_copy(update={"metadata": stripped_metadata})
    assert stripped.identification_engine == "y0"
    assert stripped.metadata["backend_operation"] == "identify_outcomes"
    assert stripped.estimand_ast["identification_method"] == "y0_oracle"
    assert transportability_proof_review_grade(stripped).value == "review_required"
    assert bundle_without_grade.proof_status == "identified"
    assert bundle_without_grade.proof_stratum == "A2_oracle_backed"
    assert bundle_without_grade.completeness_regime == "sound_incomplete"

    stripped_report_ref = persist_causal_effect_report(ir_store, _external_report(stripped))
    stripped_ctx = PassContext(
        ir=None,
        state={"artifacts_index": {"causal_report_ref": stripped_report_ref}, "_store": store},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_y0_transport_proof_stripped_review_grade",
    )
    stripped_issues = TransportabilityRequiredPass().validate(stripped_ctx)
    assert [issue.code for issue in stripped_issues] == ["TRANSPORT_REVIEW_REQUIRED"]
    assert stripped_issues[0].severity is IssueSeverity.BLOCKER
    stripped_summary = _build_transportability_summary(
        _external_report(stripped), SimpleNamespace(params={})
    )
    assert stripped_summary is not None
    assert stripped_summary["requires_expert_review"] is False
    assert stripped_summary["proof_review_grade"] == "review_required"
    assert stripped_summary["source_data_authority"] == "not_established"
