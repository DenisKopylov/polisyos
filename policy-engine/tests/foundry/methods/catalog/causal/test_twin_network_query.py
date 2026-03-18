"""Tests for TwinNetworkQuery — Pearl's Abduction-Action-Prediction twin network.

Coverage:
  1. Basic linear chain: ITE = β * (x₁ − x₀), ite_std ≈ 0 (noise cancels)
  2. po_correlation ≈ 1.0 for linear models (shared noise → perfect correlation)
  3. Deterministic SCM (noise_std=0): ite_std = 0 exactly
  4. Abduction: factual_condition pins factual outcome deterministically
  5. store_distribution=False produces None distributions
  6. Output validates as TwinNetworkResult Pydantic model
  7. to_uncertainty_envelope() returns valid UncertaintyEnvelope
  8. TwinNetworkQuery is registered in the method catalog
"""
from __future__ import annotations

import math

import pytest

from polisyos.foundry.methods.catalog.causal.protocols import TwinNetworkQueryData
from polisyos.foundry.methods.catalog.causal.twin_network_query import TwinNetworkQuery
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.structural_causal_model import (
    MechanismFamily,
    MechanismSource,
    NodeMechanism,
    StructuralCausalModelSpec,
)
from polisyos.ir.analytics.twin_network import TwinNetworkResult
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope


# ── Fixtures ───────────────────────────────────────────────────────────────────


def _chain_scm(*, noise_std: float = 0.5) -> StructuralCausalModelSpec:
    """Simple linear chain X → Y: Y = 0.5 + 2.0 * X + U_Y (U_Y ~ N(0, noise_std))."""
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    return StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable="X",
                parents=[],
                family=MechanismFamily.EMPIRICAL,
                family_params={"mean": 0.0, "std": 1.0},
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="Y",
                parents=["X"],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 0.5,
                    "coefficients": {"X": 2.0},
                    "noise_std": noise_std,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        fitted=True,
        fit_method="gcm",
    )


def _fork_scm(*, noise_std: float = 0.5) -> StructuralCausalModelSpec:
    """Fork graph: Z → X, Z → Y, X → Y (confounded).
    Y = 1.5 * X + 0.8 * Z + U_Y.
    """
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["Z", "X", "Y"],
        edges=[
            CausalEdge(src="Z", dst="X"),
            CausalEdge(src="Z", dst="Y"),
            CausalEdge(src="X", dst="Y"),
        ],
    )
    return StructuralCausalModelSpec(
        graph=graph,
        mechanisms=[
            NodeMechanism(
                variable="Z",
                parents=[],
                family=MechanismFamily.EMPIRICAL,
                family_params={"mean": 0.0, "std": 1.0},
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="X",
                parents=["Z"],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 0.0,
                    "coefficients": {"Z": 1.0},
                    "noise_std": noise_std,
                },
                source=MechanismSource.DATA_FITTED,
            ),
            NodeMechanism(
                variable="Y",
                parents=["X", "Z"],
                family=MechanismFamily.LINEAR,
                family_params={
                    "intercept": 0.0,
                    "coefficients": {"X": 1.5, "Z": 0.8},
                    "noise_std": noise_std,
                },
                source=MechanismSource.DATA_FITTED,
            ),
        ],
        fitted=True,
        fit_method="gcm",
    )


def _run_twin_query(
    scm_spec: StructuralCausalModelSpec,
    *,
    treatment_variable: str = "X",
    outcome_variable: str = "Y",
    factual_treatment_value: float = 0.0,
    counterfactual_treatment_value: float = 1.0,
    factual_condition: dict | None = None,
    n_samples: int = 3000,
    seed: int = 42,
    store_distribution: bool = True,
) -> dict:
    payload = TwinNetworkQueryData(
        scm_spec=scm_spec,
        treatment_variable=treatment_variable,
        outcome_variable=outcome_variable,
        factual_treatment_value=factual_treatment_value,
        counterfactual_treatment_value=counterfactual_treatment_value,
        factual_condition=factual_condition or {},
        n_samples=n_samples,
    )
    return TwinNetworkQuery.pure_step(
        payload,
        params={"__seed__": seed, "store_distribution": store_distribution},
    )


