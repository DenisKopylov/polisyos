import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pandas as pd

from polisyos.fabric.ingestion import run_ingestion
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.io.graph_store import GraphStore
from polisyos.ir.data_views import AccessTier, DataViewRequest
from polisyos.fabric.udf.engine import UDFEngine


def write_raw_demo(raw_dir: Path) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)

    macro = pd.DataFrame(
        [
            {
                "run_id": "demo_run",
                "step": 0,
                "gdp": 1000.0,
                "unemployment_rate": 0.05,
                "inflation_rate": 1.0,
                "avg_price": 1.2,
                "avg_income": 900.0,
                "government_balance": 0.0,
            },
            {
                "run_id": "demo_run",
                "step": 1,
                "gdp": 1100.0,
                "unemployment_rate": 0.04,
                "inflation_rate": 1.2,
                "avg_price": 1.25,
                "avg_income": 950.0,
                "government_balance": -50.0,
            },
        ]
    )
    macro.to_csv(raw_dir / "macro.csv", index=False)

    agents = pd.DataFrame(
        [
            {
                "agent_id": "agent_1",
                "agent_type": "agent",
                "age": 30,
                "income": 900.0,
                "savings": 10.0,
                "is_employed": True,
            },
            {
                "agent_id": "agent_2",
                "agent_type": "agent",
                "age": 40,
                "income": 1100.0,
                "savings": 50.0,
                "is_employed": True,
            },
            {
                "agent_id": "agent_3",
                "agent_type": "agent",
                "age": 22,
                "income": 700.0,
                "savings": 5.0,
                "is_employed": False,
            },
        ]
    )
    agents.to_csv(raw_dir / "agents.csv", index=False)

    interactions = pd.DataFrame(
        [
            {"from_id": "agent_1", "to_id": "agent_2", "step": 0, "amount": 100.0, "type": "paid_tax"},
            {"from_id": "agent_2", "to_id": "agent_3", "step": 1, "amount": 50.0, "type": "transfer"},
        ]
    )
    interactions.to_csv(raw_dir / "interactions.csv", index=False)


def main() -> None:
    data_dir = Path("data")
    raw_dir = data_dir / "raw"
    staging_dir = data_dir / "staging"
    curated_dir = data_dir / "curated"
    db_path = Path("demo_udf.duckdb")
    kuzu_path = Path("demo_udf.kuzu")

    write_raw_demo(raw_dir)

    run_ingestion(
        raw_dir=raw_dir,
        staging_dir=staging_dir,
        curated_dir=curated_dir,
        db_path=db_path,
        kuzu_path=kuzu_path,
        source="demo_generator",
        license_name="CC0",
        clear_on_start=True,
    )

    db = SimulationDB(str(db_path))
    graph = GraphStore(str(kuzu_path))
    udf = UDFEngine(db, graph)

    panel_req = DataViewRequest(
        request_id="panel_demo",
        run_id="demo_run",
        view_type="panel",
        metrics=["gdp", "unemployment_rate"],
        step_start=0,
        step_end=1,
        access_tier=AccessTier.PUBLIC,
    )
    panel_df = udf.query(panel_req)
    print("Panel View:\n", panel_df)

    network_req = DataViewRequest(
        request_id="network_demo",
        run_id="demo_run",
        view_type="network",
        metrics=["neighbor_id", "amount", "type"],
        ego_node_id="agent_1",
        hop_depth=1,
        access_tier=AccessTier.INTERNAL,
    )
    network_df = udf.query(network_req)
    print("\nNetwork View:\n", network_df)

    db.close()


if __name__ == "__main__":
    main()
