import duckdb
import pandas as pd

from src.utils.logger import logger


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
                agent_id INTEGER,
                age INTEGER,
                income DOUBLE,
                savings DOUBLE,
                is_employed BOOLEAN
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
