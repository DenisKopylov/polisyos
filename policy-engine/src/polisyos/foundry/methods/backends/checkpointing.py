"""
Checkpoint-based Chain Execution.

Long method chains (causal discovery → estimation → sensitivity → welfare)
can fail partway through due to transient errors, OOM, or external service
timeouts.  ``CheckpointingChainExecutor`` saves intermediate states to disk
after every *N* nodes and can resume from the last valid checkpoint,
skipping already-completed work.

How it works
------------
1. After a successful node, a checkpoint is written if the node index is a
   multiple of ``checkpoint_every`` or if this is the last node.
2. On resume, the executor reads the checkpoint, validates the chain digest
   matches, and fast-forwards past already-completed nodes.
3. The structural chain digest and effective execution digest guard the
   compiled plan, parameters, initial state and seed used for the checkpoint.

Checkpoint format
-----------------
The public checkpoint file is an atomic JSON pointer to one immutable UUID
generation. Its SHA-256 binds the complete snapshot: execution identity,
completed frontier, state and original per-node result history. NumPy state
and history arrays live in that generation and carry content, dtype and shape
bindings. Writers hold one filesystem lock through publication or rollback.
Existing direct-JSON checkpoints remain readable; resuming them still requires
the effective execution identity and honest history completeness.

Limitations
-----------
- State values must be JSON-serialisable or non-object NumPy arrays. Mapping
  keys must be strings; ``__npy_ref__`` is reserved for array references. Arrays
  use ``np.save`` sidecars and are loaded without pickle.
- A parent-directory fsync failure after pointer replacement raises
  ``CheckpointPublicationUncertainError`` and preserves the visible generation;
  it does not acknowledge durable success.
- Retained and interrupted orphan generations are not garbage-collected.
  Readers and writers must use this API on a local filesystem supporting flock,
  atomic replacement and directory fsync. Power-loss and hostile filesystem
  mutation are outside this execution protocol.

Usage
-----
::

    executor = CheckpointingChainExecutor(checkpoint_dir=Path("/tmp/checkpoints"))

    # First run — may fail partway through
    result = executor.execute(chain, initial_state=state)

    # Resume — skips already-completed nodes
    checkpoint = executor.find_latest_checkpoint(chain)
    result = executor.execute(chain, initial_state=state, checkpoint=checkpoint)
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import inspect
import json
import logging
import os
import shutil
import sys
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import UUID, uuid4

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts import (
    artifact_manifest_profile_projection,
    artifact_manifest_profile_sha256,
)
from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.observability import DeterminismTier
from polisyos.core.security.tenant_context import (
    get_current_access_scope_or_none,
    get_current_cell_id,
    get_current_tenant_id_or_none,
)
from polisyos.foundry.methods.artifacts._fingerprint import compute_source_hash
from polisyos.foundry.methods.backends.chain_executor import (
    ChainExecutionResult,
    _build_chain_reproducibility_contract,
    _collect_node_inputs,
)
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodTiming,
    ReproducibilityInfo,
    SolverStatus,
)
from polisyos.foundry.methods.backends.runtime_fingerprint import (
    capture_backend_runtime_fingerprint,
    capture_versions,
    safe_version,
)
from polisyos.foundry.methods.backends.validated import (
    ValidatedBound,
    ValidatedMethodFamily,
    ValidatedStatus,
)
from polisyos.foundry.methods.base import ComputeBackend, _stable_digest
from polisyos.foundry.methods.selection.registry import MethodRegistry, get_registry

__all__ = [
    "ChainCheckpoint",
    "CheckpointArtifactContext",
    "CheckpointDigestMismatchError",
    "CheckpointError",
    "CheckpointIssue",
    "CheckpointIdentityError",
    "CheckpointLoadError",
    "CheckpointPublicationUncertainError",
    "CheckpointSaveError",
    "CheckpointSerializationError",
    "CheckpointingChainExecutor",
]

_logger = logging.getLogger("foundry.methods.checkpointing")
_MAX_CHECKPOINT_ISSUES = 64


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CheckpointError(Exception):
    """Base class for typed checkpoint persistence failures."""


class CheckpointSerializationError(CheckpointError):
    """Raised when state cannot be serialised to a checkpoint."""


class CheckpointSaveError(CheckpointError):
    """Raised when a checkpoint cannot be written atomically."""


class CheckpointPublicationUncertainError(CheckpointSaveError):
    """The new manifest is visible but its directory durability is uncertain."""


class CheckpointLoadError(CheckpointError):
    """Raised when a checkpoint cannot be loaded or validated."""


class CheckpointDigestMismatchError(CheckpointError):
    """Raised when a checkpoint's chain_digest doesn't match the current chain."""


class CheckpointIdentityError(CheckpointError):
    """Required source, scope or exact artifact identity cannot be established."""


class CheckpointArtifactContext(BaseModel):
    """Declared artifact lineage, reconciled through the supplied guarded store.

    This declaration supplies identity premises, not authorization or a data
    decoder. Every reference selects an exact manifest profile. The caller
    supplies the actual initial state independently; its content is also bound.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    input_refs: dict[str, ArtifactRef] = Field(default_factory=dict)
    config_refs: dict[str, ArtifactRef] = Field(default_factory=dict)
    origin_ref: ArtifactRef | None = None
    dependency_refs: dict[str, ArtifactRef] = Field(default_factory=dict)
    cache_refs: dict[UUID, ArtifactRef] = Field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _ExecutionMethods:
    """Resolve each actual method once for one checkpoint-bound execution."""

    methods: Mapping[str, type]

    def get(self, fqn: str) -> type:
        return self.methods[fqn]


@dataclass(frozen=True, slots=True)
class CheckpointIssue:
    """Bounded diagnostic emitted for checkpoint persistence degradation."""

    operation: str
    path: str
    error_type: str
    message: str
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# ChainCheckpoint
# ---------------------------------------------------------------------------


