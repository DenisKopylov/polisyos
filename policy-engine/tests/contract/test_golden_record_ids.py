from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import to_canonical_bytes as core_to_canonical_bytes
from polisyos.fabric.provenance.core import (
    ActivityType,
    AgentType,
    EntityType,
    ProvenanceActivity,
    ProvenanceAgent,
    ProvenanceCoreGraph,
    ProvenanceEntity,
)
from polisyos.ir.canon import to_canonical_bytes as ir_to_canonical_bytes
from polisyos.ir.citations import AnchorKind, FragmentLocator
from polisyos.ir.world.event import EventKind, ProvActivity, ProvActivityType, ProvAgent, ProvAgentType
from polisyos.ir.world.ids import (
    artifact_id_to_world_id,
    claim_id_from_payload,
    conflict_set_id_from_key,
    doc_fragment_id,
    doc_source_id,
    doc_version_id_from_raw_artifact,
    quality_report_id_from_payload,
    stable_world_id_from_canon,
    trust_assessment_id_from_payload,
    world_event_id_from_payload,
)


def test_canonical_bytes_golden_records(golden_records: dict[str, object]) -> None:
    expected = golden_records["canonical_bytes"]

    simple_payload = {"alpha": 1, "beta": "hello"}
    nested_payload = {
        "threshold": Decimal("0.75"),
        "items": [Decimal("1.0"), Decimal("2.5")],
        "nested": {"z_key": 3, "a_key": 1},
    }
    dt_payload = {
        "t": datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
        "x": Decimal("1.2300"),
    }

    assert hashlib.sha256(core_to_canonical_bytes(simple_payload)).hexdigest() == expected[
        "simple_dict_sha256"
    ]
    assert hashlib.sha256(core_to_canonical_bytes(nested_payload)).hexdigest() == expected[
        "nested_decimal_sha256"
    ]
    assert hashlib.sha256(core_to_canonical_bytes(dt_payload)).hexdigest() == expected[
        "datetime_decimal_sha256"
    ]
    assert hashlib.sha256(core_to_canonical_bytes({})).hexdigest() == expected["empty_dict_sha256"]


def test_ir_and_core_canon_equivalence() -> None:
    payload = {
        "threshold": Decimal("0.75"),
        "items": [Decimal("1.0"), Decimal("2.5")],
        "nested": {"z_key": 3, "a_key": 1},
    }
    assert ir_to_canonical_bytes(payload) == core_to_canonical_bytes(payload)


