from __future__ import annotations

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.alignment_certification import (
    AlignmentOverallStatus,
    AlignmentReport,
    AlignmentReviewStatus,
    AlignmentVerificationConfig,
    AlignmentReviewerState,
    AlignmentType,
    MetadataCheckStatus,
    MeasurementComparabilityGrade,
    VariableAlignmentCertificate,
    build_alignment_report,
    load_alignment_report,
    load_variable_alignment_certificate,
    persist_alignment_report,
    persist_variable_alignment_certificate,
    verify_fragment_alignment,
    verify_fragment_bundle_alignment,
)
from polisyos.ir.analytics.cross_graph import (
    CompositionCertificate,
    InterfaceRole,
    load_composition_certificate,
    load_interface_mapping,
    SCMFragment,
    persist_composition_certificate,
    persist_interface_mapping,
    load_scm_fragment,
    persist_scm_fragment,
)
from polisyos.ir.refs import (
    AlignmentReportRef,
    CompositionCertificateRef,
    InterfaceMappingRef,
    SCMFragmentRef,
    VariableAlignmentCertificateRef,
)


def _fragment() -> SCMFragment:
    return SCMFragment(
        fragment_id="labor",
        graph_ref="artifact:graph:labor",
        semantic_namespace="policy.labor",
        interface_variables=["years_of_education", "employment_rate", "household_income"],
        exposed_inputs=["years_of_education"],
        exposed_outputs=["employment_rate", "household_income"],
        latent_summary={"household_income": "observed via a latent bridge in a later phase"},
        measurement_models={"employment_rate": "artifact:mm:employment"},
        variable_definitions={
            "years_of_education": "Completed years of formal education",
            "employment_rate": "Share of employed working-age population",
            "household_income": "Monthly disposable household income",
        },
        variable_units={"employment_rate": "percent", "household_income": "usd_per_month"},
        variable_metadata={
            "employment_rate": {
                "population": "working_age_adults",
                "time_window": {"start": "2024-01-01", "end": "2024-12-31"},
            }
        },
    )


def _certificate(
    *,
    alignment_type: AlignmentType = AlignmentType.EXACT,
    reviewer: AlignmentReviewerState = AlignmentReviewerState.AUTOMATED,
    assumptions: list[str] | None = None,
) -> VariableAlignmentCertificate:
    return VariableAlignmentCertificate(
        variable_a="years_of_education",
        fragment_a_id="education",
        variable_b="years_of_education",
        fragment_b_id="labor",
        alignment_type=alignment_type,
        measurement_model_a_ref="artifact:mm:education",
        measurement_model_b_ref="artifact:mm:labor",
        transform_ref="artifact:transform:edu" if alignment_type is AlignmentType.SCALE_LINKED else None,
        proxy_evidence_ref="artifact:proxy:evidence" if alignment_type is AlignmentType.PROXY else None,
        latent_bridge_ref=(
            "artifact:latent:bridge" if alignment_type is AlignmentType.LATENT_BRIDGE else None
        ),
        assumptions_introduced=list(assumptions or []),
        reviewer=reviewer,
        metadata={"source": "test"},
    )


def test_scm_fragment_validates_interface_subsets() -> None:
    fragment = _fragment()

    assert fragment.exposed_inputs == ["years_of_education"]
    assert fragment.exposed_outputs == ["employment_rate", "household_income"]

    with pytest.raises(ValueError, match="exposed_inputs must be a subset"):
        SCMFragment(
            fragment_id="bad",
            graph_ref="artifact:graph:bad",
            semantic_namespace="policy.bad",
            interface_variables=["x"],
            exposed_inputs=["missing"],
        )


def test_to_interface_schema_derives_roles_and_observed_flags() -> None:
    schema = _fragment().to_interface_schema()
    by_name = {item.variable_name: item for item in schema.variables}

    assert schema.fragment_id == "labor"
    assert by_name["years_of_education"].role is InterfaceRole.INPUT
    assert by_name["employment_rate"].role is InterfaceRole.OUTPUT
    assert by_name["household_income"].role is InterfaceRole.OUTPUT
    assert by_name["employment_rate"].observed is True
    assert by_name["household_income"].observed is False
    assert by_name["employment_rate"].measurement_model_ref == "artifact:mm:employment"
    assert by_name["employment_rate"].metadata == {
        "population": "working_age_adults",
        "time_window": {"start": "2024-01-01", "end": "2024-12-31"},
    }