@dataclass
class ChainCheckpoint:
    """
    Serialisable record of partial chain execution progress.

    Attributes
    ----------
    chain_digest:
        SHA-256 hex digest of the execution-order FQN list.  Used to
        verify that the checkpoint belongs to the same chain definition.
    completed_fqns:
        Ordered list of method FQNs that have been executed successfully.
    completed_node_ids:
        Ordered list of node UUID strings matching ``completed_fqns``.
    intermediate_state:
        State dict after the last completed node.
    node_timing_ms:
        Wall-clock time (ms) for each completed node.
    created_at:
        Unix timestamp when this checkpoint was written.
    checkpoint_path:
        Path to the file where this checkpoint is stored (set after save).
    """

    chain_digest: str
    completed_fqns: list[str]
    completed_node_ids: list[str]  # UUID as str
    intermediate_state: dict[str, Any]
    node_timing_ms: list[float] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    execution_digest: str | None = None
    node_results: list[dict[str, Any]] = field(default_factory=list)
    history_complete: bool = False
    identity_snapshot: dict[str, Any] | None = None
    checkpoint_path: Path | None = field(default=None, compare=False, repr=False)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Path) -> None:
        """Publish one immutable snapshot generation through an atomic pointer."""
        path = path.parent.resolve() / path.name
        path.parent.mkdir(parents=True, exist_ok=True)
        with _checkpoint_write_lock(path):
            generation_dir = path.parent / f".{path.name}.generations" / uuid4().hex
            tmp_paths: list[Path] = []
            manifest_published = False
            generation_created = False

            def mark_manifest_published() -> None:
                nonlocal manifest_published
                manifest_published = True
                self.checkpoint_path = path

            try:
                generation_dir = _resolve_checkpoint_member_path(
                    path.parent, str(generation_dir.relative_to(path.parent))
                )
                generation_dir.mkdir(parents=True, exist_ok=False)
                generation_created = True
                if not isinstance(self.intermediate_state, Mapping):
                    raise CheckpointSerializationError("Checkpoint state root must be a mapping.")
                snapshot_values: dict[str, Any] = {"intermediate_state": self.intermediate_state}
                if self.node_results:
                    snapshot_values["node_results"] = self.node_results
                # Encode the whole logical snapshot once: each array identity
                # includes its semantic root as well as its structural path.
                # User state can therefore contain arbitrary history-like keys.
                snapshot_payload, sidecars = _serialise_state(
                    snapshot_values, "snapshot", force_encoded=True
                )
                data = {
                    "chain_digest": self.chain_digest,
                    "completed_fqns": self.completed_fqns,
                    "completed_node_ids": self.completed_node_ids,
                    **snapshot_payload,
                    "node_timing_ms": self.node_timing_ms,
                    "created_at": self.created_at,
                    "execution_digest": self.execution_digest,
                    "history_complete": self.history_complete,
                    "identity_snapshot": self.identity_snapshot,
                }
                for sidecar_name, arr in sidecars.items():
                    sidecar_path = generation_dir / sidecar_name
                    tmp_sidecar = _tmp_path_for(sidecar_path)
                    tmp_paths.append(tmp_sidecar)
                    _atomic_save_numpy(tmp_sidecar, sidecar_path, arr)
                    tmp_paths.remove(tmp_sidecar)

                snapshot_bytes = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
                snapshot_path = generation_dir / "snapshot.json"
                tmp_snapshot = _tmp_path_for(snapshot_path)
                tmp_paths.append(tmp_snapshot)
                _atomic_write_bytes(tmp_snapshot, snapshot_path, snapshot_bytes)
                tmp_paths.remove(tmp_snapshot)
                # The immutable generation and its parent entry must precede
                # the pointer that lets a reader select them.
                _fsync_dir(generation_dir.parent)
                _fsync_dir(path.parent)
                pointer = {
                    "checkpoint_format": "generation-v1",
                    "snapshot_ref": str(snapshot_path.relative_to(path.parent)),
                    "snapshot_sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
                }
                json_bytes = json.dumps(pointer, indent=2, sort_keys=True).encode("utf-8")
                tmp_json = _tmp_path_for(path)
                tmp_paths.append(tmp_json)
                _atomic_write_bytes(tmp_json, path, json_bytes, on_publish=mark_manifest_published)
                tmp_paths.remove(tmp_json)
            except (
                OSError,
                TypeError,
                ValueError,
                CheckpointSerializationError,
                CheckpointLoadError,
            ) as exc:
                # Cleanup remains in the same actual writer lock. Only this
                # unpublished UUID generation belongs to the failed writer.
                _cleanup_paths(tmp_paths)
                if not manifest_published:
                    if generation_created:
                        try:
                            shutil.rmtree(generation_dir)
                        except OSError:
                            _logger.debug(
                                "checkpoint_generation_cleanup_failed path=%s", generation_dir
                            )
                    raise CheckpointSaveError(
                        f"Failed to save checkpoint at {path}: {exc}"
                    ) from exc
                raise CheckpointPublicationUncertainError(
                    f"Checkpoint manifest was replaced at {path}, but its directory "
                    f"durability is uncertain: {exc}"
                ) from exc

    @classmethod
    def load(cls, path: Path) -> ChainCheckpoint:
        """Deserialise from *path*."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise CheckpointLoadError("Checkpoint manifest must be a JSON object.")
            snapshot_base = path.parent
            if "checkpoint_format" in data:
                if data["checkpoint_format"] != "generation-v1":
                    raise CheckpointLoadError("Unsupported checkpoint manifest format.")
                snapshot_path = _resolve_checkpoint_member_path(path.parent, data["snapshot_ref"])
                snapshot_bytes = snapshot_path.read_bytes()
                if hashlib.sha256(snapshot_bytes).hexdigest() != data["snapshot_sha256"]:
                    raise CheckpointLoadError("Checkpoint generation snapshot content mismatch.")
                data = json.loads(snapshot_bytes)
                if not isinstance(data, dict):
                    raise CheckpointLoadError("Checkpoint snapshot must be a JSON object.")
                snapshot_base = snapshot_path.parent
            state = _deserialise_state(data.pop("intermediate_state"), snapshot_base)
            node_results: list[dict[str, Any]] = []
            if "node_results" in data:
                node_results_payload = _deserialise_state(
                    {"node_results": data.pop("node_results")},
                    snapshot_base,
                )
                node_results = node_results_payload["node_results"]
            return cls(
                chain_digest=data["chain_digest"],
                completed_fqns=data["completed_fqns"],
                completed_node_ids=data["completed_node_ids"],
                intermediate_state=state,
                node_timing_ms=data.get("node_timing_ms", []),
                created_at=data.get("created_at", 0.0),
                execution_digest=data.get("execution_digest"),
                node_results=node_results,
                history_complete=data.get("history_complete") is True,
                identity_snapshot=data.get("identity_snapshot"),
                checkpoint_path=path,
            )
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
            CheckpointError,
        ) as exc:
            raise CheckpointLoadError(f"Failed to load checkpoint at {path}: {exc}") from exc

    @property
    def n_completed(self) -> int:
        return len(self.completed_fqns)

    def __repr__(self) -> str:
        return (
            f"<ChainCheckpoint completed={self.n_completed} "
            f"digest={self.chain_digest[:8]}... "
            f"path={self.checkpoint_path}>"
        )


# ---------------------------------------------------------------------------
# CheckpointingChainExecutor
# ---------------------------------------------------------------------------


class CheckpointingChainExecutor:
    """
    Executes a method chain with automatic checkpointing.

    Parameters
    ----------
    checkpoint_dir:
        Directory where checkpoint files are written.  Created if absent.
        If None, checkpointing is disabled (behaves like the plain executor).
    checkpoint_every:
        Write a checkpoint after every *N* completed nodes (default: 1).
    registry:
        Optional registry override (defaults to ``get_registry()``).
    dispatcher:
        Optional dispatcher override (defaults to global singleton).
    """

    def __init__(
        self,
        checkpoint_dir: Path | None = None,
        checkpoint_every: int = 1,
        registry: MethodRegistry | None = None,
        dispatcher: MethodDispatcher | None = None,
        fail_on_checkpoint_error: bool = True,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        self._checkpoint_dir = checkpoint_dir
        self._checkpoint_every = max(1, checkpoint_every)
        self._registry = registry
        self._dispatcher = dispatcher
        self._fail_on_checkpoint_error = fail_on_checkpoint_error
        self._checkpoint_issues: list[CheckpointIssue] = []
        self._artifact_store = artifact_store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(
        self,
        chain: Any,
        initial_state: dict[str, Any],
        params_per_node: Mapping[UUID, Mapping[str, Any]] | None = None,
        *,
        checkpoint: ChainCheckpoint | None = None,
        seed: int = 0,
        artifact_context: CheckpointArtifactContext | None = None,
    ) -> ChainExecutionResult:
        """
        Execute *chain*, optionally resuming from *checkpoint*.

        Parameters
        ----------
        chain:
            A ``CompiledMethodChain`` from ``MethodComposer.build()``.
        initial_state:
            Starting state dict.
        params_per_node:
            Per-node parameter overrides.
        checkpoint:
            A previously saved ``ChainCheckpoint`` to resume from.
            If provided, already-completed nodes are skipped.
        seed:
            Random seed.

        Returns
        -------
        ChainExecutionResult
        """
        reg = self._registry or get_registry()
        disp = self._dispatcher or MethodDispatcher.get_instance()
        params_per_node = params_per_node or {}
        if artifact_context is not None:
            artifact_context = _validated_artifact_context(artifact_context)

        chain_digest = _compute_chain_digest(chain)
        execution_digest = None
        identity_snapshot = None
        if (
            checkpoint is not None
            or self._checkpoint_dir is not None
            or artifact_context is not None
        ):
            reg = _ExecutionMethods(
                {
                    chain.get_node(node_id).method_fqn: reg.get(chain.get_node(node_id).method_fqn)
                    for node_id in chain.execution_order
                }
            )
            identity_snapshot = _capture_execution_identity(
                chain, reg, artifact_context, self._artifact_store, seed=seed
            )
            execution_digest = _compute_execution_digest(
                chain,
                initial_state=initial_state,
                params_per_node=params_per_node,
                seed=seed,
                identity_snapshot=identity_snapshot,
            )
        execution_order: list[UUID] = chain.execution_order

        # Validate checkpoint if provided
        skip_until: int = 0
        state = dict(initial_state)
        all_node_results: list[tuple[UUID, MethodResult]] = []
        node_slot_outputs: dict[UUID, dict[str, Any]] = {}
        missing_history_node_ids: tuple[UUID, ...] = ()
        history_complete = True

        if checkpoint is not None:
            if checkpoint.chain_digest != chain_digest:
                raise CheckpointDigestMismatchError(
                    f"Checkpoint digest {checkpoint.chain_digest!r} does not match "
                    f"chain digest {chain_digest!r}. "
                    "The checkpoint was created for a different chain."
                )
            _validate_checkpoint_prefix(checkpoint, chain, execution_order)
            if checkpoint.execution_digest is None:
                raise CheckpointDigestMismatchError(
                    "Checkpoint lacks execution identity; legacy checkpoints cannot "
                    "be resumed safely."
                )
            if checkpoint.execution_digest != execution_digest:
                raise CheckpointDigestMismatchError(
                    "Checkpoint execution identity does not match the effective "
                    "chain plan, inputs, parameters, or seed."
                )
            if checkpoint.identity_snapshot != identity_snapshot:
                raise CheckpointDigestMismatchError(
                    "Checkpoint source, scope or selected artifact view does not match."
                )
            skip_until = checkpoint.n_completed
            state = dict(checkpoint.intermediate_state)
            prefix_ids = execution_order[:skip_until]
            restored_by_id: dict[UUID, MethodResult] = {}
            for snapshot in checkpoint.node_results:
                restored_id, restored_result = _restore_node_result(snapshot, checkpoint)
                if (
                    restored_id not in prefix_ids
                    or restored_id in restored_by_id
                    or snapshot.get("method_fqn") != chain.get_node(restored_id).method_fqn
                ):
                    raise CheckpointLoadError(
                        "Checkpoint per-node history does not match the execution prefix."
                    )
                restored_by_id[restored_id] = restored_result
            missing_history_node_ids = tuple(
                node_id for node_id in prefix_ids if node_id not in restored_by_id
            )
            history_complete = (
                checkpoint.history_complete
                and not missing_history_node_ids
                and all(
                    "history_incomplete" not in result.warnings
                    for result in restored_by_id.values()
                )
            )
            for node_id in prefix_ids:
                if node_id in restored_by_id:
                    restored_result = restored_by_id[node_id]
                    all_node_results.append((node_id, restored_result))
                    node_slot_outputs[node_id] = dict(restored_result.slot_outputs)

        # Execute remaining nodes
        for idx, node_id in enumerate(execution_order):
            if idx < skip_until:
                continue

            signature = chain.get_signature(node_id)
            method_class, materialized_state, signature, node_params = _collect_node_inputs(
                chain=chain,
                node_id=node_id,
                reg=reg,
                node_slot_outputs=node_slot_outputs,
                fx_rate_provider=None,
                current_state=state,
                signature=signature,
                current_context=state,
                params_per_node=params_per_node,
            )
            if artifact_context is not None:
                _validate_dispatch_identity(
                    method_class, signature.fqn, identity_snapshot, seed=seed
                )
            result = disp.dispatch(
                method_class=method_class,
                signature=signature,
                state=materialized_state,
                params=node_params,
                seed=seed,
            )
            if artifact_context is not None:
                _validate_dispatch_identity(
                    method_class, signature.fqn, identity_snapshot, seed=seed
                )
            node_slot_outputs[node_id] = dict(result.slot_outputs)
            if isinstance(result.output, dict):
                state.update(result.output)
            all_node_results.append((node_id, result))
            history_complete = history_complete and "history_incomplete" not in result.warnings

            # Save checkpoint if needed
            should_checkpoint = self._checkpoint_dir is not None and (
                (idx - skip_until + 1) % self._checkpoint_every == 0
                or idx == len(execution_order) - 1
            )
            if should_checkpoint:
                self._save_checkpoint(
                    chain=chain,
                    chain_digest=chain_digest,
                    completed_up_to_idx=idx,
                    execution_order=execution_order,
                    all_node_results=all_node_results,
                    state=state,
                    execution_digest=execution_digest,
                    history_provenance_complete=history_complete,
                    identity_snapshot=identity_snapshot,
                )

        reproducibility_contract = _build_chain_reproducibility_contract(
            all_node_results,
            composition_kind="serial",
        )
        reproducibility_contract.update(
            history_complete=history_complete,
            completed_node_count=len(execution_order),
            missing_history_node_ids=[str(node_id) for node_id in missing_history_node_ids],
        )
        return ChainExecutionResult(
            final_state=state,
            node_results=tuple(all_node_results),
            reproducibility_contract=reproducibility_contract,
            missing_history_node_ids=missing_history_node_ids,
            history_provenance_complete=history_complete,
        )

    def find_latest_checkpoint(self, chain: Any) -> ChainCheckpoint | None:
        """Find the most recent checkpoint for *chain* in ``checkpoint_dir``."""
        if self._checkpoint_dir is None:
            return None
        chain_digest = _compute_chain_digest(chain)
        pattern = f"checkpoint_{chain_digest[:8]}_*.json"
        candidates = sorted(
            self._checkpoint_dir.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for candidate in candidates:
            try:
                return ChainCheckpoint.load(candidate)
            except CheckpointLoadError as exc:
                self._record_checkpoint_issue("load", candidate, exc)
                continue
        return None

    @property
    def checkpoint_issues(self) -> tuple[CheckpointIssue, ...]:
        """Bounded diagnostics for checkpoint load/save degradation."""
        return tuple(self._checkpoint_issues)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save_checkpoint(
        self,
        chain: Any,
        chain_digest: str,
        completed_up_to_idx: int,
        execution_order: list[UUID],
        all_node_results: list[tuple[UUID, MethodResult]],
        state: dict[str, Any],
        execution_digest: str | None = None,
        history_provenance_complete: bool = True,
        identity_snapshot: dict[str, Any] | None = None,
    ) -> None:
        if self._checkpoint_dir is None:
            raise CheckpointSaveError("checkpoint_dir is not configured")
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        filename = f"checkpoint_{chain_digest[:8]}_{completed_up_to_idx:04d}_{timestamp}.json"
        path = self._checkpoint_dir / filename

        completed_prefix = list(execution_order[: completed_up_to_idx + 1])
        completed_node_ids = [str(nid) for nid in completed_prefix]
        completed_fqns = [chain.get_node(nid).method_fqn for nid in completed_prefix]
        timing_ms = [r.timing.wall_time_ms for _, r in all_node_results]
        history_complete = (
            history_provenance_complete
            and [nid for nid, _ in all_node_results] == completed_prefix
            and all(
                isinstance(result, MethodResult) and "history_incomplete" not in result.warnings
                for _, result in all_node_results
            )
        )
        if not history_complete:
            timing_ms = []
        node_results = (
            [
                _snapshot_node_result(node_id, chain.get_node(node_id).method_fqn, result)
                for node_id, result in all_node_results
            ]
            if all(isinstance(result, MethodResult) for _, result in all_node_results)
            else []
        )

        chk = ChainCheckpoint(
            chain_digest=chain_digest,
            completed_fqns=completed_fqns,
            completed_node_ids=completed_node_ids,
            intermediate_state=state,
            node_timing_ms=timing_ms,
            execution_digest=execution_digest,
            node_results=node_results,
            history_complete=history_complete,
            identity_snapshot=identity_snapshot,
        )
        try:
            chk.save(path)
        except CheckpointSaveError as exc:
            self._record_checkpoint_issue("save", path, exc)
            if self._fail_on_checkpoint_error:
                raise

    def _record_checkpoint_issue(self, operation: str, path: Path, exc: CheckpointError) -> None:
        issue = CheckpointIssue(
            operation=operation,
            path=str(path),
            error_type=type(exc).__name__,
            message=str(exc),
        )
        self._checkpoint_issues.append(issue)
        del self._checkpoint_issues[:-_MAX_CHECKPOINT_ISSUES]
        _logger.warning(
            "checkpoint_%s_failed path=%s error_type=%s message=%s",
            operation,
            path,
            type(exc).__name__,
            exc,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _source_identity(value: Any, *, strict: bool, visiting: set[int] | None = None) -> Any:
    """Bind inspectable code and immutable captures without hashing registry state.

    Strict artifact execution refuses unknown or mutable captured state. Legacy
    request-only execution records an unavailable boundary instead of claiming
    artifact/source closure. Imported distribution code is version-bound.
    """
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Enum):
        return {
            "enum": f"{type(value).__module__}.{type(value).__qualname__}",
            "value": value.value,
        }
    if isinstance(value, tuple):
        return [_source_identity(item, strict=strict, visiting=visiting) for item in value]
    if isinstance(value, ModuleType):
        root = value.__name__.split(".")[0]
        versions = capture_versions(base_packages=(), runtime_stack=(root,))
        version = (
            sys.version if root in sys.stdlib_module_names else next(iter(versions.values()), None)
        )
        if version is not None:
            return {"module": value.__name__, "version": version}
    elif inspect.isfunction(value) or inspect.isclass(value) or inspect.isbuiltin(value):
        visiting = set() if visiting is None else visiting
        module_name = str(value.__module__ or "<unknown>")
        symbol = f"{module_name}.{value.__qualname__}"
        if id(value) in visiting:
            return {"recursive_symbol": symbol}
        source = compute_source_hash(value)
        if source != "unavailable":
            visiting.add(id(value))
            try:
                result: dict[str, Any] = {"symbol": symbol, "source_hash": source}
                if inspect.isclass(value):
                    result["bases"] = [
                        _source_identity(base, strict=strict, visiting=visiting)
                        for base in value.__bases__
                        if base is not object
                    ]
                    result["attributes"] = {
                        name: _source_identity(item, strict=strict, visiting=visiting)
                        for name, item in sorted(vars(value).items())
                        if not name.startswith("__")
                        and name not in {"signature", "metadata"}
                        and not isinstance(item, (staticmethod, classmethod, property))
                        and not callable(item)
                    }
                if inspect.isfunction(value):
                    captures = inspect.getclosurevars(value)
                    result["captures"] = {
                        name: _source_identity(item, strict=strict, visiting=visiting)
                        for name, item in sorted((captures.globals | captures.nonlocals).items())
                    }
                    result["defaults"] = _source_identity(
                        value.__defaults__, strict=strict, visiting=visiting
                    )
                    result["keyword_defaults"] = {
                        name: _source_identity(item, strict=strict, visiting=visiting)
                        for name, item in sorted((value.__kwdefaults__ or {}).items())
                    }
                return result
            finally:
                visiting.remove(id(value))
        if strict and not inspect.isbuiltin(value):
            raise CheckpointIdentityError(
                "Strict checkpoint source identity is unavailable for " + type(value).__name__
            )
        root = module_name.split(".")[0]
        version = (
            sys.version
            if root in sys.stdlib_module_names or root == "builtins"
            else safe_version(root)
        )
        if version is not None:
            return {"symbol": symbol, "distribution_version": version}
    if strict:
        raise CheckpointIdentityError(
            "Strict checkpoint source identity is unavailable for " + type(value).__name__
        )
    return {"unavailable_type": f"{type(value).__module__}.{type(value).__qualname__}"}


def _checkpoint_scope() -> dict[str, str | None]:
    tenant = get_current_tenant_id_or_none()
    cell = get_current_cell_id()
    access = get_current_access_scope_or_none()
    if access is not None:
        if tenant is not None and tenant != access.tenant_id:
            raise CheckpointIdentityError(
                "Active checkpoint tenant scope disagrees with access scope."
            )
        if cell is not None and access.cell_id is not None and cell != access.cell_id:
            raise CheckpointIdentityError(
                "Active checkpoint cell scope disagrees with access scope."
            )
        tenant = tenant or access.tenant_id
        cell = cell if cell is not None else access.cell_id
    if cell is not None and tenant is None:
        raise CheckpointIdentityError("Checkpoint cell scope lacks a tenant.")
    return {"tenant_id": tenant, "cell_id": cell}


def _capture_execution_identity(
    chain: Any,
    registry: MethodRegistry | _ExecutionMethods,
    context: CheckpointArtifactContext | None,
    store: ArtifactStore | None,
    *,
    seed: int,
) -> dict[str, Any]:
    strict = context is not None
    methods: dict[str, Any] = {}
    for node_id in chain.execution_order:
        fqn = chain.get_node(node_id).method_fqn
        if fqn in methods:
            continue
        method = registry.get(fqn)
        methods[fqn] = _method_identity(method, fqn, strict=strict, seed=seed)
    snapshot: dict[str, Any] = {
        "profile": "artifact-source-v1" if strict else "legacy-request-source-v1",
        "methods": methods,
    }
    if context is None:
        return snapshot
    if store is None:
        raise CheckpointIdentityError("Artifact context requires a guarded artifact store.")
    # Copy/validate nested mutable ref maps before reads; a frozen Pydantic
    # model alone does not freeze its maps or the individual ArtifactRefs.
    context = _validated_artifact_context(context)
    if not set(context.cache_refs).issubset(set(chain.execution_order)):
        raise CheckpointIdentityError(
            "Checkpoint cache reference does not name a chain occurrence."
        )
    snapshot["scope"] = _checkpoint_scope()
    snapshot["python"] = sys.version
    snapshot["artifacts"] = {}
    groups = {
        "input_refs": context.input_refs,
        "config_refs": context.config_refs,
        "dependency_refs": context.dependency_refs,
        "cache_refs": {str(key): ref for key, ref in context.cache_refs.items()},
        "origin_ref": {} if context.origin_ref is None else {"origin": context.origin_ref},
    }
    for group, refs in groups.items():
        resolved = {}
        for name, ref in sorted(refs.items()):
            if ref.manifest_profile_sha256 is None:
                raise CheckpointIdentityError(
                    f"Exact selected manifest view is required: {group}/{name}"
                )
            try:
                data = store.get_bytes(ref)
                manifest = store.get_manifest(ref)
                content_hash = hashlib.sha256(data).hexdigest()
                if (
                    content_hash != ref.artifact_id.hex
                    or manifest.artifact_id != ref.artifact_id
                    or manifest.integrity.sha256 != content_hash
                    or manifest.byte_size != len(data)
                    or manifest.kind != ref.kind
                    or manifest.media_type != ref.media_type
                    or artifact_manifest_profile_sha256(manifest) != ref.manifest_profile_sha256
                ):
                    raise CheckpointIdentityError(
                        f"Artifact bytes or selected manifest disagree: {group}/{name}"
                    )
            except CheckpointIdentityError:
                raise
            except Exception as exc:
                raise CheckpointIdentityError(
                    f"Guarded artifact identity read failed: {group}/{name}: {type(exc).__name__}"
                ) from exc
            resolved[name] = {
                "ref": list(artifact_ref_identity_key(ref)),
                "manifest_profile": artifact_manifest_profile_projection(manifest),
                "content_sha256": content_hash,
            }
        snapshot["artifacts"][group] = resolved
    if snapshot["scope"] != _checkpoint_scope():
        raise CheckpointIdentityError("Active scope changed during artifact identity reads.")
    return snapshot


def _validated_artifact_context(context: CheckpointArtifactContext) -> CheckpointArtifactContext:
    try:
        return CheckpointArtifactContext.model_validate(context.model_dump(mode="python"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise CheckpointIdentityError("Artifact context is not a valid typed declaration.") from exc


def _method_identity(method: type, fqn: str, *, strict: bool, seed: int) -> dict[str, Any]:
    signature = getattr(method, "signature", None)
    digest = getattr(signature, "stable_digest", None)
    if strict and (digest is None or not callable(getattr(method, "pure_step", None))):
        raise CheckpointIdentityError(f"Current method ABI or implementation is unavailable: {fqn}")
    entry = {
        "signature_digest": digest() if digest is not None else None,
        "class_source": _source_identity(method, strict=strict),
        "callbacks": {
            name: _source_identity(inspect.unwrap(callback), strict=strict)
            for name in (
                "pure_step",
                "materialize_input",
                "dematerialize_output",
                "postprocess_output",
            )
            if callable(callback := getattr(method, name, None))
        },
    }
    if strict:
        posture = capture_backend_runtime_fingerprint(
            signature.backend, method_class=method, seed=seed
        )
        if not posture.available:
            raise CheckpointIdentityError(f"Current backend identity is unavailable: {fqn}")
        if any(
            not capture_versions(base_packages=(), runtime_stack=(package,))
            for package in posture.runtime_stack
        ):
            raise CheckpointIdentityError(
                f"Declared runtime dependency version is unavailable: {fqn}"
            )
        entry["runtime"] = {
            "backend": posture.backend.value,
            "runtime_stack": list(posture.runtime_stack),
            "library_versions": dict(posture.library_versions),
            "execution_device": posture.execution_device,
            "runtime_backend": posture.runtime_backend,
            "route_key": dict(posture.route_key),
            "determinism_tier": None
            if posture.determinism_tier is None
            else posture.determinism_tier.value,
        }
    return entry


def _validate_dispatch_identity(
    method: type, fqn: str, snapshot: dict[str, Any], *, seed: int
) -> None:
    """Fence actual source/scope around dispatch without rereading large CAS inputs."""
    if (
        _method_identity(method, fqn, strict=True, seed=seed) != snapshot["methods"][fqn]
        or _checkpoint_scope() != snapshot["scope"]
    ):
        raise CheckpointIdentityError(
            "Strict checkpoint identity changed during execution or dispatch."
        )


def _compute_chain_digest(chain: Any) -> str:
    """SHA-256 of the execution-order FQN list."""
    fqns = []
    for node_id in chain.execution_order:
        fqns.append(chain.get_node(node_id).method_fqn)
    payload = json.dumps(fqns, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _compute_execution_digest(
    chain: Any,
    *,
    initial_state: Mapping[str, Any],
    params_per_node: Mapping[UUID, Mapping[str, Any]],
    seed: int,
    identity_snapshot: Mapping[str, Any] | None = None,
) -> str:
    """Bind a checkpoint to the effective execution request.

    ``_compute_chain_digest`` remains the filename-compatible structural digest
    used by legacy checkpoints.  This second, persisted identity includes the
    compiled node occurrence, effective parameters, initial input, and seed so
    a structurally similar chain cannot silently reuse stale work.
    """
    nodes: list[dict[str, Any]] = []
    for node_id in chain.execution_order:
        node = chain.get_node(node_id)
        signature = None
        get_signature = getattr(chain, "get_signature", None)
        if get_signature is not None:
            candidate = get_signature(node_id)
            stable_digest = getattr(candidate, "stable_digest", None)
            signature = stable_digest() if stable_digest is not None else None
        effective_params = dict(getattr(node, "params", {}))
        effective_params.update(dict(params_per_node.get(node_id, {})))
        nodes.append(
            {
                "node_id": str(node_id),
                "method_fqn": node.method_fqn,
                "params": effective_params,
                "static_params": dict(getattr(node, "static_params", {})),
                "signature_digest": signature,
                "cache_key": str(getattr(chain, "cache_keys", {}).get(node_id, "")),
            }
        )

    bindings: list[dict[str, Any]] = []
    for binding in getattr(chain, "bindings", ()):
        compatibility = getattr(binding, "compatibility", None)
        compatibility_payload = None
        if compatibility is not None:
            source_slot = getattr(compatibility, "source_slot", None)
            target_slot = getattr(compatibility, "target_slot", None)
            compatibility_payload = {
                "compatible": compatibility.compatible,
                "source_slot": (
                    source_slot.stable_digest()
                    if source_slot is not None and hasattr(source_slot, "stable_digest")
                    else None
                ),
                "target_slot": (
                    target_slot.stable_digest()
                    if target_slot is not None and hasattr(target_slot, "stable_digest")
                    else None
                ),
                "warnings": list(compatibility.warnings),
                "reason": (
                    None
                    if compatibility.reason is None
                    else getattr(compatibility.reason, "value", str(compatibility.reason))
                ),
            }
        bindings.append(
            {
                "source_method": binding.source_method,
                "source_slot": binding.source_slot,
                "target_method": binding.target_method,
                "target_slot": binding.target_slot,
                "source_node_id": (
                    None if binding.source_node_id is None else str(binding.source_node_id)
                ),
                "target_node_id": (
                    None if binding.target_node_id is None else str(binding.target_node_id)
                ),
                "compatibility": compatibility_payload,
            }
        )

    dag = getattr(chain, "dag", None)
    predecessor_map = getattr(dag, "predecessors", {})
    return _stable_digest(
        {
            "execution_order": [str(node_id) for node_id in chain.execution_order],
            "nodes": nodes,
            "bindings": bindings,
            "predecessors": {
                str(node_id): sorted(
                    str(predecessor) for predecessor in predecessor_map.get(node_id, ())
                )
                for node_id in chain.execution_order
            },
            "initial_state": dict(initial_state),
            "seed": seed,
            "identity_snapshot": identity_snapshot,
        }
    )


def _validate_checkpoint_prefix(
    checkpoint: ChainCheckpoint,
    chain: Any,
    execution_order: list[UUID] | tuple[UUID, ...],
) -> None:
    """Reject a count-only or malformed completed prefix."""
    if checkpoint.n_completed > len(execution_order):
        raise CheckpointLoadError("Checkpoint completed prefix exceeds chain length.")
    if len(checkpoint.completed_node_ids) != checkpoint.n_completed:
        raise CheckpointLoadError("Checkpoint node-id count does not match completed FQNs.")
    if checkpoint.node_timing_ms and len(checkpoint.node_timing_ms) != checkpoint.n_completed:
        raise CheckpointLoadError("Checkpoint timing count does not match completed prefix.")

    for index, (node_id_text, method_fqn) in enumerate(
        zip(checkpoint.completed_node_ids, checkpoint.completed_fqns, strict=True)
    ):
        try:
            node_id = UUID(node_id_text)
        except (AttributeError, ValueError) as exc:
            raise CheckpointLoadError(
                f"Checkpoint contains an invalid completed node id: {node_id_text!r}."
            ) from exc
        expected_id = execution_order[index]
        expected_fqn = chain.get_node(expected_id).method_fqn
        if node_id != expected_id or method_fqn != expected_fqn:
            raise CheckpointLoadError(
                "Checkpoint completed nodes are not the current execution prefix."
            )


def _snapshot_node_result(
    node_id: UUID,
    method_fqn: str,
    result: MethodResult,
) -> dict[str, Any]:
    """Capture the persisted fields needed to reconstruct one real result."""
    reproducibility = result.reproducibility
    return {
        "node_id": str(node_id),
        "method_fqn": method_fqn,
        "output": result.output,
        "timing": {
            "wall_time_ms": result.timing.wall_time_ms,
            "cpu_time_ms": result.timing.cpu_time_ms,
            "compile_time_ms": result.timing.compile_time_ms,
        },
        "reproducibility": {
            "backend": reproducibility.backend.value,
            "determinism_tier": reproducibility.determinism_tier.value,
            "seed": reproducibility.seed,
            "library_versions": dict(reproducibility.library_versions),
            "solver_status": (
                None
                if reproducibility.solver_status is None
                else reproducibility.solver_status.value
            ),
            "solver_gap": reproducibility.solver_gap,
            "solver_iterations": reproducibility.solver_iterations,
            "fingerprint": reproducibility.fingerprint,
            "observed_tolerance_budget": dict(reproducibility.observed_tolerance_budget),
            "note": reproducibility.note,
        },
        "cross_backend_equivalence_ref": result.cross_backend_equivalence_ref,
        "slot_outputs": dict(result.slot_outputs),
        "artifacts": dict(result.artifacts),
        "warnings": list(result.warnings),
        "validated_bound": (
            None if result.validated_bound is None else result.validated_bound.as_dict()
        ),
    }


def _restore_node_result(
    snapshot: Mapping[str, Any],
    checkpoint: ChainCheckpoint,
) -> tuple[UUID, MethodResult]:
    """Restore one result from a complete checkpoint history snapshot."""
    try:
        node_id = UUID(str(snapshot["node_id"]))
        timing_data = snapshot["timing"]
        reproducibility_data = snapshot["reproducibility"]
        backend = ComputeBackend(reproducibility_data["backend"])
        determinism_tier = DeterminismTier(reproducibility_data["determinism_tier"])
        solver_status = reproducibility_data.get("solver_status")
        reproducibility = ReproducibilityInfo(
            backend=backend,
            determinism_tier=determinism_tier,
            seed=reproducibility_data.get("seed"),
            library_versions=dict(reproducibility_data.get("library_versions", {})),
            solver_status=(None if solver_status is None else SolverStatus(solver_status)),
            solver_gap=reproducibility_data.get("solver_gap"),
            solver_iterations=reproducibility_data.get("solver_iterations"),
            fingerprint=reproducibility_data.get("fingerprint"),
            observed_tolerance_budget=dict(
                reproducibility_data.get("observed_tolerance_budget", {})
            ),
            note=str(reproducibility_data.get("note", "")),
        )
        result = MethodResult(
            output=snapshot.get("output"),
            timing=MethodTiming(
                wall_time_ms=float(timing_data["wall_time_ms"]),
                cpu_time_ms=timing_data.get("cpu_time_ms"),
                compile_time_ms=timing_data.get("compile_time_ms"),
            ),
            reproducibility=reproducibility,
            cross_backend_equivalence_ref=snapshot.get("cross_backend_equivalence_ref"),
            slot_outputs=dict(snapshot.get("slot_outputs", {})),
            artifacts=dict(snapshot.get("artifacts", {})),
            warnings=tuple(snapshot.get("warnings", ())),
            validated_bound=_restore_validated_bound(snapshot.get("validated_bound")),
        )
        return node_id, result
    except (KeyError, TypeError, ValueError) as exc:
        path = checkpoint.checkpoint_path or Path("<checkpoint>")
        raise CheckpointLoadError(
            f"Failed to restore per-node result history from {path}: {exc}"
        ) from exc


def _restore_validated_bound(payload: Any) -> ValidatedBound | None:
    if payload is None:
        return None
    if not isinstance(payload, Mapping):
        raise TypeError("validated_bound must be a mapping or null")
    return ValidatedBound(
        status=ValidatedStatus(payload["status"]),
        quantity=str(payload["quantity"]),
        lower=_restore_bound_payload(payload.get("lower")),
        upper=_restore_bound_payload(payload.get("upper")),
        contains_point_estimate=payload.get("contains_point_estimate"),
        method_family=ValidatedMethodFamily(payload["method_family"]),
        engine=str(payload["engine"]),
        precision_bits=payload.get("precision_bits"),
        polynomial_order=payload.get("polynomial_order"),
        subdivisions=payload.get("subdivisions"),
        witness=dict(payload.get("witness", {})),
        cost=dict(payload.get("cost", {})),
        semantics=dict(payload.get("semantics", {})),
    )


def _restore_bound_payload(value: Any) -> float | tuple[float, ...] | None:
    if isinstance(value, list):
        return tuple(float(item) for item in value)
    if value is None:
        return None
    return float(value)


@contextmanager
def _checkpoint_write_lock(path: Path) -> Iterator[None]:
    """Serialize writers for one manifest without deleting a peer generation."""
    lock_path = path.with_name(f".{path.name}.lock")
    with lock_path.open("a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _iter_array_paths(value: Any, path: tuple[str, ...] = ()):
    if isinstance(value, np.ndarray):
        yield path
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _iter_array_paths(child, path + (str(key),))
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _iter_array_paths(child, path + (str(index),))


def _legacy_sidecar_names(state: Mapping[str, Any], stem: str) -> dict[tuple[str, ...], str]:
    """Build the historical flat names used by first-generation checkpoints."""
    return {path: f"{stem}_{'_'.join(path)}.npy" for path in _iter_array_paths(state)}


def _encoded_sidecar_name(stem: str, path: tuple[str, ...]) -> str:
    encoded = (
        base64.urlsafe_b64encode(
            json.dumps(list(path), ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        )
        .decode("ascii")
        .rstrip("=")
    )
    return f"{stem}__{encoded}.npy"


def _array_content_digest(value: np.ndarray) -> str:
    """Hash array semantics used by a manifest-bound sidecar reference."""
    if value.dtype.hasobject:
        raise CheckpointSerializationError("Object-dtype arrays cannot be checkpointed safely.")
    array = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(json.dumps(list(array.shape), separators=(",", ":")).encode("ascii"))
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _serialise_state(
    state: dict[str, Any],
    stem: str,
    *,
    force_encoded: bool = False,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Convert state to JSON form and extract arrays under unambiguous refs."""
    legacy_names = _legacy_sidecar_names(state, stem)
    legacy_values = list(legacy_names.values())
    use_encoded = force_encoded or len(legacy_values) != len(set(legacy_values))
    sidecar_names = {
        path: (_encoded_sidecar_name(stem, path) if use_encoded else legacy_name)
        for path, legacy_name in legacy_names.items()
    }
    sidecars: dict[str, np.ndarray] = {}

    def encode(value: Any, path: tuple[str, ...]) -> Any:
        if isinstance(value, np.ndarray):
            sidecar_name = sidecar_names[path]
            sidecars[sidecar_name] = value
            return {
                "__npy_ref__": sidecar_name,
                "__npy_dtype__": value.dtype.str,
                "__npy_shape__": list(value.shape),
                "__npy_sha256__": _array_content_digest(value),
            }
        if isinstance(value, (bool, int, float, str, type(None))):
            return value
        if isinstance(value, Mapping):
            if any(not isinstance(key, str) for key in value):
                raise CheckpointSerializationError(
                    "Checkpoint mapping keys must be strings at " + repr(path)
                )
            if "__npy_ref__" in value:
                raise CheckpointSerializationError(
                    "Checkpoint mapping uses reserved array reference tag at " + repr(path)
                )
            return {key: encode(child, path + (str(key),)) for key, child in value.items()}
        if isinstance(value, (list, tuple)):
            return [encode(child, path + (str(index),)) for index, child in enumerate(value)]
        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError) as exc:
            raise CheckpointSerializationError(
                f"State value at '{'.'.join(path)}' of type {type(value).__name__} "
                "cannot be serialised to a checkpoint. Only JSON-serialisable values "
                "and numpy arrays are supported."
            ) from exc

    payload = encode(state, ())
    if not isinstance(payload, dict):
        raise CheckpointSerializationError("Checkpoint state root must be a mapping.")
    return payload, sidecars


