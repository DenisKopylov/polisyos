from __future__ import annotations

import logging

import pytest

from polisyos.core.artifacts import SchemaInfo
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.ic_verification import (
    ICVerificationCertificateRef,
    IncentiveCompatibilityCertificate,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.catalog.microsim.protocols import MicrosimResult
from polisyos.ir.analytics.decision_layer import (
    FiscalFeedbackLink,
    SocialWeightManifestArtifact,
    build_optimization_ambiguity_certificate,
    load_fiscal_feedback_link,
    load_optimization_ambiguity_certificate,
    load_social_weight_manifest,
    persist_fiscal_feedback_link,
    persist_optimization_ambiguity_certificate,
    persist_social_weight_manifest,
)
from polisyos.ir.analytics.welfare import (
    ChannelDecompositionArtifact,
    ChannelDecompositionTargetKind,
    ChannelIdentificationStatus,
    ChannelPolicyClass,
    GEUncertaintyBundle,
    GEUncertaintyRepresentation,
    WelfareBundle,
    WelfareIntervalSemantics,
    WelfareMethod,
    WelfareStatus,
    load_welfare_bundle,
    persist_channel_decomposition_artifact,
    persist_ge_uncertainty_bundle,
    persist_welfare_bundle,
)
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    IncentiveCompatibilityCertificateRef,
    MechanismWelfareLossBoundRef,
    OptimizationAmbiguityCertificateRef,
    WelfareBundleRef,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_WELFARE_BUNDLE_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.phase3 import (
    Phase3CertificateStatus,
    phase3_gate_reference_blockers,
    resolve_phase3_gate,
)


def _ctx(tmp_path) -> ExecutionContext:
    store = FileSystemCAS(tmp_path / "cas")
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_phase3")
    return ExecutionContext(store=store, run=run, logger=logging.getLogger("test.phase3"))


def _complete_welfare_ref(ctx: ExecutionContext):
    matrix_ref = ctx.store.put_json(
        {"matrix": [[1]]},
        PutOptions(kind="ir.welfare_multiplier_matrix", media_type="application/json"),
    )
    social_weight_ref = persist_social_weight_manifest(
        _ensure_ir_artifact_store(ctx.store),
        SocialWeightManifestArtifact(
            manifest_ref="swr://phase3/test@1.0.0#weights",
            method_fqn="policy.welfare.state_dependent_inverse_social_weights@1.0.0",
            normalization="mean_one",
            income_grid=(0.0, 1.0),
            weights_on_grid=(1.2, 0.8),
            state_keys=("income",),
        ),
    )
    ge_ref = persist_ge_uncertainty_bundle(
        _ensure_ir_artifact_store(ctx.store),
        GEUncertaintyBundle(
            model_class="linearized_ge_io",
            representation=GEUncertaintyRepresentation.MULTIPLIER_INTERVALS,
            multiplier_shape=(1, 1),
            point_multiplier_ref=ArtifactRefModel.model_validate(
                matrix_ref.model_dump(mode="json")
            ),
            lower_multiplier_ref=ArtifactRefModel.model_validate(
                matrix_ref.model_dump(mode="json")
            ),
            upper_multiplier_ref=ArtifactRefModel.model_validate(
                matrix_ref.model_dump(mode="json")
            ),
        ),
    )
    return persist_welfare_bundle(
        _ensure_ir_artifact_store(ctx.store),
        WelfareBundle(
            welfare_measure="net_social_welfare",
            model_class="linearized_ge_io",
            ge_multiplier_semantics="leontief_inverse",
            social_weight_ref=social_weight_ref,
            ge_uncertainty_ref=ge_ref,
            point_estimate=1.0,
            credible_interval=(0.9, 1.1),
            robust_interval=(0.8, 1.2),
            interval_semantics=WelfareIntervalSemantics.MIXED_NESTED,
            method_used=WelfareMethod.MIXED_NESTED,
            status=WelfareStatus.OK,
        ),
    )


def _identified_behavioral_channel_ref(ctx: ExecutionContext):
    return persist_channel_decomposition_artifact(
        _ensure_ir_artifact_store(ctx.store),
        ChannelDecompositionArtifact(
            target_kind=ChannelDecompositionTargetKind.SOCIAL_WELFARE,
            policy_class=ChannelPolicyClass.LOCAL_AFFINE_TAX_TRANSFER,
            basis_labels=("delta_tax_rate",),
            step_vector=(0.02,),
            mechanical_vector=(0.6,),
            behavioral_vector=(-0.2,),
            fiscal_feedback_vector=(0.1,),
            total_vector=(0.5,),
            identification_status=ChannelIdentificationStatus.IDENTIFIED,
            baseline_microdata_ref=ArtifactRefModel(
                artifact_id="sha256:" + "2" * 64,
                kind="ir.baseline_microdata",
                media_type="application/json",
            ),
            policy_basis_ref=ArtifactRefModel(
                artifact_id="sha256:" + "3" * 64,
                kind="ir.policy_basis",
                media_type="application/json",
            ),
            mechanical_inputs_ref=ArtifactRefModel(
                artifact_id="sha256:" + "4" * 64,
                kind="ir.mechanical_inputs",
                media_type="application/json",
            ),
        ),
    )


def test_phase3_persisted_contracts_round_trip(tmp_path) -> None:
    ctx = _ctx(tmp_path)

    ambiguity_ref = persist_optimization_ambiguity_certificate(
        _ensure_ir_artifact_store(ctx.store),
        build_optimization_ambiguity_certificate(
            {"mode": "wasserstein", "radius": 0.05, "overall_status": "pass"},
            mode="wasserstein",
            source_kind="dro_payload",
            overall_status="pass",
        ),
    )
    loaded_ambiguity = load_optimization_ambiguity_certificate(
        _ensure_ir_artifact_store(ctx.store), ambiguity_ref
    )
    assert loaded_ambiguity.mode == "wasserstein"
    assert loaded_ambiguity.certificate_payload["radius"] == 0.05

    social_weight_ref = persist_social_weight_manifest(
        _ensure_ir_artifact_store(ctx.store),
        SocialWeightManifestArtifact(
            manifest_ref="swr://phase3/round-trip@1.0.0#weights",
            method_fqn="policy.welfare.state_dependent_inverse_social_weights@1.0.0",
            normalization="mean_one",
            income_grid=(0.0, 0.5, 1.0),
            weights_on_grid=(1.5, 1.0, 0.5),
            state_keys=("income", "region"),
        ),
    )
    loaded_social_weight = load_social_weight_manifest(
        _ensure_ir_artifact_store(ctx.store), social_weight_ref
    )
    assert loaded_social_weight.state_keys == ("income", "region")
    assert loaded_social_weight.weights_on_grid == (1.5, 1.0, 0.5)

    microsim_result_ref = ArtifactRefModel(
        artifact_id="sha256:" + "1" * 64,
        kind="foundry.microsim.result",
        media_type="application/json",
    )
    feedback_ref = persist_fiscal_feedback_link(
        _ensure_ir_artifact_store(ctx.store),
        FiscalFeedbackLink(
            microsim_result_ref=microsim_result_ref,
            ambiguity_certificate_ref=ambiguity_ref,
            metadata={"source": "unit_test"},
        ),
    )
    loaded_feedback = load_fiscal_feedback_link(_ensure_ir_artifact_store(ctx.store), feedback_ref)
    assert loaded_feedback.microsim_result_ref == microsim_result_ref
    assert loaded_feedback.ambiguity_certificate_ref == ambiguity_ref


def test_social_weight_writer_returns_same_write_selected_profile(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    ir_store = _ensure_ir_artifact_store(ctx.store)
    artifact = SocialWeightManifestArtifact(
        manifest_ref="swr://phase3/selected-profile@1.0.0#weights",
        method_fqn="policy.welfare.state_dependent_inverse_social_weights@1.0.0",
        normalization="mean_one",
        income_grid=(0.0, 1.0),
        weights_on_grid=(1.2, 0.8),
        state_keys=("income",),
    )

    legacy_ref = persist_social_weight_manifest(ir_store, artifact)
    selected_ref = persist_social_weight_manifest(ir_store, artifact, return_selected_profile=True)

    assert selected_ref.artifact_id == legacy_ref.artifact_id
    assert selected_ref.manifest_profile_sha256 is not None
    assert load_social_weight_manifest(ir_store, selected_ref) == artifact


def test_phase3_status_accepts_legacy_payload_without_new_fields() -> None:
    status = Phase3CertificateStatus.model_validate({})

    assert status.welfare_bundle_ref is None
    assert status.ambiguity_certificate_ref is None
    assert status.gate_passed is False
    assert status.blocking_reasons == []


def test_phase3_status_normalizes_forged_passed_gate() -> None:
    status = Phase3CertificateStatus(gate_passed=True)

    assert status.gate_passed is False
    assert "phase3.welfare_missing" in status.blocking_reasons
    assert "phase3.ambiguity_missing" in status.blocking_reasons


def test_phase3_gate_materializes_deterministic_ambiguity_for_complete_welfare(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    welfare_ref = _complete_welfare_ref(ctx)
    state = ExperimentState(
        run_id="R_phase3",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: welfare_ref},
    )

    gate = resolve_phase3_gate(ctx, state)

    assert gate.gate_passed is True
    assert gate.welfare_bundle_ref == welfare_ref
    assert gate.ambiguity_certificate_ref is not None
    ambiguity = load_optimization_ambiguity_certificate(
        _ensure_ir_artifact_store(ctx.store), gate.ambiguity_certificate_ref
    )
    assert ambiguity.mode == "not_applicable"


def test_phase3_gate_blocks_stochastic_path_without_ambiguity_payload(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    welfare_ref = _complete_welfare_ref(ctx)
    state = ExperimentState(
        run_id="R_phase3",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: welfare_ref},
        params={"moment_dro_result": {"objective_value": 1.0}},
    )

    gate = resolve_phase3_gate(ctx, state)

    assert gate.gate_passed is False
    assert gate.ambiguity_certificate_ref is None
    assert "phase3.ambiguity_missing" in gate.blocking_reasons


def test_phase3_gate_materializes_explicit_stochastic_ambiguity_payload(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    welfare_ref = _complete_welfare_ref(ctx)
    state = ExperimentState(
        run_id="R_phase3",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: welfare_ref},
        params={
            "moment_dro_result": {
                "ambiguity_certificate": {
                    "mode": "wasserstein",
                    "radius": 0.05,
                    "overall_status": "pass",
                }
            }
        },
    )

    gate = resolve_phase3_gate(ctx, state)

    assert gate.gate_passed is True
    assert gate.ambiguity_certificate_ref is not None
    ambiguity = load_optimization_ambiguity_certificate(
        _ensure_ir_artifact_store(ctx.store), gate.ambiguity_certificate_ref
    )
    assert ambiguity.mode == "wasserstein"


def test_phase3_reference_blockers_reject_unloadable_passed_refs(tmp_path) -> None:
    status = Phase3CertificateStatus(
        welfare_bundle_ref={
            "artifact_id": "sha256:" + "a" * 64,
            "kind": "ir.welfare_bundle",
            "media_type": "application/json",
        },
        ambiguity_certificate_ref={
            "artifact_id": "sha256:" + "b" * 64,
            "kind": "ir.optimization_ambiguity_certificate",
            "media_type": "application/json",
        },
        gate_passed=True,
    )
    ctx = _ctx(tmp_path)

    blockers = phase3_gate_reference_blockers(ctx.store, status)

    assert "phase3.welfare_missing" in blockers
    assert "phase3.ambiguity_missing" in blockers


def test_phase3_reference_blocker_reads_selected_certificate_view(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    payload = IncentiveCompatibilityCertificate(
        property="dominant_strategy_ic",
        backend="finite_exact",
        input_digest="sha256:" + "c" * 64,
        arithmetic="rational",
    )
    default_ref = ctx.store.put_json(
        payload,
        PutOptions(
            kind="scientist.ic_certificate",
            media_type="application/json",
            schema=SchemaInfo(name="tests.phase3.ic_certificate", version="1"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    selected_ref = ctx.store.put_json(
        payload,
        PutOptions(
            kind="scientist.ic_certificate",
            media_type="application/json",
            schema=SchemaInfo(name="tests.phase3.ic_certificate", version="2"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert default_ref.artifact_id == selected_ref.artifact_id
    assert default_ref.manifest_profile_sha256 != selected_ref.manifest_profile_sha256

    class RecordingStore:
        def __init__(self, store: FileSystemCAS) -> None:
            self.store = store
            self.read_selectors: list[object] = []

        def get_bytes(self, selector: object) -> bytes:
            self.read_selectors.append(selector)
            return self.store.get_bytes(selector)

        def __getattr__(self, name: str) -> object:
            return getattr(self.store, name)

    selected_certificate = ICVerificationCertificateRef.model_validate(
        selected_ref.model_dump(mode="python")
    )
    selected_profile = selected_ref.manifest_profile_sha256
    sibling_id = selected_ref.artifact_id
    status = Phase3CertificateStatus(
        welfare_bundle_ref=WelfareBundleRef(
            artifact_id=sibling_id,
            manifest_profile_sha256=selected_profile,
        ),
        ambiguity_certificate_ref=OptimizationAmbiguityCertificateRef(
            artifact_id=sibling_id,
            manifest_profile_sha256=selected_profile,
        ),
        semantic_ic_certificate_ref=selected_certificate,
        mechanism_ic_certificate_ref=IncentiveCompatibilityCertificateRef(
            artifact_id=sibling_id,
            manifest_profile_sha256=selected_profile,
        ),
        mechanism_welfare_loss_bound_ref=MechanismWelfareLossBoundRef(
            artifact_id=sibling_id,
            manifest_profile_sha256=selected_profile,
        ),
        mechanism_required=True,
        gate_passed=True,
    )
    recording_store = RecordingStore(ctx.store)

    blockers = phase3_gate_reference_blockers(recording_store, status)

    assert selected_certificate in recording_store.read_selectors
    assert selected_certificate.manifest_profile_sha256 == selected_ref.manifest_profile_sha256
    assert "phase3.welfare_missing" in blockers
    assert "phase3.ambiguity_missing" in blockers


def test_phase3_gate_blocks_missing_social_weight_even_when_welfare_loads(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    welfare_ref = persist_welfare_bundle(
        _ensure_ir_artifact_store(ctx.store),
        WelfareBundle(
            welfare_measure="net_social_welfare",
            model_class="linearized_ge_io",
            ge_multiplier_semantics="leontief_inverse",
            point_estimate=1.0,
            method_used=WelfareMethod.DETERMINISTIC,
            status=WelfareStatus.OK,
            ge_uncertainty_ref=persist_ge_uncertainty_bundle(
                _ensure_ir_artifact_store(ctx.store),
                GEUncertaintyBundle(
                    model_class="linearized_ge_io",
                    representation=GEUncertaintyRepresentation.MULTIPLIER_INTERVALS,
                    multiplier_shape=(1, 1),
                ),
            ),
        ),
    )
    state = ExperimentState(
        run_id="R_phase3",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: welfare_ref},
    )

    gate = resolve_phase3_gate(ctx, state)

    assert gate.gate_passed is False
    assert "phase3.social_weight_missing" in gate.blocking_reasons


def test_phase3_gate_requires_fiscal_feedback_only_when_requested(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    welfare_ref = _complete_welfare_ref(ctx)
    state = ExperimentState(
        run_id="R_phase3",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: welfare_ref},
        params={"require_phase3_fiscal_feedback": True},
    )

    gate = resolve_phase3_gate(ctx, state)

    assert gate.fiscal_feedback_required is True
    assert gate.gate_passed is False
    assert "phase3.fiscal_feedback_missing" in gate.blocking_reasons


def test_phase3_gate_requires_fiscal_feedback_for_behavioral_microsim_path(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    welfare_ref = _complete_welfare_ref(ctx)
    welfare = load_welfare_bundle(_ensure_ir_artifact_store(ctx.store), welfare_ref).model_copy(
        update={"channel_decomposition_ref": _identified_behavioral_channel_ref(ctx)}
    )
    welfare_ref = persist_welfare_bundle(_ensure_ir_artifact_store(ctx.store), welfare)
    state = ExperimentState(
        run_id="R_phase3",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: welfare_ref},
        params={
            "microsim_result": MicrosimResult(
                disposable_income=[10.0],
                tax_liability=[1.0],
                benefit_income=[0.0],
                weighted_mean_disposable_income=10.0,
                weighted_gini=0.1,
                policy_revenue=1.0,
            ).model_dump(mode="json")
        },
    )

    gate = resolve_phase3_gate(ctx, state)

    assert gate.fiscal_feedback_required is False
    assert gate.gate_passed is False
    assert gate.fiscal_feedback_ref is None
    assert "phase3.welfare_channel_input_owner_not_established" in gate.blocking_reasons


def test_phase3_gate_blocks_behavioral_microsim_when_feedback_link_cannot_materialize(
    tmp_path,
) -> None:
    ctx = _ctx(tmp_path)
    welfare_ref = _complete_welfare_ref(ctx)
    state = ExperimentState(
        run_id="R_phase3",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: welfare_ref},
        params={
            "behavioral_microsim": True,
            "microsim_result": MicrosimResult(
                disposable_income=[10.0],
                tax_liability=[1.0],
                benefit_income=[0.0],
                weighted_mean_disposable_income=10.0,
                weighted_gini=0.1,
                policy_revenue=1.0,
            ).model_dump(mode="json"),
        },
    )

    gate = resolve_phase3_gate(ctx, state)

    assert gate.fiscal_feedback_required is True
    assert gate.gate_passed is False
    assert "phase3.fiscal_feedback_missing" in gate.blocking_reasons


def test_microsim_result_serializes_optional_fiscal_feedback_ref(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    ambiguity_ref = persist_optimization_ambiguity_certificate(
        _ensure_ir_artifact_store(ctx.store),
        build_optimization_ambiguity_certificate(
            {"mode": "not_applicable"},
            mode="not_applicable",
            source_kind="test",
            overall_status="pass",
        ),
    )
    feedback_ref = persist_fiscal_feedback_link(
        _ensure_ir_artifact_store(ctx.store),
        FiscalFeedbackLink(ambiguity_certificate_ref=ambiguity_ref),
    )

    result = MicrosimResult(
        disposable_income=[10.0, 12.0],
        tax_liability=[1.0, 2.0],
        benefit_income=[0.0, 1.0],
        weighted_mean_disposable_income=11.0,
        weighted_gini=0.2,
        policy_revenue=3.0,
        fiscal_feedback_ref=feedback_ref,
    )
    round_tripped = MicrosimResult.model_validate(result.model_dump(mode="json"))
    legacy = MicrosimResult.model_validate(
        {
            "disposable_income": [10.0],
            "tax_liability": [1.0],
            "benefit_income": [0.0],
            "weighted_mean_disposable_income": 10.0,
            "weighted_gini": 0.1,
            "policy_revenue": 1.0,
        }
    )

    assert round_tripped.fiscal_feedback_ref == feedback_ref
    assert legacy.fiscal_feedback_ref is None


def test_phase3_selected_candidate_refusal_blocks_clear_gate(monkeypatch, tmp_path) -> None:
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.scientist.policy_design import phase3 as phase3_module

    ctx = _ctx(tmp_path)
    state = ExperimentState(
        run_id="R_phase3_selected_candidate_refusal",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: _complete_welfare_ref(ctx)},
        params={
            "policy_candidate_ref": {
                "artifact_id": "sha256:" + "a" * 64,
                "kind": "scientist.policy_design.candidate",
                "media_type": "application/json",
                "manifest_profile_sha256": "sha256:" + "b" * 64,
            }
        },
    )

    def refuse(_store, _ref):
        raise CanonicalProfileRefusalError("canon_profile_not_verified")

    monkeypatch.setattr(phase3_module, "load_policy_candidate_schema", refuse)
    gate = resolve_phase3_gate(ctx, state)

    assert gate.gate_passed is False
    assert (
        "phase3.selected_candidate_unreadable:canon_profile_not_verified" in gate.blocking_reasons
    )
    assert "phase3.mechanism_certificate_missing" not in gate.blocking_reasons


@pytest.mark.parametrize(
    ("selected_key", "selected_payload", "selected_ref"),
    [
        pytest.param(
            "ambiguity_certificate_ref",
            {"mode": "wasserstein", "radius": 0.05, "overall_status": "pass"},
            True,
            id="ambiguity-ref",
        ),
        pytest.param(
            "moment_dro_certificate_ref",
            {"mode": "wasserstein", "radius": 0.05, "overall_status": "pass"},
            True,
            id="moment-dro-ref",
        ),
        pytest.param(
            "ambiguity_certificate",
            {"unexpected": "shape"},
            False,
            id="ambiguity-inline",
        ),
        pytest.param(
            "moment_dro_certificate",
            {"unexpected": "shape"},
            False,
            id="moment-dro-inline",
        ),
    ],
)
@pytest.mark.parametrize(
    ("phase3_ambiguity_required", "require_phase3_ambiguity"),
    [
        pytest.param(None, None, id="both-absent"),
        pytest.param(False, None, id="primary-false"),
        pytest.param(True, None, id="primary-true"),
        pytest.param(None, False, id="alias-false"),
        pytest.param(None, True, id="alias-true"),
        pytest.param(False, False, id="both-false"),
        pytest.param(False, True, id="alias-true-primary-false"),
        pytest.param(True, False, id="primary-true-alias-false"),
        pytest.param(True, True, id="both-true"),
    ],
)
def test_phase3_malformed_selected_ambiguity_is_blocked_for_every_requirement_flag(
    tmp_path,
    selected_key: str,
    selected_payload: object,
    selected_ref: bool,
    phase3_ambiguity_required: bool | None,
    require_phase3_ambiguity: bool | None,
) -> None:
    ctx = _ctx(tmp_path / f"{selected_key}-{phase3_ambiguity_required}-{require_phase3_ambiguity}")
    params: dict[str, object] = {}
    if selected_ref:
        persisted_ref = ctx.store.put_json(
            selected_payload,
            PutOptions(
                kind="ir.optimization_ambiguity_certificate",
                media_type="application/json",
                schema=SchemaInfo(
                    name="ir.optimization_ambiguity_certificate",
                    version="1.0",
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        selected_value = persisted_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "f" * 64}
        )
        params[selected_key] = selected_value.model_dump(mode="json")
    else:
        params[selected_key] = selected_payload
    if phase3_ambiguity_required is not None:
        params["phase3_ambiguity_required"] = phase3_ambiguity_required
    if require_phase3_ambiguity is not None:
        params["require_phase3_ambiguity"] = require_phase3_ambiguity
    state = ExperimentState(
        run_id=f"R_phase3_malformed_{selected_key}_{phase3_ambiguity_required}_{require_phase3_ambiguity}",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: _complete_welfare_ref(ctx)},
        params=params,
    )

    gate = resolve_phase3_gate(ctx, state)

    assert gate.gate_passed is False
    assert gate.ambiguity_certificate_ref is None
    assert any(
        reason.startswith("phase3.selected_ambiguity_unreadable:")
        for reason in gate.blocking_reasons
    )


def test_phase3_malformed_inline_candidate_does_not_become_absence(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    state = ExperimentState(
        run_id="R_phase3_malformed_inline_candidate",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: _complete_welfare_ref(ctx)},
        params={"policy_candidate_schema": {"schema_version": "invalid"}},
    )

    gate = resolve_phase3_gate(ctx, state)

    assert gate.gate_passed is False
    assert any(
        reason.startswith("phase3.selected_candidate_unreadable:")
        for reason in gate.blocking_reasons
    )


def test_selected_ambiguity_alias_preserves_valid_refusal_and_absence(tmp_path) -> None:
    from polisyos.core.artifacts import SchemaInfo

    def selected_ref(ctx, payload):
        return ctx.store.put_json(
            payload,
            PutOptions(
                kind="ir.optimization_ambiguity_certificate",
                media_type="application/json",
                schema=SchemaInfo(
                    name="ir.optimization_ambiguity_certificate",
                    version="1.0",
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )

    valid_ctx = _ctx(tmp_path / "valid")
    valid_welfare_ref = _complete_welfare_ref(valid_ctx)
    valid_ref = selected_ref(
        valid_ctx,
        {"mode": "wasserstein", "radius": 0.05, "overall_status": "pass"},
    )
    valid_state = ExperimentState(
        run_id="R_phase3_valid_selected_ambiguity",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: valid_welfare_ref},
        params={"ambiguity_certificate_ref": valid_ref.model_dump(mode="json")},
    )
    valid_gate = resolve_phase3_gate(valid_ctx, valid_state)
    assert valid_gate.gate_passed is True
    assert valid_gate.ambiguity_certificate_ref is not None
    assert (
        load_optimization_ambiguity_certificate(
            _ensure_ir_artifact_store(valid_ctx.store),
            valid_gate.ambiguity_certificate_ref,
        ).mode
        == "wasserstein"
    )

    malformed_ctx = _ctx(tmp_path / "malformed-profile")
    malformed_welfare_ref = _complete_welfare_ref(malformed_ctx)
    malformed_ref = selected_ref(
        malformed_ctx,
        {"mode": "wasserstein", "radius": 0.05, "overall_status": "pass"},
    )
    malformed_ref = malformed_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "f" * 64}
    )
    malformed_state = ExperimentState(
        run_id="R_phase3_malformed_selected_ambiguity_profile",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: malformed_welfare_ref},
        params={"ambiguity_certificate_ref": malformed_ref.model_dump(mode="json")},
    )
    malformed_gate = resolve_phase3_gate(malformed_ctx, malformed_state)
    assert malformed_gate.gate_passed is False
    assert malformed_gate.ambiguity_certificate_ref is None
    assert any(
        reason.startswith("phase3.selected_ambiguity_unreadable:")
        for reason in malformed_gate.blocking_reasons
    )

    invalid_payload_ctx = _ctx(tmp_path / "invalid-payload")
    invalid_payload_welfare_ref = _complete_welfare_ref(invalid_payload_ctx)
    invalid_payload_ref = selected_ref(invalid_payload_ctx, {"unexpected": True})
    invalid_payload_state = ExperimentState(
        run_id="R_phase3_invalid_selected_ambiguity_payload",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: invalid_payload_welfare_ref},
        params={"ambiguity_certificate_ref": invalid_payload_ref.model_dump(mode="json")},
    )
    invalid_payload_gate = resolve_phase3_gate(invalid_payload_ctx, invalid_payload_state)
    assert invalid_payload_gate.gate_passed is False
    assert invalid_payload_gate.ambiguity_certificate_ref is None
    assert (
        "phase3.selected_ambiguity_unreadable:"
        "phase3_ambiguity_certificate_ref_payload_invalid" in invalid_payload_gate.blocking_reasons
    )

    absent_ctx = _ctx(tmp_path / "absent")
    absent_state = ExperimentState(
        run_id="R_phase3_absent_ambiguity",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: _complete_welfare_ref(absent_ctx)},
        params={},
    )
    absent_gate = resolve_phase3_gate(absent_ctx, absent_state)
    assert absent_gate.gate_passed is True
    assert absent_gate.ambiguity_certificate_ref is not None
    assert (
        load_optimization_ambiguity_certificate(
            _ensure_ir_artifact_store(absent_ctx.store), absent_gate.ambiguity_certificate_ref
        ).mode
        == "not_applicable"
    )


def test_selected_mechanism_candidate_profile_refusal_reaches_decision_packet(tmp_path) -> None:
    from polisyos.core.artifacts import SchemaInfo
    from polisyos.ir.governance.game_design import (
        BayesianTypeSpec,
        MechanismDesignSpec,
        MechanismGameRepresentation,
    )
    from polisyos.ir.governance.policy_spec import PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.scientist.nodes.builtins.decide.decision_packet.outcome_sections import (
        _build_phase3_section,
    )
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

    ctx = _ctx(tmp_path)
    candidate = PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id="phase3_selected_candidate_problem",
                domain=ProblemDomain.FISCAL,
            ),
            policy_spec=PolicySpec(
                policy_id="phase3_selected_candidate_policy",
                mechanism_design=MechanismDesignSpec(
                    design_id="phase3_selected_candidate_design",
                    representation=MechanismGameRepresentation.BAYESIAN,
                    players=("agent",),
                    action_spaces={"agent": ("low", "high")},
                    bayesian_types=[
                        BayesianTypeSpec(
                            player_id="agent",
                            type_space=("low", "high"),
                            prior_probabilities={"low": 0.5, "high": 0.5},
                        )
                    ],
                ),
            ),
            model_spec=ModelSpec(
                model_id="phase3_selected_candidate_model",
                data_snapshot_ref="sha256:" + "1" * 64,
            ),
        ),
        candidate_id="phase3_selected_candidate",
    )
    selected_ref = ctx.store.put_json(
        candidate.model_dump(mode="json"),
        PutOptions(
            kind="scientist.policy_design.candidate",
            media_type="application/json",
            schema=SchemaInfo(
                name=PolicyCandidateSchema.ARTIFACT_SCHEMA_NAME,
                version=PolicyCandidateSchema.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    welfare_ref = _complete_welfare_ref(ctx)

    valid_state = ExperimentState(
        run_id="R_phase3_selected_candidate_valid",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: welfare_ref},
        params={"policy_candidate_ref": selected_ref.model_dump(mode="json")},
    )
    valid_section = _build_phase3_section(ctx, valid_state)
    assert valid_section["refusal_status"] == "blocked"
    assert valid_section["mechanism_required"] is True
    assert "phase3.mechanism_certificate_missing" in valid_section["blocking_reasons"]

    malformed_ref = selected_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + "f" * 64}
    )
    malformed_state = ExperimentState(
        run_id="R_phase3_selected_candidate_malformed_profile",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: welfare_ref},
        params={"policy_candidate_ref": malformed_ref.model_dump(mode="json")},
    )
    malformed_section = _build_phase3_section(ctx, malformed_state)
    assert malformed_section["refusal_status"] == "blocked"
    assert malformed_section["gate_passed"] is False
    assert any(
        reason.startswith("phase3.selected_candidate_unreadable:")
        for reason in malformed_section["blocking_reasons"]
    )

    absent_state = ExperimentState(
        run_id="R_phase3_selected_candidate_absent",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: welfare_ref},
        params={},
    )
    absent_section = _build_phase3_section(ctx, absent_state)
    assert absent_section["refusal_status"] == "clear"
    assert absent_section["gate_passed"] is True
    assert absent_section["mechanism_required"] is False


