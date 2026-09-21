"""Shared linear migration traversal with explicit caller-owned profiles."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

PayloadT = TypeVar("PayloadT")
EdgeT = TypeVar("EdgeT")


@dataclass(frozen=True)
class LinearMigrationProfile(Generic[PayloadT, EdgeT]):
    """Define the observable policy around one shared linear traversal."""

    prepare: Callable[[PayloadT, str], tuple[PayloadT, str]]
    no_op: Callable[[PayloadT], PayloadT]
    edge_target: Callable[[EdgeT], str]
    apply_step: Callable[[PayloadT, EdgeT, str, str, str], PayloadT]


def run_linear_migration(
    data: PayloadT,
    *,
    artifact: str,
    target_version: str,
    edge_lookup: Callable[[str, str], EdgeT | None],
    profile: LinearMigrationProfile[PayloadT, EdgeT],
) -> PayloadT:
    """Run one-edge-per-version traversal under an explicit migration profile."""
    current_data, current_version = profile.prepare(data, artifact)
    if current_version == target_version:
        return profile.no_op(current_data)

    visited: set[str] = set()
    while current_version != target_version:
        if current_version in visited:
            raise ValueError(
                f"Migration loop detected for '{artifact}': "
                f"{current_version} -> {target_version}"
            )
        visited.add(current_version)

        edge = edge_lookup(artifact, current_version)
        if edge is None:
            raise ValueError(
                f"No migrator for '{artifact}' from "
                f"{current_version} to {target_version}"
            )
        next_version = profile.edge_target(edge)
        current_data = profile.apply_step(
            current_data,
            edge,
            artifact,
            current_version,
            next_version,
        )
        current_version = next_version

    return current_data


__all__ = ["LinearMigrationProfile", "run_linear_migration"]
