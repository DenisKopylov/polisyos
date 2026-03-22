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
from polisyos.scientist.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState

logger = get_logger(__name__)

IDEMPOTENCY_CONTRACT_VERSION = "1.0"

_IDEM_CANON = CanonSpec(
    name="polisyos.idempotency.canon",
    version=IDEMPOTENCY_CONTRACT_VERSION,
    forbid_floats=True,
    sort_keys=True,
)


class NodeCacheEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    run_id: str
    node_id: str
    idempotency_key: str = Field(..., min_length=64, max_length=64)
    outcome_ref: ArtifactRef
    created_at: datetime = Field(default_factory=lambda: utc_now(drop_microseconds=True))


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
    payload = compute_idempotency_payload(spec=spec, state=state, bind_params=bind_params)
    canonical = to_canonical_bytes(payload, _IDEM_CANON)
    return content_hash(canonical)


class NodeResultCache:
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

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def size(self) -> int:
        return len(self._index)

    def has(self, key: str) -> bool:
        return key in self._index

    def clear(self) -> None:
        self._index.clear()

    def prune(self, max_entries: int) -> int:
        return self._index.prune(max_entries)

    def get(self, key: str) -> NodeOutcome | None:
        outcome_ref = self._index.get(key)
        if outcome_ref is None:
            return None
        try:
            payload = from_canonical_bytes(self._store.get_bytes(outcome_ref.artifact_id))
            outcome = NodeOutcome.model_validate(payload)
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            logger.debug(
                "Cache miss for key %s, evicting: %s", key, exc,
            )
            self._index.delete(key)
            return None
        return outcome

    def put(self, key: str, node_id: str, outcome: NodeOutcome) -> ArtifactRef:
        outcome_ref = self._store.put_json(
            outcome.model_dump(mode="python", by_alias=True, exclude_none=False),
            PutOptions(
                kind="scientist.node_outcome",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.scientist.engine.NodeOutcome", version="1.0"),
                producer=ProducerInfo(component="scientist.engine.idempotency", version="1.0.0"),
            ),
        )
        entry = NodeCacheEntry(
            run_id=self._run_id,
            node_id=node_id,
            idempotency_key=key,
            outcome_ref=outcome_ref,
        )
        entry_ref = self._store.put_json(
            entry.model_dump(mode="python", by_alias=True, exclude_none=False),
            PutOptions(
                kind="scientist.node_cache_entry",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.scientist.engine.NodeCacheEntry", version="1.0"),
                producer=ProducerInfo(component="scientist.engine.idempotency", version="1.0.0"),
            ),
        )
        self._index.set(key, outcome_ref)
        if self._max_entries is not None:
            self.prune(self._max_entries)
        return entry_ref

    def load_entry(self, entry_ref: ArtifactRef) -> bool:
        payload = from_canonical_bytes(self._store.get_bytes(entry_ref.artifact_id))
        entry = NodeCacheEntry.model_validate(payload)
        if entry.run_id != self._run_id:
            return False
        self._index.set(entry.idempotency_key, entry.outcome_ref)
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
                            "Skipping invalid artifact ref in trace: %s", exc,
                        )
                        continue
                    if ref.kind != "scientist.node_cache_entry":
                        continue
                    try:
                        if self.load_entry(ref):
                            restored += 1
                    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
                        logger.debug(
                            "Failed to load cache entry: %s", exc,
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
                    "Failed to seed from entry ref: %s", exc,
                )
                continue
        return restored


__all__ = [
    "IDEMPOTENCY_CONTRACT_VERSION",
    "NodeCacheEntry",
    "NodeResultCache",
    "compute_idempotency_key",
    "compute_idempotency_payload",
    "extract_state_slice",
]