def _adapter_test_trinity_bundle():
    from polisyos.ir.governance.game_design import (
        BayesianTypeSpec,
        MechanismDesignSpec,
        MechanismGameRepresentation,
    )
    from polisyos.ir.governance.policy_spec import PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.trinity import TrinityBundle

    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="phase3_adapter_problem",
            domain=ProblemDomain.FISCAL,
        ),
        policy_spec=PolicySpec(
            policy_id="phase3_adapter_policy",
            mechanism_design=MechanismDesignSpec(
                design_id="phase3_adapter_design",
                representation=MechanismGameRepresentation.BAYESIAN,
                players=("agent",),
                action_spaces={"agent": ("low", "high")},
                bayesian_types=[
                    BayesianTypeSpec(
                        player_id="agent",
                        type_space=("low", "high"),
                        prior_probabilities={"low": 0.5, "high": 0.5},
                    )
                ],
            ),
        ),
        model_spec=ModelSpec(
            model_id="phase3_adapter_model",
            data_snapshot_ref="sha256:" + "1" * 64,
        ),
    )


def _adapter_test_candidate():
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

    return PolicyCandidateSchema.from_trinity_bundle(
        _adapter_test_trinity_bundle(),
        candidate_id="phase3_adapter_candidate",
    )


@pytest.mark.parametrize(
    "serialized_payload",
    [
        pytest.param(None, id="none-is-selected-invalid"),
        pytest.param("not-a-candidate-mapping", id="scalar-is-selected-invalid"),
        pytest.param({"schema_version": "invalid"}, id="malformed-mapping-is-selected-invalid"),
    ],
)
def test_selected_typed_candidate_serialization_cannot_launder_refusal_into_absence(
    tmp_path,
    serialized_payload: object,
) -> None:
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

    class CandidateWithSelectedSerialization(PolicyCandidateSchema):
        def model_dump(self, *args: object, **kwargs: object) -> object:
            return serialized_payload

    ctx = _ctx(tmp_path)
    state = ExperimentState(
        run_id="R_phase3_selected_candidate_serialization_refusal",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: _complete_welfare_ref(ctx)},
        params={},
    )
    state.params["policy_candidate_schema"] = CandidateWithSelectedSerialization.model_validate(
        _adapter_test_candidate().model_dump(mode="python")
    )

    gate = resolve_phase3_gate(ctx, state)

    assert gate.gate_passed is False
    assert (
        "phase3.selected_candidate_unreadable:phase3_selected_candidate_payload_invalid"
        in gate.blocking_reasons
    )
    assert "phase3.mechanism_certificate_missing" not in gate.blocking_reasons


