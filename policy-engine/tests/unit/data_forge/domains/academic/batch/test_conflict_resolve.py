from __future__ import annotations

import json

from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig
from polisyos.data_forge.domains.academic.batch.conflict_resolve import run_conflict_resolve


def _write_jsonl(path, rows) -> None:  # type: ignore[no-untyped-def]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_conflict_resolve_detects_directional_conflict(tmp_path) -> None:
    config = AcademicBatchConfig(snapshot_root=tmp_path / "snap")
    _write_jsonl(
        config.raw_claim_candidates_final_path,
        [
            {
                "claim_id": "c1",
                "work_id": "W1",
                "cause_text": "tax_revenue",
                "effect_text": "economic.gdp_growth",
                "direction": "positive",
                "claim_extraction_confidence": 0.81,
                "publish_to_graph": True,
            },
            {
                "claim_id": "c2",
                "work_id": "W2",
                "cause_text": "tax_revenue",
                "effect_text": "economic.gdp_growth",
                "direction": "negative",
                "claim_extraction_confidence": 0.74,
                "publish_to_graph": True,
            },
        ],
    )
    metrics = run_conflict_resolve(config)

    assert metrics["claim_sets"] == 1
    assert metrics["contested_sets"] == 1
    conflict_rows = [
        json.loads(line)
        for line in config.conflict_sets_path.read_text(encoding="utf-8").splitlines()
    ]
    assert conflict_rows[0]["status"] == "contested"
    resolution_rows = [
        json.loads(line)
        for line in config.conflict_resolutions_path.read_text(encoding="utf-8").splitlines()
    ]
    assert resolution_rows[0]["runtime_support"] == "MIXED"
    claim_set_rows = [
        json.loads(line)
        for line in config.claim_sets_path.read_text(encoding="utf-8").splitlines()
    ]
    assert claim_set_rows[0]["publishable_claims"] == 0
