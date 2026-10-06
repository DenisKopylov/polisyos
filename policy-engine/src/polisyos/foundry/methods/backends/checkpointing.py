"""
Checkpoint-based Chain Execution.

Long method chains (causal discovery → estimation → sensitivity → welfare)
can fail partway through due to transient errors, OOM, or external service
timeouts.  ``CheckpointingChainExecutor`` saves intermediate states to disk
after every *N* nodes and can resume from the last valid checkpoint,
skipping already-completed work.

How it works
------------
1. After a completed node, a checkpoint is written every ``checkpoint_every``
   nodes and after the last node.
2. On resume, the executor validates effective execution identity and the
   completed occurrence prefix, then restores original per-node results.
3. Node parameters, slot bindings, and input materialization use the same
   helpers as sequential chain execution; runtime seed is passed separately.

Checkpoint format
-----------------
Each checkpoint is a JSON file containing:

- ``chain_digest``: hex SHA-256 of the execution order FQN list.
- ``completed_fqns``: list of FQNs completed so far.
- ``execution_digest``: identity of the plan, effective parameters, inputs, and seed.
- ``node_results``: original outputs, slot outputs, artifacts, timing, and reproducibility.
- ``intermediate_state``: JSON-serialisable state dict after last completed node.
- ``created_at``: Unix timestamp of checkpoint creation.

Limitations
-----------
- State values must be JSON-serialisable or NumPy arrays. Arbitrary Python objects in state
  will cause a ``CheckpointSerializationError``.
- NumPy arrays are serialised with ``np.save`` to a companion ``.npy`` sidecar
  file; the checkpoint JSON contains a ``__npy_ref__`` pointer.
- A failed directory sync after manifest replacement reports uncertain durability
  while preserving its referenced sidecars. It does not roll back publication.
- Currency conversion bindings requiring an external FX provider are not supported
  by this executor; they fail the canonical binding adapter's provider check.

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
import json
import logging
import os
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import numpy as np

from polisyos.core.observability import DeterminismTier
from polisyos.foundry.methods.backends.chain_executor import (
    ChainExecutionResult,
    _adapt_execution_context,
    _build_chain_reproducibility_contract,
    _build_node_param_payload,
    _collect_node_inputs,
    _merge_execution_context,
)
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodTiming,
    ReproducibilityInfo,
    SolverStatus,
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
    "CheckpointDigestMismatchError",
    "CheckpointError",
    "CheckpointIssue",
    "CheckpointLoadError",
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


class CheckpointLoadError(CheckpointError):
    """Raised when a checkpoint cannot be loaded or validated."""


class CheckpointDigestMismatchError(CheckpointError):
    """Raised when a checkpoint's chain_digest doesn't match the current chain."""


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
    checkpoint_path: Path | None = field(default=None, compare=False, repr=False)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Path) -> None:
        """Serialise to *path* (JSON + optional .npy sidecars)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_paths: list[Path] = []
        published_sidecars: list[Path] = []
        manifest_published = False
        try:
            with _checkpoint_write_lock(path):
                try:
                    generation = _checkpoint_generation(path, self.intermediate_state)
                    stem = path.stem if generation is None else f"{path.stem}.gen-{generation}"
                    force_encoded = generation is not None
                    payload, sidecars = _serialise_state(
                        self.intermediate_state,
                        stem,
                        force_encoded=force_encoded,
                    )
                    history_payload: dict[str, Any] | None = None
                    if self.history_complete:
                        history_payload, history_sidecars = _serialise_state(
                            {"node_results": self.node_results},
                            stem,
                            force_encoded=True,
                        )
                        sidecars.update(history_sidecars)
                    data = {
                        "chain_digest": self.chain_digest,
                        "completed_fqns": self.completed_fqns,
                        "completed_node_ids": self.completed_node_ids,
                        "intermediate_state": payload,
                        "node_timing_ms": self.node_timing_ms,
                        "created_at": self.created_at,
                        "execution_digest": self.execution_digest,
                        "history_complete": self.history_complete,
                    }
                    if history_payload is not None:
                        data["node_results"] = history_payload["node_results"]

                    for sidecar_name, arr in sidecars.items():
                        sidecar_path = path.parent / sidecar_name
                        published_sidecars.append(sidecar_path)
                        tmp_sidecar = _tmp_path_for(sidecar_path)
                        tmp_paths.append(tmp_sidecar)
                        _atomic_save_numpy(tmp_sidecar, sidecar_path, arr)
                        tmp_paths.remove(tmp_sidecar)

                    json_bytes = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
                    tmp_json = _tmp_path_for(path)
                    tmp_paths.append(tmp_json)
                    # Track the actual publication boundary before directory sync.
                    # A sync error can leave the complete new manifest visible;
                    # deleting its sidecars would turn that uncertainty into loss.
                    _atomic_write_bytes(tmp_json, path, json_bytes, fsync_directory=False)
                    manifest_published = True
                    tmp_paths.remove(tmp_json)
                    _fsync_dir(path.parent)
                    self.checkpoint_path = path
                except (OSError, TypeError, ValueError, CheckpointSerializationError):
                    # Rollback owns these paths until cleanup finishes. A peer
                    # must not publish a cold manifest reusing them meanwhile.
                    _cleanup_paths(tmp_paths)
                    if not manifest_published:
                        _cleanup_paths(published_sidecars)
                    raise
        except (OSError, TypeError, ValueError, CheckpointSerializationError) as exc:
            raise CheckpointSaveError(f"Failed to save checkpoint at {path}: {exc}") from exc

    @classmethod
    def load(cls, path: Path) -> ChainCheckpoint:
        """Deserialise from *path*."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            state = _deserialise_state(data.pop("intermediate_state"), path.parent)
            node_results: list[dict[str, Any]] = []
            if "node_results" in data:
                node_results_payload = _deserialise_state(
                    {"node_results": data.pop("node_results")},
                    path.parent,
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
                history_complete=bool(data.get("history_complete", False)),
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
    ) -> None:
        self._checkpoint_dir = checkpoint_dir
        self._checkpoint_every = max(1, checkpoint_every)
        self._registry = registry
        self._dispatcher = dispatcher
        self._fail_on_checkpoint_error = fail_on_checkpoint_error
        self._checkpoint_issues: list[CheckpointIssue] = []

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

        chain_digest = _compute_chain_digest(chain)
        execution_digest = None
        if checkpoint is not None or self._checkpoint_dir is not None:
            execution_digest = _compute_execution_digest(
                chain,
                initial_state=initial_state,
                params_per_node=params_per_node,
                seed=seed,
            )
        execution_order: list[UUID] = chain.execution_order

        # Validate checkpoint if provided
        skip_until: int = 0
        state = dict(initial_state)
        execution_context: Any = dict(initial_state)
        previous_backend: ComputeBackend | None = None
        all_node_results: list[tuple[UUID, MethodResult]] = []
        node_slot_outputs: dict[UUID, dict[str, Any]] = {}

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
            skip_until = checkpoint.n_completed
            state = dict(checkpoint.intermediate_state)
            if checkpoint.history_complete:
                if len(checkpoint.node_results) != skip_until:
                    raise CheckpointLoadError(
                        "Checkpoint marks node history complete but the saved "
                        "per-node result count does not match completed prefix."
                    )
                for index, snapshot in enumerate(checkpoint.node_results):
                    restored = _restore_node_result(snapshot, checkpoint)
                    expected_node_id = execution_order[index]
                    expected_fqn = chain.get_node(expected_node_id).method_fqn
                    if (
                        restored[0] != expected_node_id
                        or snapshot.get("method_fqn") != expected_fqn
                    ):
                        raise CheckpointLoadError(
                            "Checkpoint per-node history does not match the execution prefix."
                        )
                    all_node_results.append(restored)
                    node_slot_outputs[restored[0]] = dict(restored[1].slot_outputs)
                    execution_context = _merge_execution_context(
                        execution_context, restored[1].output
                    )
                    previous_backend = restored[1].reproducibility.backend
            elif skip_until:
                # The state remains usable, but no per-node outputs can be
                # reconstructed or substituted for missing binding sources.
                execution_context = dict(state)
                previous_backend = chain.get_signature(execution_order[skip_until - 1]).backend

        # Execute remaining nodes
        for idx, node_id in enumerate(execution_order):
            if idx < skip_until:
                continue

            signature = chain.get_signature(node_id)
            if previous_backend is not None and previous_backend is not signature.backend:
                execution_context = _adapt_execution_context(
                    execution_context,
                    source_backend=previous_backend,
                    target_backend=signature.backend,
                )
            method_class, materialized_state, signature, node_params = _collect_node_inputs(
                chain=chain,
                node_id=node_id,
                reg=reg,
                node_slot_outputs=node_slot_outputs,
                fx_rate_provider=None,
                current_state=state,
                signature=signature,
                current_context=execution_context,
                params_per_node=params_per_node,
            )
            result = disp.dispatch(
                method_class=method_class,
                signature=signature,
                state=materialized_state,
                params=node_params,
                seed=seed,
            )
            if isinstance(result.output, dict):
                state.update(result.output)
            execution_context = _merge_execution_context(execution_context, result.output)
            previous_backend = signature.backend
            node_slot_outputs[node_id] = dict(result.slot_outputs)
            all_node_results.append((node_id, result))

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
                )

        reproducibility_contract = _build_chain_reproducibility_contract(
            all_node_results,
            composition_kind="serial",
        )
        if checkpoint is not None and skip_until and not checkpoint.history_complete:
            reproducibility_contract.update(
                checkpoint_history_complete=False,
                checkpoint_completed_nodes=skip_until,
                history_limitation="checkpoint_per_node_history_missing",
            )
        return ChainExecutionResult(
            final_state=state,
            node_results=tuple(all_node_results),
            reproducibility_contract=reproducibility_contract,
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
    ) -> None:
        if self._checkpoint_dir is None:
            raise CheckpointSaveError("checkpoint_dir is not configured")
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        filename = f"checkpoint_{chain_digest[:8]}_{completed_up_to_idx:04d}_{timestamp}.json"
        path = self._checkpoint_dir / filename

        completed_node_ids = [str(nid) for nid, _ in all_node_results]
        completed_fqns = [chain.get_node(nid).method_fqn for nid, _ in all_node_results]
        timing_ms = [r.timing.wall_time_ms for _, r in all_node_results]
        history_complete = all(
            isinstance(result, MethodResult) and "history_incomplete" not in result.warnings
            for _, result in all_node_results
        )
        node_results = (
            [
                _snapshot_node_result(node_id, chain.get_node(node_id).method_fqn, result)
                for node_id, result in all_node_results
            ]
            if history_complete
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
        effective_params = _build_node_param_payload(node, params_per_node)
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


def _checkpoint_generation(path: Path, state: Mapping[str, Any]) -> str | None:
    """Return a unique sidecar generation when a checkpoint path is reused."""
    if path.exists():
        return uuid4().hex
    for sidecar_name in _legacy_sidecar_names(state, path.stem).values():
        if (path.parent / sidecar_name).exists():
            return uuid4().hex
    return None


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
    reference = payload.get("__npy_ref__")
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
    tmp_path: Path, final_path: Path, data: bytes, *, fsync_directory: bool = True
) -> None:
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    with tmp_path.open("wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    tmp_path.replace(final_path)
    if fsync_directory:
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
