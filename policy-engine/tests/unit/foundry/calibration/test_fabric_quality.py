from __future__ import annotations

from polisyos.foundry.calibration import (
    FabricCalibrationContext,
    fabric_calibration_context_from_decision_data,
)


def test_fabric_calibration_context_caps_weight_from_quality_trust_and_staleness() -> None:
    context = fabric_calibration_context_from_decision_data(
        [
            {
                "id": "fabric_decision_data:run_123:target",
                "source_contract": {"id": "worldbank.wdi.generic"},
                "quality": {"status": "unknown_quality", "score": 0.7},
                "lineage": {
                    "id": "lin_target",
                    "trust_metadata": {"freshness": "stale"},
                },
                "access": {"classification": "public"},
                "replay": {"status": "replayable"},
                "metadata": {"source_trust_tier": "low"},
            }
        ]
    )

    assert isinstance(context, FabricCalibrationContext)
    assert context.source_contract_ids == ("worldbank.wdi.generic",)
    assert context.lineage_ids == ("lin_target",)
    assert context.min_quality_score == 0.7
    assert context.calibration_weight == 0.175
    assert context.uncertainty_inflation == 1.825
    assert context.downgrade_reasons == (
        "quality:unknown_quality",
        "source_trust:low",
        "stale_evidence",
    )


def test_fabric_calibration_context_handles_missing_evidence() -> None:
    context = fabric_calibration_context_from_decision_data([])

    assert context.calibration_weight == 0.0
    assert context.uncertainty_inflation == 2.0
    assert context.downgrade_reasons == ("fabric_evidence_missing",)
