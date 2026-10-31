"""Selected IC proof outputs retain the actual selected source view."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts import ArtifactRef, ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.ic_verification import ICVerificationRequest
from polisyos.core.contracts.lex import IssueSeverity
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.ir.artifacts import InputRef
from polisyos.ir.trinity import (
    TrinityBundle,
    load_trinity_bundle_artifact,
    persist_trinity_bundle_artifact,
)
from polisyos.scientist.governance.passes.incentive_compatibility_pass import (
    IncentiveCompatibilityPass,
)
from polisyos.scientist.validation.verification.ic import (
    load_ic_certificate,
    load_ic_negative_certificate,
    load_ic_report,
    verify_incentive_compatibility,
)
from polisyos.scientist.validation.verification.ic.service import _load_ic_report_for_request
from tests.unit.scientist.governance.test_ic_verification import (
    _model_spec,
    _persist_trinity,
    _policy_with_design,
    _problem_frame,
    _single_buyer_design,
)
from tests.unit.scientist.governance.test_incentive_compatibility_pass import _family_tax_bundle


def _selected_trinity(store: FileSystemCAS, *, payment: str, marker: bool) -> ArtifactRef:
    bundle = TrinityBundle(
        problem_frame=_problem_frame(),
        policy_spec=_policy_with_design(_single_buyer_design(high_payment=payment)),
        model_spec=_model_spec(),
    )
    inputs = []
    if marker:
        marker_ref = store.put_json(
            {"fixture": "separate selected profile"},
            PutOptions(kind="scientist.test_marker", media_type="application/json"),
            return_selected_profile=True,
        )
        inputs.append(
            InputRef(
                artifact_id=marker_ref.artifact_id,
                role="fixture_marker",
                manifest_profile_sha256=marker_ref.manifest_profile_sha256,
            )
        )
    ref = persist_trinity_bundle_artifact(ensure_ir_artifact_store(store), bundle, inputs=inputs)
    return ArtifactRef.model_validate(ref.model_dump(mode="json"))


def _assert_result_sources(store, output_ref, source_ref, *, semantics_ref=None):
    assert output_ref.manifest_profile_sha256 is not None
    inputs = store.get_manifest(output_ref).inputs
    source_edges = [input_ref_from_artifact_ref(source_ref, role="input")]
    if semantics_ref is not None:
        source_edges.append(input_ref_from_artifact_ref(semantics_ref, role="semantics"))
    assert inputs[:-1] == source_edges
    assert inputs[-1].role == "verification_request"
    assert inputs[-1].manifest_profile_sha256 is not None
    request_ref = ArtifactRef(
        artifact_id=inputs[-1].artifact_id,
        kind="scientist.ic_verification_request",
        media_type="application/json",
        manifest_profile_sha256=inputs[-1].manifest_profile_sha256,
    )
    assert store.get_manifest(request_ref).inputs == source_edges
    return request_ref


def test_actual_ic_proof_retains_each_exact_same_bytes_source_profile(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = _selected_trinity(store, payment="5", marker=False)
    foreign_view = _selected_trinity(store, payment="5", marker=True)
    assert source.artifact_id == foreign_view.artifact_id
    assert source.manifest_profile_sha256 != foreign_view.manifest_profile_sha256

    outputs = [
        verify_incentive_compatibility(
            store, ICVerificationRequest(property="dominant_strategy_ic", input_ref=ref)
        )
        for ref in (source, foreign_view)
    ]
    assert all(result.ok and result.verdict == "positive" for result in outputs)
    for result, input_ref in zip(outputs, (source, foreign_view), strict=True):
        assert result.report_ref is not None and result.certificate_ref is not None
        for output_ref in (result.report_ref, result.certificate_ref):
            _assert_result_sources(store, output_ref, input_ref)
        assert load_ic_report(store, result.report_ref).verdict == "positive"
        assert load_ic_certificate(store, result.certificate_ref).witness["max_regret"] == "0"
    for attribute in ("report_ref", "certificate_ref"):
        left = getattr(outputs[0], attribute)
        right = getattr(outputs[1], attribute)
        assert left.artifact_id == right.artifact_id
        assert left.manifest_profile_sha256 != right.manifest_profile_sha256
    request_a = ICVerificationRequest(property="dominant_strategy_ic", input_ref=source)
    request_b = ICVerificationRequest(property="dominant_strategy_ic", input_ref=foreign_view)
    assert (
        _load_ic_report_for_request(store, outputs[0].report_ref, request_a).verdict == "positive"
    )
    with pytest.raises(ValueError, match="ic_result_source_edges_mismatch"):
        _load_ic_report_for_request(store, outputs[0].report_ref, request_b)


def test_actual_negative_ic_witness_is_also_bound_to_selected_source(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = _selected_trinity(store, payment="0", marker=False)
    result = verify_incentive_compatibility(
        store, ICVerificationRequest(property="dominant_strategy_ic", input_ref=source)
    )
    assert not result.ok and result.verdict == "negative"
    assert result.report_ref is not None and result.certificate_ref is not None
    for output_ref in (result.report_ref, result.certificate_ref):
        _assert_result_sources(store, output_ref, source)
    assert load_ic_report(store, result.report_ref).verdict == "negative"
    assert load_ic_negative_certificate(store, result.certificate_ref).witness["gain"] == "1"


def test_real_pass_recomputes_instead_of_reusing_a_different_source_profile(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = _selected_trinity(store, payment="5", marker=False)
    other = _selected_trinity(store, payment="5", marker=True)
    previous = verify_incentive_compatibility(
        store, ICVerificationRequest(property="dominant_strategy_ic", input_ref=source)
    )
    assert previous.report_ref is not None and previous.certificate_ref is not None
    state = {
        "_store": store,
        "artifacts_index": {
            "trinity_bundle_ref": other,
            "dominant_strategy_ic_report_ref": previous.report_ref,
            "dominant_strategy_ic_certificate_ref": previous.certificate_ref,
        },
    }
    ctx = PassContext(
        ir=load_trinity_bundle_artifact(ensure_ir_artifact_store(store), other),
        state=state,
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="synthetic",
    )
    assert IncentiveCompatibilityPass().validate(ctx) == []
    current = state["artifacts_index"]["dominant_strategy_ic_report_ref"]
    assert current.manifest_profile_sha256 != previous.report_ref.manifest_profile_sha256
    _assert_result_sources(store, current, other)


def test_real_pass_replaces_cached_positive_when_new_source_refutes_it(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    positive = _selected_trinity(store, payment="5", marker=False)
    negative = _selected_trinity(store, payment="0", marker=False)
    previous = verify_incentive_compatibility(
        store, ICVerificationRequest(property="dominant_strategy_ic", input_ref=positive)
    )
    assert previous.report_ref is not None and previous.certificate_ref is not None
    state = {
        "_store": store,
        "artifacts_index": {
            "trinity_bundle_ref": negative,
            "dominant_strategy_ic_report_ref": previous.report_ref,
            "dominant_strategy_ic_certificate_ref": previous.certificate_ref,
        },
    }
    ctx = PassContext(
        ir=load_trinity_bundle_artifact(ensure_ir_artifact_store(store), negative),
        state=state,
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="synthetic",
    )
    assert [issue.code for issue in IncentiveCompatibilityPass().validate(ctx)] == [
        "INCENTIVE_COMPATIBILITY_VIOLATED"
    ]
    assert "dominant_strategy_ic_certificate_ref" not in state["artifacts_index"]
    assert "dominant_strategy_ic_negative_certificate_ref" in state["artifacts_index"]
    _assert_result_sources(
        store, state["artifacts_index"]["dominant_strategy_ic_report_ref"], negative
    )


@pytest.mark.parametrize(
    "setting",
    [
        {"allow_payment_synthesis": False},
        {"backend_hint": "finite_exact"},
        {"exact_number_format": "decimal_string"},
        {"mode": "counterexample_search"},
    ],
)
def test_different_request_settings_cannot_reopen_the_same_proof(tmp_path, setting) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = _selected_trinity(store, payment="5", marker=False)
    request = ICVerificationRequest(property="dominant_strategy_ic", input_ref=source)
    result = verify_incentive_compatibility(store, request)
    assert result.report_ref is not None
    other = request.model_copy(update=setting)
    with pytest.raises(ValueError, match="ic_request_content_mismatch"):
        _load_ic_report_for_request(store, result.report_ref, other)


def test_same_semantics_bytes_under_different_profiles_remain_distinct(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = _selected_trinity(store, payment="5", marker=False)
    semantics = _single_buyer_design(high_payment="5").semantics
    assert semantics is not None
    marker = store.put_json(
        {"fixture": "different semantics view"},
        PutOptions(kind="scientist.test_marker", media_type="application/json"),
        return_selected_profile=True,
    )
    edges = ([], [input_ref_from_artifact_ref(marker, role="fixture_marker")])
    refs = [
        store.put_json(
            semantics.model_dump(mode="json"),
            PutOptions(
                kind="ir.mechanism_semantics",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.ir.governance.mechanism_semantics.MechanismSemanticsSpec",
                    version="1.0",
                ),
                inputs=inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        for inputs in edges
    ]
    assert refs[0].artifact_id == refs[1].artifact_id
    assert refs[0].manifest_profile_sha256 != refs[1].manifest_profile_sha256
    requests = [
        ICVerificationRequest(
            property="dominant_strategy_ic", input_ref=source, semantics_ref=semantics_ref
        )
        for semantics_ref in refs
    ]
    results = [verify_incentive_compatibility(store, request) for request in requests]
    assert all(result.ok and result.report_ref is not None for result in results)
    for result, ref in zip(results, refs, strict=True):
        _assert_result_sources(store, result.report_ref, source, semantics_ref=ref)
    with pytest.raises(ValueError, match="ic_result_source_edges_mismatch"):
        _load_ic_report_for_request(store, results[0].report_ref, requests[1])


def test_legacy_unselected_ic_output_remains_readable_but_unbound(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = TrinityBundle(
        problem_frame=_problem_frame(),
        policy_spec=_policy_with_design(_single_buyer_design(high_payment="5")),
        model_spec=_model_spec(),
    )
    source = _persist_trinity(store, bundle)
    request = ICVerificationRequest(property="dominant_strategy_ic", input_ref=source)
    result = verify_incentive_compatibility(store, request)
    assert result.report_ref is not None and result.report_ref.manifest_profile_sha256 is None
    assert load_ic_report(store, result.report_ref).verdict == "positive"
    with pytest.raises(ValueError, match="ic_selected_source_profile_not_established"):
        _load_ic_report_for_request(store, result.report_ref, request)


def test_real_pass_refuses_selected_trinity_that_differs_from_current_context(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    positive = _selected_trinity(store, payment="5", marker=False)
    negative = _selected_trinity(store, payment="0", marker=False)
    prior = verify_incentive_compatibility(
        store, ICVerificationRequest(property="dominant_strategy_ic", input_ref=positive)
    )
    state = {
        "_store": store,
        "artifacts_index": {
            "trinity_bundle_ref": positive,
            "dominant_strategy_ic_report_ref": prior.report_ref,
            "dominant_strategy_ic_certificate_ref": prior.certificate_ref,
        },
    }
    ctx = PassContext(
        ir=load_trinity_bundle_artifact(ensure_ir_artifact_store(store), negative),
        state=state,
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="synthetic",
    )
    issues = IncentiveCompatibilityPass().validate(ctx)
    assert [issue.code for issue in issues] == ["INCENTIVE_COMPATIBILITY_UNCERTIFIED"]
    assert issues[0].severity is IssueSeverity.BLOCKER
    assert "ic_selected_trinity_context_mismatch" in issues[0].input_value
    assert "dominant_strategy_ic_certificate_ref" not in state["artifacts_index"]
    assert "dominant_strategy_ic_report_ref" not in state["artifacts_index"]


def test_family_sidecars_retain_selected_request_and_same_bytes_source_profiles(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = _family_tax_bundle()
    marker = store.put_json(
        {"fixture": "separate family profile"},
        PutOptions(kind="scientist.test_marker", media_type="application/json"),
        return_selected_profile=True,
    )
    sources = [
        ArtifactRef.model_validate(
            persist_trinity_bundle_artifact(
                ensure_ir_artifact_store(store), bundle, inputs=edges
            ).model_dump(mode="json")
        )
        for edges in (
            [],
            [
                InputRef.model_validate(
                    input_ref_from_artifact_ref(marker, role="fixture_marker").model_dump()
                )
            ],
        )
    ]
    assert sources[0].artifact_id == sources[1].artifact_id
    assert sources[0].manifest_profile_sha256 != sources[1].manifest_profile_sha256
    outputs = [
        verify_incentive_compatibility(
            store, ICVerificationRequest(property="bayesian_ic", input_ref=source)
        )
        for source in sources
    ]
    sidecars = []
    for result, source in zip(outputs, sources, strict=True):
        assert result.ok and result.certificate_ref is not None
        _assert_result_sources(store, result.report_ref, source)
        _assert_result_sources(store, result.certificate_ref, source)
        certificate = load_ic_certificate(store, result.certificate_ref)
        assert len(certificate.proof_artifacts) == 3
        for sidecar in certificate.proof_artifacts:
            _assert_result_sources(store, sidecar, source)
        sidecars.append(certificate.proof_artifacts)
    for left, right in zip(*sidecars, strict=True):
        assert left.artifact_id == right.artifact_id
        assert left.manifest_profile_sha256 != right.manifest_profile_sha256


@pytest.mark.parametrize("source_mode", ["unselected", "ephemeral"])
def test_strict_pass_requires_selected_persisted_source(tmp_path, source_mode) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = TrinityBundle(
        problem_frame=_problem_frame(),
        policy_spec=_policy_with_design(_single_buyer_design(high_payment="5")),
        model_spec=_model_spec(),
    )
    state = {"artifacts_index": {}}
    if source_mode == "unselected":
        state["_store"] = store
        state["artifacts_index"]["trinity_bundle_ref"] = _persist_trinity(store, bundle)
    ctx = PassContext(
        ir=bundle,
        state=state,
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="synthetic",
    )
    issues = IncentiveCompatibilityPass().validate(ctx)
    assert [issue.code for issue in issues] == ["INCENTIVE_COMPATIBILITY_UNCERTIFIED"]
    assert issues[0].severity is IssueSeverity.BLOCKER
    assert "ic_selected_trinity_profile_not_established" in issues[0].input_value
    assert "dominant_strategy_ic_certificate_ref" not in state["artifacts_index"]


@pytest.mark.parametrize("withdrawal", ["remove_design", "remove_constraints"])
def test_withdrawing_claim_clears_all_owned_old_proof_selections(tmp_path, withdrawal) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source = _selected_trinity(store, payment="5", marker=False)
    bundle = load_trinity_bundle_artifact(ensure_ir_artifact_store(store), source)
    prior = verify_incentive_compatibility(
        store, ICVerificationRequest(property="dominant_strategy_ic", input_ref=source)
    )
    assert bundle.policy_spec.mechanism_design is not None
    new_design = (
        None
        if withdrawal == "remove_design"
        else bundle.policy_spec.mechanism_design.model_copy(update={"constraints": []})
    )
    without_claim = bundle.model_copy(
        update={
            "policy_spec": bundle.policy_spec.model_copy(update={"mechanism_design": new_design})
        }
    )
    sentinel = {"other_owner": "preserved"}
    state = {
        "_store": store,
        "artifacts_index": {
            "trinity_bundle_ref": source,
            "dominant_strategy_ic_report_ref": prior.report_ref,
            "dominant_strategy_ic_certificate_ref": prior.certificate_ref,
            "bayesian_ic_family_mechanism_family_spec_ref": prior.certificate_ref,
            "ex_post_ir_mechanism_ic_certificate_ref": prior.certificate_ref,
            "ex_interim_ir_family_mechanism_welfare_loss_bound_ref": prior.certificate_ref,
            "sibling_report_ref": sentinel,
        },
        "ic_verification": {
            property_name: {"verdict": "positive"}
            for property_name in (
                "dominant_strategy_ic",
                "bayesian_ic",
                "ex_post_ir",
                "ex_interim_ir",
            )
        },
    }
    ctx = PassContext(
        ir=without_claim,
        state=state,
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="synthetic",
    )
    assert IncentiveCompatibilityPass().validate(ctx) == []
    assert "dominant_strategy_ic_report_ref" not in state["artifacts_index"]
    assert "dominant_strategy_ic_certificate_ref" not in state["artifacts_index"]
    assert set(state["artifacts_index"]) == {"trinity_bundle_ref", "sibling_report_ref"}
    assert state["ic_verification"] == {}
    assert state["artifacts_index"]["sibling_report_ref"] is sentinel
