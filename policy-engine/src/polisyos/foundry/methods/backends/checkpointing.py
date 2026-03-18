"""
Checkpoint-based Chain Execution.

Long method chains (causal discovery → estimation → sensitivity → welfare)
can fail partway through due to transient errors, OOM, or external service
timeouts.  ``CheckpointingChainExecutor`` saves intermediate states to disk
after every *N* nodes and can resume from the last valid checkpoint,
skipping already-completed work.

How it works
------------
1. Before executing each node, a checkpoint is written to disk if the node
   index is a multiple of ``checkpoint_every`` or if this is the last node.
2. On resume, the executor reads the checkpoint, validates the chain digest
   matches, and fast-forwards past already-completed nodes.
3. The chain digest (SHA-256 of the ordered FQN list) guards against resuming
   a checkpoint from a different chain definition.

Checkpoint format
-----------------
Each checkpoint is a JSON file containing:

- ``chain_digest``: hex SHA-256 of the execution order FQN list.
- ``completed_fqns``: list of FQNs completed so far.
- ``node_results``: list of ``{node_uid, method_fqn, wall_time_ms}`` dicts.
- ``intermediate_state``: JSON-serialisable state dict after last completed node.
- ``created_at``: ISO-8601 UTC timestamp.

Limitations
-----------
- State values must be JSON-serialisable (or numpy arrays, which are
  serialised as base64-encoded bytes).  Arbitrary Python objects in state
  will cause a ``CheckpointSerializationError``.
- NumPy arrays are serialised with ``np.save`` to a companion ``.npy`` sidecar
  file; the checkpoint JSON contains a ``__npy_ref__`` pointer.

Usage
-----
::

    executor = CheckpointingChainExecutor(checkpoint_dir=Path("/tmp/checkpoints"))

    # First run — may fail partway through
    try:
        result = executor.execute(chain, initial_state=state)
    except Exception:
        pass

    # Resume — skips already-completed nodes
    checkpoint = executor.find_latest_checkpoint(chain)
    result = executor.execute(chain, initial_state=state, checkpoint=checkpoint)
"""
from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID

import numpy as np

from polisyos.foundry.methods.backends.chain_executor import (
    ChainExecutionResult,
    execute_heterogeneous_chain,
)
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.protocol import MethodResult, MethodTiming, ReproducibilityInfo
from polisyos.foundry.methods.registry import MethodRegistry, get_registry

__all__ = [
    "ChainCheckpoint",
    "CheckpointingChainExecutor",
    "CheckpointSerializationError",
    "CheckpointDigestMismatchError",
]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CheckpointSerializationError(Exception):
    """Raised when state cannot be serialised to a checkpoint."""


