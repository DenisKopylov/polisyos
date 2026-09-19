"""Idempotency hashing and cache-entry helpers for repeat-safe Scientist node execution."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.common.logger import get_logger
from polisyos.common.serialization import to_python_data
from polisyos.common.timestamps import utc_now
from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo, SchemaInfo
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.cache import LRUCache
from polisyos.core.canon import CanonSpec, content_hash, from_canonical_bytes, to_canonical_bytes
from polisyos.scientist.orchestration.engine.protocol import (
    NodeOutcome,
    NodeSpec,
    OutputAwareNodeOutcome,
    decode_node_outcome,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import (
    StateMutation,
    StateMutationJournal,
    mutation_journal_for_state,
    mutation_journal_from_operations,
)

logger = get_logger(__name__)

IDEMPOTENCY_CONTRACT_VERSION = "1.0"
NODE_CACHE_ENTRY_SCHEMA_VERSION = "1.0"
STATE_MUTATIONS_VERSION = "1.0"
REPLAY_EPOCH = "2.0"

_IDEM_CANON = CanonSpec(
    name="polisyos.idempotency.canon",
    version=IDEMPOTENCY_CONTRACT_VERSION,
    forbid_floats=False,
    sort_keys=True,
)


class JournalProof(BaseModel):
    """Producer-issued hash binding a mutation journal to its cache manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    replay_epoch: str = Field(pattern=r"^\d+\.\d+$")
    payload_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    manifest_schema: SchemaInfo
    manifest_producer: ProducerInfo


_CACHE_ENTRY_SCHEMA = SchemaInfo(
    name="polisyos.scientist.orchestration.engine.NodeCacheEntry",
    version=NODE_CACHE_ENTRY_SCHEMA_VERSION,
)
_JOURNAL_PROOF_CANON = CanonSpec(
    name="polisyos.scientist.orchestration.engine.journal-proof",
    version="1.0",
    forbid_floats=False,
)


class NodeCacheEntry(BaseModel):
    """Artifact record linking a run-scoped idempotency key to a cached node outcome."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=NODE_CACHE_ENTRY_SCHEMA_VERSION, pattern=r"^\d+\.\d+$")
    run_id: str
    node_id: str
    idempotency_key: str = Field(..., min_length=64, max_length=64)
    outcome_ref: ArtifactRef
    state_mutations: tuple[StateMutation, ...] = Field(default_factory=tuple)
    state_mutations_version: str | None = Field(default=None, pattern=r"^\d+\.\d+$")
    replay_epoch: str | None = Field(default=None, pattern=r"^\d+\.\d+$")
    journal_proof: JournalProof | None = None
    created_at: datetime = Field(default_factory=lambda: utc_now(drop_microseconds=True))


def _cache_producer(*, output_aware: bool) -> ProducerInfo:
    return ProducerInfo(
        component="scientist.engine.idempotency",
        version="2.0.0" if output_aware else "1.0.0",
    )


def _journal_payload(entry: NodeCacheEntry) -> dict[str, Any]:
    return entry.model_dump(
        mode="python",
        by_alias=True,
        exclude_none=False,
        exclude={"journal_proof"},
    )


def _journal_proof_hash(
    entry: NodeCacheEntry,
    *,
    manifest_schema: SchemaInfo,
    manifest_producer: ProducerInfo,
) -> str:
    material = {
        "replay_epoch": entry.replay_epoch,
        "entry": _journal_payload(entry),
        "manifest_schema": manifest_schema,
        "manifest_producer": manifest_producer,
    }
    return content_hash(
        to_canonical_bytes(material, _JOURNAL_PROOF_CANON),
        prefix=True,
    )


def _build_journal_proof(
    entry: NodeCacheEntry,
    *,
    manifest_schema: SchemaInfo,
    manifest_producer: ProducerInfo,
) -> JournalProof:
    return JournalProof(
        replay_epoch=REPLAY_EPOCH,
        payload_hash=_journal_proof_hash(
            entry,
            manifest_schema=manifest_schema,
            manifest_producer=manifest_producer,
        ),
        manifest_schema=manifest_schema,
        manifest_producer=manifest_producer,
    )


def _resolve_path(state: ExperimentState, path: str) -> Any:
    parts = path.split(".")
    current: Any = state
    for part in parts:
        if isinstance(current, BaseModel):
            current = getattr(current, part, None)
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def extract_state_slice(
    state: ExperimentState,
    state_reads: list[str],
) -> dict[str, Any]:
    """Capture the declared state-read paths that participate in a node idempotency hash."""
    slice_data: dict[str, Any] = {}
    for read_path in sorted(state_reads):
        value = _resolve_path(state, read_path)
        slice_data[read_path] = to_python_data(value, sort_keys=True)
    return slice_data


def _normalize_bind_params(bind_params: dict[str, Any] | None) -> dict[str, Any]:
    params = bind_params or {}
    return {k: to_python_data(v, sort_keys=True) for k, v in sorted(params.items())}


def compute_idempotency_payload(
    spec: NodeSpec,
    state: ExperimentState,
    bind_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical payload hashed to decide whether a node execution can be reused."""
    return {
        "contract_version": IDEMPOTENCY_CONTRACT_VERSION,
        "scope": "run",
        "run_id": state.run_id,
        "node_id": str(spec.metadata.component_id),
        "state_reads_snapshot": extract_state_slice(state, spec.state_reads),
        "bind_params": _normalize_bind_params(bind_params),
    }


