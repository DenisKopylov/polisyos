import pandas as pd
from typing import Optional

from src.io.db import SimulationDB
from src.io.graph_store import GraphStore  # <--- Импорт
from src.udf.compiler import ViewCompiler
from src.udf.config import ALLOWED_RELATION_TYPES
from src.udf.schema import DataViewRequest, DataViewType
from src.utils.logger import logger


class UDFEngine:
    def __init__(self, db: SimulationDB, graph: Optional[GraphStore] = None):
        self.db = db
        # Если граф не передан, создаем дефолтный (для удобства)
        self.graph = graph if graph else GraphStore()
        self.compiler = ViewCompiler()

    def query(self, request: DataViewRequest) -> pd.DataFrame:
        logger.info(f"🚀 UDF Query: {request.view_type} | {request.metrics}")

        # 1. Графовый запрос (Network Topology)
        if request.view_type == DataViewType.NETWORK:
            return self._query_network(request)

        # 2. Табличный запрос (DuckDB)
        else:
            return self._query_relational(request)

    def _query_relational(self, request: DataViewRequest) -> pd.DataFrame:
        """Старая логика DuckDB"""
        sql, params = self.compiler.compile(request)
        logger.debug(f"SQL: {sql} | Params: {params}")
        try:
            return self.db.conn.execute(sql, params).fetchdf()
        except Exception as e:
            logger.error(f"Relational Query Failed: {e}")
            raise e

    def _query_network(self, request: DataViewRequest) -> pd.DataFrame:
        """Новая логика KùzuDB"""
        if not request.ego_node_id:
            raise ValueError("Network query requires 'ego_node_id'")

        if request.relation_types:
            unknown = [t for t in request.relation_types if t not in ALLOWED_RELATION_TYPES]
            if unknown:
                raise ValueError(f"Unknown relation_types: {unknown}")

        # Простой компилятор Cypher (в будущем вынести в compiler.py)
        # Ищем соседей на глубину hop_depth
        depth = request.hop_depth

        # Для MVP используем простой запрос на глубину 1, затем расширим
        cypher = f"""
            MATCH (a:Agent)-[e:Interaction]-(b:Agent)
            WHERE a.id = $ego_id
            {"AND e.type IN $relation_types" if request.relation_types else ""}
            RETURN b.id as neighbor_id, e.amount as amount, e.type as type, e.step as step
        """

        # Если depth > 1, добавим второй уровень
        if depth >= 2:
            cypher = f"""
                {cypher}
                UNION ALL
                MATCH (a:Agent)-[e1:Interaction]-(b:Agent)-[e2:Interaction]-(c:Agent)
                WHERE a.id = $ego_id
                {"AND e2.type IN $relation_types" if request.relation_types else ""}
                RETURN c.id as neighbor_id, e2.amount as amount, e2.type as type, e2.step as step
            """

        logger.debug(f"Cypher: {cypher}")
        try:
            params = {"ego_id": request.ego_node_id}
            if request.relation_types:
                params["relation_types"] = request.relation_types
            return self.graph.query(cypher, params)
        except Exception as e:
            logger.error(f"Graph Query Failed: {e}")
            raise e