# ── Test 1: basic chain ITE = β * (x₁ − x₀) ──────────────────────────────────


def test_basic_chain_ite_equals_true_effect() -> None:
    """For Y = 0.5 + 2.0*X + U, ITE = 2.0*(x₁−x₀) = 2.0 and ite_std ≈ 0."""
    result_dict = _run_twin_query(
        _chain_scm(noise_std=0.5),
        factual_treatment_value=0.0,
        counterfactual_treatment_value=1.0,
    )
    result = TwinNetworkResult.model_validate(result_dict["twin_network_result"])

    # ITE = 2.0 * (1.0 - 0.0) = 2.0 (noise cancels in shared-noise twin network)
    assert result.ite_mean == pytest.approx(2.0, abs=0.05)
    # Noise cancels → near-zero ITE variance
    assert result.ite_std < 0.05


def test_basic_chain_ite_scales_with_delta() -> None:
    """ITE scales linearly with the treatment delta."""
    result_dict = _run_twin_query(
        _chain_scm(noise_std=0.3),
        factual_treatment_value=0.0,
        counterfactual_treatment_value=2.0,
    )
    result = TwinNetworkResult.model_validate(result_dict["twin_network_result"])
    # ITE = 2.0 * 2.0 = 4.0
    assert result.ite_mean == pytest.approx(4.0, abs=0.1)


# ── Test 2: po_correlation ≈ 1 for linear models ──────────────────────────────


def test_po_correlation_near_one_for_linear_chain() -> None:
    """Shared noise in a linear model gives po_correlation ≈ 1.0."""
    result_dict = _run_twin_query(_chain_scm(noise_std=1.0), n_samples=5000)
    result = TwinNetworkResult.model_validate(result_dict["twin_network_result"])
    assert result.po_correlation >= 0.95


def test_po_correlation_near_one_for_confounded_scm() -> None:
    """Fork graph: shared noise across Z, X, Y still gives po_correlation ≈ 1."""
    result_dict = _run_twin_query(
        _fork_scm(noise_std=0.5),
        factual_treatment_value=0.0,
        counterfactual_treatment_value=1.0,
        n_samples=5000,
    )
    result = TwinNetworkResult.model_validate(result_dict["twin_network_result"])
    assert result.po_correlation >= 0.9


# ── Test 3: deterministic SCM → ite_std = 0 ───────────────────────────────────


def test_ite_std_zero_for_deterministic_scm() -> None:
    """Zero noise_std → all samples have the same ITE → ite_std = 0."""
    result_dict = _run_twin_query(_chain_scm(noise_std=0.0))
    result = TwinNetworkResult.model_validate(result_dict["twin_network_result"])
    assert result.ite_std == pytest.approx(0.0, abs=1e-10)
    # po_correlation = 1 for deterministic SCM
    assert result.po_correlation == pytest.approx(1.0, abs=1e-6)


# ── Test 4: abduction pins factual outcome ─────────────────────────────────────


def test_abduction_pins_factual_outcome() -> None:
    """With factual_condition {X:1.0, Y:2.5}, po_factual_mean should equal 2.5.

    Abduction infers U_Y = 2.5 - (0.5 + 2.0*1.0) = 0.0.
    In the factual world: Y(x₀=1.0) = 0.5 + 2.0*1.0 + 0.0 = 2.5 (deterministic).
    """
    result_dict = _run_twin_query(
        _chain_scm(noise_std=0.5),
        factual_treatment_value=1.0,
        counterfactual_treatment_value=0.0,
        factual_condition={"X": 1.0, "Y": 2.5},
        n_samples=100,
    )
    result = TwinNetworkResult.model_validate(result_dict["twin_network_result"])
    # Y's noise is abducted to 0 → factual outcome is pinned to 2.5
    assert result.po_factual_mean == pytest.approx(2.5, abs=0.01)
    # Counter: X=0, Y = 0.5 + 0 + 0 = 0.5
    assert result.po_counter_mean == pytest.approx(0.5, abs=0.01)
    # ITE = 0.5 - 2.5 = -2.0
    assert result.ite_mean == pytest.approx(-2.0, abs=0.01)


