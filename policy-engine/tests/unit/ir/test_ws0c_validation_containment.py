from __future__ import annotations

import logging

import pytest

import polisyos.scientist.cross_graph.compiler as cross_graph_compiler_module
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.alignment_certification import (
    AlignmentDegradedOutcomeCode,
    AlignmentType,
    AlignmentVerificationConfig,
)
from polisyos.ir.analytics.context import (
    ContextEnrichmentIssueCode,
    ContextProfile,
    ContextProfileInferenceLevel,
)
from polisyos.ir.analytics.cross_graph import SCMFragment
from polisyos.ir.analytics.latent_bridge_synthesis import (
    LatentBridgeFalsificationTest,
    LatentBridgeFalsificationTestFamily,
    LatentBridgeFalsificationTestStatus,
    LatentBridgeHeldoutMetrics,
    LatentBridgeHypothesis,
    LatentBridgeStatus,
    LatentBridgeSynthesisMode,
    load_latent_bridge_hypothesis,
    persist_latent_bridge_hypothesis,
)
from polisyos.scientist.cross_graph.compiler import (
    _verify_fragment_bundle_alignment_with_governance,
)


class _RaisingIndicatorsClient:
    def get_indicators(self, context_id: str, year: int) -> dict[str, object]:
        raise ValueError(f"backend unavailable for {context_id}/{year}")


class _InvalidPayloadClient:
    def get_indicators(self, context_id: str, year: int) -> list[str]:
        return ["unexpected", context_id, str(year)]


class _FinderFallbackClient:
    def find_closest_in_wave(
        self,
        context_id: str,
        year: int,
        *,
        max_distance_years: int,
    ) -> tuple[int, str]:
        raise LookupError(f"no survey wave for {context_id}/{year} within {max_distance_years}")

    def get_indicators(self, context_id: str, survey_year: int | None = None) -> dict[str, object]:
        return {
            "social_trust": 0.61,
            "cultural_cluster": f"{context_id}:{survey_year}",
        }