def compute_idempotency_key(
    spec: NodeSpec,
    state: ExperimentState,
    bind_params: dict[str, Any] | None = None,
) -> str:
    """Hash the canonical idempotency payload for cache lookup and replay bookkeeping."""
    payload = compute_idempotency_payload(spec=spec, state=state, bind_params=bind_params)
    canonical = to_canonical_bytes(payload, _IDEM_CANON)
    return content_hash(canonical)


class NodeResultCache:
    """Node result cache public type."""

    def __init__(
        self,
        store: ArtifactStore,
        run_id: str,
        *,
        max_entries: int | None = None,
    ) -> None:
        self._store = store
        self._run_id = run_id
        self._max_entries = max_entries
        self._index: LRUCache[str, ArtifactRef] = LRUCache(max_size=max_entries)
        self._mutation_journals: dict[str, StateMutationJournal] = {}

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def size(self) -> int:
        return len(self._index)

    def has(self, key: str) -> bool:
        return key in self._index

    def discard(self, key: str) -> None:
        """Evict one cache key and its replay contract."""
        self._index.delete(key)
        self._mutation_journals.pop(key, None)

    def clear(self) -> None:
        self._index.clear()
        self._mutation_journals.clear()

    def prune(self, max_entries: int) -> int:
        removed = self._index.prune(max_entries)
        active_keys = set(self._index.keys())
        for key in tuple(self._mutation_journals):
            if key not in active_keys:
                del self._mutation_journals[key]
        return removed

    def _verify_cache_artifact(
        self,
        ref: ArtifactRef,
        *,
        output_aware: bool,
        entry: bool = False,
    ) -> None:
        """Read back the actual immutable cache epoch, including reused CAS bytes."""
        if not self._store.verify(ref.artifact_id).ok:
            raise ValueError("cache_custody: artifact_integrity_failed")
        manifest = self._store.get_manifest(ref.artifact_id)
        kind = "scientist.node_cache_entry" if entry else "scientist.node_outcome"
        schema_name = (
            "NodeCacheEntry"
            if entry
            else ("OutputAwareNodeOutcome" if output_aware else "NodeOutcome")
        )
        expected_schema = SchemaInfo(
            name=f"polisyos.scientist.orchestration.engine.{schema_name}", version="1.0"
        )
        expected_producer = _cache_producer(output_aware=output_aware)
        if (
            ref.kind != kind
            or ref.media_type != "application/json"
            or manifest.kind != kind
            or manifest.media_type != "application/json"
            or manifest.artifact_schema != expected_schema
            or manifest.producer != expected_producer
        ):
            raise ValueError("cache_custody: immutable_epoch_mismatch")

    def _verify_output_aware_cache_artifact(
        self,
        ref: ArtifactRef,
        *,
        entry: bool = False,
    ) -> None:
        """Read back an output-aware cache artifact under its immutable epoch."""
        try:
            self._verify_cache_artifact(ref, output_aware=True, entry=entry)
        except ValueError as exc:
            raise ValueError(f"output_aware_cache_custody: {exc}") from exc

    def get(self, key: str) -> NodeOutcome | None:
        outcome_ref = self._index.get(key)
        if outcome_ref is None:
            return None
        if key not in self._mutation_journals:
            # A cache entry without a proven operation contract is historical
            # evidence only; replay it as a miss so the node can re-execute.
            self.discard(key)
            return None
        try:
            payload = from_canonical_bytes(self._store.get_bytes(outcome_ref.artifact_id))
            outcome = decode_node_outcome(payload)
            if isinstance(outcome, OutputAwareNodeOutcome):
                self._verify_output_aware_cache_artifact(outcome_ref)
            object.__setattr__(
                outcome.state,
                "_polisyos_state_mutation_journal",
                self._mutation_journals[key],
            )
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            logger.debug(
                "Cache miss for key %s, evicting: %s",
                key,
                exc,
            )
            self.discard(key)
            return None
        return outcome

    def put(self, key: str, node_id: str, outcome: NodeOutcome) -> ArtifactRef:
        output_aware = isinstance(outcome, OutputAwareNodeOutcome)
        outcome_schema = "OutputAwareNodeOutcome" if output_aware else "NodeOutcome"
        outcome_schema_info = SchemaInfo(
            name=f"polisyos.scientist.orchestration.engine.{outcome_schema}", version="1.0"
        )
        cache_producer = _cache_producer(output_aware=output_aware)
        journal = mutation_journal_for_state(outcome.state)
        state_mutations = tuple(journal.operations) if journal is not None else ()
        outcome_ref = self._store.put_json(
            outcome.model_dump(mode="python", by_alias=True, exclude_none=False),
            PutOptions(
                kind="scientist.node_outcome",
                media_type="application/json",
                schema=outcome_schema_info,
                producer=cache_producer,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        if output_aware:
            self._verify_output_aware_cache_artifact(outcome_ref)
        else:
            self._verify_cache_artifact(outcome_ref, output_aware=False)
        entry_without_proof = NodeCacheEntry(
            run_id=self._run_id,
            node_id=node_id,
            idempotency_key=key,
            outcome_ref=outcome_ref,
            state_mutations=state_mutations,
            state_mutations_version=STATE_MUTATIONS_VERSION if journal is not None else None,
            replay_epoch=REPLAY_EPOCH if journal is not None else None,
        )
        entry = (
            entry_without_proof.model_copy(
                update={
                    "journal_proof": _build_journal_proof(
                        entry_without_proof,
                        manifest_schema=_CACHE_ENTRY_SCHEMA,
                        manifest_producer=cache_producer,
                    )
                }
            )
            if journal is not None
            else entry_without_proof
        )
        entry_ref = self._store.put_json(
            entry.model_dump(mode="python", by_alias=True, exclude_none=False),
            PutOptions(
                kind="scientist.node_cache_entry",
                media_type="application/json",
                schema=_CACHE_ENTRY_SCHEMA,
                producer=cache_producer,
            ),
        )
        if output_aware:
            self._verify_output_aware_cache_artifact(entry_ref, entry=True)
        else:
            self._verify_cache_artifact(entry_ref, output_aware=False, entry=True)
        if journal is not None:
            self._index.set(key, outcome_ref)
            self._mutation_journals[key] = mutation_journal_from_operations(state_mutations)
        else:
            self.discard(key)
        if self._max_entries is not None:
            self.prune(self._max_entries)
        return entry_ref

    def load_entry(self, entry_ref: ArtifactRef) -> bool:
        payload = from_canonical_bytes(self._store.get_bytes(entry_ref.artifact_id))
        entry = NodeCacheEntry.model_validate(payload)
        if entry.run_id != self._run_id:
            return False
        offered = from_canonical_bytes(self._store.get_bytes(entry.outcome_ref.artifact_id))
        decoded = decode_node_outcome(offered)
        output_aware = isinstance(decoded, OutputAwareNodeOutcome)
        if output_aware:
            self._verify_output_aware_cache_artifact(entry.outcome_ref)
            self._verify_output_aware_cache_artifact(entry_ref, entry=True)
        else:
            self._verify_cache_artifact(entry.outcome_ref, output_aware=False)
            self._verify_cache_artifact(entry_ref, output_aware=False, entry=True)
        if entry.schema_version != NODE_CACHE_ENTRY_SCHEMA_VERSION:
            self.discard(entry.idempotency_key)
            return False
        if entry.state_mutations_version != STATE_MUTATIONS_VERSION:
            self.discard(entry.idempotency_key)
            return False
        if entry.replay_epoch != REPLAY_EPOCH or entry.journal_proof is None:
            self.discard(entry.idempotency_key)
            return False
        proof = entry.journal_proof
        entry_manifest = self._store.get_manifest(entry_ref.artifact_id)
        expected_producer = _cache_producer(output_aware=output_aware)
        if (
            proof.replay_epoch != REPLAY_EPOCH
            or proof.manifest_schema != entry_manifest.artifact_schema
            or proof.manifest_producer != entry_manifest.producer
            or proof.manifest_schema != _CACHE_ENTRY_SCHEMA
            or proof.manifest_producer != expected_producer
            or proof.payload_hash
            != _journal_proof_hash(
                entry,
                manifest_schema=entry_manifest.artifact_schema,
                manifest_producer=entry_manifest.producer,
            )
        ):
            self.discard(entry.idempotency_key)
            return False
        self._index.set(entry.idempotency_key, entry.outcome_ref)
        self._mutation_journals[entry.idempotency_key] = mutation_journal_from_operations(
            entry.state_mutations
        )
        if self._max_entries is not None:
            self.prune(self._max_entries)
        return True

    def seed_from_trace(self, trace_path: Path | None) -> int:
        if trace_path is None or not trace_path.exists():
            return 0
        restored = 0
        with trace_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if record.get("event") != "NODE_CACHE_STORE":
                    continue
                refs = record.get("refs")
                if not isinstance(refs, dict):
                    continue
                outputs = refs.get("outputs")
                if not isinstance(outputs, list):
                    continue
                for item in outputs:
                    try:
                        ref = ArtifactRef.model_validate(item)
                    except (TypeError, ValueError) as exc:
                        logger.debug(
                            "Skipping invalid artifact ref in trace: %s",
                            exc,
                        )
                        continue
                    if ref.kind != "scientist.node_cache_entry":
                        continue
                    try:
                        if self.load_entry(ref):
                            restored += 1
                    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
                        logger.debug(
                            "Failed to load cache entry: %s",
                            exc,
                        )
                        continue
        return restored

    def seed_from_entry_refs(self, refs: list[ArtifactRef] | tuple[ArtifactRef, ...]) -> int:
        restored = 0
        for ref in refs:
            if ref.kind != "scientist.node_cache_entry":
                continue
            try:
                if self.load_entry(ref):
                    restored += 1
            except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
                logger.debug(
                    "Failed to seed from entry ref: %s",
                    exc,
                )
                continue
        return restored


__all__ = [
    "IDEMPOTENCY_CONTRACT_VERSION",
    "JournalProof",
    "NodeCacheEntry",
    "NodeResultCache",
    "REPLAY_EPOCH",
    "compute_idempotency_key",
    "compute_idempotency_payload",
    "extract_state_slice",
]
