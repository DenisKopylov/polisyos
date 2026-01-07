# polisyos/io/graph_store.py
import os
import shutil
from pathlib import Path

import kuzu
from polisyos.common.logger import get_logger

logger = get_logger(__name__)

class GraphStore:
    def __init__(self, db_path: str = "simulation.kuzu", clear_on_start: bool = False):
        self.db_path = db_path
        if clear_on_start and os.path.exists(db_path):
            path = Path(db_path)
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self._init_schema()

    def _init_schema(self):
        """Создаем структуру Entity-Event Graph."""
        try:
            # 1. Узлы (Agents)
            # В Kùzu Primary Key обязателен
            self.conn.execute(
                "CREATE NODE TABLE IF NOT EXISTS Agent(id STRING, type STRING, PRIMARY KEY(id))"
            )

            # 2. Ребра (Interactions/Events)
            # FROM Agent TO Agent. Храним шаг, сумму и тип транзакции.
            self.conn.execute(
                """
                CREATE REL TABLE IF NOT EXISTS Interaction(
                    FROM Agent TO Agent,
                    step INT64,
                    amount DOUBLE,
                    type STRING
                )
                """
            )
            logger.info(f"🕸️ Graph Schema initialized at {self.db_path}")
        except Exception as e:
            logger.warning(f"Graph schema init warning: {e}")

    def add_agent(self, agent_id: str, agent_type: str):
        """Добавление узла (идемпотентно через MERGE в Cypher)."""
        # Kuzu пока поддерживает MERGE ограниченно, используем CREATE с проверкой или просто INSERT ignore логику
        # Для простоты MVP используем MERGE если версия Kuzu позволяет, иначе ловим ошибку
        try:
            self.conn.execute(
                "MERGE (a:Agent {id: $id, type: $type})",
                {"id": agent_id, "type": agent_type}
            )
        except Exception:
            # Fallback для старых версий или конфликтов
            pass

    def add_interaction(self, from_id: str, to_id: str, step: int, amount: float, type_: str):
        """Добавление ребра события."""
        self.conn.execute(
            """
            MATCH (a:Agent), (b:Agent)
            WHERE a.id = $from_id AND b.id = $to_id
            CREATE (a)-[r:Interaction]->(b)
            SET r.step = $step, r.amount = $amount, r.type = $type_
            """,
            {"from_id": from_id, "to_id": to_id, "step": step, "amount": amount, "type_": type_}
        )

    def query(self, cypher: str, params: dict = None):
        if params is None:
            params = {}
        # Возвращаем результат как Pandas DF (Kuzu это умеет)
        return self.conn.execute(cypher, params).get_as_df()
