"""Read pinned historical owner bytes from ordinary append-only Git history."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

GENERATION_CYCLE_V1_BLOB = "adab90797d1d1562ae252c076883bc5af6d77ce6"
PROMOTION_EMITTER_BASE_BLOB = "2d0319f0eca7d3ef7f09f2f21c310c9d4fb796ea"


def historical_owner_bytes(blob: str) -> bytes:
    """Resolve and verify exact Git blob bytes, refusing unavailable history."""
    root = Path(__file__).resolve().parents[4]
    result = subprocess.run(
        ["git", "cat-file", "blob", blob],
        cwd=root,
        check=True,
        capture_output=True,
    )
    raw = result.stdout
    identity = hashlib.sha1(
        b"blob " + str(len(raw)).encode() + b"\0" + raw,
        usedforsecurity=False,
    ).hexdigest()
    if identity != blob:
        raise ValueError("historical_owner_blob_identity_mismatch")
    return raw


def historical_generation_cycle_v1() -> dict[str, Any]:
    """Return the original report while its current producer advances independently."""
    return json.loads(historical_owner_bytes(GENERATION_CYCLE_V1_BLOB))
