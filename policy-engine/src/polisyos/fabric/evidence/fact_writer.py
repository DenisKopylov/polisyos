"""Public fabric fact writer module API."""

from __future__ import annotations

import json
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from polisyos.core.canon import content_hash
from polisyos.fabric.identity.segment_manifest import write_segment_manifest
from polisyos.ir.loading.fact_log import (
    Fact,
    FactLegal,
    FactProvenance,
    FactSegmentManifest,
    FactTrust,
    build_fact_id,
    utc_tx_time,
)


def _sanitize_value(value: Any) -> str | int | bool | Decimal | None:
    if value is None or (isinstance(value, float) and (pd.isna(value) or pd.isnull(value))):
        return None
    if isinstance(value, (bool, int, Decimal, str)):
        return value
    if isinstance(value, float):
        # Avoid floats in canonical JSON; store as Decimal via string.
        return Decimal(str(value))
    return str(value)


def _fact_from_payload(
    *,
    subject_id: str,
    predicate_id: str,
    object_value: Any = None,
    target_id: str | None = None,
    valid_time: Any = None,
    provenance: FactProvenance,
    trust_policy_id: str | None = None,
    legal: FactLegal | None = None,
) -> Fact:
    payload = {
        "schema_version": "1.0",
        "subject_id": subject_id,
        "predicate_id": predicate_id,
        "object_value": _sanitize_value(object_value),
        "target_id": target_id,
        "valid_time": valid_time,
        "provenance": provenance,
        "trust": FactTrust(policy_id=trust_policy_id) if trust_policy_id else None,
        "legal": legal,
    }
    fact_id = build_fact_id({k: v for k, v in payload.items() if k != "schema_version"})
    payload["tx_time"] = utc_tx_time()
    return Fact(fact_id=fact_id, **payload)


def build_fact(
    *,
    subject_id: str,
    predicate_id: str,
    object_value: Any = None,
    target_id: str | None = None,
    valid_time: Any = None,
    provenance: FactProvenance,
    trust_policy_id: str | None = None,
    legal: FactLegal | None = None,
) -> Fact:
    """Public helper to construct a Fact with deterministic fact_id."""
    return _fact_from_payload(
        subject_id=subject_id,
        predicate_id=predicate_id,
        object_value=object_value,
        target_id=target_id,
        valid_time=valid_time,
        provenance=provenance,
        trust_policy_id=trust_policy_id,
        legal=legal,
    )


def facts_from_dataframe(
    df: pd.DataFrame,
    *,
    subject_field: str,
    predicate_value_map: dict[str, str],
    provenance: FactProvenance,
    valid_time_field: str | None = None,
    target_field: str | None = None,
    trust_policy_id: str | None = None,
) -> list[Fact]:
    """Facts from dataframe helper."""
    facts: list[Fact] = []
    for _, row in df.iterrows():
        subject_id = str(row[subject_field])
        valid_time = row[valid_time_field] if valid_time_field else None
        for predicate_id, value_col in predicate_value_map.items():
            value = row.get(value_col, None)
            target_id = str(row[target_field]) if target_field else None
            fact = _fact_from_payload(
                subject_id=subject_id,
                predicate_id=predicate_id,
                object_value=value,
                target_id=target_id,
                valid_time=valid_time,
                provenance=provenance,
                trust_policy_id=trust_policy_id,
            )
            facts.append(fact)
    return facts


def _fact_to_row(fact: Fact) -> dict[str, Any]:
    return {
        "fact_id": fact.fact_id,
        "schema_version": fact.schema_version,
        "subject_id": fact.subject_id,
        "predicate_id": fact.predicate_id,
        "object_value": str(fact.object_value) if fact.object_value is not None else None,
        "target_id": fact.target_id,
        "valid_time": fact.valid_time,
        "tx_time": fact.tx_time,
        "provenance": json.dumps(fact.provenance.model_dump(mode="json", exclude_none=True)),
        "trust": json.dumps(fact.trust.model_dump(mode="json", exclude_none=True))
        if fact.trust
        else None,
        "legal": json.dumps(fact.legal.model_dump(mode="json", exclude_none=True))
        if fact.legal
        else None,
    }


def write_fact_segment(
    facts: list[Fact],
    *,
    segment_dir: Path,
    segment_name: str,
) -> FactSegmentManifest:
    """Write fact segment helper."""
    segment_dir.mkdir(parents=True, exist_ok=True)
    segment_id = f"{segment_name}_{int(time.time())}"
    segment_path = segment_dir / f"{segment_id}.parquet"
    rows = [_fact_to_row(fact) for fact in facts]
    df = pd.DataFrame(rows)
    df.to_parquet(segment_path, index=False)

    data = segment_path.read_bytes()
    digest = content_hash(data)

    time_values = [r["valid_time"] for r in rows if r["valid_time"] is not None]
    time_start = min(time_values) if time_values else None
    time_end = max(time_values) if time_values else None

    manifest = FactSegmentManifest(
        segment_id=segment_id,
        path=str(segment_path),
        row_count=len(rows),
        sha256=digest,
        time_start=time_start,
        time_end=time_end,
        stats={"columns": len(df.columns)},
    )
    manifest_path = segment_dir / f"{segment_id}_manifest.json"
    write_segment_manifest(manifest, manifest_path)
    return manifest
