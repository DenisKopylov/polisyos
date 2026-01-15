import json

import duckdb
import pandas as pd

from polisyos.common.logger import logger


class SimulationDB:
    def __init__(self, db_path: str = "simulation.duckdb"):
        self.db_path = db_path
        self.conn = duckdb.connect(db_path)
        self._setup_db()

    def _setup_db(self):
        """Создаем структуру таблиц, если их нет."""
        # Таблица для макро-показателей (1 строка на 1 шаг симуляции)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS macro_history (
                run_id VARCHAR,
                step INTEGER,
                gdp DOUBLE,
                unemployment_rate DOUBLE,
                inflation_rate DOUBLE,
                avg_price DOUBLE,
                avg_income DOUBLE,
                government_balance DOUBLE,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Таблица для микро-данных (1 млн строк на каждый срез, сохраняем не каждый шаг!)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agents_snapshot (
                run_id VARCHAR,
                step INTEGER,
                agent_id VARCHAR,
                age INTEGER,
                income DOUBLE,
                savings DOUBLE,
                is_employed BOOLEAN
            )
        """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS entity_resolution (
                raw_id VARCHAR,
                canonical_id VARCHAR,
                match_confidence DOUBLE,
                match_method VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS run_records (
                run_id VARCHAR,
                parent_run_id VARCHAR,
                seed INTEGER,
                repro_mode VARCHAR,
                backend VARCHAR,
                python_version VARCHAR,
                platform VARCHAR,
                generated_at TIMESTAMP,
                schema_version VARCHAR,
                generator_name VARCHAR,
                generator_version VARCHAR,
                library_versions VARCHAR,
                flags VARCHAR
            )
        """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _meta_segments (
                segment_id VARCHAR PRIMARY KEY,
                sha256 VARCHAR,
                row_count INTEGER,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        logger.info(f"💾 Database connected: {self.db_path}")

    def save_macro(self, data: list[dict]):
        """Быстрое сохранение макро-статистики."""
        if not data:
            return
        df = pd.DataFrame(data)
        # duckdb умеет делать INSERT прямо из DataFrame
        self.conn.execute("INSERT INTO macro_history SELECT * FROM df")
        logger.info(f"💾 Saved {len(df)} macro records.")

    def save_agents(self, run_id: str, step: int, agents_state):
        """
        Сохранение среза агентов.
        ВНИМАНИЕ: Это тяжелая операция (1 млн строк).
        Делаем это эффективно через Pandas -> DuckDB Native.
        """
        # 1. Конвертируем JAX массивы в Numpy (CPU) -> Pandas
        # JAX массивы ленивые, здесь мы их реально вычисляем
        n_agents = agents_state.size

        df = pd.DataFrame(
            {
                "run_id": [run_id] * n_agents,
                "step": [step] * n_agents,
                "agent_id": range(n_agents),
                "age": agents_state.age,  # JAX сам конвертирует в numpy при доступе
                "income": agents_state.income,
                "savings": agents_state.savings,
                "is_employed": agents_state.is_employed,
            }
        )

        # 2. Bulk Insert (очень быстро в DuckDB)
        self.conn.execute("INSERT INTO agents_snapshot SELECT * FROM df")
        logger.debug(f"DataFrame shape: {df.shape}")  # Используем df для отладки
        logger.info(f"💾 Snapshot saved: {n_agents:,} agents at step {step}")

    def close(self):
        self.conn.close()

    def save_run_record(self, record: "RunRecord") -> None:
        payload = record.model_dump()
        generator = payload.pop("generator", {})
        library_versions = json.dumps(payload.pop("library_versions", {}))
        flags = json.dumps(payload.pop("flags", {}))
        self.conn.execute(
            """
            INSERT INTO run_records (
                run_id,
                parent_run_id,
                seed,
                repro_mode,
                backend,
                python_version,
                platform,
                generated_at,
                schema_version,
                generator_name,
                generator_version,
                library_versions,
                flags
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                payload["run_id"],
                payload.get("parent_run_id"),
                payload["seed"],
                payload["repro_mode"],
                payload["backend"],
                payload["python_version"],
                payload["platform"],
                payload["generated_at"],
                payload["schema_version"],
                generator.get("name"),
                generator.get("version"),
                library_versions,
                flags,
            ],
        )
        logger.info(f"🧾 RunRecord saved: {payload['run_id']}")
