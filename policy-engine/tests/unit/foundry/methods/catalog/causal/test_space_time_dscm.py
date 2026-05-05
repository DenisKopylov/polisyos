from __future__ import annotations

import numpy as np
import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.causal import (
    FieldNode,
    OperatorEdge,
    SpaceTimeDomain,
    SpaceTimeDSCM,
    SpaceTimeFieldData,
    SpaceTimeIdentificationStatus,
    SpaceTimeIntervention,
    SpaceTimeInterventionType,
    SpaceTimeSPDEGComputation,
    SpaceTimeSupport,
    SPDEGenerator,
    SPDEMechanism,
    build_space_time_identification_certificate,
    ensure_causal_methods_registered,
    estimate_space_time_spde_g_computation,
    estimate_space_time_treatment_density_process,
    simulate_linear_diffusion_response,
    simulate_reaction_diffusion_response,
)
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import EstimationStatus
from polisyos.ir.analytics.phase4_dynamics import load_space_time_causal_certificate


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _fixture_fields() -> tuple[SpaceTimeFieldData, np.ndarray, dict[str, float]]:
    time_grid = np.linspace(0.0, 0.5, 41)
    space_grid = np.linspace(0.0, 1.0, 31)
    shape = (time_grid.shape[0], space_grid.shape[0])
    baseline = np.zeros(shape, dtype=float)
    policy = baseline.copy()
    source_mask = space_grid <= 0.25
    pulse_mask = (time_grid >= 0.05) & (time_grid <= 0.15)
    policy[np.ix_(pulse_mask, source_mask)] = 1.0
    coefficients = {
        "kappa": 0.035,
        "treatment_effect": 1.7,
        "confounder_effect": 0.0,
        "intercept": 0.0,
    }
    outcome = simulate_linear_diffusion_response(
        time_grid=time_grid,
        space_grid=space_grid,
        treatment_field=baseline,
        kappa=coefficients["kappa"],
        treatment_effect=coefficients["treatment_effect"],
    )
    data = SpaceTimeFieldData(
        outcome_field=outcome,
        treatment_field=baseline,
        time_grid=time_grid,
        space_grid=space_grid,
    )
    return data, policy, coefficients


def _region_time_average(
    field: np.ndarray,
    *,
    time_grid: np.ndarray,
    space_grid: np.ndarray,
    region_bounds: tuple[float, float],
    time_window: tuple[float, float],
) -> float:
    region_mask = (space_grid >= region_bounds[0]) & (space_grid <= region_bounds[1])
    time_mask = (time_grid >= time_window[0]) & (time_grid <= time_window[1])
    sub = field[np.ix_(time_mask, region_mask)]
    selected_space = space_grid[region_mask]
    selected_time = time_grid[time_mask]
    space_integral = np.trapezoid(sub, selected_space, axis=1)
    total_integral = np.trapezoid(space_integral, selected_time)
    measure = (selected_time[-1] - selected_time[0]) * (selected_space[-1] - selected_space[0])
    return float(total_integral / measure)


def test_space_time_dscm_contracts_validate_operator_edges_and_certificate() -> None:
    domain = SpaceTimeDomain(id="omega", time_end=1.0, mesh={"n_nodes": 31})
    edge = OperatorEdge(source="A", target="Y", operator="K_AY", delayed=True)
    treatment = FieldNode(
        id="A",
        role="treatment_field",
        mechanism=SPDEMechanism(
            type="treatment_assignment",
            generator=SPDEGenerator.TREATMENT_ASSIGNMENT,
        ),
    )
    outcome = FieldNode(
        id="Y",
        role="outcome_field",
        mechanism=SPDEMechanism(
            generator=SPDEGenerator.DIFFUSION_REACTION,
            parents=("A",),
            operators=(edge,),
        ),
    )
    model = SpaceTimeDSCM(
        domain=domain,
        nodes=(treatment, outcome),
        operator_edges=(edge,),
        interventions=(
            SpaceTimeIntervention(
                id="pulse_R",
                type=SpaceTimeInterventionType.PERFECT_FIELD,
                target="A",
                support=SpaceTimeSupport(region_bounds=(0.0, 0.25), interval=(0.05, 0.15)),
                value=1.0,
            ),
        ),
    )

    data, policy, _ = _fixture_fields()
    certificate = build_space_time_identification_certificate(data, policy)

    assert model.operator_edges[0].operator == "K_AY"
    assert certificate.g_computation_allowed
    assert not certificate.ipw_allowed
    assert certificate.status is SpaceTimeIdentificationStatus.MODEL_EXTRAPOLATION
    assert "deterministic_field_interventions_are_singular_for_ipw" in certificate.caveats


