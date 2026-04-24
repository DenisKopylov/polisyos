"""Namespace utilities for multi-tenant artifact isolation."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from polisyos.core.artifacts._integrity_ops import VerificationReport
    from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.canon import CanonSpec

_SEPARATOR = ":"
_SEGMENT_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


def _validate_segment(value: str, name: str) -> None:
    """Validate a namespace segment (tenant_id or cell_id).

    Rules:
    * Must not contain the separator character ``:``.
    * Must match ``^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$``.
    """
    if not value:
        raise ValueError(f"{name} must not be empty")
    if _SEPARATOR in value:
        raise ValueError(f"{name} must not contain separator {_SEPARATOR!r}: {value!r}")
    if not _SEGMENT_PATTERN.match(value):
        raise ValueError(f"Invalid {name}: {value!r}")


def namespaced_artifact_id(tenant_id: str, cell_id: str | None, base_id: str) -> str:
    """Prefix an artifact id with validated tenant/cell namespace segments."""
    _validate_segment(tenant_id, "tenant_id")
    if cell_id is not None:
        _validate_segment(cell_id, "cell_id")
    prefix = f"{tenant_id}{_SEPARATOR}{cell_id}" if cell_id else tenant_id
    return f"{prefix}{_SEPARATOR}{base_id}"


def namespaced_run_id(tenant_id: str, cell_id: str | None, base_run_id: str) -> str:
    """Prefix a run id with validated tenant/cell namespace segments."""
    _validate_segment(tenant_id, "tenant_id")
    if cell_id is not None:
        _validate_segment(cell_id, "cell_id")
    prefix = f"{tenant_id}{_SEPARATOR}{cell_id}" if cell_id else tenant_id
    return f"{prefix}{_SEPARATOR}{base_run_id}"


def namespaced_lock_key(tenant_id: str, cell_id: str | None, key: str) -> str:
    """Prefix a lock key with validated tenant/cell namespace segments."""
    _validate_segment(tenant_id, "tenant_id")
    if cell_id is not None:
        _validate_segment(cell_id, "cell_id")
    prefix = f"{tenant_id}{_SEPARATOR}{cell_id}" if cell_id else tenant_id
    return f"{prefix}{_SEPARATOR}{key}"


def strip_namespace(namespaced_id: str) -> tuple[str, str | None, str]:
    """Extract tenant_id, cell_id, base_id from a namespaced ID.

    Returns (tenant_id, cell_id, base_id). cell_id is None if not present.
    """
    parts = namespaced_id.split(_SEPARATOR, maxsplit=2)
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    elif len(parts) == 2:
        return parts[0], None, parts[1]
    else:
        raise ValueError(f"Invalid namespaced ID: {namespaced_id!r}")


class NamespacedArtifactStore:
    """Wrapper around ArtifactStore that auto-prefixes all IDs with tenant namespace.

    Implements the same interface as ArtifactStore but adds tenant isolation
    by transparently prefixing artifact IDs.
    """

    def __init__(self, inner: Any, tenant_id: str, cell_id: str | None = None) -> None:
        self._inner = inner
        self._tenant_id = tenant_id
        self._cell_id = cell_id

    def _ns(self, artifact_id: str) -> str:
        """Add namespace prefix to an artifact ID."""
        return namespaced_artifact_id(self._tenant_id, self._cell_id, artifact_id)

    def has(self, artifact_id: str) -> bool:
        """Return whether a tenant-local artifact exists in the wrapped store."""
        return cast("bool", self._inner.has(self._ns(artifact_id)))

    def get_bytes(self, artifact_id: str) -> bytes:
        """Read namespaced artifact bytes from the wrapped store."""
        return cast("bytes", self._inner.get_bytes(self._ns(artifact_id)))

    def get_manifest(self, artifact_id: str) -> ArtifactManifest:
        """Read a namespaced artifact manifest from the wrapped store."""
        return cast("ArtifactManifest", self._inner.get_manifest(self._ns(artifact_id)))

    def put_bytes(self, data: bytes, opts: PutOptions | None = None) -> ArtifactRef:
        """Persist artifact bytes using the wrapped store's native write contract."""
        ref = cast("ArtifactRef", self._inner.put_bytes(data, opts))
        return ref

    def put_json(
        self,
        obj: Any,
        opts: PutOptions | None = None,
        canon_spec: CanonSpec | None = None,
    ) -> ArtifactRef:
        """Persist a JSON artifact using the wrapped store's native write contract."""
        ref = cast("ArtifactRef", self._inner.put_json(obj, opts, canon_spec))
        return ref

    def verify(self, artifact_id: str) -> VerificationReport:
        """Run integrity verification for a tenant-local artifact id."""
        return cast("VerificationReport", self._inner.verify(self._ns(artifact_id)))

    def iter_artifact_ids(self) -> list[str]:
        """Yield tenant-local ids with the namespace prefix stripped."""
        prefix = namespaced_artifact_id(self._tenant_id, self._cell_id, "")
        return [
            aid[len(prefix) :] for aid in self._inner.iter_artifact_ids() if aid.startswith(prefix)
        ]
