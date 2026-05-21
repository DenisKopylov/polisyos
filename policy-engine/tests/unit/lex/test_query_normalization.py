from __future__ import annotations

from polisyos.lex.normpack.query_normalization import (
    LEX_QUERY_NORMALIZATION_SCHEMA_VERSION,
    legal_requirements_from_query_normalization_report,
    normalize_lex_query_terms,
)
from polisyos.runtime.quality.scenario_evidence_contract import (
    normalize_scenario_evidence_contract,
)
from tools.ops_runners.runtime.quality_scenarios import (
    DEFAULT_QUALITY_SCENARIO_ID,
    load_quality_scenario_contract,
)


def test_ukraine_msme_query_expands_to_ukrainian_legal_terms() -> None:
    scenario = load_quality_scenario_contract(DEFAULT_QUALITY_SCENARIO_ID)
    scenario_contract = normalize_scenario_evidence_contract(scenario).to_dict()

    report = normalize_lex_query_terms(
        original_terms=[
            "MSME credit grant wartime eligibility",
            "Ukraine wartime MSME support policy",
        ],
        target_context={
            "jurisdiction": "UA",
            "policy_domain": "wartime_msme_support",
            "as_of": "2026-05-20",
        },
        scenario_evidence_contract=scenario_contract,
        kg_paths=["/data/legal/finalize/lex_knowledge_graph.duckdb"],
    ).to_dict()

    assert report["schema_version"] == LEX_QUERY_NORMALIZATION_SCHEMA_VERSION
    assert report["jurisdiction_tags"] == ["UA"]
    assert {"en", "uk"} <= set(report["language_tags"])
    assert report["language_coverage"]["status"] == "pass"
    normalized = " ".join(report["normalized_terms"]).casefold()
    for expected_stem in ("підприєм", "кредит", "грант", "воєн"):
        assert expected_stem in normalized

    required_legal_facets = {
        "competence_refs",
        "temporal_validity_refs",
        "policy_instrument_refs",
        "beneficiary_class_refs",
        "fiscal_authority_refs",
        "implementation_agency_refs",
    }
    assert report["legal_requirements"]
    for requirement in report["legal_requirements"]:
        assert required_legal_facets <= set(requirement["required_facets"])


def test_query_normalization_preserves_nested_legal_requirements_without_top_level() -> None:
    nested_requirements = [
        {
            "requirement_id": f"legal_requirement_{index}",
            "domain": "legal",
            "expected_family": "credit_eligibility_rule",
            "required_facets": ["competence_refs"],
            "jurisdiction": "UA",
        }
        for index in range(1, 5)
    ]

    requirements = legal_requirements_from_query_normalization_report(
        {
            "schema_version": LEX_QUERY_NORMALIZATION_SCHEMA_VERSION,
            "original_terms": ["credit eligibility"],
            "normalized_terms": ["кредит", "підприєм"],
            "query_normalization_report": {
                "legal_requirements": nested_requirements,
            },
        }
    )

    assert [item["requirement_id"] for item in requirements] == [
        "legal_requirement_1",
        "legal_requirement_2",
        "legal_requirement_3",
        "legal_requirement_4",
    ]
    assert all(item["jurisdiction"] == "UA" for item in requirements)
