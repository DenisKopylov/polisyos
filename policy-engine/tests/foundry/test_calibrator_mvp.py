from decimal import Decimal

import jax.numpy as jnp
import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.contracts.foundry import (
    ExecPlan,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
    PolicySurfaceIRRef,
)
from polisyos.foundry.calibration.calibrator import Calibrator, CalibratorInputs
from polisyos.foundry.domain.state import GlobalState
from polisyos.ir.calibration import CalibrationConfig, CalibrationTarget, TrainableParamRef
from polisyos.ir.kernel.constraints import DEFAULT_CONSTRAINT_REGISTRY
from polisyos.ir.kernel.mechanisms import (
    DEFAULT_MECHANISM_REGISTRY,
    MechanismTypeRegistry,
    MechanismTypeSpec,
    ParamSpec,
    ParamType,
)
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY


def _dummy_artifact() -> ArtifactID:
    return ArtifactID.from_sha256_hex("0" * 64)


def _build_graph(nodes: list[ProgramNode]) -> tuple[ProgramGraph, ExecPlan]:
    dummy_id = _dummy_artifact()
    policy_ref = PolicySurfaceIRRef(artifact_id=dummy_id)
    program_ref = ProgramGraphRef(artifact_id=dummy_id)
    program_graph = ProgramGraph(ir_ref=policy_ref, nodes=nodes, edges=[], entrypoints=[])
    exec_plan = ExecPlan(program_ref=program_ref, order=[node.node_id for node in nodes])
    return program_graph, exec_plan


def _base_state(n_agents: int = 5) -> GlobalState:
    base_state = GlobalState.empty(n_agents=n_agents, n_firms=1)
    return base_state.replace(
        agents=base_state.agents.replace(
            income=jnp.ones(n_agents) * 100.0,
            reported_income=jnp.ones(n_agents) * 100.0,
        ),
        government_balance=jnp.array(0.0),
    )


def test_calibrator_recovers_income_tax_rate():
    n_agents = 5
    base_state = _base_state(n_agents=n_agents)

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
        hessian={"enabled": False},
    )

    node = ProgramNode(
        node_id="tax",
        node_kind="mechanism",
        mechanism_type="income_tax",
        params_ref=None,
        outputs=["agents.income", "government.balance"],
    )
    program_graph, exec_plan = _build_graph([node])

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
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
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
    assert report.fit_quality is not None


def test_calibrator_resolves_slot_id_metric():
    n_agents = 3
    base_state = _base_state(n_agents=n_agents)
    target_series = jnp.array([30.0], dtype=jnp.float32)
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="gov_balance",
                model_metric_path="government.balance",
                fabric_query=None,
            )
        ],
        max_steps=40,
        learning_rate=0.1,
        seed=0,
        hessian={"enabled": False},
    )

    node = ProgramNode(
        node_id="tax",
        node_kind="mechanism",
        mechanism_type="income_tax",
        params_ref=None,
        outputs=["agents.income", "government.balance"],
    )
    program_graph, exec_plan = _build_graph([node])

    def loader(_):
        return {"params": {"rate": 0.3}, "schedule": {"start_step": 0, "end_step": 10}}

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
        raw_targets={"gov_balance": target_series},
        controls_seq=jnp.arange(target_series.shape[0]),
    )

    report = Calibrator(inputs).run()
    calibrated_rate = report.calibrated_params.get("tax.rate")
    assert calibrated_rate is not None
    assert pytest.approx(0.1, rel=0.2) == calibrated_rate


def test_calibrator_trainable_filtering():
    base_state = _base_state(n_agents=1)
    target_series = jnp.array([20.0], dtype=jnp.float32)
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="gov_balance",
                model_metric_path="government_balance",
                fabric_query=None,
            )
        ],
        trainables=[TrainableParamRef(param_id="rate", node_id="tax")],
        max_steps=40,
        learning_rate=0.1,
        seed=0,
        hessian={"enabled": False},
    )

    nodes = [
        ProgramNode(
            node_id="tax",
            node_kind="mechanism",
            mechanism_type="income_tax",
            params_ref=None,
            outputs=["agents.income", "government.balance"],
        ),
        ProgramNode(
            node_id="subsidy",
            node_kind="mechanism",
            mechanism_type="tax_subsidy",
            params_ref=None,
            outputs=["agents.income", "government.balance"],
        ),
    ]
    program_graph, exec_plan = _build_graph(nodes)

    def loader(node):
        node_id = getattr(node, "node_id", "")
        rate = 0.2 if node_id == "tax" else 0.3
        return {"params": {"rate": rate}, "schedule": {"start_step": 0, "end_step": 10}}

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
        raw_targets={"gov_balance": target_series},
        controls_seq=jnp.arange(target_series.shape[0]),
    )

    report = Calibrator(inputs).run()
    assert pytest.approx(0.3, rel=1e-6) == report.calibrated_params["subsidy.rate"]


