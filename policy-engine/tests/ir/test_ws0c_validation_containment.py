from __future__ import annotations

import logging

import pytest

import polisyos.ir.analytics.alignment_certification as alignment_module
from polisyos.ir.analytics.alignment_certification import (
    AlignmentDegradedOutcomeCode,
    verify_fragment_alignment,
)
from polisyos.ir.analytics.context import (
    ContextEnrichmentIssueCode,
    ContextProfile,
    ContextProfileInferenceLevel,
)
from polisyos.ir.analytics.cross_graph import SCMFragment


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
        alignment_module,
        "build_fragment_alignment_ontology_warnings",
        _raise_builder,
    )

    with caplog.at_level(logging.WARNING):
        report, _ = verify_fragment_alignment(
            _fragment("education", "policy.education"),
            _fragment("labor", "policy.labor"),
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
