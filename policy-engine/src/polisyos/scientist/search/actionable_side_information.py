"""Replayable actionable side-information artifacts for funnel audit output."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from pydantic import ConfigDict, Field

from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.scientist.search.artifact_minimality import (
    ArtifactFunction,
    ArtifactMinimalityMixin,
    artifact_functions_field,
)

ActionableStoreFactory = Callable[[Path], ArtifactStore]

ACTIONABLE_SIDE_INFORMATION_SCHEMA_NAME = (
    "polisyos.scientist.search.ActionableSideInformation"
)


def _build_actionable_store(root: Path) -> ArtifactStore:
    return build_artifact_store(ArtifactStoreConfig(root=str(root)))


class ActionableSideInformation(ArtifactMinimalityMixin):
    """Canonical audit artifact for L4/L5/L6 diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.REPLAY_AUDIT,
            ArtifactFunction.CROSS_RUN_LEARNING,
        )
    )
    candidate_id: str = Field(min_length=1)
    profiler_output: dict[str, Any] = Field(default_factory=dict)
    timeout_diagnostics: dict[str, Any] = Field(default_factory=dict)
    identifiability_blockers: list[str] = Field(default_factory=list)
    sensitivity_failures: list[str] = Field(default_factory=list)
    subgroup_harm_notes: list[str] = Field(default_factory=list)
    legality_failures: list[str] = Field(default_factory=list)
    transport_failures: list[str] = Field(default_factory=list)
    discovery_ambiguity_notes: list[str] = Field(default_factory=list)
    policy_budget_explanation: dict[str, float] = Field(default_factory=dict)
    compute_budget_explanation: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


def persist_actionable_side_information(
    store: ArtifactStore,
    artifact: ActionableSideInformation,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist actionable side information that should travel with a promoted or replayable decision."""
    return store.put_json(
        artifact,
        ArtifactWriteOptions(
            kind="scientist.actionable_side_information",
            media_type="application/json",
            schema=SchemaInfo(
                name=ACTIONABLE_SIDE_INFORMATION_SCHEMA_NAME,
                version=artifact.schema_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_actionable_side_information(
    store: ArtifactStore,
    ref: ArtifactRef | str,
) -> ActionableSideInformation:
    """Load actionable side information."""
    artifact_id = (
        ref.artifact_id if isinstance(ref, ArtifactRef) else ArtifactID.model_validate(ref)
    )
    payload = from_canonical_bytes(store.get_bytes(artifact_id))
    return cast(
        "ActionableSideInformation",
        ActionableSideInformation.model_validate(payload),
    )


def resolve_actionable_store(
    *,
    context: dict[str, Any] | None = None,
    store: ArtifactStore | None = None,
    store_factory: ActionableStoreFactory | None = None,
) -> ArtifactStore | None:
    """Resolve a CAS store from an explicit value or stage context."""

    if store is not None:
        return store
    if context is None:
        return None
    context_store = context.get("store")
    if context_store is not None and hasattr(context_store, "get_bytes") and hasattr(context_store, "put_json"):
        return context_store
    cas_root = context.get("cas_root") or context.get("cas_dir")
    if cas_root is None:
        return None
    factory = store_factory or _build_actionable_store
    return factory(Path(str(cas_root)))


__all__ = [
    "ACTIONABLE_SIDE_INFORMATION_SCHEMA_NAME",
    "ActionableSideInformation",
    "load_actionable_side_information",
    "persist_actionable_side_information",
    "resolve_actionable_store",
]
