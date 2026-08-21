from __future__ import annotations

import pytest
from polisyos.runtime.http.services.cycle_board_projection import (
    CycleBoardReplayConflictError,
)

from polisyos.runtime.http.services.governed_projections import ProjectionId
from tests.unit.runtime.http.test_cycle_board_projection_service import (
    _component_packets,
    _service,
)


def test_replay_versions_require_complete_unmixed_pin_tuples() -> None:
    service, raw, _ = _service()
    raw_packet = raw.packets[ProjectionId.DEPTH_N_CYCLE_BOARD]

    raw_replay = service.get(
        replay_target="raw_v1",
        artifact_content_hash=raw_packet.source.artifact_content_hash,
        projection_hash=raw_packet.projection_hash,
        source_dependency_hash=raw_packet.source_dependency_hash,
        source_as_of=raw_packet.as_of,
    )
    assert raw_replay.model_dump_json() == raw_packet.model_dump_json()
    assert raw.calls == [
        (
            ProjectionId.DEPTH_N_CYCLE_BOARD,
            {
                "artifact_content_hash": raw_packet.source.artifact_content_hash,
                "projection_hash": raw_packet.projection_hash,
                "source_dependency_hash": raw_packet.source_dependency_hash,
                "source_as_of": raw_packet.as_of,
            },
        )
    ]
    with pytest.raises(CycleBoardReplayConflictError):
        service.get(
            replay_target="raw_v1",
            artifact_content_hash=raw_packet.source.artifact_content_hash,
            projection_hash=f"sha256:{'0' * 64}",
            source_dependency_hash=raw_packet.source_dependency_hash,
            source_as_of=raw_packet.as_of,
        )

    current = service.get()
    composed_replay = service.get(
        replay_target="composed_v2",
        projection_rule_version=current.projection_rule_version,
        composition_manifest_hash=current.composition_manifest_hash,
        projection_hash=current.projection_hash,
        source_dependency_hash=current.source_dependency_hash,
    )
    assert composed_replay == current

    invalid_pin_sets = (
        {"projection_hash": current.projection_hash},
        {
            "replay_target": "raw_v1",
            "artifact_content_hash": raw_packet.source.artifact_content_hash,
        },
        {
            "replay_target": "composed_v2",
            "projection_rule_version": current.projection_rule_version,
            "composition_manifest_hash": current.composition_manifest_hash,
            "projection_hash": current.projection_hash,
        },
        {
            "replay_target": "composed_v2",
            "projection_rule_version": current.projection_rule_version,
            "composition_manifest_hash": current.composition_manifest_hash,
            "projection_hash": current.projection_hash,
            "source_dependency_hash": current.source_dependency_hash,
            "artifact_content_hash": raw_packet.source.artifact_content_hash,
        },
    )
    for pins in invalid_pin_sets:
        with pytest.raises(CycleBoardReplayConflictError):
            service.get(**pins)

    changed_service, _, _ = _service(
        packets=_component_packets(readiness_reason="different typed absence")
    )
    changed = changed_service.get()
    assert changed.composition_manifest_hash != current.composition_manifest_hash
    assert changed.source_dependency_hash != current.source_dependency_hash
    assert changed.projection_hash != current.projection_hash
    with pytest.raises(CycleBoardReplayConflictError):
        changed_service.get(
            replay_target="composed_v2",
            projection_rule_version=current.projection_rule_version,
            composition_manifest_hash=current.composition_manifest_hash,
            projection_hash=current.projection_hash,
            source_dependency_hash=current.source_dependency_hash,
        )