def test_variable_alignment_certificate_serializes_enum_fields() -> None:
    certificate = VariableAlignmentCertificate(
        variable_a="employment",
        fragment_a_id="labor",
        variable_b="economic_activity",
        fragment_b_id="health",
        alignment_type=AlignmentType.PROXY,
        measurement_model_a_ref="artifact:mm:labor",
        measurement_model_b_ref="artifact:mm:health",
        transform_ref="artifact:transform:proxy",
        proxy_evidence_ref="artifact:proxy:evidence",
        latent_bridge_ref=None,
        assumptions_introduced=["proxy stability"],
        reviewer=AlignmentReviewerState.PENDING_REVIEW,
        metadata={"namespace": "policy"},
    )

    payload = certificate.model_dump(mode="json")

    assert payload["alignment_type"] == "proxy"
    assert payload["reviewer"] == "pending_review"
    assert payload["measurement_model_a_ref"] == "artifact:mm:labor"


def test_build_alignment_report_marks_exact_and_scale_linked_as_aligned() -> None:
    report = build_alignment_report(
        fragment_ids=["education", "labor"],
        certificates=[
            _certificate(alignment_type=AlignmentType.EXACT),
            _certificate(alignment_type=AlignmentType.SCALE_LINKED),
        ],
    )

    assert report.overall_status is AlignmentOverallStatus.ALIGNED
    assert report.review_status is AlignmentReviewStatus.CLEAR
    assert report.measurement_comparability_grade is MeasurementComparabilityGrade.MEDIUM


def test_build_alignment_report_marks_only_pending_review_as_partial() -> None:
    proxy_report = build_alignment_report(
        fragment_ids=["education", "labor"],
        certificates=[
            _certificate(
                alignment_type=AlignmentType.PROXY,
                reviewer=AlignmentReviewerState.HUMAN_VERIFIED,
            )
        ],
    )
    pending_report = build_alignment_report(
        fragment_ids=["education", "labor"],
        certificates=[_certificate(reviewer=AlignmentReviewerState.PENDING_REVIEW)],
    )

    assert proxy_report.overall_status is AlignmentOverallStatus.ALIGNED
    assert proxy_report.review_status is AlignmentReviewStatus.CLEAR
    assert proxy_report.measurement_comparability_grade is MeasurementComparabilityGrade.LOW
    assert pending_report.overall_status is AlignmentOverallStatus.PARTIALLY_ALIGNED
    assert pending_report.review_status is AlignmentReviewStatus.PENDING_REVIEW
    assert pending_report.measurement_comparability_grade is MeasurementComparabilityGrade.MEDIUM


def test_build_alignment_report_marks_incompatible_and_deduplicates_assumptions() -> None:
    report = build_alignment_report(
        fragment_ids=["education", "labor", "health"],
        certificates=[
            _certificate(
                alignment_type=AlignmentType.INCOMPATIBLE,
                assumptions=["manual review", "manual review"],
            ),
            _certificate(
                alignment_type=AlignmentType.PROXY,
                assumptions=["manual review", "proxy stability"],
            ),
        ],
        ontology_mismatch_warnings=["employment mismatch", "employment mismatch"],
    )

    assert report.overall_status is AlignmentOverallStatus.INCOMPATIBLE
    assert report.review_status is AlignmentReviewStatus.CLEAR
    assert report.measurement_comparability_grade is MeasurementComparabilityGrade.INSUFFICIENT
    assert report.incompatible_pairs == [("education:years_of_education", "labor:years_of_education")]
    assert report.alignment_assumptions == ["manual review", "proxy stability"]
    assert report.ontology_mismatch_warnings == ["employment mismatch"]


