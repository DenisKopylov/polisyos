from __future__ import annotations

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.rough_path_semantics import (
    PathLiftMethod,
    RoughPathGraphCriterion,
    RoughPathIdentificationStatus,
    RoughPathIdentificationStrategy,
    RoughPathInterventionCertificate,
    RoughPathInterventionType,
    RoughPathModelFamily,
    RoughPathTopology,
    TemporalPathSemanticsAttachment,
    TemporalPathSemanticsScope,
    load_rough_path_intervention_certificate,
    persist_rough_path_intervention_certificate,
)
from polisyos.ir.registry.refs import ArtifactRefModel, RoughPathInterventionCertificateRef
from pydantic import ValidationError


def _artifact_id(ch: str) -> str:
    return f"sha256:{ch * 64}"


def _artifact_ref(ch: str, *, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=_artifact_id(ch),
        kind=kind,
        media_type="application/json",
    )


def _rough_path_certificate_ref(ch: str = "4") -> RoughPathInterventionCertificateRef:
    return RoughPathInterventionCertificateRef(artifact_id=_artifact_id(ch))


def _certificate() -> RoughPathInterventionCertificate:
    return RoughPathInterventionCertificate(
        semantics_scope=TemporalPathSemanticsScope.REPRESENTED_PATH,
        model_family=RoughPathModelFamily.HYBRID_RDE,
        topology=RoughPathTopology.P_VARIATION,
        graph_criterion=RoughPathGraphCriterion.DELTA_SEP,
        observation_operator_ref=_artifact_ref("a", kind="test.observation_operator"),
        lift_operator_ref=_artifact_ref("b", kind="test.lift_operator"),
        interpolation_is_adapted=True,
        future_leakage_ruled_out=True,
        intervention_type=RoughPathInterventionType.POLICY_OVERRIDE,
        intervention_operator_ref=_artifact_ref("c", kind="test.intervention_operator"),
        actuatable_component="A",
        filtration_ref=_artifact_ref("d", kind="test.filtration"),
        well_posedness_ref=_artifact_ref("e", kind="test.well_posedness"),
        identification_strategy=RoughPathIdentificationStrategy.CONTINUOUS_TIME_G_FORMULA,
        positivity_ref=_artifact_ref("f", kind="test.positivity"),
        sampling_ignorability_ref=_artifact_ref("1", kind="test.sampling_ignorability"),
        target_functional_ref=_artifact_ref("2", kind="test.target_functional"),
        proof_trace_ref=_artifact_ref("3", kind="test.proof_trace"),
        status=RoughPathIdentificationStatus.IDENTIFIED_REPRESENTATION_ONLY,
        scope_notes=("representation-level only",),
    )


def test_attachment_requires_lift_faithfulness_for_latent_scope() -> None:
    with pytest.raises(ValidationError, match="lift_faithfulness_checked=true"):
        TemporalPathSemanticsAttachment(
            semantics_scope=TemporalPathSemanticsScope.LATENT_PATH,
            lift_method=PathLiftMethod.PIECEWISE_LINEAR,
            topology=RoughPathTopology.P_VARIATION,
            p_variation_order=2.0,
            interpolation_is_adapted=True,
            future_leakage_ruled_out=True,
            intervention_type=RoughPathInterventionType.RESET_AT_STOPPING_TIME,
            graph_criterion=RoughPathGraphCriterion.SIGMA_SEP,
            proof_artifact_ref=_rough_path_certificate_ref(),
            sampling_ignorability_checked=True,
            lift_faithfulness_checked=False,
        )


def test_certificate_round_trips_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    certificate = _certificate()

    ref = persist_rough_path_intervention_certificate(store, certificate)

    assert isinstance(ref, RoughPathInterventionCertificateRef)
    assert load_rough_path_intervention_certificate(store, ref) == certificate


def test_bounds_only_certificate_cannot_claim_fully_identified() -> None:
    with pytest.raises(
        ValidationError, match="bounds_only certificates cannot claim fully identified"
    ):
        RoughPathInterventionCertificate(
            **(
                _certificate().model_dump(mode="python")
                | {
                    "identification_strategy": RoughPathIdentificationStrategy.BOUNDS_ONLY,
                    "status": RoughPathIdentificationStatus.IDENTIFIED,
                }
            )
        )
