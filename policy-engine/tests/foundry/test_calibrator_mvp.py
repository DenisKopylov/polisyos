import jax
import jax.numpy as jnp
import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.contracts.foundry import ExecPlan, ProgramGraph, ProgramGraphRef, ProgramNode, PolicySurfaceIRRef
from polisyos.foundry.calibration.calibrator import Calibrator, CalibratorInputs
from polisyos.foundry.domain.state import GlobalState
from polisyos.ir.calibration import CalibrationConfig, CalibrationTarget
from polisyos.ir.kernel.mechanisms import DEFAULT_MECHANISM_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY


def _dummy_artifact() -> ArtifactID:
    return ArtifactID.from_sha256_hex("0" * 64)


def test_calibrator_recovers_income_tax_rate():
    n_agents = 5
    base_state = GlobalState.empty(n_agents=n_agents, n_firms=1)
    base_state = base_state.replace(
        agents=base_state.agents.replace(income=jnp.ones(n_agents) * 100.0),
        government_balance=jnp.array(0.0),
    )

    # Один шаг: ожидаем баланс ~ 50.0 при истинном rate=0.1
    target_series = jnp.array([50.0], dtype=jnp.float32)
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="gov_balance",
                model_metric_path="government_balance",
                fabric_query=None,
            )
        ],
        max_steps=60,
        learning_rate=0.1,
        seed=0,
    )

    dummy_id = _dummy_artifact()
    policy_ref = PolicySurfaceIRRef(artifact_id=dummy_id)
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

    def loader(_):
        # Стартовое значение ближе к 0.3, чтобы калибровка сходилась к 0.1
        return {"params": {"rate": 0.3}, "schedule": {"start_step": 0, "end_step": 100}}

    inputs = CalibratorInputs(
        config=config,
        program_graph=program_graph,
        exec_plan=exec_plan,
        base_state=base_state,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        selector_field_registry=None,
        parameter_loader=loader,
        raw_targets={"gov_balance": target_series},
        controls_seq=jnp.arange(target_series.shape[0]),
    )

    calibrator = Calibrator(inputs)
    report = calibrator.run()

    calibrated_rate = report.calibrated_params.get("tax.rate")
    assert calibrated_rate is not None
    # Ожидаем, что калибратор приблизится к истинному 0.1 (допускаем 20% погрешность)
    assert pytest.approx(0.1, rel=0.2) == calibrated_rate
    assert report.total_loss < 1.0
