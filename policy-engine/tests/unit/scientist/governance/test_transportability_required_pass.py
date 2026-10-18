from __future__ import annotations

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.lex import ComplianceIssue, IssueSeverity
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
    TransportabilityProofReviewGrade,
    persist_causal_effect_report,
    proof_bundle_from_transportability_result,
    transportability_proof_review_grade,
)
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    CrossGraphEvidenceSummary,
    EvidenceNeed,
    EvidenceNeedAssessment,
    EvidenceNeedType,
    EvidenceStatus,
    LegalStatus,
    ObservabilityStatus,
    TransportStatus,
    persist_cross_graph_evidence_profile,
)
from polisyos.ir.analytics.transportability import (
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
    persist_transportability_result,
)
from polisyos.scientist.governance.passes.transportability_required_pass import (
    TransportabilityRequiredPass,
)


def _external_report(with_transport: bool) -> CausalEffectReport:
    transport = (
        TransportabilityResult(
            status=TransportabilityStatus.IDENTIFIED,
            final_confidence=0.8,
            query="P*(Y|do(X))",
        )
        if with_transport
        else None
    )
    payload = {
        "method": CausalMethod.DOWHY_BACKDOOR,
        "status": EstimationStatus.SUCCESS,
        "estimand": "ATE",
        "point_estimate": 1.0,
        "confidence_interval": (0.8, 1.2),
        "inference_method": "backdoor.linear_regression",
        "sample_size": 100,
        "n_treated": 50,
        "n_control": 50,
        "pre_periods": 0,
        "post_periods": 0,
        "method_params": {"source_type": "external_literature"},
    }
    if with_transport:
        payload["transport_result"] = transport
    return CausalEffectReport(**payload)


def test_transportability_required_fast_skips() -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_report": _external_report(with_transport=False)},
        registry_bundle=None,
        profile=ValidationProfile.fast(),
        run_id="R_transport_pass_fast",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert issues == []


def test_transportability_required_mvp_warns_on_missing_transport_result() -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_report": _external_report(with_transport=False)},
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="R_transport_pass_mvp",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REQUIRED_MISSING"
    assert issues[0].severity == IssueSeverity.WARNING


def test_transportability_required_strict_blocks_on_missing_transport_result() -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_report": _external_report(with_transport=False)},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_transport_pass_strict",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REQUIRED_MISSING"
    assert issues[0].severity == IssueSeverity.BLOCKER


