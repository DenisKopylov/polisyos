from typing import Tuple

from src.udf.config import ALLOWED_COLUMNS, FIELD_CLASSIFICATION
from src.udf.schema import AccessTier, DataViewRequest, DataViewType
from src.utils.logger import logger


class ViewCompiler:
    """
    Превращает безопасный JSON-запрос в SQL для DuckDB.
    """

    # Разрешенные таблицы и колонки (Whitelist)
    ALLOWED_TABLES = {"macro": "macro_history", "agents": "agents_snapshot"}

    def compile(self, req: DataViewRequest) -> Tuple[str, list]:
        """
        Возвращает (sql_query, parameters).
        """
        logger.info(f"👓 Compiling DataView: {req.view_type} for {req.metrics}")

        if req.view_type == DataViewType.PANEL:
            return self._compile_panel(req)
        elif req.view_type == DataViewType.SNAPSHOT:
            return self._compile_snapshot(req)
        else:
            raise NotImplementedError(f"View type {req.view_type} not supported yet")

    def _validate_columns(
        self, table: str, metrics: list[str], filters, access_tier: AccessTier
    ) -> None:
        allowed = ALLOWED_COLUMNS.get(table, set())
        for metric in metrics:
            if metric not in allowed:
                raise ValueError(f"Metric '{metric}' is not allowed for table '{table}'")
        for f in filters:
            if f.column not in allowed:
                raise ValueError(f"Filter column '{f.column}' is not allowed for table '{table}'")
        self._validate_access_tier(table, metrics, filters, access_tier)

    def _validate_access_tier(
        self, table: str, metrics: list[str], filters, access_tier: AccessTier
    ) -> None:
        classification = FIELD_CLASSIFICATION.get(table, {})
        allowed_levels = self._allowed_levels_for_tier(access_tier)
        for metric in metrics:
            level = classification.get(metric, "internal")
            if level not in allowed_levels:
                logger.warning(
                    "PII access blocked: table={table} metric={metric} tier={tier}",
                    table=table,
                    metric=metric,
                    tier=access_tier.value,
                )
                raise ValueError(
                    f"Metric '{metric}' not allowed for access_tier '{access_tier.value}'"
                )
        for f in filters:
            level = classification.get(f.column, "internal")
            if level not in allowed_levels:
                logger.warning(
                    "PII access blocked: table={table} column={column} tier={tier}",
                    table=table,
                    column=f.column,
                    tier=access_tier.value,
                )
                raise ValueError(
                    f"Filter column '{f.column}' not allowed for access_tier '{access_tier.value}'"
                )

    def _allowed_levels_for_tier(self, access_tier: AccessTier) -> set[str]:
        if access_tier == AccessTier.PUBLIC:
            return {"public"}
        if access_tier == AccessTier.INTERNAL:
            return {"public", "internal"}
        return {"public", "internal", "sensitive"}

    def _compile_panel(self, req: DataViewRequest) -> Tuple[str, list]:
        """Строит запрос к макро-истории или агрегированным агентам."""
        # Для простоты MVP работаем с macro_history
        table = self.ALLOWED_TABLES["macro"]
        self._validate_columns(table, req.metrics, req.filters, req.access_tier)

        # SELECT
        cols = ", ".join([f"{m}" for m in req.metrics])
        # Всегда добавляем step для временного ряда
        if "step" not in req.metrics:
            cols = "step, " + cols

        sql = f"SELECT {cols} FROM {table} WHERE run_id = ?"  # <--- ФИЛЬТР
        params = [req.run_id]  # <--- ПАРАМЕТР

        # TIME FILTER
        if req.step_start is not None:
            sql += " AND step >= ?"
            params.append(req.step_start)
        if req.step_end is not None:
            sql += " AND step <= ?"
            params.append(req.step_end)

        # OTHER FILTERS
        for f in req.filters:
            # Важно: валидируем column name, чтобы не было инъекций
            # (в реальном проде нужно проверять по схеме БД)
            sql += f" AND {f.column} {f.op} ?"
            params.append(f.value)

        sql += " ORDER BY step"
        return sql, params

    def _compile_snapshot(self, req: DataViewRequest) -> Tuple[str, list]:
        """Запрос к agents_snapshot (микро-данные)."""
        table = self.ALLOWED_TABLES["agents"]
        self._validate_columns(table, req.metrics, req.filters, req.access_tier)

        # Если нужна агрегация (например, средний доход безработных)
        agg_func = req.aggregation
        cols_sql = []
        for m in req.metrics:
            cols_sql.append(f"{agg_func}({m}) as {m}")

        sql = f"SELECT {', '.join(cols_sql)} FROM {table} WHERE run_id = ?"  # <--- ФИЛЬТР
        params = [req.run_id]  # <--- ПАРАМЕТР

        # Обязательно фильтруем по step (снапшот - это момент времени)
        if req.step_end is not None:
            sql += " AND step = ?"
            params.append(req.step_end)

        for f in req.filters:
            sql += f" AND {f.column} {f.op} ?"
            params.append(f.value)

        return sql, params
