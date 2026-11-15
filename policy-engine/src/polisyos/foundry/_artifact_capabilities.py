"""Foundry capability resolution for profile-bound Core JSON reads."""

from __future__ import annotations

from typing import Protocol

from polisyos.core.artifacts.ir_adapter import CoreToIRArtifactStoreAdapter
from polisyos.core.artifacts.protocol import (
    ArtifactStore,
    CoreJSONArtifactProfileReader,
    CoreJSONArtifactStore,
    VerifiableArtifactReader,
    matches_runtime_protocol,
)


class _VerifiableCoreJSONArtifactProfileReader(
    CoreJSONArtifactProfileReader, VerifiableArtifactReader, Protocol
):
    """Compose exact-profile reads with the verifier required by semantic replay."""


def _core_json_profile_owner(store: object) -> object:
    """Resolve only the exact repository adapter to its configured Core owner."""
    if type(store) is CoreToIRArtifactStoreAdapter:
        return store.store
    return store


def resolve_core_json_profile_reader(
    store: ArtifactStore | CoreJSONArtifactProfileReader,
) -> CoreJSONArtifactProfileReader | None:
    """Resolve the actual owner for strict, read-only Core JSON profile reads.

    The exact repository Core-to-IR adapter is resolved to its configured owner.
    All other handles, including adapter subclasses, are checked as provided.
    This structural preflight is followed by the selected-profile read, which
    validates the persisted raw manifest and payload at the point of use.

    Args:
        store: The Core artifact handle supplied to a Foundry read path.

    Returns:
        The actual Core JSON profile reader, or None when unavailable.
    """
    protocol_owner = _core_json_profile_owner(store)
    if matches_runtime_protocol(protocol_owner, CoreJSONArtifactProfileReader):
        return protocol_owner
    return None


def resolve_verifiable_core_json_profile_reader(
    store: ArtifactStore | CoreJSONArtifactProfileReader,
) -> _VerifiableCoreJSONArtifactProfileReader | None:
    """Resolve a profile reader that also exposes the existing verifier contract.

    This stricter view is for read paths whose semantic contract independently
    requires integrity verification in addition to exact profile reads.

    Args:
        store: The Core artifact handle supplied to a verification-dependent read path.

    Returns:
        The actual reader/verifier owner, or None when either capability is absent.
    """
    protocol_owner = _core_json_profile_owner(store)
    if matches_runtime_protocol(protocol_owner, _VerifiableCoreJSONArtifactProfileReader):
        return protocol_owner
    return None


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
    protocol_owner = _core_json_profile_owner(store)
    if matches_runtime_protocol(protocol_owner, CoreJSONArtifactStore):
        return protocol_owner
    return None
