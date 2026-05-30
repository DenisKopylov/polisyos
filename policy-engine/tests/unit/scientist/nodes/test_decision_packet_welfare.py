from __future__ import annotations

import logging

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.phase4_dynamics import EquilibriumMultiplicityWelfareAnnotation
from polisyos.ir.analytics.welfare import (
    ChannelDecompositionArtifact,
    ChannelDecompositionTargetKind,
    ChannelIdentificationStatus,
    ChannelPolicyClass,
    WelfareBundle,
    WelfareIntervalSemantics,
    WelfareMethod,
    WelfareStatus,
    persist_channel_decomposition_artifact,
    persist_welfare_bundle,
)
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.decide.build_decision_packet import BuildDecisionPacketNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_WELFARE_BUNDLE_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)


def test_decision_packet_includes_welfare_section(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_welfare")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet.welfare"))

    trinity_ref = store.put_json(
        {"trinity": {}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        {
            "data_ref": {
                "artifact_id": str(snapshot_ref.artifact_id),
                "kind": "foundry.state_snapshot",
                "media_type": "application/json",
            }
        },
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    channel_ref = persist_channel_decomposition_artifact(
        store,
        ChannelDecompositionArtifact(
            target_kind=ChannelDecompositionTargetKind.SOCIAL_WELFARE,
            policy_class=ChannelPolicyClass.LOCAL_AFFINE_TAX_TRANSFER,
            basis_labels=("delta_tax_rate", "delta_transfer"),
            step_vector=(0.02, 1.0),
            mechanical_vector=(0.6,),
            behavioral_vector=(-0.24,),
            fiscal_feedback_vector=(0.16,),
            total_vector=(0.52,),
            identification_status=ChannelIdentificationStatus.IDENTIFIED,
            baseline_microdata_ref=ArtifactRefModel(
                artifact_id="sha256:" + "1" * 64,
                kind="ir.baseline_microdata",
                media_type="application/json",
            ),
            policy_basis_ref=ArtifactRefModel(
                artifact_id="sha256:" + "2" * 64,
                kind="ir.policy_basis",
                media_type="application/json",
            ),
            mechanical_inputs_ref=ArtifactRefModel(
                artifact_id="sha256:" + "3" * 64,
                kind="ir.mechanical_inputs",
                media_type="application/json",
            ),
        ),
    )
    welfare_ref = persist_welfare_bundle(
        store,
        WelfareBundle(
            welfare_measure="net_social_welfare",
            model_class="linearized_ge_io",
            ge_multiplier_semantics="leontief_inverse",
            point_estimate=0.84,
            credible_interval=(0.51, 1.12),
            robust_interval=(0.12, 1.43),
            interval_semantics=WelfareIntervalSemantics.MIXED_NESTED,
            channel_decomposition_ref=channel_ref,
            channel_decomposition={"pe": 0.57, "ge": 0.27},
            equilibrium_multiplicity=EquilibriumMultiplicityWelfareAnnotation(
                status="multiple",
                report_ref=ArtifactRefModel(
                    artifact_id="sha256:" + "4" * 64,
                    kind="ir.equilibrium_multiplicity_report",
                    media_type="application/json",
                ),
                selection_dependence=True,
                materiality_note="selection dependent welfare ranking",
            ),
            method_used=WelfareMethod.MIXED_NESTED,
            warnings=["dependence_assumed_independent"],
            status=WelfareStatus.DEGRADED,
        ),
    )

    state = ExperimentState(
        run_id="R_packet_welfare",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: welfare_ref},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["artifacts"]["welfare_bundle_ref"] == str(welfare_ref.artifact_id)
    assert payload["welfare"]["bundle_ref"] == str(welfare_ref.artifact_id)
    assert payload["welfare"]["point_estimate"] == 0.84
    assert payload["welfare"]["robust_interval"] == [0.12, 1.43]
    assert payload["welfare"]["status"] == "degraded"
    assert payload["welfare"]["equilibrium_multiplicity"]["status"] == "multiple"
    assert payload["welfare"]["equilibrium_multiplicity"]["selection_dependence"] is True
    assert (
        payload["welfare"]["equilibrium_multiplicity"]["materiality_note"]
        == "selection dependent welfare ranking"
    )
    assert payload["welfare"]["channel_decomposition_ref"] == str(channel_ref.artifact_id)
    assert (
        payload["welfare"]["channel_decomposition_artifact"]["identification_status"]
        == "identified"
    )
    assert payload["welfare"]["channel_decomposition_artifact"]["mechanical_vector"] == [0.6]
    assert payload["phase3"]["refusal_status"] == "blocked"
    assert payload["phase3"]["gate_passed"] is False
    assert "phase3.welfare_not_ok" in payload["phase3"]["blocking_reasons"]
    assert "phase3.ge_uncertainty_missing" in payload["phase3"]["blocking_reasons"]
    assert "phase3.social_weight_missing" in payload["phase3"]["blocking_reasons"]
    assert payload["phase3"]["ambiguity_certificate_ref"] is not None
