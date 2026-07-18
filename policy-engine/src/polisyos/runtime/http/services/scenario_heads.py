"""Durable authority contract for counterfactual scenario heads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class ScenarioHeadRecord:
    """Identify the authoritative persisted revision of one scenario."""

    scenario_id: str
    baseline_run_id: str
    revision: int
    artifact_ref: str
    manifest_hash: str
    updated_at: datetime


@runtime_checkable
class ScenarioHeadStore(Protocol):
    """Persist scenario heads with atomic compare-and-set semantics."""

    def get_scenario_head(self, scenario_id: str) -> ScenarioHeadRecord | None:
        """Return the authoritative head for a scenario, if one exists."""
        ...

    def list_scenario_heads(
        self,
        *,
        baseline_run_id: str | None = None,
    ) -> list[ScenarioHeadRecord]:
        """Return authoritative heads, optionally scoped to one baseline run."""
        ...

    def compare_and_set_scenario_head(
        self,
        *,
        scenario_id: str,
        baseline_run_id: str,
        expected_revision: int,
        new_revision: int,
        artifact_ref: str,
        manifest_hash: str,
    ) -> bool:
        """Advance a scenario head exactly one revision if its authority is unchanged."""
        ...


__all__ = ["ScenarioHeadRecord", "ScenarioHeadStore"]
