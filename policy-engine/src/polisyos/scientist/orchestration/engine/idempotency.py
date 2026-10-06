"""Idempotency hashing and cache-entry helpers for repeat-safe Scientist node execution."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.common.logger import get_logger
from polisyos.common.serialization import to_python_data
from polisyos.common.timestamps import utc_now
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ArtifactTenantContextInfo,
    ProducerInfo,
    SchemaInfo,
    artifact_ref_identity_key,
)
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.cache import LRUCache
from polisyos.core.canon import CanonSpec, content_hash, from_canonical_bytes, to_canonical_bytes
from polisyos.core.security import (
    get_current_access_scope_or_none,
    get_current_cell_id,
    get_current_tenant_id_or_none,
)
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

IDEMPOTENCY_CONTRACT_VERSION = "2.0"
LEGACY_NODE_CACHE_ENTRY_SCHEMA_VERSION = "1.0"
NODE_CACHE_ENTRY_SCHEMA_VERSION = "2.0"
STATE_MUTATIONS_VERSION = "1.0"
REPLAY_EPOCH = "2.1"

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

_DATA_PLANE_GATE_NODE_ID = "scientist.node_run_data_plane_gate@1.0.0"
_MISSING = object()


def _cache_ref_identity(ref: ArtifactRef) -> tuple[str, str, str, str | None]:
    """Return the complete immutable identity used for cache-entry custody."""
    return artifact_ref_identity_key(ref)


def _active_tenant_context() -> ArtifactTenantContextInfo | None:
    """Resolve the active tenant/cell binding using the existing scope contract."""
    access_scope = get_current_access_scope_or_none()
    tenant_id = get_current_tenant_id_or_none()
    cell_id = get_current_cell_id()
    if access_scope is not None:
        if tenant_id is not None and tenant_id != access_scope.tenant_id:
            raise ValueError("cache_entry: active_tenant_scope_mismatch")
        if (
            cell_id is not None
            and access_scope.cell_id is not None
            and cell_id != access_scope.cell_id
        ):
            raise ValueError("cache_entry: active_tenant_scope_mismatch")
        tenant_id = tenant_id or access_scope.tenant_id
        cell_id = cell_id if cell_id is not None else access_scope.cell_id
    if cell_id is not None and tenant_id is None:
        raise ValueError("cache_entry: active_tenant_scope_mismatch")
    if tenant_id is None:
        return None
    return ArtifactTenantContextInfo(tenant_id=tenant_id, cell_id=cell_id)


class NodeCacheEntry(BaseModel):
    """Artifact record linking a run-scoped idempotency key to a cached node outcome."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=NODE_CACHE_ENTRY_SCHEMA_VERSION, pattern=r"^\d+\.\d+$")
    run_id: str
    node_id: str
    idempotency_key: str = Field(..., min_length=64, max_length=64)
    tenant_context: ArtifactTenantContextInfo | None = None
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
    # preserves their original proof bytes while the v2 writer binds it. An
    # unscoped v2 entry also omits the optional scope field so existing v2
    # proofs remain readable; bound v2 entries include the tenant context.
    if entry.schema_version == LEGACY_NODE_CACHE_ENTRY_SCHEMA_VERSION:
        payload.pop("outcome_payload", None)
    if entry.tenant_context is None:
        payload.pop("tenant_context", None)
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
        if current is _MISSING:
            return _MISSING
        if isinstance(current, BaseModel):
            current = getattr(current, part, _MISSING)
        elif isinstance(current, dict):
            current = current.get(part, _MISSING)
        else:
            return _MISSING
    return current


def _effective_state_read_value(
    state: ExperimentState,
    read_path: str,
    *,
    node_id: str | None,
) -> Any:
    """Resolve a declared read while applying only a known consumer default."""
    value = _resolve_path(state, read_path)
    if (
        node_id == _DATA_PLANE_GATE_NODE_ID
        and read_path == "params.tenant_tier"
        and "tenant_tier" not in state.params
    ):
        # DataPlaneGateNode uses state.params.get("tenant_tier", "shared").
        # Apply that one declared consumer contract, not a global null policy.
        return "shared"
    return value


