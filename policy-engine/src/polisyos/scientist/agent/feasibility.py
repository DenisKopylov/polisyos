"""Feasibility probes for pre-simulation critic checks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO
from types import SimpleNamespace
from typing import Any, Protocol, runtime_checkable

import numpy as np

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import StateSnapshot
from polisyos.ir.governance.selector_expr import (
    SelectorAll,
    SelectorAny,
    SelectorExpr,
    SelectorNot,
    SelectorPredicate,
)
from polisyos.ir.kernel import SelectorFieldRegistry
from polisyos.ir.model_layer.types import SelectorOperator


@dataclass(frozen=True, slots=True)
class PopulationQueryResult:
    """Result of evaluating a selector against a concrete population snapshot."""

    matching_count: int
    total_count: int
    match_ratio: float
    snapshot_ref: str
    query_description: str
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class BudgetImpactResult:
    """Estimated budget impact for selector-targeted per-agent payout."""

    estimated_total_cost: float
    matching_count: int
    total_count: int
    budget_limit: float | None
    feasible: bool | None
    snapshot_ref: str
    query_description: str
    confidence: float = 1.0


@runtime_checkable
class FeasibilityProbe(Protocol):
    """Minimal read-only contract for feasibility checks."""

    async def count_matching_agents(
        self,
        *,
        selector_expr: SelectorExpr,
        data_snapshot_ref: str,
    ) -> PopulationQueryResult: ...

    async def check_attribute_exists(
        self,
        *,
        attribute_name: str,
        data_snapshot_ref: str,
    ) -> bool: ...

    async def estimate_budget_impact(
        self,
        *,
        selector_expr: SelectorExpr,
        amount_per_agent: float,
        data_snapshot_ref: str,
        budget_limit: float | None,
    ) -> BudgetImpactResult: ...


class NullFeasibilityProbe:
    """Fallback implementation when snapshot access is unavailable."""

    async def count_matching_agents(
        self,
        *,
        selector_expr: SelectorExpr,
        data_snapshot_ref: str,
    ) -> PopulationQueryResult:
        del selector_expr
        return PopulationQueryResult(
            matching_count=-1,
            total_count=-1,
            match_ratio=-1.0,
            snapshot_ref=data_snapshot_ref,
            query_description="Feasibility probe unavailable",
            confidence=0.0,
        )

    async def check_attribute_exists(
        self,
        *,
        attribute_name: str,
        data_snapshot_ref: str,
    ) -> bool:
        del attribute_name, data_snapshot_ref
        return True

    async def estimate_budget_impact(
        self,
        *,
        selector_expr: SelectorExpr,
        amount_per_agent: float,
        data_snapshot_ref: str,
        budget_limit: float | None,
    ) -> BudgetImpactResult:
        del selector_expr, amount_per_agent
        return BudgetImpactResult(
            estimated_total_cost=-1.0,
            matching_count=-1,
            total_count=-1,
            budget_limit=budget_limit,
            feasible=None,
            snapshot_ref=data_snapshot_ref,
            query_description="Feasibility probe unavailable",
            confidence=0.0,
        )


class StateSnapshotFeasibilityProbe:
    """Feasibility probe that evaluates selectors directly on Foundry state snapshots."""

    def __init__(
        self,
        cas: FileSystemCAS,
        *,
        selector_field_registry: SelectorFieldRegistry | None = None,
    ) -> None:
        self._cas = cas
        self._selector_field_registry = selector_field_registry

    async def count_matching_agents(
        self,
        *,
        selector_expr: SelectorExpr,
        data_snapshot_ref: str,
    ) -> PopulationQueryResult:
        try:
            state = self._load_state_for_snapshot(data_snapshot_ref)
            mask = self._evaluate_selector(selector_expr, state)
            active = self._active_mask(state, mask.shape[0])
            total = int(np.sum(active))
            matching = int(np.sum(mask & active))
            ratio = float(matching / total) if total > 0 else 0.0
            return PopulationQueryResult(
                matching_count=matching,
                total_count=total,
                match_ratio=ratio,
                snapshot_ref=data_snapshot_ref,
                query_description=f"selector matched {matching}/{total} agents",
            )
        except Exception as exc:
            return PopulationQueryResult(
                matching_count=-1,
                total_count=-1,
                match_ratio=-1.0,
                snapshot_ref=data_snapshot_ref,
                query_description=f"selector evaluation failed: {exc}",
                confidence=0.0,
            )

    async def check_attribute_exists(
        self,
        *,
        attribute_name: str,
        data_snapshot_ref: str,
    ) -> bool:
        try:
            state = self._load_state_for_snapshot(data_snapshot_ref)
            _ = self._field_values(state, attribute_name)
            return True
        except Exception:
            return False

    async def estimate_budget_impact(
        self,
        *,
        selector_expr: SelectorExpr,
        amount_per_agent: float,
        data_snapshot_ref: str,
        budget_limit: float | None,
    ) -> BudgetImpactResult:
        population = await self.count_matching_agents(
            selector_expr=selector_expr,
            data_snapshot_ref=data_snapshot_ref,
        )

        if population.matching_count < 0:
            return BudgetImpactResult(
                estimated_total_cost=-1.0,
                matching_count=population.matching_count,
                total_count=population.total_count,
                budget_limit=budget_limit,
                feasible=None,
                snapshot_ref=data_snapshot_ref,
                query_description="budget impact skipped: selector evaluation failed",
                confidence=0.0,
            )

        safe_amount = 0.0 if math.isnan(amount_per_agent) else float(max(amount_per_agent, 0.0))
        estimated = safe_amount * float(population.matching_count)
        feasible = None if budget_limit is None else estimated <= float(budget_limit)
        return BudgetImpactResult(
            estimated_total_cost=estimated,
            matching_count=population.matching_count,
            total_count=population.total_count,
            budget_limit=budget_limit,
            feasible=feasible,
            snapshot_ref=data_snapshot_ref,
            query_description=(
                f"estimated_total_cost={estimated:.4f} for {population.matching_count}"
                f" agents at amount={safe_amount:.4f}"
            ),
        )

    def _load_state_for_snapshot(self, data_snapshot_ref: str) -> Any:
        try:
            from polisyos.foundry.execute.executor import load_state_snapshot
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            load_state_snapshot = None
            _ = exc

        data_snapshot_id = ArtifactID.model_validate(data_snapshot_ref)
        payload = from_canonical_bytes(self._cas.get_bytes(data_snapshot_id))
        snapshot = DataSnapshot.model_validate(payload)

        state_ref = snapshot.data_ref
        if state_ref.kind != "foundry.state_snapshot":
            raise ValueError(
                "DataSnapshot.data_ref.kind must be 'foundry.state_snapshot', "
                f"got '{state_ref.kind}'"
            )
        if load_state_snapshot is not None:
            try:
                return load_state_snapshot(self._cas, snapshot_ref=state_ref.artifact_id)
            except Exception:
                # Some snapshots originate from agent_sim state layout and are not
                # compatible with strict contracts-state dataclass reconstruction.
                pass
        return self._load_raw_state_snapshot(state_ref.artifact_id)

    def _load_raw_state_snapshot(self, snapshot_artifact_id: str | ArtifactID) -> Any:
        snapshot_payload = from_canonical_bytes(self._cas.get_bytes(snapshot_artifact_id))
        snapshot = StateSnapshot.model_validate(snapshot_payload)
        blob = np.load(BytesIO(self._cas.get_bytes(snapshot.state_ref.artifact_id)))
        flat = {key: np.asarray(blob[key]) for key in blob.files}
        return self._to_namespace(self._nest_state(flat))

    def _evaluate_selector(self, selector_expr: SelectorExpr, state: Any) -> np.ndarray:
        if isinstance(selector_expr, SelectorPredicate):
            values = self._field_values(state, selector_expr.field)
            if isinstance(selector_expr.value, str) and selector_expr.value.strip().lower() in {
                "all",
                "any",
            }:
                return np.ones(values.shape[0], dtype=bool)
            return self._apply_operator(values, selector_expr.operator, selector_expr.value)

        if isinstance(selector_expr, SelectorNot):
            return ~self._evaluate_selector(selector_expr.clause, state)

        if isinstance(selector_expr, SelectorAll):
            masks = [self._evaluate_selector(clause, state) for clause in selector_expr.clauses]
            if not masks:
                return np.ones(self._agent_count(state), dtype=bool)
            mask = masks[0]
            for item in masks[1:]:
                mask = mask & item
            return mask

        if isinstance(selector_expr, SelectorAny):
            masks = [self._evaluate_selector(clause, state) for clause in selector_expr.clauses]
            if not masks:
                return np.ones(self._agent_count(state), dtype=bool)
            mask = masks[0]
            for item in masks[1:]:
                mask = mask | item
            return mask

        raise ValueError(f"Unsupported selector node: {type(selector_expr)}")

    def _field_values(self, state: Any, field_name: str) -> np.ndarray:
        if field_name in {"id", "agent_id"}:
            return np.arange(self._agent_count(state), dtype=np.int64)

        # Direct lookup on state.agents first.
        agents = getattr(state, "agents", None)
        if agents is not None and hasattr(agents, field_name):
            return np.asarray(getattr(agents, field_name))

        # Registry mapping fallback.
        if self._selector_field_registry is not None:
            spec = self._selector_field_registry.fields.get(field_name)
            if spec and spec.state_path:
                return np.asarray(self._state_path(state, spec.state_path))

        # Explicit dotted-path fallback.
        if "." in field_name:
            return np.asarray(self._state_path(state, field_name))

        raise ValueError(f"Selector field '{field_name}' not available")

    def _active_mask(self, state: Any, expected_size: int) -> np.ndarray:
        agents = getattr(state, "agents", None)
        if agents is not None and hasattr(agents, "active"):
            active = np.asarray(agents.active).astype(bool)
            if active.shape[0] == expected_size:
                return active
        return np.ones(expected_size, dtype=bool)

    def _agent_count(self, state: Any) -> int:
        agents = getattr(state, "agents", None)
        if agents is None:
            raise ValueError("State has no 'agents' attribute")
        if hasattr(agents, "size"):
            return int(agents.size)
        # Fallback to wealth length if available.
        if hasattr(agents, "wealth"):
            return int(np.asarray(agents.wealth).shape[0])
        raise ValueError("Unable to infer agent count")

    @staticmethod
    def _state_path(state: Any, path: str) -> Any:
        current = state
        for part in path.split("."):
            if isinstance(current, dict):
                current = current[part]
            else:
                current = getattr(current, part)
        return current

    @staticmethod
    def _nest_state(flat: dict[str, np.ndarray]) -> dict[str, Any]:
        nested: dict[str, Any] = {}
        for key, value in flat.items():
            parts = key.split(".")
            current = nested
            for part in parts[:-1]:
                current = current.setdefault(part, {})
            current[parts[-1]] = value
        return nested

    @classmethod
    def _to_namespace(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return SimpleNamespace(**{k: cls._to_namespace(v) for k, v in value.items()})
        return value

    @staticmethod
    def _coerce_scalar(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, bool):
            return bool(value)
        if isinstance(value, int):
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            if text.lower() in {"true", "false"}:
                return text.lower() == "true"
            try:
                return float(Decimal(text))
            except InvalidOperation:
                return text
        return value

    def _apply_operator(
        self, values: np.ndarray, operator: SelectorOperator, raw_value: Any
    ) -> np.ndarray:
        value = raw_value
        if isinstance(value, list):
            coerced_list = [self._coerce_scalar(item) for item in value]
            if operator == SelectorOperator.IN:
                return np.isin(values, np.asarray(coerced_list))
            if operator == SelectorOperator.NOT_IN:
                return ~np.isin(values, np.asarray(coerced_list))
            if operator == SelectorOperator.BETWEEN and len(coerced_list) == 2:
                lower, upper = coerced_list
                return (values >= lower) & (values <= upper)
            if operator == SelectorOperator.CONTAINS:
                return np.isin(values, np.asarray(coerced_list))

        scalar = self._coerce_scalar(value)
        if operator == SelectorOperator.EQUALS:
            return values == scalar
        if operator == SelectorOperator.NOT_EQUALS:
            return values != scalar
        if operator == SelectorOperator.GREATER_THAN:
            return values > scalar
        if operator == SelectorOperator.LESS_THAN:
            return values < scalar
        if operator == SelectorOperator.GREATER_EQUAL:
            return values >= scalar
        if operator == SelectorOperator.LESS_EQUAL:
            return values <= scalar
        if operator == SelectorOperator.CONTAINS:
            return np.isin(values, np.asarray([scalar]))

        raise ValueError(f"Unsupported selector operator: {operator}")


__all__ = [
    "BudgetImpactResult",
    "FeasibilityProbe",
    "NullFeasibilityProbe",
    "PopulationQueryResult",
    "StateSnapshotFeasibilityProbe",
]
