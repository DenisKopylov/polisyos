import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# check_udf.py
from polisyos.fabric.io.db import SimulationDB  # noqa: E402
from polisyos.ir.analytics.data_views import AccessTier, DataFilter, DataViewRequest  # noqa: E402
from polisyos.fabric.udf.engine import UDFEngine  # noqa: E402
from polisyos.common.logger import logger  # noqa: E402


def main():
    logger.info("👓 Starting Data View Check...")

    # 1. Подключаемся к существующей БД (там уже должны быть данные от прошлого прогона)
    db = SimulationDB()
    udf = UDFEngine(db)

    # 2. Сценарий 1: LLM просит "Дай мне динамику ВВП и безработицы за шаги 1-5"
    req_panel = DataViewRequest(
        request_id="req_001",
        run_id="demo_run",
        view_type="panel",
        metrics=["gdp", "unemployment_rate"],
        step_start=1,
        step_end=5,
        access_tier=AccessTier.PUBLIC,
    )

    logger.info("--- TEST 1: Macro Panel ---")
    df_panel = udf.query(req_panel)
    print(df_panel)

    if not df_panel.empty:
        logger.success("✅ Panel View works!")
    else:
        logger.warning(
            "⚠️ Panel is empty (maybe DB is empty? Run tools/demos/run_export_demo.py first)"
        )

    # 3. Сценарий 2: LLM просит "Какой средний доход у безработных на шаге 6?"
    req_snap = DataViewRequest(
        request_id="req_002",
        run_id="demo_run",
        view_type="snapshot",
        metrics=["income"],
        aggregation="mean",
        step_end=6,
        filters=[DataFilter(column="is_employed", op="==", value=False)],
        access_tier=AccessTier.INTERNAL,
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