def _deserialise_state(payload: Any, base_dir: Path) -> Any:
    """Inverse of ``_serialise_state`` for mappings and nested sequences."""
    if isinstance(payload, dict) and "__npy_ref__" in payload:
        sidecar_path = _resolve_sidecar_path(base_dir, payload)
        if not sidecar_path.exists():
            raise CheckpointLoadError(f"Checkpoint sidecar missing: {sidecar_path}")
        try:
            array = np.load(sidecar_path, allow_pickle=False)
        except (EOFError, OSError, ValueError) as exc:
            raise CheckpointLoadError(f"Checkpoint sidecar is unreadable: {sidecar_path}") from exc
        if not isinstance(array, np.ndarray):
            raise CheckpointLoadError(f"Checkpoint sidecar is not a NumPy array: {sidecar_path}")
        expected_shape = payload.get("__npy_shape__")
        expected_dtype = payload.get("__npy_dtype__")
        expected_digest = payload.get("__npy_sha256__")
        if (
            not isinstance(expected_shape, list)
            or not isinstance(expected_dtype, str)
            or not isinstance(expected_digest, str)
        ):
            raise CheckpointLoadError(
                f"Checkpoint sidecar content binding is missing: {sidecar_path}"
            )
        if list(array.shape) != expected_shape or array.dtype.str != expected_dtype:
            raise CheckpointLoadError(f"Checkpoint sidecar shape or dtype mismatch: {sidecar_path}")
        if _array_content_digest(array) != expected_digest:
            raise CheckpointLoadError(f"Checkpoint sidecar content mismatch: {sidecar_path}")
        return array
    if isinstance(payload, dict):
        return {key: _deserialise_state(value, base_dir) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_deserialise_state(value, base_dir) for value in payload]
    return payload


