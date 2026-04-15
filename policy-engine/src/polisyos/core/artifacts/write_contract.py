"""Backend-agnostic artifact write metadata contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .manifest import (
        ArtifactGovernanceInfo,
        CanonInfo,
        EnvInfo,
        InputRef,
        ProducerInfo,
        SchemaInfo,
    )


@dataclass(frozen=True)
class ArtifactWriteOptions:
    """Control manifest metadata attached when writing a new CAS artifact."""

    kind: str
    media_type: str
    schema: SchemaInfo | None = None
    producer: ProducerInfo | None = None
    env: EnvInfo | None = None
    inputs: list[InputRef] | None = None
    canon: CanonInfo | None = None
    governance: ArtifactGovernanceInfo | None = None


__all__ = ["ArtifactWriteOptions"]
