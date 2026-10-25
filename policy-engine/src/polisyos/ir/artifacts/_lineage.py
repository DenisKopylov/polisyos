"""Private structural lineage edge consumed by the IR persistence boundary."""

from __future__ import annotations

from typing import Protocol


class _StringRootArtifactID(Protocol):
    """Expose the validated string root shared by Core and IR artifact IDs."""

    @property
    def root(self) -> str: ...


class InputRefLike(Protocol):
    """Expose one Core or IR lineage edge without changing its selected profile."""

    @property
    def artifact_id(self) -> _StringRootArtifactID: ...

    @property
    def role(self) -> str: ...

    @property
    def manifest_profile_sha256(self) -> str | None: ...
