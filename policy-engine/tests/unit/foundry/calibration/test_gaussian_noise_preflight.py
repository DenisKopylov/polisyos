"""Gaussian scalar admission through the actual configured calibration caller."""

from decimal import Decimal
from fractions import Fraction

import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import ExecPlan, ProgramGraph, ProgramGraphRef, ProgramNode
from polisyos.foundry.calibration import calibrator as calibrator_module
from polisyos.foundry.calibration.calibrator import Calibrator, CalibratorInputs
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.mechanisms.fiscal import IncomeTax
from polisyos.ir.analytics.calibration import CalibrationConfig, CalibrationTarget
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
)


@pytest.fixture
def configured_caller(monkeypatch):
    """Count genuine compilation/execution without replacing their outputs."""
    counts = {"loader": 0, "emitter": 0}
    original = IncomeTax.emit_patches

    def observed_emitter(self, *args, **kwargs):
        counts["emitter"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(IncomeTax, "emit_patches", observed_emitter)

    def make_inputs(scales, *, during_load=None):
        def loader(_):
            counts["loader"] += 1
            if during_load is not None:
                during_load()
            return {
                "params": {"rate": 0.25},
                "schedule": {"start_step": 0, "end_step": 0},
            }

        artifact_id = ArtifactID.from_sha256_hex("0" * 64)
        node = ProgramNode(
            node_id="tax",
            node_kind="mechanism",
            mechanism_type="income_tax",
            outputs=["agents.income", "government.balance"],
        )
        graph = ProgramGraph(
            ir_ref=ArtifactRef(
                artifact_id=artifact_id, kind="ir.trinity_bundle", media_type="application/json"
            ),
            nodes=[node],
            edges=[],
            entrypoints=[],
        )
        state = GlobalState.empty(n_agents=1, n_firms=1)
        state = state.replace(
            agents=state.agents.replace(
                income=jnp.array([100.0], dtype=jnp.float32),
                reported_income=jnp.array([100.0], dtype=jnp.float32),
            ),
            government_balance=jnp.array(0.0, dtype=jnp.float32),
        )
        config = CalibrationConfig(
            targets=[
                CalibrationTarget(
                    target_id="balance",
                    model_metric_path="government_balance",
                    loss={"relative": False},
                )
            ],
            steps=1,
            max_steps=1,
            seed=19,
            learning_rate=1e-9,
            hessian={"enabled": False},
        )
        return CalibratorInputs(
            config=config,
            program_graph=graph,
            exec_plan=ExecPlan(program_ref=ProgramGraphRef(artifact_id=artifact_id), order=["tax"]),
            base_state=state,
            mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            selector_field_registry=None,
            parameter_loader=loader,
            raw_targets={"balance": [20.0]},
            gaussian_observation_std=scales,
        )

    return make_inputs, counts


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        np.bool_(True),
        np.bool_(False),
        0.0,
        -1.0,
        np.nan,
        np.inf,
        -np.inf,
        complex(2.0, 0.0),
        "2.0",
        np.array(2.0),
        np.array([2.0]),
        Decimal("2.0"),
        10**1000,
    ],
    ids=[
        "bool-true",
        "bool-false",
        "numpy-bool-true",
        "numpy-bool-false",
        "zero",
        "negative",
        "nan",
        "inf",
        "negative-inf",
        "complex",
        "numeric-string",
        "zero-dimensional-array",
        "vector",
        "unsupported-decimal",
        "float-overflow",
    ],
)
def test_invalid_noise_scalar_refuses_before_loader_and_emitter(configured_caller, value):
    make_inputs, counts = configured_caller
    with pytest.raises(ValueError, match="finite positive real scalars"):
        Calibrator(make_inputs({"balance": value})).run()
    assert counts == {"loader": 0, "emitter": 0}


@pytest.mark.parametrize("scales", [True, [2.0], 2.0])
def test_noise_scales_require_mapping_before_callbacks(configured_caller, scales):
    make_inputs, counts = configured_caller
    with pytest.raises(ValueError, match="finite positive real scalars"):
        Calibrator(make_inputs(scales)).run()
    assert counts == {"loader": 0, "emitter": 0}


@pytest.mark.parametrize("value", [2.0, np.float32(2.0), np.float64(2.0), 2, Fraction(2)])
def test_positive_real_scalar_produces_actual_non_gating_gaussian_report(configured_caller, value):
    make_inputs, counts = configured_caller
    report = Calibrator(make_inputs({"balance": value})).run()
    profile = report.execution_context["objective_profile"]
    assert type(profile["observation_std"]["balance"]) is float
    assert profile["observation_std"] == {"balance": 2.0}
    assert profile["gate_eligible"] is False
    assert profile["row_law_basis"] == "consumer_asserted"
    # Native tax revenue=100*.25=25; NLL=.5*((25-20)/2)**2.
    assert report.total_loss == pytest.approx(3.125, abs=1e-5)
    assert counts["loader"] == 1
    assert counts["emitter"] > 0


@pytest.mark.parametrize("replacement", [True, np.nan])
def test_admitted_noise_values_are_frozen_before_parameter_loader(configured_caller, replacement):
    make_inputs, counts = configured_caller
    scales = {"balance": 2.0}
    inputs = make_inputs(scales, during_load=lambda: scales.update(balance=replacement))
    report = Calibrator(inputs).run()
    assert report.execution_context["objective_profile"]["observation_std"] == {"balance": 2.0}
    assert report.total_loss == pytest.approx(3.125, abs=1e-5)
    assert counts["loader"] == 1
    assert counts["emitter"] > 0


def test_target_join_remains_contextual(configured_caller):
    make_inputs, counts = configured_caller
    with pytest.raises(ValueError, match="exactly the target IDs"):
        Calibrator(make_inputs({"wrong_target": 2.0})).run()
    assert counts == {"loader": 1, "emitter": 0}


def test_bad_value_refuses_before_contextual_target_join(configured_caller):
    make_inputs, counts = configured_caller
    with pytest.raises(ValueError, match="finite positive real scalars"):
        Calibrator(make_inputs({"wrong_target": True})).run()
    assert counts == {"loader": 0, "emitter": 0}


def test_absent_gaussian_profile_preserves_generic_caller(configured_caller):
    make_inputs, counts = configured_caller
    report = Calibrator(make_inputs(None)).run()
    assert report.execution_context["objective_profile"] is None
    assert report.total_loss == pytest.approx(25.0, abs=1e-4)
    assert counts["loader"] == 1
    assert counts["emitter"] > 0


def test_property_removal_preserves_marker_but_breaks_admission(configured_caller, monkeypatch):
    make_inputs, counts = configured_caller
    monkeypatch.setattr(
        calibrator_module, "validate_gaussian_observation_std", lambda scales: dict(scales)
    )
    report = Calibrator(make_inputs({"balance": True})).run()
    assert report.execution_context["objective_profile"]["profile"] == "gaussian_observation_nll.v1"
    assert counts["loader"] == 1
    assert counts["emitter"] > 0
    with pytest.raises(AssertionError):
        assert counts == {"loader": 0, "emitter": 0}
