from __future__ import annotations

from polisyos.foundry.uncertainty import (
    FabricUncertaintyContext,
    fabric_uncertainty_context_from_decision_data,
)


def test_fabric_uncertainty_context_inflates_for_failed_stale_non_replayable_data() -> None:
    context = fabric_uncertainty_context_from_decision_data(
        [
            {
                "id": "fabric_decision_data:run_123:quantity",
                "source_contract": {"id": "worldbank.wdi.generic"},
                "quality": {"status": "failed", "score": 0.4},
                "lineage": {
                    "id": "lin_quantity",
                    "trust_metadata": {"freshness": "stale"},
                },
                "access": {"classification": "public"},
                "replay": {"status": "non_replayable"},
            }
        ]
    )

    assert isinstance(context, FabricUncertaintyContext)
    assert context.inflation_factor == 1.8
    assert context.reasons == (
        "non_replayable",
        "quality:failed",
        "stale_evidence",
    )
