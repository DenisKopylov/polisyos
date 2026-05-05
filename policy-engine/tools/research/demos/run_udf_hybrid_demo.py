import sys

from tools.lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# check_step2.py
import os
import shutil

from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.io.graph_store import GraphStore
from polisyos.fabric.udf.engine import UDFEngine
from polisyos.fabric.udf.schema import AccessTier, DataViewRequest, DataViewType


def main():
    print("--- 1. Init Stores ---")
    if os.path.exists("test_udf.duckdb"):
        os.remove("test_udf.duckdb")
    if os.path.exists("test_udf.kuzu"):
        if os.path.isdir("test_udf.kuzu"):
            shutil.rmtree("test_udf.kuzu")
        else:
            os.remove("test_udf.kuzu")

    duck_db = SimulationDB("test_udf.duckdb")
    graph_db = GraphStore("test_udf.kuzu")

    # Заполняем DuckDB (Макро)
    print("--- 2. Ingest Data (Simulated) ---")
    duck_db.conn.execute(
        "INSERT INTO macro_history VALUES ('run_1', 1, 100.0, 0.05, 0.02, 10.0, 50.0, 1000.0, current_timestamp)"
    )

    # Заполняем KùzuDB (Граф)
    # Агент A платит Агенту B
    graph_db.add_agent("firm_a", "firm")
    graph_db.add_agent("gov_budget", "gov")
    graph_db.add_agent("worker_x", "person")

    graph_db.add_interaction("firm_a", "gov_budget", step=1, amount=500.0, type_="tax")
    graph_db.add_interaction("gov_budget", "worker_x", step=2, amount=100.0, type_="subsidy")

    engine = UDFEngine(duck_db, graph_db)

    print("--- 3. Test Relational Query (Panel) ---")
    req_panel = DataViewRequest(
        request_id="req1",
        run_id="run_1",
        view_type=DataViewType.PANEL,
        metrics=["gdp", "inflation_rate"],
        access_tier=AccessTier.PUBLIC,
    )
    df_panel = engine.query(req_panel)
    print("DuckDB Result:")
    print(df_panel)
    assert not df_panel.empty, "Panel DF is empty"

    print("\n--- 4. Test Graph Query (Network) ---")
    req_network = DataViewRequest(
        request_id="req2",
        run_id="run_1",
        view_type=DataViewType.NETWORK,
        metrics=["neighbor_id", "amount"],
        ego_node_id="firm_a",  # Ищем связи Firm A
        hop_depth=2,  # Должен найти Worker X через Budget
        access_tier=AccessTier.INTERNAL,
    )
    df_net = engine.query(req_network)
    print("KùzuDB Result (Neighbors of firm_a):")
    print(df_net)

    # Проверка: Firm A -> Budget -> Worker X. Worker X должен быть в выдаче (depth 2)
    assert "worker_x" in df_net["neighbor_id"].values, (
        "Graph traversal failed to find 2nd hop neighbor"
    )

    print("\n✅ Step 2 Complete: UDF supports both SQL and Graph queries!")


if __name__ == "__main__":
    main()
