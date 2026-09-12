"""Synthetic custody rows bound into the committed posture fixture, without source reads."""

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from polisyos.scientist.evidence.claims.posture import CUSTODY_APPOINTMENT_CONTRACT

ROOT = Path(__file__).resolve().parents[2]
VECTORS = json.loads((ROOT / "tests/fixtures/common/markdown_table_rows.json").read_text())


def rebound_register(subject: str) -> dict[str, Any]:
    """Replace each custody row with synthetic content and rebind its exact bytes."""
    payload = json.loads(
        (ROOT / "apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json").read_bytes()
    )
    custody = next(
        row for row in payload["claims"] if row["subject"] == "universal_custody_commitment"
    )
    for source in payload["custody_appointment_sources"]:
        debt_id = source["debt_id"]
        owner, command = CUSTODY_APPOINTMENT_CONTRACT[debt_id]
        source["source_content"] = (
            f"| `{debt_id}` | {subject} | `{owner}` | `{source['status']}` | `{command}` |"
        )
        bind_source(payload, source, custody=custody)
    rebind_payload(payload)
    return payload


def bind_source(payload: dict[str, Any], source: dict[str, Any], *, custody: Any = None) -> None:
    """Bind synthetic source text and its owning claim to the same byte digest."""
    source["content_digest"] = "sha256:" + sha256(source["source_content"].encode()).hexdigest()
    if custody is None:
        custody = next(
            row for row in payload["claims"] if row["subject"] == "universal_custody_commitment"
        )
    binding = next(
        item
        for item in custody["source_bindings"]
        if item["prerequisite_refs"] == [source["debt_id"]]
    )
    binding["owner"]["source_ref"] = (
        f"{source['path']}#{source['debt_id']}@{source['content_digest']}"
    )


def rebind_payload(payload: dict[str, Any]) -> None:
    """Keep envelope digest valid so the custody owner must assess each mutation."""
    encoded = json.dumps(
        {k: v for k, v in payload.items() if k != "payload_digest"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    payload["payload_digest"] = "sha256:" + sha256(encoded.encode()).hexdigest()