def _state_read_snapshot_value(value: Any, read_path: str) -> dict[str, Any]:
    """Encode presence separately so missing and explicit null cannot collide."""
    if value is _MISSING:
        return {"presence": "missing", "path": read_path}
    return {
        "presence": "present",
        "value": to_python_data(value, sort_keys=True),
    }


def extract_state_slice(
    state: ExperimentState,
    state_reads: list[str],
    *,
    node_id: str | None = None,
) -> dict[str, Any]:
    """Capture the declared state-read paths that participate in a node idempotency hash."""
    slice_data: dict[str, Any] = {}
    for read_path in sorted(state_reads):
        value = _effective_state_read_value(state, read_path, node_id=node_id)
        slice_data[read_path] = _state_read_snapshot_value(value, read_path)
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
        "state_reads_snapshot": extract_state_slice(
            state,
            spec.state_reads,
            node_id=str(spec.metadata.component_id),
        ),
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
        tenant_context: ArtifactTenantContextInfo | None = None,
    ) -> None:
        self._store = store
        self._run_id = run_id
        self._max_entries = max_entries
        active_context = _active_tenant_context()
        if tenant_context is None:
            tenant_context = active_context
        elif active_context is not None and tenant_context != active_context:
            raise ValueError("cache_entry: active_tenant_scope_mismatch")
        self._tenant_context = tenant_context
        self._index: LRUCache[str, ArtifactRef] = LRUCache(max_size=max_entries)
        self._mutation_journals: dict[str, StateMutationJournal] = {}
        # A checkpoint may repeat the same immutable CAS reference many times.
        # Keep the successful verification identity separate from the key index:
        # an invalid/absent reference must remain retryable, while a verified
        # reference must not be counted as a second cache entry on every resume.
        self._verified_entry_keys: dict[tuple[str, str, str, str | None], str] = {}
        self._lock = RLock()

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def tenant_context(self) -> ArtifactTenantContextInfo | None:
        """Return the immutable tenant/cell binding for this cache instance."""
        return self._tenant_context

    @staticmethod
    def _check_deadline(deadline_monotonic: float | None) -> None:
        if deadline_monotonic is not None and time.perf_counter() >= deadline_monotonic:
            raise TimeoutError("cache deadline exceeded")

    def _assert_active_scope(self) -> None:
        active_context = _active_tenant_context()
        if active_context is not None and active_context != self._tenant_context:
            raise ValueError("cache_entry: active_tenant_scope_mismatch")

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
            entry_ref = self._index.get(key)
            self._index.delete(key)
            self._mutation_journals.pop(key, None)
            if entry_ref is not None:
                self._verified_entry_keys.pop(_cache_ref_identity(entry_ref), None)

    def clear(self) -> None:
        with self._lock:
            self._index.clear()
            self._mutation_journals.clear()
            self._verified_entry_keys.clear()

    def prune(self, max_entries: int) -> int:
        with self._lock:
            removed = self._index.prune(max_entries)
            active_keys = set(self._index.keys())
            for key in tuple(self._mutation_journals):
                if key not in active_keys:
                    del self._mutation_journals[key]
            active_refs = {_cache_ref_identity(ref) for _key, ref in self._index.items()}
            for ref_identity in tuple(self._verified_entry_keys):
                if ref_identity not in active_refs:
                    del self._verified_entry_keys[ref_identity]
            return removed

    def _verify_cache_artifact(
        self,
        ref: ArtifactRef,
        *,
        output_aware: bool,
        entry: bool = False,
        schema_version: str | None = None,
        deadline_monotonic: float | None = None,
    ) -> None:
        """Read back the actual immutable cache epoch, including reused CAS bytes."""
        self._check_deadline(deadline_monotonic)
        if not self._store.verify(ref).ok:
            raise ValueError("cache_custody: artifact_integrity_failed")
        self._check_deadline(deadline_monotonic)
        manifest = self._store.get_manifest(ref)
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
        deadline_monotonic: float | None = None,
    ) -> None:
        """Read back an output-aware cache artifact under its immutable epoch."""
        try:
            self._verify_cache_artifact(
                ref,
                output_aware=True,
                entry=entry,
                schema_version=schema_version,
                deadline_monotonic=deadline_monotonic,
            )
        except ValueError as exc:
            raise ValueError(f"output_aware_cache_custody: {exc}") from exc

    def _read_entry(
        self,
        entry_ref: ArtifactRef,
        *,
        deadline_monotonic: float | None = None,
    ) -> tuple[NodeCacheEntry, NodeOutcome, bool]:
        """Decode one entry, verify its custody, and check its replay proof."""
        self._check_deadline(deadline_monotonic)
        payload = from_canonical_bytes(self._store.get_bytes(entry_ref))
        self._check_deadline(deadline_monotonic)
        entry = NodeCacheEntry.model_validate(payload)
        self._check_deadline(deadline_monotonic)
        entry_manifest = self._store.get_manifest(entry_ref)
        self._validate_entry_scope(entry, entry_manifest)
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
            self._check_deadline(deadline_monotonic)
            offered = from_canonical_bytes(self._store.get_bytes(entry.outcome_ref))
            decoded = decode_node_outcome(offered)
            if isinstance(decoded, OutputAwareNodeOutcome):
                self._verify_output_aware_cache_artifact(
                    entry.outcome_ref,
                    deadline_monotonic=deadline_monotonic,
                )
            else:
                self._verify_cache_artifact(
                    entry.outcome_ref,
                    output_aware=False,
                    deadline_monotonic=deadline_monotonic,
                )
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
            deadline_monotonic=deadline_monotonic,
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

    def _validate_entry_scope(self, entry: NodeCacheEntry, manifest: Any) -> None:
        """Require cache payload, manifest, and cache owner to share one scope."""
        self._assert_active_scope()
        if entry.tenant_context != manifest.tenant_context:
            raise ValueError("cache_entry: tenant_manifest_scope_mismatch")
        if self._tenant_context is None:
            if entry.tenant_context is not None:
                raise ValueError("cache_entry: scoped_artifact_on_unbound_cache")
            return
        if entry.tenant_context is None:
            if entry.schema_version == LEGACY_NODE_CACHE_ENTRY_SCHEMA_VERSION:
                raise ValueError("cache_entry: unbound_legacy_entry")
            raise ValueError("cache_entry: tenant_scope_mismatch")
        if entry.tenant_context != self._tenant_context:
            raise ValueError("cache_entry: tenant_scope_mismatch")

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

    def get(
        self,
        key: str,
        *,
        deadline_monotonic: float | None = None,
    ) -> NodeOutcome | None:
        self._check_deadline(deadline_monotonic)
        self._assert_active_scope()
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
                entry, outcome, proof_valid = self._read_entry(
                    entry_ref,
                    deadline_monotonic=deadline_monotonic,
                )
                if (
                    not proof_valid
                    or entry.idempotency_key != key
                    or entry.run_id != self._run_id
                    or tuple(journal.operations) != entry.state_mutations
                ):
                    raise ValueError("cache_entry: replay_contract_mismatch")
                object.__setattr__(outcome.state, "_polisyos_state_mutation_journal", journal)
            except TimeoutError:
                raise
            except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
                logger.debug(
                    "Cache miss for key %s, evicting: %s",
                    key,
                    exc,
                )
                self.discard(key)
                return None
            return outcome

    def put(
        self,
        key: str,
        node_id: str,
        outcome: NodeOutcome,
        *,
        deadline_monotonic: float | None = None,
    ) -> ArtifactRef:
        self._check_deadline(deadline_monotonic)
        with self._lock:
            self._assert_active_scope()
            output_aware = isinstance(outcome, OutputAwareNodeOutcome)
            cache_producer = _cache_producer(output_aware=output_aware)
            journal = mutation_journal_for_state(outcome.state)
            state_mutations = tuple(journal.operations) if journal is not None else ()
            entry_without_proof = NodeCacheEntry(
                run_id=self._run_id,
                node_id=node_id,
                idempotency_key=key,
                tenant_context=self._tenant_context,
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
            # publication as an orphan artifact. Deadline checks bound
            # admission and readback; they cannot interrupt a synchronous CAS
            # already inside the backend.
            self._check_deadline(deadline_monotonic)
            entry_ref = self._store.put_json(
                entry.model_dump(mode="python", by_alias=True, exclude_none=False),
                PutOptions(
                    kind="scientist.node_cache_entry",
                    media_type="application/json",
                    schema=_CACHE_ENTRY_SCHEMA,
                    producer=cache_producer,
                    tenant_context=self._tenant_context,
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
            self._check_deadline(deadline_monotonic)
            if output_aware:
                self._verify_output_aware_cache_artifact(
                    entry_ref,
                    entry=True,
                    deadline_monotonic=deadline_monotonic,
                )
            else:
                self._verify_cache_artifact(
                    entry_ref,
                    output_aware=False,
                    entry=True,
                    deadline_monotonic=deadline_monotonic,
                )
            self._check_deadline(deadline_monotonic)
            if journal is not None:
                previous_ref = self._index.get(key)
                self._index.set(key, entry_ref)
                self._mutation_journals[key] = mutation_journal_from_operations(state_mutations)
                if previous_ref is not None:
                    self._verified_entry_keys.pop(_cache_ref_identity(previous_ref), None)
                self._verified_entry_keys[_cache_ref_identity(entry_ref)] = key
            else:
                self.discard(key)
            if self._max_entries is not None:
                self.prune(self._max_entries)
            return entry_ref

    def load_entry(
        self,
        entry_ref: ArtifactRef,
        *,
        deadline_monotonic: float | None = None,
    ) -> bool:
        """Verify and admit one entry within the caller's absolute read deadline."""
        self._check_deadline(deadline_monotonic)
        with self._lock:
            self._check_deadline(deadline_monotonic)
            ref_identity = _cache_ref_identity(entry_ref)
            verified_key = self._verified_entry_keys.get(ref_identity)
            if verified_key is not None:
                indexed_ref = self._index.get(verified_key)
                if indexed_ref is not None and _cache_ref_identity(indexed_ref) == ref_identity:
                    return False
                # The LRU may have evicted the entry since it was verified.
                # The reference is eligible for one fresh verification.
                self._verified_entry_keys.pop(ref_identity, None)

            entry, _decoded, proof_valid = self._read_entry(
                entry_ref, deadline_monotonic=deadline_monotonic
            )
            self._check_deadline(deadline_monotonic)
            if entry.run_id != self._run_id or not proof_valid:
                return False

            existing_ref = self._index.get(entry.idempotency_key)
            if existing_ref is not None:
                if _cache_ref_identity(existing_ref) == ref_identity:
                    self._verified_entry_keys[ref_identity] = entry.idempotency_key
                else:
                    # Two immutable entries with one idempotency key are not
                    # interchangeable. Keep the first verified entry rather
                    # than silently replacing it with different content.
                    logger.warning(
                        "Refusing conflicting cache entry for idempotency key %s",
                        entry.idempotency_key,
                    )
                return False

            self._check_deadline(deadline_monotonic)
            self._index.set(entry.idempotency_key, entry_ref)
            self._mutation_journals[entry.idempotency_key] = mutation_journal_from_operations(
                entry.state_mutations
            )
            self._verified_entry_keys[ref_identity] = entry.idempotency_key
            if self._max_entries is not None:
                self.prune(self._max_entries)
            return True

    def seed_from_trace(
        self,
        trace_path: Path | None,
        *,
        deadline_monotonic: float | None = None,
    ) -> int:
        """Recover verified trace entries without refreshing the read deadline."""
        self._check_deadline(deadline_monotonic)
        if trace_path is None or not trace_path.exists():
            return 0
        restored = 0
        self._check_deadline(deadline_monotonic)
        with trace_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                self._check_deadline(deadline_monotonic)
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
                    self._check_deadline(deadline_monotonic)
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
                        if self.load_entry(ref, deadline_monotonic=deadline_monotonic):
                            restored += 1
                    except TimeoutError:
                        raise
                    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
                        logger.debug(
                            "Failed to load cache entry: %s",
                            exc,
                        )
                        continue
        return restored

    def seed_from_entry_refs(
        self,
        refs: list[ArtifactRef] | tuple[ArtifactRef, ...],
        *,
        deadline_monotonic: float | None = None,
    ) -> int:
        """Recover checkpoint refs under the same absolute admission deadline."""
        self._check_deadline(deadline_monotonic)
        restored = 0
        for ref in refs:
            self._check_deadline(deadline_monotonic)
            if ref.kind != "scientist.node_cache_entry":
                continue
            try:
                if self.load_entry(ref, deadline_monotonic=deadline_monotonic):
                    restored += 1
            except TimeoutError:
                raise
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