def test_phase_b_contracts_round_trip_via_store(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    fragment = _fragment()
    certificate = _certificate(
        alignment_type=AlignmentType.SCALE_LINKED,
        assumptions=["known linear transform"],
    )
    report = build_alignment_report(
        fragment_ids=["education", "labor"],
        certificates=[certificate],
    )

    fragment_ref = persist_scm_fragment(store, fragment)
    certificate_ref = persist_variable_alignment_certificate(store, certificate)
    report_ref = persist_alignment_report(store, report)

    assert isinstance(fragment_ref, SCMFragmentRef)
    assert isinstance(certificate_ref, VariableAlignmentCertificateRef)
    assert isinstance(report_ref, AlignmentReportRef)
    assert load_scm_fragment(store, fragment_ref) == fragment
    assert load_variable_alignment_certificate(store, certificate_ref) == certificate
    assert load_alignment_report(store, report_ref) == report


def test_verify_fragment_alignment_returns_exact_mapping() -> None:
    fragment_a = SCMFragment(
        fragment_id="labor_a",
        graph_ref="artifact:graph:labor_a",
        semantic_namespace="policy.labor",
        interface_variables=["employment_rate"],
        exposed_outputs=["employment_rate"],
        variable_definitions={"employment_rate": "Share of employed working-age population"},
        variable_units={"employment_rate": "percent"},
    )
    fragment_b = SCMFragment(
        fragment_id="labor_b",
        graph_ref="artifact:graph:labor_b",
        semantic_namespace="policy.labor",
        interface_variables=["employment_rate"],
        exposed_inputs=["employment_rate"],
        variable_definitions={"employment_rate": "Share of employed working-age population"},
        variable_units={"employment_rate": "percent"},
    )

    report, mapping = verify_fragment_alignment(fragment_a, fragment_b)

    assert report.overall_status is AlignmentOverallStatus.ALIGNED
    assert report.review_status is AlignmentReviewStatus.CLEAR
    assert mapping.entries[0].alignment_type == "exact"
    assert mapping.entries[0].observed is True
    assert len(mapping.entries[0].bindings) == 2


def test_verify_fragment_alignment_tracks_boundary_interfaces_for_asymmetric_stitch() -> None:
    fragment_a = SCMFragment(
        fragment_id="a",
        graph_ref="artifact:graph:a",
        semantic_namespace="policy.labor",
        interface_variables=["employment_rate"],
        exposed_outputs=["employment_rate"],
        variable_definitions={"employment_rate": "Employment rate"},
        variable_units={"employment_rate": "percent"},
    )
    fragment_b = SCMFragment(
        fragment_id="b",
        graph_ref="artifact:graph:b",
        semantic_namespace="policy.training",
        interface_variables=["employment_rate", "wages"],
        exposed_inputs=["employment_rate"],
        exposed_outputs=["wages"],
        variable_definitions={
            "employment_rate": "Employment rate",
            "wages": "Average wage level",
        },
        variable_units={"employment_rate": "percent", "wages": "usd_per_month"},
    )

    report, mapping = verify_fragment_alignment(fragment_a, fragment_b)

    assert report.overall_status is AlignmentOverallStatus.ALIGNED
    assert report.review_status is AlignmentReviewStatus.CLEAR
    assert report.incompatible_pairs == []
    assert report.metadata["selected_stitch_pairs"] == [["a", "b"]]
    assert report.metadata["boundary_interface_variables"] == {"a": [], "b": ["wages"]}
    assert len(report.per_variable_certificates) == 1
    assert len(mapping.entries) == 1


def test_verify_fragment_alignment_detects_scale_linked_units() -> None:
    fragment_a = SCMFragment(
        fragment_id="labor_pct",
        graph_ref="artifact:graph:labor_pct",
        semantic_namespace="policy.labor",
        interface_variables=["employment_rate"],
        exposed_outputs=["employment_rate"],
        variable_definitions={"employment_rate": "Employment rate among working-age adults"},
        variable_units={"employment_rate": "percent"},
    )
    fragment_b = SCMFragment(
        fragment_id="labor_ratio",
        graph_ref="artifact:graph:labor_ratio",
        semantic_namespace="policy.labor",
        interface_variables=["employment_rate"],
        exposed_inputs=["employment_rate"],
        variable_definitions={"employment_rate": "Employment rate among working-age adults"},
        variable_units={"employment_rate": "ratio"},
    )

    report, mapping = verify_fragment_alignment(
        fragment_a,
        fragment_b,
        config=AlignmentVerificationConfig(),
    )

    assert report.overall_status is AlignmentOverallStatus.ALIGNED
    assert report.review_status is AlignmentReviewStatus.CLEAR
    assert report.measurement_comparability_grade is MeasurementComparabilityGrade.MEDIUM
    assert mapping.entries[0].alignment_type == "scale_linked"


def test_verify_fragment_alignment_marks_proxy_and_pending_review() -> None:
    fragment_a = SCMFragment(
        fragment_id="governance_a",
        graph_ref="artifact:graph:governance_a",
        semantic_namespace="policy.governance",
        interface_variables=["RL.EST"],
        exposed_outputs=["RL.EST"],
        variable_definitions={"RL.EST": "Rule of law estimate"},
    )
    fragment_b = SCMFragment(
        fragment_id="governance_b",
        graph_ref="artifact:graph:governance_b",
        semantic_namespace="policy.governance",
        interface_variables=["GE.EST"],
        exposed_inputs=["GE.EST"],
        variable_definitions={"GE.EST": "Government effectiveness estimate"},
    )

    report, mapping = verify_fragment_alignment(fragment_a, fragment_b)

    assert report.overall_status is AlignmentOverallStatus.PARTIALLY_ALIGNED
    assert report.review_status is AlignmentReviewStatus.PENDING_REVIEW
    assert report.per_variable_certificates[0].alignment_type is AlignmentType.PROXY
    assert report.per_variable_certificates[0].reviewer is AlignmentReviewerState.PENDING_REVIEW
    assert mapping.entries[0].alignment_type == "proxy"


def test_verify_fragment_alignment_marks_human_verified_proxy_as_aligned() -> None:
    fragment_a = SCMFragment(
        fragment_id="governance_a",
        graph_ref="artifact:graph:governance_a",
        semantic_namespace="policy.governance",
        interface_variables=["RL.EST"],
        exposed_outputs=["RL.EST"],
        variable_definitions={"RL.EST": "Rule of law estimate"},
    )
    fragment_b = SCMFragment(
        fragment_id="governance_b",
        graph_ref="artifact:graph:governance_b",
        semantic_namespace="policy.governance",
        interface_variables=["GE.EST"],
        exposed_inputs=["GE.EST"],
        variable_definitions={"GE.EST": "Government effectiveness estimate"},
    )

    report, mapping = verify_fragment_alignment(
        fragment_a,
        fragment_b,
        config=AlignmentVerificationConfig(human_verified_pairs=["governance_a:RL.EST|governance_b:GE.EST"]),
    )

    assert report.overall_status is AlignmentOverallStatus.ALIGNED
    assert report.review_status is AlignmentReviewStatus.CLEAR
    assert report.per_variable_certificates[0].alignment_type is AlignmentType.PROXY
    assert report.per_variable_certificates[0].reviewer is AlignmentReviewerState.HUMAN_VERIFIED
    assert mapping.entries[0].reviewer == "human_verified"


def test_verify_fragment_alignment_marks_same_name_semantic_conflict_incompatible() -> None:
    fragment_a = SCMFragment(
        fragment_id="labor",
        graph_ref="artifact:graph:labor",
        semantic_namespace="policy.labor",
        interface_variables=["rate"],
        exposed_outputs=["rate"],
        variable_definitions={"rate": "Employment rate among working-age adults"},
        variable_units={"rate": "percent"},
        measurement_models={"rate": "artifact:mm:labor"},
    )
    fragment_b = SCMFragment(
        fragment_id="health",
        graph_ref="artifact:graph:health",
        semantic_namespace="policy.health",
        interface_variables=["rate"],
        exposed_inputs=["rate"],
        variable_definitions={"rate": "Hospital occupancy beds"},
        variable_units={"rate": "beds_per_hospital"},
        measurement_models={"rate": "artifact:mm:health"},
    )

    report, mapping = verify_fragment_alignment(fragment_a, fragment_b)

    assert report.overall_status is AlignmentOverallStatus.INCOMPATIBLE
    assert report.review_status is AlignmentReviewStatus.CLEAR
    assert report.per_variable_certificates[0].alignment_type is AlignmentType.INCOMPATIBLE
    assert report.incompatible_pairs == [("labor:rate", "health:rate")]
    assert mapping.entries == []


def test_verify_fragment_alignment_emits_explicit_incompatible_for_unrelated_interfaces() -> None:
    fragment_a = SCMFragment(
        fragment_id="labor",
        graph_ref="artifact:graph:labor",
        semantic_namespace="policy.labor",
        interface_variables=["employment_rate"],
        exposed_outputs=["employment_rate"],
        variable_definitions={"employment_rate": "Employment rate among working-age adults"},
        variable_units={"employment_rate": "percent"},
    )
    fragment_b = SCMFragment(
        fragment_id="health",
        graph_ref="artifact:graph:health",
        semantic_namespace="policy.health",
        interface_variables=["hospital_occupancy"],
        exposed_inputs=["hospital_occupancy"],
        variable_definitions={"hospital_occupancy": "Hospital occupancy rate"},
        variable_units={"hospital_occupancy": "beds_per_hospital"},
    )

    report, mapping = verify_fragment_alignment(fragment_a, fragment_b)

    assert report.overall_status is AlignmentOverallStatus.INCOMPATIBLE
    assert report.review_status is AlignmentReviewStatus.CLEAR
    assert len(report.per_variable_certificates) == 1
    assert report.per_variable_certificates[0].alignment_type is AlignmentType.INCOMPATIBLE
    assert report.incompatible_pairs == [
        ("labor:employment_rate", "health:hospital_occupancy")
    ]
    assert mapping.entries == []


def test_verify_fragment_alignment_emits_latent_bridge_and_ontology_warning() -> None:
    fragment_a = SCMFragment(
        fragment_id="labor",
        graph_ref="artifact:graph:labor",
        semantic_namespace="policy.labor",
        interface_variables=["employment_rate"],
        exposed_outputs=["employment_rate"],
        variable_definitions={"employment_rate": "Employment rate"},
    )
    fragment_b = SCMFragment(
        fragment_id="health",
        graph_ref="artifact:graph:health",
        semantic_namespace="policy.health",
        interface_variables=["employment_rate"],
        exposed_inputs=["employment_rate"],
        variable_definitions={"employment_rate": "Employment rate"},
    )

    pair_key = "health:employment_rate|labor:employment_rate"
    report, _ = verify_fragment_alignment(
        fragment_a,
        fragment_b,
        config=AlignmentVerificationConfig(explicit_latent_bridges={pair_key: "artifact:latent:bridge"}),
        ontology=[
            {
                "concept_id": "concept.labor.employment",
                "concept_kind": "variable",
                "label": "Labor employment rate",
                "join_keys": {"namespace": ["policy.labor"], "variable": ["employment_rate"]},
            },
            {
                "concept_id": "concept.health.employment",
                "concept_kind": "variable",
                "label": "Health employment rate",
                "join_keys": {"namespace": ["policy.health"], "variable": ["employment_rate"]},
            },
        ],
    )

    assert report.per_variable_certificates[0].alignment_type is AlignmentType.LATENT_BRIDGE
    assert report.per_variable_certificates[0].reviewer is AlignmentReviewerState.PENDING_REVIEW
    assert report.review_status is AlignmentReviewStatus.PENDING_REVIEW
    assert report.ontology_mismatch_warnings


def test_verify_fragment_alignment_marks_human_verified_latent_bridge_as_aligned() -> None:
    fragment_a = SCMFragment(
        fragment_id="labor",
        graph_ref="artifact:graph:labor",
        semantic_namespace="policy.labor",
        interface_variables=["employment_rate"],
        exposed_outputs=["employment_rate"],
        variable_definitions={"employment_rate": "Employment rate"},
    )
    fragment_b = SCMFragment(
        fragment_id="health",
        graph_ref="artifact:graph:health",
        semantic_namespace="policy.health",
        interface_variables=["employment_rate"],
        exposed_inputs=["employment_rate"],
        variable_definitions={"employment_rate": "Employment rate"},
    )

    pair_key = "health:employment_rate|labor:employment_rate"
    report, mapping = verify_fragment_alignment(
        fragment_a,
        fragment_b,
        config=AlignmentVerificationConfig(
            explicit_latent_bridges={pair_key: "artifact:latent:bridge"},
            human_verified_pairs=[pair_key],
        ),
    )

    assert report.overall_status is AlignmentOverallStatus.ALIGNED
    assert report.review_status is AlignmentReviewStatus.CLEAR
    assert report.measurement_comparability_grade is MeasurementComparabilityGrade.LOW
    assert report.per_variable_certificates[0].alignment_type is AlignmentType.LATENT_BRIDGE
    assert report.per_variable_certificates[0].reviewer is AlignmentReviewerState.HUMAN_VERIFIED
    assert mapping.entries[0].reviewer == "human_verified"


def test_verify_fragment_bundle_alignment_merges_pairwise_mapping() -> None:
    fragments = [
        SCMFragment(
            fragment_id="a",
            graph_ref="artifact:graph:a",
            semantic_namespace="policy.labor",
            interface_variables=["employment_rate"],
            exposed_outputs=["employment_rate"],
            variable_definitions={"employment_rate": "Employment rate"},
            variable_units={"employment_rate": "percent"},
        ),
        SCMFragment(
            fragment_id="b",
            graph_ref="artifact:graph:b",
            semantic_namespace="policy.labor",
            interface_variables=["employment_rate"],
            exposed_inputs=["employment_rate"],
            exposed_outputs=["employment_rate"],
            variable_definitions={"employment_rate": "Employment rate"},
            variable_units={"employment_rate": "percent"},
        ),
        SCMFragment(
            fragment_id="c",
            graph_ref="artifact:graph:c",
            semantic_namespace="policy.labor",
            interface_variables=["employment_rate"],
            exposed_inputs=["employment_rate"],
            variable_definitions={"employment_rate": "Employment rate"},
            variable_units={"employment_rate": "percent"},
        ),
    ]

    report, mapping = verify_fragment_bundle_alignment(fragments)

    assert report.overall_status is AlignmentOverallStatus.ALIGNED
    assert report.review_status is AlignmentReviewStatus.CLEAR
    assert len(mapping.entries) == 1
    assert {binding.fragment_id for binding in mapping.entries[0].bindings} == {"a", "b", "c"}
    assert len(report.metadata["selected_stitch_pairs"]) == 2
    assert ["a", "b"] in report.metadata["selected_stitch_pairs"]
    assert report.metadata["disconnected_fragment_ids"] == []


def test_interface_mapping_and_composition_certificate_round_trip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    report, mapping = verify_fragment_alignment(
        SCMFragment(
            fragment_id="a",
            graph_ref="artifact:graph:a",
            semantic_namespace="policy.labor",
            interface_variables=["employment_rate"],
            exposed_outputs=["employment_rate"],
            variable_definitions={"employment_rate": "Employment rate"},
            variable_units={"employment_rate": "percent"},
        ),
        SCMFragment(
            fragment_id="b",
            graph_ref="artifact:graph:b",
            semantic_namespace="policy.labor",
            interface_variables=["employment_rate"],
            exposed_inputs=["employment_rate"],
            variable_definitions={"employment_rate": "Employment rate"},
            variable_units={"employment_rate": "percent"},
        ),
    )
    mapping_ref = persist_interface_mapping(store, mapping)
    certificate = CompositionCertificate(
        status="preserved",
        composed_graph_ref="artifact:graph:stitched",
        interface_mapping_ref=str(mapping_ref.artifact_id),
        alignment_report_ref="artifact:report:alignment",
        checked_queries={},
        source_fragment_refs={"a": "artifact:fragment:a", "b": "artifact:fragment:b"},
        source_fragment_graph_refs={"a": "artifact:graph:a", "b": "artifact:graph:b"},
        failure_card_bundle_ref="artifact:failure_cards:bundle",
    )
    certificate_ref = persist_composition_certificate(store, certificate)

    assert isinstance(mapping_ref, InterfaceMappingRef)
    assert isinstance(certificate_ref, CompositionCertificateRef)
    assert load_interface_mapping(store, mapping_ref) == mapping
    assert load_composition_certificate(store, certificate_ref) == certificate


def test_alignment_report_type_is_public_contract() -> None:
    report = build_alignment_report(
        fragment_ids=["education", "labor"],
        certificates=[_certificate()],
    )

    assert isinstance(report, AlignmentReport)


def test_verify_fragment_alignment_propagates_metadata_checks_and_bindings() -> None:
    fragment_a = SCMFragment(
        fragment_id="a",
        graph_ref="artifact:graph:a",
        semantic_namespace="policy.labor",
        interface_variables=["employment_rate"],
        exposed_outputs=["employment_rate"],
        variable_definitions={"employment_rate": "Employment rate"},
        variable_metadata={
            "employment_rate": {
                "population": "adults",
                "geography": "Kyiv",
                "time_window": {"start": "2020-01-01", "end": "2020-12-31"},
            }
        },
    )
    fragment_b = SCMFragment(
        fragment_id="b",
        graph_ref="artifact:graph:b",
        semantic_namespace="policy.labor",
        interface_variables=["employment_rate"],
        exposed_inputs=["employment_rate"],
        variable_definitions={"employment_rate": "Employment rate"},
        variable_metadata={
            "employment_rate": {
                "population": "adults",
                "geography": "Lviv",
                "time_window": {"start": "2020-06-01", "end": "2020-09-01"},
            }
        },
    )

    report, mapping = verify_fragment_alignment(fragment_a, fragment_b)
    certificate = report.per_variable_certificates[0]

    assert report.metadata["metadata_warnings"] == [
        "geography: geography differs",
        "time_window: time windows overlap or contain each other",
    ]
    assert certificate.metadata_checks[0].status is MetadataCheckStatus.MATCH
    assert {check.key: check.status for check in certificate.metadata_checks} == {
        "population": MetadataCheckStatus.MATCH,
        "geography": MetadataCheckStatus.WARNING,
        "time_window": MetadataCheckStatus.WARNING,
    }
    assert mapping.entries[0].bindings[0].metadata["population"] == "adults"


def test_verify_fragment_alignment_rejects_hard_metadata_mismatch() -> None:
    fragment_a = SCMFragment(
        fragment_id="a",
        graph_ref="artifact:graph:a",
        semantic_namespace="policy.labor",
        interface_variables=["employment_rate"],
        exposed_outputs=["employment_rate"],
        variable_definitions={"employment_rate": "Employment rate"},
        variable_metadata={"employment_rate": {"population": "adults"}},
    )
    fragment_b = SCMFragment(
        fragment_id="b",
        graph_ref="artifact:graph:b",
        semantic_namespace="policy.labor",
        interface_variables=["employment_rate"],
        exposed_inputs=["employment_rate"],
        variable_definitions={"employment_rate": "Employment rate"},
        variable_metadata={"employment_rate": {"population": "youth"}},
    )

    report, mapping = verify_fragment_alignment(fragment_a, fragment_b)

    assert report.overall_status is AlignmentOverallStatus.INCOMPATIBLE
    assert report.per_variable_certificates[0].alignment_type is AlignmentType.INCOMPATIBLE
    assert {check.key: check.status for check in report.per_variable_certificates[0].metadata_checks} == {
        "population": MetadataCheckStatus.MISMATCH
    }
    assert mapping.entries == []
