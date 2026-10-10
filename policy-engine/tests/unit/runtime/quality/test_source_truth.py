from __future__ import annotations

# ruff: noqa: S101
from polisyos.runtime.quality.source_truth import detect_source_truth_conflict


def test_missing_reader_value_is_a_conflict_not_an_equal_or_complete_value() -> None:
    authoritative_value = "sha256:" + "a" * 64
    conflict = detect_source_truth_conflict(
        field_family="runtime_refs",
        authoritative_source="runtime.cas",
        authoritative_surface="runtime.cas",
        authoritative_values={"decision_packet_ref": authoritative_value},
        conflicting_source="runtime.readiness_projection",
        conflicting_surface="runtime.readiness",
        conflicting_values={},
        fields=("decision_packet_ref",),
        downstream_impact="approval would otherwise proceed without the selected packet ref",
    )

    assert conflict is not None
    assert conflict["failure_code"].startswith("hds_")
    assert conflict["lost_fields"] == ["decision_packet_ref"]
    assert conflict["authoritative_ref"] == authoritative_value
    assert conflict["conflicting_ref"] is None
    assert conflict["losing_authority_record"]["lost_fields"] == ["decision_packet_ref"]
