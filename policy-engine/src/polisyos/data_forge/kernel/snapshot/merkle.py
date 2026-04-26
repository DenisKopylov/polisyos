"""Merkle identity helpers for complete Data Forge snapshots."""

from __future__ import annotations

import polisyos.data_forge.kernel.artifacts as artifact_contracts
from polisyos.data_forge.kernel.io import sha256_bytes

ArtifactRef = artifact_contracts.ArtifactRef


def merkle_root(refs: tuple[ArtifactRef, ...]) -> str:
    """Return a deterministic Merkle root for artifact refs."""
    leaves = sorted(f"{ref.uri}\0{ref.sha256}".encode() for ref in refs)
    if not leaves:
        return sha256_bytes(b"")

    level = [sha256_bytes(leaf).encode("ascii") for leaf in leaves]
    while len(level) > 1:
        next_level: list[bytes] = []
        for index in range(0, len(level), 2):
            left = level[index]
            right = level[index + 1] if index + 1 < len(level) else left
            next_level.append(sha256_bytes(left + right).encode("ascii"))
        level = next_level
    return level[0].decode("ascii")


__all__ = ["merkle_root"]