def test_transportability_required_blocks_unknown_transport_result_grade() -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_report": _external_report(with_transport=True)},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_transport_pass_ok",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_PROOF_GRADE_UNKNOWN"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_blocks_ungraded_empty_legacy_method_params_result() -> None:
    report = _external_report(with_transport=False).model_copy(
        update={"method_params": {"source_type": "external_literature", "transport_result": {}}}
    )
    ctx = PassContext(
        ir=None,
        state={"causal_report": report},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_transport_pass_legacy",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_PROOF_GRADE_UNKNOWN"
    assert issues[0].severity is IssueSeverity.BLOCKER


@pytest.mark.parametrize("raw_result", [None, "forged-result"])
def test_transportability_required_blocks_malformed_legacy_method_params_result(
    raw_result: object,
) -> None:
    report = _external_report(with_transport=False).model_copy(
        update={
            "method_params": {
                "source_type": "external_literature",
                "transport_result": raw_result,
            }
        }
    )
    issues = TransportabilityRequiredPass().validate(_strict_context({"causal_report": report}))

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_RESULT_INPUT_INVALID"
    assert issues[0].severity is IssueSeverity.BLOCKER


@pytest.mark.parametrize("raw_input", [False, True])
def test_transportability_required_blocks_explicit_null_canonical_result(
    raw_input: bool,
) -> None:
    report = _external_report(with_transport=False).model_copy(update={"transport_result": None})
    report_input = report.model_dump(mode="json") if raw_input else report

    issues = TransportabilityRequiredPass().validate(
        _strict_context({"causal_report": report_input})
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_RESULT_INPUT_INVALID"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_multireport_grades_each_external_report() -> None:
    internal = _external_report(with_transport=False).model_copy(
        update={"method_params": {"source_type": "internal_model"}}
    )
    external_without_transport = _external_report(with_transport=False)
    external_with_transport = _external_report(with_transport=True)

    ctx = PassContext(
        ir=None,
        state={
            "causal_effect_reports": [
                internal,
                external_without_transport,
                external_with_transport,
            ]
        },
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="R_transport_pass_multireport",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert len(issues) == 2
    missing, unknown = issues
    assert isinstance(missing, ComplianceIssue)
    assert missing.code == "TRANSPORT_REQUIRED_MISSING"
    assert missing.path == ["causal_effect_reports", 1, "transport_result"]
    assert missing.severity == IssueSeverity.WARNING
    assert unknown.code == "TRANSPORT_PROOF_GRADE_UNKNOWN"
    assert unknown.path == ["causal_effect_reports", 2, "transport_result"]
    assert unknown.severity == IssueSeverity.WARNING


def test_transportability_required_multireport_empty_falls_back_to_single_report() -> None:
    ctx = PassContext(
        ir=None,
        state={
            "causal_effect_reports": [],
            "causal_report": _external_report(with_transport=False),
        },
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_transport_pass_multireport_priority",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REQUIRED_MISSING"
    assert issues[0].severity is IssueSeverity.BLOCKER


def _strict_context(
    state: dict[str, object], *, run_id: str = "R_transport_pass_source"
) -> PassContext:
    return PassContext(
        ir=None,
        state=state,
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id=run_id,
    )


def _unsupported_result() -> TransportabilityResult:
    return TransportabilityResult(
        query="P*(Y|do(X))",
        status=TransportabilityStatus.UNSUPPORTED,
        transport_mode=TransportMode.NONE,
        requires_expert_review=True,
        unsupported_reason="not_identified",
    )


def test_transportability_required_valid_legacy_result_runs_same_grade_gate() -> None:
    legacy_result = _identified_y0_candidate().model_dump(mode="json")
    report = _external_report(with_transport=False).model_copy(
        update={
            "method_params": {
                "source_type": "external_literature",
                "transport_result": legacy_result,
            }
        }
    )

    issues = TransportabilityRequiredPass().validate(_strict_context({"causal_report": report}))

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REVIEW_REQUIRED"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_typed_legacy_result_runs_same_grade_gate() -> None:
    report = _external_report(with_transport=False).model_copy(
        update={
            "method_params": {
                "source_type": "external_literature",
                "transport_result": _identified_y0_candidate(),
            }
        }
    )

    issues = TransportabilityRequiredPass().validate(_strict_context({"causal_report": report}))

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REVIEW_REQUIRED"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_conflicting_canonical_and_legacy_results_block() -> None:
    report = _external_report(with_transport=True).model_copy(
        update={
            "transport_result": _identified_y0_candidate(),
            "method_params": {
                "source_type": "external_literature",
                "transport_result": _unsupported_result().model_dump(mode="json"),
            },
        }
    )

    issues = TransportabilityRequiredPass().validate(_strict_context({"causal_report": report}))

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_RESULT_INPUT_CONFLICT"
    assert issues[0].severity is IssueSeverity.BLOCKER


@pytest.mark.parametrize("raw_ref", [False, True])
def test_transportability_required_empty_list_falls_back_to_cas_report_ref(
    tmp_path, raw_ref: bool
) -> None:
    store = FileSystemCAS(tmp_path)
    report_ref = persist_causal_effect_report(
        _ensure_ir_artifact_store(store), _external_report(with_transport=False)
    )
    issues = TransportabilityRequiredPass().validate(
        _strict_context(
            {
                "causal_effect_reports": [],
                "artifacts_index": {
                    "causal_report_ref": (
                        report_ref.model_dump(mode="json") if raw_ref else report_ref
                    )
                },
                "_store": store,
            }
        )
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REQUIRED_MISSING"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_empty_list_falls_back_to_typed_report_ref(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    report_ref = persist_causal_effect_report(
        _ensure_ir_artifact_store(store), _external_report(with_transport=False)
    )
    issues = TransportabilityRequiredPass().validate(
        _strict_context({"causal_effect_reports": [], "causal_report": report_ref, "_store": store})
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REQUIRED_MISSING"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_report_ref_without_store_is_not_absence() -> None:
    report_ref = {
        "artifact_id": "sha256:" + "0" * 64,
        "kind": "ir.causal_effect_report",
        "media_type": "application/json",
    }
    issues = TransportabilityRequiredPass().validate(_strict_context({"causal_report": report_ref}))

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REPORT_INPUT_INVALID"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_deduplicates_identical_report_aliases() -> None:
    report = _external_report(with_transport=False)
    issues = TransportabilityRequiredPass().validate(
        _strict_context({"causal_effect_reports": [report], "causal_report": report})
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REQUIRED_MISSING"


def test_transportability_required_conflicting_report_aliases_block() -> None:
    listed = _external_report(with_transport=False)
    single = listed.model_copy(update={"estimand": "ATT"})
    issues = TransportabilityRequiredPass().validate(
        _strict_context({"causal_effect_reports": [listed], "causal_report": single})
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REPORT_SOURCE_CONFLICT"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_matching_list_alias_does_not_hide_explicit_null() -> None:
    list_report = _external_report(with_transport=False)
    null_alias = list_report.model_copy(update={"transport_result": None})
    issues = TransportabilityRequiredPass().validate(
        _strict_context({"causal_effect_reports": [list_report], "causal_report": null_alias})
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_RESULT_INPUT_INVALID"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_conflicting_report_and_cas_ref_block(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    direct = _external_report(with_transport=False)
    persisted = _external_report(with_transport=False).model_copy(update={"estimand": "ATT"})
    ref = persist_causal_effect_report(_ensure_ir_artifact_store(store), persisted)
    issues = TransportabilityRequiredPass().validate(
        _strict_context(
            {
                "causal_report": direct,
                "artifacts_index": {"causal_report_ref": ref},
                "_store": store,
            }
        )
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REPORT_SOURCE_CONFLICT"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_invalid_list_entry_cannot_be_hidden_by_valid_alias() -> None:
    internal = _external_report(with_transport=False).model_copy(
        update={"method_params": {"source_type": "internal_model"}}
    )
    issues = TransportabilityRequiredPass().validate(
        _strict_context({"causal_effect_reports": [{"not": "a report"}], "causal_report": internal})
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REPORT_INPUT_INVALID"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_none_list_is_malformed_supplied_input() -> None:
    issues = TransportabilityRequiredPass().validate(
        _strict_context({"causal_effect_reports": None})
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REPORT_INPUT_INVALID"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_null_single_report_is_malformed_supplied_input() -> None:
    issues = TransportabilityRequiredPass().validate(_strict_context({"causal_report": None}))

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REPORT_INPUT_INVALID"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_null_artifact_index_is_malformed_supplied_input() -> None:
    issues = TransportabilityRequiredPass().validate(_strict_context({"artifacts_index": None}))

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REPORT_INPUT_INVALID"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_resolves_raw_report_and_ref_without_double_count(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    report = _external_report(with_transport=False)
    report_ref = persist_causal_effect_report(_ensure_ir_artifact_store(store), report)
    raw_report = report.model_dump(mode="json")
    raw_report.pop("transport_result")
    issues = TransportabilityRequiredPass().validate(
        _strict_context(
            {
                "causal_effect_reports": [],
                "causal_report": raw_report,
                "artifacts_index": {"causal_report_ref": report_ref},
                "_store": store,
            }
        )
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REQUIRED_MISSING"


def test_transportability_required_unresolved_report_ref_is_not_absence(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bad_ref = {
        "artifact_id": "sha256:" + "0" * 64,
        "kind": "ir.causal_effect_report",
        "media_type": "application/json",
    }
    issues = TransportabilityRequiredPass().validate(
        _strict_context({"artifacts_index": {"causal_report_ref": bad_ref}, "_store": store})
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REPORT_INPUT_INVALID"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_direct_cas_alias_is_evaluated_once(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    result = _identified_y0_candidate()
    result_ref = persist_transportability_result(_ensure_ir_artifact_store(store), result)
    report = _external_report(with_transport=True).model_copy(update={"transport_result": result})
    issues = TransportabilityRequiredPass().validate(
        _strict_context(
            {
                "causal_report": report,
                "artifacts_index": {"transportability_result_ref": result_ref},
                "_store": store,
            }
        )
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REVIEW_REQUIRED"


def test_transportability_required_direct_cas_conflict_with_report_blocks(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    result_ref = persist_transportability_result(
        _ensure_ir_artifact_store(store), _identified_y0_candidate()
    )
    report = _external_report(with_transport=True)
    issues = TransportabilityRequiredPass().validate(
        _strict_context(
            {
                "causal_report": report,
                "artifacts_index": {"transportability_result_ref": result_ref},
                "_store": store,
            }
        )
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_RESULT_INPUT_CONFLICT"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_malformed_direct_cas_ref_is_not_absence(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    issues = TransportabilityRequiredPass().validate(
        _strict_context(
            {
                "artifacts_index": {
                    "transportability_result_ref": {
                        "artifact_id": "invalid",
                        "kind": "ir.transportability_result",
                        "media_type": "application/json",
                    }
                },
                "_store": store,
            }
        )
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_RESULT_INPUT_INVALID"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_direct_result_ref_without_store_is_not_absence() -> None:
    result_ref = {
        "artifact_id": "sha256:" + "0" * 64,
        "kind": "ir.transportability_result",
        "media_type": "application/json",
    }
    issues = TransportabilityRequiredPass().validate(
        _strict_context({"artifacts_index": {"transportability_result_ref": result_ref}})
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_RESULT_INPUT_INVALID"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_blocks_required_direct_unsupported_artifact(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    transport_ref = persist_transportability_result(
        _ensure_ir_artifact_store(store),
        TransportabilityResult(
            query="P*(msme_survival_rate|do(credit_guarantee))",
            status=TransportabilityStatus.UNSUPPORTED,
            transport_mode=TransportMode.NONE,
            unsupported_reason="missing_causal_report",
            final_confidence=0.0,
            requires_expert_review=True,
        ),
    )
    ctx = PassContext(
        ir=None,
        state={
            "artifacts_index": {"transportability_result_ref": transport_ref},
            "params": {"transport_required": True},
            "_store": store,
        },
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="R_transport_pass_direct_artifact",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_UNSUPPORTED"
    assert issues[0].path == ["artifacts_index", "transportability_result_ref"]
    assert issues[0].severity == IssueSeverity.BLOCKER


def _identified_y0_candidate() -> TransportabilityResult:
    return TransportabilityResult(
        query="P*(Y|do(X))",
        status=TransportabilityStatus.IDENTIFIED,
        transport_mode=TransportMode.DIRECT,
        identification_engine="y0",
        requires_expert_review=True,
        expert_review_reasons=["source_data_authority_not_established"],
        metadata={
            "gate_predicates": {
                "source_data_exists": "not_established",
                "source_data_currentness": "not_established",
                "source_data_authority": "not_established",
            }
        },
    )


def test_transportability_required_blocks_y0_candidate_in_external_report() -> None:
    report = _external_report(with_transport=True).model_copy(
        update={"transport_result": _identified_y0_candidate()}
    )
    ctx = PassContext(
        ir=None,
        state={"causal_report": report},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_transport_pass_y0_report_candidate",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REVIEW_REQUIRED"
    assert issues[0].severity is IssueSeverity.BLOCKER


@pytest.mark.parametrize(
    "identification_engine",
    ["experimental_adapter", "native_id", "simplified_legacy", "y0"],
)
def test_transportability_required_blocks_unverified_identified_producer_label(
    identification_engine: str,
) -> None:
    result = TransportabilityResult(
        query="P*(Y|do(X))",
        status=TransportabilityStatus.IDENTIFIED,
        transport_mode=TransportMode.DIRECT,
        identification_engine=identification_engine,
        requires_expert_review=False,
        expert_review_reasons=[],
        estimand_ast={"identification_method": "caller_asserted_formula"},
    )
    assert transportability_proof_review_grade(result) is TransportabilityProofReviewGrade.UNKNOWN
    proof = proof_bundle_from_transportability_result(result)
    assert proof.proof_status == "identified"
    assert proof.proof_stratum == "A1_extended"
    assert proof.completeness_regime == "sound_incomplete"
    assert proof.metadata["transport_review_grade"] == "unknown"
    report = _external_report(with_transport=True).model_copy(update={"transport_result": result})
    ctx = PassContext(
        ir=None,
        state={"causal_report": report},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_transport_pass_unknown_producer",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_PROOF_GRADE_UNKNOWN"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_blocks_same_y0_candidate_from_direct_cas_ref(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    result_ref = persist_transportability_result(
        _ensure_ir_artifact_store(store), _identified_y0_candidate()
    )
    ctx = PassContext(
        ir=None,
        state={
            "artifacts_index": {"transportability_result_ref": result_ref},
            "params": {"transport_required": True},
            "_store": store,
        },
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_transport_pass_y0_direct_candidate",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REVIEW_REQUIRED"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_transportability_required_blocks_review_required_cross_graph_candidate(tmp_path) -> None:
    profile = CrossGraphEvidenceProfile(
        summary=CrossGraphEvidenceSummary(),
        needs=[
            EvidenceNeedAssessment(
                need=EvidenceNeed(
                    need_id="need_review_candidate",
                    need_type=EvidenceNeedType.OBJECTIVE_METRIC,
                ),
                legal_status=LegalStatus.ALLOWED,
                observability_status=ObservabilityStatus.DIRECT,
                evidence_status=EvidenceStatus.SUPPORTED,
                transport_status=TransportStatus.IDENTIFIED,
                transport_mode=TransportMode.DIRECT,
                requires_expert_review=True,
            )
        ],
    )
    store = FileSystemCAS(tmp_path)
    profile_ref = persist_cross_graph_evidence_profile(_ensure_ir_artifact_store(store), profile)
    ctx = PassContext(
        ir=None,
        state={
            "artifacts_index": {"cross_graph_evidence_profile_ref": profile_ref},
            "_store": store,
        },
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_transport_pass_y0_cross_graph_candidate",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REVIEW_REQUIRED"
    assert issues[0].path == ["cross_graph", "need_review_candidate"]
    assert issues[0].severity is IssueSeverity.BLOCKER


@pytest.mark.parametrize(
    ("raw_ref", "store"),
    [
        (None, None),
        ({"artifact_id": "not-a-digest"}, None),
        (
            {
                "kind": "ir.cross_graph_evidence_profile",
                "media_type": "application/json",
                "artifact_id": "sha256:" + "0" * 64,
            },
            None,
        ),
    ],
)
def test_invalid_or_unresolved_supplied_profile_ref_is_not_absence(
    raw_ref: object,
    store: object | None,
) -> None:
    state: dict[str, object] = {"artifacts_index": {"cross_graph_evidence_profile_ref": raw_ref}}
    if store is not None:
        state["_store"] = store

    issues = TransportabilityRequiredPass().validate(_strict_context(state))

    assert len(issues) == 1
    assert issues[0].code == "CROSS_GRAPH_PROFILE_INPUT_INVALID"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_supplied_profile_reference_with_store_but_no_artifact_is_not_absence(tmp_path) -> None:
    missing_ref = {
        "kind": "ir.cross_graph_evidence_profile",
        "media_type": "application/json",
        "artifact_id": "sha256:" + "1" * 64,
    }
    store = FileSystemCAS(tmp_path)

    issues = TransportabilityRequiredPass().validate(
        _strict_context(
            {
                "artifacts_index": {"cross_graph_evidence_profile_ref": missing_ref},
                "_store": store,
            }
        )
    )

    assert len(issues) == 1
    assert issues[0].code == "CROSS_GRAPH_PROFILE_INPUT_INVALID"
    assert issues[0].severity is IssueSeverity.BLOCKER


@pytest.mark.parametrize("raw_profile", [None, {"invalid": True}])
def test_supplied_direct_profile_null_or_malformed_is_not_absence(raw_profile: object) -> None:
    issues = TransportabilityRequiredPass().validate(
        _strict_context({"cross_graph_evidence_profile": raw_profile})
    )

    assert len(issues) == 1
    assert issues[0].code == "CROSS_GRAPH_PROFILE_INPUT_INVALID"
    assert issues[0].path == ["cross_graph_evidence_profile"]
    assert issues[0].severity is IssueSeverity.BLOCKER


def _cross_graph_profile(
    *,
    transport_status: TransportStatus = TransportStatus.IDENTIFIED,
    evidence_status: EvidenceStatus = EvidenceStatus.SUPPORTED,
    observability_status: ObservabilityStatus = ObservabilityStatus.DIRECT,
    requires_expert_review: bool = False,
    need_id: str = "need_profile_case",
) -> CrossGraphEvidenceProfile:
    return CrossGraphEvidenceProfile(
        summary=CrossGraphEvidenceSummary(),
        needs=[
            EvidenceNeedAssessment(
                need=EvidenceNeed(
                    need_id=need_id,
                    need_type=EvidenceNeedType.OBJECTIVE_METRIC,
                ),
                legal_status=LegalStatus.ALLOWED,
                observability_status=observability_status,
                evidence_status=evidence_status,
                transport_status=transport_status,
                transport_mode=TransportMode.DIRECT,
                requires_expert_review=requires_expert_review,
            )
        ],
    )


@pytest.mark.parametrize(
    ("transport_status", "evidence_status", "observability_status", "requires_review", "code"),
    [
        (
            TransportStatus.IDENTIFIED,
            EvidenceStatus.SUPPORTED,
            ObservabilityStatus.DIRECT,
            False,
            "TRANSPORT_PROOF_GRADE_UNKNOWN",
        ),
        (
            TransportStatus.IDENTIFIED,
            EvidenceStatus.SUPPORTED,
            ObservabilityStatus.DIRECT,
            True,
            "TRANSPORT_REVIEW_REQUIRED",
        ),
        (
            TransportStatus.PARTIALLY_IDENTIFIED,
            EvidenceStatus.MIXED,
            ObservabilityStatus.DIRECT,
            False,
            "TRANSPORT_REQUIRED_MISSING",
        ),
        (
            TransportStatus.BOUNDED_NON_IDENTIFIED,
            EvidenceStatus.SUPPORTED,
            ObservabilityStatus.PROXY_ONLY,
            False,
            "TRANSPORT_REQUIRED_MISSING",
        ),
        (
            TransportStatus.UNSUPPORTED,
            EvidenceStatus.UNSUPPORTED,
            ObservabilityStatus.UNKNOWN,
            False,
            "TRANSPORT_REQUIRED_MISSING",
        ),
    ],
)
def test_cross_graph_profile_statuses_are_strict_gate_inputs(
    transport_status: TransportStatus,
    evidence_status: EvidenceStatus,
    observability_status: ObservabilityStatus,
    requires_review: bool,
    code: str,
) -> None:
    profile = _cross_graph_profile(
        transport_status=transport_status,
        evidence_status=evidence_status,
        observability_status=observability_status,
        requires_expert_review=requires_review,
    )

    issues = TransportabilityRequiredPass().validate(
        _strict_context({"cross_graph_evidence_profile": profile})
    )

    assert len(issues) == 1
    assert issues[0].code == code
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_cross_graph_profile_partial_candidate_warns_outside_strict() -> None:
    profile = _cross_graph_profile(
        transport_status=TransportStatus.PARTIALLY_IDENTIFIED,
        observability_status=ObservabilityStatus.MISSING,
    )
    ctx = PassContext(
        ir=None,
        state={"cross_graph_evidence_profile": profile},
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="R_transport_profile_candidate",
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REQUIRED_MISSING"
    assert issues[0].severity is IssueSeverity.WARNING


def test_cross_graph_profile_direct_and_cas_aliases_are_reconciled_once(tmp_path) -> None:
    profile = _cross_graph_profile()
    store = FileSystemCAS(tmp_path)
    profile_ref = persist_cross_graph_evidence_profile(_ensure_ir_artifact_store(store), profile)
    ctx = _strict_context(
        {
            "cross_graph_evidence_profile": profile,
            "artifacts_index": {"cross_graph_evidence_profile_ref": profile_ref},
            "_store": store,
        }
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_PROOF_GRADE_UNKNOWN"


def test_conflicting_direct_and_cas_profiles_do_not_select_either(tmp_path) -> None:
    direct = _cross_graph_profile(need_id="direct_profile")
    persisted = _cross_graph_profile(
        transport_status=TransportStatus.PARTIALLY_IDENTIFIED,
        need_id="cas_profile",
    )
    store = FileSystemCAS(tmp_path)
    profile_ref = persist_cross_graph_evidence_profile(_ensure_ir_artifact_store(store), persisted)
    ctx = _strict_context(
        {
            "cross_graph_evidence_profile": direct,
            "artifacts_index": {"cross_graph_evidence_profile_ref": profile_ref},
            "_store": store,
        }
    )

    issues = TransportabilityRequiredPass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "CROSS_GRAPH_PROFILE_SOURCE_CONFLICT"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_typed_profile_is_revalidated_after_mutable_nested_content_changes() -> None:
    profile = CrossGraphEvidenceProfile.model_construct(
        summary={},
        needs=[{"need": "not-a-typed-need", "transport_status": "identified"}],
    )

    issues = TransportabilityRequiredPass().validate(
        _strict_context({"cross_graph_evidence_profile": profile})
    )

    assert len(issues) == 1
    assert issues[0].code == "CROSS_GRAPH_PROFILE_INPUT_INVALID"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_mutated_typed_report_is_revalidated_before_transport_classification() -> None:
    report = _external_report(with_transport=False).model_copy(
        update={"transport_result": "forged"}
    )

    issues = TransportabilityRequiredPass().validate(_strict_context({"causal_report": report}))

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REPORT_INPUT_INVALID"
    assert issues[0].severity is IssueSeverity.BLOCKER


@pytest.mark.parametrize("raw_value", [None, 1, "sometimes", []])
def test_malformed_transport_required_parameter_is_not_defaulted_to_false(
    raw_value: object,
) -> None:
    issues = TransportabilityRequiredPass().validate(
        _strict_context({"params": {"transport_required": raw_value}})
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REQUIREMENT_INPUT_INVALID"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_malformed_transport_parameter_container_is_not_absence() -> None:
    issues = TransportabilityRequiredPass().validate(_strict_context({"params": None}))

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REQUIREMENT_INPUT_INVALID"
    assert issues[0].path == ["params"]
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_explicit_transport_required_without_any_admitted_evidence_blocks() -> None:
    issues = TransportabilityRequiredPass().validate(
        _strict_context({"params": {"transport_required": True}})
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REQUIRED_MISSING"
    assert issues[0].path == ["params", "transport_required"]
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_explicit_transport_required_does_not_default_an_internal_report_to_out_of_scope() -> None:
    report = _external_report(with_transport=False).model_copy(
        update={"method_params": {"source_type": "internal_model"}}
    )

    issues = TransportabilityRequiredPass().validate(
        _strict_context(
            {
                "causal_report": report,
                "params": {"transport_required": True},
            }
        )
    )

    assert len(issues) == 1
    assert issues[0].code == "TRANSPORT_REQUIRED_MISSING"
    assert issues[0].severity is IssueSeverity.BLOCKER


def test_explicit_false_transport_required_preserves_optional_no_input_case() -> None:
    issues = TransportabilityRequiredPass().validate(
        _strict_context({"params": {"transport_required": "false"}})
    )

    assert issues == []
