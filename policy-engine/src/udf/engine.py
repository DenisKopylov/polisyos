import pandas as pd

from src.io.db import SimulationDB
from src.udf.compiler import ViewCompiler
from src.udf.schema import DataViewRequest
from src.utils.logger import logger


class UDFEngine:
    def __init__(self, db: SimulationDB):
        self.db = db
        self.compiler = ViewCompiler()

    def query(self, request: DataViewRequest) -> pd.DataFrame:
        """
        Исполняет высокоуровневый запрос и возвращает DataFrame.
        """
        sql, params = self.compiler.compile(request)
        logger.debug(f"Executing SQL: {sql} | Params: {params}")

        try:
            # DuckDB execute принимает параметры вторым аргументом
            # fetchdf() сразу отдает Pandas - быстро и удобно
            df = self.db.conn.execute(sql, params).fetchdf()
            return df
        except Exception as e:
            logger.error(f"UDF Query Failed: {e}")
            raise e
