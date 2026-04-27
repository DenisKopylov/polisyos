from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.fabric.decision_data import (
    AccessRef,
    FabricDecisionData,
    FabricQuantityValue,
    LineageRef,
    QualityRef,
    ReplayRef,
    SourceContractRef,
    TemporalRef,
    TypedGap,
    UnitRef,
    fabric_claim_to_authored_text,
    fabric_event_to_authored_text,
    fabric_fact_to_quantity_value,
    to_runtime_quantity_value,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _base_envelope() -> dict[str, object]:
    return {
        "id": "fabric_decision_data:test:effect_size",
        "kind": "quantity",
        "value": FabricQuantityValue(
            point=0.23,
            unit=UnitRef(code="1", system="ucum", display="ratio"),
            semantic_type="effect_size",
            metric_id="effect_size",
        ),
        "source_contract": SourceContractRef(id="worldbank.wdi.generic", version="1.1.0"),
        "quality": QualityRef(status="passed", score=0.97, report_ref="cas://sha256/quality"),
        "lineage": LineageRef(
            id="lin_abc123",
            status="verified",
            compact_summary_ref="/api/v1/lineage/lin_abc123",
            full_graph_ref="/api/v1/lineage/lin_abc123?view=full",
            raw_evidence_refs=["cas://sha256/raw"],
            export_links={"openlineage": "/openlineage", "prov": "/prov"},
        ),
        "access": AccessRef(classification="public", pii_tier="none", redaction="none"),
        "time": TemporalRef(
            valid_at=datetime(2026, 4, 15, 12, tzinfo=UTC),
            tx_at=datetime(2026, 4, 16, 9, 20, tzinfo=UTC),
            branch="main",
        ),
        "replay": ReplayRef(status="replayable", manifest_ref="cas://sha256/replay"),
        "gaps": [],
    }


def test_fabric_decision_data_envelope_serializes_and_converts_to_runtime_quantity() -> None:
    envelope = FabricDecisionData(**_base_envelope())

    payload = envelope.model_dump(mode="json")
    assert payload["quality"]["status"] == "passed"
    assert payload["lineage"]["raw_evidence_refs"] == ["cas://sha256/raw"]
    assert payload["time"]["branch"] == "main"

    runtime_quantity = to_runtime_quantity_value(envelope)
    assert runtime_quantity.point == 0.23
    assert runtime_quantity.unit.code == "1"
    assert runtime_quantity.lineage.status == "verified"
    assert runtime_quantity.time is not None
    assert runtime_quantity.time.branch == "main"


def test_schema_snapshot_is_current_and_parseable() -> None:
    schema_path = REPO_ROOT / "schemas" / "fabric" / "trust_envelope.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["x-schema-version"] == "fabric.trust_envelope.v1"
    assert schema["title"] == "FabricDecisionData"
    assert "quality" in schema["properties"]
    assert "lineage" in schema["properties"]


@pytest.mark.parametrize(
    ("gap", "message"),
    [
        ({"status": "untraced", "reason_code": "missing_lineage"}, "owner"),
        (
            {"status": "unknown_quality", "quality_surface": "metric"},
            "remediation_link",
        ),
        ({"status": "restricted", "access_policy": "policy"}, "redaction_behavior"),
        ({"status": "non_replayable", "source_reason": "api"}, "retention_alternative"),
        ({"status": "unsupported_temporal_scope"}, "capability_endpoint"),
    ],
)
def test_typed_gap_states_require_reason_metadata(
    gap: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        TypedGap.model_validate(gap)


def test_envelope_requires_matching_gap_for_unknown_states() -> None:
    payload = _base_envelope()
    payload["lineage"] = LineageRef(
        id="lin_missing",
        status="untraced",
        reason_code="source_lineage_missing",
        owner="@fabric-owners",
    )

    with pytest.raises(ValidationError, match="matching untraced gap"):
        FabricDecisionData(**payload)

    payload["gaps"] = [
        TypedGap(
            status="untraced",
            reason_code="source_lineage_missing",
            owner="@fabric-owners",
        )
    ]
    envelope = FabricDecisionData(**payload)
    assert envelope.gaps[0].status == "untraced"


def test_temporal_ref_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        TemporalRef(valid_at=datetime(2026, 4, 15, 12))


def test_fabric_fact_event_and_claim_mapping_helpers() -> None:
    quantity = fabric_fact_to_quantity_value(
        {
            "fact_id": "world.fact.gdp",
            "value": 123.4,
            "unit": {"code": "[USD]", "system": "ucum", "display": "USD"},
            "semantic_type": "gdp",
        }
    )
    claim_text = fabric_claim_to_authored_text(
        {"claim_text": "GDP increased in the observed period.", "claim_type": "finding"}
    )
    event_text = fabric_event_to_authored_text(
        {"event_type": "snapshot", "description": "Snapshot materialized"}
    )

    assert quantity.metric_id == "world.fact.gdp"
    assert quantity.unit.code == "[USD]"
    assert claim_text.semantic_type == "finding"
    assert event_text.text == "Snapshot materialized"
