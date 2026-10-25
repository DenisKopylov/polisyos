from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.catalog.microsim.protocols import MicrosimResult
from polisyos.ir.analytics.decision_layer import (
    SocialWeightManifestArtifact,
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
    WelfareMethod,
    WelfareStatus,
    build_channel_decomposition_ref,
    load_channel_decomposition_artifact,
    load_welfare_bundle,
    persist_channel_decomposition_artifact,
    persist_ge_uncertainty_bundle,
    persist_welfare_bundle,
)
from polisyos.ir.artifacts import put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    ChannelDecompositionArtifactRef,
    WelfareBundleRef,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_WELFARE_BUNDLE_REF
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.phase3 import (
    phase3_gate_reference_blockers,
    resolve_phase3_gate,
)

_OWNER_BLOCK = "upstream_input_owner_not_established"
_PHASE3_OWNER_BLOCK = "phase3.welfare_channel_input_owner_not_established"


def _ctx(tmp_path: Path) -> ExecutionContext:
    store = FileSystemCAS(tmp_path / "cas")
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_welfare_owner")
    return ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.welfare.owner"),
    )


def _persist_payload(
    ctx: ExecutionContext,
    payload: dict[str, object],
    *,
    kind: str,
    schema_name: str | None = None,
    schema_version: str = "1.0",
) -> ArtifactRefModel:
    ref = put_json_artifact(
        _ensure_ir_artifact_store(ctx.store),
        payload,
        kind=kind,
        schema_name=schema_name or kind,
        schema_version=schema_version,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ArtifactRefModel.model_validate(ref)


def _dummy_ref(char: str, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id="sha256:" + char * 64,
        kind=kind,
        media_type="application/json",
    )


def _identified_channel_ref(ctx: ExecutionContext) -> ChannelDecompositionArtifactRef:
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
            baseline_microdata_ref=_dummy_ref("1", "ir.baseline_microdata"),
            policy_basis_ref=_dummy_ref("2", "ir.policy_basis"),
            mechanical_inputs_ref=_dummy_ref("3", "ir.mechanical_inputs"),
            behavior_model_ref=_dummy_ref("4", "ir.behavior_model"),
            fiscal_state_model_ref=_dummy_ref("5", "ir.fiscal_state_model"),
            instrument_set_ref=_dummy_ref("6", "ir.instrument_set"),
        ),
    )


def _welfare_ref(
    ctx: ExecutionContext,
    channel_ref: ChannelDecompositionArtifactRef | None = None,
) -> WelfareBundleRef:
    matrix_ref = ctx.store.put_json(
        {"matrix": [[1]]},
        PutOptions(kind="ir.welfare_multiplier_matrix", media_type="application/json"),
    )
    social_weight_ref = persist_social_weight_manifest(
        _ensure_ir_artifact_store(ctx.store),
        SocialWeightManifestArtifact(
            manifest_ref="swr://welfare-owner/test@1.0.0#weights",
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
            channel_decomposition_ref=channel_ref,
            point_estimate=1.0,
            credible_interval=(0.9, 1.1),
            robust_interval=(0.8, 1.2),
            method_used=WelfareMethod.DETERMINISTIC,
            status=WelfareStatus.OK,
        ),
    )