def _fragment(fragment_id: str, namespace: str) -> SCMFragment:
    return SCMFragment(
        fragment_id=fragment_id,
        graph_ref=f"artifact:graph:{fragment_id}",
        semantic_namespace=namespace,
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


def test_context_enrichment_records_structured_issue_for_fetch_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    profile = ContextProfile(context_id="UA")

    with caplog.at_level(logging.WARNING):
        enriched = profile.enrich_from_datasources(
            wgi=_RaisingIndicatorsClient(),
            wvs=None,
            wdi=None,
            year=2024,
        )

    assert enriched.inference_level is ContextProfileInferenceLevel.INFERRED_BASIC
    assert enriched.data_sources == []
    assert len(enriched.enrichment_issues) == 1
    issue = enriched.enrichment_issues[0]
    assert issue.source == "wgi"
    assert issue.code is ContextEnrichmentIssueCode.FETCH_FAILED
    assert issue.context_id == "UA"
    assert issue.year == 2024
    assert "backend unavailable" in issue.detail
    assert "Context enrichment wgi get_indicators failed" in caplog.text


def test_context_enrichment_distinguishes_invalid_payload_from_absent_source() -> None:
    profile = ContextProfile(context_id="PL")

    enriched = profile.enrich_from_datasources(
        wgi=_InvalidPayloadClient(),
        wvs=None,
        wdi=None,
        year=2023,
    )

    assert enriched.data_sources == []
    assert len(enriched.enrichment_issues) == 1
    issue = enriched.enrichment_issues[0]
    assert issue.code is ContextEnrichmentIssueCode.INVALID_PAYLOAD
    assert "expected mapping payload" in issue.detail


def test_context_enrichment_preserves_successful_wvs_fetch_when_finder_degrades() -> None:
    profile = ContextProfile(context_id="RO")

    enriched = profile.enrich_from_datasources(
        wgi=None,
        wvs=_FinderFallbackClient(),
        wdi=None,
        year=2022,
    )

    assert enriched.inference_level is ContextProfileInferenceLevel.ENRICHED
    assert enriched.data_sources == ["wvs"]
    assert enriched.social_trust == pytest.approx(0.61)
    assert enriched.cultural_cluster == "RO:2022"
    assert len(enriched.enrichment_issues) == 1
    assert enriched.enrichment_issues[0].code is ContextEnrichmentIssueCode.FINDER_FAILED


def test_alignment_report_records_degraded_outcome_when_ontology_warning_builder_fails(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def _raise_builder(**_: object) -> list[str]:
        raise ValueError("ontology adapter mismatch")

    monkeypatch.setattr(
        cross_graph_compiler_module,
        "build_fragment_alignment_ontology_warnings",
        _raise_builder,
    )

    with caplog.at_level(logging.WARNING):
        report, _ = _verify_fragment_bundle_alignment_with_governance(
            [
                _fragment("education", "policy.education"),
                _fragment("labor", "policy.labor"),
            ],
            ontology=[{"unexpected": "payload"}],
        )

    assert any(
        "ontology_warning_build_failed" in warning for warning in report.ontology_mismatch_warnings
    )
    degraded_outcomes = report.metadata.get("degraded_outcomes")
    assert isinstance(degraded_outcomes, list)
    assert degraded_outcomes[0]["code"] == (
        AlignmentDegradedOutcomeCode.ONTOLOGY_WARNING_BUILD_FAILED.value
    )
    assert tuple(degraded_outcomes[0]["fragment_pair"]) == ("education", "labor")
    assert degraded_outcomes[0]["detail"] == "ontology adapter mismatch"
    assert "Alignment ontology warning build failed" in caplog.text


def test_alignment_ontology_missing_snapshot_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cross_graph_compiler_module,
        "_alignment_ontology_warning_results",
        lambda **_: (),
    )

    report, _ = _verify_fragment_bundle_alignment_with_governance(
        [
            _fragment("education", "policy.education"),
            _fragment("labor", "policy.labor"),
        ],
        ontology=[{"concept_id": "concept:employment"}],
    )

    degraded_outcomes = report.metadata.get("degraded_outcomes")
    assert isinstance(degraded_outcomes, list)
    assert degraded_outcomes[0]["code"] == (
        AlignmentDegradedOutcomeCode.ONTOLOGY_WARNING_BUILD_FAILED.value
    )
    assert degraded_outcomes[0]["detail"] == "ontology warning snapshot missing"


def test_alignment_governance_recomputes_forged_candidate_metadata(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    pair_key = "education:employment_rate|labor:employment_rate"
    fragment_a = _fragment("education", "policy.education").model_copy(
        update={
            "interface_variables": ["employment_rate"],
            "exposed_inputs": [],
            "exposed_outputs": ["employment_rate"],
        }
    )
    fragment_b = _fragment("labor", "policy.labor").model_copy(
        update={
            "interface_variables": ["employment_rate"],
            "exposed_inputs": ["employment_rate"],
            "exposed_outputs": [],
        }
    )
    candidate_ref = persist_latent_bridge_hypothesis(
        store,
        LatentBridgeHypothesis(
            bridge_id="latent::bridge::candidate",
            pair_key=pair_key,
            status=LatentBridgeStatus.PROPOSED,
            synthesis_mode=LatentBridgeSynthesisMode.MEASUREMENT_MODEL,
            heldout_metrics=LatentBridgeHeldoutMetrics(
                delta_cv=0.2,
                lower_ci=0.1,
            ),
            falsification_tests=[
                LatentBridgeFalsificationTest(
                    test_family=LatentBridgeFalsificationTestFamily.CTA,
                    status=LatentBridgeFalsificationTestStatus.PASS,
                )
            ],
            metadata={
                "latent_governance": {
                    "active": True,
                    "valid": True,
                    "claim_mode": "validated_measurement_latent",
                    "degradation_mode": "measurement_ready",
                    "readiness_cap": "estimation_ready",
                    "promotion_allowed": True,
                    "human_gate_required": False,
                    "not_for_decision_support": False,
                    "missing_requirements": [],
                    "surfaced_assumptions": [],
                    "surfaced_falsification_tests": [],
                    "no_promotion_reasons": [],
                    "promotion_verdict": None,
                    "metadata": {"latent_artifact_kind": "latent_bridge"},
                }
            },
        ),
    )

    report, mapping = _verify_fragment_bundle_alignment_with_governance(
        [fragment_a, fragment_b],
        config=AlignmentVerificationConfig(
            explicit_latent_bridges={pair_key: candidate_ref}
        ),
        artifact_store=store,
    )

    certificate = next(
        item
        for item in report.per_variable_certificates
        if item.metadata.get("pair_key") == pair_key
    )
    governance = certificate.metadata["latent_bridge_governance"]
    assert certificate.alignment_type is AlignmentType.LATENT_BRIDGE
    assert governance["readiness_cap"] == "proof_only"
    assert governance["promotion_allowed"] is False
    assert governance["not_for_decision_support"] is True
    assert certificate.latent_bridge_hypothesis_ref is not None
    governed = load_latent_bridge_hypothesis(
        store,
        certificate.latent_bridge_hypothesis_ref,
    )
    assert governed.readiness_cap == "proof_only"
    assert governed.promotion_allowed is False
    assert governed.metadata["latent_governance"]["promotion_allowed"] is False
    latent_entry = next(item for item in mapping.entries if item.alignment_type == "latent_bridge")
    assert latent_entry.metadata["latent_bridge_readiness_cap"] == "proof_only"
    assert latent_entry.metadata["latent_bridge_promotion_allowed"] is False

    canonical_builder = cross_graph_compiler_module._build_latent_governance_input

    def _tamper_receipt(**kwargs):
        return canonical_builder(**kwargs).model_copy(
            update={"receipt_content_hash": "sha256:" + "0" * 64}
        )

    monkeypatch.setattr(
        cross_graph_compiler_module,
        "_build_latent_governance_input",
        _tamper_receipt,
    )
    rejected_report, rejected_mapping = (
        _verify_fragment_bundle_alignment_with_governance(
            [fragment_a, fragment_b],
            config=AlignmentVerificationConfig(
                explicit_latent_bridges={pair_key: candidate_ref}
            ),
            artifact_store=store,
        )
    )
    rejected = next(
        item
        for item in rejected_report.per_variable_certificates
        if item.metadata.get("pair_key") == pair_key
    )
    assert rejected.alignment_type is AlignmentType.INCOMPATIBLE
    assert "latent_governance_snapshot_invalid" in rejected.metadata[
        "hard_conflict_reasons"
    ]
    assert rejected_mapping.entries == []
