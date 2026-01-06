from typing import Tuple

from src.udf.schema import DataViewRequest, DataViewType
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

    def _compile_panel(self, req: DataViewRequest) -> Tuple[str, list]:
        """Строит запрос к макро-истории или агрегированным агентам."""
        # Для простоты MVP работаем с macro_history
        table = self.ALLOWED_TABLES["macro"]

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
