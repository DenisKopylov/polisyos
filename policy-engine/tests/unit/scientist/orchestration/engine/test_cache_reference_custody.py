"""Resolve exact manifest views through real cache seeding and replay consumers."""

from __future__ import annotations

import json

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.orchestration.engine.idempotency import (
    REPLAY_EPOCH,
    NodeCacheEntry,
    NodeResultCache,
    _build_journal_proof,
)
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.engine.state_merge import merge_parallel_outcomes


class ReadCountingCAS(FileSystemCAS):
    def __init__(self, root):
        super().__init__(root)
        self.entry_reads: list[ArtifactRef | str] = []

    def get_bytes(self, ref):
        if self.get_manifest(ref).kind == "scientist.node_cache_entry":
            self.entry_reads.append(ref)
        return super().get_bytes(ref)


def publish(store, *, key="a" * 64, value=4):
    state = branch_state(
        ExperimentState(run_id="R_view", params={"same": 4, "unrelated": "old"}),
        write_paths=("params",),
    ).state
    state.params["same"] = value
    cache = NodeResultCache(store, "R_view")
    return cache.put(key, "scientist.view_consumer@1.0.0", NodeOutcome(status="ok", state=state))


def alternate_view(store, ref):
    payload = from_canonical_bytes(store.get_bytes(ref))
    manifest = store.get_manifest(ref)
    alternate = store.put_json(
        payload,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=ProducerInfo(component="foreign.producer", version="1.0.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    assert alternate.artifact_id == ref.artifact_id
    assert alternate.manifest_profile_sha256 != ref.manifest_profile_sha256
    assert store.verify(alternate).ok
    assert store.get_manifest(alternate).producer.component == "foreign.producer"
    assert store.get_manifest(ref).producer.component == "scientist.engine.idempotency"
    return alternate


@pytest.mark.parametrize("inlet", ["trace", "checkpoint"])
def test_seed_rejects_valid_foreign_manifest_view_without_default_fallback(tmp_path, inlet):
    store = FileSystemCAS(tmp_path / "cas")
    ref = publish(store)
    alternate = alternate_view(store, ref)
    # A fresh filesystem store must resolve the offered profile, including
    # its producer epoch, rather than a cached/default manifest for the blob.
    reopened = FileSystemCAS(tmp_path / "cas")
    cache = NodeResultCache(reopened, "R_view")
    if inlet == "trace":
        trace = tmp_path / "trace.jsonl"
        trace.write_text(
            json.dumps(
                {
                    "event": "NODE_CACHE_STORE",
                    "refs": {"outputs": [alternate.model_dump(mode="json")]},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        restored = cache.seed_from_trace(trace)
    else:
        restored = cache.seed_from_entry_refs([alternate])
    assert restored == 0
    assert cache.get("a" * 64) is None
    assert cache.load_entry(ref)
    outcome = cache.get("a" * 64)
    assert outcome is not None
    merged = merge_parallel_outcomes(
        ExperimentState(run_id="R_view", params={"same": 9, "unrelated": "new"}),
        {"compute": outcome},
        {"compute": ["params"]},
    )
    assert merged.applied
    assert merged.state.params == {"same": 4, "unrelated": "new"}


def test_verified_default_does_not_dedupe_a_distinct_foreign_view(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    ref = publish(store)
    alternate = alternate_view(store, ref)
    cache = NodeResultCache(FileSystemCAS(tmp_path / "cas"), "R_view")
    assert cache.load_entry(ref)
    with pytest.raises(ValueError, match="immutable_epoch_mismatch"):
        cache.load_entry(alternate)
    assert cache.get("a" * 64) is not None


def test_successful_full_ref_dedupe_does_not_skip_another_entry(tmp_path):
    store = ReadCountingCAS(tmp_path / "cas")
    first = publish(store)
    second = publish(store, key="b" * 64, value=8)
    store.entry_reads.clear()
    cache = NodeResultCache(store, "R_view")
    assert cache.seed_from_entry_refs([first] * 100 + [second]) == 2
    assert len(store.entry_reads) == 2
    assert cache.get("a" * 64).state.params["same"] == 4
    assert cache.get("b" * 64).state.params["same"] == 8


def test_legacy_outcome_ref_keeps_its_selected_manifest_view(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    state = branch_state(ExperimentState(run_id="R_view"), write_paths=()).state
    producer = ProducerInfo(component="scientist.engine.idempotency", version="1.0.0")
    outcome_ref = store.put_json(
        NodeOutcome(status="ok", state=state).model_dump(mode="python"),
        PutOptions(
            kind="scientist.node_outcome",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.NodeOutcome", version="1.0"
            ),
            producer=producer,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    offered_outcome = alternate_view(store, outcome_ref)
    schema = SchemaInfo(
        name="polisyos.scientist.orchestration.engine.NodeCacheEntry", version="1.0"
    )
    entry = NodeCacheEntry(
        schema_version="1.0",
        run_id="R_view",
        node_id="scientist.view_consumer@1.0.0",
        idempotency_key="c" * 64,
        outcome_ref=offered_outcome,
        state_mutations_version="1.0",
        replay_epoch=REPLAY_EPOCH,
    )
    entry = entry.model_copy(
        update={
            "journal_proof": _build_journal_proof(
                entry, manifest_schema=schema, manifest_producer=producer
            )
        }
    )
    entry_ref = store.put_json(
        entry.model_dump(mode="python", exclude_none=False),
        PutOptions(
            kind="scientist.node_cache_entry",
            media_type="application/json",
            schema=schema,
            producer=producer,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    cache = NodeResultCache(FileSystemCAS(tmp_path / "cas"), "R_view")
    with pytest.raises(ValueError, match="immutable_epoch_mismatch"):
        cache.load_entry(entry_ref)
    assert cache.get("c" * 64) is None
