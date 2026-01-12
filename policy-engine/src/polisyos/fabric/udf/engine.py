from dataclasses import asdict
from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from polisyos.common.logger import logger
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import (
    DataViewRequestRef,
    FabricResult,
    QueryPlanRef,
)
from polisyos.fabric.evidence import build_evidence_bundle, persist_evidence_bundle
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.io.graph_store import GraphStore  # <--- Импорт
from polisyos.fabric.registry import ManifestRegistry
from polisyos.fabric.udf.compiler import ViewCompiler
from polisyos.fabric.udf.config import UdfSchema, load_udf_schema
from polisyos.fabric.udf.plan import DataViewPlan
from polisyos.ir.data_views import DataViewRequest, DataViewType


class UDFEngine:
    def __init__(
        self,
        db: SimulationDB,
        graph: Optional[GraphStore] = None,
        curated_dir: Path | str = Path("data/curated"),
        schema: Optional[UdfSchema] = None,
        cas_root: Path | str = Path(".polisyos"),
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
        self.cas = FileSystemCAS(Path(cas_root))

    def compile(self, request: DataViewRequest) -> DataViewPlan:
        return self.compiler.compile(request)

    def query(self, request: DataViewRequest) -> pd.DataFrame:
        result = self.query_result(request)
        return self._materialize_dataframe(result.data_ref)

    def query_arrow(self, request: DataViewRequest) -> pa.Table:
        result = self.query_result(request)
        return self._materialize_arrow(result.data_ref)

    def query_result(self, request: DataViewRequest) -> FabricResult:
        logger.info(f"🚀 UDF Query: {request.view_type} | {request.metrics}")
        plan = self.compile(request)
        table = self._execute(plan, as_arrow=True)

        # Persist request + plan + data in CAS
        request_ref = self._persist_request(request)
        plan_ref = self._persist_plan(plan, request_ref)
        data_ref = self._persist_data(table)

        evidence_bundle = build_evidence_bundle(
            sources=[request_ref, plan_ref, data_ref],
            notes=["auto-generated evidence bundle"],
        )
        evidence_ref = persist_evidence_bundle(self.cas, evidence_bundle)

        return FabricResult(
            request_ref=request_ref,
            plan_ref=plan_ref,
            data_ref=data_ref,
            sources=[request_ref, plan_ref],
            evidence_ref=evidence_ref,
        )

    def _execute(self, plan: DataViewPlan, *, as_arrow: bool = False):
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

    # ---- Persistence helpers -------------------------------------------------
    def _persist_request(self, request: DataViewRequest) -> DataViewRequestRef:
        ref = self.cas.put_json(
            request.model_dump(),
            opts=PutOptions(
                kind="ir.data_view_request",
                media_type="application/json",
                schema=SchemaInfo(name="ir.data_view_request", version="1.0"),
            ),
        )
        return DataViewRequestRef.model_validate(ref.model_dump())

    def _persist_plan(self, plan: DataViewPlan, request_ref: DataViewRequestRef) -> QueryPlanRef:
        ref = self.cas.put_json(
            asdict(plan),
            opts=PutOptions(
                kind="fabric.query_plan",
                media_type="application/json",
                schema=SchemaInfo(name="fabric.query_plan", version="1.0"),
            ),
        )
        return QueryPlanRef.model_validate(ref.model_dump())

    def _persist_data(self, table: pa.Table) -> ArtifactRef:
        buf = pa.BufferOutputStream()
        pq.write_table(table, buf)
        data_bytes = buf.getvalue().to_pybytes()
        ref = self.cas.put_bytes(
            data_bytes,
            opts=PutOptions(
                kind="fabric.data",
                media_type="application/parquet",
                schema=SchemaInfo(name="fabric.data", version="1.0"),
            ),
        )
        return ArtifactRef.model_validate(ref.model_dump())

    def _materialize_arrow(self, data_ref: ArtifactRef) -> pa.Table:
        blob = self.cas.get_bytes(ArtifactID.model_validate(data_ref.artifact_id))
        return pq.read_table(pa.BufferReader(blob))

    def _materialize_dataframe(self, data_ref: ArtifactRef) -> pd.DataFrame:
        return self._materialize_arrow(data_ref).to_pandas()
