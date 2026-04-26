from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal import (
    build_dynamic_proof_bundle,
    build_forecast_intervention_proof_bundle,
)
from polisyos.ir.analytics.dynamic_causal_semantics import (
    DynamicReductionStatus,
    DynamicSemanticsAttachment,
    DynamicSemanticsFamily,
    ForecastAnnouncementWindow,
    ForecastCensoringChecks,
    ForecastContrastSpec,
    ForecastDownstreamChannel,
    ForecastExogeneityChecks,
    ForecastIdentificationMethod,
    ForecastIdentifiedComponent,
    ForecastInterventionAttachment,
    ForecastInterventionCertificate,
    ForecastInterventionQuery,
    ForecastSemanticsClass,
    ForecastSupportChecks,
    ForecastUpdateOperatorKind,
    GraphicalOracleKind,
    InterventionKind,
    InterventionScope,
    LocalIndependenceAttachment,
    WellPosednessStatus,
    WellPosednessWitness,
    build_forecast_intervention_attachment,
    forecast_intervention_proof_status,
    load_forecast_intervention_certificate,
    load_forecast_intervention_query,
    persist_forecast_intervention_certificate,
    persist_forecast_intervention_query,
)
from polisyos.ir.refs import ForecastInterventionCertificateRef, ForecastInterventionQueryRef

_REPLAY_FINGERPRINTS = {
    "announcement_timing_hash": "sha256:" + ("1" * 64),
    "disclosure_rule_hash": "sha256:" + ("2" * 64),
    "update_operator_hash": "sha256:" + ("3" * 64),
    "graph_projection_hash": "sha256:" + ("4" * 64),
    "decomposition_witness_hash": "sha256:" + ("5" * 64),
}


def _identified_forecast_attachment() -> ForecastInterventionAttachment:
    return ForecastInterventionAttachment(
        semantics_class=ForecastSemanticsClass.DELPHIC,
        identified_component=ForecastIdentifiedComponent.EXPECTATION_ONLY,
        announcement_node="A_tau",
        intervention_time="2026-04-25T10:00:00Z",
        expectation_process_ref="B_tau_plus",
        update_operator_kind=ForecastUpdateOperatorKind.BAYES,
        update_operator_ref="belief-update:bayes:v1",
        admissible_intervention=True,
        downstream_channels_allowed=(ForecastDownstreamChannel.EXPECTATIONS,),
        graphical_oracle=GraphicalOracleKind.DELTA,
        separation_claim_ref="sep:announcement_expectations",
        local_independence_claim_ref="li:announcement_window",
        causal_validity_rule="local_independence_reweighting_validity_v1",
        identification_method=ForecastIdentificationMethod.LOCAL_INDEPENDENCE_REWEIGHTING,
        exogeneity_checks=ForecastExogeneityChecks(
            preannouncement_orthogonalization_passed=True,
            simultaneous_action_excluded=True,
            anticipation_excluded=True,
        ),
        support_checks=ForecastSupportChecks(
            positivity_passed=True,
            overlap_notes=("message contrast observed in disclosure support",),
        ),
        censoring_checks=ForecastCensoringChecks(
            independent_censoring_checked=True,
            causal_censoring_validity_checked=True,
        ),
        well_posedness_ref="well-posed:forecast-post-law",
        required_observables=("A_tau", "B_tau_plus", "Y"),
        notes=("forecast publication is interpreted as public information law",),
        proof_support_fingerprints=_REPLAY_FINGERPRINTS,
    )


def _forecast_query() -> ForecastInterventionQuery:
    return ForecastInterventionQuery(
        message_var="A_tau",
        announcement_time="2026-04-25T10:00:00Z",
        semantics_class=ForecastSemanticsClass.DELPHIC,
        expectation_target="B_tau_plus",
        outcome_target="Y",
        contrast_spec=ForecastContrastSpec(
            message="published_soft_landing_forecast",
            baseline_message="baseline_projection",
        ),
        decomposition_goal=ForecastIdentifiedComponent.EXPECTATION_ONLY,
        update_operator_kind=ForecastUpdateOperatorKind.BAYES,
        decomposition_method=ForecastIdentificationMethod.LOCAL_INDEPENDENCE_REWEIGHTING,
        pre_announcement_window=ForecastAnnouncementWindow(
            start="2026-04-25T09:55:00Z",
            end="2026-04-25T10:00:00Z",
        ),
        post_announcement_window=ForecastAnnouncementWindow(
            start="2026-04-25T10:00:00Z",
            end="2026-04-25T10:05:00Z",
        ),
        positivity_claimed=True,
        censoring_assessed=True,
        required_observables=("A_tau", "B_tau_plus", "Y"),
    )


