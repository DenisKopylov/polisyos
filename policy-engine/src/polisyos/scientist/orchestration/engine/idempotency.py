"""Idempotency hashing and cache-entry helpers for repeat-safe Scientist node execution."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import RLock
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
LEGACY_NODE_CACHE_ENTRY_SCHEMA_VERSION = "1.0"
NODE_CACHE_ENTRY_SCHEMA_VERSION = "2.0"
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
_LEGACY_CACHE_ENTRY_SCHEMA = SchemaInfo(
    name="polisyos.scientist.orchestration.engine.NodeCacheEntry",
    version=LEGACY_NODE_CACHE_ENTRY_SCHEMA_VERSION,
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
    # ``outcome_ref`` is retained solely for reading the predecessor v1
    # two-artifact wire shape. New entries bind the decoded outcome bytes into
    # this same immutable CAS record so publication cannot leave an orphan
    # outcome artifact when the entry write fails.
    outcome_ref: ArtifactRef | None = None
    outcome_payload: dict[str, Any] | None = None
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
    payload = entry.model_dump(
        mode="python",
        by_alias=True,
        exclude_none=False,
        exclude={"journal_proof"},
    )
    # v1 entries predate the embedded payload field. Omitting the field here
    # preserves their original proof bytes while the v2 writer binds it.
    if entry.schema_version == LEGACY_NODE_CACHE_ENTRY_SCHEMA_VERSION:
        payload.pop("outcome_payload", None)
    return payload


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
        self._lock = RLock()

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._index)

    def has(self, key: str) -> bool:
        with self._lock:
            return key in self._index

    def discard(self, key: str) -> None:
        """Evict one cache key and its replay contract."""
        with self._lock:
            self._index.delete(key)
            self._mutation_journals.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._index.clear()
            self._mutation_journals.clear()

    def prune(self, max_entries: int) -> int:
        with self._lock:
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
        schema_version: str | None = None,
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
            name=f"polisyos.scientist.orchestration.engine.{schema_name}",
            version=(
                schema_version
                if schema_version is not None
                else (NODE_CACHE_ENTRY_SCHEMA_VERSION if entry else "1.0")
            ),
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
        schema_version: str | None = None,
    ) -> None:
        """Read back an output-aware cache artifact under its immutable epoch."""
        try:
            self._verify_cache_artifact(
                ref,
                output_aware=True,
                entry=entry,
                schema_version=schema_version,
            )
        except ValueError as exc:
            raise ValueError(f"output_aware_cache_custody: {exc}") from exc

    def _read_entry(
        self,
        entry_ref: ArtifactRef,
    ) -> tuple[NodeCacheEntry, NodeOutcome, bool]:
        """Decode one entry, verify its custody, and check its replay proof."""
        payload = from_canonical_bytes(self._store.get_bytes(entry_ref.artifact_id))
        entry = NodeCacheEntry.model_validate(payload)
        entry_manifest = self._store.get_manifest(entry_ref.artifact_id)
        known_schema = entry.schema_version in {
            LEGACY_NODE_CACHE_ENTRY_SCHEMA_VERSION,
            NODE_CACHE_ENTRY_SCHEMA_VERSION,
        }
        manifest_schema_version = entry_manifest.artifact_schema.version

        if entry.outcome_payload is not None and entry.outcome_ref is not None:
            raise ValueError("cache_entry: multiple_outcome_sources")
        if entry.outcome_payload is not None:
            decoded = decode_node_outcome(entry.outcome_payload)
        elif entry.outcome_ref is not None:
            offered = from_canonical_bytes(self._store.get_bytes(entry.outcome_ref.artifact_id))
            decoded = decode_node_outcome(offered)
            if isinstance(decoded, OutputAwareNodeOutcome):
                self._verify_output_aware_cache_artifact(entry.outcome_ref)
            else:
                self._verify_cache_artifact(entry.outcome_ref, output_aware=False)
        else:
            raise ValueError("cache_entry: missing_outcome")

        if decoded.state.run_id != entry.run_id:
            raise ValueError("cache_entry: run_identity_mismatch")

        output_aware = isinstance(decoded, OutputAwareNodeOutcome)
        self._verify_cache_artifact(
            entry_ref,
            output_aware=output_aware,
            entry=True,
            # Unknown payload versions are rejected below, but custody is
            # still checked against the immutable manifest actually offered.
            schema_version=entry.schema_version if known_schema else manifest_schema_version,
        )
        if entry.schema_version == NODE_CACHE_ENTRY_SCHEMA_VERSION:
            if entry.outcome_payload is None or entry.outcome_ref is not None:
                raise ValueError("cache_entry: v2_requires_embedded_outcome")
        elif entry.schema_version == LEGACY_NODE_CACHE_ENTRY_SCHEMA_VERSION:
            if entry.outcome_ref is None or entry.outcome_payload is not None:
                raise ValueError("cache_entry: v1_requires_outcome_ref")

        proof_valid = self._replay_proof_valid(
            entry,
            entry_manifest=entry_manifest,
            output_aware=output_aware,
        )
        return entry, decoded, proof_valid

    def _replay_proof_valid(
        self,
        entry: NodeCacheEntry,
        *,
        entry_manifest: Any,
        output_aware: bool,
    ) -> bool:
        """Check the versioned replay contract without trusting payload shape."""
        if entry.schema_version == NODE_CACHE_ENTRY_SCHEMA_VERSION:
            expected_schema = _CACHE_ENTRY_SCHEMA
        elif entry.schema_version == LEGACY_NODE_CACHE_ENTRY_SCHEMA_VERSION:
            expected_schema = _LEGACY_CACHE_ENTRY_SCHEMA
        else:
            return False
        if (
            entry.state_mutations_version != STATE_MUTATIONS_VERSION
            or entry.replay_epoch != REPLAY_EPOCH
            or entry.journal_proof is None
        ):
            return False
        proof = entry.journal_proof
        expected_producer = _cache_producer(output_aware=output_aware)
        return (
            proof.replay_epoch == REPLAY_EPOCH
            and proof.manifest_schema == entry_manifest.artifact_schema
            and proof.manifest_producer == entry_manifest.producer
            and proof.manifest_schema == expected_schema
            and proof.manifest_producer == expected_producer
            and proof.payload_hash
            == _journal_proof_hash(
                entry,
                manifest_schema=entry_manifest.artifact_schema,
                manifest_producer=entry_manifest.producer,
            )
        )

    def get(self, key: str) -> NodeOutcome | None:
        with self._lock:
            entry_ref = self._index.get(key)
            journal = self._mutation_journals.get(key)
            if entry_ref is None:
                return None
            if journal is None:
                # A cache entry without a proven operation contract is
                # historical evidence only; replay it as a miss.
                self.discard(key)
                return None
            try:
                entry, outcome, proof_valid = self._read_entry(entry_ref)
                if (
                    not proof_valid
                    or entry.idempotency_key != key
                    or entry.run_id != self._run_id
                    or tuple(journal.operations) != entry.state_mutations
                ):
                    raise ValueError("cache_entry: replay_contract_mismatch")
                object.__setattr__(outcome.state, "_polisyos_state_mutation_journal", journal)
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
        with self._lock:
            output_aware = isinstance(outcome, OutputAwareNodeOutcome)
            cache_producer = _cache_producer(output_aware=output_aware)
            journal = mutation_journal_for_state(outcome.state)
            state_mutations = tuple(journal.operations) if journal is not None else ()
            entry_without_proof = NodeCacheEntry(
                run_id=self._run_id,
                node_id=node_id,
                idempotency_key=key,
                outcome_payload=outcome.model_dump(
                    mode="python", by_alias=True, exclude_none=False
                ),
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
            # The outcome and replay journal are one typed CAS payload. There
            # is no preceding outcome write that can survive a failed entry
            # publication as an orphan artifact.
            entry_ref = self._store.put_json(
                entry.model_dump(mode="python", by_alias=True, exclude_none=False),
                PutOptions(
                    kind="scientist.node_cache_entry",
                    media_type="application/json",
                    schema=_CACHE_ENTRY_SCHEMA,
                    producer=cache_producer,
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
            if output_aware:
                self._verify_output_aware_cache_artifact(entry_ref, entry=True)
            else:
                self._verify_cache_artifact(entry_ref, output_aware=False, entry=True)
            if journal is not None:
                self._index.set(key, entry_ref)
                self._mutation_journals[key] = mutation_journal_from_operations(state_mutations)
            else:
                self.discard(key)
            if self._max_entries is not None:
                self.prune(self._max_entries)
            return entry_ref

    def load_entry(self, entry_ref: ArtifactRef) -> bool:
        with self._lock:
            entry, _decoded, proof_valid = self._read_entry(entry_ref)
            if entry.run_id != self._run_id or not proof_valid:
                self.discard(entry.idempotency_key)
                return False
            self._index.set(entry.idempotency_key, entry_ref)
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