def test_abduction_with_partial_condition() -> None:
    """Abduction works when only some variables are observed."""
    result_dict = _run_twin_query(
        _chain_scm(noise_std=0.5),
        factual_treatment_value=0.0,
        counterfactual_treatment_value=1.0,
        factual_condition={"Y": 3.5},  # only observe Y, not X
        n_samples=500,
    )
    result = TwinNetworkResult.model_validate(result_dict["twin_network_result"])
    # Should not crash; produces valid result
    assert math.isfinite(result.ite_mean)
    assert result.ite_std >= 0.0


# ── Test 5: store_distribution=False ──────────────────────────────────────────


def test_store_distribution_false_gives_none_distributions() -> None:
    result_dict = _run_twin_query(_chain_scm(), store_distribution=False)
    result = TwinNetworkResult.model_validate(result_dict["twin_network_result"])
    assert result.ite_distribution is None
    assert result.po_factual_distribution is None
    assert result.po_counter_distribution is None


def test_store_distribution_true_gives_lists() -> None:
    result_dict = _run_twin_query(_chain_scm(), n_samples=100, store_distribution=True)
    result = TwinNetworkResult.model_validate(result_dict["twin_network_result"])
    assert result.ite_distribution is not None
    assert len(result.ite_distribution) == 100
    assert result.po_factual_distribution is not None
    assert result.po_counter_distribution is not None


# ── Test 6: output validates as TwinNetworkResult ─────────────────────────────


def test_twin_result_is_valid_pydantic_model() -> None:
    result_dict = _run_twin_query(_chain_scm())
    result = result_dict["twin_network_result"]
    # Should be a TwinNetworkResult instance directly
    assert isinstance(result, TwinNetworkResult)
    assert result.outcome_variable == "Y"
    # CI must be ordered
    lo, hi = result.ite_ci
    assert lo <= hi
    # po_correlation in [-1, 1]
    assert -1.0 <= result.po_correlation <= 1.0
    # std non-negative
    assert result.ite_std >= 0.0
    assert result.po_factual_std >= 0.0
    assert result.po_counter_std >= 0.0


def test_output_dict_has_required_keys() -> None:
    result_dict = _run_twin_query(_chain_scm())
    assert "twin_network_result" in result_dict
    assert "envelope" in result_dict
    assert "warnings" in result_dict
    assert "__determinism_tier__" in result_dict
    assert isinstance(result_dict["warnings"], list)


# ── Test 7: to_uncertainty_envelope() ────────────────────────────────────────


def test_twin_to_uncertainty_envelope() -> None:
    result_dict = _run_twin_query(_chain_scm())
    result = result_dict["twin_network_result"]
    envelope = result_dict["envelope"]
    assert isinstance(envelope, UncertaintyEnvelope)
    # Envelope point estimate should equal ite_mean
    assert envelope.point_estimate == pytest.approx(result.ite_mean, abs=1e-9)
    # CI matches
    assert envelope.confidence_interval[0] == pytest.approx(result.ite_ci[0], abs=1e-9)
    assert envelope.confidence_interval[1] == pytest.approx(result.ite_ci[1], abs=1e-9)
    assert envelope.confidence_level == pytest.approx(0.95, abs=1e-9)
    assert envelope.gate_eligible is True


# ── Test 8: registration ──────────────────────────────────────────────────────



def test_twin_network_query_registered() -> None:
    from polisyos.foundry.methods.catalog.causal import ensure_causal_methods_registered
    from polisyos.foundry.methods.registry import MethodRegistry

    MethodRegistry.reset_instance()
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    structural_names = {sig.name for sig in registry.query(namespace="causal.structural")}
    assert "twin_network_query" in structural_names