def test_calibrator_constraint_penalty():
    base_state = _base_state(n_agents=1)
    target_series = jnp.array([0.0], dtype=jnp.float32)
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="gov_balance",
                model_metric_path="government_balance",
                fabric_query=None,
                loss={"weight": 0.0},
            )
        ],
        max_steps=10,
        learning_rate=0.05,
        seed=0,
        constraint_loss={"enabled": True, "weight": 1.0},
        constraint_values={"min_balance": 1000.0},
        hessian={"enabled": False},
    )

    node = ProgramNode(
        node_id="tax",
        node_kind="mechanism",
        mechanism_type="income_tax",
        params_ref=None,
        outputs=["agents.income", "government.balance"],
    )
    program_graph, exec_plan = _build_graph([node])

    def loader(_):
        return {"params": {"rate": 0.1}, "schedule": {"start_step": 0, "end_step": 10}}

    inputs = CalibratorInputs(
        config=config,
        program_graph=program_graph,
        exec_plan=exec_plan,
        base_state=base_state,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        constraint_registry=DEFAULT_CONSTRAINT_REGISTRY,
        parameter_loader=loader,
        raw_targets={"gov_balance": target_series},
        controls_seq=jnp.arange(target_series.shape[0]),
    )

    report = Calibrator(inputs).run()
    assert report.total_loss > sum(report.per_target_loss.values())


def test_calibrator_prior_penalty():
    base_state = _base_state(n_agents=1)
    target_series = jnp.array([0.0], dtype=jnp.float32)
    mechanism_registry = MechanismTypeRegistry(
        mechanisms={
            "income_tax": MechanismTypeSpec(
                mechanism_id="income_tax",
                params={
                    "rate": ParamSpec(
                        param_id="rate",
                        required=True,
                        value_type=ParamType.RATE,
                        min_value=Decimal("0"),
                        max_value=Decimal("1"),
                        trainable=True,
                        prior_mean=Decimal("0.5"),
                        prior_std=Decimal("0.1"),
                        unit_id="ratio",
                    )
                },
                reads_slots=["agents.reported_income"],
                writes_slots=["agents.income", "government.balance"],
                default_merge={"agents.income": "sum", "government.balance": "sum"},
            )
        }
    )
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="gov_balance",
                model_metric_path="government_balance",
                fabric_query=None,
                loss={"weight": 0.0},
            )
        ],
        max_steps=1,
        learning_rate=1e-6,
        seed=0,
        prior_loss={"enabled": True, "weight": 1.0},
        hessian={"enabled": False},
    )

    node = ProgramNode(
        node_id="tax",
        node_kind="mechanism",
        mechanism_type="income_tax",
        params_ref=None,
        outputs=["agents.income", "government.balance"],
    )
    program_graph, exec_plan = _build_graph([node])

    def loader(_):
        return {"params": {"rate": 0.1}, "schedule": {"start_step": 0, "end_step": 10}}

    inputs = CalibratorInputs(
        config=config,
        program_graph=program_graph,
        exec_plan=exec_plan,
        base_state=base_state,
        mechanism_registry=mechanism_registry,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        parameter_loader=loader,
        raw_targets={"gov_balance": target_series},
        controls_seq=jnp.arange(target_series.shape[0]),
    )

    report = Calibrator(inputs).run()
    calibrated_rate = report.calibrated_params["tax.rate"]
    expected = ((calibrated_rate - 0.5) / (0.1 + config.prior_loss.epsilon)) ** 2
    assert pytest.approx(expected, rel=1e-3) == report.total_loss


def test_calibrator_gradnorm_updates_weights():
    base_state = _base_state(n_agents=1)
    targets = {
        "gov_balance": jnp.array([1000.0], dtype=jnp.float32),
        "avg_income": jnp.array([10.0], dtype=jnp.float32),
    }
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="gov_balance",
                model_metric_path="government_balance",
                fabric_query=None,
                loss={"relative": False, "weight": 1.0},
            ),
            CalibrationTarget(
                target_id="avg_income",
                model_metric_path="agents.income",
                fabric_query=None,
                aggregation="mean",
            ),
        ],
        max_steps=5,
        learning_rate=0.1,
        seed=0,
        grad_norm={"enabled": True, "update_every": 1, "lr": 0.5},
        hessian={"enabled": False},
    )

    node = ProgramNode(
        node_id="tax",
        node_kind="mechanism",
        mechanism_type="income_tax",
        params_ref=None,
        outputs=["agents.income", "government.balance"],
    )
    program_graph, exec_plan = _build_graph([node])

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
        raw_targets=targets,
        controls_seq=jnp.arange(1),
    )

    report = Calibrator(inputs).run()
    weights = report.target_weights
    assert abs(weights["gov_balance"] - weights["avg_income"]) > 1e-3


def test_calibrator_hessian_uncertainty():
    base_state = _base_state(n_agents=1)
    target_series = jnp.array([10.0], dtype=jnp.float32)
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="gov_balance",
                model_metric_path="government_balance",
                fabric_query=None,
            )
        ],
        max_steps=20,
        learning_rate=0.1,
        seed=0,
        hessian={"enabled": True, "damping": 1e-6},
    )

    node = ProgramNode(
        node_id="tax",
        node_kind="mechanism",
        mechanism_type="income_tax",
        params_ref=None,
        outputs=["agents.income", "government.balance"],
    )
    program_graph, exec_plan = _build_graph([node])

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
        raw_targets={"gov_balance": target_series},
        controls_seq=jnp.arange(target_series.shape[0]),
    )

    report = Calibrator(inputs).run()
    uncertainties = report.uncertainties
    assert uncertainties is not None
    assert len(uncertainties.params) == 1
    assert len(uncertainties.std) == 1
    assert len(uncertainties.correlation) == 1
    assert pytest.approx(1.0, rel=1e-6) == uncertainties.correlation[0][0]
