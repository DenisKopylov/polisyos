"""Checkpoint markers for long-running nodes."""

from __future__ import annotations

from polisyos.scientist.orchestration.engine.protocol import NodeEvent

CHECKPOINT_CODE = "node.checkpoint"


def emit_checkpoint(
    node_id: str,
    progress: float,
    label: str = "",
) -> NodeEvent:
    """Create a checkpoint marker event.

    The engine can intercept events with ``code="node.checkpoint"``
    to persist intermediate state for long-running nodes.

    Parameters
    ----------
    node_id:
        Identifier of the emitting node.
    progress:
        Completion fraction in [0.0, 1.0].
    label:
        Optional human-readable label (e.g. ``"phase_2_complete"``).
    """
    clamped = max(0.0, min(1.0, progress))
    return NodeEvent(
        level="info",
        code=CHECKPOINT_CODE,
        message=f"Checkpoint: {label or node_id} ({clamped:.0%})",
        attrs={
            "node_id": node_id,
            "progress": int(clamped * 100),
            **({"label": label} if label else {}),
        },
    )


__all__ = [
    "CHECKPOINT_CODE",
    "emit_checkpoint",
]