@pytest.mark.parametrize("error_type", [TypeError, ValueError])
def test_expected_candidate_serializer_errors_are_typed_refusals(
    tmp_path,
    error_type: type[Exception],
) -> None:
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

    class CandidateWithExpectedSerializerError(PolicyCandidateSchema):
        def model_dump(self, *args: object, **kwargs: object) -> object:
            raise error_type("selected candidate serialization failed")

    ctx = _ctx(tmp_path)
    state = ExperimentState(
        run_id="R_phase3_expected_candidate_serializer_error",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: _complete_welfare_ref(ctx)},
        params={},
    )
    state.params["policy_candidate_schema"] = CandidateWithExpectedSerializerError.model_validate(
        _adapter_test_candidate().model_dump(mode="python")
    )

    gate = resolve_phase3_gate(ctx, state)

    assert gate.gate_passed is False
    assert (
        "phase3.selected_candidate_unreadable:phase3_selected_candidate_payload_invalid"
        in gate.blocking_reasons
    )


def test_unexpected_candidate_serializer_error_remains_visible(tmp_path) -> None:
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

    class CandidateWithUnexpectedSerializerError(PolicyCandidateSchema):
        def model_dump(self, *args: object, **kwargs: object) -> object:
            raise RuntimeError("unexpected candidate serializer failure")

    ctx = _ctx(tmp_path)
    state = ExperimentState(
        run_id="R_phase3_unexpected_candidate_serializer_error",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: _complete_welfare_ref(ctx)},
        params={},
    )
    state.params["policy_candidate_schema"] = CandidateWithUnexpectedSerializerError.model_validate(
        _adapter_test_candidate().model_dump(mode="python")
    )

    with pytest.raises(RuntimeError, match="unexpected candidate serializer failure"):
        resolve_phase3_gate(ctx, state)


