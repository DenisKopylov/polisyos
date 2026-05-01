from __future__ import annotations

from polisyos.scholar import ScholarFabricCitation, scholar_citation_from_fabric_decision_data


def test_scholar_citation_uses_fabric_lineage_and_contract() -> None:
    citation = scholar_citation_from_fabric_decision_data(
        {
            "id": "fabric_decision_data:run_123:gdp",
            "source_contract": {"id": "worldbank.wdi.generic", "version": "1.1.0"},
            "quality": {"status": "passed", "score": 0.97},
            "lineage": {
                "id": "lin_gdp",
                "raw_evidence_refs": ["cas://sha256/source"],
                "export_links": {"prov": "/api/v1/lineage/lin_gdp?format=prov"},
            },
            "access": {"classification": "public"},
            "replay": {"status": "replayable"},
        },
        title="GDP evidence",
    )

    assert isinstance(citation, ScholarFabricCitation)
    assert citation.citation_id == "fabric:lin_gdp"
    assert citation.title == "GDP evidence"
    assert citation.source_contract_id == "worldbank.wdi.generic"
    assert citation.evidence_refs == ("cas://sha256/source",)