class CheckpointDigestMismatchError(Exception):
    """Raised when a checkpoint's chain_digest doesn't match the current chain."""


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
    completed_node_ids: list[str]   # UUID as str
    intermediate_state: dict[str, Any]
    node_timing_ms: list[float] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    checkpoint_path: Path | None = field(default=None, compare=False, repr=False)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Path) -> None:
        """Serialise to *path* (JSON + optional .npy sidecars)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        payload, sidecars = _serialise_state(self.intermediate_state, path.stem)
        data = {
            "chain_digest": self.chain_digest,
            "completed_fqns": self.completed_fqns,
            "completed_node_ids": self.completed_node_ids,
            "intermediate_state": payload,
            "node_timing_ms": self.node_timing_ms,
            "created_at": self.created_at,
        }
        path.write_text(json.dumps(data, indent=2))
        # Write numpy sidecars alongside the JSON
        for sidecar_name, arr in sidecars.items():
            np.save(path.parent / sidecar_name, arr)
        object.__setattr__(self, "checkpoint_path", path) if hasattr(self, "__dataclass_fields__") else None
        self.checkpoint_path = path

    @classmethod
    def load(cls, path: Path) -> "ChainCheckpoint":
        """Deserialise from *path*."""
        data = json.loads(path.read_text())
        state = _deserialise_state(data.pop("intermediate_state"), path.parent)
        chk = cls(
            chain_digest=data["chain_digest"],
            completed_fqns=data["completed_fqns"],
            completed_node_ids=data["completed_node_ids"],
            intermediate_state=state,
            node_timing_ms=data.get("node_timing_ms", []),
            created_at=data.get("created_at", 0.0),
            checkpoint_path=path,
        )
        return chk

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
    ) -> None:
        self._checkpoint_dir = checkpoint_dir
        self._checkpoint_every = max(1, checkpoint_every)
        self._registry = registry
        self._dispatcher = dispatcher

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
        execution_order: list[UUID] = chain.execution_order

        # Validate checkpoint if provided
        skip_until: int = 0
        state = dict(initial_state)
        all_node_results: list[tuple[UUID, MethodResult]] = []

        if checkpoint is not None:
            if checkpoint.chain_digest != chain_digest:
                raise CheckpointDigestMismatchError(
                    f"Checkpoint digest {checkpoint.chain_digest!r} does not match "
                    f"chain digest {chain_digest!r}. "
                    "The checkpoint was created for a different chain."
                )
            skip_until = checkpoint.n_completed
            state = dict(checkpoint.intermediate_state)
            # Reconstruct stub results for already-completed nodes
            for i, (node_id, fqn, ms) in enumerate(zip(
                [UUID(s) for s in checkpoint.completed_node_ids],
                checkpoint.completed_fqns,
                checkpoint.node_timing_ms or [0.0] * skip_until,
            )):
                stub_result = MethodResult(
                    output=state,
                    timing=MethodTiming(wall_time_ms=ms, jit_compile_ms=0.0),
                    reproducibility=ReproducibilityInfo(seed=seed, backend="restored"),
                    status="restored_from_checkpoint",
                )
                all_node_results.append((node_id, stub_result))

        # Execute remaining nodes
        for idx, node_id in enumerate(execution_order):
            if idx < skip_until:
                continue

            node = chain.get_node(node_id)
            node_params = dict(node.params)
            node_params.update(params_per_node.get(node_id, {}))
            node_params.setdefault("seed", seed)

            method_class = reg.get(node.method_fqn)
            t0 = time.perf_counter()
            result = disp.dispatch(
                method_class=method_class,
                signature=method_class.signature,
                state=state,
                params=node_params,
                seed=seed,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000

            if isinstance(result.output, dict):
                state.update(result.output)
            all_node_results.append((node_id, result))

            # Save checkpoint if needed
            should_checkpoint = (
                self._checkpoint_dir is not None
                and (
                    (idx - skip_until + 1) % self._checkpoint_every == 0
                    or idx == len(execution_order) - 1
                )
            )
            if should_checkpoint:
                self._save_checkpoint(
                    chain=chain,
                    chain_digest=chain_digest,
                    completed_up_to_idx=idx,
                    execution_order=execution_order,
                    all_node_results=all_node_results,
                    state=state,
                )

        return ChainExecutionResult(
            final_state=state,
            node_results=tuple(all_node_results),
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
        if not candidates:
            return None
        try:
            return ChainCheckpoint.load(candidates[0])
        except Exception:
            return None

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
    ) -> None:
        assert self._checkpoint_dir is not None
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        filename = f"checkpoint_{chain_digest[:8]}_{completed_up_to_idx:04d}_{timestamp}.json"
        path = self._checkpoint_dir / filename

        completed_node_ids = [str(nid) for nid, _ in all_node_results]
        completed_fqns = [
            chain.get_node(nid).method_fqn for nid, _ in all_node_results
        ]
        timing_ms = [r.timing.wall_time_ms for _, r in all_node_results]

        chk = ChainCheckpoint(
            chain_digest=chain_digest,
            completed_fqns=completed_fqns,
            completed_node_ids=completed_node_ids,
            intermediate_state=state,
            node_timing_ms=timing_ms,
        )
        try:
            chk.save(path)
        except Exception:
            pass  # checkpoint failure must never abort execution


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


def _serialise_state(
    state: dict[str, Any], stem: str
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """
    Convert *state* to JSON-serialisable form, extracting numpy arrays as sidecars.

    Returns (json_payload, {sidecar_filename: array}).
    """
    payload: dict[str, Any] = {}
    sidecars: dict[str, np.ndarray] = {}

    for key, value in state.items():
        if isinstance(value, np.ndarray):
            sidecar_name = f"{stem}_{key}.npy"
            sidecars[sidecar_name] = value
            payload[key] = {"__npy_ref__": sidecar_name}
        elif isinstance(value, (bool, int, float, str, type(None))):
            payload[key] = value
        elif isinstance(value, (list, tuple)):
            payload[key] = list(value)
        elif isinstance(value, dict):
            sub_payload, sub_sidecars = _serialise_state(value, f"{stem}_{key}")
            payload[key] = sub_payload
            sidecars.update(sub_sidecars)
        else:
            # Try JSON serialisation; raise informative error on failure
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError) as exc:
                raise CheckpointSerializationError(
                    f"State key '{key}' of type {type(value).__name__} "
                    "cannot be serialised to a checkpoint. "
                    "Only JSON-serialisable values and numpy arrays are supported."
                ) from exc

    return payload, sidecars


def _deserialise_state(
    payload: dict[str, Any], base_dir: Path
) -> dict[str, Any]:
    """Inverse of ``_serialise_state``."""
    state: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, dict) and "__npy_ref__" in value:
            sidecar_path = base_dir / value["__npy_ref__"]
            if sidecar_path.exists():
                state[key] = np.load(sidecar_path)
            else:
                state[key] = None  # sidecar missing — best effort
        elif isinstance(value, dict):
            state[key] = _deserialise_state(value, base_dir)
        else:
            state[key] = value
    return state