def _resolve_sidecar_path(base_dir: Path, payload: Mapping[str, Any]) -> Path:
    """Resolve a sidecar only within the checkpoint directory, without links."""
    return _resolve_checkpoint_member_path(base_dir, payload.get("__npy_ref__"))


def _resolve_checkpoint_member_path(base_dir: Path, reference: Any) -> Path:
    """Admit a snapshot or array only within its owning directory, without links."""
    if not isinstance(reference, str) or not reference:
        raise CheckpointLoadError("Checkpoint sidecar reference must be a non-empty string")
    relative = Path(reference)
    if relative.is_absolute() or ".." in relative.parts:
        raise CheckpointLoadError(
            f"Checkpoint sidecar reference escapes its directory: {reference}"
        )
    root = base_dir.resolve()
    candidate = root.joinpath(*relative.parts)
    cursor = root
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise CheckpointLoadError(f"Checkpoint sidecar path contains a symlink: {reference}")
    try:
        resolved = candidate.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise CheckpointLoadError(f"Checkpoint sidecar path is invalid: {reference}") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise CheckpointLoadError(
            f"Checkpoint sidecar reference escapes its directory: {reference}"
        ) from exc
    return candidate


def _tmp_path_for(path: Path) -> Path:
    return path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")


def _atomic_save_numpy(tmp_path: Path, final_path: Path, arr: np.ndarray) -> None:
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    with tmp_path.open("wb") as fh:
        np.save(fh, arr, allow_pickle=False)
        fh.flush()
        os.fsync(fh.fileno())
    tmp_path.replace(final_path)
    _fsync_dir(final_path.parent)


def _atomic_write_bytes(
    tmp_path: Path,
    final_path: Path,
    data: bytes,
    *,
    on_publish: Callable[[], None] | None = None,
) -> None:
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    with tmp_path.open("wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    tmp_path.replace(final_path)
    if on_publish is not None:
        on_publish()
    _fsync_dir(final_path.parent)


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _cleanup_paths(paths: list[Path]) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            _logger.debug("checkpoint_temp_cleanup_failed path=%s", path)
