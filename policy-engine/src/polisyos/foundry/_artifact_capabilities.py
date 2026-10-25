"""Foundry capability resolution for profile-bound Core JSON reads."""

from __future__ import annotations

from polisyos.core.artifacts.ir_adapter import CoreToIRArtifactStoreAdapter
from polisyos.core.artifacts.protocol import (
    ArtifactStore,
    CoreJSONArtifactStore,
    matches_runtime_protocol,
)


def resolve_core_json_profile_store(
    store: ArtifactStore,
) -> CoreJSONArtifactStore | None:
    """Resolve the actual owner for strict profile reads.

    The exact repository Core-to-IR adapter is resolved to its configured owner.
    All other handles, including adapter subclasses, are checked as provided.
    This structural preflight is followed by the actual selected-profile read;
    the reader preserves a typed refusal when a delegated raw reader is unavailable.
    A guarded owner stays intact, and no arbitrary wrapper is unwrapped.

    Args:
        store: The generic store supplied to a Foundry compile or execute call.

    Returns:
        The actual Core JSON profile store, or None when unavailable.
    """
    if type(store) is CoreToIRArtifactStoreAdapter:
        protocol_owner: object = store.store
    else:
        protocol_owner = store
    if matches_runtime_protocol(protocol_owner, CoreJSONArtifactStore):
        return protocol_owner
    return None
