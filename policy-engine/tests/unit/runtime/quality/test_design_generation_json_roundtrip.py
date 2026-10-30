"""The real N4 receipt owner preserves its typed result across the JSON wire."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from polisyos.core import canon
from polisyos.runtime.quality import design_generation as n4

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_actual_strangle_receipts_are_json_native_without_changing_legacy_wire() -> None:
    """Every recomputed receipt is JSON-native; prior tuple encoding stays identical."""
    receipts = n4.design_generation_strangle_receipts(REPO_ROOT)
    fresh_receipts = n4.design_generation_strangle_receipts(REPO_ROOT)
    assert receipts
    assert fresh_receipts == receipts
    for receipt, fresh in zip(receipts, fresh_receipts, strict=True):
        assert receipt["verified_by"] is not fresh["verified_by"]
        restored = json.loads(json.dumps(receipt))
        assert restored == receipt
        assert canon.to_canonical_bytes(restored) == canon.to_canonical_bytes(receipt)
        # This is the sole changed container representation, not a new profile.
        legacy = {**receipt, "verified_by": tuple(receipt["verified_by"])}
        assert canon.to_canonical_bytes(legacy) == canon.to_canonical_bytes(receipt)


@pytest.mark.parametrize("status", ["preflight_rejected", "generation_unavailable"])
def test_actual_terminal_result_preserves_full_typed_json_roundtrip(status) -> None:
    """The production terminal assembler roundtrips every field without a fixture codec."""

    class UnavailableSyntheticCatalog:
        async def list_model_ids(self, *, timeout: float | None = None) -> list[str]:
            raise RuntimeError("controlled unavailable catalog; no external availability claim")

    preflight = asyncio.run(
        n4.preflight_model_profile(UnavailableSyntheticCatalog(), model_id="synthetic-unavailable")
    )
    assert preflight.status == "gateway_unavailable"
    result = n4._terminal_result(
        design_problem_ref=n4.gy_content_hash({"synthetic": "typed-json-roundtrip"}),
        model_id=preflight.model_id,
        preflight=preflight,
        status=status,
        reason=preflight.reason,
        organ="preflight",
        min_diverse_candidates=1,
    )
    assert result.strangle_receipts
    assert result.firewall_evidence
    assert n4.GenerationUnderAResult.model_validate_json(result.model_dump_json()) == result
