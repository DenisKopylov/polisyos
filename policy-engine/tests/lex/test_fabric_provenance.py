from __future__ import annotations

from polisyos.lex import LexFabricEvidencePath, lex_evidence_from_fabric_decision_data


def test_lex_evidence_path_uses_fabric_raw_refs_and_replay_state() -> None:
    evidence = lex_evidence_from_fabric_decision_data(
        {
            "id": "fabric_decision_data:run_123:citation",
            "source_contract": {"id": "parliament.legislation.generic"},
            "quality": {"status": "passed", "score": 0.91},
            "lineage": {
                "id": "lin_law",
                "raw_evidence_refs": ["cas://sha256/legal-source"],
                "export_links": {"raw": "/api/v1/lineage/lin_law/raw"},
            },
            "access": {"classification": "public"},
            "replay": {"status": "replayable"},
        },
        citation_label="Legal evidence",
    )

    assert isinstance(evidence, LexFabricEvidencePath)
    assert evidence.legal_evidence_id == "fabric:fabric_decision_data:run_123:citation"
    assert evidence.lineage_path == "lin_law"
    assert evidence.raw_source_refs == ("cas://sha256/legal-source",)
    assert evidence.replay_status == "replayable"
