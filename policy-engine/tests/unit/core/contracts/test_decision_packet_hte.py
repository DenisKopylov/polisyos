from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.contracts.decision_packet_hte import (
    DecisionPacketLegacyHTEPreview,
    build_decision_packet_legacy_hte_preview,
)


def _legacy_wire(name: str) -> dict[str, object]:
    repo = Path(__file__).resolve().parents[4]
    path = repo / "apps/runtime-dashboard/src/features/artifacts/domain/__test__/wire" / name
    return json.loads(path.read_text())


def test_actual_legacy_builder_wire_projects_only_limited_values() -> None:
    source = _legacy_wire("legacy-builder-wire.json")

    preview = build_decision_packet_legacy_hte_preview(source)

    assert preview.availability == "available"
    assert preview.source_result_ref == source["result_ref"]
    assert preview.ate == source["ate"]
    assert preview.bounds_meaning_status == "not_established"
    assert preview.conditional_coverage_status == "not_established"
    assert preview.population_coverage_status == "not_established"
    assert preview.authority_status == "limited_display_only"
    assert not hasattr(preview, "artifact_ref")
    assert "manifest_profile_sha256" not in preview.model_dump()


def test_legacy_parse_failure_carries_no_numeric_result() -> None:
    source = {
        "result_ref": "sha256:" + "d" * 64,
        "parse_warning": "hte_result_parse_failed",
    }

    preview = build_decision_packet_legacy_hte_preview(source)

    assert preview.availability == "unavailable"
    assert preview.ate is None
    assert preview.ate_ci_lower is None
    assert preview.ate_ci_upper is None
    assert preview.top_features == []
    assert preview.warnings == []


@pytest.mark.parametrize(
    "mutate",
    [
        lambda source: source.update(extra="not producer output"),
        lambda source: source.pop("ate"),
        lambda source: source.update(ate=float("nan")),
        lambda source: source["top_features"][0].update(extra="untyped"),
    ],
)
def test_legacy_wire_rejects_partial_nonfinite_or_unowned_fields(mutate) -> None:
    source = _legacy_wire("legacy-builder-wire.json")
    mutate(source)

    with pytest.raises(ValueError):
        build_decision_packet_legacy_hte_preview(source)


def test_limited_preview_schema_refuses_promoted_authority_or_bound_meaning() -> None:
    source = build_decision_packet_legacy_hte_preview(
        _legacy_wire("legacy-builder-wire.json")
    ).model_dump(mode="json")
    source["authority_status"] = "publishable"

    with pytest.raises(ValidationError):
        DecisionPacketLegacyHTEPreview.model_validate(source)
