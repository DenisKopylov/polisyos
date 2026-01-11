from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow as pa

from polisyos.fabric.registry import ManifestRegistry
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.io.graph_store import GraphStore  # <--- Импорт
from polisyos.ir.data_views import DataViewRequest, DataViewType
from polisyos.fabric.udf.compiler import ViewCompiler
from polisyos.fabric.udf.config import UdfSchema, load_udf_schema
from polisyos.fabric.udf.plan import DataViewPlan
from polisyos.common.logger import logger


class UDFEngine:
    def __init__(
        self,
        db: SimulationDB,
        graph: Optional[GraphStore] = None,
        curated_dir: Path | str = Path("data/curated"),
        schema: Optional[UdfSchema] = None,
    ):
        self.db = db
        # Если граф не передан, создаем дефолтный (для удобства)
        self.graph = graph if graph else GraphStore()
        curated_path = Path(curated_dir)
        self.manifests = ManifestRegistry(curated_path)
        if schema is None:
            schema_path = curated_path / "udf_schema.json"
            if not schema_path.exists():
                raise ValueError(f"Missing UDF schema file: {schema_path}")
            self.schema = load_udf_schema(schema_path)
        else:
            self.schema = schema
        self.compiler = ViewCompiler(self.manifests, self.schema)

    def compile(self, request: DataViewRequest) -> DataViewPlan:
        return self.compiler.compile(request)

    def query(self, request: DataViewRequest) -> pd.DataFrame:
        logger.info(f"🚀 UDF Query: {request.view_type} | {request.metrics}")
        plan = self.compile(request)
        return self.execute(plan)

    def query_arrow(self, request: DataViewRequest) -> pa.Table:
        logger.info(f"🚀 UDF Arrow Query: {request.view_type} | {request.metrics}")
        plan = self.compile(request)
        return self.execute(plan, as_arrow=True)

    def execute(self, plan: DataViewPlan, *, as_arrow: bool = False):
        if plan.view_type == DataViewType.NETWORK:
            return self._execute_network(plan, as_arrow=as_arrow)
        return self._execute_relational(plan, as_arrow=as_arrow)

    def _execute_relational(self, plan: DataViewPlan, *, as_arrow: bool = False):
        if not plan.sql:
            raise ValueError("Relational plan missing SQL")
        logger.debug(f"SQL: {plan.sql} | Params: {plan.params}")
        try:
            if as_arrow:
                return self.db.conn.execute(plan.sql, plan.params).fetch_arrow_table()
            return self.db.conn.execute(plan.sql, plan.params).fetchdf()
        except Exception as e:
            logger.error(f"Relational Query Failed: {e}")
            raise e

    def _execute_network(self, plan: DataViewPlan, *, as_arrow: bool = False):
        if not plan.cypher:
            raise ValueError("Network plan missing Cypher")
        logger.debug(f"Cypher: {plan.cypher}")
        try:
            df = self.graph.query(plan.cypher, plan.cypher_params)
            if as_arrow:
                return pa.Table.from_pandas(df)
            return df
        except Exception as e:
            logger.error(f"Graph Query Failed: {e}")
            raise e
