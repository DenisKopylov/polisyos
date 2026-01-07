from polisyos.fabric.registry import ManifestRegistry
from polisyos.ir.data_views import AccessTier, DataViewRequest, DataViewType
from polisyos.fabric.udf.config import UdfSchema
from polisyos.fabric.udf.plan import DataViewPlan
from polisyos.common.logger import logger


class ViewCompiler:
    """
    Превращает безопасный JSON-запрос в SQL для DuckDB.
    """

    # Разрешенные таблицы и колонки (Whitelist)
    ALLOWED_TABLES = {"macro": "macro_history", "agents": "agents_snapshot"}
    NETWORK_COLUMNS = {"neighbor_id", "amount", "type", "step"}

    def __init__(self, manifests: ManifestRegistry, schema: UdfSchema) -> None:
        self.manifests = manifests
        self.schema = schema

    def compile(self, req: DataViewRequest) -> DataViewPlan:
        """
        Возвращает план выполнения (request -> plan -> execution).
        """
        logger.info(f"👓 Compiling DataView: {req.view_type} for {req.metrics}")

        if req.view_type == DataViewType.PANEL:
            return self._compile_panel(req)
        elif req.view_type == DataViewType.SNAPSHOT:
            return self._compile_snapshot(req)
        elif req.view_type == DataViewType.NETWORK:
            return self._compile_network(req)
        raise NotImplementedError(f"View type {req.view_type} not supported")

    def _validate_columns(
        self, table: str, metrics: list[str], filters, access_tier: AccessTier
    ) -> None:
        allowed = self.schema.allowed_columns.get(table, set())
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
        classification = self.schema.field_classification.get(table, {})
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

    def _compile_panel(self, req: DataViewRequest) -> DataViewPlan:
        """Строит запрос к макро-истории или агрегированным агентам."""
        # Для простоты MVP работаем с macro_history
        self.manifests.require("macro")
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
        return DataViewPlan(
            request_id=req.request_id,
            view_type=req.view_type,
            dataset_name="macro",
            table=table,
            sql=sql,
            params=params,
            cypher=None,
            cypher_params={},
            access_tier=req.access_tier,
            redacted_fields=[],
        )

    def _compile_snapshot(self, req: DataViewRequest) -> DataViewPlan:
        """Запрос к agents_snapshot (микро-данные)."""
        self.manifests.require("agents")
        self.manifests.require_entity_resolution()
        table = self.ALLOWED_TABLES["agents"]
        self._validate_columns(table, req.metrics, req.filters, req.access_tier)

        if req.aggregation is None:
            cols_sql = ", ".join(req.metrics)
        else:
            cols_sql = ", ".join([f"{req.aggregation}({m}) as {m}" for m in req.metrics])

        sql = f"SELECT {cols_sql} FROM {table} WHERE run_id = ?"  # <--- ФИЛЬТР
        params = [req.run_id]  # <--- ПАРАМЕТР

        # Обязательно фильтруем по step (снапшот - это момент времени)
        sql += " AND step = ?"
        params.append(req.step_end)

        for f in req.filters:
            sql += f" AND {f.column} {f.op} ?"
            params.append(f.value)

        return DataViewPlan(
            request_id=req.request_id,
            view_type=req.view_type,
            dataset_name="agents",
            table=table,
            sql=sql,
            params=params,
            cypher=None,
            cypher_params={},
            access_tier=req.access_tier,
            redacted_fields=[],
        )

    def _compile_network(self, req: DataViewRequest) -> DataViewPlan:
        self.manifests.require("interactions")
        self.manifests.require_entity_resolution()

        if req.relation_types:
            unknown = [t for t in req.relation_types if t not in self.schema.allowed_relation_types]
            if unknown:
                raise ValueError(f"Unknown relation_types: {unknown}")

        if any(metric not in self.NETWORK_COLUMNS for metric in req.metrics):
            raise ValueError(f"Network metrics must be subset of {sorted(self.NETWORK_COLUMNS)}")

        return_fields = []
        for metric in req.metrics:
            if metric == "neighbor_id":
                return_fields.append("b.id as neighbor_id")
            else:
                return_fields.append(f"e.{metric} as {metric}")
        return_clause = ", ".join(return_fields)

        base_match = """
            MATCH (a:Agent)-[e:Interaction]-(b:Agent)
            WHERE a.id = $ego_id
        """
        if req.relation_types:
            base_match += " AND e.type IN $relation_types"
        cypher = f"""
            {base_match}
            RETURN {return_clause}
        """

        if req.hop_depth >= 2:
            return_fields_second = []
            for metric in req.metrics:
                if metric == "neighbor_id":
                    return_fields_second.append("c.id as neighbor_id")
                else:
                    return_fields_second.append(f"e2.{metric} as {metric}")
            return_clause_second = ", ".join(return_fields_second)
            cypher = f"""
                {cypher}
                UNION ALL
                MATCH (a:Agent)-[e1:Interaction]-(b:Agent)-[e2:Interaction]-(c:Agent)
                WHERE a.id = $ego_id
                {"AND e2.type IN $relation_types" if req.relation_types else ""}
                RETURN {return_clause_second}
            """

        params = {"ego_id": req.ego_node_id}
        if req.relation_types:
            params["relation_types"] = req.relation_types

        return DataViewPlan(
            request_id=req.request_id,
            view_type=req.view_type,
            dataset_name="interactions",
            table=None,
            sql=None,
            params=[],
            cypher=cypher,
            cypher_params=params,
            access_tier=req.access_tier,
            redacted_fields=[],
        )
