"""Single verification chokepoint for claim-publishability consumers."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from polisyos.data_forge.domains.academic.batch.claim_adjudicator import (
    load_admitted_claim_adjudication_batch,
)

if TYPE_CHECKING:
    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig


def _compatibility_rows(config: AcademicBatchConfig) -> list[dict[str, Any]]:
    if not config.claim_adjudications_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        config.claim_adjudications_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(
                f"claim adjudication compatibility row {line_number} must be an object"
            )
        rows.append(payload)
    return rows


def load_verified_claim_adjudication_rows(
    config: AcademicBatchConfig,
) -> dict[str, dict[str, Any]]:
    """Return result rows only when CAS authority and projection bytes agree."""
    if not config.claim_adjudication_result_ref_path.exists():
        if _compatibility_rows(config):
            raise ValueError("unreceipted claim adjudication compatibility rows")
        return {}

    batch, result_ref = load_admitted_claim_adjudication_batch(config)
    receipt_id = str(result_ref.artifact_id)
    expected_rows = [
        {
            **result.model_dump(mode="json"),
            "adjudication_receipt_id": receipt_id,
            "authority_rule_version": batch.rule_version,
        }
        for result in batch.results
    ]
    projected_rows = _compatibility_rows(config)
    if projected_rows and projected_rows != expected_rows:
        raise ValueError("claim adjudication compatibility projection differs from receipt")
    return {str(row["claim_id"]): row for row in expected_rows}


__all__ = ["load_verified_claim_adjudication_rows"]
