from __future__ import annotations

import pytest

from polisyos.runtime.quality.workspace.foundry_consumption import (
    ConstraintStoreIngestor,
    evaluate_constraint_store_for_phase2,
)


def test_governed_requirement_artifacts_become_constraint_store_entries() -> None:
    snapshot = ConstraintStoreIngestor().ingest(
        snapshot_id="constraint-store-phase2",
        grammar_expansion_ref="pdc://phase2/grammar",
        artifacts=[
            {
                "artifact_ref": "obligation://legal-authority",
                "source_kind": "obligation",
                "status": "block",
                "consumer_ref": "ESTIMATE",
                "reason": "Legal authority must be verified.",
            },
            {
                "artifact_ref": "participation://affected-firms",
                "source_kind": "participation_requirement",
                "status": "limit",
                "consumer_ref": "SIMULATE",
                "reason": "Affected firms were not sampled.",
            },
            {
                "artifact_ref": "method-requirement://causal-identification",
                "source_kind": "method_requirement",
                "status": "block",
                "consumer_ref": "VERIFY",
                "reason": "Identification method required.",
            },
        ],
    )

    assert len(snapshot.constraint_records) == 3
    assert set(snapshot.hard_constraint_ids) >= {
        "phase2.obligation.legal-authority",
        "phase2.method_requirement.causal-identification",
    }
    assert snapshot.governance_owned_gap_ids == [
        "phase2.obligation.legal-authority",
        "phase2.method_requirement.causal-identification",
    ]


def test_constraint_ingestor_rejects_free_text_inferred_constraints() -> None:
    with pytest.raises(ValueError, match="governed artifact"):
        ConstraintStoreIngestor().ingest(
            snapshot_id="constraint-store-phase2",
            grammar_expansion_ref="pdc://phase2/grammar",
            artifacts=[
                {
                    "text": "probably needs public consultation",
                    "source_kind": "free_text",
                    "status": "block",
                    "consumer_ref": "VERIFY",
                    "reason": "inferred",
                }
            ],
        )


def test_constraint_store_snapshot_is_consumed_by_phase2_authority_gate() -> None:
    snapshot = ConstraintStoreIngestor().ingest(
        snapshot_id="constraint-store-phase2",
        grammar_expansion_ref="pdc://phase2/grammar",
        artifacts=[
            {
                "artifact_ref": "obligation://legal-authority",
                "source_kind": "obligation",
                "status": "block",
                "consumer_ref": "VERIFY",
                "reason": "Legal authority must be verified.",
            },
            {
                "artifact_ref": "participation://affected-firms",
                "source_kind": "participation_requirement",
                "status": "limit",
                "consumer_ref": "ESTIMATE",
                "reason": "Affected firms were not sampled.",
            },
        ],
    )

    decision = evaluate_constraint_store_for_phase2(snapshot)

    assert decision.blocks_promotion is True
    assert decision.downgrades_authority is True
    assert decision.blocking_constraint_ids == ["phase2.obligation.legal-authority"]
    assert decision.limiting_constraint_ids == ["phase2.participation_requirement.affected-firms"]
