from __future__ import annotations

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.welfare import (
    ChannelDecompositionArtifact,
    ChannelDecompositionTargetKind,
    ChannelIdentificationStatus,
    ChannelPolicyClass,
    WelfareBundle,
    build_channel_decomposition_ref,
    load_channel_decomposition_artifact,
    load_welfare_bundle,
    persist_channel_decomposition_artifact,
    persist_welfare_bundle,
)
from polisyos.ir.artifacts import put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    ChannelDecompositionArtifactRef,
    GEUncertaintyBundleRef,
    WelfareBundleRef,
)


def _persist_payload(
    store: FileSystemCAS, payload: dict[str, object], *, kind: str
) -> ArtifactRefModel:
    ref = put_json_artifact(
        store,
        payload,
        kind=kind,
        schema_name=kind,
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ArtifactRefModel.model_validate(ref)


def _artifact_ref(suffix: str, *, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id="sha256:" + suffix * 64,
        kind=kind,
        media_type="application/json",
    )


def test_welfare_bundle_and_channel_artifact_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    channel = ChannelDecompositionArtifact(
        target_kind=ChannelDecompositionTargetKind.NET_REVENUE,
        policy_class=ChannelPolicyClass.LOCAL_AFFINE_TAX_TRANSFER,
        basis_labels=("delta_tax_rate", "delta_transfer"),
        step_vector=(0.02, 1.0),
        mechanical_vector=(1.0, 1.2, 1.4),
        behavioral_vector=(-0.2, -0.3, -0.4),
        fiscal_feedback_vector=(0.1, 0.1, 0.2),
        total_vector=(0.9, 1.0, 1.2),
        identification_status=ChannelIdentificationStatus.IDENTIFIED,
        baseline_microdata_ref=_artifact_ref("a", kind="ir.baseline_microdata"),
        policy_basis_ref=_artifact_ref("b", kind="ir.policy_basis"),
        mechanical_inputs_ref=_artifact_ref("c", kind="ir.mechanical_inputs"),
        behavior_model_ref=_artifact_ref("d", kind="ir.behavior_model"),
        fiscal_state_model_ref=_artifact_ref("e", kind="ir.fiscal_state_model"),
        instrument_set_ref=_artifact_ref("f", kind="ir.instrument_set"),
        first_stage_stats={"behavior_f": 18.0, "fiscal_f": 15.0},
        overid_stats={"hansen_pvalue": 0.31},
        overlap_stats={"min_propensity": 0.12},
        timing_assumptions=["policy -> behavior -> closure"],
        observability_notes=["baseline weights calibrated"],
        diagnostic_summary={"policy_rank_ok": True},
    )

    channel_ref = persist_channel_decomposition_artifact(store, channel)
    loaded_channel = load_channel_decomposition_artifact(store, channel_ref)

    assert isinstance(channel_ref, ChannelDecompositionArtifactRef)
    assert loaded_channel == channel

    bundle = WelfareBundle(
        welfare_measure="mvpf",
        welfare_ref=_artifact_ref("1", kind="ir.policy_welfare_result"),
        social_weight_ref=_artifact_ref("2", kind="ir.social_weight_manifest"),
        ge_uncertainty_ref=GEUncertaintyBundleRef(artifact_id="sha256:" + "3" * 64),
        channel_decomposition_ref=channel_ref,
        metadata={"track": "7.5"},
    )

    bundle_ref = persist_welfare_bundle(store, bundle)
    loaded_bundle = load_welfare_bundle(store, bundle_ref)

    assert isinstance(bundle_ref, WelfareBundleRef)
    assert loaded_bundle == bundle


def test_build_channel_decomposition_ref_identified_with_matrix_replay(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    baseline_ref = _persist_payload(
        store,
        {
            "overlap_ok": True,
            "overlap_stats": {"min_propensity": 0.11},
            "observability_notes": ["baseline microdata aligned"],
        },
        kind="ir.baseline_microdata",
    )
    policy_basis_ref = _persist_payload(
        store,
        {
            "basis_labels": ["delta_tax_rate", "delta_transfer"],
            "step_vector": [0.02, 1.0],
            "policy_class": "local_affine_tax_transfer",
            "policy_rank_ok": True,
            "timing_assumptions": ["policy -> behavior -> closure"],
        },
        kind="ir.policy_basis",
    )
    mechanical_ref = _persist_payload(
        store,
        {
            "mechanical_matrix": [
                [80.0, -1.0],
                [100.0, -1.0],
                [140.0, -1.0],
            ],
            "observability_notes": ["statutory replay on baseline"],
        },
        kind="ir.mechanical_inputs",
    )
    behavior_ref = _persist_payload(
        store,
        {
            "behavioral_vector": [-0.24, -0.36, -0.48],
            "first_stage_ok": True,
            "first_stage_stats": {"behavior_f": 18.0},
        },
        kind="ir.behavior_model",
    )
    fiscal_ref = _persist_payload(
        store,
        {
            "fiscal_feedback_vector": [0.10, 0.15, 0.20],
            "first_stage_ok": True,
            "first_stage_stats": {"fiscal_f": 14.0},
        },
        kind="ir.fiscal_state_model",
    )
    instrument_ref = _persist_payload(
        store,
        {
            "overid_ok": True,
            "overid_stats": {"hansen_pvalue": 0.27},
            "timing_ok": True,
        },
        kind="ir.instrument_set",
    )

    ref = build_channel_decomposition_ref(
        store,
        target_kind="net_revenue",
        baseline_microdata_ref=baseline_ref,
        policy_basis_ref=policy_basis_ref,
        mechanical_inputs_ref=mechanical_ref,
        behavior_model_ref=behavior_ref,
        fiscal_state_model_ref=fiscal_ref,
        instrument_set_ref=instrument_ref,
    )
    artifact = load_channel_decomposition_artifact(store, ref)

    assert artifact.identification_status is ChannelIdentificationStatus.IDENTIFIED
    assert artifact.mechanical_vector == pytest.approx((0.6, 1.0, 1.8))
    assert artifact.behavioral_vector == pytest.approx((-0.24, -0.36, -0.48))
    assert artifact.fiscal_feedback_vector == pytest.approx((0.10, 0.15, 0.20))
    assert artifact.total_vector == pytest.approx((0.46, 0.79, 1.52))
    assert artifact.first_stage_stats["behavior_f"] == pytest.approx(18.0)
    assert artifact.first_stage_stats["fiscal_f"] == pytest.approx(14.0)
    assert artifact.overid_stats["hansen_pvalue"] == pytest.approx(0.27)
    assert artifact.diagnostic_summary["policy_rank_ok"] is True


def test_build_channel_decomposition_ref_downgrades_without_fiscal_channel(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    baseline_ref = _persist_payload(store, {"overlap_ok": True}, kind="ir.baseline_microdata")
    policy_basis_ref = _persist_payload(
        store,
        {
            "basis_labels": ["delta_tax_rate", "delta_transfer"],
            "step_vector": [0.02, 1.0],
            "policy_rank_ok": True,
        },
        kind="ir.policy_basis",
    )
    mechanical_ref = _persist_payload(
        store,
        {"mechanical_vector": [0.6, 1.0, 1.8]},
        kind="ir.mechanical_inputs",
    )
    behavior_ref = _persist_payload(
        store,
        {
            "behavioral_vector": [-0.24, -0.36, -0.48],
            "first_stage_ok": True,
        },
        kind="ir.behavior_model",
    )
    instrument_ref = _persist_payload(store, {"overid_ok": True}, kind="ir.instrument_set")

    ref = build_channel_decomposition_ref(
        store,
        target_kind=ChannelDecompositionTargetKind.NET_REVENUE,
        baseline_microdata_ref=baseline_ref,
        policy_basis_ref=policy_basis_ref,
        mechanical_inputs_ref=mechanical_ref,
        behavior_model_ref=behavior_ref,
        instrument_set_ref=instrument_ref,
    )
    artifact = load_channel_decomposition_artifact(store, ref)

    assert artifact.identification_status is ChannelIdentificationStatus.BOUNDED
    assert artifact.behavioral_vector == pytest.approx((-0.24, -0.36, -0.48))
    assert artifact.fiscal_feedback_vector is None
    assert artifact.total_vector == pytest.approx((0.36, 0.64, 1.32))
    assert "fiscal_feedback_channel_unidentified" in artifact.blocking_reasons


def test_build_channel_decomposition_ref_blocks_on_rank_failure(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    baseline_ref = _persist_payload(store, {"overlap_ok": True}, kind="ir.baseline_microdata")
    policy_basis_ref = _persist_payload(
        store,
        {
            "basis_labels": ["delta_tax_rate", "delta_transfer"],
            "step_vector": [0.02, 1.0],
            "policy_rank_ok": False,
        },
        kind="ir.policy_basis",
    )
    mechanical_ref = _persist_payload(
        store,
        {"mechanical_vector": [0.6, 1.0, 1.8]},
        kind="ir.mechanical_inputs",
    )
    behavior_ref = _persist_payload(
        store,
        {
            "behavioral_vector": [-0.24, -0.36, -0.48],
            "first_stage_ok": True,
        },
        kind="ir.behavior_model",
    )

    ref = build_channel_decomposition_ref(
        store,
        target_kind="net_revenue",
        baseline_microdata_ref=baseline_ref,
        policy_basis_ref=policy_basis_ref,
        mechanical_inputs_ref=mechanical_ref,
        behavior_model_ref=behavior_ref,
    )
    artifact = load_channel_decomposition_artifact(store, ref)

    assert artifact.identification_status is ChannelIdentificationStatus.BLOCKED
    assert artifact.behavioral_vector is None
    assert artifact.fiscal_feedback_vector is None
    assert artifact.mechanical_vector == pytest.approx((0.6, 1.0, 1.8))
    assert "policy_rank_failed" in artifact.blocking_reasons