@pytest.mark.parametrize("typed_input", [False, True], ids=["valid-mapping", "valid-typed-model"])
def test_selected_candidate_adapter_preserves_supported_mapping_and_typed_inputs(
    tmp_path,
    typed_input: bool,
) -> None:
    candidate = _adapter_test_candidate()
    selected_payload = candidate if typed_input else candidate.model_dump(mode="python")
    ctx = _ctx(tmp_path)
    state = ExperimentState(
        run_id="R_phase3_supported_candidate_adapter_input",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: _complete_welfare_ref(ctx)},
        params={},
    )
    state.params["policy_candidate_schema"] = selected_payload

    gate = resolve_phase3_gate(ctx, state)

    assert gate.mechanism_required is True
    assert "phase3.selected_candidate_unreadable:" not in " ".join(gate.blocking_reasons)
    assert "phase3.mechanism_certificate_missing" in gate.blocking_reasons


def test_absent_inline_schema_keeps_trinity_fallback(tmp_path) -> None:
    from polisyos.core.artifacts import CanonInfo, SchemaInfo
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.scientist.nodes.builtins.state_keys import INPUT_TRINITY_BUNDLE_REF

    ctx = _ctx(tmp_path)
    trinity = _adapter_test_trinity_bundle()
    canon_spec = CanonSpec(forbid_floats=False, exclude_none=False)
    trinity_ref = ctx.store.put_json(
        trinity.model_dump(mode="json"),
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
            ),
            canon=CanonInfo.from_spec(canon_spec),
        ),
        canon_spec=canon_spec,
        return_selected_profile=True,
    )
    state = ExperimentState(
        run_id="r_phase3_absent_inline_candidate_trinity_fallback",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: ArtifactRef.model_validate(
                trinity_ref.model_dump(mode="json")
            )
        },
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: _complete_welfare_ref(ctx)},
        params={},
    )

    gate = resolve_phase3_gate(ctx, state)

    assert gate.mechanism_required is True
    assert "phase3.selected_candidate_unreadable:" not in " ".join(gate.blocking_reasons)
    assert "phase3.mechanism_certificate_missing" in gate.blocking_reasons
