from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from polisyos.fabric.world.store import (
    WorldFactError,
    append_world_segment_index,
    emit_doc_meta_facts,
    emit_edge_fact,
    emit_world_node_facts,
    load_world_fact_manifests,
    stable_world_provenance_v1,
    write_world_fact_segment,
)
from polisyos.ir.world.abi import EdgeKind, NodeKind
from polisyos.ir.world.claim import Claim, ClaimSourceKind
from polisyos.ir.world.doc import DocMeta
from polisyos.ir.world.ids import doc_source_id, doc_version_id_from_raw_artifact


def _artifact_id(value: str) -> str:
    return f"sha256:{value * 64}"


def test_emit_doc_meta_facts_idempotent_fact_ids() -> None:
    raw_ref = _artifact_id("0")
    meta_artifact_id = _artifact_id("1")
    canonical_url = "https://example.com/doc"

    meta = DocMeta(
        doc_source_id=doc_source_id(canonical_url=canonical_url, official_id=None),
        doc_version_id=doc_version_id_from_raw_artifact(raw_artifact_id=raw_ref),
        canonical_url=canonical_url,
        official_id=None,
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        mime="text/html",
        license="public",
        raw_ref=raw_ref,
    )

    provenance = stable_world_provenance_v1()
    facts1 = emit_doc_meta_facts(
        meta,
        meta_artifact_id=meta_artifact_id,
        provenance=provenance,
    )
    facts2 = emit_doc_meta_facts(
        meta,
        meta_artifact_id=meta_artifact_id,
        provenance=provenance,
    )

    ids1 = Counter(f.fact_id for f in facts1)
    ids2 = Counter(f.fact_id for f in facts2)
    assert ids1 == ids2

    def _payload_key(fact) -> tuple:
        return (
            fact.subject_id,
            fact.predicate_id,
            fact.object_value,
            fact.target_id,
            fact.valid_time,
        )

    payload1 = Counter(_payload_key(fact) for fact in facts1)
    payload2 = Counter(_payload_key(fact) for fact in facts2)
    assert payload1 == payload2


def test_emit_edge_fact_requires_target() -> None:
    provenance = stable_world_provenance_v1()
    with pytest.raises(WorldFactError):
        emit_edge_fact(
            src_id="doc.source",
            edge_kind=EdgeKind.DOC_HAS_VERSION,
            dst_id="",
            provenance=provenance,
        )


def test_claim_doc_requires_citations_contract_guardrail() -> None:
    with pytest.raises(ValidationError):
        Claim(
            claim_id="claim.test",
            predicate_id="predicate.test",
            subject_text="subject",
            value_text="value",
            confidence="0.5",
            source_kind=ClaimSourceKind.DOC,
            citations=[],
        )


def test_write_world_fact_segment_roundtrip(tmp_path: Path) -> None:
    provenance = stable_world_provenance_v1()
    facts = []
    facts.extend(
        emit_world_node_facts(
            node_id="doc.source",
            kind=NodeKind.DOC_SOURCE,
            label="Doc",
            artifact_id=None,
            props_ref=None,
            provenance=provenance,
        )
    )
    facts.extend(
        emit_world_node_facts(
            node_id="doc.version",
            kind=NodeKind.DOC_VERSION,
            label=None,
            artifact_id=_artifact_id("2"),
            props_ref=None,
            provenance=provenance,
        )
    )
    facts.append(
        emit_edge_fact(
            src_id="doc.source",
            edge_kind=EdgeKind.DOC_HAS_VERSION,
            dst_id="doc.version",
            provenance=provenance,
        )
    )

    manifest = write_world_fact_segment(
        facts,
        fact_log_root=tmp_path,
        segment_name="World Segment 1",
    )
    append_world_segment_index(manifest, fact_log_root=tmp_path)

    manifests = load_world_fact_manifests(tmp_path)
    assert len(manifests) == 1

    manifest_path = Path(manifest.path)
    df = pd.read_parquet(manifest_path)
    required_columns = {
        "fact_id",
        "schema_version",
        "subject_id",
        "predicate_id",
        "object_value",
        "target_id",
        "valid_time",
        "tx_time",
        "provenance",
        "trust",
        "legal",
    }
    assert required_columns.issubset(df.columns)
    assert manifest.row_count == len(df)

    digest = sha256(manifest_path.read_bytes()).hexdigest()
    assert manifest.sha256 == digest
