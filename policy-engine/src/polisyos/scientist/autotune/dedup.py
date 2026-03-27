"""Trial deduplication via content hashing."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel

from .models import MutationArtifact


class TrialFingerprint(BaseModel):
    """Content-based fingerprint for a trial candidate."""

    digest: str
    loop_id: str


class TrialDeduplicator:
    """Deduplicates trial candidates by content hash.

    Prevents re-evaluation of identical parameter configurations within
    the same autotune loop.
    """

    def __init__(self) -> None:
        self._seen: dict[str, set[str]] = {}

    def fingerprint(self, candidate: MutationArtifact | dict[str, Any]) -> str:
        """Compute a deterministic content hash for a candidate."""
        if isinstance(candidate, BaseModel):
            payload = candidate.model_dump(mode="json")
        else:
            payload = dict(candidate)

        # Remove non-deterministic fields
        payload.pop("notes", None)

        canonical = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def is_duplicate(self, candidate: MutationArtifact | dict[str, Any], loop_id: str = "") -> bool:
        """Check if this candidate has been seen before."""
        digest = self.fingerprint(candidate)
        seen = self._seen.get(loop_id, set())
        return digest in seen

    def register(self, candidate: MutationArtifact | dict[str, Any], loop_id: str = "") -> TrialFingerprint:
        """Register a candidate as seen. Returns its fingerprint."""
        digest = self.fingerprint(candidate)
        if loop_id not in self._seen:
            self._seen[loop_id] = set()
        self._seen[loop_id].add(digest)
        return TrialFingerprint(digest=digest, loop_id=loop_id)

    def reset(self, loop_id: str | None = None) -> None:
        """Clear seen candidates for a loop (or all loops)."""
        if loop_id is None:
            self._seen.clear()
        else:
            self._seen.pop(loop_id, None)

    def count(self, loop_id: str = "") -> int:
        """Number of unique candidates seen for a loop."""
        return len(self._seen.get(loop_id, set()))
