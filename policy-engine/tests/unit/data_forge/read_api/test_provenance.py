from __future__ import annotations

from polisyos.data_forge.read_api import OfficialSnapshotAnswer
from polisyos.data_forge.read_api.provenance import (
    OfficialSnapshotAnswer as SurfaceOfficialSnapshotAnswer,
)


def test_provenance_read_api_exposes_official_snapshot_answer() -> None:
    answer = SurfaceOfficialSnapshotAnswer(
        status="satisfied",
        claim_id="claim:ua-msme-survival",
        requirement_id="requirement:firm-survival",
        role="official_snapshot",
        corpus_id="ua",
        snapshot_id="snapshot-20260528",
        snapshot_ref="cas://snapshot",
        data_hash="sha256:" + "a" * 64,
        creation_time="2026-05-28T00:00:00+00:00",
        lineage_refs=("manifest:ua",),
        supported_by=("firm_fundamentals",),
    )

    payload = answer.model_dump()

    assert OfficialSnapshotAnswer is SurfaceOfficialSnapshotAnswer
    assert payload["status"] == "satisfied"
    assert payload["lineage_refs"] == ("manifest:ua",)