def test_forecast_publication_attachment_roundtrips_through_dynamic_proof_bundle() -> None:
    attachment = _identified_forecast_attachment()
    dynamic_semantics = DynamicSemanticsAttachment(
        semantics_family=DynamicSemanticsFamily.LOCAL_INDEPENDENCE_GRAPH,
        reduction_status=DynamicReductionStatus.VALIDATED_REDUCTION,
        intervention_scope=InterventionScope(
            kind=InterventionKind.FORECAST_PUBLICATION,
            targets=("A_tau",),
            admissible=True,
            admissibility_theorem="forecast_publication_expectation_update_v1",
        ),
        continuous_time_attachment=LocalIndependenceAttachment(
            graphical_oracle=GraphicalOracleKind.DELTA,
            causal_validity_rule="local_independence_reweighting_validity_v1",
            process_family="marked_point_process",
            policy_semantics="forecast_publication",
            identification_method="local_independence_reweighting",
            independent_censoring_checked=True,
            positivity_assumed=True,
        ),
        well_posedness_witness=WellPosednessWitness(
            status=WellPosednessStatus.PROVED,
            family="local_independence_graph",
            method="admissible_reweighting_post_law",
            confidence="theorem_backed",
        ),
        forecast_intervention=attachment,
    )

    bundle = build_dynamic_proof_bundle(
        dynamic_semantics=dynamic_semantics,
        theorem_family="forecast_local_independence_v1",
        proof_status=attachment.proof_status,
        proof_trace=["forecast-publication", "belief-update", "local-independence"],
    )

    assert forecast_intervention_proof_status(attachment) == "identified"
    assert attachment.replay_composability_status == "reusable"
    assert bundle.proof_status == "identified"
    assert bundle.proof_stratum == "A1_dynamic"
    assert bundle.implementation_coverage == (
        "declared-dynamic-scope:forecast_local_independence_v1"
    )
    assert bundle.dynamic_semantics is not None
    assert bundle.dynamic_semantics.forecast_intervention is not None
    assert (
        bundle.dynamic_semantics.forecast_intervention.intervention_kind
        == "forecast_publication"
    )
    assert DynamicSemanticsAttachment.model_validate(
        dynamic_semantics.model_dump(mode="json")
    ) == dynamic_semantics


def test_build_forecast_attachment_and_proof_bundle_from_query() -> None:
    query = _forecast_query()
    attachment = build_forecast_intervention_attachment(
        query=query,
        graphical_oracle=GraphicalOracleKind.DELTA,
        exogeneity_checks=ForecastExogeneityChecks(
            preannouncement_orthogonalization_passed=True,
            simultaneous_action_excluded=True,
            anticipation_excluded=True,
        ),
        support_checks=ForecastSupportChecks(positivity_passed=True),
        local_independence_claim_ref="li:forecast",
        causal_validity_rule="local_independence_reweighting_validity_v1",
        well_posedness_ref="well-posed:forecast-post-law",
        proof_support_fingerprints=_REPLAY_FINGERPRINTS,
    )

    bundle = build_forecast_intervention_proof_bundle(
        forecast_intervention=attachment,
        graph_ref="graph:forecast",
    )

    assert attachment.proof_status == "identified"
    assert attachment.blocking_reasons == ()
    assert bundle.proof_status == "identified"
    assert bundle.graph_ref == "graph:forecast"
    assert bundle.query_ref is None
    assert bundle.metadata["query_kind"] == "forecast_intervention"
    assert bundle.metadata["forecast_replay_composability_status"] == "reusable"


def test_forecast_query_and_certificate_persistence_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    query = _forecast_query()
    certificate = _identified_forecast_attachment()

    query_ref = persist_forecast_intervention_query(store, query)
    certificate_ref = persist_forecast_intervention_certificate(store, certificate)

    assert isinstance(query_ref, ForecastInterventionQueryRef)
    assert isinstance(certificate_ref, ForecastInterventionCertificateRef)
    assert load_forecast_intervention_query(store, query_ref) == query
    loaded_certificate = load_forecast_intervention_certificate(store, certificate_ref)
    assert isinstance(loaded_certificate, ForecastInterventionCertificate)
    assert loaded_certificate.announcement_node == certificate.announcement_node
    assert loaded_certificate.proof_status == "identified"


def test_hybrid_expectation_only_forecast_stays_at_frontier_boundary() -> None:
    attachment = _identified_forecast_attachment().model_copy(
        update={
            "semantics_class": ForecastSemanticsClass.HYBRID,
            "identification_method": ForecastIdentificationMethod.MIXED,
        }
    )
    dynamic_semantics = DynamicSemanticsAttachment(
        semantics_family=DynamicSemanticsFamily.LOCAL_INDEPENDENCE_GRAPH,
        reduction_status=DynamicReductionStatus.HEURISTIC_ONLY,
        forecast_intervention=attachment,
    )

    bundle = build_dynamic_proof_bundle(
        dynamic_semantics=dynamic_semantics,
        theorem_family="forecast_hybrid_unseparated",
        proof_status=attachment.proof_status,
    )

    assert attachment.proof_status == "oracle_needed"
    assert bundle.proof_status == "oracle_needed"
    assert bundle.implementation_coverage == (
        "dynamic-research-boundary:forecast_hybrid_unseparated"
    )


def test_failed_support_forecast_certificate_is_non_identified() -> None:
    attachment = _identified_forecast_attachment().model_copy(
        update={
            "support_checks": ForecastSupportChecks(
                positivity_passed=False,
                overlap_notes=("counterfactual message has no observed support",),
            ),
            "blocking_reasons": ("positivity_failed",),
        }
    )

    assert attachment.proof_status == "non_identified"


def test_identified_forecast_attachment_requires_local_independence_dynamic_semantics() -> None:
    attachment = _identified_forecast_attachment()

    with pytest.raises(ValueError, match="local_independence_graph"):
        DynamicSemanticsAttachment(
            semantics_family=DynamicSemanticsFamily.IOSCM,
            reduction_status=DynamicReductionStatus.VALIDATED_REDUCTION,
            forecast_intervention=attachment,
        )
