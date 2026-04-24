from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from polisyos.ir.canon import CanonViolation
from polisyos.ir.citations import AnchorKind, CitationRef, DocumentRef, FragmentLocator
from polisyos.ir.kernel.base import ID_PATTERN
from polisyos.ir.world.claim import Claim, ClaimSourceKind
from polisyos.ir.world.doc import DocFragment, DocMeta
from polisyos.ir.world.event import (
    EventKind,
    ProvActivity,
    ProvActivityType,
    ProvAgent,
    ProvAgentType,
    WorldEvent,
    WorldObjectRef,
)
from polisyos.ir.world.ids import artifact_id_to_world_id, stable_world_id_from_canon

ARTIFACT_ID = "sha256:" + "a" * 64
ARTIFACT_ID_B = "sha256:" + "b" * 64


def _citation() -> CitationRef:
    return CitationRef(
        doc=DocumentRef(doc_id="doc.test"),
        fragment_id="frag.test",
    )


def _doc_meta_base() -> dict:
    return {
        "doc_source_id": "doc.test",
        "doc_version_id": "docv.test",
        "retrieved_at": datetime(2024, 1, 1, tzinfo=UTC),
        "mime": "text/plain",
        "license": "cc0",
        "raw_ref": ARTIFACT_ID,
    }


def _doc_fragment_base() -> dict:
    return {
        "fragment_id": "frag.test",
        "doc_version_id": "docv.test",
        "locator": FragmentLocator(
            anchor_kind=AnchorKind.PAGE,
            page_start=1,
            page_end=1,
        ),
        "text_hash": ARTIFACT_ID_B,
    }


def _claim_base() -> dict:
    return {
        "claim_id": "claim.test",
        "predicate_id": "pred.test",
        "subject_id": "entity.test",
        "value_text": "10",
        "confidence": Decimal("0.7"),
        "source_kind": ClaimSourceKind.DOC,
        "citations": [_citation()],
    }


def _agent() -> ProvAgent:
    return ProvAgent(
        agent_id="prov.agent.test",
        agent_type=ProvAgentType.SYSTEM,
        label="system",
    )


def _activity(started_at: datetime | None = None, ended_at: datetime | None = None) -> ProvActivity:
    return ProvActivity(
        activity_id="prov.activity.test",
        activity_type=ProvActivityType.FETCH_DOC,
        label="fetch",
        started_at=started_at or datetime(2024, 1, 1, tzinfo=UTC),
        ended_at=ended_at,
    )


def test_artifact_id_to_world_id_pattern() -> None:
    world_id = artifact_id_to_world_id(prefix="artifact", artifact_id=ARTIFACT_ID)
    assert world_id == "artifact.sha256_" + "a" * 64
    assert re.fullmatch(ID_PATTERN, world_id)


def test_stable_world_id_from_canon_is_deterministic() -> None:
    payload = {"a": "b"}
    first = stable_world_id_from_canon(prefix="doc", payload=payload)
    second = stable_world_id_from_canon(prefix="doc", payload=payload)
    assert first == second
    assert re.fullmatch(ID_PATTERN, first)


def test_stable_world_id_from_canon_rejects_float() -> None:
    with pytest.raises(CanonViolation):
        stable_world_id_from_canon(prefix="doc", payload={"a": 1.25})


def test_docmeta_requires_source_identity() -> None:
    payload = _doc_meta_base()
    with pytest.raises(ValidationError):
        DocMeta(**payload)


def test_docmeta_rejects_float_props() -> None:
    payload = _doc_meta_base()
    payload["canonical_url"] = "https://example.com"
    payload["props"] = {"score": 0.25}
    with pytest.raises(ValidationError):
        DocMeta(**payload)


def test_docfragment_requires_locator() -> None:
    payload = _doc_fragment_base()
    payload.pop("locator")
    with pytest.raises(ValidationError):
        DocFragment(**payload)


def test_docfragment_requires_text_hash() -> None:
    payload = _doc_fragment_base()
    payload.pop("text_hash")
    with pytest.raises(ValidationError):
        DocFragment(**payload)


def test_claim_requires_subject() -> None:
    payload = _claim_base()
    payload.pop("subject_id")
    with pytest.raises(ValidationError):
        Claim(**payload)


def test_claim_doc_requires_citations() -> None:
    payload = _claim_base()
    payload["citations"] = []
    with pytest.raises(ValidationError):
        Claim(**payload)


def test_claim_non_doc_requires_source_artifacts() -> None:
    payload = _claim_base()
    payload["source_kind"] = ClaimSourceKind.DATASET
    payload["citations"] = []
    with pytest.raises(ValidationError):
        Claim(**payload)


def test_claim_rejects_float_props() -> None:
    payload = _claim_base()
    payload["props"] = {"score": 0.5}
    with pytest.raises(ValidationError):
        Claim(**payload)


def test_claim_rejects_float_qualifiers() -> None:
    payload = _claim_base()
    payload["qualifiers"] = {"confidence": 0.5}
    with pytest.raises(ValidationError):
        Claim(**payload)


def test_worldobjectref_requires_world_or_artifact() -> None:
    with pytest.raises(ValidationError):
        WorldObjectRef()


def test_activity_end_before_start_invalid() -> None:
    started_at = datetime(2024, 1, 2, tzinfo=UTC)
    ended_at = datetime(2024, 1, 1, tzinfo=UTC)
    with pytest.raises(ValidationError):
        _activity(started_at=started_at, ended_at=ended_at)


def test_worldevent_rejects_float_parameters() -> None:
    with pytest.raises(ValidationError):
        ProvActivity(
            activity_id="prov.activity.test",
            activity_type=ProvActivityType.FETCH_DOC,
            label="fetch",
            started_at=datetime(2024, 1, 1, tzinfo=UTC),
            parameters={"score": 0.1},
        )


def test_worldevent_accepts_minimal_payload() -> None:
    event = WorldEvent(
        event_id="event.test",
        event_kind=EventKind.FETCH_DOC,
        agent=_agent(),
        activity=_activity(),
        inputs=[WorldObjectRef(artifact_id=ARTIFACT_ID)],
        outputs=[],
    )
    assert event.event_id == "event.test"