def _identified_builder_output(ctx: ExecutionContext) -> ChannelDecompositionArtifactRef:
    baseline = _persist_payload(
        ctx,
        {
            "overlap_ok": True,
            "overlap_stats": {"min_propensity": 0.2},
        },
        kind="ir.baseline_microdata",
        schema_name="ir.baseline_microdata.unregistered",
        schema_version="9.9",
    )
    policy_basis = _persist_payload(
        ctx,
        {
            "basis_labels": ["delta_tax_rate"],
            "step_vector": [0.02],
            "policy_class": "local_affine_tax_transfer",
            "policy_rank_ok": True,
            "timing_ok": True,
        },
        kind="ir.policy_basis",
        schema_name="ir.policy_basis.unregistered",
        schema_version="9.9",
    )
    mechanical = _persist_payload(
        ctx,
        {"mechanical_vector": [0.6]},
        kind="ir.mechanical_inputs",
        schema_name="ir.mechanical_inputs.unregistered",
        schema_version="9.9",
    )
    behavior = _persist_payload(
        ctx,
        {
            "behavioral_vector": [-0.2],
            "first_stage_ok": True,
            "first_stage_stats": {"behavior_f": 18.0},
        },
        kind="ir.behavior_model",
        schema_name="ir.behavior_model.unregistered",
        schema_version="9.9",
    )
    fiscal = _persist_payload(
        ctx,
        {
            "fiscal_feedback_vector": [0.1],
            "first_stage_ok": True,
            "first_stage_stats": {"fiscal_f": 15.0},
        },
        kind="ir.fiscal_state_model",
        schema_name="ir.fiscal_state_model.unregistered",
        schema_version="9.9",
    )
    instruments = _persist_payload(
        ctx,
        {
            "overid_ok": True,
            "overid_stats": {"hansen_pvalue": 0.3},
            "timing_ok": True,
        },
        kind="ir.instrument_set",
        schema_name="ir.instrument_set.unregistered",
        schema_version="9.9",
    )
    return build_channel_decomposition_ref(
        _ensure_ir_artifact_store(ctx.store),
        target_kind="social_welfare",
        baseline_microdata_ref=baseline,
        policy_basis_ref=policy_basis,
        mechanical_inputs_ref=mechanical,
        behavior_model_ref=behavior,
        fiscal_state_model_ref=fiscal,
        instrument_set_ref=instruments,
        total_vector=(0.5,),
    )


