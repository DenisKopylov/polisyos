"""Own Lex's typed strategic-response expectations and search handoff."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import Field

from polisyos.ir.governance.policy_spec import PolicySearchLevel
from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.observation.bundles import StrategicResponseSpec, StrategicResponseSpecsBundle
from polisyos.ir.observation.contracts import StrategicResponseChannel


class StrategicResponseRegistryEntry(KernelModel):
    """Registry entry layered on top of the IR strategic response contract."""

    spec: StrategicResponseSpec
    expected_response_type: str = Field(default="performative_shift", min_length=1, max_length=120)
    hook_config: dict[str, Any] = Field(default_factory=dict)


class HierarchicalPolicySearchPlan(KernelModel):
    """Serializable handoff contract for Scientist hierarchical policy search."""

    coordinator_fqn: str = Field(
        default="polisyos.scientist.policy_design.search.HierarchicalSearchCoordinator",
        min_length=1,
        max_length=255,
    )
    candidate_id: str = Field(..., min_length=1, max_length=120)
    candidate_hash: str = Field(..., min_length=1, max_length=120)
    policy_family: str = Field(..., min_length=1, max_length=120)
    level_order: list[PolicySearchLevel] = Field(
        default_factory=lambda: [
            PolicySearchLevel.STRUCTURE,
            PolicySearchLevel.PARAMETER,
            PolicySearchLevel.NARRATIVE,
        ]
    )
    search_config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StrategicResponseSpecRegistry:
    """Lookup helper for strategic-response expectations by intervention kind."""

    def __init__(
        self,
        entries: Iterable[StrategicResponseRegistryEntry | Mapping[str, Any]] = (),
    ) -> None:
        self._entries: dict[str, StrategicResponseRegistryEntry] = {}
        for entry in entries:
            self.register(entry)

    @classmethod
    def from_bundle(
        cls,
        bundle: StrategicResponseSpecsBundle | Mapping[str, Any],
    ) -> StrategicResponseSpecRegistry:
        resolved_bundle = (
            bundle
            if isinstance(bundle, StrategicResponseSpecsBundle)
            else StrategicResponseSpecsBundle.model_validate(bundle)
        )
        return cls(
            StrategicResponseRegistryEntry(spec=spec) for spec in resolved_bundle.expectations
        )

    def register(
        self,
        entry: StrategicResponseRegistryEntry | Mapping[str, Any],
    ) -> StrategicResponseRegistryEntry:
        """Register one strategic-response spec and reject duplicate intervention kinds."""
        resolved = (
            entry
            if isinstance(entry, StrategicResponseRegistryEntry)
            else StrategicResponseRegistryEntry.model_validate(entry)
        )
        if resolved.spec.intervention_kind in self._entries:
            raise ValueError(
                f"duplicate strategic response spec for '{resolved.spec.intervention_kind}'"
            )
        self._entries[resolved.spec.intervention_kind] = resolved
        return resolved

    def get(self, intervention_kind: str) -> StrategicResponseRegistryEntry | None:
        return self._entries.get(intervention_kind)

    def require(self, intervention_kind: str) -> StrategicResponseRegistryEntry:
        resolved = self.get(intervention_kind)
        if resolved is None:
            raise KeyError(f"strategic response spec not found for '{intervention_kind}'")
        return resolved

    def channels_for(self, intervention_kind: str) -> tuple[StrategicResponseChannel, ...]:
        resolved = self.get(intervention_kind)
        if resolved is None:
            return ()
        return tuple(resolved.spec.channels)

    def hook_fqn_for(self, intervention_kind: str) -> str | None:
        resolved = self.get(intervention_kind)
        return None if resolved is None else resolved.spec.hook_fqn

    def hook_config_for(self, intervention_kind: str) -> dict[str, Any]:
        resolved = self.get(intervention_kind)
        return {} if resolved is None else dict(resolved.hook_config)

    def expected_response_type_for(self, intervention_kind: str) -> str | None:
        resolved = self.get(intervention_kind)
        return None if resolved is None else resolved.expected_response_type

    def strategic_required_for(self, intervention_kind: str) -> bool:
        resolved = self.get(intervention_kind)
        return bool(resolved is not None and resolved.spec.strategic_response_expected)

    def bundle(self) -> StrategicResponseSpecsBundle:
        return StrategicResponseSpecsBundle(
            expectations=[self._entries[key].spec for key in sorted(self._entries)]
        )


__all__ = [
    "HierarchicalPolicySearchPlan",
    "StrategicResponseRegistryEntry",
    "StrategicResponseSpecRegistry",
]
