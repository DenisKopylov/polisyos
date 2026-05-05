from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from polisyos.core.observability import get_metrics, get_tracer
from polisyos.fabric.world.providers import resolve_world_observability
from polisyos.fabric.world.store import (
    WorldFactError,
    WorldSegmentError,
    WorldSegmentGCReport,
    append_world_segment_index,
    emit_doc_meta_facts,
    emit_edge_fact,
    emit_world_node_facts,
    gc_world_segments,
    load_world_fact_manifests,
    stable_world_provenance_v1,
    vacuum_world_segment_index,
    write_world_fact_segment,
)
from polisyos.ir.world.abi import EdgeKind, NodeKind
from polisyos.ir.world.claim import Claim, ClaimSourceKind
from polisyos.ir.world.doc import DocMeta
from polisyos.ir.world.ids import doc_source_id, doc_version_id_from_raw_artifact
from pydantic import ValidationError


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
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
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


def test_concurrent_world_segment_index_appends_are_not_corrupt(tmp_path: Path) -> None:
    provenance = stable_world_provenance_v1()
    facts = emit_world_node_facts(
        node_id="doc.source",
        kind=NodeKind.DOC_SOURCE,
        label="Doc",
        artifact_id=None,
        props_ref=None,
        provenance=provenance,
    )
    base_manifest = write_world_fact_segment(
        facts,
        fact_log_root=tmp_path,
        segment_name="concurrent",
    )

    def _append(index: int) -> None:
        append_world_segment_index(
            base_manifest.model_copy(update={"segment_id": f"segment.{index}"}),
            fact_log_root=tmp_path,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(_append, range(30)))

    manifests = load_world_fact_manifests(tmp_path)
    assert {manifest.segment_id for manifest in manifests} == {
        f"segment.{index}" for index in range(30)
    }


def test_append_world_segment_index_uses_injected_observability_providers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provenance = stable_world_provenance_v1()
    facts = emit_world_node_facts(
        node_id="doc.source",
        kind=NodeKind.DOC_SOURCE,
        label="Doc",
        artifact_id=None,
        props_ref=None,
        provenance=provenance,
    )
    manifest = write_world_fact_segment(
        facts,
        fact_log_root=tmp_path,
        segment_name="tenant-observable",
    ).model_copy(update={"stats": {"tenant_id": "tenant-explicit"}})

    tracer = get_tracer()
    metrics = get_metrics()
    resolved_calls: list[tuple[object | None, object | None]] = []
    monkeypatch.setattr(
        "polisyos.fabric.world.store.segments.resolve_world_observability",
        lambda **kwargs: (
            resolved_calls.append((kwargs.get("tracer"), kwargs.get("metrics")))
            or SimpleNamespace(tracer=tracer, metrics=metrics)
        ),
    )

    append_world_segment_index(
        manifest,
        fact_log_root=tmp_path,
        tracer=tracer,
        metrics=metrics,
    )

    manifests = load_world_fact_manifests(tmp_path)
    assert [item.segment_id for item in manifests] == [manifest.segment_id]
    assert resolved_calls == [(tracer, metrics)]


def test_resolve_world_observability_uses_factory_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracer = object()
    metrics = object()

    monkeypatch.setattr(
        "polisyos.fabric.world.providers._default_tracer",
        lambda: (_ for _ in ()).throw(AssertionError("global tracer should not be used")),
    )
    monkeypatch.setattr(
        "polisyos.fabric.world.providers._default_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global metrics should not be used")),
    )

    resolved = resolve_world_observability(
        tracer_factory=lambda: tracer,  # type: ignore[arg-type]
        metrics_factory=lambda: metrics,  # type: ignore[arg-type]
    )

    assert resolved.tracer is tracer
    assert resolved.metrics is metrics


def test_invalid_world_segment_index_fails_closed(tmp_path: Path) -> None:
    index_path = tmp_path / "world" / "_segments.jsonl"
    index_path.parent.mkdir(parents=True)
    index_path.write_text("{not-json}\n", encoding="utf-8")

    with pytest.raises(WorldSegmentError):
        load_world_fact_manifests(tmp_path)


def test_vacuum_world_segment_index_drops_missing_entries(tmp_path: Path) -> None:
    provenance = stable_world_provenance_v1()
    facts = emit_world_node_facts(
        node_id="doc.source",
        kind=NodeKind.DOC_SOURCE,
        label="Doc",
        artifact_id=None,
        props_ref=None,
        provenance=provenance,
    )
    manifest = write_world_fact_segment(
        facts,
        fact_log_root=tmp_path,
        segment_name="vacuum",
    )
    append_world_segment_index(manifest, fact_log_root=tmp_path)
    Path(manifest.path).unlink()

    vacuumed = vacuum_world_segment_index(tmp_path)

    assert vacuumed == []
    assert load_world_fact_manifests(tmp_path) == []


def test_gc_world_segments_keeps_latest_and_unapplied(tmp_path: Path) -> None:
    provenance = stable_world_provenance_v1()
    segment_ids: list[str] = []
    manifests = []
    for index in range(3):
        facts = emit_world_node_facts(
            node_id=f"doc.source.{index}",
            kind=NodeKind.DOC_SOURCE,
            label=f"Doc {index}",
            artifact_id=None,
            props_ref=None,
            provenance=provenance,
        )
        manifest = write_world_fact_segment(
            facts,
            fact_log_root=tmp_path,
            segment_name=f"gc_{index}",
        )
        append_world_segment_index(manifest, fact_log_root=tmp_path)
        manifests.append(manifest)
        segment_ids.append(manifest.segment_id)

    report = gc_world_segments(
        tmp_path,
        applied_segment_ids=segment_ids[:2],
        retain_latest=2,
    )

    assert isinstance(report, WorldSegmentGCReport)
    assert segment_ids[0] in report.deleted_segment_ids
    assert segment_ids[1] in report.retained_segment_ids
    assert segment_ids[2] in report.retained_segment_ids
    assert not Path(manifests[0].path).exists()
    remaining = {manifest.segment_id for manifest in load_world_fact_manifests(tmp_path)}
    assert remaining == set(report.retained_segment_ids)