def test_builder_keeps_math_candidate_but_blocks_unowned_role_inputs(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    ref = _identified_builder_output(ctx)
    artifact = load_channel_decomposition_artifact(_ensure_ir_artifact_store(ctx.store), ref)

    assert artifact.identification_status is ChannelIdentificationStatus.BLOCKED
    assert _OWNER_BLOCK in artifact.blocking_reasons
    assert artifact.diagnostic_summary["candidate_identification_status"] == "identified"
    assert artifact.diagnostic_summary["input_owner_status"] == "not_established"
    assert artifact.mechanical_vector == pytest.approx((0.6,))
    assert artifact.behavioral_vector == pytest.approx((-0.2,))
    assert artifact.fiscal_feedback_vector == pytest.approx((0.1,))
    assert artifact.total_vector == pytest.approx((0.5,))


def test_phase3_and_final_reference_replay_refuse_identified_vectors_without_role_owners(
    tmp_path: Path,
) -> None:
    ctx = _ctx(tmp_path)
    channel_ref = _identified_channel_ref(ctx)
    welfare_ref = _welfare_ref(ctx, channel_ref)
    state = ExperimentState(
        run_id="R_welfare_owner",
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

    assert gate.gate_passed is False
    assert _PHASE3_OWNER_BLOCK in gate.blocking_reasons
    assert gate.fiscal_feedback_required is False
    assert gate.fiscal_feedback_ref is None


def test_phase3_reference_replay_refuses_forged_passed_channel_ref(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    channel_ref = _identified_channel_ref(ctx)
    welfare_ref = _welfare_ref(ctx, channel_ref)
    state = ExperimentState(
        run_id="R_welfare_owner",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: welfare_ref},
    )
    gate = resolve_phase3_gate(ctx, state)
    forged_pass = gate.model_copy(update={"gate_passed": True, "blocking_reasons": []})

    assert forged_pass.gate_passed is True
    replay_blockers = phase3_gate_reference_blockers(ctx.store, forged_pass)

    assert _PHASE3_OWNER_BLOCK in replay_blockers


def test_decision_packet_refuses_unowned_identified_channel_values(tmp_path: Path) -> None:
    from polisyos.scientist.nodes.builtins.decide.decision_packet.outcome_sections import (
        _build_welfare_section,
    )

    ctx = _ctx(tmp_path)
    channel_ref = _identified_channel_ref(ctx)
    welfare_ref = _welfare_ref(ctx, channel_ref)
    packet_payload: dict[str, object] = {}
    section = _build_welfare_section(
        ctx,
        {ARTIFACT_WELFARE_BUNDLE_REF: welfare_ref},
        packet_payload=packet_payload,
    )

    assert section is not None
    candidate = section["channel_decomposition_artifact"]
    assert candidate["identification_status"] == "blocked"
    assert candidate["blocking_reasons"] == [_OWNER_BLOCK]
    assert candidate["authority_status"] == "not_established"
    assert "mechanical_vector" not in candidate
    assert "behavioral_vector" not in candidate
    assert "fiscal_feedback_vector" not in candidate
    assert "total_vector" not in candidate


def test_welfare_bundle_current_and_rollback_tuples_are_exact(tmp_path: Path) -> None:
    from polisyos.ir.analytics.welfare import (
        _WELFARE_BUNDLE_OWNER,
        WelfareBundle,
        persist_welfare_bundle,
    )
    from polisyos.ir.migrations.base import (
        IRRepresentationKey,
        find_writable_representation,
        get_current_ir_representation,
        get_default_write_representation,
        get_ir_owner_registry_snapshot,
    )

    snapshot = get_ir_owner_registry_snapshot()
    current = get_current_ir_representation(
        snapshot,
        _WELFARE_BUNDLE_OWNER.registry_key,
        owner_ref=_WELFARE_BUNDLE_OWNER.contract_id,
        schema_name="ir.welfare_bundle",
    )
    default = get_default_write_representation(
        snapshot,
        _WELFARE_BUNDLE_OWNER.registry_key,
        owner_ref=_WELFARE_BUNDLE_OWNER.contract_id,
    )
    legacy = find_writable_representation(
        snapshot,
        _WELFARE_BUNDLE_OWNER.registry_key,
        owner_ref=_WELFARE_BUNDLE_OWNER.contract_id,
        schema_name="ir.welfare_bundle",
        schema_version="1.0",
        payload_version="1.0",
    )
    assert current is not None
    assert current.schema_version == "1.1"
    assert default == current
    assert default is not None
    assert default.default_write
    assert current.current
    assert current.writable
    assert current.readable_from == (IRRepresentationKey("ir.welfare_bundle", "1.0", "1.0"),)
    assert legacy is not None
    assert legacy.readable
    assert legacy.writable
    assert not legacy.current
    assert not legacy.default_write

    ctx = _ctx(tmp_path)
    legacy_bundle = WelfareBundle(
        welfare_measure="net_social_welfare",
        point_estimate=1.0,
    )
    assert legacy_bundle.schema_version == "1.0"
    legacy_ref = persist_welfare_bundle(_ensure_ir_artifact_store(ctx.store), legacy_bundle)
    legacy_manifest = ctx.store.get_manifest(legacy_ref)
    legacy_payload = from_canonical_bytes(ctx.store.get_bytes(legacy_ref.artifact_id))
    assert legacy_manifest.artifact_schema.name == "ir.welfare_bundle"
    assert legacy_manifest.artifact_schema.version == "1.0"
    assert legacy_payload["schema_version"] == "1.0"

    rollback_bundle = WelfareBundle(
        schema_version="1.0",
        welfare_measure="net_social_welfare",
        point_estimate=0.75,
    )
    rollback_ref = persist_welfare_bundle(
        _ensure_ir_artifact_store(ctx.store),
        rollback_bundle,
        schema_version="1.0",
    )
    rollback_manifest = ctx.store.get_manifest(rollback_ref)
    rollback_payload = from_canonical_bytes(ctx.store.get_bytes(rollback_ref.artifact_id))
    assert rollback_manifest.artifact_schema.version == "1.0"
    assert rollback_payload["schema_version"] == "1.0"

    new_bundle = WelfareBundle(
        schema_version="1.1",
        welfare_measure="net_social_welfare",
        point_estimate=0.5,
        nominal_component_labels=("income",),
        nominal_welfare_pe_components=(0.4,),
        nominal_welfare_total_components=(0.5,),
    )
    new_ref = persist_welfare_bundle(_ensure_ir_artifact_store(ctx.store), new_bundle)
    fresh_store = FileSystemCAS(tmp_path / "cas")
    new_manifest = fresh_store.get_manifest(new_ref)
    new_payload = from_canonical_bytes(fresh_store.get_bytes(new_ref.artifact_id))
    assert new_manifest.artifact_schema.name == "ir.welfare_bundle"
    assert new_manifest.artifact_schema.version == "1.1"
    assert new_payload["schema_version"] == "1.1"
    fresh_reader = _ensure_ir_artifact_store(fresh_store)
    assert load_welfare_bundle(fresh_reader, new_ref) == new_bundle
    assert load_welfare_bundle(fresh_reader, legacy_ref) == legacy_bundle
    assert load_welfare_bundle(fresh_reader, rollback_ref) == rollback_bundle

    historical_payload = legacy_bundle.model_dump(mode="json")
    for field in (
        "nominal_component_labels",
        "nominal_welfare_pe_components",
        "nominal_welfare_total_components",
    ):
        historical_payload.pop(field)
    historical_ref_payload = put_json_artifact(
        _ensure_ir_artifact_store(ctx.store),
        historical_payload,
        kind="ir.welfare_bundle",
        schema_name="ir.welfare_bundle",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False),
    )
    historical_ref = WelfareBundleRef.model_validate(historical_ref_payload)
    typed_history = load_welfare_bundle(_ensure_ir_artifact_store(fresh_store), historical_ref)
    assert typed_history.schema_version == "1.0"
    assert typed_history.nominal_component_labels == ()
    assert typed_history.nominal_welfare_pe_components == ()
    assert typed_history.nominal_welfare_total_components == ()


@pytest.mark.parametrize(
    ("manifest_version", "payload_version", "expected_error"),
    [
        ("1.2", "1.2", "ir_owned_artifact_representation_unregistered"),
        ("1.1", "1.0", "ir_owned_artifact_representation_unreadable"),
        ("1.1", "unknown", "ir_owned_artifact_representation_unreadable"),
    ],
)
def test_welfare_bundle_reader_rejects_unknown_and_mismatched_tuples(
    tmp_path: Path,
    manifest_version: str,
    payload_version: str,
    expected_error: str,
) -> None:
    ctx = _ctx(tmp_path)
    payload = WelfareBundle(
        schema_version="1.0",
        welfare_measure="net_social_welfare",
        point_estimate=1.0,
    ).model_dump(mode="json")
    payload["schema_version"] = payload_version
    raw_ref = put_json_artifact(
        _ensure_ir_artifact_store(ctx.store),
        payload,
        kind="ir.welfare_bundle",
        schema_name="ir.welfare_bundle",
        schema_version=manifest_version,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    typed_ref = WelfareBundleRef.model_validate(raw_ref)
    with pytest.raises(ValueError, match=expected_error):
        load_welfare_bundle(_ensure_ir_artifact_store(ctx.store), typed_ref)


@pytest.mark.parametrize(
    ("schema_version", "expected_error"),
    [
        (None, "ir_owned_artifact_write_override_invalid"),
        ("", "ir_owned_artifact_write_override_invalid"),
        ("malformed", "ir_owned_artifact_write_override_unregistered"),
        ("1.0", "ir_owned_artifact_write_override_unregistered"),
    ],
)
def test_welfare_bundle_writer_rejects_invalid_or_mismatched_override_before_cas(
    tmp_path: Path,
    schema_version: object,
    expected_error: str,
) -> None:
    from polisyos.ir.analytics.welfare import WelfareBundle, persist_welfare_bundle

    ctx = _ctx(tmp_path)
    bundle = WelfareBundle(
        schema_version="1.1",
        welfare_measure="net_social_welfare",
        point_estimate=1.0,
    )
    before = tuple(sorted(str(ref) for ref in ctx.store.iter_artifact_ids()))
    with pytest.raises(ValueError, match=expected_error):
        persist_welfare_bundle(
            _ensure_ir_artifact_store(ctx.store),
            bundle,
            schema_version=cast("str", schema_version),
        )
    assert tuple(sorted(str(ref) for ref in ctx.store.iter_artifact_ids())) == before
