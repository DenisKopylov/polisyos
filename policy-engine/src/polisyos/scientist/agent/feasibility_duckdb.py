"""DuckDB-backed feasibility probe for persisted agent snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polisyos.fabric.io.db import SimulationDB
from polisyos.ir.governance.selector_expr import SelectorAll, SelectorAny, SelectorExpr, SelectorNot, SelectorPredicate
from polisyos.ir.types import SelectorOperator
from polisyos.scientist.agent.feasibility import BudgetImpactResult, PopulationQueryResult


@dataclass(frozen=True, slots=True)
class DuckDBProbeConfig:
    table_name: str = "agents_snapshot"
    run_id: str | None = None
    step: int | None = None


class DuckDBFeasibilityProbe:
    """Feasibility probe implementation over `SimulationDB` snapshots."""

    def __init__(self, db: SimulationDB, *, config: DuckDBProbeConfig | None = None) -> None:
        self._db = db
        self._config = config or DuckDBProbeConfig()

    async def count_matching_agents(
        self,
        *,
        selector_expr: SelectorExpr,
        data_snapshot_ref: str,
    ) -> PopulationQueryResult:
        try:
            where_sql, params = self._selector_to_sql(selector_expr)
            base_filter, base_params = self._base_filter_sql()
            where_parts = [base_filter, where_sql]
            where_clause = " AND ".join(part for part in where_parts if part)
            all_params = [*base_params, *params]

            total_query = f"SELECT COUNT(*) FROM {self._config.table_name}"
            if base_filter:
                total_query += f" WHERE {base_filter}"
            total = int(self._db.conn.execute(total_query, base_params).fetchone()[0])

            match_query = f"SELECT COUNT(*) FROM {self._config.table_name}"
            if where_clause:
                match_query += f" WHERE {where_clause}"
            matching = int(self._db.conn.execute(match_query, all_params).fetchone()[0])

            ratio = matching / total if total > 0 else 0.0
            return PopulationQueryResult(
                matching_count=matching,
                total_count=total,
                match_ratio=ratio,
                snapshot_ref=data_snapshot_ref,
                query_description=f"duckdb selector matched {matching}/{total}",
            )
        except Exception as exc:
            return PopulationQueryResult(
                matching_count=-1,
                total_count=-1,
                match_ratio=-1.0,
                snapshot_ref=data_snapshot_ref,
                query_description=f"duckdb query failed: {exc}",
                confidence=0.0,
            )

    async def check_attribute_exists(
        self,
        *,
        attribute_name: str,
        data_snapshot_ref: str,
    ) -> bool:
        del data_snapshot_ref
        if not attribute_name.replace("_", "").isalnum():
            return False
        try:
            rows = self._db.conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
                [self._config.table_name],
            ).fetchall()
            return attribute_name in {str(row[0]) for row in rows}
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
        pop = await self.count_matching_agents(
            selector_expr=selector_expr,
            data_snapshot_ref=data_snapshot_ref,
        )
        if pop.matching_count < 0:
            return BudgetImpactResult(
                estimated_total_cost=-1.0,
                matching_count=-1,
                total_count=-1,
                budget_limit=budget_limit,
                feasible=None,
                snapshot_ref=data_snapshot_ref,
                query_description="duckdb budget check skipped",
                confidence=0.0,
            )

        amount = max(float(amount_per_agent), 0.0)
        estimated_total = amount * pop.matching_count
        feasible = None if budget_limit is None else estimated_total <= budget_limit
        return BudgetImpactResult(
            estimated_total_cost=estimated_total,
            matching_count=pop.matching_count,
            total_count=pop.total_count,
            budget_limit=budget_limit,
            feasible=feasible,
            snapshot_ref=data_snapshot_ref,
            query_description=(
                f"duckdb estimate={estimated_total:.4f} for {pop.matching_count} agents "
                f"at amount={amount:.4f}"
            ),
        )

    def _base_filter_sql(self) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if self._config.run_id is not None:
            clauses.append("run_id = ?")
            params.append(self._config.run_id)
        if self._config.step is not None:
            clauses.append("step = ?")
            params.append(int(self._config.step))
        return " AND ".join(clauses), params

    def _selector_to_sql(self, selector: SelectorExpr) -> tuple[str, list[Any]]:
        if isinstance(selector, SelectorPredicate):
            field = selector.field
            if not field.replace("_", "").isalnum():
                raise ValueError(f"Invalid selector field '{field}'")
            operator, params = self._operator_sql(selector.operator, selector.value)
            return f"{field} {operator}", params

        if isinstance(selector, SelectorNot):
            sql, params = self._selector_to_sql(selector.clause)
            return f"NOT ({sql})", params

        if isinstance(selector, SelectorAll):
            clauses: list[str] = []
            params: list[Any] = []
            for clause in selector.clauses:
                sql, sql_params = self._selector_to_sql(clause)
                clauses.append(f"({sql})")
                params.extend(sql_params)
            return " AND ".join(clauses) if clauses else "1=1", params

        if isinstance(selector, SelectorAny):
            clauses = []
            params: list[Any] = []
            for clause in selector.clauses:
                sql, sql_params = self._selector_to_sql(clause)
                clauses.append(f"({sql})")
                params.extend(sql_params)
            return " OR ".join(clauses) if clauses else "1=1", params

        raise ValueError(f"Unsupported selector type: {type(selector)}")

    def _operator_sql(self, operator: SelectorOperator, value: Any) -> tuple[str, list[Any]]:
        if operator == SelectorOperator.EQUALS:
            return "= ?", [value]
        if operator == SelectorOperator.NOT_EQUALS:
            return "!= ?", [value]
        if operator == SelectorOperator.GREATER_THAN:
            return "> ?", [value]
        if operator == SelectorOperator.LESS_THAN:
            return "< ?", [value]
        if operator == SelectorOperator.GREATER_EQUAL:
            return ">= ?", [value]
        if operator == SelectorOperator.LESS_EQUAL:
            return "<= ?", [value]
        if operator in {SelectorOperator.IN, SelectorOperator.NOT_IN}:
            if not isinstance(value, list) or not value:
                raise ValueError("IN/NOT_IN requires non-empty list")
            placeholders = ",".join("?" for _ in value)
            op = "IN" if operator == SelectorOperator.IN else "NOT IN"
            return f"{op} ({placeholders})", list(value)
        if operator == SelectorOperator.BETWEEN:
            if not isinstance(value, list) or len(value) != 2:
                raise ValueError("BETWEEN requires [lower, upper]")
            return "BETWEEN ? AND ?", [value[0], value[1]]
        if operator == SelectorOperator.CONTAINS:
            return "= ?", [value]
        raise ValueError(f"Unsupported selector operator {operator}")


__all__ = ["DuckDBFeasibilityProbe", "DuckDBProbeConfig"]
