# check_udf.py
from src.io.db import SimulationDB  # noqa: E402
from src.udf.engine import UDFEngine  # noqa: E402
from src.udf.schema import DataFilter, DataViewRequest  # noqa: E402
from src.utils.logger import logger  # noqa: E402


def main():
    logger.info("👓 Starting Data View Check...")

    # 1. Подключаемся к существующей БД (там уже должны быть данные от прошлого прогона)
    db = SimulationDB()
    udf = UDFEngine(db)

    # 2. Сценарий 1: LLM просит "Дай мне динамику ВВП и безработицы за шаги 1-5"
    req_panel = DataViewRequest(
        request_id="req_001",
        view_type="panel",
        metrics=["gdp", "unemployment_rate"],
        step_start=1,
        step_end=5,
    )

    logger.info("--- TEST 1: Macro Panel ---")
    df_panel = udf.query(req_panel)
    print(df_panel)

    if not df_panel.empty:
        logger.success("✅ Panel View works!")
    else:
        logger.warning("⚠️ Panel is empty (maybe DB is empty? Run check_export.py first)")

    # 3. Сценарий 2: LLM просит "Какой средний доход у безработных на шаге 6?"
    req_snap = DataViewRequest(
        request_id="req_002",
        view_type="snapshot",
        metrics=["income"],
        aggregation="mean",
        step_end=6,
        filters=[DataFilter(column="is_employed", op="==", value=False)],
    )

    logger.info("\n--- TEST 2: Unemployment Analysis (Snapshot) ---")
    df_snap = udf.query(req_snap)
    print(df_snap)

    if not df_snap.empty:
        logger.success("✅ Snapshot Aggregation works!")
    else:
        logger.warning("⚠️ Snapshot empty")

    db.close()


if __name__ == "__main__":
    main()
