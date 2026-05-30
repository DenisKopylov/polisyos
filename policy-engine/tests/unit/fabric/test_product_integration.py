from __future__ import annotations

from polisyos.fabric._internal.compatibility import validate_fabric_compatibility_bridges
from polisyos.fabric.product_integration import (
    evidence_path_from_fabric_decision_data,
    evidence_paths_from_fabric_decision_data,
)


def _decision_data() -> dict[str, object]:
    return {
        "id": "fabric_decision_data:run_123:effect_size",
        "kind": "quantity",
        "value": {"label": "Effect size", "point": 0.23},
        "source_contract": {"id": "worldbank.wdi.generic", "version": "1.1.0"},
        "quality": {"status": "passed", "score": 0.8},
        "lineage": {
            "id": "lin_abc123",
            "status": "verified",
            "raw_evidence_refs": ["cas://sha256/raw"],
            "export_links": {"openlineage": "/api/v1/lineage/lin_abc123?format=openlineage"},
            "trust_metadata": {"freshness": "stale"},
        },
        "access": {"classification": "public", "pii_tier": "none"},
        "time": {"valid_at": "2026-04-15T12:00:00Z", "tx_at": "2026-04-16T09:20:00Z"},
        "replay": {"status": "replayable", "manifest_ref": "cas://sha256/replay"},
        "metadata": {"source_trust_tier": "low"},
    }


def test_fabric_product_evidence_path_normalizes_decision_data() -> None:
    path = evidence_path_from_fabric_decision_data(_decision_data())

    assert path.subject_id == "fabric_decision_data:run_123:effect_size"
    assert path.lineage_id == "lin_abc123"
    assert path.source_contract_id == "worldbank.wdi.generic"
    assert path.evidence_refs == ("cas://sha256/raw",)
    assert path.export_links["openlineage"].endswith("format=openlineage")
    assert path.calibration_weight == 0.2
    assert path.uncertainty_inflation == 1.8


def test_fabric_product_evidence_batch_and_compatibility_registry() -> None:
    paths = evidence_paths_from_fabric_decision_data([_decision_data()])

    assert len(paths) == 1
    assert paths[0].citation_label == "Effect size"
    assert validate_fabric_compatibility_bridges() == []