def test_fem_spde_g_computation_matches_oracle_linear_policy_simulation(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    data, policy, coefficients = _fixture_fields()
    params = {
        "artifact_store": store,
        "policy_field": policy,
        "baseline_policy_field": np.zeros_like(policy),
        "coefficients": coefficients,
        "intervention_region_bounds": (0.0, 0.25),
        "intervention_interval": (0.05, 0.15),
        "outcome_region_bounds": (0.65, 1.0),
        "time_window": (0.15, 0.5),
        "impulse_lags": (0.0, 0.1, 0.2, 0.3),
    }

    result = estimate_space_time_spde_g_computation(data, params)

    oracle_policy = np.asarray(result.policy_surface, dtype=float)
    oracle_baseline = np.asarray(result.baseline_surface, dtype=float)
    expected = _region_time_average(
        oracle_policy - oracle_baseline,
        time_grid=data.time_grid,
        space_grid=data.space_grid,
        region_bounds=(0.65, 1.0),
        time_window=(0.15, 0.5),
    )
    assert result.policy_effect_region_time_average == pytest.approx(expected)
    assert result.green_kernel_summary["semantics"] == "operator_support_not_binary_adjacency"
    assert result.spillover_impulse_response["values"][-1] > 0.0
    assert result.positivity_report["g_computation_allowed"] is True
    assert result.space_time_causal_certificate.status == "model_extrapolation"
    assert result.space_time_causal_certificate_ref is not None
    loaded = load_space_time_causal_certificate(store, result.space_time_causal_certificate_ref)
    assert loaded == result.space_time_causal_certificate


def test_space_time_method_registers_and_emits_foundry_payload() -> None:
    ensure_causal_methods_registered()
    method_cls = MethodRegistry.get_instance().get("causal.space_time.fem_spde_g_computation@1.0.0")
    data, policy, coefficients = _fixture_fields()

    output = method_cls.pure_step(
        data,
        {
            "policy_field": policy,
            "baseline_policy_field": np.zeros_like(policy),
            "coefficients": coefficients,
            "intervention_region_bounds": (0.0, 0.25),
            "intervention_interval": (0.05, 0.15),
            "outcome_region_bounds": (0.65, 1.0),
            "time_window": (0.15, 0.5),
            "impulse_lags": (0.0, 0.2, 0.3),
        },
    )

    assert method_cls is SpaceTimeSPDEGComputation
    assert output["report"].status is EstimationStatus.SUCCESS
    assert output["result"]["identification_certificate"]["g_computation_allowed"] is True
    assert output["result"]["space_time_causal_certificate"]["certificate_type"] == (
        "space_time_causal_certificate"
    )
    assert output["positivity_report"]["ipw_allowed"] is False


def test_reaction_diffusion_policy_path_emits_convergence_diagnostics() -> None:
    time_grid = np.linspace(0.0, 0.6, 49)
    space_grid = np.linspace(0.0, 1.0, 33)
    shape = (time_grid.shape[0], space_grid.shape[0])
    baseline = np.zeros(shape, dtype=float)
    policy = baseline.copy()
    source_mask = space_grid <= 0.3
    pulse_mask = (time_grid >= 0.08) & (time_grid <= 0.2)
    policy[np.ix_(pulse_mask, source_mask)] = 0.45
    initial = 0.24 + 0.04 * np.cos(np.pi * space_grid)
    coefficients = {
        "kappa": 0.025,
        "treatment_effect": 0.8,
        "confounder_effect": 0.0,
        "intercept": 0.0,
        "reaction_rate": 0.35,
        "carrying_capacity": 1.2,
    }
    outcome = simulate_reaction_diffusion_response(
        time_grid=time_grid,
        space_grid=space_grid,
        treatment_field=baseline,
        initial_field=initial,
        kappa=coefficients["kappa"],
        treatment_effect=coefficients["treatment_effect"],
        growth_rate=coefficients["reaction_rate"],
        carrying_capacity=coefficients["carrying_capacity"],
    )
    data = SpaceTimeFieldData(
        outcome_field=outcome,
        treatment_field=baseline,
        time_grid=time_grid,
        space_grid=space_grid,
    )

    result = estimate_space_time_spde_g_computation(
        data,
        {
            "policy_field": policy,
            "baseline_policy_field": baseline,
            "coefficients": coefficients,
            "fit_reaction": True,
            "intervention_region_bounds": (0.0, 0.3),
            "intervention_interval": (0.08, 0.2),
            "outcome_region_bounds": (0.55, 1.0),
            "time_window": (0.2, 0.6),
            "compute_convergence": True,
        },
    )

    assert result.policy_effect_region_time_average > 0.0
    assert result.fitted_coefficients.reaction_rate == pytest.approx(0.35)
    assert "mesh_stride_2" in result.convergence_diagnostics["checks"]
    assert "time_stride_2" in result.convergence_diagnostics["checks"]
    assert "outcome_residual_diagnostics" in result.diagnostics


def test_stochastic_policy_ipw_and_dr_are_available_under_absolute_continuity() -> None:
    time_grid = np.linspace(0.0, 0.4, 33)
    space_grid = np.linspace(0.0, 1.0, 25)
    treatment = 0.35 + 0.08 * np.sin(2.0 * np.pi * time_grid[:, None]) * np.cos(
        np.pi * space_grid[None, :]
    )
    smooth_shift = 0.01 * np.sin(np.pi * time_grid[:, None]) * (space_grid[None, :] <= 0.5)
    policy = np.clip(
        treatment + smooth_shift,
        float(np.min(treatment)) + 1.0e-5,
        float(np.max(treatment)) - 1.0e-5,
    )
    coefficients = {
        "kappa": 0.02,
        "treatment_effect": 1.1,
        "confounder_effect": 0.0,
        "intercept": 0.0,
    }
    outcome = simulate_linear_diffusion_response(
        time_grid=time_grid,
        space_grid=space_grid,
        treatment_field=treatment,
        kappa=coefficients["kappa"],
        treatment_effect=coefficients["treatment_effect"],
    )
    data = SpaceTimeFieldData(
        outcome_field=outcome,
        treatment_field=treatment,
        time_grid=time_grid,
        space_grid=space_grid,
        baseline_treatment_field=treatment,
    )

    result = estimate_space_time_spde_g_computation(
        data,
        {
            "policy_field": policy,
            "baseline_is_observed": True,
            "coefficients": coefficients,
            "policy_mode": "stochastic",
            "policy_absolute_continuity": True,
            "compute_ipw": True,
            "compute_dr": True,
            "treatment_diffusion_scale": 2.5,
            "intervention_region_bounds": (0.0, 0.5),
            "outcome_region_bounds": (0.5, 1.0),
            "time_window": (0.1, 0.4),
        },
    )
    direct_ipw = estimate_space_time_treatment_density_process(
        data,
        policy,
        params={"treatment_diffusion_scale": 2.5},
        region_mask=(space_grid >= 0.5),
        time_mask=(time_grid >= 0.1) & (time_grid <= 0.4),
    )

    assert result.identification_certificate.status is SpaceTimeIdentificationStatus.IDENTIFIED_IPW
    assert result.ipw_result is not None
    assert result.ipw_result["status"] == "computed"
    assert result.doubly_robust_estimate is not None
    assert direct_ipw["status"] == "computed"
