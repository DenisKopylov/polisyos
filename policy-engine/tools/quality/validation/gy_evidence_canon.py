#!/usr/bin/env python3
"""Reproducible (time-invariant) evidence hashing for GY Task 0 smokes.

The first census smokes baked wall-clock timing (`ms`, `seconds`, `vector_ms`,
`duration_ms`, timestamps) into the hashed blob, so re-running produced a
different `output_hash`. That made the evidence prove *presence*, not *replay*.

`canonical_evidence_hash` strips volatile fields recursively and hashes a
canonical JSON serialization, so the same logical result hashes identically
across runs regardless of timing/ordering. Use it for every recorded smoke
`output_hash` going forward.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

# keys whose values are run-to-run volatile and must never enter an evidence hash
_VOLATILE_KEYS = {
    "ms", "seconds", "secs", "elapsed", "elapsed_s", "elapsed_ms",
    "vector_ms", "text_ms", "duration_ms", "duration_s", "took_ms",
    "timestamp", "generated_at", "started_at", "finished_at", "created_at",
    "wall_time", "wall_clock", "now", "run_at", "executed_at",
}
# suffix patterns that mark volatile timing/latency fields
_VOLATILE_SUFFIX = re.compile(r".*(_ms|_secs?|_at|_ns|_us|_latency|_duration)$")


def _is_volatile(key: str) -> bool:
    k = key.lower()
    return k in _VOLATILE_KEYS or bool(_VOLATILE_SUFFIX.fullmatch(k))


def strip_volatile(obj: Any) -> Any:
    """Recursively drop volatile timing/timestamp fields from a JSON-like object."""
    if isinstance(obj, dict):
        return {k: strip_volatile(v) for k, v in obj.items() if not _is_volatile(str(k))}
    if isinstance(obj, (list, tuple)):
        return [strip_volatile(v) for v in obj]
    return obj


def canonical_evidence_hash(obj: Any) -> str:
    """Return `sha256:<hex>` over the time-stripped, canonically serialized object.

    Two results that differ only in timing/timestamps/ordering hash identically.
    """
    stripped = strip_volatile(obj)
    payload = json.dumps(stripped, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


__all__ = ["canonical_evidence_hash", "strip_volatile"]


if __name__ == "__main__":  # tiny self-check
    a = {"returned": 8, "ms": 7247.2, "top": [{"id": "x", "sim": 1.0}]}
    b = {"returned": 8, "ms": 11.9, "top": [{"id": "x", "sim": 1.0}]}
    assert canonical_evidence_hash(a) == canonical_evidence_hash(b), "timing must not affect hash"
    print("canonical_evidence_hash OK:", canonical_evidence_hash(a))