def test_world_id_golden_records(golden_records: dict[str, object]) -> None:
    expected = golden_records["world_ids"]

    assert stable_world_id_from_canon(prefix="test", payload={"key": "value"}) == expected[
        "stable_world_id_test_payload"
    ]
    assert conflict_set_id_from_key(conflict_key="a" * 64) == expected["conflict_set_id_64a"]
    assert artifact_id_to_world_id(prefix="doc", artifact_id="sha256:" + "ab" * 32) == expected[
        "artifact_to_world_doc"
    ]

    claim_doc = claim_id_from_payload(
        claim_payload={
            "predicate_id": "pred.gdp",
            "subject_id": "us",
            "value_text": "100",
            "source_kind": "doc",
            "citations": [{"doc": {"doc_id": "doc.test"}, "fragment_id": "frag.test"}],
            "qualifiers": {"year": 2024},
        }
    )
    assert claim_doc == expected["claim_doc"]

    claim_dataset = claim_id_from_payload(
        claim_payload={
            "predicate_id": "pred.gdp",
            "subject_id": "us",
            "value_text": "100",
            "source_kind": "dataset",
            "source_artifacts": ["sha256:" + "b" * 64],
        }
    )
    assert claim_dataset == expected["claim_dataset"]

    assert (
        doc_source_id(canonical_url="https://example.gov/doc/1", official_id=None)
        == expected["doc_source_url"]
    )
    assert doc_version_id_from_raw_artifact(raw_artifact_id="sha256:" + "c" * 64) == expected[
        "doc_version_from_artifact"
    ]
    assert doc_fragment_id(
        doc_version_id="docv.sha256_" + "c" * 64,
        locator=FragmentLocator(anchor_kind=AnchorKind.PAGE, page_start=1, page_end=1),
        text_artifact_id="sha256:" + "d" * 64,
    ) == expected["doc_fragment"]

    event_id = world_event_id_from_payload(
        event_payload={
            "event_kind": EventKind.FETCH_DOC,
            "agent": ProvAgent(
                agent_id="prov.agent.system",
                agent_type=ProvAgentType.SYSTEM,
                label="system",
            ),
            "activity": ProvActivity(
                activity_id="prov.activity.fetch",
                activity_type=ProvActivityType.FETCH_DOC,
                label="fetch",
                started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            "inputs": [{"artifact_id": "sha256:" + "1" * 64}],
            "outputs": [{"world_id": "doc.source.us"}],
        }
    )
    assert event_id == expected["world_event"]

    trust_id = trust_assessment_id_from_payload(
        payload={
            "policy_id": "policy.tax",
            "algorithm_version": "1.0.0",
            "target_world_id": "claim.sha256_" + "2" * 64,
            "score": Decimal("0.75"),
            "tier": "high",
            "features": {"source_count": 3},
            "rationale": {"reason": "consistent"},
            "props": {},
        }
    )
    assert trust_id == expected["trust_assessment"]

    quality_id = quality_report_id_from_payload(
        payload={
            "scope": "claims_pipeline",
            "run_event_id": "event.sha256_" + "3" * 64,
            "policy_id": "policy.tax",
            "algorithm_version": "1.0.0",
            "metrics": {"claims": 10},
            "issues": [],
            "props": {},
        }
    )
    assert quality_id == expected["quality_report"]


def test_cas_golden_records(tmp_path: Path, golden_records: dict[str, object]) -> None:
    expected = golden_records["cas"]
    cas = FileSystemCAS(tmp_path)

    data = b"integrity check payload"
    ref_bytes = cas.put_bytes(data, PutOptions(kind="test", media_type="application/octet-stream"))
    assert str(ref_bytes.artifact_id) == expected["put_bytes_artifact_id"]
    assert hashlib.sha256(data).hexdigest() == expected["put_bytes_sha256"]

    obj = {"alpha": 1, "beta": [2, 3], "gamma": "hello"}
    obj_reordered = {"gamma": "hello", "beta": [2, 3], "alpha": 1}

    ref_a = cas.put_json(obj, PutOptions(kind="test", media_type="application/json"))
    ref_b = cas.put_json(obj_reordered, PutOptions(kind="test", media_type="application/json"))

    assert str(ref_a.artifact_id) == expected["put_json_artifact_id"]
    assert str(ref_b.artifact_id) == expected["put_json_reordered_artifact_id"]
    assert ref_a.artifact_id == ref_b.artifact_id


def test_world_id_hash_matches_canonical_digest() -> None:
    payload = {"subject": "test", "value": "42"}
    world_id = stable_world_id_from_canon(prefix="x", payload=payload)
    digest = hashlib.sha256(core_to_canonical_bytes(payload)).hexdigest()
    assert world_id == f"x.sha256_{digest}"


def test_provenance_stable_id_golden_record(golden_records: dict[str, object]) -> None:
    expected = golden_records["provenance"]

    graph = ProvenanceCoreGraph(graph_id="golden-graph")
    graph.add_entity(
        ProvenanceEntity(
            entity_id="raw.data",
            entity_type=EntityType.DATASET,
            label="Raw Data",
            created_at=datetime(2026, 1, 1, 10, 0, 0),
        )
    )
    graph.add_activity(
        ProvenanceActivity(
            activity_id="activity.ingest",
            activity_type=ActivityType.INGEST,
            label="Ingest",
            started_at=datetime(2026, 1, 1, 10, 5, 0),
            ended_at=datetime(2026, 1, 1, 10, 10, 0),
        )
    )
    graph.add_agent(
        ProvenanceAgent(
            agent_id="agent.system",
            agent_type=AgentType.SYSTEM,
            label="PolicyOS",
        )
    )
    graph.add_usage("activity.ingest", "raw.data")

    assert graph.compute_stable_id() == expected["stable_id"]
