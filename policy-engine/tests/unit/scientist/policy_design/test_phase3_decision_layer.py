from __future__ import annotations

import logging

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
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
from polisyos.ir.refs import ArtifactRefModel
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_WELFARE_BUNDLE_REF
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
        ctx.store,
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
        ctx.store,
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
        ctx.store,
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
        ctx.store,
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
        ctx.store,
        build_optimization_ambiguity_certificate(
            {"mode": "wasserstein", "radius": 0.05, "overall_status": "pass"},
            mode="wasserstein",
            source_kind="dro_payload",
            overall_status="pass",
        ),
    )
    loaded_ambiguity = load_optimization_ambiguity_certificate(ctx.store, ambiguity_ref)
    assert loaded_ambiguity.mode == "wasserstein"
    assert loaded_ambiguity.certificate_payload["radius"] == 0.05

    social_weight_ref = persist_social_weight_manifest(
        ctx.store,
        SocialWeightManifestArtifact(
            manifest_ref="swr://phase3/round-trip@1.0.0#weights",
            method_fqn="policy.welfare.state_dependent_inverse_social_weights@1.0.0",
            normalization="mean_one",
            income_grid=(0.0, 0.5, 1.0),
            weights_on_grid=(1.5, 1.0, 0.5),
            state_keys=("income", "region"),
        ),
    )
    loaded_social_weight = load_social_weight_manifest(ctx.store, social_weight_ref)
    assert loaded_social_weight.state_keys == ("income", "region")
    assert loaded_social_weight.weights_on_grid == (1.5, 1.0, 0.5)

    microsim_result_ref = ArtifactRefModel(
        artifact_id="sha256:" + "1" * 64,
        kind="foundry.microsim.result",
        media_type="application/json",
    )
    feedback_ref = persist_fiscal_feedback_link(
        ctx.store,
        FiscalFeedbackLink(
            microsim_result_ref=microsim_result_ref,
            ambiguity_certificate_ref=ambiguity_ref,
            metadata={"source": "unit_test"},
        ),
    )
    loaded_feedback = load_fiscal_feedback_link(ctx.store, feedback_ref)
    assert loaded_feedback.microsim_result_ref == microsim_result_ref
    assert loaded_feedback.ambiguity_certificate_ref == ambiguity_ref


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
    ambiguity = load_optimization_ambiguity_certificate(ctx.store, gate.ambiguity_certificate_ref)
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
    ambiguity = load_optimization_ambiguity_certificate(ctx.store, gate.ambiguity_certificate_ref)
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


def test_phase3_gate_blocks_missing_social_weight_even_when_welfare_loads(tmp_path) -> None:
    ctx = _ctx(tmp_path)
    welfare_ref = persist_welfare_bundle(
        ctx.store,
        WelfareBundle(
            welfare_measure="net_social_welfare",
            model_class="linearized_ge_io",
            ge_multiplier_semantics="leontief_inverse",
            point_estimate=1.0,
            method_used=WelfareMethod.DETERMINISTIC,
            status=WelfareStatus.OK,
            ge_uncertainty_ref=persist_ge_uncertainty_bundle(
                ctx.store,
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
    welfare = load_welfare_bundle(ctx.store, welfare_ref).model_copy(
        update={"channel_decomposition_ref": _identified_behavioral_channel_ref(ctx)}
    )
    welfare_ref = persist_welfare_bundle(ctx.store, welfare)
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

    assert gate.fiscal_feedback_required is True
    assert gate.gate_passed is True
    assert gate.fiscal_feedback_ref is not None
    feedback = load_fiscal_feedback_link(ctx.store, gate.fiscal_feedback_ref)
    assert feedback.channel_decomposition_ref is not None
    assert (
        MicrosimResult.model_validate(state.params["microsim_result"]).fiscal_feedback_ref
        == gate.fiscal_feedback_ref
    )


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
        ctx.store,
        build_optimization_ambiguity_certificate(
            {"mode": "not_applicable"},
            mode="not_applicable",
            source_kind="test",
            overall_status="pass",
        ),
    )
    feedback_ref = persist_fiscal_feedback_link(
        ctx.store,
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
