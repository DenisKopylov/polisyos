from pathlib import Path

import jax.numpy as jnp
import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import ExecPlan, ProgramGraph, ProgramGraphRef, ProgramNode
from polisyos.fabric.io.db import SimulationDB
from polisyos.foundry.calibration.calibrator import Calibrator, CalibratorInputs
from polisyos.foundry.domain.state import GlobalState
from polisyos.ir.calibration import CalibrationConfig, CalibrationTarget
from polisyos.ir.data_views import AccessTier, DataViewRequest, DataViewType
from polisyos.ir.kernel.mechanisms import DEFAULT_MECHANISM_REGISTRY
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY

pytestmark = pytest.mark.integration


def _dummy_artifact() -> ArtifactID:
    return ArtifactID.from_sha256_hex("0" * 64)


def test_calibrator_fetches_targets_from_udf(tmp_path: Path) -> None:
    pytest.importorskip("kuzu")
    from polisyos.fabric.udf.engine import UDFEngine
    db_path = tmp_path / "calibration.duckdb"
    cas_root = tmp_path / ".polisyos"
    db = SimulationDB(str(db_path))
    db.save_macro(
        [
            {
                "run_id": "calib_run",
                "step": 0,
                "gdp": 1.0,
                "unemployment_rate": 0.1,
                "inflation_rate": 0.0,
                "avg_price": 1.0,
                "avg_income": 100.0,
                "government_balance": 10.0,
                "timestamp": None,
            },
            {
                "run_id": "calib_run",
                "step": 1,
                "gdp": 1.0,
                "unemployment_rate": 0.1,
                "inflation_rate": 0.0,
                "avg_price": 1.0,
                "avg_income": 100.0,
                "government_balance": 20.0,
                "timestamp": None,
            },
        ]
    )

    curated_dir = Path(__file__).resolve().parents[2] / "data" / "curated"
    udf = UDFEngine(db, curated_dir=curated_dir, cas_root=cas_root)

    try:
        request = DataViewRequest(
            request_id="calib",
            run_id="calib_run",
            view_type=DataViewType.PANEL,
            metrics=["government_balance"],
            step_start=0,
            step_end=1,
            access_tier=AccessTier.PUBLIC,
        )
        config = CalibrationConfig(
            targets=[
                CalibrationTarget(
                    target_id="gov_balance",
                    model_metric_path="government_balance",
                    fabric_query=request.model_dump(),
                    align={"time_column": "step"},
                )
            ],
            max_steps=5,
            learning_rate=0.1,
            seed=0,
            hessian={"enabled": False},
        )

        dummy_id = _dummy_artifact()
        policy_ref = ArtifactRef(
            artifact_id=dummy_id,
            kind="ir.trinity_bundle",
            media_type="application/json",
        )
        program_ref = ProgramGraphRef(artifact_id=dummy_id)
        node = ProgramNode(
            node_id="tax",
            node_kind="mechanism",
            mechanism_type="income_tax",
            params_ref=None,
            outputs=["agents.income", "government.balance"],
        )
        program_graph = ProgramGraph(ir_ref=policy_ref, nodes=[node], edges=[], entrypoints=[])
        exec_plan = ExecPlan(program_ref=program_ref, order=["tax"])

        base_state = GlobalState.empty(n_agents=1, n_firms=1)
        base_state = base_state.replace(
            agents=base_state.agents.replace(
                income=jnp.array([100.0]),
                reported_income=jnp.array([100.0]),
            ),
            government_balance=jnp.array(0.0),
        )

        def loader(_):
            return {"params": {"rate": 0.2}, "schedule": {"start_step": 0, "end_step": 10}}

        inputs = CalibratorInputs(
            config=config,
            program_graph=program_graph,
            exec_plan=exec_plan,
            base_state=base_state,
            mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            selector_field_registry=None,
            parameter_loader=loader,
            udf_engine=udf,
            controls_seq=jnp.arange(2),
        )

        report = Calibrator(inputs).run()
        series = report.series_comparison["gov_balance"].real
        assert series == [10.0, 20.0]
        assert report.series_comparison["gov_balance"].time == [0.0, 1.0]
    finally:
        db.close()
