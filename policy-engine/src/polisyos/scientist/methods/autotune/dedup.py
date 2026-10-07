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

        from polisyos.scientist.methods.search.frontier import policy_candidate_hash

        # Native proposal IDs/acquisition diagnostics are technical envelopes;
        # explicitly declared independent replicas still own physical calls.
        replicas = {
            name: {
                key: values[key]
                for key in ("replicate_id", "replica_id", "seed")
                if key in values
            }
            for name, values in (
                ("candidate", payload),
                ("metadata", payload.get("metadata", {})),
                ("strategy", payload.get("_strategy_metadata", {})),
            )
            if isinstance(values, dict)
        }
        canonical = json.dumps(
            {"candidate": policy_candidate_hash(payload), "replicas": replicas},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def is_duplicate(
        self, candidate: MutationArtifact | dict[str, Any], loop_id: str = ""
    ) -> bool:
        """Check if this candidate has been seen before."""
        digest = self.fingerprint(candidate)
        seen = self._seen.get(loop_id, set())
        return digest in seen

    def register(
        self, candidate: MutationArtifact | dict[str, Any], loop_id: str = ""
    ) -> TrialFingerprint:
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
