from __future__ import annotations

import hashlib
import json
from pathlib import Path

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.scholar import BudgetsV1, ResearchIntent, SourceSpec, ThresholdsV1
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.world.materialize import materialize_world_duckdb_from_fact_log
from polisyos.ir.world.trust import TrustTier
from polisyos.scholar.api import enrich_topic


def _load_json_artifact(cas: FileSystemCAS, artifact_id: str) -> dict:
    payload = json.loads(cas.get_bytes(ArtifactID.model_validate(artifact_id)))
    assert isinstance(payload, dict)
    return payload


def _query_count(db: SimulationDB, sql: str) -> int:
    row = db.conn.execute(sql).fetchone()
    assert row is not None
    return int(row[0])


def test_scholar_phase15_mvp_end_to_end_and_determinism(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))

    raw_bytes = b"\n".join(
        [
            b"claim: policy.tax_rate = 20 [percent]",
            b"claim: policy.tax_rate = 25 [percent]",
        ]
    )
    source_locator = f"bytes.sha256_{hashlib.sha256(raw_bytes).hexdigest()}"

    intent = ResearchIntent(
        domain="tax",
        jurisdictions=["US"],
        seed_sources=[
            SourceSpec(
                kind="bytes",
                source_locator=source_locator,
                license="public",
                mime_hint="text/plain",
                props={
                    "source_type": "test",
                    "jurisdiction": "US",
                    "language": "en",
                },
                data=raw_bytes,
            )
        ],
        claim_targets=["policy.tax_rate"],
        budgets_v1=BudgetsV1(
            max_docs=4,
            max_bytes_total=1_000_000,
            max_claims_total=1_000,
        ),
        thresholds_v1=ThresholdsV1(min_doc_trust_tier=TrustTier.LOW),
    )

    result_1 = enrich_topic(cas=cas, fact_log_root=tmp_path, intent=intent)
    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    assert _query_count(db, "SELECT COUNT(*) FROM world.doc_sources") == 1
    assert _query_count(db, "SELECT COUNT(*) FROM world.doc_versions") == 1
    assert _query_count(db, "SELECT COUNT(*) FROM world.doc_fragments") > 0

    assert _query_count(db, "SELECT COUNT(*) FROM world.claims") > 0
    assert _query_count(db, "SELECT COUNT(*) FROM world.claim_citations") > 0

    assert _query_count(db, "SELECT COUNT(*) FROM world.conflict_sets") >= 1
    assert _query_count(db, "SELECT COUNT(*) FROM world.conflict_members") >= 2
    assert (
        _query_count(
            db,
            "SELECT COUNT(*) FROM world.world_edges WHERE kind='conflict.resolves_to'",
        )
        >= 1
    )

    assert _query_count(db, "SELECT COUNT(*) FROM world.trust_assessments") > 0

    cas.get_manifest(result_1.knowledge_bundle_ref.artifact_id)
    bundle_payload_1 = _load_json_artifact(
        cas,
        str(result_1.knowledge_bundle_ref.artifact_id),
    )
    assert bundle_payload_1["bundle_id"] == result_1.bundle_id
    assert bundle_payload_1["doc_version_ids"]
    assert bundle_payload_1["claim_ids"]
    assert bundle_payload_1["conflict_set_ids"]

    doc_versions_before = _query_count(db, "SELECT COUNT(*) FROM world.doc_versions")
    claims_before = _query_count(db, "SELECT COUNT(*) FROM world.claims")
    events_before = _query_count(db, "SELECT COUNT(*) FROM world.world_events")

    result_2 = enrich_topic(cas=cas, fact_log_root=tmp_path, intent=intent)
    assert result_2.bundle_id == result_1.bundle_id

    bundle_payload_2 = _load_json_artifact(
        cas,
        str(result_2.knowledge_bundle_ref.artifact_id),
    )
    assert bundle_payload_2["doc_version_ids"] == bundle_payload_1["doc_version_ids"]
    assert set(bundle_payload_2["claim_ids"]) == set(bundle_payload_1["claim_ids"])

    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    doc_versions_after = _query_count(db, "SELECT COUNT(*) FROM world.doc_versions")
    claims_after = _query_count(db, "SELECT COUNT(*) FROM world.claims")
    events_after = _query_count(db, "SELECT COUNT(*) FROM world.world_events")

    assert doc_versions_after == doc_versions_before
    assert claims_after == claims_before
    assert events_after > events_before
