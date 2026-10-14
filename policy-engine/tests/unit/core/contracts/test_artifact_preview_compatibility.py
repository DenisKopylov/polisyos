from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from polisyos.core.contracts.runtime import (
    ArtifactContentPreview,
    ArtifactSchemaView,
    PredictiveCoverageDiagnosticPreview,
)

_ARTIFACT_ID = "sha256:" + "a" * 64
_PROFILE_SHA256 = "sha256:" + "b" * 64
_STATUS_VALUES = (
    "not_applicable",
    "not_evaluated",
    "declared_bytes_conformant",
    "profile_absent_unqualified_candidate",
    "declared_unknown_candidate",
)

_DIAGNOSTIC_PAYLOAD: dict[str, Any] = {
    "source_artifact_id": _ARTIFACT_ID,
    "source_manifest_profile_sha256": _PROFILE_SHA256,
    "source_schema_version": "1.0",
    "metric": "predictive_interval_coverage",
    "measurement_status": "not_measured",
    "reason_code": "no_evaluated_intervals",
    "assessment": "limited",
    "source_materialization": "reader_materialized",
    "producer_attestation_status": "not_established",
    "s10_metric_mapping_status": "not_established",
    "s10_threshold_status": "not_established",
    "issuer_status": "not_established",
    "effective_time_status": "not_established",
    "counterfactual_credibility_status": "not_established",
    "causal_effect_status": "not_established",
    "may_not_use_for": [
        "promotion",
        "publication",
        "policy_selection",
        "causal_effect_claim",
    ],
    "scenarios": [],
}

_PREVIEW_PAYLOADS: tuple[tuple[type[BaseModel], dict[str, Any]], ...] = (
    (
        ArtifactContentPreview,
        {
            "artifact_id": _ARTIFACT_ID,
            "kind": "ir.backtest_report",
            "media_type": "application/json",
            "mode": "json",
            "size_bytes": 10,
            "max_bytes": 100,
        },
    ),
    (
        ArtifactSchemaView,
        {
            "artifact_id": _ARTIFACT_ID,
            "kind": "ir.backtest_report",
            "media_type": "application/json",
        },
    ),
    (PredictiveCoverageDiagnosticPreview, _DIAGNOSTIC_PAYLOAD),
)


@pytest.mark.parametrize(("model_type", "payload"), _PREVIEW_PAYLOADS)
def test_legacy_status_omission_maps_to_nonqualifying_status(
    model_type: type[BaseModel], payload: dict[str, Any]
) -> None:
    parsed = model_type.model_validate(payload)

    assert parsed.canon_read_status == "not_evaluated"
    assert parsed.model_dump(mode="json")["canon_read_status"] == "not_evaluated"

    schema = model_type.model_json_schema()
    assert "canon_read_status" not in schema.get("required", [])
    status_schema = schema["properties"]["canon_read_status"]
    assert "null" not in json.dumps(status_schema)

    for status in _STATUS_VALUES:
        with_status = model_type.model_validate({**payload, "canon_read_status": status})
        assert with_status.model_dump(mode="json").get("canon_read_status") == status
        assert with_status.model_dump(mode="json")["canon_read_status"] == status

    with pytest.raises(ValidationError):
        model_type.model_validate({**payload, "canon_read_status": None})
    with pytest.raises(ValidationError):
        model_type.model_validate({**payload, "canon_read_status": "unrecognized"})


def test_current_content_producer_still_supplies_a_computed_status() -> None:
    preview = ArtifactContentPreview(
        artifact_id=_ARTIFACT_ID,
        manifest_profile_sha256=_PROFILE_SHA256,
        kind="ir.backtest_report",
        media_type="application/json",
        mode="json",
        canon_read_status="declared_bytes_conformant",
        size_bytes=10,
        max_bytes=100,
    )

    assert preview.model_dump(mode="json")["canon_read_status"] == "declared_bytes_conformant"
